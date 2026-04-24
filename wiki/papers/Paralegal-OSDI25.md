---
type: paper
name: Paralegal
full_title: "Paralegal: Practical Static Analysis for Privacy Bugs"
authors: [Justus Adam, Carolyn Zech, Livia Zhu, Sreshtaa Rajesh, et al.]
venue: OSDI
year: 2025
tags: [static-analysis, privacy, rust, program-dependence-graph, code-analysis]
source_pdf: "[[osdi25-adam.pdf]]"
source_md: "[[osdi25-adam]]"
---

# Paralegal: Practical Static Analysis for Privacy Bugs (OSDI 2025)

> **一句话总结**：Paralegal 用带 marker 的 Program Dependence Graph（PDG）对 Rust 应用做可交互的静态隐私分析，在 8 个真实应用上找出 5 个已知和 2 个未知隐私 bug，比 CodeQL 能覆盖更多策略类型。

## 问题

企业应用需要遵守 GDPR 等隐私法规（账户删除时所有用户数据必须被删除、受限数据不得流到非法 sink 等），但当前主要靠人工审计，低频且易错。现有代码分析工具存在两类极端：领域定制工具（DroidSafe、PrivGuard、RuleKeeper）把策略逻辑硬编码到工具里，无法跨场景；而通用 IFC 或 CodeQL 这类工具要么要求全代码库加注解、要么需要维护大量第三方库的手工模型，查询以 AST 的语法正则表达为主，遇到代码演化就崩。

目标是构建一个既能表达丰富策略（包含「必须到达」这类 liveness 性质）、又能 scale 到真实应用、还能对库代码做精确抽象的静态分析器。

## 核心方法

关键抽象是**带 marker 的 PDG**。Paralegal 把策略与代码解耦：隐私工程师用高层策略语言写基于 marker 词汇表（如 `user_data`、`deletes`）的规则；应用开发者把 marker 附着到具体代码实体（类型、函数、参数）；Paralegal 则从 Rust MIR 生成 flow-/context-/field-sensitive 的 PDG，把 marker 传播到节点，然后把策略编译成 PDG 查询。Plume 的例子：要求所有标 `user_data` 的类型都必须流到 `deletes` 函数。

选 Rust 作为宿主是设计核心。Rust 的 ownership 类型系统让 Paralegal 用**模块化类型近似**替代手写库模型：不可变引用不会被 mutate、lifetime 限定返回值别名范围——所以对缺源码的库函数，Paralegal 可以保守但精确地推断数据/控制流。Rust 的静态 dispatch（trait 单态化）大大减少虚调用带来的精度损失。再加上 marker 引导的**自适应近似**：只要某函数体内及其被调函数没有任何 marker，就用类型签名级近似跳过，大幅收缩 PDG。

## 关键结果

- 8 个 Rust web 应用（Atomic、Plume、Lemmy、Hyperswitch、mCaptcha、WebSubmit、Freedit、Contile）上找到 5 个已知 + 2 个未知隐私 bug，开发者已确认。
- 能表达 11 条策略中 IFC 只能表达 6 条的（IFC 无法表达 liveness 类策略如「必须删除」）。
- 与 CodeQL 比：CodeQL 在跨过程控制流、async 代码、未实例化模板、库函数建模、C++ alias 分析等多处失败，Paralegal 都能过。
- 性能足以 IDE/CI 交互使用；在 2.5 年、1000+ commits 的 Atomic 上追踪，marker 改动少、策略完全不用改。
- 198k LOC 的代码库上也能秒级完成分析。

## 相关

- **相关概念**：Program Dependence Graph、Information Flow Control、Static Analysis、Rust Ownership
- **同会议**：[[OSDI-2025]]
