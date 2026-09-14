---
type: paper
name: SBB
full_title: SBB: Eliminating Centralized Bottlenecks in Userspace Network Runtime
authors: [Kang Hu, Shuqi Dong, Chuandong Li, Ran Yi, Zonghao Zhang, et al.]
venue: OSDI
year: 2026
tags: [userspace-networking, scheduling, user-interrupt, load-balancing, cpu-sharing]
source_pdf: "[[osdi26-hu-kang.pdf]]"
source_md: "[[osdi26-hu-kang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-17
---

# 消除用户态网络运行时集中式瓶颈的 SBB（OSDI 2026）

> **原题**：SBB: Eliminating Centralized Bottlenecks in Userspace Network Runtime

> **一句话总结**：SBB 观察到用户态网络运行时的 timer、monitor 和 dispatcher 随 worker 数量增长会成为瓶颈，于是利用 UINTR 提供每核 timer/NIC 通知，并用“任务窃取处理瞬时失衡、流迁移处理持续失衡”的两级策略，在 48 个 worker 上取得约 2.8× 扩展和相对既有系统 1.7×–5.2× 的吞吐收益。

## 问题与动机

微秒级网络服务同时需要三类调度：抢占长请求以避免队头阻塞，在延迟敏感任务与 best-effort 任务之间分配 CPU，以及把请求分散到多个 worker 以保持工作守恒。既有运行时通常为每类调度设置一个集中式 timer、monitor 或 dispatcher。它们在 worker 较少时简洁有效，但集中组件的处理速率、扫描成本或中断发送速率会限制整体扩展。

SBB 的目标是删除这些跨 worker 共享的调度组件，同时保留低尾延迟、CPU 共享和负载均衡。论文将问题拆成系统机制与调度策略两部分：UINTR 负责把 timer 和 NIC 事件直接送到用户态；负载均衡则需要识别 RSS 造成的瞬时与持续两类失衡。

## 关键观察 / 隐含假设

- **观察 1：集中式调度实体无法靠简单增加 dispatcher/monitor 核心来扩展。** Shinjuku 的集中式 timer 在超过 16 个 worker 后吞吐停止增长；集中式 dispatcher 的实测处理上限约为 5 MRPS，因为单包处理约 200 ns（图 3）。多个 dispatcher 又重新引入分组间失衡（图 3d）。
  - **依赖假设**：所有 worker 都需要频繁接受抢占、队列扫描或请求分发。
  - **可能失效场景**：请求率较低、worker 数量较少，或硬件 NIC 已经提供足够强的全局调度能力时，集中组件未必是主导瓶颈。
- **观察 2：RSS 造成的失衡同时包含瞬时失衡和持续失衡。** 单个 flow 的突发会造成短期拥塞；flow 数量或请求重量分布不均则会让某个 core 长期过载。任务窃取适合前者，却会在后者反复搬运同一批 flow 的请求，产生缓存一致性流量（图 4）。
  - **依赖假设**：NIC 支持 flow director，且持续过载的 flow 能够被识别和迁移。
  - **可能失效场景**：flow 极短、迁移规则安装成本占主导，或 NIC 的 flow 表容量不足时，流迁移收益会下降。
- **假设 1：NIC 与 LAPIC timer 的 UINTR 可以在用户态以足够低的成本使用。** 论文在 Intel E810 上测得 NIC UINTR 相对 polling 增加约 0.49 µs，timer 编程约 50 cycles（§6.5）。证据强度：强，但硬件覆盖有限。
- **假设 2：应用层处理时间的主要变异足以代表需要抢占的部分。** SBB 只在 application-layer execution 阶段启用 timer UINTR，并依赖网络栈其他阶段耗时相对稳定（§4.4）。证据强度：中；对复杂协议栈或不可预测的内核/设备操作仍需验证。

## 核心方法

SBB 为每个 worker 绑定一个 CPU core、独立的 Rx/Tx 队列、本地请求队列和本地 timer。NIC 通过 RSS 把 packet 放入某个 Rx queue；worker 直接从自己的队列接收和处理请求，不经过共享 dispatcher。该结构回应了观察 1，数据面不再受单一分发线程限制。

SBB 使用 UINTR 同时支持两类本地事件。NIC 队列到包时触发用户态通知；若 LC 线程当前不在运行，内核侧的 NIC handler 将其唤醒并触发调度，因此不需要集中式 monitor 轮询所有队列。处理每个 LC 请求前，worker 设置一次性 LAPIC timer；超时后由用户态 timer handler 保存请求上下文并把请求重新放入本地队列，实现自抢占。

由于 Intel UINTR 没有直接提供中断来源区分，SBB 将处理流程拆成 top half 与 bottom half，并让 NIC UINTR 与 timer UINTR 在不重叠的阶段启用。NIC 中断触发时只设置 pending flag；worker 随后批量取包、解析协议、执行应用逻辑和发送响应。NIC 的自动屏蔽能力避免高包率下的 interrupt storm（§4.4）。

负载均衡采用两级策略。worker 按接收轮次和水位线进入 Light、Busy、Overloaded 状态；Busy 表示暂时突发，stealer 从其队列窃取部分请求；Overloaded 表示持续过载，stealer 读取被发布的 flow 标识并写入 NIC flow-director 规则，把整个 flow 迁移到空闲 worker。这直接对应观察 2。

SBB 还优化任务窃取：队列前 16 项作为 owner-exclusive block，减少低负载锁操作；被窃取的请求直接处理，避免多次窃取；批量出队并使用 try-lock；stealer 从上轮成功窃取的 victim 开始扫描以利用局部性（§4.5.2）。

## 设计取舍

- **中断替代 polling**：获得了非运行 LC 任务的及时唤醒和 CPU 共享能力，但 NIC UINTR 比 polling 增加约 0.49 µs 延迟，并引入硬件、内核补丁和中断重臂逻辑。
- **流迁移替代持续任务窃取**：减少跨核队列访问和缓存一致性开销，但 flow-director 规则安装约需 10 µs，只适合持续失衡，不能替代短期窃取。
- **纯去中心化架构**：消除了单点调度瓶颈，但负载均衡仍需 worker 间同步。论文承认 48 核以后扩展变得次线性，主要原因正是任务窃取与流迁移的跨核通信成本（§7）。

## 实验与结果

- 在 Fixed(1)、50× 的 P99.9 slowdown SLO 下，16 worker 的 SBB 达到 9.7 MRPS，比 TQ、Concord 和 Shinjuku 高超过 90%（图 8a）。
- High-Bimodal 下吞吐达到 260 KRPS，比基线高超过 30%；Extreme-Bimodal 下吞吐提升超过 40%（图 8b–c）。
- RocksDB 的轻尾和重尾负载下，在相同 SLO 目标下吞吐比既有系统高 20%–80%（图 8d–e）。
- 与 Caladan 和 Caladan-DL 共置 Memcached、swaptions 时，p99.9 小于 100 µs 的 Memcached 吞吐分别高 28% 和 15%；swaptions 获得的 CPU 效率与 Caladan-DL 接近（图 9）。
- Fixed(1) 从 16 扩展到 32、48 worker 时吞吐约为 9.5、19、26.5 MRPS，即 2× 和 2.8×；高于 32 的部分收益受负载均衡同步开销影响（图 11a）。
- E810 上 NIC UINTR 相对 polling 增加 0.49 µs，仅占端到端 9 µs 链路延迟的 4.7%；传统 DPDK interrupt 的通知开销为 3.4 µs（图 12）。增强任务窃取使吞吐提高约 30%，混合策略进一步降低高负载下的窃取开销（图 13）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 集中式 timer/monitor/dispatcher 会限制多核扩展 | 图 3a–e；§2.3.2 | 代表性运行时、最多约数十 worker、特定 NUMA 机器 | 强 |
| UINTR 能以较低成本支持用户态抢占和 CPU 分配 | §4.2–§4.4、图 12、表 4 | Intel Sapphire Rapids、E810/ConnectX-5、定制 Linux | 中 |
| 两级策略能同时处理瞬时与持续失衡 | 图 4、§4.5、图 13 | RSS + flow director；合成负载为主 | 强 |
| SBB 在更多 worker 上保持吞吐增长 | 图 11a–d | 16–48 worker，双 NUMA，100 Gbps NIC | 中 |

## 批判性分析

### 论证链条

论文的链条基本闭合：图 3 先定位集中组件的瓶颈，UINTR 消除 timer/monitor 的集中控制，图 4 再解释单纯任务窃取为何不够，最后用 flow migration 补上持续失衡。SBB 的主要结果与这些组件的消融实验一致。

但“纯去中心化”并不等于没有全局协调。flow migration 仍需访问其他 worker 状态并修改 NIC 规则，任务窃取仍会产生锁和缓存一致性流量。因此，论文证明的是集中式瓶颈被推迟和分散，而不是调度协调成本消失。

### 假设压力测试

论文的 NIC UINTR 机制依赖特定 Intel UINTR 行为、可映射的 UPID 和自定义内核 handler。AMD、虚拟机、SR-IOV 或云 NIC 是否暴露同样能力，论文没有实测。flow migration 还依赖可编程 flow 表；大量短 flow、连接迁移或加密隧道可能使五元组规则不稳定。

SBB 在简化 TCP/UDP 栈上评估，并明确未实现拥塞控制。真实生产协议栈中的重传、拥塞反馈、TLS 和多级 RPC 可能改变“应用层是主要变异来源”的假设。论文使用合成服务时间与内存驻留 RocksDB，尚未覆盖存储阻塞或网络拥塞主导的 workload。

### 实验可信度

实验覆盖固定、重尾、RocksDB、Memcached 和 swaptions，并包含消融、共置和扩展性测试。对集中式 dispatcher 的瓶颈解释也有 200 ns/packet 的测量支撑。另一方面，不同基线使用不同 Linux 内核和 NIC；Caladan 甚至改用 ConnectX-5 以避免 E810 性能下降，这使跨系统比较更接近“各自最佳配置”，但也降低了严格同硬件比较的可比性。

### 系统性缺陷

SBB 需要 2,095 行 kernel patch、4,343 行 runtime，并要求应用实现三个 hook。论文未量化升级内核、故障恢复、规则表耗尽、流迁移失败、可观测性和多租户隔离成本。每个 worker 的本地状态降低了共享竞争，却可能增加状态收集和故障诊断难度。

## 局限与后续工作

- **局限 1**：48 个 worker 后仍出现次线性扩展，任务窃取和流迁移的跨核同步成为新瓶颈（§7）。
- **局限 2**：结论集中在 Intel Sapphire Rapids、E810/ConnectX-5 和定制 Linux；其他 CPU、NIC、虚拟化环境的 UINTR 可用性未验证。
- **局限 3**：协议栈缺少拥塞控制，实验请求主要是内存内处理，生产网络中的拥塞、重传和阻塞 I/O 可能改变调度收益。
- **后续工作 1**：在 64–128 个 worker、跨 NUMA 的真实 trace 上分别测量窃取、flow-rule 更新和缓存一致性流量，判断两级策略的扩展上限。
- **后续工作 2**：比较不同 NIC flow 表容量、规则安装延迟和短 flow churn 下的迁移收益，并设计迁移失败时的退化策略。
- **后续工作 3**：将 UINTR 与 DLB 或 SmartNIC 调度结合，测量硬件卸载能否降低 48 核后的同步成本。

## 相关

- **相关概念**：[[User Interrupt]]、[[Work Stealing]]、[[Receive Side Scaling]]、[[Tail Latency]]
- **同类系统**：[[Shinjuku]]、[[Caladan]]、[[Shenango]]、[[Skyloft]]、[[Concord]]
- **同会议**：[[OSDI-2026]]
