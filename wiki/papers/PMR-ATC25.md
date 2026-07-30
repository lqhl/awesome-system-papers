---
type: paper
name: PMR
full_title: "PMR: Fast Application Response via Parallel Memory Reclaim on Mobile Devices"
authors: [Wentong Li, Li-Pin Chang, Yu Mao, Liang Shi]
venue: ATC
year: 2025
tags: [mobile, memory-reclaim, android, swap, flash-storage]
source_pdf: "[[atc2025-li-wentong.pdf]]"
source_md: "[[atc2025-li-wentong]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# PMR：通过移动设备上的并行内存回收实现快速应用程序响应（ATC 2025）

> **原题**：PMR: Fast Application Response via Parallel Memory Reclaim on Mobile Devices

> **一句话总结**：关键观察是 Android 内核 [[Memory-Reclaim]] 瓶颈不在 flash 带宽而在串行的 page shrinking / page writeback 路径（shrinking 占 55%、unmap 极不稳定）；PMR 用独立 `kshrinkd` 预产 victim pages（PPS）并按应用批量 unmap + 10 MB bulk write（SPW），在 Pixel 6 Pro 上把应用响应时间降低 43.6%、峰值回收吞吐提升 82.8%、[[LMKD]] 次数减少 82%。

## 问题与动机

现代 Android 应用内存 footprint 动辄数百 MB 到数 GB，而旗舰机 DRAM 增长缓慢（iPhone 16 仍 8 GB、Galaxy S25 Ultra 16 GB）。内存压力管理依赖三层机制：后台 [[kswapd]] 异步 swap、前台分配触发的 [[Direct-Reclaim]]、以及最后的 [[LMKD]] 杀进程。LMKD 能快速释放内存，但冷启动延迟可达 warm switch 的 3.1×，用户上下文全部丢失。

作者 claim 的核心痛点是：**内核级 memory reclaim 太慢，系统被迫频繁走 LMKD**。在 12 GB 的 Pixel 6 Pro 上，36 应用切换 workload 仅 5 分钟就出现 26 次进程被杀；回收吞吐多数时间 < 80 MB/s，峰值也不到 150 MB/s，而应用启动阶段内存增长可达 400 MB–1 GB。更反直觉的是，UFS 3.1 比 UFS 2.1 快得多，但 reclaim 吞吐几乎没跟上——说明瓶颈在系统软件路径，而非硬件。

论文因此聚焦 Linux/Android 内核 reclaim path 本身，而非替换策略或触发时机。这与 Acclaim（foreground-aware victim selection + 动态 kswapd size）和 Fleet（ART GC 与 kernel swap 协同）形成互补：PMR 加速「怎么执行 reclaim」，后两者优化「选谁 reclaim / 何时 reclaim」。

## 关键观察 / 隐含假设

- **观察 1：page shrinking 与 page writeback 串行执行，且 shrinking 占 reclaim 延迟过半。** 用 `ktime` 分解，每轮 reclaim 平均 shrinking 4.48 ms（54.8%）、writeback 3.66 ms（45.2%）；writeback 必须等 shrinking 产出 victim pages 才能开始，无法与 flash 写并行。
  - **依赖假设**：mobile reclaim 仍以 Linux 经典两阶段路径为主（`isolate_lru_pages` → `page_list` → per-page writeback），且 measurement 在 Android 13 / kernel 5.10 上具有代表性。
  - **可能失效场景**：若厂商 heavily fork 了 vmscan 路径、使用 zram-only 无 swap partition、或 reclaim 主要由 compaction 主导，时间分解比例可能不同。

- **观察 2：page shrinking 频繁「期望远大于实际」，导致反复迭代。** `nr_to_reclaim` 在 memory swapping 时可达 ~39,340 pages（~154 MB），但 `nr_reclaimed` 远小于目标——大量页因 recently referenced、locked、或 anon/file scan 不平衡而早退。
  - **依赖假设**：victim 稀缺是 reclaim 慢的主因之一，而非单纯 I/O 带宽不足；提前准备 isolated pages 能直接减少 reclaim 轮次等待。
  - **可能失效场景**：若 workload 全是 hot anonymous pages（游戏、LLM inference），victim list 再满也换不出足够页，PPS 收益会下降。

- **观察 3：flash 带宽充裕，但 page-by-page unmap/write 吃不满存储并行度。** Pixel 5 fio 随机写 378 MB/s、Pixel 6 Pro ~1000 MB/s，而 reclaim 吞吐 < 150 MB/s；I/O conflict 场景（前台切 app）与 memtester 场景峰值吞吐仅差 8.3%。page writeback 内部，unmap 延迟高且极不稳定（reverse mapping 易被中断），写也是 4 KB 粒度。
  - **依赖假设**：mobile 已启用 flash-based swap（2 GB swap partition），且 UFS 内部并行需要较大、较连续的写请求才能释放带宽。
  - **可能失效场景**：eMMC 老设备、swap 在慢分区、或 storage 已接近寿命/热节流时，bulk write 收益可能缩小；重度 read-heavy 前台切换若与 swap write 争用 controller，论文仅测了有限 conflict 场景。

- **假设 1：维持 ~462 MB 的 victim page list（`nr_ideal_victim_page`）在多数应用上净收益为正。**
  - **证据强度：中。** Section 5.5 sensitivity 显示 δ 从 154 MB 增到 462 MB 响应时间下降，再增到 770 MB 反而变差（page thrashing）；但默认值为固定常数，未按 per-app 自适应。

- **假设 2：按应用聚合 unmap + 绑定 big core 能稳定降低 unmap 尾延迟，且不影响前台交互。**
  - **证据强度：中。** SPW 把 unmap 线程提优先级并 affinitize 到 big core，论文报告 CPU 总开销 +5.3%；但未单独给出 foreground jank、ANR 或 big core 被 reclaim 长期占用的 trace。

## 核心方法

PMR 不重写 [[LRU]] victim selection，也不改 reclaim 触发水位或 `nr_to_scan` 全局策略，而是在现有 mm 子系统上插入两条并行化路径：**Proactive Page Shrinking (PPS)** 和 **Storage-friendly Page Writeback (SPW)**。

### PPS：解耦 shrinking 与 writeback

新增内核线程 `kshrinkd`（每 NUMA node 一个，初始化类似 kswapd），专门从四条 LRU list 扫描 eligible pages，用 `PG_ISOLATED` 标记后移入独立的 **victim page list**（新 list type `LRU_VICTIM`）。触发逻辑从「内存水位低」改为「victim list 页数 < `nr_ideal_victim_page`」：

- **系统启动**：`kshrinkd` 持续 shrink 直到 victim list 达到 δ（默认 462 MB ≈ 3× 单次 memory swapping 目标），然后 sleep。
- **reclaim 触发时**：[[kswapd]] / [[Direct-Reclaim]] 直接从 victim list 取页做 writeback，同时 `kshrinkd` 以 `nr_to_reclaim` 为 batch 并行补货；使用 continuous scanning loop，避免原版 shrinking 在 `nr_anon`/`nr_file` 为零时早退。

victim list 与 page writeback 之间用轻量 spinlock 协调，避免 kshrinkd 与 reclaim 线程同时访问冲突。PPS 单独启用时 CPU 开销仅 +2.0%（kswapd 24.31% → 13.94%，kshrinkd 新增 10.97%），说明主要是工作重分配而非无限增线程。

### SPW：应用感知批量 unmap + bulk write

传统 writeback 对每个 victim page 串行执行 check → swap entry 分配 → unmap → `writepage`（4 KB）。SPW 改为：

1. **Application-aware page unmap**：按所属进程聚合 unmap job，增大单次 unmap 粒度，减少 reverse mapping 被其他进程打断的次数；unmap 线程高优先级 + big core 执行。
2. **Batch write I/O**：unmap 完成后按设备最优块大小组 batch 提交 block layer（Pixel 6 Pro 10 MB → 1261 MB/s fio 随机写；Pixel 5 1 MB）。通过 `/proc` 接口 `mem_unmap_unit` 可运行时调参。

SPW 与 block layer I/O plugging 正交——前者在 page reclaim 层准备 batched I/O，后者对 reclaim 不透明。SPW 仍继承原有 page check / lock 语义，改动相对「最小侵入」。

### 正交性与组合

PMR 明确保留：默认 LRU 替换、原有 reclaim 触发条件、原版 `nr_to_reclaim` 规模设置。因此可与 Acclaim、Fleet 叠加——实验显示 PMR+Fleet 相对 OriginalMR 响应时间降 67.4%，相对单 Fleet 再降 38.9%。论文还展望 mobile LLM 等高内存压力场景与 UFS 4.0 更高带宽下的潜力。

实现细节与算法伪代码见 [[atc2025-li-wentong]] / [[atc2025-li-wentong.pdf]]。

## 设计取舍

- **常驻 victim list（~462 MB）vs 内存占用与 page thrashing**：提前 isolate 页消除 reclaim 时 shrinking 等待，但 δ 过大（770 MB）会导致页在 LRU 与 victim list 间反复迁移，增加访问开销；δ 过小则 writeback 仍可能饿死。
- **单 kshrinkd 线程 vs Multiplekswapd 式多线程 reclaim**：避免多 reclaim 线程在 mobile 有限 CPU 上互相争用 LRU lock 和带宽；代价是 shrinking 并行度上限固定为 1，极端内存风暴时可能仍不够。
- **应用级 unmap 聚合 vs 跨应用共享页**：按进程组织 unmap 利于批量和减少锁干扰，但对大量 shared anonymous/file pages（libc、GPU buffer、ashmem）的 unmap 路径可能不如 per-page 灵活；论文未单独量化 shared page 比例对 SPW 的影响。
- **big core 优先执行 unmap vs 前台 CPU 竞争**：提升 unmap 确定性，但 5.3% 额外 CPU 与 big core 占用可能影响 burst 型前台任务；论文未报告 per-core utilization 或 sched latency。
- **更激进 swap-out vs flash 磨损**：PMR 使 reclaim 更有效，30 分钟实验 flash 写入量增加 12.1%；作者认为容量增大后寿命焦虑下降，但未建模长期 daily-active 用户的 TBW 影响。
- **不改 victim selection vs 天花板**：继承 LRU 意味着 page fault rate 与 OriginalMR 相同（论文实测如此）；吞吐提升来自路径效率，而非更少换出错误页。

## 实验与结果

- **平台**：Google Pixel 5（8 GB / UFS 2.1）、Redmi Note 11（6 GB / UFS 2.2）、Google Pixel 6 Pro（12 GB / UFS 3.1）；Android 13，kernel 5.10，2 GB flash swap partition。
- **Workload**：36 应用（10 前台切换 + 26 后台），UI Automator 模拟用户操作，adb 测 launch latency，10 轮随机顺序取平均。
- **应用响应时间（Pixel 6 Pro）**：PMR 相对 OriginalMR 降 **43.6%**；Acclaim 降 32.4%，Fleet 降 35.7%；PMR+Fleet 降 **67.4%**（相对 Fleet 单独再优 38.9%）。
- **回收吞吐峰值**：PMR 相对 OriginalMR **+82.8%**、相对 Acclaim **+75.5%**；PPS 单独在 Pixel 6 Pro 峰值 ~205 MB/s（比 Pixel 5 高 45%），PPS+SPW 在 Pixel 6 Pro 平均吞吐达 Pixel 5 的 65%（更好利用 UFS 3.1）。
- **系统事件**：LMKD 次数相对 OriginalMR **-82%**、相对 Acclaim **-54%**；direct reclaim 相对 Acclaim **-45%**；page fault 与 OriginalMR 持平（符合不改 selection 的设计）。
- **开销**：PMR CPU 总开销 25.61% vs OriginalMR 24.31%（+5.3%）；flash 写入量 +12.1%（30 分钟）。
- **Sensitivity**：δ=462 MB 为响应时间甜点；unmap batch 设备相关（Pixel 5 1 MB，Pixel 6 Pro 10 MB）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| PMR lowers application response time | 43.6% lower vs OriginalMR (§5.2, Fig.11) | Pixel 6 Pro, Android 13/kernel 5.10, 36-app workload, 10 rounds | high |
| PMR+Fleet improves response in same workload | 67.4% lower vs OriginalMR, 38.9% vs Fleet (§5.2, Fig.11) | same device/workload; not general device claim | high |
| Parallel reclaim improves peak throughput | 82.8% vs OriginalMR, 75.5% vs Acclaim (§5.3.1, Fig.12) | peak metric; Fleet excluded from comparison | high |
| PMR reduces pressure events with unchanged selection policy | LMKD −82% vs OriginalMR/−54% vs Acclaim; direct reclaim −45% vs Acclaim (§5.3.2, Fig.13) | page-fault rate same as OriginalMR | high |
| PMR trades CPU/flash write overhead for reclaim gain | CPU 25.61 vs 24.31 (+5.3%); flash writes +12.1% (§5.6, Table 3) | 30-min run, not long-term flash-lifetime evidence | high |

## 批判性分析

### 论证链条

论文的 measurement → design → evaluation 链条整体闭合，且 ablation 有分量：PPS 单独提升吞吐说明「预产 victim pages + 并行 shrinking」有效；叠加 SPW 后进一步吃满 flash，说明 unmap 批量化是第二瓶颈。I/O conflict 对照实验（8.3% 差距）有力支撑「不是 flash 慢，是软件路径慢」这一核心 narrative。

较弱的一环是 **从 reclaim 吞吐 → 用户体验** 的因果：响应时间改善部分来自减少 LMKD（冷启动 → warm switch），部分来自更快 direct reclaim；论文报告了两类指标，但没有把单次 reclaim 延迟分布与 UI jank frame 直接关联。PMR+Fleet 的叠加结果很强，说明路径加速与「换对页 / 少无效 reclaim」确实正交，但也暗示 PMR 单独仍无法消除所有 memory pressure——LMKD 相对 Acclaim 仍减少 54%，而非归零。

### 假设压力测试

**Victim list 常驻 462 MB** 在 6 GB 机上占比 ~7.7%，在内存更紧的设备上可能挤压可用 cache，论文主要在 8–12 GB 机种验证。δ 的「一次 fit all」假设在 LLM on-device、相机 multibuffer 等极端 footprint 应用上可能不够或过多。

**Flash swap 前提**：实验统一启用 2 GB swap；若厂商策略偏向 zram、或用户关闭 memory expansion，SPW 的 bulk write 优化主要针对 swap partition 写路径，对 pure zram compress 路径收益未验证。

**Application-aware unmap** 假设进程边界与 I/O 局部性相关；WebView、多进程 browser、heavy shared memory 应用可能让「按 app 聚合」退化接近 per-page。

**硬件代际外推**：UFS 4.0 带宽更高，论文仅做 fio 趋势推断；若 future reclaim 仍受 CPU/unmap 主导，存储升级边际收益可能再次饱和——这恰是 PMR 自己 measurement 在 Pixel 5 vs 6 Pro 上已显示的现象（存储快 3×，reclaim 仅快 ~10%）。

### 实验可信度

优点：真实手机、真实流行应用、多档位硬件、与 Acclaim / Fleet 等 mobile memory 方向 SOTA 对比；指标覆盖响应时间、吞吐、LMKD、direct reclaim、page fault、CPU、flash wear sensitivity。

不足：

- **Baseline 公平性**：Acclaim 优化 selection 而非路径，对比 PMR 吞吐合理，但 Acclaim 在 LMKD 上仍频繁——部分可能因为 Acclaim 本身不追求吞吐，读者需注意「LMKD -54% vs Acclaim」不等于 Acclaim 无效，而是优化维度不同。
- **Workload 代表性**：36 应用切换偏 multitasking power user；单应用重度（游戏、视频编辑、on-device LLM）场景未作为主表。
- **Tail latency**：报告平均响应时间与峰值吞吐，对 direct reclaim 阻塞分配路径的 p99/p999 延迟分布讨论较少。
- **长期稳定性**：30 分钟 wear 测试很短；victim list 与 `PG_ISOLATED` 长期运行下的 corner case（OOM 压力极高、kshrinkd 与 reclaim 死锁、升级 kernel 兼容性）论文未讨论。

### 系统性缺陷

- **可观测性**：论文未讨论如何通过 ftrace、/proc/vmstat 或 Android meminfo 区分 PPS/SPW 各阶段延迟，生产环境调 δ 和 `mem_unmap_unit` 可能需要厂商级 tooling。
- **故障恢复**：`kshrinkd` 异常、victim list 与 LRU 不一致、或 batch write 部分失败时的恢复语义，论文未覆盖。
- **隔离与公平**：更激进 reclaim 可能优先换出后台 app pages，对多租户 / 分屏 / 画中画场景的 cgroup fairness 未评估。
- **能耗**：额外 background shrinking + big core unmap + 更多 flash 写可能增加功耗；论文未讨论。
- **内核维护成本**：修改 mm/vmscan、新增 list type 和线程，需跟随 Android GKI / 厂商 kernel fork 持续 port；论文强调 minimal invasive，但仍是 deep kernel change。

## 局限与后续工作

- **局限 1**：`nr_ideal_victim_page` 与 unmap batch size 为设备级静态参数，论文承认难以为不同应用类型设不同默认值；δ 过大引发 page thrashing 已在 sensitivity 中展示。
- **局限 2**：继承 LRU 导致 page fault 无法下降，内存压力极高时仍可能触发 LMKD；PMR 是路径加速器，不是 replacement policy 替代品。
- **局限 3**：victim page list 维护的精细策略（动态调整、per-app hint、与 [[LMKD]] 阈值联动）作者明确留给 future work。
- **Future work 1**：在 Android 13+ 真实 trace 上测量 on-device LLM / 大模型推理 workload 的 reclaim latency 与 LMKD 率，验证 PPS 在「几乎无可换 cold pages」时的下限。
- **Future work 2**：将 PMR 与 Acclaim、Fleet、SWAM 等 selection / timing 优化组合，做 factorial ablation，量化「路径 × 策略」各自对 tail latency 的贡献。
- **Future work 3**：针对 UFS 4.0 与不同 swap backend（zram vs flash vs hybrid）做 device-specific `mem_unmap_unit` 自动标定，避免手工 per-device tuning。
- **Future work 4**：长期（日/周级）flash TBW 与热节流下的性能退化测量，验证 12.1% 写入增量在产品寿命模型中是否可接受。

## 相关

- **相关概念**：[[Memory-Reclaim]]、[[Swap]]、[[LMKD]]、[[Direct-Reclaim]]、[[LRU]]、[[Page-Cache]]、[[Flash-Storage]]、[[UFS]]、[[Android]]
- **同类系统**：Acclaim、Fleet、SWAM、SEAL、Multiplekswapd、IOSR
- **同会议**：[[ATC-2025]]
- **对比**：PMR 加速 kernel reclaim 执行路径；Acclaim 优化 foreground-aware victim selection 与 kswapd 规模；Fleet 协调 ART GC 与 kernel swap——三者可正交叠加
