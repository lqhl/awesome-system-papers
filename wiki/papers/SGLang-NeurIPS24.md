---
type: paper
name: SGLang
full_title: "SGLang: Efficient Execution of Structured Language Model Programs"
authors: [Lianmin Zheng, Liangsheng Yin, Zhiqiang Xie, Chuyue Sun, Jeff Huang, Cody Hao Yu, Shiyi Cao, Christos Kozyrakis, Ion Stoica, Joseph E. Gonzalez, Clark Barrett, Ying Sheng]
venue: NeurIPS
year: 2024
tags: [llm-serving, kv-cache, radix-attention, structured-generation, domain-specific-language]
source_pdf: "[[neurips24-zheng-sglang.pdf]]"
source_md: "[[neurips24-zheng-sglang]]"
---

# SGLang: Efficient Execution of Structured Language Model Programs (NeurIPS 2024)

> **一句话总结**：把 LLM 的多调用工作流（agent、few-shot、branch-solve-merge）抽象为 Python embedded DSL，后端用 **RadixAttention**（radix tree 做跨请求 KV cache 共享）+ **compressed FSM**（fast structured decoding）加速，比 vLLM/Guidance/LMQL 吞吐高 up to 6.4×。

## 问题

LLM 的应用模式从单次问答进化到「LM Program」——包含多次 LLM 调用、控制流、并行分支的复杂工作流（agent、few-shot、tree-of-thought、JSON 解码）。现有系统有两个断点：

1. **编程困难**：每次调用都要手工做 string manipulation、输出解析、并行控制
2. **执行低效**：多次调用间共享的 prefix 被反复 recompute，KV cache 用完即弃，且 structured decoding 每次只解码一个 token

## 核心方法

**Frontend（DSL）**：Python embedded DSL，提供 primitives：
- `gen` / `select`：生成和选择
- `fork` / `join`：并行分支和合并
- `image` / `video`：多模态输入
- `regex`：constrained decoding

Interpreter 模式把 prompt state 当异步 stream 管理，primitive 提交非阻塞，intra-program parallelism 透明。

**Backend Runtime（两个关键优化）**：

1. **RadixAttention**：用 radix tree 维护所有请求的 KV cache，LRU eviction + cache-aware scheduling。自动识别不同请求间的 prefix 重叠并复用 KV cache——比 [[vLLM-SOSP23|vLLM]] 的 block table 方案更细粒度地处理非对齐 prefix 共享（多个请求的公共前缀不必从第 0 个 token 开始完全相同）

2. **Compressed Finite State Machine**：对 constrained decoding（如 JSON schema）的 FS 做压缩——把 multi-token 路径合并为 single-step，一次 decode 多个 token

还支持 API-only 模型（GPT-4）的 **API speculative execution**：并行发起多个 API 调用，用第一个返回的结果。

## 关键结果

- vs vLLM / Guidance / LMQL：**最高 6.4× 吞吐**
- 覆盖 agent control、logical reasoning、few-shot、JSON decoding、RAG、multi-turn chat、multi-modal 多个场景
- 模型：Llama-7B/70B、Mistral-8x7B、LLaVA、LLaVA-NeXT
- 支持 SRT (SGLang Runtime) for open-weight models + OpenAI/Anthropic API models

## 相关

- **核心创新**：[[RadixAttention]]、Compressed FSM、API speculative execution
- **同类系统**：[[vLLM-SOSP23|vLLM]]（PagedAttention）、Guidance、LMQL
- **基于 SGLang 的工作**：[[Libra-ICLR26|Libra]]（MoE LB in SGLang v0.4.10）
- **同会议**：NeurIPS 2024
