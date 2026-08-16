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
last_reviewed: 2026-08-14
---

# 用对象级地址空间工程改善内存分层（OSDI 2026）

> **原题**：OBASE: Object-Based Address-Space Engineering to Improve Memory Tiering

> **一句话总结**：操作系统按 page 分层，应用却按 object 访问，少量热对象会把大量冷字节困在 DRAM；OBASE 用可重定向的 `Guide`、持续热度追踪和并发对象迁移，把对象重新聚成 HOT/COLD 页面，使现有 page-level backend 的 page utilization 提升 2–4 倍、RSS 降低 65%–72%，平均吞吐代价为 2.5%。

## 问题与动机

内存分层（memory tiering）的管理单位通常是 4 KB 或 2 MB page，而 C/C++ 服务真正访问的是大小、生命周期和热度都不同的 object。普通 allocator 只看分配时间，不知道对象未来是否会被访问，因此一个 page 往往同时放着少量热对象和大量冷对象。只要热对象继续被访问，操作系统就不能安全地把整页移到慢内存或 swap。论文把这种现象称为热度碎片（hotness fragmentation）。

作者分析 Google 六类 workload 的 cache-line trace：实际被访问的字节只占 1.7%–21.3%，但访问分散到大量页面中；在部分 workload 中，活跃页里最多约 97% 的字节仍然是冷的。Tahoe 和 Yankee 的 page-utilization 中位数约为 3%，说明问题并不只是 huge page 太大，4 KB page 内也存在严重混放（§2.2、图 1–2）。

把对象在 allocation time 静态分成 hot/cold 也不够。Meta 和 Twitter trace 中，64 B–4 KB 的中等对象占 94% 和 98.2%；75% key 的 reuse spread 超过 5 倍，65% 超过 30 倍，说明热度会随时间和阶段变化（§2.3、图 3）。OBASE 因此不尝试替代 kswapd、TMO、TPP 或 Memtis，而是先把进程地址空间整理成“更容易被 page backend 判断”的形状。

## 关键观察 / 隐含假设

- **观察 1：page-level hotness 不能代表 page 内所有 object 的热度。** Google trace 中，活跃页仍有 70%–90% 字节未访问；在 2 MB page 下，Tahoe、Bravo 和 Yankee 有 85%–90% 的页面利用率少于 10%（§2.2、图 2）。
  - **依赖假设**：64 B cache-line trace 和论文估算的最长约 30 秒观察窗口，足以代表实际 tiering 决策中的 working set。
  - **可能失效场景**：对象本身接近一页、访问天然连续，或 workload 的热集变化远快于采样窗口时，可整理空间会变小。
- **观察 2：对象热度需要持续学习，不能由 allocation site 一次决定。** 相同数据结构中的 key 会出现不同复用周期和 phase shift（§2.3、图 3）。
  - **依赖假设**：大多数 phase 持续时间长于 OBASE 的扫描和收敛时间。
  - **可能失效场景**：亚秒到数秒级热集振荡会让 120 秒扫描明显落后，刚被放入 COLD 的对象可能很快又被访问。
- **假设 1：目标 C/C++ 数据结构能接受一层 `Guide` 间接寻址。** OBASE 要求对象由单一 guide 拥有，不允许跨 public operation 保存 raw pointer，也不支持 pointer arithmetic。
  - **证据强度**：中。论文移植了十种 lock-free、细粒度锁、粗粒度锁和 OCC 数据结构，但明确排除了通用 graph、双向链表、连续 array/matrix 和需要稳定地址的接口（§4.1、§7）。
- **假设 2：先提高页面“纯度”，现有 backend 就能作出更好的迁移决定。** OBASE frontend 本身不决定 page 去向。
  - **证据强度**：较强。paging、cgroup、TMO、TPP、AutoNUMA 和 Memtis 都获得收益；不过主动 hint 的可扩展实现另有 Linux kernel patch，不能把所有结果都理解成完全零侵入（§4.6、§5.3）。

## 核心方法

OBASE 先把 object identity 与物理地址分开。开发者只标注需要管理的 pointer field，Clang pass 将其改成 `Guide<T>`；LLVM pass 再沿 call graph 找出接触 guide 的函数，在 public API 入口/出口插入 TAG 管理，在每次 guide dereference 前插入追踪。这样 caller 只传普通 key 或 value，不会直接持有 guide，迁移协议被限制在数据结构内部（§4.7、图 7）。

一个 guide 仍占 64 bit：低 48 bit 保存对象地址，高 16 bit 保存 access bit、迁移锁、heap id、连续未访问窗口（CIW）和 active-thread count（ATC）。每次解引用通过 atomic read-modify-write 设置 access bit；对象已经标记为热时可跳过重复写。SODA 用稀疏 bitmap 找到有效 guide，避免后台 collector 理解每种容器的内部拓扑（§3.2、§4.2）。

SAMA 把地址空间划成连续的 NEW、HOT 和 COLD heap。新对象先进入 NEW；collector 定期扫描 access bit，把持续活跃对象放入 HOT，把连续多个窗口未访问的对象放入 COLD。连续的 COLD range 可直接交给 page backend，也可在 hinted mode 中用 `MADV_COLD` 或 `MADV_PAGEOUT` 主动提示内核（§3.3–§3.4、图 4–5）。

分类器默认每 120 秒扫描一次，cold threshold 初始为 3 个窗口。controller 以 1% promotion rate 为目标：冷对象过快回热就提高 threshold，过于保守就降低 threshold，每轮加减 1，并限制在 1–32 个窗口。它要优化的不是“预测每个对象下一次访问”，而是把错误 demotion 控制在 backend 可接受的范围内（§3.4、§5.5）。

并发迁移使用 migration epoch、线程本地 TAG 和 guide 内 ATC。collector 先进入 PREPARE，让后续 public operation 开始登记；所有旧 operation 退出后进入 ACTIVE。只有 ATC 为 0 时才复制对象并用 CAS 提交新地址。如果复制期间应用再次解引用该 guide，访问路径会修改 guide 状态，collector 的 CAS 失败并回滚，因此应用线程不需要等待迁移线程（§3.5、图 6）。

OBASE 的基本 frontend 可以配合未修改的 page backend。为了让大范围主动 pageout 不被逐页 TLB shootdown 拖垮，作者还修改 `shrink_folio_list()`，按最多一个 PMD、即 512 pages 批量清 PTE、flush TLB 和提交 I/O；回收 10 GiB 时，IPI 数量下降超过 99%（§4.6）。这是 hinted fast path 的额外部署成本。

## 设计取舍

- **低成本迁移换严格 ownership**：一个对象只有一个可更新 guide，CAS 提交很简单；shared graph、双向边、隐藏 raw alias 和稳定地址 ABI 因而不适用。
- **精细信号换访问路径开销**：每次 guide dereference 都可能做 atomic RMW。它比 page sampling 更精确，但在纯 DRAM、无内存压力的理想 baseline 上仍会降低吞吐。
- **稳定分类换响应速度**：CIW 和 120 秒窗口减少误迁移，却会延迟跟踪快速 phase change。
- **地址内联 metadata 换兼容性**：高 16 bit 让 guide 保持 8 bytes，但可能与 LAM、TBI、HWASAN 等高地址位用途冲突；ATC 的 7 bit 也把单对象并发计数限制在 128。
- **frontend/backend 解耦并非完全零修改**：只做对象聚类时可复用原 backend；高效的主动 pageout 还依赖 madvise 和 kernel batching patch。

## 实验与结果

- **对象聚类能产生真正可回收的冷页**：CrestDB 中十种 concurrent data structure、10M keys、约 13 GiB 数据集上，初始 page utilization 只有 18%–20%；三轮扫描后，YCSB-A 提高约 2 倍、YCSB-B 约 3 倍、YCSB-C 最高 4 倍，绝对利用率约为 40%–80%。系统通常在 3–4 个扫描窗口、即 6–8 分钟内收敛；主动 pageout 后 RSS 降低 65%–72%，YCSB-B 的 baseline 12.4 GiB 降到 3.5–4.0 GiB（§5.2、图 8）。
- **改善了回收 backend 的性能—容量取舍**：MassTree/YCSB-C 中，13 GiB footprint 只有约 4 GiB working set。无 OBASE 时，cgroup 虽压到 4 GiB，却损失 38% 吞吐；有 OBASE 后，kswapd、cgroup、TMO 和 hinted mode 都接近 4 GiB，且论文未观察到吞吐下降（§5.3.1、图 9）。
- **改善了内存分层 backend**：50M keys、67 GiB MassTree/YCSB-B 中，逻辑 hot set 从 16.3 GiB、21% utilization 压缩为 6.33 GiB、57%。在最紧张的 1:16 fast:slow capacity ratio 下，TPP 从 slow-tier baseline 的 1.25 倍提高到 1.45 倍，Memtis 从 1.55 倍提高到 1.70 倍（§5.3.2、图 10）。实验慢层实际是单独 NUMA node 上的 Optane PMEM，延迟约为 DRAM 的 2.5 倍，用来近似早期 CXL memory，并不是真实 CXL 设备。
- **常态开销较小但不是零**：十种结构平均吞吐下降 2.5%，p90 latency 上升 5%；不同结构的吞吐损失为 1.5%–5%。三种结构在 2–32 threads 下开销保持 1%–8%，collector 使用少于 1% CPU（§5.4、图 11）。
- **公开 production trace 上仍有收益**：Meta CacheLib、DBench Mixgraph、Twitter Cluster 7/23 replay 中，page utilization 提高 1.8–3.4 倍；OBASE Hinted 相对不回收降低 RSS 36%–58%，OBASE+TMO 相对 TMO alone 再节省 15%–30%（§5.5、图 12）。
- **controller 能跟随小时级变化**：Meta 2.3 小时 trace 启动时 promotion rate 为 14%；约 25 分钟内 threshold 从 3 提到 18，promotion rate 降到 1% 目标附近。约 5400 秒发生 phase shift 后，threshold 在 10–20 个窗口之间再次收敛（§5.5、图 13）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| page/object 粒度差异是明显的真实问题 | Google 六 workload 的 cache-line trace；活跃页中 70%–90% 字节未访问（图 1–2） | trace 最长时间由 instruction/core 假设估算为约 30 秒 | 强 |
| 动态 object clustering 能提高 page quality | 十种数据结构、三类 YCSB 中 page utilization 提高 2–4 倍（图 8） | 应用统一承载在作者实现的 CrestDB 中 | 强 |
| 更纯的页面能让多种既有 backend 作出更好决定 | kswapd、cgroup、TMO、TPP、AutoNUMA、Memtis 的组合实验（图 9–10） | tiering 慢层是 Optane PMEM 模拟环境，不是真实 CXL | 强 |
| 追踪和迁移开销在实验规模内可控 | 平均吞吐下降 2.5%，2–32 threads 下为 1%–8%（图 11） | 并发扩展只测三种结构，最高 32 threads | 强 |
| feedback controller 能适应长期 workload 变化 | Meta CacheLib 2.3 小时 trace 中两次收敛（图 13） | 长期动态曲线只展示一条 trace | 中 |

## 批判性分析

### 论证链条

论文的因果链较完整：先证明 page 中存在冷热混放，再证明 object hotness 会变化，然后设计持续追踪和迁移，最后证明页面整理能帮助多个 backend。最需要谨慎的跳步是两类 trace 的角色不同：Google trace 直接支持物理 page fragmentation，Meta/Twitter 的 key trace 主要支持热度变化；它们不是同一生产服务上的端到端验证。

### 假设压力测试

OBASE 的核心不是普通 allocator 优化，而是改变 C/C++ pointer 语义。只要存在 guide 之外的长期 alias、跨 operation 保存的 raw pointer、pointer arithmetic 或双向 ownership，迁移后的旧地址就可能继续被使用。compiler pass 可以捕获部分语法模式，却很难证明整个大型 C++ 服务没有隐藏 alias。快速热集振荡和单对象超过 128 个并发访问者，也会压力测试分类器和 guide 编码。

### 实验可信度

实验覆盖 production trace、十种数据结构、paging 与 tiering backend、吞吐、RSS、p90 latency 和 thread scaling，证据比只展示内存节省完整。两个重要边界是：多数端到端实验都在 CrestDB 中完成，不能直接代表成熟服务的移植难度；所谓 CXL-like tier 使用 Optane PMEM，因此结论更准确地说是“page quality 对分层普遍有帮助”，而不是已经验证了真实 CXL 设备的全部行为。

### 系统性缺陷

部署面同时包括 compiler、runtime、allocator 语义、可选 madvise 和 kernel patch。论文没有量化 annotation 数量、移植工时、debugger/profiler 兼容性、fork/checkpoint、异常恢复或 collector 失败后的行为。高地址位 metadata 与现有 sanitizer/architecture feature 的冲突，也会影响生产环境是否能直接采用。

## 局限与后续工作

- **局限 1**：只适合 unique-owned、pointer-based object；连续 array、matrix、packed columnar layout、graph、双向链表和 stable-address API 不支持（§7）。
- **局限 2**：默认 120 秒扫描，快速 phase shift 的错误 demotion、swap-in 和 p99/p99.9 latency 没有系统测量。
- **局限 3**：扩展性只到 32 threads；guide 的 ATC 编码和单 collector 设计尚未覆盖 128+ core、multi-socket 服务器。
- **后续工作 1**：在真实大型 C++ 服务中记录 annotation 数、compiler reject rate、hidden-alias bug、移植工时和线上回滚成本。
- **后续工作 2**：扫描 1–120 秒 phase、scan interval 和 promotion target，联合测量错误 demotion、page-in、内存节省和 p99.9 latency 的 Pareto frontier。
- **后续工作 3**：在真实 CXL memory、128+ threads 和多 [[NUMA]] node 上比较单 collector 与 per-node collector，并验证 LAM/HWASAN 兼容编码。

## 相关

- **相关概念**：[[CXL]]、[[NUMA]]
- **相关论文**：[[MemoryTrap-ATC25]]、[[ScaleSwap-FAST26]]
- **同会议**：[[OSDI-2026]]
