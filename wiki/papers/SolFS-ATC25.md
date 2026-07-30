---
type: paper
name: SolFS
full_title: "SolFS: An Operation-Log Versioning File System for Hash-free Efficient Mobile Cloud Backup"
authors: [Riwei Pan, Yu Liang, Lei Li, Hongchao Du, Tei-Wei Kuo, Chun Jason Xue]
venue: ATC
year: 2025
tags: [filesystem, mobile, cloud-backup, versioning, delta-sync]
source_pdf: "[[atc2025-pan.pdf]]"
source_md: "[[atc2025-pan]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# SolFS：用于无哈希高效移动云备份的操作日志版本控制文件系统（ATC 2025）

> **原题**：SolFS: An Operation-Log Versioning File System for Hash-free Efficient Mobile Cloud Backup

> **一句话总结**：观察到 mobile [[Delta-Sync]] 为定位修改范围必须对整文件做 hash（Pixel 8 上额外 +170% 延迟、+224% CPU 能耗），而 mobile workload 以小 write 为主；SolFS 在 [[F2FS]] 上记录每次 write 的 (offset, length) 操作日志并做 backup-driven 版本化，让云备份 APP 无 hash 获知修改范围，随机更新场景云同步时间降 **88.8%**、client/server 计算开销降 **90%+**、真实 APP workload 同步时间 **89s→29s**。

## 问题与动机

手机已成为个人数据主存储，云备份（Dropbox、OneDrive、厂商内置）是防数据丢失的主流手段。备份流程本质是「读文件 → 上传」，但两条路径都有硬伤：

1. **整文件上传**：minor change 也传全量，移动网络下流量与耗时不可接受。
2. **[[Delta-Sync]]**：用 chunk hash（MD5/SHA256）或 [[rsync]] rolling checksum 比对差异，只传修改块；但**无论实际修改多少，都要扫描并 hash 整文件**才能定位修改范围。

作者在 Pixel 8 上复现 Dropbox 式 content hash 备份 15GB 数据：相对只读 baseline，hash 阶段平均多花 **170%** 执行时间、**224%** CPU 能耗；4 线程并行 hash 虽可略快于单线程读，但能耗仍超 baseline **2.3×**，且与前台应用争用 CPU。QuickSync、NetSync、WebR2sync+ 等 prior work 优化了 chunking 或把比对移到 server，但**客户端仍须对全文件做 weak/strong hash**——在 resource-limited mobile 上，这直接推高厂商/用户降低备份频率的动机（如一周一次），与「新编辑文档应立即备份」的需求冲突。

另一条路是用文件系统 snapshot/versioning 无 hash 区分 old/new data（[[Copy-on-Write]] reflink、BetrFS、WaybackFS）。但 CoW 在多次更新后产生**文件碎片化**，10MB 文件随机更新 1MB 后 sequential read 明显变慢；且需为多个 file data 版本持续分配存储，对手机不友好。在 [[F2FS]] 上移植这些设计还常需改 on-disk layout。

SolFS 的 claim：**不必 hash 整文件，也不必 duplicate file data**——只要文件系统知道「自上次 backup 以来每次 write 的 offset 和 length」，backup APP 就能精确上传增量。

## 关键观察 / 隐含假设

- **观察 1**：典型 delta sync（chunk-level MD5 或 rolling checksum）对**全文件**做 hash 比对，修改范围再小也无法跳过扫描；Pixel 8 实测 hash 占 backup 主要 CPU 与能耗（Figure 1）。
  - **依赖假设**：主流 backup APP 要么不做 delta（Dropbox/OneDrive/Google Drive），要么做 delta 就走全文件 hash 路径；mobile CPU 是稀缺资源且与 UX 强相关。
  - **可能失效场景**：未来 OS/芯片提供专用 hash 加速器、或 backup 完全 offload 到后台低优先级核且用户无感知；大文件 + 极低修改率时，操作日志累积与版本链遍历成本可能反超单次顺序 hash。

- **观察 2**：Mobile 设备上 **small writes 占主导**（<1MB 文件、<1MB I/O 普遍），随机写（SQLite DB 更新）多于大块顺序写；因此「只 hash/上传实际修改字节范围」的收益空间大。
  - **依赖假设**：backup 场景下修改范围远小于文件总大小；insertion 类全文件 rewrite 相对少见（真实 trace 中 Facebook/Twitter 以 random write 为主）。
  - **可能失效场景**：视频编辑、大文件 in-place 全量 rewrite、或 backup 前长时间未同步导致累积修改接近全文件——此时 SolFS 退化为「大范围上传」或需配合 rolling checksum。

- **观察 3**：CoW/reflink 式 versioning 能无 hash 标记修改，但引入**碎片化与双倍数据存储**；对 [[F2FS]] 改造成本高。相比之下，**只 version 操作日志、不 version 文件数据**，写仍落到原 inode，可保持 sequential read 性能。
  - **依赖假设**：(offset, length) 日志足以让 APP 定位需上传的字节；日志存储开销可压到可接受（compact mlog、merge、dynamic granularity）。
  - **可能失效场景**：同一字节被反复覆盖后内容不变（write 了但语义未变）——SolFS 仍会标记为 modified，需 APP 侧可选 hash 压缩流量；日志粒度过粗（page-level）会多传未改字节。

- **假设 1**：Backup APP 愿意并能够集成 SolFS 的 `delta_open` / `delta_getdiff` / `delta_close` ioctl，与 cloud server 交换 **version number** 而非 checksum list。
  - **证据强度**：**中**——论文实现了 prototype APP 与 server，但未改造商业 Dropbox/Seafile；生态采纳是部署前提。

- **假设 2**：用户在同一文件上通常只活跃使用**一个** backup APP；多 APP 并存时 versioned inode 链深度仍可控。
  - **证据强度**：**中**——评估明确假设 single backup APP；设计支持多 APP 但链深度 =10 时 diff 搜索 7.6ms，论文称仍远低于 hash，未测极端多 APP 交错 backup。

## 核心方法

SolFS 是构建在现有 mobile FS（原型实现于 [[F2FS]]）上的 **operation-log versioning** 层，不改动正常 read/write 路径，仅在数据修改路径插入轻量日志。

### MLogging（per-file mergeable operation logging）（MLogging（按文件合并操作日志记录））

每次 write（及 fallocate、truncate、mmap PROT_WRITE）产生一条 **mlog**（offset + length），存入 per-file 的 in-memory **mlog tree**（改造自 extent tree）。相邻或重叠 mlog 在插入时合并，控制日志条数。Sequential write/append 用 root 的 **mlog pointer cache** 命中最近 mlog，更新为 **O(1)**；未命中则树插入 **O(log N)**。

- **On-demand loading**：`open` 时不从盘加载历史 mlog，只建空树；writeback 时 worker 线程异步把 in-memory 树与盘上 mlog 合并后持久化，避免拖慢 open 与 I/O critical path。
- **Compact mlog**：盘上每条 mlog 默认 8B（offset 4B + length 4B）；小范围 write 可压成 **4B**（offset 嵌入 length 低 16 位，length 最高位作 compact 标志），mobile 小写场景可省 **33%** 存储。
- **Dynamic granularity**：单文件 in-memory mlog 超 **5000** 条时，从 byte-level 升到 page-level 建新树并转换旧 mlog，换更低内存/存储换更粗修改分辨率。

文件数据仍写在**原 file inode**；mlog 存在**辅助 versioned inode**，避免 CoW 碎片化。

### Backup-driven mlog versioning（备份驱动的 mlog 版本控制）

与传统「每次 write 一个新版本」不同，SolFS **每次 backup 触发**新版本（若自上次 backup 无修改则不插入，保持链紧凑）：

- Versioned inode 通过 **extended attributes** 存 `ino_ver`、`ver_link`、`ino_flag`、`next_ino`，不破坏 [[F2FS]] on-disk 结构，claim **backward compatibility**。
- 各 backup APP 持有自己的 version 指针；diff 时从 APP 的 start version 沿 `next_ino` 链遍历到 latest，合并各版本 mlog 得到**累计修改范围**（extent tree）。
- **`ver_link` 引用计数** + 异步 compaction：无 APP 引用的中间 versioned inode 合并 mlog 后删除，控制链深度与存储。

### Hash-free delta synchronization（无哈希增量同步）

协作流程：backup 后 APP 从 SolFS 拿 version 号同步到 server；下次 backup 从 server 取旧 version，调用 `delta_getdiff` 得累计修改区间与最新 version。Server **不再需要生成/传输 checksum list**（大文件可省显著流量）。

APP 可：
1. **直接上传**修改区间（默认，优先省 mobile CPU）；
2. 对修改区间再做 rolling checksum（类似 WebR2sync+），处理「写了但内容相同」的 corner case；
3. 若 version 不一致（崩溃恢复后），`delta_getdiff` 返回覆盖全文件的特殊 range，强制全量上传。

`delta_open` 期间 **block 该文件 write** 并 flush dirty pages/mlog，保证 diff 视图一致。

### Version consistency（版本一致性）

文件 data 与 mlog 持久化**非原子**。SolFS 用 `ino_flag` 配合 [[F2FS]] write-ordering（data writeback 先于 metadata）：data 已落盘但 mlog 未完成时 flag 保持 dirty，崩溃恢复后**拆除 versioned inode 链**、从更高 version 重启，迫使 APP 全量上传以对齐 cloud。Inode 链结构变更依赖 F2FS checkpoint 防半链。

实现细节与 ioctl 语义见 [[atc2025-pan]]。

## 设计取舍

- **取舍 1：只 log 操作、不 log 数据**——存储与碎片化成本远低于 WaybackFS/CoW snapshot，但无法回答「哪些字节内容实际变了」；为省流量需 APP 可选对修改区间 hash，复杂度上移到应用层。
- **取舍 2：Backup-driven 而非 write-driven versioning**——多 APP 可各管各的 diff baseline，链深度与 backup 频率绑定而非 write 频率；代价是每次 `delta_getdiff` 插入 head versioned inode 并可能短暂 block writes，长 backup 窗口影响写入延迟（论文未量化 tail latency）。
- **取舍 3：Dynamic granularity**——超 5000 mlog 时自动变粗，防止极端 random write 打爆内存；代价是 delta 上传多传 page 内未改字节，网络流量上升。
- **取舍 4：Rename 视为全文件修改**——实现简单、保守正确，但跨目录 rename 大文件会触发不必要全量上传。
- **边界条件**：对频繁小 random write 的 SQLite DB、文档类 APP 最优雅；对 insertion（5MB 处插入导致后半 rewrite）、全文件覆盖、或加密层下不可见 write 的场景变脆。论文**未讨论** metadata-only 变更（`fstat`/xattr 需 APP 自行同步）。

## 实验与结果

**平台**：Google Pixel 8 / Android 14 / kernel 5.15；server Ubuntu 20.04 / i9-14900K。Baseline 为自实现 HashSync（chunk MD5）、[[rsync]]、WebR2sync+（未比 NetSync，非开源）。网络 ~100 Mbps，chunk 2048B，mlog byte-level。

**Microbenchmark（10MB 文件，≤1KB I/O）**：
- 随机更新：SolFS 平均 sync 时间 **-88.8%**；1MB 修改时网络流量仅为 HashSync 的 **12.3%**（避免 checksum list + chunk 对齐放大）。
- 顺序更新：趋势类似；**插入**场景 SolFS 配合 rolling checksum 与 WebR2sync+ 相当，HashSync 需传插入点后 ~5MB（~5× 流量）。
- Sync breakdown（1MB random）：client+server hash 计算开销平均 **-92%**；100Mbps 下软件开销占比 SolFS **10.8%** vs HashSync 21.8% / Rsync 49.3%。

**真实 APP workload**（Facebook/Twitter/Capcut/Dropbox，20 分钟使用后 diff）：
- 平均 sync 时间 **-71%**（HashSync 89s → SolFS 29s）；delta 期间 CPU 使用 **-70%**。
- Random write 主导时 HashSync 反而优于 Rsync/WebR2sync+（二进制数据 + 少 insertion）。

**SolFS 自身开销**（9 条开源 mobile trace 各 2 小时 replay）：
- I/O 性能为原生 [[F2FS]] 的 **99.2%**（差距 <1.5%）；日常 CPU 8.3% → 8.5%。
- 最坏情况（byte-level、关闭释放）累计额外内存 **470KB** / 18 小时；compact mlog 存储比内存再省 **33%**。
- Version 链深度 10：diff 搜索 **1.67ms→7.6ms**；10K mlog 转换 ~10ms，持久化合并 ~30ms。

## 批判性分析

### 论证链条

观察（全文件 hash 贵 + mobile 小写为主）→ 设计（FS 记录 write offset/length + per-APP version）→ 结果（sync 时间与 CPU 大幅下降、F2FS I/O 几乎无损）整体闭合较好。关键跳步在于：**生产 backup APP 是否会改用 SolFS ioctl 与 version 协议**——论文证明了 prototype 路径可行，但未证明商业 APP 在无厂商预装情况下的可部署性。把 microbenchmark 的 88.8% 与「mobile cloud backup 问题已解决」之间仍隔了一层生态采纳。

### 假设压力测试

| 假设 | 压力场景 | 风险 |
|------|----------|------|
| 修改范围 ≪ 文件大小 | 长时间未 backup、日志合并后范围接近全文件 | 优势缩小；page-level granularity 进一步多传 |
| 单 backup APP | 多第三方 APP 交错 backup 同一文件 | Inode 链变长、compaction 逻辑复杂；7.6ms@depth10 仍小，但 block-write 窗口叠加 |
| F2FS write-ordering | 其他 FS 移植、或 ordering 语义变化 | All-or-nothing 恢复策略失效风险 |
| APP 集成 ioctl | 仅系统镜像内置、第三方无权限 | 通用性 claim 打折 |
| Small write 主导 | 视频导出、大文件顺序 rewrite | Mlog 少但单次上传大；与 hash 方案差距收窄 |

**论文已证明**：F2FS 上日志开销可忽略、hash-free diff 在自实现 baseline 上显著更快。**推断未覆盖**：加密文件系统层、端到端加密 backup、多用户隔离、以及 backup 期间 write block 对交互式 APP 的影响。

### 实验可信度

- **Baseline 公平性**：HashSync/Rsync/WebR2sync+ 均为作者 C++/NDK 移植，非官方 APP；调优程度未知，但对比维度一致（同文件、同 trace）。
- **Workload 代表性**：真实 APP dump + 公开 trace 较好覆盖 social/media 场景；缺少大型单文件（相册原图、离线地图）与 multi-APP 并发 backup。
- **Ablation**：compact mlog、mlog cache、dynamic granularity、compaction 有分项微基准，但缺少「关掉 merge / 关掉 backup-driven versioning」的端到端对比。
- **Metric**：覆盖 sync 时间、流量、CPU、I/O、内存；**未测** backup 期间应用 write 尾延迟、电池整盘 backup 曲线、崩溃恢复全量上传频率。

### 系统性缺陷

- **可用性**：`delta_open` 阻塞写入，大文件 backup 时同文件并发写会 stall（论文未讨论超时或 copy-out 策略）。
- **正确性**：崩溃后 version 链重置依赖 APP 全量重传，cloud 与 local 短暂不一致窗口需 APP 处理；metadata backup 非 SolFS 职责。
- **安全/隐私**：论文未讨论 ioctl 暴露的 diff 信息是否构成侧信道，或多租户下 version 隔离。
- **运维**：需 kernel/FS 模块与 APP、server 三方协议升级；对存量 65 亿+ 设备的「backward compatible」指 on-disk layout，不等于无需刷机。
- **可观测性**：论文未讨论 mlog 膨胀、compaction 失败或 version 不一致的 telemetry。

## 局限与后续工作

- **局限 1**：评估假设**单 backup APP**；多 APP 与设计目标 generality 之间仍有工程与性能验证缺口。
- **局限 2**：**Metadata backup**（权限、mtime、xattr）未优化，需 APP 走通用接口，与 data path 割裂。
- **局限 3**：Version 不一致或 crash 后只能 **fallback 全文件上传**，对大文件和 metered 网络仍痛；全量上传触发频率未在生产级长期 trace 上测量。
- **Future work 1**：量化 **backup 期间 write block** 对 SQLite/WAL 等延迟敏感 workload 的影响，并探索 snapshot-read 或无锁 diff 是否可行。
- **Future work 2**：在 **E2E 加密 backup** 与第三方不可信 APP 场景下，评估 operation log 是否泄露访问模式，以及是否需 kernel 侧 access control。
- **Future work 3**：与 **[[Content-Defined-Chunking]]** / server 端 dedup 协议对接——当修改范围大时自动切换「mlog 指引 + 选择性 CDC hash」的混合策略，用 measurement 找交叉点。

## 相关

- **相关概念**：[[Delta-Sync]]、[[F2FS]]、[[Copy-on-Write]]、[[Inode-Versioning]]、[[Log-Structured-File-System]]、[[Content-Defined-Chunking]]
- **同类系统**：[[rsync]]、WebR2sync+、QuickSync、NetSync、WaybackFS、BetrFS、[[SkySync-FAST26|SkySync]]
- **同会议**：[[ATC-2025]]
- **对比**：SolFS 用 **write operation log** 取代全文件 hash；[[SkySync-FAST26|SkySync]] 则复用存储栈已有 checksum 减 hash 计算——二者都质疑「delta sync 必须重算」的前提，但假设的存储层能力不同
