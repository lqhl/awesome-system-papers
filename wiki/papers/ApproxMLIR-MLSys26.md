---
type: paper
name: ApproxMLIR
full_title: "ApproxMLIR: An Accuracy-Aware Compiler for Compound ML Systems"
authors: [Hao Ren, Yi Mu, Sasa Misailovic]
venue: MLSys
year: 2026
tags: [mlir, approximate-computing, rag, compiler, autotuning]
source_pdf: "[[a5771bce93e200c36f7cd9dfd0e5deaa.pdf]]"
source_md: "[[a5771bce93e200c36f7cd9dfd0e5deaa]]"
---

# ApproxMLIR: An Accuracy-Aware Compiler for Compound ML Systems (MLSys 2026)

> **一句话总结**：compound AI（LLM+BM25/工具等非 ML 组件）近似 knob 分散在 JAX/Polygeist/LLVM 碎片 toolchain 中；ApproxMLIR 用 **approx dialect** 统一跨层近似声明 + OpenTuner 搜 Pareto 前沿 + approx-runtime 动态决策，在 LLM+RAG 等系统上相对静态策略 **2.64–3.04×** 加速（6–9% QoS 损失），一致优于单点近似。

## 问题与动机

[[RAG]]、tool-calling 等 compound 系统各组件天然容忍误差，但 ML（JAX→StableHLO）与非 ML（C++→Polygeist）分离编译，无法在端到端 QoS 约束下联合调 approximate knob（corpus skip、term scoring、LLM 量化等）。

## 关键观察 / 隐含假设

- **观察 1：把近似绑在现有 op attribute 上会在 tiling/bufferization 中丢失；独立 approx dialect 作 first-class op 可存活到 lowering。**
  - **依赖假设**：autotuner 只理解 approx.knob，不需懂各 backend dialect。
  - **可能失效场景**：未覆盖的新 transform type 需手写 rewrite rule。

- **观察 2：compound 系统 QoS 是任务准确率等应用指标，非单 kernel 误差；需 OpenTuner 搜 knob 配置 + QoS evaluator。**
  - **依赖假设**：代表性 eval 数据集可测 QoS；配置空间可离散化。
  - **可能失效场景**：QoS 对输入分布敏感时静态 Pareto 点运行时失效——靠 approx.decision_tree 缓解。

- **观察 3：动态近似（decision tree on runtime state）优于静态全局 knob，尤其在 RAG 检索阶段。**
  - **依赖假设**：runtime 库提供 get_retrieval_state 等钩子。
  - **可能失效场景**：错误近似传播需 approx.try 恢复，增加延迟。

## 核心方法

**approx dialect**：approx.knob（接口）、approx.transform（策略）、approx.decision_tree（动态）、approx.try（校验恢复）。

**Workflow**：JAX/C++ frontends → MLIR + approx 标注 → OpenTuner 搜配置 → approx-opt passes 施加变换 → LLVM + IREE 后端。

**BM25 RAG 示例**：corpus subsetting、term scoring skip、context selection、LLM substitute 四类 knob 统一表达。

## 设计取舍

- **MLIR 统一 vs 各栈独立近似**：工程量大，赢得跨组件联合优化。
- **OpenTuner 外置 vs 内置**：复用成熟搜索，依赖外部依赖。
- **动态 runtime vs 纯 AOT**：更好 QoS–性能，runtime 复杂度升。
- **边界条件**：三套 compound 系统 + 五非 ML kernel；Gemma 3 系列 LLM。

## 实验与结果

- LLM+RAG(kb)：**2.64×** @ 6% QoS loss，**3.04×** @ 9% QoS loss。
- Pareto 曲线整体支配静态近似与无近似 MLIR baseline。
- 多 benchmark 上 consistently 更高 speedup at same QoS。

## Critical Analysis

### 论证链条

碎片化痛点清晰 → dialect 设计回应 attribute 丢失 → 端到端 autotune 结果支撑 claim。QoS 仅 accuracy 类指标，延迟/成本多目标部分靠 ExecTime 隐含。

### 假设压力测试

新 LLM 架构需新 approx transform；OpenTuner 搜索成本随 knob 数指数；生产 traffic 分布漂移使 decision tree 过时。

### 实验可信度

三 compound 系统有深度；baseline 含静态策略。缺大规模在线 A/B。

### 系统性缺陷

编译链长、调试难；approx.try 恢复路径开销；论文未讨论安全关键场景禁用近似。

## 局限与 Future Work

- **局限**：搜索与 compile 成本高；QoS evaluator 需 per-app 定制；GPU 后端覆盖有限。
- **Future work**：与 [[torch.compile]] 路径集成；multi-objective（能耗+latency）Pareto； formal QoS contract 验证。

## 相关

- **相关概念**：[[RAG]]、[[MLIR]]
- **同会议**：[[MLSys-2026]]