---
type: paper
name: RTSFaaS
full_title: "Towards High-Performance Transactional Stateful Serverless Workflows with Affinity-Aware Leasing"
authors: [Jianjun Zhao, Haikun Liu, Shuhao Zhang, Haodi Lu, Yancan Mao, et al.]
venue: ATC
year: 2025
tags: [serverless, faas, rdma, transactional, concurrency-control]
source_pdf: "[[atc2025-zhao-jianjun.pdf]]"
source_md: "[[atc2025-zhao-jianjun]]"
---

# Towards High-Performance Transactional Stateful Serverless Workflows with Affinity-Aware Leasing (ATC 2025)

> **一句话总结**：基于 affinity-aware lease + 单边 [[RDMA]] 动态租约转移的事务性 serverless 框架，相比 Boki / Beldi 吞吐分别提升 5× / 20×，且即使把对手的 CC 协议适配到 RDMA 也仍快 1.7× / 2.1×。

## 问题

Stateful FaaS 需要在多函数 workflow（如 banking 中 withdraw → deposit）间保证事务一致性。Beldi（2PL）/ Boki（OCC）/ T-Statefun 等依赖远端 datastore 做 lock 管理与冲突验证，频繁远端通信开销大；本地 cache 因为 lock 必须远端获取或 OCC 频繁 abort 而效果受限——即便上 RDMA，CC overhead 仍是主要瓶颈。

## 核心方法

提出 lease-based 并发控制：每个对象在分布式 cache 中只有一个独占副本（leaseholder 持有），允许大多数事务以"对 cached object 的强亲和"执行。

- **Affinity-aware Lease Assignment**：driver 维护统计表记录每 worker 对每个 KV object 的访问频次，新请求到来时综合 affinity score $A_i = \sum N_i(k_j)$ 和 load balancing score 给请求选 worker；批结束后把 key 的 lease 重新指派给访问频次最高的 worker，让函数尽量本地命中 cache。
- **Planning–Execution 解耦**：planning 阶段每 worker 用 Function Timestamp 识别 temporal dependency 与 parametric dependency，构建 local TPG 并通过广播虚拟 vertex 拼成 global TPG（保证 conflict-serializable）。
- **RDMA-capable Dynamic Lease Transfer**：execution 阶段只 leaseholder 能 prefetch 与控制对象访问；远端访问对象时用单边 RDMA write 拉数据并比对 lease flag，再通过更新 lease flag 把租约让给目标 worker。Push-based circular buffer + Chandy-Lamport 风格 transition flag 保证 batch 切换一致性。
- **Fault Tolerance**：snapshot + lightweight log 协助恢复，故障时回退到上一 snapshot 重放本批次。

详见 [[atc2025-zhao-jianjun]]。

## 关键结果

- Movie Review / Travel Reservation / Banking workload 上：相比 Boki 吞吐 2.0×–5.0×，相比 Beldi 6.0×–20×（700ms 中位延迟下）。
- 把 Boki / Beldi 的 CC 协议移植到 RDMA 后再比较，RTSFaaS 仍快 1.7× / 2.1×。
- 把 5 节点 cluster + TiKV 后端，单 RDMA 操作 RTT 7µs。

## 相关

- **相关概念**：[[RDMA]]、[[Serverless]]、[[Concurrency-Control]]
- **同会议**：[[ATC-2025]]
