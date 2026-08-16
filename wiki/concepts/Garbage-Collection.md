---
type: concept
aliases: [GC, Storage-Garbage-Collection]
last_updated: 2026-08-14
tags: [storage, reclamation, compaction, write-amplification]
---

# Garbage Collection

> 垃圾收集（garbage collection，GC）是在不能或不宜立即原地覆盖数据的系统中，确认哪些状态已经失效、迁移仍有效的状态，并安全回收其占用资源的过程。

## 核心思想

“垃圾”不是一种固定的数据类型，而是系统已经能证明不会再需要的状态。托管语言中的垃圾是不可达对象；日志结构存储中的垃圾是被新版本覆盖的记录；CRDT 中可能是已经因果稳定的 tombstone；受时间锁保护的存储中，则只有锁已到期、且新映射已经安全提交的旧块才可回收。不同系统的第一步都是先建立一个**可安全回收的判定条件**。

确认失效后，GC 通常还要迁移仍然有效的数据，才能释放整个 page、segment、zone 或 log extent。它的总成本因此不只取决于垃圾量，还取决于回收单元中的有效数据比例、有效数据是否连续、设备是否支持 discard/reset，以及迁移流量是否会和前台请求争用 CPU、内存带宽和 I/O 队列。

本页同时覆盖托管运行时、存储与元数据回收，但不把它们当成同一种算法。托管 GC 的主要正确性问题是对象可达性与并发 mutation；存储 GC 更关注 crash consistency、写放大和介质寿命；协议元数据 GC 则常受因果稳定性或安全保留期约束。[[jwmalloc-OSDI26]] 的两缓冲延迟回收与 GC 有相似的容量—延迟取舍，但它是内存分配器的 range reclamation，不是 tracing collector。

## 为什么重要

GC 常被放在后台，却会直接决定前台尾延迟。[[DGC-OSDI26]] 测到受限 JVM 中 concurrent marking 会与 mutator 争 CPU；[[ZUFS-FAST26]] 的量产手机数据则显示，碎片化可迫使 [[F2FS]] 进入 foreground GC。只要后台工作在压力最高时才被迫启动，“平均开销低”就不能保证 P99 或 P99.9 稳定。

GC 也是写放大的主要来源。日志结构系统必须复制 victim 中仍有效的数据；设备内部闪存转换层（FTL）可能再做一遍搬移，使 host logical write amplification 与 device physical write amplification 相乘。[[DisCoGC-FAST26]]、[[DOGI-FAST26]] 和 [[WARP-FAST26]] 分别从 discard、生命周期放置和 NVMe FDP hint 处理这条链，但都没有让错误分类的代价消失。

最后，GC 经常处在正确性边界上。[[Acumen-OSDI26]] 只有在 tombstone 达到因果稳定后才可压平；[[Timelock-Drive-OSDI26]] 必须先把 condensed mapping log 锁住，才能释放旧 log；[[ZENO-OSDI26]] 则假设旧引用被数据库 GC/VACUUM 清除前绝不复用 FID。过早回收会造成数据泄露、悬空引用或不可恢复，过晚回收则会耗尽容量。

## 关键观察 / 隐含假设

- **GC 的关键输入是“失效证据”，不是简单的空间水位。** [[LifeLine-OSDI26]] 用对象图与 reference-field mutability 近似共同生命周期；[[DOGI-FAST26]] 用历史和模型预测 block invalidation；[[Acumen-OSDI26]] 依赖 causal stability。三者共同说明，错误的生命周期判断会分别变成额外复制、写放大或无法回收。
- **回收单元越大，元数据越少，但一次搬移越重。** [[ZUFS-FAST26]] 用大 zone 大幅缩小 L2P 表，却把回收责任上移到约 1,056 MB 的 F2FS section；极端空间压力下仍可能进入 foreground GC。
- **集中式所有权会让 GC 本身成为多核瓶颈。** [[DeLFS-OSDI26]] 不只是移除一把锁，而是把 curseg、SIT/NAT、bio、segment 与 discard 管理划入 per-core domain；代价是局部资源失衡和跨 domain 协调。
- **“并发”不等于“不干扰”。** [[DGC-OSDI26]] 中 marker 与应用并发时仍抢占同一小 CPU 配额；把 marking 池化可以错开 burst，但又引入远端内存、RDMA、预测误差和共享故障域。
- **空间连续性决定 discard 是否能替代复制。** [[DisCoGC-FAST26]] 对长连续 stale range 使用 discard，对碎片化范围仍需 compaction。设备支持 TRIM/discard 并不表示任意垃圾分布都能零复制回收。
- **host hint 只是 best-effort。** [[WARP-FAST26]] 表明 FDP 仍由 device firmware 执行 GC；hint 若错误地把不同寿命数据放在同一 reclaim unit，WAF 会明显恶化。
- **许多系统隐含“后台资源最终会空出来”。** [[DINGO-OSDI26]] 显示 after-cache HDD I/O 中有 45%–70% 来自扫描型维护任务；[[Ambulance-OSDI26]] 还把 GC stall 视为现实中的 BFT slowdown 来源。持续高负载会让 proactive 与 reactive GC 都失去理想窗口。
- **安全保留期会故意推迟回收。** [[Timelock-Drive-OSDI26]] 的 block 在 unfreeze 后仍必须等待完整 timelock；更长窗口提高抗勒索恢复机会，也同步增加 version data、log、wear 与最坏恢复成本。

## 设计空间与取舍

- **Tracing / reference counting / reachability summary**：精确 tracing 能找出不可达对象，但要扫描图并处理并发 mutation；计数或摘要更增量，却要处理 cycle、漏记与元数据开销。
- **Copy / compaction / discard / zone reset**：复制适用于通用块设备但产生写放大；compaction 恢复连续空间却抢前台带宽；discard/reset 减少 host copy，但要求垃圾范围连续，并把实际回收时机交给设备。
- **Reactive / proactive**：空间低于阈值再回收能少做无用工作，却可能触发 emergency stall；提前回收能平滑延迟，但长期占用 CPU、I/O 和能耗。[[ZUFS-FAST26]] 的 proactive GC 只证明在所测手机 workload 中减轻 foreground GC，没有证明极端写压力下永不阻塞。
- **Global / partitioned ownership**：全局 victim 选择更容易找到最优回收单元；per-core、per-zone 或 per-tenant ownership 更可扩展，但可能形成局部空间债务。[[DeLFS-OSDI26]] 选择后者以换 128 核扩展。
- **In-process / shared service**：本地 collector 故障域小、能直接访问内部状态；[[DGC-OSDI26]] 的共享 marking service 可平滑多个 runtime 的 burst，却能读取多个 heap，并在 NIC 或 coordinator 故障时造成相关尾延迟。
- **Offline oracle / heuristic / learned policy**：oracle 可刻画理论上限，启发式便宜稳定，learned model 能利用复杂生命周期特征；[[DOGI-FAST26]] 说明三者差距真实存在，也说明模型漂移与推理开销必须计入。
- **立即回收 / 延迟回收**：立即归还容量最积极，却减少与邻接空闲 range 合并的机会；[[jwmalloc-OSDI26]] 用两 epoch 缓冲等待短寿 range 一起释放，换取暂时更高 footprint。

## 引用本概念的论文

### 以 GC 为核心机制

- [[DGC-OSDI26]] — 把 Shenandoah concurrent marking 外移到共享 SHM/RDMA 服务，并用全局调度错开 GC burst；收益集中在 GC pressure 较高但应用尚未完全饱和的区间。
- [[LifeLine-OSDI26]] — 让 mature object 的生命周期与 physical page 对齐，以整页 remap 替代部分对象复制；证据来自 Pixel 7 Pro 的特定商业应用 workload。
- [[DeLFS-OSDI26]] — 把日志结构文件系统的普通写和 GC 都改为 per-core domain，解除集中元数据在众核上的串行化。
- [[DisCoGC-FAST26]] — 根据 stale range 的连续性在 discard 与 compaction 间选择，直接处理 logical/physical write amplification 叠加。
- [[DOGI-FAST26]] — 以 oracle、启发式与轻量模型联合预测数据寿命，并在 ZNS 原型上降低 GC 搬移和 WAF。
- [[ZUFS-FAST26]] — 消除 device-level GC 的同时，把大 zone 的回收压力显式上移到 F2FS，并以主动策略减轻 foreground GC。
- [[OdinANN-FAST26]] — 直接插入 on-disk graph 时，用 logical GC 处理 log-structured record 膨胀；说明动态图索引也有持续回收成本。

### GC 参与正确性或安全边界

- [[Acumen-OSDI26]] — 只有 causally stable tombstone 才能异步压平；离线或恶意成员可长期阻止回收推进。
- [[Timelock-Drive-OSDI26]] — mapping log 的 condensed copy 必须先被时间锁保护，再释放旧链；长期 retention 的容量与 wear 尚未验证。
- [[ZENO-OSDI26]] — FID 复用安全依赖旧引用已经被数据库 GC/VACUUM 清除。
- [[WriteGuards-OSDI26]] — 把 GC/runtime stall 作为旧 owner 的 delayed write 仍可能晚到存储端的现实来源。

### GC 作为工作负载或系统干扰

- [[DINGO-OSDI26]] — 将存储 GC 与 scrubbing、reconstruction 等归为大量 after-cache 扫描型维护 I/O。
- [[Ambulance-OSDI26]] — 将 GC pause 视为 BFT replica 暂时 slowdown，而非单纯 crash。
- [[Blink-OSDI26]] — 指出只采 interval 前若干次调用会漏掉 GC、warmup 与 thermal phase，GC 在这里是 profiling 边界而非该论文的回收机制。
- [[Spice-OSDI26]] — snapshot 构建前在语言安全点触发 GC，以减少运行时状态和恢复工作集。
- [[Mohabi-OSDI26]] — 将大部分 JavaScript GC 一并放入不可信引擎沙箱，GC 在这里影响隔离边界。
- [[jwmalloc-OSDI26]] — 用 delayed range reclamation 处理内存分配器的生命周期分层；与 GC 相似但不是 tracing collector。
- [[PolarStore-FAST26]] — 压缩、FTL 与数据库存储布局共同影响设备 GC 和写放大。
- [[TapeOBS-FAST26]] — 磁带归档中的回收受长寿数据、顺序介质和重写成本约束。
- [[WARP-FAST26]] — 刻画 NVMe FDP hint 如何改变 device GC 与 WAF。
- [[DShuffle-ATC25]] — 将 GC 列为 DPU shuffle runtime 的资源与暂停因素，但不是核心贡献。
- [[Z-LFS-ATC25]] — ZNS 把设备内部 GC 责任上移给 host 文件系统。

## 已知局限 / 开放问题

- 缺少跨 application、filesystem、block layer 与 device firmware 的统一生命周期接口。上层标签过粗会制造 device GC，设备内部策略不透明又让 host 难以判断 hint 是否有效。
- 多租户 GC 需要同时约束 P99/P99.9、容量、CPU、memory bandwidth、I/O、WAF、wear 与能耗；现有论文通常只优化其中两三项。
- 学习式生命周期预测遇到 workload、schema 或 embedding drift 时应如何检测失效、如何安全回退，仍缺少统一方法。
- 分区 ownership 的局部空间债务何时需要全局借用或重平衡，必须在扩展性与最坏进度之间给出可验证上界。
- 托管 GC 外移、host-assisted GC 和 device-managed GC 都扩大了共享故障域；crash、partition、stale metadata 与重复回收需要系统性 fault injection。
- 长期实验不足。许多工作只跑小时级或有限 trace，无法同时回答月级 fragmentation、wear、retention、GC debt 和恢复时间。
