# Quake: Adaptive Indexing for Vector Search

**作者**：Jason Mohoney, Devesh Sarda, Mengze Tang (University of Wisconsin–Madison); Shihabur Rahman Chowdhury, Anil Pacaci, Theodoros Rekatsinas (Apple); Ihab F. Ilyas (University of Waterloo); Shivaram Venkataraman (University of Wisconsin–Madison)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/mohoney
**源文件**：[[osdi25-mohoney.pdf]]

---

## 一、背景

向量搜索（Vector Search）是现代机器学习应用的核心基础设施，广泛用于 RAG、推荐系统和信息检索等场景。其任务是在高维向量数据库中找到与查询向量最近的 k 个邻居（KNN）。由于精确 KNN 搜索在大规模数据上计算代价过高，实践中使用近似最近邻（ANN）索引，以可控的 recall 损失换取数量级的延迟降低。

当前主流 ANN 索引分为两大类：**图索引**（如 HNSW、DiskANN、SVS）通过近邻图遍历实现高 recall 和低延迟，但更新代价高昂；**分区索引**（如 Faiss-IVF、SCANN）通过 k-means 聚类将向量划分到不同分区，更新友好但搜索延迟比图索引高一个数量级。然而，真实世界的向量搜索工作负载具有**动态性**和**偏斜性**——数据持续变化（插入/删除），查询和写入都集中在少数热点区域——现有方法在这类场景下性能严重退化。

---

## 二、要解决的问题

1. **分区不平衡导致延迟退化**：在偏斜的写入模式下，部分分区膨胀为热点大分区，扫描代价急剧增加。Faiss-IVF 在 Wikipedia 工作负载上搜索时间从可接受水平增长到 165 小时。
2. **固定 nprobe 无法适应动态索引**：现有分区索引使用固定数量的分区扫描（nprobe），当索引结构因维护操作而变化时，recall 随之退化。现有 early termination 方法（SPANN、LAET、Auncel）要么需要离线调优，要么假设静态索引。
3. **分区索引与图索引的性能差距**：标准分区索引是内存带宽受限的，查询延迟比图索引高一个数量级（如 Faiss-IVF 44ms vs Faiss-HNSW 6.8ms）。
4. **图索引更新代价过高**：图索引在频繁插入/删除场景下需要重新连接图结构，更新延迟比分区索引高 18-126×。

---

## 三、洞察与设计

**关键洞察**：分区索引的查询延迟可以建模为各分区「访问频率 × 扫描延迟」之和（Cost = ΣA_lj · λ(s_lj)），而偏斜工作负载中少数频繁访问的大分区贡献了绝大部分延迟。因此，只需针对性地对高成本分区进行 split/merge 维护，即可以最小代价实现全局延迟优化。同时，通过在查询过程中基于超球与分区边界的几何交集实时估计 recall，可以逐查询自适应决定扫描分区数，无需离线调优。

基于此洞察，Quake 的核心设计包括三个组件：

### 1. 自适应增量维护（Adaptive Incremental Maintenance）
- **代价模型**：跟踪每个分区的大小和访问频率，估计其对查询延迟的贡献 C_lj = A_lj · λ(s_lj)
- **维护动作**：Split（k-means 拆分热点/大分区）、Merge（删除冷/小分区并重分配向量）、Add/Remove Level（管理层级平衡）
- **Estimate-Verify-Commit 流程**：先用轻量估计筛选候选动作，执行后验证实际收益，只有 ΔC < -τ 才提交，否则回滚。确保代价单调递减
- **分区细化（Refinement）**：split 后对邻近分区执行额外 k-means 迭代，减少分区重叠

### 2. 自适应分区扫描（Adaptive Partition Scanning, APS）
- 基于几何模型实时估计 recall：利用查询超球体与各分区 Voronoi 边界的交集体积，计算每个分区包含近邻的概率
- 按概率降序扫描分区，累积 recall 估计达到目标即停止
- 预计算 Beta 函数值 + 仅在查询半径变化超过阈值时重算概率，开销极低
- 无需任何离线调优，自动适应索引结构变化

### 3. NUMA 感知查询处理
- 分区按 round-robin 分配到 NUMA 节点，扫描任务调度到数据所在的本地核心
- 分区绑定特定 CPU core 以最大化缓存利用
- 支持 NUMA 节点内 work stealing 处理负载不均
- 与 APS 集成：主线程周期性合并各 worker 的部分结果，估计 recall 达标即终止

---

## 四、实现细节

- **代码规模**：7,500 行 C++，配有 Python API
- **依赖库**：Faiss（倒排列表管理）、PyTorch（批量张量操作）、SimSIMD（AVX512 距离计算）、高性能并发队列避免协调瓶颈
- **多级索引**：底层存储实际向量，高层存储 centroid 向量。查询自顶向下搜索，先在高层找到候选分区再扫描底层
- **APS 优化**：预计算 regularized incomplete beta function 在 1024 个均匀点上的值并线性插值；只在查询半径变化 >1% 时重计算概率，减少 29% 延迟
- **维护调度**：每处理一批操作后检查代价模型，自底向上逐层执行维护
- **分区细化参数**：refinement radius r_f=50（考虑邻近 50 个分区），1 轮 k-means 迭代
- **开源**：https://github.com/marius-team/quake

---

## 五、实验结果

**实验平台**：4-socket Intel Xeon Gold 6148（80 核/160 线程），500GB RAM，4 NUMA 节点，300GB/s 总内存带宽。部分微基准在 M2 Max MacBook Pro 上运行。

**工作负载**：Wikipedia-12M（真实偏斜读写）、OpenImages-13M（含删除）、MSTuring10M-RO（纯读）、MSTuring10M-IH（插入+搜索）。目标 recall=90%, k=100。

### 端到端性能（总搜索时间，小时）

| 方法 | Wikipedia-12M | OpenImages-13M | MSTuring10M-RO | MSTuring10M-IH |
|------|:---:|:---:|:---:|:---:|
| **Quake-MT** | **1.53** | **0.03** | 0.63 | **0.54** |
| Quake-ST | 9.48 | 0.14 | 2.43 | 2.12 |
| Faiss-IVF | 165.8 | 0.45 | 12.25 | 13.72 |
| DiskANN | 12.11 | 0.22 | 1.16 | 0.81 |
| SVS | 20.54 | 0.29 | **0.33** | 2.11 |
| SCANN | 50.27 | 0.41 | 2.97 | 6.70 |
| Faiss-HNSW | 14.65 | — | 1.9 | 1.27 |

### 关键数据
- **动态工作负载**：Quake-MT 搜索延迟比 HNSW/DiskANN/SVS 低 1.5-13×，更新延迟低 18-126×
- **APS vs Oracle**：在 SIFT1M 上 APS 的延迟仅比 oracle 高 17-29%，且零离线调优开销
- **NUMA 扩展性**：在 MSTURING100M 上线性扩展至 64 线程，峰值吞吐 200GB/s，NUMA 感知相比非 NUMA 获得 4× 延迟降低
- **消融实验**：禁用维护后延迟从 3.28ms 飙升到 45.20ms（14×）；禁用 APS 对延迟影响小但 recall 标准差从 0.005 增大到 0.025
- **多查询处理**：批量 10,000 查询时 Quake 比 Faiss-IVF/SCANN 快 6.7×，比 DiskANN 快 1.8×

---

## 六、批判性分析

1. **静态场景竞争力有限**：在 MSTuring10M-RO（纯读静态）工作负载上，SVS 搜索时间 0.33 小时 vs Quake-MT 0.63 小时，图索引仍有明显优势。论文标题强调 "adaptive" 但在静态场景下 Quake 并不占优，这限制了其通用性。

2. **单线程性能差距被 NUMA 并行掩盖**：论文大量强调 Quake-MT 的优势，但单线程 Quake-ST 在 MSTuring10M-IH 上 2.12 小时 vs DiskANN 0.81 小时，差距达 2.6×。NUMA 感知并行是独立的工程优化，可同样应用于图索引（SVS 已有类似优化），将其作为 Quake 独有优势有误导性。

3. **代价模型假设的局限性**：代价模型假设 λ(s) 可通过离线 profiling 获得且稳定，但实际系统中缓存效应、并发查询间的干扰、内存带宽竞争等因素会导致 λ(s) 波动。论文未讨论代价模型在高并发场景下的准确性。

4. **并发支持缺失**：当前实现中搜索、更新和维护串行执行。论文在 Discussion 中轻描淡写地提到可通过 copy-on-write 支持并发，但这是生产系统的核心需求，未实现也未评估。

5. **APS 的均匀密度假设**：APS 的几何模型假设向量在分区内均匀分布（uniform-density assumption），而论文的核心动机恰恰是偏斜分布。虽然实验表明 APS 在实践中有效，但这个理论-实践的矛盾未被充分讨论。

6. **维护开销的可预测性**：维护时间在不同工作负载上差异很大（Wikipedia-12M 维护 0.44 小时 vs 搜索 1.53 小时，占比 22%）。在延迟敏感的在线服务中，维护操作（尤其是 split + refinement）可能导致不可预测的延迟尖刺，论文未评估尾延迟影响。

7. **基线实现公平性**：LIRE 和 DeDrift 是在 Quake 框架内重新实现的，SCANN 使用了"未公开的维护策略"。这些重新实现可能无法完全反映原始系统的优化水平。

---

## 七、AI Infra / MLSys 视角

1. **RAG 系统的索引层优化**：Quake 直接解决了 RAG 场景中的核心痛点——知识库持续更新导致索引性能退化。其自适应维护策略可以集成到 Milvus、Qdrant 等向量数据库中，为 LLM 应用提供更稳定的检索延迟。

2. **推理系统中的 KV Cache 管理启发**：Quake 的代价模型思路（频率 × 大小 → 成本）与 LLM 推理系统中的 KV cache 驱逐策略有相似性。PagedAttention 等方案可以借鉴类似的自适应分区和代价驱动维护思想，优化不同长度请求的 cache 管理。

3. **Embedding 模型持续更新场景**：随着 embedding 模型迭代更新（如 fine-tuning 或 continuous learning），向量空间分布会发生漂移。Quake 的增量维护能力使其特别适合这类场景，无需全量重建索引。

4. **值得跟进的方向**：
   - **GPU 加速的分区扫描**：论文提到代价模型可扩展到 GPU，但未实现。在 GPU 内存层级下重新设计分区扫描和 APS 是有价值的研究方向
   - **与量化技术的结合**：Quake 目前未启用向量压缩，与 PQ/SQ 等量化方法结合后的性能表现值得探索
   - **分布式 Quake**：论文仅简要讨论了分布式扩展，如何在多机环境下协调维护决策、处理跨节点的分区重分配是关键挑战

---

## 八、总结

Quake 是一个面向动态偏斜工作负载的自适应向量搜索索引系统，核心贡献在于：(1) 基于代价模型的增量分区维护，通过 estimate-verify-commit 流程确保延迟单调递减；(2) 基于几何概率的自适应分区扫描（APS），无需离线调优即可逐查询设定 nprobe 以满足 recall 目标；(3) NUMA 感知的查询并行化，充分利用多核服务器内存带宽。在动态工作负载上 Quake 相比图索引搜索延迟降低 1.5-13× 且更新延迟降低 18-126×，但在静态场景下仍不及优化良好的图索引。系统当前不支持并发操作，是走向生产部署的主要障碍。
