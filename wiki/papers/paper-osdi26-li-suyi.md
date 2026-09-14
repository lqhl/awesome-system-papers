---
type: paper
name: Li-ClusterHeterogeneity
full_title: "Heterogeneity at Hyperscale: Characterization and Scheduling of Large Production AI Clusters at Alibaba"
authors: [Suyi Li, Lingyun Yang, Haoxuan Yu, Sheng Yao, Tianyuan Wu, et al.]
venue: OSDI
year: 2026
tags: [gpu-cluster, workload-characterization, scheduling, heterogeneity, resource-fragmentation]
source_pdf: "[[osdi26-li-suyi.pdf]]"
source_md: "[[osdi26-li-suyi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-13
---

# 超大规模异构 AI 集群的刻画与调度（OSDI 2026）

> **原题**：Heterogeneity at Hyperscale: Characterization and Scheduling of Large Production AI Clusters at Alibaba

> **一句话总结**：对 Alibaba ASI 六个月、155,410 张 GPU 和 81 个部门的生产轨迹分析表明，低有效利用率主要来自跨节点碎片、CPU 不足、网络局部性和生产预留，而非 fractional GPU；IPC 将有 slack 的节点数减少 20.2%，SpotGPU 将 GPU allocation ratio 从 68% 提高到 93%，但异构硬件间的网络、干扰和隔离仍未解决。

## 问题与动机

论文研究一个共享生产集群同时承载开发、训练、在线推理和离线推理时，GPU 为什么仍会闲置。ASI 的规模和工作负载比既有公开轨迹更接近当前生产环境：集群包含多代、多厂商 GPU，任务还带有优先级、CPU/内存需求和网络拓扑约束。

作者的核心判断是，需求旺盛不等于容量可以被有效分配。GPU 可能散落在不同节点，节点可能缺 CPU，跨 access switch（ASW）会损失通信带宽，生产用户也会为流量峰值、故障冗余和突发事件预留容量。因此调度器需要匹配工作负载、硬件、拓扑和优先级，而不只是寻找任意空闲 GPU。

## 关键观察 / 隐含假设

- **观察 1：ASI 的碎片主要来自 stranded GPU、CPU 瓶颈和拓扑约束。** fractional GPU 使用在该集群中很少；对于中等规模请求，未充分占用节点上的 GPU 无法拼成连续多 GPU 资源，而高 CPU/GPU 比请求则常因 CPU 耗尽而失败（图 10、图 13）。
  - **依赖假设**：多 GPU 任务需要连续、同质或 ASW-local 的资源。
  - **可能失效场景**：任务支持跨 ASW 通信，或 GPU sharing 在更小模型上重新普及时，碎片构成会改变。
- **观察 2：生产预留制造了大量可回收但不能直接出售的空闲容量。** Standby 容量在午夜最高可达 10,000 GPU hours，HP-only allocation ratio 为 68%，加入 LP spot 任务后达到 93%（图 9、图 16）。
  - **依赖假设**：HP 任务可以快速恢复，LP 任务可被中断，且用户能够提供有效 checkpoint 或优雅退出逻辑。
- **观察 3：网络拓扑会改变异构 GPU 的调度价值。** 同一 ASW 内放置使 allreduce 带宽比跨 ASW 高 27%（§4.1）。异构 GPU 虽可能按 prefill/decode 阶段提供更好的硬件匹配，却可能把 KV cache 传输置于关键路径。
- **假设 1：GPU 类型应由用户显式指定。** 超过 99% 的任务固定请求 GPU 型号，少于 1% 使用异构 GPU（§3.1）。这反映了软件兼容性、性能可预测性和部署复杂度，而不是调度器可以自由替换硬件。
- **假设 2：在线推理可以安全共享互补资源。** 在线推理的中位 SM 利用率只有 6%、显存利用率为 30%；GenAI 推理约使用 94% 显存却只使用 5% SM，而传统 DNN 约使用 20% 显存和 6% SM（§5.2）。但该互补性尚未被可接受的延迟隔离机制利用。

## 核心方法

### IPC：面向生产约束的 GPU 整理

IPC（iterative partitioned consolidation）以集群快照为输入，目标是迁移任务并腾空尽可能多的节点。它把节点随机划分为独立分区并行处理，使决策保持在分钟级；在每个分区内优先选择 pod 较少、较容易清空的节点。

当目标节点容纳不下待迁移任务时，IPC 使用 ejection chain 递归把其他任务挪走，最多深度为 3。该过程显式遵守 affinity、anti-affinity 和 locked task 约束；ASI 中约 40% 任务被标记为 locked。迁移采用 make-before-break，在新节点启动实例后才终止旧实例，避免服务停机。算法最多迭代五轮，实际边际收益在第三轮后变小。

### 拓扑感知分配

对大型单任务请求，ASI 用 GPU entropy 衡量 GPU 在多个 ASW 上的分布，优先选择能使 entropy 最小的 ASW，并尽量集中分配。该贪心算法对单任务是最优的；多任务联合分配仍是组合问题，生产实现按任务规模降序调度，并复用 IPC 完成带拓扑约束的迁移（§4.1）。

### SpotGPU：回收生产预留

HP 用户可经 API 将任务标为 Standby。平台保留容器但停止服务进程、解除流量，使 GPU 和 CPU 可以分配给折价的 LP spot 任务。HP 需要恢复时，平台先优雅驱逐 LP 任务，再恢复原命令。平均驱逐时间为 13 秒，P95 为 48 秒，少于 5% 的驱逐超过 60 秒并被强制终止。

SpotGPU 的调度先尝试非抢占分配；无法满足 HP 请求时，按 checkpoint 之后的浪费工作量选择 LP 受害者。单个任务的代价为 GPU 数乘以距最近成功 checkpoint 的时间，异构 GPU 时扩展为资源向量。该策略避免驱逐即将完成的任务；相对随机驱逐和不考虑驱逐历史的基线，LP 完成时间降低 24%，HP 性能不受影响（§4.2）。

### 异构 GPU 的软件适配

XPU-A 的纸面规格优于 H20，但未优化的 DeepSeek-R1 性能只有 H20 的 80%。作者在 prefill 阶段沿 attention-head 维度重新分配 Compute Engine 工作，使 4k token、64 heads 的 prefill 计算加速 1.58×；在 decode 阶段修复 Triton 对 SplitKV thread-block layout 的错误变换，并将修复贡献回 Triton。优化集成到 RTP-LLM 后，XPU-A 的 HP 请求量增加 2.5×，在 vLLM 测试中相对未优化版本的延迟改善为 33%（1 RPS）和 43%（2 RPS），并分别超过 H20 2% 和 21%（§5.1）。

## 设计取舍

- IPC 使用启发式而非全局最优规划。25 节点 ILP 约需 5 分钟，100 节点约需两天，而实际分区约含 500 节点；启发式牺牲最优性，换取在线可用性。
- Standby 保留热容器，减少恢复时延，但占用容器和平台管理成本；LP 的进度可能因 checkpoint 间隔过长而丢失。
- ASW-local 分配改善通信，却缩小可用资源池，并可能阻止异构 GPU 混合。论文只给出单任务拓扑策略，没有多任务全局收益数字。
- CPU-only 与 GPU 任务共置能回收 CPU 空闲，但 CPU-job-dominant 节点上的 GPU training 中位和 P90 SM 利用率分别下降 10% 和 18%（§5.2）。

## 实验与结果

- ASI 轨迹覆盖 155,410 张 GPU、81 个部门和六个月；中位 job 运行时间为 5 小时，中位调度延迟为 1 秒，HP 任务 P90 调度延迟为 101 秒（§3.2）。
- IPC 在两个月轨迹回放中将未完全占用节点数减少 20.2%，线上决策时间低于 2 分钟（§4.1）。
- 同 ASW placement 相对跨 ASW placement 将 allreduce 带宽提高 27%；严格 ASW 约束会显著降低 128/256 GPU 请求的可满足数量（§4.1，图 14）。
- SpotGPU 将平均 GPU allocation ratio 从 68% 提高到 93%；平均 90% 的 Standby GPU hours 被回收（§4.2，图 9、图 16）。
- 在线推理中，GenAI 与传统 DNN 的显存/计算使用互补，但现有 MIG、MPS 和 time-sharing 难以同时提供动态性与延迟隔离（§5.2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 有效容量损失主要来自节点、CPU 和拓扑碎片，而非 fractional GPU | 图 10、图 13，§4.1 | ASI 六个月生产轨迹；请求形状由 ASI 用户决定 | 强 |
| IPC 能在生产约束下快速回收整节点容量 | IPC 线上运行低于 2 分钟；两个月回放减少 20.2% slack 节点，§4.1 | 依赖快照、可迁移任务和最大深度 3 的 ejection chain | 中 |
| SpotGPU 能提高容量利用并保持 HP 服务 | allocation ratio 68%→93%；LP 完成时间降低 24%，HP 无性能损失，§4.2 | 依赖 Standby API、60 秒退出窗口和 checkpoint | 强 |
| 异构硬件只有在软件栈匹配后才具有生产吸引力 | XPU-A 优化后请求量 2.5×，vLLM 延迟改善 33%/43%，§5.1 | 主要是 Qwen/DeepSeek、XPU-A 与 H20，不能外推到所有模型 | 中 |

## 批判性分析

### 论证链条

从轨迹测量到 IPC 和 SpotGPU 的设计，论文的链条基本闭合：碎片对应整理，预留对应可抢占 spot，checkpoint 对应抢占代价。IPC 的 20.2% 是回放结果，论文没有给出长期线上容量收益或迁移量分布，因此不能把它直接解释为同等比例的吞吐提升。拓扑感知策略声称单任务最优，但多任务调度只使用降序贪心，整体收益仍未量化。

### 假设压力测试

ASI 中 GPU 型号几乎总由用户固定指定，这使硬件异构成为调度约束。若统一运行时和模型编译器降低了迁移成本，当前采用率可能不再代表未来工作负载。SpotGPU 的代价模型只计入 checkpoint 后的 GPU 工作量，没有明确计入重建通信状态、数据缓存、用户退出脚本和服务质量损失。对于没有频繁 checkpoint 的长任务，该模型可能低估真实代价。

### 实验可信度

生产轨迹规模很大，且包含优先级和网络信息，这是论文相对既有轨迹的优势。IPC 主要以回放验证，SpotGPU 同时有部署指标和基线比较。异构 GPU 优化使用少数 LLM 和推理引擎；多模态、扩散模型以及跨厂商混部没有同等实验覆盖。论文也没有报告 SpotGPU 的长期故障率、HP 恢复尾延迟或租户行为变化。

### 系统性缺陷

论文未详细讨论 IPC 迁移期间的网络流量、缓存重建和 checkpoint 存储开销。SpotGPU 将透明性部分转移给用户定义的优雅退出逻辑，超过 60 秒的任务会被 SIGKILL。在线推理共置缺少可证明的尾延迟隔离；CPU/GPU 共置已有 18% 的 P90 SM 利用率损失，说明简单资源空闲检测不足以保证干扰可控。

## 局限与后续工作

- **局限 1**：轨迹不包含专用集群上的超大规模 foundation-model pretraining，也没有细分 fine-tuning、LoRA 等训练子类型。
- **局限 2**：拓扑感知分配尚未解决多任务联合优化，论文没有报告其集群级收益。
- **后续工作 1**：建立同时考虑 GPU 类型、ASW 带宽、KV cache 传输和阶段性能的多任务调度器，并在 128/256 GPU 请求上报告可满足率、通信时间和成本。
- **后续工作 2**：为在线 GenAI 与传统 DNN 设计动态显存/SM 隔离，分别测量 P99 TTFT、TPOT、吞吐和 OOM 风险。
- **后续工作 3**：扩展抢占代价模型，纳入 checkpoint 写入、恢复、缓存和用户退出行为，并用长期线上故障与恢复数据验证。

## 相关

- **相关概念**：[[GPU-Cluster-Scheduling]]、[[GPU-Fragmentation]]、[[LLMServing]]、[[KV-Cache]]
- **同类系统**：[[vLLM]]、[[RTP-LLM]]、[[Triton]]、[[Kubernetes]]
- **同会议**：[[OSDI-2026]]
