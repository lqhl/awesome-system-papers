---
type: paper
name: Hetu v2
full_title: "Hetu v2: A General and Scalable Deep Learning System with Hierarchical and Heterogeneous Single Program Multiple Data Annotations"
authors: [Haoyang Li, Fangcheng Fu, Hao Ge, Sheng Lin, Xuanyu Wang, Jiawen Niu, Yuming Zhou, Xupeng Miao, Bin Cui]
venue: OSDI
year: 2026
tags: [distributed-training, spmd, heterogeneous-computing, elastic-training, parallelism]
source_pdf: "[[osdi26-li-haoyang.pdf]]"
source_md: "[[osdi26-li-haoyang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 用分层异构 SPMD 统一表达异构训练

> **原题**：Hetu v2: A General and Scalable Deep Learning System with Hierarchical and Heterogeneous Single Program Multiple Data Annotations

## 一句话总结

Hetu v2 提出 HSPMD，在标准 SPMD annotation 上增加两层非对称分片、分层通信、逐设备 graph specialization 与动态 graph switching，从同一套原语表达异构 GPU、设备故障和变长数据训练。

## 问题与动机

SPMD 的优势是用户只写单设备视角程序，系统从 annotation 推导分片和通信；其隐含前提却是设备与 workload 对称。混用 H800/H20、GPU 故障以及文本长度分布变化都会要求不同设备执行不同计算量或在时间上切换策略。MPMD 能直接写不同程序，但大集群单任务可能生成和管理数千程序；已有 HexiScale、Oobleck、HotSPa 则在对称 SPMD 之上加入场景专用 scheduler，策略表达与执行紧耦合。

作者的核心主张是：异构性应下沉到 declarative primitive，而不是由 scheduler 绕过 SPMD；同时把具体场景归约为两种性质——空间异构要求设备特化，时间异构要求策略重配置。

## 关键观察 / 隐含假设

### 关键观察

- 实际集群常在“子组内同构、子组间异构”的两层结构上运行，适合用 hierarchical annotation 表达。
- 复杂非对称 reshard 仍可优先分解为子组内标准 collective；仅剩余部分需要 batched send-receive。
- 异构策略间的差异可归结为 tensor layout 变化，因而能由 annotation 计算最小 state transfer，而非 checkpoint-restart。
- 静态设备差异、未知故障和可预测长度变化虽然触发方式不同，却可复用 specialization 与 switching 两个 building blocks。

### 隐含假设

- 每个 subgroup 内足够同构，且两层拓扑能覆盖当前训练集群；更深层次异构不值得额外表达复杂度。
- 外部 planner 能给出质量较好的 annotation plan；HSPMD 本身不保证全局最优。
- operator sharding rule、cost profile 与通信拓扑准确，运行时干扰不会频繁推翻计划。
- 故障后仍保留足够 [[Data-Parallelism|DP]] redundancy 恢复参数；为此禁用 [[ZeRO|ZeRO-1]] 会带来明确内存和性能代价。

## 核心方法

### 分层异构 annotation

标准 annotation 由 Device Group（DG）与 Distributed States（DS）组成，DS 表示 Split、Duplicate 或 Partial。HSPMD 将它们提升为 DG Union 与 DS Union：每个 device subgroup 内仍使用普通 SPMD 分片，称 bottom-tier；`HSize` 表示 subgroup 数，`HDim` 表示 subgroup 之间的 top-tier Split/Duplicate/Partial。由此，同一 tensor 可在不同 GPU 子组采用不同 [[Tensor-Parallelism|TP]] degree、replication 或 pipeline placement。

### 分层通信解析

若 top-tier layout 不变，各 subgroup 独立解析为 identity、send-receive、all-reduce、reduce-scatter 或 all-gather。若仅 `HDim` 改变，系统把 shard 切到共同细粒度，再生成 SplitAR/SplitRS/SplitAG；若 collective 条件不满足，则构造 Batched-Send-Receive（BSR）表，记录每个最细 slice 的 owner 与 receiver，优先高带宽 link 并平衡发送负载。启发式复杂度为 `O(pq)`，避免求解 NP-hard generalized assignment。

### 渐进式计算图特化

用户提供含 leaf、Reshard marker 与普通 operator 的逻辑 graph，annotation plan 仅标注关键 tensor。系统先在各 subgroup 内复用标准 SPMD deduction，再逐设备实例化所需 operator 和通信，删除无关分支，形成 device-specific executable graph。这样程序定义仍是单一的，但执行逻辑可非对称。

### 动态计算图切换

新 annotation plan 到达时，HSPMD 在运行中 specialization 新 graph，并比较旧、新 tensor layout 生成 state reshard。系统融合多个 tensor 的 BSR 以均衡 NVLink/[[RDMA|IB]] 流量，然后原子切换 executable graph。异构设备只离线特化一次；故障场景在线规划与切换；混合长度场景预生成多个 graph，运行时按输入选择。

### Planner 边界

系统附带 profiling-based planner，以 ILP、MINLP 或动态规划生成场景计划，但 planner 是可替换模块。最差可退化为 homogeneous annotation，即标准 SPMD；这保证可执行性，却不保证异构性能。

## 实验与结果

Hetu v2 在 16 张 H800 与 32 张 H20 上训练不同规模 Llama，默认 4K context、global batch 64；混合长度实验使用 32 张 H20、32B 模型、100 steps 和 200K-token batch。基线包括 [[DeepSpeed|DeepSpeed]]、[[Megatron|Megatron]]、HexiScale、Oobleck 与 HotSPa。

- 同构设备上各系统表现接近；异构设备上 HSPMD 持续优于基线，原因是能同时改变 pipeline stage 与 TP degree，并用 hierarchical collective/BSR 避免粗粒度 broadcast。
- 故障后，DeepSpeed/Megatron 因对称分片必须丢弃整个 node 并 checkpoint-restart；HSPMD 可继续使用其余 31 张 H20。Oobleck 无需 restart，但固定 pipeline template 限制策略空间。
- 为无 checkpoint 恢复而禁用 ZeRO-1 会让一个配置的 step time 从 6.05 s 增至 6.91 s，约 15% 代价；这是 fault tolerance 的成本，而非 HSPMD 免费消除。
- 混合长度 trace 中 97% sequence 少于 8K；固定 32K-oriented homogeneous strategy 浪费计算。HSPMD 在两个 heterogeneous strategy 间切换，并同时在 pipeline 间按长度平衡，优于 HotSPa 的 homogeneous hot switching。
- C1→C2 重配置中，annotation deduction 开销可忽略，包含 CCL group 创建的 specialization 通常在 10 s 内完成；fused BSR 在总通信量不变时取得最低 switching overhead。
- case study 表明 C2 的 asymmetric rank workload 基本平衡，额外 SplitAR/BSR 开销较小，loss curve 也未显示收敛偏差。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| primitive-level asymmetry 能统一多种异构场景 | 图 15–18 覆盖混合 GPU、故障 trace、CommonCrawl/GitHub 长度变化 | 均为 Llama 训练，尚非跨模型族验证 | 强 |
| 分层 annotation 不牺牲同构性能 | 图 15 中 homogeneous 配置各系统表现接近 | 依赖 Hetu operator/kernel 实现质量 | 强 |
| tensor-level switching 优于 template/restart | 图 16：HSPMD 使用剩余 GPU且重配置更短；图 20：fused BSR 最低 | 故障恢复依赖 DP redundancy，禁用 ZeRO-1 | 强 |
| 空间与时间异构需要同时处理 | 图 17–18：HotSPa 只能切 homogeneous 策略，HSPMD 还可步内负载均衡 | 长度分布具有可预测性并可预生成 plan | 强 |
| 额外通信原语可控 | 图 20：SplitAR/BSR 占比小，specialization 通常少于 10 s | 动态 network contention 未被重点评估 | 强 |
## 批判性分析

### 论证链条

HSPMD 的贡献主要是抽象而非单一 scheduler：它保留 SPMD 单程序接口，又让 tensor layout 原生表达不对称，因而通信推导、执行特化与状态迁移共享同一语义基础。三类场景使用相同原语，确实比逐场景堆机制更具一致性。与多种专用系统比较也验证了 generality 并非只有 API 示例。

### 假设压力测试

- 性能强依赖 scenario-specific planner，论文把最难的 plan quality 问题模块化而非解决；“至少退化到同构策略”只保证正确，不保证实用性能。
- 两层 hierarchy 是工程折中，并无形式证明足以表达未来多级网络、混合 accelerator 或跨 data center 的异构性。
- BSR 只建模 point-to-point bandwidth，未系统处理 shared-link contention；拥塞时 heuristic 可能失准。
- specialization 需要创建通信组且可达秒级，对高频故障或迅速变化的资源池仍偏重。
- 主要评估 Llama；[[MoE|MoE]] expert imbalance 仅在 discussion 中说明可表达，没有实现和实测。
- elastic 配置禁用 ZeRO-1，内存冗余使其与追求最大模型容量的训练目标存在张力。

### 实验可信度

三类异构场景均与专用系统比较，同构配置也控制了实现差异；但数字主要依赖图中读数，planner quality 与动态 network contention 缺少独立消融。

## 局限与后续工作

- **局限**：end-to-end 性能受外部 planner 与两层 topology model 的准确性支配。
- **后续工作**：应扩展 MoE、多模态与多级网络，并形式化验证 graph switching 的状态一致性。

后续可把 topology/contention-aware planner 与 HSPMD 解耦接入，验证 MoE、视觉/多模态和跨代 accelerator；缓存或增量创建通信组以降低 specialization；为 annotation deduction、graph switching 与 failure recovery 建立形式化正确性条件；并研究多层 hierarchy 是否能在不显著扩大搜索空间的情况下覆盖 rack/cluster/region 网络。

## 相关概念

- [[SPMD]]
- [[Distributed-Training]]
- [[Heterogeneous-Computing]]
- [[Elastic-Training]]
- [[Hybrid-Parallelism]]
