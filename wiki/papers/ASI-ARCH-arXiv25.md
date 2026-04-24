---
type: paper
name: ASI-ARCH
full_title: "AlphaGo Moment for Model Architecture Discovery"
authors: [Yixiu Liu, Yang Nan, Weixian Xu, Xiangkun Hu, Lyumanshan Ye, et al.]
venue: arXiv
year: 2025
tags: [auto-research, neural-architecture-search, multi-agent, linear-attention, llm-agent, scaling-law]
source_pdf: "[[2507.18074v1.pdf]]"
source_md: "[[2507.18074v1]]"
---

# AlphaGo Moment for Model Architecture Discovery (arXiv 2025)

> **一句话总结**：ASI-ARCH 让多 agent LLM 系统在 20,000 GPU hours 内自主跑完 1,773 次架构实验，从 DeltaNet 出发进化出 **106 个 SOTA linear attention 架构**，并首次给"科学发现本身"建立了一条计算与 SOTA 产出近似线性的 scaling law。

## 问题

AI 能力指数增长，但 AI 研究进度仍线性受限于人类认知带宽。传统 NAS（Neural Architecture Search）只在人类预定义的 building block 上做组合搜索，不能创造新机制；而 AI scientist 类系统（如 [[AI-Scientist-arXiv24]]、[[AlphaEvolve-arXiv25]]）多聚焦在 ML 代码重构或数学命题证明，还没有人把"端到端的神经网络架构创新"——从假设生成、代码实现、训练验证到洞察归纳——交给一个完全自主的系统跑通。作者选 linear attention 这一活跃且知识密集的子领域作 testbed，直面 automated innovation 而非 automated optimization。

## 核心方法

ASI-ARCH 是一个 closed-loop 多 agent 框架，围绕 **Researcher / Engineer / Analyst** 三个角色 + Cognition 知识库协同演化。

**1. Fitness Function（反 reward-hacking）**：
- $\mathrm{Fitness} = \frac{1}{3}[\sigma(\Delta_{\mathrm{loss}}) + \sigma(\Delta_{\mathrm{benchmark}}) + \mathrm{LLM_{judge}}]$。
- Sigmoid 变换把 loss/benchmark 改进压到 [0,1]，防止某个指标被 exploit；LLM-as-judge 评架构创新、复杂度、收敛性等定性维度。

**2. Researcher（提新架构）**：
- Seed selection：候选池保留 top-50；每步从 top-10 随机抽 parent，从 11-50 抽 4 个 reference 提供多样示例。
- Program Implementation：motivation 和 code 用**同一个 agent**顺序生成，避免跨 agent 的 implementation drift。
- Novelty & Sanity Check：embedding 检索 top-5 相似 motivation 做 novelty 判定；静态检查不超过 $O(n^2)$ 复杂度、mask 正确性；不通过则 rewrite。

**3. Engineer（训练验证 + 自愈）**：
- 在真实代码环境里跑训练，失败时把 error log 回灌 agent 让其改代码（而不像 [[AlphaEvolve-arXiv25]] 那样 AST 检查后直接丢弃），loss 异常低视作 info leakage 立即终止。

**4. Analyst（挖 insight）**：
- Cognition base：从 ~100 篇 linear attention 经典论文抽 1-3 条 cognition（scenario / algorithm / context），embedding 检索按当前实验 shortcoming 返回相关历史智慧。
- Contextual Analysis：把当前架构 + 其 parent 和 sibling 节点一起喂 Analyzer，模拟 ablation study 推断每个组件的贡献。

**5. Exploration-then-Verification 两阶段**：
- Exploration：20M 参数 + 1B token，跑了 1,773 次实验、10k GPU hours；cold start 前 200 次不更新候选池促创新；之后每 50 次批量更新。
- Verification：先 340M + 1B token 过滤到 ~400 个架构，再选 106 个 SOTA 放到 15B token 做最终评估；5 个代表模型在 wiki / LAMBADA / PIQA / ARC / BoolQ 等 benchmark 上超过 DeltaNet / Gated DeltaNet / Mamba2 baseline。

## 关键结果

- **1,773 次自主实验 / 20,000 GPU hours → 106 个 SOTA linear attention 架构**，全部开源到 Model Gallery。
- **Scaling law for scientific discovery**：SOTA 架构累计数量随 GPU hours 近似线性增长——架构突破可以用算力 scale，而非只靠研究员。
- 候选池 raw loss / benchmark 指标持续改善，但 fitness score 因 sigmoid 饱和不会一路上涨，说明系统在持续进步而没 reward hacking。
- 设计 provenance 分析（Table 3）：top 106 gallery 里 **44.8% 组件来自 analysis**（历史实验归纳），48.6% 来自 cognition，6.6% 原创——越是 SOTA 的架构越依赖 analysis 而非死记人类文献。
- 组件偏好分析显示系统自发收敛到 gating + convolution 等成熟 primitive，而非追求花哨的 physics-inspired 机制，与人类科学家的设计美学一致。
- 代表架构如 PathGateFusionNet（hierarchical gating）、ContentSharpRouter（learnable-temperature routing）、FusionGatedFIRNet（parallel sigmoid fusion）在 340M/15B 配置下 average benchmark 超过 Gated DeltaNet 1-2 个点。

## 相关

- **相关概念**：[[Linear-Attention]]、[[Neural-Architecture-Search]]、[[LLM-as-Judge]]、[[Multi-Agent-System]]、[[Reward-Hacking]]
- **相关 baseline 架构**：DeltaNet、Gated DeltaNet、Mamba2
- **同类系统**：[[AlphaEvolve-arXiv25]]、[[AI-Scientist-arXiv24]]、[[AI-Scientist-v2-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[FunSearch-Nature24]]
- **同主题**：[[Auto-Research]]
