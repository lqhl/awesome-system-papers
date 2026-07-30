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
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# HEC：通过等式饱和对代码转换进行等价验证检查（ATC 2025）

> **原题**：HEC: Equivalence Verification Checking for Code Transformation via Equality Saturation

> **一句话总结**：观察到 control-flow 变换（unrolling/tiling/fusion）的 tiling 因子、新变量名等元数据只能在运行时才确定，静态 [[e-graph]] 规则无法覆盖，HEC 以 [[MLIR]] 为前端、混合 62 条静态 datapath 规则与运行时 Z3 校验的动态 control-flow 规则做 [[Equality-Saturation]]，在 PolyBenchC 上 40 分钟内验证 10 万+ 行 MLIR，并检出 mlir-opt 两类真实编译 bug（loop unrolling 边界检查错、loop fusion RAW 违例）。

## 问题与动机

现代编译与 [[HLS]] 流水线大量使用 source-to-source 变换：control-flow 侧有 loop unrolling、tiling、fusion；datapath 侧有 De Morgan 律、常量折叠、shift-multiply 等价等。性能优化研究很多，但**变换正确性**常被忽视——一旦变换破坏语义，轻则数据损坏，重则系统失效。

现有验证工具高度碎片化：
- **[[PolyCheck]]**、ISA 面向 affine 程序，只管 control-flow 变换
- Samuel et al. 等工作面向 RTL datapath，不管 loop 结构
- **[[MLIR-TV]]** 虽在 MLIR 层做 translation validation，但论文实测不支持 affine dialect，无法覆盖本文 benchmark 的核心算子

作者 claim：需要**同时覆盖 datapath + control-flow** 的统一等价性检查框架，才能捕捉多域变换叠加时的 subtle bug。论文以 Figure 1 的 motivating example 说明：同一 baseline 经 loop hoisting、De Morgan 律、loop tiling 分别得到三个变体，传统工具只能各自验证一层，无法 holistic 处理。

## 关键观察 / 隐含假设

- **观察 1**：control-flow 变换的关键参数（unrolling 因子、tiling 因子、新生成 loop 变量名、loop bound）在 e-graph 编译时未知，纯静态 term rewriting 无法写出通用 lhs⇔rhs 规则。
  - **依赖假设**：变换实例来自有限模式族（unrolling/tiling/fusion/coalescing），且每个模式的**数学正确性条件**可被形式化（Table 2 中的迭代空间等式、loop-body 复制关系、无 RAW 违例等）。
  - **可能失效场景**：编译器引入论文未建模的变换（interchange、distribution、polyhedral schedule 等）；loop body 结构不满足 isomorphism 条件；非 affine 或含 side-effect 的 MLIR dialect。

- **观察 2**：将 [[MLIR]] 分解为 dataflow graph + 显式 `loopvalue`/`block` 结构后，variable hoisting 等「仅改变变量位置、不改变依赖」的变换可在进入 e-graph 前自动统一（Listing 1 vs Listing 2 映射到同一 Figure 4 dataflow）。
  - **依赖假设**：验证对象是 MLIR affine/arith 等 dialect 的 kernel 片段；loop 可用 start/end/step + block body 的 isolated output 建模；store 等无副作用输出的 op 用 pseudo output term 追踪。
  - **可能失效场景**：含 unstructured control flow（goto、异常）、指针别名、多线程、DMA/side-effect 的 kernel；global 变量重命名策略在复杂 scoping 下可能碰撞。

- **观察 3**：[[Equality-Saturation]] 的 e-class 成员判定可将「两程序是否功能等价」归约为 saturation 后根 e-node 是否合并；datapath 等价由静态代数恒等式驱动，control-flow 等价由运行时生成的动态规则驱动，二者可在同一 e-graph 中交织探索。
  - **依赖假设**：egg 框架的 congruence closure 能发现所有合法变换路径；动态规则 pattern 本身 sound（静态规则由 De Morgan/结合律等证明，动态条件由 [[Z3]] 验证）。
  - **可能失效场景**：saturation 在计算上限前终止 → false negative；规则集不完备 → 等价程序被判不等价；e-graph 规模随 unrolling 指数增长（Figure 8/9）。

- **假设 1**：PolyBenchC / PolyBench-NN 的 kernel 级 MLIR（经 [[Polygeist]] 从 C 提升）足以代表 HLS/编译器优化管道的验证需求。
  - **证据强度**：**中**——12 个 benchmark + CNN_Forward 覆盖典型线性代数与 stencil，且成功挖出 mlir-opt 真实 bug；但未覆盖完整端到端 HLS 流（[[CIRCT]]、[[ScaleHLS]] 等）或生产级 dialect 组合。

- **假设 2**：验证开销主要由 e-graph saturation 主导（>90%），Z3 仅用于动态规则条件校验（<1 s），不会成为 scalability 瓶颈。
  - **证据强度**：**强**——Section 4.2 与 Section 5.2 的 runtime 分解一致；dynamic rule 数量远小于 e-class 增长带来的 saturation 成本。

## 核心方法

HEC 流水线（Figure 3）分三步：

**Step 1 — MLIR graph representation**：将 MLIR 转为类 AST 的 dataflow graph。每个 op 是一个 vertex，记录 operator、dtype、dimension、input/output edges；按全局出现顺序重命名变量以避免 scope 冲突。for/if/func 统一建模为 `loopvalue`（start/end/step + 变量名）+ `block`（loop body 的 isolated output terms，顺序敏感）。这使 loop hoisting 等变换在 graph 层自动归一。

**Step 2 — 动态规则生成器**：扫描 graph 中候选 for-loop，匹配预定义变换模式（Table 2）：
- **Unrolling**：单 loop ⇔ 多 loop，要求迭代空间等式 + body 复制关系
- **Tiling**：单 loop ⇔ 嵌套 loop，`k1 == f×k2`，内层 bound 为 `min(%1+k1, n2)`
- **Fusion**：相邻同 bound loop ⇔ 单 loop，要求 body 拼接且无跨 loop RAW
- **Coalescing**：嵌套 loop ⇔ 单线性索引 loop

模式条件用 [[Z3]] 形式化验证（如 Figure 5 的 unrolling 迭代空间公式），通过后为**该输入实例**生成定制 lhs⇔rhs 动态规则（Listing 7/8 示例）。引入 `combine` 伪节点绑定多个 loop 候选（Figure 7）。

**Step 3 — e-graph verification runner**：基于 [[egg]] 做 [[Equality-Saturation]]。先插入 62 条 bitwidth-dependent 静态 datapath 规则（Table 1：shift-multiply 等价、De Morgan、布尔吸收律等）。若静态规则不足以合并两程序根节点，则迭代：rule generator 追加动态规则 → saturation → inverter 将 e-graph 转回 graph → 重复，直到等价确认或无法生成新规则。等价判定：两程序根 e-node 落入同一 e-class。

**Soundness / Completeness**：静态规则由代数恒等式保证 sound；动态 pattern 条件经 Z3 证明。框架**不完备**（规则集外等价或 saturation 提前终止会 false negative），但声称**不会产生 false positive**。

深度细节回 [[atc2025-yin]] 或 [[atc2025-yin.pdf]]。

## 设计取舍

- **取舍 1：MLIR 前端 vs 多语言 AST**——选 [[MLIR]] 作为统一 IR，使 [[Polygeist]]、IREE、[[CIRCT]] 等任意 MLIR 生成器都可接入；代价是只覆盖 MLIR 可表达的变换，且依赖 dialect 支持质量。
- **取舍 2：混合静态/动态规则 vs 纯 SMT 证明**——动态规则处理 control-flow 的参数化结构，Z3 仅验证 pattern 条件而非全程参与 saturation，避免 [[SMT]] 在大程序上的 scalability 瓶颈；代价是每类新变换需人工形式化 pattern + 条件，扩展成本不低。
- **取舍 3：Equality saturation vs 专用 affine 验证器**——e-graph 可同时探索 datapath 与 control-flow 组合路径，Congruence closure 自动发现多步变换序列；代价是 nested unrolling 时 e-class 数二次增长，runtime 呈指数级（2MM U16-U8 达 173.8 s，U16-U8 嵌套 unrolling 达 5069 e-classes）。
- **取舍 4：Soundness 优先 vs 完备性**——宁可漏报（false negative）也不误报（false positive），适合编译器 QA 场景；不适合需要「证明不等价」的安全关键场景。
- **边界条件**：单/双层 loop 的 unrolling/tiling/fusion + 布尔/算术 datapath 重写表现稳定；超大 unrolling factor、深层嵌套 loop、或规则库未覆盖的 polyhedral 变换会变脆或超时。

## 实验与结果

- 在 Xeon Gold 6418H 的 PolyBench kernel benchmark 中，相比原始 MLIR，HEC 验证 transformation equivalence；大多数案例少于 1 分钟，2MM U16-U8 为 173.8 s，边界是 LLVM 18.0.0 的指定 unrolling configuration（§5.1–5.2，Table4）。

- **Control-flow 验证**（PolyBenchC 12 kernel + CNN_Forward，变换由 mlir-opt LLVM 18.0.0 生成）：unrolling/tiling/fusion 全部配置验证通过；多数 case **<1 分钟**，tiling factor T2–T64 结果稳定
- **Nested unrolling scalability**（Figure 8）：factor 2–16 的嵌套 unrolling，多数 benchmark **<20 分钟**；saturation 占 runtime >90%；对角线样本 runtime 与 e-class 数随 factor 近似指数增长
- **Datapath 验证**（150+ benchmark，15k–90k LOC）：全部在 **40 分钟**内完成；最大 108,012 LOC 用时 2,305 s（≈38 min）；e-node 数与 LOC 近似线性（Figure 10）
- **Table 4 典型数字**：Gemm U64 unrolling 17.3 s / 932 e-classes；2MM U16-U8 嵌套 unrolling 173.8 s / 5069 e-classes；Bicg 基础 tiling 22.2 s
- **真实 bug 检出**（Section 5.4）：
  - **Loop boundary check error**：当 loop start > end 时，mlir-opt unrolling 仍执行 remainder loop（%0<10 时多跑一次）；影响 Jacobi_1d、Seidel_2d
  - **Memory RAW violation**：loop fusion 将 copy-then-increment 两 loop 合并后，迭代间 increment 依赖被破坏，输出从「全为 arg0[0]+1」变为线性递增序列
- **Baseline 对比**：与 MLIR-TV 的直接对比因后者不支持 affine dialect 而未能进行；论文列举 [[CompCert]]、[[Alive2]]、PolyCheck 等作为不同层次的相关工作

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| HEC verifies selected PolyBench kernel transformation | Table4 cases equivalence，most less than1min（§5.1） | C→MLIR/LLVM18 transform、kernel portion only | high |
| Nested unrolling scalability can degrade | 2MM U16-U8 173.8s/5069 e-class，saturation >90% time（§5.2，Fig8–9） | code-growth config、some timeout | high |
| Generated datapath suite reaches large inputs | 108012 LOC/2305s，e-node roughly linear（§5.3，Fig10） | synthetic datapath，非 compiler pipeline latency | high |
| Case study exposes unrolling boundary bug | 15>10 source zero iteration，transformed remainder once（§5.4，Listing9–10） | LLVM18 condition setting | high |
| Case study exposes fusion RAW mismatch | unfused/fused final array differ（§5.4，Listing11–12） | representative case，no prevalence claim | high |

## 批判性分析

### 论证链条

论文从「多域变换缺乏统一验证」（Figure 1 motivating example）→「静态 e-graph 规则无法表达参数化 control-flow」（Listing 6–8）→「混合动态规则 + MLIR graph 表示」（Section 4）→「PolyBenchC 上可扩展验证 + 挖出 mlir-opt bug」（Section 5），逻辑链条整体闭合。最强证据不是 synthetic micro-benchmark，而是**在标准 mlir-opt 管道中检出两类语义错误**，直接支撑「验证缺失有真实代价」的 claim。

薄弱跳步在于：将 kernel 级 affine MLIR 验证外推为「holistic multi-domain transformation verification」——实验未覆盖 datapath 与 control-flow **同一 pass pipeline 的连续叠加**（如先 fusion 再 unroll 再布尔化简的端到端序列），也未验证非 affine dialect 或带 memory ordering 的复杂 kernel。

### 假设压力测试

- **论文已证明**：在 Polygeist 提升的 PolyBenchC kernel、mlir-opt 生成的 unrolling/tiling/fusion 变换上，HEC 能在分钟级完成验证并 sound 地拒绝不等价程序（两类 bug case）。
- **可能失效**（推断）：
  - **变换覆盖**：规则库仅含 Table 2 四类 control-flow + Table 1 静态 datapath；polyhedral scheduling、loop interchange、vectorization、outline/inlining 等未建模变换会导致 false negative
  - **规模外推**：nested unrolling factor 16×16 时部分 benchmark 超时（Figure 8 标 X）；production kernel 的 loop 嵌套深度与 code size 可能远超评测
  - **MLIR 语义**：仅验证 functional equivalence（∀I, O_A(I)=O_B(I)），未讨论 undefined behavior、浮点 rounding、溢出、NaN 等；bitwidth-dependent 规则在跨宽度变换时可能遗漏 corner case
  - **部署集成**：作为离线验证工具，未嵌入 mlir-opt pass manager 做 per-pass checking；CI 中每次变换都跑 saturation 的成本论文未量化

### 实验可信度

- **Benchmark 代表性**：PolyBenchC 是 MLIR/HLS 社区标准套件，CNN_Forward 补充 DNN kernel；但只取 kernel 片段、经 Polygeist 提升，与真实 HLS 端到端（含 interface、memory allocation、host code）有距离
- **Baseline 强度**：未与 MLIR-TV、PolyCheck、Alive2 做同等条件下的 head-to-head，主要理由是 MLIR-TV 不支持 affine——这本身说明 HEC 填补空白，但也使性能/精度对比缺乏锚点
- **Ablation**：缺少「仅静态规则」「仅动态规则」「无 Z3 条件校验」的分解实验；e-class 数与 runtime 的相关性有展示（Figure 9），但未 isolate saturation iteration 次数、规则顺序等因子
- **Metrics**：聚焦 verification runtime、e-class/e-node 数、dynamic rule 数；**未报告** false negative rate（故意注入 bug 的检出率）、memory footprint、并行化潜力、与 compilation time 的比例

### 系统性缺陷

- **尾延迟**：nested unrolling 场景 runtime 指数增长（2MM U16-U8 173.8 s，Seidel_2d 同配置 380.1 s），缺乏 timeout 策略或 incremental verification 的讨论
- **可观测性**：验证失败时如何定位「哪条变换/哪个 loop」导致不等价，论文未讨论 debug 接口；bug case study 靠人工分析 Listing
- **故障恢复与并行**：e-graph saturation 的单线程 egg 实现、中断恢复、大规模 job 调度论文未讨论
- **运维成本**：每类新变换需形式化 pattern + Z3 条件 + 测试，工程门槛高于 plug-and-play 的 translation validator
- **兼容性**：绑定 MLIR affine/arith dialect 子集；论文未讨论与 [[LLVM]] IR 层 [[Alive2]] 的互补或重复验证策略

## 局限与后续工作

- **局限 1**（论文承认）：基于 rewriting rules 的验证**不完备**——规则集未覆盖的等价路径或 saturation 计算上限会导致 false negative
- **局限 2**（论文承认）：MLIR-TV 等最接近 baseline 因 affine dialect 支持缺失无法直接对比，外部读者难以量化 HEC 相对现有 MLIR 验证器的优势边界
- **局限 3**（实验边界）：评测限于 PolyBenchC kernel + mlir-opt 生成的变换；未覆盖 [[CIRCT]]/[[ScaleHLS]]/[[HeteroCL]] 完整 HLS 管道或用户自定义 pass 组合
- **局限 4**（推断）：nested unrolling 的指数 runtime 使高 unrolling factor 场景不实用，而论文也承认此类 factor 在 PPA 约束下本就罕见——工具 worst-case 与 typical-case 差距大
- **Future work 1**：扩展变换 pattern 库（loop interchange、distribution、polyhedral schedule 等），并为每个 pattern 建立 Z3-verified 条件 + false-negative 评测集
- **Future work 2**：将 HEC 嵌入 mlir-opt pass pipeline 做 per-pass regression gate，量化「验证时间 / 编译时间」在 CI 中的可接受比例
- **Future work 3**：与 MLIR-TV 在共同支持的 dialect 上做 head-to-head，并推动 affine dialect 支持以便公平对比
- **Future work 4**：研究 saturation 早停、incremental e-graph update、parallel rewriting 以降低 nested unrolling 的尾延迟

## 相关

- **相关概念**：[[E-Graph]]、[[Equality-Saturation]]、[[MLIR]]、[[Formal-Verification]]、[[Compiler-Optimization]]、[[SMT]]、[[Affine-Loops]]
- **同类系统**：[[PolyCheck]]、[[MLIR-TV]]、[[Alive2]]、[[CompCert]]、[[egg]]、Seer、[[Polygeist]]
- **同会议**：[[ATC-2025]]
- **对比**：PolyCheck（仅 affine control-flow）、Alive2（LLVM IR peephole）、MLIR-TV（MLIR 层但缺 affine 支持）
