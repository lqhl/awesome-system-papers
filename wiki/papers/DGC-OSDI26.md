---
type: paper
name: DGC
full_title: "Shaving the Peaks: Taming Tail Latency for Managed Workloads via Disaggregated Garbage Collection"
authors: [Hongtao Lyu, Yuhan Li, Mingyu Wu]
venue: OSDI
year: 2026
tags: [garbage-collection, disaggregation, rdma, tail-latency, resource-pooling, area/operating-systems]
source_pdf: "[[osdi26-lyu.pdf]]"
source_md: "[[osdi26-lyu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# DGC：用解耦式垃圾回收削平托管应用的尾延迟

> **原题**：Shaving the Peaks: Taming Tail Latency for Managed Workloads via Disaggregated Garbage Collection

> **一句话总结**：DGC 发现 concurrent GC 虽缩短 STW pause，却会在受限容器中周期性抢走 mutator CPU；它把最重的 marking 放进多个 JVM 共享的 SHM/RDMA 服务，并用 CP-SAT 错开 GC burst，在相同总 CPU 预算下将 SPECjbb P99 最多降低 64.4%、critical-jOPS 提高 24.0%，但极高应用负载、低 GC pressure 和 12 个 RDMA clients 已暴露边界。

## 问题与动机

现代 [[Garbage-Collection|垃圾回收]]器常让 marking 与应用线程（mutator）并行，从而避免长时间 stop-the-world（STW）。但在多租户云中，JVM 通常只有 1–8 cores 和较小 heap；并发 marker 没有多余 CPU，只能和请求处理线程竞争。

SPECjbb 的 8-core、4 GB 实验说明了这个问题：没有 GC 时 CPU 有 45.7% idle；concurrent marking 开始后，总 CPU 达 98.2%，应用占比从 53.3% 降到 32.6%，throughput 降 47%，平均 latency 增到 10.5×（图 1、§3）。所以“pause 很短”不等于“tail latency 很低”。

简单调参也不理想。为每个 JVM 永久多配 cores 会让 GC 空闲期浪费资源；加 heap 会加重数据中心的内存瓶颈；把 marker threads 从 8 降到 4 虽拉长每次 marking，却制造更多 floating garbage，使 GC frequency 增 11%，P99 没改善、P50 反而高 20%（表 2）。论文因此把周期性 GC 当成适合跨 runtime 池化的 bursty service。

## 关键观察 / 隐含假设

- **观察 1：干扰来自周期峰值，不是平均 CPU 不足。** 同一 workload 在非 GC 阶段有大量 idle，在 marking 阶段却接近满载。若把多个不同步的 GC burst 放进共享 pool，可以用相同总 cores 提供更稳定的 mutator CPU（图 1、§3）。
- **观察 2：并发 GC 中 marking 最适合外移。** Marking 是 CPU-heavy、只读对象图的阶段；evacuation、load barrier 和最终一致性处理与本地 heap 关系更紧，DGC 把它们留在 JVM（§4–§5）。
- **观察 3：SATB 允许 marker 看到陈旧、分段的 heap。** Snapshot-at-the-Beginning write barrier 会记录被覆盖的旧引用；远端遍历与 SATB buffer 的并集仍覆盖逻辑快照中的 live objects，不要求一次复制完整 heap（§5.1）。
- **观察 4：JVM region 是合适的软件 page。** 2 MB region 与 bump-pointer allocation 保留对象 locality；4 GB heap 的压缩 region page table 只有约 4 KB，可放进 48 KB L1d，避免普通 4 KB remote paging 的 translation 与 fault 开销（§5.2）。
- **隐含假设 1：多个 runtime 的 GC 周期可以被可靠预测并错开。** Scheduler 依赖 free memory、allocation rate、历史 live-set 和 marker duration；突然的 allocation burst 会让 deadline 前移。
- **隐含假设 2：平台与租户处于同一信任边界。** DGC service 能读取应用 heap、class metadata 和 SATB buffer。论文面向 operator-managed JVM，不是互不信任租户可直接使用的通用云服务（§4.2、§9）。
- **隐含假设 3：marking 是 tail 的主因。** 低 allocation workload、evacuation/compaction 或应用本身成为瓶颈时，外移 marking 不会有明显收益。

## 核心方法

### 1. 只把 concurrent marking 变成共享服务

DGC 包含 Disaggregated Marking Engine 与 Global GC Orchestrator（图 2）。同机模式 DGC-SHM 用共享内存读取 heap；跨机模式 DGC-RDMA 用 200 Gbps [[RDMA]] 拉取 heap region。Served JVM 仍负责初始/最终短 STW、write barrier、evacuation、reclamation 和 degenerated GC。

这不是把每个 JVM 的 GC cores 简单放到另一台机器。一个 marker pool 同时服务多个 JVM，orchestrator 决定每个周期何时开始、用几条线程，避免多个 marking 同时占满 pool（§4、§6）。

### 2. SATB 维持远端标记正确性

周期开始时，JVM 在短 STW 中固定 roots 和 heap state。应用恢复后，DGC 一边复制 region，一边遍历已经到达的对象图；mutator 覆盖引用时，本地 SATB barrier 记录旧 edge。DGC 定期取得 SATB entries，最后把 liveness bitmap 写回 JVM，再由最终短 STW 处理尚未同步的少量 roots（图 3、§5.1）。

关键不变量是：快照开始时 live 的每条可达路径，要么仍在 DGC 看到的 heap edge 中，要么由 SATB buffer 补上。Marker 本身不回收对象，所以可以在由不同时刻 region 拼成的非一致视图上工作。论文给出算法论证，但没有 model checking 或大规模并发 mutation 的错误注入。

### 3. Region paging 让复制与图遍历重叠

DGC-RDMA 在服务端维护部分 heap cache。对象引用指向未缓存 region 时，marker 不等待，而是把 reference 放进该 region 的 thread-local pending queue；region 到达后，control thread 合并 queue 并交给一条 marker thread，避免 bitmap cache-line contention（§5.3）。

每个 region 有 8-byte state/counter：状态为 `NotCached/OnTrans/Cached/OnEvict`，counter 相当于重入读锁。GC thread 先原子增加 counter 再检查状态；RDMA thread 只有 counter 为 0 才能 CAS 改状态或覆盖 cache，防止扫描中 region 被换出。

Paging policy 用未处理 grey-object 总大小估计 region hotness；未缓存 region 先以 pending reference 数和平均对象大小估计。只有候选热度超过 victim 一个倍率才换入，避免 thrashing。启动时先 prefetch 含 roots 的 region，marker 尚未分配 cores；动态 class 则借助 APPCDS 与 system-dictionary hook 在每轮前同步（§5.4–§5.5）。

### 4. CP-SAT 同时选择开始时间和线程数

每个 JVM monitor 暴露 free memory、allocation rate 与历史 marking duration。Coordinator 估计 `deadline = free memory / allocation rate`，并为不同 thread count 估计 duration。约束是每个 GC 必须在 OOM 前完成，任意时刻 active marker threads 不能超过 pool cores；目标是在安全范围内尽量晚开始，减少 SATB floating garbage（§6.1–§6.3、附录 B）。

Coordinator 每 10 ms 重算一次。单 instance solve 约 5 ms，12 backends 时为 11.1 ms；后者已经略长于 monitoring tick，但 GC task 通常持续数百 ms。冷启动时先用本地 Shenandoah 学习；workload drift 超过 headroom 时，本周期回退本地 concurrent GC（§6.4）。

### 5. 回退优先保进程正确性，不保证低尾延迟

DGC service 不可达时，后续周期静默退回本地 Shenandoah。若服务在 marking 中失败，当前周期可能错过 deadline并进入 Shenandoah degenerated STW；论文在 SPECjbb 中称该 pause 约 100 ms。Trigger 有 version tag，重启后的 coordinator 不会执行旧计划（§6.4）。

这让最坏情况接近现有 collector 的保守路径，但共享服务失败会同时让许多 JVM 失去低尾延迟；论文没有系统性的 crash、network partition 或 recovery experiment。

## 设计取舍

- **稳定应用 CPU 换远端 CPU、内存和网络。** 总 core budget相同，但 DGC-RDMA 还需要 heap cache、NIC 与流量；成本不是“免费 idle cores”。
- **只外移 marking 换较小正确性协议。** Evacuation 与 load barrier 留在本地，降低远端复杂度，却保留 compaction 阶段的 residual latency spike（图 5）。
- **共享 pool 换协调依赖。** 多 runtime 能平滑 burst，但 deadline 预测错误、同步 GC storm 或 coordinator 故障会扩大 blast radius。
- **Region 粒度换 locality。** 大 page 降 translation/round trips；引用分散、region 内大多无关对象时，会读入无用数据。
- **CP-SAT 通用性换 solver 开销。** 异构 workload 不需手写 heuristic，但系统依赖 OR-Tools，规模增大后 solve time 会接近控制周期。
- **中等负载优化换极高负载容量。** DGC JVM 少了 `c` 个本地 cores；应用本身饱和时，它比拥有 `8+c` cores 的 baseline 更早出现 P99 divergence（图 4）。

## 实验设计

DGC 基于 OpenJDK 17 Shenandoah，实现 10,383 行 C/C++。两台服务器各有双路 Xeon Gold 6430，每台共 64 physical cores、128 GB memory，关闭 SMT；每台有 200 Gbps BlueField-3，接 [[PCIe|PCIe]] 4.0×16（§7、§8.1）。

应用包括 SPECjbb2015、两 RegionServer 的 HBase 2.5.11/YCSB，以及 DaCapo 23.11 中 9 个能报告 request latency 的 workload。基线是 Shenandoah 和 JDK17 默认 G1。每个 heap 设为该应用能在 Shenandoah 运行的最小值的 2×。

CPU 对比刻意保持总预算相同：baseline 的 `N` 个 JVM 各用 `8+c` cores；DGC 的每个 JVM 只用 8 application cores，再由共享 service 使用 `N×c` cores。SPECjbb/HBase 的 `c=2`，小 heap、高 GC pressure 的 DaCapo 为 `c=4`。因此收益来自资源时间复用，但 DGC 应用在极高 load 下确实少了本地可用 cores（§8.1）。

## 实验与结果

- **动机实验确认 concurrent marking 会制造 CPU 与 latency 峰值。** SPECjbb 中 marking 激活后应用 CPU share 53.3%→32.6%、throughput 下降 47%、average latency 增至 10.5×；减少 marker thread 并未改善 P99，8→4 threads 反而让 GC frequency 增 11%、P50 增 20%（图 1、表 2、§3）。
- **SPECjbb 主结果只在中等负载区成立。** 两 backend、相同总 cores 下，DGC-SHM critical-jOPS 比 Shenandoah/G1 高 24.0%/36.8%；DGC-RDMA 比 Shenandoah/G1 高 13.4%/25.0%，并比 SHM 低 8.6%。在 Shenandoah critical load 10,356 req/s，SHM/RDMA 的 P99 分别低 64.4%/60.3%。更高 rate 时 DGC 因每个 JVM 少 2 cores而比 baseline 更早 P99 divergence（图 4–5、§8.2）。
- **收益随 GC pressure 强烈变化。** HBase read/update peak 下，SHM 的 read/update P99 比较好的基线 G1 低 58.3%/40.3%，RDMA 低 53.8%/29.1%；read/insert 中相对 Shenandoah 则分别低 81.8%/55.7% 和 41.4%/28.5%。DaCapo 只有 h2、tradesoap、tradebeans、lusearch、kafka 这 5/9 明显优于 Shenandoah；tomcat、spring、jme、cassandra 的 GC pressure 太低而无明显差距，G1 还在 tradesoap、spring、cassandra 上有优势（图 6、§8.2）。
- **异构共享 workload 支持 orchestration 的价值。** 两 SPECjbb 加两 HBase 在 100% mix load 下，SHM 将 SPECjbb P99 142→46 ms，YCSB read 4.64→1.51 ms，update 11.1→2.80 ms，相对 Shenandoah 低 67.6%/67.5%/74.8%；RDMA 分别低 51.5%/58.5%/75.9%。四 DaCapo mix 中 lusearch 的 Shenandoah P99 在 60% load 崩到 64 s，而 SHM 为 708 µs，这个极端倍数来自 baseline 进入 degenerated GC（图 7、§8.3）。
- **远端资源成本与规模上限不可忽略。** 两个 4 GB heaps 共用 2 GB cache 的 `1/2` 配置增加 25% remote memory；每 cycle 平均 RDMA traffic 为 5.52 GB，相对 4 GB heap 放大 37%，P99 仍明显低于 Shenandoah。6 backends 时 RDMA/SHM 对 Shenandoah 的 P99 改善约 43.3%/50.9%；RDMA 测到 12 backends 后收益开始缩小，日志显示 200 Gbps NIC 成为瓶颈（图 8–9、§8.4–§8.5）。
- **全局 scheduling 比 transfer overlap 更关键。** SPECjbb fixed 10,356 req/s 下，完整 DGC-RDMA P99 为 81.5 ms；禁用 copy/mark overlap 后为 87.0 ms，只差 6.7%。去掉 coordinator 后 P99 变成 13,800±7,132 ms，并因 deadline 失准进入 degenerated GC。这个消融说明 selected 200 Gbps setting 下 pipeline 收益较小，而跨 JVM 调度决定系统能否稳定运行（表 3、§8.6）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 把 marking 移出 JVM 可降低 concurrent GC 对 mutator 的 tail interference | 图 4–6：SPECjbb P99 低 60.3%–64.4%，HBase 与 5/9 DaCapo 有收益 | 相同总 cores、2× minimum heap；中等负载 | 强 |
| 多 runtime 共享 marker pool 需要全局协调 | 图 7、表 3：混合 workload 改善；noCOOR P99 81.5 ms→13.8 s | 最多 4 个异构 runtimes 的 mix；CP-SAT 依赖预测 | 强 |
| RDMA partial-heap marking 能接近同机 SHM | SPECjbb critical-jOPS 仅比 SHM 低 8.6%，P99 reduction 60.3% 对 64.4% | 200 Gbps BlueField-3、两台 server、充足 cache | 中强 |
| DGC 普遍优于成熟本地 GC | 4/9 DaCapo 对 Shenandoah 无明显收益，G1 在 3 项更好；极高 load DGC 更早发散 | 收益要求 GC pressure 是主要 tail 来源 | 弱 |
| 架构可扩到数据中心级共享服务 | RDMA 只到 12 backends 且 NIC 已成为瓶颈 | 没有 rack-scale、拥塞或共享故障实验 | 弱 |

## 批判性分析

### 论证链条

论文先测到“concurrent 不等于无干扰”，再排除多配 core/memory 和减少 threads，接着用 SHM 版本隔离 CPU 原因，用 RDMA 版本证明跨机可行，最后用 mixed workload 和 noCOOR 消融证明共享 pool 需要 orchestration。这条 observation→design→evidence 链很完整；相同总 CPU budget 也避免了“只是多给 GC cores”的简单混淆。

最值得保留的负面结论是收益区间。DGC 面向 GC pressure 足以影响 tail、但应用尚未占满 8 cores 的中等负载。低 GC pressure 时没有峰值可削；极高 load 时 baseline JVM 的额外 `c` cores 反而有用。标题中的“managed workloads”不能外推为所有 JVM workload。

### 假设压力测试

Scheduler 把 `free memory / allocation rate` 当 deadline，并用历史 live set 拟合 duration。Traffic surge、phase change、promotion failure 或 object survival 突变会同时改变两项估计。10 ms 重算和 headroom 只能吸收有限 drift；大量 JVM 同时达到临界点时，回退 local GC 会让本机 CPU 和 shared marker 同时变热。

Region locality 也不是普遍成立。Pointer-rich graph 跨很多 regions、cache 远小于 live set 或大对象 region 中只有少量 reachable data 时，2 MB fetch 会浪费 bandwidth。12 clients 已把单 NIC 推成 bottleneck；在共享 storage/RDMA fabric 上，网络 tail 和 incast 会直接进入 GC deadline。

SATB 论证假设 barrier 完整记录所有 overwritten edges，class metadata 在周期前同步，bitmap 回写与最终 STW 正确串联。JVM bug、RDMA stale write、cache state race 或 coordinator version error 都可能变成内存安全问题，而不只是性能退化。

### 实验可信度

SPECjbb、HBase/YCSB 和 9 个 request-oriented DaCapo workload 覆盖 web、database、search 与 messaging；G1 和 Shenandoah 是强 baseline。作者报告 4/9 无收益、G1 的胜点、极高 load 发散、remote memory/traffic、12-backend NIC 瓶颈，证据边界比只报最大提升更可信。

但系统只有两台 server。所谓 scalability 主要是增加 JVM backends，不是增加 marker servers、NICs 和 fault domains。P99 是主指标，没有 P99.9/P99.99；三次重复的 min/max band 对稀有 GC/failure tail 仍有限。Heap 固定为 2× minimum 是合理控制变量，却未覆盖生产中更大 heap、generational tuning 和不同 allocation phase。

noOPT 只比完整版慢 6.7%，说明在 200 Gbps 和该 cache 下 transfer–mark overlap 不是主收益；论文对这一 co-design 的篇幅与实际 end-to-end贡献不完全匹配。noCOOR 很强，但只在固定 SPECjbb setting 验证，无法单独区分预测失真、thread allocation和 trigger staggering 各自作用。

### 系统性缺陷

DGC 把每个 JVM 内部的维护功能变成 stateful shared service。Marker 可读完整 heap 和 class layout，一次服务漏洞或错误可能影响多个租户。论文要求 operator-managed trust boundary，并引用 cgroup/[[NUMA|NUMA]]/namespace 做隔离，但这些机制不能阻止 DGC 自身读取或误写别的 runtime state；没有加密、capability 或 memory-safety隔离方案。

故障回退只保正确性底线。In-flight service failure 可能触发约 100 ms degenerated STW，随后多个 JVM 同时回本地 Shenandoah；论文没有 fault injection、MTTR、重复 bitmap、network partition 或 coordinator failover 测试。共享服务由此引入 correlated latency spike。

DGC 也没有 memory-bandwidth、PCIe 或 NIC QoS。一个高 allocation tenant 可消耗 heap cache与 RDMA，影响其他 runtime；CP-SAT 的 core constraint没有把 bandwidth、remote memory、fairness 和 energy 纳入目标。2 GB cache与每轮5.52 GB traffic的完整 TCO 也未与直接多配 CPU 比较。

## 局限与后续工作

- 在数十至数百 JVM、多 marker servers 和共享 RDMA fabric 上测 P99.9、deadline miss、fairness 与 GC storm。
- 注入 marker/coordinator crash、packet loss、partition、stale trigger 和 bitmap writeback failure，验证回退正确性与 correlated tail。
- 把 NIC bandwidth、PCIe、memory bandwidth、heap cache 和 tenant fairness加入 scheduler constraint，并报告 admission rejection。
- 改变 heap 从 1.2× 到 8× minimum、allocation phase 和 live-set locality，画出 DGC 相对 G1/Shenandoah 的适用区间。
- 给出 cores、remote DRAM、NIC traffic、energy 与云成本的 TCO，对比简单 overprovisioning。
- 验证 G1/Generational Shenandoah/ZGC 等移植，不只依赖“SATB 可泛化”的架构论证。
- 用 memory-safe marker 或硬件 capability 隔离各 runtime heap，限制共享服务的 blast radius。

## 相关

- **相关概念**：[[Garbage-Collection]]、[[Disaggregation]]、[[RDMA]]、[[CXL]]、tail latency、resource pooling
- **同类系统**：Shenandoah、G1、ZGC、Semeru、Mako
- **同会议**：[[OSDI-2026]]
