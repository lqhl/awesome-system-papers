---
type: paper
name: 151 Trading Strategies
full_title: "151 Trading Strategies"
authors: [Zura Kakushadze, Juan Andrés Serur]
venue: SSRN
year: 2018
tags: [finance, quant-trading, trading-strategies, asset-classes, options, fixed-income, reference]
source_pdf: "[[techreport18-kakushadze-151-strategies.pdf]]"
source_md: "[[techreport18-kakushadze-151-strategies]]"
---

# 151 Trading Strategies (SSRN 2018)

> **一句话总结**:Kakushadze (作者同 [[101-Alphas-arXiv15|101 Formulaic Alphas]]) 与 Serur 合著的**通用量化策略参考书**:**550+ 数学公式 + 2000 参考文献 + 900 术语词表**覆盖 150+ 交易策略,从期权组合、固定收益、期货、ETF、外汇、商品、加密货币、到再保险、波动率、real estate、distressed asset、税收套利等「其它资产类」;还包含 ML 策略(神经网络、Bayes、k-NN)和开源 backtest 样例代码。

## 问题

现代量化行业高度碎片化,一个想入行的从业者要面对 10+ 资产类、上千种策略变体、数十年积累的文献。**没有一本「百科」式教程把这些公式、backtest 方法、历史结果压缩在统一符号和可重现的范式下**。本书要补的就是这个空白:**pedagogical 而非 cutting-edge research**。

## 核心方法

本书不是研究论文而是结构化手册:

- **每个策略给完整公式 + backtest 图 + 参考文献**,所有资产类用统一符号
- 提供 R 源码示例用于 out-of-sample backtest,含注释讲解
- 策略分 13 大类,每类数十种变体:
  1. **Options**(covered call/put、bull/bear spread、ladder、straddle/strangle、butterfly、condor、calendar、collar 等)
  2. **Stocks**(value、momentum、statistical arbitrage、pairs trading、event-driven)
  3. **Fixed Income**(yield curve trades、convexity、relative value)
  4. **Futures / Commodities**(term structure、carry、momentum)
  5. **Currency FX**(carry trade、momentum、value)
  6. **Cryptocurrencies**
  7. **ETFs / Indexes**
  8. **Convertibles**
  9. **Structured Assets**
  10. **Volatility as an asset class**
  11. **Real Estate**
  12. **Distressed assets**
  13. **Misc**(weather、energy、inflation、global macro、infrastructure、tax arbitrage)
- **部分策略集成 ML**:ANN、Naive Bayes、k-NN 等作为 signal generator

## 关键结果

本书不推出新 alpha,而是**建立统一参考框架**:

- **150+ 策略的完整公式**,每条都在同一套符号体系里定义
- **900+ 词的术语词表**——对 quant 新人的「金融英文-数学符号」双向 lookup 之必备
- **开源 R backtest 代码**——对学术者和入行者第一次提供同等 granularity 的复现路径
- 在学术界作为**量化策略 taxonomic reference** 被大量引用

## 相关

- **同作者前作**:[[101-Alphas-arXiv15|101 Formulaic Alphas]]（2015）——那篇专注股票 alpha 公式,本书把视野扩到跨 asset class
- **自动化路线的基线对象**:[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]]、AlphaForge 等自动化 factor mining 工作常以 Kakushadze 的公式集作为 baseline 或灵感
- 角色**偏 textbook 而非 novel research**——wiki 页主要作为金融 topic 的**reference anchor**
