---
type: paper
name: Quota-Marketplace
full_title: "Quota Marketplace: Dynamic Pricing for Efficient Allocation of ML Training Resources"
authors: [Balasubramanian Sivan, Renato Paes Leme, Mihai Tiuca, Ian McFarlane, Vasilis Gkatzelis, Nehal Mehta, Soheil Hassas Yeganeh, Vahab Mirrokni, Amin Vahdat]
venue: OSDI
year: 2026
tags: [ml-cluster, resource-allocation, market-mechanism, production-system]
source_pdf: "[[osdi26-sivan.pdf]]"
source_md: "[[osdi26-sivan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用动态价格分配机器学习训练资源（OSDI 2026）

> **原题**：Quota Marketplace: Dynamic Pricing for Efficient Allocation of ML Training Resources

> **一句话总结**：Quota Marketplace（QM）把 Google 各业务单元按季度分配的静态训练芯片 quota 改成约每分钟清算一次的内部市场：公司用 market weight 表达业务单元优先级，团队用 credit、job queue 和 limit price 表达当下价值；系统已管理数十万加速器，所比较 QM pool 的平均 occupancy 为 93%、传统 pool 为 75%，但生产证据主要是汇总观察，理论保证又依赖大市场、资源可分、参与者能预见未来价格等强假设。

## 问题与动机

传统 ML fleet 把 accelerator 按业务单元切成静态 pool，再由管理员每季度或每半年把芯片分给团队。这种方法有清楚的所有权和可用性隔离，却用数月一次的决策应对分钟级变化：新硬件分批上线，serving 流量突然需要 clawback，训练任务因 demo、实验或截稿临时暴增。一个 pool 排长队时，另一个 pool 的资源仍可能空闲或只被低优先级 opportunistic job 填充。

按 chip-hour 记长期使用量的 Karma 等机制能处理动态 demand，但默认每次请求的单位价值相同。真实组织中，一次关键模型训练和一次可延迟实验显然价值不同；如果系统不允许表达这种差异，用户只能通过虚报 demand 或人工 escalation 绕过机制。

QM 的目标是把“公司认为哪个业务单元重要”“团队此刻最想跑哪个任务”“什么芯片、什么时间和地点最拥塞”分开表达，再用价格把这些信息合并。它主要面向能等待、迁移和被抢占的 training workload，不承诺像 serving quota 那样的硬可用性。

## 关键观察 / 隐含假设

- **观察 1：组织优先级是分层的。** 公司管理者适合给业务单元分配 market weight，pool 管理者适合给本单元团队分 credit income，工程师最了解具体 job 的 deadline 与替代资源。QM 让每层只做自己知道的决策（§1、§2）。
  - **依赖假设**：market weight 和 team income 确实反映公司价值。市场只能执行这些权重，不能消除错误、政治性或滞后的管理判断。
- **观察 2：credit 可以与具体硬件解耦。** chip 和 chip-hour 都绑定资源类型与地点，是零和量；credit 可以继续增发，由 pool 的 exchange rate 自动调整购买力，因此供给增加、clawback 或临时给团队加权时不必逐项收回物理 quota（§1、§2）。
  - **依赖假设**：用户理解“余额更多不一定购买力更强”。同一 pool 的总 purchasing power 由 market weight 固定，增发 credit 会稀释该 pool 的本地货币。
- **观察 3：价格同时是分配工具和拥塞信号。** 新芯片或冷门地点价格低，用户会延迟、迁移或适配 workload；论文的部署案例显示新资源价格和 occupancy 会随供给快速变化（§3，图 9–11）。
  - **依赖假设**：任务有可替代的时间、地点或 accelerator type，迁移成本低于价格差；硬 deadline、固定 topology 和 serving workload 不满足这一点。
- **观察 4：市场需要足够“厚”。** 按单个 cell 清算会因供需稀疏而波动，小 cell 的平均 occupancy 比大 cell 低约 3%；QM 因而汇总成 Global Cell，以局部 placement 精度换流动性（§2.1）。
  - **依赖假设**：全局总量 quota 大多能由下游 scheduler 落到某个真实 cell 和连续 topology；论文仍观察到约 10% 场景存在 cell-level contention。
- **假设 1：参与者大体合作且接近 price taker。** Google 内部政策禁止故意伤害其他团队；一般对抗市场中的价格操纵、假 demand 和货币兑换攻击并未被当前机制完全解决（§4、§5、附录 B）。

## 核心方法

### 两层预算把组织目标变成购买力

公司给 pool `k` 分 market weight `W_k`，表示业务单元的总购买力。pool 管理者给团队配置持续产生 credit 的 income；若该 pool 每单位时间共 mint `C_k` 个本地 credit，一个 credit 的全局价值就是 `W_k / C_k`。因此 pool 内可自主决定谁得到多少 income，但不能靠多印 credit 增加整个业务单元的市场力量（§2，图 2）。

团队以 job priority queue 提交 demand。系统提供自动 bidder，从队首开始估计 job 成本并形成 team-level bid；用户可设置每个 job 的最高可接受价格（limit order）、团队最大 income leverage 和更复杂的队列策略。默认设置承担大部分工作，dashboard 则显示实时价格、历史价格、balance、income 和 burn rate（§2）。

### 用 blended price 同时尊重自有 pool 和共享资源

每类 accelerator 的供给分成 pool 自有 supply 与全局 shared supply。对给定 reference price，QM 先求每个 pool 需要从共享市场购买多少资源，以及混合自有“免费”供给后的内部价格。一个 team 在价格 `p` 下最多获得“实际 demand”和“bid 能买到的数量 `b/p`”中的较小值。

随后系统寻找最低 reference price，使所有 pool 对 shared supply 的总购买量不超过实际供给；供大于求时价格为零。内部 pool clearance 和全局 clearance 形成嵌套 binary search，经过预处理可做到近线性时间。最终得到的是逻辑 quota，再交给 scheduler 安排 job（§2）。

### 把高频市场与低频记账解耦

QM 是一个为可用性做复制的中央 monolithic binary。市场循环少于 1 分钟运行一次；income 与 charge 每 5 分钟结算一次；capacity 通常约每小时导入，紧急变化可在分钟级人工传播。credit、capacity、quota 和 demand 都写入强一致 datastore，并按 timestamp 标记 cycle（§2.1，图 3）。

记账慢于市场不会立即造成失控，因为 **minimum affordable duration** 只允许团队报出按当前 burn rate 至少能维持 120 分钟的 bid。核心 `RunAuction` 是无状态纯函数，输入、输出和辅助数据都被保存，可用完全相同的 handler 离线 replay 历史 cycle、复现 incident 和比较新算法。新功能还能按 resource type 灰度。

QM 不直接运行 job，而是给 scheduler 生成 quota。市场故障时，scheduler 使用最后一份有效 quota 回退到静态 pool；效率和 prioritized occupancy 会下降，但 job execution 不会跟中央市场一起停摆。

### 在市场抽象与物理调度之间搭桥

最初 QM 只是 above-cell scheduler 上方的异步 coordinator。市场立刻改变 quota，resource manager 却要慢慢把 capacity 在 legacy pool 间搬移，产生状态不一致。近期实现把 above-cell scheduling 上移到 QM，统一跨 pool 排队，把 end-to-end 反馈降到约 30 秒；代价是中央组件 failure domain 更大（§2.1）。

市场仍把 accelerator 当成标量，只明确给 principal resource 定价；CPU、RAM、disk 和 network 按 accelerator quota 配给。64-chip job 可能要求完整 `4 × 4 × 4` cube，单一价格只保证总芯片存在，不保证恰好拼成该 geometry。cell-level scheduler 继续负责 bin packing 与 defragmentation，未来才考虑 topology-aware pricing。

## 设计取舍

- **动态效率换取可用性确定性**：静态 pool 给团队硬保证；QM quota 随价格变化，更适合可延迟、可抢占训练，不适合严格 SLA serving。
- **单一价格换取多资源精度**：用户只需理解 accelerator price，系统也能快速清算；CPU、network、location 和 topology 的真实稀缺性被留给 scheduler，可能得到“有 quota 但放不下”的结果。
- **Global Cell 换取市场流动性**：聚合后价格更稳，小 cell 不再形成薄市场；约 10% 场景仍有局部 contention。
- **中央纯函数换取较大 blast radius**：replay、全局一致性和跨 pool 优化更简单，但错误 rollout 可影响大范围 fleet；last-snapshot fallback 只保可运行，不保高效。
- **自动 bidding 换取有限表达力**：默认 queue 降低用户负担，但 job 的 scientific value、deadline 和失败风险最终仍被压成 bid 与 limit price。
- **内部合作环境换取机制简单**：当前系统没有采用更复杂的 anti-gaming auction；移到跨公司或不可信 tenant 环境前不能沿用这一假设。

## 实验与结果

- QM 已部署给数千名日活用户，累计消费数十亿 accelerator-hours，管理数十万 ML accelerator，覆盖 Google 全部 ML fleet 的两位数百分比。它不是小规模模拟，而是跨业务单元生产系统（§1）。
- 对同一种热门资源、规模都为数十万芯片的两个 pool，8 周平均总 occupancy 在 QM 中为 93%，传统 pool 为 75%，相对提高约 24%；其中 opportunistic occupancy 从 33.5% 降到 5.67%。这说明更多占用来自 company-prioritized job，但两个 pool 不是随机分组（§3，图 4–5）。
- 24 周 fleet 数据显示资源类型和总供给持续变化。10 周 bonus-capacity 案例中，serving buffer 与 holding pool 合计带来的 capacity lift 最低约 25%，多数时段更高，峰值超过 100%；绝对规模持续为数十万芯片。25% 是观察窗口最低点，不是平均值或总 bonus 与 committed capacity 的固定比例（§3，图 6–8）。
- 同一批新 accelerator 同时进入 QM pool 和静态 pool 后，QM occupancy 在 10 周内紧跟供给，静态 pool 明显滞后，且前者没有依靠全公司公告。另一个新 resource type 的价格在 4 天内从很低水平快速接近可替代旧芯片，说明用户会响应价格并调整需求（§3，图 9–11）。
- 清算优化把 market-cycle p50 从 100 秒降到少于 30 秒；把 above-cell scheduling 合入市场后，端到端反馈也约为 30 秒。此前调度延迟对应全 fleet 约 1.3% occupancy wastage。与此同时，Global Cell 仍在约 10% 场景发生局部 contention，topology 不可拼成约占 1% 场景（§2.1）。
- 简化理论模型证明：chip-hour mechanism 即使在 uniform value 下也不能保证优于 `1/n` 的全局公平，bi-valued value 下连 Pareto efficiency 也可能失去；市场在一般 heterogeneous value 下满足 Pareto efficiency，并在 agent 平均支付价格不超过全局均价 `f_i` 倍时达到 `min_i(1/f_i)`-fair。证明假设资源可分、总 demand 不低于 supply、单个 agent 不能影响价格，而且 agent 能预估未来 demand/price 并最优分配 budget（§4、附录 A）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| QM 在生产规模可运行并快速响应 | 数十万芯片、数千日活、数十亿 accelerator-hours；cycle p50 少于 30 秒（§1、§2.1） | 单一公司内部、合作参与者 | 强 |
| QM pool 比传统 pool 有更高且更“有价值”的占用 | 总 occupancy 93% 对 75%，opportunistic 5.67% 对 33.5%（图 4–5） | 两个可比但非随机、非同 workload 的生产 pool | 中 |
| 动态价格帮助吸收供给变化 | QM 新资源 occupancy 跟随 supply；新芯片价格 4 天内接近旧芯片（图 9–11） | 少数自然实验，缺少用户迁移成本与其他同时变化因素 | 中 |
| credit 能安全替代具体 chip-hour | pool weight 固定总购买力，新增或 clawback 不必重分物理 quota（§2） | credit 分配正确、exchange rate 与余额处理无 bug | 强 |
| QM 的抽象市场在简化模型中满足 Pareto efficiency，并在条件满足时近似 max-min fair | 定理 3–4 证明简化市场模型的条件性保证（§4） | 真实资源不可分、有 topology、用户未必有 foresight，也可能影响价格 | 中偏弱 |

## 批判性分析

### 论证链条

论文的核心逻辑很清楚：静态 quota 的问题不只是 demand 预测不准，而是没有渠道表达“这一时刻的这项需求值多少钱”；credit 把长期组织权重与具体芯片解绑，实时 price 再把局部信息变成资源选择信号。生产图说明 price 之后 occupancy 和新资源吸收确实变化，理论部分则解释为什么固定 chip-hour 在 heterogeneous value 下会失败。

最需要收窄的是因果和保证。93% 对 75% 来自两个生产 pool 的观察比较，不能排除 workload、管理员、供给质量或接入 QM 的团队本来就更灵活。理论中的市场参与者有未来价格 foresight、按效用最优花预算且不能影响价格；生产系统用默认自动 bidder、离散 gang job 和异步 scheduler。两者方向一致，但论文没有证明实际实现达到理论 equilibrium。

### 假设压力测试

应首先挑选一个拥有大 market share 的业务单元，测其增减 bid 是否能显著改变 clearing price；若能，price-taking 假设失效。再注入 deadline job、只接受单一 cell 的大 cube、不可抢占任务和高迁移成本，比较 scalar quota 与真实 completion rate。这里真正重要的不是 market 是否清算成功，而是得到 quota 的高价值 job 是否按时完成。

货币也需做 adversarial test。业务单元可以先高 income 积累 credit，再降低 mint rate 提高汇率；恶意团队还可提交几乎不可能调度、调度后立刻失败的任务，抬高别人价格却因未运行而不付费。附录提出“按 allocation 收费”等方案，但会误罚因下游冲突没有运行的正常团队，当前没有完整答案。

### 实验可信度

真实生产规模、长时间供给变化、可比 pool、自然发生的新硬件上线和系统自身延迟指标都很有价值。论文也诚实披露 Global Cell contention、1.3% latency tax、约 1% topology mismatch、较高 preemption 和中央 failure domain，没有只展示 occupancy 收益。

不足是多数 y 轴归一化，隐去了价格、供给与 job 数量的绝对分布；没有置信区间、同期 workload matching、逐团队公平性、price volatility、preemption cost、queueing time、job completion、time-to-quality 或模型产出价值。用户“受价格驱动”的结论还可能混有聊天、邮件和团队协调。理论没有通过 replay 对实际 trace 计算 Pareto gap 或 fairness ratio，生产与模型之间缺少一座定量桥梁。

### 系统性缺陷

QM 把困难的价值判断从芯片分配转移到 market weight、team income 和 bid policy，并没有消除它。内部价格优化的是组织给出的购买力，不必然等于科学价值、营收或用户效用。团队可能囤币、拆 job、选择性 checkpoint 或制造 demand；而管理员增发 credit 又会造成同 pool 通胀，用户很难直观看懂余额实际价值。

工程上，中央 coordinator、Global Cell 和 principal-resource pricing 都有意牺牲局部精度。市场分到的 quota 可能因 location、network 或 cube geometry 无法使用；按实际 occupancy 收费又允许 phantom demand 抬价。fallback 保证 scheduler 继续运行，却会回到过期 quota；大规模价格 bug、权重误配和 replay 之外的新状态组合仍有较大 blast radius。

## 局限与后续工作

- **局限 1**：部署结果主要报告 occupancy，缺少 job completion、deadline miss、preemption waste、模型产出和逐团队公平性，无法证明 93% occupancy 等于更高业务价值。
- **局限 2**：理论只覆盖单一、可分资源和有 foresight 的 price taker；生产任务具有 gang size、topology、location、辅助资源和不完整信息。
- **局限 3**：Global Cell 在约 10% 场景仍有局部 contention，topology gap 约占 1% 场景；单一 accelerator price 不能表达全部约束。
- **局限 4**：currency conversion 与免费抬价攻击尚无兼顾简单 UX 和鲁棒性的完整方案，安全性依赖公司内部政策。
- **后续工作 1**：对实际 trace 计算 ex-post Pareto gap、`f_i` 与 max-min ratio，并按团队规模、业务单元和 job 类型报告长期分布。
- **后续工作 2**：把 deadline、gang shape、location、network 和 energy 作为受控附加信号，而不是直接引入难操作的完全组合拍卖。
- **后续工作 3**：建立 shadow market 与故障注入，验证错误 price、过期 quota、datastore 延迟和中央 coordinator outage 下的恢复、限损与回滚。
- **后续工作 4**：用 matched workload 或逐步 rollout 做更强因果比较，同时报告 completion time、useful accelerator-hours 和用户迁移成本。

## 相关

- **相关系统**：Karma、static pool、above-cell scheduler、cell-level scheduler
- **相关概念**：动态定价、Pareto efficiency、max-min fairness、resource allocation、market mechanism
- **同会议**：[[OSDI-2026]]
