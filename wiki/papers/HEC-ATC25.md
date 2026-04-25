---
type: paper
name: HEC
full_title: "HEC: Equivalence Verification Checking for Code Transformation via Equality Saturation"
authors: [Jiaqi Yin, Zhan Song, Nicolas Bohm Agostini, Antonino Tumeo, Cunxi Yu]
venue: ATC
year: 2025
tags: [formal-verification, e-graph, mlir, compiler, equivalence-checking]
source_pdf: "[[atc2025-yin.pdf]]"
source_md: "[[atc2025-yin]]"
---

# HEC: Equivalence Verification Checking for Code Transformation via Equality Saturation (ATC 2025)

> **一句话总结**：基于 e-graph 的 MLIR 等价性验证框架，混合静态 datapath 重写规则与运行时生成的动态 control-flow 重写规则，在 PolyBenchC 上 40 分钟处理 100k+ 行 MLIR，并发现 mlir-opt 两类真实编译 bug（loop unrolling 边界检查错、loop fusion RAW 违例）。

## 问题

source-to-source code transformation（unrolling/tiling/fusion 改控制流，De Morgan/常量折叠改 datapath）在 HLS 和编译器优化里普及，但等价性验证工具碎片化：PolyCheck、ISA 只验证 affine 程序的控制流变换；针对 RTL datapath 的方法又不能管控制流。**没有同时覆盖 datapath + control flow**的统一验证框架，意味着多变换叠加产生的 bug 经常漏掉。

## 核心方法

把 MLIR 转成 graph representation（dataflow + 显式 for/block 结构）后塞进 e-graph，做 equality saturation：

- **静态 datapath 规则**：62 条 bitwidth-dependent 规则，覆盖 De Morgan、shift-multiply 等价、布尔代数恒等式等。例如 `a<<b ⇔ a×2^b`、`¬(a∧b) ⇔ ¬a∨¬b`
- **动态 control-flow 规则**：tiling 因子、unrolling 倍数、新生成变量名都是运行时才知道的，静态 e-graph 规则没法表达。HEC 在编译时扫描候选 for-loop，发现满足 unrolling/tiling/fusion/coalescing 模式（迭代空间公式由 Z3 SMT 验证）后**当场生成定制 lhs⇔rhs 重写规则**
- **e-graph runner**：用 egg 框架做 equality saturation，最终判断原程序与变换后程序的根 e-node 是否在同一 e-class 即为等价

深度细节回 [[atc2025-yin]]。

## 关键结果

- PolyBenchC benchmarks 上验证 loop unrolling/tiling/fusion 全套变换；100k+ 行 MLIR 在 40 分钟内完成
- 发现 mlir-opt 的两类编译 bug：
  - **loop unrolling 边界检查错**：触发非预期的 iteration 执行
  - **loop fusion 内存 RAW 违例**：改变了程序语义
- Z3 仅用于验证动态规则的 pattern condition（每次 <1 s），不参与 saturation 主循环，避免 SMT scalability 问题

## 相关

- **相关概念**：[[E-Graph]]、[[Equality-Saturation]]、[[MLIR]]、[[Formal-Verification]]、[[Compiler-Optimization]]
- **同会议**：[[ATC-2025]]
