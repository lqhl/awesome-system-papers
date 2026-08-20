---
type: concept
aliases: [BPF, extended BPF, Berkeley Packet Filter]
last_updated: 2026-08-14
tags: [kernel, programmability, observability, security]
---

# eBPF

> eBPF（extended Berkeley Packet Filter）让经过验证的程序动态附着到 Linux 内核 hook，在网络、观测、安全、内存和调度路径上执行。它减少了为每个策略修改内核的需求，但不自动保证策略正确、多租户隔离、公平调度或低尾延迟。

## 基本执行模型

一个典型 eBPF 扩展包含以下部分：

1. **Program type 与 hook**：程序附着到 XDP、TC、tracepoint、kprobe、cgroup、LSM、`sched_ext`、`struct_ops` 等位置。hook 决定它何时运行、能看到什么 context，以及能否睡眠或被抢占。
2. **Verifier**：加载前做静态分析，检查控制流有界、指针和内存访问安全、helper 调用合法、stack 与资源限制等。
3. **JIT 或解释执行**：通过验证后，通常编译为本机指令，在事件路径上运行。
4. **Map**：程序与用户态或其他 eBPF 程序共享状态。map 的生命周期、并发与租户归属仍需系统设计。
5. **Helper / kfunc**：受控调用内核能力。它们既是功能接口，也是 verifier 能看见的安全边界。

“verifier 接受”只表示它证明了当前模型中的若干低层安全属性。它不表示程序业务逻辑正确，不表示运行时间短，也不表示两个各自安全的程序组合后不会相互干扰。

## 为什么它重要

eBPF 把“改内核源码、重启机器”变成“加载一个受限策略程序”。这特别适合机制稳定、策略经常变化的场景：内核保留 packet processing、page fault、scheduler queue 或 page cache 等可信机制，eBPF 决定分类、优先级、淘汰和监控规则。

但论文也显示，eBPF 已从几十条 packet filter 扩展到数据库、文件系统、调度器和虚拟化 fast path。程序规模、状态与执行时间增长后，原来“短小、同一信任域、run-to-completion”的前提逐一失效。

## 三类核心边界

### 1. Verifier 的安全性与表达力

[[BCF-SOSP25]] 发现，Linux verifier 为保持内核内分析便宜，使用 interval、tristate 等较粗抽象，会误拒安全程序。BCF 只在 verifier 卡住时把精化交给用户态 SMT solver，再让内核线性时间检查 proof；512 个真实误拒程序中接受 403 个（78.7%），平均 proof 为 541 B、检查约 48.5 微秒。它提高的是特定 false reject 的精度，不代表覆盖全部 ISA、helper 和 verifier bug。

[[Veritas-SOSP25]] 从相反方向找问题：用 SMT 规格当 fuzzing oracle，在三个月间歇 campaign 中报告 15 个 issue，其中包括 3 个不安全程序被接受和 9 个安全程序被拒绝。规格本身也可能有错，因此结果需要人工归因；它说明“生产 verifier 是可信根”仍需持续测试，不是一次形式化工作即可结束。

[[Rex-ATC25]] 认为大型程序的根本问题是源语言与 bytecode verifier 的契约不一致。它用 safe Rust 和轻量 runtime 替代 bytecode verifier 路径，同时复用 eBPF hook 与 helper。BMC 重写用 326 行 Rust 代替 513 行 C 和 7 个 tail-call program，8 核吞吐 1.98M RPS，略高于 eBPF 版本的 1.92M。代价是受限 Rust 子集、每个内核 ABI 重建、watchdog termination，以及仍需维护少量 `unsafe` 可信代码；这是一条替代验证层的路线，不是 eBPF verifier 本身的升级。

### 2. Run-to-completion 与 CPU accounting

[[PeeR-OSDI26]] 测到现代 eBPF invocation 的运行时间可能有很长尾部：RocksDB XRP 的 P50/P99 为 4/882 微秒。XDP 等程序在 softirq 中不可抢占地执行，内核调度器看不到真正消耗 CPU 的租户，长程序会挡住短事件。PeeR 让 verifier 标出 helper/kfunc 边界的安全 continuation point，超预算后把程序续跑到 per-CPU kernel thread，再交给 `sched_ext` 调度；短请求 P99 降低 3–19.8 倍，一次 yield/resume 平均 247 ns。

该机制依赖程序会到达足够密集的安全点。长时间不调用 helper 的循环、不可恢复的 helper side effect、continuation queue 过载和 daemon failure，仍需要额外 guardrail。更一般地说，eBPF 安全证明和 CPU 调度语义必须联合设计。

### 3. 单一信任域与多租户隔离

[[vBPF-OSDI26]] 指出 Linux 把程序在加载时固定到全局 physical hook：不同租户会争 singleton `struct_ops`，顺序修改共享 state，并为无关程序支付线性执行成本。vBPF 在 hook 前放 multiplexer，事件发生后由 Snifer 判断 namespace，再用 hash dispatch 选择该租户程序与 state overlay。跨租户 lmbench latency 最高改善 3.9 倍，PostgreSQL TPS 最高提高 29%；160 个 kprobe 的 microbenchmark 中，相对 native 线性执行最高快 54 倍。

这些数字来自“跳过无关程序”；同租户的相关程序仍要运行。隔离还依赖 resource→namespace attribution、修改后的 kernel、verifier/JIT、编译器分析和人工 `vbpf_safe` 标注。kfunc、RCU reader、共享 socket、合并 I/O、资源复用与恶意 resource churn 都没有完整覆盖，所以 vBPF 提供的是共享内核内的逻辑隔离，不等同于 MicroVM 硬件边界。

## eBPF 作为策略层

### 调度

[[Aeolia-SOSP25]] 通过 `sched_ext` 和 eBPF map 协调用户态 NVMe interrupt 与内核调度，避免 I/O 完成后错误 sleep/idle；它的贡献同时依赖 user interrupt、用户态文件系统和调度器，不应把最高 19.1 倍 LevelDB 增益全归因于 eBPF。

[[MUSCHED-OSDI26]] 在移动设备上增加临时 VIP 调度类，用 eBPF maps 和 `sched_ext_ops` 热更新交互场景策略。它在 2,000 万台以上 Honor 设备上线，并把启动、动画、滑动异常分别降低 30.7%、25.0%、35.7%。首次部署仍修改 bpfloader、加入 kfunc 和调度机制；普通应用不能只加载一个程序就得到同样能力。

[[FlexGuard-SOSP25]] 用 `sched_switch` hook 检测持锁线程是否在 critical section 内被抢占，再把 spin waiter 转为 blocking。结果说明 eBPF 能把内核调度事件反馈给用户锁，但依赖特权、栈/寄存器可见性和准确的 critical-section 标记。

[[vBOIDs-OSDI26]] 只把用 `sched_ext`/eBPF 重做容器 BOID 调度列为后续工作；其约 3 倍 throughput-under-SLO 来自定制内核实现，不能当作 eBPF 实验结果。

### 内存与缓存

[[PageFlex-ATC25]] 保留 Linux swap 机制，把 reclamation 与 prefetch policy 委托给用户态，并用 eBPF 在 page event 上维护每页 4 B 状态。Redis 相对 kernel LRU 开销少于 1%，17 行 Hyperbolic policy 和 Leap prefetch 在特定 strided workload 中把 refault 改善 75.4%。复杂跨页或 ML policy 仍会撞 verifier、map 和状态限制。

[[cache_ext-SOSP25]] 走另一条路：用 eBPF `struct_ops` 在内核内实现 page-cache eviction policy，kernel 仍管理 folio。generic policy 吞吐最高提高 38%，application-informed policy 最高 1.70 倍并把 P99 降低 58%。论文自己的结论是“没有统一最佳策略”，不是任意 workload 都应替换 LRU。

[[Osprey-OSDI26]] 用 page-fault pre-handler 上的 eBPF 将访问地址写入 ring buffer，帮助安全计算程序提前换页；32 GB 限制下相对 Linux swapping 最高 12 倍。它同时依赖双 pass、MPK、修改后的 `userfaultfd`/`madvise` 和库 annotation，eBPF 只是低成本 trace 通道。

[[uCache-FAST26]] 则故意不使用 eBPF verifier：unikernel 内 callback 直接运行，换取性能和共享符号能力，也把 buggy policy 的故障域扩大到整个 VM。论文没有与 PageFlex/cache_ext 做同机对比，因此只能说明另一种安全—性能取舍。

### 内核参数与虚拟化 fast path

[[Xkernel-OSDI26]] 用 Kprobe 拦截常量 materialization，再让 eBPF 风格 policy 通过专用 kfunc选择已分析过的值。140 个常量支持 139 个，中位切换时间 2.8 ms，KLP 为 30.4 ms；但 verifier 不知道数值是否符合 RFC、设备限制或多个 knob 的业务 invariant，安全值域仍由 policy 作者负责。

[[HyperTurtle-ATC25]] 让 L1 hypervisor 把短小 vm-exit 逻辑写成 eBPF hyperupcall，直接在 L0 处理 L2 事件，避免进入 L1 的 world switch。EPT fault 延迟降低 5.1 倍，Kata 启动快 27%；复杂、需要锁或 frame pool 耗尽的情况 fallback 到传统路径。其安全依赖 L0 verifier、helper 地址检查和正确的 L1/L2 资源归属。

[[RosenBridge-FAST26]] 在 QEMU 用户态运行 uBPF，而不是把 guest 程序放入 host kernel。PREVAIL 检查程序，`io_uring` SQ/CQ 双 hook 支持 submission 与 content-based resubmit。RosenXRP 相对 virtio-blk 吞吐提高 461.8%，但仍落后 bare-metal XRP；这是 eBPF ISA/生态在虚拟化中的变体，不应与原生内核 eBPF 混称为同一隔离强度。

## eBPF 作为观测工具

[[Loom-SOSP25]] 的动机来自 eBPF/perf 等每秒数百万条记录的 telemetry：采集快不等于存得下、查得快。Loom 的贡献是 log 与稀疏索引，不是 eBPF runtime。

[[Blink-OSDI26]] 把 eBPF、perf 等列为已有 profiling 工具，并用函数边界直接读 PMU，解决 mobile short-function 的 skid 与 shadow effect。Blink 没有以 eBPF 实现主机制。

[[mwait-sched-OSDI26]] 用生产 eBPF 样本观察到 `mwait` idle duration 近似双峰，再设计虚拟化感知调度。eBPF 在这里是测量来源，不是调度执行路径。

## 还只是方向、不是已有结果的用法

- [[Ichnaea-OSDI26]] 提议未来用 kernel/eBPF 捕获绕过 libc 的内存访问；当前完整性结果没有实现这条路径。
- [[Rakaia-OSDI26]] 当前用内核 C parser 做 TCP message 调度，并把新增协议的 eBPF extension 留作可能方向；它的 5 倍 KCM 结果不是 eBPF 结果。
- [[vBOIDs-OSDI26]] 如上所述，只提出 sched_ext/eBPF prototype 作为后续比较。

## 设计取舍总结

| 选择 | 好处 | 代价 |
|---|---|---|
| 内核内 eBPF policy | fast path 低开销，能直接看内核事件 | verifier 表达力、调试和升级兼容受限 |
| 用户态 policy + eBPF event | 重逻辑易开发、易更新 | 需要异步队列、批量接口和状态一致性 |
| run-to-completion | 路径短、实现简单 | 长程序无 accounting，造成队头阻塞 |
| continuation/preemption | 可做公平调度和尾延迟隔离 | 需要安全点、状态保存和过载控制 |
| static binding | 原生 Linux 简单高效 | singleton 与多租户功能、性能冲突 |
| late binding | 按租户选择程序和 state | 每事件 attribution、lookup 与更大可信根 |
| bytecode verifier | 语言无关、加载时检查 | false reject、实现 bug、源码映射困难 |
| safe-language extension | 契约更贴近开发者 | 换 ABI、runtime 与编译器可信根 |

## 批判性分析

eBPF 最成功的抽象是把“允许扩展内核”拆成两个问题：内核提供少量受控 hook/helper，策略程序在加载时验证。它让大量原本需要 fork kernel 的功能可迭代部署。

但论文共同表明，eBPF 的安全故事不能停在 verifier。完整系统至少还要回答：事件属于谁、程序能运行多久、谁为 CPU 付费、多个程序如何组合、map/state 如何隔离、helper side effect 是否完整建模，以及坏策略如何回滚。PeeR、vBPF、BCF 与 Veritas 分别补调度、租户、精度与测试，恰好说明单一 verifier 无法覆盖这些维度。

评测还需区分“eBPF 是核心机制”“eBPF 只是 policy language”“eBPF 只是 trace source”。把整个系统的最高加速都归给 eBPF，会掩盖 user interrupt、MPK、CXL、文件系统或内核 parser 的主要贡献。

## 开放问题

- 能否统一 verifier proof、运行时 continuation 和 CPU accounting，而不把 helper 变成唯一安全点？
- 多租户 hook、map、kernel object 与 parent audit 的隔离语义如何形式化并做故障注入？
- helper/kfunc 快速增长时，如何让 side-effect annotation、规格、fuzz oracle 和内核版本 CI 同步？
- 如何给 eBPF program 设置 CPU、内存、map、事件率和 continuation queue 的可组合 quota？
- policy 更新失败或 verifier/JIT 回归时，怎样安全回滚并保持 map state 与业务语义？
- safe Rust、证明携带代码和传统 verifier 应如何按 program complexity 自动选择？

## 相关论文

- **智能体控制面**：[[SchedCP-arXiv25]] 用 `sched_ext`、静态检查、微虚拟机和签名令牌约束智能体生成的调度策略；性能案例存在，但安全机制尚无独立漏检率实验。
- **验证与安全**：[[BCF-SOSP25]]、[[Veritas-SOSP25]]、[[Rex-ATC25]]。
- **调度与多租户**：[[PeeR-OSDI26]]、[[vBPF-OSDI26]]、[[Aeolia-SOSP25]]、[[MUSCHED-OSDI26]]、[[FlexGuard-SOSP25]]。
- **内存与缓存策略**：[[PageFlex-ATC25]]、[[cache_ext-SOSP25]]、[[Osprey-OSDI26]]、[[uCache-FAST26]]。
- **虚拟化与参数控制**：[[HyperTurtle-ATC25]]、[[RosenBridge-FAST26]]、[[Xkernel-OSDI26]]。
- **观测或未来方向**：[[Loom-SOSP25]]、[[Blink-OSDI26]]、[[mwait-sched-OSDI26]]、[[Ichnaea-OSDI26]]、[[Rakaia-OSDI26]]、[[vBOIDs-OSDI26]]。

## 相关概念

- verifier、JIT、XDP、`sched_ext`、`struct_ops`、kprobe、tracepoint、BPF map、helper、kfunc
