---
type: probe
topic: "异构小集群（约 10–20 GPU）上的 multi-model agent serving：频繁模型切换下 GPU state 驻留决策"
created: 2026-06-26
probed_papers: ["[[CrossPool-arXiv26]]", "[[Aegaeon-SOSP25]]", "[[Weaver-ATC25]]", "[[HELIOS-MLSys26]]", "[[BOUTE-MLSys26]]", "[[LMCache-arXiv25]]", "[[Jenga-SOSP25]]", "[[Pie-SOSP25]]", "[[FlashAgents-MLSys26]]", "[[MorphServe-MLSys26]]", "[[LLMStation-ATC25]]", "[[HetRL-MLSys26]]", "[[FluxMoE-arXiv26]]", "[[MOE-INFINITY-arXiv24]]", "[[KTransformers-SOSP25]]", "[[DeepSeek-V4-arXiv26]]", "[[MoE-Serving-Tax-MLSys26]]", "[[AssyLLM-ATC25]]"]
---

# 调研：异构小集群多模型智能体服务

> **目标场景**：小型企业约 10–20 张**异构** GPU，服务约 10 名研发的 multi-model agent；模型集精简但**频繁切换**；核心挑战是**在资源受限下决策哪些 state（权重 / KV / expert cache）驻留 GPU 才能满足 SLO**。[[CrossPool-arXiv26]] 面向 cold-model MaaS、权重全在 GPU、无 offloading、无异构 GPU；[[DwarfStar]] 走本地窄栈 SSD streaming + disk KV，亦非通用集群调度器。

## Landscape

### 每个相关工作的定位

| 工作 | 做了什么 | 没做什么 | 关键观察 | 隐含假设 | 可攻击点 / 脆弱点 |
|------|----------|----------|----------|----------|--------------------|
| [[CrossPool-arXiv26]] | 把 cold MoE 的 **FFN 权重池** 与 **KV-cache 池** 拆到不同 GPU 组，层间传 hidden state 而非 KV；P95 聚合 KV 需求做 pool 规划 | **权重仍在 GPU**（无 CPU/NVMe offloading）；面向 **cold、低并发** 长尾模型；原型用 **NVLink + NVSHMEM** 同构互联；不处理 agent 工作流、异构算力 | OpenRouter 约 90% 模型 cold；低 RPS 时各模型 active KV 很少同时 peak → 共享 KV pool 可省显存；MQA/MLA + DP 在低并发下单请求只见 1/GPU 的 KV 容量 | 部署模型目录大、请求极 skew；同构 GPU 组、NVLink 足够传每层 hidden state；「几乎不用的模型」仍 worth keeping online | **小团队 agent 场景**：已部署模型都「够热」，cold-model 假设不成立；**异构卡**（3090+A100+L40 混部）下 hidden-state 传输与算力不匹配未建模；资源真正紧缺时需 **offload 到 Host/SSD**，CrossPool 未覆盖 |
| [[DwarfStar]] | DeepSeek V4 特化本地引擎：**SSD routed-expert streaming** + **disk KV checkpoint** + 正确性回归 | 非通用 multi-model server；无集群调度、无异构 GPU placement、无多租户 SLO | 个人/高端单机：expert 与 KV **争用同一内存层次**；disk KV 让 session switch / 重启可复用 prefill | batch=1、单用户 agent/coding；模型 layout 已知且可特化 | 10 卡集群 + 多模型 + 多用户时 **policy 无法直接移植**；expert streaming 与 disk KV 仍是两套 policy，**无统一资源仲裁**（与 moe-kv-cache-offload probe 一致） |
| [[Aegaeon-SOSP25]] | 模型市场 **token-level** 抢占式 auto-scaling + KV swap 优化，每 GPU **7** 模型（少于 3 个） | 阿里生产 **数十–数百模型** 长尾；深度绑定自研 engine；**同构** 大集群；cold catalog 语义 | 100 模型中平均 **46.55** active（长请求 HOL）；swap overhead 朴素实现 tens of seconds → 需 **-97%** 组件重用 | per-token SLO 可定义；skew 生产 trace 稳定 | **约 5–8 个精选模型** 时 active set 接近全集，token-level 抢占收益缩小；**异构卡** swap 带宽/延迟差异大；agent 长 session KV 使 swap 更贵 |
| [[Weaver-ATC25]] | hot 模型把部分 **attention+KV** offload 到正在跑 cold 模型的 GPU，扩 hot batch | 需 **hot/cold 角色固定**；cold QPS≈1；**同构 NVLink** 单机；无 cluster scheduler | top 5% 模型 74.8% tokens；cold GPU 1 QPS 时显存利用率 **43%** | cold 模型长期在线且低负载；IPC/CUDA shared memory 可用 | agent 多模型 **轮流变热** 时 hot/cold 角色动态翻转；**PCIe 异构**（无 NVLink）通信开销可能吞掉收益；只 offload attention，不解决 **权重驻留** |
| [[HELIOS-MLSys26]] | **多 EE-LLM 互补 early-exit** + greedy partial load，释显存扩 batch | 需预训练 early-exit 变体；默认 **3 候选串行 profiling**；4×A100 **同构** | 单模型 EE-LLM **零显存收益**（worst-case 全层+KV）；多模型 exit 分布互补可达 **92%** early-exit | 在线 perplexity + CBC 可 guard 精度；RI=150 内 workload 稳定 | 标准 frontier 模型（无 EE 头）不适用；**切换/补层** P99 spike 未系统测；与 **异构 GPU**（小模型放弱卡）未联合 |
| [[BOUTE-MLSys26]] | **MOBO 联合优化** routing 阈值 τ + 每模型 GPU 类型/数量/TP | **静态 co-design**（离线 BO）；threshold router；2 模型为主实验 | routing 与 deployment **circular dependency**，分开优化 P95 可差 **10%+** | 离线 profile 代表在线；价目表固定 | **约 10 人小团队** 更关心 **session 内模型切换延迟** 而非 GSM8K routing；agent 工作流模型调用图非简单 threshold；**超过 3 个模型** action space 爆炸 |
| [[LMCache-arXiv25]] | GPU/CPU/SSD/remote **多 tier KV** 中间件 + controller API（lookup/pin/move） | **不管理模型权重 / expert**；placement 偏 KV-local | 企业 stored KV **30T+ bytes** 主要在 non-GPU；小 page I/O 打不满带宽 → 大 chunk | prefix/chunk 复用足够高；connector 可跟上 engine layout 变化 | **短 agent turn、低 prefix 复用** 时 load 不如 re-prefill（32Gbps 下需 **大于 256K** context 才划算）；与 **权重驻留决策** 正交但未联合 |
| [[Jenga-SOSP25]] | 异构 **attention 机制**（SWA/Mamba/VLM/spec decode）下 LCM allocator + per-layer prefix cache | 单模型 serving；**同构 GPU 节点**；不碰 multi-model 切换 | 均匀 per-layer paging 可致 **2.16×** 吞吐损失；Llama4 **10M** context on 8×B200 | layer property 静态可知 | agent 多模型时 **各模型 KV layout 不同**，pool 规划比 Jenga 更复杂；与 [[CrossPool-arXiv26]] 的 **跨模型 KV pool** 可组合但未验证 |
| [[Pie-SOSP25]] | Wasm **inferlet** 编排 embedding/forward/sampling/KV op，支撑 agent/tree-of-thought | 不解决 **集群级显存预算**；标准 completion **3–12%** overhead | monolithic prefill-decode 环无法表达 **应用级 KV 分配/驱逐** 与 tool loop | handler 粒度够表达主流 agent 模式 | 10 人共享集群仍需 **底层 pool 调度**；inferlet 碎片化可能损害 batching |
| [[FlashAgents-MLSys26]] | 多 agent **streaming prefill overlap** + intra-turn radix cache（[[SGLang]]） | 假设 agent **co-located**；不碰权重/KV **跨 tier**；异构部署仅作 motivation | 顺序依赖导致 inter-agent idle；8B→32B 异构链放大 overlap 窗口 | 因果 attention 允许 incremental prefill | **跨机 agent**、**模型冷启动** 未覆盖；与「哪些 state 留 GPU」正交 |
| [[MorphServe-MLSys26]] | 压力下 **runtime 层量化 swap** + **KVResizer** 扩 KV，SLO 违约 **-92%** | **单模型**；同构 GPU；不处理 multi-model 切换 | 突发负载下静态 AWQ 永远掉点 | offline layer sensitivity 可迁移 | 多模型时 **各模型 sensitivity 不同**；morph 频繁触发在 **弱 GPU** 上更慢 |
| [[LLMStation-ATC25]] | PEFT + serving **iteration-level** 共置（共享 base model） | **非 multi-model pool**；需 serving SLO slack | decoding memory-bound vs PEFT compute-bound 互补 | 共享 base + LoRA adapter | agent 场景多为 **多 base model**，非单 base 多 adapter |
| [[HetRL-MLSys26]] | 异构 GPU 上 **四模型六任务** RL workflow 联合调度 | **训练**非 serving；20k GPU-hour 规模 | 单模型异构调度套到 multi-model workflow **不可扩展**（搜索慢 1000–10000×） | 静态 cost model + 离线 planner | serving 的 **KV 有状态、权重切换** 与训练 iteration 不同；但证明 **multi-model × 异构** 需联合优化 |
| [[FluxMoE-arXiv26]] | MoE expert **PagedTensor** 分页，腾 HBM 给 KV | cloud serving；未与 multi-model 混部 | expert 与 KV **争用 HBM** | expert 窗口可滑动覆盖 | 多模型同时部分 resident 时 **working set 膨胀** |
| [[MOE-INFINITY-arXiv24]] | personal-machine **expert cache** + SSD offload | 明确排除 cloud continuous batching | batch=1 request-level expert reuse | 本地 NVMe 带宽够 | 10 用户 concurrent batching 时 cache 策略需重写 |
| [[KTransformers-SOSP25]] | CPU/GPU **heterogeneous MoE**：GPU attention+hot expert，CPU 跑多数 routed expert | 非通用 server；窄模型 | 强 CPU/AMX 下 expert matmul 可接受 | attention/KV 留 GPU 最优 | 小集群若 **CPU 弱或 NUMA 差**，切分点变化；与 **多模型** 未组合 |
| [[DeepSeek-V4-arXiv26]] | CSA/HCA + FP4 MoE + **异构 KV**（压缩块/SWA/on-disk prefix） | 模型侧非 runtime 调度 | 1M context 下单 token FLOPs **27%**、KV **10%** vs V3.2 | 架构压缩降低系统 offload 压力 | 通用 [[vLLM]]/[[SGLang]] 接入成本高；**多模型混部** 时各模型 KV layout 不一 |
| [[MoE-Serving-Tax-MLSys26]] | 量化 MoE vs Dense **2–3×** serving tax 及 prefill/decode 形态差异 | 表征论文，非调度系统 | decode tax 常由 **weight amplification** 主导 | 公平 DenseFA 基线 | 小集群上 **多 MoE 权重驻留** 比 KV 更快触顶 |
| [[AssyLLM-ATC25]] | 边端 **block pool + LRU swap** 组装异构预训练块 | 联邦 QA，非 online serving | block 池 FP16 **42GB**；swap 流水降 I/O **68%** | CKA/COR 选 block | 生成式 agent 上 block 混搭合法性未验证；但 **异构块 swap** 与 multi-model 切换同设计空间 |

**一句话总结**：现有工作分别在 **cold multi-LLM pooling**（[[CrossPool-arXiv26]]/[[Aegaeon-SOSP25]]/[[Weaver-ATC25]]）、**KV 多 tier**（[[LMCache-arXiv25]]/[[DwarfStar]]）、**单模型弹性**（[[MorphServe-MLSys26]]/[[Jenga-SOSP25]]）、**agent 编排**（[[Pie-SOSP25]]/[[FlashAgents-MLSys26]]）、**异构静态 co-design**（[[BOUTE-MLSys26]]/[[HetRL-MLSys26]]）上成熟，但几乎无人同时处理 **「资源紧缺 + 异构 GPU + 少量热模型频繁切换 + agent 有状态 session」** 下的 **权重/KV/expert 统一驻留预算**。

## Tensions

### 张力 1：冷模型池化与热切换小目录

[[CrossPool-arXiv26]]、[[Aegaeon-SOSP25]]、[[Weaver-ATC25]] 的动机都建立在 **模型目录大、流量极 skew、cold 模型值得常驻** 上（OpenRouter 约 90% cold、Aegaeon 100 模型中 46+ active）。小团队 agent 栈相反：**只 deploy 5–8 个常用模型，切换频繁，不存在「几乎永不使用」的模型**。同一套「共享 KV pool / attention offload 到 cold GPU」在 **全员 warm** 时退化为 **全员争用有限 HBM**，收益从 pooling 变成 **优先级与抢占** 问题。

涉及：[[CrossPool-arXiv26]]、[[Aegaeon-SOSP25]]、[[Weaver-ATC25]]。

### 张力 2：仅 GPU 分解与真正的内存层次结构卸载

[[CrossPool-arXiv26]] 的 disaggregation 是 **GPU 内两组 pool**（权重池 vs KV 池），权重不离开 HBM。[[DwarfStar]]、[[MOE-INFINITY-arXiv24]]、[[LMCache-arXiv25]] 则把 **SSD/CPU** 纳入可用层级。资源紧缺时这两条路线冲突：**GPU-only** 简化通信但 **可部署模型数硬上限**；**offload** 扩容量但 **switch latency** 与 **双 miss 带宽竞争**（moe-kv-cache-offload probe Tension 3）。

涉及：[[DwarfStar]]、[[FluxMoE-arXiv26]]、[[LMCache-arXiv25]]、[[KTransformers-SOSP25]]。

### Tension 3: Heterogeneous GPU — 放哪张卡 vs 留多少 state

[[BOUTE-MLSys26]] 优化「小模型上弱卡、大模型上强卡」的 **静态 placement**；[[Zorse-MLSys26]]（训练）优化异构 **算力/显存/带宽** 三角。Serving 侧缺少等价物：**同一张 3090 放 7B KV 还是放 70B 的部分权重？** 异构下 **PCIe vs NVLink** 使 [[Weaver-ATC25]]/[[CrossPool-arXiv26]] 的 hidden-state 传输假设失效。

涉及：[[BOUTE-MLSys26]]、[[Weaver-ATC25]]、[[CrossPool-arXiv26]]、[[HetRL-MLSys26]]。

### 张力 4：代理会话状态与模型级池

[[Pie-SOSP25]]、[[FlashAgents-MLSys26]] 优化 **请求内/跨 agent** 的 KV 复用与 overlap，默认 **底层已有足够 GPU**。LMCache 优化 **跨请求 prefix**。Agent **单用户长 session**（tool loop、多模型 handoff）产生 **per-session KV 与 per-model weights 同时活跃**，与「cold 模型 KV 很少 peak」假设相反——**session 数 × 模型数** 驱动内存，而非 catalog 大小。

涉及：[[Pie-SOSP25]]、[[FlashAgents-MLSys26]]、[[LMCache-arXiv25]]、[[HELIOS-MLSys26]]。

### Tension 5: MoE weights vs KV 争用随「切换」形态变化

[[MoE-Serving-Tax-MLSys26]]：decode 阶段 **weight amplification** 主导。频繁 **模型 A→B 切换** 时，瓶颈从单模型 KV 变为 **多模型权重 working set + 各自 KV**；[[FluxMoE-arXiv26]]/[[MOE-INFINITY-arXiv24]] 的 expert cache 按 **单模型 locality** 设计，切换后 **cache 冷启动**。

涉及：[[FluxMoE-arXiv26]]、[[MOE-INFINITY-arXiv24]]、[[MoE-Serving-Tax-MLSys26]]、[[DwarfStar]]。

## 脆弱的假设

1. **「Cold 模型可共享 KV pool」在小 catalog 仍成立**（[[CrossPool-arXiv26]]、[[Aegaeon-SOSP25]]、[[Weaver-ATC25]]）  
   - 不稳原因：5–8 个模型对 10 人 **同时活跃** 时，aggregate KV 接近 sum of peaks，非 sublinear pooling。  
   - 验证：录 1–2 周 **agent trace**（模型 ID、session ID、context 增长），画 **同时活跃模型数 CDF** 与 **aggregate KV bytes P95**；对比 independent vs pooled admission。

2. **Hidden-state 跨 GPU pool 通信可被 pipeline 隐藏**（[[CrossPool-arXiv26]]）  
   - 不稳原因：异构集群 **弱卡算力慢、链路仅 PCIe**，层间 transfer 占 decode 比例上升。  
   - 验证：在 **NVLink 同构 vs PCIe 异构** 上测 2–3 模型切换下的 **per-layer exposed latency**；扫 batch=1 agent decode。

3. **GPU 驻留权重足够，无需 CPU/NVMe tier**（[[CrossPool-arXiv26]]、kvcached 类 baseline）  
   - 不稳原因：10–20 卡混部 **总 HBM 可能不足单模型 TP 需求**（如 70B+MoE）。  
   - 验证：列出 **实际 deploy 列表 + 量化格式**，算 **同时 resident 权重下界**；测 **首次 switch TTFT**（冷权重 load）vs **保持 warm 的 idle 显存成本**。

4. **Routing/placement 离线 co-design 可长期有效**（[[BOUTE-MLSys26]]）  
   - 不稳原因：研发 **日内模型偏好漂移**（coding 用 coder、review 用 reasoner）。  
   - 验证：按 **小时级** 滑动窗口统计模型调用矩阵；测静态 plan 的 **P95 switch latency** 退化速度。

5. **Expert cache locality 在 multi-model agent 下可迁移**（[[FluxMoE-arXiv26]]、[[MOE-INFINITY-arXiv24]]、[[DwarfStar]]）  
   - 不稳原因：切换模型后 **expert working set 完全不同**；ds4 的 hotlist 是 **单模型** 的。  
   - 验证：同一 trace 上对比 **单模型 vs 多模型交错** 的 expert cache hit rate 与 TPOT。

6. **Prefix/KV offload 总是值得**（[[LMCache-arXiv25]]）  
   - 不稳原因：agent **短 turn、高 churn** 时 hit ratio 低；load 开销超过 re-prefill。  
   - 验证：按 session 统计 **reuse distance**；复现 LMCache sensitivity（context length vs load-or-prefill crossover）。

## 行业活动

| 系统 / 项目 | 与场景关系 | 公开信息缺口 |
|-------------|-----------|--------------|
| [[DwarfStar]] | 本地 agent：**disk KV session** + SSD expert streaming；正确性优先 | 无多模型调度、无集群异构 placement |
| [[CrossPool-arXiv26]] | 2026-06 arXiv；cold MoE multi-LLM；vs kvcached/Chimera | 代码未开源；异构/offload 未讨论 |
| [[LMCache-arXiv25]] + NVIDIA Dynamo KVBM | 生产 KV tier；[[vLLM]]/[[SGLang]] connector 生态 | 不管理权重；小集群 **谁 pin 哪段 KV** 需自建 policy |
| [[vLLM]] / [[SGLang]] | 默认 **per-engine 单模型**；multi-model 靠多实例或 MuxServe 类 | 无 **异构集群全局 state 预算器** |
| [[Pie-SOSP25]] | Agent inferlet 可表达 KV 显式控制 | 集群显存调度仍外置 |
| MuxServe / ServerlessLLM / kvcached（Chimera） | [[CrossPool-arXiv26]] 对标的多 LLM GPU 复用 | 权重+KV 单体 pool；cold skew 假设 |
| 云 MaaS（[[DeepServe-ATC25]]、[[Aegaeon-SOSP25]]） | 大规模同构 + 长尾目录 | 小团队 **自建集群** 形态差异大 |

## 候选空白

### CB1: 异构小集群上的 unified **{weights, KV, expert} residency planner**

现有 [[CrossPool-arXiv26]]/[[LMCache-arXiv25]]/[[FluxMoE-arXiv26]] 各管一类对象，且多假设 **同构 GPU + 充足 HBM 或 cold skew**。约 10 张异构卡、5–8 个 **都够热** 的 agent 模型、10 个并发 session，需要一个 **在线 planner**：输入 session SLO、模型大小、卡型算力/带宽/显存，输出 **每张卡驻留哪些模型的哪部分 state**。[[BOUTE-MLSys26]] 只做离线 routing×placement，且不包含 KV/expert tier。

### CB2: **Model switch latency** 作为一等 metric 的 agent serving 研究

论文优化吞吐、TTFT、TPOT、成本，但 agent **handoff**（planner 7B → coder 32B → summarizer 7B）关心 **switch tail latency**（权重 cold、KV 迁移、expert cache 冷）。[[HELIOS-MLSys26]] 的换模 **6 次/1087 请求** 规模远小于交互式 agent。缺少 **「切换耗时 vs 保持 warm 的显存税」** Pareto 曲线。

### CB3: 异构互联下的 **partial disaggregation**（非 NVLink 假设）

[[CrossPool-arXiv26]]/[[Weaver-ATC25]] 依赖 **NVLink/IPC** 传 hidden state 或 QKV。真实小集群常见 **多代 PCIe GPU**。空白：**何种 operator 切分**（attention local、FFN remote vs 反向）在 PCIe 上仍净收益？[[Weaver-ATC25]] 在 L40S+PCIe 有数据，但未与 **多模型切换 + 权重驻留** 联合。

### CB4: **Warm catalog admission control** — 不是 cold model 下线，而是 **state tier 降级**

小团队不 deploy 冷模型，但可在 **内存压力** 下对热模型做 **tier 降级**：权重 INT4、KV CPU pin、expert SSD-only（[[DwarfStar]] 路线）、保留 **routing metadata** 以便快速 promote。[[MorphServe-MLSys26]] 只做单模型层 swap；缺少 **multi-model 间抢占谁降级** 的公平策略。

### CB5: Agent trace 驱动的 **session-aware state retention**

[[FlashAgents-MLSys26]]/[[Pie-SOSP25]] 优化 **单 workflow 内** overlap；[[LMCache-arXiv25]] 优化 **跨 query prefix**。空白：**同一研发 session** 跨模型、跨 tool call 的 **KV 是否保留、保留在哪张弱卡**，与 **另一同事的 session** 如何抢显存——10 人规模已有 **multi-tenant**，但负载远小于云 MaaS，现有 fairness 研究不匹配。

## 关键未知数

| Unknown | 为什么重要 | 测量建议 |
|---------|-----------|----------|
| **实际 deploy 模型集与切换矩阵** | 决定 pooling 是否有效、planner 输入维度 | 1–2 周日志：`(user, session, model, tokens_in/out, timestamp)`；马尔可夫切换矩阵 + 同时活跃模型分布 |
| **Switch vs warm 的 Pareto 前沿** | 核心设计权衡：省显存 vs 切模型快 | 对每个模型测 **cold load TTFT**（权重从 CPU/SSD）、**warm idle 显存**；扫「保留 K 个模型 warm」的 SLO 违约率 |
| **异构卡上的瓶颈算子** | 决定 placement（大模型上 A100、小模型上 3090？） | 每卡 profile：**prefill/decode TFLOPs、HBM BW、PCIe BW**；agent trace replay 测 **P95 TPOT per (model, GPU type)** |
| **KV vs weights 谁先触顶** | 决定优先 offload 哪类 state | 固定并发 session 数，渐增 context / 模型数，记录 **OOM 前 first killer**（KV OOM vs weight load fail） |
| **Agent prefix 复用率** | 决定 LMCache/disk KV 是否值得 | 统计 **跨 turn、跨模型** 共享 token 比例；对比「只缓存 system prompt」vs「全 session KV pin」收益 |
| **MoE expert cache 跨模型干扰** | MoE agent 栈（DeepSeek、Qwen-MoE）常见 | 多模型交错 trace 下测 **expert hit rate**；对比 [[DwarfStar]] 式 SSD streaming vs GPU cache 的 **switch 后首 token 延迟** |
| **10 人 SLO 定义** | 研发场景常为 **interactive tail** 非 cloud QPS | 访谈 + 测量可接受 **P95 TTFT/TPOT/switch latency**；区分 **blocking tool call** vs **background job** |

## 场景定位对照

| 维度 | cold-catalog 路线（[[CrossPool-arXiv26]] 等） | 目标场景（小集群 agent） |
|------|-----------------------------------------------|--------------------------|
| 模型集 | 目录大、长尾 cold | 5–8 个精选、均够热 |
| 流量 | 极 skew、低 RPS/model | 10 人、频繁 model switch |
| 内存策略 | GPU 内权重/KV 双 pool | 常需 Host/SSD tier |
| 硬件 | 同构 NVLink 集群 | 异构、PCIe 混部 |
| 核心 metric | 长 context 容量、TBT | **switch latency** vs warm 显存税 |
