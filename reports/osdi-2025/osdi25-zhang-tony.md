# Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols

**作者**：Tony Nuda Zhang, Keshav Singh (University of Michigan); Tej Chajed (University of Wisconsin-Madison); Manos Kapritsos (University of Michigan); Bryan Parno (Carnegie Mellon University)
**会议**：OSDI 2025 (19th USENIX Symposium on Operating Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/osdi25/presentation/zhang-tony
**源文件**：[[osdi25-zhang-tony.pdf]]

---

## 一、背景

分布式协议的正确性验证是系统领域的核心挑战。形式化验证通过证明协议满足某个安全性质（safety property）来保证其正确性，而这需要找到一个归纳不变量（inductive invariant），满足三个条件：（1）蕴含安全性质，（2）在初始状态成立，（3）对所有状态转移封闭。

找到归纳不变量是一个极其困难的任务。现有方法要么要求开发者手动推导（如 IronFleet，Multi-Paxos 的归纳不变量花了数月），要么要求将协议限制在可判定逻辑片段（如 EPR）中以实现自动化。EPR 本身有严格限制，禁止算术等常见编程模式，且将协议翻译为 EPR 本身就很困难。

前序工作 Kondo 在不可判定逻辑下迈出了一步，提出了不变量分类法，能自动生成部分不变量，但仍需开发者手动推导跨主机属性（inter-host properties），这些属性往往需要深刻理解协议为何正确，对专家来说也需要数周时间。

---

## 二、要解决的问题

1. **手动推导归纳不变量极其费力**：在不可判定逻辑框架中，开发者需要经历痛苦的"不变量-证明循环"——猜测候选不变量、尝试证明、失败后修改、再尝试，可能迭代很多次。IronFleet 中 Multi-Paxos 的证明耗时数月。

2. **跨主机属性难以自动化**：Kondo 能自动生成部分简单不变量（如 Send Invariants），但跨越多个主机和协议步骤的属性（inter-host properties）仍需开发者凭直觉手动推导和证明，这是最困难、最需要创造力的部分。

3. **可判定逻辑的限制过于严格**：EPR 等可判定逻辑虽然支持自动化，但禁止算术、∀∃ 量词等常见模式，将协议翻译为 EPR 本身就是一项专家级任务，且并非所有协议都能表达。

---

## 三、洞察与设计

**关键洞察**：复杂的跨主机属性（inter-host properties）其实可以分解为多个简单的 Provenance Invariants 的组合——每个 Provenance Invariant 只需要通过静态分析单个主机的步骤就能推导出来。具体而言，如果主机 R 的状态变量 x=5，可以追溯到最近更新 x 的协议步骤所接收的消息 M，而 M 又可以追溯到发送者 S 的状态，从而建立 R 和 S 之间的因果链——这条链完全由局部的 Provenance Invariants 构成。

基于此洞察，论文提出两个核心技术：

### Provenance Invariants

一类新的不变量，分为两种：

- **Network-Provenance Invariant**：将网络中的消息关联到发送它的主机步骤。例如"网络中每条 DECIDE 消息，都能在协调者的历史中找到执行了 CoordinatorSendDecide 步骤的相邻状态对"。
- **Host-Provenance Invariant**：将主机当前状态的某个局部属性关联到使该属性成立的步骤。例如"如果参与者的 decision 为 Commit，则其历史中必存在执行了 ParticipantReceiveDecision 的步骤"。

关键性质：每个 Provenance Invariant 天然是归纳的（trivially inductive），因为执行历史是不可变的（immutable），一旦某步骤执行的事实被记录在历史中，后续转移永远无法使其变为假。

### Atomic Sharding 算法

自动识别主机变量中的"原子碎片"（atomic shard）——一组总是被原子地同时更新的变量子集。通过三个阶段实现：

1. **估算足迹**（Footprint Estimation）：静态分析每个步骤可能修改的变量集合
2. **计算最大原子碎片**：通过足迹的 Venn 图分析找到最大原子碎片
3. **精化集合类型碎片**：对集合/映射等集合类型变量进一步拆分，以追踪单个元素的来源

### 跨主机属性的推导

通过链式组合 Provenance Invariants 来推导跨主机属性。例如证明"如果某参与者决定 Commit，则协调者也决定了 Commit"：先用 Host-Provenance 追溯参与者的 Commit 决定到接收的 DECIDE 消息，再用 Network-Provenance 追溯该消息到协调者的发送步骤，最后由步骤的语义得出协调者的决定也是 Commit。

---

## 四、实现细节

Basilisk 基于 Kondo 代码库实现，后者本身是 Dafny 4.2 验证器的扩展。Basilisk 在 Dafny 验证器上新增约 2,000 行 C# 代码。

**开发者工作流程**（四步）：

1. **协议定义**：用户以 Dafny 编写主机状态、初始化条件和状态转移关系。Basilisk 比 Kondo 更宽松，允许单个步骤同时接收和发送消息。
2. **自动生成异步协议模型**：Basilisk 自动构建带历史记录的异步消息传递协议 P_h，包含全局状态（主机历史序列 + 网络消息集合）。
3. **自动生成归纳不变量**：Basilisk 通过 atomic sharding 自动生成 Provenance Invariants 和 Monotonicity Invariants 的合取作为归纳不变量 I，并自动证明 I 的归纳性。
4. **用户证明安全性**：用户编写 Dafny lemma 证明 I 蕴含安全性质。这是唯一需要创造力的步骤，但比手动找不变量简单得多。

**足迹计算**：通过解析 Dafny 的状态更新语法（`v' = v.(Z₁ := X₁, ..., Zₖ := Xₖ)`）自动提取。安全地过估（over-estimate）但不欠估。

**处理条件更新**的限制：如果一个步骤中两个变量通过不同条件更新（如 `if c then x:=5 else y:=6`），Basilisk 会拒绝，要求用户拆分为两个步骤。

---

## 五、实验结果

在 16 个分布式协议上评估，包括 Echo Server、Ring Leader Election、Paxos（及其变体）、Multi-Paxos、Two-Phase Commit、Three-Phase Commit、Raft Leader Election 等。

| 指标 | Basilisk | Kondo |
|------|----------|-------|
| 用户手写不变量数量 | 全部协议为 **0** | 大多数协议需要手写（Paxos 需 20 条） |
| 用户提供的 Provenance hints | 64 条 Host-Provenance 中仅 6 条需要 hint | N/A |
| 协议定义代码量 | 显著更少（如 Paxos: 418 vs 631 行） | 因不允许同时收发消息而代码膨胀 |
| 安全性证明代码量 | 竞争力强（Flexible Paxos: 441 vs 559 行） | 还需额外定义不变量（200+ 行） |
| 验证时间 | 更快（Flexible Paxos: 22.8s vs 49.4s，Multi-Paxos: 61.5s） | 更慢 |

关键数据：

- Basilisk 在全部 16 个协议上成功找到归纳不变量，**零用户手写不变量**
- Multi-Paxos 验证时间仅 61.5 秒（Kondo 未能完成该协议）
- Kondo 仅完成了 16 个协议中的 10 个

---

## 六、批判性分析

1. **评估对象的选择偏差**：论文承认前 6 个协议用于开发和调试 Provenance Invariants 概念，然后才应用到其余协议。这意味着核心技术可能天然地为这些协议量身定制，而 16 个协议的规模难以充分验证泛化能力。

2. **Atomic Sharding 的理论完备性缺失**：论文承认 atomic sharding 不能发现所有 Host-Provenance Invariants（如变量间隐式关系的情况），但将理论分析留给"future work"。缺乏对哪类协议会失败的系统性刻画，仅给出了一个 year/events 的示例。

3. **"零用户不变量"的表述略有误导**：虽然用户不需要手写不变量子句，但仍需提供 monotonicity 注解、ownership 标签以及 provenance hints（共计 6 个）。更重要的是，用户仍需编写安全性证明 lemma（Multi-Paxos 需 522 行），这本身仍需要对协议的深入理解。

4. **与 Kondo 的比较不完全公平**：Kondo 的 5 个缺失协议标注为"由于适配限制所需的工作量"而未完成，但这是否说明 Basilisk 在这些协议上的优势来自更宽松的输入规范而非更好的自动化能力？论文未对此进行控制实验。

5. **验证时间加速的归因不清晰**：论文假设加速来自更少的主机步骤和用户直接编写异步证明。但缺乏消融实验来量化这两个因素的各自贡献。

6. **实际系统的适用性未验证**：所有协议都是教科书级别的经典协议（规模在 100-450 行），而实际生产系统的协议可能复杂得多。IronFleet 报告 Multi-Paxos 的不变量推导花费数月，但那是在完整实现上，而非简化的协议模型上。

---

## 七、总结

Basilisk 提出了 Provenance Invariants 这一新型不变量类别，通过将复杂的跨主机属性分解为可从单个主机步骤局部推导的简单不变量，并结合 atomic sharding 算法实现自动化生成。在 16 个分布式协议（包括 Multi-Paxos）上，Basilisk 能在无用户手写不变量的情况下自动找到归纳不变量并证明其归纳性。该工作显著降低了在不可判定逻辑框架中验证分布式协议的门槛，但其适用范围仍限于崩溃容错的异步消息传递协议，且对实际规模的生产系统协议的验证能力有待进一步验证。
