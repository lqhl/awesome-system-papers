---
type: paper
name: HDTX
full_title: Fast Distributed Transactions for RDMA-based Disaggregated Memory
authors: [Haodi Lu, Haikun Liu, Yujian Zhang, Zhuohui Duan, Xiaofei Liao, Hai Jin, Yu Zhang]
venue: ATC
year: 2025
tags: [distributed-transactions, rdma, disaggregated-memory, occ, replication]
source_pdf: "[[atc2025-lu.pdf]]"
source_md: "[[atc2025-lu]]"
---

# Fast Distributed Transactions for RDMA-based Disaggregated Memory (ATC 2025)

> **一句话总结**：用 redo log + RDMA Wait/Enable 把分布式事务压成两个 RTT，并把 Release 阶段下放到 memory node 的 RNIC 上，TPC-C 延迟比 FORD/FaRM 降 72.1% / 88.3%、吞吐升 84.7% / 2.08×。

## 问题

Memory disaggregation 让 compute 与 memory node 分离，DM node 几乎没有 CPU 来跑事务逻辑。OCC + Primary-Backup Replication 的 RDMA dtxn 系统传统要 5 RTT（FaRM、FaSST），SOTA FORD 优化到 3 RTT 但仍要在 commit / release 间发两轮数据；undo log 还会因 RDMA ordering 规则被 Fence flag 拖一个 RTT。还要解决 (1) RTT 数量、(2) commit 阶段 RNIC 复制冗余、(3) DM node 没 CPU 做优先级锁这三个问题。

## 核心方法

HDTX 三件套：

- **Fast Commit Protocol (FCP)**：基于 redo log + visibility bit 把 Validation、Commit Backup、Commit Primary 三阶段压成一个 Validation&Commit RTT。Locking 与 Execution 也合并，整个 dtxn 只需 2 RTT（Execution&Locking → Validation&Commit），后台异步 Release。Validation 失败回滚时 redo log 可直接丢弃，开销与 FORD 相当。
- **RDMA-enabled Release Offloading**：memory node RNIC 初始化时在两个 WQ 中预排好 RDMA Wait、Enable、Write、FAA 等 primitive；computing node Release 阶段只需发 1 个 RDMA Send 携带源/目的地址，RNIC 监听到 Recv 完成事件自动激活后续操作（local copy redo log → 数据区、更新版本、清 visibility bit、解锁），全程不打扰 memory node CPU，节省一轮跨节点带宽。
- **Decentralized Priority Locking**：64-bit lock object 编码两组 Lamport Bakery 队列 ⟨Pc,Pm,Nc,Nm⟩；用 RDMA FAA 抢号，高优先级 dtxn 走优先队列，可在不依赖 memory CPU 的情况下做全局调度；溢出/死锁靠 RDMA CAS 重置 + lease（默认 1 ms）。

支持 PM 持久化（DCPMM + RDMA Flush 一致性），实现于 5 节点集群（双副本）。深度细节见 [[atc2025-lu]]。

## 关键结果

- TPC-C 上比 FORD / FaRM 平均延迟降 72.1% / 88.3%、P99 延迟降 60.9% / 82.7%、吞吐升 84.7% / 2.08×。
- SmallBank 同样有显著吞吐与延迟优势；TATP 因为 80% 只读，三系统接近。
- skewed 高读写冲突场景下 FCP 单独贡献 67.7% 平均延迟下降。
- 写密集 workloads 受益最多。

## 相关

- **相关概念**：[[RDMA]]、[[Distributed-Transactions]]、[[OCC]]、[[Disaggregated-Memory]]、[[Primary-Backup-Replication]]
- **同类系统**：FaRM、FaSST、DrTM+H、FORD、DSLR
- **同会议**：[[ATC-2025]]
