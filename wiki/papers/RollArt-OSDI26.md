---
type: paper
name: RollArt
full_title: "ROLLART: Disaggregated Multi-Task Agentic RL Training at Scale"
authors: [Wei Gao, Yuheng Zhao, Tianyuan Wu, Shaopan Xiong, Weixun Wang, Dakai An, Lunxi Cao, Dilxat Muhtar, Zichen Liu, Haizhou Zhao, Ju Huang, Siran Yang, Yongbin Li, Wenbo Su, Jiamang Wang, Lin Qu, Bo Zheng, Wei Wang]
venue: OSDI
year: 2026
tags: [agentic-rl, disaggregation, heterogeneous-computing, distributed-training, serverless]
source_pdf: "[[osdi26-gao.pdf]]"
source_md: "[[osdi26-gao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# RollArt：大规模解耦式多任务 Agentic RL 训练（OSDI 2026）

> **原题**：ROLLART: Disaggregated Multi-Task Agentic RL Training at Scale

> **一句话总结**：Agentic RL 的 prefill、decode、环境、reward 和训练适合不同硬件，batch barrier 又会把环境长尾放大；RollArt 用 task-domain hardware mapping、trajectory-level async rollout、[[Serverless|serverless reward]] 和 bounded-staleness training 拆开这些阶段，在 Qwen3-32B 达到平均 validation score 0.85 的时间上，相对 Sync+、One-off、AReaL 分别缩短 2.05×、1.35×、1.31×，并在 3,000+ GPU 上训练数千亿参数 MoE 一周。

## 问题与动机

Agentic reinforcement learning（agentic RL）不是一次生成一段回答。Actor [[LLM]] 先看 observation，生成 action；外部 environment 执行动作并返回新 observation；这个循环可持续几十甚至上百 turn，完成后才计算 reward，再用 trajectory 更新模型。一次训练 step 因而至少包含 generation、environment、reward 和 training 四种 workload。

这四类工作不适合同一硬件：

- Training 和多次长 prefill 需要高 compute 与高速 collective，适合 H800；
- 长 decode 主要吃 HBM bandwidth，较便宜的 H20 可能更合适；
- Environment 是 stateful CPU/container workload，会受 image pull、disk、network 和 turn 数影响；
- Reward 常是固定的 rule、sandbox 或 judge model，stateless 且在 rollout 结束时 burst 到达，长期预留 GPU 很浪费。

论文在 Qwen3-8B/SWE-bench 的 32×H800 run 中测到：无失败的 step 平均 365.7 s，LLM generation 只占 53.8%，training 23.1%，env.reset 14.6%；发生环境失败时平均增到 513.3 s，env.reset 占 78.2%（图 3）。因此，“只优化 generation”无法解决 agentic RL 的主要长尾。

已有 monolithic framework 把 rollout/reward/training 放在同一 GPU pool；部分系统只拆 training 和 rollout，仍把一个 batch 内的 LLM/environment/reward 同步推进。慢 environment 会让所有快 trajectory 在 barrier 前等待，reward GPU 又大部分时间空闲。RollArt 的目标是把 stage 和 trajectory 两个层级都解耦，同时限制 policy staleness 与跨 cluster weight movement。

## 关键观察 / 隐含假设

- **观察 1：Generation 并非统一 bandwidth-bound。** Cost-equivalent 的 2×H800 与 6×H20 上，prefill-heavy FrozenLake 用 H800 的 rollout time 最低为 H20 的 0.53×；decode-heavy GEM-Math 用 H20 则为 H800 的 0.49×–0.79×（§3.1、图 4）。
  - **设计含义**：不能把所有 rollout 固定在“便宜、带宽高”的 GPU；应按 task domain 路由。
  - **依赖假设**：同一 domain 的 turn、prompt/response 和 prefill/decode 比例在训练中相对稳定。
- **观察 2：环境长尾是 trajectory-local，却会被 batch barrier 全局放大。** Env.reset 在生产可长达数百秒；batch environment interaction 相对 ideal execution 最多增加 21.3% rollout time（§3.1、图 5）。
  - **设计含义**：每条 trajectory 要独立推进 generation→env.step，不能等整批最慢者。
  - **风险**：独立推进只消除 trajectory 之间的直接 barrier；trainer 仍要等 SampleBuffer 收够一个 batch。
- **观察 3：Reward 既 stateless 又 bursty。** Qwen3-8B/SWE-bench 中，专门给固定 7B reward LLM 留 4×H800，平均利用率只有 7.4%（§3.1、图 6）。
  - **依赖假设**：Reward 不依赖本地 mutable state，可安全重试，内部 FaaS 能提供所需 GPU、sandbox、privacy 和吞吐。
- **观察 4：Trajectory packet 小而频繁，weight update 大而带宽敏感。** Environment exchange 从 KB 到数 MB，关注稳定 latency；Qwen3-32B weight 为 61.02 GB，跨 cluster TCP 传输 29.649 s，400 Gbps [[RDMA|RDMA]] 为 9.442 s（§3.2、表 3）。
  - **设计含义**：trajectory 用异步 object transfer，weight 则 bucketize、经 store 异步 overlap。
- **观察 5：放宽 staleness 会减少 abort，但不保证更快收敛。** `α=1→6` 的最佳 step-time 收益最多 1.22×；`α=2` 已在后期 time-to-score 上落后 `α=1`（§7.2–§7.3、图 10/13）。
- **假设 1：异构、可拆分的基础设施已经存在。** RollArt 依赖 H800/H20/CPU/FaaS 多 resource pool、200/400 Gbps 网络、Redis、Ray、Mooncake 和 Kubernetes。
  - **可能失效场景**：homogeneous cluster、strict on-policy RL、compute-light RL 或没有 elastic reward backend 时，多项设计退化为 no-op（§9）。

## 核心方法

### 1. Resource、data、control 三个 plane

**Resource plane** 的 ResourceManager 用共享 metadata store（实现可用 Redis）记录 H800、H20、CPU 和 serverless endpoint。用户用 Python decorator 为 Worker method 声明 hardware affinity；preferred pool 不可用时可以回退到 compatible default resource，避免 deployment 阻塞。

**Data plane** 用 Worker 和 Cluster 抽象。Worker 封装 train、generate、environment、reward 方法及其 hardware annotation；Cluster 是一组同 role Worker 的 proxy/controller，负责 ActorTrain、ActorGen、Environment、Reward 四类 worker group，并把方法映射到 [[Megatron|Megatron]]、[[vLLM]]/[[SGLang|SGLang]] 或 serverless URL（§5、Listing 1–2）。

**Control plane** 由 rollout scheduler、LLMProxy 和 SampleBuffer 组成。它不要求用户写 coordination logic：系统独立推进每个 trajectory，把完成并评分的 sample 放进 buffer，trainer 收够 batch 后更新模型（图 7）。

### 2. Trajectory-level rollout 与 reward

每个 EnvManager 只管理一个 environment lifecycle。它 reset 后循环执行：把历史 `(observation, action)` 发给 LLMProxy、取得下一个 action、调用 env.step、保存返回 observation。不同 EnvManager 没有 turn barrier。

Inference worker 运行 non-blocking event loop：在 engine step 之间处理 `ADD` 和 `ABORT` command；没有 command 时继续 vLLM/SGLang 的 prefill/decode。某条 request 完成立即 callback 对应 EnvManager，不等别的 request。Trajectory 完成后，reward worker 立刻异步调用 serverless function，评分与其他 rollout 重叠（§6.1、图 8）。

这让慢 environment 不会挡住快 trajectory 的下一轮，但环境本身仍可能失败。可选的 redundant environment rollout 会启动多于训练 batch 所需的 trajectory，收够目标数量后取消其余 straggler；它以额外 LLM token/CPU 工作换 tail tolerance（§6.3）。

### 3. 有界陈旧度的异步训练

Rollout 和 training 在独立 cluster 并行。每轮权重同步有六步（§6.2、图 9）：

1. `get_batch` 阻塞到 SampleBuffer 有足够 scored trajectory；
2. `suspend` 让 LLMProxy 暂停接收新 generation，保留 in-flight trajectory；
3. `update` 把最新 weight 更新到 inference worker；
4. `resume` 恢复 generation；
5. 对旧版本下的 in-flight trajectory 重算 [[KV-Cache]]，用新权重继续 rollout；
6. ActorTrain 同时对第 1 步取得的 batch 执行 `train_step`。

若当前 model version 为 `n`，buffer 只接受由不早于 `n−α` 版本发起的 trajectory，超界就 abort；`E` 个 environment 时，pending sample 上界为 `O(αE)`。论文默认 `α=1`。正文实验描述 RollArt 会在每个 turn 控制 staleness，而 §6.2 的形式化写法使用“trajectory initiated version”；两种口径对一条 trajectory 中途更新权重时并不完全相同，论文没有进一步给出 action-level on-policy 定义。

### 4. 按数据路径选择传输机制

Trajectory 和 supervision data 以 Ray object reference 传递，并按 worker parallelism sharding。Cluster 内 weight update 用 [[NCCL]] 和 NVLink/InfiniBand。跨 H800 training 与 H20 inference 的慢 Ethernet 路径则用 [[Mooncake]] CPU store：trainer 把更新后的 weight 切成约 1 GB bucket 异步 publish，inference worker 按需 pull；push/pull 都尽量与 ongoing rollout overlap（§6.3）。

### 5. 从 task-level affinity 扩展到 phase-level

默认 mapping 以 task domain 为粒度：prefill-heavy task→H800，decode-heavy→H20。可选 prefill/decode disaggregation（PD）进一步让同一 request 的 prefill 在 8×H800 node、decode 在 8×H20 node。论文把 1P3D、2P2D 当显式配置，尚未自动搜索最优 ratio（§6.3、§7.4）。

## 设计取舍

- **静态 domain mapping 换简单可控。** 一周 production run 中 domain profile 无需重调，但 curriculum、policy 或 prompt mix 改变后可能选错 GPU；在线 profiler 仍是 future work。
- **吞吐换 policy freshness。** `α` 越大越少 abort/idle，却更偏离最新 policy；实验最终选择最严格的 `α=1`。
- **继续 trajectory 换重算成本和语义复杂度。** Weight update 后重建 KV 能复用 environment progress，但同一 trajectory 的历史 action 可能来自旧 policy、后续 action来自新 policy。
- **消尾换浪费和 sample bias。** Redundant rollout 让“先完成的 trajectory”更容易进入 batch，可能偏向短、快或成功环境，并丢弃已经花掉的 token。
- **Serverless 弹性换外部依赖。** 释放 dedicated reward GPU，却引入 remote cost、cold start、provider failure、数据治理和 exactly-once reward 问题。
- **解耦换 weight tax。** 32B 未 overlap 时 push+accumulated pull 为 157.0 s；overlap 后仍暴露 9.6 s，是主要 disaggregation overhead（表 4）。

## 实验设计

Testbed 有 96×H800 和 32×H20，cluster 内 400 Gbps InfiniBand，跨 cluster 200 Gbps Ethernet；另有两套 CPU environment cluster 与内部 serverless reward platform。默认共 128 GPUs，RollArt 把 32×H800 留给 training，其余 H800/H20 做 rollout。Baseline 使用 128×H800，因此论文估算 RollArt 每 GPU-hour cost 约为 baseline 的 83%，不是完全相同硬件的 A/B（§7.1）。

模型为 Qwen3-8B/14B/32B，最大 context 32K；环境是 SWE-bench、WebShop、FrozenLake、GEM-math、GEM-game。训练用 GRPO，batch 512、group size 8、uniform task sampling；rollout 为 vLLM 0.8.4，training 为 Megatron 0.12.2。

Sync 和 Sync+ 都在 RollArt codebase 上实现；Sync+ 已加入 async reward、async environment 和 serverless。One-off 与 AReaL 也带 Sync+ 优化，AReaL 是作者在 RollArt 内重实现。Laminar closed-source，没有直接运行，只用功能分解做推断。Step time 默认取 5 iterations 平均；Qwen3-32B 每 10 iteration测一次 average validation score（§7.1）。

## 实验与结果

- **端到端 convergence 与 throughput。** Qwen3-32B 达到 average validation score 0.85 时，`α=1` 相对 Sync+、One-off、AReaL 的 time-to-score 分别缩短 2.05×、1.35×、1.31×。Across 8B/14B/32B，RollArt throughput 是 Sync 的 2.65×–4.58×；相对 AReaL 再高 1.22×–1.36×（§7.2、图 10）。这不是与 Laminar 的直接数字比较。
- **Hardware affinity 和 trajectory async 各有独立收益。** 近似等成本的 64 H800+24 H20 mix，相对 208 H20-only 把 step time 降 1.30×–1.68×，相对 72 H800-only 降 1.12×–1.37×。Environment latency 取均值 10 s、标准差 1→10 s 的 Gaussian injection 时，trajectory-level 相对 batch rollout 从 1.23× 提高到 2.27×（§7.3、图 11）。
- **Serverless 回收了 reward 预留资源，staleness 仍有质量代价。** 16×H800 上三个 concurrent math jobs 中，local reward 的 GPU utilization 约 5.8%/6%，serverless 方案为 88%；因为把另外 4 张 GPU 也给 rollout，平均 rollout time 从 158 降到 77 s。`α=1→6` 最多再少 1.22× step time，但 `α=2` 的后期 time-to-score 已退化（§7.3、图 12–13）。
- **Cross-cutting optimization 的收益不是免费。** Async weight transfer 相对同步 NCCL-style cross-cluster scheme 把 step time改善 1.10×–1.16×；redundant GEM-math rollout 最高 1.62×。PD 对 Qwen3-32B 的 1P3D/2P2D 仅 1.03×/1.05×，对 Qwen3-30B-A3B [[MoE]] 为 1.11×/1.21×，说明 phase affinity 强烈依赖模型（§7.4、图 14、表 5）。
- **Disaggregation tax 主要是 weight。** 8B/14B/32B 的 naive push+pull 为 38.6/84.1/157.0 s，overlap 后 exposed pull 是 1.4/5.1/9.6 s。Environment payload 最大 2.7 MB，I/O 最大/平均 1.4/0.02 s；reward payload 最大 5.2 MB，最大/平均 2.1/0.01 s（§7.5、表 4）。这些是内部 network/FaaS 条件下的数字。
- **Production 证明能运行，也暴露剩余 bubble。** 过去 9 个月已有数千 job 使用 RollArt；论文详述一个 3,000+ GPU、数千亿参数 MoE 的一周 run。Prompt/response 最长 12K/46K，task 平均 turn 1–48；最长 response 是均值 5×–9×，最大 environment turn 超过均值 40×。最长 iteration 1.5 h，`get_batch` 等 sample 最多占 62% 时间，理想移除只可再少 22%。调 training:generation ratio 和 [[Prefix-Caching|prefix cache]] 后，前 25 steps 累积时间改善 1.66×；这是同一生产 job 的 tuning 前后，不是相对其他 RL system 的 A/B。Env.reset success 提至 99.99% 以上，一周观察到一次 worker failure（§8、图 15）。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 多任务 rollout 需要按 hardware affinity 放置 | 图 4、图 11a：H800/H20 最优方向随 task 改变，mix 再少 1.12×–1.68× step time | Qwen3 8B–32B、两类 GPU、五个 task；mapping 人工声明 | 强 |
| Trajectory-level async 能隔离 environment variance | 图 11b：Gaussian std 1→10 s 时为 batch 的 1.23×–2.27× | 合成 latency injection；production tail只做 characterization | 强 |
| Bounded staleness 改善 time-to-score | 图 10：`α=1` 比 Sync+/One-off/AReaL 快 2.05×/1.35×/1.31× | 只在 Qwen3-32B、target score 0.85；AReaL 为重实现 | 强 |
| Serverless reward 提高 GPU efficiency | 图 12：利用率 6%→88%，rollout 158→77 s | 内部 FaaS、16 H800、三个 math jobs；未报告 dollar cost | 强 |
| 架构可扩到 3,000+ GPU production job | §8、图 15：MoE 一周运行、一次 worker failure | 单个内部 job；1.66× 包含手工调资源与 prefix cache | 中 |

## 批判性分析

### 论证链条

论文先用 Figure 3–6 把 generation、environment、reward、weight communication 的瓶颈分开，再让 R1–R4 一一对应 hardware mapping、trajectory async、serverless 和 bounded staleness；端到端结果后又逐项消融，设计—证据链比较完整。Production section 不只报规模，也暴露 `get_batch` 仍占 62% 的 idle，这是有价值的负面结果。

需要避免把所有倍数都归因于一个 abstraction。Sync+、One-off、AReaL、RollArt 逐级叠加 async environment、serverless、training overlap、staleness control 和 affinity；2.65×–4.58× 是一组机制的总效果。RollArt 还使用 H20/H800 mix，baseline 是 128 H800，论文按价格估算前者每 GPU-hour cost 为 83%；这更接近成本导向比较，不是同硬件 controlled comparison。

### 假设压力测试

Static task-domain affinity 在论文的一周 job 内稳定，但 policy、curriculum 和 prompt mix 可能逐步改变 input/output/turn distribution。同一个 SWE domain 也可能一阶段长 observation、下一阶段长 response。没有 online profiler 时，mapping 错误不会自动纠正；preferred resource fallback 又可能悄悄把 task 路到性能不同的 GPU。

Asynchronous correctness 需要更清楚的定义。§6.2 用 trajectory 的“发起版本”约束 `α`，§7.2 又说每个 turn 检查并 abort stale trajectory；weight update 后还会保留过去 observation/action，只重算 KV 并用新 policy继续。这样的 mixed-version trajectory 对 GRPO 的 importance correction、log-prob recomputation和 on-policy 偏差，论文没有形式化说明。

Redundant rollout 取先完成的样本，可能偏向短 trajectory、低 network latency 或没有 environment failure 的 task。Uniform task sampling 发生在启动时，不保证完成 batch 仍 uniform。需要记录被取消 token 与 task/reward distribution，才能确认 1.62× speedup 没有换来训练偏差。

### 实验可信度

Qwen3 三个规模、五个 task、H800/H20、convergence、throughput、四项消融、communication tax 和 production deployment，覆盖面很强。对 environment variance 的 synthetic sweep 可控制变量，Figure 10 又补了真实 training convergence。

局限是 AReaL 为重实现，Sync/Sync+ 也来自同 codebase；Laminar 因 closed source 没有直接比较。论文声称把多个 isolated gain “组合”可作为 RollArt 对 Laminar gap 的下界，但各机制可能重叠、互相限制，不能简单相乘或保证 lower bound。Time-to-score 只在 Qwen3-32B 和一个 0.85 threshold 上测，`α>2` 只给 step time，没有完整 convergence curve。

Serverless 的 6%→88% 同时把 local reward 的 4 张 GPU 改给 rollout，所以它证明的是“重新分配+远程 reward”的整体效果，不是 reward kernel 本身快了。Internal FaaS 的 cold start、GPU billing、queue limit、failure 和 data isolation没有公开。

### 系统性缺陷

约 60K Python LOC，加上 Ray、Redis、Mooncake、Kubernetes、Megatron、vLLM/SGLang 和内部 FaaS，形成很大的 failure surface。论文描述 inference restart/migrate、training checkpoint 和 environment backoff，却没有系统 fault injection；一周只出现一次 worker failure，不足以评估恢复正确性或 MTTR。

SampleBuffer 是新的集中等待点。Production 最差 step 仍因 `get_batch` 让 GPU idle 62%，说明 trajectory async 没消除 sample supply不足。Mooncake/Redis/FaaS 故障可能同时影响大量 worker；trajectory abort、reward retry 和 SampleBuffer insert 是否 exactly once、取消 environment 是否彻底清理，论文未证明。

## 局限与后续工作

- **局限 1**：Hardware affinity 静态声明，PD ratio 也人工选择；domain drift 时没有自动 remap。
- **局限 2**：Bound `α` 与 mixed-version trajectory 的 on-policy 语义没有形式化，完整 convergence 只覆盖 `α=1/2`。
- **局限 3**：Redundant rollout 的 wasted token、完成顺序 bias 和 serverless dollar/privacy cost 未报告。
- **局限 4**：Baseline 部分为同 codebase 重实现，Laminar 没有直接运行；硬件与 GPU-hour成本也不完全相同。
- **局限 5**：Production 仍有最高 62% `get_batch` idle，且可靠性证据只是一周一次 worker failure。
- **后续工作 1**：在线估计每个 domain 的 prefill/decode/turn distribution，报告 remap frequency、迁移成本、fallback 次数和相对 oracle gap。
- **后续工作 2**：为每个 action 记录 behavior-policy version/log-prob，比较 trajectory-start 与 per-turn staleness bound 的 bias、abort 和 convergence。
- **后续工作 3**：比较 first-N、random-N、stratified-N 和 importance-weighted redundant sample，量化 task/reward distribution 与浪费 token。
- **后续工作 4**：报告 FaaS cold-start、queue、GPU-second bill 与 failure；对 Redis/Mooncake/FaaS/cluster partition 做 fault injection，验证 sample/reward exactly once。
- **后续工作 5**：围绕 SampleBuffer 做 adaptive batch sizing 或 trainer backpressure，以 production 的 `get_batch` idle、time-to-score 和 sample freshness 为目标。

## 相关

- **相关概念**：agentic RL、[[Disaggregation]]、bounded staleness、[[Serverless]]、[[MoE]]、[[KV-Cache]]、[[NCCL]]
- **同类系统**：AReaL、veRL、Laminar、[[Mooncake]]、[[vLLM]]
- **同会议**：[[OSDI-2026]]
