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
last_reviewed: 2026-07-30
---

# 在云中统一日志、指标与追踪的观测系统

> **原题**：All Along the Watchtower: Achieving the Trinity of Observability in Cloud with DiTing

## 一句话总结

DiTing 以“Central–Node Collaboration”统一 logs、metrics、traces：优先在数据产生 node 上用闲置资源存储近期数据并 pushdown query，AZ 集中层负责长期持久化与 fallback；生产覆盖百万 node，CapEx 相比既有方案降低 3–65 倍。

## 问题与动机

SRE 调查一个 incident 往往先看 metric alert，再沿 trace 定位 component，最后查 log root cause；三类 telemetry 却位于不同系统、使用不同 query language，需人工 script 关联。只统一 compute 的 data lake 仍跨网络扫描百 GiB，需数十秒到数分钟；全 in-memory NewSQL 对数百 PiB logs/traces 过贵。

阿里曾以约 600 physical nodes、8 PiB 数据部署 ClickHouse，继续扩展时遭遇单 service 超百万 partition、wide metrics 数千 column 导致约 85% memory/OOM；加资源预计占 cloud CapEx 超过 20%。纯 resource harvesting 又在 node crash/traffic burst——恰是最需要 observability 时——失效，且 local disk 不够可靠。DiTing 因此把 node locality 与 centralized reliability 组合，而非二选一。

## 关键观察 / 隐含假设

### 关键观察

- observability 的核心瓶颈是 query/ingestion CPU 与 memory，而不是便宜的长期 storage capacity。
- telemetry query 有强 spatial locality（查产生数据的 node/component）和 temporal locality（最近一小时/一周最热）。
- cloud fleet 已采购但平均闲置的 CPU、DRAM、SSD 聚合后是巨大 distributed cache/compute layer。
- logs、metrics、traces 可共享 relational/columnar substrate 和 SQL interface，但 ingestion、index、retention 优化不能完全相同。

### 隐含假设

- per-node agent 的 harvested work 可被严格限流，不干扰 tenant；约 99% query 能在 node 正常执行。
- physical-location metadata 准确且更新及时，足以避免 Bloom-filter false positive 造成大规模错误 pushdown。
- telemetry append-only、single writer，能容忍短期 staleness/minor inconsistency，因此无需完整 ACID。
- harvested resource 在 CapEx 核算中视为 sunk cost；这降低 accounting cost，但仍消耗 energy 与 opportunity capacity。

## 核心方法

### 中心与节点协作

Global layer 只路由跨 AZ query，metadata service 把 virtual disk/service 映射到 physical location。每 AZ 有 20–100 个 dedicated node：3 个 zone root 组成 Raft group，其余 mixer/leaf 可互换，保存长期数据、聚合结果，并在 node failure/timeout/overload 时 fallback。Node agent 收集 telemetry、缓存/本地持久化近期 co-Log、使用 idle CPU执行 subquery，并周期上传 AZ/可选 OSS。

zone root 按 physical hierarchy 构造 query tree。聚合 query 的 fan-out 取 `min(N,1000)` 控制 mixer load，scan 可直接 fan-out `N`。node 已失联则直接 centralized execution；pushdown 后 timeout 则 reroute；overloaded node 可进入 fetch-only，由 AZ 完成 compute。生产仅约 1% query fallback。

### co-Log 数据模型

co-Log 用 SQL relational table 统一 telemetry：metric 是 timestamp/labels 加 10K–20K measurement columns，每 15 s 一行；trace 以 span table 记录 id/parent/trace/time/duration；log 是 timestamp/location/severity/body，非结构文本 query 时 schema-on-read。

文件采用 PAX hybrid：row group 内 column、column 内 page；footer 同时保存 file/row-group/column/page multi-level index，默认索引 time/location。wide table 可有数万 column，而一次 query 通常约 10 个；metadata 采用 raw format 而非 ProtoBuf/Thrift，换更大 metadata 为随机字段查找速度。它支持 schema evolution 与 CRC，但刻意不支持 strong ACID、complex array/map 和重型多粒度 compression。

### Query 与 ingestion 优化

metadata 按 node IP/cluster 切片并 pushdown，local join 无需往返 global/AZ；该优化使 latency 降 33%，node CPU 从约 45% 降到 16%，只增加数 MiB memory。resource limit 覆盖 CPU、memory、disk，持续超限会终止 agent。

node 以 memory buffer吸收高频 metric；极端 20K metric/node 时 900 MiB 仍覆盖超过 99.9% query，100 MiB 约 90%。上传时先合并同 server row group并保留 IP metadata，再按 cluster 合并/sort，既减少 billions small file，又保留 spatial pushdown 信息。long-range metric 预聚合到 5 min/1 h 粒度。

### 一致性、完整性与可用性

每 node 是其 telemetry replica group 的固定 leader，无 leader election；node→AZ→OSS 复制，node 宕机就不会产生新记录，因此 fixed-leader Raft-like protocol 足够。node/AZ freshness 差异会估计并通知用户。CRC 贯穿 generation/network/disk，后台 scrub 与 OSS cross-check；nested block 利用 composable CRC避免重读。node+AZ 根据 failure model 约九个 9，可选 OSS 达约十二个 9。

## 实验与结果

- **证据定位**：§5.1–§5.3、图 9–12；覆盖 microbenchmark、production deployment 与 CapEx analysis。
- 80-server production metric、400 concurrency 下，DiTing 在约 1K QPS 时 latency 约 0.2 s；centralized-only 慢 7–82 倍，长窗口是 0.2 s vs 18.1 s，30-day query 甚至 OOM。
- 单 CPU core microbenchmark 可达约 1,500 QPS（摘要称 2K QPS），300 MB limit 下多种配置仍接近；20K/60K node region/global query latency 约 0.5/0.8 s。
- metadata-assisted pushdown 将需扫描约 1.4 PiB、耗时数十分钟的 430K virtual-disk query 缩短到 2 s。
- node unavailable 比例从 0% 到 100% 时 latency 渐进上升，由 AZ fallback 保持可用。
- 生产已超过 100 万 node；一个 region 的 36K node/300 cluster 样本中，每 node平均约 0.5% DRAM、少于 2% CPU core、10–20 GB local disk，聚合 cache 达约 34 TB。
- 与内部 Solution A 比，50/400-node production deployment 的 QPS 提高 4–9 倍，latency 降至 1/10–1/4。
- Type-I persistence cost 是 Solution A/B 的约 1/180、1/6；Type-II ingestion cost 低 17.6、2.4 倍；总 CapEx 低约 65、3 倍。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| node-local harvesting 同时改善 latency 与成本 | centralized-only 慢 7–82 倍；总 CapEx 低 3–65 倍 | harvested resource按 sunk cost计价，未计全部 opportunity/energy cost | 强 |
| centralized fallback 可弥补易失 node | 生产约 1% fallback；0–100% unavailable 时 latency 渐增 | 极端 incident 同时压垮 node 与 AZ 时未深入展示 | 强 |
| physical metadata 可精确大规模 pushdown | 1.4 PiB potential scan 缩到 2 s；metadata pushdown latency 降 33% | mapping stale 或跨 service entity 漂移可能漏查/错查 | 强 |
| 一套 substrate 可支撑 telemetry trinity | metric、trace、log及 join microbenchmark，统一 SQL/co-Log | 三类 ingestion/index仍有大量专用路径，并非真正同构 | 强 |
| fleet-scale overhead 单点很低 | 每 node约 0.5% DRAM、少于 2% cores | 聚合仍是 34 TB cache，agent regression blast radius巨大 | 强 |
## 批判性分析

### 论证链条

DiTing 的贡献在 production architecture：它把“观察云不能依赖云本身”的循环依赖、centralized cost curve 与 harvest reliability 风险同时纳入。三层 fallback、精确物理 pushdown、co-Log wide-table index 和 fixed-leader replica 都服务于同一 cost/locality thesis。百万 node、数十到数百 PiB、内部 audited CapEx 让证据比实验室 observability prototype 更有分量。

### 假设压力测试

- 成本 baseline 匿名、绝对数字保密，65 倍差异难由外部复算；“闲置资源免费”是会计假设而非物理事实。
- node agent 同时 collection、storage、query、metadata，论文自己承认 regression 可在数小时影响全 fleet；安全隔离与升级验证是系统可信核心。
- telemetry 可容忍 minor inconsistency 并非普遍成立，security audit/billing/compliance log 可能要求更强 completeness。
- SQL trinity 的 user experience、cross-source schema/clock alignment 和 root-cause workflow 成效缺少定量用户研究。
- 查询评估主要来自内部 workload，ClickHouse/solution A/B 配置公平性无法完全核验。
- 百万 node 元数据更新、Global service partition 与控制面灾难恢复没有同等深度展开。

### 实验可信度

百万节点 production deployment、内部 CapEx 审计和多种 telemetry benchmark 很强；但 baseline 匿名、绝对成本保密且 harvested resource accounting 未计 opportunity cost，外部不可完全复算。

## 局限与后续工作

- **局限**：per-node agent 的 blast radius、弱一致性与匿名成本模型限制可迁移性。
- **后续工作**：应增强 agent sandbox、incident resource reservation，并公开可复验 workload 与 normalized TCO model。

生产经验强调 stability-first：canary、分 cluster/region rollout、自动 rollback、rate limit、circuit breaker、backpressure、load shedding 比复杂算法更关键；每个 feature 都应评估 fleet-wide bytes/day、write amplification 与 CPU。未来可进一步研究 agent sandbox/verification、incident-aware resource reservation、cross-source clock/identity semantics、cost-aware retention、隐私访问控制，以及公开 workload/normalized TCO model 以便外部复验。

## 相关概念

- [[Observability]]
- [[Telemetry]]
- [[Resource-Harvesting]]
- [[Distributed-Query-Processing]]
- [[Operational-Systems]]
