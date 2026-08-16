---
type: concept
aliases: [nvme, Non-Volatile Memory Express, NVMe SSD, NVMe-oF, NVMe-over-Fabrics, NVMe-over-RDMA]
last_updated: 2026-08-14
tags: [storage, ssd, kernel, virtualization, disaggregation]
---

# NVMe

> Non-Volatile Memory Express（NVMe）是面向高速非易失存储的主机控制器与命令协议；它用大量 submission/completion queue 暴露并行性，也把软件路径、完成通知、虚拟化和故障处理推到性能关键路径。

## 核心思想

NVMe host 把 command 写入 submission queue（SQ），更新 doorbell 通知 controller；controller 取 command、DMA 数据，完成后写 completion queue（CQ），再由 polling 或 interrupt 通知软件。一个 controller 可有多组 queue pair，每组能容纳许多未完成请求，因此不同 CPU core、VM 或 application 可以少共享锁地并行提交。

协议只定义命令、queue、namespace 与状态语义，并不自动提供高性能文件系统。一次 4 KB I/O 仍可能经过 syscall、VFS、page cache、block layer、IOMMU/DMA mapping、driver、scheduler wake-up 与虚拟化边界。设备达到微秒延迟和百万 IOPS 后，这些软件常数、cache-line contention 与 context switch 可能比 NAND 访问更先成为瓶颈。

不同软件栈利用 NVMe 的方式不同。Linux block layer 提供通用权限、调度、文件系统和故障处理；[[io_uring]] 减少提交/完成开销但仍使用内核；[[SPDK]] 把 driver 与 polling 放到用户态，绕开内核关键路径；GPU-initiated I/O 甚至让 GPU 写 SQ。路径越短，应用越需要自行承担 queue ownership、CPU polling、buffer registration、空间管理、crash recovery 和 device failure。

NVMe over Fabrics（NVMe-oF）把同一命令模型延伸到 RDMA/TCP 等网络 transport。它让远端 SSD 看起来像 block device，却加入 network RTT、remote CPU/NIC、distributed lock 与更大的 failure domain。把 local NVMe 的软件结论直接套到 NVMe-oF，通常会低估网络与共享 target 的成本。

## 为什么重要

NVMe 让系统瓶颈从介质向 host 栈移动。[[DeLFS-OSDI26]] 的裸设备能随核心扩到约 5.24 GB/s，原 F2FS 路径却停在约 1.06 GB/s；[[WSBuffer-FAST26]] 发现 PCIe 5.0 NVMe 下，page-cache write management 与 `xa_lock` 足以让 direct I/O 更快；[[RISTRETTO-FAST26]] 则展示 VM exit、syscall 与 interrupt 如何让 virtual disk 只达到 physical NVMe 的一小部分 IOPS。

完成机制成为独立设计问题。纯 polling 延迟低，却持续占 CPU 或 GPU；interrupt 省执行资源，却有 interrupt delivery、sleep/wakeup 和 cache pollution。[[Aeolia-SOSP25]]、[[DPAS-FAST26]]、[[UnICom-FAST26]] 与 [[CoPilotIO-OSDI26]] 都没有找到一个对所有 load 普适的固定答案，而是重新放置通知、改 scheduler 或做 hybrid control。

NVMe 也是异构数据路径的交汇点。[[Helmsman-OSDI26]] 用 SPDK 批量读取多块本地 SSD；CoPilotIO 让 GPU 提交、CPU 回收 completion；[[RosenBridge-FAST26]] 跨 VM 暴露 express path；[[CetoFS-FAST26]] 则把 NVMe-over-RDMA 中的权限、锁和 logging 与 storage target 协作。共同问题不是“盘够不够快”，而是谁拥有 queue、谁轮询、数据和控制经过哪些 trust/virtualization boundary。

## 关键观察 / 隐含假设

- **Queue 多不等于软件自动可扩展。** [[DeLFS-OSDI26]] 移除一层瓶颈后，per-inode writeback、curseg、bio、SIT/NAT 与 discard 管理会依次变热；硬件并行度必须逐层传到应用。
- **completion policy 没有普适最优。** [[DPAS-FAST26]]、[[Aeolia-SOSP25]] 和 [[UnICom-FAST26]] 都在 polling 的低延迟与 interrupt 的 CPU efficiency 间重做折中；最优点随 IOPS、CPU contention 和 SLO 变化。
- **轮询放在哪个处理器上同样重要。** [[CoPilotIO-OSDI26]] 将 CQ 放在 CPU memory、让 CPU poller 唤醒 GPU；在所测四盘配置中用 24 个而不是 72 个以上 SM 饱和约 25 GB/s，但需要 dedicated CPU cores，且只验证单 GPU。
- **批量、无依赖 I/O 更能利用 SSD array。** [[Helmsman-OSDI26]] 的 cluster list 可一次提交给 12 块盘，图搜索的逐跳读取却难以吃满带宽；这是大 top-k、本地多盘和 90% recall regime 的结论。
- **高带宽不能修复错误的访问粒度。** [[Umap-OSDI26]] 说明分布式文件系统上的 4 KB mmap fault 无法利用大块传输；它合并远端 fault，同时明确 latency-critical、少于 4 KB 的随机 I/O 仍应留给 local NVMe mmap。
- **bypass 把责任移给 application。** Helmsman 的裸设备布局减少最多 58% 的内核路径开销，却必须自行处理 allocator、校验、掉盘、原子发布和恢复；论文对正常路径的证据强于故障路径。
- **虚拟化固定开销随设备变快而放大。** [[RISTRETTO-FAST26]] 和 [[RosenBridge-FAST26]] 都把 VM exit、eventfd/interrupt 与 host copy 视为关键成本；硬件 passthrough 又会收窄可迁移性和可观测性。
- **host hint 不是设备保证。** [[WARP-FAST26]] 中 FDP 允许 host 用 RUH 表达生命周期，但 GC 仍由 firmware 管理；错误分类会显著增加 WAF。
- **协议支持不代表 end-to-end integrity 已接通。** [[FS-PI-FAST26]] 指出 NVMe PI 的合法布局与 Linux block-integrity 假设不一致，硬件能力存在但 filesystem/application 闭环仍可能缺失。
- **远端 NVMe 会放大文件系统锁。** [[CetoFS-FAST26]]、[[Lockify-FAST26]] 表明 NVMe-oF 不是只多一段 RTT；inode/分布式锁和 host–target responsibility 会把 network latency 放进串行路径。

## 设计空间与取舍

- **Kernel stack / userspace bypass**：内核提供通用性、隔离、page cache 与成熟故障处理；SPDK 降低 crossing 和锁，却通常要独占 queue/core/device，并重做资源管理。
- **Polling / interrupt / hybrid**：polling 适合高负载和极低 latency，代价是 CPU/GPU 与能耗；interrupt 适合低负载，代价是 wake-up；hybrid 要选择阈值、hysteresis，并处理 burst 误判。
- **Per-core queue / shared queue**：per-core ownership 减少锁和 cache bouncing；shared queue 更易平衡负载，却可能形成 hot lock 与 completion owner 问题。
- **Small random / coalesced large I/O**：小请求减少 overfetch、适合 demand access；合并提高 bandwidth efficiency，却增加等待、额外数据与放大后的失败范围。
- **Buffered I/O / direct I/O**：page cache 透明吸收读写并服务 legacy API；高速盘下，其 metadata 与 writeback 可能主导。direct I/O 更直接，但要求 alignment、lifetime 和 application cache policy。
- **Local NVMe / NVMe-oF**：本地盘延迟与 failure domain 小，但容量绑定节点；远端池化提高利用率和弹性，却需要 network QoS、distributed coordination 与 target recovery。
- **Passthrough / emulation / mediated device**：passthrough 接近物理性能；emulation 易迁移但 crossing 多；DPU/mediated path 可 offload policy，却受硬件迭代和 feature compatibility 限制。
- **Block compatibility / zoned or placement hint**：普通 block interface 最兼容；ZNS 把回收责任交 host；FDP 保留 block API 并提供 best-effort hint，控制力与部署成本居中。

## 引用本概念的论文

### Queue、完成与异构 I/O

- [[CoPilotIO-OSDI26]] — GPU 提交 NVMe command，CPU 用户态轮询 CQ，并在 CPU 跟不上时恢复 GPU co-polling。
- [[Aeolia-SOSP25]] — 用 user interrupt 直接把完成投递到用户态，并与 `sched_ext` 协同，区分 interrupt 本身与错误 sleep policy 的成本。
- [[DPAS-FAST26]] — 在 interrupt 与 polling 之间设计更准确、低开销的 SSD completion 路径。
- [[UnICom-FAST26]] — 面向 NVMe/CXL-SSD 的通用 completion 机制，处理 polling 与 interrupt 的固定二选一问题。
- [[RosenBridge-FAST26]] — 跨虚拟化边界支持 XRP/GDS 等 express I/O path。
- [[Sepia-OSDI26]] — 用 NVMe-over-TCP SPDK 作为 DDIO/page-coloring 应用之一；NULL block device 的结果不能代表真实 SSD media。

### 文件系统、内核与虚拟化路径

- [[DeLFS-OSDI26]] — 从 128 核日志结构文件系统中逐层移除集中 ownership，让写和 GC 接近裸 NVMe 扩展。
- [[Oxbow-OSDI26]] — 在 kernel、userspace 与 computational storage components 间协作，避免全内核路径或全设备端的单边缺陷。
- [[WSBuffer-FAST26]] — 为高带宽 SSD 重构 buffered write path，以 scrap buffer、直送大写和并发 metadata 减少 page-cache 开销。
- [[RISTRETTO-FAST26]] — 展示 cloud local NVMe 从 kernel、SPDK 到 ASIC+SoC DPU 的演进及硬件迭代成本。
- [[ScaleSwap-FAST26]] — 为 128 核、8 NVMe 的全闪存 swap array 重做 core-to-resource ownership。
- [[Xkernel-OSDI26]] — 同一 block request 常量在 HDD 与 NVMe 上最优方向相反，说明已部署 kernel knob 需要安全调节。
- [[FS-PI-FAST26]] — 修补 application/filesystem/block/NVMe PI 的 end-to-end integrity gap。
- [[Timelock-Drive-OSDI26]] — 讨论真实 NVMe controller 集成仍未包含在小于 1% 的 host-side prototype overhead 中。

### Bypass、存储布局与设备语义

- [[Helmsman-OSDI26]] — 用 SPDK 直接管理 12 块裸 NVMe，批量读取固定 cluster list；故障恢复证据弱于性能证据。
- [[WARP-FAST26]] — 刻画 NVMe FDP 的 RUH placement、device GC 与 WAF。
- [[PolarStore-FAST26]] — 以标准 NVMe 接口暴露可压缩 CSD，结合变长 physical layout 与扩展 FTL。
- [[Espresso-OSDI26]] — 修改 NVMe driver，把 borrower command 重定向到 lender SSD processor；真实 CXL 盘间路径仍以仿真为主。
- [[CetoFS-FAST26]] — 在 NVMe-over-RDMA 上将 permission、lock 和 redo logging 与可信 target 协作。
- [[Lockify-FAST26]] — 说明 NVMe-over-Fabrics shared-disk 文件系统即使低争用也会有分布式锁管理成本。
- [[Sandman-SOSP25]] — 在 SPDK/NVMe 栈中联合性能与设备 power management。

### 作为容量层、测试设备或适用边界

- [[Umap-OSDI26]] — 聚合 DFS mmap fault；少于 4 KB 的 latency-critical random access 仍建议 local NVMe。
- [[Spice-OSDI26]] — 在单机高端 PCIe 5.0 NVMe、冷 page cache 上恢复 serverless snapshot；控制面和普通云盘未覆盖。
- [[Strata-OSDI26]] — 将 NVMe 作为长上下文 KV cache 的更低层，主结论仍主要来自 GPU/host cache 路径。
- [[Seer-OSDI26]] — RL rollout chunk mobility 依赖跨节点 DRAM、NVMe 与 RDMA 的 cache infrastructure。
- [[M3U-OSDI26]] — device-aware post-copy 只完整验证特定 DPU/VirtIO stack，不能据此覆盖所有 NVMe passthrough device。
- [[Osprey-OSDI26]] — 用本地 NVMe 作为超出 32 GB 内存的 secure-computation backing device，属于实验平台条件。
- [[Incr-OSDI26]] — NVMe 是程序重执行 benchmark 的本地存储环境，不是论文核心机制。
- [[hS-OSDI26]] — shell 推测执行在 NVMe 机器上评测，结果不能分离设备贡献。
- [[uCache-FAST26]] — 以高带宽 NVMe 暴露 kernel page cache/VMA 的扩展问题。

## 已知局限 / 开放问题

- 需要跨 kernel、userspace runtime、DPU、GPU 与 device firmware 的 queue ownership、QoS 和错误传播协议；今天的快路径往往只优化成功请求。
- 多 tenant、多 SSD、多 GPU 共享 PCIe switch/root complex 时，device 内 queue priority 不能独自保证端到端带宽与尾延迟隔离。
- polling policy 应联合 CPU/GPU resource、能耗、IOPS、SLO 与共置服务成本，而不是只最大化设备吞吐。
- bypass storage 的 checksum、bad block、atomic publish、process crash、掉盘与升级回滚需要和正常路径同等强度的评测。
- NVMe-oF 与 memory-semantic fabric 共存后，block cache、remote memory cache 与 application cache 的一致性、故障和权限边界仍未统一。
- FDP/ZNS/FTL 的 host–device 生命周期协作缺少可观测反馈；host 很难确认 hint 是否真正降低 WAF，或只是把回收推迟到未来。
