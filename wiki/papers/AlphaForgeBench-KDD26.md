---
type: paper
name: AlphaForgeBench
full_title: "AlphaForgeBench: Benchmarking End-to-End Trading Strategy Design with Large Language Models"
authors: [Wentao Zhang, Mingxuan Zhao, Jincheng Gao, Jieshun You, Huaiyu Jia, Yilei Zhao, Bo An, Shuo Sun]
venue: KDD
year: 2026
tags: [finance, research-benchmark, financial-benchmark, alpha-factors, strategy-generation, deterministic-execution, code-generation]
source_pdf: "[[kdd26-zhang-alphaforgebench.pdf]]"
source_md: "[[kdd26-zhang-alphaforgebench]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-20
---

# AlphaForgeBench 端到端策略设计基准（KDD 2026）

> **原题**：AlphaForgeBench: Benchmarking End-to-End Trading Strategy Design with Large Language Models

> **一句话总结**：AlphaForgeBench 不让 [[LLM]] 逐时输出交易动作，而让其生成可执行因子和策略代码；在 903 个问题、六种模型、七类资产和 35,190 次实现中，温度 0 与 0.7 的 Sharpe 比率最大差异低于 0.008，显著提高了评价可复现性。

## 问题与动机

直接交易基准把模型的随机动作、状态缺失和策略能力混在一起。即使温度为 0，同一模型也会生成不同交易路径，并在相邻时间频繁反向操作。AlphaForgeBench 把模型定位为量化研究者：先形成显式规则，再由确定性引擎执行。

## 关键观察 / 隐含假设

- **观察 1**：直接动作智能体在相同输入和确定性解码下仍有显著运行间差异；代码生成把随机性限制在一次生成，后续执行可重放（附录 C、§5）。
  - **依赖假设**：研究能力主要体现为一次性规则合成，而不是在线适应。
- **观察 2**：从规则翻译到开放策略设计，模型排序发生反转；Level 1 到 Level 2 的模型平均 Sharpe 比率下降 16%，Level 3 的模型间差距扩大到 Level 1 的 14 倍（§4.3.2、§4.3.6）。
  - **可能失效场景**：合成难度分类可能偏向作者选择的单资产规则语言。
- **假设 1**：确定性执行使结果差异更接近金融推理能力。
  - **证据强度**：中；仍可能测到代码模板熟悉度、数据集污染和回测器假设适配。

## 核心方法

Stage 1 从券商报告、量化平台、论文、开源库和传统出版物抽取 3,176 个因子策略条目，本次只使用其中 633 个单资产问题。Stage 2 再生成 270 个结构化问题，以“规则翻译、逻辑补全、目标驱动设计”三个层级和易、中、难三个等级形成 $3\times3$ 分类。

每种模型生成因子与长仓策略代码，标准回测器在七类美股和加密资产上执行。评价同时报告收益、Sharpe 比率、最大回撤、波动率、Calmar 比率及五次独立运行的稳定性。

## 设计取舍

- **研究与执行分离换取稳定性**：避免逐时动作翻转，但不评价在线更新、实时状态和执行故障。
- **单资产长仓换取能力隔离**：减少组合构建干扰，却排除了跨资产依赖、做空和风险预算。
- **标准成本换取可比性**：固定交易成本 $10^{-3}$，不建模滑点和流动性，不能直接推断可部署收益。

## 实验与结果

- 数据包含 633 个真实来源问题和 270 个结构化问题；六种前沿模型、七类资产、每设置五次运行，共 35,190 个实现（§6）。
- 温度从 0 调到 0.7 后，各模型、指标和难度层级几乎不变，Sharpe 比率最大差异低于 0.008（§4.3.6）。
- Level 1 到 Level 2 的模型平均 Sharpe 比率下降 16%；Level 3 的模型间差距是 Level 1 的 14 倍（§4.3.2）。
- Claude Sonnet 4.5 获得最佳 Calmar 比率 1.650，并表现出最窄运行间区间；Gemini 3 Pro 在开放设计任务更强但风险和方差更高（§4.3.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 代码生成评价比直接动作更稳定 | §4 与附录 C 的运行间比较 | 六种模型、固定回测器 | 强 |
| 难度层级区分不同研究能力 | §4.3.2、图 3 | 270 个模型增广问题 | 中 |
| 基准结果能代表真实策略设计 | 633 个真实来源问题与跨资产结果 | 仅单资产长仓、固定成本 | 中 |

## 批判性分析

稳定性是明确贡献，但“结果可重放”只说明执行确定，不说明策略在样本外有效。生成代码仍可能适应固定回测器或利用已见过的公开策略；论文没有封存时间留出或前瞻测试。

Stage 1 的 3,176 条中仅使用 633 条单资产问题，作者将其称为刻意隔离能力，但这仍是范围限制。Stage 2 由模型生成并按预定义分类，可能放大特定模型熟悉的表述和规则结构。

## 局限与后续工作

- **局限 1**：单资产、长仓、固定成本，无滑点和流动性。
- **局限 2**：不覆盖组合管理、实盘晋级、故障恢复和策略退役。
- **后续工作 1**：把已保留的 2,172 个组合问题与 371 个多资产问题纳入统一真值执行。
- **后续工作 2**：加入封存时间窗口和前瞻模拟交易，区分代码稳定性与经济稳定性。

## 相关

- **相关主题**：[[Finance]]、[[Auto-Research]]
- **同类工作**：[[Market-Bench-arXiv25]]、[[BacktestBench-KDD26]]、[[AgonAlpha-arXiv26]]
