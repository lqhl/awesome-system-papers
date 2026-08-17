---
type: paper
name: ODRP
full_title: "ODRP: On-Demand Remote Paging with Programmable RDMA"
authors: [Zixuan Wang, Xingda Wei, Jinyu Gu, Hongrui Xie, Rong Chen, Haibo Chen]
venue: NSDI
year: 2025
tags: [disaggregated-memory, rdma, remote-paging, rnic-offloading, memory-management]
source_pdf: "[[nsdi2025-wang-zixuan.pdf]]"
source_md: "[[nsdi2025-wang-zixuan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# ODRP：用可编程 RDMA 实现按需远程分页（NSDI 2025）

> **原题**：ODRP: On-Demand Remote Paging with Programmable RDMA

> **一句话总结**：远程 swap 若静态预留内存会浪费容量，若动态注册 MR 或走 RPC 又会压垮 memory node CPU；ODRP 把 4 KiB 分配、地址翻译、swap load/store/invalidate 编成 commodity RNIC 的 self-modifying WR chain，实现 100% 远端内存利用率和近零远端 CPU，真实 workload 相比静态 one-sided RDMA 仅增加 0.8–14.6% 执行时间。

## 问题与动机

[[RDMA]] 适合让 compute node（CNode）直接访问 disaggregated memory，但标准 one-sided data path 不提供动态内存管理。静态为每个 CNode 注册整个 swap space 性能好却利用率低；动态 MR registration 和 two-sided RPC 能细粒度分配，却依赖本就很弱的 memory node（MNode）CPU。

ODRP 的问题不是重新设计交换策略，而是在不增加 SmartNIC/FPGA 的前提下，用 commodity RNIC 原生 work request（WR）链完成远端页分配、映射、访问和回收。

## 关键观察 / 隐含假设

- **观察 1**：CAS、FAA、READ/WRITE、WAIT/ENABLE 组合出的 self-modifying WR chain 足以在 RNIC 上表达复杂控制逻辑（§2.4）。
  - **依赖假设**：RNIC 支持 Enhanced Atomic、scatter/gather 和论文依赖的 WR 排序语义；不同 vendor/firmware 的可移植性未验证。
- **观察 2**：Linux swap backend 知道某 swap address 是否已映射，因此可由 CNode 选择 mapped/unmapped store chain，删去 RNIC 上昂贵的分支（§4.4）。
  - **可能失效场景**：多个 actor 能独立改变映射、或请求并非 swap 语义时，client-assisted state 可能不完整。
- **观察 3**：MNode 已执行的 WR 没有从 WQ 物理擦除；CNode 可计算 index 并重激活 WR，避免 MNode CPU 持续 repost（§4.4）。
- **假设 1**：可信 MNode、可能恶意 CNode 的 threat model 足够；侧信道、RNIC firmware compromise 与 memory exhaustion 仅由预算监控缓解。

## 核心方法

MNode 把 DRAM 划成 4 KiB page，用 FIFO free-page ring 管理，并为每个 CNode维护单级 translation table（TT）。page load、mapped store、unmapped store 和 invalidate 各由一条预装 WR chain 实现；CNode 用 RDMA SEND 触发。

ODRP 构造两个 meta WR：Masked FAA 实现 ring modulo；reverse scatter/gather 用一次 READ 完成 endian swap。unmapped store chain 从 queue pop page、写 TT、存 page content 并通知 CNode，全程不唤醒 MNode CPU。

正确性依赖 TT/free queue 不变量和 RDMA 8-byte atomic access。TT 的 MR permission 把每条 chain 限制在本 CNode 的 TT；非法地址触发 protection error。CNode 的配额用 RNIC hardware counter 由 MNode CPU 周期性读取，而不是扫描 TT。

## 设计取舍

- **取舍 1**：以更长的 WR chain 和 4.6–5.5 μs load/store latency，换 4 KiB 动态分配和零 critical-path CPU。
- **取舍 2**：把部分判断和 WR recycle 计算交给 CNode，简化 RNIC program；安全性依赖 MNode-side bounds 与 protection checks 覆盖全部参数。
- **边界条件**：prototype 只有单 MNode，实验最多 8 CNode、100 Gbps ConnectX-5；free queue 为空时仍需 MNode CPU 修复 head state。

## 实验与结果

- 1 MNode+8 CNode、100 Gbps ConnectX-5；Quicksort、Kmeans、Memcached、GAPBS BC/PR、VoltDB/TPC-C，与 static/dynamic one-sided、two-sided 和 4 KiB MR baseline 比较（§5.1）。
- ODRP、two-sided 和 dynamic/4KB 均达 100% memory utilization；ODRP 比 static 提升 1.72–12 倍，且不使用远端 CPU（图 7）。
- 相比 static one-sided，六类应用执行时间/吞吐损失为 0.8–14.6%；Memcached average/max latency 增量少于 2%，VoltDB average/max latency增量少于 1%/4.9%（§5.2）。
- 8 CNode、32 个 Quicksort task 时，two-sided 和 dynamic 比 static 慢 505%/234%；ODRP 在 8 CNode 达到 static swap throughput 的 87.3%（图 8–9）。
- native RDMA READ/WRITE latency 为 2.9 μs，ODRP mapped store/load 为 4.6/5.5 μs；最慢的 unmapped store 经四项优化由 35.9 μs 显著下降（图 11–12）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| RNIC 可承担页级动态管理而不使用 MNode CPU | 图 7：ODRP remote CPU 近零、utilization 100% | ConnectX-5、单 MNode | 强 |
| 性能接近静态预留方案 | §5.2–5.3：应用 overhead 0.8–14.6% | 最多 8 CNode、六类 workload | 中强 |
| 恶意 CNode 下隔离成立 | §4.5 的不变量与 MR bounds 论证 | 非形式证明，未做攻击实验 | 中 |

## 批判性分析

### 论证链条

论文清楚展示传统方案在 memory utilization、CPU 与 latency 之间的三角冲突，并用 application、scalability 和 microbenchmark 逐层闭合论证。client-assisted principle 是实现简化的关键，而不只是工程细节。

### 假设压力测试

固定 4 KiB allocation/access 与 swap 语义限制了通用性；object store、variable-size allocator 或需要直接 one-sided access 的系统不能直接使用。RNIC 上 WR chain 越复杂，[[PCIe|PCIe]] roundtrip 和 atomic throughput 越容易成为瓶颈。

### 实验可信度

baseline 覆盖 coarse/fine、one/two-sided，且限制 MNode CPU 后又补充 sufficient-CPU 对照，比较较公平。规模只到 8 CNode，单 MNode 与旧版 Linux/OFED 限制了数据中心外推。

### 系统性缺陷

WR chain 与 vendor-specific RNIC 行为耦合，调试、升级和故障观测成本未量化。queue empty、CNode crash 和恶意请求仍有 CPU control plane，因而“零 CPU”只指正常 data path。

## 局限与后续工作

- **局限 1**：只实现单 MNode 和固定页粒度；多 MNode 只给出分区扩展思路。
- **局限 2**：隔离是非形式论证，缺少 fault injection、firmware 差异和资源耗尽实验。
- **后续工作 1**：在多 MNode 与现代 200/400 Gbps RNIC 上测 WR-chain throughput、QP 数和 PCIe contention 的扩展曲线。
- **后续工作 2**：将 allocation/access 解耦为 variable-size primitive，并与 [[OneSidedMW-NSDI26]] 比较安全、灵活性和 latency。

## 相关

- **相关概念**：[[RDMA]]、disaggregated memory、remote paging
- **同类系统**：[[OneSidedMW-NSDI26]]
