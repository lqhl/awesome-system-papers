---
type: paper
name: OD-MoE
full_title: "OD-MoE: On-Demand Expert Loading for Cacheless Edge-Distributed MoE Inference"
authors: [Liujianfu Wang, Yuyang Du, Yuchen Pan, Soung Chang Liew, Jiacheng Liu, Kexin Chen]
venue: arXiv
year: 2025
tags: [llm-inference, moe, edge, expert-loading, distributed-inference]
source_pdf: "[[arxiv25-od-moe.pdf]]"
source_md: "[[arxiv25-od-moe]]"
---

# OD-MoE: On-Demand Expert Loading for Cacheless Edge-Distributed MoE Inference (arXiv 2025)

> **一句话总结**：OD-MoE 用 quantized shadow model 做 Scaled Emulative Prediction，在多台低成本 edge GPU 上并行提前加载 expert，完全取消 GPU expert cache，达到 fully cached MoE 约 75% decoding speed，同时只用 1/3 GPU memory 且 expert activation prediction accuracy 达 99.94%。

## 问题

边缘设备 GPU memory 小、CPU-GPU I/O 带宽低，部署大 [[MoE]] 模型时 expert offloading 的加载延迟非常突出。传统方案用 GPU expert cache 缓住热门 expert，但 cache 本身占用大量 HBM，使低成本设备很难承载大模型；量化或跳过 expert 又会损伤模型质量。

OD-MoE 的目标更激进：不保留 expert cache，只在需要前即时加载目标 expert，用完立即驱逐，同时仍避免 compute stall。

## 核心方法

OD-MoE 的关键是 Scaled Emulative Prediction（SEP）。系统在 shadow node 上运行一个更快的 quantized MoE shadow model，让它领先 full-precision main model 若干层，直接用 shadow model 已展开的未来 routing 来预测 full model 的未来 expert activation。由于 quantized model 和 full model 的 routing 行为高度相似，SEP 比基于局部 gate 或历史频率的 predictor 更准。

为避免 autoregressive 过程中的误差积累，SEP 周期性对齐 shadow model 与 full model 的 token 和 [[KV-Cache]]。这带来 late-departure cost：shadow model 需要等 full model 当前 token 生成后才能对齐，再追赶预测未来层。论文用不同 token/KV alignment interval 分析了 prediction accuracy 与延迟的权衡。

系统层面，OD-MoE 把 worker nodes 分组并 round-robin 调度：一组设备计算当前层 expert，其他组并行加载未来层 expert。SEP 的多层 ahead prediction 让每个 worker 知道自己未来要加载什么 expert，从而用多条 CPU-GPU link 叠加 I/O 带宽。

## 关键结果

- FP16 shadow model 下，SEP expert activation recall 达 99.94%；INT8 和 NF4 shadow model 仍有 97.34% 和 95.67%。
- 在 10-node edge testbed 上，OD-MoE 达到 fully GPU-cached MoE deployment 约 75% decoding speed。
- 每个 worker node 的 GPU footprint 小于 1GB，整体只需要 fully cached 部署约 1/3 GPU memory。
- 论文强调 cache-free 设计可让低成本 IoT/edge devices 参与 MoE inference，而不是必须拥有能容纳 expert cache 的大显存 GPU。

## 相关

- **相关概念**：[[MoE]]、[[KV-Cache]]
- **同类系统**：MOE-INFINITY、ContextAwareMoE-CXLNDP、CoX-MoE
- **方法关键词**：Scaled Emulative Prediction、shadow model、cacheless expert loading、edge-distributed inference

