---
type: paper
name: KTransformers
full_title: "KTransformers: Unleashing the Full Potential of CPU/GPU Hybrid Inference for MoE Models"
authors: [Hongtao Chen, Weiyu Xie, Boxin Zhang, Jingqi Tang, Jiahao Wang, et al.]
venue: SOSP
year: 2025
tags: [llm-inference, moe, cpu-gpu-hybrid, expert-offloading, amx]
source_pdf: "[[3731569.3764843.pdf]]"
source_md: "[[3731569.3764843]]"
---

# KTransformers: Unleashing the Full Potential of CPU/GPU Hybrid Inference for MoE Models (SOSP 2025)

> **一句话总结**:通过 AMX 专用 kernel + 异步 CPU-GPU 调度 + Expert Deferral 执行重排,让 671B [[DeepSeek-V3]]/R1 这类大 [[MoE]] 模型在单 A100 + 双 Xeon 上可用,prefill 加速 4.62–19.74×、decode 加速 1.25–4.09×,Expert Deferral 再叠加 1.45× 吞吐且精度损失 < 0.5%。

## 问题

[[MoE]] 模型总参数量巨大(671B DeepSeek-V3/R1)但激活稀疏,天然适合 CPU/GPU 混合推理——把 [[Attention]] 和共享专家留在 GPU,路由专家放到 CPU DRAM。然而 Fiddler 风格的现有方案在本地低并发部署(1×A100 + 2×Xeon)下严重瓶颈:prefill 70 tok/s,decode 4.68 tok/s,GPU 利用率 < 30%。

根因有两条:(1) prefill 阶段 CPU 计算不足——PyTorch 走 oneDNN 的 AMX kernel 只发挥 7% 理论峰值,内存布局和缓存效率差;(2) decode 阶段 CPU-GPU/CPU 协调低效——Fiddler 每 token 发起 7000+ CUDA kernel launch,占 GPU 时间的 73%,NUMA 跨 socket 访问代价高。

## 核心方法

**Arithmetic Intensity-Aware Hybrid Kernel**:为 Intel AMX 指令定制 tiling-aware 内存布局——专家权重在加载时预处理成 AMX 兼容子矩阵(16 行 × 64 字节 tile),对齐 64 字节缓存行,Int4/Int8 block-wise 对称量化。高 ARI 场景(prefill,长 prompt)走 AMX,低 ARI 场景(decode,1-4 token/expert)自动切回 AVX-512。配合算子级 Gate/Up/Down 投影 fusion 和动态任务调度,AMX kernel 单 socket 达 21.3 TFLOPS(3.98× 超过 oneDNN)。

**Asynchronous CPU-GPU Task Scheduling**:利用 `cudaLaunchHostFunc` 把 submit/sync 两个屏障塞进 CUDA 流回调,整个 decode 路径单 token 仅一个 [[CUDA-Graph]] 实例,消除 kernel launch 开销,decode 加速 1.23×。配合 NUMA-aware tensor 并行,不对称分配工作量以对冲跨 socket 访问延迟。

**Expert Deferral**:核心执行策略创新。在 MoE 层里只立即执行部分 experts(immediate),其余 deferred experts 与下一层的 attention 并发执行。通过重排执行管线,CPU/GPU 利用率从 74%/28% 提升到 100%/37%,DeepSeek-V3 decode 吞吐提升 33%(最高 45%),在 HumanEval/MBPP/GSM8K/StrategyQA/LiveBench 上精度平均下降 ≤ 0.5%。

## 关键结果

- Prefill 速度 4.62–19.74× 高于 Fiddler/Llama.cpp 基线
- Decode 速度 1.25–4.09×(加 Expert Deferral 后 1.66–4.90×)
- DeepSeek-V3 decode CPU 利用率从 74% 升到 100%
- 支持万亿参数 MoE 在单 server + 单消费级 GPU 上跑
- 已在 kvcache-ai/ktransformers 开源,被开源社区和工业界广泛采用,运行在数百台机器上

## 相关

- **相关概念**:[[MoE]]、[[KV-Cache]]、[[Expert-Offloading]]、[[CUDA-Graph]]、[[NUMA]]、[[Attention]]
- **同类系统**:[[vLLM]]、[[SGLang]]、Fiddler、Llama.cpp
- **同会议**:[[SOSP-2025]]
