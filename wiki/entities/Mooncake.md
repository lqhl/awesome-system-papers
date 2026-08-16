---
type: entity
kind: system
aliases: [Mooncake Store, Mooncake Transfer Engine]
status: active
last_updated: 2026-08-14
tags: [llm-inference, kv-cache, disaggregation, rdma, serving]
---

# Mooncake

> Mooncake 是 Moonshot AI 的分离式数据底座。它最初围绕 [[KV-Cache]] 设计，但 OSDI 2026 语料显示，第三方系统也会复用 Mooncake Store 和 Transfer Engine 搬运 KV、权重或其他大块 GPU/CPU 状态。

## 是什么

Mooncake 的核心抽象是：不让每个 prefill/decode worker 只看自己的本地显存，而是把已计算的 KV 作为可定位、可传输、可分层存储的数据对象。常见组件包括：

- 按 cache residency、请求负载和 prefix 命中做决策的全局调度；
- 经 [[RDMA]]/P2P 在 GPU memory、host DRAM 和节点之间搬数据的 Transfer Engine；
- 为更大容量、跨进程共享和持续化提供底座的 Mooncake Store。

这些机制可以支持 prefill/decode [[Disaggregation]]，也可以单独当作数据传输与容量层。因此“使用 Mooncake”不一定表示完整采用 Mooncake serving 调度器。

## 关键观察 / 隐含假设

- **复用 KV 只在加载比重算更便宜时成立。** [[KVCacheInTheWild-ATC25]] 显示真实请求的复用率、大小和生命周期并不等同于合成 trace。短 prompt、低命中或慢网络上，一次 remote load 可能比重做 prefill 更慢。
- **全局 KV pool 能把“请求迁移”和“从头 prefill”分开。** [[Seer-OSDI26]] 用 Mooncake 搭建跨 inference node 的 DRAM/SSD 层级 KV pool，经 RDMA 拉取 active request 的 cache。它在负载相近时优先最长 prefix hit，负载差距过大时改用 load-first；这说明 cache affinity 不能单独决定路由。
- **“已命中”不等于“已就绪”。** [[Strata-OSDI26]] 使用 Mooncake tool-agent trace，观察到 38% 请求与一秒内另一请求共享至少 6K token；但分页 KV 的碎片搬运仍可让 prefill 等待。所以调度器需要知道 ready time，不能只看命中长度。
- **完全 P/D 分离依赖网络。** [[EcoServe-OSDI26]] 在 L20/A800 普通网络上报告，减少跨实例 KV 传输的时间分段方案相对 MoonCake 基线有明显收益；到 H100+NVLink/IB 时差距缩小，个别 CodeLlama2-34B 点上 MoonCake 还会超过 EcoServe。这是 workload 和 network 的 crossover，不是对 disaggregation 的总体否定。
- **Mooncake Store 的用途已超出 KV。** [[RollArt-OSDI26]] 在 H800 trainer 与 H20 inference 的慢 Ethernet 路径上，用 Mooncake CPU store 发布约 1 GB 的权重 bucket，inference worker 按需拉取并与 rollout 重叠。因此实体页不应把 Mooncake 等同于单一 KV cache policy。

## 设计空间与取舍

| 决策 | 好处 | 代价 / 失效场景 |
|---|---|---|
| 搬 KV，不重做 prefill | 长 prefix 可节省大量 GPU 计算 | 低命中、短 context 或慢网络上不划算 |
| 全局 pool | 请求可跨 worker 迁移，cache 容量可扩到 DRAM/SSD | ownership、版本、驱逐、失败恢复变复杂 |
| P/D 分离 | 两个阶段可独立扩容 | KV 传输、跨 rack 拥塞和负载不均可主导尾延迟 |
| 通用 Store/Transfer substrate | 可复用于权重、checkpoint 或其他大对象 | 上层必须自己定义一致性和重试语义 |

## 演进时间线

- **2025**：Mooncake 建立 KVCache-centric 分离式 serving、Transfer Engine 与全局调度的基本定位；[[KVCacheInTheWild-ATC25]] 开始用生产 trace 检验其 cache 假设。
- **2026**：[[Bidaw-FAST26]] 把 Mooncake 视为高性能 pooled capacity 对照，[[fabric-lib-MLSys26]] 把 Transfer Engine 放入通用 GPU communication API 的比较。
- **2026·OSDI**：[[Seer-OSDI26]] 复用层级 KV pool，[[RollArt-OSDI26]] 复用 CPU store 发权重，[[EcoServe-OSDI26]] 和 [[Strata-OSDI26]] 分别暴露了慢网络和碎片 I/O 边界。

## 相关概念

- [[KV-Cache]]
- [[Prefix-Caching]]
- [[Disaggregation]]
- [[RDMA]]
- [[LLM-Inference]]

## 相关论文

- [[Seer-OSDI26]] — 用 Mooncake 层级 KV pool 保留 rollout request 迁移时的 prefix 状态。
- [[RollArt-OSDI26]] — 把 Mooncake CPU store 用于异构集群之间的权重更新。
- [[EcoServe-OSDI26]] — 给出普通 Ethernet 上 full disaggregation 的 crossover 证据。
- [[Strata-OSDI26]] — 从碎片 KV 传输和 ready-time 调度方面补充 Mooncake trace。
- [[LMetric-OSDI26]] — 在 cluster router 中同时权衡 prefix locality 与实例负载。
- [[fabric-lib-MLSys26]] — 比较 Mooncake Transfer Engine 与其他 GPU 通信后端。
- [[Bidaw-FAST26]] — 从本地 SSD 成本角度对比高速远程 KV 容量层。
