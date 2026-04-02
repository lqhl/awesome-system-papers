# NanoFlow: Towards Optimal Large Language Model Serving Throughput

**作者**：Kan Zhu, Yufei Gao, Yilong Zhao, Liangyu Zhao, Gefei Zuo, Yile Gu, Dedong Xie, Tian Tang, Qinyu Xu, Zihao Ye, Keisuke Kamahori, Chien-Yu Lin, Ziren Wang, Stephanie Wang, Arvind Krishnamurthy, Baris Kasikci（University of Washington, Tsinghua University, UC Berkeley, University of Michigan）
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/zhu-kan
**源文件**：[[osdi25-zhu-kan.pdf]]

---

## 一、背景

LLM 推理服务面临巨大的规模需求——ChatGPT 周活跃用户超 2 亿，API 调用量在 GPT-4o Mini 发布后翻倍。在 GPU 资源紧张的背景下，最大化硬件利用率、提升吞吐量（tokens/device/s）是降低服务成本的关键。

LLM 推理相比传统 DNN 有独特挑战：模型参数量极大（GPT-3 175B 需要 5 张 A100 80GB 才能存放 FP16 权重）；Self-Attention 的 KV-cache 随上下文长度增长，内存需求巨大；每次迭代需加载全部模型权重和 KV-cache，但每个 decode 序列仅产出一个 token。因此，LLM 推理长期被认为是 memory-bound 的。

---

## 二、要解决的问题

1. **LLM 推理的瓶颈被误判**：传统观点认为 LLM 推理整体是 memory-bound 的，但作者通过详细分析发现，在 GQA、大 batch、连续 batching 等现代优化下，端到端推理实际是 **compute-bound** 的。然而现有系统未按此特征优化。

2. **GPU 资源利用率低下**：现有推理引擎（vLLM、DeepSpeed-FastGen、TensorRT-LLM）在单个 GPU 内顺序执行 compute-bound、memory-bound 和 network-bound 操作。虽然各操作对其瓶颈资源利用率约 80%，但由于顺序执行，整体 compute 利用率仅约 40%，产生大量 pipeline bubble。

3. **与理论最优吞吐量差距巨大**：以 LLaMA-2-70B 在 8×A100 上为例，理论最优吞吐量为 1857 tokens/s/GPU，而 vLLM 仅达 22.0%，TensorRT-LLM 仅达 37.8%。

---

## 三、洞察与设计

**关键洞察**：现代 LLM 推理在端到端层面是 compute-bound 的（compute 耗时是 memory 耗时的 2 倍以上），因此将大 batch 拆分为多个 nano-batch 虽然会增加权重加载次数，但额外的 memory I/O 可以被 compute 操作完全隐藏——只要通过 intra-device parallelism 让异构操作（compute-bound、memory-bound、network-bound）在同一 GPU 上并行执行。

基于此洞察，NanoFlow 的核心设计包括：

- **Nano-batching**：将输入 batch 拆分为多个 nano-batch，每个操作复制为多个 nano-operation，各自独立处理不同的 nano-batch。由于 nano-operation 之间无数据依赖，异构操作可以并行执行。

- **Auto-search 两阶段搜索引擎**：
  - **Stage I（Pipeline Structure Search）**：使用 MILP 确定 nano-operation 的数量、batch size、执行顺序，先忽略 kernel 干扰以降低搜索空间复杂度。
  - **Stage II（Pipeline Refinement）**：引入实际 kernel 干扰 profiling 结果，优化 GPU 资源分配（R 值），通过 R-to-P 映射表量化 compute-memory 和 compute-network 的性能权衡。

- **GPU 资源分配模型**：以 GEMM 性能为代理（R），profiling 成对 kernel 干扰模式（GEMM-GEMV、GEMM-Network），建立资源利用率 R 到实际性能 P 的映射表（Table 3），指导并行调度。

- **Runtime 系统**：异步 batch 调度（提前一个迭代形成下一个 batch，隐藏 CPU 调度开销）；KV-cache 分层管理（GPU→CPU→SSD），支持多轮对话场景下的 offload/reload。

---

## 四、实现细节

- 约 10K 行 CUDA + 6K 行 Python 实现。
- 使用多个 CUDA stream 执行 nano-operation，通过 CUDA events 强制依赖顺序。
- Kernel profiling：遍历所有 GEMM/GEMV/Network kernel 实现变体（thread block 数、warp 数、tile size），GEMV 和 Network kernel 限制 thread block 数在 8-128 之间以缩减搜索空间。
- 对于 70B 级别模型（LLaMA-2-70B、LLaMA-3-70B、Qwen2.5-72B、Deepseek-67B），在 KQV 生成阶段（三种资源同时重叠）使用 4 个 nano-operation，其余部分使用 2 个。Decode attention 的 R=0.4（减少 40% GEMM 性能），换取 80% decode attention 性能。
- 8B 模型不需网络操作，仅拆分为 2 个 nano-operation。
- MoE 模型使用 grouped-GEMM 实现 FFN 的 tensor parallelism。
- Batch 形成策略：优先调度未完成的 decode 请求，使用 chunked prefill（token 粒度）填充剩余容量，保持 dense batch size 恒定。
- KV-cache offload：在 KQV 生成后立即异步 offload 到 host，利用 NUMA-aware thread binding 优化传输。

---

## 五、实验结果

**实验平台**：8×A100 80GB SXM（NVLink 互连），FP16 推理。

**模型**：LLaMA-2-70B（主要评估）+ LLaMA-3-70B/8B、Qwen2-72B、Deepseek-67B、Mixtral 8×7B。

**基线**：vLLM v0.5.3、DeepSpeed-FastGen v0.2.3、TensorRT-LLM v0.8.0。

### 离线吞吐量（LLaMA-2-70B，8 GPU）

| 工作负载 | vLLM | DeepSpeed-FastGen | TensorRT-LLM | NanoFlow | 最优理论值 |
|---------|------|-------------------|--------------|----------|-----------|
| 固定长度（平均） | — | — | — | 2.62×/2.78×/1.73× vs 基线 | 1857 tok/s/GPU |
| 真实数据集（平均） | — | — | — | 4.18×/3.45×/1.91× vs 基线 | 1857 tok/s/GPU |

NanoFlow 最高达到理论最优吞吐量的 68.5%。

### 其他模型吞吐量（Input 1024, Output 512）

| 模型 | vLLM 占最优比 | NanoFlow 占最优比 |
|------|-------------|-----------------|
| LLaMA-3-70B | 32.0% | 70.6% |
| Qwen2-72B | 30.8% | 67.4% |
| Deepseek-67B | 27.4% | 59.1% |
| Mixtral 8×7B | 31.9% | 78.5% |
| LLaMA-3-8B | 9.7% | 50.4% |

### 延迟

- 在 200ms SLO 约束下，NanoFlow 可承受比 TensorRT-LLM 高 1.64× 的请求率（LMSYS-Chat-1M 数据集）。
- P99 延迟仅为平均延迟的 1.07×（得益于恒定 dense batch size）。

### 消融实验

- Nano-batching 本身（不重叠）降低 13.2% 性能（权重重复加载开销）。
- 重叠 network-bound kernel：1.07× 提升。
- 同时重叠 network + memory-bound kernel：1.17× 提升。
- KV-cache offload 引入 3.0% 性能损失，但在多轮对话场景减少 3.02× 计算量。

---

## 六、批判性分析

1. **评估硬件局限性**：所有实验仅在 A100 上进行，尽管论文分析了 H100/B200/MI300 等硬件的 compute/memory/network 比率，但未在这些平台上实际验证。随着 H100/B200 的 compute/memory 比率变化（Table 1 显示并非单调递增），NanoFlow 的收益可能不同。

2. **FP16 限定**：实验全部使用 FP16，但实际部署中 INT8/INT4/FP8 量化已成为主流。量化后 compute 需求大幅降低，可能使工作负载重新变为 memory-bound，此时 NanoFlow 的前提假设（compute-bound）不再成立。论文对此未做讨论。

3. **搜索空间简化的代价**：auto-search 假设成对 kernel 干扰的 R-to-P 映射在三个 kernel 同时运行时仍然成立，这是一个未经验证的简化。Figure 6 显示 KQV 阶段确实需要 3 类资源同时重叠，此时干扰模式可能与成对 profiling 结果偏差较大。

4. **与 Splitwise/DistServe 缺乏直接对比**：论文在 related work 中提到了 phase-level 分离方案（Splitwise、DistServe），但未与之进行实验对比。这两类方案解决的是类似问题（异构操作导致的资源浪费），缺少直接对比削弱了说服力。

5. **请求丰富假设**：NanoFlow 假设系统始终有足够请求维持大 batch（B_dense ~2048）。在请求率不足时，论文将责任推给外部控制平面（减少 NanoFlow 实例数），但这在实际部署中并不容易实现——缩容/扩容的延迟可能导致大量时间内 batch 不饱和。

6. **Nano-batching 的权重加载开销被乐观处理**：消融实验显示 nano-batching 本身带来 13.2% 性能损失，而重叠带来的收益（17%）与之相差不大。随着模型量化或硬件 compute/memory 比率变化，这一收支平衡可能被打破。

---

## 七、AI Infra / MLSys 视角

1. **Compute-bound 分析框架的价值**：论文提供了一套清晰的 LLM 推理工作负载分类方法（Equation 1-4），将硬件规格、模型配置、用户查询统计纳入统一分析框架，得出理论最优吞吐量（Equation 5）。这个框架本身对 AI Infra 从业者评估系统瓶颈和选型非常有用。

2. **Intra-device parallelism 的启发**：传统优化集中在 inter-device parallelism（TP/PP/DP），NanoFlow 打开了 intra-device 层面的优化空间。这一思路对未来 GPU 架构设计也有启示——如果硬件能提供更细粒度的资源分区（类似 MIG 但更灵活），intra-device parallelism 的收益可以更大。

3. **值得跟进的方向**：
   - **量化场景下的 NanoFlow**：INT8/FP8 推理下工作负载特征变化后，intra-device parallelism 策略需要如何调整？
   - **Prefill-Decode 分离 + NanoFlow 的结合**：Splitwise/DistServe 的 phase-level 分离与 NanoFlow 的 operation-level 重叠是否可以正交组合？
   - **多租户场景**：NanoFlow 的 nano-batching 能否扩展为跨请求/跨模型的 GPU 资源复用？
   - **Kernel 干扰的自动建模**：当前的成对 profiling + lookup table 方案扩展性有限，能否用轻量级模型预测任意 kernel 组合的干扰？

4. **最有价值的切入点**：将 NanoFlow 的分析框架和 auto-search 方法适配到 FP8/INT4 量化推理场景，验证在 compute-bound 程度降低后 intra-device parallelism 是否仍有收益，这是最直接且实用的延伸方向。

---

## 八、总结

NanoFlow 通过 intra-device parallelism（nano-batching + 异构操作重叠）解决了 LLM 推理中 GPU 资源顺序使用导致的 compute 利用率低下问题。其 auto-search 引擎可自动为不同模型生成优化的 pipeline 调度方案。在 LLaMA-2-70B 上实现了比 TensorRT-LLM 1.91× 的吞吐量提升，达到理论最优的 68.5%。核心假设是现代 LLM 推理整体为 compute-bound，因此权重重复加载的代价可被计算重叠隐藏。主要局限在于仅在 A100+FP16 上验证，在量化推理和新硬件上的适用性需进一步评估。
