---
type: paper
name: HetRL
full_title: "HetRL: Efficient Reinforcement Learning for LLMs in Heterogeneous Environments"
authors: [Yongjun He, Shuai Zhang, Jiading Gai, Xiyuan Zhang, Boran Han, Bernie Wang, Huzefa Rangwala, George Karypis]
venue: MLSys
year: 2026
tags: [rlhf, heterogeneous-gpu, scheduling, distributed-training, ppo, grpo]
source_pdf: "[[7f39f8317fbdb1988ef4c628eba02591.pdf]]"
source_md: "[[7f39f8317fbdb1988ef4c628eba02591]]"
---

# HetRL: Efficient Reinforcement Learning for LLMs in Heterogeneous Environments (MLSys 2026)

> **一句话总结**：观察到跨区异构 GPU（A100/L40S/L4 + 1–60ms 延迟）总量可超过单区同构集群，但 PPO/GRPO 四模型六任务 workflow 使 per-model 异构调度不可扩展；HetRL 将 RL 调度建模为 NP-hard 联合优化，用五级搜索 + nested SHA + 双层 swap GA + 异构 cost model 在 [[vLLM]]/Megatron 上实现，20k GPU-hour 评测吞吐最高 **9.17×**、平均 **3.17×** 于 verl/StreamRL。

## 问题与动机

[[RLHF]] / RL post-training（PPO、GRPO 等）已成为提升 [[LLM]] 推理与对齐能力的主流路径，算力需求随模型规模爆炸式增长。工业界现状是依赖**单区域内大量同构高端 GPU + 高带宽网络**（如 [[vLLM]] 生态下的 verl、OpenRLHF），而全球数据中心存在大量**中低端或上一代 GPU 跨地域闲置**（Strati et al. 2024 等测量）。把这些 geo-distributed 异构算力用于 RL 训练，在资源总量上可能超过任何单一同构集群。

但 RL workflow 与单模型训练/推理根本不同：以 PPO 为例，同时涉及 **actor、critic、reward、reference 四个模型**和 **actor generation、reference/reward/critic inference、actor/critic training 六个任务**，任务间有复杂数据与计算依赖。异构环境下高效调度需要**联合优化**：（1）模型共置与任务并行；（2）各模型内 [[Tensor-Parallelism]]/[[Pipeline-Parallelism]]/DP 划分；（3）tasklet 到异构设备的细粒度映射。

现有 RL 系统（verl、StreamRL、RLHFuse 等）搜索空间面向**同构 GPU + 高带宽网络**设计；StreamRL 虽支持跨数据中心，但要求**组内 GPU 仍同构且同 DC**。更自然的做法是复用 DTFM、Metis、Helix、ThunderServe 等**单模型异构调度**算法逐个套到 RL 各任务上——但 verl/RLHFuse 报告，即便同构环境搜索一个 RL plan 也需数百万到数十亿候选、数百到数千秒；单模型异构搜索还要慢 **1000–10000×**，对多模型 workflow **既不 practical 也不可扩展**。

HetRL 针对上述缺口：在异构 GPU 与异构网络基础设施上，为完整 RL workflow 提供**端到端联合调度**与分布式执行系统。

## 关键观察 / 隐含假设

- **观察 1：RL workflow 内各任务瓶颈与资源画像高度分化，异构硬件下「一刀切」并行策略必然浪费算力。** actor generation 偏 memory-bound、需维护 [[KV-Cache]]；actor/critic training 偏 compute-bound、需 activations/gradients/optimizer states；reference/reward inference 又是另一套 serving 特征。同规模 LLM 用于各角色时，最优 TP/PP/DP 与设备映射并不相同。
  - **依赖假设**：评测中 actor/critic/reward/reference **共用同尺寸 Qwen**（4B/8B/14B），但方法允许不同任务用不同尺寸模型；cost model 能分项估计 gen/inference/training + 异构带宽延迟。
  - **可能失效场景**：reward/critic 远小于 actor、或 MoE/多模态 RL 使任务图结构变化时，task grouping 与 cost model 需重标定；论文未测异构模型尺寸组合。

- **观察 2：跨区异构网络的延迟/带宽差异会放大错误调度的代价，且随地理跨度单调恶化。** 实验模拟 Single-Region → Multi-Region-Hybrid（10ms/5Gbps，edge 1Gbps）→ Multi-Country（5–30ms）→ Multi-Continent（5–60ms/0.9–5Gbps）。场景 2–4 相对 verl 的加速倍数显著大于场景 1，说明**网络异构是主要 pain point**，而非仅 GPU 算力差。
  - **依赖假设**：跨区链路延迟/带宽可用静态 profile 建模（AWS 十区域实测表），且训练期间相对稳定；resharding 与 async 权重同步成本可并入 cost model。
  - **可能失效场景**：动态拥塞、故障切换、或非 AWS 网络栈（仅测 OFI NCCL + EFA）时，静态 cost model 可能系统性偏差；论文未报告 plan 上线后相对估计值的 drift。

- **观察 3：RL 调度搜索空间虽 NP-hard 且巨大，但可用多级分解 + 预算分配把搜索集中在有希望的 task grouping / GPU grouping 上。** 作者将问题形式化为 partitioning strategy ρ（tasklet 图）与 assignment strategy σ（设备映射）的联合最小化，证明 NP-hard；用 **5 级 coarse-to-fine 框架**（task grouping → coarse/medium/fine GPU assignment → intra-model parallelization）配合 **nested Successive Halving（L1/L2）** 与 **genetic algorithm + 跨 task / 跨 tasklet 双层 swap（L3–L5）**，在固定搜索预算下优于 verl 与「简单拼接异构算法」的 HetRL (simple)。
  - **依赖假设**：cost model 对真实 iteration time 的排序与真实执行足够一致，使 SHA 剪枝不会过早丢掉最优解；搜索预算 B 由用户给定且可摊销到长跑训练任务上。
  - **可能失效场景**：短作业搜索开销占比高；cost model 对 async PPO/GRPO 的 staleness、bubble overlap 估计误差大时，选出的 plan 可能次优——Fig. 4 显示同预算下 HetRL 收敛优于 verl，但未给绝对 wall-clock search 秒数与在线重规划频率。

- **假设 1：基于 verl + Megatron-LM + [[vLLM]] 的执行引擎足以承载异构 fine-grained tasklet 放置，无需重写训练/推理 kernel。**
  - **证据强度**：**中**——~3k LOC 扩展 scheduler/profiler/execution engine/load balancer，工程可行；但依赖 Megatron/vLLM 对异构 TP/PP 的支持边界，论文未讨论跨 vendor GPU 或自定义 collective 栈。

- **假设 2：吞吐（tokens/s 或 samples/s）是异构 RL 部署的首要优化目标，收敛精度与跨设备数值一致性可沿用标准 RLHF 设定而不单独验证。**
  - **证据强度**：**弱**——全文聚焦 throughput；Limitations 明确未研究跨异构 GPU 交换数据时的 precision 问题是否影响收敛；async 模式已知有 staleness 精度代价，论文只比吞吐。

## 核心方法

HetRL 将异构 RL 训练调度形式化为：给定 RL workflow 计算图 G 与设备拓扑图 GD（节点标计算力/显存/HBM 带宽，边标延迟/带宽），求 partitioning ρ 与 assignment σ，最小化 cost model C 估计的**每 iteration 执行时间**，并满足内存等约束（Definition 1；NP-hard，Appendix A 归约到 graph partitioning / knapsack / minimum makespan）。

### 五级搜索框架

对应 Fig. 1 的 coarse-to-fine 构造：

1. **Level 1 — Task grouping**：将六类 RL 任务划分为不相交 task group；同组任务共享 GPU 集且模型共置。
2. **Level 2 — Coarse GPU assignment**：按 group 数量划分 GPU group（只定每组 GPU **数量**，不定具体卡）。
3. **Level 3 — Medium GPU assignment**：为每个 task group 生成候选的**具体 GPU 集合**。
4. **Level 4 — Intra-model parallelization**：对每个候选 assignment 枚举可行 TP/PP/DP，将任务分解为 tasklet。
5. **Level 5 — Fine GPU assignment**：将 tasklet 映射到具体 GPU，形成完整 execution plan。

Levels 1+4 实例化 ρ；Levels 2+3+5 实例化 σ。

### 搜索算法

- **Nested SHA（L1/L2）**：把 task grouping 与 GPU grouping 视为 multi-armed bandit arms，以 cost model 估计时间为 loss；每层先给子预算，评估后**淘汰最差一半、预算翻倍**继续（Algorithm 1）。避免在差分组上浪费 L3–L5 的 GA 预算。
- **GA + two-level swaps（L3–L5）**：将 medium/fine assignment 视为设备拓扑图上的图划分问题；mutation 生成 offspring 后，在 **L3 跨 task group 交换 GPU**、**L5 跨 tasklet group 交换 GPU**，淘汰高 cost 个体。相对 Yuan et al. 2022 式「仅模型内 swap」的 HetRL (simple)，能跨模型/任务联合优化。
- **Cost model**：分项建模 actor generation、三类 inference、critic/actor training；用 Φ(·) 聚合无依赖任务（系数 η 控制并行度 0/1/部分）；每项再拆 computation、HBM、pipeline bubble、TP/PP/DP 通信（同步 PPO 主文，async/GRPO 变体见 Appendix B）。避免每候选 plan 真跑 tens-of-minutes 的 RL step。

### 系统组件（Fig. 2）

- **Profiler**：采集 GPU TFLOPs、显存、HBM 带宽、机内/跨机带宽与延迟。
- **Scheduler**：运行上述搜索，输出 near-optimal execution plan。
- **Execution engine**：基于 verl，扩展 fine-grained resource assignment；训练 Megatron-LM，generation/inference [[vLLM]]。
- **Load balancer**：**data-level**——rollout 时按 cost model 调 DP 组内 local batch；已知序列长度任务把长序列样本分给更强 GPU；**layer-level**——按估计调 [[Pipeline-Parallelism]] 各 stage 层数。论文称对 verl/Megatron/vLLM **非侵入**集成；更激进策略（如 Metis 式）留作 future work。

## 设计取舍

- **联合 workflow 调度 vs per-model 异构调度**：赢得全局吞吐与跨任务共置/并行优化，代价是搜索空间更大、实现与调试更复杂；用 nested SHA + cost model 换可承受搜索时间，但短任务可能不划算。

- **Cost model 驱动搜索 vs profile-guided 真跑**：避免 20k GPU-hour 评测中每次候选都真训练，但引入模型–实测偏差风险；论文用 Fig. 4 收敛曲线论证排序有效，未系统报告 estimation error 分布。

- **扩展 verl 栈 vs 从零构建**：降低工程门槛、复用 HybridFlow 编程模型，但继承 verl 在同构假设下的结构限制；异构 fine-grained placement 的边界由 Megatron/vLLM 能力决定。

- **吞吐优先 vs 收敛/成本**：明确不比较 dollar efficiency（云价波动）；不验证跨 GPU 数值精度对 RL 收敛的影响——适合**长跑 post-training 产能**场景，不适合对精度/成本极敏感的小规模实验。

- **边界条件**：在 **PPO/GRPO、Qwen 4B–14B、GSM8k、global batch 1024、64 卡 NVIDIA 三代 GPU、AWS 类跨区网络** 下最优雅；仅三种 NVIDIA GPU + OFI NCCL/EFA；StreamRL 非开源故作者自实现 async 版于 verl 上对比。

## 实验与结果

**硬件**：64 GPU = 24×A100 + 24×L40S + 16×L4（Table 1）；十区域延迟/带宽 profile 注入四类场景（Fig. 3a–b）。

**Workload**：Qwen 4B/8B/14B；PPO / GRPO，sync 与 async；GSM8k；prompt/response max len 1024；每 prompt 8 responses；训练 mixed precision Adam，推理/生成 BF16。

**Baselines**：verl（同构向 SoTA）；StreamRL-async（作者基于 verl 复现，actor generation 与其余任务分两组跨 DC）。

**端到端吞吐（Fig. 3c–e，相对 verl / StreamRL）**

| 场景 | Sync vs verl | Async vs StreamRL / verl（节选） |
|------|----------------|-------------------------------------|
| Single-Region | **1.51–2.05×** | **1.1–1.31×** / StreamRL |
| Multi-Region-Hybrid | **3.01–4.99×** | **1.11–1.27×** StreamRL；**4.07–9.17×** verl |
| Multi-Country | **1.4–3.07×** | **1.19–1.5×** / **1.71–4.0×** |
| Multi-Continent | **2.24–5.46×** | **2.25–3.72×** StreamRL；**4.38–10.76×** verl |

- 论文 aggregate：**最高 9.17×、平均 3.17×** SoTA；场景 2–4 增益更大（网络异构更重）。
- HetRL-Async 恒快于 HetRL-Sync；verl-Async 在部分异构场景反而慢于 verl-Sync（调度未优化异构）。
- PPO vs GRPO 差距不同（GRPO 无 critic 模型与对应任务）。

**调度算法（Fig. 4）**：固定/递增搜索预算下，HetRL 收敛计划优于 verl 与 HetRL (simple)（禁用 SHA、仅模型内 swap）；同预算时 HetRL (simple) 在 scenario 1 甚至劣于 verl。

**Load balancing（Fig. 5）**：同步 RL 下吞吐提升 up to **12%**（Single-Region）、**18%**（Cross-Region）；低于 Metis 报告的 19–22%，作者归因未集成更多 Metis 策略。Async 下收益不显著（generation vs training 资源切分主导）。

**GPU 组合（Fig. 6）**：Qwen-8B Single-Region，HetRL vs verl **1.57–4.33×**（按 PPO/GRPO × sync/async）；**ALL GPUs** vs **24×A100 only** 再快 **1.57–2.0×**；跨区异构相对单区有限同构 homo GPU 仍有 **1.09–1.77×**（Fig. 3 与 Fig. 6 交叉解读）。

**规模**：总评测 **~20,000 GPU-hour**。

## Critical Analysis

### 论证链条

链条：**测量/论证** geo-distributed 异构 GPU 资源可观 + RL 多模型任务异构性强 + per-model 异构调度不可扩展 → **形式化**联合 (ρ, σ) 优化并 NP-hard → **算法**五级分解 + nested SHA 剪枝 + 跨任务 GA → **系统** verl 栈执行 + load balancing → **结果** 四类网络场景一致大幅提速，且 ablation 支持 SHA/双层 swap 必要性。

最强环节是问题定义与搜索框架对 workflow 结构的显式建模，以及 Multi-Region-Hybrid async **9.17×** 等极端场景下相对 verl 的巨大差距——与「网络异构放大队列/气泡」的叙事一致。HetRL (simple) 在同预算下输给 verl 的反例也支撑「必须联合跨任务搜索」而非简单拼接。

薄弱环节：从 64 卡、三型号 NVIDIA、GSM8k、同尺寸四模型 **外推**到 production RLHF（多租户、动态扩缩、不同 reward 模型规模、长 context rollout）仍是大跳步；**未验证**选中 plan 的 cost 排序在真实 async staleness 下是否稳定。

### 假设压力测试

**Workload**：数学推理 GSM8k、固定 1024 序列、global batch 1024；无 code RL、无 tool-use 多轮、无 multimodal。Actor generation memory-bound 假设在更长 response 或更大 batch rollout 时可能改变最优 grouping（KV 主导 vs 计算主导翻转）。

**硬件**：仅 NVIDIA A100/L40S/L4 + AWS EFA/O FI NCCL；无 AMD/Intel、无消费级卡混部、无 NVLink 拓扑细粒度实验。跨 vendor 时数值格式与 collective 语义可能破坏「直接交换 rollout 数据」假设——论文明确未测。

**规模**：64 GPU 对应当前 RL 集群仍偏小；SHA/GA 搜索时间与 GPU 数、task grouping 数量关系未给闭式或实测曲线，千卡扩展性未知。Load balancer 的 layer/data 调整是否随规模出现新的 straggler 模式未讨论。

**部署**：假设搜索一次、长跑摊销；故障后重调度、弹性扩缩、spot 实例抢占等生产事件未覆盖。

### 实验可信度

**优点**：baseline 统一 vLLM + Megatron；StreamRL 公平性通过同栈复现；覆盖 sync/async × PPO/GRPO × 三模型尺寸 × 四网络场景；ablation（HetRL simple）、load balancing、GPU 组合多视角；20k GPU-hour 投入可观。

**限制**：
- **无收敛/奖励曲线**——仅 throughput，无法判断加速是否来自有效学习步还是 pipeline 填谷。
- **无搜索开销报告**——plan 生成 wall-clock、内存、是否需重搜未量化。
- StreamRL 为复现而非官方实现，绝对数值对比需谨慎。
- MinerU markdown 中公式/表格 OCR 噪声；关键倍数以正文明确区间为准。
- **无成本模型误差分析**——选出的 plan 与真跑 iteration time 的相关性未展示。
- Scenario 3 在原文出现两次标签（Multi-Country / Multi-Continent），以正文描述区分。

### 系统性缺陷

- **故障恢复与弹性**：跨区 tasklet 布局下节点失效后的重规划、checkpoint 一致性——论文未讨论。
- **尾延迟与 straggler**：优化目标为平均 iteration 时间；rollout 长尾、跨区慢链对 async pipeline 的影响未单独 metric。
- **多租户隔离**：异构资源细粒度映射是否加剧 noisy neighbor——论文未讨论。
- **可观测性**：复杂五级 plan 的 debug、cost model vs 实测漂移监控——论文未讨论。
- **精度与一致性**：Limitations 承认未研究跨异构 GPU 数据交换的 precision 对收敛影响；对 RL 生产是实质性风险。
- **运维复杂度**：~3k LOC 但依赖 profiler 准确性与搜索预算调参；论文未给默认 B 或 sensitivity。

## 局限与 Future Work

- **局限 1**（论文承认）：仅三种 NVIDIA GPU、AWS 网络栈；未支持其他代际/厂商 GPU 与其他 networking stack。
- **局限 2**：评测 unchanged mainstream RLHF 算法，**只优化吞吐**，未调查收敛是否受异构精度影响。
- **局限 3**：无 cost-efficiency 比较（云价波动）。
- **局限 4**：Load balancing 弱于 Metis 全策略集成；async 下 load balancing 收益有限。
- **局限 5**：StreamRL 非开源，对比基于自实现；搜索绝对耗时与千卡扩展未验证。

- **Future work 1**（论文暗示）：集成 Metis、Um et al. 等更先进 load balancing / layer 划分到多级搜索框架。
- **Future work 2**：支持其他 GPU 代际、厂商与网络栈；测量跨设备数值格式对 PPO/GRPO 收敛的 sensitivity。
- **Future work 3**（可验证延伸）：在真实 geo-distributed trace 上对比「HetRL plan 真跑 iteration time / cost model 预测」的 Spearman 秩相关，量化何时需在线重搜；在 critic≠actor 尺寸、长 context rollout 下重测 task grouping 最优结构。
- **Future work 4**：将吞吐优化与 **$/GPU-hour、搜索摊销、故障重调度开销** 联合建模，给出异构跨区 RL 相对「租同构高端集群」的 break-even 区域。

## 相关

- **相关概念**：[[KV-Cache]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Continuous-Batching]]、[[Disaggregation]]
- **同类系统**：verl（HybridFlow）、StreamRL、OpenRLHF、RLHFuse、[[HexiScale-MLSys26|HexiScale]]、Metis、DTFM、Helix、ThunderServe
- **同会议**：[[MLSys-2026]]
- **对比**：同构 RL 栈（verl）vs 两组跨 DC 异构（StreamRL）vs **全 workflow 联合异构调度**（HetRL）vs 单模型异构训练（HexiScale/Metis）