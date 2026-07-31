---
type: concept
aliases: [Expert Parallelism, Expert-Parallel, expert-parallel, EP, MoE Expert Parallelism]
parent: "[[MoE]]"
last_updated: 2026-07-30
tags: [moe, distributed-training, llm-inference, parallelism]
---

# Expert-Parallelism

> 专家并行（expert parallelism, EP）把 MoE experts 分布到不同 devices，让 token 经 router 后 AllToAll dispatch 到目标 expert，再 combine 返回；其性能由负载倾斜、拓扑与数据重排共同决定。

## 核心思想

每张 GPU 只保存部分 expert weights，token 稀疏激活 top-k experts。与复制完整 FFN 相比，EP 容纳更大参数并降低单卡 weight memory，但每层产生两次 token permutation/AllToAll，消息大小和目的地由动态 routing 决定。

EP 必须联合考虑 expert placement、capacity、token drop/padding、intra-/inter-node bandwidth、compute overlap 与 fail-slow。均匀 expert count 不等于均匀 token load。

## 为什么重要

MoE 以较低 active FLOPs 扩大参数，却把 dense collective 变成 irregular all-to-all。训练和 serving 中，网络、host orchestration、GPU queue ordering 和 expert hot spot 都可能压倒 FFN compute；可移植通信与在线 balance 因而成为独立系统问题。

## 关键观察 / 隐含假设

- **post-overlap cost 决定 stage/EP topology**：[[Tessera-OSDI26]] 用 task DAG 联合 pipeline partition 与 expert communication，并依据 router token count 预测 bubble。
- **portable EP 需要显式 ordering 与 backend abstraction**：[[UEP-OSDI26]] 用软件协议适配不同 NIC/GPU queue，代价是 CPU/ordering overhead 与更大的验证面。
- **本地 MoE 仍可用 CPU–GPU hybrid 模拟 EP**：[[LocalMoE-Hybrid-OSDI26]] 把部分 expert 放 CPU/低精度路径以满足 consumer hardware capacity，瓶颈转为 DDR/PCIe 与 p99 SLO。
- **层级网络需要层级 collective**：DeepEP、[[MoEBlaze-MLSys26]]、[[FP8FlowMoE-MLSys26]] 分别从 NVLink/RDMA、overlap 与 precision/layout 优化 dispatch/combine。
- **router distribution 会漂移**：[[MoE-Serving-Tax-MLSys26]]、[[LatencyOptimal-MoELB-INET4AI25]] 表明静态 placement 无法覆盖 workload/model phase 变化。

## 设计空间与取舍

- **flat AllToAll**：接口简单，在异构/层级拓扑上容易拥塞。
- **hierarchical EP**：先节点内再跨节点，减少慢链路流量，增加 staging 与 synchronization。
- **expert replication**：缓解 hot expert，消耗 HBM 并引入 replica consistency/routing。
- **token dropping/padding**：获得固定 shape，高 load 下影响质量或浪费 compute。
- **CPU/GPU hybrid**：扩展本地容量（[[LocalMoE-Hybrid-OSDI26]]），受 PCIe/DDR 和 energy 限制。

## 引用本概念的论文

- [[Tessera-OSDI26]] — 联合 EP communication、pipeline partition 与 bubble filling。
- [[UEP-OSDI26]] — 提供跨 NIC/backend 的 portable expert-parallel communication。
- [[LocalMoE-Hybrid-OSDI26]] — 在本地设备上以 CPU–GPU hybrid 执行 MoE experts。
- DeepEP — 针对 H800 NVLink/RDMA 层级带宽优化 EP。
- [[MoEBlaze-MLSys26]] — 重叠 MoE communication 与 compute。
- [[FP8FlowMoE-MLSys26]] — 联合低精度 layout 与 expert data flow。

## 已知局限 / 开放问题

- 对 routing drift、hot expert 和 multi-tenant traffic 做低成本在线 rebalance。
- 形式化 GPU/NIC queue ordering、retry 与 partial failure correctness。
- 联合 precision、expert placement、replication 和 PP/DP topology 搜索。
- 报告 CPU core、network energy、p99 token latency 与 quality/drop 影响。
