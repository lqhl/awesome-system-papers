---
type: paper
name: PageFlex
full_title: "PageFlex: Flexible and Efficient User-space Delegation of Linux Paging Policies with eBPF"
authors: [Anil Yelam, Kan Wu, Zhiyuan Guo, Suli Yang, Rajath Shashidhara, Wei Xu, Stanko Novakovic, Alex C. Snoeren, Kimberly Keeton]
venue: ATC
year: 2025
tags: [memory-tiering, ebpf, paging, policy-delegation, linux-kernel]
source_pdf: "[[atc2025-yelam.pdf]]"
source_md: "[[atc2025-yelam]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# PageFlex：使用 eBPF 灵活高效地在用户空间委派 Linux 分页策略（ATC 2025）

> **原题**：PageFlex: Flexible and Efficient User-space Delegation of Linux Paging Policies with eBPF

> **一句话总结**：hyperscaler 的 proactive memory offloading（[[g-swap]]/[[TMO]]）仍受限于内核 [[LRU]]/read-ahead，与 Belady MIN 在 1% refault 约束下差 14–37%；PageFlex 用 [[eBPF]] 把 reclamation/prefetching **策略**外置到用户态、保留内核 swap stack，Redis 上比内核 LRU 仅慢 <1%，17 行实现 Hyperbolic caching、Leap prefetching 在 strided 访问上 refault 改善 75.4%。

## 问题与动机

内存成本在 hyperscaler TCO 中持续上升。Google [[g-swap]]、Meta [[TMO]] 等系统通过把"冷"页透明 offload 到 zswap 或 NVMe SSD，在几乎不影响应用性能的前提下节省 20–30% 内存。这些部署的核心是 **page reclamation policy**（推断哪些页冷、何时 offload）和 **prefetching policy**（在 refault 前把页拉回），二者直接决定 memory savings 与 refault 代价的 tradeoff。

作者 claim 的痛点不是 swap 机制本身，而是 **策略演进太慢、太脆**：

1. **内核策略空间窄**：生产环境依赖 [[LRU]]/active-inactive list、[[MGLRU]]、per-page age（g-swap）和 Linux 默认 sequential read-ahead；文献中的 Hyperbolic caching、Leap、LRB 等难以进入 fleet。
2. **内核改动部署成本高**：Google 自身经验表明 kernel rollout 月级别都"不被容忍"（类比 [[GhOSt]] 对调度的外置）；实验性、workload-specific 策略更难 upstream，只能维护 fork。
3. **完全外置 paging 代价太大**：[[Userfaultfd]] 把所有 page fault 路由到用户态，zero-page fault 从 1.2 µs 涨到 5.6 µs（相对 zswap 6 µs median 增加 >50%），且无法复用内核 zswap、cgroup swap accounting、swap device sharing。[[AIFM]]/[[DiLOS]] 等 library 方案要改应用，即使无 offload 也有高达 40% 的软件 indirection 开销。

论文核心问题：**能否在不拖慢应用、不改应用代码、不重写 swap 基础设施的前提下，把 paging policy 外置到用户态？** PageFlex 的答案是：只外置非性能关键的策略决策，用 eBPF 在内核事件路径上低开销执行 policy 逻辑，用 `process_madvise` 批量下发 page-in/out hint。

## 关键观察 / 隐含假设

- **观察 1：在真实 trace 上，LRU 与 Belady MIN 之间存在显著且稳定的 memory savings gap。** 在 g-swap promotion rate（refault rate 归一化到 working set）≤1% 或 ≤5% 的约束下，模拟 proactive reclamation 显示 LRU 比 MIN 少 offload 14–37%（1% refault）和 22–38%（5% refault），覆盖 Redis、Memcached、Database A、Twitter/Meta KV 等 trace（Table 2）。
  - **依赖假设**：refault rate 能代表应用性能影响；proactive reclamation（按 interval 定目标 offload 量）与生产 g-swap/TMO 控制环路足够接近。
  - **可能失效场景**：on-demand reclamation（内存压力触发）主导时，ordering 质量与 savings 的关系可能不同；高 refault 容忍 workload 或 latency-insensitive batch job 会改变最优 policy。

- 观察 2：page fault 路径上的微秒级开销会完全吃掉 better policy 的收益。 userfaultfd 额外 4 µs/refault 在 Redis 实验中使应用最多再慢 13.3%；而随机 reclaim 使 refault 升 40% 仅慢 8.1%。这说明 policy 必须留在内核 fault 快路径之外，但不能把 fault 本身搬到用户态。
  - **依赖假设**：swap backend 延迟在 µs 级（zswap ~6 µs，SSD ~50 µs）；应用对 refault 敏感。
  - **可能失效场景**：swap 在远端 RDMA/云存储（ms 级）时，fault 路径固定开销占比下降，userfaultfd 相对劣势可能缩小；但论文未测。

- **观察 3：大多数 reclamation/prefetching 策略可用少量 per-page 状态 + 周期 access bit 表达。** g-swap age、LFU hit count、Hyperbolic hit density 都可映射为 4-byte per-page weight；prefetching 只需 refault 历史与 minor-fault hit 信号。复杂策略（Belady MIN、Leap trend detection）可把重逻辑放用户态，eBPF 只导出摘要。
  - **依赖假设**：32-bit per-page state + 周期性 page-table scan（类似 g-swap kstaled）足以近似策略所需 access history；eBPF verifier 能容纳目标策略的 event handler。
  - **可能失效场景**：需跨页空间相关性、ML 推理（LRB）或大表 lookup 的策略会撞 eBPF 复杂度/状态上限（§4.3 已承认）。

- **假设 1：madvise/`process_madvise` 足以在不新增内核 reclaim 基础设施的情况下执行 policy 决策。**
  - **证据强度**：中。论文量化 batch madvise 比 kreclaimd 慢 14%，且 prefetch 走异步 agent 线程；但未覆盖所有 swap backend、所有 cgroup 配置下的语义边界。

- **假设 2：policy 失败应是 fail-safe 的——应用不应因 policy bug 崩溃，且应能回退到默认内核策略。**
  - **证据强度**：强。设计明确只外置非关键决策；enclave 绑定 cgroup，PageFlex 失败时释放绑定，g-swap 可接管。与 userfaultfd「handler 挂了就 fault 失败」形成对比。

## 核心方法

PageFlex 把 paging 拆成 **内核机制**（page fault、swap I/O、cgroup accounting、access bit 采集）和 **外置策略**（选页顺序、prefetch 预测、控制环路阈值），二者通过 tracepoint + eBPF + 用户态 agent 衔接。

**In-kernel eBPF event handlers**（回应观察 2、3）：在内核 paging 路径上挂 tracepoint，暴露 OnPageAlloc/Free、OnPageFault（含 swapcache hit/miss）、OnPageScanned（周期 access bit）四类事件。policy 订阅子集并提供 eBPF handler，同步执行（~50 ns/调用）。每页在 `struct page` 预留 **4 byte** writable tracepoint 字段，handler 可直接读写，避免用户态 hash lookup 或 eBPF map 查表开销；swap-out 后状态可经 swap cgroup map 持久化。

**简化策略接口**（回应观察 3）：
- Reclamation：`UpdateWeight(state, accessBit)` 在每次 scan 后更新 per-page weight；可选 `OnSwapIn`/`OnSwapOut` 处理 ghost queue 等跨 reclaim 状态。LRU/LFU/Hyperbolic（17 LoC eBPF）、Belady MIN（33 LoC eBPF + 100 LoC 用户态 oracle）均落在此接口。
- Prefetching：`PredictTrend(page, isHit)` 基于 OnPageFault 检测趋势并返回 prefetch 窗口；Linux read-ahead（61 LoC，41 行借自内核）、Leap（187 LoC，160 行借自原实现）走此路径。

**用户态 agent**：加载 eBPF、配置 map、跑 reclamation 控制环路（根据 weight 分布调阈值）、通过 `process_madvise` **批量**（最多 64 页）下发 MADV_PAGEOUT/PREFETCH hint。prefetch/reclaim 均在异步路径，不阻塞应用 fault 快路径。

**Enclave 隔离**（类比 [[GhOSt]] enclave）：每个 enclave 绑定一个 cgroup、运行单一 policy，与默认内核策略共存并共享 swap backend。升级或崩溃时 graceful 解绑，不拖垮其他 workload。

**Region-aware specialization**（§4.2）：授权 agent 经 IPC 把地址区间映射到不同 sub-policy（RegionPolicy 组合现有策略）。案例：KV store 按 key-space 热区设不同 reclaim 阈值（最多 +36% memory savings）；GAPBS PageRank 的 edge array 用 MRU + lookahead prefetch（+6.4% savings，应用仅需 ~10 行 hint 代码）。

实现规模：内核改动 608 LoC（主要是 tracepoint + page struct 字段）；agent 2,900 LoC C++；通用 eBPF 基础设施 700 LoC。深度实现见 [[atc2025-yelam]]。

## 设计取舍

- **只外置策略 vs 完全外置 paging**：保留内核 fault/swap 栈，获得与 g-swap/TMO 兼容和 refault 低延迟；代价是 policy 表达力受 eBPF 4-byte state 和 verifier 限制，复杂 ML policy 需把推理放用户态并承担 export 开销。
- **eBPF 内联执行 vs 用户态处理**：性能关键路径（fault、scan）用 eBPF 消化事件，避免大量 metadata 导出；复杂 trend detection（Leap）放用户态。代价是 eBPF 开发/debug 难度高于普通 C++。
- **madvise 执行 vs 内核 kreclaimd**：无需新内核 reclaim API，fleet rollout 快；代价是 syscall 开销（未 batch 时 offload 一页慢 57%，batch 64 后仍慢 14%）。
- **4-byte per-page state vs 丰富元数据**：固定 0.1% 内存开销（与 g-swap age 相同），lookup 为零；代价是无法在 kernel 侧维护跨页空间模式或大型 per-page 结构。
- **608 LoC 内核修改 vs 零内核改动**：需要 tracepoint 和 writable page field，仍比 upstream 新 policy 轻，但非纯 eBPF CO-RE 方案，需维护 kernel patch。
- **边界条件**：最适于 hyperscaler proactive offloading（zswap/SSD backend、cgroup 隔离、可容忍异步 reclaim/prefetch 延迟）；脆弱于需 in-kernel 同步 reclaim 的场景、硬实时 fault 路径、或 policy 需大量 per-page 用户态状态且 scan 频率很高的 workload。

## 实验与结果

- **功能等价 + 低开销（Redis + zipf(0.5)）**：PageFlex LRU vs g-swap kernel LRU，各 offload target 下应用性能在 baseline 的 99.02% 以内；注入 4 µs userfaultfd 式 fault 延迟则最多再慢 13.3%。
- **LFU vs LRU（synthetic LFU-friendly）**：10% slowdown 时 LFU 达 41% swap usage，LRU 仅 20%（**2× memory savings**）；两版 LRU 表现相近且均劣于 LFU。
- **Read-ahead 等价性**：SSD 仿真 backend 上，kernel read-ahead 比无 prefetch 快 82%，PageFlex 版快 76%；strided 无收益时 PageFlex 仅慢 0.8%。zswap 上 PageFlex 异步 prefetch 甚至略快于内核同步 prefetch。
- **文献策略**：Hyperbolic caching 在 Memcached trace 上同 refault 下最多多 5% offload；Leap 在 strided pattern + SSD 上达 28,710 ops/s，比两版 read-ahead 高 **75.4%**。
- **Region-aware**：KV store specialization +36% memory savings（同性能目标）；GAPBS PageRank ExtMem 式策略 +6.4% savings，性能开销 <2%。
- **基础设施开销**：page-table scan 比 g-swap 慢 17%（0.87s vs 0.72s / 12GB）；batch madvise reclaim 比 kreclaimd 慢 14%（4.9 µs vs 4.3 µs / page）。

## 批判性分析

### 论证链条

主链条较闭合：**测量证明 LRU 有可观改进空间**（Figure 1 trace 模拟）→ **userfaultfd/library 全外置在 refault 路径上代价过高**（Figure 2 + Redis 注入实验）→ **PageFlex 只外置非关键决策 + eBPF 内联轻量逻辑** → **与内核等价 policy 的 application slowdown <1%**（Figure 7）→ **同一框架可承载更优文献策略并量化收益**（LFU 2×、Hyperbolic +5%、Leap +75.4%、region +36%）。

最有力的证据是「equivalence first」：先把 g-swap LRU 和 Linux read-ahead 原样搬到 PageFlex，证明框架不吃掉 policy 收益，再展示更强 policy。这比直接报 Hyperbolic/Leap 数字更能支撑「deployment vehicle」的 claim。

薄弱跳步在于 **production control loop 的外推**：实验多用 static offload target 或 trace replay；真实 fleet 上 PSI/refault-driven 动态阈值、多 tenant 争抢 swap bandwidth、内存 pressure 与 proactive reclaim 交互，论文仅定性类比 g-swap/TMO，未端到端复现完整生产控制面。

### 假设压力测试

**workload assumption**：评估偏重 KV store、DB trace、GAPBS 等 Google/Meta 熟悉 workload；对 GPU memory tiering、file-backed mmap 密集、或 COW-heavy 容器镜像场景覆盖不足。Region specialization 假设应用能提供正确区间 hint（KV 需 key-range heap segregation），否则 agent 无法自动发现语义区域。

**resource bottleneck assumption**：默认瓶颈是 **refault 延迟 × refault rate**；CPU 用于 scan 的开销被视为后台可容忍。全机 scan 所有物理页（当前实现）在 TB 级内存机器上可能限制 scan 频率，间接伤害需要细粒度 access 信息的策略；论文提到未来可改用 cgroup-specific MGLRU scan，但未实现评估。

**hardware/deployment assumption**：双路 Xeon E5-2696、128 GB、Linux 5.10 + PageFlex patch、zswap 或 50 µs SSD ublk 仿真。ARM、不同 swap 设备（远程内存/RDMA）、内核 6.x + 上游 MGLRU 组合未测。608 LoC 内核 patch 的 fleet 维护成本相对「零内核改动的 eBPF-only 工具」仍是一个 deployment 变量，论文通过与月度 kernel rollout 对比论证可接受，但缺少 operator 视角量化。

**scaling assumption**：Trace replay 加速 policy 执行以收集更多数据点，只比较 policy effectiveness（miss/refault rate），不比较 raw latency——合理用于算法对比，但不能直接外推「长周期 production trace 上 agent/eBPF 的 CPU 占比」。

**correctness/SLO assumption**：Policy bug 被假设为 fail-safe，但论文未做 fault injection（agent 崩溃、eBPF verifier 失败、错误 madvise 风暴）下的 tail latency 与 recovery 时间测量；RegionPolicy 非重叠区间约束下错误 hint 的行为未形式化验证。

### 实验可信度

**强项**：baseline 强且公平——g-swap 是 Google 生产路径的直接对标；PageFlex LRU 与 kernel LRU 逐项对比 performance + refault rate；userfaultfd 开销用受控注入近似，规避了 userfaultfd 无法共用 kernel swap backend 的 apples-to-oranges 问题；prefetch 实验同时覆盖 zswap（低延迟）和 SSD 仿真（高延迟）两种 backend。

**弱点**：
- Hyperbolic/Belady MIN 主要在 **trace replay** 上评 refault rate，未与 production Redis/Memcached 在线 QPS 联合评；
- 与 **MGLRU**、TMO PSI 驱动阈值、仅 user-space 控制环路等「非 g-swap」生产配置的对比缺失；
- Region-aware KV 结果依赖 synthetic db_bench 模式复现，与 Figure 10 的 36% 是否稳定于真实 RocksDB 部署未验证；
- 未报告 tail latency（P99 fault latency、agent 积压时延迟），只给 median/p25/p75 分布片段。

### 系统性缺陷

- **可观测性**：论文未讨论 policy 决策、weight 分布、madvise 批量大小的运维可观测接口；大规模 fleet debug 外置 policy 比内核 LRU 更依赖额外 tooling（论文未描述）。
- **资源隔离**：enclave 按 cgroup 隔离 policy，但同一 swap device 上的 I/O 争抢、错误 aggressive prefetch 对邻居的影响未评估。
- **尾延迟**：PageFlex read-ahead 在 zswap 上 miss path 仍比 No-Prefetch 略高；高负载下 agent 线程与 scan 线程的调度延迟论文未讨论。
- **兼容性**：仍需内核 patch（tracepoint + writable page field）；与上游 Linux 6.x MGLRU、userfaultfd 新 access tracking 特性的关系未展开。
- **复杂策略上限**：LRB 等 ML policy 需把特征 export 到用户态，论文承认 CPU/内存成本可能抵消收益，但未给出 break-even 测量。
- **故障恢复**：graceful fallback 到 g-swap 在设计上成立，但论文未给出 failure mode 实验数据。

## 局限与后续工作

- **局限 1**：policy 表达受 eBPF verifier 与 4-byte per-page state 约束；需大状态或跨页上下文的策略实现困难，复杂 policy 需承担用户态 export 成本。
- **局限 2**：page-table scan 当前全机扫描，开销随内存容量线性增长；cgroup-specific scan 仍待集成上游 MGLRU 机制。
- **局限 3**：Region specialization 依赖应用或授权 agent 提供正确语义 hint，无法对黑盒应用自动做语义感知分区。
- **Future work 1**：在 production 规模机器上测量 cgroup-scoped scan + 动态控制环路（PSI/refault feedback）下的 CPU 占比与 savings，验证 scan 频率上限是否成为新瓶颈。
- **Future work 2**：对 agent 崩溃、错误 prefetch/reclaim hint 做 fault injection，量化 tail latency 影响与 fallback 到内核策略的恢复时间——直接检验 fail-safe claim。
- **Future work 3**：与 [[FetchBPF]] 等纯 eBPF prefetch 方案、以及上游 MGLRU + 用户态 weight 导出路线对比，厘清「608 LoC 内核 patch」是否可被更小侵入方案替代。

## 相关

- **相关概念**：[[eBPF]]、[[Memory-Tiering]]、[[LRU]]、[[MGLRU]]、[[Prefetching]]、[[Userfaultfd]]、[[Kernel-Extensions]]
- **同类系统**：[[g-swap]]、[[TMO]]、[[AIFM]]、[[DiLOS]]、[[ExtMem]]、[[FetchBPF]]、[[GhOSt]]
- **同会议**：[[ATC-2025]]
- **对比**：PageFlex 与 userfaultfd/[[AIFM]] 是「保留内核 swap 栈的外置策略」vs「全外置 paging」；与 [[GhOSt]] 是同一「用户态策略 + 内核机制 + enclave」哲学在内存子系统的延伸
