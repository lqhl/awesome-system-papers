---
type: theme
topic: Finance
theme_kind: domain
member_tag: domain/finance
candidate_tags: [finance, quant-trading, asset-pricing, factor-mining, portfolio-optimization]
paper_count: 6
first_generated: 2026-04-24
last_updated: 2026-08-19
tags: [topic-overview, finance, quant-trading, alpha-factors, llm-agent, time-series, market-efficiency, portfolio-optimization]
---

# 量化投研（Finance）综述

> 本 theme 关注如何把市场信息转化为可审计的投资研究结论，而不是泛金融 AI。六篇核心论文分别提供研究先验与可执行搜索空间、signal / factor / model 生成、时间一致验证以及 portfolio / risk 映射；其中只有 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 形成 hypothesis → code → backtest → feedback 的自动研究内环，且没有任何工作覆盖 live deployment、strategy retirement 与 crash recovery。

## 定义与边界

纳入范围包括：直接定义量化投研的研究空间、数据与信号、预测模型、回测与选择协议、组合与风险映射，或自动化这些阶段的工作。排除支付、信贷、保险、反欺诈和金融问答等泛金融应用；没有金融数据或投资评价的通用 agent；以及只生成市场评论、没有可执行研究产物或时间一致验证的系统。

“纯量化”和“金融 + Agent”不拆开。前者定义搜索空间、baseline、verifier 和下游约束，后者负责连接这些组件。Agent 是编排方法，不是与 factor、forecast 或 portfolio estimator 平级的金融任务类别。一篇论文是否同时属于 [[Auto-Research]] 需要独立判断：当前只有 R&D-Agent(Q) 闭合了研究反馈循环，其余五篇仍只是 Finance 核心。

`AI4Finance` 也不构成当前独立 theme。TimesFM-Fin、News Shock 和 R&D-Agent(Q) 都使用 AI，但分别回答预测、资产定价和研究编排问题；用“是否用了 AI”组织它们，不如按投研流程和验证边界组织。

## 自动化量化投研流程

```text
研究问题与先验
→ signal / factor / model
→ 可执行实现
→ point-in-time validation / backtest
→ 选择与归因
→ portfolio / risk / cost
→ paper/live deployment
→ monitoring / retirement
→ 反馈到下一轮研究
```

| 阶段 | 当前证据 | 主要空白 |
|---|---|---|
| 研究先验与搜索空间 | [[151-Trading-Strategies-SSRN18\|151 Strategies]]、[[101-Alphas-arXiv15\|101 Alphas]] | 知识库如何保持 point-in-time，如何记录已失效策略 |
| Signal / factor / model | [[101-Alphas-arXiv15\|101 Alphas]]、[[RD-Agent-Quant-arXiv25\|R&D-Agent(Q)]]、[[TimesFM-Fin-arXiv24\|TimesFM-Fin]]、[[NewsShock-NBER26\|News Shock]] | 价量、文本和模型信号如何在同一协议下比较与组合 |
| 实现与执行 | 101 Alphas 提供公式；R&D-Agent(Q) 生成并执行 factor / model 代码 | 环境版本、数据快照、随机种子和失败产物缺少统一 provenance |
| 验证与选择 | R&D-Agent(Q) 的 Qlib 闭环、News Shock 的 expanding-window、TimesFM-Fin 的 temporal holdout、[[UPSA-NBER23\|UPSA]] 的 rolling OOS | 自动搜索加剧 multiple testing；缺少 sealed test、purged walk-forward 和独立重复 |
| Portfolio / risk / cost | News Shock 的 MSRR、UPSA 的 shrinkage ensemble | 借券、impact、capacity、约束和净收益没有形成统一 objective |
| 部署、监控与退出 | 无核心论文直接覆盖 | 数据/模型漂移、策略退化、熔断、回滚和人工发布 gate 均为空白 |

## 核心论文

### 研究空间与可执行基线（2 篇）

- [[101-Alphas-arXiv15|101 Formulaic Alphas]] — 公开 101 条生产环境公式，给出持仓期、相关性和 turnover 等统计；它是可执行搜索空间与长期 benchmark，不是自动研究系统。
- [[151-Trading-Strategies-SSRN18|151 Trading Strategies]] — 用统一符号整理 150 多类交易策略、550 多个公式和大量文献；适合作为研究先验与 taxonomy，但没有统一回测和盈利承诺。

### Signal 与模型发现（2 篇）

- [[TimesFM-Fin-arXiv24|TimesFM-Fin]] — 在金融价格序列上持续预训练 TimesFM，并用 log-transform MSE 与动态 mask 改善部分市场预测；FX/crypto 上仍不及 AR(1)。
- [[NewsShock-NBER26|News Shock]] — 从 Reuters 新闻 embedding 中剥离可由传统股票特征预测的部分，以残差构造持续约 18 个月的文本异常；强结果依赖数据许可、正交化和递归估计协议。

### 自动研究循环（1 篇）

- [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] — 用 Specification、Synthesis、Implementation、Validation 和 Analysis 单元闭合 factor/model 研究循环，并用 Thompson Sampling 调度方向；证据仍限于历史回测和短 OOS。

### Portfolio 与风险映射（1 篇）

- [[UPSA-NBER23|UPSA]] — 将多个 ridge portfolio 组合成非负 ensemble，在高维 factor universe 中学习 nonlinear shrinkage；尚未把交易成本、impact 和 leverage constraint 纳入主目标。

## 自动化成熟度矩阵

这里的成熟度衡量自动化覆盖范围，不代表论文证据质量：`M0` 是知识或候选空间；`M1` 产生可执行 artifact 并有经验验证；`M2` 在固定目标下自动选择或组合；`M3` 形成结果会改变下一轮假设或实现的研究闭环；`M4` 还具备版本化状态、恢复、监控和人工发布 gate。

| 论文 | 成熟度 / 覆盖 | 闭环 | Verifier | Leakage / OOS | 成本 | 状态、恢复与人工 gate |
|---|---|---|---|---|---|---|
| [[151-Trading-Strategies-SSRN18\|151 Strategies]] | M0；策略先验与公式模板 | 否 | 文献指针；无统一数值回测 | 无 OOS 协议 | 样例代码可选线性成本 | 选择、实现和验真全部由人完成 |
| [[101-Alphas-arXiv15\|101 Alphas]] | M1；可执行 signal DSL | 否 | WorldQuant 私有生产统计 | 无显式 train/test split | 报告 turnover / CPS，收益未扣成本 | 人工筛选与披露；无监控、失效检测或恢复 |
| [[TimesFM-Fin-arXiv24\|TimesFM-Fin]] | M1；训练、预测、mock trading | 否 | 方向指标与 market-neutral mock trading | 2023+ 单次 temporal holdout | 8×V100 约 1 小时；PnL 按零交易成本 | 仅模型 checkpoint；无 drift、restart 或 live gate |
| [[NewsShock-NBER26\|News Shock]] | M1；文本 signal 到 managed portfolio | 否 | Expanding-window MSRR、多模型/新闻源稳健性 | 递归 OOS；无 2023+ live 证据 | 换手约 45%–75%，只做 10 bps 敏感性 | 有滚动估计，无版本恢复；特征和解释由人决定 |
| [[UPSA-NBER23\|UPSA]] | M2；固定 factor universe 下自动组合 | 否，权重不反馈研究假设 | LOO utility、rolling OOS 与 simulation | 1981–2022 time-OOS；LOO 非时序感知 | 报告 turnover，未计 impact 和 borrow | 保存 rolling weights，无 solver fallback、监控或回滚协议 |
| [[RD-Agent-Quant-arXiv25\|R&D-Agent(Q)]] | M3；假设、代码、回测、分析和下一轮调度 | 是，限历史回测内环 | 执行/相关性检查 + Qlib IC、IR、MDD | Schema 隔离减少显式泄漏；重复选择仍可能 research-overfit | 30 loops API 少于 10 美元；未覆盖 live impact | Knowledge forest 与 SOTA cache；未测进程重启、状态失效或发布 gate |

当前语料只有一个 M3，没有 M4。下一步的关键不是再做一个会调用工具的 agent，而是把历史回测内环升级为可审计、可恢复、能安全接入 paper trading 的研究系统。

## 主题综述

### 研究先验从手写资产变成自动系统的搜索空间

[[101-Alphas-arXiv15|101 Alphas]] 和 [[151-Trading-Strategies-SSRN18|151 Strategies]] 代表由行业研究者有限披露公式与策略知识。到了 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]]，手写公式的角色从 generator 变成 benchmark 与先验：agent 负责提出和实现候选，但仍需要这些可执行模板定义合理语法、对照强度和失败模式。自动化没有消除既有 quant knowledge，反而提高了对高质量、point-in-time 研究语料的依赖。

### Agent、foundation model 和文本 signal 是可组合组件

[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 用语言模型编排 factor/model 搜索，[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 直接从价格序列学习 forecast，[[NewsShock-NBER26|News Shock]] 则从新闻不可预测成分提取信号。三者不是互斥路线：forecast 和文本 embedding 都可以成为自动研究循环的输入，agent 也可以根据回测和相关性反馈决定何时继续、组合或淘汰候选。

真正困难的是比较协议。R&D-Agent(Q) 的 CSI500/NASDAQ100 结果、TimesFM-Fin 的单次 temporal holdout 和 News Shock 的长样本 expanding-window 使用不同市场、horizon、成本与组合方法；任何“agent 优于模型”或“文本优于价量”的结论都需要在同一 point-in-time 数据与 sealed OOS 下重做。

### Signal 越多，下游选择偏差越严重

自动生成 factor、forecast 和高维 embedding 会同时扩大候选数与 $N/T$。[[UPSA-NBER23|UPSA]] 说明，即使每个 signal 都看似有效，统一 ridge、PCA 或 plug-in Markowitz 仍可能在样本外失效。发现速度越高，越需要 nested holdout、候选分母记录、cost-aware portfolio objective 和失效策略清理；否则 agent 只是在更快地扩大 factor zoo。

## Auto-Research 可迁移机制

本节引用通用自动科研工作作为设计证据，不把它们计入 Finance 核心成员：

1. **Artifact 化研究状态**：把 hypothesis、point-in-time dataset、代码 commit、环境、seed、运行结果、claim 和 portfolio decision 变成有依赖关系的对象。
2. **Generator / verifier 分离**：agent 可以生成候选，但 sealed OOS、独立重执行和成本/风险检查不能由同一反馈通道反复调参。
3. **证据失效传播**：数据修订、成本模型或 evaluator 变化时，自动 invalidate 下游 backtest、claim 和 portfolio；[[EviGraph-arXiv26|EviGraph]] 提供了可迁移的依赖图思路。
4. **失败知识库**：保留无效 factor、重复 signal、实现错误与 regime-specific failure，避免只积累赢家；[[AutoScientists-arXiv26|AutoScientists]] 展示了 champion 与 dead-end registry 的价值。
5. **过程指标**：同时报告 valid candidate yield、失败类型、avg@k / best@k、human interventions、总 token / compute / wall-clock，而不只报最高 IR。
6. **明确人工 gate**：人类至少负责 universe、risk appetite、数据许可、最终 OOS 解封与 paper/live release；目标不是追求无人化。

## 长程可靠性压力测试

运行 12 小时不能单独证明长程能力。Finance 只把 [[Long-Horizon-Agents|长程智能体可靠性]] 当成熟度检查，而不作为另一个金融分类：

| 故障注入 | 应验证的行为 | 指标 |
|---|---|---|
| Context compaction / 进程重启 | 恢复 hypothesis、数据版本、代码、实验队列与当前 best | 恢复率、恢复时间、额外成本 |
| 异步 backtest timeout / stale result | 结果不会绑定到错误代码或旧数据 | 错配率、重复执行率 |
| 数据修订 / evaluator 升级 | 自动失效所有依赖旧输入的结果与 claim | 失效传播完整率 |
| 虚假高分 / leakage candidate | 隔离候选并回滚 best state | 污染持续轮数、best-state 保持率 |
| 损坏 checkpoint / optimizer failure | 回退到最后可验证状态并继续 | 成功降级率、性能损失 |
| Paper-trading 副作用重试 | 通过 idempotency key 避免重复委托或资源消耗 | 重复副作用数 |
| 研究预算从短到长扩展 | 更长预算是否持续改善，而非停滞或过拟合 | IR/OOS yield 对 actions、wall-clock、compute 的曲线 |

六篇核心目前均未完整做过这些实验。R&D-Agent(Q) 最接近长时自动循环，但只证明历史回测内环可运行，没有证明 restart/recovery correctness。

## 共同观察

1. **Agent 是 orchestration layer，不是新的 alpha 类型。** 它连接问题、代码、回测和选择；真正的候选仍来自公式、模型、文本和其他数据模态。
2. **自动化依赖可执行 benchmark anchor。** 101 Alphas、Alpha 158/360 和固定 Qlib 协议让 agent 有可比较目标，但旧公式的生产统计与现代公开数据并不等价。
3. **Point-in-time 比“LLM 不看 raw data”更重要。** Schema 隔离减少显式 data snooping，却不能消除预训练记忆、反复候选选择和短 OOS 带来的自适应过拟合。
4. **Signal 生成和 portfolio construction 不能分开评价。** News Shock、TimesFM forecast 和 agent factors 的 gross predictive power，最终都要经过相关性、turnover、capacity 和 shrinkage。
5. **当前最大空白在运行治理。** 没有论文同时覆盖数据/代码/claim provenance、策略 retirement、恢复、paper trading gate 和 live monitoring。

## 假设冲突与脆弱点

1. **可解释 factor 与直接 forecast 谁更适合自动研究？** 前者便于审计和组合，后者减少人工特征工程；两者尚无等数据、等成本、等 portfolio backend 的比较。
2. **更多候选究竟增加发现率还是增加选择偏差？** R&D-Agent(Q) 鼓励持续生成，UPSA 则提醒 $N/T$ 和 covariance noise 会随 factor pool 扩大。
3. **价量与文本 signal 是互补还是重复定价？** News Shock 的残差构造试图隔离传统特征，但尚未和自动 factor pool、TS forecast 做联合正交化。
4. **强回测 verifier 会不会训练出 evaluator shortcut？** 反复读取 IC、IR 和 MDD 可能使 agent 适应特定 split，而不是发现可迁移规律。
5. **历史 OOS 能否代表生产正确性？** 交易成本、market impact、borrow、数据延迟和执行故障可能逆转 gross backtest 的排序。

## 值得关注的方向

### 1. 建立 point-in-time、成本感知的公式复现基准

在统一数据快照、survivorship 处理、purged walk-forward 和成本模型下重跑 101 Alphas 与代表性策略，公开每条公式的有效期、相关性、turnover 和失效原因，为自动研究系统提供 sealed benchmark。

### 2. 构建价量、forecast 与新闻的多模态研究循环

让 agent 在 formulaic factor、TimesFM forecast 和 News Shock 表示之间生成、组合与淘汰候选；固定数据、portfolio backend 和总搜索预算，区分新信息增益与多重比较收益。

### 3. 联合 factor discovery 与 cost-aware portfolio construction

把 R&D-Agent(Q) 产生的高维 factor pool 接入带 transaction cost、capacity 和 exposure constraint 的 UPSA-style backend，报告 gross/net Sharpe、turnover、peak leverage 和 factor 数的 scaling curve。

### 4. 做可恢复的量化研究 agent

把数据、代码、实验、claim 和 portfolio decision 建成版本化依赖图，注入重启、stale result、错误高分、坏 checkpoint 和 paper-trading retry，测量恢复率、失效传播和重复副作用。目标是把当前 M3 历史回测内环推进到带人工发布 gate 的 M4。
