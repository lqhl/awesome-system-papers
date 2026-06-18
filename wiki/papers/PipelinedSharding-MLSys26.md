---
type: paper
name: PipelinedSharding
full_title: "Efficient, VRAM-Constrained xLM Inference on Clients"
authors: [Aditya Ukarande, Deep Shekhar, Marc Blackstein, Ram Rangan]
venue: MLSys
year: 2026
tags: [client-inference, cpu-gpu-offload, vram, llama-cpp, vlm, moe]
source_pdf: "[[eb160de1de89d9058fcb0b968dbbbd68.pdf]]"
source_md: "[[eb160de1de89d9058fcb0b968dbbbd68]]"
---

# Efficient, VRAM-Constrained xLM Inference on Clients (MLSys 2026)

> **一句话总结**：Pipelined Sharding 在 llama.cpp 里按 sub-layer 切分 dense/MoE LLM 与 VLM，用 install-time kernel profile + 三档 schedule（GPU-only / Static / Dynamic）按 token tier 自适应 CPU-GPU-PCIe 三角，2G VRAM 上 235B MoE 仍达 7.7 TPS，TTFT 最高 6.7×、TPS 最高 30×。

## 问题

客户端单卡 GPU VRAM 有限，但游戏助手（NVIDIA IGI SDK）与物理 AI（Cosmos-Reason1 VLM）需要 **无损**、高参数 dense/MoE LLM 与原生分辨率 VLM，并随 CPU 线程数、PCIe 带宽、VRAM 预算、prefill/decode 阶段与 batch 大小自适应。现有 hybrid scheduling（FlexGen、PowerInfer、ZeRO-Inference、静态 layer partition）往往只覆盖大 batch 或单一阶段，无法同时处理 interactive + batched、dense + [[MoE]]、LLM + VLM。

## 核心方法

**四阶段流水线**（Figure 1）：

1. **Install**：15 分钟 benchmark matmul/GQA/MHA/MoE/elementwise，建 170KB CPU+GPU FLOPS profile（含 PCIe 争用）。
2. **Planning**：按 token tier {1,4,16,…,16K} 为每层 sub-layer 生成三档 plan——(a) 全 GPU + scratch 双缓冲 JIT 拷权重；(b) Static CPU/GPU 固定划分，只传 activation；(c) Dynamic 更少 CPU 层、权重流与 CPU 计算重叠。用 roofline 估时选最优；attention/KV cache/FFN/output 优先级递减 pin VRAM。
3. **Inference**：按 batch-wide new tokens 选 tier，拓扑序执行 schedule；高 token tier 兼作 [[Chunked-Prefill]] chunk size。

**VLMOpt**（语言侧仍用 pipelined sharding）：vision 权重 CPU offload、vision encoder 启用 [[Flash-Attention]] + Q-chunking、vision 与 language 串行初始化避免 VRAM 峰值叠加。

实现于 llama.cpp branch 6097，已开源（Appendix A）。

## 关键结果

- Interactive（bs=1）：TTFT 平均 **2×**（最高 **6.7×**），TPS 平均 **3.7×**（最高 **30×**）；batched TPS 平均 **2.3×**（最高 **8.2×**）。
- **2G VRAM**：Qwen-235B-A22B（磁盘 77GB）1K context **7.7 TPS**，16K 仍 **5.2 TPS**（≥5 TPS 可读阈值）。
- VLM：CR1 图像推理 VRAM 相对 vLLM baseline **10×** 下降；vnemo4b E2EL 最高 **1.78×**。
- 相对手动 MoE FFN offload：64K context 下 TPS 最高 **21.8×**。

## 相关

- **相关概念**：[[KV-Cache]]、[[MoE]]、[[Flash-Attention]]、[[Chunked-Prefill]]、CPU Offloading
- **同类系统**：llama.cpp、FlexGen、PowerInfer、ZeRO-Inference、[[vLLM]]
- **目标产品**：NVIDIA IGI SDK、Cosmos-Reason1
- **同会议**：[[MLSys-2026]]