---
type: paper
name: Mohabi
full_title: "Mohabi: Disaggregating and Sandboxing the Firefox JavaScript Engine"
authors: [Abhishek Sharma, Anand Balaji, Zachary Yedidia, Anthony Du, Taehyun Noh, et al.]
venue: OSDI
year: 2026
tags: [browser-security, javascript-engine, sandboxing, software-fault-isolation, firefox]
source_pdf: "[[osdi26-sharma.pdf]]"
source_md: "[[osdi26-sharma]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Firefox JavaScript 引擎的解耦与沙箱化（OSDI 2026）

> **原题**：Mohabi: Disaggregating and Sandboxing the Firefox JavaScript Engine

> **一句话总结**：Mohabi把高度耦合的SpiderMonkey从Firefox其余部分划出边界，用类型系统与代码生成构造safe interface，再以支持大地址空间的x86-64 SFI隔离JIT/runtime code；JetStream/Speedometer overhead为24.82%/24.43%。

## 问题与动机

JavaScript engine含interpreter、多级JIT、runtime-generated code，是browser memory-safety漏洞中心。禁用JIT损失3.5×–7×且仍挡不住interpreter漏洞；process isolation又因大量跨engine/browser object与调用过重。Mohabi探索retrofit in-process sandbox，同时保留JIT。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

作者系统性disaggregate SpiderMonkey的data structures/control flow，用类型标注区分sandbox pointer/host pointer，并自动生成跨边界marshalling/trampoline，减少数万函数人工改写。SFI toolchain对sandbox memory/code access插入检查，控制indirect branch和system interaction，并优化large memory footprint/address masking以适合JS heap/JIT。

假设SFI validator、boundary code和host APIs可信；sandbox阻止engine memory bug逃逸，但不阻止通过合法接口的logic/confidentiality abuse。

## 实验与结果

- 完整现代Firefox运行常见web/JIT功能，JetStream overhead 24.82%、Speedometer 24.43%。
- 通用x86-64 SFI toolchain在SPEC 2017 overhead 5.9%–6.6%，说明余下browser成本来自engine boundary/特殊workload。
- security分析覆盖JIT-generated code、memory access与control-flow escape，并把engine compromise限制在sandbox。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

这是工程规模很强的case study，证明类型+codegen能让legacy C++组件解耦可控；但约25% browser benchmark成本不低，且TCB仍含复杂boundary和SFI runtime。侧信道、Spectre、semantic confused-deputy及engine借合法Firefox API攻击不由memory isolation自动解决。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 针对真实SpiderMonkey CVE做exploit containment回放。
- 降低DOM/[[Garbage-Collection|GC]]/JIT boundary crossing，并评估memory/energy/mobile成本。
- 扩展到V8/JavaScriptCore验证方法通用性。

## 相关

- **相关概念**：[[Software-Fault-Isolation]]、[[In-Process-Sandboxing]]、[[JIT-Compilation]]、[[Memory-Safety]]
- **相关系统**：[[Firefox]]、[[SpiderMonkey]]
- **同会议**：[[OSDI-2026]]
