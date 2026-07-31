---
type: paper
name: ARCTIC
full_title: "Arctic: a practical lock-free adaptive radix tree"
authors: [Newton Ni, Nicolas Garza, Jenny Stinehour, Michael Goppert, Michal Friedman, Emmett Witchel]
venue: OSDI
year: 2026
tags: [concurrent-data-structure, adaptive-radix-tree, lock-free, memory-reclamation, database-index]
source_pdf: "[[osdi26-ni.pdf]]"
source_md: "[[osdi26-ni]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 实用的无锁自适应基数树（OSDI 2026）

> **原题**：Arctic: a practical lock-free adaptive radix tree

> **一句话总结**：ARCTIC以128-bit CAS原地更新node metadata，用freezing protocol协调结构变化，并以operation key近似保护reachable pointers；80 threads相对ART在YCSB提升1.3×–7.7×，接入RocksDB/Turso最高+40%/+12%。

## 问题与动机

hash map快但无range scan，skiplist/树有序却常依赖lock；已有lock-free trie/SMART的indirection、copy-on-write和safe memory reclamation成本高。ARCTIC目标同时满足high performance、lock freedom和range/prefix scans，尤其在oversubscription时不因持锁thread暂停阻塞全体。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

node将version/state/pointer等放进可由128-bit CAS原子更新的metadata，不增加ART之外的pointer indirection。structural modification先freeze相关node，使竞争operation帮助完成或重试，保证global progress，再原地改变node形态。

Hazard keys不在每次pointer dereference发布hazard pointer；operation开始只announce logical key，reclaimer据tree prefix推断该key可能reach的retired nodes。读与range/prefix scan wait-free，但scan明确非linearizable。硬件必须有高效128-bit CAS/load。

## 实验与结果

- 80 threads、七种key distributions下，相对lock-based ART：YCSB-C 1.3×，YCSB-A最高7.7×。
- oversubscription下lock-based baseline因holder deschedule下降，ARCTIC保持throughput，支持lock-free价值。
- RocksDB write-heavy throughput最高1.40×，Turso最高1.12×（表 3）。
- memory相对ART依key：integer 0.97×–1.5×，string 0.19×–0.61×；hazard keys的reclamation/throughput对distribution敏感。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 无锁ART可胜过lock-based索引 | YCSB/thread scaling | 目标x86机器 | 强 |
| hazard keys降低SMR hot-path成本 | §4.3/ablation | trie/key lookup | 强 |
| 可改善真实数据库 | RocksDB/Turso | write-heavy benchmarks | 强 |
| range scan语义满足一般数据库 | 仅non-linearizable | 需要snapshot语义时不满足 | 弱 |

## 批判性分析

### 论证链条

ARCTIC最重要的限制写得清楚：scan非linearizable，故不能替换所有ordered index；128-bit atomic也限制architecture portability。Hazard key利用trie中logical key与pointer reachability的特殊关系，很巧妙但非通用SMR。RocksDB/Turso收益小于microbenchmark，说明index未必是端到端主瓶颈。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 设计linearizable/snapshot range scan并量化代价。
- 验证ARM等无廉价128-bit atomic平台的fallback。
- 对skew、long key、scan/update并发和crash consistency做压力测试。

## 相关

- **相关概念**：[[Lock-Free]]、[[Adaptive-Radix-Tree]]、[[Safe-Memory-Reclamation]]、[[Hazard-Pointers]]
- **相关系统**：[[RocksDB]]、[[Turso]]、[[ART]]
- **同会议**：[[OSDI-2026]]
