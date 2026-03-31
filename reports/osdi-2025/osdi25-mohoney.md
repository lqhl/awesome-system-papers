# Quake: Adaptive Indexing for Vector Search

**作者**：Jason Mohoney, Devesh Sarda, Mengze Tang（University of Wisconsin–Madison）；Shihabur Rahman Chowdhury, Anil Pacaci, Theodoros Rekatsinas（Apple）；Ihab F. Ilyas（University of Waterloo）；Shivaram Venkataraman（University of Wisconsin–Madison）
**会议**：OSDI 2025（第 19 届 USENIX Symposium on Operating Systems Design and Implementation，Boston, MA，2025年7月7–9日）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/mohoney
**源文件**：[osdi25-mohoney.pdf](../../papers/osdi-2025/osdi25-mohoney.pdf)

---

## 一、背景

向量搜索（Vector Search）是现代机器学习应用的基础设施，用于在高维向量数据库中找到查询向量的 k 近邻（KNN）。推荐系统、检索增强生成（RAG）、语义搜索、信息检索等场景均依赖高效的向量索引。精确 KNN 搜索在大规模高维数据上计算代价极高，因此工业界广泛采用近似最近邻（ANN）索引，以少量精度损失（recall 下降）换取数量级的延迟降低。

工业界最主流的两类 ANN 索引各有优劣：
- **基于图的索引**（HNSW、DiskANN、SVS）：图结构导致查询延迟低、recall 高，但频繁 insert/delete 时维护代价极大（随机内存访问，需重新连边）。
- **基于分区的索引**（Faiss-IVF、SCANN、SPANN）：更新友好（顺序访问），但查询延迟比图索引高约一个数量级，且固定的 nprobe 参数无法适应数据分布和查询模式的动态变化。

真实工作负载具有明显的**读写倾斜（skew）**特征：热门内容（如维基百科上 Lionel Messi 的页面）会集中收到大量查询，新数据的插入也集中在特定区域。现有索引在这类动态倾斜负载下均表现不佳。

---

## 二、要解决的问题

### 2.1 现有方法的核心不足

| 方法类型 | 更新代价 | 动态查询适应 | 自动维护 |
|---------|---------|------------|---------|
| 图索引（HNSW/DiskANN/SVS） | 极高（随机访问） | 无 | 无 |
| 分区索引（Faiss-IVF） | 低 | 无（固定 nprobe） | 无 |
| DeDrift | 中 | 无 | 部分（大分区重聚类） |
| LIRE/SpFresh | 中 | 无（依赖阈值调参） | 部分（尺寸阈值分裂） |
| 早停方法（SPANN/LAET/Auncel） | 不适用 | 部分 | 需离线调参 |

### 2.2 三大技术挑战

1. **读倾斜导致的热分区问题**：高频查询集中打向部分分区，导致这些分区扫描开销主导查询延迟，而现有索引不会自动感知并重平衡分区。
2. **nprobe 无法在线适应**：分区结构随 insert/delete 变化后，固定 nprobe 会导致 recall 下降或不必要的过度扫描；现有早停方法依赖离线调参，在动态环境下需要频繁重标定。
3. **分区索引与图索引的性能差距**：分区索引查询是内存带宽受限（memory-bound）的操作，单线程性能比图索引差约 6–10×；多核 NUMA 架构的带宽优势未被充分利用。

---

## 三、核心设计

Quake 是一个自适应分区 ANN 索引，由三个核心机制构成：

### 3.1 自适应增量维护（Adaptive Incremental Maintenance）

基于**代价模型**指导分区的分裂与合并，使查询延迟最小化：

$$C = \sum_{l=0}^{L-1} \sum_{j=0}^{N_l-1} A_{lj} \cdot \lambda(s_{lj})$$

其中 $A_{lj}$ 是滑动窗口内分区 $j$ 在层 $l$ 的访问频率，$\lambda(s)$ 是扫描 $s$ 个向量的实测延迟函数。每次维护通过估算 $\Delta C$ 决定是否执行 Split/Merge 操作，引入"估计—验证—提交/回滚"三阶段工作流，确保代价单调递减。

**关键设计决策**：
- Split 后进行局部 k-means 精化（Refinement），重新分配邻近分区的向量，避免重叠导致 recall 下降
- Merge 将访问频率低且尺寸小的分区合并入最近邻分区
- 支持多层分区，层间通过动态增删上层来平衡 centroid 扫描开销

### 3.2 自适应分区扫描（Adaptive Partition Scanning, APS）

APS 在查询执行期间**在线估算当前 recall**，一旦估算值超过目标即终止扫描，无需离线调参：

$$\hat{\rho}(q) = p_0 + \sum_{i=1}^{m-1} p_i$$

其中 $p_0$ 是最近分区内未命中近邻的概率，$p_i$ 基于**超球帽几何**（hyperspherical cap）计算邻居落在已扫描分区之外的概率。当中间 top-k 距离阈值收缩超过 $\tau_\rho = 1\%$ 时才重计算概率，利用预计算的 beta 函数值降低开销。

### 3.3 NUMA 感知并行查询处理

多插槽服务器上内存访问非均匀，Quake 采用：
- **Round-robin 分区放置**：分区均匀分布到各 NUMA node
- **亲和性调度**：查询被分配到存放目标分区的 NUMA node 上的工作线程
- **工作窃取（Work Stealing）**：在同一 NUMA node 内均衡负载
- 与 APS 深度集成：主线程周期性聚合各 NUMA node 的局部结果并估算 recall，达到目标后通知所有工作线程终止

---

## 四、实现细节

- **代码规模**：7,500 行 C++，提供 Python API
- **底层依赖**：Faiss（倒排表管理）、LibTorch（批量张量操作）、SimSIMD（AVX512 距离计算）、`moodycamel::ConcurrentQueue`（无锁并发队列）
- **延迟函数 $\lambda(s)$**：离线 profiling 获得，由于 top-k 排序的非线性开销，扫描延迟相对于分区大小呈非线性
- **索引结构**：多层分区，底层存放原始向量，高层存放 centroid 向量；查询自顶向下 beam-search centroid，再扫描最底层分区
- **维护触发**：每处理一批查询/更新后触发，频率可配置
- **开源地址**：https://github.com/marius-team/quake

---

## 五、实验结果

### 实验平台

- 大规模实验：4-socket 服务器，Intel Xeon Gold 6148（80核/160线程），500GB RAM，4个 NUMA nodes，总内存带宽 300 GB/s
- 微基准：MacBook Pro M2 Max

### 主要工作负载

| 工作负载 | 规模 | 特征 |
|---------|------|------|
| WIKIPEDIA-12M | 1.6M→12M 向量，103次月度更新 | 真实读写倾斜，inner product |
| OPENIMAGES-13M | 滑动窗口 2M 驻留向量 | 含 delete，inner product |
| MSTURING10M-RO | 10M 向量 | 纯查询，静态 |
| MSTURING10M-IH | 1M→10M 向量 | 90% insert / 10% query |

### 端到端对比（总耗时，小时）

| 方法 | WIKIPEDIA-12M | OPENIMAGES-13M | MSTURING10M-IH |
|-----|:---:|:---:|:---:|
| **Quake-MT** | **1.98** | **0.15** | **0.70** |
| Quake-ST | 9.93 | 0.26 | 2.28 |
| DiskANN | 12.43 | 1.75 | 1.28 |
| SVS | 21.11 | 2.61 | 2.35 |
| Faiss-HNSW | 14.83 | — (不支持删除) | 2.64 |
| Faiss-IVF | 165.8+ | 0.46 | 13.73 |
| SCANN | 52.02+ | 0.62 | 6.79 |

（recall 目标 = 90%，k = 100；+ 表示 24 小时内未完成，基于 10% 抽样估算）

### APS 与早停方法对比（SIFT1M，90% recall 目标）

| 方法 | Recall | nprobe | 延迟 | 离线调参时间 |
|-----|-------|--------|-----|-----------|
| **APS** | 91.2% | 20.2 | 0.48ms | **0** |
| Auncel | 98.1% | 73.8 | 1.29ms | 73.8s |
| SPANN | 90.2% | 19 | 0.43ms | 183s |
| LAET | 90.5% | 18.2 | 0.42ms | 104s |
| Oracle | 92.4% | 19.3 | 0.41ms | 331s |

### 可扩展性（MSTURING100M）

- NUMA 感知并行在 64 线程时达到 6ms 延迟，峰值吞吐 200 GB/s
- 相比无 NUMA 配置快 4×，相比单线程快 20×

### 消融实验（WIKIPEDIA-12M）

| 配置 | 搜索延迟 | Recall 标准差 |
|-----|---------|-------------|
| Quake-MT（完整） | 0.53ms | 0.008 |
| 禁用 APS | 0.50ms | **0.025**（recall 不稳定）|
| 禁用 NUMA 多线程 | 3.28ms（6×） | 0.005 |
| 禁用 Maintenance | 45.20ms（85×） | 0.014 |

---

## 六、批判性分析

### 6.1 实验设计局限

**单查询延迟 vs 并发吞吐**：实验中查询是逐条串行处理的（one-at-a-time），这有利于 Quake 的 NUMA 并行单查询设计，但不代表在高并发场景下的实际吞吐表现。向量数据库在生产中通常需要处理大量并发请求，此时单查询 NUMA 并行的收益可能与 server-side batching 策略产生冲突。

**与图索引的静态比较**：在静态只读场景（MSTURING10M-RO）中，SVS 以 0.33h 优于 Quake-MT 的 0.71h。作者承认在静态场景下图索引仍占优，但未给出在实际部署中什么比例的工作负载是纯动态的，无法量化这一场景覆盖盲区。

**维护开销未充分讨论**：论文将 maintenance 时间单独列出（可后台执行），但未详细讨论 maintenance 期间对查询延迟的 tail latency 影响。Split 操作涉及 k-means 和分区精化，对实时系统可能引入抖动。

### 6.2 逻辑与一致性问题

**APS 的 "near-optimal" 声明有限**：APS 在 SIFT1M 上延迟仅高于 Oracle 17-29%，但 Oracle 的调参代价高达 331s；而对比方法 SPANN（183s）的延迟（0.43ms）实际接近 Oracle（0.41ms），与 APS（0.48ms）相比并没有显著劣势。"APS 无需调参"是真正的优势，但"近似 Oracle 精度"的声明在 90% recall 目标下被 SPANN 反驳。

**Wikipedia-12M 嵌入方法存疑**：论文用 DistMult 图嵌入来表示维基百科页面，而非主流的语言模型嵌入（如 CLIP、sentence-BERT）。这一选择不够贴近真实的 RAG / 语义搜索场景，可能低估或高估倾斜程度。

### 6.3 系统假设

**串行执行假设**：当前实现中搜索、更新、维护是串行执行的，论文在 Discussion 中仅提及"可通过 copy-on-write 支持并发"，但未实现。在需要高写入吞吐的生产系统中，这是一个重大限制。

**参数敏感性**：$f_M$（初始候选分区比例，1%–10%）对性能影响最大，论文承认未来工作目标是移除这一参数，暗示当前设计仍依赖人工干预。

---

## 七、AI Infra / MLSys 视角

### 直接价值

向量搜索是 AI 系统的核心基础设施，直接支撑 RAG pipeline 中的 retrieval 模块、推荐系统的 embedding 检索、多模态搜索等场景。Quake 在**动态数据集**（持续更新的知识库、实时内容库）上相比现有 SOTA 有 8× 以上的端到端性能提升，对需要 fresh data 的 RAG 系统尤为关键。

### 可迁移的技术思路

1. **代价模型驱动的自适应数据结构**：将访问频率和数据分布作为代价模型输入，指导索引结构的在线调整，这一思路可迁移到 KV cache 管理（按 attention frequency 动态调整缓存分配）、MoE 路由器的专家负载均衡等 AI Infra 场景。

2. **几何感知的早停机制**：APS 的 recall 估算利用超球帽体积来量化"已覆盖的向量空间"，无需历史标定数据。这种纯几何推理的在线精度估算思路值得在 beam search、speculative decoding token 验证等需要在线置信度估计的场景中探索。

3. **NUMA 感知的内存密集型工作负载优化**：Quake 的分区-NUMA node 绑定 + 亲和性调度策略可借鉴到 LLM 推理系统中大批量矩阵乘法的内存带宽优化，特别是在多路服务器上部署 large batch inference 时。

### 值得跟进的研究方向

- **与 LLM serving 的协同设计**：RAG 系统中 retrieval 和 generation 交错执行，能否在 LLM decode 的 idle 时隙触发向量索引维护，形成流水线协同？
- **GPU 向量索引**：论文 Discussion 提及代价模型可扩展到 GPU（λ_GPU(s)），但未实现。GPU 的 SIMD 宽度和 HBM 带宽特性下，APS 的超球帽几何估算开销占比如何？
- **量化感知的分区维护**：向量压缩（Product Quantization、SQ8）会改变扫描延迟曲线 λ(s)，压缩后分区的代价模型如何与重构误差联合建模？
- **多租户向量数据库**：不同租户的查询模式差异显著，在共享分区索引下如何针对每个租户的访问模式独立维护，同时控制索引内存占用？

---

## 八、总结

Quake 针对动态倾斜工作负载下的向量搜索问题，提出了以代价模型驱动的自适应分区维护、几何感知的在线 recall 估算（APS）和 NUMA 感知并行三位一体的系统设计。在真实 Wikipedia 工作负载上，Quake-MT 相比最强图索引 DiskANN 实现了 8× 端到端加速，同时大幅降低更新延迟。APS 在无需任何离线调参的前提下逼近 Oracle 精度，是论文最有实用价值的贡献。主要局限在于：单查询串行执行假设限制了高并发场景的适用性，维护期间的 tail latency 未被充分量化，静态场景下仍落后于成熟图索引实现。
