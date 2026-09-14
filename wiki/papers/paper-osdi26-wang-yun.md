---
type: paper
name: mwait-sched
full_title: "What Are You (M)Waiting For: The Hidden Cost of Idle in the Hyperscale Cloud"
authors: [Yun Wang, Xingguo Jia, Ben Luo, Kenan Liu, Shengdong Dai, Jingdong Han, Weihao Chen, Yicheng Gu, Xingzi Yu, Yibin Shen, Jiesheng Wu, Zhengwei Qi, Haibing Guan]
venue: OSDI
year: 2026
tags: [virtualization, oversubscription, cpu-scheduling, idle-management, tail-latency]
source_pdf: "[[osdi26-wang-yun.pdf]]"
source_md: "[[osdi26-wang-yun]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-03
---

# 让空闲 vCPU 可调度：mwait-sched（OSDI 2026）

> **原题**：What Are You (M)Waiting For: The Hidden Cost of Idle in the Hyperscale Cloud

> **一句话总结**：mwait-passthrough 在 1:1 配置中以较少 VM exit 换取低唤醒延迟，却让共享 pCPU 上的空闲 vCPU 对 hypervisor 隐身；mwait-sched 用按工作负载调节的定时器仿真、稳定/瞬态空闲分类和多地址 mwait-proxy 恢复可见性，在 3.2M pCPU 的生产集群中把 oversubscription 从 1.0% 提高到 20.3%，同时将高争用 steal 事件降低超过 80%。

## 问题与动机

云平台把多个 vCPU 复用到较少的 pCPU 上，以提高利用率和可售容量。对延迟敏感服务而言，安全复用需要 hypervisor 知道某个 vCPU 何时真正空闲。传统 hlt 或 trapped mwait 能提供调度点，但每次空闲/唤醒都可能引起 VM exit；mwait-passthrough 则让 guest 直接进入硬件 C-state，减少退出并改善延迟。

论文指出，这两种目标在 oversubscription 下发生冲突。passthrough 的 vCPU 虽然在硬件层面等待，却仍被 host scheduler 视为 runnable，因而占住 pCPU；同一 pCPU 上的其他 vCPU 只能等待无关的 timer 或调度事件。生产集群中即使平均 CPU 利用率很低，steal time 仍可能超过 SLO 阈值，说明利用率不能作为安全复用的充分信号。

## 关键观察 / 隐含假设

- **观察 1：mwait-passthrough 的收益依赖独占 pCPU。** YCSB 测试中 passthrough 比 hlt 和 trapped mwait 的平均读写延迟低约 20%，并避免了超过 1.8M 次 idle-induced exits（图 3、表 1）；但与空闲 VM 共置时，mwait-nop 和 passthrough 都显著恶化延迟（图 4）。
  - **依赖假设**：guest 的 mwait 确实代表等待，且 pCPU 是否共享是可由 hypervisor 控制的。
  - **可能失效场景**：在真正 1:1 部署中，失去调度可见性的代价很小；在共享核上，低退出次数反而会掩盖争用。
- **观察 2：空闲时长近似分成瞬态和稳定两类。** 生产 eBPF 采样显示，忙 vCPU 的 99.6% mwait episode 在 200 µs 内结束，而空闲 vCPU 的 96.0% 超过 1 ms（图 12）。
  - **依赖假设**：不同 workload 的空闲间隔在部署期间仍保持可分离。
  - **可能失效场景**：突发流量、锁竞争或混合 workload 可能把间隔推入中间区域，使二元阈值不再可靠。
- **假设 1：Linux guest 的主要 mwait 唤醒信号是 `need_resched`。** proxy 通过比较监控地址的值而非捕获每一次 coherence 写入来判断唤醒；论文认为当前 idle 路径不会依赖同值写或短暂置位事件。
  - **证据强度**：中。论文分析了 Linux idle 路径并与 KVM 的 mwait-nop 行为比较，但没有覆盖任意 guest OS 或未来内核实现。

## 核心方法

**按 profile 选择的 timer-based emulation。** 对共享 pCPU 的 vCPU，hypervisor 用周期 timer 定期重新取得控制权，检查模拟的 mwait 状态并让出 pCPU。I/O 密集或同步密集 workload 使用约 20–50 µs 的短 slice，CPU 密集 workload 使用更长 slice；PMU 中的 IOPS/利用率比值用于分类。图 8 显示短 slice 对 Redis、MySQL、ZooKeeper 等延迟敏感负载更有利，而 super-pi 需要较长 slice；图 9 也显示过短 slice 会把 host CPU 利用率从约 8–10% 推到 50–60%。

**VM-wide wakeup。** 单独唤醒等待者会造成锁持有者仍被 deschedule 的 lock-holder preemption。mwait-sched 在检测到唤醒时，把同一 VM 中可能参与临界路径的 runnable vCPU 一并标为可运行。48-vCPU 压测中，标记所有 vCPU 的 hypervisor 成本约 20 µs；在 1.5 倍 oversubscription 下，全部实际上线的等待时间约 240 µs（图 11）。

**mwait-based aggregation。** 分类器只聚合 stable-idle vCPU，把 transient-idle vCPU 留在独立执行路径；一旦 vCPU 恢复活动便 de-aggregate。它用 guest 已经产生的 mwait 信号代替粗粒度 CPU 利用率或 run queue 采样，使稳定空闲成为可复用容量。

**多地址 mwait-proxy。** 在较高密度下，为每个 vCPU 安装 timer 会产生过多 VM 切换。proxy 把多个 monitored address 放入 hypervisor 链表，在每次 hypervisor entry 时统一扫描。它适用于 burst instance 的约 1:4 密度，但扫描成本随列表增长；1:6 和 1:8 时同步密集 workload 的 P99 已达到基线的约 10–16 倍（图 15）。

## 设计取舍

- **延迟与调度可见性**：passthrough 保留硬件低延迟，但破坏共享核调度；timer emulation 恢复可见性，却引入 slice 上界和 VM exit 开销。
- **简单 profile 与自适应复杂度**：作者选择 PMU 比值和离线阈值，而非在线机器学习或 guest instrumentation，降低了 hyperscale 运维成本，但分类器依赖 workload 类型稳定。
- **VM-wide wakeup 与过度唤醒**：唤醒整个 VM 可避免锁持有者被遗漏，却可能短时增加 runnable vCPU 数量。论文只测量了标记和上 CPU 延迟，未完整评估更大规模 VM 的调度压力。
- **软件多地址监控与扩展性**：proxy 避免每个 vCPU 的 timer，但 hypervisor entry 的链表扫描是线性成本；作者因此提出需要硬件级 vectorized monitor。

## 实验与结果

- 2 vCPU:1 pCPU 的九类 workload 中，mwait-sched 相对 mwait-nop 将 Redis、ZooKeeper 等延迟敏感负载的 P99 降低 30–50%，steal ratio 降低 30–40%（图 14）。mwait-nop 下同步密集 workload 的 steal time 可超过 90%，mwait-sched 将其压到 60% 以下。
- IOPS/利用率分类器在 1,000 个生产 VM 上的总体误分类率为 0.21%；阈值在 50–150 范围内时误分类率低于 0.7%（§5.1）。
- mwait-proxy 在生产密度 1:4 时，普通 CPU/I/O workload 的 P99 膨胀约 1.8–3.4 倍；同步密集的 ZK Get、RD Get、RD Set 分别达到约 8.2、7.0、6.4 倍。1:8 压力测试中最差约 11–16 倍（图 15）。
- 三个生产区域部署后，高争用 steal 事件分别下降 85%、97% 和 86%，每日 hot migration 同步下降（图 16）。
- 覆盖 3.2M pCPU 的全球部署把 oversubscription 从 1.0% 提高到 20.3%，增加约 600,000 个可售 vCPU；每日告警从每万台 512 降到 197（图 17）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| passthrough 在共享 pCPU 上会把硬件空闲隐藏给 host scheduler | 共置 YCSB 的尾延迟对比（图 4）；机制分析（§3.2） | x86、Linux/KVM 风格虚拟化、特定 YCSB 配置 | 强 |
| 空闲时长可用于安全聚合 | 生产 eBPF 分布（图 12），99.6%/96.0% 分离 | 随机生产主机采样，未覆盖所有 guest OS | 中 |
| mwait-sched 改善过载下尾延迟与 steal | 九类 workload 的 P99/steal 对比（图 14） | 主要为 2:1 及更高 oversubscription、单 NUMA 节点 | 强 |
| 机制能提升 hyperscale 可售容量且降低告警 | 3.2M pCPU 生产 rollout（图 17） | 生产部署的专用 instance fleet；因果混杂和长期回归信息有限 | 中 |

## 批判性分析

### 论证链条

论文的主链条较完整：passthrough 消除退出却隐藏 idle，隐藏 idle 造成共享核争用，idle interval 提供了可用的 guest 信号，分类与 emulation 恢复了调度点。图 3–4 先隔离延迟收益和共置伤害，图 8–12 再解释 slice 与分类器的设计依据，图 14–17 覆盖微基准到生产信号。

最大跳步是把生产 rollout 的 steal、migration 和告警下降主要归因于 mwait-sched。论文没有给出同期负载、放置策略、硬件变化或控制组策略的完整反事实，因此容量收益应视为强工程证据，而非完全隔离的因果估计。

### 假设压力测试

二元 stable/transient 分类依赖明显的间隔空洞。突发网络服务、忙闲交替的 batch job 或不同内核 idle 实现可能产生大量 200 µs–1 ms 的中间样本。IOPS/利用率比值也可能被缓存、批处理和多线程结构改变，导致短 slice 被错误分配。

proxy 的值比较只适合论文假定的 Linux `need_resched` 路径。其他 guest OS、驱动或自定义 runtime 如果依赖“每一次写入都唤醒”，当前实现可能漏掉事件。论文也没有证明在 NUMA 跨节点、CPU 频率变化、SMT 或更大 vCPU 数量下同样成立。

### 实验可信度

论文覆盖 24 类、220 个由生产流量派生的场景，并同时报告 P99、steal、host 开销和生产告警，基线包含 mwait-nop 与 passthrough，方向上足以支持调度可见性这一主张。另一方面，proxy 在 1:4 以上已出现很大尾延迟，专用 fleet 与 burst fleet 的部署策略不同；“整体 oversubscription 提升”不能直接理解为所有 workload 都能安全运行在 1:4 或 1:6。

### 系统性缺陷

timer slice、PMU 分类、VM-wide wakeup 和地址链表都增加了 hypervisor 状态与诊断路径。论文未讨论 live migration 期间 monitored address 的迁移、vCPU 热插拔、guest 内存映射变化、链表损坏恢复和多租户隔离的详细实现。安全部分说明 passthrough 的 DoS 风险被限制，但未提供恶意 guest 的压力测试或 side-channel 量化。

## 局限与后续工作

- **局限 1**：timer emulation 对 `fdatasync` 等频繁 fsync workload 可能每次增加一个 slice 的延迟；论文中该负载在所有 oversubscription 比例下仍保持较高延迟（§5.2）。
- **局限 2**：mwait-proxy 的链表扫描在高密度下成为瓶颈，1:8 仅作为压力点，不代表可扩展生产配置（图 15）。
- **后续工作 1**：在多种 guest OS、不同 Linux idle 实现和热迁移场景下验证 monitored-address 事件语义，特别是同值写与 write-then-revert。
- **后续工作 2**：测量分类器在突发 workload 和 concept drift 下的误判代价，并比较自适应阈值与固定 PMU 阈值的长期 SLO 结果。
- **后续工作 3**：实现并评估作者提出的 vectorized monitor 或 virtualization-aware wait ISA，验证它是否能把 proxy 的线性扫描成本降到可接受范围。

## 相关

- **相关概念**：[[Virtualization]]、[[CPU Scheduling]]、[[Oversubscription]]、[[Tail Latency]]
- **同类系统**：[[SmartHarvest]]、[[UFO]]、[[Shenango]]
- **同会议**：[[OSDI-2026]]
