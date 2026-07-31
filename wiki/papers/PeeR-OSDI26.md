---
type: paper
name: PeeR
full_title: "PeeR: First-Class Scheduling for Latency-Critical eBPF Applications"
authors: [Jeremy Carin, Ben Holmes, Weiyang Wang, Ankit Bhardwaj, Manya Ghobadi]
venue: OSDI
year: 2026
tags: [ebpf, scheduling, preemption, tail-latency, kernel]
source_pdf: "[[osdi26-carin.pdf]]"
source_md: "[[osdi26-carin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 延迟关键 eBPF 应用的一等调度（OSDI 2026）

> **原题**：PeeR: First-Class Scheduling for Latency-Critical eBPF Applications

> **一句话总结**：复杂 eBPF 已打破“softirq 程序短且均匀”的 fast-path 假设；PeeR 利用 verifier 在 helper boundary 保留的类型与资源状态实现 cooperative preemption，并通过 per-CPU worker 和 `sched_ext` 调度 continuation，使短请求 p99 降低 3×–19.8×，一次 yield/resume 代价 247 ns。

## 问题与动机

延迟关键 eBPF 通常从 XDP 等 I/O hook 在不可抢占 softirq 中 run-to-completion。这样免去 context switch，却让执行时间记到被 interrupt 的 userspace process 上，scheduler 看不见真实消费者；同一 receive queue 中的长 eBPF invocation 还会阻塞后续短请求。现代 key-value store、transport、storage 程序已经包含数千条 instruction、loop 和 data-dependent path，原本针对小 packet filter 的假设不再成立（表 1）。

Redis-KFlex 的 99.5% point/0.5% scan workload 中，200 μs scan 会阻塞 0.2 μs GET，默认 eBPF 的 GET p99 相对假想 5 μs preemption model 高 7.4×（图 1）。colocation 时 eBPF 还能在名义 50% allocation 下吃到 90% CPU。PeeR 的目标是让 eBPF invocation 成为可 accounting、budget、preempt 和 policy scheduling 的 task，同时保留短任务的 softirq fast path。

## 关键观察 / 隐含假设

- **观察 1**：verifier 只允许 eBPF 经 helper/kfunc 与 kernel 交互，并在调用点维护 register/stack type、lock、reference 与 liveness；这些边界是可验证的 cooperative yield point（§4–§6）。
  - **依赖假设**：程序足够 helper-dense。七个应用虽普遍如此，但 XRP 的 compute loop 可连续约 20 万 instructions 无 helper（表 1）。
  - **可能失效场景**：纯计算 loop 或长期持有 RCU pointer/spin lock 时，yield opportunity 稀疏甚至不存在。
- **观察 2**：短 invocation 可继续在 softirq 完成，只有超过 budget 的长 task 才需保存状态并转移到 worker；因此无需让所有请求承担 thread scheduling 成本（图 3）。
  - **依赖假设**：合适 budget 能把常见短请求留在 fast path，同时及时截断长请求。
  - **可能失效场景**：service-time 分布接近单峰或 task 普遍短于 quantum 时，调度收益很小；过小 budget 会因频繁切换降吞吐。
- **假设 1**：hook context 可以延长生命周期，并能在另一 execution context 中重建。
  - **证据强度**：中；论文完整实现 XDP packet frame retention，只审计其他 hook 的适用性。
- **假设 2**：允许 invocation interleaving 不会破坏应用语义，或开发者会显式同步共享状态。
  - **证据强度**：弱到中；PeeR 保证 memory/hook safety，但不保留原 softirq run-to-completion 的逻辑原子性（§6）。

## 核心方法

PeeR 修改 eBPF JIT，在 verifier 判定安全的 helper site 前插入 per-CPU budget flag check。未超时只多 1–2 cycles；超时则进入 site-specific stub，保存 11 registers、512-byte BPF stack、hook context 与 `site_id`，返回 softirq。XDP packet 被转成有 reference count 的 `xdp_frame`，避免 NAPI poll 结束后 buffer 失效（§5.1）。

yielded task 进入 per-CPU continuation buffer，由本 CPU 的 PeeR-kthread 恢复。因为 worker stack/context 地址不同，PeeR 导出 verifier 在每个 site 的 `PTR_TO_STACK`/`PTR_TO_CTX` 类型，按 old/new base 重定位保存的 pointer；每个 site 的 `endbr64` trampoline 使间接跳转满足 CFI，且从 helper call 本身恢复，避免重复或漏掉 side effect（§5.2、图 6）。

PeeR 不在 RCU-protected pointer 或 BPF lock 活跃时插 yield check。它结合 verifier type 和 liveness 判断 pointer 是否已 dead；这保护 memory safety，但减少部分程序的 preemption point（§5.3）。更深层的语义变化是：后续 invocation 可在先前 task yield 时访问共享 map，应用若依赖 run-to-completion atomicity 必须加同步。

调度分两层：外层 `sched_ext` 把 PeeR-kthread 当普通 kernel thread，控制所有 slow-path eBPF 的 aggregate CPU share；内层 per-kthread micro-scheduler 用 priority queue 排 FIFO、SRPT 或 WRR continuation。softirq 与 worker 的 runtime event 都回报 scheduler；默认 5 μs quantum 通过 per-CPU epoch 让 helper check 判断是否 yield（§7）。

## 设计取舍

- **cooperative safety 换抢占粒度**：只在 verifier-safe helper boundary yield，避免 arbitrary interrupt 的状态不一致，却无法截断 helper-free compute region。
- **fast path 换混合运行时复杂度**：短 task 保持 softirq 低开销，长 task 需要 packet ownership、state save、pointer patch、CFI trampoline 与 worker lifecycle。
- **短请求延迟换长请求 deep tail**：Redis 近饱和时 SCAN p99.9 达 baseline 的 2.3×，TPC-C StockLevel p99.9 高 1.5–1.7×（§8.1.2）。
- **per-CPU 简单性换负载均衡**：continuation 不迁核，避免 context/ownership 问题，但热点 NIC queue 对应的 CPU 无法借用其他 CPU。
- **边界条件**：XDP 是完整实现目标；其他 hook 必须逐一验证 context lifetime 与 deferred verdict semantics。

## 实验与结果

- 两台 28-core Xeon Gold 5420+、256 GB、ConnectX-7 400 Gbps，Ubuntu 24.04/Linux 6.16；Redis 99.5% GET/0.5% SCAN 下 PeeR 相对默认 eBPF 将 GET p99 降低 19.8×，相对 userspace KeyDB 吞吐高 3.77×，且相对默认 eBPF吞吐高 10.3%（图 8）。
- Memcached 50/50 GET/SCAN 下，PeeR 将 GET p99 相对默认 eBPF 降低 4.5×；KFlex 两种配置相对 userspace 吞吐均高 3.46×（图 8）。
- TPC-C-derived XDP workload 在 300 krps 下，SRPT 相对 baseline eBPF 将 mean latency 降低 3×；短 Payment 持续受益，但长 StockLevel 在高负载付出 deep-tail 代价（图 9/10）。
- 50/50 colocation 下，默认 BMC 使 batch throughput 只剩 fair share 的 30.9%，默认 Memcached 使 batch CPU 降至 7%；PeeR 维持配置份额。Redis-KFlex 的 batch target 从 0%–75% 变化时，PeeR 跟踪误差在 6% 内（图 11）。
- 一次 preemption/resumption 平均 247 ns：yield 77 ns，worker activation/dispatch/restore 170 ns；测量超过一百万次（图 12）。always-on helper check 是 1 cycle，scheduler 写 flag 时 2 cycles（§8.3）。
- 5 μs echo request 下，500 ns budget 峰值 275 krps，10 μs budget 匹配 no-preemption 的 330 krps；95% 0.5 μs/5% 100 μs workload 中，2 μs budget 的短请求 p99 最低 31 μs，而 500 ns–1 μs 为 110–190 μs、200 μs budget 为 565 μs（图 13/14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 现代 eBPF 已破坏短且均匀的 fast-path assumption | 表 1、图 1/2 | 七个应用；Redis-KFlex synthetic mixed workload | 强 |
| helper boundary 可实现低成本安全抢占 | §5、图 12 | XDP、x86、Linux 6.16；247 ns cycle | 强 |
| PeeR 显著改善 bimodal workload 的短请求 p99 | 图 8–10 | Redis/Memcached/TPC-C-derived workload、单一 28-core server | 强 |
| PeeR 能执行跨 eBPF/userspace 的 CPU policy | 图 11 | 三种 eBPF app 与一个 compute-bound batch job | 强 |
| 合适 quantum 存在但依赖 workload | 图 13/14 | echo server 与 95/5 synthetic service-time mix | 强 |

## 批判性分析

### 论证链条

论文从现实程序 characterization 到 head-of-line blocking/accounting，再把 verifier helper invariant 映射为 yield point，链条扎实。它清楚地区分 memory safety 与 application-level atomicity，也披露长请求 deep-tail 代价。较大的外推是把 XDP 实现称为通用 eBPF runtime 基础；hook context 能否延长、verdict 能否延期，需要逐 hook 工程与语义证明。

### 假设压力测试

helper-free loop 是 cooperative design 的根本盲点；论文在 XRP 已观察最长 compute gap，却没有端到端测试其 latency bound。另一个压力点是 task 固定原 CPU：RSS/queue skew、NIC flow imbalance 或不同 task service time 可令某个 worker backlog，即使系统其他核空闲。量子还是 workload-dependent，固定 5 μs 不是普遍安全默认值。

### 实验可信度

评测涵盖 Redis、Memcached、TPC-C-derived mix、colocation、三种 policy 与 microbenchmark，且公开长请求退化，证据质量高。不过 TPC-C 是 echo server 按 transaction profile spin，并非真实数据库路径；只用一个 server CPU/NIC 平台，缺乏 kernel version/hardware replication。p99 改善很强，但生产关注的 p99.9 已显示代价，未给综合 SLO optimization。

### 系统性缺陷

约 5000 LOC kernel/JIT/scheduler modification 扩大可信计算基与升级维护面。userspace daemon 异步汇总 runtime event 可能形成 accounting lag；论文未量化 event loss、daemon failure、worker crash、continuation buffer exhaustion 与 overload backpressure。preemption 改变共享 map interleaving，现有看似正确的 XDP 程序可能出现新 race，这一兼容风险可能比运行时 overhead 更关键。

## 局限与后续工作

- **局限 1**：只完整实现 XDP；其他 hook 的 context retention、sleepability 与 deferred result 未经端到端验证。
- **局限 2**：纯 cooperative preemption 无法约束 helper-free compute loop 的最长 blocking time。
- **局限 3**：continuation 不迁核，缺乏跨 CPU work stealing 和 overload isolation。
- **后续工作 1**：对表 1 所有应用测量“最长 verifier-safe gap”的 p99/p99.9，并加入 compiler-inserted safe poll 或 hybrid timer fallback，比较 safety proof 与 overhead。
- **后续工作 2**：以真实 TPC-C/transactional eBPF 程序验证 shared-state interleaving，结合 race detector 统计迁移前后新增 data race。
- **后续工作 3**：在 skewed RSS、多 queue 与 overload 下比较 fixed-CPU、[[NUMA|NUMA]]-local stealing 和 global stealing的 short/long p99.9、公平性与 cache cost。

## 相关

- **相关概念**：[[eBPF]]、[[Cooperative-Preemption]]、[[Tail-Latency]]、[[sched-ext]]、[[RCU]]
- **同类系统**：[[Shinjuku]]、[[Shenango]]、[[KFlex]]、[[SchedBPF]]
- **同会议**：[[OSDI-2026]]
