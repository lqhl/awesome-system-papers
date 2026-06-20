---
type: paper
name: Mage
full_title: "Scalable Far Memory: Balancing Faults and Evictions"
authors: [Yueyang Pan, Yash Lala, Musa Unal, Yujie Ren, Seung-seob Lee, et al.]
venue: SOSP
year: 2025
tags: [far-memory, remote-memory, rdma, scalability, memory-offloading, tlb-shootdown]
source_pdf: "[[3731569.3764842.pdf]]"
source_md: "[[3731569.3764842]]"
---

# Scalable Far Memory: Balancing Faults and Evictions (SOSP 2025)

> **一句话总结**：针对多核 page-based far memory 的 fault-in/eviction 协调崩塌，提出 always-asynchronous decoupling + cross-batch pipelining + contention avoidance，MageLnx/MageLib 吞吐 **1.2–4.2×**、memcached P99 降 **94.5%**。

## 问题与动机

Page-based far memory 通过 [[RDMA]] 透明扩展本地 DRAM，云厂商广泛采用。但 Hermit、DiLOS 等为低线程数优化，在 48 线程 GapBS 上仅 10% offload 就掉 **75%/**50% 吞吐，远超 ideal ~10%。根因：把为毫秒级磁盘设计的 paging 机制硬套微秒级远程内存——TLB shootdown 跨核 IPI 昂贵、全局 LRU 争用、allocator tail latency。

## 关键观察 / 隐含假设

- **观察 1**：高线程数下 eviction path 吞吐崩塌是 fault-in 等待空闲页的主因，而非单次 RDMA 延迟。
  - **依赖假设**：应用 memory bandwidth 需求超过单 eviction 线程服务能力时，同步 fallback 会阻塞 fault-in。
  - **可能失效场景**：极低线程数或 working set 极小，eviction 压力可忽略。
  - **证据强度**：强——Fig. 5 fault-in only vs fault-in+eviction 对比，sequential scan prefetch 仍无收益。
- **观察 2**：精确 page hotness 追踪在多核下争用成本高于收益。
  - **依赖假设**：牺牲 eviction 精度换吞吐，不会系统性驱逐热页导致 thrashing。
  - **可能失效场景**：高度局部性、极小 working set 反复访问同一页，粗粒度 LRU 可能次优。
  - **证据强度**：中——设计原则推导 + 多 workload 验证，但 hotness 误差未单独量化。
- **假设 1**：专用少量 evictor 线程 + 禁止 sync fallback 可维持稳定 free page 供应。
  - **证据强度**：强——batch 与 latency-critical 应用均改善。

## 核心方法

三原则：**always-asynchronous decoupling**（eviction  offload 到专用线程池，fault-in 不阻塞）、**cross-batch pipelining**（跨 batch 重叠 eviction 阶段）、**scalability prioritization**（per-CPU sharding，牺牲精确 hotness）。

实现 MageLnx（Linux）和 MageLib（LibOS），共享设计哲学。

## 设计取舍

- **取舍 1**：eviction 精度 ↓，多核吞吐 ↑；可能增加 remote access 比例。
- **取舍 2**：LibOS 路径更低 fault 开销，但牺牲 kernel 通用性。
- **边界条件**：RDMA 后端、page-based 语义；CXL 字节可寻址等新模式需重新评估。

## 实验与结果

- GapBS/XSBench 48 线程：10% offload 下 Hermit 降 73–75%，Mage 接近 ideal
- Batch 应用吞吐 **1.2–4.2×** vs Hermit/DiLOS
- memcached P99 延迟降 **50.2–94.5%**
- BSP 阶段切换时避免 ~99% 临时性能崩塌

## Critical Analysis

### 论证链条

ideal baseline 建模 → 三瓶颈归因 → 三原则 → 双实现，论证清晰。Fig. 1 对 datacenter operator 的 SLO tradeoff 图示有实践价值。

### 假设压力测试

- CXL 内存池、压缩 swap 等非 RDMA 后端是否同样受益未验证。
- 单 job 极大 working set 时专用 evictor 数量如何调参？论文未给 auto-tuning。
- 与 kernel THP、userfaultfd 等演进的关系未讨论。

### 实验可信度

Ideal analytical model 合理；多 workload（random/sequential/BSP/latency-critical）覆盖好。与 DiLOS LibOS 对比需注意实现成熟度差异。

### 系统性缺陷

论文未讨论：multi-tenant 隔离；remote memory 节点故障恢复；与 CXL 异构内存分层协同。

## 局限与 Future Work

- **局限 1**：聚焦 page-based RDMA，未覆盖 object-level far memory。
- **局限 2**：eviction 精度牺牲在特定 locality 下可能回退。
- **Future work 1**：自适应 evictor 线程数 + hotness 精度旋钮，按 workload 在线调节。

## 相关

- **相关概念**：far memory、[[RDMA]]、TLB shootdown、memory offloading
- **同类系统**：Hermit、DiLOS、Infiniswap
- **同会议**：[[SOSP-2025]]