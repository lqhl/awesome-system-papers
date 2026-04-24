---
type: concept
aliases: [KV cache, KV Cache, kv-cache, KV-cache, key-value cache, KvCache]
parent: "[[Attention]]"
last_updated: 2026-04-24
tags: [memory, attention, llm-inference]
---

# KV-Cache

> LLM 推理的核心内存对象。自回归生成每个 token 时，attention 都要看历史所有 K/V；缓存它们避免重新计算，但也带来巨大的内存压力和复杂的管理问题——围绕 KV cache 的优化几乎是过去三年 LLM serving 论文的主线之一。

## 核心思想

Transformer 的 self-attention 在 decode 步骤需要把当前 query 与所有过去 token 的 key/value 做 dot-product。如果每步都重算所有过去 K/V，复杂度是 O(L²)。

**KV cache** 把每个 token 在每层每个 head 的 K/V 算一次后缓存下来：
- prefill 阶段：一次算完整个 prompt 的 K/V
- decode 阶段：每生成一个 token 把它的 K/V 追加到 cache，attention 复杂度降到 O(L)

代价：内存占用与 `batch × seq_len × num_layers × num_heads × head_dim × 2 (K+V) × precision` 成正比，13B Llama-2 单序列 4K context 约 1.6 GB；并发序列 / 长 context 直接撑爆 HBM。

## 为什么这是个核心问题

KV cache 是 LLM serving 系统设计中的「资源拮抗中心」：

1. **内存碎片**：每个 sequence 长度不一，预分配 max_seq_len 浪费严重 → [[PagedAttention]] 解决
2. **跨请求共享**：相同 prompt prefix 应该共享 → [[Prefix-Caching]] / [[RadixAttention]] 解决
3. **长 context 内存爆炸**：百万 token context 单 KV cache > 100 GB → 各种压缩/sparse 方案
4. **分布式调度**：[[Disaggregation]] 把 prefill / decode 分到不同 GPU，KV cache 必须在节点间传递 → RDMA 通信
5. **冷热分层**：热请求 KV 在 HBM、温的在 host DRAM、冷的在 SSD → tiered storage

## 相关概念

- 上游：[[Attention]]、[[Transformer]]
- 内存管理：[[PagedAttention]]、[[Prefix-Caching]]、[[RadixAttention]]
- 压缩 / sparse：[[KV-Cache-Compression]]、[[Sparse-Attention]]、[[MSA-arXiv26|MSA]]
- 分布式：[[Disaggregation]]、[[RDMA]]
- 推理调度：[[Continuous-Batching]]
- 同代际方法：[[FlashAttention]]（attention kernel 优化，与 KV 管理正交但常一起出现）

## 引用本概念的论文

- [[Transformer-NeurIPS17|Attention Is All You Need]] — KV cache 概念的直接上游,scaled dot-product attention 定义了 K/V 数据结构
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 1M context 下 KV cache 压到 DeepSeek-V3.2 的 10%(CSA+HCA),对比 BF16 GQA8 baseline 仅 ~2%;异构 KV 结构 + on-disk storage
- [[TransferEngine-MLSys26|TransferEngine (pplx-garden)]] — KvCache transfer for disaggregated inference
- [[Libra-arXiv26|Libra]] — MoE 推理 LB 的目标也是降 KV cache 加载延迟
- [[MSA-arXiv26|MSA]] — KV cache compression + tiered storage 让 100M token 推理可行
- [[AttnRes-arXiv26|Attention Residuals]] — block representation 用 KV cache 类似机制存储
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — 间接相关（MoE expert 搬运也是 KV-like 数据移动）
- [[FluxMoE-arXiv26|FluxMoE]] — 反向思路：用 expert paging 把 MoE 专家驱逐出 HBM，直接扩大 KV cache 容量，serving 吞吐 3.0× over vLLM

## 已知局限 / 开放问题

- 跨节点 KV transfer 的 vendor lock-in 是 [[TransferEngine-MLSys26|TransferEngine]] 关注的痛点
- KV cache 的 sparse / compressed 表示与精确计算之间的 trade-off 未完全解决
- 异构内存层次（HBM / DRAM / SSD / 远端）的 placement 策略仍在演进
