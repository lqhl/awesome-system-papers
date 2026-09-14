---
type: paper
name: DynaRL
full_title: "DynaRL: Flexible and Dynamic Scheduling of Large-Scale Reinforcement Learning Training"
authors: [Yuanqing Wang, Hao Lin, Junhao Hu, Chunyang Zhu, Quanlu Zhang, Zhen Guo, Yuchen Zhang, Xu Fu, Si Xu, Bo Dai, Zixiao Huang, Chao Yu, Boxun Li, Guohao Dai, Zhi Yang, Yu Wang]
venue: OSDI
year: 2026
tags: [reinforcement-learning, dynamic-scheduling, llm-training, agentic-rl, resource-migration]
source_pdf: "[[osdi26-wang-yuanqing.pdf]]"
source_md: "[[osdi26-wang-yuanqing]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-14
---

# 大规模强化学习训练的灵活动态调度（OSDI 2026）

> **原题**：DynaRL: Flexible and Dynamic Scheduling of Large-Scale Reinforcement Learning Training

> **一句话总结**：现代 RL 的 rollout 长尾和多轮工具调用会让静态 GPU 划分浪费最多 60% 的计算；DynaRL 用动态超图、可迁移 WorkerGroup 和多轮感知请求调度在运行时重分配资源，在数学推理和 agentic RL 上取得最高 1.98× 吞吐提升，在线调度与迁移开销低于 1%。

## 问题与动机

大模型 RL 训练同时包含 rollout、推理、工具调用和策略训练。rollout 长度呈重尾分布，多轮 agent 还会等待搜索、Python 或 Lean 等外部工具。一个阶段的尾部请求可能使整组 GPU 继续运行，而其他阶段已经没有足够工作可做。

verl 和 RLinf 等系统通常在训练开始前静态划分资源，或按阶段串行使用集群。这种安排无法匹配每个阶段随时间变化的负载。论文在 1.5B 数学推理任务中观察到，约 95% 的查询在最大 decode 时间的约 60% 内完成，但少数长请求会使几乎所有 inference engine 继续占用资源，计算浪费最高达 60%（图 2、图 3）。

## 关键观察 / 隐含假设

- **观察 1：rollout 的有效并行度会随轨迹完成而下降。** 中段只剩少于 30% 的查询未完成时，几乎所有 engine 仍处于运行状态（图 3）。
  - **依赖假设**：可以在不会破坏语义的中断点缩小 rollout WorkerGroup。
  - **可能失效场景**：请求长度更均匀、阶段之间强同步，或迁移代价接近剩余计算时间时，回收 GPU 的收益会变小。
- **观察 2：多轮 agent 的后续轮次通常更短，FIFO 会损害 KV cache 复用。** 后续轮次若不能及时回到原 Worker，SGLang 中已完成查询的 KV cache 可能被驱逐，导致重复 prefill（图 4、图 5）。
  - **依赖假设**：同一 episode 的后续请求在短时间内返回，且 KV cache 局部性值得优先于严格 FIFO。
  - **可能失效场景**：后续轮次同样很长、工具延迟极高，或 KV cache 足够大而几乎不驱逐时，优先级调度收益会下降。
- **假设 1：训练阶段存在可安全迁移的状态边界。** Megatron-LM 的参数、optimizer state 和 gradient buffer 能在新 rank 完整接收后切换。
  - **证据强度**：强；论文给出 create-before-destroy、分布式 barrier 和回滚流程，并验证 reward 曲线与静态配置接近（图 16）。

## 核心方法

DynaRL 把 RL pipeline 表示为动态超图。HyperNode 对应一个 WorkerGroup，记录组件类型、依赖、中断属性、Worker 资源和利用率；HyperEdge 记录数据流、处理进度及 Worker affinity。Global Scheduler 只接收按 WorkerGroup 聚合的运行信号，因而可以在不理解每个组件内部实现的情况下决定资源分配。

系统提供统一的 `MigrationManager` 接口，并按状态和迁移成本选择三种策略。轻量组件可采用重启迁移；无共享状态的 inference 使用 WorkloadMigration，暂停待处理任务并重新分发；Megatron-LM 使用 p2pMigration，在销毁旧 Worker 前启动新 Worker、传输参数和 optimizer state、重建通信组。迁移失败时保留旧 Worker，避免训练状态处于半切换状态。

每个 WorkerGroup 内运行本地 DataRouter。它在数据上附加 episode 的 affinity 和轮次状态，并在接收端改变请求顺序。agentic RL 中，请求优先级由已完成工具调用数决定，同轮次再按 KV cache 前缀长度排序（算法 2）。这同时减少 cache 重填和末尾短请求造成的拖尾。

调度器把组件分为吞吐随资源近似线性增长的 static component，以及资源收益递减、负载会自然收缩的 dynamic component。若超过阈值比例的 Worker 在持续窗口内低利用率，系统生成多个缩容候选，预测 donor 损失和全局吞吐，再选择预测收益最高的方案（算法 1）。

## 设计取舍

- **资源收益换迁移成本**：更激进地缩减 rollout 可让 trainer 更早扩容，但会增加状态传输和重新分发开销。论文用持续低利用率窗口和多候选预测抑制频繁震荡。
- **优先级换 FIFO 公平性**：后续轮次优先可能让新 episode 等待。论文依赖后续轮次较短的任务结构，并声称在该规律不存在时退化到接近 FIFO。
- **统一接口换组件适配工作**：调度策略保持通用，但 rollout、inference、tool agent 和 trainer 仍需分别实现迁移逻辑，Megatron 的重分片和通信组重建也增加了工程复杂度。

## 实验与结果

- 在 64/128 张 H100、1.5B/7B/32B 模型和 AReaLboba-Data 上，DynaRL 相比 verl 或 RLinf 的数学推理 RLHF token 吞吐提升 1.27×–1.98×；128 GPU、32B 配置达到相对 verl 的 1.98×、相对 RLinf 的 1.40×（图 11）。
- 多轮 agentic RL 在 rstar2-agent 上相对 RLinf 提升 1.06×–1.53×；加入优先级请求调度后提升 1.27×–1.64×（图 12）。
- 调度决策在 200 ms 内完成，每次重分配耗时 0.5–5 s，在线调度总开销低于 0.5%，论文汇总为低于 1%（§7.4）。
- trainer 迁移即使在 32B/128 GPU 下也只占端到端延迟少于 0.5%；rollout 迁移在数秒内完成（图 14）。
- 1.5B 数学任务中，`U_low` 在 0.1–0.3 时吞吐距峰值约 1.5%；过低或过高分别使吞吐下降 19.7% 和 14.1%（图 15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 动态资源重分配能缓解 RL 阶段间的尾部不平衡 | 图 3、图 11、图 13 | H100，64/128 GPU，1.5B–32B，数学推理 RL | 强 |
| 多轮感知请求顺序能减少 agentic RL 的 KV cache 浪费 | 图 5、图 12 | rstar2-agent，SGLang，1.5B–32B | 中 |
| 迁移不会改变 RL 学习语义 | §7.6、图 16 | 1.5B、64 GPU 数学推理任务；仅展示 reward 曲线 | 中 |

## 批判性分析

### 论证链条

论文的链条在已测工作负载内是闭合的：长尾造成 donor，超图聚合信号识别 donor，迁移释放 GPU，trainer 与 rollout 重叠缩短关键路径。吞吐目标被近似为同步阶段吞吐的最小值，但真实 pipeline 含有异步工具调用和数据依赖；预测模型如何处理这些相关性，正文没有给出误差分布。

### 假设压力测试

调度器依赖动态组件具有凹收益曲线，且 profile 与在线回归能预测缩容代价。模型、提示长度、工具延迟或租户混合变化更剧烈时，静态 profile 可能失准。优先级规则也把“轮次越后越短”作为主要经验，论文虽声称可优雅退化，但没有覆盖违反该规律的系统实验。

### 实验可信度

实验覆盖 1.5B–32B 和 64/128 H100，包含数学推理与多轮 agentic RL，并报告吞吐、迁移和参数敏感性。agentic RL 只与 RLinf 比较，因为 verl 的 FSDP 路径较慢；这使该部分的基线覆盖有限。正确性验证主要是 reward 曲线相似，而非不同随机种子下的统计检验或 checkpoint bit-level 对照。

### 系统性缺陷

迁移需要组件合作实现，且 p2p 状态传输会占用网络带宽。论文未讨论多个 WorkerGroup 同时申请迁移、GPU 故障恢复期间的调度公平性、跨租户隔离和生产环境中的资源碎片。集中式 scheduler 只处理聚合信号，降低了复杂度，但也可能丢失单 Worker 热点和网络拓扑信息。

## 局限与后续工作

- **局限 1**：主要评测集中在单一 128 GPU H100 集群和两类 RL 工作负载；结论对异构 GPU、跨地域网络和更长工具链的外推仍待测量。
- **局限 2**：吞吐预测器的误差、错误决策后的恢复次数和迁移失败率没有单独报告。
- **后续工作 1**：在打乱多轮响应长度规律、扩大工具延迟分布并引入异构 GPU 后，测量优先级策略的收益和 tail latency。
- **后续工作 2**：记录预测吞吐与实际吞吐的逐次误差，比较集中式超图调度与拓扑感知、分布式调度在 256 GPU 以上的控制开销。

## 相关

- **相关概念**：[[KV-Cache]]、[[Dynamic Scheduling]]、[[Resource Migration]]
- **同类系统**：[[RLinf]]、[[SGLang]]、[[Megatron-LM]]
- **同会议**：[[OSDI-2026]]
- **对比**：[[RLHFuse-vs-DynaRL]]
