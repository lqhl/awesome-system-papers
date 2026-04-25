---
type: paper
name: QFactory
full_title: "QFactory: Accelerating Quantized Large Language Model Serving with Qtile Graphs"
authors: [Qihao Zhang, Mingshu Zhai, Rui Sun, Jidong Zhai]
venue: ATC
year: 2025
tags: [quantization, llm-inference, compiler, gpu-kernel, qtile]
source_pdf: "[[atc2025-zhang-qihao.pdf]]"
source_md: "[[atc2025-zhang-qihao]]"
---

# QFactory: Accelerating Quantized Large Language Model Serving with Qtile Graphs (ATC 2025)

> **一句话总结**：用 Qtile 抽象 + 延迟 dequantization 的 QGraph 编译框架，单 kernel 平均比 BitBLAS 快 1.66×，集成进 [[vLLM]] 端到端解码加速 1.23×。

## 问题

低比特 [[Quantization]] LLM serving 中，weight dequantization 必须 on-the-fly 执行，而现有 DL 编译器（BitBLAS、Welder 等）采用 eager execution paradigm：碰到量化值立即 dequantize，丢失了 graph-level 重写空间，且无法利用 quantization 参数（scale、zero）的共享特性，对非对称 W4A16 比 simple-cast 慢 30%，bit-width 越低劣化越严重。

## 核心方法

- **Qtile 抽象**：把 quantized tensor 注解上 mapping function（量化算法 + 参数）和 group pattern（共享粒度：tensor / channel / block / individual），融合 weight 与 quantization 参数为一个统一对象，便于编译期推导。
- **Qtile-graph (QGraph)**：把计算图中的量化张量替换为 Qtile，dequantization 不再立即触发，可被 propagate 到下游 op。
- **Qtile Computation Transformation**：对 element-wise add 和 matmul 给出 Qtile 间的代数变换表（如 $A_{z_1} \cdot B_{z_2} = AB + (J_A B)^{z_1} + (A J_B)^{z_2} + (J_{AB})^{z_1 z_2 K}$），通过 J 矩阵的全 1 性质 + 标量塌缩，降低实际 dequant 操作数。
- **Differentiated Qtile Scheduling**：针对 GPU 多层 memory hierarchy（DRAM / L2 / shared memory / register）+ PTX cache 操作（.cg、.cs）+ Hopper TMA，给 weight tile / activation tile / quant params 各自选不同 data path，schedule (a)/(b)/(c)/(d) 视占用与 group 粒度切换。
- **Template + ML-based selector**：CUTLASS 风格模板生成 + lightweight MLP 预测 bandwidth utilization 来加速 auto-tuning。

详见 [[atc2025-zhang-qihao]]。

## 关键结果

- H100 上对 BitBLAS：W8 1.17×、W4 1.52×、W2 1.66× 加速；4-bit 上比手工优化的 Marlin 还快 1.30×。
- A100：W8 1.17×、W4 1.40×、W2 1.71×；与 Marlin 相当（1.04×）。
- 集成到 [[vLLM]] 后 Llama-2 / Qwen-2.5 端到端解码加速 1.23×。

## 相关

- **相关概念**：[[Quantization]]、[[KV-Cache]]
- **相关实体**：[[vLLM]]
- **同会议**：[[ATC-2025]]
