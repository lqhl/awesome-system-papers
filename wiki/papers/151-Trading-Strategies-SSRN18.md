---
type: paper
name: 151 Trading Strategies
full_title: "151 Trading Strategies"
authors: [Zura Kakushadze, Juan Andrés Serur]
venue: SSRN
year: 2018
tags: [finance, quant-trading, trading-strategies, asset-classes, reference, encyclopedia]
source_pdf: "[[techreport18-kakushadze-151-strategies.pdf]]"
source_md: "[[techreport18-kakushadze-151-strategies]]"
---

# 151 Trading Strategies (SSRN 2018)

> **一句话总结**：Kakushadze 与 Serur 将 **150+ 跨资产类交易策略**压缩成统一符号体系的公式手册（**550+ 公式、~2000 参考文献、900+ 术语**），明确声明**不承诺盈利**、正文**不含数值回测**；核心观察是金融市场人造且策略短命，因此价值在于 taxonomy + 可复现模板，而非 alpha 发现——Appendix A 仅提供 dollar-neutral 日内 mean-reversion/momentum 的 R 样例代码。

## 问题与动机

量化金融知识高度碎片化：期权组合、股票 factor、固定收益 carry、ETF rotation、波动率风险溢价、外汇 carry、商品 roll yield、加密货币 ML signal、global macro、税收套利等各自有独立文献与行业惯例，但缺少**统一符号、统一 portfolio 约束表述、统一参考文献入口**的 cross-asset 参考书。从业者要「walk the walk」需要知道行业里**曾经认真考虑过哪些策略族**，以及每种策略在数学上如何落到 holdings / payoff / break-even 上。

本书定位是 **descriptive & pedagogical encyclopedia**，不是 cutting-edge research。作者 claim 的边界非常清楚：不提供「如何赚钱」指南，只提供「人们考虑过什么」的公式化描述；任何 profitability 都取决于 implementation、transaction cost、slippage 与 regime change（Introduction 与 Appendix B 均反复强调 disclaimer）。这与同作者前作 [[101-Alphas-arXiv15|101 Formulaic Alphas]] 形成互补：前者公开 **101 条股票 alpha 显式公式**，本书把视野扩到 **几乎所有常见 asset class / trading style**。

项目起源是 2015 年「101 Trading Strategies」论文计划，最终膨胀为 350+ 页、160–170 条策略（计数方式不同）的专著；2018 年作者因出版流程问题将 SSRN 版免费开放（Preface 详述）。目标读者是 academic、practitioner、学生与 aspiring quant researcher。

## 关键观察 / 隐含假设

- **观察 1：金融市场是人造物，策略会「死亡」**——NYSE 2006 起从 specialist 系统转向电子交易后，许多 statistical arbitrage 策略隔夜失效；随后 HFT 进一步压缩利润。作者用此说明「过去有效的公式」不能保证未来有效。
  - **依赖假设**：策略 edge 来自**特定市场微观结构 + 参与者行为**的稳定组合，而非物理定律式的不变规律。
  - **可能失效场景**：交易所规则变更、流动性迁移、监管变化、算法交易渗透率上升时，书中任意模板都可能突然失效——书中不会预警具体哪条。
- **观察 2：cross-sectional / 大样本统计策略比 single-stock 技术分析更有「科学」基础**——Section 3.21 明确指出，单股 MA 交叉、支撑阻力、channel、单股 KNN 被许多专业人士视为 unscientific；而 momentum、mean-reversion、stat arb 依赖**行业相关性、factor stratification、投资者共识的统计放大**。
  - **依赖假设**：同一 industry/cluster 内股票 return 存在可 exploit 的短期偏离，且可通过 dollar-neutral 组合与 risk model 管理 idiosyncratic risk。
  - **可能失效场景**：行业边界漂移、factor crowding、相关性结构突变（危机期）时，cluster-neutral 残差不再 mean-revert。
- **观察 3：现代 alpha 极淡，必须 mega-alpha 组合才可交易**——Section 3.20 引用 [[101-Alphas-arXiv15|101 Formulaic Alphas]]：单条 alpha 无法覆盖成本，需将数十万条 faint signal 用 nontrivial weights 合成；权重 procedure 引用 Kakushadze & Yu 2017b/2018a。
  - **依赖假设**：alpha 之间相关结构稳定、历史 realized return 可估计 future weight；流动性足以同时交易 2500 只美股。
  - **可能失效场景**：alpha decay 不同步、相关性 spike、capacity 约束——书中只给权重公式，不验证组合后 Sharpe。
- **假设 1：公式模板 + 文献指针足以支撑「百科全书」claim，无需正文实证**——全书刻意不含 numeric simulation / backtest / empirical study，把证据外包给 ~2000 篇参考文献。
  - **证据强度**：**弱**（就「策略有效」而言）；**强**（就「文献与公式覆盖」而言）——Bouchaud 等书评也承认 profitability 取决于 implementation details。

## 核心方法

全书按 **asset class × strategy family** 组织，每条策略尽量给出：**经济直觉 → 数学 payoff/信号 → portfolio 权重约束 → 关键参数（formation/holding period、decile cut、MA 长度等）→ 参考文献**。统一符号贯穿期权 break-even、股票 decile sort、固定收益 duration-neutral butterfly、ETF dual-momentum filter 等。

**资产类覆盖（20 章）**：

| 章节 | 内容要点 |
|------|----------|
| Ch.2 Options | ~57 种组合策略：covered call/put、spread、straddle/strangle、butterfly/condor、calendar/diagonal、collar、seagull 等；区分 directional vs non-directional、bullish vs bearish、volatility vs sideways |
| Ch.3 Stocks | price/earnings momentum、value、low-vol anomaly、implied vol、multifactor、residual momentum、pairs/mean-reversion（单/多 cluster、weighted regression）、MA 系列、event-driven M&A、KNN、**mean-variance stat arb + dollar-neutrality**、market-making、**alpha combos** |
| Ch.4 ETFs | sector momentum rotation（含 MA filter、dual-momentum）、alpha rotation、R² selectivity、IBS mean-reversion、LETF 负 drift 套利、multi-asset trend following |
| Ch.5–6 Fixed Income & Indexes | bullets/barbells/ladders、immunization、butterfly 变体、yield curve、CDS/swap spread arb、cash-and-carry、dispersion、index ETF intraday arb |
| Ch.7–10 Vol/FX/Commodities/Futures | VIX basis、vol risk premium、variance swap、FX carry & triangular arb、roll yield、hedging pressure、trend/contrarian |
| Ch.11–17 结构性/另类 | CDO/MBS、convertible arb、税收套利、通胀/天气/能源、distressed、real estate、REPO 等 |
| Ch.18–19 Crypto & Macro | BTC **ANN**（技术指标 → quantile 分类 → softmax）、**naive Bayes** sentiment；fundamental macro momentum、通胀 hedge、跨国债券 factor sort |
| Ch.20 Infrastructure | 基础设施资产 diversification（篇幅较短） |

**股票策略的「标准配方」**（反复出现）：在 universe 上按 signal sort → top/bottom decile（或 quintile）→ long-only 或 dollar-neutral（$\sum w_i = 0$，$\sum |w_i| = 1$）→ uniform 或 $1/\sigma$、$1/\sigma^2$ 加权 → 固定 holding period（momentum 常用 12-1 formation + 1 month hold）。Stat arb 则走 expected return $E_i$ + covariance $C_{ij}$ → Sharpe 最大化或 mean-variance 目标 + Lagrange multiplier 实现 dollar-neutrality（Eq. 354–358）。

**ML 策略**（Ch.18）：crypto 缺乏 fundamentals，故依赖 technical indicator + ANN quantile forecast，或 Twitter sentiment + naive Bayes；作者明确警告 **over-fitting** 自由参数（$\tau_a$、$\lambda_a$、hidden layer 规模等）。

**Appendix A — R backtest 样例**（全书唯一可执行代码）：`qrm.backtest()` 演示 **intraday open-to-close**、dollar-neutral、universe 按 ADDV 每 `d.r` 天重选、risk model（`qrm.cov.pc` / heterotic model）、`bopt.calc.opt` 优化持仓；区分 **delay-0 mean-reversion** vs **delay-1 momentum**；可选 Almgren et al. 线性成本近似（默认 ~10 bps）。明确**不处理 survivorship bias**，但声称对日内策略影响有限。

## 设计取舍

- **取舍 1：广度换深度**——150+ 策略平均每条 1–3 页公式，复杂策略（ANN、weighted regression mean-reversion）更长，但无一做到 production-grade 完整 pipeline（数据清洗、borrow cost、corporate action、regulatory constraint）。
- **取舍 2：公式统一换实现多样性**——同一「momentum」在不同章节 decile、skip period、weighting 可选方案众多，读者必须自行选定；作者把选择空间留给 backtest，正文不给默认最优参数。
- **取舍 3：参考文献极其丰富换正文零实证**——每章末尾 references + 全书 Glossary/Acronyms/Math Notations/Index；避免重复已有实证文献，但也使读者无法从本书本身判断策略当前是否仍盈利。
- **边界条件**：期权章节适合** payoff 结构学习与对冲直觉**；股票 factor 章节适合**与 Fama-French / Asness 文献对照**；market-making 章节仅**概念性**（承认 Rule 359 在 toxic flow 下必亏）；crypto ML 章节在**高噪声、小样本**下极易过拟合；distressed / tax arb 等强依赖法域与事件细节，公式只是骨架。

## 实验与结果

本书**正文不包含**系统性的 numeric backtest、Sharpe 表或 alpha decay 曲线——这是作者 intentional design，而非遗漏。可陈述的「结果」均为**元层面**：

- **150+ 策略**均有公式化描述（简单策略 concise，复杂策略 multi-page）
- **550+ displayed equations** + 大量 inline math
- **~2000 bibliographic references** + **900+ glossary/acronym/math definitions**
- Appendix A 输出示例指标：total P&L、annualized return、**Sharpe ratio**、**cents-per-share**——但**未给出具体数值结果**，仅为代码框架
- 外部书评（Peter Carr、Bouchaud、Kazemi 等）共识：书是 **comprehensive recipe collection / secret sauce 揭秘**，**不声称**回测盈利；Jim Liew 调侃「一切都变 beta 了」
- 学术/工业界将其用作 **quantitative strategies taxonomic reference**，被后续自动化 factor mining（如 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]]、[[AlphaEvolve-arXiv25|AlphaEvolve]]）当作 baseline 或灵感来源

## Critical Analysis

### 论证链条

作者逻辑链是：**(1)** 市场人造且策略短命 → **(2)** 因此不应把本书当 profit manual → **(3)** 用统一公式描述跨资产策略空间 + 指向文献与样例代码，帮助读者 build intuition 与 reproduction starting point。这条链在 **pedagogical claim** 上闭合。

断裂出现在读者若把「公式存在 + 文献曾报告有效」外推为「策略现在仍有效」——作者虽多次 disclaimer，但全书体量与权威作者背景（WorldQuant、Quantigicr Solutions）容易让读者 subconsciously 当作 alpha cookbook。Section 3.21 对 technical analysis 的批判与 Section 3.11–3.15 仍收录 MA/channel 策略并存，**没有给出纳入标准**（除主观「cross-sectional 更科学」）。

### 假设压力测试

| 假设 | 压力场景 | 判断 |
|------|----------|------|
| decile sort + 月度 rebalance 可交易 | 小市值、低流动性、高 borrow fee | 论文未量化 capacity；仅 Appendix 用 ADDV filter |
| 行业分类稳定 OOS | M&A、业务转型 | 作者承认 fundamental classification 较稳，statistical clustering 可能漂移 |
| mean-variance + 样本协方差 | $N$ 大、$T$ 短 | 依赖 Kakushadze-Yu risk model 外部文献，本书不讨论 estimator error |
| delay-0 intraday signal | 真实 open 成交不可达 | Appendix 坦承 borderline in-sample，仅用于测 signal strength |
| crypto ANN quantile | regime change、exchange outage | 自由参数多，over-fitting 风险高；训练/测试 split 需读者自建 |

### 实验可信度

- **benchmark**：无统一 empirical benchmark；策略有效性完全外包给外部文献，质量参差不齐、时期各异。
- **baseline**：不与任何生产策略或公开 index 对比。
- **ablation**：无；对 multifactor 组合仅列举 uniform / $1/\sigma$ / rank-average 等 weighting 选项，无性能分解。
- **metric**：Appendix 关注 Sharpe、cents-per-share、linear cost，**未覆盖** tail risk、max drawdown、turnover capacity、borrow、market impact 非线性项。

### 系统性缺陷

- ** survivorship bias**：Appendix 明确不处理；对跨多年日频/月频 factor 策略，这是致命缺口（作者仅辩称日内策略影响小）。
- **regime change**：Introduction 讨论 NYSE/HFT 历史，但各策略章节不写「已知死亡日期」。
- **execution realism**：market-making、dispersion、LETF short-leg 等策略的 queue position、margin、short squeeze 风险多为文字提示，无量化。
- **ML 可复现性**：ANN/Bayes 章节给架构与 loss，不给训练数据、hyperparameter 选择 protocol。
- **运维与合规**：tax arbitrage、money laundering 章节（Ch.17.2）偏教育性列举 dark side；distressed 涉及破产法域。论文未讨论合规与操作风险。
- **可观测性**：作为参考书无「监控指标」概念；若迁移到 production，需自建 PnL attribution 与 factor exposure 仪表板——本书未覆盖。

## 局限与 Future Work

- **局限 1**：正文**零系统性回测**，读者无法从本书直接回答「2020s 哪些策略仍有效、衰减多快」。
- **局限 2**：公式模板留下大量 **implementation degrees of freedom**（decile vs quintile、holding period、weighting、universe filter），易被 data mining 滥用。
- **局限 3**：跨资产策略的 **capital allocation、杠杆、margin、相关性危机** 未统一建模；每章各自为政。
- **局限 4**：加密货币、structured credit 等章节随市场演化最快，2018 年后产品与市场结构已有显著变化（如 crypto ETF、利率路径）。
- **Future work 1**：对书中 **10–20 个代表性策略族**（momentum、stat arb、vol risk premium、FX carry、ETF dual-momentum）做 **统一数据与成本假设** 的 out-of-sample panel backtest，量化 decay 与 capacity——可客观验证百科全书哪些条目仍是 living strategy。
- **Future work 2**：将 Appendix A 的 risk model + optimizer  pipeline 扩展到 **delay-1 多因子组合**，并系统加入 survivorship-free universe、borrow fee、非线性 market impact，测量「公式模板」与「可交易版本」之间的 performance gap。
- **Future work 3**：把 Section 3.20 alpha combo 与 [[101-Alphas-arXiv15|101 Formulaic Alphas]] 公开公式对接，实证检验 **2018 年后 combo weighting procedure** 是否仍改善 cost-adjusted Sharpe。

## 相关

- **同作者前作**：[[101-Alphas-arXiv15|101 Formulaic Alphas]]（101 条股票 alpha 显式公式；本书 Section 3.20 直接引用）
- **自动化 factor / strategy mining**：[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]]、[[AlphaEvolve-arXiv25|AlphaEvolve]]、[[Auto-Research-arXiv25|Auto-Research]]——常以 Kakushadze 公式集为对照或灵感
- **相关概念**：[[Mean-Variance-Optimization]]、[[Statistical-Arbitrage]]、[[Momentum]]、[[Pairs-Trading]]、[[Dollar-Neutrality]]、[[High-Frequency-Trading]]、[[Volatility-Risk-Premium]]
- **同类参考**：期权/固定收益教科书（Hull 等）偏定价；本书偏 **策略 payoff 与 portfolio 构造** 的跨资产索引
- **金融时序基础模型**：[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 等预测模型可视为本书 ML 策略章节的下游工具，但本书不含 neural forecast 的系统评测