---
type: paper
name: R&D-Agent-Quant
full_title: "R&D-Agent-Quant: A Multi-Agent Framework for Data-Centric Factors and Model Joint Optimization"
authors: [Yuante Li, Xu Yang, Xiao Yang, Minrui Xu, Xisen Wang, Weiqing Liu, Jiang Bian]
venue: arXiv
year: 2025
tags: [finance, llm-agent, multi-agent, quant-trading, factor-mining, automl, auto-research, qlib]
source_pdf: "[[arxiv25-li-rd-agent-quant.pdf]]"
source_md: "[[arxiv25-li-rd-agent-quant]]"
---

# R&D-Agent(Q): Data-Centric Multi-Agent Framework for Quant R&D (arXiv 2025)

> **一句话总结**:Microsoft Research Asia + CMU/HKUST/Oxford 把 quant 研究拆成 5 个 LLM agent 单元(Specification/Synthesis/Implementation/Validation/Analysis)+ bandit scheduler 做 factor↔model 联合优化。CSI500 + NASDAQ100 上 o4-mini 版跑到 **IR 2.17 / 1.77**,ARR **~2× 经典 factor 库**,且**总成本 < $10**。

## 问题

Qlib 解决了 quant pipeline 的数据处理和回测,但两大核心「factor mining」和「model innovation」仍完全人工。已有 LLM 金融 agent(FinAgent、TradingAgents)通常:

1. **覆盖片段化**:只做新闻抽取、事件预测等 narrow subtask
2. **弱可解释**:LLM 直接输出 trading signal 容易幻觉
3. **不联合优化**:factor 与 model 独立迭代,跨阶段反馈缺失

R&D-Agent(Q) 的目标是**全栈 data-centric 自动化 + 联合优化**,第一次以端到端形式跑完整 quant R&D loop。

## 核心方法

**5 个单元组成闭环**(Research phase + Development phase):

1. **Specification Unit**:将优化目标、数据 schema、输出约束、执行环境(Qlib)编码为 $\mathcal{S} = (B, \mathcal{D}, \mathcal{F}, \mathcal{M})$,固定接口,杜绝下游越界
2. **Synthesis Unit**:基于历史实验 $\{(h_i, f_i)\}$ 生成新 hypothesis。维护「knowledge forest」 + SOTA 集合;给 action-conditioned 子集做 prompt context
3. **Implementation Unit**:**Co-STEER** 代码生成 agent——集成调度、CoT 规划、LLM self-feedback、growing practical knowledge 四项能力(比 few-shot / CoT / Reflexion / Self-Debugging 都多一项「长期知识累积」)。对简单基础任务优先生成 → 为后续复杂 task 提供 scaffolding
4. **Validation Unit**:交给 Qlib 做真实市场回测
5. **Analysis Unit**:用 IC、ICIR、ARR、MDD、IR、SR 等统一 metric 打分,反馈到 Synthesis;用 **contextual Thompson Sampling** 在 factor vs model 两个方向上做 bandit 调度

**关键设计**:**Data-centric 隔离**——LLM 始终只看 schema-level 信息,绝不看原始市场数据或时间切分,从根上切掉 data leakage 风险。

## 关键结果

**in-sample on CSI 300**(o3-mini backend):

- Bandit scheduler > LLM-based > random(IC 0.053 vs 0.048 vs 0.045)
- R&D-Factor 用 **仅 22% factor 数** 达到 Alpha 158/360 级别 IC,在 2019-2020 baseline 退化期保持稳定
- Co-STEER pass@k 在少数迭代内收敛,o3-mini 恢复率 > GPT-4o

**out-of-sample**(Train 2008-2021 / Val 2022-23 / Test 2024-06.2025,LLM cutoff ≤ 测试期):

| 模型 | CSI500 IR | CSI500 MDD | NASDAQ100 IR | NASDAQ100 MDD |
|---|---|---|---|---|
| LightGBM | -0.32 | -0.21 | -0.26 | -0.13 |
| Alpha 158 | 0.25 | -0.18 | 0.03 | -0.11 |
| AutoAlpha | 0.57 | -0.10 | 0.10 | -0.12 |
| R&D-Factor (o4-mini) | 1.00 | -0.12 | 1.12 | -0.07 |
| R&D-Model (o4-mini) | 1.40 | -0.07 | 1.27 | -0.07 |
| **R&D-Agent(Q) (o4-mini)** | **2.17** | **-0.07** | **1.77** | **-0.06** |

- **联合优化明显好于只优化 factor 或只优化 model**
- 总 API 成本 **< $10 / 次完整 pipeline**(30 loops)
- 6 种 API backend 横比:o1 > GPT-4.1 > 其它 > GPT-4o-mini

## 相关

- **工具链**:[[entities/Qlib|Qlib]] 做回测基础设施、OpenAI o3-mini / o4-mini / GPT-4.1 做 LLM backend
- **对照 formulaic alpha 路线**:[[101-Alphas-arXiv15|101 Formulaic Alphas]]、AlphaEvolve (KDD'21)、AutoAlpha、AlphaForge
- **对照 foundation-model 路线**:[[TimesFM-Fin-arXiv24|TimesFM-Fin]]——R&D-Agent(Q) 走「agent 合成小模型」而非「fine-tune 大模型」,在同一个 quant 目标上代表两条竞争路径
- **框架亲缘**:AutoGen / AutoGPT / MetaGPT 的 multi-agent 调度范式,但 R&D-Agent(Q) 增加了**硬性数据层隔离** + **bandit scheduler**
- **代码**:<https://github.com/microsoft/RD-Agent>
