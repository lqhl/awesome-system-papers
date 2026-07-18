---
type: paper
name: CetoFS
full_title: "CetoFS: A High-Performance File System with Host-Server Collaboration for Remote Storage"
authors: [Wenqing Jia, Dejun Jiang, Jin Xiong]
venue: FAST
year: 2026
tags: [file-system, disaggregated-storage, nvme-of, rdma, userspace]
source_pdf: "[[fast2026-jia.pdf]]"
source_md: "[[fast2026-jia]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# CetoFS: A High-Performance File System with Host-Server Collaboration for Remote Storage (FAST 2026)

> **一句话总结**：在 [[NVMe-oF]]/[[RDMA]] 解聚 Optane SSD 场景下，作者实测内核 [[Ext4]] 数据路径 65% 延迟来自软件栈（其中 NVMe-over-RDMA 驱动占 36%），且 inode 级锁把网络 RTT 放大成并发串行化；CetoFS 将数据面下沉用户态，并把权限检查、并发控制、redo logging 三项 offload 到可信 storage target，单线程 4KB 随机读延迟 19µs（比 Ext4 低 52%）、共享文件并发写吞吐最高提升 19×。

## 问题与动机

存储解聚（disaggregated storage）让计算与存储独立扩缩容；[[NVMe-oF]] over [[RDMA]] 把远端 Optane 等低延迟 SSD 暴露为 initiator 上的块设备，[[Ext4]]/[[F2FS]] 等内核文件系统可直接挂载使用。但作者认为「块设备能远程访问」不等于「文件系统数据路径高效」——在 NVMe-over-RDMA 上跑传统内核 FS，三类开销会叠加：

1. **重内核栈**：4KB 随机写总延迟 ~41µs 中，syscall + FS + NVMe + NVMe-oF 驱动占 65%，其中 NVMe-over-RDMA 驱动单独占 36.1%；一次写路径上有 3 次 RDMA 中断唤醒内核线程。
2. **串行化被网络放大**：并发写共享文件时，host 端 inode reader-writer lock 要求前一请求走完「发命令→写盘→回 completion」全流程才释放锁；远端场景下 T2/T3 分别多等 26.6µs / 53.2µs 纯网络等待，20 线程吞吐反而比 1 线程低 30%。
3. **failure-atomic IO 跨网搬移昂贵**：journal/CoW 都要在 host 与 target 间多次往返搬日志或旧数据，journal 路径上数据搬移超过 2×。

已有 userspace FS（[[uFS]]、[[SplitFS]] 等）针对本地 SSD/PM，要么忽略网络延迟对并发与原子写的影响，要么权限检查依赖 IOMMU/SSD 固件/page table 等无法直接用于 RDMA 远程块设备的机制。CetoFS 的核心 claim 是：**在保持内核控制面安全语义的前提下，把数据面与三类网络敏感操作协同 offload 到 storage target**。

## 关键观察 / 隐含假设

- **观察 1：NVMe-over-RDMA 上内核软件栈已成为主导延迟，而非设备或网络本身。**
  - **依赖假设**：实验硬件为 ConnectX-5 + Intel Optane P4800X，NVMe-oF 走 CPU mode（非 NIC offload mode）；应用使用 O_DIRECT 绕过 page cache。
  - **可能失效场景**：TCP fabric、更高性能 RDMA NIC/驱动优化、或 kernel-bypass block 层（如 [[ReFlex]]）显著削减驱动开销后，userspace 相对收益会缩小；NIC offload mode 虽省 target CPU 但论文引用其性能可降 88%，故未采用。

- **观察 2：host 端 inode 锁导致的串行化，在远程存储下会把网络 RTT 线性叠加到等待链上，并导致 RDMA/SSD 利用率不足。**
  - **依赖假设**：workload 存在对同一文件的并发写或读写交错；锁粒度为文件级（非 range/page 级优化路径）。
  - **可能失效场景**：每线程私有文件（DWOL/DWAL）时各 FS 差距大幅缩小；全线程 hammer 同一 4KB block（DRBH）时所有系统都卡在 ~160 Kops/s，offload 并发控制帮不上忙。

- **观察 3：failure-atomic IO 的瓶颈是跨网数据搬移次数，而非日志算法本身。**
  - **依赖假设**：应用使用 CetoFS 提供的 `atomic_write_start/commit/abort` API；target 有足够 CPU/内存跑 redo log 与 background checkpoint。
  - **可能失效场景**：需要与 POSIX 原子写语义完全兼容、或 crash consistency 要覆盖 metadata+data 的统一事务模型时，两阶段 append 与 K-FS journal 的语义可能弱于完整 FS 事务。

- **假设 1：remote storage server（target）是厂商提供的可信实体，可安全执行权限检查与并发排序。**
  - **证据强度**：中——这是架构前提而非实验验证项；多租户云存储若 target 被攻破，reverse permission table 即最后一道防线。

- **假设 2：每文件独立 request queue + 用户态 extent 翻译表足以支撑高性能数据路径，且 K-FS 仅在 open/fiemap miss 时介入。**
  - **证据强度**：中——Varmail 等 metadata 密集 workload 下 CetoFS 与 F2FS 打平，说明控制面往返仍会成为瓶颈；论文未测百万级同时 open 文件。

## 核心方法

CetoFS 采用 **host–target 三层协作**：U-Lib（用户态 shim）、K-FS（复用 [[Ext4]] 管 metadata/控制面）、T-Handler（target 端 userspace IO 服务）。

**Userspace 数据面**：U-Lib 拦截 read/write，维护 per-file address translation table（extent tree，fiemap 按需填充），通过 per-file 双 ring buffer（server_rb / host_rb）用 [[RDMA]] `WRITE_WITH_IMM` 提交请求（immediate 字段携带 server_rb 槽位地址，避免 target 轮询全部队列）。每 initiator 线程一个 RDMA QP，而非每文件一个 QP，规避 QP 规模问题。

**Offload #1 — 权限检查**：打开文件时 K-FS 做标准权限校验并建立 queue；数据路径上 target 维护 block-granularity **reverse permission table**（每 block owner ID = 文件 inode 或 0 表示 metadata/free）。T-Handler 校验「block owner == queue owner」且操作类型匹配 queue 的 RO/WO/RW flag。表存 SSD 保留区（1TB 盘约 2GB），可整表或按 device block 缓存到 radix tree。Append 分两阶段：先 `fallocate` 让 K-FS 分配 block 并更新 permission entry，再 userspace 写数据。

**Offload #2 — 并发控制**：U-Lib 用 per-file spinlock 分配 monotonic group ID——每个 write 自成一组，相邻 read 合并入当前组；嵌入 group/request ID 后立即释放锁并并行 RDMA 提交。T-Handler 用 curr_gid、first_rid_table、curr_fin_reqs、curr_max_rid、rid_to_queue_pos 五元状态 + poller/finisher 算法保证 **inter-group 严格顺序、intra-group 并行**。进一步用 per-file 红黑树做 **merging group**：无范围冲突的相邻 group 合并，使 disjoint 区域可并行打到 SSD。

**Offload #3 — failure-atomic IO**：提供 `atomic_write_start` / `atomic_write_commit` / `atomic_write_abort`。选 redo logging（非 undo）使 host 仅一次跨网写新数据到 target 端 t_log；commit 只刷 transaction metadata 到 pt_table，checkpoint 异步回写原位。配合 transaction-aware batch submission/completion 减少 RDMA doorbell MMIO。

## 设计取舍

- **收益 vs 安全边界**：把 block 级权限与并发正确性押在 target，换取 host 侧零内核数据路径与并行提交；代价是信任模型从「内核强制」变为「target + reverse table」，且非法地址请求只能在 target 被拒绝。
- **收益 vs 语义/兼容性**：只 offload 数据面 read/write/atomic write API，metadata 操作仍走 K-FS syscall；POSIX 全语义兼容但 append 原子性与 [[Ext4]] metadata journaling 同级，非更强保证。
- **收益 vs 资源开销**：per-file queue 上限 64K（与 NVMe-oF 驱动类似），大集群需按权限共享 queue；reverse permission table 占盘 0.2%，pt_table 持久化带来写放大（论文建议未来用 NVMe PMR 优化）。
- **边界条件**：对共享文件、范围不重叠的并发写（DWOM + merging group）最优雅；metadata 密集或单 block 热点读写下优势有限；open 额外 ~5µs（约占 open 总时间 31%）是一次性摊销成本。

## 实验与结果

- **单线程微基准**：4KB 随机读延迟 CetoFS 19µs vs Ext4 42µs（内核栈多 26µs）；顺序/随机 overwrite 平均吞吐比 Ext4/F2FS/uFS 高 74%/65%/24%；append 高 52%/50%/12%。
- **并发 FxMark**：DWOM（共享文件并发写）CetoFS 唯一持续扩展，相对 Ext4/F2FS/uFS 平均高 72%/76%/38%；DRBH 全体 ~160 Kops/s 饱和；私有文件 DWOL/DWAL 仍领先但差距小于 DWOM。
- **Filebench**：Fileserver 平均吞吐 +75%/+72%/+64%；Webserver/Webproxy +25–33% / +14–50%；Varmail 与 F2FS 相近（metadata 密集暴露 K-FS 交互成本）。
- **LevelDB db_bench**：write sync 延迟比 Ext4/F2FS 低 57%/30%；其他写操作低 up to 31%/23%；读因 block cache 提升较小。
- **Atomic write**：单线程比 J-Undo/J-Redo 高 1.8×/58%；64KB 并发 atomic write 吞吐最高，~12 线程后 SSD 带宽饱和。
- **Breakdown**：permission check 内存命中仅 +0.2µs；最坏 translation+permission 双 miss 36.7µs 仍低于 Ext4；并发写 MG policy 相对 RW lock 接近 Ideal no-lock。

## Critical Analysis

### 论证链条

论文从 §2 延迟分解（内核栈 > 硬件）→ userspace 数据面设计 → 三类 offload 分别对应锁放大、原子写搬移 → 微基准/Filebench/LevelDB 验证，主链条闭合较好。最强证据在 **DWOM 并发写** 与 **atomic write 跨网次数**，直接对应两个 motivation 量化实验。较弱环节是把单节点双机 Optane 结果外推到「解聚 NVMe SSD 普遍最优」——未测多 tenant、多 target、纠删/副本、故障恢复路径。

### 假设压力测试

- **可信 target**：云厂商多租户 JBOF 若 target OS 被攻破，reverse table 即数据面全部防线；论文未讨论 attestation 或加密完整性。
- **64K open files**：超限时需按权限共享 queue，可能削弱 per-file 隔离语义；百万容器场景未验证。
- **Metadata-heavy workload**：Varmail 已显示 F2FS 可匹敌甚至依赖 roll-forward fsync 优势；CetoFS 没有 offload metadata 快速路径。
- **硬件代际**：Optane + ConnectX-5 属于低延迟组合；普通 NAND SSD 或更高延迟网络下，userspace 绝对收益仍在但 offload 并发控制的相对价值可能变化。

### 实验可信度

- Baseline 选取合理：内核 [[Ext4]]/[[F2FS]] + 扩展远程能力的 [[uFS]]，覆盖 journal FS、log-structured FS、userspace semi-microkernel FS。
- 公平性：统一 O_DIRECT；uFS 远程扩展为作者实现；atomic write 对比自建 J-Undo/J-Redo 而非仅内核默认路径，更能 isolate offload 价值。
- 缺口：缺少 tail latency / P99、故障注入与 crash recovery 正确性测试、多 initiator 竞争同一 target、security microbenchmark（非法地址攻击）、与 [[CrossFS]]/[[Trio]] 等 range-level 并发 FS 的对比。LevelDB 单线程也难以压测 U-Lib 并发控制。

### 系统性缺陷

- **故障恢复**：redo log + pt_table 描述较完整，但无端到端 crash/recovery 实验数据；checkpoint 与 permission table 更新的一致性依赖 K-FS journal 通知 T-Handler，运维复杂度高于纯内核 FS。
- **尾延迟与隔离**：未报告 P99；target worker 数、per-file queue 竞争、background checkpoint 对 foreground IO 的干扰均未量化。
- **可观测性/运维**：三套组件（U-Lib、K-FS 补丁、ceto_open、T-Handler）部署与升级链长于单内核 FS；论文未讨论。
- **多节点扩展**：RAID-0/dRAID、OCFS2 式分布式锁仅为 future work，当前本质是单 initiator–单 target 优化。

## 局限与 Future Work

- **局限 1**：每文件 request queue 上限 64K；open 路径额外 RDMA 交换 ~5µs；append 需两阶段，高吞吐 append 依赖后台 preallocation 优化。
- **局限 2**：pt_table 持久化带来写放大；Varmail 表明 metadata 密集场景优势消失；仅评估单 initiator 对单 Optane target。
- **Future work 1**：扩展到多 SSD/多 target/多 initiator（dRAID、OCFS2 分布式锁）；将 T-Handler offload 移植到 [[DPU]]/SmartNIC（论文引用 [[Gimbal]]、[[LeapIO]] 路线）。
- **Future work 2**：用 NVMe PMR 降低 pt_table 刷盘放大；与 kernel-bypass 远程块层（[[ReFlex]]、[[RIO]]、[[Volley]]）正交组合的上限需实测。

## 相关

- **相关概念**：[[NVMe-oF]]、[[RDMA]]、[[Disaggregated-Storage]]、failure-atomic IO、redo logging、reader-writer lock、userspace file system
- **同类系统**：[[Ext4]]、[[F2FS]]、[[uFS]]、[[SplitFS]]、[[CrossFS]]、[[Trio]]、[[ReFlex]]、[[RIO]]、[[Volley]]、[[Gimbal]]
- **同会议**：[[FAST-2026]]
- **对比**：CetoFS 把并发与原子写 offload 到 target；[[CrossFS]] 用 FD-queue + interval tree 在设备侧排序但放松读一致性；[[uFS]] 全 FS 进 trusted process 导致 IPC 开销
