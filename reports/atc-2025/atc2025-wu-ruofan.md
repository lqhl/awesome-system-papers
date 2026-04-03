# PluS: Highly Efficient and Expandable ML Compiler with Pluggable Graph Schedules

**作者**：Ruofan Wu (Renmin University of China), Zhen Zheng (Microsoft), Feng Zhang (Renmin University of China), Chuanjie Liu (Microsoft), Zaifeng Pan (Renmin University of China), Jidong Zhai (Tsinghua University), Xiaoyong Du (Renmin University of China)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wu-ruofan
**源文件**：[[atc2025-wu-ruofan.pdf]]

---

## 一、背景

ML 编译器在将 DNN 模型部署到不同硬件平台时扮演着关键角色。编译器通常将模型转换为由算子组成的计算图，并通过图变换技术（如算子融合）来提升性能。当前 DNN 架构呈现"趋同但持续演进"的趋势——Attention 机制成为主流，但具体实现不断变化（如 RMSNorm 替代 LayerNorm、SwiGLU 替代 GELU）。与此同时，新的图优化技术（FlashAttention、fused Matmul-LayerNorm-Matmul）不断涌现。

现有 ML 编译器分为两类：**嵌入式编译器**（如 XLA、TorchInductor、TensorRT）将图变换规则硬编码在编译器内部，添加新优化需要大量修改编译器代码；**模板式编译器**（如 AITemplate）允许用户自定义子图匹配，但依赖精确的算子组合匹配，对模型结构的微小变化适应性差。

---

## 二、要解决的问题

1. **嵌入式编译器缺乏灵活性**：图变换规则硬编码在编译器中，支持新的子图优化（如 FlashAttention）需要大规模修改编译器内部代码，开发代价高、响应速度慢。
2. **模板式编译器缺乏泛化能力**：AITemplate 等依赖精确的算子组合匹配，如支持 `gemm_rcr_bias_gelu` 但不支持 `gemm_rcr_gelu`（去掉 Bias），每个新变体都需要单独定义前端和后端代码。T5 模型因缺少 T5LayerNorm 模板而无法被 AITemplate 支持。
3. **重复劳动**：结构相似但算子组合略有不同的子图需要反复定义代码生成模板，无法复用已有的 codegen schedule。
4. **动态 shape 支持不足**：AITemplate 等不支持动态 shape，限制了实际部署的灵活性。

---

## 三、洞察与设计

**关键洞察**：子图的 codegen schedule 主要由关键算子（如 MatMul、Reduce）的循环结构决定，而非所有算子的精确组合。例如，将 Add 替换为 Sub 不改变循环结构，因此不需要重新定义 codegen schedule。不同算子组合只要共享相同的循环骨架（loop skeleton），就可以复用相同的代码生成方案。

基于此洞察，PluS 设计了三个核心组件：

### +Graph：基于循环特征的子图抽象

+Graph 是子图的轻量级标识符，由嵌套的 +Loop 组成。每个 +Loop 有三个属性：
- **Size**：循环大小（常量或符号化动态 shape）
- **Parallelism**：可并行 / 不可并行（决定是否存在循环迭代间的数据依赖）
- **Operation**（可选）：关键操作（如 dot product、reduceMax）

+Graph 只关注关键算子的循环特征，忽略 trivial 算子，使得不同算子组合映射到相同的 +Graph。

四个变换原语（Primitive）定义了多个算子合并时 +Loop 的变换规则：
1. **Merge without Altering**：size 和 parallelism 相同时直接合并
2. **Merge with Parallelism Modification**：size 相同但 parallelism 不同时，合并为 non-parallelizable
3. **Transition to New Loop**：prev_loop 为 non-parallelizable 时，创建新的 +Loop
4. **Nested Loop Collapsing**：折叠连续的同类嵌套 +Loop

### Pattern Warehouse：可插拔的模式仓库

专家维护一个模式仓库，将 +Graph 映射到对应的代码模板。仓库支持动态增删，用户可以通过两种方式添加模式：(1) 提供 `torch.nn.Module` 和对应代码；(2) 直接定义 +Graph 和 +Code 模板。

### 子图识别算法

采用贪心扩展策略，从 skeleton 算子出发（MatMul、Reduce 等非可并行循环算子），向 prologue/epilogue 方向迭代扩展，每步生成 +Graph 并与仓库中的模式进行匹配。匹配分完美匹配和部分匹配，部分匹配允许继续扩展。

---

## 四、实现细节

- **框架集成**：基于 PyTorch 的 TorchDynamo 后端实现，以 `torch.fx.GraphModule` 为输入，利用 Hidet 的 API 解析计算图
- **代码生成**：+Code 接口提供三种语句类型——data placeholder、compute、data write-back。编译器遍历 +Loop 叶节点生成代码，填充 trivial 操作
- **Kernel 集成**：集成了 CUTLASS、ByteTransformer、FlashAttention、FlashInfer 等高性能实现
- **动态 shape**：使用符号化类型表示 shape，代码模板将 shape 视为运行时变量，专家可在模板中编写基于 shape 的路由逻辑
- **编译开销**：模型缓存后 18–25 秒（主要为 NVCC 编译），首次编译 1–2 分钟；内存开销 130–190 MB（CPU 端）

---

## 五、实验结果

**平台**：NVIDIA A100 PCIe 80GB、RTX 4090；AMD EPYC 7V13 / Intel Xeon Gold 5318Y CPU

**基线**：TorchInductor v2.4.0、TensorRT v10.5.0（ONNX Runtime v1.18.0）、AITemplate v0.3.dev0

**模型**：BERT-base、ALBERT、GPT-2、T5、ViT；batch size = 1 / 16，seq_len = 128

### 端到端推理延迟

| 对比基线 | A100 平均加速 | RTX 4090 平均加速 |
|---|---|---|
| vs TorchInductor | 4.04× | 4.59× |
| vs TensorRT | 1.77× | 2.01× |
| vs AITemplate | ~7.8% 提升 | ~7.2% 提升 |

### Fusion Rate（算子融合率）

| 模型 | 原始算子数 | TorchInductor | TensorRT | AITemplate | PluS |
|---|---|---|---|---|---|
| BERT | 635 | 195 | 107 | 88 | 87 |
| GPT2 | 630 | 171 | 126 | 89 | 87 |
| T5 | 1460 | 364 | 247 | 不支持 | 220 |
| ViT | 655 | 201 | 105 | 90 | 87 |

PluS 相比 TorchInductor 和 TensorRT 融合率分别提升 2.08× 和 1.25×。

### 可移植性（T5 案例）

- AITemplate 不支持 T5（缺少 T5LayerNorm 模板）
- AITemplate 添加新子图需 250+ LoC（无 Bias 变体）或 1701 LoC（T5LayerNorm 全套）
- PluS 仅需 18 LoC 定义 +Graph + 129 LoC 代码模板，后续变体（如 zero-centered gamma）无需额外代码

---

## 六、批判性分析

1. **评估模型过于陈旧且规模偏小**：所有评估模型（BERT-base、ALBERT、GPT-2、T5、ViT）均为较早期的 Transformer 架构，未包含当前主流的大规模生成模型（LLaMA、Mistral、GPT-4 级别）。这些模型的子图结构相对简单，无法验证 PluS 在更复杂架构（如 MoE、GQA/MQA、Sliding Window Attention）上的表现。

2. **仅评估推理场景**：论文只测了推理延迟，未讨论训练场景。训练涉及反向传播、梯度累积、混合精度等更复杂的图变换需求，PluS 的 +Graph 抽象是否适用于训练图仍不清楚。

3. **加速倍数的不对称来源**：vs TorchInductor 的 4.04× 加速主要来自 TorchInductor 的融合能力弱（规则过于保守），而非 PluS 本身的算法优势。vs AITemplate 仅 7.8% 提升，说明 PluS 的主要贡献在可扩展性而非性能。但论文标题和摘要的 "Highly Efficient" 措辞给人的印象是性能大幅领先。

4. **Pattern Warehouse 的维护成本被低估**：论文强调 PluS 减少了专家的工作量（18 LoC vs 250 LoC），但 pattern warehouse 本身的质量和完备性仍然依赖专家持续维护。论文未讨论仓库规模增长后的模式冲突、匹配歧义等问题。

5. **贪心匹配策略的局限**：贪心扩展可能导致次优的子图划分。论文提到若算子 A 同时可与 B 或 C 融合则先遇到谁就融合谁，但未证明这种策略在所有情况下都能产生接近最优的结果。

6. **动态 shape 评估缺失**：论文声称支持动态 shape，但实验中 TorchInductor 的动态 shape 被禁用（"due to its poor performance"），实际上并未公平对比动态 shape 场景下各编译器的性能。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴

- **循环骨架作为子图等价类的思路**值得借鉴：在 LLM 推理引擎（如 vLLM、SGLang）的 kernel 选择中，可以用类似的循环特征抽象来自动匹配不同 Attention 变体（GQA、MQA、MLA）到同一组 CUDA kernel，减少手动适配工作。
- **可插拔 codegen 架构**：当前主流推理框架的 kernel 集成方式仍然较为硬编码（if-else 选择 FlashAttention / FlashInfer / cuBLAS），PluS 的 pattern warehouse 模式提供了一种更系统化的 kernel 调度抽象。

### 局限与跟进方向

- **LLM 推理的核心挑战未触及**：当前 LLM 推理的性能瓶颈在 KV cache 管理、连续批处理（continuous batching）、投机采样（speculative decoding）等系统层面的优化，而非纯粹的算子融合。PluS 的图级优化与这些系统级优化是正交的。
- **与 Triton 生态的关系**：Triton 已成为自定义 GPU kernel 的主流工具，PluS 的 +Code 模板是否能与 Triton kernel 无缝集成？这是实际落地的关键问题。
- **训练场景扩展**：将 +Graph 抽象扩展到训练图（含反向传播、All-Reduce 通信算子融合）是一个有价值的方向，但挑战在于训练图的动态性更强（gradient checkpointing、动态 loss scaling）。

### 可操作的研究切入点

将 PluS 的 loop-centric pattern matching 思路应用于 LLM serving 中的 prefill/decode 阶段 kernel 自动选择——不同阶段的 workload 特征（compute-bound vs memory-bound）对应不同的最优 kernel 实现，可以用 +Graph 风格的抽象来系统化这个选择过程。

---

## 八、总结

PluS 是一个支持可插拔图调度的 ML 编译器，核心创新在于提出了基于循环特征的子图抽象 +Graph，使得不同算子组合但相同循环结构的子图可以复用同一 codegen schedule。相比嵌入式编译器（TorchInductor、TensorRT）有显著的融合率和性能优势，相比模板式编译器（AITemplate）在可扩展性上大幅胜出，且支持动态 shape。主要局限在于评估模型规模偏小、仅覆盖推理场景，且 pattern warehouse 的长期维护成本和贪心匹配策略的最优性未被充分论证。
