---
type: paper
name: LMETRIC
full_title: Simple is Better: Multiplication May Be All You Need for LLM Request Scheduling
authors: [Dingyan Zhang, Jinbo Han, Kaixi Zhang, Xingda Wei, Sijie Shen, Chenguang Fang, Wenyuan Yu, Jingren Zhou, Rong Chen]
venue: OSDI
year: 2026
tags: [llm-serving, request-scheduling, kv-cache, load-balancing, production-systems]
source_pdf: "[[osdi26-zhang-dingyan.pdf]]"
source_md: "[[osdi26-zhang-dingyan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 简单乘法用于 LLM 请求调度（OSDI 2026）

> **原题**：Simple is Better: Multiplication May Be All You Need for LLM Request Scheduling

> **一句话总结**：LLM 集群调度同时受 KV cache 命中和实例负载影响；LMETRIC 用“路由后新增 prefill token 数 × 实例 batch size”作为无超参数分数，在 16 张 H20 GPU、聊天与 coding-agent trace 上降低平均 TTFT 最高 92%，并在 BAILIAN 数百 GPU 的 canary 中降低 TTFT 39%、TPOT 51%。

## 问题与动机

LLM 请求路由有两个相互牵制的目标。把共享前缀送到拥有对应 KV cache 的实例，可以减少 prefill 计算；把请求均匀分布到实例，则能避免某些实例排队和 decode 变慢。vLLM-v1 主要按 batch size 做负载均衡，忽略 cache affinity；只追求命中率又会把请求集中到少数实例。

已有方案用加权和、阈值过滤或在线 simulator 合并两个信号。加权和需要按 workload 调参，且最优权重可能随负载变化；过滤方案在触发时完全放弃其中一个目标；simulation 方案则需要按模型、硬件和部署重新校准。论文的问题是：能否只用便宜、直接可观测的指标，同时保留两种目标的效果。

## 关键观察 / 隐含假设

- **观察 1：只做负载均衡会丢失显著的 cache 收益。** 在 Qwen3-30B 的 ChatBot trace 上，加入 KV-aware 路由后平均 TTFT 降低 84%，TPOT 降低 17%（图 7）。
  - **依赖假设**：请求前缀存在可复用性，且本地命中明显便宜于重新计算。
  - **可能失效场景**：前缀高度随机、cache 很小或远程 KV cache 访问成本接近本地命中时，cache-aware 信号的价值会下降。
- **观察 2：KV 命中率和 batch size 的加权和存在 workload-specific knee。** ChatBot trace 的较优权重约为 0.7，继续增大到 0.9 会造成实例 prefill 工作量失衡（图 9–11）。
  - **依赖假设**：固定权重无法覆盖请求到达率、输入长度和前缀分布随时间变化的 workload。
- **观察 3：新增 prefill token 数比命中率更能反映路由后的工作量。** 两者命中率相近时，P-token 仍能利用排队中的 prefill token，P50/P95 TTFT 分别低 14.4%/42.8%（图 18）。
  - **可能失效场景**：实例内部执行策略使 token 数与实际 prefill 时间严重脱钩，或模型结构、硬件代际改变了这个关系。
- **假设 1：decode 负载可由 batch size 近似。** 论文认为 decode 时间随 batch size 更稳定，而总 token 数还会受 KV cache 影响（图 19）。这是在 PD-colocation、同模型同 GPU 的集群设定下得到的经验假设。
- **假设 2：KV hotspot 足够少，或能被检测。** 乘法在“请求类别占比不超过其 cache 覆盖占比”时不会制造热点失衡（式 2、图 20）。论文在 trace 中未观察到该条件被破坏，但在一段生产 thinking workload 中发现了失败窗口，并用两阶段 detector 回退到负载均衡策略（图 21）。

## 核心方法

LMETRIC 为每个候选实例计算两个指标：P-token，即请求路由到该实例后需要新做的 prefill token 数，已扣除 KV cache 命中并计入排队的 prefill 工作；BS，即实例当前 batch size。调度器选择 `P-token × BS` 最小的实例（图 17）。P-token 越小表示 cache 利用越好，BS 越小表示 decode 负载越低。

乘法不需要线性组合中的权重。比较两个实例时，乘法分数保留了“一个指标变好、另一个指标变差时进行折中”的性质；论文的解释是，原本需要调节的比例在实例间比较时被隐去。该结论不是对任意指标都成立，因此论文分别选择了 P-token 和 BS，而不是直接复用命中率和总 token 数。

指标工厂由 Rust router 实现，沿用实例响应中的状态信息，并通过统一 API 支持 vLLM、BAILIAN、Dynamo、llm-d、Preble 和 PolyServe 等策略。这样做隔离了策略差异与 router 实现差异，也避免 Python 路由器吞吐不足影响对比（§3）。

对于 KV hotspot，第一阶段按请求类别监控请求流行度与 cache 覆盖的比例；违反式 2 时发出告警并暂时过滤拥有热点前缀的实例。第二阶段只在后续连续请求持续偏好热点实例时介入，从而避免把必要的 cache affinity 一律关闭（§5.2）。

## 设计取舍

- **简单性换取模型精确度**：不需要 per-model、per-hardware simulator，也不需要离线权重搜索；代价是 P-token × BS 只是近似，ToolAgent trace 上 llm-d 的 simulator 在 TTFT 上略优。
- **局部 cache affinity 换取集群状态依赖**：P-token 需要知道请求前缀命中情况和排队 prefill 工作，router 与实例之间必须持续交换状态。
- **稳定的 BS 指标换取目标范围限制**：BS 适合论文关注的 PD-colocated 场景；PD-disaggregation 中 prefill 和 decode 可分别调度，适用关系不同。
- **检测器换取额外状态追踪**：热点检测只跟踪高命中率请求以限制开销，但漏报、误报及检测滞后对短 burst 的影响没有完整量化。

## 实验与结果

- 在 16 个实例、16 张 NVIDIA H20 GPU、Qwen3-30B/Qwen2-7B 和四类真实 trace 上，LMETRIC 的 TTFT/TPOT CDF 整体优于 vLLM、Dynamo、llm-d 和调参后的 BAILIAN 策略（图 22）。ChatBot 上相对 vLLM，平均 TTFT 降低 92%，平均 TPOT 降低 24%；相对第二优的 llm-d，P99 TPOT 降低 13%。
- 在不同请求到达率下，LMETRIC 保持领先；ToolAgent 上平均 TTFT 比 llm-d 高约 10%，但 TPOT 低 30%，并取得最低 TPOT（图 23）。
- 相对 Preble，ChatBot 上平均 TTFT/TPOT 分别降低 56%/8%，P99 TTFT/TPOT 分别降低 45%/16%（图 26）。Preble 大部分时间落入线性组合分支（图 27）。
- 相对 PolyServe，LMETRIC 的 TTFT 和 TPOT 均更低；PolyServe 为 autoscaling 保留负载梯度，只使用部分实例，LMETRIC 则把负载分散到 16 个实例（图 28）。两者优化目标并不完全相同。
- P-token 替代 `1-KV-hit-ratio` 后，P50/P95 TTFT 分别降低 14.4%/42.8%（图 18）；BS 替代总 token 数也更好（图 19）。
- BAILIAN 的 Qwen3.5-27B 生产 canary 将 1/3 流量送入 LMETRIC 集群，双方按 GPU 配置相同 reqs/GPU；LMETRIC 平均 TTFT 降低 39%，平均 TPOT 降低 51%（图 29）。具体集群配置未公开。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 乘法同时保留 KV affinity 与负载均衡收益 | 图 22、图 24–25 | 16 H20 GPU；Qwen2/Qwen3；四类 trace | 强 |
| P-token 比命中率更适合作为 cache 指标 | 图 18 | 主要展示 Qwen3-30B ChatBot；作者称其他 trace 趋势一致 | 中 |
| 乘法无需 workload-specific 超参数 | §5、图 11–12、图 15 | 指标和实例状态仍需工程接入；未证明任意模型/硬件 | 中 |
| 生产部署改善服务质量 | 图 29、§6.3 | Qwen3.5-27B；数百 GPU；配置与原始数值受限 | 中 |
| hotspot 失败可提前检测并缓解 | 式 2、图 20–21、§5.2 | 生产中展示一类 thinking workload；检测开销和误报率未充分报告 | 中 |

## 批判性分析

### 论证链条

论文的主链条较闭合：KV 命中减少 prefill 工作，BS 近似 decode 负载，乘法把两者放进同一排序分数，端到端结果同时改善 TTFT 与 TPOT。P-token 的选择尤其重要，因为它把排队 prefill 工作纳入 cache-aware 指标。乘法“超参数自动消失”的解释依赖排序比较，而不是声称两个物理成本可以被精确相乘。

证据仍主要来自单模型、同构 GPU、PD-colocated 集群。论文把生产 canary 作为外部验证，但没有公开完整请求率、cache 容量、实例数和置信区间，因此难以判断收益中有多少来自特定部署条件。

### 假设压力测试

若一个热门前缀只存在于很少实例，而请求短时间集中到该前缀，P-token 的下降可能压过 BS 的上升，形成热点。论文给出了必要条件和两阶段修复，但第二阶段的连续请求阈值仍是设计参数，且没有系统性报告在更多 adversarial trace 上的误报、漏报和恢复时间。

BS 作为 decode 负载代理在当前测试模型上成立，不代表对长输出、小 batch、不同 attention 实现或异构 GPU 都成立。PD-disaggregation、跨实例 KV fetch、动态 autoscaling 和多模型混部也可能改变指标含义。

### 实验可信度

作者把各 baseline 放入同一个 Rust router，改善了实现公平性；但同时重实现闭源或不同目标的调度器会引入实现选择。Dynamo、BAILIAN、Preble 的超参数按 workload 调到最佳，而 LMETRIC 不调参，这符合论文要比较的运维成本，却不等价于统一配置下的部署比较。PolyServe 的目标是满足 SLO 并形成 autoscaling 梯度，与 LMETRIC 的低延迟目标不同，结果应理解为目标取舍而非全面淘汰。

### 系统性缺陷

router 必须获取每个实例的 cache 匹配结果、P-token 和 BS；大规模集群上的状态新鲜度、通信开销和故障处理只做了概述。论文未详细讨论 router 重启、实例状态丢失、cache eviction 竞态、租户隔离和公平性。生产结果使用 dashboard 截图，缺少公开的尾延迟分布与成本数据。

## 局限与后续工作

- **局限 1**：评测集中于同构、单模型、PD-colocated 部署；异构 GPU、跨模型路由和 PD-disaggregation 只在讨论部分推断。
- **局限 2**：乘法的失败边界依赖请求类别和 cache ownership 的在线估计；论文未给出完整的检测 CPU、内存和网络开销。
- **局限 3**：生产 canary 的详细配置、绝对延迟和统计显著性不可见，难以复核 39%/51% 收益。
- **后续工作 1**：在公开的 hotspot adversarial trace 上测量 detector 的误报率、漏报率、恢复时间及对 P99 TTFT/TPOT 的影响。
- **后续工作 2**：在异构 GPU、远程 KV cache 和 PD-disaggregation 下重新校准工作指标，验证乘法是否仍比 simulator 或自适应加权更稳健。

## 相关

- **相关概念**：[[KV-Cache]]、[[LLM Serving]]、[[Request Scheduling]]
- **同类系统**：[[vLLM]]、[[Preble]]、[[PolyServe]]、[[Mooncake]]
- **同会议**：[[OSDI-2026]]
- **源码**：[blitz-router](https://github.com/blitz-serving/blitz-router)
