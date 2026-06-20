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

> **一句话总结**：Paralegal 用 marker 解耦隐私策略与代码，在 Rust 上构建 flow/context/field-sensitive 的 marked PDG，8 个真实 Rust web 应用上找到 5 个已知 + 2 个未知隐私 bug，秒级可跑在 IDE/CI，且比 CodeQL 覆盖更多 liveness 类策略。

## 问题与动机

企业应用必须满足 GDPR 等隐私法规：用户数据必须可删除、敏感数据不得流向非法 sink、加密密钥不得泄露等。现实里主要靠人工审计，低频且易错。现有工具两极分化：DroidSafe、PrivGuard、RuleKeeper 等把领域语义硬编码进分析器，跨场景泛化差；IFC 安全类型语言或 CodeQL 等通用引擎要么要求 pervasive 注解，要么需要大量第三方库手工模型，且 CodeQL 常以正则匹配标识符，代码演化后 brittle。

Paralegal 的目标是：**策略表达力强**（含「必须删除」等 liveness）、**能 scale 到真实应用**、**库代码建模成本低**、**开发者日常可用**（IDE/CI 秒级反馈）。论文选择 Rust 作为宿主语言，因为 ownership/lifetime 类型系统可模块化近似库行为，且静态 dispatch 让跨过程分析更精确。

## 关键观察 / 隐含假设

- **观察 1**：隐私合规检查的核心是「语义级数据/控制依赖 + 可维护的策略词汇」，而非 AST 语法模式。Plume 账户删除漏删 comments 的 bug 需要 field-sensitive PDG 才能发现。
  - **依赖假设**：开发者愿意与隐私工程师协作维护 marker；策略用 marker 词汇表表达，代码实体由应用开发者标注。
  - **可能失效场景**：marker 标注错误或长期不维护；策略与实现脱节时需要迭代修订（论文把这当作正常 workflow，但会增加组织成本）。
- **观察 2**：Rust 的 mutability 与 lifetime 约束让「无源码库函数」的类型级近似足够精确，可替代 CodeQL 式手工库模型。
  - **依赖假设**：目标代码以 safe Rust 为主；unsafe、interior mutability、FFI 封装不完整时会漏依赖。
  - **证据强度**：中——Flowistry 等工作证明类型近似有效，但论文明确 soundness 是 policy-dependent。
- **假设 1**：marker 能精确定位策略相关代码子图，从而对无 marker 可达的函数做廉价类型签名近似，PDG 仍可秒级生成。
  - **证据强度**：强——Atomic 2.5 年 1000+ commits 上 marker 改动少、策略无需改；198k LOC 仍秒级。

## 核心方法

**三层架构**：(1) 从 Rust MIR 构建 flow-/context-/field-sensitive **Program Dependence Graph (PDG)**；(2) **marker** 作为隐私工程师与应用开发者之间的语义词汇（如 `user_data`、`deletes`）；(3) 策略语言编译为对 marked PDG 的查询。

**Rust 特化**：monomorphization 解析 trait 静态分派；对第三方库用 Flowistry 式**模块化类型近似**（不可变引用不 mutate、lifetime 限制别名）；**marker 引导近似**——函数体及 callee 无 marker 可达时仅用类型签名建子图。

**工作流**：隐私工程师写 marker 策略 → 开发者标注代码 → 定期跑 Paralegal → 报告违反（含 Plume 式缺失删除路径）。策略与代码解耦使策略可读、可审计，且代码重构时 marker 维护量小于重写策略。

## 设计取舍

- **取舍 1**：为实用性选择 **policy-dependent soundness**——宁可多报 false positive（保守加边）也不漏 true dependency（safe Rust 下保证）；开发者应像对待 linter 一样对待输出。
- **取舍 2**：专注 Rust，换取类型系统带来的库建模与可扩展性；C++/Java/Python 生态需另建分析后端。
- **边界条件**：unsafe、RefCell 等 interior mutability、动态分派、async 控制流会增加漏报；liveness 策略对 false dependency 敏感（可能误报），deletion 类策略对漏 dependency 敏感。

## 实验与结果

- 8 个 Rust web 应用（Atomic、Plume、Lemmy、Hyperswitch、mCaptcha、WebSubmit、Freedit、Contile）：5 已知 + 2 未知 bug，开发者已确认。
- 11 条策略中 IFC 只能表达 6 条；Paralegal 覆盖 liveness（如「必须删除」）而 IFC 不能。
- vs CodeQL：跨过程控制流、async、未实例化模板、库建模、C++ alias 等多处 CodeQL 失败，Paralegal 通过。
- Atomic 长期演化：marker 改动罕见，策略零修改仍有效。
- 性能：198k LOC 秒级；适合 IDE/CI 交互使用。

## Critical Analysis

### 论证链条

观察（隐私 bug 常是依赖路径缺失）→ marker+PDG 查询可表达 deletion/liveness → Rust 类型近似降低库建模成本 → 真实应用找到 unknown bugs。链条在「Rust web 应用 + 合作式标注」场景闭合较好；对「零标注全自动」claim 论文未做。

### 假设压力测试

- 大型 monorepo 若 unsafe/FFI 比例高，类型近似可能系统性漏报。
- marker 维护在 churn 极高的微服务可能不如 Atomic 案例乐观。
- 策略表达能力仍有限：论文承认无 universally sound PDG 近似。

### 实验可信度

8 个应用 + 与 IFC/CodeQL 对比有说服力；缺非 Rust 语言、缺与商业 SAST 全面对标。性能与长期维护证据（Atomic）是亮点。

### 系统性缺陷

论文未讨论：多租户 CI 下策略版本治理、误报率量化与开发者疲劳、与运行时监控的互补。部署到「大型互联网公司」仍在评估阶段。

## 局限与 Future Work

- **局限 1**：static analysis 只能推理编译期已知信息；unsafe/interior mutability 破坏保证。
- **局限 2**：soundness/completeness 依赖具体策略，非单一全局保证。
- **Future work 1**：量化 marker 维护成本与误报率随团队规模的变化；扩展 async/动态分派精度。
- **Future work 2**：将 marker 层抽象迁移到其他具备别名分析的语言（需重新设计近似）。

## 相关

- **相关概念**：Program Dependence Graph、Information Flow Control、Static Analysis
- **同类系统**：CodeQL、Flowistry、DroidSafe、PrivGuard
- **同会议**：[[OSDI-2025]]