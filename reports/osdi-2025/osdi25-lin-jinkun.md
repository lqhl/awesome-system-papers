# Understanding Stragglers in Large Model Training Using What-if Analysis

**作者**：Jinkun Lin (NYU), Ziheng Jiang, Zuquan Song, Sida Zhao, Menghan Yu, Chenyuan Wang (ByteDance Seed), Zhanghan Wang (NYU), Zuocheng Shi (Zhejiang University), Xiang Shi (ByteDance), Wei Jia, Zherui Liu, Shuguang Wang, Haibin Lin, Xin Liu (ByteDance Seed), Aurojit Panda, Jinyang Li (NYU)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/lin-jinkun
**源文件**：[[osdi25-lin-jinkun.pdf]]

---

## 一、背景

大语言模型（LLM）训练是当今最具挑战性的分布式计算任务之一，通常需要数千个 GPU 通过混合并行策略（DP + PP + TP + CP）协同工作。这种高度同步的工作负载模式使得训练极易受到 straggler（掉队者）的影响——少量慢速 worker 就能拖慢整个训练作业。然而，与传统 MapReduce 等大数据框架不同，LLM 训练的并行策略更加复杂，传统的 straggler 分析方法和缓解策略并不直接适用。尽管 straggler 问题被广泛认知，但此前缺乏对真实大规模 LLM 训练集群中 straggler 问题的系统性、定量化分析研究。

---

## 二、要解决的问题

1. **缺乏定量理解**：straggler 在真实 LLM 训练中究竟有多普遍？对作业性能的实际影响有多大？目前缺乏基于大规模生产集群 trace 的量化数据。
2. **根因分析困难**：straggler 的成因复杂多样（硬件故障、负载不均、数据偏斜、GC 暂停等），且在混合并行下各类 straggler 的影响会相互叠加和传播，难以归因。
3. **传统方法不适用**：传统 critical path 分析对 LLM 训练这种高度并行且同构的工作负载不适用（存在大量等价关键路径）；传统 straggler 缓解方案（backup worker、异步 SGD、丢弃更新）要么资源开销过大，要么影响模型精度。
4. **在线检测与诊断缺失**：缺乏实用的工具帮助运维团队实时发现和定位 straggler 问题。

---

## 三、洞察与设计

**关键洞察**：在无 straggler 的理想场景下，同类型操作（如各 PP stage 的 forward-compute、各 DP rank 的 grads-sync）的执行时间应该完全相同。因此，可以通过构造一个"所有同类操作执行时间一致"的理想时间线，与实际执行进行对比，从而精确量化 straggler 的影响。

基于这一洞察，作者设计了一套 **what-if analysis** 方法论：

1. **OpDuration Tensor**：将所有 traced 操作组织为四维张量（training step × microbatch × PP rank × DP rank），每种操作类型对应一个张量。
2. **理想化执行时间估计**：对于计算操作，用同组操作的均值替代（等效于重新平衡负载）；对于通信操作，分离出 transfer-duration（去掉等待时间），并用中位数替代（因为通信的 straggler 通常是极端异常值，均值会被严重偏斜）。
3. **依赖关系模型**：每个 worker 运行 6 个 stream（compute、DP-comm、4 个 PP-comm stream），模拟器根据流内顺序依赖、DP 通信-计算依赖、PP 通信-计算依赖、跨 rank 集合通信依赖来重建执行时间线。
4. **选择性修复**：可以选择性地只"修复"特定 worker、特定操作类型或特定 PP stage 的 straggler，从而将总体 slowdown 归因到具体的根因。

---

## 四、实现细节

- **Trace 收集**：基于 ByteDance 内部工具 NDTimeline，对 Megatron-LM 训练系统进行 profiling，默认采样 10% 的训练步。记录每个操作的类型、起止时间戳、step ID、microbatch ID、PP rank、DP rank 等元数据。
- **Trace 规模**：2024/01/01–2024/05/31，五个月期间收集的 ≥128 GPU 的 LLM 预训练作业，经过过滤后得到 3079 个作业（其中 562 个 ≥512 GPU，111 个 ≥5000 GPU），覆盖约 56.4% 的 GPU 小时数。
- **集群配置**：类似 NVIDIA DGX 的硬件配置（8 GPU/节点，NVLink/PCIe 互连，4-8 个高速 NIC），三层 CLOS 网络拓扑，网络带宽过量配置以避免拥塞，作业独占 GPU。
- **模拟器验证**：模拟误差中位数 1.3%，P90 为 5.5%。通过人工注入 straggler（后台运行 10K×10K MatMul）进行验证，实测 slowdown 分别为 1.16/1.40/2.03，模拟估计为 1.21/1.42/1.98，吻合度高。丢弃模拟误差 ≥5% 的 trace 以确保分析可靠性。
- **SMon 监控系统**：将分析流水线的核心功能部署为在线监控服务，每次 NDTimeline profiling 后自动运行，估算 slowdown 并通过 heatmap 展示各 worker 的 slowdown 分布。不同根因呈现不同的 heatmap 模式（worker 故障为孤立热点、PP stage 不均衡为水平条带、序列长度不均衡为随机散布）。

---

## 五、实验结果

### Straggler 的影响

| 指标 | 数值 |
|------|------|
| 受 straggler 影响的作业比例（slowdown ≥ 1.1） | 42.5% |
| 资源浪费中位数 | 7.8% |
| 资源浪费 P90 | 21.3% |
| 资源浪费 P99 | 45.0% |
| 全集群 GPU 小时浪费比例 | 10.4% |

### Straggler 的特征

- **时间维度**：straggler 导致的 slowdown 在各训练步之间高度一致（归一化后 P50=1.0, P90=1.06），说明 straggler 多由持续性问题引起，而非瞬态扰动。
- **操作类型**：计算操作（forward/backward-compute）是主要瓶颈，通信操作影响较小（得益于充足的网络带宽和专用集群）。
- **作业规模**：作业规模与 straggler 严重程度无明显正相关（大作业有专人优化）。

### 根因分析

| 根因 | 影响范围 | 备注 |
|------|---------|------|
| 个别 worker 故障 | 仅 1.7% 的 straggling 作业中占主要因素 | 发生时 slowdown 严重（平均 3.04 vs 整体平均 1.28） |
| PP stage 分区不均衡 | 39.3% 的作业中占主要因素 | 最后一个 stage 的 loss layer 计算量显著大于 transformer layer |
| 序列长度不均衡 | 21.4% 的作业受影响 | 长上下文作业影响更大，平均 slowdown 1.34 |
| Python GC | 显著影响 | 128 DP rank 下 planned GC 带来 12.6% 改善 |
| CUDA 内存碎片 | 少见 | 导致 cudaFree/cudaMalloc 调用增多 |
| 虚假 kernel 依赖 | 少见 | MoE 模型中 reduce-scatter 阻塞无关 kernel |

### 缓解措施效果

| 方案 | 效果 |
|------|------|
| 手动调整 PP stage 层数分配 | 9.9% 加速（但仍不完美，最后 stage 前向计算仍为其他 stage 的 1.55 倍） |
| 序列长度重分配（跨 DP rank 均衡 ∑s²） | 23.9% 吞吐提升 |
| Planned GC（128 DP rank，每 500 步） | 12.6% 改善 |

---

## 六、批判性分析

1. **Trace 覆盖率有限**：最终仅覆盖 38.2% 的作业和 56.4% 的 GPU 小时，大量 trace 因格式问题、作业反复失败、模拟误差过大等原因被丢弃。被丢弃的作业可能恰恰包含更严重的 straggler 问题（如频繁失败的作业），这意味着论文可能系统性地低估了 straggler 的影响。

2. **TP/CP 粒度的 straggler 盲区**：NDTimeline 以 microbatch 为粒度记录 forward/backward-compute，无法分析 TP/CP 组内部的 straggler。如果 straggler 均匀影响所有 microbatch，其方法无法检测到。这是一个显著的局限，因为 TP 组通常在同一节点内，TP 级别的不均衡可能也是重要问题。

3. **序列长度不均衡的缓解方案不够完整**：作者提出的序列重分配方案仅在单个作业上验证了 23.9% 的提升，但承认尚未在规模化部署中验证，且可能增加内存需求。此外，该方案只解决 DP 级别的不均衡，对 PP 级别的序列长度不均衡（多 microbatch、大 PP degree 场景）未提供解决方案。

4. **Planned GC 的实用性问题**：论文指出 planned GC 难以在实践中广泛采用（需要手动调参 GC interval），但未提出自动化的替代方案。这个问题的根本原因（Python GC 暂停所有 kernel 启动）实际上暗示了 Python 作为训练框架控制面语言的固有局限。

5. **缺乏与已知缓解方案的系统性对比**：论文主要是分析性工作，对各根因提出的缓解方案都比较初步，缺乏系统性的端到端评估。例如，对 PP stage 不均衡问题仅手动调了一个作业，对 Vocabulary Parallelism 等已有方案只是引用而未评估。

6. **专用集群的外部有效性**：所有分析基于 ByteDance 的专用 LLM 训练集群（无资源竞争、网络过配），这使得通信类 straggler 的影响被显著低估。在共享集群或网络带宽有限的环境中，结论可能截然不同。

---

## 七、AI Infra / MLSys 视角

1. **Pipeline 并行中 loss layer 不均衡**是一个被低估但影响广泛的问题。随着词表规模增长（如 Llama 3 的 128K 词表），loss layer 计算量与 transformer layer 的比值将持续增大，限制 PP 的可用 stage 数量。Vocabulary Parallelism 是一个值得关注的方向。

2. **序列长度变异性对长上下文训练的影响**将随着上下文窗口的持续增长（128K → 1M+）而愈发严重。论文验证了 ∑s² 是准确的计算时间预测指标，这为 microbatch 负载均衡提供了直接可用的 cost model。将序列重分配与 DynaPipe 等 PP 级别的动态调度结合是一个有价值的方向。

3. **Python GC 对大规模训练的影响**提示了一个系统层面的优化机会：将更多训练控制逻辑迁移到 C++ 侧（如 backward-compute 已经不受 GC 影响），或者探索使用 GC 更可控的语言（如 Rust/Mojo）实现训练框架的调度层。

4. **What-if 分析方法论的可迁移性**：论文提出的 OpDuration tensor + 依赖关系模拟 + 选择性修复的分析框架，可以直接应用于推理系统（如 continuous batching 场景下的 straggler 分析）、分布式 RL 训练等场景。SMon 的 heatmap 模式识别思路也值得借鉴到其他分布式 AI 系统的监控中。

5. **值得跟进的研究方向**：
   - 自动化 PP stage 分区：基于 profiling 数据自动调整各 stage 的层数分配，考虑 loss layer、embedding layer 的计算量差异
   - GC-aware 训练调度：自动化 GC interval 选择，或实现分代 GC 与训练步的协调机制
   - 跨 TP 组的 straggler 分析：需要更细粒度的 profiling 来覆盖论文的盲区

---

## 八、总结

本文基于 ByteDance 五个月、3079 个 LLM 训练作业的 trace，通过 what-if 分析方法系统性地量化了 straggler 对大规模 LLM 训练的影响：42.5% 的作业受 straggler 影响超过 10%，全集群 10.4% 的 GPU 小时被浪费。根因分析揭示了三个主要原因——PP stage 分区不均衡、序列长度不均衡和 Python GC——而非传统认知中的硬件故障。论文方法论（OpDuration tensor + 依赖关系模拟）具有较好的通用性，但分析范围受限于 trace 工具的粒度（无法分析 TP/CP 级别 straggler），且缓解方案尚处于初步验证阶段。
