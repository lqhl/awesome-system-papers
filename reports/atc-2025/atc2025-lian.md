# Universal Checkpointing: A Flexible and Efficient Distributed Checkpointing System for Large-Scale DNN Training with Reconfigurable Parallelism

**作者**：Xinyu Lian (UIUC), Sam Ade Jacobs (Microsoft), Lev Kurilenko (Microsoft), Masahiro Tanaka (Microsoft), Stas Bekman (Snowflake), Olatunji Ruwase (Microsoft), Minjia Zhang (UIUC)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/lian
**源文件**：[[atc2025-lian.pdf]]

---

## 一、背景

大规模 DNN/LLM 训练需要在数百甚至数千 GPU 上运行数周乃至数月。训练过程中硬件故障、资源弹性调整（如 spot instance 回收、集群节点到期）频繁发生——LLaMA 3.1 在 16,000 GPU 上训练 54 天遭遇了 419 次故障，平均每 3 小时发生一次。当故障发生或硬件环境变化时，训练作业需要在不同数量的 GPU 或不同并行策略下恢复（reconfigurable parallelism），以避免从头重训。

现有分布式训练系统（PyTorch、Megatron-LM、DeepSpeed）的 checkpoint 机制与特定并行策略高度耦合：DP、TP、PP、SP、ZeRO 等不同策略生成结构完全不同的 checkpoint 文件。当需要从一种并行策略切换到另一种时，开发者必须手写转换脚本，工程量大且容易出错。

---

## 二、要解决的问题

1. **Checkpoint 与并行策略强耦合**：不同并行策略（DP、TP、PP、ZeRO）产生的 checkpoint 文件结构完全不同，无法跨策略加载。PyTorch Distributed Elastic 仅支持调整 DP 度数，不支持从 ZeRO 切换到 3D parallelism 等复杂场景。

2. **缺乏自动化重配置流水线**：现有系统要么只支持有限的并行策略子集，要么依赖手写转换脚本（ad-hoc conversion scripts）。DCP 仅支持 DP 和 ZeRO，MCP 不支持 ZeRO-DP 和 MoE 模型。覆盖面窄且难以维护。

3. **重配置开销大**：模型规模持续增长（参数量从 7B 到 1T+），checkpoint 大小可达数十 TB。顺序执行重配置耗时过长（数小时级别），成为训练恢复的性能瓶颈。

---

## 三、洞察与设计

**关键洞察**：所有主流并行策略对模型参数的处理方式，本质上可以归纳为少数几种 tensor 分片模式（pattern）——Unique、Replicate、Partial、Shard-V/H/Hy/NC。如果将 checkpoint 从特定并行策略中解耦，统一到一个"原子"表示（每个参数对应一个完整的、不包含分片信息的 tensor），就可以通过 pattern 匹配和 pattern-aware 操作自动完成任意并行策略之间的转换。

基于这一洞察，UCP 设计了三个核心组件：

### 1. Atomic Checkpoint
- 将每个模型参数的权重和优化器状态（Adam 的 m 和 v）分别存储为独立的 FP32 tensor 文件
- 不包含任何 rank ID、分片信息或 padding，与并行策略和硬件配置完全解耦
- 作为所有并行策略之间转换的"公共中间表示"

### 2. Pattern-Based Reconfiguration Pipeline
- 定义了 7 种 tensor 分片 pattern：Unique（PP 中的独有层）、Replicate（DP 复制或 TP 中的 LayerNorm）、Partial（异步训练）、Shard-V（列分片）、Shard-H（行分片）、Shard-Hy（多维分片）、Shard-NC（非连续分片，用于 MoE 和 GQA）
- 5 种 pattern-aware 操作：Extract（从分布式 checkpoint 提取片段）、Union（按 pattern 合并片段）、StripPad（去除对齐 padding）、UcpInfo（生成目标并行策略的元数据）、Load（按目标策略加载 atomic checkpoint）
- Source → Atomic → Target 的两阶段流水线，避免了 O(n²) 的两两转换

### 3. 高效重配置优化
- **Nested Parallel Reconfiguration**：将重配置建模为 MapReduce 问题，利用多节点多核并行处理，并通过基于参数大小的负载均衡避免 straggler
- **Redundancy-bypassing Loading**：同一 DP group 内的 worker 共享加载任务，通过 all-gather 分发，利用 GPU 互联（NVLink 900 GB/s）替代存储 I/O
- **Lazy Reconfiguration Invocation**：仅在 P_src ≠ P_tgt 时触发重配置，不改变正常 checkpoint 保存逻辑

---

## 四、实现细节

- 基于 DeepSpeed 实现并开源，通过 HuggingFace 和 PyTorch Lightning 等框架可直接使用
- Atomic checkpoint 按 layer-by-layer 方式加载到 GPU，加载完一层后释放 CPU 内存，峰值 CPU 内存从全模型降低到单层
- ZeRO-3 场景：识别 flatten 后的 1D tensor 为 Shard-V pattern，合并后去除 padding；加载时重新计算分片元数据并添加对齐 padding
- 3D Parallelism 场景：同一模型的不同参数可能同时具有 Replicate（LayerNorm）、Shard-V/H（matmul）、Partial（AlibiEmbedding）、Unique（PP 层）等多种 pattern
- MoE 场景：Fused expert weight matrix 形状为 [n_experts × hidden_out, hidden_in]，使用 Shard-NC pattern 处理非标准维度分片
- GQA 场景：QKV fused matrix 中 Q/K/V 大小不等，Shard-NC 配合 shape info 识别变长片段
- 支持 mixed-precision training（FP16/BF16/FP32），atomic checkpoint 统一存 FP32，加载时转换

---

## 五、实验结果

**实验平台**：64× A100 40GB（主要实验）、384× A100 80GB（176B 模型）、1024× MI250X 64GB（1T 模型）

### 准确性验证

| 实验类型 | 结果 |
|---------|------|
| Single Source → Multiple Targets | 从 TP=2,PP=2,DP=2 重配置到多种目标策略，训练曲线与原策略完全一致 |
| Multiple Sources → Single Target | 从多种 Source 配置重配置到同一 Target，训练曲线匹配 |

### 与现有系统对比

| 系统 | Change DP | Switch ZeRO-DP | Change MP | MoE |
|------|-----------|----------------|-----------|-----|
| DCP (PyTorch) | 支持 | 支持 | 失败 | 失败 |
| MCP (Megatron) | 支持 | 失败 | 支持 | 失败 |
| UCP | 支持 | 支持 | 支持 | 支持 |

### 重配置效率

| 模型 | 硬件 | Save | Transform | Load | 端到端 |
|------|------|------|-----------|------|--------|
| GPT-3 7B | 4 nodes A100 | 0.29 min | 0.73 min | 0.36 min | 1.38 min |
| GPT-3 13B | 8 nodes A100 | 0.38 min | 1.17 min | 0.47 min | 2.02 min |
| MoE 42B | 8 nodes A100 | 0.42 min | 2.64 min | 0.58 min | 3.64 min |
| GPT-3 176B | 48 nodes A100 | 0.48 min | 1.67 min | 0.68 min | 2.83 min |
| GPT-3 1TB | 128 nodes MI250X | 0.50 min | 2.93 min | 0.69 min | 4.12 min |

- Nested Parallel vs Sequential：14-257× 加速
- Loading overhead：相比标准 checkpoint 加载仅增加约 10s
- 端到端重配置开销：< 0.001% 总训练时间

### 真实部署验证

成功用于 BLOOM 176B、Microsoft Phi-3.5-MoE 42B、SmileyLlama 8B、YuLan-Mini 4.2B 的实际训练。BLOOM 176B 训练中集群从 48 节点缩减到 24 节点时，UCP 实现了无缝恢复。

---

## 六、批判性分析

1. **Pattern 集合的完备性声称过于乐观**：论文声称 7 种 pattern 覆盖了"widely used parallelism strategies"，但实际上 Expert Parallelism（EP，独立于 TP 的 expert 分片）、Context Parallelism（CP，与 SP 不同的分布式注意力策略）等新兴策略并未讨论。论文承认扩展新 pattern 需要"similar amount of implementation effort"，但这正好说明系统并非真正"universal"。

2. **准确性验证规模有限**：训练准确性实验仅跑了 200 iterations（在 100 iteration 处重配置），且用的是 GPT-3 medium (350M) 这样的小模型。虽然 176B 也做了训练曲线实验，但只展示了 loss 曲线的短期匹配，没有验证长期收敛和下游任务性能。Checkpoint 重配置的数值精度问题（如 FP16→FP32→FP16 的舍入误差累积）可能在长训练中显现。

3. **效率评估的 I/O 带宽条件宽松**：实验集群的 I/O 带宽为 3-5 GB/s，论文自己也承认"comparable to consumer-grade SSDs"。在带宽受限的云环境中（如多租户共享存储），重配置时间可能显著增加，但论文没有给出这些场景的数据。

4. **与 PyTorch DCP resharding 的对比不够公平**：论文对比的 DCP 版本可能不是最新的。PyTorch DCP 在持续演进，已逐步增加对更多并行策略的支持。论文中 Table 1 和 Fig. 8 展示的 DCP 限制可能已部分解决。

5. **Lazy invocation 的触发时机分析缺失**：论文声称 UCP 仅在需要时触发重配置，但没有讨论故障检测到重配置完成的端到端延迟。在实际训练中，故障发生后需要先将 checkpoint 从远程存储加载到新集群，然后才能执行重配置——这个完整路径的延迟分析缺失。

6. **Atomic checkpoint 的存储开销**：所有参数统一存为 FP32 atomic checkpoint，相比直接保存分布式 checkpoint（可能是 FP16/BF16），存储开销至少翻倍。对于 1T 参数的模型，这意味着额外数十 TB 的存储成本，但论文没有讨论这一 trade-off。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint 作为并行策略解耦层的设计思路具有普适性**：UCP 的 atomic checkpoint 本质上是一个"canonical form"——将所有并行策略归一化到参数级别的完整 tensor。这种中间表示的思路可以借鉴到其他需要跨并行策略迁移的场景，如模型合并（model merging）、联邦学习中的异构聚合、以及训练到推理的无缝过渡。

2. **Pattern-based abstraction 对推理引擎也有价值**：推理系统（如 vLLM、SGLang）在加载模型时也面临 checkpoint 格式适配问题（不同训练框架导出的 checkpoint 结构不同）。UCP 的 pattern 匹配机制可以扩展为通用的 checkpoint format converter，减少推理部署中的格式转换工程量。

3. **值得跟进的方向**：
   - **与异步 checkpoint 系统的深度集成**：UCP 与 Gemini、CheckFreq 等 in-memory checkpoint 系统正交，如何在异步保存的同时维护 atomic checkpoint 的一致性是一个有价值的研究问题
   - **弹性训练场景的全链路优化**：结合 Bamboo、Parcae 等 spot instance 训练系统，将 UCP 的重配置延迟从分钟级进一步压缩到秒级
   - **跨框架 checkpoint 互操作**：当前 UCP 在 DeepSpeed 内实现，但不同框架（Megatron、FSDP、Colossal-AI）的 checkpoint 格式互不兼容。基于 atomic checkpoint 的思路设计跨框架的标准 checkpoint 格式是一个有实际需求的方向

4. **最佳切入点**：将 UCP 的 pattern-based reconfiguration 扩展到支持 training-to-serving 的无缝转换，特别是在 MoE 模型中，训练时的 EP+TP 分片方式与推理时的分片方式可能完全不同，自动化这一转换有很大的实用价值。

---

## 八、总结

UCP 通过引入 atomic checkpoint（与并行策略解耦的参数级 canonical form）和 pattern-based reconfiguration pipeline（基于 7 种 tensor 分片模式的自动化转换流水线），实现了大规模分布式训练中任意并行策略之间的灵活重配置。系统在 DeepSpeed 中实现并开源，支持 DP、TP、PP、SP、ZeRO 及其组合，覆盖 dense LLM、sparse MoE 和 GQA 等架构。通过 nested parallel reconfiguration 等优化，1T 参数模型的端到端重配置仅需约 4 分钟。主要局限在于 pattern 集合的可扩展性取决于手动识别新并行策略的分片模式，以及 FP32 atomic checkpoint 带来的额外存储开销。
