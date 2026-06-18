---
type: paper
name: MorphServe
full_title: "MorphServe: Efficient and Workload-Aware LLM Serving via Runtime Quantized Layer Swapping and KV Cache Resizing"
authors: [Zhaoyuan Su, Zeyu Zhang, Tingfeng Lan, Zirui Wang, Haiying Shen, "et al."]
venue: MLSys
year: 2026
tags: [llm-serving, quantization, kv-cache, elastic, workload-aware]
source_pdf: "[[fc490ca45c00b1249bbe3554a4fdf6fb.pdf]]"
source_md: "[[fc490ca45c00b1249bbe3554a4fdf6fb]]"
---

# MorphServe: Efficient and Workload-Aware LLM Serving via Runtime Quantized Layer Swapping and KV Cache Resizing (MLSys 2026)

> **一句话总结**：MorphServe 在 runtime 按负载 **token 粒度形变**模型——低敏感度层在 FP16/INT4 间异步切换，释放显存弹性扩 [[KV-Cache]]；相比全精度服务平均 SLO 违规降 **92.45%**、P95 TTFT 改善 **2.2–3.9×**，低负载恢复全精度无持久精度损失。

## 问题

Azure / BurstGPT 等真实 workload 高度突发。静态方案两难：

- **全精度 [[vLLM]] 式服务**：尖峰时内存耗尽、queueing 暴涨，TTFT SLO（2s）破裂
- **静态 [[Quantization]]**（AWQ INT4）：低负载也承受持久精度损失
- **KV compression/eviction**：固定 heuristic，难随 workload 调整，GQA/MLA 兼容性差

## 核心方法

**反馈闭环**：Serving Monitor → Morphing Controller → Morphing Executor

**LayerSwapper**：
- 离线 LTS/LRS/MDS 综合得 Layer Importance Score（LIS = 0.25·LTS + 0.25·LRS + 0.5·MDS）
- FP16/INT8/INT4/INT3 变体预载 pinned CPU + kernel 预编译；异步 CUDA stream in-place swap（INT4 ~6ms，与 decode overlap）
- **Token 级**：单 request decoding 中途可换层，仅尾部 token 降精度

**KVResizer**：
- 扩展 [[PagedAttention]]，动态 attach/release KV blocks
- 压力高时先 swap 层释内存再扩 KV；缓解 prefill queueing 与 decode preemption

基于 SwiftLLM（~2200 行 Python + 500 行 C++/CUDA）。

## 关键结果

- 平均 SLO 违规 **−92.45%**；P95 TTFT **2.2×–3.9×**（accuracy mode）vs FP16
- vs AWQ INT4：F1/ROUGE-L 退化减少 **88.85%**；内存利用率 **+29.29%**
- vs LLM-PQ：accuracy gap 平均闭合 **41.3%**（最高 **82.3%**），latency 可比或更低
- vs PyramidKV：P95 TTFT **1.73×–2.4×** 更快且精度更高
- 峰值 KV 容量可超全精度上限 **32.97%**；吞吐饱和点延迟 **1.83×**
- Vicuna-7B / Llama2-7B / Llama3-8B / CodeLlama-34B，BurstGPT + Azure trace

## 相关

- **相关概念**：[[Quantization]]、[[KV-Cache]]、[[PagedAttention]]、[[Flash-Attention]]、[[Continuous-Batching]]
- **同类系统**：[[vLLM]]、Orca、Sarathi-Serve、AWQ、GPTQ、LLM-PQ、PyramidKV
- **同会议**：[[MLSys-2026]]