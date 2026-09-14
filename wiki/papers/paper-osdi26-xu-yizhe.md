---
type: paper
name: M3U
full_title: "M3U: Scalable Kernel Memory Management for Efficient Post-copy Live Migration of High-end Virtual Machines"
authors: [Yizhe Xu, Yuan Tao, Zhibin Zhang, Kang Yan, Chao Zhang, Shuo Shi, Zongpu Zhang, Xu Huan, Yibin Shen, Xudong Zheng, Jiesheng Wu, Jian Li, Haibing Guan]
venue: OSDI
year: 2026
tags: [live-migration, post-copy, virtual-machine, kernel-mmu, io-page-fault]
source_pdf: "[[osdi26-xu-yizhe.pdf]]"
source_md: "[[osdi26-xu-yizhe]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向高端虚拟机高效后复制迁移的可扩展内核内存管理（OSDI 2026）

> **原题**：M3U: Scalable Kernel Memory Management for Efficient Post-copy Live Migration of High-end Virtual Machines

> **一句话总结**：作者观察到高端虚拟机的后复制迁移被内核 MMU 中过度的锁保护拖慢，因此用静态物理内存与并行页标记缩短停机时间、用分离地址空间和混合页大小解耦主动推送与按需分页，并在 64 vCPU、256 GB VM 上将停机时间最多降低 47.0%、后复制阶段缩短 89.6%，来宾服务性能提高 4.1 倍。

## 问题与动机

高端 VM 的内存、vCPU 和 I/O 密度使传统 pre-copy 容易遇到收敛问题。作者对云平台 12 个月、超过 50,000 次高端 VM 迁移样本的分析显示，pre-copy 成功率只有 81%，主要失败原因是来宾写脏页的速度超过网络传输速度。post-copy 让 VM 先在目标机恢复运行，未传输页由缺页路径按需获取，因此可以保证最终收敛。

但 post-copy 把代价转移到了切换停机和恢复阶段。对 64 vCPU、256 GB VM 的测试中，脏页注册占总停机时间的 57–66%；128 GB 工作集的随机写负载会触发最多约 3,200 万次 unmap。恢复阶段中，按需分页和主动推送共同更新 HPT、EPT 与 IOPT，锁竞争使分页只使用了可用网络带宽的 9.2%。一个 Redis 测试还出现超过 15 秒的网络中断，而 24 GB 内存按 50 Gbps 传输的理想下界只有 3.84 秒（图 3、图 4）。

## 关键观察 / 隐含假设

- **观察 1：脏页注册的主要成本来自逐页 unmap，而非数据传输。** 在 VM 切换期间，VM 已暂停，物理内存并不需要真正释放；但现有路径仍通过受锁保护的 unmap 同时处理物理内存、HPT 和 TLB。
  - **依赖假设**：迁移期间可以保持 VM 物理内存静态分配。
  - **可能失效场景**：目标机内存紧张、迁移与内存 overcommit 交织进行，或平台要求迁移期间立即回收物理页时，静态保持会增加资源压力。
- **观察 2：主动推送和按需分页需要相反的页粒度。** 按需分页偏好 4 KB 以降低单次缺页延迟；主动推送偏好 2 MB 以减少控制面操作和提高带宽利用率（§2.2、§4.2）。
  - **依赖假设**：两条路径可以使用彼此独立的地址空间和页表更新时序。
  - **可能失效场景**：工作集高度随机、主动推送频繁覆盖即将被按需访问的页，或地址空间分离引入额外内存管理成本时，混合粒度的收益可能下降。
- **观察 3：IOPF 主要集中在迁移恢复初期的 VirtIO 描述符页。** 描述符位于固定且循环复用的 virtqueue 结构中，通常每次迁移至多触发一次；动态 I/O buffer 多数先被 CPU 访问并由普通缺页恢复（§2.3）。
  - **依赖假设**：设备状态结构小且可被 VMM 解析，设备在切换期间能够 drain 并保持一致。
  - **可能失效场景**：设备使用不同的队列语义、描述符状态无法完整导出，或 DMA buffer 在 CPU 首次访问前就被设备使用时，预安装可能覆盖不足。

## 核心方法

M3U（Migration Memory Management Unit）作为 QEMU 与原有内核 MMU 之间的模块，使用标准接口管理 VM 内存，同时自带缺页处理和页表管理逻辑。它在 post-copy 期间尽量保持 HPT、EPT、IOPT 的物理映射稳定，把锁保护从不必要的分配、释放和数据复制路径中移除。

第一，M3U 用 page flagging 替代逐页 unmap。它把 2 MB 页表拆成 512 个 4 KB 项，仅清除 Present/Writable 等权限位，并用 dirty bitmap 记录缺失页。物理页保持分配，TLB flush 从每次 unmap 延迟到注册完成后统一执行。HVA 空间按 1 GB 区域划分，worker 线程处理互不共享 PUD/PMD 锁的区域，实现脏页注册并行化。这直接回应观察 1。

第二，M3U 为主动推送建立独立的 PVA（Post-copy Virtual Address）空间。数据流线程通过 PVA 直接把远端页复制到来宾内存，再由单独的页表更新线程异步维护 HPT、EPT 和 IOPT 的一致性。多条 active-pushing 数据流负责吞吐，单独的 demand-paging 数据流（上限 20 Gbps）负责低延迟缺页，避免两者互相排队。

地址空间分离还允许混合页大小：按需分页使用 4 KB，主动推送以 2 MB 批量恢复；当 2 MB 区域内 512 个 4 KB 页都恢复后再合并页表项。这回应观察 2，也避免传统 QEMU 为等待完整 2 MB 页而使用临时缓冲区产生的中间复制。

第三，M3U 在 VM 恢复前解析并传输 dirty virtqueue 状态，包括 vring、descriptor 和关联 buffer。测试中 virtqueue 总内存最多约 671 MB，在 20 Gbps 迁移带宽下传输成本不超过 300 ms（图 10）。这回应观察 3，并把昂贵的 IOPF 处理从设备 DMA 关键路径移出。

## 设计取舍

- **静态物理内存换取低停机**：保留物理页减少分配、释放和 TLB shootdown，但迁移阶段不能依靠目标机 swap 来缓解内存压力。作者明确让迁移内存保持常驻，overcommit 只在迁移外继续生效。
- **单线程一致性更新换取数据复制并行**：多个数据流可以并行复制，跨表更新集中到一个线程，减少锁竞争；但该线程可能成为新的排队点，论文主要用批量 2 MB 合并和 6 条数据流来缓解。
- **预传设备状态换取切换开销**：设备状态预安装增加 94–304 ms，约占总停机时间的 12.7–29.0%，但避免了恢复期设备 DMA 阻塞。
- **硬件与实现绑定**：原型基于 QEMU 8.2、Alios/Linux 4.19 和 DPU VirtIO offload，虽在 4.19、5.15、6.6 上验证接口兼容性，论文没有给出不同 hypervisor、设备类型和 NUMA 拓扑下的完整成本矩阵。

## 实验与结果

- 在双路 Intel Xeon 8369B、512 GB DDR4、200 Gbps 物理网络的平台上，默认 VM 为 64 vCPU、256 GB 内存、100 Gbps passthrough vNIC；M3U 将脏页注册时间降低 60.0–90.2%（图 12）。
- active pushing 使用 6 条数据流时达到约 80 Gbps，较 4 KB baseline 的分页效率提高 7.6 倍；相对 baseline 的最佳提升为 7.6–8.3 倍（图 13、图 14）。
- 在 Liblinear、Graph500、Llama.cpp 等负载下，M3U 相比 TDP MMU 在 4 KB 页配置下快 3.9–4.5 倍，在 2 MB 配置下快 2.6–3.6 倍（图 15）。
- device state pre-installation 将 IOPF 降至每次迁移 0.2–3.8 次，相比 baseline 最多减少 98.5%（图 16）。
- M3U 最多减少 47.0% 停机时间；post-copy completion time 相比 baseline 减少 85.8–89.6%，单数据流也减少 33.4–55.6%（图 17、图 18）。
- YCSB Memcached 操作延迟相比 2 MB baseline 降低 1.8–4.9 倍，相比 4 KB baseline 降低 8.3–14.5 倍；Memtier 的 Redis/Memcached 吞吐损失降低 2.6–4.1 倍（图 19、图 20）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 内核 MMU 锁竞争是高端 post-copy 的主要瓶颈 | baseline 分页效率仅利用 9.2% 网络带宽；锁竞争分析（§2.2、图 4） | 64 vCPU、256 GB VM，QEMU/KVM 与特定 Linux/DPU 配置 | 强 |
| page flagging 能缩短切换停机 | 脏页注册时间降低 60.0–90.2%，总停机最多降低 47.0%（图 12、图 17） | 随机写、1 KB block；CPU 状态迁移仍占 0.2–1.4 s | 强 |
| PVA、混合页大小和多流推送能缩短恢复阶段 | PCT 降低 85.8–89.6%，分页效率提高 7.6–8.3 倍（图 14、图 18） | 100 Gbps 迁移带宽，6 条 active-pushing 流为最优配置 | 强 |
| 预安装 VirtIO 状态能规避大多数 IOPF | IOPF 减少最多 98.5%，剩余 0.2–3.8 次（图 16） | VirtIO passthrough；设备前端存在非原子 buffer 发布窗口 | 中 |

## 批判性分析

### 论证链条

论文的主要链条是闭合的：高端 VM 放大逐页 MMU 操作成本；静态映射与锁放松降低切换和恢复路径的同步开销；微基准与端到端服务测试呈现一致收益。TDP MMU 对照说明只放宽 EPT 锁并不足以解决 HPT、IOPT 和页粒度冲突。

但“可泛化到现有社区方案”的范围仍主要由一个 QEMU/KVM 原型支持。实验没有展示不同内存大小、不同 NUMA 放置、迁移带宽变化和更大 vCPU 数量下的完整扩展曲线，因此从单机配置外推到所有高端云 VM 需要谨慎。

### 假设压力测试

M3U 假设迁移期间物理内存可常驻。论文讨论了 overcommit，但通过“迁移前恢复被回收页、迁移期间禁止 swap”维持这一不变量；这规避了问题，未测量内存压力下的额外恢复时间和资源竞争。

active pushing 的单独一致性线程降低了数据流间锁竞争，却把更新顺序和积压管理集中到一个组件。论文报告了总体分页效率，没有给出更新队列深度、不同 fault/push 比例下的尾延迟或该线程饱和点。

IOPF 预安装依赖 VirtIO descriptor 的固定位置和可解析性。作者承认 VirtIO 前端在分配 buffer 与发布 descriptor 之间存在窗口，仍会产生少量 IOPF；若要完全消除，需要修改 guest，因而与 guest transparency 有冲突。

### 实验可信度

基线包含原生 QEMU 8.2 和 TDP MMU，工作负载覆盖 CPU、内存、网络、块 I/O 及 Redis/Memcached 服务。M3U 的核心组件也有消融线索：单流仍改善分页，多流进一步提高吞吐，2 MB 与 4 KB 页配置体现了粒度取舍。

主要限制是 TDP MMU 无法在同一 DPU passthrough 平台运行，因此其比较只覆盖分页效率和 PCT，不能公平比较停机、来宾服务和 I/O 指标。论文也没有报告迁移总字节数、目标机额外内存占用、P99 缺页延迟或故障恢复实验。

### 系统性缺陷

post-copy 的基本故障脆弱性仍然存在：源机或目标机任一侧失败都可能使 VM 无法恢复。论文建议结合 checkpoint/restore，但没有实现或评估。设备状态解析目前以 VirtIO 为主，虽然作者认为方法可扩展到其他 passthrough 设备，但缺乏跨设备实测。超过 6 条数据流后收益下降，说明网络协议栈或单线程更新路径仍可能限制更高带宽平台。

## 局限与后续工作

- **局限 1**：少量 IOPF 来自 VirtIO 前端的非原子处理窗口；完全消除需要 guest 感知迁移或 paravirtualized 协作，当前设计无法做到。
- **局限 2**：post-copy 仍缺少内建故障容错；应在 M3U 上接入 checkpoint/restore，并测量故障发生位置、恢复时间和额外存储成本。
- **局限 3**：实验集中在单一硬件代际、Linux/QEMU 组合和 100 Gbps 迁移带宽；后续应在 RDMA/CXL、更高带宽、NUMA 跨节点和内存压力场景下测量锁放松收益是否仍成立。
- **后续工作 1**：记录页表更新队列长度、P99 fault latency 和 active-pushing 线程吞吐，改变 fault/push 比例以定位单线程一致性更新的饱和点。

## 相关

- **相关概念**：[[Post-copy Live Migration]]、[[Kernel MMU]]、[[IOPF]]、[[Huge Pages]]
- **同类系统**：[[QEMU]]、[[TDP MMU]]
- **同会议**：[[OSDI-2026]]
