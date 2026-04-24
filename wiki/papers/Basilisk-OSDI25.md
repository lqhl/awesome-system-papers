---
type: paper
name: Basilisk
full_title: "Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols"
authors: [Tony Nuda Zhang, Keshav Singh, Tej Chajed, Manos Kapritsos, Bryan Parno]
venue: OSDI
year: 2025
tags: [formal-verification, distributed-protocols, inductive-invariants, dafny]
source_pdf: "[[osdi25-zhang-tony.pdf]]"
source_md: "[[osdi25-zhang-tony]]"
---

# Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols (OSDI 2025)

> **一句话总结**：Basilisk 用「Provenance Invariants + 原子分片」自动推导 16 个分布式协议（含 Multi-Paxos、Flexible Paxos）的 inductive invariant，用户几乎无需手写协议间的跨主机不变式。

## 问题

形式化验证分布式协议需要找到 inductive invariant——同时蕴含安全属性、在初始状态成立、对所有状态转移封闭。在不限定逻辑的情形下（undecidable logic），这件事极其耗时：IronFleet 团队为 Multi-Paxos 花了数月；Kondo [OSDI 24] 的 Paxos 证明仍需用户手写 ~20 条跨主机属性，专家约两周。限定到 EPR 等可判定片段虽能自动化，但牺牲了算术等自然编程能力，几乎不可用。

核心难点是 **inter-host property**：跨主机、跨协议步骤的关系（如「若某 participant decide Commit，则 coordinator 的决定也是 Commit」）需要深度洞察协议 why it works，很难机械化推导。

## 核心方法

**Provenance Invariants**：一类「把当前状态追溯到历史步骤」的不变式。基于 history-preserving 模型（每个 host 的状态附加一条只读 append-only 历史），Basilisk 区分两种：(a) Network-Provenance Invariant——网络中每条消息 m 都必然由某个 send step 产生，可追溯到 sender 的两个相邻历史状态；(b) Host-Provenance Invariant——某本地属性 q 成立意味着 host 历史中存在使 q 为真的那一步。因为历史不可变，单条 Provenance Invariant 本身天然 inductive。

**跨主机关系的自动化**：以前需要人工拼出的 inter-host 属性，现在通过「Network-Provenance 把消息连到 sender 步骤」+「Host-Provenance 把 receiver 状态连到 receive 步骤」的因果链自动蕴含。Paxos 中 20 条手写 Protocol Invariant 被完全替换。

**Atomic Sharding 算法**：自动发现 Host-Provenance。把 host 的状态变量划成「atomic shard」——一组总是被同一步原子更新的变量；对每个 shard 只需枚举修改它的步骤集合 A\_σ，就能机械生成「shard 非初始态 ⇒ 必然执行过 A\_σ 中某步」这条不变式。工具实现在 Kondo 的 Dafny fork 上，保留 Monotonicity / Ownership Invariant 的既有自动化。

## 关键结果

- 16 个协议全部自动验证，包括 Multi-Paxos、Paxos、Flexible Paxos、Paxos-Dynamic、Raft Leader Election、Three-Phase Commit 等 Kondo 不支持或不完整支持的。
- 用户手写 invariant clauses：**0**（Kondo 在 Paxos 需 20 条）；Provenance hints：16 个协议共 6 处。
- 证明代码量：Flexible Paxos 的 safety lemma 441 行 vs Kondo 的 559 行（-21%），且省掉 200+ 行用户 invariant 定义。
- Dafny 验证时间：Multi-Paxos 约 1 分钟；Flexible Paxos 22.8s vs Kondo 49.4s。

## 相关

- **相关概念**：inductive invariant、[[Provenance-Invariant]]、[[Atomic-Sharding]]、history-preservation、EPR
- **同类系统**：IronFleet、[[Kondo]]、DistAI、DuoAI、Ivy
- **同会议**：[[OSDI-2025]]
