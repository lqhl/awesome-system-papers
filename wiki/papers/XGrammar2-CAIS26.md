---
type: paper
name: XGrammar2
full_title: "XGrammar-2: Dynamic and Efficient Structured Generation Engine for Agentic LLMs"
authors: [Linzhang Li, Yixin Dong, Guanjie Wang, Ziyi Xu, Alexander Jiang, Tianqi Chen]
venue: CAIS
year: 2026
tags: [structured-generation, constrained-decoding, tool-calling, llm-serving, agents, area/ai-infra]
source_pdf: "[[cais26-li-xgrammar2.pdf]]"
source_md: "[[cais26-li-xgrammar2]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-18
---

# XGrammar-2：面向 Agentic LLM 的动态结构化生成引擎（CAIS 2026）

> **原题**：XGrammar-2: Dynamic and Efficient Structured Generation Engine for Agentic LLMs

> **一句话总结**：XGrammar-2 观察到 tool calling 的输出结构会跨请求、甚至在单次输出内动态切换，因而加入 TagDispatch、Cross-Grammar Cache、Earley adaptive mask cache、JIT 与 repetition compression；相对既有 structured-generation engine 编译最高快 6×以上，并在现代 serving 中接近零端到端开销。

## 问题与动机

初代 XGrammar 假设请求开始前 grammar 已知；agent response protocol 常由 tag 触发自然语言/JSON/tool-call 切换，且不同 tool schema 只共享局部子结构。整 grammar compile/cache 会重复工作（§1–2）。

## 关键观察 / 隐含假设

- **观察 1：agent grammar 具有细粒度共享而非整对象复用。** Cross-Grammar Cache 以子结构 hash 复用（§3.3）。
  - **依赖假设**：实际 schema 有稳定重复 fragment。
- **观察 2：structure switching 必须成为 runtime semantics。** TagDispatch 在生成遇到 tag 时切 parser（§3.2）。
  - **可能失效场景**：ambiguous/嵌套 tag 或模型偏离 protocol 会增加 recovery complexity。

## 核心方法

系统组合 tag-triggered dispatch、subgrammar cache、Earley-based adaptive token-mask cache、configurable JIT 与 repetition-state compression，并保持与 serving engine 的异步 overlap（§3）。

## 设计取舍

- 动态 grammar 增加表达力，也扩大 parser state 与安全 surface。
- JIT 降首 token 延迟，但配置 K 依赖 workload。
- cache 提速依赖 schema 重复并引入版本/隔离问题。

## 实验与结果

- 在真实 agentic task 中量化 request 内外 grammar dynamism（§4.1）。
- compilation 相对 prior engines 最高快 6×以上，mask generation 与 memory 同时改善（§4.2、Appendix G–H）。
- [[vLLM|vLLM]]/[[SGLang|SGLang]] 类端到端实验显示 structured generation overhead 接近零（§4.3）；各优化消融见 §4.4。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| dynamic grammar 是 agent serving 常见需求 | §4.1 trace/task analysis | 选定 agent workloads | 中到强 |
| XGrammar-2 降低编译/生成开销 | §4.2–4.4、6×+ | grammar benchmark 与 serving | 强 |
| 提升 agent task correctness | Appendix I | protocol correctness，不是任务智能 | 中 |

## 批判性分析

### 论证链条

workload dynamism→两类 first-class mechanism→micro/E2E/ablation 的证据完整。它解决输出约束成本，不改善 agent planning、tool correctness 或 long-horizon state。

### 假设压力测试

多租户 tool schema 高频变化、恶意 recursive grammar 和 cache isolation 可能使编译/内存开销重新显性。

### 实验可信度

同时测 grammar processing 与 engine E2E 较强；缺生产 P99、安全攻击与超大 schema churn。

### 系统性缺陷

grammar/cache version skew、tenant isolation、parser DoS 与 invalid tool semantics 未充分讨论。

## 局限与后续工作

- **局限 1**：结构合法不等于 tool call 语义正确。
- **后续工作 1**：用生产 schema churn 测 P99 compile、cache hit、隔离和攻击防护。

## 相关

- **相关概念**：[[Structured-Generation]]、[[LLM-Inference]]、[[Prefix-Caching]]
- **前作**：[[XGrammar-MLSys25]]
