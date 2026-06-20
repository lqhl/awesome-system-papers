---
type: paper
name: TokenWeave
full_title: "TOKENWEAVE: EFFICIENT COMPUTE-COMMUNICATION OVERLAP FOR DISTRIBUTED LLM INFERENCE"
authors: [Microsoft Research authors]
venue: MLSys
year: 2026
tags: [tensor-parallel, llm-inference, allreduce, overlap, nvlink]
source_pdf: "[[e4da3b7fbbce2345d7772b0674a318d5.pdf]]"
source_md: "[[e4da3b7fbbce2345d7772b0674a318d5]]"
---

# TOKENWEAVE: EFFICIENT COMPUTE-COMMUNICATION OVERLAP FOR DISTRIBUTED LLM INFERENCE (MLSys 2026)

> **一句话总结**：[[Tensor-Parallelism|Tensor-Parallel]] serving 在 8×H100 上 [[AllReduce]] 仍占 **9–23%** 且小 batch（~1K tokens）overlap 因 wave quantization 不划算；TokenWeave 用 smart-split + **AllReduce–RMSNorm** 融合（NVSHARP/Multimem **2–8 SM**）在 **1024** token 起达 **1.28×** 延迟、ShareGPT **1.19×** 吞吐，部分场景优于「无通信」理想下界。

## 问题与动机

[[LLM]] TP 推理每 block 两次 AllReduce；NVLink 已优化仍 **9–23%** 延迟（Llama-3.3-70B 等）。[[RMSNorm]] 另占 **4–9%**。Flux/TileLink 等 overlap 需大 batch（8K+）才划算；[[vLLM]]/[[SGLang]]/[[TensorRT-LLM]] 默认不开 overlap，因低延迟 serving batch 小，拆分 GEMM 反而更慢。

TokenWeave 首个在 **≥1024 tokens** 迭代高效 overlap TP comm 的系统。

## 关键观察 / 隐含假设

- **观察 1：小 tensor 上 RS+AG 拆分 AllReduce 带宽差（Fig. 4），但 smart-split 控制 wave 数可降拆分税（Fig. 9）。**
  - **依赖假设**：132 SM H100 上 132-CTA「满波」split 最优。
  - **可能失效场景**：不同 GPU SM 数需重调 split 策略。

- **观察 2：AllReduce 后立即 RMSNorm 可融合，且 Multimem 通信用 **2–8 SM** 即饱和带宽，余 SM 可跑另一 split 的 GEMM。**
  - **依赖假设**：Hopper/Blackwell NVSHARP/Multimem 可用（vLLM-Multimem baseline）。
  - **可能失效场景**：无 multimem 硬件退化需 fallback。

- **观察 3：融合 kernel 相对顺序 AR+RMSNorm **1.34–1.39×**（64–32K tokens），接近纯 AR 时间。**
  - **依赖假设**：RMSNorm 内存 bound，融合减 HBM 往返。
  - **可能失效场景**：非标准 hidden size 未优化。

- **假设 1**：≥4K tokens 时 TokenWeave 可超过「无通信」counterfactual（因同时优化 RMSNorm）。**
  - **证据强度**：**强**——Fig. 2 实测。

## 核心方法

**Smart-splitting**：按 CTA 波次将 batch 拆两 split，一 split 满波（132 CTA），overlap 另一 split 计算与当前 split AR+RMSNorm。

**Fused AllReduce–RMSNorm2**：单 kernel 完成通信+归一化；极少 SM 跑 comm。

**vLLM-V1 集成**：co-located prefill/decode；disaggregated 下小 decode 仍受益融合，大 prefill 受益 full overlap。

## 设计取舍

- **融合 vs 纯 overlap**：融合对小 batch 仍有效；大 batch 双管齐下。
- **少 SM comm vs 多 SM comm**：释放算力 overlap，极端拥塞时可能需调 SM 数。
- **vs TileLink**：TokenWeave 在 2K tokens 仍赢，TileLink 反而变慢。
- **边界条件**：8×H100 DGX；bf16 hidden 8192 等。

## 实验与结果

- 延迟：**1.28×** peak（vs vLLM-Multimem）；**1.2×** @ 1K tokens。
- 吞吐：ShareGPT **1.19×**、arXiv **1.15×**。
- ≥4K：优于 vLLM-nocomm（无通信理想）。
- 融合 kernel Table 1：**1.34–1.39×** 各序列长。

## Critical Analysis

### 论证链条

小 batch overlap 不划算根因是拆分+忽略 RMSNorm → smart-split+融合+少 SM comm → 1024 起有效，链条完整。

### 假设压力测试

跨节点 TP（IB）multimem 不适用时收益未知。与 [[TokenWeave]] 名不同 [[Disaggregation]] 分离部署的 comm 形态变化。

### 实验可信度

产线 vLLM 集成；多模型 trace。缺：70B+ 多节点、MoE EP 混合。

### 系统性缺陷

论文未讨论与 [[DP]]/[[EP]] 组合、故障降级路径。SM 占用与 concurrent kernel 争用未长期压测。

## 局限与 Future Work

- **局限 1**：强依赖 NVSHARP/Multimem 硬件代际。
- **局限 2**：跨节点 TP 未验证。
- **Future work 1**：IB 上 fused AR 变体 + smart-split 联合 profile。
- **Future work 2**：与 [[BOUTE]] 异构集群 TP shard 协同。

## 相关

- **相关概念**：[[Tensor-Parallelism|Tensor-Parallel]]、[[AllReduce]]、[[RMSNorm]]、[[NVLink]]
- **同类系统**：Flux、TileLink、[[vLLM]]
- **同会议**：[[MLSys-2026]]