---
type: paper
name: DeLFS
full_title: DeLFS: A Decentralized Log-Structured File System for Manycores
authors: [Taehwan Ahn, Chanhyeong Yu, Sangjin Lee, Yongseok Son]
venue: OSDI
year: 2026
tags: [file-system, log-structured, manycore, decentralized-locking, garbage-collection]
source_pdf: "[[osdi26-ahn.pdf]]"
source_md: "[[osdi26-ahn]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-14
---

# 面向多核系统的去中心化日志结构文件系统（OSDI 2026）

> **原题**：DeLFS: A Decentralized Log-Structured File System for Manycores

> **一句话总结**：现有日志结构文件系统在 128 核上被 page flush、日志分配、I/O 提交和段元数据的全局锁限制在约 1.06 GB/s；DeLFS 将资源和锁按核拆分，并把可延迟的远端失效处理移出关键路径，在同一测试机上相对 F2FS、MAX、ScaleLFS 和 F2FSJ 的随机写吞吐最高分别提升 4.34×、4.29×、4.10× 和 4.50×。

## 问题与动机

日志结构文件系统（LFS）把小随机写转换为大块顺序写，适合闪存，但传统实现把 SIT、NAT、段列表、多头日志和 bio 提交结构集中管理。多核并发增加后，page cache 刷写、段分配和元数据更新会争用少数全局锁。论文的测量显示，NVMe 原始随机写吞吐可随核心数扩展至 5.24 GB/s，而 F2FS、MAX、ScaleLFS 和 F2FSJ 在增加核心后仍约为 1.06 GB/s（图 1、图 2）。

作者先用 ScaleCache 消除脏页刷写中的阻塞，再发现性能仍被 `writepages`、`curseg_mutex`、`io_rwsem`、`sentry_lock`、段列表和 NAT 等锁限制。也就是说，单独优化 page cache 或垃圾回收并不能消除 LFS 的整体集中式组织问题。

## 关键观察 / 隐含假设

- **观察 1：瓶颈会沿 I/O 路径逐层转移。** 消除 page-flushing throttling 后，争用转移到 per-inode writeback 序列化锁；放宽该锁后，又转移到多头日志分配和 bio 提交；继续拆分后，SIT、段列表、NAT 和 discard 管理成为瓶颈（表 1、表 4）。
  - **依赖假设**：这些资源可以按核拆分，且跨核访问不是每次写入的常态。
  - **可能失效场景**：核心间工作极度倾斜、空间耗尽导致频繁远端分配，或工作负载大量覆盖旧块时，远端锁共享会重新成为主导成本。
- **观察 2：部分更新可以从应用线程的关键路径中移出。** 覆盖写需要把新块标为有效并把旧块标为失效；节点只有在新块完成有效登记后才指向新块，因此旧块失效可以延后到 checkpoint 前完成（图 8、图 10）。
  - **证据强度**：强。论文给出了节点锁、checkpoint reader/writer lock、commit record 和 Crash-Monkey 测试的配合流程，但该结论依赖既有 F2FS 恢复语义。
- **假设 1：以“每核拥有一个资源域”为主要组织方式不会造成不可接受的空间碎片或 GC 损失。** 证据强度：中。DeLFS 在本地空间耗尽后按 round-robin 借用其他核心的段，并报告总 WAF 仅从 F2FS 的 1.088 增至 1.101，但更极端的空间倾斜仍会削弱收益。
- **假设 2：checkpoint 足够不频繁，延迟队列能够在提交前被处理而不拖慢系统。** 证据强度：中。论文报告远端失效委派总耗时仅 1.32 秒，但没有给出不同 checkpoint 频率、故障密度和队列积压下的完整敏感性分析。

## 核心方法

DeLFS 基于 Linux 6.6.8 的 F2FS 和 ScaleCache，包含三个相互配合的设计。

1. **去中心化资源组织。** SIT、NAT、SSA、当前段信息、多头日志、bio 和数据段被分成 per-core domain。普通刷写优先使用执行核自己的段和元数据，使一次 inode 的 I/O 路径尽量保持在一个资源域内。空间不足时再按 round-robin 使用其他核心的空闲段（图 3–图 6）。这直接回应了观察 1。
2. **去中心化、解耦锁（DDL）。** 每个资源域拥有自己的锁。跨域更新不再持有一个锁等待另一个锁，而是将新块有效登记和旧块失效登记拆成两个 lock-update-unlock 序列。节点锁保证节点不会先指向无效块，checkpoint 保证崩溃恢复时 SIT 状态收敛到一致版本（图 7、图 8）。与要求按核心编号获取全部锁的 DFL 相比，DDL 减少了等待和死锁环。
3. **lazy lock coordination。** 远端旧块失效由目标核心的 decentralized lazy lock coordinator 异步处理。应用线程只完成本地有效登记、节点更新和委派；checkpoint 在写 commit record 前协同处理所有待处理任务（图 9、图 10）。因此远端锁等待不再阻塞普通写入关键路径。
4. **去中心化 GC。** 多个线程以 GC reader lock 协作，各自从本地段列表选择 victim 并迁移数据；本地没有脏段时再按 round-robin 扩展到其他核心域。checkpoint 阶段使用 GC writer lock 将全空段转为 free segment（图 11）。局部 victim 选择牺牲了全局最优性，换取了正常 I/O 与 GC 的并行性。

## 设计取舍

- **空间局部性换取跨核访问成本。** 核心本地分配减少锁争用并改善读合并，但本地 free pool 耗尽后必须访问远端域。可用空间从 75% 降到 1% 时，DeLFS 相对 F2FS 的优势从 2.37× 降至接近 1×（表 7）。
- **延迟失效换取关键路径吞吐。** 委派会短暂保留两个有效块，并引入队列、协调器和 checkpoint 协作逻辑。论文以节点锁和 commit record 证明了正确性，但队列积压、异常终止和恢复期间的运维可见性讨论较少。
- **局部 GC 换取 WAF。** DeLFS 的 victim 选择不保证全局最优，GC 阶段 WAF 开销比 F2FS 高；在给定实验中总 WAF 只增加 1.2%，但更偏斜的数据布局可能放大该代价。

## 实验与结果

- 在双路 AMD EPYC 7713、128 核、96 GB DRAM 和 FireCuda 530 NVMe SSD 上，FIO 采用 4 KB 请求、每线程 2.2 GB 文件；128 线程总数据量为 281.6 GB。DeLFS 随核心数扩展，随机写吞吐相对 F2FS、MAX、ScaleLFS、F2FSJ 最高提升 4.34×、4.29×、4.10×、4.50×（图 12a）。
- 在同一组最佳配置下，128 核时 DeLFS 的 P99 尾延迟比 F2FS+ScaleCache+serialization-free、MAX、ScaleLFS 和 F2FSJ 低 3.73×、2.75×、3.50× 和 2.75×（图 12c）。
- GC 实验使用 30 GB 分区和 128 个线程。DeLFS 的应用级执行时间最高降低 2.77×，设备级带宽最高提高 2.32×（图 12d、图 12e）；总 WAF 为 1.101，而 F2FS 为 1.088。
- filebench 中，DeLFS 相对 F2FS 的 fileserver、varmail、videoserver 吞吐分别最高提高 2.34×、1.66×、1.31×（图 13）。
- RocksDB/YCSB 的 update-only 工作负载上，DeLFS 相对 F2FS、MAX、ScaleLFS、F2FSJ 最高提高 2.24×、2.14×、2.54×、2.20×（图 14d）。在读占比较高的 workload B 上仍有 1.19×–1.77×优势，说明写路径争用会干扰读操作。
- 在约 7300 万个失效页的重覆盖场景中，deLLC 比 DFL 和 DDL 分别快 89.63% 和 43.83%，委派总耗时为 1.32 秒（表 5）。额外内存约 1121.67 KB，checkpoint 元数据额外占用 11.9 KB（§5.6）。Crash-Monkey 的 checkpoint 与 create/delete 测试通过（§5.7）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 全面拆分 LFS 资源和锁能改善多核写扩展性 | 随机写吞吐，图 12a；锁分解，表 4 | 128 核 AMD EPYC、单块 NVMe、FIO 4 KB 随机写 | 强 |
| 将远端失效处理延后能减少关键路径阻塞 | DFL/DDL/deLLC 对比，表 5；流程，图 9–10 | 约 7300 万失效页、特定覆盖工作负载 | 强 |
| 去中心化 GC 的 WAF 代价可接受 | WAF 1.088→1.101，§5.2 | 30 GB 分区、特定随机覆盖实验 | 中 |
| 设计适用于更真实的应用负载 | filebench 图 13、RocksDB/YCSB 图 14 | 三种 filebench 和四种 YCSB 工作负载，仍为单机 | 中 |

## 批判性分析

### 论证链条

论文的主要链条较完整：锁争用测量定位到多个集中式资源，资源按核拆分后再用 DDL 和 deLLC 处理跨域更新，最后用性能分解显示瓶颈逐步下降。它还测试了 GC、老化、低空闲空间和崩溃一致性，而不是只报告理想的随机写吞吐。

但“整体去中心化是必要的”与“在更大规模上仍然有效”之间仍有一步未被直接覆盖。实验规模最高为 128 核、单块 NVMe；没有展示多设备、跨 NUMA 节点、更多核心或多个租户同时运行时，per-core 元数据和跨域空间分配是否继续扩展。

### 假设压力测试

DeLFS 默认写入可以归属到执行核的资源域，跨核访问是例外。文件迁移、线程迁移、强烈的 inode 热点或高度倾斜的 free pool 可能破坏这一假设。表 7 已显示可用空间只有 1% 时优势基本消失，但论文没有报告热点文件集中在少数核心时的锁和段分布。

DDL 的一致性论证依赖节点锁与 checkpoint 的顺序。若未来加入更复杂的事务、写回错误处理或 journaling 模式，这个顺序是否仍成立需要单独验证。论文也指出，把 F2FSJ 式 journaling 集成进 DeLFS 的 metadata-intensive 场景仍是后续工作。

### 实验可信度

基线覆盖 F2FS、MAX、ScaleLFS、F2FSJ，并分别加入 ScaleCache 和 serialization-free 变体，能够区分 page cache、序列化锁和后续元数据锁的作用。filebench、RocksDB/YCSB、老化和 Crash-Monkey 提高了覆盖面。限制在于硬件平台只有一台 128 核机器和一块消费级 NVMe SSD，缺少多设备、不同 SSD 队列深度、不同 NUMA 绑定及生产 trace 的结果；因此性能倍数不应直接外推为所有存储平台上的收益。

### 系统性缺陷

去中心化复制了锁和数据结构，增加了 per-core 管理、跨域分配、lazy coordinator 和 checkpoint 协作代码。论文报告的内存与存储开销很小，但没有量化代码维护、调试、故障诊断和在线扩缩容成本。论文也未讨论核心热插拔、CPU 亲和性改变、协调器线程饥饿、异常退出时待处理队列的可观测性，以及在多租户环境中的隔离效果。

## 局限与后续工作

- **局限 1：硬件与规模边界窄。** 结论来自单机、128 核、单块 NVMe；需要在多 NVMe、更多 NUMA 节点和不同 SSD 写放大特征上测量锁扩展和设备利用率。
- **局限 2：空间极度紧张时收益消失。** 表 7 的 1% available-space 配置中，DeLFS 与 F2FS 几乎持平。后续可测量全局 free-pool 调度、段迁移和预留空间策略对跨核分配的影响。
- **局限 3：metadata-intensive 场景仍有空缺。** 作者明确把 F2FSJ 式 journaling 集成列为未来工作；应在大量小文件、频繁 rename/fsync 和目录元数据更新下分别测量 checkpoint 延迟、恢复时间与尾延迟。
- **局限 4：一致性测试覆盖有限。** Crash-Monkey 通过了两类 workload，但尚未覆盖 deLLC 队列积压、写回错误、checkpoint 并发 GC 和设备重置等故障组合。

## 相关

- **相关概念**：[[Log-Structured File System]]、[[Garbage Collection]]、[[Crash Consistency]]、[[NUMA]]
- **同类系统**：[[F2FS]]、[[MAX]]、[[ScaleLFS]]、[[ScaleCache]]
- **同会议**：[[OSDI-2026]]
