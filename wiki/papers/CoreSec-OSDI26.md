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
last_reviewed: 2026-08-14
---

# 允许拒绝归因的 Clos 网络根因分析（OSDI 2026）

> **原题**：The Abstention Protocol: RCA for Clos Fabrics (Operational Systems)

> **一句话总结**：大型 Clos fabric 总有少量坏链路和异常计数，旧式 weighted RCA 即使证据缺失或冲突也必须选一个“根因”，因而长期有 18%–22% false positive；CoreSec 用 PAM 风格的 requisite/required/sufficient/optional flag 组合 telemetry agent，不确定时明确 abstain，再用拓扑传播规则选层级，三年 712,345 个 Azure incident 中把 false positive 降至少于 1%、近半年 abstention 降到 1.5%，但对照来自系统上线前且 postmortem ground truth 不是盲标。

## 问题与动机

大型云网络不是“平时全部健康，事故时只有一个部件坏”。在一个区域中，光模块漂移、CRC 增长、link flap、switch reboot 和滚动升级一直存在；论文给出的正常背景是任意时刻约 0.3%–1% 链路有 loss、flap 或 optics degradation（§2）。Clos 的多路径会绕开多数故障，所以客户 incident 发生时，监控往往同时看到许多无关的 unhealthy entity。

Pingmesh 能确认哪些端到端路径有 loss 或高延迟，NetBouncer 能推断哪些 link/device 当前不健康，但 on-call 真正要回答的是：**这一次特定客户 incident 是哪一个实体造成的？** 早期 Azure RCA 给每个 telemetry agent 一个权重，再选总分最高的实体。不同 failure mode 需要不同证据，missing data 又仍会被压成一个分数，结果是 false positive 长期在 18%–22%，调好一种故障会调坏另一种。

CoreSec 把这个问题重新定义为证据组合，而不是分数排序。agent 的证据有不同角色：有的缺失就不能继续，有的单独出现便足够，有的必须共同满足。若证据仍不完整或冲突，系统不猜，而是输出 abstention 和可审计的上下文，阻止自动 mitigation 并交给人工。

## 关键观察 / 隐含假设

- **观察 1：agent 的可靠性取决于 failure mode，不是一个全局常数。** active probe 覆盖快但可能稀疏，device counter 直接但噪声大，traffic-derived signal 反映客户影响却依赖流量，infrastructure signal 又可能很慢（§2）。
  - **依赖假设**：每个 agent 的语义、freshness 和适用故障面可以稳定地写成 flag 与阈值。
  - **可能失效**：多个 agent 实际共享同一上游数据、拓扑或时钟，common-mode error 会让“多 agent 同意”失去意义。
- **观察 2：Clos 层级决定故障的空间形状。** 单个 cable/TOR 通常只影响局部，而 T1 故障会让其 fan-out 中大量 TOR 同时异常；这让跨层 suppression 比单纯排名更自然（§5）。
  - **依赖假设**：topology inventory 正确，症状能在 16 分钟窗口内展开，并且根因大体落在 cable、TOR、T1、T2 或 cluster 这些 failure surface。
  - **可能失效**：多个独立故障同时发生、软件/config 问题跨层传播、inventory 已过期，或 incident 被错误切成一个时间窗口。
- **观察 3：在高风险自动化中，错误归因比“不归因”更危险。** 错误 mitigation 可能扩大 outage；结构化 abstention 至少告诉 on-call 哪些证据缺失（§7）。
  - **依赖假设**：人工队列有能力接手约 1.5% 的 persistent abstention，而且不同 incident 的误报与漏报成本差别不需要显式建模。
- **观察 4：少量拓扑 threshold 在不同 Azure 环境中保持稳定。** P2.15、two-thirds fan-out 和 4% cluster drop 在 sensitivity curve 的 knee 附近，并在十个 sensitivity deployment 及更广泛生产环境中未重新调参（图 5、§9–10）。
  - **依赖假设**：未来 Clos fan-out 与流量传播规律不会发生结构变化。
- **假设 1：postmortem 标签可以作为 RCA ground truth。**
  - **证据强度**：中。规模很大，但 CoreSec 输出对 postmortem 作者可见，论文明确承认没有 blinded evaluation。

## 核心方法

**1. incident 触发五条并行配置。** CoreSec 不是持续检测器；外部 alert 触发后，它分别运行 server–TOR cable、TOR、switch–switch cable、T1、T2 五个 configuration，再用 hierarchy heuristic 合并。系统每 5 分钟重跑一次，最长观察 16 分钟；最慢被采用的 agent 约 13 分钟才到，最后留一点晚到余量（图 2、§5–6）。

**2. 用 control flag 表达 agent 的证据角色。** `sufficient` agent 满足条件时立即 vote；`requisite` agent 失败或缺少关键 fresh data 时立即 abstain；所有 `required` agent 必须 pass，否则最终 abstain；`optional` 只作辅助。每个 agent 都有独立 freshness window，旧数据不参与。论文伪代码按固定顺序执行这些短路规则，因此 configuration 的可解释性来自“哪一条 flag 决定了结果”，而不是不透明总分（§3）。

**3. 为 noisy signal 留出 abstention region。** 每个原始 signal 设健康阈值 `θ−` 和故障阈值 `θ+`：低于前者判健康，高于后者判故障，中间值不作答。missing、stale 和相互冲突的 evidence 因此不会被强制压成 healthy/unhealthy。当前 persistent abstention 中约 60% 来自 telemetry gap、39% 来自证据冲突、1% 来自 multi-cluster 或 datacenter-wide event（§3、§7）。

**4. configuration 按 failure surface 选 authoritative agent。** server–TOR 使用 port counter、NIC failsafe、[[RDMA|RDMA]] timeout；TOR 汇总 CRC、host failure 和 control-plane event；switch cable 依赖 active path probe 与 T1 counter；T1 使用多 uplink probe；T2 使用 end-to-end multipath probe（表 1）。同一 agent 在一个 configuration 中可以是强证据，在另一个 configuration 中只是辅助，这正是 PAM analogy 的价值。

**5. 用拓扑规则决定归因层。** server impact 先按 TOR 聚合：数量超过所有 TOR 的 97.85th percentile，也就是 P2.15，并且至少 20% server 受影响，才把 TOR 当候选。若某 T1 fan-out 至少三分之二 TOR unhealthy，则 T1 归因压制其下 TOR candidate。cluster aggregate probe drop 超过 4% 时判 cluster-level event（§5）。独立的不同层故障可以保留；较高层满足 sufficiency 后，较低层不再重新出现。

**6. 输出结构化 trace，并给出一个有限形式化。** 16 分钟后仍没有足够证据时，系统输出 abstention、缺失 agent、partial candidate 和时间戳，暂停自动 mitigation。Appendix A 把已经归一化的 `H/U/I` 状态定义为三值 merge：`U` 吸收其他状态，只有全 `H` 才为 `H`，其余冲突为 `I`，并证明这个运算 associative。这个证明适用于该简化 merge，不直接覆盖 control flag 的固定短路顺序或跨层 hierarchy heuristic。

## 设计取舍

- **abstention 换 precision。** CoreSec 不再每次都给根因，减少错误自动化，却把约 1.5% incident 留给人工并延后处置。
- **离散 flag 换可控与可解释。** operator 能读懂 requisite/required/sufficient，但表达不了连续 confidence，也依赖长期人工治理 flag assignment。
- **固定拓扑规则换部署稳定。** 三个 threshold 三年未改，系统简单；新 failure mode 仍要新增 agent，非 Clos 根因或 correlated multi-fault 不自然。
- **16 分钟 convergence 换稳定性。** 容纳异步 telemetry，代价是不能做秒级 mitigation；一旦高层 attribution 锁定，后来的低层证据不会撤回它。
- **历史 ground truth 换生产规模。** postmortem 能覆盖 70 万 incident，但不是 blinded label，也无法公开复现。
- **适用边界。** 最适合已有多个成熟 telemetry agent、拓扑层次明确且 false mitigation 成本高的 incident-level RCA。

## 实验设置与有效性边界

- CoreSec 连续部署超过三年，覆盖 60 多个 Azure region、400 个 datacenter、数十万 server 和数千 switch，共处理 712,345 个 network incident（§8、表 2）。
- “旧 weighted RCA”是 CoreSec 上线前、同一网络和同一 operations team 测得的历史 baseline，不是把两个系统并行跑在同一组 incident 上。表 2 把相同总数列在两边，但论文说明旧系统的 18%–22% 来自此前时期。
- ground truth 是 on-call engineer 写的 postmortem。CoreSec 上线后，labeler 能看到它的建议，可能产生 confirmation bias；论文没有盲标或 inter-rater agreement。
- 作者计划但尚未完成两个更强对照：在 CoreSec 之前的 incident 上 backtest 新逻辑，以及在 CoreSec postmortem set 上重新跑旧 weighted system（§8）。

## 实验与结果

- **归因质量**：相对历史 weighted baseline 的 18%–22% false positive，CoreSec current 在 712,345 个 incident 中少于 7,017 个，也就是少于 1%；约 701,660 个 incident（98.5%）自动归因，约 10,685 个（1.5%）abstain 并按 false negative 计（表 2）。这是前后时期比较，不是同集 A/B。
- **三年演进**：在 false positive 始终少于 1% 的同时，abstention 从上线首季度 10% 降到调优后的 5%，再降到最近六个月 1.5%，主要靠新增 agent 补 coverage gap，而不是放宽三个拓扑 threshold；明确 misattribution 约每季度一次（图 4、§8）。
- **错误自动化与人工成本**：表 2 报告 wrong mitigation 约 700 次，占 0.1%，manual RCA 从约 3 FTE-equivalent 降到 0；内部前后对比还称 mis-triggered mitigation 降低 80%、与错误归因相关的 customer complaint 降低 40%（§7–9）。后两个指标没有给绝对分母或同期对照。
- **收敛时间**：CoreSec 每 5 分钟重跑，约 99% incident 在前两次 rerun 内稳定，通常在 alert 后 10 分钟内返回；三年记录中没有观察到旧 voting/scoring 系统常见的 attribution oscillation（§6、§9）。这反映实现的单向 dominance 规则，不等同于根因一定正确。
- **根因分布**：自动归因的 incident 中，server–TOR/switch–switch cable 占 70%，TOR switch 占 28%，T1/T2/cluster-level 合计仅 2%（表 3）。高层样本很少，因此整体少于 1% 的 false positive 主要由低层常见故障决定。
- **threshold sensitivity**：十个 deployment 上，T1 fan-out 从 0.50 扫到 0.90 时约 0.66 的 total error 最低；cluster drop 在 3% 以下误报升高、5% 以上漏报升高，4% 位于 knee；server–TOR percentile 从 P1 扫到 P5 时，约 97%–98% 最好（图 5、§9）。论文未公开每个 deployment 的样本数与置信区间。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| flag composition 加 abstention 比旧 weighted RCA 少误报 | 表 2：18%–22% 降至少于 1% | Azure 三年；历史前后对比、非同集 A/B、非盲标 | 中到强 |
| abstention 可在不提高 FP 的情况下逐步降低 | 图 4：10%→5%→1.5%，FP 始终少于 1% | 通过增加 agent 演进；不是固定系统版本的对照 | 强 |
| 三个 topology threshold 在多环境有稳定 knee | 图 5：0.66、4%、约 97%–98% | 十个 Azure deployment；内部数据未公开 | 中 |
| 系统能稳定收敛而不来回改归因 | §6/§9：99% 前两次 rerun 稳定，未观察到 oscillation | 单向 cross-layer dominance 本身会锁定高层结果 | 中到强 |
| Appendix A 证明整个 CoreSec order-invariant | Appendix A 只证明简化 `H/U/I` merge associative | 未建模 requisite/sufficient 短路、optional 或 hierarchy rule | 弱 |

## 批判性分析

### 论证链条

论文最有说服力的部分是问题选择：背景故障很多、强制归因代价高，所以把 abstention 设计成第一等输出非常合理。三年 FP/FN 时间线和 downstream operation 也说明系统确实有价值。不能直接推出的是“二十倍改善完全来自 PAM algebra”：同一时期还新增了 agent、清理了循环依赖、改变了 topology heuristic 和运维流程，旧系统又不是同集并行 baseline。

### 假设压力测试

如果 NetBouncer、counter 和 topology service 共用一个错误 inventory，多个 agent 会一致地指错实体，离散 consensus 无法发现 common-mode error。两个独立 TOR fault 恰好落在同一 T1 下，也可能触发高层 suppression。反过来，真实 T1 fault 若 16 分钟内不足三分之二 TOR 报异常会被漏掉，这正是论文报告的主要 false negative 来源。跨 region config error 或 datacenter-wide event 则被有意交给人工。

### 实验可信度

712,345 个 incident、三年、60 多 region 的生产规模非常少见，运营指标比小型 synthetic RCA benchmark 更真实。主要威胁也被作者坦诚写出：postmortem 非盲标；历史 baseline 与新系统不在同一 incident set；内部 telemetry、label 和阈值样本无法复现；没有 confidence interval、抽样审计一致性或 academic baseline。80% mitigation 与 40% complaint 的下降提供旁证，但仍可能受同期运营变化影响。

### 形式化与实现之间的缺口

Appendix A 的 `⊕` 只处理已经归一化的 `H/U/I`，不包含四种 control flag。正文伪代码又按固定顺序短路：如果一个 `sufficient pass` 和一个 `requisite fail` 同时存在，谁先执行会影响结果；`optional` 在展示的伪代码中也没有改变任何变量。因此 associativity 不能证明完整 configuration 与跨层 heuristic 的 order-invariance。论文的生产实现可以靠固定 order 保持 deterministic，但“异步到达下顺序无关”的形式化覆盖范围应收窄。

### 系统性缺陷

CoreSec 的可靠性依赖 agent owner 正确维护 schema、freshness、threshold 和 flag。论文讲述过一次真实 circular dependency：下游系统把旧 CoreSec attribution 又作为新证据，曾掩盖其他故障数小时；这说明 configuration governance 本身是关键 failure surface。论文较少讨论 topology service stale、agent rollout 版本不一致、control-plane HA、权限审计和错误规则回滚。单向高层 dominance 消除 oscillation，也可能把一个过早的错误高层归因锁到窗口结束。

## 局限与后续工作

- **局限 1**：历史 baseline、非盲 postmortem 和同步期系统演进使 18%–22% 到少于 1% 不能当成随机因果实验。
- **局限 2**：形式化 merge 没有覆盖完整 PAM flag stack 和 hierarchy heuristic。
- **局限 3**：高层 T1/T2/cluster 根因只占 2%，multi-fault、novel failure 与 telemetry outage 常被 abstain 或漏掉。
- **局限 4**：数据与 agent 都是 Azure 内部系统，外部无法复现阈值和 confusion matrix。
- **后续工作 1**：对上线前 incident backtest CoreSec，并在同一个 blinded postmortem sample 上并行运行 weighted baseline；报告按 failure layer 分层的 precision、recall、abstention 和置信区间。
- **后续工作 2**：把 requisite/required/sufficient/optional 与 cross-layer dominance 纳入一个完整状态机模型，模型检查所有 agent order、missing/stale 组合，验证 determinism、non-oscillation 和错误高层归因能否撤回。
- **后续工作 3**：重放 double fault、stale topology、common-mode agent outage 和 circular feedback，测错误 suppression、persistent abstention、自动 mitigation 安全性和规则回滚时间。
- **后续工作 4**：按 incident severity、mitigation blast radius 和 engineer queue 建 decision-cost metric，对比固定 abstention 与 cost-aware policy 的总损失。

## 相关

- **相关概念**：[[Root-Cause-Analysis]]、[[Gray-Failure]]、[[Clos-Network]]、[[Abstention]]
- **同类系统**：[[Pingmesh]]、[[NetBouncer]]
- **同会议**：[[OSDI-2026]]
