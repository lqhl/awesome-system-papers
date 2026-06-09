---
type: paper
name: ContextAwareMoE-CXLNDP
full_title: "Context-Aware Mixture-of-Experts Inference on CXL-Enabled GPU-NDP Systems"
authors: [Zehao Fan, Yayue Hou, Zhenyu Liu, Hadjer Benmeziane, Liu Liu, Yunzhen Liu, Kaoutar El Maghraoui]
venue: arXiv
year: 2025
tags: [llm-inference, moe, cxl, ndp, quantization, offloading]
source_pdf: "[[arxiv25-context-aware-moe-cxl-ndp.pdf]]"
source_md: "[[arxiv25-context-aware-moe-cxl-ndp]]"
---

# Context-Aware Mixture-of-Experts Inference on CXL-Enabled GPU-NDP Systems (arXiv 2025)

> **一句话总结**：这篇把 [[MoE]] expert offloading 放到 CXL-attached NDP 层执行，用 prefill-stage routing 统计决定 GPU/NDP expert placement 和 NDP 侧 1-4 bit mixed precision，在 Mixtral-8x7B/8x22B 上相对 MoNDE 最高 8.7x decoding throughput 提升且平均精度只降 0.13%。

## 问题

MoE 模型的 expert 权重经常超过单 GPU HBM，直接从 CPU/CXL memory 搬 expert 到 GPU 会被 PCIe/CXL 传输主导。GPU-NDP 系统提供了另一条路：把冷 expert 留在 CXL-attached near-data processing 设备上就地计算，只传 activation。但已有 GPU-NDP MoE 系统多是 context-agnostic 的静态或 reactive placement，无法适应不同输入和 decode step 的 expert 热度变化。

另一个瓶颈是 NDP compute 能力有限。即便冷 expert 不搬到 GPU，如果全部用 full precision 在 NDP 上跑，也可能把瓶颈转移到 NDP 侧。

## 核心方法

论文提出 context-aware expert placement and quantization。系统在 prefill 阶段收集每层每个 expert 的 activation count 和 routing score，计算 expert importance；每个 sequence 只在 prefill 后做一次 placement，hot experts 固定放在 GPU HBM 且保持 FP16，剩余 cold experts 留在 CXL-NDP。

对 NDP-resident experts，系统预先缓存 GPTQ 量化后的 1/2/3/4-bit 版本，并基于同一份 prefill importance 和离线量化 loss table 做 prefix-structured mixed-precision assignment。这样更重要、对精度更敏感的冷 expert 分配更高 bitwidth，低重要度 expert 用更低 bitwidth 来减轻 NDP 计算压力。

## 关键结果

- Mixtral-8x7B 上，3-bit 配置相对 MoNDE 实现 6.6-8.3x end-to-end speedup，2-bit 配置达到 7.9-10.6x；decoding throughput 最高提升 11.2x。
- Mixtral-8x22B 上，3-bit 配置达到 7.6-8.7x speedup，2-bit 配置达到 9.5-11.2x；decoding throughput 最高提升 11.5x。
- NDP-side execution 单独看，3-bit 和 2-bit 分别带来约 5x 和 8x latency reduction。
- Mixtral-8x7B 上，3-bit 配置平均精度相对 full precision 只下降 0.13%；2-bit 平均下降 3.4%。

## 相关

- **相关概念**：[[MoE]]、[[Quantization]]
- **同类系统**：MOE-INFINITY、OD-MoE、CoX-MoE
- **硬件方向**：CXL-attached memory、Near-Data Processing、GPU-NDP co-execution

