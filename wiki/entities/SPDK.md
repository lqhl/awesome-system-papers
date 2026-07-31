---
type: entity
kind: tool
aliases: [Storage-Performance-Development-Kit]
status: active
last_updated: 2026-07-30
tags: [storage, nvme, kernel-bypass, userspace-io]
---

# SPDK

> SPDK 是面向 NVMe 的用户态 kernel-bypass 存储栈，以 polling、per-core queue pair 和 zero-copy 路径换取高吞吐与低延迟。

## 是什么

SPDK 将设备 queue、completion polling 与 buffer 管理放进 userspace，绕过通用 block/file-system path。它既可作为应用 data plane，也常被论文用作“设备可达到的上限”基线，用来分离 kernel crossing、page cache、filesystem semantics 与真正介质性能。

代价是 CPU core ownership、POSIX compatibility、共享设备协调和 crash semantics。polling 在独占 core 上高效，在 oversubscription 或 energy-sensitive 环境下可能反而昂贵。

## 关键观察 / 隐含假设

- **polling 把 latency 换成持续 CPU 占用**：[[DPAS-FAST26]] 比较 polling、hybrid polling 与 interrupt；[[CoPilotIO-OSDI26]] 进一步把 GPU I/O polling 转移给 CPU，并在 CPU 紧张时动态回退。
- **kernel-bypass 不是文件系统替代品**：[[Oxbow-OSDI26]] 保留 kernel read/page-cache 路径，只把 write 和 background metadata work 分派到 userspace/CSD。
- **高带宽 SSD 改变索引算法优先级**：[[Helmsman-OSDI26]] 利用 SPDK 与多 Gen5 SSD，使 dependency-free clustered ANNS batch I/O 优于长依赖链 graph search。
- **tail 与共享资源仍由上层负责**：[[RosenBridge-FAST26]]、[[uCache-FAST26]]、[[RISTRETTO-FAST26]] 表明 cache、queueing、NUMA 和隔离策略决定真实 workload，而非 SPDK API 本身。

## 演进时间线

- 2025 SOSP：[[Sandman-SOSP25]]、[[Aeolia-SOSP25]] — 在高性能 storage stack 上重构调度与 isolation。
- 2026 FAST：[[DPAS-FAST26]] — 系统分析 polling/interrupt 的 workload-dependent 取舍。
- 2026 OSDI：[[CoPilotIO-OSDI26]] — 用 CPU 代理 GPU storage completion，释放 GPU SM。
- 2026 OSDI：[[Oxbow-OSDI26]] — 在 multi-component filesystem 中选择性保留 kernel 与 userspace 路径。
- 2026 OSDI：[[Helmsman-OSDI26]] — 以 SPDK 驱动多 SSD 的 production-scale clustered ANNS。

## 相关概念

- [[Kernel-Bypass]]、[[NVMe]]、[[Polling]]、[[Userspace-IO]]、[[Zero-Copy]]

## 相关论文

- [[DPAS-FAST26]] — 分析 SPDK completion path 在不同 contention 下的最优策略。
- [[CoPilotIO-OSDI26]] — 将 I/O polling 在 CPU/GPU agents 间切换。
- [[Oxbow-OSDI26]] — 选择性采用 userspace write path，而非完全舍弃 kernel filesystem。
- [[Helmsman-OSDI26]] — 用 SPDK 与多 Gen5 SSD 实现高吞吐 ANNS。
- [[RosenBridge-FAST26]] — 探索高性能 NVMe data path 的架构取舍。
- [[UnICom-FAST26]] — 将 SPDK 作为 userspace storage building block。
