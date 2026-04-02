# EMT: An OS Framework for New Memory Translation Architectures

**作者**：Siyuan Chai, Jiyuan Zhang, Jongyul Kim, Alan Wang, Fan Chung, Jovan Stojkovic (University of Illinois Urbana-Champaign); Weiwei Jia (University of Rhode Island); Dimitrios Skarlatos (Carnegie Mellon University); Josep Torrellas, Tianyin Xu (University of Illinois Urbana-Champaign)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/chai-siyuan
**源文件**：[[osdi25-chai-siyuan.pdf]]

---

## 一、背景

随着内存容量进入 TB 级别（CXL 内存扩展、大容量 DRAM），加上机器学习、图计算、生物信息学等新兴工作负载具有不规则内存访问模式和弱局部性，TLB 命中率下降，内存地址翻译（memory translation）已成为重要的性能瓶颈。当前 x86-64 使用四级（即将五级）radix tree 页表，TLB miss 时需顺序遍历多级页表；在嵌套虚拟化场景下，最多需要 24 次（四级）甚至 35 次（五级）顺序内存访问，可占内存密集型工作负载超过 50% 的执行时间。

学术界已提出大量新型翻译架构（如 hash-based 的 ECPT、flattened page table FPT、hybrid 方案等），但这些方案几乎都未在真正的 commodity OS 上实验过。主要原因是 Linux 的内存管理代码深度绑定了 radix tree 页表结构，缺乏扩展性接口，支持新架构需要大规模改写架构无关代码。

---

## 二、要解决的问题

1. **Linux 内存管理硬编码 radix tree 假设**：架构无关代码中充斥着对多级树结构的隐式假设（如通过指针递增遍历相邻条目、PMD 条目要么指向 2MB 大页要么指向 4KB 页目录），支持非树结构（如 hash table、flat table）需大量改写。仅添加第五级页表就需修改 23 个文件 715 行架构无关代码。

2. **缺乏可扩展的翻译接口**：与 VFS 之于文件系统不同，Linux 没有为内存翻译提供类似的可扩展框架。Mach/BSD 的 pmap 接口虽然做了机器无关/相关分离，但不够表达——无法暴露翻译条目以进行 in-place 更新、批量锁定等硬件特定优化。

3. **新硬件方案无法获得真实 OS 评估**：现有评估依赖硬件模拟器估算 OS 开销或在原版 Linux 上收集 trace 再回放，假设 OS 开销在不同翻译架构下恒定——本文证明该假设不成立。

4. **缺乏开发/评估工具链**：实验性翻译硬件尚未量产，开发者需要能在模拟器上运行真实 OS 内核的工具链。

---

## 三、洞察与设计

**关键洞察**：尽管翻译架构的数据结构差异巨大（radix tree vs. hash table vs. flat table），但从 OS 内存管理的角度看，翻译的本质功能是统一的——输出虚拟地址到物理地址的映射及其关联元数据。可以将翻译相关操作抽象为架构中立的对象接口，同时通过可定制函数保留硬件特定优化能力。

基于此洞察，EMT（Extensible Memory Translation）设计了三层抽象：

- **Translation Object**：编码一个虚拟-物理地址映射及其元数据（大小、权限、存在位、swap 信息等），不关心底层存储方式。通过 `tobj_read_attr` / `tobj_write_attr` 读写属性。
- **Translation Database**：存储一个地址空间的所有 translation objects，通常由页表实现。通过 `tdb_find_tobj` / `tdb_update_tobj` / `tdb_remove_tobj` 操作。
- **Translation Service**：管理 MMU 状态，负责地址空间的创建、销毁和切换。

EMT API 分为两类：
- **Basic functions**（15 个）：必须由每个 MMU driver 实现，代表最小功能集。
- **Customizable functions**（35 个，7 组）：有架构中立的默认实现，MMU driver 可选择性覆盖以实现硬件特定优化。通过 `#ifndef` 宏机制实现，新增 customizable function 不会破坏已有 driver。

例如，translation object iterator 的默认实现每次都从根开始查找，而 x86-64 radix MMU driver 可利用树的空间局部性直接递增指针获取下一条目，ECPT driver 则利用 entry cluster 内的局部性。

---

## 四、实现细节

**EMT-Linux**：基于 Linux v5.15 实现，将架构无关代码中的翻译操作替换为 EMT API 调用，移除硬编码假设。通过编译器优化（函数内联、缓存效率）确保接口开销极小。

**MMU Drivers**：
- **x86-64 Radix driver**：维护传统多级树页表，编码所有级别的页表条目到 translation object，支持 Intel MPK 等硬件特性。
- **FPT driver**：基于 x86-64 driver 代码复用，664 行 C 代码，支持所有三种树层级折叠模式，无需修改架构中立代码。
- **ECPT driver**：7.4K 行 C 代码。每个页大小（4KB/2MB/1GB）维护三路 Cuckoo hash 表，共 9 个控制寄存器（用户空间）+ 9 个（内核空间）。使用 64 字节 cache line 对齐的 entry cluster（8 个条目共享 VPN tag）。实现了 Cuckoo Walk Table (CWT) 和 Cuckoo Walk Cache (CWC)。表占用率超过 0.6 时，后台内核线程渐进式 resize 和迁移条目。

**模拟器工具链**：基于 QEMU 的 software MMU 机制，实现了 ECPT MMU 模拟器（3.1K 行 C），支持指令/内存 trace 导出，可接入 DynamoRIO 等 cycle-accurate 硬件模拟器。

**关键工程挑战**：
- **Self-reference paradox**：kECPT（内核页表）管理内核自身的代码和数据，Cuckoo hashing 需要移动条目解决冲突，但被移动的条目可能正是当前代码或 kECPT 自身的映射。解决方案：先复制再删除（允许临时重复条目），MMU 处理相同映射的重复条目。
- **Atomic kECPT switching**：KPTI 切换需原子性地替换所有 kECPT way 的控制寄存器，通过增加额外寄存器组 + 硬件原子切换指令解决。
- **稀疏地址空间扫描效率**：hash table 无层次结构，无法像 radix tree 通过高层条目快速跳过空范围，需要设计特殊的状态编码条目。
- **锁设计**：ECPT 条目可被移动，split page table lock 实现困难，当前使用粗粒度锁。

---

## 五、实验结果

**实验平台**：双路 Intel Xeon Gold 6346（16 核，256GB DDR4-3200），关闭超线程，固定核心频率。

**功能正确性**：EMT-Linux（Radix/ECPT/FPT driver）通过全部 1,208 个 LTP 测试（覆盖 376 个系统调用）。

**EMT 接口开销**（EMT-Linux vs. vanilla Linux，相同硬件）：

| 指标 | 结果 |
|------|------|
| LEBench 微基准平均 | 99.9%（标准差 1.1%）|
| 最大微基准开销 | 4.2%（epoll_big，因函数未内联）|
| 宏基准开销 | < 0.1% |
| 应用吞吐/平均延迟/P99 延迟差异 | < 0.1% / 0.1% / 0.2% |

**ECPT OS 开销分析**（EMT-Linux ECPT vs. Radix，模拟环境）：

| 指标 | 4KB 页 | THP |
|------|--------|-----|
| Page fault 处理指令数 | 1.74x | 2.59x |
| Iterator 优化后节省 | 49.0% 总内核工作 | 52.5% page fault 工作 |

**硬件模拟结果**（ECPT vs. x86-64 Radix）：

| 指标 | 平均值 |
|------|--------|
| 页表遍历延迟加速 | 23.1% |
| IPC 提升 | 7.0% |
| 总 cycle 减少 | 2.3%（含 OS 开销）|
| 总 cycle 减少（仅运行阶段）| 6.6% |
| GUPS 总 cycle 减少 | 11.5% |
| Memcached 总 cycle 减少 | 12.9% |

**FPT 硬件模拟结果**（FPT L3+L2 flattening vs. x86-64）：

| 指标 | 平均值 |
|------|--------|
| 页表遍历延迟加速 | 5.5% |
| IPC 提升 | 1.0% |
| 总 cycle 减少 | 1.1% |

FPT 同时折叠 L4+L3 和 L2+L1（仅 4KB 页）时性能接近 ECPT：页表遍历加速 15.3%，IPC 提升 3.6%，总 cycle 减少 3.7%。

---

## 六、批判性分析

1. **"总 cycle 减少 2.3%" 与 "页表遍历加速 23.1%" 的巨大落差**：ECPT 在硬件翻译层面有显著优势，但 OS 层面的额外开销（page fault 处理指令数增加 1.74x-2.59x）大幅抵消了硬件收益。论文虽然诚实地报告了这一点，但这实际上动摇了 ECPT 作为 radix tree 替代方案的价值主张——如果端到端收益仅 2.3%，工程复杂度却极高，实际部署的动力不足。

2. **粗粒度锁回避了核心可扩展性问题**：论文承认 ECPT 的 split page table lock 实现"nontrivial"，当前使用粗粒度锁。但在多核高并发场景下（正是大内存工作负载的典型场景），粗粒度锁可能导致严重的性能瓶颈，而论文的多线程应用评估（Redis、Memcached、PostgreSQL）在模拟器上运行，无法暴露真实的锁竞争问题。

3. **模拟器评估的局限性**：所有 ECPT/FPT 性能数据来自 QEMU 模拟 + DynamoRIO 模拟，作者自己也承认"results could be different with different hardware simulators"以及 SST 评估留作 future work。模拟器的 in-order 执行模型可能高估或低估 OS 开销的影响。

4. **工作负载选择偏向**：宏基准以 GraphBIG（~8.5GB 工作集）和 GUPS/Sysbench（64GB 工作集）为主，但当前 ML 推理工作负载的 KV cache 可达数百 GB，论文未评估真正的 TB 级场景——恰恰是论文声称最需要新翻译架构的场景。

5. **Self-reference paradox 的解决方案引入新的正确性风险**：允许临时重复条目 + 依赖 MMU 处理重复的方案，需要 MMU 硬件保证在所有 corner case 下行为正确，但论文对这一硬件契约的形式化描述不足。

6. **稀疏地址空间问题被轻描淡写**：论文在 §7.2 提出的"special entries for encoding states"方案仅是设想，未实现也未评估。这是 hash-based 页表的根本性缺陷——缺乏层次化结构来高效跳过空洞——论文没有充分讨论这对实际工作负载的影响。

---

## 七、AI Infra / MLSys 视角

1. **LLM 推理的 KV cache 管理**：LLM 推理中的 KV cache 是典型的大内存、不规则访问场景。vLLM 等系统通过 PagedAttention 管理虚拟-物理内存映射，EMT 的抽象思路（将翻译结构与翻译对象解耦）可启发用户态内存管理器的设计。不同的 KV cache 驻留模式（prefill vs. decode）可能受益于不同的翻译策略。

2. **分布式训练的大地址空间**：分布式训练中使用 CXL 内存扩展或 RDMA 的场景需要管理 TB 级地址空间，嵌套翻译开销尤为突出。ECPT 的并行查找特性对 CXL 内存池化等场景有潜在价值，但 OS 开销问题需要先解决。

3. **可迁移的设计思路**：EMT 的"basic functions + customizable functions"二层 API 设计模式可迁移到 AI 框架的 memory allocator 设计（如 PyTorch 的 CUDAMallocManagedAllocator），为不同硬件后端（GPU、TPU、自定义加速器）提供统一接口同时允许硬件特定优化。

4. **值得跟进的方向**：
   - 在 GPU 显存管理中探索类似 EMT 的可扩展翻译框架（GPU 的 address translation 也面临类似瓶颈）
   - 将 ECPT 的并行查找思路应用于 CXL 内存的地址翻译
   - 研究 AI 工作负载（尤其是 MoE 推理、长序列 Attention）对不同翻译架构的 sensitivity

---

## 八、总结

EMT 是一个构建在 Linux 之上的可扩展内存翻译框架，通过 translation object / database / service 三层抽象和 basic + customizable 二层 API 设计，使 Linux 能够以模块化方式支持新型翻译硬件架构。框架本身开销极小（< 0.5%），并成功用于实现 ECPT 和 FPT 两种实验性翻译方案的 OS 支持。论文最重要的贡献在于揭示了一个被硬件社区忽视的事实：翻译架构对 OS 性能有深远影响，不能假设 OS 开销在不同架构间恒定。ECPT 虽在硬件层面显著加速页表遍历（23.1%），但 OS 开销的增加使端到端收益降至 2.3%。论文的主要局限在于评估完全依赖模拟器、ECPT 的锁可扩展性未解决、以及稀疏地址空间扫描效率问题仅停留在设想阶段。
