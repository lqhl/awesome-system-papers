---
type: entity
kind: tool
aliases: [optimize_anything, Optimize Anything, GEPA optimize_anything]
status: active
last_updated: 2026-08-12
tags: [auto-research, llm-optimization, evolutionary-search, agent-optimization]
source_url: "https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/"
---

# Optimize Anything

> GEPA 团队在 [[GEPA-ICLR26]] 之后推出的声明式优化 API：把任意可序列化文本作为候选，把分数与诊断反馈作为搜索信号；它继承 GEPA 的反思式演化内核，但通用 API 的八类案例不属于 ICLR 论文主实验。

## 是什么

`optimize_anything` 只要求两个核心输入：待优化的文本制品（也可以只给自然语言目标）和评价候选的 `evaluator`。用户声明“优化什么、怎样算好”，框架负责维护候选、选择父代、构造反思提示词并提出下一轮修改。对象可以是 prompt、代码、智能体运行框架、调度策略、CUDA kernel、配置或 SVG；统一的是接口，并非这些问题具有相同难度。

评估器除标量分数外，还能返回**可操作附加信息（Actionable Side Information，ASI）**，例如编译错误、运行输出、profiler 轨迹、分项指标、结构化数据或图像。这对应 [[GEPA-ICLR26]] 的 `μ_f`：正式论文证明执行轨迹和评估轨迹能让反思 LM 做隐式 credit assignment，而 API 把这种反馈从复合 LLM prompt 推广到任意文本候选。

同一接口覆盖三种模式：

- **单任务搜索（single-task search）**：候选就是一个问题的答案，例如算法代码或装箱方案；验证集可与目标任务相同，实质是推理时搜索。
- **多任务搜索（multi-task search）**：在一组相关任务间迁移优化经验，例如为多个 PyTorch 算子生成 CUDA kernel。
- **泛化模式（generalization）**：用训练集产生修改、验证集选择候选，优化能迁移到未见任务的 prompt、skill、智能体或策略。

## 与 GEPA 正式论文的关系

[[GEPA-ICLR26]] 是算法证据的来源：它优化复合 AI 系统的一组 prompt，以反思式变异、按样例的 Pareto candidate selection 和可选 system-aware merge 搜索固定权重模型的行为。ICLR 2026 Oral 的主评测覆盖六个自动评分任务、Qwen3-8B 与 GPT-4.1 Mini；在 Qwen3-8B 上，GEPA 平均比 24,000-rollout GRPO 高约 6 个百分点、最多高 19 个百分点，并以 4–35 倍更少 rollout 达到最优结果。

`optimize_anything` 是其后的产品化扩展。它把“多个 prompt 构成的 program”放宽为“任意文本制品”，把论文中的执行/评估轨迹概括为 ASI，并用更小的声明式接口隐藏搜索器配置。因而应分开理解两类证据：

- **论文已验证**：prompt 优化、复合 LLM program、跨两个模型的六任务结果，以及 NPUEval/KernelBench 的推理时代码搜索扩展。
- **博客展示**：repo skill、CloudCast、ARC-AGI agent、AIME prompt、多任务 kernel、视觉制品等八类 API 案例。
- **尚未证明**：一个固定默认配置能跨所有文本对象稳定胜过领域专用优化器，或博客结果可在不同 evaluator、模型和预算下复现。

## 发布方报告的扩展案例

2026 年 2 月 18 日的[发布博客](https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/)报告了八类案例。较能说明系统边界的结果包括：

- repo-specific 编程 skill 在 Bleve 评测中把 Claude Haiku 4.5 完成率从 79.3% 提到 98.3%，把 Claude Sonnet 4.5 从 94.8% 提到 100%，并使 Sonnet 解决时间缩短 47%；
- CloudCast 从 Dijkstra seed 搜索出感知云服务商成本的 Steiner tree，报告测试成本节省 40.2%；
- ARC-AGI 智能体从 10 行 seed code 演化为 300 多行运行框架，Gemini 3 Flash 的公开测试准确率从 32.5% 提到 89.5%；
- AIME prompt 优化把 GPT-4.1 Mini 在 AIME 2025 上的准确率从 46.67% 提到 60.00%；
- 多任务模式在 KernelBench 的 V100 workload 上跨算子迁移 CUDA 优化经验。

这些结果比先前“仅有博客”多了一个经 ICLR 同行评审的算法基础，但案例数字本身仍来自项目方博客及其可运行示例，不等于独立复现。尤其不能用论文的六任务平均结果替博客案例背书：两者的对象、评估器、模型、预算和 selection protocol 并不相同。

## 关键观察 / 隐含假设

- **观察 1：真正统一的是反馈接口，不是搜索问题。** “文本候选 + evaluator + ASI”能隐藏 island topology、变异 meta-prompt 等控件，比 [[AlphaEvolve-arXiv25]] 的整文件演化接口更小；但 evaluator 的正确性、成本和抗 reward hacking 能力仍由用户负责。
- **观察 2：ASI 是可读的近似梯度，其质量决定样本效率。** 编译错误和 profiler 轨迹能直接定位失败，LLM/VLM judge 的解释却可能 noisy、被候选利用或与真实目标错位。[[GEPA-ICLR26]] 的正式实验支持“rich feedback 有用”，但没有证明任意 ASI 都可信。
- **假设 1：相关任务之间存在可迁移结构。** 多任务搜索只有在算子、硬件约束或错误模式共享时才可能优于逐任务搜索；异质任务共享候选池可能只会增加 evaluator 调用。
- **假设 2：验证集足以约束泛化。** 反复按 validation frontier 选候选仍会产生自适应过拟合；需要搜索过程不可见的二级 holdout 审计跨仓库、模型与 evaluator 迁移。
- **观察 3：通用 API 扩大可优化对象，也扩大验证责任。** [[Auto-Research]] 的 verifier-driven 路线原本多针对数学、kernel 或 NAS 等强 evaluator 窄领域；对象扩展到 agent、自然语言 skill 和视觉制品后，结果可信度更加取决于指标是否真正代表目标。

## 演进时间线

- **2025-07**：GEPA 预印本发布，提出 Genetic-Pareto prompt optimizer。
- **2026-01-26**：[[GEPA-ICLR26]] 作为 ICLR 2026 Oral 正式发布，确立反思式 prompt evolution 相对 GRPO 和 MIPROv2 的 rollout 效率证据。
- **2026-02-18**：团队发布 `optimize_anything`，把 GEPA 内核扩展为任意文本制品的单任务、多任务和泛化 API。

## 相关概念

- [[LLM]]

## 相关主题

- [[Auto-Research]]

## 相关论文

- [[GEPA-ICLR26]] — 算法与正式实验基础；页面刻意把论文证据同后续博客案例分开。
- [[AlphaEvolve-arXiv25]] — 同属“LLM proposer + executable evaluator”路线；AlphaEvolve 强调整文件演化、island population 与大规模部署，`optimize_anything` 强调声明式接口和跨模式统一。
- [[BES-arXiv26]] — 用 backward goal decomposition 为稀疏奖励构造密集引导，与 ASI 目标相近，但作用在 trajectory/sample generation，而不是通用文本制品 API。
- [[AccelOpt-MLSys26]] — 将 GEPA 列为需要 architecture best practice 的相关优化方法，反衬 `optimize_anything` 隐藏任务专用搜索 scaffolding 的接口取舍。

## 外部来源

- [GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning](https://openreview.net/forum?id=RQm2KQTM5r) — ICLR 2026 Oral
- [optimize_anything: A Universal API for Optimizing any Text Parameter](https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/) — GEPA 项目发布博客，2026-02-18
