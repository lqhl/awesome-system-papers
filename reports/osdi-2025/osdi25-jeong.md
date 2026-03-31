# Bayesian Code Diffusion for Efficient Automatic Deep Learning Program Optimization

**作者**：Isu Jeong, Seulki Lee（蔚山国立科学技术大学，UNIST）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会），Boston, MA，2025年7月
**链接**：https://www.usenix.org/conference/osdi25/presentation/jeong
**源文件**：[osdi25-jeong.pdf](../../papers/osdi-2025/osdi25-jeong.pdf)

---

## 一、背景

深度学习模型的高效执行依赖于编译器将计算图转化为面向目标硬件（CPU、GPU 等）优化的底层程序。TVM、Glow、XLA 等深度学习编译器通过自动调优（auto-tuning）搜索最佳的程序参数（如循环分块大小、轴注解等），以最小化程序执行延迟。其中，Ansor 是当前最具代表性的 auto-tuning 框架，它自动构建搜索空间（sketch），通过随机初始化加进化搜索找到最优参数，并用在线学习的代价模型（cost model）预测候选程序性能。

然而，auto-tuning 过程极其耗时——在大型模型上可能需要数小时。随着深度学习模型规模持续扩大，编译优化时间已成为重要瓶颈。

---

## 二、要解决的问题

作者识别出当前 auto-tuning 方法（以 Ansor 为代表）的三个核心缺陷：

**1. 忽视子图相似性（Opportunity 1）**
深度学习模型的计算图被切分为多个子图分别优化，但模型中大量子图结构相似（如 BERT 中 8 个子图有 5 个共享相同的 sketch）。现有方法独立地为每个子图做搜索，浪费了可共享的优化信息。

**2. 随机初始化效率低下（Opportunity 2）**
Ansor 对每个子图随机初始化参数后再通过进化搜索精调，大量搜索时间花在远离最优解的区域。TransferTuning 等方法尝试复用参数，但需要预先编译好的参考程序，实用性有限。

**3. 代价模型缺乏学习策略（Opportunity 3）**
Ansor 的代价模型在编译过程中用轮询（round-robin）或梯度方式采样训练数据，数据来自异质的多个子图，导致模型训练样本过于多样、收敛慢、预测精度低。

---

## 三、核心设计

### Bayesian Code Diffusion 的核心思路

将深度学习程序优化问题重新表述为 Bayesian 推断问题。具体如下：

- **Prior 子图**：对每个子图聚类，选代表性子图作为 prior，充分搜索其最优参数 θ*_p。
- **Prior 传播（Prior Propagation）**：将 prior 子图的最优参数 θ*_p 传播给结构相似的 posterior 子图，作为其初始搜索空间的起点。
- **Code Diffusion**：在每次搜索迭代 t 中，从 θ*_p 出发对 posterior 参数进行扩散采样：

  ```
  θ_s^(t) = sqrt(1 - σ²_s,t) · θ*_p + sqrt(σ²_s,t) · ε,  ε ~ N(0, I)
  ```

  逐步将搜索空间从 prior 参数分布出发扩展，而非随机初始化。

### Sketch-based 子图聚类

基于 Ansor 生成的 sketch（优化规则序列）对子图聚类：共享相同 sketch 的子图归为一类，其参数空间结构相同，适合直接传播。

### 三种 Code Diffusion 机制

由于 prior 和 posterior 子图循环轴的 extent 可能不同，设计了三种扩散方式（随机选其一）：
1. **直接复用**：extent 相同时，直接复用 θ*_p 的 length 参数。
2. **比例扩散**：按 extent 比例缩放 θ*_p 的 length，选最近的合法因子。
3. **随机扰动**：保留随机化以提供多样性，防止陷入局部最优。

### 代价模型的 Pre-training + Fine-tuning

- **Pre-training**：先用所有 prior 子图的执行数据训练代价模型，覆盖多样性，提升泛化。
- **Fine-tuning**：再对每个子图聚类的 posterior 子图数据继续训练，提升对特定结构的预测精度。
- 代价模型架构不变（仍用 XGBoost），只调整训练数据顺序。

---

## 四、实现细节

- **实现基础**：在 Ansor（tvm@a340dbe）上实现，改动量小，可与现有框架无缝集成。
- **代码开源**：https://github.com/eai-lab/BayesianCodeDiffusion
- **Schedule 编码**：为计算子图参数间距离，将 schedule 编码为向量——11 种优化规则 one-hot 编码，参数列表 zero-padding 补齐，拼接后计算余弦相似度。
- **代价模型**：沿用 Ansor 的 XGBoost，不修改架构或输入特征，仅调整训练样本顺序。
- **Prior 选择策略**：在线估计 cluster 内子图间的 tensor shape 距离，选相似度最高的子图作 prior；cluster 大小越大，分配给 prior 的搜索时间越多。
- **搜索时间分配**：先将总时间按比例分配给各 prior 子图做充分搜索（pre-training 阶段），再通过 code diffusion 优化 posterior 子图，剩余时间用梯度方式进一步精调。

---

## 五、实验结果

**实验平台**：Intel Core i9-11900K（CPU）、NVIDIA A6000（GPU）

**对比方法**：Ansor、FamilySeer、DietCode、ETO、SelectiveTuning

**测试模型**：ResNet-18、VGG-16/19、BERT、MobileNet、MobileNetV2、SqueezeNet、InceptionV3、MXNet、EfficientNet

### 端到端编译加速（Fig. 13）

| 平台 | 相比 Ansor 平均加速 | 相比其他方法平均加速 | 最大加速 |
|------|---------------------|----------------------|---------|
| CPU | 2.52× | 1.95× | 3.31× |
| GPU | 2.00×（含所有对比方法） | — | 2.79× |

### 程序执行延迟（Table 4）

Bayesian code diffusion 在首次扩散后即可提供优于其他方法的执行延迟（如 MXNet on GPU 达 1.65× 首次延迟优势），完整优化后最优执行延迟达 1.13×（VGG-19 on GPU）。

### 子图聚类优化加速（Fig. 15）

对 cluster 内子图，平均子图编译加速 2.11×，相比 Ansor 取得等效或更低的执行延迟。

### 代价模型效果（Fig. 17）

Pre-training + Fine-tuning 策略在不改变代价模型结构的前提下，显著降低编译时间，提升程序延迟。

### 子图稀疏度分析（Table 6）

Sketch 稀疏度（子图间 sketch 差异程度）在 CPU 上与加速比强相关（Pearson -0.70），Operator 稀疏度在 GPU 上相关性更强（Pearson -0.58），说明 prior 传播主导 CPU 优化收益，代价模型策略更主导 GPU 收益。

---

## 六、批判性分析

**实验规模和硬件覆盖偏窄**：实验只在一块 CPU 和一块 GPU 上验证，缺乏对现代 AI 训练中常见的多 GPU 环境、不同 GPU 架构（如 H100、A100、T4）的评估。编译优化的效果高度依赖硬件微架构，单一平台的结论可信度存疑。

**与 Ansor 框架深度绑定**：代码扩散的具体实现（三种扩散机制、schedule 编码方式）紧密依赖 Ansor 的 sketch 表示和 split-step 结构，论文承认推广到 MetaSchedule 等其他框架需要额外适配，但未给出量化评估。

**Prior 选择的离线分析与在线估计的差距**：最优 prior 只能在完整编译后才能确认，在线时用 tensor shape 距离作代理指标，论文承认在某些情况下存在"更优 prior"被错过的问题，但未量化这一误差对整体性能的影响。

**Prior 搜索时间分配的超参数敏感性未充分分析**：prior 子图的时间分配按 cluster 大小比例决定，但这个策略的鲁棒性和对不同时间预算的敏感性缺乏消融实验。

**基线设置不够公平**：ETO、SelectiveTuning 等方法在 CPU 上标注为 "⊘"（不适用），DietCode 也只支持部分算子，实质上 Bayesian code diffusion 的主要对手只有 FamilySeer（CPU 和 GPU 均可用），但 FamilySeer 的加速比仅微弱优于 Ansor，这使对比中的"胜出"显得容易。

**代价模型改进效果缺乏独立消融**：pre-training/fine-tuning 策略的贡献无法从 code diffusion 本身的贡献中明确分离——论文仅在 Fig. 17 用"关闭 code diffusion 只测代价模型"的方式评估，但没有"只用 code diffusion 不用新训练策略"的对照实验。

---

## 七、AI Infra / MLSys 视角

**核心 insight 的迁移价值**：论文的核心 insight——同一模型的多个算子/子图存在结构相似性，因此可以复用搜索经验——是深刻且通用的。这一思路可以直接迁移到以下场景：

- **LLM 推理的 kernel 编译**：LLM 推理图（如 Transformer decoder）高度重复，每层的 attention、FFN 结构几乎一致，Bayesian code diffusion 的 prior 传播可大幅减少逐层 kernel 调优时间。
- **MoE 模型编译**：MoE 模型中大量同构的 expert 子图是理想的应用场景，prior 传播的收益更为显著。

**与现代编译栈的结合**：MetaSchedule（TVM v2 的调度框架）和 OpenAI Triton 的调优机制均面临类似问题。值得探索将 code diffusion 的思路集成进这些框架，特别是 Triton 的 autotuner 目前完全随机搜索，prior 传播的引入有明显提升空间。

**Future work 方向**：
1. **跨模型 prior 传播**：当前 prior 限于同一模型内，如果能跨模型复用（类似 TransferTuning 但不需要预编译），对 serving 系统中多模型部署场景价值巨大。
2. **更好的 prior 选择**：用 GNN 对 subgraph 建模，学习 subgraph 间的迁移潜力，替代 tensor shape 距离这一简单启发式。
3. **与神经网络代价模型结合**：TLP（neural cost model）+ pre-fine tuning 策略的组合是否能进一步提升代价模型精度，值得探索。
4. **动态形状支持**：如何将 prior 传播扩展到 dynamic shape 场景（如变长序列的 LLM 推理）是重要的 open problem。

---

## 八、总结

Bayesian Code Diffusion 将深度学习程序优化形式化为 Bayesian 推断问题，通过对相似子图间传播优化参数（code diffusion）和对代价模型引入 pre-training/fine-tuning 训练策略，在 Ansor 基础上实现了 CPU 平均 2.52×、GPU 平均 2.00× 的编译加速，同时保持甚至略微降低了程序执行延迟。该方法实现简洁、改动量小，对结构重复度高的 Transformer 类模型（BERT、MoE 等）具有较强的适用性；主要局限在于与 Ansor 框架高度绑定、硬件覆盖单一，以及 prior 选择策略在极端情况下的次优性尚未解决。
