---
type: paper
name: Converos
full_title: "CONVEROS: Practical Model Checking for Verifying Rust OS Kernel Concurrency"
authors: [Ruize Tang, Minghua Wang, Xudong Sun, Lin Huang, Yu Huang, Xiaoxing Ma]
venue: ATC
year: 2025
tags: [formal-methods, model-checking, rust, os-kernel, concurrency, tla-plus]
source_pdf: "[[atc2025-tang.pdf]]"
source_md: "[[atc2025-tang]]"
---

# CONVEROS: Practical Model Checking for Verifying Rust OS Kernel Concurrency (ATC 2025)

> **一句话总结**：用 PlusCal/TLA+ 多层多粒度规约 + 改进的 trace validation 验证 ASTERINAS Rust OS 内核并发模块，4 人月、12 模块发现 20 个 bug（其中 9 个由 model checker 直接报）。

## 问题

ASTERINAS 是面向 Ant Group 部署的 Rust 通用 OS 内核（100K LoC、200 syscall、跑 JVM/MySQL）。Rust 在 safe 代码中阻止 data race，但 OS 必然要 unsafe，加上设计错误仍会引发死锁/活锁/lost wakeup/kernel panic。常规 review + CI 难以覆盖角落情况。直接用 model checking 又面临两大难题：写规约门槛高、规约-实现差异（modeling error 或代码演化）会污染验证结论。

## 核心方法

CONVEROS = 规约 + 一致性检查 + model checking 三步：

- **多层多粒度规约**：高层规约抽象公共 API 设计意图（用于早期一致性检查），低层规约贴近代码（用于检出真实 bug）；mixed-grained 借鉴 Remix，验证过的模块抽象成 coarse-grained action 减少状态空间，遵循 interaction-preserving 原则。选 PlusCal 而非纯 TLA+ 是因其类 C 命令式语法对程序员更友好，每个对共享变量的修改对应一个 atomic label。
- **改进 trace validation**：bottom-up 收集执行 trace（带时间戳、event、process id、变量更新约束）后用 trace specification 在状态空间中匹配。新增 **missing event 算法**——允许在不知道事件确切顺序/缺日志的代码段插入 missing event 占位，model checker 自动推断 0 或多个匹配 action，并配 maximum exploration depth + convergence point 两种剪枝。
- **自动化**：自动生成 trace spec、自动产生 discrepancy debug trace（用 `ENABLED` 操作符 + breakpoint 找最长未匹配的 trace 行）。

## 关键结果

- 在 12 个并发模块（SpinLock、Mutex、RwLock、RwMutex、CondVar、Semaphore、PageCursor、Pipe、RangeLock、Flock、Futex、TTY）发现 20 个新 bug，9 个直接由 model checker 报、11 个为 by-product；14 个已修复。
- spec-to-code ratio 0.3–2.3，4 模块平均 ≈3.6 人天，全部工作 4 人月。
- 所有 bug 在 2–5 process 配置下、3 分钟内（16-core 笔记本）被发现。
- 案例：range lock 的 lost wakeup bug 经过 3 次错误尝试才修对，每次 model checker 都给出反例；Mutex 的 `then_some` eager-eval 引发的互斥失效；RwLock 非原子 `try_read` 导致的 livelock。

## 相关

- **相关概念**：Model Checking、TLA+、PlusCal、Trace Validation、Concurrency Bug
- **同会议**：[[ATC-2025]]
