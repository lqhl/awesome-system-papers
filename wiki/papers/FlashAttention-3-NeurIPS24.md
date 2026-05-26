---
type: paper
name: FlashAttention-3
full_title: "FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-precision"
authors: [Jay Shah, Ganesh Bikshandi, Ying Zhang, Vijay Thakkar, Pradeep Ramani, Tri Dao]
venue: NeurIPS
year: 2024
tags: [attention, gpu-kernel, hopper, fp8, transformer]
source_pdf: "[[neurips24-shah-flashattention3.pdf]]"
source_md: "[[neurips24-shah-flashattention3]]"
---

# FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-precision (NeurIPS 2024)

> **一句话总结**：FlashAttention-3 把 [[FlashAttention-2-ICLR24|FA2]] 的 exact attention kernel 重写到 Hopper H100 的异步执行模型上，用 TMA/WGMMA warp specialization、GEMM-softmax overlap 与 FP8 block quantization + incoherent processing，把 BF16 forward 提到最高 **840 TFLOPs/s**（85% H100 理论峰值），相对 FA2 **1.5-2.0x**，FP8 forward 达 **1.3 PFLOPs/s** 且比 per-tensor FP8 baseline 数值误差低 **2.6x**。

## 问题

[[FlashAttention-NeurIPS22|FlashAttention]] 和 [[FlashAttention-2-ICLR24|FlashAttention-2]] 已经把 exact [[Attention]] 从 HBM IO 问题转成更接近 GEMM 的 GPU kernel 问题，但 FA2 的算法模型仍然偏同步：不显式利用 Hopper 的 Tensor Memory Accelerator (TMA)、异步 WGMMA Tensor Core、warpgroup 级寄存器重分配，也没有把 FP8 作为算法一等公民。论文指出 FA2 在 H100 上只有约 35% utilization，而高度优化的 GEMM 可到 80-85%。

根本瓶颈是 **asynchrony 和 low precision 都会改变 attention kernel 的算法形状**。softmax 依赖 QK 的输出，看起来不能和 GEMM overlap；FP8 虽然能把 matmul 吞吐翻倍，但 attention 有连续两个 GEMM，FP32 accumulator 到 FP8 operand 的 layout、V tile 的 k-major 约束、LLM outlier feature 的量化误差都不能靠简单换 dtype 解决。

## 核心方法

FlashAttention-3 仍保持 [[Flash-Attention]] 的 exact dense attention 语义，但把 kernel 拆成适配 Hopper 异步硬件的 pipeline：

1. **Producer-consumer warp specialization**：把 warpgroup 分成 producer 和 consumer。producer 用 TMA 异步搬 Q/K/V tile 到 shared memory，consumer 用 WGMMA 做 QK 和 PV；配合 circular SMEM buffer、mbarrier 和 `setmaxnreg`，让搬运和计算更少互相阻塞。
2. **Pingpong scheduling**：两个 consumer warpgroup 交替工作，让一个 warpgroup 做 softmax 时，另一个 warpgroup 的 GEMM 在 Tensor Core 上跑。论文实测 head dim 128、seq 8192 的 FP16 forward 从约 570 TFLOPs/s 提到 620-640 TFLOPs/s。
3. **2-stage / 3-stage WGMMA-softmax pipelining**：跨 loop iteration 打破 softmax 和第二个 GEMM 的顺序化等待，把下一块 QK 的 WGMMA 与当前块 softmax/PV overlap。代价是多保留一份 `S_next` 等中间状态，必须和 tile size、寄存器压力一起权衡。
4. **FP8 layout 适配**：处理 FP32 accumulator 到 FP8 operand 的 register ownership 变换，并在 kernel 内对 V tile 做 SMEM/RMEM/SMEM transpose，满足 Hopper FP8 WGMMA 的 k-major operand 约束。
5. **FP8 accuracy**：用 block quantization 为 Q/K/V 的每个 block 维护独立 scale，并借鉴 QuIP/QuIP# 的 incoherent processing，对 Q/K 乘随机正交矩阵摊平 outlier。由于正交变换不改变 QK^T，理论上保持 attention 结果，只降低量化误差。

## 关键结果

- H100 80GB SXM5 上，BF16 forward 相对 FA2 **1.5-2.0x**，backward **1.5-1.75x**。
- BF16 forward 最高 **840 TFLOPs/s**，约 **85%** H100 理论峰值。
- FP8 forward 最高 **1.3 PFLOPs/s**。
- 标准 attention baseline 相比，FA3 可达 **3-16x**；中长序列上 BF16 可超过 H100 优化过的 cuDNN attention。
- Ablation 显示 warp-specialization + 2-stage overlap 把固定配置从 **570 TFLOPs/s** 提到 **661 TFLOPs/s**。
- FP16 数值误差与 FA2 相当；FP8 + block quantization + incoherent processing 在 outlier 场景下比 per-tensor FP8 baseline 误差低 **2.6x**。
- 开源：https://github.com/Dao-AILab/flash-attention

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、[[Online-Softmax]]、[[Quantization]]
- **前序工作**：[[FlashAttention-NeurIPS22|FlashAttention]]、[[FlashAttention-2-ICLR24|FlashAttention-2]]
- **后续工作**：[[FlashAttention-4-MLSys26|FlashAttention-4]]
- **同主题**：[[Foundation]]、[[AI-Infra]]
