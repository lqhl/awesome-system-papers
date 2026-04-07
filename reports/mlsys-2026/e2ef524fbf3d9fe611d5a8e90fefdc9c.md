# Agentic Operator Generation for ML ASICs

**作者**：Alec M. Hammond, Aram Markosyan, Aman Dontula, Simon Mahns, Zacharias Fisches, Dmitrii Pedchenko, Keyur Muzumdar, Natacha Supper, Mark Saroufim, Joe Isaacson, Laura Wang, Warren Hunt, Kaustubh Gondkar, Roman Levenstein, Gabriel Synnaeve, Richard Li, Jacob Kahn, Ajit Mathews（Meta / FAIR, Meta Superintelligence Labs）
**会议**：MLSys 2026
**链接**：[arXiv](https://arxiv.org/abs/2512.19077)
**源文件**：[[e2ef524fbf3d9fe611d5a8e90fefdc9c.pdf]]

---

## 一、背景

随着 AI 和 ML 工作负载的爆发式增长，数据中心对高效加速器硬件的需求日益迫切。行业正大量投资定制 ASIC 加速器以降低总体拥有成本——例如 Meta 的 MTIA（Meta Training and Inference Accelerator）在服务推荐模型时相比 GPU 降低了 44% 的成本。然而每个新加速器平台都需要大量工程投入来构建与 PyTorch 等框架兼容的软件栈，尤其是需要实现大量的 ATen 算子内核。算子覆盖率（operator coverage）——即有多少 ATen 算子能在新硬件上原生执行——是新加速器平台能否实用的关键瓶颈。

此前的内核生成工作主要聚焦于少量高频关键算子的性能优化，而非全面覆盖。这导致新硬件平台的 PyTorch 后端搭建仍是一项耗时数月的手工工程。

---

## 二、要解决的问题

1. **算子覆盖的工程瓶颈**：PyTorch ATen 包含数百个算子，为新加速器逐一手写内核成本极高，且难以覆盖所有数据类型、张量形状和参数模式。
2. **硬件特异性语义的学习难度**：MTIA 等 ASIC 有独特的硬件约束（如 32 字节对齐内存访问、禁用 scatter store 等），现成的 Triton 代码无法直接使用，需要基于编译器和硬件反馈进行适配。
3. **"作弊"问题**：已有的 LLM 内核生成方法常通过调用其他未实现的 PyTorch 算子或将计算分发到 CPU 来"伪实现"，无法产生真正可用的内核。
4. **测试不充分**：先前工作的测试规模小，无法保证在生产环境中不同数据类型、形状和参数组合下的正确性。

---

## 三、洞察与设计

**关键洞察**：对于新加速器平台，LLM 不需要预先知道硬件的全部规格文档——只要有足够的编译器、linter 和调试器的执行反馈，LLM 就能通过 in-context learning 逐步"蒸馏"出硬件特定的 Triton 语义，从而生成正确的内核代码。

基于这一洞察，TritorX 将内核生成设计为一个有限状态机（FSM）驱动的迭代反馈循环：

- **初始提示**：仅提供 ATen 算子的 docstring 和三个手工编写的参考内核示例（exp、argmax、diag），不提供完整的 MTIA 硬件文档。
- **自定义 Linter**：防止"作弊"（禁止调用其他未实现的 torch 算子、禁止 CPU/CUDA 数据迁移、禁止 eval/exec 等动态执行），同时检查 Triton MTIA 方言的合法性。
- **JIT 编译与测试**：通过 Triton JIT 在真实 MTIA 硬件或 QEMU 模拟器上编译和执行，获得编译错误、运行时崩溃或精度偏差的反馈。
- **反馈分层处理**：编译错误通过辅助 LLM 总结长日志以节省上下文窗口；运行时崩溃通过 LLDB 调试器提取回溯信息；精度错误通过对比 CPU 参考输出和 MTIA 输出的摘要来定位。
- **FSM 而非 Agent 架构**：选择 FSM 而非自由 agent 的 tool-calling，因为 FSM 在生产环境中更易调试、有明确的执行保障。

---

## 四、实现细节

- **FSM 状态流**：Generate Kernel → Lint → Compile → Test → Feedback → (循环或退出)。每个算子独立生成，可大规模并行。
- **LLM 配置**：使用 Code World Model (CWM) 或 GPT-OSS 120B 作为生成模型，Llama-4-Maverick 作为编译日志总结模型。上下文长度 131,072 tokens，temperature 1.0。
- **测试框架**：采用 PyTorch OpInfo 作为主要测试套件，覆盖每个算子的多种数据类型（bfloat16、float16、float32、int32、int64）、张量形状和参数组合，总计 20,000+ 测试用例。仅当算子通过全部对应测试时才算覆盖。
- **生产数据测试**：额外使用 `__torch_dispatch__` 从真实模型（NanoGPT、DLRM、内部推荐模型）的前向/反向传播中捕获实际输入数据，作为补充测试。
- **Linter 实现**：基于 Python AST 解析 + regex 匹配的规则系统，包含 tl 和 torch 模块的白名单、作用域限制（tl.* 只能在 kernel 函数中使用）、禁止设备迁移方法和动态代码执行。
- **规模化部署**：在 200 台生产 MTIA 设备上分发生成任务，95% 的算子在 2 小时内完成，尾部任务需额外 6-8 小时。
- **运行参数**：每个算子最多 3 次尝试（dialog session），每次尝试最多 15 次 LLM 调用。

---

## 五、实验结果

### 整体覆盖率

| 配置 | 覆盖率 |
|------|--------|
| CWM（单次运行） | 55.3% |
| GPT-OSS 120B（单次运行） | 72.0% |
| 多次运行聚合（全局） | **84.7%**（481/568 算子） |

### 按算子类别覆盖率

| 算子类别 | 数量 | CWM | GPT-OSS |
|----------|------|-----|---------|
| Shape Manipulation | 75 | 96.0% | 96.0% |
| Elementwise | 161 | 80.1% | 84.6% |
| Linear Algebra | 78 | 71.8% | 79.5% |
| Indexing & Selection | 34 | 73.5% | 79.4% |
| Other | 78 | 75.6% | 74.3% |
| Reduction | 63 | 69.8% | 74.6% |
| Deep Learning | 90 | 64.4% | 71.1% |

### 端到端模型覆盖

| 模型 | 全算子集 OpInfo | 全算子集 MIS | OpInfo 子集 OpInfo | OpInfo 子集 MIS |
|------|----------------|-------------|-------------------|----------------|
| NanoGPT | 87.2% | 80.0% | — | 100.0% |
| DLRM | 81.4% | 80.0% | — | 90.0% |
| MetaM1 | 79.8% | 83.8% | — | 91.9% |
| MetaM2 | 80.6% | 81.7% | — | 87.3% |

### 消融实验

| 方法 | CWM | GPT-OSS |
|------|-----|---------|
| Baseline（单次运行） | 55.3% | 72.0% |
| 移除 Linter | 48.9%（-6.4%） | 68.7%（-3.3%） |
| 移除 Summarization | 48.2%（-7.1%） | 71.5%（-0.5%） |

### 未来硬件模拟

在 QEMU 模拟器上对未来一代 MTIA 的单次运行覆盖率为 73.1%。

---

## 六、批判性分析

1. **覆盖率的统计膨胀**：84.7% 的最终覆盖率是通过多次运行、多种模型配置聚合得到的"best-of-N"结果，单次运行最高仅 72%。论文坦承了 test-time scaling 的作用，但在摘要和标题中突出 84.7% 有一定误导性——实际生产中不太可能为每个算子运行多次。

2. **性能完全不讨论**：论文明确将性能排除在范围之外，声称"coverage-first"。但实际生产中，功能正确但性能极差的内核几乎不可用。缺乏任何性能数据（甚至不提相比手写内核有多大差距），使得"overnight generation of complete PyTorch backends"的愿景缺乏说服力。

3. **"作弊"防护的有效性未充分验证**：Linter 通过白名单方式禁止调用其他 torch 算子，但论文没有分析有多少算子因此生成失败，也没有讨论是否存在 Linter 未能捕获的其他"作弊"途径。

4. **算子筛选收窄了评估范围**：从 629 个算子筛选到 568 个（排除复数、随机数、>900 测试的算子），排除了约 10% 的算子。这些被排除的算子可能恰好是更难生成的复杂算子，实际覆盖率可能低于报告值。

5. **模型端到端覆盖的定义模糊**：Table 2 展示了 80%+ 的模型算子覆盖率，但没有说明剩余 20% 未覆盖算子的 fallback 方案。如果这些算子需要 CPU fallback 执行，对整体推理延迟的影响可能很大。

6. **FSM vs. Agent 架构的比较缺乏实证**：论文声称 FSM 比自由 agent 更适合生产环境，但没有提供任何对比实验或量化数据支持这一判断。

---

## 七、AI Infra / MLSys 视角

1. **加速器软件栈的自动化趋势**：TritorX 展示了用 LLM 自动化加速器后端开发的可行性。随着 AI 芯片创业公司和定制 ASIC 的增多，自动化后端搭建将成为关键竞争力。这对 AI Infra 从业者意味着：内核工程的重心可能从逐个手写内核转向构建更好的编译器反馈和测试基础设施。

2. **编译器反馈质量是 LLM 代码生成的关键**：论文中一个重要发现是，详细的编译器错误信息比提供全面的硬件文档更有效。这提示 AI 编译器（如 Triton、TVM）的开发应重视错误信息的可读性和信息密度，因为未来的"用户"可能是 LLM 而非人类。

3. **可跟进的研究方向**：
   - **自洽算子生成**（Self-consistent generation）：允许算子间相互调用而非孤立生成，需要拓扑排序和依赖感知的生成策略。
   - **性能优化层**：在 TritorX 正确性基础上叠加 autotuning 和 schedule search，实现正确+高效的双目标。
   - **跨代迁移**：利用 QEMU 模拟器在芯片流片前预生成内核，缩短新硬件的软件就绪时间。

4. **最有价值的切入点**：将 TritorX 的方法论迁移到其他 DSL 和加速器（如 TPU/Pallas、NPU），或将其与 torch.compile/Inductor 集成，实现端到端的自动化后端生成。

---

## 八、总结

TritorX 是 Meta 提出的 coverage-first 的 agentic 内核生成系统，通过 FSM 驱动的 LLM + linter + 编译器 + 调试器反馈循环，为 MTIA 加速器自动生成了 481 个通过全部 OpInfo 测试（20,000+）的 ATen 算子内核，达到 84.7% 的覆盖率。系统设计聚焦于正确性和广覆盖而非性能优化，适用于新加速器平台的快速后端搭建和下一代硬件的预研。主要局限在于不涉及性能优化、高覆盖率依赖多次运行聚合、且排除了部分复杂算子。
