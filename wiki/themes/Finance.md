---
type: theme
topic: Finance
paper_count: 4
first_generated: 2026-04-24
last_updated: 2026-04-24
tags: [topic-overview, finance, quant-trading, alpha-factors, llm-agent, time-series]
---

# Finance 综述

> 本 topic 目前收录 4 篇围绕「量化交易 alpha / 自动化 quant R&D」的代表作。一条贯穿线:从 **人工写死公式**(2015 [[101-Alphas-arXiv15|101 Alphas]] → 2018 [[151-Trading-Strategies-SSRN18|151 Strategies]])到 **LLM 生成 factor + model**(2025 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]])和 **time-series foundation model 继续训练**(2024 [[TimesFM-Fin-arXiv24|TimesFM-Fin]])两条并行自动化路径;formulaic alpha 仍然是两条新路径的 benchmark anchor。

## 论文列表

### Formulaic alpha 与策略参考库(2 篇)

- [[101-Alphas-arXiv15|101 Formulaic Alphas]] — Kakushadze / WorldQuant 2015。首次公开 **101 条生产环境真实交易 alpha** 的完整 DSL 公式(rank / ts_* / correlation / delta / IndNeutralize 等算子),持仓期 0.6-6.4 天,pairwise correlation 15.9%,$R \sim \sigma^{0.76}$;成为后续所有自动化因子挖掘工作的 de facto benchmark
- [[151-Trading-Strategies-SSRN18|151 Trading Strategies]] — Kakushadze & Serur 2018。**量化策略百科全书**——550+ 公式、2000+ 参考文献、900+ 术语词条覆盖期权/固收/期货/外汇/crypto/波动率/real estate/distressed asset/tax arbitrage 等 13 大类;部分策略嵌入 ANN / Bayes / k-NN 作为 signal generator;**textbook 定位,是新人和研究者 taxonomic reference 首选**

### LLM-driven 多 agent 自动化 quant R&D(1 篇)

- [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] — Microsoft Research Asia 2025。将 quant 研究分解成 **5 个 LLM agent 单元**(Specification / Synthesis / Implementation-Co-STEER / Validation-Qlib / Analysis) + **contextual Thompson Sampling bandit** 在 factor vs model 间调度;CSI500 out-of-sample(o4-mini backend)做到 **IR 2.17 / MDD -0.07**,在 NASDAQ100 也 IR 1.77;**全流程成本 < $10**,factor 数只有经典库的 22%;data-centric 隔离(LLM 永远不看 raw market data,只看 schema)从根切除 leakage

### Time-series foundation model 金融适配(1 篇)

- [[TimesFM-Fin-arXiv24|TimesFM-Fin]] — MIT + Preferred Networks 2024。用 **100M 金融时间点**(S&P500/TOPIX500/FX/crypto 多粒度) continual pre-train Google TimesFM;关键修改是 **log-transform MSE**(抗大尺度资产主导 + 抗崩盘 NaN)+ 动态 mask;S&P500 market-neutral mock trading horizon=128 做到 **Sharpe 1.68**(原始 TimesFM 0.42,AR(1) 1.58);但 currencies/crypto 上 AR(1) 更好 → **foundation model 对短期 noisy regime 并无额外优势**

## 主题综述

### 从「封闭披露」到「公开自动化」的 10 年

2015-2018 的两篇 Kakushadze 工作([[101-Alphas-arXiv15|101 Alphas]]、[[151-Trading-Strategies-SSRN18|151 Strategies]])代表的是**工业界有限解密模式**——由在 WorldQuant 有访问权限的研究者把一部分真实生产公式以论文/手册形式公开,从而让学术界第一次对 quant 的公式 anatomy 有系统认识。这是当时唯一可能的「开放」:**策略是手写的,人是 insider**。到 2024-2025,两条自动化路径同时出现,完全绕开「insider 公开真公式」的瓶颈:[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 让 LLM agent **自己生成 factor**,[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 让**大时间序列模型从价格里直接学**。**「手写公式」的角色从「Generator」降格为「Benchmark」**——两篇 2024/2025 工作都把 Kakushadze 的 101 Alphas(以及 Qlib 的 Alpha 158 / 360)作为主要对照基线。这是 quant 领域 10 年间**主体性转移**的最清楚证据。

### 两条自动化路径:agent 路线 vs foundation-model 路线

[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 和 [[TimesFM-Fin-arXiv24|TimesFM-Fin]] 代表两种技术哲学:

- **agent 路线(R&D-Agent)**:LLM 不碰原始数据,只做 **hypothesis → code → 回测 → 反馈**。factor 和 model 仍是小/中规模,靠 LLM 的规划能力组合。优点:可解释、成本 <$10、无 leakage 风险;缺点:每一个 factor 仍是人工特征工程范式,agent 做的是"更快的人脑"
- **foundation-model 路线(TimesFM-Fin)**:大模型直接在价格序列上 continual pre-train,输出就是 forecast。优点:零特征工程、规模化后泛化潜力大;缺点:在 noisy regime(crypto / FX)里跑不过 AR(1);S&P500 上 Sharpe 1.68 固然好看,但差不多等于 AR(1) 的 1.58——**增量并非来自"大"而来自"continual pre-training 对 horizon=128 的适应"**

两条路线的 empirical 性能均不压倒对方。[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 在 CSI500 IR 2.17 的数字诱人,但那是把 factor mining + model search + strategy ranking 的 "每一步都靠 LLM" 拧在一起的端到端收益;若拆解每一步的边际贡献会发现 bandit scheduler 和 Co-STEER 的累积增益大,而单步 LLM 生成的 factor 本身并不比经典 Alpha 158 强太多。[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 虽然是 zero-feature-engineering,但依赖 TimesFM 的 200M 参数和 8×V100 训练——这个 cost 和 R&D-Agent(Q) 的 <$10/run 对比也是两个不同商业模型。

### Formulaic alpha 的持久性:为什么 Kakushadze 2015 在 2025 仍是基线

[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 的实验表里 **Alpha 158 / Alpha 360** 反复作为对照,这两个 factor 库正是以 [[101-Alphas-arXiv15|101 Alphas]] 的 DSL 风格扩写而成(Qlib 的 Alpha 158 源码导入即 Kakushadze 风格公式)。过了 10 年,写死公式的 Sharpe / IC 仍落在业界自动化系统要击败的范围内——这说明:

1. **formulaic alpha 的信息含量并不低**——价量 OHLCV 加上 rank、delta、correlation 等基本算子组合已经捕获了市场大部分一阶信号
2. **自动化方法的 marginal gain 被 data-centric leakage、regime shift 风险稀释**——R&D-Agent(Q) 不得不专门做 schema-level 隔离和 Bandit scheduler 来稳住新 factor 的 out-of-sample 表现
3. **对策略研究者真正稀缺的是「已验证公式语料」**——[[101-Alphas-arXiv15|101 Alphas]] + [[151-Trading-Strategies-SSRN18|151 Strategies]] 之所以有工具地位,正因为它们给出了 **「生产中真跑过」的明确公式**,这是 retail 数据 + ML training 无法提供的

## 值得关注的方向

### 1. 用 LLM agent 做 formulaic alpha 的大规模语料扩写

**方向**:接 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 的 Co-STEER 思路,专门跑一个 factor-mining agent,目标是在给定公共数据集 + 回测框架下,让 agent 生成**百万级**可执行 formulaic alpha 的语料,并按 out-of-sample IC 自动过滤。类似 [[101-Alphas-arXiv15|101 Alphas]] 的 101 条 → 自动化放大到 $10^6$ 条,形成开源因子库。

**为什么小团队能做**:需要的 compute 不在训 LLM,而在 **Qlib 回测 × 并行 alpha 评估**——8 核 CPU 一周可跑数万条。LLM backend 用 o4-mini / DeepSeek / GLM-4 等便宜 API 即可。

**指向这个空白的论文**:
- [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 已证 LLM 能生成可执行 factor,但其目标是"端到端 pipeline",而非"语料扩写"
- [[101-Alphas-arXiv15|101 Alphas]] 给了明确的 DSL 目标结构

**具体 open problem**:
- 百万级 alpha 的 pairwise correlation 分布如何?是否仍落在 15.9% 附近?
- 规模化 alpha 池的 orthogonal rank 怎么选?如何做 sparse 组合避免 overfitting?
- 多市场 transfer:CSI300 上学到的 alpha 在 NASDAQ100 上的 IC 分布?

### 2. 金融窄域 time-series foundation model 的 scaling 曲线

**方向**:[[TimesFM-Fin-arXiv24|TimesFM-Fin]] 只做了 1 个 fine-tune 点(100M tokens)、1 个 backbone(TimesFM 200M)。有一条明确的 scaling 研究路径:(a) TimesFM 多个尺寸 + 多个 fine-tune data size 做 scaling curve; (b) 对比 **金融专用 pre-train from scratch** vs **general TS model fine-tune**,回答"TimesFM 的 general prior 是 help 还是 hurt"。

**为什么小团队能做**:scaling curve 关键是多点 + 同设置对照,单点可以复用 TimesFM-Fin 的开源 code;每点成本 $10^3$ 量级 GPU-hour。

**指向这个空白的论文**:
- [[TimesFM-Fin-arXiv24|TimesFM-Fin]] 给了 recipe(log-loss + dynamic mask)和数据(Yahoo/Binance 公开),但只有 1 个 scaling 点
- 类比自然语言领域的 fine-tune-vs-scratch 争论(Chinchilla 2022)——TS domain 里这场 debate 还没做

**具体 open problem**:
- 100M → 1B 金融 token 时,S&P500 market-neutral Sharpe 的 marginal gain 曲线
- 跨市场 transfer(S&P500 训 → 港股/A 股测)是否有效
- 对 **crypto/FX** 这类原论文失效的 regime,更大模型能否救回来,还是 noise floor 天花板?

### 3. Agent 生成 factor 与 foundation model forecast 的 joint system

**方向**:把 [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 和 [[TimesFM-Fin-arXiv24|TimesFM-Fin]] 拼起来——用 agent 生成 factor 作为 TimesFM 的 auxiliary input,或反过来用 TimesFM 的 forecast 作为 agent 的 macro regime feature。这是两条路径首次系统性的 composition 研究。

**为什么小团队能做**:两端都有开源 code(RD-Agent / pfnet-research/timesfm_fin),关键是拼接与 ablation,不需要 from-scratch 训练。

**指向这个空白的论文**:
- [[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 明确承认 "current framework relies solely on the LLM's internal financial knowledge"——没接外部 forecast 信号
- [[TimesFM-Fin-arXiv24|TimesFM-Fin]] 的 forecast 只用于 direction prediction,没进 factor 系统

**具体 open problem**:
- TimesFM forecast 作为新 factor 加入 R&D-Agent(Q) 的 factor pool,IC / IR 增益?
- agent 生成的 factor 作为 conditioning token 接到 TimesFM decoder,是否改善 noisy regime(FX/crypto)?
- 两者都训练后的整体 drift — agent 是否倾向生成和 TimesFM forecast 高度 correlated 的冗余 factor?

### 4. 2015-2018 Kakushadze 公式集的 modern replication / 可审计 reproducibility

**方向**:[[101-Alphas-arXiv15|101 Alphas]] 的 101 条和 [[151-Trading-Strategies-SSRN18|151 Strategies]] 的 150+ 策略在现代数据上(2015-2025)的完整复现。作者本人用的是 WorldQuant 私有数据,**没有任何独立第三方做过全部 101 条的系统复现**。

**为什么小团队能做**:Yahoo Finance + Alpha Vantage + Kaggle 公开数据覆盖 US stocks,本任务是工程任务不是研究任务,价值在于**补建立一个持续更新的开源复现基准**,为 1 / 2 / 3 方向都提供 ground truth。

**具体 open problem**:
- 101 条公式在 2015-2025 的 Sharpe 衰减曲线(哪些仍有效?哪些已死?)
- rolling 10 年窗口里这些 alpha 的 pairwise correlation 是否仍保持 15.9% 量级,还是结构性抬升?
- 为自动化工作(R&D-Agent 系列 + AlphaForge 等)提供**固定 split 的 golden benchmark**,让 2025 之后的论文能互相直接比较
