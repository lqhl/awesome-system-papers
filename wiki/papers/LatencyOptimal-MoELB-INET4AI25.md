---
type: paper
name: LatencyOptimal-MoELB
full_title: "Latency-Optimal Load Balancing for Distributed MoE Inference"
authors: [Venkata Pavan Kumar Miriyala, German Sviridov, Bingxu Chen, Haris Javaid]
venue: INET4AI
year: 2025
tags: [moe, llm-inference, expert-parallelism, load-balancing, ilp, gpu]
source_pdf: "[[inet4ai25-miriyala-latency-optimal-moelb.pdf]]"
source_md: "[[inet4ai25-miriyala-latency-optimal-moelb]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# LatencyOptimal-MoELB：分布式 MoE 推理的延迟最优负载平衡（INET4AI 2025）

> **原题**：Latency-Optimal Load Balancing for Distributed MoE Inference

> **一句话总结**：这篇论文的关键观察是 [[EPLB]] 这类 expert-to-device 负载均衡虽然能让 [[MoE]] expert load 接近均匀，但一次重平衡要移动约 12.8k-13.0k 个 expert，代价接近理想均衡收益的 10x；作者把均衡收益、expert 搬运和算法运行时间放进同一个 latency objective，用 ILP 给出模型内最优解，再用 O(E^2 log E) heuristic 把 expert moves 从 13036 降到 2440，使 DeepSeek-V3 的 MoE 执行延迟最高下降 12.5%，并把可接受的 LB 频率提高约 2x。

## 问题与动机

[[MoE]] 推理通过 sparse activation 扩展模型容量：每个 token 只路由到少量 FFN experts。问题是路由器学出的 expert specialization 会让不同 workload 激活不同 expert 子集；在 [[Expert-Parallelism]] 部署里，expert 被分散到多张 GPU 上，一旦热 expert 集中在少数 GPU，这些 GPU 就同时承担更多 compute 和 all-to-all communication，最终由最慢 GPU 决定同步 MoE layer 的整体延迟。

训练期的 auxiliary loss 或 routing bias 可以缓解 expert imbalance，但不能保证 inference workload 的实际 token-to-expert 分布始终均匀。系统层面的 E2D assignment 因此会在运行时重分配或复制 expert，例如 [[DeepSeek-V3]] 的 [[EPLB]] 根据近期 token 统计把 hot/cold experts 重新放到 GPU 上。这类方法的隐含目标通常是让每张 GPU 的 expert load 尽量均匀。

本文指出这个目标少了一半：对于线上推理，load balance 本身也在 critical path 上。复制或重分配 expert 意味着运行时搬运 expert weights；如果下一段 workload 很快漂移，或者搬运无法被隐藏，那么“更均匀的 placement”可能比不做 LB 更慢。论文因此把问题重写为 latency-optimal load balancing：不是追求最均匀的 expert placement，而是在 future MoE execution latency、expert movement latency 和 LB algorithm runtime 之间做联合优化。

这个 framing 很系统味：贡献不在于发现 MoE 有 imbalance，而在于把“E2D assignment 的收益”与“E2D assignment 的代价”放到同一目标函数里，并展示 SOTA baseline 在真实硬件上处在明显的 cost-benefit 失衡区间。

## 关键观察 / 隐含假设

- **观察 1：DeepSeek-V3 的 expert activation 在不同 domain workload 和 MoE layer 上明显偏斜。** Figure 2 展示 OpenOrca、MBXP、GSM8K 在 DeepSeek-V3 第 3、32、60 个 MoE layer 的 expert workload heatmap，少数 experts 在连续 forward passes 中反复成为 hot experts；Figure 3 进一步把这种 skew 映射到 8 GPU EP 部署中的 compute、communication 和 synchronization 延迟差异。
  - **依赖假设**：近期 token-to-expert 统计能代表接下来若干 iteration 的需求；否则基于历史统计的 E2D assignment 很快过期。
  - **可能失效场景**：多租户混合请求、conversation/code/math 交错 batch、prefill/decode 比例快速变化、serving scheduler 改变 batching 策略时，expert popularity 的半衰期可能短到不足以 amortize 重平衡成本。

- **观察 2：EPLB 的重平衡代价远大于一次理想均衡带来的单步收益。** 作者在 8x AMD MI300 单机上测量 DeepSeek-V3 + [[SGLang]] v0.4.7，发现理想均衡最多可把 MoE layer latency 降低约 25%，但 EPLB 的一次 LB 总延迟接近该收益的 10x；其中 expert reallocation 约占总 LB latency 的一半，每 GPU 平均替换约 28/32 个 experts，全模型跨层移动约 12.8k-13.0k 个 experts。
  - **依赖假设**：expert weight movement 在 LB 阶段基本阻塞推理，且不能被其他层或请求处理有效隐藏。
  - **可能失效场景**：如果系统能提前预取、异步复制、利用空闲窗口或 overlap attention/non-MoE compute，movement cost 的主导性会下降，目标函数权重也需要重估。

- **观察 3：接近均匀的 load metric 不等于最小端到端 latency。** Table 2 中 EPLB、ILP 和 heuristic 的 Mean/Max load 都接近 1，Mean normalized stddev 也都很低；但 EPLB 移动 13036 个 experts，heuristic 只移动 2440 个，ILP 为 2223 个。相同的均衡质量可以有很不同的实现代价。
  - **依赖假设**：movement count 和 weighted movement cost 与实际 rebalancing latency 强相关，足以作为优化目标的一部分。
  - **证据强度**：中到强。论文用硬件 profiling 构建 cost functions，并在 Figure 5 中显示 rebalancing latency 下降约 57%；但只覆盖单机 MI300/ROCm 6.3 环境。

- **假设 1：线性 cost model 足够指导 placement decision。** 作者 profile GEMM、all-to-all 和 GPU P2P collectives 后采用线性函数估计 compute、communication 和 expert movement latency。
  - **证据强度**：中。对本文单节点实验似乎足够，但论文明确说没有覆盖 network congestion、compute/communication overlap、hierarchical interconnect 等更复杂现象。

- **假设 2：周期性 aggregate LB 是合理控制面。** 本文仍然沿用“每 n 次 iteration 做一次 LB”的控制方式，只是让算法在 cost > benefit 时跳过。
  - **证据强度**：中。Figure 6 说明不同 n 下收益差异很大，但没有给出自动选择 n 的策略，也没有测量真实 workload 的 distribution drift。

## 核心方法

论文把 E2D assignment 表述成一个 cost-aware optimization problem。决策变量 `p_kv` 表示 expert `k` 是否放在 GPU `v` 上；`p'_kv` 是当前 placement；`d_k` 是预测到的 expert demand；`B_v` 是每张 GPU 能容纳的 expert 数量上限；`c_v^(s)` 表示 GPU `v` 的 token processing latency；`c_v^(m)` 表示把 experts 搬到 GPU `v` 的 movement cost；`c^(a)` 是 LB algorithm runtime。

ILP 的 objective 是最小化 `c^(a) + max_v(c_v^(s)) + max_v(c_v^(m))`。这里的 `max` 很关键：MoE layer 是同步执行，最慢 GPU 的 processing 或 movement 决定端到端等待时间。movement cost 用 weighted Hamming distance 表示，只对 `0 -> 1` 的 expert load-in 计费，因为卸载 expert 本身不需要传输权重；权重项 `c_vw^(e)` 可表达不同 GPU/link 之间的移动成本。

约束包括两类：每张 GPU 的 expert 数量不能超过 `B_v`；每个 expert 的 demand 必须由承载它的 GPU 按 service rate 满足。这个 formulation 支持 expert replication，不只是单纯交换 hot/cold experts。它的意义更像 oracle：在给定 cost model 和 demand prediction 的条件下，ILP 给出 latency objective 下的最优 placement，用来判断可达上界和验证 heuristic。

ILP 的问题是不可在线使用。Table 2 里 ILP runtime 超过 100s，虽然移动 expert 数量最低，但远超过 LB 控制面能承受的时间。因此作者设计一个轻量 heuristic：先按当前负载排序 GPU，在最忙和最闲 GPU 之间找 expert swap，使两者更接近目标 load；每次 swap 后重新计算总 cost，只有当新配置降低目标函数才接受，否则回滚。这个过程重复到达到 balance 或 move budget。若当前 workload 下 LB cost 已经超过预计收益，算法会选择不做 LB。

这个 heuristic 的实质是把 [[Load-Balancing]] 从“让 load variance 最小”改成“只接受有正收益的局部 placement move”。它牺牲全局最优性，但保留了本文最重要的系统约束：每一个 move 都要为可见的 latency reduction 付账。复杂度为 O(E^2 log E)，实验 runtime 0.17s，比 EPLB 的 0.26s 更低，和 ILP 的 >100s 形成明显对比。

## 设计取舍

- **ILP 作为 oracle，heuristic 作为在线控制面**：ILP 让论文能定义“latency-optimal”这一理论目标，但实际系统只能用近似 heuristic。好处是简单且可运行；代价是没有全局最优保证，遇到需要多步非局部 rearrangement 的 placement 时可能卡在局部最优。

- **少移动 expert，而不是追求完美均匀**：heuristic 的 Mean/Max load 为 0.996，略低于 EPLB/ILP 的 0.998/0.999，Mean Norm. Std. 也略高；换来的是 expert moves 从 13036 降到 2440。这个取舍很合理，因为论文证据表明 movement 才是当前环境下的主要瓶颈。

- **显式 cost model 带来可移植性成本**：方法原则上能表达异构 GPU、scale-up/scale-out link、不同 P2P cost，但前提是每个部署都要 profile compute、all-to-all、P2P movement，并维护这些 cost functions。实现复杂度从 LB algorithm 转移到了 profiling 与模型校准。

- **周期性重平衡对 rapidly shifting workload 仍然脆弱**：本文的 adaptive skip 能避免过频 LB 造成负收益，但不能让 placement 追上每个 iteration 的专家分布变化。作者也承认理想均匀每步可有 25% latency 改善，而实际 LB 最高只拿到 12.5%，原因就是 aggregate statistics 与 per-iteration distribution 之间有 gap。

- **优化平均 MoE execution latency，不等于完整 serving SLO**：实验主要看 MoE layer execution latency、LB latency、load balance metrics 和 estimated speedup；没有覆盖多租户隔离、P99/P999 request latency、scheduler queueing、故障恢复、在线 rollback 或 observability。

## 实验与结果

- **实验环境**：单节点，两颗 AMD EPYC 9655 96-core CPU，8 张 AMD Instinct MI300 GPU，ROCm 6.3，[[SGLang]] v0.4.7，模型为 DeepSeek-V3；workload 来自 OpenOrca、MBXP、GSM8K，分别代表 conversation、coding、math。

- **imbalance 的性能影响**：在 GSM8K 第 32 个 MoE layer 示例中，skewed placement 导致不同 GPU 的 compute、communication 和 synchronization latency 明显不均；理想均衡可带来最高约 25% 的 MoE layer latency speedup。

- **EPLB 的 cost-benefit 问题**：一次 EPLB LB 的总延迟约为理想单步收益的 10x；rebalancing latency 是最大瓶颈之一，平均每 GPU 替换约 28 个 experts，接近每张 GPU 已存 experts 的 87%。

- **load balance quality 接近**：Table 2 中 Baseline 的 Mean/Max load 为 0.650、Mean Norm. Std. 为 0.351；EPLB、heuristic、ILP 分别达到 0.998/0.001、0.996/0.003、0.999/0.001，说明 heuristic 基本保留了 E2D load balance 的核心效果。

- **movement 和 runtime 大幅下降**：expert moves 从 EPLB 的 13036 降到 heuristic 的 2440，接近 ILP 的 2223；algorithm runtime 从 EPLB 的 0.26s 降到 0.17s，而 ILP 超过 100s。Figure 5 显示 heuristic 使 rebalancing latency 下降约 57%，algorithm runtime 下降约 31%，总体 LB latency 接近 EPLB 的一半。

- **MoE latency speedup**：在每 100 iterations 做一次 LB 时，heuristic 相对 no-LB baseline 获得约 12.5% MoE layer execution latency improvement，高于 EPLB 的约 8%。在每 10 iterations 做一次 LB 时，heuristic 仍比 no-LB 快约 4%，且比 EPLB 快约 15%。

- **adaptive skip 避免负收益**：当每 iteration 都做 LB 时，EPLB 因无条件执行而出现约 73% 性能下降；heuristic 因 cost model 判断 LB 不划算而跳过，基本避免了这种最坏情况。

## 批判性分析

### 论证链条

论文的主链条比较闭合：先证明 MoE expert skew 在 DeepSeek-V3 上真实存在，再量化 skew 对 MoE layer latency 的影响，然后证明 EPLB 的 movement cost 大到足以吞掉收益，最后提出 cost-aware objective 和低开销 heuristic。最有说服力的点是 Table 2：不同算法能达到几乎一样的 balance metric，但 expert movement 差异巨大，这直接支撑“均衡质量不是唯一目标”。

需要收窄的是“latency-optimal”的语义。ILP 是在给定 demand、capacity、linear latency model 和 movement model 后的最优；在线 heuristic 是 cost-aware near-optimal，没有最优性证明。论文标题容易让读者误以为系统整体端到端 latency 已被最优控制，实际更准确的说法是“用 ILP 定义 latency objective，并用 heuristic 近似求解 E2D placement”。

### 假设压力测试

最脆的假设是 workload predictability。Figure 6 其实同时说明了方法有效和方法脆弱：n=100 时收益最好，n=1000 时 workload drift 让收益接近消失，n=1 时 movement overhead 会压垮 EPLB。真实服务里 n 不会是固定常数，而会随 batch composition、tenant mix、prompt length、decode phase 和模型 routing policy 改变。本文没有给出如何估计 expert distribution 的 half-life，也没有把 n 的选择纳入控制回路。

第二个压力点是 topology。本文的单机 8x MI300 环境适合证明 movement cost 重要，但 scale-out MoE serving 会遇到 rack 内/跨 rack link、NCCL/RCCL scheduling、network congestion、RDMA contention 和 failure domains。ILP 里 weighted Hamming distance 可以扩展到非均匀 link cost，但 heuristic 的 pairwise swap 是否仍然有效，需要新的实验。

第三个压力点是 overlap。论文把 LB 视为通常会 stall inference 的阶段，并提出未来可与 attention 等 non-MoE operations overlap。如果 overlap 成功，当前 objective 中 `max_v(c_v^(m))` 对 end-to-end latency 的贡献会改变，少移动 expert 的优势可能缩小，或者最优策略会变成“移动更多但藏在可 overlap 窗口里”。

### 实验可信度

实验的硬件测量是真实的，baseline 也选到了当前最相关的 [[EPLB]]。Table 2 覆盖了 load balance quality、algorithm runtime 和 expert movement，Figure 5/6 把这些 metric 连回 latency，因此比只报告 load variance 更可信。

主要不足是覆盖面窄。模型只有 DeepSeek-V3，硬件只有单机 8x MI300，serving framework 只有 [[SGLang]] v0.4.7，workload 是三个离线 dataset。论文没有展示真实在线 trace、不同 batch size、prefill/decode 分离、multi-node deployment、不同 expert size、不同 router policy 或 tail latency。对一个 workshop paper 这可以接受，但它限制了结论外推。

另一个小问题是 metric 仍偏 MoE layer 内部。论文声称 MoE execution latency 最高下降 12.5%，不是完整 request-level throughput-per-dollar 或 P99 latency 改善。对于生产 serving，LB 可能还会影响 memory pressure、admission control、scheduler fairness 和 rollback 复杂度，这些没有进入实验。

### 系统性缺陷

实现上，方法需要把 cost model、recent demand estimation、placement decision、expert weight transfer 和 serving runtime 的 executor 协调起来。论文没有讨论 placement 切换期间的 correctness 语义：正在执行的 batch 是否继续使用旧 placement，新 batch 何时切换，失败或部分移动时如何恢复，replicated experts 的 metadata 如何同步。

资源隔离也未讨论。多租户场景中，为了服务一个 workload 的 expert redistribution 可能影响另一类请求，尤其当不同 tenant 的 expert hot set 不同。heuristic 的 objective 以全局 average latency 为中心，没有显式 fairness 或 per-tenant SLO。

可观测性方面，系统需要知道什么时候 distribution drift 已经让 placement 失效，也需要解释为什么某次 LB 被跳过。论文展示了 adaptive skip 的效果，但没有给出线上监控指标、trigger hysteresis 或安全阈值。

## 局限与后续工作

- **局限 1：实验只覆盖单节点 DeepSeek-V3。** 需要在多节点、多拓扑、多 GPU 代际和不同 MoE 模型上验证 movement cost 是否仍然主导。

- **局限 2：workload drift 只通过固定 LB interval 间接呈现。** 后续应测量 expert distribution 的稳定窗口，并让 LB interval 或 trigger 由 drift estimator 自动决定。

- **局限 3：cost model 是线性的部署内 profile。** 未来可以加入 congestion、overlap、hierarchical interconnect、heterogeneous GPU 和 P2P/RDMA contention，用更接近真实系统的 latency predictor 替换简单线性模型。

- **局限 4：没有 request-level serving SLO。** 需要在真实 scheduler 中报告 end-to-end throughput、TTFT、TPOT、P50/P99/P999 latency、GPU memory pressure 和失败恢复时间。

- **Future work 1：topology-aware expert movement。** 把 weighted Hamming distance 扩展成跨节点 min-cost flow 或 constrained placement 问题，并检验 pairwise swap heuristic 是否还能逼近 ILP。

- **Future work 2：overlap-aware LB。** 把 expert transfer 与 attention、normalization、prefill/decode 间隙或低优先级后台 copy overlap，并客观测量 movement 的 exposed latency 是否下降。

- **Future work 3：online trigger policy。** 用最近 token routing 分布的 drift、预测收益和 movement backlog 决定是否 LB，而不是手工扫描 n=1/10/100/1000。

- **Future work 4：与 router/training 方案联合优化。** 比较 auxiliary loss、routing bias、expert replication 和 cost-aware E2D placement 的组合，判断应该在模型训练、运行时系统还是两者之间承担 balance 责任。

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[Load-Balancing]]、[[ILP]]、[[Distributed-Inference]]
- **同类系统 / 方法**：[[EPLB]]、[[DeepSeek-V3]]、[[SGLang]]、[[FasterMoE]]、[[FlexMoE]]、[[Tutel]]、[[Prophet]]
- **评估硬件 / 软件**：AMD Instinct MI300、ROCm 6.3、[[SGLang]] v0.4.7
- **评估 workload**：OpenOrca、MBXP、GSM8K
- **同会议**：[[INET4AI-2025]]
