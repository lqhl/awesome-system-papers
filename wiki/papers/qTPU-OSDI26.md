---
type: paper
name: qTPU
full_title: "qTPU: Hybrid Tensor Networks for Quantum-Classical Acceleration"
authors: [Nathaniel Tornow, Emmanouil Giortamis, Dennis Sprokholt, Christian B. Mendl, Pramod Bhatotia]
venue: OSDI
year: 2026
tags: [quantum-computing, compiler, heterogeneous-computing]
source_pdf: "[[osdi26-tornow.pdf]]"
source_md: "[[osdi26-tornow]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向量子—经典加速的混合张量网络
> **原题**：qTPU: Hybrid Tensor Networks for Quantum-Classical Acceleration

## 问题与动机

QPU 能表示经典内存指数爆炸的 quantum state，却噪声高、资源少、吞吐低；现有 host–quantum-kernel 模型要求人工切分，阻碍跨量子—经典边界的整体优化与动态执行。

## 关键观察 / 隐含假设

- tensor network 可统一表示 classical tensor operation 与 quantum circuit。
- contraction/rewrite choice 可在 classical FLOPs 与 quantum error 之间形成 Pareto frontier。
- 假设 QPU error/cost model 足以指导编译，远程 QPU 可由 runtime 可靠编排。

## 核心方法

[[qTPU]] 提出 hybrid Tensor Network（hTN）抽象：programming model 声明统一图，compiler 做跨边界 rewrite、partition 与 cost/error optimization，runtime 在异构 QPU 和 classical accelerator 上可扩展执行。

## 实验与结果

在 hybrid ML、circuit knitting、quantum error mitigation workload 上，qTPU 相对 state-of-the-art baseline 把 classical overhead 降低 3–4 个数量级、quantum error rate 最高降低 7.2×、compile time 最高加速 53×，端到端 speedup 超过 20×（§8，图 8–14）。边界包括模拟/估算 QPU 执行与论文所测 20–150 qubit 场景。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| hTN 支持跨边界整体优化 | classical overhead 降低 1000–10000× | 三类 hybrid workload | 强 |
| cost/error tradeoff 可改善端到端执行 | error 7.2×、E2E 超过 20× | 所测 noise model/QPU | 中 |

## 批判性分析

### 论证链条
统一 IR 消除人工边界，编译器搜索 cost/error tradeoff，runtime 再兑现异构执行；三层设计对应编程、优化、扩展三个缺口。

### 假设压力测试
真实 QPU queue delay、calibration drift、correlated noise 与 vendor constraint 若偏离模型，静态 Pareto choice 可能失效。

### 实验可信度
workload 范围和多维指标丰富，但大量大规模结果依赖模拟或估算，真实 QPU 端到端复现仍是关键外部效度限制。

## 局限与后续工作

- 引入在线 noise calibration、queue-aware scheduling 与跨 vendor backend。
- 在更大真实 QPU 上验证 wall-clock、成本和结果质量。

## 相关

- [[OSDI-2026]]
- [[Quantum-Computing]]
- [[Tensor-Network]]
