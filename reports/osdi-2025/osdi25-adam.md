# Paralegal: Practical Static Analysis for Privacy Bugs

## 论文基本信息

- **标题**: Paralegal: Practical Static Analysis for Privacy Bugs
- **作者**: Justus Adam, Carolyn Zech, Livia Zhu, Sreshtaa Rajesh, Nathan Harbison, Mithi Jethwa, Will Crichton, Shriram Krishnamurthi, Malte Schwarzkopf (Brown University)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/adam
- **开源**: https://github.com/withparallax/paralegal

---

## 研究背景与动机

现代软件处理大量敏感用户数据，必须遵守 GDPR 等隐私法规和数据保留限制。然而，代码库规模大、贡献者多、第三方库广泛使用，使得隐私合规在实践中极为困难。现有解决方案存在根本性局限：专用工具局限于特定领域，通用安全类型化编程语言要求函数式风格或大量注解，通用代码分析工具（如 CodeQL）对库代码需要手动建模，且策略编写者被鼓励直接查询语法构造而非语义属性，导致策略脆弱。

---

## 要解决的核心问题

如何设计一个实用的隐私漏洞静态分析工具，满足四个成功标准：
1. 能发现真实隐私漏洞
2. 策略表达力强、维护性好、与应用代码细节解耦
3. 策略可由非开发者（隐私工程师）审计
4. 可扩展到真实应用

核心挑战在于：隐私工程师与应用开发者之间技能不对称（隐私工程师不熟悉代码，开发者不熟悉隐私合规）；第三方库没有源码可用；代码频繁变化，策略需要鲁棒。

---

## 主要贡献

1. **Paralegal 静态分析器**：将高层属性（隐私策略）转换为对低层代码 PDG（程序依赖图）的查询
2. **Marker 抽象**：在策略和代码之间引入语义层，分离关注点；开发者维护 marker 与代码元素的关联，隐私工程师撰写策略
3. **灵活的策略框架**：将策略编译为对带标记 PDG 的查询，提供可读的错误消息
4. **实践经验**：在 8 个真实 Rust Web 应用上的案例研究

---

## 研究方法与设计

### 核心设计：Marker 抽象

**Marker** 是附加到代码实体（函数、参数、返回值、类型定义）的抽象标签，如 `user_data`、`deletes`。Marker 由应用开发者维护，与代码一同演进；隐私工程师基于 marker 撰写策略，无需了解代码实现细节。

关键设计点：
- Marker 不直接标记代码中的每一个变量，而是通过 PDG（程序依赖图）传播：类型上的 marker 传播到使用该类型的所有节点
- 隐私工程师在 marker 层面表达策略，不直接引用函数名或类型名

### 程序依赖图（PDG）

Paralegal 从 Rust MIR（中级中间表示）构建 PDG，包含：
- **数据依赖**：值如何从一个变量流向另一个
- **控制依赖**：条件分支如何影响执行

PDG 要求三个精度属性：
1. **流敏感（Flow-sensitive）**：区分同一变量在不同程序位置的值
2. **上下文敏感（Context-sensitive）**：区分同一函数在不同调用上下文中
3. **字段敏感（Field-sensitive）**：区分结构体的不同字段

### Rust 所有权类型系统的利用

利用 Rust 的两个特性实现高效精确的分析：

1. **不可变引用不产生变异**：Rust 不允许通过不可变引用修改数据，因此函数调用不会变异不可变引用指向的值。Paralegal 可假设 `HashMap::remove` 只修改 `self` 而不修改 `key`。

2. **生命周期（Lifetime）精确别名分析**：Rust 生命周期注解表明精确的、有限的可能别名集合。例如 `HashMap::get` 返回生命周期 `'a` 的引用，表明指向 `self` 而非 `key`。

3. **模块化近似**：对于没有源码的第三方库，使用 Rust 类型系统近似函数行为。若函数体中无可达 marker，则根据类型签名近似函数效果——这比精确分析开销小，且精度足够。

### 策略语言

Paralegal 策略是一种受法律文件启发的受控自然语言语法，编译为 Rust 程序，查询带标记 PDG 上的以下原语关系：
- `"value" marked sensitive`：绑定标记敏感的 PDG 节点
- `"value" goes to "sink"`：数据流路径存在性
- `"value" affects whether "operation" happens`：控制依赖
- `"value" goes to "sink" only via "disclosure"`：所有路径必经某个中间节点（用于信息泄露）

策略语言是可判定的（PDG 有限、可达性可判定、量词有限），且不支持递归策略。

---

## 关键实现细节

- **代码规模**：15.1k 行 Rust，作为 Rust 编译器插件实现
- **多 crate 支持**：跨多个编译 crate 分析，MIR 和 marker 元数据持久化（最大案例达 411MB 元数据）
- **异步代码处理**：故意丢弃 await 引入的状态机控制流（避免混淆的误报）
- **错误报告**：诊断框架将 PDG 节点映射回源代码位置，提供类似 Rust 编译器的错误消息

---

## 实验结果与分析

### 漏洞发现

在 8 个真实 Rust 应用上评估，发现：
- **5 个已知漏洞**：Paralegal 能检测出
- **2 个新漏洞**（Lemmy 平台）：被开发者确认
  - 被禁用户仍可向社区写内容（banned community moderator 可以解除自己的封禁）
  - Lemmy 中 72 个 HTTP 端点中 16 个缺少社区删除检查

### 与 IFC（信息流控制）和 CodeQL 的对比

| 应用 | IFC | CodeQL | Paralegal |
|------|-----|--------|-----------|
| Atomic 授权 | 部分可表达 | 失败 | 通过 |
| Plume 数据删除 | 失败 | 通过 | 通过 |
| Lemmy 访问控制 | 部分可表达 | 失败 | 通过 |
| Freedit 数据保留 | 失败 | 失败 | 通过 |

**CodeQL 的主要失败原因**：
- 控制流分析不是过程间的
- 库调用被视为无数据流
- 字段级污点传播需要手动建模
- 别名分析缺失（性能问题）

**Policy 维护性**：在 Lemmy 超过 1000+ 提交、2.5 年开发历史中，marker 变更罕见，策略无需修改。

### 性能

- 优化后 PDG 生成可在秒级完成，适合频繁交互使用
- 对 198k LOC 的 HyperSwitch 也能正常运行

---

## 潜在问题与局限性

### 核心局限

1. ** Unsound 静态分析**：
   - **Unsafe 代码**：Rust unsafe 块内的指针运算可能引入未知别名，Paralegal 无法建模
   - **内部可变性（Interior Mutability）**：`RefCell<T>` 等允许通过不可变引用修改数据，违反类型系统假设
   - **外部效应**：对文件系统、数据库的副作用无法建模
   - **自适应近似**：Paralegal 通过保守假设包含假依赖（而非遗漏真依赖），这意味着可能出现假阳性而非假阴性

2. **Marker 表达力有限**：
   - 目前只支持函数、参数、返回值和类型定义，不支持字段或常量
   - 为此需要引入 no-op 包装函数来施加 marker

3. **异步代码**：丢弃了 await 状态机控制流，无法检测某些恶意异步模式

4. **策略可判定性**：不支持递归策略

### 实践局限

- 作为 Rust 编译器插件实现，绑定到特定 Rust 版本（nightly-2023-08-25）
- 策略健壮性依赖于 marker 注解的完整性和正确性
- 依赖 Rust 所有权系统，不适用于其他语言

---

## 未来工作方向

- 支持更多 Rust 语言特性（如 async runtime 细节处理）
- 扩展 marker 可附加的元素范围（字段、全局变量）
- 与 IDE 深度集成（实时反馈）
- 自动化 marker 推荐

---

## 个人评注

### 优势

1. **设计优雅**：Marker 抽象完美地解决了隐私工程师与应用开发者之间的技能不对称问题，将"谁负责什么"分离得非常清晰
2. **工程扎实**：15.1k 行 Rust 代码的原型，支持真实应用，18 个月以上生产部署
3. **与 Rust 类型系统的深度结合**：充分利用所有权、生命周期等特性是本文的核心创新

### 潜在争议

1. **"假依赖"取舍**：论文明确说明 Paralegal 偏向包含假依赖而非遗漏真依赖（保守包含）。这导致假阳性而非假阴性。论文原话是"Paralegal errors on the side of including false dependencies rather than omitting true dependencies"，但随后的 Limitations 章节中又提到"including a false dependency can cause a false-positive for policies like 'secure sources cannot flow to insecure sinks', while it may cause a false-negative for policies like 'user data must flow to a deletion function'"。这两处表述存在微妙矛盾：前者说总是包含假依赖，后者说有时会导致假阴性。实际上，由于保守估计，Paralegal 应该更倾向于假阳性（报告不存在的漏洞），而非假阴性（遗漏真实漏洞）。"errors on the side of"应理解为"宁可多报，不可漏报"，这符合隐私合规的实践需求。

2. **商业化进展**：论文称"正在被一家大型互联网公司评估"——这是较弱的承诺，与"已在生产使用"之间还有差距，读者应适度降低预期。

3. **评估规模**：8 个应用，规模从 1.6k 到 198k LOC，涵盖多个领域（社交、支付、认证等），但缺乏对更大规模代码库（>500k LOC）的评估。
