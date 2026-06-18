---
type: paper
name: MoE-Serving-Tax
full_title: "Demystifying the Mixture of Experts Serving Tax"
authors: [Pratyush Patel, Dayeol Lee, Shintaro Iwasaki, Arvind Krishnamurthy]
venue: MLSys
year: 2026
tags: [moe, llm-serving, performance-analysis, expert-parallelism, tensor-parallelism]
source_pdf: "[[fbd7939d674997cdb4692d34de8633c4.pdf]]"
source_md: "[[fbd7939d674997cdb4692d34de8633c4]]"
---

# Demystifying the Mixture of Experts Serving Tax (MLSys 2026)

> **一句话总结**：系统刻画 [[MoE]] 相对 FLOP 等价 dense 模型的「serving tax」：端到端慢 **2–3×**；prefill 受 batch subdivision 与 padding 主导，decode 受 weight amplification 主导，且 routing skew 在 decode 反而可能降税——并提出 balls-bins-buckets 分析框架指导优化。

## 问题

[[MoE]] 承诺「大模型质量、小模型每 token 算力」，但云厂商对同等 activated-parameter 的 MoE 定价常比 dense 高 **2.5–10×**。FLOP 对齐的 dense（DenseFA）看不到 conditional computation 带来的系统开销：更低 arithmetic intensity、[[Expert-Parallelism]] AllToAll、routing 引发的 padding / straggler / 通信失衡。需要可分解、可预测的 tax 模型指导 serving 配置。

## 核心方法

定义 MoE tax τ = T_MoE / T_DenseFA。相对 DenseFA（每 token 同 FLOP）和 DensePA（总参数量对齐下界）对比。

**Baseline tax sources**：
- **GroupGEMM batch subdivision**：每 expert 分到的 token 更少 → prefill 算术强度低于 dense
- **Weight amplification**：decode 需加载 E_active/K 倍 expert 权重，batch 中等时接近 DensePA 延迟
- **Ancillary kernels**：router / align / local-sum，通常 <8% 层时间
- **DP+EP AllToAll**：API 级 fan-out K× 于 AllReduce；多节点 p95 combine 开销可达 uniform 的 **2.7×**

**Token distribution 调制（phase-dependent）**：
- Prefill：padding tax（blockwise vs max padding 最坏情况相反）、EP straggler tax（+40–80%）
- Decode：skew 可能 **减** tax——激活更少 expert，weight loading 下降超过 imbalance 成本
- 提出 **balls-bins-buckets** 框架分析 fine-grained expert、DP attention 等新架构

在 Mixtral-8x7B、Qwen2-MoE、DeepSeek-V3 上用 [[vLLM]] microbenchmark + 端到端测量，并推导可解析 tax 分解模型（R² 对齐实测）。

## 关键结果

- **Prefill tax**：小 batch 高（Mixtral/Qwen 最低 ~**1.28×** @1024 tokens；DeepSeek ~**1.7×**）；细粒度 expert 模型 tax 更高
- **Decode tax**：呈钟形曲线；batch=32 时 Mixtral **2.08×**、Qwen **2.57×**、DeepSeek **~3×**（@128）；中等 batch 延迟可逼近或超过 DensePA
- MoE 整体比 FLOP-equivalent dense **慢 2–3×**；云定价差距与 measured tax 一致
- Padding：FusedMoE prefill padding overhead 可达 **15–25%**；DeepGEMM decode 用 max padding
- 反直觉：decode 阶段 routing skew 可通过减少 activated experts 净收益

## 相关

- **相关概念**：[[MoE]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[KV-Cache]]、[[Chunked-Prefill]]
- **同类系统**：[[vLLM]]、DeepGEMM、DeepEP、Mixtral、DeepSeek-V3
- **同会议**：[[MLSys-2026]]