---
type: paper
name: CountingAtomicity
full_title: "Inferring Likely Counting-related Atomicity Program Properties for Persistent Memory"
authors: [Yunmo Zhang, Junqiao Qiu, Hong Xu, Chun Jason Xue]
venue: ATC
year: 2025
tags: [persistent-memory, atomicity, bug-detection, static-analysis, smt]
source_pdf: "[[atc2025-zhang-yunmo.pdf]]"
source_md: "[[atc2025-zhang-yunmo]]"
---

# Inferring Likely Counting-related Atomicity Program Properties for Persistent Memory (ATC 2025)

> **一句话总结**：用 symbolic range analysis + SMT 求解器自动推断 PM 程序中"容器数组与其逻辑 size 变量"的 counting-correlated 原子性属性，在 4 个真实 PM 系统中找到 14 个原子性 bug（其中 11 个新发现）。

## 问题

[[Persistent-Memory]] 程序面临 crash consistency 问题，需要程序员标注 ordering 与 atomicity 属性来辅助测试工具找 bug。Witcher、Huang et al. 等 dependency-based 推断方案能处理简单 ordering，但对 PM 中常见的"数组 + size 变量"这种 counting correlation 无能为力——因为数组本身不充当 guardian 出现在 if 条件中，ordering 模式抓不到。例如 P-ART 中 children 数组与 childrenCount，若 crash 时只持久了一边，会导致 dangling pointer 或数据丢失。

## 核心方法

提出 counting-related 原子性属性的三种 pattern：(1) SZ 是单数组 ARR 的逻辑大小；(2) SZ 是多数组逻辑大小之和；(3) SZ 是数组相对常数 C 的补 size。

- **Read range invariant**：所有对 ARR 的 read 索引必须 < SZ 的当前值（pattern 2 用 sum，pattern 3 用 C-SZ）。Read 取代 write 是因为 insert 等场景下 write 索引可能临时越界（≤ SZ）。
- **Write range invariant（可选）**：放宽允许 write index ≤ SZ + c。
- **Symbolic Range Analysis (SRA)**：用 LLVM pass 把程序转 Extended SSA，沿 control flow 用符号区间格 [l, r] 推断每个整型变量与数组访问索引的范围，遇 φ-function 取并、σ-function 取交。
- **SMT 验证**：把候选 (ptr, int) 变量对的 invariant 编码成 Z3 约束（取 negation 求 UNSAT），通过即生成 likely 原子性属性 ATOMICITY(ptr, int)。

详见 [[atc2025-zhang-yunmo]]。

## 关键结果

- 在 P-ART、P-BwTree、CCEH、Level-Hashing 上发现 14 个原子性 bug，11 个为新 bug。
- 对比 MUVI 仅识别 4 个、Witcher 仅识别 3 个。
- 静态分析时间 0.2–0.6 秒/程序，远快于 Witcher 的 11min–1h。

## 相关

- **相关概念**：[[Persistent-Memory]]、[[Crash-Consistency]]
- **同会议**：[[ATC-2025]]
