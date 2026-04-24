---
type: paper
name: Collective-NoC
full_title: "A Lightweight High-Throughput Collective-Capable NoC for Large-Scale ML Accelerators"
authors: [Luca Colagrande, Lorenzo Leone, Chen Wu, Tim Fischer, Raphael Roth, Luca Benini]
venue: MLSys
year: 2026
tags: [noc, collective-communication, ml-accelerator, in-network-computing, hardware]
source_pdf: "[[42a0e188f5033bc65bf8d78622277c4e.pdf]]"
source_md: "[[42a0e188f5033bc65bf8d78622277c4e]]"
---

# A Lightweight High-Throughput Collective-Capable NoC for Large-Scale ML Accelerators (MLSys 2026)

> **一句话总结**：给 tile-based manycore ML 加速器设计 collective-capable NoC（扩展 FlooNoC），用 Direct Compute Access 让 interconnect fabric 借用 compute tile 的 FPU 做 in-network reduction，router 面积仅增 16.5%；在 1–32 KiB 数据上 multicast/reduction 分别 2.9×/2.5× 几何平均加速，大 mesh 下 GEMM 端到端最高 3.8× 加速。

## 问题

Tile-based manycore ML SoC（如 Cerebras WSE-3、Tenstorrent Blackhole、AMD XDNA、SambaNova SN40L、Meta MTIA）正把上千 PE 塞到单 die，片上分布式系统的边界消失。Collective 通信（MPI 统计显示 reduction、barrier、broadcast 最常用）如果没有硬件支持就会吃掉带宽。实验显示 256×256 mesh 跑 GEMM 时利用率 < 50%，memory-bound。FlashAttention-3 类 workload 通过协同片上 collective 操作能拿到 4× speedup（FlatAttention 证明）。已有 NoC 只做 unicast，需要一个支持片上 multicast + reduction 的 collective NoC，但高吞吐量 in-network arithmetic reduction 是否能在片上便宜实现是公开问题。

## 核心方法

**基础架构**：扩展 FlooNoC（SoA 开源 NoC），AXI4-compliant，用 narrow 网（64 bit, 延迟敏感小包）+ wide 网（512 bit, bursted bulk transfer）双网络。

**1. Multi-Address Encoding**：沿用先前工作的 (address, mask) 对，mask 放 AWUSER signal；mask bit = 1 表示对应 address bit 是 "don't care"，n 位 mask 能表示 2ⁿ 个目标，编码只随地址空间对数增长，和目的数独立。

**2. Multicast Router Extension**：`xy_route_fork` 根据 X/Y mask 选出多个输出口，下游 `stream_fork` 只在所有输出口 ready 时才接受输入。Narrow + wide 网都加。

**3. Parallel Reduction Router Extension**：每个输出口的 `output_arbiter` 把 reduction 包路由到 `reduction_arbiter`，`synchronization module` 按 X/Y mask 等齐来自多源的 reduction flit 再下送。`leading_zero_counter` 仲裁多并发 reduction，副本化 sync module 保证不死锁。实现三个轻量 op：`CollectB`（AXI 多 B response 聚合），`LsbAnd`（LSB bitwise AND，用于 barrier），`SelectAW`（多 AW 聚合）。

**4. Wide Reduction Router Extension**（浮点算术 reduction）：全 router 共享单个集中实例，限 2-input reduction；带 hdr buffer 吸收 pipelined FPU 的延迟，buffer depth > pipeline depth 可达到 1 reduction/cycle 吞吐。额外提供 offload 口给外部 compute 资源。

**5. Direct Compute Access (DCA)**：
- 核心创新。像 DMA 直接访存一样，让 interconnect 直接访问 cluster 的 FPU 资源做 in-network compute，此时 core 可做其他工作或进低功耗。
- Snitch cluster 装 3 个 512-bit 端口（2 操作数 + 1 结果），把 512-bit 操作数切成 8 个 64-bit 喂给 8 个 FPU 并行。SIMD 后 8× FP64 或 64× INT8 reduction/cycle。
- DCA 请求与 core 自己的 FPU 请求用 tag 区分并仲裁。把 DCA 接口接到 router offload 口，复用已有 datapath，开销微乎其微。

**6. Barrier via LsbAnd**：传统 barrier 用 amoadd 原子自增 counter（3 cycle/cluster），换成 `LsbAnd` reduction + `fence` 指令，数据包在路径上边走边 reduce，scale 从 3.3 cycle/cluster 降到 1.3 cycle/cluster（匹配预期 1 cycle/cluster）。

## 关键结果

- TSMC 7nm，FUSION COMPILER 2024.09，1 GHz 目标（SS, -40°C, 0.675V），无 timing 退化。
- **面积**：NI 仅增 3.5%；完整 collective router（multicast + parallel reduction + wide reduction）相比 baseline FlooNoC router 只增 **16.5%**；整个 cluster tile（5.6 MGE）视角下 **< 1%** 开销。
- **性能**（4×4 mesh，1–32 KiB 数据）：
  - Multicast 几何平均 **2.9×** 加速 vs. 软件优化版。
  - Reduction 几何平均 **2.5×** 加速。
  - Hardware barrier 1.3 cycle/cluster vs. software 3.3 cycle/cluster。
- **大 mesh GEMM**（估算）：
  - Multicast 最高 **3.8×** 加速。
  - Reduction 最高 **2.4×** 加速。
  - Energy 最高 **1.17×** 节能。
- 设计可泛化到任何 2D mesh + 瓦片内有 arithmetic unit + 可编程通信的加速器。

## 相关

- **相关概念**：[[Collective-Communication]]、[[In-Network-Computing]]、[[NoC]]、[[GEMM]]、[[Barrier-Synchronization]]、[[Multicast]]、[[AllReduce]]
- **对比系统**：FlooNoC（基线）、FlashAttention-3、FlatAttention、NVIDIA SHARP
- **相关加速器**：Cerebras WSE-3、Tenstorrent Blackhole、AMD XDNA、SambaNova SN40L、Meta MTIA
- **同会议**：[[MLSys-2026]]
