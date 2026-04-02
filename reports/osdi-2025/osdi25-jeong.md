# Bayesian Code Diffusion for Efficient Automatic Deep Learning Program Optimization

**作者**：Isu Jeong, Seulki Lee（Ulsan National Institute of Science and Technology, UNIST）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/osdi25/presentation/jeong
**源文件**：[[osdi25-jeong.pdf]]

---

## 一、背景

深度学习编译器（如 TVM、Glow、XLA）通过中间表示（IR）将深度学习模型编译为针对不同硬件架构优化的程序代码，避免对硬件厂商特定库（如 cuDNN、MKL）的依赖。为了生成更高效的程序，auto-tuning 技术（如 AutoTVM、Ansor）被提出，自动搜索程序参数空间以找到最优的硬件特定优化配置。

然而，auto-tuning 面临严重的效率问题：搜索空间巨大、优化时间过长。以 Ansor 为代表的 auto-tuner 为每个子图独立构建搜索空间并随机初始化参数，导致大量冗余搜索。随着深度学习模型复杂度和硬件多样性的增加，编译优化时间成为瓶颈。

---

## 二、要解决的问题

现有 auto-tuning 方法存在三个关键不足：

1. **忽略子图相似性**：深度学习模型中大量子图结构相似（如 BERT 中 8 个子图有 5 个共享相同 sketch），但每个子图被分配独立的搜索空间和优化任务，未利用相似子图之间的参数复用机会。

2. **随机初始化低效**：现有方法（如 Ansor）通过随机参数初始化 + 进化搜索来寻找最优程序，起点随机导致需要大量迭代才能收敛，浪费搜索时间。

3. **Cost model 训练策略缺失**：cost model 在编译过程中从零开始在线训练，采用 round-robin 或梯度策略选择训练数据，导致数据过于多样化、模型收敛慢、预测精度不佳。

现有改进方法（如 TransferTuning、DietCode、FamilySeer、Selective Tuning）各自只解决部分问题，且存在硬件兼容性差（仅支持 CPU 或 GPU）、算子支持有限等局限。

---

## 三、洞察与设计

**关键洞察**：深度学习模型中结构相似的子图，其最优程序参数在搜索空间中也是彼此接近的。具体而言，共享相同 sketch（优化规则集合）的子图，其最优配置之间的余弦距离显著小于不同 sketch 子图之间的距离。因此，一个子图的最优参数可以作为其相似子图优化的良好起点。

基于这一洞察，论文提出 **Bayesian Code Diffusion** 框架，包含三个核心机制：

### 1. Sketch-based 子图聚类
按 sketch（优化规则集合）而非操作类型对子图聚类。相同 sketch 意味着相同的优化空间结构，使得参数在子图间的传播更加有效。

### 2. Prior 传播与 Code Diffusion
- 在每个聚类中选择一个 **prior 子图**（tensor 维度与其他子图最相似的那个），充分搜索找到其最优参数 θ*_p
- 将 θ*_p 作为 **posterior 子图**的初始参数，通过三种 diffusion 机制生成候选参数：
  - 若 prior 和 posterior 的 extent 相同，直接复用 length 参数
  - 若 extent 不同，按 extent 比例映射到最近的合法 divisor
  - 随机生成以保持多样性
- 迭代 diffuse 参数 θ_s^(t) = √(1-σ²) θ*_p + √σ² ε，在 prior 参数附近高概率区域搜索

### 3. Cost Model 的 Pre-training + Fine-tuning
- **Pre-training 阶段**：用不同聚类的 prior 子图数据训练 cost model，增强泛化能力
- **Fine-tuning 阶段**：逐个聚类用 posterior 子图数据微调，提升针对性预测精度

---

## 四、实现细节

- 在 Ansor（TVM）上实现，修改量较小
- **聚类**：基于 sketch 生成结果对子图分组（而非操作类型），同一 sketch 集合的子图归入同一 cluster
- **Prior 选择**：构建 tensor 维度相似度矩阵 S ∈ R^{N×N}，选择行平均相似度最高的子图作为 prior（公式 7）
- **Code Diffusion 实现**：修改 Ansor 的 `InitFillTileSize` 等参数初始化规则，在 split-step (SP) 的 length 参数上实施三种 diffusion 策略（直接复用、比例映射、随机），随机选择其一
- **距离度量**：将 schedule 编码为向量（优化规则 one-hot 编码 + 参数 zero-padding 对齐），用于聚类和相似度计算
- **Cost model**：使用 XGBoost（与 Ansor 相同），仅改变训练数据顺序——先 prior 数据 pre-train，再逐 cluster fine-tune
- 代码开源：https://github.com/eai-lab/BayesianCodeDiffusion

---

## 五、实验结果

**实验平台**：Intel Core i9-11900K CPU + Nvidia A6000 GPU

**模型**：ResNet-18、VGG-16/19、BERT、MobileNet、MobileNet-V2、SqueezeNet、Inception-V3、MXNet、EfficientNet（10 个模型）

**基线**：Ansor、FamilySeer、DietCode、ETO、Selective Tuning

### 端到端编译加速

| 指标 | CPU | GPU |
|------|-----|-----|
| 平均编译加速（vs Ansor） | **2.52×** | **2.00×** |
| 最大编译加速 | **3.31×**（MobileNet / SqueezeNet） | **2.79×** |
| 平均编译加速（vs 所有方法） | **1.95×** | — |

### 程序执行延迟（vs Ansor 最优 = 1.0）

| 阶段 | CPU | GPU |
|------|-----|-----|
| First-diffused latency | 1.00–1.21（起始即接近最优） | 1.15–1.65（起始远优于其他方法） |
| Last-diffused latency | 1.00–1.03 | 1.01–1.13（**GPU 上 VGG-19 达到 1.13× speedup**） |

### 关键发现
- 其他方法在多数配置下要么无法生成等效延迟的程序（×），要么不适用于特定硬件/算子（⊘）
- 子图 cluster 级别平均优化加速 2.11×
- Sketch sparsity 与 CPU 加速强相关（Pearson -0.70），operator sparsity 与 GPU 加速强相关（Pearson -0.58）
- 高相似度 prior 选择在 GPU 上优势更明显（l_h/l_l = 0.91）

---

## 六、批判性分析

1. **Bayesian 框架的"假设性"过强**：论文核心的贝叶斯公式（Eq. 1-5）建立在多个 "hypothetical" 分布假设上——f_min 的定义（Eq. 2）是一个非标准的指示函数而非真正的概率密度，θ_p 和 θ_s 的高斯分布假设也未经验证。实际实现中这些公式并未被直接计算，而是用启发式的三种 diffusion 方法近似。理论与实现之间存在较大 gap，Bayesian 框架更像是事后包装而非真正驱动设计。

2. **仅在 Ansor 上实现和评估**：虽然 Discussion 中讨论了向 MetaSchedule、TASO 的扩展可能性，但实际只在 Ansor 一个框架上验证。Ansor 本身已非最新 SOTA（TVM 社区已转向 MetaSchedule），实用价值有限。

3. **模型多样性不足**：评估模型以 CNN 为主（ResNet、VGG、MobileNet 等），Transformer 仅有 BERT。缺少对 LLM（GPT 类）、Diffusion Model 等现代大模型的评估，而这些模型的子图结构可能更复杂且重复性不同。

4. **"等效延迟"的比较标准可能有利于本方法**：Fig. 13 衡量的是"达到 Ansor 最优延迟所需时间的加速比"，而非在相同时间预算下的延迟比较。当其他方法被标记为 × 时，可能只是略慢但尚未收敛，这种二值化处理掩盖了差距大小。

5. **Sparsity 与加速的相关性分析缺乏因果解释**：Tab. 6 和 Fig. 18 显示 sketch/operator sparsity 与加速之间存在相关性，但 CPU 和 GPU 上主导因素不同的原因未被充分解释，仅做了相关性报告。

6. **单一硬件配置**：仅在一种 CPU 和一种 GPU 上评估，未验证跨硬件泛化能力（如 AMD CPU、不同代 Nvidia GPU 或 AI 加速器）。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴

1. **子图相似性利用是编译优化的通用思路**：现代 LLM 具有高度重复的 Transformer block 结构，子图相似性更强。将 code diffusion 思想应用到 LLM 编译（如 TensorRT-LLM、vLLM 的 kernel tuning）可能带来更大收益。

2. **Pre-training + Fine-tuning 策略可迁移到 kernel autotuning**：当前 AI Infra 中 kernel 调优（如 Triton autotuner）通常独立调优每个 kernel。可以借鉴本文的思路，用已调优的相似 kernel 配置初始化新 kernel 的搜索。

3. **Cost model 训练顺序的影响**：论文证明了仅改变训练数据顺序（不改架构）就能显著提升 cost model 性能，这对 AI Infra 中的性能预测模型设计有启发——数据 curriculum 可能比模型结构更重要。

### 值得跟进的方向

- **将 code diffusion 扩展到跨模型/跨硬件的 kernel 参数迁移**：例如从 A100 上调优过的 kernel 配置快速迁移到 H100
- **与 Triton/CUTLASS 等现代 kernel 库集成**：Triton 的 autotuner 目前是穷举搜索，code diffusion 可显著加速
- **将子图聚类思想用于 LLM serving 的 kernel 调度**：不同 batch size / sequence length 的请求可能共享相似的最优 kernel 配置

### 最有价值的切入点
将 Bayesian code diffusion 的核心思想（相似子图参数传播 + cost model pre-training/fine-tuning）移植到 Triton compiler 或 MetaSchedule 上，针对 LLM 推理场景（decoder-only Transformer 的高度重复结构）进行验证，这是最直接且高价值的延伸工作。

---

## 八、总结

Bayesian Code Diffusion 提出了一种基于贝叶斯框架的深度学习程序优化方法，核心思想是利用模型中相似子图的参数接近性，将已优化子图的参数传播给相似子图并在其附近搜索，同时通过 cost model 的 pre-training/fine-tuning 策略提升预测精度。在 Ansor 上的实现表明，该方法在 10 个模型、CPU 和 GPU 上均能以 2-3× 的编译加速达到等效或更优的程序执行延迟。主要局限在于理论框架的假设性较强、仅在 Ansor 单一平台验证、评估模型偏传统 CNN、以及缺乏跨硬件泛化验证。
