# HEC: Equivalence Verification Checking for Code Transformation via Equality Saturation

**作者**：Jiaqi Yin, Zhan Song (University of Maryland, College Park); Nicolas Bohm Agostini, Antonino Tumeo (Pacific Northwest National Laboratory); Cunxi Yu (University of Maryland, College Park)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/yin
**源文件**：[[atc2025-yin.pdf]]

---

## 一、背景

在后摩尔时代，源到源代码变换（source-to-source code transformation）被广泛用于提升计算效率，包括控制流变换（loop unrolling、tiling、fusion）和数据通路变换（算子级优化、布尔代数简化）。这些变换在高层次综合（HLS）和编译器优化中扮演关键角色。然而，变换后代码的正确性验证长期被忽视——现有工具要么只能处理仿射变换（如 PolyCheck），要么只针对数据通路（如 RTL 级验证），无法同时覆盖控制流和数据通路变换。

Equality saturation 是一种基于 e-graph 数据结构的新兴技术，能在一个图中紧凑地表示多个等价表达式，支持双向重写规则，为统一验证提供了可能性。

---

## 二、要解决的问题

1. **验证工具碎片化**：现有验证工具（PolyCheck、ISA、MLIR-TV、Alive2 等）各自局限于编译栈的某一层或某一类变换，无法提供跨数据通路和控制流的统一等价性检查。
2. **控制流变换难以用静态规则表达**：Loop unrolling、tiling 等变换会引入运行时才确定的参数（unrolling factor、新变量名、循环边界），传统 e-graph 的静态重写规则无法通用地覆盖所有情形。
3. **编译器变换引入的隐性 bug**：MLIR 编译器（mlir-opt）在执行变换时可能破坏语义等价性（如循环边界错误、内存 RAW 违规），但缺乏有效检测手段。

---

## 三、洞察与设计

**关键洞察**：数据通路变换可以用数学上已证明的代数恒等式（如 De Morgan 定律、算术结合律）静态捕获，而控制流变换的参数（unrolling factor、tiling factor、新变量名）虽在编译前未知，但在获得输入代码后可以从图表示中提取并动态生成对应的重写规则——将两类规则统一在 e-graph 框架中即可实现全面的等价性验证。

### 整体架构

HEC 框架分三步：

1. **MLIR → 图表示转换**（Step 1）：将 MLIR 代码转换为类 AST 的图表示，统一变量重命名，将 for 循环分解为 loop value component（起止步长）和 block operation（循环体），自动处理 loop hoisting 等不影响数据依赖的变换。
2. **动态规则生成**（Step 2）：基于预定义的变换模式（unrolling、tiling、fusion、coalescing），分析图表示中的循环结构，在运行时为每对候选循环生成专用重写规则。规则的正确性条件由 Z3 SMT solver 形式化验证。
3. **混合 e-graph 验证**（Step 3）：e-graph runner 同时应用 62 条位宽相关的静态数据通路规则和动态生成的控制流规则。迭代执行：每轮先尝试静态规则，若不能判定等价则将图表示送回规则生成器创建新动态规则，直到等价确认或无新规则可生成。

### 关键设计决策

- **循环表示的分解**：将 for 循环拆为 loop value 和 block 两个组件，使得同参数不同变量名的循环可以区分，同时循环体内的操作顺序被保留。
- **Combine 伪节点**：为动态规则中需要合并的循环对引入 combine 节点作为父节点，使嵌套 unrolling 可以通过多轮迭代逐层合并。
- **可扩展性**：新的控制流变换只需形式化其模式和正确性条件即可接入。

---

## 四、实现细节

- **前端**：以 MLIR 为输入语言，支持通过 Polygeist、IREE 等工具从 C 代码生成 MLIR。
- **e-graph 引擎**：基于 egg 框架实现 equality saturation。
- **静态规则**：62 条位宽相关的数据通路重写规则，覆盖移位-乘法转换、De Morgan 定律、XOR 恒等式、算术结合律等。
- **动态规则**：支持 4 类控制流变换模式——unrolling（检查迭代空间划分条件）、tiling（检查 tiling factor 与循环边界关系）、fusion（检查 RAW 无违规）、coalescing（检查 floordiv/mod 索引替换）。
- **Z3 集成**：仅用于验证动态规则的模式条件，不参与整个 saturation 过程，避免可扩展性瓶颈。动态规则生成（含 Z3 检查）通常在 1 秒内完成。
- **e-graph 构建算法**：按拓扑序从叶到根插入节点（Algorithm 1），确保子节点先于父节点处理。
- **逆转换器**：每轮迭代后将 e-graph 转回图表示，供下一轮规则生成器使用。

---

## 五、实验结果

**实验平台**：Intel Xeon Gold 6418H（48 核，4GHz），1024GB RAM，LLVM 18.0.0。

**基准测试**：PolyBenchC 的 12 个 kernel + CNN_Forward（来自 PolyBench-NN）。

### 控制流变换验证

| 基准测试 | 复杂度 | Tiling (T2~T64) | Unrolling U8 | Unrolling U16 | Nested U16-U8 |
|---|---|---|---|---|---|
| 2MM | O(n³) | 7.3s | 7.8s | 10.9s | 173.8s |
| GEMM | O(n³) | 6.8s | 6.8s | 8.5s | 101.5s |
| TRISOLV | O(n²) | 6.8s | 6.3s | 7.0s | 36.0s |
| CNN_Forward | O(n⁷) | 8.1s | 7.5s | 8.6s | 45.3s |

- Tiling 变换运行时间稳定（不增大代码），不同 tiling factor 影响极小。
- 单层 unrolling 多数在 1 分钟内完成。
- 嵌套 unrolling 运行时间随 factor 指数增长（代码量二次增长），但 16×16 嵌套最大约 380 秒。

### 数据通路变换验证

- 生成 150+ 个不同规模的基准测试（15K~90K LOC）。
- 最大基准 108,012 LOC 在 2,305 秒（~40 分钟）内完成验证。
- e-node 数量随 LOC 线性增长，运行时间可预测地扩展。

### Bug 发现

| Bug 类型 | 影响 | 触发条件 |
|---|---|---|
| Loop Boundary Check Error | 循环边界条件不满足时 unrolling 后产生多余执行 | 循环 end < start 且 unrolling factor > 1 |
| Memory RAW Violation | Loop fusion 改变操作顺序导致内存状态不一致 | 相邻循环间存在 read-after-write 依赖 |

两个 bug 均为 mlir-opt 中的真实编译错误，影响 Jacobi_1d 和 Seidel_2d 基准测试。

---

## 六、批判性分析

1. **完备性限制被轻描淡写**：论文承认 HEC 是不完备的（inherently incomplete），但未量化 false negative 的发生频率。对于 saturation 未收敛或规则集不覆盖的情况，用户无法区分"确实不等价"和"验证能力不足"——这在实际使用中是严重问题。
2. **动态规则模式的覆盖范围有限**：仅支持 4 类控制流变换（unrolling、tiling、fusion、coalescing），而现实编译器还有 interchange、skewing、distribution、vectorization 等常见变换未被覆盖。论文的"可扩展性"声称需要用户自行形式化新模式，门槛不低。
3. **基线对比缺失**：由于 MLIR-TV 不支持 affine dialect，论文未与任何现有工具进行直接对比。读者无法判断 HEC 相对于已有工具在能力和性能上的具体优势。
4. **Bug 发现的方法论不清晰**：论文声称发现了 mlir-opt 中的两个 bug，但未说明这些 bug 是否已被上游确认/修复，也未讨论 HEC 发现这些 bug 的系统性——是偶然发现还是有针对性的 bug hunting？
5. **嵌套 unrolling 的可扩展性存疑**：16×16 嵌套 unrolling 部分 benchmark 已超时（图中标"X"），且运行时间呈指数增长。论文以"实际中很少使用大 unrolling factor"来淡化这一问题，但在 AI 编译器中 unrolling 与 tiling 的组合变换非常常见。
6. **Soundness 论证依赖 Z3 但未充分讨论**：静态规则声称"by construction"正确，动态规则由 Z3 验证，但论文未讨论 Z3 验证本身的局限性（如非线性算术的不可判定性）以及手动编写变换模式时引入错误的风险。

---

## 七、AI Infra / MLSys 视角

1. **编译器验证对 AI 编译栈的启发**：AI Infra 中 XLA、TVM、Triton 等编译器大量使用循环变换和算子融合优化。HEC 的混合验证方法可迁移用于验证这些编译器变换的正确性，尤其是在 ML 编译器引入新优化 pass 时的回归测试。

2. **e-graph 在计算图优化中的应用**：论文引用了 TASO（用图替换优化 DNN 计算）和 tensor graph superoptimization 等工作。HEC 的动态规则生成思路可扩展到验证 ML 计算图变换——例如验证算子融合、layout 变换、量化替换等是否保持语义等价。

3. **MLIR 生态的验证工具缺口**：随着 MLIR 在 AI 编译器中的广泛采用（IREE、Triton、StableHLO），MLIR 变换的正确性验证变得越来越重要。HEC 是目前少数能在 MLIR affine dialect 层面进行验证的工具，填补了一个实际需求。

4. **可跟进方向**：
   - 将 HEC 扩展到支持 linalg、tensor、scf 等更多 MLIR dialect，覆盖 ML 编译器常用的变换层级
   - 将动态规则生成与 AI 编译器的 auto-tuning pipeline 结合，在搜索最优变换配置的同时验证正确性
   - 探索将 equality saturation 用于 ML 模型的数值等价性验证（考虑浮点精度）

---

## 八、总结

HEC 提出了基于 e-graph equality saturation 的代码等价性验证框架，通过静态数据通路规则和动态控制流规则的混合设计，首次实现了对 MLIR 代码中控制流和数据通路变换的统一验证。在 PolyBenchC 上验证了 unrolling、tiling、fusion 等变换，处理 100K+ LOC 在 40 分钟内完成，并发现了 mlir-opt 中两个真实编译 bug。主要局限在于变换模式覆盖有限（仅 4 类控制流变换）、完备性无法保证、以及嵌套变换的可扩展性受限。适用于 HLS 和编译器开发中对变换正确性有严格要求的场景。
