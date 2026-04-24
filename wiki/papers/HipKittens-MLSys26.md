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

> **一句话总结**：把 ThunderKittens 风格的 tile-based C++ 嵌入式 DSL 移植到 AMD CDNA3/CDNA4，用新的 8-wave ping-pong 调度 + 显式寄存器 pin + chiplet-aware swizzle，性能追平甚至超过 AMD 手写汇编 AITER（GQA backward 1.8×、memory-bound kernel 最多 2.4×），消灭 "CUDA moat"。

## 问题

AMD MI355X 峰值算力（2.5 PFLOPs BF16）和带宽（8 TB/s）追上甚至超过 NVIDIA B200，但软件生态滞后："peak performance" AMD kernel 只能手写汇编（AITER、Composable Kernel），难以覆盖全部 AI workload——AITER 的 Llama GQA backward 在 MI355X 上只有 SoTA 的 30%，PyTorch 只有 24%。

NVIDIA 侧已经收敛到 tile-based DSL（ThunderKittens、CuTe DSL、Gluon）+ wave specialization（producer-consumer）模式。核心问题：**这些抽象能不能迁移到 AMD？**

直接迁移的坑：
- HIPCC 编译器限制（如不能把 AGPR 做 MFMA 输入）
- AMD 的 matrix instruction 缺 NVIDIA 那种 16×16 复合结构，tile layout 爆炸
- wave specialization 在 AMD 失效：静态寄存器分配让 producer wave 白占寄存器、不参与计算，限制输出 tile 大小——MI355X 上 wave-spec BF16 GEMM 只到峰值 80%

## 核心方法

**HipKittens (HK)** 保留 ThunderKittens 的 tile 数据结构和 bulk operator（mma、exp 等），但为 AMD 重新设计三项核心原语：

1. **Developer-controlled register scheduling**：绕过 HIPCC，让开发者显式 "pin" 每个 tile 到具体寄存器，能把 AGPR 作为 MFMA 输入使用。MHA backward 从 855 TFLOPS（compiler-managed）→ 1024 TFLOPS（pinned，与 AITER 1018 持平）

2. **两种 AMD 专用调度模式**（替代 wave specialization）：
   - *8-wave ping-pong*（均衡负载）：每 thread block 8 waves、每 SIMD 2 waves，成对轮换 compute↔memory 角色，条件 barrier 控制翻转；编程接近 wave spec，代码紧凑
   - *4-wave interleave*（不均衡负载）：每 SIMD 1 wave，细粒度交错 compute 和 memory 指令，像手写汇编但用 tile 原语；代码更长但对 compute/memory-heavy 工作负载收益更大
   - 实测 8-wave 已足够匹配 AITER 的 BF16 GEMM、FP8 GEMM、attention fwd；4-wave 在 MHA backward 再快 22%

3. **Chiplet-aware grid schedule**：MI355X 有 8 个 XCD（每个 32 CU + 私有 L2），共享 LLC。naive row-major 只得 36% L2 命中率，纯优化 L2 伤 LLC。HK 的 Algorithm 1 同时建模 L2 和 LLC，比 row-major 快 19%

4. **Swizzle 策略**：AMD 没法用一套 swizzle 覆盖所有 layout，HK 识别常共现的 layout 组合并为它们提供 bank-conflict-free swizzle。global→shared 的 swizzle 要对 HBM 地址做（而不是 shared 地址，和 NVIDIA TMA 不同）

## 关键结果

在 MI325X (CDNA3) 和 MI355X (CDNA4) 上验证：

- BF16 GEMM、FP8 GEMM、MHA/GQA fwd/bwd、RoPE、LayerNorm 等工作负载：**追平或超过 AMD 手写汇编 AITER**
- 手写汇编覆盖不到的场景（d=64 attention、GQA backward、memory-bound kernel）：**1.2–10× vs 所有基线**
- vs Triton BF16 GEMM 最多 3×，vs Mojo MHA fwd 2×
- 证明 tile-based 抽象可以跨 GPU 厂商，为统一 AI kernel 编程模型铺路
- 开源：https://github.com/HazyResearch/HipKittens

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、GEMM、MFMA
- **同类系统**：ThunderKittens、CuTe DSL、Gluon、Triton、TileLang、Mojo、AITER、Composable Kernel
- **同会议**：[[MLSys-2026]]
