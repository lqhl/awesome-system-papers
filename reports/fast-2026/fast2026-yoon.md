# Cylon: Fast and Accurate Full-System Emulation of CXL-SSDs

**作者**：Dongha Yoon†, Hansen Idden†, Jinshu Liu, Berkay Inceisci, Sam H. Noh, Huaicheng Li（Virginia Tech）（†Co-lead authors）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/yoon
**源文件**：[[fast2026-yoon.pdf]]

---

## 一、背景

现代数据密集型工作负载（ML/AI、图处理等）日益受限于 memory wall：DRAM 成本高昂且难以扩展。Compute Express Link (CXL) 提供了一条新路径，允许异构内存设备通过 load/store 接口直接连接 CPU。其中一个重要方向是 CXL-SSD：将 SSD 挂载在 CXL 之后，以小容量 DRAM cache 提供 sub-µs 的热数据访问延迟，以大容量 NAND flash 提供 TB 级存储容量，从而在存储级成本下提供近似内存的可编程性。

Samsung CMM-H 是典型的 CXL-SSD 原型：48GB DRAM cache + 1TB NVMe SSD 后端，通过 Intel Agilex FPGA 控制器协调，采用 write-back + LRU 替换策略。然而，CXL-SSD 的设计空间仍处于早期阶段——cache 管理策略、prefetching 机制、硬件-软件协同设计等关键问题都缺乏系统性的研究工具。

---

## 二、要解决的问题

CXL-SSD 研究面临三大工具缺口：

1. **硬件原型不透明**：商业 CXL-SSD（如 CMM-H）是黑盒，cache 管理由固件控制，无法调整策略参数，难以系统性探索设计空间。
2. **现有模拟器不完整**：
   - Trace-driven 模拟器（MQSim-CXL、ESF）：慢于实时数个数量级，无法运行未修改的完整软件栈。
   - Cycle-accurate 模拟器（CXL-SSD-Sim、CXL-DMSim）：精度高但极慢，无法进行系统级研究。
   - QEMU-CXL：可运行完整 OS，但依赖 MMIO/VM-exit 路径，每次访问延迟约 15µs，比真实 CXL-SSD cache hit（sub-µs）慢两个数量级，且不建模 NAND 特性。
   - FPGA 平台（OpenCXD）：依赖专用硬件，不开放、不可扩展。
3. **缺乏硬件-软件协同设计能力**：没有平台同时支持可配置的 cache 策略和应用层接口，无法研究应用感知的 CXL-SSD 优化。

核心需求：一个同时具备 **full-stack 执行能力**（运行未修改 OS 和应用）、**近 bare-metal 速度**（准确再现 sub-µs hit 和 tens-of-µs miss）、**准确设备建模**（DRAM cache 动态 + NAND timing）的平台。

---

## 三、洞察与设计

**关键洞察**：CXL-SSD 的性能特征本质上是双模态的——cache hit 在 sub-µs 完成（类似 DRAM），cache miss 需要 tens-of-µs（落到 NAND）。通过动态操纵 Intel EPT（Extended Page Table）的权限位，可以让 cache hit 走"直通"路径（无 VM-exit 开销），而 cache miss 走"陷入"路径（触发 VM-exit 进入模拟器处理），从而在 full-system 模拟器中忠实再现这种延迟不对称性。

基于此洞察，Cylon 的核心设计包括三个关键机制：

### 1. Dynamic EPT Remapping (DER)

为每个 page 定义两种 EPT 状态：
- **Direct 状态**：EPTE 指向 DRAM cache 的 HPA，设置 R/W 权限，EPT walk 直接完成，无 VM-exit。
- **Trap 状态**：EPTE 设置 R=W=X=0，任何访问触发 EPT violation → VM-exit → 进入 FEMU 处理。

Cache fill 时从 Trap→Direct，eviction 时从 Direct→Trap。使用 INVEPT/INVVPID 进行精准 TLB 失效，支持批量合并以提高效率。

### 2. Shared EPT Memory

在 VM 初始化时预分配所有 leaf EPTE 到一个连续内存区域，同时映射到内核空间和用户空间（QEMU/FEMU）。EPTE 可通过 LPN 直接索引，O(1) 查找和更新，避免了 ioctl syscall 和 EPT walk 开销。FEMU 通过 `<index, desired state, cookie>` 描述符请求更新，内核验证后应用，仅允许修改 PFN selector 和 R/W/X 权限位。

### 3. 可配置 Caching 框架

支持插件式 eviction 策略（FIFO、LIFO、CLOCK、S3FIFO 等）和 prefetching 策略（next-N）。提供应用层接口（通过共享内存 ring queue），支持显式 prefetch/pin/evict、动态策略切换、细粒度统计查询。通过 EPT accessed bit 采样和 Intel PEBS 提供 observability。

### 4. 架构可扩展性

不限于模拟 CMM-H，还支持探索 NVMe-oC（CXL + NVMe 融合）、CXL-FTL 集成、低延迟 flash、多设备拓扑等新兴架构。

---

## 四、实现细节

Cylon 基于 QEMU/FEMU/Linux KVM 构建：
- **代码量**：FEMU (v8.0.0) 新增约 6,282 行，Linux kernel (v6.4.6) 新增约 1,261 行。
- **后端内存分配**：通过 Linux boot 参数 `memmap=[size]![offset]` 在 NUMA node 1 上预留物理连续 DRAM 作为模拟 CXL-SSD 的 DRAM cache。Guest vCPU pin 在 NUMA node 0，访问 cache 时经过 remote-NUMA 路径（~150ns）。
- **Cache hit 延迟**：由 host remote-NUMA DRAM 访问时间决定（~150ns），低于 CMM-H 的 ~800ns（后者含 FPGA 控制器开销），提供理想化基线。
- **Shared EPTE**：引入新 KVM memslot flag `KVM_MEMSLOT_DUAL_MODE`，在 EPT violation 时将 EPTE 分配到用户空间共享内存区域。
- **NAND timing**：复用 FEMU 已验证的 NAND flash timing 模型，模拟 channel/die/plane 并行性、read/program/erase 延迟、GC 干扰等。延迟非固定值，取决于当前 FTL 和 NAND 状态。
- **后端存储**：当前使用 host DRAM 存储后端 SSD 数据（限制模拟容量），正在开发 SPDK-based NVMe 后端以支持 TB 级模拟。
- **已开源**：https://github.com/MoatLab/FEMU

---

## 五、实验结果

**实验平台**：
- Host：双路 Intel Xeon Gold 6242，384GB DDR4，Ubuntu 20.04 + 修改版 Linux v6.4.6
- Guest VM：8 vCPU，96GB local DRAM，96GB CXL DAX 设备（4.8GB DRAM cache + 96GB NAND flash）
- NAND timing：40µs read，200µs write，2,000µs erase
- 验证平台：双路 Intel Xeon 6710E + Samsung CMM-H（1TB CXL-SSD，48GB DRAM cache）

**关键结果**：

| 实验 | 结果 |
|------|------|
| Cache hit 延迟 | Cylon 0.16µs vs. QEMU 14.74µs（~92× 提升） |
| Cache miss 延迟（不含 NAND） | Cylon-S 16.27µs vs. Cylon-I（ioctl）23.04µs，Shared EPT Memory 节省 ~6.8µs |
| 延迟分布 | Cylon 呈双模态分布（avg hit 977ns + µs 级 miss），QEMU 单峰（avg 14.6µs） |
| 带宽 | Cylon 在 cache 内维持 remote-NUMA 带宽（~32GB/s），超出 cache 后两者收敛到 NAND 带宽 |
| Redis (YCSB-C) | 三种 WSS 下，Cylon 的延迟 CDF 与 CMM-H 趋势一致，cache 内 Cylon 略优（无 FPGA 开销） |
| GAPBS (Betweenness Centrality) | 不同图规模下 Cylon 与 CMM-H 执行时间趋势一致 |
| Eviction 策略对比 | FIFO/CLOCK 在顺序访问下相同；S3FIFO 在多数模式下最优；LIFO 在 Zipfian 分布下因保留旧热 key 表现最佳 |
| Prefetching (next-N) | Stride-4096 模式下，N=0 hit rate 18% → N=8 hit rate 86%；随机访问下 prefetching 无效 |

---

## 六、批判性分析

1. **Cache hit 延迟低于真实硬件**：Cylon 的 cache hit 延迟（~150ns）远低于 CMM-H（~800ns），因为绕过了 FPGA 控制器开销。论文将其定位为"理想化基线"，但这意味着在 cache hit 占主导的场景下，Cylon 会系统性地高估应用性能。对于需要评估真实部署性能的研究者，这是一个重要偏差。论文提到添加校准延迟注入是"straightforward future work"，但未实现。

2. **后端存储使用 host DRAM**：所有"NAND"数据实际存储在 host DRAM 中，限制了模拟容量（受 host 内存限制），也意味着 GC 等涉及实际数据搬移的行为可能与真实 SSD 有差异。SPDK-based NVMe 后端是 ongoing work。

3. **验证覆盖范围有限**：仅验证了 Redis 和 GAPBS 两个应用，且 Redis 只测了 YCSB-C（100% read）。缺少写密集型工作负载的验证，而 dirty eviction 路径（需要 write-back 到 SSD）恰恰是 CXL-SSD 中更复杂的场景。

4. **可扩展性验证不足**：论文声称 Cylon 可探索 NVMe-oC、CXL-FTL 集成等新架构，但实验部分完全没有展示这些扩展能力，仅停留在设计层面的讨论。

5. **多线程场景探索浅**：大部分微基准测试使用单线程。虽然提到 CMM-H 在 4 线程时性能饱和（设备并行度限制），但缺乏对高并发下 DER 开销（TLB shootdown、EPT 锁竞争）的系统性分析。

6. **与 CMM-H 的绝对性能差异被淡化**：论文强调"qualitative trends"一致，但 Cylon 在 cache hit 场景下的绝对延迟比 CMM-H 低 5× 以上，在实际研究中可能导致错误的性能预期。

---

## 七、AI Infra / MLSys 视角

1. **CXL-SSD 作为 AI 训练/推理的内存扩展层**：随着 LLM 参数规模和 KV cache 需求的持续增长，CXL-SSD 可能成为 GPU/CPU 内存的廉价扩展方案。Cylon 提供了评估 AI 工作负载在 CXL-SSD 上性能表现的平台——例如 KV cache offloading 到 CXL-SSD 时，不同 eviction 策略对推理延迟的影响。

2. **应用感知 cache 策略的启发**：论文的应用层接口（prefetch/pin/evict hints）直接适用于 AI 场景：训练 pipeline 可以预取下一个 mini-batch，推理引擎可以 pin 热门 prompt 的 KV cache。这种硬件-软件协同设计思路可以迁移到 GPU memory management。

3. **DER 机制的技术迁移价值**：Dynamic EPT Remapping 通过操纵页表权限位实现快慢路径分离的思路，可以迁移到其他需要区分热冷数据的内存管理场景，例如 tiered memory 系统中的自动热页迁移。

4. **值得跟进的方向**：
   - 在 Cylon 上评估 vLLM、SGLang 等 LLM 推理系统的 KV cache offloading 到 CXL-SSD 的性能
   - 设计 AI workload-aware 的 CXL-SSD cache 策略（如基于 attention pattern 的预取）
   - 探索 CXL-SSD 作为 checkpoint storage 在分布式训练中的可行性

---

## 八、总结

Cylon 是首个基于 FEMU 的 CXL-SSD full-system 模拟器，通过 Dynamic EPT Remapping 消除 cache hit 的 VM-exit 开销、通过 Shared EPT Memory 降低 miss 路径的 EPT 更新成本，实现了在完整系统模拟器中忠实再现 CXL-SSD 的 sub-µs hit / tens-of-µs miss 延迟不对称性。其可插拔的 caching 框架和应用层接口支持策略探索和硬件-软件协同设计。主要局限在于 cache hit 延迟低于真实硬件、后端存储使用 host DRAM 限制容量、以及验证场景（尤其是写密集和多线程）覆盖不足。适用于需要快速、灵活探索 CXL-SSD 设计空间的系统研究者。
