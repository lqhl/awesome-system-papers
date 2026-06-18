---
type: paper
name: HipKittens
full_title: "HipKittens: Fast and Furious AMD Kernels"
authors: [William Hu, Drew Wadsworth, Sean Siddens, Stanley Winata, Daniel Y. Fu, et al.]
venue: MLSys
year: 2026
tags: [gpu-kernels, amd, dsl, compiler, gemm, attention]
source_pdf: "[[2a38a4a9316c49e5a833517c45d31070.pdf]]"
source_md: "[[2a38a4a9316c49e5a833517c45d31070]]"
---

# HipKittens: Fast and Furious AMD Kernels (MLSys 2026)

> **一句话总结**：将 ThunderKittens 式 tile DSL 移植到 AMD CDNA3/4，用 8-wave ping-pong 调度、显式寄存器 pin 与 chiplet-aware swizzle 追平 AITER 手写汇编，GQA backward 1.8×、部分 attention 形状 1.2–2.4× 于全部基线。

## 问题

AMD MI355X 峰值算力与带宽已具竞争力，但 peak kernel 依赖 AITER/CK 等汇编库，难以覆盖全量 AI workload——AITER Llama GQA backward 仅 SoTA 30%，PyTorch SDPA 24%。NVIDIA 侧 [[Flash-Attention]] 生态已收敛到 ThunderKittens 等 tile DSL。NVIDIA 已收敛到 ThunderKittens/CuTe DSL + wave specialization，能否迁移到 AMD 是开放问题。

直接迁移障碍：HIPCC 限制 AGPR 作 MFMA 输入；AMD matrix layout 无 NVIDIA 16×16 复合结构；wave specialization 在 AMD 静态寄存器分配下 producer 占寄存器不算力，MI355X BF16 GEMM 仅峰值 80%。

## 核心方法

**HipKittens (HK)** 保留 tile + bulk operator，为 AMD 重设三项原语：

1. **显式寄存器 pin**：绕过 HIPCC，MHA backward 855→1024 TFLOPS，匹配 AITER 1018
2. **8-wave ping-pong / 4-wave interleave**：每 SIMD 两 wave 轮换 compute↔memory；8-wave 覆盖 GEMM/attention fwd，4-wave 在 GQA non-causal backward 再快至 2.3× 基线
3. **Chiplet grid schedule（Algorithm 1）**：联合优化 L2/LLC 复用，naive row-major 36% L2 hit → 调参后 +19% 性能

AMD shared memory swizzle 需对 HBM 地址做（非 NVIDIA TMA 式 shared 地址 swizzle）。

## 关键结果

MI325X/MI355X 上 BF16/FP8 GEMM、GQA/MHA fwd/bwd、RoPE、LayerNorm：**追平或超过 AITER**
- 汇编未覆盖场景（d=64 attention、GQA backward、memory-bound）：**1.2–10×**
- vs Triton BF16 GEMM 最多 3×，vs Mojo MHA fwd 2×
- 开源：https://github.com/HazyResearch/HipKittens

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]
- **同类系统**：ThunderKittens、CuTe DSL、Gluon、Triton、AITER、Composable Kernel
- **同会议**：[[MLSys-2026]]