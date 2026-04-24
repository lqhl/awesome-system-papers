---
type: paper
name: BOOST
full_title: "BOOST: Bottleneck-Optimized Scalable Training Framework for Low-Rank Large Language Models"
authors: [Zhengyang Wang, Ziyue Liu, Ruijie Zhang, Avinash Maurya, Paul Hovland, "et al."]
venue: MLSys
year: 2026
tags: [low-rank, tensor-parallelism, training, bottleneck, gpu-utilization]
source_pdf: "[[fe9fc289c3ff0af142b6d3bead98a923.pdf]]"
source_md: "[[fe9fc289c3ff0af142b6d3bead98a923]]"
---

# BOOST: Bottleneck-Optimized Scalable Training Framework for Low-Rank LLMs (MLSys 2026)

> **一句话总结**：BOOST 为低秩瓶颈架构（CoLA / LORO / LaX）设计 Bottleneck-aware Tensor Parallelism——把 TP chunk 边界移到瓶颈 narrow 处，在低维 r 上做 collective 而非大维 d；相比 full-rank baseline 加速 **1.46–1.91×**，相比 vanilla TP **1.87–2.27×**。

## 问题

低秩瓶颈架构（把 d×d 替换为 d×r, r×d 两层）能同时减少参数、显存、计算量，精度损失小。但这些工作都只在小规模（≤7B，单卡能放下）验证过。按 Megatron-LM 的 full-rank [[Tensor-Parallelism]] 做 naive 适配，会导致：

1. **通信爆炸**：瓶颈层更深→sync point 翻倍，vanilla TP 每个 decoder block 通信量从 2bsd 涨到 5bsd + 2bs·d_ff（d_ff ≈ 4d 时高 6.5×）
2. **GPU 利用率暴跌**：vanilla TP 沿 r 维切，GEMM reduction dimension 进一步缩小，arithmetic intensity 仅 full-rank TP 的 0.2× → 进入 memory-bound

## 核心方法

**Bottleneck-aware Tensor Parallelism (BTP)**：
- 把 TP chunk 边界从"一对瓶颈层"移到"上投影 + 下投影"的组合：up-projection (r×d) column-parallel，下一 down-projection (d×r) row-parallel
- **沿大维 d 切分**而非小维 r，保 GEMM reduction 大、AI 高
- **在低秩 r 上做 collective**：payload 从 [b,s,d] 降到 [b,s,r]，per block 总量 7bsr = (7r/2d)·V_full——r = d/4 时相比 vanilla TP 降 **5.7×**、甚至比 full-rank TP **低 1.14×**

**Online RMSNorm**：
- RMSNorm 原本是 sharded-unsafe（需全局 mean/var），加 sync 会多一次小 payload collective、latency-dominated
- 借鉴 FlashAttention online-softmax：先用 local RMS 做归一化 + GEMM，把 local stat 和 GEMM 的 all-reduce **融合**，接着用 $\alpha = \text{RMS}_{\text{local}} / \text{RMS}_{\text{global}}$ 做 per-row 修正，数学等价

**Linear Layer Grouping**：
- QKV 和 gate+up 的 batched-GEMM 融合：输入不同时用 batched GEMM over (input, weight) pairs
- 降低 kernel launch、减少 X 的重复读取，提高 per-call collective payload

**Comm-free Low-rank Activation Checkpointing**：
- 只保存低秩 activation（r 维），BTP 的 chunk 边界正好与 checkpoint interval 对齐
- re-forward 完全在 chunk 内，**无需额外 collective**（vanilla TP 需一次额外同步）

## 关键结果

- **1.46–1.91×** 加速 vs full-rank baseline；**1.87–2.27×** vs vanilla low-rank TP
- NERSC-Perlmutter 4×A100 per node、up to 4 nodes（16 GPUs）
- 模型规模 1B/3B/7B/13B/30B LLaMA-2，bf16，sequence 4096
- MLP 块 BTP 的 arithmetic intensity 是 vanilla TP 的 **2.5×**
- 集成到 Nanotron；支持 CoLA / LORO / LaX / SVD；可与 PP、DP、ZeRO 叠加

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、Low-Rank、Activation-Checkpointing、[[Flash-Attention]]
- **同类系统**：Megatron-LM、Nanotron、DeepSpeed、TorchTitan、CoLA、LORO、LaX、ReLoRA、SLTrain
- **同会议**：[[MLSys-2026]]
