---
type: paper
name: Moirai
full_title: "Moirai: Optimizing Placement of Data and Compute in Hybrid Clouds"
authors: [Ziyue Qiu, Hojin Park, Jing Zhao, Yu-Kai Wang, Arnav Balyan, Gurmeet Singh, et al.]
venue: SOSP
year: 2025
tags: [hybrid-cloud, cost-optimization, data-placement, spark, presto]
source_pdf: "[[3731569.3764802.pdf]]"
source_md: "[[3731569.3764802]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Moirai: Optimizing Placement of Data and Compute in Hybrid Clouds (SOSP 2025)

> **一句话总结**：Uber 66.7M 查询/13.3EB 访问显示 job-table 高互联且 project 边界弱，简单复制或 Yugong 项目级 MIP 仍贵；Moirai 用在线访问分析 + 模板分组 MIP + 新 job routing，在 50/50 hybrid split 上相对 Yugong **降本 97%**（egress **95–99.5%**↓）。

## 问题与动机

企业长期 [[Hybrid-Cloud]]：on-prem 与公有云并存，**数据+计算共置**决定 egress（~$0.09/GB）、专线与复制存储成本。Twitter 全量复制、Spotify 无复制、Alibaba Yugong 项目级 MIP 在 Uber 轨迹上仍 dollar cost 巨大（Figure 1b）。Uber Presto/Spark 占 >95% IO，300PB 表、弱 project 内依赖（仅 10% 读在 project 内），每周 ~50% 新 job——需细粒度、成本感知、可扩展优化器。

## 关键观察 / 隐含假设

- **观察 1**：85% job、77% table 属于最大弱连通分量；仅 10% 数据读发生在 project 内——human org 边界不适合作 placement 单元。
  - **依赖假设**：query template fingerprint（去 literal 的 canonical plan hash）稳定可聚类。
  - **可能失效场景**：ad-hoc SQL 无模板复用时 predictor 退化。
- **观察 2**：56% 流量来自 recurring job，但模板数以 16–68/天 增长，数据量年增 ~30%——纯静态分区不够。
  - **依赖假设**：一周未访问表可 prune；最近 3 个月数据覆盖大多数访问（Rep 3Mon 启发）。
  - **可能失效场景**：突发回溯历史冷表时 egress  spike。
- **假设 1**：MIP 目标应直接最小化 **美元**（egress + 复制 + 链路），非仅带宽。
  - **证据强度**：强；Table 1 定价模型与 Uber 财务动机一致。

## 核心方法

**Moirai 框架**（Figure 1a 反馈环）：

1. 在线 job log + per-table 访问字节
2. 模板相似分组降维；prune 一周未访问表；预选高频复制表
3. MIP：数据放置 + 复制 + recurring job 放置
4. **新 job routing**：per-table access-size predictor 最小化 remote fetch
5. 周期重优化适应资源比例变化

开源 simulator + 将发布 traces（[20]）。

## 设计取舍

- **取舍 1**：MIP 精确但需启发式剪枝 → 最优性让位于可扩展（Uber 规模）。
- **取舍 2**：依赖 Uber 式 data lake（Hive/Hudi 日分区）——其他架构需改模型。
- **边界条件**：50/50 split 称「最难」；其他 split 仍有类似节省但未逐一列表。

## 实验与结果

- vs Yugong（hybrid 适配）：**97%** 成本降低
- egress：**95–99.5%**↓；复制：**最高 99%**↓；on-prem 网络基建：**89–98%**↓
- 资源比例漂移时，aware repartitioning 随时间显著优于静态方案
- Uber 正推进生产部署基础设施

## Critical Analysis

### 论证链条

大规模 trace 刻画 C1–C3 挑战 → Moirai 分解（分组/prune/MIP/routing）→ 97% 成本降，simulator 链条闭合。到生产部署跳步：optimizer 误判导致 job 远程读延迟、合规数据驻留约束、写入一致性论文在 simulator 中简化。

### 假设压力测试

- **预测**：新 job 用历史 per-table access-size——schema 变更、突发 marketing query 可能失效。
- **定价**：egress 费率变化、reserved link 合同改变 MIP 最优解。
- **通用性**：Microsoft Cosmos/Wing 互联较弱场景 Moirai 是否仍 **97%** 优于 Yugong 需独立 trace。

### 实验可信度

4 个月 Uber 生产 trace 极强；Yugong 为 SOTA 合理 baseline。Simulator 非 live cutover，真实网络 jitter、Presto coordinator 行为可能偏差。

### 系统性缺陷

MIP 求解延迟、失败 fallback、人工 override policy 论文未讨论；跨云身份/安全边界对数据复制的约束未深入。

## 局限与 Future Work

- **局限 1**：优化周期与 workload 漂移速度需 tuning。
- **局限 2**：写密集 Spark pipeline 与 Presto 读优化权重可能不均。
- **Future work 1**：生产 A/B 测量实际 egress 账单 vs simulator 偏差。
- **Future work 2**：与 spot/preemptible 计算定价联合 MIP。

## 相关

- **相关概念**：[[Hybrid-Cloud]]、[[Data-Placement]]、[[Spark]]、[[Presto]]、[[Egress-Cost]]
- **同类系统**：Yugong、Cloudward Bound、Twitter/Spotify 迁移实践
- **同会议**：[[SOSP-2025]]
