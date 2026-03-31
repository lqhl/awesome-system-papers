# Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols

**作者**：Tony Nuda Zhang, Keshav Singh（University of Michigan）; Tej Chajed（University of Wisconsin-Madison）; Manos Kapritsos（University of Michigan）; Bryan Parno（Carnegie Mellon University）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation），2025年7月7–9日，Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/zhang-tony
**源文件**：[osdi25-zhang-tony.pdf](../../papers/osdi-2025/osdi25-zhang-tony.pdf)

---

## 一、背景

分布式协议（如 Paxos、Raft、Two-Phase Commit）出了名地难以正确设计。过去十年，研究者和工程师越来越多地转向形式化验证来提升协议的可靠性。形式化验证的核心任务是找到一个**归纳不变式（inductive invariant）**——一个比安全属性（safety property）更强的属性，满足：(1) 蕴含安全属性；(2) 在初始状态成立；(3) 在所有协议步骤下保持不变。

现有自动化方案存在根本性的分歧：允许任意逻辑表达（undecidable logic）的框架（如 IronFleet）要求开发者手工找到归纳不变式，代价极高（Multi-Paxos 证明据报需数月）；而自动化程度高的方案（如 I4、DuoAI、Kondo）则要求协议写在**有效命题推理（EPR）**等可判定逻辑片段内，对协议表达力有严苛限制，禁止算术运算等常见编程模式。

---

## 二、要解决的问题

**核心矛盾**：在 undecidable 设置下自动推导归纳不变式。具体痛点如下：

1. **手工推导归纳不变式代价太高**：IronFleet 风格的验证需要开发者创造性地猜测、反复修改候选不变式，Multi-Paxos 这类复杂协议需要数月时间。
2. **Kondo（最新先驱工作）的局限**：Kondo 将不变式分类为 Regular Invariants 和 Protocol Invariants，其中跨主机的 inter-host 属性（Protocol Invariants）仍需人工推导，Paxos 证明仍需专家花费两个人周手写 20 条此类属性。
3. **EPR 约束过于严格**：所有高度自动化的工具都要求协议在 EPR 中表达，而 EPR 禁止量词交替（∀∃）和算术等，协议翻译本身就是专家工作，且对很多协议根本不可行。

**目标**：在 undecidable 逻辑下，以最少的用户交互，自动找到足以证明分布式协议安全性的归纳不变式。

---

## 三、核心设计

### 3.1 Provenance Invariants

论文提出 **Provenance Invariant** 这一新型不变式，将主机的当前状态与产生该状态的协议步骤（provenance，"来源"）关联起来。这一思想源于对执行历史（execution history）的分析：不变式描述的是"某个状态值是由哪个步骤造成的"这一事实，而历史是不可变的，因此每条 Provenance Invariant 天然是归纳不变式。

两类 Provenance Invariant：

- **Network-Provenance Invariant**：网络中某条消息 *m*，必然是某个特定主机步骤（集合）发送的。例如："网络中每条 DECIDE 消息，在 coordinator 的历史中必然有相邻状态对通过 CoordinatorSendDecide 步骤发送了它。"
- **Host-Provenance Invariant**：主机当前状态满足某属性 *q*（provenance witness），则历史中必然存在某个步骤使 *q* 首次成立。例如："若参与者决定了 Commit，其历史中必然有 ParticipantReceiveDecision 步骤发生。"

**关键洞察**：复杂的 inter-host 属性（如"若某参与者决定 Commit，则 coordinator 也决定 Commit"）可以通过链式组合多条 Provenance Invariant 推导出来，无需开发者手动构造这些全局关系。

### 3.2 Atomic Sharding 算法

为了自动推导 Host-Provenance Invariants，论文提出 **atomic sharding** 算法：

1. **Footprint 估计**：对每个主机步骤，静态分析其可能修改的局部变量集合（只过估计，不会漏算）。
2. **原子 shard 识别**：若一组变量 σ 总是被同一批步骤整体更新（没有步骤只更新 σ 的一部分），则 σ 构成一个原子 shard。
3. **Shard 精炼**：对集合类型变量（set/map）进一步细化，更精确地追踪元素级别的 provenance。

原子 shard 原则：若某 shard 中的变量已离开初始值，则必有某步骤修改过它——由此可自动生成对应的 Host-Provenance Invariant。

### 3.3 不变式分类体系

Basilisk 在 Kondo 的 Regular Invariant 分类上做了扩展：

| 类别 | 来源 | 自动化程度 |
|------|------|-----------|
| Provenance Invariants（本文新增） | atomic sharding 自动生成 | 高（偶尔需要 provenance witness 提示） |
| Monotonicity Invariants | 继承自 Kondo | 全自动（需用户标注单调类型） |
| Ownership Invariants | 继承自 Kondo | 全自动（需用户标注所有权） |

---

## 四、实现细节

**工具 Basilisk** 基于 Kondo 代码库（后者又基于 Dafny 4.2 验证器）实现，向 Dafny verifier 添加约 2,000 行 C# 代码。

**开发者工作流**（图 5）：
1. **Step 1（用户）**：用 Dafny 定义协议——主机类型、状态字段、初始条件、步骤关系，以及单调/所有权类型标注。
2. **Step 2（Basilisk 自动）**：生成 history-preserving 异步协议模型 $P_h$，维护全局历史序列和异步网络（消息集合单调增）。
3. **Step 3（Basilisk 自动）**：对 $P_h$ 运行 atomic sharding，生成 Provenance Invariants + Monotonicity Invariants + Ownership Invariants 的合取 $I$，并自动证明 $I$ 的归纳性。
4. **Step 4（用户）**：用 $I$ 证明安全属性 $\phi$，只需证明 $I \Rightarrow \phi$（Ob1: Init 蕴含 $I \land \phi_h$；Ob2: $I \land \phi_h \land \text{Next} \Rightarrow I' \land \phi_h'$）。

若 Step 4 发现 $I$ 不够强，用户可提供 provenance witness 作为 hint，引导 Basilisk 生成更强的不变式（图 5 中虚线箭头）。

**Footprint 计算**：对 Dafny 状态更新语法 $v' = v.(Z_1 := X_1, \ldots, Z_k := X_k)$ 做句法分析，直接提取被修改字段；对 relation 形式（$r(v'.Z, v, m)$）目前暂不支持（prototype 限制）。

---

## 五、实验结果

**评测协议**：16 个分布式协议，覆盖 EchoServer、Ring Leader Election、Simple Leader Election、Paxos（标准/Combined/Dynamic）、Flexible Paxos、Distributed Lock、Sharded KV（普通/批量）、Lock Server、Two-Phase Commit、Three-Phase Commit、Reduce、Raft Leader Election、Multi-Paxos。所有协议均在 EPR 可判定逻辑之外。

**对比基线**：Kondo（OSDI 2024，前代最先进工具）

**关键结果（Table 1）**：

| 协议 | Basilisk 用户手写不变式 | Kondo 用户手写不变式 | Basilisk 协议代码行数 | Kondo 协议代码行数 | Basilisk 验证时间 | Kondo 验证时间 |
|------|---------|---------|---------|---------|---------|---------|
| EchoServer | 0 | 1 | 157 | 260 | 5.1s | 7.9s |
| Paxos | 0 | 20 | 418 | 631 | 24.6s | 42.9s |
| Flexible Paxos | 0 | 20 | 418 | 633 | 22.8s | 49.4s |
| Two-Phase Commit | 0 | 4 | 278 | 385 | 7.4s | 8.9s |
| Multi-Paxos | 0 | N/A（未评测） | 447 | — | 61.5s | — |

- **有效性**：Basilisk 对全部 16 个协议均自动找到足够的归纳不变式，无需用户提供任何 Protocol Invariant。
- **代码量**：Basilisk 协议描述比 Kondo 更简洁（允许 send+receive 合并为一步）。
- **用户证明努力**：Flexible Paxos 的安全性引理在 Basilisk 下比 Kondo 小 21%（441 行 vs. 559 行），且用户无需定义 200+ 行的归纳不变式。
- **验证速度**：Basilisk 显著快于 Kondo（Flexible Paxos 不到一半时间）。64 条 Host-Provenance Invariants 中仅 6 条需要用户提供 provenance witness 提示。

---

## 六、批判性分析

**优点**：
- 核心 insight 扎实：Provenance Invariant 的不可变性来自执行历史的单调性，因此每条单独成立，归纳性免费获得，这一设计非常优雅。
- 评测覆盖全面，16 个协议跨越难度层次，Multi-Paxos 是公认的验证难题。

**值得质疑之处**：

1. **实验的"零用户不变式"结论可能误导**：Table 1 中 Basilisk 的 "User invs" 全为 0，但这只是不计入 provenance witness hints。实际上 6 条 hints 对应恰恰是最复杂的协议（Paxos-Dynamic 2条、Raft 2条、Multi-Paxos 2条），这些 hints 的推导难度论文未能量化，可能仍需一定的专业直觉。

2. **与 Kondo 的对比公平性存疑**：Kondo 因"禁止 send+receive 合并步骤"限制，必须拆分步骤，导致协议代码更复杂、不变式更多。Basilisk 放宽了这一限制，因此两者的协议描述实际上是不同的，直接对比 "Lines of proof" 并不完全公平——部分优势源于建模方式改变，而非推理能力提升。

3. **完备性主张过于保守但又隐含乐观**：论文坦承 Basilisk 不保证完备，但同时声称"在所有真实世界例子中均未遇到失败案例"。16个协议样本量较小，且均是比较经典的协议，缺乏对工业级复杂协议（如 ZooKeeper、etcd Raft 完整实现）的验证，外推能力存疑。

4. **Footprint 过估计的影响被轻描淡写**：论文承认 footprint 过估计会弱化生成的不变式，但说"在我们的实验中未遇到此问题"，这一说法与 6 条 hint 的事实存在张力——这 6 条 hint 中有多少是因为 footprint 过估计导致的？缺乏系统分析。

5. **Safety-only 范围**：Basilisk 不支持 liveness 证明，而分布式协议的 liveness（如 Paxos 的终止性）常常比 safety 更难，实际工程价值因此受限。

6. **协议描述与实现之间的 gap**：论文依赖用户确保 Dafny 状态机描述忠实反映真实系统实现，但这一"信任假设"是整个验证链中最薄弱的一环，论文仅一句带过。

---

## 七、总结

Basilisk 提出了 Provenance Invariant 这一新型不变式类别，通过将主机状态变化追溯到具体协议步骤，将难以手工构造的 inter-host 全局属性分解为一组可自动推导的局部属性，从而在 undecidable 逻辑下（Dafny）实现了对 16 个分布式协议（含 Multi-Paxos）归纳不变式的几乎全自动生成，相比 Kondo 显著降低了用户推导不变式的负担，同时改善了验证速度。主要局限在于：不支持 liveness 证明，对隐式跨步骤变量关系的处理依赖用户提示，以及协议模型与真实实现之间的桥接仍需额外工作。
