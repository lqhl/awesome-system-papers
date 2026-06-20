---
type: paper
name: Acela
full_title: "Cost-Aware Duration Prediction for Software Upgrades in Datacenters"
authors: [Yi Ding, Aijia Gao, Thibaud Ryden, Michal Sedlak, Essam Ewaisha, Igor Marnat, Henry Hoffmann]
venue: MLSys
year: 2026
tags: [datacenter, scheduling, prediction, firmware-upgrade, slo]
source_pdf: "[[3c59dc048e8850243be8079a5c74d079.pdf]]"
source_md: "[[3c59dc048e8850243be8079a5c74d079]]"
---

# Cost-Aware Duration Prediction for Software Upgrades in Datacenters (MLSys 2026)

> **一句话总结**：Acela 用非对称代价感知的 quantile regression 预测 Meta 生产环境 firmware upgrade 时长，使 upgrade window 利用率 **1.25×**、调度/完成量 +33%/+41%，取消率降 **2.4×** 且仍满足 95% SLO。

## 问题与动机

超大规模数据中心必须定期做 OS / firmware / kernel 等软件升级以维持可靠性，但升级调度与 service job scheduling 长期被分开研究。Meta 现网采用 **circle-based upgrade process**：rack 内服务器组成 upgrade group（UG），按固定 **upgrade window** 轮转升级；窗口内须让 **≥95%** 升级按时完成，否则服务器进入 repair / overflow 流程，运维难以区分「慢」与「坏」。

为保守满足 SLO，Meta 对所有升级类型使用 **worst-case 固定时长** 估计，每 server 每周期只排少量升级。结果是 16 个数据中心 5 个月实测 upgrade window 利用率仅 **20–40%**（部分达 50%），方差大、idle 严重，需要更多 cycle 才能扫完全部升级。

论文核心 claim 不是「把 duration prediction 做准」，而是：**在 asymmetric misprediction cost 下，预测目标应直接服务调度吞吐与 SLO，而非对称 accuracy**。作者将升级调度形式化为带 SLO 约束的优化问题，提出 Acela 作为 Meta 现有 scheduler 的增强层（非替换），并在 400 万+ 训练、100 万测试的真实 firmware upgrade 上部署评估。

## 关键观察 / 隐含假设

- **观察 1（利用率低源于 uniform worst-case）**：Figure 1 显示 Meta 16 DC 平均 window 利用率 20–40%，主因是忽略 upgrade type / hardware context 的统一长时长假设。
  - **依赖假设**：若用 per-upgrade 差异化时长，同一 window 可安全塞入更多升级而不系统性违约 SLO。
  - **可能失效场景**：若 buffer capacity、UG 内并行度上限（如 25%）或 repair 流程成为硬瓶颈，仅缩短预测时长无法线性提升吞吐。

- **观察 2（misprediction cost 非对称）**：underprediction 导致 window 过载、取消与 repair 歧义；mild overprediction 反而有利于 SLO；straggler 训练样本会把模型推向 extreme overprediction，回到 worst-case 低效。
  - **依赖假设**：SLO 是「95% 按时完成」这类 one-sided 目标，等价于需要 OPR（overprediction rate）略高于 95%，而非最小化 MAE。
  - **可能失效场景**：若运维改为对称 cost（如过度 overprediction 也会触发人工复核），或 SLO 收紧到 99%，当前 τ / score 权衡需重标定。

- **观察 3（upgrade type 长尾分布差异大）**：8 类 firmware（BIC/BIOS/CPLD/DISK/FLASH/ME/NIC/BMC）duration CDF 形态与尾延迟差异显著（Figure 6），占 Meta firmware 升级 **>99%**。
  - **依赖假设**：per-type 独立建模 + 特征（版本、硬件、位置、上次升级时间）足以刻画条件分布。
  - **可能失效场景**：新 upgrade version 分布漂移（§5.1 已列为风险）；OS/kernel 等更稳定或更短类型上收益可能有限（论文明确 firmware 为最高不确定性类别）。

- **观察 4（accuracy 与系统 outcome 可脱钩）**：Naïve-ML（同 GBT 结构、L2 loss 最小化 MAE）在仿真中 scheduled 最多，但 cancellation rate 高；Strawman（per-type 均值）亦过载。
  - **依赖假设**：调度决策读的是「是否安全塞进 window」的保守分位，而非点估计。
  - **证据强度**：**强**——生产与仿真均显示 MAE 最优者 completion 未必最高。

- **假设 1（Meta circle-based 语义可保留）**：Acela 只改 duration 输入与同等优先级下的 tie-break，不改变 dependency / stakeholder / history 优先级语义。
  - **证据强度**：**中**——已集成三路 RPC 模块，但复杂冲突仍依赖 operator 人工介入。

## 核心方法

Acela 是 **cost-aware duration prediction framework**，通过三模块接入现有 scheduler（Figure 9）：

**1. Quantile Gradient Boosting Trees（QGBT）**

用 τ > 0.5 的 quantile loss 估计条件分位而非条件均值，使 underprediction 惩罚更重、mild overprediction 可接受。基于 LightGBM 实现，按 upgrade type 各训一模型，捕捉 Figure 6 的分布差异。

**2. Custom scoring 选模**

在时间上晚于训练集的 validation set 上，对多组 τ 与训练集变体打分：

- OPR ≥ SLO（95%）时：最小化 MAE，避免过度保守
- OPR < SLO 时：用惩罚参数 α（生产取 10，月度 cross-val 复核）加重 under-SLO 风险

这直接把模型选择绑到「能否多排升级且仍达标」，而非纯 prediction leaderboard。

**3. Training set diversification**

对训练集按 p99 / p99.9 截断生成多个子集，分别训练+打分，选 score 最低模型。剔除 straggler 后 OPR 几乎不变（96.275% vs 96.075%），但 MAE 改善约 **1.2×**，减轻极端 overprediction bias。

**4. 调度集成逻辑**

- 同等优先级：优先排 **预测时长更短** 的升级，提高 window 填充率
- 优先级冲突：仍先执行高优先级升级（依赖、stakeholder、criticality）
- 在线每周重训，滚动丢弃旧数据、加入新 upgrade

系统模块：**DCP**（持续采集特征）→ **MTS**（训练/选模）→ **PQS**（JSON RPC 返回预测时长）→ 原 scheduling service。

## 设计取舍

- **取舍 1：略偏 overpredict vs 吞吐**：quantile + score 接受比 Naïve-ML 更差的 MAE（约 1.2–2.4×），换取 OPR≈95% 与低 cancellation——用 window 利用率换 prediction 竞赛名次。
- **取舍 2：截断 straggler vs 尾事件覆盖**：去掉 p99/p99.9 训练样本降低对硬件 failure 长尾的显式建模，依赖 repair 流程处理真正 straggler；避免回到 worst-case 式空闲。
- **取舍 3：增强层 vs 新调度器**：保留 Meta 既有 priority / UG / buffer 语义，降低部署风险，但 correlated underprediction within UG、buffer 25% 并行上限等结构性约束无法靠预测单独消除。
- **边界条件**：firmware、1–2 小时级、周级重训、α=10 的设定下最优雅；短升级（kernel/switch <30min）或 OS 高可预测流程上边际收益可能很小——论文 §6.1 已说明聚焦 firmware 的理由。

## 实验与结果

**生产对比（198 UG，≈100 万升级；151 UG 用 Acela，47 UG Heuristic）**
- Upgrade window 利用率：**1.25×**（相对 Figure 1 的 20–40% 基线）
- Scheduled upgrades：**+33%**；Completed upgrades：**+41%**
- Cancellation rate：**÷2.4**；Acela 满足 <5% 取消率对应 95% SLO，Heuristic 未达标

**仿真单 UG（14,515 请求）**
- Acela completed 最多且 CR 最低；Naïve-ML scheduled 最多但 CR 高；Strawman CR 比 Acela 差 **11.75×**，Naïve-ML 差 **10.4×**

**预测指标（8 类 firmware）**
- Heuristic MAE 比其它方法高 **38–79×**（固定长时长）
- 仅 Acela（quantile loss）达到 OPR≈95%；L2/L1/Huber 对称 loss OPR≈50%，不满足 SLO
- 去 straggler：MAE **1.2×** 改善，OPR 基本持平

**训练规模**：400 万+（3 个月）训练，100 万（1 月）测试；每周重训，p99/p99.9 截断。

## Critical Analysis

### 论证链条

「worst-case → 低利用率」的 measurement（Figure 1）→「非对称 cost + 分位预测 + SLO-aware 选模」设计 → 生产利用率 1.25×、完成量 +41%、CR ÷2.4 且达标」链条**闭合且可部署**。有力论据是 Naïve-ML 反例：accuracy 更高却系统 outcome 更差，支撑「prediction for scheduling」而非「prediction for accuracy」的 framing。

薄弱跳步：**151 vs 47 UG 的非随机分配**——因 Acela 提高 scheduling volume 而扩到更多 UG，虽每 UG ≥1000 upgrades，但非严格 A/B。论文用仿真（<1% 偏差）补强，生产数字应理解为「部署 cohort 相对历史 heuristic 的 before/after」，非完全随机对照。

### 假设压力测试

- **Workload**：仅 firmware（占 >99% 但非全部软件升级）；OS/kernel 更短更稳，论文承认预测需求较低。
- **分布漂移**：新 upgrade version 后特征空间变化；周级重训+version feature 可缓解，§5.1 仍标为 failure mode。
- **UG 内相关性**：同 rack 多 server 若同时 underpredict，小误差可叠加违约——论文提出需监测 correlated error，未给量化实验。
- **规模外推**：4M/1M 已是 datacenter scale，但 47 UG 仍用 heuristic；全量 rollout 后 buffer/repair 压力是否变化未讨论。

### 实验可信度

- **Baseline**：Heuristic 是真实生产长期策略，对比有现实意义；Strawman/Naïve-ML 仅仿真（每 server 每 upgrade 只发生一次，production A/B 成本高），合理但削弱「相对 ML 强基线」的 live 证据。
- **Metric**：utilization、cancellation、scheduled/completed 直接对齐运维目标；缺少 dollar cost、repair 工单数、operator intervention 次数等二级指标。
- **Ablation**：loss 函数、straggler removal、τ sweep（Figures 12–16）支持各组件必要性；α 仅报 cross-val 选定值 10，敏感性未展开。

### 系统性缺陷

- **故障降级**：PQS 超时或缺特征时若 silent fallback 到 unsafe default，可能批量 underpredict——§5.1 列出但未给生产降级策略与实测。
- **尾延迟与 repair 歧义**：目标之一是减少「慢 vs 坏」误判，但论文未报告 repair 率、overflow 使用或人工 inspection 变化。
- **可观测性 / 运维**：三模块 RPC 流水线、周级重训、多数据集×多 τ 选模，模型漂移告警与 rollback 流程论文未讨论。
- **公平性与多租户**：stakeholder-critical 升级可 override duration tie-break，duration 优化对低优先级升级的收益分配未量化。

## 局限与 Future Work

- **局限 1**：聚焦 firmware；对 OS/kernel/网络设备等类别的泛化仅基于定性特征对比，无实验。
- **局限 2**：生产评估非随机 UG 分配；Strawman/Naïve-ML 未 live 部署。
- **局限 3**：worst-case 与 correlated failure 的形式化鲁棒边界分析留作 future work（§5.1 明确 in-depth worst-case analysis deferred）。
- **Future work 1**（论文提出）：对 rack 级 correlated underprediction、distribution shift、straggler removal 副作用、PQS 依赖失败做可观测信号+replay/fault injection 测试。
- **Future work 2**（可验证延伸）：报告 repair/overflow/人工 inspection 率随 Acela 部署的变化，验证「SLO 达标」是否转化为运维成本下降。
- **Future work 3**：在 upgrade version 大版本切换窗口测量 OPR/CR 漂移曲线，评估周级重训是否足够或需 event-triggered 重训。

## 相关

- **相关概念**：Quantile-Regression、Service-Level-Objective、Upgrade-Scheduling
- **同类系统**：Meta circle-based upgrade scheduler、3Sigma（job runtime 分布预测）、NURD（datacenter straggler prediction）
- **同会议**：[[MLSys-2026]]