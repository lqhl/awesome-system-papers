---
type: paper
name: MUSCHED
full_title: "Surviving the Impossible Trinity: Revisiting CPU Scheduling Problem on Modern COTS Mobile Devices (Operational Systems)"
authors: [Jun Xiao, Qinhui Gu, Ligeng Chen, Lizhi Sun, Zicheng Wang, Yinggang Guo, Lu Liu, Hao Wu, Borui Li]
venue: OSDI
year: 2026
tags: [cpu-scheduling, mobile, ebpf, production-system]
source_pdf: "[[osdi26-xiao.pdf]]"
source_md: "[[osdi26-xiao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# MUSCHED：跨过移动 CPU 调度的“不可能三角”（OSDI 2026）

> **原题**：Surviving the Impossible Trinity: Revisiting CPU Scheduling Problem on Modern COTS Mobile Devices (Operational Systems)

> **一句话总结**：MUSCHED 认为移动交互同时受稀缺高性能核、跨进程依赖和 8.3 ms 级帧期限约束，而内核看不到用户语义；它在 RT 与 CFS 之间加入临时 VIP 调度类，并沿锁和 Binder 传播优先级、用 [[eBPF]] 更新场景策略，在 10 个应用上把平均冷启动缩短 14.8%，上线超过 2,000 万台 Honor 设备后把启动、动画和滑动异常分别降低 30.7%、25.0% 和 35.7%。

## 问题与动机

移动设备看重的是交互是否及时，而不只是总吞吐。120 Hz 屏幕每 8.3 ms 就要产出一帧；一次点击或启动又会突然唤醒 UI、RenderThread、SystemUI、Binder service 等一串短任务。高端 SoC 只有少量最快的核心，还受功耗和温度限制，因此调度器不能简单为所有任务加速。

现有 Android 调度抽象有一个语义缺口。CFS 根据历史 CPU 使用量追求公平，刚被触摸事件唤醒的短任务还没有积累足够负载；RT 可以立即抢占，却可能让复杂应用线程饿死系统服务。Android 在用户态调整 cgroup 和 nice 值，也只能提高已知线程本身，无法看到它正同步等待另一个进程的 Binder worker 或锁持有者。

论文把这三个约束称为“不可能三角”：高性能核稀缺、关键路径跨进程、期限很紧。它们会互相放大——即使 UI 线程优先级很高，只要远端低优先级任务长时间处于 runnable 状态，UI 线程仍会睡眠等待，最终错过整帧。MUSCHED 的目标是把“当前交互路径是否关键”变成一等调度目标，同时让优先级提升短暂、有界，而且能在已经售出的商用设备上更新策略。

## 关键观察 / 隐含假设

- **观察 1：交互延迟常来自依赖任务没有及时获得 CPU，而不是调用者自身算得慢。** 图 1 展示高优先级 main thread 发起 IPC 后睡眠，远端 `prio=120` 任务长时间 runnable；给远端传播 VIP 后，调用者更早醒来（§2.3，图 1）。
  - **依赖假设**：系统能在锁与同步 Binder 路径上准确找到当前阻塞者，并在依赖结束后及时撤销提升。
  - **可能失效场景**：异步消息、GPU/存储/网络等待、用户态自定义同步或很深的动态依赖图，不一定能由现有 hooks 表达。
- **观察 2：RT 与 CFS 之间确实缺少一个“强于普通任务但不能压过系统关键任务”的等级。** MUSCHED 让 RT 先运行、VIP 次之、CFS 最后，并以 3 ms time slice、场景总预算和 4 ms 迁移阈值限制 VIP（§4.1–§4.2）。
  - **依赖假设**：被标注任务对当前用户体验的价值高于同期普通任务；20 ms audio、10 ms video、120 ms WebView、20 ms display 等预算能代表真实需求。
  - **证据强度**：中。预算来自代表性 profile，但论文没有给出阈值消融或最坏公平性结果。
- **观察 3：关键路径标签既有跨应用共性，也有应用特例。** main/UI、RenderThread 和 Binder pool 可作为默认候选；离线 systrace 找应用专属线程，beta 用户的 jank trace 再补受控实验没覆盖的情况（§4.3，表 1）。
  - **依赖假设**：框架 hooks 能识别 app launch、focus、动画和 frame callback 的开始与结束，且后续应用更新不会让标签快速失效。
  - **可能失效场景**：未知应用、混合前后台媒体、游戏或错误标注过多线程时，VIP 队列本身会变成争用点。
- **假设 1：商用设备需要更新“策略数据”，但底层调度机制可以随系统镜像固定。** Android 只允许 `bpfloader` 在启动时加载 eBPF；MUSCHED 扩展它以支持 `BPF_MAP_TYPE_STRUCT_OPS`，运行时主要通过 BPF maps 和状态机切换策略（§5）。
  - **证据强度**：强于“每次改策略都重编内核”，弱于“完全不需内核改动”。初次部署仍修改 bpfloader、sched_ext 集成和 kfunc，不能当作普通应用更新。

## 核心方法

MUSCHED 使用“用户态决定语义、内核快速执行”的分层结构。用户态 policy library 保存每个场景要提升的线程类别、VIP 有效期等配置，通过 eBPF map 传给内核。Android framework 在应用前后台切换、focus 变化、Launcher/SystemUI 动画和 frame rendering 回调处打 hooks，进入交互阶段时给相应线程加 VIP 标签；没有标签的线程继续走原生路径（§3，图 2）。

内核侧在 RT 与 CFS 之间实现 VIP class，并为每个 CPU 建立 VIP dispatch queue。唤醒任务时，调度器先找空闲大核，再找没有 RT/VIP 的核，最后选无 RT 且 VIP 最少的核。CPU 空闲时可从其他核偷取 VIP；若一个 VIP 已 runnable 超过 4 ms，tick 路径也会尝试迁移，避免它在 120 Hz 半帧时间后仍排队（§4.1，图 3）。

VIP 并不是永久高优先级。每个任务按 FIFO 获得 3 ms time slice；只要没有耗尽场景总预算，就可重新排到队尾，耗尽后暂时去掉 VIP 并回到 CFS。不同工作负载使用不同预算。这个设计既保护 RT，又给普通任务留下运行机会；代价是预算选择进入产品策略，过短会丢失收益，过长会破坏公平和能耗（§4.2）。

语义标注解决“谁重要”，优先级传播解决“重要线程在等谁”。当 VIP waiter 阻塞在 futex、mutex 或 rwsem 上时，hook 记录并找到 lock owner，临时把 VIP 传给 owner；VIP waiter 还可在锁等待队列中越过普通 waiter。owner 解锁、依赖消失或提升超时后，继承标签被撤销。对于同步 Binder，MUSCHED 在 transaction 开始时提升远端 service thread，调用返回后恢复普通优先级（§4.3）。

实现建立在 Linux `sched_ext` 的 `sched_ext_ops` 上：`sched_select_cpu` 选大核，`sched_enqueue` 放入高优先级 DSQ，`sched_dispatch` 先消费本地 VIP、再尝试邻核 VIP。`cpu_contexts` 和 `task_contexts` 两类 eBPF maps 保存每核与每任务状态。因为 Android 原生 bpfloader 不支持 sched_ext 需要的 struct_ops，作者扩展 loader，并用 `INIT`、`INUSE`、`TOBEFREE`、`READY` 状态与 `BPF_F_LINK` 控制一次加载后的安全启用（§5）。

## 设计取舍

- **临时不公平换取可感知延迟**：VIP 可抢占 CFS、锁 waiter 可越过 FIFO，这直接缩短交互关键路径，但会改变普通任务的等待顺序；time slice 和总预算只是经验性保护，并非严格公平性证明。
- **语义标签换取可解释性**：明确标出 UI、render、Binder 等角色，比仅看历史负载更早行动；维护应用专属标签、处理版本变化和误标则需要持续运营。
- **传播优先级换取端到端加速**：锁与 Binder 提升消除常见 priority inversion，但增加 kernel bookkeeping，也可能把错误标签沿依赖放大。
- **策略可热更新换取底层定制**：设备不必因每个 app 策略重编内核或重启；然而第一次支持仍需要厂商修改 bpfloader、引入 sched_ext 与 kfunc，移植门槛高于普通 eBPF 程序。
- **性能优先但未联合控制频率**：MUSCHED 选择合适核心，却没有统一管理 DVFS。论文自己的经验指出，高性能核若被降频仍无法满足期限，激进选核也可能浪费电（§7.2）。

## 实验与结果

- **实验室冷启动**：Magic 7、Snapdragon 8 Elite（2 个 4.32 GHz super cores、6 个 3.53 GHz performance cores）、MagicOS 9 / Android 15 / Linux 6.6 上，10 个热门应用各运行 100 次，并固定显示、温度、电池、governor 与清缓存流程。相对 Android 原生调度，平均 cold-start time 降低 14.8%，跨次实验标准差降低 24.25%（§6，图 4、表 2）。
- **机制指标与端到端结果一致**：同一组冷启动中，所有 VIP tasks 的总 uninterruptible sleep time 平均降低 71.8%，runnable 等待时间平均降低 52.6%；10 个应用的两个指标都下降，支持“依赖传播加快资源释放、VIP class 缩短排队”的解释（§6，图 5–6）。
- **混合前后台负载**：后台 PiP video call 存在时，Taobao cold start 从 149.7 ms 降到 135.0 ms（9.8%），WeChat Moments 从 163.5 ms 降到 126.3 ms（22.8%）；Douyin live scroll 与 news scroll 分别降低 13.8% 和 17.8%（§6，表 3）。
- **调度开销**：短视频场景下，平均 context-switch latency 保持 5 µs，`pick next task` 从 2 µs 增到 3 µs；120 FPS 游戏里平均 FPS 从 119.76 变为 119.69，normalized current 从 726.62 mA 变为 718.16 mA，最差掉帧数从 4 变为 3（§6，表 4）。这些均是少数平均指标，不构成最坏开销上界。
- **生产部署**：系统从 2024 年 1 月起部署到超过 2,000 万台 Honor 设备，覆盖旗舰与中端、MediaTek 与 Qualcomm。按每千小时异常次数统计，动画连续掉帧大于 50 ms 从 27.2 降到 20.4（25.0%），滑动从 10.5 降到 6.8（35.7%），启动大于 2 s 从 94.5 降到 65.5（30.7%）（§7.1，表 5）。
- **明确的负结果**：大型 MOBA 游戏已经有稳定、简单的关键线程，瓶颈转向功耗与温度。MUSCHED 对平均 FPS 和帧时间波动没有显著改善，CPU 使用量只小幅降低，电流与外壳温度反而略差（§7.2）；因此论文结论不能扩成“所有移动 workload 都受益”。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 语义感知的 VIP class 与依赖传播能缩短冷启动 | 平均启动降低 14.8%，sleep/runnable 时间降低 71.8%/52.6%（§6，图 4–6） | 单款 Magic 7，10 个 app，各 100 次，受控前后台压力 | 强 |
| MUSCHED 在混合交互场景仍有效 | 4 个 PiP 并发场景延迟降低 9.8%–22.8%（§6，表 3） | 4 个指定场景，只报告平均 latency | 中 |
| 调度 fast path 的平均开销较小 | context switch 5→5 µs，pick-next 2→3 µs，游戏 119.76→119.69 FPS（§6，表 4） | 一个短视频和一个游戏场景，无 P99 或最坏 verifier/hook 成本 | 中 |
| 系统能在商用规模改善 QoE | 2,000 万台设备；三类异常降低 25.0%–35.7%（§7.1，表 5） | Honor 设备上的上线前后聚合数据，未披露随机对照和置信区间 | 强 |

## 批判性分析

### 论证链条

论文从一条具体 IPC priority-inversion trace 出发，把语义缺口拆成“识别关键线程、让它高于 CFS、提升它依赖的线程、避免 RT/VIP 冲突”四个设计，实验又分别给出 sleep、runnable 和端到端启动时间，因此主链条是闭合的。20M 设备数据证明方案能运行，不只是原型。缺少的是组件消融：当前结果无法分清 VIP class、锁/Binder 传播、选核和 load balancing 各自贡献多少，也不能确定全部复杂性都必要。

### 假设压力测试

核心假设是场景和关键线程能被准确标注。标签漏掉一个 Binder 链节点会留下瓶颈，标签过宽则让许多任务竞争 VIP；策略过时还可能在应用更新后悄悄退化。优先级传播对同步 Binder 和已支持锁最直接，但异步队列、驱动、GPU fence、I/O 与网络依赖仍可能成为关键路径。热限制更严、核心更少的中端 SoC 上，迁移和抢占的收益也可能被 DVFS 与温控抵消。

### 实验可信度

实验室部分固定设备状态、每应用重复 100 次，并报告了机制指标，设计较扎实；生产覆盖两家 SoC 和多档设备，外部有效性也很强。不过实验主要给平均值，没有 P95/P99、置信区间或功耗随时间变化。生产表是上线前后聚合异常频率，论文没有说明 cohort 随机化、同期版本变化或 per-device 配对方法，因此能证明相关的真实改善，却不能像严格 A/B test 那样隔离因果。

### 系统性缺陷

“用户态调度”这个说法容易低估内核改动：MUSCHED 扩展 bpfloader，依赖 sched_ext struct_ops，并通过 kfunc 把复杂逻辑和内核数据写入带回内核。eBPF verifier 限制促使实现把状态放进全局 maps、拆分控制流，这些路径的故障恢复、map 状态损坏和升级兼容性没有量化。论文也没有给出恶意或错误策略能否滥用 VIP、普通任务最大饥饿时间、跨 cgroup 隔离、嵌套优先级传播环、设备崩溃率等安全边界。

## 局限与后续工作

- **做分解实验**：在同一 10-app 集合上分别关闭 VIP class、锁传播、Binder 传播和 load balancing，报告 cold-start P50/P95/P99、sleep/runnable 时间与能耗，验证每个组件的必要性。
- **测最坏公平性**：构造持续产生 VIP、错误标注和多层锁依赖的压力测试，给出 CFS 最大等待时间、VIP 预算超限率、迁移次数与 RT deadline miss 数，而不只报告平均性能。
- **验证生产因果**：用设备/版本分层的随机 A/B cohort 复测三类每千小时异常，公开样本量、置信区间、功耗和崩溃率，排除同期软件更新影响。
- **联合核心与频率控制**：把 thermal headroom 和 DVFS 纳入 policy；以“同一 QoE anomaly rate 下 normalized energy 至少不劣于原生调度”为客观验收条件。
- **扩大依赖覆盖**：测量 GPU fence、异步 Binder、I/O 和网络等待占交互关键路径的比例，再只对占比显著的路径增加传播机制，避免无边界扩张 hooks。

## 相关

- **相关概念**：[[eBPF]]
- **同会议**：[[OSDI-2026]]
- **原始材料**：[[osdi26-xiao]]、[[osdi26-xiao.pdf]]
