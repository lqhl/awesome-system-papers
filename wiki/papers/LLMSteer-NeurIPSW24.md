---
type: paper
name: LLMSteer
full_title: "LLMSteer: Improving Long-Context LLM Inference by Steering Attention on Reused Contexts"
authors: [Zhuohan Gu, Jiayi Yao, Kuntai Du, Junchen Jiang]
venue: NeurIPS Workshop (ML for Systems)
year: 2024
tags: [kv-cache, attention-steering, long-context, prefix-caching, llm-inference]
source_pdf: "[[arxiv24-gu-llmsteer.pdf]]"
source_md: "[[arxiv24-gu-llmsteer]]"
---

# LLMSteer: Improving Long-Context LLM Inference by Steering Attention on Reused Contexts (NeurIPS Workshop 2024)

> **一句话总结**：利用 prefix KV cache 可以被提前修改的特性，用两个不同 prefix prompt 让 LLM 对同一 context 做两次「阅读」，取两次中一致高 attention 的 token 做 attention 加权，在 prefix-caching 兼容的前提下用零额外延迟把 Llama-8B 的长 context 质量拉近 70B 水平（缩小差距 65.9%）、比 AutoPASTA 快 4.8×。

## 问题

LLM 推理中同一份长 context 经常被不同 query 复用，prefix caching 避免了重复 prefill，但模型仍然会在长 context 中「lost in the middle」——KV cache 的内容保持不变，模型对关键信息的注意力不足。已有的 attention steering 方法（如 [[PASTA-ICLR24|PASTA]]、AutoPASTA）要么需要人工标注重点 token，要么依赖 query 信息导致每次请求都得重新 steering——后者和 prefix caching 天然冲突（steering 修改了 KV cache，就不能复用了）。

## 核心方法

**Key insight**：对同一段 context 用不同 prefix prompt 让 LLM 各跑一次 prefill，得到两份不同的 KV cache（分别对应不同的「理解」）。在两次阅读中都获得高 attention 的 token，很可能就是真正需要关注的关键内容。

LLMSteer 三步：

1. **Contextual re-reading**：用两个 query-independent 的 prefix prompt 各处理一次 context，生成两份 KV cache。这两个 pass 是 **offline 的**——不依赖具体 query，所以 steering 结果可以被所有后续 query 复用，天然兼容 prefix caching
2. **Token selection**：每层每 head 累加 attention score，排序取 top-k；取两次 pass 中同时 top-k 的 token 作为 steering target
3. **Steering**：对选中 token 的 attention score 乘以放大系数 α（$A_{steered} = M \odot A$）

## 关键结果

- SQuAD / TriviaQA / GSM8K 三个数据集上，LLMSteer + Llama-8B vs Llama-8B baseline：F1 提升 10-12.5%
- 与 70B 模型的差距缩小 **65.9%**
- 请求延迟接近 8B baseline（prefix cache 已就绪），vs 70B 快 7.1-7.5×，vs AutoPASTA 快 1.4-4.8×
- GSM8K 上甚至**超过 70B 模型**
- 有趣的发现：query-independent 版本的效果**优于** query-dependent 版本——说明好的 attention steering 不需要知道具体 query

## 局限

- 只在 ≤10K token context 上测试，长 context (>10K) 效果未知
- 只测了 Llama-8B，未验证其他模型
- 基于 HuggingFace Transformers，未集成 [[PagedAttention]] / [[FlashAttention]]

## 相关

- **相关概念**：[[KV-Cache]]、[[Attention]]、[[Prefix-Caching]]、[[PagedAttention]]
- **同类方法**：[[PASTA-ICLR24|PASTA]]、AutoPASTA
- **作者线**：Kuntai Du ([[vLLM]] lead)、Junchen Jiang ([[LMCache]] lead)
