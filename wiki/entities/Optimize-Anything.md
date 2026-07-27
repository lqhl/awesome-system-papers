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

> GEPA 在 2026 年发布的声明式优化 API：把代码、prompt、agent 架构、配置等可序列化文本统一表示为候选制品，用 evaluator 的分数与诊断反馈驱动 LLM 搜索。

## 是什么

`optimize_anything` 将优化问题压缩为两个核心输入：待优化的文本制品（或自然语言目标）和评价候选的 `evaluator`。用户声明「优化什么、如何衡量」，框架负责构造 reflection prompt、选择候选、维护搜索状态并提出下一轮修改。它建立在 GEPA 的 reflective prompt evolution 上，但把搜索对象从 prompt 扩展到代码、agent harness、调度策略、CUDA kernel、配置和 SVG 等任意文本表示。

evaluator 除了返回标量分数，还能通过 **Actionable Side Information（ASI）** 回传编译错误、运行输出、profiler trace、分项指标、结构化数据或图像。LLM proposer 因而不是盲目 mutation，而是读取失败原因后做定向修改；系统同时按 task、example 或 metric 维护 Pareto frontier，避免平均分掩盖局部强项。

同一接口覆盖三种模式：

- **Single-task search**：候选本身就是单个问题的答案，例如算法代码或 packing solution。
- **Multi-task search**：在一组相关任务间迁移优化经验，例如为多个 PyTorch operator 生成 CUDA kernel。
- **Generalization**：用 training set 优化 prompt、skill、agent 或 policy，再用独立 validation set 选择能迁移到未见任务的候选。

## 发布方报告的结果

2026 年 2 月 18 日的[发布博客](https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/)报告了八类案例。较能说明系统边界的结果包括：

- repository-specific coding skill 在 Bleve 评测中把 Claude Haiku 4.5 的完成率从 79.3% 提至 98.3%、Claude Sonnet 4.5 从 94.8% 提至 100%，并将 Sonnet resolve duration 缩短 47%；
- CloudCast 从 Dijkstra baseline 搜索出 provider-aware Steiner tree，报告 test cost saving 40.2%；
- ARC-AGI agent 从 10 行 seed 演化为 300 多行 harness，Gemini 3 Flash public test accuracy 从 32.5% 提至 89.5%；
- AIME prompt optimization 将 GPT-4.1-mini 在 AIME 2025 上的准确率从 46.67% 提至 60.00%；
- multi-task 模式在 KernelBench 的 V100 workload 上跨 operator 迁移 CUDA 优化经验。

这些数字来自项目方博客及其 runnable examples，不等同于独立复现或同行评审证据。不同案例使用不同 evaluator、模型、预算和 baseline，不能把「八个领域都有效」直接解释成统一算法在任意领域都稳定优于专用优化器。

## 关键观察 / 隐含假设

- **观察 1：真正被统一的是优化接口，不是问题难度。** 「文本制品 + evaluator + ASI」隐藏了 island topology、mutation prompt 等 framework-specific 控件，比 [[AlphaEvolve-arXiv25]] 的整文件 evolution 接口更窄；但 evaluator 的正确性、成本和抗 reward hacking 仍由用户承担。
- **观察 2：ASI 是可读的近似梯度，但不是可信梯度。** 编译错误和 profiler trace 能直接定位失败，LLM/VLM judge 的自然语言反馈却可能噪声大、被候选利用或与真实目标错位。[[BES-arXiv26]] 用 backward goal decomposition 缓解 sparse terminal reward，指向同一个问题：没有高质量 dense feedback 时，搜索效率会快速下降。
- **假设 1：不同任务之间存在可迁移的优化结构。** Multi-task search 只有在相关 operator、硬件约束或错误模式共享时才可能优于逐任务搜索；异质任务混在同一 Pareto frontier 中可能增加 evaluator 调用而不产生 transfer。
- **假设 2：validation set 足以约束 agent 或 skill 的泛化。** Generalization 模式比直接优化 test task 更严格，但反复选择 validation frontier 仍会产生 adaptive overfitting；跨 repository、跨模型和跨 evaluator 的迁移需要独立 held-out audit。
- **观察 3：通用 API 扩大了 auto-research 的可操作范围，也扩大了验证责任。** [[Auto-Research]] 中 verifier-guided 路线原本多针对数学、kernel 或 NAS 等强 evaluator 窄域；`optimize_anything` 把同一 loop 推向 agent 架构、自然语言 skill 和视觉制品后，结果可信度更依赖 evaluator 是否代表真实目标。

## 演进时间线

- **2026-02-18**：GEPA 发布 `optimize_anything`，将 reflective prompt evolution 扩展为任意文本制品的声明式优化接口，并公开 single-task、multi-task、generalization 三种模式及案例代码。

## 相关概念

- [[LLM]]

## 相关主题

- [[Auto-Research]]

## 相关论文

- [[AlphaEvolve-arXiv25]] — 同属 LLM proposer + executable evaluator 路线；AlphaEvolve 强调整文件 evolution、island population 与大规模部署案例，`optimize_anything` 强调更小的声明式接口和跨模式统一。
- [[BES-arXiv26]] — 通过 backward goal decomposition 为 sparse reward 构造 dense guidance，与 ASI 的目标相近，但作用在 trajectory/sample generation 而非通用文本制品 API。
- [[AccelOpt-MLSys26]] — 将 GEPA 列为需要架构 best practice 的相关优化方法，反衬 `optimize_anything` 试图隐藏 task-specific search scaffolding 的接口取舍。

## 外部来源

- [optimize_anything: A Universal API for Optimizing any Text Parameter](https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/) — GEPA 项目发布博客，2026-02-18
