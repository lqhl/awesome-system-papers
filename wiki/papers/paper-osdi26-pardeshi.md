---
type: paper
name: Svalinn
full_title: Svalinn: Overload Control in Large-Scale Servers with Multiple Resource Bottlenecks
authors: [Bhaskar Subhash Pardeshi, Peidi Song, Ahmed Saeed]
venue: OSDI
year: 2026
tags: [overload-control, resource-contention, memory-bandwidth, tail-latency, admission-control]
source_pdf: "[[osdi26-pardeshi.pdf]]"
source_md: "[[osdi26-pardeshi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-16
---

# 多资源瓶颈服务器的过载控制（OSDI 2026）

> **原题**：Svalinn: Overload Control in Large-Scale Servers with Multiple Resource Bottlenecks

> **一句话总结**：现有过载控制把应用当作单队列整体调节，内存带宽饱和时会连同仍有 CPU 余量的请求一起限流；Svalinn 用信用额度控制总吞吐，再用按瓶颈的 AQM 和自适应 `m_semaphore` 限制内存密集请求并发，在 Memcached、RocksDB、DataFrame 和合成负载上将 goodput 提高最高 6.51×，同时维持延迟 SLO。

## 问题与动机

服务器请求往往共享同一个二进制，但不同输入会走不同路径：小对象 GET 主要消耗 CPU，大对象 GET 会消耗内存带宽，热点写入又可能竞争锁。传统控制器依据端到端延迟、in-flight 请求数或单一资源的状态整体限流，隐含了“所有请求受同一个瓶颈队列约束”的 single-queue fallacy。一个资源达到饱和后，其他资源的可用容量便被浪费；论文在动机实验中观察到聚合机器吞吐损失最高达 83%。

内存带宽尤其难控。网络、磁盘和锁通常有显式队列，但 LOAD/STORE 指令隐式共享内存带宽。让所有线程继续运行会产生停顿，停顿线程又占用 CPU，使 CPU 看似拥塞而实际没有用于有效工作。Svalinn 的目标是在异构请求和动态请求混合下同时提高资源利用率、goodput 与延迟可预测性。

## 关键观察 / 隐含假设

- **观察 1：内存带宽瓶颈会吞噬本可服务 CPU 请求的核心。** 在合成负载中，约 6 个并发内存请求即可打满 SETUPA 的内存带宽；继续增加并发只会让线程等待，CPU 利用率反而超线性增长（图 1、图 2）。
  - **依赖假设**：内存密集路径可以被识别，并能在其入口附近插入控制点。
  - **可能失效场景**：内存访问分散在大量不可改动的代码中，或带宽需求无法由少量路径代表时，`m_semaphore` 的隔离粒度会不足。
- **观察 2：请求类型的资源需求可能由输入数据决定。** Memcached 和 RocksDB 的小值与大值 GET 走相近服务，但前者偏 CPU、后者偏内存带宽；DataFrame 的请求类型也有数量级不同的服务时间。
  - **依赖假设**：系统不需要在请求到达前准确分类，只要开发者能在执行中识别内存密集区段。
  - **可能失效场景**：请求在进入控制点前已经消耗大量资源，或者资源需求变化快于控制器收敛速度。
- **假设 1：吞吐和延迟可以由两个相对独立的控制回路优化。** 论文将总信用额度交给吞吐控制，将各瓶颈队列的排队延迟交给 AQM。该假设在其测试的微秒级 RPC 和有限瓶颈集合上证据较强，但跨资源相互反馈时仍可能出现控制回路振荡。

## 核心方法

Svalinn 将控制拆为两层。信用额度 admission controller 以服务端发放的 credit pool 约束总请求量，用两次微实验分别增加和减少额度，比较用户定义 utility。utility 可只包含吞吐，也可加入丢弃率、资源利用率等目标。控制器按实际收到的请求量重新标记两次实验，避免客户端持有 credit 却不发送请求造成错误归因；额度改变后还等待 warmup 以覆盖网络传播延迟。

每个显式瓶颈部署一个 AQM。请求进入系统时获得由 SLO 推导的排队延迟预算，经过多个瓶颈时扣除已经等待的时间。若剩余预算不足以等待当前队列，控制器在入队前丢弃请求。请求可被部分执行后丢弃，因此应用需要 cleanup callback；这也把故障处理和资源回收责任推给开发者。

`m_semaphore` 把隐式内存带宽转成显式队列。开发者在内存密集代码路径前调用 `try_wait()` 或 `wait_if_uncongested()`，在离开后调用 `post()`。前者维持零长度队列，无法立即进入的请求直接丢弃；后者允许在剩余 SLO 预算足够时排队。单例 semaphore 让多个被标注路径共享容量。

semaphore 容量由 ε-greedy 多臂赌博机在线调节。每个可能的并发核心数是一只 arm，reward 同时奖励内存带宽利用率并惩罚使用的核心数。控制器只在当前最优容量附近探索，以减少跳变；持续探索用于应对值大小等导致的非平稳需求。实验中默认 `∆t_msem=500µs`、`α=0.7`、`ω=0.8`、`ε=0.3`。

## 设计取舍

- **低延迟换取丢弃率**：`try_wait()` 在队列将形成时立即拒绝请求，适合有副本重试的服务，却可能造成基线丢弃率约 5%，并要求客户端或 sidecar 处理重试。
- **应用改动换取内存带宽可控性**：Memcached 和 RocksDB 各只需包裹一个主要路径，单个路径改动约 4–10 行；但复杂应用仍需 profiling、标注和 cleanup，不能完全透明部署。
- **通用 utility 换取调参责任**：吞吐优先 utility 可达到更高 goodput，但合成负载中丢弃率最高达 19%；加入 10% 丢弃率约束后，实际丢弃率降至 7%，吞吐也下降（图 9）。

## 实验与结果

- 合成 50/50 CPU/内存负载中，Svalinn 的 CPU 与内存请求 goodput 相比基线最高分别提高 5.06× 和 1.60×；两类请求 p99 延迟最高降低 5.95× 和 3.49×（图 4）。
- RocksDB 在 SETUPA 上的 CPU 请求 goodput 最高提高 7.62×，内存请求 goodput 提高 1.26×；p99 延迟分别最高降低 2.95× 和 1.47×（图 7）。
- DataFrame 中 CPU 请求 p99 延迟相对 SEDA 和 Protego 最高降低 42.77× 和 21.17×，CPU goodput 最高提高 3.99×（图 8）。
- 内存需求切换后，`m_semaphore` 平均约 50 ms 收敛到新的最优容量（图 11）。三瓶颈合成负载中，整体 goodput 相比 SEDA 和 Protego 最高提高 3.46× 和 2.50×（图 12）。
- 在第二套 180 GB/s 内存带宽机器上，RocksDB 的 CPU goodput 相比两种基线提高 2.65×；Go runtime 合成负载中 CPU goodput 提高 3.21×（图 13、图 14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 按瓶颈控制可释放未饱和资源的容量 | 合成负载中 CPU goodput 最高提高 5.06×（图 4） | SETUPA，CPU/内存混合请求，Shenango | 强 |
| `m_semaphore` 能将隐式内存带宽变成可控队列 | 内存并发限制后延迟保持 SLO，RocksDB CPU goodput 最高提高 7.62×（图 7） | RocksDB、Memcached、DataFrame；需人工标注路径 | 中 |
| 控制器可适应动态内存需求 | 需求切换后平均 50 ms 收敛（图 11） | 合成负载，预设三种内存访问模式 | 中 |
| utility 可表达吞吐与丢弃率取舍 | 吞吐 utility 的丢弃率达 19%，drop utility 将实际丢弃率限制在 7%（图 9） | 单一合成负载与固定参数 | 强 |

## 批判性分析

### 论证链条

论文的主链条在测量层面闭合：内存带宽饱和导致线程停顿，聚合控制器因此错误限流或继续放大 CPU 浪费；限制内存路径并发后，吞吐控制器可以利用剩余 CPU。图 4、图 7、图 8 和三瓶颈实验覆盖了多种请求混合，支持该机制解释。

但“通用资源无关控制器”的范围仍受限于已识别且可暴露的瓶颈。实验主要使用 CPU、内存带宽和锁；网络、存储 IOPS、NUMA 远端访问和多级共享缓存没有被集成验证。6.51× 的摘要级最高值也不是所有应用或所有请求类型的共同收益。

### 假设压力测试

请求丢弃后能否低成本重试是设计的重要前提。论文在双服务器实验中显示快速失败不会突破调整后的 SLO（图 10），但没有评估重复执行的副作用、写请求幂等性或跨服务链的重试放大。部分执行后 cleanup callback 也可能难以覆盖外部副作用。

MAB 依赖内存带宽计数器和稳定的容量-带宽关系。NUMA 拓扑、多个 socket 共享带宽、后台噪声或 workload 同时变化时，单例容量和邻域探索可能不再足够。论文的收敛实验使用预设切换，尚未证明面对真实生产 trace 的频繁混合变化仍能保持稳定。

### 实验可信度

基线包含经典的 SEDA 和针对锁竞争的 Protego，且报告了 goodput、p99、drop rate、不同机器和 Go/Shenango 两种 runtime。参数大多跨工作负载复用，降低了逐例调参的疑虑。另一方面，工作负载主要是合成请求、键值服务和一个固定 FX 数据集；没有生产 trace、成本模型、能耗结果的完整对比，也没有与硬件级 memory bandwidth throttling 或更强的细粒度隔离方案进行公平评测。

### 系统性缺陷

实现并非轻量级：Shenango 的 throughput controller、`m_semaphore` 和 IOKernel 修改分别增加 1815、961 和 631 行代码，应用集成还需数百至上千行。论文称主要内存路径只需少量包装，但没有量化 profiling、维护多个 cleanup callback 和升级 runtime 的运维成本。控制器也会在线做微实验，短时内可能牺牲性能；论文未系统报告控制开销、控制震荡和多租户公平性。

## 局限与后续工作

- **局限 1**：实验覆盖的资源类型有限，不能据此断言对任意隐式共享资源都有效。
- **局限 2**：`m_semaphore` 需要开发者选择内存密集代码区段；错误标注会造成欠利用或把普通请求误丢弃。
- **后续工作 1**：在 NUMA 多 socket、共享 LLC 和多级内存带宽拓扑上测量单例 semaphore 是否需要按 socket 或路径拆分，并以 p99、goodput 和公平性共同判定。
- **后续工作 2**：用真实请求 trace 测量 MAB 在连续 workload 漂移下的收敛时间、振荡次数和控制损失，并与 UCB、Thompson sampling 等策略比较。
- **后续工作 3**：评估非幂等写请求、微服务链重试和部分执行 cleanup 的正确性成本。

## 相关

- **相关概念**：[[Active Queue Management]]、[[Tail Latency]]、[[Resource Isolation]]、[[Multi-Armed Bandit]]
- **同类系统**：[[Protego]]、[[Breakwater]]、[[Caladan]]、[[Shenango]]
- **同会议**：[[OSDI-2026]]
