---
type: paper
name: PowerSight
full_title: "Hardware Lifecycle-Aware Power Planning in Commercial Hyperscale Datacenters (Operational Systems)"
authors: [Ruihao Li, Leonardo Piga, Wei Su, Neeraja J. Yadwadkar, Lizy K. John, Carlos Torres, Jovan Stojkovic, Abhishek Dhanotia]
venue: OSDI
year: 2026
tags: [datacenter, power-management, capacity-planning, machine-learning, operational-systems]
source_pdf: "[[osdi26-li-ruihao.pdf]]"
source_md: "[[osdi26-li-ruihao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向硬件生命周期的超大规模数据中心功率规划

> **原题**：Hardware Lifecycle-Aware Power Planning in Commercial Hyperscale Datacenters (Operational Systems)

## 一句话总结

Meta 总结十年生产功率规划经验：量产期用全 fleet 的 workload mix 与实测功率持续收紧 rack power budget，早期无传感器阶段则以 PowerSight 从性能计数器预测系统功率，两者合计支持全 fleet 平均约 20% 的安全功率超配。

## 问题与动机

商业数据中心长期混用多代 compute、storage 与 AI server。功率规划既不能把每台机器的 design peak 简单相加——所有服务很少同时达峰，会形成 stranded power；也不能把量产后的历史 telemetry 套到新平台——pre-EVT 到 MP 超过 18 个月，而可靠功率传感器通常到 DVT/PVT 才存在，rack 采购与供电位置却必须更早决定。

论文把 hardware lifecycle 纳入规划：早期预测 forecast RPB，量产后利用真实 service distribution 与 sensor data 形成 refined RPB，部署一年后继续随配置与 workload 演化调整。它同时给出生产 characterization 和传感器缺失时的替代模型 PowerSight。

## 关键观察 / 隐含假设

### 关键观察

- SPEC CPU2017 虽能把 core 推到高利用率，却低估 memory、SoC non-core、NIC、fan 等功耗；生产 workload 平均达到 design power 的 85.6%，SPEC 仅 75.5%。
- 生产 service 功率横跨 design power 的 20%–90%，且约 15% 服务器低于 50%；异构和非同时峰值正是安全 oversubscription 的来源。
- 代际改进不均衡：CPU-E 相比 CPU-B 同吞吐 socket power 约降 2 倍，而 DDR5 相比 DDR4 同带宽功率仅改善约 1.2 倍；最新代 memory 已超过系统功率的 20%。
- CPU utilization 与系统功率关系随代际变化，storage I/O、GPU SM utilization 等也呈非线性，单指标或线性模型不足。
- performance counters 在全生命周期都可得，因此可以作为无 power sensor 阶段的统一输入。

### 隐含假设

- service mix、上一代 workload fraction 与新平台早期实际部署足够相似，可用于 prior。
- 上百万生产样本覆盖部署分布；新架构不会出现训练数据之外的根本功率行为。
- aggregation-level power cap 能吸收少量预测误差，且 fleet workload 峰值相关性保持稳定。
- Meta 的高度标准化 telemetry、规模与部署流程能被其他 operator 部分复用。

## 核心方法

每个 rack 有 design power `D`，但上游 panel、switchboard 与 main switch 才是集中管理点。forecast RPB 在 pre-EVT/EVT/DVT 阶段结合 benchmark、供应商规格与早期样机估算，避免 rack 被放入供电不足的位置；到 PVT/MP 后，用每类 workload 的 fleet fraction `f_w`、对应实测功率 `p_w`、rack server 数 `n` 和 ToR 功率计算 refined RPB。随着部署数据积累，规划器持续更新分布，而不是永久使用一次性峰值。

相比仅按 design power，forecast RPB 使 rack density 增加 13%；refined RPB 又在 forecast 之上增加 11%。按 rack 功率 footprint 加权后，这套方法十年间在 compute、storage、AI fleet 平均支持约 20% 超配，相当于在不增加总供电 footprint 下部署约 20% 更多 rack。

## PowerSight

### 输入与模型

PowerSight 用 machine configuration 与已有 performance counters 预测整机功率，不依赖 BMC power sensor。输入涵盖 CPU、memory、storage、network、GPU 等指标；先以 PCA-based clustering 去除强相关 counter，选出的子集与全特征相比准确率损失少于 0.1%。作者比较 Lasso、Ridge、SVM、decision tree、GBDT 和 MLP，非线性 tree/MLP 更合适；SVM 在百万样本下训练成本过高。

### 训练与跨架构

数据来自数百万 server、数千 service 和数十 machine configuration。仅数万样本时误差超过 10%，作者建议至少数百万样本。单架构上 DT、GBDT、MLP 均超过 95% 准确率；联合所有 compute/storage/AI 架构时，MLP、DT、GBDT 分别达到 96.19%、95.59%、95.53%。

### 规划用例

leave-one-generation-out 预测 CPU-E 时，PowerSight 对 rack design power 的 MAPE 为 1.7%，由此得到的 server count/rack 误差为 8.7%；复用上一代 `f_w` 预测 RPB，误差为 2.5%。这让 rack density、供电预算和系统配置选择可提前数月进行。

## 实验与结果

生产数据覆盖数百万机器、数千服务和多代 compute、storage、AI server；主要结果包括约 20% fleet oversubscription、联合架构 MLP 96.19% 准确率，以及新一代 rack power 1.7% MAPE。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 标准 benchmark 会低估 hyperscale 系统功率 | 图 4：生产 workload 达 design power 85.60%，SPEC 为 75.51%，相差 11.8% | Meta workload 与 SPEC 的对比，未覆盖所有第三方 benchmark | 强 |
| workload diversity 可转化为安全 capacity | 图 5、10：功率为 design 的 20%–90%；forecast/refined 各增加 13%/11% rack density | 安全性依赖持续 telemetry 与上游 cap | 强 |
| 生命周期方法有长期生产价值 | 在 Meta 全球 fleet 部署超过十年，加权平均约 20% oversubscription | operational study 缺少随机对照，策略也随时间共同演化 | 强 |
| 无传感器阶段可预测系统功率 | 联合架构 MLP 准确率 96.19%；CPU-E rack power MAPE 1.7% | 需要百万级历史数据及相似上一代平台 | 强 |
| 功率模型必须多指标、非线性 | DT/GBDT/MLP 各代均超过 95%，优于线性模型 | 模型细节与 artifact 尚计划未来公开 | 强 |
## 批判性分析

### 论证链条

论文罕见地把 power planning 写成贯穿研发、部署、量产和退役的 operational loop，而非单次算法。数据横跨数百万机器、多代硬件和三类 rack，结论直接对应真实 capex 与供电约束。PowerSight 的定位也务实：不是替代量产 telemetry，而是填补 pre-silicon/early-silicon 的信息缺口。

### 假设压力测试

- PowerSight 的训练数据、完整 feature、模型和生产保护逻辑尚未公开，外部难以复现 96% 准确率。
- “准确率”聚合指标不能完全说明 underprediction tail；功率规划更关心少数危险低估，而论文主要报告平均误差。
- 使用上一代 workload fraction 作为 prior，在 AI workload 快速增长或架构剧变时可能出现 distribution shift。
- 20% fleet gain 是十年综合运营结果，无法严格分离生命周期算法、硬件演化、调度与人工工程的贡献。
- 方法依赖 Meta 规模；样本量分析明确显示数万点误差仍超过 10%，小型 operator 难以直接复制。

### 实验可信度

十年 operational deployment 与 fleet-wide telemetry 很有说服力，但 artifact、absolute power、危险 underprediction quantile 均未公开，20% 收益也无法严格分离多项共同演化的工程贡献。

## 局限与后续工作

- **局限**：平均误差没有刻画 power underprediction 的高风险尾部，跨代分布漂移仍可能破坏预算。
- **后续工作**：应输出 prediction interval、风险敏感 RPB，并公开可复现的去敏数据与模型。

后续应报告 underprediction quantile、prediction interval 与 risk-aware RPB；研究新 accelerator/液冷平台下的 domain adaptation；将 workload covariance 与时序峰值直接纳入模型；公开去敏 artifact；并评估 carbon-aware scheduling、power capping 与 lifecycle budgeting 的联合优化，避免各控制环相互抵消。

## 相关概念

- [[Datacenter-Power-Management]]
- [[Power-Oversubscription]]
- [[Capacity-Planning]]
- [[Performance-Counters]]
- [[Operational-Systems]]
