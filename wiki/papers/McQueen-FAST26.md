---
type: paper
name: McQueen
full_title: "McQueen: Apple's Geo-Distributed Object Store at Exabyte Scale"
authors: [Benjamin Baron, Aline Bousquet, Eric Metens, Swapnil Pimpale, Nick Puz, Marc de Saint Sauveur, Varsha Muzumdar, Vinay Ari]
venue: FAST
year: 2026
tags: [object-store, geo-replication, erasure-coding, production, apple]
source_pdf: "[[fast2026-baron.pdf]]"
source_md: "[[fast2026-baron]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# McQueen: Apple's Geo-Distributed Object Store at Exabyte Scale (FAST 2026)

> **一句话总结**：Apple 在「多租户、对象大小跨 5+ 量级、读多写少且 CDN 分流」的 workload 下，用 stamp 内 (20,2,2) [[Local-Reconstruction-Codes|LRC]] + 跨 region 5-way XOR parity 的两层编码，把 geo-replicated object store 的 replication factor 从 2.40 压到 1.50，代价是 full-object GET 约 +50 ms 跨 region 延迟，但生产 10+ 年、EB 级数据仍满足 durability/availability SLO。

## 问题与动机

Apple 的 [[iCloud]]、Apple TV、Apple Music、Apple Maps 及大量内部服务，需要一个能同时服务用户侧与内部 analytics 的 [[Object-Store]]：对象从 KB 级缩略图到 GB 级视频跨多个量级，日请求量达 billions，且用户期望数据「永远在线、永不丢失」。业界常见方案（[[S3]]、GCS、[[Ceph]]、Facebook [[f4]]、[[Tectonic]] 等）多在单 region 或有限 geo-replication 上权衡 cost vs. availability；Apple 的约束更苛刻——必须在自有数据中心、跨北美多 region 部署，同时控制存储成本与运维复杂度。

McQueen 1.0（2013）用双 region active-active + stamp 内 [[Erasure-Coding]] + 跨 stamp 全量异步复制，支撑了十年生产，但暴露出三类结构性瓶颈：**存储成本**（(20,2,2) LRC × 2× 跨 region 复制 → RF 2.40）、**store lifecycle**（每 store 容量固定、客户端需管理多 endpoint/credential/quota、下线需逐对象迁移）、**metadata 全局扩展**（双 [[Cassandra]] 有热点、LIST 慢、缺跨 stamp 强一致）。McQueen 2.0 的目标不是重写存储引擎，而是在保留 stamp/LRC/container 核心路径的前提下，用更省空间的跨 region 编码、统一 endpoint 和自研 metadata（ClassVI）解决规模化与成本问题。

## 关键观察 / 隐含假设

- **观察 1：Apple workload 高度异质，但多数读流量已被 [[CDN]]/PoP 分流，McQueen 直接承载的是「写路径 + 非缓存读 + 内部低延迟 DC 内访问」**。
  - **依赖假设**：Media/Maps 等大对象读极少打到 McQueen；iCloud 照片/视频在写入后短期内高频读删，但长期 tail 由 CDN 承担；内部 workload 更看重同 DC 低延迟而非跨大陆 full-object 读。
  - **可能失效场景**：若 CDN 命中率下降、或 live streaming/新服务绕过 CDN 直连 McQueen，2.0 的跨 region segment fetch 会成为主导延迟；论文对这类 workload shift 未做压力测试。

- **观察 2：跨 region 全量复制是 1.0 存储成本的主导项；对象可被切成等长 segment 并用 bitwise XOR 做 regional parity，可在单 region 故障时仍可服务 GET/PUT**。
  - **依赖假设**：对象 PUT 时必须提供完整 object length（含 multipart）；segment 大小可预知；5 个 region 中任意 4 个可用即可完成写；网络带宽足以在 PUT 时并行写 5 个 segment。
  - **可能失效场景**：**双 region 同时故障**时 2.0 完全不可用（1.0 在单 region 故障时仍有完整副本）；极大对象或极差跨洋带宽时，PUT 的 4-of-5 quorum 可能频繁触发异步补 segment（虽论文称仅 0.01%）。

- **观察 3：metadata 变更频率远低于 data 读——仅在 PUT、rebalance 时更新，因此 optimistic inconsistent read + prefetch 在 99.99995% GET 上可安全加速**。
  - **依赖假设**：ClassVI 更新传播足够快；0.001% metadata mismatch 的丢弃 prefetch 成本可接受；客户端可容忍 eventual consistency 的 metadata read（强一致读仍并行发起）。
  - **证据强度**：**强**——生产一个月全量 host 统计，有具体 mismatch 比例与 TTFB 对比。

- **假设 1：HDD + JBOD + 大 container（4–32 GiB）+ sealing 后 immutable 的模式，在 EB 规模下仍是最 cost-efficient 的存储介质组合**。
  - **证据强度**：**中**——十年生产验证，但结论明确承认下一代更大容量磁盘将挑战 maintenance IOPS；论文未量化 SSD/NVMe tier 或 EC 与 replication 混合 tier 的 TCO。

- **假设 2：region 故障相互独立，可用 binomial 模型估算 degraded（单 region down）与 unavailable（≥2 region down）状态时长**。
  - **证据强度**：**弱**——模型用于设计选型（Table 3 XOR-5 vs XOR-6 tradeoff），非生产故障相关性实测；现实中 correlated failure（电力、骨干网、软件发布）可能使「双 region 同时不可用」概率高于独立假设。

## 核心方法

**架构骨架（1.0 → 2.0 延续）**：McQueen 以 **stamp** 为基本部署单元（每 stamp ~500 PiB raw，含 compute host + storage host + JBOD）。客户端走 [[S3]]-compatible API；请求经 DNS → 公网 load balancer（TLS 终止）→ request handler（checksum、加解密、签名校验、rate limit）→ storage layer。对象按 256 KiB chunk 流式写入 **container**（大文件，聚多对象）；新写入走 5-replica replicated cluster，写满后 **sealing** 生成 (20,2,2) [[Local-Reconstruction-Codes|LRC]] parity container 并 immutable，回应观察 2 中「热写用复制、冷数据用 EC」的成本优化。

**McQueen 1.0 的 geo-replication**：每个 store = 两个地理分离 stamp，active-active；stamp 内 LRC 抵御 disk/host/rack 故障（4 container 失败 86.15% 可恢复），跨 stamp **全量异步复制**保证单 region/stamp 维护时可 failover proxy。GET 走 degraded read 链：本地 container → LRC local/global parity → 对端 stamp，多源并行、先返回者胜出。

**McQueen 2.0 的核心设计——Cross-region XOR-5 segmentation**（回应观察 2）：将每个对象（及 multipart 的每个 part）切成 **4 个等大 data segment + 1 个 bitwise XOR parity segment**，分布到 5 个 region。RF_regional = 5/4 = 1.25，配合 LRC RF_local = 1.2，总 **RF = 1.50**（vs 1.0 的 2.40）。PUT 向 5 个 region 并行发 segment，**≥4 成功即返回**；缺失 segment 由后台异步 XOR 重建。GET full object 需拉齐 4 个 data segment（或 3 data + parity 重建）；range read 优先只读对应 data segment 的字节范围，仅在 segment 不可用时才跨 region 拉全 segment 做 XOR。

**ClassVI metadata**（回应 1.0 metadata 瓶颈）：自研 [[BigTable]]-like 分布式 KV，[[RocksDB]] 本地引擎，跨 region [[Raft]] 保证 **row-level 强一致**；默认允许本 region 单副本 **inconsistent read** 换延迟（trade-off eventual consistency）。PUT 完成全部 segment 后一次性写入 segment location metadata。

**统一 endpoint 与弹性扩展**（回应 store lifecycle 痛点）：单一 DNS 名，权威 DNS 按客户端地理位置解析最近 region 的 load balancer IP；stamp 权重由可用磁盘容量驱动，**rebalancer** 以 sealed container 文件级拷贝在 stamp 间搬数据（避免重走 transaction log + sealing 的 CPU/IO）。两层 rate limiter：deployment-level（segmentation 前保护全局）+ stamp-level（保护单 stamp 存储资源）。

**运维与迁移**：1.0→2.0 迁移分五阶段（client 配置 → 异步对象迁移为 segment 布局 → checksum 校验 → 请求 proxy → DNS cutover），数 EB 数据、数年完成、零 downtime。latency 优化包括 DNS geo-routing、metadata prefetch、segment regional preference（优先选 RTT 最小的 4 segment，常意味着读 parity 做本地 XOR 而非跨洋拉 data）；inter-stamp 流量过大时 **bypass load balancer**（p50 GET latency −22%）。

## 设计取舍

- **存储成本 vs 读延迟**：XOR-5 把 RF 从 2.40 降到 1.50，但 full-object GET 在 1 MiB/10 MiB 上比 1.0 慢约 **50 ms**（跨 region RTT）；TTFB 略高。作者用 CDN 分流、metadata prefetch、regional segment 选择部分对冲，但 latency-sensitive 流量需单独 endpoint。
- **可用性 vs region 数量**：更多 region 降低 RF（XOR-N 的 RF = N/(N−1)），但 Table 3 显示 degraded/unavailable 年时长随 N 增加；XOR-5 是在 durability MTTDL、99.999% SLO 与成本间的定点选择。
- **PUT 耐久 vs 尾延迟**：4-of-5 quorum 允许最快 4 个 segment 确认后返回，第 5 个 best-effort；99.99% 在 PUT 路径完成全部 segment，异步补复制 lag 比 1.0 全量跨 stamp 复制小几个数量级，但存在短暂「未完全 geo-redundant」窗口。
- **Metadata 一致 vs 读性能**：inconsistent read + prefetch 在 0.001% 请求上浪费 prefetch IO；放弃 multi-row 分布式事务，简化设计但限制复杂原子元数据操作。
- **边界条件**：单 region 故障下 2.0 可 degraded 服务；**≥2 region 故障则读写均失败**（1.0 在单 region 故障时仍有完整对象副本）。LRC degraded read 在 >p50 可增加 30 ms–数百 ms。论文未讨论 encryption key 管理、tenant 隔离、合规删除等细节。

## 实验与结果

- **规模**：生产 10+ 年；多 EB 数据；日 billions 请求；2.0 部署 5 region，每 stamp ~500 PiB raw。
- **RF**：1.0 (20,2,2) LRC + 2× cross-stamp = **2.40**；2.0 (20,2,2) LRC + XOR-5 = **1.50**。
- **延迟**（一个月生产流量，Section 6.2 优化后）：GET TTFB 两系统接近，2.0 略高；PUT 1 MiB/10 MiB 与 1.0 相当；full-object GET 2.0 慢 ~50 ms。
- **Replication lag**：1.0 跨 stamp 复制 90% 对象 <10 s；2.0 仅 0.01% segment 需异步复制，lag 小几个数量级。
- **故障路径开销**：跨 region XOR 重建 p90 **0.3 ms** CPU，GET +10 ms（无 stamp failover）至 +50 ms（failover 时）；stamp 内 LRC 重建 p90 **2 ms**，degraded read +30 ms（至 p50）至数百 ms（>p75，受 500 ms local parity timeout 影响）。
- **Metadata**：99.99995% GET 仅需 inconsistent metadata read，无额外延迟；0.001% mismatch 需丢弃 prefetch。
- **Durability 模型**：XOR-5 regional MTTDL ~1.31×10²¹ 年（仍满足「11 nines」量级 SLA），低于 1.0 全复制的 ~1.32×10²²，但作者认为仍远超业务需求。

## Critical Analysis

### 论证链条

论文的 observation → design → result 链条在 **成本与规模化** 维度较闭合：1.0 十年生产数据证明 workload 多样性与 LRC+复制路径可行；1.0 的 RF 2.40 与 metadata/store 碎片化是直接 measured pain point；2.0 的 XOR-5、ClassVI、统一 endpoint 逐一对应；生产一个月 latency/durability 指标支持「可运行且更省空间」。薄弱环节在于 **把 CDN 分流下的延迟表现外推为整体 SLO 满足**：Figure 6 的 GET 对比已承认 2.0 workload 对象 size 分布因迁移而不同，跨系统对比并非严格同分布；50 ms 惩罚对「非 CDN 读」是否可接受，论文用单独 latency-sensitive endpoint 回避而非量化主路径占比。

迁移叙事（数 EB、零 downtime）强化可信度，但 **verification 与 proxy 阶段的长尾对象**、迁移期间双写/双读一致性边界，仅靠 checksum 校验概括，缺少 conflict rate 或 rollback 案例。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 5 region 中最多 1 个同时长期不可用 | 模型 + 故障读取路径微基准 | 相关故障、控制面 bug 导致多 region 失联；PUT 4-of-5 期间再丢 region |
| CDN 吸收大部分 read | workload 表（Media/Maps GET 占比低） | 新产品的 edge-less 读；CDN 故障回源洪峰 |
| XOR segment 等长且 PUT 前已知 size | 设计约束 | 流式上传未知长度对象（若客户端不遵守 header 约束） |
| ClassVI inconsistent read 足够新 | 99.99995% 统计 | 高频 metadata 更新 workload（论文称极少）；rebalance 期间 mismatch 上升是否仅 0.001% 未分场景给出 |
| HDD/container sealing 仍最优 | 十年运营 | 高 IOPS 小对象、AI checkpoint 等随机写密集 workload；结论自述大容量盘将恶化 maintenance IOPS |

### 实验可信度

- **优势**：真生产、全 host、一个月窗口、latency CDF 与 replication lag 有统计量；1.0 vs 2.0 对照有同公司运维上下文，比纯仿真更有外部效度。
- **局限**：**无第三方可复现**；baseline 是自家上一代而非 S3/GCS/f4；durability 主要靠 Markov MTTDL 模型（λ=0.02、修复 T=1 年等保守/简化参数），非注入故障实验；availability 用独立 region 二项分布，未用真实 outage trace 校验 Table 3 的 degraded 秒数。
- **Ablation**：latency 优化（prefetch、regional preference、LB bypass）在 Section 6 讨论但未给逐项消融百分比；XOR-4/6 仅在 Table 3 模型出现，生产为何选 XOR-5 的 sensitivity 分析有限。

### 系统性缺陷

- **尾延迟与多租户隔离**：rate limiter 架构有描述，但 **跨 tenant noisy neighbor**、stamp 级 throttle 对 SLO 的影响未量化；LRC degraded read >p75 可达数百 ms，对延迟敏感 iCloud 子服务的影响未分层报告。
- **故障恢复与运维**：repair 有 30 min grace period、双路径 corruption scan，但 **region 级灾难恢复 RTO/RPO**、async segment 补全 backlog 在 prolonged degraded 下的增长未建模。
- **可观测性与正确性**：checksum + metadata 校验为主；**拜占庭/静默数据损坏跨 XOR segment** 的端到端验证流程未展开；ClassVI row-level 一致但无跨对象事务，multipart commit 失败后的垃圾 segment 回收策略未细述。
- **安全与合规**：at-rest encryption、TLS 全链路有提及，但 key rotation、tenant 级加密域、删除可追溯性（GDPR 式 erase）论文未讨论。
- **工程复杂度**：LB bypass 需 request handler 重做 health/连接管理；5 region segment _placement + rebalancer + 双 rate limiter 显著增加控制面状态——论文承认但未评估 MTTR/人力成本。

## 局限与 Future Work

- **局限 1**（论文自述）：更大容量磁盘将加剧 **maintenance IOPS** 压力（repair、compaction、scrub 与业务 IO 争用）；2.0 GET 延迟 inherently 高于 1.0，需持续靠路由与 prefetch 优化。
- **局限 2**（论文自述）：2.0 在 **≥2 region 不可用** 时无法读写；比 1.0 全复制在极端灾难下的鲁棒性更弱。
- **局限 3**（实验边界）：生产结果混合 migration 后 workload 变化，跨版本对比非 controlled experiment；durability/availability 结论依赖简化 Markov 模型而非 chaos testing。
- **Future work 1**：量化 **next-gen HDD**（更高 TB/disk、更低 IOPS/TB）下 sealing/repair/compaction 的 IOPS budget，是否需要 disk-adaptive redundancy（类似 [[PACEMAKER]]/[[Morph]] 思路）或 hot/cold tier 分离。
- **Future work 2**：在 **无 CDN 或高 range-read** workload 上测量 XOR-5 vs 全复制 vs 更强 EC（如 [[Pando]] 式 cross-region EC）的 latency–cost Pareto，而非仅报告 full-object GET。
- **Future work 3**：对 **correlated multi-region failure** 做 production outage replay，验证 4-of-5 PUT quorum 与 async segment repair 在长时间 degraded 下是否积累不可恢复的 segment 缺口。

## 相关

- **相关概念**：[[Object-Store]]、[[Erasure-Coding]]、[[Local-Reconstruction-Codes]]、[[Geo-Replication]]、[[Raft]]、[[RocksDB]]、[[CDN]]、[[S3]]
- **同类系统**：[[Ceph]]、Amazon [[S3]]、Google Colossus、Azure Blob Storage、Facebook [[f4]]、[[Tectonic]]、Ambry、Walnut
- **同会议**：[[FAST-2026]]
- **对比**：McQueen 2.0 与 Meta [[f4]] 同属跨 region XOR 省空间路线，但 McQueen 强调 mutable user object + 强一致 metadata + 5-region XOR-5；与 [[Pando]] 相比更偏 operational simplicity（bitwise XOR vs 复杂 cross-region EC）
