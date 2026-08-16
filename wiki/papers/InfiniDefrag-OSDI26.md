---
type: paper
name: InfiniDefrag
full_title: "Compaction-Free Memory Defragmentation for Virtualization via Infinite Guest Physical Address Space"
authors: [Peixin Zeng, Hao Huang, Yanqi Pan, Wen Xia, Darong Yang, Jiahao Chen, Nan Zhang]
venue: OSDI
year: 2026
tags: [virtualization, memory-fragmentation, huge-pages, memory-compaction, linux]
source_pdf: "[[osdi26-zeng.pdf]]"
source_md: "[[osdi26-zeng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# InfiniDefrag：用近乎无限的 GPA 做免压缩内存去碎片（OSDI 2026）

> **原题**：Compaction-Free Memory Defragmentation for Virtualization via Infinite Guest Physical Address Space

> **一句话总结**：InfiniDefrag 发现 VM 中的 guest physical address（GPA）其实还会经 EPT 映射到 host physical address（HPA），所以 guest 不必在原来的有限 GPA 区间里搬页来凑 2 MB 连续空间。它回收散落的空闲 GPA，把同等容量换到地址空间末端，再更新 GPA–HPA 映射；在论文构造的严重碎片环境中，生成连续内存的速度从 Linux compaction 的 0.91 GB/s 提高到接近 20 GB/s；host 使用 huge page 时，多数 workload 的端到端性能接近无碎片上界。不过“免压缩”只严格指 guest 关键路径：host 使用 huge page 时仍可能在后台 compaction。

## 问题与动机

虚拟机的一次内存访问先做 GVA→GPA，再做 GPA→HPA。2 MB huge page 能减少 TLB miss 和两级 page-table walk（PTW），因此 guest 和 host 都使用 huge page 时通常最快。但 huge page 需要连续物理地址；长期分配与释放会把空闲页打散，即使空闲总量足够，buddy allocator 也可能找不到连续 2 MB（§2、图 1）。

已有方法有两条路。Anti-fragmentation 用放置策略尽量把相似寿命的页放在一起，但依赖 workload 规律，而且碎片一旦形成就不能主动制造连续空间；defragmentation 则复制、迁移页面并更新页表，能恢复 huge page，却占用 CPU、带宽并触发 TLB shootdown。论文的 YCSB–Redis 预实验中，LLFREE 和 Linux THP 在严重碎片下只有无碎片配置 49%–72% 的 throughput，latency 高 30%–102%，部分配置甚至不如只用 4 KB 页（§3.1、图 3–5）。

论文指出，host 物理地址确实有限，但 GPA 是 VM 看到的“虚拟物理地址”。只要 host 维护新的 GPA–HPA 映射，guest 可以放弃旧的空洞地址，在更高 GPA 处得到一块新的连续区间，而不用搬动仍在使用的数据页。真正困难变成：怎样快速找出可交换的空闲 GPA、怎样不让 HPA 用量超过 VM quota，以及怎样在多线程、多 VM 下避免新的锁和 host 碎片（§3.3–§4.1）。

## 关键观察 / 隐含假设

- **观察 1：guest 连续与 host 连续是两个不同条件。** Guest huge page 只要求 GVA→GPA 的 2 MB 区间连续；host 用 4 KB 页承载时，同一 guest huge page 最多仍会对应 512 个 EPT entries。扩展 GPA 因而可以消除 guest compaction，即使底层 HPA 并不连续（§2.1、§3.3、§6.2）。
  - **代价**：host-base 配置仍有较长 nested PTW，端到端性能和 host-huge 的无碎片上界之间保留明显差距。
- **观察 2：57-bit address space 在常见 churn 速度下很难耗尽。** 论文用 cloud live migration 的 32 MB/s dirty-page rate 估算，每天约写 2.76 TB；57-bit 空间可维持约 4.7 万天，即超过一世纪（§3.3）。
  - **依赖假设**：处理器、KVM 和 guest 都能使用足够宽的物理地址；更重要的是，dirty rate 只是 GPA 扩展速度的代理，实际扩展由碎片和 huge-page 请求触发，二者未必相等。
- **观察 3：空闲碎片可以与新区间等量交换。** Guest 先保留散落的 free base pages，再把等容量 GPA 加到地址空间末端；HPA 被解除旧映射并用于新 GPA，所以地址范围增长，但 VM 实际使用的 host 内存不增长（§4.2–§4.3）。
  - **依赖假设**：当 huge-page allocation 失败时，仍有足够多可回收 free fragments。内存几乎占满、free pages 不足时，这个交换也无法凭空创造容量。
- **观察 4：host-base 与 host-huge 需要不同数据路径。** Base-page 模式可把 4 KB HPA 直接 self-hosted remap 到新 GPA；host-huge 模式若逐个 remap 会产生大量 syscall，因此改用 batch unmapping 和 hybrid paging（§4.3–§4.4）。
  - **重要边界**：hybrid paging 会让 host 对旧碎片页做后台 compaction，故系统不是“整个虚拟化栈完全无 compaction”。
- **观察 5：同步 TLB flush 在特定状态下可以推迟。** Guest 已把被回收 GPA 标为不可访问，host remap 时不必让每个线程同步 shootdown；异步 flush 可减少 KVM MMU lock 和 page-table lock 争用（§4.4、图 10）。
  - **依赖假设**：回收标记、映射更新和所有可能访问之间的 happens-before 关系始终成立。论文以实现和性能实验支持该设计，没有给出形式化一致性证明或 crash-path 分析。
- **假设 1：旧碎片大多不在性能关键路径。** Hybrid paging 用 4 KB HPA 保留不能回收的旧页，把新 workload working set 放到 host huge pages；作者认为旧页多是 kernel objects、page cache 等 cold memory（§4.4）。若热数据长期留在旧区，PTW 与 host compaction 开销会更大。

## 核心方法

### Memory trade 与 Infinite Address Manager

当普通 high-order allocation 找不到连续 GPA 时，guest 通过 VirtIO 发起 memory trade。Guest Reclaimer 从 buddy allocator 的 free lists 中找散落的 4 KB 页并逻辑保留，Guest Extender 则增加同等容量的新 GPA；两边满足“回收 base-page 总字节数 = 新增 block 总字节数”。新连续 region 的基本 block 是 1 GB（§4.2）。

直接逐页调用 buddy allocator 会争用 zone lock。Fast Reclaim 因此用 bitmap 表示页状态并一次扫描：普通 order 不大于 6 的 allocation 用 `atomic64_try_cmpxchg` 原子检查和更新最多 64 个 base pages；更大的 allocation 分成 order-6 transaction，任一部分失败就 rollback。正常 allocate/free 仍走原 buddy allocator，只多做 bitmap 一致性检查（§4.2、§4.4）。

Memory trade 异步执行，期间的新请求先回退到 base page，避免阻塞 foreground allocation。为降低 memory hotplug 和 QEMU backend 建立成本，系统每次扩 4 GB，并在启动时预先初始化 96 GB offline reserved region；论文称准备时间少于 1 秒，通常可支撑小时级运行后才再次 hotplug（§4.2）。

### Host Memory Guard 与 quota

Host Memory Guard 把旧 GPA 对应的 HPA 解除映射，并为新 GPA 建立映射；交换前后 HPA 总量不超过 VM quota（§4.3、图 9）。

host 使用 base pages 时，self-hosted remap 不先把 HPA 还给 host buddy allocator。VM-exit handler 只把回收的 page frame 记入 Page Dispatcher；新 GPA 第一次触发 EPT violation 时，dispatcher 直接取一个旧 frame 建新映射。实现从扩展性较差的 `mremap`、`userfaultfd` 进一步下沉到 in-kernel remap，并把 TLB flush 延后（§4.3、§4.4、图 10）。

host 使用 huge pages 时，4 KB 直接 remap 会拆成大量操作。Batch unmapping 先用 bitmap 合并相邻的 unmap range，减少 syscall、address-space lock、page-table walk 和 TLB shootdown。Hybrid paging 则让新扩展 GPA 尽量由 2 MB HPA 支撑，旧区中仍有效的散页改用 4 KB HPA，并由 host 后台恢复 huge pages（§4.3–§4.4、图 11）。

### 多线程与多 VM 扩展

Fast Reclaim 的 atomic bitmap 避开全局 bitmap lock；优化后的 in-kernel remap 避免每页同步 shootdown；hybrid paging 减少多 VM 相互制造 host-side huge-page fragmentation。查询和 fault path 因而能随线程数扩展，而 multi-VM 时每台 VM 仍通过等量回收和重映射维持自己的 HPA quota（§4.4）。

### 跨三层实现

原型约修改 7K LoC，跨 guest Linux、host Linux 和 QEMU/KVM。Guest kernel 接入 high-order allocation、Fast Reclaim 与 memory hotplug；host kernel 实现 HPA 回收、quota、remap、batch unmap 和 hybrid paging；QEMU 提供 reserved memory backend，KVM 处理 EPT fault 和二级映射。应用无需改动，但部署不是 stock VM，guest、host 与 VMM 必须配套修改（§5）。

## 设计取舍

- **扩大地址范围换取消 guest page migration**：数据页不搬，allocation critical path 更短；GPA、per-page metadata 和相关 page-table state 会随扩展增长。
- **异步 memory trade 换短暂停顿**：foreground 不等交易完成；交易期间回退到 4 KB 页，huge-page 覆盖不会瞬间达到 working-set 上界。
- **4 GB chunk 与 96 GB reserve 换 hotplug 次数**：扩展不频繁；启动时要预备更大地址区和 metadata，小 VM 或受限 VMM 未必愿意承担。
- **host-base 的灵活性换 EPT 效率**：4 KB HPA 容易回收和 remap；2 MB guest region 仍可能需要 512 个 EPT entries。
- **host-huge 的性能换后台整理**：新 working set 获得 2 MB–2 MB mapping；旧散页可能拆 huge page，host 仍要异步 compaction。
- **延迟 TLB flush 换更复杂的一致性条件**：减少 shootdown 和锁争用；实现必须保证旧 GPA 已不可达，且异常、取消和并发 fault 不会重新访问旧 translation。

## 实验与结果

- **平台、workload 与 baseline**：双路 Intel Xeon Gold 6330，每路 28 cores、128 GB DRAM；host 为 Ubuntu 22.04、Linux 6.10，QEMU 8.2.94/KVM；guest 为 Ubuntu 20.04、16 vCPUs、64 GB。十个 workload 包括 Gups、Specjbb、Redis、Graph500、GAPBS PR/BC、XSBench、Liblinear、CG.d 和 Random，working set 为 4.5–20 GB。基线是 CBMM、LLFREE、Linux THP default/aggressive/synchronous、Linux 4 KB 和无碎片 NoFrag（§6.1、表 1）。
- **碎片方法与端到端 throughput**：Extreme 设置先让超出 VM 容量的 file page cache 打乱 LRU，再在每个 2 MB region 随机访问 256 个 4 KB pages，使回收后主要只剩 4–8 KB extents；Moderate 设置每区留下 1–2 个 pinned pages，最多可合并到 512 KB 或 1 MB；另有 freshly initialized 的 light/no-fragment case。图 12–13 全部统一归一化到 host-huge NoFrag。Extreme 下 InfiniDefrag 在十个 workload、host-base/host-huge 两种配置中均最高；host-huge 多数接近 NoFrag，host-base 因 EPT 被打碎仍有差距。论文摘要给出的 YCSB–Redis 相对 LLFREE、Linux THP 和 Linux 4 KB 提升范围为 21%–105%。Moderate 时仍领先，但差距缩小；light/no-fragment 下各系统相近，作者未画出结果（§6.1–§6.2、图 12–14）。
- **latency 与去碎片带宽**：YCSB–Redis 的 host-base extreme 实验中，THP Sync 在 load phase 因同步 compaction 抬高 latency，THP Aggr 在 run phase 因后台扫描和迁移产生 spike；InfiniDefrag 在所画配置中最低。没有 foreground workload 时，Linux compaction 生成连续内存的速度为 0.91 GB/s，Fast Reclaim + Self-hosted Remap 接近 20 GB/s，论文报告约 19 倍提升（§6.3–§6.4、图 15–16）。
- **huge page、线程与多 VM**：Extreme host-base 下，CBMM/LLFREE 在多个 workload 中分不到任何 huge page，InfiniDefrag 的 guest huge pages 接近 working-set 上界；其 PTW cycles 与 throughput 也相应下降。线程数增加时，优化后的 Fast Reclaim/Remap 在所测六个 workload 中保持领先；三个 VM、host-huge 实验中，大多数 workload 也优于 baseline，作者观察不到明显 VM 间干扰。Hybrid paging 实验里每台 VM 只需约 30–40 GB host huge pages，主要覆盖扩展区的 working set（§6.5–§6.7、图 17–23）。
- **组件开销与资源**：`mremap` 的单页 remap 在 16 threads 约 270 µs，`userfaultfd` 约 63 µs；优化后的 kernel remap 接近普通 anonymous fault，并消除了大部分 lock/TLB-flush 时间。实时 CPU 图中 InfiniDefrag 使用 cores 更少、波动更小。Fast Reclaim bitmap 每页 2 bits；GPA 每增加一个 4 KB page，还需 64 bytes per-page metadata，即约 1.6% 容量，其他 kernel structures 被作者称为可忽略（§4.4、§6.7–§6.8、图 10、22、24）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 扩展 GPA 可绕开 guest compaction 并快速形成连续区 | 连续内存生成速度接近 20 GB/s，对 Linux compaction 的 0.91 GB/s，约 19 倍（图 16） | 无 foreground、host-base、人工 extreme fragmentation | 强（机制速度） |
| 机制能把更多 guest memory 放进 huge pages | Extreme 下总 huge pages 接近 workload working set，多个 baseline 在多项 workload 为零（图 18–19） | 仍可能因异步 trade 暂时回退 base pages；host 连续性另算 | 强（所测配置） |
| 去掉 guest compaction 能改善应用性能 | 十个 workload 中均最高；YCSB–Redis 相对所列 baseline 提升 21%–105%（图 12–15） | 单一 Intel/QEMU 平台；碎片主要由实验注入 | 强（覆盖配置内） |
| 设计可扩到并发和多个 VM | 多线程保持领先，三个 VM 的平均 throughput 多数领先且结束时间相近（图 20–23） | 仅三个 64 GB VM；未测超配、[[NUMA\|NUMA]] 分区或长期 churn | 中到强 |
| 扩大 GPA 不增加 VM 的实际 HPA quota | Memory trade 等量回收和重映射，Host Memory Guard 控制 mapping（§4.2–§4.3） | 论文主要给设计与资源量结果，没有恶意/故障下 quota stress test | 中 |

## 批判性分析

### 论证链条

论文抓住了虚拟化特有的一层间接映射：guest 需要的是连续 GPA，不必让原 GPA 像真实机器 HPA 一样固定。Memory trade 直接把“搬仍在用的数据”改成“移动空闲地址的映射”，Fast Reclaim 和 remap 又分别消掉 guest allocator lock 与 host buddy round trip。端到端结果、连续内存带宽、PTW、huge-page 数量和 remap breakdown 能互相对应，论证链较完整。

需要收紧的是“compaction-free”的范围。host-base 模式确实不靠 host huge page；host-huge 模式的 hybrid paging 明确让 host 对旧 4 KB 页做后台 compaction。贡献应表述为“guest huge-page allocation 不把 compaction 放在 critical path”，而不是整个系统完全不整理内存。

### 假设压力测试

“57-bit 足够一世纪”的估算把 32 MB/s dirty-page rate 当作 GPA consumption rate，但 dirty data 与产生无法复用的 GPA 地址并不是同一事件。反复 allocate/free、短生命周期 VM、不同 huge-page 请求粒度可能更快或更慢地扩地址。实际硬件暴露的 GPA width、guest memory hotplug 上限、QEMU memory backend 数量和云平台策略也会先于理论 57-bit 极限成为约束。

Memory trade 还要求能找到等量 free fragments。高 utilization 下若 free pages 不足，系统不能只靠地址空间制造实际容量。Host-huge 模式假设旧散页较冷；若数据库热集跨新旧区，拆分 EPT 和后台 compaction 可能直接干扰 foreground。NUMA-aware trade 只在讨论中说可按 node 实现，没有实测 remote memory、跨 socket fault 或多个 VM 争同一 huge-page pool。

### 实验可信度

优点是同时测 host 4 KB/2 MB、十个 memory-intensive workload、三档碎片、线程与三 VM，也把 THP default/aggressive/synchronous 分开，避免只挑一个较弱配置。图 16、17、18 和 22 把 throughput 收益追到生成带宽、PTW、huge pages 与锁/TLB 成本，机制证据较扎实。

局限是主结果来自单台双路 Intel 服务器，Extreme/Moderate 都是 page-cache 驱动的人工构造；没有 production fragmentation trace、数天或数周运行，也没有 confidence interval。Light/no-fragment 因结果“相近”而没有图；部分 host-huge 详细结果因篇幅省略，只称趋势相似。三 VM 不足以代表 cloud overcommit，且没有测试 live migration、snapshot、VM resize、passthrough/DMA、memory failure 或 host crash 后的 mapping 恢复。

### 系统性缺陷

InfiniDefrag 约 7K LoC 跨 guest kernel、host kernel 和 QEMU/KVM，升级与部署必须三层同步，不是一个可独立加载的 guest policy。延迟 TLB flush、异步 memory trade、EPT fault remap 和 memory hotplug 形成新的并发状态机；论文主要验证性能，没有用 model checking 或 fault injection 验证 mapping 永不重复、丢失或越 quota。

地址不耗物理容量，但 metadata 会增长。论文给出每 4 KB GPA 需 64 bytes，即 1.6%；96 GB reserved region 也需提前准备相应 metadata。无限扩展最终仍要回收旧地址或 fallback 到 Linux THP，作者把 address recycling 留给 future work。系统因此把“立即搬页成本”换成“长期地址与元数据管理”，这个长期账在当前实验中没有结清。

## 局限与后续工作

- 用 production VM 的长期 allocation/free trace 回放 GPA consumption，而不是以 dirty rate 间接估计；报告数天运行后的地址、metadata、page table 和 TLB footprint。
- 实现旧 GPA 回收与安全复用，验证 wraparound、hot-unplug、VM resize、snapshot 和 live migration 时的映射一致性。
- 在 NUMA、多 socket remote memory、更多 VM 和 memory overcommit 下评估 per-node trade、quota 与 host huge-page fairness。
- 覆盖 VFIO/passthrough、DMA、pinned/shared pages 等依赖物理映射稳定性的路径，明确哪些页不可交换以及如何回退。
- 对 delayed TLB flush、concurrent EPT fault、取消中的 memory trade 和 host crash 做形式化检查或 fault injection。
- 报告 light/no-fragment 原始数据、run variance、p95/p99 allocation latency、energy 和后台 host compaction 带宽，而不只给归一化 throughput。

## 相关

- **概念**：GPA–HPA 二级映射、huge page、memory compaction、memory hotplug、TLB shootdown
- **同会议**：[[OSDI-2026]]
