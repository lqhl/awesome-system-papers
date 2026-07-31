---
type: entity
kind: system
aliases: [Mooncake Store, Mooncake Transfer Engine]
status: active
last_updated: 2026-07-30
tags: [llm-inference, kv-cache, disaggregation, rdma, serving]
---

# Mooncake

> Mooncake 是 Moonshot AI 的 KVCache-centric 分离式 LLM serving 栈；它把 KV cache 变成跨 prefiller、decoder、请求与存储层共享的一等数据对象。

## 是什么

Mooncake 以“更多存储换更少计算”为设计哲学：prefill 与 decode 在不同 GPU pools 执行，global scheduler 依据 KV residency 路由请求，Transfer Engine 通过 RDMA/P2P 搬运 cache，Mooncake Store 则提供分布式容量层。它既是完整 serving system，也逐渐成为第三方系统复用的 storage/transfer substrate。

Mooncake 的收益建立在 cache reuse 与高速网络可覆盖 transfer cost 上。长 context、重复 prefix 和昂贵 recompute 更有利；短 prompt、低命中、拥塞或跨 rack traffic 会削弱价值。

## 关键观察 / 隐含假设

- **KV cache 可比计算更值得移动和持久化**：[[Mooncake-FAST25]] 将 cache residency 纳入 global scheduling；[[KVCacheInTheWild-ATC25]] 说明真实 reuse、大小和生命周期决定收益。
- **传输层是 disaggregation 的性能边界**：[[fabric-lib-MLSys26]] 指出 Mooncake Transfer Engine 与 EFA/RDMA 能力绑定；[[EcoServe-OSDI26]] 则表明 commodity network 上 full disaggregation 可能输给 data-reduced orchestration。
- **共享 KV pool 可支持运行中迁移**：[[Seer-OSDI26]] 利用 Mooncake 风格 global KV cache 在 RL rollout chunks 间迁移请求而不 re-prefill。
- **控制面与状态版本必须共同容错**：[[RollArt-OSDI26]] 在 agentic RL 中复用 Mooncake，并要求 trajectory、weight 和 cache state 在重试时不重复或错版。

## 演进时间线

- 2025 FAST：[[Mooncake-FAST25]] — 提出 KVCache-centric disaggregated serving、Transfer Engine 与 global scheduler。
- 2025 ATC：[[KVCacheInTheWild-ATC25]] — 用真实 workload 检验跨实例 KV-aware routing 和 cache 行为。
- 2026 FAST：[[Bidaw-FAST26]] — 将 Mooncake 作为高速 pooled capacity layer，对比低成本本地 SSD KV storage。
- 2026 MLSys：[[fabric-lib-MLSys26]] — 把 Transfer Engine 纳入统一 GPU communication API/benchmark。
- 2026 OSDI：[[Seer-OSDI26]]、[[RollArt-OSDI26]]、[[EcoServe-OSDI26]] — 分别将其用于同步 RL migration、多任务 agentic RL，并挑战 full disaggregation 在 commodity cluster 的适用边界。

## 相关概念

- [[KV-Cache]]、[[Disaggregation]]、[[RDMA]]、[[LLM-Inference]]、[[Prefix-Caching]]

## 相关论文

- [[Mooncake-FAST25]] — Mooncake 主论文与生产 serving 设计。
- [[Seer-OSDI26]] — 以全局 KV pool 支持 rollout request chunk migration。
- [[EcoServe-OSDI26]] — 说明低带宽环境下减少跨实例数据可能优于 full P/D disaggregation。
- [[RollArt-OSDI26]] — 在多任务 agentic RL 中复用 Mooncake data plane。
- [[fabric-lib-MLSys26]] — 比较 Transfer Engine 与其他 GPU communication backend。
- [[Bidaw-FAST26]] — 从低成本 SSD 角度界定 Mooncake 的高性能容量层 niche。
