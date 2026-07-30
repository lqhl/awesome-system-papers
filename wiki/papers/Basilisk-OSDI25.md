---
type: paper
name: Basilisk
full_title: "Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols"
authors: [Tony Nuda Zhang, Keshav Singh, Tej Chajed, Manos Kapritsos, Bryan Parno]
venue: OSDI
year: 2025
tags: [formal-verification, distributed-systems, invariant-inference, paxos]
source_pdf: "[[osdi25-zhang-tony.pdf]]"
source_md: "[[osdi25-zhang-tony]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Basilisk：使用来源不变量来自动化不可判定协议的证明（OSDI 2025）

> **原题**：Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols

> **一句话总结**：Basilisk 用 Provenance Invariants（变量值追溯到产生它的协议步）和 atomic sharding 静态推导，在不可判定逻辑上自动合成归纳不变量；在作者的 16 个协议语料中，均能得到安全证明所需的不变量。

## 问题与动机

形式化验证需 inductive invariant I：初态成立、保持、蕴含 safety。自动推理多限制在 EPR（无算术等）。放开逻辑则开发者迭代「猜不变量→证明失败→加强」循环，Kondo 仍把跨 host 复杂性质留给人工（Paxos 需 20 条，专家两周）。

## 关键观察 / 隐含假设

- **观察 1**：许多跨 host 性质可拆成 Provenance Invariants——本地变量值由某 send/receive/local 步产生，沿消息链追溯到对方状态。
  - **依赖假设**：协议步足够结构化以静态匹配 provenance。
  - **可能失效场景**：高度算术或加密性质可能无法仅用 provenance 表达。
- **观察 2**：若状态 shard 总是被某类步原子更新，可自动推断「该 shard 非初态则某步已发生」类不变量。
  - **证据强度**：强——atomic sharding 算法 §4 与 2PC 示例。
- **假设 1**：剩余 Monotonicity/Ownership（Kondo 子类）+ Provenance 足以构成完整 I，无需新手工 inter-host 引理。
  - **可能失效场景**：协议若需全局计数/算术归纳，可能仍需 hint（论文称 occasional minor hints）。

## 核心方法

**Provenance Invariants**：send/receive/local 三类步上推导变量来源关系。

**Atomic sharding**：静态划分原子更新 shard，生成 provenance 子句。

**Basilisk 工具**：合成 I 并证明 inductiveness；开发者仅用 I 证 safety（较易）。

评估含 **Multi-Paxos**、2PC 等 **16** 协议。

## 设计取舍

- **取舍 1**：不保证所有不可判定协议可自动化，换实用覆盖。
- **取舍 2**：需协议以验证友好形式编写，非任意 C 实现。
- **边界条件**：与 Kondo  taxonomy 兼容，扩展 Provenance 类。

## 实验与结果

- 作者的 16 个 Dafny/IronFleet 风格状态机协议均自动得到归纳不变量与 safety proof，未需要新增用户定义的不变量；边界是语料均不含 EPR 外的复杂算术（§6.1，Table 1）。
- 对 Kondo 的 Paxos 描述，Basilisk 的用户不变量子句数为 0、Kondo 为 20；为满足 Kondo 的限制，作者修改了其协议描述（§6.1–6.2，Table 1）。
- Flexible Paxos 的安全引理为 441 LOC，Kondo 版本为 559 LOC（作者报告少 21%）；比较的是最终证明工件，未计入开发迭代成本（§6.2，Table 1）。
- Flexible Paxos 的最终异步 proof 耗时 22.8 s，Kondo 为 49.4 s；该数值是作者的 artifact 环境测量，非生产实现性能（§6.3，Table 1）。
- 在该 proof-checking benchmark 中，相比 Kondo，Flexible Paxos 的验证耗时为 22.8 s 对 49.4 s；边界是 artifact 环境而非协议运行性能（§6.3，Table 1）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Basilisk 在 16 协议语料中自动补齐证明所需不变量 | 16/16 protocol 均有 inductive invariant 与 safety proof，且未新增用户定义的不变量（§6.1，Table 1） | Dafny/IronFleet 风格状态机；EPR 外复杂算术不在语料中 | high |
| Basilisk 可替代 Kondo Paxos 中大量跨主机手工不变量 | 用户不变量子句为 0，对 Kondo 为 20（§6.1–6.2，Table 1） | Kondo 描述被修改以满足其语言限制 | medium |
| Flexible Paxos 的最终安全引理更短 | 441 LOC，对 Kondo 为 559 LOC，作者报告少 21%（§6.2，Table 1） | 不包含开发过程与维护成本 | medium |
| Basilisk 更快完成 Flexible Paxos 的最终异步证明 | 22.8 s，对 Kondo 为 49.4 s（§6.3，Table 1） | artifact proof-checking benchmark，不代表协议运行性能 | medium |
| provenance hint 的人工负担在一个子集上较小 | 64 个不变量中 6 个需要 provenance-witness hint（§6.2） | 仅适用于 Host-Provenance 子集 | medium |

## 批判性分析

### 论证链条

「复杂 inter-host → 消息 provenance 链」洞察清晰 → sharding 扩覆盖 → 多协议 case study，对 verification 社区说服力强。Safety 证明仍可能需要人工，但比全手工 invariant 轻。

### 假设压力测试

含 subtle 算术的协议（成员计数、版本号比较）是否总需 hint？与 TLA+/Ivy 等生态互操作成本？论文未评估大型工业协议模型上的性能。

### 实验可信度

16 协议含经典与复杂案例；与 Kondo 对比公平。缺乏与最新 ML 引导 invariant 工具对照。

### 系统性缺陷

论文未讨论错误 hint 的调试体验；provenance 爆炸导致子句过多时的证明时间。

## 局限与后续工作

- **局限 1**：不可判定性下无完备算法，失败案例存在。
- **Future work 1**：与 liveness 证明结合。
- **Future work 2**：从实现代码自动提取协议模型的工具链。

## 相关

- **同会议**：[[OSDI-2025]]
