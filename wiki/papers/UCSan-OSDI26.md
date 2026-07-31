---
type: paper
name: UCSan
full_title: "A Compilation-based Under-Constrained Execution Engine"
authors: [Mingjun Yin, Zhaorui Li, Ju Chen, Haochen Zeng, Chengyu Song]
venue: OSDI
year: 2026
tags: [program-analysis, symbolic-execution, compiler]
source_pdf: "[[osdi26-yin.pdf]]"
source_md: "[[osdi26-yin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 基于编译的欠约束执行引擎
> **原题**：A Compilation-based Under-Constrained Execution Engine

## 问题与动机

分析大型 C/C++ 系统中的单个函数时，完整构建环境成本高，传统欠约束 symbolic execution 又常依赖专用解释器、兼容性有限。目标是把任意代码子集直接编译为可执行分析单元。

## 关键观察 / 隐含假设

- 未提供的 memory、参数和 external function 可在运行时按欠约束语义补全。
- 借助原生编译器可复用优化、ABI 与 sanitizer 生态。
- 假设目标缺陷可在局部路径触发，外部语义的近似不会掩盖关键行为。

## 核心方法

[[UCSan]] 通过编译插桩把选定函数及依赖变成 self-contained executable；运行时惰性初始化未知内存、解析外部调用，并结合 symbolic/concolic execution 探索路径，同时用 sanitizer 检测错误。

## 实验与结果

在 Linux kernel 分析任务上，UCSan 相对 KLEE-based engine 最高快 15.06×；可成功编译超过 80% kernel code，扩展版本处理 63,957 个目标、覆盖 95.46%（§6，表 3）。边界是可由编译插桩支持的 C/C++ 代码。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 编译式执行改善兼容性 | Linux kernel 超过 80% 代码可编译 | §6 | 强 |
| 原生执行降低分析成本 | 相对 KLEE 最高快 15.06× | 表 3 | 强 |

## 批判性分析

### 论证链条
论文把 under-constrained semantics 移入编译产物与 runtime，绕开重新实现完整 ISA/环境的负担。

### 假设压力测试
强依赖设备、并发、时序或复杂外部状态的函数，局部补全可能产生大量伪路径或漏报。

### 实验可信度
大规模 kernel corpus 与性能对比有力，但 bug precision、重复路径和人工确认成本同样关键。

## 局限与后续工作

- 需要扩展并发、内核异步事件、跨语言边界，并量化外部函数模型造成的 false positive/negative。

## 相关

- [[OSDI-2026]]
- [[Symbolic-Execution]]
- [[Program-Analysis]]
