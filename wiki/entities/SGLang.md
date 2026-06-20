---
type: entity
kind: system
aliases: [SGLang]
status: active
last_updated: 2026-06-20
tags: [llm-inference, serving, scheduling]
---

# SGLang

> LMSYS 团队提出的 LLM serving 框架，以 [[RadixAttention]]（radix tree 跨调用 prefix 共享）与 structured generation DSL 为标志；在 MoE load balancing、agent 流式 prefill、speculative decoding 与长 prompt 场景常被作为 [[vLLM]] 的替代或对照。

## 是什么

SGLang 由 Zheng 等人在 NeurIPS 2024 提出（[[SGLang-NeurIPS24]]），核心命题是：**LM Program 的多调用结构应显式暴露给 runtime**，而不是把每次 `gen()` 当成独立请求。Frontend 提供 Python embedded DSL（`gen`、`fork`/`join`、`select`、regex 约束等）；backend runtime（SRT）用 radix tree 维护 token 序列到 [[KV-Cache]] 的映射，与 [[PagedAttention]] 兼容，并配合 cache-aware scheduling 与 compressed FSM（Jump Forward）加速 constrained decoding。

论文在 Llama-7B 等 workload 上相对 vLLM v0.2.5、Guidance、LMQL 吞吐最高 **6.4×**、延迟最高 **3.7×** 降低；Chatbot Arena 生产 trace 上 LLaVA hit rate **52.4%**、Vicuna **74.1%**。这些论文共同假设：当 workload 存在跨调用 prefix 重叠（few-shot、agent template、RAG context、短输出多轮对话）时，RadixAttention 的收益显著；长输出单轮对话或低重复 prompt 时收益迅速下降。

SGLang 与 vLLM 的分工在 wiki 图谱中反复出现：vLLM 更像通用 chat/completion serving 默认栈；SGLang 更擅长**程序结构已知**的 agent、benchmark、RL rollout 与 MoE EP 实验平台。大量 2025–2026 论文选择 SGLang 实现系统原型，因其 scheduler、CUDA graph 与 MoE 路径相对可改，且 PRISM、Libra 等工作强调必须在生产栈而非 PyTorch toy 上验证加速。

## 关键观察 / 隐含假设

- **观察 1：RadixAttention 的收益与 prefix 局部性强绑定，且会与 batch size 争用显存。** [[SGLang-NeurIPS24]] 测量 MMLU/HellaSwag/ReAct 等场景 **50%–99%** cache hit；但 waiting queue 足够大时会 evict 全部 cache 换更大 batch。cache-aware 调度按最长前缀优先，论文承认可能导致 starvation（[[BatchLLM-MLSys26]] 进一步指出 LRU radix 在离线全局 prefix 场景仅 **35.8%** token 节省 vs 最优 **58.1%**）。
- **观察 2：SGLang 是 MoE 系统论文的常见实现载体，尤其在 prefill EP 与 speculative decoding 方向。** [[Libra-ICLR26]] 基于 SGLang v0.4.10 做 lookahead expert LB；[[CRAFT-MLSys26]] 在 v0.4.8 集成 cost-aware replication；[[FarSkip-Collective-MLSys26]] 在 SGLang 上实现 MoE EP 通信重叠，DeepSeek-V3 671B prefill 最高 **1.34×** TTFT。
- **观察 3：生产栈级 speculative decoding 评测必须以 SGLang 类引擎为锚，否则易高估收益。** [[PRISM-MLSys26]] 在 SGLang 完整集成 drafter，相对已优化引擎再提 **>2.6×** 吞吐；[[ReSpec-MLSys26]] 把 EAGLE-3 搬进 VeRL+SGLang 训练环，端到端 **1.5–4.5×** 且 reward 曲线与无 SD baseline 一致。
- **观察 4：与 vLLM 共享的 PagedAttention swap 语义在 superchip 上同样成为瓶颈。** [[SuperInfer-MLSys26]] 指出并发 H2D/D2H 在共享 block table 下存在 data race，迫使 [[vLLM]]/[[SGLang]] 串行 swap-in/out；说明两者在 KV offload 路径上仍有共同软件债。
- **观察 5：框架选择本身会引入 output drift，不能仅用吞吐验收迁移。** [[DriftBench-MLSys26]] 在 vLLM 0.11.0 vs SGLang 0.5.2 上测 **236,985** prompt-response 对；生产案例 H100/FP16/SGLang→B200/FP8/SGLang 出现 **23.85%** safety 分类翻转而 aggregate unsafe 率仅 +1.15%。

## 演进时间线

- **2024 NeurIPS**：[[SGLang-NeurIPS24]] 提出 RadixAttention、compressed FSM 与 frontend-runtime co-design。
- **2025**：[[Libra-ICLR26]]（SGLang v0.4.10 MoE LB）、[[LatencyOptimal-MoELB-INET4AI25]]（v0.4.7 评估 EPLB）等把 SGLang 定为 MoE serving 实验平台。
- **2026 MLSys**：[[PRISM-MLSys26]]、[[GhostServe-MLSys26]]、[[FlashAgents-MLSys26]]、[[LAPS-MLSys26]]、[[FlashInfer-Bench-MLSys26]]、[[FarSkip-Collective-MLSys26]] 等在同一时期选用 SGLang 做系统级验证或后端集成。

## 相关概念

- [[RadixAttention]]
- [[KV-Cache]]
- [[Prefix-Caching]]
- [[PagedAttention]]
- [[MoE]]
- [[Continuous-Batching]]
- [[Speculative-Decoding]]

## 相关论文

- [[SGLang-NeurIPS24]] — 原始系统：RadixAttention、compressed FSM、LM Program DSL
- [[Libra-ICLR26]] — 基于 SGLang v0.4.10 的 MoE prefill load balancing，最高 +19.2% throughput
- [[CRAFT-MLSys26]] — 在 SGLang v0.4.8 替代 EPLB 做 per-layer expert replication，goodput 1.14×
- [[PRISM-MLSys26]] — speculative drafter 系统级集成，>2.6× 解码吞吐
- [[ReSpec-MLSys26]] — VeRL+SGLang RL 环自适应 speculative decoding，1.5–4.5×
- [[FarSkip-Collective-MLSys26]] — MoE EP 通信重叠，推理 TTFT 最高 +18.5%
- [[FlashAgents-MLSys26]] — inter-agent streaming prefill + intra-turn prefix cache，workflow 延迟最高 −40%
- [[LAPS-MLSys26]] — PD-disaggregation 上长短分离，prefill 延迟 −30%
- [[LatencyOptimal-MoELB-INET4AI25]] — SGLang v0.4.7 评估 EPLB / heuristic
- [[GhostServe-MLSys26]] — SGLang 0.5.1 后端 erasure-coded KV checkpointing
- [[ContextPilot-MLSys26]] — context block 对齐/去重，与 SGLang prefix cache 协同
- [[Behdin-SemanticJobSearch-MLSys26]] — LinkedIn cross-encoder prefill-only 优化，2000 items/s/GPU
- [[FlashInfer-Bench-MLSys26]] — ShareGPT trace + `apply()` 动态替换 SGLang 算子
- [[BatchLLM-MLSys26]] — 离线全局 prefix 树，相对 SGLang 最高 10.8×
- [[DriftBench-MLSys26]] — 105 配置 drift 测量中的 serving 框架维度
- [[OSWorld-Human-MLSys26]] — Agent S2 grounding 模型用 SGLang serving
- [[SHIP-MLSys26]] — Groq SRAM pipeline 对比对象之一
- [[EventTensor-MLSys26]] — ETC megakernel 对比 SGLang v0.5 baseline，batch=1 decode 1.20×