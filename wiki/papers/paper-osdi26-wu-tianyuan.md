---
type: paper
name: WEAVE
full_title: Weave: Efficient Co-Scheduling for Disaggregated RL Post-Training
authors: [Tianyuan Wu, Lunxi Cao, Yining Wei, Wei Gao, Yuheng Zhao, Dakai An, Shaopan Xiong, Zhiqiang Lv, Ju Huang, et al.]
venue: OSDI
year: 2026
tags: [rl-post-training, disaggregation, co-scheduling, gpu-cluster, llm-systems]
source_pdf: "[[osdi26-wu-tianyuan.pdf]]"
source_md: "[[osdi26-wu-tianyuan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-24
---

# 面向解耦 RL 后训练的协同调度（OSDI 2026）

> **原题**：Weave: Efficient Co-Scheduling for Disaggregated RL Post-Training

> **一句话总结**：WEAVE 观察到同步、on-policy RL 后训练中 rollout 与 training 的结构性空闲可以由另一作业的活跃阶段填充，于是用带主机内存驻留的 co-execution group、SLO 感知的两层调度和长尾迁移交织多个作业；在 328 张 H20 加 328 张 H800 的生产规模测试床上，相比普通解耦部署降低 1.84× 配置成本，并保持 100% SLO 达成。

## 问题与动机

RL 后训练通常循环执行 rollout、training 和 synchronization。rollout 受 KV cache 和内存带宽限制，training 需要高算力与高速互连，因而生产系统倾向于把两者放在不同 GPU 集群。同步、on-policy 算法又要求每轮阶段严格依赖，导致 rollout 运行时 training 集群空闲，反之亦然。

普通解耦部署可能抵消硬件异构带来的成本优势。论文测量的生产配置中，Solo-D 的成本为 0.94K 美元/小时，高于把所有阶段放在 H800 上的 veRL（0.71K 美元/小时）。WEAVE 不改变 on-policy 依赖关系，而是在集群层面把一个作业的空闲窗口交给另一个作业使用。

## 关键观察 / 隐含假设

- **观察 1：阶段空闲在多租户集群中可互补。** 单个作业的依赖气泡不可消除，但不同作业的 rollout-heavy 与 train-heavy 阶段可以并行执行（图 1）。
  - **依赖假设**：作业之间有足够的阶段互补性，且共享资源后的 slowdown 能落在各自 SLO 内。
  - **可能失效场景**：所有作业都 rollout-heavy，或资源争用集中在同一类 GPU；论文图 3 中两个 rollout-heavy 作业会分别变慢 1.40× 和 1.64×。
- **观察 2：RL 工作负载高度异构且带长尾。** 生产作业覆盖 3B–32B 模型、4K–32K response，阶段耗时约 50–900 秒，多轮交互的 rollout 可为 training 的 3–4 倍（图 2）。少量最大长度 response 会拖慢整个 batch（图 12）。
  - **依赖假设**：最大 token limit 可作为保守的阶段时长上界，运行时又能把少量 straggler 迁移到小规模 GPU 子集。
  - **可能失效场景**：token 上限严重高估实际负载会造成过度保守和较差 packing；响应分布持续漂移并超过预留容量时，静态 placement 可能违反 SLO。
- **观察 3：上下文切换成本决定调度粒度。** 一个作业的模型权重、optimizer state 和执行上下文占用数百 GB；冷启动最高 135 秒，可使端到端吞吐下降 45%（图 4）。主机 DRAM 驻留可将切换延迟降低最多 71.5×，但每个节点通常只能容纳 2–5 个作业。
  - **证据强度**：强。论文给出了不同模型规模的内存表和冷/热启动测量（表 2、图 4）。

## 核心方法

WEAVE 引入 **co-execution group**：一组作业固定共享一对 rollout 与 training 资源池，每个作业被 pin 到确定的节点，使其工作集驻留在节点主机内存。这样全局 NP-hard 的 Job-Shop Scheduling 被拆成组间 placement 和组内执行两个层次。

组间调度器在新作业到达时，先剔除已饱和的组，再尝试三类 placement：直接塞入已有气泡、只扩展 rollout 池、或新建隔离组。它以边际 GPU 配置成本为目标，同时检查每节点内存驻留和所有成员的 SLO。阶段时长按最大 response 长度估计，用保守 admission 保证最坏情况。

组内调度器采用 round-robin meta-iteration，让每个作业各执行一次 rollout 和 training。论文在其未饱和条件下证明该策略使两类资源池的聚合利用率最优：最长作业决定 cycle time，其他作业的阶段填入其依赖气泡。运行时通过 `@weave.phase` 和 `@weave.runtime_hook` 控制阶段许可、状态换入换出及队列推进。

为处理 rollout 长尾，WEAVE 在约 80% response 完成后，把剩余请求集中到少量 GPU，立即释放其余 GPU 给下一个作业。该迁移只发生在同类 rollout GPU 之间，论文认为不会改变学习样本或 reward。模型同步则采用“跨集群 scatter、集群内 broadcast”：跨 20 Gbps Ethernet 只传一份完整模型，随后利用 InfiniBand/NVLink 广播，避免每个 rollout GPU 独立拉取模型。

## 设计取舍

- **保守 admission 换取 SLO 保证**：最大 token 长度简化了随机运行时的在线决策，但可能预留过多容量。
- **节点 pinning 换取热启动**：减少切换成本，却限制了作业跨节点迁移和全局资源重平衡。
- **round-robin 换取可证明性与简单性**：适用于组未饱和且每个作业每轮执行一次的模型；更复杂的优先级或截止时间策略未被比较。
- **静态分组换取低运维开销**：漂移严重时不能自动全局重组。论文建议只停止并重新提交发生显著漂移的作业。

## 实验与结果

- 在相同配置成本下，三个 micro-benchmark 中 WEAVE 相比 Solo-D 的吞吐提升为 1.82×、1.90× 和 1.99×；相比 Gavel+ 为 1.43–1.78×，相比 veRL 为 1.35–1.47×（图 10）。
- 与 solo execution 相比，协同执行的单轮开销为 1.6%–9.8%；相对理想化的零网络开销 H800 共置上界慢 8.0%–18.1%（表 4）。
- 长尾迁移使端到端吞吐提升 1.06×–1.28×，Qwen2.5 7B、14B、32B 的 reward 曲线与 veRL 在测量噪声内一致（图 11、图 12）。
- 拓扑感知同步在 8 H800 → 8 H20 时比 veRL 快 7.87–8.33×，在 16 → 16 GPU 时快 2.62–2.75×（图 13）。
- 回放两周、200 个生产作业时，WEAVE 配置成本为 510 美元/小时，较 Solo-D 降低 1.84×，较 veRL 降低 1.38×，所有作业达到 SLO（图 14）。
- 调度仿真中，WEAVE 相对离线最优的成本开销为 1.01×–1.12%，2,000 个作业的决策时间为 591 ms；暴力搜索在 13 个作业时已超过 5 小时（图 15、表 5）。
- 漂移实验中，静态分组相对动态重组的成本仅高 1.08×–1.11%，SLO 达成率为 95.6%–98.7%；但 370.2 小时 trace 中动态重组本身消耗 32.9 小时迁移和重启时间（图 17、图 18）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 跨作业交织能回收解耦部署的依赖气泡 | 图 10；吞吐提升 1.82–1.99× | 五类 Qwen workload，H20/H800 测试床 | 强 |
| 热启动使细粒度切换可行 | 图 4；切换延迟最多降低 71.5× | 8-GPU 节点，模型规模受表 2 覆盖 | 强 |
| 保守组间调度能同时控制成本与 SLO | 图 14、图 15；生产 trace 成本降低 1.38–1.84×，SLO 100% | 200 作业、SLO 取 1–2 倍 solo runtime | 中 |
| 长尾迁移不改变训练结果 | 图 11；三种模型规模 reward 与 veRL 接近 | 同类 H20 rollout，指定训练配置 | 中 |

## 批判性分析

### 论证链条

论文的主链条较完整：生产阶段异构和同步依赖造成空闲，互补作业可填充空闲，组内 round-robin 在特定负载约束下达到最优，热启动和长尾迁移使该调度能落地。成本结果也同时来自硬件匹配和气泡回收，不能全部归因于调度器。

“最优”主要是组内利用率最优，而不是全局在线成本最优。组间策略仍是带剪枝的在线启发式；其接近最优的结果来自仿真和给定的作业生成分布。离线最优允许在线系统不能使用的重排和重组，因此结果是上界比较，不是可部署基线。

### 假设压力测试

保守 token 上界对极端长尾提供安全边界，却可能导致组容量长期闲置。论文没有量化不同上界估计策略、token limit 与真实分位数之间的成本差异。静态 pinning 还依赖主机 DRAM 足够容纳所有 resident state；更大 optimizer state、不同并行策略或多租户内存争用可能改变组大小。

长尾迁移的语义安全性在同类 GPU、请求可中断且状态可迁移的 rollout 上得到支持。论文未覆盖跨 GPU 代际迁移、环境状态复杂的多轮 agent、迁移时的 checkpoint 一致性和中断恢复尾延迟。

### 实验可信度

实验同时包含生产 trace、真实 H20/H800 测试床、消融、仿真和故障注入，覆盖成本、吞吐、利用率、同步延迟和 reward。限制是生产 trace 来自单个 tenant，微基准主要使用 Qwen 与指定数据集；没有报告公平性、队列等待、优先级、内存压力下 OOM，以及多个租户之间的隔离效果。

### 系统性缺陷

每个作业使用独立 Ray 实例，控制面依赖 Redis，系统实现约 5.2K 行。论文展示了单作业故障隔离，但没有给出 scheduler、Redis、主机 DRAM cache 或跨集群同步链路故障时的恢复协议。固定节点 placement 也可能降低碎片整理和故障域均衡能力。对生产部署而言，profiler 的一次最大长度运行成本、状态缓存容量管理和可观测性开销仍需测量。

## 局限与后续工作

- **局限 1**：静态分组对轻度漂移有效，但在持续严重漂移时只能重提交流水线；其 SLO 达成率在 mixed drift 中降至 95.6%。
- **局限 2**：成本与最优性结论依赖 H20/H800 的价格和带宽比例，不能直接外推到其他 GPU 代际或云定价。
- **后续工作 1**：测量不同 response 长度分位数作为 admission 上界时的成本—SLO 曲线，并比较动态上界更新与当前最大长度策略。
- **后续工作 2**：在多租户优先级、GPU 故障、主机内存不足和跨代 GPU 混用下验证组重构与状态恢复。

## 相关

- **相关概念**：[[Disaggregation]]、[[GPU-Cluster-Scheduling]]、[[LLM-Inference]]、[[Reinforcement-Learning]]
- **同类系统**：[[veRL]]、[[AReaL]]、[[StreamRL]]、[[Rollpacker]]
- **同会议**：[[OSDI-2026]]
