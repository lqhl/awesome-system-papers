---
type: theme
topic: Finance
theme_kind: domain
member_tag: domain/finance
paper_count: 6
first_generated: 2026-04-24
last_updated: 2026-08-18
tags: [topic-overview, finance, quant-trading, alpha-factors, llm-agent, time-series, market-efficiency, llm-embedding, behavioral-finance, portfolio-optimization, shrinkage]
---

# Finance 综述

> 本 topic 收录 6 篇覆盖量化交易 alpha、自动化 quant R&D、time-series foundation model、LLM 嵌入与市场效率、高维 portfolio optimization 的代表作。四条主线并存：**formulaic alpha 作为 baseline anchor**（2015 [[101-Alphas-arXiv15|101 Alphas]] → 2018 [[151-Trading-Strategies-SSRN18|151 Strategies]]）；**两条自动化路径**（LLM agent 生成 factor 的 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] vs foundation model 直接 forecast 的 [[TimesFM-Fin-arXiv24|TimesFM-Fin]]）；**LLM 嵌入用于理解市场效率本身**（[[NewsShock-NBER26|News Shock]]）；以及**高维环境下如何把大量 factor 稳健组合成 SDF**（[[UPSA-NBER23|UPSA]]）。

## 核心论文

### Formulaic alpha 与策略参考库（2 篇）

- [[101-Alphas-arXiv15|101 Formulaic Alphas]] — Kakushadze / WorldQuant 2015。首次公开 **101 条生产环境真实交易 alpha** 的完整 DSL 公式（rank / ts_* / correlation / delta / IndNeutralize 等算子），持仓期 0.6-6.4 天，pairwise correlation 15.9%，$R \sim \sigma^{0.76}$；成为后续所有自动化因子挖掘工作的 de facto benchmark
- [[151-Trading-Strategies-SSRN18|151 Trading Strategies]] — Kakushadze & Serur 2018。**量化策略百科全书**——550+ 公式、2000+ 参考文献、900+ 术语词条覆盖期权/固收/期货/外汇/crypto/波动率/real estate/distressed asset/tax arbitrage 等 13 大类；部分策略嵌入 ANN / Bayes / k-NN 作为 signal generator；textbook 定位，是新人和研究者 taxonomic reference 首选

### LLM-driven 多 agent 自动化 quant R&D（1 篇）

- [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] — Microsoft Research Asia 2025。将 quant 研究分解成 **5 个 LLM agent 单元**（Specification / Synthesis / Implementation-Co-STEER / Validation-Qlib / Analysis）+ **contextual Thompson Sampling bandit** 在 factor vs model 间调度；CSI500 out-of-sample（o4-mini backend）做到 **IR 2.17 / MDD -0.07**，在 NASDAQ100 也 IR 1.77；**全流程成本 < $10**，factor 数只有经典库的 22%；data-centric 隔离（LLM 永远不看 raw market data，只看 schema）从根切除 leakage

### Time-series foundation model 金融适配（1 篇）

- [[TimesFM-Fin-arXiv24|TimesFM-Fin]] — MIT + Preferred Networks 2024。用 **100M 金融时间点**（S&P500/TOPIX500/FX/crypto 多粒度）continual pre-train Google TimesFM；关键修改是 **log-transform MSE**（抗大尺度资产主导 + 抗崩盘 NaN）+ 动态 mask；S&P500 market-neutral mock trading horizon=128 做到 **Sharpe 1.68**（原始 TimesFM 0.42，AR(1) 1.58）；但 currencies/crypto 上 AR(1) 更好 → foundation model 对短期 noisy regime 并无额外优势

### LLM 嵌入与资产定价异常（1 篇）

- [[NewsShock-NBER26|News Shock]] — Didisheim, Kelly et al. NBER 2026。将 Reuters 新闻的 LLM embedding 对 132 个 JKP 股票特征做截面回归，提取不可预测的残差「news shock」；用 MSRR 构建多空组合，**年化 Sharpe 3.1**（1996-2022），是 JKP 因子库中最大异常（Sharpe 1.4）的两倍，预测力持续 18 个月；用 SAE 将 dense embedding 解压为可解释主题，发现 62% 异常权重来自 underreaction（负面/量化密集新闻），38% 来自 overreaction（高关注度/模糊新闻）；经 chronologically consistent LLM 排除 lookahead bias 后结论稳健

### 高维投资组合收缩（1 篇）

- [[UPSA-NBER23|UPSA]] — Kelly, Malamud, Pourmohammadi & Trojani 2023（2026 修订）。把不同 penalty 的 ridge portfolio 组成非负 ensemble，用 LOO 直接优化样本外 quadratic utility；153 个 JKP factors 上年化 Sharpe **1.92**（ridge 1.59、PCA 1.45、Ledoit–Wolf 1.31），样本外 SDF pricing $R^2$ **67%**（ridge 39%）。关键发现不是删除低方差 PC，而是对 eigen-spectrum 非线性重加权；在 recession 中 Sharpe 仅下降 30%，ridge 下降 53%，但结果尚未计入交易成本与 leverage constraint

## 主题综述

### 从「封闭披露」到「公开自动化」的 10 年

2015-2018 的两篇 Kakushadze 工作（[[101-Alphas-arXiv15|101 Alphas]]、[[151-Trading-Strategies-SSRN18|151 Strategies]]）代表的是**工业界有限解密模式**——由在 WorldQuant 有访问权限的研究者把一部分真实生产公式以论文/手册形式公开，从而让学术界第一次对 quant 的公式 anatomy 有系统认识。这是当时唯一可能的「开放」：**策略是手写的，人是 insider**。到 2024-2025，两条自动化路径同时出现，完全绕开「insider 公开真公式」的瓶颈：[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 让 LLM agent **自己生成 factor**，[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 让**大时间序列模型从价格里直接学**。**「手写公式」的角色从「Generator」降格为「Benchmark」**——两篇 2024/2025 工作都把 Kakushadze 的 101 Alphas（以及 Qlib 的 Alpha 158 / 360）作为主要对照基线。这是 quant 领域 10 年间**主体性转移**的最清楚证据。

### 两条自动化路径：agent 路线 vs foundation-model 路线

[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 和 [[TimesFM-Fin-arXiv24|TimesFM-Fin]] 代表两种技术哲学：

- **agent 路线（R&D-Agent）**：LLM 不碰原始数据，只做 **hypothesis → code → 回测 → 反馈**。factor 和 model 仍是小/中规模，靠 LLM 的规划能力组合。优点：可解释、成本 <$10、无 leakage 风险；缺点：每一个 factor 仍是人工特征工程范式，agent 做的是"更快的人脑"
- **foundation-model 路线（TimesFM-Fin）**：大模型直接在价格序列上 continual pre-train，输出就是 forecast。优点：零特征工程、规模化后泛化潜力大；缺点：在 noisy regime（crypto / FX）里跑不过 AR(1)；S&P500 上 Sharpe 1.68 固然好看，但差不多等于 AR(1) 的 1.58——**增量并非来自"大"而来自"continual pre-training 对 horizon=128 的适应"**

两条路线的 empirical 性能均不压倒对方。[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 在 CSI500 IR 2.17 的数字诱人，但那是把 factor mining + model search + strategy ranking 的 "每一步都靠 LLM" 拧在一起的端到端收益；若拆解每一步的边际贡献会发现 bandit scheduler 和 Co-STEER 的累积增益大，而单步 LLM 生成的 factor 本身并不比经典 Alpha 158 强太多。[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 虽然是 zero-feature-engineering，但依赖 TimesFM 的 200M 参数和 8×V100 训练——这个 cost 和 R&D-Agent(Q) 的 <$10/run 对比也是两个不同商业模型。

### Formulaic alpha 的持久性：为什么 Kakushadze 2015 在 2025 仍是基线

[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 的实验表里 **Alpha 158 / Alpha 360** 反复作为对照，这两个 factor 库正是以 [[101-Alphas-arXiv15|101 Alphas]] 的 DSL 风格扩写而成（Qlib 的 Alpha 158 源码导入即 Kakushadze 风格公式）。过了 10 年，写死公式的 Sharpe / IC 仍落在业界自动化系统要击败的范围内——这说明：

1. **formulaic alpha 的信息含量并不低**——价量 OHLCV 加上 rank、delta、correlation 等基本算子组合已经捕获了市场大部分一阶信号
2. **自动化方法的 marginal gain 被 data-centric leakage、regime shift 风险稀释**——R&D-Agent(Q) 不得不专门做 schema-level 隔离和 Bandit scheduler 来稳住新 factor 的 out-of-sample 表现
3. **对策略研究者真正稀缺的是「已验证公式语料」**——[[101-Alphas-arXiv15|101 Alphas]] + [[151-Trading-Strategies-SSRN18|151 Strategies]] 之所以有工具地位，正因为它们给出了 **「生产中真跑过」的明确公式**，这是 retail 数据 + ML training 无法提供的

### News Shock 异常对 quant 路线的含义

[[NewsShock-NBER26|News Shock]] 的发现——news shock 组合 Sharpe 3.1 是 JKP 因子库最大异常的两倍——对本 topic 其他工作提出了一个根本性问题：**当前所有自动化 quant 方法（formulaic alpha、agent factor mining、foundation model forecast）都在用价格/特征数据，但最大的 alpha 源可能藏在新闻文本的不可预测成分里**。这有几层含义：

1. **formulaic alpha 和 agent 生成的 factor 主要基于价量数据**——它们捕获的是已定价的信息，而 news shock 捕获的是市场尚未消化的新信息到达——两者在信息源头上互补而非竞争
2. **TimesFM-Fin 的 forecast 完全是 price-based**，天然的盲点是新闻事件冲击——将 textual news shock 作为 conditioning signal 接入 TS foundation model 可能是下一个突破点
3. **News Shock 的 18 个月预测力持久性**远超 momentum/reversal/PEAD 等传统异常——这意味着 market efficiency 的边界比预想的更宽，为长期 horizon 策略提供了新的 signal source
4. **行为金融维度**：News Shock 揭示的 underreaction（负面/量化密集新闻）和 overreaction（高关注度/模糊新闻）的二分，可以为 agent 系统的 hypothesis generation 提供先验——让 LLM 在生成 factor 时主动偏向 underreaction 模式而非 overreaction 模式

### 从发现 signal 到稳健组合：UPSA 补上的 estimator 层

前五篇论文主要回答「signal 从哪里来」：手写 formula、agent-generated factor、price forecast 或 text shock。[[UPSA-NBER23|UPSA]] 指出，即使 signal universe 已经给定，$N/T$ 较大时 plug-in Markowitz 仍会因 mean / covariance noise 在样本外失败。它补上了此前 Finance topic 缺少的 estimator 层：不是再找一个 alpha，而是学习怎样在 PC spectrum 上收缩全部 alpha。

这个区分直接影响自动化 quant pipeline。[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 若持续生成新 factors，会推高 $N/T$ 并加剧 covariance ill-conditioning；[[NewsShock-NBER26|News Shock]] 的 4096 维 embedding 也必须先压成 managed-factor portfolio。UPSA 的 ridge ensemble 提供一种闭式 nonlinear shrinkage，但当前证据只覆盖 153 个 JKP factor portfolios，尚未证明它能在高换手的 agent factor pool 或 text embedding universe 中保留净收益。

## 共同观察

**1. Formulaic alpha 的信息含量在 10 年后仍是自动化系统的硬 baseline。** [[101-Alphas-arXiv15|101 Alphas]] 的 101 条生产公式（pairwise correlation 15.9%、$R \sim \sigma^{0.76}$）与 Qlib Alpha 158/360 仍被 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 反复击败对照——说明 rank/ts_*/correlation 等基本算子组合已捕获市场大部分一阶信号。**适用边界**：WorldQuant 专有数据上的 Sharpe 无法被 retail 数据独立复现；2010-2013 低波动 regime 的 scaling exponent 在 2020+ 可能漂移。

**2. 自动化 quant 的两条路径对「数据模态」假设截然不同。** [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 假设 LLM 只看 schema 不看 raw data 即可防 leakage，在价量 OHLCV 上生成 factor；[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 假设 continual pre-train 100M 金融时间点可直接 forecast；[[NewsShock-NBER26|News Shock]] 假设 **文本 embedding 残差** 才是最大 alpha 源（Sharpe 3.1 vs JKP 最大 1.4）。**适用边界**：R&D-Agent 的 OOS 窗仅 2024-2025.06；TimesFM-Fin 在 crypto/FX 跑不过 AR(1)；News Shock 依赖 Reuters + JKP 特征正交化质量。

**3. 「手写公式」角色从 Generator 降格为 Benchmark 是 2015→2025 的主体性转移。** [[101-Alphas-arXiv15|101 Alphas]]/[[151-Trading-Strategies-SSRN18|151 Strategies]] 代表 insider 有限解密；[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]]/[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 完全绕开 insider，把 Kakushadze 公式集当对照锚。**适用边界**：151 Strategies 无统一 empirical benchmark，策略有效性外包给外部文献，质量参差不齐。

**4. 市场效率边界可能比传统因子模型更宽——新闻 underreaction 持久 18 个月。** [[NewsShock-NBER26|News Shock]] 的 MSRR 组合预测力持续 18 个月，远超 momentum/reversal/PEAD；SAE 解压显示 62% 权重来自 underreaction、38% 来自 overreaction。**适用边界**：新闻供给结构变化（social media 主导、AI 生成新闻）或 embedding 模型漂移会使 residual 映射失效；过度正交化可能剔除可交易信息。

**5. Signal 数量越多，estimator 层越不能使用 one-size-fits-all shrinkage。** [[UPSA-NBER23|UPSA]] 在 153 个 JKP factors 上把 ridge Sharpe 从 1.59 提至 1.92，且显式 lasso 只增加 0.02 Sharpe、却把月换手从 12.4% 推到 19.5%。这挑战了「factor zoo 应先硬删弱 PC」的直觉：连续 nonlinear reweighting 可能比 sparse selection 更稳。**适用边界**：训练与 pricing test 共用同一 factor universe，且未扣成本；LOO 的 exchangeability 假设对金融时序并不严格成立。

## 假设冲突与脆弱点

**1. Agent 生成 factor vs foundation model forecast：谁该拥有 alpha？** [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 假设 compact factor 库 + bandit 调度可达 CSI500 IR 2.17；[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 假设 zero-feature-engineering 的 TS foundation model 在 S&P500 Sharpe 1.68 已接近 AR(1) 的 1.58——**增量来自 continual pre-training 对 horizon=128 的适应，而非「大」本身**。**脆弱点**：两条路线 empirical 均不压倒对方；R&D-Agent 端到端收益可能被子步骤 bandit/Co-STEER 放大；TimesFM-Fin 依赖 200M 参数 + 8×V100 vs R&D-Agent <$10/run。需 joint system ablation。

**2. 价量 alpha vs 文本 news shock：互补还是竞争？** [[101-Alphas-arXiv15|101 Alphas]]/[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 主要基于 OHLCV；[[NewsShock-NBER26|News Shock]] 证明最大异常在新闻不可预测成分。**脆弱点**：当前自动化 pipeline 对 textual signal 天然盲点；将 news shock 接入 factor pool 或 TS decoder conditioning 尚未系统验证；4096 维 embedding 与价量 factor 的正交性未知。

**3. Data-centric leakage 防护 vs LLM 内部金融知识。** [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 假设 schema-level 隔离从根切除 leakage；论文也承认 "relies solely on LLM's internal financial knowledge" 未接外部 forecast。**脆弱点**：LLM 预训练可能含未来信息模式；bandit 某一臂饱和时会浪费 loop；factor 分支是 IC/ARR 主驱动、model 分支更像 MDD 平滑器——联合收益可能被少数成功 round 放大。

**4. 工业界公式披露 vs 学术可复现性。** [[101-Alphas-arXiv15|101 Alphas]] 绑定 WorldQuant 专有执行；[[151-Trading-Strategies-SSRN18|151 Strategies]] 是 textbook 无统一回测。**脆弱点**：独立研究者在 Yahoo/Qlib 上复现 101 条更可能验证信号定义而非 Table 1 Sharpe；交易所规则/流动性迁移可使任意模板突然失效——书中不预警。需 2015-2025 rolling 复现基准。

**5. 不断扩张 factor zoo vs 高维 estimation noise。** [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 与 News Shock 类方法都鼓励加入更多候选 signals；[[UPSA-NBER23|UPSA]] 则表明 $N/T$ 增大时，未经目标对齐的 Markowitz / covariance shrinkage 会制造严重 IS–OOS wedge。**脆弱点**：UPSA 的 gross factor-level 优势未经过 transaction-cost-aware objective，自动生成的高换手 factors 可能让较低 estimation error 被更高执行成本吞没。

## 值得关注的方向

### 1. 用 LLM agent 做 formulaic alpha 的大规模语料扩写

**方向**：接 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 的 Co-STEER 思路，专门跑一个 factor-mining agent，目标是在给定公共数据集 + 回测框架下，让 agent 生成**百万级**可执行 formulaic alpha 的语料，并按 out-of-sample IC 自动过滤。类似 [[101-Alphas-arXiv15|101 Alphas]] 的 101 条 → 自动化放大到 $10^6$ 条，形成开源因子库。

**为什么小团队能做**：需要的 compute 不在训 LLM，而在 **Qlib 回测 × 并行 alpha 评估**——8 核 CPU 一周可跑数万条。LLM backend 用 o4-mini / DeepSeek / GLM-4 等便宜 API 即可。

**指向这个空白的论文**：
- [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 已证 LLM 能生成可执行 factor，但其目标是"端到端 pipeline"，而非"语料扩写"
- [[101-Alphas-arXiv15|101 Alphas]] 给了明确的 DSL 目标结构

**具体 open problem**：
- 百万级 alpha 的 pairwise correlation 分布如何？是否仍落在 15.9% 附近？
- 规模化 alpha 池的 orthogonal rank 怎么选？如何做 sparse 组合避免 overfitting？
- 多市场 transfer：CSI300 上学到的 alpha 在 NASDAQ100 上的 IC 分布？

### 2. 金融窄域 time-series foundation model 的 scaling 曲线

**方向**：[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 只做了 1 个 fine-tune 点（100M tokens）、1 个 backbone（TimesFM 200M）。有一条明确的 scaling 研究路径：（a）TimesFM 多个尺寸 + 多个 fine-tune data size 做 scaling curve；（b）对比 **金融专用 pre-train from scratch** vs **general TS model fine-tune**，回答"TimesFM 的 general prior 是 help 还是 hurt"。

**为什么小团队能做**：scaling curve 关键是多点 + 同设置对照，单点可以复用 TimesFM-Fin 的开源 code；每点成本 $10^3$ 量级 GPU-hour。

**指向这个空白的论文**：
- [[TimesFM-Fin-arXiv24|TimesFM-Fin]] 给了 recipe（log-loss + dynamic mask）和数据（Yahoo/Binance 公开），但只有 1 个 scaling 点
- 类比自然语言领域的 fine-tune-vs-scratch 争论（Chinchilla 2022）——TS domain 里这场 debate 还没做

**具体 open problem**：
- 100M → 1B 金融 token 时，S&P500 market-neutral Sharpe 的 marginal gain 曲线
- 跨市场 transfer（S&P500 训 → 港股/A 股测）是否有效
- 对 **crypto/FX** 这类原论文失效的 regime，更大模型能否救回来，还是 noise floor 天花板？

### 3. Agent 生成 factor 与 foundation model forecast 的 joint system

**方向**：把 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 和 [[TimesFM-Fin-arXiv24|TimesFM-Fin]] 拼起来——用 agent 生成 factor 作为 TimesFM 的 auxiliary input，或反过来用 TimesFM 的 forecast 作为 agent 的 macro regime feature。这是两条路径首次系统性的 composition 研究。

**为什么小团队能做**：两端都有开源 code（RD-Agent / pfnet-research/timesfm_fin），关键是拼接与 ablation，不需要 from-scratch 训练。

**指向这个空白的论文**：
- [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 明确承认 "current framework relies solely on the LLM's internal financial knowledge"——没接外部 forecast 信号
- [[TimesFM-Fin-arXiv24|TimesFM-Fin]] 的 forecast 只用于 direction prediction，没进 factor 系统

**具体 open problem**：
- TimesFM forecast 作为新 factor 加入 R&D-Agent(Q) 的 factor pool，IC / IR 增益？
- agent 生成的 factor 作为 conditioning token 接到 TimesFM decoder，是否改善 noisy regime（FX/crypto）？
- 两者都训练后的整体 drift — agent 是否倾向生成和 TimesFM forecast 高度 correlated 的冗余 factor？

### 4. 2015-2018 Kakushadze 公式集的 modern replication / 可审计 reproducibility

**方向**：[[101-Alphas-arXiv15|101 Alphas]] 的 101 条和 [[151-Trading-Strategies-SSRN18|151 Strategies]] 的 150+ 策略在现代数据上（2015-2025）的完整复现。作者本人用的是 WorldQuant 私有数据，**没有任何独立第三方做过全部 101 条的系统复现**。

**为什么小团队能做**：Yahoo Finance + Alpha Vantage + Kaggle 公开数据覆盖 US stocks，本任务是工程任务不是研究任务，价值在于**补建立一个持续更新的开源复现基准**，为 1 / 2 / 3 方向都提供 ground truth。

**具体 open problem**：
- 101 条公式在 2015-2025 的 Sharpe 衰减曲线（哪些仍有效？哪些已死？）
- rolling 10 年窗口里这些 alpha 的 pairwise correlation 是否仍保持 15.9% 量级，还是结构性抬升？
- 为自动化工作（R&D-Agent 系列 + AlphaForge 等）提供**固定 split 的 golden benchmark**，让 2025 之后的论文能互相直接比较

### 5. 将 News Shock 信号接入自动化 quant pipeline

**方向**：[[NewsShock-NBER26|News Shock]] 证明了新闻文本的不可预测成分是最强的 alpha 源，但该论文用的是 offline MSRR 组合。一个自然延伸是把 news shock embedding 作为新的一类 factor 接入 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 的 factor pool，或作为 [[TimesFM-Fin-arXiv24|TimesFM-Fin]] 的 conditioning signal，测试两条自动化路线能否从 textual news shock 中提取额外收益。

**为什么小团队能做**：News Shock 构建只需要 Reuters/DJ 新闻数据（可通过 Bloomberg Terminal 或 Refinitiv 获取） + 公开 JKP 特征 + 开源 embedding 模型（E5-Mistral-7B），不需要自己训 LLM。R&D-Agent(Q) 和 TimesFM-Fin 均有开源 code。

**指向这个空白的论文**：
- [[NewsShock-NBER26|News Shock]] 给了完整的 news shock 构建 recipe，且证明 residual embedding 远强于 raw embedding，但未与 agent-based 或 foundation-model-based 的 trading pipeline 做任何集成
- [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 的 factor pool 目前只有价量 factor + 经典 formulaic alpha，未接入文本类信号
- [[TimesFM-Fin-arXiv24|TimesFM-Fin]] 的输入纯为价格序列，未考虑文本模态

**具体 open problem**：
- news shock embedding 的 4096 维中有多少维与价量 factor 正交？加入后 IC/IR 增益？
- news shock 的 18 个月预测持久性能否改善 TimesFM-Fin 在 crypto/FX 上的弱表现？
- 用 SAE 可解释主题做 factor selection——只保留 underreaction 主题的 news shock 坐标，能否进一步提升 Sharpe？

### 6. Cost-aware UPSA 用于自动生成 factor pool

**方向**：把 [[UPSA-NBER23|UPSA]] 作为 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 的 portfolio-construction backend，在 ridge ensemble 的 quadratic utility 中加入可估 transaction cost 与 gross-exposure penalty；对比当前 strategy ranking、single ridge、PCA 与 lasso，判断 nonlinear shrinkage 的 gross Sharpe 优势能否转化为 net performance。

**为什么小团队能做**：两者均有开源 code，核心改动是把每个基础 ridge portfolio 的 LOO return 扩展为 cost-adjusted return，再解同一低维 ensemble problem，不需要训练新模型。

**具体 open problem**：
- factor 数从 50 扩到 5000 时，UPSA、ridge 与 sparse selection 的净 Sharpe / turnover / peak leverage scaling 曲线如何？
- blocked / purged time-series CV 能否替代 UPSA 的 IID/LOO 假设，同时保持 penalty stability？
- 把 News Shock managed factors 加入价量 factor pool 后，UPSA 的 ensemble 是否保留其与传统 anomaly 的互补性？
