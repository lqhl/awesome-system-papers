---
type: paper
name: mwait-sched
full_title: "What Are You (M)Waiting For: The Hidden Cost of Idle in the Hyperscale Cloud (Operational Systems)"
authors: [Yun Wang, Xingguo Jia, Ben Luo, Kenan Liu, Shengdong Dai, Jingdong Han, Weihao Chen, Yicheng Gu, Xingzi Yu, Yibin Shen, Jiesheng Wu, Zhengwei Qi, Haibing Guan]
venue: OSDI
year: 2026
tags: [virtualization, cpu-scheduling, cloud, oversubscription, mwait]
source_pdf: "[[osdi26-wang-yun.pdf]]"
source_md: "[[osdi26-wang-yun]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 超大规模云中 `mwait` 空闲的隐性代价

> **原题**：What Are You (M)Waiting For: The Hidden Cost of Idle in the Hyperscale Cloud (Operational Systems)

> **一句话总结**：原生 `mwait` passthrough 在独占核上很快，却让 hypervisor 看不到 vCPU 已空闲，超售后反而让“空闲”租户长期占住 pCPU；mwait-sched 用定时器、空闲分类、整 VM 唤醒和多地址代理把这个硬件空闲重新变成可调度信号，并在 320 万 pCPU 的 dedicated fleet rollout 中显著降低争用事件。

## 问题与动机

x86 的 `monitor/mwait` 让 CPU 监视一个内存地址并进入 C-state，地址被写时可低延迟醒来。在 vCPU 与 pCPU 一一绑定时，直接把 `mwait` 交给 guest 执行能避免 VM exit，延迟接近 bare metal。问题出在超售：硬件核心虽然进入空闲状态，但 host 上的 vCPU 线程仍被视为 runnable 并继续拥有这颗 pCPU；hypervisor 没收到“我可以让出核心”的信号，真正可运行的共置 vCPU 只能等待。

KVM 默认把 guest `mwait` 当作 NOP 也不能解决问题，因为 vCPU 会持续自旋。`hlt` 会 trap 并让出核心，但每次 idle/active 切换都有 exit、模拟和中断注入成本。论文要同时保留 `mwait` 的低唤醒延迟与 [[CPU-Scheduling|host 调度器]]需要的空闲可见性。

## 关键观察 / 隐含假设

- **观察 1：guest 空闲与 host runnable 是两套语义。** passthrough 只改变物理核心的 C-state，不会让 host scheduler 把 vCPU 线程睡眠；所以低 CPU utilization 不能说明安全超售，steal time 才直接反映拿不到 pCPU 的等待（§1–§3）。
- **观察 2：`mwait` 空闲时长近似双峰。** 生产 [[eBPF|eBPF]] 样本中，busy vCPU 的 99.6% 空闲段短于 200 us，而 idle vCPU 的 96.0% 空闲段长于 1 ms，中间很少。长且方差低的空闲可聚合到共享核，短且波动大的空闲应继续独占核（§4.2，图 12）。
- **观察 3：不同工作负载需要不同定时器切片。** I/O 和同步密集服务适合 20–50 us，CPU 密集任务适合更长切片。作者用 PMU 的 IOPS/vCPU-utilization 比值分类，不检查租户应用内部状态（§4.1）。
- **观察 4：只唤醒 waiter 会造成 lock-holder preemption。** 某个 vCPU 的等待条件满足时，它依赖的 lock holder 可能仍被暂停；因此系统把同一 VM 的所有 runnable vCPU 一起标为可运行（图 10–11）。
- **假设 1：Linux idle 路径的 `need_resched` 语义稳定。** `mwait-proxy` 比较监视地址的值，而硬件 `mwait` 对任意 store 都会醒。论文依赖当前 Linux 只让 idle vCPU 把 `need_resched` 从 1 清为 0，认为不会漏掉有意义的同值写或短脉冲（§4.3）。

## 核心方法

mwait-sched 让 active vCPU 继续以 1:1 方式运行 `mwait-passthrough`。空闲分类器看到持续、低方差的稳定空闲后，才把 vCPU 聚合到共享 pCPU；一旦它恢复短暂活跃，就拆回独占 pCPU。共享核上不再直接 passthrough，而按实例类型采用两种模拟路径（§4，图 6）。

**低密度 dedicated 实例使用定时器路径。** guest 执行 `mwait` 后让出 pCPU，hypervisor 设定周期性 tick，让 vCPU 最迟在一个切片后重新检查唤醒条件。短切片醒得快但产生更多 timer、VM exit 和重调度。mwait-sched 用 PMU 比值在 I/O 型短切片和 CPU 型长切片间选择，并在一次唤醒时把同 VM 的 runnable vCPU 都标记为可运行，减少 lock holder 被暂停的问题（§4.1）。

**高密度 burst 实例使用 `mwait-proxy`。** 每个进入 `mwait` 的 vCPU 把监视地址加入 hypervisor 共享链表；以后每次已有的 hypervisor entry 都扫描链表，发现值变化就唤醒对应 vCPU。它避免为每个 vCPU 安装周期定时器，但扫描成本随共置数增长，而且只能在下一次 hypervisor entry 观察变化。生产策略按实例类别预先选择：dedicated fleet 固定 1:2 使用 mwait-sched，burst fleet 通常 1:4、峰值 1:6 使用 proxy，并不是对每台 VM 在线切换两种机制（§4.3、§5.4）。

## 实验与结果

- **基线与环境**：受控平台是双路 Intel Xeon Platinum 8269CY，共 104 个硬件线程、192 GB DDR4，host Linux 4.9.168、QEMU 8.2.2；guest 为 4 vCPU、8 GB、Linux 5.10.134。24 类工作负载和 220 个场景来自生产流量、用户报告和事故，图表重点展示 File I/O、MySQL、Ping、Redis、SuperPI、TCP loop、ZooKeeper（§5，表 2–3）。
- **根因测量**：单 VM 时，passthrough 的平均读写延迟比 `hlt` 和 `mwait-nop` 约低 20%。但表 1 显示 `mwait-nop` 每秒有 1,826,602 次 idle-induced exits，`hlt` 为 1,773，passthrough 为 0；把一个完全空闲的 `mwait` VM 与延迟敏感 VM 共置后，尾延迟最高可膨胀到 3 倍，因为空闲 vCPU 不让核（§3，图 3–4、表 1）。
- **切片与分类器**：图 8 中，多数 I/O/同步负载在 20–50 us 切片达到最低 P99；切片从 400 us 缩到 0–20 us 时，host CPU 从约 8%–10% 升到 50%–60%，guest 仍约 6%–9%。在 1,000 个可由 VM image 标注类型的生产 VM 上，IOPS/utilization 中位数为 I/O 型 840、CPU 型 20；阈值 100 的总误分类率为 0.21%，阈值 50–150 时均低于 0.7%（§4.1、§5.1，图 8–9）。
- **1:2 受控结果**：在 1:1 时四种机制接近；到 1:1.5 和 1:2，mwait-sched 相对默认 `mwait-nop` 把 Redis、ZooKeeper 等同步敏感负载的 P99 降低 30%–50%，并把超过 90% 的 steal time 压到低于 60%，论文总结为 steal ratio 降低 30%–40%。这里的 30%–50% 基线是 `mwait-nop`，不是 passthrough。`fdatasync` 会为每次 fsync 多等至一个切片，MySQL set 在 1:1 passthrough 下也会受深 C-state 唤醒影响（§5.2，图 14）。
- **proxy 扩展边界**：1:4 是 burst tier 的典型密度。此时 CPU/I/O 型负载 P99 为 1:1 基线的 1.8–3.4 倍，但 TC、Redis set/get、ZooKeeper get 分别达 4.9、6.4、7.0、8.2 倍。到生产峰值 1:6，后几类达到 7.9–12 倍；超出生产范围的 1:8 压力点最坏达 11–16 倍。proxy 能提高密度，却没有保持接近 1:1 的尾延迟（§5.3，图 15）。
- **生产 rollout**：§5.4 的数字只来自 1:2 dedicated fleet 的 mwait-sched。上线约 10 天后，三个代表区域的高争用 steal 事件分别下降 85%、97%、86%；图 16 显示 daily live migrations 同步下降，摘要将降幅汇总为 30%–50%。多个区域共 320 万 pCPU 上，平台报告的 oversubscription ratio 从 1.0% 升至 20.3%，约增加 60 万个可售 vCPU；每日告警从每万台 512 次降到 197 次，即 61.5%（摘要、§5.4，图 16–17）。

## 论断—证据表

| 论断 | 直接证据 | 证据边界 | 置信度 |
|---|---|---|---|
| passthrough 的空闲不可见会造成共置干扰 | 空闲 `mwait` VM 使共置负载尾延迟最高变为 3 倍；图 5 给出调度因果过程 | 受控 x86/KVM 环境，未覆盖其他 ISA 和 hypervisor | 强 |
| 定时器路径可改善低密度超售 | 1:1.5/1:2 下 P99 比 `mwait-nop` 低 30%–50%，steal time 同步下降 | 受控场景，短切片的 host CPU 成本可能很高 | 强 |
| 空闲与工作负载分类足够清楚 | idle-duration 双峰；1,000 VM 上 PMU 分类错误率 0.21% | 类型标签来自 VM image，混合或变相 workload 未单独验证 | 中强 |
| 软件 proxy 可以服务高密度 burst 实例 | 1:4/1:6 扫描实验覆盖生产典型和峰值密度 | 同步负载延迟膨胀 5–12 倍，生产 rollout 章节未报告 proxy 指标 | 中 |
| rollout 提高了全局可售容量并减少事故 | 320 万 pCPU 前后对比：1.0% 到 20.3%，告警 512 到 197；三个区域 steal/migration 同降 | before/after 观察，没有随机对照或并行变化说明 | 中强 |

## 批判性分析

### 论证链条

论文从“利用率低却不能超售”的生产现象，追到 passthrough 下 guest idle 没有变成 host yield，再用共置实验复现，因果链很完整。定时器恢复控制权、整 VM 唤醒解决 lock-holder preemption、稳定空闲再聚合，也分别对应清楚的问题。较弱的是 proxy：它依赖“下一次已有 hypervisor entry”扫描，机制上没有定时器路径那样明确的唤醒上界，而高密度结果本身显示同步负载会有很大尾延迟膨胀。

### 假设压力测试

需要重点测试阶段变化和语义变化。PMU 分类器用 VM image 当标签，无法说明一个同时含 CPU 和 I/O 阶段的 VM 会多快切换切片，也没有报告阈值抖动。idle classifier 使用长短与方差，但论文没有给出窗口长度、误聚合率和拆分延迟的系统敏感性。proxy 还应注入同值写、写后恢复、长时间无 hypervisor entry 以及自定义 guest idle loop，验证 Linux `need_resched` 之外的行为。

### 实验可信度

24 类、220 个生产派生场景，配合 320 万 pCPU 的多区域数据，使问题真实性很强；表 1、图 8–15 又把 VM exit、CPU 开销、P99 和 steal time 连在一起。生产证据仍是上线前后观察，不是随机 canary 或差分实验；同一时期 oversubscription ratio 还大幅上升，虽然告警反而下降很有说服力，但其他调度或容量变化没有被控制。更重要的是，生产章节明确只报告 dedicated fleet，不能用这些数字证明 proxy 在 burst fleet 的实际效果。

### 系统性缺陷

定时器路径把不可见空闲变成周期轮询，最短切片会让 host CPU 升到 50%–60%，这部分成本会吞掉可售容量和能耗收益，但论文没有给出全 fleet 功耗或净成本。VM-wide wakeup 可能形成小型惊群；只测了单个 48-vCPU VM 的标记和排队时间，没有测许多 VM 同时唤醒。proxy 的链表扫描是 `O(N)`，图 15 已暴露 1:6 后的扩展墙。论文还把“恶意 guest 最多占核到下一次 hypervisor entry”描述为小且可预测，但在没有 entry 的情况下这个界并不确定，DoS、公平性和 timing side channel 也未做攻击实验。

## 局限与后续工作

- 对定时器、整 VM 唤醒和 proxy 分别报告功耗、净可售容量、调度公平性与多租户安全实验。
- 用受控 canary 或差分设计验证 rollout 因果关系，并单独公布 burst fleet 的 proxy 生产数据。
- 公开 idle classifier 的窗口、阈值、迁移/拆分策略和 phase-change 反应时间。
- 采用论文提出的向量化 `vmonitor` 或其他硬件多地址监视，去掉链表线性扫描，并为 x86、Arm、RISC-V 定义可虚拟化的等待语义（§6，图 18）。

## 相关

- **相关概念**：[[Virtualization]]、[[CPU-Scheduling]]、[[Oversubscription]]、[[Tail-Latency]]、[[Lock-Holder-Preemption]]
- **相关系统**：[[KVM]]、[[QEMU]]
- **同会议**：[[OSDI-2026]]
