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

> **一句话总结**：MorphServe 在 runtime 按负载 token 粒度**形变**模型——把低敏感度层在 FP16 / INT4 之间异步切换，同时把释放的显存弹性扩给 [[KV-Cache]]；相比全精度服务平均 SLO 违规降 **92.45%**、P95 TTFT 改善 **2.2-3.9×**，且低负载时回到全精度无持久精度损失。

## 问题

真实 LLM workload（Azure、BurstGPT）高度突发。静态方案无解：

- **全精度服务**：流量尖峰时 GPU 内存耗尽、queueing 暴涨，TTFT SLO（2s）破裂
- **静态 quantization**（[[vLLM]] + AWQ INT4）：**持久**精度损失——即使低负载也无法恢复全精度
- **Over-provisioning**：低谷期资源浪费；edge 部署不可弹性
- **KV compression/eviction**：用固定 heuristic，不随 workload 调整，难兼容 GQA/MLA

## 核心方法

三组件反馈闭环：**Serving Monitor** → **Morphing Controller** → **Morphing Executor**。

**LayerSwapper：运行时层交换**
- **离线 profiling** 构造 swap 顺序：综合 Layer Transformation Sensitivity (LTS)、Layer Replacement Sensitivity (LRS)、Model Degradation Sensitivity (MDS) 得 Layer Importance Score (LIS = 0.25·LTS + 0.25·LRS + 0.5·MDS)；cos-similarity 优于 L2
- 所有精度变体（FP16/INT8/INT4/INT3）**预加载**到 pinned CPU 内存；对应 kernel 预编译
- **Asynchronous in-place swapping**：用独立 CUDA stream 搬运，与 decoding overlap；INT4 变体 ~6ms 完成，TPOT 几乎无影响
- **Token 级粒度**：单个 request 的 decoding 内也可中途换层，早期 token 全精度、压力期少量 token 降精度，压力消退后再回 FP16

**KVResizer：弹性 KV cache**
- 扩展 [[PagedAttention]]，动态 attach/release KV blocks，全异步
- 触发逻辑：queue 长度或等待时间超阈值时先触发 layer swap 释放 GPU 内存，再扩 KV 缓存；压力消退时反向
- Prefill 期缓解 queueing → TTFT；decode 期避免 preemption / KV swap → TPOT

## 关键结果

- **平均 SLO 违规降低 92.45%**
- P95 TTFT 改善 **2.2×–3.9×**（accuracy mode），**3.4×–19.5×**（performance mode），相比 FP16 baseline
- 相比 AWQ INT4：F1/Rouge-L 退化减少 **88.85%**，内存利用率 +**29.29%**
- KV 缓存容量在峰值时可**超出全精度上限 32.97%**，queueing 延迟降 3.8×
- Pareto 最优：在 Vicuna-7B / Llama2-7B / Llama3-8B / CodeLlama-34B，BurstGPT/Azure trace，GovReport/Multi-News/QMSum/DuReader 数据集上持续领先
- 基于 SwiftLLM（vLLM 轻量复刻）；约 2200 行 Python + 500 行 C++/CUDA

## 相关

- **相关概念**：[[Quantization]]、[[KV-Cache]]、[[PagedAttention]]、[[Flash-Attention]]、[[Continuous-Batching]]
- **同类系统**：[[vLLM]]、Orca、Sarathi-Serve、FastServe、AWQ、GPTQ、MARLIN、LayerSkip、FlexiDepth
- **同会议**：[[MLSys-2026]]
