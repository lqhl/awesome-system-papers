---
type: entity
kind: system
aliases: [KTransformers, ktransformers]
status: active
last_updated: 2026-06-20
tags: [llm-inference, moe, cpu-gpu-hybrid, expert-offloading, amx]
source_url: "https://github.com/kvcache-ai/ktransformers"
---

# KTransformers

> kvcache-ai 的 CPU/GPU 异构 [[MoE]] 推理引擎：AMX 优化 CPU expert 执行、单 CUDA Graph 异步调度与 Expert Deferral，使 671B 级稀疏 MoE 在有限 GPU 显存 + 双路 Xeon 上可本地运行。

## 是什么

KTransformers 对应 SOSP 2025 论文 [[KTransformers-SOSP25]]，是 **低并发本地部署** 方向的 MoE inference 系统，而非通用 cloud continuous batching 框架。它把 attention、shared experts 与 hot routed experts 放在 GPU，把多数 routed experts 放到 CPU DRAM 并用 Intel AMX（prefill）/ AVX-512（decode）执行，从而在单 A100 + 双 Xeon 上运行 DeepSeek-V3/R1 类 671B 模型。

论文相对 Fiddler / Llama.cpp 等竞品：full accuracy 下 prefill **4.62–19.74×**、decode **1.25–4.09×**；叠加 Expert Deferral 后 decode 累计 **1.66–4.90×**，平均精度损失 <0.5%。实现约 11K 行 C++，接口兼容 HuggingFace 生态。

在 wiki 图谱中，KTransformers 与 [[FluxMoE-arXiv26]]、[[MOE-INFINITY-arXiv24]] 共同定义「GPU 显存不足时 MoE 怎么办」的几种设计点：KTransformers 选择 **CPU 执行 expert**（而非 expert 权重分页到 GPU 后再算，也非 NVMe expert cache）。attention 与 [[KV-Cache]] 通常留在 GPU，CPU 层级主要服务 routed experts——切分简单、可运行，但也暴露 expert 与 KV 统一 offload 时缺乏联合调度的问题。

## 关键观察 / 隐含假设

- **观察 1：MoE 低并发 decode 的瓶颈是 CPU 算力未释放 + GPU 同步开销，而非单纯 PCIe 带宽。** [[KTransformers-SOSP25]] profiling 显示 671B 在 1×A100+2×Xeon 上 GPU <30%、AMX 仅 7% 峰值；Fiddler 每 token **7000+** kernel launch 占 GPU 时间 73%。单 CUDA Graph 封装整段 decode 可获 **1.23×** 加速。
- **观察 2：Expert Deferral 用近似换 overlap，是少数「改执行顺序」而非纯工程优化的设计。** 把部分 routed expert 延后到下一层 attention 期间执行，CPU/GPU 利用率从 74/28% 提到 100/37%，decode +33%；但非 bit-exact，高并发 batch 或精度敏感任务可能不适用（[[KTransformers-SOSP25]]）。
- **观察 3：论文明确不覆盖 cloud-scale continuous batching。** [[KTransformers-SOSP25]] 聚焦 batch size 小、单用户本地场景；与 [[vLLM]]/[[SGLang]] 的多租户 serving 假设正交。后续 MoE offload 论文（[[FluxMoE-arXiv26]]、[[CoX-MoE-DAC26]]）在 related work 中引用 KTransformers，但主实验往往未与其同硬件对标。
- **观察 4：CPU expert 路线与 GPU paging / NVMe cache 路线形成互补设计空间。** [[FluxMoE-arXiv26]] 在 [[vLLM]] 上做 expert paging 释放 HBM 给 KV；[[MOE-INFINITY-arXiv24]] 用 EAM 做 NVMe/DRAM expert cache；[[OD-MoE-arXiv25]] 走 cacheless prediction-driven load。KTransformers 代表「算在 CPU、权重在 DRAM」的第三象限。
- **观察 5：现代 MoE 的 FP4/压缩权重可能改变 CPU offload 的性价比。** [[DeepSeek-V4-arXiv26]] 与 [[FluxMoE-arXiv26]] 显示模型侧 FP4 expert 与 KV 压缩正在缩小「必须 offload 到 CPU」的压力；KTransformers 的 AMX Int4/Int8 block quant 路径是否仍是最优，取决于目标模型与硬件代际。

## 演进时间线

- **2025 SOSP**：[[KTransformers-SOSP25]] 发布 AMX kernel、异步 CPU-GPU 调度、Expert Deferral 与 DeepSeek-V3 端到端评估。
- **2025–2026 周边**：[[ContextAwareMoE-CXLNDP-arXiv25]]、[[CoX-MoE-DAC26]]、[[OD-MoE-arXiv25]]、[[FluxMoE-arXiv26]] 在 MoE offload 综述中将 KTransformers 列为 CPU-GPU hybrid 代表；[[DecDEC-OSDI25]] 同属 expert 执行路径讨论语境。

## 相关概念

- [[MoE]]
- [[Expert-Offloading]]
- [[KV-Cache]]
- [[CUDA-Graph]]
- [[NUMA]]
- [[Quantization]]

## 相关论文

- [[KTransformers-SOSP25]] — 原始系统：AMX kernel、CUDA Graph 异步调度、Expert Deferral、DeepSeek-V3 评估
- [[FluxMoE-arXiv26]] — 对比路线：vLLM 上 expert paging vs CPU 执行；related work 点名 KTransformers 但主实验未直接对标
- [[MOE-INFINITY-arXiv24]] — 同类 personal-machine MoE：NVMe/DRAM expert cache + EAM，非 CPU 算 expert
- [[OD-MoE-arXiv25]] — cacheless expert loading + shadow model prediction，边缘分布式推理
- [[CoX-MoE-DAC26]] — batch throughput 场景 AMX CPU-GPU co-execution；相关工作建议与 KTransformers 直连对比
- [[ContextAwareMoE-CXLNDP-arXiv25]] — CXL-NDP cold expert compute；MoE offload 生态对照之一
- [[DeepSeek-V4-arXiv26]] — FP4 MoE + 异构 KV 改变本地部署的资源权衡语境