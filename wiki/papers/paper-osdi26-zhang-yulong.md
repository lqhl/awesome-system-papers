---
type: paper
name: Blowfish
full_title: "Elastic Virtual Machine Memory for Disaggregated Memory"
authors: [Yulong Zhang, Yilong Luo, Diyu Zhou, Quan Chen, Quanxi Li, et al.]
venue: OSDI
year: 2026
tags: [memory-overcommitment, disaggregated-memory, virtual-machines, thp, mglru]
source_pdf: "[[osdi26-zhang-yulong.pdf]]"
source_md: "[[osdi26-zhang-yulong]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-14
---

# 面向解聚内存的弹性虚拟机内存（OSDI 2026）

> **原题**：Elastic Virtual Machine Memory for Disaggregated Memory

> **一句话总结**：Blowfish 观察到数据中心 VM 中约 33–49% 的内存可在性能下降不超过 5% 时回收，但传统方案受 THP 混合粒度和 GPT/IOPT 页表开销限制；它把热度跟踪留在 guest、把数据搬运和 EPT 重映射放在 host，并用子页跟踪处理 THP，最终将单页回收与恢复延迟降至 14.5µs 和 9.8µs。

## 问题与动机

VM 内存超售通常只回收空闲页。冷页占据了大量内存，却难以安全地回收：guest-level swapping 要修改 GPT、EPT 和 IOPT，host-level swapping 又看不到 guest 的访问语义。磁盘换入换出达到毫秒级，容易违反延迟 SLO；解聚内存通过 InfiniBand、RoCE 或 CXL 把数据搬到远端内存，使微秒级冷页回收成为可能。

论文在七个真实工作负载上测得，在关闭 THP、性能下降约束为 5% 时，可回收 33–49% 的应用内存（§3.1）。开启 THP 后，可回收比例降至 16–25%，原因包括 huge page 放大热度，以及 2MB 与 4KB 页混合时的不公平热度排序（§3.2.1）。

## 关键观察 / 隐含假设

- **观察 1：冷内存的分布通常不连续。** 约 43% 的可回收内存以 4KB 粒度存在，HyperAlloc 的 2MB 回收因此覆盖不足（§3.2.2）。
  - **依赖假设**：远端内存的访问延迟足够低，且工作负载能容忍受 PSI 控制的少量缺页。
  - **可能失效场景**：远端内存拥塞、网络故障或工作集快速变化时，恢复延迟可能直接进入请求关键路径。
- **观察 2：host 无法低成本获得 guest 的访问热度。** host-level swapping 比 guest-level swapping 多产生约 5.0× TLB flush；其 26% 的恢复由 guest 内核服务访问触发（§3.2.3）。
  - **依赖假设**：guest 能通过约定协议报告冷页和分配器状态。
- **观察 3：THP 使单页访问概率与页大小相关。** 2MB 页包含 512 个 4KB 子页，标准 MGLRU 会过度奖励 huge page 的一次访问。
  - **可能失效场景**：只有两代 LRU 的系统无法充分体现增量晋升；论文只在 Linux 6.1/MGLRU 环境中验证。

## 核心方法

Blowfish 是 guest/host 协同的 VM 内存超售框架。guest 复用 Linux MGLRU 进行热度排序，host 负责物理页回收、远端内存传输和 EPT 映射。冷页地址通过共享内存通道传给 host，回收时只失效 EPT；访问已回收页时由 EPT violation handler 从远端内存恢复。这样 GPT 和 IOPT 无需参与冷页路径。

论文加入 Fair MGLRU：4KB 页保持一次访问即晋升到最年轻代；2MB 页每次访问只晋升一代。它降低 huge page 因包含更多子页而获得的热度偏置，同时保留真正高频访问 huge page 的晋升机会（§4.3.1）。

Subpage Tracker 每 100ms 从次年轻代选取最多 32 个 huge page，临时把 PMD 映射拆成 PTE 映射，在 100ms 窗口观察子页访问位。少于 20% 子页被访问时，将其冷子页报告给 host；随后重新合并映射，避免长期增加细粒度页表项（§4.3.2）。

Blowfish 还修改 khugepaged 和 kcompactd，使其跳过冷页或已回收页，减少 guest 内核服务造成的无效恢复。自动策略优先回收空闲页，低于 100MB 水位后再按 PSI 阈值回收冷页（§4.5–§4.6）。

## 设计取舍

- **低延迟换取 guest 改造成本**：约 1700 行 guest kernel 和 6000 行 host kernel/QEMU 改动换来更短的回收路径；部署者必须维护 guest-host 协议。
- **映射拆分而非物理页拆分**：降低 `struct page` 和迁移开销，但需要周期性修改 guest 页表，并依赖访问位的可靠性。
- **PSI 控制而非固定回收率**：适应不同工作负载，但控制策略是启发式的，不能保证所有突发访问模式下的尾延迟。

## 实验与结果

- 在 5% 性能下降约束下，Blowfish 相比 HyperAlloc-4K-G、HyperAlloc-H、HyperAlloc-G 的平均回收比例提升：Memcached 为 3.1×、5.3×、3.2×；Cassandra 为 2.1×、4.0×、3.3×（§5.1.1）。
- GraphChi PageRank 上，Blowfish 相比三类基线提升 3.4×、6.1×、3.9×；KMeans 上提升 3.0×、5.6×、3.7×（§5.1.1）。
- Memcached/Cassandra 的 p95 延迟下降幅度相对 HyperAlloc-4K-G 分别为 2.8×/4.7×/3.9× 和 1.9×/2.5×/2.1×（§5.1.2）。
- Fair MGLRU 使 Memcached 和 KMeans 的回收比例分别提高 7.2% 和 6.5%；Subpage Tracker 对 Cassandra 和 TriangleCount 的性能开销为 3.1% 和 0.9%（§5.3）。
- 单页回收/恢复延迟为 14.5µs/9.8µs，比 HyperAlloc-4K-G 低 53%/60%；单线程后端约在 170K pages/s 达到处理瓶颈，4 线程容量约为单线程的 3.9×（§5.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Blowfish 能在受控性能损失下回收更多 VM 内存 | 七个工作负载的回收比例（§5.1、图 6） | 单个 CPU/内存服务器，100Gbps InfiniBand，Linux 6.1 | 强 |
| host-side EPT 路径降低冷页操作延迟 | 14.5µs/9.8µs 延迟分解（图 11） | 单页微基准，未覆盖网络拥塞 | 强 |
| THP 感知机制改善混合粒度回收 | Fair MGLRU 消融和 Subpage Tracker 消融（图 9） | 主要验证两个应用，参数由经验设定 | 中 |
| guest 语义能减少无效恢复 | HyperAlloc-H 中 26% 恢复由内核服务触发，且 Blowfish 加入过滤器（§3.2.3、§4.5） | 未单独量化每个内核服务的长期运维影响 | 中 |

## 批判性分析

### 论证链条

论文的链条较完整：冷页比例测量说明机会存在；页表、TLB 和语义缺失测量解释基线为何失败；Blowfish 分别把热度识别、物理回收和 guest 服务协调放到合适层次；消融实验验证 Fair MGLRU 与 Subpage Tracker 的作用。单页延迟和队列扩展实验也支撑了微秒级路径的实现可行性。

### 假设压力测试

系统依赖 guest 合作报告冷页。论文提供 host-level fallback 以维持正确性，但 fallback 会重新承担热度跟踪和误回收成本。实验使用单个内存服务器和 100Gbps InfiniBand，尚未证明多租户网络竞争、远端内存故障和更大 NUMA 拓扑下的行为。PSI 也可能滞后于突发请求，尤其是恢复流量超过后端约 170K pages/s 时。

### 实验可信度

基线均接入相同 Hermit 数据路径和 PSI 策略，且覆盖七个应用、吞吐、p95 延迟、共置 VM、消融和后端扩展性。局限是硬件规模较小，未报告远端内存故障恢复、跨 VM 隔离压力、网络拥塞下的尾延迟，以及更多 guest OS 版本的兼容性。

### 系统性缺陷

Blowfish 修改 guest kernel、host kernel 与 QEMU，升级和调试成本高于只改 host 的方案。EPT 中编码远端地址依赖硬件页表项未使用位和特定虚拟化实现。论文讨论了错误 guest physical address 和并发锁，但未给出崩溃恢复、远端数据持久性、网络分区或安全隔离的完整方案。Subpage Tracker 的 20%/80%、100ms 和 32 页参数也可能需要按工作负载重新调节。

## 局限与后续工作

- **局限 1**：Fair MGLRU 依赖多代 LRU；传统双链表 LRU 只能用额外访问次数近似，效果可能较弱（§6）。
- **局限 2**：实验环境未覆盖 CXL、RoCE、多内存节点和网络拥塞；这些因素可能改变回收与恢复的尾延迟。
- **后续工作 1**：在多 VM、多远端内存节点和故障注入环境中测量 PSI 控制器的稳定性，并验证 P99 延迟与隔离指标。
- **后续工作 2**：比较固定参数与在线自适应的子页采样策略，量化采样开销、误回收率和不同 THP 分布下的收益。

## 相关

- **相关概念**：[[Disaggregated-Memory]]、[[Transparent-Huge-Pages]]、[[MGLRU]]、[[EPT]]
- **同类系统**：[[HyperAlloc]]、[[Hermit]]、[[Demeter]]、[[Memtis]]、[[HugeScope]]
- **同会议**：[[OSDI-2026]]
