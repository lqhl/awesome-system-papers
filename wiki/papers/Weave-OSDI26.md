---
type: paper
name: Weave
full_title: "Weave: Efficient Co-Scheduling for Disaggregated RL Post-Training"
authors: [Tianyuan Wu, Lunxi Cao, Yining Wei, Wei Gao, Yuheng Zhao, Dakai An, Shaopan Xiong, Zhiqiang Lv, Ju Huang, Siran Yang, Yinghao Yu, Jiamang Wang, Lin Qu, Wei Wang]
venue: OSDI
year: 2026
tags: [rl-post-training, gpu-scheduling, disaggregation, cluster-scheduling, model-synchronization]
source_pdf: "[[osdi26-wu-tianyuan.pdf]]"
source_md: "[[osdi26-wu-tianyuan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向解耦式 RL 后训练的高效协同调度（OSDI 2026）

> **原题**：Weave: Efficient Co-Scheduling for Disaggregated RL Post-Training

> **一句话总结**：WEAVE 抓住同步 on-policy RL 中 rollout 与 training 两个 GPU 池交替空闲的结构性气泡，把不同作业的互补阶段编进固定的协同执行组，并用 host DRAM 热启动、长尾迁移和分层模型同步控制切换成本；两周、200 作业的生产 trace 回放中，它以每小时 510 美元完成负载，成本相对专用解耦 Solo-D 改善 1.84 倍、相对共置 veRL 改善 1.38 倍，并在这组名义回放中满足全部 SLO。

## 问题与动机

同步 on-policy RL 后训练反复执行 rollout、training 和 model synchronization。Rollout 以生成和 [[KV-Cache]] 访问为主，通常受显存容量与带宽限制；training 更需要算力和高速互连。生产系统因而把两阶段做 [[Disaggregation|解耦]]：rollout 放到便宜、适合推理的 H20，training 放到昂贵、算力强的 H800。论文测试床的 H800 单价是 H20 的 2.85 倍，这种硬件匹配本应降低成本（表 1）。

同步依赖却会制造“dependency bubble”：rollout 时 training 池空闲，training 时 rollout 池空闲。论文回放中，给每个作业独占两类资源的 Solo-D 反而需约 940 美元/小时，高于全部阶段共置 H800 的 veRL（约 710 美元/小时）。异步、off-policy 系统能让同一作业内阶段重叠，但会引入样本陈旧；WEAVE 的目标是在不改变同步 on-policy 语义的前提下，用其他作业填这些气泡。

跨作业复用并不是普通的 GPU time sharing。生产 workload 的模型大小为 3B–32B、最大响应长度为 4K–32K，阶段时长从 50 秒到 900 秒以上；agentic 任务的 rollout 可比 training 长 3–4 倍（图 2）。随意把两个 rollout-heavy 作业放在一起，会把它们分别拖慢 1.40 倍和 1.64 倍（图 3）。同时，一个 8-GPU 节点上的模型权重、优化器和执行状态要占数百 GB，冷启动最长 135.8 秒，足以损失 45% 训练吞吐（图 4）。

## 关键观察 / 隐含假设

- **观察 1：单个同步作业无法消除的气泡，在多作业层面是可复用容量。** 当作业 A rollout 时让作业 B training，两个异构池可以同时工作，而每个作业内仍保持 rollout→training→sync 的顺序（图 1）。
  - **依赖假设**：系统中持续有多个阶段比例不同的作业；若只有一个作业，或所有作业同时 rollout-heavy，互补空间会显著减少。
  - **可能失效场景**：完全异步 RL 已经在作业内连续重叠 rollout 和 training，没有结构性气泡，WEAVE 也明确不适用（§7）。
- **观察 2：缓存到 host DRAM 后，状态切换才足够快。** 7B–70B 的 rollout 热启动约为 0.9–1.9 秒，training 热启动约为 4.1–5.9 秒；相比最长 135.8 秒的冷启动，最多快 71.5 倍（图 4）。
  - **依赖假设**：每个组内所有作业的工作集能同时驻留在节点的 1–2 TB host memory 中。实测单个 actor 常需数百 GB，所以一个节点通常只能留 2–5 个作业。
  - **可能失效场景**：更大模型、更多 optimizer state、host memory oversubscription 或 [[NUMA|NUMA]]/[[PCIe|PCIe]] 带宽拥塞会压缩组大小并放大切换成本。
- **观察 3：rollout 的少数长响应会让大部分 GPU 提前空闲。** WEAVE 在约 80% 响应结束后，把剩余请求收拢到少量同型号 GPU，使下一作业能先占用释放出的 GPU（图 7、图 12）。
  - **依赖假设**：请求能安全迁移，且迁移只发生在同构设备之间。论文只验证 H20 到 H20，不支持把活动请求跨异构 GPU 迁移。
- **假设 1：按最大 token 长度做一次 profile 可以作为保守 admission bound。** 组间调度用这个上界模拟各成员的 slowdown，再决定是否满足 SLO。
  - **证据强度**：中。它覆盖响应长度随机性，但 GPU 干扰、网络抖动、reward 环节变化和运行期 workload drift 未必都由最大 token 长度上界控制。
- **假设 2：SLO 可以表达为相对单独运行的迭代 slowdown。** 这让 admission 能用一次 meta-iteration 仿真检查。
  - **证据强度**：中。论文评测中的 SLO 多为从 `(1, 2)` 均匀采样，而不是 trace 中真实记录的用户目标；deadline、公平性和优先级没有进入模型。

## 核心方法

WEAVE 的核心抽象是协同执行组（co-execution group）。每个组拥有一组 rollout GPU 和一组 training GPU，成员作业被固定到具体节点；不同组互不共享节点。固定放置让模型状态留在这些节点的 host DRAM，也把全局 NP-hard 调度问题拆成多个小组内问题。代价是节点内存成为 admission 的硬约束（§4.1）。

组间调度器在新作业到达时最小化新增的每小时 GPU 成本。它依次考虑三类方案：直接塞进现有气泡、只扩容 rollout 资源、或新建隔离组。每个候选都必须同时满足节点 host memory 容量，以及新旧所有成员的相对 slowdown SLO。调度器先剪掉瓶颈资源总负载已经达到自然 cycle 的饱和组，再对剩余组模拟一轮执行；因此组大小较小时，搜索随活跃组数近似线性增长（算法 1、图 5–6）。

组内采用循环 round-robin：每个 meta-iteration 中，每个作业恰好执行一次 rollout 和一次 training。论文的 Theorem 1 只对“未饱和或恰好饱和、阶段时长按给定值、每个作业每轮执行一次”的组证明利用率最优；它不是对任意随机 Job-Shop 调度的无条件最优证明。运行时若 rollout 出现长尾，调度器触发请求迁移，让上一作业的尾部与下一作业的头部重叠（§4.3）。

系统层面，用户用 `@weave.phase` 标注 rollout、training 和 sync。阶段结束时，WEAVE 把数据状态卸载到 host DRAM，却不销毁进程，而是保留 [[NCCL]] communicator 和环境句柄后休眠；下一次只需把已缓存状态装回 GPU。`@weave.runtime_hook` 汇报生成进度、推进各节点 FIFO，并触发长尾迁移。实现基于 ROLL，约 5.2K 行代码，控制器用 Python，placement search 用 C++（图 8、§5.1）。

模型同步使用两级拓扑。训练侧把参数切成不重复的 shard，每张训练 GPU 只向对应 rollout GPU 发送一个 shard，因此慢速跨集群 20 Gbps Ethernet 上总共只经过一份完整模型；收到后再通过集群内 400 Gbps [[RDMA|InfiniBand]]/NVLink 广播。它避免 veRL 的 flat collective 让每个 rollout worker 都跨慢链路获取完整副本（图 9、§5.2）。

故障隔离依赖每作业独立 Ray 实例和 Redis 控制通道。某作业失败后，组内其他作业继续；恢复时把它当新 arrival 重新 admission，并从最后完成的 iteration checkpoint 恢复。严重 workload drift 也不做全局在线重组，而由运维停止并重新提交单个作业（§5.3）。

## 设计取舍

- **保守 admission 换 SLO 安全余量**：用最大 token 长度估算能避免把随机短 rollout 当成稳定容量，但可能过度预留。长尾迁移负责在运行时取回这部分未用容量。
- **固定组与状态驻留换快速切换**：热启动把切换降到秒级，却把 host DRAM 变成稀缺资源，并限制了作业在组间自由移动。
- **简单 round-robin 换可证明和可执行性**：在筛选后的组上容易仿真，也有条件最优性；阶段漂移后，这些前提可能不再成立。
- **静态 placement 换稳定运行**：避免频繁全局重组和数百秒迁移，但持续漂移时会牺牲 SLO。论文的 fallback 是停掉并重交作业，不是无缝调整。
- **边界条件**：同步 on-policy 或仍保留 rollout/training 气泡的一步 off-policy 负载最合适；完全异步训练、单作业集群或状态不能驻留 host memory 时收益很小。

## 实验与结果

- **测试床与 workload**：两个地理分离的集群分别使用 H800 training GPU 和 H20 rollout GPU，集群内 400 Gbps InfiniBand，跨集群仅 20 Gbps Ethernet；总容量各 328 张 GPU。微基准使用 Qwen/Qwen2.5/Qwen3 的 7B–32B、DeepMath-103K 和 Math-Orz57K，覆盖单轮和多轮任务（§6.1、表 3）。
- **组内协同执行**：在相同每小时硬件成本下，时间复用、rollout-heavy 复用和空间复用三组微基准中，WEAVE 相对 Solo-D 的训练吞吐分别提高 1.82、1.90 和 1.99 倍；相对 Gavel+ 为 1.43–1.78 倍，相对 veRL 为 1.35–1.47 倍。单作业相对 solo 的干扰 slowdown 为 1.6%–9.8%（图 10、表 4）。
- **机制消融**：长尾迁移让端到端吞吐提高 1.06–1.28 倍；Qwen2.5 7B、14B、32B 的平均 reward 曲线与无迁移 veRL 在测量噪声内一致。拓扑感知同步在 8 H800→8 H20 时比 veRL 快 7.87–8.33 倍，在 16→16 时快 2.62–2.75 倍（图 11–13）。
- **两周 trace 回放**：来自单个 tenant 的 200 个生产作业，模型 3B–32B、响应上限 4K–32K、平均作业时长 27.9 小时；SLO 是实验者从 `(1, 2)` 均匀采样。WEAVE 以 510 美元/小时、总计 188.8K 美元完成全部作业，名义回放中 SLO attainment 为 100%；相对 Solo-D 和 veRL 的成本分别改善 1.84 和 1.38 倍（图 14）。
- **资源来源**：WEAVE 相对 Solo-D 把 rollout 和 training 气泡分别减少 24.4% 和 43.1%。其实际峰值是 216 张 H20 与 152 张 H800，而不是同时使用测试床的 328+328；Solo-D 需要 328 张 H20 和 328 张 H800，veRL 峰值需 328 张 H800（图 14）。
- **调度与稳健性**：在 300 作业、580 小时 Philly arrival trace 加合成 RL 作业画像的模拟中，WEAVE 成本为离线穷举最优的 1.01–1.12 倍，并满足全部合成 SLO；2,000 个并发作业时一次 decision 为 591 ms。加入 increasing/decreasing/mixed drift 后，静态 WEAVE 相对每小时理想重组基线的成本为 1.11/1.10/1.08 倍，但 SLO attainment 降到 98.6%/98.7%/95.6%（图 15、图 17、表 5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 跨作业阶段编排能显著回收解耦气泡 | 图 10、表 4 | H20/H800 双集群；三组 7B–32B 微基准 | 强 |
| WEAVE 能以更少 GPU 完成生产 trace 回放 | 图 14、§6.4 | 单 tenant、200 作业、两周 replay；实验生成 SLO | 强 |
| 长尾迁移不破坏 RL 学习结果 | 图 11–12 | Qwen2.5 7B/14B/32B；平均 reward 曲线 | 中 |
| 组间调度接近最优且可扩展 | 图 15、表 5 | Philly arrival 加合成 RL profile；离线最优仅适用于小规模比较 | 中 |
| 系统能承受 workload drift | 图 17–18 | 基于生产模式合成的三类 drift；SLO 仅 95.6%–98.7% | 中 |

## 批判性分析

### 论证链条

论文从生产 workload 的阶段不平衡与冷启动测量出发，用 co-execution group 同时回应组合爆炸和状态驻留，再用组间 admission、组内 round-robin、尾部迁移处理三个挑战，设计映射很清楚。微基准和 trace replay 也确实展示了利用率转化为成本。不过，“100% SLO”只成立于静态名义回放和模拟设置；同一论文的 drift 实验已经降到 95.6%–98.7%。因此不能把它外推成生产中无条件的 SLO 保证。

### 假设压力测试

核心机会要求集群中有足够多、阶段互补的作业。低负载时没有别的 job 填气泡，极端 rollout-heavy workload 则仍会留下 rollout 瓶颈。保守 profile 假设最大 token 长度能上界主要随机性，但 reward service、数据处理、网络抖动或训练 kernel 变化可能绕过这个上界。Host DRAM residency 对更大模型尤其紧张；状态超过内存后，系统会退回慢速加载或拒绝 packing。Theorem 1 的最优性依赖未饱和、固定时长等条件，不能覆盖实际长尾和长期 drift。

### 实验可信度

异构 328+328 GPU 容量、真实硬件成本和跨地域 20 Gbps 链路使系统证据很强；微基准、两周回放、模拟、消融和故障注入也覆盖较完整。但大规模结果是 trace replay，不是在线生产调度；trace 只来自一个 tenant，SLO 由均匀分布生成。Philly 实验只采用 arrival 和 duration，RL 阶段比例是合成的。Reward 验证覆盖三个 Qwen2.5 模型，但没有完整比较最终 accuracy、方差或更多 RL 算法。价格优势也依赖论文中的 H800/H20 单价和资源供给关系。

### 系统性缺陷

WEAVE 要求用户标注 phase、保留每作业 Ray/NCCL 控制状态、预留大量 host DRAM，并维护跨集群同步通道，运维复杂度不低。SLO 模型只看相对 iteration slowdown，没有 tenant fairness、priority、deadline 或 starvation 目标。故障实验是手动 kill 后再手动恢复和 resubmit，只证明隔离与恢复路径可工作，没有报告自动检测时间、MTTR、checkpoint 丢失窗口或 scheduler 自身故障。严重 drift 的处理方式是停机重交，可能影响长作业可用性；论文也未讨论 host-memory pressure 下的 eviction policy 和数据安全隔离。

## 局限与后续工作

- **局限 1**：只适用于存在 rollout/training 结构性气泡的同步或有限 off-policy RL；完全异步系统没有可回收气泡。
- **局限 2**：生产回放来自单 tenant，SLO 是合成的相对 slowdown，未覆盖公平、优先级和真实 deadline。
- **局限 3**：状态驻留会消耗数百 GB host DRAM，组大小和收益随模型状态、NUMA 与 PCIe 拥塞而变化。
- **后续工作 1**：在在线多租户集群中记录真实 SLO、arrival 和 drift，分别报告 attainment、JCT、公平性与每 tenant 成本。
- **后续工作 2**：实现单作业增量 re-placement，比较它和“停机重交”、全局重组在迁移时间、SLO 违约和额外成本上的阈值。
- **后续工作 3**：对 Ray、Redis、scheduler、host-state 损坏和跨集群断链分别做自动故障注入，报告检测时间、MTTR 与未完成 iteration 损失。

## 相关

- **相关概念**：[[Disaggregation]]、[[GPU-Scheduling]]、[[RL-Post-Training]]、[[Warm-Start]]、[[Model-Synchronization]]
- **相关系统**：[[veRL]]、[[ROLL]]、[[AReaL]]、[[AsyncFlow]]
- **基础设施**：[[NCCL]]、[[Ray]]、[[Redis]]
- **同会议**：[[OSDI-2026]]
