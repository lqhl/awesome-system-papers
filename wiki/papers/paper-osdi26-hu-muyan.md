---
type: paper
name: VTC
full_title: "VTC: DNN Compilation with Virtual Tensors for Data Movement Elimination"
authors: [Muyan Hu, Ahan Gupta, Jiachen Yuan, Vima Gupta, Taeksang Kim, Xin Xu, Janardhan Kulkarni, Ofer Dekel, Vikram Adve, Charith Mendis]
venue: OSDI
year: 2026
tags: [dnn-compilation, data-movement, virtual-tensor, gpu, llm-inference]
source_pdf: "[[osdi26-hu-muyan.pdf]]"
source_md: "[[osdi26-hu-muyan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-01-26
---

# 用虚拟张量消除 DNN 数据搬运（OSDI 2026）

> **原题**：VTC: DNN Compilation with Virtual Tensors for Data Movement Elimination

> **一句话总结**：VTC 观察到 DNN 图中大量 `Split`、`Reshape`、`ScatterND` 和 `Expand` 只重排数据，却仍触发全局内存读写；它用编译期索引映射把中间张量表示为虚拟张量，在 A100/H100 上相对最佳基线最高提速 1.93 倍、平均 1.28 倍，并平均节省 17.5% 推理显存。

## 问题与动机

现代 GPU 的计算能力增长快于内存带宽，DNN 执行逐渐受全局内存访问限制。现有编译器主要依赖布局优化和算子融合。两者都只能覆盖部分数据搬运算子：难以融合的算子仍会单独启动 kernel，并把中间结果写回、再读出全局内存。

论文用 Llama 3 8B 解码层说明这个问题。TensorRT 已经融合 QKV projection 和 FlashDecoding，但两者之间仍有多次 `Split`、`ScatterND`、`Expand`、`Transpose` 等操作；在 batch size 16、context length 4096 的设置下，这些搬运的耗时超过计算 kernel，VTC 在该子图上相对 TensorRT 达到 4 倍加速（图 2）。

## 关键观察 / 隐含假设

- **观察 1：许多数据搬运算子只改变索引，不改变元素值。** `Transpose`、`Split`、`Reshape`、`Expand` 和部分 `ScatterND` 可以表示为输出索引到输入物理地址的映射。论文据此把实际复制推迟到计算 kernel 的全局内存 I/O 阶段（§2.2、§4.1）。
  - **依赖假设**：映射在编译期已知，并且可以限制为一对一映射。
  - **可能失效场景**：真正的一对多语义、动态索引或需要原地别名语义的算子无法直接使用该表示。
- **观察 2：GPU 计算单元要求片上 buffer 中的数据连续，但全局内存访问不必完全连续。** 只要连续块大于最小合并访问粒度，部分连续的访问仍能保持较高带宽。QKV projection 中每个 attention head 的维度为 128，大于 warp size 32，因此可直接写入多个物理目标（§3.1、图 3）。
  - **依赖假设**：非连续访问的连续块足够大，额外地址计算和访存分散的代价小于被消除的搬运代价。
  - **可能失效场景**：小张量、细碎切分、不同 GPU 的合并访问规则，以及带宽已不是主瓶颈的 workload。
- **假设 1：逐次 profiling 得到的局部收益足以指导全局策略。** VTC 的虚拟张量机会图（VTOG）可能有指数级策略空间，论文用全局贪心算法并在每轮重新 profiling；其最坏图算法复杂度为 O(|V|²)，实际编译时间在测试模型上少于 10 分钟。该假设的证据强度为中：论文报告了结果，但没有给出与穷举最优策略的系统比较。

## 核心方法

VTC 将虚拟张量定义为映射函数和若干物理 tensor pointer 的元组。虚拟张量保留连续的逻辑索引空间，但每次 `load`/`store` 根据映射函数定位一个或多个物理张量。嵌套虚拟张量通过函数复合表示连续的数据重排。该抽象直接回应观察 1，避免为只重排数据的中间结果分配完整显存。

论文只改计算 kernel 的全局内存 I/O 阶段，不改片上计算阶段。VTC 在 Triton 中重载 `tl.load` 和 `tl.store`，对编译期已知的映射生成专用 Python 代码。这样既能复用现有 MatMul、attention 等 kernel，也把额外开销限制在地址计算和非完全连续的全局访问上（§4.2、§6）。

编译器为每个数据搬运算子预先定义输入输出之间的虚拟化规则。VTOG 的节点是 tensor，边表示消除一个搬运算子的可能性；冲突集合排除会破坏一对一映射的组合。随后，贪心算法按当前边际延迟收益选择可兼容的边，并对受影响的边重新 profiling，直到最大收益为负（§5.1–§5.2）。

VTC 的收益分析将映射分成完全连续、部分连续和不确定三类。完全连续的虚拟化被定理 1 判定为总是有利；部分连续访问通常保持合并访问；其余情况由真实硬件 profiling 决定。该设计把观察 2 转化为编译器的静态筛选和运行时测量。

## 设计取舍

- **消除搬运 vs 计算 kernel 速度**：虚拟化可能让 MatMul 的输出写入非连续物理地址。论文报告 VTC 的计算算子通常慢于 TensorRT，但消除搬运的收益更大（§7.4）。
- **通用自动搜索 vs 编译时间**：VTOG 覆盖比布局规则更大的搜索空间，但 profiling 成为主要编译成本。论文使用多项式时间贪心而非穷举，牺牲全局最优保证换取可部署性。
- **一对一映射 vs 算子覆盖范围**：限制一对一映射简化了 kernel 实现，却排除了需要一对多映射的语义。`Expand` 的广播通过特殊的索引偏置处理，但复杂动态映射仍是边界。
- **通用 Triton 实现 vs 硬件专用 kernel**：VTC 建在 TorchInductor/Triton 上，而 TensorRT、vLLM 可使用更成熟的 cuBLAS 或手写 kernel。H100 上强制启用一个在 A100 有利的优化会造成 8% 退化，说明 profiling 只能避免负优化，不能弥补底层 kernel 差距。

## 实验与结果

- 在单张 A100 或 H100、batch size 1 和 16 的五个模型（Llama 3、Gemma 2、EfficientViT、YOLOv11、ShuffleNet）上，VTC 相对 PyTorch、ONNX Runtime、XLA 和 TensorRT 中的最佳者最高提速 1.93 倍，平均 1.28 倍（§7.2、图 9）。
- Transformer 模型平均提速 1.36 倍，CNN 模型平均提速 1.15 倍；这与 Transformer 中数据搬运占比更高的 breakdown 相符（§7.2、图 10）。
- VTC 最高节省 60% 峰值 GPU 显存，平均节省 17.5%，对大型中间 tensor 的虚拟化贡献最大（§7.3、表 2）。
- 10 个模型与 batch 配置中有 7 个完全消除了数据搬运算子；但计算算子本身常慢于 TensorRT（§7.4）。
- 与 vLLM V1 的 Llama 3 8B 比较中，A100 上 VTC 对解码层端到端提速 1.011 倍；H100 上 profiling 选择不启用该优化，强制启用反而慢 8%（§7.5、表 3–4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 虚拟张量能覆盖现有布局优化和融合未覆盖的数据搬运 | Llama 解码层中消除 `Split`、`ScatterND`、`Expand` 等；7/10 配置完全消除搬运 | A100/H100、5 个模型、batch size 1/16 | 强 |
| 消除搬运的收益能抵消非连续 I/O 的 kernel 开销 | 端到端最高 1.93 倍、平均 1.28 倍；计算算子仍常慢于 TensorRT | 单 GPU 推理，基线为四个编译器 | 强 |
| 虚拟化可降低显存占用 | 峰值显存最高降低 60%、平均降低 17.5% | 与 PyTorch 比较，未覆盖训练和多租户服务 | 强 |
| profile-guided 贪心能避免负优化 | H100 上自动跳过会导致 8% 退化的策略 | 未与最优策略或更多 GPU 代际比较 | 中 |

## 批判性分析

### 论证链条

论文的主链条基本闭合：数据搬运只重排索引，映射函数可表达该重排；全局内存不完全连续仍可能保持合并访问；因此 kernel 可以直接读写目标物理 tensor。图 2、图 10 和端到端结果共同支持这条链条。局部结果外推到“所有不必要的数据搬运”时仍需谨慎，因为实现依赖每个 ONNX 算子的手写映射规则，且虚拟张量限定为一对一映射。

### 假设压力测试

论文主要评测静态、单 GPU、batch size 1/16 的推理图。动态 shape、动态索引、极小连续块、强烈不规则的 Scatter，以及跨 kernel 的同步和别名约束没有充分覆盖。较新的 GPU 可能提供 TMA 等批量搬运机制，非连续访问与显式异步搬运之间的收益关系未测量。多租户 SLO、故障恢复和服务端编译缓存也未讨论。

### 实验可信度

基线覆盖 PyTorch、ONNX Runtime、XLA 和 TensorRT，且加入了 vLLM 这一专用 LLM serving 系统；模型横跨 Transformer、视觉 Transformer 和 CNN。实验仍以单 GPU、静态 batch 为主，缺少长时间服务吞吐、P99、编译摊销和不同输入长度的结果。VTOG 贪心的质量也没有通过小图穷举或 oracle 对照验证。

### 系统性缺陷

虚拟 I/O 增加了 kernel 代码生成和映射维护复杂度。每种数据搬运算子都需要开发者提供规则，算子集合或语义扩展会带来维护成本。论文声称数值等价，但没有展开动态内存错误、并发写入或调试可观测性。当前 Triton 后端限制了硬件适配；论文明确指出 Blackwell 上 CUTLASS 可能更快，且没有显式处理 TMA（§9）。

## 局限与后续工作

- **局限 1**：逐轮 profiling 的编译开销可能不适合频繁变化或低延迟编译场景；论文报告所有测试模型少于 10 分钟，但没有给出逐模型、逐策略的 profiling 次数。
- **局限 2**：当前实现依赖 Triton，H100 上已出现底层 kernel 不如 cuBLAS 的案例；迁移到 CUTLASS 等后端是必要验证。
- **局限 3**：尚未显式建模 TMA 等异步多维传输。后续可比较“虚拟访问”和 TMA 搬运在不同连续块大小、shape 与 GPU 代际上的交叉点。
- **后续工作 1**：在含动态 shape、动态索引和真实服务 trace 的 workload 上，记录 P50/P99、编译摊销、显存峰值与策略稳定性，并与穷举小图 oracle 比较贪心策略的最优性损失。

## 相关

- **相关概念**：[[PagedAttention]]、[[FlashAttention]]、[[Tensor Compiler]]
- **同类系统**：[[vLLM]]、[[TensorRT]]、[[TorchInductor]]、[[Triton]]
- **同会议**：[[OSDI-2026]]
