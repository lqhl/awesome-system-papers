---
type: paper
name: OBASE
full_title: "OBASE: Object-Based Address-Space Engineering to Improve Memory Tiering"
authors: [Vinay Banakar, Suli Yang, Kan Wu, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau, Kimberly Keeton]
venue: OSDI
year: 2026
tags: [memory-tiering, address-space, object-migration, compiler-runtime, datacenter]
source_pdf: "[[osdi26-banakar.pdf]]"
source_md: "[[osdi26-banakar]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 用对象级地址空间工程改善内存分层（OSDI 2026）

> **原题**：OBASE: Object-Based Address-Space Engineering to Improve Memory Tiering

> **一句话总结**：数据中心活跃页中最多 97% 字节实际是冷数据且对象热度持续变化；OBASE 以 guide indirection、持续访问追踪和无锁迁移把 C/C++ 对象动态聚成 HOT/COLD 页，使不改动的 page-level backend 将 page utilization 提升 2–4×、RSS 最高降低 70%，代价为约 2–5% 吞吐开销。

## 问题与动机

内存分层（memory tiering）以 page 为迁移单位，而应用以大小不一的 object 为访问单位。allocator 不按未来热度布局对象，少量 hot bytes 会让整页看起来活跃，把周围 cold bytes 留在昂贵 DRAM。论文称此为热度碎片（hotness fragmentation）：Google 六类 workload 中只有 1.7%–21.3% bytes 被访问，但被触及的 pages 比例远高于此；现实部署因此只得到约 20%–32% memory saving，而非理论上的 80%–98%（图 1、§2.2）。

静态 hot/cold allocation 也不足够，因为同一 allocation site 会产生不同生命周期的对象，Meta/Twitter trace 中 key hotness 还会分阶段或 bursty 地变化（图 3）。OBASE 因而把“形成可回收页面”的 layout frontend 与决定 page 去向的 OS backend 解耦，目标是不修改 kswapd、TMO、TPP、Memtis 等机制，就提升它们看到的 page quality。

## 关键观察 / 隐含假设

- **观察 1**：被 OS 判为 active 的页面仍有 70%–90% bytes 没有访问；4 KB page 上也存在明显碎片，因此单纯缩小 huge page 或改进 page classifier 不能解决 sub-page 混放（§2.2、图 2）。
  - **依赖假设**：trace 的 cache-line access 能代表 tiering decision window 内的真实 hotness。
  - **可能失效场景**：对象尺寸接近/超过 page、访问天然按连续区域聚集时，重排空间较小。
- **观察 2**：对象热度无法在 allocation time 准确知道且随时间变化；64 B–4 KB 对象中 75% key 的 reuse spread 超过 5×、65% 超过 30×（§2.3）。
  - **依赖假设**：变化速度慢于 OBASE 默认 120 s scan 和迁移收敛周期。
  - **可能失效场景**：亚秒级 phase change 会让 cold classification 落后并触发 promotion。
- **假设 1**：latency-sensitive C/C++ 数据结构可接受 guide indirection，并满足 single ownership、无跨 operation raw pointer、无 pointer arithmetic。
  - **证据强度**：中；十种 concurrent structures 验证了多种同步方式，但 arrays、graphs、doubly-linked nodes 与通用 STL 语义明确不支持（§7）。
- **假设 2**：提升 page layout quality 能与未来 backend 正交组合。
  - **证据强度**：较强；六种 reclaim/tiering backend 均受益，但 OBASE hinted mode 还需要 kernel batching patch，并非所有效果都完全 backend-unmodified。

## 核心方法

OBASE 将逻辑 object identity 与地址分离。开发者标注可迁移 pointer field，Clang/LLVM pass 把它们改写为 `Guide<T>` 并在 public API 边界和 dereference 插入 tracking；guide 以 48-bit address 加 16-bit metadata 记录 access、heap、inactive windows、migration lock 与 active thread count（§3.2、§4.1/4.7）。

每次 dereference 用一次 atomic RMW 设置 access bit，常见 hot object 后续可跳过冗余写。SODA sparse bitmap 让后台 Object Collector 无需理解容器 graph 就能发现 guide。空间由 SAMA 分成连续 NEW、HOT、COLD heaps；连续 range 既改善 page purity，也允许 `MADV_COLD`/`MADV_PAGEOUT` 等 coarse-grained hint（图 4、§3.3–§3.4）。

分类用 consecutive inactive window（CIW）抑制短暂抖动。默认每 120 s 扫描，cold threshold 初始为三窗口，并以 1% promotion-rate target 做 additive adjustment；访问过的 COLD object 返回 HOT，长期 inactive object 被 demote（图 5、§4.4）。这直接回应“hotness 动态变化”的观察。

并发迁移采用 migration epoch、thread-local active scope guard（TAG）与 per-object active thread count（ATC）。ATC 只在 PREPARE/ACTIVE epoch 开启；当 ATC=0 时 collector 复制 object，并 CAS 更新唯一 guide。若 copy 期间发生访问，dereference 会改变 guide 状态，使 commit CAS 失败并回滚，应用线程不等待 collector（§3.5、表 1）。

为避免大批 `MADV_PAGEOUT` 产生逐页 TLB shootdown，作者还修改 Linux `shrink_folio_list()`，按最多一个 PMD（512 pages）批量清 PTE、flush TLB 与提交 I/O，回收 10 GiB 时 IPI 数减少超过 99%（§4.6）。

## 设计取舍

- **可迁移性换编程模型约束**：single guide ownership 使迁移只需原子更新一个 word，但 shared graph、doubly-linked structure、pointer arithmetic、跨 API 缓存 raw pointer 不再合法。
- **精确追踪换公共路径开销**：per-dereference RMW 提供 object-level signal，DRAM-only 吞吐平均下降 2.5%、p90 latency 增加 5%。
- **稳定性换响应速度**：CIW 和 120 s scan 减少误迁移，但对快速 phase change 响应滞后。
- **frontend 解耦并不完全零侵入**：基础 layout 可配合 unmodified backend；主动 pageout 的高效路径则依赖 kernel batching change。
- **边界条件**：unique-owned pointer-based records 最适合；contiguous arrays、matrix、packed columnar data 和需要稳定地址的 ABI 不适用。

## 实验与结果

- Google 六 workload trace 显示 active pages 中 70%–90% bytes 未访问；Tahoe/Yankee 的 median page utilization 约 3%，2 MB pages 中 Tahoe/Bravo/Yankee 有 85%–90% utilization 少于 10%（图 2）。
- 十种 concurrent data structures、YCSB 与多种 skew 下，OBASE 将 page utilization 提升 2–4×；MassTree footprint 从 12.4 GiB 降至 3.5–4.0 GiB，RSS 最高减少约 70%（§5.2）。
- MassTree YCSB-C、13 GiB footprint/约 4 GiB working set 下，Kswapd、Cgroup、TMO 配合 OBASE 均达到约 4 GiB RSS 且无吞吐下降；无 OBASE 的 Cgroup 虽达 4 GiB，却损失 38% throughput（图 9）。
- 67 GiB MassTree/YCSB-B、DRAM:[[CXL|CXL]] 从 1:4 到 1:16 时，OBASE 将 logical hot set 从 16.3 GiB/21% utilization 压到 6.33 GiB/57%；TPP 在 1:16 从 1.25× CXL-only 提升到 1.45×，Memtis 从 1.55× 到 1.7×（图 10）。
- 无 tiering backend 时，十种结构平均 throughput overhead 2.5%、p90 latency overhead 5%；2–32 threads 下开销保持 1%–8%，collector CPU 少于 1%（图 11）。
- Meta CacheLib、DBench Mixgraph、Twitter Cluster 7/23 trace 上 page utilization 提升 1.8–3.4×，OBASE Hinted 将 RSS 降低 36%–58%，在 TMO 之上额外节省 15%–30%（图 12）。
- Meta 2.3 小时 trace 中 controller 约 25 分钟把 threshold 从 3 调至 18，使 promotion rate 从 14% 降到 1% target 附近；后续 phase shift 后可再次收敛（图 13）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| page/object granularity gap 是显著的 production 现象 | 图 1/2、§2.2 | Google 六 workload、估计最长约 30 s trace | 强 |
| 动态重排优于 allocation-time placement | 图 3、§2.3 | Meta/Twitter key traces、10M operations/time bucket | 中 |
| OBASE 让多种 page backend 更有效地回收/分层 | 图 9/10 | MassTree、YCSB-C/B、paging 与三种 tiering backend | 强 |
| 常态 tracking 与迁移开销较低且不随 32 threads 恶化 | 图 11、§5.4 | 十种结构；scaling 只测三种结构、最多 32 threads | 强 |
| 对 production-style access pattern 仍能适应 | 图 12/13 | 四条公开 trace，其中长时 adaptation 展示 Meta 一条 | 中 |

## 批判性分析

### 论证链条

论文先量化 hotness fragmentation，再证明 hotness churn，随后把二者映射到 continuous classification 和 migration，最后跨多个 backend 验证，逻辑闭环清晰。最大跳步是把 key-level trace 与 object/page physical layout 关联：Google trace 直接支持 page fragmentation，而 Meta/Twitter 的 key trace主要支持时间变化，二者并非同一应用的端到端因果证据。

### 假设压力测试

论文明确承认 stable pointer、multiple ownership 与 pointer arithmetic 不兼容。这不是普通 engineering limitation，而是采用 single-guide CAS 获得低成本迁移的核心前提。快速 hot-set oscillation、对象被短时借用后跨 operation 缓存、超过 128 threads 同时触及同一 object，以及 high address bits 被 LAM/TBI/HWASAN 占用时，协议或编码需要重设计。

### 实验可信度

评测同时覆盖 synthetic/production traces、十种 data structures、reclamation/tiering backend、RSS、throughput、p90 latency 与 scalability，baseline 和 ablation 较完整。不过多数应用承载于 CrestDB，无法代表大型现有 C++ service 的 annotation/porting difficulty；scaling 上限 32 threads 也弱于 hyperscale server 的常见 core count。Google trace duration 是按 instruction/core 假定估算，可能影响冷热窗口解释。

### 系统性缺陷

编程错误如 hidden raw alias 可能破坏 correctness，compiler validation 能拒绝部分 pattern，却无法证明整个 C++ 程序无逃逸 alias。论文未量化 source annotation、debugger/profiler compatibility、failure recovery、fork/checkpoint、[[NUMA|NUMA]] placement 与 collector stalled 的运维影响。kernel batching patch 也扩大部署面和维护成本。

## 局限与后续工作

- **局限 1**：只支持 unique-owned pointer-based object；graphs、doubly-linked lists、arrays/matrices 和 stable-address API 不支持（§7）。
- **局限 2**：2–32 threads 的 scaling 证据不足以覆盖 128-core hyperscale server，ATC 仅用 7 bits 也把单对象并发上限编码为 128。
- **局限 3**：采用 120 s scan，快速 workload phase 的 transient tier miss 和 tail latency 未被系统评测。
- **后续工作 1**：用真实大型 C++ service 统计需要 annotation 的 pointer fields、validation reject rate、移植工时与 hidden-alias bug 数量。
- **后续工作 2**：扫过 1 s–120 s hot-set phase、不同 scan interval 和 promotion target，测量错误 demotion、swap-in、p99/p99.9 latency 与 memory saving 的 Pareto frontier。
- **后续工作 3**：在 128+ threads、NUMA/CXL 多节点上比较 centralized collector 与 per-NUMA collector，并验证 high-bit metadata 与 LAM/HWASAN 的组合方案。

## 相关

- **相关概念**：[[Memory-Tiering]]、[[CXL-Memory]]、[[Hotness-Fragmentation]]、[[Object-Migration]]、[[Epoch-Based-Reclamation]]
- **同类系统**：[[TMO]]、[[TPP]]、[[Memtis]]、[[AIFM]]、[[Alaska]]
- **同会议**：[[OSDI-2026]]
