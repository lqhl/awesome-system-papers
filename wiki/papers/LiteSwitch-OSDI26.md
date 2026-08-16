---
type: paper
name: LiteSwitch
full_title: "Harvesting Sub-Microsecond CXL Memory Stalls with LiteSwitch"
authors: [Nanqinqin Li, Yuhong Zhong, Asaf Cidon, Michael J. Freedman]
venue: OSDI
year: 2026
tags: [cxl, memory-stalls, context-switch, hardware-software-codesign]
source_pdf: "[[osdi26-li-nanqinqin.pdf]]"
source_md: "[[osdi26-li-nanqinqin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 回收亚微秒级 CXL 内存停顿（OSDI 2026）

> **原题**：Harvesting Sub-Microsecond CXL Memory Stalls with LiteSwitch

> **一句话总结**：LiteSwitch 把一次真正阻塞退休、且确定要访问 [[CXL]] 的 load 变成同进程内的轻量分支，再切给同一 bundle 中的另一个可运行线程；论文的模拟实验显示，它在 200 ns CXL 延迟下可把多数工作负载相对本地 DRAM 的 slowdown 从 8%–29% 降到 1.7%–10%，但核心硬件 LDMB 没有实现，模拟还把所有 CXL-bound LLC miss 都当成可回收停顿，因此结果更像“若该硬件语义成立，软件能获得多少收益”，不是现有处理器上的部署结论。

## 问题与动机

本地 DRAM 的 load-to-use 延迟通常约 81–117 ns，论文汇总的直接连接 CXL 内存约为 214–394 ns；经过交换机、远端 [[NUMA|NUMA]] 或多租户争用后，还可能接近 1 µs。很多内存密集程序本来就有 20%–80% 的周期在等内存，CXL 会把这些停顿再拉长（§1、§2）。

已有方案覆盖不了约 200 ns 到 1 µs 这一段：

- SMT 只能提供少量硬件上下文。两个 sibling 同时等待 CXL 时，核心仍会闲置；即使只有一个线程等待，它也不会被“解除停顿”。
- MSH 一类软件方案靠离线 profiling 放置 yield point，但页面位置、CXL 拓扑和租户争用会在线变化，同一条 load 不一定每次都慢。
- SkyByte 用中断和内核调度处理几十微秒级 CXL-SSD miss。论文实测中断交付约 600 ns，已经超过 LiteSwitch 想回收的整个窗口。
- 即使采用用户态调度，完整保存和恢复 SIMD/FP 扩展状态（xstate）也要 70–300 ns，不能每次都付（§3、§4.3）。

问题因此被拆成三步：尽早且准确地**检测**真正的 CXL 停顿，用低于中断的代价把它**交付**给软件，再以远低于普通 context switch 的代价完成**调度**。

## 关键观察 / 隐含假设

- **观察 1：CXL 目标位置比预测具体延迟更稳定。** CPU 的 cache lookup 和路由逻辑本来就知道请求是否 miss、是否要去 CXL；与其预测“会慢多久”，不如在线识别“已经成为退休瓶颈的 CXL load”（§4.1）。
  - **依赖假设**：从 CXL 判定到数据返回之间仍有足够窗口。Intel Flat Memory Mode 必须先查本地 DRAM cache tag，检测会晚一个 DRAM 访问；直接暴露 CXL 地址时可以更早按物理地址路由。
- **观察 2：同地址空间内可以用分支代替中断。** 触发者、handler 和接替线程都属于同一进程，因此无需切特权级、页表、IDT 或内核栈；硬件只需清掉更年轻的推测状态并跳到注册的 handler（§4.1）。
  - **依赖假设**：现代乱序处理器能安全实现这种同步、同权限的 redirect，并正确处理异常、信号、抢占和暂态执行。
- **观察 3：普通 worker 可以互相接替。** 同进程线程通常共享代码、数据结构和 TLB 状态，比专门的 best-effort scavenger 更有局部性；而且单向 handoff 不要求 scavenger 在原 load 返回前主动 yield，少付一次切换（§4.2）。
  - **依赖假设**：每核有足够多的可运行线程。线程同步、I/O 或少并发服务使 bundle 只剩一个 runnable thread 时，停顿仍然完全暴露。
- **观察 4：xstate 使用集中在少数函数。** 图 12 中 graph workload 在使用 xstate 的函数里只花不到 5% 时间，多数其他程序也低于 55%；可用静态函数范围判断何时跳过 `xsave/xrstor`（§4.3、§6.2.3）。
  - **依赖假设**：二进制有可靠符号和静态函数边界。stripped binary、JIT、Python/Java runtime 不满足这个条件，Windows 的 callee-saved XMM 规则也需要额外处理。
- **假设 1：吞吐而非单请求尾延迟是主要目标。** Bundled Handoff 提高的是每核完成的总工作量，不会让原请求的 CXL load 更早完成；fan-out 服务的最慢子请求可能看不到收益（§4.2）。

## 核心方法

### 1. LDMB：只在真正退休阻塞时跳转

位置相关内存分支（Location-Dependent Memory Branching，LDMB）复用 LLC miss 和内存路由结果。内存控制器在确认请求去 CXL、且已分配 MSHR 后向核心发信号。为避免把有足够内存级并行性（MLP）的普通 miss 也当成 stall，microcode 还比较该 load 的 ROB entry 与 ROB head：只有请求尚未完成并正在阻塞顺序退休时才 redirect，否则放弃这次机会（图 2、§4.1）。

redirect 进入预先注册的同权限 handler，只在用户栈压入 `rip` 和 `rflags`；返回时用一个设想的 `LRET` 恢复。原内存请求继续异步执行。接替后再回来重试 load 时，数据通常已经进 cache；若还没完成，line buffer 会合并请求。论文估计从内存控制器回信约 10 ns，清流水线并 redirect 约 10 ns，总 LDMB 交付成本约 20 ns，但这只是架构估算，不是硅上测量。

### 2. Bundled Handoff：把调度策略留给原 scheduler

正常 kernel 或 user-level scheduler 每次不再只选一个线程，而是给每个硬件线程形成一个小 bundle。bundle 中的线程都已经通过原有的公平性、优先级和核绑定策略；LDMB 触发后，handler 只需在 bundle 内 round-robin 选下一个 runnable thread，不再执行完整策略判断（图 2、§4.2）。

handoff 是单向的：新线程一直运行到自己也遇到 stall，或发生 yield、阻塞、时间片耗尽、抢占等正常调度事件。后一类事件会拆掉整个 bundle，把所有线程退回原 scheduler。论文认为 bundle 大小 2 往往已经够用；真正决定是否有 scavenger 的是全局 worker oversubscription 和线程是否因同步而阻塞。

### 3. xstate-Aware Context Switch：只在必要时保存 SIMD/FP

离线工具 `xstatedump` 从 ELF symbol table 找出完全不含 xstate 指令的函数范围。进程启动后把这些范围映射到运行时地址，并建成默认 64 B 粒度的只读 bitmap。handler 用 stall frame 中的 `rip` 查 bitmap：若当前位置被保守地标为 xstate-free，就只保存通用寄存器；否则执行完整 `xsave/xrstor`，或者在代价大于可回收窗口时直接放弃（图 2–3、§4.3）。

通用寄存器切换约 10 ns，scavenger selection 约 4 ns；包括 bitmap lookup 在内的固定软件路径，在热点状态下约 18 ns。加上估计的 LDMB 交付，xstate-free 的常见完整路径约在 50 ns 内，而不是把“少于 20 ns”理解成从硬件检测到新线程运行的全部成本。

### 4. 原型如何模拟不存在的硬件

软件实现基于 Caladan，运行在 Intel Emerald Rapids 与 Linux 6.8.12。作者没有实现 LDMB：FPGA 无法准确复现现代服务器 CPU 的 cache、ROB 和乱序时序，因此用 PMU 统计 LLC load miss，并按真实 Intel Flat Memory Mode 机器测得的每 workload CXL access ratio 触发 PMI；kernel shim 构造 stall frame，再用 `tpause` 注入指定长度的停顿。shim 自身的损失按每次 PMI 测量后从结果中扣除（§5.1）。

这个“真实比例 + 软件注入”保留了平均 stall 时间与总吞吐影响，但事件按近似平坦频率注入，PMI 还在原 LLC miss 已完成后到达。更重要的是，模拟没有执行 LDMB 设计里的 ROB-head 检查，也没有建模 MLP；它把每个抽中的 CXL-bound LLC miss 都当成独立、可回收的 stall，论文明确承认这会高估可回收事件数。

## 设计取舍

- **精确触发换硬件修改。** 地址位置和 ROB head 能避免离线预测误差，但需要处理器厂商新增 signal、控制寄存器、stall frame 和返回语义。
- **同进程低开销换跨进程能力。** LiteSwitch 不能把一个租户的空闲周期安全地交给另一个进程，也不能直接帮助单线程程序。
- **更多 runnable thread 换 cache 与调度压力。** 4–8 倍 oversubscription 能快速减少无 scavenger 情况，但更多栈、工作集和同步竞争可能恶化 cache、内存带宽和公平性。
- **函数级静态分析换适用范围。** bitmap lookup 很便宜且保守，但 JIT、动态生成代码、stripped binary 和频繁加载 library 需要新的元数据路径。
- **只处理真 stall 换漏掉机会。** LDMB 对 CXL 信号只检查一次 ROB head，不追踪后来才阻塞退休的 load；硬件简单了，但会漏掉部分可收割窗口。
- **平均吞吐换尾延迟证据。** 模拟适合计算等量工作完成时间，不保留真实 miss burst、依赖链或请求级 tail behavior。

## 实验设置

- CXL access ratio 来自一台 50:50 DRAM:CXL 的 Intel Flat Memory Mode 系统；性能实验则在只有本地 DRAM 的 Xeon Gold 5512U 上注入事件。主要设置把 CXL 访问延迟设为 200 ns（表 1–2、§5.1、§6）。
- workload 包括 GAP graph、SPEC CPU 2017、Memcached、FASTER KV 和 Silo；端到端指标是相对“无限本地 DRAM”oracle 的吞吐 slowdown。除 SMT 专项外，配置关闭 SMT，并为每种配置分别选择表现最好的 worker 数。
- 对比项是无回收的 IFM-200、假定 20 ns LDMB 交付的 LiteSwitch，以及用约 600 ns 中断路径的 SkyByte。所有 CXL 行为都在本地 DRAM机器上模拟，不是三套真实硬件。

## 实验与结果

- **端到端 slowdown**：图 4 中，LiteSwitch 对每个 workload 都优于 IFM-200。`bfs/urand`、`bfs/web`、`cc/urand`、`cc/web` 分别从 20.7%、8.3%、29.4%、27.4% 降到 4.1%、1.7%、9.6%、10.0%；FASTER/YCSB-A 和 Silo/TPCC 从 9.9% 与 9.0% 降到 2.5% 与 3.1%。多数 workload 相对 IFM-200 回收 30%–80% 的 slowdown；SIMD/FP 较重的 SPEC `619.lbm_s`、`657.xz_s` 仍有 8.4%、7.1% slowdown（图 4、§6.1.1）。
- **与 SMT 的关系**：`bfs/urand` 相对无 LiteSwitch、无 SMT 基线，LiteSwitch 单独加速 1.16 倍，SMT 单独 1.69 倍，二者合用 1.87 倍。大多数 graph 与 KV workload 也呈现互补，但 SPEC 的 slowdown 降幅在开 SMT 后从 33%/31% 缩到 7%/22%，说明 sibling 争用会吃掉部分收益（图 5–6、§6.1.2）。
- **LDMB 成本敏感性**：在 200 ns CXL 延迟下逐步增大 LDMB 交付成本，slowdown 近似线性上升。`619.lbm_s` 约在 72 ns 与 IFM-200 打平，`bfs/urand` 到约 185 ns 才打平；能否承受较慢硬件路径强烈依赖 xstate 开销和事件频率（图 7、§6.1.3）。
- **CXL 延迟敏感性**：`bfs/urand` 从约 200 ns 扫到 800 ns 时，IFM slowdown 近似随延迟线性增加，LiteSwitch 曲线接近平坦，因为每次主要支付固定 handler 成本；剩余增长来自 bundle 偶尔只有一个 runnable thread。论文称其他 workload 有相同定性趋势，但只画出这一项（图 8、§6.1.4）。
- **oversubscription 与固定路径**：`bfs/urand` 在 2 倍 oversubscription 时有 45% invocation 没有 scavenger，6–8 倍时降到 12%–14%；多数 workload 需要约 6–12 倍才能让超过 90% 的 stall 有可运行线程。固定 handler 在触发率极低时超过 100 ns，但达到每千条指令 `10^-2` 次 CXL access 后稳定在约 18 ns，所测 workload 都处在这一热路径区间（图 9、图 11、§6.2.1–6.2.2）。
- **xstate 消融**：图 12 中“实际执行于 xstate 函数的时间”与“handoff 需要 `xsave/xrstor` 的比例”总体接近，说明 bitmap 判断有效；graph workload 的保存比例接近 0，`619.lbm_s` 与 `657.xz_s` 接近 100%。默认 64 B block 对多数 workload 足够，但 `cc/web` 要缩到 8 B 才能把保存比例从超过一半降到接近 0（图 10、图 12、§6.2.3）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 亚微秒 CXL stall 中确有足够软件 handoff 空间 | 图 4：多数 workload 的 slowdown 相对 IFM-200 减少 30%–80%；图 11：热点固定软件路径约 18 ns | 20 ns LDMB 是估算；CXL 与 LDMB 都靠注入模拟，且未建模 MLP | 中 |
| LiteSwitch 能补充而不是替代 SMT | 图 5：`bfs/urand` 从 1.16/1.69 倍分别收益组合到 1.87 倍；图 6 给出全 workload 结果 | SPEC workload 在 SMT 争用下增益明显缩小 | 中到强 |
| xstate-aware 分析能避免多数无用保存 | 图 10、图 12：xstate-light workload 的 `xsave/xrstor` 比例大幅下降，且 block 粒度结果可解释 | 依赖带符号静态二进制；JIT、stripped binary 未支持 | 强 |
| 更长 CXL 延迟主要转成固定每事件成本 | 图 8：`bfs/urand` 在 200–800 ns 范围内曲线近似平坦 | 只展示一个 workload；注入不保留 burst、依赖链和请求尾延迟 | 中 |
| 大量 runnable thread 是端到端收益的必要条件 | 图 9：2 倍时 45% 无 scavenger，6–8 倍降至 12%–14% | 高 oversubscription 的 cache、内存和调度副作用没有独立量化 | 强 |

## 批判性分析

### 论证链条

论文的拆解很清楚：CXL 位置与 ROB head 解决检测，同地址空间 branch 解决交付，bundle 和 xstate bitmap 解决调度成本；图 7、图 9–12 也分别测试了硬件预算、线程供给和软件开销。薄弱的一环正是最关键的一环：LDMB 没有实现，评测又没有执行设计中避免 MLP 误触发的 ROB-head 条件。因而图 4 证明的是“给定理想化 stall event，Bundled Handoff 可以利用它”，不能完整证明真实 CPU 会产生同样数量、同样时机的 event。

### 假设压力测试

若程序只有少量线程、线程常在 barrier 同时等待，或一个请求的关键路径不能被其他工作替代，LiteSwitch 只会支付 handler 成本。AVX-512、矩阵和加密 workload 会频繁保存 xstate，`619.lbm_s` 已显示 break-even 只剩约 72 ns。真实 CXL miss 若有较高 MLP，许多 LLC miss 并不阻塞退休；而 Flat Memory Mode 又要等 DRAM tag check 后才能知道落到 CXL，两者都会缩短或消除论文假定的窗口。

### 实验可信度

workload 跨 graph、SPEC、KV 和数据库，作者还分别扫描 SMT、LDMB 成本、CXL 延迟、线程数、handler 热度和 bitmap 粒度，软件部分的内部证据完整。作者也主动披露 double emulation、平坦注入和 tail-latency 限制。可惜没有真实 CXL 请求 trace 重放、周期级模拟器、RTL/FPGA 控制路径或请求 P99；PMI 在触发 miss 完成后才到达，kernel shim 的 cache 污染虽被计时扣除，也不能完全等同于硬件 redirect。

### 系统性缺陷

LDMB 修改了处理器最敏感的控制流和异常语义，却没有面积、功耗、critical path、nested event、安全或 transient-execution 分析。bundle 把一个 OS 可见线程扩成多个运行上下文，可能破坏 perf accounting、signal delivery、debugger、priority inheritance 和语言 runtime 的假设。系统还通过高 oversubscription 交换吞吐，可能增加 cache footprint、内存带宽、单请求等待和能耗；这些成本没有进入论文的 throughput slowdown 指标。

## 局限与后续工作

- **局限 1**：LDMB 只有高层提案和 20 ns 成本估算，没有 RTL、模拟器或实体处理器验证。
- **局限 2**：事件注入没有建模 ROB-head、MLP、miss burst、依赖链和请求尾延迟，可能高估 harvestable stall。
- **局限 3**：xstate 优化要求静态、带符号二进制；JIT、stripped binary、动态代码和不同 ABI 尚未支持。
- **局限 4**：主要指标是吞吐 slowdown，没有服务 P95/P99、公平性、能耗或多租户 cache/带宽干扰。
- **后续工作 1**：用 gem5/周期级模拟或 CPU vendor 原型实现 LDMB，逐项测信号时序、ROB 条件、异常、功耗和安全性。
- **后续工作 2**：采集真实 CXL miss trace，保留 burst、MLP 和依赖关系重放，并同时报告 throughput、每请求 P99 和无收益 event 比例。
- **后续工作 3**：让 runtime 根据 xstate 比例、scavenger availability 和尾延迟在线关闭 harvesting，避免少线程与 SIMD 密集场景产生负收益。
- **后续工作 4**：系统化验证 bundle 与 Linux signal、preemption、debugging、cgroup accounting 和语言调度器的组合语义。

## 相关

- **相关概念**：[[CXL]]、[[PCIe]]
- **相关工作**：MSH、SkyByte、Caladan、switch-on-event multithreading
- **同会议**：[[OSDI-2026]]
