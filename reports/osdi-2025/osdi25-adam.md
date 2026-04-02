# Paralegal: Practical Static Analysis for Privacy Bugs

**作者**：Justus Adam, Carolyn Zech, Livia Zhu, Sreshtaa Rajesh, Nathan Harbison, Mithi Jethwa, Will Crichton, Shriram Krishnamurthi, Malte Schwarzkopf（Brown University）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/osdi25/presentation/adam
**源文件**：[[osdi25-adam.pdf]]

---

## 一、背景

处理用户敏感数据的应用必须遵守 GDPR 等隐私法规以及组织内部的访问控制和数据保留策略。在大型代码库中，众多开发者每天频繁修改代码，正确实现并持续遵守这些隐私要求极具挑战。目前，组织主要依赖隐私专家的人工审计来检查代码是否违反隐私属性，但人工审计成本高、容易出错，且难以频繁进行。

现有的代码分析工具在实用性方面存在显著不足：领域特定工具（如 DroidSafe、PrivGuard、RuleKeeper）局限于特定应用场景；通用安全类型语言（如 IFC 语言）要求函数式编程风格或大量注解，实际采用率极低；CodeQL 等通用代码分析引擎需要手动为库代码编写行为模型，且策略与代码语法高度耦合，维护成本高昂。

---

## 二、要解决的问题

1. **库代码建模困难**：现有工具要么忽略第三方库代码，要么要求开发者为库函数手动编写行为模型（如 CodeQL 维护了大量 C++ 标准库模型），这一过程繁琐且易出错。
2. **策略与代码紧耦合**：CodeQL 等工具的策略直接引用函数名或语法结构（如通过正则表达式匹配标识符），代码变动后策略即失效，维护成本高。
3. **表达能力不足**：传统 Information Flow Control（IFC）只能表达"禁止某类数据流"（safety property），无法表达"某类数据必须流向删除函数"（liveness property）等重要隐私属性。
4. **扩展性差**：精确的程序分析（flow-sensitive、context-sensitive、field-sensitive）代价高昂，现有工具难以在合理时间内完成对大型代码库的分析。

---

## 三、洞察与设计

**关键洞察**：Rust 的 ownership 类型系统从根本上控制了 aliasing 和 mutation，使得可以仅通过函数的类型签名就 sound 且 precise 地近似（approximate）第三方库函数的行为——无需源码、无需手动建模。结合 marker 标注识别策略相关代码的能力，大量无关代码可被安全跳过（adaptive approximation），从而实现对大型代码库的高效分析。

基于这一洞察，Paralegal 的设计包含三个核心组件：

1. **Program Dependence Graph（PDG）构建**：从 Rust 的 MIR（中间表示）提取 flow-sensitive、context-sensitive、field-sensitive 的 PDG。利用 Rust ownership 系统的两个特性进行 modular approximation：(a) 不可变引用保证函数不会修改其背后的数据，限制了可能的输出集；(b) lifetime 注解精确标识了引用的 aliasing 关系。通过 function cloning 实现 context-sensitivity，通过 monomorphization 解析 trait 方法的静态分发。

2. **Marker 抽象层**：引入 marker 作为策略与代码之间的解耦层。隐私工程师用 marker 定义抽象概念（如 `user_data`、`deletes`），开发者将 marker 标注到具体代码实体（类型、函数、参数）。这使策略独立于代码细节，且 marker 被用于 adaptive approximation——只有 marker 可达的函数才会被完整分析，否则使用类型签名近似。

3. **策略语言**：提供受控自然语言语法的策略 DSL，模仿法律文书的嵌套条款结构，支持一阶逻辑公式。策略原语包括 data flow（`goes to`）、control flow dependency（`affects whether`）和 declassification（`only via`），编译为 Rust 代码在 marked PDG 上执行查询。

---

## 四、实现细节

- **代码规模**：15.1k 行 Rust 代码，实现为 rustc 编译器插件，操作 Rust 的 MIR。
- **Multi-crate 支持**：通过持久化 MIR、lifetime outlives 关系、类型检查结果和 marker 注解实现跨 crate 分析。最大案例 Lemmy 的所有 crate 元数据合计 411MB。
- **Adaptive approximation 实现**：对每个函数调用，通过廉价的 call graph 遍历检查 marker 是否可达。结果被缓存复用。若无 marker 可达，则用类型签名近似函数效果，避免生成其子图。
- **Async 处理**：刻意丢弃 `await` 引入的状态机控制流，因为这些依赖关系在隐私语义上无意义，会导致令人困惑的误报。
- **Marker 传播**：对类型 marker，采用递归传播策略——若 marked type τ 出现在 τ' 内部（如 `Vec<τ>` 或包含 τ 字段的结构体），则 marker 传播到 τ' 对应的 PDG 节点。
- **策略编译**：DSL 策略编译为 Rust 代码，利用低级 API 查询 marked PDG。诊断框架借鉴 Rust 编译器的错误消息风格，将 PDG 节点关联到源码位置。

---

## 五、实验结果

**实验平台**：Intel Xeon E3-1230 v5 (3.4 GHz)，64 GiB RAM，Ubuntu 20.04，Rust nightly-2023-08-25。

**案例研究应用**（8 个真实 Rust Web 应用）：

| 应用 | 类型 | 代码量 | 策略 | Marker 数 | 标注位置 | 入口点 |
|------|------|--------|------|-----------|----------|--------|
| Atomic | Graph DB | 9.6k LoC | Access Control | 4 | 4 | 1 |
| Contile | Advertising | 4.9k LoC | Purpose Limitation | 3 | 5 | 1 |
| Freedit | Social | 6.6k LoC | Data Retention | 5 | 5 | 4 |
| Hyperswitch | Payments | 198.9k LoC | Credential Security, Limited Collection | 6 | 7 | 3 |
| mCaptcha | Auth | 10.6k LoC | Data Deletion, Limited Collection | 5 | 5 | 2 |
| Lemmy | Social | 31.4k LoC | Access Control | 8 | 145 | 72 |
| Plume | Blogging | 21.4k LoC | Data Deletion | 7 | 7 | 1 |
| WebSubmit | Homework | 1.6k LoC | Data Deletion, Access Control | 11 | 18 | 3 |

**Bug 发现**：
- 发现 **7 个真实隐私 bug**，其中 **2 个为此前未知**（Lemmy 中被封禁用户可操作已删除社区、被封禁的社区管理员可自行解封），**5 个为已知已修复 bug**。
- Paralegal 在所有 8 个应用上均无误报（Contile 在调整 k+=1 后消除）。

**与 IFC / CodeQL 的对比**（11 个策略）：

| 方法 | 成功表达并执行策略数 |
|------|----------------------|
| IFC | 6 / 11 |
| CodeQL | 5 / 8（3 个应用因代码量过大无法移植） |
| Paralegal | **11 / 11** |

CodeQL 的主要失败原因包括：过程间控制流分析缺失、库代码行为模型缺失、struct 字段 taint 传播需手动建模、不支持 async 等。CodeQL 策略中仅 36% 为真正的策略逻辑，其余 64% 为 marker 等价物、库模型和分析原语。

**维护成本**：在 Atomic 的 1,024 个 commit（跨 2.5 年）上运行，仅 2 个 commit 影响了 marker，策略本身完全不需要修改。

**性能**：

| 配置 | 典型运行时间 |
|------|-------------|
| Workspace Only | 大多数应用 < 2.2s（Hyperswitch 12s，Lemmy 22.5s） |
| Per-endpoint | 平均 0.8s（最慢 Hyperswitch < 5s） |
| All Dependencies | 大多数 < 5s（Lemmy 94s，72 个入口点） |

**Adaptive approximation 效果**：在 All Dependencies 配置下平均减少 35% 运行时间；对 Lemmy 和 Plume 而言，没有此优化则 PDG 构建无法在 15 分钟内完成。

---

## 六、批判性分析

1. **Rust 限定性过强**：Paralegal 的核心优势——利用 ownership 类型系统近似库函数行为——完全依赖 Rust 语言特性。这意味着该方法无法直接迁移到 Python、Java、Go 等主流语言，而绝大多数存在隐私合规需求的 Web 应用恰恰使用这些语言。论文对此局限性轻描淡写，但这本质上限制了 Paralegal 的实际影响力。

2. **Soundness 依赖策略**：论文承认 soundness 和 completeness 是 policy-dependent 的，但未提供系统性方法让用户判断给定策略下分析的可靠性。对于 unsafe 代码、interior mutability、外部副作用等场景，Paralegal 可能漏掉真实依赖关系，且用户难以预知哪些策略会受影响。

3. **评估规模有限**：8 个应用中最大的 Hyperswitch 为 198k LoC，但其仅分析了 3 个入口点。真正的大型生产系统可能有数千个入口点和数百万行代码。Lemmy 的 72 个入口点已导致 94 秒运行时间，scalability 在更大规模下存疑。

4. **CodeQL 对比的公平性**：由于 CodeQL 不支持 Rust，评估需要将 Rust 代码手动移植到 C++。这引入了多种阻抗失配（async、trait→template、ownership→raw pointer），使得 CodeQL 的失败可能部分归因于移植质量而非工具本身的能力。

5. **Marker 标注仍需手动**：虽然 marker 数量不多（4–145 个标注位置），但需要开发者理解隐私策略含义并正确对应到代码实体。论文报告在 6/8 个应用中需要修改源码（引入 no-op 函数或提取 helper），这对"非侵入式"的宣称有所折扣。

6. **缺乏误报/漏报的系统性量化**：论文仅报告了"发现了 N 个 bug"和"没有误报"，但未系统注入已知 bug 来测量 recall，也未在更大范围上测量 false positive rate。

---

## 七、AI Infra / MLSys 视角

本文主要关注隐私合规的静态分析，不直接涉及 AI 训练/推理系统。但其中部分思路对 AI Infra 有间接启发：

1. **ML 系统的合规性检查**：随着 AI 系统面临越来越多的数据隐私和安全法规（如 EU AI Act），类似 Paralegal 的静态分析方法有望用于检查 ML pipeline 中的数据处理是否合规——例如确保训练数据在 data subject 请求删除后被正确清理（machine unlearning 的验证）。

2. **Rust 在 AI Infra 中的采用**：随着 Hugging Face Candle、Burn 等 Rust ML 框架的兴起，以及 Rust 在高性能系统中的采用增加，Paralegal 有可能直接应用于这些 Rust 编写的 AI 基础设施组件，检查模型权重/用户数据的访问控制和数据保留策略。

3. **Adaptive approximation 思路的借鉴**：利用语言类型系统信息来决定分析深度的策略，可借鉴于 ML 编译器（如 TVM、XLA）中的优化 pass 分析——在已知类型约束下跳过不必要的分析路径。

4. **局限**：AI Infra 中大量核心组件使用 Python/C++/CUDA 编写，Paralegal 的 Rust 限定使其无法直接应用于 PyTorch、TensorFlow 等主流框架。

---

## 八、总结

Paralegal 是一个面向 Rust 程序的实用静态隐私 bug 检测工具，通过 marker 抽象解耦策略与代码、利用 Rust ownership 类型系统实现库代码的自动近似、并通过 adaptive approximation 优化分析规模。在 8 个真实应用上发现 7 个隐私 bug（含 2 个未知），表达力优于 IFC 和 CodeQL，运行时间满足交互式和 CI 使用需求。主要局限在于仅支持 Rust 语言、soundness 依赖具体策略、以及在超大规模代码库上的可扩展性尚未验证。
