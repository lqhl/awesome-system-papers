---
type: paper
name: Blink
full_title: "When Sampling Lies: Trustworthy Performance Profiling for Flat Workloads with Blink (Operational Systems)"
authors: [Rishikesh Devsot, ChenXing Yang, Yi Fan Yu, Prabhdeep Singh Soni, Afshin Arefi, Bryan Chan, Reza Azimi, Ding Yuan]
venue: OSDI
year: 2026
tags: [profiling, performance-counter, mobile-systems, instrumentation, compiler]
source_pdf: "[[osdi26-devsot.pdf]]"
source_md: "[[osdi26-devsot]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Blink：当采样结果会说谎，如何可信地分析 Flat Workload（OSDI 2026）

> **原题**：When Sampling Lies: Trustworthy Performance Profiling for Flat Workloads with Blink (Operational Systems)

> **一句话总结**：Huawei 的手机 workload 由数千个短函数平均分摊成本，perf 不仅覆盖不足，还会因 skid 与 shadow effect 稳定地把事件归错位置；Blink 改在函数 entry/exit 直接读取 PMU，并用每函数限额和 self-patching 控制 tracing，在一个受限的 dynamic-instruction ground-truth 实验中超过 99.999% 记录完全正确，在 12 个 workload 上平均覆盖 96%，但目前只用于 rooted ARM64 测试手机，不能测 JIT code，也没有证明 production worst-case overhead。

## 问题与动机

传统 profiler 假设少数热点函数占据大部分执行时间。对这种 profile，perf 每隔一段 PMU event 采一个 instruction pointer，即使漏掉很多短函数，也能找到主要 bottleneck。Huawei HarmonyOS compiler 团队面对的工作负载不同：`render_service` 会调用数千个短小 routine，整体成本比较平，单个编译优化只有约 1% 也值得追踪。工程师需要知道“某个函数到底少了几条 instruction、几个 cycle”，而不只是大致热点。

论文的触发案例是 ARM Large System Extension Optimization（LSEO）。优化前，atomic decrement 使用 `ldaxr/sub/stlxr/cbnz` retry loop；优化后换成 `mov + ldaddal`。静态上 4,006 个位置都正确改写，perf record 却持续报告 `librender` dynamic instructions 增加约 6%、即 90M。团队花了数周排查，最后用 whole-process `perf stat` 看到总 instruction 实际减少 13M、约 0.4%（§2.2）。

更细的图 1 显示：sampling 把 `librender` 记成增加 30.9M，同时两个未改变、但会调用它的 library `librender_server + ld-musl` 被记成减少 38.7M。总量方向正确，归属位置却错了。这样的 profiler 比“方差大”更危险，因为重复运行仍会得到稳定的错误方向。

## 关键观察 / 隐含假设

- **观察 1：skid 加 shadow effect 会产生有方向的 bias。** ARM PMU overflow interrupt 不能精确停在触发 event 的 instruction，记录 IP 会向后滑；长延迟 `ldaddal` 又长期占据 reorder buffer head，挡住后续 retirement，缩短 skid window，使 sample 更容易落在它附近（§2.2）。
  - **为什么平均不能修好**：skid 不是独立、零均值 noise；instruction latency 改变了 sample 被吸向哪里的分布。
  - **适用边界**：Intel PEBS 和 AMD IBS 的 precise instruction-count sampling 可以解决该案例；Kirin 9000S 没有 ARM SPE，而论文认为 SPE 的 micro-op sampling 对这种长 micro-op instruction 仍可能有偏。
- **观察 2：flat profile 下，coverage 比 sample 总数更重要。** 12 个 workload 中，perf 4 kHz 平均只看到 54% unique functions，30 kHz 也只有 62%；Blink 平均 96%（§2.3、图 2）。
  - **注意口径**：62% 对应 **30 kHz**，不是 40 kHz。另一个 40 kHz 实验只说明请求频率提高 10× 时，sample 实际约增 7×，因为 perf 默认把 CPU overhead 控制在 25% 以下而自动 throttle。
- **观察 3：sampling interrupt 会改变被测系统。** 作者不能同时用 perf 占用 PMU register 并测 L1D miss，因此用 4 kHz timer interrupt 作为 proxy；`read_random()` 的 L1D miss 增加 15–46×（§2.4、图 3）。
  - **证据边界**：这是 interrupt cache-pollution 的受控代理实验，不是“40 kHz perf 直接测出 46×”。调度迁移和 contention 变化主要是论文的工程观察。
- **观察 4：直接在 program point 读 PMU 能消除 interrupt attribution error，但 PMU read 自身也会重排。** Blink 在测 dynamic instructions 时可在读 counter 前加 ISB，并在 post-processing 扣除固定 44 条 instrumentation instruction（§3.2）。
  - **隐含假设**：ISB、offset correction 和 instrumentation 本身不会改变目标函数控制流；其他 PMU event 默认不用 ISB，也没有 ground truth 校正。
- **观察 5：tracing 必须把高频函数的成本封顶。** 每个 thread、每个 function、每个 `T` ms 最多收集 `N` 次 invocation；默认评测为 `N=30, T=400 ms`（§3.1、§4）。
  - **可能失效场景**：只收每个 interval 的前 `N` 次会偏向 phase 开头；若后半 interval 行为不同，样本未必代表全段。
- **假设 1：工程师能预先确定要 instrument 的 binary/region。** Blink 擅长确认 compiler A/B 和分析短 frame window，不是无需先验的全系统 discovery profiler。
- **假设 2：可修改 binary 与 executable text。** Self-patching 需要 rooted、unlocked phone；production end-user device 没有这个权限（§6）。

## 核心方法

### 1. 在 entry/exit 直接记录 PMU

Blink 默认给每个函数的 entry 和所有 exit 插 trace point，也允许用户指定任意 basic block。每次 trace point 记录 `<tpID, PMU value>` 到 thread-local buffer；post-processing 配对 entry/exit，取 counter 差值得到该次调用的 dynamic instructions、cycles 或 cache event，并能生成 flamegraph（§3）。

`fID` 标识函数，`tpID` 标识某个具体 entry/exit；一个函数可能有多个 exit，recursion 中也要靠 trace-point 序列正确配对。简单的 entry–exit 差值包含全部 callee，论文称为 tree measurement；要得到只算本函数的 self measurement，post-processing 会减去已 instrument callee。如果某个 callee 没有 instrument，则需在 call site 前后另插 trace point；很短的 helper 可以显式排除，避免开销过大（§3.3）。

### 2. MIR placeholder 避免影响 compiler optimization

若很早在 compiler IR 中插完整 tracing call，可能改变 inlining、instruction scheduling 或后续优化，导致“instrumented binary 已不是原来的 binary”。Blink 在主要优化完成后的 Machine Intermediate Representation（MIR）阶段只插 placeholder；MIR lower 到 assembly 时才替换成手写 AArch64 snippet（§3.4）。

Snippet 只保存 `x0, x1, x8, x16, x29, x30`，构造 `FData*` 与 `tpID` 两个参数，再调用 assembly tracing routine。这样比保存完整 caller-saved register set 更轻，但也使实现与 AArch64 ABI、编译链紧密绑定。

### 3. 用 binary rewriting 把 disabled path 降到一个 jump

每个 trace point 第一条 instruction 初始为 `nop`，后面是 13 条 instrumentation instruction。函数收集达到上限时，tracing routine 找到 call site，把 `nop` 改成无条件 `b +13`，直接跳过整个 snippet；disabled path 因此只多执行一条 jump，不需要每次读 shared flag 再 conditional branch（Listing 2–3）。

每次 invocation 通常经过 entry 和一个 exit，所以 counter 以 `2N` 个 trace-point record 为阈值，对应 `N` 个完整样本。Control thread 每 `T` ms 扫 FData，把 `b +13` 改回 `nop`。Buffer 和 per-function counter 都是 per-thread，避免 lock/cache coherence；`fn.disabled` 是少量更新的 shared state。

Blink 初始可以保持全部 trace disabled，收到 signal 后才启动 control thread，允许工程师跳过 process startup。这个机制控制平均开销，却也引入 text patch 的并发、I-cache synchronization、W^X/code-signing 和安全权限问题。

### 4. 处理 PMU ordering、context switch 与固定 offset

CPU out-of-order execution 也可能把 PMU read 移过目标边界。测 dynamic instructions 时，Blink 在每次 PMU read 前可加 ISB；instrumentation 本身会被计入，作者手工算出固定 offset 为 44 instructions，并在 post-processing 扣除。测其他 PMU event 时，默认不加 ISB，也不做这一 offset correction（§3.2、§4）。

PMU counter 属于 CPU core，会跨 context switch 继续增长。Blink 利用 Linux perf subsystem 已有的 save/restore 路径：每个 thread 第一次经过 trace point 时发一次 `perf_event` syscall，让 kernel 后续在切换时保存其 event state。用户态再直接读可用的 PMU counter。Mate 60 Pro 有 8 个 counter，作者经验上前 5 个被 kernel reserve，默认用 index 5，并提供脚本探测其他配置（§3.4）。

### 5. Thread-local buffer 与 OpenHarmony 适配

每条 record 为 16 bytes。§3.4 说默认 buffer 是 10,000 records、即 160 KB/thread，约每 100 ms flush 一次。OpenHarmony 当时没有 native TLS，调用 `pthread_get_specific` 的 emuTLS 较慢；Blink 第一次查到指针后，把它缓存到 reserved register，避免每个 trace point 都查 TLS。

这里论文内部有两个需要注意的口径问题：§4.2 的 memory 实验又称“default buffer size”为 100K elements，与 §3.4 的 10K 不一致；其报告的 memory overhead mean 417.9 KB、median 1,339.6 KB、max 5,666 KB，非负样本通常不应出现 mean 小于 median。没有原始数据，无法判断是配置差异、baseline subtraction 产生负值，还是文字/统计错误。

## 设计取舍

- **Tracing 换 attribution correctness。** Blink 不依赖 PMU interrupt 的 delayed IP，能覆盖短函数；代价是每个被收集 trace point 执行约 140.9 instructions、38.7 cycles，还会改变 branch、I-cache、register 和 timing。
- **限额换 bounded overhead。** `N/T` 防止热点函数无限 trace，也优先覆盖 rare function；代价是 first-`N` phase bias，且共享 disable timing可能让不同 thread 收到的样本不均。
- **编译期 instrument 换精确边界。** MIR placeholder 尽量保留 optimization decision，但要求有 compiler/binary cooperation，无法直接处理闭源、interpreted 或 JIT-generated code。
- **按需 target 换较低成本。** 工程师可以只 include 目标函数，在 8.33 ms frame window 内收精细 counter；它不能独立发现应该先看哪个模块。
- **Self-patching 换近零 disabled overhead。** 一条 unconditional branch 很便宜，却需要修改 executable code；root、W^X、CFI、code signing 和多核 instruction-cache consistency 都进入 trusted implementation。
- **ISB 只用于 DI。** Dynamic instruction 有 ground truth 和 44-instruction correction；cycles/cache 等 event 没有同等严格验证，不能把 DI 的 99.999% 直接推广给所有 PMU event。

## 实验设计

所有主要结果来自一台 Huawei Mate 60 Pro：OpenHarmony 0324、KIRIN 9000S，包含 1×2.62 GHz Cortex-A710、3×2.15 GHz Cortex-A710、4×1.53 GHz Cortex-A510 和 12 GB memory。主要目标是 `render_service`；test suite 有 Camera/Browser 的 12 个用户交互 workload，除非另说取 10 次平均。默认 Blink sampling mode 为每 thread/function 每 400 ms 最多 30 个样本。

Correctness 实验从 `librender` 选 1,112 个没有 branch 和 call 的 straight-line function，因此静态 instruction count 就是每次调用的 ground truth；C/LPV 连跑 100 次。Overhead 使用 gallery swipe 的 jank distribution、10M 次 microbenchmark 和 12 workload 的 RSS high-watermark。Utility 则用 compiler flag auto-tuning、frame anomaly triage、LSEO 复核和 12-test integration 四个案例。

## 实验与结果

- **99.999% 是一个严格但窄的 DI 结果。** 1,112 个静态候选中只有 157 个实际被调用；约 177M 次 invocation 里只有 568 条、少于 0.001% 与 ground truth 有任何偏差，其余完全一致。这个数字使用 straight-line functions、ISB 和 44-instruction correction。去掉 ISB 后，157 个函数的平均误差为 −3.12 instructions，95% CI 为 `[−5.38, −0.86]`（§4.1、图 4）。
- **用户可见开销只在一个 jank workload 上接近 1 个百分点。** C/LPV 10 次运行中，Jank0（按时完成的 frame）从 baseline 65% 变成 Blink 64%；其他 jank level 分布也接近。论文称这在通常少于 2% 的可接受 margin 内。Microbenchmark 中每个 collected trace point 平均执行 140.9 instructions、花 38.7 **cycles**，不是 38.7 ns（§4.2、表 1）。
- **覆盖率显著高于 perf。** 12 个 workload 上 Blink 覆盖 94%–97%、平均 96% unique functions；perf 4 kHz 平均 54%，30 kHz 平均 62%。剩余 3%–6% 多为 MIR instrumentation 之后才由 linker/compiler 生成、使用特殊 ABI 的 helper/stub（§2.3、§4.3.4、图 2）。
- **Auto-tuning 的主要收益是少重复运行。** 对 80 个受 compiler flag 影响的关键函数，perf 的 per-function cycle difference 要 50 次或更多 run 才稳定，Blink 约 2 次就稳定；实验把 repeat count 从 2 扫到 100。这支持 ML compiler tuning 的反馈成本优势，但论文没有给完整 end-to-end training-hour speedup（§4.3.1、图 5）。
- **两个 case study 说明 utility，也暴露不能到达的边界。** Frame anomaly 中，Blink 在单个 8.33 ms VSync window 发现 `libArk.execute` 时间增加 10%，把问题缩到 app/runtime，而不是完整 root-cause；其 JIT callee 使用特殊 ABI，Blink 无法继续 instrument。LSEO case 中，目标 `update` 有 26 个优化机会，perf 说 DI 增 20%，Blink 测得每次调用平均从 352.8 降到 349.8、即少 3 条（§4.3.2–4.3.3、表 2）。
- **Cycle comparison 有相关性，没有 ground truth。** 在两个 app、12 个 test 中，Blink 与 perf 对长函数的总 cycle 趋于一致；8/12 test 是 perf 标准差更大，只有 B/OFN 明确是 Blink 更大。9/12 regression 有正 intercept，作者认为是每个 trace point 的 38.7-cycle overhead未扣除。所有 `R²` 较高，但论文明确承认 true cycle count 未知，因此不能据此证明 Blink 的 cycle 值严格正确（§4.3.4、图 6、表 3）。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| perf sampling 在 flat workload 上可能稳定地给错 attribution 方向 | LSEO：`librender` +30.9M，两个 caller library −38.7M，whole process 实际 −13M | 单一 ARM atomic optimization、KIRIN 9000S、perf record 4 kHz | 强 |
| 单纯提高 sampling rate 不能获得完整覆盖 | 图 2：4 kHz 54%，30 kHz 62%，Blink 96% | 12 个 Huawei Camera/Browser workload | 强 |
| Blink 的 DI read 在受控条件下高度准确 | 177M straight-line invocation，仅 568 条有偏差 | 157 个实际执行函数；ISB+44 instruction correction；只验证 DI | 强 |
| Blink 对用户可见 jank 的扰动较小 | 表 1：Jank0 65%→64%，分布相近 | 单手机、单 C/LPV workload、10 runs；不是 production worst case | 中 |
| Blink 能缩短 compiler profiling 反馈 | 图 5：约 2 runs 稳定，对 perf 需 50+ | 80 个函数、一个内部 auto-tuning setting | 中 |

## 批判性分析

### 论证链条

论文最有价值的部分不是“又做了一个 tracing profiler”，而是给出一次 operational failure 的完整证据链：静态二进制确认优化已发生，whole-process counter 确认总数下降，library attribution 却向相反方向移动，再用 caller/callee 与 long-latency atomic 解释 sample 迁移。它说明 sampling error 可能是结构性 bias，重复 50 次只会更相信错误均值。

Blink 的回答也直接：把 event observation 移到明确 program point，从机制上绕开 interrupt IP attribution；再用 self-patching 与 `N/T` cap 控制 tracing。MIR placeholder、context-switch PMU save/restore、emuTLS cache 和 PMU register probing 显示它不是概念原型，而是为 Huawei 编译链做过完整工程集成。

### 假设压力测试

Blink 仍有观察者效应。38.7 cycles 对长函数小，对只有几十个 cycle 的函数可能比目标本身还大；extra branch、stack write、PMU read、ISB 和 buffer store 都可能改变 cache、branch predictor、contention 和 scheduler。DI 可以扣固定 44 instructions，cycle/cache interference 却很难统一扣除。

每 interval 只收前 `N` 次调用，在稳定 compiler benchmark 中合理；对 startup、warmup、[[Garbage-Collection|GC]]、thermal throttling 或交互 phase 明显的 workload，前 30 次不一定代表之后。Patch 是 function-level shared state，而 counters 是 per-thread；某 thread 先打满阈值会改变其他 thread 的采集机会，论文没有分析 sampling fairness 或 race 的误差。

Precise hardware 也改变比较结论。Intel PEBS/AMD IBS 能解决论文的 instruction-count skid case；Blink 的优势仍包括 coverage 与任意 PMU boundary，但论文没有在这些平台画 accuracy–coverage–overhead curve。Kirin 9000S 又没有 SPE，所以外部有效性主要是“没有 precise sampling 的 ARM 手机”。

### 实验可信度

Ground truth、user-visible jank、coverage、真实误诊与四个 use case 组合得很好。尤其作者没有把 cycle regression 当 ground truth，也明确说 frame case 只 triage 到 libArk。这些边界增强了可信度。

但 99.999% 只能用于“straight-line function 的 dynamic instruction count，启用 ISB 和 offset correction”，不能扩展到 cycles、cache misses、带 branch/call 的复杂函数或 end-to-end profile。Abstract 的“1% overhead”主要落在 C/LPV Jank0 减少 1 个百分点；§6 反而明确说 production profiler 仍需证明 worst-case 维持 1%–2%。它现在只在 testing/development 使用。

Cache 15–46× 来自 4 kHz timer proxy，不是 perf 同时直接测量。Coverage 的最高实测 rate 是 30 kHz；40 kHz 是独立 throttle 观察。把这些实验揉成“40 kHz perf 导致 46×、仍只有 62%”会超过论文证据。

Memory 数字和 buffer default 在正文内部不一致：10K records vs 100K elements，且 mean 417.9 KB 小于 median 1,339.6 KB。原始数据和计算方式未给出，因此只能保留论文原数，不能据此建立可靠的 memory scaling model。

### 系统性缺陷

Self-modifying executable code 要处理多核 patch atomicity、instruction-cache coherence、signal/reentrancy、thread exit 和 crash；论文解释了 fast path，但没有系统 fault-injection。Root/unlocked 权限与 W^X、CFI、code signing 冲突，使它暂时不能下放到 end-user production device。

Blink 只 instrument compiled ARM64 binary。Frame case 已实际撞到 JIT/nonstandard ABI 的墙；link-time helper 也造成剩余 coverage 缺口。它需要 engineer 选择 target 或 include/exclude list，因此最好与低开销 discovery profiler 配合：先找模块，再用 Blink 做短函数 attribution。

Per-thread buffer 的 memory 随 thread count 增长，flush I/O、buffer overflow 和 multi-process aggregation 没有成为主要评测。其他 architecture 还需重写 hand-written assembly 和 PMU/context-switch integration，不是简单重新编译。

## 局限与后续工作

- **局限 1**：只在一款 KIRIN 9000S/ARM64 手机和 Huawei 编译链上深入评测，跨 hardware/OS 外部有效性有限。
- **局限 2**：99.999% 只覆盖 straight-line DI+ISB+offset；其他 PMU event 和真实复杂函数没有 ground truth。
- **局限 3**：目前只用于 testing/development；root/self-patching 不适合普通 end-user device，production worst-case 1%–2% 尚未验证。
- **局限 4**：不能 instrument interpreted/JIT code、special ABI stub 和部分 link-time helper，也不能代替全系统 target discovery。
- **局限 5**：Buffer 配置和 memory 统计在正文内部不一致，per-thread scaling、flush/overflow 与 crash behavior 缺少数据。
- **后续工作 1**：在 Intel PEBS、AMD IBS、ARM SPE 与无 precise sampling 的 ARM 上运行同一 flat benchmark，统一比较 direction error、coverage、cache perturbation 和 jank。
- **后续工作 2**：按函数 duration、thread count、`N/T`、ISB 与 trace-point 数量画 accuracy–overhead surface，给出 Blink 的 break-even 条件。
- **后续工作 3**：设计 phase-aware 或 reservoir sampling，避免每个 interval 只取前 `N` 次，并检验多 thread shared-disable 的公平性。
- **后续工作 4**：实现符合 W^X/CFI/code-signing 的 patching，注入 concurrent patch、signal、thread exit、buffer full 和 process crash。
- **后续工作 5**：与 runtime profiler 协作覆盖 JIT code，并把 sampling discovery→Blink targeted tracing 形成自动两阶段 workflow。

## 相关

- **相关概念**：performance profiling、hardware performance counter、binary instrumentation、observer effect
- **相关工具**：perf、[[eBPF]]、XRay、Hubble、ARM SPE、Intel PEBS、AMD IBS
- **同会议**：[[OSDI-2026]]
