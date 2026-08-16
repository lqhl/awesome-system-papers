---
type: paper
name: Svalinn
full_title: "Svalinn: Overload Control in Large-Scale Servers with Multiple Resource Bottlenecks"
authors: [Bhaskar Subhash Pardeshi, Peidi Song, Ahmed Saeed]
venue: OSDI
year: 2026
tags: [overload-control, admission-control, tail-latency, memory-bandwidth]
source_pdf: "[[osdi26-pardeshi.pdf]]"
source_md: "[[osdi26-pardeshi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 多资源瓶颈下的服务器过载控制（OSDI 2026）

> **原题**：Svalinn: Overload Control in Large-Scale Servers with Multiple Resource Bottlenecks

> **一句话总结**：Svalinn 指出“一个服务只有一个共享瓶颈队列”是错误前提，于是让全局 credit controller 只负责寻找最高 utility 的总负载，让 memory bandwidth、mutex 等局部 controller 各自在真正访问点控制延迟；其中 `m_semaphore` 把隐式内存带宽变成可排队或丢弃的显式入口，在两套机器、Shenango/Go、三个真实应用和合成 workload 上相对 SEDA/Protego 的 goodput 最高提高 6.51/6.49 倍，但需要开发者标出内存密集路径，并允许已经开始执行的请求被丢弃和清理。

## 问题与动机

一个服务二进制内的请求并不相同。小 value 的 GET 可能主要消耗 CPU，大 value GET 可能受内存带宽限制，写热点 key 又可能卡在锁上；甚至同一个 API 也会因数据大小走向不同瓶颈。传统 overload controller 却看整体 p99、总 in-flight request 或某一种固定资源，一旦最先拥塞的资源变慢，就减少所有请求（§1、§2）。论文把这个错误称为**单队列谬误（single-queue fallacy）**。

问题不只是留下空闲资源。合成实验中，内存请求只用 24/45 个 core 就能打满内存带宽；继续调度更多内存请求不会增加 throughput，只会让更多 core stall，最终看起来像 CPU 也满了。80% CPU 请求与 20% 内存请求混合时，普通 latency admission 在约 300 kRPS 停止增长，而如果限制内存并发，剩余 core 还能把 CPU 请求 goodput 提高约 3 倍（图 1–2、§2.2）。Aspen preemption 也没有改善 throughput，因为它只是把线程换来换去，没有减少同时争内存带宽的请求数。

显式锁、网络和 storage queue 可以直接做主动队列管理（Active Queue Management，AQM），内存带宽却由任意 `LOAD/STORE` 隐式使用，没有软件队列。Svalinn 要同时解决三个目标：提高所有资源的总利用率、让每条资源路径仍满足 SLO，并在请求资源需求只能执行到中途才知道时继续工作。

## 关键观察 / 隐含假设

- **观察 1：总负载最优点与每个资源的局部排队状态不是同一个控制问题。** 全局 controller 应继续增加有价值的请求，而真正拥塞的 queue 只拒绝会访问它的请求；否则一个 lock 或 memory path 会让不相关的 CPU path 一起停下（图 2、图 12）。
  - **依赖假设**：局部 controller 的拒绝不会破坏全局 utility，多个 controller 的动作不会形成明显振荡。
  - **可能失效场景**：请求串行经过多个瓶颈、已付出大量前置工作后才被拒绝，局部最优并不等于端到端最优。
- **观察 2：内存带宽饱和后，额外并发只消耗 core，不增加带宽。** 图 1 的带宽与 throughput 在红线后不再上升，CPU 使用却超线性增加；因此目标应是找到“打满带宽所需的最少 core”，不是把 memory request 调度到所有 core（§2.2、§3.2）。
  - **依赖假设**：存在相对稳定的饱和点，硬件 counter 能及时反映它；[[NUMA|NUMA]]、cache miss 模式和其他 tenant 不会让最优并发在一个控制周期内剧烈变化。
- **观察 3：资源需求可以在代码路径上暴露，而不必在请求入口分类。** 开发者在真正的大 `memcpy` 或 memory-heavy region 前调用 `m_semaphore`；Memcached 与 [[RocksDB]] 各只需标一个 call path（§3.4）。
  - **依赖假设**：开发者能找到完整且稳定的重内存区域，进入该区域前的 CPU/锁成本较小。
  - **可能失效场景**：库、kernel、JIT 或不可预测 cache behavior 才是带宽来源，遗漏标注会绕过控制；过宽标注则误杀轻请求。
- **观察 4：请求可共享一个 SLO-derived queueing budget。** 每经过一个 bottleneck，就扣掉已等待时间；若剩余 budget 小于当前 queue delay，就在入队前丢弃。这样不必为每种资源配置一套独立 SLO（§3.3）。
  - **依赖假设**：服务能安全取消请求、运行 cleanup callback，并让客户端或 sidecar 把失败请求送到另一个 replica。
- **假设 1：用户定义 utility 能真实表达运营目标。** controller 只比较 micro-experiment 的 utility，不理解 tenant 公平、业务优先级或错误重试成本；错误 utility 会稳定地优化错误目标。

## 核心方法

### 1. 全局 throughput controller 只调一个 credit pool

所有请求类型共享同一组 credits，client 先报告 demand，只有得到 credit 才发送请求。server 不根据某个资源的 latency 直接设负载，而是反复做两个短 micro-experiment：把 pool 增加 `δ` 和减少 `δ`，各等待 `Δt_warmup` 让网络传播生效，再在 `Δt_monitor` 内记录 request、response、drop、queue delay、energy、memory bandwidth 等指标，选择 utility 更高的方向（§3.1、算法 2）。

credit pool 只是 arrival rate 的代理。若 `+δ` 期间真实到达率反而更低，Svalinn 会按实际到达率重新标记两组 measurement，避免把 traffic noise 错当成 pool 效果。client 可能持有 credit 不用，server 因此允许安全 overcommit。默认 utility 只最大化 response throughput；也可加入 drop 上限或资源使用。

### 2. 每个 bottleneck 独立执行 latency control

请求进入服务时带一个由 SLO 算出的 queueing-delay budget。mutex、`m_semaphore` 等每个显式 queue 都看同一剩余 budget：若当前估计等待时间已超过剩余量，就不再排队。被丢请求需要向 client 回失败，或由 server 转发到其他 replica；应用还必须注册 cleanup callback 回滚状态、释放资源。不能安全取消的请求可标成 non-droppable，AQM 会把它当高优先级（§3.3）。

### 3. `m_semaphore` 把内存带宽变成显式 queue

开发者在 memory-intensive section 前调用 `try_wait()` 或 `wait_if_uncongested()`，结束后 `post()`。runtime 内只有一个 singleton `m_semaphore`，所有标注区域共享 capacity（图 3、§3.2、§4）：

- `try_wait()` 是默认路径，不允许排队；没拿到 permit 就立即 drop，延迟最低但 drop 更多。
- `wait_if_uncongested()` 允许有足够剩余 SLO budget 的请求等待，适合不想立即 shed 的场景。

permit 数不是固定配置。每个可能 core count 是一个 multi-armed bandit arm；每 500 µs 读 Intel PCM 的 memory-bandwidth counter，用“归一化 bandwidth 收益减去 core 使用惩罚”更新 reward。默认 `α=0.7`、EMA weight `ω=0.8`、探索率 `ε=0.3`。大多数周期选择历史 reward 最好 capacity，探索时只试相邻 capacity，避免跨很大范围跳动（算法 1）。

### 4. 实现并不只有几行 wrapper

Svalinn 分别实现于 Shenango 与 Go。应用的 memory path wrapper 和 drop handler 确实只需 4–10 LoC，但完整集成更大：Shenango throughput RPC controller 1815 LoC、`m_semaphore` 961 LoC、IOKernel counter 支持 631 LoC；DataFrame/RocksDB RPC 集成各 1462/1668 LoC。Go RPC layer 5696 LoC，另有 1502 LoC perf goroutine 和 454 LoC semaphore（§4）。

counter 读取不放在请求 fast path：Shenango IOKernel 每 5–10 µs 采样，Go 则专门占一个 logical core，每 5 µs 更新 memory bandwidth、runtime queue delay 和 TCP RX delay。这是系统持续付出的观测成本。

## 设计取舍

- **分离控制换组合复杂度。** throughput loop 不再被最坏资源绑架，但多个局部 AQM 与一个全局 credit loop 同时变化，没有形式化稳定性或全局最优保证。
- **执行点判断换入口预测。** 不必提前给请求分类，却可能在执行一半后才 drop，浪费已消耗的 CPU、锁和网络工作。
- **零长度 queue 换低 latency。** 默认 `try_wait()` 让失败很快，适合有 spare replica 的服务；单 replica 或重试风暴下会直接损失可用性。
- **MAB 自适应换持续探索。** `ε=0.3` 能跟上 phase change，但稳定 workload 也一直尝试非最优 capacity；reward 又以历史最大带宽归一化，硬件或 tenant 状态变化后可能滞后。
- **通用 utility 换可预测性。** operator 能表达 throughput/drop/energy 取舍，但不能从“凸 utility”自动得到公平、优先级和每类最低 goodput。
- **少量业务标注换部署负担。** memory wrapper 很短，真正困难的是准确找 region、保证取消安全，并维护 runtime、RPC 与 monitoring 修改。

## 实验设置

- SETUPA 是 11 台 CloudLab 节点：每台 10-core E5-2640v4、约 45 GB/s memory bandwidth、25 GbE、约 10 µs RTT，应用用 18 logical core。SETUPB 是两台双路 Xeon Gold 6442Y、约 180 GB/s、200 Gb/s NIC；只用一个 socket 的 45 logical core，RTT 约 40 µs（§5.1）。
- workload 包括 synthetic、Memcached、RocksDB、DataFrame；请求分为 CPU、memory 和 lock 型，mix 人工设置为 50/50、80/20、99/1 或 25/25/50。Go 只测 synthetic，真实应用主要在 Shenango/Caladan runtime。
- baseline 是按整体 p99 调 client rate 的 SEDA，以及全局 credit + per-lock AQM 的 Protego。两者都没有 memory-bandwidth concurrency controller；没有与可控制 memory bandwidth 的同功能系统比较。
- SLO 统一设为 `5 × (最长请求类型的平均 service time + 平均 RTT)`；goodput 只统计 SLO 内完成的请求，并按请求类型分别报告 p99。load generator 为 100 client thread 的 open-loop Poisson arrival。

## 实验与结果

- **合成双瓶颈**：SETUPA 的 50/50 CPU/memory workload 中，六个并发 memory request 已打满带宽。Svalinn 相对 SEDA/Protego 将 CPU goodput 最多提高 5.06 倍、memory goodput最多提高 1.60 倍；CPU p99 分别低 5.48/5.95 倍，memory p99 低 2.87/3.49 倍，并保持在 0.4 ms SLO 内（图 4、§5.2）。
- **突发与快速拒绝**：在本来能承载 115 kRPS CPU + 50 kRPS memory 的 server 上加入 25 kRPS memory burst，Protego 的 CPU throughput 从 115 降到约 90 kRPS，两类 drop 约 20%；Svalinn 保住全部 CPU load、CPU drop 为 0%，但在 burst 峰值丢约 25% memory request，平稳期也因瞬时 arrival spike 丢约 5%。两 server retransmission 实验中，第二台机器可吸收这些快速失败，请求 p99 仍低于放宽后的 SLO（图 5–6、图 10、§5.2–§5.3）。
- **真实应用**：RocksDB 的 CPU/memory goodput相对基线最高提高 7.62/1.26 倍，p99 最多低 2.95/1.47 倍；DataFrame 的 CPU goodput最高提高 3.99 倍，CPU p99 相对 SEDA/Protego 低 42.77/21.17 倍。Memcached 的 CPU/lock goodput最高提高 2.53/2.58 倍，三类 p99 最多低 13.57、1.74、17.32 倍。摘要汇总的最高 application goodput 增益为相对 SEDA 6.51 倍、Protego 6.49 倍（图 7–8、图 16、§5.2、附录 B.2）。
- **三个并发瓶颈**：25/25/50 CPU/memory/lock workload 中，SEDA 在 lock 约 180 kRPS 饱和后停止，Protego 到 memory 约 300 kRPS 饱和后停止。Svalinn 把 mutex AQM 与 `m_semaphore` 组合，overall goodput相对 SEDA/Protego 最高高 3.46/2.50 倍，p99 最高低 2.80/1.61 倍；CPU 类型单独可高 8.71/4.18 倍（图 12、图 15、§5.3、附录 B.1）。
- **controller 消融与适应性**：throughput-only utility 比 drop-aware utility 只多 1.03/1.01 倍 CPU/memory goodput，却让 drop 到 19%；drop-aware 将目标设为 10%，实际最多 7%，并把两类 p99 降低 1.52/1.32 倍。memory request 每 2 秒在 5000/6500/9000 MB/s per-core demand 间切换时，`m_semaphore` 平均 50 ms 收敛到新 capacity。reward 模拟的正文称 `α≤0.3` 时会偏向低于最优的 core count、`0.3<α<0.9` 时峰值落在正确 core count、`α=1` 时会振荡；这两段范围在 `α=0.3` 处互相重叠，论文没有澄清该边界（图 9、图 11、图 17–18、§5.3、附录 B.3–B.4）。
- **硬件与 runtime 可移植性**：SETUPB RocksDB 中，Svalinn 的 CPU goodput比两基线高 2.65 倍，CPU p99 相对 SEDA/Protego 低 8.09/3.87 倍；Go synthetic 中 CPU goodput最高高 3.21 倍，两类 p99 最多低 3.25/1.85 倍。结果说明机制不只依赖 SETUPA/Shenango，但 Go 没有真实应用结果（图 13–14、§5.3）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| aggregate controller 会因最先拥塞资源浪费其他容量 | 图 2、图 4：memory 饱和后 CPU path 停止增长；Svalinn 的 CPU goodput高 5.06 倍 | 人工区分 CPU/memory 的合成 workload；baseline 无 memory controller | 强 |
| `m_semaphore` 能以更少 core 打满带宽 | 图 4：六个 memory request 已饱和；图 11：需求切换后平均 50 ms 找到新 capacity | Intel PCM、单一 singleton、两个 Intel 平台；持续探索成本未单独量化 | 强 |
| throughput 与 per-resource latency controller 可以组合 | 图 12/15：lock+memory+CPU 下 overall goodput高 3.46/2.50 倍且 p99 更低 | 只组合 mutex 与内存，未测 NIC、storage 或长 microservice chain | 强 |
| utility 能表达 throughput 与 drop 取舍 | 图 9：drop 从 19% 限到 7%，goodput只少约 1% | 一个 80/20 synthetic mix；没有 tenant fairness 或业务 value | 中到强 |
| 设计可迁移到不同硬件与 runtime | 图 13–14：SETUPB RocksDB 与 SETUPA Go 都保持收益 | 仍是单 server 内控制；Go 只测 synthetic | 中 |

## 批判性分析

### 论证链条

论文从图 1–2 的测量得到明确 observation：memory bandwidth 饱和会把“仍有可用 CPU”伪装成整体 overload。全局 credit loop、局部 AQM 和 `m_semaphore` 分别回应总负载、显式 queue 与隐式 bandwidth，三瓶颈实验也验证了组合。主链条是闭合的。需要克制解读最高 6.51 倍：SEDA 与 Protego 本来就不能限制 memory concurrency，因此这些大倍数同时说明 baseline 的功能缺口；它们不代表 Svalinn 相对所有现代 resource partitioning 或 bandwidth controller 都有同样优势。

### 假设压力测试

memory-intensive region 如果跨很多函数、由 data-dependent cache miss 形成或发生在 library/kernel 内，4–10 LoC wrapper 的前提会失效。请求在写状态后才遇到 semaphore 时，drop callback 可能无法无代价回滚。没有 spare replica 时，零 queue 会把 overload 变成可见错误；有 spare replica 时，多个 server 同时 shed 又可能形成重试风暴。MAB 以 500 µs 周期控制，论文的 phase 每 2 秒才变化；更快 oscillation、NUMA 多 controller 和共租户 bandwidth noise 未验证。

### 实验可信度

两档 CPU/内存/NIC、Shenango 与 Go、三个真实应用、突发、retransmission、三瓶颈、utility、request mix 和 MAB sensitivity，覆盖比单一 microbenchmark 完整。作者也给所有系统调参，并统一 SLO。主要缺口是 workload mix 与资源路径都由作者精心构造，最长 SLO 用最长 request 的平均 service time 统一计算，可能对短 CPU request 较宽松。没有 production trace、能耗结果、控制 loop 稳定性统计、P99.9 或多 tenant；没有同功能 memory-bandwidth admission baseline，使绝对增益很难拆分。

### 系统性缺陷

Svalinn 把 request cancellation、cleanup、resource annotation 和 utility 正确性放进应用 TCB。论文只说多数开源程序已有 cancellation handler，没有证明 handler 在任意中间点都幂等、安全。所有标注区域共享 singleton semaphore，不表达 NUMA node、memory channel 或 [[CXL|CXL]]/DRAM 分层。Go 每 5 µs 采样还专门占一个 logical core；大规模 RPC 集成是数千 LoC。论文未讨论 controller state checkpoint、counter 故障、credit leak、client crash、non-droppable request 饿死普通请求或 AQM 错误估计后的恢复。

## 局限与后续工作

- **局限 1**：需要人工识别 memory-heavy call path；未标注、跨 NUMA 或库内部流量绕过控制。
- **局限 2**：默认策略会丢弃已开始执行的请求，依赖 cleanup 与另一 replica，未覆盖有副作用或不可重试操作。
- **局限 3**：评测只组合 CPU、memory bandwidth 和 mutex；NIC、storage IOPS、CXL 与跨服务 bottleneck 仍未验证。
- **局限 4**：最高结果来自人工 request mix 与不具备 memory control 的 baseline，没有生产长期 trace、公平性和能耗。
- **后续工作 1**：用 production trace 重放 request path 和 phase change，报告每类 goodput、P99.9、drop/retry amplification 与 controller settling time。
- **后续工作 2**：按 NUMA node、memory channel 和 tier 拆分 `m_semaphore`，在跨 socket 与共租户干扰下验证 locality 和稳定性。
- **后续工作 3**：对多 controller 建立小信号或控制论模型，扫描 `δ`、monitor interval、`ε` 和 workload period，量化振荡与 SLO violation。
- **后续工作 4**：给 stateful request 定义可验证 cancellation contract，并注入 cleanup 失败、client crash、counter stale 和 retry storm。

## 相关

- **相关系统**：[[RocksDB]]、SEDA、Protego、Shenango
- **相关概念**：overload control、AQM、memory bandwidth、tail latency
- **同会议**：[[OSDI-2026]]
