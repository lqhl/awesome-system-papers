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
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# ApproxMLIR：复合机器学习系统的准确性感知编译器（MLSys 2026）

> **原题**：ApproxMLIR: An Accuracy-Aware Compiler for Compound ML Systems

> **一句话总结**：ApproxMLIR 用 approx dialect、OpenTuner 和 runtime decisions 联合优化 compound AI 的近似 knobs；LLM+RAG(kb) 在 3%/6%/9% QoS-loss budget 下，相对 exact MLIR 为 2.64×/2.64×/3.04×，static approximation 为 1.69×/1.93×/2.27×；dynamic 在部分 workload/budget 更高、其他设定持平（§7.1，Fig. 6）。

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

- **LLM+RAG(kb)**：相对 exact MLIR，dynamic 在 3%/6%/9% QoS-loss budget 下为 2.64×/2.64×/3.04×，static 为 1.69×/1.93×/2.27×（§7.1，Fig. 6；Gemma 3 1B/4B、NQ、90,011-document corpus，硬件未报告）。
- **Dynamic vs static**：9% budget 下 BM25 为 1.57× vs 1.00×、KB 为 3.04× vs 2.27×，但 tools 同为 1.20×；3% 时 BM25 也同为 1.00×（§7.1，Fig. 6；三个 compound benchmarks，12-hour tuning）。
- **Pareto frontier**：dynamic 通常有更低 execution time 或更多 Pareto points，但部分区域与 static 重合；作者将其归因于较大的 dynamic search space 在固定 budget 内未充分搜索（§7.1–7.2，Fig. 7–8；compound 12h、kernels 2h）。
- **Held-out degradation**：tuning 到不重叠 evaluation set 的 speedup gap 上限为 BM25 18.6%、KB 19.5%、tools 3.7%；evaluation set 是 tuning set 的 5×，但未给 query 绝对数量（§6、§7.1，Fig. 6–7）。
- **Compile/search cost**：parameterized ML kernels 平均 compile 120 秒，non-ML kernels 5 秒；search space 从 450 configs 到 `1.7 × 10^25`（§6 Table 2、§7.3；硬件未报告）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| ApproxMLIR 在 LLM+RAG(kb) 上比 exact MLIR 达到 2.64–3.04× speedup | §7.1, Fig. 6 | Gemma 3 1B/4B；NQ；3/6/9% budgets；硬件未报告 | strong |
| Dynamic approximation 只在部分 workload/budget 严格优于 static | §7.1, Fig. 6 | BM25/KB/tools；12h tuning；多个持平点 | strong |
| Dynamic frontier 通常改善但与 static 存在重合 | §7.1–7.2, Fig. 7–8 | 3 compound systems；5 kernels；固定 tuning budgets | medium |
| Held-out speedup gap 最高为 19.5% | §6, §7.1, Fig. 6–7 | disjoint split；evaluation size 5× tuning；query count 未给 | medium |
| Approximation search 具有可测 compile 与 configuration cost | §6 Table 2, §7.3 | 5 kernels/3 systems；无 compiler baseline；硬件未报告 | medium |

## 批判性分析

### 论证链条

碎片化痛点清晰 → dialect 设计回应 attribute 丢失 → 端到端 autotune 结果支撑 claim。QoS 仅 accuracy 类指标，延迟/成本多目标部分靠 ExecTime 隐含。

### 假设压力测试

新 LLM 架构可能需新 approx transform；论文只报告 configuration count 与固定 tuning budget，未证明搜索复杂度随 knobs 指数增长；production traffic drift 也未在线测量。

### 实验可信度

三 compound 系统有深度；baseline 含静态策略。缺大规模在线 A/B。

### 系统性缺陷

编译链长、调试难；approx.try 恢复路径开销；论文未讨论安全关键场景禁用近似。

## 局限与后续工作

- **局限**：搜索与 compile 成本高；QoS evaluator 需 per-app 定制；论文将 IREE artifacts offload 到 GPU，但未比较 backend coverage。
- **Future work**：与 [[torch.compile]] 路径集成；multi-objective（能耗+latency）Pareto； formal QoS contract 验证。

## 相关

- **相关概念**：[[RAG]]、[[MLIR]]
- **同会议**：[[MLSys-2026]]
