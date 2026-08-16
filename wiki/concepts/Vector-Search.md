---
type: concept
aliases: [Vector-Search, ANN-Search, Approximate-Nearest-Neighbor-Search]
last_updated: 2026-08-14
tags: [retrieval, ann, indexing, systems]
---

# Vector Search

> 向量搜索（vector search）按 embedding 距离寻找近邻。大规模系统通常接受近似结果，以换取更低延迟和更少资源；真正的设计问题不是只选一种索引，而是在 recall、rank utility、依赖深度、容量、更新、并发和硬件成本之间取舍。

## 核心概念

给定 query 向量，精确搜索要计算它与所有数据向量的距离，成本随数据量线性增长。近似最近邻搜索（ANNS）通过图、聚类、量化或学习式裁剪缩小候选集，再对少量候选做精确距离或 rerank。

算法只决定“可能访问谁”，系统还要决定“数据放哪里、按什么顺序读取、何时停止、怎样更新”。同一 recall 下，少读数据的图索引可能被逐跳依赖卡住；多读一些 cluster 的方案反而能一次把请求铺到多块 SSD。向量都放 GPU 可减少延迟，却遇到 HBM 容量墙；放到 CPU/SSD/PIM 则要重新组织预取、并发和数据布局。

## 关键观察 / 隐含假设

- **访问量和依赖深度必须一起看。** [[Helmsman-OSDI26]] 发现，大 top-k 下 SSD 图搜索虽然读得少，却形成很长的串行 I/O 链；聚类索引可以一次并发读取很多 posting lists，更能利用 12 块 Gen5 NVMe。[[FlowANN-OSDI26]] 则没有放弃图，而是发现 graph discovery 与真正 expansion 之间通常有多个 step 的窗口，用这个窗口隐藏 CPU→GPU edge fetch。
  - **隐含假设**：Helmsman 需要大 top-k、本地多盘和可批量 cluster I/O；FlowANN 需要静态 proximity graph、可预测的小块 fetch 延迟与强 host。两者回答的 workload 不同，不能只用“图或聚类谁更好”概括。

- **容量可以换计算、传输或磁盘。** [[LEANN-MLSys26]] 不保存 dense embedding，查询时从原文重新编码，只保留压缩图和 PQ 提示；[[PIMANN-ATC25]] 把 IVFPQ distance computation 放进 UPMEM，以大量弱核和聚合内存带宽换 GPU HBM。前者适合生成阶段很长的端侧 RAG，后者适合高 QPS、cluster-based ANNS 和特定 PIM 硬件。
  - **隐含假设**：原始对象与 encoder 始终可用，或 PIM 的 query 热度和 cluster 副本可稳定管理。模型升级、低 QPS、动态图和硬件接口变化都可能破坏这些前提。

- **多 GPU 不应只复制完整搜索。** [[PathWeaver-ATC25]] 指出，传统 sharding 让每个 shard 从头独立遍历，再在 CPU 合并，GPU 数增加时总 iteration 也增加。它让搜索路径跨 shard 延续，并过滤大量不会进入 top-k 的邻居，在四张 A6000 上改善吞吐扩展。
  - **隐含假设**：查询 batch 足够大，可以填满跨 GPU pipeline；静态、随机 sharding 与 L2 距离适合 direction-guided selection。在线小 batch、语义分片或更多 GPU 尚无同等证据。

- **动态更新会改变搜索结构。** [[OdinANN-FAST26]] 把 buffered insert 的 merge 尖峰改成 direct insert，并用页面内 out-of-place update 与近似并发控制稳定 search latency。它说明静态 ANN benchmark 无法代表持续摄取服务：更新路径可能争用 SSD、抬高内存，甚至慢慢损伤图质量。
  - **隐含假设**：约 2 倍磁盘空间与轻微 recall/I/O 退化比 merge 尖峰更可接受；单条约 11 ms insert 满足目标。强一致或高写带宽场景可能选择不同方案。

- **搜索到“足够好”时应考虑停止。** [[Terminus-MLSys26]] 观察到磁盘图搜索的高排名结果常在早期 I/O 出现，而 RAG 质量对前几名更敏感；它按每轮新结果的 rank-weighted utility 决定提前停止。这个方向把固定 Recall@k 改成与下游效用更一致的预算分配。
  - **隐含假设**：rank utility 随位置衰减，且可用近期任务校准。多跳检索、reranker 或要求近乎完整 recall 的任务可能让尾部文档重新重要。

- **向量检索只是 RAG 工作流的一段。** [[HedraRAG-SOSP25]] 将多轮 retrieval、generation、rewrite 和 rerank 表成 RAGraph，再跨请求批处理、重排和缓存索引。它说明“单次 ANN QPS 更高”未必等于整个 RAG workflow 更快；CPU 检索和 GPU generation 的节奏、分支与 speculative work 也会决定吞吐。

## 设计空间

### 索引结构

- **图索引**（如 [[HNSW]]、[[DiskANN]]）通常少读候选、recall 高，但遍历有逐步依赖，更新还要维护邻接关系；
- **聚类/IVF** 可以批量扫描独立 posting lists，适合 SSD/PIM 并行，代价是可能 over-read，并需决定 `nprobe`；
- **量化**降低 vector footprint 和距离成本，但高压缩误差会误导导航，常需精确重算或 rerank；
- **混合结构**可让 DRAM/GPU 保存导航层、SSD/CPU 保存主体，但需要 cache、预取和一致性。

### 数据与执行位置

- GPU/HBM 延迟低、吞吐高，容量贵；多 GPU sharding 又会引入路径重复或通信；
- CPU/DRAM 容量大，随机访问和 distance compute 较慢，但可做 rerank 或为 GPU 提供冷边；
- NVMe 容量便宜，适合批量独立 I/O；逐跳小随机读会暴露 IOPS 和依赖深度；
- PIM/CXL 等硬件能把计算靠近数据，却把系统绑定到专用调度、driver 和数据放置。

### 质量与预算

- Recall@k 对所有位置等权，容易忽略下游更看重 top ranks；
- Ranked Recall、RAG EM/F1 或业务 reranker 指标更贴近最终价值，但需要任务特定校准；
- 固定 I/O/step budget 易部署，却不能适应 query 难度；动态早停或 learned `nprobe` 更高效，也需要 conservative fallback；
- 平均 recall 达标不等于每个 query 达标，rare query 与高价值请求应单独报告。

### 更新与运维

- 周期重建给静态索引较高质量，但需要双版本切换、辅助 delta index 和大量构建资源；
- direct insert 提高新鲜度并摊平成本，却会引入写放大、锁与图退化；
- tombstone/soft delete 很便宜，但长期累积会增加无效遍历，最终仍要 compact 或 rebuild；
- embedding 升级会让旧向量、图和学习式裁剪一起过期，其成本经常高于一次普通索引更新。

## 跨论文张力

- **少读 vs 可并行读**：FlowANN/OdinANN/Terminus 尽量减少或隐藏图访问；Helmsman 接受更多读取，换独立、大批 I/O。
- **低存储 vs 低查询计算**：LEANN 用在线重算换 50 倍索引缩小；传统 HNSW/DiskANN 用预存 embedding 换低延迟。
- **专用硬件 vs 可部署性**：PIMANN 在真实 UPMEM 上得到高吞吐，却依赖未文档化 control interface 和修改 driver；普通 CPU/GPU/SSD 路线更易获得。
- **批吞吐 vs 在线尾延迟**：PathWeaver 使用 60K query batch 展示多 GPU pipeline；FlowANN 也随 batch 增大更容易隐藏 fetch。在线小 batch 是否受益必须单独测。
- **静态最优 vs 持续变化**：Helmsman/FlowANN 的离线布局和 profile 很强；OdinANN 说明 insert/delete 与 query drift 会重写这张性能图。

## 证据边界

- [[FlowANN-OSDI26]] 的“一张 GPU”仍配 160-core CPU、2 TB DRAM 和 CPU rerank；它证明 accelerator 数少，不证明整机成本低。
- [[Helmsman-OSDI26]] 的 2–16 倍汇总绑定 90% recall、大 top-k 和 12 盘本地阵列；它相对全内存 HNSW 的吞吐仍常为 25%–70%。
- [[OdinANN-FAST26]]、[[Terminus-MLSys26]] 都是单机 NVMe 结果，未覆盖多租户共享盘、分片和副本；前者的 crash recovery 主要是设计，后者主要报平均 I/O/QPS。
- [[LEANN-MLSys26]] 的端到端延迟结论依赖 LLM generation 明显慢于 retrieval；纯搜索 API 或高并发检索可能无法接受在线重算。
- [[PathWeaver-ATC25]] 止于 4 GPU 和 50M 向量，不能直接支撑十亿规模、多节点扩展。
- [[PIMANN-ATC25]] 只支持 cluster-based IVFPQ，不支持依赖跨核随机访问的 graph ANNS。
- [[HedraRAG-SOSP25]] 的 1.5–5 倍是多种 workflow 的系统结果，不能归因于向量索引单项，也不能保证 speculative path 不浪费计算。

## 研究判断

向量搜索的评测单位应从“一个 ANN kernel”扩展为“持续运行的检索服务”。至少要同时报告数据规模、维度、距离、top-k、recall/rank metric、batch、P50/P99、构建、insert/delete、内存/磁盘、CPU/GPU/SSD 数和故障路径。只报 QPS–Recall 曲线，很难判断系统能否服务真实 RAG 或推荐负载。

当前最值得继续研究的不是再争论图和聚类谁普遍更好，而是让系统根据 query、rank utility、更新压力和硬件争用动态选择路径，并提供可观测的保守回退。真正可靠的服务还要把 embedding 版本、索引版本、结果新鲜度和 rebuild 状态作为一等元数据。

## 引用本概念的论文

- [[FlowANN-OSDI26]] — 解耦图节点依赖，用 CPU–GPU 分层隐藏十亿规模 edge fetch。
- [[Helmsman-OSDI26]] — 面向大 top-k 的全闪存聚类 ANNS 与生产部署。
- [[OdinANN-FAST26]] — 用 direct insert 消除在线图索引的 merge 尖峰。
- [[LEANN-MLSys26]] — 用 embedding 重算与图剪枝换极低索引存储。
- [[PathWeaver-ATC25]] — 让搜索路径跨 GPU shard 延续，减少重复遍历。
- [[PIMANN-ATC25]] — 在 UPMEM 上细粒度调度 IVFPQ distance computation。
- [[Terminus-MLSys26]] — 按下游 rank utility 为磁盘图搜索动态早停。
- [[HedraRAG-SOSP25]] — 将 retrieval 与 generation 放进同一个异构 RAG workflow 调度。
