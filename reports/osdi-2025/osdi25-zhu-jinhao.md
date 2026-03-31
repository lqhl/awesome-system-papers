# Compass: Encrypted Semantic Search with High Accuracy

**作者**：Jinhao Zhu（UC Berkeley）、Liana Patel（Stanford University）、Matei Zaharia（UC Berkeley）、Raluca Ada Popa（UC Berkeley）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会），2025 年 7 月，波士顿
**链接**：https://www.usenix.org/conference/osdi25/presentation/zhu-jinhao
**源文件**：[osdi25-zhu-jinhao.pdf](../../papers/osdi-2025/osdi25-zhu-jinhao.pdf)

---

## 一、背景

随着 WhatsApp、iCloud、Signal 等服务普及端到端加密，用户数据以加密形式存储在云端。然而，**加密数据上的搜索**仍然是悬而未决的难题：现有工作要么泄露访问模式（leaky search），要么依赖可信硬件（TEE），要么仅支持低精度的关键词检索。

与此同时，现代搜索系统（Google、Bing、Elasticsearch、Mac Spotlight）早已转向**语义搜索（Semantic Search）**：将查询和文档映射到高维向量空间（embedding），通过向量相似度匹配语义，而不是字符串匹配关键词。语义搜索在问答、图像、音视频检索上的准确率远超传统关键词搜索。图-based 的近似最近邻（ANN）算法，尤其是 HNSW（Hierarchical Navigable Small World），已是语义搜索的事实标准索引。

**如何在加密向量数据上高效、准确、安全地执行语义搜索**，是本文要解决的核心问题。

---

## 二、要解决的问题

### 2.1 现有方案的安全缺陷

- **泄漏访问模式的方案**：大量加密搜索工作（DSSE、OBI 等）允许服务器观察访问模式，而 leakage-abuse 攻击可借此重建查询内容或数据分布。
- **依赖可信硬件的方案**（SGX 等）：硬件 enclave 存在广泛的侧信道攻击（Spectre、SGX 缓存攻击），无法视作真正安全。
- **多服务器信任模型**：假设多个逻辑服务器中至少一个诚实，但实际部署中攻击者往往能同时攻陷所有服务器。

### 2.2 现有方案的精度缺陷

现有加密搜索大多仅支持**关键词搜索**（inverted index），不能理解语义，在问答场景下准确率远低于现代系统。少数支持语义搜索的工作（HERS、SANNS）要么用 FHE 做线性扫描（开销极大），要么结合多重重量级密码原语，性能不可接受。

### 2.3 高效性难题

HNSW 的图遍历天然依赖**多跳、数据驱动的本地访问**。在远程 ORAM 后端上做 HNSW 搜索时：
- 每个候选节点需要获取其所有邻居的 embedding 来计算距离；
- HNSW 每个节点有数十至数百个邻居，整个搜索需访问数千节点；
- 朴素方案需要数十至数百次 ORAM 往返，延迟高达数百秒。

---

## 三、核心设计

Compass 的架构是**客户端执行搜索逻辑，服务器仅提供加密存储**。Embedding 和 HNSW 索引以加密形式存储在不可信服务器上，客户端通过 Oblivious RAM（Ring ORAM）访问数据，服务器无法推断访问模式。

Compass 提出三项关键技术协同解决效率问题：

### 3.1 Directional Neighbor Filtering（方向性邻居过滤）

**核心思想**：在 HNSW 图遍历的每一步，不需要获取当前节点的所有邻居，只需获取与查询方向"一致"的邻居子集。

- 客户端本地缓存全部 embedding 的**量化版本（Product Quantization hints）**，大小约为原始数据的 1%；
- 利用量化 hints 估算每个邻居与查询的距离，选出距离最近的 `efn` 个邻居发起 ORAM 请求；
- 过滤掉方向相反的邻居，显著减少带宽消耗，同时基本不损失准确率。

### 3.2 Speculative Neighbor Prefetch（推测性邻居预取）

**核心思想**：借鉴 CPU 预取机制，在当前批次的 ORAM 请求尚未返回前，基于量化 hints 推测下一步可能访问的节点，将多跳访问合并为一次批量 ORAM 请求。

- 每次从候选集中提取 `efspec` 个最优候选，遍历其未访问邻居（集合 E₂）；
- 从 E₂ 中选出最优的 `efspec × efn` 个节点（集合 E₃），批量发起 ORAM 请求；
- 将多轮 ORAM 往返压缩为 `⌈ef/efspec⌉` 轮，大幅减少 round trip 次数。

### 3.3 Graph-Traversal Tailored ORAM（图遍历定制 ORAM）

**核心思想**：将 HNSW 遍历模式与 Ring ORAM 协议做白盒联合设计，而非简单叠加。

- **Lazy Eviction（延迟驱逐）**：标准 Ring ORAM 每次访问后立即做 eviction，但 Compass 将所有 eviction 延迟到查询结束后统一执行，把 eviction 的延迟从用户可感知路径移出（在 RAG pipeline 中可与 LLM 推理并行）；
- **批量 ORAM 访问**：将 E₃ 中的多个节点合并为一次批量 Ring ORAM 请求，极大减少往返次数（实测 12–20× 延迟降低）；
- **Stash 排序优化**：延迟驱逐导致 stash 增大，通过按 path ID 对 stash 中的 block 排序，将查找复杂度从 O(ZN) 降至 O(log N)。

### 3.4 安全性保障

- 基于 Ring ORAM 的访问模式隐藏 + Merkle 树（双层结构）完整性保护；
- 安全性定义：IND-based 不可区分性，攻击者既无法区分查询，也无法在不被检测的情况下篡改结果；
- 假设碰撞抗性哈希函数和 IND-CCA2 安全的加密方案，Compass 满足定理 1 的安全界。

---

## 四、实现细节

- 约 **5,000 行 C++ 代码**；
- HNSW 索引构建和 Product Quantization 使用 **Faiss 库**；
- 加密：AES-256-CBC；哈希：SHA-256（via OpenSSL EVP）；
- HNSW 图的上层（除最后两层外）全部缓存在客户端，避免频繁 ORAM 访问热点节点；
- Ring ORAM 参数：Z=32, S=64, A=36（略微偏离带宽最优值以减少 early reshuffle 和 round trip）；
- 量化 hints 大小约为原始 embedding 的 1%；
- 插入复杂度（poly）对数级，与 HNSW 原本一致；
- 代码开源：https://github.com/Clive2312/compass

---

## 五、实验结果

**实验平台**：Google Cloud Platform，客户端：n2-standard-8（8 vCPU, 32 GB），服务端：n2-highmem-64（64 vCPU, 512 GB）；通过 Linux tc 模拟两种网络：fast（3 Gbps, 1 ms RTT）和 slow（400 Mbps, 80 ms RTT）。

**数据集**：

| 数据集 | 向量维度 | 文档数 | 语义类型 |
|--------|---------|--------|---------|
| MS MARCO | 768 | 8,841,823 | 文本（通用问答） |
| TripClick | 768 | 1,523,871 | 文本（医疗健康） |
| SIFT1M | 128 | 1,000,000 | 图像特征 |
| LAION | 512 | 100,000 | 图像-文本 |

**搜索质量与延迟（MRR@10，slow 网络）**：

| 系统 | 准确率 | 用户感知延迟 |
|------|--------|------------|
| Compass | ≈ Plaintext-HNSW（brute-force embedding 上限） | 0.57–1.28 s |
| Plaintext-HNSW（不安全基线） | 最优 | 快 6–10× |
| HE-Cluster | 在 TripClick 上低于 TF-IDF | 比 Compass 慢数量级 |
| Inv-ORAM（关键词搜索） | 远低于 Compass | 需更大 list 才能接近 TF-IDF 精度 |
| BM25 / TF-IDF | 低于语义搜索 | — |

**通信开销**（每次查询，slow 网络）：

| 数据集 | 非驱逐通信量 | Round trips | vs HE-Cluster |
|--------|------------|------------|--------------|
| LAION | 0.7 MB | 8 | 12.5× 更少 |
| SIFT1M | 1.1 MB | 8 | 14× 更少 |
| MS MARCO | 8.9 MB | 9 | 大幅更少 |

**客户端内存**（LAION：5.5 MB；SIFT1M：35.8 MB；MS MARCO：498 MB）。

**消融实验**：
- 去掉 lazy eviction：延迟增加 1.5–5.6×；
- 去掉批量 ORAM（vanilla Ring ORAM）：延迟增加 12–20×；
- 方向性过滤（efn）和推测预取（efspec）各贡献显著的延迟降低，直至参数过小时精度开始下降。

---

## 六、批判性分析

### 6.1 有限的适用场景

论文声称面向"个人用户在云端搜索自己的私密数据"场景，但 MS MARCO 拥有 880 万文档、需要 498 MB 客户端内存——这已不是轻量级的个人数据场景，而更接近企业知识库。文中对"个人数据"的界定前后不一致：一方面说 client memory 很小（5.5 MB for LAION），另一方面又展示 500 MB 的 MSMARCO 客户端内存，并称"这是我们留给未来工作的局限性"。

### 6.2 安全模型的刻意回避

Compass **不隐藏操作类型**（search/insert/delete）。论文轻描淡写地说"我们不尝试隐藏操作类型"，但操作类型本身在某些场景下就是敏感信息（例如，频繁的 delete 可能暗示用户正在清理某类内容）。此外，论文明确不保护基于时序的侧信道攻击，而在真实部署中，请求时序往往是重要攻击面。

### 6.3 基线对比不够公平

HE-Cluster 是论文自己实现的 Tiptoe 扩展，并不是已发表的竞争系统；Inv-ORAM 代表的是关键词搜索，与语义搜索本质上是不同的能力。对于最具竞争力的近期工作 SANNS 和 Panther，论文仅在 Related Work 中定性描述，未做量化对比，也未说明为何无法直接比较（例如代码不开源、配置不同等）。

### 6.4 量化 hints 的信息泄露风险

客户端缓存的量化 hints 是 embedding 的有损压缩。论文将其视为"公共参数"的一部分，认为不影响安全性。然而，量化 hints 本质上是数据内容的压缩表示——若客户端被攻击（如移动设备丢失），这些 hints 可能泄露部分数据分布信息。论文对此未做讨论。

### 6.5 插入和删除的实用性不足

MS MARCO 在 slow 网络上插入一条文档需要 **19.2 秒**。对于文档持续更新的动态场景（如实时邮件、笔记应用），这一开销几乎不可接受。删除操作同样昂贵。论文对此的处理是简单说"留给未来工作"，但这是实际部署中的核心问题。

### 6.6 Fault Tolerance 设计的安全漏洞

论文在 §4.11 坦承：若客户端本地磁盘损毁，恢复依赖服务端提供的状态和日志，而恶意服务器可提供过时状态——此时 Compass 的安全保证失效。这与论文前文声称的"against a fully compromised server"有明显矛盾，应在安全模型中显式说明这一限制条件。

---

## 七、AI Infra / MLSys 视角

### 7.1 对私有 RAG 系统的直接价值

论文明确将 Compass 定位为**私有 RAG 系统的检索层**（retrieval in encrypted RAG database）。当前 RAG 系统（如 LangChain + Pinecone/Weaviate）将用户文档明文存储在向量数据库中，存在严重的数据隐私风险。Compass 提供了一个可以与现有推理隐私技术（BOLT、Delphi 等）结合的检索组件，构成端到端的私有 RAG pipeline。

### 7.2 ORAM 与向量索引的协同设计方法论

Compass 的核心方法论——**将向量索引的访问模式特征注入 ORAM 协议设计**（白盒协同）——对 AI 系统领域有普遍借鉴价值。未来可将类似思路推广到：
- **GPU 上的安全推理**：将模型权重存于加密内存，推理时按 attention pattern 做 ORAM 访问；
- **安全 KV Cache**：在 multi-tenant 推理服务中，通过 ORAM 隐藏 KV cache 的访问模式，防止跨用户的旁路推断。

### 7.3 量化 hints 的设计模式

"在客户端缓存 1% 大小的量化压缩以加速远程访问判断"这一设计，类似于 AI 推理系统中的**推测解码（Speculative Decoding）**：用廉价的本地信息驱动远程高代价操作的选择，从而减少实际触发次数。这一模式值得在其他带宽敏感的分布式 AI 系统中探索。

### 7.4 值得跟进的研究方向

- **动态 embedding 场景的支持**：当 embedding 模型升级或 fine-tuning 时，如何在不暴露访问模式的情况下批量更新加密向量索引？
- **多用户共享的加密向量数据库**：Compass 目前每个用户维护独立索引。如何在保持访问模式隐私的前提下支持多用户共享同一语料库的 semantic search（如企业知识库）？
- **与 confidential computing 的结合**：Compass 刻意回避了 TEE，但若结合 AMD SEV 或 Intel TDX（VM 级别的机密计算，侧信道风险低于 SGX），可能在安全性与性能之间找到更好的平衡点。

---

## 八、总结

Compass 是首个在**强安全保证**（全恶意服务器、无可信硬件、无访问模式泄漏）下实现**语义搜索准确率与明文系统齐平**的加密搜索系统。其核心贡献是将 HNSW 图遍历与 Ring ORAM 进行白盒协同设计，通过方向性邻居过滤、推测性预取、延迟驱逐三项技术，将朴素方案百秒级的延迟压缩至秒级。主要局限在于：客户端内存开销随数据规模增长不可忽视（大数据集需 500 MB+），动态操作（插入/删除）性能较差，安全模型中存在若干隐式假设（客户端磁盘完整性、操作类型可见）。最适用于中小规模个人数据或企业代理模型场景下的私有语义检索，以及私有 RAG 系统的检索层。
