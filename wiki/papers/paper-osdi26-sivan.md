---
type: paper
name: QuotaMarketplace
full_title: "Quota Marketplace: Dynamic Pricing for Efficient Allocation of ML Training Resources"
authors: [Balasubramanian Sivan, Renato Paes Leme, Mihai Tiuca, Ian McFarlane, Vasilis Gkatzelis, Nehal Mehta, Soheil Hassas Yeganeh, Vahab Mirrokni, Amin Vahdat]
venue: OSDI
year: 2026
tags: [ml-resource-allocation, dynamic-pricing, cluster-scheduling, fairness, market-mechanism]
source_pdf: "[[osdi26-sivan.pdf]]"
source_md: "[[osdi26-sivan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-12
---

# Quota Marketplace：用动态定价分配 ML 训练资源（OSDI 2026）

> **原题**：Quota Marketplace: Dynamic Pricing for Efficient Allocation of ML Training Resources

> **一句话总结**：Quota Marketplace 把 GPU 配额从静态池或 chip-hour 变成可跨池交易的 credits，并以约 1 分钟一次的供需清算分配训练资源；Google 部署数据显示整体 occupancy 从 75% 提升到 93%，但全局配额、拓扑无感知和集中式故障域仍造成约 10% 的位置争用、约 1% 的几何碎片化抢占及更大的失效半径。

## 问题与动机

Google 的 ML 训练资源供给和需求都快速变化。新一代 accelerator 分批到货，生产流量上升时资源又可能被临时收回；团队的训练、演示和探索任务也很难按季度准确预测。静态 pool 能提供较强的隔离和可预期性，却会把资源锁在业务单元内部，产生闲置容量，并且无法及时反映任务价值的差异。

已有 chip-hour 机制能随需求变化分配资源，但通常把每个请求视为同等价值。论文指出，在训练任务的时间价值不同、不同团队对同一资源的收益不同的情况下，这会同时损害效率和长期公平性。Quota Marketplace（QM）让团队用 bid 表达任务价值，以动态价格协调跨 pool 的供需。

## 关键观察 / 隐含假设

- **观察 1：供给和需求的变化速度远高于人工配额周期。** 论文中的市场每分钟左右重新清算，而传统优先级评估按季度或半年进行。图 6 展示了 24 周内 fleet 组成持续变化；图 7–8 显示可回收的 serving buffer 和 holding pool 容量达到数十万 chips 量级。
  - **依赖假设**：训练 workload 能容忍抢占，且团队可以把部分任务延后、迁移到其他 cell 或资源类型。
  - **可能失效场景**：强 location constraint、不可抢占的长任务或严格 SLO 的 serving workload 不适合直接使用这种动态配额。
- **观察 2：资源价值具有时间和团队异质性。** 同一个团队的任务可能有不同截止时间，业务单元也有不同的组织优先级。固定 chip-hour 价格无法表达这种差异；市场价格则同时提供支付约束和拥塞信号。
  - **证据强度**：强。第 4 节构造的 bi-valued 实例证明，chip-hour 机制即使面对 HIGH/LOW 两种价值也可能违反 Pareto efficiency。
- **假设 1：accelerator 是训练集群的主导瓶颈。** QM 只显式给 ML accelerator 定价，CPU、RAM、disk 和 network 按 accelerator quota 比例分配。
  - **证据强度**：中。该选择符合 Google 的部署观察，但论文没有系统评估辅助资源成为瓶颈时的损失。
- **假设 2：大市场中的单个团队近似是 price-taker。** 理论分析要求单个 agent 不显著影响价格，并假设团队能估计未来需求和价格。
  - **证据强度**：中。该假设支撑福利定理式的 Pareto 结论，但在资源类型或 cell 很小的市场中可能不成立。

## 核心方法

QM 在层次化 ML scheduler 之上加入一个全局 coordinator。团队提交排队 workload，自动 bidder 根据优先级、credit balance、income rate、limit order 等设置，生成每种资源的 bid。市场按 accelerator 类型和 cell 聚合供给与需求，寻找使共享供给与总需求相等的 clearing price；内层求每个 pool 的内部价格，外层用二分搜索求共享市场价格。

Credits 与物理资源解耦。pool 管理员通过 income 给团队铸造 credits，公司通过 market weight 控制各 pool 的总购买力。Credits 不绑定具体地点或 chip type，因此新增或收回数十万 chips 时无需重新分配账户余额；只需在下一次清算中更新供给。该设计回应了观察 1，也把跨 pool 的优先级调整从零和的“从谁那里收回 chips”改成调整购买力。

系统每分钟运行 market cycle，每 5 分钟处理 income 和 charge，每小时左右导入 capacity。minimum affordable duration 要求团队在当前 burn rate 下至少能维持 120 分钟，抑制因账务周期造成的价格抖动和频繁抢占。RunAuction 是无状态纯函数，输入、输出和辅助状态都持久化，因此可以重放历史市场周期，用于事故复现、离线模拟和回归检查。

为保持市场流动性，QM 使用 Global Cell 抽象，而不是为每个 cell 单独拍卖。位置灵活的 workload 可以在全局获得 quota，再由 scheduler 进行实际放置。该设计避免了小市场的价格波动，但牺牲了 quota 与物理位置之间的一致性。论文还描述了后续把 above-cell scheduling 上移到 QM 的架构变化，以减少市场和 scheduler 的异步状态冲突。

理论模型把每轮资源看作可分割的单一资源。市场给 agent 分配预算和每轮价格，团队根据需求、limit price 和预算购买资源。论文证明这种市场机制对一般异质价值保持 Pareto efficiency，并在平均支付价格满足一定条件时获得近似 max-min fairness；相反，chip-hour 机制在均匀价值下的公平性最坏只能达到 1/n，在 bi-valued 实例下甚至无法保证 Pareto efficiency。

## 设计取舍

- **动态效率 vs. 稳定性**：价格和 quota 快速跟随供需，减少闲置，却会带来更多抢占和用户行为波动。120 分钟可负担时长及其他调度平滑机制降低了 churn。
- **市场流动性 vs. 放置精度**：Global Cell 避免 cell 级薄市场；代价是约 10% 的案例出现“全局 quota 足够但目标 cell 争用”的情况。
- **简单价格信号 vs. 多资源最优性**：只给 accelerator 定价降低用户认知负担，但在 CPU、RAM、网络不再按比例扩展时，单资源模型会错误估计真实成本。
- **集中式一致性 vs. 故障半径**：单体 QM 简化清算和 replay，并把 market 与 scheduler 的逻辑逐步合并；同时也形成集中式故障域。宕机时系统回退到最近一次有效 quota snapshot 和静态 pool 调度，但效率会下降。
- **标量 quota vs. 拓扑约束**：QM 不知道 64-chip workload 所需的连续 4×4×4 cube，物理 scheduler 只能事后通过 bin-packing 和 defragmentation 修正，论文报告约 1% 的相关抢占。

## 实验与结果

- Google 全局部署覆盖数十万 ML accelerators，拥有数千 daily active users，已消耗数十亿 accelerator hours（引言与贡献概述）。
- 对规模相近、各含数十万 chips 的 pool 比较中，传统静态 pool 的平均整体 occupancy 为 75%，QM 为 93%，整体提升约 24%；opportunistic occupancy 从 33.5% 降至 5.67%（图 4–5）。
- QM 将 serving buffer 和 holding pool 中原本难以及时优先级化的瞬时容量纳入市场，额外释放的 bonus capacity 持续达到数十万 chips 量级（图 7–8）。
- 新 accelerator 批次加入后，QM pool 的 occupancy 能快速跟随 supply；静态 pool 存在明显滞后（图 9–10）。新资源类型的低价还促使用户迁移工作流，价格逐渐接近替代资源类型（图 11）。
- 市场周期 p50 latency 从 100 秒降到 30 秒以下；端到端调度延迟曾造成 fleet 约 1.3% occupancy wastage。架构整合后端到端延迟约为 30 秒（§2.1）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| QM 能减少静态 pool 的闲置并提高整体 occupancy | 75%→93%，图 4–5 | Google 内部、可比 pool、数十万 chips；非公开 trace | 强 |
| 动态价格能吸收新增供给并塑造需求 | 新资源加入后 occupancy 跟随 supply，替代资源价格收敛，图 9–11 | 观察性部署数据，未隔离价格信号与团队沟通的因果贡献 | 中 |
| 市场机制在异质价值下保持 Pareto efficiency | Theorem 3；第 4 节单资源、可分割供给模型 | 依赖 price-taking、理性预算分配和充分需求假设 | 中 |
| Global Cell 提高流动性但引入位置错配 | 小 cell occupancy 约低 3%，约 10% 案例发生 cell contention，§2.1 | Google fleet 的 cell 分布和工作负载约束 | 强 |
| 拓扑无感知带来额外抢占 | 约 1% 案例发生 quota 存在但几何不匹配，§2.1 | 当前部署的离散拓扑 workload | 中 |

## 批判性分析

### 论证链条

论文的主链条在系统层面较完整：动态供需和价值异质性推动价格机制；credits 解耦了组织优先级与物理供给；周期性清算把价格转换为 scheduler quota；部署数据显示 occupancy 和瞬时容量利用率改善。理论部分则在简化模型中证明市场相对 chip-hour 的效率与公平优势。

但理论保证没有覆盖生产系统中的多资源、离散拓扑、位置约束和异步 scheduler。生产结果证明的是部署相关指标改善，不等同于证明所有团队获得了更高效用或长期公平。尤其是 93% occupancy 可能伴随更高抢占、等待时间或运维负担，论文没有给出完整的 P95/P99 作业等待和失败成本。

### 假设压力测试

Global Cell 的约 10% 位置争用说明全局价格与实际可执行 quota 之间存在结构性间隙。若 workload 的 location constraint 更强，市场可能持续出售无法及时兑现的 quota。类似地，topology-oblivious 设计在大规模 cube 请求或碎片化严重的 fleet 中可能产生高于 1% 的 defragmentation 成本。

市场的价值表达依赖自动 bidder 和团队配置。默认设置在论文部署中“多数情况下有效”，但高波动期间仍需人工调节。对于预算有限、需求预测弱或无法理解价格历史的团队，名义上的自由竞价未必等价于公平的价值表达。理论中的 price-taking 假设在资源稀缺且参与者较少的细粒度市场中也可能失效。

### 实验可信度

部署规模和对照 pool 使 occupancy 结果具有工程参考价值，且图 9–11 展示了价格与供给变化下的真实行为。局限是数据主要来自 Google 内部，论文没有公开 workload trace、业务单元构成、价格分布、抢占代价和团队效用，因此外部读者难以复现或判断选择偏差。静态 pool 与 QM pool 虽描述为可比，但缺少更细的随机化或准实验设计来分离 pool 特征、硬件世代和团队行为的影响。

### 系统性缺陷

QM 的单体全局 coordinator、跨 pool quota 移动和市场/scheduler 异步接口扩大了故障和状态不一致的影响范围。replay、snapshot fallback 和按 resource type 的渐进 gate 缓解了风险，但无法消除中心化清算错误的 blast radius。论文明确讨论了两类 gaming：通过改变本地货币铸造率制造汇率收益，以及提交难以调度但不实际运行的 workload 抬高他人价格。对抗性环境中的惩罚机制仍是开放问题。

## 局限与后续工作

- **局限 1**：理论保证基于单资源、可分割供给和 price-taking agent，不能直接推出 Google 生产系统在多资源和拓扑约束下的公平性。
- **局限 2**：论文未完整报告等待时间、抢占次数、失败重试、checkpoint 开销和跨团队效用分布，occupancy 提升的总成本仍不清楚。
- **局限 3**：Global Cell 将价格稳定置于放置精度之上；约 10% 的 cell contention 和约 1% 的拓扑相关抢占显示 quota 兑现仍依赖下游 scheduler。
- **后续工作 1**：把 topology-aware pricing 纳入市场，并测量在 cube 请求比例变化时的 occupancy、P99 等待时间和抢占率。
- **后续工作 2**：比较多级或按位置分片的 QM 与单体市场，在效率、价格波动、恢复时间和故障 blast radius 上的 Pareto 前沿。
- **后续工作 3**：为 currency conversion 和未运行 workload 的价格操纵设计可验证的 charge 或 deposit 机制，并评估额外 UX 复杂度。
- **后续工作 4**：在 accelerator 不是唯一瓶颈的 workload 上评估组合定价，验证比例分配辅助资源是否仍能保持公平和效率。

## 相关

- **相关概念**：[[Max-Min Fairness]]、[[Cluster Scheduling]]、[[Dynamic Pricing]]、[[Resource Allocation]]
- **同类系统**：[[Karma]]
- **同会议**：[[OSDI-2026]]
- **对比**：[[QuotaMarketplace-vs-Karma]]
