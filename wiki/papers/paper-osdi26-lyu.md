---
type: paper
name: DGC
full_title: Shaving the Peaks: Taming Tail Latency for Managed Workloads via Disaggregated Garbage Collection
authors: [Hongtao Lyu, Yuhan Li, Mingyu Wu]
venue: OSDI
year: 2026
tags: [garbage-collection, managed-runtime, tail-latency, disaggregation, rdma]
source_pdf: "[[osdi26-lyu.pdf]]"
source_md: "[[osdi26-lyu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-24
---

# 用分离式垃圾回收削平托管工作负载的延迟峰值（OSDI 2026）

> **原题**：Shaving the Peaks: Taming Tail Latency for Managed Workloads via Disaggregated Garbage Collection

> **一句话总结**：论文观察到并发 GC 在资源受限的多租户 JVM 中会把应用 CPU 份额从 53.3% 压到 32.6%，使平均延迟升高 10.5 倍；DGC 将标记阶段卸载到共享的本地或 RDMA 远端资源池，并协调多个运行时的 GC 窗口，在 SPECjbb2015 上比 Shenandoah 提高 24.0% critical-jOPS、最多降低 64.4% 的 P99 延迟。

## 问题与动机

并发 GC 减少了 stop-the-world（STW）暂停，但标记线程仍与应用线程共享 CPU。在每个 JVM 只有少量 CPU、内存配额也受限的云环境中，GC 以周期性突发形式出现：非 GC 时 CPU 低利用率，标记时应用线程又被挤压。作者在 8 核、4 GB 的 SPECjbb2015 配置中观察到，Shenandoah 标记期间总 CPU 利用率升至 98.2%，应用吞吐下降 47%，平均延迟升高 10.5 倍（§3，图1）。

增加 CPU 或固定 GC 核数能消除竞争，却把峰值所需的核长期闲置；减少 GC 线程又会延长 SATB 周期、增加 floating garbage 和 GC 频率。论文因此把 GC 的突发计算需求视为适合资源池化的工作负载，而不是继续在单个 JVM 内调参。

## 关键观察 / 隐含假设

- **观察 1：并发标记造成周期性的 CPU 供给抖动。** Shenandoah 非 GC 时有 45.7% CPU 空闲，标记时应用 CPU 份额由 53.3% 降至 32.6%（§3，图1）。
  - **依赖假设**：托管实例足够小且 GC 窗口彼此错开，集群中存在可汇聚的空闲 CPU。
  - **可能失效场景**：所有租户同步分配或 GC，或者应用本身持续满载，资源池无法提供弹性容量。
- **观察 2：标记的访问模式允许用高带宽网络换取本地 CPU。** 测试中的标记扫描速度约为 2.6 GB/s，而 400 Gbps 级 RDMA 在带宽上有余量（§3）。
  - **依赖假设**：RDMA 延迟、NIC 和 PCIe 带宽不会超过标记计算收益；区域级局部性足以降低远程访问次数。
  - **可能失效场景**：缓存很小、对象图跨区域引用密集，或多个运行时共享单个 NIC 导致带宽竞争。
- **假设 1：平台组织拥有 JVM、GC 服务和部署环境。** DGC 需要读取堆、类元数据和 SATB 记录，因此假定它们位于同一运营方信任边界内（§4.2）。证据强度：强，部署模型明确排除了任意租户间服务。

## 核心方法

DGC 把并发 GC 的标记阶段从 served runtime 中抽出，形成共享标记服务。共置运行时使用共享内存（SHM）；跨主机运行时使用 RDMA 读取堆的副本。清扫、压缩和应用执行仍留在原 JVM 中，因而卸载边界主要针对 CPU 密集的标记阶段（§4，图2）。

远程标记采用 Snapshot-at-the-Beginning（SATB）：运行时在短 STW 阶段记录根和快照，应用恢复后由写屏障记录被覆盖的旧引用。标记器即使看到不同时间点拼接出的远程堆，也能把堆遍历结果与 SATB 缓冲区合并，覆盖快照中的存活边。最终再用短 STW 阶段处理尚未同步的记录（§5.1，图3）。

RDMA 数据面使用与 JVM GC 区域一致的用户态软件分页，而不是操作系统远程分页。区域状态表和读锁保护缓存替换；未缓存区域的引用进入按区域组织的 pending queue，区域到达后再交给单一标记线程，避免位图竞争。标记线程和 RDMA 控制线程可重叠工作，热点评分和预取窗口减少重复搬运（§5.2–§5.4）。

多个 JVM 共享一个标记池。每个运行时监控空闲堆、分配速率、存活对象量和历史标记时长；中心协调器每 10 ms 用 CP-SAT 选择 GC 启动时间与线程数，使任务在 OOM 截止时间前完成，同时不超过 GC 核数。服务不可达或预测失准时，运行时退回本地 Shenandoah，避免把调度错误直接变成 OOM（§6.2–§6.4）。

## 设计取舍

- **远程副本换本地 CPU**：DGC-RDMA 不影响应用读写，但需要额外缓存和 RDMA 流量；缓存越小，搬运和替换压力越大。
- **标记卸载而非整套 GC 卸载**：保留本地压缩和屏障逻辑，降低正确性改造范围，但压缩阶段仍会造成残余尾延迟（§8.2，图5）。
- **延迟启动 GC 换取更少 floating garbage**：依赖分配速率和标记时长预测；预测过时会触发保守回退。CP-SAT 适应异构负载，但引入了外部求解器依赖。
- ** moderate load 优化换取极高负载下更早恶化**：DGC 每个 served JVM 只有 8 个应用核，基线还拥有额外的 GC 核；因此极高负载时 DGC 曲线较早发散（§8.2）。

## 实验与结果

- 在双路 Xeon Gold 6430、每机 64 个物理核、200 Gbps BlueField-3 RDMA 环境中，SPECjbb2015 两实例下 DGC-SHM 的 critical-jOPS 比 Shenandoah 高 24.0%，DGC-RDMA 高 13.4%；在 Shenandoah 的 10,356 req/s 点，P99 分别降低 64.4% 和 60.3%（§8.1–§8.2，图4）。
- HBase YCSB Read+Update 在峰值吞吐下，DGC-SHM 相对较优基线把 read/update P99 降低 58.3%/40.3%；Read+Insert 相对 Shenandoah 降低 81.8%/55.7%（§8.2，图6）。
- DaCapo 中 h2、tradesoap、tradebeans、lusearch、kafka 显示明显收益；lusearch 在 Shenandoah 下出现多秒级 P99，而 DGC-SHM 可扩展到约 20k req/s 并保持低毫秒延迟。低 GC 压力的 spring、tomcat、jme、cassandra 没有明显收益，部分场景 G1 更好（§8.2，图6）。
- 异构 SPECjbb+HBase 混部时，DGC-SHM 将 SPECjbb P99 从 142 ms 降至 46 ms，并将 YCSB read/update P99 降至 1.51/2.80 ms（§8.3，图7）。
- RDMA 缓存限制到半堆时，只需相对两个 4 GB 堆增加 2 GB 远端缓存，平均每轮流量 5.52 GB；限制到四分之一缓存仍比 Shenandoah 降低 51.5% P99（§8.4，图8）。12 个 backend 时 CP-SAT 求解约 11.1 ms，但 RDMA NIC 成为瓶颈（§8.5，图9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 并发 GC 的 CPU 竞争是尾延迟峰值来源 | §3，图1；应用吞吐下降 47%、平均延迟升高 10.5 倍 | SPECjbb2015、8 核、4 GB、Shenandoah | 强 |
| 分离标记可在同等总 CPU 预算下提升吞吐 | §8.2，图4；critical-jOPS +24.0% | 两实例、Xeon Gold 6430、DGC-SHM | 强 |
| RDMA 远程标记保留大部分收益 | §8.2、§8.4，图4/8；P99 -60.3%，四分之一缓存仍 -51.5% | 200 Gbps RDMA、特定 JVM 堆和区域配置 | 中 |
| 全局协调对混部稳定性不可或缺 | §8.3、§8.6，图7/表3；无协调时触发 degenerated GC | 2–12 个运行时，CP-SAT 调度 | 强 |

## 批判性分析

### 论证链条

从 CPU 利用率周期性峰值到标记卸载，论证链条在中等负载下是闭合的：DGC 保持应用核稳定，把突发标记放到专用池，再用全局调度错开窗口。论文没有证明所有托管运行时都以标记为主瓶颈；低 GC 压力的四个 DaCapo 工作负载没有收益，说明收益条件是分配压力与并发标记竞争同时存在。

### 假设压力测试

实验最多扩展到 12 个 backend，且 RDMA 在该点已受 NIC 限制。生产环境中若对象图的跨区域引用比例更高，区域缓存的局部性和热点评分可能失效。DGC 的 SATB 正确性依赖写屏障记录完整；论文讨论了协议语义，但没有给出异常、丢包或服务重启期间的长时间恢复开销。

### 实验可信度

基线与 DGC 使用相同总物理核预算，且覆盖 SPECjbb、HBase 和九个 DaCapo 工作负载，消融也显示全局调度会影响可持续性。限制在于主要硬件是双路 Intel 服务器，DGC-RDMA 的主要结果假定远端内存充足；不同 NIC、NUMA 拓扑、JVM 版本和生成式 Shenandoah 配置尚未验证。

### 系统性缺陷

标记器需要访问堆内容、类信息和运行时元数据，部署因此必须由同一平台组织管理。论文未量化多租户间内存带宽、PCIe 和 NIC 队列的隔离成本；作者也承认持续 fan-in 时存在共享 PCIe 带宽干扰。服务失效时在一次 SPECjbb 测试中可能出现约 100 ms 的 degenerated GC 暂停，虽然后续周期会退回本地 Shenandoah（§6.4）。

## 局限与后续工作

- **局限 1**：DGC-RDMA 的可扩展性受单 NIC 带宽约束；12 个 backend 时收益已开始下降（§8.5）。
- **局限 2**：低分配压力工作负载中，SATB 写屏障和并发 bookkeeping 的固定成本可能使 G1 更有优势（§8.2）。
- **后续工作 1**：测量不同区域大小、跨区域引用率和缓存容量对 RDMA 流量及 P99 的影响，并确定热点分页策略的失效阈值。
- **后续工作 2**：用无求解器启发式替代 CP-SAT，比较在异构分配速率变化下的求解时间、OOM 安全裕量和尾延迟。
- **后续工作 3**：引入 MBA 或按 queue pair 限速，验证共享 PCIe/NIC 带宽下的租户隔离。

## 相关

- **相关概念**：[[Garbage-Collection]]、[[RDMA]]、[[SATB]]、[[Resource-Disaggregation]]
- **同类系统**：[[Shenandoah]]、[[ZGC]]、[[Jade]]、[[Semeru]]、[[Mako]]
- **同会议**：[[OSDI-2026]]
