---
type: paper
name: SHIP
full_title: "SHIP: SRAM-Based Huge Inference Pipelines for Fast LLM Serving"
authors: [Andrew Bitar, Aravind Vellora Vayalapra, Baorui Zhou, Matt Boyd, Charlie Wang, "et al."]
venue: MLSys
year: 2026
tags: [llm-serving, sram, groq, pipeline-parallelism, low-latency]
source_pdf: "[[7647966b7343c29048673252e490f736.pdf]]"
source_md: "[[7647966b7343c29048673252e490f736]]"
---

# SHIP: SRAM-Based Huge Inference Pipelines for Fast LLM Serving (MLSys 2026)

> **一句话总结**：Groq 把 LPU 上 weights+KV 全放 on-chip SRAM，经 QuadFour 拓扑把数千芯片 pipeline/tensor 并行起来，配合 dynamic chunked prefill、fused context-batch 与两级 prefix cache，在 OpenRouter 实测端到端延迟领先次快 provider，日服务数百亿 token。

## 问题

LLM serving 在 prefill（compute-bound）与 decode（memory-bound）间拉扯 SLO：HBM GPU 要靠大批次抬高 OI，但 reasoning 模型 10× 更长生成、P:D 比持续波动，chunked prefill 仍难同时稳住 TTFT 与 TPOT。SRAM 带宽远高于 HBM，但容量极小，必须把模型切到上千芯片且控制 collective 延迟。

## 核心方法

**LPU + SHIP 架构**：compiler 静态调度、deterministic C2C（300 ns/hop）；QuadFour 拓扑（节点内 K8 clique，跨节点 32 link）支持 TP+PP 异构分区；72-LPU 分区直径 3 hop、16.56 GB SRAM。

**内存管理**：自研 [[PagedAttention]]（128–512 token page）；prefix cache 用 SRAM+host DRAM 两级（gpt-oss-120B 72 节点可达 51 TB DRAM cache pool）；[[Speculative-Decoding]] 作额外 PP stage 减 KV 占用。

**动态 pipeline**：dynamic chunked prefill（1–2 token chunk 即可饱和 self-attention）；fused context-batch 消除长短 context 混批 bubble；decode 优先 + capacity-filling prefill；MoE 小 batch 下 per-token expert 执行保 pipeline 平衡。

## 关键结果

- Groq Cloud 一个月数据：多模型端到端延迟优于 OpenRouter 上各模型次快 provider（Fig. 1）
- Qwen3-235B-A22B vs [[SGLang|SGLang]] on B200：SHIP 在中高 P:D 维持稳定 system throughput；production traffic 下 ot/s/u 绝对值显著高于 SGB200，TPOT 更稳
- Collective：8/64 LPU 上 32KiB AllReduce 达 50% 带宽饱和；MatMul+AllReduce 可 cycle 级 overlap
- 系统：LPU 每卡 388 W vs B200 DGX 1788 W/GPU；C2C 小 tensor 延迟 sub-µs vs NCCL 1–10 µs

## 相关

- **相关概念**：[[PagedAttention]]、[[KV-Cache]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Chunked-Prefill]]、[[Prefix-Caching]]、[[Speculative-Decoding]]、[[MoE]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Google TPU serving 回顾
- **同会议**：[[MLSys-2026]]
- **对比**：SRAM low-batch latency-first vs HBM high-batch throughput