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

> **一句话总结**:在非抢占式线程架构下把 in-memory KVS 拆成「cache-resident」和「memory-resident」两层线程池，配合自动调优，在 YCSB 上相比 run-to-completion 基线取得 1.03-5.46× 吞吐提升。

## 问题

面向 >10M ops/s 的高速 KVS（使用 [[RDMA]]、DPDK 等用户态数据面），当前主流选择是 non-preemptive thread-per-queue (NP-TPQ) + run-to-completion 模型：每个 worker 线程从拉网络包、查索引、拷数据到发响应全部一条龙处理。这种 monolithic 函数在 tens of millions ops/s 场景下有两个固有问题：

- **Cache 不友好**：不同子任务访问模式迥异——网络 buffer polling 是小范围顺序访问、适合 DCA/DDIO 直达 LLC，而索引遍历和数据拷贝访问广阔内存，放一起会相互污染 cache。单次 cache miss 50-150ns，而一次 KV 操作仅几百 ns，cache thrashing 代价极大。
- **Skewed workload 下线程间冲突**：shared-nothing 下热点分片过载、share-everything 下锁争用加剧，二者都难以平衡。

传统 thread-per-stage (TPS, SEDA 风格) 在 preemptive 世界很成功但被认为不适合 non-preemptive 高速场景，因为 inter-stage 通信会吞掉收益。

## 核心方法

μTPS **重新拥抱 NP-TPS**，但不按功能切分，而是按 cache residency 二分：

- **Cache-resident (CR) 层**：pin 专用线程 + 专用 LLC way（通过 Intel CAT 分配），只管网络 buffer 和最热 KV items（10K 条）。用「hot set + 后台线程定期识别 + epoch 原子切换」，热集合大小通过 auto-tuner 动态调整。索引用 sorted array（range query）或复用主 hash table。
- **Memory-resident (MR) 层**：持有全量 index 和数据。用 C++20 stackless coroutine + prefetch 做 batched indexing 来摊销 cache miss；数据拷贝直接在 network buffer 和 KV storage 间做，不通过 CR-MR queue。
- **Reconfigurable RPC**：基于 RDMA Shared Receive Queue (SRQ) + Multi-Packet RQ (MP-RQ) 的单队列设计，worker 按 `m mod n = i` round-robin 取请求，调整线程数只需改一个全局变量 `n`，无需通知客户端。
- **CR-MR queue**：多生产者多消费者 lock-free ring buffer，每线程对之间专用；请求压到 16 字节、通过 tail 指针 piggyback 完成通知。
- **Auto-tuner**：hierarchical trisecting search，结合 convex 假设快速探索 thread allocation、cache size、LLC way 分配三维空间，整个重配置 0.9 秒完成且不阻塞请求处理。

## 关键结果

- 相比同架构 run-to-completion 基线 BaseKV：YCSB 各 workload 1.03-5.46× 吞吐；tree-based index 下读密集平均 1.29-1.30×，1KB 读提升达 43.53%
- 相比 eRPC-KV（shared-nothing 分片）：skewed 下吞吐显著更高、均匀负载下接近
- 对比 passive KVS RaceHash/Sherman：active 设计在大多数 workload 上大幅领先
- 系统基于 200Gbps RDMA，在 Meta ETC 池、Twitter traces 下 10-29% 吞吐提升
- 重配置对延迟影响可忽略（<10ms 监控窗口）

## 相关

- **相关概念**:[[KV-Store]]、[[RDMA]]、[[Thread-Per-Stage]]、[[LLC]]、[[DCA]]、[[Coroutines]]
- **同类系统**:[[MICA]]、[[FaRM]]、[[Memcached]]、[[eRPC]]
- **同会议**:[[SOSP-2025]]
