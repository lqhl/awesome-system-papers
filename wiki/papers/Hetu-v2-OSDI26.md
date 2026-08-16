---
type: paper
name: Hetu-v2
full_title: "Hetu v2: A General and Scalable Deep Learning System with Hierarchical and Heterogeneous Single Program Multiple Data Annotations"
authors: [Haoyang Li, Fangcheng Fu, Hao Ge, Sheng Lin, Xuanyu Wang, Jiawen Niu, Yuming Zhou, Xupeng Miao, Bin Cui]
venue: OSDI
year: 2026
tags: [distributed-training, spmd, heterogeneous-computing, elastic-training, parallelism]
source_pdf: "[[osdi26-li-haoyang.pdf]]"
source_md: "[[osdi26-li-haoyang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Hetu v2：用分层异构 SPMD 表达异构训练（OSDI 2026）

> **原题**：Hetu v2: A General and Scalable Deep Learning System with Hierarchical and Heterogeneous Single Program Multiple Data Annotations

> **一句话总结**：标准 SPMD 的对称分片无法充分利用混合 GPU、故障后的剩余 GPU 和变长数据；Hetu v2 的 HSPMD 用两层非对称 annotation、逐设备 graph specialization 与在线 graph switching 保留单程序接口，在 16 张 H800 加 32 张 H20 上把 32B Llama 每步时间从 DeepSpeed 的 13.78 秒、Megatron 的 10.45 秒和 HexiScale 的 8.06 秒降到 6.05 秒，但性能仍依赖场景专用 planner。

## 问题与动机

SPMD 让用户从单设备视角写程序，再由系统根据 annotation 推导 tensor sharding 和通信。这个接口简单、容易扩展到大集群，但它默认设备 mesh 规则、各 shard 工作量相同、collective 的参与者对称。现代 [[LLM]] 训练却越来越不满足这些前提：云集群会混用不同代 GPU，故障会留下不规则数量的设备，文本和多媒体样本的长度也会不断变化。

MPMD 可以为不同设备生成不同程序，却可能在大规模单任务训练中管理大量 program 和 compilation。HexiScale、Oobleck、HotSPa 等系统仍保留 SPMD，但把非对称行为写进某一种场景的 scheduler；这种方案能解决目标问题，却让策略表达、执行机制和场景绑定，难以复用。

Hetu v2 的 HSPMD（Hierarchical and Heterogeneous SPMD）把非对称能力下沉到 tensor annotation。论文再把异构性拆成两个维度：同一时刻负载不均是空间异构，需要让不同设备执行不同 graph；资源或输入随时间变化是时间异构，需要在线切换 parallel strategy。系统提供统一执行底座，但自动寻找好策略仍交给可替换的 scenario-specific planner。

## 关键观察 / 隐含假设

- **观察 1**：混合 GPU、设备故障和 mixed-length data 的表面原因不同，最终都需要非对称 sharding；后两者还需要随时间重配置（表 1、图 2–图 3）。
  - **依赖假设**：这三类异构能代表大规模训练中的主要不对称需求。
  - **可能失效场景**：动态 [[MoE]] routing、多租户抢占、跨 region 网络和非 GPU accelerator 可能引入新的状态与调度约束；论文只讨论 MoE 的可表达性，没有实现。
- **观察 2**：真实集群常呈现“subgroup 内相对同构、subgroup 间异构”的两层结构，因此可以在组内复用成熟 SPMD collective，只在组间表达不对称（§4–§5）。
  - **依赖假设**：两层 hierarchy 足以近似 node、GPU group 和网络拓扑。
  - **可能失效场景**：rack、pod、cluster 多级带宽与共享链路同时主导时，两层模型和只看 P2P bandwidth 的 BSR heuristic 可能选错路径。
- **观察 3**：不同 parallel strategy 的持久状态差异可以表示为 tensor layout 变化，因而能用 reshard 直接从旧 graph 切到新 graph，无需 checkpoint-restart（§7、图 14）。
  - **依赖假设**：剩余设备还保存完整参数和 optimizer state；fault-tolerant 配置为此保留 [[Data-Parallelism|数据并行]] redundancy 并禁用 [[ZeRO|ZeRO-1]]。
  - **可能失效场景**：多个 replica 同时丢失、optimizer state 不完整，或 collective 中途故障时，仍可能需要 checkpoint。
- **观察 4**：大部分 operator annotation 可直接传播，复杂 Reshard 也常能分解成现有 all-reduce、all-gather 和 reduce-scatter（表 2、图 7）。
  - **依赖假设**：operator sharding rule 和 tensor shape 约束完整且正确；BSR 不需要处理复杂 Partial tensor。
  - **可能失效场景**：新 operator、动态控制流或 Partial 参与复杂重分片时，需要新增规则和通信实现。
- **假设 1**：外部 planner 的 profile、cost model 和输入分布足以选出接近最优的 annotation plan。
  - **证据强度**：中。论文在三种场景都得到好结果，也把 DeepSpeed/Megatron 调到最优；但没有独立报告 cost-model error 或 planner optimality gap。

## 核心方法

标准 SPMD annotation 用 Device Group（DG）表示 tensor 在哪些设备上，用 Distributed States（DS）表示 Split、Duplicate 或 Partial。HSPMD 把单个 DG/DS 提升为 DG Union 和 DS Union：每个 sharding subgroup 仍执行普通 SPMD，称为 bottom tier；`HSize` 表示 subgroup 数量，`HDim` 表示 subgroup 之间沿哪个 tensor dimension Split、Duplicate 或 Partial，称为 top tier（§4、图 6）。这样，同一个 tensor 可以在不同 GPU 组采用不同 [[Tensor-Parallelism|张量并行]] degree。

通信解析先尽量复用 collective。Top-tier layout 不变时，各 subgroup 独立选择 identity、send-receive、all-reduce、reduce-scatter 或 all-gather；只有 `HDim` 变化时，系统切到共同的最细 slice，再生成 SplitAR、SplitRS 或 SplitAG。Collective 无法表达的重分片由 Batched-Send-Receive（BSR）完成：BSR table 记录每个 slice 的 owner 和 receiver，heuristic 优先高带宽 link 并均衡累计发送量。它把 NP-hard assignment 降为 `O(pq)`，但只建模 P2P bandwidth，且不直接处理带 Partial 的复杂 BSR（§5、图 7–图 11）。

用户定义一个包含 Leaf、Reshard marker 和普通 operator 的逻辑 graph，annotation plan 只标注关键 tensor。Graph specialization 先把 annotation 传播到整个 graph，再为每个设备删除 non-local operator、实例化通信，得到 device-specific executable graph。执行时又把 graph 拆为 pre/post、forward 和 backward subgraph，支持 GPipe 与 1F1B；symbolic shape 在运行时解析，使不同 pipeline 能处理不同 micro-batch 数量、大小和 sequence length（§6、附录 A.2）。

时间异构由 graph switching 处理。新计划到达后，系统 specialization 新 graph，用旧、新 annotation 计算每个 weight 的 reshard，再把多个 tensor 的 BSR 合成一个 Fused BSR，以便在所有 GPU 间平衡 NVLink/[[RDMA|IB]] 流量。故障场景在线生成一个新计划；mixed-length 场景则离线准备少量按 maximum sequence length 划分的 graph，运行时只选择并切换（§7、图 14）。

默认 planner 对 operator、GPU 和 interconnect 做 profiling，以 ILP、MINLP 或 dynamic programming 生成计划。它是模块化组件，不是 HSPMD abstraction 的一部分；极端情况下可退化为 homogeneous SPMD，保证能运行但不保证有异构加速。整个 prototype 有 87.9K 行 C++ 和 16.9K 行 CUDA，其中 HSPMD 核心约 16.9K 行 C++，说明它是完整训练 runtime，而不是给现有框架加几个 annotation 字段就能得到的实现（§8、附录 A）。

## 设计取舍

- **两层 annotation，换取可控复杂度**：覆盖论文中的 node/group 异构并复用 SPMD rule；代价是更深层网络只能压平到两层，规划可能忽略共享 bottleneck。
- **低层 primitive，换取通用表达力**：同一套机制能服务三种场景；实现必须维护 operator deduction、device graph、symbolic shape 和新通信原语。
- **优先 collective，BSR 兜底**：常见路径利用 [[NCCL|NCCL]] 的成熟优化；BSR heuristic 不保证全局最优，也未覆盖一般 Partial reshard。
- **运行时 reshard，换取 restart-free reconfiguration**：省去 checkpoint reload；切换期间仍需传输参数和 optimizer state，通信组创建可达数秒。
- **DP redundancy，换取故障恢复**：单 GPU/node failure 后可继续使用剩余设备；禁用 ZeRO-1 增加内存占用，并让正常 step time 约增加 15%。
- **planner 可替换，换取系统边界清晰**：HSPMD 不绑定一种搜索算法；论文的端到端收益却依赖 planner profile 和 workload prediction。

## 实验与结果

- 测试床包含 16 张 H800 与 32 张 H20；H800 BF16 算力为 990 TFLOPS、NVLink 为 400 GB/s，H20 分别为 148 TFLOPS 与 900 GB/s。32B、16 H800 加 32 H20 时，HSPMD 每步 6.05 秒，DeepSpeed、Megatron、HexiScale 分别为 13.78、10.45、8.06 秒；跨异构配置，HSPMD 最多比 DeepSpeed 快 2.3 倍、比 HexiScale 快 1.4 倍，而同构配置的差距很小（§9、图 15、表 7）。
- 32 H20 降为 31 H20 时，HSPMD 的在线重配置为 10.39 秒，DeepSpeed/Megatron checkpoint-restart 为 86.41/95.37 秒；重配置后 HSPMD 每步 17.27 秒，Oobleck 为 28.36 秒。异构 trace 中 HSPMD 的切换为 10.79–14.76 秒，两个 standard SPMD baseline 的 restart 为 69.63–92.02 秒（§9、图 16）。
- 32 H20、32B Llama、100 steps、200K-token batch 的 mixed-length 实验中，32K CommonCrawl 的平均 step time 为 12.56 秒，HotSPa、Megatron、DeepSpeed 分别为 19.56、27.94、36.52 秒；四个 dataset/context 组合中，HSPMD 相对 HotSPa 最多快 1.56 倍，相对 DeepSpeed 最多快 2.91 倍（§9、图 17–图 18）。
- C1 到 C2 的 10.39 秒重配置由 planning 0.82 秒、graph specialization 7.40 秒和 Fused BSR switching 2.17 秒组成；specialization 中 operator instantiation 为 7.15 秒，annotation deduction 仅 0.24 秒。Fused BSR 把无 heuristic 的 13.94 秒总时间降低约 25%，总通信量不变但跨 rank 更均衡（§10、图 20、表 4）。
- Fault-tolerant C4 配置为保留 DP replica 禁用 ZeRO-1，32B 模型每步从普通异构训练的 6.05 秒增至 6.91 秒，论文计为约 15% 成本；附录 B 的约 1,100-step loss trace 显示 C1、C2 与 Megatron 均收敛，但只覆盖一个模型与两种策略（附录 B、附录 C.3、图 22）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Primitive-level asymmetry 能提高混合 GPU 训练效率 | 图 15：32B、16 H800 加 32 H20 时为 6.05 秒/step，三个 baseline 为 8.06–13.78 秒 | Llama 32B/70B、两种 GPU、最多 48 卡 | 强 |
| 同一 abstraction 能支持静态、故障和数据异构 | 图 15–图 18 分别覆盖 heterogeneous GPU、failure trace、CommonCrawl/GitHub | 三类人工选定场景，均为 Llama training | 强 |
| Annotation-guided switching 比 restart/template 更灵活 | 图 16：HSPMD 切换 10.39–14.76 秒，restart 69.63–95.37 秒，且 step time 低于 Oobleck | 依赖 DP replica；未覆盖 replica 同时丢失 | 强 |
| Fused BSR 能降低切换通信开销 | 图 20、表 4：相同总 volume 下，13.94 秒降到 10.39 秒 | 单次 C1→C2、论文特定 NVLink/IB topology | 强 |
| 两层 HSPMD 是面向异构训练的一般基础抽象 | §11 说明 MoE 和现有 SPMD 可扩展，但没有对应实现或实验 | 实证只覆盖 Llama 与三种场景 | 中弱 |

## 批判性分析

### 论证链条

论文的核心贡献是把“不对称”变成 annotation 能直接表达的语义，而不只是再做一个 scheduler。两层 annotation 产生 tensor layout，layout 同时驱动 communication resolution、device graph specialization 和 graph switching，因此从表达、执行到迁移的逻辑是统一的。三个场景复用同一组 primitive，确实支持“比逐场景堆 scheduler 更一般”的主张。

不过，性能优势由两部分共同产生：HSPMD 扩大 strategy space，scenario-specific planner 再找到好策略。实验说明组合有效，却没有分离 abstraction 与 planner quality 的贡献。“可以 fallback 到 homogeneous SPMD”只是可执行性下界，不是性能下界。

### 假设压力测试

两层结构适合论文的 H800/H20 cluster，但真实 fabric 可能同时有 NVLink、[[PCIe|PCIe]]、跨 node IB、跨 rack oversubscription。BSR 只用 endpoint P2P bandwidth，没有追踪 path 上共享 link；并发 collective 或其他 tenant 制造拥塞时，平衡 sender 不一定平衡网络。

故障实验还依赖至少一个完整 DP replica。若故障同时破坏所有 replica 中同一参数分片，graph switching 无法凭空恢复状态。论文也没有展示 collective 中途失败、straggler、GPU memory error 的检测和一致性恢复；图 16 更接近“device availability 改变后的重规划”实验。

### 实验可信度

优点是 DeepSpeed、Megatron 使用穷举出的最佳配置，同构实验控制了 runtime engineering 差异；每个场景还选择了强专用 baseline。图 20 把 planning、specialization 和 switching 分开，附录又公开具体 parallel strategy 与 loss curve，证据较完整。

边界也明显：硬件只有 H800/H20 两类、最大 48 卡，模型只有 Llama 32B/70B。Mixed-length 使用 100-step trace，failure trace 的事件数很少；没有 production failure distribution、network contention、cost-model prediction error 或多次运行方差。收敛性只测一个 32B 配置，不能代替对所有 reshard rule 的正确性验证。

### 系统性缺陷

HSPMD prototype 是 10 万行以上的自建 C++/CUDA training framework。论文说 annotation-based SPMD framework 可增加一层后复用 HSPMD，但没有真正把它接入 GSPMD、Alpa 或 DTensor；对 Megatron/DeepSpeed 这类 layer API 更难。维护 operator rule、symbolic shape、NCCL group 与 kernel 的成本不可忽略。

在线 specialization 主要花在创建 operator 和 CCL group，单次为 6.2–7.9 秒。高频抢占或短作业中，这个成本可能超过收益。论文也没有说明 switching 中途 crash、旧新 graph 并存时的资源上限、失败回退、计划版本和 observability；错误 annotation 或 BSR scheme 如何安全拒绝执行仍不清楚。

## 局限与后续工作

- **局限 1**：实证只覆盖两种 GPU、最多 48 卡和 Llama；MoE、视觉、多模态与更深网络层级仍是设计推断。
- **局限 2**：端到端性能依赖外部 planner，但论文没有报告 cost-model error、optimality gap 或 workload drift。
- **局限 3**：restart-free failure recovery 依赖 DP replica，且没有测试 simultaneous replica loss、in-flight collective failure 或 switching crash。
- **后续工作 1**：在 2、3、4 层 topology 和 background traffic 下比较 P2P-only 与 per-link contention model，报告 plan regret、step time 和 BSR tail latency。
- **后续工作 2**：对 planner 注入 5%、10%、20% profile error 及 sequence-distribution drift，测策略选择错误率和 homogeneous fallback 触发点。
- **后续工作 3**：在实际 GPU kill、node loss、collective hang 和 switching crash 下做 fault injection，验证 parameter/optimizer checksum、恢复时间和重复 step 行为。
- **后续工作 4**：把 HSPMD 接入至少一个现有 annotation framework，并以 MoE expert imbalance 实测开发改动、兼容性和跨版本维护成本。

## 相关

- **相关概念**：[[SPMD]]、[[Distributed-Training]]、[[Heterogeneous-Computing]]、[[Elastic-Training]]、[[Hybrid-Parallelism]]
- **并行机制**：[[Data-Parallelism]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[ZeRO]]
- **同类系统**：[[DeepSpeed]]、[[Megatron]]、[[HexiScale]]、[[Oobleck]]、[[HotSPa]]
- **同会议**：[[OSDI-2026]]
