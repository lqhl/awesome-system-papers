---
type: paper
name: iLand
full_title: "iLand: An Instruction-Level Dynamic Binary Instrumentation framework for iOS"
authors: [Kaitao Xie, Yizhuo Wang, Xiaolong Bai]
venue: OSDI
year: 2026
tags: [ios, dynamic-binary-instrumentation, emulation, mobile-security, program-analysis]
source_pdf: "[[osdi26-xie-kaitao.pdf]]"
source_md: "[[osdi26-xie-kaitao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# iOS 指令级动态二进制插桩（OSDI 2026）

> **原题**：iLand: An Instruction-Level Dynamic Binary Instrumentation framework for iOS

> **一句话总结**：iLand绕开iOS禁止JIT/RWX的限制，把guest instructions翻译为预定义micro-ops并由预编译atomic units解释，只模拟app code、system libraries原生执行；对60个热门App发现13个仍调用private API、15个以SVC直接收集敏感信息。

## 问题与动机

non-jailbroken iOS强制code signing、禁止动态code generation，传统Valgrind/DynamoRIO式DBI不可用。repackaging改变binary且多为API-level；完整模拟Dyld Shared Cache又会因app+host两份约3.3GB触发Jetsam。

## 关键观察 / 隐含假设

- **观察 1**：性能或安全瓶颈并非只由资源容量决定，还取决于数据布局、执行粒度或信任边界。
- **观察 2**：论文提出的细粒度控制机制可以隔离主要开销，同时保留保守回退以维持正确性。

## 核心方法

iLand把ARM instruction decode成有限micro-operations，由提前签名/编译进app的atomic execution units解释，因此运行时不生成unsigned code。application-only emulation只解释guest app pages，system library call切换到native host library；维护guest register/memory与ABI bridge，并支持UI、interaction、video等真实行为。

假设guest和host system library版本/ABI一致；system-library内部instruction不可见，故不是完整whole-process tracing。

## 实验与结果

- 标准sandbox/non-jailbroken device运行，保留dynamic UI、实时交互和video streaming。
- instruction tracing分析60 top-ranked App Store apps：13个（21%）调用private APIs，其中2个明确禁止；15个（25%）直接SVC收集敏感信息。
- CPU/memory优化证明application-only approach比full emulation实际可部署。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

以precompiled micro-op解释器规避code-signing限制很巧妙，但性能天然低于JIT DBI；native library blind spot会漏掉跨boundary行为。将其他app放入iLand执行涉及decryption/signing/entitlement与App Store政策，研究prototype可行不等于普通用户部署。

### 假设压力测试

核心假设一旦不成立，收益会下降或触发保守回退；部署前应覆盖负载漂移、资源争用和极端输入。

### 实验可信度

实验支持主要机制，但硬件、模型与工作负载范围限定了结论的外推能力。

## 局限与后续工作

- 量化各instruction class slowdown、energy和memory tail。
- 扩大system-library observability而不复制DSC。
- 对不同iOS versions/anti-emulation与App完整兼容性评测。

## 相关

- **相关概念**：[[Dynamic-Binary-Instrumentation]]、[[Binary-Translation]]、[[iOS-Sandbox]]、[[Code-Signing]]
- **同会议**：[[OSDI-2026]]
