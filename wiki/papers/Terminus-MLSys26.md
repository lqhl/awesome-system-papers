---
type: paper
name: Terminus
full_title: "When Enough is Enough: Rank-Aware Early Termination for Vector Search"
authors: [Jianan Lu, Asaf Cidon, Michael J. Freedman]
venue: MLSys
year: 2026
tags: [vector-search, rag, ann, disk-io, early-termination]
source_pdf: "[[45c48cce2e2d7fbdea1afc51c7c6ad26.pdf]]"
source_md: "[[45c48cce2e2d7fbdea1afc51c7c6ad26]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# When Enough is Enough: Rank-Aware Early Termination for Vector Search (MLSys 2026)

> **一句话总结**：在磁盘驻留 graph [[ANNS]] 中，top-ranked 结果多在早期 I/O 即发现而 [[RAG]] 准确率主要由前几位文档主导；Terminus 用 per-I/O rank-weighted utility 动态早停搜索，在 Starling 上相对 rank-agnostic 早停吞吐 **1.4×**、相对无早停 **3.2×**，RAG Exact Match 影响极小。

## 问题与动机

[[Vector-Search]] / graph-based [[ANNS]] 是 [[RAG]]、agent reasoning 等 LLM 应用的基础设施。随着 embedding 维度升高（OpenAI text embedding 1536–3072 维）和语料规模扩大，proximity graph 无法全量驻留内存，必须 offload 到本地或网络盘（[[DiskANN]]、[[Starling]] 等）。图遍历路径依赖 query 与图结构，产生大量小随机读——单 query 可触发数十至数百次 I/O，**磁盘 IOPS 成为吞吐主瓶颈**（Table 1：假设每 query ~100 I/O，NVMe 上理论 QPS 上限仅数百）。

既有优化集中在**索引构建与布局**（DiskANN 长边「express lane」、Starling 相似向量 block 共置、in-memory navigation graph），能降低单次遍历 I/O，但**不改变搜索终止语义**：系统仍会一直搜到队列中所有候选被访问、无法再改进 top-L 为止，即使 top-ranked 结果早已找到。这与下游 workload 的真实效用严重错位——[[RAG]] 对第 0 位文档的依赖远大于第 19 位，而传统 Recall@k 对所有 rank 等权，无法反映这种效用结构。

论文核心问题：能否在 graph ANN 搜索过程中**按 rank 效用动态分配 I/O**，在已找到高价值结果后尽早停止，从而在不显著伤害 [[RAG]] 准确率的前提下突破 IOPS 瓶颈？

## 关键观察 / 隐含假设

- **观察 1：最高相似度结果通常在搜索早期即被发现，后续 I/O 收益递减**。
  - **依赖假设**：graph 搜索分两阶段（navigation → similarity），进入目标邻域后短边遍历能快速收敛；Starling 上 rank 0–1 多在 I/O 3–7 出现，而 rank 19 所需 I/O 约为 rank 0 的 **2×**（Figure 2b/c）。
  - **可能失效场景**：难 query 或劣质 entry point 导致 navigation 阶段拉长；索引布局差使「早期发现 top result」规律不成立；k 很大时 tail rank 仍影响某些 rerank-heavy pipeline。

- **观察 2：[[RAG]] 端到端准确率由 top-ranked 检索文档主导，k 饱和后扩检索收益有限**。
  - **依赖假设**：Natural Questions 上 exhaustive search 的 top-k 在 **k ≥ 20** 后 EM 饱和（Pythia-1B、LLaMA-2-7B）；逐位丢弃第 i 个文档的 normalized accuracy loss 随 rank 急降（Figure 3）。
  - **可能失效场景**：多跳/agent 检索需要长尾文档互补；rerank 或 fusion 改变 rank 效用曲线；不同任务（代码检索、结构化 QA）对 tail 更敏感。

- **观察 3：相似度分数的绝对增量是脆弱信号，rank 位置变化才是更稳健的 per-I/O 效用指标**。
  - **依赖假设**：搜索队列已含中等质量候选时，真 best result 的 cosine 增量可能极小；「是否插入更高 rank」是离散、可观测的结构变化。
  - **可能失效场景**：大量 tie-breaking 或近似距离导致 rank 抖动；极小队列 L 使每次 I/O 都引发大幅 rank 重排，utility 信号噪声大。

- **假设 1：rank 效用可用指数衰减权重 $w(r)$ 建模，且应与下游任务 rank sensitivity 对齐**。
  - **证据强度**：**中**——Figure 3 的 RAG accuracy loss 与 $\tau=1.8, \beta=0.5$ 的权重曲线经验匹配；但权重形式未在多任务上系统验证，论文也承认可换 Reciprocal Rank、DCG 等形式。

- **假设 2：滑动窗口内连续低 utility I/O 意味着可安全早停，无需 oracle 知道「真 best 是否已出现」**。
  - **证据强度**：**中**——Figure 6c 显示 utility 曲线前 10 次 I/O 已覆盖 top-5 与 9/10 top-10；但 graph search 有 long-tail 行为，窗口过小（X=1）会过早终止（Figure 8c）。

## 核心方法

Terminus 在 graph ANN 搜索栈中插入两个组件：**utility estimator** 与 **termination engine**（Figure 4），实现于 Starling 代码库以公平对比。

### Rank-aware utility modeling

每次 I/O 读入 disk block 并更新相似度排序的 search queue（大小 L ≥ k）后，utility estimator 记录**本轮新插入结果**的 rank 集合 $\Delta R_t$，计算：

$$U_t = \sum_{r \in \Delta R_t} w(r)$$

权重采用指数衰减 $w(r)$，参数 $\tau$ 控制衰减位置（小 $\tau$ 强调 top rank）、$\beta$ 控制曲线陡峭度。默认 $\tau=1.8, \beta=0.5$，与 Natural Questions RAG rank sensitivity 对齐。直觉：rank 0 的改进比 rank 9 贡献更大 utility，使系统对「找到更重要结果」更敏感，而非追逐相似度微小增量。

### Dynamic early termination

Termination engine 用大小为 **X** 的滑动窗口跟踪最近 I/O 的 utility。当窗口内**每个** I/O 的 $U_i$ 均低于阈值 **ε** 时触发停止，返回当前 best-k。这比固定 I/O budget（IO-Budget）更自适应：易 query 早停、难 query 多搜；比 VBASE 的「近期候选不如 queue top-E」更细粒度且**显式 rank-aware**。

引擎位于 graph traversal 与 I/O manager 之间，可逐 I/O 决定 allow/reject；触发后向 index 发 stop 信号。默认 **X=2**；ε 越大早停越激进。早停跟踪与 utility 计算开销 ≤ 总 query latency 的 **2%**（Figure 9c）。

### Ranked Recall 指标

针对 Recall@k 的 rank-agnostic 缺陷，论文提出 **Ranked Recall@k**：对 ground truth 序列 $G$ 与检索序列 $R$，按 rank 位置加权匹配——高位命中权重更大。当权重均匀时退化为标准 Recall。实验表明：相同 I/O 下不同早停方案的 **Recall–I/O 曲线几乎重合**，但 **Ranked Recall–I/O 曲线可区分** top-ranked 检索质量差异（Figure 7）；Ranked Recall@20 与 RAG EM 呈强单调相关（Figure 10c）。

## 设计取舍

- **Rank-aware utility vs rank-agnostic 早停（VBASE、IO-Budget）**：用 per-rank 加权换取对 top result 的 I/O 倾斜；代价是需为下游任务调 $\tau, \beta$，且对「所有 rank 等重要」的 benchmark 不占优。
- **动态 ε 阈值 vs 固定 I/O budget**：自适应 query 难度；代价是 ε/X 调参空间与 long-tail 查询的保守搜索之间的张力——极高 recall 目标仍需大量尾部 I/O（Figure 2c long-tail）。
- **早停 vs 完整遍历**：显著降 IOPS（中等准确率区间收益最大，0.6–0.9 Ranked Recall）；牺牲 tail rank 召回，不适合要求 near-perfect retrieval 的场景（论文建议此时禁用或增大 ε 保守阈值）。
- **叠加于 Starling vs 独立系统**：复用 Starling 的 block layout、navigation graph、I/O–compute pipeline，贡献正交于布局优化；但结论外推到纯内存 [[HNSW]] 或非 graph ANN 需重新测量 I/O 行为。
- **边界条件**：**磁盘驻留 graph ANN + [[RAG]] 类 rank-sensitive 下游** 最优雅；**极高 recall 检索**、**rank 效用平坦的任务**、**I/O 非瓶颈的内存索引** 收益有限。

## 实验与结果

**Setup**：CloudLab r650（72 core、256 GB RAM、1.6 TB NVMe）；RAG 评测用 RTX 2080 Ti / GV100 GPU 节点；异步 I/O + O_DIRECT 绕过 page cache。数据集 Wikipedia-20M（Contriever-MSMARCO embedding、Natural Questions query）与 SPACEV-100M（Bing 场景 web 向量）。默认 **k=20**（RAG 饱和点）；对比 Starling（无早停）、VBASE（X=1, 调 E）、IO-Budget（调 B）、Terminus（X=2, $\tau=1.8$, 调 ε）。

- **向量搜索效率**：Terminus 在 Ranked Recall 维度 consistently 优于 IO-Budget——相同平均 I/O 下 top rank（0–10）命中率约高 **5–10%**，rank 0 附近约 **80%** 查询成功命中（Figure 8a）；k=100 时相同 Ranked Recall 平均少 **5** 次 I/O/query（Figure 8b）。
- **吞吐–准确率**：中等准确率（Pythia-1B EM≈0.16）Terminus QPS 为 IO-Budget 的 **1.4×**；高准确率（LLaMA-2-7B EM≈0.33）相对 VBASE **1.6×**（Figure 10a/b）。
- **相对无早停 Starling**：同 k=20 目标下 Pythia-1B 最高 **1.2×** QPS；相对 k=10 的「少检索快基线」仍可达 **2×**（Pythia-1B）/ **3.2×**（LLaMA-2-7B）QPS 且准确率更高（Figure 11）——大 k 保留 top-ranked 价值 + 早停省 I/O 的组合效应。
- **ε 敏感性**：ε=0.09 时相对 baseline（ε=0）QPS 提升近 **150%**，EM 仍 >0.16（无 RAG baseline 0.0263）；准确率随 ε 增大非严格单调——embedding 噪声与 LLM「lost-in-the-middle」可解释（Figure 9a）。
- **X 与 L**：X=1 易过早终止；X=2/3 平衡最好；更大 search queue L 使 baseline 更慢而 Terminus QPS 增益更大（top result 仍在早期 I/O 发现）（Figure 9b）。
- **开销**：早停逻辑 ≤ **2%** latency；compute–I/O overlap 比例与 Starling 相近（68% vs 73%）。

## Critical Analysis

### 论证链条

主链条清晰：**测量到磁盘 graph ANN 受 IOPS 限制且 top rank 早现** → **RAG 效用集中在高 rank** → **per-I/O rank-weighted utility 可估计边际收益** → **低 utility 窗口触发早停** → **Ranked Recall 与 RAG EM 对齐的吞吐提升**。

设计映射明确：utility 用 rank 而非 similarity delta 回应观察 3；指数权重回应观察 2；滑动窗口回应 long-tail I/O 风险。与 DiskANN/Starling 布局优化正交，定位合理。

薄弱环节：将 Natural Questions + Contriever 上的 rank decay **外推为通用 vector search 早停策略**；未证明 Terminus 在**纯检索 API**（无 LLM 下游）仍是最优；把 Ranked Recall 与 RAG EM 的相关性当作「metric 足够」的证据，但因果上仍可能有 confounder（embedding 质量、prompt 构造）。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| Top rank 早期出现 | Starling Figure 2b/c | 差 entry point、非 Starling 布局、极高维稀疏图 |
| RAG 效用随 rank 急降 | Figure 3，k=20 饱和 | 多跳检索、长文档 rerank、代码/结构化任务 |
| 指数 $w(r)$ 匹配下游 | τ=1.8 经验拟合 | 新模型、新任务需重标定；rank 效用非单调 |
| 低 utility 窗口 = 可停 | 多数据集 Ranked Recall–I/O 曲线 | Long-tail 好结果晚现；X 过小 premature stop |
| Starling 基线代表 SOTA 磁盘 ANN | 选用最新 Starling | 其他系统（FusionANNS、CXL-ANNS）I/O 形态不同 |

### 实验可信度

- **优势**：在 Starling 代码库内实现所有早停方案，控制变量；同时报 Recall 与 Ranked Recall，并做端到端 RAG（两种 LM）；覆盖 web 与 Wikipedia 两种数据分布；ε/X/L 有 sensitivity sweep。
- **局限**：Ground truth 仍依赖 exhaustive/高 L 搜索代理，非人工标注 relevance；SPACEV 实验以向量检索为主，RAG 端到端主要在 Wikipedia-20M；VBASE 偏保守，可能低估「高 recall 早停」设计空间。
- **缺失**：**多租户共享盘**、**P99 latency**、**在线 query 分布漂移**、**与 reranker 级联** 的实验；未测 Terminus 对 index update/streaming ingest 的交互。

### 系统性缺陷

- **尾延迟与 SLO**：聚焦平均 I/O 与 QPS，**P99 query latency**、早停误判导致偶发低 recall 的长尾未量化。
- **资源隔离**：CloudLab 单节点、O_DIRECT 绕过 page cache——与生产环境多租户共享 EBS/NVMe 的 effective IOPS 不同（论文在 Introduction 提及云盘共享但未实验）。
- **可观测性**：per-I/O utility 与终止决策可增加调试信号，但论文未讨论如何在生产中解释「为何某 query 被早停」。
- **运维成本**：需为每个下游任务标定 $\tau, \beta, \varepsilon, X$；embedding 或 prompt 策略变更后 rank sensitivity 可能漂移，**重标定成本**未讨论。
- **正确性**：早停不改变检索结果的正确性定义，但可能增加「漏掉次优但任务关键文档」的风险；论文未讨论与 access control、一致性读相关的场景。

## 局限与 Future Work

- **局限 1**（论文自述）：graph search 的 long-tail I/O 使**极高 retrieval quality** 仍需深度遍历；near-perfect 场景应禁用早停或采用保守 ε。
- **局限 2**（论文自述）：embedding 模型不能完美捕捉语义相关性，导致相似度与真实 relevance 错位；RAG accuracy 随 ε 非单调（Figure 9a）。
- **局限 3**（论文自述）：rank-weight 函数需与下游任务对齐；指数形式是可选之一，其他任务需 empirical profiling（如 Figure 3）或领域先验。
- **局限 4**（实验边界）：实现与评测绑定 **Starling + 异步 block I/O**；未覆盖 GPU/CXL 分层索引、纯内存 [[HNSW]]、或 learned early termination（Li et al. 2020）。
- **Future work 1**：在 **production RAG trace** 上自动拟合 rank-weight 曲线，并测量 embedding 版本升级后的早停参数漂移与重标定频率。
- **Future work 2**：将 Terminus 与 **reranker / cascade retrieval** 联合建模效用——rerank 可能抬升 tail 文档价值，改变最优早停点。
- **Future work 3**：量化 **multi-tenant 云盘** 下早停对 effective IOPS 与 P99 latency 的影响，并与 quota-aware admission control 协同。

## 相关

- **相关概念**：[[RAG]]、[[ANNS]]、[[Vector-Search]]、[[Graph-Index]]、[[Approximate-Nearest-Neighbor]]
- **同类系统**：[[DiskANN]]、[[Starling]]、VBASE、[[HNSW]]、FusionANNS
- **同会议**：[[MLSys-2026]]
- **对比**：Terminus vs IO-Budget（rank-aware utility vs 固定 I/O budget）；vs VBASE（细粒度 per-I/O vs 粗粒度 queue 稳定判据）；vs Starling 无早停（同 k 更高吞吐，或相对小 k 基线 **3.2×** QPS 且准确率更好）
