---
type: paper
name: IntervalSkiplist
full_title: "Scalable Address Spaces using Concurrent Interval Skiplist"
authors: [Tae Woo Kim, Youngjin Kwon, Jeehoon Kang]
venue: SOSP
year: 2025
tags: [operating-systems, virtual-memory, concurrency, scalability, linux-kernel]
source_pdf: "[[3731569.3764807.pdf]]"
source_md: "[[3731569.3764807]]"
---

# Scalable Address Spaces using Concurrent Interval Skiplist (SOSP 2025)

> **一句话总结**:用并发 interval skiplist 替换 Linux `mmap_lock` + maple tree,真正并行化 `mmap`/`munmap`/`mprotect` 等 Alloc/Modify 操作,单 mmap microbench 吞吐 13.1×,LevelDB 4.49×、Apache 3.19×、Metis 1.47×、Psearchy 1.27×。

## 问题

Linux 等主流内核的地址空间操作靠 `mmap_lock`(读写锁)串行化 Alloc(mmap) 和 Modify(munmap/mprotect/mremap/madvise)。在 48 核 dual-socket 机上,Apache 浪费 90% 时间等锁,Metis 60%、Psearchy 41%、LevelDB 40%——被社区长期称作 "最难缠的内存管理竞争点"。per-VMA 锁只救了 Fault,Alloc/Modify 依然串行;range-lock 补丁退化为 global lock。唯一真正并行化的是 sv6 上的 RadixVM,但 radix tree 不亲和 RCU,per-page metadata 开销大,Alloc 启发式易耗尽地址空间,工程上不可落地 Linux。

## 核心方法

作者识别并系统解决五个可扩展性挑战:

- **动态 locking interval**:munmap 要锁的范围依赖 address map 的当前状态(metadata 结构跨界、邻接 gap 也得锁以防 page table 复活)。既有 "先查再锁" 两步走会在高并发下不断 retry。解法:把 map 和 lock 合体进 **concurrent interval skiplist**——每节点是一个 interval,节点级锁与 interval map 语义统一,traversal 是 [[RCU]]-safe 的 lock-free。
- **Scalable & RCU-safe interval updates**:传统 B-tree/red-black tree 跨多节点更新在 RCU 下要 copy 整条路径(包括 sibling 和祖先),maple tree 每节点 10–16 entry 使 copy 更贵。Skiplist 结构天然对跨多节点更新友好,节点粒度锁即可原子化连续区间更新。
- **全空间操作(fork/exit)**:fine-grained 锁要抓几十万把锁太贵。引入新 **distributed lock**——锁 CPU core 而非每个节点,让 global 操作廉价。
- **Alloc 策略**:Linux first-fit 让所有并发 mmap 撞在同一起点。作者重设进程 address space 布局为多 arena,skiplist 内部分层支持 arena,CAS 插入 node,让并发 Alloc 天然分散。
- **资源限额**:`setrlimit` 类全局计数器成为瓶颈。设计 **adaptive scalable counter**:平时走 percpu_counter,临近上限时逐步切回集中计数以 enforce hard limit。

工程落地:基于 Linux 6.8.0 实现,POSIX 兼容、对应用透明,不改用户代码。

## 关键结果

- 48 核双 socket 下相对 Linux 6.8.0:
  - mmap microbenchmark 13.1×
  - LevelDB 4.49×
  - Apache 3.19×
  - Metis MapReduce 1.47×
  - Psearchy 1.27×
- 代码开源:github.com/kaist-cp/interval-vm

## 相关

- **相关概念**:[[RCU]]、[[Skip-List]]、[[Virtual-Memory]]、[[Fine-Grained-Locking]]、[[Linux-Kernel]]
- **同类工作**:RadixVM(sv6)、Linux maple tree、range-lock 补丁、per-VMA locking
- **同会议**:[[SOSP-2025]]
