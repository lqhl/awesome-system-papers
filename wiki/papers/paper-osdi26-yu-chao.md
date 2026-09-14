---
type: paper
name: RLinf
full_title: "RLinf: Flexible and Efficient Large-Scale Reinforcement Learning via Macro-to-Micro Flow Transformation"
authors: [Chao Yu, Yuanqing Wang, Zhen Guo, Hao Lin, Si Xu, Hongzhi Zang, Quanlu Zhang, Yongji Wu, Chunyang Zhu, et al.]
venue: OSDI
year: 2026
tags: [reinforcement-learning, rl-training, workflow-scheduling, pipeline-parallelism, heterogeneous-systems]
source_pdf: "[[osdi26-yu-chao.pdf]]"
source_md: "[[osdi26-yu-chao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-26
---

# RLinf：用宏观到微观的流转换调度大规模强化学习（OSDI 2026）

> **原题**：RLinf: Flexible and Efficient Large-Scale Reinforcement Learning via Macro-to-Micro Flow Transformation

> **一句话总结**：现代 RL 工作流同时包含动态 rollout、推理、训练和模拟器，固定的共置或完全流水线模式会在长尾和资源失衡之间取舍；RLinf 以 M2Flow 将用户编写的宏观逻辑流转换为按数据粒度、设备放置和时间复用组织的微观执行流，在 H100 集群上的推理 RL、agentic RL 和 embodied RL 中取得 1.07×–2.43× 的端到端吞吐提升。

## 问题与动机

LLM 时代的 RL 训练把生成、log-prob 推理、奖励或 critic、参数训练、工具调用和环境模拟器放进同一工作流。它们对显存、计算单元、CPU、GPU 图形管线和并行方式的要求不同。生成长度、环境步数和工具调用次数也会变化，因此一个批次经常被少数慢任务拖住。

现有系统通常采用两种执行方式。共置模式让多个阶段轮流占用同一组 GPU，节省设备但暴露 rollout 长尾；分离式流水线把阶段放到不同 GPU 上并发执行，能隐藏长尾，却可能让训练或推理保留未充分利用的设备。论文认为真正需要的是按组件特征组合时间复用、空间流水线和混合调度，同时不要求用户重写工作流代码。

## 关键观察 / 隐含假设

- **观察 1：rollout 的运行时间具有长尾，规模扩大后共置模式的空闲更严重。** 在 8 个节点、每节点 8 张 H100 的 7B 数学 RL 实验中，生成阶段很快只剩少量未完成 response，但这些 response 阻塞后续阶段（图 2）。
  - **依赖假设**：下游推理或训练可以消费部分生成结果，且组件间数据依赖允许细粒度流水线。
  - **可能失效场景**：必须等待完整全局 batch 才能计算的算法，或 response 长度几乎固定时，流水线收益会下降。
- **观察 2：不同组件的计算、显存和并行特性不一致。** 在 embodied RL 中，模拟器 GPU 利用率低于 24%，环境显存随实例数增长；生成阶段随 batch size 近似线性变慢且 GPU 利用率超过 70%，训练又有更大的显存需求（图 3）。因此模拟器适合独立扩展，训练却可能适合与其他组件时间共享。
  - **依赖假设**：可以可靠测量组件在不同设备数和数据粒度下的时间、显存和通信开销。
  - **可能失效场景**：组件性能受网络拥塞、缓存状态或输入内容强烈影响，离线 profiling 的外推可能不再代表实际运行。
- **假设 1：多数 worker 能以不同数据粒度执行。** 弹性流水线依赖 SPMD worker 支持单样本、小批次和大批次处理；训练还需要区分 micro-batch 与 global batch。
  - **证据强度**：中。论文在 LLM rollout、推理、训练和模拟器上实现并评测，但任意新组件是否满足该接口仍需适配。
- **假设 2：训练状态可以在重新调度前安全 checkpoint。** 运行时 profiler 在延迟偏离估计值超过默认 15% 后暂停训练、保存状态并重新部署计划。
  - **证据强度**：中。论文描述了机制和渐进式 response-length drift，但没有报告频繁重调度或节点故障下的恢复开销。

## 核心方法

RLinf 的核心抽象是宏观到微观的流转换（M2Flow）。用户以过程式接口编写 worker 之间的逻辑数据流和同步关系；系统再决定每个 worker 放在哪些设备、以多大数据粒度运行，以及何时与其他 worker 共享设备。worker 通过 `send`、`recv`、`onload` 和 `offload` 暴露通信与资源管理接口，`WorkerGroup` 将同类进程作为一个可异步调用的整体。

空间调度由弹性流水线实现。执行流管理器可以把一个宏观任务切成更小的数据块，让下游在部分结果就绪后启动，也可以合并任务以减少调度和通信开销。这样同一套工作流可以表达不同的流水线粒度，而无需修改逻辑代码。

时间调度由自动 context switching 实现。共享设备的 worker 通过 data channel 上的分布式 `device_lock` 互斥访问 GPU；worker 获得锁后加载资源，执行结束后释放锁并卸载资源。锁利用数据依赖和设备放置信息确定优先级，减少竞争和不必要的加载。该机制使训练、推理和模拟器可以在同一组设备上交替运行。

调度器先对每个组件和不同数据并行规模做 profiling，估计执行时间和显存，再把运行时捕获的工作流图递归切分为子图。每个切分点比较共享设备的时间调度与分离设备的流水线时间，并用动态规划选择计划。对动态 workload，worker 持续记录真实执行时间，偏离阈值后触发重新 profiling 和调度。

通信层自动根据 worker 与数据位置选择 NCCL、cudaIPC 或 Gloo 等后端，并支持包含多个 CPU/GPU buffer 的 Python 对象。data channel 将控制流和数据流解耦，提供 FIFO、GPU 数据卸载和按权重的消费者负载均衡。RLinf 使用 Ray 管理集群和进程，但自行管理跨节点、非连续设备的分配。

## 设计取舍

- **灵活性换取运行时与实现复杂度**：worker 必须实现资源加载/卸载，系统还要维护连接生命周期、设备锁、数据 channel 和动态部署；论文报告实现约 20K 行 Python，核心组件约 5K 行。
- **自动搜索依赖 profiling 模型**：多种执行模式由系统选择，降低人工调参，但多项式外推和流水线时间模型可能在输入分布变化、通信拥塞或非平稳 workload 下产生误判。
- **时间复用节省显存但引入迁移开销**：onload/offload、参数重分片和 checkpoint 会增加延迟；当组件可以长期并发运行时，过度共置反而会损失吞吐。
- **故障处理偏保守**：worker 失败时 RLinf 停止整个作业，从最新 checkpoint 重启，而不是只恢复失败组件。这样保护了依赖一致性，但会放大故障恢复时间。

## 实验与结果

- 在 32 节点、每节点 8 张 H100-80GB 的集群上，Qwen2.5 的 GRPO 实验中，RLinf 的 temporal 模式相对 veRL 在 1.5B、7B 和 32B 设置取得 1.10×–1.58× 加速；长序列（最大 28672）下，RLinf 的显存管理允许更大的 KV cache（图 8、图 9）。
- Qwen2.5 PPO 实验中，RLinf-Spatial 相对 veRL 在 1.5B 设置提升 35.0%–69.6%，在 7B 设置提升 38.7%–60.7%；相对 RLinf-Temporal，7B 提升 19.0%–44.8%（图 10、图 11）。
- 对 Qwen3-30B-A3B 的 GRPO，RLinf-Spatial 在 32 和 64 GPU 上相对 Slime-Colocate 分别快 31.2% 和 7.2%；128 GPU 时，空间模式因流水线重叠不足而落后，说明执行模式确实依赖 workload（图 12、图 13）。
- Search-R1 风格 agentic RL 在单节点 8 张 H100 上达到 67.3 requests/s，而官方 veRL 实现为 30.4 requests/s，即 2.2× 吞吐（§5.1.2）。
- OpenVLA 的 ManiSkill 实验中，RLinf-Hybrid 相对 temporal 模式提升 52.2%–69.1%，相对 spatial 模式提升 60.7%–87.2%；LIBERO 中 temporal 模式相对 SimpleVLA-RL 提升 37.8%、42.6% 和 143.4%（8、16、32 GPU，图 14）。
- 调度预测误差在 temporal 模式低于 2%，空间流水线低于 5%（图 16）；在 1.5B GRPO、128 GPU 的噪声实验中，rollout 时间低估约 29% 或训练时间高估约 48% 以内仍能保持最优放置。论文正文同时声称 8–1024 GPU 的搜索时间为 7×10⁻⁴–5.98 秒，但图 16(b) 的扩展实验还报告 4096 GPU 下低于 60 秒，二者对应的实验范围不同。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| M2Flow 可以在不改工作流逻辑的情况下探索时间、空间和混合执行 | worker 接口、data channel 与三种执行流示例（图 5–7）；同一 workflow runner 可被 temporal/spatial 调度 | 主要是论文实现支持的 RL worker；新组件仍需适配资源接口 | 强 |
| 自动选择执行模式能提高端到端吞吐 | Qwen2.5、Qwen3、Search-R1、ManiSkill 和 LIBERO 的吞吐对比（图 8、10、12、14） | H100 集群、指定模型和公开 benchmark；未覆盖更广泛生产 trace | 强 |
| profiling-guided scheduler 的估计足以指导放置 | temporal 误差低于 2%，spatial 误差低于 5%；噪声容忍实验（图 16、17） | 少于十节点的典型工作流，且模型和集群配置有限 | 中 |
| RLinf 的吞吐提升不破坏下游训练效果 | AIME、GPQA、ManiSkill、LIBERO 的模型分数（表 2–4） | 结果依赖训练配方、数据和 RL 超参数；不是对算法质量的独立比较 | 中 |

## 批判性分析

### 论证链条

论文的主链条较完整：RL 组件的资源和时延特征不同，固定执行模式会浪费资源；M2Flow 暴露更大的空间—时间调度空间；弹性流水线、context switching 和 profiling scheduler 将该空间变成可执行计划；多类 workload 的结果显示不同模式确实各有优劣。Qwen3 在 128 GPU 上空间模式变慢、LIBERO 上 hybrid 逊于 temporal，是对“总是流水线最好”的反例，也支持按 workload 选择模式。

但“最优”主要指给定资源边界、估计模型和候选执行模式下的最优。调度器没有显式优化 GPU 成本、能耗、网络拥塞、恢复时间或多租户公平性，因此不能把吞吐最优外推成部署总成本最优。

### 假设压力测试

M2Flow 依赖 worker 能以可控粒度暂停、恢复和迁移资源。对于有长时间内部状态、不可抢占模拟器或强耦合通信的组件，`onload/offload` 可能不够表达一致的切换语义。论文展示了 PPO、GRPO、agentic 和 embodied 工作流，但没有给出包含大量并发工具请求、跨租户抢占或高频重调度的实验。

调度模型用多项式外推组件时间。图 16 显示 response 长度变化已经使空间模式误差高于 temporal；更强的输入漂移、网络抖动或混合硬件可能让误差改变模式排序。运行时重调度通过 checkpoint 避免状态不一致，但会制造全局暂停，论文未量化这种暂停在高频漂移场景下的成本。

### 实验可信度

基线使用相同的 SGLang 和 Megatron 配置，结果在 warm-up 后 10 次迭代取平均，且覆盖多个模型规模和集群规模，这是公平性的有利证据。消融式比较 temporal、spatial 和 hybrid 也能说明模式选择的影响。

边界在于实验集中于 H100、少数公开模型和特定 RL 数据集。论文没有给出端到端美元成本、能耗、P99 延迟、通信流量、worker 加载开销的完整拆分，也没有与所有支持异步更新的系统在同一 workload 上比较。模型分数用于确认训练正确，但不能单独证明吞吐提升在等计算预算下普遍带来更好的样本效率。

### 系统性缺陷

- **恢复**：worker 故障会停止整个作业，恢复粒度较粗；论文未评估大规模节点故障的恢复时间和 checkpoint 存储压力。
- **运维**：动态设备分配、资源卸载和自动重调度增加了排障状态，论文未报告可观测性工具或线上调试成本。
- **隔离**：论文讨论了单作业内的 device lock 和集群管理器分配边界，但未评估多个作业竞争共享网络、CPU 或存储时的干扰。
- **正确性**：异步 worker、循环数据流和权重同步需要明确版本语义；论文说明了 workflow 支持，但没有提供跨故障、重复消费或延迟权重更新的系统化正确性测试。

## 局限与后续工作

- **局限 1**：调度目标主要是端到端吞吐，未联合考虑成本、能耗、P99、故障恢复和多租户公平性。
- **局限 2**：profiling 采用离线测量和函数外推，动态输入和网络状态变化可能让候选模式排序失真。
- **局限 3**：故障处理停止整个训练作业，无法证明在长时间、多节点 RL 训练中具有低恢复成本。
- **后续工作 1**：在真实 response-length 漂移 trace 上测量重调度频率、checkpoint 大小、暂停时间和最终吞吐，并与不重调度的静态计划比较。
- **后续工作 2**：把成本、能耗和 P99 纳入调度目标，在异构 GPU/NPU 与多租户干扰下验证 Pareto 前沿，而不只报告 H100 吞吐。
- **后续工作 3**：为 worker 状态、channel 消费和权重版本建立故障注入测试，验证部分恢复、重复消费和延迟更新的正确性。

## 相关

- **相关概念**：[[Ray]]、[[Pipeline Parallelism]]、[[KV-Cache]]、[[LLM Reinforcement Learning]]
- **同类系统**：[[veRL]]、[[Slime]]、[[AReaL]]
- **同会议**：[[OSDI-2026]]
