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
last_reviewed: 2026-08-14
---

# FARLock：兼顾本地快速路径与先到先得的 RDMA 锁（OSDI 2026）

> **原题**：FARLock: Asymmetric RDMA Locking Made Fair

> **一句话总结**：传统公平 RDMA lock 让本地请求也绕回 RNIC，非对称的 ALock 虽省掉 loopback，却因 local/remote 两队列重排请求并频繁跨节点 handover；FARLock 让两队列先排队、再由队首借助 Peterson lock 领取全局 ticket，以 ticket 顺序提交，在 10-node high-contention microbenchmark 中把 local tail latency 最多降低 62×，替换 Sherman 的锁后把 update tail latency 最多降低 14×且保持近似吞吐。

## 问题与动机

[[RDMA]] one-sided CAS/FAA 由 RNIC 执行。它能与同一 RNIC 上的其他 RDMA atomic 保持原子性，却不保证与 host CPU 对同一内存位置的普通 access 原子。因此，经典的 RDMA MCS/ticket lock 即使服务本机 thread，也要让请求绕过本机 RNIC（loopback）。一次 local cache access 约 100 ns，RDMA 是 µs 级，这条本地路径很浪费（§1–§2.3）。

ALock 的思路是把 local requester 和 remote requester 放进两条独立 queue：local queue 用 CPU operation，remote queue 用 RDMA。但 lock 在两条 queue 间交替，不能按真实到达顺序服务。论文让 12 个 local request 先到、12 个 remote request 后到；ALock 仍交替执行，早到的最后几个 local request 反而等得最久（图 3a）。Thread 越多，processing order 与 arrival order 的偏差越大（图 3b）。这既破坏 first-come-first-served（FCFS），也增加跨节点 handover，抬高 tail latency。

FARLock 想同时满足两件事：local requester 全程不走 RNIC；所有 local/remote requester 仍按一个全局顺序拿锁。困难在于两条 queue、全局 ticket counter 和当前 ticket owner 分属不同位置，不能一次原子更新。若 ticket order 与各自 queue order 不一致，就需要在 queue 中搜索或重排，既慢又容易出错。

## 关键观察 / 隐含假设

- **观察 1：非对称锁的 tail 不只来自单次 RDMA，而来自重排和反复跨节点 handover。** ALock 优先 local、在两类间交替，remote/local tail 出现明显偏差；high contention 时偏差随 waiting request 数增加（§2.3、图 2–3）。
  - **设计含义**：只优化 local operation 不够，还要恢复两类请求间的全局顺序。
  - **可能失效场景**：若 contention 很低、queue 很短，reordering 几乎不存在，FARLock 额外 ticket/RDMA step 反而可能更贵；图 8 在多于 30 locks 后已经看到这一点。
- **观察 2：先 enqueue，再拿 ticket，可把复杂协调缩成两个队首。** 同类型 requester 已由 MCS-style FIFO queue 排序；每个 requester 等 predecessor 取得 ticket 后才继续，因此同一 queue 的 ticket 单调。最终只有 local head 和 remote head 会同时争 global ticket（§3–§4.2）。
  - **设计含义**：两方 mutual exclusion 可以使用只含 read/write 的 Peterson lock，不要求 CPU 与 RNIC 对同一 atomic word 共同原子。
- **观察 3：High contention 下，逐请求进入 Peterson lock 是重复工作。** 同类型的连续 waiter 已经排好顺序，可以组成 group，共用一个 ticket 和一次 Peterson critical section（§4.3）。
  - **边界**：Remote grouping 在节点增多时反而降低 throughput；作者推测 remote queue 被过快清空，增加 network bounce。最佳配置不是简单把两边 group 都调大（§5.4、图 11）。
- **假设 1：FCFS 是目标 workload 想要的 fairness。** FARLock 用 arrival/ticket order 消除任意插队。
  - **可能失效场景**：Deadline、priority 或长短 critical section 混合时，严格 FCFS 会形成 convoy，未必最小化 SLO miss。
- **假设 2：Requester 在 protocol 中不会失败。** Queue node、predecessor handshake、Peterson owner 和 ticket owner 都需要参与者继续执行。
  - **证据强度**：弱。论文明确把 node-failure handling 留作 future work；一个 dead queue head/holder 可能永久阻塞后继。
- **假设 3：CPU/RDMA read-write ordering 足以正确实现 Peterson lock。** 论文遵循已有 one-sided RDMA synchronization guideline，但没有形式化 memory-model proof 或跨 RNIC/CPU fault campaign。
  - **风险**：QP reset、reconnect、write visibility 或 queue-node reclamation 出错会破坏 safety/liveness。

## 核心方法

### 1. 两条 queue 加一个全局 ticket

每把 FARLock 有 `local_tail`、`remote_tail`，以及 Peterson lock 保护的 `next_ticket` 和 `ticket_owner`（§4.1、图 5）。每个 requester 自带 queue node，其中保存同类型 successor、ticket，以及 `proceed`、`qgrant`、`release` 等 handshake bit。

Local requester 对本机 lock metadata 用 CPU load/store；remote requester 对 lock host 用 one-sided RDMA。两类仍进不同 queue，所以 local path 不需要 loopback。全局 ticket 决定最终 grant 顺序，queue 只负责同类型内的排队与直接 handover。

### 2. Basic acquire：排队先于领号

Acquire 有三步（算法 1）：

1. 用 RDMA-aware `XCHG` 把自己的 queue node 接到对应 tail；若有 predecessor，就先建立 `next` link；
2. 读取 predecessor ticket，并用 `release/proceed` handshake 确保前驱的 ticket 已稳定、queue node 尚未被回收；只有 local/remote 两个 head 会进入 Peterson lock，原子地取得 `next_ticket++`；
3. 写入自己的 ticket，通知潜在 successor 可以继续；有 predecessor 时等 `qgrant`，最后等 `ticket_owner == my_ticket` 才进入 critical section。

关键 ordering invariant 是：对任意两个同类型 request，queue 中靠前者的 ticket 必须更小。先 enqueue、再沿 predecessor chain 领号，避免 queue/ticket 两套顺序分叉。两类 queue head 则由 Peterson lock 串行访问 counter，形成一个全局 ticket order（§3–§4.2）。

这里的“arrival”应理解为 protocol 能观察到的 enqueue/ticket serialization order，而不是不同机器上一个精确的全局 wall-clock order。对几乎同时到达的 local/remote head，谁先进入 Peterson lock 就先拿 ticket；论文没有定义跨机器物理到达时间的 tie-break。

### 3. Release 与直接 handover

Holder release 时先把 `ticket_owner` 改为自己的 ticket+1，唤醒下一个全局 owner（算法 2）。随后按 MCS 方式检查同类型 successor：若 CAS 能把 tail 从自己改成 null，说明无 successor，可直接返回；否则等待 successor 通过 `release` bit 确认已读取本节点的 ticket，再把 successor 的 `qgrant` 置 true。

Ticket owner 保持全局顺序，MCS handshake 保证同一 queue 的 node 不会过早复用。与单 queue MCS 相比，protocol state 更多；与 ALock 相比，跨 queue grant 不再靠固定交替或 batch budget。

### 4. 保持公平的 grouping

Fairness-preserving grouping 给 queue node 增加 `group_ticket` 和 `budget`（算法 3、图 6）。Group head 进入 Peterson lock 取得一个 ticket；同类型后继沿 queue 继承该 ticket，直到预算耗尽。中间 member 只等 queue-local `qgrant`，不再轮流读 central `ticket_owner`。组形成时由最后一个 member 释放 Peterson lock；这一组按 queue 顺序执行，最后一个 member 完成 critical section 后才推进 `ticket_owner`。

同组 request 原本在同一 FIFO queue 中连续等待，所以组内仍按 queue position handover。Lock 可分别配置 local/remote maximum group size。Figure 11 显示 local group size 5、remote size 1 的总 throughput 较好；扩大 remote group 会让 remote queue 更快耗尽，随后反而增加跨类 bounce。Grouping 是 workload-dependent optimization，不是越大越好。

### 5. 可选的 optimistic reader

论文还提出 reader extension（§4.4）：lock 增加独立 version，writer acquire/release 各加 1；reader 等 version 为偶数，读取数据后再次验证 version 未变，否则 retry。Reader 全程不写 local/RDMA metadata，因而路径很短。

作者明确承认这套 reader policy 在 reader/writer 间不公平，偏向 writer。Evaluation 主要比较 mutual-exclusion lock，没有给 reader-heavy/mixed workload 的 correctness、retry rate 或 tail latency；因此它是设计草案式 extension，不是 headline 结果已经验证的部分。

## 设计取舍

- **全局 FCFS 换掉调度自由。** 它消除 ALock 的任意插队，却不能让 urgent request 越过长 critical section。
- **双 queue+ticket 换掉 local loopback。** Local fast path 更快，但 lock/qnode metadata、handshake 和 memory ordering 比 MCS 更复杂。
- **Peterson read/write 换 CPU–RNIC atomic。** 只让两个 head 竞争很简洁；前提是跨设备 visibility 和 ordering 正确，且参与者不失败。
- **Grouping 换少量 fairness 粒度。** 同类 concurrent requester 共用 ticket，组内依 FIFO；参数过大可能让另一类等待，也可能因 queue 排空增加 bounce。
- **Optimistic read 换 writer preference。** Reader 不写 lock word，但冲突时要重读，且不再提供 reader/writer FCFS。
- **One-sided lock 换恢复难度。** Remote CPU 不参与 fast path；holder/head crash 后也没有一个天然 coordinator 清理 queue。

## 实验设计

Testbed 是 CloudLab Apt 的 10 台机器，每台双 Xeon E5-2650v2（16 cores）、64 GB DRAM、Mellanox FDR CX3 RNIC，InfiniBand FDR switch 提供 56 Gbps。所有 lock 放在一台 host；该机 12 threads 是 local requester，另外 9 台各 12 threads 是 remote requester。Lock 数从 1 增到 240；每个 thread uniform random 选 lock（§5.1）。

Local critical section 固定 300 cycles（约 100 ns），remote 固定 15,000 cycles（约 5 µs），用来模拟 CPU cache 与 RDMA 的 10–100× cost gap。这个设置使 local/remote service time 天生不同，也是 fairness 与 handover 结果的一部分。每项运行 20 s，只取中间 10 s，重复 3 次；报告 P95/P99/P99.9/P99.999 job latency，job 包含 acquire、critical section 和 release。三次 run 的 standard deviation 为 0.97%–14.88%，最大值出现在 P99.999。

Baseline 包含 RDMA 版 test-and-set（TS）、MCS、Ticket，以及 ALock/ALock batching。作者扫描 ALock batching 后选 local=20、remote=5 的最佳配置；FARLock 默认无 grouping，FARLock-G 默认 group size 5，再单独扫描 local/remote group 参数（表 1、§5.1）。没有 ShiftLock/DSLR 的实现对比，也没有 failure-aware lock baseline。

## 实验与结果

- **High contention 下 local tail 大幅下降。** 1–10 locks 时，FARLock local tail latency 相对公平 MCS/Ticket 最多低 62×，相对 ALock 低 8×，相对会 starvation 的 TS 低 55×–5,898×；remote latency 与 MCS 竞争性相近，通常优于 ALock，但 MCS 因指令更少也会在一些点更快（§5.2、图 7）。这些是不同 percentile/lock-count 中的最大倍数，不是所有配置的平均值。
- **公平顺序得到直接验证，低 contention 也暴露额外成本。** 12 local 后 12 remote 的 controlled arrival 中，FARLock 先完成全部 local 再完成 remote，最后一个 remote 等 135.30 µs；ALock 交替后，最后一个 local 最慢（图 9）。当 lock 多于 30、contention 降低时，FARLock 比 Ticket 多出的 RDMA operation 已能在 tail latency 中看见（§5.2、图 8）。
- **吞吐 headline 主要来自 local fast path。** FARLock local throughput 相对 MCS/TS/Ticket 最高高 891×；相对 ALock，在 1/10 locks 时高 11.9×/2×。MCS/Ticket 在 lock 数增大后可有更高 remote throughput，因为其 remote instruction path 更短（§5.3、图 10）。论文没有用一个 aggregate 倍数概括 total throughput，应避免把 891×理解为全系统 throughput。
- **Grouping 只对正确一侧有利。** 1 lock、2–10 nodes 中，local grouping 提高 local/total throughput；remote grouping 随节点增多会降低 remote 和 total throughput。Local=5、remote=1 的配置较好，并保持与不 grouping 相近的 tail latency（§5.4、图 11）。这是重要负结果：group size 需要随 arrival composition 调整。
- **Sherman update workload 保持吞吐并降低 tail。** 10-node deployment 中，一台同时作为 memory/compute server，40 GB shared memory；每 compute server 有 500 MB cache，预装 800M 个 8-byte key/value。Random update 下，相对 Sherman 原锁，FARLock 的 local tail 在 uniform/Zipf `θ=0.99` 分别低 11×–14×/3.6×–11×，remote 低 1.7×–6×/1.8×–3.5×，throughput 近似不变（§6、图 12）。这验证的是 write-heavy update，不代表 read-heavy query 或 transaction workload。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 两条 asymmetric queue 可以按全局 ticket 顺序公平 handover | §3–§4、算法 1–3；图 9 controlled arrival | 无 failure；跨类型同时 arrival 由 Peterson serialization 定序；无形式化 proof | 中到强 |
| 去掉 local loopback 并消除 reorder 可降低 high-contention tail | §5.2、图 7：相对公平 lock 最多 62×、ALock 最多 8× | 10 nodes、1–10 locks、固定 100 ns/5 µs critical section | 强 |
| Local fast path 提高 throughput | §5.3、图 10：local 最高 891×，对 ALock 为 11.9×/2× | 只指 local throughput；remote/total 没有同样倍数 | 强 |
| Grouping 能在保持 fairness 时减少 ticket overhead | §5.4、图 11：local grouping 增益，tail 近似 | 1 lock；remote grouping 反而退化，参数 workload-dependent | 中 |
| FARLock 可改善真实 RDMA index tail | §6、图 12：Sherman 最高 14×、throughput 相似 | Update-only、uniform/Zipf 0.99、单 memory server | 强 |

## 批判性分析

### 论证链条

论文先用 controlled arrival 证明 ALock 的问题确实是 reorder/bounce，再把设计拆成两层：MCS queue 保持同类型顺序，Peterson+ticket 给两类建立全序。Microbenchmark 同时比较公平但 loopback 的 MCS/Ticket，以及快速但不公平的 ALock；Sherman 替换实验再说明机制收益能传到 application tail，主线完整。

最大倍数需要分清来源。62× 是 local tail 对需要 RNIC loopback 的公平 lock，891× 是 local throughput，不是 total throughput；对更接近设计目标的 ALock，local throughput 是 11.9×/2×。Sherman 的 14× 来自原锁的 local-budget reshuffle，也不是对所有 RDMA index 的统一收益。

### 假设压力测试

“严格 arrival order”在分布式系统中需要一个可观测定义。同一 queue 有明确 XCHG order；跨 local/remote queue 则由两个 head 取得 Peterson lock 的先后生成 ticket。对明显先后到达的 Figure 9 workload，结果是 FCFS；对几乎同时到达、network delay 不同的 request，论文没有给 global-clock definition 或 linearization proof。更准确的结论是严格遵循 protocol 产生的 ticket order。

FCFS 也不总等于更好 SLO。一个长 remote critical section 可阻塞后面大量短 local request；priority、deadline 和 reader workload 可能主动需要 reorder。论文的 local/remote critical section 是固定 100 ns/5 µs，未扫描 heavy-tail service time，因此没有覆盖 convoy cost。

### 实验可信度

P95 到 P99.999、多 contention level、controlled arrival、tuned ALock、机制参数扫描和 Sherman 集成，覆盖面很好。作者还披露 extreme-tail 三次 run 的最大 standard deviation 14.88%，让结果更可审计。

外部有效性较窄：56 Gbps FDR/CX3 与现代 200/400 Gbps RNIC 有代差；所有 lock 集中在一台 server，local:remote thread 是 12:108；critical section 固定 busy-wait。Sherman 只做 random update，一台 memory server 也同时是 compute server。没有多 lock transaction、read/write mix、lock sharding/migration、network congestion 或 rack-scale test。

### 系统性缺陷

Failure handling 是最严重缺口。Acquire 会等 predecessor ticket、`qgrant`、Peterson lock 和 `ticket_owner`；holder、queue head 或中间 group member crash，都可能让整条 queue 永久停住。Related work 明确说 ShiftLock 已处理 node failure，而 FARLock 把它留作 future work。没有 lease/fencing，直接跳过 dead owner 又可能让两个 holder 同时进入 critical section。

实现还要处理 queue-node lifetime、ABA、ticket wraparound、QP reset、reconnect 和 lock host migration。论文没有 formal model、model checking 或 fault injection。Optimistic reader 只在设计章节出现，且本身偏向 writer；把它描述成已验证的 fair reader-writer lock 会超过证据。

## 局限与后续工作

- **局限 1**：没有 requester/holder/host failure protocol；单个 stale queue node 可能破坏 liveness。
- **局限 2**：Fairness 的跨机器 arrival linearization 没有形式化定义或 proof，主要靠算法说明与 controlled experiment。
- **局限 3**：固定 local/remote critical-section time 未覆盖 heavy-tail、priority、deadline 和 convoy。
- **局限 4**：所有 lock 位于一台旧 FDR node；没有 lock sharding/migration、现代 RNIC 或 network congestion。
- **局限 5**：Sherman 只测 update，reader extension 没有实测；不能外推到 reader-heavy transaction。
- **局限 6**：Grouping 对 remote side 有负收益，需要 workload-specific local/remote 参数。
- **后续工作 1**：设计 lease+fencing 或可验证 queue repair，并注入 holder/head/group-member crash、QP reset、partition 和 reconnect，报告 safety、recovery time 与 blocked request 数。
- **后续工作 2**：明确 enqueue/ticket/grant 的 linearization point，用 model checker 检查 CPU/RNIC weak ordering、simultaneous head、node failure 和 ticket wraparound。
- **后续工作 3**：扫描 critical-section mean/tail、local:remote ratio、priority/deadline，比较 FCFS、ALock 和 deadline-aware policy 的 throughput、P99.999 与 SLO miss。
- **后续工作 4**：在线估计 queue length 与 bounce rate，动态选择 local/remote group size，并在 phase-changing trace 上验证 oscillation 和 fairness。
- **后续工作 5**：在 200/400 Gbps RNIC、多 lock server、read/write mix 和 multi-lock transaction 中复测；单独评估 optimistic reader retry/starvation。

## 相关

- **相关概念**：[[RDMA]]、distributed lock、MCS lock、ticket lock、FCFS fairness、Peterson lock
- **相关系统**：ALock、Sherman、DSLR、ShiftLock
- **同会议**：[[OSDI-2026]]
