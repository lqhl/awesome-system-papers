---
type: paper
name: PIMS
full_title: "PIMS: Fleet-wide Datacenter Maintenance with Minimal Capacity Buffer and Predictable Latency"
authors: [Benjamin Leonhardi, Evangelia Kalyvianaki, Yang Wang, Abdelrahman Adam, Agshin Nabiyev, et al.]
venue: OSDI
year: 2026
tags: [datacenter-maintenance, capacity-buffer, fleet-management, scheduling, fault-domains]
source_pdf: "[[osdi26-leonhardi.pdf]]"
source_md: "[[osdi26-leonhardi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向全舰队的数据中心维护（OSDI 2026）

> **原题**：PIMS: Fleet-wide Datacenter Maintenance with Minimal Capacity Buffer and Predictable Latency

> **一句话总结**：PIMS 把计划维护、故障域、硬件放置和服务迁移放进同一份维护契约，用一个按区域复用的 buffer 覆盖维护与单故障域损失，再以 MD 轮转和分层 SLO 调度升级；生产数据表明 buffer 从约 4.5% 降至约 4%，截至 2026 年 5 月约为 fleet 容量的 3%，OS rollout 从约 3 年缩短到 45 天。

## 问题与动机

在 Meta 的数百万台服务器和数万项服务上，内核、驱动、firmware 以及物理设备都需要持续维护。维护会暂时减少可用容量，传统做法为不同事件分别预留 buffer，既浪费资源，也难以给升级完成时间作出承诺。

PIMS 的目标是同时控制两个量：每个区域为维护保留的容量，以及从请求创建到全舰队完成升级的时间。论文讨论的是计划维护，不负责应用级发布和大范围灾害；但它必须和故障、纠正性维护及服务迁移共享同一套容量视图。

## 关键观察 / 隐含假设

- **观察 1：共享组件的维护天然以 fault domain 为单位。** 同一 power supply 或 network switch 下的服务器会同时不可用，因此逐台维护无法避免共享组件造成的整域容量损失（§2.2）。
  - **依赖假设**：服务和数据可以跨 MD 分布，并能承受一个 MD 的损失。
  - **可能失效场景**：某类服务存在强硬件亲和性、跨域副本不足，或一个 MD 内的资源类型严重偏斜时，单一 buffer 不够。
- **观察 2：buffer 的大小由各类硬件在 MD 间的最大偏斜决定。** 将服务器均匀放置，比单纯缩小 fault domain 更直接地降低 buffer（§1、§5.1）。
  - **依赖假设**：同一区域的 MD 具有相近的电力、网络和冷却能力，且机架可以实际搬迁。
  - **可能失效场景**：区域内 MD 设计异构、搬迁受拓扑限制，或新型 GPU 网络域与 power domain 不一致。
- **假设 1：计划维护和 MD 故障的并发风险可以接受。** 2025 年共记录 4 次 MD 故障；自动维护遇到故障时须在 35 分钟内归还 buffer（§3.4）。证据强度：中，依赖五年生产经验和有限故障样本。
- **假设 2：服务能在 3 小时内完成 drain。** Stateful 服务另获 24 小时预通知；超时任务会被强制抢占（§4.4）。证据强度：强，契约和生产监测均覆盖，但长尾并未消失。

## 核心方法

PIMS 将每个区域划为 maintenance domains（MD），通常与最大 power fault domain 对齐。每个区域只有一个 `b_PIMS`，覆盖一个 MD 的容量损失。服务、数据和硬件都要跨 MD 均匀分布；硬件放置器每月运行贪心机架迁移，目标函数同时考虑 headroom、资源超用、服务器类型均匀性、网络兼容性和 tapbox 使用。它不保证 MILP 的全局最优，但一次运行约 25 分钟。

维护侧采用“maintenance train”。一个 boxcar 包含约 3 小时 drain window 和 3 小时 work window；PIMS 用 Least Recently Visited 顺序轮换 MD，并在每个 boxcar 内按 gold、silver、bronze 三档填充升级。gold 通常要求 45 天收敛，firmware 等 silver 工作按预估耗时获得比例预算，bronze 只使用剩余时间。

维护契约把责任分给服务、调度器和执行器：服务须容忍一个 MD 损失并在 3 小时内迁移；PIMS 须维持每个 MD 的访问周期；buffer 要覆盖一个常见 MSB 故障；若自动维护期间发生 MD 故障，正在使用 buffer 的维护须在 35 分钟内释放容量。这样，buffer 复用不是单纯的概率假设，而是由暂停、监控和执行器接口共同约束。

实现上，Intent、Sequencing、Budgeting、Orchestration、Execution 五层分别负责声明升级意图、选 MD、生成 boxcar、建立安全执行环境和实际升级。OpsCoordinator 统一检查同类 MD 不能并发下线、buffer 是否足够、拓扑冲突和 drain 状态，并在大规模故障时暂停计划维护。

## 设计取舍

- **单 buffer 复用**降低容量开销，但把故障处置和维护调度绑定起来；故障发生时必须快速暂停维护，35 分钟释放 SLO 也增加了执行器和 on-call 的约束。
- **贪心放置**牺牲全局最优换取规模和低延迟。目标函数权重靠客户反馈调节，长期最优性和跨区域泛化没有证明。
- **固定 6 小时 boxcar**牺牲短期利用率换取周期可预测性。平均 drain 利用率仅 7%、work 利用率 23%，但 P99 drain 达 175 分钟，缩短窗口会增加强制执行和未完成升级。

## 实验与结果

- 2025 Q2 搬迁 15,716 个机架后，`b_PIMS` 从 fleet 容量约 4.5% 降到约 4%，相对下降约 15%；截至 2026 年 5 月约为 3%（图 5、§5.1）。
- 在 2024 年六个月内，系统每月处理全球约 2–3K 个 rollout、52 类升级；大多数月份按 SLO 完成率至少 90%，故障月份为 72% 和 84%，原因是日志配置更新和 intent discovery bug（图 6、§5.2）。
- OS provision 的 95% 服务器可在 45 天内完成；论文将其与此前约 3 年的 fleet-wide OS upgrade 相比，报告约 23× 的 rollout 时间缩短（§5.2）。
- 固定和 flexi-date 维护大多达到“计划时间 ±30 分钟”95% SLO；flexi-date 维护在六个月中有五个月满足 90 天内启动的 99% SLO（图 7–8）。
- 45 天 MD 访问周期合规率持续高于 95%，drain 超过 3 小时而被强制处理的比例为 0.6%；约 0.5% 服务器无法在 work window 内完成维护（表 2、§5.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 均匀硬件放置能降低维护 buffer | 15,716 个机架迁移使 buffer 从 4.5% 降到 4%（图 5） | Meta 生产 fleet，2025 Q2；非随机对照 | 强 |
| PIMS 能提供可预测的升级周期 | 45 天周期合规率高于 95%，多数 rollout 月度成功率至少 90%（图 6、表 2） | 六个月窗口；异常月份暴露出软件故障 | 中 |
| 一个 buffer 可复用来应对维护和 MD 故障 | 2025 年 4 次 MD 故障均在 20 分钟内释放容量，未使用其他 buffer（§3.4） | 单年、少量故障；并发独立性未被充分验证 | 中 |
| 固定 boxcar 能平衡预测性与利用率 | P95/P99 drain 为 77/175 分钟，而平均窗口利用率为 7%（§5.4） | 六小时窗口、Meta 区域；手工维护不能随时提前开始 | 强 |

## 批判性分析

### 论证链条

论文的主链条较完整：MD 对齐解释了维护粒度，硬件和服务均匀放置解释了 buffer 降低，维护契约和分层调度解释了周期 SLO。生产数据也覆盖了 buffer、周期和 drain 三个层面。最弱的一步是把低频 MD 故障外推为可长期复用的 buffer 设计；故障样本很少，且“独立发生”的计算只是近似模型。

### 假设压力测试

当区域内出现多个 MD 同时失效、服务处于峰值负载，或故障持续超过历史最长的 5 小时时，单 buffer 需要依赖随机故障 buffer 或灾备 buffer。论文报告这些情况很少，但没有给出按服务类型、峰值利用率和故障持续时间划分的风险曲线。新一代 GPU 集群的网络域不再总与 power domain 对齐，论文也明确承认维护粒度仍可能变化（§6）。

### 实验可信度

生产规模和时间跨度是优点，但缺少独立基线。buffer 的下降同时受算法、fleet 增长、安装和退役影响；论文没有给出反事实放置或随机对照。rollout 成功率按资产数加权，适合容量目标，却可能掩盖少量小规模但高风险升级。结果也主要关注 SLO 合规，未量化迁移造成的资源成本、服务 tail latency 或业务影响。

### 系统性缺陷

PIMS 依赖服务遵守 drain 契约、执行器实现统一接口、硬件团队执行机架搬迁，还需要多个团队共同调节目标函数权重。论文提到 fault-tolerant database 和 on-call 机制，但未详细讨论调度器恢复期间的重复执行、审计能力、权限隔离以及跨区域灾难时 buffer 的联动。固定窗口的低平均利用率也是用容量换预测性的持续成本。

## 局限与后续工作

- **局限 1**：buffer 复用的安全边界主要由经验故障率支撑，缺少针对相关故障、峰值负载和长时间故障的压力实验。
- **局限 2**：硬件放置器是局部贪心搜索，目标权重依赖人工反馈；论文没有报告与更强全局优化器或不同区域配置的对比。
- **后续工作 1**：按区域和服务负载建立 MD 并发故障的容量风险模型，验证在 P99 故障持续时间和峰值负载下仍能满足 35 分钟释放 SLO。
- **后续工作 2**：在 GPU 网络域、power domain 和服务拓扑不一致时，比较按网络域、按 power domain 及混合粒度维护的 buffer、重启和训练 checkpoint 成本。
- **后续工作 3**：用可提前启动的自动维护替代部分固定 boxcar，测量在不降低 45/90 天 rollout SLO 的情况下能否减少 7%/23% 的窗口空闲。

## 相关

- **相关概念**：[[Fault Domains]]、[[Capacity Management]]、[[Rolling Upgrade]]、[[SLO]]
- **同类系统**：[[Twine]]、[[Flux]]、[[RAS]]、[[Conveyor]]
- **同会议**：[[OSDI-2026]]
