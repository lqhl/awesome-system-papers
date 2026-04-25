---
type: paper
name: Optimus
full_title: "Optimus: Accelerating Large-Scale Multi-Modal LLM Training by Bubble Exploitation"
authors: [Weiqi Feng, Yangrui Chen, Shaoyu Wang, Yanghua Peng, Haibin Lin, Minlan Yu]
venue: ATC
year: 2025
tags: [llm-training, multimodal, 3d-parallelism, pipeline-bubble, distributed-training]
source_pdf: "[[atc2025-feng.pdf]]"
source_md: "[[atc2025-feng]]"
---

# Optimus: Accelerating Large-Scale Multi-Modal LLM Training by Bubble Exploitation (ATC 2025)

> **一句话总结**：把 MLLM 训练中 LLM bubble（DP all-gather/reduce-scatter + PP warm/cooldown + TP 子毫秒级气泡，48% GPU cycle）填上 encoder kernel 计算，3072 GPU 上 ViT-22B + GPT-175B 训练加速 20.5%-21.3%。

## 问题

MLLM (GPT-4V、Gemini 等) 多 encoder + 大 LLM backbone 的异构结构在 3D 并行下导致大量 bubble：DP all-gather 3.3% + reduce-scatter 8.9%、PP warm 5.0% + cooldown 9.2% + other 8.7%、[[Tensor-Parallelism]] 子毫秒 bubble 11.2%，总计 ~48% GPU cycle 浪费。Megatron-LM 把 encoder 与 LLM 用同一 3D 并行计划分布到 GPU，导致仅一个 PP stage 的 GPU 同时持有 encoder + LLM 状态，其他 GPU 即使 LLM bubble 出现也无法跑 encoder。

## 核心方法

三个核心 design decision：

1. **Encoder/LLM 分离的并行策略**：枚举 (DPenc, PPenc, TPenc)，要求 PPenc 整除 PPllm、TPenc 整除 TPllm，让所有 GPU 都同时拥有 encoder + LLM 模型状态。memory overhead 通常 < 12%（encoder 参数最多 22 B vs LLM 几百 B）。
2. **Dual-stage dependency management**：local scheduling 处理迭代依赖与 encoder 内部 PP 依赖；global ordering 通过排序各 microbatch 的 encoder forward 完成时间 EFi、backward 起始时间 EBi 来检验 encoder-LLM microbatch 级依赖 (EFi ≤ Fi、EBi ≥ Bi)。
3. **Kernel 级 bubble scheduling**：把 encoder layer 拆成 kernel sequence 以填子毫秒 TP bubble；coarse-grained 阶段先把 encoder forward 排在所有 LLM 计算前的 DP+PP-warm 大 bubble、encoder backward 排在 PP-cooldown+reduce-scatter 大 bubble；fine-grained 阶段迭代找 critical path 上的 encoder pipeline 把 microbatch 计算 kernel 散到 LLM 计算间的 PP/TP bubble。Encoder TP 通信 kernel 不与 LLM TP bubble 抢带宽，而是与 LLM compute kernel overlap。

调整 1F1B-interleaved 的 warmup microbatch 数把后半段 forward 依赖点 F5-F8 推迟以多腾出可用 bubble。详细 algorithm 回 [[atc2025-feng]]。

## 关键结果

- 在生产集群 3072 NVIDIA Hopper GPU 上 ViT-22B + GPT-175B 比 Megatron-LM/MegaScale/Zero Bubble 加速 **20.5%-21.3%**。
- Optimus 相比所有 baseline 平均加速 20.3%。
- Memory overhead < 12%（encoder 状态多复制了 DPenc-DPllm 份）。
- 调度算法复杂度 O(C²(np+1) · Nmb^m · (F+B))，实际几分钟可算出最优 schedule（一次性开销）。
- 支持多 encoder 模型（每个 encoder 独立 PPenc 切分）。

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Data-Parallelism]]、[[3D-Parallelism]]、[[Pipeline-Bubble]]、[[1F1B]]
- **同类系统**：Megatron-LM、MegaScale、Zero Bubble Pipeline、Chimera、DistMM、DistTrain、DiffusionPipe
- **同会议**：[[ATC-2025]]
