---
type: paper
name: kSTEP
full_title: "kSTEP: Characterization and Deterministic Testing of Linux CPU Scheduler Bugs"
authors: [Tingjia Cao, Shawn (Wanxiang) Zhong, Caeden Whitaker, Ke Han, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau]
venue: OSDI
year: 2026
tags: [linux-scheduler, deterministic-testing, kernel-testing, fuzzing, policy-bugs]
source_pdf: "[[osdi26-cao.pdf]]"
source_md: "[[osdi26-cao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# kSTEP：Linux CPU 调度器缺陷的刻画与确定性测试（OSDI 2026）

> **原题**：kSTEP: Characterization and Deterministic Testing of Linux CPU Scheduler Bugs

> **一句话总结**：Linux 调度器缺陷中 73% 不会留下明确告警，且触发往往依赖瞬时状态、内核事件和硬件拓扑；kSTEP 在隔离 CPU 上控制任务、内核事件、CPU 属性和 tick，并重置时钟与调度状态，使最多 20 个事件即可稳定重现 7 个真实缺陷，另发现 4 个新缺陷。

## 问题与动机

Linux CPU 调度器同时承担严格的功能正确性和软性的策略目标。前者包括 CPU affinity、唤醒和避免饥饿，后者包括公平性、局部性、负载均衡、能效与调度开销。策略缺陷不会让系统崩溃，外部看到的性能下降也可能只是正常的策略权衡，因此很难构造可靠的判定器。

作者分析了 2020 年以来 Linux 调度器的 232 个修复提交。现有测试主要依靠长时间 benchmark，无法精确控制事件时序，也难以覆盖由 kthread、CPU hotplug 或特殊拓扑引起的路径。普通 trace 又会把中断、RCU、workqueue 和时钟变化混入结果，妨碍调试。

## 关键观察 / 隐含假设

- **观察 1：缺陷多数是静默的。** 仅 27% 的缺陷表现为 panic、oops、warning 等明显信号；73% 是静默功能违规或策略偏离（图 7）。
  - **依赖假设**：调度器的内部状态和意图可以作为比外部性能更可靠的判定依据。
  - **可能失效场景**：若策略本身没有可操作的不变量，内部 trace 仍可能只能显示异常，不能证明其为 bug。
- **观察 2：触发条件依赖精确时序和丰富输入。** 90% 的缺陷需要特定用户任务行为，54% 依赖调度属性，28% 还需要内核事件或特殊 CPU 属性（图 12）。
  - **可能失效场景**：串行事件驱动器不能直接探索调度器内部并发竞态；论文统计中约 12% 的根因属于并发问题。
- **观察 3：调度器缺陷长期存在。** 约 45% 的缺陷在主线中隐藏超过一年，5% 超过十年（图 5）。研究样本来自带 `Fixes:` 或缺陷关键词的修复提交，未修复或未报告的缺陷不在样本内。

## 核心方法

kSTEP 将测试写成由事件组成的 driver。事件可以创建、暂停、唤醒、冻结和绑定任务，配置 cgroup 与调度属性，注入 kthread 活动，并修改 CPU topology、capacity 和 frequency。driver 不能直接写调度器状态，只能调用正常内核路径；这保持了对真实 Linux 调度器的测试保真度。

它提供显式 scheduler tick 和 `tick_until`。后者持续注入 tick，直到指定谓词成立，再执行下一个事件，因此可以把操作放在瞬时调度状态中。该机制直接回应了 §2.3 的时序挑战，例如在 EEVDF 的 delayed dequeue 造成“排队但不可运行”的窗口内触发同步唤醒。

确定性模块模拟 `sched_clock` 和 `jiffies`，将中断、RCU callback、workqueue worker 重定向到控制 CPU 之外，并在每次运行前重置 runqueue load、任务 vruntime 和负载均衡计数器。受控 CPU 只运行测试任务，tick 结束后等待所有 CPU 完成调度与 softirq，从而让相同 driver 在同一内核上产生稳定 trace。

在此基础上，kSTEP tracer 按事件和任务记录调度器控制流；fuzzer 使用 SanitizerCoverage 的边覆盖率，维护任务状态以生成合法事件，并从产生新覆盖率的前缀重新播放、变异后续事件。确定性 replay 使覆盖率反馈和中间状态变异具有可重复语义。

## 设计取舍

- **隔离与时钟模拟换取可诊断性**：结果适合比较 kernel 版本和策略配置，但主要保证的是同一内核环境下的重复性，不是完整机器级 record-and-replay。
- **内核模块和 QEMU 换取低侵入性与可移植性**：使用 ftrace、kallsyms 和未修改的 Linux 内核，支持 v5.15、v6.1、v6.6、v6.12、v6.18、v7.0，以及 x86_64 和 arm64；代价是需要维护内核接口适配和专用测试环境。
- **串行 driver 换取时序控制**：适合状态与策略缺陷，不直接覆盖调度器内部并发竞态。

## 实验与结果

- 232 个自 2020 年以来的调度器 bug-fix commit 构成刻画样本；75% 根因是状态更新或逻辑错误，54% 依赖调度属性，28% 不能仅靠用户态行为触发（§3）。
- 7 个真实缺陷均可由不超过 20 个 kSTEP 事件、最多 47 行 driver 代码触发；多数测试只需不超过 5 个任务，测试在 QEMU 中数秒完成（§6.1，表 4）。
- fuzzer 在 24 小时运行中重现了研究缺陷；除需要 20k 线程的 Bug #6 外，大多数在 1 小时内触发，复杂的 cgroup 缺陷 Bug #2 用时超过 8 小时（§6.1，表 4）。
- kSTEP 复现 7 个已知缺陷，并发现 4 个新缺陷：其中两个由手写 driver 发现，两个由 fuzzer 发现（§6.3）。新缺陷包括 work-conserving 违规、拓扑分组标签错误和低容量 CPU 上 `util_avg` 突降。
- trace 在触发点之前保持一致、触发后清晰分叉；例如 Bug #1 的远端放置可使首轮 CPU-bound 延迟约慢 3×，Bug #6 的 rebalance 开销约为 2.5 ms，而修复后约为 1 µs（图 2、图 16）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 调度器缺陷普遍难以从外部观察 | 73% 无 warning；策略缺陷占比高（图 7） | 232 个 Linux 修复提交 | 强 |
| 精确事件控制能压缩复现程序 | 7 个案例最多 20 事件、47 行代码（表 4） | 7 个缺陷，QEMU，指定 kernel 版本 | 强 |
| 确定性 trace 有助于定位影响 | 触发前 trace 一致，触发后行为分叉（图 16） | 同一内核、隔离 CPU | 强 |
| kSTEP 可发现新缺陷 | 4 个新缺陷，手写与自动 fuzzing 各发现 2 个（§6.3） | 最新 Linux、有限拓扑与 fuzzing 规模 | 中 |

## 批判性分析

### 论证链条

论文从缺陷刻画得到“时序、输入控制和噪声”三个测试障碍，再分别用事件 API、显式 tick 和隔离/状态重置回应，逻辑链条是闭合的。案例也显示这些机制确实能把月级调试压缩为短 driver。但“可触发”与“可判定”仍有差距：策略 bug 的 oracle 需要人工编码不变量，异常 trace 不一定自动等价于策略违规。

### 假设压力测试

kSTEP 假定测试者能把所需内核活动抽象成可调度事件，并能在 QEMU 中表达目标硬件属性。真实生产环境的中断竞争、驱动行为和多租户噪声被隔离掉后，可能遗漏只在真实硬件或真实负载下出现的问题。fuzzer 的事件序列是串行的，因此其发现能力不覆盖并发根因。

### 实验可信度

7 个案例覆盖多个组件、可观测性和触发类型，且逐一比较修复前后版本；这足以验证机制可用性。样本规模对“发现新 bug 的普遍能力”仍有限，fuzzer 只运行 24 小时，Bug #6 也表明线程数和状态空间会成为瓶颈。论文没有给出与现有 scheduler benchmark、LinSched 或通用 kernel fuzzer 在同等预算下的系统性对比。

### 系统性缺陷

driver 运行在内核模块中，并借助 kallsyms 调用私有函数，增加了权限、接口稳定性和审计成本。论文报告了跨若干 kernel 版本的兼容性，但未量化维护成本、QEMU 与真实硬件的性能差异，也未讨论将生成测试接入 Linux CI 后的运行时间、失败归因和资源隔离。

## 局限与后续工作

- **局限 1**：串行事件模型不能直接暴露调度器内部竞态；需要将受控并发与当前的精确 tick 组合起来。
- **局限 2**：策略 oracle 依赖人工为每个 bug 编写不变量；后续应评估从调度策略文档、历史修复或 invariant mining 自动生成 oracle 的误报率。
- **局限 3**：特殊硬件属性主要是模拟的；应在真实 NUMA、异构 CPU、chiplet 和不同 SMT 配置上验证测试结果是否保持一致。
- **后续工作 1**：把 kSTEP driver 作为回归测试运行在多个 LTS kernel 上，测量跨版本行为差异、每次测试的启动成本和缺陷重现率。

## 相关

- **相关概念**：[[Linux Scheduler]]、[[Deterministic Replay]]、[[Kernel Fuzzing]]、[[Work Conservation]]
- **同类系统**：[[LinSched]]、[[syzkaller]]
- **同会议**：[[OSDI-2026]]
