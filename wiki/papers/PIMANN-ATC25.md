---
type: paper
name: PIMANN
full_title: "Turbocharge ANNS on Real Processing-in-Memory by Enabling Fine-Grained Per-PIM-Core Scheduling"
authors: [Puqing Wu, Minhui Xie, Enrui Zhao, Dafang Zhang, Jing Wang, Xiao Liang, Kai Ren, Yunpeng Chai]
venue: ATC
year: 2025
tags: [anns, processing-in-memory, upmem, vector-search, scheduling]
source_pdf: "[[atc2025-wu-puqing.pdf]]"
source_md: "[[atc2025-wu-puqing]]"
---

# Turbocharge ANNS on Real Processing-in-Memory by Enabling Fine-Grained Per-PIM-Core Scheduling (ATC 2025)

> **一句话总结**：基于 UPMEM 上 CPU/PU 共享 DDR 总线互斥导致 batch gang-scheduling 在 inter-batch 与 intra-batch 双重空转（strawman 仅达理论吞吐 18.2%）这一观察，PIMANN 改造每个 PU 的隐藏 control interface 做 per-PU 细粒度总线仲裁，配合 persistent kernel、coroutine 隐藏切换延迟与 selective replication 动态调度，在真实 UPMEM 上把 [[IVFPQ]] [[ANNS]] 吞吐相对 [[Faiss]]-CPU 提升 5.9–10.4×、相对 batching PIM baseline 提升 2.4–2.9×，PU 利用率从 ~20% 提到 65–83%。

## 问题与动机

[[ANNS]] 是推荐、语义搜索、[[RAG]] 等 AI 基础设施的核心算子，其 compute-to-memory access ratio 接近 1:1，本质是 memory-bound。CPU 有 TB 级容量但 DRAM 带宽约 200 GB/s；GPU 算力与 HBM 带宽强，但单卡显存（如 H100 100 GB）装不下十亿级高维向量。两者都受 [[Memory-Wall]] 约束。

[[UPMEM]] 是 2022 年首个商用真实 [[Processing-in-Memory]] 硬件：20 块 DIMM、2,560 个 PU、聚合内存带宽约 2–2.5 TB/s，看起来非常适合 [[ANNS]]。但作者实现的 strawman PIM ANNS（基于 [[Faiss]] 把 distance computation offload 到 PU）在 SPACE-1B 上只达到 UPMEM 理论吞吐上限的 **18.2%**，且 **65%** 时间内活跃 PU 数为 0（两 batch 间 CPU 拷数据时 PU 全 idle）。

根因是现有 PIM 编程模型的 **batching paradigm**：因 CPU 与 PU 不能同时访问共享 DDR 总线，应用只能在 kernel 边界与 PIM 交互——CPU 先拷完整 batch 到 MRAM，再 gang-launch 全部 PU，最后回收结果。这带来两类 under-utilization：

- **Inter-batch**：两 batch 间 PU 必须等待 CPU 完成 MRAM 读写，单次 gap 超过 1.21s，占单 batch 时长 65%。
- **Intra-batch**：UPMEM PU 是 share-nothing 弱核，batch 内 query 负载不均时 straggler PU 拖累整批完成时间。

PIMANN 的 claim 边界明确：它不是新 ANN 算法，而是在真实 UPMEM 上重新设计 **调度与数据放置**，让 cluster-based [[IVFPQ]] 尽可能吃满 PIM 并行度与内存带宽。Graph-based ANNS 因 PU 间通信带宽仅 ~0.41 GB/s 被作者明确排除。

## 关键观察 / 隐含假设

- **观察 1：UPMEM 的 batching 低效来自「kernel 运行期间 PU 独占总线」这一可被打破的假设，而非硬件算力不足。** 每个 PU 除 DDR 数据路径外，还有一条未文档化的 control interface（经 WRAM 路由，完全绕过 DDR 总线），原本用于 launch/sync kernel，可被改造为 runtime 总线仲裁与 CPU-PU 控制消息通道。
  - **依赖假设**：该 control interface 在未来 UPMEM 代际中仍会保留（作者 Discussion 认为它是标准化控制机制）；driver 可被修改以在 PIM 运行时 expose MRAM 给 CPU。
  - **可能失效场景**：未来硬件收紧 userspace 对 MUX/control interface 的访问；固件更新改变 WRAM 消息语义；不同 PIM 厂商不提供类似旁路控制通道。

- **观察 2：ANNS online phase 中最可并行、最适合 offload 的是 IVFPQ 的 distance computation（step ➌），其余 cluster filtering、LUT 构建、Top-K 仍在 CPU 完成。** 论文聚焦 IVFPQ 正是因为其遍历 cluster 内点、查 LUT 的距离计算高度并行，且对 PU 弱浮点（整数 ALU + 软件浮点）仍可接受。
  - **依赖假设**：`nprobe`、cluster 大小分布使得单 query 在 PU 上的 distance 计算量足以摊销 CPU↔PIM 数据搬运与总线切换开销；query 到达率足够高以维持 persistent kernel 持续工作。
  - **可能失效场景**：极低 QPS 下 persistent kernel 空转；高 recall 需要 probe 大量 cluster 时 CPU 侧 LUT/调度成为瓶颈；graph ANNS 或需要跨 PU 随机访存的算法。

- **观察 3：cluster 访问热度高度倾斜，per-PU 调度必须配合 selective replication 才能避免 hotspot straggler。** 在 share-nothing 架构下，热 cluster 若只放一个 PU，会成为负载瓶颈；副本数按 popularity \(p_i = s_i \times f_i\) 相对平均负载决定。
  - **依赖假设**：离线/在线统计的 cluster 热度在短时间窗内相对稳定，可用滑动窗口（如 1000 queries、2× 变化阈值）检测 hotness shift；额外副本的 MRAM 开销可接受。
  - **可能失效场景**：查询分布突变（冷启动、营销活动、embedding 版本切换）使 live adjustment 跟不上；MRAM 容量限制 replica 上限；多租户隔离要求固定分片而非动态副本。

- **隐含假设：相邻 PU 共享物理 MUX，最小总线切换粒度是 PU pair。**
  - **证据强度**：强。作者通过实验确认直接访问某 PU 的 MRAM 会导致相邻 PU 任务异常，并据此设计 pairwise cluster slicing 让相邻 PU 同时活跃。

## 核心方法

PIMANN 的核心是 **per-PU scheduling paradigm**：不再把「整批 query」作为原子调度单元，而是让 CPU 在 runtime 持续向单个 PU 投递 ANNS 请求，并通过细粒度 MUX 仲裁在 CPU-side / PU-side 间切换 MRAM 访问权。

### Persistent PIM Kernel

系统初始化时启动一个长驻 PIM kernel，每个 PU 循环执行：从消息队列 dequeue 请求 → 等待 CPU 拷入 LUT 等输入 → 切到 Running 做 distance computation → 切到 WaitCPUCopy → 等待 CPU 取回结果。与 batching 不同，PU 在两次请求之间不再整体 idle，从而消除 inter-batch gap。

### Hot Transfer：控制路径与数据路径分离

- **控制路径**：在 WRAM 上经 control interface 实现 per-PU 消息队列，存放 query ID、ownership 切换命令等小消息（队列容量仅数十字节，放不下 32 KB 级 LUT）。CPU 侧用专用线程轮询各 PU 队列（PIM 无法 interrupt CPU）。
- **数据路径**：修改 UPMEM driver，使 PIM 运行时 CPU 仍可通过 mmap 直接读写 MRAM；启动前用 `dpu_copy_to` 记录变量符号→MRAM 偏移映射。写 MRAM 需做 transpose 以匹配 UPMEM memory-level parallelism。

### Per-PU Bus Ownership Switching

每个 PU 的 MUX 寄存器映射到 userspace。WaitCPUCopy→Running：CPU 拷完数据后发 ownership transfer 消息，PU 轮询收到后安全读 MRAM。Running→WaitCPUCopy：PU 发消息给 CPU，CPU 切 MUX 并 ack。MUX 状态在 userspace 缓存以避免频繁读硬件。

**Pairwise switching**：因相邻 PU 共享 MUX，切换粒度最小为 2 个 PU；为此把 cluster slice 成两半放到相邻 PU，尽量让 pair 同时工作，减少「为切一个 PU 而浪费相邻 PU」的开销。

**Coroutine 隐藏延迟**：单 PU 任务可达数 ms；轮询一个 rank（64 PU）消息队列需 0.9 ms。PIMANN 在 CPU 侧用 Boost coroutine，优先调度 MUX 已在 CPU-side 的 PU，并对 PU-side 任务做基于确定性执行时间的 predictive scheduling，约带来 **3×** 吞吐（相对无 coroutine）。

### Per-PU Query Dispatching + Selective Replication

- **数据放置**：按 cluster popularity 决定 replica 数；MRAM 切成固定 slot 放 uniform-size cluster slice，降低碎片；在 pairwise PU 约束下贪心分配 slice 以均衡负载。
- **Live adjustment**：滑动窗口监测访问频率，热度变化超过 2× 阈值时增删副本；persistent kernel 保证调整无需 shutdown PIM。
- **在线分发**：维护 cluster→PU replicas 映射表，每次选消息队列最浅的 PU 发送请求。

CPU 仍负责 IVFPQ 的 cluster filtering、LUT 构建与 Top-K 聚合；PIM 只做最并行的 distance 计算。深度实现细节回 [[atc2025-wu-puqing]] 或 [[atc2025-wu-puqing.pdf]]。

## 设计取舍

- **取舍 1：打破 batching，换取 driver 侵入与低 CPU-PIM 带宽。** 收益是消除 65% inter-batch idle、降低端到端延迟；代价是修改官方 UPMEM driver、依赖未文档化 control interface，且 per-PU 拷贝带宽仅 ~0.41 GB/s（batch 可利用 8-PU bank parallelism 更高）。作者认为单 query 数据搬运时间仍可忽略（Figure 15 紫色 bar）。
- **取舍 2：per-PU 调度 + pairwise MUX，而非 per-8PU 调度。** 收益是避免 cluster 切 8 份带来的 8× top-k 计算冗余，且调度更细；代价是相邻 PU 必须配对激活，硬件电路限制带来资源浪费，需 cluster slicing 补偿。
- **取舍 3：selective replication 换 load balance，牺牲 MRAM 容量与放置复杂度。** 收益是消除 hotspot straggler，per-PU dispatching 带来 88–112% 额外吞吐；代价是热 cluster 多副本占用 MRAM，live adjustment 增加运维与一致性复杂度。
- **边界条件**：在 UPMEM 单机、IVFPQ、高 QPS、cluster 热度可预测/可监测的场景下设计优雅；在需 graph ANNS、低 QPS、无 UPMEM 硬件、严格多租户隔离或不愿改 driver 的环境会变脆。

## 实验与结果

- **平台**：2× Intel Xeon Silver 4210、128 GB DDR4、20× UPMEM DIMM（2,560 PU @ 400 MHz、每 PU 16 threads）、Ubuntu 22.04；GPU 对比用 RTX A6000。默认 SPACE-1B、recall@10=0.9、4096 clusters、coroutine=4、slice size=100K。
- **数据集**：SPACE-1B（10 亿 100 维向量）、SIFT-1B（10 亿 128 维向量）。
- **Baselines**：[[Faiss]]-CPU、自实现 batching PIM 系统 PIMANN-Batch（按 DRIM-ANN 论文复现）、Faiss-GPU（全量向量在 GPU 显存）。
- **吞吐（Exp #1）**：PIMANN-Batch 比 Faiss-CPU 高 2.4–3.7×；PIMANN 再比 PIMANN-Batch 高 2.4–2.9×；相对 Faiss-CPU 总提升 **5.9–10.4×**。相对 Faiss-GPU 高 **2.4–3.7×**。
- **延迟（Exp #2）**：PIMANN-Batch 平均延迟比 Faiss-CPU 高 7.1–10.5×、P99 高 1.7–8.8×（inter-batch 阻塞）。PIMANN 相对 PIMANN-Batch 平均延迟降 **32–43%**、尾延迟降 **26–63%**。
- **PIM 利用率（Exp #3）**：PIMANN 活跃 PU 积分利用率 **65–83%**（运行时约 80% 稳定），PIMANN-Batch 仅 ~20%。
- **技术消融（Exp #4–#6）**：coroutine 约 **3×** 吞吐；persistent kernel 单独贡献 30–70% 吞吐；per-PU dispatching 再贡献 88–112%。无 selective replication 时单 PU hotspot 明显。
- **能效与成本（Exp #7–#8）**：PIMANN 功耗效率比 Faiss-GPU 高 1.6–2.5×（UPMEM 总功耗 462W vs A6000 ~300W）。QPS/$：PIMANN **0.233** vs Faiss-CPU 0.096（2.4×）、Faiss-GPU 0.049（4.8×）。

## Critical Analysis

### 论证链条

论文的 efficiency 论证链条在 UPMEM 单机 IVFPQ 场景下较闭合：先用 Figure 1/5 量化 batching 的 inter/intra-batch under-utilization（18.2% 理论上限、65% 零活跃 PU 时间）→ 指出根因是「kernel 期间总线互斥」这一编程模型假设 → 用 control interface 旁路通道 + driver 修改实现 runtime 仲裁 → persistent kernel 与 per-PU dispatching 分别对应两类 under-utilization → 利用率、吞吐、延迟分解与消融实验互证。

主要跳步在 **「fully harness UPMEM potential」** 与 **production ANNS** 之间。论文证明的是 IVFPQ distance-computation offload 在特定硬件上的调度效率，没有评估完整向量数据库能力（插入、删除、过滤查询、多索引、一致性语义）。相对 Faiss-GPU 的容量优势（十亿向量放 PIM MRAM vs GPU 显存）是重要卖点，但实验未覆盖超单机 MRAM 总量的索引分片与跨节点查询。

### 假设压力测试

最脆的是 **硬件与 driver 依赖**。整套方法建立在 reverse-engineer 未文档化 control interface、修改 UPMEM SDK、暴露 MUX 到 userspace 之上。企业部署若无法获得厂商支持或签名驱动，系统不可移植。作者声称该接口会跨代际保留，但这仍是推断而非厂商公开承诺。

第二个压力点是 **算法适用范围**。Graph-based ANNS（[[HNSW]]、DiskANN 类）因 0.41 GB/s CPU-PIM/PU-PU 带宽被排除；真实生产常混合 IVF 与 graph 或需要 rerank、filter。IVFPQ 对高 recall 需增大 `nprobe`，CPU 侧 LUT 与调度开销上升，可能重新让 CPU 成为瓶颈——论文在 recall 0.84–0.94 范围测试，但未展示 CPU 饱和点。

第三个压力点是 **workload 与热度模型**。Selective replication 假设热度可通过滑动窗口监测并 live 调整；对突发流量、embedding 漂移、多租户交错查询，副本增删可能造成 MRAM 抖动与短暂负载失衡。论文未给出 adjustment 期间的 tail latency 或查询正确性（副本一致性）测量。

第四个压力点是 **pairwise MUX 约束**。这是硬件电路导致的结构性效率损失；虽用 cluster slicing 缓解，但在 cluster 数量少或热度极端倾斜时，仍可能出现「为配对而空转半个 pair」的资源浪费。论文未量化该 waste 占理论上限的比例。

### 实验可信度

**强项**：在真实商用 UPMEM 上完成端到端评估，非模拟；PIMANN-Batch 作为公平 PIM 对照（同硬件、同 IVFPQ）；消融实验分离 persistent kernel、dispatching、coroutine、replication 贡献；同时报告吞吐、平均/P99 延迟、利用率、功耗与 QPS/$。

**弱点**：
- Faiss-GPU baseline 受限于单卡显存规模，与 PIMANN 的容量场景不完全同构；GPU 侧未用分层/分片方案（如 [[RUMMY]]、BANG）做更强对比。
- 未与 [[CXL-ANNS]]、FPGA/SmartNIC ANNS（如 [[Snary-ATC25|SNARY]]）、[[DiskANN]] 等异构内存路线比 cost-normalized performance。
- 数据集是标准 billion-scale benchmark，缺少 production query trace 的时序到达、热度漂移与混合操作。
- Tail latency 在并发多客户端、driver 故障、live replica migration 下的表现论文未讨论。

### 系统性缺陷

**可运维性**：修改内核/driver、依赖未公开硬件细节，使升级、安全补丁与多机部署复杂。论文未讨论版本兼容、回滚策略、可观测性（per-PU 队列深度、MUX 等待时间、副本迁移指标）。

**尾延迟与隔离**：Per-PU 调度 + 轮询 2560 个消息队列在极高并发下 CPU 调度开销可能成为新瓶颈；多租户场景下 selective replication 与 live adjustment 可能互相干扰。论文未讨论 QoS 隔离。

**故障恢复**：persistent kernel 长跑期间 PU 挂死、MUX 状态不一致、消息队列损坏如何检测与恢复——论文未讨论。

**能耗**：UPMEM 总功耗 462W 高于 RTX A6000 ~300W；虽 QPS/Watt 仍优于 GPU，但机房 TCO、散热与碳排放在大规模部署时需与 QPS/$ 一并权衡。

## 局限与 Future Work

- **局限 1：仅支持 cluster-based IVFPQ，明确放弃 graph ANNS。** Future work 应在更高 PU-PU 带宽的下一代 PIM 或 hierarchical 索引上复用 per-PU scheduling 思想，并量化通信受限时的 break-even point。
- **局限 2：强依赖未文档化接口与修改 driver，可移植性受限。** Future work 应推动厂商标准化 runtime bus arbitration API，或评估同样思路在 [[CXL]]-PIM、HBM-PIM 等架构上的可复用性（作者 Discussion 已提及多类 PIM 有类似特征）。
- **局限 3：实验以 throughput/recall 为主，缺少 production ops 指标。** Future work 应测量多租户并发下的 P99/P999、live replica migration 抖动、索引更新与查询交织、故障注入后的恢复时间。
- **局限 4：pairwise MUX 导致结构性资源浪费。** Future work 可在硬件允许时评估更细或更粗切换粒度的最优性，或结合 pipeline batching 在冗余与带宽间做动态选择。
- **局限 5：与 GPU 分片/分层 ANNS 的对比不完整。** Future work 应以同等召回率曲线对比 Faiss-GPU sharding、[[HM-ANN]]、[[CXL-ANNS]] 等，并统一 memory footprint、硬件成本与功耗。

## 相关

- **相关概念**：[[ANNS]]、[[Vector-Search]]、[[IVFPQ]]、[[Product-Quantization]]、[[Processing-in-Memory]]、[[Memory-Wall]]、[[RAG]]、[[Top-K-Selection]]
- **同类系统**：[[Faiss]]、[[Milvus]]、[[CXL-ANNS]]、[[DiskANN]]、[[Snary-ATC25|SNARY]]、DRIM-ANN
- **同会议**：[[ATC-2025]]
- **对比**：PIM per-PU scheduling vs PIM batching paradigm；PIM 大容量 vs GPU 高算力 ANNS