---
type: paper
name: PeeR
full_title: "PeeR: First-Class Scheduling for Latency-Critical eBPF Applications"
authors: [Jeremy Carin, Ben Holmes, Weiyang Wang, Ankit Bhardwaj, Manya Ghobadi]
venue: OSDI
year: 2026
tags: [ebpf, xdp, preemption, scheduling, tail-latency, resource-isolation]
source_pdf: "[[osdi26-carin.pdf]]"
source_md: "[[osdi26-carin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向延迟关键 eBPF 应用的优先调度（OSDI 2026）

> **原题**：PeeR: First-Class Scheduling for Latency-Critical eBPF Applications

> **一句话总结**：现代 eBPF 程序的运行时间已不再短且均匀，软中断中的不可抢占执行会造成队头阻塞和 CPU 份额失真；PeeR 在 helper 边界插入协作式预算检查，把超预算调用保存为 continuation 并交给 sched_ext 管理，在 Redis-KFlex、Memcached 和 TPC-C 负载上将短请求 P99 延迟降低 3–19.8 倍，单次抢占-恢复开销为 247 ns。

## 问题与动机

eBPF 的 XDP 等快速路径把应用逻辑放进 Linux 内核，避免上下文切换和数据复制，适合微秒级网络与存储请求。早期 eBPF 程序通常很短，因此在 softirq 中按到达顺序运行、直到完成，代价可以接受。

论文的测量表明，这个“快速路径假设”已经失效。Redis-KFlex 的点查询和范围扫描可能相差约 500 倍；Cilium 的单个程序有 7,622 条指令和 233 个 helper 调用。长调用会阻塞后续短调用，而 softirq 中的 CPU 时间又不被调度器单独记账。共置场景下，Redis-KFlex 在只配置 50% CPU 份额时最多占用 90%，使其他任务饥饿（§3）。

PeeR 的目标是让一次 eBPF 调用成为可记账、可抢占、可按策略排序的任务，同时保留短任务直接在 softirq 执行的低延迟路径。

## 关键观察 / 隐含假设

- **观察 1：eBPF 的 helper 边界提供了可验证的安全检查点。** verifier 会在 helper 调用处跟踪寄存器、栈槽、锁和资源状态；非平凡程序又通常包含大量 helper 或 kfunc 调用（§3.1、§5）。
  - **依赖假设**：程序的 helper 间指令区间足够短，能够满足目标延迟；不会长期在无 helper 的计算循环中运行。
  - **可能失效场景**：XRP 一类扫描循环可在无 helper 的情况下重复约 2,000 次，最长 helper 间隔可能达到数百条指令，抢占粒度会变粗。
- **观察 2：不可抢占 FCFS 执行同时损害应用内尾延迟和应用间公平性。** Redis-KFlex 的混合点查/扫描负载中，短请求 P99 比可抢占模型高 7.4 倍；共置任务的 CPU 份额会被 XDP 隐形消耗（图 1、图 2）。
  - **依赖假设**：工作负载包含明显的短长请求混合，且 eBPF 程序是共置资源竞争中的主要 CPU 消耗者。
- **假设 1：hook 可以接受延迟返回结果。** XDP 必须保留数据包，调用方也不能要求在原始 softirq 调用中立即得到 verdict；论文只实现并验证了原生 XDP（§6）。证据强度：强，作者逐项审计了输入生命周期、结果延迟和调用方锁状态。
- **假设 2：eBPF 程序能够承受调用交错。** PeeR 可能让后来的调用先完成，因此依赖隐式原子性或 per-CPU 完成顺序的程序必须自行使用锁或其他同步。证据强度：强，论文明确列出该语义变化（§6）。

## 核心方法

PeeR 采用“softirq 快速路径 + 每 CPU worker 慢速路径”。调用开始时获得由 sched_ext 控制的预算。JIT 编译器在每个 helper 调用前插入轻量检查；预算未过期时只增加约一个 cycle，超预算时跳转到 yield stub，保存 11 个寄存器、512 字节栈和 hook 上下文（§4、§5.1）。

保存的 continuation 被放入每 CPU 缓冲区，并由 PeeR-kthread 恢复。上下文切换会改变栈和 hook 对象地址，直接恢复指针并不安全。PeeR 导出 verifier 在各 helper 边界记录的 `PTR_TO_STACK` 与 `PTR_TO_CTX` 类型，生成 patch descriptor，在恢复时按新栈基址和新上下文地址重定位指针；标量值不修改（图 6）。恢复入口使用每个 yield 点的 CFI 安全 trampoline，确保 helper 恰好执行一次（§5.2）。

RCU 指针、持有的锁或其他不可跨越上下文的资源仍然是限制。PeeR 只在 verifier 判断这些资源不再存活的 helper 边界插入检查；对 XDP 则把数据包转为独立持有、引用计数的 `xdp_frame`，以延长输入生命周期（§5.3、§6）。

调度分为两层。外层 sched_ext 把 PeeR-kthread 当作普通内核线程，控制所有 eBPF 慢路径任务的总 CPU 份额；内层 micro-scheduler 在一个 worker 内决定 continuation 顺序。`enqueue()` 和 `requeue()` 可实现 FIFO、SRPT 或 weighted round-robin，并可使用应用提供的剩余工作量、流标识或权重提示（§7）。

## 设计取舍

- **协作式而非定时器抢占**：避免 timer interrupt 和任意中断带来的高开销与不安全状态，但抢占只能发生在安全的 helper 边界。
- **延迟短请求，推迟长请求**：SRPT 和小预算降低短请求尾延迟，却会增加长请求的深尾延迟；Redis 的 SCAN P99.9 在接近饱和时约为非抢占基线的 2.3 倍（§8.1.2）。
- **每 CPU continuation**：保持原始 CPU 归属，简化状态和缓存处理，但当前实现不支持跨 CPU 迁移，可能限制负载均衡。
- **外层与内层分层**：sched_ext 能做系统级资源隔离，micro-scheduler 能做请求级排序；代价是记账事件经 userspace daemon 异步聚合，策略链路引入额外组件。

## 实验与结果

- Redis-KFlex 在 99.5% GET（约 0.2 µs）、0.5% SCAN（约 200 µs）负载下，PeeR 将 GET P99 比默认 eBPF 降低 19.8 倍，吞吐比 userspace KeyDB 高 3.77 倍；PeeR 吞吐比默认 eBPF 高 10.3%（图 8）。
- Memcached 的 50% GET、50% SCAN 负载中，KFlex 两种配置吞吐均约为 userspace 的 3.46 倍；PeeR 将 GET P99 降低 4.5 倍，但整体吞吐略低于无抢占 eBPF（图 8）。
- 模拟 TPC-C 的 XDP echo server 中，SRPT 在 300 krps 时将平均延迟比基线 eBPF 降低 3 倍；短 Payment 请求在各负载下受益，长 StockLevel 请求在超过 300 krps 后才明显受影响（图 9、图 10）。
- 共置调度中，PeeR 能让 batch 任务保持目标 CPU 份额；Redis-KFlex 的目标份额从 0% 到 75% 变化时，实际值误差不超过 6%，而默认 eBPF 的份额取决于其剩余 CPU（图 11）。
- 抢占成本为 77 ns，恢复成本为 170 ns，总计 247 ns。每个 helper 的常态检查开销约 1 cycle；对 5 µs echo 请求，10 µs 预算可达到无抢占基线吞吐 330 krps（图 12、图 13）。
- 预算存在工作负载依赖的 U 型权衡：95% 的 0.5 µs 短请求和 5% 的 100 µs 长请求下，2 µs 预算达到约 31 µs 的短请求 P99；200 µs 预算则升至 565 µs（图 14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 不可抢占 eBPF 会放大短请求尾延迟 | 混合 GET/SCAN 的 P99，图 1、图 8 | Redis-KFlex、KFlex，XDP，双机 28-core Xeon | 强 |
| helper 边界上的协作式抢占能安全恢复程序 | verifier 类型重定位、RCU 与 hook 审计，§5–§6；247 ns，图 12 | 只实现原生 XDP；其他 hook 为设计时分类 | 中 |
| PeeR 能同时提供应用内排序和应用间 CPU 隔离 | SRPT 图 9；份额误差图 11 | sched_ext/scx_layered，固定每 CPU worker，不含迁移 | 强 |
| PeeR 的收益来自可调的抢占粒度，而非免费优化 | 预算扫描图 13、图 14；长请求深尾代价 §8.1.2 | 合成 echo 与特定 Redis/Memcached 混合负载 | 强 |

## 批判性分析

### 论证链条

论文的链条基本闭合：复杂程序和重尾执行打破快速路径假设；helper 边界提供安全检查点；continuation 与类型重定位支持跨上下文恢复；两层调度分别解决系统级份额和请求级排序。实验覆盖了应用内队头阻塞、应用间公平性和微基准开销。

仍有一个外推缺口。安全恢复依赖 hook 级审计，而不是 verifier 单独保证。论文验证的是 XDP，不能直接把结果推广到 tc、存储 hook 或需要立即返回结果的 hook。

### 假设压力测试

无 helper 的长计算循环会扩大最坏抢占延迟；论文给出的 XRP 扫描例子已经说明该风险。固定每 CPU 执行且不迁移，在 NIC 流量分布不均或某些 key 热点集中时可能导致局部队列拥塞。应用还必须接受 eBPF 调用交错；对于依赖隐式 per-CPU 原子性的旧程序，启用 PeeR 可能改变语义。

### 实验可信度

Redis、Memcached、TPC-C 事务时长和共置 batch 场景覆盖了短长混合与资源竞争，但部分 TPC-C 负载由固定 spin 时长模拟，并非完整数据库执行。基线包含 userspace、cpumap 和默认 eBPF，能够区分内核执行优势与抢占机制收益。实验没有报告大规模多租户、跨 CPU 迁移、故障恢复或不同 CPU 代际下的结果。

### 系统性缺陷

PeeR 增加约 5,000 行 Linux 内核代码、JIT 元数据、每 CPU worker、异步记账 daemon 和 hook-specific 生命周期处理。论文未量化这些组件的运维与升级成本，也未展示 worker 故障、进程退出、数据包异常路径或内存压力下 continuation 的恢复策略。sched_ext 以毫秒级外层调度配合微秒级内层调度，份额反馈依赖异步事件，突发负载下的控制延迟仍需测量。

## 局限与后续工作

- **局限 1**：当前实现只支持原生 XDP；其他 hook 需要重新证明输入生命周期、延迟结果和调用方锁状态满足条件。
- **局限 2**：纯协作式抢占无法处理 helper 间隔过长的程序；混合式定时器兜底或更密集的循环检查是待评估方向。
- **局限 3**：PeeR 改变了完成顺序和共享状态可见性；程序需要显式同步，论文没有给出现有应用迁移成本。
- **后续工作 1**：在真实生产 trace 上测量 helper 间隔、请求重尾和预算自适应策略，并报告 P99.9/P99.99 与 CPU 份额收敛时间。
- **后续工作 2**：扩展到 tc、LWT、netfilter 和睡眠式存储路径，逐个验证 continuation 的输入与结果生命周期；论文 §9 提到未来可支持等待磁盘 I/O 的工作负载。

## 相关

- **相关概念**：[[eBPF]]、[[XDP]]、[[sched_ext]]、[[Preemption]]、[[Tail-Latency]]
- **同类系统**：[[KFlex]]、[[DINT]]、[[eTran]]、[[XRP]]、[[cpumap]]、[[Shinjuku]]、[[TinyQuanta]]
- **同会议**：[[OSDI-2026]]
