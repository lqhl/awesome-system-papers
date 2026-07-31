---
type: paper
name: Quota-Marketplace
full_title: "Quota Marketplace: Dynamic Pricing for Efficient Allocation of ML Training Resources"
authors: [Balasubramanian Sivan, Renato Paes Leme, Mihai Tiuca, Ian McFarlane, Vasilis Gkatzelis, et al.]
venue: OSDI
year: 2026
tags: [ml-cluster, resource-allocation, market-mechanism, production-system]
source_pdf: "[[osdi26-sivan.pdf]]"
source_md: "[[osdi26-sivan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Quota Marketplace：以动态定价高效分配 ML 训练资源（OSDI 2026）

> **原题**：Quota Marketplace: Dynamic Pricing for Efficient Allocation of ML Training Resources

Google 的 Quota Marketplace 用每分钟清算的内部 chip price 取代季度静态配额，让团队以 credit 和 bid 表达 workload 价值，并跨 business unit 动态转移数十万 accelerators。

## 问题与动机

静态 pool 依赖季度/半年人工预测，却面对分钟级 supply clawback、新容量上线和训练 burst，造成一边排队、一边 silo capacity 闲置。Karma 等 max-min 机制默认不同需求价值均匀，无法区分关键模型与可延迟实验；QM 要把组织优先级、实时供需和公平性统一为内部市场。

## 关键观察 / 隐含假设

### 关键观察

- 公司层只需给 business units 配 market weights，pool admin 给团队配 location/resource-agnostic credits；具体 chip/time 选择可由实时价格分散完成。
- 训练比 serving 更能容忍等待与抢占，适合把价值表达为 willingness-to-pay 和 limit price。
- pool 自有资源与 global shared supply 可通过 blended internal price 清算，保留组织 ownership 又允许跨 pool 交易。

### 隐含假设

- 团队大体合作且近似 price taker，不会系统性操纵价格或耗尽他人 credit。
- credit allocation 正确代表公司价值；市场只能执行政策，不能解决管理者权重设错。
- scheduler 能把市场获得的逻辑 allocation 落到满足 topology/shape 的真实设备。

## 核心方法

### 周期性市场清算

每个 resource type/location 读取实时 supply 与 scheduler queue demand。自动 bidder 把 team credit、job priority 和 limit price 转为 demand curve，系统以 binary search 求 global reference price，再为每个 pool 计算包含自有免费供给的 blended price。

### Credit charging 与 allocation

team 按实际占用 chip-hours 付费，quota 不再保证具体芯片数量。价格高时低价值 workload 自愿后退，供应突然增加时价格下降并吸引可迁移需求。

### 稳定性工程

系统按较大 market cell 聚合供需，缓解小市场波动；价格 dashboard、历史趋势和 bidding automation 降低用户认知负担。market 和 scheduler 分层，但 topology mismatch 会产生 allocation wastage。

## 设计取舍

- 简单统一 price 提高可解释性，却只显式定价 accelerator，CPU、network、geometry 等次级资源由 scheduler 处理。
- 聚合 market 增加 liquidity 和稳定性，但价格相同不代表每个 cell 都能放下具体 topology request。
- 动态价格减少人工谈判，也会把工程团队变成需要理解预算、限价与波动的市场参与者。
- 公平/效率定理依赖简化模型与 foresight，生产中的战略行为和不可分割 gang scheduling 更复杂。

## 实验与结果

- QM 已分配数十万 ML accelerators，覆盖 Google 整体 ML fleet 的两位数百分比；market 大约每分钟清算一次，优化后 p50 cycle latency 从 100 s 降至 30 s 以下（§2–§3）。
- 相比 conventional pool 约 75% 的总 occupancy，QM pool 达 93%，提高约 24%；company-prioritized 之外的低价值 opportunistic occupancy 从 33.5% 降至 5.67%。
- 在一个 10 周观察窗口中，动态 bonus capacity 总量约等于 committed capacity 的 25%，QM 能随 supply 迅速提高 occupancy，说明静态 buffer 的机会成本显著。
- market 与下游 scheduler 的不一致造成 fleet 约 1.3% occupancy wastage；特定 4×4×4 geometry 无法落地的情况约占 1%，显示单价不能完全编码 topology。
- 小 cell 的 scheduling outcome 波动约 3%，系统以 global market 聚合改善 liquidity；代价是 pool/local scarcity 可能被平均化。
- 论文理论上证明在其动态、异质 valuation 模型下 market allocation 满足 Pareto efficiency 与相应 max-min fairness；保证取决于 credit、price-taking 与可分配资源假设。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| 动态价格能减少静态 silo 浪费 | 跨 pool 每分钟清算 | occupancy 从 75% 升至 93% | 比较为生产观察，非随机对照 |
| 市场可吸收快速 supply shock | price 与 automated bidder | 10 周 bonus 约为 committed 的 25% | 训练 workload 需可延迟/迁移 |
| 异质价值可同时兼顾效率与公平 | credit、bid 与 clearing price | Pareto/max-min 定理 | 简化连续资源与非战略参与假设 |
| 单一 accelerator price 可规模化运营 | market/scheduler 分层 | 数十万 chips、cycle p50 少于 30 s | topology mismatch 浪费 1.3% occupancy |

## 批判性分析

### 论证链条

论文把资源分配从 scheduler policy 提升为组织经济机制：先描述生产 stack，再报告 occupancy 与 shock response，最后给出福利/公平证明。工程规模与制度细节是主要贡献，理论解释了为何不是简单 spot queue。

### 假设压力测试

单个大 pool 或关键团队若能影响 price，price-taking 假设失效；team 可抬价消耗对手 credits。若 job 是不可分割大 gang、只接受少数 cells，连续 demand curve 的 efficient allocation 可能无法被 scheduler 实现。

### 实验可信度

真实数十万芯片部署极有价值，也披露 1.3% mismatch。因业务保密，图多为 normalized aggregate，缺少 workload completion、time-to-train、price volatility、用户满意度和静态 pool 严格同期对照，因果证据有限。

### 系统性缺陷

QM 把管理判断编码为 credits，而 credit 本身仍靠人工政治过程产生。市场 price 可能优化“愿意支付”而非 scientific impact，并激励团队囤 credit、拆 job 或策略性申报；附录承认 gaming，但生产防护不完整。

## 局限与后续工作

- 为 topology、CPU、network 和 energy 建立多资源价格，减少 1.3% allocation–scheduling mismatch。
- 设计抗操纵机制，量化 price power、credit hoarding 和跨团队外部性。
- 报告 job completion、time-to-quality、公平性和用户行为，而不只 occupancy。
- 支持不可分割 gang、deadline 与 serving clawback 的正式约束。

## 相关

- [[ML-Cluster-Scheduling]]
- [[Resource-Pricing]]
- [[Karma]]
- [[Max-Min-Fairness]]
