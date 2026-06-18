---
type: paper
name: Meta-LLM-Deploy
full_title: "Optimizing Deployment Configurations for LLM Inference: Challenges and Insights"
authors: ["Meta Inference Team"]
venue: MLSys
year: 2026
tags: [llm-inference, deployment, design-space-exploration, parallelism, disaggregation]
source_pdf: "[[c7e1249ffc03eb9ded908c236bd1996d.pdf]]"
source_md: "[[c7e1249ffc03eb9ded908c236bd1996d]]"
---

# Optimizing Deployment Configurations for LLM Inference: Challenges and Insights (MLSys 2026)

> **一句话总结**：Meta 用基于算子 benchmark 的轻量 simulator 在数百万部署配置中搜索最优组合，服务近 10 亿月活用户的 Llama 推理吞吐最高提升约 2.5×，并总结出 runtime、5D 并行、异构硬件等生产级洞察。

## 问题

Llama 等 LLM 服务近 10 亿月活用户，部署需在硬件（H100/H200/MI300X）、5D 并行（TP/PP/EP/CP/DP）、runtime（[[Continuous-Batching]] vs prefill-decode [[Disaggregation]]）、[[KV-Cache]] 管理等维度做组合优化，同时满足 TTFT/TTIT SLO。每个服务场景就有模型×硬件×runtime×并行 ≈ 百万级配置，手工启发式不可持续。

## 核心方法

Meta 构建 bottom-up 轻量性能 simulator：

1. **Micro-benchmarking**：在目标硬件上 profile GEMM、attention、AllReduce、All2All 等算子，每硬件保留 100K+ 测量点。
2. **Operator Performance Model**：多维分段线性插值，比解析模型更准确（误差通常 ±5%）。
3. **Block-level 组装**：把算子模型拼成 prefill/decode 端到端延迟与吞吐。
4. **SLO-aware ranking**：过滤违反 TTFT/TTIT 的配置，按 QPS_cluster 排序。

在此框架上系统探索：runtime 架构、phase-specific 并行策略、异构硬件混部、MoE 架构影响、平台 scale-out vs scale-up 选择。

## 关键结果

- 整体吞吐改进最高约 **2.5×**。
- 在线严格延迟 SLO 下，disaggregated runtime 比 continuous batching 高 1.5–2.2× QPS（70B/405B）；离线吞吐导向场景两者趋同，continuous batching 运维更简单。
- Prefill 与 decode 最优并行策略显著不同（如 70B online：prefill PP4-TP2，decode TP8 batch 128）。
- 异构配置（如 GPU-A prefill + GPU-B/C decode）可达与最佳同构相当的 67 QPS_cluster，有潜在成本节省。
- 错误平台选择可导致 2–3× 成本低效或 SLO 失败。

## 相关

- **相关概念**：[[Continuous-Batching]]、[[Disaggregation]]、[[KV-Cache]]、[[MoE]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[Speculative-Decoding]]
- **同类系统**：Vidur、LLMServingSim、Agrawal et al. 推理分析
- **同会议**：[[MLSys-2026]]