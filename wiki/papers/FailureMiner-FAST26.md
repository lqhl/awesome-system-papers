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

> **一句话总结**：在 SSD 故障样本极度稀缺、false alarm 运维成本远高于漏报的生产约束下，FailureMiner 用 boundary-preserving downsampling 保留「易混淆」healthy 边界样本，再从 [[Random-Forest]] 中按 SHAP 联合贡献抽取少量 if-then joint key decision 规则；在腾讯 70M+ Telemetry log 上 precision 82.2%、recall 29.6%（F0.5=0.61），相对 RF/WEFR/MVTRF 等 baseline precision 平均 +38.6%、recall 平均 +80.5%，规则已在线服务 350,000+ Samsung PM9A3 SSD 逾一年。

## 问题与动机

企业数据中心 [[SSD]] 故障会直接威胁数据可用性与服务连续性。业界普遍走「data preprocessing → model building → model interpretation」三步：对 healthy 样本 [[Downsampling]] 缓解类别不平衡，用 feature selection 去噪，再用 [[SHAP]]/decision tree 解释故障相关 attribute。但 Samsung + 腾讯在两年生产实践中发现，这套流水线在 **运维可接受** 的精度–召回权衡上仍不够：

1. **Random/representative downsampling 会删掉分类边界附近的 healthy 样本**。这些样本与 failed 样本 pattern 相似，是模型学习细微差别的关键；删掉后 true alarm 上升的同时 false alarm 暴涨——healthy:failed 压到 1:1 时，FA 可比不下采样高 **210×**（Table 2），在 35 万盘规模下 0.1% FA 率就意味着数百次误换盘。
2. **Attribute 级 feature selection（如 WEFR）过粗**：单独看相关性弱的 attribute 可能被误删，但在多 attribute 组合决策中起辅助作用（Figure 1：WEFR 能降 FA 也会漏掉 RF 能抓到的 failure）。
3. **解释粒度不够且 SDE 类方法有系统性偏差**：SHAP 只给 attribute importance，看不到具体阈值与组合；SDE 按决策出现频率选 important decision，但 Figure 2 显示 top-5 频繁决策里仅 CapHealth 有高 SHAP，其余多为噪声；且 SDE 把决策当独立项，忽略多 attribute 联动反映的 failure pattern（如 BadNandBlock 与 ReadRetry 几乎同步飙升）。

FailureMiner 的目标不是再训一个黑盒 classifier，而是产出 **高精度、可解释、运维可直接执行的精简规则集**，并顺带挖掘影响 SSD 健康的弱信号因子。

## 关键观察 / 隐含假设

- **观察 1：在极度不平衡的 SSD 故障数据上，「边界附近、与 failed 相似的 healthy 样本」决定 precision–recall 权衡，而非单纯 healthy:failed 比例**。
  - **依赖假设**：failed 样本可聚成有限类 failure pattern；每类 cluster 的边界距离 B_n 能刻画「与该类 failed 相似」的 healthy 子集；JIC 选出的 attribute 足以支撑聚类分 pattern。
  - **可能失效场景**：罕见/新型 failure pattern 样本过少导致单 cluster 数据不足、过拟合；跨厂商/跨代 SSD Telemetry schema 变化使 JIC attribute 失效；workload 剧变导致 temporal feature（3/7/15 天 delta）语义漂移。

- **观察 2：生产环境对 false alarm 的惩罚远大于漏报——运维宁愿少报也不能频繁误换健康盘**。
  - **依赖假设**：评估指标应偏重 precision（论文采用 F0.5）；strong decision 定义 precision ≥ 50%；告警后人工换盘成本固定且高。
  - **可能失效场景**：业务 SLO 转向「零容忍数据丢失」时 recall 权重应上升，F0.5 与 strong/weak 阈值需重标定；多租户场景下不同业务线对 FA/TA 代价不同，单一全局规则可能不适用。

- **观察 3：Failure pattern 常体现为多 attribute 阈值判断的 **联合** 关系，单 attribute/单 decision 既噪声大又漏子模式**。
  - **依赖假设**：[[Random-Forest]] 在「正确预测 failure」的 key decision path 上，决策级 SHAP（imp_score）+ 共现频率可筛出真正有贡献的 joint key decision；Apriori 式扩展能发现 2–3 个阈值的组合规则且可人工审核。
  - **证据强度**：**中**——Table 6 显示每个 joint decision 的 F0.5 均高于其单 decision 分量；但 strong decision 数量极少（腾讯仅 3 条），对长尾 failure 的覆盖依赖 recall 29.6% 这一事实。

- **假设 1：Samsung Telemetry（85 attributes）相对 [[SMART]]（24 attributes）提供更细粒度内部机制信号，且腾讯 PM9A3 两年 trace 可代表大规模云盘部署**。
  - **证据强度**：**强（腾讯域内）**——70M log、788 labeled failure、一年在线部署；**弱（跨域）**——阿里 MC2 SMART 21 attributes 上仍有效（P 68.4%、R 26.4%），但 attribute 语义与盘型均不同。

- **假设 2：每季度重训 RF + 重抽规则即可适应数据 pattern 轻微漂移，在线推理只需跑几条 if-then 规则**。
  - **证据强度**：**中**——训练 1673s、预测 6s（vs RF 预测 167s），季度重训成本可接受；论文未给出重训后规则稳定性或 concept drift 量化。

## 核心方法

FailureMiner 分两阶段（Figure 3）：**boundary-preserving downsampling（BPD）** 解决「学什么样本」，**joint contribution-based key decision set extraction（JKE）** 解决「从模型里抽出什么可部署规则」。

### Boundary-preserving downsampling

1. **Temporal feature generation**：对原始 Telemetry attribute 用滑动窗口 w=3/7/15 天计算 `Delta_w A = max(A) - min(A)`，捕捉故障前异常趋势（与 [[MVTRF-FAST23]] 等思路一致）。
2. **Failed SSD clustering**：先用 JIC 遍历 attribute 阈值选区分 failed/healthy 能力强的 attribute，min-max 归一化后对 failed 数据 K-means 聚 **N=50** 类；每类以类内 failed 样本到 cluster center 的 **最大距离** 为边界 B_n，把 failure pattern 分区。
3. **Healthy SSD dividing**：对 healthy 数据同样预处理，将欧氏距离 < B_n 的样本划入对应 cluster（「易混淆」边界 healthy）+ 等量随机 healthy 防过拟合；其余大量 healthy 丢弃以实现平衡。后续 **按 cluster 独立** 训模型，减少跨 pattern 干扰。

### Joint contribution-based key decision set extraction

1. **Per-cluster Random Forest 训练**：聚类阶段用 JIC attribute，但 RF 训练使用 **全部** 原始 + temporal feature，避免预删辅助 attribute。
2. **Key decision mining**：只在每棵树中 **正确预测 failure** 的 key decision path 上，递归计算 **决策节点级 SHAP**（imp_score，跨路径累加）；imp_score > 0.1 的决策进入候选池——比 attribute 级 SHAP/SDE 频率更贴近真实贡献。
3. **Key decision set extraction**：仿 [[Apriori]] 从 1-decision set 迭代合并为 k-decision set，用联合贡献分 `contrib_score = avg(imp_score) × co-occurrence_count` 过滤；保留 G_k 中全部集合作为 joint key decision，得到形如「(Delta15NandUECC ≥ 10) or (Delta15NandUECC ≥ 1 & Delta3UserRead < 36)」的可读规则。

**部署形态**：训练后丢弃 RF，仅保留 strong joint key decisions（训练集 precision ≥ 50%）做在线 if-then 匹配；weak decisions（precision < 50%）不用于告警，但用于健康风险因子分析（Section 6.2）。

## 设计取舍

- **精度优先 vs 召回**：F0.5、strong decision 阈值、运维叙事均偏向压低 false alarm；代价是 recall 29.6%，大量实际故障仍漏报（论文未讨论漏报的业务代价量化）。
- **可解释规则 vs 模型表达能力**：117,404 个原始决策压缩为 3 条 strong rule（腾讯），预测延迟 6s、运维可理解；代价是规则集对复杂/罕见 failure 覆盖有限，需依赖季度重训与多 cluster 分而治之。
- **Per-cluster 训练 vs 全局模型**：50 个 cluster 各自 RF + 规则抽取，训练 1673s（N=50 时最优），隔离 pattern 干扰；N 过小（3）边界过宽、recall 25.2%、训练 14237s；N 过大（200）单 cluster 数据不足、过拟合、recall 降。
- **BPD 选择性样本 vs 数据代表性**：刻意丢弃绝大多数 healthy 样本以聚焦边界；若 healthy 分布长尾变化，随机补充量等于「相似样本」均值，可能不足以代表 cluster 内 healthy 多样性。
- **边界条件**：同一服务器型号（PM9A3）、Telemetry 丰富场景最优雅；仅 SMART、少 attribute、无 temporal 窗口的部署需重新验证 JIC/cluster/阈值；PCIe error 等与服务器类型强相关（Figure 8），规则可解释但跨机型泛化需重测。

## 实验与结果

- **腾讯数据集**：2 年、350,000+ Samsung PM9A3、70M+ Telemetry log、85 attributes、788 运维标注 failure；训练 1–13 月、测试 14–23 月。
- **阿里 MC2 SMART**：2 年、20,000 SSD、10M log、21 attributes；验证跨企业/跨 attribute 泛化。
- **主结果（腾讯 test）**：FailureMiner **P=82.2%、R=29.6%、F0.5=0.61**；RF P=55.4%/R=20.4%；CNN-LSTM P=50.0%/R=12.8%；WEFR P=67.9%/R=15.2%；MVTRF P=68.1%/R=19.6%。相对既有方法 **precision 平均 +38.6%、recall 平均 +80.5%**。
- **阿里 test**：FailureMiner P=68.4%、R=26.4%、F0.5=0.52；2 条 strong joint key decision（r198/r174、r1/r187 组合）。
- **Joint vs single（Table 6）**：5 组 joint decision 的 F0.5 均严格高于任一 single decision（如 Joint 1：0.55 vs 0.44/0.32/0.001）。
- **Ablation（腾讯）**：BPD+RF 较 RF **P +21.7%、R +13.7%**；RF+JKE **P +20.4%、R +25.5%**；二者叠加达最高。
- **效率（Xeon Platinum 8380）**：训练 1673s、预测 **6s**；RF 673s/167s；CNN-LSTM 2306s(RTX4090)/2318s；MVTRF 3340s/365s。
- **生产部署**：腾讯数据中心 **350,000+ SSD 在线运行逾一年**，成功预警 **100+** 次实际故障；central DB 预处理 + 规则匹配 + 告警列表驱动换盘。

## Critical Analysis

### 论证链条

论文的 production pain point（downsampling 抬 FA、feature selection 误删、SDE 噪声）有 Attempt 1–3 的定量支撑（Table 2、Figure 1–2），与 BPD/JKE 设计一一对应；ablation 显示两组件独立贡献且叠加有效，论证链条在「同数据集上提升 P/R」层面较闭合。薄弱环节在于：**把 3 条 strong rule 的 interpretability 等同于整体方案价值**——大量 failure 仍靠未抽取的 RF 路径或完全漏报；**平均 +38.6%/+80.5%** 是相对多种 baseline 的算术平均，非单一最强对手 head-to-head；部署成功案例（100+ TA）相对 788 训练 failure 与 35 万盘基数，未报告在线 precision/recall 与离线 test 的一致性。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 边界 healthy 保留可改善 P/R | Table 2 反例 + BPD ablation | Failure pattern 快速演化；cluster 数 N 不适配新盘型 |
| 决策级 SHAP + Apriori 可去噪 | Figure 2 vs SDE；Table 6 joint>single | imp_score 阈值 0.1、contrib 20th percentile 敏感；路径仅「正确预测 failure」可能漏掉难例 |
| F0.5 对齐运维偏好 | Section 5.6 运维经验 | 不同云厂商换盘/迁移成本差异；关键业务盘 recall 权重更高 |
| 季度重训足够 | 训练成本表 | 突发 firmware bug 导致 failure 机制突变；规则集版本回滚策略未述 |
| Telemetry 优于 SMART | 腾讯 vs 阿里实验 | 仅 SMART、无厂商 Telemetry 的部署；attribute 命名/尺度跨代变化 |

### 实验可信度

- **优势**：真实腾讯生产数据 + 公开阿里数据；时间切分 train/test；多 baseline（RF、CNN-LSTM、WEFR、MVTRF）；硬件拆解（Figure 6–9）与一年部署经验增强外部效度。
- **局限**：**788 failure 标签**依赖运维上报，存在漏标/延迟标；CNN-LSTM 未用 server-level/spatial metrics（论文自述），对比可能偏弱；**无与 SDE/SHAP-only 规则的直接端到端对比**（仅 Figure 2 单样本）；交叉验证/多次随机种子稳定性未报告。
- **Metric**：F0.5 合理但未给出 **单位盘 FA 率、换盘成本、预警到故障 lead time 的 SLA 达标率**；strong decision 逐条 recall 很低（DRAM/CapHealth 仅 3.2%），合并后 29.6% 主要靠 UECC 规则贡献，子模式覆盖不均。

### 系统性缺陷

- **尾延迟与在线路径**：预测 6s 相对 RF 167s 已优，但 central DB 预处理 + 网络采集延迟、告警风暴时运维队列积压——**论文未讨论**。
- **多租户/多型号隔离**：腾讯多业务线共池训练，未量化不同 workload 下规则误报率；PCIe error 与 server type 强相关（S1/S6 高达 0.67–0.7），**规则是否应 per-server-type 条件化**未展开。
- **故障恢复与版本管理**：季度重训流程有述，但 **规则变更审计、灰度发布、误报回滚** 论文未讨论。
- **隐私与合规**：Telemetry 汇聚到 central DB，跨租户数据隔离与保留策略未涉及。
- **正确性**：规则基于统计阈值，对 **adversarial/log 篡改** 或传感器故障导致的 attribute 异常未讨论；weak decision 用于健康洞察但 precision < 50%，直接行动可能误导运维。

## 局限与 Future Work

- **局限 1**（实验边界）：recall 29.6% 意味着多数故障仍无法提前预警；单条 strong rule recall 低至 3.2%（DRAM/CapHealth），方案本质是 **高精度窄覆盖** 而非全面预测。
- **局限 2**（方法边界）：hyperparameter（N=50、imp_score>0.1、contrib 20th percentile、w=3/7/15）在阿里/腾讯上手动调优，**自动选型与敏感性**仅在 Section 5.5 部分讨论。
- **局限 3**（论文自述）：false alarm 仍是生产第一关切；早期以 recall/FA rate 评估会低估 0.1% FA 在百万盘上的运维爆炸。
- **Future work 1**：对 **未覆盖 failure 长尾** 做 error analysis：被漏报样本是否形成新 cluster，能否用增量 joint decision 挖掘而非全量重训。
- **Future work 2**：在 **仅 SMART、多厂商混合盘、边缘部署** 三类场景系统测量 BPD/JKE 各步退化幅度，建立 attribute 丰富度与 F0.5 的 calibration 曲线。
- **Future work 3**：将 weak decision 的健康风险因子（PCIe error 34×、bad block 60× 等）与 **主动迁移/限速/固件策略** 联动，量化「不换盘但降风险」vs「换盘」的 TCO，而非仅报告 failure rate 倍数。

## 相关

- **相关概念**：[[SSD]]、[[SMART]]、[[Telemetry]]、[[Random-Forest]]、[[SHAP]]、[[Downsampling]]、[[Apriori]]、[[Failure-Prediction]]
- **同类工作**：[[MVTRF-FAST23]]（multi-view temporal RF + SDE）、WEFR（DSN 21）、CNN-LSTM（[[FAST-20]] Lu et al.）、Alter et al. SC'19 RF、Zhang et al. FAST'23
- **同会议**：[[FAST-2026]]
- **对比**：FailureMiner 相对 MVTRF/WEFR 的核心差异是 **边界保留下采样 + 决策级联合挖掘**，而非更多 temporal view 或 attribute ranking