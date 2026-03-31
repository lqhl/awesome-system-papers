# EMT: An OS Framework for New Memory Translation Architectures

**作者**：Siyuan Chai, Jiyuan Zhang, Jongyul Kim, Alan Wang, Fan Chung, Jovan Stojkovic（UIUC）；Weiwei Jia（University of Rhode Island）；Dimitrios Skarlatos（CMU）；Josep Torrellas, Tianyin Xu（UIUC）
**会议**：OSDI 2025（第19届 USENIX 操作系统设计与实现研讨会，2025年7月7-9日，波士顿）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/chai-siyuan
**源文件**：[osdi25-chai-siyuan.pdf](../../papers/osdi-2025/osdi25-chai-siyuan.pdf)

---

## 一、背景

随着内存容量突破 TB 级别（CXL 内存扩展器、高密度 DRAM），以及机器学习、图计算、生物信息等新兴工作负载的爆发，虚拟内存翻译已经成为系统性能的重要瓶颈。

现代处理器（x86-64）使用多级 radix tree 组织页表（4级，近年扩展到5级）。TLB miss 时，MMU 必须顺序遍历整棵树，对 4 级页表需要多达 4 次串行内存访问。在虚拟化环境中，嵌套翻译（guest + host 两维页表游走）最多需要 24 次串行内存访问，占内存密集型负载执行时间的 50% 以上。

为此，学界提出了大量新型 MMU 硬件架构：
- **基于 hashing 的页表**（如 ECPT：Elastic Cuckoo Page Table）——并行查找 PTE，内在可扩展性优于 radix tree
- **Flattened Page Table（FPT）**（ARM 提出）——动态合并中间树层级，减少 page walk 跳数
- **混合翻译架构**——根据地址范围选择不同翻译方案

然而，这些新硬件架构几乎从未在真实 OS 上实验过，主要依赖性能模型或在 vanilla Linux 上收集 trace 后离线回放。

---

## 二、要解决的问题

### 问题 1：Linux 缺乏对新翻译架构的可扩展支持

Linux 的内存管理子系统硬编码了 radix tree 的假设——全局宏定义、页表级别迭代器、PMD/PUD 直接操作等都与 radix tree 深度耦合（如图3所示）。支持任何非 radix tree 的架构都需要大规模修改架构无关（arch-independent）代码，工程代价极高。Linux 对文件系统有 VFS 这样的抽象层，但对内存翻译毫无类似设计。

### 问题 2：OS 开销被新架构研究忽视

现有硬件研究的普遍假设是"不同翻译架构下 OS 开销恒定"。因此，实验只模拟硬件翻译延迟，忽略了页故障处理、地址范围扫描等 OS 操作在不同翻译架构下的巨大差异。本文表明这一假设是错误的，OS 操作对最终性能有深远影响。

### 问题 3：缺乏开放的开发与评估平台

新翻译硬件（如 ECPT）尚无实物芯片，现有仿真工具链（如 Simics）是闭源商业软件，无法方便地与 Linux 内核协同开发和评估。

---

## 三、核心设计

### EMT（Extensible Memory Translation）框架

EMT 是构建在 Linux 之上的一套**架构中立的内存翻译接口**，具有四个目标：
1. 支持多样化的内存翻译架构（radix tree、hash table 等）
2. 允许硬件特定优化（如 ECPT 的 Cuckoo Walk Cache、Intel MPK）
3. 兼容现代硬件和 OS 的复杂特性（huge page、KPTI、THP、split page table lock）
4. 相对于 vanilla Linux 的硬编码实现，开销可忽略不计

### 核心抽象

EMT 提供三个核心抽象：

| 抽象 | 含义 | 关键 API |
|------|------|----------|
| **Translation Object（tobj）** | 单条虚拟→物理地址映射，携带属性（PA、权限位等） | `tobj_read_attr`, `tobj_update_attr` |
| **Translation Database（tdb）** | 管理整个翻译结构（即页表），每个进程一个 | `tdb_find_tobj`, `tdb_update_tobj` |
| **Address Range Lock** | 锁住某个虚拟地址范围内的翻译条目 | `addr_range_get_lock`, `addr_range_write_lock` |

架构无关的 OS 代码只通过 EMT API 操作 tobj 和 tdb，不再直接访问 PTE/PMD/PUD 等硬件结构。硬件特定的翻译逻辑封装在 **MMU Driver** 中，由开发者针对具体架构实现。

### 可定制化函数（Customizable Functions）

EMT 允许 MMU Driver 通过钩子函数覆盖默认实现，以实现架构特定优化：
- **迭代器（iterator）**：遍历地址范围内的 tobj，默认实现是逐个 hash lookup，ECPT 可用指针算术加速
- **锁语义（lock）**：允许 ECPT 实现基于地址范围的锁，而非页表条目级别的锁
- **TLB flush**、**大页判断（thp_eligible）**、**编码/解码（swp entry）** 等均可定制

---

## 四、实现细节

### EMT-Linux

基于 Linux v5.15 实现。架构无关代码（`mm/memory.c`、`mm/vmalloc.c` 等）重构为使用 EMT API，移除所有对 radix tree 的硬编码假设。实现 EMT 接口带来 **<0.5% 平均开销**。

### x86-64 MMU Driver

对应 vanilla Linux 的 radix tree 实现，支持 Intel MPK、split page table lock 等所有硬件特性。驱动可通过指针操作直接操作 PMD/PUD 条目，维持原有优化。

### ECPT MMU Driver（7.4K 行 C 代码）

基于 Elastic Cuckoo Page Table 设计：
- 三路 Cuckoo hashing，每路对应一个 PTE 数组
- 64 字节 cache line 中聚集 8 条 PTE，共享 VPN tag（5 bits/entry），最后一项作为 cluster occupancy counter
- 管理 kECPT（全局内核地址空间）和 uECPT（每进程用户空间）共 18 组控制寄存器
- 后台线程在 occupancy >0.6 时扩容并迁移条目
- CWT（Cuckoo Walk Table）用于缓存 page size 和 way 信息，仅在 ECPT MMU Driver 内部管理

### FPT MMU Driver（664 行 C 代码）

复用 x86-64 MMU Driver 代码，支持三种 tree 层级合并模式（L3+L2、L4+L3、L2+L1）。通过 EMT API，无需修改任何架构无关代码。

### QEMU 仿真工具链

- 用 QEMU 的 software MMU 机制实现 ECPT MMU 仿真（3.1K 行 C 代码）
- 通过 TCG plugin 实现指令和内存访问 tracer，可对接 DynamoRIO 等周期级仿真器

---

## 五、实验结果

### EMT 接口开销

**测试平台**：双路 Intel Xeon Gold 6346，3.10 GHz，16 核，256 GB DDR4-3200

| 基准类型 | 与 vanilla Linux 差异 |
|----------|----------------------|
| LEBench 微基准（41项） | 平均 99.9%（标准差 1.1%） |
| 宏基准（GraphBIG 等9项） | <0.1% |
| Redis 吞吐/延迟/P99 | 分别在 0.1% / 0.1% / 0.2% 内 |

最大开销来自 `epoll big` 基准（4.2%），因函数未内联，可通过强制 inline 优化。

### ECPT OS 开销分析

相比 Radix，ECPT 的页故障处理内核指令数：
- 4KB 页：多 **1.74x**
- THP 启用：多 **2.59x**（因 2MB 范围扫描需遍历最多 512 个独立 PTE 条目）

迭代器优化效果（GraphBIG BFS + THP）：
- 节省 49.0% 总内核工作量
- 节省 52.5% 页故障处理工作量

### 硬件仿真结果（DynamoRIO）

| 指标 | ECPT vs x86-64 | FPT(L3+L2) vs x86-64 | FPT(L4+L3+L2+L1, 4KB) vs x86-64 |
|------|---------------|---------------------|----------------------------------|
| Page Table Walk 延迟 | -23.1% | -5.5% | -15.3% |
| IPC | +7.0% | +1.0% | +3.6% |
| 总周期（含OS开销） | -2.3% | -1.1% | -3.7% |
| 总周期（仅 running phase） | -6.6% | — | -6.4% |

ECPT 显著受益的场景：GUPS（总周期 -11.5%）、Memcached（-12.9%）——page table walk 占执行时间 >66%。

---

## 六、批判性分析

**OS 开销数字令人担忧**：ECPT 的 page table walk 有 23% 的硬件加速，但 OS 页故障处理增加 1.74x 内核指令（4KB）或 2.59x（THP）。最终端到端总周期仅减少 2.3%——硬件侧的收益大部分被 OS 软件开销抵消。这说明"硬件加速翻译"和"系统实际性能提升"之间存在重大鸿沟，值得警惕。

**评估基于仿真，不是真实硅片**：所有 ECPT 的实验都在 QEMU 软件仿真 MMU 上进行，硬件周期数据来自 DynamoRIO 指令级模拟。真实 ECPT 芯片的行为（时序、cache 压力、内存带宽争用）可能与仿真结果有显著偏差。

**THP 场景下 ECPT 开销被低估**：论文在 §8.4 承认 ECPT 在 THP 启用时内核指令暴增 2.59x，根因是稀疏地址空间扫描效率差。提出的"特殊状态编码条目"方案（§7.2）只是展望，未实现，因此 THP + ECPT 的性能存在根本性缺陷，目前只能依赖迭代器优化来规避，治标不治本。

**多核扩展性问题未解决**：§7.2 明确指出 ECPT 的 entry 可移动性导致 split page table lock 难以实现，存在死锁风险。当前实现使用粗粒度锁（coarse-grained lock），会在多核高并发场景下成为瓶颈。替代方案（独立 lock table）仍在探索中，论文对此语焉不详。

**工作量主要在 UIUC 一家**：论文作者来自 UIUC + 两所合作机构，ECPT 和 FPT 均与 UIUC 组的前序工作高度重叠。客观性上存在一定的"自家工具评估自家架构"的风险。

**FPT(L3+L2) 收益极其有限**：5.5% walk 延迟提升、1.1% 总周期减少——这与 ARM 提出 FPT 时的预期差距较大。论文将其归因于 L3 条目本已被有效缓存。只有完整四级合并（L4+L3+L2+L1，仅支持 4KB 页）才能达到与 ECPT 相近的性能，但这种配置目前不支持 huge page，实用性受限。

---

## 七、AI Infra / MLSys 视角

EMT 框架本身与 AI Infra 关联有限，但其揭示的几个核心问题对 AI 系统研究具有参考价值：

**内存翻译是 AI 工作负载的真实瓶颈**：论文引用的 ML 训练/推理（以及图计算、生物信息）均属于大内存、弱局部性访问模式，是 TLB 压力最大的场景。GUPS（随机内存更新）在 ECPT 下总周期减少 11.5%，类似的访问模式在 LLM embedding lookup、KV cache 随机访问、大批量 attention 计算中普遍存在。

**可能的迁移方向**：
- **GPU/NPU 内存翻译**：GPU IOMMU 同样受页表游走开销影响，类似 EMT 的框架化设计可以探索在 GPU 驱动（如 NVIDIA UVM）中支持实验性翻译架构。
- **CXL 分级内存下的翻译优化**：随着 CXL 内存池化，远端内存的地址翻译延迟更敏感，hashing-based 翻译的并行查找优势更明显。
- **稀疏地址空间管理**：AI 训练中的模型并行、流水线并行产生大量稀疏的虚拟地址映射，EMT 揭示的"hashing 页表难以高效管理稀疏地址空间"问题值得在 AI 框架的内存管理层面重新审视。

**值得跟进的 future work**：
- 在 THP 场景下为 ECPT 设计高效的"range state encoding"，使 OS 无需遍历全部 4KB PTE 即可判断 2MB 范围是否有映射
- 探索 ECPT/FPT 在虚拟化（嵌套翻译）场景下的 OS 开销，这对云端 AI 推理服务有直接价值

---

## 八、总结

EMT 构建了一个实用的 Linux 内存翻译框架，通过 Translation Object / Translation Database / MMU Driver 三层抽象，将 Linux 内存管理与底层硬件翻译架构解耦，实现了对 ECPT 和 FPT 两种新型翻译方案的 OS 支持，并配备了基于 QEMU 的仿真工具链。其核心贡献在于揭示了"OS 开销在不同翻译架构下并非恒定"这一被硬件研究长期忽视的问题，填补了新型 MMU 硬件设计与真实 OS 实验之间的空白。主要局限在于：端到端性能收益（总周期仅 -2.3%）远小于硬件指标（walk 延迟 -23.1%）的承诺，THP 场景下 OS 开销问题未根本解决，且评估全部基于仿真而非真实芯片。
