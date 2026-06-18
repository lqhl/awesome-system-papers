---
type: paper
name: Flashlight
full_title: "Flashlight: PyTorch Compiler Extensions to Accelerate Attention Variants"
authors: [Bozhi You, Irene Wang, Zelal Su Mustafaoglu, Abhinav Jangda, Angélica Moreira, et al.]
venue: MLSys
year: 2026
tags: [pytorch-compiler, attention-variants, triton, kernel-fusion, torchinductor]
source_pdf: "[[b53b3a3d6ab90ce0268229151c9bde11.pdf]]"
source_md: "[[b53b3a3d6ab90ce0268229151c9bde11]]"
---

# Flashlight: PyTorch Compiler Extensions to Accelerate Attention Variants (MLSys 2026)

> **一句话总结**：在 TorchInductor 中加三类图重写（结构化融合 + 代数变换 + tiling-aware 维度消除），让 `torch.compile` 自动为任意 PyTorch 编写的 attention 变体生成 [[Flash-Attention]] 风格融合 Triton kernel，性能对齐甚至超过 FlexAttention。

## 问题

[[Flash-Attention]] 硬编码 vanilla attention 的手工 kernel；新 attention 变体（differential attention、Evoformer 行列门控自注意力、AlphaFold IPA、RSA）跑不了。FlexAttention 用 `score_mod` 静态模板能覆盖一部分，但不支持数据依赖、多矩阵乘法交织的复杂变体。直接 `torch.compile` 又缺少 reduction 融合、跨内存边界的复杂 operator 融合。

## 核心方法

Flashlight 把 attention 内核优化从工程师手工活变成编译优化问题。扩展 TorchInductor：

1. **统一 reduction IR**：引入能表达 matmul 为 loop+reduction 的 IR，让 matmul 可以与其他 reduction（max、softmax）一同做代数变换。
2. **代数语义 reduction**：捕获 reduction 的可换/结合/可分配性质，支持把 stable softmax 变换成 online softmax（关键 FlashAttention 技巧）。
3. **Logical grid dimensions**：让 tiled dimension 之间也能融合。

三类全局图重写：
- **Structural fusion + dimension demotion**：把 matmul 后接 max() 的维度降级，融合 matmul + simple reduction。
- **Semantic fusion + algebraic transformation**：stable softmax → online softmax 的自动改写，融合 `softmax(QK^T/√d)`。
- **Structural fusion + tiling-aware dimension elimination**：融合连续 matmul，如 `softmax(QK^T/√d) @ V`。

用户只要 `torch.compile` 一个 flag，写原生 PyTorch 代码即可，无需 `block_mask` 或 mask 缓存等 FlexAttention 样板。

## 关键结果

- 在 H100 / A100 上评估，覆盖 sliding window、differential、Evoformer 行列门控、IPA、RSA 等变体。
- 对 FlexAttention 能表达的变体：Flashlight 生成代码性能相当或更快。
- 对所有变体：显著快于默认 `torch.compile`。
- **AlphaFold Evoformer 行列门控自注意力**：kernel 时间 > **5×** 加速，端到端推理延迟下降 **6%–9%**。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]
- **同类系统**：FlexAttention、FlashInfer、TorchInductor
- **同会议**：[[MLSys-2026]]