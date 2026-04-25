---
type: paper
name: Para-ksm
full_title: "Para-ksm: Parallelized Memory Deduplication with Data Streaming Accelerator"
authors: [Houxiang Ji, Minho Kim, Seonmu Oh, Daehoon Kim, Nam Sung Kim]
venue: ATC
year: 2025
tags: [memory-deduplication, ksm, dsa, accelerator-offload, datacenter-tax]
source_pdf: "[[atc2025-ji.pdf]]"
source_md: "[[atc2025-ji]]"
---

# Para-ksm: Parallelized Memory Deduplication with Data Streaming Accelerator (ATC 2025)

> **一句话总结**：把 Linux ksm 的 memcmp/xxhash 卸载到 Intel DSA 并将串行算法重写为按候选页 batch 提交，使每 CPU cycle 去重量提升 31–50%、协同应用退化从 1.6–5.8× 降到 1.3–2.7×。

## 问题

ksm（Kernel Same-page Merging）是 Linux 内核的内存去重机制，Meta 等厂商用它降低 Instagram 进程的内存压力，但 ksm 自己消耗 14–65% 的 CPU 周期，并污染 cache，导致同机器协同应用退化 1.6–5.8×。其中 memcmp 和 xxhash 两个数据面函数占 ksm 38% 的 CPU 周期。

Intel 4 代以后的 Xeon 自带 Data Streaming Accelerator (DSA) 片上加速器，理论上可以零拷贝、不污染 cache 地完成 page comparison 和 CRC checksum。但直接把 ksm 的 memcmp/xxhash 替换成 DSA 调用（DSA-ksm）暴露两个问题：(1) 单次 DSA 调用比 CPU 慢 2.6–2.7×（PCIe round-trip 主导）；(2) 单次卸载没法用 DSA 的 batch 能力，因为 ksm 的 RB 树搜索本身是串行的（要看上一个比较结果才决定下一步走哪个 tree page）。

## 核心方法

**DSA-ksm（baseline）**：把 memcmp/xxhash 改成异步 DSA 调用，CPU 在等结果时让出去给其他进程。DSA 异步模式相对 CPU temporal load 节省 6.6×/6.0× CPU cycle、不污染 cache，但单页延迟变高，去重率下降。

**Para-ksm 的关键改造**：把 ksm 重写成可以一次比对一批候选页，使 DSA batch descriptor 真正派上用场。两个候选方案：

- **Para-ksmC**（候选页 batching，本工作选这个）：选 N=256 个连续候选页一起进入 RB 树搜索，搜索时同一层的所有候选页 vs 当前 tree page 打包成一个 batch descriptor 提交给 DSA；插入阶段先全部完成搜索再统一插入，用 RB 树的「rebalance 不改变 predecessor/successor」性质（P1）和「同 hash group 的 search_result 共享 successor」性质（P2）保证插入正确性。
- **Para-ksmT**（候选页固定、speculatively 比对多个 tree page）：因 speculative 浪费 DSA 资源被舍弃。

batch size 8 时 memcmp/xxhash 平均延迟降低 81%/83%；但 batch size > 16 后 BD 利用率从 90%+ 跌到 < 60%（comparison skewness：批内不同候选页所需比较次数差距大）。深度细节回 [[atc2025-ji]]。

## 关键结果

- 每 CPU cycle 去重量比原版 ksm 提升 31–50%
- 协同 Redis/Graph500 等应用的性能退化从 ksm 的 1.6–5.8× 降到 Para-ksm 的 1.3–2.7×（DSA-ksm 是 1.0–1.6× 但去重率掉）
- 异步 DSA memcmp/xxhash 相对 CPU temporal load 省 6.6×/6.0× CPU 周期且不污染 cache
- DSA 6µs xxhash latency vs SmartNIC RDMA 17µs（片上 PCIe 优于片外）

## 相关

- **相关概念**：[[Memory-Deduplication]]、[[DSA]]（Data Streaming Accelerator）、[[On-Chip-Accelerator]]、[[Datacenter-Tax]]
- **同会议**：[[ATC-2025]]
