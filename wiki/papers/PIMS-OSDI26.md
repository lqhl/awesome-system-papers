---
type: paper
name: PIMS
full_title: "PIMS: Fleet-wide Datacenter Maintenance with Minimal Capacity Buffer and Predictable Latency (Operational Systems)"
authors: [Benjamin Leonhardi, Evangelia Kalyvianaki, Yang Wang, Abdelrahman Adam, Agshin Nabiyev, et al.]
venue: OSDI
year: 2026
tags: [datacenter, maintenance, capacity-management, production-system]
source_pdf: "[[osdi26-leonhardi.pdf]]"
source_md: "[[osdi26-leonhardi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# PIMS：小容量缓冲且延迟可预测的全数据中心维护系统（OSDI 2026）

> **原题**：PIMS: Fleet-wide Datacenter Maintenance with Minimal Capacity Buffer and Predictable Latency (Operational Systems)

PIMS 是 Meta 运行五年的全 fleet 维护系统，以 fault domain 为执行单位、复用一份容量缓冲，并用跨团队 maintenance contract 将软件、固件和物理维护组织成可预测的 rollout。

## 问题与动机

维护会暂时移除服务器或整个故障域，服务必须迁入预留 capacity buffer。缓冲越大，并行维护越快，但对数百万服务器 fleet 而言几个百分点就是数万台机器；缓冲过小又会使升级无限排队，甚至与突发故障叠加。PIMS 的目标是在保留故障容错的同时，最小化缓冲并为端到端维护时间提供 SLO。

## 关键观察 / 隐含假设

### 关键观察

- 服务器维护、故障域物理维护和故障域突发失效不必各留一份缓冲；自动维护可在另一故障域失效时快速暂停，因此三类事件可以复用一份 buffer。
- buffer 由单个 region 中最大 maintenance domain 的服务容量决定；均匀放置硬件与服务比单纯提高调度并行度更能降低长期预留。
- 延迟横跨 PIMS 调度、服务 drain 和具体维护动作，任何单方优化都无法保证端到端 SLO，必须用 contract 明确各层预算和强制行为。

### 隐含假设

- 物理维护只占约 9%，与另一故障域同时失效的概率足够低；自动维护占约 91%，且可安全、迅速暂停。
- 服务能在 3 小时内 drain，超时强制抢占的可用性风险可接受。
- region 内故障域失效近似独立；相关电力、网络或软件故障不会频繁同时击穿多个域。

## 核心方法

### 缓冲复用与故障域对齐

PIMS 在每个 region 预留约一个 fault domain 的容量，并让 maintenance domain 与其对齐。自动维护遇到其他域失效时让出容量；低频、难暂停的物理维护则依赖事件重叠概率较低这一运营事实。

### 均衡硬件放置

硬件 placement 算法把机型和资源在 maintenance domains 间尽量铺平，并提出 rack relocation 建议。这样服务也能跨域均匀分片，最大域的容量下降，所需 buffer 随之减小。

### 维护契约与分层调度

maintenance contract 为 Sequencing、Orchestration、服务 drain 和执行工作流分别规定 SLO。中央调度器处理优先级、依赖和冲突；boxcar 将同一域的多个动作批处理，并在 batch 内按优先级排序，在吞吐和单项延迟间折中。

### 跨维护协调

系统避免软件升级与纠正性维修在同一设备并发，必要时取消低优先级动作。OpsCoordinator 驱动 workload drain、监控拓扑冲突，并在 3 小时预算耗尽时执行强制策略。

## 设计取舍

- PIMS 选择单域 buffer，而非通过全面复制交换机与电力组件缩小故障域，节省基础设施但保留约 20K 服务器的域粒度。
- 固定 boxcar 窗口便于人工维护和 SLO 推理，却造成 drain/work window 大量空闲。
- 中央协调提高全局可预测性，也使维护栈和组织 contract 成为新的关键依赖。
- 强制 drain 保证 rollout 节奏，但把极端慢服务的风险从维护系统转回业务团队。

## 实验与结果

- 2025 Q2 按 placement 建议移动 15,716 个 racks 后，PIMS buffer 从约 fleet 的 4.5% 降到约 4%，实际容量节省约 15%；截至 2026 年 5 月进一步降至约 3%，对应每年节省数万台服务器（§5.1，图 5）。
- 生产环境每月平均执行 2–3K 个 rollouts，覆盖数百万服务器；六个月中有四个月按资产加权的 rollout success rate 至少 90%，两个异常月分别为 72% 和 84%，根因是日志配置与 intent discovery bug。
- OS freshness SLO 要求 95% 服务器每 45 天重新 provision；相比旧系统一次 fleet-wide OS upgrade 约 3 年，当前周期缩短 23 倍。
- 固定与弹性日期物理维护在六个月中多数月份有至少 95% 能在计划时间后 30 分钟内开始；弹性维护“请求后 90 天内开始”的 99% SLO 在六个月中满足五个月。
- boxcar drain 的 P95 为 77 分钟、P99 为 175 分钟，3 小时超时强制率为 0.6%；长尾说明进一步缩短窗口会显著增加抢占或未完成升级。
- 一个月中 drain window 平均利用率仅 7%，work window 为 23%；这是可预测固定窗口换来的明显容量空转。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| 一份 buffer 可覆盖多类维护与故障 | maintenance domain 对齐，自动维护可暂停 | 当前 buffer 约占 fleet 3% | 依赖故障独立和暂停路径可靠 |
| 均衡放置可实质减少预留 | rack relocation 缩小最大域资源偏斜 | 2025 Q2 buffer 容量降低约 15% | 观察性生产数据，缺少对照 fleet |
| 分层 contract 可使维护延迟可预测 | 每层 SLO、boxcar 与强制 drain | 45 天 OS SLO 多月超过 95%；drain 强制率 0.6% | 两个月软件故障曾使成功率降至 72%/84% |
| 系统已达 hyperscale 可运营性 | 中央协调软件、固件与物理动作 | 每月 2–3K rollouts，覆盖数百万服务器 | Meta 私有云架构与组织流程特定 |

## 批判性分析

### 论证链条

论文不是提出全新调度算法，而是把 buffer sizing、拓扑放置、维护排序和组织契约组合成生产闭环。五年运营数据将资源节省与 SLO 达成联系起来，最有价值的是揭示“可预测维护”本质上是跨系统、跨团队协议问题。

### 假设压力测试

若两个域因共享软件或上层电力故障相关失效，单域 buffer 会不足；若服务不能在 3 小时内安全迁移，强制 drain 可能将维护 SLO 转化为用户事故。物理维护占比上升时，依靠低重叠概率复用 buffer 的论据也会削弱。

### 实验可信度

数据规模、时间跨度和失败案例披露增强可信度，但研究主要是 before/after 观察，placement、fleet 增长和流程改进同时发生，难以做严格因果归因。论文也没有公开服务中断率、维护导致的用户影响或 buffer 不足事件。

### 系统性缺陷

固定窗口利用率仅 7%/23%，显示 PIMS 用显著时间冗余换取组织可预测性。中央系统的配置与 discovery bug 已造成明显 SLO 下滑，说明控制面本身是 fleet-wide blast radius；论文对这一风险的隔离机制讨论不足。

## 局限与后续工作

- 建模相关故障、极端多域事故及 buffer 不足时的降级策略。
- 通过更细粒度的自适应窗口降低 7%/23% 的低利用率，同时保持人工维护可计划性。
- 报告用户可见中断、强制 drain 后果和维护控制面故障的 blast radius。
- 在不同规模、拓扑与组织边界的数据中心验证 maintenance contract 的可迁移性。

## 相关

- [[Datacenter-Maintenance]]
- [[Fault-Domain]]
- [[Capacity-Planning]]
- [[Twine]]
