# PipeANN: Achieving Low-Latency Graph-Based Vector Search via Aligning Best-First Search Algorithm with SSD

## 论文基本信息

| 字段 | 内容 |
|------|------|
| 标题 | Achieving Low-Latency Graph-Based Vector Search via Aligning Best-First Search Algorithm with SSD |
| 作者 | Hao Guo, Youyou Lu（清华大学） |
| 会议 | OSDI 2025 |
| 链接 | https://www.usenix.org/conference/osdi25/presentation/guo |

## 研究背景与动机

向量搜索是推荐系统和 RAG 等应用的核心技术。ANNS（近似最近邻搜索）在大规模数据集（十亿级）上更受欢迎，其中**图索引**因低搜索延迟和高精度而受到青睐。

**SSD 存储图索引的原因**：
- 十亿级数据集无法全部放入内存
- SSD 成本效益高

**核心问题**：现有图索引在 SSD 上**无法维持内存中的低搜索延迟**：
- DiskANN 搜索延迟是 Vamana（内存）的 4.18×（0.9 recall）和 3.14×（0.99 recall）
- 在高召回率场景（≥0.9），延迟差距更明显

## 核心问题

为什么图基 ANNS 在 SSD 上延迟高？

1. **有序的跨搜索步计算与 I/O**：Best-first 算法在每一步按 batch 读取邻居，产生计算-I/O 顺序依赖。长 I/O 延迟（是计算的 7.43×）无法与计算 overlap
2. **每步同步 I/O**：即使使用 W>1 的 beam search，仍然同步等待整个 batch 完成，导致 I/O 管道利用率低（76% @ W=8，58% @ W=32）

## 主要贡献

1. **发现最佳优先搜索算法限制**：分析其与 SSD I/O 特性的不匹配
2. **PipeSearch 算法**：通过 compute-I/O overlap 和更好的 I/O 管道利用加速搜索
3. **PipeANN 系统**：结合动态 pipeline 调整和算法优化，解决 PipeSearch 的吞吐量问题
4. **10 亿级数据集验证**：PipeANN 延迟仅为 DiskANN 的 35.0%，吞吐量高 1.71×

## 研究方法与设计

### 关键洞察

**可行性的关键**：
- 图基 ANNS 有多条搜索路径，best-first 算法估计的是"短路径"而非"唯一路径"
- 调整搜索算法不会阻止收敛，只会改变路径

### PipeSearch 算法

**核心改进**：在 best-first 搜索中引入**伪依赖**概念——每步要读取哪些邻居**可以仅由内存中的候选池决定**，无需等待进行中的 I/O 或计算完成。

**PipeSearch 流程**：
1. 维护候选池 P（固定长度 L）和 I/O 管道 Q（宽度 W）
2. **异步填充 I/O 管道**：当 Q 未满时，根据当前候选池异步发出读请求，无需等待之前的 I/O 完成
3. **Overlap 计算**：在 I/O 重叠中，best-effort 方式探索最近邻
4. **Poll I/O 完成**：轮询 I/O 完成，将向量加入未探索集合

**优势**：
- 计算和 I/O 重叠
- I/O 管道利用率更高

### PipeANN：解决 PipeSearch 吞吐量问题

PipeSearch 追求低延迟但吞吐量低（每次搜索发出更多 I/O）。PipeANN 提出两个优化：

**优化 1：动态管道宽度调整**

发现：I/O 浪费随搜索进展**减少**（候选池中未探索 top-k 邻居数增加）

方案：在收敛阶段使用更大 W（更多 overlap），在接近阶段使用较小 W（减少浪费）

**优化 2：算法优化——多 I/O 完成时控制重探索**

问题：多个 I/O 同时完成时，会积累大量待探索邻居

方案：每完成一个 I/O 就探索一个邻居 + 发出一个 I/O，而不是一次发出多个 I/O 充满管道

效果：平衡 full pipeline（PipeSearch）和减少 I/O 浪费（best-first）

### 与现有工作的正交性

PipeANN 的设计与以下技术**正交**，可直接结合：
- Entry point 优化（LSH-APG、Starling）
- 自适应早停（Proxima、Learned Adaptive Early Termination）
- 图重排序（Starling）

## 关键实现细节

- 使用 56 线程进行并行 ANNS 搜索
- 动态管道宽度根据 L 和 recall 目标自动调整
- 评估在 SIFT（128 维 uint8）和 DEEP（96 维 float）数据集上进行

## 实验结果与分析

### 100M 级数据集

**搜索延迟（recall=0.9）**：
- 比 DiskANN 低 60.9%/51.5%（SIFT/SPACEV）
- 比 SPANN 低 70.6%
- Vamana（内存）1.14×-2.02×（差距已大幅缩小）

**吞吐量（recall=0.9）**：
- 比其他系统高 1.35×

### 10 亿级数据集（SIFT1B、SPACEV1B）

**搜索延迟（recall=0.9）**：
- SIFT1B：0.719ms（是 SIFT100M 的 1.28×）
- SPACEV1B：0.578ms（是 SPACEV100M 的 1.09×）
- **仅为 DiskANN 的 35.0%**

**吞吐量**：
- SIFT1B：19.4K QPS（是 SIFT100M 的 79.9%）
- SPACEV1B：26.1K QPS（是 SPACEV100M 的 98.0%）
- **比 DiskANN 高 1.71×**

### 分解分析

- +Pipe（仅 PipeSearch）：延迟降至 55.1%（相比 Baseline）→ 但吞吐量降至 88.5%
- +AlgOpt（算法优化）：吞吐量提升 1.08×
- +Dynamic Pipeline（动态管道）：延迟进一步降至 81.1%（0.99 recall），吞吐量提升 1.07×

### 准确性保持

- PipeANN 与 DiskANN 相比，recall 保持 ≥95.9%（≥0.9 recall 时 ≥98.8%）
- 准确性损失随 L 增大而减小

## 潜在问题与局限性

1. **吞吐量 vs 延迟权衡**：PipeANN 在低准确性（recall=0.8）时吞吐量比"理想 best-first（W=1）"低 31.6%，这是一个真实存在的权衡
2. **搜索精度与最优参数**：动态管道宽度需要根据 recall 目标调整，L 参数选择也影响准确性
3. **未探索 I/O 积累**：宽管道 + 慢邻居探索时可能积累大量未探索邻居，导致次优 I/O 决策
4. **多线程场景下的管道管理**：当多个搜索并发时，SSD 的并行 I/O 能力如何在多个管道间分配
5. **静态索引构建开销**：PipeANN 继承了 Vamana 的索引构建过程，在 10 亿级数据集上构建时间可能很长（论文未报告）
6. **与学习型索引的结合**：未探索与其他学习型 ANNS 方法的结合可能性

## 未来工作方向

1. 与图重排序技术（Starling）结合
2. 扩展到远程内存和其他存储介质
3. MoE 稀疏注意力索引支持

## 个人评注

**优点**：
- 对 best-first 算法与 SSD I/O 特性不匹配的分析深刻，伪依赖的洞察非常有价值
- 动态管道宽度调整是一个非常实用的优化，能够在不同搜索阶段自适应调整
- 实验覆盖面广，从 microbenchmark 到 10 亿级真实数据集
- **35% 的 DiskANN 延迟**这一结果在实际应用中非常有价值

**潜在争议**：
- PipeANN 的动态管道调整在 0.9 和 0.99 recall 之间的表现差异值得进一步分析——当 recall 提高时，approach 阶段（pipeline 不饱和）占比增加，此时性能退化可能更明显
- 论文未报告**索引构建时间**，这对生产环境部署非常重要
- **吞吐量降低 31.6%**（与理想 best-first 相比）在高吞吐量场景下可能不可接受，需要在具体应用场景中权衡
- 与 SPANN 的比较略显不公平——SPANN 是混合内存-SSD 架构，不是纯 SSD 方案

总体而言，PipeANN 是一项扎实的系统工作，对 SSD 上图索引搜索的 latency-throughput 权衡提供了深入分析和有效解决方案。
