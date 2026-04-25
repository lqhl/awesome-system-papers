---
type: paper
name: Cylon
full_title: "Cylon: Fast and Accurate Full-System Emulation of CXL-SSDs"
authors: [Dongha Yoon, Hansen Idden, Jinshu Liu, Berkay Inceisci, Sam H. Noh, Huaicheng Li]
venue: FAST
year: 2026
tags: [cxl, ssd, emulator, femu, kvm, virtualization]
source_pdf: "[[fast2026-yoon.pdf]]"
source_md: "[[fast2026-yoon]]"
---

# Cylon: Fast and Accurate Full-System Emulation of CXL-SSDs (FAST 2026)

> **一句话总结**：Cylon 在 [[FEMU]] + QEMU/KVM 上加 Dynamic EPT Remapping 与 Shared EPT Memory 两大机制，构建首个 full-system [[CXL]]-SSD 仿真器——cache hit 走直映 EPTE 不触发 VM-exit（~150 ns），cache miss 才陷入 KVM 走 [[FEMU]] 的 NAND 时序模型（~40 µs），对 Samsung CMM-H 原型校准后，速度近 bare-metal、可跑 unmodified OS 与全栈 workload。

## 问题

[[CXL]]-SSD（如 Samsung CMM-H）把小 DRAM cache + 大 NAND SSD 暴露成 byte-addressable memory tier，hit 亚微秒、miss 数十微秒。研究者想探索 cache policy、prefetch、hardware-software co-design，但已有平台都不够：
- **商用 prototype**：firmware 不开放，policy knob 极少。
- **OpenCXD（FPGA）**：能跑功能但不模拟 NAND 时序。
- **Trace-driven simulator**（MQSim-CXL、ESF）：太慢、跑不了真应用。
- **Cycle-accurate simulator**（CXL-SSD-Sim、CXL-DMSim 基于 gem5）：精度高但慢得没法做 system-level 研究。
- **QEMU upstream CXL**：所有访问走 MMIO/VM-exit，单访问 ~15 µs，根本没法模拟亚微秒 cache hit。

需求：full-stack execution + near bare-metal 速度 + accurate device 时序 + 可扩展 policy。

## 核心方法

**Hybrid access path** (Algorithm 1)：cache hit 走 fast path（不 VM-exit）、cache miss 走 slow path（陷入 [[FEMU]] 跑 NAND 时序）。

**Dynamic EPT Remapping (DER)**：每个 page 的 EPTE 在两态间切换：
- **Direct state**：EPTE = [HPA | DIRECT_MASK]，RW、WB 内存类型，guest 直接 load/store cache，无 VM-exit。
- **Trap state**：R=W=X=0，访问触发 EPT violation 进 KVM，KVM 把请求转给 [[FEMU]] fetch SSD。
- Fill 时把 EPTE 改 Direct + INVEPT 失效 stale TLB；evict 时改回 Trap，dirty 先写回 NAND 再清。
- 安全：VM 创建时锁定 cache 与 SSD 两段 GPA range，KVM 用 mask 限定只能改 PFN+R/W/X，其它字段不可动。

**Shared EPT Memory**：VM 启动时预分配整段连续 leaf EPTE，映射到内核与 QEMU/[[FEMU]] 双方 → FEMU 用 LPN 直接索引更新 EPTE，O(1)，无 syscall、无 page-table walk。多次更新可批量 INVEPT 摊销。

**Configurable caching layer**：插件式 eviction（FIFO、[[S3-FIFO]]、CLOCK ...）+ prefetch（next-line 等）。提供观测：周期清 EPT accessed bit + Linux DAMON、可选 Intel PEBS 采样。

**Application-level interface**：ring queue 共享内存 + 用户库，让 app 主动 prefetch/pin/evict、查 stat（类比 OpenChannel-SSD 的 host-managed FTL 思路）。

## 关键结果

- 对 Samsung CMM-H 真机校准：bandwidth、latency 分布、Redis 与图分析 workload 趋势全部匹配。
- Cache hit ~150 ns（remote-NUMA DRAM）；cache miss ~40 µs（FEMU NAND 模型）；远好于 QEMU CXL 的 ~15 µs/访问。
- 跑 unmodified OS 与全栈应用，scalability 在 4 thread 处饱和（CMM-H 设备并发限制，非 host coherency）。
- 已 upstream 到 FEMU（github.com/MoatLab/FEMU），加 ~6,282 行 FEMU + ~1,261 行 Linux kernel。
- 支持探索超出 CMM-H 的设计：CXL-NVMe 一体化、CXL-FTL 直通、低延迟 flash 等。

## 相关

- **相关概念**：[[CXL]]、[[FEMU]]、EPT、KVM、[[S3-FIFO]]、DAMON
- **同类系统**：QEMU-CXL、MQSim-CXL、CXL-SSD-Sim、CXL-DMSim、OpenCXD、NVMeVirt
- **同会议**：[[FAST-2026]]
