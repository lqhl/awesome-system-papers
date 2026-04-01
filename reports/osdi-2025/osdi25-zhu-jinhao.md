# Compass: Encrypted Semantic Search with High Accuracy

**作者**：Jinhao Zhu (UC Berkeley), Liana Patel (Stanford University), Matei Zaharia (UC Berkeley), Raluca Ada Popa (UC Berkeley)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/zhu-jinhao
**源文件**：[osdi25-zhu-jinhao.pdf](../../papers/osdi-2025/osdi25-zhu-jinhao.pdf)

---

## 一、背景

端到端加密（E2EE）已被 WhatsApp、iCloud、Signal 等主流数据系统广泛采用，用户数据以加密形式存储在云端。在此场景下，加密搜索（encrypted search）是一个长期研究方向，旨在让服务器在不解密数据的情况下执行搜索。

现代搜索系统（Google、Bing、Elasticsearch、Mac Spotlight 等）已普遍采用语义搜索（semantic search），通过将查询和文档转化为高维向量 embedding，基于向量空间中的距离而非关键词匹配来理解查询意图。语义搜索在准确性上显著优于传统的关键词（lexical）搜索。

然而，现有的加密搜索方案在安全性和搜索质量之间存在根本矛盾：要么泄漏访问模式以换取效率，要么依赖可信硬件（TEE），要么仅支持精度较低的关键词搜索。

---

## 二、要解决的问题

1. **安全性不足**：大量加密搜索方案泄漏 access pattern，可被 leakage-abuse attack 重建大量数据或查询内容；另一些方案依赖 TEE（如 SGX），但 TEE 存在广泛的侧信道攻击；还有些方案假设多个不串通的服务器，部署困难且假设脆弱。

2. **搜索准确率低**：现有加密搜索大多只支持关键词搜索（倒排索引），无法捕捉查询的语义意图，远逊于 state-of-the-art 的语义搜索。

3. **加密语义搜索效率差**：少数加密 embedding 搜索方案要么使用 FHE 线性扫描（HERS），开销极大；要么组合多种重量级密码学工具（SANNS），性能不可接受；要么针对公开数据库设计（Tiptoe），不适用于私有数据场景。

核心挑战：将 state-of-the-art 的 graph-based ANN 搜索（HNSW）跑在 ORAM 之上时，HNSW 的多跳图遍历需要大量远程 ORAM 请求，导致带宽和往返延迟极高。一次搜索可能需要获取数千个节点的数据，产生数十到数百次网络往返。

---

## 三、洞察与设计

**关键洞察**：在 HNSW 图遍历中，每一步实际需要访问的邻居节点只是所有邻居中与查询方向一致的一小部分；同时，候选列表中排名靠前的节点高度可能在后续步骤被访问。这两个特性使得可以通过方向过滤大幅减少带宽、通过投机预取大幅减少往返次数，从而将原本不可行的 ORAM 上的图遍历变为实际可用。

基于此洞察，Compass 的架构为：客户端运行搜索算法，服务器仅存储加密的 ORAM 树。三大核心技术：

### 1. Directional Neighbor Filtering（方向性邻居过滤）

客户端本地缓存所有节点的 Product Quantization (PQ) 压缩向量（称为 Quantized Hints，约为原始 embedding 大小的 1%）。在遍历每一步，先在量化空间中计算所有邻居到查询的距离，只从 ORAM 获取最近的 efn 个邻居的全精度坐标，而非全部 M 个邻居。带宽降低 M/efn 倍。

### 2. Speculative Neighbor Prefetch（投机性邻居预取）

借鉴 CPU 投机执行的思路，每次 ORAM 请求不仅获取当前最近候选节点的邻居，还同时获取候选列表中排名前 efspec 个节点的邻居。通过批量 ORAM 请求，将网络往返次数减少 efspec 倍。

### 3. Graph-Traversal Tailored ORAM（图遍历定制 ORAM）

对 Ring ORAM 进行白盒改造：
- **Batching**：将同一搜索步骤的多个 ORAM 请求合并为一次批量请求
- **Multi-hop lazy eviction**：将 ORAM 驱逐操作延迟到查询结束后执行，用户感知延迟大幅降低（1.5–5.6×）
- **节点块设计**：将 embedding 和邻居列表存储在同一 ORAM block 中，避免额外往返
- **Tree-top caching**：缓存 ORAM 树顶部若干层，减少 early reshuffle

---

## 四、实现细节

- 约 5000 行 C++ 代码实现
- 使用 Faiss 库构建 HNSW 索引和 Product Quantization
- 加密使用 AES-256-CBC，哈希使用 SHA-256（通过 OpenSSL EVP）
- ORAM 参数：Z=32（真实块槽位），S=64（dummy 槽位），A=36（驱逐频率）
- 客户端缓存 HNSW 上层（除最后两层外），减少远程访问
- 完整性保护：在 ORAM 树之上构建 Merkle 树，每个 bucket 内再构建二级 Merkle 树，支持单 block 读取时的完整性验证
- 安全性：通过固定搜索步数和 padding 邻居数量来防止泄漏 batch 大小和搜索步数
- 开源：https://github.com/Clive2312/compass

---

## 五、实验结果

**实验环境**：Google Cloud Platform，n2-standard-8（客户端）+ n2-highmem-64（服务器），模拟快速网络（3Gbps/1ms RTT）和慢速网络（400Mbps/80ms RTT）。

**数据集**：

| 数据集 | 维度 | 文档数 | 查询数 |
|--------|------|--------|--------|
| MS MARCO | 768 | 8.8M | 6,980 |
| TripClick | 768 | 1.5M | 1,175 |
| SIFT1M | 128 | 1M | 10,000 |
| LAION | 512 | 100K | 1,000 |

**搜索质量**：Compass 在所有数据集上的 MRR@10 与明文 brute-force embedding search 持平，显著优于 Inv-ORAM（关键词搜索）和 HE-Cluster（同态加密聚类）。

**延迟（慢速网络，用户感知延迟）**：

| 数据集 | 用户感知延迟 (semi-honest) | 用户感知延迟 (malicious) |
|--------|---------------------------|------------------------|
| LAION | 0.28s | 0.60s |
| SIFT1M | 0.57s | 0.60s |
| TripClick | 0.84s | 0.92s |
| MS MARCO | 1.13s | 1.28s |

**与 baseline 对比**：
- 比 naive HNSW+ORAM 快高达 **920×**
- 比 HE-Cluster 和 Inv-ORAM 快数个数量级
- 相比明文 HNSW 约 6–10× 开销

**通信开销**：非驱逐通信（影响用户感知延迟）在最大数据集 MS MARCO 上仅 8.9MB。

**客户端内存**：LAION 5.5MB，SIFT1M 35.8MB，MS MARCO 498.6MB（大规模 web 搜索尚不适用）。

**服务器吞吐**：LAION 数据集在 32Gbps 带宽下达到 436 QPS。

---

## 六、批判性分析

1. **可扩展性瓶颈被轻描淡写**：对于 MS MARCO（8.8M 文档），客户端内存已达 ~500MB，作者承认"not yet scalable for global-scale web searches"，但这也意味着对于企业级私有数据（数千万到数亿文档）同样不可行。论文将这一根本性限制以"留作未来工作"轻松带过。

2. **场景适用性窄**：Compass 定位为"个人用户搜索自己的加密数据"，但个人数据规模通常较小（数万到数十万文档），此时直接在客户端本地建索引可能是更简单的方案。论文虽在 §6.5 讨论了与 client-side index 的对比，但主要从 cold-start 角度论证优势，未充分讨论在持续使用场景下客户端索引的实用性。

3. **延迟对比不完全公平**：与明文 HNSW 的 6–10× 开销看似可接受，但明文 HNSW 延迟通常在毫秒级，而 Compass 在秒级。对于交互式搜索体验，1 秒以上的延迟在某些场景下可能影响用户体验。

4. **ORAM 驱逐的尾延迟**：lazy eviction 将驱逐延迟到查询返回之后，但 MS MARCO 的全延迟（含驱逐）在慢速网络下达 7–8 秒。如果用户连续快速查询，驱逐任务会积压，可能导致 stash 溢出或后续查询延迟飙升，论文未讨论这种并发场景。

5. **安全模型限制**：不隐藏操作类型（search vs insert vs delete），不防护时间侧信道。在实际攻击场景中，操作类型和时间模式本身可泄漏有价值信息（如用户搜索频率模式）。

6. **插入性能**：MS MARCO 上单文档插入需 19.2 秒（慢速网络），对于需要实时索引新文档的场景（如加密邮件）不够实用。

---

## 七、AI Infra / MLSys 视角

1. **加密 RAG 的关键组件**：Compass 可作为 private RAG pipeline 的检索模块，与 secure inference（如 MPC/FHE 推理）结合实现端到端加密的 RAG。随着 RAG 成为 LLM 应用标准范式，加密 RAG 具有显著的商业需求（医疗、法律、金融领域）。

2. **量化技术的跨领域借鉴**：Quantized Hints 使用 Product Quantization 将 embedding 压缩到 1% 大小作为方向性过滤依据，这种"用低精度表示做粗筛、用全精度做精确计算"的两阶段思路，与 AI Infra 中常见的 mixed-precision 策略异曲同工，可以迁移到分布式向量检索系统的网络优化中。

3. **投机执行在 AI 系统中的推广**：Speculative Neighbor Prefetch 将 CPU 投机执行的思想应用到图搜索中。类似思路可应用于分布式 KV cache 访问、远程 embedding 检索等 AI 推理系统中网络延迟占主导的场景。

4. **可跟进方向**：
   - 将 Compass 的技术扩展到更大规模（10M+ 向量），探索分布式 ORAM 或层级化 ORAM 减少客户端内存
   - 研究 GPU 加速的加密向量检索，利用 GPU 的并行能力加速 PQ 距离计算和 ORAM 操作
   - 探索在 confidential computing（如 CVM）中结合 Compass 的 ORAM 技术，实现更强安全保证的推理服务

---

## 八、总结

Compass 首次实现了在不泄漏访问模式、不依赖可信硬件的条件下，达到 state-of-the-art 明文语义搜索精度的加密搜索系统。其核心贡献是将 HNSW 图遍历与 Ring ORAM 进行白盒协同设计，通过方向性邻居过滤、投机预取和延迟驱逐三项技术，将加密语义搜索的用户感知延迟降至秒级。系统适用于个人加密数据搜索和加密 RAG 场景，但在大规模数据（数百万文档以上）时客户端内存开销仍是主要限制。
