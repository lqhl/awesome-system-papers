---
type: paper
name: Seer
full_title: "Seer: Online Context Learning for Fast Synchronous LLM Reinforcement Learning"
authors: [Ruoyu Qin, Weiran He, Weixiao Huang, Yangkun Zhang, Yikai Zhao, et al.]
venue: OSDI
year: 2026
tags: [llm-training, reinforcement-learning, rollout, scheduling, speculative-decoding]
source_pdf: "[[osdi26-qin.pdf]]"
source_md: "[[osdi26-qin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Seer：用在线上下文学习加速同步 [[LLM|LLM]] 强化学习（OSDI 2026）

> **原题**：Seer: Online Context Learning for Fast Synchronous LLM Reinforcement Learning

Seer 利用同一 prompt group 内 response length 和 token pattern 的相关性，先用 probe response 学习该组上下文，再以细粒度 rollout、KV cache 全局池和 grouped speculative decoding 消除同步 RL 的长尾。

## 问题与动机

rollout 占现代 LLM RL iteration 的 63%–87%。长 [[Chain-of-Thought|CoT]] output 同时产生 heavy-tailed execution time 与不断增长的 KV cache，导致 worker 间失衡、OOM preemption 和昂贵 re-prefill。异步 RL 能隐藏尾部，却引入 off-policy/staleness 与 length bias；Seer 针对必须严格同步、on-policy 的训练。

## 关键观察 / 隐含假设

### 关键观察

- GRPO 等算法为同一 prompt 生成一组 responses；组内 output length 和 response pattern 强相关，可用首个样本在线预测剩余工作。
- 把整组视为不可拆单元造成 inter-/intra-instance imbalance；chunk 化后可在执行过程中迁移和重排。
- 同组 responses 具有相似 token pattern，适合共享 adaptive speculative-decoding policy。

### 隐含假设

- prompt group 内相关性在任务和训练阶段中稳定；probe response 不会是异常短/长样本。
- 集群具有可供所有 inference instances 访问的高带宽 global KV cache，迁移成本低于重新 prefill。
- draft model 与 target model 的接受率可在线估计，并且额外 draft compute 不挤占关键资源。

## 核心方法

### 拆分式 Rollout（Divided Rollout）

Seer 把每个 prompt group 拆为更小 chunks，scheduler 按 KV budget 增量发放。请求可在下个 chunk 迁往负载较轻 worker；Mooncake 风格 global KV pool 保留 prefix，避免迁移后 re-prefill。

### 上下文感知调度

每组先生成 speculative/probe request，估计该 prompt 的 output length 与 KV footprint。scheduler 近似 longest-job-first，将长短组搭配形成密集 batch，减少末尾只剩少数长请求的 drain time。

### 自适应成组推测解码

系统利用组内 acceptance context，为长尾与普通请求分别选择 draft length，并根据 batch、接受率和关键路径 latency 最大化预测 throughput，而不是使用固定 speculation 参数。

## 设计取舍

- 严格同步保持算法语义，却仍必须等待最慢 request；Seer 只能压缩而不能消除 straggler barrier。
- chunk/migration 提升平衡性，但增加 scheduler 与 global KV metadata/data traffic。
- probe 提供在线上下文，也让每组早期决策受单个样本噪声影响。
- speculative decoding 用额外模型计算换 target decode 时间，资源竞争会改变最优点。

## 实验与结果

- 在 Moonlight、Qwen2-VL-72B 和 Kimi-K2 三个 production-grade RL workload、32/128/256 GPUs 上，Seer 相比 veRL rollout throughput 提高 44%–104%，最高为 2.04 倍（§4.2，图 7）。
- 三个任务的 rollout tail time 分别降低约 84%、94% 和 72%；基线最后 10% requests 最多占总 rollout 时间 50%。
- Qwen2-VL-72B 基线出现 13,686 次 preemption；最后 5% requests 平均到总时间 42% 才开始执行，worker 完成时间差占 70%，直接支持 load imbalance 诊断。
- 消融中 Divided Rollout 分别带来 1.41/1.42/1.16 倍 throughput，context scheduling 提升到 1.47/1.56/1.27 倍，grouped SD 后达到 1.90/2.04/1.53 倍。
- context-aware scheduling 相比无上下文进一步提高最高 14% throughput，并达到 oracle throughput 的 96%；tail latency 相比 baseline 降低 89%，而仅 divided rollout 为 21%。
- adaptive grouped SD 相比 vanilla SD 在各任务最高提高 1.3 倍 throughput；全局 KV transfer 低于 rollout traffic 的 0.1%，但评估依赖 400 Gbps 网络。
- reward curves 显示 Seer 与严格同步基线训练质量相当，Partial Rollout 因偏向短 trajectory 表现较差；质量证据限于所测任务与训练时长。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| 组内上下文可预测 rollout 长尾 | probe response 估计 length/KV | 达到 oracle throughput 的 96% | 依赖 prompt group 相关性 |
| 细粒度 rollout 可消除负载失衡 | chunk scheduling 与 global KV | 单独带来最高 1.42 倍 throughput | 需要高速共享 KV infrastructure |
| grouped SD 可进一步加速尾部 | 自适应 draft length | 最终 throughput最高 2.04 倍 | draft model compute 未必免费 |
| 严格同步可在不改 RL 语义下加速 | 所有 samples 同 iteration 完成 | reward 与同步基线相当 | 少数任务，未证明普遍收敛等价 |

## 批判性分析

### 论证链条

论文从 rollout phase 占比和 preemption trace 定量定位问题，再以三个互补机制分别解决分组粒度、调度信息和 decode 速度；逐层消融尤其清楚。与 Partial Rollout 的质量比较把系统收益和算法语义联系起来。

### 假设压力测试

若同 prompt responses 因探索温度而高度多样，probe 预测会退化；若 KV pool 跨 rack 或网络拥塞，迁移可能比 re-prefill 更慢。训练后期输出分布快速变化时，profiled draft policy 也可能滞后。

### 实验可信度

三种大模型 workload、最高 256 GPUs、端到端 reward 和详细消融较强。系统来自 Moonshot，外部难复现完整集群；没有比较最新异步系统在控制 staleness 后的 quality/time-to-target，也缺少 scheduler CPU 与 KV pool failure 分析。

### 系统性缺陷

Seer 将 inference engine 与 RL group semantics 深度绑定，通用 rollout framework 集成复杂。它优化单 iteration throughput，但额外 probe/speculation、global KV 内存和网络占用的 TCO 未统一核算；同步 barrier 在极端异常 response 下仍存在。

## 局限与后续工作

- 在高温度、多样化 response 与训练阶段漂移下量化 context prediction error。
- 比较 time-to-quality，而不只 rollout throughput，并覆盖更多 RL 算法。
- 在跨 rack、KV pool 故障与网络拥塞下验证迁移/回退机制。
- 联合优化 draft GPU、target GPU、KV memory 和 network 的完整资源成本。

## 相关

- [[LLM-Reinforcement-Learning]]
- [[Speculative-Decoding]]
- [[KV-Cache]]
- [[Mooncake]]
