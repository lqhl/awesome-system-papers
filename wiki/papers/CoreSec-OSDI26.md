---
type: paper
name: CoreSec
full_title: "The Abstention Protocol: RCA for Clos Fabrics (Operational Systems)"
authors: [Madhava Gaikwad, Deepak Pandey]
venue: OSDI
year: 2026
tags: [datacenter-network, root-cause-analysis, clos, telemetry, gray-failure]
source_pdf: "[[osdi26-gaikwad.pdf]]"
source_md: "[[osdi26-gaikwad]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 以显式 Abstention 进行 Clos Fabric 根因分析（OSDI 2026）

> **原题**：The Abstention Protocol: RCA for Clos Fabrics (Operational Systems)

> **一句话总结**：Azure 旧式 weighted-score RCA 在 noisy/partial/asynchronous telemetry 下必选 culprit，误报 18%–22%；CoreSec 以 PAM-style required/sufficient/optional flag 和三值 abstention lattice 组合 agent，再用 Clos topology rule 消歧，三年处理 70 万余 incident 后把 false positive 降至少于 1%、近半年 abstention 降至 1.5%。

## 问题与动机

大型 Clos fabric 持续存在 CRC、flap、upgrade 和 intermittent packet corruption 等 background fault，ECMP path diversity 又使 fabric 仍能工作。当某个 customer service 告警时，Pingmesh、active probe、counter、traffic 与 control-plane telemetry 会同时指出许多异常 entity，大部分却与 incident 无关。

Azure 早期系统给每个 agent 分数并加权，最高者即根因。该方法在 evidence missing/conflict 时仍强制作答，调一个 failure mode 的 weight 又伤害另一个，false positive 长期在 18%–22%。CoreSec 的核心观点是 RCA 首先是证据 composition，而非 score ranking；不确定时应有可观测的 abstention。

## 关键观察 / 隐含假设

- **观察 1**：没有单个 telemetry agent 跨 failure mode 可靠；active probe、device counter、traffic signal 在 coverage、latency 与 noise 上互补（§1–2）。
  - **依赖假设**：agent verdict 可归一为 healthy/unhealthy/indeterminate，且其角色能稳定标为 requisite/required/sufficient/optional。
  - **可能失效场景**：agent error 强相关、共同依赖同一坏 telemetry source，或 adversarial/Byzantine signal。
- **观察 2**：Clos failure surface 有结构：server–TOR cable、TOR、switch cable、T1、T2 的 fan-out pattern 可用少量 topology threshold 区分（§4–5）。
  - **依赖假设**：拓扑 inventory 准确，incident failure 基本落在这五种单层 attribution，历史 threshold 可跨 deployment 泛化。
  - **可能失效场景**：多根因、configuration error、cross-layer software fault 或 topology metadata stale。
- **假设 1**：宁可 abstain 并交给人工，也不要 false positive 触发错误 mitigation；论文把 abstention 计为 false negative。
  - **证据强度**：强。三年 KPI 直接追踪 FP/FN trade-off，但不同业务的 abstention cost 可能不同。
- **假设 2**：post-incident 的 16 分钟 window 足以聚合最慢 agent 并对应同一 causal episode。
  - **证据强度**：中。线上 operational choice 稳定，但短 transient 或跨 window cascade 可能丢失。

## 核心方法

每个 telemetry agent 对候选 entity 输出 healthy、unhealthy 或 indeterminate，并带 PAM-style control flag。`requisite` 失败可立即否决，`required` 必须最终满足，`sufficient` 可在 required 均健康时单独确证，`optional` 只在没有更强 evidence 时参与。missing/conflicting evidence 不再被 score 掩盖，而是传播为 abstention。

CoreSec 为 server–TOR cable、TOR、switch-to-switch cable、T1 与 T2 建五个并行 configuration。configuration 内用三值 merge algebra 组合 agent，满足 associativity/order-invariance；新证据只会让 verdict 从 indeterminate 单调收敛到 healthy/unhealthy，适合 asynchronous arrival。

configuration 之间再用 topology-aware hierarchy rule 消歧。例如同一 T1 fan-out 至少三分之二 TOR 异常时，T1 attribution 抑制各 TOR candidate；server/TOR/cluster 层另有从多年 incident error curve knee 选择的 threshold。若没有 configuration 证据充分，CoreSec 显式 abstain，并把结构化 summary 交给 engineer。

系统由外部 detector 触发，对特定 incident 查询前后 16 分钟 telemetry；它复用 Pingmesh、NetBouncer、counter、control-plane 和 infrastructure summary，不承担 continuous anomaly detection。

## 设计取舍

- **abstention 换 precision**：显著降低错误归因/mitigation，但增加人工处理和未自动定位 incident。
- **离散 flag 换可解释性**：比 continuous score 稳定、无需频繁 retune，代价是不能表达细腻 confidence 与 context-dependent reliability。
- **topology heuristic 换简单部署**：少量 threshold 跨环境复用，难以覆盖 correlated multi-fault 与非拓扑根因。
- **post-incident batch**：容忍 asynchronous telemetry 并给稳定 RCA，不能用于 sub-second mitigation。

## 实验与结果

- CoreSec 在 Azure hyperscale Clos fabric 上连续运行三年，处理超过 700,000 incidents，跨多种 deployment 无需重新调权（§8）。
- 相对旧 weighted fusion，false positive 从 18%–22% 降到少于 1%，约二十倍改善；错误触发 mitigation 下降 80%（§8、表 2）。
- abstention 被保守计为 false negative；初期约 10%，通过补 telemetry/agent 后最近六个月降到 1.5%，体现 monotonic system evolution 而非降低 precision（§8）。
- 自动化替代约 3 个 full-time engineer 的 manual RCA 工作；attribution latency 主要由最慢 agent 决定，约为固定 telemetry convergence window（§1、§8–9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| abstention composition 大幅降低错误 RCA | §8、表 2：FP 18%–22% 到少于 1% | Azure 三年、70 万余 incident；与历史系统比较 | 强 |
| abstention 不必永久维持高 FN | §8：10% 降至近半年 1.5% | 通过新增/改进 agent 的长期演进 | 强 |
| algebra 在 async arrival 下 deterministic/order-independent | Appendix A：三值 lattice 的 associativity/absorption/consensus | 抽象 verdict model；不保证 agent 本身正确 | 强 |
| topology threshold 可跨部署复用 | §5/§8：多年部署称无需 recalibration | Azure Clos family，细分数据未公开 | 中 |

## 批判性分析

### 论证链条

“weighted system 在 ambiguity 下必答”与“引入 abstention”之间因果非常清晰，三年 FP/FN 时间线也证明 operational value。PAM analogy 提供简单 compositional interface，formal lattice 解释 determinism；但 accuracy 同时来自 algebra、agent flag assignment 和 topology heuristic，论文承认它们不可完全分离，不能把全部二十倍收益归于 algebra 单项。

### 假设压力测试

若多个 agent 共享 detector、clock 或 inventory，它们会一致地给出错误 verdict，consensus 反而强化错误。多 failure 并发时 topology suppression 可能把 leaf fault 吞并为 parent，16 分钟窗口也可能混合相邻 incident。abstention cost 在 customer outage 与后台 incident 间不同，固定 flag 没有纳入 severity/decision cost。

### 实验可信度

70 万 incident、三年 rollout、operational KPI 与人工负担是很强的外部有效性。主要缺口是内部 incident/label 无法复现，ground truth 如何建立、抽样审计的一致性、deployment composition 与 confidence interval 报告有限；旧系统到新系统也不是随机 A/B，期间 telemetry agent 与运维流程共同演进。

### 系统性缺陷

CoreSec 依赖 topology/telemetry freshness、agent ownership 与 flag governance。错误 configuration、schema change 或 silent agent outage 会系统性影响 RCA；论文讨论 freshness，却较少给出 control-plane HA、version rollout、audit trail 与 access control。系统只解释 network entity，不判定“network 非根因”之外的 application/storage cause。

## 局限与后续工作

- **局限 1**：单一 cloud provider，内部 telemetry 与 labels 不公开，难以独立复现。
- **局限 2**：五类 topology surface 和 threshold 难覆盖 concurrent/cross-layer fault。
- **局限 3**：abstention 被统一当 FN，未建模 incident severity 和人工成本。
- **后续工作 1**：构造 correlated double-fault、stale topology 与 common-mode agent failure replay，报告 attribution/abstention confusion matrix。
- **后续工作 2**：对 flag/threshold 变更做 shadow evaluation 与 counterfactual audit，量化每项机制对 FP/FN 的边际贡献。
- **后续工作 3**：引入 decision-cost-aware abstention：按 mitigation risk、customer impact 和 engineer queue 选择自动回答阈值，并用历史 incident 验证总成本。

## 相关

- **相关概念**：[[Root-Cause-Analysis]]、[[Gray-Failure]]、[[Clos-Network]]、[[Abstention]]
- **同类系统**：[[Pingmesh]]、[[NetBouncer]]
- **同会议**：[[OSDI-2026]]
