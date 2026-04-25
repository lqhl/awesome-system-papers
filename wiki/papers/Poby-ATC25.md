---
type: paper
name: Poby
full_title: "Poby: SmartNIC-accelerated Image Provisioning for Coldstart in Clouds"
authors: [Zihao Chang, Jiaqi Zhu, Haifeng Sun, Yunlong Xie, Kan Shi, et al.]
venue: ATC
year: 2025
tags: [smartnic, container, coldstart, serverless, rdma]
source_pdf: "[[atc2025-chang.pdf]]"
source_md: "[[atc2025-chang]]"
---

# Poby: SmartNIC-accelerated Image Provisioning for Coldstart in Clouds (ATC 2025)

> **一句话总结**：把容器 image provisioning 的 download/decompress/transmit/unpack 拆开 offload 到 BlueField-2 SmartNIC 的 RDMA + 解压加速器 + on-NIC ARM + host CPU，pipeline + best-effort 分布式 registry，相比 containerd 快 13.2×、相比 iSulad 快 8×。

## 问题

云容器 coldstart 中 image provisioning 占主要开销，但被忽视：

- Warm start（CodeCrunch 90 TB 内存达成 80% 命中）、fast snapshot recovery（要求 stateless）、fast download（[[P2P]] 加速）都各自有局限，且无法完全避开 coldstart；
- 实测 image extraction（解压 + unpack）占 image provisioning 时间 >68.8%，但被现有研究忽略；
- Extraction 还会严重干扰共置应用（Redis 延迟涨 110×），因为是 CPU + IO 密集。

挑战：（C1）SmartNIC ARM CPU 性能弱，整个 offload 反而慢；（C2）serial pipeline 等待时间长；（C3）集中 registry 在 RDMA 下成新瓶颈。

## 核心方法

**Poby** 是软硬件协同系统，三大设计：

- **Disaggregated architecture**：把流程拆成 4 个操作并 offload 到合适硬件——download 走 SmartNIC RDMA，decompress 走片上解压加速器（zlib 7× 提速），transmit 走 PCIe 把 *已解压* 数据塞到 host，unpack 留在 host CPU（规避大量小文件 PCIe 事务瓶颈）。还允许跨节点 collaborative，用 `block_status` 标记数据是 raw 还是 decompressed。
- **Pipeline-based data-driven workflow**：把 image 切成 16 MB block（兼顾解压器 6.9 ms 启动开销和并行度），4 个操作并行 + redundant 加速器队列吸收 bubble；用每 block 头部内嵌 `block_index` + `block_status` 取代 centralized 控制消息（self-driven，pipeline 自驱动）。
- **Distributed image download**：best-effort 从其他刚好持有该 layer 的节点拉，IMI（Image Metadata Index）跟踪 layer 位置和节点工作量，回退到原 registry 保证 0 额外延迟；offload 到 SmartNIC 不占 host。

实现基于 NVIDIA BlueField-2（8 个 ARM A72 + 解压加速器），dual-card prototype。

## 关键结果

- 比 [[containerd]] 快 13.2×、比 [[iSulad]] 快 8×；host CPU 用量降 87.5%（vs iSulad）。
- 解压加速器在 ≥16 MB 块上比 host zlib 快平均 7×。
- Best-effort 分布式 download 与 [[Kraken]] / [[FaaSNET]] 在 host CPU 上的 scalability 相当，但只用 SmartNIC ARM。
- Redis 共置干扰几乎消失（host CPU 不再被 unpack 抢占）。

## 相关

- **相关概念**：[[SmartNIC]]、[[RDMA]]、[[Container-Coldstart]]、[[OCI-Image]]
- **同类系统**：[[Kraken]]、[[FaaSNET]]
- **同会议**：[[ATC-2025]]
