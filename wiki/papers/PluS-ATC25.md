---
type: paper
name: PluS
full_title: "PluS: Highly Efficient and Expandable ML Compiler with Pluggable Graph Schedules"
authors: [Ruofan Wu, Zhen Zheng, Feng Zhang, Chuanjie Liu, Zaifeng Pan, et al.]
venue: ATC
year: 2025
tags: [ml-compiler, graph-optimization, kernel-fusion, gpu, pattern-matching]
source_pdf: "[[atc2025-wu-ruofan.pdf]]"
source_md: "[[atc2025-wu-ruofan]]"
---

# PluS: Highly Efficient and Expandable ML Compiler with Pluggable Graph Schedules (ATC 2025)

> **一句话总结**：用 loop-centric 的 +Graph 子图抽象 + 专家可维护的 pattern warehouse，让 ML 编译器即插即用集成 FlashAttention、CUTLASS 等专家 kernel，A100 上端到端比 TorchInductor 快 4.04×、比 TensorRT 快 1.77×。

## 问题

ML 编译器（[[XLA]]、TorchInductor、BladeDISC、TensorRT）的图变换规则是 hard-coded 在编译器里的，每出一个新优化技术（[[Flash-Attention]]、fused MatMul-LayerNorm-MatMul）都要大改代码、追不上手写 kernel 的性能。模板类编译器（AITemplate）允许用户加优化但是按 operator 组合精确匹配 pattern，模型架构稍微一变（比如 T5 的 RMSNorm、去掉 Bias）就要重写 250+ 行前后端代码。

## 核心方法

PluS 把图变换从编译器里解耦成 pluggable pattern warehouse：

- **+Graph 抽象**：用 `+Loop` 表达每个 operator 的循环骨架（size、parallelism、key operation），通过四种 transformation primitive（merge keep / merge alter parallelism / new loop / nested coalesce）把多个 operator 的 +Loop 合并成子图的 +Graph。不同 operator 组合（比如 Add 替换 Sub）若 loop 结构相同就映射到同一 +Graph，共享 codegen schedule。
- **Pattern matching**：从 skeleton operator（MatmulOp、ReduceOp 这类有 non-parallelizable +Loop 的 op）出发贪心扩展 prologue/epilogue，迭代查询 pattern warehouse；同时支持「partial match」让子图能继续生长成完整 pattern。
- **+Code 接口**：专家用 `data placeholder / compute / writeback` 三类语句定义 codegen 模板，编译器负责填充 trivial 算子、地址、加载代码；后端集成 [[CUTLASS]]、ByteTransformer、[[Flash-Attention]]、FlashInfer。
- 支持 dynamic shape（用 symbolic 维度），运行时由模板里的 routing 逻辑选实现。

深度细节回 [[atc2025-wu-ruofan]]。

## 关键结果

- BERT/ALBERT/GPT2/T5/ViT 五个模型平均：A100 上比 TorchInductor 快 4.04×、比 TensorRT 快 1.77×；RTX 4090 上 4.59× / 2.01×。
- 比 AITemplate 平均快 7.8%，且能编译 AITemplate 不支持的 T5（T5LayerNorm 在 AITemplate 需 1701 LoC，PluS 仅 18+129 LoC）。
- BERT 子图比 TensorRT 平均快 1.53×、比 AITemplate 快 1.07×。
- 编译开销：缓存命中 18-25s，首次编译 1-2 分钟，内存增加 130-190 MB。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Kernel-Fusion]]、[[ML-Compiler]]
- **同类系统**：[[TVM]]、AITemplate、TorchInductor、TensorRT、BladeDISC
- **同会议**：[[ATC-2025]]
