---
type: proposal
name: LiveSessionMigration
title: 把 disaggregated LLM serving 集群当作分布式 OS——live decode session 迁移与 rank-level failover
status: draft
category: mlsys
created: 2026-04-27
last_updated: 2026-04-27
tags: [llm-serving, fault-tolerance, live-migration, kv-cache, rdma, disaggregation, p2p]
related_papers: ["[[TransferEngine-MLSys26]]", "[[BlitzScale-OSDI25]]", "[[NanoFlow-OSDI25]]", "[[FuseLink-OSDI25]]", "[[SMon-OSDI25]]", "[[MorphServe-MLSys26]]", "[[NVIDIA-Disagg-Study-MLSys26]]", "[[CRAFT-MLSys26]]"]
related_concepts: ["[[Disaggregation]]", "[[KV-Cache]]", "[[RDMA]]", "[[Continuous-Batching]]", "[[PagedAttention]]", "[[Tensor-Parallelism]]", "[[MoE]]"]
related_systems: ["[[vLLM]]", "[[SGLang]]"]
novelty: medium
feasibility: high
effort: medium-long
verdict: pending
---

# 把 disaggregated LLM serving 集群当作分布式 OS——live decode session 迁移与 rank-level failover

> **TL;DR**:把 in-flight decode 请求抽象成可迁移的"session"(prefix KV shards 指针 + decode RNG + sampler 配置 + 已发 tokens + KV layout),用 [[TransferEngine-MLSys26|TransferEngine]] 的 P2P 原语做 **pre-copy + stop-and-copy** 风格的 KV-preserving live migration,在 **pre-warmed standby**(权重已加载、未上线)的支撑下,把 rank failure / planned drain / load rebalance / MoE expert hotness shift 收敛到同一套迁移 API。**核心差异化**:与同空间近期工作([AnchorTP](https://arxiv.org/abs/2511.11617) failure-only / [BanaServe](https://arxiv.org/abs/2510.13223) load + 中心 KV store / [Tarragon](https://arxiv.org/abs/2601.01310) failure-only MoE)相比,本提案占据三角 distinct 设计点——(a) decentralized prefix index 替代 centralized KV store;(b) session-grain 抽象捕获 in-flight decode 的 RNG / sampler / decode-iter delta(layer-grain 与 attention-grain 的 BanaServe 天然不包含);(c) 同一 migration protocol 在 failure / drain / load / hotness 4 类 trigger 上的代码复用,降低 reconfiguration 路径种类数。**目标**:planned-drain 场景比 cancel-and-reroute baseline 的请求挽留率 ≥ 80%、rank-level 故障下挽留率 ≥ 90%、有 hot-standby 时服务空白 < 500 ms,在 1-3 × 8 H100 上覆盖 dense(Llama-3-70B / Qwen3-32B) 与 MoE(DeepSeek-V2-Lite-16B) 两类部署。

## Idea

**问题动机**。LLM serving 已经从单实例单卡演化成 PD-disaggregated、TP/PP/EP 多维并行的复杂集群,但**故障/迁移语义还停留在 NCCL static-membership 时代**:任何一个 GPU 挂掉、任何一次扩缩容,都意味着整个 collective group 重新初始化、in-flight 请求全部 cancel、KV cache 全部重算。

可靠性侧的间接证据来自训练:[[SMon-OSDI25]] 在字节跳动 3079 个 LLM 训练 job 上的 what-if 分析显示 42.5% job 被 stragglers 拖慢 ≥10%——**虽然主因是 PP 不均/序列长度 skew/GC 而非硬件故障,但它说明大规模 LLM 集群的可靠性问题广泛存在**;推理侧目前没有公开的同等量化研究,但 BurstGPT / Azure trace 显示请求 2 秒内能爆 5×([[BlitzScale-OSDI25]] 数据),意味着**频繁的扩缩容、re-routing、热度重平衡**才是推理侧 reconfiguration 的高频触发源,故障只是诸多触发源之一。

[[BlitzScale-OSDI25]] 通过 ZigZag layer-level pipeline split 让新实例加载若干层后即可分担 in-flight 请求的深层执行,但**单 session 的 KV / RNG / decode-iter state 仍 anchor 在原实例**——不做跨 instance 的 session-state migration,也不解决 rank failure 与 graceful drain 场景。最近一波 LLM-FT 工作([AnchorTP](https://arxiv.org/abs/2511.11617) / [BanaServe](https://arxiv.org/abs/2510.13223) / [Tarragon](https://arxiv.org/abs/2601.01310) / [ReviveMoE](https://arxiv.org/abs/2602.21140))各自处理一类 trigger,但**没有人把 failure / drain / load / hotness shift 看成同一个 reconfiguration primitive 的不同 trigger**——尤其是,**session 作为捕获 in-flight decode RNG / sampler / decode-iter delta 的 first-class 抽象,没有在已发表方案里出现**:BanaServe 在 layer + attention 粒度做 module + KV cache migration on load trigger(覆盖了 non-failure KV-preserving migration 的部分空间),但其抽象不显式建模单个 in-flight decode 的 sampler / RNG continuation。

**核心方法**。引入 **session** 作为 disaggregated LLM serving 的一等抽象,类比 OS 中的 process:

- **Session = (prefix KV shards 指针,decode RNG 状态 + sampler 配置,已生成 tokens 序列,attention layout / sharding 元数据)**——一个可序列化、可迁移、可校验的小对象;关键是它把 sampled decoding 下的 *continuation 等价性* 显式纳入抽象内
- **Migration primitive**:把一个 session 从 source rank-tuple 迁到 target rank-tuple 的原子操作,内部分两阶段
  - **Pre-copy phase**:source 继续 decode + 后台 P2P 流式 push KV shard 到 target,target 进入 "warm" 状态;为避免与 PD KV transfer 抢带宽,pre-copy 跑在 **bandwidth reservation** 下(见 R5)
  - **Stop-and-copy phase**:source 停掉 1-2 个 decode iter (dense 70B + TP8 在 H100 上 ≈ 30-100 ms),把当前 KV delta + RNG + attention state 推过去,target 接管下一 token
- **统一 trigger**:rank failure(IMMCOUNTER 超时检测)、planned drain(scheduler 主动调用)、load rebalance(controller 决策)、MoE expert hotness shift(expert tracker 决策),都通过同一套 migration API 触发——**这是 unification 的真正价值**,不是抽象上的"统一名词",而是同一段 protocol 代码在 4 类场景下复用,降低 reconfiguration 路径种类数(可量化指标:LoC reuse 率、protocol round-trip 复用率)
- **Pre-warmed standby**:为达 < 500 ms RTO,集群保留少量 standby rank,**权重已加载、未上线服务**,failure 时直接 KV reattach + 接续(避免 weight reload 吃掉 RTO budget——70B / TP8 即每 rank 8.75 GB,400 Gbps 链路下也要 ~175 ms 才能拉完)。Standby 比例可调,典型 1/8(每 8 个 active rank 对 1 个 standby),约 12.5% capacity overhead——比 over-provisioning 廉价得多
- **底层通信**:基于 [[TransferEngine-MLSys26|TransferEngine]] 的 paged WRITE + IMMCOUNTER,跨 ConnectX-7 与 EFA vendor-neutral;P2P 不依赖 collective group,迁移期间不影响其他 in-flight 请求
- **Decentralized prefix cache**:每个 instance 维护本地 prefix index + Bloom filter 周期 broadcast,跨 instance 用 P2P pull 取——**明确取舍**:prefix cache 本身**不做 FT**(持有者挂掉则该 prefix 失效,重新 prefill;FT 的主体是 session 而非 prefix)。与 [Mooncake](https://arxiv.org/abs/2407.00079) / [LMCache](https://arxiv.org/abs/2510.09665) / [BanaServe](https://arxiv.org/abs/2510.13223) 的核心差异是**无 centralized metadata service**(三者均依赖 centralized Conductor / orchestrator / KV Cache Store),而非 P2P data path 本身

**预期收益**(完整 ablation 见 M4):
- 单 GPU 故障 + hot-standby 场景:服务空白 < 500 ms,挽留 ≥ 90% in-flight 请求,TPOT P95 退化 < 5%
- Planned drain 场景:挽留 ≥ 80% in-flight 请求(对比 cancel + 重 prefill baseline)
- Load rebalance 场景:跨 instance 迁移 decode session 解决 hot instance 问题(与 [BanaServe](https://arxiv.org/abs/2510.13223) layer + attention 粒度做对比;[[MorphServe-MLSys26]] 用 quantization 换内存的另一条路径)
- 同一套机制覆盖 dense TP / MoE EP 两种部署

## 相关工作(仓库内)

### Disaggregated serving 与 KV transfer 底座

- [[TransferEngine-MLSys26]] — 直接底座:P2P RDMA + IMMCOUNTER 完成通知 + UVM watcher 让 GPU kernel 驱动传输,vendor-neutral。**已 MIT 开源在 [pplx-garden](https://github.com/perplexityai/pplx-garden)** (Nov 2025),本提案在其上构造 session 抽象与迁移协议
- [[NVIDIA-Disagg-Study-MLSys26]] — 数十万设计点扫描得到 PD disaggregation 在 prefill-heavy + >10B 模型最有收益,本提案补它没覆盖的"运行时迁移"维度
- [[FuseLink-OSDI25]] — 多 NIC 聚合 + NVLink relay 把两 GPU 间带宽推到 212 GB/s,本提案的 migration 带宽预算可借此放宽

### Autoscaling / 运行时形变

- [[BlitzScale-OSDI25]] — 最强直接对比:O(1) host caching + 层粒度 live autoscaling + ZigZag。**关键差异**:BlitzScale 的 ZigZag 调度通过 layer-level pipeline split 让新旧 instance 共享 in-flight 请求的层执行,但**单 session 的 KV / RNG / decode-iter state 仍 anchor 在原实例,不做跨 instance session migration**;也不处理 rank failure 与 graceful drain。本提案补的是 BlitzScale 留下的"跨 instance session-state migration + 多 trigger 统一"那一半
- [[MorphServe-MLSys26]] — runtime 按负载切换层精度 + 弹性 KV;另一种 elastic 思路(沿精度维度形变)。本提案沿 placement 维度形变,二者可叠加

### Production 可靠性背景

- [[SMon-OSDI25]] — 训练侧 straggler 量化研究(42.5% job 受影响);为大规模 LLM 集群的可靠性需求提供旁证,但**不直接外推到推理侧 failure 频率**
- [[CRAFT-MLSys26]] — MoE expert replication 的 **静态** 分配(MCKP DP),与本提案的 runtime hotness migration 是 placement layer 上的不同决策维度,可叠加(静态 base placement + 动态 session migration)

### 不直接相关但常被混淆

- [[NanoFlow-OSDI25]] — intra-device parallelism + nano-batching(把 batch 切成 nano-batch,让 compute/memory/network 异构 op 在同卡 overlap),覆盖 prefill+decode 两阶段。与本提案的 cross-instance decode-session migration 正交,**不在本提案 baseline 中**
- [[LayeredPrefill-MLSys26]] / [[LAPS-MLSys26]] — prefill-side scheduling(layer-group 调度 / 长短 prefill 分池),正交,不在 baseline

## 相关工作(外部)

最近 6 个月这一带是热点,必须诚实标注重叠:

- Xu et al. (Nov 2025) [AnchorTP: Resilient LLM Inference with State-Preserving Elastic Tensor Parallelism](https://arxiv.org/abs/2511.11617) — **最近的强竞品**。Daemon 进程把 model + KV 解耦保留在 GPU 显存,Continuous Minimal Migration 算法做 P2P reload。**只覆盖 single-GPU failure**,abstract 未提 non-failure 触发。本提案延续其 "decoupled state" 思路,但把 trigger 与场景显著扩张到 drain / load / hotness 三类 non-failure 场景
- He et al. (Oct 2025) [BanaServe: Unified KV Cache and Dynamic Module Migration](https://arxiv.org/abs/2510.13223) — **同空间最直接竞品**。明确做 **Layer-level weight migration + Attention-level KV Cache migration + Global KV Cache Store with layer-wise overlapped transmission**,触发器是 load imbalance(non-failure),覆盖了"non-failure trigger 上 KV-preserving migration"这一空间的相当部分。本提案与 BanaServe 的真实差异是三联组合:**(a) decentralized prefix index 替代 centralized KV Cache Store; (b) session-grain 抽象显式建模 in-flight decode 的 RNG + sampler + decode-iter delta(layer + attention 粒度天然不包含 sampler continuation 等价性); (c) 同一 migration protocol 复用到 failure / drain / load / hotness 4 类 trigger,而非 BanaServe 仅 load-balancing 单一 trigger**
- Zhang et al. (Jan 2026) [Making MoE-based LLM Inference Resilient with Tarragon](https://arxiv.org/abs/2601.01310) (Songyu Zhang, Aaron Tam, Myungjin Lee, Shixiong Qi, K. K. Ramakrishnan) — MoE 专用,reconfigurable datapath + self-healing,attention 与 expert 作为独立 failure domain。**worker 粒度 + 仅 failure 触发**。本提案 dense + MoE 统一,session 抽象不依赖 MoE 假设
- Li et al. (Feb 2026) [ReviveMoE: Fast Recovery for Hardware Failures in Large-Scale MoE LLM Inference](https://arxiv.org/abs/2602.21140) — failure-only。abstract 未明确披露是 KV-preserving 还是 token-only re-prefill;若是后者(ServerlessLLM 范式),与本提案是 opposite design point;具体范式归属待 paper 全文核对
- Tongxuan Liu et al. (Oct 2025 v1 / Mar 2026 v2) [xLLM Technical Report](https://arxiv.org/abs/2510.14686) — 多节点 FT 架构面向高可用,52 作者的工业 report;有 decoupled service-engine architecture 与 global KV Cache management 但未在 abstract 提 in-flight session migration 的具体协议
- Liu et al. (Oct 2025) [LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference](https://arxiv.org/abs/2510.09665) (first author Yuhan Liu;Yihua Cheng 同组次位) — KV cache 跨 GPU/CPU/disk 分层,centralized orchestration。本提案的 decentralized prefix index 与之是设计点对比
- Fu et al. (Jan 2024 → 2024 OSDI) [ServerlessLLM](https://arxiv.org/abs/2401.14351) — live migration 但**只移 token 不移 KV**(paper §5.2:"migrate tokens (typically 10-100s KB) instead of the large KV-Cache (typically 1-10s GB)"),destination 重新 prefill 重算 KV。是另一极端设计点(优化 net,牺牲 compute);ReviveMoE 若是同范式则属此一脉
- Wu et al. (Apr 2024) [LoongServe](https://arxiv.org/abs/2404.09526) — 长上下文场景的 elastic sequence parallelism,有 KV cache migration 但焦点在 sequence 沿 CP 维度切分而非"session"作为 first-class 抽象
- Qin et al. (FAST 2025) [Mooncake: A KVCache-Centric Disaggregated Architecture](https://arxiv.org/abs/2407.00079) — 中心 Conductor 调度器 + Mooncake Transfer Engine(本身是 P2P RDMA)。本提案的真正差异化是**无 centralized metadata service**,而不是 P2P data path

## Novelty 评估

- **新颖点**(三角差异化,任一不足以单独构成 OSDI-bar contribution,联合才有意义):
  - **Decentralized prefix index + session-level FT 双层设计**:与 [BanaServe](https://arxiv.org/abs/2510.13223) / [Mooncake](https://arxiv.org/abs/2407.00079) / [LMCache](https://arxiv.org/abs/2510.09665) 的 centralized metadata service 是设计点对比。Decentralized 端 prefix-cache 不保 FT(明确取舍),但 session 由 hot-standby 保 FT,两层分担保证 production 端可观察影响仅是 prefix miss 时的 TTFT 抖动一次
  - **Session 作为 first-class 抽象**:显式建模 RNG state + sampler 配置 + decode-iter delta + token history。BanaServe 的 layer + attention 粒度 module + KV migration 不显式包含 sampler continuation 等价性,session-grain 是更精确的迁移对象。Sampled decoding 下的 distributional equivalence(KL + top-k overlap)只能在 session-grain 上做严格 verify
  - **同一 protocol 覆盖 4 类 trigger 的代码复用**:failure / drain / load / hotness 都跑 pre-copy + stop-and-copy,差异只在 trigger detector 与 placement decision policy。可量化:M4 报告 protocol code path LoC reuse 率(目标 ≥ 80%),区别于 BanaServe(load only)、AnchorTP(failure only)、Tarragon(failure-only MoE)的单 trigger 实现
  - **Vendor-neutral**:AnchorTP / BanaServe / Tarragon / ReviveMoE 普遍假设单一 vendor stack,本提案天然跨 ConnectX + EFA(继承 [[TransferEngine-MLSys26]])
- **不新颖处**:
  - "Decoupled daemon 保留 KV 在显存"已被 [AnchorTP](https://arxiv.org/abs/2511.11617) 提出
  - "Live autoscaling"被 [[BlitzScale-OSDI25]] 充分讨论
  - "P2P RDMA 跨 vendor"是 [[TransferEngine-MLSys26]] 的 contribution
  - "Non-failure trigger 上的 KV-preserving migration"被 [BanaServe](https://arxiv.org/abs/2510.13223) 在 layer + attention 粒度做了——本提案的差异不在"是否 non-failure",而在 grain(session)+ topology(decentralized)+ trigger 数(4)
  - VM live migration 的 pre-copy + stop-and-copy 本身是 2005 年起的成熟技术
- **总体判断**:**medium**。同方向 6 个月内密集出现 4-5 篇 arXiv,纯"FT for LLM serving"或"KV migration on load"已饱和;本提案的差异化必须以**三联组合**为单位 narrate(任一单点都已被某 prior work 占据),OSDI-bar 取决于评审对"decentralized + session-grain + 4-trigger 协议复用"组合是否构成实质 contribution 的判断。若评审认为只是 packaging,投 NSDI 更合适(协议 contribution 比抽象 contribution 突出)。

## 可行性评估

- **核心组件**:
  - **Session state codec**(~2 周,1 人):序列化/反序列化 KV layout、RNG、sampler 配置、token history;校验和;版本号
  - **Migration controller**(~3 周):pre-copy 调度、停顿点选择、target rank 准备、handoff 协议
  - **Failure detector**(~2 周):基于 [[TransferEngine-MLSys26|TransferEngine]] IMMCOUNTER 超时 + heartbeat,识别 rank-level / instance-level 故障
  - **Hot-standby manager**(~2 周):standby 池管理、权重 lazy load、failure 触发 standby promotion
  - **Rank-failover protocol**(~2 周):侦测 → promote standby → KV reattach → 在最近 layer boundary 接续
  - **Decentralized prefix index**(~2 周):每个 instance 维护 local prefix index,Bloom filter 广播 + on-demand P2P pull;FP rate budget 设定 ≤ 1%(filter size 与广播频率折中)
  - **Bandwidth reservation 机制**(~1 周):pre-copy 与 PD KV transfer 共享 NIC 时,token-bucket 限速保证 production 流量优先(见 R5)
  - **Chaos injection harness**(~1 周):生产 trace replay + 可控 GPU kill / link drop / latency injection
  - **Eval pipeline**(~2 周):TTFT/TPOT/RTO/挽留率/迁移开销的自动测量与可视化

- **可复用代码**:
  - [[vLLM]] 0.7+ 作为 host serving 框架(选 vLLM 因为 BlitzScale 也开源在 vLLM 之上,baseline 对齐方便)
  - [pplx-garden TransferEngine](https://github.com/perplexityai/pplx-garden) 作为通信层(Nov 2025 已 MIT 开源,直接复用,不需 fallback)
  - [BlitzScale 开源代码](https://github.com/blitz-serving/blitz-scale)作为 autoscaling baseline(46 stars, Rust, OSDI'25 official 实现)
  - BurstGPT / AzureCode / AzureConv trace 作为 workload(同 BlitzScale)
  - chaos-mesh / 自写脚本做 GPU 故障注入

- **数据 / 算力**:
  - **硬件**:1-3 × 8 H100 / H200。1 台用于单实例 baseline + 故障注入;2 台做 cross-instance migration;3 台做完整 chaos 集群 + hot-standby。完全在大学实验室 / 单云 instance 可达(AWS p5 / Lambda 8-GPU 节点)
  - **模型**:Llama-3-70B(TP8 fits 8×H100),Qwen3-32B(TP4 + DP2),DeepSeek-V2-Lite-16B(MoE,TP4 + EP4)。无须 trillion-param
  - **trace**:BurstGPT、Azure 公开数据集

- **关键风险**:
  - **R1: Stop-and-copy 接管的正确性语义** — pre-copy 期间 source 还在生成 token,stop-and-copy 时 source/target 必须同步 RNG state、KV delta、token history。**Bit-exact 在异构 sharding(不同 TP 度、不同 stream 配置)下不可期**(CUDA reduction 顺序敏感)。**修正后的验证 metric**:(a) 同 sharding 下 token sequence bit-exact;(b) 异构 sharding 下 attention output L∞ 误差 < ε(ε=1e-3 量级),分布距离(top-k overlap、KL divergence)与 baseline 无统计显著差异。Sampled decoding 下,把 RNG state 与 sampler 配置一并迁,target 用同 seed 续采(详见"开放问题")
  - **R2: BanaServe scoop-risk** — BanaServe 已经在 load 触发器上做 module + KV cache migration,本提案不能再以"首个非故障 KV-preserving migration"为 narrative。**Mitigation**:narrative 重心从"first"改为"distinct design point",在 M4 上做 BanaServe-style baseline 严格对比(实测 decentralized vs centralized 的 metadata service overhead、session-grain vs layer/attention-grain 在 sampled decoding continuation 上的差异、4-trigger 协议复用率),把三联组合的实测证据作为 contribution 主体
  - **R3: AnchorTP 已发表** — 评审会问"你比 AnchorTP 多了什么"。**Mitigation**:eval 中明确加 "non-failure migration" 场景(load shift / planned drain),AnchorTP 在这些场景下要么不支持要么退化为 cold restart——这是 narrative 重心,不是次要 ablation
  - **R4: MoE expert migration 与 session 迁移耦合** — 不同 expert hotness 触发的迁移粒度不同。**Mitigation**:dense 与 MoE 都是 must-have,但 M3 先打通 dense,M4 才接 MoE 完整 eval;若 MoE 实现严重超期,M4 可只展示 MoE 上"failure 接管"的基本可用性,不打吞吐对比
  - **R5: Bit-exact 不可能跨 sharding** — 见 R1 的 metric 调整。同时本风险意味着**不能宣称"perfect continuation"**,只能宣称"distributional equivalence"
  - **R6: Pre-copy 带宽与 production traffic 抢占** — PD-disagg 已经吃掉相当 RDMA 带宽,pre-copy 叠加会冲击 SLO。**Mitigation**:用 token-bucket reserve production-traffic 的 minimum bandwidth(typical: 留 20-30% NIC BW 给 pre-copy),pre-copy 退化为更长但不阻塞;ablation 中 sweep 该比例
  - **R7: Replica-less prefix cache 与 FT 取舍** — 若 prefix 持有者挂掉,prefix 失效。**Mitigation**:**显式声明 prefix-level 不保 FT**,FT 主体是 session(由 hot-standby 接管);prefix miss 退化为标准 cache miss + re-prefill,production 端可观察的影响仅是该请求 TTFT 抖动一次。这是设计选择,不是 bug
  - **R8: Sampled decoding 正确性 metric 缺乏共识** — 学术界对"sampling 下迁移正确"无标准定义。**Mitigation**:借用 RL / synthetic-data 评估的标准做法——用 KL divergence、top-k overlap、人评 sample 数据对比 baseline,而非追求 bit-exact
  - **R9: Baseline 复现工程量** — AnchorTP / BanaServe / Tarragon / ReviveMoE 全部无公开开源,从 paper 实现 fair baseline 单项 2-4 人周。**Mitigation**:M4 收窄到 AnchorTP(failure)+ BanaServe-style(load)两个核心 baseline 严格做;Tarragon / ReviveMoE 仅引用其论文数字 narrative 对比,不自实现;M4 时长扩到 5 周

- **总体判断**:**high**。所有核心组件都有可参考的开源前序工作或论文实现;硬件需求小;trace 公开;主要工程量在 controller + protocol 实现 + 2 核心 baseline 复现 + 4 trigger 场景 eval,**4-5 人 5-7 个月**可达 paper-grade prototype(effort 标 medium-long)。

## 实现规划

### M1 — Baseline + 通信层准备(~3 周)
- 部署 [[vLLM]] 0.7+ 单实例 + PD disaggregation in 8 卡 H100,跑 BurstGPT trace
- 集成 [pplx-garden TransferEngine](https://github.com/perplexityai/pplx-garden) 作为 KV transfer layer,验证 paged WRITE 和 IMMCOUNTER notify 端到端可用
- 实现 bandwidth reservation 机制(token bucket,可配比)
- 复现 [[BlitzScale-OSDI25]] 数字作为 autoscaling baseline
- 实现 chaos injection harness(GPU kill、NIC drop、link latency)
- **验证标准**:Llama-3-70B TP8 上 BurstGPT trace 跑通,TTFT P95 与 [[vLLM]] 论文 / [[BlitzScale-OSDI25]] 对齐(±10%);chaos harness 能确定性触发 rank failure 与 instance drain

### M2 — Session 抽象 + Live migration 协议(~4 周)
- 定义 session state schema 与 codec(含 RNG state 与 sampler 配置)
- 实现 pre-copy phase:source decode 中后台 P2P 推 KV shard,target 维护 warm state;pre-copy 跑在 reserved bandwidth 内
- 实现 stop-and-copy phase:在 layer boundary 同步 RNG + 增量 KV + token history,target 接管(目标 stop 1-2 个 decode iter)
- 同 sharding 下验证 bit-exact;异构 sharding 下验证 ε-tolerance + 分布等价
- **验证标准**:在 2 台 H100 节点之间,迁移一个 in-flight Llama-3-70B 解码 session(prompt 4K + output 1K):
  - (a) 同 sharding (TP8 → TP8) 下 deterministic decoding,token sequence 与 baseline 完全一致 + sampled decoding 下 KL(P_target ‖ P_baseline) < 0.05、top-k overlap > 0.95
  - (b) 异构 sharding (TP8 → TP4×2) 下 attention output L∞ < 1e-3
  - (c) 迁移期 TPOT 退化 P95 < 10%(该阶段允许放宽,M3 目标 < 5%)
  - (d) 迁移触发到完成 < 500 ms
- **Go/no-go gate**:若 R1 metric 在 M2 末仍不达标 → pivot 到 token-only 迁移变体(承认与 ServerlessLLM/可能的 ReviveMoE 范式趋同,差异化退到 "unified controller for both KV-preserving and token-only modes")

### M3 — Rank-level failover + decentralized prefix index(~3 周)
- 实现 hot-standby manager:每实例预留 1/8 standby rank,权重已加载、未上线服务
- IMMCOUNTER 超时检测 → promote standby → KV reattach 从幸存 ranks(对 TP)或 partner replica(对 EP)拉
- 在最近 layer boundary 重接 in-flight requests
- 每个 instance 维护 prefix Bloom filter + 周期 broadcast(目标 FP rate ≤ 1%、广播 BW ≤ 1% NIC),decentralized prefix lookup;prefix miss 透明 fallback 到 re-prefill
- **Sanity-check**:对 BanaServe-style 中心 KV store baseline(自实现轻量版)做 load 场景 retention 数字测量,据此校准 M4 阈值是否需要再调
- **验证标准**:
  - (a) 注入 1/8 rank failure,**有 hot-standby 时**服务空白 < 500 ms,TPOT P95 退化 < 5%,挽留 ≥ 90% in-flight requests;无 hot-standby 时(冷重启) RTO ~3-5s 作 baseline 对比
  - (b) prefix cache 跨 3 instance 命中率 vs. centralized [LMCache](https://arxiv.org/abs/2510.09665) baseline 在 ShareGPT trace 上差距 < 3 个百分点;Bloom filter FP 触发的失败 P2P pull < 1% 总 prefix lookup
  - (c) 12.5% standby capacity overhead 下端到端吞吐损失 < 15%(hot-standby cost 量化)

### M4 — 完整 eval + ablation(~5 周,扩展自原 3 周)
- **核心 baseline 严格做**(自实现 + 严格对比):
  1. **Failure-driven**:vs. [AnchorTP](https://arxiv.org/abs/2511.11617)-style restart-then-migrate(自实现轻量版,严格对比 RTO / 挽留率 / TPOT 退化)
  2. **Load-driven** ★:vs. [BanaServe](https://arxiv.org/abs/2510.13223)-style centralized KV Cache Store + layer/attention-grain migration(自实现轻量版,严格对比 retention / metadata service overhead / sampled decoding continuation 等价性 / 4-trigger 协议复用率)
- **Narrative baseline**(引用论文数字对比,不自实现):
  3. [Tarragon](https://arxiv.org/abs/2601.01310):MoE failure-only,本场景下 hotness shift 退化为 cold reroute;引用 paper 数字
  4. [ReviveMoE](https://arxiv.org/abs/2602.21140):若全文确认是 token-only,与本提案是 opposite design point;引用 paper 数字
  5. [[CRAFT-MLSys26]] 作为 static placement context(与本提案 runtime migration 是不同决策维度,可叠加)
- **4 个 trigger 场景**(★ 是差异化重心):
  1. Failure-driven:vs. AnchorTP-style baseline,预期挽留 ≥ 90%,RTO < 500 ms
  2. **Drain-driven** ★:vs. cancel + cold reroute(BlitzScale baseline 行为),预期挽留 ≥ 80% absolute(对照 baseline 0% retention by definition)
  3. **Load-driven** ★:vs. BanaServe-style centralized + layer/attention-grain,预期 hot instance 时 SLO 违规率降 ≥ 30%、sampled decoding KL divergence 显著优于 BanaServe-style baseline
  4. Hotness-driven (MoE):vs. cold reroute baseline + Tarragon paper 数字 narrative,展示 unification 不引入额外开销
- **Ablation**:pre-copy on/off、bandwidth reservation 比例 sweep、hot-standby capacity 比例 sweep、decentralized vs. centralized prefix、不同 stop-and-copy 调度策略、protocol code-path LoC reuse 量化(目标 ≥ 80%)
- **模型覆盖**:Llama-3-70B / Qwen3-32B / DeepSeek-V2-Lite-MoE
- **验证标准**(harmonized 与 TL;DR 同 metric basis):
  - Failure-driven:absolute 挽留率 ≥ 90%,RTO < 500 ms,TPOT P95 退化 < 5%
  - Drain-driven:absolute 挽留率 ≥ 80%(vs cancel-and-reroute baseline 0% retention)
  - Load-driven:SLO 违规率较 BanaServe-style baseline 降 ≥ 30%,sampled decoding continuation KL < 0.05 vs BanaServe-style baseline KL > 0.1(layer-grain 不显式 carry sampler state 的可观测后果)
  - Hotness-driven (MoE):至少不退化于 cold reroute,protocol 复用率 ≥ 80%
  - Ablation 显示每个组件贡献 ≥ 5%

> **Go/No-Go gates**:
> - M2 末若 R1 metric 不达标 → pivot 到 token-only 迁移变体(承认 ServerlessLLM 范式趋同)
> - M3 末若 hot-standby capacity overhead 过高(端到端吞吐损失 > 30%) → 转向 lazy weight reload + 容忍 RTO ~1s 的设计
> - M3 末 sanity-check 若 BanaServe-style baseline 已能在 load 场景挽留 ≥ 70% → 重新校准 M4 drain/load 场景的差异化叙事(可能转 NSDI)
> - M4 末若 drain/load 场景三联组合的实测证据(decentralized vs centralized 实测开销 + session-grain sampler equivalence + 协议复用率)合在一起仍构不成 distinct contribution → 重写 narrative,转向 NSDI(协议 contribution 比抽象 contribution 突出),不强行投 OSDI

## 开放问题

- **Session 跨异构 sharding 的迁移**:source 用 GQA-8 + TP4,target 用 MLA + TP8,KV layout 不兼容,是否在 codec 层做 transcoding?cost / benefit 如何?
- **Sampled decoding 下迁移的"正确性"标准**:R1 / R8 给了 metric 方向(KL + top-k overlap + 人评),但学术界缺共识;本提案是否需要顺手提一个 standard benchmark?
- **Pre-copy bandwidth 与 KV-aware schedule 协同**:reserve 比例固定还是按 source 当前 TPOT 余量动态调?能否与 [[NanoFlow-OSDI25]] / FlashAttention 的 op-level overlap 协同?
- **多 trigger 同时触发**:rank failure + load 突发同时来,migration controller 如何 priority schedule?这是 OS scheduler 类问题,可借鉴现有 OS 调度文献
- **MoE expert migration 与 session migration 的边界**:expert 是 weight 不是 state,但热度会牵引 session placement;两者应该是同一 controller 还是分层?
- **Hot-standby 比例的自适应**:固定 1/8 是否最优?能否按 historical failure rate / drain frequency 动态调?
- **OSDI vs NSDI 取舍**:本提案的 "P2P 协议 + bandwidth reservation" 成分重,如果协议 contribution 比抽象 contribution 更突出,NSDI 更对口;反之保持 OSDI——M3 sanity-check 与 M4 结果会决定

## 参考

- 内部相关:[[Disaggregation]]、[[KV-Cache]]、[[RDMA]]、[[TransferEngine-MLSys26]]、[[BlitzScale-OSDI25]]、[[FuseLink-OSDI25]]、[[MorphServe-MLSys26]]、[[SMon-OSDI25]]、[[NVIDIA-Disagg-Study-MLSys26]]、[[CRAFT-MLSys26]]、[[OSDI-2025]]、[[MLSys-2026]]
- 外部链接(已在「相关工作(外部)」展开):[AnchorTP](https://arxiv.org/abs/2511.11617) / [BanaServe](https://arxiv.org/abs/2510.13223) / [Tarragon](https://arxiv.org/abs/2601.01310) / [ReviveMoE](https://arxiv.org/abs/2602.21140) / [xLLM](https://arxiv.org/abs/2510.14686) / [LMCache](https://arxiv.org/abs/2510.09665) / [ServerlessLLM](https://arxiv.org/abs/2401.14351) / [LoongServe](https://arxiv.org/abs/2404.09526) / [Mooncake](https://arxiv.org/abs/2407.00079)
