---
type: entity
kind: tool
aliases: [optimize_anything, Optimize Anything, GEPA optimize_anything]
status: active
last_updated: 2026-07-27
tags: [auto-research, llm-optimization, evolutionary-search, agent-optimization]
source_url: "https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/"
---

# Optimize Anything

> GEPA 在 2026 年发布的声明式优化 API：只要一个对象能表示成文本、质量能被评估器测量，就可以让 LLM 根据分数和诊断反馈持续改进它。

## 是什么

`optimize_anything` 只要求两个核心输入：待优化的文本制品（也可以只给自然语言目标）和评价候选的 `evaluator`。用户声明“优化什么、怎样算好”，框架负责构造反思提示词、选择候选、维护搜索状态并提出下一轮修改。它建立在 GEPA 的反思式提示词演化之上，但把对象扩展到代码、智能体运行框架、调度策略、CUDA kernel、配置和 SVG 等任意文本表示。

评估器除了返回标量分数，还能通过**可操作的附加信息（Actionable Side Information，ASI）**回传编译错误、运行输出、profiler 轨迹、分项指标、结构化数据或图像。因此，LLM 提议器不是盲目变异，而是读取失败原因后定向修改。系统还会按任务、样例或指标维护 Pareto 前沿，避免平均分掩盖某个候选的局部强项。

同一接口覆盖三种模式：

- **单任务搜索（single-task search）**：候选本身就是单个问题的答案，例如算法代码或装箱方案。
- **多任务搜索（multi-task search）**：在一组相关任务间迁移优化经验，例如为多个 PyTorch 算子生成 CUDA kernel。
- **泛化模式（泛化）**：用训练集优化提示词、skill、智能体或策略，再用独立验证集选择能迁移到未见任务的候选。

## 发布方报告的结果

2026 年 2 月 18 日的[发布博客](https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/)报告了八类案例。较能说明系统边界的结果包括：

- 面向特定仓库的编程 skill 在 Bleve 评测中把 Claude Haiku 4.5 的完成率从 79.3% 提到图中报告的 98.3%，把 Claude Sonnet 4.5 从 94.8% 提到 100%，并使 Sonnet 的解决时间缩短 47%；
- CloudCast 从 Dijkstra 基线搜索出感知云服务商成本的 Steiner tree，报告测试成本节省 40.2%；
- ARC-AGI 智能体从 10 行种子代码演化为 300 多行运行框架，Gemini 3 Flash 的公开测试准确率从 32.5% 提到 89.5%；
- AIME 提示词优化把 GPT-4.1-mini 在 AIME 2025 上的准确率从 46.67% 提到 60.00%；
- 多任务模式在 KernelBench 的 V100 工作负载上跨算子迁移 CUDA 优化经验。

这些数字来自项目方博客及其可运行示例，不等同于独立复现或同行评审证据。不同案例使用不同评估器、模型、预算和基线，不能把「八个领域都有效」直接解释成统一算法在任意领域都稳定优于专用优化器。

## 关键观察 / 隐含假设

- **观察 1：真正统一的是接口，不是问题难度。** “文本制品 + 评估器 + ASI”隐藏了 island topology、变异提示词等框架专用控件，比 [[AlphaEvolve-arXiv25]] 的整文件演化接口更小；但评估器的正确性、成本和抗奖励投机能力仍由用户负责。
- **观察 2：ASI 像可读的近似梯度，但不一定可信。** 编译错误和 profiler 轨迹能直接定位失败，LLM/VLM 评审器的自然语言反馈却可能噪声大、被候选利用或与真实目标错位。[[BES-arXiv26]] 用向后目标分解缓解稀疏最终奖励，指向同一问题：没有高质量的密集反馈时，搜索效率会迅速下降。
- **假设 1：相关任务之间存在可迁移的优化结构。** 多任务搜索只有在算子、硬件约束或错误模式共享时才可能优于逐任务搜索；把异质任务放进同一 Pareto 前沿，可能只会增加评估器调用。
- **假设 2：验证集足以约束智能体或 skill 的泛化。** 泛化模式比直接优化测试任务更严格，但反复选择验证集前沿仍会产生自适应过拟合；跨仓库、模型和评估器的迁移需要独立留出集审计。
- **观察 3：通用 API 扩大了可优化对象，也扩大了验证责任。** [[Auto-Research]] 中验证器驱动路线原本多针对数学、kernel 或 NAS 等强评估器窄领域；`optimize_anything` 把同一循环推向智能体架构、自然语言 skill 和视觉制品后，结果可信度更依赖评估器是否真正代表目标。

## 演进时间线

- **2026-02-18**：GEPA 发布 `optimize_anything`，将反思式提示词演化扩展为任意文本制品的声明式优化接口，并公开单任务、多任务、泛化三种模式及案例代码。

## 相关概念

- [[LLM]]

## 相关主题

- [[Auto-Research]]

## 相关论文

- [[AlphaEvolve-arXiv25]] — 同属“LLM 提议器 + 可执行评估器”路线；AlphaEvolve 强调整文件演化、island population 与大规模部署，`optimize_anything` 强调更小的声明式接口和跨模式统一。
- [[BES-arXiv26]] — 通过向后目标分解为稀疏奖励构造密集引导，与 ASI 的目标相近，但作用在轨迹和样本生成，而不是通用文本制品 API。
- [[AccelOpt-MLSys26]] — 将 GEPA 列为需要架构最佳实践的相关优化方法，反衬 `optimize_anything` 试图隐藏任务专用搜索脚手架的接口取舍。

## 外部来源

- [optimize_anything: A Universal API for Optimizing any Text Parameter](https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/) — GEPA 项目发布博客，2026-02-18
