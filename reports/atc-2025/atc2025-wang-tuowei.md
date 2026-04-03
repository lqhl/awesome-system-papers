# JENGA: Enhancing LLM Long-Context Fine-tuning with Contextual Token Sparsity

**作者**：Tuowei Wang, Xingyu Chen (Tsinghua University); Kun Li, Ting Cao (Microsoft Research); Ju Ren, Yaoxue Zhang (Tsinghua University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wang-tuowei
**源文件**：[[atc2025-wang-tuowei.pdf]]

---

## 一、背景

大语言模型（LLM）在文档分析、多轮对话、代码处理等场景中对长上下文窗口的需求日益增长。然而 LLM 预训练时通常使用固定的上下文窗口（如 Llama2 的 4K），当输入超过该限制时性能显著下降。通过在更长序列上 fine-tuning 可以扩展上下文窗口，但这一过程面临巨大的内存压力——特别是 activation memory 随序列长度线性增长，成为主要瓶颈。例如 GPT-3 175B 在 64K 序列长度下，activation 内存达到模型状态的 71.6 倍。

现有的高效 fine-tuning 方法主要沿两条路径发展：参数高效微调（PEFT，如 LoRA）减少可训练参数和优化器状态的内存，但无法减少 activation memory；稀疏注意力方法（如 LongLoRA）通过近似 dense attention 减少计算量，但由于其稀疏性作用在 hidden dimension 层面而非 token 层面，无法减少 activation memory。

---

## 二、要解决的问题

1. **Shadowy Activation 问题**：现有稀疏注意力方法（如 LongLoRA 的 S2-Attn）虽然减少了每个 token 参与的计算量，但只要一个 token 参与了计算，其 activation 就必须保留在内存中（被其他 token 引用），导致内存无法节省。这个现象被称为 Shadowy Activation。

2. **PEFT 方法对 activation memory 无能为力**：LoRA 冻结了预训练权重，只更新低秩矩阵，但由于梯度计算仍需遍历完整的 chain rule，activation memory 不降反升（低秩矩阵嵌入在模型结构中，需要额外存储 activation）。

3. **长上下文 fine-tuning 的内存瓶颈**：在长序列场景下，activation memory 远超模型状态内存，严重限制了可训练的序列长度和单 GPU 的承载能力。

---

## 三、洞察与设计

**关键洞察**：自然语言在长上下文场景中存在显著的冗余性，标准 full attention 可以通过只关注少量最具信息量的 token 之间的交互来有效近似。更重要的是，这种 token 级别的稀疏性具有**上下文依赖性**（Contextual Token Sparsity）——哪些 token 重要取决于具体输入和具体层，且随着序列长度增加，稀疏比例更高（4K 时约 38%，16K 时约 70%）。

基于此洞察，JENGA 提出从 token 级别（而非 hidden dimension 级别）进行稀疏化，直接减少参与计算的 token 数量，从根本上同时减少 activation memory 和计算量。系统设计围绕三个核心技术：

1. **Information-driven Token Elimination**：基于 token 间交互（attention score 聚合）定义 token informativeness，以 block-wise 方式进行消除，并采用 layer-specific threshold 适配不同层的稀疏特性。
   - Token informativeness 定义为该 token 与所有其他 token 的 attention score 之和
   - 将 attention score 分块，取每块最大值作为块的 informativeness score
   - 聚合时只保留正 attention score（负值经 softmax 后影响可忽略但会偏移正值的贡献）
   - 阈值通过两步优化：先用平均 score 初始化，再用有限差分梯度微调

2. **Context-aware Pattern Prediction**：部署轻量神经网络 predictor 预测稀疏 pattern，避免计算完整 attention score 的 O(s²) 开销。
   - 每层两个 predictor 分别近似 Q 和 K 的 informativeness，通过矩阵乘法得到 attention score 的 informativeness
   - Elastic Size Transformation：跟踪 predictor 中间层的零激活频率，动态裁剪不活跃神经元，平均减少 64.6% 参数量

3. **High-performance Kernel Optimization**：
   - Permutation-free Token Movement：将 token selection、padding、residual addition 融合进 attention 计算 kernel，避免昂贵的全局内存搬运
   - Segment-based Peak Cutting：将 loss 梯度计算分段处理，降低大词汇表 + 长序列带来的 activation 内存峰值

---

## 四、实现细节

- **代码规模**：超过 3000 行 Python 和 C++ 代码
- **Predictor 架构**：每个 predictor 由 3 个可训练低秩矩阵组成，中间用 ReLU 激活。输入为 token embedding，以 block 为单位处理
- **Predictor 训练**：离线训练，收敛速度快（<400 epochs），通过自定义 FlashAttention kernel 在线获取 ground truth informativeness score，内存复杂度为 O(s) 而非 O(s²)
- **Predictor 推理开销**：计算 O(sh²) + O(s²/b²)，b 为 block size（默认 64），可通过增大 b 控制
- **兼容性**：支持不同 MLP 结构（ReLU-based 使用 ReLU 后输出，SiLU-based 使用 gate projection × up projection），无需修改模型代码即可适配多种 LLM 架构
- **扩展**：支持与 hidden-dimension-level sparsity 组合（2D-Sparsity），以及与 activation offloading 技术结合（Sparsity-sensitive Offload）
- **开源**：https://github.com/Pairshoe/Jenga-AE

---

## 五、实验结果

**硬件平台**：

| 平台 | GPU | 显存 | FP32 TFLOPS | BF16 TFLOPS |
|------|-----|------|-------------|-------------|
| A | 1×A800 | 80GB | 19.5 | 312 |
| B | 1×A40 | 48GB | 37.4 | 150 |
| C | 4×4090 | 24GB | 82.6 | 82.6 |

**模型**：OPT (350M/1.3B/2.7B/6.7B)、Llama2-7B、Llama3-8B

**内存节省**：

| 对比基线 | 4K 序列 | 8K 序列 |
|----------|---------|---------|
| vs LoRA | 平均 38.2% | 平均 50.5% |
| vs LongLoRA | 类似 | 类似（LongLoRA 因 Shadowy Activation 内存甚至略增） |

- End-to-end 内存减少最高 1.93×
- 可训练序列长度翻倍：OPT-1.3B 从 16K→32K，OPT-350M 从 32K→64K（单 A800 GPU）

**速度提升**：
- 相比 LoRA 平均加速 10.8%（A800）和 8.6%（A40）
- 更长序列（配合 recomputation）最高 1.36× 加速
- 2D-Sparsity 扩展最高 2.04× 加速

**精度影响**：

| 指标 | 原始 LoRA | JENGA |
|------|-----------|-------|
| PG19 Perplexity (16K) | 6.87 | 7.08 |
| Proof-Pile Perplexity (16K) | 2.57 | 2.70 |
| LongBench 平均 | 基本持平 | 部分任务略有波动但整体可比 |

**组件分析**：
- Token Elimination：Attention block 平均节省 38.3% 内存，MLP block 平均节省 51.1%
- Pattern Predictor：平均 recall 95.13%，收敛仅需 <400 epochs
- Kernel Optimization：permutation-free 策略带来 10×~50× kernel 级加速；segment-based peak cutting 额外节省约 15% 内存
- 多 GPU 扩展性良好（4×4090 线性扩展）

---

## 六、批判性分析

1. **精度评估不够充分**：Perplexity 增幅约 2-5%，在 LongBench 上部分任务表现下降明显（如 qmsum 从 22.64→20.33，repobench 从 52.00→48.32），但论文将此轻描淡写为"comparable"。对于下游任务敏感的应用场景，这种精度损失可能不可接受。

2. **Block-wise 消除的粒度问题**：论文声称 block size 相对序列长度足够小（如 64 vs 16K），所以包含重要 token 的 block 能被保留。但这一论证是定性的——没有给出不同 block size 下精度和内存的 trade-off 曲线，也没有分析 block size 对不同类型任务的影响。

3. **Predictor 的训练开销被低估**：虽然单个 predictor 训练快（<400 epochs），但每层需要两个 predictor，且 elastic size transformation 需要跟踪训练过程中的零激活频率。论文没有量化这个离线训练的总成本，也没有讨论当模型或数据分布变化时 predictor 的泛化能力。

4. **基线选择有局限**：仅与 LoRA 和 LongLoRA 比较，缺少与 activation recomputation（gradient checkpointing）和 activation compression 等更常用的 activation memory 优化方法的直接对比。虽然论文声称 JENGA 可与这些技术组合，但没有给出组合后的 end-to-end 收益数据（仅有 offloading 扩展的部分结果）。

5. **实验模型规模偏小**：最大模型仅为 Llama3-8B，而当前主流 LLM 已达 70B+。在更大模型上，attention 在总计算中的占比、稀疏性特征、predictor 的有效性可能发生变化，论文缺少相应讨论。

6. **Layer-specific threshold 的鲁棒性**：阈值优化依赖有限差分近似梯度（Algorithm 1），但没有讨论这个优化的收敛保证、对学习率 η 的敏感性，以及在不同数据分布下阈值是否需要重新调整。

---

## 七、AI Infra / MLSys 视角

1. **Token-level sparsity 是 activation memory 优化的新维度**：不同于现有的 recomputation/offloading/compression 等"以计算/通信换内存"的策略，JENGA 从"减少需要处理的 token 数量"这个角度切入，直接减少 activation 的产生。这一思路可以推广到其他需要处理长序列的 AI 系统场景（如长序列推理、视频理解、多模态模型）。

2. **Permutation-free kernel design 的参考价值**：JENGA 将 token selection/padding/residual addition 融合进 attention kernel 的设计模式，对于任何涉及动态稀疏计算的系统都有参考意义。特别是避免全局内存搬运带来的 10×~50× kernel 加速，展示了 kernel fusion 在稀疏计算中的重要性。

3. **与推理侧 token pruning 的结合**：JENGA 的 contextual token sparsity 机制目前仅用于 fine-tuning，但类似思路可以迁移到 prefill 阶段的 KV cache 压缩——在 prefill 时识别不重要的 token，减少存入 KV cache 的 token 数量，从而降低推理阶段的内存和计算开销。

4. **值得跟进的研究方向**：
   - 将 token-level sparsity 应用于大规模分布式训练（70B+ 模型），研究跨节点 activation memory 优化
   - 探索 training-free 的 token importance 估计方法，避免 predictor 的离线训练开销
   - 结合 MoE 架构研究 token sparsity 与 expert sparsity 的交互效应
   - Segment-based peak cutting 的思路可以推广到其他存在内存峰值的训练阶段

---

## 八、总结

JENGA 首次将 token-level sparsity 引入 LLM 长上下文 fine-tuning，通过识别和消除冗余 token 从根本上减少 activation memory，克服了现有 PEFT 和稀疏注意力方法面临的 Shadowy Activation 问题。系统通过 information-driven token elimination、context-aware pattern prediction 和 kernel optimization 三项技术实现了最高 1.93× 内存节省和 1.36× 加速，同时保持与 LoRA 相当的模型精度。不过，其评估集中在 8B 以下模型，precision loss 在部分任务上非平凡，predictor 的离线训练成本和泛化能力也值得进一步验证。
