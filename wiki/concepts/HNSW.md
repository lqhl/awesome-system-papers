---
type: concept
aliases: [Hierarchical-Navigable-Small-World]
last_updated: 2026-08-14
tags: [vector-search, ann, graph-index]
---

# HNSW

> Hierarchical Navigable Small World（HNSW）是分层的近似最近邻图索引：稀疏上层负责快速接近查询区域，稠密底层负责扩大候选，以图内存、构建和更新成本换取高召回与低查询延迟。

## 核心思想

HNSW 为向量随机选择最高层级，并在每层维护有限数量的近邻边。查询从最高的稀疏层入口开始贪婪移动，逐层下降；到底层后，用候选队列继续 best-first 探索，直到剩余候选不足以改善当前结果。`M` 控制节点度数，`efConstruction` 控制建图探索，`efSearch` 控制查询探索宽度。

它把高维全扫描改成“沿有导航性的图访问一小部分节点”。但节点访问次序依赖刚读回的邻居，所以执行不是规则的矩阵计算，而是不规则的 pointer chasing。HNSW 在 DRAM 中通常很快；放到 SSD、跨 CPU–GPU 分层或多 GPU 时，串行依赖深度、随机访问和远端边获取会成为一等成本。

HNSW 也不是单一固定配置。索引精度、图度、候选宽度、量化、过滤、入口与内存布局共同决定性能。比较系统时必须在相同数据、distance metric、recall、top-k 和更新状态下调参；只比较默认 `efSearch` 的 QPS，容易把质量差异误当成系统加速。

## 为什么重要

HNSW 是 [[Vector-Search]] 中最常用的强内存基线之一。它代表“用较多随机边和 DRAM，减少实际距离计算与数据扫描”的路线。[[LEANN-MLSys26]] 以 HNSW 图为导航骨架，却不保存 dense embedding；[[PathWeaver-ATC25]] 则把图搜索映射到多 GPU。它既是完整索引，也是许多新系统可裁剪、分层或重新布局的基础部件。

OSDI 2026 的 [[Helmsman-OSDI26]] 给出了重要反例：HNSW 在 DRAM 中仍强，但不表示“读得更少的图”在 SSD 上也一定更快。大 top-k 会扩大每跳候选，并形成多轮依赖读取；多块 NVMe SSD 更擅长同时处理大量互不依赖的 cluster list。Helmsman 的结论是特定生产 regime 下应改用聚类，不是 HNSW 已被普遍替代。

动态图索引还把维护成本暴露出来。[[OdinANN-FAST26]] 指出，双向邻边更新会把一次 insert 扩散到许多 record；缓冲插入会产生 merge spike，log-structured direct insert 又会产生 logical GC。静态构建后的 recall/QPS 不能代表持续插入、删除、tombstone 与重建期间的服务质量。

## 关键观察 / 隐含假设

- **图搜索成本包含访问量和依赖深度两个维度。** [[Helmsman-OSDI26]] 的生产大 top-k 场景中，图方案虽少读数据，却不能把 12 块 SSD 的并行带宽转成吞吐；聚类批量读反而更合适。
- **少量高层或高度节点承担了大量导航。** [[LEANN-MLSys26]] 利用访问概率和 out-degree 倾斜保留重要边、裁剪低价值边；这说明图元数据并非每条边同等重要，但该规律仍依赖数据与查询分布。
- **重算可以替代向量存储，但不能消除查询工作。** LEANN 从原始文本重新运行 encoder，显著缩小索引；它把容量成本换成查询期 GPU/encoder 计算，因此适合生成延迟本来就占主导的 RAG，不适合所有低延迟 ANNS。
- **入口质量会决定后续探索量。** [[PathWeaver-ATC25]] 的 ghost graph 用极少量采样节点改善单/多 GPU 搜索入口，但它是 post-build 辅助层，不等于重新构建完整 HNSW hierarchy。
- **在线更新不是免费的局部操作。** [[OdinANN-FAST26]] 的 neighbor bi-directional update、并发锁和记录回收说明，查询热点节点也往往是更新争用热点。
- **硬件放置会改变“最佳算法”。** [[PIMANN-ATC25]] 因 CPU–PIM 带宽限制而排除图式 ANNS；[[Snary-ATC25]] 选择更 pipeline-friendly 的 LSH。两者说明硬件友好性可能迫使系统牺牲 HNSW 的图质量优势。
- **提前终止需要质量信号。** [[Terminus-MLSys26]] 在 Starling 异步磁盘图搜索上利用排名稳定性停止读取，但结论不能直接外推到纯内存 HNSW；存储布局和 I/O pipeline 是证据的一部分。
- **隐含假设：embedding 空间在索引生命周期内相对稳定。** 模型漂移会同时改变近邻关系、热点节点与最优参数；局部修补是否仍保导航性，不能只靠旧 recall 验证。

## 设计空间与取舍

- **图度 `M`**：更多边通常改善连通性与召回，也增加内存、构建、更新和 cache miss；度过小会形成局部陷阱。
- **`efConstruction` / `efSearch`**：更宽探索能提高图质量或查询召回，代价是更多距离计算、候选队列和尾延迟。两者不能脱离目标 recall 单独比较。
- **完整向量 / 量化向量 / 查询时重算**：完整向量最快但占空间；PQ 等量化减少容量并引入近似误差；[[LEANN-MLSys26]] 的重算最省索引，却消耗查询期 encoder 算力。
- **DRAM / SSD / CPU–GPU 分层**：全 DRAM 延迟低、成本高；SSD 扩大容量但暴露逐跳 I/O；异构分层可把距离计算放 GPU、图边放 host，却必须像图搜索流水线那样隐藏 fetch latency。
- **静态高质量图 / 在线可变图**：离线图可以花更久选择邻边；动态系统需要 insert buffer、delta graph、tombstone、merge 或周期重建，并为查询提供一致视图。
- **单入口 / 多入口 / 辅助 ghost layer**：更好的入口减少无效探索，但增加额外图、训练或采样维护。入口在 embedding drift 后也可能失效。
- **图索引 / 聚类索引 / 混合索引**：小 top-k、热点可缓存和严格低延迟时 HNSW 很强；大 top-k、多 SSD 且允许较宽延迟时，[[Helmsman-OSDI26]] 的 dependency-free cluster scan 更能利用带宽。
- **固定搜索预算 / query-aware termination**：固定预算容易配置和复现；按查询难度或排名稳定性调整能省工作，却要处理 rare query 与质量下界。

## 引用本概念的论文

- [[Helmsman-OSDI26]] — 以生产大 top-k 负载说明 DRAM HNSW 成本高，而 SSD 图遍历依赖深；聚类方案是在特定 regime 下的替代，不是普遍胜出。
- [[LEANN-MLSys26]] — 保留 HNSW 导航图并裁剪低价值边，查询时从原始文本重算 embedding；把 76 GB 语料的索引从约 188 GB 降到 4 GB 的结果依赖同一 encoder 与 RAG 端到端延迟结构。
- [[OdinANN-FAST26]] — 研究十亿级图索引的直接在线插入，暴露双向边更新、锁热点、log 膨胀和 logical GC。
- [[PathWeaver-ATC25]] — 将图式 ANNS 扩到多 GPU，并以极小 ghost graph 改善入口；其辅助层不改变主图 reachability。
- [[PIMANN-ATC25]] — 指出所测 PIM 平台的 CPU–PIM/PU–PU 带宽不适合 HNSW 类 pointer chasing，因而选用 IVFPQ。
- [[Snary-ATC25]] — 采用更适合 SmartNIC pipeline 的 LSH，并把真实业务是否需要 HNSW/PQ/IVF-PQ 质量列为外推边界。
- [[Terminus-MLSys26]] — 在磁盘图系统 Starling 上做 ranking-aware early termination；尚未证明相同信号适用于纯内存 HNSW。

## 已知局限 / 开放问题

- 缺少统一覆盖 recall、top-k、filter selectivity、更新率、P99/P99.9、构建时间、索引峰值内存和重建期间质量的生产基准。
- 删除与持续插入会逐步破坏导航性；何时局部修边、何时合并 delta、何时全量重建，仍缺少能预测质量退化的可靠指标。
- embedding/model drift 会改变近邻、入口和热点，自动重调 `M`、`efSearch`、量化与 tier placement 仍是开放问题。
- 多租户下，候选队列、随机 DRAM/SSD 访问和热点节点会造成 cache、带宽与 I/O queue 干扰，现有系统很少给出质量感知的隔离保证。
- HNSW 与聚类、PQ、SSD tier、GPU 重算的混合结构应如何按 workload trace 自动选择，不能只根据数据规模决定。
- rare query 的 recall violation 往往被平均 recall 隐藏；需要按 query cohort、业务价值和最坏质量报告，而不只给总体 Recall@k。
