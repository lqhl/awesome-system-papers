---
type: paper
name: FlexiCache
full_title: "FlexiCache: Leveraging Temporal Stability of Attention Heads for Efficient KV Cache Management"
authors: [Nazmul Takbir, Hamidreza Alikhani, Nikil Dutt, Sangeetha Abdu Jyothi]
venue: MLSys
year: 2026
tags: [kv-cache, sparse-attention, long-context, hierarchical-memory, inference]
source_pdf: "[[76dc611d6ebaafc66cc0879c71b5db5c.pdf]]"
source_md: "[[76dc611d6ebaafc66cc0879c71b5db5c]]"
---

# FlexiCache: Leveraging Temporal Stability of Attention Heads for Efficient KV Cache Management (MLSys 2026)

> **一句话总结**：发现 KV head 的 top-K page 集合存在跨 step temporal stability 且 model-intrinsic，按 stable/unstable 分别处理——稳定头仅 top-K 驻 GPU 其余卸载到 host，不稳定头全驻 GPU，在 vLLM 上长上下文 GPU 显存降 70%、吞吐 1.38-1.55×、延迟 1.6-2.1× 改善。

## 问题

长上下文 + 长生成推理中，[[KV-Cache]] 增长线性消耗 GPU 显存，限制 batch size 进而限制 throughput。现有稀疏注意力方法各有缺陷：StreamingLLM 静态窗口不管 context 依赖；SnapKV、MorphKV 永久丢弃 token，长 generation 中丢弃的内容可能后来变重要；Quest 每步重新选 top-K 不减显存；LServe 用 DuoAttention 把半数 head 改 streaming 永久丢 KV 在长-长场景会降准确率。

## 核心方法

**关键观察**：KV head 对 top-K page 集合的选择存在 head-level temporal stability，用 random-corrected overlap (RCO) 量化，同一模型 bottom 25% 最不稳定 head 跨任务高度重合（Llama-3.1-8B 跨 8 任务平均 overlap 0.83），一次性 offline profiling 足够。

FlexiCache 把 head 分成 stable / unstable：
- **Stable head**（75%）：仅 top-K pages 驻 GPU 其余卸载到 host；每 16 步重排一次，只把新晋升的 top-K page fetch 回来。
- **Unstable head**（25%）：全部 KV 驻 GPU 每步重排，无 host 传输。

page 重要性 score 用 min/max key 向量的点积上界（类 Quest），min-max 向量存独立的 MinMax cache 常驻 GPU。实现要点：UVA 自定义 CUDA kernel 绕过 CPU gather/scatter、per head-layer block table + dirty tracking 只传改动段、physical block reuse 避免 churn、null block 保持 dense layout、CDU offload/reload 用低优先级 stream 并分块与 compute 重叠。

## 关键结果

- 基于 vLLM Triton Flash-Decoding，H100 94GB 平台。
- LongBench 16 任务 + L-Eval 长上下文长生成任务上保持 **99% dense accuracy**（Llama-3.1-8B、Mistral-7B-v0.2）。
- L-Eval 上 LServe 掉 6%，FlexiCache 在同等 token budget 下保持 99%。
- 长请求 GPU 显存降 **up to 70%**；decode kernel 最高 **4× 加速**（大 batch）。
- 离线吞吐改善 **1.38-1.55×**（Llama）、1.44-1.46×（Mistral）。
- 在线 TPOT 在 0.4 req/s 改善 **2.1×**（1024 budget）。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Attention]]
- **同类系统**：[[vLLM]]、Quest、LServe、SnapKV、StreamingLLM
- **同会议**：[[MLSys-2026]]
