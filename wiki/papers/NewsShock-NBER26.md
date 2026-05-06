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

> **一句话总结**：将新闻 LLM embedding 对股票特征做正交分解，提取不可预测的"新闻冲击"(news shock)残差——该信号的多空组合年化 Sharpe 达 3.1，是 JKP 异常因子库中最大异常的两倍，且可预测未来 18 个月的收益；市场对负面/量化密集的新闻反应不足，对高关注度/模糊的新闻反应过度。

## 问题

已有研究（Chen et al., 2026）用 LLM embedding 分析新闻对股价的影响，发现市场价格对新闻信息的反应存在几天延迟。但这些研究忽略了一个关键问题：**新闻内容本身可由已知的股票特征高度预测**——约 10% 的 embedding 变异可由 JKP 特征解释。如果不剥离这部分"旧闻"，就混淆了已经被市场定价的已知信息和真正的新信息到达对价格的影响。

本文要回答：如果只保留新闻中不可预测的部分（news shock），市场对它的定价效率如何？

## 核心方法

**News Shock 构建**。用 E5-Mistral-7B 对每只股票每月的 Reuters 新闻生成 4096 维 embedding $E_t$，然后对 132 个 JKP 股票特征 $S_t$ 做逐月截面回归：

$$E_t = S_t \beta_t + \varepsilon_t$$

拟合值 $S_t \beta_t$ 是"可预测新闻"，残差 $\varepsilon_t$ 就是 **news shock**——真正不可预测的新信息。回归的 pooled $R^2$ 约 7.5%，主要由基本面特征（value、quality、leverage）驱动，而非动量/反转等价格趋势特征。

**投资组合构建**。用 Maximum Sharpe Ratio Regression (MSRR) 将高维 news shock 信号聚合为单一多空组合，滚动窗口训练 + leave-one-out 选 ridge penalty。

**可解释性分析**。用 LLM Sparse Autoencoder (SAE) 将 4096 维 dense embedding 解压为 131,000 维稀疏表示，识别出 148 个与新闻冲击异常相关的可解释主题，聚类为 12 个经济主题（如 Earnings、Distress、M&A、Guidance 等），分析各主题的 over/underreaction 模式。

**Chronologically Consistent LLM**。为排除 LLM 的 lookahead bias，用只在历史数据上训练的 CCLLM 重做实验，结论稳健。

## 关键结果

- **News shock 组合年化 Sharpe 3.1**（1996-2022 全样本），raw embedding 组合仅 1.1；控制 JKP 全量特征后 alpha 年化 29%
- **是 JKP 异常因子库中最大异常（Sharpe 1.4）的两倍以上**；在大盘股子集中 news shock Sharpe 1.4 vs JKP 最佳 0.9
- **预测力持续 18 个月**才衰减至不显著，远超 momentum/reversal/PEAD 等已知异常
- **换手率 75%**，但用 6 个月平均 embedding 可将换手降至 45% 而 Sharpe 仍保持 3.0，net-of-cost 仍超所有 JKP 因子
- **62% 的组合权重来自 underreaction**（市场反应不足），38% 来自 overreaction
- 行为驱动因素：负面情感和量化密集的新闻 → underreaction（市场迟钝）；高模糊度和高关注度新闻 → overreaction（市场过度反应后反转）
- 异常不随时间衰减，2000 年后 Momentum/Trading 主题占比下降，Corporate Guidance 主题上升为最主要驱动

## 相关

- **相关概念**：[[Market-Efficiency]]、[[Asset-Pricing-Anomaly]]、[[Underreaction]]、[[Overreaction]]
- **同类研究**：Chen et al. (2026) — LLM embedding + return prediction 的前置工作
- **外部参考**：[NBER WP 35093](http://www.nber.org/papers/w35093)
