---
type: concept
aliases: [Disaggregation, disaggregated inference, prefill-decode disaggregation, P/D disaggregation]
parent: "[[LLM-Inference]]"
last_updated: 2026-07-30
tags: [llm-inference, scheduling, system-architecture]
---

# Disaggregation

> 分离式架构（disaggregation）将原本共置的计算阶段或资源拆成独立 pools/services，使它们分别伸缩和调度；在 LLM serving 中通常特指 prefill–decode 分离并跨池传 KV cache。

## 核心思想

prefill compute-heavy，decode memory-bandwidth-heavy。P/D disaggregation 为两池选择不同 GPU 数、parallelism 与 batch，由 global scheduler 把请求送入 prefiller，再通过 RDMA/P2P 迁移 KV 到 decoder。更广义上，storage、GC、MoE experts、memory 与 agentic RL roles 也可独立池化。

分离提升 resource matching 与 failure isolation，却引入 data movement、queueing、状态 ownership、跨服务 version 与网络依赖。收益条件是独立伸缩/复用节省大于 transfer/control cost。

## 为什么重要

现代 workload 阶段异构且资源昂贵，共置常留下 compute、HBM、CPU 或 storage 的互补空洞。但 full disaggregation 不是默认最优：commodity network、低并发、短 context、stateful retry 和复制成本可能让 hybrid/collocated 更好。

## 关键观察 / 隐含假设

- **P/D 适配与 KV transfer 是同一问题**：[[Mooncake]]、[[KVCacheInTheWild-ATC25]] 将 cache residency/transfer 纳入全局调度；网络必须足够快且 cache hit 可复用。
- **commodity cluster 需要 data-reduced hybrid**：[[EcoServe-OSDI26]] 发现 full disaggregation 的 KV traffic/load balance 可成为瓶颈，用 cross-instance phase orchestration降低传输。
- **生产诊断必须跨服务边界**：[[StriaTrace-OSDI26]] 追踪 online LLM inference；分离后 root cause 可能来自 queue、network、prefiller、decoder 或 cache layer。
- **MoE/agentic RL 也需要 role disaggregation**：[[LocalMoE-Hybrid-OSDI26]] 分离 CPU/GPU expert execution，[[RollArt-OSDI26]] 分离 rollout、environment、reward 与 trainer；两者都面临状态/版本协调。
- **GC disaggregation 平滑周期性 burst**：[[DGC-OSDI26]] 将 marking 变成 RDMA 共享服务，显著降低 p99，但付出 25% 远端 memory 和每周期约 5.52 GB traffic。

## 设计空间与取舍

- **full P/D pools**：资源独立伸缩，KV network 与 control-plane 最重。
- **macro-instance/hybrid**：[[EcoServe-OSDI26]] 减少数据跨实例，仍需复制模型和同步 phase。
- **cache/storage disaggregation**：容量共享、reuse 高，tail/network failure 进入关键路径。
- **compute service disaggregation**：如 [[DGC-OSDI26]]，可平滑 burst，但共享服务形成 blast radius。
- **role disaggregation**：适合 agentic RL/复杂 pipeline，需明确 version、retry 与 backpressure。

## 引用本概念的论文

- [[Mooncake]] — KVCache-centric P/D disaggregated serving 系统与传输/存储层。
- [[EcoServe-OSDI26]] — 界定 commodity network 下 full disaggregation 的不足并提出 hybrid orchestration。
- [[StriaTrace-OSDI26]] — 跨 online inference components 做 trace 与 diagnosis。
- [[LocalMoE-Hybrid-OSDI26]] — 分离 CPU/GPU MoE expert execution。
- [[DGC-OSDI26]] — 将 GC marking 作为共享远端服务。
- [[RollArt-OSDI26]] — 分离多任务 agentic RL roles 与 data plane。
- [[FineMem-OSDI25]]、[[Nostor-OSDI25]] — 从 memory/storage 角度扩展 disaggregation。

## 已知局限 / 开放问题

- 自动绘制 collocation、full disaggregation 与 hybrid 的 workload/network crossover。
- 在扩缩容、节点故障与 retry 中维护 KV/output/model-version exactly-once ownership。
- 把 NIC、CPU、memory、energy 和 replication 纳入完整 TCO。
- 处理跨服务 backpressure、tail amplification、公平性和共享 blast radius。
