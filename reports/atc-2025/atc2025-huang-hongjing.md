# SwCC: Software-Programmable and Per-Packet Congestion Control in RDMA Engine

**作者**：Hongjing Huang†, Jie Zhang†, Xuzheng Chen, Ziyu Song, Jiajun Qin, Zeke Wang*（浙江大学计算机科学系）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/huang-hongjing
**源文件**：[atc2025-huang-hongjing.pdf](../../papers/atc-2025/atc2025-huang-hongjing.pdf)

---

## 一、背景

现代数据中心广泛采用 RDMA（特别是 RoCE）来实现低延迟、高吞吐、低 CPU 开销的网络通信。RoCE 依赖 PFC 来保证无损网络，但 PFC 会引入队头阻塞、拥塞扩散和死锁等问题。为了从根本上避免 PFC 的触发，研究者提出了各种拥塞控制算法（CCA）来优化网络性能。

随着上层应用（尤其是 ML 工作负载）的快速演进，CCA 也需要持续迭代。2021–2023 年间就有 11 种新 CCA 被提出，而同期商用 NIC 的更新周期远远跟不上。与此同时，数据中心网络带宽即将从 100 Gbps 跃升至 400/800 Gbps，对拥塞控制的响应速度提出了更严格的要求。

---

## 二、要解决的问题

现有四类 RDMA 拥塞控制方案各有不足：

1. **ASIC-based NIC CC**（如 DCQCN on CX-5）：控制环路延迟低（~3.1 µs），但 CCA 硬连线在芯片中，无法升级。一款 NIC 通常只支持 1–2 种 CCA，且 Mellanox 过去 10 年仅发布 7 款 CX 系列 NIC，完全无法跟上 CCA 的快速迭代。

2. **CPU-based CC**（如 Soft-RoCE）：灵活性和可编程性高，但控制环路延迟高达 ~23 µs（比 NIC 方案高一个数量级），因 PCIe 穿越和软件栈开销，导致交换机队列排空时间增加 7.8×。

3. **Naive FPGA SmartNIC CC**（如 Tonic, NanoTransport）：控制环路延迟低（~3.3 µs），灵活性高，但需要用 HDL/P4 编程，工程量大、调试困难、开发周期长，可编程性低。

4. **SoC SmartNIC CC**（如 NVIDIA BlueField-3 PCC）：允许在 RISC-V DPA 上用 C 编程，但 DPA 的 cache/memory 性能差（L1: 10 ns, memory: 300 ns），单线程性能弱。PCC 只能调整 per-flow rate，不支持 window-based 和 credit-based CCA，灵活性受限。在 100 Gbps 下 1 KB 包的到达间隔仅 89 ns，远低于 DPA 的内存访问延迟。

**核心矛盾**：没有现有方案能同时提供低控制环路延迟、高灵活性和高可编程性。

---

## 三、洞察与设计

**关键洞察**：CCA 在 NIC 上运行时的数据访问模式具有高度可预测性——收到包后，CC 控制器只需访问该包对应 QP 的上下文和包头信息，且在 RX 硬件流水线处理包的同时可以用 QPN 作为 hint 提前预取 QP 上下文，从而将 DRAM 访问延迟隐藏在 RX 预处理流水线中。此外，大多数 CCA 可以被清晰地拆分为独立的 TX 和 RX 两个函数，不需要在同一个核上同时处理收发逻辑。

基于上述洞察，SwCC 的核心设计包括三个层面：

### 1. TX/RX 分离的多核架构
将 CCA 的 TX 逻辑和 RX 逻辑分别运行在不同的 RISC-V 核上。每个 QP 通过 QPN mod N 映射到特定的 TX/RX 核对，避免跨核同步。单核只需连接 NIC 资源的子集（TX 核只连 TX 端口，RX 核只连 RX 端口），减少 50% 的路由线，使 FPGA 设计频率提升最高 16%。

### 2. QP-aware Memory Subsystem
四个协同机制：
- **QP Context Table**：用 on-NIC DRAM（而非 host DRAM）支撑的 4-way set-associative cache，以 QP 为粒度组织，每个 slot 128B，总计 128 KB（可缓存 1K QP）
- **CSR-based Fast Path**：在 CC 核触发前，硬件将 QP 上下文和包头信息写入 RISC-V 的 CSR 寄存器（64 个，共 256 B），读取仅需 1 cycle
- **QPN Hint 预取**：RX Parser 提取 QPN 后立即发送给 QP Context Table 预取，利用 RX 流水线处理时间（~60 ns）隐藏 DRAM 访问延迟（~100 ns）
- **硬件锁一致性保证**：每个 QP context entry 有 lock bit，硬件自动管理 TX/RX 核对同一 QP 的互斥访问

### 3. 灵活性机制
- **Extensible CC Header**：在 RoCEv2 BTH 头后添加 0–64 B 的可扩展 CC 头，支持 ECN、RTT、INT、Token 四类 CC 信号
- **Selective Triggering**：Packet Filter 根据用户配置的 32-bit one-hot opcode 掩码，选择性地为特定类型的包生成事件

### 4. 编程接口
提供 4 个核心 API：`pollEventSync`、`updatePkt`、`updateContext`、`postEvent`，开发者只需定义 `TracedPkts`、`PktHeader`、`QPContext` 三个结构和 TX/RX 两个函数即可实现完整的 CCA。

---

## 四、实现细节

- **FPGA 原型**：基于 Xilinx Alveo U280 实现，6K 行 Chisel3 代码，复用 FpgaNIC 的 PCIe 和 CMAC 模块
- **RISC-V 核**：采用开源 riscv-mini，3 级流水线，修改了 cache/memory 子系统和硬件接口
- **运行频率**：SwCC 逻辑运行在 250 MHz
- **已实现的 CCA**：5 种代表性算法
  - DCQCN（ECN, rate-based）：140 行 C
  - TIMELY（timestamp, rate-based）：102 行 C
  - HPCC（INT, window-based）：148 行 C
  - Swift（timestamp, window-based）：164 行 C
  - Homa（token, credit-based）：95 行 C
- **FPGA 资源占用**：SwCC-8（16 核）仅占 LUT 8.6%、REG 4.8%、BRAM 11%，剩余资源充足

---

## 五、实验结果

实验平台：3 台服务器（Intel Xeon Silver 4214, 256 GB DDR4），通过 P4 可编程交换机连接，各配备 Xilinx U280 FPGA 和 Mellanox CX-5 NIC。

| 指标 | SwCC | RoCE (CX-5) | Soft-RoCE | BF3 PCC |
|------|------|-------------|-----------|---------|
| 控制环路 RTT | 3.1 µs (avg) | 3.1 µs | ~23 µs | 3.5 µs |
| 达到 100G 线速所需最小包 | 512 B | 512 B | 无法达到 | - |
| CC 控制器执行周期 | 1× (baseline) | - | ~3× | ~11.4× |

**吞吐量**：
- SwCC-8 和 RoCE-8 均在 512B 以上包大小达到 100 Gbps 线速
- SwCC-1 吞吐量为 RoCE-1 的 1.1–1.5 倍（因 SwCC 用 TX+RX 两个核处理单流）
- Soft-RoCE-24（24 线程）仅达 ~24 Gbps

**QP-aware Memory 效果**：
- 相比 naive cache，QP-aware memory 减少内存访问时间至少 50%
- 吞吐量提升：naive cache 约为 QP-aware memory 的 40%（小包场景）

**端到端性能**：
- SwCC vs RoCE（100 Gbps）：SwCC 的 DCQCN 实现 FCT 略优于 CX-5
- SwCC vs Soft-RoCE（10 Gbps）：Soft-RoCE 的 FCT 分别是 SwCC 的 14×（TIMELY）、39×（DCQCN）、42×（HPCC）

**ASIC 模拟估算**：达到 800 Gbps 线速，naive cache 需要 8 GHz 核频，QP-aware memory 仅需 2.4 GHz。

---

## 六、批判性分析

1. **FPGA 原型 vs ASIC 声称的差距**：论文核心贡献在 FPGA 上验证，但反复声称"ASIC 设计可轻松扩展到更高带宽"。ASIC 估算仅基于简单的频率模拟，未考虑实际流片中的时序收敛、功耗、面积等工程挑战。2.4 GHz RISC-V 核在 NIC 上并非易事，论文将其轻描淡写。

2. **与 BF3 PCC 的对比不够公平**：BF3 PCC 是商用产品中对外暴露的编程接口，其设计需兼顾通用性和多租户隔离等生产环境需求。SwCC 是学术原型，不需要考虑这些约束。直接比较执行周期（11.4× 差距）可能夸大了架构优势。

3. **实验规模有限**：仅 3 台服务器、最多 10 条流的 dumbbell 拓扑，远不能代表真实数据中心的复杂流量模式（incast、多跳拥塞、多租户干扰等）。论文未在任何大规模或真实负载下验证。

4. **QP 数量的扩展性存疑**：QP Context Table 仅 128 KB 可缓存 1K QP。虽然实验中测试了 100K QP 场景下吞吐量"几乎不变"，但这依赖于 QPN hint 预取能完全隐藏 DRAM 延迟——在高并发、小包、多 QP 场景下，预取失效率和 lock contention 可能导致性能退化。

5. **Extensible CC Header 的兼容性代价被低估**：论文承认使用自定义 CC 信号时需要对端也是 SwCC NIC，INT 场景还需要可编程交换机。这大幅限制了实际部署的可行性——数据中心不可能一次性替换所有 NIC 和交换机。

6. **Go-back-N 重传机制**：SwCC 使用 go-back-N 而非 selective repeat，在高丢包场景下效率低，但论文未讨论这一设计选择的影响。

---

## 七、AI Infra / MLSys 视角

1. **ML 训练通信的拥塞控制**：大规模分布式训练（尤其是 MoE 模型的 All-to-All 通信）产生极其 bursty 的流量模式，当前 DCQCN 等固定 CCA 难以应对。SwCC 的可编程 CC 框架允许针对训练通信的特征（如周期性 burst、collective 同步语义）设计定制化 CCA，这是一个有价值的方向。

2. **推理场景的延迟敏感性**：LLM 推理的 prefill/decode 阶段对网络延迟极其敏感（尤其是 disaggregated inference 中的 KV cache 传输）。SwCC 3 µs 级的控制环路延迟和 per-packet CC 能力，理论上可以更快地响应推理流量的微突发拥塞。

3. **可迁移的设计思路**：
   - QP-aware memory subsystem 的"利用领域知识构建专用内存子系统"的思路，可以迁移到 GPU/NPU 的片上 memory 管理
   - CSR-based fast path 的"硬件预写入+软件零延迟读取"模式，适用于其他需要软硬件协同的 NIC offload 场景

4. **可跟进方向**：
   - 针对 collective communication pattern（AllReduce, All-to-All）设计专用 CCA，利用 SwCC 框架在 NIC 上实现
   - 结合 network-aware scheduling：将训练调度器的信息传递给 NIC CC 控制器，实现"应用感知"的拥塞控制
   - 在 disaggregated memory/storage 场景下，利用可编程 CC 优化远程内存访问的尾延迟

---

## 八、总结

SwCC 通过在 RDMA 引擎中集成 RISC-V 核，并精心设计 TX/RX 分离多核架构、QP-aware memory subsystem 和硬件-软件交互机制，实现了软件可编程的 per-packet 拥塞控制。其控制环路延迟与商用 ASIC NIC 相当（~3.1 µs），同时支持 rate/window/credit 三类 CCA，开发者仅需 100–160 行 C 代码即可实现主流 CCA。主要局限在于：FPGA 原型到 ASIC 量产的差距被低估，实验规模偏小，Extensible CC Header 的部署兼容性受限。整体而言，SwCC 为数据中心可编程拥塞控制提供了一个有说服力的架构方案，尤其适合 CCA 快速迭代的研发测试场景。
