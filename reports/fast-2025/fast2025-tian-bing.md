# Towards High-throughput and Low-latency Billion-scale Vector Search via CPU/GPU Collaborative Filtering and Re-ranking

**作者**：Bing Tian, Haikun Liu*, Yuhang Tang, Shihai Xiao, Zhuohui Duan, Xiaofei Liao, Hai Jin, Xuecang Zhang, Junhua Zhu, Yu Zhang（华中科技大学 & 华为）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/tian-bing
**源文件**：[fast2025-tian-bing.pdf](../../papers/fast-2025/fast2025-tian-bing.pdf)

---

## 一、背景

近似最近邻搜索（ANNS）是数据库和 AI 基础设施的关键组件，尤其在 Retrieval Augmented Generation（RAG）场景中，ANNS 可能占 LLM 查询总延迟的约 50%。随着向量数据集规模增长到十亿级别，现有 ANNS 系统面临性能、成本和精度三方面的挑战。

主流 ANNS 方案分为两类索引技术：IVF（倒排文件索引）和图索引。IVF 索引（如 SPANN）将数据集分为多个 posting list 存储在 SSD 上，图索引（如 DiskANN）使用近邻图结构。为降低内存开销，Product Quantization（PQ）可将高维向量压缩至原大小的 5%，但属有损压缩，需要 re-ranking 恢复精度。GPU 可加速 PQ 距离计算，但 HBM 容量有限，十亿级数据集会导致 GPU 与 CPU 之间大量数据交换。

---

## 二、要解决的问题

1. **SSD-based ANNS 吞吐量低**：SPANN 在并发查询下吞吐量极为有限，仅 4 个 CPU 线程即达到峰值 QPS，因为多查询并发读取大量 posting list 导致严重 SSD I/O 争用。

2. **HI + PQ + GPU 简单组合反而性能更差**：直接将 PQ 和 GPU 加速叠加到 SPANN 上，端到端延迟不降反升，QPS 甚至下降 65%。根本原因在于：(a) GPU HBM 无法容纳所有 PQ 压缩后的 posting list（因 boundary replication 使索引膨胀 8×），导致 CPU-GPU 间大量数据交换；(b) PQ 引入的 re-ranking 过程增加 70% 的 I/O 次数；(c) re-ranking 过程中原始向量（128-384 bytes）远小于 SSD 最小读粒度（4KB），造成严重读放大。

3. **Re-ranking 数量因查询而异**：不同查询达到目标精度所需的 re-ranking 向量数量差异极大（从几个到数十个），静态配置 re-ranking 数量会导致大量不必要的 I/O 和计算。

---

## 三、洞察与设计

**关键洞察**：IVF 索引中 posting list 的 boundary replication 机制导致索引体积膨胀 8×，但 posting list 中的向量内容（PQ code）和向量 ID 可以解耦——GPU HBM 只需存储不重复的 PQ 压缩向量（而非膨胀后的 posting list），主存只需存储 posting list 的向量 ID 列表（不含向量内容），这样就能让十亿级数据集的所有 PQ 向量完全驻留在入门级 GPU 的 HBM 中，从根本上消除 CPU-GPU 间的数据交换瓶颈。

基于此洞察，FusionANNS 提出三个核心设计：

### 1. Multi-tiered Indexing（多层索引）

将数据分布在三个存储层级：
- **主存**：导航图（SPTAG 构建的 centroid 图）+ 每个 posting list 的向量 ID 列表（metadata）
- **GPU HBM**：所有向量的 PQ 压缩码（无重复，不含 posting list 结构）
- **SSD**：原始向量（用于 re-ranking）

由于 HBM 只存储去重后的 PQ 向量而非膨胀的 posting list，即使入门级 GPU（如 V100 32GB）也能容纳十亿级数据集的所有压缩向量。

### 2. CPU/GPU Collaborative Filtering（协同过滤）

查询流程：
1. GPU 生成查询向量的 PQ distance table
2. CPU 遍历内存中的导航图，找到 top-m 最近 posting list
3. CPU 收集这些 posting list 的向量 ID（不含向量内容）
4. CPU 将向量 ID 传给 GPU（轻量数据传输）
5. GPU 对向量 ID 去重，从 HBM 读取对应 PQ 向量，计算距离
6. GPU 排序返回 top-n 候选向量 ID
7. CPU 从 SSD 读取原始向量进行 re-ranking

### 3. Heuristic Re-ranking（启发式 re-ranking）

将 re-ranking 分为多个 mini-batch 顺序执行，每个 mini-batch 完成后用 max-heap 的变化率（change rate Δ）判断是否继续。当连续 β 次 Δ < ε 时提前终止。最优参数为 ε=0.1, β=1, BatchSize=k。

### 4. Redundant-aware I/O Deduplication（冗余感知 I/O 去重）

- **优化存储布局**：将与同一 centroid 相近的原始向量紧凑存储在相同 SSD page 上，提高空间局部性
- **Mini-batch 内去重**：同一 mini-batch 中映射到相同 SSD page 的 I/O 请求合并
- **Mini-batch 间去重**：利用 DRAM buffer 消除后续 mini-batch 的重复读取

---

## 四、实现细节

- **代码规模**：22K 行 C++ 和 CUDA 代码
- **查询处理**：每个 CPU 线程处理一个独立查询
- **GPU 内存管理**：系统初始化时加载 PQ 向量到 HBM，剩余空间作为内存池划分为多个独立 block，每个 block 分配给一个查询，避免频繁内存分配和锁争用
- **GPU Kernel 设计**：每个向量分配多个 GPU 线程按维度并行计算距离；向量 ID 去重使用并行 hash 算法（spinlock 保护 hash table）
- **Direct I/O**：使用 Direct I/O 充分利用 NVMe SSD 低延迟特性
- **索引构建**：使用 hierarchical balanced clustering 算法离线分区数据集，每个向量最多分配到 8 个 cluster，posting list 数量约为向量总数的 10%

---

## 五、实验结果

**实验平台**：2× Intel Xeon 2.2GHz 64-core CPU，1TB 主存（SSD-based 方案仅使用 64GB），NVIDIA V100 32GB GPU，Samsung 990Pro 2TB SSD。

**数据集**：

| 数据集 | 维度 | 原始数据大小 | 数据类型 | 领域 |
|--------|------|-------------|----------|------|
| SIFT1B | 128 | 119GB | uint8 | 图像 |
| SPACEV1B | 100 | 93GB | int8 | 网页搜索 |
| DEEP1B | 96 | 358GB | float32 | 图像 |

**基线**：SPANN、DiskANN（SSD-based）、RUMMY（GPU-accelerated in-memory）以及 SPANN-GPU、DiskANN-GPU 变体。

### 主要结果（Recall@10=90%）

| 对比系统 | QPS 提升 | 成本效率 (QPS/$) 提升 | 内存效率 (QPS/GB) 提升 |
|---------|---------|---------------------|----------------------|
| vs SPANN | 9.4-13.1× | 5.67-8.78× | 2.7-13.1× |
| vs DiskANN | 3.2-4.3× | 2.0-2.5× | 2.9-3.8× |
| vs RUMMY | 2.0-4.9× | 2.25-6.82× | 5.9-32.4× |

### 各技术贡献分解

- Multi-tiered Indexing (CPU)：QPS 提升 1.5-4.2× vs SPANN
- Multi-tiered Indexing (GPU)：QPS 提升 5.9-6.8× vs SPANN
- + Heuristic Re-ranking：额外提升 QPS 39%，减少 I/O 30%
- + I/O Deduplication：额外提升 QPS 17%，减少 I/O 23%

### 扩展性

FusionANNS 在 1-64 线程范围内 QPS 持续增长。SPANN 在 4 线程即饱和，RUMMY 在 16 线程后 QPS 反降（PCIe 带宽争用）。

---

## 六、批判性分析

1. **GPU 选型局限性**：实验仅使用 V100（已过时两代），未评估更新的 GPU（如 A100/H100）。V100 的 32GB HBM 对十亿级 PQ 向量恰好够用，但论文未讨论当数据规模进一步增长（如百亿级）时 HBM 容量不足的情况。

2. **基线公平性存疑**：将 DiskANN 纳入对比但承认其设计目标不同（高吞吐而非低延迟），RUMMY 被扩展为支持高精度查询的版本，这些调整可能不利于基线系统发挥最佳性能。SPANN-GPU 和 DiskANN-GPU 是作者自己实现的 GPU 加速版本，不是原系统作者的优化实现。

3. **成本计算过于简化**：系统成本仅列出硬件采购价格，未考虑运维成本、能耗（GPU 功耗）、散热等 TCO 因素。V100 定价 $3000 也远低于市场价（即使二手也不止），这使成本效率数字偏乐观。

4. **Re-ranking 参数敏感性不足**：heuristic re-ranking 的 ε=0.1, β=1 号称是实验调优结果，但论文缺少这些参数对不同数据分布的鲁棒性分析。β=1 意味着只要一次 change rate 低于阈值就终止，这在高方差查询分布下可能导致精度不稳定。

5. **索引构建开销被忽略**：论文未报告多层索引的离线构建时间和资源消耗，对于需要频繁更新索引的在线服务场景，这可能是重要的实际限制。

6. **单 SSD 配置**：实验仅使用单块 SSD，未评估多 SSD 配置下的 I/O 并行度提升。考虑到该系统的核心瓶颈在 SSD I/O，多 SSD 对基线系统（SPANN）的提升可能同样显著，缩小与 FusionANNS 的差距。

---

## 七、AI Infra / MLSys 视角

1. **RAG 系统的向量检索加速**：FusionANNS 直接面向 RAG 场景（ANNS 占 LLM 查询 ~50% 延迟），其 CPU/GPU 协同方案在 GPU 主要用于 LLM 推理的部署中特别有吸引力——只需一块入门级 GPU 即可同时服务 ANNS 和小规模推理任务。

2. **数据分层存储思想的迁移**：多层索引的核心思路——将不同粒度的数据放在最匹配的存储层级（ID→主存，PQ code→HBM，raw data→SSD）——可以迁移到 KV cache 管理、模型参数分层存储等 AI Infra 场景。

3. **Heuristic early termination 的通用性**：基于 stability detection 的提前终止策略不仅适用于 re-ranking，也可推广到 speculative decoding 的 verification 阶段、beam search 的候选淘汰等场景。

4. **值得跟进的研究方向**：
   - **FusionANNS + CXL**：利用 CXL 扩展内存池，将导航图和 metadata 放入 CXL-attached memory，释放 DRAM 给 LLM 推理使用
   - **动态 GPU 共享**：在 LLM 推理和 ANNS 之间动态分配 GPU HBM 和计算资源，而非将 PQ 向量固定 pin 在 HBM 中
   - **端到端 RAG 优化**：将 ANNS 与 LLM 推理的 prefill/decode 阶段流水线化，利用 ANNS 查询期间 GPU 的空闲 SM 执行部分推理计算

---

## 八、总结

FusionANNS 是首个在十亿级数据集上同时实现高吞吐、低延迟、低成本和高精度的 GPU 加速 SSD-based ANNS 系统。其核心贡献在于通过多层索引解耦 posting list 结构与向量内容，使 PQ 向量完全驻留在入门级 GPU HBM 中，消除了 CPU-GPU 数据交换瓶颈。配合启发式 re-ranking 和冗余感知 I/O 去重，相比 SPANN 和 RUMMY 分别实现了高达 13.1× 和 4.9× 的 QPS 提升。主要局限在于评估仅基于单块较旧的 GPU 和 SSD，索引构建开销和动态更新能力未被充分讨论。
