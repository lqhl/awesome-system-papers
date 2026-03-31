# Achieving Low-Latency Graph-Based Vector Search via Aligning Best-First Search Algorithm with SSD

**作者**：Hao Guo, Youyou Lu（清华大学）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation，July 7–9, Boston, MA）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/guo
**源文件**：[osdi25-guo.pdf](../../papers/osdi-2025/osdi25-guo.pdf)

---

## 一、背景

向量检索（ANNS，Approximate Nearest Neighbor Search）是现代推荐系统和 RAG（Retrieval-Augmented Generation）的核心基础设施。由于高维向量空间的维度诅咒，精确 top-k 搜索效率极低，业界普遍采用近似搜索。图结构索引（如 DiskANN 使用的 Vamana 图、HNSW）因其在高精度下搜索延迟低而备受青睐。

随着数据规模达到十亿级别，内存装不下全量索引，越来越多的系统选择将图索引存储在 SSD 上。但实测表明，同等索引在磁盘上的搜索延迟是内存版本的 4× 以上——例如 DiskANN（磁盘）vs. Vamana（内存），在 0.9 recall 下延迟差距达 4.18×。这一延迟鸿沟在实时搜索推荐场景（latency budget ~10ms）下难以接受。

---

## 二、要解决的问题

本文指出，磁盘上图搜索高延迟的根本原因是**best-first 搜索算法与 SSD I/O 特性的内在不匹配**：

**SSD 的两个关键特性**：
- 长 I/O 延迟（µs 到数十 µs）
- 支持异步并行 I/O（可同时处理多个 in-flight 请求）

**Best-first search 的两个问题**：

1. **跨搜索步骤的有序 compute-I/O**：每步 I/O 依赖上一步 compute 结果（必须先探索完邻居才能决定下一批 I/O），导致 I/O 延迟无法与 compute 重叠。实测 W=8 时 compute 仅占 I/O 延迟的 45.6%，长 I/O 时间被白白浪费。

2. **每步内同步等待 I/O**：即使用 W>1 做 batch read，仍需等全批 I/O 完成（取 tail latency）。实测 W=8 时 I/O pipeline 利用率仅 76%，W=32 时更低至 58%。

---

## 三、核心设计

### 关键洞察：compute 与 I/O 之间是"伪依赖"

虽然 best-first search 中 I/O 顺序依赖 compute 结果，但本文发现这个依赖可以打破：**下一个 I/O 读谁，只需看当前 in-memory 的候选池（candidate pool）**，不需要等待正在进行的 I/O 或 compute 完成。原因是图索引中每个向量有多条入边，best-first 只是估算了一条较短路径，并非唯一路径——tweaked 算法可走不同路径仍然收敛。

### PipeSearch 算法

基于上述洞察，设计 PipeSearch：
- 维护候选池 P（固定长度 L）和 I/O pipeline Q（宽度 W）
- **无需等待 I/O 完成**：只要 pipeline 未满，立即从候选池中 speculative 读取当前最近邻
- **与 I/O 并行 explore**：对已读回但未探索的向量集合 U，在 I/O 等待期间做 best-effort 探索
- 结果：compute 与 I/O 重叠，pipeline 利用率显著提升，延迟约降至 best-first 的 50%

### PipeANN 系统（解决延迟-吞吐 dilemma）

PipeSearch 虽降低延迟，但产生 I/O waste（speculative 读了但没被探索的向量），降低吞吐。PipeANN 通过两个机制解决：

**1. 两阶段搜索 + 动态 pipeline 宽度**

搜索自然分为两个阶段：
- **Approach phase（趋近阶段）**：候选池快速向目标靠近，I/O waste 大，pipeline 不宜宽。PipeANN 使用**内存图子索引做入口点优化**（采样 1% 向量建内存 Vamana 图），并以小宽度（W=4）启动 PipeSearch。
- **Converge phase（收敛阶段）**：候选池趋于稳定，top-k 邻居逐渐被召回，I/O waste 自然下降，可用更宽 pipeline。PipeANN 动态增大 W：当已召回向量数估计超过阈值（默认 5），检测当前 I/O 命中候选池的比例，若超过 0.9 则 W+1。

**2. 算法优化：避免邻居向量积压**

当多个 I/O 同时完成时，若立刻填满 pipeline，会导致 I/O 在邻居信息缺失的情况下做出次优决策（accumulated unexplored vectors → I/O waste 爆炸）。PipeANN 的策略：多个 I/O 完成时，**逐个处理**（发一个 I/O + 探索一个向量），将 I/O completion 时间散开，保证第 n 个 I/O 能参考前 n-W 次 compute 的邻居信息。

---

## 四、实现细节

- **异步 I/O**：使用 `io_uring`，每线程维护私有 io_uring 实例；用 `prep_read` 发送请求，`peek_batch_cqe`（non-blocking）轮询完成
- **SQ polling**：启用 io_uring 的 Submission Queue Polling，降低 I/O 发出和轮询的延迟开销
- **PQ 距离计算**：邻居距离用 Product Quantization 压缩向量（32 bytes/vector）在内存中估算，避免磁盘读；最终结果用精确距离重排
- **Cache 防污染**：PQ 全局表（不参与搜索）用 AVX512 non-temporal load，避免污染 L1/L2 cache
- **初始化重叠**：等待第一个磁盘 I/O 的 ~50µs 期间，与 local PQ 表初始化重叠
- **内存占用**：billion-scale 数据集 <40GB（32GB PQ 向量 + <4GB 内存图）；disk 需 600GB+（图索引）

---

## 五、实验结果

**实验平台**：2×28-core Intel Xeon Gold 6330 @ 2.00GHz，512GB RAM，Samsung PM9A3 3.84TB NVMe SSD，Ubuntu 22.04

**数据集**：SIFT1B/100M，SPACEV1B/100M，DEEP100M（100M~1.4B 向量）

**对比系统**：DiskANN（图，best-first），Starling（图，I/O 优化），SPANN（cluster-based）

### 延迟（1 线程，recall10@10）

| 场景 | 指标 |
|------|------|
| PipeANN vs DiskANN（100M，0.9 recall） | 39.1% 延迟（缩短约 2.5×） |
| PipeANN vs Starling（100M，0.9 recall） | 48.5% 延迟（缩短约 2×） |
| PipeANN vs SPANN（100M，0.9 recall） | 70.6% 更低延迟 |
| PipeANN vs DiskANN（SIFT1B，0.9 recall） | 35.0% 延迟（0.719ms vs ~2ms） |
| PipeANN vs Vamana（内存，0.9 recall） | 1.14×–2.02× 延迟（大幅弥合延迟鸿沟） |

### 吞吐（56 线程）

| 场景 | 指标 |
|------|------|
| PipeANN vs 对比系统（100M，0.9 recall） | 平均 1.35× 更高吞吐 |
| PipeANN vs DiskANN（SIFT1B，0.9 recall） | 1.71× 更高吞吐（19.4K QPS） |
| PipeANN vs Starling（0.99 recall） | 0.80× 吞吐（略低，因 Starling 的磁盘重排技术减少了 I/O） |

### Ablation（SIFT100M，0.9 recall）

| 配置 | 相对 Baseline 延迟 |
|------|------|
| Baseline（best-first，W=8） | 1.0× |
| +Pipe（PipeSearch，W=8） | 55.1% |
| +AlgOpt（多 I/O 完成优化） | 53.8%（同时吞吐 +8.5%）|
| PipeANN（动态 pipeline） | 43.5%（高 recall 场景提升更显著）|

---

## 六、批判性分析

**1. Speculative I/O 的吞吐代价被低估**

论文承认 PipeANN 在低 recall（0.8）时吞吐比 ideal DiskANN（W=1）低 17–34%，但却将"低 recall 不是目标场景"作为借口轻描淡写。然而很多大规模系统在实际部署中会针对不同 SLA 混合运行不同 recall 目标，PipeANN 对低 recall 吞吐的劣势可能是严重的部署障碍。

**2. 对比基线存在明显不公平**

- 与 Starling 对比时，因为 billion-scale 下 Starling 的磁盘记录重排开销太大而放弃对比，改为只对比 DiskANN。这回避了一个关键问题：Starling 的重排技术能否与 PipeSearch 组合，两者正交性只是"留给未来工作"而没有实验验证。
- SPANN 的 cluster-based 方法在 recall=0.8 时比 PipeANN 更快，论文将此归咎于 PipeANN 的 approach phase 开销，但没有分析如何优化 approach phase 的效率。

**3. 实验规模偏保守**

多线程吞吐测试使用所有 56 核（全核），未展示在部分核（如 8/16 核）下的吞吐扩展性，也没有分析 I/O 带宽是否成为真正瓶颈（SSD 带宽 vs. CPU 计算之间的关系）。实际部署中 ANNS 服务通常与其他服务共享机器，全核测试不具代表性。

**4. Dynamic pipeline 调整策略缺乏严格分析**

论文使用 threshold=5 和 ratio=0.9 等经验参数，虽然图 17 显示 dynamic 比 static 仅好 6–9%，说明不敏感，但对于不同数据集（向量维度、分布、图连通性）是否普遍适用缺乏系统性验证。

**5. 精度降低的轻描淡写**

论文报告 PipeANN 在相同参数下比 DiskANN 至少保持 95.9% recall，但这意味着在 recall=0.9 标准下可能有 ~5% 的结果质量损失。对于某些高精度要求场景（如金融、医疗 RAG），这并非可忽略的误差，论文对此缺乏深入讨论。

---

## 七、AI Infra / MLSys 视角

**直接相关性**：向量数据库是现代 LLM 推理链路（特别是 RAG）的核心组件，PipeANN 直接优化了磁盘向量检索的延迟，对 LLM 推理 latency SLA 有实际影响。

**关键 insight 迁移**：
- **I/O-compute 伪依赖打破**的思路可迁移到其他存储层场景：例如 KV cache offloading 到 SSD 时的 prefetch 策略（PagedAttention + SSD tiering），可以参考 PipeSearch 的 speculative 预读逻辑——在决定下一批 token 的 KV cache 读取时，不必等待当前 attention compute 完成
- **两阶段自适应流水线**的设计范式也适用于异构存储分层系统中的 I/O 调度：初期数据"冷启动"时保守，稳定阶段激进并行

**值得跟进的研究方向**：
- **PipeANN + 磁盘重排（Starling 的 reorder）**：两者被声称正交，但 billion-scale 下 reorder 开销是否可以通过增量/在线方式摊销？结合后性能能否进一步提升？
- **CXL/Remote Memory 场景的验证**：论文提到 PipeSearch 可扩展到 CXL 内存（2µs 延迟），这与 AI Infra 中的 CXL 内存池化趋势高度契合，值得实验验证
- **向量 + 标量混合查询**（如 filtered ANNS）：PipeSearch 的 speculative I/O 在加了过滤条件后的 recall 效率如何变化？
- **与 LLM inference 的端到端集成**：PipeANN 能否作为 RAG pipeline 的 retrieval backend，在实际 LLM 推理 latency budget 下带来端到端收益（而非仅孤立的搜索延迟）？

---

## 八、总结

PipeANN 通过识别 best-first 搜索算法与 SSD 特性的"伪依赖"，将图搜索的 compute 与 I/O 重叠，并通过两阶段动态 pipeline 宽度调整平衡延迟与吞吐，在 billion-scale 数据集上将磁盘 ANNS 延迟压缩至 DiskANN 的 35%，并使延迟接近内存索引（1.14×–2.02×）。主要局限在于低 recall 场景吞吐下降（17–34%）、与 Starling 磁盘重排的组合尚未验证，以及精度轻微下降。对于以 0.9+ recall 为目标的大规模搜索推荐和 RAG 检索场景，PipeANN 是目前磁盘 ANNS 系统中延迟最优的方案之一。
