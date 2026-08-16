---
type: paper
name: Xkernel
full_title: "Xkernel: Principled Performance Tunability of Operating System Kernels"
authors: [Zhongjie Chen, Wentao Zhang, Yulong Tang, Ran Shu, Fengyuan Ren, Tianyin Xu, Jing Liu]
venue: OSDI
year: 2026
tags: [linux, kernel, ebpf, performance-tuning, live-update]
source_pdf: "[[osdi26-chen-zhongjie.pdf]]"
source_md: "[[osdi26-chen-zhongjie]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 让已部署的内核性能常量可安全调节（OSDI 2026）

> **原题**：Xkernel: Principled Performance Tunability of Operating System Kernels

> **一句话总结**：Linux 的固定性能常量会把旧硬件和旧 workload 的取舍固化进 binary；Xkernel 离线找出常量进入机器状态的 critical span 和副作用消退前的 safe span，运行时通过 Kprobe 与 [[eBPF]] 间接改写结果，在 140 个常量中支持 139 个，并把图 21 中的中位切换时间从 KLP 的 30.4 ms 降到 2.8 ms。

## 问题与动机

Linux 中大量 threshold、batch size、time interval 和 scaling factor 以 macro、literal 或 `static const` 固化。论文把它们称为性能关键常量（performance-critical constant，perf-const）：它们不决定某项功能是否存在，却决定延迟与吞吐、响应性与利用率等性能取舍。一个数值通常由开发者在当年的硬件和有限测试上选定，部署后却不能按设备、workload、process 或 flow 改变。

`sysctl`/`sysfs` 不是通用答案。每个 knob 都要单独改源码和维护 ABI，粒度通常预先固定为 system-wide。作者统计 Linux 6.14 的 145 个 performance-related sysctl knob，其中 96 个自 2005 年以来没有改变；附录图 24 统计有 20 个 knob 在转换后需要 bug fix，作者还人工标出 43 个可能存在 race 或 inconsistent state 的 knob（§2.2、附录 A）。把只读常量变成任何线程都可写的 global variable，本身会增加并发风险。

[[Kernel-Live-Patching]]（KLP）可以替换运行中的函数，但每个新数值仍需改源码、编译和生成 binary diff。它以 function 为 version atomicity 的单位，范围对一个常量往往过大，而且只保证线程不混用新旧函数版本，不保证旧值产生的副作用已经消失。Xkernel 因而要提供一种更小、更快的单位：不改原 kernel binary，就让任意合适的 perf-const 在运行时变成细粒度、可编程的 knob。

`BLK_MAX_REQUEST_COUNT` 展示了这个需求为何真实。同一默认值 32，在 7200-RPM HDD 的近顺序 FIO 上应增到 128，read/write 分别提高 7×/54×；在 Toshiba XG3 [[NVMe|NVMe]] 上跑 32 GB [[RocksDB|RocksDB]] random workload 时却应降到 1，吞吐提高 1.2×，P50/P75 latency 分别改善 1.37×/1.41×（§2.1、图 1）。固定默认值无法同时覆盖方向相反的 regime。

## 关键观察 / 隐含假设

- **观察 1：perf-const 第一次进入 register 或 memory 的 binary 范围通常很小。** 140 个常量一共产生 367 个 critical span（CS）；48% 的常量只有一个 CS，86% 少于 5 个，几乎所有 CS 只有一条 instruction（§6.1、图 16–17）。
  - **依赖假设**：compiler 的 constant folding、strength reduction 和 inlining 虽改变形式，但 symbolic execution 仍能找到所有 materialization site。
  - **可能失效场景**：常量被 dead-code elimination 删除、多个 symbol 在 binary 中无法区分、Kprobe 不能挂载，或影响 JIT/self-modifying code。
- **观察 2：改常量时，version atomicity 不足以代表安全。** 线程即使完整执行旧版或新版 CS，旧值衍生的数据仍可能被后续 instruction、callee 或其他线程消费；因此要等这些依赖离开 safe span（SS）后才能切换（§3.5、图 5）。
  - **依赖假设**：inter-procedural data slice 能保守覆盖所有 transitive consumer；论文当前主要追踪 data dependency。
  - **可能失效场景**：安全性依赖 control flow、异步 workqueue、RCU callback、设备寄存器或 DMA，而这些状态没有被 slice 封装。
- **观察 3：CS 与 SS 通常比整个 function 小得多。** 300 个 SS 的中位大小是 10 条 instruction，而最大值约 8K，呈明显长尾；用小范围做 transition 能比 function-level KLP 更快，也暴露了少数复杂依赖（§6.1、图 17）。
  - **依赖假设**：线程会频繁越过 SS boundary，使 reference count 最终收敛到 0。
  - **可能失效场景**：目标路径长期不执行，或线程长期停留在 SS 内；Xkernel 只能在 timeout 后报告 transition 失败。
- **假设 1：用户选择的新值属于“只影响性能、不改变正确性”的范围。**
  - **证据强度**：弱到中。它是 perf-const 的定义，但 Xkernel 除 register-width 等架构限制外不提供内置范围检查，极端值和错误分类仍可能造成 overflow、资源耗尽或 starvation（§7）。
- **假设 2：运行 kernel 的准确源码、compiler version、build config 和相关 module/driver source 可获得。**
  - **证据强度**：中。定制 kernel 通常满足，distribution kernel 也可能提供构建信息；闭源 vendor driver 或供应链不完整时则无法生成可信 scope table。

## 核心方法

Xkernel 的核心机制叫作用域间接执行（Scoped Indirect Execution，SIE）。离线工具先由用户给出 perf-const 的 source file、line 和 token，使用特殊“magic value”重编译同一 kernel，并比较 binary 找到受影响位置。随后从这些 seed 做向前和向后的 symbolic execution，直到恢复出常量 `V` 与受影响 machine state `IV` 的关系以及最小 single-entry/single-exit CS（§3.2–§3.3、图 2–4）。scope table 与准确 binary 绑定，可在运行相同 binary 的机器间复用。

运行时不会删除或修改原 CS。Xkernel 在 `{binary location, update}` 处放置 Kprobe，把控制转到 JIT 生成的短代码，再把 register 或 memory 调整成“如果原 binary 使用新常量”应得到的状态。若原操作可逆，indirection 先逆运算再应用新值；若 bit masking 等操作丢失信息，则在 CS 前保存原状态、在后一个位置恢复无关部分，形成 dual-location indirection。367 个 CS 中只有 3 个需要后一种路径（§3.4、图 3–4）。

为了保证副作用安全（side-effect safety），离线 LLVM pass 从每个 CS 做 inter-procedural forward thin slicing，把所有消费 constant-dependent state 的 instruction 包进 single-entry、multi-exit SS；重叠 SS 会合并。切换期间临时在 SS entry/exit 插入 Kprobe。per-thread 模式在目标线程越过安全边界时切换；global-consistency 模式只调用一次 `stop_machine` 扫描所有 stack 初始化 reference count，之后让线程在越过边界时自然更新计数，归零后才启用新值（§3.5、图 5）。rollback 走同一机制。

策略层由 `xk-gen` 生成 Xk-tune stub，用户用 eBPF 风格代码读取 process、device、RTT、BPF map 或 kernel metric，并调用 `xk_set` 选值、用 `xk_transition_done` 检查切换是否结束。普通 eBPF 不能写 kernel memory，Xkernel 只向经过 verifier 的 Xk-tune 暴露专用 BPF kfunc，由预生成的 SIE indirection 执行受控写入。多个 perf-const 的 Xk-tune 可放在一个文件中原子 load/unload；每个常量同一时刻最多属于一个 active transaction（§3.6、图 6–8）。

实现中，Xk-runtime 约 1.7K 行 kernel C，工具链约 11K 行 Python，其中约 5K 行用于 CS/SS 分析。runtime 以 module、Kprobe、eBPF 和 background monitor kthread 实现，不修改 kernel source 或原 binary。为了减少 probe 成本，它尽量使用 boosted/jump-optimized Kprobe，并调整 attachment location（§4、附录 B）。

## 设计取舍

- **通用 knob 换静态分析可信度**：不再为每个常量手改源码，但 CS 或 SS 漏掉一个依赖就可能破坏安全，离线分析器进入 trusted computing base。
- **细粒度更新换热路径 probe 成本**：jump-optimized Kprobe 的空开销约 168 cycles，INT3 路径约 1,765 cycles；极短、高频 operation 或同时开启大量 knob 时会明显变慢。
- **策略可编程性换数值风险**：eBPF verifier 只检查 program safety，不知道新数值是否符合 RFC、设备约束或跨 knob invariant；范围检查由 Xk-tune 作者负责。
- **精确 artifact 换部署复用**：scope table 可供相同 binary 的机器共享，但 kernel、compiler、config、module 或 driver 任一更新都要重建。
- **安全优先换覆盖率**：系统主动拒绝会改变 memory layout、被 dead-code elimination 删除或不能安全挂 Kprobe 的常量，因此论文标题里的“any perf-const”应理解为“任何满足 SIE 前提的 perf-const”。
- **边界条件**：CS/SS 小、operation 自身超过约 20 µs、线程经常经过 SS boundary 时最合适；长 SS、高并发、INT3-only site 和缺少源码时会变脆。

## 实验与结果

- CloudLab 测试机使用 28-core Xeon Gold 5512U、128 GB RAM 和两块 800 GB NVMe Gen4 SSD；storage、network、CPU、memory 的 140 个手选 perf-const 中支持 139 个（99.3%），唯一失败是 Btrfs `SEND_MAX_EXTENT_REFS` 的 duplicate symbol 使 Kprobe target 有歧义（§6、附录 C）。367 个 CS 大多为 1 条 instruction；300 个 SS 中位 10 条、最大约 8K（图 15–17）。
- 单次空 jump-optimized Kprobe 增加 168 cycles，INT3 增加 1,765 cycles；每个 operation 计算为 0/5/10/20 µs 时，median latency slowdown 分别约 15%/5%/2%/少于 1%。Redis YCSB/ETC 开 32 个热路径 probe 时吞吐最多降 4%，128 个时降 7%–14%（§6.2、表 3、图 18–19）。
- 即使一个 perf-const 有 15 个 SS，policy update 也不超过 542 ms；per-thread side-effect-safe transition 均少于 10 ms，global consistency 在 16 threads 的压力实验中最高报告 144 ms。图 21 的曲线给出 Xkernel P50 2.8 ms、Linux KLP 30.4 ms，且 KLP 的时间还不含约 7 分钟 patch generation（§6.3、图 20–23）。
- 每个常量的离线流程平均 18 分钟：两次编译并行使用 56 threads，约 7 分钟；SS construction 平均 `11 ± 20` 分钟，最复杂者 124 分钟。N 个常量需要 2N 次重编译，但不同常量可并行，结果可按 exact binary 摊销（§6.4）。
- storage case 中，`BLK_MAX_REQUEST_COUNT` 按 device/workload 分别设为 128 或 1：HDD FIO read/write 相对默认 32 提高 7×/54×；32 GB NVMe RocksDB 吞吐提高 1.2×，I/O wait CPU time 降 12%，P50/P75 latency 改善 1.37×/1.41×（§2.1、§5.1、图 1）。
- 其余 case 展示的是可调节的取舍而非统一加速：`MAX_SOFTIRQ_RESTART=10` 时 CPU utilization 52%、worst latency 560 µs，最优 latency 149 µs 要付出 22% CPU utilization penalty；`SHRINK_BATCH` 大于 24 会使 zswap workload thrash；动态联合调 3 个 TCP CUBIC 常量后，80 ms flow 的 P99.99 FCT 降 81%，20 ms flow 基本不变（§5.1、图 9–12）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| perf-const 的 binary influence 通常足够局部，可用 CS 间接改写 | 图 16–17：139/140 支持，CS 几乎都为 1 条 instruction | Linux 四个 subsystem、140 个手选常量、单一 build 环境 | 强 |
| SIE 在一般 operation 上开销较低，但不是无条件 negligible | 表 3、图 18–19：20 µs 后少于 1%，128 probes 为 7%–14% | `/dev/null` microbenchmark 与 Redis YCSB/ETC | 强 |
| CS/SS 能让在线 policy update 与安全切换达到毫秒到亚秒 | 图 20–23：2.8 ms P50、per-thread 少于 10 ms、global 144 ms | 最多 15 SS、16 threads；不含离线分析 | 中到强 |
| 一个固定 perf-const 确实无法覆盖异构 hardware/workload | 图 1：HDD 最佳 128、NVMe RocksDB 最佳 1 | 一块 SAS HDD、一块 Toshiba XG3 NVMe、两个 workload | 强 |
| 可编程细粒度调节能改善真实应用尾延迟 | 图 12：长 RTT NGINX P99.99 FCT 降 81% | 20/80 ms 混合 flow、人工选择的 CUBIC policy | 中 |

## 批判性分析

### 论证链条

论文从“固定常量隐含动态 policy”出发，用 CS 的局部性证明 indirect update 可行，再用 SS 补上普通 live patch 缺少的副作用安全，设计与测量大体闭合。139/140 的覆盖率和 span distribution 支持 SIE 对所选样本的通用性。但“Xkernel 能调任何 perf-const”外推过强：系统明确排除 memory-layout constant、DCE case 和无法定位 Kprobe 的情况，140 个样本也是作者承认的 Linux 全部 perf-const 的小子集。

### 假设压力测试

SS 目前主要按 data dependency 构造；如果安全条件来自 control flow，或旧值已传播到设备、DMA、异步 worker、timer/RCU callback，薄 slice 可能无法封装真正副作用。global transition 还假设线程最终离开 SS，论文只提供 timeout，没有 liveness guarantee。最重要的是，Xkernel 保证的是“如何一致地换值”，不是“这个值正确”：错误范围、多个 knob 的语义冲突和不稳定 feedback controller 都可能让 kernel 表现甚至正确性恶化。

### 实验可信度

评测覆盖四个 subsystem、五类 case、probe overhead、并发 transition 和 offline cost，比只展示调优收益更完整。主要不足是只有一套 CPU/ISA/compiler/build 环境，没有用独立 oracle 验证 static analysis 是否漏掉 CS/SS，也没有长时间 fuzz、crash/recovery 或不同 architecture 的结果。140 个常量由作者选择，不能估计全 kernel 的真实拒绝率。

论文还有两个需要谨慎读取的数字口径。图 21 和图例明确显示 Xkernel P50 2.8 ms、KLP 30.4 ms，但相邻正文把两者名字写反；这里按图、load time 标注和“CS 更快”的结论采用前者。主文表 3 把 jump-optimized CS 比例写为 84.2%，附录 B 又说优化后从 66.6% 提到 88.3%，论文没有解释这两个口径的差别。

### 系统性缺陷

部署需要带源码和 debug/build 信息做离线分析，再加载 kernel module、BPF kfunc 和多个 Kprobe，增加了供应链、权限与攻击面。论文展示 atomic transaction，却没有系统评测不同团队 policy 冲突、签名和审计、crash 后恢复哪个值、kernel upgrade 如何废止旧 scope table，或坏 policy 如何自动 rollback。INT3-only 热点和 128 个 active probe 已有 7%–14% slowdown，规模继续增加时也没有 admission control。

## 局限与后续工作

- **局限 1**：只评测 140 个手选 perf-const，且明确不支持 memory-layout、DCE 和少数 Kprobe-ambiguous constant。
- **局限 2**：safe span 主要追踪 data dependency；control dependency、异步 kernel work 和外部设备状态没有完整覆盖。
- **局限 3**：Xkernel 不提供 value bound、跨 knob semantic constraint 或最优值搜索，policy correctness 由用户承担。
- **局限 4**：scope table 绑定 exact kernel source、compiler 和 config；闭源 driver 或 binary 更新会阻断复用。
- **局限 5**：安全 transition 可能 timeout，论文没有保证何时一定能找到 safe point。
- **后续工作 1**：在 x86/Arm、多组 compiler optimization 和 kernel 版本上重建 scope table，用“重新编译为目标常量”的 kernel 做 differential execution，比较关键 machine/kernel state。
- **后续工作 2**：把 control dependency、workqueue、timer、RCU 和 device/DMA state 加入 SS 分析，并用 fault injection 检查 transition 前后 invariant。
- **后续工作 3**：为 Xk-tune 加 machine-checkable range、跨 knob constraint、signed policy 和 canary rollback；用 crash、deadlock、starvation 与 SLO regression 作为客观判据。
- **后续工作 4**：扫描整个 Linux source 自动发现候选 perf-const，报告接受、拒绝和人工误分类比例，而不只在预选 140 个上计算覆盖率。

## 相关

- **相关概念**：[[eBPF]]、[[Kernel-Live-Patching]]、[[Dynamic-Software-Update]]、[[Operating-System-Tuning]]
- **同类系统**：[[Kprobe]]、[[Kpatch]]、[[Ksplice]]、[[sysctl]]
- **同会议**：[[OSDI-2026]]
