---
type: paper
name: METIS
full_title: "METIS: Fast Quality-Aware RAG Systems with Configuration Adaptation"
authors: [Siddhant Ray, Rui Pan, Zhuohan Gu, Kuntai Du, Shaoting Feng, et al.]
venue: SOSP
year: 2025
tags: [rag, llm-inference, scheduling, quality-latency-tradeoff, configuration-adaptation]
source_pdf: "[[3731569.3764855.pdf]]"
source_md: "[[3731569.3764855]]"
---

# METIS: Fast Quality-Aware RAG Systems with Configuration Adaptation (SOSP 2025)

> **一句话总结**：per-query LLM 估计 profile 剪枝 RAG 配置空间，再联合调度 GPU batch，四数据集生成延迟 **1.64–2.54×** 降低且不牺牲质量。

## 问题与动机

[[RAG]] 检索更多 chunk 提升质量但增加 [[LLM]] prefill 延迟。Prior work 要么只优化 scheduling（固定配置），要么只调配置（忽视 GPU 队列/显存），且 RAG query 自然语言 under-specified，多 knob（chunk 数、synthesis 方式）组合爆炸。固定配置比 per-query 最优差 **12–15%** 质量且 **2.5–3×** 延迟。

## 关键观察 / 隐含假设

- **观察 1**：query 复杂度（需多少信息片段、是否需 joint reasoning）可由小 LLM profiler 从 query+DB metadata 快速估计，足以剪枝配置空间。
  - **依赖假设**：profiler 延迟 ≈ RAG 执行 1/10；profile 误差不系统性排除最优配置。
  - **可能失效场景**：domain 迁移、corpus 风格剧变；adversarial query 误导 profiler。
  - **证据强度**：中——四 dataset 有效，profiler 错误率未单独报告。
- **观察 2**：剪枝后配置在 GPU 显存约束下选，可避免「看似快但 OOM 排队」的 pitfall（配置 C1 vs C2）。
  - **依赖假设**：scheduler 准确知悉 GPU memory；batch 形成策略与 quality 无关部分可解耦。
  - **可能失效场景**：动态 KV 长度极高 variance 时 memory model 失准。
  - **证据强度**：强——联合调度案例动机清晰。
- **假设 1**：两阶段 decouple（先 quality 剪枝、再 delay 优化）近似全局最优。
  - **证据强度**：中——2× 加速，但未证明 optimality gap bound。

## 核心方法

**METIS** 两阶段：
1. **Profiler LLM**：估计信息片段数、是否 joint reasoning → 缩小 chunk 数、synthesis 等 knob
2. **Joint scheduler**：在剪枝空间内选配置 + batch，最小化 delay 且满足 quality

## 设计取舍

- **取舍 1**：额外 profiler LLM 调用换主 RAG 路径节省，net 仍 1.6–2.5× 快。
- **取舍 2**：profile 特征手工设计，非 end-to-end learned scheduler。
- **边界条件**：QA 类 RAG；agentic multi-hop RAG 未覆盖。

## 实验与结果

- 四 RAG-QA dataset（含 FinSec KG）：延迟 **1.64–2.54×**↓，质量不降
- Per-query vs fixed config：**12–15%** 质量 + **2.5–3×** 延迟优势
- vs SOTA RAG 优化 baseline 全面优于

## Critical Analysis

### 论证链条

「RAG under-specified → 需 per-query config + joint schedule」逻辑清楚。两阶段 decouple 是实用 engineering compromise，非理论最优。

### 假设压力测试

- Profiler 用何模型、成本随 query rate 线性增长？
- 多 hop agent RAG 配置空间更大，剪枝是否仍有效？
- Quality metric 多样性（RAGAS、human eval）下结论稳健性？

### 实验可信度

四 dataset 覆盖 finance/KG 等。缺 production serving trace（并发、cache hit）。Baseline 是否调优公平需读者判断。

### 系统性缺陷

论文未讨论：retrieval 质量波动对 profile 的反馈；多 tenant fairness；与 [[KV-Cache]] prefix sharing 协同。

## 局限与 Future Work

- **局限 1**：额外 profiler 成本与失败模式。
- **局限 2**：非 agentic/multi-hop RAG。
- **Future work 1**：retrieval feedback 闭环，动态修正 profile。

## 相关

- **相关概念**：[[RAG]]、[[LLM]] inference scheduling、[[KV-Cache]]
- **同类系统**：vLLM、SGLang、RAG tuning frameworks
- **同会议**：[[SOSP-2025]]