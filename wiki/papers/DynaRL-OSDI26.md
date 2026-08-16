---
type: paper
name: DynaRL
full_title: "DynaRL: Flexible and Dynamic Scheduling of Large-Scale Reinforcement Learning Training"
authors: [Yuanqing Wang, Hao Lin, Junhao Hu, Chunyang Zhu, Quanlu Zhang, Zhen Guo, Yuchen Zhang, Xu Fu, Si Xu, Bo Dai, Zixiao Huang, Chao Yu, Boxun Li, Guohao Dai, Zhi Yang, Yu Wang]
venue: OSDI
year: 2026
tags: [reinforcement-learning, distributed-training, dynamic-scheduling, resource-migration, agentic-rl]
source_pdf: "[[osdi26-wang-yuanqing.pdf]]"
source_md: "[[osdi26-wang-yuanqing]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# DynaRL：大规模强化学习训练的灵活动态调度（OSDI 2026）

> **原题**：DynaRL: Flexible and Dynamic Scheduling of Large-Scale Reinforcement Learning Training

> **一句话总结**：长尾 rollout 会让不足 30% 的 query 拖住几乎全部 inference engine，多轮 tool call 又让 FIFO 调度反复丢失 [[KV-Cache]]；DynaRL 用动态 hypergraph 统一观察 RL 组件，以三种在线迁移方式在 rollout、inference 和 trainer 间重分 GPU，再优先推进接近完成且 cache 可复用的请求，在 64/128 张 H100 上把 math-reasoning RL 吞吐提高 1.27×–1.98×，把带优先级的 agentic RL 吞吐提高 1.27×–1.64×。

## 问题与动机

大模型强化学习（reinforcement learning，RL）不是一个固定 computation graph。最简单的 GRPO 也有 rollout、log-prob inference 和 training 三个主要组件；PPO-based RLHF 可有七个组件。Agentic RL 还会插入 search、Python、compiler、Lean 等外部工具，组件间既有数据依赖，也有无法预测的等待（§2.1、图 1）。

第一个动态来源是 autoregressive generation 的长尾。作者在 1.5B 模型的 math-reasoning GRPO workload 中看到：decode 最长约 259.51 s，约 95% query 在 150 s 内结束；到 generation 中段时只剩不足 30% query，却因这些长尾均匀散在 64 个 inference engine 上，几乎所有 engine 仍不能释放，最多浪费 60% compute，尚未计入闲置的 KV cache（§2.2、图 2–3）。

第二个来源是多轮工具交互。一个 ReAct-style request 生成一轮、调用工具、把结果拼回 context，再进入下一轮；tool latency 和 turn 数都高度偏斜。[[SGLang]]、[[vLLM]] 默认 FIFO 时，刚结束第一轮的 request 会排在许多新 request 后面，其 cache prefix 可能在第二轮被调度前淘汰。论文在相同 100 GB KV-cache threshold 下看到 agentic RL 比单轮 math RL 产生明显更多 re-prefill token（图 4–5）。

现有 verl、RLinf 等框架能把 Worker 放到 GPU、建立 channel 并运行 pipeline，但通常在训练前固定物理 partition 或 time sharing。它们无法随着 active rollout 减少，把空闲 GPU 提前转给 inference/trainer；也无法把多轮 request 的 cache affinity 纳入调度。DynaRL 的目标是把这类在线变化变成 runtime 的一等控制对象，同时保持 model/optimizer state 和 RL 语义不变。

## 关键观察 / 隐含假设

- **观察 1：Rollout 的“资源—性能”曲线会随剩余 query 数变平。** 早期更多 engine 有用，后期每台只剩一两个长尾 request，额外 GPU 的边际收益接近零；trainer 在输入充足时则近似随 GPU 线性扩展（§5.1）。
  - **设计含义**：以 overprovision 为 donor signal，比预先猜一个固定 rollout:train 比例更适合 phase-changing workload。
  - **依赖假设**：作者把组件分成 static/linear 与 dynamic/concave 两类，并把近同步 pipeline 的端到端吞吐近似为各 stage 吞吐的最小值；复杂 overlap、network bottleneck 或 non-concave scaling 可能破坏这个模型。
- **观察 2：安全迁移不要求所有组件共享一种 checkpoint 机制，但要求存在明确的 interruptible point。** Stateless inference 可以移请求，Megatron trainer 必须转 model/optimizer shard 并重建 communication group（§4.2、图 8–9）。
  - **依赖假设**：组件能合作地到达 interrupt point；若长 kernel、tool hang 或不可中断 collective 持续太久，scheduler 看到瓶颈也不能立刻执行计划。
- **观察 3：后期 tool turn 通常比第一轮短，而且更值得保 cache。** 作者观察 round 0 最长，后续平均 generation token 随完成度单调减少，因此“已完成 tool call 更多”可同时近似 shortest-remaining-work 与 cache urgency（§5.2）。
  - **可能失效场景**：反复规划、长 observation、late-stage proof 或 tool output 很大的 agent 可能后期更长；论文声称此时退化为近 FIFO，但没有给 adversarial/fairness 实验。
- **观察 4：控制面可以按组件聚合，而不必逐 GPU 求解。** 每个 WorkerGroup Manager 汇总 worker metric；scheduler 只对 3–7 个 component、每个 3–10 个 candidate allocation 做 `O(K×|C|)` 评估，与 GPU 数量独立（§5.1.2）。
  - **风险**：聚合值可能隐藏一个 rank、NIC 或 queue 的局部 straggler；128-GPU 的低求解开销不自动证明千卡规模的数据与迁移开销也不变。
- **假设 1：短 profiling 建出的 throughput predictor 能跟上 workload drift。** 系统在训练前测 batch/sequence 代表点，在线再用 throughput、queue depth 和 batch composition 做 regression 更新（§5.1.2）。
  - **证据强度**：中到弱。端到端结果说明闭环可用，但论文没有单独报告预测误差、cold-start 时长或 concept drift 速度。

## 核心方法

### 1. 动态 hypergraph 作为统一控制面

DynaRL 运行在 RLinf 一类通用 RL framework 上，本身也是一个 WorkerGroup。Global Scheduler 与每个组件的 WorkerGroup Manager 形成反馈环：manager 汇报 utilization、queue pressure、per-worker throughput，scheduler 计算新 allocation，manager 执行迁移（图 6）。

一个 HyperNode 表示 rollout、trainer、tool agent 等逻辑组件，内部的 Node 表示同质 worker。静态字段记录 component type、predecessor/successor 和可中断性；动态字段记录 worker、resource 与 utilization。HyperEdge 表示组件间 dataflow，并附带 progress 和 worker affinity。它既让 scheduler 知道谁过配、谁已 ready，也让迁移后的 data router 知道数据应去哪个 worker（§4.1、图 7）。

实现不要求用户手写整张图。DynaRL 用 Python `ast` 找到继承 WorkerGroup 的 component class 和 framework channel `put/get` call，构造静态 node/edge；运行时 hook 再登记 worker、资源、utilization、progress 与 affinity。这个自动抽取依赖 RLinf 的 class/API 约定（§6）。

### 2. 一套接口，三种迁移语义

所有组件都暴露 `interrupt()` 与 `migrate(dest_resources)`。Manager 到达自然的 batch/query boundary 后通知 scheduler；scheduler 只联合当前可中断的组件求解，再让各 manager 使用自己的迁移策略（§4.2、图 8）：

- **RebootMigration**：保存必要状态，关闭旧 worker，在目标 GPU 重启。最通用，但 restart 成本最高，适合轻量组件或 hang 后强制恢复。
- **WorkloadMigration**：暂停要释放的 worker，收集 pending/in-flight request，再分发给保留 worker。Rollout、tool agent、inference、reward 等 stateless/weakly-stateful component 使用它。
- **p2pMigration**：先在目标资源创建新 trainer，根据旧/新 data/tensor/pipeline parallelism 生成 rank mapping 和 reshard plan，用 peer-to-peer 传 model parameters、optimizer states 与 gradient buffer，重建 [[NCCL]] group，确认所有新 rank ready 后才切换并销毁旧 rank（图 9、§6）。Transfer 失败则丢弃新 worker，旧 worker 继续运行。

Create-before-destroy 给 trainer state 一个近似原子的切换点，但迁移期间需要源和目标 worker 同时存在，也要求目标 GPU/内存足以先启动新进程。

### 3. 保留 cache affinity 的数据路由

每个 WorkerGroup 内有 local DataRouter。数据发出前附两类 context：`affinity` 表示必须、优先或无需回到上次 worker；`status` 表示 sequence 已经过多少 step。`distribute_data` 在 group 间按 affinity 选择目标，`priority_schedule` 在一个 worker 的 input queue 内排序（§4.3、图 10）。

这样，资源 migration 后仍能把 episode 的后续 turn 尽量送回保存 prefix 的 inference worker。HyperEdge 不只是依赖图，也携带恢复数据局部性所需的信息。

### 4. 从 overprovision 检测到 reallocation

Scheduler 有 WorkerGroup、worker、request data 三层。跨组件控制 loop 分两步（算法 1）：

1. 对 dynamic component 聚合 utilization。Rollout 的实际 signal 是各 engine active KV-cache size / capacity。若超过 `θ` 比例的 engine 在连续 `T` 秒内低于 `U_low`，就把它标成 donor；示例 `θ=80%`，`U_low` 也可取历史 utilization 的低 percentile。
2. 生成 3–10 个可行的缩容候选。Performance predictor 估计 donor 缩容损失，再把释放 GPU 分给 queue/throughput 显示为 bottleneck 的其他 component，预测每个方案的 end-to-end throughput；只在严格优于当前方案时提交最优候选。

持续窗口过滤瞬时抖动，interruptible point 限制迁移频率，online regression 随 workload 更新。因为 manager 先聚合 worker metric，128 GPU 上一次 plan 可在 200 ms 内完成（§5.1）。

### 5. 多轮请求的优先级

Agentic request 的排序 key 是 `(k_r, m_r)`：`k_r` 为已完成 tool-call 次数，`m_r` 为 prefix-tree cache 中可复用 prefix 的长度。系统先选 tool round 更靠后的 request，同一 round 再选 cache prefix 更长者，组成下一 batch（算法 2）。

这个策略让刚返回的后续 turn 在 cache 被淘汰前继续执行，也让通常较短、接近完成的 episode 更快离开系统。它与 GPU reallocation 是两层互补机制：request priority 更早排空 rollout worker，resource scheduler 才能更早把 GPU 交给 trainer（图 13）。

DynaRL 共约 7K 行 Python：2K global scheduler、4K migration manager/strategy、1K hypergraph/router/辅助逻辑；已实现 rollout、tool agent、trainer、inference 和 reward component（§6）。

## 设计取舍

- **集中控制换全局视野。** Hypergraph 能联合组件求解，但 Global Scheduler、manager report 和在线 predictor 成为新的 stale-state 与可用性风险；论文只描述 worker heartbeat/reboot，没有控制面 failover。
- **合作式中断换迁移正确性。** 在 query/batch boundary 切换容易保持语义，却会延迟对长任务和 hang 的反应；强制 RebootMigration 又可能丢失 in-flight work。
- **Create-before-destroy 换回滚能力。** p2p migration 在新 rank 完整后才切换，避免半状态 trainer；代价是迁移窗口内暂时保留两套 worker、额外 P2P traffic 和 NCCL group rebuild。
- **回归预测换低求解成本。** `O(K×|C|)` 很简单，但只能从测过的 batch/sequence 邻域外推；classification 错误或 network contention 会让“预测最优”不是实际最优。
- **Cache/完成度优先换公平性。** Late-turn request 更快，fresh request 可能持续被插队；论文没有 starvation bound、age term 或多 tenant priority policy。
- **同质 GPU 池换清晰模型。** 公式明确假设固定数量 homogeneous resources；异构 GPU、不同 NIC topology、CPU/tool bottleneck 与跨作业资源竞争没有进入 planner。

## 实验设计

Testbed 有 16 台服务器、共 128×NVIDIA H100-80GB；每台 8 GPU，以 NVLink 互联，并有 8 张 400 Gbps ConnectX-7 [[RDMA|RoCEv2]] NIC、双 48-core Xeon 8558 和 2 TB DRAM。实验用 64 或 128 GPU，模型为 1.5B、7B、32B；rollout batch 512、group size 16、最大 sequence length 28,672。Trainer TP 分别为 2/4/8，rollout TP 为 1/2/4（§7.1）。

Math-reasoning 数据来自 AReaLboba-Data，baseline 是 verl 0.5、RLinf，以及作者在 RLinf 内重实现的 RLHFuse；rollout engine 为 [[SGLang]]，trainer 为 [[Megatron]]。Agentic RL 用 rstar2-agent，只比较 RLinf，因为 verl 在该实验只支持较慢的 [[FSDP|FSDP]] backend。吞吐取 warm-up 后 10 个 training iteration 的均值；math 使用 tokens/s，agentic 使用 requests/s（§7.1）。

## 实验与结果

- **Math-reasoning 的主收益来自把 rollout 尾部与下游重叠。** 64 GPU、1.5B/7B 时，DynaRL 相对静态 baseline 快 1.43×–1.55×；32B 时 verl OOM，DynaRL 相对 RLinf 快 1.27×。128 GPU 下，1.5B/7B 增益约 1.40×–1.52×；32B 相对 verl 为 1.98×、相对 RLinf 为 1.40×。跨配置相对 RLHFuse 为 1.21×–1.42×（§7.2、图 11）。
- **Agentic workload 证明 request priority 不是小优化。** 64 GPU 上只做 dynamic allocation 相对 RLinf 为 1.06×–1.38×；加 priority 后，1.5B/7B/32B 分别为 1.51×/1.53×/1.27×。128 GPU 时三者为 1.40×/1.64×/1.58×。32B 的 cache pressure 更高，所以 priority 从 64 到 128 GPU 仍有 21%→24% 的额外收益；小模型因 cache 更充足，额外收益从 14%–15% 降到 11%（§7.2、图 12）。
- **Timeline 解释了端到端倍数。** 7B/64-GPU math run 中，静态模式把 64 GPU 依次全给 rollout、inference、trainer；dynamic 模式在 rollout active request 下降时逐步给 inference 约 8 GPU、trainer 最多 52 GPU。加 request priority 后 trainer 约 380 s 已拿到 52 GPU；不加时约 420 s 才到 32 GPU（§7.3、图 13）。
- **调度便宜，但迁移本身是秒级。** 所有 scheduling decision 少于 200 ms，一个 iteration 的总调度开销低于 0.5%。图 14 中 trainer migration 从 1.5B 的约 0.5 s 增到 32B 的约 2.8 s；§7.4 把 1.5B 写成“sub-millisecond”与图的秒单位明显矛盾，应是“sub-second”的笔误。论文称即使 32B/128 GPU 也低于端到端时间的 0.5%；rollout migration 的中位数大致为 3.5–5 s，极值接近 7.5 s。论文摘要中的“negligible overhead”不能理解为每次 migration 少于 0.5 秒或少于 200 ms（§7.4、图 14）。
- **控制参数有宽平台，但极端值会明显退化。** 1.5B math workload 中，`U_low=0.1–0.3` 时吞吐在 233K tokens/s 峰值的约 1.5% 内；`0.01` 因重配太频繁降至 188.65K（低 19.7%），`0.5` 因不愿重配降至 201.82K（低 14.1%）。`T=2–8` 在约 235.5K 的 0.5% 内，`T=32/64` 分别低 3.1%/6.4%（§7.5、图 15）。
- **正确性只做了一条经验曲线。** 1.5B、64 GPU 的 math task 中，dynamic 与 static 的 step-wise reward curve 基本重合（§7.6、图 16）。这说明该 run 没看到 convergence 退化，但没有覆盖 7B/32B、agentic、不同 seed 或统计置信区间。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 在线跨组件重分 GPU 能缩短长尾 rollout 的 critical path | 图 11、图 13：math 吞吐提高 1.27×–1.98×，下游提前启动 | 64/128 H100、1.5B–32B、单一 math 数据组合 | 强 |
| Multi-turn-aware priority 能减少 agentic RL 的 cache/straggler 浪费 | 图 12：加 priority 后相对 RLinf 为 1.27×–1.64×，并高于仅 dynamic 版本 | rstar2-agent、SGLang、只与 RLinf 比较 | 强 |
| 三种 migration 足够便宜，可用于 iteration 内多次调整 | 图 14、§7.4：trainer 约 0.5–2.8 s，rollout 多为数秒；占端到端比例小 | H100/RoCEv2、Megatron/SGLang、最多 128 GPU；无失败注入 | 中到强 |
| Scheduler 不依赖精细调参 | 图 15：`U_low=0.1–0.3`、`T=2–8` 形成稳定平台 | 只测 1.5B math workload；没有 agentic/32B sensitivity | 中 |
| 动态迁移不改变 RL convergence | 图 16：dynamic/static reward curve 接近 | 单模型、单任务、64 GPU、未报多 seed 与 final score statistics | 弱到中 |

## 批判性分析

### 论证链条

论文先用图 2–5 把 compute waste 分成“component allocation 不随 phase 变”和“request FIFO 破坏 cache/完成顺序”两层，再分别用 online migration 与 priority scheduler 处理；图 13 展示 GPU ownership 随时间改变，图 11–12 给端到端增益，逻辑是闭合的。

不过，dynamic hypergraph、performance predictor 和三种 migration interface 是一组基础设施，实验只比较整个 DynaRL 或去掉 request priority，没有分别证明 hypergraph 比普通 DAG/status table 更必要、online regression 比规则式收缩更准、三种 migration 中每种贡献多少。1.98× 是组合系统相对某个 baseline/configuration 的最大值，不应外推为所有 RL workload 的统一收益。

### 假设压力测试

核心优化假设 rollout 是 concave dynamic donor、trainer 是近线性 receiver。若 trainer 受 all-reduce/network 限制、rollout 小 batch 反而因缩容变慢、reward/tool CPU 才是瓶颈，释放 GPU 不一定提高 pipeline minimum。Planner 没有把 topology、NIC congestion、energy 或 migration risk 写进 objective。

Priority 假设 later turn 更短且 prefix 仍在 cache。长 tool output 会增大下一轮 prefill；某些 agent 在最后一步生成长 report/proof，优先它可能延长其他 request 的等待。只按 `(tool_count, cached_prefix)` 排序还可能让新 episode starvation，需要 age/deadline/tenant quota 才适合共享训练平台。

Migration 依赖可中断点与状态完整转移。Create-before-destroy 的 rollback 描述很清楚，但 network partition、destination OOM、old worker crash、NCCL rebuild hang 和 scheduler crash 都没有实验。模型状态一致不等于整个 pipeline exactly once：迁移中的 request、tool side effect、reward 与 channel message 是否重复，论文没有说明。

### 实验可信度

64/128 H100、三个模型规模、math 与 multi-turn agentic 两类 workload、verl/RLinf/RLHFuse baseline、dynamic-only ablation、timeline、migration、parameter sweep 和 reward curve，覆盖了主要性能路径。Baseline 统一 SGLang/Megatron，有助于公平比较。

限制也很明确。RLHFuse 没有公开 artifact，由作者重实现；agentic 不比较 verl，原因是它只支持较慢 FSDP，因此结果不能区分 framework backend 与 scheduler 的差异。每个点只平均 warm-up 后 10 iteration，没有长训练、variance 或 cost。Convergence 只有 1.5B/64-GPU math 的单条 reward curve；没有 agentic reward、32B、多个 seed、最终质量或 sample efficiency。

所谓“large-scale”最大是 128 GPU，与设计动机中的 hundreds of GPUs 接近下界；没有 production cluster trace、千卡扩展、异构 GPU 或多 job interference。调度求解只处理 component summary，所以 200 ms 可外推；真正的 state transfer、NCCL rebuild、queue redistribution 和 network contention 则不能仅凭复杂度公式外推。

### 系统性缺陷

集中式 Global Scheduler 掌握 allocation 与 migration，manager/hypergraph/predictor 状态若丢失会影响所有 component。论文提到 worker daemon heartbeat 和用 RebootMigration 处理 hang，却没有 scheduler replication、durable graph、split-brain 防护或 fault-injection 结果。

Python AST 自动抽取对框架版本和动态代码较脆：wrapper、higher-order call、reflection、自定义 channel 或运行时创建 component 可能漏 edge。错误 hypergraph 会让 scheduler 违反 dependency 或错误迁移，论文没有静态检查的 precision/recall 与人工校验流程。

p2p migration 期间双份 worker/state、重建 DP/TP/PP group，并在 128 GPU 上转数秒。训练集群若资源完全占满，目标 worker “先创建”需要先让其他组件释放足够显存；多个迁移并发时还可能形成短时 network burst。论文没有报告额外峰值显存、迁移失败率或迁移之间的 admission control。

## 局限与后续工作

- **局限 1**：Planner 假设 homogeneous GPU、固定资源池和 static/dynamic 两类 scaling curve；没有 topology、network、CPU/tool 或跨 job 资源。
- **局限 2**：Predictor 没有误差、profiling cost、drift 或错判实验，hypergraph 自动抽取也没有 coverage 测量。
- **局限 3**：RLHFuse 为重实现，agentic baseline 只有 RLinf；端到端点仅取 10 iteration 均值。
- **局限 4**：正确性证据只有 1.5B math 的一条 reward curve；没有多 seed、agentic convergence、exactly-once tool/reward 或迁移 failure test。
- **局限 5**：最大 128 H100，未覆盖 heterogeneous/千卡、多租户和 production deployment。
- **后续工作 1**：公开每次 candidate 的 predicted/actual throughput、prediction error 与 regret，在 phase shift、network contention 和 unseen sequence distribution 下复测。
- **后续工作 2**：让 planner 显式建模 GPU type、NVLink/RoCE topology、migration bytes、CPU/tool queue 和 peak memory，比较 topology-oblivious policy。
- **后续工作 3**：给 priority queue 加 age/deadline/tenant term，在 late-long-turn、large-tool-output 与 mixed-agent trace 上报告 cache hit、JCT、starvation 和 throughput。
- **后续工作 4**：注入 scheduler/manager/worker crash、destination OOM、NCCL hang、partition 与 duplicate message，验证 rollback、state consistency 和 recovery time。
- **后续工作 5**：在 7B/32B math 与 agentic workload 上做多 seed 长训练，联合报告 wall-clock-to-reward、sample efficiency 与最终质量。

## 相关

- **相关概念**：[[KV-Cache]]、[[Data-Parallelism]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、动态调度、资源迁移
- **同类系统**：RLinf、verl、RLHFuse、[[SGLang]]、[[Megatron]]
- **同会议**：[[OSDI-2026]]
