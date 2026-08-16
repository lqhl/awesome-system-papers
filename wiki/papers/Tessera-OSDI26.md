---
type: paper
name: Tessera
full_title: "Tessera: A Holistic Pipeline Parallelism Framework for Trillion-Parameter Heterogeneous MoE Training (Operational Systems)"
authors: [Weifang Hu, Langshi Chen, Man Yuan, Youyang Yao, Xiulong Yuan, Li Tian, Yong Li, Wei Lin, Xuanhua Shi, Zhengping Qian, Jingren Zhou]
venue: OSDI
year: 2026
tags: [distributed-training, mixture-of-experts, pipeline-parallelism, communication-overlap, load-balancing]
source_pdf: "[[osdi26-hu-weifang.pdf]]"
source_md: "[[osdi26-hu-weifang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 异构 MoE 训练的整体流水线并行（OSDI 2026）

> **原题**：Tessera: A Holistic Pipeline Parallelism Framework for Trillion-Parameter Heterogeneous MoE Training (Operational Systems)

> **一句话总结**：Tessera 发现，异构 [[MoE]] 中不同 layer pair 能隐藏的通信比例相差约 3 倍，所以先按串行 FLOPs 分 stage、再套固定 overlap 会重新失衡；它先为候选 layer pair 生成并实测细粒度 schedule，再联合选择 [[Pipeline-Parallelism|pipeline partition]]，运行时还把 Wgrad 等可移动任务塞进 router 波动造成的气泡，在 4,096–12,288 张 Hopper GPU 的五个 Qwen3/Qwen3-Next 生产任务上把 MFU 相对提高 20.0%–32.8%。

## 问题与动机

传统 Transformer 每层结构相同。按每层串行 FLOPs 或 latency 切分 pipeline 后，各 stage 通常也有相近的 compute/communication 比例，一份固定的通信—计算重叠模板可以反复使用。Qwen3-Next 不再满足这个前提：每四层由三个 Gated DeltaNet 线性 attention 和一个 full softmax attention 组成，每层后面又有稀疏 MoE；相邻 attention 的 compute time 最多相差 10 倍（§2.2、图 1、图 3）。

在 interleaved 1F1B 中，同一 rank 会让不同 microbatch、不同 chunk 的 forward/backward 相遇。一个 chunk 的 All-to-All（A2A）能否藏在另一个 chunk 的计算后面，取决于两者方向和具体 layer 组合，而不只是串行成本之和。partition 决定会形成哪些 overlap pair；每个 pair 的重叠效果又决定哪个 partition 最平衡。现有“先分区、后重叠”的瀑布式流程因此形成错误的优化目标（§2.1–§2.3）。

即使静态计划准确，router 每轮给各 expert/rank 的 token 数仍会波动。Qwen3-Next 每个 token 只激活 512 个 expert 中的 10 个，单个 expert 的相对波动更明显；在一万张以上 GPU 上，它会变成局部空闲和跨设备等待。Tessera 同时解决两个层次的问题：离线联合优化结构性 partition/overlap，在线回收 routing 造成的临时气泡。它固定高层 pipeline template，并不搜索所有 pipeline schedule。

## 关键观察 / 隐含假设

- **观察 1：串行成本相等，不代表重叠后的成本相等。** Qwen3-Next-80B、128 GPUs、256K sequence 的测量中，C-C pair 的 overlap gain 是 41.6%，D-D 只有 14.0%；串行平衡方案的最大 post-overlap cost 比 overlap-aware 方案高 1.14 倍（§2.3.2、图 4）。
  - **依赖假设**：生产性能主要由反复出现的 steady-state overlap edge 瓶颈决定，最大 edge cost 可以近似完整 iteration critical path。
  - **可能失效场景**：microbatch 很少、warmup/cooldown 占比高，或 straggler 不出现在被选 edge 上时，这个 surrogate objective 可能选错 partition。
- **观察 2：纯 analytical schedule 忽略真实硬件干扰。** Qwen3-Next 上理论 makespan 平均低估实测约 5%；A2A kernel 会占约 20 个 SM，使并行 Attention/MoE-MLP 慢 10%–20%（§5）。
  - **依赖假设**：用相同 TP/EP topology 的 reference group 实测 chunk pair，能够代表目标集群；GPU、通信库和网络状态在 plan 有效期内足够稳定。
- **观察 3：routing metadata 早于气泡出现。** EP group 在 dispatch 前已有 per-expert token count，只交换这些 scalar 就能预测 MoE 边界后的空闲窗口，不需要 cluster-wide synchronization（§3.2.1、图 5）。
  - **依赖假设**：routing 是主要短期动态来源，token count 到 kernel duration 的 profile 在目标 slot 前仍准确。论文讨论了 network jitter 扩展，但没有系统验证。
- **观察 4：Wgrad、gradient reduction 等任务有正 deadline slack。** 它们可以延后到 iteration end 前执行，从而构成填气泡的 task pool（§2.3.3、§3.2.2）。
  - **代价**：延后会拉长 activation 和 gradient 的生命期。作者在生产中确实遇到过 aggressive bubble filling 导致 OOM，必须限制每 GPU 的 pool 容量（§5）。

## 核心方法

Static Planner 先从固定的 interleaved 1F1B template 构建 overlap graph。node 是 virtual pipeline stage，edge 表示同一 rank 上两个 stage/pass direction 会同时执行；同一对 stage 的 forward–backward 与 backward–forward 是不同 edge，自环表示同一 virtual stage 的不同 microbatch 相遇。planner 从串行平衡 baseline 出发，只在每个边界附近生成有限个连续 layer-range candidates，避免搜索任意 partition（§3.1.1、图 6）。

每个 edge 的候选 chunk pair 被拆成两个 task DAG。task 有依赖、预估时长、Comp/Comm resource 和是否可移动等属性。事件驱动 scheduler 先推进决定完成时间的 backbone task，再用 gap-fit 挑选最适合另一资源空档的任务；若 movable task 会拉长 makespan，就先 defer，最后按 best-fit 填剩余 slot。这个启发式避免对每个 pair 求 resource-constrained ILP（算法 1、图 7）。

生成 schedule 后，Tessera 不直接信任模型，而是在与目标 rank 相同 TP/EP topology 的 reference device group 上实测 post-overlap cost。相同 chunk、pass direction 和 device-mesh class 只 profile 一次并缓存。论文说明 primitive-level profile 的 tail error 可达 15%，足以改变 partition；因此生产默认使用完整 chunk-pair profile，代价是新模型/拓扑部署前要占一组 GPU 最多约一小时（§3.1.2、§5）。

有了每条 edge、每对候选的实测 cost，partition 选择变成 MILP graph labeling：每个 stage 选一个 candidate，同时满足 layer 连续、不重叠、topology 与 memory 约束，目标最小化所有被选 overlap edge 的最大 cost。baseline 的 bottleneck cost 是安全上界；任何更慢 pair 都不可能改进 baseline，可以剪掉。solver 输出 layer assignment 和每个 pair 的细粒度 schedule，组成执行 plan（§3.1.3、式 1）。

Dynamic Bubble Optimizer（DBO）只在离线 plan 标注的 MoE 后边界工作。它用当前 token count 和离线 profile 异步估算 window `b`，从按 deadline 排序、容量受限的 movable-task pool 中选“放得下且不会错过 deadline”的任务；找不到就留空，deadline 快到时强制回主 stream。slot sizing 和 task selection 合计少于 10 μs。算法不改变 backbone 次序、operator 语义或 reduction order（§3.2、算法 2、图 8）。

实现是集成到内部 [[Megatron]]-LM 的独立 library，约 11 KLoC Python 和 2 KLoC C++。C++ plan-agnostic engine 用 lock-free FSM 协调 forward、backward Torch threads 和执行 movable task 的 background thread；模型代码只需在 task boundary 插入 `advance()` probe，用 `register_task()` 暴露 Wgrad 等任务。系统还用执行空通信、不参与 loss/optimizer 的 shadow action，解除 microbatch 数必须整除 pipeline size 的限制，实测约 0.5% 开销（§4–§5）。

## 设计取舍

- **完整 chunk profiling 换准确性**：能吸收 SM contention、cache 和 launch overhead；代价是 plan 与 GPU、拓扑、kernel、通信 backend 版本绑定，升级后可能要重新 profile。
- **有限候选换可解性**：只扰动串行 baseline 附近边界，使 profile 和 MILP 可控；若真正最优 partition 离 baseline 很远，搜索空间根本看不到它。
- **最大 edge cost 换简单目标**：适合固定模板的 steady state，但没有直接最小化 warmup、cooldown 和完整 iteration critical path。
- **动态填洞换确定性**：DBO 不重排 backbone，保持计算图和 reduction order；代价是只能利用已有 slack，不能消除没有可移动任务或 computation 不足时的通信暴露。
- **显存换吞吐**：pool 越大，填洞机会越多，也让更多 tensor 保持存活；生产配置必须按实际 memory headroom 限制容量。

## 实验与结果

- 生产环境是每机 8 张 NVIDIA Hopper GPU、[[RDMA|RoCE]] 网络；baseline 是已经包含 interleaved 1F1B、原生通信重叠和 FLOPs-balanced partition 的内部 Megatron-LM。保持 cluster configuration 与 hyperparameters 不变后，五个 Qwen3/Qwen3-Next workload 的 MFU 分别从 29.7%→36.3%、32.0%→39.0%、16.7%→20.0%、19.6%→24.0%、15.9%→21.1%，对应相对增幅 22.0%、21.8%、20.0%、22.5%、32.8%，规模为 4,096–12,288 GPUs。这里的 20.0%–32.8% 是相对增幅，不是增加相同数量的百分点；数据为内部与开源混合数据（§6.1–§6.2、表 2）。
- 8,192-GPU Qwen3-XL 两周 hot-upgrade trace 中，Static Planner 上线后 throughput 约提高 13%，其中约 9% 归因于 post-overlap load balance；DBO 上线后 MFU 达 39.0%。不过最佳的 Qwen3-Next-L case 仍有 8.3% iteration time 是 exposed EP、8.5% 是 PP idle；compute 较弱的 Qwen3-Next-M 总 exposed EP 达 38.9%，说明系统不能用不存在的计算完全隐藏 A2A（图 9、图 10）。
- 在 256 GPUs 上，Tessera 对内部 Megatron 的 Qwen3-235B、DeepSeek-V3、Nemotron-3 Super MFU 分别提高 1.27、1.24、1.13 倍；相对 recipe-tuned Megatron-Core，Qwen3-235B 是 40.1% 对 32.4%（1.24 倍），DeepSeek-V3 是 33.7% 对 33.4%，Nemotron 是 27.7% 对 26.3%，后两者只能称为接近或小幅提高（§6.3、图 11）。
- 关闭 DBO、固定 uniform mock router 后，Qwen3-Next-80B/128 GPUs 和 Qwen3-Next-M/256 GPUs 都出现同一反转：无 overlap 时串行 latency-balanced Partition A 略好，启用 overlap 后 Tessera 的 Partition B 最好，相对 Megatron-default 吞吐分别高 39.1% 和 34.1%（§6.4、图 12）。
- 536 个 EP8 和 690 个 EP32 overlap instances 上，heuristic 的实测 post-overlap cost 距 CBC ILP 分别只有 0.76% 和 1.07%；ILP 单实例预算 300 s，全部求解需数小时到数天，而 heuristic 全部完成少于一分钟。8,192-GPU target 的完整 chunk profiling 在 64-GPU reference group 上最多约 3,050 s，MILP 经 3–5 倍剪枝后只需 0.34–4.22 s（§6.5、§6.7、图 13、表 4）。
- Qwen3-Next-M、256 GPUs、每 GPU pool cap 8 时，DBO 把 baseline/overlap-aware iteration time 从 8.28/6.98 s 降到 7.83/6.67 s，即 5.4%/4.4%；peak memory 从 69.3%/67.4% 升到 72.9%/70.0%。只运行监控但不移动任务的 always-keep 反而约慢 1%；另一个 6,144-GPU Qwen3-L 生产任务中，DBO 单独减少 641 ms PP bubble，吞吐提高 3.4%（§6.6、表 3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| partition 必须按 post-overlap cost 选择 | 图 4、图 12 | Qwen3-Next；128/256 GPUs；固定 template、DBO 关闭 | 强 |
| 整体方案能在万卡生产训练中持续提高 MFU | 表 2、图 9 | Alibaba Hopper/RoCE、五个 Qwen3-family workload、内部 baseline | 强 |
| 事件驱动 heuristic 接近 ILP，但规划更快 | 图 13、表 4 | 536/690 pair instances；EP8/EP32；64-GPU profiling group | 强 |
| DBO 能利用 routing-induced bubble | 表 3、§6.6 | 256-GPU ablation 和两个独立生产案例；pool cap 8 | 强 |
| 方法可迁移到 Qwen3 之外的异构 MoE | 图 11 | 三个公开模型、256 GPUs；相对公开 baseline 仅 Qwen 明显胜出 | 中 |

## 批判性分析

### 论证链条

论文最强的证据不是总 MFU，而是图 4 和图 12 的“排序反转”：串行看起来更平衡的 partition，在 overlap 后反而更慢。这个反例直接否定了旧 objective，再由 pair scheduler、实机 profile 和 partition MILP 逐层修正。All-to-All 暴露、partition、scheduler 和 DBO 都有对应消融，因此“partition 与 overlap 应联合优化”的论证闭合。

生产总收益则来自多项机制叠加。Qwen3 结构较均匀，仍因细粒度 inter-microbatch overlap、边界 chunk 调整和 DBO 获益；所以不能把表 2 的全部 20%–33% 都归因于“异构 partition”。论文自己用 Qwen3-XL rollout、图 12 和表 3 分解了一部分，但没有在五个最大规模 workload 上逐项 ablation。

### 假设压力测试

Static Planner 固定 interleaved 1F1B 和 virtual-stage topology，只在现有边界附近搜索。若最优解需要改 microbatch schedule、pipeline degree 或远距离移动 layer，Tessera 不会发现。以最大 pair cost 近似完整 iteration 也偏向 steady state；图 10 已显示 warmup/cooldown 在较优案例里仍贡献大量暴露通信和 PP bubble。

profile cache 假设软件和硬件稳定。kernel fusion、通信 backend、sequence length、GPU degradation 或网络拥塞改变后，原 pair ranking 可能失效。论文提出用最近 10 iteration 的 moving average 让 DBO吸收 infrastructure jitter，但明确说 controlled validation 仍是 future work；这不能作为已证明能力。

### 实验可信度

生产规模、持续部署、相同配置对比、公开模型的 256-GPU controlled baseline、静态排序反转和 DBO memory/overhead 表，使证据比只报告单次峰值完整。deterministic 模式下，一组 trillion-scale Qwen3-Next 的 loss trajectory bit-identical，也支持“只改时间线、不改数学”的 correctness claim。

限制是大规模 baseline、模型细节、数据和 Tessera 实现都不是公开可复现实验；论文按 Small/Medium/Large/Trillion 分类隐藏了若干实际模型参数。生产 rollout 的 step change 有现场真实性，但不是随机 A/B 实验，可能夹杂时间上的环境变化。主结果也没有误差条、重复次数、P99 iteration time、故障率或不同网络拥塞强度。

### 系统性缺陷

每种新 operator 都要正确标出 task boundary、resource type、dependency、movability 和 deadline。probe 或 deadline 写错可能造成 deadlock、tensor 过早释放或 silent wrong result；bit-identical 测试覆盖一个 deterministic workload，不能替代对所有自定义 plan 的验证。论文没有讨论 plan schema validation、deadlock checker、超时降级或在线回退到 baseline。

离线 profiling 最坏约占用 64 张 GPU 近一小时，约为数十 GPU-hours；硬件或软件变化会重复付费。DBO 还明确在 aggressive 配置下导致过 OOM。论文通过 bounded pool 控制风险，但没有展示自动选择 cap、OOM 前的安全 margin、任务取消、GPU failure 或训练 job elastic resize 下如何保持 plan 正确。

## 局限与后续工作

- **局限 1**：高层 pipeline template、parallel degrees 和候选邻域固定；系统不是完整的 distributed-training strategy search。
- **局限 2**：万卡数据来自内部 Qwen stack，公开 baseline 只到 256 GPUs；外部难以复现最大规模收益。
- **局限 3**：profile 与 Hopper/RoCE、kernel 和 backend 版本绑定；network jitter 自动适配、失败恢复和在线 replan 未验证。
- **后续工作 1**：在注入 GPU slowdown、RoCE congestion 和 kernel-version drift 的实验中，测 profile ranking 变化、P99 iteration time，并给出触发 re-profile/replan 的客观阈值。
- **后续工作 2**：把 warmup/cooldown critical path、pipeline degree 和 microbatch schedule 纳入联合搜索，比较完整 iteration time，而不只优化最大 steady-state edge。
- **后续工作 3**：为 plan/probe 增加 dependency、lifetime、deadline 和 memory 静态检查；通过错误 plan、OOM、GPU failure 注入验证自动回退到 baseline。

## 相关

- **相关概念**：[[MoE]]、[[Pipeline-Parallelism]]、[[Expert-Parallelism]]、[[Tensor-Parallelism]]、[[Attention]]
- **相关系统**：[[Megatron]]、Megatron-Core MoE、Qwen3-Next、DeepSeek-V3
- **同会议**：[[OSDI-2026]]
