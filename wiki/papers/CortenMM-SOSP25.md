---
type: paper
name: CortenMM
full_title: "CortenMM: Efficient Memory Management with Strong Correctness Guarantees"
authors: [Junyang Zhang, Xiangcan Xu, Yonghao Zou, Zhe Tang, Xinyi Wan, et al.]
venue: SOSP
year: 2025
tags: [virtual-memory, formal-verification, concurrency, operating-systems, scalability]
source_pdf: "[[3731569.3764836.pdf]]"
source_md: "[[3731569.3764836]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# CortenMM: Efficient Memory Management with Strong Correctness Guarantees (SOSP 2025)

> **一句话总结**：Linux 等 OS 用 VMA 树 + 页表双层抽象同步复杂且易并发 bug；CortenMM 在 x86/ARM/RISC-V 上 **eliminate software-level abstraction**，用 transactional MMU 接口 + 可验证锁协议，formally verified 实现比 Linux 快 1.2–26×。

## 问题与动机

[[Linux]] MM 在 multicore 上仍是瓶颈（Android startup 等），且优化常引入 subtle concurrency CVE。根因：SunOS 1986 以来 **software-level abstraction**（VMA 树）与 **hardware page table** 两套结构需持续同步——可移植历史产物，但主流 ISA 已统一 multi-level radix page table，差异可用 C macro 隐藏。

CortenMM 问：能否单层 MMU 编程 + 强正确性证明，同时 beat Linux 性能？

## 关键观察 / 隐含假设

- **观察 1**：x86/ARM/RISC-V 页表格式趋同，software-level VMA 树主要带来同步开销与 bug 面，而非必要表达能力。
  - **依赖假设**：advanced semantics（demand paging、COW）所需额外状态可存 per-page auxiliary region，无需第二棵树。
  - **可能失效场景**：非主流 MMU（segment、hashed PT）需另设计——论文 scope 明确主流 ISA。
- **观察 2**：消除第二层后，可用 **transactional interface + scalable locking** 直接编程 MMU， contention 更低。
  - **依赖假设**：锁协议可形式化验证且验证成本可控。
  - **证据强度**：强。有 verification + 1.2–26× benchmark。
- **观察 3**：单层设计使 concurrent MMU 操作 correctness 可完整 formal verify（basic ops + locking protocols）。
  - **依赖假设**：验证工具链与 Ant Group 生产 OS 路线可长期维护 proofs。
  - **可能失效场景**：新语义（如新 TEE mapping API）需扩展 proof 库，成本未知。

## 核心方法

- **One-level design**：直接操作 page table；per-page auxiliary metadata 支持 on-demand paging/COW 等。
- **Transactional MMU API**：scalable locking protocols 减少 cross-layer 锁。
- **Formal verification**：并发 MMU 基本操作与锁协议 correctness（非全 OS verify）。
- **Production-oriented**：面向替代 Linux 的新 OS 栈（TEE、数据中心、移动）。

## 设计取舍

- **Clean-slate vs incremental Linux patch**：性能与证明简洁，但生态迁移成本巨大。
- **Verified subset vs entire MM subsystem**：强保证范围需读者核对 proof scope。
- **Drop VMA tree vs 丢失部分 Linux 语义便利性**：某些 procfs/status 遍历路径可能需重做。

## 实验与结果

- Multicore mmap/munmap/page fault microbench：显著优于 Linux 与其他 academic MM（Fig.1）。
- Real-world applications：**1.2×–26×** vs Linux。
- Formally verified concurrent code（论文 claim）。
- 单线程 16KB microbenchmark 中，相比 Linux，四项 MM operation 快 7.8–46.8%，mmap 慢 3.1%；边界是 Ubuntu 22.04 上的 AMD EPYC VM（§6.2，Fig. 13）。
- 384-core low-contention benchmark 中，相比 Linux 为 33–2270×；该 metric 只覆盖 disjoint-region synthetic workload，高 contention 在 64 thread 后停止扩展（§6.3，Fig. 14）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| MMU core 的关键性质经形式化证明 | 证明 non-overlapping mutual exclusion、query/map/mark/unmap correctness 和 page-table well-formedness（§5，Fig. 10–12） | Verus MMU-facing core；信任 hardware、Verus/SMT 与 allocator/DMA/lock/RCU | high |
| CortenMMadv 在多数单线程微基准提升吞吐 | 四项比 Linux 高 7.8–46.8%，mmap 慢 3.1%（§6.2，Fig. 13） | 16KB microbenchmark、Ubuntu 22.04、EPYC VM | high |
| 低争用下具有高核数扩展性 | 384 core 时为 Linux 的 33–2270×（§6.3，Fig. 14） | synthetic disjoint-region benchmark；高争用在 64 thread 后不再扩展 | high |
| 真实 MM-intensive workload 有收益 | metis 384 core 为 26×，JVM thread creation 快 32%（§6.4，Fig. 16） | 1.6 GB text、RadixVM-style chunk；不代表一般应用 | high |
| proof 有明确规模与信任边界 | 5.2:1 proof/code LOC、约 8 person-month、Verus 少于 20 s（§6.6，Table 4） | separately ported proof，不含 unproven OS dependencies | high |

## Critical Analysis

### 论证链条

「双层抽象是瓶颈根因 → 单层 + transactional API → 性能 + proof」逻辑清晰。从 microbench 到 full Android 兼容生产的路径仍长——论文是 larger OS effort 一环。

### 假设压力测试

- 26× 峰值可能来自特定 pathology Linux 已部分 upstream fix——需看 workload 是否 cherry-pick。
- Proof 与 hand-written unsafe assembly MMU flush 交互是否完全覆盖——trust boundary 需查附录。
- 仅 MM 子系统 verified，file system/network 仍可能有 bug 危及 security。

### 实验可信度

- vs Linux 与 academic baselines 公平性较好；26× 需读具体 app（可能是 mmap-heavy）。
- 独立第三方 re-verify 尚未广泛报道（新论文）。

### 系统性缺陷

- 论文未讨论 NUMA、THP、huge page、userfaultfd 等 Linux 高级特性 parity。
- 迁移现有 Linux workload 的 binary compatibility 未讨论。
- verified code 的性能 tuning 是否受 proof 约束——可能限制 hand optimization。

## 局限与 Future Work

- **局限**：新 OS 栈；proof 范围有限；Linux 特性 parity 未完成。
- **Future work**：扩展 verified semantics；Linux 渐进式 port 实验；NUMA/huge page。

## 相关

- **相关概念**：[[Virtual-Memory]]、Page-Table、Formal-Verification、[[Linux]]、COW
- **同类系统**：Linux MM、seL4 VM、BVML/类似 academic MM
- **同会议**：[[SOSP-2025]]
