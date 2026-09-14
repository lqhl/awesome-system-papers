---
type: paper
name: MUSCHED
full_title: "Surviving the Impossible Trinity: Revisiting CPU Scheduling Problem on Modern COTS Mobile Devices"
authors: [Jun Xiao, Qinhui Gu, Ligeng Chen, Lizhi Sun, Zicheng Wang, Yinggang Guo, Lu Liu, Hao Wu, Borui Li]
venue: OSDI
year: 2026
tags: [mobile-systems, cpu-scheduling, android, ebpf, interactive-qoe]
source_pdf: "[[osdi26-xiao.pdf]]"
source_md: "[[osdi26-xiao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-15
---

# 在“不可能三角”中维持交互响应（OSDI 2026）

> **原题**：Surviving the Impossible Trinity: Revisiting CPU Scheduling Problem on Modern COTS Mobile Devices

> **一句话总结**：MUSCHED 认为移动交互同时受限于稀缺的 prime core、跨进程依赖和 8.3 ms 的 120 Hz 帧预算，因此用介于 RT 与 CFS 之间的 VIP 调度类、跨锁与 Binder 的优先级传播以及基于 eBPF 的用户态策略更新，将 10 个应用的平均冷启动时间降低 14.8%，并在超过 2,000 万台设备上把冷启动异常降低 30.7%。

## 问题与动机

Android 调度器主要依据线程、历史 CPU 利用率和 cgroup 等低层信号做决策，却不知道一次触摸、启动或滑动操作的端到端关键路径。UI 线程可能只运行很短时间，大部分时间在等待 Binder 服务或锁；依赖它的服务线程却可能处于低优先级或受限 cgroup 中。局部线程的“公平”会转化为用户可见的卡顿。

移动 SoC 还只有少数高性能核心，并受功耗与温度限制。120 Hz 屏幕每帧只有 8.3 ms，交互负载又具有突发性。RT 类过于强硬，可能饿死系统服务；CFS 类过于保守，难以及时处理短暂的交互突发。论文将这三项约束概括为移动调度的“不可能三角”。

## 关键观察 / 隐含假设

- **观察 1：交互延迟常由跨进程依赖决定，而非调用方本身的运行时间决定。** 图 1 展示了高优先级主线程同步等待低优先级远端线程的优先级反转；Android 既有的本地锁继承不会自动覆盖 Binder 路径或跨 cgroup 依赖。
  - **依赖假设**：框架能够识别同步 Binder 调用和锁的持有者，并能在依赖结束时撤销提升。
  - **可能失效场景**：异步消息、无法追踪的用户态同步原语、依赖图快速变化或存在循环依赖时，传播可能不完整或扩大优先级竞争。
- **观察 2：历史 CPU 利用率对短生命周期的交互线程反应太慢。** PELT/WALT 等历史统计可能把等待中的关键线程视为低负载；等调度器观察到负载并迁移或升频时，帧预算已经消耗。
  - **依赖假设**：交互关键线程可以由 Android 角色、离线 systrace 和线上 jank trace 稳定标注。
  - **可能失效场景**：新应用、应用版本变化、长尾交互路径或标注错误会导致关键线程漏标或误标。
- **观察 3：并非所有高刷新率工作负载都能从语义调度获益。** 论文在大型 MOBA 游戏中观察到，线程切换规律稳定，瓶颈转向功耗和热约束；MUSCHED 对平均 FPS 和帧时间变化没有统计显著影响，电流与机身温度还略有变差。

## 核心方法

MUSCHED 将用户态策略与内核执行分开。用户态控制器从 SystemUI、Launcher、前后台切换、焦点变化和帧回调等 hook 获取场景信息，通过 eBPF maps 更新策略；内核侧用 `sched_ext` 实现每个 CPU 的 VIP 队列。RT 任务仍优先于 VIP，VIP 再优先于 CFS。

VIP 是一种临时、受限的优先级提升。任务按 FIFO 排队，每次运行 3 ms；不同场景有总预算，例如 audio 20 ms、video 10 ms、WebView 120 ms、display 20 ms。预算用尽后任务回到 CFS，避免 VIP 任务无限占用 CPU。这回应了交互突发和 RT 稳定性之间的冲突。

场景感知标注首先使用通用角色，如 main/UI thread、RenderThread、MotionThread 和 Binder worker；随后用离线关键路径分析补充应用专属线程，再用线上 jank trace 修正漏标。标注只在启动、滑动、动画等交互状态激活。

优先级传播处理两类依赖。对于 futex、mutex 和 rwsem，内核记录锁持有者；VIP 线程阻塞时，临时提升持有者并在释放或依赖消失后撤销。对于同步 Binder 调用，MUSCHED 找到远端服务线程并传播 VIP 标记。这样优化目标从单线程扩展为交互关键路径。

为适配 COTS Android，作者扩展 `bpfloader` 以在启动阶段加载 `struct_ops` 对象，并通过状态机和 `BPF_F_LINK` 管理 `sched_ext`。论文指出 eBPF verifier 的栈、循环、内存和控制流限制，因此把复杂逻辑封装到 kernel kfunc，将 eBPF 保持为薄控制面。

## 设计取舍

- **收益与公平性的取舍**：VIP 可抢占 CFS，但通过 3 ms 时间片和场景预算限制持续占用；预算和阈值依赖 profiling，跨应用迁移成本较高。
- **灵活性与实现边界的取舍**：eBPF 允许不重编译 kernel 更新策略，但 Android 仍要求启动时加载程序，且复杂逻辑需要 kfunc 等内核扩展，并非完全用户态。
- **响应与功耗的取舍**：VIP 优先选择性能核心并在 VIP runnable 超过 4 ms 时触发迁移。该阈值约为半个 120 Hz 帧预算，但更积极的迁移可能增加功耗和热压力。

## 实验与结果

- 在 Snapdragon 8 Elite、Android 15、MagicOS 9 的 Magic 7 上，用 10 个热门应用、每个应用 100 次冷启动与原生 Android 调度比较，平均冷启动时间降低 14.8%，标准差降低 24.25%（图 4）。
- VIP 线程在冷启动中的不可中断睡眠时间和 runnable 等待时间均下降（图 5、图 6），与“减少资源等待和调度等待”的机制解释一致。
- 在后台 PiP 视频通话与前台交互并存时，四类场景的前台响应延迟降低 9.8%–22.8%（表 3）。
- 短视频场景中 context switch 平均延迟保持 5 µs，pick-next-task 延迟由 2 µs 增至 3 µs；游戏 120 FPS 测试的平均帧率基本不变，电流相近（表 4）。
- 超过 2,000 万台设备的生产数据中，冷启动异常降低 30.7%，动画异常降低 25.0%，滑动异常降低 35.7%；异常定义分别为冷启动超过 2 s、连续掉帧超过 50 ms（表 5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 语义标注和 VIP 调度能降低交互启动延迟 | 平均冷启动降低 14.8%，图 4；睡眠与 runnable 等待下降，图 5–6 | 单一 Snapdragon 8 Elite 实验机、10 个应用 | 强 |
| 跨锁与 Binder 的传播能缓解关键路径阻塞 | 冷启动等待时间下降，图 5–6；四类 PiP 混合场景降低 9.8%–22.8%，表 3 | 未分别报告 Binder、锁传播的独立贡献 | 中 |
| 方案能在 COTS 设备上维持低运行时开销 | context switch 5 µs 不变，pick-next 2→3 µs，表 4 | 短视频和单款游戏；未给出更多 SoC 的微基准 | 中 |
| 方案具有生产环境收益 | 2,000 万台设备，冷启动/动画/滑动异常分别降低 30.7%/25.0%/35.7%，表 5 | 观测性生产数据，缺少随机化实验、置信区间和分层信息 | 中 |

## 批判性分析

### 论证链条

从“调度器缺少交互语义”到“标注关键线程并传播依赖”的逻辑是闭合的，图 1 给出了优先级反转的具体机制。实验也测量了 VIP 线程的等待时间，而不只报告端到端时间。可是，论文没有提供标注准确率、关键路径覆盖率，或 Binder 传播与锁传播的独立消融，因此无法判断收益主要来自哪一部分。

### 假设压力测试

方法依赖场景识别和线程标注的稳定性。应用更新、厂商定制框架、异步化 IPC 或新的运行时线程模型都可能使离线 profiling 过时。跨进程传播还需要正确处理依赖生命周期；论文未讨论循环依赖、恶意或错误标注策略，以及多个 VIP 场景同时发生时的预算组合。

### 实验可信度

实验固定了显示模式、热状态、电池模式、governor 和清缓存过程，并使用真实应用与合成背景压力，控制较为完整。生产结果覆盖 Qualcomm 和 MediaTek、多档产品，但论文没有说明部署前后的设备分组、版本差异、用户选择偏差或统计显著性。游戏结果反而说明调度收益强烈依赖工作负载瓶颈。

### 系统性缺陷

VIP 队列、锁 owner 记录、Binder 追踪、框架 hook 和策略 reconciliation 增加了可观测性与运维负担。论文没有详细讨论故障恢复、错误策略回滚、跨版本 ABI 兼容性和安全隔离。eBPF 方案仍需修改 Android `bpfloader` 并在 boot 阶段加载，不能简单视为无需固件协作的通用插件。

## 局限与后续工作

- **局限 1**：实验硬件和应用数量有限；生产数据虽规模大，但缺少可复现的对照设计和按设备、应用、温度分层的统计。
- **局限 2**：VIP 时间预算（如 WebView 120 ms）来自代表性 workload profiling，跨应用泛化和错误标注成本未量化。
- **后续工作 1**：对 VIP 标注、锁传播、Binder 传播、CPU 选择分别做消融，并报告关键路径覆盖率、误标率和 P99 交互延迟。
- **后续工作 2**：在不同 SoC、热状态和电池模式下联合测量 QoE、能耗、温度和频率，验证 4 ms 迁移阈值是否需要自适应。
- **后续工作 3**：设计可验证的循环依赖检测、预算组合和策略回滚机制，明确错误策略对系统稳定性的最坏影响。

## 相关

- **相关概念**：[[eBPF]]、[[sched_ext]]、[[Priority Inversion]]、[[Android]]
- **同类系统**：[[ghOSt]]、[[Syrup]]、[[Orthrus]]
- **同会议**：[[OSDI-2026]]
