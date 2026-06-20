---
type: paper
name: IntervalSkiplist
full_title: "Scalable Address Spaces using Concurrent Interval Skiplist"
authors: [Tae Woo Kim, Youngjin Kwon, Jeehoon Kang]
venue: SOSP
year: 2025
tags: [virtual-memory, mmap, scalability, linux, data-structure]
source_pdf: "[[3731569.3764807.pdf]]"
source_md: "[[3731569.3764807]]"
---

# Scalable Address Spaces using Concurrent Interval Skiplist (SOSP 2025)

> **一句话总结**：Linux 6.8 上 Apache/LevelDB 等最高 **90%** 时间等在 [[mmap_lock]]；concurrent interval skiplist 把 interval map 与细粒度锁合一，在 48-core 上 mmap microbench **13.1×**、LevelDB **4.49×**、Apache **3.19×**。

## 问题与动机

[[Virtual-Memory]] address space 的 Alloc（[[mmap]]）/Modify（munmap/mprotect）在 Linux 等内核用粗粒度 **mmap_lock** 写锁序列化；Fault 可 per-VMA 并行但 Alloc/Modify 仍互斥。现代 malloc 多 arena、MapReduce/DB 频繁 mmap，multi-thread 扩展性差。RadixVM 可并行但 RCU/实用性不足；per-VMA locking 未解决 Alloc/Modify 互斥。

## 关键观察 / 隐含假设

- **观察 1**：lockstat 显示高线程数下 Apache **90%**、Metis **60%**、Psearchy **41%**、LevelDB **40%** 时间等 mmap_lock（Figure 1）。
  - **依赖假设**：测试配置代表「VM 密集」类生产负载。
  - **可能失效场景**：jemalloc 禁用 munmap、tcmalloc 少 mmap 的应用收益有限。
- **观察 2**：locking interval 动态变化，需数据结构同时承担 map + 锁区间管理。
  - **依赖假设**：skiplist 上 fine-grained lock + RCU-safe 遍历可实现。
  - **可能失效场景**：极大地址空间稀疏映射时 skiplist 层级开销需验证。
- **假设 1**：POSIX 透明、无需改应用即可获益。
  - **证据强度**：强；Linux 6.8.0 完整实现。

## 核心方法

**Concurrent interval skiplist**：interval→metadata，集成映射与 per-interval 锁；支持并行 interval alloc/modify/查询。

配套：**全局锁快速路径**、分层 Alloc 策略（新 address layout + skiplist leveling）、可扩展 resource limit counter。

实现：Linux 6.8.0 fork；开源 https://github.com/kaist-cp/interval-vm.git 。

## 设计取舍

- **取舍 1**：skiplist vs maple tree/B-tree——换并行性可能增常数因子，微 benchmark 赢但极端稀疏 map 未详述。
- **取舍 2**：保持 POSIX 语义 → 不能采用 RadixVM 式简化假设。
- **边界条件**：Psearchy **1.27×**、Metis **1.47×** 提升低于 LevelDB/Apache。

## 实验与结果

- mmap microbenchmark：**13.1×**
- LevelDB：**4.49×**；Apache：**3.19×**；Metis：**1.47×**；Psearchy：**1.27×**
- 平台：dual-socket **48-core**，Linux 6.8.0

## Critical Analysis

### 论证链条

lockstat 瓶颈证据 → interval skiplist 并行 Alloc/Modify → 多应用加速，链条直接。upstream Linux 合并路径与 maple tree 维护成本是工程跳步；与 per-VMA + 未来无锁 maple 改进的竞争未评测。

### 假设压力测试

- **安全**：细粒度锁死锁/优先级反转——实现需 lock order 纪律，论文概述但生产 hardened 需时间。
- **workload**：Go/runtime 大量 mmap 行为各异；Android 内核是否可移植另说。
- **内存**：skiplist 指针开销 vs maple tree 紧凑性 trade-off 未量化。

### 实验可信度

KAIST 团队、标准 benchmark + microbench；缺 Windows/FreeBSD 对比（背景提及但未实现）。

### 系统性缺陷

仅 address map 层；页表 shootdown、TLB 压力在超高频 munmap 场景论文未与 baseline 分离测量。内核 upstream 审查风险未讨论。

## 局限与 Future Work

- **局限 1**：对少 mmap 应用收益小。
- **局限 2**：skiplist 内存开销 vs tree 需 workload 级剖析。
- **Future work 1**：合并到主线后跑 Meta/Google 级服务 trace，测 tail latency 而非仅吞吐。
- **Future work 2**：与 [[Copier]]/userfaultfd 频繁 map 交互的复合效应。

## 相关

- **相关概念**：[[Virtual-Memory]]、[[mmap]]、[[RCU]]、[[Scalability]]
- **同类系统**：RadixVM、Linux per-VMA locking、maple tree
- **同会议**：[[SOSP-2025]]