---
type: paper
name: Kamino
full_title: "Kamino: Efficient VM Allocation at Scale with Latency-Driven Cache-Aware Scheduling"
authors: [David Domingo, Hugo Barbalho, Marco Molinaro, Kuan Liu, Abhisek Pan, et al.]
venue: OSDI
year: 2025
tags: [vm-allocation, cache-aware-scheduling, cloud, azure, tail-latency]
source_pdf: "[[osdi25-domingo.pdf]]"
source_md: "[[osdi25-domingo]]"
---

# Kamino: Efficient VM Allocation at Scale with Latency-Driven Cache-Aware Scheduling (OSDI 2025)

> **一句话总结**：Kamino 把 VM 分配请求按"预估端到端延迟"（队列时间 + 缓存感知的处理时间）派发到多个 allocator agent，Azure 生产部署使平均分配延迟降低 42%、缓存 miss 率降低 33%、内存占用降低 17%。

## 问题

Azure 等大云的 VM 分配器（Protean）用多 agent（AA）并行处理请求，每个 AA 自带分层私有缓存（上层缓存识别相同请求类型，下层缓存子规则结果）避免重新计算。但现有调度策略（round-robin、work-stealing、consistent hashing）与 cache 无感知，主要问题：

1. Cache hit/miss 延迟差异巨大且不规则——某些请求类型的 hit 反而比另一些的 miss 更慢（分层 cache 导致），hit/miss 延迟变化可达 5×
2. 单纯 cache-aware pinning 遇突发流量会打热点
3. 每 AA 的 cache 条目 10-100 MB，节点内 AA 数受限于内存，盲目增加 AA 数会让每个 cache 变小、miss 率升高

## 核心方法

Kamino 把 VM 分配当作带缓存的在线作业调度问题，核心是 **LatCache** 算法：新请求到来时，为每个 AA 估计它的端到端延迟 = `remainingProcTime + queueTime + processingTime`，把请求派给估计延迟最低的 AA。

三个延迟分量都要"cache-aware"估计：

- `processingTime`：不是看当前缓存，而是看该请求**开始处理时**缓存的预期状态（取决于队列中前序请求、LRU/等缓存淘汰策略）
- `queueTime`：对队列中每个请求依次估计其处理时间加总
- `remainingProcTime`：当前正在执行请求的剩余时间

关键新颖点：cache state（尤其 hit rate）只是延迟的一个组成部分，而非优化目标本身；Kamino 把 cache、queue 两种状态统一到端到端 latency 这个真正的指标上。系统实现把 request classification、queue assignment 等阶段 pipelined 起来，保持高吞吐；VM-assignment 内部逻辑和 LatCache 严格分离，便于各自演化。作者也在 LSM-tree（LevelDB）上做了可迁移性验证。

## 关键结果

- 高保真仿真（Azure 多 region trace）：相比 latency-agnostic 基线平均延迟降低 **42%**，突发负载下吞吐最高 2×
- Azure 生产部署（所有 production zones，节点含数十万机器）：p90 分配延迟降低 11.9%，cache miss 降低 **33%**，单 AA 内存占用降低 **17%**
- LSM-tree prototype 上套用同思路，平均查找延迟降低 22%，证明该方法可泛化到有层级数据 tier、请求延迟可变的系统（分布式数据库、CDN、微服务）

## 相关

- **相关概念**：[[Cache-Aware-Scheduling]]、[[Load-Balancing]]、[[Tail-Latency]]、[[Consistent-Hashing]]
- **相关系统**：Protean（Azure 生产 VM allocator，baseline）、Omega、Kubernetes、Twine、Kerveros
- **同会议**：[[OSDI-2025]]
