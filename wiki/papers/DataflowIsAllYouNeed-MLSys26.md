---
type: paper
name: DataflowIsAllYouNeed
full_title: "Dataflow Is All You Need"
authors: [Darshan Gandhi, Pushkar Nandkar, David Koeplinger, Nasim Farahini, Romy Tsoupidi, et al.]
venue: MLSys
year: 2026
tags: [dataflow, inference, decode, speculative-decoding, sambanova, rdu]
source_pdf: "[[33e75ff09dd601bbe69f351039152189.pdf]]"
source_md: "[[33e75ff09dd601bbe69f351039152189]]"
---

# Dataflow Is All You Need (MLSys 2026)

> **一句话总结**：SambaNova SN40 数据流架构上用 KernelLooping、BatchStreaming、ScheduleOffloading 三项编译/运行时协同优化，decode 达 roofline 75%+、[[Speculative-Decoding]] 端到端 >6×，16 片 SN40 比 DGX H100 快 1.7×（可比 HBM 带宽下）。

## 问题

开源大模型 context 变长 + chain-of-thought 让 decode 阶段（memory-bandwidth-bound）成为瓶颈。GPU 上 Llama3.1-8B 在 8×H100 仅用到 21% HBM 带宽读权重和 [[KV-Cache]]；kernel 边界强制同步、compute-communication 重叠不足，[[Speculative-Decoding]] 时 draft 模型占每步 72% 时间。

Megakernel 等融合方案缓解单 GPU kernel launch，但中间仍访问 HBM，且难覆盖多卡 collective；NVSHMEM 等 GPU-GPU 通信仍经 global memory，对 decode 这类带宽敏感场景伤害大。CUDA Graphs 又与 [[MoE]] 动态 expert routing 不兼容。

## 核心方法

在 SambaNova **SN40 RDU**（Reconfigurable Dataflow Unit）上，大子图跨 chip 异步执行、chip 间经 on-chip memory 直传、不经 HBM，计算/访存/通信天然重叠。三项数据流专属优化：

**1. KernelLooping（编译器）**：把重复 decoder layer 调用折叠成带 pipeline 外循环的单一 kernel，消除层间同步、跨层重叠 compute 与通信。Llama3.1-8B 从 H100 上 320 次 kernel call 降到 SN40 上 4 次；geomean **1.6×**，Qwen2.5-72B 近 **2×**。

**2. BatchStreaming（编译器）**：用 LoopBuffer 在 decoder 层间建非阻塞通道，样本不必等同层全部完成再进下一层，消除 batch 边界人为同步；batch≥2 时对 1B/3B/8B draft 模型显著提速，batch 越大 warm-up 摊销越好。

**3. ScheduleOffloading（运行时）**：把 [[Speculative-Decoding]] 的 draft/target 调度链卸载到硬件 graph orchestration，减少 host 往返；k=9 时 draft-only 吞吐明显提升，小模型收益更大。

对比：TensorRT-LLM 在 H100 上每层 decoder 拆 10 个 kernel（K1–K10），[[Tensor-Parallelism|tensor parallel]] allreduce 不与算子重叠；SN40 整层融合为单 kernel K0，allreduce 与 GEMM/Add 流水线并行。

## 关键结果

- 覆盖 dense、[[MoE]]、hybrid、GQA/MLA 等多种架构；decode 稳态吞吐达理论 roofline **45–78%**（大模型更高）
- 三项优化合计：**>6×** vs 无优化 target model；batched speculative decode 在 Llama 70B/405B 等工作负载上验证
- Llama3.1 70B + 8B draft（k=9）：SN40-16 比 DGX H100 **快 60–80%**；16 SN40 vs DGX H100 speculative decoding **1.7×**（HBM 带宽相近）
- 已部署于 cloud.sambanova.ai 生产推理云

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、[[MoE]]、[[Tensor-Parallelism]]、[[Continuous-Batching]]
- **同类系统**：TensorRT-LLM、megakernels、CUDA Graphs、[[vLLM]]、[[SGLang]]
- **同会议**：[[MLSys-2026]]