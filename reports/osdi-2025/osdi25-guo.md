# Achieving Low-Latency Graph-Based Vector Search via Aligning Best-First Search Algorithm with SSD

**作者**：Hao Guo, Youyou Lu*（清华大学）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/osdi25/presentation/guo
**源文件**：[osdi25-guo.pdf](../../papers/osdi-2025/osdi25-guo.pdf)

---

## 一、背景

高维向量搜索（Vector Search）是推荐系统、RAG 等场景的核心技术。图索引（Graph-based Index）因其在高精度下的低延迟优势，成为近似最近邻搜索（ANNS）的主流方案。随着数据规模增长到十亿级，越来越多的组织选择将 ANNS 索引存储在 SSD 上以降低成本。然而，图索引在 SSD 上的搜索延迟远高于内存——DiskANN 在 0.9 recall 下延迟是内存 Vamana 的 4.18×，0.99 recall 下为 3.14×。这一巨大的延迟差距限制了 SSD 上图索引的实际应用。

---

## 二、要解决的问题

现有 on-disk 图索引延迟高的根本原因是 **best-first search 算法与 SSD I/O 特性之间的不匹配**，具体体现为两个问题：

1. **搜索步骤间的有序计算与 I/O（Ordered Compute and I/O）**：Best-first search 在每一步中，当前 I/O 批次依赖上一步的计算和 I/O 完成。SSD I/O 延迟是计算延迟的 7.43×，但这段长 I/O 时间无法与计算重叠，白白浪费。

2. **每步内的同步 I/O（Synchronous I/O）**：Best-first search 使用 beam width W > 1 来并行读取多条记录，但必须同步等待整个批次中所有 I/O 完成。由于 SSD I/O 延迟波动，实际 I/O pipeline 利用率仅 76%（W=8），导致大量等待时间。

---

## 三、洞察与设计

**关键洞察**：图索引中 best-first search 的计算与 I/O 之间存在 **伪依赖（pseudo-dependency）**——每一步要读取哪些邻居，仅由内存中的 candidate pool（包含邻居 ID）即可决定，无需等待正在进行的 I/O 或计算完成。这是因为图索引中每个向量有多条搜索路径（多条入边），best-first 只是估计一条较短路径而非唯一路径，因此可以在不影响搜索收敛性的前提下调整算法。

基于此洞察，论文提出 **PipeSearch** 算法：

- **打破严格的计算-I/O 顺序**：当 I/O pipeline 未满时，PipeSearch 异步发起对 candidate pool 中当前最近未读邻居的读取请求，不等待已有 I/O 或计算完成。与此同时，best-effort 地探索已读回但未探索的邻居。
- **实现 compute-I/O 重叠**：计算和 I/O 在同一量级的延迟（µs 级），重叠后可获得约 1.7× 加速。
- **提高 I/O pipeline 利用率**：异步 I/O 填充 pipeline，避免因等待慢请求而闲置。

进一步，论文实现 **PipeANN** 系统，解决 PipeSearch 的延迟-吞吐量矛盾：

1. **两阶段搜索（Approach + Converge）**：Approach 阶段 I/O 浪费大，使用内存索引优化入口点并保持小 pipeline width（W=4）；Converge 阶段 I/O 浪费递减，动态增大 pipeline width。
2. **动态 Pipeline 宽度调整**：通过监测已召回向量数量和 I/O 命中率，动态增大 W，在低延迟与高吞吐之间取得平衡。
3. **算法优化减少 I/O 浪费**：当多个 I/O 同时完成时，不立即填满 pipeline，而是逐一发起 I/O 并探索一个邻居，确保每个 I/O 决策最多缺失 W 个邻居的信息，减少投机 I/O 浪费。

---

## 四、实现细节

- **索引布局**：磁盘存储邻接表（向量 + 邻居 ID），内存存储 PQ 压缩向量（32 bytes/vector）和小型图索引用于入口点优化。
- **入口点优化**：采样 1% 数据点构建内存 Vamana 索引（maximum out-degree=32），搜索时先遍历内存索引选择入口点（L_mem=10）。
- **异步 I/O**：使用 Linux io_uring，每线程独立 io_uring 实例，prep_read 发送请求，peek_batch_cqe 非阻塞轮询完成。启用 SQ polling 进一步降低 I/O 提交延迟。
- **Converge 阶段触发**：估计已召回向量数 n_v 达到阈值（默认 5）后开始动态调整 pipeline width。
- **动态调整策略**：默认使用 dynamic approach——监测已完成 I/O 中向量仍在 candidate pool 中的比例，超过 0.9 时将 W 增加 1。最大 W 限制为 32。
- **初始化重叠**：第一次磁盘 I/O 等待期间并行执行 PQ table 初始化，使用 AVX512 non-temporal load 避免 cache pollution。
- **内存开销**：十亿级数据集约 40GB 内存（32GB PQ 压缩向量 + ~3GB 内存索引 + 少量辅助结构），磁盘使用 600GB+，内存/磁盘比约 1:15。

---

## 五、实验结果

**实验平台**：2×28-core Intel Xeon Gold 6330, 512GB RAM, Samsung PM9A3 3.84TB NVMe SSD, Ubuntu 22.04。

**百万级数据集（100M 向量）延迟对比（0.9 recall10@10，单线程）**：

| 系统 | SIFT | SPACEV | DEEP |
|------|------|--------|------|
| PipeANN | **最低** | **最低** | **最低** |
| vs DiskANN | 39.1% 延迟 | 39.1% 延迟 | 39.1% 延迟 |
| vs Starling | 48.5% 延迟 | 48.5% 延迟 | 48.5% 延迟 |
| vs SPANN | 低 70.6% | 低 70.6% | 低 70.6% |

**百万级数据集吞吐量（0.9 recall10@10，56 线程）**：PipeANN 平均优于其他系统 1.35×。

**十亿级数据集（1B 向量）**：

| 指标 | SIFT1B | SPACEV1B |
|------|--------|----------|
| PipeANN 延迟 | 0.719ms | 0.578ms |
| vs DiskANN | 35.0% 延迟 | — |
| PipeANN QPS | 19.4K | 26.1K |
| vs DiskANN | 1.71× 吞吐 | — |

**与内存索引对比（100M 向量）**：

| Recall | PipeANN vs Vamana（内存） |
|--------|--------------------------|
| 0.8 | 3.38× 延迟 |
| 0.9（SIFT） | 2.02× 延迟 |
| 0.9（DEEP） | 1.14× 延迟 |

**Breakdown 分析**（SIFT100M, 0.9 recall）：
- Baseline → +PipeSearch: 延迟降至 55.1%，吞吐降至 88.5%
- +AlgOpt: 吞吐恢复至 1.08×，I/O/search 降至 91.8%
- +Dynamic Pipeline: 延迟进一步降至 81.1%（0.99 recall），吞吐增 1.07×

---

## 六、批判性分析

1. **吞吐量代价被淡化**：PipeANN 在高 recall（0.99）下吞吐仅为 Starling 的 0.80×，在低 recall（0.8）下吞吐比 ideal DiskANN 低 31.6%–34.1%。论文强调 0.9 recall 下的优势，但实际生产系统通常追求更高 recall，此时吞吐劣势明显。

2. **与 Starling 正交但未集成的说法缺乏说服力**：论文声称 PipeANN 可以采用 Starling 的 reordering 技术来进一步减少 I/O，但以"十亿级数据集开销大"为由未做集成实验。这恰恰是最需要验证的场景——在 reordering 后 PipeSearch 的投机 I/O 浪费是否仍有优势？

3. **精度损失分析不够严谨**：论文将 PipeANN 类比为 candidate pool length 为 L-W 的 best-first search，但这只是上界估计。实际的精度损失取决于数据分布和图结构，论文仅在有限数据集上验证了"至少 95.9% recall"，缺少对 worst-case 分布的分析。

4. **参数敏感性讨论不足**：系统涉及多个关键参数（起始 W=4、触发阈值 n_v=5、动态调整比例阈值 0.9、最大 W=32），论文仅简要提及默认值，缺少系统的参数敏感性分析。虽然 §5.6 比较了 static 和 dynamic 两种调整策略，但对各参数如何影响不同数据集和 recall 目标的讨论有限。

5. **基线对比不完全公平**：论文为 DiskANN 和 Starling 也替换了 io_uring，但 PipeANN 额外启用了 SQ polling 而其他系统没有。虽然论文解释了 SQ polling 对 best-first search 无益，但这使得部分性能提升归因变得模糊。

6. **实际部署场景考量不足**：论文假设单查询延迟优化场景，但现实中 ANNS 系统通常需要处理大量并发查询。PipeANN 每线程独占 io_uring 实例并占用更多 I/O 带宽，在高并发场景下资源争用问题未被讨论。

---

## 七、AI Infra / MLSys 视角

1. **对 RAG 系统的直接价值**：PipeANN 将十亿级向量搜索延迟降至亚毫秒级（0.578–0.719ms），这对 RAG pipeline 中的检索环节意义重大。在 LLM 推理的 prefill 阶段前完成向量检索，可以减少端到端延迟，特别是在 streaming 场景下。

2. **算法-硬件对齐的设计范式**：PipeSearch 的核心思路——识别算法中的伪依赖，通过异步/投机执行与硬件 pipeline 对齐——可以迁移到其他 AI Infra 场景：
   - **KV Cache 管理**：在 PagedAttention 等方案中，KV cache 的加载与注意力计算之间可能存在类似的伪依赖，可以用 pipeline 思路优化。
   - **分布式推理中的 tensor 通信**：All-Reduce 等通信操作与部分计算之间的依赖关系可以进一步松弛。

3. **远程内存场景的延伸**：论文明确指出 PipeSearch 可用于 RDMA/CXL 远程内存（µs 级延迟 + 并行访问），这与当前 AI Infra 中的内存池化（Memory Pooling）趋势高度相关。在 disaggregated memory 架构下，embedding table 或 KV cache 的远程访问可以借鉴 PipeSearch 的 pipeline 思路。

4. **值得跟进的方向**：
   - PipeSearch + 向量量化（如 RaBitQ）的联合优化：减少内存占用的同时利用 pipeline 加速。
   - 将 PipeSearch 思路应用到 GPU 上的图搜索：GPU 的 memory hierarchy 同样存在计算-访存延迟不匹配的问题。
   - 探索 PipeSearch 在 filtered ANNS（带属性过滤的向量搜索）场景下的适用性。

---

## 八、总结

PipeANN 通过识别 best-first search 中计算与 I/O 的伪依赖关系，提出 PipeSearch 算法将搜索过程与 SSD 异步并行 I/O 特性对齐，在不牺牲搜索精度的前提下大幅降低了 on-disk 图索引的搜索延迟。在十亿级数据集上达到 DiskANN 35% 的延迟和 1.71× 的吞吐，将 on-disk 与 in-memory ANNS 的延迟差距从 4.18× 缩小至 1.14×–2.02×。主要局限在于投机 I/O 带来的吞吐量损失，特别是在高 recall 和高并发场景下。整体而言，论文展示了"将算法与硬件特性对齐"这一设计思路在系统优化中的巨大潜力。
