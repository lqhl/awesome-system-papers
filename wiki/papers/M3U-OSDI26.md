---
type: paper
name: M3U
full_title: "M3U: Scalable Kernel Memory Management for Efficient Post-copy Live Migration of High-end Virtual Machines"
authors: [Yizhe Xu, Yuan Tao, Zhibin Zhang, Kang Yan, Chao Zhang, Shuo Shi, Zongpu Zhang, Xu Huan, Yibin Shen, Xudong Zheng, Jiesheng Wu, Jian Li, Haibing Guan]
venue: OSDI
year: 2026
tags: [virtualization, live-migration, memory-management, post-copy, cloud]
source_pdf: "[[osdi26-xu-yizhe.pdf]]"
source_md: "[[osdi26-xu-yizhe]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 高端虚拟机 Post-copy 迁移的可扩展内核内存管理（OSDI 2026）

> **原题**：M3U: Scalable Kernel Memory Management for Efficient Post-copy Live Migration of High-end Virtual Machines

> **一句话总结**：M3U 发现高端 VM 的 post-copy 不是先受网络极限限制，而是被 HPT/EPT/IOPT 更新中的过度锁保护串行化；它以静态物理内存、page flagging、分离的 userfault pipeline 和设备状态预安装减少锁与 I/O fault，在默认 64-vCPU/256-GB VM、100-Gbps 迁移带宽的双机实验中相对 baseline 最多降低 47.0% downtime、85.8%–89.6% post-copy completion time，并把 Redis/Memcached 吞吐损失改善 2.6–4.1 倍。

## 问题与动机

论文把“高端 VM”定义为至少 64 vCPU、256 GB memory，并可配到 100 Gbps network 与 600K IOPS。传统 pre-copy 在 VM 继续写内存时反复传 dirty page；一旦 dirty rate 高于传输速度就不能收敛。作者分析 Alibaba Cloud 12 个月、超过 50,000 次高端 VM pre-copy 样本，成功率只有 81%，并把失败根因归为不收敛。这里的生产数据证明了问题真实，但并不是 M3U 的线上 A/B 评测。

Post-copy 先暂停源 VM，把 CPU/device state 和 dirty-page 标记移到目标，再在目标恢复执行；缺页由 demand paging 紧急拉取，其余页由 active pushing 后台传输。它保证 dirty set 不再增长，所以能收敛，却引入三个用户可见指标：切换 downtime、post-copy completion time（PCT）和恢复期间的 guest 性能下降。

高端 VM 放大了 kernel MMU 的串行成本。128-GB working set 最多产生 3,200 万次 4-KB unmap，dirty-page registration 占总 downtime 的 57%–66%；page-in 要在锁内分配物理页、复制内容，并原子维护 HPT、EPT 和 IOPT，实测 demand pushing 加 active pushing 只利用 9.2% 物理网络带宽。Demand fault 希望 4 KB 以减小单次等待，background push 又希望 2 MB 以减少控制开销，统一 page size 让两者不能各自最优（图 2–5、§2.2）。

Pass-through device 还会在 DMA 访问缺失页时触发硬件 I/O page fault（IOPF）。一次 IOPF 要多走 [[PCIe|PCIe]] transaction 和 host interrupt，平均 demand-paging latency 约为 vCPU fault 的 2 倍、最大 3.21 倍，并会堵住设备 queue。作者观察到绝大多数 IOPF 都集中在恢复后的最初几秒，主要访问固定、循环复用的 VirtIO descriptor，而新 I/O buffer 通常先被 CPU 触碰并通过普通 page fault 拉回（§2.3）。

## 关键观察 / 隐含假设

- **观察 1：post-copy 中很多 map/unmap 锁保护对应的物理分配、释放和逐次 TLB shootdown 并非必要。** 切换期 VM 已暂停，目标物理页也可预先保留，因此只改 Present/Writable bit 就能标记 missing page（图 7–8）。
  - **依赖假设**：迁移期间 VM memory 全驻留、目标不 swap 这些页，且 VM switching 时 vCPU 完全停止。
  - **可能失效场景**：目标 memory overcommit、ballooning、hotplug 或和迁移并发的 host reclaim 会破坏“物理位置静态”的前提。
- **观察 2：data copy 与 page-table consistency 不必由每个 userfault handler 在同一个锁区完成。** 另建 PVA 后，多条 pushing stream 可并行写已分配物理页，再由单独线程异步批量更新三套 page table（图 9）。
  - **依赖假设**：bitmap 能保证每页只传、只恢复一次，guest 在 Present bit 恢复前无法读取未完成内容。
  - **证据强度**：强。单 stream 也比 baseline 快 1.6–2.1 倍，6 stream 则快 7.6–8.3 倍，说明解耦和并行各有贡献（图 14）。
- **观察 3：active pushing 与 demand paging 应使用不同粒度。** Demand path 只拉 4 KB；当一个 2-MB 区域的 512 个 4-KB page 全部到达时，background path 再合为一个 2-MB HPT entry（§4.2.2）。
  - **依赖假设**：2-MB 区域最终能聚齐，atomic bitmap check 和 HPT coalescing 不会和 concurrent fault 发生遗漏。
- **观察 4：device state 很小且位置可识别，批量预传比处理 IOPF 更便宜。** 所测 VirtIO virtqueue footprint 最大约 671 MB，在 100-Gbps downtime link 上传输不超过约 300 ms（图 10）。
  - **可能失效场景**：不同 device/driver 的 descriptor 不透明、state 更大或不能 drain 时，自动识别与一次性 pre-install 不一定成立。
- **假设 1：post-copy 的双机故障风险由外部 checkpoint/restore 方案处理。** M3U 自身不实现 failure tolerance。
  - **证据强度**：弱。论文只在 discussion 引用可组合方案，没有故障注入或恢复实验。

## 核心方法

M3U 是插在 VMM 与原 kernel MMU 之间的 migration-specific MMU module。它通过标准 MMU abstraction 管理 VM memory，自行实现 page fault 与 page-table update，同时让 HPT/EPT/IOPT 的物理映射在整个 post-copy 期间尽量不变。三个模块分别处理 dirty registration、page transfer 和 pass-through device state（图 6）。

第一部分是并行 dirty-page registration。M3U 把已有 2-MB HPT entry 拆成 512 个 4-KB entry，清除 Present bit，并用 HVA dirty bitmap 记录缺失页，而不是 unmap 并释放物理页。因为切换期 VM 不执行，它删去不需要的 EPT invalidation callback，并把每次 unmap 的 TLB flush 合并成最后一次。HVA address space 再按互不重叠的 1-GB region 分区，由 worker pool 并行 flag；不同 region 使用独立 PUD/PMD lock，避免线程互相争用。实现默认每 8 GB guest memory 配一个 worker、最多 16 个（§4.1、§5）。

第二部分是解耦 userfault pipeline。M3U 给同一批静态物理内存建立额外 post-copy virtual address（PVA），active pushing 通过 PVA 直接 copy，省去原 QEMU 的 userspace→kernel 中间 copy。多个 QEMU `multifd` socket 并行传数据，一个专用 page-table thread 根据 bitmap 异步恢复 HPT/EPT/IOPT consistency。Demand paging 则独占一条上限 20 Gbps 的 stream，不会排在 background push 后面；它以 4 KB 恢复 faulted page，active pushing 用 2 MB 聚合 table update。实现通常给 pushing 配 6–8 条 stream（§4.2、§5）。

第三部分是 device-state pre-installation。VM/device 在源端暂停和 drain 后，M3U 从 VirtIO backend 找到 vring、descriptor table 以及 pending/in-flight buffer，把所有 dirty virtqueue state 在 downtime 内一次传到目标并重建。这样恢复后的 DMA 大多不会触碰 missing descriptor page；新 buffer 因通常先由 guest CPU 初始化，仍走较便宜的 vCPU fault。这个机制对 guest 透明，但依赖 VMM/driver 能解释设备数据结构（§4.3）。

并发正确性由两层约束维持：源端切换期暂停 vCPU、drain device；恢复后 non-present page 对 guest 不可访问。Demand 与 push 可能同时处理同一页，源 dirty bitmap 保证只发送一次，目标 received bitmap 保证 data/mapping 只恢复一次。Prototype 基于 QEMU 8.2 和 AliOS/Linux 4.19，约有 2,000 行 userspace 与 4,000 行 kernel code；作者另验证了 4.19、5.15、6.6 的接口兼容性（§4.4–§5）。

## 设计取舍

- **保留物理内存换低锁开销**：不再反复 alloc/free/unmap，注册与 page-in 更快；代价是迁移期间必须让全部 VM memory resident，目标 host 禁止 swap migrated page。
- **单 page-table updater 换 data-copy 并行**：把锁竞争移出多个 stream，但 consistency update 仍可能成为更高带宽或更多 stream 下的新瓶颈。
- **4-KB demand + 2-MB push 换两种目标兼顾**：减少 fault overfetch 和 table operation；代价是 bitmap、split/coalesce 与两条 address space 的复杂 race surface。
- **预传 device state 换少 IOPF**：最多减少 98.5% IOPF，却额外增加 94–304 ms device migration，已占总 downtime 的 12.7%–29.0%（图 17）。
- **guest transparency 换无法消灭最后 IOPF**：剩余 fault 来自 guest VirtIO frontend 分配 buffer 到发布 descriptor 之间的非原子窗口；彻底消除需要修改 guest，论文选择不做。
- **边界条件**：大内存、高 dirty rate、100-Gbps 级迁移和 VirtIO pass-through 最匹配；小 VM、低 dirty rate 或 memory 紧张的 target 可能不值得承担复杂度。

## 实验与结果

- **平台与 baseline**：source/target 各为 dual-socket Intel Xeon 8369B、512 GB DDR4，并配 PCIe Gen3×8 DPU；默认 guest 为 64 vCPU、256 GB、100-Gbps pass-through vNIC，vCPU 固定在单个 [[NUMA|NUMA]] socket 的 hyperthread。Host 用 2-MB huge page、关闭 THP；迁移可用 100 Gbps。Baseline 是 QEMU 8.2/Linux 4.19 加同一 DPU IOPF 方案；TDP MMU 因与 DPU stack 不兼容，另在 Linux 5.15、无 DPU 的同型 bare metal 上，只比较 paging efficiency 与 PCT。实验只做一轮 hybrid pre-copy，以突出 post-copy 差异（§6.1）。
- **注册与 page transfer**：M3U 把 dirty-page registration time 降低 60.0%–90.2%，16 worker 后收益饱和。相对 4-KB baseline，一条 pushing stream 的 paging efficiency 提高 1.6–2.1 倍，6 stream 提高 7.6–8.3 倍并达到约 80 Gbps；在 Liblinear、Graph500、Llama.cpp 下，6 stream 仍最优，相对 TDP MMU 在 4-KB/2-MB 设置分别快 3.9–4.5/2.6–3.6 倍（图 12–15、§6.2）。
- **迁移指标**：随 guest working set 从 2 GB 增到 128 GB，M3U 相对 baseline 最多降低 47.0% downtime；dirty registration 占 downtime 的比例从 40.2%–64.4% 降到 6.1%–15.4%。PCT 相对 baseline 降低 85.8%–89.6%；即使只有一条 stream，也降低 33.4%–55.6%（图 17–18、§6.3）。
- **guest 服务**：YCSB on Memcached 的 READ/UPDATE/INSERT/RMW latency 相对 2-MB baseline 低 1.8–4.9 倍，相对 4-KB baseline 低 8.3–14.5 倍。Redis/Memcached SET 的 post-copy throughput valley 表明，M3U 把吞吐损失改善 2.6–4.1 倍（图 19–20）。
- **IOPF**：Memcached I/O stress 与 8-vCPU/32-GB 到 64-vCPU/256-GB 配置中，device pre-install 后每次 migration 只剩 0.2–3.8 个 IOPF，相对 baseline 最多减少 98.5%。未 pre-install 的 M3U 也因 page-in 更快而比 baseline fault 少；所以该结果不能全部归因于 device-state module（图 16、§6.2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 过度锁保护是高端 post-copy 的主要瓶颈 | 图 2–5、图 12–15 | x86/QEMU-KVM；最高 64 vCPU、256 GB；100-Gbps migration | 强 |
| Page flagging 与 parallel registration 能显著缩短切换 | 图 12、图 17 | random-write dirty workload；2–128 GB working set | 强 |
| 分离 address space 与 mixed page size 能接近网络上限 | 图 14–15、图 18 | 单对节点；1–10 pushing stream；4-KB/2-MB page | 强 |
| Device pre-install 能基本消除所测 VirtIO IOPF | 图 10、图 16 | DPU VirtIO backend；网络/存储/内存 workload | 中 |
| M3U 改善 guest 可见性能 | 图 19–20 | YCSB/Memtier；Redis、Memcached；SET 和四类操作 | 强 |

## 批判性分析

### 论证链条

论文用 downtime breakdown、network utilization 和 IOPF 时间分布把三个症状分别映射到 HPT 锁、cross-table consistency 和 device descriptor，再由三个设计逐一处理；microbenchmark、端到端 migration 和 guest workload 形成了完整证据链。需要收窄的是“fully generalizable”结论：无 device 部分依赖标准接口，确实有可迁移性；device-state parsing 只在作者的 DPU/VirtIO stack 上做了端到端验证，尚不足以证明各种 NIC、[[NVMe|NVMe]]、GPU passthrough 都可直接适用。

### 假设压力测试

M3U 最强的假设是 migration 期间 memory 全驻留且物理位置不变。论文说明 overcommit 在迁移前会 swap-in，目标也禁止 swap，等于把 memory pressure 移到 admission 和迁移前阶段；当 target 容量紧张时，迁移可能推迟或影响其他 VM。6-stream 最优点依赖 100-Gbps bandwidth、CPU 和 DPU，换成更慢网络、[[RDMA]]、[[CXL]] 或更强 NIC 后，单个 table updater 与 memory bandwidth 可能成为瓶颈。Device pre-install 还假设 driver state 可识别、drain 后稳定。

### 实验可信度

硬件 post-copy、真实 QEMU/KVM、64-vCPU/256-GB VM、compute/memory/network/storage workload 与 guest-level latency/throughput使结果有说服力。但只有一对 Intel/DPU 节点；生产 50,000 样本只证明 pre-copy 问题，不验证 M3U 效果。实验固定只做一轮 pre-copy，会保留更多 dirty page，适合压力测试 post-copy 机制，却不代表每个生产 policy。TDP MMU 因软件/硬件不兼容在不同 kernel 且无 DPU 环境中测试，也不能用于 downtime、I/O 或 guest 端到端公平比较。论文没有做逐组件 end-to-end ablation，把 PVA、mixed page、multi-stream 各自对 PCT 的贡献完全拆开。

### 系统性缺陷

约 4K 行 kernel code 改写 page fault/table-management 路径，错误可能造成 silent memory corruption 或隔离漏洞；论文以 bitmap 与阶段不变量论证 safety，但没有 model checking、race detector、stress/fault injection 或 crash-consistency 实验。Post-copy 本身把 VM state 分散在两台 host，任一主机失败都可能使 VM 不可恢复；M3U 只引用可组合 checkpoint/restore，没有实现。Residual downtime 仍含 0.2–1.4 秒 CPU-state migration，device pre-install 也会占近三成 downtime。监控、rollback、在线判断何时不用 M3U，以及升级不同 kernel/device driver 的维护成本均未讨论。

## 局限与后续工作

- **局限 1**：实测局限于一对 x86 server、DPU VirtIO pass-through 与 QEMU-KVM；跨 vendor/device 的泛化仍是设计推断。
- **局限 2**：迁移期间不允许 memory overcommit/swap，需要 target 预留全部 VM memory。
- **局限 3**：M3U 不提供 post-copy failure tolerance，也未验证 source/target crash、packet loss 或 page-table update 中断后的恢复。
- **后续工作 1**：对 HPT/EPT/IOPT 并发状态机做 model checking，并注入 demand/push 同页、CPU/device race、host crash 和 bitmap corruption。
- **后续工作 2**：在 Intel/AMD、不同 NIC/NVMe/GPU passthrough 与 25/100/200-Gbps、RDMA 链路上重测最优 worker/stream 数和 IOPF 覆盖率。
- **后续工作 3**：把 pre-copy round、dirty rate、available memory、network congestion 和 SLO 纳入 policy，客观选择 pre-copy、hybrid 或 M3U post-copy。
- **后续工作 4**：集成 checkpoint-based failure tolerance，报告额外 bandwidth/storage、downtime、PCT 和双机故障恢复率。

## 相关

- **相关概念**：[[Live-Migration]]、[[Post-Copy]]、[[Virtual-Memory]]、[[IOMMU]]、[[Huge-Pages]]
- **相关系统**：[[QEMU]]、[[KVM]]、[[VirtIO]]、[[TDP-MMU]]
- **相关硬件**：[[DPU]]、[[RDMA]]、[[CXL]]
- **同会议**：[[OSDI-2026]]
