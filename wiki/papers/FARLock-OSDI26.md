---
type: paper
name: FARLock
full_title: "FARLock: Asymmetric RDMA Locking Made Fair"
authors: [Yuehao Hu, Jiatang Zhou, Tianzheng Wang, Keval Vora]
venue: OSDI
year: 2026
tags: [rdma, distributed-lock, fairness, tail-latency, indexing]
source_pdf: "[[osdi26-hu-yuehao.pdf]]"
source_md: "[[osdi26-hu-yuehao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 公平的 Asymmetric RDMA Lock（OSDI 2026）

> **原题**：FARLock: Asymmetric RDMA Locking Made Fair

> **一句话总结**：现有 fair RDMA lock 迫使 local request 走 RNIC loopback，而 asymmetric lock 分开 local/remote queue 后会乱序并放大 tail；FARLock 用全局 ticket、两条 MCS-style queue 与 Peterson 协调恢复严格 arrival order，在 10 节点上 local tail 最多降 62×，替换 Sherman 锁后 query tail 降最高 14×且吞吐不变。

## 问题与动机

RNIC atomic 与 host CPU access 之间不保证原子性，所以传统 fair MCS/ticket RDMA lock 连本机 requester 也必须 loopback RNIC，付出微秒而非约 100 ns local access。ALock 把 local/remote 分两条 queue 以利用 asymmetry，却按 queue 交替而不是全局 arrival order，早到 request 可被大量晚到 request 越过，产生尾延迟和 bias。

FARLock 的目标不是只防 starvation，而是严格 first-come-first-served，并继续让 local path 使用 CPU access。困难在于两条 queue 与全局 ticket 无法原子更新，若 queue order 与 ticket order 不一致，handover 需搜索/重排。

## 关键观察 / 隐含假设

- **观察 1**：high contention 下 asymmetric queue 的 reorder/bounce 而非单次 RDMA latency 会主导 P99.9/P99.999；arrival/processing 差异随 thread 增长（§2.3、图 2–3）。
  - **依赖假设**：FCFS 与 workload priority/SLO 对齐，critical-section service time 不应允许 intentional scheduling。
  - **可能失效场景**：priority/deadline lock、reader preference，或长短 critical section 混合时 FCFS convoy。
- **观察 2**：先 enqueue、再由两条 queue 的 head 竞争 ticket，可让各 queue position 与 ticket order 保持一致，mutual exclusion 仅缩为两个 head（§3–4）。
  - **依赖假设**：local/remote 各自 queue 已 FIFO，head failure/timeout 可恢复。
  - **可能失效场景**：requester crash 留在 queue、RDMA write visibility/order 异常或 network partition。
- **假设 1**：Peterson lock 的 read/write ordering 在 CPU/RDMA memory model 下经 barrier 后正确，不需要跨 RNIC/CPU atomic。
  - **证据强度**：中强。实现/实验支持，formal crash model 未充分展开。
- **假设 2**：一台 node host lock、local vs remote 二分类足够代表 distributed index placement。
  - **证据强度**：中。Sherman case 匹配，multi-owner/migration 更复杂。

## 核心方法

每把锁维护 local 与 remote MCS-style queue、global serving ticket，以及仅由两个 queue head 使用的 Peterson lock。request 先按类型 enqueue；只有成为 head 后才进入 Peterson critical section领取下一个 ticket。由于 enqueue 先于 ticket assignment，同类型内部 queue order 与 ticket order一致，两个 head 又被 Peterson 串行，最终形成全局 FCFS。

unlock 根据下一个 ticket 把 ownership 交给对应 queue head。local queue 操作和 ticket access尽量走 CPU，remote path 用 one-sided RDMA；避免所有 local request loopback，同时 ticket 而非交替 queue 决定跨类型顺序。

high contention 时，同类型连续 request 可组成 group：首个 head 只进入一次 Peterson lock，后继按 queue 顺序共享/连续取得 ticket，减少 network bounce 与 coordination。实验表明只 group local request、size 5 更合适；remote grouping 可能让 remote queue 过快排空、反而增加 bounce。论文另给 optimistic reader extension，以 version validation 减少 read-side roundtrip。

## 设计取舍

- **FCFS 换 policy flexibility**：消除 reorder tail，但无法越过长 critical section，priority workload 可能需要另一语义。
- **双 queue + ticket 换 loopback elimination**：local 快且公平，metadata/protocol 比单 MCS 更复杂。
- **grouping 换协调开销**：同类 burst 高效，group 大会延迟另一类；需按 local/remote 单独调参。
- **one-sided fast path**：少 remote CPU，requester crash/queue repair 的工程难度更高。

## 实验与结果

- 10 台 RDMA node，每 node 12 thread，1–240 lock 调 contention；remote critical section 15,000 cycles（约 5 µs），local 300 cycles（约 100 ns），每项 20 s、取中间 10 s并重复三次（§5.1）。
- 1–10 lock 高 contention 下，相对 fair MCS/Ticket，FARLock local tail latency 最多低 62×；相对 ALock 最多低 8×，相对 TS 低 55–5898×（§5.2、图 7）。
- local throughput 相对 MCS/TS/Ticket 最高 891×；相对 ALock 在 1/10 lock 下分别高 11.9×/2×（§5.3、图 10）。
- controlled arrival 中 FARLock 严格处理 12 local 后 12 remote，最大 wait 135.30 µs且低于 ALock；验证 latency 与 arrival order 对齐（§5.2、图 9）。
- Sherman 10-node、40 GB shared memory、每 compute node 500 MB cache、800M key-value 下，uniform/Zipfian local tail 分别改善 11–14×/3.6–11×，remote 改善 1.7–6×/1.8–3.5×，吞吐相似（§6、图 12）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| FARLock 同时保证 FCFS 与避免 local loopback | §3–4 ordering consistency protocol | 两类 queue、标准 RDMA ordering、无 crash 细化 | 强 |
| 公平性显著降低高 contention tail | §5.2、图 7：相对 fair lock 最多 62×、ALock 8× | 10 node、1–10 lock、设定 critical section | 强 |
| local fast path 提高吞吐 | §5.3、图 10：最高 891×，相对 ALock 11.9× | microbenchmark、单 lock host | 强 |
| 实际 RDMA index 获得 tail 收益 | §6、图 12：Sherman 最高 14×、吞吐相似 | update-only stress、uniform/Zipf 0.99 | 强 |

## 批判性分析

### 论证链条

论文将 ALock 的尾延迟明确归因于跨 queue reorder/bounce，再用 ticket 给两队列建立全序，microbenchmark 与 Sherman 都验证 tail 改善，链条闭合。极大 local throughput 倍数部分来自 fair baseline 被迫 loopback 的结构差异；更贴近实践的核心是相对 ALock 与 Sherman 的结果。

### 假设压力测试

FCFS 遇到长 critical section 会形成 convoy，严格公平不一定最小化 SLO violation；priority/deadline request 也不能插队。queue head crash 会阻塞同类甚至 global ticket，论文未给 lease/failure detector。remote grouping 的负结果说明机制对 arrival composition 敏感，production 比例变化需要 adaptation。

### 实验可信度

多 percentile、contention sweep、受控 arrival、强 baseline、应用集成和重复方差均较完整。限制是所有 lock 放一台 host、critical-section size 固定、Sherman 只 stress update；缺少 mixed read/write、multi-lock transaction、node failure 与 network congestion。P99.999 三次 run 的方差最高 14.88%，极尾倍数需谨慎。

### 系统性缺陷

双 queue/ticket/Peterson state 的 crash recovery、memory reclamation、ABA 与 reconnect 未充分讨论。one-sided requester 可能离线而保留 queue node；没有 coordinator 的安全清除较难。strict ticket 还会泄露 global serialization point，lock migration/resharding 时需转移完整 sequence state。

## 局限与后续工作

- **局限 1**：未实现/评测 crash-stale queue node 的恢复。
- **局限 2**：只支持 FCFS，不覆盖 priority/deadline 或 convoy mitigation。
- **局限 3**：单 lock-host topology 与 update-heavy Sherman 不能覆盖全部部署。
- **后续工作 1**：注入 requester/host crash、QP reset 和 packet loss，验证 queue repair、ticket continuity 与 bounded blocking。
- **后续工作 2**：在 mixed critical-section/priority workload 下比较 FCFS、ALock 与 deadline-aware extension 的 SLO miss/P99。
- **后续工作 3**：设计在线 local/remote group size controller，以 bounce rate 和 queue length 为输入，在 phase-changing trace 上验证稳定性。

## 相关

- **相关概念**：[[RDMA]]、[[Distributed-Lock]]、[[MCS-Lock]]、[[Fairness]]
- **同类系统**：[[ALock]]、[[Sherman]]、[[DSLR]]
- **同会议**：[[OSDI-2026]]
