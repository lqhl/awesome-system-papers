---
type: paper
name: Collective-NoC
full_title: "A Lightweight High-Throughput Collective-Capable NoC for Large-Scale ML Accelerators"
authors: [Luca Colagrande, Lorenzo Leone, Chen Wu, Tim Fischer, Raphael Roth, Luca Benini]
venue: MLSys
year: 2026
tags: [noc, collective-communication, on-chip, gemm, ml-accelerator]
source_pdf: "[[42a0e188f5033bc65bf8d78622277c4e.pdf]]"
source_md: "[[42a0e188f5033bc65bf8d78622277c4e]]"
---

# A Lightweight High-Throughput Collective-Capable NoC for Large-Scale ML Accelerators (MLSys 2026)

> **一句话总结**：在 FlooNoC 上扩展 collective-capable NoC + Direct Compute Access（DCA），router 面积仅 +**16.5%**，multicast/reduction 原语 geomean 加速 **2.9×/2.5×**，大 mesh GEMM 端到端最高 **3.8×**、能效 **1.17×**。

## 问题

单 die 集成数千 PE 后，on-chip 通信与 collective（barrier、broadcast、reduction）成为扩展瓶颈；计算增速远超带宽，大 mesh GEMM 利用率可 **<50%**。现有 NoC 多 unicast，缺乏高吞吐 in-network reduction。

## 核心方法

**Collective-capable NoC**：扩展 FlooNoC NI/router，AWUSER 携带 multi-address mask 与 opcode；multicast router fork 多向；parallel reduction 合并 AXI 响应；wide reduction 集中算术单元。

**DCA（Direct Compute Access）**：互连直接借用 Snitch cluster 8×FPU 做 512-bit wide in-network FP reduction，SIMD 下每 cycle 最高 **64×** 8-bit FP reduce。

**Multi-address encoding**：XY mask 对数级表示多目的地，适配规则 submesh 地址映射。

## 关键结果

- 4×4 mesh 1–32 KiB 传输：multicast **2.9×**、reduction **2.5×** geomean vs 软件基线
- 256×256 mesh GEMM：multicast 支持 **3.8×**、reduction **2.4×** 估计性能；能效至 **1.17×**
- TSMC 7nm：router +**16.5%** 面积，full tile **<1%**；timing 无退化

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Flash-Attention]]
- **同类系统**：FlooNoC、FlatAttention、NVIDIA NVSwitch collectives
- **同会议**：[[MLSys-2026]]