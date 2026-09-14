---
type: paper
name: Seer
full_title: "Seer: Online Context Learning for Fast Synchronous LLM Reinforcement Learning"
authors: [Ruoyu Qin, Weiran He, Weixiao Huang, Yangkun Zhang, Yikai Zhao, et al.]
venue: OSDI
year: 2026
tags: [llm-reinforcement-learning, synchronous-rl, rollout, speculative-decoding, kv-cache, scheduling]
source_pdf: "[[osdi26-qin.pdf]]"
source_md: "[[osdi26-qin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向快速同步式 LLM 强化学习的在线上下文学习（OSDI 2026）

> **原题**：Seer: Online Context Learning for Fast Synchronous LLM Reinforcement Learning

> **一句话总结**：SEER 观察到 GRPO 类算法同一 prompt 的 8–16 个 response 在长度和 token 模式上高度相关，于是用分块 rollout、上下文感知调度和分组投机解码处理 KV cache 膨胀与长尾；在 256 张 H800 上相对 veRL 将 rollout 吞吐提高 44–104%（最高 2.04×），长尾时间降低 72–94%，同时保持严格同步语义。

## 问题与动机

同步式 LLM 强化学习包含 rollout、奖励计算、经验构造、训练和权重更新。论文测得 rollout 占三类生产工作负载总迭代时间的 63–87%（表 1）。长 CoT 生成使输出长度从数百 token 延伸到 96k token，KV cache 随生成过程持续增长；若保持高并发，容易触发驱逐和 re-prefill，若过早降低并发，GPU 又会长期空闲。

请求长度的重尾分布还会造成同步 rollout 的尾部阶段：大多数请求已经完成，少量长请求却继续占用部分实例。异步或非严格同步方案能隐藏这段尾部，但会引入 off-policy 数据、样本分布偏斜和复现风险。SEER 针对需要严格 on-policy 语义的同步场景优化 rollout。

## 关键观察 / 隐含假设

- **观察 1：同一 prompt 的 response 长度相关。** GRPO 及其变体为每个 prompt 生成多个 response。图 4 显示，同组 response 的输出长度通常相近，先完成的 probe response 可用于估计同组剩余工作量。
  - **依赖假设**：group size、采样策略和模型状态下，同组长度相关性足以支持近似最长作业优先（LFS）。
  - **可能失效场景**：探索性更强、temperature 更高、奖励过滤改变，或 group size 很小时，长度相关性可能下降。
- **观察 2：同组 response 复用 token 模式。** Qwen2-VL-72B 的测量显示，将同组历史作为 n-gram 参考可把后期接受 token 数提高最多 119%（表 2）。
  - **依赖假设**：同组输出的局部语法和语义模板足够稳定，CST 更新与同步开销不会抵消接受率收益。
- **假设 3：rollout 没有单请求严格延迟约束。** 这允许把请求切成 chunk 后跨实例迁移。在线服务若有严格 per-request SLO，SEER 的调度自由度和迁移策略未必成立。
- **假设 4：全局 KV cache 池能容纳活跃请求。** 实验中最重节点的活跃 KV footprint 不超过分配 DRAM 的一半；更大上下文、更高并发或较小 DRAM 预算可能引入 cache miss 和 re-prefill。

## 核心方法

SEER 的 rollout 子系统由推理实例池、全局 Request Buffer 和 Context Manager 组成，实例共享基于 Mooncake 的分布式 KV cache。训练仍使用 Megatron，推理使用 vLLM，奖励计算与生成并行执行。

**Divided Rollout** 把 prompt group 拆成独立 request，再把每个 request 切成有界 generation chunk。每个 chunk 完成后，下一块可被调度到当前 KV/计算负载较低的实例。全局 KV cache 通过 DRAM、SSD 和 RDMA 保存并迁移历史 cache，避免跨实例调度造成 re-prefill。调度器在负载可接受时优先 cache affinity；实例间 in-flight request 差距超过阈值后优先均衡负载，cache prefix 差距超过约 512 token 时主动拉取缺失 cache。

**Context-Aware Scheduling** 为每个 group 选择一个 speculative request，并优先用 shortest-first 让 probe 尽早结束。Context Manager 将已完成 response 的最大长度作为组长度估计；没有完成样本的组按最大长度保守初始化。随后对普通 request 近似 LFS，优先推进预测较长的组，同时周期性服务欠缺组避免饥饿。

**Adaptive Grouped Speculative Decoding** 使用 Distributed Grouped Draft Server（DGDS）聚合同组 response 的 token 路径。DGDS 异步维护每组 Compressed Suffix Tree（CST），推理实例周期性增量拉取并在本地生成草稿。Marginal-Benefit-Aware 策略根据当前 batch size、接受率和目标模型耗时动态选择 draft length，并为高优先级 probe 分配更高预算。大 batch 时可关闭或缩短投机，进入长尾的小 batch 则增加 draft 长度和多路径搜索。

## 设计取舍

- 分块与跨节点迁移换取负载均衡，代价是全局 KV cache、RDMA 流量和一致的请求状态管理。
- 用 probe 的在线估计近似 oracle LFS，避免离线长度预测模型，但早期估计可能错误，因此需要保守上界和防饥饿机制。
- 分组 CST 避免独立 draft model 的推理开销，代价是上下文更新、跨实例同步和对组内模式相关性的依赖。
- SEER 保留严格同步边界，牺牲了异步系统可获得的一部分重叠空间，但不改变 rollout 数据的 policy 归属。

## 实验与结果

- 在 32 个节点、256 张 H800（每节点 8 张）上评测 Moonlight、Qwen2-VL-72B 和 Kimi-K2，使用 GRPO，group size 为 8 或 16。相对 veRL，端到端 rollout 吞吐提高 44–104%（图 7）。
- 长尾定义为最后 10% 完成的 request；在 Moonlight 和 Qwen2-VL-72B 中，veRL 尾部最多占总时间 50%，SEER 将尾部时间降低 72–94%（图 8）。
- 消融显示 Divided Rollout 单独最多带来 42% 吞吐提升；上下文调度再增加最多 14%；分组投机解码在调度优化基础上再增加 26–48%（表 4）。
- 上下文调度相对仅分块方案将尾延迟降低 89%，吞吐达到 oracle LFS 的 96%（图 12）。
- SEER 的分组投机解码相对 vanilla SD 最高提升 1.3×，相对 CST 基线平均接受长度增加 0.22（图 13）。
- 相对 Partial Rollout，SEER 在 Qwen2-VL-72B 上吞吐高 43%；在 Moonlight 的 100 次训练中，SEER 与严格同步 veRL 的 reward 曲线接近，而 Partial Rollout 约第 50 次迭代后落后（图 10、图 11）。
- 全局 KV cache 在最重工作负载中单轮迁移约 3 TB，但每节点迁移时间低于对应 rollout 时间的 0.1%，活跃 cache footprint 未超过分配 DRAM 的一半（图 14、图 15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 同步 rollout 的主要瓶颈是长尾与 KV cache 驱逐 | 表 1；图 3，Qwen2-VL-72B 有 13,686 次 preemption，实例完成时间差占总时间 70% | 生产级 RL trace，H800，三类任务 | 强 |
| 在线同组上下文足以改善调度 | 图 4、图 12；吞吐达到 oracle 的 96%，尾部下降 89% | GRPO，三种模型，固定 workload | 强 |
| 分组投机解码能在动态 batch 中保持收益 | 表 2；图 13，最高 1.3×，接受长度较 CST 增加 0.22 | 三个模型，单轮 rollout 消融 | 中 |
| SEER 不改变严格同步训练质量 | 图 11，100 次 Moonlight RL 训练中 reward 曲线接近 veRL | 单模型、单数据和固定 prompt 集 | 中 |

## 批判性分析

### 论证链条

论文的主要链条是闭合的：输出长度与模式相关，因而可用 probe 估计组工作量；分块调度解决内存与实例不均衡；CST 复用同组 token，并在小 batch 长尾阶段加速。消融大体分离了三部分收益。需要谨慎的是，论文把三种机制部署在同一套全局 cache 和调度基础设施上，组件之间的交互收益不完全可加；“可推广到所有多样本生成”的结论也超出了三类 RL workload 的直接证据。

### 假设压力测试

长度估计使用组内已完成样本的最大长度。若同组 response 的长度相关性因采样温度、奖励模型或 prompt 类型改变而减弱，保守估计会让长任务过度优先，乐观估计则会重新产生尾部。论文没有报告按相关性分桶的退化曲线，也没有在跨域 production trace 上测试。

全局 KV cache 的低迁移成本依赖 8×400 Gbps RDMA、每节点 2 TB DRAM 和活跃 working set 小于容量。云上网络抖动、节点失效、跨租户隔离和 cache 池拥塞未被评测。DGDS 的异步 CST 更新则引入了 draft context 的新鲜度问题；论文说明其不影响同步训练正确性，但没有单独量化 stale CST 对接受率和尾延迟的影响。

### 实验可信度

基线统一使用同一 in-house vLLM，避免推理引擎差异；同时包含 veRL、拥有 ground-truth prompt 长度的 StreamRL-Oracle、多个 SD 策略和 Partial Rollout，覆盖了调度、解码和同步语义。局限是总体吞吐主要平均 5 次 rollout，训练质量只在 Moonlight 上运行 100 次，未覆盖故障恢复、网络拥塞、不同采样温度和更长训练周期。Partial Rollout 的质量差异支持了同步语义的价值，但不能单独证明所有非严格同步方法都会有同样退化。

### 系统性缺陷

SEER 把调度器、全局 KV cache、RDMA 迁移和 DGDS 引入 rollout critical path 外围，部署复杂度高于普通 vLLM/veRL。论文未讨论节点故障时 cache 恢复、CST 丢失、调度器重启、跨租户资源隔离和迁移流量的优先级控制。论文也未给出 CPU/DRAM/SSD 的绝对成本，因而“吞吐提升”尚不能直接转换成成本收益。

## 局限与后续工作

- **局限 1**：评测集中在高端 H800 集群和三类 reasoning model；不同硬件、网络拓扑、group size 及更弱长度相关性的任务尚未覆盖。
- **局限 2**：全局 cache 容量与 RDMA 迁移的安全余量较大，无法说明容量接近上限时的退化曲线。
- **局限 3**：DGDS 的一致性、故障恢复和 CST stale 状态没有独立的可靠性实验。
- **后续工作 1**：按组内长度相关系数、batch size 和 cache 容量做二维压力测试，测出调度收益转负的边界。
- **后续工作 2**：加入节点故障和 RDMA 限速注入，比较 cache 丢失、re-prefill 与降级到非分块 rollout 的恢复时间。
- **后续工作 3**：在多租户 SLO 下评估分块调度，量化迁移流量、DRAM/SSD 成本和单请求尾延迟。

## 相关

- **相关概念**：[[KV-Cache]]、[[Speculative-Decoding]]、[[Long-Tail-Latency]]
- **同类系统**：[[vLLM]]、[[Mooncake]]、[[veRL]]
- **同会议**：[[OSDI-2026]]
- **对比**：[[SEER-vs-Partial-Rollout]]
