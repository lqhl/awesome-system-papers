---
type: entity
kind: tool
aliases: [Disk-ANN]
status: active
last_updated: 2026-08-14
tags: [vector-search, ann, ssd, indexing]
---

# DiskANN

> DiskANN 是面向 SSD 的图式近似最近邻搜索（approximate nearest-neighbor search，ANNS）系统族：它用可导航近邻图减少必须读取的向量数量，让十亿级索引不必全部常驻 DRAM。

## 是什么

DiskANN 把向量组织成 proximity graph。查询从入口节点开始，反复读取候选节点的邻居和向量，用 best-first/greedy search 逐步靠近 query。常用部署会把较小的导航或量化结构放在内存，把完整向量和图记录放在 SSD；搜索质量由图构建、beam 宽度、缓存和 I/O 路径共同决定。

它代表一个清晰的设计点：尽量少做 SSD 随机读，即使这些读取之间存在数据依赖。这个选择非常适合较小 top-k 和高 recall 的静态索引，却不保证能充分利用多块高速 SSD，也会让更新、删除和大 top-k 请求变得困难。

## 关键观察 / 隐含假设

- **串行依赖可能比总 I/O 数更重要。** [[Helmsman-OSDI26]] 的 RedNote 负载需要 top-k 10–3000；DiskANN 类图搜索每轮都等上一轮节点，难以把多盘 IOPS 一次用满。该结论针对大候选集，不能推翻 DiskANN 在小 top-k、高 recall 场景的优势。
- **增量更新不能只靠大批 merge。** [[OdinANN-FAST26]] 发现 DiskANN buffered insert 的 merge 会与前台查询争 SSD 并占大量内存；它用直接插入、out-of-place 合并和较弱的 per-record 一致性减少尖峰，代价是更多磁盘空间和少量额外 I/O。
- **搜索后段的 I/O 价值会递减。** [[Terminus-MLSys26]] 在 Starling 上按排名效用早停，说明磁盘图搜索不必总把固定 beam 跑到底；但 near-perfect recall 时仍需深搜。
- **图路径中的等待窗口可以隐藏远端取边。** [[FlowANN-OSDI26]] 观察到节点被发现到真正展开之间常隔多个 step，因此把部分 edge 放到 CPU 并异步获取。它不是 DiskANN 实现，但说明“图依赖完全串行”也不是绝对事实。
- **DiskANN 默认假设索引相对稳定。** 持续 insert/delete、embedding 升级和 query drift 会改变图质量与缓存热度；现有论文多在单机、静态或稳定速率下评估。

## 演进时间线

- **DiskANN 基础路线**：建立“内存导航 + SSD 图/向量”的十亿级 ANNS 方案，成为磁盘图搜索的重要基线。
- **2025–2026 硬件与容量扩展**：[[PIMANN-ATC25]] 选择聚类式 IVFPQ 而非图搜索，把距离计算放到 PIM；[[LEANN-MLSys26]] 则现场重算 embedding，说明索引容量还可从“少存向量”方向压缩。
- **2026 更新与早停**：[[OdinANN-FAST26]] 把直接更新和近似并发控制放进磁盘图；[[Terminus-MLSys26]] 按下游 rank utility 决定何时停止 I/O。
- **2026 大 top-k 反例**：[[Helmsman-OSDI26]] 用生产大候选集说明聚类扫描可以通过并行 I/O 胜过更省读取的串行图搜索。

## 相关概念

- [[Vector-Search]]
- [[HNSW]]
- 近似最近邻搜索（approximate nearest-neighbor search）
- 图搜索（graph search）
- [[NVMe]]

## 相关论文

- [[Helmsman-OSDI26]] — 给出 DiskANN 类磁盘图在大 top-k、多 SSD 场景中的生产反例。
- [[OdinANN-FAST26]] — 直接针对 DiskANN 的更新 merge、内存峰值和前台干扰问题。
- [[Terminus-MLSys26]] — 为磁盘图搜索加入 rank-aware early termination。
- [[FlowANN-OSDI26]] — 用 discovery–expansion window 隐藏分层图读取，展示另一种依赖解耦方式。
- [[LEANN-MLSys26]] — 用重算换索引容量，并把 DiskANN 作为“先量化遍历再 rerank”路线的对照。
- [[PIMANN-ATC25]] — 选择 cluster-based IVFPQ 映射到 PIM，明确展示图与聚类索引的硬件适配差异。

## 已知局限 / 开放问题

- 需要按 top-k、目标 recall、SSD 数量和 query batch 画清图搜索与聚类扫描的 crossover。
- 持续更新下要联合衡量 recall 漂移、merge/repair、前台 P99 和崩溃恢复，而不只报告稳定吞吐。
- 多租户云盘、NVMe-oF、CXL 和异构 SSD 会让 I/O latency 出现长尾，可能破坏静态 beam/cache 参数。
- DiskANN 的系统成本应包含 DRAM cache、SSD overprovision、轮询 CPU、建索引和无损升级，而不只包含索引文件大小。
