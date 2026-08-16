---
type: concept
aliases: [f2fs, Flash-Friendly File System, flash-friendly file system, Flash Friendly File System]
last_updated: 2026-08-14
tags: [filesystem, flash, mobile, log-structured, zoned-storage]
---

# F2FS

> Flash-Friendly File System（F2FS）是面向 NAND 闪存的 Linux 日志结构文件系统。它主要采用异地更新、冷热数据分流和 segment 级垃圾回收，常被移动设备和闪存系统论文用作真实基线或改造对象。F2FS 在一些 Android 设备中部署广泛，但不能笼统称为所有 Android 设备的默认根文件系统。

## 核心思想

F2FS 把磁盘空间划成 segment，并把新数据和元数据顺序追加到活跃日志。旧 block 失效后，由 [[Garbage-Collection|垃圾回收]] 搬走仍有效的数据，再回收整个 segment。它还用 NAT 记录 node 的位置，用 SIT 记录 segment 状态，用 SSA 保存摘要，并通过 checkpoint 保存可恢复的一致状态。

异地更新适合不能原地覆盖的闪存，但代价不会消失：文件长期修改会产生碎片，空间不足时 GC 会搬运更多数据；多个日志头、NAT/SIT 更新、checkpoint 和 block I/O 提交也可能成为共享瓶颈。F2FS 的“flash-friendly”主要描述介质与布局，并不保证它天然适合 manycore、ZNS、远端 NVMe 或 GPU 直接 I/O。

## 为什么重要

F2FS 同时具备生产相关性和可修改的开源实现，因此适合检验新介质或新接口是否真能进入文件系统。当前 inbound 论文覆盖了五种角色：

- [[DeLFS-OSDI26]] 以 F2FS 为起点研究 manycore 去中心化。
- [[Z-LFS-ATC25]] 与 [[ZUFS-FAST26]] 检查日志结构设计和 zoned device 的真实匹配程度。
- [[SolFS-ATC25]] 在 F2FS 上加入面向移动备份的操作日志。
- [[WARP-FAST26]]、[[WSBuffer-FAST26]] 和 [[CetoFS-FAST26]] 把 F2FS 当作主流基线，暴露 placement hint、page cache 和远端软件栈问题。
- [[GoFS-SOSP25]] 复用 F2FS-compatible 格式，但把文件系统控制路径移到 GPU。

这些工作共同说明：一个成熟文件系统的磁盘格式、恢复语义和生态很有价值，但新的并行性、介质约束和跨设备路径经常要求重新划分内部所有权。

## 关键观察 / 隐含假设

- **日志结构不等于可扩展。** [[DeLFS-OSDI26]] 发现，当设备足够快、page-cache 节流不再主导时，F2FS 的日志头、SIT/NAT、bio 和 segment 管理会连续变成锁瓶颈。把这些状态分到每核 domain 后，128 核随机写最高提升 4.34 倍；但只剩 1% 空闲空间时，局部 GC 选择变差，优势几乎消失。
- **顺序写方向相同，不代表可直接运行在 ZNS 上。** [[Z-LFS-ATC25]] 指出 F2FS 仍有原地更新的元数据，而且少量固定日志流不能充分利用数百个 active zones。其结果针对特定 small-zone 设备拓扑，不能外推到所有 ZNS SSD。
- **移动设备的长期碎片会进入用户可见尾延迟。** [[ZUFS-FAST26]] 用 10,000 台设备 telemetry 说明碎片并不只在磁盘接近写满时出现，再以 strict LFS 和主动 GC 改造 Android—F2FS—UFS 路径。其结论依赖所测 OEM、设备代际和 workload 分布。
- **上层知道的数据生命周期，F2FS 默认分类未必知道。** [[WARP-FAST26]] 发现评测中的 F2FS 几乎把用户数据都标成 WARM，导致 NVMe FDP 的 placement hint 无法区分生命周期；这证明的是当前集成过粗，不是 FDP 对任何 F2FS workload 都无效。
- **记录“改了哪里”可以避免全文件 hash。** [[SolFS-ATC25]] 让 F2FS 保存写入 offset/length 和版本关系，为备份应用直接给出变化范围。性能证据来自原型和单备份应用假设，商业应用是否采用新 ioctl 仍未证明。
- **高带宽设备会把 page cache 管理变成瓶颈。** [[WSBuffer-FAST26]] 把大块对齐写直接送到底层文件系统，只缓冲小写和非对齐部分。F2FS 是比较对象之一；论文没有证明相同收益已在完整 F2FS 集成中逐项复现。
- **远端和 GPU 路径的瓶颈常在控制面。** [[CetoFS-FAST26]] 在 NVMe-oF 上绕开传统内核文件系统栈，[[GoFS-SOSP25]] 则把 F2FS-compatible 控制和数据路径搬到 GPU。它们不是对 F2FS 的小补丁，而是说明 host inode lock、驱动或 metadata path 可能需要重新放置。

## 设计空间与取舍

- **全局状态或 per-core domain**：共享状态容易保持空间全局最优；per-core 状态减少锁，却会产生空间倾斜、跨核更新和 checkpoint 协调。
- **宽松日志结构或 strict LFS**：允许部分原地更新可简化小同步写；严格顺序写更适合 zoned device，但需要更多缓冲、回收和写序控制。
- **固定冷热类别或应用语义 hint**：固定类别接口简单，容易把生命周期不同的数据混在一起；更精确的 hint 能降低写放大，也更依赖应用和文件系统共同维护语义。
- **周期 checkpoint 或细粒度日志**：checkpoint 批量恢复简单，但停顿和恢复粒度较粗；细粒度操作日志便于追踪变化，却增加元数据、版本和崩溃边界。
- **保留内核路径或移动控制面**：保留 F2FS 兼容性和成熟语义，可能留下 CPU/锁瓶颈；userspace、target-side 或 GPU-side 路径更快，但重新承担权限、并发和 crash consistency。
- **本地 GC 或设备/系统协同**：F2FS 自己选择 victim 容易部署；知道 zone、FDP RUH 或设备内部并行度的协同策略可以减少写放大，但可移植性更弱。

## 引用本概念的论文

- [[DeLFS-OSDI26]]：以 F2FS 的共享日志和元数据路径为对照，按核心拆分资源所有权。
- [[Z-LFS-ATC25]]：说明默认 F2FS 布局在 small-zone ZNS 上的三类结构性失配。
- [[ZUFS-FAST26]]：从生产设备碎片观察出发，改造移动端 F2FS 与 UFS 的跨层行为。
- [[SolFS-ATC25]]：在 F2FS 上记录文件操作和版本，减少移动云备份的全文件扫描。
- [[WARP-FAST26]]：用真实 FDP SSD 和 emulator 说明 F2FS 的粗粒度 hint 可能抹掉 FDP 收益。
- [[WSBuffer-FAST26]]：把 F2FS 列入高带宽 SSD 下传统 buffered I/O 的比较范围。
- [[CetoFS-FAST26]]：以远端 F2FS/Ext4 为内核 baseline，转向 host—target 协同文件系统。
- [[GoFS-SOSP25]]：复用 F2FS-compatible 格式，在 GPU 侧实现可扩展的直接存储路径。
- [[DOGI-FAST26]]：研究日志结构系统的数据放置与 GC；其原型基于 ZNS/ZenFS，不是 F2FS 实现。
- [[MlsDisk-FAST26]]：在可信块存储中采用分层安全日志；它借鉴日志结构和 segment GC，不是 F2FS 扩展。
- [[SysSpec-FAST26]]：把 F2FS 与 Ext4 作为大型工业文件系统的规模边界，实际生成的是较小的 FUSE 文件系统。

## 已知局限 / 开放问题

- manycore 结果需要扩展到多 socket、NUMA、CPU migration 和多 SSD；单机单盘结果不足以证明去中心化长期稳定。
- zoned、FDP 和普通闪存要求不同。不能把一种设备上的最优日志数、zone 分组或 hint 策略直接复制到另一种设备。
- 空闲空间很少时，GC 成本可能压过前台并行收益；论文应同时报告稳态写放大、尾延迟和长时间空间倾斜。
- 新的日志、ioctl 或 GPU/target-side 控制面必须重新验证 fsync、rename、断电恢复、权限和升级兼容性。
- 多数评测集中在单一原型和有限 trace。跨 OEM、跨内核版本和多年设备老化的公开 field study 仍然不足。
