---
type: paper
name: AIRS
full_title: "AIRS: Scaling Live Inference in Resource Constrained Environments"
authors: [Nilesh Jagnik, Xiaohao Yang, Chelsea Chen, Tuan Do, GM Harshvardhan]
venue: MLSys
year: 2026
tags: [llm-serving, tpu, search-quality, batching, caching, quota-management]
source_pdf: "[[7f6ffaa6bb0b408017b62254211691b5.pdf]]"
source_md: "[[7f6ffaa6bb0b408017b62254211691b5]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# AIRS: Scaling Live Inference in Resource Constrained Environments (MLSys 2026)

> **一句话总结**：Google Search Quality 的 AI Rater Service（AIRS）在 TPU 预算远小于 rating 需求（日 1 亿+ PQ 请求、大部分 TPU 留给 live traffic）时，用 Rating Fulfillment 队列 + 共享 TPU 池 + quota 优先级 + 90 天客户端缓存（~40% hit）+ 默认 batch=12，把尖峰 QPS 压成 sustained load；AR1 模型 mean TPU duty cycle 峰值近 **1.0**，实际打到 model 的 QPS 仅峰值的 **1–4%**，80th percentile 成功率 **97.8%**。

## 问题与动机

Google Search Quality Evaluation 需对海量 query–result 对打 Page Quality（PQ）、Needs Met 等分，以驱动实验决策与产品发布。人工 rater 贵且慢（数天）；LLM autorater 可即时打分，且新 AI 产品（AI Overviews、AI Mode）与新 metric 进一步推高需求。顶层 PQ autorater  alone 日约 **1 亿+** rating 请求（数百实验 × 数十万 query × 每 query 数十 result）；另有数百个 cross-functional autorater（通常 <10B 参数）。

瓶颈是 **TPU 配额**：公司大部分 TPU 预留给 live user traffic，rating 预算常不够，高峰时 metric 算不出来、阻塞开发周期。早期离线 MapReduce pipeline 不可靠，产物与 Evaluation pipeline 集成差。AIRS（AI Rater Service）统一所有 autorater 的 live inference，目标是在资源受限下 **高可靠、低延迟** 产出 rating，供下游算 metric。

## 关键观察 / 隐含假设

- **观察 1：Evaluation workload 高度重复且尖峰明显。** 标准化 workflow 与 curated query set 导致多团队重复请求相同 search result 的 rating；同时数百实验并发产生 spiky QPS，而 TPU 在 idle 时 duty cycle 很低，尖峰直接打满 quota 会失败。
  - **依赖假设**：90 天内同一 (query, result, model) 的 rating 仍有效（PQ/Needs Met freshness window）；世界状态与模型版本变化可通过 fingerprint + model ID 失效缓存。
  - **可能失效场景**：强时效性 metric、频繁 model rollout、或 landing page 剧变时，长 TTL 缓存可能返回 stale rating；论文用 model ID 换版失效，但未量化 world-state drift 下的误差。

- **观察 2：Integrated 模式下「先 quota check 再 RPC」比 isolated 模式的被动 back-pressure 更能维持高 TPU duty cycle。** isolated 模式 aggressive 打到 model 报错才退；integrated 可 peek Model Management 的 quota/利用率，失败用更短 backoff，减少无效 RPC 与 retry 放大。
  - **依赖假设**：Model Management 侧的 utilization 信号及时、准确；Rating Fulfillment 与 Model Management 由同一团队运维。
  - **可能失效场景**：共享 TPU pool 内多 model 竞争时，单 model 利用率不能代表 pool 级瓶颈；信号延迟时 integrated 优势缩小。

- 观察 3：Post-cache 流量仍远大于实际 model QPS，说明 quota + retry 是主要 shaping 手段。 AR1 观测：incoming batched QPS 为峰值 30–100%，缓存后 20–40%，实际 model 仅 1–4%（Fig. 9）；大量任务在 queue 内 retry，而非均匀打到 TPU。
  - **依赖假设**：高优 evaluation（占 AR1 请求 80–90%）可 immediate execute；低优可容忍 5–10× 延迟与多次 retry。
  - **可能失效场景**：若低优任务也有硬 deadline，或 retry 无上限导致 queue 膨胀，尾延迟与失败率会恶化（90th percentile 失败率已达 **23%**）。

- **假设 1：Autorater 多为小 encoder-only 模型（<10B），batch inference 比单条更高效，默认 batch=12 普适。**
  - **证据强度**：**中**——符合 TPU serving 常识，但不同 autorater prompt 长度与外部数据依赖差异大，统一 batch 未必最优；论文未做 batch size sweep。

- **假设 2：PQ autorater 质量已达「平均 human rater」水平，infra 优化不会掩盖 rating 质量 gap（距顶尖 expert 仍有差距）。**
  - **证据强度**：**中**——训练 pipeline（Gemini fine-tune → lightweight encoder）与 validation pipeline 在正文仅简述；本文 focus serving，质量风险靠独立 monitoring pipeline 兜底，与 AIRS 吞吐 claim 弱耦合。

## 核心方法

AIRS 双组件架构（Fig. 3）：

**Rating Fulfillment**（Fig. 6 九步流水线）：
1. **Rating Fulfillment Server** 收 workflow 请求（①）→ archive 指纹查缓存（②）→ 命中则 State 表写 COMPLETED，未命中则入 **Queue** 并写 PENDING（③）
2. **Queue** 按 RID 限 outgoing QPS，RPC 失败则降 delivery rate；失败任务 exponential backoff 重试（上限 30 min），queue 无容量上限（④）
3. **Rating Generator** executor fleet：按 autorater API 拼 prompt、调外部数据、RPC model server（⑥）；integrated 模式下先 **Quota Management** check（⑤），失败短 backoff 回 queue
4. **Completion Checker** 周期扫 State，workflow 级任务全完成则通知下游算 metric（⑧⑨）；超时/部分失败可按 max duration 强制 complete，避免少数卡死任务阻塞全流程

**Model Management**：
- 长驻 TPU model server、UI 注册 serving config、auto-restart、动态 replica 伸缩
- **共享 TPU pool**：静态 pool size，按各 model utilization 动态再分配 replica；多 autorater 争用同一 pool 时做 cross-model balancing
- **Back-pressure**：按 evaluation priority、server load 限流；priority 也编码进 request context，model server 在资源紧张时 reject 低优请求

**Autorater 插件 API**：输入为 SRP scrape 数据，输出为自定义 protobuf；每个 autorater 有唯一 **RID**，Fulfillment 与 Model Management 分别按 RID 控流与记账。

**Integrated vs Isolated**：可单独用 Fulfillment（自管 model URL）或 Management（自管 hosting）；双组件联用为 integrated，quota peek 使 traffic shaping 更主动。

**客户端缓存（6.6）**：
- PQ/Needs Met：**90 天** freshness；用 query/result 关键字段 hash 成 lookup key，可扩展为 query-level 或整 prompt 级
- Key 含 **model identifier**，换模型自动失效；TTL 90 天 + buffer 后 storage 擦除
- 用廉价 storage/CPU 换稀缺 TPU；与 model server 侧细粒度缓存正交

**Batching（6.7）**：workflow 可设 batch size，默认 **12**，聚合多条 rating task 再送 Rating Generator，利于 TPU batch efficiency。

## 设计取舍

- **Client-side cache vs 实时推理**：~40% hit 显著降 TPU 负载，但牺牲对网页内容变更的即时响应；用 model ID + TTL 缓解，非强一致。
- **无限 queue + retry vs 快速失败**：提高最终成功率（80th p **97.8%**），但低优任务延迟 5–10×、90th p 失败率 **23%**；queue 无上限在持续过载时有堆积风险。
- **共享 TPU pool vs 专用池**：小流量 autorater 无法独享 TPU，共享提高利用率，但 AR1/AR2 等非线性 latency–allocation 关系（共享 pool 下 AR2 常被 scale down）说明 **隔离性弱**。
- **Integrated quota check vs isolated 被动 back-pressure**：吞吐更高、无效 RPC 更少，但耦合两组件、运维复杂度上升；部分 client 选 isolated 换简单性。
- **边界条件**：在 **Google 内部 Search Evaluation、TPU 长驻 serving、多 autorater 共用预算、latency 敏感 workflow 占主导** 时最优雅；通用 LLM API serving、GPU 集群、或强 tail-SLO 场景需重新设计 quota 与 cache 策略。

## 实验与结果

**设置**：顶层 autorater **AR1**，integrated 模式，8 天生产观测（2025 年 10 月）；QPS 图为相对峰值百分比；对比 autorater **AR2**（TPU 分配约为 AR1 的 **1/20**，共享 pool）latency（2026 年 3 月，相似 query 数 workflow）。

**TPU 利用率（Fig. 7）**
- Mean TPU duty cycle 峰值时段近 **1.0**；scale-up 新 TPU 时短暂下降；周末更低

**缓存（Fig. 8）**
- AR1 平均 cache hit rate **~40%**；低 hit 日（如 10/12）post-cache QPS 明显上升

**QPS 漏斗（Fig. 9）**
- Incoming batched QPS：峰值 **30–100%**（已除 batch size）
- Post-cache：**20–40%**
- 实际 model QPS：**1–4%**（quota check 主导；内部 retry 抬高 post-cache 计数）

**可靠性（2025 年 10 月）**
- 2 小时 deadline 后标失败
- 中位失败率 **0.8%**；80th percentile 成功率 **97.8%**；90th percentile 失败率 **23%**（大 evaluation 过载）

**延迟（Fig. 10）**
- AR1 P75 metric latency 常在 **~30 分钟**内
- AR2 P75 繁忙日可达 **33 小时**；非线性于 TPU 分配（共享 pool 动态 scale-down）
- Off-peak：AR2 latency 降、AR1 升（资源再分配）

**优先级**
- AR1 queryset 高优占 **80–90%**，收到即执行；低优 **5–10×** 慢，需多次 retry

**系统规模（正文）**
- 顶层 PQ：日 **1 亿+** 请求；数百实验/日
- 结论 claim：top-line rating 可在 **数小时内** 完成（相对人工数天）

## Critical Analysis

### 论证链条

链条：**测量** rating 需求远超 TPU 配额且 workload 重复/尖峰 → **设计** 缓存减载 + queue/backoff 整形 + quota 优先级 + shared pool 动态伸缩 + batching → **结果** duty cycle ≈1、40% cache hit、97.8%（80th p）成功率、高优 workflow 近实时。

最强支撑是生产 trace 上的 **QPS 漏斗分解**（Fig. 9）与 **duty cycle** 曲线，把各优化层的边际贡献拆开。integrated quota check 相对 isolated 的机制对比（§4.4、§6.3）逻辑闭合。

薄弱环节：论文是 **单公司单域**（Search Quality Evaluation）infra 经验；把「objectives 适用于大多数 resource-constrained live inference」（§3 开篇）外推为通用 recipe，缺少跨 workload 对照。AR1/AR2 对比说明共享 pool 下 latency 不可线性预测，但缺多 tenant 公平性定量指标。

### 假设压力测试

**Workload**：Curated evaluation query、重复 result 多 → 40% cache hit 可能 **高于** 开放域 serving；若请求高度 unique，收益骤降。数百 autorater 并存，但实验仅详报 AR1/AR2。

**硬件**：TPU 长驻 server；未讨论 GPU、CPU inference 或 spot/preemptible 资源。Model server 侧 reject 低优依赖 serving stack 支持 priority context，泛化性未验证。

**规模**：Queue 无上限在 **持续 100% 峰值 + 低 cache** 日（10/12）是否导致 metric latency 失控，论文用 AR1 P75「稳定」概括，但 90th p 23% 失败说明长尾仍脆。

**质量**：Serving 优化不改善 autorater 与 top expert 的 gap；缓存 90 天与 batch 可能引入 **rating 一致性** 与 **内容新鲜度** 风险，monitoring pipeline（Appendix C）在 wiki 层不可见，读者难评估 trade-off。

### 实验可信度

**优点**：8 天连续生产数据、相对 QPS 规避保密绝对值的同时保留漏斗比例；failure rate 分位数诚实披露 90th p 23%；AR1 vs AR2 展示 TPU 分配与共享 pool 的 non-linear latency。

**限制**：
- 仅 **1–2 个** top-line autorater 详报；数百 autorater 的 tail 行为未知
- 缺 **P99 metric latency**、queue depth 分布、单 evaluation 完成时间 CDF
- Cache hit 与 latency 相关性以 10/12 个案说明（§7.7），无回归或因果实验
- Baseline 是旧 MapReduce/offline pipeline，非业界通用 serving 框架（[[vLLM]]、[[SGLang]] 等），外部可比性有限
- 图表为相对单位，绝对吞吐、单请求成本、storage 开销未报

### 系统性缺陷

- **Queue 无界**：过载时内存、状态表膨胀与 Completion Checker 扫描成本；论文未讨论上限或 shedding 策略
- **尾延迟与公平性**：低优 5–10× 慢、高优 80–90% 流量 immediate——多用户同时跑大 evaluation 时的 **starvation** 仅靠「单用户多 evaluation 降流」部分缓解
- **故障恢复**：Model server auto-restart 有述；Queue/State 一致性、重复通知、exactly-once completion 语义未讨论
- **可观测性**：Duty cycle、cache hit、分阶段 QPS 有监控；per-evaluation 排队时间、retry 次数分布未公开
- **缓存正确性**：World-state 变更无自动失效，仅靠 TTL/model ID；强 factuality metric 可能不适用 90 天窗口
- **开源/复现**：内部系统，细节依赖 Google infra，外部只能借鉴设计模式

## 局限与 Future Work

- **局限 1**：聚焦 Search Quality Evaluation；通用 chat serving、多模态、或 streaming 场景未验证
- **局限 2**：Autorater 质量仍低于顶尖 human expert；infra 不能替代 quality monitoring 与 gold-set 建设
- **局限 3**：共享 TPU pool 使 latency–allocation 关系非线性，用户难以预估大 evaluation 完成时间
- **局限 4**：90 天 cache 与默认 batch=12 为静态策略，无 per-metric 自适应
- **局限 5**：论文未量化 archive storage 成本、hash collision 风险、或 Completion Checker 对超大 workflow 的扩展性

- **Future work 1**（论文结语）：将 caching、queuing、batching、quota、back-pressure、prioritization 经验推广到其他 **resource-constrained live inference** 域——需在非重复 workload 上重新测量 cache 与 quota 收益
- **Future work 2**（可验证延伸）：对 cache TTL、batch size、quota 参数做 **per-autorater** 自动调优，以 metric freshness SLO 为约束优化 TPU 成本
- **Future work 3**：在 queue 深度、retry 次数上设 **adaptive shedding** 或 deadline-aware scheduling，压低 90th p 23% 失败而不牺牲高优 SLO
- **Future work 4**：将 client-side fingerprint cache 与 [[Prefix-Caching]] / server-side KV 思路对照，量化 determinism vs freshness 的 Pareto 前沿

## 相关

- **相关概念**：[[Continuous-Batching]]、[[Prefix-Caching]]、Back-Pressure、Quota Management、Traffic Shaping
- **同类系统**：离线 MapReduce rating pipeline、通用 model hosting；生产 LLM serving 栈（[[vLLM]]、[[SGLang]]）解决不同 workload，可对照 quota/batching 思路
- **同会议**：[[MLSys-2026]]
- **对比**：专用 TPU 池 + 无限 retry queue（AIRS）vs 弹性 per-tenant 隔离 vs 无客户端缓存的 raw QPS 直通
