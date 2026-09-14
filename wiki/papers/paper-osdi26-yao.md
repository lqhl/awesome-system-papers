---
type: paper
name: OpenTela
full_title: "OpenTela: Unifying Decentralized Computing Resources for Heterogeneous LLM Serving"
authors: [Xiaozhe Yao, Youhe Jiang, Ilia Badanin, Qinghao Hu, Robert Matthew Smith, Binhang Yuan, Imanol Schlag, Eiko Yoneki, Ana Klimovic]
venue: OSDI
year: 2026
tags: [llm-serving, hpc, decentralized-orchestration, heterogeneous-gpus, crdt]
source_pdf: "[[osdi26-yao.pdf]]"
source_md: "[[osdi26-yao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-05-17
---
# 在异构 HPC 上联邦化 LLM 服务（OSDI 2026）

> **原题**：OpenTela: Unifying Decentralized Computing Resources for Heterogeneous LLM Serving

> **一句话总结**：针对 Slurm 分配短暂、GPU 异构且跨集群节点不可入站访问的 sovereign AI 场景，OpenTela 用用户态 libp2p gossip + CRDT registry 统一服务发现、路由和调度；22 个月的部署服务了 1,300 万请求、150 亿 token 和 142 个模型，但其服务质量、跨节点 KV cache 复用和强可用性仍未解决。

## 问题与动机

现有 LLM serving engine（如 vLLM、SGLang）负责模型执行、KV cache 和 batching，却把服务发现、健康检查、负载均衡和稳定入口交给 Kubernetes 等外部控制面。HPC 集群通常由 Slurm 管理，作业有固定时限，节点可能被抢占，且没有持久服务名或外部路由层。直接改用 Kubernetes 会破坏 HPC 的拓扑感知和 MPI 工作流，静态划分两类资源又会造成一侧空闲、另一侧排队。

OpenTela 的目标是把多个由不同机构管理的 Slurm/Kubernetes 集群叠加成统一服务平台，不替换底层资源管理器，也不要求 root 权限或集群重配置。用户看到一个 OpenAI-compatible API，系统负责把请求送到满足模型和信任约束的实例。

## 关键观察 / 隐含假设

- **观察 1：HPC GPU 容量和 LLM 请求都高度动态。** 生产 trace 中模型使用呈多层 power-law，模型峰值 TPM/活跃期平均 TPM 的比值最高超过 80（图 9–11）。
  - **依赖假设：** 不同集群的闲置容量和请求峰值在时间上有足够互补性，联邦资源池能吸收波动。
  - **可能失效场景：** 高峰同步发生、网络策略阻断跨集群路径，或热门模型没有可用副本时，联邦化只能暴露短缺，不能创造容量。
- **观察 2：模型工作负载的输入/输出比例、输出长度和 prefix reuse 差异很大。** reasoning 请求 P95 E2E latency 为 173.58 s，是非 reasoning 请求 30.77 s 的 5.5 倍；一个代表性 reasoning 模型的 prefix reuse 超过 90%（图 12–15）。
  - **依赖假设：** 调度器能从请求统计中得到足够准确的 arrival rate 和 token 分布，并据此选择模型与 GPU 放置。
  - **可能失效场景：** 模型刚上线、流量突变、prompt 分布漂移或大量长尾模型使历史统计不稳定。
- **假设 1：最终一致的 registry 足以支持请求路由。** 节点状态允许短暂过期，且健康检查、候选过滤和 best-effort retry 能覆盖状态传播窗口。
  - **证据强度：** 中。8–128 节点时 95% 状态在 1 秒内收敛，但最慢节点在 128 节点时约 10 秒才收敛；论文没有给出网络分区期间的错误路由率。
- **假设 2：用户可以可靠维护 provider allowlist。** 系统将数据治理信任交给请求方，而非通过全局策略强制执行。
  - **证据强度：** 中。机制明确，但 allowlist 错配、机构撤销和 provider 身份生命周期的运维成本未评测。

## 核心方法

OpenTela 节点以用户态进程运行，包装已有的 vLLM 或 SGLang 启动命令。节点用 libp2p 建立加密 peer-to-peer 网络，借助 Kademlia DHT、随机 gossip、NAT hole punching 和 circuit relay 连接通常只能出站的 HPC 计算节点。一个公开 ingress 节点接收外部请求，但它不依赖中心 catalog，而是读取本地 registry 副本。

registry 使用 G-Map CRDT。每个节点记录唯一 session ID、硬件元数据、模型服务信息和生命周期状态，更新经 gossip 传播并在本地合并。节点状态按 JOIN → SERVING → DOWN → LEFT 单调推进；健康探测失败先进入可自愈的 suspicion，超过宽限期才永久驱逐。应用层先清理过期节点，之后压缩 tombstone，避免 CRDT 无限增长。该设计回应了观察 1 中的节点 churn，并牺牲强一致性来消除中心协调器。

请求到达 ingress 后，先按模型从本地 Model Registry 找候选，再按用户指定的 provider allowlist 过滤，最后使用随机、round robin 或加权随机策略选择 session ID。非 streaming 请求失败时可重试到其他节点；streaming 已经开始后无法透明迁移，因为标准 API 无法从部分输出恢复非确定性生成。这是对短暂节点失效的 best-effort 容错，而非强语义恢复。

服务 scheduler 将模型需求和 GPU 类型联合建模。它决定 GPU allocation matrix 与每个模型的数据/张量并行配置，以平均端到端延迟为目标，并约束 GPU 总量、模型权重与 KV cache 的显存需求及并行度整除关系。性能由基于 roofline 的 serving simulator 估计，再交给 constraint programming 求解。模拟器覆盖 continuous batching、model parallelism 和调度策略，但未覆盖 chunked prefill、prefill-decode disaggregation 或 prefix caching，回应观察 2 的异构与工作负载差异，却使调度结果依赖近似模型。

## 设计取舍

- **去中心化换取可用性，牺牲一致性和诊断简单性。** 每个节点保存完整副本，分区时仍可路由；代价是状态传播存在秒级尾延迟，且分布式故障排查困难。
- **用户态 overlay 换取部署兼容性，牺牲深层安全保证。** 签名 binary 只能证明 OpenTela 文件未被替换，不能阻止 provider root 修改 serving engine 或读取 loopback 上的 prompt。
- **不主动回收运行中资源，换取可预测性，牺牲弹性。** 当前调度器只利用新出现的空闲资源，不会把低负载模型改放给热门模型，也不会在线改变并行配置。
- **统一 OpenAI API 换取客户端兼容性，牺牲 QoS 表达能力。** 量化位宽、context limit 和数值质量依赖模型命名约定，尚不能在请求中协商。

## 实验与结果

- 在 1 GH200 上服务 Qwen3-1.7B 时，ingress 为 0.33 ms，CRDT lookup 少于 0.1 ms；控制面约占 p50 TTFT 的 10%，TPOT 的额外开销低于 1 ms（图 5）。Frankfurt 到瑞士的跨地域部署增加约 3.5 ms TTFT，其中约 3.1 ms 来自网络往返。
- 8–128 节点的 gossip 更新中，50% 节点在 7–13 ms 收敛，75% 在 26 ms 内，95% 在 1 s 内；128 节点最慢节点约 10 s。控制面消息在 10 节点时约 1 KB/s，在 50 节点时约 8 KB/s；高频 CRDT 重注册时可达 40 KB/s/节点。
- 在最多 64 张 GH200、随机终止 worker 的持续负载实验中，吞吐量平均随活跃副本数变化，整个实验没有用户可见 HTTP error（图 4）。该结果证明了 failover 路径可用，但没有给出请求重试次数、完成延迟尾部或 streaming 中断率。
- 在 24 张 A100 和 32 张 GH200、混合 13B/34B/70B 工作负载上，异构感知放置优于按显存需求比例分配的 memP 基线（表 1、图 7）。论文强调该策略并不保证全局最优。
- roofline simulator 的绝对延迟误差最高约 10%，但预测 H100 相对 RTX 3090 的 speedup 与实测值相差不超过 6%（图 8）。这足以支持相对硬件排序，却不足以证明绝对 SLO 预测准确。
- 真实部署运行超过 22 个月，覆盖 3 个 Alps 子集群、1,000 多名研究者、142 个模型、1,300 万请求和超过 150 亿 token；trace 时间跨度为 2024 年 7 月至 2025 年 10 月，包含 46 个公开 open-weight 模型和 96 个社区自训模型（§6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 用户态 overlay 能在瞬态 HPC 资源上提供低额外延迟的统一入口 | 图 5：lookup 少于 0.1 ms，控制面约占 TTFT 10% | Qwen3-1.7B、单 GH200；跨地域只测少数路径 | 强 |
| CRDT gossip 能在节点 churn 下维持服务连续性 | 图 4：最多 64 GH200，随机终止节点且 0 HTTP error | 没有网络分区、streaming 失败和重试尾延迟数据 | 中 |
| 异构感知放置优于显存比例启发式 | 表 1、图 7：混合三模型与 A100/GH200 集群 | 单一合成 trace；未证明全局最优或多租户隔离 | 中 |
| trace 反映了需要弹性和 workload-aware serving 的真实需求 | §6：22 个月、142 模型、1,300 万请求；峰均比最高超过 80 | 内容被匿名化，机构与模型生命周期可能影响分布 | 强 |
| simulator 可指导异构调度 | 图 8：绝对误差最高 10%，相对 speedup 误差不超过 6% | H100/RTX 3090，三种长度和 batch 配置；缺少多种 serving 优化 | 中 |

## 批判性分析

### 论证链条

论文的主链条较完整：Slurm 的瞬态分配和 GPU 异构导致传统控制面难以复用，CRDT/gossip 解决服务状态传播，本地副本支持快速路由，调度器利用异构性能模型进行放置，部署 trace 证明问题确实存在。实验覆盖了控制面开销、churn、放置和 simulator 相对准确性。

但“零 HTTP error”不能等同于服务质量保持。节点失败后的透明 retry 可能增加完成时间，也可能重复执行有副作用的请求。论文没有报告这些情况。类似地，scheduler 的优化目标是平均 E2E latency，而生产请求包含极长 reasoning 尾部；平均值未必对应用户的 P95/P99 SLO。

### 假设压力测试

最终一致 registry 在 ingress 自身已看到新服务后即可路由，但在节点刚 DOWN、其他副本尚未收到状态时可能产生 stale dispatch。三路探测与宽限期降低误杀，却也延长了失效节点从全局候选集中消失的时间。论文未测量该窗口下的失败请求比例。

跨机构路由还受到数据主权、网络拥塞和 provider 信任变化影响。allowlist 只限制“发给谁”，不能证明 provider 使用了未篡改的 serving engine。硬件 attestation 被留作未来工作，因此对敏感 prompt 的保护弱于系统接口给人的安全感。

### 实验可信度

部署 trace 的时间跨度和模型多样性是强项，优于只含单模型的公开 trace。合成放置实验则只对比一个 memP 启发式，且没有与 Helix、HexGen 等更强调度方法直接比较。fault-tolerance 实验采用随机终止节点，未覆盖 Slurm 抢占、NCCL hang、网络分区、负载相关故障和长期滚动升级。模拟器的相对误差结果有说服力，但缺失 prefix caching、chunked prefill 等优化会改变真实排序。

### 系统性缺陷

OpenTela 当前是 best-effort 服务。streaming 失败无法透明恢复，强可用性、服务等级和 QoS 协商尚未提供。每个节点保存完整 CRDT 副本，节点数和 metadata 规模继续增长时的内存成本没有评测。Ingress 的统一入口仍是实际的公共依赖点，虽然 registry 没有中心协调器，但 ingress 故障恢复和多 ingress 一致性没有展开。论文也未报告认证、usage tracking 和日志汇聚对生产吞吐及隐私的额外成本。

## 局限与后续工作

- **局限 1：协议无法表达服务质量。** 未来应支持请求级量化位宽、GPU 类型、context limit 和稳定性约束，并测量约束过滤对可用率和延迟的影响。
- **局限 2：缺少强可用性等级。** 可按稳定分区与 scavenger queue 建立 tiered service level，再用真实抢占 trace 评测 P95/P99 完成率。
- **局限 3：跨节点 KV cache 与阶段拆分未支持。** 应测量全局 KV cache、prefill/decode disaggregation 在跨集群网络延迟下的命中收益与带宽成本。
- **局限 4：安全边界停留在 binary signature。** 可用 hardware-backed attestation 验证 serving engine，但需要同时评估 enclave 对 GPU 性能、部署兼容性和运维的影响。
- **局限 5：调度器依赖不完整 simulator。** 应加入 prefix caching、chunked prefill、能耗和尾延迟模型，并在生产 trace 上做预测—实测闭环校准。

## 相关

- **相关概念**：[[CRDT]]、[[KV-Cache]]、[[Continuous-Batching]]、[[Model-Parallelism]]
- **同类系统**：[[vLLM]]、[[SGLang]]、[[HexGen]]、[[Helix]]
- **同会议**：[[OSDI-2026]]
