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
---

# Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols (OSDI 2025)

> **一句话总结**：分布式协议安全证明需归纳不变量，EPR 等可判定片段太受限，手工找不变量（IronFleet Multi-Paxos 数月）太贵；Basilisk 用 Provenance Invariants（变量值追溯到产生它的协议步）+ atomic sharding 静态推导，在不可判定逻辑上自动合成归纳不变量，**16** 个协议含 Multi-Paxos 几乎无需人工提示。

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

- **16/16** 协议：Basilisk 自动生成归纳不变量并证明 inductiveness（少量 hint）。
- Multi-Paxos：相对 IronFleet 手工数月，自动化显著降人力（定性）。
- Kondo Paxos 20 条手工 inter-host 性质由 provenance 替代。

## Critical Analysis

### 论证链条

「复杂 inter-host → 消息 provenance 链」洞察清晰 → sharding 扩覆盖 → 多协议 case study，对 verification 社区说服力强。Safety 证明仍可能需要人工，但比全手工 invariant 轻。

### 假设压力测试

含 subtle 算术的协议（成员计数、版本号比较）是否总需 hint？与 TLA+/Ivy 等生态互操作成本？规模化到工业级协议（Thousands lines）性能未强调。

### 实验可信度

16 协议含经典与复杂案例；与 Kondo 对比公平。缺乏与最新 ML 引导 invariant 工具对照。

### 系统性缺陷

论文未讨论错误 hint 的调试体验；provenance 爆炸导致子句过多时的证明时间。

## 局限与 Future Work

- **局限 1**：不可判定性下无完备算法，失败案例存在。
- **Future work 1**：与 liveness 证明结合。
- **Future work 2**：从实现代码自动提取协议模型的工具链。

## 相关

- **同会议**：[[OSDI-2025]]