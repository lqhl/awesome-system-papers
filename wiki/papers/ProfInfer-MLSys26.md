---
type: paper
name: ProfInfer
full_title: "ProfInfer: An eBPF-Based Fine-Grained LLM Inference Profiler"
authors: [Bohua Zou, Debayan Roy, Dhimankumar Yogesh Airao, Weihao Xu, Binqi Sun, "et al."]
venue: MLSys
year: 2026
tags: [profiling, ebpf, llm-inference, edge, llama-cpp]
source_pdf: "[[6ea9ab1baa0efb9e19094440c317e21b.pdf]]"
source_md: "[[6ea9ab1baa0efb9e19094440c317e21b]]"
---

# ProfInfer: An eBPF-Based Fine-Grained LLM Inference Profiler (MLSys 2026)

> **一句话总结**：用 eBPF uprobe 非侵入挂到 llama.cpp 的 token/graph/operator 三层，结合 PMC 与 ProfDAG/ProfTime/ProfStat 三种视图，decode 开销 < 4%（libbpf 1.7%），可诊断 [[MoE|MoE]] expert 激活与 backend 异构。

## 问题

On-device LLM 推理（llama.cpp 等）缺乏 operator-level、非侵入式 profiler；现有方案要重编译或只给 throughput。连 prefill vs decode 的 memory/compute bound 都难判断。

## 核心方法

**Tracer**：libbpf/BCC attach `llama_decode`、`ggml_backend_graph_compute_async`、`ggml_compute_forward` 等；按 QoS 动态开关 probe；kernel handler 解析 ggml_tensor 得 op 类型与维度。

**PMC**：per-operator 读 l3d_cache_refill、mem_access、stall cycles 等，量化 DRAM 流量与 bound。

**Analyzer**：ProfDAG 重建算子 DAG+带宽标注；ProfTime 转 Chrome trace；ProfStat 跨 token/op-type/expert 统计。MoE 通过 `ggml_compute_forward_mul_mat_id` 读 top-k expert ID。

## 关键结果

- Decode speed 下降：BCC 2.8–4%，libbpf 最低 1.7%；probe CPU load 可忽略
- 对比：llama.cpp 内置 graph dump 13% overhead，ONNX Runtime profiler ~8%
- 平台：Orange Pi 5 Pro/Plus、Ubuntu、OpenHarmony

## 相关

- **相关概念**：[[KV-Cache]]、[[MoE]]、[[Speculative-Decoding]]
- **同类系统**：ONNX Runtime profiler、TensorRT profiler
- **同会议**：[[MLSys-2026]]