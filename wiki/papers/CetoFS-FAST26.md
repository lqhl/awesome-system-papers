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
---

# CetoFS: A High-Performance File System with Host-Server Collaboration for Remote Storage (FAST 2026)

> **一句话总结**：面向 NVMe-over-RDMA 解聚 SSD 的 host-target 协同文件系统：数据面整体下沉用户态、把权限检查/并发控制/redo logging 三件事 offload 到目标端，单线程文件访问延迟降最多 52%、并发吞吐提升最多 19×（vs Ext4/F2FS/uFS）。

## 问题

[[NVMe-oF]]（NVMe-over-RDMA）让远端 SSD 暴露成本地块设备，但作者实测在 Ext4 上跑 4 KB 随机写时：内核栈占总延迟 65%（其中 NVMe-over-RDMA 驱动一项占 36%，因为有 3 次 RDMA 中断处理）、并发写吞吐反而随线程数从 1→20 跌 30%（inode-level reader-writer lock 把网络延迟放大成串行化等待）、failure-atomic IO 用 journaling/CoW 都要往返多次跨网数据搬移。

已有 userspace FS（uFS、Strata 等）只针对本地设备，要么忽略网络延迟要么权限检查不能直接搬过去（特殊硬件 / page-table 控制对 SSD 不适用 / 三方进程通信开销大）。

## 核心方法

**Userspace-kernel 协同 + 三大 offload**：

- **架构**：U-Lib（用户态 shim 库，拦截系统调用，per-file 双 ring buffer = server_rb + host_rb，用 [[RDMA]] WRITE_WITH_IMM 携带 server_rb 地址）+ K-FS（复用 Ext4 管 metadata 和打开时的权限检查）+ T-Handler（远端 userspace 进程，多 worker 轮询 server_rb 直接打 NVMe）。
- **Offload #1 权限检查**：在目标端建一个 block-granularity reverse permission table（每 block 的 owner ID = 文件 inode 号 / 0 表示元数据/free）。每个 server_rb 绑定一个 owner，T-Handler 收到 IO 请求先查 block owner 是否匹配队列 owner、再校验 read/write flag，1 TB 盘只占 2 GB 表（< 0.2%）。Append 走 fallocate 两阶段处理。
- **Offload #2 并发控制**：U-Lib 用 per-file spinlock 给每个 write 自增一个 group ID（连续 read 共享一个 group），把 Group/Request ID 嵌进 RDMA 请求即释放锁，**冲突请求并行发送**到目标。T-Handler 用 5 个状态变量（curr_gid, first_rid_table, curr_fin_reqs, curr_max_rid, rid_to_queue_pos）+ poller/finisher 双任务保证 inter-group 严格顺序、intra-group 并行。Merging group 用红黑树检测无范围冲突的相邻 group 合并执行。
- **Offload #3 失败原子 I/O**：传统 journaling 要 2 次跨网搬数据；CetoFS 把 redo log 直接落到目标端 t_log，host 只发 1 次数据。in-memory mt_table + persistent pt_table + log_index 管理事务，commit 后 background checkpoint。

## 关键结果

- 单线程：4 KB 随机读延迟 19 µs（Ext4 42 µs，省 26 µs 内核栈）；append 平均比 Ext4/F2FS/uFS 高 52%/50%/12% 吞吐。
- 并发：FxMark DWOM（共享文件并发写）唯一线性 scale，比 Ext4/F2FS 高 19×。Filebench Fileserver 比三者高 75%/72%/64%。
- LevelDB write sync 延迟比 Ext4/F2FS 降 57%/30%。

## 相关

- **相关概念**：[[NVMe-oF]]、[[RDMA]]、failure-atomic I/O、redo logging、reader-writer lock
- **同类系统**：[[Ext4]]、[[F2FS]]、uFS、Strata
- **同会议**：[[FAST-2026]]
