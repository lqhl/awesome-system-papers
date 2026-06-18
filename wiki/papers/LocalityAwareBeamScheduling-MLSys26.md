---
type: paper
name: LocalityAwareBeamScheduling
full_title: "Locality-Aware Beam Scheduling for Efficient Test-Time Compute with a Consumer-Grade GPU"
authors: [Hsing-Ti Wang, Hung-Tso Shiao, Chia-Lin Yang]
venue: MLSys
year: 2026
tags: [test-time-compute, kv-cache, beam-search, offloading, consumer-gpu]
source_pdf: "[[44f683a84163b3523afe57c2e008bc8c.pdf]]"
source_md: "[[44f683a84163b3523afe57c2e008bc8c]]"
---

# Locality-Aware Beam Scheduling for Efficient Test-Time Compute with a Consumer-Grade GPU (MLSys 2026)

> **一句话总结**：针对 consumer GPU 上 step-wise beam search 的 [[KV-Cache]] 瓶颈，按 inter-token / inter-beam locality 重排 beam 执行顺序，KV 传输量 **>95%** 削减，OPT/LLaMA/Qwen-7B 端到端 **3.4–9.7×** 加速。

## 问题

Test-time compute（step-wise beam search）使每路径独立 [[KV-Cache]]，宽 beam 下 cache 占 GPU 内存 **>70–80%**，layer-wise offloading 导致 I/O stall 占 latency **85%**。此前优化多聚焦权重 offload，忽视 TTC 下 cache 主导的问题。

## 核心方法

**Inter-token locality**：步内按 beam（或 beam group）顺序解码，组内 KV 常驻 GPU 至该步结束，避免 token-by-token 全 beam 交替导致的反复 reload。

**Inter-beam locality**：共享 prefix 的 beam 划入同组，重叠 KV 只传一次；贪心构造 BeamSet，动态查询剩余显存决定 #Beam。

**Balanced grouping + prefetch**：均分 beam 到各组并预取下一组 KV，overlap 传输与计算；GPU stall 从 70–90% 降至 **<15%**。

## 关键结果

- KV cache 传输量较 layer-wise offloading 减少 **>95%**（64 beam 理论 53012→540 GB 量级）
- RTX 4090：OPT-6.7B **3.39–9.72×**、LLaMA-2-7B **3.60–8.74×**、Qwen-7B **4.17–7.99×** E2E 加速
- 32/64 beam 时 KV 占内存 **70%+/80%+**，验证 TTC 新瓶颈

## 相关

- **相关概念**：[[KV-Cache]]、[[Speculative-Decoding]]
- **同类系统**：FlexGen、llama.cpp、DeepSpeed-Inference
- **同会议**：[[MLSys-2026]]