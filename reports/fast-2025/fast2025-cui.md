# PIMLex: A High-Performance Learned Index with Processing-in-Memory

**作者**：Lixiao Cui, Kedi Yang, Yusen Li, Gang Wang*, Xiaoguang Liu*（南开大学计算机科学学院）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/cui
**源文件**：[fast2025-cui.pdf](../../papers/fast-2025/fast2025-cui.pdf)

---

## 一、背景

数据处理需求的指数增长使得传统冯·诺依曼架构中 CPU 与内存之间的"内存墙"（memory wall）问题日益严峻。Learned index（学习索引）作为存储系统中的关键组件，利用简单的机器学习模型拟合数据分布的 CDF 来预测 key 的位置，在传统架构上已展现出相比 B+-tree 等传统索引的显著性能优势。然而，learned index 本质上是数据密集型应用——其模型预测和"last mile"搜索都涉及大量内存访问，Intel VTune 分析表明 ALEX 和 LIPP 等先进 learned index 超过 60% 的执行时间花在内存停顿上。

Processing-in-Memory（PIM）技术通过将处理单元直接集成到内存设备中，使计算在数据附近进行，从根本上减少数据搬移。UPMEM 是目前商用可用的通用 PIM 硬件，每个 DIMM 包含 128 个 PIM 模块，每个模块拥有 64MB MRAM 和 64KB WRAM，峰值带宽可达 80GB/s per DIMM——远超传统 DRAM。

---

## 二、要解决的问题

将 learned index 直接部署到 PIM 架构上面临三个非平凡的挑战：

1. **容量冲突**：Learned index 空间放大严重（如 LIPP 可占数据量 5 倍以上的空间），而 UPMEM 每 DIMM 仅 8GB，远小于传统 DRAM 的 64GB/DIMM，无法容纳大规模数据集的完整索引。

2. **模型结构与 PIM 特性不匹配**：PIM 的 DPU 是简单的 32 位 RISC 核心，不支持原生浮点运算（需软件模拟，比整数运算慢数个数量级）。现有 learned index 依赖多层次层级模型，每次查询需要 3-4 次浮点乘法，在 PIM 上的计算开销巨大（单 PIM 模块浮点乘法吞吐仅 1.91 MOPS）。实验表明 BasicLex 约 80% 的 PIM 内核时间花在模型预测上，其中超过 50% 是计算开销。

3. **倾斜负载下的负载不均衡**：PIM 由多个独立模块组成 shared-nothing 架构，通过 range partitioning 分布数据。然而 learned index 的真实工作负载往往高度倾斜（Zipfian），导致部分模块过载而其他空闲。在 skewness=0.99 时，BasicLex 的吞吐量仅为均匀分布的 9.2%-9.9%。

---

## 三、洞察与设计

**关键洞察**：Learned index 的模型查询和 last-mile 搜索中，绝大部分操作是内存访问而非计算，而 PIM 的核心优势恰恰是极高的内存带宽（但计算能力弱）。因此，可以通过"以更多内存访问换取更少计算"（trading more memory access for less computation）的原则来重新设计 learned index 的模型结构，使其与 PIM 的硬件特性对齐。

基于此洞察，PIMLex 提出了三个核心设计：

### 1. 解耦双层结构（Decoupled Two-Layer Structure）

- **Search layer**（PIM 侧）：仅存储从主数据数组中每隔 δ（默认 8）个 key 采样的 anchor key，以及基于 anchor key 训练的模型。通过 range partitioning 分布到多个 PIM 模块。
- **Data layer**（DRAM 侧）：存储完整的 key-value 对（有序数组 + buffer pages + overflow tree）。

查询流程：① 查 partition table 确定目标 PIM 模块 → ② PIM 侧通过 search layer 获得近似位置 → ③ DRAM 侧在数据层中定位精确位置并读写。这样将大部分内存访问转移到高带宽 PIM 上，同时 PIM 空间占用极小（anchor key 数量仅为原始 key 的 1/δ，且不存 value）。

### 2. PIM 友好的模型结构

- **模型搜索方法选择**：对于层级模型的上层，比较 model-based search（需要浮点计算）和 global binary search（纯内存访问）的代价，自底向上选择代价更低的方案。对计算能力弱的 PIM，上层通常选择 global binary search。
- **Lookup-table based model**：将搜索 key 高位与模型斜率的乘法结果预计算并存入查找表（默认 16 个 slot），在运行时用一次表查找替代浮点乘法。虽然预测精度略降（搜索范围从 [Pos_full-ε, Pos_full+ε] 扩大到 [Pos_lower-ε, Pos_upper+ε]），但完全消除了浮点运算。
- **模型放入 WRAM**：将模型存入 PIM 模块的 64KB 快速 SRAM（WRAM），anchor key 放在较慢的 MRAM。若模型过多则加倍 ε 直到能放下。

### 3. Hotness-aware 副本机制

- 将 search layer 分为 N 个 partition，分布到 M 个 PIM 模块（M≥N），热门 partition 创建多个副本。
- 定义 load factor L_i = (T_i/R_i)/(T_total/M)，目标是最小化 L_global = max(L_i)。
- 两阶段负载均衡算法：第一阶段粗估每个 partition 的副本数，第二阶段 fine-tuning（在最忙和最闲 partition 间重分配）。
- 支持热点变化时的快速调整（仅执行第二阶段），以及正常调整（完整两阶段）。

---

## 四、实现细节

- **硬件平台**：基于 UPMEM PIM 实现，使用 4 个 UPMEM DIMM（共 512 个 PIM 模块），每模块 64MB MRAM + 64KB WRAM；另有 4 个传统 DRAM DIMM（128GB）。Host CPU 为 Intel Xeon Silver 4110（16 核）。
- **Anchor interval δ = 8**：primary data array 中每 8 个 key 采样一个 anchor key，使得 DRAM 侧的 last-mile 搜索在一个 cache line 内完成。
- **Search layer partition 数 N = 128**。
- **Insert 流程**：通过 search layer 找到对应 anchor key → 写入 buffer page（有序数组，默认容量 8）→ buffer page 满则写入 overflow tree（修改版 B+-tree，内部节点在 PIM 侧）→ 数据量达阈值（主数组 50%）时触发 merge 重建。
- **并发控制**：primary data array 每 512 个连续 key-value pair 共享一个读写锁；buffer page 和 overflow tree 各有独立锁。
- **流水线执行**：PIM 侧和 DRAM 侧执行重叠，提升多 batch 吞吐。
- **Partition table** 维护在 host 侧，记录每个 partition 的 PIM 模块位置和最小 key。
- **副本调整**：search layer 在 DRAM 保留一份副本，调整期间可通过 DRAM 副本继续服务（但有 CPU 竞争）。

---

## 五、实验结果

### 与 PIM 基线 BasicLex 对比

| 指标 | PIMLex 优势 |
|------|-----------|
| Get 吞吐量（skewed） | 最高 **36.5×** |
| Insert 吞吐量（skewed） | 最高 **9.5×** |
| PIM 执行时间（skewed） | Opt 0.78-0.85s vs Baseline 12.47-12.85s（~**16×** 加速） |

### 与 DRAM-based learned index 对比（200M 数据集）

| 对比对象 | Get | Insert | Mixed |
|---------|-----|--------|-------|
| vs ALEX | 最高 2.2× | 优于 | 最高 3.6× |
| vs LIPP | 最高 3.25× | 优于 | 最高 6.7× |
| vs FINEdex | 最高 3.05× | 优于 | 最高 2.73× |
| vs SALI | 最高 2.84× | 部分数据集略低 | 最高 2.03× |

### 大规模数据集（800M keys，~30GB）

PIMLex 相比 ALEX 在 Get/Insert/Mixed 上分别最高提升 2.47×/2.09×/2.93×。LIPP 和 SALI 因索引大小超出平台内存而无法运行。

### 与 PIM-tree 对比（100M keys）

PIMLex 在 Get 和 Insert 上分别最高超过 PIM-tree 3.79× 和 6.02×。

### 其他实验

- **Range Query**：PIMLex 与 ALEX 性能接近（因需大量 DRAM 侧访问，PIM 优势减弱），优于 LIPP 和 SALI。
- **Update 负载**：Update-heavy 下 PIMLex 优于 ALEX/LIPP/FINEdex/SALI 4%-48%，但数据竞争限制了 PIM 优势。
- **空间效率**：PIMLex 使用的 PIM 空间极小，整体内存效率显著优于 LIPP/FINEdex/SALI。
- **副本调整**：正常调整方法 L_global=1.14（接近最优 1），快速调整随 Num_fine_tune 减小性能下降 10%-31%，但调整时间从 0.45s 降至 0.15s。

---

## 六、批判性分析

1. **硬件公平性存疑**：PIMLex 使用 4 个 UPMEM DIMM + 4 个 DRAM DIMM（共 8 个 DIMM slot），而 DRAM-based 基线在另一台配置 8 个 DRAM DIMM 的服务器上评测。作者声称这对 PIMLex 更公平，但两台服务器 CPU 不同（Silver 4110 vs Silver 4210，后者核数更多、缓存更大），且 UPMEM DIMM 每个仅 8GB 而 DRAM DIMM 32GB——PIMLex 平台总内存容量远小于 DRAM 平台。真正公平的对比应在同一平台上进行或至少控制更多变量。

2. **Insert 性能的短板被轻描淡写**：PIMLex 的 data layer 仍在 DRAM 侧，Insert 操作（尤其是 buffer page 写入和 merge 重建）主要由 host CPU 处理，未能充分利用 PIM。在部分数据集上（如 Books）PIMLex 的 Insert 性能不如 SALI，作者将其归因于 PIM 容量限制并寄希望于未来硬件改进——这本质上承认了当前设计在写入密集场景下的局限。

3. **Merge 重建的代价分析缺失**：当 buffer pages 和 overflow tree 数据量达到主数组 50% 时触发全量 merge 和 search layer 重建。论文没有量化 merge 操作的延迟和对前台请求的影响（尤其在高写入负载下 merge 频率会很高），也没有评估 tail latency。

4. **Skewness 参数单一**：所有 skewed workload 实验仅使用 Zipfian skewness=0.99（接近极端），缺少不同 skewness 程度下的性能变化分析。在中等倾斜度下 PIMLex 的负载均衡优势可能不那么显著。

5. **UPMEM 硬件的代表性**：UPMEM 是目前唯一商用通用 PIM，但其设计（32-bit 核心、无浮点、64KB WRAM）较为特殊。论文在 Discussion 中声称设计可推广到其他 PIM（如 HBM-PIM、AiM），但这些架构有原生浮点支持和更大带宽，PIMLex 的"以内存换计算"策略在这些平台上可能反而不是最优选择。

6. **Range Query 和 Update 场景下优势有限**：这些是真实存储系统中的常见操作，PIMLex 在这些场景下仅与 DRAM-based 方案持平甚至更差，削弱了其实用价值的论证。

---

## 七、AI Infra / MLSys 视角

1. **Embedding table 索引加速**：推荐系统中的 embedding lookup 与 learned index 的数据访问模式高度相似（大规模、高度倾斜、读多写少），PIMLex 的解耦结构和 hotness-aware 副本机制可以直接迁移到 PIM 上的 embedding table 索引设计。

2. **"以内存换计算"的设计哲学**：这个原则对 AI Infra 中利用各类近存计算（CXL memory、SmartNIC、DPU）加速数据密集型任务有普适借鉴意义。在 KV cache 管理、attention 计算中的内存访问密集环节，都可以考虑类似的 trade-off 重设计。

3. **Lookup-table 替代浮点计算**：这一技巧对在低精度/弱计算硬件上部署 ML 推理有直接参考价值，例如在 edge device 或专用加速器上用查表替代部分浮点运算。

4. **值得跟进的方向**：
   - 将 PIMLex 的解耦设计应用于 PIM 上的 vector index（如 ANN search），search layer 做粗粒度检索、data layer 存完整向量。
   - 研究 HBM-PIM（如 Samsung 的 AiM、LPDDR-PIM）上 learned index 的最优设计——这些平台有原生浮点和更高带宽，设计空间与 UPMEM 截然不同。
   - 将 hotness-aware replication 机制扩展到 CXL disaggregated memory 场景下的热数据管理。

---

## 八、总结

PIMLex 是首个基于真实 PIM 硬件（UPMEM）的 learned index 系统，通过解耦双层结构解决 PIM 容量瓶颈，通过 PIM 友好的模型结构（global binary search + lookup table）消除浮点计算瓶颈，通过 hotness-aware 副本机制解决倾斜负载下的不均衡问题。在 Get 和 Mixed 工作负载上展现了相比 DRAM-based learned index 最高 2-3× 的吞吐提升，但在写入密集和 range query 场景下优势有限。其核心贡献在于验证了 PIM 加速 learned index 的可行性，并提出了适配 PIM 硬件特性的系统化设计方法论，但目前受限于 UPMEM 硬件的诸多约束（容量小、无浮点、CPU-PIM 带宽低），实际应用场景较窄。
