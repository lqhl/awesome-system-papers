---
type: concept
aliases: [Function-as-a-Service, FaaS-Platform]
last_updated: 2026-07-30
tags: [cloud, faas, isolation, scheduling]
---

# Serverless

> 无服务器计算（serverless computing）按需创建和调度短生命周期执行单元，把机器管理隐藏在平台后，同时把冷启动、状态、隔离与细粒度计费变成核心系统问题。

## 核心思想

平台接收 function/task invocation，选择或创建 sandbox，装载代码/状态，执行后回收或缓存环境。实现可用 process、container、MicroVM、WebAssembly 或专用 runtime；“serverless”描述资源与运营抽象，不等于无服务器或无状态。

新一代工作把 serverless 原则扩展到 batch task 与 continuation：资源只在真正计算时分配，I/O wait、slot idle 和固定 executor reservation 不再伪装成忙碌。

## 为什么重要

细粒度弹性能回收 idle capacity，却使 sandbox creation、snapshot restore、control-plane QPS、remote shuffle/state 和 tail variance 成为瓶颈。平台必须证明节省的 compute 大于启动与状态迁移成本，并把 isolation、failure semantics 和计费边界纳入端到端评估。

## 关键观察 / 隐含假设

- **process snapshot 的结构不同于传统 checkpoint**：[[Spice-OSDI26]] 发现 snapshot 是 sparse/reordered overlay；bulk metadata restore 和 page-cache sharing 可接近 warm start，但 container/namespace setup 不在其 critical path 数字内。
- **batch allocation 不等于有效利用**：[[Quark-OSDI26]] 在生产 Spark 中发现只有 67% allocated CU 做有效计算；task-level serverless 可节省平均 42.68% CU，却增加 control-plane 与 task-time variance。
- **continuation 可进一步拆开 compute 与 I/O**：[[Arca-OSDI26]] 用微秒级 continuation capture 将 monolithic program 自动切为 effects/funclets，但牺牲完整 POSIX 与 shared-memory compatibility。
- **serverless reward 适合 bursty agentic RL**：[[RollArt-OSDI26]] 认为 stateless reward 与短 remote I/O 适合 FaaS；隐含条件是 invocation/cold-start 和 dollar cost 低于长期预留 GPU。
- **隔离选择决定冷启动与 TCB**：[[Dandelion-SOSP25]]、[[Aegaeon-SOSP25]]、[[PhoenixOS-SOSP25]] 展示 process、runtime 与 VM 路线的不同边界。

## 设计空间与取舍

- **环境复用**：warm latency 低，但跨租户残留状态与容量占用更复杂。
- **snapshot/restore**：[[Spice-OSDI26]] 降低初始化成本，代价是 snapshot validity、external state 与 working-set prediction。
- **task-level batch**：[[Quark-OSDI26]] 回收 executor idle，但放大调度、remote data 和 sandbox throughput 要求。
- **continuation-centric**：[[Arca-OSDI26]] 暴露动态 dependency，代价是新的 OS/API 与 compatibility 缺口。

## 引用本概念的论文

- [[Spice-OSDI26]] — 以 process snapshot 和 bulk restore 实现 near-warm cold start。
- [[Quark-OSDI26]] — 将 serverless task allocation 用于共置 Spark batch workload。
- [[Arca-OSDI26]] — 把 continuation capture 作为 serverless OS primitive。
- [[RollArt-OSDI26]] — 用 serverless reward service 吸收 agentic RL burst。
- [[Dandelion-SOSP25]] — 探索细粒度 serverless execution 与 data dependency。
- [[Aegaeon-SOSP25]] — 研究 serverless isolation/执行环境的资源取舍。

## 已知局限 / 开放问题

- 将 snapshot、network、storage、control-plane 和 billing 全部计入 cold-start/TCO。
- 为 socket、device、timer、multi-process 与 mutable shared state 定义恢复语义。
- 在 burst/adversarial arrival 下保证 p99、公平性和 capacity protection。
- 明确 task/continuation retry 的 exactly-once effect 与数据一致性。
