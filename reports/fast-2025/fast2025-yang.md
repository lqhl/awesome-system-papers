# Oasis: An Out-of-core Approximate Graph System via All-Distances Sketches

**作者**：Tsun-Yu Yang, Yi Li, Yizou Chen, Bingzhe Li, Ming-Chang Yang（The Chinese University of Hong Kong, The University of Texas at Dallas）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/yang
**源文件**：[fast2025-yang.pdf](../../papers/fast-2025/fast2025-yang.pdf)

---

## 一、背景

图（Graph）是表达现实世界关系的核心数据结构，广泛应用于社交网络分析、推荐系统、影响力传播等场景。这些应用的核心需求是获取顶点的"邻域信息"——即一个顶点如何与图中其他顶点相连。然而，随着图规模指数级增长（如 Twitter 图有 4200 万顶点、14 亿条边），精确的图遍历计算变得极其耗时，甚至在合理时间内无法完成。

All-Distances Sketch（ADS）是一种理论上成熟的近似图处理技术。它为每个顶点构建一个概率性的邻域摘要数据结构，可以高效估计 closeness centrality、shortest-path distance、influence 等多种图属性，且提供理论精度保证。ADS 的优势在于三点：多功能性、可控精度保证、近线性的构建时间复杂度。

---

## 二、要解决的问题

尽管 ADS 理论成熟，但在实际大规模图处理中存在严重的工程瓶颈：

1. **内存开销巨大**：ADS 数据结构的总大小为 O(|V|k log|V|)，可达原始图的 30x-60x。例如 512GB 的图，其 ADS 可能需要 30TB 内存，远超当前机器的内存容量。

2. **现有方案只关注内存场景**：已有研究主要在全内存环境下运行 ADS，限制了可处理的图规模。SOTA 构建算法虽然将边遍历次数从 O(VE) 降至 O(Ek log V)，但其内存需求反而更高（因为随机访问所有顶点的 ADS）。

3. **传统 out-of-core 图系统不适用**：传统图系统优化的是边数据的 I/O，而 ADS 场景中最大的数据是 ADS 本身而非边。此外，ADS 构建同时从所有顶点进行最短路径搜索，活跃顶点规模可达 O(V²)，传统图系统无法处理。

4. **ADS 估计缺乏系统支持**：ADS 估计需要按需加载不同顶点的 ADS，缺乏用户友好的编程接口和 I/O 优化机制。

---

## 三、洞察与设计

**关键洞察**：ADS 的极致加速能力（数量级的性能提升）可以弥补存储 I/O 的低带宽劣势，而 ADS 巨大的数据量恰好适合存放在廉价大容量的存储设备上——两者形成天然的互补关系（synergy）。

基于这一洞察，Oasis 设计为首个 out-of-core ADS 图系统，核心思路是通过分区（partitioning）将 ADS 管理在存储上，同时通过系统级优化减少不必要的 I/O：

**ADS 构建模块**：
- **分区式 ADS 构建**：将 SOTA 的逐顶点遍历转为 scan-and-merge 方式，所有顶点同时开始搜索，按迭代推进直到收敛。用户可通过分区数 P 控制内存用量，满足 O(Vk log V) / 2P < M。
- **Lock-free Edge Layout**：将 edge grid 按目标顶点 ID 范围切分为不相交的 block，使不同线程更新不同 ADS，避免锁竞争。
- **Active Data Separation**：将每轮迭代新产生的活跃 ADS entry 单独存储在独立文件中，下一轮直接加载该文件而非扫描整个 ADS 结构，I/O 从 O(Vk log V · P · I) 降至 O(2 · Vk log V)。
- **Selective ADS Accessing**：在构建接近收敛时，先扫描边数据确定哪些 ADS 需要加载，再选择性加载，避免加载整个分区。

**ADS 估计模块**：
- **统一编程框架**：支持 single-ADS 和 dual-ADS 两类估计器，用户只需定义估计函数并填充查询队列。
- **Locality-aware Query Assignment**：按目标顶点 ID 排序查询，使同一线程尽量复用已加载的 ADS，提升 I/O 利用率。
- **Grid-based Estimation**：针对 dual-ADS 查询，按 ADS 分区将查询组织成网格，顺序处理相邻网格时复用已加载的分区。

---

## 四、实现细节

- **ADS 构建**基于转置图 G^T 进行，先创建转置图并分区，再迭代式地更新每个目标分区的 ADS。每轮迭代遍历所有 (P_x, P_y) 的组合，加载目标分区 P_x 的 ADS 和源分区 P_y 的活跃 ADS 及边数据，执行 ADS 方程更新。
- **Lock-free edge layout** 通过两次边数据扫描实现：第一次收集邻居信息确定每个 block 的目标顶点 ID 范围，第二次按目标顶点 ID 重排边。
- **Active data separation** 将新增的活跃 ADS entry 写入独立文件，下一轮直接读取并在处理完后批量删除。
- **估计框架**中每个线程维护一个 8MB 的内存缓冲区和一个 bitmap 追踪待加载的 ADS，通过贪心策略批量加载能装入缓冲区的查询所需 ADS。
- **最终调整阶段**：ADS 构建完成后，按距离递增排序每个顶点的 ADS entry，并为估计器生成辅助数据。
- 开源代码：https://github.com/tsunyuyang/Oasis

---

## 五、实验结果

**实验平台**：HPE ProLiant DL560 Gen10，Intel Xeon Platinum 8160 CPU，32×32GB DDR4-2666 内存，2×1TB Samsung NVMe SSD（总顺序读 6.0GB/s），16 线程，Debian GNU/Linux 9。

**评估图数据集**：

| 图 | 顶点数 | 边数 | 类型 |
|---|---|---|---|
| Pokec | 1.6M | 31M | 有向 |
| soc-LiveJournal | 4.8M | 69M | 有向 |
| hollywood2009 | 1.1M | 113M | 无向 |
| Twitter | 42M | 1.4B | 有向 |

**ADS 构建结果**（k=32，16 分区）：

| 指标 | Basic | SOTA | Oasis |
|---|---|---|---|
| soc-LJ 时间 | ~2.6 天 | 424 秒 | ~754 秒 |
| soc-LJ 内存 | 14.1GB | 33.1GB | ~2.4GB |
| Twitter 时间 | ~472 天 | 3.4 天 | ~6 天 |
| 内存节省（vs SOTA） | - | - | **13.8x** |
| 时间开销（vs SOTA） | - | - | 1.79x |

**ADS 估计结果**（closeness centrality，k=32）：

| 方案 | Twitter 时间 | Twitter 内存 | 精度 |
|---|---|---|---|
| Ligra+（精确） | ~50 天 | 11GB | 100% |
| In-memory ADS | 0.014 秒 | 147GB | 95.4% |
| Oasis（out-of-core） | 0.024 秒 | 1.4GB | 95.4% |

**关键数据**：
- 内存 ADS 估计 vs Oasis：Oasis 慢 2.9x，但内存节省 **42x**
- Locality-aware query assignment 平均提升 40.7%
- Grid-based estimation 提升 11.8%-16.7%
- 各设计贡献：Active data separation 提升 3.3x-4.2x，Lock-free layout 提升 1.76x-2.97x，Selective ADS accessing 提升 ~11.1%
- 精度随 k 增大而提高，k=32 时 closeness centrality 精度约 95.4%

---

## 六、批判性分析

1. **图规模仍然有限**：最大的 Twitter 图仅 1.4B 边，对应 ADS 大小在 TB 级别以内。论文标题强调"large-scale"，但未评估百亿边级别的图（如 Common Crawl web graph），此时分区数可能需要极大，性能退化情况未知。

2. **估计应用的覆盖面选择性展示**：ADS 理论上支持 7 类估计器，但实验只评估了 closeness centrality 和 closeness similarity 两种，以"工作方式类似"为由省略其他。不同估计器的 I/O 模式和计算复杂度可能差异显著，全面评估更有说服力。

3. **存储设备的假设较强**：实验使用 2 块高端 NVMe SSD（6GB/s 顺序读），这对"大多数用户"的假设偏乐观。在普通 SATA SSD 或 HDD 上，I/O 瓶颈会更严重，论文未讨论存储介质对性能的影响。

4. **与分布式方案的对比缺失**：论文将自己定位为单机方案，但未与分布式图处理系统（如 PowerGraph、Pregel）在多机环境下的比较。对于 30TB 级 ADS，分布式内存方案可能更实际。

5. **精度指标的呈现不够细致**：仅报告 NRMSE 作为精度指标，未展示不同查询的精度分布（如 worst case、tail latency 对应的精度）。对于实际应用而言，平均精度 95.4% 可能掩盖某些顶点估计误差很大的情况。

6. **分区数选择缺乏指导**：虽然 Section 4.4 展示了不同分区数的影响，但仅在 soc-LiveJournal 上做了实验。不同图结构（如幂律度分布 vs 均匀度分布）对最优分区数的影响未探讨。

---

## 七、总结

Oasis 是首个基于 All-Distances Sketch 的 out-of-core 近似图处理系统，通过分区式构建、lock-free edge layout、active data separation、selective ADS accessing 等系统优化，在存储上高效管理 ADS，以 1.79x 的构建时间代价换取 13.8x 的内存节省，以 2.9x 的估计时间代价换取 42x 的内存节省。系统适用于单机环境下大规模图的近似查询处理，但目前仅在中等规模图上验证，对超大规模图和不同存储介质的适用性有待进一步探索。
