---
type: concept
aliases: [BPF, extended BPF, Berkeley Packet Filter]
last_updated: 2026-07-30
tags: [kernel, programmability, observability, security]
---

# eBPF

> extended Berkeley Packet Filter（eBPF）是在 verifier 约束下把程序动态加载到内核 hook 的可编程执行环境，用于 networking、observability、security 与 scheduling。

## 核心思想

eBPF 通过 verifier、JIT、map、helper/kfunc 与 attach point 在无需内核模块的情况下扩展 fast path。安全来自受限控制流和资源证明，但系统语义仍取决于 hook 的执行上下文、共享 state、抢占与租户归属。

## 为什么重要

程序变复杂后，“eBPF 总是短小”的旧假设失效。[[PeeR-OSDI26]] 在 verifier 保留的安全点做 cooperative preemption；[[vBPF-OSDI26]] 指出 static binding 默认单一信任域，以 late binding 隔离多租户程序；[[TypeCraft-OSDI26]] 与 [[Xkernel-OSDI26]] 则把类型/执行边界推向更复杂的 kernel extensibility。

## 关键观察 / 隐含假设

- **观察：verifier state 不只是安全证明，也可成为 runtime continuation metadata。** [[PeeR-OSDI26]] 在 helper boundary yield/resume。
- **观察：program-safe 不代表 tenant-safe。** [[vBPF-OSDI26]] 显示共享 hook/context 会产生性能干扰和 state corruption。
- **假设：hook attribution 准确且开销有界。** interrupt/softirq 与跨租户 object 会挑战 [[vBPF-OSDI26]] 的归属模型。

## 设计空间与取舍

- **Static / late binding**：静态附着简单，late binding 提供多租户隔离但需 runtime dispatch。
- **Run-to-completion / preemption**：前者快路径简单，后者保护 tail latency却需保存安全状态。
- **Restricted ISA / richer extension**：表达能力越强，verifier、调度与攻击面越复杂。

## 引用本概念的论文

- [[vBPF-OSDI26]] — late-binding 多租户虚拟化。
- [[PeeR-OSDI26]] — verifier-assisted cooperative preemption。
- [[Rakaia-OSDI26]] — 内核可编程路径的安全控制。
- [[TypeCraft-OSDI26]] — 类型驱动的安全 kernel extension。
- [[Aeolia-SOSP25]] — eBPF 驱动的 I/O 路径控制。

## 已知局限 / 开放问题

- 需要同时验证 program safety、tenant isolation 与 scheduler fairness。
- JIT、helper side effect 和跨 hook state 的组合行为仍难以形式化。
