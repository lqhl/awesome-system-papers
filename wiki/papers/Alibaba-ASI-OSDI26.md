---
type: paper
name: Alibaba-ASI
full_title: "Heterogeneity at Hyperscale: Characterization and Scheduling of Large Production AI Clusters at Alibaba (Operational Systems)"
authors: [Suyi Li, Lingyun Yang, Haoxuan Yu, Sheng Yao, Tianyuan Wu, Xiaoxiao Jiang, Hanfeng Lu, Kangjin Wang, Chenhao Wang, Shenglin Xu, Lun Wang, Qingyang Duan, Shenghao Liang, Xiu Lin, Meng Zhang, Wenchao Wu, Yinghao Yu, Guodong Yang, Liping Zhang, Wei Wang]
venue: OSDI
year: 2026
tags: [gpu-cluster, workload-characterization, scheduling, fragmentation, production-system]
source_pdf: "[[osdi26-li-suyi.pdf]]"
source_md: "[[osdi26-li-suyi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Alibaba ASI：超大规模异构生产 AI 集群的刻画与调度

> **原题**：Heterogeneity at Hyperscale: Characterization and Scheduling of Large Production AI Clusters at Alibaba (Operational Systems)

> **一句话总结**：Alibaba ASI 的六个月、15.5 万 GPU trace 表明，生产集群的主要困难已经不是“把一个 GPU 切得更细”，而是 GPU 型号锁定、8-GPU 节点上的剩余卡、CPU 配比、网络拓扑和在线服务预留容量相互叠加；论文用 IPC 去碎片和 SpotGPU 回收预留容量，但 93% allocation ratio 仍不等于 93% 计算利用率。

## 问题与动机

现代 AI 集群同时运行开发、训练、在线推理和离线推理，也同时包含多代 NVIDIA GPU 与其他厂商 XPU。不同作业要求不同 GPU 型号、CPU 数、节点数量和网络位置。即使集群总空闲 GPU 很多，一个新作业也可能因为“卡不在同一节点”“CPU 已被占满”或“卡分散在不同 access switch（ASW）”而无法调度。

另一个问题是在线服务会为白天峰值、故障切换和突发活动预留容量。夜间这些 GPU 已经分配给高优先级服务，却没有做多少计算。普通 GPU sharing 只能回收单卡内的小碎片，也难以应对大模型占满显存和强隔离需求。

论文做两件事：先用 Alibaba Serverless Infrastructure（ASI）的生产 trace 说明异构集群真实负载，再介绍已经部署的 IPC 去碎片、拓扑感知放置和 SpotGPU。最后，它用 XPU-A 适配案例说明：异构硬件能否被采用，不只由规格决定，还取决于 kernel 和软件栈。

## 数据范围与读法

Trace 覆盖 2025 年连续六个月、约 1,400 万 jobs、155,410 GPUs、37,707 GPU nodes 和 81 个部门。作业包含 Dev、Training、Online-inference、Offline-inference；硬件包含 H20、H800、A10、A30、A100、A800、L20 以及匿名的 XPU-A/B/C/D/E。每个任务的资源请求、等待和运行时间，以及 GPU SM、显存、CPU 和主存利用率都有记录，运行中遥测每 20 秒采样一次（§3.1–§3.3、表 1）。

需要注意，trace 不包括运行在独立高端集群上的超大 foundation model 预训练；它代表的是 Alibaba 大型共享生产集群。公开版还做了脱敏，GPU 厂商、业务细类和部分策略信息不可见。因此，它比小规模实验更真实，但不是“Alibaba 所有 AI 计算”的完整画像（§6）。

## 关键观察 / 隐含假设

- **GPU 型号几乎不可替换。** 超过 99% 的 jobs 指定 GPU 型号，少于 1% 混用不同 GPU。硬件理论兼容并没有自然变成 scheduler 可用的弹性（图 4、§3.1）。
- **工作负载比旧 trace 更大、更久。** ASI job 的 GPU request 中位数/均值为 2/11，GenAI 子集为 4/11；PAI 是 1/2.6，Acme 是 1/5。ASI job 运行中位数为 5 小时，PAI 为 23 分钟，Acme 为 2 分钟（图 7–8）。
- **分配率和实际计算利用率是两个指标。** 加入低优先级作业后，集群 allocation ratio 从 68% 到 93%，表示 GPU 容量被 job claim；但在线推理整体 SM 中位数只有 6%，所以不能把 93% 叫作“SM 利用率”（图 9、§5.2）。
- **fractional GPU 不是主导碎片。** ASI 很少使用小数 GPU。对大多数请求，真正阻塞来自 8-GPU 节点上剩余的整卡、CPU 不足和拓扑约束（图 10、13–14）。
- **网络 locality 会把“总量足够”变成“局部不够”。** 同一 ASW 内 all-reduce bandwidth 比跨 ASW 高 27%，但强制同 ASW 会大幅减少可满足的大作业数量（§4.1）。
- **预留容量可收割，但依赖用户合作。** SpotGPU 假设 HP 服务愿意进入 Standby，LP 作业可 checkpoint、可被 60 秒内终止，并接受折扣资源没有保证。
- **硬件规格不是应用性能。** XPU-A 的显存、带宽和 FP16 规格优于 H20，但未优化 DeepSeek-R1 仍只达到约 68%–76% 的 H20 吞吐；关键差距来自 FlashAttention 与 SplitKV 的硬件映射（表 2、图 17）。

## 核心方法

### 1. IPC：用分区和 ejection chain 做在线去碎片

IPC（iterative partitioned consolidation）定期取得节点与任务快照，目标是迁走部分节点上的任务，腾出完整机器。集群先被随机切成互不重叠的 partition，各 partition 并行求解。这样牺牲全局最优，换取大规模下的分钟级决定（§4.1）。

每个 partition 内，IPC 优先尝试清空任务较少的节点。如果目标节点空间不足，它递归移动目标节点上的其他任务，形成 ejection chain；最大深度 `K=3`。算法同时检查 affinity、anti-affinity、GPU/CPU 需求，以及约 40% 不能移动的 locked tasks。一次执行最多 5 rounds，因为第 3 round 后边际收益已经很小（算法 1、图 15）。

迁移采用 make-before-break：先在目标节点启动新 instance，成功后再结束旧 instance，尽量避免服务中断。这个做法需要临时双份资源，也要求应用能容忍短时间重复 instance；论文没有量化迁移期间的资源峰值和尾延迟。

### 2. 用 entropy 尽量把大作业放进少数 ASW

对单个大作业，ASI 用 entropy 表示 GPU 在多个 ASW 上有多分散。调度器每轮选择加入后 entropy 最小的 ASW，尽量先填满少数 switch；生产中还按 job size 从大到小处理，并可复用 IPC 做跨 ASW 迁移（算法 2）。

该 greedy 对单个 job 最优，但多个 jobs 的先后顺序会形成组合问题。论文没有给出整个集群使用该策略后的 aggregate benefit，只把它作为已经部署的单作业规则和仍待解决的多作业问题（§4.1、§5.2）。

### 3. SpotGPU：在 job 粒度收割在线服务预留

高优先级（HP）作业获得不被抢占的保障；低优先级（LP）spot 作业价格更低，可以被 HP 收回资源。在线服务进入 Standby 时，ASI 断开流量，把容器主进程替换成 `sleep`，释放 CPU/GPU，但保留 warm container。恢复时先驱逐 LP，再还原原命令，避免重新拉镜像和完整调度（图 16、§4.2）。

调度器先尝试不抢占放置，并依次按三个条件打破平局：把任务 pack 到剩余 GPU 少的节点；把 HP 与 HP、LP 与 LP 放在一起；根据历史 eviction 把波动集中到一部分节点。若 HP 仍无法放下，再选择 LP victim。

抢占代价定义为 `GPU 数 × 距上次 checkpoint 的时间`，表示预计丢失的计算。对异构 GPU，这个标量变成按型号区分的资源向量。完整 MILP 在线求解太慢，因此生产使用按节点挑选最低代价 victim 的 heuristic（§4.2、附录 A）。

### 4. 用 kernel 适配缩小 XPU 采用差距

XPU-A 的 FlashAttention prefill 原实现沿 sequence 维度轮转分配工作，causal mask 让后半段工作更重，导致 compute engine 负载不均。作者改为沿 [[Attention|attention]] head 分配，在 4K sequence、64 heads 下把 prefill computation 提高 1.58×。

decode 的 [[PagedAttention]]/SplitKV 用 Triton 移植后，compiler 反转了 thread-block layout，使线程组重复计算整个矩阵。作者加入 compiler pass 修正并行映射，并把这些优化集成进 RTP-LLM，同时提供 drop-in API。这个案例说明“增加新 GPU 型号”必须同时投入 kernel、compiler 和 serving engine 适配（图 17–19、§5.1）。

## 设计取舍

- **IPC 用可控搜索换全局最优。** 25-node ILP 已需约 5 分钟，100 nodes 要 2 天；IPC 每 partition 可含 500 nodes，并在 2 分钟内决定，但随机分区会错过跨 partition 的更好迁移。
- **make-before-break 用容量换无中断。** 新旧 instance 暂时共存，不适合没有空闲 headroom 的集群；约 40% locked tasks 也限制可整理空间。
- **拓扑集中换可调度容量。** 同 ASW 通信快，却把分散在其他 ASW 的空闲 GPU 排除。多作业下不能只为当前大作业最小化 entropy。
- **SpotGPU 用 LP 重算换 HP 保障。** checkpoint 越旧、驱逐越慢，浪费越大。`GPU-time since checkpoint` 也没有表示 task 剩余时间、数据下载和恢复开销。
- **allocation ratio 换易运营指标。** 它适合计费与容量管理，却无法说明 GPU 是否在做有用的 tensor 计算。
- **多厂商换供应弹性。** 供应链风险降低，但硬件专用 kernel、编译器、通信和模型验证成为长期工程税。

## 实验与分析方法

论文不是传统“一个系统对多个 baseline”的评测，而是三类证据组合：六个月生产 trace 用于 workload characterization；两个月 trace replay 用于 IPC；线上部署统计用于 SpotGPU。网络 locality、XPU kernel 和 CPU/GPU interference 则来自定点 microbenchmark 或 case study。

因此，不同数字的因果强度不同。99% 型号锁定、运行时长和资源利用来自观察；IPC 的 20.2% 是历史 replay；SpotGPU 的收割率与 eviction 是生产记录；XPU 是少数模型/硬件的人工优化。不能把它们都当成同一种受控 A/B 实验。

## 实验与结果

- **共享集群以在线推理和长任务为主。** 在线推理超过 job 数的一半；GenAI 占训练的 71%、离线推理的 98%，在线推理则有 63% 是推荐模型。job 运行中位数 5 小时，调度中位数只有 1 秒；HP 的 P90 等待 101 秒，而 P90 运行时间为 24 小时。PD disaggregation 作业的日均 GPU 数在 trace 期从 1,041 增至 3,841，即 3.7×；但用户仍多选同型号 GPU，原因包括部署和跨硬件网络复杂度（图 2–8、§3）。
- **碎片主要在节点、CPU 与拓扑层。** fractional GPU 请求在 ASI 中几乎可以忽略；高 CPU/GPU ratio 时 CPU 先耗尽，中等到整节点请求则常留下 stranded GPUs。同 ASW 的 all-reduce bandwidth 比跨 ASW 高 27%，但加上同 ASW 限制后，128-GPU 请求的可满足数量从 A100 8、L20 14、H20 32 分别降为 0、0、17；256-GPU 请求从 3、5、15 降为 0、0、4。允许异构型号虽提高可满足量，实际却少于 1% jobs 使用（图 13–14、§4.1）。
- **IPC 很快，但核心容量收益来自 replay。** IPC 已在 scheduler 稳定运行多年，生成 migration decision 少于 2 分钟。两个月 trace replay 中，未满载节点减少 20.2%。对照上，25-node ILP 约 4,000 binary variables、800 constraints，16 CPU 上约 5 分钟；100 nodes 要 2 天。论文没有报告生产迁移后 job tail latency、失败率或实际腾空节点曲线（§4.1）。
- **SpotGPU 明显提高“被分配容量”，也带来可见抢占成本。** HP-only 的平均 GPU allocation ratio 为 68%，加 LP 后为 93%；Standby 在午夜最高可释放约 10,000 GPU-hours，平均 90% 被收割。LP graceful eviction 平均 13 秒、P95 48 秒，60 秒后仍未退出的少于 5%，这些会被 `SIGKILL`。与关闭 colocation/eviction awareness、随机选 victim 的 baseline 相比，成本感知 scheduler 将 LP completion time 降低 24%，未观察到 HP performance 下降（图 9、16、§4.2）。
- **异构 GPU 的瓶颈常在软件，剩余利用问题仍很大。** XPU-A 优化后，vLLM 在 1/2 RPS 下 request latency 相对未优化版低 33%/43%，相对 H20 低 2%/21%；优化发布后，HP 对 XPU-A 的请求量增至 2.5×。但在线推理总体 SM/显存中位数只有 6%/30%；其中 GenAI 为 5%/94%，传统 DNN 为 6%/20%。把 CPU-only job 与 GPU training 共置后，CPU-job-dominant nodes 上训练的 SM 中位数/P90 反而低 10%/18%，说明 allocation 提高后仍有隔离与有效利用问题（图 17–18、§5）。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 超大规模共享 AI 集群的主导碎片不是 fractional GPU | 图 10、13：小数 GPU 极少；stranded GPU 与 CPU 不足主导多种 request shape | 单个公司、单套配额与硬件组织 | 强 |
| 在线 defragmentation 可在可接受时间内改善整机空闲 | IPC 决策少于 2 分钟；两个月 replay 使未满载节点少 20.2% | 容量数字来自 replay，未报告生产迁移 SLO | 中强 |
| 可抢占 LP 作业能收割在线服务预留 | allocation 68%→93%，Standby 平均收割 90%，LP completion time 低 24% | allocation 不是 SM 利用；依赖 checkpoint 与 Standby | 强 |
| 网络拓扑会显著缩小可用 GPU 池 | 同 ASW all-reduce 高 27%；128/256-GPU fulfill 数明显下降 | 特定 ASI fat-tree 与 ASW 大小 | 强 |
| 软件优化可以改变异构 GPU 的采用 | XPU-A latency 改善 33%/43%，HP 请求增至 2.5× | 少数 Qwen/DeepSeek 案例，长期人工优化投入未计 | 中 |

## 批判性分析

### 论证链条

论文最清楚的结构是“观察—机制”对应：节点/CPU 碎片对应 IPC，在线预留对应 SpotGPU，拓扑碎片对应 ASW 集中放置，GPU 采用不均对应 kernel 优化。Trace 规模让这些问题不是合成出来的，论文也主动把仍未解决的在线推理低 SM、异构拓扑和 CPU 共置干扰列为 open challenges。

但机制证据的强度不一样。SpotGPU 有生产 eviction 和收割数据；IPC 只给决策已上线，却用 trace replay 证明 20.2% 容量结果；拓扑 greedy 只证明单个 job 的规则，没有集群总收益；XPU 是 case study。总结时不能把它们都写成“已在生产证明同等有效”。

### 假设压力测试

IPC 假设迁移可透明进行。make-before-break 要短时保留新旧两份资源，若集群已很满，最需要去碎片时反而最难迁移。40% locked tasks、affinity 和 stateful service 都会切断 ejection chain；随机 partition 还可能把本来可配对的 source/destination 分开。

SpotGPU 假设用户准确标记 Standby，并让 LP 作业定期 checkpoint。若 HP 流量突然回来，平均 13 秒、P95 48 秒的 eviction 可能仍太慢；少于 5% `SIGKILL` 也意味着部分工作无法优雅保存。只按“GPU 数×距 checkpoint 时间”选 victim，会忽略即将完成的 job、恢复数据量和不同 GPU 的实际成本。

异构执行还受到网络反向约束：同 ASW 内 GPU 型号相同，要求 locality 就难以让 prefill/decode 使用不同硬件；跨 ASW 又让 [[KV-Cache]] 传输进入关键路径。论文在 trace 中观察到 PD disaggregation 快速增长，却没有给出解决这个三方冲突的 scheduler。

### 实验可信度

六个月、1,400 万 jobs、15.5 万 GPUs 和 81 个部门的 trace 是很强的规模证据，且作者公开脱敏数据。论文同时报告任务数、GPU-hours、request、allocation 和 SM/显存等多种指标，避免只看一个维度。负面结果也重要：GPU sharing 很少被用、XPU 初始较慢、CPU 共置降低 GPU SM。

外部有效性仍受单一公司限制。ASI 的 8-GPU 节点、ASW 规模、内部价格、HP/LP 规则、用户激励和厂商适配团队都可能不同于其他集群。排除大型 foundation model 预训练后，结论不能直接覆盖最昂贵的专用训练集群。公开 trace 经过脱敏，也很难重建业务 SLO、模型细分和完整 scheduler 决策。

实验还缺少一些关键分母：IPC 没有生产迁移次数、失败率、临时容量和 SLO；SpotGPU 没有 LP 被丢弃的 GPU-hours、checkpoint I/O 和价格收益；XPU 没有工程人月、能耗和更多模型；拓扑策略没有 aggregate cluster result。

### 系统性缺陷

论文的核心效率指标是 allocation ratio，它直接影响容量售卖，却不等于有用工作。在线推理 SM 中位数只有 6%，说明 93% GPU 被 claim 后仍可能大部分时间空闲。若只优化调度分配，系统可能把“未分配浪费”转换成“已分配但低利用浪费”。

IPC、SpotGPU 和拓扑调度分别处理空间、时间和网络约束，但缺少统一目标。IPC 想把任务压紧，SpotGPU 想为 HP 保留可快速收回的空间，拓扑放置想把 GPU 集中在少数 ASW，多厂商阶段拆分又想跨硬件。局部 heuristic 可能互相破坏；论文没有给出同时考虑 allocation、SM、SLO、迁移、抢占和网络的全局策略。

多厂商适配也不是一次性工作。XPU-A 的收益来自人工修改 FlashAttention、Triton compiler 和 serving engine；新模型、多模态、视频生成和新 attention 机制可能重新产生差距。Drop-in API 简化用户代码，却没有消除平台团队维护硬件专用实现的成本。

## 局限与后续工作

- 在公开 trace 中补充脱敏后的 queue、preemption、migration、checkpoint 和 topology decision，方便复现 IPC/SpotGPU 研究。
- 在线 A/B IPC，报告实际腾空节点、迁移成功率、临时双份容量、服务尾延迟和作业失败。
- 把 allocation、SM/HBM/network、energy、useful tokens 和成本一起报告，避免用 93% allocation 代表总体效率。
- 联合优化 IPC、SpotGPU 和 topology placement，明确多目标权重及各策略互相干扰时的优先级。
- 评估 sudden HP reclaim 下的 P99 eviction 与容量恢复，并量化 `SIGKILL`、checkpoint I/O 和 LP 丢失工作。
- 用更多模型、GPU 代际和供应商衡量 XPU 适配的人力、能耗、正确性与长期维护成本。
- 研究 GenAI/DNN GPU 共置和 CPU/GPU 共置的隔离机制，使低 allocation 与低 SM 两类浪费能同时下降。

## 相关

- **相关概念**：GPU 碎片、抢占式调度、[[Serverless]]、[[Disaggregation]]、[[KV-Cache]]、[[PagedAttention]]、[[Flash-Attention]]
- **相关系统**：ASI、Kubernetes、RTP-LLM、[[vLLM]]
- **同会议**：[[OSDI-2026]]
