---
type: paper
name: MAC-Attention
full_title: "MAC-Attention: A Match-Amend-Complete Scheme for Fast and Accurate Attention Computation"
authors: [Jinghan Yao, Sam Ade Jacobs, Walid Krichene, Masahiro Tanaka, Dhabaleswar K Panda]
venue: MLSys
year: 2026
tags: [long-context, attention, kv-cache, inference, rope]
source_pdf: "[[5ef059938ba799aaa845e1c2e8a762bd.pdf]]"
source_md: "[[5ef059938ba799aaa845e1c2e8a762bd]]"
---

# MAC-Attention: A Match-Amend-Complete Scheme for Fast and Accurate Attention Computation (MLSys 2026)

> **一句话总结**：通过 pre-RoPE 查询匹配复用 attention summary、在边界 band 修正并 log-domain merge tail，MAC-Attention 在 128K 上下文将 KV 访问减最多 99%、per-token 延迟降 60%+、attention 阶段加速 ≥14.3×（最高 ~46×），端到端最高 2.6×，同时保持 full attention 质量。

## 问题

长上下文 LLM 解码是 IO-bound：每步都要重读不断增长的 [[KV-Cache]]。[[Flash-Attention]]、[[PagedAttention]] 等 IO-aware kernel 和 [[vLLM]] 式内存管理缓解了浪费，但大 prefix 的重复读取仍是主瓶颈。压缩（低秩、[[Quantization]]）和选择/驱逐会降低保真度或限制可访问 token，在 delayed recall、长生成任务上掉点明显。

## 核心方法

**Match–Amend–Complete (MAC)**：training-free、model-agnostic，在单条 decoding stream 内复用语义相似 query 的 attention 计算，保留全序列访问。

1. **Match**：在 size-K（≤1024）ring buffer 中对 **pre-RoPE** query 做 L2 匹配（非 post-RoPE，避免 RoPE 相位破坏相似性）
2. **Amend**：复用缓存的 rectified prefix summary $AS^{(p)}_{1:p-r}$，只重算边界 band $[p-r+1, p]$ 修正近似误差
3. **Complete**：对 tail $[p-r+1, m]$ 做 fresh attention，用 numerically stable log-domain merge 融合

命中时 compute/bandwidth 与序列长度无关（O(1)）；未命中则 fallback full attention。可与 IO-aware kernel、[[PagedAttention]]、MQA/GQA 组合。

## 关键结果

- LongBench v2 (120K)、RULER (120K)、LongGenBench (16K)：**KV 访问最多减 99%**
- 128K：**per-token 延迟降 60%+**；attention 阶段 **≥14.3×**（256K 设置下最高 ~46×）
- LLaMA 端到端生成最高 **2.6×**；相对 FlashInfer 保持 full-attention 质量
- 相比 FlashInfer baseline，accuracy–KV budget 曲线贴近 full attention

## 相关

- **相关概念**：[[KV-Cache]]、[[Flash-Attention]]、[[PagedAttention]]、[[Attention]]、[[Quantization]]
- **同类系统**：[[vLLM]]、FlashInfer、prefix caching
- **同会议**：[[MLSys-2026]]