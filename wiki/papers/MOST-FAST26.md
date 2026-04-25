---
type: paper
name: MOST
full_title: "Getting the MOST out of your Storage Hierarchy with Mirror-Optimized Storage Tiering"
authors: [Kaiwei Tu, Kan Wu, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau]
venue: FAST
year: 2026
tags: [storage-hierarchy, tiering, mirroring, cachelib, load-balancing]
source_pdf: "[[fast2026-tu.pdf]]"
source_md: "[[fast2026-tu]]"
---

# Getting the MOST out of your Storage Hierarchy with Mirror-Optimized Storage Tiering (FAST 2026)

> **一句话总结**：在经典 tiering 上加少量（约 20% 容量）热数据 mirror，用一个 offloadRatio 反馈控制器在两层设备间路由请求，在静态 cache workload 上吞吐比 SOTA（Colloid/HeMem/Orthus）高最多 2.34×，P99 延迟降最多 75%，dynamic workload 写入量减少最多 84%。

## 问题

新一代设备（low-latency SSD、NVMeoF SSD、SATA SSD、disaggregated SSD 等）和「DRAM-on-HDD」时代不同——performance 层和 capacity 层的延迟/带宽比可能只有 1.25:1 ~ 2.2:1，性能区间大量重叠。经典做法都不适合：

- **Single copy**：striping 不擅长异构；hotness-based tiering（HeMem、BATMAN、Colloid）需要昂贵的 migration 调整负载分布，跟不上 dynamic workload，且写迁移浪费 SSD 寿命。
- **Multiple copy**：mirroring 写带宽被慢盘卡死，capacity 利用率低；caching/Orthus 性能层只存 duplicate，浪费小盘容量，且写场景受限。

migration-based 方法在存储层的核心痛点：数据集大、写带宽低、读写互扰、设备磨损、软件间接层延迟相对慢——决定了不能像内存层级那样靠迁移调负载。

## 核心方法

**MOST = mirroring + tiering 的混合布局**：
- **Mirrored class**（小，~20% 总容量，存最热数据，两层都有副本）+ **Tiered class**（单副本，warm 在性能层，cold 在容量层）。
- **OffloadRatio 反馈控制器**：测两设备 end-to-end latency，比较 L_P 与 L_C。L_P > (1+θ)·L_C → 增大 offloadRatio（更多请求路由到 capacity）；反之减小；扩展 mirrored class 仅在 offloadRatio 已到上限时触发。
- **Probability-based write allocation**：新写以 offloadRatio 概率分到 capacity，自适应地不挤爆性能层。
- **Subpage-level dirty tracking**：mirrored class 内部按 4 KB 子页跟踪 invalid bit + location bit，写入只更新一份，读取仍能负载均衡（避免 mirroring 的写 bottleneck）；后台 selective cleaning 按 rewrite distance 决定何时同步双份。
- **Tail latency protection**：用户可设 max offloadRatio，避免 capacity 层尾延迟传染。

**Cerberus 实现**：在 [[CacheLib]] 的 storage management layer 替换 striping，提供 block 接口给 LOC（log-structured）和 SOC（hash bucket）使用。

## 关键结果

- 静态 cache workload：吞吐最多 2.34× 提升 vs Colloid/HeMem/Orthus；P99 延迟最多降 75%。
- 四个生产 cache workload：吞吐最多 1.86×；P99 GET 延迟最多降 90%。
- Dynamic workload：device 写入量比 Colloid 少最多 84%（因为靠路由而非迁移调负载）。
- 评估覆盖三类设备（Optane、PCIe 4.0/3.0 NVMe Flash、NVMeoF over RDMA、SATA Flash）。

## 相关

- **相关概念**：Storage Tiering、Mirroring、Caching、Load Balancing、Heterogeneous Storage
- **同类系统**：[[CacheLib]]、HeMem、Colloid、Orthus、BATMAN、AutoTiering、Nomad
- **同会议**：[[FAST-2026]]
