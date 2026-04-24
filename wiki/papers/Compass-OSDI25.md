---
type: paper
name: Compass
full_title: "Compass: Encrypted Semantic Search with High Accuracy"
authors: [Jinhao Zhu, Liana Patel, Matei Zaharia, Raluca Ada Popa]
venue: OSDI
year: 2025
tags: [encrypted-search, oram, ann-search, hnsw, privacy]
source_pdf: "[[osdi25-zhu-jinhao.pdf]]"
source_md: "[[osdi25-zhu-jinhao]]"
---

# Compass: Encrypted Semantic Search with High Accuracy (OSDI 2025)

> **一句话总结**：Compass 把 HNSW 图遍历和 Ring ORAM 做白盒协同设计，实现精度比肩明文的加密语义搜索，user-perceived 延迟 0.57–1.28s（跨区网络），比 baseline HNSW-over-ORAM 快 920×，无需可信硬件、服务端完全不可信。

## 问题

端到端加密的云服务（WhatsApp、iCloud Backup、Dropbox）需要支持「搜自己加密的数据」。现有加密搜索有两大问题：(1) **精度低**——主流工作都是 inverted-index 的 lexical 搜索（TF-IDF），捕捉不到语义；现代 Google/Bing/Dropbox Dash 都用 embedding-based semantic search。(2) **安全性妥协**——要效率就得泄漏 access pattern（被 leakage-abuse attack 反推数据）、依赖 TEE（SGX 侧信道）、或假设多服务器非合谋（很难部署）。

若直接在 HNSW（top 图 ANN 索引）上套 ORAM，每访问一个图节点发一次 ORAM 请求，单次查询需几十到上百次 round trip、GB 级带宽，完全不可用。FHE 做 linear scan（HERS）开销巨大，不支持任意 embedding 距离度量。

## 核心方法

**系统架构**：client 保存 ORAM stash、position map、HNSW 上层图与 Quantized Hints；server 保存 Ring ORAM 树，每个 block 对应一个 HNSW 节点（嵌入 + 邻居列表）。client 本地跑搜索算法，只通过 ORAM 请求按需取数据。

三个关键技术：

1. **Directional Neighbor Filtering**：在 client 本地保存所有节点的 Product Quantization 压缩向量（Quantized Hints，~1% 原大小）。遍历时先用量化向量算 query 到邻居的近似距离，只取 top efn 个真实邻居（而非全部 M 个）——省 M/efn 倍带宽，精度损失可控（M=128, efn=24 时几乎无损）。
2. **Speculative Neighbor Prefetch**：每一步从 candidate list 取 top efspec 个节点，一次批量 ORAM 请求把它们的邻居都拉回来——把轮次从 ef 级降到 ef/efspec 级，显著压缩 round trip。
3. **Graph-Traversal Tailored ORAM**：白盒修改 Ring ORAM——(a) 把节点 embedding 和邻居列表塞进同一个 ORAM block 省一次 round trip；(b) **multi-hop lazy eviction**——一次 query 的多轮 ORAM 批量访问全部跳过 eviction，先返回给用户再统一驱逐，online latency 掉 1.5–5.6×；(c) 对 stash 按 path ID 排序把 bucket 查找从 O(ZN) 降到 O(log N)。配合 Merkle tree 做完整性保护抵御恶意服务器。

## 关键结果

- 精度：4 个数据集（MS MARCO、TripClick、SIFT1M、LAION）上 Recall@10 ≥ 0.9，匹配 brute-force embedding search；显著高于所有 lexical baseline。
- 延迟：slow cross-region 网络（400 Mbps/80 ms RTT）user-perceived 0.57–1.28 s；比 HNSW-over-ORAM (strawman) 快 920×，比 HE-Cluster (Tiptoe 式) 快数个数量级。
- 通信：每 query 10 MB 以下非驱逐开销；MS MARCO (8.8M 文档) 总量 226 MB / 9 round trips。
- 内存：小数据集 client < 100 MB；MS MARCO client ~500 MB（强于 client-side index 的 34 GB 强 27–75×）。
- 安全：IND-CCA2 + collision-resistant hash 下，完全不可信 malicious server，不依赖 TEE、不依赖非合谋假设。

## 相关

- **相关概念**：[[Oblivious-RAM]]（Ring ORAM / Path ORAM）、[[HNSW]]、[[Product-Quantization]]、[[ANN-Search]]、leakage-abuse attack、[[RAG]]
- **同类系统**：HERS（FHE linear scan）、SANNS、Tiptoe（public DB）、Oblix、DORY、Pacmann
- **同会议**：[[OSDI-2025]]
