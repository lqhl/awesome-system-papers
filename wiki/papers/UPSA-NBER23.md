---
type: paper
name: UPSA
full_title: "Universal Portfolio Shrinkage"
authors: [Bryan T. Kelly, Semyon Malamud, Mohammad Pourmohammadi, Fabio Trojani]
venue: NBER
year: 2023
tags: [portfolio-optimization, nonlinear-shrinkage, asset-pricing, principal-components, cross-validation, stochastic-discount-factor]
source_pdf: "[[techreport23-kelly-universal-portfolio-shrinkage.pdf]]"
source_md: "[[techreport23-kelly-universal-portfolio-shrinkage]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-04
---

# 通用投资组合收缩（NBER 2023）

> **原题**：Universal Portfolio Shrinkage

> **一句话总结**：当资产数接近或超过观测数时，单一 ridge penalty 会把不同主成分一刀切且随窗口剧烈跳变；UPSA 将多个 ridge portfolio 组成非负闭式 ensemble，并用 LOO 直接优化样本外效用，在 153 个 JKP 异常因子上把年化 Sharpe 从最佳 ridge 的 1.59 提至 1.92、把样本外定价 $R^2$ 从 39% 提至 67%。

## 问题与动机

经典 Markowitz portfolio 需要估计均值和二阶矩。当资产数 $N$ 与时间样本数 $T$ 同阶、甚至 $N>T$ 时，样本内最优权重会被估计噪声污染：低方差主成分（principal component, PC）容易获得极端权重，样本内 Sharpe 虚高，样本外表现则坍塌。论文将这一困难写成复杂度比率 $c=N/T$；图 1 显示 $c$ 增大时，未正则化组合的样本内与样本外 Sharpe 出现迅速扩大的楔子。

现有收缩方法各自限制了设计空间。Ridge 对全部 eigenvalue 加同一 penalty；PCA 或 lasso 直接丢弃部分 PC；Ledoit–Wolf nonlinear shrinkage 优化 covariance estimation error，而不是投资者最终关心的 portfolio utility。作者的核心 claim 是：高维投资组合需要同时做到**非线性 spectral shrinkage**与**economic-objective alignment**，不能仅凭统计估计误差或硬截断决定权重。

论文提出 Universal Portfolio Shrinkage Approximator（UPSA）。它把不同 penalty 的 ridge portfolio 当作基础资产，以非负权重组合，形成对广泛 matrix-monotone nonlinear shrinkage function 的通用近似；组合权重由 leave-one-out（LOO）cross-validation 产生的样本外回报直接求解。最终训练仍是一个低维 Markowitz problem，因此保留闭式结构并可扩展到 $N>T$。

## 关键观察 / 隐含假设

- **观察 1：不同 ridge penalty 不是同一策略的轻微扰动，而是可形成有效 ensemble 的异质回报源。**
  - **证据**：153 个 JKP factors、120 个月 rolling window 下，不同 ridge portfolio 的样本外相关系数最低约为 -2%（图 2）；最佳单一 penalty 还会在相邻窗口间跨多个数量级跳变（图 7）。
  - **依赖假设**：这类异质性反映可泛化的 eigen-spectrum 与 expected-return uncertainty，而非 LOO 产生的有限样本噪声。
  - **可能失效场景**：若资产 covariance 近似球形、各 PC 的 risk-return tradeoff 同质，ensemble 可能退化为单一 ridge，额外自由度不再有收益。

- **观察 2：投资组合目标所需的 shrinkage 与最小化 covariance estimation error 的统计目标并不一致。**
  - **证据**：模拟中，直接优化 quadratic utility 的 economic ridge 平均 Sharpe 为 0.28，statistical ridge 为 0.22，并在 87% 的 10,000 次模拟中胜出（图 14）；允许非线性后，UPSA 再把平均 Sharpe 提至 0.33，并在 96% 模拟中胜过 economic ridge（图 15）。
  - **依赖假设**：quadratic utility 与 Sharpe 足以代表投资者目标，且训练期 LOO utility 能预测未来目标。
  - **可能失效场景**：强交易成本、杠杆约束、tail risk 或多期 wealth dynamics 主导时，未显式进入目标的代价可能改变最优 shrinkage。

- **观察 3：最小方差 PC 不应被机械删除；更重要的是按经济信号对 spectrum 非线性重加权。**
  - **证据**：加入全部 120 个 PC 时，ridge Sharpe 从 32-PC 峰值 2.16 降至 1.59（降约 26%），UPSA 从 2.19 降至 1.92（降约 12%）；其与 infeasible sparse oracle 的相关性分别为 0.72 与 0.81（图 10）。图 11 显示 UPSA 对中间 eigenvalue 施加更强 regularization，同时没有硬删除最小 PC。
  - **依赖假设**：小 eigenvalue 方向中确有稳定 risk premium，而不全是 estimation noise；样本 eigenvector 对未来仍有足够稳定性。
  - **可能失效场景**：covariance eigenvector 快速旋转、低方差方向被 market microstructure noise 支配，或 short-sale constraint 使近套利 PC 无法交易。

- **假设 1：月度 factor returns 可近似视为 exchangeable / IID，使 LOO utility 成为无偏样本外代理。**
  - **证据强度**：中。Lemma 4 在 exchangeability 下给出无偏性；rolling-window、business-cycle 与 Markov-switching 模拟支持一定的时变适应能力，但实证收益显然存在 regime dependence，严格 IID 并不成立。

- **假设 2：153 个 anomaly portfolios 足以代表高维实际投资组合问题。**
  - **证据强度**：中。数据覆盖 1971–2022、13 个 factor themes，并对规模组和 60/240/360 月窗口做 robustness；但 factor portfolio 比个股更平滑、交易维度更低，也未计入真实执行成本。

## 核心方法

**从 PC 空间重写组合。** 作者将样本二阶矩分解为 eigenvectors 与 eigenvalues，把 Markowitz return 写成 PC returns 的加权和。一般 spectral shrinkage 用正函数 $f(\bar\lambda_i)$ 修改每个 PC 的 mean-variance 权重；单一 ridge 是 $f_z(\lambda)=1/(\lambda+z)$，只能让全部 PC 共用同一个 $z$。

**Ridge ensemble 的通用近似。** UPSA 选择一组 penalty grid $Z=\{z_1,\ldots,z_L\}$，用非负权重组合基础函数 $1/(\lambda+z_i)$。Lemma 1 证明，对满足正性与 matrix-monotone decreasing 等条件的 shrinkage function，足够宽且密的 ridge grid 可在 compact interval 上一致逼近。非负约束保持 shrunken second-moment matrix 为 positive definite，并保留 PC 风险排序。

**把函数学习化成 portfolio problem。** 对每个 $z_i$，作者在每次 LOO split 上训练一个 ridge portfolio，并记录它在被留出月份的 realized return。由这些 LOO returns 估计基础 ridge portfolios 的样本外均值与二阶矩；求 ensemble weight 等价于在这 $L$ 个基础 portfolio 上再解一次 Markowitz optimization（Lemma 2）。因此 UPSA 没有训练一般 neural network，却获得类似 shallow network 的 nonlinear approximation 能力与闭式、低成本实现。

**Bayesian 解释。** 单一 ridge 对应投资者对 expected-return uncertainty 采取一个固定 prior；UPSA 则对不同 uncertainty scale 的 priors 做 mixture，并由数据决定各自权重。论文进一步证明，在 mean 与 covariance 共同不确定的 Normal–Inverse-Wishart mixture 下，posterior Markowitz portfolio 也恰好具有 ridge ensemble 形式（§5.1、Appendix B）。这解释了 UPSA 为何比每期 point-select 一个 penalty 更平滑。

**Asset-pricing 评测。** 作者把估计出的 efficient portfolio 视为 tradable stochastic discount factor（SDF），除 Sharpe 外，还比较其对 153 个 JKP factor realized Sharpe 的样本外定价误差。这个双重评测把「组合赚得更好」和「能否解释 cross-section expected returns」分开审计。

## 设计取舍

- **取舍 1：** 用 ridge basis + 非负 ensemble 换取闭式、positive-definite 与可扩展性，代价是通用性只对满足给定 regularity / monotonicity 的 shrinkage class 成立；Lemma 5 的一般连续函数近似不自动满足经济 shape constraint。
- **取舍 2：** 直接用 LOO quadratic utility 对齐经济目标，避免 Ledoit–Wolf 的 proxy-objective mismatch；代价是 LOO 要反复估计 portfolio，并把 exchangeability 与有限样本稳定性变成核心前提。
- **取舍 3：** 保留所有 PC 并连续 reweight，避免 PCA/lasso 的离散选择不稳定；代价是噪声 PC 仍可能保留非零 exposure，不能提供真正 sparse、易解释的 holdings。
- **取舍 4：** 论文以 gross Sharpe 和 SDF pricing 为主目标，没有把 turnover penalty 直接放进训练；UPSA 虽经验上 turnover 更低，但这不是 optimization guarantee。
- **边界条件：** 结论在美股 anomaly factor、月频、rolling 估计、quadratic utility 和可做 long–short 的环境最强；对个股、日频、约束组合与国际市场的外推仍待验证。

## 实验与结果

- **主结果**：153 个 JKP factor、1971–2022、120 个月 rolling training、1981–2022 样本外期中，UPSA 年化 Sharpe **1.92**，高于 ridge **1.59**、PCA **1.45**、Ledoit–Wolf **1.31**、FF5 **1.13** 与 CAPM **0.54**（图 3）。
- **显著性**：UPSA 相对最接近的 ridge 年化 alpha 为 **4.46%**，HAC $t=3.72$；pre-2000 与 post-2000 都保持相对领先（图 5）。
- **定价能力**：对同一组 153 个 factors 的直接样本外 SDF pricing，UPSA 的 cross-sectional $R^2$ 为 **67%**，ridge 为 **39%**、PCA 为 **22%**，其余为负（图 6）；按 beta 表示的替代评测中，UPSA / ridge / PCA / LW 分别为 **73% / 63% / 55% / 52%**（图 28）。
- **稳定性与换手**：ridge 在约四分之三月份的 turnover 更低，但少数跳变使其平均 turnover 比 UPSA 高约 **30%**、标准差近 **5 倍**（图 8）；grid 超过 3–4 个点后，UPSA Sharpe 与月换手约 **12.5%** 均趋于稳定（图 17–18）。
- **Regime robustness**：NBER recession 中，UPSA Sharpe 从 expansion 的 2.01 降至 **1.40**（降 30%），ridge 从 1.77 降至 **0.83**（降 53%）；UPSA recession return 为 18.8%，接近 expansion 的 19.3%（图 29）。
- **显式 sparsity 不划算**：加 lasso 后 UPSA Sharpe 仅从 1.92 升至 **1.94**，月换手却从 **12.4%** 升至 **19.5%**；ridge 则 Sharpe 由 1.59 降至 1.54、换手由 16.3% 升至 24.7%（图 19–21）。
- **Simulation mechanism**：固定 covariance、让 expected returns 做 Markov switching 时，UPSA 在 **88%** 的 10,000 条路径中 Sharpe 更高（均值 0.28 vs 0.24），在 **74%** 路径中换手更低（4.4% vs 6.1%，图 16）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| UPSA 在主样本显著优于单一 ridge 与其他 shrinkage baseline | 图 3、图 5：Sharpe 1.92 vs 1.59；相对 ridge alpha 4.46%，$t=3.72$ | 153 个 JKP long–short factors；120 月 rolling window；1981–2022 OOS；未扣交易成本 | 强 |
| UPSA 的收益不仅是 higher Sharpe，也对应更小的样本外 asset-pricing error | 图 6：直接 SDF pricing $R^2$ 67% vs ridge 39%；图 28：beta-based 73% vs 63% | test assets 与训练 assets 同为 153 个 JKP factors，存在 universe reuse | 中强 |
| 非线性 economic shrinkage 的优势来自对 spectrum 的异质处理，而非只增加参数 | 图 14–15：economic ridge 胜 statistical ridge 87%；UPSA 胜 economic ridge 96% | 人工构造 3 段 eigen-spectrum；$N=150,T=600$；10,000 simulations | 中强 |
| 对 penalty uncertainty 做 ensemble 能提高 regime 稳定性并降低极端换手 | 图 7–9、图 16、图 29 | 月频 factor data 与两状态模拟；未在优化中显式加入交易成本或 turnover penalty | 中 |
| 硬 sparsity 对 UPSA 的增益很小且换手代价明显 | 图 19–21：Sharpe +0.02，turnover 12.4%→19.5% | sequential lasso、同一 penalty grid 与 LOO；结果不覆盖其他 sparsity prior | 中强 |

## 批判性分析

### 论证链条

论文的主链条基本闭合：高维 moment estimation 使 plug-in Markowitz 失效 → 单一或 proxy-objective shrinkage 限制过强 → ridge basis 可近似 nonlinear spectral rule → LOO utility 可估 ensemble → empirical Sharpe、pricing error、turnover 与 simulation mechanism 同方向。尤其难得的是，论文没有只给 performance table，而是用图 10–13 将 spectral reweighting 连接到 low-signal PC attenuation、fundamental theme tilts 与 Sharpe decomposition。

仍有两个跳步。第一，universal approximation 是对函数类的表示能力，不等于有限 $T$ 下能可靠学到该函数；实证 grid sensitivity 缓解但没有给 generalization bound。第二，Bayesian mixture 为 UPSA 提供事后解释，却不证明 LOO 求出的权重就是某个稳定、可审计 prior 的 posterior；“diversifying beliefs”更接近解释框架而非独立识别结果。

### 假设压力测试

**时间依赖**：Lemma 4 依赖 exchangeability，金融 returns 的 volatility clustering、structural break 与 recession regime 明显违反这一条件。Rolling windows 与 Markov-switching 实验说明方法在一定程度上可适应，但 LOO 随机留月可能低估相邻期 dependence；blocked / purged time-series CV 是直接的压力测试。

**目标错配**：论文正确批评 covariance estimator 不应优化错误 proxy，但自身也只优化 quadratic utility。若实施者关心 expected shortfall、drawdown、capacity、leverage、borrow availability 或 transaction cost，economic alignment 仍不完整。较低 turnover 是 emergent outcome，而非对成本最优。

**训练与测试 universe 重叠**：SDF pricing test assets 就是构建 portfolio 的 153 个 JKP factors。虽然权重与 pricing 均按时间样本外，cross-section 并非未见资产，因此 67% $R^2$ 不能直接解读为对新 anomaly universe 的外部泛化。用独立 portfolios、国际市场或个股做 test assets 会更强。

**信号的经济来源**：UPSA 向 value、quality、low-risk 等 persistent fundamentals 倾斜，而避开 seasonality、skewness、momentum；Shapley decomposition 将其与 Sharpe gap 联系起来。但主题权重是结果分解，并未证明 nonlinear shrinkage 因这些经济机制而成功，也可能只是特定 1971–2022 factor zoo 的稳定性选择。

### 实验可信度

强项是时间跨度长、baseline 覆盖 ridge / nonlinear covariance shrinkage / PCA / FF5 / CAPM，并对窗口长度、size groups、grid、lasso、business cycle 与两类 simulation 做系统 robustness。主结果给出 Sharpe、alpha、pricing $R^2$、turnover 与 regime breakdown，证据面比只报单个 return metric 完整。

主要缺口是没有 transaction cost、market impact、leverage 与 drawdown 报告；153 个 factor portfolios 也弱化了个股层面的容量与 microstructure 问题。论文虽称方法 computationally cheap / scalable，却没有 runtime、memory、$N$ scaling curve 或实现复杂度数据。因此“高维可扩展”主要由算法形式支持，未被 systems-style benchmark 直接验证。

### 系统性缺陷

生产部署需要维护滚动 LOO、ridge grid、portfolio constraints、数据缺失与 covariance conditioning；论文没有讨论这些 operational failure modes。正权重只约束 ridge ensemble basis 的组合，不代表最终资产 holdings 为 long-only，也不自动限制 gross exposure。极端期 factor covariance 突变时，rolling window 内的旧 regime 仍可能拖慢适应；UPSA 的平滑性既是稳定来源，也可能延迟响应真正的 structural break。

## 局限与后续工作

- **局限 1**：主证据来自同一套 153 个 JKP factors，尚未验证对独立 test assets、个股、其他国家和更高频数据的 cross-universe 泛化。
- **局限 2**：LOO 依赖 exchangeability，未与 blocked、purged 或 regime-aware time-series CV 正面对照。
- **局限 3**：没有把 transaction cost、turnover、leverage、short-sale 或 tail-risk constraint 纳入训练目标；gross Sharpe 不能直接转成 deployable performance。
- **局限 4**：所谓 closed-form / cheap / scalable 没有 runtime 与 memory benchmark，无法量化相对 Ledoit–Wolf、PCA 或 constrained optimizer 的工程成本。
- **后续工作 1**：在相同 rolling windows 下对比 LOO、blocked CV 与 purged CV，报告 penalty stability、OOS Sharpe 和 turnover 的差异，并按 recession / expansion 分层。
- **后续工作 2**：把 expected transaction cost 与 gross-exposure penalty 直接加入 ridge-portfolio ensemble objective，检验净 Sharpe 是否仍显著高于 cost-aware ridge。
- **后续工作 3**：在 JKP 上训练 shrinkage function，使用未参与训练的 options、international equity、industry 或 individual-stock portfolios 做定价测试，分离 time-OOS 与 asset-OOS generalization。
- **后续工作 4**：公开 $N/T$、grid size 与 constraint 数量的 runtime / peak-memory scaling curve，验证 $N>T$ 下的实际求解稳定性。

## 相关

- **相关概念**：[[Portfolio-Shrinkage]]、[[Markowitz-Portfolio]]、[[Principal-Component-Analysis]]、[[Cross-Validation]]、[[Stochastic-Discount-Factor]]、[[Asset-Pricing-Anomaly]]
- **同一 factor universe**：[[NewsShock-NBER26]] — 同样使用 JKP anomaly factors，但研究文本 information shock，而非 portfolio estimator regularization
- **后续扩展**：[Noise-Proofing Universal Portfolio Shrinkage](https://arxiv.org/abs/2511.10478) — 针对 UPSA 的 estimation noise 与 covariate shift 提出 time-averaging / Average Oracle 修正
- **代码**：[Universal Portfolio Shrinkage GitHub](https://github.com/pourmohammadimohammad/Universal_Portfolio_Shrinkage)
