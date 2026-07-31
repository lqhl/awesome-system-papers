---
type: concept
aliases: [f2fs, Flash-Friendly File System, flash-friendly file system, Flash Friendly File System]
last_updated: 2026-07-30
tags: [filesystem, flash, mobile, log-structured, zoned-storage]
---

# F2FS

> Flash-Friendly File System（F2FS）是 Samsung 为 NAND/闪存设计的 log-structured 文件系统，以 out-of-place 更新、温度分离（hot/warm/cold）与 segment 级 [[Garbage-Collection]] 适配闪存写放大特性；作为 Android 默认根文件系统，它在 mobile、ZNS/ZUFS 与云备份等场景中是「闪存友好 FS」的基准实现与改造载体。

## 核心思想

F2FS 把用户数据与元数据组织为 **segment**（通常 2MB），以 append-only 方式写入，后台 GC 回收无效 segment。核心 on-disk 结构包括 **NAT**（inode→block 映射）、**SIT**（segment 使用情况）、**SSA**（segment summary）与 **checkpoint**，形成典型的日志结构文件系统（Log-Structured File System）布局。

为降低写放大，F2FS 将写入分为六路日志流（data/node × hot/warm/cold），并维护多个 **open zone/section**，使顺序写与闪存擦除块对齐。Recovery 传统上依赖 **周期性 checkpoint**（默认 60s）：触发时阻塞 I/O，crash 间隔内最多丢失约 **9.1%** 数据（[[F2FSJ-OSDI25]]）。这与 EXT4/JBD2 的 journaling 语义不同——out-of-place 更新使 inode 物理位置漂移，经典 ordered journaling 不能直接套用。

F2FS 的设计边界在近年被三类新约束持续挤压：(1) **ZNS/ZUFS** 禁止 zone 内随机写，要求 host 承担 GC 与 active zone 管理（[[Z-LFS-ATC25]]、[[ZUFS-FAST26]]）；(2) **mobile 真实负载** 下长期碎片化普遍，telemetry 显示约 **30%** 设备 fragmentation level > 0.7（[[ZUFS-FAST26]]）；(3) **跨层协同**（备份、GPU 存储、解聚 NVMe-oF）要求在不破坏 on-disk layout 的前提下外挂新语义（[[SolFS-ATC25]]、[[GoFS-SOSP25]]、[[CetoFS-FAST26]]）。

OSDI 2026 的 [[DeLFS-OSDI26]] 又揭示第四类边界：当 page-cache 节流被解除、设备足够快且核心数上升时，固定日志头、SIT/NAT、bio 与 segment 管理的集中式所有权会形成级联锁瓶颈。也就是说，“面向闪存”并不自动意味着“面向 manycore”。

## 为什么重要

F2FS 是 **闪存 + 移动平台** 的事实标准栈：Android framework → F2FS → block layer → UFS/NVMe 驱动 → device firmware 全链路优化的锚点。论文反复回到 F2FS，原因包括：

1. **可改造性**：开源、部署广泛，适合叠加 journaling（[[F2FSJ-OSDI25]]）、operation-log versioning（[[SolFS-ATC25]]）、zoned sysfs knob（[[ZUFS-FAST26]]）而不必从零写 FS。
2. **LFS 语义与新型介质对齐**：ZUFS/ZNS 的 zone 顺序写与 F2FS 的 log-structured 设计「天然同向」，但默认 6 open zone、metadata 原地更新、粗粒度 checkpoint 在 small-zone 设备上暴露结构性失配（[[Z-LFS-ATC25]]）。
3. **作为 baseline 的压力测试**：高带宽 NVMe buffered I/O（[[WSBuffer-FAST26]]）、NVMe FDP placement hint（[[WARP-FAST26]]）、解聚远程 FS（[[CetoFS-FAST26]]）均拿 F2FS 与 EXT4/XFS 对比，使其成为「传统闪存 FS 是否跟得上硬件」的标尺。
4. **移动体验直接相关**：碎片化导致 foreground GC、写延迟 P99 达 **678 ms/MB**（[[ZUFS-FAST26]]），相册 jank、游戏加载等 UX 指标与 F2FS GC 行为绑定。

## 关键观察 / 隐含假设

- **观察 1：F2FS 粗粒度 checkpoint 在 mobile 上带来可感知的阻塞与粗 crash recovery。** [[F2FSJ-OSDI25]] 测得最坏 checkpoint 延迟 **293 ms**；默认 60s 间隔下 crash 最多丢 **9.1%** 数据，fsync 不触发 checkpoint 时已刷盘数据仍可能丢。
- **观察 2：真实手机 F2FS 碎片化普遍且与存储利用率弱相关，直接恶化尾延迟。** [[ZUFS-FAST26]] 对 10,000 台设备 telemetry：fragmentation level 与 utilization 相关系数 r≈0.74，但大量低利用率设备仍高碎片化；fragmentation > 0.8 后写吞吐断崖下跌。
- **观察 3：F2FS 在 commodity small-zone ZNS 上遭遇 metadata 原地更新、active zone 利用率低、die/channel 冲突三重失配。** [[Z-LFS-ATC25]] 指出简单把 metadata 改为 zone 粒度双 zone 交替写在随机更新下性能可降 **9.32×**、写入量增 **7.8×**；六路日志流各绑一 zone 最多只用 6 个 active zone，而设备支持 384 个。
- **观察 4：CoW/reflink 式 versioning 能无 hash 区分修改，但引入碎片化与双倍存储；operation-log 是更轻量的替代。** [[SolFS-ATC25]] 在 F2FS 上只 version 操作日志、不 duplicate file data，随机更新云同步时间降 **88.8%**，I/O 性能为原生 F2FS 的 **99.2%**。
- **观察 5：F2FS 的数据 classification hint 过粗时，下游 NVMe FDP 等设备优化完全失效。** [[WARP-FAST26]] 显示 F2FS 将 99% 用户数据标为 WARM → 单 RUH，FDP 对 Fileserver/OLTP 与 NoFDP 相同（WAF ~2.3–2.5）。
- **观察 6：集中式资源所有权会在 manycore 写路径中形成连续接棒的锁瓶颈。** [[DeLFS-OSDI26]] 将元数据、日志头、I/O 提交与 GC 划成 per-core domain，在 128 核随机写下相对 F2FS 最高提升 **4.34×**；但可用空间降到 1% 时优势几乎消失。

## 设计空间与取舍

- **路线 1：checkpoint 强化（维持 OOP 语义）**：[[F2FSJ-OSDI25]] 用 per-inode 分散日志 + epoch 解耦 data/control 平面，checkpoint 时间最高降 **4.9×**；牺牲是仅 ordered journal mode，writeback/data journal 未覆盖。
- **路线 2：ZNS/ZUFS 适配（standalone 或小 zone）**：[[Z-LFS-ATC25]] 用 append-only metadata + 推测式 active zone 分配 + superzone/IG 冲突感知，最高 **33.44×** vs F2FS(+CNS)；[[ZUFS-FAST26]] 跨 Android→F2FS→UFS 全栈协同，放弃 IPU 换 strict LFS 语义。牺牲是内存缓冲（+250–380MB）、设备拓扑硬编码与运维阈值调校。
- **路线 3：上层语义扩展（不改 on-disk layout）**：[[SolFS-ATC25]] 用 extended attributes 链 versioned inode，backward compatible；牺牲是依赖 backup APP 集成 ioctl、多 APP 交错时 version 链深度管理。
- **路线 4：绕过或替换 metadata 路径**：[[GoFS-SOSP25]] 指出 GPUDirect Storage 仍依赖 host F2FS/ext4 管 metadata，control path 成瓶颈；[[CetoFS-FAST26]] 在 NVMe-oF 上内核 F2FS/Ext4 因 inode 锁与驱动栈延迟低效，转向 host-target 协同 userspace FS。
- **路线 5：写路径旁路 page cache（WSBuffer 类）**：[[WSBuffer-FAST26]] 对 EXT4/F2FS/BTRFS/XFS 统一重架构 buffered 写路径；F2FS 作为 log-structured 代表仍受 page cache 全缓冲架构限制，集成 scrap buffer 成本未充分验证。
- **路线 6：per-core 去中心化**：[[DeLFS-OSDI26]] 以 core-local segment、元数据和 bio 消除共享所有权，并把非关键远端更新延期到 checkpoint 前完成；代价是局部 victim 选择、空间倾斜、CPU affinity 和 checkpoint 协调成为新的正确性与性能变量。

## 引用本概念的论文

- [[F2FSJ-OSDI25]] — 首套 F2FS ordered journaling：per-inode 分散日志 + epoch 解耦，checkpoint 时延降 **4.9×**，recovery 粒度优于 60s checkpoint
- [[DeLFS-OSDI26]] — 从 F2FS 出发把日志结构文件系统按 core 去中心化，揭示解除 page-cache 瓶颈后的级联共享锁问题
- [[ZUFS-FAST26]] — JEDEC ZUFS 落地：F2FS 碎片化 telemetry、strict LFS + proactive GC sysfs、端到端写序修补
- [[Z-LFS-ATC25]] — small-zone ZNS 上 F2FS 结构性失配与 Z-LFS 三大策略（append-only metadata、推测式 zone 分配、冲突感知 superzone）
- [[SolFS-ATC25]] — 构建于 F2FS 的 operation-log versioning，无 hash 移动云备份，保持 **99.2%** 原生 I/O 性能
- [[WARP-FAST26]] — F2FS + Filebench 评测 NVMe FDP；粗粒度 WARM 分类使 FDP 完全无效
- [[CetoFS-FAST26]] — NVMe-oF 上内核 Ext4/F2FS baseline 延迟分解与并发串行化问题
- [[WSBuffer-FAST26]] — 高带宽 NVMe 下 F2FS 等主流 FS 的 buffered 写瓶颈与 WSBuffer 对比
- [[GoFS-SOSP25]] — GPU 文件系统仍依赖 host F2FS 管 metadata，control path 瓶颈
- [[DOGI-FAST26]] — 设备端 GC 优化原型绑定 ZenFS/RocksDB，F2FS 移植未涉及
- [[MlsDisk-FAST26]] — segment 级 greedy GC 借鉴 LFS/F2FS 设计
- [[SysSpec-FAST26]] — 以 Ext4/F2FS 级百万行内核 FS 为形式化验证边界案例

## 已知局限 / 开放问题

- **Journaling 覆盖范围**：[[F2FSJ-OSDI25]] 仅 ordered mode；writeback/data journal 与 upstream 合并成本未知
- **ZNS 外推**：[[Z-LFS-ATC25]] 绑定 Samsung PM1731A 类拓扑；large-zone ZNS 或不同 zone 映射下 superzone/IG 策略需重标定
- **ZUFS 小同步写**：strict LFS 放弃 IPU 后 SQLite/fsync 密集场景依赖 Write-Booster 等旁路，ZUFS 本身不加速
- **FDP 协同**：F2FS 温度分类粒度远粗于应用生命周期（[[WARP-FAST26]]），host hint 接口价值取决于 FS 分类质量
- **解聚场景语义**：[[CetoFS-FAST26]] 未证明改造 F2FS 本身即可解决 NVMe-oF 锁与跨网原子写，userspace 协同是另一路线
- **长期 field study 缺口**：F2FSJ、ZUFS 等缺少跨 OEM、多代设备的长期生产 telemetry 与 crash 率统计
- **manycore 退化边界**：[[DeLFS-OSDI26]] 只在单台 128-core、单 NVMe 上验证；NUMA、CPU migration、多设备 striping 与长期 free-space skew 尚未覆盖
