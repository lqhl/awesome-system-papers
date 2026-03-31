# Paralegal: Practical Static Analysis for Privacy Bugs

**作者**：Justus Adam, Carolyn Zech, Livia Zhu, Sreshtaa Rajesh, Nathan Harbison, Mithi Jethwa, Will Crichton, Shriram Krishnamurthi, Malte Schwarzkopf（Brown University）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会），July 7–9, 2025, Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/adam
**源文件**：[osdi25-adam.pdf](../../papers/osdi-2025/osdi25-adam.pdf)

---

## 一、背景

处理敏感用户数据的应用必须遵守 GDPR 等隐私法规和访问控制要求。随着代码库规模增大、参与开发人员增多，在日常开发过程中持续保证隐私合规愈发困难——一个人的代码改动可能在不知情的情况下引入隐私漏洞。目前业界主要依赖人工审计或外部合规顾问，成本高、频次低、容易出错。

代码分析工具本可以补充人工审计，但现有工具要么领域过于专用（仅支持特定框架）、要么需要大量手动编写库模型（如 CodeQL）、要么采用过于学术化的类型系统（如 IFC）而难以在工程实践中推广。

---

## 二、要解决的问题

**核心问题**：现有隐私 bug 检测工具缺乏实用性，主要体现在三个维度：

1. **库代码处理困难**：现实软件大量使用第三方库。要么忽略库代码（漏报）、要么要求开发者手工维护大量库模型（如 CodeQL 维护了数万行 C++ 标准库模型），成本极高。

2. **策略表达能力不足**：
   - IFC（信息流控制）只能表达"信息不能从 A 流向 B"（safety 属性），无法表达"数据必须流向删除函数"（liveness 属性），也无法处理访问控制与撤销许可等复杂策略。
   - CodeQL 策略直接引用代码符号（函数名、正则表达式匹配），与代码实现深度耦合，代码重构后策略极易失效。

3. **工程可维护性差**：策略编写者（隐私工程师）需要深入了解应用代码细节；代码演进时策略需要频繁同步更新，负担沉重。

---

## 三、核心设计

Paralegal 的核心思路是：通过**分层职责划分**同时解决表达能力、库代码处理、和可维护性三个问题。

### 3.1 Marker 抽象

Marker 是策略与代码之间的语义桥梁。**隐私工程师**用 marker 名称（如 `user_data`、`make_delete_query`、`executes`）写策略，无需了解代码；**应用开发者**将 marker 注解（`#[paralegal::marker(user_data)]`）贴到具体代码实体（函数、参数、返回值、类型定义）上，并随代码演进维护这些注解。

这一分工带来两个好处：
- 策略层只涉及业务语义，独立于实现细节，不随代码重构而失效。
- Paralegal 可以利用 marker 的位置信息优化 PDG 构建规模。

### 3.2 带 Marker 的程序依赖图（Marked PDG）

Paralegal 从 Rust 编译器的 MIR（中间表示）中提取 PDG（Program Dependence Graph），具备三个关键敏感性：

- **Flow-sensitivity**：区分同一变量在不同程序位置的值（避免误判 query 构造和执行的顺序）
- **Context-sensitivity**：通过函数克隆（function cloning）区分同一函数的不同调用上下文
- **Field-sensitivity**：区分结构体的不同字段（如 `my_data.posts` 与 `my_data.comments`）

### 3.3 Rust 类型系统驱动的库代码近似

对于没有源代码的第三方库，Paralegal 利用 Rust 类型系统进行**模块化近似**（modular approximation），无需手工建模：

- **Mutability**：Rust 不可变引用保证函数不能修改通过 `&T` 传入的数据，因此 `HashMap::remove(&mut self, key: &K)` 中只有 `self` 可能被修改，key 不会。
- **Lifetimes**：Rust 生命周期标注精确指示引用可能指向的对象范围，限制别名集合大小，减少误报。

此外，Rust 的 trait 系统鼓励静态分派，Paralegal 利用单态化（monomorphization）将 trait 方法调用解析为具体实现，提高分析精度。

### 3.4 自适应近似优化

Paralegal 不会无差别地分析整个代码库，而是根据 marker 可达性剪枝：仅当某个函数调用链上**可能触达** marker 时才构建子图，否则用类型签名近似其行为。这一"自适应近似"（adaptive approximation）大幅减小 PDG 规模。

### 3.5 策略语言

Paralegal 提供一个仿法律文书风格的受控自然语言 DSL，可表达对 marked PDG 的**一阶逻辑断言**，原语包括：

- `"value" goes to "sink"`：数据流路径存在
- `"value" affects whether "operation" happens`：控制流依赖
- `"value" goes to "sink" only via "disclosure"`：带中间节点的路径约束（用于 declassification）

策略被编译为调用低级 Rust API 的 Rust 程序，对 marked PDG 执行查询。

---

## 四、实现细节

- **代码规模**：15.1k 行 Rust，作为 Rust 编译器插件（rustc compiler plugin）实现，作用于 MIR 层。
- **多 crate 支持**：Paralegal 通过持久化 MIR、lifetime 关系和 marker 注解跨 crate 构建 PDG。Lemmy 的所有 crate 元数据合计 411 MB（rustc 本身产生 258 MB）。
- **async 处理**：刻意丢弃 Rust async 状态机引入的控制流边，避免对隐私工程师不透明的误报，代价是无法检测恶意的 hung future 等异步安全模式。
- **错误信息**：借鉴 Rust 编译器的诊断框架，错误报告将 PDG 节点关联到具体源码行，并输出违规路径（见 Figure 4）。
- **IDE/CI 集成**：面向两种使用模式——"WorkspaceOnly"（仅分析当前 workspace，使用近似处理外部依赖）用于交互式开发；"AllDependencies"（分析全部可达源代码）用于 CI。

---

## 五、实验结果

### 5.1 评估应用

| 应用 | 类型 | LoC | 策略类型 |
|------|------|-----|---------|
| Atomic v0.34.2 | GraphDB | 9.6k | AccessControl |
| Contile v1.11.0 | 广告服务 | 4.9k | PurposeLimitation |
| Freedit v0.6.0-rc.3 | 社交平台 | 6.6k | DataRetention/Expiration |
| Hyperswitch v0.2.0 | 支付系统 | 198.9k | CredentialSecurity, LimitedCollection |
| mCaptcha v0.1.0 | 认证服务 | 10.6k | DataDeletion, LimitedCollection |
| Lemmy v0.16.6 | 社交平台 | 31.4k | AccessControl（72 个 HTTP 端点） |
| Plume v0.7.2 | 博客系统 | 21.4k | DataDeletion |
| WebSubmit v1.0 | 作业提交 | 1.6k | DataDeletion, AccessControl |

### 5.2 Bug 发现

| 应用 | Bug 描述 | 是否为新发现 |
|------|---------|------------|
| Plume | 删除用户时未删除评论和媒体文件 | 否（known） |
| Atomic | 用户可绕过权限校验给自己写权限 | 否（known） |
| Lemmy | 已封禁/删除用户可登录 | 否（known） |
| Lemmy | 用户可向已删除社区发帖 | 否（known） |
| Lemmy | 已封禁用户可在社区内操作 | 否（known） |
| Lemmy | 16 个端点缺少社区删除校验 | **新发现（confirmed）** |
| Lemmy | 部分控制器缺少社区封禁校验 | **新发现（confirmed）** |

### 5.3 与基线对比（11 条策略）

| 工具 | 可表达策略数 | 可正确执行策略数 |
|------|------------|----------------|
| 经典 IFC | 6/11 | 6/11（但需额外代码改动） |
| CodeQL | 11/11（可表达） | 约 7/11（实际执行有缺陷） |
| Paralegal | 11/11 | 11/11 |

CodeQL 失败原因涵盖：控制流分析不跨函数、库代码无数据流建模、结构体字段 taint 传播缺失、无别名分析、模板代码无法分析、async 代码支持缺失。

### 5.4 性能

| 配置 | 多数应用 | Lemmy（72 端点） | Hyperswitch（198k LoC） |
|------|---------|----------------|------------------------|
| WorkspaceOnly | < 2.2s | 22.5s | 12s |
| 每端点（IDE 模式） | ~0.8s（均值），< 5s（最坏） | — | — |
| AllDependencies | < 5s | 94s | — |

### 5.5 可维护性

对 Atomic 的 1,024 个提交（2.5 年演进）跑 Paralegal，仅发生 2 次 marker 需要调整的情况，策略代码全程无需修改。

### 5.6 自适应近似效果

相比固定深度 k 的理想基线，自适应近似平均节省 35% 运行时间；对 Lemmy 和 Plume，固定 k 会在 15 分钟内超时，自适应近似是其能够终止的必要条件。

---

## 六、批判性分析

**1. 评估规模偏小，且存在自评偏差**

8 个应用，最大 198k LoC，策略数量合计仅 11 条。发现的"新 bug"仅 2 个，均在 Lemmy 这一应用。论文声称 Paralegal 被"某大型互联网公司"评估使用，但未提供任何具体数据。这种背书在系统论文中常见，但缺乏可验证性。

**2. 与 CodeQL 的对比存在系统性不公平**

作者将 Rust 代码人工移植为 C++ 后才能使用 CodeQL，承认这一翻译无法保证完全等价（C++ 异常 vs. Rust Result，async 语义差异等）。这导致 CodeQL 的多项失败（T、¶ 标注）来自阻抗失配，而非 CodeQL 本身在原生语言上的能力。论文在 Figure 8 的图例中确实标注了这些原因，但在结论部分仍将其归纳为"Paralegal 更好"，有过度解读之嫌。

**3. 策略的正确性本身无法自动验证**

Paralegal 检查"代码是否符合策略"，但并不验证"策略是否正确表达了隐私意图"。论文案例中 mCaptcha 就出现了策略写错（误解开发者意图）的情况。这是一个根本性局限——工具的价值依赖于策略的正确性，而策略正确性仍需人工保证，这一链条的脆弱性被轻描淡写。

**4. Rust 生态的适用范围限制**

整个系统深度依赖 Rust 的类型系统（所有权、生命周期、trait 单态化）来实现库代码近似和精度保证。论文虽然承认这一点，但对其迁移到其他语言的路径没有讨论。实际上，大量高价值的隐私敏感代码库仍以 Java、Python、Go 为主，Rust 专用的工具覆盖面有限。

**5. unsafe 代码与 interior mutability 的处理存在静默漏洞**

Paralegal 对 unsafe 块和 `RefCell`/`Mutex` 等 interior mutability 原语的处理会导致**漏报（false negative）**——但漏报在隐私合规场景中后果更严重（误以为安全，实则不安全）。论文承认了这一点，但仅以"在我们的评估应用中 interior mutability 很少见"为由轻描带过。Hyperswitch（198k LoC 支付系统）若有此类代码，漏报的代价可能极高。

**6. 性能数据缺乏基准上下文**

"大多数应用 2.2 秒以内"听起来快，但这只是 WorkspaceOnly 模式，AllDependencies 模式下 Lemmy 需要 94 秒，且仅 88-878 个 crate。现实大型工程（如 Mozilla 或 Google 的代码库）依赖规模远超于此，外推空间不确定。

---

## 七、总结

Paralegal 是一个面向 Rust 程序的实用隐私 bug 静态检测工具，其核心贡献在于通过 **marker 抽象**将隐私策略与代码实现解耦，并借助 **Rust 类型系统**（所有权、生命周期）无需手工建模即可近似第三方库行为，从而在实用性和表达能力上超越 IFC 和 CodeQL。在 8 个真实 Rust Web 应用上，Paralegal 找到了 2 个新 bug，策略可以跨越 2.5 年的代码演进保持稳定，大多数应用在秒级内完成检测。主要局限在于专为 Rust 设计、不处理 unsafe 代码与运行时依赖的策略、以及策略本身的正确性仍依赖人工保证。
