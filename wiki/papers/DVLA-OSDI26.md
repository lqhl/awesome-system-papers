---
type: paper
name: DVLA
full_title: "DVLA: Dynamic VM Lifetime Aware Scheduling for Drifting Lifetime Distributions and Long-Lived VM Placement Debt (Operational Systems)"
authors: [Zhengtong Zhang, Zihan Xu, Zhidong Hu, Yanbo Shan, Fei Peng, Suhong Chen, Kaiyuan Shen, Xiangyun Kong, Handu Ding, Bing He, Binda Ma]
venue: OSDI
year: 2026
tags: [cloud-scheduling, virtual-machine, lifetime-prediction, bin-packing, operational-systems]
source_pdf: "[[osdi26-zhang-zhengtong.pdf]]"
source_md: "[[osdi26-zhang-zhengtong]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向生命周期漂移与长寿 VM 放置债务的动态调度

> **原题**：DVLA: Dynamic VM Lifetime Aware Scheduling for Drifting Lifetime Distributions and Long-Lived VM Placement Debt (Operational Systems)

> **一句话总结**：DVLA 的关键认识不是“把 VM 生命周期预测得更准”，而是静态 lifetime bucket 会随 cluster 和时间失效，少量被放散的长寿 VM 还会长期钉住机器，形成 online scheduler 无法自行偿还的 [[Placement-Debt|放置债务]]；系统用动态 affinity group、非对称 online placement 和维护期 live migration 共同治理，在 23 个生产 cluster trace 中比 LAVA 多提高 0.6 个百分点 packing density，并在 Alibaba Cloud 七个月部署中把 long-lived packing density 相对模型化反事实提高 1.19 个百分点。

## 问题与动机

Alibaba Cloud 的数百万次日常分配呈现极端长尾：生命周期少于一天的 VM 占 96% 请求，却贡献少于 2% core-hours；生命周期超过一个月的 VM 只占 2.5% 请求，却贡献 93% core-hours（§2.1，图 1）。调度器如果只看请求数，会把注意力放在大量很快结束的 VM 上；真正决定机器多久不能回收的，是少量长寿 VM。

这也改变了 [[Bin-Packing|装箱]] 目标。把一个短 VM 填到已有长寿机器上，单机利用率会立即变高；但把第一个长寿 VM 放到一台短寿机器上，可能让整机数月不能回收。论文测到，剩余寿命超过 720 小时和 8,760 小时的 VM 在其所在机器上平均只占 57.7% 和 39.8% cores，说明它们已广泛散开（§3.2，图 4）。

已有 lifetime-aware scheduler 还有两个问题。第一，LA-Binary、NILAS、LAVA 固定使用同一组 bucket，但每个 cluster 的 lifetime distribution 不同并随时间漂移；按“没有一个 bucket 占至少 95% 才算 policy 可用”的口径，LA-Binary 几乎在所有 cluster 失效，NILAS/LAVA 分别在 85%/74% cluster 失效，60 天后仍适用的比例只剩 55%/44%（§3.1，图 3）。第二，即使长寿 VM 误判率只有 5%，在独立误差假设下，一台机器放入 14 个“预测为短”的 VM 后，至少混入一个真实长寿 VM 的概率已超过 50%。在线贪心决定一旦做出，旧 VM 不会因为后续模型变准而自动移动。

## 关键观察 / 隐含假设

- **观察 1：应该按 core-hours，而不是请求数定义重要 lifetime class。** DVLA 每天统计正在运行 VM 在各寿命 class 上的 core 比例，让占资源多但请求少的长寿类别进入 affinity group；这比只看 arrival distribution 更贴近机器占用（§4.2）。
- **观察 2：第一个长寿 VM 的边际伤害最大。** 机器从零个变为一个 long-lived assignment 后，recycle frequency 和 occupied duration 明显恶化，继续增加的边际变化较小。系统因此优先限制“有长寿 VM 的机器数量”，而不是平均分散它们（§3.2，图 4）。
- **观察 3：online prevention 与 offline correction 缺一不可。** 40% VM 因硬件依赖、workload 或 policy 限制无法迁移，offline-only 追不上新债务；online-only 又不能修复历史误放。合成 trace 中只有两者结合能压低 stranded machine（§3.3，表 1、图 5）。
- **假设 1：历史身份和行为能预测未来寿命。** Initial model 最重要特征包括 `image_id`、`user_id` 和 operator；remaining model 更依赖 user history 与 VM 已存活时间（附录 A，图 15–16）。这对 recurring workload 有效，却可能在新租户、新镜像、行为突变或隐私限制下失效。
- **假设 2：CPU packing density 能代表基础设施收益。** PD 只计算 allocated cores 与非空机器总 cores；论文 cluster 内机器同构，因此没有把 memory、network、[[NUMA|NUMA]]、storage、accelerator、power 或 license 约束纳入债务。
- **假设 3：少量 live migration 的净收益为正。** PDRE 只搬 migratable VM，设 migration budget 并要求 net-positive placement，生产中还搭载现有 maintenance；但论文没有公开 migration traffic、downtime、energy 和 workload interference 的成本模型。

## 核心方法

**两级 One-vs-Rest 预测。** 每个 lifetime threshold 由独立 binary classifier 处理，生产 bucket 为 0–1 小时、1 小时–1 天、1–7 天、7–30 天、30 天–1 年和超过 1 年。Initial model 只用创建请求里的 19 个静态特征，满足 online path 少于 100 ms 的预算；Remaining model 加入 survival history、用户统计和近期 CPU/memory 指标，供每日 tagging 与 offline scheduler 使用（§4.1、附录 A）。

**Dynamic Affinity Grouping。** 每个 cluster 每天生成 lifetime cores-distribution vector，先计算它与 EWMA workload baseline 的 cosine-distance error，再用历史 `ewma_error` 和 `ewma_stddev_error` 标准化为非负 drift score。正文 §4.2 把 daily drift score 简写成 cosine distance，附录算法 3 才给出上述标准化公式；这里以更具体的算法为准。状态机依次经过 Warmup、Stable、Observation、Cooldown：异常持续一个 observation window 且平均分数超过 confirmation threshold 才更新；否则把这段数据补学回 baseline。更新时按 core 占比从高到低选择 lifetime class，直到累计覆盖 95%，同时至少保留配置的 `N_min` 个 class（§4.2、附录 B，算法 1、3–4）。

**Debt-Aware Placement Policy（DAPP）。** 系统先把每台机器上 VM 的 lifetime index 按 cores 加权平均，再映射到当前 affinity group 最近的 category，平局取更长的一类。Placement score 只重罚“长 VM 放到短机器”这一方向：普通 mismatch 的权重示例为 0.8，超过一个月的 VM 降至 0.2；相反方向不受同等惩罚。已有散乱 cluster 使用 WAVG 避免单个长 VM 把几乎所有机器标成长寿，空 cluster 则先用更激进的 MAX，第一次 group update 后切到 WAVG（§4.3、§6.3，算法 2）。

**Placement Debt Rectification Engine（PDRE）。** Remaining model 找出预计还会运行超过一个月、位于 stranded machine 且允许迁移的 VM。PDRE 先挑 stranded VM 最少、最容易清空的机器，再优先搬 remaining lifetime 最长的 VM，destination 选择已有长寿机器；含不可迁移长寿 VM 的 source 被排除。生产实现把它并入 machine maintenance 和 evacuation，不单独触发一套迁移系统（§4.4、§5.1）。

**低延迟状态管理与降级。** Initial prediction cache 命中率超过 90%；miss 访问 autoscaling inference service。服务不可用时先做本地 profile matching，准确率约为主模型的 75%，仍失败则保守标为 1 个月–1 年。Machine tag 可略旧，系统只在空机放入第一个 VM、释放最后一个 VM、迁走最后一个长寿 VM 时做 event update，再用每日全量更新校准，作者称这样把更新量降一个数量级（§5.1–§5.2，图 7）。

## 设计取舍

- **分类换取抗长尾能力。** Bucket 比精确 regression 稳定，也方便独立增减 threshold；代价是临界点两侧的 VM 会被当成不同类别，而且六个生产阈值仍是环境特定参数。
- **慢确认换取少振荡。** 生产参数为 20 天 observation window、alarm 2.0、confirmation 3.0，cost function 给 false positive 70% 权重；它偏向稳定，却可能用数周响应真实突变。
- **WAVG 换取成熟 cluster 的可区分性。** WAVG 在已有 cluster 比 MAX 多 0.5 个百分点 PD gain，但可能淡化“一个超长 VM 已经钉住机器”的事实；空 cluster 中 MAX 反而多 0.2 个百分点（§6.3，图 10）。
- **非对称 affinity 换取更高风险聚集。** 把长寿 VM 集中到更少机器有利于回收其他机器，也会集中同一 customer 或相似 workload。明确 anti-affinity 始终硬执行，但软指标 VRAR 在模拟和生产分别增加 0.3/0.28 个百分点。
- **维护期 correction 换取低额外操作风险。** PDRE 可复用已有 drain 和 live migration 流程，因此作者称没有额外 scheduling overhead；但这也限制了偿债速度，并把效果绑定到 maintenance 频率。
- **缓存与稀疏更新换取可能陈旧。** 高 cache hit 和 selective tag update 保住 online latency，却允许 category 短时过期；论文报告 99% VM tag、98% machine tag coverage，没有给 staleness distribution 或错放损失。

## 实验与结果

- **模拟设置与公平基线**：event-driven simulator 与生产 scheduler 共用核心逻辑，重放 23 个 Alibaba Cloud cluster 的两个月 trace；cluster 为 200–2,200 台机器、12 K–800 K 个 VM event。对比非 lifetime-aware production policy、2 小时阈值的 LA-Binary 和 LAVA；各系统使用同一 production predictor，LAVA 另获 7 天 threshold 上 99% precision、90% recall 的 regression model，强于其原论文报告的 70% recall（§6.1）。
- **端到端模拟**：按 cluster size 加权后，真实预测下 DVLA 相对 production baseline 的 PD 增加 1.5 个百分点，LAVA 为 0.9、LA-Binary 为 0.6；PDL 分别增加 0.9、0.4、0.1。DVLA 的真实预测结果还高于 LAVA oracle 的 1.4 个百分点；逐 cluster 比 LAVA 多 0.2–4.3 个百分点，平均多 0.6。VRAR 增加 0.3 个百分点，比 LAVA 多 0.1（§6.2，图 8）。
- **适应与消融**：60 天内 21/23 cluster 至少更新一次 policy；处于 Stable、Observation、Cooldown 的时间中位数分别为 23.3%、43.3%、33.3%，更新间隔中位数 28 天、IQR 28–29 天。Oracle 下完整 DVLA 的 PD gain 为 2.00 个百分点；按 waterfall 顺序移除 dynamic grouping、PDRE、daily tagging、event tagging 后再损失 0.34、0.31、0.21、0.14 个百分点。因为是顺序移除，这些值不是互相独立的边际贡献（§6.3，图 9、11）。
- **预测敏感性**：long-lived recall 从 40% 提到 100% 时，真实误差系列的 PD gain 从 1.02 增到 1.66 个百分点；即使 recall 只有 40% 仍有正收益。它支持系统不会因单一误判立即失效，但误差是合成注入，且 earlier “14 个 VM”分析假设误差独立，不能覆盖 tenant-correlated error（附录 C.2，图 18）。
- **七个月生产运行**：Remaining/Initial model accuracy 为 92%/82%，VM/machine tag coverage 为 99%/98%，超过 98% 新 VM 被放到 lifetime category 不短于自己的机器。每天平均迁移 810 个 VM，其中修正 39 个误放长寿 VM；每个 maintenance task 平均让 PDL 增加 0.3 个百分点。Training 为每周 40 分钟的一台 16-core/64 GB 实例及每天并行 1 小时的五台 16-core/32 GB 实例；prediction cache miss P99 为 5 ms（§6.4）。
- **生产收益口径**：上线后 PDL 相对“由上线前 long-lived sale rate 与 PDL 关系外推”的 counterfactual 平均高 1.19 个百分点，VRAR 高 0.28 个百分点；stranded machine 比例从 25.3% 降至 21.3%，只含一个 long-lived VM 的机器从 4.3% 降至 3.5%，PD-Sensitivity 比 pre-DVLA、上一年同期与模拟 counterfactual 平均低 7.1 个百分点。这里没有随机 holdout cluster，论文的“节省数千台机器”也未给绝对 fleet 分母（§6.4，图 12–14）。

## 论断—证据表

| 论断 | 直接证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 固定 lifetime bucket 对空间和时间漂移很脆弱 | LA-Binary 几乎全部 cluster 不适用；NILAS/LAVA 60 天适用率降至 55%/44%（图 3） | “适用”由单 bucket 是否达到 95% 定义，不等于实际 PD 一定退化 | 中强 |
| 放置债务是独立于预测精度的系统问题 | 第一个 long VM 显著延长占用；40% VM 不可迁移；online/offline 单独策略都积债（图 4–5、表 1） | online/offline 对比是 trace-driven empty-cluster simulation | 中强 |
| DVLA 比强 lifetime-aware baseline 提高 packing density | 真实预测下 PD gain 1.5 个百分点，LAVA 0.9；23 cluster 均多 0.2–4.3（图 8） | 专有两个月 trace、CPU-only PD、作者 simulator | 强（所测环境） |
| 动态 grouping 和 offline correction 都影响结果 | 顺序消融分别带来 0.34 与 0.31 个百分点损失（图 11） | waterfall 非正交，后项效果依赖前项已移除 | 中 |
| 七个月生产部署产生了 1.19 个百分点 PDL 因果收益 | 部署后实际值持续高于 sale-rate counterfactual，stranded 比例同时下降（图 12–14） | 无随机对照；反事实来自上线前相关关系，可能受同时期变化混淆 | 中 |

## 批判性分析

### 论证链条

论文把 lifetime scheduling 从“预测准确率”重新表述为两个控制问题：policy 必须跟随 distribution drift，过去的错误必须被显式偿还。生产数据证明长寿 VM 主导 core-hours 和 machine pinning，23-cluster simulator 证明四个组件组合提高 PD，七个月部署再证明系统能持续运行，这条链比只做离线模型实验完整。需要收紧的是因果语言：模拟里的 0.6 个百分点对 LAVA 优势证据强；生产 1.19 个百分点来自模型化 counterfactual，而不是未部署对照组，不能排除 demand composition 或同期 scheduler 变化。

### 假设压力测试

最重要的测试是制造相关误差和快速漂移：让某个大 tenant、image 或 region 的长寿 VM 同时被错判，观察非对称 affinity 是否一次污染大量机器；让 distribution 在 20 天 observation 内反转，记录检测延迟、错误 policy 持续时间和 cooldown 锁死。资源层面还应构造 CPU 合得上但 memory、network 或 NUMA 冲突的 VM，检查 PD gain 是否只是把瓶颈转移。迁移测试则要包含高 dirty rate、不可迁移比例上升与 maintenance 下降时 PDRE 能否追上新债务。

### 实验可信度

两个月、23 个真实 cluster、七个月 operational deployment、明确 baseline 配置和预测公平化，让结论具有少见的生产价值；论文也报告 VRAR、training/inference overhead、tag coverage 与 prediction sensitivity，不只展示 PD。可复现性却弱：trace、fleet 绝对规模、simulator 和成本没有完整公开；ablation 是顺序 waterfall；生产没有 randomized holdout。所谓 100% availability 与“没有用户投诉”是运维观察，不等价于没有 tail-latency、migration pause 或 failure-domain 风险。

### 系统性缺陷

DVLA 优化的是同构 cluster 内的 CPU core packing，现实 cloud 的多维资源与 placement constraint 可能让 lifetime affinity 排名失真。系统依赖 `user_id`、`image_id` 和历史行为，既有 cold-start 和隐私问题，也可能把 tenant-specific drift 放大成相关误判。DAPP 通过聚集长寿 VM 提高可回收性，同时提高共同故障暴露；VRAR 只衡量超过 soft threshold 的共址比例，没有直接测故障损失。PDRE 对 40% 不可迁移 VM 无能为力，且复用 maintenance 让偿债能力受外部流程限制。最后，大量阈值仍是 Alibaba 环境手调，所谓“dynamic”主要是约每 28 天重选 group，并没有消除静态 bucket 和经验参数。

## 局限与后续工作

- 做 cluster-level randomized rollout 或保留长期 holdout，分离 DVLA、需求变化和其他 scheduler 更新的生产因果影响。
- 公开脱敏 trace、simulator 口径和按 cluster 绝对 machine savings；同时报告 confidence interval，而不只给加权平均。
- 把 memory、network、NUMA、storage、energy 与 accelerator 纳入多维 placement debt，验证 CPU PD 提升是否真的能关机。
- 量化 live migration 的网络量、dirty-page 重传、pause、能耗和 workload SLO，并研究 maintenance 稀少或 40% 不可迁移比例更高时的偿债上限。
- 针对新 tenant、行为突变、相关预测错误和敏感身份特征设计校准、隐私保护与 fallback；报告 per-tenant 错放和风险聚集。
- 缩短并在线验证 drift detection，给出 detection lag、false alarm、policy rollback 与振荡的完整控制指标。

## 相关

- **相关概念**：[[VM-Scheduling]]、[[Bin-Packing]]、[[Concept-Drift]]、[[Placement-Debt]]
- **相关系统**：LA-Binary、NILAS、LAVA、LARS
- **同会议**：[[OSDI-2026]]
