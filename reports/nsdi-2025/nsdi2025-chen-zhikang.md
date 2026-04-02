# ClubHeap: A High-Speed and Scalable Priority Queue for Programmable Packet Scheduling

**作者**：Zhikang Chen (Tsinghua University), Haoyu Song (Futurewei Technologies), Zhiyu Zhang, Yang Xu (Fudan University), Bin Liu (Tsinghua University)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/chen-zhikang
**源文件**：[nsdi2025-chen-zhikang.pdf](../../papers/nsdi-2025/nsdi2025-chen-zhikang.pdf)

---

## 一、背景

在网络交换机中，报文调度（packet scheduling）决定了数据包的发送顺序和时间，是流量管理（Traffic Manager）的核心功能。随着可编程网络设备（programmable switches、SmartNICs）在软件定义网络（SDN）中的重要性日益提升，支持多种调度算法的可编程调度器成为刚需。

Push-In First-Out（PIFO）是一种被广泛接受的优先队列抽象，允许元素按优先级插入任意位置但只能从队头弹出，通过 mesh 互连的 PIFO block 可以构成树形结构来支持多级层次化调度。然而，PIFO 的高效硬件实现面临吞吐量（throughput）、可扩展性（scalability）和逻辑分区（logical partitioning）三大挑战，现有方案均无法同时满足。

---

## 二、要解决的问题

现有 PIFO 优先队列实现存在以下不足：

1. **基于线性数据结构的实现**（如 SR-PIFO、APQ）需要 O(N) 个比较器并行比较所有元素，硬件开销大、时钟频率随 N 增长显著下降，无法满足元素数量 N 的可扩展性要求。SR-PIFO 在 N=4096 时已占用约 900K LUTs，频率仅 40MHz。

2. **基于 bucket 的实现**（如 BBQ）对元素数量 N 可扩展，但优先级级数 P 受限于 bucket 数量（如 BBQ 仅支持 2^15 个 bucket），无法满足需要高精度时间戳的算法需求。

3. **基于 heap 的实现**（如 P-Heap、BMW-Tree、PipelinedHeap）在 N 和 P 两个维度上有较好的可扩展性，但受**操作间数据依赖**（inter-operational data dependency）问题困扰——连续 pop 操作在堆中形成依赖链，需要跨层 bypass 和多候选比较，严重限制了流水线化实现。至今没有可扩展的 PIFO 实现能达到 CPR=1（每个时钟周期完成一次 replace 操作）的理论下界。

4. **逻辑分区支持不足**：P-Heap 和 BMW-Tree 不支持逻辑分区，而 BBQ 的逻辑分区会线性放大 bucket 需求。PipelinedHeap 支持逻辑分区但全局总线成为瓶颈。

---

## 三、洞察与设计

**关键洞察**：在传统二叉堆中，连续 pop 操作会形成跨层依赖链（最小元素可能分布在不同层），导致需要从多个层级 bypass 数据到根节点并在多个候选者间比较。但如果将堆的每个节点扩展为存储 K 个有序元素的 cluster（K >= 2），则连续操作只会访问同一 cluster 内的不同元素，从而消除跨层的操作间数据依赖，使完全流水线化（CPR=1）成为可能。

基于此洞察，论文提出 ClubHeap（Clustered Binary Heap）：

- **数据结构**：二叉树的每个节点存储最多 K 个有序元素（cluster）。定义保证：对任意节点 x 及其子节点 y，x 中所有元素的 rank 不大于 y 中任何元素的 rank。由此推导出元素紧凑分布在上层节点的特性（Corollary 2），使得深层节点数量受控于 N/(K(1-1/2^(L-1))+1)，而非 M×2^(L-1)，显著减少逻辑分区时的内存需求。

- **流水线架构**：每个堆层级配备一个 Processor，包含 READ、CMP、WRITE 三个阶段。连续操作在不同层级的不同阶段重叠执行，实现 CPR=1。关键设计：每个非根节点的最小 rank 元素存储在其父节点中，使得 CMP 阶段所需数据全部在同一层级可用，消除层间数据依赖。

- **混合内存分配**：浅层使用静态分配（地址可直接计算），深层使用动态分配（free list 管理），在减少指针开销和节省存储空间之间取得最优平衡。

---

## 四、实现细节

- 使用 **919 行 Chisel 代码**实现，参数化设计支持自定义 K、N（最大元素数）、P（优先级级数）、M（逻辑 PIFO 数量）。

- **FPGA 原型**：部署在 Xilinx Alveo U280 数据中心加速卡上，支持最多 2^17 个元素、2^8 个逻辑 PIFO、32-bit 优先级精度。

- **ASIC 分析**：使用 Design Compiler 在 45nm 工艺下综合，800MHz 频率。ClubHeap（K=2）面积仅为 BBQ 的 17.7%。

- **Processor 结构**：
  - READ 模块：读取一对兄弟节点（存储在同一地址），同时获取子节点地址。
  - CMP 模块：核心执行单元，根据操作类型（push/pop/replace）进行元素比较和选择。由于 cluster 内元素有序，最小元素无需比较即可确定。
  - WRITE 模块：将更新后的节点数据写回内存。

- **动态内存分配**：深层使用单向链表 free list（本质是栈），pop 节点分配空间，push 节点回收空间，分配和回收可在同一周期完成。

- 每个处理器使用双端口 SRAM（READ 和 WRITE 阶段各一个端口）。

---

## 五、实验结果

实验平台：Xilinx Alveo U280 FPGA（1,303K LUTs、2,607K FFs、2,016 BRAMs、960 UltraRAMs），以及 45nm ASIC 综合分析。

### 不同 K 值对 ClubHeap 的影响

| 指标 | K=2 (N=2^17) | K=16 (N=2^17) | K=32 (N=2^17) |
|------|-------------|--------------|---------------|
| 时钟频率 | 189.57 MHz | ~200 MHz | 207.25 MHz |
| LUT 占比 | ~1% | ~3% | ~6.2% |
| FF 占比 | ~1% | ~3% | ~1.6% |

### 与 BMW-Tree、BBQ 的对比（N=2^17, P=2^16, M=1）

| 指标 | ClubHeap (K=2) | ClubHeap (K=16) | BBQ | BMW-Tree |
|------|---------------|----------------|-----|----------|
| CPR | 1 | 1 | 2 | 3 |
| 吞吐量 | ~200 Mpps | ~200 Mpps | ~120 Mpps | ~67 Mpps |
| BRAM 节省 | 基准 | +6% | +33%~39% 更多 | 相当 |

### 关键结论

- **N 可扩展性**：ClubHeap 吞吐量比 BBQ 高 63%~72%（N=2^17），比 BMW-Tree 高 3x。
- **P 可扩展性**：P 从 2^16 增至 2^20 时 ClubHeap 频率仅降 3%，BBQ 频率显著下降；P=2^20 时 ClubHeap 吞吐量是 BBQ 的 3.28x。ClubHeap 可扩展至 P=2^32，仅 5.5% 频率损失。
- **M 可扩展性**：M=2^8 时 ClubHeap（K=2）频率仅降 16.7%，BBQ 存储需求线性增长。
- **ASIC 面积**：ClubHeap（K=2）面积仅为 BBQ 的 17.7%（N=2^17, P=2^16, M=1）。
- **二叉堆优于多路堆**：clustered 三叉/四叉堆频率更低、资源消耗更多，验证了二叉堆的选择。

---

## 六、批判性分析

1. **实验仅限 FPGA 仿真和 ASIC 综合，缺乏真实网络环境验证**。论文声称 100Gbps 线速处理，但未在真实交换机或 SmartNIC 上部署端到端测试。吞吐量通过 FPGA 仿真获得，未考虑实际流量模式、调度算法开销和系统集成问题。

2. **CPR=1 的实际收益被高估**。论文将 CPR 作为核心性能指标，但实际吞吐量 = 频率/CPR。ClubHeap 在大 N 时频率与 BBQ 相当（~200MHz），因此实际吞吐量提升主要来自 CPR 差异（1 vs 2），而非数量级改进。论文标题中的 "High-Speed" 可能给读者造成更大提升的印象。

3. **逻辑分区的实际验证不充分**。论文理论上证明了 ClubHeap 的内存效率优于 BBQ 在 LP 场景下的表现，但实验中 M 最大只测到 2^8，未验证更大规模的逻辑分区是否仍然有效。

4. **与 APQ 的对比不够公正**。APQ 同样实现了 CPR=1，论文以 APQ 的 N 可扩展性差为由将其排除在主要对比之外，但未在相同的小 N 场景下直接比较两者的资源效率和频率。

5. **K 值选择缺乏系统性指导**。论文指出 K 越大频率越高但资源消耗越大，建议 "根据具体需求选择"，但未给出不同应用场景下的 K 值推荐或自动选择方法。

6. **动态内存分配的性能影响未充分分析**。free list 操作是否会在极端场景（大量逻辑 PIFO 频繁创建/销毁）下成为瓶颈未被讨论。

---

## 七、总结

ClubHeap 提出了 Clustered Binary Heap 数据结构，通过将堆节点扩展为存储 K 个有序元素的 cluster，消除了困扰 heap-based PIFO 实现的操作间数据依赖问题，首次在 heap-based 设计中实现了 CPR=1 的完全流水线化。结合混合内存分配策略，ClubHeap 同时满足了高吞吐量、N/P/M 三维可扩展性和逻辑分区支持，是目前最全面的 PIFO 优先队列硬件实现方案。主要局限在于仅有 FPGA 原型和 ASIC 综合验证，缺乏真实网络环境中的端到端评估。
