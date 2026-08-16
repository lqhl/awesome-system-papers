---
type: paper
name: vBOIDs
full_title: "vBOIDs: Taming Chaos via Coarse-grained Scheduling Abstraction for Containers"
authors: [Kaesi Manakkal, Nathan Daughety, Yu Sun, Marcus Pendleton, Hui Lu]
venue: OSDI
year: 2026
tags: [containers, cpu-scheduling, microservices, linux, performance-isolation]
source_pdf: "[[osdi26-manakkal.pdf]]"
source_md: "[[osdi26-manakkal]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# vBOIDs：用粗粒度调度抽象治理容器调度混乱（OSDI 2026）

> **原题**：vBOIDs: Taming Chaos via Coarse-grained Scheduling Abstraction for Containers

> **一句话总结**：vBOIDs 发现高密度容器的主要问题不是同核切换，而是 Linux 把每个线程都当成跨核迁移候选，形成 migration storm；它把容器线程归入少量类似 vCPU 的 BOID，再用跨核 BOID 迁移和容器内线程再平衡恢复 locality，在 chaos-prone microservices 上把满足 SLO 的吞吐提高到 default container 的约 3×，但收益依赖人工配置合适的 BOID 数和深度修改内核调度器。

## 问题与动机

容器共享宿主内核，每个进程和线程都直接出现在 Linux 调度器中。一套 24-service Hotel Reservation 部署会产生 500 多个 host-visible scheduling entities，而对应 Firecracker micro-VM 只向宿主暴露约 52 个 vCPU。线程越多，CFS runqueue 的瞬时差异越频繁，load balancer 就越积极地逐线程扫描和迁移。

作者把由此产生的状态称为 scheduling chaos：大量 inter-core migration 不断丢失 L1/L2 cache、扰动 LLC、触发 TLB shootdown 和跨核锁协调；硬件还没建立新 locality，线程又被搬走。Hotel Reservation 的 default container 在系统 CPU 利用率低于 30% 时就出现 latency spike，而同核时间片切换在 container 和 micro-VM 中都很多，却没有同样破坏性。

手工 CPU affinity 能稳定 placement，但无法维护数百个短命线程，且限制弹性。cgroup quota 只限制一段时间内用多少 CPU，不限制瞬时占多少 core；例如 2-CPU quota 仍可短暂在 100 cores 上同时执行。micro-VM 的少量 vCPU 天然提供稳定迁移单元，却付出 guest kernel 和 hypervisor 成本。vBOIDs 的目标是在原生容器中引入类似 vCPU 的 placement unit，同时保留动态负载均衡。

## 关键观察 / 隐含假设

- **观察 1：真正破坏 locality 的是跨核迁移，不是必要的同核切换。** 1k RPS 下，default container 的 cache/TLB miss 和 inter-core migration 显著高于 pinned container 与 micro-VM；pinning 将迁移减少约 60% 并稳定 latency（§2.1–§2.2，图 3、表 1）。
  - **依赖假设**：这些 counter 与端到端退化具有因果关系，而不是共同由另一种 overload 引起。
  - **可能失效场景**：CPU-bound、共享 cache 友好或线程状态很小的工作负载，迁移未必是主要瓶颈。
- **观察 2：宿主 placement 不需要看到容器内部每个线程。** micro-VM 用少量长寿 vCPU 就能保持稳定 runqueue；容器也可以把执行粒度保留在线程，把迁移粒度提升到 container-level virtual core（§2.3）。
  - **依赖假设**：BOID 数接近容器真实并行需求；太少会人为串行，太多会重新扩大调度状态空间。
- **观察 3：只做粗粒度迁移会产生 elephant BOID。** 某个 BOID 的 aggregate load 若大于 source/destination gap，整体搬迁只会反转不平衡并 ping-pong；必须在容器内部把部分线程移到较轻 BOID（§4.3）。
  - **依赖假设**：PELT 的衰减负载能及时代表 bursty RPC 需求，线程级转移也能在任务结束前生效。
- **假设 1：管理员能像配置 VM vCPU 一样配置 BOID 数。** 当前实现按预期并发需求人工设置，虽支持 runtime resize，却没有自动 policy。
  - **证据强度**：强；§5 明确把 adaptive vertical scaling 留作后续工作。

## 核心方法

### BOID：容器级虚拟执行核

BOID（Bound Object Integrated Dispatch）是一等 kernel object，保存成员线程、aggregate PELT load、当前 CPU 和目标 CPU（图 4）。同一 BOID 的线程只能在 BOID 所在物理 core 上运行，而且同时最多运行一个。容器配置 `N` 个 BOID，最多便有 `N` 个并行 execution contexts，行为类似 `N` 个 vCPU。

BOID 不替换 CFS 的同核线程选择。线程仍按 vruntime 竞争，cgroup weight 仍用于 inter-container proportional share；变化在于跨核 load balancer 把 BOID 而非 thread 当成原子候选。每个线程的 allowed-CPU mask 指向其 BOID 当前 core，现有 `is_cpu_allowed()` 路径自然执行边界，不需修改 pick-next hot path。

### 跨核 BOID balancing

线程 PELT 更新时，vBOIDs 以 atomic delta 增量累加到所属 BOID，避免 balance 时遍历成员。全局搜索空间由 `T` 个线程压缩到 `N` 个 BOID，其中 `N≪T`。balancer 先跳过 residency 低于 hotness threshold 的 cache-hot BOID，并限制目的 core 在允许的 [[NUMA|NUMA]] topology 内。

若 BOID load 小于 imbalance gap，且搬过去确实缩小 source/destination 差距，系统才提交迁移。逻辑提交只用 CAS 更新 `boid->new_cpu`，不同时锁两个 runqueue。成员线程在后续 wakeup 或 context switch 中发现新目标，再逐个物理搬迁；因此 balancer 看见的是一次 atomic flock-like move，实际成本被摊到自然调度事件。

### 容器内线程 balancing

BOID 比 gap 更重时被视为 elephant，不能整体搬。容器内 balancer 找到同一 container 最轻的 BOID，只在两者差距足够大、候选 task load 不会 overshoot 时，把一个线程重新归属过去。它既避免 coarse unit 内部形成 hotspot，也把 elephant 逐渐变回可以跨核迁移的大小。新 fork 默认放到最轻 BOID，帮助短命并行任务立即扩散。

### 内核实现与控制面

Linux 6.15 patch 约 2,000 行，修改 `fair.c`、`pelt.c`、`cgroup.c` 等。`task_group` 增加 BOID array，`task_struct` 通过 RCU pointer 指向所属 BOID；affinity hot path 用 RCU read 和 atomic state 保持 wait-free。新 cgroup 文件 `cpu.boids` 可运行时修改 BOID 数，并 round-robin 重分配已有线程。每容器还有 migration cooldown 和 balance cooldown，默认都为 0；RPC-heavy workload 对 balance cooldown 更敏感，CPU-heavy、频繁 fork 的 workload 主要靠新线程初始放置（§5、§6.3）。

## 设计取舍

- **并发上界换取 placement 稳定**：`N` BOIDs 阻止容器瞬时冲到超过 `N` cores；如果 `N` 低估需求，即使机器还有空 core，也会排队。
- **粗粒度全局迁移换取细粒度局部修正**：减少跨核 churn，但实现了两套相互反馈的 balancer，正确性与调参复杂度提高。
- **惰性迁移换取低锁开销**：只 CAS 目标 CPU，不阻塞 hot path；逻辑 move 与所有线程物理收敛之间存在短暂过渡期，load accounting 和 affinity 必须保持一致。
- **原生兼容换取内核侵入**：Docker 和 Kubernetes 应用不用修改，但 patch 深入 CFS internals，upstream、版本升级和 EEVDF/sched_ext 兼容成本较高。
- **边界条件**：最适合线程多、RPC 阻塞频繁、CPU 尚未饱和却有 migration storm 的服务；极短、CPU-bound、需要立刻占用很多 core 的任务收益较小。

## 实验与结果

- testbed 是双路 Intel Xeon Gold 6430、64 个物理 core、64 GB DDR5，关闭 hyperthreading，运行 Ubuntu 22.04 和修改后的 Linux 6.15。基线为 default/pinned Docker container、default/pinned Firecracker，所有配置按每 service 1–4 cores、vCPUs 或同数 BOIDs 对齐；wrk2 使用 exponential inter-arrival，60 秒正式测量（§6、表 2）。
- Hotel Reservation 以 200 ms average-latency SLO 计，default container 在约 1k RPS 后停止扩展，vBOIDs、pinned container 和 Firecracker 可持续到 4k RPS；vBOIDs 吞吐比 default 高 3×以上，整体 CPU 使用约为 default 的 40%、pinned container 的 80%（§6.1，图 1–3、表 1）。
- Social Network 中 default container 约在 2k RPS 饱和，vBOIDs 与 pinned container 在满足 SLO 时接近 5k RPS；1k RPS 测量点上，vBOIDs 将跨核 migration 减少 85%，cache/TLB miss 同时降低（§6.1，图 6–8、表 3）。
- CPU-intensive Media Services 需要快速扩散短命线程；vBOIDs 会允许更多 BOID migration，性能与最快的 unpinned container 相当，而 pinned configurations 更慢。这说明系统没有一律禁止迁移，但该 workload 也没有得到 3×收益（§6.1，图 9–11）。
- Social Network 5k RPS 的 60 秒 trace 中，全局 BOID migration 约 600 次，容器内 task redistribution 约 16k 次，多数活跃 core 约在 50% utilization。2k RPS 下加入最多 1,000 个各占单 BOID、约 1%–2% 单核的 noise containers 后仍维持目标吞吐，但平均 latency 开始上升（§6.2–§6.3，图 12、14–15）。
- Kubernetes Online Boutique 把标准容器的 359 个 scheduler-visible units 压缩为 31 BOIDs。负载线性升到 2k concurrent users 时，default pods 的 p95 超过 4,000 ms；vBOIDs 与手工 pinning 都保持在 500 ms 内，并有相近吞吐（§6.4，图 16）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 高密度容器的 inter-core migration 是主要退化来源 | pinning/Firecracker/vBOIDs 同时减少 migration、cache/TLB miss 和 latency（§2、§6.1） | 控制对照强，但没有只改变 migration rate 的单因素实验 | 中 |
| BOID 能在 chaos-prone 服务上恢复 pinning 级稳定性 | Hotel 4k vs default 1k RPS；Social 5k vs 2k RPS（图 1、6） | 人工按 core/vCPU 数配置 BOID，单台 x86 server | 强 |
| 两层 balancing 没有必然牺牲 CPU-heavy 并行性 | Media Services 匹配最快 unpinned configuration（图 9–11） | 只覆盖一种 CPU-heavy microservice；BOID 未严重欠配 | 中 |
| 状态空间压缩可用于 Kubernetes 和高 container count | 359→31 units；1,000 noise containers 下保持吞吐（图 14、16） | background containers 很轻，仍低于文中 production density | 中 |
| hot-path 实现开销较低 | Media Services 无明显退化；PELT delta O(1)、RCU/atomic 路径（§5–§6） | 没有 scheduler microbenchmark 或 per-operation cycle breakdown | 中 |

## 批判性分析

### 论证链条

论文先用 container、pinned container 和 micro-VM 三组对照把问题定位到 host-visible entity 数和跨核迁移，再用 BOID 把 vCPU 的 placement 稳定性引入共享内核，最后以 two-level balancing 避免粗粒度造成内部 hotspot。Hotel/Social 的 migration、cache counter 与吞吐共同变化，Media Services 又验证必要时仍能扩散，整体从 observation 到 design 再到 result 比较连贯。

但 3×增益不能只归因于“迁移次数减少”。BOID 同时限制并行度、缩小 load-balancer scan、改变 runqueue 分布和 cache locality；论文没有逐一关闭 hotness filter、lazy migration、intra-container balancing 或 state-space compression。因此“migration storm 是核心原因”有很强旁证，却没有完整的机制贡献分解。

### 假设压力测试

BOID count 是新的一等资源参数。太大时每容器重新暴露很多迁移单元，太小时 strict serial invariant 限制并行，即使系统有空 core 也未必 work-conserving。论文所有主对比把 BOID 数设成预先测得的 CPU demand，与 Firecracker vCPU 数相同；真实 autoscaling、突发负载和错误配置尚未验证。

PELT 有 32 ms half-life，极短 burst 可能在 balancer 反应前结束。作者用 least-loaded BOID 放置新 fork 缓解，但 §8 仍承认高度并行、极短任务可能来不及摊销 placement/cache warming。SMT、heterogeneous cores、real-time class、nested cgroup、CPU hotplug 和跨 NUMA memory placement也可能破坏当前假设，实验关闭了 hyperthreading。

### 实验可信度

DeathStarBench 三个行为不同的应用、Firecracker/pinning 对照、Kubernetes Online Boutique、1,000 noise containers 和 cooldown sensitivity 提供了多角度证据。资源对齐清楚，负载生成方式和 SLO 口径也有说明。负结果中 Media Services 几乎无收益，避免了只选 chaos workload 的单面叙述。

局限是所有实验都在一台 64-core x86 server 上，且主 workload 的 BOID 数经人工配置。Hotel/Social 主要用 average latency 判断 SLO，只有 Kubernetes 给 p95，没有 p99。背景 containers 仅各用 1%–2% 单核，不能代表有 CPU contention、不同 cgroup weights 和多个 latency-critical tenants 的 production consolidation。论文也没有评估 runtime resize、fairness error 或 BOID migration 的单次开销。

### 系统性缺陷

约 2,000 行 patch 触及 scheduler 核心结构，任何 race、RCU lifetime 或 affinity invariant 错误都可能影响整机。逻辑迁移先于物理迁移，故障排查需要同时观察 BOID state、thread runqueue 和 PELT aggregate；论文没有给出 tracing、debugging 或 rollback 工具。

“强 performance isolation by construction”只限制并发 core 数，不隔离 LLC、memory bandwidth、I/O 或 security boundary，也没有 VM 级故障隔离。容器间 fairness 沿用 CFS weights 的论证是设计说明，实验没有用多个不同权重 tenant 验证。默认 cooldown 为零在当前 workload 可行，不代表所有机器无需调参。

## 局限与后续工作

- **局限 1**：BOID 数需 operator 预估，自动 vertical scaling 尚未实现；欠配会限制并行，过配可能重现 scheduling chaos。
- **局限 2**：实现绑定 Linux 6.15 CFS internals，未验证 EEVDF、sched_ext、SMT、heterogeneous core、RT task 和 nested cgroup。
- **局限 3**：评测只有单机、单 CPU architecture，缺少多 tenant 权重公平、p99、能耗和 runtime resize 稳定性。
- **后续工作 1**：实现按 runnable load 与 SLO 自动增减 BOID，在阶跃负载下测 resize 收敛时间、p99 latency、migration 和空闲 core 比例。
- **后续工作 2**：加入不同 cgroup weights、CPU quota 和三类 tenant 的过载实验，验证长期 CPU share error 与性能隔离，而不只看总吞吐。
- **后续工作 3**：用 sched_ext/[[eBPF|eBPF]] 实现等价 prototype，与内核 patch 比较 hot-path cycles、功能覆盖和版本维护成本。

## 相关

- **相关概念**：[[Container-Scheduling]]、[[CFS]]、[[CPU-Affinity]]、[[Microservices]]、[[Performance-Isolation]]
- **同类系统**：Firecracker、Caladan、ghOSt、sched_ext
- **同会议**：[[OSDI-2026]]
