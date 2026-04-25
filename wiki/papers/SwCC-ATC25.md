---
type: paper
name: SwCC
full_title: "SwCC: Software-Programmable and Per-Packet Congestion Control in RDMA Engine"
authors: [Hongjing Huang, Jie Zhang, Xuzheng Chen, Ziyu Song, Jiajun Qin, Zeke Wang]
venue: ATC
year: 2025
tags: [rdma, congestion-control, smartnic, risc-v, fpga]
source_pdf: "[[atc2025-huang-hongjing.pdf]]"
source_md: "[[atc2025-huang-hongjing]]"
---

# SwCC: Software-Programmable and Per-Packet Congestion Control in RDMA Engine (ATC 2025)

> **一句话总结**：在 NIC 引擎里集成 RISC-V 核做软件可编程的 per-packet 拥塞控制，达到 ASIC 级 3.1 µs 控制环 RTT 与 100 Gbps 线速，且用 100~150 行 C 代码即可实现 DCQCN/TIMELY/HPCC。

## 问题

RDMA 拥塞控制有四种方案各有缺陷：1) ASIC NIC（如 Mellanox CX 系列）控制环延迟低但写死，11 个新 CCA 在 3 年内提出而 Mellanox 10 年只发了 7 款 NIC；2) CPU-based（Soft-RoCE）灵活但 PCIe + 内核栈让 control loop 长 23 µs，交换机队列排空时间增加 7.8×；3) FPGA SmartNIC（Tonic、NanoTransport）需写 HDL，开发周期长；4) SoC SmartNIC（NVIDIA BF3 PCC）虽支持 C 编程，但 DPA 单核弱、cache/memory 慢（300ns），无法做 per-packet CC，只支持 rate-based。

## 核心方法

把 RISC-V 核嵌入 RDMA engine，关键是与 NIC 资源精细 co-design：

- **TX/RX 分离多核**：每个核只处理 TX 或 RX 函数，QPN mod N 映射到固定核避一致性问题。FPGA 布线减少 50%，频率提升最多 16%。
- **QP-aware 内存子系统**：抛弃通用 cache。on-chip SRAM 组织成 4-way set-associative，每条 cache line 直接装一个 QP 的全部 context（128B），用 on-NIC DRAM 做 backing。CSR-based fast path：硬件预先把 QP context 和包头写入 64 个 RISC-V CSR，CC 核 1 cycle 读到 GPR；prefetch with QPN hint 在 RX Parser 阶段提前从 DRAM 拉 QP context 隐藏 60ns 延迟；硬件锁保证 TX/RX 核并发访问一致。
- **可扩展 CC header**：RoCEv2 BTH 后追加最多 64 字节自定义头，支持 ECN/RTT/INT/Token 四类信号。Packet Filter 让用户用 32-bit one-hot CSR 决定哪些 opcode 触发 CC 事件。
- **简洁 API**：pollEventSync/postEvent/updatePkt/updateContext 四个函数。

在 Xilinx U280 FPGA 实现（6K 行 Chisel3），引擎跑 250 MHz，复用 FpgaNIC 的 PCIe/CMAC。深度细节回 [[atc2025-huang-hongjing]]。

## 关键结果

- 控制环 RTT 3.1 µs（vs ConnectX-5 RoCE 3.1 µs；Soft-RoCE 23 µs）
- 100 Gbps 线速所需最小包 512B，与 CX-5 持平
- DCQCN/TIMELY/HPCC/Swift/Homa 五种 CCA 仅需 140/102/148/164/95 行 C
- QP-aware memory 比 naive cache 减少 ≥50% 访问时间，CC 控制器执行 cycle 比 BF3 PCC 少 11.4×、比 Soft-RoCE 少 3×
- 模拟 ASIC 设计，QP-aware memory 仅需 2.4 GHz 即达 800 Gbps（naive cache 需 8 GHz）
- FPGA 资源 SwCC-8 占 LUTs 8.6%，留有大量余量

## 相关

- **相关概念**：[[RDMA]]、[[Congestion-Control]]、SmartNIC、RISC-V
- **同类系统**：Tonic、NanoTransport、BlueField-3 PCC、Soft-RoCE
- **同会议**：[[ATC-2025]]
