---
type: paper
name: Seer
full_title: "Seer: Online Context Learning for Fast Synchronous LLM Reinforcement Learning"
authors: [Ruoyu Qin, Weiran He, Weixiao Huang, Yangkun Zhang, Yikai Zhao, Bo Pang, Xinran Xu, Yingdi Shan, Yongwei Wu, Mingxing Zhang]
venue: OSDI
year: 2026
tags: [llm-training, reinforcement-learning, rollout, scheduling, speculative-decoding]
source_pdf: "[[osdi26-qin.pdf]]"
source_md: "[[osdi26-qin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Seer：用在线组内上下文加速同步 LLM 强化学习（OSDI 2026）

> **原题**：Seer: Online Context Learning for Fast Synchronous LLM Reinforcement Learning

> **一句话总结**：Seer 观察到 GRPO 为同一 prompt 采样的 responses 在长度和 token pattern 上相关，于是把 rollout 拆成可迁移 chunks，用一个现有 response 在线估计组长短，并共享组级 suffix context 做自适应推测解码；在 32–256 张 H800、三种 32 GB–1 TB reasoning models 上，相对优化过的同步 veRL 将 rollout throughput 提高 44%–104%，最后 10% requests 的处理时间降低 72%–94%。

## 问题与动机

现代 [[LLM]] 强化学习每轮包含 rollout、reward、experience construction、training 和 weight update。论文三个 production workloads 中，rollout 占整轮时间的 63%–87%（表 1）。[[Chain-of-Thought|CoT]] reasoning 会产生几百到约 96k tokens 的输出；每个请求的 [[KV-Cache|KV cache]] 从很小增长到数 GB，既挤压并发，又形成极重的输出长度长尾。

传统同步系统常以整个 prompt group 为调度单元。早期放太多请求会 OOM/preempt，丢掉 KV 后需要昂贵 re-prefill；保守限流又让短请求只占很小 cache 时 GPU 空闲。末期只剩少量极长 groups，许多 inference instances 无事可做。Qwen2-VL-72B 的 veRL trace 中，一轮发生 13,686 次 preemption，各 instance 最早与最晚完成时间之差占总时间 70%。

异步或 non-strict synchronous RL 可以不等长尾，但会把旧 policy 数据用于新 iteration，或把未完成长样本推迟，带来 off-policy/staleness 和偏向短输出的问题。Seer 聚焦严格同步、on-policy 语义：一轮仍要完成原本所有 responses，只在轮内更细地调度并加速生成。

## 关键观察 / 隐含假设

- **观察 1：同一 prompt group 的 response length 相关。** GRPO 及变体通常为同一 prompt 生成 8–16 个 responses；生产 trace 中同组列呈相似长度（§2.3，图 4）。
  - **依赖假设**：一个已开始或完成的 response 能代表组内剩余工作；高 temperature、强探索或多模态偶发分支可能使组内 variance 增大。
  - **可能失效场景**：PPO 等不做 group sampling 的算法、group size 很小，或同 prompt 被刻意要求多样化。
- **观察 2：同组 responses 还共享局部 token pattern。** 在 20 个 Qwen2-VL-72B prompt groups 上，使用组内其他 paths 作为 CST references，后期接受的 draft tokens 最多比只用自身历史增加 119%（§2.3，表 2）。
  - **依赖假设**：组内 context 更新及时，draft 查找开销低于 target-model 并行验证节省。
  - **可能失效场景**：response pattern 高度分散，或大 batch 已使 target verification compute-bound。
- **观察 3：rollout 没有在线 serving 那样严格的单请求 latency SLO。** 请求可在每个 generation chunk 后换 instance，只要整轮更快；这让 proactive KV migration 比“一个请求固定一台 engine”更灵活（§3.2）。
  - **依赖假设**：全局 KV pool 的 DRAM/SSD/[[RDMA|RDMA]] 容量足够，迁移比重新 prefill 便宜。
- **假设 1：“在线上下文学习”是轻量 heuristic，不是训练预测模型。** 长度估计取组内已完成样本的最大值，group CST 汇总已生成 tokens；它会快速适应 policy 更新，但准确性由 workload 结构决定。
  - **证据强度**：强；§3.3、§A 明确给出规则，context scheduler 达到 length-oracle throughput 的 96%。

## 核心方法

### 系统架构

Seer 是 colocated synchronous RL system：[[Megatron|Megatron]] 负责训练，统一的内部 [[vLLM]] 实现负责 rollout，reward server 与生成并行，Moonshot Checkpoint Engine 传新权重。rollout subsystem 包含 Inference Engine Pool、全局 Request Buffer 和逻辑集中式 Context Manager（图 5）。后者同时维护 group length context、调度优先级和 grouped draft context。

### Divided Rollout 与全局 KV pool

Seer 先把 prompt group 拆成独立 requests，再把每个 request 拆成固定上限的 generation chunks。chunk 完成后，下一个 chunk 可发到当前 memory/compute 更空闲的 instance；因此长请求不会从头到尾绑定一个 worker，并发也能随 KV footprint 增长逐步降低。

迁移若重算整个 prefix 会抵消收益。Seer 复用 [[Mooncake]] 构建跨 inference nodes 的 hierarchical KV pool，以 DRAM/SSD 保存所有 active requests 的 cache，并通过 RDMA 拉取。scheduler 在 instance load 接近时优先选最长 cache-prefix hit；in-flight request count 差超过阈值时改为 load-first。若新节点与最佳 cache-affinity 节点的 hit length 相差超过 512 tokens，就主动迁移缺少部分。请求完成立即释放 cache，而不是只依赖 LRU。

### 上下文感知调度（Context-Aware Scheduling）

每组挑一个原本就必须生成的 response 作为 speculative request，并非额外采样。它进入高优先级队列，以 shortest-generated-first 尽快筛出短组；长时间未结束的 probe 则提前暴露潜在长组。Context Manager 把已完成 responses 的最大输出长度作为该组 estimate；尚无完成样本的组先按最大 generation limit 保守估计。

其余 requests 按 approximate longest-first scheduling，优先让预测较长的组提前推进，避免最后才启动长请求。scheduler 偶尔服务长期没被选中的 group，防止 prediction error 导致 starvation。每次仍结合各 instance KV usage，只有存在可用 memory 的 placement 才发下一个 chunk（算法 2）。

### 自适应成组推测解码（Adaptive Grouped Speculative Decoding）

Distributed Grouped Draft Server（DGDS）为每个 group 维护 Compressed Suffix Tree（CST）。各 inference instance 异步分批 append 新 tokens；server 按 request path 隔离后聚合，embedded draft clients 周期性增量 fetch CST，再在本地做 batch speculate。这样 draft critical path 不需访问中央 server，也不需另一个频繁随 RL policy 更新的 neural draft model。

固定 draft length 在 rollout 不稳定：大 batch 时 verification 易 compute-bound，长 draft 可能负收益；长尾小 batch 时可以多验证 tokens。Marginal-Benefit-Aware policy 用 offline-profiled target forward time 和在线 acceptance/batch size，计算总 draft budget；若预计无收益就关闭 speculation。它再以 `λ=2` 偏向高优先级 probes，在 high/low priority requests 间按边际收益分配最多 8 个 draft tokens，并支持 top-k multi-path candidates（§3.4、算法 1）。

## 设计取舍

- **严格同步换取算法语义**：所有本轮 samples 仍完成，避免 staleness 和 length selection bias；极端 outlier 仍是 barrier，只能被提前执行或加速。
- **chunk mobility 换取 KV 基础设施**：细粒度平衡避免 preemption/re-prefill，却依赖跨节点 DRAM、[[NVMe|NVMe]] 和高带宽 RDMA，并增加 cache metadata 与迁移控制。
- **一个组内样本换取长度信号**：不训练 predictor、可随 policy 在线更新；单个 probe 若异常短或长会误导早期顺序。
- **共享 CST 换取 draft accuracy**：没有 neural draft forward，却需要 DGDS、增量同步和 per-group tree memory；逻辑集中式 Context Manager 也成为控制面扩展与故障点。
- **边界条件**：最适合 GRPO-like、group size 较大、long-CoT 且 rollout 严格同步的训练；短输出、无 group correlation 或低带宽集群中的收益会缩小。

## 实验与结果

- testbed 有 32 nodes，每台 8×H800、224 CPU cores、2 TB DRAM、4 TB NVMe。Moonlight 为 32 GB、32 GPUs、每实例 1 GPU、每轮 3,200 requests、group 8；Qwen2-VL-72B 为 146 GB、128 GPUs、每实例 8 GPUs、9,600 requests、group 16；Kimi-K2 为 1 TB、256 GPUs、每实例 32 GPUs、6,400 requests、group 8。三者 temperature 为 1.0/0.8/1.0，最大生成长度为 65,536/40,960/98,304 tokens，平均输出为 22,386/7,615/38,959 tokens（§4.1，表 3）。
- 所有系统使用统一内部 vLLM engine。相对同步 veRL，Seer 在不同 tasks/group sizes 上将平均 rollout token throughput 提高 44%–104%，最高 2.04×；还领先使用 ground-truth lengths 的 StreamRL-Oracle，以及为各模型定制的 SuffixDecoding、Qwen2-7B-VL draft model、MTP baselines（§4.2.1，图 7）。
- 论文把最后完成的 10% requests 定义为 tail。Moonlight tail time 从 1,817 s 降到 278 s（84%），Qwen2-VL-72B 从 2,301 s 降到 123 s（94%），Kimi-K2 从 3,144 s 降到 850 s（72%）；对应 total rollout time 也分别由 3,910/3,957/12,202 s 降到 2,181/1,922/8,267 s（§4.2.2，图 8）。
- 累积消融显示 Divided Rollout 后三任务为 baseline 的 1.41×/1.42×/1.16×；加入 context scheduling 后为 1.47×/1.56×/1.27×；再加 Grouped SD 达 1.90×/2.04×/1.53×。因此 divided rollout 最高贡献 42%，context 额外最高 14%，Grouped SD 在前两者上再贡献 26%–48%（§4.3，表 4）。
- 只做 divided rollout 的 No-Context 将 tail time 降 21%，context-aware scheduler 降 89%，吞吐达到知道真实 output lengths 的 Oracle 的 96%。Grouped SD 相对 vanilla SD 最高再提高 1.3× throughput，并把 CST-based SD mean acceptance length 增加 0.22（§4.5.1–§4.5.2，图 12–13）。
- Qwen2-VL-72B 一轮累计 KV migration 约 3 TB，但每节点 transfer time 少于对应 rollout duration 的 0.1%，因为每节点配有 `8×400 Gbps` RDMA；最忙节点的 in-flight KV footprint 始终低于 1 TB DRAM budget 的一半。与 2× over-issue 的 Partial Rollout 比，Seer throughput 高 43%；Moonlight 100 iterations 的 reward curve 与 veRL 接近，而 Partial Rollout 约从第 50 轮起落后（§4.4–§4.5.3，图 10–11、14–15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 组内长度 context 足以接近理想 long-first scheduling | context scheduler 达 Oracle throughput 96%，tail time 降 89%（图 12） | 三个 GRPO-like production workloads；无公开 correlation coefficient | 强 |
| chunk-level rollout 能缓解 memory 与 instance imbalance | 单独增加 Divided Rollout 后最高 1.42×（表 4）；preemption/tail trace 改善 | 依赖 Mooncake global KV pool 和高速 RDMA | 强 |
| grouped context 能让 speculative decoding 在 rollout 中获益 | 相对 vanilla SD 最高 1.3×，mean acceptance length +0.22（图 13） | 每模型 baseline 不同；单轮 SD ablation | 中 |
| Seer 提高严格同步 rollout throughput | 相对统一 engine 的 veRL 提高 44%–104%，tail 降 72%–94%（图 7–8） | 32–256 H800、三个内部 workloads、平均 5 iterations | 强 |
| 系统加速没有观察到训练质量损失 | Moonlight 100-iteration reward 与 veRL 接近（图 11） | 单模型、单数据和 reward metric；不是普遍收敛证明 | 中 |

## 批判性分析

### 论证链条

论文先用 phase breakdown、96k-token length distribution、13,686 次 preemption 和 instance idle trace 定位同步 rollout 的 memory/long-tail 问题，再从 GRPO 的组内长度和 pattern correlation 提取上下文。Divided Rollout、context scheduler、Grouped SD 分别回应调度粒度、未知长度和低 batch decode，累积消融与独立 extended studies 能对上每个设计，论证链条很完整。

“Online Context Learning”容易被误解成 learned predictor；实际长度 estimator 是完成样本最大值，pattern model 是在线 CST。这种简单性是优点，也意味着跨 workload 泛化完全依赖 group sampling 结构。论文声称设计可推广到其他 parallel generation，但没有在非 RL、多样化采样或 group size 1 的 workload 上验证。

### 假设压力测试

当同 prompt responses 被高 temperature 或 diversity objective 刻意拉开时，一个 probe 可能无法代表剩余 7–15 个请求。未完成组先按最大 generation length 会保守地把许多组放进 long-first，可能挤压真正长组；论文有 anti-starvation，但没有报告 prediction error distribution 或调度错误率随训练阶段如何变化。

全局 KV pool 的低成本依赖极强硬件：每节点 2 TB DRAM、4 TB NVMe 和 8×400 Gbps RDMA。测得 3 TB 累计迁移本身并不小，只是在该 fabric 上传输时间占比低。跨 rack congestion、KV server failure、DRAM budget 缩小或多训练 job 共用网络时，chunk mobility 可能从收益变为瓶颈。

### 实验可信度

三个模型跨 32–256 H800、最大 1 TB、平均输出 7.6k–39k tokens，规模和 workload 真实性很强。所有 baselines 共用同一 inference engine，StreamRL 甚至使用 ground-truth lengths，降低了实现与 predictor bias。Table 4、context Oracle、多个 SD strategy、KV traffic 和 end-to-end reward 形成了少见的完整证据链。

主要限制是系统与数据都来自 Moonshot，模型、内部 vLLM 和生产 workload 难以外部复现。throughput 只平均 5 iterations，没有方差或多次训练 seed。Partial Rollout 按 APRIL 配置 over-issue 2×，在 memory-constrained workload 中天然加重 preemption；这证明该设定下 Seer 更好，不等价于覆盖所有 asynchronous/staleness-bounded systems。reward 只测 Moonlight 100 iterations，也没有报告 time-to-target reward。

### 系统性缺陷

Seer 新增 global Request Buffer、Context Manager、distributed KV pool、DGDS 和每 instance draft client，控制面和状态量显著增加。论文量化了 KV migration，却没有给出 Context Manager/DGDS 的 CPU、memory、network overhead、最大 groups/s、故障恢复和 backpressure。逻辑集中式 scheduler 在更大集群可能成为 bottleneck。

Grouped CST、KV chunks 和 request state 分散在多个节点；节点失败后如何恢复一个进行中的 strict-synchronous iteration 没有讨论。系统优化的是 token throughput 和 batch completion，未统一核算 256 H800 之外的 CPU、2 TB DRAM、NVMe 与 RDMA TCO。异常超长 response 仍必须完成，strict barrier 只能被压缩，不能被移除。

## 局限与后续工作

- **局限 1**：收益依赖 GRPO-like group length/pattern correlation；论文没有报告 prediction error，也未测高多样性、非 grouped RL 或普通 serving。
- **局限 2**：global KV pool 在极高规格 RDMA/DRAM 集群上验证，跨 rack 拥塞、容量不足和节点失败不在实验范围。
- **局限 3**：训练质量只用 Moonlight、100 iterations、单条 reward curve；缺少多 seed、time-to-quality 和完整异步系统对比。
- **后续工作 1**：按 group size、temperature 和训练 iteration 分桶公开 length prediction error，并测 context scheduler 相对 Oracle 的 throughput/tail degradation。
- **后续工作 2**：对 RDMA 限速、DRAM budget 减半、跨 rack 和单节点故障做注入，量化 re-prefill 次数、恢复时间和 end-to-end throughput。
- **后续工作 3**：在至少三个 seed 上比较 Seer、veRL、Partial Rollout 和 staleness-bounded async system 的 wall-clock time-to-target reward，而不只比较 rollout tokens/s。

## 相关

- **相关概念**：[[LLM-Reinforcement-Learning]]、[[Speculative-Decoding]]、[[KV-Cache]]、[[Chain-of-Thought]]
- **同类系统**：[[Mooncake]]、[[vLLM]]、veRL、StreamRL、Partial Rollout
- **同会议**：[[OSDI-2026]]
