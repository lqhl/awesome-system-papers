---
type: paper
name: MixLLM
full_title: "MixLLM: LLM Quantization with Global Mixed-precision between Output-features and Highly-efficient System Design"
authors: [Zhen Zheng, Xiaonan Song, Chuanjie Liu]
venue: MLSys
year: 2026
tags: [quantization, llm-inference, mixed-precision, gpu-kernel, ai-infra]
source_pdf: "[[2723d092b63885e0d7c260cc007e8b9d.pdf]]"
source_md: "[[2723d092b63885e0d7c260cc007e8b9d]]"
---

# MixLLM: LLM Quantization with Global Mixed-precision between Output-features and Highly-efficient System Design (MLSys 2026)

> **一句话总结**：W4.4A8 混合精度量化，按「全局显著性」给 ~10% 输出通道分配 8-bit、其余 4-bit，配合 two-step dequantization 和 fast I2F 转换复用 int8 Tensor Core，Llama 3.1 70B PPL 退化从 SOTA 的 ~0.5 降至 <0.2，MMLU-Pro 平均提升 0.93。

## 问题

[[Quantization]] 要同时满足精度、显存、系统效率三角约束，但已有方案各有短板：
- **Weight-only**（GPTQ/AWQ）解决显存但 4-bit 精度退化明显，且大 batch 下因 dequantization 开销反而降速。
- **Weight-activation**（SmoothQuant/QoQ）能用低 bit 计算单元但激活难量化、精度更差。
- **Outlier 分离 / mixed-precision**（SpQR/Atom）在层内局部识别高显著元素，难以覆盖不同层间重要性差异，且非结构化稀疏计算效率低。

如何在一个方案里覆盖精度、显存和系统效率的「triangle」？

## 核心方法

**1. 全局显著性识别的输出通道混合精度**

- 对每个 linear 层的每个输出 channel 用 Taylor 一阶+二阶（以 Fisher 信息近似 Hessian）估算「量化后对模型最终 loss 的贡献」，得到一个标量显著性 $S_c$。
- 所有层、所有 channel 的 $S_c$ 一起排序，top $N_{\text{largebit}}$ 走 8-bit，其余走 4-bit。不同层自动得到不同比例的 8-bit channel（图 2 显示差异巨大）。
- 相比 Atom 的输入特征 mixed-precision，输出特征之间自然 disjoint，对 [[Tensor-Parallelism]] 和 kernel 切分非常友好。

**2. 算法-系统协同的量化配置**

- 激活用 **8-bit 对称 group-wise**（4-bit 激活对精度帮助大但对大 MatMul 的算力省得少，推导自 compute intensity 公式）。
- 权重用 **4-bit 非对称 group-wise**（非对称对 4-bit 精度至关重要）。

**3. Two-step dequantization + fast I2F 软件流水**

- 先在 int8 域做 $(W_q - z) \cdot A_q$（不溢出，仍走 int8 [[Tensor-Core]]），再乘以 $s_w \cdot s_a$ 做最后的 float 还原。
- I2F 指令贵；利用整数和 float 二进制在某连续区间内等价的性质，把 I2F 替换为一次加 bias 再减 bias 的 float subtraction，并把加法 fuse 进 mma 指令的 accumulator 初始化——省了 >20 TOPS（A100, 512×4096×4096）。
- 软件流水重叠 HBM→shared memory load、dequant、MatMul。

## 关键结果

- **精度**：仅用 ~10% 的 channel 8-bit（W4.4A8），Llama 3.1 70B 上 PPL 增量从 SOTA 的 ~0.5 降到 <0.2；三大流行模型 MMLU-Pro 平均比 SOTA 高 0.93。
- **精度 vs 4-bit 方法**：W4.4A8 精度全面超过所有 4-bit weight-only 方案。
- **系统效率**：在大 batch 下同时超过 SOTA W4A16（83% float16）和 W4A8 QoQ，达到 SOTA 系统效率。
- **Fast I2F 单项贡献**：对 512/4096/4096 quantized MatMul 在 A100 上提升 >20 TOPS。

## 相关

- **相关概念**：[[Quantization]]、[[Tensor-Core]]、[[Chunked-Prefill]]、[[Continuous-Batching]]
- **同类系统**：Atom、QoQ、GPTQ、AWQ、SmoothQuant、QuaRot
- **同会议**：[[MLSys-2026]]
