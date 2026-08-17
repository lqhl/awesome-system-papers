---
type: concept
aliases: [CXL, Compute Express Link, CXL.mem, CXL.io, CXL.cache, CXL-SSD]
last_updated: 2026-08-17
tags: [memory, disaggregation, interconnect, tiered-memory, datacenter]
---

# CXL

> Compute Express Link（CXL）是在 [[PCIe]] 物理层之上连接处理器、内存和设备的一组协议。它让主机能用 load/store 访问扩展内存，也能支持设备缓存主机内存和机架级资源池。不过，CXL 只提供连接与一致性的基础能力；放什么数据、如何迁移、怎样隔离拥塞和如何恢复故障，仍由系统软件解决。

## 核心思想

CXL 不是一种单独的“远端内存”。它主要包含三条协议路径：

- `CXL.io` 负责设备发现、配置和普通 I/O，角色接近 PCIe。
- `CXL.cache` 允许设备缓存主机内存，并与主机维持一致性。
- `CXL.mem` 让主机访问设备侧内存，常用于内存扩展和分层。

常见系统把本地 DRAM 当快层，把 CXL memory 当容量更大的慢层；也有工作把多台主机、SSD、NIC 或近内存计算单元接到 CXL fabric。协议让资源“能被访问”，但不会自动解决四件事：访问延迟是否可接受、容量和带宽如何分配、多个使用者怎样同步、设备或交换机故障后怎样恢复。

## 为什么重要

内存容量、内存带宽和设备利用率经常不同步。传统服务器把 DIMM、NIC 和 SSD固定绑定给一台主机，容易出现一项资源不够、另一项资源空闲。CXL 提供了重新组合这些资源的硬件入口。

OSDI 2026 的论文也表明，“把内存接上 CXL”只是开始：[[RamRyder-OSDI26]] 分别管理容量和 memory-channel 带宽；[[NEMO-OSDI26]] 在控制器旁观测真实访问；[[OBASE-OSDI26]] 重新组织对象，让 page-level tiering 看见更纯的冷热页；[[Megalon-OSDI26]]、[[Duhu-OSDI26]] 和 [[Soul-OSDI26]] 则分别用部分一致、不可变对象和广义一致性来处理共享语义。

## 关键观察 / 隐含假设

- **容量和带宽不是同一种资源。** [[RamRyder-OSDI26]] 关闭默认 channel interleaving，以 page-to-channel mapping 给虚拟机单独增加容量或带宽。应用实测支持单机机制，但论文报告的集群利用率提升来自 Alibaba trace 外推，不是生产部署。
- **“远端页”过于粗。** [[OBASE-OSDI26]] 发现一个页里的少量热对象会把大量冷字节留在快层，因此先按对象迁移、再把同温度对象聚到页中。这个结论依赖 managed runtime 能重定向对象引用，并不直接适用于任意原生程序。
- **控制器旁边更容易看到真实流量。** [[NEMO-OSDI26]] 的 CXL 2.0 FPGA 原型能做地址映射、计数和阈值通知。原型只观察 CXL 慢层，而且通知由 1 ms 轮询模拟，所以“完整、即时、低开销”三者尚未在同一实机中全部证明。
- **共享数据和共享元数据常有不同需求。** [[Megalon-OSDI26]] 把大而冷的对象索引复制到主机，只把小而热的一致性记录放进有限的一致区；[[Duhu-OSDI26]] 直接共享不可变大对象，把可变元数据交给单一 owner。两者都依赖明确的工作负载语义，而不是提供通用共享内存。
- **硬件一致性并不等于高效同步。** [[Soul-OSDI26]] 把锁和相关数据纳入一致性协议，减少高延迟网络上的重复往返；代价是修改 cache controller 和 directory。其原型是 8 个 Ethernet compute blade，不是真实 CXL 3.x fabric。
- **近内存计算能减少数据移动，但证据常含模拟。** [[MAC-OSDI26]] 把 Linux 回收元数据遍历卸载到 CXL 侧，完整系统主要用双 NUMA 模拟，FPGA只验证部分热路径；[[Cocoon-OSDI26]] 和 [[ContextAwareMoE-CXLNDP-arXiv25]] 也把历史状态或 MoE expert 计算移到近内存端，但分别含带宽缩放和 Ramulator 模拟。
- **资源池依赖负载不同时到峰值。** [[Espresso-OSDI26]] 让 SSD 借用其他盘的处理器和 DRAM，[[Oasis-SOSP25]] 与 [[DRack-ATC25]] 分别池化 PCIe 设备和 NIC。若全盘重建、集中 checkpoint 或网络突发同时发生，统计复用空间会明显缩小。

## 设计空间与取舍

- **放置粒度**：page 兼容现有 OS，但冷热混杂；object 或 metadata record 更精确，却要求 runtime、索引和生命周期管理。
- **静态放置或动态迁移**：动态迁移能跟随 phase，迁移本身会占 CXL 带宽。[[DSA-2LM-ATC25]] 用 Intel DSA 卸载页复制，说明迁移引擎也会成为设计的一部分。
- **完全一致、部分一致或软件 owner**：完全一致最透明，目录和 snoop 状态的成本也最高；部分一致节省硬件状态，但应用必须区分哪些数据会变；单 owner 语义简单，却可能形成热点和故障恢复难点。
- **缓存或直接慢层访问**：缓存能隐藏常见访问，miss 会形成双峰延迟。[[Cylon-FAST26]] 专门模拟 CXL-SSD 的亚微秒 hit 和数十微秒 miss，说明只报告平均延迟会掩盖问题。
- **通用 CPU 或近内存加速器**：加速器减少搬运和 CPU 开销，但操作集合有限、开发和验证成本更高，也更依赖尚未普及的硬件。
- **单机扩展或 fabric 池化**：单机 Type-3 memory 更容易落地；多主机池能提高利用率，却把交换机拥塞、权限、故障域和多租户 QoS 放进关键路径。

## 引用本概念的论文

### 直接研究 CXL 内存与共享

- [[StarfishOS-SOSP26]] — 官方 metadata 显示其以 state-partitioned microkernel 重访 CXL single-system image；截至 2026-08-17 无公开全文，状态切分、一致性和故障边界尚不能从题名确认。
- [[RamRyder-OSDI26]]、[[DSA-2LM-ATC25]]、[[Demeter-SOSP25]]、[[SoarAlto-OSDI25]]：分别研究 channel 资源、页迁移、虚拟机委派和分层放置。
- [[NEMO-OSDI26]]、[[OBASE-OSDI26]]、[[LiteSwitch-OSDI26]]：分别从访问观测、对象重组和硬件推测隐藏慢层开销；LiteSwitch 主要是模拟证据。
- [[Megalon-OSDI26]]、[[Duhu-OSDI26]]、[[Soul-OSDI26]]：三种共享语义，分别面向部分一致区域、不可变对象和锁/数据一体化一致性。
- [[Cocoon-OSDI26]]、[[MAC-OSDI26]]、[[ContextAwareMoE-CXLNDP-arXiv25]]：把特定计算移到 CXL/近内存端。
- [[Cylon-FAST26]]、[[Xerxes-FAST26]]：在真实大规模 CXL 硬件不足时，提供 CXL-SSD 和 CXL 3.1 系统研究工具。

### 设备池与邻接系统

- [[Espresso-OSDI26]]、[[Oasis-SOSP25]]、[[DRack-ATC25]]：共享 SSD 内部资源、PCIe 设备和 NIC。
- [[FORGE-OSDI26]]、[[DMTree-FAST26]]、[[DGC-OSDI26]]：研究解耦内存上的缓存元数据、树索引和远端 GC；它们说明 CXL/RDMA 连接之上仍需减少同步与突发。
- [[MDK-OSDI26]]、[[ScaleSwap-FAST26]]、[[M3U-OSDI26]]、[[Svalinn-OSDI26]]：讨论回收、交换、虚拟机迁移和内存带宽过载，主要提供操作系统侧的邻接约束，不是 CXL 协议本身的证据。
- [[UnICom-FAST26]]、[[LESS-FAST26]]、[[PIMANN-ATC25]]：这些页提到 CXL 作为实现选择、比较对象或未来平台；不能据此声称相应机制已经在真实 CXL fabric 上验证。

## 已知局限 / 开放问题

- 多数研究只有单机 CXL 2.0、NUMA 模拟、FPGA 原型或小规模 Ethernet 集群。CXL 3.x 的交换机拥塞、目录规模和故障恢复仍缺充分实机数据。
- CXL memory 的平均延迟不能代表 tail：cache miss、迁移、snoop、交换机排队和共享服务会叠加。
- 热度变化可能让迁移来回震荡；池内负载相关时，资源借用也会失效。系统需要公开 crossover，而不是只报告最有利的负载。
- 跨主机 load/store 扩大了权限、隔离和故障域。设备热拔、旧 owner 复活、半完成写和交换机分区都需要明确协议。
- 不同厂商设备的 channel mapping、缓存策略和 telemetry 能力并不统一；依赖隐藏硬件细节的策略可能无法移植。
