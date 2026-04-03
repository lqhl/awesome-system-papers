# PathWeaver: A High-Throughput Multi-GPU System for Graph-Based Approximate Nearest Neighbor Search

**作者**：Sukjin Kim, Seongyeon Park, Si Ung Noh, Junguk Hong, Taehee Kwon, Hunseong Lim, Jinho Lee（Seoul National University）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/kim
**源文件**：[[atc2025-kim.pdf]]

---

## 一、背景

近似最近邻搜索（ANNS）是推荐系统、自然语言处理、计算机视觉和信息检索等领域的核心操作。随着数据集规模持续增长（从百万级到十亿级向量），精确的 k-NNS 因维度灾难而变得不可行，ANNS 成为实际部署的标准选择。在各类 ANNS 方法中，基于图的方法（如 HNSW、CAGRA、GGNN）因其能有效表达数据点间的邻近关系、在较少的节点访问下获得高精度而受到广泛关注。

GPU 的大规模并行能力为 ANNS 提供了显著加速，但单 GPU 显存有限，无法容纳大规模数据集。现有多 GPU 方案简单地将数据分片（sharding），每个 GPU 独立搜索，扩展效率低下。同时，GPU 上的图搜索存在三个核心瓶颈：随机起始点大量浪费、每次迭代的距离计算开销过大、多 GPU 扩展性差。

---

## 二、要解决的问题

1. **多 GPU 扩展效率低**：现有 sharding 方法将数据集分到多个 GPU，每个 GPU 对所有 query 独立搜索。由于每个分片的搜索迭代次数不会随分片大小线性减少，总迭代次数反而增加。实测 4 GPU 下 CAGRA 仅获 1.39× 加速（扩展效率约 35%），GGNN 约 1.7×（约 43%）。

2. **随机初始点浪费严重**：搜索从大量随机采样点开始，但由于 beam search 的特性，绝大多数初始点的后续探索在前几轮就被丢弃，只有少数最优起点的后代存活，造成大量无效计算和内存访问。

3. **每次迭代中无效距离计算过多**：访问一个图节点需要计算其所有邻居（通常几十个）的 L2 距离，但超过 80-86% 的被访问节点最终被丢弃，从未进入 top-k 结果，导致大量无意义的高维向量读取和距离计算。

---

## 三、洞察与设计

**关键洞察**：在 sharding 多 GPU 搜索中，各分片看似独立的搜索操作实际上可以通过共享中间搜索结果来优化——前一个分片找到的接近 query 的节点，可以作为下一个分片搜索的更优起始点，从而大幅减少后续分片的搜索迭代。此外，图中节点到 query 的方向信息是一个轻量但有效的代理指标，可以在不做完整 L2 距离计算的情况下过滤掉大部分无关邻居。

基于上述洞察，PathWeaver 提出三个核心设计：

### 1. Pipelining-based Path Extension（流水线式路径扩展）

将数据集随机分片到 N 个 GPU，各自构建独立的近邻图。关键创新在于：为相邻分片之间的每个节点建立单向跨分片边（每个节点连接到相邻分片中最近的节点），形成环形拓扑。搜索时，一个 query 在第一个 GPU 上完成搜索后，将其最优结果（top-1 节点）通过跨分片边映射到下一个 GPU，作为新的搜索起点。由于起点已接近 query，后续 GPU 的搜索迭代次数大幅减少。所有 GPU 以流水线方式并行处理不同的 query batch。

### 2. Ghost Staging（幽灵阶段）

流水线设计的瓶颈在于第一阶段仍需从随机点开始搜索。Ghost staging 在每个分片前添加一个小型辅助分片：从原始分片中随机采样少量"幽灵节点"，构建轻量级网络，并与原始图建立跨层边。搜索时先在幽灵图上快速定位接近 query 的区域（因为节点少，每一步跳跃覆盖范围更大），然后通过跨层边进入原始图继续精细搜索。实验表明极低采样率（如 0.0001）即可获得最佳效果。

### 3. Direction-Guided Selection（方向引导选择）

在每次搜索迭代中，不再对当前节点的所有邻居都做完整 L2 距离计算。预处理阶段为每条边生成压缩的方向位向量（sign bits of vector differences）。运行时计算 query 到当前节点的方向位向量，与邻居的方向位向量做比对（XOR + popcount），仅对方向最匹配的 top-n 个邻居执行完整距离计算。搜索末期进入 cool-down 阶段（默认最后 30% 迭代）取消过滤以保证精度。

---

## 四、实现细节

- 基于 CAGRA 搜索 kernel 实现，采用 query-per-thread-block 方式，thread block 大小等于 warp 大小（32 线程）
- 跨分片边表在图构建阶段预计算，每个节点在相邻分片中做一次 ANNS 查询取 top-1 结果存入 lookup table
- 流水线通信只传输 query 的 top-1 结果索引，通信量为 Q × b_idx（极小）
- 方向位向量存储为 uint32 压缩格式，运行时用 `__shfl_xor_sync()` 做 warp 内高效 shuffle，`__popcll()` 计数差异位
- Ghost staging 辅助分片和方向位表均在 CPU 上多线程预计算
- 跨分片边构建、幽灵节点连接和方向位表生成的额外图构建开销：单 GPU 场景 <10%，多 GPU 场景 <15%
- 代码开源：https://github.com/AIS-SNU/PathWeaver

---

## 五、实验结果

**实验平台**：4× NVIDIA RTX A6000 GPU，AMD EPYC 9124 16-Core CPU，2 GPU 通过 NVLink Bridge 连接，另一对通过 PCIe switch 连接。Ubuntu 22.04，CUDA 12.1。

**数据集**：

| 数据集 | 维度 | 规模 | 用途 |
|--------|------|------|------|
| Sift-1M | 128 | 1M | 单 GPU |
| Gist-1M | 960 | 1M | 单 GPU |
| Deep-10M | 96 | 10M | 单/多 GPU |
| Wiki-10M | 768 | 10M | 多 GPU |
| Deep-50M | 96 | 50M | 多 GPU |

**主要结果（95% Recall@10）**：

| 场景 | 对比基线 | 加速比 |
|------|----------|--------|
| 多 GPU（geomean） | CAGRA w/ Sharding | 3.24× |
| 多 GPU（Wiki-10M） | CAGRA w/ Sharding | 5.30× |
| 单 GPU（geomean） | CAGRA | 3.43× |
| 4 GPU 扩展效率 | — | 62%（vs 基线 35-43%） |

**消融实验**：PPE（流水线路径扩展）、GS（幽灵阶段）、DGS（方向引导选择）三个组件逐步叠加均带来一致加速，且在不同数据集上趋势一致。

**其他发现**：
- L2 距离计算占搜索时间 80-95%，PathWeaver 主要通过减少距离计算次数获得加速
- 方向引导选择丢弃 70% 邻居时精度仅下降 0.003（随机丢弃下降 0.038）
- 幽灵节点采样率 0.0001 时 QPS 比 0.1 高 1.39×
- 通信开销几乎可忽略（J×v 通常超过 10⁴，远大于通信量）

---

## 六、批判性分析

1. **硬件平台局限性**：全部实验仅在 4 GPU 的单节点上完成，且只有 2 GPU 间有 NVLink，另一对通过 PCIe 连接。论文声称的流水线扩展性在更大规模（8/16/32 GPU 或跨节点）下是否成立未经验证。环形拓扑在跨节点场景下的通信延迟可能显著增加。

2. **基线公平性存疑**：CAGRA 原生不支持多 GPU，论文自行扩展了 sharding 版本作为基线。这个"naïve sharding"是否代表了 CAGRA 团队可能采用的最优多 GPU 策略值得商榷。同时缺少与 FAISS 等工业级多 GPU 向量搜索库的对比。

3. **Query batch size 设定**：多 GPU 实验使用 60,000 的 batch size 以"充分利用多设备"。这偏向吞吐量场景，但实际向量数据库的在线查询通常是小 batch 甚至单条查询，低延迟场景下流水线填充效率可能大打折扣。

4. **方向引导选择的维度敏感性**：sign bit 压缩将每个维度量化为 1 bit，在低维空间（如 Deep-10M 的 96 维）信息损失相对可控，但在极高维空间下 sign bit 的区分度如何变化缺乏分析。Gist-1M（960 维）虽然测试了但主要在单 GPU 场景。

5. **静态图假设**：PathWeaver 只支持静态图，Discussion 中对动态更新的讨论停留在定性层面（"小量插入可以增量更新"），没有任何实验支撑。实际向量数据库需要频繁插入/删除，这是一个严重的实用性限制。

6. **图构建开销被淡化**：虽然声称额外开销 <15%，但图构建本身已经是一个昂贵操作。论文没有报告绝对的图构建时间，只给了相对百分比，无法判断实际耗时。

---

## 七、AI Infra / MLSys 视角

1. **RAG/向量检索加速**：PathWeaver 的多 GPU ANNS 加速直接适用于 LLM 推理中的 RAG pipeline。当向量库规模达到数千万到数亿级别时，检索延迟成为端到端延迟的重要组成部分。PathWeaver 的流水线路径扩展思路可以集成到 FAISS/Milvus 等向量数据库的 GPU 后端中。

2. **方向引导选择的启发**：用低成本的方向位比较（XOR + popcount）预筛选候选项，再对筛选后的少量候选做精确计算——这种"粗筛+精排"的两阶段模式在 AI Infra 中有广泛应用场景，如 KV cache eviction 策略（用 attention score 的近似值快速判断哪些 token 值得保留）、MoE routing 的专家预选等。

3. **跨分片流水线通信模式**：Pipelining-based path extension 的核心思想——在分布式搜索中传递少量中间结果以引导后续搜索——可以推广到分布式 embedding lookup、分布式 MoE 推理中的 token routing 等场景。关键 insight 是通信量极小（只传 top-1 索引）但收益巨大（减少大量冗余计算）。

4. **值得跟进的研究方向**：
   - 将 PathWeaver 与量化技术（PQ/SQ）结合，支持更大规模数据集的多 GPU ANNS
   - 在 GPU 集群（跨节点）场景下验证流水线扩展性，探索 NCCL/RDMA 下的最优拓扑
   - 将 direction-guided selection 思路迁移到 attention 计算中，用方向位快速估计 attention score 以加速 sparse attention

---

## 八、总结

PathWeaver 是一个面向大规模图 ANNS 的多 GPU 加速框架，通过三个互补的优化——流水线跨分片路径扩展（减少冗余搜索迭代）、幽灵阶段（优化初始搜索点）和方向引导选择（裁剪无效距离计算）——在 95% recall 下实现了 3.24× 的多 GPU 加速和 3.43× 的单 GPU 加速。系统设计干净、各组件正交、实现基于成熟的 CAGRA kernel。主要局限在于仅支持静态图、实验规模限于 4 GPU 单节点、缺少低延迟/小 batch 场景的评估，以及与工业级向量数据库的集成验证。
