---
type: paper
name: FastACS
full_title: "Fast ACS: Low-Latency File-Based Ordered Message Delivery at Scale"
authors: [Sushant Kumar Gupta, Anil Raghunath Iyer, Chang Yu, Neel Bagora, Olivier Pomerleau, Vivek Kumar, Prunthaban Kanthakumar]
venue: ATC
year: 2025
tags: [messaging, distributed-systems, rma, file-system, low-latency, google]
source_pdf: "[[atc2025-gupta.pdf]]"
source_md: "[[atc2025-gupta]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-16
---

# Fast ACS: Low-Latency File-Based Ordered Message Delivery at Scale (ATC 2025)

> **一句话总结**：Fast ACS 的关键判断是大规模实时系统的痛点不是“消息能不能持久化”，而是数千 consumer 同时 tail-read 有序字节流会把存储和网络打成热点；它用 [[Colossus]] 做持久 single source of truth、用基于 [[CliqueMap]] 的 4KB chunk 内存 cache 和 [[RDMA|RMA]] 读吸收热尾部，在 Google Ads 生产中做到日级 p99 约 630ms、单 leaf cluster 实验峰值 1.8 Tbps，但代价是强依赖 tail-following workload、RMA 基础设施和复杂运维。

## 问题与动机

Fast ACS 解决的是 Google Ads 这类实时 serving 系统里的状态更新分发问题：producer 在少数集群产生更新，全球几十个 serving cluster 中的成千上万个 replica 需要尽快拿到这些更新，并且要保留单个 stream shard 内的顺序和 at-least-once delivery。论文明确把 exactly-once 排除在范围外，因为跨集群 two-phase commit 的工程代价和可用性风险太高。

这个问题和通用 pub-sub 的区别在于 fan-out 特别大、consumer 对自身 CPU 和延迟很敏感、并且很多 consumer 只是跟随文件尾部读取最近写入的字节。Push-based 系统会把消息处理推到 latency-sensitive backend 的关键资源上；传统 pull-based 系统如 [[Kafka]] 依赖 broker 本地文件和 broker 读路径，consumer 数量上去后读写共享存储和网络资源，很容易从“消息吞吐”问题变成“尾部热读放大”问题。

论文用一个 Google Cloud 上的 Kafka 实验说明这个瓶颈：3 个 broker、9 个非复制 partition、producer 以 240 Mbps 写 1KB message，consumer 规模增长后 consumer throughput 到 14 Gbps 左右开始退化，producer byte rate 下降到 120 Mbps。作者认为 [[Apache Pulsar]] / [[BookKeeper]] 这类大 segment 存储也会在大量 tail-reader 下遇到类似的 data-node 热点问题。

Fast ACS 的目标不是 sub-50ms messaging，而是“几百毫秒到几秒”级别的 ordered byte delivery，在 consumer fan-out 和资源成本之间找一个 production 可接受点。这个目标边界很重要：论文的设计选择优先保护高 fan-out、低成本和故障后 eventual progress，而不是追求通用消息系统的事务语义或极限低延迟。

## 关键观察 / 隐含假设

- **观察 1：大 fan-out messaging 的主瓶颈是尾部热读放大，而不是 producer 写入本身。** Kafka consumer-scaling 实验在 240 Mbps producer write rate 下，只把 consumer throughput 推到 14 Gbps 就触发读写冲突和 producer 吞吐下降；Fast ACS 的生产 ablation 也显示 data cache 不可用时，大量 consumer 直接打到 Colossus chunkserver，会出现 3-5% read unavailability，且 99% 以上来自网络拥塞。
  - **依赖假设**：consumer 大多读取最近写入的 hot bytes，历史 catch-up 可以退回持久文件系统慢慢完成。
  - **可能失效场景**：如果大量 consumer 长时间落后、需要频繁随机回放历史、或者每个 consumer 的 read window 差异很大，1 分钟 TTL 的内存 hot cache 就不能吸收主要读流量。

- **观察 2：ordered delivery 不要求网络传输也按顺序执行。** 论文把 append-only 文件切成 4KB chunk，用 hash(file path, chunk sequence) 分布到 cache replica；complete chunk 可以并行写，partial chunk 只保证 prefix 正确，consumer 再按文件 offset 顺序重组。这让全局顺序约束和底层并行传输解耦。
  - **依赖假设**：顺序语义只在单个 message stream shard 内成立，且上层协议能从 ordered bytes 中自行反序列化 message。
  - **可能失效场景**：跨 shard / 跨 stream 全局顺序、exactly-once、事务性 consumer offset commit、或者需要按 message 级别做过滤和路由的系统，不能直接套用这个 file-byte abstraction。

- **观察 3：RMA 读路径适合读多写少的 intra-cluster hot data。** Fast ACS 把 cache write 留给 RPC，把 cache read 放到 [[RDMA|RMA]]，因为集群内 consumer traffic 是读重型。实验 2(a) 中单 leaf cluster data cache read bandwidth 达到 1.8 Tbps，生产对比 predecessor 也声称 RMA 带来更稳定 tail latency 和超过三分之一的总成本节省。
  - **依赖假设**：部署环境有 Pony Express / RMA 这类高效 one-sided read 基础设施，cache server CPU 不是必须参与每次读请求。
  - **可能失效场景**：普通云环境没有可用 RMA、NIC 资源隔离弱、或者 server-side computation 必须参与每次读授权/过滤时，这个收益会明显缩水。

- **观察 4：metadata polling 会成为隐藏的 scale limit。** 文件字节读被 data cache 分散后，consumer 仍要频繁 poll metadata cache 获取 Colossus file length 和 cache file length。20,000 consumer 实验里 metadata cache 峰值达到 19.2M QPS，consumer polling interval 被迫放宽到 500ms，否则会压垮 metadata cache。
  - **依赖假设**：业务能接受 polling 带来的百毫秒级额外延迟，且 metadata key 分布足够均匀。
  - **可能失效场景**：要求更低 p99 latency、更多文件/stream shard、或者更密集 polling 时，metadata cache 可能先于 data cache 失稳。

- **假设 1：Colossus 作为持久 fallback 足以兜住 correctness。**
  - **证据强度**：中偏强。Appendix 用 TLA+ 验证了 dueling cache writers 下 safety 和 eventual progress，核心安全论证也清楚：cache chunk 若存在必须是正确 offset bytes，缺失或落后则回退到 Colossus。但模型规模很小，验证的是抽象机制，不覆盖生产调度、网络、rollout、deadlock 等实现风险。

- **假设 2：consumer 自主 pull 比 push 更适合 latency-sensitive serving backend。**
  - **证据强度**：中。论文从 Google Ads 部署经验出发，这个判断可信；但没有和现代 push / hybrid push-pull 系统做 production 等价对比。

## 核心方法

Fast ACS 把 message delivery 降成 append-only file delivery。Producer 把 message 写入 message stream，每个 stream 再按 shard 拆分；每个 shard 是一个目录，里面有按时间滚动的 chronological message files。Ads 集成中每个 shard 还有 data file 和 index file：data file 存 message contents，index file 存 offset。顺序保证来自文件 append 顺序和 consumer 对 byte stream 的顺序读取。

系统的 authority 是 [[Colossus]] 文件。Producer / writer 先把 bytes append 到 Colossus，Colossus metadata update 是原子步骤；cache 层只是 hot path mirror。这个选择回应了“volatile cache 不应承担 correctness”的假设：即使 data cache 或 metadata cache 丢状态，consumer 仍可从 Colossus 取得最终进展。

在 Colossus 上方，Fast ACS 构造两个 [[CliqueMap]] instance。Data cache 存 4KB file chunks，key 是全局唯一 Colossus path 和 chunk sequence 的 hash，value 是 chunk bytes，TTL 默认 1 分钟；metadata cache 存当前 file length 和 best-effort lock，TTL 24 小时。Data cache 只保留 hot bytes，metadata cache 提供低延迟 file length polling，避免所有 consumer 去打 Colossus Bigtable。

读路径分成 metadata polling 和 data fetch。Reader / consumer 先通过 consistent bulk read 从 metadata cache 得到 file length，再对 data cache 做 relaxed RMA read。如果 relaxed read 返回 bytes 不足，说明读到了落后的 replica，再做 consistent read；relaxed read 会在 30ms 后 hedge。即使 consistent read 仍 miss，也会把缺失 chunk 合并成一次 Colossus read，以摊薄 RPC 和 disk cost。

写路径的关键是不破坏 prefix correctness。Complete chunks 只会写一次，可以并行写；最后一个 partial chunk 可能被多个 flush 覆盖，所以必须串行，且 metadata cache 中的 length 只有在从文件开头到该 offset 的 bytes 都已经写入 data cache 后才推进。这个设计让 out-of-order chunk transfer 不影响 consumer 看到的 ordered prefix。

跨集群复制通过 copy tree 完成。每个 message stream 用 Prim-based optimizer 生成 minimum spanning tree，优化目标主要是 bandwidth cost，同时限制 tree depth 和 fan-out；典型 copy tree 最多 4 跳，可以覆盖几百个 cluster。每一跳有 reader job 和 writer job：reader poll 上游 storage、通过 long-lived streaming RPC 发 bytes，下游 writer 写入目标 cluster 的 Colossus 和 cache。

Fast ACS 刻意把 Colossus operation 和 cache operation 拆开调度。这样会把 cross-cluster bandwidth 大致翻倍，但 cache operation 不需要昂贵的 Colossus Open write lock，也能更激进地并行化。这里是典型的系统取舍：用额外网络和复制换低延迟 hot path。

消费者优先读 data cache，但不是简单读“更领先”的 storage。论文发现 Colossus 有时会短暂领先 cache，尤其是某个 copy tree hop 的 cache stream 中断时；如果立刻转向 Colossus，容易引发 chunkserver throttling。Fast ACS 因此引入 delayed Colossus reads：只要 cache 可能在 1 秒内追上，就继续等 cache；超过阈值才 fallback。

为了处理 weak-consistency scheduler 带来的 dueling writers，cache file 使用 metadata cache lock。Lock 本质是 lease，值里有 writer replica id 和 nonce；新 operation 可以 poison 旧 lock，旧 writer 发现 poison 后退出。论文强调这个 lock 是性能优化，不是 correctness 根基：即使 cache 被 clobber，Colossus 仍是安全网。

运维层面，系统依赖大量保守策略：data cache GC 在 80% capacity 开始，slab / bucket 预分配，consumer passively rate-limit 以防 producer restart 后 backlog 放大读流量，cache rollout 一次只更新同一 key-shard 的部分 replica，scheduler 与 worker 不同时 rollout。论文的 production experience 显示，这些策略和核心算法同等重要。

## 设计取舍

- **把 correctness 放在 Colossus，latency 放在 volatile cache**：好处是 cache 层可以简单、快、可丢；代价是 cache outage 会把流量打回 Colossus，造成分钟级延迟或 read unavailability。
- **用 pull + polling 保护 consumer 自主节奏**：consumer 不被 push 消息打断关键 CPU，但 metadata QPS 与 polling interval 直接进入 latency budget。实验 2 为了避免 metadata overload 把 consumer polling interval 设到 500ms。
- **用 4KB chunk 分散 hot tail**：小 chunk 与 MTU / message size 匹配，降低热点；但 slow-growing files 会反复重写同一个 partial chunk，增加 intra-cluster bandwidth。
- **用 relaxed read 优先节省资源**：多数情况下随机 replica 足够新，consistent read 只作为补救；代价是每个短读都要有正确的 fallback path，尾延迟分析更复杂。
- **用 weak lock 保可用性**：Slicer weak consistency 和 poison lease 避免强协调服务的 availability cost；代价是 dueling writers 仍可能制造性能抖动，正确性证明必须依赖 Colossus fallback。
- **copy tree 降低 WAN 成本但引入父节点放大效应**：树状复制比 source fan-out 便宜；但父 hop 延迟会传染给整棵 subtree，故障重路由还可能让 consumer 失去本地 RMA 读。
- **共享 cache 提高利用率但牺牲隔离**：当前 shared data cache 可能被单个 stream 过度使用，论文把 key-space isolation 列为 future work。

## 实验与结果

- **Kafka baseline**：3 broker、9 non-replicated partitions、240 Mbps producer、1KB messages；consumer throughput 到 14 Gbps 后 producer byte rate 掉到 120 Mbps，整体 consumer throughput 退化。这个实验支持“broker/storage 读写冲突会限制 fan-out”，但不是完整 Kafka tuning study。
- **实验环境**：所有实验跑在 shared [[Borg]]，cache replica 配 1 CPU / 8GB RAM，consumer 配 1 CPU / 4GB RAM，reader/writer 配 2 CPU / 4GB RAM；WAN 走 [[B4]]，intra-cluster 机器有 Pony Express RMA。metric 是 producer timestamp 到 monitor consumer consumption 的 message delivery delay，使用 smeared UTC，报告相对误差小于 7%。
- **Experiment 1(a), ideal fixed cache**：9 个 data cache replica、6 个 metadata cache replica，两个 source region，总 producer write rate 240 Mbps，15 个 destination clusters，120-way sharded streams，consumer 每个读 4 shard / 8 Mbps。单 leaf cluster 从 1,500 平滑扩到 7,950 consumers，data cache 峰值 70 Gbps、4.5M QPS，稳定期无 Colossus fallback，p99 delivery delay 约 500ms。
- **延迟分解**：500ms p99 中 producer buffering 和 data/index serial flush 约 120ms，network transit 约 180ms，consumer polling 和 serial index/data read 约 100ms；Fast ACS 每 hop 处理延迟约 25ms，主要是 I/O。
- **Experiment 1(b), abrupt consumer spike**：同样 setup 下 consumer 从 0 突然到 4,000，data cache read QPS 峰值 4.7M。读写共享 OS network buffers 和 bandwidth，写延迟升高，cache operation failure 增加，consumer fallback 到 Colossus，delivery delay 约增加 1s，持续约 150 秒后恢复。
- **Experiment 1(c), multi-hop spike**：在 copy tree 最长 branch 的 4 个 cluster 同时 turn up 4,000 consumers。parent hop 的 delay 会影响 downstream subtree；p99 大多低于 600ms，但 Colossus fallback 时 spike 到 1.8s。
- **Experiment 1(d), fault tolerance**：单个 data cache replica failure 时 quorum 保住，无明显 read/write failure；同一 key-shard 失去两个 replica 时 repair 期间 key-shard unavailable，Colossus fallback 达到 60,000 reads/s，latency spike 到 2s。reader/writer failure 影响较小，scheduler 约 50ms 内 reschedule。
- **Experiment 2(a), horizontal scaling**：初始 18 个 data cache replica、6 个 metadata cache replica，两个 streams 总 480 Mbps，consumer 每个读 20 shards / 80 Mbps，consumer polling interval 500ms。consumer 从 1,000 平滑增到 20,000，data cache read bandwidth 达 1.8 Tbps；data cache 从 18 扩到 481 replica，metadata cache 从 6 扩到 81 replica；scale-up re-sharding 带来 transient unavailability 和 fallback，但 monitor p99 仍低于 2.5s。
- **Experiment 2(b), abrupt scaling**：consumer 突然从 0 到 6,500，data cache 峰值 645 Gbps、metadata cache 6.24M QPS；data cache 扩到 406 replica，metadata cache 扩到 29 replica，fallback 峰值 300,000 reads/s，p99 超过 3s，约 7 分钟后恢复到 1.5s 以下。
- **Experiment 2(c), backlog recovery**：6,500 consumers、每个 consumer read rate cap 160 Mbps；producer 停 15 分钟后重启，峰值 bandwidth 超过 1.6 Tbps，持续约 2 分钟后回落到 600 Gbps。rate limit 控住 fan-out，data cache 只从 171 小幅扩到 184 replica，但 backlog 期间出现显著 delivery delay。
- **生产经验**：从早期设计到部署投入约 8 SWE-years，核心系统新增 17,500 行 non-test C++，Ads integration 又新增 7,600 行。迁移若干 Ads streams 后，按一天监控数据，p95/p99/p999/p9999 latency 分别为 500ms / 630ms / 730ms / 5.71s，最大 stream 的 p9999 为 8.59s；Colossus operation 的 opportunistic cache read hit rate 为 96%，节省 disk time。
- **成本与 predecessor**：论文声称相对旧系统，Fast ACS 在有限 fan-out 下 tail latency 更稳定，并因为 RMA 降低 server-side CPU，总成本节省超过三分之一。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Fast ACS avoids fallback under controlled steady-state fan-out | 1500→7950 consumer，70 Gbps/4.5M QPS，stable state no fallback、p99 about 500 ms（§4.1，Fig. 8） | 2 region→15 destination、120 shard、smooth ramp | high |
| Cache layer reaches Tbps reads under smooth scaling | 1000→20000 consumer，1.8 Tbps、19.2M metadata QPS、p99 below 2.5 s（§4.2，Fig. 12） | polling 500 ms、18→481 replica | high |
| Abrupt scale-up has multi-minute degradation | 0→6500，fallback 300k read/s、p99 >3 s，7 min 后 <1.5 s（§4.2，Fig. 13） | synthetic outage-like ramp | high |
| Same-key replica failures increase latency but retain access | two replica failure：60k Colossus read/s、up-to-2 s（§4.1，Fig. 11） | 4000 consumer/one leaf，非 correlated outage | high |
| Ads production monitor has long tail | p95/p99/p999/p9999 500/630/730 ms/5.71 s，hit 96%（§5） | migrated Ads stream，workload-specific | high |

## Critical Analysis

### 论证链条

论文的主线在“tail-following high fan-out ordered byte delivery”这个范围内是闭合的：Kafka/Pulsar 类系统的存储读放大问题，引出 file tail bytes 的热读 cache；4KB chunk + consistent hashing 回应 hotspot；RMA read 回应 server CPU 和 QPS；Colossus fallback 回应 volatile cache correctness；copy tree 回应 WAN fan-out 成本。实验也覆盖了 steady-state、abrupt consumer spike、multi-hop amplification、replica failure、horizontal scaling、backlog recovery 和 production rollout。

它没有证明的是“Fast ACS 是通用 messaging 系统的替代品”。作者其实承认目标不是 sub-50ms，也不做 exactly-once。更准确的 claim 是：当业务可以接受 file-byte abstraction、at-least-once、consumer-side deserialization、tail-following hot set 和 Google-style infrastructure 时，Fast ACS 能把大 fan-out 的主要成本从 disk/broker CPU 转到可水平扩展的 RMA cache bandwidth。

### 假设压力测试

最脆的 workload 假设是 consumer lag。系统把 data cache 设计成只服务 non-lagging consumers；落后 consumer 从 Colossus catch up，追上 head 后再读 cache。只要“少量落后”成立，设计很干净；但如果 region outage、large backlog、consumer restart storm 同时发生，Colossus fallback、metadata polling 和 cache scale-up 会叠加，实验 2(b) 已经显示会出现数分钟级不稳定。

第二个压力点是 metadata。Data chunks 被 hash 分散后，metadata length 仍然是每个 file 的热门 key。论文用 bulk polling、RMA 和水平扩展扛住了 19.2M QPS，但也因此把 polling interval 放到 500ms。若业务把 p99 目标从秒级压到几十毫秒级，metadata cache 可能成为新的 broker。

第三个压力点是部署可移植性。Fast ACS 的核心收益来自 Google 内部组合：Colossus、CliqueMap、Pony Express RMA、Borg priority、B4 WAN、Slicer、Monarch，以及 Ads workload 的 stream/shard 结构。论文说 ideas 可适配到其他系统，但没有给云上 Kafka/Pulsar/HDFS 的替代实现或成本模型。

### 实验可信度

主实验的内部可信度较强：setup、resource allocation、polling interval、producer rate、consumer count、QPS/bandwidth、fallback 和 latency 都给得比较具体，并且有生产经验支撑。特别有价值的是论文没有只报 happy path，也报告了 abrupt scale-up、cache replica loss、rollout bug、deadlock、bad machine、intercontinental link outage 等工程现实。

外部可信度相对弱。Kafka baseline 只是一个小规模 Google Cloud setup，不代表 Kafka 的最佳配置、tiered storage、page cache tuning、consumer batching、partition 数调优或 broker 扩容策略；Pulsar/BookKeeper 也主要是机制推断，没有同等 benchmark。论文真正强的是 Google production case study，而不是公开系统横向比较。

### 系统性缺陷

Fast ACS 最大的系统性缺陷是复杂度。论文明确给出 8 SWE-years、17.5K 行核心 C++、7.6K 行 Ads integration，并且 production 中出现过由代码复杂度导致的 bug 和数小时 latency spike。Deadlock 难以 debug，因为 cluster-local monitor 无法区分 producer stopped 和 worker deadlock；bad machines 也可能只表现为 tail latency 变差。

资源隔离也没有完全解决。Data cache 和 metadata cache 都在 shared Borg 环境中运行，读写共享 OS network buffers 和 bandwidth；abrupt load 下 write latency 被 read QPS 反压，触发 fallback。论文在 future work 中承认 shared cache 缺乏 per-stream fairness，说明当前设计仍可能出现 noisy-stream 影响其他 stream。

故障恢复是 eventual-progress 风格，不是 strict SLO 风格。单 replica failure 很好，两个同 key-shard replica failure 会 fallback 到 Colossus 并造成 2s spike；data+metadata cache 同时不可用时，系统只能低频 poll Colossus Bigtable，观察到分钟级 latency。换言之，Colossus fallback 保护 correctness，但不保证 latency。

### 读者可复用的抽象

这篇论文最值得抽取的抽象是“persistent ordered log + volatile distributed hot-tail cache + monotonic length metadata”。它比“用 RMA 加速 messaging”更泛化：只要 workload 有 append-only ordered bytes、大量 tail-following readers、允许 fallback 到持久层，就可以把 hot tail 从文件系统中剥离出来，靠小 chunk、hash distribution 和客户端重组获得 scale。

另一个可复用发现是 ordered delivery 的传输层可以乱序。系统只需要保证 consumer 暴露出的 prefix 顺序正确，而不是每个 network hop、每个 storage write 都顺序执行。这个思想在实现里靠 partial chunk serialization、metadata length monotonicity、fallback reads 和 consumer-side assembly 组合起来。

## 局限与 Future Work

- **局限 1：只覆盖 at-least-once ordered bytes，不覆盖 exactly-once message processing。** 后续可以测量在 consumer offset commit、dedup state 或 idempotent apply 参与后，Fast ACS 的端到端延迟和恢复复杂度是否仍然可控。
- **局限 2：non-lagging consumer 是核心前提。** 可客观验证的问题是：在不同 lag distribution、region outage duration、producer restart backlog 下，Colossus fallback QPS、cache miss rate 和 p9999 latency 的相变点在哪里。
- **局限 3：metadata cache 是潜在新瓶颈。** 论文提出增加 RMA endpoints、合并多个 file metadata 到单个 key。更好的后续实验是比较 per-file key、per-shard aggregated key、push-notification hybrid 三种 metadata path 的 QPS/latency/correctness 代价。
- **局限 4：shared cache 缺乏 per-stream isolation。** 论文未来工作是 key-space isolation；可以用多 stream 混部实验验证 noisy stream 是否会降低其他 stream 的 chunk availability 和 tail latency。
- **局限 5：copy tree outage 会放大到 subtree。** 可以把 routing optimizer 的目标从 bandwidth-first 扩展为 latency/SLO-risk-aware，并用历史 outage trace 比较 MST、k-redundant tree、dynamic reroute 的成本和 p999 latency。
- **局限 6：生产可观测性不足。** 论文提到 monitor 不能区分 producer stopped 和 worker deadlock。后续可以定义 per-hop liveness proof 或 end-to-end watermark 机制，让 consumer-visible staleness 能定位到 producer、reader、writer、cache、Colossus 或 network。
- **局限 7：可移植性未证明。** 一个有价值的外部验证是用 commodity RDMA 或普通 TCP/RPC cache，在 HDFS / object storage / Kafka tiered storage 上实现同样的 hot-tail abstraction，测量没有 Google 内部基础设施时还剩多少收益。

## 相关

- **相关概念**：[[RDMA|RMA]]、[[Distributed-File-System]]、[[Tail-Latency]]、[[At-Least-Once-Delivery]]、[[Ordered-Message-Delivery]]、[[Hot-Tail-Cache]]
- **同类系统**：[[Kafka]]、[[Apache Pulsar]]、[[BookKeeper]]、[[Wormhole]]、[[Cloud PubSub]]、[[ActiveMQ]]
- **依赖/内部系统**：[[Colossus]]、[[CliqueMap]]、[[Slicer]]、[[Borg]]、[[B4]]、[[Monarch]]
- **同会议**：[[ATC-2025]]
