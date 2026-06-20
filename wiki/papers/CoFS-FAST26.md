---
type: paper
name: CoFS
full_title: "CoFS: A Filesystem for Fast Container Startup"
authors: [Li Wang, Jinxiu Du, Yang Yang, Qingbo Wu, Tao Liu, Haoze Wu]
venue: FAST
year: 2026
tags: [container, filesystem, fuse, mphf, lazy-pulling]
source_pdf: "[[fast2026-wang-li.pdf]]"
source_md: "[[fast2026-wang-li]]"
---

# CoFS: A Filesystem for Fast Container Startup (FAST 2026)

> **一句话总结**：利用「container image 构建后 filesystem tree 固定只读」这一观察，在 build 时用 MPHF 把 inode metadata 编成 dense array，让 extended [[FUSE]] driver 在 kernel 内单次 I/O 完成 lookup，并用 sparse mirror file 把已下载数据走 host filesystem 快路径；相比 fuse-loopback 平均 lookup 降 73–86%，mariadb/redis/tomcat/elasticsearch 冷启动全面快于 [[Nydus]]-fuse/[[Nydus]]-erofs/[[eStargz]]。

## 问题与动机

[[Kubernetes]] 等编排下的 container cold start 是 serverless 弹性扩缩和 burst 响应的硬瓶颈。Slacker [14] 测量显示：**拉镜像占 container 启动时间 76%，但启动阶段实际只读 6.4% 数据**——大量带宽和时间花在整层 tar.gz 下载与解压上，容易违反 responsiveness SLA。

业界转向 **on-demand pulling（lazy pulling）**：[[Overlaybd]] 在 block 层做 seek-able 镜像；[[Nydus]]、[[eStargz]]、[[Stargz]] 在 filesystem 层做可索引格式，配合 userspace daemon 边运行边从 registry 拉数据。filesystem 层方案还能让多 container 共享 page cache [27]，比 block 层更省内存。

但现有 lazy pulling 在 **metadata lookup** 和 **首次数据访问** 上各有硬伤：

- **[[FUSE]]-based（[[Nydus]]-fuse、[[eStargz]]）**：Linux VFS 逐层 path resolution 会把多次 LOOKUP 转发到 userspace daemon，带来频繁 context switch 与 request/data copy；已缓存数据的 READ 仍经 userspace。
- **[[Nydus]]-erofs + [[fscache]]**：内核 [[EROFS]] 减少 userspace 介入，但首次访问要走 erofs → fscache → userspace daemon 下载 → 同步写盘 → 通知 kernel 的长链路，实测反而慢于 [[Nydus]]-fuse；fscache eviction 不可控还导致性能波动。
- **纯内核方案**：灵活解析自定义 image format + 远程下载的维护成本高。

作者的核心 claim 不是再造一种 image format，而是抓住一个被忽视的结构性事实：**从 container 视角，image 在 build 完成后就是一棵固定的只读 filesystem tree**。现有方案仍把 lookup 当成动态目录遍历，浪费了「key 集合已知且不变」这一前提。

## 关键观察 / 隐含假设

- **观察 1：container image 的 inode metadata 在 build 后不再变化，lookup key 集合 {(parent inode, filename)} 可在 build 时完全枚举。**
  - **依赖假设**：runtime 不修改 lower layer 内容；union filesystem（[[overlayfs]]）的 upper layer 只承载写时复制变更，lookup 热路径落在只读 lower。
  - **可能失效场景**：频繁 overlay upper 写入、动态生成大量新文件（如某些 build-on-run 镜像）、或 image 层在运行时被 remount 为可写时，MPHF 静态索引不再覆盖全部 lookup key。

- **观察 2：FUSE 的 lookup 延迟是 cold start 的主导开销之一，且与目录深度/宽度相关；fuse-loopback 本地镜像仍要多次 userspace LOOKUP。**
  - **依赖假设**：startup 阶段会触发大量 stat/open 导致的 LOOKUP；page cache 冷启动时 metadata 未预热。
  - **可能失效场景**：极小镜像、极浅目录树、或 metadata 已被 prefetch 进 page cache 的 warm start；此时 CoFS 相对收益缩小。

- **观察 3：已下载的 image data 若能通过 kernel 内 host filesystem 直接读取，可与 traditional/[[Nydus]]-erofs 持平，显著优于仍走 FUSE daemon 的方案。**
  - **依赖假设**：mirror sparse file 与 host FS（ext4/xfs/btrfs）的 SEEK_HOLE/SEEK_DATA 语义可靠；VFS inode lock 保证 lseek 与 snapshotter 异步 write 互斥。
  - **可能失效场景**：不支持 sparse file 或 hole 语义的底层 FS；高并发读写同一 mirror file 时若 FS 实现锁粒度不同，可能出现 race（论文仅论证 ext4 路径）。

- **假设 1：MPHF 构建开销（1M files ~34 s、~9.5 MB 辅助结构）相对 image build（数分钟级）可忽略，且 n≈2.5m 时 Czech 算法迭代次数稳定。**
  - **证据强度**：**强**——Table 2 随机图实验 + Table 1 真实镜像 build 时间对比（增幅 5–10%）。

- **假设 2：用 kprobe 挂 `do_filp_open`、对深度 >3 的路径做 bottom-up 并行 inode 构造，与 kernel top-down lookup 可安全并发且普遍有效。**
  - **证据强度**：**中**——elasticsearch 上 parallel lookup 平均再快 28%，但依赖特定 workload 的深路径；kprobe 属于 out-of-tree 侵入，上游可维护性未验证。

## 核心方法

CoFS 由 **cofs-snapshotter**（userspace，基于 [[stargz-snapshotter]] / [[containerd]] snapshotter 插件）和 **cofs-driver**（extended [[FUSE]] driver，Linux 6.9.1）组成，挂载在 [[overlayfs]] lower layer 上。

**MPHF metadata indexing**（回应观察 1–2）：

- Image build 时遍历 filesystem tree，为每个文件分配 inode；以 `(parent_inode || filename)` 为 key，用 Czech 等 O(m) 算法构造 **minimal perfect hash function（MPHF）**，输出 `{m, n, T1, T2, g}`。
- Metadata entry（120 B）存入 dense array，按 MPHF 值索引；hard link 为每个 link 单独占槽位（多 key 同 value）。布局写入 `cofs.inode.array`，基于 [[eStargz]] 格式剥离原 JSON inode 部分。
- Lookup：cofs-driver 在 kernel 内算 hash → 索引 array → 比对 parent inode 与 filename（≤16 B 内联，更长则读 tail extra metadata）→ 构造 inode。**至多一次磁盘 I/O**，page cache 命中则零 I/O。无效 key 仍会算出 hash，靠 stored key 比对拒绝——无 collision chain。

**Parallel path resolution**（回应观察 2 的深度路径）：

- 第二个 MPHF 以**完整绝对路径**为 key，构造时强制与 component-wise MPHF 映射到相同 hash 值（MPHF 可指定 desired hash value 的性质）。
- kprobe 拦截 `do_filp_open`；CoFS 路径且深度 >3 时，workqueue 从路径尾部向上并发预构造 inode。若某层 inode 已在内存，则其祖先必已在内存（bottom-up 与 top-down 的互补不变量）。

**Sparse mirror fast read path**（回应观察 3）：

- 每层镜像对应 mirror 目录 + FUSE mount。snapshotter 异步只拉 `cofs.inode.array` 并通过 ioctl 把 fd 交给 driver；container I/O miss 时从远程拉数据，写入以 inode number 命名的 **sparse mirror file**（nominal size 与远程一致）。
- Read：cofs-driver 用 `vfs_lseek(SEEK_HOLE)` 判断 `[offset, offset+length)` 是否已落盘；已缓存则 `vfs_read` 走 host FS（kernel 内快路径），否则转发 snapshotter（慢路径，等同标准 FUSE）。
- 与 [[ExtFUSE]]、[[RFUSE]]、[[XFUSE]] 等 FUSE 优化正交——它们可加速慢路径，而 CoFS 的核心是减少必须走 FUSE 的 lookup 次数。

## 设计取舍

- **Extended FUSE vs 纯内核 FS**：保留 FUSE 的开发/维护灵活性（远程拉取、格式演进在 userspace），用 MPHF + ioctl 把热路径 lookup 拉回 kernel；代价是仍依赖 FUSE 框架、首次 read 仍可能进 userspace，且需维护 out-of-tree kernel patch。
- **静态 MPHF vs 动态目录结构**：换取 O(1) 级 lookup 与 space-optimal metadata 布局，牺牲对 runtime 动态增删文件的支持；只读 image 场景下这是正确 trade-off。
- **Sparse mirror vs fscache**：本地 sparse file 布局让 startup 热数据趋向连续，后续同镜像 container 可能更快；但 mirror 占用本地磁盘，无统一 eviction 策略描述，长期多镜像场景的磁盘压力论文未量化。
- **Parallel lookup 的 kprobe 方案**：免改 VFS 核心即可实验性加速深路径，但生产可维护性、与 security lockdown / BTF 限制的兼容性存疑；深度 ≤3 的路径不触发并行优化。
- **边界条件**：最适于 **大镜像、深目录、冷 page cache、registry 带宽受限** 的 cold start；warm start、metadata 已缓存、或镜像极小场景收益有限。背景 prefetch（`*-p` 配置）在实验中多数情况下反而拖慢启动——整镜像远大于 startup 实际读取量，与网络/磁盘争用。

## 实验与结果

**测试床**：双路 10-core Xeon E5-2640 V4、128 GB RAM、1 GbE 连远程 registry、4 TB HDD；Linux 6.9.1 + stargz-snapshotter 0.15.1；对比 CoFS（lz4）、CoFS-gzip、traditional、[[Nydus]]-fuse、[[Nydus]]-erofs、[[eStargz]]（含 background download `*-p` 变体）。

- **Cold startup**（bucketbench，等 ready message，清 cache，10 次）：CoFS 在 mariadb/redis/tomcat/elasticsearch 四类镜像上**全面最快**；background download 在多数情况下负优化（与整镜像大小 vs startup 读取量不匹配一致）。
- **Lookup microbenchmark**（SystemTap 测 `fuse_lookup`，对比 fuse-loopback）：平均 lookup 时间降低 **73–86%**；p99 同步改善；`cofs-nonp` 消融显示 parallel lookup 在 elasticsearch 上再快 **28%**。
- **Image 开销**（Table 1）：相对 [[eStargz]]，CoFS 镜像体积增幅 <1%，build 时间增加约 **5–10%**（如 mariadb 23 s → 25.36 s）。
- **MPHF 构建**（Table 2）：1M node 随机图平均 **34 s**，c=n/m 平均 ~2.46，与「build 时可接受」假设一致。
- **Cached read**（100 GB 文件 fio，清 host page cache）：CoFS 与 traditional/[[Nydus]]-erofs 带宽/延迟几乎相同（kernel 内访问）；[[Nydus]]-fuse/[[eStargz]] 明显更低。

## Critical Analysis

### 论证链条

主链条清晰：**测量确立 pulling 主导 cold start 且 FUSE lookup 昂贵**（Introduction + Slacker 引用）→ **只读固定 tree 使 MPHF 静态索引成立**（设计洞察）→ **kernel lookup + sparse mirror 分别砍掉 userspace metadata 与 cached data 开销**（Figure 2 双路径）→ **startup 与 lookup microbenchmark 全面优于 lazy pulling 基线**（Figure 3–5）。

最强支撑是 lookup 消融：相对 fuse-loopback（已去掉网络，只 isolates FUSE lookup 成本）仍有 73–86% 提升，说明收益主要来自 **metadata 路径重设计**，而非仅网络优化。薄弱环节在于 **把四类 Java/DB 镜像的 cold start 优势外推为 general serverless SLA 满足**：未覆盖函数计算极短生命周期、多租户混部、或镜像层数极多时的 snapshotter 调度开销。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| Image tree build 后只读 | 设计前提 + overlay lower 模型 | 运行时大量 upper 写入、init 容器动态 unpack 新文件 |
| MPHF lookup 单次 I/O | microbenchmark + 算法复杂度 | 超长文件名频繁访问（需读 tail）；metadata file 本身未进 page cache 的极端冷启动 |
| Sparse mirror 快路径正确 | ext4 inode lock 论证 + fio | 非 ext4/xfs/btrfs；sparse hole 语义异常；磁盘满时 mirror 增长失败的处理未详述 |
| Parallel lookup 安全有效 | elasticsearch +28% | 浅路径镜像；kprobe 被禁用环境；与 fanotify/security 模块交互 |
| 1 GbE + HDD 结论可迁移 | 有意模拟受限 registry | 数据中心 25/100 GbE + NVMe registry 时，lookup 占比下降、网络优化空间变化；论文未给 breakdown |

### 实验可信度

- **优势**：baseline 覆盖 filesystem 与 block 两条 lazy pulling 路线（[[Nydus]]-fuse/erofs、[[eStargz]]、traditional）；lookup 测试用 fuse-loopback 隔离变量；报告 `*-p` prefetch 负结果，诚实展示 trade-off。
- **局限**：仅 **4 个镜像、单机、1 GbE**；未与 [[Overlaybd]]、[[FlacIO]]（FAST'25 网络层优化）组合；cold start 用修改版 bucketbench，非 production trace；无多 container 并发启动、无 tail latency SLO（P99 startup）；cofs-driver 为 **out-of-tree kernel patch**，复现门槛高。
- **Ablation**：parallel lookup（`cofs-nonp`）有；但缺「仅 MPHF、无 sparse mirror」「仅 sparse mirror、无 MPHF」的分解，难量化两路径各自贡献占比。

### 系统性缺陷

- **尾延迟与多租户**：论文未讨论多 container 同时 cold start 时 snapshotter 下载队列、mirror 目录锁、或 registry 限流下的 P99 startup；仅报平均 lookup 与整体 startup 时间。
- **资源隔离与磁盘管理**：sparse mirror 随访问增长，**无全局 cache quota/eviction 策略**；与 [[fscache]] 相比可控性如何、长期运行磁盘耗尽怎么办，论文未讨论。
- **故障恢复**：remote registry 超时、部分 layer 下载失败、ioctl 传 metadata fd 失败后的重试与一致性，论文未描述；mirror 写一半时 crash 的恢复语义未验证。
- **可观测性与运维**：依赖 kprobe + custom FUSE driver，**升级 kernel 6.9→6.10+ 的维护成本**、与 containerd/[[stargz-snapshotter]] 版本耦合未评估；无可观测性指标（lookup cache hit、mirror fill rate）。
- **安全**：kprobe 挂 `do_filp_open` 的处理全部路径字符串，对不可信 container 是否构成侧信道或性能干扰，论文未讨论。

## 局限与 Future Work

- **局限 1**（设计边界）：CoFS 仍基于 extended [[FUSE]]，**首次数据访问**和 **慢路径 read** 仍有 userspace 参与；不像 [[Nydus]]-erofs 那样全内核，但作者论证 erofs+fscache 首次路径更慢。
- **局限 2**（实验边界）：background prefetch 在多数场景有害，说明 **startup I/O 与全镜像 prefetch 简单叠加不可行**；但未给出基于 access trace 的选择性 prefetch 方案。
- **局限 3**（论文未展开）：MPHF 对 **镜像更新后 key 集合变化** 的处理——每次 rebuild 需重建 `cofs.inode.array`，增量 layer 更新的开销未量化。
- **Future work 1**：测量 **MPHF lookup vs sparse mirror fast path** 在总 startup 时间中的占比分解，指导是否值得把 MPHF 思路移植到纯 in-kernel FS（如 [[EROFS]]）而彻底去掉 FUSE。
- **Future work 2**：在 **25/100 GbE + NVMe registry + serverless burst trace** 上复测，验证当网络不再是绝对瓶颈时，CoFS 相对 [[Nydus]]-erofs/[[eStargz]] 的优势是否仍成立。
- **Future work 3**：设计 **mirror sparse file 的全局容量管理与 eviction**（可按 inode 热度或镜像维度），并与 [[FlacIO]] 等网络层优化正交组合，避免多镜像长期运行的磁盘失控。

## 相关

- **相关概念**：[[FUSE]]、[[EROFS]]、[[Lazy-Loading]]、[[Cold-Start]]、[[Sparse-File]]、[[overlayfs]]、[[MPHF]]、[[containerd]]
- **同类系统**：[[Nydus]]、[[eStargz]]、[[Stargz]]、[[Overlaybd]]、[[fscache]]、[[ExtFUSE]]、[[RFUSE]]、[[XFUSE]]、fuse-loopback
- **同会议**：[[FAST-2026]]
- **对比**：[[Nydus]]-erofs 走全内核但首次访问链路长；[[eStargz]]/[[Nydus]]-fuse 保持 FUSE 灵活性但 lookup/read _userspace 开销大；CoFS 在 FUSE 框架内用 MPHF 把 metadata 热路径推回 kernel