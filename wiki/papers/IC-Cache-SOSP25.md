---
type: paper
name: IC-Cache
full_title: "IC-Cache: Efficient Large Language Model Serving via In-context Caching"
authors: [Yifan Yu, Yu Gan, Nikhil Sarda, Lillian Tsai, Jiaming Shen, et al.]
venue: SOSP
year: 2025
tags: [llm-serving, semantic-cache, routing, in-context-learning, cost-optimization]
source_pdf: "[[3731569.3764829.pdf]]"
source_md: "[[3731569.3764829]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# IC-Cache：通过上下文缓存提供高效的大型语言模型服务（SOSP 2025）

> **原题**：IC-Cache: Efficient Large Language Model Serving via In-context Caching

> **一句话总结**：生产 trace 显示 >70% LLM 请求有语义相似历史，但 naive semantic cache 损质量；IC-Cache 选高 utility 历史 request-response 作 in-context examples，用 bandit router 把请求 offload 到小模型，在数百万真实请求上吞吐 1.4–5.9×、延迟降 28–71% 且不损 response quality。

## 问题与动机

LLM serving 优化多聚焦 [[KV-Cache]]/并行/调度，但忽略 **请求相似性**：四数据集 >70% 请求存在语义相似 counterpart。Exact cache hit 低；相似 response 复用质量差。与此同时 1B–10B 长上下文小模型可 in-context learning——能否用历史大模型 exemplar **live augment** 小模型能力，从而 offload 降本降延迟？

## 关键观察 / 隐含假设

- **观察 1**：相似 ≠ 高 utility；example 质量、模型能力、输入长度 trade-off 决定 offload 是否划算。
  - **依赖假设**：两阶段 selection（相关性预筛 + proxy model 估 end-to-end utility）可扩展至百万级日请求。
  - **可能失效场景**：domain shift（新话题）使历史 example 有害；proxy 估错导致质量回归。
- **观察 2**：更多 examples 提升质量但拉长 prefill、逼近小模型 context 上限。
  - **依赖假设**：utility/coverage 联合优化可找到 sweet spot。
  - **可能失效场景**：极长 system prompt 占满 context，offload 空间消失。
- **观察 3**：请求分布、模型版本、负载突发变化要求 router **在线自适应**。
  - **依赖假设**：轻量 bandit router 用近期反馈即可，无需重训大模型。
  - **证据强度**：中。数百万请求评估强，但 quality metric 定义关键。
- **假设 1**：离线 cost-aware replay 提升 example 库质量，online cache 有界且隐私可控。
  - **证据强度**：中。机制合理，privacy 细节依部署而定。

## 核心方法

IC-Cache 三机制：

1. **Two-stage example selection**：高相关子集 + proxy 估 utility。
2. **Bandit-based request router**：联合 request、examples、负载路由到不同能力模型。
3. **Cost-aware example replay**：离线 selective refine；在线 retain/evict 维持有界 cache。

实现：少量代码接入 [[vLLM]]、HuggingFace Runtime、LangChain。与 prefix/semantic cache 互补。

## 设计取舍

- **Quality-preserving offload vs max cost cut**：router 保守可牺牲部分 offload 机会。
- **Example cache vs 直接 distillation**：无离线训练大工程，但 cache 维护与隐私负担。
- **Complementary to vLLM**：不替代 KV 优化，而是 request-level 决策层。

## 实验与结果

- 数百万 open-source + proprietary（Gemini 等）真实请求。
- 吞吐 **1.4–5.9×**；延迟降 **28–71%**；response quality 不下降（相对评估协议）。
- 模型族：DeepSeek-R1、Qwen、Gemma、Phi 等。

## 批判性分析

### 论证链条

「高相似比例 + naive cache 不行 → in-context augmentation + router」→ 大规模 A/B，链条在 reported metrics 下闭合。**Quality 不损**依赖特定 judge/rubric——读者需检查 §6 评估协议是否偏乐观。

### 假设压力测试

- 对抗性或 highly unique 请求占比上升时 offload 收益趋零。
- Example 含敏感历史 response 的 privacy/leakage——论文 §4.3 提及 respect privacy，但生产合规细节不足。
- Bandit 在 cold start 或 model upgrade 后可能短期质量波动。

### 实验可信度

- 数百万真实 query 规模大；多框架集成增可信度。
- 与纯 semantic cache / 固定路由的 ablation 需在原文细读；wiki 读者应回 source_md。
- Proprietary model 部分结果可复现性受限。

### 系统性缺陷

- 论文未讨论与 PD-disaggregation、speculative decoding 的组合运维复杂度。
- Router 单点故障与 cache 一致性跨 region 未讨论。
- Long-term example staleness 对 quality 的 drift 缺少多月跟踪。

## 局限与后续工作

- **局限**：依赖历史大模型 exemplar；privacy/domain shift 风险；quality 评估敏感。
- **Future work**：与 distillation 混合；跨 region example 联邦； formal utility 上界。

## 相关

- **相关概念**：[[LLM-Serving]]、[[vLLM]]、[[Semantic-Cache]]、In-Context-Learning、[[Prefix-Caching]]
- **同类系统**：GPTCache、semantic cache line、model routing 服务
- **同会议**：[[SOSP-2025]]
