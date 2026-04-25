---
type: paper
name: AutoMan
full_title: "AutoMan: Facilitating Verified Distributed Systems Development Through Automatic Code Generation and Manual Optimizations"
authors: [Zihao Zhang, Ti Zhou, Christa Jenkins, Omar Chowdhury, Shuai Mu]
venue: SOSP
year: 2025
tags: [formal-verification, distributed-systems, code-generation, refinement, dafny]
source_pdf: "[[3731569.3764822.pdf]]"
source_md: "[[3731569.3764822]]"
---

# AutoMan: Facilitating Verified Distributed Systems Development Through Automatic Code Generation and Manual Optimizations (SOSP 2025)

> **一句话总结**:一套基于 refinement 的分布式系统开发工作流,把 TLA 风格 Dafny 规约自动翻译成可证明实现 + 验证义务,再允许手动优化性能关键组件并验证其 refinement,在 Multi-Paxos、PBFT、Sharded KV、CausalMesh 上把人工量减少 70%-97%,吞吐达到 IronFleet 的 90% 以上。

## 问题

开发正确且高性能的分布式系统极其困难。两条主流路线各有缺陷:(i) 形式化验证(如 [[IronFleet]]、Verdi)能给出机器检查的正确性保证,但需要巨大专家工作量;(ii) 从规约自动编译到实现(如 PGo),能省力但没有端到端正确性保证,且性能差。能否把二者优点结合起来?

## 核心方法

AutoMan 采用一个四层 refinement 工作流:$S_0 \leftarrow S_1 \leftarrow I_0 \leftarrow I_1$。输入是 Dafny 表达的 TLA 风格状态机规约 $S_1$,系统做三件事:

1. **Translator**:把 Dafny TLA spec 的 action 谓词翻译成 functional-style 实现代码 $I_0$,同时生成 refinement proof 义务。Translator 分为 Parser → Annotator → Mode Validator → Checker → Code Generator 五个模块,通过用户提供的 input/output mode 注解(`+`/`-`,源自逻辑编程传统)和静态 flow-sensitive 分析,识别 functionalizable 谓词并处理 implicit I/O、relational constraints、nondeterminism 三大挑战。
2. **Manual optimization**:开发者可用命令式 Dafny 代码手写性能关键部分 $I_1$,并通过 Abstractify 函数把手工证明接入生成的 refinement 脚手架。
3. **Refinement scaffolding**:保证 auto-generated 和 hand-tuned 代码能和谐共存,端到端正确性和纯手工验证(如 IronFleet)一致。

关键洞察:分布式系统(尤其是 [[Raft]]/[[Paxos]] 类 SMR)性能常由数据复制平面主导(仅占 10%-24% 代码),控制平面(leader 选举、恢复)虽然复杂但不影响稳态性能,所以只优化少数组件即可。

## 关键结果

- 在 Multi-Paxos 重写中,人工代码量减少 70%-97%
- 四个案例研究:Multi-Paxos、PBFT、Sharded KV、CausalMesh
- 生成系统吞吐达到 IronFleet 等纯手工实现的 90%+
- Translator 基于 Dafny,原生兼容 TLA+(提供 TLA+ → Dafny TLA 转换工具)

## 相关

- **相关概念**:[[Formal-Verification]]、[[State-Machine-Replication]]、[[Paxos]]、[[Raft]]
- **同类系统**:[[IronFleet]]、Verdi、PGo
- **同会议**:[[SOSP-2025]]
