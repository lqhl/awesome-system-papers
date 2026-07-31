---
type: paper
name: FORGE
full_title: "FORGE: Mitigating Synchronization Amplification for Memory-Disaggregated Caching Systems"
authors: [Zhijun Yang, Yu Hua, Ming Zhang, Menglei Chen, Yixiao Wang]
venue: OSDI
year: 2026
tags: [disaggregated-memory, caching, rdma]
source_pdf: "[[osdi26-yang-zhijun.pdf]]"
source_md: "[[osdi26-yang-zhijun]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 缓解内存解耦缓存系统的同步放大
> **原题**：FORGE: Mitigating Synchronization Amplification for Memory-Disaggregated Caching Systems

## 问题与动机

内存解耦缓存把 housekeeping metadata 更新变成远程原子操作，约 2000 ns 的 RDMA 同步比本地操作慢至少 20×；逐对象维护淘汰状态会形成同步放大。

## 关键观察 / 隐含假设

- 淘汰决策不需要每个对象的精确全局顺序。
- 相似热度对象可成组管理，以一次同步摊销多个对象。
- 假设 workload 热度有局部稳定性，NIC 上可部署少量加速逻辑。

## 核心方法

[[FORGE]] 将相似缓存对象分组，以 group-level synchronization 降低远程原子频率；用无争用、hotness-aware FIFO 选择冷组，并延迟到必要时才更新热度。RDMA NIC 片上逻辑加速关键元数据路径。

## 实验与结果

在 YCSB 与真实 workload 上，FORGE 相对现有解耦缓存最高提高吞吐 4.5×，P50/P99 latency 分别降低 4.0×/7.5×，hit ratio 平均提高 1.14×（§7，图 12）。边界是 RDMA memory-disaggregated cache。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 对象级 housekeeping 是主要放大源 | 远程同步延迟至少为本地的 20× | §2 | 强 |
| 分组近似兼顾性能和命中率 | 吞吐 4.5×、平均 hit ratio 1.14× | §7 | 强 |

## 批判性分析

### 论证链条
从远程同步成本出发，用分组降低频率，再用热度策略补偿精度损失，权衡明确。

### 假设压力测试
热点剧烈漂移、小对象组内异质性或 NIC 资源紧张时，分组近似可能退化。

### 实验可信度
同时报告吞吐、分位延迟和命中率，避免只优化一端；NIC 可移植性证据仍有限。

## 局限与后续工作

- 可研究自适应分组粒度、NIC 无关的软件 fallback，以及故障下元数据恢复与一致性。

## 相关

- [[OSDI-2026]]
- [[Disaggregated-Memory]]
- [[RDMA]]
