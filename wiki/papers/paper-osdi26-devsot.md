---
type: paper
name: Blink
full_title: "When Sampling Lies: Trustworthy Performance Profiling for Flat Workloads with Blink"
authors: [Rishikesh Devsot, ChenXing Yang, Yi Fan Yu, Prabhdeep Singh Soni, Afshin Arefi, Bryan Chan, Reza Azimi, Ding Yuan]
venue: OSDI
year: 2026
tags: [performance-profiling, tracing, pmu, mobile-systems, compiler-optimization]
source_pdf: "[[osdi26-devsot.pdf]]"
source_md: "[[osdi26-devsot]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-14
---

# Blink：让扁平工作负载中的性能剖析可信（OSDI 2026）

> **原题**：When Sampling Lies: Trustworthy Performance Profiling for Flat Workloads with Blink

> **一句话总结**：在数千个短命函数均匀分摊开销的手机渲染工作负载中，perf 的采样会因 skid、shadow effect 和中断扰动而系统性误导优化判断；Blink 在函数入口/出口直接读取 PMU，达到超过 99.999% 的指令计数准确率、96% 的函数覆盖率，并将用户可见的掉帧变化控制在约 1%。

## 问题与动机

Huawei 的编译器团队需要判断细粒度编译优化是否真的减少 CPU 周期、动态指令或 cache miss。此类优化的收益可能只有 1%，因此函数级归因必须稳定。传统 perf sampling 更适合寻找长时间运行的热点，却不适合函数执行时间短、函数数量多且开销近似均匀的 flat profile。

论文给出了 LSE 优化的实际反例。该优化把原有的原子重试序列替换成 `ldaddal`，按程序语义应减少指令数；但 perf record 持续报告 `librender` 的指令数增加 6%。直到使用 perf stat 的非采样模式才确认总指令数实际下降。错误结果曾导致工程师进行数周的排查。

## 关键观察 / 隐含假设

- **观察 1：skid 与 shadow effect 会造成有方向性的错误，而非仅增加方差。** 在 LSEO 中，长延迟的 `ldaddal` 阻塞乱序执行窗口，使样本更容易归因到该指令；原先从 `librender` 滑到调用者库的样本被重新吸附到原子指令附近（§2.2，图 1）。
  - **依赖假设**：PMU 采样通过中断记录溢出后的 IP，且目标 ARM 核心不提供足够精确的指令级事件投递。
  - **可能失效场景**：支持 Intel PEBS/AMD IBS 指令计数采样的硬件可能消除该类错误；不同 ARM 微架构的 skid 窗口和长延迟指令行为也可能不同。
- **观察 2：短命函数的采样覆盖率很低。** 在 12 个测试中，perf 4 kHz 只覆盖平均 54% 的函数，30 kHz 也只有 62%；Blink 达到 96%（图 2）。提高采样率还会改变调度和 cache 行为，模拟中断使 L1-D cache miss 增加 15–46 倍（图 3）。
  - **依赖假设**：渲染开销确实分散在大量短函数中，而非集中在少数稳定热点。
  - **可能失效场景**：长函数、低函数数目的服务端工作负载可能仍然适合 perf，Blink 的固定插桩成本也可能变得不划算。
- **假设 1：编译后的 ARM64 二进制可在接近最终机器码阶段插入稳定的入口/出口探针。** 这是 Blink 获得函数覆盖率的基础，但证据强度为中：论文只在 OpenHarmony 的 ARM64 编译链上验证，JIT 代码和非标准 ABI 代码仍无法插桩。

## 核心方法

Blink 在每个函数入口和所有出口插入配对 trace point，直接读取 PMU 计数器并把 `<tpID, PMU value>` 写入每线程缓冲区。后处理通过入口/出口差值计算函数的 tree cost，也可根据嵌套调用关系扣除被调函数得到 self cost。`fID` 标识函数，`tpID` 标识具体探针；两者分离使递归调用能够正确配对。

为限制开销，Blink 使用二进制自修改开关。探针开头的 `nop` 可被改写为跳过后续 tracing 代码的无条件分支；关闭时只留下一个跳转。每线程维护计数器和缓冲区，避免高频共享变量同步。采样模式下，每个线程每个函数在每个时间窗口最多记录 N 次，控制线程周期性重新启用已关闭的探针。

读取指令数时，Blink 可在 PMU 读取前插入 `ISB`，防止读取指令被乱序执行。插桩本身带来固定的 44 条指令偏移，后处理会扣除。实现放在 MIR（机器中间表示）阶段的占位符上，避免更早插桩干扰编译器优化和函数内联。

## 设计取舍

- **准确性换取插桩成本**：入口/出口 tracing 消除了 sampling 的 skid 和 shadow bias，但需要重新编译/重写二进制，且每个探针平均约 38.7 cycles；论文未证明所有生产负载的最坏情况都低于 1–2%。
- **覆盖率换取架构专用实现**：手写 ARM64 汇编、固定 PMU 寄存器和 emuTLS 降低了开销，却使移植到其他 ISA、原生 TLS 环境或不同内核配置需要额外工程工作。
- **自修改换取部署约束**：self-patching 需要 rooted、unlocked 的手机，因此当前只适用于测试和开发环境，不适合直接部署到终端设备。

## 实验与结果

- 在 `librender` 的 1,112 个无分支、无调用直线函数上运行 C/LPV 100 次，累计约 1.77 亿次调用，仅 568 次测量偏离精确 ground truth，准确率超过 99.999%（§4.1）。不启用 ISB 时平均低估 3.12 条指令，95% CI 为 [-5.38, -0.86]（图 4）。
- Mate 60 Pro 的 C/LPV gallery swipe 工作负载中，Blink 的及时帧（Jank0）比无插桩基线下降 1%，处于团队可接受的少于 2% 范围内（§4.2，表 1）。
- 12 个工作负载的常驻内存高水位平均增加 417.9 KB，中位数 1,339.6 KB，最大 5,666 KB；主要来自每线程缓冲区（§4.2）。
- 对 80 个受编译器 flag 影响的函数，perf 需要 50 次以上重复运行才趋于稳定，Blink 通常两次运行即可稳定（§4.3.1，图 5）。
- 在 `update` 函数的 26 个 LSEO 机会中，Blink 测得每次调用平均减少 3 条动态指令；这与 perf 报告的 20% 增加相反（§4.3.3，表 2）。跨 12 个测试，Blink 覆盖 96% 函数，perf 至多 62%；8/12 个测试中 perf 的标准差更高（§4.3.4，图 2、图 6、表 3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| perf 在 flat profile 中可能系统性误导指令归因 | LSEO 前后 `librender` 与调用者库的反向变化（§2.2，图 1） | Kirin 9000S、OpenHarmony、ARM64、render_service | 强 |
| Blink 能精确读取函数级动态指令 | 约 1.77 亿次调用中准确率超过 99.999%（§4.1） | 直线函数、C/LPV、ISB 开启 | 强 |
| Blink 提供更高覆盖且重复运行更少 | 覆盖率 96% 对比 62%；两次对比 perf 的 50+ 次（图 2、图 5） | Huawei 12 测试、编译器调参场景 | 中 |
| Blink 的用户可见开销较低 | Jank0 下降 1%，内存平均增加 417.9 KB（表 1） | 开发测试环境，非终端生产设备 | 中 |

## 批判性分析

### 论证链条

从采样归因机制到 LSEO 反例，再到插桩设计，论文的主要链条是闭合的。Blink 的准确性由可计算的直线函数 ground truth 支撑。对复杂函数的可信度主要来自更高覆盖率、更低跨运行方差和工程案例，而不是全面的独立 ground truth。perf 与 Blink 的周期回归只能说明一致性，不能单独证明 Blink 绝对正确。

### 假设压力测试

实验集中在一款 ARM64 手机、OpenHarmony 和 render_service。不同 PMU 实现、核心频率变化、线程迁移、极短函数密集调用都可能改变插桩开销和计数器行为。Blink 不能覆盖 JIT 生成代码、解释执行代码和非标准 ABI；论文中的 frame jank 案例只能定位到 `libArk` 的 `execute`，无法继续追踪其 JIT callees。

### 实验可信度

直线函数实验的 ground truth 很强，但只覆盖无分支、无调用函数。真实用户体验指标只在 10 次 C/LPV 运行上比较，生产环境的最坏开销未测量。perf 与 Blink 的全套对比缺少已知真值，且 Blink always-on 结果包含未扣除的 38.7-cycle 固定开销。论文没有展示更多手机型号、不同 Android/ARM 实现或更大规模应用的结果。

### 系统性缺陷

自修改代码需要权限和指令缓存一致性处理，控制线程重新启用探针也引入运维复杂度。固定大小的每线程 buffer 在高线程数下会放大内存占用。PMU counter 选择依赖设备经验配置，内核保留计数器或权限策略变化可能使用户态读取失效。故障恢复、探针写入失败、长时间 trace 文件管理和多租户隔离均未讨论。

## 局限与后续工作

- **局限 1**：当前只支持 ARM64 编译二进制，不能直接处理 JIT 或解释型代码，也不能覆盖少量特殊 ABI 函数。
- **局限 2**：只在开发/测试设备上使用。应在不需要 root 的受控机制下评估生产部署，并报告 P99 开销、功耗和长时间运行影响。
- **后续工作 1**：在多个 ARM SoC、Android/OpenHarmony 版本和不同 PMU 事件上，用硬件计数器或静态计数建立 ground truth，验证 Blink 的误差是否仍低于预设阈值。
- **后续工作 2**：为 JIT runtime 提供运行时 trace API，把 native 探针与 JIT code cache 的函数身份和版本绑定，测量 frame-level 延迟而不破坏代码生成。

## 相关

- **相关概念**：[[Performance Profiling]]、[[Hardware Performance Counter]]、[[Flame Graph]]
- **同类系统**：[[Hubble]]、[[XRay]]、[[perf]]
- **同会议**：[[OSDI-2026]]
