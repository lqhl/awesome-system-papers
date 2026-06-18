---
type: paper
name: FlashAttention-4
full_title: "FlashAttention-4: Algorithm and Kernel Pipelining Co-Design for Asymmetric Hardware Scaling"
authors: [Ted Zadouri, Markus Hoehnerbach, Jay Shah, Timmy Liu, Vijay Thakkar, Tri Dao]
venue: MLSys
year: 2026
tags: [attention, blackwell, cuda, flash-attention, kernel]
source_pdf: "[[72b32a1f754ba1c09b3695e0cb6cde7f.pdf]]"
source_md: "[[72b32a1f754ba1c09b3695e0cb6cde7f]]"
---

# FlashAttention-4: Algorithm and Kernel Pipelining Co-Design for Asymmetric Hardware Scaling (MLSys 2026)

> **一句话总结**：针对 Blackwell B200 上 tensor core 翻倍但 SMEM/MUFU 不变的不对称缩放，FA-4 用 TMEM 异步 MMA、FMA 模拟 exp、conditional softmax rescaling 与 2-CTA backward，BF16 最高 1613 TFLOPs/s（71% 峰值），比 cuDNN 9.13 快 1.3×、Triton 快 2.7×。

## 问题

Hopper 上 [[Flash-Attention]]-3 优化异步 MMA，但 Blackwell 瓶颈从 matmul 转向 shared memory traffic 与 exponential unit（roofline 显示可超 MMA 25–60%）。

## 核心方法

**Forward pipeline**：双 warpgroup ping-pong softmax 与 MMA；P 经 TMEM 传递；correction warpgroup 把 rescale 移出 critical path。

**Exp 瓶颈**：10–25% 元素用 Horner FMA 多项式算 2^x，其余走 MUFU；degree-3 与 hardware BF16 误差相当。

**Conditional rescaling**：仅当 \(m_j - m_{j-1} > \tau\)（默认 log2(256)）才 rescale，减 vector mul。

**Backward**：TMEM 存中间量减 SMEM；2-CTA MMA  halve dQ atomic；CuTe-DSL Python 实现，编译快 20–30×。

## 关键结果

- B200 BF16：最高 **1613 TFLOPs/s**（~71% 理论峰值）
- vs cuDNN 9.13 / Triton：**1.3× / 2.7×**
- Backward SMEM 3328 cycles > MMA 2560 > exp 1024（M=N=d=128）

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、[[KV-Cache]]
- **同类系统**：FlashAttention-3、cuDNN attention、Triton
- **同会议**：[[MLSys-2026]]