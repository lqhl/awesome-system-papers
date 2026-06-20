---
type: paper
name: Gohil-UncertaintyAware
full_title: "When Machine Learning Isn't Sure: Building Resilient ML-Based Computer Systems by Embracing Uncertainty"
authors: [Varun Gohil, Nevena Stojkovic, Noman Bashir, Sundar Dev, Gaurang Upasani, David Lo, Parthasarathy Ranganathan, Christina Delimitrou]
venue: MLSys
year: 2026
tags: [ml-for-systems, uncertainty-estimation, ood-detection, graceful-degradation, production-ml]
source_pdf: "[[182be0c5cdcd5072bb1864cdee4d3d6e.pdf]]"
source_md: "[[182be0c5cdcd5072bb1864cdee4d3d6e]]"
---

# When Machine Learning Isn't Sure: Building Resilient ML-Based Computer Systems by Embracing Uncertainty (MLSys 2026)

> **一句话总结**：提出 uncertainty-aware 框架：推理时用 uncertainty 作 misprediction 代理，超阈值拒绝 ML 输出并降级 fallback；三个 case study（Google 服务器容量规划 / Sinan 集群调度 / Heimdall SSD 准入）证明 **最佳 estimator 与 fallback 集成方式都取决于任务延迟与设计约束**，而非单一万能方案——微秒级只能 distance-based（~7 µs），毫秒级固定模型选 conformal（QoS violation −2–11%），分钟级可换 BNN（OOD uncertainty 15.6 vs ID 1.2 GBps）。

## 问题与动机

ML 已广泛用于 workload scheduling、资源管理、编译优化，但生产部署仍受 **generalizability** 制约：OOD 样本、分布漂移、对抗输入会让模型静默失效，且后果严重（如调度器一次误判可连带违反多个共置应用的 QoS）。传统周期性重训练是 **reactive** 且计算昂贵，在线学习在训练周期间仍允许错误发生。

理想「generalizability oracle」——在采用预测前就知道对错——不可能，因为判断准确性需要事后 ground truth。论文核心 claim：**prediction uncertainty 与 misprediction rate 强相关**，可在推理时 proactive 量化并拒绝不可靠输出，再 **graceful degradation** 到安全 fallback（启发式、人工审查、simulator 等），把 brittle ML 系统变成可降级的 resilient 系统。

两个必须回答的设计问题：(1) 如何检测不确定？(2) 不确定时做什么？论文主张答案都 **context-dependent**，需结合任务的 runtime 与 design constraints 选型。

## 关键观察 / 隐含假设

- **观察 1：Uncertainty 是可行的 misprediction 代理，但非 ground truth。** 三个 case study 中，高 uncertainty 与 OOD 场景下的高 error 同步出现（如 Amber 服务器 47% MAPE + uncertainty 15.6；Sinan 负载超训练分布后 violation 从 5% 升至 22%）。框架把 uncertainty estimation 当作「generalizability oracle」的实用替代。
  - **依赖假设**：估计器输出的 uncertainty 与真实 error 在目标 workload 上保持单调相关；阈值可校准到可接受的误拒/漏拒率。
  - **可能失效场景**：calibration set 与生产分布脱节、对抗样本刻意压低 uncertainty、或 ID 数据上模型本身高方差时，proxy 相关性可能断裂。

- **观察 2：没有 universal best uncertainty estimator——延迟预算是硬筛子。** BNN 在分钟级 server design 可行（~600 ms/batch），在 Sinan 毫秒调度需 variance propagation 仍占 760 MB / 98.3% CPU；Heimdall 微秒准入下 BNN 单次 238 µs（33× 于 distance），conformal 扫 1000 calibration 样本 ~500 µs，仅 distance-based ~7 µs 可用。
  - **依赖假设**：任务端到端延迟预算在选型前已知且稳定；estimator 开销相对主推理可忽略或必须并行隐藏。
  - **证据强度**：强。Table 3 与 §4.3 直接测量三类 estimator 跨数量级 latency 差异。

- **观察 3：Model modifiability 决定能否用 Bayesian 路线。** Sinan 模型 pre-trained 且固定，BNN 虽 violation 最低（再降 4–16%）但违反「不换模型」约束；必须用 conformal prediction 或 distance-based 等 **model-agnostic** wrapper。
  - **依赖假设**：生产系统常已有部署模型，retrain/replace 成本高于 post-hoc wrapper。
  - **可能失效场景**：greenfield 设计可自由选架构时，BNN 的高 efficacy 可能被低估；论文在 Sinan 上为对比而替换 BNN，已标注 infeasible。

- **观察 4：Fallback 集成方式由延迟与 fallback 成本共同决定。** 分钟级 server provisioning 可 **sequential** 跑昂贵 simulator；毫秒级 Sinan 必须 **parallel** 执行 AutoScaleOpt heuristic，因 inference 主导端到端时间；微秒级 Heimdall 对不确定请求才 hedging，避免全量双发。
  - **依赖假设**：fallback 结果与 ML 预测在决策语义上可替换；并行 fallback 的额外资源消耗可接受。
  - **可能失效场景**：fallback 本身有副作用（hedging 双倍 I/O、heuristic 过度扩容）；论文在 Sinan 上测了 CPU 分配但未量化 fallback 的长期资源浪费。

- **假设 1**：Unit-consistent uncertainty（BNN 标准差、conformal interval 与目标同单位）让领域专家能设阈值；distance-based 高维 latent distance 只能 empirical 取 90th percentile。
  - **证据强度**：中。§4.1/§4.2 展示 GBps/ms 阈值语义；distance 的「非直观性」是设计 tradeoff 而非缺陷，但增加运维校准成本。

- **假设 2**：OOD 与「分布相近的 unseen」可区分——BNN 对 Jade/Opal（分布类似训练集）低 error + 低 uncertainty，对 Amber 高 error + 高 uncertainty。
  - **证据强度**：中。仅在一个 Google fleet 子集与 Sinan 单一应用上验证；边界 case（轻微 shift 仍低 uncertainty）论文未系统刻画。

## 核心方法

框架在 ML 推理路径插入 **uncertainty estimator → decision module**：超阈值则拒绝预测并触发 fallback。评估三类 estimator：

**Bayesian Neural Networks**：输出 posterior variance；可用 MC sampling（server case，直到分布 std 收敛 ≤5% 变化）或 single-pass variance propagation（Sinan 对比实验）。高 efficacy、unit-consistent，但 latency/内存最高，且 **非 model-agnostic**。

**Conformal Prediction**：model-agnostic，finite-sample coverage 保证；用 calibration set 算 non-conformity score，推理时按 L2 距离加权取 (1−α) quantile 得 prediction interval。Sinan 用 residual、α=0.1、relative uncertainty 阈值 15%（≈5 ms）；与 Sinan 推理 **并行** 计算，超阈值切 AutoScaleOpt。

**Distance-based**：算输入（或 CNN latent）到训练集 centroid 的距离（Euclidean / Mahalanobis）；超训练集距离 90th percentile 判不确定。Heimdall 上仅增 ~7 µs；不确定时 **hedging**（双 SSD 并发，先返回者胜）。

三个 case study 刻意覆盖 classification/regression、静态/动态环境、微秒–分钟级延迟：

1. **Server resource capacity provisioning（Google）**：1.2M profiling 点、四种 seen 服务器训练，预测 90th percentile memory bandwidth；未见 Amber MAPE 飙至 47%（seen 上简单模型更准）。新设计任务可改架构 → 2-layer BNN + MC；不确定时人工审查或 simulator。
2. **Cluster resource management（Sinan）**：复现 DeathStarBench SocialNetwork + CloudLab；负载每 2 min +50 用户，6 min 后 OOD。固定模型 → conformal 最优（violation −2–11%，KB 级 calibration 存储）。
3. **Storage I/O admission（Heimdall）**：Chameleon 双 Samsung 970 PRO，Alibaba/Microsoft/Tencent trace；微秒预算 → Euclidean distance + selective hedging（仅 5.22% 请求不确定，99.9th latency −56%）。

## 设计取舍

- **拒绝预测换系统安全**：主动放弃 ML 收益以避免 silent failure；代价是 fallback 频率与质量决定上限——AutoScaleCons violation 最低但 CPU 超配 3×。
- **Estimator 精度换延迟**：distance-based efficacy 低、无理论保证，但是微秒任务的唯一选项；conformal 需独立 calibration set，小数据 regime 是 barrier。
- **Parallel fallback 换零额外延迟**：Sinan 同时跑 heuristic，不增加 1 s 调度周期内的决策时间；代价是每次调度都消耗 fallback 算力，即便 ML 最终被采纳。
- **Sequential expensive fallback 换资源**：server design 仅在不确定时启动 simulator，节省大量算力；代价是 designer 工作流被中断，需人工介入。
- **边界条件**：框架在「有合理 fallback + 可校准 uncertainty」时优雅；无安全默认策略（必须做决策的实时控制）或 fallback 比 ML 更差时，拒绝机制可能放大损害。

## 实验与结果

- **Google server provisioning**：六种回归模型在 seen 上 MAPE 低，unseen Amber 全线恶化；BNN seen 8.7% MAPE / uncertainty 1.2 GBps，Amber 47% MAPE / uncertainty 15.6；两服务器训练时 Jade/Opal 仍低 error（12.8%/11.8%）+ 低 uncertainty。
- **Sinan cluster**：baseline 在 OOD 段 violation 5%→22%；uncertainty-aware 工作流均优于 baseline Sinan 且 CPU 相近；conformal 在多种 diurnal/random 负载下稳定；BNN violation 再降 4–16% 但需换模型 + 760 MB / 98.3% CPU。
- **Heimdall I/O**：Mahalanobis tail 最优（99.9th −57%）但 17.25% 请求不确定；Euclidean 平均 −12%、99.9th −56%，仅 5.22% 不确定，综合更优。
- **Threshold ablation**：Sinan 上提高 uncertainty 阈值 → fallback 率降、OOD violation 升（Figure 9）；说明阈值是运维关键旋钮。
- **Practitioner guidelines（§5.3）**：微秒延迟 → distance；固定模型 → conformal；约束宽松 → BNN；重 fallback sequential，轻 fallback parallel。

## Critical Analysis

### 论证链条

主链条清晰：generalizability failure 有生产证据（§4.1.3 Google unseen server、§4.2.3 Sinan OOD load）→ uncertainty 可作 runtime proxy（三案例 error/uncertainty 共变）→ 不同约束下 estimator/fallback 选型不同（Table 3 + 三案例各取最优）→ graceful degradation 改善指标。

较弱环节是 **从三个异构任务归纳 general framework**：三案例任务类型、标签空间、fallback 质量差异大，「无 universal estimator」结论支撑充分，但 **跨任务迁移的决策流程**（如何在新任务上选 estimator + 阈值 + fallback）仍偏经验，guideline 是规则表而非自动选型器。

### 假设压力测试

**Uncertainty–error 相关性**：论文展示共变但未给 calibration curve（如 rejection rate vs saved error 的 ROC）。阈值 15%、90th percentile 多为手工/经验选取 — **推断**生产需 per-task 再校准。

**Fallback 质量下界**：Sinan 用 AutoScaleOpt（可过度或不足扩容）；Heimdall hedging 假设双 SSD 足够；server case 假设 designer 会处理不确定配置。若 fallback 系统性更差，框架只保证「不用坏 ML」不保证「系统更好」— **论文未量化 fallback regret**。

**Distribution shift 类型**：Amber 是硬件分布 shift；Sinan 是应用行为 shift（每请求返回 post 数增加）；Heimdall 是 trace 加压。对抗 shift、渐进 drift、多模态混合 shift 下 distance centroid 可能失效 — **部分覆盖**。

**LLM 扩展（§6）**：声称 logit/self-consistency 可扩展，但无实验 — **未来工作**，非本文证据。

### 实验可信度

Case study 选择代表性强，覆盖 ML-for-systems 谱系（回归/分类、静态/动态、μs–min 延迟）。Google 案例有生产规模数据（1.2M 点、fleet profiling），说服力强。

弱点：(1) Sinan/Heimdall 为学术复现，规模小于 Google；(2) 缺少 end-to-end **cost of uncertainty**（误拒率、fallback 开销、人工延迟）统一 metric；(3) conformal 与 distance 对比在 Sinan 上公平，但 BNN「最优却不可行」使 efficacy 上限已知却不可部署；(4) 未与 online retraining 组合实验，尽管 Discussion 声称可互补。

### 系统性缺陷

- **只回答「if」不回答「why」**：拒绝预测不解释根因，不利于模型修正；feature/neuron attribution 仅 future work。
- **运维复杂度**：每任务需选 estimator、calibration set、阈值、fallback；distance 阈值无领域语义，增加监控负担 — **论文承认 unit-consistency 差异，未给自动化阈值学习**。
- **Calibration 维护**：动态环境（Sinan）下 calibration set 会 stale；论文用固定 3850 样本，未评估 refresh 策略。
- **多 estimator ensemble / 级联**：未探索 cheap distance 预筛 + expensive conformal 二级 — **论文未讨论**。
- **与部署系统集成**：Discussion 提及 SOL `AssessModel`，但无生产集成案例 — **论文未证明** operator 工作流。

## 局限与 Future Work

- **局限 1**：框架缓解 misprediction 影响，不阻止 misprediction；高 uncertainty 仍意味着部分请求走次优路径。
- **局限 2**：不解释模型为何失败，难指导 targeted retrain 或 feature 修复。
- **局限 3**：三个案例的 fallback 质量与任务强绑定，框架本身不保证 fallback 最优。
- **局限 4**：未系统评估 uncertainty 引导的 retraining（Discussion 提出用 uncertainty 触发训练与选样本，但无实验）。
- **Future work 1**：在 production trace 上测量 rejection rate、fallback cost、误拒造成的 QoS/latency 损失，建立 per-task 阈值自动校准。
- **Future work 2**：将框架接入 SOL 类部署流水线（`AssessModel` + `TakeAction`），验证 operator 能否用单一 uncertainty score 统一决策。
- **Future work 3**：对 LLM-for-systems 任务（code gen、config synthesis）用 logit/self-consistency uncertainty，对比与传统 estimator 的 latency–efficacy 曲线。

## 相关

- **相关概念**：Conformal-Prediction、Bayesian-Neural-Network、OOD-Detection、Graceful-Degradation、Predictions-with-Rejections
- **同类系统**：Sinan（微服务资源管理）、Heimdall（SSD I/O admission）、Guardrails/Safeguards、Data-Slicing、Neural-Network-Verification-for-Systems
- **同会议**：[[MLSys-2026]]