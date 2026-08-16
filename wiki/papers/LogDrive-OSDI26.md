---
type: paper
name: LogDrive
full_title: "The LogDrive: Composable Durability for Cloud-Based Shared Logs"
authors: [Gardner Vickers, Lucas Bradstreet, Mahesh Balakrishnan, Prince Mahajan, David Mao, Xavier Léauté, Ismael Juma, Nikhil Bhatia, Jack Vanlightly, Prateek Jindal, Sumit Arrawatia, Andrew Grant, Dhruvil Shah, Dimitar Dimitrov, Gaurav Badoni, Shimiao Zhang, Yang Yu]
venue: OSDI
year: 2026
tags: [distributed-storage, shared-log, cloud-storage, durability, replication]
source_pdf: "[[osdi26-vickers.pdf]]"
source_md: "[[osdi26-vickers]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 云共享日志的可组合持久层（OSDI 2026）

> **原题**：The LogDrive: Composable Durability for Cloud-Based Shared Logs

> **一句话总结**：LogDrive 发现传统 shared-log `append` 同时决定位置与保存数据，两个 log 会给同一 entry 不同位置，所以很难像 RAID mirror 那样复制组合；它把 durability 降成“single-value address + 不保证线性一致的 `weakTail(K)`”，让 S3、DynamoDB、S3Express shim 可继续做 striping/quorum，再由带 soft-state sequencer 和 K-window 的 AtomicLog 恢复 linearizable shared log；上层 Conflux 已作为 K2 metadata service 支撑 9 GB/s produce、27 GB/s fetch，但论文的 10 倍 metadata cost 与 3 倍 total cost 是 2K write/s、6K read/s、5 倍 compression、100 ms batching 下相对 hypothetical direct-DynamoDB strawman 的模型结果，并付出约 6.5 倍 write-latency slowdown。

## 问题与动机

K2 是 Confluent 为 bulk Kafka workload 构建的 cloud-native pub-sub：broker 把多个 topic 的 data 合成大 object 写 S3，metadata 则是每个 topic 的有序 DataRef 列表。若每个 165-byte metadata update 都直接写 DynamoDB，作者估算 metadata 会占整个 K2 cloud cost 的约 75%；自己在 VM/Kubernetes 上运营 FoundationDB、ZooKeeper 或 etcd，又把 durability、upgrade 与 recovery 的复杂度带回来（§1–§2）。

shared log 看似是合适中间层：把很多小 metadata update batch/compress 成一次 cloud write，各 server 重放同一 log，在本地保存完整 materialized view，read 就不再按次付 cloud database 费用。问题是 shared-log `append(payload)` 通常由 log 自己分配 timestamp。若同一 entry 同时 append 到两个 log，它们可能返回不同位置；并发与 retry 还会产生不同顺序或 duplicate。于是 shared log 容易串接和 striping，却不能用一个轻量 wrapper 做同步 replication（§1、§2.1）。

把 sequencing 拆掉，退回普通 address space 也不够：soft-state sequencer crash 后，系统必须从分散的 cloud objects 恢复“第一个未写位置”，同时面对 concurrent in-flight write 与 hole。若要求 backend 提供 fence、conditional write 或 first-unwritten API，又失去“任意 passive cloud storage 都能实现”的目标。LogDrive 因此刻意给出比 write-once register 更弱的接口，只保留 AtomicLog recovery 真正需要的 tail 信息。

## 关键观察 / 隐含假设

- **观察 1：阻碍 replication 的不是 durability，而是每个 replica 都在 sequencing。** 两个 conventional shared log 可以都可靠保存 payload，却无法保证 append 返回同一 timestamp；用外部 timestamp 又要求 replay reorder 和重 sequencer（§1、§2.1）。
  - **依赖假设**：上层愿意把 sequencing 放进独立 AtomicLog；需要原 backend 自带 transaction/order API 的应用不直接使用 LogDrive。
- **观察 2：恢复 linearizable tail 不要求底层 tail query 本身 linearizable。** `weakTail` 只需等价于 operation interval 内对各 address 的 unordered、non-atomic scan；只要 true tail 单调，它返回的 observed tail 必落在 start/end tail 之间。AtomicLog 又让 append 严格按 address 顺序 complete，因此可把这个范围内任一点当合法 linearization point（LD.1、AL.1、§3.1、§4、附录 A）。
  - **依赖假设**：每个 address 最多写一个 value，写过不会恢复为 unwritten；同一 address 写不同 value 时行为未定义。
- **观察 3：限制 in-flight window 可把全盘 scan 变成小尾窗 scan。** application 保证 contiguous tail 与 non-contiguous tail 距离最多 `K`，backend 先求后者，再只扫描前 `K` 个 address 就能返回全部 hole（LD.2、§3.1）。
  - **依赖假设**：caller 给出的 `K` 始终正确且较小；Conflux 默认 `K=16`。错误 bound 会破坏 correctness，不只是性能退化。
- **观察 4：cloud metadata 的成本结构奖励 batching、compression 与本地 read。** DynamoDB 对每个少于 1 KB write 都按 WRU 收费；Conflux 把多条 165-byte record 合并、按 production 中观察到的压缩率建模为约 5 倍，再从每台 server 的强一致 full copy 提供 read（§2、§6.2）。
  - **依赖假设**：业务能容忍默认 100 ms batch timeout，以及每台 server 保存完整 shard state；低延迟小写 workload 不一定适合。
- **观察 5：weak common denominator 使 backend 和 RAID-like composition 都很薄。** primitive S3/DynamoDB/S3Express adapter 约 519/528/525 LoC，Striped/Quorum layer 为 194/325 LoC；同一 VirtualLog 可在线切 backend（图 12、§6.1）。
  - **依赖假设**：cloud store 的 point read/write、listing/query 与 durability semantics符合 adapter 模型，pricing/API 变化不会悄悄破坏实现。
- **假设 1：quorum replica 的 failure domain 真正独立。** 跨 AZ/region 可以提高 durability/availability，但 provider-wide control-plane bug、credential error 或 correlated deletion 不一定被多份同类 service 隔离。

## 核心方法

### 1. LogDrive：single-value address 与弱尾部

接口只有 `write(address,payload)`、`read(address)` 和 `weakTail(K)`（图 2、§3.1）。address 初始为 unwritten，一旦写入就不回退；同 value 可重复写，不允许两个不同 value 竞争同一 address。`write/read` 对 well-formed execution 是 linearizable。

令 `T` 为第一个前面全已写的 address，`N` 为最高 written prefix 后的第一个 unwritten address，二者之间像“瑞士奶酪”，hole set `H` 记录其中未写位置。`weakTail(K)` 返回 `N` 和 `H`，caller 可取 `H` 最小值（无 hole 时取 `N`）得到 observed `T`。它不保证一次原子 snapshot，只保证可解释成 call interval 内不同时间的逐 address observation（图 3、LD.1）。

### 2. 三种 cloud primitive 与 striping

S3LogDrive 给每个 drive 一个 prefix，并把 address reverse-encode 成 key，按 lexicographic list 取最后 `K` 个 slot；DynamoDBLogDrive 用 drive ID 作 partition key、address 作 sort key并反向 query；S3Express 不能有序 list，就建立 directory-like hierarchy 找 `N`，再向前扫 `K`（§3.2）。

StripedLogDrive 像 RAID-0，把 global address 轮转映射到多个 child LogDrive；`weakTail` 并行问所有 stripe，把 local address 转回 global，再合并 non-contiguous tail 与 hole。它要求 `K` 能被 stripe 数整除。Quorum 与 stripe 可任意套叠，形成类似 RAID-10 或 RAID-01 的结构（图 1、图 4、SLD.1）。

### 3. QuorumLogDrive：一轮写与 tail repair

`N` 个 replica 配置 write quorum `Qw`，write 发给全部、收到 `Qw` ack 就返回；因为 address 只有一个合法 value，不需要 ABD 那样先读再写。read quorum `Qr=N-Qw+1` 与 completed write 相交。`weakTail` 为容错需访问 `Qf=max(Qw,Qr)` 个 replica，对尾部 `K` 个 global slot逐一分类（§3.4、附录 A.5）：

- `Qr` 个 replica 都报 unwritten，判为 global unwritten。
- `Qw` 个都报 written，判为 global written。
- 信息不足但至少看到一个 value，则把同一 value repair 到 `Qw` 份，再判 written。

这让同步 cross-region `2/3` 或 `3/3` replication 仍只需一轮 write quorum，但 latency 取决于第 `Qw` 慢的 region，weakTail 还可能带 repair。

### 4. AtomicLog 把弱底层恢复成 linearizable shared log

AtomicLog 是 client library，另有一个不保存 payload 的 soft-state sequencer。append 先 `acquireSlot` 取 address，写 LogDrive，再 `completeSlot`；sequencer 只允许最多 `K` 个 in-flight slot，并让 complete 按 address order等待。append 的 linearization point 是 `completeSlot`。因此普通 `checkTail` 可直接问 sequencer，sealed/recovery slow path 才调用底层 `weakTail`（图 5、§4）。

seal bit 放在 cloud storage 的指定位置。若 sequencer unavailable，client 先 seal，之后所有 checkTail 切到 LogDrive slow path，避免 fast/slow 两个 tail source 逆序。AtomicLog 本身**不保证 append 高可用**：sequencer crash，或 client acquire 后未 complete，都会让当前 loglet 停止 append（§4）。

### 5. VirtualLog 承担故障切换

Conflux 复用 Delos VirtualLog，把多个 loglet 的 address range 串成一个高可用 shared log。当前 AtomicLog 卡住时，VirtualLog seal 它、用 checkTail 确定切换点，再把新 loglet mapping 写入一个 conditional register。这个 register 是整个系统最终且唯一的 consensus source，生产实现仍放在 DynamoDB；只是状态很小，仅 reboot/reconfiguration 时访问（图 6、§4、§5.1）。

### 6. Conflux 与 K2

每个 Conflux server 用本地 [[RocksDB]] 保存一个 shard 的完整 state，update append 到 VirtualLog 后按顺序 apply；linearizable read 先 checkTail，再追到该位置才从本地 state 返回。每 10 分钟把 snapshot 写 cloud storage并 trim log，避免恢复时从头 replay。Conflux 可 multi-master deterministic execute，也支持 primary/speculative mode（§5.1）。

K2 broker 把 data batch 写 S3，再给每个 topic 在 Conflux append 一个 DataRef。topic index 本身也是 fine-grained read-only log，Conflux 的 replication log则是 coarse-grained log，二者复用 API/test/observability wrapper。生产每个 region 有三种 Conflux service（metadata、consumer group、transaction），每个 service 再切多个 shard，每 shard通常 3–5 个 soft-state server（图 7–8、§5.2–§5.3）。

## 设计取舍

- **弱 LogDrive 语义换 backend 可实现性**：S3 不必提供 conditional write，代价是 single-value-per-address 与 correct `K` 进入 application TCB。
- **sequencing/durability 分层换恢复协议**：quorum 与 stripe 可组合，系统却多出 AtomicLog sequencer、seal bit、VirtualLog membership 和 conditional register。
- **soft-state sequencer 换简单 fast path**：普通 append/checkTail 很轻；任一卡住 slot 会让 loglet append unavailable，只能 seal 并切新 loglet。
- **batch/local materialization 换成本**：少付 API request，也让 write p99 从直接 DynamoDB 约 20 ms 增到 Conflux 约 130 ms，并在每个 replica 保存完整 state。
- **cloud durability 换 provider dependency**：server 本身无 hard state、运维简单；正确性与数据生存性依赖 S3/DynamoDB/S3Express 的实际 semantics、IAM 和 failure domain。
- **arbitrary stacking 换配置风险**：RAID-10/01、quorum size 和 region placement 能表达多种 SLA，也更容易把 correlated replicas误当独立副本。

## 实验设置

- benchmark 全在 AWS EC2/Kubernetes 上，server 用 EBS；单 region 时每 AZ 一个 Conflux server（us-west-2 示例为 4 台），client 分布各 AZ。multi-region compute 仍在 us-west-2，但同步写另外两个约 60/120 ms 远的 region（§6）。
- benchmark instance 为 `m6g.xlarge`；production server 规格未公开。cloud backend 是 S3、DynamoDB、S3Express。snapshot 每 10 分钟，batch timeout 100 ms、size threshold 60 KB、AtomicLog `K=16`，所有 latency 都报 p99。
- production record 平均 165 byte，write:read 为 1:3。成本模型固定 2K write/s、6K read/s，Conflux compression 取 5 倍；对应 data plane 假设每 record 指向 128 KB data、batch 成 5 MB S3 object，data cost 为每小时 2.37 美元（§6.2）。
- 成本/latency baseline 是**未实现的 hypothetical DynamoDB strawman**：每个 `appendDataRef` 一次 write、每个 `fetchDataRef` 一次 read。作者称它是可达 latency/cost 的 lower bound，但真实 concurrency control 还会增加工程与开销（§6）。

## 实验与结果

- **backend 可插拔性**：S3/DynamoDB/S3Express primitive 分别只需 519/528/525 LoC，Striped/Quorum wrapper 需 194/325 LoC。1:3 write:read benchmark 中，三种 backend 都能覆盖从低 load 的约 125–300 ms p99 到 14–16 KOps/s 高 load 的约 0.6–1 s p99，但曲线不是相同 durability 配置，不能只按最快点排名（图 9、图 12、§6.1）。
- **在线 composition/reconfiguration**：同一 run 依次从跨 region DynamoDB `3/3` 切到 `2/3`、S3Express `3/3`、再到 `2/3`，服务没有停机，write/read p99 随等待的 quorum 变化。S3Express `2/3` 中在约 125 秒屏蔽 us-west-2 access 后仍继续写，write p99从约 0.3 s 升到约 0.8–1 s（图 10–11、§6.1）。这是访问控制模拟的单 region storage outage，不是完整 AWS region failure。
- **metadata 成本**：2K write/s + 6K read/s 模型中，direct DynamoDB metadata 是 7.20 美元/小时，Conflux-over-DynamoDB 是 0.69 美元/小时，即约 10.4 倍更低；加同样 2.37 美元 data plane 后，总成本从 9.57 降到 3.06 美元/小时，即约 3.13 倍（图 13、§6.2）。
- **成本—延迟代价**：同一 Conflux-over-DynamoDB 配置 write p99 约 130 ms，相对 direct-DynamoDB lower-bound 慢约 6.5 倍。Conflux-over-S3/S3Express metadata cost 为 1.10/0.85 美元/小时，反而高于 Conflux-over-DynamoDB 的 0.69；所以“LogDrive 能换 backend”不等于 object storage一定最便宜（图 13、§6.2）。
- **K2 生产规模**：一个跨 3 AZ 的 deployment 有 114 个 K2 broker（108 serving）、20 个 Conflux shard、每 shard 3 server，持续约 9 GB/s produce 和 27 GB/s fetch；produce/fetch p99 约 600/300 ms，metadata `appendDataRef` p99 约 130 ms，record compression 实际约 6–7 倍（图 14–15 左、§6.3）。
- **生产迁移**：早期 K2 从 S3LogDrive 切到 DynamoDBLogDrive，一名 engineer 约一周完成 production adapter，并用 StripedLogDrive 绕过 partition-key rate limit。图 15 右展示在线切换；第一次指向错误 table 后回退 S3，再切到正确 DynamoDB，未报告数据丢失或停机，但该图也暴露 configuration mistake 是现实故障源（§6.3）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 弱 `weakTail` 足以构造 linearizable shared log | LD.1/LD.2、AL.1 与附录 A 的 striped/quorum proof；failure/delay sim-test | 假定 single value/address、linearizable primitive read/write、正确 `K`；非全栈形式化证明 | 强但前提严格 |
| LogDrive 可薄适配并组合多种 cloud backend | 图 9/12：三 primitive 约 519–528 LoC，stripe/quorum 194/325 LoC | 都是 AWS service；最终 membership register 仍在 DynamoDB | 强 |
| composition 可改变 durability/latency并容忍一个 storage outage | 图 10–11：`3/3`/`2/3` 与 DDB/S3E 在线切换，ACL outage 后继续服务 | compute 不跨 region，故障为访问控制模拟；未测 correlated loss/rebuild | 中到强 |
| Conflux 显著降低目标 metadata workload 成本 | 图 13：7.20 降至 0.69 美元/小时，总计9.57 降至3.06 | modeled 2K/6K、5 倍 compression、当时 AWS price；write 慢6.5倍 | 强但 workload-specific |
| 系统已在 K2 production 工作 | 图 14–15：9/27 GB/s、114 broker、20×3 Conflux server、约130 ms metadata p99 | 一个产品/region的观测；server规格、availability和recovery统计未公开 | 强 |

## 批判性分析

### 论证链条

论文的抽象链条闭合：先给出 shared-log timestamp 为什么阻碍 replication，再把底层语义削弱到 cloud API 可实现的程度，以 LD/AL theorem 说明弱 tail 仍能恢复 strong log，最后用三种 backend、quorum/stripe、Conflux/K2 展示 utility。理论贡献和 production evidence 相互补强。需要避免把“可组合”直接翻译成“更便宜”：实际最便宜的 Conflux backend 是 DynamoDB，S3/S3Express 更贵；10 倍来自 batching、compression 和 local read共同作用，不是 LogDrive primitive 单独带来的数字。

### 假设压力测试

如果两个 writer 给同一 address 写不同 value，LogDrive behavior 未定义；如果 bug 让 in-flight distance 超过 `K`，window scan 可漏 hole。cloud listing/query 若不满足 adapter 假定，tail recovery 可能错误而非单纯变慢。100 ms batching 对 Freight 可接受，对 transaction metadata、lock service 或低延迟 Kafka 不适用。跨 cloud/region replica 只有在 credential、operator、provider fault 独立时才提升 durability；同步 `3/3` 已在图 10 显示远 region tail latency 很高。

### 实验可信度

优点是有真实 AWS service、p99 curve、online reconfiguration、outage injection、LoC、cost breakdown 和大规模 production dashboard；append/checkTail 还有 proof 与 linearizability sim-test。弱点是 direct DynamoDB baseline 只是理想 cost/latency model，没有同 API implementation；cost 对价格、5 倍 compression、1:3 ratio 和 100 ms SLA 敏感。outage 用 ACL 模拟，没测 AZ/region compute failure、partial listing、throttling、snapshot corruption 或 rebuild。production 隐去 server规格，也没有长期 SLO violation、availability、data-loss incident与恢复时间。

### 系统性缺陷

分层并没有消灭 stateful coordination：sequencer 是单点 soft state，stuck client 可封死 current loglet；VirtualLog 要 seal/reconfigure，membership 又依赖 DynamoDB conditional register。每个 Conflux replica 保存完整 RocksDB shard，large metadata state 的 replay、snapshot、EBS cost和 compaction 没有量化。Quorum weakTail 的 scan/repair 在 failure 下可能放大 cloud requests，论文没有给 repair storm 或 rate-limit 结果。arbitrary stacking 增加配置验证需求，而 production 首次切错 table 已证明 human error 不是假设风险。

## 局限与后续工作

- **局限 1**：safety 依赖 single-value address 与正确小 `K`；违反时没有 conflict detection 或安全 fallback。
- **局限 2**：AtomicLog append 本身不高可用，sequencer/client stall 要靠 seal + VirtualLog 新 loglet恢复。
- **局限 3**：10 倍/3 倍是 workload/price model，伴随 6.5 倍 write slowdown；不是所有 backend 或 SLA 的普遍结果。
- **局限 4**：production evidence 缺 server规格、长期 availability、snapshot/replay、correlated failure 与 data-loss 审计。
- **后续工作 1**：加入 runtime `K` violation detector和不同-value write guard，故障时 fail closed并验证不会返回错误 tail。
- **后续工作 2**：注入 sequencer crash、stuck slot、partial listing、rate limit、snapshot corruption、整 AZ/region loss，报告 seal/switchover/replay 的 p99 和 request amplification。
- **后续工作 3**：对 batch timeout、compression、write:read ratio、record size 与 cloud price 做二维/三维 sensitivity，输出 cost-latency Pareto curve。
- **后续工作 4**：为 nested stripe/quorum 生成 machine-checkable failure-domain policy，阻止把同一 account/region/control plane 误当独立 replica。

## 相关

- **相关概念**：shared log、state-machine replication、quorum replication、object storage
- **相关系统**：Conflux、K2、Delos、DynamoDB、S3、S3Express、[[RocksDB]]
- **同会议**：[[OSDI-2026]]
