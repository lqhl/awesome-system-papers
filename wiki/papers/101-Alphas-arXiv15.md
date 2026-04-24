---
type: paper
name: 101 Formulaic Alphas
full_title: "101 Formulaic Alphas"
authors: [Zura Kakushadze]
venue: arXiv
year: 2015
tags: [finance, quant-trading, alpha-factors, formulaic, worldquant]
source_pdf: "[[1601.00991v3.pdf]]"
source_md: "[[1601.00991v3]]"
---

# 101 Formulaic Alphas (arXiv 2015/2016)

> **一句话总结**:WorldQuant 首次公开披露 **101 条真实量化交易 alpha 的显式数学公式**(多数以「价量」量 close/open/high/low/volume/vwap/returns 为主,少数引入市值、GICS/BICS 等行业分类做 industry-neutralize),平均持仓期 0.6–6.4 天,pairwise 相关 15.9%,80/101 论文发表时仍在生产使用。

## 问题

现代量化交易的两条主线在 2015 年呈现矛盾:一方面因子越来越「淡」(faint、ephemeral),必须规模化挖掘以组合成「mega-alpha」;另一方面这个领域极其封闭,实操 alpha 公式从不外传。外部研究者既不知道实际 alpha 长什么样,也无法判断它们是主要靠 mean-reversion、momentum 还是别的什么,更无法在自己的数据上复现实证。本文要做的就是**解密**。

## 核心方法

不是提出新方法,而是**公开 101 条产品环境里真在跑的 alpha 公式**。

所有 alpha 都写成统一 DSL,算子包括:

- `rank`:横截面 rank 标准化(核心操作,几乎每条都用)
- `Ts_ArgMax / ts_rank / ts_min / ts_max / stddev / decay_linear`:时序算子
- `correlation / covariance`:短窗口 pairwise 统计
- `delta(x, d)` / `delay(x, d)`:一阶差分与滞后
- `IndNeutralize(x, G)`:按行业分组做中性化
- 条件三元 `(a ? b : c)`

示例几条:

- **Alpha#1**:`(rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)` — 波动率-价格耦合的 mean-reversion
- **Alpha#2**:`(-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))` — 量价背离
- **Alpha#101**:delay-1 日内动量,收盘突破开盘且高突破低时次日做多

按 delay 分:

- **delay-0 alpha**:数据和交易发生在同一天(如接近收盘 rebalance)
- **delay-1/2 alpha**:使用的数据比交易日早 1/2 天,是大部分公式的类型

## 关键结果

- **101 条公式完整公开**,附 algebraic 算子定义(附录 A)
- **实证特征**(2010-01-04 ~ 2013-12-31,$N=101$,$T=1006$ 日):
  - 平均 Sharpe 分布 + 日换手分布 + cents-per-share 分布(Table 1)
  - 平均 pairwise correlation = **15.9%**(median 14.3%)——分散度良好
  - $R \sim \sigma^X$,$X \approx 0.76$——收益与波动率强相关,与换手率无显著相关
  - `ln(T_i) × ln(T_j)` 对 pairwise correlation 的解释力极弱:换手率不是 alpha correlation 的好 factor
- **81 alphas 发表时仍在生产**——不是 toy benchmark

## 相关

- 该论文成为后续自动化因子挖掘工作的「benchmark anchor」:AutoAlpha、AlphaEvolve、AlphaForge、[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]]、Qlib 的 Alpha 158/Alpha 360 都以它为对照
- **概念**:formulaic alpha = 用封闭表达式(几个时序/截面算子的组合)表示 alpha,对应符号回归/遗传编程这条路线的可解释性 baseline
- 作者后续书 [[151-Trading-Strategies-SSRN18|151 Trading Strategies]] (2018) 继续同一精神,但覆盖面从「101 股票 alpha 公式」扩展到「150+ 跨 asset class 策略家族」
