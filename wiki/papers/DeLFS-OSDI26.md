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
last_reviewed: 2026-08-14
---

# 面向众核的去中心化日志结构文件系统（OSDI 2026）

> **原题**：DeLFS: A Decentralized Log-Structured File System for Manycores

> **一句话总结**：DeLFS 发现扩展 page cache 只会让日志结构文件系统的瓶颈从节流依次转移到 writeback、空间分配、I/O 提交和元数据锁，于是把日志、SIT/NAT/SSA、I/O 与 GC 划成 per-core domain，再用 DDL 和延迟锁协调处理跨核更新，在 128 核 4 KB 随机写下相对 F2FS、MAX、ScaleLFS、F2FSJ 分别提升 4.34、4.29、4.10、4.50 倍。

## 问题与动机

日志结构文件系统（log-structured file system，LFS）把小随机写整理成顺序日志，适合 flash。问题是，[[F2FS]] 一类系统仍用固定数量的 log head 和 bio，并用全局锁保护 SIT、NAT、segment list、discard list 等结构。核心数增加后，多个写线程不是并行前进，而是在同一组锁前排队（§2–§3）。

论文的初始测量很直接：裸 [[NVMe]] 随核心数扩展到约 5.24 GB/s，F2FS、MAX、ScaleLFS 和 [[F2FSJ-OSDI25|F2FSJ]] 却停在约 1.06 GB/s（图 1）。接入 ScaleCache 后，dirty-page 节流消失，但吞吐没有明显改善，因为瓶颈马上转到 per-inode writeback serialization；再删掉这把锁，curseg、bio、SIT/NAT 和 segment/discard 管理又依次变热（表 1、表 4）。

因此，DeLFS 不把问题看成“一把锁太慢”，而是把整个写路径的集中式资源所有权看成根因。它在 Linux 6.6.8 上基于 F2FS 与 ScaleCache 实现，目标是在保持原有 checkpoint crash consistency 的前提下，让普通写入和 [[Garbage-Collection|垃圾回收]] 都能利用 128 核并行度（§4–§5）。

## 关键观察 / 隐含假设

- **观察 1：解除一个瓶颈只会暴露下一层集中式锁。** 原始 F2FS 的 96.17% 执行时间花在 io_schedule_timeout；加入 ScaleCache 后 writepages 占 52%；再去掉 serialization 后 curseg_mutex 占 47.95%（表 1）。继续拆分后，sentry、NAT、segment-list 和 discard 锁又依次成为主因（表 4）。
  - **依赖假设**：工作负载并发度和设备带宽足够高，使 CPU 同步而不是介质延迟成为主导瓶颈。
  - **可能失效场景**：低并发、慢盘或纯读 workload 下，去中心化不会带来同等级收益。
- **观察 2：大多数写路径资源可以由当前 core 独占；论文重点处理的跨核情况是旧块失效和本地 free segment 耗尽。** 因此可以先让每个 core 在自己的日志和元数据域内完成常见路径，只为少数远端访问付协调成本（图 3–6、§4.3）。
  - **依赖假设**：空间和写入在 core 之间大致均衡，线程/CPU 归属不会频繁变化。
  - **可能失效场景**：free-space skew、CPU migration 或单个热 inode 集中到少数 core 时，远端锁比例会上升。
- **观察 3：覆盖写的“新块置 valid”和“旧块置 invalid”可以分开执行。** 只要 node lock 保证指针更新顺序，checkpoint reader/writer lock 保证落盘边界，两次 SIT 更新不必同时持有两把跨核同类锁（图 7–8、§4.4）。
  - **依赖假设**：所有延期的 invalidation 都在 checkpoint commit 前完成；恢复始终以 checkpoint 的 commit record 为边界。
  - **证据强度**：中；时序论证清楚，但 fault test 只覆盖两个 Crash-Monkey workload。
- **观察 4：局部 GC 可能选到较差的 victim，却能用更低的锁竞争换来更短的总执行时间。** 论文的 GC workload 中，总 WAF 只从 F2FS 的 1.088 增到 DeLFS 的 1.101（§5.2）。
  - **依赖假设**：这个 1.2% 增幅能代表长期、不同数据温度和更严重空间倾斜下的代价。
  - **可能失效场景**：设备长期接近满盘时，本地 victim 质量和跨核借空间成本会同时恶化。

## 核心方法

DeLFS 先重划资源所有权。它把 SIT、NAT、SSA、current-segment information、bio、segment 和相关锁拆成 per-core domain；每个 core 主要从自己的多头日志分配 block，并把所处理 inode 的脏页写进自己的 segment（图 3–5）。本地 free segment 用完时，才按 round-robin 到下一个 core 的 free-space domain 借空间（图 6）。这种做法从结构上移除全局热点，而不只是把一把锁换成更细的锁。

仅做 per-core partition 会产生跨域死锁。覆盖写同时涉及新块和旧块：两个 core 若各自持有本地 SIT 锁，再等待对方的锁，就形成环。DeLFS 的 decentralized and decoupled locking（DDL）规定，跨 core 更新同一种资源时，一次只持有一把该类型的锁，按 lock—update—unlock 拆成两个步骤（图 7）。它并没有删除 F2FS 原有的核内嵌套顺序；例如 NAT-tree/NAT-list、SIT/segment-list 仍按原顺序获取（§4.4）。

DDL 的正确性依靠 node lock 与 cp_rwsem。系统先把新 SIT entry 标为 valid，再处理旧 entry 的 invalidation，最后才更新 node 指向新块。checkpoint writer 必须等待此前的 reader 退出，因此 checkpoint 要么恢复旧状态，要么在 commit record 后恢复完整的新状态（图 8）。中间时刻可能暂时有两个 valid block，但 node 不会指向 invalid block。

DDL 仍可能等待远端 SIT 锁。decentralized lazy lock coordinator（deLLC）进一步把远端旧块 invalidation 从应用关键路径拿走：应用完成本地 valid update 后，把 invalidation 委托给目标 core 的 coordinator，随后更新 node 并返回。checkpoint 会等待并协助清空全部待办任务，之后才写 commit record（图 9–10、§4.5）。这个机制只延期可安全拆开的工作，并不把所有跨核操作都异步化。

GC 也沿用 per-core domain。多个应用线程持共享 GC reader lock，并行从各自 segment list 选 victim 和迁移数据；某个 core 没有本地 dirty segment 时，再按 round-robin 帮其他 core。最先完成的线程取得 GC writer lock，等待其他迁移结束，再通过 checkpoint 把 pre-segment 转成 free segment（图 11、§4.6）。这样普通 I/O 与回收路径使用同一套去中心化资源。

## 设计取舍

- **局部性换空间弹性**：静态 per-core segment pool 减少共享，却会在某些 core 先耗尽时触发远端分配；可用空间只剩 1% 时，DeLFS 与 F2FS 几乎同速（表 7）。
- **并行度换 CPU**：DeLFS 的 CPU utilization 为 47.56%，明显高于原始 LFS，并与去掉节流和 serialization 的 SC+SF 变体处在相近范围；CPU 配额紧张时，吞吐提升不等于成本效率提升（表 2）。
- **异步关键路径换新不变量**：deLLC 减少应用等待，但 coordinator queue 必须在 checkpoint 前全部完成；checkpoint latency 现在同时受待办 invalidation 数量影响。
- **局部 victim 换 WAF**：per-core GC 避免全局 segment-list 锁，却放弃全局最优 victim；测得 WAF 增加 1.2%，长期满盘下可能更高。
- **简单恢复换全局边界**：DDL/deLLC 复用 checkpoint，避免另做日志协议，但 cp_rwsem、GC reader/writer lock 仍是全局同步点。
- **写路径收益换适用范围**：read-only 已接近设备上限，DeLFS 与其他 LFS 表现相近；主要价值来自高并发写和读写混合 workload（图 12b）。

## 实验与结果

- 在双路 128-core AMD EPYC 7713、96 GB DRAM、2 TB FireCuda 530 NVMe 上，FIO 使用 1–128 线程、每线程 2.2 GB 文件和 4 KB 请求。128 线程随机写时，DeLFS 相对 F2FS、MAX、ScaleLFS、F2FSJ 的吞吐分别高 4.34、4.29、4.10、4.50 倍（图 12a、§5.2）。
- 即使把 ScaleCache 和 serialization-free 都加到各基线，DeLFS 在 128 核仍高 3.70、6.41、3.05、3.89 倍；相对这些最强变体，99th-percentile latency 分别降低 3.73、2.75、3.5、2.75 倍（图 12a/12c）。
- 30 GB partition 的 GC 实验用 128 线程先写约 28.5 GB，再覆盖同一 workload。DeLFS 的 application execution time 最多降低 2.77 倍，device bandwidth 最多提高 2.32 倍；总 WAF 从 1.088 增至 1.101（图 12d/12e、§5.2）。
- Filebench 的 fileserver、varmail、videoserver 相对 F2FS 分别提高 2.34、1.66、1.31 倍。[[RocksDB]] 使用 10 million records、1.28 million operations；YCSB A/B/F/update-only 在 128 核相对 F2FS 分别提高 1.78、1.19、1.98、2.24 倍（图 13–14）。
- 表 4 的逐步分解显示，单项去中心化会继续暴露新热点：吞吐从 F2FS+SC+SF 的 1.23 GB/s，经 De-curseg 的 0.51、De-io 的 0.56、De-sentry 的 1.49、De-NAT 的 2.45、De-LLC 的 3.04、De-seglist 的 4.21，最终到 De-discard 的 4.55 GB/s。表 5 中，deLLC/DDL/DFL 吞吐为 2471/1718/1303 MB/s，总执行时间为 119/171/226 s；处理 71,377,706 个委托任务只累计 1.32 s delegation time。
- aged fileserver 下，DeLFS 在 128 线程为 3047 ops/s，F2FS 为 1557 ops/s；可用空间从 75% 降到 10% 时，DeLFS 相对 F2FS 的优势从 2.37 倍降到 1.17 倍，1% 时为 468 对 458 ops/s。额外内存为 1121.67 KB，checkpoint storage 为 11.9 KB；Crash-Monkey 的 checkpoint 与 create/delete 两类测试均通过（表 6–7、§5.6–§5.7）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 现有 LFS 的扩展问题是整条路径上的级联瓶颈 | 表 1、表 4 的锁占比与逐步分解 | F2FS 系列、Linux 6.6.8、单台 128-core x86 server | 强 |
| holistic per-core resource design 显著提高写吞吐并降低尾延迟 | 图 12a/12c：最高 4.50 倍吞吐、3.73 倍更低 p99 | 4 KB FIO、单个 NVMe、最多 281.6 GB dataset | 强 |
| DDL/deLLC 比严格全局锁序更适合跨核更新 | 表 5：2471 对 1718/1303 MB/s，119 对 171/226 s | 1.8 TB 预填充、约 7138 万次 invalidation | 强 |
| 去中心化 GC 的 victim 质量损失在该实验中较小 | WAF 1.088→1.101，执行时间最高降低 2.77 倍 | 30 GB partition、一次预填充加 overwrite | 中 |
| crash consistency 被保留 | 图 8/10 的时序论证；§5.7 Crash-Monkey 全部通过 | 仅 checkpoint_example 与 create_delete 两类 workload | 中 |

## 批判性分析

### 论证链条

论文最有说服力的地方不是最终 4 倍吞吐，而是先展示“修一层、下一层接棒”的 profiling，再用表 4 逐项重建同一条路径。observation → per-core ownership → DDL/deLLC → throughput 的链条基本闭合。表 5 还把“去中心化资源”与“怎样安全协调远端锁”分开，说明严格锁序、拆分更新和延期 invalidation 的差别。

但是，性能结论和正确性结论的证据强度不同。性能由多类 workload 和消融支持；crash consistency 主要依赖协议时序，加上两个 Crash-Monkey workload。后者还不足以覆盖 DDL 与 deLLC 每个中间状态、queue drain 和 GC/checkpoint 交错。

### 假设压力测试

实验已经显示 free space 是关键控制量：空间从 75% 降到 1%，优势几乎完全消失。这说明 core-local pool 不是无条件成立的抽象。若写入、数据温度或 free segment 在 core 之间严重倾斜，远端借空间、远端 invalidation 和较差 GC victim 会同时增加。论文没有直接报告 remote-access ratio、coordinator queue depth 或 checkpoint 等待时间随 skew 的变化。

固定 CPU ownership 还隐含稳定的调度环境。容器改变 affinity、CPU hotplug、任务迁核以及双路 [[NUMA]] 的 remote-memory placement 都可能削弱 local domain 的价值。论文使用双路机器，却没有按 socket 分解吞吐、锁等待或内存访问。

### 实验可信度

baseline 较完整，包括 F2FS、MAX、ScaleLFS、F2FSJ，以及加入 ScaleCache 和 serialization-free 的加强版本；micro、Filebench、RocksDB、GC、aging、free-space 和消融也覆盖了主要场景。每项运行 10 次并报告平均值。

不足是只有一台服务器、一个消费级 SSD 和一个 kernel 版本，且没有置信区间。尾延迟只报告 p99，没有 p99.9 或 checkpoint/GC spike；RocksDB 仍是 YCSB，而不是 production trace。更高 CPU utilization 是否值得，还缺少 ops/CPU-second 或能耗结果。

### 系统性缺陷

去中心化并未消除所有全局协调：checkpoint writer、GC writer 和“checkpoint 前清空 deLLC”仍可能形成尾延迟瓶颈。论文没有说明 coordinator 过载时的 backpressure、queue memory bound、故障或卡死检测，也没有报告 recovery time。per-core 元数据本身只多约 1.1 MB，但维护 core ownership、跨核借空间和调度亲和性的运维复杂度没有量化。

## 局限与后续工作

- **局限 1**：结论来自单机、单 NVMe 和最多 128 核，不能直接外推到多盘、更多 socket 或数百核。
- **局限 2**：free space 接近 1% 时收益消失；论文没有给出更一般的空间倾斜和动态 rebalance 策略。
- **局限 3**：Crash-Monkey 只测两个 workload，deLLC queue、GC 与 checkpoint 的故障交错覆盖不足。
- **后续工作 1**：在每个 DDL/deLLC 状态转换后注入 power loss，并枚举 checkpoint、create/delete、overwrite、GC 的交错；报告可恢复状态覆盖率和 recovery latency。
- **后续工作 2**：联合扫描 free-space skew、checkpoint frequency 和 CPU migration rate，测 remote-lock ratio、deLLC queue depth、p99.9 latency、WAF 与吞吐，找出明确退化边界。
- **后续工作 3**：在多 NVMe、不同 NUMA placement 和更高 core count 上比较静态 per-core ownership、NUMA-aware ownership 与动态 rebalance 的收益和迁移成本。
- **后续工作 4**：加入多租户 CPU quota 和读写干扰实验，报告 ops/CPU-second、fairness 和 checkpoint spike，判断更高 CPU utilization 是否值得。

## 相关

- **相关概念**：[[Garbage-Collection]]、[[NVMe]]、[[NUMA]]
- **同类系统**：[[F2FS]]、MAX、ScaleLFS、[[F2FSJ-OSDI25|F2FSJ]]
- **应用评测**：[[RocksDB]]
- **同会议**：[[OSDI-2026]]
