---
type: paper
name: PoWER
full_title: "PoWER Never Corrupts: Tool-Agnostic Verification of Crash Consistency and Corruption Detection"
authors: [Hayley LeBlanc, Jacob R. Lorch, Chris Hawblitzel, Cheng Huang, Yiheng Tao, et al.]
venue: OSDI
year: 2025
tags: [formal-verification, storage, crash-consistency, persistent-memory, key-value-store]
source_pdf: "[[osdi25-leblanc.pdf]]"
source_md: "[[osdi25-leblanc]]"
---

# PoWER Never Corrupts: Tool-Agnostic Verification of Crash Consistency and Corruption Detection (OSDI 2025)

> **一句话总结**：PoWER 把 crash consistency 编码为「写操作的 precondition」,只用标准 Hoare logic + ghost 变量 + 量词,不依赖 Crash Hoare Logic / Perennial 这类专用框架;基于此在 Verus 和 Dafny 上分别做出了验证过的 PM KV 存储 CAPYBARAKV 与公证服务 CAPYBARANS,两者 <1min 完成验证,性能与未验证系统持平或更快。

## 问题

验证存储系统的 crash consistency 和 corruption detection 一直很难落地,原因有三:(1) Hoare logic 用 pre/post condition 刻画函数语义,但 crash 可能发生在函数执行中间——既有方案如 FSCQ 的 Crash Hoare Logic、VeriBetrKV 的 TLA-style state machine refinement、Perennial 的 crash invariant 都要求专用验证器或重型扩展,学习曲线陡;(2) VeriBetrKV 的 corruption detection 假设 checksum 与 data 必须原子写入、且同址存储,这在字节级寻址的持久内存(PM)上根本不成立;(3) 历史上已验证的存储系统性能都比不上未验证对手,主流不用。

## 核心方法

核心思想——**把 crash consistency 编码成写操作 API 的 precondition**:调用 `write()` 时必须提供一段证明,证明「此次写产生的任何 crash 状态都是合法的」。这样反而只需标准 Hoare logic + 量词(主流验证器 Verus、Dafny、Prusti、Creusot 都支持),不需要 CHL、Perennial atomic invariants 那样的专用构造。

为了让证明不过于繁重,作者把存储开发者的常识整理成一套 **proof strategy 库**:例如「只写到逻辑上不可达的字节一定不会破坏一致性」,这类策略只需要关心写的位置、不关心写的内容或具体 crash state。作者还证明了 PoWER 的保证等价于 CHL 的 crash condition 和 Perennial 的 crash invariant。

对 corruption detection,作者基于 CRC 的理论性质给出新模型,**不限制 data 与 checksum 的位置、不要求原子共写**。为在 PM 8-byte 原子写的苛刻约束下仍能做 crash-atomic 的 CRC 更新,提出 **corruption-detecting Boolean (CDB)** 原语——一个受 CRC 保护的单 bit flag,用 flip 来切换两份候选 data+CRC 之间的「当前有效副本」。

两个案例:CAPYBARAKV 用 Verus 实现(支持 reader-writer 锁和 sharding 两种并发扩展),CAPYBARANS 用 Dafny 实现——证明 PoWER 与具体验证器无关。

## 关键结果

- 两套系统均在**不到一分钟内**完成整体验证。
- CAPYBARAKV 在多数 benchmark 上性能优于业界未验证的 PM KV store,设计目标是落地到 Azure Storage 的 battery-backed DRAM 系统,已与 Rust 原型整合。
- 证明 PoWER 的 soundness 与 Crash Hoare Logic 和 Perennial 的 crash invariant 等价。
- CDB 原语让 PM 上 CRC 更新的 crash-atomic 证明得以被标准 Hoare logic 处理,大幅简化 proof。

## 相关

- **相关概念**:crash consistency、persistent memory、CRC、Hoare logic、Verus、Dafny
- **同类工作**:FSCQ(Crash Hoare Logic on Rocq)、VeriBetrKV(Dafny + TLA-style refinement)、GoJournal / Perennial(crash invariants)、Yggdrasil(push-button 验证)
- **同会议**:[[OSDI-2025]]
