---
type: paper
name: HeteroInfer
full_title: "Characterizing Mobile SoC for Accelerating Heterogeneous LLM Inference"
authors: [Le Chen, Dahu Feng, Erhu Feng, Yingrui Wang, Rong Zhao, et al.]
venue: SOSP
year: 2025
tags: [llm-inference, mobile, heterogeneous-computing, npu, gpu]
source_pdf: "[[3731569.3764808.pdf]]"
source_md: "[[3731569.3764808]]"
---

# Characterizing Mobile SoC for Accelerating Heterogeneous LLM Inference (SOSP 2025)

> **一句话总结**：HeteroInfer 首个让手机 GPU+NPU 真正并行跑 [[LLM-Inference|LLM 推理]] 的引擎，在 Snapdragon 8 Gen 3 上 prefill 超 1000 tok/s、decode 超 50 tok/s，端到端相比 GPU-only/NPU-only 基线加速 1.34-6.02×。

## 问题

手机本地 LLM 推理为了隐私与低延迟越来越重要，SoC 已经集成 CPU/GPU/NPU 多种加速器，但现有移动推理引擎（MLC、MNN-LLM、PowerInfer2、llm.npu、Qualcomm-AI）都只用其中单一后端。作者识别三个障碍使 GPU-NPU 并行难以实现：(1) GPU 与 NPU 算力差距大（Adreno 750 约 1 TFLOPS 实际 vs Hexagon 10 TFLOPS），简单按算力切分未必更快；(2) 跨处理器同步开销巨大（clFinish 约 400 μs，可与单 kernel 时长相当）；(3) decoding 是 memory-bound，单纯加算力可能被同步开销抵消。此外，NPU 对 INT4/8 量化精度损失可达 20%，而直接用 FP16 性能又对张量形状极其敏感。

## 核心方法

HeteroInfer 基于对移动 SoC 的系统性 characterization，利用三条新观察驱动设计：NPU 的 stage/order/shape-sensitive 性能；CPU/GPU/NPU 共享的 [[Unified-Memory-Architecture|UMA]]；单处理器无法打满 SoC 内存带宽（68 GB/s 理论 vs 单 GPU 40-45 GB/s）。CPU 只作控制面做同步和 GPU kernel 调度，NPU 作主计算单元，GPU 作辅助补 NPU 的"短板形状"。

三种张量级并行策略：(1) Weight-centric partition with static shape：沿 weight 行维切分，把 NPU 不擅长（如 FFN-down 列长行短）的部分交给 GPU；(2) 在 prefill 中对短序列或形状不对齐的情形调 GPU；(3) decoding 阶段 75/25 GPU-NPU split 以共同拉满内存带宽。微秒级同步机制基于"可预测 kernel 等待时间"避免 clFinish 的 400 μs 惩罚；离线 tensor partitioning solver + hardware profiler 求解最优切分比。系统基于 OpenCL GPU kernel + Qualcomm QNN NPU operator 在 Snapdragon 8 Gen 3 实现，全程高精度（W4A16），不引入量化精度损失。

## 关键结果

- 首个在手机billion-parameter LLM 上高精度计算突破 1000 tok/s prefill 与 50 tok/s decoding 的引擎
- prefill 相比 PI-2（NPU）最多 3.69×、相比 MNN（GPU）8.68×
- 序列长度与 NPU graph shape 不对齐时相比 padding 方案 2.12×
- decoding 稳定 1.50-2.53× 领先
- 与游戏共跑时 FPS 不掉，prefill 仅慢 2.2%、decoding 仅慢 17.7%

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Attention]]、[[Transformer]]、[[Quantization]]
- **同类系统**：[[PowerInfer2]]、[[llm.npu]]、[[MLC-LLM]]、[[MNN-LLM]]、[[vLLM]]
- **同会议**：[[SOSP-2025]]
