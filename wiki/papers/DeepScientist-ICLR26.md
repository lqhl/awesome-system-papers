---
type: paper
name: DeepScientist
full_title: "DeepScientist: Advancing Frontier-Pushing Scientific Findings Progressively"
authors: [Yixuan Weng, Minjun Zhu, Qiujie Xie, Qiyao Sun, Zhen Lin, Sifan Liu, Yue Zhang]
venue: ICLR
year: 2026
tags: [ai-agents, scientific-discovery, bayesian-optimization, long-horizon, multi-agent, domain/auto-research, concern/long-horizon]
source_pdf: "[[iclr26-weng-deepscientist.pdf]]"
source_md: "[[iclr26-weng-deepscientist]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-27
---

# DeepScientist：渐进地产生推进前沿的科学发现（ICLR 2026）

> **原题**：DeepScientist: Advancing Frontier-Pushing Scientific Findings Progressively

> **一句话总结**：DeepScientist 把目标明确的科研发现建模为 Bayesian Optimization，用发现记忆 + UCB 将约 4,879 个想法漏斗筛到 1,108 次实现和 21 个进展发现，在 16×H800、20,000 GPU 小时和约 \$100k 下于三个 AI 任务超过人类 SOTA 183.7%、1.9%、7.9%；但约 60% 抽样失败源于实现错误，全部结果仍由 3 名人类监督者验真（§3–4，图 3–4，附录 C）。

## 问题与动机

[[AI-Scientist-arXiv24]] 一类端到端系统能生成想法、跑实验和写论文，但若目标只是「新颖」，搜索容易退化为已有方法的浅层重组。DeepScientist 将任务收窄为：从一个人工确认、可复现的前沿 SOTA 出发，在单一可量化目标上持续找到更优方法。它追求的不是一次性论文生成，而是让每次成功和失败进入共享记忆，形成下一个研究循环的先验（§1–3）。

作者选择智能体失败 Attribution、LLM Inference Acceleration、AI Text Detection 三个软件型 AI 任务，人工复现起点，保留测试脚本，再让系统在最长一个月内并行探索。核心论断是：当实验反馈相对快速、目标函数清晰时，LLM 智能体可以用海量低成功率试错换取超越当期人类 SOTA 的结果（§4，表 1）。

## 关键观察 / 隐含假设

- **观察 1：前沿想法极度稀疏，验证与过滤比想法生成更稀缺。** 三任务共生成 4,879 个想法，实施 1,108 个，最终仅 21 个形成进展发现；UCB 筛选后的成功率约 1–3%，每任务随机抽 100 个想法的消融实验成功率接近 0（§4.3，图 4）。
  - **依赖假设**：[[LLM|LLM]] 评审器对 utility、质量、探索 value 的 0–100 估值与真实实验价值正相关。
  - **可能失效场景**：surrogate 偏好熟悉/易实现方法时，会系统性过滤掉高风险高价值假设；论文没有报告 calibration 或排序 correlation。
- **观察 2：失败主要不是科学假设错误，而是智能体无法可靠实现。** 专家对 300 个失败 trial 做因果归因，约 60% 因实现错误提前终止；Claude Code 初次实现约 50% 因内部超时未完整结束（§4.3，附录 B–C）。
  - **依赖假设**：人工归因能稳定区分实现失败与科学 regression；论文未报告标注一致性。
  - **可能失效场景**：在更成熟的编程智能体上，瓶颈可能转回假设质量；在湿实验中，仪器与样本失败会产生新的失败 class。
- **观察 3：在单周固定设置中，parallel 算力与进展发现数呈上升趋势。** 4、8、16 GPU 分别得到 1、4、11 个进展发现（§4.3，图 6）。
  - **证据强度**：弱到中。只有一次一周运行、少量资源点、无重复和误差条；不能称为跨任务稳定规模定律。
- **假设 1：单一基准指标的提升可作为科学价值的代理。**
  - **证据强度**：中。三项结果均有执行验证和 SOTA 基线，但 1.9% 吞吐增益与 183.7% attribution 准确率增益的科学意义不可直接等量比较。

## 核心方法

DeepScientist 将候选研究方法空间记为未显式定义的概念空间，把完整实现、实验和分析后的指标视为昂贵黑盒函数。与 [[AlphaEvolve-arXiv25]] 的代码 mutation + 显式 fitness 相似，它依赖可执行评估器；不同之处是候选首先以自然语言科学假设出现，因此用 LLM surrogate 近似真实价值，再用实验完成最终验证（§3.1）。

**Strategize & Hypothesize** 读取由人类知识和历史实验构成的发现记忆。由于完整记忆超过上下文窗口，retrieval 模型选 Top-K（固定 K=15）；LLM 评审器为新假设输出 utility、质量、探索 value 三维 0–100 评分。这个结构直接回应观察 1：失败不丢弃，而是成为后续选题的检索证据（§3.2，附录 C）。

**Implement & Verify** 用 UCB acquisition function 汇总三维估值，平衡利用与探索；最高分想法被提升为 Implement 发现。Claude-4-Opus/Claude Code 在人工验证的基线仓库副本中实现，DeepScientist 再独立重跑主脚本以减少「智能体自称成功」的误报（§3.2，附录 C）。

**Analyze & 报告** 只处理超过基线的结果：多个智能体设计消融实验、扩展数据集评测和分析，再自动汇总成论文。成功记录升级为进展发现并回写记忆，成为下一轮 limitation identification 的起点。AI Text Detection 从 T-Detect 到 TDT、PA-Detect 的连续路径是作者展示的 progressive 探索样例（§4.1，图 1、5）。

系统用 Gemini-2.5-Pro 负责核心推理、Claude-4-Opus 负责代码；两个服务器共 16×H800，每张 GPU 独立运行一个实例并共享记忆。三名人类专家持续验证输出并过滤幻觉，因此论文所称「fully autonomous」应理解为搜索循环自主，而不是无人工审计的 unattended science（§4，附录 C）。

## 设计取舍

- **明确目标函数 vs 开放科学价值**：单指标让实验可筛选、可累积，却把科研问题选择、指标设计和基线真实性留给人类。
- **分层验证 vs 漏掉异端想法**：便宜 surrogate 先过滤可节省 GPU，但评审器 bias 会成为探索的先验上限。
- **并行试错 vs 成本/能耗**：20,000 GPU 小时和约 \$100k 换来 21 个进展发现；对反馈慢的 foundation-模型预训练、药物合成并不经济。
- **共享发现记忆 vs 错误传播**：成功/失败可跨实例复用，若早期实验或归因错误，错误结论也会污染后续 acquisition。
- **自动循环 vs 人工可信度边界**：三名监督者提高结果真实性，但削弱「无需人类」以及成本完全自动化的论断。

## 实验与结果

- 智能体失败 Attribution 的 A2P 在 Who&When handcraft / algorithm-generated 设置分别得 29.31 / 47.46；作者报告相对起点 SOTA 准确率提升 183.7%（§4.1，图 3a–b）。
- LLM Inference Acceleration 的 ACRA 在 MBPP 将 Token Recycling 的 190.25 tokens/s 提至 193.90 tokens/s，即 1.9%；其改进来自稳定后缀 pattern 的 context-aware draft，仍保留 lossless verification（§4.1，图 3c）。
- AI Text Detection 两周内依次产生 T-Detect、TDT、PA-Detect，在 RAID 上相对 Binoculars 提高 7.9% AUROC，并将推理 speed 提高约 2×；所有 zero-shot 方法固定 Falcon-7B（§4.1，图 1、3d）。
- 探索漏斗为：AI Text Detection 2,472 想法/600 实现/7 进展；失败 Attribution 1,077/196/12；Inference Acceleration 1,330/312/2，共 4,879/1,108/21（§4.3，图 4a）。
- 专家抽样分析 300 个失败实现，约 60% 为实现错误，其余多数不提升或发生 regression；筛选后成功率约 1–3%，随机每任务验证 100 个想法时成功率接近 0（§4.3，图 4b）。
- 单周规模扩展实验从 4 GPU 的 1 个进展发现增至 8 GPU 的 4 个、16 GPU 的 11 个；无重复试验或置信区间（§4.3，图 6）。
- 3 名专家对 5 篇生成论文盲审，平均 rating 5.00，接近 ICLR 2025 投稿均值 5.08，但 soundness 仅 2.27/4；两篇得 5.67，另两篇 4.33（§4.2，表 3、附录 A）。
- 总成本约 \$100,000；每个想法约 \$5 API、每次实现约 \$20 API + 1 GPU-hour、进入分析和写作的成功发现再约 \$150（附录 C）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 系统能在三个前沿 AI 任务上超过人类 SOTA | §4.1，图 1、3 | 三个由作者选择且人工复现的软件任务；16×H800；三名专家验真 | 强 |
| 分层筛选对极低命中率的发现搜索至关重要 | §4.3，图 4 | 4879 个想法、1108 次实现、21 个进展；每任务随机取 100 个想法时几乎没有成功 | 中 |
| 共享记忆下的科学发现数量可能随算力近线性扩展 | §4.3，图 6 | 单周、1/2/4/8/16 张 GPU、无重复与误差条；1/2 张 GPU 时无突破 | 弱 |
| 生成论文达到接近 ICLR 平均的总体评价 | §4.2，表 3，附录 A | 5 篇论文、3 名同领域志愿评审器、无答辩；平均 5.00 vs 5.08 | 中 |
| 实现可靠性是当前主要瓶颈 | §4.3，附录 B–C | 人工归因 300 个失败，约 60% 为实现错误；初次实现约 50% 超时 | 中 |

## 批判性分析

### 论证链条

论文最扎实的链条是「成功稀疏 → 必须分层过滤 → 记忆保留失败 → 大规模并行实验得到少数可验证改进」。三个任务均从人工复现基线开始，结果由主脚本二次执行并人工检查，比只依赖生成报告的 [[AI-Scientist-v2-arXiv25]] 更可靠。

最薄弱的跳步有两个。第一，作者把基准指标上的新 SOTA 解释为「科学价值」，但 1.9% 吞吐优化也可能是局部工程；排除与 [[PagedAttention|PagedAttention]] 等已有机制组合是作者的价值判断，不是实验能证明的科学/工程边界。第二，从一次 one-week resource sweep 推出发现规模定律过强；曲线既无随机种子，也无法区分更多并行 trial 和共享记忆的协同收益。

### 假设压力测试

系统要求反馈闭环够快、基线可复制、指标自动计算。论文自己指出 foundation-模型预训练与 pharmaceutical 综合因单次验证昂贵而不适用；这意味着它当前更接近评估器-有依据程序搜索，而非跨科学领域的通用科学家。

发现记忆将失败当作资产，但检索只取 K=15，且 valuation 完全由 LLM 评审器给出。若某方向需要连续多次负结果后才显现价值，Top-K retrieval 和 UCB 会把它过早压低。相反，表面新颖、容易编码的想法可能因 surrogate 乐观而消耗大量预算。

### 实验可信度

三项结果有明确基线、指标、固定模型和执行日志，headline 数字本身证据较强。独立性则有限：任务、起点、系统和验证流程均由同一团队设计；三名人类监督者全程过滤，生成论文的三名评审器规模很小，且自动评审使用同团队的 DeepReviewer。没有外部团队复现 A2P、ACRA、PA-Detect 的完整运行。

AI Text Detection 的 7.9% AUROC、A2P 的 183.7% 和 ACRA 的 1.9% 跨指标不可比较；用「三个任务均超 SOTA」汇总会掩盖效应量差异。论文也未给搜索基线的等预算完整对照：随机只抽 100 想法，而主系统验证约 1,100 个，样本预算不匹配。

### 系统性缺陷

实现层错误占失败的约 60%，说明 GPU 调度、超时、代码正确性和故障恢复不是外围工程，而是方法有效性的主导因素。当前方案依赖 DeepScientist 二次执行和人工逐项检查；论文未报告监督工时、误判率、容器/集群故障恢复、重复实验方差或 malicious 代码防护。

共享记忆每五轮同步并支持 16 个实例，但没有并发一致性、重复试验去重和 stale 发现处理协议。与 [[AutoScientists-arXiv26]] 显式 shared-state / dead-end registry / noise-aware champion 验证相比，DeepScientist 更强调搜索结果，较少审计协调系统本身。

## 局限与后续工作

- **局限 1**：仅三个软件型 AI 任务，且由作者按「前沿、热门、便于人工监督」选择；不支持通用科学发现的外推。
- **局限 2**：三名人类监督者验证所有结果，人工工时未计入约 \$100k 成本，「fully autonomous」边界不透明。
- **局限 3**：规模扩展论断来自单次短曲线，无 seed、误差条和独立任务复现。
- **局限 4**：生成论文平均 soundness 2.27/4，评审器明确指出基准、消融实验和关键基线不充分；想法新颖不等于科学论证完整。
- **后续工作 1**：在固定总 trial/GPU 小时下对比 random、LLM rank、UCB、diversity-aware acquisition，报告进展 yield 与 surrogate calibration。
- **后续工作 2**：对 4/8/16 GPU 各运行至少 5 个 seed，分离 parallelism 与 共享记忆 的贡献，并给发现-rate 置信区间。
- **后续工作 3**：把实现验证器升级为单元测试、实验来源追踪、重复运行和产物 hash，目标是将实现错误占比从约 60% 降到少于 20%。
- **后续工作 4**：公开人工监督时长和 intervention log，并做 no-人类、audit-only、continuous-supervision 三组对照。

## 相关

- **相关概念**：[[Auto-Research]]、Bayesian Optimization、发现记忆、评估器引导搜索、长程智能体
- **同类系统**：[[ASI-ARCH-arXiv25]]、[[AlphaEvolve-arXiv25]]、[[AutoScientists-arXiv26]]、[[AI-Scientist-v2-arXiv25]]
- **评测与审计**：[[AstaBench-ICLR26]]、[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[PaperBench-ICML25|PaperBench]]
- **同会议**：ICLR 2026
