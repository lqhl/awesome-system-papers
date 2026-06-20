---
type: concept
aliases: [KV cache, KV Cache, kv-cache, KV-cache, key-value cache, KvCache]
parent: "[[Attention]]"
last_updated: 2026-06-20
tags: [memory, attention, llm-inference]
---

# KV-Cache

> 自回归推理中缓存每层每 token 的 K/V 张量，把 decode 复杂度从 O(L²) 降到 O(L)；它是 LLM serving 的主导内存对象，也是 batch 并发、长 context、disaggregation 与压缩/sparse 优化的共同锚点。

## 核心思想

Transformer self-attention 在 decode 每步只需算当前 token 的 query，却要与全部历史 key/value 做点积。若每步重算所有过去 K/V，复杂度回到 O(L²)。**KV cache** 在 prefill 一次性算完 prompt 的 K/V，decode 每生成一个 token 就追加一对 K/V，attention 每步只读缓存、不再重算。

内存占用与 `batch × seq_len × num_layers × num_heads × head_dim × 2 (K+V) × precision` 成正比。13B Llama-2 单序列 4K context 约 1.6 GB；百万 token context 单 KV 可超 100 GB。现代 serving 栈（[[vLLM]]、[[SGLang]]）围绕 KV cache 做分页、共享、offload 与压缩——几乎整条 LLM inference 系统论文的主线都与此对象相关。

## 为什么重要

这些论文共同假设：**在 co-located 或 disaggregated serving 中，KV cache 容量与带宽往往先于算力成为吞吐与 SLO 的硬约束**。[[vLLM-SOSP23|vLLM]] 测量显示连续预分配下仅 20–38% KV 显存真正存 token state；[[FluxMoE-arXiv26|FluxMoE]] 在 Mixtral 上把 KV budget 从 20 GiB 扩到 60 GiB 可使 batch 128、context 4096 吞吐提升 58.8%。

KV cache 还是跨子系统边界的「搬运对象」：[[Disaggregation]] 要在 prefill/decode 池间传 KV；[[Prefix-Caching]] / [[RadixAttention]] 要在请求间共享 prefix KV；[[MoE]] serving 中 expert 权重与 KV 争用同一块 HBM。因此 KV 管理不是单一优化点，而是调度、内存层次、网络传输与 attention kernel 的交汇中心。

## 关键观察 / 隐含假设

- **观察 1：KV cache 是 serving 的主导内存瓶颈，且连续预分配利用率极低。** [[vLLM-SOSP23|vLLM]] 在 A100 上测得 FasterTransformer/Orca 类实现仅 20.4%–38.2% KV 显存用于实际 token state；根因是 varying-length 序列 + max_seq_len 预分配 + 无法 block 级共享。
- **观察 2：token 级 sparsity 与 page 级管理存在粒度错配。** [[OPKV-MLSys26|OPKV]] 指出 recallable sparsity 在 token 级选关键 KV，但 [[PagedAttention]] 按 page（16 token）管理；按「含任一选中 token 的整页」召回可使 I/O 放大约 4×。
- **观察 3：offload 路径的 effective bandwidth 决定 SLO-aware serving 上限。** [[SuperInfer-MLSys26|SuperInfer]] 发现 GH200 上 [[vLLM]] 式 PCIe offload 仅用到 NVLink-C2C <5% 峰值（~10 GB/s vs 理论 ~200 GB/s/方向），根因是 [[PagedAttention]] 碎片化小段与串行 H2D/D2H。
- **观察 4：长 context 下 attention 对少数 token 高度稀疏，但 page layout 影响 offload 效率。** [[IceCache-arXiv26|IceCache]] 认为按 token 顺序组织 page 会使 query-aware retrieval 加载大量无关 token；语义聚类 page 可在 256-token budget 下保留约 99% Full KV accuracy。
- **观察 5：MoE 冷 expert 权重与热 KV cache 争用 HBM。** [[FluxMoE-arXiv26|FluxMoE]] 把瓶颈归因于「冷 expert 常驻挤占 KV budget」；expert paging 腾 HBM 后 vLLM 在 batch 128→256 时因 KV swap 吞吐下降 32.2%，FluxMoE 仍可 scale。

## 设计空间与取舍

- **分页管理（[[PagedAttention]]）**：OS 式 block + block table 消除内外部碎片、支持 copy-on-write prefix 共享；代价是 attention kernel 慢 20–26%（[[vLLM-SOSP23|vLLM]]），但更大 batch 抵消。
- **跨请求共享（[[Prefix-Caching]] / [[RadixAttention]]）**：相同 prompt prefix 复用 physical block；边界是多轮对话 KV 生命周期、跨实例 disaggregation 时 prefix 一致性难保证（[[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]]）。
- **压缩 / 量化（[[Kitty-MLSys26|Kitty]]、[[ScaleSearch-MLSys26|ScaleSearchAttention]]）**：2-bit/FP4 KV 近 8× 省内存；牺牲精度或需 per-channel 校准，与 exact attention 质量 trade-off 未完全闭合。
- **稀疏 / recallable offload（[[OPKV-MLSys26|OPKV]]、[[FlexiCache-MLSys26|FlexiCache]]、[[SkipKV-MLSys26|SkipKV]]）**：把非关键 KV 放 CPU/DRAM 按需召回；需处理 iteration–layer 时间错配与 page 级 I/O 放大。
- **语义布局 / 检索（[[IceCache-arXiv26|IceCache]]、[[MAC-Attention-MLSys26|MAC-Attention]]）**：按 query 相似性复用 attention summary 或重排 page；依赖 decode 流时间冗余或 key embedding 近邻假设。
- **分层存储 / 跨节点传输（[[MSA-arXiv26|MSA]]、[[fabric-lib-MLSys26|fabric-lib]]、[[SuperInfer-MLSys26|SuperInfer]]）**：HBM → Grace DRAM → host → SSD/远端；带宽与 vendor lock-in 是部署关键（[[fabric-lib-MLSys26|fabric-lib]] 关注 EFA/ConnectX 碎片化）。

## 引用本概念的论文

- [[Transformer-NeurIPS17|Attention Is All You Need]] — scaled dot-product attention 定义了 K/V 数据结构，KV cache 是其推理侧自然推论
- [[vLLM-SOSP23|vLLM]] — 测量 KV 低利用率并提出 [[PagedAttention]] 分页管理
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 1M context 下 CSA+HCA 把 KV 压到 V3.2 的 10%，异构 KV + on-disk storage
- [[fabric-lib-MLSys26|fabric-lib]] — disaggregated inference 的 page-wise KV transfer over EFA & ConnectX
- [[FluxMoE-arXiv26|FluxMoE]] — expert paging 腾 HBM 给 KV cache，Qwen3-Next-80B 上 3.0× over vLLM
- [[OPKV-MLSys26|OPKV]] — recallable sparsity plugin 接入 PagedAttention，高 batch 吞吐 1.3–1.8×
- [[SuperInfer-MLSys26|SuperInfer]] — DuplexKV 全双工 KV rotation 修复 GH200 C2C 低利用率
- [[IceCache-arXiv26|IceCache]] — DCI-tree 语义 page 聚类 + query-aware retrieval，36k context 99.0% full-cache accuracy
- [[MAC-Attention-MLSys26|MAC-Attention]] — decode 复用 attention summary，KV 访问最高减 99%
- [[MoE-nD-arXiv26|MoE-nD]] — per-layer routing eviction，136 MB 达 14× compression 匹配 1.9 GB baseline
- [[Stream2LLM-MLSys26|Stream2LLM]] — streaming prompt 用 LCP 选择性失效 KV block，RAG 场景 TTFT 最多 11×
- [[GhostServe-MLSys26|GhostServe]] — erasure-coded parity checkpoint 保护流式 KV，省 75% 内存
- [[BreakingTheIce-MLSys26|BreakingTheIce]] — vLLM 启动 KVCache profiling；MoE routing 使 profiling 偏离 dense 线性规律
- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — persistent/paged KV 与 tiered offloading 的系统级 trade-off 分析
- [[SkipKV-MLSys26|SkipKV]] — CoT 句子级 KV eviction + steering，2× 压缩 accuracy 最高 +26.7%
- [[FlexiCache-MLSys26|FlexiCache]] — per-head 时序稳定性分层，stable head GPU 只留 top-K
- [[Kitty-MLSys26|Kitty]] — 2-bit KV + channel-wise INT4，内存近 8×、吞吐 2.1–4.1×
- [[CRAFT-MLSys26|CRAFT]] — expert replication 挤占 GPU memory，影响 KV 容量与 batch 并发
- [[MorphServe-MLSys26|MorphServe]] — layer swap 释内存后弹性扩 KV，峰值超全精度 32.97%
- [[SpanQueries-MLSys26|SpanQueries]] — span query IR 优化跨请求 KV 局部性，TTFT 10–20×
- [[ContextPilot-MLSys26|ContextPilot]] — context block 对齐/去重提升 prefix hit，长上下文 prefill 1.5–3×
- [[SparseSpec-MLSys26|SparseSpec]] — dynamic KV manager 激进提并发，OOM 时 chunk-wise offload
- [[SHIP-MLSys26|SHIP]] — weights+KV 全放 on-chip SRAM，两级 prefix cache
- [[RaidServe-MLSys26|RaidServe]] — cyclic placement 均衡 irregular TP 下 KV；host backup 恢复 41.5× 快于 recompute
- [[MSA-arXiv26|MSA]] — KV compression + tiered storage 让 100M token 推理可行
- [[TeleRAG-MLSys26|TeleRAG]] — RAG pipeline 中 GPU IVF retrieval 与 KV 争用显存

## 已知局限 / 开放问题

- 跨节点 KV transfer 的 vendor lock-in 与 sharding 不一致（GQA/MLA）仍是 [[fabric-lib-MLSys26|fabric-lib]] 关注的痛点
- sparse/compressed KV 与 exact attention 质量之间的 trade-off 未完全解决；recallable sparsity 与 [[Continuous-Batching]] iteration 粒度仍可能冲突
- 异构内存层次（HBM / Grace DRAM / host / SSD / 远端）的 placement 策略与 SLO-aware 调度仍在演进
- speculative decoding rejection 时 synced KV block 失效前提需重证（[[SuperInfer-MLSys26|SuperInfer]] 的 eager rotation 假设）