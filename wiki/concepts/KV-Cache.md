---
type: concept
aliases: [KV cache, KV Cache, kv-cache, KV-cache, key-value cache, KvCache]
parent: "[[Attention]]"
last_updated: 2026-06-09
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
- [[fabric-lib-MLSys26|fabric-lib]] — KvCache transfer for disaggregated inference
- [[Libra-ICLR26|Libra]] — MoE 推理 LB 的目标也是降 KV cache 加载延迟
- [[MSA-arXiv26|MSA]] — KV cache compression + tiered storage 让 100M token 推理可行
- [[AttnRes-arXiv26|Attention Residuals]] — block representation 用 KV cache 类似机制存储
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — 间接相关（MoE expert 搬运也是 KV-like 数据移动）
- [[FluxMoE-arXiv26|FluxMoE]] — 反向思路：用 expert paging 把 MoE 专家驱逐出 HBM，直接扩大 KV cache 容量，serving 吞吐 3.0× over vLLM
- [[IceCache-arXiv26|IceCache]] — semantic token clustering + PagedAttention page selection；用 DCI-tree 把相关 tokens 聚到同一 page，36k context 下 99.0% full-cache accuracy、0.11s TPOT
- [[MoE-nD-arXiv26|MoE-nD]] — per-layer routing eviction ratio / K bits / V bits；LongBench 4-task 上 136 MB cache 达到 14x compression 且匹配 1.9 GB full cache baseline
- [[CRAFT-MLSys26|CRAFT]] — expert replication 挤占 GPU memory，影响 MoE serving 的 KV cache 容量与 batch 并发
- [[OPKV-MLSys26|OPKV]] — recallable sparsity 把非关键 KV offload 到 CPU 并按需召回，plugin 接入 [[PagedAttention]] 后高 batch 吞吐 1.3–1.8×
- [[Stream2LLM-MLSys26|Stream2LLM]] — streaming prompt 动态增长/更新时用 LCP 选择性失效 KV block，多租户 RAG 场景 TTFT 最多 11×
- [[GhostServe-MLSys26|GhostServe]] — erasure-coded parity checkpoint 保护流式 KV，8:2 比全量复制省 75% 内存
- [[BreakingTheIce-MLSys26|BreakingTheIce]] — vLLM 启动阶段 KVCache profiling 为少数 GPU-bound 步骤；dense 模型与参数量线性相关，[[MoE]] 因 expert routing 偏离
- [[DataflowIsAllYouNeed-MLSys26|DataflowIsAllYouNeed]] — SN40 decode 优化权重与 KV 加载，HBM 利用率从 GPU 21% 提升至 roofline 75%+
- [[MAC-Attention-MLSys26|MAC-Attention]] — 长上下文 decode 复用 attention summary，KV 访问最高减 99%，保持 full-attention 质量
- [[TiDAR-MLSys26|TiDAR]] — hybrid diffusion-AR 架构支持 exact KV cache，单 forward 并行 draft+sample
- [[SpanQueries-MLSys26|SpanQueries]] — 用交换律约束 span query IR 优化跨请求 KV 局部性，TTFT 10–20×
- [[ContextPilot-MLSys26|ContextPilot]] — context block 对齐/去重提升 prefix hit，长上下文 prefill 1.5–3×
- [[LocalityAwareBeamScheduling-MLSys26|LocalityAwareBeamScheduling]] — TTC beam search 下 KV 占 80%+，调度降传输 >95%
- [[ScaleSearch-MLSys26|ScaleSearchAttention]] — NVFP4 KV cache + 注意力矩阵，PPL 近零损
- [[SuperInfer-MLSys26|SuperInfer]] — GH200 上 DuplexKV 全双工 KV rotation，SLO-aware offload 扩 effective KV 容量
- [[SkipKV-MLSys26|SkipKV]] — LRM 冗长 CoT 的句子级 KV eviction + steering，2× 压缩下 accuracy 最高 +26.7%
- [[TeleRAG-MLSys26|TeleRAG]] — RAG 多轮 pipeline 中 GPU 侧 IVF retrieval 与 LLM [[KV-Cache]] 争用显存，lookahead prefetch 缓解
- [[SparseSpec-MLSys26|SparseSpec]] — dynamic KV manager 激进提并发，OOM 时 chunk-wise 异步 offload 到 host
- [[FlexiCache-MLSys26|FlexiCache]] — 按 head 时序稳定性分层：stable head GPU 只留 top-K，其余 offload host
- [[SHIP-MLSys26|SHIP]] — weights+KV 全放 on-chip SRAM，两级 prefix cache（SRAM+host DRAM）
- [[CDLM-MLSys26|CDLM]] — block-causal student 支持 block KV cache，DLM 推理 latency 最高 14.5×↓
- [[Kitty-MLSys26|Kitty]] — 2-bit KV + channel-wise INT4 boost，内存近 8×、吞吐 2.1–4.1×，精度接近 FP16
- [[PipelinedSharding-MLSys26|PipelinedSharding]] — 客户端将 KV cache 与 attention 一并纳入 sub-layer schedule，64K context TPS 最高 30×
- [[ExecuTorch-MLSys26|ExecuTorch]] — 端侧 LLM 的 per-channel quantized KV cache + quantized attention 降长 context 内存
- [[FlashAgents-MLSys26|FlashAgents]] — 多 agent 链路上游 decode 与下游增量 prefill 共享/增量构建 KV cache
- [[RaidServe-MLSys26|RaidServe]] — cyclic placement 均衡 irregular TP 下 KV；host backup 恢复 41.5× 快于 recompute
- [[MorphServe-MLSys26|MorphServe]] — layer swap 释内存后弹性扩 KV，峰值超全精度 32.97%
- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — persistent/paged KV cache 与 tiered memory offloading 的系统级 trade-off 分析

## 已知局限 / 开放问题

- 跨节点 KV transfer 的 vendor lock-in 是 [[fabric-lib-MLSys26|fabric-lib]] 关注的痛点
- KV cache 的 sparse / compressed 表示与精确计算之间的 trade-off 未完全解决
- 异构内存层次（HBM / DRAM / SSD / 远端）的 placement 策略仍在演进
