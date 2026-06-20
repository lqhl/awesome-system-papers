---
type: paper
name: LEANN
full_title: "LEANN: A Low-Storage Overhead Vector Index"
authors: [Yichuan Wang, Zhifei Li, Shu Liu, Yongji Wu, Ziming Mao, et al.]
venue: MLSys
year: 2026
tags: [vector-search, ann, rag, storage-efficiency, hnsw]
source_pdf: "[[093f65e080a295f8076b1c5722a46aa2.pdf]]"
source_md: "[[093f65e080a295f8076b1c5722a46aa2]]"
---

# LEANN: A Low-Storage Overhead Vector Index (MLSys 2026)

> **一句话总结**：在 [[RAG]] 端到端延迟被 LLM 生成主导（>20 s vs 搜索 ms 级）这一观察下，LEANN 不存 dense embedding、查询时用同一 encoder 现场重算，并以两级搜索（[[Product-Quantization|PQ]] 近似 + 精确重算）和高度节点保留图剪枝压缩 [[HNSW]] 元数据，把 76 GB 语料索引从 188 GB 压到 4 GB（50×），90% Recall@3 下 RAG 端到端只多 <20% 延迟、下游准确率与 HNSW 持平。

## 问题与动机

[[Vector-Search]] / [[ANNS]] 是 [[RAG]]、推荐、语义搜索的基础设施。高维 embedding 加上 proximity graph 元数据后，索引体积常常是原始数据的数倍：论文在 76 GB Wikipedia 语料（60M 个 256-token chunk、768-dim [[Contriever]] embedding）上测得 **173 GB** 向量 + **15 GB** [[HNSW]] 图，总计约 **188 GB**，远超个人设备常见的 32 GB RAM（RTX 4090 测试机配置）。

已有降存储路线各有硬伤：

- **[[Product-Quantization|PQ]] 极致压缩**：约 35× 才能把向量压到 5 GB，但高压缩比量化误差让检索 recall 掉到甚至低于 [[BM25]]，RAG 下游 EM/F1 也明显劣化。
- **PQ 压不了图元数据**：每个节点 64 邻居 × 4 B = 256 B，相对典型 1 KB 文本 chunk 已是 25% 额外开销；[[DiskANN]] 的 sector-aligned layout 更夸张，总 footprint 可达 **270 GB**。
- **[[IVF-Recompute]] / EdgeRAG 类方案**：只存 centroid、查询时重算 embedding，存储够小，但检索要 O(√N) 次重算，比 graph 的 O(log N) 慢最多 **200×**。

作者在 Table 1 的关键测量是：在 RTX 4090 上用 Qwen3-4B 做 [[RAG]] 时，**生成阶段占端到端延迟绝对主导**（复杂推理可达数十秒），向量搜索仅毫秒到百毫秒级。因此「用少量搜索延迟换巨大存储节省」在端侧 RAG 场景是合理 trade-off。论文核心问题是：能否在 storage-constrained 环境（笔记本、工作站、冷数据集）里，把索引压到原数据 **5% 以下**，同时保持 SOTA recall 和可接受的 RAG 延迟。

## 关键观察 / 隐含假设

- **观察 1：Proximity graph 查询只需访问 O(log N) 个节点的 embedding，不必全量存储向量**。
  - **依赖假设**：图遍历质量足够高（[[HNSW]] best-first search + 合适 `ef`），且 build/query 使用**同一 embedding encoder**；原始文本 chunk 可本地读取以支持重算。
  - **可能失效场景**：embedding 模型升级后旧图与新 encoder 不匹配；纯图像/多模态索引若原始对象不可快速重编码，重算路径断裂；极高 recall 目标迫使 `ef` 膨胀、重算次数接近线性扫描。

- **观察 2：[[HNSW]] 图中节点访问概率与 out-degree 高度倾斜——少量 high-degree hub 承担大部分遍历，低度节点边可激进剪枝**。
  - **依赖假设**：图在 build 后 degree 分布稳定；保留 top **β%**（实验约 **2%**）hub 的完整邻接、其余节点限 **m = M/5** 即可维持连通性；剪枝后平均度可减半而 recall 几乎不掉。
  - **可能失效场景**：数据分布变化导致 hub 漂移；频繁 update 破坏 hub 结构；与 [[RNG-Pruning]] 等更激进稀疏化结合时，冷启动查询可能找不到入口。

- **观察 3：RAG 端到端 latency budget 主要在 LLM generation，检索阶段可承受额外重算与 batching 带来的 staleness**。
  - **依赖假设**：下游是「retrieve-then-generate」长生成任务（Qwen3-4B 上常 >10 s）；用户接受端到端检索开销 <20%（多数任务 <10%，GPQA 等长 CoT 任务 <3%）。
  - **可能失效场景**：高 QPS 并发检索、无生成阶段的纯搜索 API；短回答 chatbot 检索占比变大；CPU-only 或弱 GPU 端侧 encoder 吞吐不足时，「可换延迟」假设不成立。

- **假设 1：100× 压缩的 PQ 表误差很大，不能学 [[DiskANN]]「先 PQ 全图遍历再 rerank top-100」；必须交错近似与精确距离**。
  - **证据强度**：**强**——Figure 4/6 显示高压缩 PQ 单独搜索 recall 不足；two-level search 相对 naive recomputation 平均 **1.4×** 加速。

- **假设 2：查询路径存在 skewed access，可选地为 hot 节点缓存 exact embedding（论文 Appendix D.3）能进一步降延迟**。
  - **证据强度**：**中**——缓存 10% embedding 带来 **1.5×** 加速、hit rate 最高 41.9%，但 SSD 加载开销使收益低于 hit rate；论文主路径不依赖缓存。

## 核心方法

LEANN 在 [[FAISS]] 上实现，离线只持久化两样东西：**剪枝后的 proximity graph（CSR 邻接表）** + **高度压缩的 PQ 表**（codebook 约为原向量的 1/100，约 `O(4N × dim/100)` B）。原始 dense embedding 在 build 后丢弃。

### Graph-based recomputation + 两级搜索

核心思路：查询沿 [[HNSW]] 图 best-first 遍历时，对需要距离的邻居**不读盘取向量，而是从原始文本 chunk 调本地 encoder 重算**（Algorithm 2）。

难点是 naive 逐步重算太慢，尤其 PQ 压缩比极高时近似距离会误导遍历。LEANN 的 **two-level search** 交错两类距离：

1. 对每个未访问邻居，先用 PQ 算 approximate distance，放入 approximate queue **AQ**；
2. 从 AQ 取 top **α%**（且不在 exact queue **EQ** 中）的候选做**精确重算**，插入 **EQ** 继续图扩展；
3. **EQ 用精确距离保证遍历方向正确，AQ 用廉价 PQ 信号剪枝不必要的重算**。

这比 DiskANN 式「PQ 全程导航 + 最后 rerank」更抗高压缩误差：错误近似邻居不会把搜索带进死胡同后靠 rerank 补救。

**Dynamic batching** 进一步缓解 GPU 利用率：放宽 best-first 的严格步间依赖，跨多个 exploration step 累积待重算节点，直到 batch 达到阈值（如 64）再一次性送 encoder。代价是探索顺序略有 staleness，但 Figure 5 显示在 two-level 基础上再叠 batching，平均加速从 1.4× 提到 **1.8×**（峰值 **2.0×**），HotpotQA 等多跳路径受益最大。

### High-degree preserving graph pruning

即使去掉向量，图元数据仍可达原数据 30%+。LEANN 把剪枝形式化为：在存储预算 **B** 内最小化每次查询重算节点数 **T(G')**，同时 recall ≥ **τ**（Algorithm 3）。

策略：按 out-degree 选 top **β%** 为 hub，hub 保留最多 **M** 条边，普通节点只保留 **m = M/5**。重建邻接时仍允许普通节点与 hub 建立双向链接（上限 M），避免低度节点失去导航骨干。相对 random 50% 删边或全局 Small-M 限度，在平均度从 18 减半到 9 时，达到同 recall 所需重算节点数：random 多 **1.8×**，Small-M 多 **5.8×**，且在 94%/96% recall 直接失败。

### Storage-efficient build & update

**Sharded merging pipeline**（§6）：k-means 软分配到两个 shard → 分片建图并立即丢弃 embedding → 合并 shard 图（重复节点取更高 HNSW level，超限随机丢边）。15 分片可把建索引峰值存储降约 **5×**，k-means 分片比随机分片连通性明显更好（Figure 10）。

**Update**：单点插入通过距离 cache + 简化 neighbor shrink 把复杂度从 O(M·efC + efC² + M³) 降到 O(M·efC)；**soft delete** 只打 flag、不拆图；批量插入先 buffer embedding，查询时合并 buffer 结果再异步落盘。Figure 8 显示相对 naive add 最高 **63.3×** 加速。

可选 **embedding cache**：磁盘预算放松时可为高频访问节点物化 exact vector（Appendix D.3）。

## 设计取舍

- **重算 vs 存储**：换来 **50×** 索引缩小（<5% raw data），牺牲 standalone 检索延迟（高于 [[HNSW]]/[[DiskANN]]）和查询期 GPU/encoder 算力；在 [[RAG]] 端到端里这笔账通常划算。
- **100× PQ vs 精度**：PQ 表极小（~4 GB/60M 向量），但误差大；用 two-level 交错精确距离弥补，而不是把 PQ 当最终排序依据。
- **Dynamic batching vs 遍历新鲜度**：跨步 batch 提高 GPU 利用率，但引入轻微探索 staleness；适合 batch 目标明确（64）的 GPU encoder，不适合极低延迟单点查询。
- **Hub-preserving prune vs 通用图压缩**：只保留 2% hub 完整邻接，对均匀随机图或动态更新剧烈的索引可能变脆；random/Small-M 更「公平」但严重伤害 recall。
- **Soft delete vs 空间回收**：O(1) 删除、保持连通，但 deleted 节点仍占图结构与遍历成本；>5% 删除率需 background rebuild（论文留作 future work）。
- **边界条件**：**端侧 RAG / 冷数据集 / skewed access** 最优雅；**高 QPS 纯搜索**、**embedding 模型频繁变更**、**无本地原文的多模态索引**会变脆；主实验 embedding 固定为 Contriever，生成用 Qwen3-4B。

## 实验与结果

**Setup**：RPJ-Wiki **76 GB** → 60M passage；QA 评测 NQ、TriviaQA、GPQA、HotpotQA，外加 FinanceBench、Enron Email、LAION；硬件 RTX 4090（32 GB RAM）与 M1 Ultra Mac；对比 [[HNSW]]、[[IVF]]、[[DiskANN]]、IVF-Disk、IVF-Recompute、PQ、[[BM25]]。

- **存储**：仅 LEANN 与 IVF-Recompute 总开销 <5% raw data；LEANN **4 GB** vs HNSW **188 GB** vs DiskANN **270 GB** vs PQ+图 **20 GB**；相对 HNSW 在多个 personal dataset 上节省 **>97%** 存储（Table 3）。
- **检索延迟 @90% Recall@3**：IVF-Recompute 比 LEANN 慢最多 **200×**；LEANN standalone 慢于 HNSW/DiskANN，但 **RAG 端到端额外开销 <20%**（GPQA 长生成 <3%）；M1 上结论一致（Table 4）。
- **RAG 准确率**：90% recall 配置下 LEANN EM/F1 **与 HNSW 持平**；相对 BM25 EM 最高 +11.8%、PQ +11.3%；NQ/TriviaQA 提升最大，GPQA/HotpotQA 因语料 OOD 与单跳检索设置提升较小（Figure 4）。
- **组件消融**：two-level search **1.4×**（最高 1.6×）；+dynamic batching **1.8×**（最高 2.0×）；hub-preserving prune 在边数减半时 recall 曲线贴近原图；GTE-small 替代 Contriever 在 2M 语料上 **2.3×** 加速、准确率差 <2%。
- **可部署性**：HNSW/IVF 在 32 GB 机器 OOM，LEANN 可在 RTX 4090 与 EC2 Mac 上运行；1 秒内 top-3 recall 可达 **>90%**。

## Critical Analysis

### 论证链条

主链条较闭合：**测量到索引体积是端侧部署瓶颈** → **RAG 生成主导延迟允许换检索时间** → **图遍历只需少量 exact distance** → **不存向量 + PQ 引导重算 + hub 剪枝** → **存储降 50× 且 90% recall 下 RAG 准确率不掉**。

设计映射也清楚：two-level search 直接回应「高压缩 PQ 不能单独导航」；dynamic batching 回应「重算是 GPU-bound」；hub prune 回应 Figure 2 的 degree/access skew；sharded build 回应建索引峰值存储。

薄弱环节在于把 **个人设备 RAG 实验**外推为「通用 storage-efficient ANNS」：主 benchmark 是 Wikipedia 检索 + 固定 encoder；未系统测量 **高并发查询**、**索引长期 update 后图退化**、**换 embedding 模型** 的成本。论文声称「first to study storage challenge」，但磁盘型 ANNS（[[DiskANN]]、AiSAQ、LM-DiskANN）早已在 DRAM/SSD 维度做压缩，LEANN 的差异化在 **重算 + 极致剪枝** 而非全新问题定义。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 生成主导延迟，检索可换 | Table 1/2 多次测量 generation >> retrieval | 纯搜索 API、短生成、检索 QPS 极高 |
| O(log N) 重算足够 | 60M 规模 90% Recall@3 + 消融 | 更高 recall、更差图质量、update 后 hub 退化 |
| Hub 剪枝保连通 | Figure 6/7 vs random/Small-M | 非 HNSW 图、动态图、β/M 未重调 |
| 同 encoder build/query | 实现与实验协议如此 | 模型版本升级、domain adapter 变更 |
| Soft delete 可长期运行 | 删除 flag + 遍历跳过 | 删除率 >5% 后性能与空间未量化 |

### 实验可信度

- **优势**：Baseline 覆盖 graph（HNSW、DiskANN）、cluster（IVF 系）、压缩（PQ）、lexical（BM25）和 IVF-Recompute；主结果同时报 **存储、standalone latency、端到端 RAG latency、下游 EM/F1**；关键组件有逐步消融（Figure 5–8）。
- **局限**：HNSW/IVF 在 32 GB 机器 OOM，延迟对比在**更大内存 server** 上测，端侧「同机对比」不完全公平；Recall@3 的 ground truth 来自 exact search 代理，非人工标注；GPQA/HotpotQA 上的有限提升被合理解释，但也说明 **多跳 / OOD** 场景并非主战场。
- **缺失**：缺少 **tail latency**（P99）、**多租户并发**、**crash consistency**、**索引长期 churn** 实验；与 EdgeRAG/MicroNN 等端侧方案的 head-to-head 有限。

### 系统性缺陷

- **尾延迟与 SLO**：报告的是达到 90% recall 的平均检索时间与端到端均值，**P99 检索延迟**、encoder 排队、batch 等待时间未讨论。
- **资源隔离**：单用户端侧假设；多应用共享 GPU encoder 时的干扰、公平性论文未覆盖。
- **故障恢复**：soft delete + async batch insert 的崩溃一致性、重建策略未实验验证。
- **可观测性**：two-level search 与 dynamic batching 使查询路径更难解释；论文未讨论如何诊断「重算过多 / hub 失效」。
- **运维成本**：需本地保留原文 + embedding 模型；模型与索引版本绑定带来的 **re-embed 全库** 成本未量化；论文未讨论与云端托管向量库（[[Milvus]] 等）的 TCO 对比。
- **正确性**：soft delete 后图仍遍历 deleted 节点，长期可能增加无效 hop；>5% 删除触发 rebuild 的策略仅有概念描述。

## 局限与 Future Work

- **局限 1**（论文自述）：高压缩 PQ 误差大，必须依赖 two-level 交错精确距离；其他近似形式（distilled encoder、link-and-code）仅一笔带过。
- **局限 2**（论文自述）：分片合并时对超限边采用 **random drop**，更优的 [[RNG-Pruning]] 合并留作 future work。
- **局限 3**（论文自述）：soft delete 在删除比例超阈值（如 5%）时需 background rebuild，策略未深入评估。
- **局限 4**（实验边界）：主场景是 **单跳 Wikipedia RAG + 端侧 GPU**；GPQA/HotpotQA 提升有限，未覆盖 agent 多轮检索或跨模态大规模索引。
- **Future work 1**：在 **production trace**（查询频率倾斜、embedding 版本滚动、持续 insert/delete）上测量 recall 与延迟退化曲线，给出 rebuild / re-embed 触发条件。
- **Future work 2**：量化 **dynamic batching staleness** 对 tail latency 与 recall 的独立影响，并探索 **CPU/GPU pipeline overlap**（Figure 13 显示重算占 ~76% 且有 I/O、tokenize 可重叠空间）。
- **Future work 3**：与 **极轻量 on-device encoder**（论文 GTE-small 已示 2.3× 潜力）和 **分层缓存**（hot hub 物化）做联合调度，在固定 5% 存储预算下画清 latency floor。

## 相关

- **相关概念**：[[ANNS]]、[[Vector-Search]]、[[RAG]]、[[HNSW]]、[[Product-Quantization]]、[[Graph-Index]]、[[Approximate-Nearest-Neighbor]]
- **同类系统**：[[FAISS]]、[[DiskANN]]、[[IVF-Recompute]]、EdgeRAG、[[BM25]]、MicroNN、ObjectBox
- **同会议**：[[MLSys-2026]]
- **对比**：[[LEANN-MLSys26|LEANN]] vs [[HNSW]]（50× 存储，RAG 端到端延迟可接受）；vs IVF-Recompute（同量级存储，但 O(√N) 重算慢 200×）；vs [[DiskANN]]（磁盘导航型压缩 vs 端侧重算型压缩）