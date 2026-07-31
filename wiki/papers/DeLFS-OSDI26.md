---
type: paper
name: DeLFS
full_title: "DeLFS: A Decentralized Log-Structured File System for Manycores"
authors: [Taehwan Ahn, Chanhyeong Yu, Sangjin Lee, Yongseok Son]
venue: OSDI
year: 2026
tags: [file-system, log-structured-file-system, manycore, concurrency, garbage-collection]
source_pdf: "[[osdi26-ahn.pdf]]"
source_md: "[[osdi26-ahn]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向众核的去中心化日志结构文件系统（OSDI 2026）

> **原题**：DeLFS: A Decentralized Log-Structured File System for Manycores

> **一句话总结**：现有日志结构文件系统（LFS）在解除 page-cache 节流后会依次暴露多组全局锁瓶颈；DeLFS 把元数据、日志头、I/O 提交与 GC 划成 per-core domain，并以单锁更新和延迟协调维持一致性，在 128 核随机写下相对 F2FS、MAX、ScaleLFS、F2FSJ 分别最高提升 4.34×、4.29×、4.10×、4.50×。

## 问题与动机

LFS 将随机小写转成顺序写，适合 flash，但 F2FS 等系统仍围绕固定数量的 log head、bio 与全局元数据结构组织写路径。论文的 profiling 表明，加入可扩展 page cache 后性能并不会自然扩展：解除 dirty-page throttling 和 inode writeback serialization，只会让 `curseg_mutex`、`io_rwsem`、SIT/NAT、segment list 与 discard 锁依次成为新瓶颈（§3.2、表 1）。因此问题不是一把“最热的锁”，而是集中式所有权贯穿整个 LFS 数据路径。

作者的目标是在不放弃 F2FS checkpoint crash consistency 的前提下，让普通写入与 GC 都随核心数扩展。DeLFS 基于 Linux 6.6.8、F2FS 与 ScaleCache 实现，重点面向高并发、写密集、[[NVMe|NVMe]] 饱和之前受 CPU synchronization 限制的服务器。

## 关键观察 / 隐含假设

- **观察 1**：page-cache flushing 只是第一层瓶颈；解除节流和 per-inode serialization 后，空间分配、bio 合并、SIT/NAT、segment/discard 管理的集中式锁会级联接棒（§3.2、表 1/4）。
  - **依赖假设**：设备带宽和应用并发足够高，使 CPU 侧锁竞争而非介质延迟主导。
  - **可能失效场景**：低并发、读为主或慢设备上，去中心化收益会缩小而 CPU/元数据成本仍存在。
- **观察 2**：多数写入可在 core-local 资源完成，少量跨核更新又可拆成关键路径与可延期路径，因此没有必要在前台同步获取全部远端锁（§4.2–§4.5）。
  - **依赖假设**：checkpoint 是可用的全局一致性边界，延期任务能在 checkpoint 前排空。
  - **可能失效场景**：频繁 checkpoint、空间高度倾斜或 core-local free pool 枯竭会增加跨核协调。
- **假设 1**：按 core 划分 segment 和元数据造成的局部 victim 选择损失，小于解除锁竞争所得收益。
  - **证据强度**：中；GC 实验中总 WAF 仅从 1.088 升至 1.101，但设备、填充方式与 workload 范围有限。
- **假设 2**：固定 CPU 拓扑和 core ownership 在部署周期内稳定，且额外 CPU 消耗可接受。
  - **证据强度**：中；128 核实验显示扩展性，但未覆盖容器 CPU 热插拔、频繁 affinity 变化与多租户隔离。

## 核心方法

DeLFS 先把 SIT、NAT、SSA、current segment、bio 与 segment 划为 per-core domain，形成“一核一资源”的去中心化组织（图 3）。正常写路径优先访问本核元数据与 segment，从所有权层面消除原本覆盖整个表或固定六个 log stream 的共享锁。

仅把锁拆开会引入跨 domain 死锁。去中心化且解耦的锁（DDL）把复合更新拆成一次只持有一个资源锁的 `lock-update-unlock` 操作，并用严格顺序和原有 checkpoint 机制维持原子恢复语义（§4.4）。这回应了“锁不能简单删除，但所有权可以安全分散”的观察。

对并非前台正确性所必需的远端更新，lazy lock coordinator 将任务委托给目标 core 的 coordinator；checkpoint 前等待并协助处理未完成任务（§4.5）。这样前台不必因远端锁共享而停顿，同时保留明确的持久化屏障。

GC 也按 core-local segment 运行，并在本地候选不足时逐渐扩展到其他 core。它牺牲全局最优 victim 选择，换取并行回收与较低锁竞争；GC reader/writer lock 与 checkpoint 保证回收和前台写入的 crash consistency（§4.6）。

## 设计取舍

- **局部性换全局最优**：per-core segment pool 提升锁与 I/O 局部性，但可能选择回收成本更高的 victim，并在空间不足时退化为跨核访问。
- **异步性换协调复杂度**：lazy coordination 缩短前台路径，却把“延期任务必须在 checkpoint 前完成”变成新的正确性不变量。
- **并行度换 CPU**：系统用更高 CPU utilization 换取更高设备吞吐；这不一定适合 CPU 配额紧张的多租户环境。
- **边界条件**：写密集、高核数、剩余空间充足时最优雅；论文显示可用空间降至 1% 时与 F2FS 性能几乎相同（表 7）。

## 实验与结果

- 在双路 128-core AMD EPYC 7713、96 GB DRAM、2 TB FireCuda 530 NVMe 上，FIO 128 线程、每线程 2.2 GB、4 KB 随机写时，DeLFS 相对 F2FS、MAX、ScaleLFS、F2FSJ 吞吐分别高 4.34×、4.29×、4.10×、4.50×（图 12a）。
- 相对各系统加入 ScaleCache 与 serialization-free 的最佳变体，128 核下仍高 3.70×、6.41×、3.05×、3.89×；99th-percentile latency 分别低 3.73×、2.75×、3.5×、2.75×（图 12c）。
- GC 场景使用 30 GB partition、128 线程先写约 28.5 GB 再 overwrite；DeLFS execution time 最高低 2.77×、device bandwidth 最高高 2.32×，总 WAF 相对 F2FS 只增加 1.2%（§5.2）。
- Filebench fileserver/varmail/videoserver 中相对 F2FS 吞吐分别高 2.34×、1.66×、1.31×；[[RocksDB|RocksDB]] YCSB A/B/F/update-only 在 128 核下相对 F2FS 高 1.78×、1.19×、1.98×、2.24×（图 13/14）。
- deLLC 在处理约 7300 万 invalid pages 时相对 DFL、DDL 高 89.63% 与 43.83%，总 delegation time 为 1.32 s（表 5）。
- aged fileserver 中仍最高比 F2FS 快 1.96×；额外内存约 1121.67 KB、checkpoint storage 11.9 KB；Crash-Monkey 覆盖 checkpoint 与 create/delete workload，均通过（§5.6–§5.7）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 集中式 LFS 存在级联锁瓶颈，单点修补不足 | §3.2、表 1/4 | F2FS 系列、ScaleCache、128-core x86、NVMe 随机写 | 强 |
| DeLFS 显著提高 manycore 写吞吐并改善尾延迟 | 图 12a/12c | 4 KB FIO、1–128 threads、281.6 GB 最大数据集 | 强 |
| 去中心化 GC 的局部 victim 损失较小 | §5.2、图 12d/12e | 30 GB partition、一次 overwrite GC 场景 | 中 |
| 收益可延伸到应用工作负载 | 图 13/14 | Filebench 三种 workload、RocksDB/YCSB 四种 workload | 强 |
| 仍维持 crash consistency | §5.7 | Crash-Monkey 的 checkpoint 与 create/delete 两类测试 | 中 |

## 批判性分析

### 论证链条

论文从逐层解除锁后的 bottleneck shift 出发，而不是只展示最终系统速度，observation → resource ownership → locking → result 的链条较完整。表 4 的逐步分解支持“必须整体去中心化”的论点。不过，从两类 Crash-Monkey workload 推到完整 crash consistency、从单机固定拓扑推到一般 manycore 部署，仍有未覆盖的跳步。

### 假设压力测试

论文已证明在 128 核、单 NVMe、写密集 workload 下全局锁是主导瓶颈，也测得空间从 75% 降至 1% 时收益逐步消失。由此可推断，core-local space 的均衡程度是隐含控制变量；长时间运行后数据温度、core affinity 与 free-space skew 共同变化时，远端协调可能更频繁。[[NUMA|NUMA]] placement、CPU hotplug 与容器迁核均未测量。

### 实验可信度

baseline 包括 F2FS、MAX、ScaleLFS、F2FSJ 及其 ScaleCache/serialization-free 变体，且覆盖 micro、macro、RocksDB、aging、GC、breakdown，证据面较强。主要局限是只有一台 x86 server、一个 SSD 型号；报告十次平均但未给置信区间，Crash-Monkey workload 也偏少。

### 系统性缺陷

checkpoint 同时成为延期任务排空和 crash consistency 的关键边界，若 coordinator stalled 或 checkpoint latency 升高，可能形成新的尾延迟风险。论文报告额外元数据很小，却未讨论 per-core domain 在数百至数千核、CPU offline、任务跨核与多租户 quota 下的运维语义，也未给 recovery time 和故障注入覆盖率。

## 局限与后续工作

- **局限 1**：单设备、单 NUMA 服务器不足以验证跨 socket locality 和多设备 striping 下的 ownership 设计。
- **局限 2**：1% free space 时性能优势消失，说明空间倾斜是实质退化点而非边缘情况。
- **局限 3**：Crash-Monkey 只覆盖两类 workload，无法量化 DDL/deLLC 各交错点的 crash-state 覆盖。
- **后续工作 1**：在不同 free-space skew、core migration rate 与 checkpoint frequency 的二维/三维扫描中，测量 remote-lock ratio、99.9th latency 与 WAF，找出退化边界。
- **后续工作 2**：对每个延期更新阶段做 power-cut fault injection，并以可恢复状态数量与 recovery latency 审计一致性协议。
- **后续工作 3**：在多 NVMe 与更高 core count 上比较静态 per-core ownership、NUMA-aware ownership 与动态 rebalance 的吞吐/迁移成本。

## 相关

- **相关概念**：[[Log-Structured-File-System]]、[[Crash-Consistency]]、[[Garbage-Collection]]、[[Manycore-Scalability]]
- **同类系统**：[[F2FS]]、[[ScaleLFS]]、[[ScaleCache]]、[[MAX]]
- **同会议**：[[OSDI-2026]]
