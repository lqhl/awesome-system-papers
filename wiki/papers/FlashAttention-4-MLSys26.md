---
type: paper
name: FlashAttention-4
full_title: "FlashAttention-4: Algorithm and Kernel Pipelining Co-Design for Asymmetric Hardware Scaling"
authors: [Ted Zadouri, Markus Hoehnerbach, Jay Shah, Timmy Liu, Vijay Thakkar, "et al."]
venue: MLSys
year: 2026
tags: [attention, gpu-kernel, blackwell, cuda, inference]
source_pdf: "[[72b32a1f754ba1c09b3695e0cb6cde7f.pdf]]"
source_md: "[[72b32a1f754ba1c09b3695e0cb6cde7f]]"
---

# FlashAttention-4: Algorithm and Kernel Pipelining Co-Design for Asymmetric Hardware Scaling (MLSys 2026)

> **一句话总结**：针对 Blackwell B200 的 attention kernel 重设计——用 2-CTA MMA、TMEM、FMA 软件模拟 exp、条件 softmax rescale 缓解 shared-memory 和 MUFU bottleneck，BF16 上最高 1613 TFLOPS/s（71% 峰值），比 cuDNN 9.13 快 1.3×，比 Triton 快 2.7×。

## 问题

Blackwell B200 相比 Hopper H100 把 FP16/BF16 tensor core 吞吐从 1 PFLOPS 翻倍到 2.25 PFLOPS，但 shared memory 带宽和 MUFU 指数单元没跟上。roofline 分析显示 attention 的 softmax exponential 与 SMEM 流量合并后超过 MMA 时间 25–60%，成为真正瓶颈。[[Flash-Attention]] 3 针对 H100 的 warp specialization 无法直接迁移，H100 的 MMA 指令甚至没 forward compatibility。

## 核心方法

针对三类新瓶颈各出一招：

1. **新 pipeline**：利用 Blackwell 完全异步 MMA 直接写 TMEM（不占寄存器），配合更大 tile 128×128。前向沿用 ping-pong 两 warp group 做 softmax，第三个 correction warpgroup 专门处理 rescaling；TMEM 分区选 "两份 S + 两份 P overlap" 便于流水线起步。
2. **指数函数 FMA 模拟**：B200 MUFU 只有 16 ops/clock/SM，8192 的 MMA 吞吐形成严重不均衡。用 Cody-Waite range reduction + 度数 3-5 多项式在 FMA 单元上算 2^x，BF16 精度下误差被量化噪声 (~3.9e-3) 吞噬。对每行 10-25% entries 走 emulation，其余仍用 MUFU，避免寄存器压力。
3. **Conditional softmax rescaling**：仅当 max 增量 > τ（通常 log2(256)=8）才 rescale `O_{j-1}`，其他情况跳过向量乘。
4. **dQ/dK/dV backward**：用 2-CTA MMA，两个 CTA 每个只 stage 一半 B 操作数到 SMEM，把 atomic reductions 数量减半。还提供 deterministic mode 以支持 RL 训练重现。

整个 kernel 用 **CuTe-DSL 嵌 Python** 实现，编译比 C++ 模板快 20-30×。

## 关键结果

- B200 BF16 对比 cuDNN 9.13 最高 1.3×，对比 Triton 最高 2.7×。
- 长序列下峰值 ~1613 TFLOPS/s（71% 理论峰值）。
- 多项式度 3 在 BF16 输出下与硬件 MUFU.EX2 在 99% 输入上 1-ULP 内一致。
- 编译速度比 CUTLASS C++ 模板快 20-30×。
- 开源：https://github.com/Dao-AILab/flash-attention/tree/main/flash_attn/cute。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]
- **同会议**：[[MLSys-2026]]
