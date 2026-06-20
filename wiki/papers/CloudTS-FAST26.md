---
type: paper
name: CloudTS
full_title: "An Efficient Cloud Storage Model with Compacted Metadata Management for Performance Monitoring Timeseries Systems"
authors: [Kai Zhang, Tianyu Wang, Zili Shao]
venue: FAST
year: 2026
tags: [time-series, cloud-storage, metadata, object-storage, monitoring]
source_pdf: "[[fast2026-zhang-kai.pdf]]"
source_md: "[[fast2026-zhang-kai]]"
---

# An Efficient Cloud Storage Model with Compacted Metadata Management for Performance Monitoring Timeseries Systems (FAST 2026)

> **一句话总结**：基于监控 workload 中 tag 占 metadata 80%+ 且 70%+ 跨 partition 重复、time-partitioned block 直搬 [[S3]] 造成严重读放大的观察，CloudTS 将 metadata（Patricia-trie [[TagDict]] + 二维 bitmap [[TTMapping]]/TMMC）与数据（按 tag 相似度分组的 TSObject）解耦存储，在 Amazon S3 上对 Cortex 平均提速 **1.37×**（生产环境 **1.43×**），查询读数据量减少 **36–61%**，并优于 Apache Parquet 与 JSON Time Series。

## 问题与动机

[[Prometheus]]、Cortex、[[InfluxDB]]、TimescaleDB 等 performance monitoring [[Time-Series]] 系统正迁往云存储（[[S3]]、Azure Blob、GCS），以换取弹性与 pay-as-you-go。但云 object 的高 RTT 与带宽按请求计费特性，与本地 TSDB 的 time-partitioned block 模型天然不匹配。

现有做法有三类痛点：

1. **整 block 上云（Cortex/Thanos 范式）**：每个时间窗口把 index + 全部 series chunk 打成单一 object；查询哪怕只要一个 series 的一小段，也得拉整个 block，读放大严重。
2. **列式格式（Apache Parquet）**：同 metric 的 series 放同一列，但列彼此独立，定点读某 series 某时间窗仍要扫冗余行；metadata 与 data 混在一起，metadata 访问也放大。
3. **每 series 一 object（JSON Time Series）**：避免 block 内冗余读，但 tag-based query 需枚举/扫描大量 object，规模上去后 metadata 查找成为瓶颈。

与此同时，容器/微服务监控带来 **海量短命 series** 与 **极高 tag 基数**：ByteDance 监控每天超百亿 distinct series；论文分析的生产数据里 tag 占 metadata **80%+**，约 **73%** tag 重复，region/cluster 等通用 tag 被 **90%+** series 共享，却在每个 time partition 重复存储与访问。现有数据压缩工作主要针对 sample 值，不解决 tag 冗余。

作者 claim：在不改变上层 time-partitioned、tag-based query 语义的前提下，设计一套 **metadata/data 分离** 的云存储模型，同时压缩 tag 冗余、精确索引、减少 object 读取量。边界是 performance monitoring 场景（高 tag 冗余、chunk 式写入、immutable block），而非通用 OLAP 或高频 update workload。

## 关键观察 / 隐含假设

- **观察 1**：time-partitioned TSDB block 直接映射为 cloud object 时，查询延迟主要由 **不必要的 object 读取量** 决定，而非 CPU 解压本身；Cortex baseline 在 TSBS 上访问数据量比 CloudTS 多 **36–61%**（如 `high-all` 626 MB vs 305 MB）。
  - **依赖假设**：querier 与 S3 之间网络带宽充足（实验机 100 Gbps），瓶颈在 **read amplification + 串行 GET** 而非算力；查询以 tag filter + 时间范围为主，符合 Prometheus/Cortex API 模式。
  - **可能失效场景**：若 metadata 全量常驻内存、或数据已在本地 EBS cache hit，CloudTS 相对优势会缩小；极小查询在绝对延迟上可能都被 RTT 主导，倍数优势不明显。

- **观察 2**：timeseries–tag 倒排关系极度稀疏——Node Exporter 场景 691 series × 452 tags 的 bitmap 仅 **0.7%** bit 为 1，且 tag 跨 partition 高度重复。
  - **依赖假设**：监控 metric 的 tag cardinality 相对可控（每 series 平均 ~3 个 tag），倒排可用压缩 bitmap/CSR 高效表达；全局 [[TagDict]] 去重后，partition 内只需维护局部 tag array。
  - **可能失效场景**：高基数、自由文本 label（如 user_id=xxx）爆炸时，TagDict trie 与 TTMapping 列数膨胀，全局字典可能变成内存热点；论文 high label churn 实验已显示延迟上升。

- **观察 3**：相关 series 在 tag 空间有结构——部分 tag name 互斥（CPU vs memory metric），部分 tag pair 高频共用（region/cluster）；按 tag 频率分组可把 TTMapping 拆成小子矩阵并并行读 TSObject。
  - **依赖假设**：真实监控数据的 tag 共现模式在较长时间内稳定，CloudWriter 离线分析频率后分组仍有效；TSObject 按 group 聚合后单 object 大小落在「不太小（metadata 开销）/不太大（读放大）」之间。
  - **证据强度**：**中**——动机测量与 grouping 启发式合理，但 grouping 最优性未形式化证明，异构 metric 混部时可能退化为近似「按 tag name 粗分」。

- **假设 1**：immutable block 异步上传模型可接受——CloudWriter 在 block 封口后 daemon 转换，查询热数据仍走本地 ingester/cache，冷数据才走 CloudQuerier。
  - **证据强度**：**中**——论文证明上传期间 query latency 未明显恶化，但未量化 block 封口到 S3 可查的 **ingestion lag**，也未讨论上传失败重试与一致读。

- **假设 2**：云 object 存储的高带宽适合 **并行 GET 多个小 TSObject**，8 并发可将 `high-all` 网络吞吐从 ~102 MB/s 提到 ~231 MB/s。
  - **可能失效场景**：S3 请求费率、LIST/GET 配额、跨区流量费时，并行度收益可能被 dollar cost 抵消；论文 **未做成本模型**。

## 核心方法

CloudTS 是嵌入 Cortex 的 **存储格式 + 读写路径**，保持上层 PromQL/tag query 透明。核心组件：TagDict、TTMapping、TSObject，由 CloudWriter 写入、CloudQuerier 读取。

**Metadata/Data 分离（回应观察 1）**：每个 immutable time partition 不再 monolithic block；metadata 对象含 TagDict 增量、partition 级 TTMapping（TMMC 压缩）、tag array；数据对象 TSObject 按 **timeseries group** 切分。查询先只拉 metadata 定位 series 与 object key，再并行拉必要 chunk，避免整 block 下载。

**TagDict（§3.2，回应观察 2）**：全局 Patricia trie-like 结构，tag pair（含 metric name）共享前缀，叶子存全局 encoding；双向指针支持 tag↔id  O(1) 跳转。每个 partition 维护 **只含本 partition 活跃 tag** 的 tag array（按频率排序），查询先在局部数组解析 partition-local encoding，再映射到 TTMapping 列。这与 [[Inverted-Index]] 中 symbol table 去重思路一致，但提升到 **跨 partition 全局** 层面。

**TTMapping + TMMC（§3.3，回应观察 2）**：二维 bitmap，行=series ID，列=partition 内 tag 列；支持行查（series→tags）与列查（tags→series）。TMMC 在 [[CSR]] 基础上去掉 value 数组，只保留 `ind`（置 1 位置）和 `ptr`（行前缀和），空间从 $O(M \times N)$ 降到 $O(M+N)$。这是整个 metadata 压缩的关键杠杆。

**Timeseries Group（§3.3.2，回应观察 3）**：按 tag pair 频率分桶——低频高选择性 tag 用于过滤，高频共用 tag（如 region）不足以切分 series，转而按 **同 tag name 覆盖全集** 的粗粒度分组。理想情况互斥 tag set 形成对角子矩阵；现实中退化为多组较小 TTMapping + 多 TSObject，查询可 **跨组并行**。

**TSObject（§3.4）**：每个 partition × group 一个 object；内部 chunk 按 series ID 与时间排序，保证顺序读带宽。相比 Parquet rowgroup，额外按 tag 相似度聚 series，使一次 GET 服务一组相关查询。CloudWriter 在 block 封口时：更新 TagDict → 构建 TTMapping/group → 顺序读 chunk 打包 TSObject → 上传 S3；与在线写入路径解耦。

**CloudQuerier 查询三阶段（§3.5）**：(1) 拉取/缓存涉及 partition 的 tag array + TTMapping；(2) TagDict + TTMapping 解析得 series ID 与 group；(3) 并行 GET 目标 TSObject 并按时间过滤 chunk。metadata cache 避免重复远程读索引。

## 设计取舍

- **格式专用 vs 通用列存**：放弃 Parquet 生态互通，换取监控语义下的精确剪枝；TSObject 布局绑定 Cortex/Prometheus chunk 格式，迁移到其他 TSDB 需新 Writer。
- **全局 TagDict vs 纯局部索引**：全局去重节省空间、加速重复 tag 解析，但引入 **跨 partition 共享状态**（字典持续增长、版本兼容）；partition 局部 TTMapping 则控制单次查询 metadata 工作集。
- **Bitmap 倒排 vs 传统 posting list**：bitmap 列查在 tag 数适中时简洁，TMMC 保证稀疏性；tag 列数极大时列扫描成本上升，论文靠 frequency ordering 缓解但未给出硬上限。
- **并行 GET vs 请求数**：提升带宽利用，但增加 S3 请求次数；**论文未讨论** tail latency 在限流下的表现。
- **边界条件**：在 **冷历史查询、宽 tag filter、多 partition 范围查询** 时最优雅；单 partition、单 series、metadata 已热 cache 时，优势趋近常数因子而非数量级。

## 实验与结果

平台：AWS EC2（64 GB RAM，100 Gbps），S3 后端，Cortex 1.16.0 集成 CloudTS（Go 原型）；对比 Original Cortex、Parquet 改造版、JTS 改造版，部分实验对比 InfluxDB 3.x。

- **生产环境**（10 台 Debian × 10 Node Exporter，48h 预热后 4h 查询）：端到端 query latency 平均 **1.43×** 于 Cortex；上传周期（每 2h block persist）内查询无明显抖动。
- **TSBS 合成**（500K series，24h 数据，8 种 query pattern）：平均 latency **1.37×**（文中亦写 36% 提升）；全面优于 Parquet/JTS；`high-all` first data arriving time 显著短于 baseline/JTS。
- **读数据量**（Table 5）：`5-8-1` 65 MB vs baseline 154 MB；`high-all` 306 MB vs 626 MB（约 **51%** 减少）；`cpu-all-8` 352 MB vs 696 MB。
- **资源开销**：查询 CPU 利用率 CloudTS **45.7%** vs Cortex **60.4%**；`high-all` 内存 **3.35 GB** vs **5.21 GB**。
- **并行度**：`high-all` 8 线程并发 GET 吞吐 **230.7 MB/s** vs baseline **102.5 MB/s**。
- **vs InfluxDB 3.x**：复杂查询 `high-all` / `cpu-all-8` 分别快 **15.5%** / **6.8%**；简单查询二者接近（metadata cache 主导）。
- **长期保留**（200 partition，136 万 unique series）：TagDict 内存稳定；每 partition TTMapping+tag array 平均约 **21 MB**。
- **高 label churn**（每 partition 137 万短命 series）：查询延迟显著上升，但每 partition metadata 仍 **<30 MB**；说明 churn 成本主要在 **更多 partition 扫描**，而非 TagDict 爆炸。

## Critical Analysis

### 论证链条

动机测量（tag 冗余 + 云读放大）→ metadata/data 分离 + 全局 TagDict + 稀疏 bitmap 索引 + tag-aware TSObject 分组 → 更少 GET 字节 + 更高并行度 → 延迟/内存/CPU 全面下降：链条整体闭合。最强证据是 **accessed data volume** 与 latency 同向变化，支持「读放大是主因」叙事。薄弱环节：(1) 生产评估只有 **1.43×**，低于部分 TSBS pattern 的感知收益，说明真实 workload 的 cache/查询混合可能稀释优势；(2) grouping 与 TMMC 的 **独立 ablation** 不够细，难判断哪一项贡献最大。

### 假设压力测试

- **热数据路径**：论文承认 InfluxDB 3.x 靠 ingester/cache 对近期数据很快；CloudTS 优势集中在 **冷数据、宽扫描**。若生产查询 90% 命中本地 cache，整体 TCO 收益需重新建模——**论文未覆盖**。
- **标签基数爆炸**：churn 实验是合成注入，真实场景可能是不可预测的新 label；全局 TagDict 无淘汰策略时，长期运维内存与 trie 深度 **论文未讨论 GC**。
- **多租户/隔离**：Cortex 部署常多 tenant 共享 querier；CloudTS metadata cache 与并行 GET 的隔离、公平性、资源上限 **论文未讨论**。
- **S3 一致性与故障**：block 上传中途失败、部分 object 可见时的查询行为 **论文未讨论**。

### 实验可信度

- **Baseline 选取合理**：Cortex 代表工业界 Prometheus 远程存储；Parquet/JTS 覆盖列存与 per-series object 两种范式；InfluxDB 3.x 补充 cloud-native 竞品。
- **公平性疑点**：所有方案都跑在 Cortex 改造壳内，Parquet/JTS 是「换存储引擎」而非独立最优实现，可能低估成熟 Parquet 查询层优化；生产规模（100 targets）远小于合成 500K series，**外推需谨慎**。
- **指标覆盖**：偏重平均 latency、读字节、CPU/内存；**尾延迟 P99/P999、S3 请求数、美元成本、写入放大、恢复时间** 缺失。
- **Ablation**：线程数实验有；缺 TagDict-only、TTMapping-only、无 grouping、无 TMMC 的分项对比。

### 系统性缺陷

- **写入与生命周期**：只验证 CloudWriter 不拖慢并发查询，未量化转换 CPU、上传带宽占用、block 封口延迟；无 compaction/GC/删除旧 partition 的工程故事。
- **可观测性**：metadata cache 命中率、每查询 S3 GET 次数、group 划分质量等运维指标 **论文未讨论**。
- **兼容性**：原型绑定 Cortex block 格式；对 Thanos/Mimir/其他远程存储的移植成本未知。
- **正确性**：查询结果与 baseline 一致性有隐含假设，未见端到端 correctness 校验实验。

## 局限与 Future Work

- **局限 1**：评估聚焦 Amazon S3 + Cortex，未覆盖 Azure/GCS 或跨云 replication；结论对 Region 内低延迟查询更强。
- **局限 2**：高 label churn 下延迟上升明显，需更细 partition（15 min）与频繁 flush 缓解，说明 **极端动态 cardinality** 仍是边界。
- **局限 3**：缺少经济账——读字节减少未必等于账单减少，若并行 GET 增加 request count，S3 费用可能反升。
- **Future work 1**：在真实 multi-tenant 生产 trace 上测量 **metadata cache 命中率 vs S3 GET 成本**，建立 cost-latency Pareto 曲线。
- **Future work 2**：TagDict 的增量 GC、冷 tag 归档，以及 churn 场景下 TTMapping 列剪枝（column ordering / bitmap width 自适应）的系统性评测。
- **Future work 3**：与 [[KV-Cache]] 式分层缓存或 disaggregated memory 结合，量化热冷分层后 CloudTS 格式是否仍必要，或仅冷层使用。

## 相关

- **相关概念**：[[Time-Series]]、[[Object-Storage]]、[[Inverted-Index]]、[[Patricia-Trie]]、[[CSR]]、[[S3]]
- **同类系统**：[[Prometheus]]、Cortex、Thanos、[[InfluxDB]]、TimescaleDB、ModelarDB、ByteSeries、Apache Parquet、JSON Time Series
- **同会议**：[[FAST-2026]]
- **对比**：云监控存储在「整 block 上云」与「metadata 压缩索引 + 细粒度 object」之间的设计光谱；可与 [[RISTRETTO-FAST26]] 等生产级云存储经验论文对照阅读