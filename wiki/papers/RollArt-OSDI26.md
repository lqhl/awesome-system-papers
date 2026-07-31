---
type: paper
name: RollArt
full_title: "Roll Art: Disaggregated Multi-Task Agentic RL Training at Scale"
authors: [Wei Gao, Yuheng Zhao, Tianyuan Wu, Shaopan Xiong, Weixun Wang, et al.]
venue: OSDI
year: 2026
tags: [agentic-rl, disaggregation, heterogeneous-computing, distributed-training, serverless]
source_pdf: "[[osdi26-gao.pdf]]"
source_md: "[[osdi26-gao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 大规模解耦式多任务 Agentic RL 训练（OSDI 2026）

> **原题**：Roll Art: Disaggregated Multi-Task Agentic RL Training at Scale

> **一句话总结**：agentic RL 同时包含 compute-bound prefill、bandwidth-bound decode、CPU-heavy/long-tail environment 与 bursty stateless reward；RollArt 用 task-domain hardware affinity、trajectory-level asynchronous rollout、serverless reward 和 bounded-staleness training 把各阶段映射到 H800/H20/CPU/FaaS，在 Qwen3 8B–32B 上相对 Sync+、One-off、AReaL 将 step time 分别降低 2.05×、1.35×、1.31×，并在 3000+ GPU [[MoE|MoE]] 训练中连续运行一周。

## 问题与动机

多任务 agentic RL 的一次 trajectory 会在 LLM generation 与外部 environment 间往返数十轮，再做 reward 和 training。不同阶段甚至同一 rollout 内的硬件偏好相反：H800 compute 强，prefill-heavy workload 相对 H20 可到 0.53×时间；H20 HBM bandwidth/成本更合适，decode-heavy 相对 H800 可到 0.49×–0.79×；environment 是 stateful CPU process 且 heavy-tailed；reward stateless、bursty，dedicated GPU utilization 最低只有 7.4%（§3）。

现有 monolithic framework 把所有 role 放同一 GPU pool；部分异步系统只拆 training/rollout，仍把 generation、environment、reward 当一个 batch，slow/failing environment 让整批等待。RollArt 的目标是把 pipeline 与 trajectory 都解耦，再以数据/权重一致性协议限制 disaggregation tax 和 policy staleness。

## 关键观察 / 隐含假设

- **观察 1**：task domain 的 prefill/decode ratio 与 turn profile 在 production run 内相对稳定，足以用静态 domain label 做粗粒度 hardware affinity，而无需逐请求 profiler（§5.2、§8）。
  - **依赖假设**：policy 演化不会让同一 domain 中 observation/response distribution 大幅漂移。
  - **可能失效场景**：curriculum、tool policy 或 prompt mix 在训练中改变时，静态 mapping 会选错 GPU。
- **观察 2**：environment latency/failure 是 trajectory-local；按 batch barrier 同步会把 max latency 传播给所有样本，trajectory-level scheduler 可完成足够快样本后取消尾部（§6.1、图 11b）。
  - **依赖假设**：过采样/取消不会改变训练 sample distribution，且环境可以安全 abort/retry。
- **观察 3**：reward stateless 且到达 bursty，serverless 比预留 GPU 更匹配；trajectory payload 小，remote I/O 平均只约 0.01 s/call（§7.3/7.5）。
  - **依赖假设**：FaaS 支持需要的模型/沙箱、data privacy 与 cold-start SLO。
- **假设 1**：bounded policy staleness 可用更高 throughput 换取不明显的 convergence loss。
  - **证据强度**：中；`α=1` time-to-score 最佳，`α=2` 后期已出现 regression，更大 bound 只测 step time。

## 核心方法

RollArt 分 resource/data/control 三 plane。用户用 `hw_mapping` decorator 将 training/prefill-heavy generation 映到 H800、decode-heavy task 映到 H20、environment 映到 CPU、reward 用 `register_serverless` 指向 FaaS。ResourceManager 用共享 metadata store 分配 pool；Worker 封装方法和硬件偏好，Cluster 管 ActorTrain、ActorGen、Reward、Environment worker group（图 7、Listing 1）。

control plane 的 EnvManager 为每条 trajectory 独立推进 generation→environment turn，LLMProxy 聚合 generation 请求但不强制 trajectory 同步；完成 trajectory 立即送 reward 并写 SampleBuffer，trainer 一旦有足够 scored samples 就更新。redundant environment rollout 可以启动超额 trajectory，在达到 batch 目标后取消 straggler（§6.1、§7.4）。

training 与 rollout 并行，以 weight version 和 staleness bound `α` 控制 sample：trajectory 在每 turn 检查 version，超过界限就 abort/restart，最多保留 `O(αE)` pending trajectories。`α=1` 是默认，避免 AReaL 只在 trajectory start 检查而让长尾样本越来越 stale（§6.2）。

跨 H800 training/H20 inference cluster 的 weight 通过 Mooncake CPU store：trainer 将约 1 GB bucket 异步 push，inference on demand pull；push/pull 与 ongoing rollout overlap。trajectory 用 Ray object reference 分片传输，集群内 weight 用 [[NCCL|NCCL]]。可选 PD disaggregation 进一步把同一 request prefill 路由 H800、decode 路由 H20（§6.3）。

## 设计取舍

- **异构效率换静态配置**：domain annotation 简单、可解释，但 mapping 和 PD ratio 由用户选择，不能自动适应 drift。
- **吞吐换 on-policy fidelity**：`α` 放宽减少 abort/idle，却可能恶化 time-to-score；论文最终选最严格 `α=1`。
- **tail tolerance 换额外工作**：redundant environments 通过过采样消除 max tail，会浪费被取消 trajectory 的 [[LLM|LLM]] tokens/CPU。
- **serverless elasticity 换外部依赖**：消除 reward standby GPU，却引入 remote payload、cold start、provider failure 与成本/隐私问题。
- **disaggregation 换 weight movement**：32B 未 overlap 的 push+pull 达 157 s，虽实际 exposed 为 9.6 s，仍是最大 tax（表 4）。

## 实验与结果

- 96×H800 与 32×H20，集群内 400Gb [[RDMA|IB]]、跨集群 200Gb Ethernet，外加两套 CPU environment cluster 和内部 FaaS；默认 128 GPUs，Qwen3 8B/14B/32B、32k context、GRPO batch 512/group 8（§7.1）。
- Qwen3-32B 到 validation score 0.85 时，`α=1` 相对 Sync+、One-off、AReaL step time 分别改善 2.05×、1.35×、1.31×；整体相对 Sync throughput 高 2.65–4.58×（图 10）。
- 等成本 rollout 配置中，64 H800+24 H20 affinity mix 相对 H20-only step time 改善 1.30–1.68×，相对 72 H800-only 改善 1.12–1.37×（图 11a）。
- environment latency mean 10 s、std 1–10 s 时，trajectory-level async 相对 batch rollout speedup 从 1.23× 升到 2.27×（图 11b）。
- reward offload 把 dedicated reward GPU utilization 从 6% 提至 88%，step rollout time 约减半；staleness bound 1→6 最多再改善 step time 1.22×，但 `α=2` 已有后期 convergence 回退（图 12/13）。
- cross-cluster 8B/14B/32B naive weight cost 38.6/84.1/157.0 s，overlap 后 exposed pull 1.4/5.1/9.6 s；environment/reward I/O 平均 0.02/0.01 s，最大 1.4/2.1 s（表 4、§7.5）。
- PD disaggregation 对 Qwen3-32B 提升 1.03–1.05×，对 Qwen3-30B-A3B MoE 提升 1.11–1.21×，说明 phase-level affinity 很依赖模型/workload（表 5）。
- production 3000+ GPU、hundreds-of-billions MoE 运行一周；调参后前 25 steps 累计时间加速 1.66×，environment reset success 高于 99.99%，一周观察一次 worker failure（图 15、§8）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 异构 hardware affinity 可降低 agentic rollout step time | 图 11a | Qwen3 8B/14B/32B、H800/H20、等成本近似 | 强 |
| trajectory-level async 隔离 environment tail | 图 11b/14b | Gaussian synthetic latency 与 GEM-math redundant rollout | 强 |
| bounded-staleness orchestration 改善 time-to-score | 图 10/13 | Qwen3-32B target 0.85、α=1/2；更大 α 未完整 convergence | 强 |
| serverless reward 显著提升资源利用 | 图 12、§7.3/7.5 | 内部 FaaS、特定 reward model/payload | 强 |
| 架构可扩展到 3000+ GPU production | §8、图 15 | 单个 MoE job、一周、内部 cluster | 中 |

## 批判性分析

### 论证链条

论文的 workload characterization 与四项 requirement 对应清楚，end-to-end 后再逐项 ablation，证据链完整。最大的混合变量是 RollArt 集成了 affinity、trajectory async、serverless、weight overlap、redundancy 等多种优化；相对开源/重实现 baseline 的 2×+收益不是单一 abstraction 的结果。production 证明可运行，但没有 production A/B baseline。

### 假设压力测试

静态 domain mapping 是显式 limitation。同一 SWE domain 中 prompt 可从 long observation 转向 long response，H800/H20 最优点会改变。redundant rollout 会偏向快 environment/短 trajectory，若直接取前 N 完成样本，可能产生 length/success bias。`α=1` 仍允许 rollout/training overlap，其严格 on-policy 性取决于 version check 和 abort timing。

### 实验可信度

三模型、五 task、异构 cluster、time-to-score、throughput、ablation、tax 与大规模 deployment，覆盖很强。baseline AReaL 是在 RollArt codebase 重实现，Laminar 因 closed source 只用“isolated gains 下界”推断，不能等同直接比较。production failure 仅一次，无法验证文中 robust fault-tolerance 的统计效果。

### 系统性缺陷

60K Python LOC、Redis metadata、Ray、Mooncake、Kubernetes、FaaS 和多个 cluster 组成很大的 failure surface。SampleBuffer 是 trainer 等待点，production 最长 iteration 中 `get_batch` 可占 62% idle，说明 disaggregation 没消除供给不足。跨 cluster bandwidth 或 Mooncake store 故障会同时阻塞所有 inference worker；exactly-once trajectory/reward 与取消后的环境清理未系统证明。

## 局限与后续工作

- **局限 1**：homogeneous cluster、strict on-policy 或 compute-light RL 中，R1/R4 优势缩小（§9）。
- **局限 2**：hardware affinity 静态声明，PD ratio 也需人工调优。
- **局限 3**：redundant rollout 的 sample-selection bias、wasted tokens 与 FaaS dollar cost 未报告。
- **后续工作 1**：用 online profiler 按 domain 估 prefill/decode/turn distribution，量化 remap oscillation、迁移成本和相对 oracle gap。
- **后续工作 2**：比较“前 N 完成”“随机保留”“importance weighted” redundant trajectories 的 reward/convergence 与浪费 tokens。
- **后续工作 3**：注入 Redis/Mooncake/FaaS/cluster partition，验证 version、SampleBuffer 与 trajectory state 在重试中不重复训练或丢失。

## 相关

- **相关概念**：[[Agentic-RL]]、[[RL-Post-Training]]、[[Prefill-Decode-Disaggregation]]、[[Bounded-Staleness]]、[[Serverless-Computing]]
- **同类系统**：[[AReaL]]、[[verl]]、[[Laminar]]、[[Mooncake]]
- **同会议**：[[OSDI-2026]]
