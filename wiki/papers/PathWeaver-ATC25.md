---
type: paper
name: PathWeaver
full_title: "PathWeaver: A High-Throughput Multi-GPU System for Graph-Based Approximate Nearest Neighbor Search"
authors: [Sukjin Kim, Seongyeon Park, Si Ung Noh, Junguk Hong, Taehee Kwon, Hunseong Lim, Jinho Lee]
venue: ATC
year: 2025
tags: [anns, vector-search, multi-gpu, graph-search, cagra]
source_pdf: "[[atc2025-kim.pdf]]"
source_md: "[[atc2025-kim]]"
---

# PathWeaver: A High-Throughput Multi-GPU System for Graph-Based Approximate Nearest Neighbor Search (ATC 2025)

> **一句话总结**：在「多 GPU sharding 把额外 GPU 当内存扩展、每 shard 独立从头搜导致 scale efficiency 极低」这一观察下，PathWeaver 用跨 shard 流水线 path extension、ghost staging 与 direction-guided selection 减少 L2 距离计算与迭代次数，在 95% recall@10 下相对 CAGRA/GGNN 平均 3.24×、最高 5.30× 加速，4 GPU scale efficiency 约 62%。

## 问题与动机

[[Vector-Search]] 与 [[ANNS]] 是推荐、检索、[[RAG]] 等场景的基础设施；graph-based 方法（[[HNSW]]、CAGRA、GGNN）因高 recall 与可扩展性成为主流。单 GPU 方案（尤其 CAGRA）已把距离计算推到 GPU 极限，但十亿级向量索引无法放进单卡显存，迫使系统走向多 GPU。

现有多 GPU 做法几乎清一色 **dataset sharding**：随机切分数据、每 GPU 建独立 proximity graph、对每个 query 在每个 shard 上独立 beam search，最后在 CPU 做 top-k reduce（GGNN 原生支持；论文将 CAGRA 扩展为「CAGRA w/ Sharding」）。作者 claim 这种设计把多 GPU 当成「显存容量倍增器」，而非「吞吐倍增器」——每个 query 要在每个 shard 重复完整搜索路径，shard 越多 total iteration 反而上升，scale efficiency 崩塌。

论文进一步指出两个单 GPU 也存在的微观浪费：（1）beam search 从大量随机起点出发，绝大多数邻居几轮内被丢弃；（2）每次扩展 priority queue 都要对度数约 64 的全部邻居算 L2 距离，但 80%+ 访问最终被丢弃。测量显示 L2 距离计算占搜索时间 80%–95%（Fig. 2），因此核心优化目标是 **减少迭代次数 i 与每轮考察邻居数**，而非再堆更多 GPU 做重复劳动。

## 关键观察 / 隐含假设

- **观察 1：Sharding 的 total iteration 随 GPU 数近似线性增长，scale efficiency 仅 35%–43%**
  - **依赖假设**：数据集随机均匀切分、每 shard 独立建图、query 必须在每个 shard 上完整搜索后才能 reduce；图具有 reachability/convexity，局部搜索迭代数与 shard 规模非线性下降。
  - **可能失效场景**：若 shard 边界与向量聚类结构强相关（非随机切分），或图质量差导致每 shard 收敛极慢，iteration 增长模式可能不同；论文未测 skewed / filtered ANNS workload。
- **观察 2：>80% 的邻居访问与 L2 距离计算最终被丢弃，从未进入 top-k**
  - **依赖假设**：proximity graph out-degree 固定为几十（实验用 64）；beam search 的 priority queue 能快速淘汰远距离点；丢弃比例在 Sift/Gist/Deep 等标准 benchmark 上稳定。
  - **可能失效场景**：高维稀疏向量、非 L2 度量、或需要极高 recall（>99%）时，过早剪枝或方向过滤可能显著伤 accuracy；论文主要锚定 95% recall@10。
- **观察 3：相邻 shard 间存在可预计算的「最近邻桥接点」，可把上一 shard 的搜索结果作为下一 shard 的高质量起点**
  - **依赖假设**：随机 sharding 后，任意节点 u 在相邻 shard 中的最近邻 I(u) 仍接近 query 方向；环形单向 pipeline 下通信量仅为 Q×index_bytes，远小于 Q×I×J×d 的内存访问。
  - **可能失效场景**：数据分布高度聚类且 shard 边界切断簇时，inter-shard edge 质量下降，后续 stage 收益减弱；多 tenant 动态插入导致 shard 失衡时桥接表需频繁重建。
- **假设 1：Sign-bit 方向表足以在 cool-down 前安全过滤大部分「方向偏离」邻居**
  - **证据强度**：**中**——在 Sift/Deep 上 discarding ratio 0.7 时 recall 降幅 ≤0.003，优于 random discarding（≤0.038），但依赖图 convexity 在误删时通过增加迭代补偿而非掉 recall；高维 Gist-960 上方向压缩误差更大，论文未单独压力测试。

## 核心方法

PathWeaver 在 CAGRA search kernel（query-per-threadblock、warp 级 bitonic sort、forgettable hash）上叠加三项机制，均直接回应上述观察。

**Pipelining-based Path Extension（PPE）**：sharding 建图后，对每个节点 u∈G_i 预计算到相邻 shard G_{(i+1)%N} 的最近邻 I(u)，形成环形单向 inter-shard edge。搜索时 GPU i 处理 |Q|/N 的 query chunk，局部收敛后取局部 top-1（可调，默认 1 以最小化通信）经 I(z) 延伸到下一 GPU 继续搜；所有 GPU 流水线轮转直到每块 query 走完 N 个 stage，再 CPU reduce。这把「每 shard 独立从头搜」变成「跨 shard 延续搜索路径」，显著降低后续 stage 迭代（Deep-10M 上 baseline 18 轮达 0.90 recall，PathWeaver 14 轮）。通信仅为 stage 间传递索引，论文量化其相对 L2 内存访问可忽略（Section 6.4）。

**Ghost Staging（GS）**：PPE 的第一 stage 仍无 prior result，成为流水线瓶颈（Deep-50M 上 first stage 占 31%）。GS 在每个 shard 随机抽样极小比例节点建 lightweight ghost graph，并连回主图；搜索先在 ghost 层几步定位近 query 的 hub，再下沉主图。本质是 **post-build hierarchical entry**，不同于 [[HNSW]] 在构图时多层插入——目标仅是更好的 entry point，不改动主图 reachability。采样率 0.0001 即可带来 1.39× QPS 提升（Sift-1M），说明 ghost 层可极小。

**Direction-Guided Selection（DGS）**：离线为每条边存源节点到邻居差向量的 sign-bit 压缩表；每轮对当前节点，计算 query 方向 sign，与邻居 direction sign 做 XOR popcount 排序，只选 top-n 做 L2 距离，最后 30% 迭代 cool-down 全量计算以保 accuracy。这是 **query-dependent dynamic pruning**，区别于 CAGRA 构图期 static edge pruning。

实现细节（inter-shard lookup 预计算、ghost 连接、uint32 packed sign table、`_shfl_xor_sync` warp 内处理）见 [[atc2025-kim]] / [[atc2025-kim.pdf]]。

## 设计取舍

- **取舍 1：环形单向 pipeline + 每 query 只传 top-1**——换取极低 inter-GPU 通信与实现简洁，但 pipeline depth 固定为 GPU 数，且 first stage 仍需 GS 补救；双向或多跳桥接可能更好但通信与建图成本上升。
- **取舍 2：DGS 用 1-bit 方向近似而非完整距离预筛**——大幅削减高维向量读取，但存在误删候选风险，靠 cool-down phase 与图 convexity 兜底；random discarding 在同等比例下 recall 掉 0.038，说明方向信息是关键。
- **取舍 3：基于 CAGRA 图构建，额外预处理（inter-shard edge、ghost、direction table）**——搜索路径与 CAGRA 兼容、baseline 公平，但绑定 CAGRA 图质量与 out-degree=64 设定；graph build 开销在 Deep-50M 上达 15%，小数据集 <10%。
- **边界条件**：在 **多 GPU + 大 batch（60k queries）+ 95% recall@10** 的高吞吐离线/批检索场景最优雅；单 GPU 仍受益于 GS+DGS（3.43× vs CAGRA）。Wiki-768 维等宽向量场景 QPS 降一个数量级，DGS 收益相对更突出。动态更新、filtered search、在线小 batch 低延迟场景论文仅讨论未实现。

## 实验与结果

- **主结果（4× RTX A6000，2 对 NVLink）**：95% recall@10 下相对最佳 baseline CAGRA w/ Sharding **3.24× geomean QPS**，Wiki-10M 最高 **5.30×**；88%–92% recall 区间 **3.36×**。
- **多 GPU scale**：1→4 GPU 最快配置 **2.47×** 加速（**62% scale efficiency**），比 CAGRA/GGNN sharding 的 35%–43% 高约 17 个百分点。
- **单 GPU**：GS+DGS 相对 CAGRA **3.43×**；相对 CPU [[HNSW]]（64 线程）优势更大（Fig. 10）。
- **Ablation（Deep-10M/50M, Sift-1M）**：PPE、GS、DGS 逐级叠加均一致提速；单 GPU 上 GS 贡献最大（整段搜索等价于「first stage」）。
- **Breakdown**：优化后 L2 距离占比仍主导但绝对时间大幅下降；inter-GPU 通信在 multi-GPU 总时间中可忽略；DGS 略增 kernel 杂项（direction lookup）。
- **Build overhead**：单 GPU 目标数据集 <10%；Deep-50M multi-GPU 最高 15%，ghost 连接开销可忽略。

## Critical Analysis

### 论证链条

观察（sharding iteration 膨胀 + 80% 距离计算浪费 + L2 占 95%）→ 三机制分别减少跨-shard 重复迭代、改善 entry point、削减每轮邻居考察 → QPS-recall 曲线全面占优，ablation 与 iteration-recall 曲线（Fig. 13）支持「更少迭代达到同等 recall」的中间 claim。链条在 **批处理高吞吐 ANNS** 上闭合较好。

薄弱环节：（1）把 62% scale efficiency 表述为「显著改善」仍远离线性扩展，且实验仅限 4 GPU；（2）最强 baseline 是作者自扩展的 CAGRA sharding，而非工业级多节点系统（如 Faiss multi-GPU、分布式 DiskANN）；（3）accuracy claim 集中在 recall@10，未覆盖 filtered / range ANNS 等生产变体。

### 假设压力测试

- **随机 sharding + 静态图**：若生产按语义分片或热度分片，inter-shard edge 质量与负载均衡可能下降——**论文未证明，需 trace-driven 测量**。
- **方向过滤**：对 960 维 Gist 仅报告 QPS 变慢（维度主导），未单独给出 DGS 的 recall sensitivity；非 L2 或非欧氏嵌入（内积、cosine、learned metric）下 sign-bit 方向语义弱化——**可能失效**。
- **Batch size 依赖**：multi-GPU 用 60k query batch 填满流水线；在线小 batch 时 pipeline 气泡与跨 GPU 同步可能侵蚀收益——**论文未覆盖**。
- **硬件拓扑**：仅 4×A6000 + 部分 NVLink；全 PCIe 或 8+ GPU 集群上通信与 reduce 瓶颈未验证。

### 实验可信度

- **Benchmark**：Sift/Gist/Deep/Wiki 是 ANNS 社区标准集，但偏「均匀批量检索」；缺少真实 recommendation / RAG trace 的 query 分布与 k 值变化。
- **Baseline 公平性**：统一 out-degree 64、CAGRA 构图算法，较公平；GGNN 作为唯一原生 multi-GPU 竞品偏少；未与 BANG、FusionANNS 等 CPU-GPU 混合方案比（定位不同但是大规模 ANNS 相关竞品）。
- **Ablation**：PPE/GS/DGS 正交叠加清晰；DGS vs random discarding 对照有力。
- **Metrics**：QPS + recall 覆盖吞吐-精度权衡，但 **无 tail latency、无 per-query latency 分布、无成本/瓦特数**。

### 系统性缺陷

- **动态更新**：Section 6.2 讨论增量 insert/delete 策略，但 **无实验**；inter-shard edge 与 direction table 在大量更新后是否需全量重建未量化。
- **故障与隔离**：多 GPU pipeline 中任一 stage 失败对整批 query 的影响、checkpoint 恢复——**论文未讨论**。
- **可观测性 / 调参**：ghost 采样率、cool-down 比例、top-n discarding 等多超参，生产 auto-tuning 复杂度——**论文未讨论**。
- **尾延迟**：高 batch 优化对延迟敏感在线服务的外推风险高——**论文未讨论**。

## 局限与 Future Work

- **局限 1**：仅评估 **静态索引 + 批量 query**；动态图维护、删除累积、shard 负载失衡只有定性讨论。
- **局限 2**：scale 实验止于 **4 GPU / 50M 向量**；未验证十亿级、跨节点 RDMA 或 CXL 内存池等部署形态（对比 [[RDMA]]、CXL-ANNS 类方向）。
- **局限 3**：DGS 依赖 L2 欧氏空间方向直觉，对非标准度量与极高 recall 的鲁棒性证据不足。
- **Future work 1**：用 **生产 trace** 测量非随机 sharding、小 batch、filtered query 下 inter-shard edge 命中率与 pipeline 利用率，量化何时 PPE 收益崩溃。
- **Future work 2**：将 direction-guided 思想与 **learned early termination**（如 SIGMOD 2020 adaptive termination）或 per-query adaptive top-n 结合，在保持 warp 平衡的前提下减少 cool-down 依赖。
- **Future work 3**：在 **8+ GPU / 全 PCIe / 多 tenant 增量更新** 场景做 end-to-end 测量，明确 graph rebuild 摊销、通信与 CPU reduce 是否成为新瓶颈。

## 相关

- **相关概念**：[[ANNS]]、[[Vector-Search]]、[[Beam-Search]]、[[Quantization]]、[[Pipeline-Parallelism]]
- **同类系统**：CAGRA、GGNN、[[HNSW]]、BANG、FusionANNS
- **同会议**：[[ATC-2025]]
- **对比**：graph-based GPU ANNS 中「sharding = 内存扩展」vs PathWeaver「sharding + 跨片路径延续」代表两种 multi-GPU 扩展哲学