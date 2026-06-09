---
type: paper
name: CoX-MoE
full_title: "CoX-MoE: Coalesced Expert Execution for High-Throughput MoE Inference with AMX-Enabled CPU-GPU Co-Execution"
authors: [Muyoung Son, Yi Chen, Soongyu Choi, Seungjae Yoo, Joo-Young Kim]
venue: DAC
year: 2026
tags: [llm-inference, moe, cpu-gpu, amx, offloading, throughput]
source_pdf: "[[arxiv26-cox-moe.pdf]]"
source_md: "[[arxiv26-cox-moe]]"
---

# CoX-MoE: Coalesced Expert Execution for High-Throughput MoE Inference with AMX-Enabled CPU-GPU Co-Execution (DAC 2026)

> **一句话总结**：CoX-MoE 指出 MoE batch inference 中 micro-batching 会把 expert GEMM 打碎成 memory-bound 小任务，转而用 AMX-enabled CPU-GPU co-execution + coalesced expert execution + expert-aware stratification，在 Mixtral/DeepSeek/Qwen3 上相对 MoE-Lightning 和 FlexGen 分别最高提升 2.4x、7.1x throughput。

## 问题

高吞吐 [[MoE]] inference 会同时遇到模型权重、intermediate activation 和 [[KV-Cache]] 的 HBM 压力。传统 offloading 系统常把大 batch 切成 micro-batches，以降低瞬时显存占用并复用权重；但 MoE expert 本来就只接收稀疏 token，micro-batching 会进一步降低每个 expert 的 arithmetic intensity，让 expert computation 变成 memory-bound。

另一类 CPU-assist 系统多依赖 AVX，主要 offload decode-stage attention 的 GEMV，对 prefill 阶段的大 GEMM expert workload 帮助有限。CoX-MoE 的判断是：Intel AMX 的 BF16/INT8 tile matrix multiply 已经足够强，可以把 CPU 作为真正的 expert co-execution 资源，而不是只当 host memory。

## 核心方法

CoX-MoE 有两个核心设计。第一是 coalescing-aware orchestration：非 MoE 操作仍可按 micro-batch 调度，但 expert computation 必须对整个 batch coalesce 后执行，以提高 operational intensity；同时系统在 CPU/GPU 之间联合选择 QKV projection、attention、output projection 和 expert FFN 的执行位置，并考虑 PCIe transfer、compute roofline、KV store 等成本。

第二是 expert-aware stratification（EAS）。在吞吐型批处理场景里，整批 workload 事先可见，但全量 profiling 太贵。EAS 先对输入 embedding 聚类，抽样代表性 prototypes，做 prefill-only probing 得到近似 expert activation map，再静态把高频 expert 预放入 GPU，其余交给 CPU/host 路径，减少 PCIe 搬运并平衡 CPU/GPU workload。

实现上，作者扩展 Intel Extension for PyTorch，使其能和 NVIDIA GPU 协同执行，并使用共享 CUDA streams 和 buffer overlap 数据移动与计算。

## 关键结果

- CoX-MoE 在 batch size 1024、不同 input/output 长度、Mixtral/DeepSeek/Qwen3 与多种 GPU 配置上，相对 MoE-Lightning 达到 1.7-2.4x throughput，相对 FlexGen 达到 3.4-7.1x。
- 论文总结平均相对 SOTA 方法高 2.0x throughput。
- EAS 在显存只能容纳有限 expert 的场景下，比 random expert selection 高约 40% expert hit ratio，并带来最高 1.47-1.50x throughput improvement。
- ablation 中，coalescing expert micro-batches + AMX co-execution 带来最大单项收益，达到 1.51x。

## 相关

- **相关概念**：[[MoE]]、[[KV-Cache]]
- **同类系统**：MOE-INFINITY、OD-MoE、ContextAwareMoE-CXLNDP
- **硬件方向**：Intel AMX、CPU-GPU co-execution、PCIe-aware orchestration

