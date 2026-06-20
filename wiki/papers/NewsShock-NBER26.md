---
type: paper
name: NewsShock
full_title: "The Inefficient Pricing of News"
authors: [Antoine Didisheim, Bryan T. Kelly, Mohammad Pourmohammadi, Hanqing Tian]
venue: NBER
year: 2026
tags: [news-shock, market-efficiency, llm-embedding, asset-pricing, behavioral-finance, anomaly]
source_pdf: "[[techreport26-didisheim-inefficient-pricing-news.pdf]]"
source_md: "[[techreport26-didisheim-inefficient-pricing-news]]"
---

# The Inefficient Pricing of News (NBER 2026)

> **一句话总结**：金融新闻 LLM embedding 约 10% 可由 JKP 股票特征预测，正交残差「news shock」才是市场缓慢消化的真正新信息——经 MSRR 聚合的多空组合年化 Sharpe 3.1，约为 JKP 异常因子库最大值（1.4）的两倍，预测力可持续 18 个月；异常主要由负面/量化密集新闻的 underreaction（62% 权重）驱动，高关注/模糊新闻则 overreaction。

## 问题与动机

Chen et al. (2026, CKX) 用 [[LLM]] embedding 把新闻文本接入传统资产定价回归，发现股价对新闻信息的反映存在数日延迟，且足以在扣除交易成本后产生统计显著利润。但这类工作隐含地把「新闻 embedding」整体当作外生信息冲击，没有区分其中多少内容其实是「旧闻」——即给定公司基本面、行业归属和已知 anomaly 特征后，本就可预期的叙事。

本文的核心 claim 是：**不剥离可预测成分，会系统性低估市场对真正新信息的定价低效**。作者用 Thomson Reuters 1996–2022 约 670 万篇单股新闻、E5-Mistral-7B 生成 4096 维 stock-month embedding，证明 JKP 132 个特征可解释约 7.5%–10.2% 的 embedding 变异；残差 **news shock** 的月度收益预测力超过 raw embedding 一倍以上，且显著性可延续至 18 个月。由此得到的 anomaly 规模超过 Jensen et al. (2022, JKP) 因子库中全部 132 个异常，并可通过 SAE 解码到 12 个经济主题与四类行为金融渠道。

问题在「信息到达 vs 价格更新」的边界上尤其重要：若大量新闻只是基本面状态的滞后反映，那么 raw embedding 的 predictability 会与 value、quality、momentum 等已知因子重叠，从而把「新闻 inefficiency」与「特征 anomaly」混为一谈。

## 关键观察 / 隐含假设

- **观察 1**：股票新闻 embedding 的内容高度可由持久基本面特征预测，而非由短期价格趋势驱动。
  - **证据**：逐月截面回归 $E_t = S_t \beta_t + \varepsilon_t$ 的 pooled adjusted $R^2$ 约 7.5%；加入 25 个 GICS 行业哑变量后升至 10.2%。Table 3 显示 value、quality、leverage 等主题的单主题 $R^2$ 均值约 3%，而 momentum、short-term reversal 仅约 1%–1.4%。Figure 3 用滞后 1/3/6/12 个月特征预测当期新闻，$R^2$ 分布与 contemporaneous 模型几乎不可区分。
  - **依赖假设**：LLM embedding 确实压缩了与公司「身份」相关的结构性叙事（行业、估值、杠杆、盈利质量），且这些身份在数月内相对稳定。
  - **可能失效场景**：若新闻供给端发生结构性变化（例如 social media 主导、AI 生成新闻泛滥），或 embedding 模型对事件型语言编码方式改变，可预测比例与特征映射可能漂移。

- **观察 2**：可预测新闻成分几乎不预测收益，而不可预测的 news shock 才是强 predictors。
  - **证据**：Figure 4 中 raw embedding MSRR 组合 Sharpe 1.1；仅 cross-sectional demean 后升至 1.7；对 JKP 全量特征 residualize 后 news shock Sharpe 达 3.1。Predictable news 组合 $F^{\star E|S}$ 的 CAPM alpha 大多不显著，而 news shock alpha 在所有设定下均显著；控制 13 个 JKP 主题后，news shock 年化 alpha 29%，$R^2$ 仅 11%。
  - **依赖假设**：市场已基本定价「旧闻」，但对真正意外到达的文本信息反应迟缓；且 MSRR 训练窗口内的映射在样本外仍稳定。
  - **可能失效场景**：若 residualization 使用的特征集不完整，仍把部分 priced-in 信息留在 $\varepsilon_t$ 中，则会高估 news shock anomaly；反之，若过度正交化把可交易信息也剔除，则会低估。

- **观察 3**：news shock 的 mispricing 以 underreaction 为主，但 overreaction 通道可解释且可度量。
  - **证据**：SAE 解码的 5000 个主题中 61% 表现为 underreaction（$\rho_k > 0$）；news shock 组合 62.1% 绝对权重落在 underreaction 主题。Table 5 显示负面情感、量化强度正向预测 $\rho_k$，模糊度与关注度负向预测；联合回归 $R^2 = 4.1\%$。
  - **依赖假设**： contemporaneous news-managed return $F_{t,t}^{\tilde{\epsilon}}$ 与下月 return $F_{t,t+1}^{\tilde{\epsilon}}$ 的相关结构能区分 drift vs reversal；Loughran-McDonald 词典代理与 SAE 主题标签语义稳定。
  - **可能失效场景**：主题级 $\rho_k$ 估计噪声大、样本内选择 148 个重要坐标可能放大极端主题；宏观冲击期（金融危机、疫情）可能同时改变 initial impact 与后续 drift 机制。

- **假设 1**：「embeddings for downstream regression」工作流下，预训练 LLM 的 lookahead bias 对组合绩效影响有限。
  - **证据强度**：中强。Chronologically consistent LLM（CCLLM） point-in-time vs foresight 设定 Sharpe 几乎相同（JKP residual 情形 1.63 vs 1.61）；但换用弱得多的 CCLLM 后 Sharpe 从 3.1 降至约 1.6，说明主要衰减来自模型质量而非 foresight。

- **假设 2**：月频、月末使用当月全部新闻、MSRR 直接优化 Sharpe 足以代表「新闻定价低效」的经济量级。
  - **证据强度**：中。MSE + quintile sort 仍得 Sharpe 2.68（EW H-L），与 MSRR 高度相关（67%），但 MSRR 更贴近可交易目标；论文未覆盖日内执行与实时新闻到达延迟。

## 核心方法

**数据与 embedding 管线**。主样本为 Reuters Real-time News Feed 经 CKX 式过滤后的 6,680,550 篇文章（剔除 3PTY、短/长文、近重复），对齐美股月度收益。每篇文章用 E5-Mistral-7B 对 token embedding 等权平均得到 article embedding，再聚合为 stock-month $E_{i,t}$；对 embedding 做 expanding pooled Z-score 以缓解 anisotropy。覆盖上，月均 4,198 只股票，52.5% 当月至少有一篇新闻，大市值 decile 月均 19.7 篇/股。

**News shock 构造**。核心是对每月全体股票运行截面回归 $E_t = S_t \beta_t + \varepsilon_t$，其中 $S_t$ 为 132 个 JKP rank-standardized 特征（可逐步加入 CAPM/FF3/FF6/行业）。拟合值 $S_t \hat{\beta}_t$ 为 predictable news，残差 $\varepsilon_t$ 为 news shock。Figure 5 显示随机抽取 $k$ 个特征 residualize 时，$k \approx 50$ 后 Sharpe 增益趋于饱和，说明可预测新闻主要由特征间共享信息构成，而非某个孤立因子。

**MSRR 组合**。遵循 Kelly and Xiu (2023)，将高维 embedding 坐标视为 managed factors $F_{t+1} = X_t' R_{t+1}$，通过 ridge-regularized maximum Sharpe ratio regression 学组合权重 $w_t = X_t b$，用 expanding window（最短 12 个月）递归估计，leave-one-out 选 $\lambda$。分解恒等式 $F^E = F^{E|S} + F^\varepsilon$ 把 raw、predictable、shock 三类 news portfolio 放在同一框架下比较。

**可解释性：SAE + 主题聚类**。为破解 dense embedding 的 polysemantic 问题，作者用 Gemma2-9B 预训练 SAE 将文本映射到 131,000 维稀疏坐标，聚焦 Chen et al. (2025) 选出的 5000 个金融相关 feature；对 top-100 激活文章用 LLM 自动命名并人工审计。在 sparse embedding 上重复 JKP 正交化与 MSRR（lasso 约束每期 30 个非零坐标），得到 148 个时变重要主题，手工聚为 12 个经济主题（Earnings、Guidance、Distress、M&A 等）。

**行为渠道检验**。对每个 SAE 主题 $k$ 计算 misreaction $\rho_k = \mathrm{Corr}(F_{t,t}^{\tilde{\epsilon},(k)}, F_{t,t+1}^{\tilde{\epsilon},(k)})$，再回归于 NegSent、Quant、Ambiguity、Attention 四类文本代理，连接 Hong-Stein 传统 under/overreaction 理论与可观测新闻语言特征。

## 设计取舍

- **取舍 1**：用线性截面回归从 4096 维 embedding 中剥离可预测成分，换取与 JKP anomaly 因子直接可比、可递归估计的简洁性；代价是假设 embedding 空间中的「旧闻」可由线性特征张成，可能遗漏非线性交互或宏观状态变量。
- **取舍 2**：MSRR 直接优化 Sharpe 而非 MSE 预测收益，更贴近交易目标但也更依赖 ridge 与训练窗稳定性；MSE quintile sort 作为稳健性仍支持主结论，但 EW H-L Sharpe 2.68 低于 MSRR 3.1。
- **取舍 3**：月频月末批处理所有当月新闻，保守对齐收益，降低微观结构噪声，但牺牲了对「新闻到达后数日内价格调整」的精细刻画（CKX 的日频结论被聚合掉）。
- **取舍 4**：SAE 主题选择用 full-sample return objective（Chen et al. 2025），明确用于解释已确立的 anomaly，而非重新做 OOS 预测；这提升可解释性但引入解释层的 in-sample 选择偏差。
- **边界条件**：在 Reuters/Dow Jones 高质量通讯社、美股、1996–2022、月频 long-short、充足分散化（$N \approx 2500$）时结论最强；第三方新闻源 Sharpe 降至 2.3；大盘股子样本 Sharpe 1.4 主要来自横截面股票数减少而非效率更高。

## 实验与结果

- **主 anomaly**：JKP residualized news shock 年化 Sharpe **3.1**（1996–2022），CAPM alpha 年化 **29%**；JKP 单因子最大 Sharpe **1.4**，MSRR 聚合全部 JKP 因子后仍低于 news shock。
- **Raw vs shock**：raw embedding Sharpe 1.1 → demean 1.7 → JKP residual 3.1；predictable news 组合 Sharpe 显著更弱，说明 inefficiency 集中在残差而非可预期叙事。
- **规模与分散化**：小盘股 news shock Sharpe 2.7 vs 大盘股 1.4，但 bootstrap 实验显示差异主要来自大样本 $N=2500$ vs 大盘股 $N \approx 832$ 的分散化损失，而非大市值更有效定价。
- **持久性**：引入 $\tau$ 月交易延迟后，一个月 predictability 约减半，但需 **≥18 个月** 才衰减至不显著；对比 JKP 异常在 12 个月延迟后大多消失（Figure 10）。
- **换手与成本**：单月 embedding 策略 one-sided turnover **75%**；6 个月滚动平均 embedding 时 turnover 约 **45%**、Sharpe 仍约 **3.0**，假设 10 bps 交易成本后 net Sharpe 仍超全部 JKP 因子（Figure 11–12）。
- **稳健性**：CCLLM point-in-time Sharpe ~1.6–1.9 仍超 JKP；lookahead 与 foresight 模型几乎无差异；Llama3-405B embedding Sharpe **4.1**；Dow Jones 源 Sharpe **3.7**；MSE EW quintile H-L Sharpe **2.68**；5 年滚动 Sharpe 在 2.1–4.5 之间，2018 后略有竞争加剧迹象。

## Critical Analysis

### 论证链条

主链条逻辑闭合且递进清晰：① 新闻非外生 → ② 可预测部分已被定价 → ③ 残差 shock 才承载缓慢调整 → ④ shock anomaly 大于所有已知特征 anomaly → ⑤ SAE 主题与行为代理解释机制。Figure 4/6 把「剥离旧闻」每一步的 Sharpe 增益都可视化，Table 4 证明对 13 个 JKP 主题控制后 alpha 仍上升、$R^2$ 下降，支持「不是简单重述 momentum/quality」的 claim。

薄弱环节在于从「统计残差」到「经济新信息」的命名。线性正交化保证与 $S_t$ 正交，但不保证 $\varepsilon_t$ 与所有已定价公共信息正交（例如未纳入的宏观变量、期权隐含信息、供应链文本）。作者用 lagged characteristics 仍高 $R^2$ 支持「旧闻=基本面身份」，这是合理叙事，但仍是结构假设而非直接观测「信息到达」。

### 假设压力测试

**特征集完备性**：若存在未观测的 firm state 同时驱动新闻与下月收益，news shock 可能吸收 spurious predictability。JKP+industry 已将 $R^2$ 推至 10.2%，边际增益有限，但 macro news、peer network、供应链 shock 未被显式剔除。

**LLM 与数据许可**：主结果依赖 Mistral-7B 与私有 Reuters 数据；CCLLM 将 Sharpe 腰斩表明「新闻 shock 量级」对 embedding 质量高度敏感，可复现性受 compute divide 约束。Chronologically consistent 模型是下界，工业级 point-in-time embedding 流水线仍是开放工程问题。

**组合构造与过拟合**：MSRR 在高维（4096 坐标）上优化 Sharpe，虽有 ridge、OOS expanding window 和多种替代设定（MSE sort、滚动窗、子样本），但直接以 Sharpe 为训练目标仍比传统 factor sort 更易吸收特定样本期的 noise。5 年滚动 Sharpe 在 2018 后走低，与「其他资管采用 LLM 新闻策略」的叙述一致，暗示 live trading 衰减风险。

**交易可行性**：月频月末信号对通讯社新闻尚可，但对高频竞争者仍慢；75% turnover 在 10 bps 成本下仍盈利，但短卖约束、借券成本、小盘股流动性与新闻覆盖缺口（小市值仅 30% 有新闻）会压缩 implementable alpha，论文未做 live portfolio 或 capacity 分析。

### 实验可信度

**强点**：数据规模（670 万篇）、时间跨度（27 年）、与 JKP 全因子库同口径比较、系统性 robustness（LLM 族、新闻源、MSRR/MSE、CCLLM、行业、训练窗）。大盘股子样本与 bootstrap 分离「效率 vs 分散化」是扎实贡献。

**弱点**：baseline 主要是 JKP 特征因子而非 CKX 日频交易策略或最新 NLP asset pricing 模型；net-of-cost 只测 10 bps 单一成本；SAE 解释路径含 full-sample feature selection；第三方新闻仍达 Sharpe 2.3，说明源质量影响大，结论对「高质量通讯社 + 美股」依赖明显。

### 系统性缺陷

论文未讨论生产部署中的工程与风控：实时 embedding 推理成本、新闻去重与实体链接错误、LLM 版本漂移、组合杠杆与风险预算、极端事件下 short leg 的 squeeze 风险。对 tail risk、drawdown 以外的高阶矩、以及 anomaly 与宏观流动性 regime 的交互也着墨不多。可交易性上，29% alpha 在 10% 年化波动标准化组合上惊人，但 absolute capacity 与 market impact 论文未覆盖。

## 局限与 Future Work

- **局限 1**：线性 residualization + 月频聚合可能无法捕捉新闻到达的日内动态与交叉股票网络溢出；CKX 的「数日延迟」与本文「数月延迟」并存，时间尺度关系需更细测量。
- **局限 2**：主结论绑定 Reuters/Dow Jones 与 Mistral 级 embedding；CCLLM 与 BERT 结果显示性能随模型规模单调上升，point-in-time 工业复现成本高昂。
- **局限 3**：SAE 行为解释在 5000 维主题上做 cross-sectional 回归，$R^2$ 仅 4.1%，机制证据是统计关联而非因果识别；148 个精选主题可能遗漏尾部但经济重要的新闻类型。
- **Future work 1**：构建 point-in-time 新闻 shock 流水线（rolling LLM + 实时特征正交化），测量日频/周频延迟结构与交易成本敏感性，检验 anomaly 在 2023+ 样本是否加速衰减。
- **Future work 2**：把 residualization 扩展至宏观、行业 peer、期权与供应链文本，量化「未纳入旧闻」对 Sharpe 的上调幅度，界定 news shock 的因果信息边界。
- **Future work 3**：在 live paper trading 中测试 6 个月平均 embedding 策略的容量、借券约束与新闻覆盖偏误，分离 statistically significant alpha 与 economically deployable alpha。

## 相关

- **相关概念**：[[Market-Efficiency]]、[[Asset-Pricing-Anomaly]]、[[Underreaction]]、[[Overreaction]]、[[LLM]]、[[Behavioral-Finance]]
- **前置/对比工作**：CKX (Chen et al., 2026) — raw embedding 收益预测；JKP (Jensen et al., 2022) — anomaly 基准宇宙；Tetlock (2007)、Lopez-Lira & Tang (2024) — 新闻与价格效率
- **方法组件**：MSRR (Kelly & Xiu, 2023)、Sparse Autoencoder (SAE)、Loughran-McDonald 金融词典
- **同来源**：[[NBER-2026]]