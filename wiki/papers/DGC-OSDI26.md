---
type: paper
name: DGC
full_title: "Shaving the Peaks: Taming Tail Latency for Managed Workloads via Disaggregated Garbage Collection"
authors: [Hongtao Lyu, Yuhan Li, Mingyu Wu]
venue: OSDI
year: 2026
tags: [garbage-collection, disaggregation, rdma, tail-latency]
source_pdf: "[[osdi26-lyu.pdf]]"
source_md: "[[osdi26-lyu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# DGC：以解耦式垃圾回收削平托管工作负载尾延迟（OSDI 2026）

> **原题**：Shaving the Peaks: Taming Tail Latency for Managed Workloads via Disaggregated Garbage Collection

DGC 将 concurrent GC 最昂贵的 marking 阶段变成跨 JVM 共享服务，以 RDMA 软件分页远程遍历 heap，并通过全局编排错开多个 runtime 的周期性 GC 峰值。

## 问题与动机

concurrent collector 减少 stop-the-world pause，却在 CPU-limited container 内让 marker 与 mutator 竞争。GC 是周期性 burst：为峰值永久预留 core 会浪费，少配 core 又使请求 p99 在 marking 期间陡增。DGC 试图把 GC 算力池化，让应用 core 保持稳定并跨 runtime 复用峰值容量。

## 关键观察 / 隐含假设

### 关键观察

- Shenandoah 的 marking 可用 SATB snapshot 与 mutator 解耦，远端 marker 不必与每次对象更新同步。
- JVM region 可充当粗粒度软件 page，降低远程对象图遍历的 address translation 和 RDMA request 开销。
- 多 JVM 的 GC 触发点可预测且通常不完全重合；全局 orchestrator 能错开 burst，避免远端服务重新产生 contention。

### 隐含假设

- RDMA 网络可靠、低延迟且有足够带宽，远端 GC 节点在故障与拥塞时不会成为更严重的尾部来源。
- heap 大小约为 workload 最小需求的 2 倍，SATB 与远端页面缓存的额外内存可接受。
- marking 是主要干扰源；evacuation、barrier 和 degenerated GC 仍留在本地，其成本不会主导所有 workload。

## 核心方法

### 解耦式标记引擎（Disaggregated marking engine）

OpenJDK Shenandoah 将 roots、SATB 信息和 heap region 暴露给独立 DGC service。远端 marker 在不完整对象图上推进，缺失 region 异步 RDMA fetch，使 graph traversal 与数据传输重叠。

### 热度驱动的软件分页

系统以 region 为页，依据 pending references 和访问热度预取/保留远端副本，减少细粒度随机 RDMA。bitmap 与 work-stealing queue 保持对象只被标记一次。

### 全局 GC 编排器

每个 runtime 的 allocation monitor 预测下一次 marking deadline；orchestrator 用 CP-SAT 分配共享 marker cores并错开任务。当需求超过 headroom 或计划失效时，JVM回退本地 Shenandoah，避免 OOM。

## 设计取舍

- DGC 将本地 CPU interference 换成网络、远端内存和共享服务依赖。
- 保留 evacuation 在 JVM 内缩小远程协议范围，但 tail latency 仍可能受 compaction/load barrier 影响。
- 全局优化提高利用率，却需要监控每个 runtime allocation rate，并处理预测误差。
- 公平比较保持总 core budget 相同；DGC JVM 本身比基线少 marker cores，因此极高 load 下 mutator 更早饱和。

## 实验与结果

- SPECjbb2015 在相同总 CPU budget 下，DGC-SHM 相比 Shenandoah critical-jOPS 提高 24.0%，相比 G1 提高 36.8%；RDMA 版本相比 Shenandoah提高 13.4%（§8.2，图 4）。
- 在 Shenandoah 的 10,356 req/s critical load 下，DGC-SHM 与 DGC-RDMA 分别将 SPECjbb P99 latency 降低 64.4% 和 60.3%。
- HBase YCSB peak throughput 下，DGC-SHM 相比 G1 将 read/update P99 分别降低 58.3%/40.3%，RDMA 版本降低 53.8%/29.1%。
- 多 workload 100% load 下，DGC-SHM 将 SPECjbb P99 从 142 ms 降至 46 ms，将 YCSB read 从 4.64 ms 降至 1.51 ms、update 从 11.1 ms 降至 2.80 ms；降幅分别为 67.6%、67.5%、74.8%。
- 远端节点需约 25% 额外 memory，单次 GC RDMA traffic 约 5.52 GB、相当于 37% heap；这是尾延迟收益对应的资源成本。
- 扩展到 6 backends 时，DGC 相比 Shenandoah 的 P99 改善最高 43.3%–50.9%；更大规模受实验机器 core 数限制，尚未证明 rack-scale 扩展。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| 远程 marking 能消除 GC-mutator CPU 峰值竞争 | SATB 与 RDMA region paging | SPECjbb P99 降低 60.3%，critical-jOPS 提高 13.4% | 需要 RDMA 和额外远端内存 |
| GC 服务可跨 runtime 共享 | allocation 预测与 CP-SAT 编排 | 6 backends P99 改善最高 50.9% | 小规模实验，预测错误会回退本地 GC |
| 远端执行可接近本地 offload | traversal 与 page fetch 重叠 | RDMA P99 收益接近 SHM 的 64.4% | 每周期产生 5.52 GB 流量 |
| 收益来自平滑 burst 而非增加总 CPU | 两侧保持相同总 core budget | 多 workload throughput/latency 同时改善 | 极高 load 下 DGC JVM 更早饱和 |

## 批判性分析

### 论证链条

论文用 GC active/inactive 时的 CPU 与 latency spike 建立因果动机，再逐步验证 SHM offload、RDMA data plane 和 multi-runtime orchestrator。等总 core budget 的比较很关键，说明结果不是简单多给资源。

### 假设压力测试

网络拥塞、DGC 节点故障或多个 JVM 同步爆发会把本地偶发 stall 变成共享 blast radius。低 allocation、短 heap workload 中远程协议成本可能超过收益；G1 在部分 DaCapo 上优于 DGC，也说明 concurrent marking 并非普遍最佳。

### 实验可信度

SPECjbb、HBase/YCSB 和九个 DaCapo latency workload 覆盖较好，结果披露失败区间、memory 与 network cost。缺少 p999、DGC service failure、真实多租户网络干扰和超过 6 backends 的规模验证。

### 系统性缺陷

DGC 使 language runtime 依赖外部 stateful service；heap 数据跨机器传输还引入安全、带宽计费与数据驻留问题。25% 远端内存和 37% heap/GC 的流量可能抵消云端 CPU pooling 的成本优势，论文未给出完整 TCO。

## 局限与后续工作

- 在网络拥塞、丢包、远端节点故障下验证回退正确性与 p999 latency。
- 扩展到数十/数百 JVM，评估 orchestrator 复杂度、公平性和同步 GC storm。
- 给出 CPU、DRAM、RDMA NIC 与网络流量的完整 TCO/能耗比较。
- 移植到 ZGC、V8、Go 等 runtime，并解决跨租户 heap 隔离与加密。

## 相关

- [[Garbage-Collection]]
- [[Shenandoah]]
- [[RDMA]]
- [[Resource-Disaggregation]]
