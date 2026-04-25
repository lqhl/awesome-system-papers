---
type: paper
name: CacheSlide
full_title: "CacheSlide: Unlocking Cross Position-Aware KV Cache Reuse for Accelerating LLM Serving"
authors: [Yang Liu, Yunfei Gu, Liqiang Zhang, Chentao Wu, Guangtao Xue, et al.]
venue: FAST
year: 2026
tags: [llm-serving, kv-cache, agent, positional-encoding, vllm]
source_pdf: "[[fast2026-liu-yang.pdf]]"
source_md: "[[fast2026-liu-yang]]"
---

# CacheSlide: Unlocking Cross Position-Aware KV Cache Reuse for Accelerating LLM Serving (FAST 2026)

> **一句话总结**：为 agent 场景定义新的 KV cache 复用范式 RPDC（Relative-Position-Dependent Caching）—— 可复用片段保持相对顺序但绝对位置漂移；通过 Chunked Contextual Position Encoding + Weighted Correction Attention + SLIDE 系统层优化（spill-aware、layer-wise decoupling、dirty-page eviction）扩展 [[vLLM]]，实现 3.11–4.3× 延迟降低、3.5–5.8× 吞吐提升。

## 问题

Agent 场景（MemGPT、Reflexion、SWE-Agent、AutoGen）的 prompt 由 system prompt（静态前缀）+ updated prompt（每轮变化）+ fixed prompt（历史/记忆，静态后缀）组成。**关键观察**：updated 段长度变化使后续 fixed 段绝对位置漂移，但相对顺序不变。

已有方案两难：
- **PDC**（PromptCache、ContextCache）只允许在固定绝对位置复用，updated 段长度一变就失效；强行重排 fixed/updated 段会破坏 agent 语义（例如 MemGPT 把最近 memory 放头部以获得更多 attention，SWE-Agent 槽位间存在数据依赖）。
- **PIC**（CacheBlend、EPIC）丢弃绝对位置全部从 0 编码，引入 Positionally Misaligned KV Drift (PMKD)：[[RoPE]] 高位置敏感，prefix shift 1000 token 使 CKSim 余弦相似度跌 > 90%。预选 token 子集重计算无法稳定恢复精度（multi-head 关注模式只在 decode 才显现）。
- 系统层：vLLM/SGLang 同层 KV load/write 串行无法 overlap；spill 到 SSD 用 LRU 而非 dirty-aware，写放大严重。
- Window padding（强制 update 段定长）会丢失关键信息，F1 降 78.1%。

## 核心方法

**RPDC 范式**：保持 cached 与 recompute KV 的相对位置一致，避免绝对位置失配。

**Chunked Contextual Position Encoding (CCPE)**：基于 CoPE（语义边界索引）思想，相邻 token 可共享 position index，使段内/段间 attention 在绝对位移下变化平缓 —— 实测 CKSim 仅降 28%（vs RoPE 90%+）。

**Weighted Correction Attention**：复用 cached KV 时只对极少子集 token 重算 attention，再用学到的权重把 cached 与新算 KV 加权融合，兼顾计算效率与生成质量。

**SLIDE 系统层优化**：
- **Spill awareness**：感知 KV 是否已 spill 到 SSD，调度上层避让；
- **Load–write decoupling (intra-layer)**：打破层内 load-before-write lock，实现 I/O 与 compute overlap；
- **Dirty-page Eviction**：跟踪页面 dirty 状态，避免 spill 时 LRU 误择，降低写放大。

实现：基于 [[vLLM]] KV cache 管理扩展。

## 关键结果

- 延迟降低 3.11–4.3×，吞吐提升 3.5–5.8×（多个 LLM × 多个 agent benchmark）。
- 准确率几乎无损失。
- CCPE 把 prefix shift 1000 token 时的 CKSim 损失从 RoPE 的 > 90% 降到 28%。
- 与 PDC（ContextCache、PromptCache）对比解锁 agent 场景下"非前缀片段"的可复用性；与 PIC（CacheBlend、EPIC）对比避免 PMKD 与 system 层 stall。

## 相关

- **相关概念**：[[KV-Cache]]、[[RoPE]]、[[Prefix-Caching]]、[[PagedAttention]]、[[Agent]]
- **同类系统**：[[vLLM]]、[[SGLang]]、CacheBlend、EPIC、PromptCache、ContextCache、MemGPT
- **同会议**：[[FAST-2026]]
