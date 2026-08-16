---
type: paper
name: PIMS
full_title: "PIMS: Fleet-wide Datacenter Maintenance with Minimal Capacity Buffer and Predictable Latency (Operational Systems)"
authors: [Benjamin Leonhardi, Evangelia Kalyvianaki, Yang Wang, Abdelrahman Adam, Agshin Nabiyev, Aleks Shirokov, Amitav Mohanty, Daniil Balenko, Elaine Zhao, Essam Ewaisha, Hongbo Dong, Igor Marnat, Lev Novikov, Min Zeng, Steven Shingler, Timofey Durakov, Wiliam de Abreu Pinho, Ben Christensen, Mayank Pundir, Kaushik Veeraraghavan]
venue: OSDI
year: 2026
tags: [datacenter, maintenance, capacity-management, fault-domain, production-system]
source_pdf: "[[osdi26-leonhardi.pdf]]"
source_md: "[[osdi26-leonhardi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# PIMS：用小容量缓冲实现可预测的全机群维护（OSDI 2026）

> **原题**：PIMS: Fleet-wide Datacenter Maintenance with Minimal Capacity Buffer and Predictable Latency (Operational Systems)

> **一句话总结**：PIMS 把一次只维护一个故障域写成跨基础设施、业务服务和维护团队共同遵守的 contract，并让计划维护、故障域物理维护和意外故障复用同一份区域容量；这套系统在 Meta 数百万服务器上运行五年，2025 Q2 配合 rack relocation 让专用缓冲相对减少约 15%，同时把 OS 全机群升级从约三年缩到 45 天。

## 问题与动机

数据中心必须持续更新 kernel、driver、OS 和 firmware，也要定期停电或断网检查物理设备。维护期间，受影响服务器上的服务要先搬到预留容量。若为每种维护保留独立 buffer，数百万服务器机群里的几个百分点就是数万台机器；若 buffer 太小，又会令升级长时间排队，或在维护和故障重叠时损害服务容量。

PIMS 的范围是计划自动维护和计划物理维护，不包括应用自身发布，也不直接调度按需的纠正性维护、超大区域灾难和数据中心退役。不过，它必须看到这些事件，才能避免与正在执行的计划维护冲突。Meta 的维护中约 91% 是自动操作、9% 是物理操作。

Meta 把一个区域分成多个 maintenance domain（MD），它同时也是 [[Fault-Domain|故障域]]：域内服务器共享低压配电或网络设备，一旦共享组件停机，整个域都不可用。上层电力设备有冗余，网络域又被设计在电力域以内，因此 PIMS 主要按最大无完整冗余的 MSB 域规划；一个 MD 约含 20K servers。PIMS 每个 region 单独运行，并维护专用的 `b_PIMS`。截至 2026 年 5 月，它约占全 fleet 的 3%。另有一份约占全 fleet 2% 的随机单机故障 buffer；区域灾难和应用发布也各有独立 buffer，论文没有给出后二者比例，不能混为一谈。

## 关键观察 / 隐含假设

- **观察 1：三类容量损失不必各留一份 buffer。** 单机/软件计划维护和共享设备的物理维护都按一个 MD 执行；自动维护遇到另一个 MD 故障时可以暂停并归还容量，因此还可与意外 MD failure 复用（§3.4）。
  - **依赖假设**：服务平时能容忍失去一个 MD，自动维护能在 35 分钟内释放容量，物理维护与另一个 MD 故障重叠足够少。
- **观察 2：buffer 由每种硬件在最偏斜 MD 中的数量决定。** 对每个 server type 取跨 MD 最大值，再把不同类型相加，得到 `b_PIMS`；所以只缩小平均域没有用，还必须把硬件、服务和数据均匀铺开（§2.3）。
  - **依赖假设**：同一 region 的 MD 在电力、网络和冷却能力上近似同构。Meta 只在新 region 采用新的 MD 设计，以避免域内混杂。
- **观察 3：维护延迟不是单个调度器能控制的。** 总时间包括请求转成 intent、选域、服务 drain、具体 upgrader 和硬件工程师执行。只有为每个参与方规定 SLO，并允许超时强制动作，端到端时间才可预测。
  - **依赖假设**：业务服务愿意接受统一 contract，包括三小时内 drain，必要时被强制 preempt；状态服务可利用提前 24 小时通知完成复制。
- **观察 4：固定窗口看似浪费，却保护长尾和人工计划。** 一个月内 drain/work window 平均只使用 7%/23%，但 drain P99 达 175 分钟，接近三小时上限（§5.4）。缩短窗口会提高利用率，也会增加未完成升级和人工排期冲突。
- **假设 1：区域内多 MD 故障近似独立且很少发生。** 2025 年全 fleet 只有四次 MD failure；这是共享 buffer 的经验依据，但样本很小，不能证明相关电力、网络或软件故障不会同时击穿多个域。

## 核心方法

### 1. 用 maintenance contract 固定责任边界

contract 有四条核心要求：服务始终能承受失去一个 MD；域内 workload 在约三小时内 drain；`b_PIMS` 至少覆盖常见情况下一个最大 MSB 域；若意外故障发生，正在使用 buffer 的自动维护要在 35 分钟内归还容量。这样，业务团队可以自行决定 quorum、replica 或流量迁移方式，PIMS 只检查是否按时腾空，而不理解每个服务内部实现。

该设计把可预测性建立在组织协议上，而不只是调度算法上。它也有强制性：三小时仍未 drain 时，OpsCoordinator 除大规模基础设施故障外会 preempt workload。论文报告 enforcement rate 很低，但没有量化这些强制动作的用户影响。

### 2. Placement stream 缩小最大域

hardware placement 同时考虑 power/network/cooling headroom、资源超配惩罚、server type 分布、网络兼容性和共享供电单元。虽然可写成 MILP，生产规模下 PIMS 改用贪心搜索：每轮枚举把一个 rack 从当前位置移动到另一位置的候选，选择令加权 objective 降得最多的一步，直到收益小于阈值。大部分项用 [[PyTorch|PyTorch]] tensor 表达，gradient 帮助估计 rack 移动对目标的影响；权重仍靠多个团队长期反馈调节（图 3）。

算法每月运行一次，总用时约 25 分钟，每轮约一秒，通常做几次到几百次迭代。输出只是 rack relocation 建议，实际搬迁由独立团队和另一小份 buffer 执行。服务 placement 由 [[Twine]] 等库把实例铺到多个 MD，数据 replica 则由 ShardManager 分散；硬件、服务和数据三者缺一不可（图 2）。

### 3. Maintenance train 与 boxcar

每个 region 有一列持续循环的 maintenance train，一次只访问一个 MD。Sequencing 按 least recently visited（LRV）选择下一域，再把人工工作时间、失败 revisit 和 emergency train 放入最长 90 天的时隙；未来三个工作日的顺序冻结，避免反复改计划。72 个 MD、每次访问 12 小时需要 36 天，再留 9 天重试，形成常见的 45-day cycle。

一次 MD visit 是固定时长的 boxcar，例如三小时 drain 加三小时 work。多个 rollout 共享一次 drain 成本。Budgeting 把请求分成 gold、silver、bronze：Q1 2026 约 65% 是 gold、35% 是 silver；gold 常在 15–30 分钟内完成并给 100% budget，silver 常需一到两小时，按预计时长分配，bronze 尽力执行。kernel 的全 fleet SLO 是 45 天，firmware 通常是 90 天（表 1）。

### 4. 五层维护栈

Intent 持续把 rollout scope 转成每台机器的目标状态；Sequencing 选择 MD；Budgeting 选本次 boxcar 的升级；Orchestration 处理 drain、拓扑和跨维护冲突；Execution 运行标准接口的 upgrader，并按成功率、耗时和升级后 host health 找出 bad actor。各层异步运行，但都有对相邻层的 SLO。状态保存在容错数据库，PIMS 进程重启后可继续已有 intent 和 boxcar（图 4）。

failed boxcar 的成功率低于约 80% 时会安排 revisit，多次失败则退避，避免一个坏域阻塞整列 train。人工 train 优先于自动 train；紧急回滚可插入最高优先级 train，或在容量类型允许时一次覆盖少量跨域机器，把某些故障版本缓解时间从数周降到一两天。

### 5. 故障发生时归还共享容量

检测到一个 MD failure 后，PIMS 不再开始新维护。若自动维护已在另一个域运行，则等待当前可中断单元结束并归还容量；很长的 upgrader 必须由 client 拆小，卡住时 on-call 可手动释放。过去五年没有违反 35 分钟 SLO；2025 年四次 MD failure 都在 20 分钟内归还容量，也没有借用其他 buffer。

物理维护难以暂停。作者按 9% 操作占比、某 region 最长五小时 failure 和独立事件假设，估计其与 MD failure 重叠约 0.45 小时/年；自动维护对应约 4.6 小时/年。这只是简化风险估算，不能覆盖共同原因故障。

## 设计取舍

- **一份 MD buffer 换双域风险**：常态容量最小，但维护尚未退出时若另一个域故障，会短暂同时失去两个域。
- **约 20K-server 域换基础设施成本**：进一步复制低层电力与网络可以缩域，却会增加设备、复杂度和运维成本；PIMS 选择中间点。
- **固定 boxcar 换可预测性**：让人力和 rollout 能提前排期，但平均窗口利用率低，未完成的约 0.5% servers 还要借随机故障 buffer 吸收。
- **中央 contract 换本地自主性**：所有服务得到统一边界，却必须实现单域容错、按时 drain，并接受超时强制 preemption。
- **贪心 rack movement 换可运营性**：25 分钟可给出实用建议，但不保证全局最优；目标权重和实际搬迁成本依赖人工经验。

## 实验与结果

- **生产范围与 buffer reduction**：PIMS 从 2019 年开始集中化、2021 年主要部署；论文覆盖 Meta 数百万服务器、数万个服务和五年生产运行。2025 Q2 根据 placement 建议实际移动 15,716 racks，`b_PIMS` 从 fleet 约 4.5% 降到约 4%；由于同期总 fleet 还在增长，作者计算相对 reduction 约 15%，折合每年数万台服务器，截至 2026 年 5 月约为 3%。36–72 MD 的理论完美均衡下界是 region 的 1.4%–2.8%，但多机型和其他资源约束使它未必可达。结果均为私有 fleet 运营观测，没有对照实验或公开 trace（图 5、§5.1、§6）。
- **自动 rollout**：图 6 实际画出 2024 年 5–11 月七个柱状月份，按 asset 加权的成功率依次为 72.2%、98.1%、91.5%、84.5%、98.2%、95.1%、97.2%；五个月至少 90%，四个月至少 95%。低点来自 logging 配置错误和 intent-discovery bug。同期每月约 2–3K rollouts、六个月汇总超过 300 个 Kernel/Firmware/OS 版本和 52 种 upgrade type。95% servers 现在每 45 天 provision OS，旧系统约需三年，论文换算为 23 倍缩短（图 6、§5.2）。
- **物理维护**：目标是 95% fixed/flexi-date boxcar 在计划时间后 30 分钟内开始。图 7 显示多数点很高，但并非月月达标，最低 fixed 为 85.7%、最低 flexi 为 90.2%。flexi request 的另一目标是 99% 在创建后 90 天内开始；图 8 七个月中五个月达到 99%，最低为 95.2%，主要例外来自 network retrofit 的物料和人力约束（图 7–8）。
- **分层 SLO**：2024 年 5–11 月 Sequencing 的 45-day compliance 为 98.2%–99.9%。drain P95/P99 为 77/175 分钟，只有 0.6% 超过三小时而被 enforce。多数 upgrader 每百万次的成功率、耗时和 host-failure breach 很少，但 RDMAFirmware 每月仅 46,174 次，却分别有 22/282/0 次 breach，后来归因于错误地运行了另一个更长 workflow（表 2）。
- **效率边界**：一个月内 drain/work window 平均利用率只有 7%/23%，说明可预测性依靠大量时间余量。约 0.5% servers 到 work window 结束仍没完成，PIMS 释放已完成机器、继续处理剩余机器并前往下个 MD，由随机故障 buffer 吸收残余容量（§4.4、§5.4）。
- **共享 buffer 的历史证据**：2025 年四次 MD failure 分布在三个 region，单 region 最长累计五小时；四次都在 20 分钟内收回自动维护容量，低于 35 分钟 contract，且未借其他 buffer。物理/自动维护与故障的 0.45/4.6 小时年重叠量来自独立性估算，不是实际冲突次数（§3.4）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 均匀硬件放置能实质减少 PIMS buffer | 15,716 racks 搬迁；图 5 从约 4.5% 到约 4%，作者计算相对降 15% | 2025 Q2 before/after，无对照 region，其他 fleet 变化并存 | 中 |
| contract 与分层 SLO 能让自动 rollout 大体可预测 | 图 6、表 2：多数月份 rollout 高，45-day compliance 98.2%–99.9% | Meta 七个月数据；控制面 bug 曾降到 72.2%/84.5% | 中 |
| 一份 buffer 可同时支持维护与意外 MD failure | 五年无 35 分钟违约；2025 四次故障均少于 20 分钟归还 | 仅四次近期事件，依赖故障独立和服务单域容错 | 中 |
| 固定 boxcar 能覆盖 drain 长尾 | P95/P99 77/175 分钟，三小时 enforcement 0.6% | 私有服务组合；未报告用户可见影响 | 强 |
| 系统已经在 hyperscale 长期运行 | 五年、数百万服务器、数万服务、每月 2–3K rollouts | 单一公司、特定拓扑和组织流程 | 强 |

## 批判性分析

### 论证链条

PIMS 不是靠一个新优化器取胜，而是把 failure-domain sizing、rack placement、服务/data placement、批处理调度和跨团队 contract 组成闭环。论文先说明 buffer 为什么由最大域决定，再通过迁架 before/after 展示容量变化；又把端到端 latency 分摊到五层 SLO，并用五年运营数据展示结果。逻辑合理，但两条主结论的证据类型不同：系统长期运行是直接事实，“placement 造成全部 15% reduction”和“三份 buffer 可安全合一”更多是观察性归因和风险判断。

### 假设压力测试

共享 buffer 最怕共同原因故障。软件 bug、上层网络或电力事件可能同时影响多个 MD，和单域 failure 独立模型不同；物理维护又不能快速暂停。服务必须能承受一个完整域丢失，三小时后还可能被强制 preempt，这对复制慢、容量紧或 quorum 脆弱的状态服务并不轻。新 AI cluster 的 GPU 网络域也不再自然落在电力域内，论文承认现在会为自动和物理维护采用不同粒度，设计仍在变化。

### 实验可信度

五年、数百万服务器和真实失败记录提供了小规模 testbed 无法替代的外部真实性，论文也没有隐藏 May/Aug 异常和低窗口利用率。不过，没有对照 fleet、随机试验或逐组件消融；rack relocation、fleet 增长、placement library 和流程改造同时发生，无法严格把 buffer reduction 分给某一组件。图 6 的正文称“六个月”，图中却是 May–Nov 七个柱；物理 SLO 也有多个低于目标的点，因此“predictable”应理解为有 contract、能测量和大体收敛，不是每次都按时。

### 系统性缺陷

集中式 Intent/Sequencing/Budgeting 控制面拥有很大 blast radius，logging 配置和 intent discovery bug 已让整月 rollout success 明显下降。虽然状态存在容错数据库，论文没有说明错误 plan、错误 priority 或错误域映射的自动隔离与回滚。实际搬动 15,716 racks 需要人力、停机、re-image 和独立容量，这些成本没有与节省的服务器做净额比较。论文也没有报告强制 drain 后的用户可见故障、SLO 违约、数据重建流量或共享 buffer 真正不足的次数。

## 局限与后续工作

- **局限 1**：共享 buffer 的并发故障证据只有四次 2025 事件，物理维护重叠还使用独立概率近似。
- **局限 2**：容量和 rollout 结果来自 Meta 私有拓扑与组织流程，算法、trace、迁架成本和服务影响无法外部复现。
- **局限 3**：固定窗口平均利用率低，中央控制面 bug 又可能同时影响大量 rollout。
- **后续工作 1**：用共享软件、网络和电力故障 trace 建相关故障模型，报告双域 loss 下 buffer deficit、降级时间和用户流量损失。
- **后续工作 2**：对 boxcar 做受控的窗口缩短实验，联合测利用率、P99 drain、enforcement、未完成升级和人工排期违约。
- **后续工作 3**：公开按季度的净成本账，包括 rack relocation、re-image、额外 buffer、强制 drain 事故和节省的服务器数量。

## 相关

- **相关概念**：[[Datacenter-Maintenance]]、[[Fault-Domain]]、[[Capacity-Planning]]、[[Rolling-Upgrade]]
- **相关系统**：[[Twine]]、ShardManager、OpsCoordinator
- **同会议**：[[OSDI-2026]]
