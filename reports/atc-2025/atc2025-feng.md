# Optimus: Accelerating Large-Scale Multi-Modal LLM Training by Bubble Exploitation

**作者**：Weiqi Feng (Harvard University), Yangrui Chen (ByteDance), Shaoyu Wang (University of Southern California), Yanghua Peng (ByteDance), Haibin Lin (ByteDance), Minlan Yu (Harvard University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/feng
**源文件**：[[atc2025-feng.pdf]]

---

## 一、背景

多模态大语言模型（MLLM）将 LLM 的能力扩展到文本、图像、音频等多种模态，在视觉问答、多模态翻译、内容生成等领域取得了显著进展。典型 MLLM 由多个模态 encoder（如 ViT）、input projector 和 LLM backbone 组成。encoder 处理非文本模态输入，projector 将特征对齐到文本特征空间，最终由 LLM backbone 统一处理。

随着模型规模增长至数千亿参数，MLLM 训练需使用数千 GPU 进行 3D 并行（DP + PP + TP）。然而，现有分布式训练系统（如 Megatron-LM、MegaScale）主要为同构 LLM 设计，在训练异构的 MLLM 时效率低下——在 ByteDance 内部使用 3000+ NVIDIA GPU 训练 ViT + GPT（>100B 参数）的任务中，超过 48% 的 GPU 周期处于空闲状态。

---

## 二、要解决的问题

现有 MLLM 训练系统面临严重的 GPU bubble 问题，主要来源于三类：

1. **DP 通信 bubble**：分布式优化器的 all-gather（3.3%）和 reduce-scatter（8.9%）操作导致 GPU 空闲。
2. **PP pipeline bubble**：warm-up（5.0%）、cool-down（9.2%）和其他 PP bubble（8.7%）源于 pipeline 阶段间的数据依赖。MLLM 的 encoder 和 LLM 异构性导致 pipeline stage 不平衡，进一步加剧 bubble。
3. **TP 通信 bubble**：每个 transformer layer 的前向/反向需多次 all-gather 和 reduce-scatter，产生大量亚毫秒级 bubble（平均约 300µs），累计占训练时间 11.2%。

现有优化方案（Zero Bubble Pipeline、MegaScale 的通信-计算重叠等）无法同时优化 encoder 和 LLM，因为它们将 MLLM 视为统一 pipeline，导致大部分 GPU 无法在 bubble 期间执行 encoder 计算。

---

## 三、洞察与设计

**关键洞察**：MLLM 训练中约 90% 的 bubble 发生在 LLM backbone 的前向/反向阶段，而 encoder 的计算量（FLOPs）远小于 LLM backbone（因参数量小得多，如 Flamingo 80B 中 LLM 占 70B）。因此，可以将 encoder 的计算调度到 LLM 的 bubble 中执行，从而"消化"这些空闲时间。

基于这一洞察，Optimus 的核心设计包含三个关键决策：

**设计决策 1：分离并行计划，共置 encoder 与 LLM**。现有框架将 MLLM 作为单一 pipeline 分布，encoder 层只在前几个 pipeline stage，导致大部分 GPU 没有 encoder 模型状态。Optimus 为 encoder 和 LLM 分别制定 3D 并行计划（如 encoder 用 DP=2, PP=2, TP=2，LLM 用 DP=1, PP=4, TP=2），使每个 GPU 都持有 encoder 和 LLM 的模型状态，从而所有 GPU 都能在 LLM bubble 期间执行 encoder 计算。

**设计决策 2：双阶段依赖管理**。MLLM 训练中存在三层依赖——迭代依赖、encoder 内部 pipeline 依赖、encoder-LLM microbatch 级依赖。Optimus 采用 local scheduling 处理前两者，global ordering 处理 encoder-LLM 依赖（通过比较时间戳验证依赖满足）。

**设计决策 3：kernel 级调度**。将 encoder layer 分解为一系列 CUDA kernel，以利用亚毫秒级 TP bubble。同时将 encoder 的通信 kernel 调度到 LLM 的计算期间执行（而非 TP bubble），避免带宽竞争。

---

## 四、实现细节

Optimus 基于 Megatron-LM 实现，核心包含两个组件：

**Model Planner**：
- 先确定 LLM 的 3D 并行计划 (DP_llm, PP_llm, TP_llm)
- 枚举 encoder 的 3D 并行计划 (DP_enc, PP_enc, TP_enc)，约束 PP_enc 是 PP_llm 的因子，TP_enc 是 TP_llm 的因子
- 在所有 GPU 上共置 encoder 和 LLM 模型状态
- 根据 GPU 内存约束裁剪不可行的计划
- 构建独立的 microbatch 分配方案：m = DP_enc / DP_llm 个 encoder pipeline 分担 N_mb 个 microbatch

**Bubble Scheduler**（Algorithm 2）：
- **粗粒度 bubble 利用**：将 encoder forward 调度到 LLM 计算开始前的大 bubble（DP all-gather + PP warm-up），encoder backward 调度到 LLM 计算结束后的大 bubble（PP cool-down + reduce-scatter）
- **细粒度 bubble 利用**：迭代式优化——找到关键路径上的 encoder pipeline，将其 microbatch 计算调度到 LLM 计算间隙的小 bubble 中，分解到 kernel 粒度
- **Encoder-LLM 依赖管理**：通过 GetEncLLMDep 获取依赖点（调整 1F1B interleaved schedule 的 warm-up microbatch 数），通过 CheckEncLLMDep 验证所有 microbatch 的前向/反向依赖是否满足
- 插入 P2P send/receive 通信来传递 encoder 输出 activation 和 LLM 反向梯度

**多 encoder 支持**：每个 encoder 独立应用并行计划，不同 encoder 间无数据依赖，kernel 统一调度。

**算法复杂度**：O(C²_{n_p+1} × N_mb^m × (F+B))，实际运行数分钟即可完成（一次性开销）。

**内存开销**：额外内存为 k(DP_enc - DP_llm)φ_enc / n_gpu，实验中最大 12%。

---

## 五、实验结果

**实验平台**：ByteDance 生产集群，数千 NVIDIA Hopper GPU（80GB 显存，989 TFLOPS），NVLink + RDMA。

**模型**：ViT-5B/11B/22B encoder + LLAMA-70B/GPT-175B backbone。

### Weak-Scaling 实验

| 配置 | Encoder | LLM | GPU 数 | Batch Size |
|------|---------|-----|--------|------------|
| Model A | ViT-11B | LLAMA-70B | 64 | 32 |
| Model B | ViT-22B | LLAMA-70B | 128 | 64 |
| Model C | ViT-11B | GPT-175B | 256 | 128 |
| Model D | ViT-22B | GPT-175B | 512 | 256 |

Optimus 相比 Megatron-LM 加速最高 1.22×，相比 Megatron-LM balanced 加速最高 1.18×。Alpa 和 FSDP 在这些规模下 OOM。

### Strong-Scaling 实验（ViT-22B + GPT-175B，batch size 1536）

| GPU 数 | Megatron-LM 迭代时间 | Optimus 迭代时间 | MFU 提升 |
|--------|---------------------|-----------------|---------|
| 1536 | 10.65s | 9.80s | 31.6% → 34.4% (1.06×) |
| 2048 | 8.26s | 7.29s | 30.6% → 34.6% (1.11×) |
| 3072 | 5.91s | 4.87s | 28.5% → 34.6% (1.21×) |

GPU 数增加时 Optimus 优势更大：baseline MFU 下降而 Optimus 保持稳定。

### 多 Encoder 实验（512 GPU）

双 encoder 配置下，Optimus 相比 Megatron-LM 加速 1.25×–1.27×。

### Bubble Scheduler 效率

| 设置 | Microbatch 数 | Eff_coarse | Eff_fine | 运行时间 |
|------|--------------|-----------|---------|---------|
| 1536 GPU | 32 | 34.3% | 57.5% | 322.2s |
| 2048 GPU | 24 | 45.8% | 69.3% | 89.6s |
| 3072 GPU | 16 | 68.7% | 85.0% | 15.1s |

细粒度 bubble 利用相比粗粒度最高提升 1.67×。

### 内存开销

最大 12% 额外 GPU 内存（某些配置下 Optimus 反而更省内存，因 baseline 的 pipeline 分层导致内存不均衡）。

---

## 六、批判性分析

1. **实验模型覆盖有限**：仅评估 ViT + GPT/LLAMA 这一类架构，未涉及音频 encoder、视频 encoder 等其他模态。论文 Introduction 提到 MLLM 处理"text, images, and audio"，但实验仅限图像模态，泛化性存疑。

2. **Zero Bubble Pipeline 的排除理由不够充分**：论文称 Zero Bubble Pipeline "requires changes to the optimizer, which raises concerns about end-to-end model convergence"——但 Zero Bubble 的原论文已验证其收敛性。Optimus 没有与之正面对比，而是绕开了这个最强 baseline。

3. **静态离线调度的局限性被轻描淡写**：论文承认 kernel 运行时间波动可能导致调度次优，但仅在 Discussion 中一笔带过，没有量化实际偏差有多大。在大规模集群中，straggler、网络抖动等问题频繁，静态调度的鲁棒性是核心问题。

4. **Strong-scaling 中 Optimus MFU 提升的归因**：随 GPU 数增加，baseline MFU 下降是因 bubble ratio 增大。Optimus "保持稳定 MFU" 的说法暗示其完全消除了 bubble 增长的影响——但从 scheduling efficiency 数据看（57.5%–85.0%），仍有大量 bubble 未被利用。实际是 baseline 变差让 Optimus 的相对优势放大了。

5. **端到端收敛性验证缺失**：论文未报告任何训练 loss 曲线或下游任务精度。虽然 Optimus 不修改优化器或梯度计算，但独立的 encoder 并行计划改变了 microbatch 分配和 gradient aggregation 顺序，可能影响数值行为。

6. **排除 DistTrain 和 DiffusionPipe 的理由值得商榷**：DistTrain 采用的 disaggregated training 思路（encoder 和 LLM 使用不同 GPU 集群）是一种不同但合理的设计，不能仅因"not open source"就排除概念层面的对比分析。

---

## 七、AI Infra / MLSys 视角

**启发与借鉴价值**：
- **异构模型的分离并行化**思路具有普适性。当前 MoE 模型中 expert 和 shared layer 的异构性、Mixture-of-Depth 中的条件计算，都可以借鉴 Optimus "为不同组件制定独立并行计划"的方法。
- **Kernel 级 bubble 填充**技术可迁移到其他场景：例如在 pipeline parallelism 中利用 bubble 执行 prefill/decode disaggregation 中的辅助计算，或在训练中插入 checkpoint validation。

**可跟进的研究方向**：
1. **动态 bubble 调度**：Optimus 的离线调度假设 kernel 运行时间稳定，但实际存在波动。结合 runtime profiling 的在线调度器（如基于 RL 或 bandit 的方法）是一个明确的改进方向。
2. **推广到更复杂计算图**：论文 Discussion 提到支持更复杂的 MLLM 计算图（如 encoder 输出在 LLM 不同层注入的交叉注意力架构），需要新的图分区算法，是一个有价值的系统问题。
3. **与 disaggregated training 的融合**：Optimus 的共置策略与 DistTrain 的分离策略形成对偶——在不同网络拓扑和模型配置下，哪种更优？是否可以混合使用？
4. **推理场景的迁移**：多模态推理中 prefill 阶段同样存在 encoder-decoder 异构性和 pipeline bubble，Optimus 的 bubble 填充思路可能适用于推理系统的吞吐优化。

**最有价值的切入点**：将 bubble exploitation 思路推广到 MoE 训练——expert 计算的不均匀性产生的 bubble 与 encoder/LLM 异构性产生的 bubble 具有结构相似性，但 MoE 的动态路由使问题更具挑战性。

---

## 八、总结

Optimus 针对 MLLM 训练中 encoder 与 LLM backbone 异构性导致的大量 GPU bubble 问题，提出将 encoder 计算调度到 LLM bubble 中执行的方案。其核心技术包括：为 encoder 和 LLM 制定独立的 3D 并行计划以实现模型共置、双阶段依赖管理处理复杂数据依赖、kernel 级分解利用亚毫秒级 bubble。在 ByteDance 生产集群上，Optimus 在 3072 GPU 训练 ViT-22B + GPT-175B 时实现了 20.5%–21.3% 的加速。主要局限在于依赖静态离线调度、实验仅覆盖 ViT+LLM 架构、缺少收敛性验证，以及未与 Zero Bubble Pipeline 等强 baseline 直接对比。
