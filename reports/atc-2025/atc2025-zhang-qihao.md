# QFactory: Accelerating Quantized Large Language Model Serving with Qtile Graphs

**作者**：Qihao Zhang, Mingshu Zhai, Rui Sun, Jidong Zhai（清华大学）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zhang-qihao
**源文件**：[[atc2025-zhang-qihao.pdf]]

---

## 一、背景

量化是加速 LLM 推理的关键技术。由于 LLM 自回归解码阶段的 memory-bound 特性，计算瓶颈主要在于从 GPU 显存加载模型参数。量化算法将模型参数压缩为低精度格式（如 FP16→INT4），显著降低显存访问量，从而提升解码速度。

为了在极低 bit-width 下保持模型精度，细粒度量化算法（如 GPTQ）引入了 asymmetric、group-wise 量化方法，使用额外的 zero point 和 scaling factor 等量化参数。这些额外参数在 on-the-fly dequantization 时引入了显著的计算和内存开销，成为新的性能瓶颈。

当前深度学习编译器（如 BitBLAS）对量化 kernel 的支持不够高效。例如，BitBLAS 编译的 asymmetric 量化 kernel 相比 simple type-casting kernel 延迟高出 30%，且在更低 bit-width 下性能下降更加严重。

---

## 二、要解决的问题

现有系统采用**即时执行（eager execution）**范式处理 dequantization：一旦遇到量化值，立即按量化算法定义进行类型转换。这种静态方法存在两个核心问题：

1. **优化搜索空间受限**：量化引入的 dequantization 操作改变了原始计算图，创造了新的图级变换机会。但现有方法不感知这些变化，直接在原始图上执行 dequantization，无法利用这些潜在的优化空间。

2. **内存带宽利用不足**：量化参数在一组权重参数间共享（group-wise），但现有方法对每个权重参数独立执行 dequantization，未利用共享属性，导致内存带宽浪费。不同 tensor tile 的数据加载策略未作区分，无法最大化整体带宽利用率。

---

## 三、洞察与设计

**关键洞察**：Dequantization 操作可以延迟执行（deferred execution），沿计算图向后续算子传播，而非在遇到量化张量时立即执行。通过将量化信息编码为张量的注解（annotation），dequantization 可以在计算图中灵活放置，从而开辟更大的优化空间。

基于此洞察，QFactory 设计了 **Qtile** 抽象——带有量化注解的 tensor tile 表示。Qtile 包含两类注解：

- **Mapping Function**：编码 dequantization 所需的全部信息，包括量化算法、scaling factor、zero point 等辅助参数。
- **Group Pattern**：描述量化参数的共享范围，提供 tensor/channel/block/individual 四种粒度。

QFactory 的编译流程：

1. **Qtile Computation Transformation（图级优化）**：将用户定义的量化程序转为 Qtile-graph（Qgraph），通过 BFS 搜索对 Qtile 沿算子传播，生成数学等价的 Qgraph 候选集。传播涉及 group pattern 变换（如通过 GCD 计算公共 group pattern）和 mapping function 变换（如在 MatMul 中利用全 1 矩阵 J 的约简性质减少 dequantization 开销）。

2. **Differentiated Qtile Scheduling（算子级优化）**：利用 GPU 多层内存层次（DRAM→L2→Shared Memory→Register），为不同 Qtile 选择差异化的数据加载路径。例如，利用 `.cg` cache operator 让权重 tile 绕过 L1 cache，为量化参数腾出 cache 空间实现数据重用；在高 occupancy 场景下牺牲 activation 的 shared memory 缓存来换取更高的 GPU 占用率。

3. **Template-based Kernel Generation + ML-based Kernel Selector**：基于 CUTLASS 风格的 CUDA 代码模板生成 kernel，利用 ILP 重叠内存访问和计算；训练轻量 MLP 预测 kernel 配置的带宽利用率，在 15 次试验内即可找到接近最优的 kernel 配置。

---

## 四、实现细节

- **Qtile 传播算法**：BFS 遍历 Qgraph 中所有算子，检查输入 tile 是否包含 Qtile 且满足变换规则，生成新的 Qtile 替换原有输出 tile，产生新 Qgraph 加入候选集。
- **MatMul 的 Qtile 变换**：两个 Qtile 相乘会产生四项求和，其中利用全 1 矩阵 J 的性质，可将 dequantization 简化为仅对一行执行后广播，甚至降为标量运算。
- **差异化调度策略**：提供 4 种调度方案（baseline / better reuse / better occupancy / fine-grained quantization），根据量化粒度和 GPU 架构自动选择。
- **快速类型转换**：实现模板函数，统一处理不同格式低 bit 整数到 FP16 的高效转换。
- **对齐优化**：通过 compile-time 常量传递矩阵形状和调优参数，消除低 bit-width 数据类型引入的非对齐条件跳转。
- **ML Kernel Selector**：离线对每个 kernel 随机采样 50 个配置进行 profiling，训练 MLP 模型以带宽利用率为回归目标，在线编译时只需对预测最优的少量（~15）配置实际测量。

---

## 五、实验结果

**实验平台**：NVIDIA V100 (PCIe, 32GB)、A100 (PCIe, 40GB)、H100 (PCIe, 80GB)

**Kernel 级性能（相对 BitBLAS 的平均加速比）**：

| GPU | W8 | W4 | W2 |
|---|---|---|---|
| H100 | 1.17× | 1.52× | 1.66× |
| A100 | 1.17× | 1.40× | 1.71× |
| V100 | 0.99× | 1.17× | 1.41× |

- 在 H100 上，QFactory 比手工优化的 Marlin kernel（W4）快 1.30×。
- 在 A100 上，QFactory 与 Marlin 相当（1.04× speedup）。

**端到端推理性能（H100, GPTQ 量化, batch size=1）**：

| 量化精度 | vs llama.cpp | vs Marlin | vs BitBLAS |
|---|---|---|---|
| 4-bit | 1.21× | 1.32× | 1.03× |
| 2-bit | 1.58× | N/A | 1.23× |

**代表性绝对速度**（H100, 4-bit）：Llama-2-7B 198.6 tok/s，Qwen-2.5-72B 36.0 tok/s。

**Batch size 扩展（H100, Asymmetric W4A16）**：

| Batch Size | BitBLAS | Marlin | QFactory |
|---|---|---|---|
| 1 | 2.19× | 2.56× | 3.44× |
| 2 | 1.46× | 2.54× | 3.18× |
| 4 | 0.87× | 2.53× | 2.52× |

---

## 六、批判性分析

1. **Batch size 增大后优势消失**：论文坦承 weight-only quantization 在 batch size 增大时从 memory-bound 转为 compute-bound，加速比下降。但论文仅在 batch size 1-4 的极小范围评估，而实际 LLM serving 中通过 continuous batching，有效 batch size 通常远大于 4。论文没有评估在典型 serving 场景（如 batch size 16-128）下 QFactory 的表现，这削弱了"加速 LLM serving"这一核心 claim 的说服力。

2. **与 Marlin 的对比不够公平**：论文在 H100 上对 Marlin 做了"必要的源代码修改"才能运行，但未详细说明修改了什么。Marlin 本身针对 Ampere 架构优化，在 H100 上的性能可能因移植不完整而偏低。在 A100（Marlin 原生支持平台）上 QFactory 仅微幅领先 1.04×，说明 QFactory 在 H100 上的大幅优势可能部分来自 Marlin 移植的不完整。

3. **仅支持 weight-only quantization**：当前主流推理框架已在大 batch 场景下广泛使用 activation-weight 联合量化（如 W8A8、W4A4），论文将此完全留作 future work，限制了 QFactory 的适用范围。

4. **端到端加速比与 kernel 加速比差距大**：Kernel 级别 1.66× 加速（W2），端到端仅 1.23×。这意味着实际 serving 场景中非量化线性层的开销、kernel launch 开销等"不透明"部分占比很大，削弱了 QFactory 的实际价值。

5. **仅评估 decoding 阶段**：论文完全没有评估 prefill 阶段的性能，而现代 LLM serving 中 prefill 和 decode 是混合调度的。

---

## 七、AI Infra / MLSys 视角

**启发与借鉴价值**：

- **Deferred execution 范式的通用性**：QFactory 提出的"延迟 dequantization 执行"思想不仅适用于量化，可以推广到其他涉及格式转换的场景（如 MoE 中的 expert 参数压缩与解压、KV cache 的量化与反量化）。核心思想是：不急于在数据产生时立即转换格式，而是将格式信息作为注解沿计算图传播，在最有利的位置再执行转换。

- **Qtile 抽象的可扩展性**：Qtile 的 mapping function + group pattern 设计提供了一种统一表示各种量化格式的方式，对于构建支持多种量化后端的通用推理框架有参考价值。

**值得跟进的方向**：

1. **将 Qtile 抽象扩展到 activation-weight 联合量化**：论文已指出这一方向。具体研究问题：当 activation 也是量化 Qtile 时，MatMul 的变换规则如何扩展？activation 的动态量化参数对调度策略有何影响？
2. **与 Tensor Core 的深度集成**：论文 batch size 扩展实验中 Marlin 在大 batch 下超越 QFactory，因为 Marlin 使用了手动优化的 MMA 指令。将 Qtile 调度与 Tensor Core 的 warp-level 矩阵运算结合是一个高价值方向。
3. **Prefill-Decode 混合场景下的自适应调度**：QFactory 的多种调度策略（better reuse / better occupancy）在不同计算模式下各有优势，可以根据当前是 prefill 还是 decode 阶段动态切换。

---

## 八、总结

QFactory 是一个面向量化 LLM 推理的编译框架，通过 Qtile 抽象将量化信息编码为张量注解，实现 dequantization 的延迟执行和灵活放置。在图级别通过 Qtile 传播搜索数学等价的计算图变换，在算子级别通过差异化内存调度最大化带宽利用率。在多代 NVIDIA GPU 上，kernel 级别平均加速 1.66×（W2），端到端推理加速 1.23×。主要局限在于仅支持 weight-only quantization 且在大 batch size 下优势减弱，适用于低 batch size 的 LLM 解码推理场景。
