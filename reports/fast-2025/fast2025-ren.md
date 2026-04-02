# PolyStore: Exploiting Combined Capabilities of Heterogeneous Storage

**作者**：Yujie Ren (Rutgers University / EPFL), David Domingo, Jian Zhang, Paul John (Rutgers University), Rekha Pitchumani (Samsung Semiconductor Inc.), Sanidhya Kashyap (EPFL), Sudarsun Kannan (Rutgers University)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/ren
**源文件**：[[fast2025-ren.pdf]]

---

## 一、背景

现代存储硬件正朝着多样化方向发展：字节寻址的持久内存（PM，如 Intel Optane）提供低延迟访问，NVMe SSD 凭借 PCIe 演进实现高吞吐，CXL-based SSD 兼具低延迟和高带宽，SATA SSD 则提供大容量低成本存储。数据密集型应用（大型数据库、数据流处理、图计算等）对存储带宽有极高需求。

在这一背景下，如何在单机内高效利用多种异构存储设备（Heterogeneous Storage Devices, HSDs）的**聚合能力**（而非仅仅将快设备作为慢设备的缓存），成为存储系统设计的核心挑战。

---

## 二、要解决的问题

现有的异构存储管理方案普遍遵循**层次化（hierarchical）**哲学，分为三类：缓存（caching）、分层（tiering）和应用导向（application-directed）。它们存在三个根本性缺陷：

1. **无法利用累积写带宽**：缓存和分层方案将快设备置于层次顶端，所有写操作先经过快设备（如 PM），导致慢设备的写带宽被浪费。即使 Orthus 这类"非层次化"缓存方案也仅在快设备带宽饱和时才并行读取慢设备，写操作仍是层次化的。

2. **快设备成为竞争瓶颈**：多线程 I/O 密集场景下，所有线程争抢单一快设备，在软件和硬件层面均产生严重竞争。此外，过度向快设备放置数据导致频繁的缓存驱逐和数据迁移，消耗存储带宽。

3. **DRAM 缓存未感知异构性**：传统 DRAM 缓存（如 Linux page cache）和 DRAM+PM 方案是静态的，无法针对不同 HSD 的性能差距自适应调整缓存准入和驱逐策略。

---

## 三、洞察与设计

**关键洞察**：在新兴存储介质"非层次化"的性能趋势下，异构设备之间的关系不再是严格的快-慢层级，而是各有带宽优势的并行资源。将它们水平排列（horizontally structured）而非垂直堆叠，可以通过细粒度数据分布实现累积带宽利用，同时保留各设备专用文件系统的成熟优化。

基于此洞察，PolyStore 设计为一个**元层（meta-layer）**，位于设备优化文件系统之上、应用之下，跨用户空间和内核空间。核心架构包含五个组件：

1. **Poly-index**：基于 range-tree（augmented red-black tree）的可扩展数据索引，以 2MB 为默认粒度将逻辑文件的块范围映射到不同物理设备上的物理文件。每个节点有独立的读写锁，支持高并发访问。内存开销极低（1TB 文件仅需 64MB，0.0064%）。

2. **Poly-inode**：逻辑文件的抽象表示，维护逻辑文件到多个物理文件（分布在不同 HSD 上）的映射，包含文件描述符和引用计数。

3. **Poly-placement**：动态的带宽感知数据放置机制。以 epoch 为周期监测各设备的实际带宽利用率，动态将应用线程的 I/O 请求映射到不同设备，防止单一设备过饱和。写线程映射采用类似贪心背包算法，根据设备剩余带宽动态调整。

4. **Poly-cache**：异构感知的用户空间 DRAM 缓存。针对不同设备实施差异化的缓存准入和驱逐策略——例如写请求可缓存但读请求不缓存（当快设备带宽充裕时），驱逐时将 DRAM 中原本在慢设备上的数据迁移到快设备（如有空间）以加速后续访问。

5. **Poly-persist**：跨设备的协调持久化机制，利用事务边界（TxB/TxE）和快设备上的元数据日志，确保跨异构设备的原子性、持久性和崩溃一致性。

此外，PolyStore 在内核中实现了薄层 PolyOS 组件（VFS 层），负责安全共享和公平 I/O 调度。

---

## 四、实现细节

- **自适应文件创建**：小文件（默认 < 2MB）仅在单一设备上创建物理文件；文件增长且带宽饱和时，才在其他设备上按需创建额外物理文件，避免小文件的元数据开销。

- **混合命名空间管理**：快设备使用传统目录层次，慢设备使用基于路径哈希的扁平命名，减少跨设备文件的随机访问开销。

- **写索引流程**：写操作遍历 Poly-index 定位块范围，处理三种情况——新范围（创建节点并发 I/O）、部分存在（整范围 I/O 并更新索引）、已存在（原地更新）。

- **并发追加**：使用 Poly-index 中的时间戳维护全局追加顺序，支持多线程并发追加到不同设备的物理文件，同时保持 POSIX 语义下的 O_APPEND 一致性。

- **Epoch-based 带宽监测**：默认 200ms 一个 epoch，runtime 统计各设备实际读写带宽，下一个 epoch 据此重新分配线程到设备。

- **崩溃恢复**：恢复时先并行恢复各物理文件系统，再恢复 Poly-inode 和 Poly-index。利用快设备上的事务日志保证元数据一致性。

- **代码规模**：用户空间 runtime 约 8K 行 C 代码，内核 PolyOS 模块约 1.5K 行。

---

## 五、实验结果

**实验平台**：

| 配置 | 快设备 | 慢设备 |
|------|--------|--------|
| Config I | Intel Optane PM (6×128GB) | Intel NVMe SSD 750 (400GB) |
| Config II | Intel NVMe SSD | SATA SSD (Samsung 870 EVO) |
| Config III | PM + NVMe + SATA（三设备） |

**基线**：Orthus（caching）、Strata（tiering）、SPFS（tiering）、P2CACHE（PM+DRAM）、单设备 NOVA/ext4。

**微基准测试（Direct I/O，无 DRAM 缓存）**：

| 工作负载 | PolyStore vs 最佳基线 | 说明 |
|----------|----------------------|------|
| 顺序写（PM/NVMe） | 最高 9.38X | 接近 PM+NVMe 理论累积带宽上限 |
| 顺序读 | 显著优于层次化方案 | 并发从两设备读取 |
| 随机写 | 最高 ~5X | 消除快设备竞争 |
| 随机读 | 最高 ~3X | 利用累积读带宽 |
| NVMe/SATA 写 | 1.87X vs NVMe-only | Config II 无 PM 场景 |
| 共享文件 | 写 2.95X / 读 3.04X | vs NVMe-only, 32 线程 |
| 三设备 | 利用 91.7% 累积带宽 | Config III |

**DRAM 缓存效果**：Poly-cache 随机写 3.18X vs PM-only，2.21X vs NVMe-only（带 page cache）。

**元数据密集型工作负载（Filebench）**：Fileserver 3.12X vs PM-only；Varmail 也有显著提升。

**真实应用**：

| 应用 | 提升 | 说明 |
|------|------|------|
| RocksDB YCSB-A | 1.52X | 写密集，利用累积写带宽 |
| RocksDB YCSB-F | 2.02X | 读-修改-写，Poly-cache 贡献大 |
| RocksDB + Redis 多应用 | 1.96X | 不降低 Redis 性能 |
| GraphWalker | PM 写减少 2.46X | 64GB 图，减少数据迁移开销 |

**故障恢复**：PolyStore 恢复后吞吐量优于其他系统 2.91X，恢复时间略长（需恢复多文件系统元数据）。

---

## 六、批判性分析

1. **微基准与端到端的差距**：微基准最高 9.38X 的提升在真实应用中缩减到 1.52X-2.02X（RocksDB YCSB），跨度巨大。论文标题和摘要突出 9.38X 的数字有误导性，因为微基准是理想条件下的性能上限，实际应用受限于应用本身的计算开销、I/O 模式和元数据操作。

2. **PM 硬件已停产的大象**：论文的主实验平台（Config I）依赖 Intel Optane PM，但 Intel 已于 2022 年宣布停产 Optane。论文虽在 Config II 展示了纯 SSD 场景，但主要贡献和性能数据仍建立在 PM+NVMe 组合上。论文未充分讨论后 Optane 时代（CXL-based memory/storage）下 PolyStore 的适用性。

3. **动态放置的开销和稳定性**：Poly-placement 使用 200ms epoch 监测带宽并重新分配线程，但论文未深入分析：(a) epoch 切换时的性能抖动；(b) 工作负载快速变化（如突发读写切换）时的适应延迟；(c) 多应用共享设备时的干扰效应。参数敏感性实验仅展示了稳态下的结果。

4. **DRAM 缓存基线不公平**：对比 Poly-cache 时，PM-only 方案不使用 DRAM 缓存，而 PolyStore 使用了用户空间 DRAM 缓存。虽然论文标注了 * 号区分，但部分对比（如 3.18X vs PM-only）的增益有一部分来自 DRAM 缓存本身而非水平架构设计。

5. **安全性和共享语义简化**：PolyOS 模块仅 1.5K 行代码处理跨进程文件共享和安全检查，论文对并发共享场景的正确性验证较为简略，缺少系统性的正确性测试（如 crash consistency 的形式化验证或模型检查）。

6. **可移植性和部署门槛**：PolyStore 需要修改内核（VFS 层模块）、需要为每种设备配置专用文件系统（NOVA for PM, F2FS for NVMe），部署复杂度较高。论文未讨论与容器化环境、云存储的兼容性。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint 和模型存储的启发**：大模型训练的 checkpoint 写入是典型的带宽密集型操作，PolyStore 的水平带宽聚合思路可直接应用——将 checkpoint 数据细粒度分布到多种存储设备（NVMe + CXL SSD + 网络存储），最大化写吞吐，减少训练中断时间。

2. **KV Cache 的异构存储卸载**：LLM 推理中 KV cache 的存储和换入换出（如 vLLM 的 offloading）可以借鉴 Poly-placement 的动态带宽感知放置策略，根据 GPU HBM、CPU DRAM、NVMe 的实时带宽利用情况动态决定 KV cache 块的放置位置。

3. **数据加载 pipeline 优化**：训练数据加载（如大规模图像/视频数据集）通常受限于单一存储设备的读带宽。PolyStore 的并发多设备读取 + 异构感知 DRAM 缓存思路可用于构建更高效的数据加载器，特别是在数据集分布于不同速度介质的场景。

4. **可操作的研究方向**：
   - 将 PolyStore 的水平存储架构与 CXL memory 结合，研究 GPU-direct-storage + CXL SSD + NVMe 的三级水平存储用于 LLM 推理中的权重和 KV cache 管理
   - 在分布式训练的 collective checkpoint 场景中，利用节点内异构存储的累积带宽降低 checkpoint 延迟
   - Epoch-based 动态放置与 ML 训练的 iteration 周期天然对齐，可探索训练感知的存储带宽调度

---

## 八、总结

PolyStore 提出了异构存储设备的水平化架构，通过细粒度数据索引（Poly-index）、动态带宽感知放置（Poly-placement）、异构感知 DRAM 缓存（Poly-cache）和协调持久化（Poly-persist）四大机制，实现了多设备累积带宽的高效利用。在 PM/NVMe 和 NVMe/SATA 配置下，微基准最高提升 9.38X，真实应用（RocksDB、Redis、GraphWalker）提升 1.52X-2.94X。其核心贡献在于打破了异构存储管理中根深蒂固的层次化思维，但实际适用性受限于 PM 硬件停产、部署复杂度和动态工作负载下的适应性。
