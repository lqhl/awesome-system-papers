# Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols

## 论文基本信息

- **标题**: Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols
- **作者**: Tony Nuda Zhang, Keshav Singh (University of Michigan), Tej Chajed (University of Wisconsin-Madison), Manos Kapritsos (University of Michigan), Bryan Parno (Carnegie Mellon University)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/zhang-tony

## 研究背景与动机

分布式协议（如 Paxos、Multi-Paxos）是构建容错系统的基石，但其正确性证明极为困难。**归纳不变量（Inductive Invariant）** 是形式化验证的核心——必须同时满足：
1. 在初始状态下成立
2. 蕴含安全属性
3. 在所有状态转换下保持不变

现有方法的困境：
- **IronFleet**：要求开发者手工推导归纳不变量，据报道 Multi-Paxos 花费数月
- **Kondo**：尝试自动生成，但要求协议必须用 EPR（有效命题推理）表达——禁止常见编程模式（如 `i := i + 1`），且关键的**跨主机属性**（inter-host properties）仍需开发者手工提供

## 要解决的核心问题

如何在**不限制逻辑表达能力**（不要求 EPR）的前提下，自动推导出分布式协议的归纳不变量？

## 主要贡献

1. **Provenance Invariants**：一类新的不变量，通过追踪主机状态的历史来源（provenance）来建立主机间关系
2. **Atomic Sharding 算法**：自动从协议步骤中推导 Provenance Invariants
3. **Basilisk 工具**：实现上述方法，在 16 个分布式协议上自动找到归纳不变量
4. **无需 EPR**：支持开发者用自然方式编写协议，自动生成归纳不变量

## 研究方法与设计

### 不变量分类学（Invariant Taxonomy）

```
Regular Invariants
├── Provenance Invariants（本文引入）
│   ├── Network-Provenance Invariant
│   └── Host-Provenance Invariant
├── Monotonicity Invariants（Kondo 引入）
└── Ownership Invariants（Kondo 引入）
```

### Provenance Invariants 详解

#### Network-Provenance Invariant

将消息 $m$ 的存在（网络中）与发送该消息的步骤关联：

$$\forall m \in \text{network}: \exists i: T_i(\text{hist}[i], \text{hist}[i+1], m)$$

即：网络中的每条消息必然由发送者的历史中某一步骤产生。

#### Host-Provenance Invariant

将主机当前状态的一个属性 $q$（称为 provenance witness）与导致该属性为真的协议步骤关联：

$$q(h_{\text{cur}}) \land \forall h_0: \neg(\text{HostInit}(h_0) \land q(h_0)) \implies \exists i: \neg q(\text{hist}[i]) \land q(\text{hist}[i+1]) \land T(\text{hist}[i], \text{hist}[i+1])$$

即：如果 $q$ 在当前状态成立但在任何初始状态不成立，则必然存在某一步骤使得 $q$ 从假变真。

### Atomic Sharding 算法

**目标**：自动识别哪些变量总是被一起原子更新。

**核心思想**：若某组变量（称为 shard）总是被同一组步骤原子更新，则 shard 中任一变量的非初始值可以追踪到这些步骤之一。

**算法流程**：
1. **估计 Footprint**：静态分析每个步骤可能修改的变量集
2. **计算原子 Shard**：分析 footprint 交集，构建 Venn 图，最大 shard 即为原子 shard
3. **Refined Shard**：对集合类型变量（如 set、map），将每个集合放入独立 shard 以保持粒度

**关键属性**：每个原子 shard 对应一个 Host-Provenance Invariant。

### 从 Provenance Invariants 推导 Inter-Host Properties

这是 Basilisk 最精彩的部分。看似需要"跨主机直觉"的 Participant-Agreement 属性：

> "若某参与者决定 Commit，则协调者也必须决定 Commit"

可以通过组合两个 Provenance Invariants 推导：

1. **Participant-Decision-Provenance**（Host-Provenance）：
   > 若参与者决定 Commit，则必然执行了 `ParticipantReceiveDecision`

2. **Decide-Msg-Provenance**（Network-Provenance）：
   > 网络中的每条 DECIDE 消息必然由协调者的 `CoordinatorSendDecide` 步骤发送

3. 由 (1) 可知参与者收到了 DECIDE(Commit) 消息
4. 由 (2) 可知该消息由协调者发送
5. 由协调者步骤语义可知协调者不 equivocate → 协调者也决定 Commit

### Basilisk 工作流

```
开发者编写协议（Host定义、Step定义）
         ↓
Basilisk 生成 History-Preserving 异步协议 Ph
         ↓
Basilisk 自动推导 Provenance Invariants（Atomic Sharding）
         ↓
Basilisk 生成归纳不变量 I + 归纳性证明
         ↓
开发者用 I 证明安全性（Proof Obligations Ob1, Ob2）
```

## 关键实现细节

- 修改了 Kondo 代码库（Dafny verifier 4.2），增加约 **2,000 行 C# 代码**
- 支持 Dafny 编写的异步消息传递协议
- 支持接收和发送消息的联合步骤（与 Kondo 不同，Kondo 禁止此模式）

## 实验结果与分析

### 自动生成归纳不变量

Basilisk 在所有 16 个协议上成功自动找到归纳不变量，而 Kondo 在大多数协议上需要开发者手工提供不变量。

### 用户体验改善

| 协议 | Kondo 手工不变量数 | Basilisk 手工不变量数 |
|------|-----------------|-------------------|
| Paxos | 20 | 5 |
| Multi-Paxos | —（未实现） | 4 |
| Flexible Paxos | 20 | 5 |
| Two-Phase Commit | 4 | 3 |

### 验证延迟

所有协议的 Dafny 验证时间均在 2 秒以内，不影响开发体验。

## 潜在问题与局限性

1. **Conditional Updates 限制**：Atomic Sharding 当前拒绝含条件更新的步骤（如"若 c 则 x:=5 否则 y:=6"），要求拆分为两步，开发者需手工完成
2. **Protocol Bug 不在范围内**：若协议本身有 bug，Basilisk 无法发现，仍需开发者调试
3. **仅支持异步消息传递**：不支持同步 RPC 等其他通信模型
4. **共享内存协议缺失**：未在共享内存并发协议上验证
5. **Dafny 依赖**：工具链绑定于 Dafny，增加了使用门槛
6. **Hint 的必要性**：某些情况下 Provenance Invariants 不够强，仍需开发者提供 hints（但相比 Kondo 少得多）

## 未来工作方向

- 支持条件更新
- 扩展到其他通信模型（同步 RPC、共享内存）
- 集成到其他验证框架

## 个人评注

1. **核心技术贡献深刻**：Atomic Sharding 算法是一个简洁优雅的自动推导方法，将"变量是否原子更新"的语义分析转化为自动生成 Provenance Invariants 的机制。核心洞察——通过 Provenance Invariants 的组合替代显式跨主机属性——极具原创性。

2. **缓解了形式化验证的最大痛点**：Multi-Paxos 被广泛认为是形式化验证的硬骨头，Basilisk 将开发者从数月的"猜测-证明-修正"循环中解放出来。

3. **与 Kondo 的对比略显不公平**：Kondo 的设计目标是"不要求不变量分类"，而 Basilisk 扩展了分类学使更多不变量可自动生成。两者是互补关系而非竞争关系，但论文叙述方式让 Basilisk 看起来是 Kondo 的直接超越。

4. **表 1 细节值得细读**："Mono annots"列在 Basilisk 和 Kondo 之间完全相同，说明 Monotonicity Invariants 完全是继承关系，不是 Basilisk 的贡献。但论文清晰地标注了这一点，诚实。

5. **Multi-Paxos 实验的缺失**：Kondo 未实现 Multi-Paxos，Basilisk 单独实现了一个，这是增量贡献，不算直接对比。论文对此说明清晰。

6. **整体评价**：这是一篇扎实的形式化验证工作，在保证理论严谨性的同时有清晰的实用价值。实验设计覆盖了足够多样的协议，但仅在 Dafny 上验证，缺少在 Coq、Isabelle 等其他证明助手中的迁移验证。
