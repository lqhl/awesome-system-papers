---
type: paper
name: uTPS
full_title: "Rearchitecting the Thread Model of In-Memory Key-Value Stores with μTPS"
authors: [Youmin Chen, Jiwu Shu, Yanyan Shen, Linpeng Huang, Hong Mei]
venue: SOSP
year: 2025
tags: [kvs, thread-architecture, cache-efficiency, rdma, in-memory]
source_pdf: "[[3731569.3764794.pdf]]"
source_md: "[[3731569.3764794]]"
---

# Rearchitecting the Thread Model of In-Memory Key-Value Stores with μTPS (SOSP 2025)

> **一句话总结**：在 >10M ops/s 的 [[RDMA]] in-memory [[KV-Store]] 中，NP-TPQ run-to-completion 会把网络 polling 与索引/数据拷贝混在同一 monolithic 函数里导致 cache thrashing；μTPS 按 cache residency 二分 CR/MR 两层线程池并配合 reconfigurable RPC 与 auto-tuner，在 YCSB 上相对 RTC 基线取得 1.03–5.46× 吞吐提升。

## 问题与动机

面向 tens of millions ops/s 的 in-memory [[KV-Store]]（[[RDMA]]/DPDK 用户态数据面），主流 [[Thread-Per-Queue]] run-to-completion 把 polling、索引遍历、数据拷贝串在同一 worker 上。作者测量表明：单次 cache miss 50–150ns，而一次 KV 操作仅几百 ns，异构子任务混跑会严重污染 [[LLC]]；skewed workload 下 shared-nothing 分片过载、share-everything 锁争用也难平衡。传统 [[Thread-Per-Stage]] 在抢占式世界成功，但被认为 non-preemptive 高速场景下 inter-stage 通信开销过大而不适用——μTPS 要反驳这一共识。

## 关键观察 / 隐含假设

- **观察 1**：把 network buffer polling 与 index/data access 分到不同线程池后，即使去掉 inter-stage queue 开销，NP-TPS 仍比 NP-TPQ 高 1.22–1.54× 吞吐；polling 线程 [[LLC]] miss 约 2% vs TPQ 的 33%。
  - **依赖假设**：[[DCA]]/DDIO 使 network buffer 适合驻留 LLC；索引/拷贝访问广阔内存是 miss 主因。
  - **可能失效场景**：item 极大、索引结构极深，或 CR 层 hot set 识别不准时，MR 层仍主导延迟。
- **观察 2**：skewed workload 下把 0.1‰ 最热 key 路由到专用线程池，MassTree lookup 吞吐平均 +8%；put 场景 NP-TPS 在 share-everything 争用下仍优于 SN/SE 的 NP-TPQ。
  - **依赖假设**：热点可在线识别且规模可控（默认 10K items）；[[Intel-CAT]] 能隔离 LLC way。
  - **可能失效场景**：热点快速漂移或 Zipf 参数变化时，epoch 切换 hot set 可能滞后。
- **假设 1**：按 cache residency 二分只需 CR↔MR 一条轻量队列，inter-stage 开销可被收益覆盖。
  - **证据强度**：中；§2.2 实验在零通信 replay 下成立，完整系统靠 16B 压缩请求 + 专用 queue 设计缓解。

## 核心方法

μTPS 将 KVS 分为 **cache-resident (CR)** 与 **memory-resident (MR)** 两层：CR 用 pinned 线程 + 专用 LLC way 管理 network buffer 与 hot KV；MR 持有全量 index，用 C++20 stackless [[Coroutines]] + batched prefetch 摊销 miss。数据拷贝直接在 network buffer 与 storage 间完成，不经 CR-MR queue。

**Reconfigurable RPC**：基于 [[RDMA]] SRQ + MP-RQ 单队列接收，worker 按 `m mod n = i` round-robin 取请求，改线程数只需更新全局 `n`，无需通知客户端。**Resizable cache**：后台线程用 count-min sketch + min heap 识别 hot set，epoch 原子切换；tree index 用 sorted array，hash index 复用主表。**Auto-tuner**：hierarchical trisecting search 联合调 thread、cache size、LLC way，重配置约 0.9s 且不阻塞请求。

实现 μTPS-H（libcuckoo）与 μTPS-T（MassTree），基于 200Gbps [[RDMA]]。

## 设计取舍

- **取舍 1**：放弃经典按功能切多 stage，只保留 CR/MR 二分 → 降低 queue 频率，但 workload-dependent 阶段（如 index vs copy）需进一步按热度拆分。
- **取舍 2**：hot set 过大反而有害（CR-MR 性能差距非 DRAM/HDD 量级）→ 动态限制 hot set 规模。
- **边界条件**：uniform/hash index、低 skew 时收益 modest（1.03× 量级）；读密集 tree index、1KB value 场景收益最大（至 43.53%）。

## 实验与结果

- YCSB 各 workload：相对 RTC 基线 BaseKV **1.03–5.46×** 吞吐；tree index 读密集平均 **1.29–1.30×**
- 相对 eRPC-KV（shared-nothing）：skewed 显著更高，均匀负载接近
- 相对 passive KVS RaceHash/Sherman：active 设计大多数 workload 大幅领先
- Meta ETC 池、Twitter traces：**10–29%** 吞吐提升
- 重配置对延迟影响可忽略（<10ms 监控窗口）

## Critical Analysis

### 论证链条

观察（LLC miss 分化 + 热点可隔离）→ 按 cache residency 二分 + 硬件资源绑定 → YCSB/生产 trace 吞吐提升，逻辑基本闭合。弱点在于 §2.2「无 inter-stage 通信」实验与完整 μTPS 之间的跳步：真实 CR-MR queue 在极端 skew 或线程数频繁变化时是否仍占优，论文用 auto-tuner 和轻量 queue 设计论证但未给出与「理想 NP-TPS」的 ablation 差距上界。

### 假设压力测试

- **硬件**：依赖 [[Intel-CAT]]、DDIO 行为、200Gbps [[RDMA]]；AMD/其他 NIC 上 reconfigurable RPC 语义需重验证。
- **Workload**：Twitter/Meta trace 有支持，但跨租户隔离、多租户混部下 auto-tuner 稳定性论文未充分讨论。
- **规模**：>10M ops/s 测量在特定集群；更小规模可能 thread 划分收益不足以摊销复杂度。

### 实验可信度

YCSB + 生产 trace + PCM LLC 计数器较完整；eRPC-KV、RaceHash 等基线合理。缺少与 ShRing/Iat/CacheDirector 等「不改 thread 架构只优化 cache」方案的 head-to-head。latency 声称「comparable」但尾延迟、P99 在 skew 突变时覆盖不足。

### 系统性缺陷

auto-tuner 与 reconfigurable RPC 增加运维与调试复杂度；论文未讨论故障恢复、多 NUMA 节点扩展、与 kernel bypass 栈以外网络栈的兼容性。CR 层 FSM 异步等待 MR 响应时的尾延迟行为需生产环境长期观察。

## 局限与 Future Work

- **局限 1**：hash/uniform workload 收益有限，作者承认但认为大规模下微小改进仍有成本价值。
- **局限 2**：inter-stage 通信在极端配置下仍可能抵消收益（§2.3 已讨论）。
- **Future work 1**：在更多 NIC/CPU 代际上测量 DDIO + CAT 与 NP-TPS 收益的解耦，明确「thread 二分」vs「仅 cache 分区」的边际贡献。
- **Future work 2**：将 auto-tuner 与云侧弹性扩缩容联动，测量 skew 漂移时的 SLO 违反率。

## 相关

- **相关概念**：[[KV-Store]]、[[RDMA]]、[[Thread-Per-Stage]]、[[LLC]]、[[DCA]]、[[Coroutines]]、[[Intel-CAT]]
- **同类系统**：[[MICA]]、[[FaRM]]、[[Memcached]]、[[eRPC]]
- **同会议**：[[SOSP-2025]]