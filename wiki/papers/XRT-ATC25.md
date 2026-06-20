---
type: paper
name: XRT
full_title: "XRT: An Accelerator-Aware Runtime for Accelerated Chip Multiprocessors"
authors: [Neel Patel, Mohammad Alian]
venue: ATC
year: 2025
tags: [runtime, accelerator, scheduling, datacenter, tail-latency]
source_pdf: "[[atc2025-patel.pdf]]"
source_md: "[[atc2025-patel]]"
---

# XRT: An Accelerator-Aware Runtime for Accelerated Chip Multiprocessors (ATC 2025)

> **一句话总结**：关键观察是现有 [[Concord]]/[[TinyQuanta]] 类 runtime 把请求当成「全程在 GP core 执行」，在带 DSA/IAA 的 XMP 上 offload 反而可能比不加速更慢；XRT 用 worker-centric [[Two-Level-Scheduling]] + notification-aware scheduler + ENQCMD software fallback，在 6 个 µs 级服务上吞吐-under-SLO 最高 3.2× unoptimized、最高 32× 无加速器，且从不负向。

## 问题与动机

现代 datacenter server CPU（XMP，Accelerated Chip Multi-Processor）把 DSA、IAA、QAT、DLB 等 fixed-function accelerator 集成在片上，与 GP core 共享内存子系统、支持 shared work queue 和极低 offload tax，目标是让 (de)compression、encryption、memcpy、analytics 等 "datacenter taxes" 以更高能效执行，同时仍满足 µs 级尾延迟 SLO。

硬件已经支持 offload，但 runtime 层仍停留在「同构 CMP」假设：[[Concord]]、[[Shenango]]、[[Shinjuku]]、[[TinyQuanta]] 等系统用 dispatcher + worker 架构做 load balancing 和 request scheduling，默认 end-to-end 请求处理发生在 GP core 上。把 accelerator 硬塞进这些架构会出现三类系统性失败：

1. **Dispatcher-Centric 中央调度器过载**：dispatcher 既要 poll NIC、又要收集所有 accelerator completion notification，在 many-core many-accelerator 系统上迅速成瓶颈。
2. **Worker-Centric 无效唤醒**：类似 TinyQuanta 的 round-robin 本地调度会在 offload 尚未完成时 resume thread，造成大量无效 context switch。
3. **Accelerator 竞争反噬吞吐**：高负载下 accelerator work queue 满，core 在 ENQCMD 处 stall；此时继续 offload 可能比直接在 core 上执行更慢。

作者的核心 claim 不是「加速器一定更快」，而是：**没有 accelerator-aware runtime，片上加速器在 scale 上无法稳定转化为应用吞吐收益，甚至可能拖慢系统**。XRT 针对 XMP 重新划分调度职责并消除上述两类 software overhead。

## 关键观察 / 隐含假设

- **观察 1**：在 XMP 上，centralized dispatcher 同时处理 NIC 与 accelerator notification 会显著压低可持续吞吐。
  - **证据**：DDH workload 上，Worker-Centric baseline 在违反 50× p99.9 slowdown SLO 前约达 2.5 MRPS，Dispatcher-Centric 仅约 1.0 MRPS（Figure 3）。
  - **依赖假设**：accelerator notification 频率与 core 数、请求到达率成正比；dispatcher 单线程处理能力有硬上限。
  - **可能失效场景**：notification 可完全 offload 到 hardware/eventfd、或 dispatcher 可水平扩展时，centralized 设计未必劣势明显。

- **观察 2**：naive Yield 模式会在 offload 未完成时反复 resume worker thread，context switch 开销可占显著端到端比例。
  - **证据**：baseline Worker-Centric runtime 在 DDH 上平均每请求 21 次无效 resumption；单次 ~30 cycles，但累计占 ~4µs 请求延迟的 13%。
  - **依赖假设**：请求采用 Pre-Processing → Accelerable Function offload → Post-Processing 三阶段模型；worker 在 offload 后 yield core 给其他请求。
  - **可能失效场景**：offload 极短、或 Block&Wait 模式已足够、或 scheduler 能直接 sleep 在 completion event 而非轮询 resume 时，该开销可能不主导。

- **观察 3**：accelerator 饱和时，继续尝试 offload 会让 Yield 模式端到端延迟超过 NoAcceleration。
  - **证据**：合成 memcpy + 2µs post-processing workload，负载升至 ~3 MRPS 后 Yield 执行时间超过 NoAcceleration；stall 时间随负载上升成为主因（Figure 4）。
  - **依赖假设**：shared work queue 容量有限；多 worker 可同时在飞多个 offload；memcpy 类函数在数据位于 core private cache 时，DSA offload 甚至可能比 core 更慢。
  - **可能失效场景**：accelerator 容量远大于并发需求、或 workload 以 compute-bound decompress 为主且 accelerator 明显更快时，contention 问题较轻。

- **假设 1**：accelerator 按 FCFS 顺序完成 offload，因此 scheduler 只需跟踪「下一个预计完成」的 completion record。
  - **证据强度**：中。论文直接利用 Intel accelerator interface 的 completion record 机制，并在 Discussion 中将其作为设计前提；未做 out-of-order completion 的压力测试。

- **假设 2**：单次 ENQCMD 的 success/retry 语义足以做 offload 决策，无需阻塞重试。
  - **证据强度**：强。这是 Intel XMP 硬件接口的直接能力；software fallback 在 MC/DMD 等高负载实验中显著优于 RR-Worker/Block&Wait。

- **假设 3**：目标 workload 是 µs 级、轻尾、Poisson 到达的 datacenter microservice，且可用三阶段 accelerable function 建模。
  - **证据强度**：中。6 个 representative workload 覆盖 streaming、KV/DB、recommendation、analytics，但均为实验室合成而非 production trace。

## 核心方法

XRT（XMP RunTime）延续 [[TinyQuanta]] 的 **worker-centric two-level scheduling**：一个 dispatcher core 仅负责 [[Join-the-Shortest-Queue]] load balancing，每个 worker core 维护浅队列（避免空队列 poll 开销）并在本地做 request scheduling。与 baseline 的根本差异在于 worker 端的两项 accelerator-aware 机制。

### Notification-Aware Scheduler

每个 worker 的 scheduler thread 维护两个 ring buffer：

- **Monitoring Set**：cacheline-sized completion records，由 accelerator 在 offload 完成时写入（利用 descriptor 中的 completion address 字段）。
- **Thread Contexts**：指向 userspace work thread（Boost coroutine）的指针数组。

scheduler 在 completion record 与 thread context 间维护逻辑映射。基于 **FCFS 完成顺序**，它只需轮询「下一个预计完成」的 record——L1 命中约 2–3 cycles——而不是盲目 resume 所有 yielded thread。offload 真正完成后才唤醒对应 thread 执行 Post-Processing，从而消除 baseline 中「醒来发现还在等 accelerator」的无效切换。

### Software Fallback

worker 用 [[ENQCMD]] 向 accelerator shared work queue 提交 offload descriptor；指令返回 success 或 retry。XRT **只尝试一次**：retry 时立即在 core 上执行 accelerable function 的 software implementation，而不是 spin 或反复重试。这直接回应观察 3——当 accelerator 已成瓶颈时，把 core 从 stall 中释放出来比坚持 offload 更有价值。

### 端到端请求生命周期

dispatcher 收到请求后用 JSQ 选最短 worker 队列并入队；worker scheduler 把请求交给 idle thread，执行 Pre-Processing；随后单次 offload 尝试，成功则 yield，scheduler 在间隙 poll Monitoring Set；notification 到达后 resume 已完成 offload 的 thread 做 Post-Processing。整个流程依赖 SVM、PASID 和 shared work queue 让多核共享 accelerator 且保持低 offload tax。

深度实现细节回 [[atc2025-patel]] 或 [[atc2025-patel.pdf]]。

## 设计取舍

- **Worker-Centric 而非 Dispatcher-Centric**：把 accelerator notification 分散到各 worker，换取 dispatcher 可扩展性；代价是 scheduler 只有本地队列可见性，无法做全局最优的 core+accelerator 协同调度。
- **Notification polling 而非 event-driven wake**：利用 completion record 的 L1 低成本轮询，避免通用 OS/event 路径开销；代价是依赖 FCFS 假设，且 polling 行为本身在极端 notification 密度下可能仍有成本（论文未量化）。
- **单次 ENQCMD + software fallback**：避免 accelerator 饱和时 core stall；代价是在 contention 高时放弃 accelerator 能效，且 memcpy 类函数 fallback 后可能重复占用 core bandwidth。
- **浅 per-worker 队列 + userspace coroutine**：快速切换、近似 processor sharing；代价是实现复杂度高，且与 Boost coroutine 绑定，故障隔离/debug 难度高于内核线程模型。
- **单地址空间 userspace runtime**： programmer 仍写同步 API，XRT 透明管理调度；代价是默认不适合 public cloud 多租户互信隔离（论文承认需额外 userspace process abstraction）。

## 实验与结果

- **平台**：Intel Xeon 8571N（5th gen），4× [[IAA]] + 4× [[DSA]]，26 cores（1 dispatcher + 25 workers），双 NUMA（一端 load generator，一端 server）。
- **对比配置**：NoAcceleration、Block&Wait、RR-Worker（Section 3 naive worker-centric）、XRT。
- **指标**：p99.9 slowdown，相对 Block&Wait 下 uninterrupted accelerated execution 归一化。
- **DDH / DC（decompress 类）**：NoAcceleration 在低负载即差；XRT 与 RR-Worker 都优于 Block&Wait（Yield 提高 core 利用率），XRT 进一步优于 RR-Worker。
- **DMD / MC（memcpy 类）**：只有 XRT 能从 offload 获益；Block&Wait 因 cache-resident 数据 offload 更慢而无法超过 NoAcceleration；RR-Worker 高负载下 MC 慢 14%、DMD 慢 188%（accelerator blocking）。
- **MMP / UFH**：pre/post-processing 占 99%+ 执行时间，各 runtime 差异可忽略。
- **总体**：6 workload 上 XRT 相对 unoptimized runtime 吞吐-under-SLO 最高 **3.2×**，相对 NoAcceleration 最高 **32×**，且**从不慢于无加速器系统**。

## Critical Analysis

### 论证链条

论文论证链条清晰且层层递进：measurement 证明现有 CMP runtime 架构在 XMP 上失效（dispatcher bottleneck、无效 resume、accelerator stall）→ 设计空间探索排除 Dispatcher-Centric → 两个 targeted mechanism（notification-aware scheduler、software fallback）分别对应两类 overhead → 六 workload 上验证「永不负向 + 显著正向」。贡献定位准确：不是新 accelerator API，而是 **runtime 如何把 hardware offload 能力转化为 SLO 约束下的吞吐**。

较弱环节在于 **从 representative microbenchmark 到 production datacenter service 的外推**。论文证明了 scheduling overhead 和 contention handling 的重要性，但没有证明真实服务（更复杂 control flow、更多 accelerator 类型、动态 tenant 行为）仍可用三阶段模型充分近似。

### 假设压力测试

- **FCFS completion 假设**：若未来 accelerator 支持重排、多队列优先级或 QoS，仅 poll「下一个预计完成」可能唤醒错误 thread 或引入额外等待。论文未覆盖。
- **单次 retry fallback**：在 offload 短暂饱和但很快恢复时，fallback 到 core 可能浪费一次 accelerator 机会；论文未评估「短暂 retry 后成功」与「立即 fallback」的 tradeoff 曲线。
- **memcpy/cache locality**：DMD/MC 结果表明 offload 收益高度依赖数据位置与 accelerator 数据路径；换 NUMA 布局、不同 cache footprint 或更大 payload 可能改变 crossover point。论文只在固定 testbed 上展示。
- **多 accelerator 类型混部**：实验主要用 DSA 或 IAA 子集；QAT/DLB 及多 accelerator 同时竞争同一请求流水线的行为未测。
- **论文已证明**：worker-centric + 两项优化在 Intel 8571N、六类合成 workload 上优于 baselines；**推断**：production trace 中若 pre-processing 占比更高（如 MMP），XRT 优势会缩小。

### 实验可信度

优点：baseline 覆盖全面（无加速、Block&Wait、naive RR-Worker、XRT），metric 选用与 [[Concord]]/[[TinyQuanta]] 一致的 p99.9 slowdown，硬件为真实 Intel XMP 且启用 SVM/shared queue/ENQCMD；关键 motivation 实验（Figure 3/4）有具体数字支撑设计选择。

边界：workload 为自建 representative service，到达过程 Poisson、服务时间 exponential，与真实 bursty/trace replay 有差距；仅 26-core 单节点，未测多 socket 扩展或更多 accelerator SKU；MMP/UFH 的「无收益」案例说明结论对 workload shape 敏感，但论文未给出判定规则（何时 XRT 值得部署）。

### 系统性缺陷

- **多租户与隔离**：论文明确 XRT 是单地址空间 userspace runtime，public cloud 多租户需额外 isolation 层；未评估 fallback 路径是否引入侧信道或资源争抢公平性问题。
- **故障恢复**：accelerator 错误、completion record 丢失、ENQCMD 非 retry 类失败时行为论文未讨论。
- **可观测性 / 运维**：transparent scheduling 降低 programmer 负担，但也隐藏 offload/fallback 决策，排障时难以判断请求走了 hardware 还是 software path。
- **尾延迟分布**：主指标是 p99.9 slowdown，未深入分析更高分位或 SLO violation 的恢复行为。
- **能耗**：强调 accelerator 能效动机，但实验只报 throughput-under-SLO，未测 energy per request。

## 局限与 Future Work

- **局限 1**：单地址空间设计不适合未隔离的多租户 public cloud；私有云/单租户场景更合适。
- **局限 2**：仅 Intel Xeon 8571N 单节点验证；多 socket、更多 accelerator、不同厂商 XMP 的泛化性未知。
- **局限 3**：workload 为合成 representative service；未用 production trace 验证三阶段 accelerable function 抽象是否覆盖主流微服务。
- **局限 4**：当 pre/post-processing 主导（MMP、UFH）时 runtime 优化几乎无收益；论文未给出 deployment 前的 profiling 判据。
- **Future work 1**：结合 userspace process abstraction（如 fast core scheduling 方向）做 tenant 隔离，测量隔离开销下 XRT 是否仍保持吞吐优势。
- **Future work 2**：在 production RPC/streaming trace 上测量 accelerator contention 与 fallback 触发率，验证 software fallback 阈值是否需要自适应。
- **Future work 3**：扩展 scheduler 支持 out-of-order completion、多 accelerator 类型协同、更接近 processor sharing 的全局策略。
- **Future work 4**：在 ARM ST64BV、RISC-V Atomic IO Enqueue 等等价 ISA 上移植 XRT，量化 notification 机制差异带来的性能变化。

## 相关

- **相关概念**：[[On-Chip-Accelerator]]、[[Two-Level-Scheduling]]、[[ENQCMD]]、[[DSA]]、[[IAA]]、[[Tail-Latency]]
- **同类系统**：[[TinyQuanta]]、[[Concord]]、[[Shenango]]、[[Shinjuku]]
- **同会议**：[[ATC-2025]]