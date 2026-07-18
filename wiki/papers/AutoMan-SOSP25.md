---
type: paper
name: AutoMan
full_title: "AutoMan: Facilitating Verified Distributed Systems Development Through Automatic Code Generation and Manual Optimizations"
authors: [Zihao Zhang, Ti Zhou, Christa Jenkins, Omar Chowdhury, Shuai Mu]
venue: SOSP
year: 2025
tags: [distributed-systems, formal-verification, code-generation, dafny, refinement]
source_pdf: "[[3731569.3764822.pdf]]"
source_md: "[[3731569.3764822]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# AutoMan: Facilitating Verified Distributed Systems Development Through Automatic Code Generation and Manual Optimizations (SOSP 2025)

> **一句话总结**：AutoMan 从 Dafny TLA specification 生成实现与 proof obligations，并允许手工 hot-path optimization 以 refinement 接入；Multi-Paxos 中相对 IronRSL 的 manual effort 降 70–97%，四服务器实验中 optimized I1 peak throughput 达 IronRSL 的 97%；KV 的 unoptimized I0 在所测 workload 上超过 IronKV 的 90%（§6.1–6.2，Table 3，Fig. 8/11）。

## 问题与动机

分布式系统正确性难保证：[[IronFleet]]/[[Verdi]] 等 formal verification 强但 expert effort 高；[[PGo]] 等从规格编译实现省力但性能差且 codegen 不可信。能否 **lower effort 且保持 end-to-end correctness + reasonable performance**？

AutoMan workflow：**先 correctness（自动生成）→ 再 selective manual optimization（仍用 refinement 证明）**，利用 SMR 等系统中 control plane 占 76–90% LOC 但 performance-insensitive 的结构性观察。

## 关键观察 / 隐含假设

- **观察 1**：TLA state machine 的 action predicate 可一一映射到实现函数 + refinement proof obligation，适合 action-level 自动化。
  - **依赖假设**：规格落在 AutoMan 可翻译的 Dafny TLA fragment 内；用户供给 I/O mode 注解。
  - **可能失效场景**：高度 nondeterministic 或复杂 relational action 可能通不过 flow-sensitive checker。
- **观察 2**：分布式系统性能常由少数 data plane 组件主导（如 replication），control plane 可全自动生成。
  - **依赖假设**：profile 能识别 hot path；手动优化仍可用 Abstractify/refinement 接入。
  - **可能失效场景**：无清晰 hot/cold 划分的系统仍需大量手写。
- **观察 3**：refinement methodology 允许 auto-generated 与 hand-optimized 代码共存于同一证明树。
  - **依赖假设**：Dafny SMT 能 discharge 大部分 obligation；失败时需人工 hint。
  - **可能强度**：强。这是方法论核心，case study 支撑。

## 核心方法

Pipeline：Parser → Annotator → Mode Validator → Checker → Code Generator → refinement scaffolding。

- 输入：Dafny TLA spec + predicate mode annotations（`+` input / `−` output）。
- 静态 flow-sensitive analysis 判定 action 是否 functionalizable。
- 生成 functional-style 实现 + Abstractify 脚手架；手动优化代码写 refinement proof 挂接。
- 支持 TLA+ → Dafny TLA 转换工具；与 network framework 集成成 runnable system。

Case studies：Multi-Paxos、PBFT、sharded KV、CausalMesh。

## 设计取舍

- **Decidable fragment vs full TLA expressiveness**：可自动化，但规格需改写。
- **Trust codegen vs trust proofs**：生成代码仍经 Dafny 验证，比 PGo 强；但 network/runtime 框架可能未验证。
- **Manual optimization freedom vs proof burden**：hot path 优化仍要写 refinement，可能抵消部分 effort 节省。

## 实验与结果

- **Multi-Paxos effort**：AutoManRSL-I0 相对 IronRSL 降 97%，I1 降 70%；I0 为 2,119 generated LoC 加约 200 manual LoC/4 hours，I1 再加约 2,200 manual LoC/1 week，IronRSL 约 8,100 manual LoC（§6.1，Table 3；single-developer accounting，不含 framework/main-loop/marshalling）。
- **Multi-Paxos throughput**：四服务器 local cluster、1–256 serial-request threads 下，I1 peak throughput 为 I0 的 2.7×、达 IronRSL 的 97%；I0 为 36% 且高并发接近 0（§6.2，Fig. 8a；3 replicas + client，各 64 CPU/96GB）。
- **Sharded KV**：I0 在所测 get/set workloads 上超过 IronKV 的 90%，I1 在 I0 增加 8% 后匹配 IronKV（§6.2，Fig. 11；100,000 64-bit-key dataset，varying values/threads）。
- **Other cases**：PBFT I1 为 I0 的 2.04×；CausalMesh I1 为 I0 的 1.92×，但 unverified Rust implementation 超过 4.7×，因此不能归纳为 universal manual-baseline match（§6.2，Fig. 8b/12；CausalMesh CloudLab 5 servers、50/50 read/write）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Multi-Paxos generation 减少 70–97% manual effort | §6.1, Table 3 | single-developer accounting；只含 core logic/proofs | medium |
| Multi-Paxos I1 达到 IronRSL 97% peak throughput | §6.2, Fig. 8a | local 4-server cluster；1–256 serial-request threads | strong |
| Sharded KV I0/I1 达到或匹配 IronKV | §6.2, Fig. 11 | 100k-key dataset；get/set；varying values/threads | strong |
| PBFT/CausalMesh 优化有收益但不证明普适 baseline match | §6.2, Fig. 8b/12 | specific local/CloudLab configurations | strong |

## Critical Analysis

### 论证链条

「Action-level codegen + refinement = 低 effort + 可信 + 可优化」在四案例上闭合；从四案例外推到「多数 OSDI/SOSP 分布式系统」仍跳步——fragment 边界需逐案验证。

### 假设压力测试

- 论文介绍 TLA 可表达 safety/liveness，但未按性质类别报告 case-study proof 覆盖或人工证明量，因此不能由本文量化 liveness 自动化程度。
- Dafny/Z3 失败时 expert 仍需介入；未量化 hint 行数占比。
- 性能对比聚焦 throughput，tail latency/fault injection 覆盖有限。

### 实验可信度

- IronFleet 是强 baseline；effort 度量需读者信任作者 accounting methodology。
- 缺少独立团队 blind replication study。

### 系统性缺陷

- §7 明示 main event loop 与 marshalling/unmarshalling 等 glue code 仍由开发者实现；Table 3 的 effort 统计也排除 framework code。因此文中的 end-to-end 应按 refinement proof 覆盖的 core logic 解读，glue code 的验证边界需另行确认。
- 论文未讨论规格与实现 drift 的 CI 成本。

## 局限与 Future Work

- **局限**：可翻译 fragment 有限；liveness/复杂 fault model 仍重；runtime 未全验证。
- **Future work**：扩大 fragment；自动生成 mode annotations；与 Rust/Go 生产栈集成。

## 相关

- **相关概念**：[[IronFleet]]、[[Verdi]]、TLA+、Dafny、Refinement
- **同类系统**：[[IronFleet]]、PGo、Verdi
- **同会议**：[[SOSP-2025]]
