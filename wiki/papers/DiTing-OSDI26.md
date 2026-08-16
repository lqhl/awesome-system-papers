---
type: paper
name: DiTing
full_title: "All Along the Watchtower: Achieving the Trinity of Observability in Cloud with DiTing"
authors: [Zhenyu Ren, Shuzhi Feng, Erci Xu, Changsheng Niu, Haoyu Mao, Beibei Wang, Chong Gao, Zhenshan Zhang, Xinrui Yu, Jiangwei Huang, Jiesheng Wu, Hong Tang]
venue: OSDI
year: 2026
tags: [observability, telemetry, resource-harvesting, distributed-query, operational-systems]
source_pdf: "[[osdi26-ren.pdf]]"
source_md: "[[osdi26-ren]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# DiTing：在云中统一指标、日志与追踪（OSDI 2026）

> **原题**：All Along the Watchtower: Achieving the Trinity of Observability in Cloud with DiTing

> **一句话总结**：DiTing 利用观测查询“最近、就地”的时间和空间局部性，把近期数据与大部分查询放到百万台云节点的闲置资源上，AZ 集中层负责长期存储和失败回退；它用 co-Log 与 SQL 统一 metrics、logs、traces，在生产样本中相对内部系统把 QPS 提高 4–9 倍，并把总 CapEx 降低约 3–65 倍。

## 问题与动机

一次云故障调查通常要先看指标（metrics）确认异常，再沿追踪（traces）缩小故障范围，最后用日志（logs）定位原因。三类 telemetry 互相补充，却往往存放在三套系统里，查询语言和 schema 不同。SRE 不但要切换工具，还要写临时脚本对齐 component、location 和 time。跨系统扫描一次常见诊断所需的 100 GB 以上数据，会花数十秒甚至数分钟，远慢于事故处理期望的亚秒响应（§1、§3.1）。

把所有数据搬进一套集中式内存系统也不可行。Alibaba 的日志每天以 PB 级增长、总量达数百 PB，trace 总量接近百 PB。团队从 2022 年起把 ClickHouse 扩到 8 个 cluster、600 多台 physical node，保存约 8 PB telemetry；继续扩容时，单 service 超过一百万 partition、数千列 wide table 和大范围 scan 让部分 node memory 达约 85%，并出现 OOM。按原架构继续加 CPU/DRAM，估算会消耗整个 cloud infrastructure CapEx 的 20% 以上（§2–§3.2）。

另一个极端是完全使用 end-node idle resources。数据就地产生、就地处理，网络和专用 cluster 成本都低；但 node crash、network partition 或 tenant traffic burst 恰好会发生在最需要观测的事故期。local disk 也不能承担唯一持久副本。DiTing 因此采用中心—节点协作（Central–Node Collaboration，CNC）：正常查询尽量下推到 node，失败时由 AZ 集中层接管，而长期数据始终上传到集中存储（§4、图 6）。

## 关键观察 / 隐含假设

- **观察 1：集中式观测系统的先到瓶颈是计算和内存，不是长期存储容量。** 600-node ClickHouse 部署在 partition、wide schema、CPU/DRAM 上先失效；底层对象/文件存储每 GB 反而便宜（§3.2）。
  - **依赖假设**：telemetry 的大部分计算可以在 source node 独立完成，集中层只需聚合小结果；需要全局 shuffle 的复杂 join 会削弱这一优势。
- **观察 2：查询同时有空间局部性和时间局部性。** SRE 通常查特定 region/AZ/cluster/node 上最近一小时或一周的数据，所以 source node 既知道位置，又能缓存最热数据（§4）。
  - **可能失效场景**：跨 region 的全局趋势分析、长 retention 合规查询或没有明确物理位置的 logical entity，仍会大量使用 AZ storage 与 network。
- **观察 3：一台 server 可以产生 10K–20K 种 metric，但一次生产 query 平均只访问 11.2 个 field。** 因此 co-Log 应优化 wide-table 的随机少列访问，而不是为所有列建立同样昂贵的结构（§4.2、§5.1）。
  - **依赖假设**：热点列和查询 predicate 的 skew 长期存在；field access 变得密集时，raw metadata 与多级 index 的收益会下降。
- **观察 4：大部分 telemetry 是 append-only、single-writer，并能容忍小幅 freshness 差异。** 每个 node 可以成为自己 replica group 的固定 leader，无需完整 database transaction 或 leader election（§4.5）。
  - **可能失效场景**：security audit、billing、compliance log 若要求完整、强一致、不可抵赖，DiTing 的弱一致语义不够。
- **假设 1：harvested CPU、DRAM 和 SSD 已被业务购买，可在 CapEx 中按 sunk cost 处理。** 这是 65 倍 cost claim 的关键会计边界。
  - **证据强度**：中。内部财务审计能说明公司实际核算，但论文不计额外 power、wear、opportunity cost，也不公开绝对成本。
- **假设 2：physical-location metadata 足够及时、准确。** DiTing 宁可维护确定性 mapping，也不用 Bloom filter，因为百万 node 上 false positive 会放大 traffic（§4.3）。
  - **证据强度**：中。430K virtual disk 案例证明 mapping 很有效，但论文没有报告 stale mapping 的 false-negative rate 或更新 SLO。

## 核心方法

### 三层 CNC 架构

Global layer 是跨 AZ 入口。Global Root 不保存 telemetry，也不执行 query，只根据 Global Meta Service 中的 logical-to-physical mapping 找到目标 AZ；Global Config Service 下发 node resource limit 和 upload interval。多个 Global Root 分布到不同 AZ，避免单点（§4.1）。

每个 AZ 有一个 20–100 台专用 physical machine 的集中系统。通常 3 台 Zone Root 组成 [[Raft]] group，剩余 node 可以担当 Zone Mixer 或 Zone Leaf。Root 建 query tree，Mixer 拆分/聚合，Leaf 保存长期 co-Log 并承担 fallback execution。AZ 可把额外副本写入同 AZ 的 OSS。Node layer 上的 Data Collector 同时负责采集、近期缓存、local persistence 和上传；Node Leaf 用受限 idle CPU/DRAM 执行下推 query（图 6）。

聚合 query 需要下推到 `N` 个 node 时，fan-out 取 `min(N, 1000)`，避免 Mixer 同时聚合百万分支；纯 scan 不需中间聚合，fan-out 直接取 `N`。位置选择不用 probabilistic index，而是按 IP、hostname 中的 cluster、硬件安装位置，以及 virtual-disk-to-physical-disk mapping 精确路由（§4.3）。

失败有三条回退路径：pushdown 前若 heartbeat 已显示 node unavailable，直接交给 Zone Leaf；pushdown 后 timeout，再 reroute；node 仍可读但 CPU overloaded 时进入 fetch-only，只返回最新 raw data，由 AZ 完成计算。生产中约 1% query 走集中 fallback。Node agent 还有 CPU、memory、disk limit 和短 grace period，持续超限会被终止，但论文没有量化对 tenant p99 的隔离效果。

### co-Log：统一格式但不强求同样处理

co-Log 把三类 telemetry 暴露为 relational table 和 SQL（§4.2、图 7）：metrics 用 timestamp、location labels 和上万 measurement columns；trace 以 span ID、parent、trace ID、timestamp 和 duration 表示；log 包含 timestamp、location、severity 和 body，unstructured field 在 query 时按 regex/rule 做 schema-on-read。

文件采用类似 Parquet/ORC 的 PAX layout：file 包含固定大小 row group，row group 内按 column 划分，column 再分 page。footer 同时保存 file、row-group、column、page 四级 index，并默认索引 time 与 location。因为一次只碰约十列且热点会变化，metadata 使用可直接随机读取的 raw format，不采用 ProtoBuf/Thrift；代价是 metadata 更大。co-Log 支持 schema evolution 和 data/metadata CRC，但刻意不提供 strong ACID、array/map complex type，也不做更重的 column-level compression（表 1）。

这套统一 substrate 并不把三类数据完全同构。metrics 需要高 QPS 和 long-range aggregation；trace 行数多、常查短时间范围；log 体积最大，优先 lossless fast ingestion，重 parsing 可异步。论文在 §6 也明确把“unifying is not identical handling”列为生产教训。

### 就地 query、metadata 与近期 cache

node-side join 若仍要向 Global/AZ 取 user、disk 等 metadata，就会抵消 locality。DiTing 让用户声明可与 node 关联的 field，再按 IP 切 metadata partition，下发给对应 node。论文报告该优化将 query latency 降低 33%，node CPU 从约 45% 降到 16%，每台只增加数 MB memory（§4.3）。

node 用固定大小 memory buffer 缓存最新 telemetry。一个极端 20K metrics/server 的 workload 中，900 MiB buffer 覆盖超过 99.9% query；100 MiB 也约有 90% hit。长时间 metric query 不保留每 15 s 的 172,800 个 30-day point，而是预聚合成 1 min、5 min、1 h 的 average/sum/max/min。这个优化只用于 metric（§4.4）。

每台 node 默认每分钟上传 co-Log，直接保留会产生数十亿 small file。DiTing 先合并同 server 的 row group并保留 IP，再合并同 cluster 的 row group、按 IP 排序，在 footer 写 cluster 和 IP-to-zone map。这样减少 file count，却不丢失 fallback query 所需的空间位置（图 8）。

### 弱一致复制、完整性与可用性

每个 node 的数据形成一个简化的 Raft-like replicated unit：node 永远是 leader，没有 election；若它 down，就不会再产生该 node 的新 telemetry，旧数据仍可从 AZ/OSS 查询。node 与 AZ 的结果可能因 upload lag 略有不同，DiTing估计 staleness 并提示用户，用户可选择重跑 centralized copy（§4.5）。

CRC 覆盖 generation、network 和 disk，后台还周期 scrub 并与 OSS cross-check；nested block 用 CRC composition 避免反复读取。根据 failure-rate analysis，node+AZ 两份被估算为约 9 个 9，可选 OSS backup 后约 12 个 9。它们是模型估算，不是长时间 failure campaign 的实测可用性。

## 设计取舍

- **harvesting 换集中 CapEx**：每台 node 只用少量资源，fleet 合计却是一套 34 TB 级 distributed cache；额外 energy、SSD wear 和 tenant opportunity cost 不会凭空消失。
- **source-local execution 换大规模 agent TCB**：query 少搬数据；collection、cache、storage、query、metadata 集中在一个 agent，bug 可以在数小时内影响整个 fleet。
- **精确 mapping 换 control-plane freshness**：避免 Bloom false positive traffic；stale logical-to-physical mapping 可能漏查真正位置，风险比多查几个 node 更严重。
- **pre-aggregation 换原始分辨率**：30-day metric query 很快；想做秒级历史取证时，coarse aggregate 不能替代 raw sample。
- **统一 SQL/co-Log 换 data-type special path**：用户入口统一；metrics、traces、logs 仍有不同 schema、ingestion、index 和 retention policy。
- **弱一致 fixed leader 换简单运维**：append-only observability 足够；要求 transaction、不可抵赖 audit 或多 writer 的场景不能直接复用。
- **AZ fallback 换双份存储与 correlated-failure 风险**：node offline 仍可查；重大 incident 同时让 source node、network 和 AZ overloaded 时，论文没有给出容量保证。

## 实验与结果

- **metric microbenchmark 的硬件与口径**：数据来自 OSS 的 80-server production cluster；每次从 1,000 多列中随机查 12 列，时间窗从 5 min 到 30 days，concurrency 为 400。论文先说明 ClickHouse baseline 使用 18 台 96-core、256 GB、12×14 TB QLC SSD、2×1 TB PMEM node；DiTing AZ 只有 3 台 64-core、128 GB、12×3.5 TB QLC SSD node，但还使用 80 台 source node 的 harvested resources。紧接着，论文把图 9a 的对照称为 DiTing 的 centralized-only variant（图例写作 CK），却没有进一步解释它与前述 ClickHouse baseline 是否完全相同。约 1K QPS 时 DiTing latency 为 0.2 s，该 centralized-only variant 慢 7–82 倍；7-day case 为 0.2 s 对 18.1 s，30-day centralized query OOM。centralized side 没开 pre-aggregation，因为作者认为会增加 ingestion CPU/write latency，因此这个倍数同时包含 architecture 和 feature choice（§5.1、图 9a–c）。
- **cache、scale 与统一 query**：Figure 9 精确实测单 CPU core 约 1,500 QPS，虽然 Introduction 把结果概括为 2K；300 MB memory limit 下许多 case 仍接近。20K-node AZ 和 60K-node global query latency 分别约 0.5/0.8 s。400 concurrency 下，metric cache hit 的 latency 为 1.01–1.22 s、QPS 279–333；out-of-cache 为 9.07–9.71 s、QPS 16.0–19.3。metrics+traces+logs join 的 small/medium/large latency约 0.4/0.6/1.1 s，主要时间花在 row 数更多的 trace（§5.1、表 2、图 9d、图 9g）。
- **metadata 与 failover**：一个大客户的 430K virtual disk 分布在多 region/AZ；没有 metadata 要扫描约 1.4 PiB、耗时数十分钟，mapping-assisted pushdown 在 2 s 完成。200-node、single-thread failover test 把 offline rate 从 0% 提到 100%，1-hour metric query latency从约 0.04 s 平滑升到约 0.14 s，说明 AZ fallback 可用，但没有模拟 AZ 自身拥塞或 control-plane partition（§5.1、图 9h）。
- **production deployment**：系统已部署到全球 100 万台以上 node。一个 region 的 Service A/B 样本覆盖 300 多个 cluster、36K node 和约 600 TB AZ data；AZ 平均 1,200 QPS，node agents 合计约 40K QPS。平均每 node 使用约 0.5% DRAM、少于 2% CPU core、10–20 GB disk，36K node 合计 memory 约 34 TB。与匿名内部 Solution A 相比，50/400-node production test 中 DiTing QPS 高 4–9 倍，latency 为其 `1/10`–`1/4`（§5.2、图 10–11）。
- **CapEx 主结果**：绝对成本保密，Figure 12 以内部财务审计后的 normalized cost 比较。DiTing 的 Type I persistence cost 是 Solution A/B 的约 `1/180`、`1/6`，Type II ingestion cost 低 17.6/2.4 倍，总 CapEx 低约 65/3 倍。三者底层 long-term filesystem 相同，但 DiTing 的多值模型/co-Log 降低存储量；harvested node 已由业务购买，因此不计 Type II，这是结果成立的关键 accounting boundary（§5.3）。
- **未被充分量化的 headline**：Abstract 声称 sub-second ingestion 和 65 倍 CapEx；§5 对 query latency/QPS、deployment 和 cost 很详细，却没有给 ingestion-latency distribution、write amplification 或 incident burst loss rate。可用性 9/12 nines 也来自 failure-rate analysis，而不是本节的长期 fault measurement（§4.5、§5）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| node-local harvesting 能降低近期 query latency | 80-node metric test 中约 0.2 s，centralized path 慢 7–82 倍（图 9a–c） | DiTing 额外使用 source-node resources；centralized baseline 未开 pre-aggregation | 强 |
| physical metadata 让百万级 pushdown 可行 | 430K VD 查询从潜在 1.4 PiB scan 缩到 2 s；metadata 下推 latency 低 33%（§4.3、§5.1） | mapping staleness、false negative 和更新 traffic 未量化 | 强 |
| CNC 在 node 不可用时能保持查询 | 200 node 的 offline rate 0%–100% 时 latency 平滑升至约 0.14 s；生产约 1% fallback（图 9h） | single-thread、单 AZ；未注入 AZ/Global correlated failure | 中到强 |
| 一套系统能查询三类 telemetry | co-Log/SQL + trinity join，small/medium/large 为约 0.4/0.6/1.1 s（图 9g） | join 只按 time 做一个固定 workflow；用户诊断效率和 clock alignment 未评测 | 中 |
| DiTing 显著降低 fleet CapEx | 相对内部 A/B 总成本低约 65/3 倍（图 12） | baseline 匿名、绝对值保密、idle node 按 sunk cost 且不计 energy/opportunity cost | 中 |

## 批判性分析

### 论证链条

论文先用 600-node ClickHouse 失败说明 centralized cost curve，再用 temporal/spatial locality 解释为何 source node 有价值，最后用 AZ fallback补上“事故时 node 不可靠”的缺口，architecture 逻辑完整。co-Log、metadata routing、pre-aggregation 和 file merge 都围绕同一 locality/cost thesis。最大跳步是从 query-heavy evaluation 外推“sub-second ingestion、完整 observability trinity”：ingestion 没有同等详细指标，trinity 也只测一个固定 time join。

### 假设压力测试

若 incident 让大量 source node 和 AZ 同时 CPU/network saturated，正常只有 1% 的 fallback 可能瞬间变成 100%，而 20–100 台 AZ machine 是否有足够 reserve 未被证明。若 logical entity 快速迁移，stale mapping 不只是多发 RPC，还可能漏掉真正数据。另一个压力点是成本：idle resources 在低负载时可用，但 telemetry query 峰值往往和业务故障峰值重合，此时 opportunity cost 最高。

### 实验可信度

百万节点生产部署、真实 telemetry、36K-node统计和内部 audited CapEx 很难得；实验也主动报告单 node overhead与 100% offline fallback。可是 baseline 资源和功能不完全相同：DiTing 用 3 台 AZ node 加 80 台 harvested source，centralized configuration 有 18 台更强 node但不开 pre-aggregation。Solution A/B 匿名且成本绝对值保密，外部无法复算。缺少 ingestion、tenant p99、data loss、metadata miss 和 Global/AZ disaster recovery metric。

### 系统性缺陷

每台机器都运行高权限 Data Collector/Node Leaf，使 deployment blast radius 成为核心风险。论文的 canary、staged rollout、rollback、rate limit、circuit breaker 和 load shedding 是必要生产措施，却没有证明 agent 的 CPU/memory isolation 对 tenant tail SLO 足够。Telemetry 还含敏感 user/service 信息，跨服务统一查询需要 authentication、authorization、multi-tenant isolation 和 audit；论文几乎未讨论。CRC 能发现随机 corruption，不能防被攻陷 node 伪造 telemetry。弱一致、staleness 提示和固定 leader 对普通 debug 够用，对 security/compliance 场景则可能系统性缺数据。

## 局限与后续工作

- 在业务 CPU/network incident 与 AZ overload 同时发生时，把 fallback rate 从 1% 提到 100%，测 query p95/p99、queue growth、load shedding 和 tenant impact。
- 公开可复现的 normalized workload/cost model，把 harvested power、SSD wear、reserved headroom 和 opportunity cost纳入 TCO sensitivity。
- 测量 logical-to-physical mapping 的更新延迟、false-negative query 和 entity migration rate，并为 stale mapping 设计安全的多位置查询窗口。
- 给 ingestion 补全 p50/p99、burst loss、upload lag、write amplification 与 recovery backlog，验证 abstract 中的 sub-second claim。
- 定义 cross-source clock、identity 和 missing-span/log semantics，用已知 ground truth 的 incident replay 衡量 root-cause accuracy 与 SRE time-to-diagnosis。
- 对 node agent 做 sandbox、least privilege、signed rollout 和 fleet-level fault containment；验证单个 buggy release 不会在数小时内扩散。
- 增加 per-tenant authorization、query audit 和 sensitive-field policy，区分普通 observability 与不可抵赖 security/compliance telemetry。

## 相关

- **相关概念**：[[Observability]]、[[Telemetry]]、[[Resource-Harvesting]]、[[Distributed-Query-Processing]]
- **同会议**：[[OSDI-2026]]
