---
type: paper
name: IC-Cache
full_title: "IC-Cache: Efficient Large Language Model Serving via In-context Caching"
authors: [Yifan Yu, Yu Gan, Nikhil Sarda, Lillian Tsai, Jiaming Shen, et al.]
venue: SOSP
year: 2025
tags: [llm-inference, semantic-cache, in-context-learning, request-routing, load-balancing]
source_pdf: "[[3731569.3764829.pdf]]"
source_md: "[[3731569.3764829]]"
---

# IC-Cache: Efficient Large Language Model Serving via In-context Caching (SOSP 2025)

> **一句话总结**:把历史请求-响应对作为 in-context examples 复用,让小模型模仿大模型的能力并由路由器选择性 offload,吞吐 1.4–5.9× 提升、延迟降低 28–71%,且不损失响应质量。

## 问题

大模型([[LLM]])推理既贵又慢,但用户对质量敏感——DeepSeek-R1 有 671B 参数、部署要 16×A100。现实负载又高度突发:Azure trace 的峰值可到谷值的 25×,给 [[vLLM]] 之类引擎带来巨大 overprovision 压力。作者实测发现 70%+ 的请求在历史里存在语义近似的对应者,但朴素 semantic caching(GPTCache、Databricks)直接返回历史响应会让 win rate 从 50% 跌到 18%,语义相似不等于语义等价。

## 核心方法

IC-Cache 不复用历史响应,而是把历史 request-response pair 作为 **in-context examples** 拼到新请求前面,让小模型借助大模型的 response 轨迹产生高质量输出("live capability augmentation")。架构有三大组件:

1. **Example Selector**:两阶段,先按 relevance 粗筛,再用轻量 proxy 模型估算端到端 utility。除 relevance 外还考虑 example 质量、coverage、目标模型能力,并权衡 input 变长带来的 prefill 开销。
2. **Request Router**:bandit-based 路由,联合请求复杂度、example 质量、瞬时负载,把请求分配给小模型(带 examples)或大模型,随工作负载漂移持续更新策略。
3. **Example Manager**:cost-aware replay——空闲时异步"replay"历史请求,保留质量最好的 response 作为未来 example;带容量上限的 eviction。

可以与 [[vLLM]]、HuggingFace Runtime、LangChain 集成,数行代码改动。建立在 [[KV-Cache]] prefix caching 和 semantic caching 之上,是一层补充。

## 关键结果

- 吞吐提升 **1.4–5.9×**,响应延迟降低 **28–71%**,响应质量不降。
- 在 Gemini-1.5-Pro/Flash、DeepSeek-R1、Qwen2.5-3B/7B/32B、Gemma、Phi 等多模型家族验证。
- 实测 70%+ 请求有 cosine 相似度 >0.8 的历史对应者。
- 小模型 + 精选 in-context examples 可在 NL2Bash 与 Math-500-Hard 上接近大模型。

## 相关

- **相关概念**:[[KV-Cache]]、[[In-Context-Learning]]、[[Semantic-Cache]]、[[Prefix-Caching]]、[[Request-Routing]]
- **同类系统**:[[vLLM]]、[[SGLang]]、GPTCache
- **同会议**:[[SOSP-2025]]
