---
type: paper
name: BurstComputing
full_title: "Burst Computing: Quick, Sudden, Massively Parallel Processing on Serverless Resources"
authors: [Daniel Barcelona-Pons, Aitor Arjona, Pedro García-López, Enrique Molina-Giménez, Stepan Klymonchuk]
venue: ATC
year: 2025
tags: [serverless, faas, burst-computing, worker-packing, message-passing, data-analytics]
source_pdf: "[[atc2025-barcelona-pons.pdf]]"
source_md: "[[atc2025-barcelona-pons]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Burst Computing: Quick, Sudden, Massively Parallel Processing on Serverless Resources (ATC 2025)

> **一句话总结**：Burst Computing 的关键判断是 burst-parallel job 需要 job-level simultaneity 和 locality，而不是一千个彼此隔离的 function invocation；它用 flare group invocation + worker packing 把 [[FaaS]] 式并行变成可同步通信的 worker group，在 960 worker 启动上快 11.5×、PageRank 远程流量降 98.5% 并提速 13×、TeraSort 平均提速 1.91×。

## 问题与动机

论文要解决的是一种介于传统 batch cluster 和普通 [[Serverless]] function 之间的 workload：短、突然、并行度很高、数据量或参数规模由用户交互动态决定，作者称为 burst。例如 Jupyter notebook 里临时跑一次大规模 grid search、SQL / sort / PageRank、或实时流里突然变大的分析任务。它们不值得提前常驻 Spark / Dask / Ray 集群，但又希望在 1-2 分钟内完成。

传统 cluster engine 的问题是 provisioning 太慢。论文表 1 里，EMR Spark / Dataproc / Dask / Ray 的启动时间从 95 s 到 431 s 不等；相比之下，AWS Lambda 1000 个 function 大约 6 s 能起来，[[OpenWhisk]] 在作者环境里约 21 s，说明 FaaS 的 burstability 确实接近目标。

但作者认为现有 FaaS 把隔离和调度单位固定在单个 function invocation 上，正是 burst-parallel job 的根本阻碍。一个 job 里的 worker 被当成彼此无关的 tenant 请求处理，导致三类摩擦：worker 不能保证同时存在，job 被切成多轮 function stage 并靠外部 orchestration 串起来，数据和 shuffle 通信都被迫走远端存储或远端消息系统。

所以论文不是单纯优化 cold start，而是在抽象层上把管理单位从 function 提升到 job：用户发起一次 flare，平台一次性创建一组 worker，并把同一 job 的多个 worker pack 到同一个隔离环境里。这个抽象试图保留 FaaS 的按需和免运维，同时给 burst-parallel job 提供类似 [[MPI]] 的同步通信和 locality。

## 关键观察 / 隐含假设

- **观察 1：FaaS 的资源启动够快，但 worker skew 会破坏短并行 job 的有效并行性**。AWS Lambda 可以在秒级启动 1000 个 function，但论文的 960-worker 实验中，FaaS / g=1 下第一个和最后一个 worker 启动相差 18.8 s，MAD 为 2.65 s；Burst 在 g=48 时 range 降到 0.44 s，MAD 降到 0.1 s。
  - **依赖假设**：目标 job 是短生命周期且 worker 大体同步推进的 burst；如果总计算时间很长，或者 workload 本身允许异步补偿，启动 skew 的相对影响会变小。
  - **可能失效场景**：长时间运行的 batch job、straggler 主要来自数据倾斜而非启动延迟、或完全 embarrassingly parallel 且不需要全局 barrier 的 workload。
- **观察 2：burst-parallel job 的远程通信量主要由 pack 数量决定，而不是 worker 数量本身**。Broadcast 只需要每个 remote pack 收一次数据；PageRank 的 256 worker / 10 iteration 中，g=1 远程流量为 3068 GiB，g=64 降到 44 GiB，减少 98.5%。
  - **依赖假设**：worker 间存在大量重复 broadcast / reduce / all-to-all 数据，并且 pack 内 local communication 的成本远低于 remote backend。
  - **可能失效场景**：每个 worker 数据完全独立、消息很小、通信瓶颈已由直接网络或 RDMA-like FaaS backend 解决，或 remote backend 不再是主要瓶颈。
- **观察 3：大量 isolated function 重复加载代码、依赖和共享输入，会把 FaaS 的秒级启动优势吃掉**。Grid search 里 96 个 worker 都要读取同一个 S3 对象时，FaaS 等价于重复下载 96 份；Burst 让同 pack worker 协作下载并共享，1 GiB object 的下载时间从约 14 s 降到约 1 s，ready time 从 17.51 s 降到 2.57 s。
  - **依赖假设**：同一 job 的 worker 有可共享的 code / dependency / input data，且 pack 内有足够内存容纳共享副本。
  - **可能失效场景**：每个 worker 读取不同 partition，输入无法共享，或高 granularity 让单 container 的内存 / I/O / CPU 竞争超过 locality 收益。
- **假设 1：同一 burst job 内的 worker 可以共享一个更大的隔离边界**。
  - **证据强度**：中。单 tenant job 内部共享隔离边界在语义上合理，论文也用 Rust runtime 约束 shared-memory 安全，但没有系统评估 pack 内故障隔离、安全策略、side effect 隔离或 noisy worker 对同 pack 其他 worker 的影响。
- **假设 2：平台能为一个 flare 同时预留一组资源，并通过 granularity 管住利用率和碎片化**。
  - **证据强度**：中偏弱。作者在 EKS + OpenWhisk 原型上证明了可实现性，并讨论 mixed packing 减少 fragmentation；但真正 public cloud 下，多租户排队、billing、公平性、quota、spot-like 资源波动都没有实验覆盖。
- **假设 3：目标应用多数是短、同步、协作式 MPP job，而不是高 variance task bag**。
  - **证据强度**：中。PageRank、TeraSort、grid search 都符合这个画像；论文也承认 worker duration 差异大时 pack-level reclaim 会浪费资源，动态 pack sizing 是 future work。

## 核心方法

Burst Computing 引入两个核心原则：**group awareness** 和 **locality exploitation**。Group awareness 通过 flare 实现：用户不再发出 n 个 function invocation，而是发一次 group invocation，让平台知道这些 worker 属于同一 job。平台因此可以保证 worker 同时运行、给每个 worker 下发同一个 burst context，并把隔离边界从单 function 提升到 job / pack 级别。

第二个关键设计是 worker packing。一个 burst 有 n 个 worker，平台把它们放进 m 个 pack，granularity 为 g = n / m。g 越大，需要创建的 container 越少，code / dependency / input data 的重复加载越少，pack 内 worker 之间也可以通过 local channel 通信。作者讨论了三种 packing 策略：heterogeneous 最大化 locality 但容易碎片化，homogeneous 简单但限制 locality，mixed 用小 pack 做资源分配、同机合并成更大 container，是论文认为更适合 provider 的折中。

编程模型上，burst definition 类似一个 function，但 work 函数会在每个 worker 上运行，并收到 `BurstContext`。这个 context 暴露 `workerID`、`burstSize`、`packID`、`packSize`、`numPacks`、`belongToPack()`、`isPackLeader()`，让代码可以在不显式管理机器的情况下知道自己的局部性。这个选择回应了观察 2 和观察 3：应用能写 pack-aware 数据加载或 collective 通信，但资源放置仍由平台决定。

通信由 BCM（Burst Communication Middleware）提供，接口类似 [[MPI]]：`send` / `recv` / `broadcast` / `allToAll` / `reduce`。BCM 对程序隐藏 locality：同 pack worker 走 local zero-copy，跨 pack worker 走 remote backend。这样，broadcast 只需每个 pack 远程接收一次，然后 pack 内共享；reduce 的低层 tree level 可以在本地完成；all-to-all 也能把同 pack 的那部分通信留在本地。

实现上，作者基于 [[OpenWhisk]] v1.0.0 改了约 2K SLOC：controller 新增 `deploy` 和 `flare` endpoint，负责 burst definition 注册、worker allocation 和 packing；invoker 改为按 CPU 监控和创建 pack container；runtime 基于官方 Rust environment 修改，一个 pack 内为每个 worker 开一个 thread。原型里每个 worker 分配 1 vCPU，container 当前不会跨 burst 复用。

BCM 本身约 5K SLOC Rust。Local path 中，同 pack worker 是同一进程内的 thread，BCM 用 in-memory queue 和 pointer passing 做 zero-copy，依赖 Rust memory safety 和 reference counting 管住共享只读数据。Remote path 中，每个 pack 维护连接池，大消息按 chunk 并行读写；backend 支持 Redis、DragonflyDB、RabbitMQ 和 S3，并对 direct message 与 broadcast message 分开优化。为避免消息丢失或乱序，BCM 依赖 backend 的 delivery guarantee，并给 direct / collective message 加 counter、chunk header、duplicate filtering 和 out-of-order cache。

## 设计取舍

- **job-level isolation 换 group scheduling / locality**：收益是平台终于能把 worker 当作一个协作 group 来调度，代价是 FaaS 原本极简单的 per-invocation 隔离、计费和失败边界被放大，provider 需要新 scheduler 和新 billing 语义。
- **高 granularity 换更少 container 和更少 remote communication**：g 越大，启动和通信越快；但大 container 更难放置，也更容易在 worker duration 不均衡时造成 pack 内 idle resource。
- **low-level message passing 换表达能力**：`send` / `recv` / collectives 足以写 PageRank、TeraSort 这类协作式 job，也能让上层框架构建 DAG；但普通 serverless 用户必须面对 worker ID、collective matching、deadlock 和 failure handling。
- **间接 remote backend 换部署简单性**：Redis / DragonflyDB / RabbitMQ / S3 让原型容易落地，也贴近 FaaS 文献里的 state sharing 方式；但 pack-to-pack 路径仍受一个外部 backend 的吞吐、尾延迟和故障模式限制。
- **Rust thread-based pack 换 zero-copy 简洁实现**：同进程 thread 让 pack 内 communication 很干净；但它把 prototype 的最佳路径绑定到 Rust runtime，Python binding 仍在进行，跨语言 runtime 的安全和性能没有验证。

## 实验与结果

- **资源启动时间**：表 1 中，960 worker 的 Burst Computing 启动时间为 1.7 s；AWS Lambda 约 6 s，OpenWhisk 约 21 s，Knative 54 s / 229 s，Spark / Dataproc / Dask / Ray 类方案为 95-431 s。
- **worker group invocation**：960-worker burst 中，g=48 相比 g=1 / FaaS 的 all-worker-ready latency 快 11.5×；启动 range 从 18.8 s 降到 0.44 s，MAD 从 2.65 s 降到 0.1 s。
- **共享数据加载**：96-worker grid search 读取同一个 1 GiB S3 object 时，Burst 的 pack-aware parallel download 让数据下载时间从 FaaS 的约 14 s 降到约 1 s；500 MiB Amazon reviews 数据集上 ready time 从 17.51 s 降到 2.57 s。
- **remote backend microbenchmark**：1 GiB point-to-point payload 中，Redis / DragonflyDB 在 1 MiB chunk 时最好；并发 worker 增大后，DragonflyDB List 可超过 2.5 GiB/s aggregate throughput，而 RabbitMQ 大约不再超过 1 GiB/s，S3 虽能随并行扩展但整体较慢。
- **collective communication**：Broadcast 的 remote traffic 与 pack 数近似线性相关，g=48 时 latency reduction 接近 98%；All-to-All 的收益取决于 burst size 与 pack 数，48 worker / one pack 可接近 100% reduction，96 worker / two packs 约 50%，192 worker / four packs 约 25%。
- **PageRank**：50M node、约 30 GiB graph、256 partition、10 iteration；g=64 相比 g=1 总执行时间提速 13×，远程流量从 3068 GiB 降到 44 GiB，减少 98.5%。主要收益来自 communication phase 缩短。
- **TeraSort**：100 GiB dataset、192 partition；serverless MapReduce baseline 需要 map / reduce 两轮 function invocation 和 object storage shuffle，Burst 用单次 flare + locality-aware all-to-all，单次示例约 2×，6 次平均 1.91×。
- **Spark 参照**：同等资源 Spark on AWS EMR 跑 TeraSort 的纯执行时间约 100-110 s，介于 FaaS 和 Burst 之间，但 cluster creation 额外超过 5 min；论文也承认这里有 Scala vs Rust、Spark direct communication vs Burst indirect backend 等不可直接归因的差异。

## Critical Analysis

### 论证链条

论文的主链条比较完整：先把 FaaS 用于 burst-parallel job 的问题拆成 F1 worker isolation、F2 job fragmentation、F3 data movement；再用 flare 解决 group awareness，用 packing 解决 locality，用 BCM 把 locality 转化为 collective communication 的减少远程流量；最后用 invocation、collective microbenchmark、PageRank、TeraSort 和 grid search 逐段验证。

最强的证据是 PageRank 和 collective：这里 communication 是主瓶颈，pack 数下降直接推导到 remote traffic 下降，实验也几乎按这个模型变化。TeraSort 的证据也有说服力，因为它把两轮 serverless MapReduce 和 object-storage shuffle 合并成单 flare + all-to-all，结果 timeline 很清楚地展示了 orchestration gap 和 startup skew 的消失。

较弱的跳步在于“这是一个新的 cloud service model”这个 claim。原型证明 OpenWhisk 可以改成支持 flare 和 packing，但 public cloud 的多租户调度、quota、公平性、billing、pack 内隔离和 provider 资源利用率都还停留在讨论层。论文证明了 substrate 有价值，但没有完整证明它能以 FaaS 的运营复杂度和可用性上线。

### 假设压力测试

workload assumption 是最关键的：Burst 适合短、突然、协作式、同步推进的 MPP job。若 job 是长时间 batch，提前启动 cluster 的摊销成本会变低；若任务执行时间高度不均衡，pack-level reclaim 会让快 worker 的资源被慢 worker 拖住；若 workload 只有少量共享输入和少量通信，packing 的收益也会明显变小。

resource bottleneck assumption 是 container creation、重复数据加载和 remote communication 主导。论文在 PageRank / TeraSort / grid search 上成立，但如果未来 FaaS 平台提供 direct function networking、RDMA-backed state sharing、或更强的 function fusion，Burst 的优势会从“解决不可行”转成“是否还能足够简化编程和运营”。

hardware / deployment assumption 也比较具体：实验在 AWS us-east-1，用 EKS 上的改造版 OpenWhisk，最多 20 台 c7i.12xlarge invoker，communication server 使用 c7i.48xlarge。结论对类似 cloud VM + container runtime 的环境有参考性，但对真实 AWS Lambda / Google Cloud Functions 内部 scheduler 是否可行，只能算间接证据。

scaling assumption 没有被完全压穿。Invocation 展示到 960 worker，communication backend 展示到 384 worker，PageRank 256 worker，TeraSort 192 worker。对于更大规模、更多 concurrent flares、多个 tenant 同时争抢 pack locality、或 backend server 故障，论文没有给出 tail latency 和 saturation 行为。

correctness / SLO assumption 主要在 BCM 层有基础设计，但缺少系统实验。BCM 处理 duplicate / out-of-order / chunked message，并提供 at-least-once 语义；然而 worker failure、pack failure、backend failover、collective timeout、partial retry、observability 和 deadlock diagnosis 都未被量化。

### 实验可信度

实验设计覆盖了从机制到应用的路径：先测 startup / simultaneity，再测 remote backend，再测 collective，最后跑三类应用。这比只给 end-to-end speedup 更可信，因为能看到 g 增大到底影响了哪一段。

baseline 的选择总体合理但不完美。FaaS baseline 代表当前 serverless data analytics 文献里的 state-of-practice；Spark 作为 cluster baseline 也被提及。但 TeraSort 里 Spark、FaaS MapReduce 和 Burst 的语言、runtime、communication path 都不同，论文自己也承认归因复杂。因此 TeraSort 更适合读成“Burst 抽象能避免 serverless MapReduce 的结构性开销”，而不是严格证明 Burst runtime 比 Spark engine 更快。

benchmark 代表性中等偏强。Grid search、PageRank、TeraSort 分别覆盖共享输入、迭代 reduce / broadcast、shuffle-heavy workload，正好对应论文的三类 friction。但它们仍是作者选出来适合 burst model 的 workload；论文没有 production trace、真实多租户混部、SQL engine、k-means、stream burst、或非 lockstep task bag 的结果。

metric 覆盖了 latency、traffic、throughput 和 startup dispersity，但缺 cost / billing / utilization。对于 serverless model，成本和 provider-side utilization 是一等指标；如果 high granularity 提升用户延迟但降低 provider packing efficiency，cloud service 的经济性可能和论文用户侧性能不同。

### 系统性缺陷

最大的系统缺口是 scheduler / resource management。论文说 mixed packing 可以兼顾小块资源管理和 locality，但没有展示多 tenant、多个 concurrent burst、quota、preemption、fairness 或 fragmentation 随时间累积的实验。对于云服务来说，这些可能比单 job latency 更难。

第二个缺口是 failure model。Burst 把 worker 同时性和 collective communication 作为语义基础，一旦某个 pack 或 backend 出问题，整个 job 可能被 collective 卡住。论文没有说明是否做 worker retry、pack replacement、collective cancellation、partial progress recovery，或者如何向用户暴露失败。

第三个缺口是编程和调试复杂度。作者把 Burst 定位为 low-level primitive，未来可在上面做 DAG engine；这符合 worst-is-better 的简单实现路线，但用户今天得到的是 MPI-like API。对 serverless 用户来说，message matching、worker ID 分支、collective order、共享数据生命周期、debugging 和 observability 都是新负担。

第四个缺口是 pack 内资源隔离。虽然同一 job 属于同一 tenant，但 pack 内 worker 共享 process / runtime / memory path，论文未讨论某个 worker 内存膨胀、CPU busy loop、panic、unsafe code、或 language runtime GC 对同 pack worker 的影响。Rust 减少 memory safety 风险，不等于解决 performance isolation。

## 局限与 Future Work

- **局限 1**：没有真实 public cloud 多租户调度与 billing 实验；Future work 可以构造 concurrent flare trace，比较 homogeneous / heterogeneous / mixed packing 在 utilization、fairness、queueing delay 和 locality 上的 Pareto frontier。
- **局限 2**：应用主要是短、同步、协作式 job；Future work 应测量 worker duration skew、data skew 和 straggler 下的 pack-level idle resource，并设计动态 pack resizing 或 pack 内 work stealing。
- **局限 3**：remote communication 仍依赖 centralized indirect backend；Future work 可以把 FMI、RDMA、direct TCP / QUIC 或 near-data backend 接成 BCM remote backend，比较吞吐、tail latency、failure recovery 和 provider 可部署性。
- **局限 4**：低层 message-passing API 对普通 serverless 用户偏硬；Future work 应在 Burst 上实现一个最小 DAG / SQL / Spark-like runtime，验证能否隐藏 worker ID 和 collective ordering，同时保留 flare 的启动与 locality 收益。
- **局限 5**：failure handling 和 correctness 只在设计层讨论；Future work 需要注入 worker crash、pack crash、backend restart、duplicate message、slow worker，给出 collective timeout / retry / recovery 的语义和代价。
- **局限 6**：缺少成本模型；Future work 应把用户侧 billed duration、backend cost、provider stranded resources、pack fragmentation 和 cold/warm reuse 一起建模，而不是只看 wall-clock speedup。

## 相关

- **相关概念**：[[FaaS]]、[[Serverless]]、[[MPI]]、[[Cold-Start]]、[[Worker-Packing]]、[[Granular-Computing]]
- **同类系统 / 机制**：[[OpenWhisk]]、AWS Lambda、[[Spark]]、Dask、Ray、Knative、Wukong、Pocket、Cloudburst、FMI、Faasm、SAND、MXFaaS、ProPack
- **同会议**：[[ATC-2025]]
- **可对比论文**：[[AFaaS-OSDI25]] 关注 production serverless cold start；[[RTSFaaS-ATC25]] 关注 stateful FaaS transaction 的 RDMA + lease；[[Cosmic-ATC25]] 展示 Lambda 上的 deadline-driven burst workload；[[DShuffle-ATC25]] 从 DPU 侧优化 Spark shuffle。
