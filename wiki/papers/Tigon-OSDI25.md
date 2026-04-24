---
type: paper
name: Tigon
full_title: "Tigon: A Distributed Database for a CXL Pod"
authors: [Yibo Huang, Haowei Chen, Newton Ni, Yan Sun, Vijay Chidambaram, et al.]
venue: OSDI
year: 2025
tags: [distributed-database, cxl, transaction, cache-coherence, memory]
source_pdf: "[[osdi25-huang-yibo.pdf]]"
source_md: "[[osdi25-huang-yibo]]"
---

# Tigon: A Distributed Database for a CXL Pod (OSDI 2025)

> **一句话总结**：首个用 CXL memory 原子操作同步跨主机事务的内存数据库，通过把 "cross-host active tuples" 放进 CXL 硬件缓存一致区 + 软件缓存一致协议扩展 SWcc 容量，消灭 2PC，在 TPC-C/YCSB 上比 shared-nothing CXL 数据库快 2.5×、比 RDMA 数据库快 18.5×。

## 问题

分布式事务数据库的难题几十年没变：跨主机同步开销大。Shared-nothing 架构下 multi-partition 事务要走 2PC 和大量消息交换；RDMA 加速过的 disaggregated memory 方案把 memory 访问走 RDMA（µs 级 round-trip），仍比本地 DRAM 慢 1-2 个数量级。CXL 3.0/3.2 允许多主机共享 CXL memory 并做硬件缓存一致（cacheline 粒度），且访问是 load/store 指令而非 RDMA 协议，理论上完美解决问题。但 CXL 有两个硬限制：延迟比 local DRAM 高 2× 左右（214-394 ns vs 111-117 ns）、带宽低 10× 左右（18-52 vs 218-246 GB/s）；硬件缓存一致（HWcc）的 snoop filter 出于成本考虑只能覆盖 CXL 物理空间的一小部分（AMD 分析只有 dozens-hundreds MB）。naive 把整个 DB 放 CXL 会性能崩塌。

## 核心方法

关键观察：虽然整个数据库可以很大，但 **正在被多主机并发读写的 tuple 数量很小**（TPC-C 单事务平均 39 个 tuple、共 ~7 KB；1000 核并发也就 7 MB 左右）。作者把这一集合叫做 **CAT (Cross-host Active Tuples)**。Tigon 只把 CAT 放进 CXL，把静止数据留在各主机 local DRAM：这样就把多次跨主机消息 + 2PC 变成 CXL 内的原子操作 + 数据结构操作。

数据组织有三层：(1) 每个主机 local DRAM 存本 partition 的 local row（含 local-latch、2pl-lock、shortcut-ptr、is-valid、tuple）；(2) CXL 的 HWcc 区存 8-byte **HWcc record**（HWcc-latch、2pl-lock、has-next-key、is-dirty、clock-bit、SWcc-bitmap、SWcc-row-ptr），用于跨主机同步的 metadata；(3) CXL 的 non-HWcc（SWcc）区存真正的 tuple。作者设计了软件缓存一致协议，依赖数据库已有 latch：SWcc-bitmap 记录哪些主机可以 cacheable load 该 row；写者 unset 其他主机的 bit，读者看到自己 bit 没 set 就 flush cacheline 再重读——本质上把 coherence 粒度从 cacheline 放宽到 tuple，snoop filter 压力大幅下降，可利用远超硬件一致区的 CXL 容量。

事务层针对 CXL 重做：用 **shortcut-ptr** 让 owner 直接定位 CXL 里自己迁去的 tuple，绕过 CXL 索引；enhance 2PL + next-key locking + has-next-key 标志处理 phantom；用 Pasha 架构和 SiloR 改编的 epoch-based group commit 实现 **无 2PC**——单主机 log 所有 tuple 变化即可保证原子性和持久性，索引变化可从 tuple 恢复期重建。数据 movement 用 CLOCK 策略（把很久没被非 owner 访问的 tuple 搬回 local DRAM），只需每 HWcc record 1 bit。

## 关键结果

- TPC-C：比两个 CXL-as-transport 的优化 shared-nothing 数据库快最多 2.5×
- 比 RDMA-based 分布式数据库快最多 18.5×
- YCSB 变体上也保持同级优势
- 通过实验变化 HWcc 区大小评估限制影响（真实硬件的 HWcc 大小未公开）
- 第一个显式利用 CXL 有限硬件一致区 + 软件一致协议扩展可用 CXL 容量的事务 DB

## 相关

- **相关概念**：[[CXL]]、[[Cache-Coherence]]、[[RDMA]]、[[Two-Phase-Commit]]、[[Disaggregation]]
- **同类系统**：基于 RDMA 的分布式 DB（FaRM、DrTM），shared-nothing DB
- **同会议**：[[OSDI-2025]]
