---
type: paper
name: ROLLART
full_title: "RollArt: Disaggregated Multi-Task Agentic RL Training at Scale"
authors: [Wei Gao, Yuheng Zhao, Tianyuan Wu, Shaopan Xiong, Weixun Wang, et al.]
venue: OSDI
year: 2026
tags: [agentic-rl, disaggregated-training, hardware-affinity, asynchronous-training]
source_pdf: "[[osdi26-gao.pdf]]"
source_md: "[[osdi26-gao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-01-01
---

# 面向大规模多任务 Agentic RL 的解耦训练（OSDI 2026）

> **原题**：RollArt: Disaggregated Multi-Task Agentic RL Training at Scale

> **一句话总结**：ROLLART 观察到 agentic RL 同时包含 prefill、decode、CPU 环境和突发 reward 四类异构负载，因此把它们映射到不同资源池，并用轨迹级异步执行与有界策略陈旧度隐藏环境和权重同步开销；在 Qwen3 8B–32B 上相对强化同步基线将 time-to-score 降低 2.05×，吞吐提升至 2.65–4.58×。

## 问题与动机

Agentic RL 的 rollout 不是一次生成，而是 LLM 与环境反复交互。一次训练迭代同时包含生成、环境初始化与执行、reward 计算和参数更新。不同任务的交互轮数、响应长度和环境成本差异很大，单一 GPU 类型或单一同步粒度会把一种阶段的资源优化传递成另一阶段的空闲。

现有系统通常将 rollout 与训练放在同一 GPU 集群，或者只在训练与 rollout 之间做粗粒度解耦。它们没有同时处理 prefill/decode 的硬件亲和性、环境长尾、reward GPU 低利用率和跨集群权重传输。ROLLART 将这些问题作为同一个调度问题处理。

## 关键观察 / 隐含假设

- **观察 1：生成阶段并不总是 bandwidth-bound。** FrozenLake 等多轮任务偏 prefill，在成本近似的配置下 H800 的 rollout 时间最低为 H20 的 0.53×；GEM-Math 等长思维链任务偏 decode，H20 达到 H800 的 0.49–0.79×（图 4）。
  - **依赖假设**：任务域的 turn count 和 prefill/decode 比例在训练期间相对稳定。
  - **可能失效场景**：策略改变导致同一任务域的响应长度或交互轮数漂移时，静态域级映射会过时。
- **观察 2：环境执行具有严重长尾。** Qwen3-8B 的成功迭代平均 365.7 秒，LLM generation 只占 54%；发生环境失败时平均升至 513.3 秒，env.reset 占 rollout 时间 78%（图 3）。批量环境交互相对理想执行最多增加 21.3%（§3.1）。
  - **依赖假设**：环境可被拆成独立的 trajectory controller，并允许提前终止或重试。
- **观察 3：reward 负载突发且多为无状态函数。** 专用 reward GPU 利用率只有 7.4%（图 6），而 serverless offloading 后利用率从 6% 提升到 88%。
- **观察 4：跨集群权重同步会制造 GPU 空泡。** 模型越大，训练集群与 rollout 集群之间的传输越难被同步流程吸收；异步执行可以隐藏大部分传输成本（§3.2、表 3）。

## 核心方法

ROLLART 将运行时分成 resource、data 和 control 三个平面。用户通过 Python decorator 声明 Worker 的角色、硬件偏好和 serverless 方法；ResourceManager 根据资源池状态完成绑定，Cluster 则代理一组 Worker 的调用。训练和 prefill-heavy generation 默认使用 compute-optimized GPU，decode-heavy generation 使用 bandwidth-optimized GPU，环境使用 CPU 集群，reward 可使用 serverless endpoint。

控制平面以 trajectory 为最小调度单位。LLMProxy 在环境控制器与推理 Worker 之间转发请求；每个 EnvManager 独立推进 reset、生成、step 和终止流程。某个环境变慢或失败时，其他轨迹继续运行。轨迹结束后立即异步提交 reward，不等待整个 batch 完成。这直接回应环境长尾观察，并允许生成、环境和 reward 重叠。

训练与 rollout 在独立 GPU 集群上并行。每轮先从 SampleBuffer 收集 batch，暂停接收新请求但保留 in-flight trajectory，更新 rollout 权重后恢复请求，再对旧权重生成的 in-flight trajectory 重算 KV cache。异步边界 α 限制轨迹起始版本不早于当前版本减 α，并淘汰过旧轨迹；默认 α=1，在吞吐与训练稳定性之间取折中。

跨集群权重通过 Mooncake 分桶写入远端 CPU store，推理侧按需拉取，而不是让 rollout 同步等待完整权重传输。系统还提供冗余环境 rollout，以及把 prefill 和 decode 分别放到 H800/H20 的 PD disaggregation。

## 设计取舍

- **异步训练换取资源利用率**：允许有限策略陈旧度，换来 rollout 与训练重叠；α 从 1 增大到 2 虽改善早期收敛，却使后期 time-to-score 变差（§7.2、§7.3）。
- **冗余 rollout 换取长尾鲁棒性**：启动多于需求数量的环境，收集足够轨迹后终止其余任务；代价是额外 CPU、容器和环境执行成本。
- **显式域级硬件映射换取实现简单性**：不做逐请求在线负载均衡，降低控制复杂度，但依赖任务域画像稳定。
- **serverless reward 换取网络与平台依赖**：远程调用的最大 I/O 开销为 2.1 秒；部署必须具备弹性 serverless 基础设施。

## 实验与结果

- Qwen3 8B、14B、32B，128 GPU（H800/H20），GRPO batch size 512。ROLLART 相对 Sync+、One-off 和 AReaL 的 time-to-score 分别快 2.05×、1.35×、1.31×（图 10a）。
- 相对同步基线，整体吞吐提升 2.65–4.58×；相对 AReaL 的增益为 1.22–1.36×，主要来自硬件亲和性映射（图 10b）。
- 硬件亲和性相对 H800-only 和 H20-only 分别降低 step time 1.12–1.37× 和 1.30–1.68×（图 11a）。轨迹级调度在环境延迟方差增大时相对 batch 调度提升 1.23–2.27×（图 11b）。
- serverless reward 将 rollout 时间从 158 秒降至 77 秒，GPU 利用率从 6% 提升至 88%（图 12）。异步权重传输隐藏 67–78% 的 pull 成本，32B 模型暴露的剩余开销最多 9.6 秒（表 4）。
- 在超过 3,000 GPU 的 Qoder 生产训练中，最长响应长度超过均值 5×并达到 9×，最长交互轮数超过均值 40×；缓存优化后 env.reset 成功率超过 99.99%，一周运行仅观察到一次故障（§8、图 15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| agentic RL 需要按任务域区分 prefill/decode 硬件 | 图 4；图 11a | Qwen3 8B–32B，H20/H800，FrozenLake/GEM-Math 等任务 | 强 |
| 轨迹级异步能吸收环境长尾 | 图 3、图 11b | 32k context；部分环境延迟为合成 Gaussian 注入 | 中 |
| 有界异步训练兼顾吞吐与收敛 | 图 10a、图 13 | α=1–6；主要在 Qwen3 和 GRPO 上验证 | 中 |
| 解耦方案能扩展到生产规模 | §8、图 15 | Alibaba 内部任务，3000+ GPU，一周运行 | 中 |

## 批判性分析

### 论证链条

从负载测量到四项需求，再到资源映射、轨迹级调度、serverless reward 和有界异步训练，设计对应关系清楚。主要跳步在于把域级稳定性从一个生产部署推广为普遍假设；论文只用有限公开任务和一套生产 trace 验证这一点。

### 假设压力测试

静态硬件映射在任务域固定且画像稳定时有效，但策略训练可能改变响应长度和工具调用路径。α=1 的安全性也可能依赖 reward 噪声、算法和 on-policy 要求；论文主要以 GRPO 测量，未覆盖严格 on-policy 算法。SampleBuffer 的 blocking `get_batch` 在生产中最多造成 62% 的 GPU idle，说明轨迹解耦仍没有消除 batch 成形瓶颈（§8）。

### 实验可信度

论文提供了主结果、功能消融、通信税和生产部署，且基线都加入 Sync+ 的环境与 reward 优化，比较相对公平。环境长尾的一部分实验使用合成延迟；Laminar 未直接运行，而是用能力分解估计差距，因此与 Laminar 的结论应视为下界而非直接对比。

### 系统性缺陷

系统约 60k 行 Python，依赖 Kubernetes、Ray、Mooncake、vLLM、Megatron 和内部 serverless 平台。跨集群网络、容器镜像缓存和故障恢复是运行前提。论文未量化冗余环境造成的额外 CPU、存储和能耗，也未充分讨论多租户隔离、serverless 冷启动、reward 服务故障对训练质量的影响。

## 局限与后续工作

- **局限 1**：硬件亲和性需要用户提供域级声明，无法自动适应运行时分布漂移。
- **局限 2**：`get_batch` 仍以固定 batch size 等待轨迹，生产 trace 中这一等待占迭代时间最多 62%。
- **后续工作 1**：实现在线 profiler，按域持续测量 prefill/decode 比例，并在可复现实验中比较静态映射、按域重映射和逐请求路由的成本与收益。
- **后续工作 2**：将 SampleBuffer 改为带质量、版本和截止时间的流式批处理，测量在固定训练质量下能否消除 62% 的等待空泡。

## 相关

- **相关概念**：[[PagedAttention]]、[[KV-Cache]]、[[Resource Disaggregation]]
- **同类系统**：[[AReaL]]、[[StreamRL]]、[[Laminar]]、[[vLLM]]、[[SGLang]]
- **同会议**：[[OSDI-2026]]
