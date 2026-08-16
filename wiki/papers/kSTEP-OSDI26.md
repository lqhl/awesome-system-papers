---
type: paper
name: kSTEP
full_title: "kSTEP: Characterization and Deterministic Testing of Linux CPU Scheduler Bugs"
authors: [Tingjia Cao, Shawn Wanxiang Zhong, Caeden Whitaker, Ke Han, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau]
venue: OSDI
year: 2026
tags: [linux, cpu-scheduler, kernel-testing, fuzzing, determinism]
source_pdf: "[[osdi26-cao.pdf]]"
source_md: "[[osdi26-cao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Linux CPU 调度器缺陷的刻画与确定性测试（OSDI 2026）

> **原题**：kSTEP: Characterization and Deterministic Testing of Linux CPU Scheduler Bugs

> **一句话总结**：对 232 个 Linux scheduler 修复的研究发现，73% 的缺陷没有 panic 或 warning，45% 潜伏超过一年；kSTEP 把用户任务、内核事件、CPU 属性和 scheduler tick 变成可精确控制的事件，使 7 个历史缺陷都能用至多 20 步、47 行代码确定性复现，并进一步找到 4 个新缺陷。

## 问题与动机

CPU scheduler 的“正确”不止是不崩溃。Affinity、task wakeup、Deadline runtime 等是严格功能语义，违反后能明确判错；fairness、load balance、locality、work conservation、frequency control 和 energy efficiency 则是策略目标。后一类实现偏离仍能让程序运行，外部只看到偶发变慢，很难判断是 bug 还是合理取舍。论文把前者称为 functionality bug，把后者称为 policy bug。

普通 scheduler 测试有三个根本困难。第一，内部状态每个 tick 都变化，某些 bug 只在很窄的时间窗口触发；简单重放 `fork/wakeup` 顺序还不够。第二，触发源不只有用户程序，还可能是 kthread、cgroup、freezer、CPU hotplug、timer tick、拓扑、容量或频率。第三，interrupt、RCU callback、workqueue、boot state 和 clock 会让两次 trace 不同，长 benchmark 中真正的触发路径容易淹没在噪声里（§2.3）。

一个生产案例说明了代价：`bbce3de` 导致 `pick_task_fair` 空指针，用户和开发者往返 25 封邮件、远程调试数周，约一个月后靠代码推理合入修复，始终没有确认 reproducer，也没有回归测试。kSTEP 最后用 20 个事件复现了它（图 3、图 14）。

## 关键观察 / 隐含假设

### 收集方法与偏差

作者扫描 2020 年以来 mainline 和 stable branch 中修改 `kernel/sched/` 的 commit，排除 `sched_ext`。含 `Fixes:<SHA>`，或 commit message 出现 fix、regression、hang、violate 等缺陷信号的修复进入样本；feature、optimization、维护性修改和注释修改被排除。最终 232 个 bug 中，每个 bug 由一名作者调查和分类（§3.1）。

因此这些数字描述的是“近年已被发现并修复、而且留下明显修复信号的 Linux scheduler bug”，不是所有现实缺陷。未报告、未修、commit message 不明显的缺陷会漏掉；单人分类也有主观误差。

### 主要发现

- **大多不发出明显信号。** 15% 会 crash/hang；26% 是没有 warning 的 silent functionality fault，47% 是对外有影响的 policy misalignment，另有少量 benign policy bug。论文独立统计的总结果是：只有 27% 出现清楚的 panic 或 warning，73% 没有这类信号。Fair scheduler 中约 70% 属于 policy bug（§3.3、图 7）。
- **很多潜伏很久。** 45% 在 mainline 中存在超过一年，5% 超过十年。另一方面，修复进入 mainline 后，大多数受影响 LTS 都得到了正确 backport（图 5–6）。
- **状态和逻辑错是主体。** 75% 源于错误状态更新或错误决策逻辑；并发约 12%，内存错误约 7%。前者需要 scheduler domain knowledge，也更容易保持沉默（图 11）。
- **触发空间跨层。** 90% 需要特定 workload 行为，54% 依赖 scheduler attribute；19% 需要其他内核子系统事件。88% 可在普通 multicore + SMT 上触发，剩余需要 [[NUMA]]、非对称核心或其他特殊 CPU 属性。合起来有 28% 不能只靠特定用户态行为触发（§3.7、图 12）。
- **发现和修复流程缺少闭环。** 用户或测试能发现 89% 的 fatal bug、65% 的 non-fatal functionality bug，却只发现 47% 的 policy bug。61% 的 runtime-exposed bug 没有精确 trigger sequence；用户报告的 patch 只有 22% 被明确复现并验证。修复后极少补 unit test、warning 或 tracepoint（图 9–10）。

## 核心方法

### 1. 用事件驱动真实 scheduler 路径

kSTEP 的输入是一个 kernel-space driver program。driver 可以创建、暂停、唤醒、冻结和 pin task，设置 scheduling class/priority，创建 cgroup 或 kthread，也能设置 CPU topology、capacity、frequency，并显式发出 scheduler tick。特殊原语 `tick_until(predicate)` 会不断推进逻辑时间，直到短暂内部状态成立，再立刻发下一个事件（表 3、图 14）。

driver 不允许直接改 scheduler state。即便要构造复杂 cgroup/vruntime 状态，也必须通过正常的 task、cgroup 和 tick 路径达到。这样控制性来自输入事件，而被测的是 Linux 原有调度代码，不是另写的 scheduler 模型。

### 2. 把环境噪声移到 CPU 0

CPU 0 运行 driver 和 control module；CPU 1 到 N 是受控区域，只运行 kSTEP 明确创建的用户任务和被测 scheduler（图 13）。用户任务本身只是 busy loop，由 signal 决定何时运行、暂停或醒来。interrupt、RCU callback 和 workqueue worker 被重定向到 CPU 0，最小化 PID 1 避免多余进程进入受控 CPU。

Determinism module 控制 scheduler 看到的 `sched_clock` 和 `jiffies`，每轮所有 CPU 完成 tick 后才推进时间；测试前还会清零 runqueue load estimate、重设 task `vruntime`、清除各 scheduling domain 的 load-balancing cost。这样同一个 driver 在同一 kernel 上从相同状态开始，得到相同 trace（§4.3）。

### 3. 不改 scheduler 源码，但在外部加可观测性

核心 kSTEP 由约 1.5K 行 kernel module 和约 150 行最小用户态程序组成。它用 ftrace 观察 scheduler function，用 kallsyms 找 private function 地址；tick 通过 IPI 发到各受控 CPU，并等待 tick 和 softirq 全部结束后再执行下一事件。作者持续测试 kernel 5.15、6.1、6.6、6.12、6.18 和当时最新的 7.0，支持 x86_64 与 arm64（§4.4）。

“不改 kernel”主要指不修改 scheduler 源码与其决策路径。为了做 execution-path tracer 和 coverage-guided fuzzer，实验构建会另外启用 LLVM SanitizerCoverage，记录控制流 edge 的 PC，再用 `addr2line` 映射源码位置（§5.1）。

### 4. 确定性 trace 与 coverage-guided fuzzing

Tracer 按 kSTEP event、CPU 和参与 task 分开记录执行路径。例如 A 唤醒 B 时，waker path 与 wakee path 分开显示。因为 replay 稳定，开发者可以比较 buggy/fixed kernel，或逐步缩短事件序列，而不必猜测差异是否来自环境噪声。

Fuzzer 的 host manager 管理 corpus，多个 worker 各自用新 QEMU 运行测试（图 15）。guest executor 每执行一个事件就返回 task state 和 PC coverage；worker 只为 running/runnable/blocked/frozen 的当前状态生成合法后续动作。产生新 coverage 的事件成为 split point，后续 mutation 先确定性 replay 相同 prefix，再从该状态生成短后缀。要判断“新路径是不是 bug”，测试者仍需把功能或策略意图写成 invariant，最后人工检查 violation。

## 设计取舍

- **确定性换环境完整性**：移走 interrupt、workqueue 和 boot noise 后，因果路径清楚，但依赖这些活动的 bug 也可能被移走。
- **串行事件换可控 replay**：task 可以在多 CPU 并行运行，但 driver 发出的事件是串行序列，所以不能直接暴露 scheduler 内部 concurrency bug。论文样本中这类根因约占 12%。
- **真实 code path 换硬件真实性**：不直接写 scheduler state 保住了软件路径 fidelity；QEMU 中设置 topology/capacity 并不等于真实 cache、NUMA latency、firmware 和频率响应。
- **手写 invariant 换精确 oracle**：policy bug 可以用设计意图判定，却要求专家先知道应该保持什么性质，不是完全自动的通用找错器。

## 实验设计

Case study 从 232 个 bug 中抽取 7 个，覆盖 Core/Fair/Topology 等组件、policy/functionality 两类和多种触发条件。主机为 2 颗 Intel Xeon Silver、每颗 10 cores，Ubuntu 24.04。每个 case 都 checkout 修复前 commit，在新 QEMU 中跑 driver，再 checkout 修复 commit 重新运行；每次测试都重新启动并关闭 QEMU（§6）。

Fuzzer 为每个历史 bug 编写一个对应 invariant，单项运行 24 小时。这个实验回答“给定 oracle 后能否自动找到触发序列”，并不回答“在不知道 bug 的情况下 24 小时能找到多少真实缺陷”。

## 实验与结果

- **7 个历史 bug 都有短 reproducer。** 最长为 20 events、47 LoC；除一个要创建 20K task 的 case 外，其余最多用 5 个 task。所有手写 reproducer 都在数秒内运行（表 4）。
- **复杂生产 bug 可以变成直接测试。** `bbce3de` 的 reproducer 用 20 events、38 LoC 构造 cgroup 层级和 delayed-dequeue 状态，再让 `vruntime` 溢出；修复前 task 几乎永久 starvation，修复后正常分享 CPU（图 14、图 16.2）。
- **自动触发速度有明显差异。** 6 个处于 fuzzer 规模内的历史 case 中，4 个在 0.01–0.49 小时触发；sync-wakeup case 用 2.13 小时，cgroup case 用 8.68 小时。20K-task case 超出 fuzzing scale，24 小时内未触发（表 4）。
- **trace 能把影响说清楚。** 7 个 case 包括 remote CPU placement、cgroup starvation、freeze 后仍运行、重复 rebalance、`util_avg` 错估、超慢 load balance 和一次 benign `min_vruntime` 错差。正文用于确定性检查的图 16.1–16.5 和 16.7 在触发前保持相同轨迹，触发后才出现与缺陷相关的差异；图 16.6 主要比较 rebalance 的 wall time。
- **调度开销从几乎无害到严重。** 在 20K pinned task 的 CPU 设置中，修复前一次 rebalance 约需 2.5 ms，相对修复后的约 1 µs 慢了三个数量级；该设置约每 200 ms 浪费 4 ms CPU。另一个 `util_avg` 错误约 500 ms 才恢复，可能让 frequency governor 降频。`min_vruntime` case 只偏一个 tick，几乎不影响应用（§6.2）。
- **发现 4 个新 bug。** 手写 driver 找到官方 sync-wakeup 修复不完整，以及特定异构拓扑下“有 runnable task 却让 CPU 空闲”的错误；fuzzer 又找到错误 sched-group label 和低容量 CPU idle-time accounting 两个问题（图 17–18）。论文给出了修复，并称已报告给开发者；不能据此推断所有 patch 都已进入 upstream release。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| Linux scheduler bug 大多低可观测 | §3.3、图 7：73% 无 panic/warning，Fair 中 70% 为 policy bug | 2020 年后 232 个已修复 commit，单人分类 | 强 |
| 触发 scheduler bug 需要跨层输入 | §3.7、图 12：90% 需 workload，54% 需 attribute，28% 非纯用户态 | 从修复和报告反推触发条件，可能缺信息 | 中 |
| kSTEP 能把所选历史 bug 变成短确定性测试 | §6.1、表 4：7/7，至多 20 events、47 LoC | 7 个有目的选择的 case，QEMU 环境 | 强（对样本） |
| kSTEP trace 能精确比较修复前后行为 | §6.2、图 16.1–16.5、16.7：触发前一致、触发后分岔 | 没有大规模 repeated-run 统计，也未与物理机 trace 对照；图 16.6 主要测 wall time | 中 |
| 平台能帮助发现未知 bug | §6.3、图 17–18：4 个新问题 | 2 个来自手写 driver、2 个来自 fuzzer；需要 invariant 和人工确认 | 强 |

## 批判性分析

### 论证链条

Characterization 先把问题拆成“难观察”和“难触发”，kSTEP 再分别用 clean trace 与 controllable event 回答，7 个 case 最后覆盖 reproduce、observe、discover，结构很完整。外推薄弱点也很明确：平台没有在整个 232-bug population 上测可表达率，所选 case 可能本来就更适合串行 event model。

### 假设压力测试

若 bug 依赖真实 interrupt storm、device driver callback、firmware、cache hierarchy、NUMA latency、并发 race 或非确定频率变化，mock CPU attribute 可能只复现配置，不复现真实因果。反过来，清空状态和抑制活动也可能构造生产中极少到达的状态。kSTEP 证明的是“给定事件在真实 scheduler 代码中的确定行为”，不是该行为在生产中出现的频率。

### 实验可信度

逐 commit 的修复前/后 A/B、短 driver、内部 trace 和 4 个新 bug，使 case-level 证据很强。表 4 也诚实保留 20K-task case 的 fuzzing 失败。缺少的是固定 CPU-hour 下与 Syzkaller、LTP、长期 benchmark 或 record/replay 的直接比较；论文没有报告 fuzzer coverage、false positive、每项重复试验的方差，也没有说明 7 个历史 case 的抽样规则是否在看到可复现性前确定。

### 系统性缺陷

kSTEP 是开发测试底座，不是 production detector。长期使用仍依赖 kernel module、QEMU、内部 symbol、版本适配和专家编写 driver/invariant。虽然作者报告跨 kernel 与 x86_64/arm64 兼容，但 case evaluation 主要在一台 Intel 主机上，无法替代真实异构硬件验证。更根本的是，事件串行化把 12% concurrency 根因排除在直接搜索范围之外，而 policy oracle 的知识仍来自人。

## 局限与后续工作

- **局限 1**：driver event 串行执行，不能直接发现 scheduler concurrency bug。
- **局限 2**：7 个 case 不足以代表 232 个缺陷，且真实硬件 case 主要用 QEMU 属性模拟。
- **局限 3**：fuzzer 依赖手写 invariant，覆盖反馈只能找到新路径，不能自动判断策略是否正确。
- **局限 4**：论文验证 deterministic behavior，没有测 reproducer 对生产发生概率的代表性。
- **后续工作 1**：按 root cause、component、trigger 分层抽取至少 50 个历史 bug，报告 event model 可表达率、复现率、driver 编写时间和跨版本稳定性。
- **后续工作 2**：把同一 driver 放到 x86、arm64、NUMA、非对称核心和物理机上，比较 trace 与实际性能影响，区分“逻辑可复现”和“硬件上可达”。
- **后续工作 3**：与 Syzkaller/LTP 在相同 CPU-hour 下比较 scheduler edge coverage、unique bug、false positive 和 time-to-trigger。
- **后续工作 4**：加入受控并行事件或 bounded interleaving，专门覆盖 characterization 中约 12% 的 concurrency 类缺陷。
- **后续工作 5**：从 scheduler 文档和已有 selftest 自动提取 invariant，再用人工审阅衡量 oracle 生成的正确率。

## 相关

- **相关概念**：[[NUMA]]
- **同会议**：[[OSDI-2026]]
- **Artifact**：作者公开了 kSTEP 源码（§4.4）。
