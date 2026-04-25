---
type: paper
name: FailureMiner
full_title: "FailureMiner: A Joint Key Decision Mining Scheme for Practical SSD Failure Prediction and Analysis"
authors: [Shuyang Wang, Yuqi Zhang, Haonan Luo, Kangkang Liu, Gil Kim, et al.]
venue: FAST
year: 2026
tags: [ssd, failure-prediction, telemetry, random-forest, interpretability]
source_pdf: "[[fast2026-wang-shuyang.pdf]]"
source_md: "[[fast2026-wang-shuyang]]"
---

# FailureMiner: A Joint Key Decision Mining Scheme for Practical SSD Failure Prediction and Analysis (FAST 2026)

> **一句话总结**：用 boundary-preserving downsampling + 基于 SHAP 的 joint key decision 抽取，从 Samsung Telemetry 数据训出可解释的 SSD 故障预测规则，相比已有方法 precision 平均 +38.6%、recall 平均 +80.5%；规则已在腾讯数据中心 350,000+ SSD 部署一年，发现 NAND/DRAM/电容三类故障模式与 PCIe error 等健康影响因子。

## 问题

数据中心 SSD 故障会导致数据丢失和服务中断。已有 ML failure prediction 三步走：data preprocessing → model build → model interpretation。但作者发现三个实际问题：

1. **Downsampling 误删边界样本**：random/representative downsampling 把分类边界附近、与 failed 样本相似的 healthy 样本删掉了，模型学不到细微差别，导致 false alarm 暴涨（1:1 平衡时 FA 比 baseline 高 200×）。
2. **Feature selection 太粗**：WEFR 等会误删辅助 attribute（单独无用但组合有用）。
3. **Attribute-level interpretation 不够细**：SHAP 只给 attribute importance，看不到具体阈值；SDE 按出现频率挑 important decision 但很多高频决策实际 SHAP 值很低。

## 核心方法

**Boundary-preserving downsampling**：
- Temporal feature generation：用滑动窗口 w=3/7/15 天计算 max-min 差值作为变化趋势特征。
- Failed SSD clustering：用 JIC 选出区分能力强的 attribute，min-max 归一化，K-means 聚 N=50 类，每类用最大类内距离作为 cluster boundary B_n。
- Healthy SSD dividing：对每类只保留欧氏距离 < B_n 的 healthy 样本（边界附近的「易混淆」样本）+ 等量随机样本防过拟合，其余大量健康样本丢弃。

**Joint contribution-based key decision set extraction**：
- 在每个 cluster 训 Random Forest（用全部原始 + temporal feature）。
- Key decision mining：在 RF 的「正确预测 failure」的 decision path 上递归算每个 decision 节点的 SHAP 值（从 attribute 级细化到 decision 级），imp_score = 跨路径累计；imp_score > 0.1 的留作 key decision。
- Key decision set extraction：仿 Apriori，从 1-decision set 出发按 contrib_score（综合 imp_score + co-occurrence frequency）扩到 k-decision set，得到「joint key decision」——多个属性 + 阈值的组合规则。

**部署模式**：抽出的 joint key decisions 是 if-then 规则（attribute combinations + threshold range），无需在线跑模型，运维易理解。

## 关键结果

- 在腾讯（70M Telemetry log，788 故障）+ 阿里公开数据集上，precision 平均 +38.6%、recall +80.5%（vs 现有方法）。
- 规则已部署到腾讯 350,000+ Samsung PM9A3 SSD 上一年，提升可靠性。
- 发现三类强 joint key decision 对应 NAND（NandUECC + BadNandBlock + ReadRetry）、DRAM（DramCECC + DramCECC-Add）、电容（CapHealth）故障模式。
- 提取 weak decision 揭示 PCIe error（BadTLP/BadDLLP/PHYError）、bad block、end-to-end error 是 SSD 健康的关键影响因子。

## 相关

- **相关概念**：Failure Prediction、SHAP、Random Forest、Apriori、SMART Telemetry、Downsampling
- **同类工作**：MVTRF、WEFR、SDE、CNN-LSTM for SSD prediction、JIC
- **同会议**：[[FAST-2026]]
