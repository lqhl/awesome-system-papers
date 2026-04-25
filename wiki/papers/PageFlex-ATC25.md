---
type: paper
name: PageFlex
full_title: "PageFlex: Flexible and Efficient User-space Delegation of Linux Paging Policies with eBPF"
authors: [Anil Yelam, Kan Wu, Zhiyuan Guo, Suli Yang, Rajath Shashidhara, et al.]
venue: ATC
year: 2025
tags: [memory-tiering, ebpf, paging, policy-delegation, linux-kernel]
source_pdf: "[[atc2025-yelam.pdf]]"
source_md: "[[atc2025-yelam]]"
---

# PageFlex: Flexible and Efficient User-space Delegation of Linux Paging Policies with eBPF (ATC 2025)

> **一句话总结**：用 eBPF 把 Linux page reclamation/prefetching 的策略外置到用户态、保留内核 swap stack，相比 g-swap 应用变慢 <1%，比 userfaultfd 快得多（zero-page fault 1.2 µs vs 5.6 µs），还能用 17 行代码把 Hyperbolic caching、21 行实现 Leap prefetching。

## 问题

Google g-swap、Meta TMO 等 hyperscaler 已经靠透明把"冷"页 offload 到 zswap/SSD 节省 20–30% 内存，但 Linux 内核的 LRU/MGLRU/read-ahead 策略与 Belady MIN 之间还有 14–37% 的可改进空间（在 1% refault rate 约束下）。新策略（Hyperbolic、LRB、Leap）发表多年没法部署：

- 写到内核要全 fleet rollout，Google 自己也只能月级别推送
- userfaultfd 把所有 page fault 路由到用户态，zero-page fault 从 1.2 µs 涨到 5.6 µs，还要重写整个 swap backend（zswap 共享、cgroup 计费等）
- AIFM/DiLOS 这类 user-level library 要改应用，且即使没 offload 也带来 40% 软件 indirection 慢化

## 核心方法

只把**非性能关键**的策略决策（reclamation 选哪些页 evict、prefetching 预测哪些页）外置，**保留**内核的 page fault handling 和 swap subsystem：

- **In-kernel eBPF event handlers**：tracepoint 追踪 OnPageAlloc/Free/Fault/Scanned，policy 订阅事件后 eBPF 处理器同步执行（<50 ns/调用）。每页在 page struct 预留 4 byte 给 eBPF 安全读写，免去用户态 hash map lookup
- **简化策略接口**：reclamation 用 `UpdateWeight(state, accessBit)` 周期更新每页权重；prefetching 用 `PredictTrend(page, isHit)`。LRU/LFU/Hyperbolic/Belady-MIN 都能套这个模板（17 行 Hyperbolic、33 行 MIN）
- **用户态 agent**：跑控制环路调阈值，用 `process_madvise` 批量发送 page-in/page-out hint（攒 64 页），通过 cgroup-based "enclave" 与默认内核策略并存
- **Region-aware specialization**：应用通过 IPC 把不同地址区间绑定到不同 sub-policy（如 KV store 的热/冷 region 用不同 LRU 阈值；GAPBS 顺序遍历区间用 read-ahead，随机 vertex 区间用 LFU）

深度细节回 [[atc2025-yelam]]。

## 关键结果

- Redis + memtier zipf(0.5)：PageFlex LRU vs g-swap kernel LRU，应用慢 <0.98%；emulated 4 µs userfaultfd 开销则慢 13.3%
- LFU on synthetic LFU-friendly workload：10% slowdown 下 LFU 41% swap usage vs LRU 20%（**2× 内存节省**）
- Hyperbolic caching 在 Memcached trace 上比 LRU 多 5% 内存节省
- Leap prefetching strided pattern：refault rate 比 Linux read-ahead 提升 75.4%
- Region-aware specialization：KV store 比 LRU 多 36% 内存节省、GAPBS PageRank 多 6%
- Page-table scan 的 eBPF 开销比纯内核高 17%；user-space madvise 比 kreclaimd 慢 14%（都不在 critical path）

## 相关

- **相关概念**：[[eBPF]]、[[Memory-Tiering]]、[[LRU]]、[[MGLRU]]、[[Prefetching]]、[[Userfaultfd]]
- **同类系统**：[[g-swap]]、[[TMO]]、[[AIFM]]
- **同会议**：[[ATC-2025]]
