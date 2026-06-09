---
type: paper
name: IceCache
full_title: "ICECACHE: Memory-Efficient KV-Cache Management for Long-Sequence LLMs"
authors: [Yuzhen Mao, Martin Ester, Qitong Wang, Ke Li]
venue: arXiv
year: 2026
tags: [llm-inference, kv-cache, long-context, pagedattention, sparse-attention, offloading]
source_pdf: "[[arxiv26-icecache.pdf]]"
source_md: "[[arxiv26-icecache]]"
---

# ICECACHE: Memory-Efficient KV-Cache Management for Long-Sequence LLMs (arXiv 2026)

> **一句话总结**：IceCache 把语义相近的 tokens 聚到同一批 [[PagedAttention]] page，再用 DCI-tree 做 query-aware page retrieval 和 CPU-GPU bulk loading，在 LongBench / GSM8K CoT / RULER 上以 64-256 token budget 保持接近 full [[KV-Cache]] accuracy，并在 36k context 下实现 99.0% full-cache accuracy 与约 0.11s TPOT。

## 问题

长序列 LLM 推理中，[[KV-Cache]] 占用随 context length 线性增长，成为显存瓶颈。已有 eviction 方法速度快但常用静态 token 选择，长生成任务中 accuracy 掉得明显；offloading 方法能把 KV 放到 CPU，但需要精确找回当前 query 需要的 cache page，否则会加载大量无关 token，浪费 PCIe 带宽。

Quest、ArkVale 等基于 PagedAttention 的 query-aware 方法仍按原始 token 顺序组织 page。语义相关 token 可能分散在许多 page 中，导致为了找少数关键 token 必须搬很多无关 page。

## 核心方法

IceCache 改变 KV page 的组织方式：prefill 阶段按 key embedding 的语义相似度构造每个 attention head 的 DCI-tree，把相似 tokens 聚为 tree node，并把 node 映射到 physical memory page。decode 阶段给定当前 query 后，IceCache 用 M-DCI approximate nearest neighbor search 找 top-k relevant tokens / nodes，再加载对应 pages 做 sparse attention。

它与 [[PagedAttention]] 的关系是：仍使用 page abstraction 管理 KV，但 page 不再按 token 顺序填充，而是按语义 cluster 填充。这样相关 token 更可能集中在少数 page，提升 selected page 的 hit rate。

系统还做了两个工程优化：bulk loading 把分散的 selected pages 聚合成 contiguous CPU preload buffer 后一次性传到 GPU，再 scatter 到 KV table；prefill pipeline 则重叠 GPU prefill、PCIe KV offloading 和 CPU DCI indexing。

## 关键结果

- Passkey Retrieval 在 10k-100k words、budget 64/128/256 下保持 100% retrieval accuracy。
- LongBench 上，Llama-3.1-8B budget 64 时平均 accuracy 47.8，超过 PQCache budget 256 的 47.3；budget 256 达 49.0，接近 Full KV 49.5。
- Qwen3-32B 上 budget 64 保留 Full KV 97.2% LongBench performance，budget 256 保留 99.3%；LongChat-7B-v1.5 上分别为 96.3% 和 99.4%。
- 36k sequence 下，IceCache TPOT 约 0.11s 且保持 99.0% full-cache accuracy；IceCache(reuse) 可到 0.06s。
- GSM8K CoT 10% budget 下达到 47.4%，接近 Full KV 48.2%，高于 PQCache 46.0%。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Sparse-Attention]]
- **同类方法**：Quest、ArkVale、PQCache、OmniKV、SnapKV、StreamingLLM
- **实现关键词**：DCI-tree、semantic token clustering、query-aware page selection、bulk loading

