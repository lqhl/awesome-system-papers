---
type: paper
name: Scalio
full_title: "Scalio: Scaling up DPU-based JBOF Key-value Store with NVMe-oF Target Offload"
authors: [Xun Sun, Mingxing Zhang, Yingdi Shan, Kang Chen, Jinlei Jiang, Yongwei Wu]
venue: OSDI
year: 2025
tags: [storage, dpu, jbof, key-value-store, rdma, nvme-of]
source_pdf: "[[osdi25-sun.pdf]]"
source_md: "[[osdi25-sun]]"
---

# Scalio: Scaling up DPU-based JBOF Key-value Store with NVMe-oF Target Offload (OSDI 2025)

> **一句话总结**：用 NVMe-oF Target Offload 把 SSD I/O 彻底从 DPU CPU 卸载到 HCA 硬件，配合 RDMA 缓存一致性协议，在高密度 JBOF 上把小 KV 存储吞吐量拉到 LEED 的 2.5× 到 17×。

## 问题

DPU-based JBOF（Just a Bunch of Flash）是能效友好的高密度存储架构，一个 DPU 挂多个 NVMe SSD。但现有 JBOF KV 存储（如 LEED）在 SSD 数量从 1 增到 7 时吞吐量在 4 块 SSD 处饱和——瓶颈在 DPU 上那些弱 ARM 核的 CPU 上。

讽刺的是网络资源被严重浪费：测得 LEED 的网络 I/O 利用率不到 1%，Mellanox ConnectX-6 HCA 有 200M IOPS 能力但只跑到 600K。DPU CPU 和网络能力差三个数量级，这给「把 SSD I/O 卸载到网络」留出了巨大窗口。

## 核心方法

Scalio 的第一招是利用 NVMe over Fabrics Target Offload，把 NVMe-oF 协议实现直接下沉到 HCA 硬件上：client 发出的 NVMe 命令由 HCA 通过 PCIe P2P 直连 SSD，完全绕过 DPU CPU。这样 target 端 CPU 占用降到零。

第二招是双层内存结构：DPU DRAM 里维护一个 RDMA 可访问的 hash 表作为热读缓存，每个 block 存多个 key-value slot（block size 放大到 1KB，利用网络带宽空洞）；写请求走 ring buffer + group commit，DPU CPU 批量刷 SSD 而不是逐条。客户端通过单边 [[RDMA]] 操作和 CAS 直接操作 slot，把索引维护成本卸载到客户端。

第三招解决 disaggregated 架构下的缓存一致性：DPU DRAM 和 SSD 之间没有硬件 cache coherence 协议。Scalio 设计了一套 RDMA 驱动的缓存一致性协议，用 occupied/complete 两个 flag + double-read 校验，在保证 linearizability 的同时尽量避免高成本的 RDMA CAS（CAS 的 IOPS 比 read/write 低 10×）。

## 关键结果

- 相比 LEED：吞吐提升 2.5× 到 17×
- 相比 LEED + Ditto（disaggregated DRAM cache 作为内存层）：吞吐提升 1.8× 到 3.3×
- 在 YCSB A/B/C/D/F 工作负载下，SSD 数从 1 到 7 吞吐量可持续扩展（LEED 在 4 块 SSD 就饱和）
- NVMe-oF Target Offload 让 target CPU 占用从 562% 降到 0%

## 相关

- **相关概念**：[[RDMA]]、[[KV-Cache]]
- **同会议**：[[OSDI-2025]]
