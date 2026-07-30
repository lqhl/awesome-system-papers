---
type: paper
name: SyzMini
full_title: Optimizing Input Minimization in Kernel Fuzzing
authors: [Hui Guo, Hao Sun, Shan Huang, Ting Su, Geguang Pu, Shaohua Li]
venue: ATC
year: 2025
tags: [fuzzing, kernel-fuzzing, input-minimization, syzkaller, bug-finding, security]
source_pdf: "[[atc2025-guo.pdf]]"
source_md: "[[atc2025-guo]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# SyzMini：优化内核模糊测试中的输入最小化（ATC 2025）

> **原题**：Optimizing Input Minimization in Kernel Fuzzing

> **一句话总结**：SyzMini 的核心观察是 [[Syzkaller]] 的 input minimization 既不可少又太贵：去掉 minimization 会让覆盖和 bug 数分别下降 27.5%/40.4%，但它又消耗 57.5% program executions；论文用 influence-guided call removal 和 type-informed argument simplification 减少 coverage-preservation 验证次数，使 minimization 执行数下降 60.7%，分支覆盖提升 12.5%，unique bug 数提升 1.7-2.0x。

## 问题与动机

Coverage-guided [[Kernel-Fuzzing]] 的核心循环通常由 mutation 和 minimization 两部分组成。mutation 生成新的 syscall sequence；当某个 program 覆盖新分支后，minimization 会把它压缩成更短、更少冗余参数、仍保留新覆盖的 seed。这个阶段不是清理工作，而是影响后续 mutation 质量的关键路径：更短的 seed 通常意味着更小的搜索空间和更高概率的有用变异。

问题在于，Syzkaller 的默认 one-by-one minimization 非常保守。删除每个 syscall、简化每个 argument 或 sub-field 之后，都要重新动态执行 program，验证 target call 的新覆盖是否仍然保留。对 kernel fuzzer 来说，program execution 本身昂贵，因为它涉及 user/kernel crossing、VM 中 kernel 执行、KCOV/KASAN 等 instrumentation。论文测到，在 48 小时 fuzzing campaign 中，minimization 消耗了 57.5% 的 program executions，甚至超过 mutation。

作者的 claim 边界很清楚：SyzMini 不试图替换 fuzzing oracle、mutation policy 或 seed scheduler，而是优化已有 coverage-guided kernel fuzzer 的 minimization stage。它的目标不是生成“语义上最小”的 testcase，而是在保持 Syzkaller 式 coverage-preserving seed 质量的同时，减少为了验证 coverage preservation 所需的动态执行次数。

## 关键观察 / 隐含假设

- **观察 1：minimization 对 kernel fuzzing 效果是必要的，而不是可有可无的后处理。** 论文在 Linux 5.15 上比较 Syzkaller 与去掉 minimization 的 Syzkaller-，48 小时内 Syzkaller- 的 branch coverage 和 unique bug 数分别下降 27.5% 和 40.4%，且差距随时间扩大。
  - **依赖假设**：coverage-preserving short seeds 对后续 mutation 的收益足以抵消 minimization 自身成本。
  - **可能失效场景**：如果 mutation policy 本身能处理长 syscall sequence，或目标 bug 依赖较长历史状态，过度追求短 seed 可能不总是最优。

- **观察 2：minimization 的主要成本是反复动态执行 reduced program 来确认 coverage 是否保留。** 作者记录 mutation/minimization execution share，minimization 在 4.5 小时时达到 68.1% 峰值，48 小时后仍占 57.5%；在 minimization 内部，call removal 占 34.0%，argument simplification 占 66.0%。
  - **依赖假设**：program execution count 是 fuzzing budget 的主要代理指标，减少 execution 次数会把真实 wall-clock 时间释放给 mutation。
  - **可能失效场景**：如果 relation collection、type analysis、coverage bookkeeping 或 VM reset 成为新的主导成本，execution count 的改善不一定等比例转化为吞吐。

- **观察 3：syscall sequence 中很多 call 对 target call 的新覆盖没有 execution influence，可以批量删除。** 论文把 influence relation 定义为一个 call 通过修改 kernel internal state 改变另一个 call 的 execution path；基于静态 Syzlang type/resource 分析和动态 minimization 历史，作者收集了 74,865 条 influence relations，并用它们把 call-removal verification executions 降低 57.1%。
  - **依赖假设**：influence relation 的覆盖率和精度足够高，错误识别 irrelevant calls 不会频繁导致批量删除失败。
  - **可能失效场景**：新 driver、新 syscall、并发路径、隐式全局状态、时间相关状态或 nondeterministic coverage 都可能让 influence matrix 过期或不完整。

- **观察 4：许多 fixed-size argument 的 simplification 不会有效缩小后续 mutation space。** Syzkaller 对 integer、flag、protocol、resource 等 primitive argument 也会尝试替换成默认值，但这类 fixed-size 参数不像 array/buffer 那样包含可删减的元素。作者统计 Syzkaller 近五年 syscall descriptions，fixed-size parameters 长期占 74.0%-80.6%，并让 type-informed strategy 把 argument-simplification verification executions 降低 62.8%。
  - **依赖假设**：argument type 是“是否值得 minimization”的好代理；fixed-size scalar 的默认化收益小于它消耗的验证成本。
  - **可能失效场景**：某些 scalar/resource 值虽然不改变大小，却会显著影响后续 mutation locality、reproducer 稳定性或 bug trigger probability。

- **假设 1：target-call branch coverage preservation 足以代表 minimization correctness。**
  - **证据强度**：中。它延续 Syzkaller 的默认 criterion，并在 coverage/bug finding 上有效，但 coverage equivalence 不是 semantic equivalence，也不保证保留所有潜在 bug-triggering behavior。

## 核心方法

SyzMini 集成在 Syzkaller commit `1759857fa9bd` 上，只改 minimization stage。它保留 Syzkaller 的基本约束：每次成功删减都要保证 target call 的 branch coverage 被保留；如果优化策略不能安全减少 program，就回到默认 one-by-one minimization 兜底。

第一部分是 **influence-guided call removal**。对一个 interesting program `P = [c1, ..., cn]`，假设 `cn` 是产生新覆盖的 target call。SyzMini 先从 influence matrix 中找出对 `cn` 有直接 influence 的前序 calls，再用 worklist 递归追踪间接 influence，得到 relevant calls。剩下的 calls 被视为 irrelevant calls，SyzMini 会一次性删除它们并执行 reduced program。如果 target call coverage 被保留，则批量删除成功；如果不保留，则回滚。无论批量删除是否成功，剩余 program 还会继续经过 one-by-one call removal，保证最终 call set 不只是“关系上相关”，还通过了实际 coverage check。

influence relation 的来源有两类。静态部分来自 Syzlang syscall descriptions：如果 `ci` 返回某种 resource，而 `cj` 的参数使用该 resource，或者 `ci` 的 outward pointer 参数可能产生 `cj` inward 使用的 resource，就认为存在潜在 influence。动态部分复用默认 minimization 的经验：当删除某个 call 改变后续 call 的 coverage path，就记录 influence。这个设计直接回应观察 3：不要为每个显然无关的 call 各跑一次验证，而是先用 dependency approximation 做批量尝试，再用 coverage execution 作为最终裁判。

第二部分是 **type-informed argument simplification**。SyzMini 把 argument 分成 fixed-size 和 variable-size。Integer、Flag、Protocol、Resource 属于 fixed-size；Array 和 Buffer 属于 variable-size；Pointer 和 Struct/Union/Enum 则递归检查 pointed-to object 或 sub-fields。对 fixed-size argument，SyzMini 跳过 simplification；对 variable-size argument，仍然用 binary search 删除元素，并在每次删减后验证 target call coverage。这个策略回应观察 4：真正能显著压缩 mutation space 的往往是 variable-length payload，而不是把每个 scalar 都替换成默认值。

两个策略的组合保持了一个很“系统论文”的取舍：它没有引入复杂的新 oracle，也没有尝试精确建模 kernel semantics，只用 cheap approximation 找到可能省掉的验证执行，再用原有 dynamic execution 保住 observable correctness。SyzMini 因而也能移植到 SyzVegas、CountDown、SyzDirect 这类仍继承 Syzkaller minimization 结构的工具。

## 设计取舍

- **批量删除换取执行次数下降，但依赖 influence relation 的新鲜度。** relation 越完整，越能一次删掉更多 irrelevant calls；但 matrix 需要随 Syzlang、kernel version、driver coverage 演化维护。论文收集动态 influence relations 花了约四天，这个成本适合长期 fuzzing service 摊销，不适合一次性短任务。
- **简单失败处理换实现稳健。** 当 irrelevant-call batch deletion 失败时，SyzMini 直接回滚并进入 one-by-one，而不是继续把 batch 二分细拆。收益是实现简单、不会削弱默认 minimization correctness；代价是部分“batch 中只有少数误判 call”的场景没有被继续优化。
- **跳过 fixed-size argument simplification 换更多 mutation 时间。** 这个取舍在系统层面很有力，因为 fixed-size 参数占比高；但它牺牲了某些 scalar 默认化可能带来的 seed canonicalization 或 replay 稳定性收益。
- **coverage-preserving criterion 换通用性。** 用 branch coverage 判断删减是否成功，与 Syzkaller 原模型一致，容易移植；但 coverage 相同不代表 kernel state、bug trigger condition 或后续 mutation distribution 完全等价。
- **最小侵入换适用面。** SyzMini 不干预 scheduler、mutation operator 或 bug oracle，因此能与其他 kernel fuzzing optimization 正交叠加；相应地，它能解决的也只是不必要 minimization execution，而不是 syscall specification 缺失、stateful driver modeling、concurrency bug exploration 等问题。

## 实验与结果

- **实验设置**：主实验在 Ubuntu 20.04、AMD 3995WX 64-core CPU、128 GB RAM 上进行，目标 kernel 为 Linux 5.15、6.1、6.11，启用 KCOV/KASAN；每个 fuzzing VM 分配 4-core CPU 和 4 GB RAM。端到端比较 SyzMini 和 Syzkaller 时，每组 24 小时，重复 10 轮。
- **动机实验**：去掉 minimization 的 Syzkaller- 在 48 小时内 coverage 少 27.5%，unique bugs 少 40.4%；与此同时，默认 Syzkaller 的 minimization 消耗 57.5% program executions，说明“不能删掉 minimization，但必须降成本”这个问题成立。
- **coverage 主结果**：SyzMini 在 Linux 5.15/6.1/6.11 上分别从 145.371K/150.677K/133.172K branches 提升到 164.724K/169.015K/149.311K branches，对应 +13.3%/+12.2%/+12.1%；overall branch coverage +12.5%，达到 Syzkaller 同等覆盖的平均 speed-up 为 1.69x。
- **bug finding 主结果**：SyzMini 在三版 kernel 上的 unique bugs 分别为 28/20/12，而 Syzkaller 为 14/12/6；总体 unique bugs 从 27 提升到 50。对双方都能找到的 common bugs，SyzMini 的 hitting-round 更高、平均 time-to-exposure 更低。
- **长期 fuzzing**：在 Linux 6.11 上跑三天，SyzMini 平均覆盖 199.4K branches，比 Syzkaller 的 188.9K 高 5.6%。它还找到 13 个 previously unknown bugs，全部被确认，其中 4 个已修复。
- **ablation**：只启用 influence-guided strategy 的 SyzMiniα 带来 3.5%-4.6% coverage 提升和 1.0-1.35x bug 提升；只启用 type-informed strategy 的 SyzMiniβ 带来 8.3%-9.1% coverage 提升和 1.2-1.5x bug 提升。两者作用在不同 minimization 子阶段，因此效果近似正交。
- **minimization cost**：对 16,266 个 interesting programs 的 controlled experiment 中，one-by-one minimization 需要 400,859 次验证执行；两项优化同时启用后降到 157,268 次，减少 60.7%。其中 call removal 从 140,620 降到 60,372，argument simplification 从 260,239 降到 96,896。
- **execution share**：以 Linux 5.15 为例，Syzkaller 的 minimization 占 48.2% program executions，而 SyzMini 只有 11.5%；mutation execution share 从 51.8% 提升到 88.5%。这解释了 coverage 和 bug finding 的端到端提升来自哪里：省下来的预算回到了 mutation。
- **泛化到其他 fuzzers**：移植到 SyzVegas 后，branch coverage +14.5%，unique bugs 从 16 增到 24；移植到 CountDown 后，KASAN bugs 从 27 增到 43，branch coverage +4.5%；移植到 SyzDirect 后，10 个目标 bug 中可复现数量从 6 增到 9，且 common bugs 的 hitting-round/TTE 更好。

## 批判性分析

### 论证链条

论文的 observation -> design -> result 链条比较闭合。它先证明 minimization 对 seed quality 有用，再证明 one-by-one minimization 吃掉过半执行预算；两个设计分别对应 minimization 的两个主要成本源：call removal 用 influence relation 减少候选验证，argument simplification 用 type information 跳过低收益参数；最后用 controlled execution-count experiment 解释为什么端到端 coverage/bug finding 会提升。

最强的部分是 ablation 和 cost decomposition。SyzMiniα/SyzMiniβ 分别证明两个策略独立有效，Table 7 又把“覆盖提升”还原成具体省掉了多少 verification executions。这避免了很多 fuzzing 论文常见的问题：只展示最终 bug 数，却说不清机制是否真起作用。

需要收窄的是 generality claim。论文证明的是：在 Syzkaller-family、coverage-guided、syscall-sequence kernel fuzzing 中，minimization verification cost 是一个可优化瓶颈；它没有证明所有 kernel fuzzing 或所有 input minimization 都应跳过 fixed-size scalar 或依赖 syscall influence matrix。

### 假设压力测试

influence-guided strategy 最脆的地方是 relation freshness。静态 Syzlang relation 只能覆盖类型和 resource 层面的显式依赖，动态 relation 又依赖预先跑过的 workload。对于新加入的 syscall、out-of-tree driver、复杂 global state、并发交错、timer/interrupt 影响或 nondeterministic path，matrix 可能漏掉真实 influence。SyzMini 的最终 coverage check 可以防止错误删除被接受，但如果 batch 经常失败，优化收益会下降。

type-informed strategy 的关键假设是“fixed-size simplification 的收益小”。这在 mutation-space size 上很合理，但 fuzzing seed quality 不只由大小决定。某些 scalar 参数的默认化可能让后续 mutation 更稳定、更可复现，或避免把 corpus 填满难以 replay 的边缘值。论文用端到端结果说明整体收益为正，但没有细分哪些 bug 或 subsystem 可能从 scalar simplification 中受益。

coverage preservation 也是一个有限 oracle。SyzMini 保留 target call branch coverage，但 coverage 相同并不保证 kernel state 相同，也不保证后续 mutation 的概率分布相同。对 bug discovery 来说，这通常是 Syzkaller 已接受的工程折中；但如果目标是 crash reproducer minimization、security exploitability triage 或 semantic minimization，就需要更强 oracle。

### 实验可信度

实验设置总体扎实：多个 Linux LTS/upstream 版本、10 轮重复、24 小时 campaign、long-term 3 天实验、ablation、controlled cost measurement，以及对 SyzVegas/CountDown/SyzDirect 的移植。baseline 也足够强，因为 Syzkaller 是实际部署和学术工作常用的 kernel fuzzer。

主要实验缺口有三个。第一，论文报告 mean 和 standard deviation，但没有显式统计检验或 confidence interval；fuzzing 结果方差通常较大。第二，dynamic influence collection 的四天预处理成本没有纳入端到端成本模型；对长期 fuzzing service 可以摊销，对短期 campaign 则可能影响收益。第三，所有主实验集中在 Linux + Syzkaller/Syzlang 生态，不能直接外推到 Windows kernel fuzzing、closed-source drivers、microkernel 或非 syscall-sequence 输入模型。

### 系统性缺陷

SyzMini 的工程风险主要在维护面，而不是 runtime correctness 面。influence matrix 需要随 syscall descriptions 和 kernel evolution 更新；如果更新流程不自动化，fuzzer 可能逐渐退化回 one-by-one 的成本，或者频繁 batch failure。论文没有详细讨论 relation database 的版本管理、增量更新、过期检测和 observability。

论文也没有深入讨论 nondeterminism。Kernel fuzzing 中 coverage 可能受调度、设备状态、内存布局、race、timeout 影响。SyzMini 和 Syzkaller 都依赖 coverage check，但批量删除让一次尝试覆盖更多变化，如果 coverage 抖动较大，可能更容易误判成功或失败。这里需要更多关于 retry policy、flakiness filtering、tail-latency impact 的实现细节。

最后，SyzMini 把更多时间交给 mutation，但 mutation 侧是否会出现新的瓶颈没有展开。例如 corpus growth、scheduler pressure、duplicate bug triage、VM crash recovery、KASAN overhead 等都可能在长期 fuzzing 中成为下一个限制因素。论文三天实验显示收益仍在，但 production service 级别的多周运行还需要单独验证。

## 局限与后续工作

- **局限 1：influence relation collection 有明显 amortization 假设。** Future work 可以做 incremental relation learning，报告 relation freshness、batch success rate、过期 relation 检测率，以及不同 kernel/Syzlang 版本迁移时的收益衰减。
- **局限 2：coverage-preserving minimization 不等于 bug-preserving minimization。** 可以在 crash reproducer corpus 上比较 SyzMini minimization 与 one-by-one minimization 对 crash replay rate、triage stability、stack trace consistency 的影响。
- **局限 3：fixed-size argument simplification 被整体跳过，缺少 finer-grained 例外机制。** 一个可测方向是识别“高影响 scalar/resource argument”，只对这类参数做 simplification，并用 execution budget、coverage、bug replay stability 三指标比较。
- **局限 4：实验生态集中在 Linux/Syzkaller-family。** 后续可以在 Windows kernel fuzzer、driver-specific fuzzer 或非 Syzlang 描述系统上重做 influence/type 两个抽象，验证哪些部分是真正通用的。
- **局限 5：长期 production 运维面未覆盖。** 可以把 SyzMini 部署到持续 fuzzing service 中，测量多周的 relation update cost、corpus size、duplicate reports、VM crash recovery cost、new-bug yield over time。

## 相关

- **相关概念**：[[Kernel-Fuzzing]]、[[Coverage-Guided-Fuzzing]]、[[Input-Minimization]]、[[System-Call-Dependency]]、[[Delta-Debugging]]
- **同类系统**：[[Syzkaller]]、[[SyzMini]]、[[Healer]]、[[SyzVegas]]、[[CountDown]]、[[SyzDirect]]、[[Moonshine]]
- **同会议**：[[ATC-2025]]
- **源材料**：[[atc2025-guo]]、[[atc2025-guo.pdf]]
