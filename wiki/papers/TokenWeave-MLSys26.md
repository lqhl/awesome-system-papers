---
type: paper
name: TokenWeave
full_title: "TOKENWEAVE: EFFICIENT COMPUTE-COMMUNICATION OVERLAP FOR DISTRIBUTED LLM INFERENCE"
authors: [Raja Gond, Nipun Kwatra, Ramachandran Ramjee]
venue: MLSys
year: 2026
tags: [tensor-parallel, llm-inference, allreduce, overlap, nvlink]
source_pdf: "[[e4da3b7fbbce2345d7772b0674a318d5.pdf]]"
source_md: "[[e4da3b7fbbce2345d7772b0674a318d5]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# TOKENWEAVE: EFFICIENT COMPUTE-COMMUNICATION OVERLAP FOR DISTRIBUTED LLM INFERENCE (MLSys 2026)

> **一句话总结**：TokenWeave 用 smart splitting 与 fused [[AllReduce]]–[[RMSNorm]] 在 8×H100 上重叠 [[Tensor-Parallelism|TP]] inference 的计算和通信；相对 vLLM-Multimem，dense models 从 1K tokens 起获得 1.16–1.28× latency speedup，ShareGPT throughput 最高为 1.19×（§5.2.1–5.2.2，Fig. 11/13）。

## 问题与动机

[[LLM]] TP 推理每 block 两次 AllReduce；NVLink 已优化仍 **9–23%** 延迟（Llama-3.3-70B 等）。[[RMSNorm]] 另占 **4–9%**。Flux/TileLink 等 overlap 需大 batch（8K+）才划算；[[vLLM]]/[[SGLang]]/[[TensorRT-LLM]] 默认不开 overlap，因低延迟 serving batch 小，拆分 GEMM 反而更慢。

TokenWeave 首个在 **≥1024 tokens** 迭代高效 overlap TP comm 的系统。

## 关键观察 / 隐含假设

- **观察 1：小 tensor 上 RS+AG 拆分 AllReduce 带宽差（Fig. 4），但 smart-split 控制 wave 数可降拆分税（Fig. 9）。**
  - **依赖假设**：132 SM H100 上 132-CTA「满波」split 最优。
  - **可能失效场景**：不同 GPU SM 数需重调 split 策略。

- **观察 2：AllReduce 后立即 RMSNorm 可融合；实现为 fused kernel 分配 2–8 SM，Fig. 10 显示 8 SM 在多数被测配置接近最优，余下 SM 可执行另一 split 的 GEMM。**
  - **依赖假设**：Hopper/Blackwell NVSHARP/Multimem 可用（vLLM-Multimem baseline）。
  - **可能失效场景**：无 multimem 硬件退化需 fallback。

- **观察 3：融合 kernel 相对顺序 AR+RMSNorm 在 64–32K tokens 上达到 1.34–1.39×，接近纯 AR 时间（§4.2–4.3，Table 1）。**
  - **依赖假设**：RMSNorm 内存 bound，融合减 HBM 往返。
  - **可能失效场景**：非标准 hidden size 未优化。

- **假设 1**：大于等于 4K tokens 时，TokenWeave 可超过不产生正确输出的 vLLM-nocomm counterfactual，因为它还优化 RMSNorm；这不是可部署 baseline 或理论下界（Fig. 2）。
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

- **Prefill iteration latency**：相对 optimized vLLM-Multimem，dense models 从 1K tokens 起达到 1.16–1.28×；Llama-3.3-70B 在 1K 为 1.2×、峰值 1.28×（§5.2.2，Fig. 13/2；8×H100、vLLM 0.8.5 V1、prefill-only single forward）。Mixtral 在 1K/2K 开 full overlap 有净开销，4K 起才启用 full overlap。
- **Serving throughput**：相对 vLLM-Multimem，ShareGPT 与 arXiv trace 的最高 throughput 分别为 1.19× 与 1.15×（§5.2.1，Fig. 11；8×H100、hybrid prefill/decode + chunked prefill，dense chunk 2K、Mixtral 4K，忽略 CPU detokenization）。
- **Fused kernel**：相对顺序 Multimem AR + RMSNorm，fused AllReduce–RMSNorm 在 64–32K tokens 上为 1.34–1.39×，几乎达到 AR-only；简单 RS+RMSNorm+AG 在 512–8K 反而更慢（§4.2–4.3，Table 1；hidden 8192、bf16、8×H100 microbenchmark）。
- **TileLink comparison**：Llama-3.3-70B 单层、batch 1 下，TokenWeave 在 1K tokens 为 1.20×、最高 1.35×；TileLink 在小 sequence 有净开销，4K 起改善并约在 1.2× 饱和（§5.2.3，Fig. 14；8×H100；TileLink 未集成 serving stack）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| TokenWeave 从 1K tokens 起降低 dense-model TP iteration latency | §5.2.2, Fig. 13/2 | prefill-only；dense models；8×H100；vLLM-Multimem；Mixtral threshold 不同 | strong |
| TokenWeave 在 ShareGPT/arXiv 上提高 serving throughput | §5.2.1, Fig. 11 | 8×H100；vLLM-V1；chunked prefill；忽略 CPU detokenization | strong |
| Fused AllReduce–RMSNorm 比顺序执行快 1.34–1.39× | §4.2–4.3, Table 1 | hidden 8192；bf16；64–32K tokens；8×H100 microbenchmark | strong |
| TokenWeave 在单层小 request 上优于 TileLink | §5.2.3, Fig. 14 | Llama-3.3-70B；batch 1；8×H100；非端到端比较 | medium |

## Critical Analysis

### 论证链条

小 batch overlap 不划算根因是拆分+忽略 RMSNorm → smart-split+融合+少 SM comm → 1024 起有效，链条完整。

### 假设压力测试

跨节点 TP（IB）multimem 不适用时收益未知。[[Disaggregation]] 分离部署的通信形态也会变化。

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
