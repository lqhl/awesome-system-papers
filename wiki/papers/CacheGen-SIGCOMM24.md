---
type: paper
name: CacheGen
full_title: "CacheGen: KV Cache Compression and Streaming for Fast Large Language Model Serving"
authors: [Yuhan Liu, Hanchen Li, Yihua Cheng, Siddhant Ray, Yuyang Huang, Qizheng Zhang, Kuntai Du, Jiayi Yao, Shan Lu, Ganesh Ananthanarayanan, Michael Maire, Henry Hoffmann, Ari Holtzman, Junchen Jiang]
venue: SIGCOMM
year: 2024
tags: [kv-cache, compression, streaming, network, llm-serving]
source_pdf: "[[sigcomm24-liu-cachegen.pdf]]"
source_md: "[[sigcomm24-liu-cachegen]]"
---

# CacheGen: KV Cache Compression and Streaming for Fast Large Language Model Serving (SIGCOMM 2024)

> **一句话总结**：KV cache 在跨节点复用时需要网络传输，但原始 tensor 体积庞大（10s GB）。CacheGen 用自定义量化 + 算术编码把 KV cache 编码成紧凑 bitstream（3.5-4.3× 压缩），并做自适应 streaming——按网络带宽动态选每 chunk 的压缩级别，保证 SLO 内的延迟和高质量。TTFT 降 3.2-3.7×，且可与 H2O/LLMLingua 等 context pruning 方法叠加。

## 问题

当 KV cache 用于跨请求复用时，它不一定在本地 GPU 内存中——可能在另一台机器的存储服务上。从远端 fetch 整个 KV cache 的**网络延迟**可以高达 100ms 到 10s+（取决于 context 长度和带宽）。已有的 KV cache 优化（quantization / token dropping）目标是 GPU 显存 footprint，不解决传输大小问题。CacheGen 是**第一个聚焦 KV cache 传输时大小优化**的工作。

## 核心方法

**1. KV cache encoding**：不做传统 tensor quantization（保留 tensor shape），而是把 KV cache 编码为紧凑 bitstream：

- 利用 KV cache 的分布特性：**locality across nearby tokens**（相邻 token 的 KV 高度相关）、**per-layer sensitivity**（不同层对压缩的敏感度不同）
- Custom quantization scheme + **arithmetic coding**，实现远超 uniform quantization 的压缩比
- GPU-based decoder 做 decompression，与传输 pipeline 重叠

**2. KV cache streaming**：类似视频 streaming 的自适应传输：

- Context 被切成多个 chunk，每个 chunk 的 KV 按多个压缩级别预编码
- 传输时根据实时带宽逐 chunk 自适应选压缩级别——高带宽时低压缩（高质量），低带宽时高压缩（保 SLO）
- 极端低带宽时 fallback 到传原始 text chunk（让 LLM 本地 recompute KV）

## 关键结果

- KV cache size **降 3.5-4.3×**（vs 8-bit quantization baseline）
- TTFT（含传输 + prefill）**降 3.2-3.7×**，相比 8-bit quantization 仍降 1.67-1.81×
- 与 H2O token dropping 叠加后进一步 **降 3.3-4.2×** 带宽
- 在 Mistral-7B / Llama-7B-70B 上测试，LongChat / GovReport / QMSum 等长 context 数据集
- 近乎无损的生成质量（F1 / perplexity）

## 相关

- **相关概念**：[[KV-Cache]]、[[Prefix-Caching]]、[[Quantization]]
- **同类系统**：H2O、LLMLingua、StreamingLLM（CPU-GPU KV offloading 方向）
- **后续工作**：[[CacheBlend-EuroSys25|CacheBlend]]（multi-chunk KV 复用）、[[LMCache-arXiv25|LMCache]]（全栈 KV cache 层，CacheGen 的编码技术被集成）
- **作者线**：Yuhan Liu（第一作者）、Kuntai Du、Junchen Jiang — UChicago LMCache 团队
- **同会议**：SIGCOMM 2024
