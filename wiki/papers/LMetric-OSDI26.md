---
type: paper
name: LMetric
full_title: "Simple is Better: Multiplication May Be All You Need for LLM Request Scheduling"
authors: [Dingyan Zhang, Jinbo Han, Kaixi Zhang, Xingda Wei, Sijie Shen, Chenguang Fang, Wenyuan Yu, Jingren Zhou, Rong Chen]
venue: OSDI
year: 2026
tags: [llm-serving, request-scheduling, kv-cache, load-balancing]
source_pdf: "[[osdi26-zhang-dingyan.pdf]]"
source_md: "[[osdi26-zhang-dingyan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用一个乘积调度 LLM 请求

> **原题**：Simple is Better: Multiplication May Be All You Need for LLM Request Scheduling

> **一句话总结**：LLM router 既要复用 prefix [[KV-Cache|KV cache]]，又不能把请求堆到少数 instance；LMETRIC 用“路由后的待处理新 prefill token 数 × 当前 batch size”作为无权重 score，在 16 张 H20 的真实 trace replay 中相对 [[vLLM]] 把 mean TTFT/TPOT 降低 92%/24%，并在数百 GPU 的生产 canary 中相对旧 scheduler 降低 39%/51%。

## 问题与动机

Cluster-level LLM router 每来一个请求就要选一个 serving instance。只做 load balancing 会错过 [[Prefix-Caching|prefix KV cache]]：请求若被送到已有相同 prefix 的 instance，prefill 可以跳过命中的 token。只追求 KV hit 又会反复选择少数 instance，排队和 decode batch 失衡，最终 TTFT、TPOT 都变差。

现有方案大致有三类。线性组合把 KV 指标和 load 指标加权相加，但两个指标量纲不同，weight 还随 workload 变化；论文测得 ChatBot 的较优 weight 是 0.7，API trace 是 0.55。Filter-based 方法先按 batch imbalance 决定是否放弃 KV locality，仍要调 threshold，而且一旦触发就完全忽略 KV 收益。Simulation-based 方法预测每个 instance 的 TTFT，理论上能综合更多状态，却要为 model、GPU、engine 和 deployment 校准 simulator；即使 well-tuned，约 10% 请求仍有大于 20% 的预测误差（§4，图 11–16）。

LMETRIC 的目标很窄也很实际：在同一 model、同一种 GPU、prefill/decode colocated 的 instance cluster 内，找一个简单、不按 workload 调组合权重、同时兼顾 KV locality 和 load 的 routing score。

## 关键观察 / 隐含假设

- **观察 1：乘法保留两个目标，但公共 weight 会消失。** 若把两个带权项相乘，所有 instance 的 score 都包含同一个 $\lambda(1-\lambda)$；做 pairwise comparison 时这个因子被约掉。这个推导说明乘积不需要线性组合的 weight，但不说明乘积等价于某个最优线性和，更不构成全局最优证明（§5，图 17）。
- **观察 2：KV 指标应使用 P-token，而不是 hit ratio。** P-token 是把新请求放到某 instance 后，需要实际 prefill 的新 token 加上其已排队 prefill work；它同时反映 cache miss 的计算量和 prefill queue。相同 BS 指标下，P-token 相对 `1 − KV hit ratio` 把 P50/P95 TTFT 再降低 14.4%/42.8%，两者的 hit ratio 却几乎相同（§5.1，图 18）。
- **观察 3：Decode load 用 batch size 比 total token 更合适。** Prefill work 已由 P-token 表示；decode 每 step 为 batch 中各 request 生成一个 token，因此当前 batch size 更直接反映 decode pressure。总 context token 与 decode time 并非稳定线性关系，尤其小 batch 时更弱（§5.1，图 19）。
- **观察 4：乘法的明确失败模式是 KV hotspot。** 若同一 prefix class 的请求占比远高于缓存该 prefix 的 instance 占比，低 P-token 可能一直压过增长的 BS，把请求继续送向 hotspot。四条主要评测 trace 没出现该条件，但作者在另一段 BAILIAN production workload 中找到一个反例（§5.2，图 20–21）。
- **假设 1：Cluster 内的 instance 同构。** 同一 score 默认每个 batch、prefill token 在不同 instance 上成本相近；论文只评估单 model、单 GPU type cluster，并用逻辑分 cluster 处理生产中的 model/GPU heterogeneity（§7）。
- **假设 2：Router 看到的状态足够新。** P-token、BS、KV map 从 engine response piggyback 更新；高 arrival rate、长请求或失联 instance 会让状态滞后。论文没有单独分析 stale indicator 对乘积决策的影响（§3）。

## 核心方法

**Indicator factory。** 作者实现一个独立 Rust router，与具体 [[LLM|LLM]] engine 解耦。Router 和每个 instance 保持长连接，从 response header 收集 batch、queue 和 KV metadata，在本地 factory 中维护每个 instance 的符号指标。每个 policy 都写成“可选 filter、计算 per-instance score、选 min/max”的短函数，便于在同一实现中公平比较不同 scheduler（§3，图 4）。

**乘法 score。** 对请求 $r$ 和 instance $i$，router 计算：

$$
\text{score}_i = P\text{-token}_i(r) \times BS_i
$$

其中 $P\text{-token}_i(r)$ 表示考虑本地 KV hit 后，该 instance 已排队以及新增加的 prefill token；$BS_i$ 是当前 batch size，主要近似 decode work。Router 选择 score 最小的 instance。高 KV hit 会降低第一项，重 load 会提高第二项，整个组合没有 workload-specific coefficient（§5，图 17）。

**Hotspot detector。** 请求按共享 KV prefix 分成 class $c$。在一个窗口内，设该 class 与其他请求的比例为 $x/\bar{x}$，缓存该 prefix 的 hit-instance 集合与 non-hit 集合规模比为 $|M|/|\bar{M}|$。若 $x/\bar{x}$ 不大于 $|M|/|\bar{M}|$，即使所有 class 请求都去 hit instances，它们平均也不会比 non-hit instances 更拥塞。反向不等式只是 hotspot 的必要条件，所以 detector 分两步：先发现比例越界；再等连续 $2|M|$ 个该 class 请求的乘积仍偏向 hotspot，才把这些 instance 暂时从候选中滤掉（§5.2）。

**适用范围。** 论文实现针对 prefill/decode colocated serving。作者认为 PD-disaggregation 更简单：prefill router 可直接按新 prefill token，decode router 按 batch/load；异构 model/GPU 先切成同构 cluster。远端 KV sharing 也不让 locality 失效，因为本地 hit 仍省掉传输和重复 cache 副本，但这些扩展只在 discussion 中分析，没有实验（§7）。

## 设计取舍

- **简单 score 换取有限表达力。** 乘积不需要 weight 或 latency simulator，但也不直接表达 GPU capacity、SLO、request priority、预计 output length、remote KV transfer 和 tenant fairness。
- **P-token 与 BS 分工换取同构假设。** 两个指标分别近似 prefill、decode work，解释清楚、收集便宜；当 model、GPU 或 engine config 不同时，同一个 token/batch 的成本不再可比。
- **乘法的放大作用换取 hotspot guard。** 正常 workload 中，任一项增大都会推高 score；若 P-token 为零或极小，BS 再大也难以抵消 KV attraction，因此必须有单独 detector 和 load-only fallback。
- **统一 Rust reimplementation 换取对比可控性。** 所有 baseline 共用高性能 router，避免原实现语言和 bug 干扰；但结果验证的是作者重实现的 policy，不一定等于原系统连同其 telemetry、simulator 和控制面的实际表现。
- **Latency 优先换取 autoscaling 目标。** PolyServe 会故意制造 load gradient，让空 instance 可释放；LMETRIC 均匀铺开请求，latency 更低，却未证明 GPU-hour 或 autoscaling 成本更好（§6.2，图 28）。

## 实验与结果

- **平台与 workload**：主要实验使用 16 张 NVIDIA H20-96GB，每张 GPU 是一个 vLLM-v1 instance；router 在 160-core Xeon、1 TB DRAM server 上运行。模型包括 dense Qwen2-7B 和 [[MoE|MoE]] Qwen3-30B；trace 为 ChatBot(Qwen)、Agent(Qwen)、BAILIAN 2025 年 11 月一天的 Coder，以及 ToolAgent(Kimi)。默认把 arrival rate 缩到 testbed 最大吞吐的一半；Coder 的绝对 rate 因保密被归一化（§4.1、§6）。
- **与 production scheduler 比较**：BAILIAN 和 Dynamo 的 weight 针对每条 workload 调到最佳，llm-d 使用作者扩展并校准过的 VIDUR simulator，所有 policy 都在 Rust router 中重实现。ChatBot/Qwen3-30B 上，LMETRIC 相对 vLLM 把 mean TTFT 降低 92%、mean TPOT 降低 24%；相对第二好的 llm-d，在 TTFT 相近时 P99 TPOT 再低 13%。四条 trace 的 CDF 中它都优于这些基线（§6.1，图 22、24–25）。
- **不同 request rate 与研究基线**：随 rate 升高，大多数 workload 上 LMETRIC 的优势扩大；例外是 ToolAgent，在某些 rate 下 mean TTFT 比 llm-d 高约 10%，但 TPOT 低 30%。ChatBot/Qwen3-30B 上，相对调优后的 Preble，LMETRIC 的 mean TTFT/TPOT 低 56%/8%，P99 TTFT/TPOT 低 45%/16%；它也在所有测试 rate 下比调优 SLO 的 PolyServe latency 更低，但 PolyServe 目标包含 autoscaling（§6.1–§6.2，图 23、26–28）。
- **指标选择与失败 case**：P-token 对比 hit ratio 的消融给出 P50/P95 TTFT 14.4%/42.8% 的改善，BS 也比 total tokens 更好。四条主 trace 的每分钟采样都满足论文给出的安全比例；一个额外 thinking workload 在约第 11 分钟出现共享长 prefix burst，LMETRIC 无法优于 load-balance-only。论文展示了 detector 规则，但没有单独报告启用两阶段 mitigation 后的端到端恢复曲线或 detector overhead（§5.1–§5.2，图 18–21）。
- **生产 canary**：2026 年 5 月的一天，Qwen3.5-27B 流量按 1/3 与 2/3 分到 LMETRIC 和旧 BAILIAN scheduler cluster，并把两边配置成相同 requests/GPU；LMETRIC 侧有数百张 GPU，其他规模细节保密。Internal dashboard 显示 mean TTFT/TPOT 分别降低 39%/51%。这是很有价值的真实证据，但只是单日 canary snapshot，没有 P99、误差、SLO attainment、GPU-hour 或随机化细节（§6.3，图 29）。

## 论断—证据表

| 论断 | 直接证据 | 评测边界 | 置信度 |
|---|---|---|---|
| P-token × BS 能同时利用 KV locality 与平衡 load | 四条 trace 的 TTFT/TPOT、KV hit 与 per-instance prefill load 对比 | 同构、PD-colocated、默认半载集群 | 强（该范围） |
| 乘法不需要 workload-specific 组合权重 | Score 只有 P-token 与 BS；对比的线性/filter baseline 均需逐 workload 调参 | Indicator 选择、hotspot detector 和部署参数仍需设计 | 强（组合权重） |
| 指标选择而非“任意两项相乘”很关键 | P-token 比 hit ratio 的 P50/P95 TTFT 低 14.4%/42.8%；BS 优于 total tokens | 详细消融只展示 ChatBot/Qwen3-30B | 中强 |
| LMETRIC 优于多类现有 scheduler | 同一 Rust framework 中比较 vLLM、BAILIAN、Dynamo、llm-d、Preble、PolyServe | 多个 baseline 是 policy reimplementation；目标不完全相同 | 强（实现内）/中（原系统） |
| 生产环境中仍有明显收益 | 数百 GPU canary 的 mean TTFT/TPOT 降 39%/51% | 单 model、单日、配置保密、无 tail/cost 数据 | 中强 |

## 批判性分析

### 论证链条

论文先把 KV locality 与 load balancing 的冲突量化，再逐类说明 weighted sum、filter 和 simulator 的工程代价，最后从实际 prefill/decode work 选择 P-token 与 BS。这个“问题—指标—简单组合—真实部署”的链条很有说服力。不过公共系数在乘积比较中约掉，只能证明乘积无须这个系数；它没有证明乘积与最佳线性组合等价，也没有证明 latency optimal。真正支撑方法的是四条 trace、消融和 canary，而不是一个一般性定理。

### 假设压力测试

最关键的反例就是 P-token 为零或极小的 hot prefix：乘积会持续偏爱 hit instance，即使 BS 已很大。应系统扫 prefix popularity、hit-set size、prompt length 和 burst duration，量化 detector 的 false positive、false negative、发现延迟和 fallback 抖动。还应让 telemetry 延迟多个 response、混合长短 output、开启 remote KV sharing，并在异构 GPU 上测试 score 是否仍保持正确排序。

### 实验可信度

真实 provider trace、dense/MoE 模型、多个 arrival rate、统一高性能 router 和生产 canary，比只用合成 Poisson workload 强得多。论文也诚实展示 ToolAgent 上 TTFT 输给 llm-d，以及 production trace 中的 hotspot 反例。限制是默认 trace 被缩放到半载，Coder rate 与 production cluster 细节保密；baseline 的原 router 被替换，llm-d simulator 也由作者扩展，端到端外部可复现性较弱。Production 图是 dashboard snapshot，没有置信区间、tail 或相同请求的 paired comparison。

### 系统性缺陷

LMETRIC 是单目标 latency router，不提供 SLO isolation、priority、fairness、autoscaling 或多租户约束。它把 prefill work 压成 P-token、decode work 压成 BS，无法表达 heterogeneous capacity、predicted output length、memory pressure 和 cache eviction cost。所谓“无参数”只准确描述两个指标的组合：hotspot 判定仍需要 class/window 状态，系统仍依赖 trace scaling、engine batching 和 cache 配置。更重要的是，论文提出的两阶段 hotspot mitigation 没有像主 score 一样经过完整端到端与生产消融，因此最危险的 fallback path 证据最少。

## 局限与后续工作

- 对两阶段 hotspot detector 做完整 trace replay 和 production shadow test，报告 overhead、误报、漏报、恢复时间和切换抖动。
- 把 capacity-normalized P-token/BS 扩到异构 GPU，并与 per-hardware simulator 比较，确认简单性是否仍成立。
- 加入 SLO、priority、tenant fairness 和 autoscaling cost，明确它们与最低 latency 目标冲突时的政策接口。
- 测量 stale KV/BS telemetry、cache eviction、remote KV fetch 和 PD-disaggregation 下的效果，而不只做定性讨论。
- 公开更完整的 canary 统计，包括 P50/P99、SLO miss、GPU-hours、请求随机分流方法和多日波动。

## 相关

- **相关概念**：[[KV-Cache]]、[[Prefix-Caching]]、load balancing、request routing、TTFT、TPOT
- **相关系统**：[[vLLM]]、[[Mooncake]]、Preble、NVIDIA Dynamo、llm-d、PolyServe
- **同会议**：[[OSDI-2026]]
