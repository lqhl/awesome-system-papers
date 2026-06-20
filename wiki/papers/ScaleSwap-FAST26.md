---
type: paper
name: ScaleSwap
full_title: "ScaleSwap: A Scalable OS Swap System for All-Flash Swap Arrays"
authors: [Taehwan Ahn, Chanhyeong Yu, Sangjin Lee, Yongseok Son]
venue: FAST
year: 2026
tags: [os-swap, nvme, scalability, linux-kernel, many-core]
source_pdf: "[[fast2026-ahn.pdf]]"
source_md: "[[fast2026-ahn]]"
---

# ScaleSwap: A Scalable OS Swap System for All-Flash Swap Arrays (FAST 2026)

> **一句话总结**：Linux swap 的 all-to-all 共享锁（`lru_lock` 占 53% 执行时间、`si_lock` 全局争用）在 128 核 + 8 块 [[NVMe]] SSD 的 all-flash swap array 上无法 scale；ScaleSwap 用 one(core)-to-one(resource) 的 core-centric 模型 + opportunistic inter-core delegation + 每核 [[LRU]] 列表，把吞吐拉到 Linux swap 的 **3.4×**、平均延迟降到 **1/11.5**、99.9th 尾延迟降到 **1/27.2**。

## 问题与动机

[[Linux]] swap 是防止 OOM、扩展有效内存容量的最后一道防线。随着 ML 训练、图处理、[[Apache-Spark]] 预处理、VM/容器 overcommit 等 TB 级内存负载常态化，DRAM 成本在 hyperscaler TCO 中占比极高（Meta ~37%、Azure ~50%），而 NVMe SSD 单价约为 DRAM 的 **1/26**。多块 SSD 组成的 **all-flash swap array** 因此成为性价比极高的内存扩展层——Google Cloud 单 VM 可提供 3 TB local SSD swap，StorageReview lab 甚至用 921 TB SSD 做 swap 跑科学计算。

但 Linux swap 子系统设计于单盘时代，采用 **all-to-all 模型**：任意核可访问任意 swap space，靠 `si_lock`（swap metadata）和 `lru_lock`（per-node [[LRU]] 列表）全局锁串行化。作者在 128 核 + 8 NVMe SSD 上测得：

- Raw device（FIO）随 SSD 数近线性增长到 **11.2 GB/s**，Linux swap 无论 1 还是 8 块 SSD 吞吐都卡在约 **4 GB/s**；
- 核数超过 32 后 Linux swap 几乎不再提升，128 核时比 raw device 慢 **2.6×**；
- `direct reclaim` 触发时，所有应用线程抢同一把 `lru_lock`，延迟尖峰、吞吐骤降（Figure 4 timeline）。

论文 claim 的缺口不是「要不要 swap」，而是 **swap 机制本身的并发度跟不上现代多核 + 多 SSD 硬件并行度**。这与 [[ZNSwap]]、[[TMO]]、[[ExtMem]] 等工作的关注点不同——后者分别优化 ZNS 接口、offload 策略、用户态内存策略，而 ScaleSwap 聚焦 **OS swap 子系统在高并发下的锁瓶颈**。

## 关键观察 / 隐含假设

- **观察 1：Linux swap 的 SSD 不可扩展性主要来自锁竞争，而非 I/O 栈本身。** Performance breakdown（Table 5）显示 128 核 + 8 SSD + stress 负载下，`lru_lock` 占 Linux swap 总执行时间 **53.27%**，`si_lock` 占 **1.43%**；仅把 LRU 改成 per-core（ScaleSwap-LRU）可把吞吐从 4.34 提到 8.13 GB/s，但瓶颈转移到 `si_lock`（5.03%）；完整 ScaleSwap 消除 `si_lock` 后达 **14.81 GB/s**。
  - **依赖假设**：瓶颈是 metadata/LRU 锁而非 block layer、文件系统（EXT4 swap file）或 SSD 内部通道争用。
  - **可能失效场景**：swap partition 直挂、不同 FS、或 [[CXL]]/远端 swap 设备改变 I/O 延迟占比后，锁不再是主导瓶颈。

- **观察 2：direct reclaim 的高并行性被 per-node LRU 锁抵消。** 内存低于 min watermark 时应用线程直接参与 page reclaim，理论上并行度高；但所有核在 swap out/in 时争用同一 node 的 `lru_lock`，导致 Figure 4 中 latency spike 和吞吐下跌。
  - **依赖假设**：workload 会触发大量 concurrent direct reclaim（内存压力 > 96 GB DRAM 的 stress/Spark 场景）。
  - **可能失效场景**：内存充足、主要靠 `kswapd` 后台异步 swap 的轻度 overcommit，锁竞争可能不那么极端。

- **观察 3：per-core 独占 swap resource 在常见 workload 下 delegation 开销可忽略。** 每核独立 swap file + metadata，跨核访问仅在 swap space 满或共享页/进程迁移时触发；平均 delegation 时间 **29.99 ns**（纯内存操作），即使 96/128 个 swap file 满仍保持峰值吞吐的 **84%**。
  - **依赖假设**：页分配与访问具有 core affinity（线程大多在本核分配并回访本核页）；per-core swap space 容量足够，delegation 为 rare path。
  - **可能失效场景**：频繁进程迁移、大量 shared anonymous pages（fork+COW 密集）、或单核 swap file 过早填满导致 delegation 风暴。

- **假设 1：把 swap entry `type` 字段从 5 bit 扩到 8 bit（最多 247 个 swap file）、offset 缩到 47 bit（仍支持 128 TB/file）是合理 trade-off。**
  - **证据强度**：中。作者论证当前最大 SSD 128 TB、多数 < 15 TB；但未评估与依赖旧 swap entry 布局的 kernel 模块/工具兼容性。

- **假设 2：per-core LRU + page flag 记录核号（7 bit，支持 128 核）不会显著伤害全局内存管理质量。**
  - **证据强度**：中。page fault 减少 9.15%，说明局部性有收益；但论文未测 multi-tenant 混合 workload 下的 reclaim 公平性或 scan resistance。

## 核心方法

ScaleSwap 的核心原则是把 swap 资源与 swap in/out 操作尽可能 **去中心化到 per-core**，只在必要时跨核协作。实现于 Linux **6.6.8**，开源在 syslab-CAU/ScaleSwap。三个策略分别回应上述观察：

**Strategy 1：Core-centric swap resource management**（回应观察 1 的 `si_lock` 瓶颈）

打破 Linux round-robin 全局 swap space 选择与 `si_lock` 保护。每核独占 swap metadata（`swap_info`）、swap cache、swap space（per-core swap file），swap out 时直接访问本核 cluster，无需全局 available swap space list。为支持 > 23 个 swap space（Linux 默认上限），扩展 `swp_entry_t` 的 `type` 字段到 8 bit。深度实现见 [[fast2026-ahn]] Figure 6–7。

**Strategy 2：Opportunistic inter-core swap assistance**（回应观察 3 的跨核 rare path）

当本核 swap space 满（swap-out delegation）或页位于其他核 swap space（swap-in delegation，如共享页），请求方把 96-byte swap task 入目标核 task queue，唤醒 per-core **delegator** 代为更新 swap metadata；I/O 仍由请求线程直接发起（delegation 只做内存操作）。单消费者 FIFO 保序；等待期间 **cooperative swapping**——请求方主动处理自己核 queue 里的任务，避免纯 spin 或 context switch。NUMA-aware：先在同 node round-robin 找空 swap space，再跨 node。

**Strategy 3：Core-affinity page & LRU management**（回应观察 1–2 的 `lru_lock` 瓶颈）

每核独立 LRU list + 独立 spinlock，替代 per-node LRU。页分配时把核号写入 page flag（复用 4 unused bit + 从 node 字段借 3 bit）；swap-in 时按 flag 回插原核 LRU。swap out/in 默认只碰本核 LRU，direct reclaim 时多核不再抢同一把锁。

## 设计取舍

- **独占资源 vs 全局利用率**：per-core swap file 简化了锁路径，但 workload 若核间内存需求不均，某些核 swap space 会先满并触发 delegation，而空闲核的 swap space 闲置；delegation 开销随满 file 数上升（avg 29.99 ns → 81.76 ns）。
- **core affinity vs 全局最优驱逐**：per-core LRU 提升局部性、降 page fault（-9.15%），但可能让冷页在「非分配核」的 LRU 上滞留更久，全局内存效率可能不如 centralized policy——论文未评 reclaim 质量。
- **busy-wait cooperative delegation vs blocking**：平均 30 ns 的 metadata delegation 用 spin + cooperative work 避免 syscall；delegator 睡眠时等待时间会变长，cooperative 缓解但论文未给 tail case 分布。
- **内核侵入 vs 部署**：需修改 swap entry layout、page flag、LRU 结构、delegator 线程；比纯用户态方案（[[ExtMem]]）侵入大，但保留标准 OS swap 语义，应用零修改。
- **边界条件**：最适于 **many-core + multi-SSD + 内存远超 DRAM 的 anonymous page 密集** workload（stress、Spark 预处理、DNA/BFS）；在轻度 swap、file-backed 为主、或 swap 策略层（何时换出）是瓶颈的场景收益有限。

## 实验与结果

**测试床**：128 核双路 AMD EPYC 7713、**96 GB DRAM**、8× FireCuda 530 NVMe（各 2 TB，RAID-0 raw 混合读写 **11.4 GB/s**）、Ubuntu 22.04 + Linux 6.6.8、128 个 EXT4 swap file。

- **Micro-benchmark（stress，128 线程 × 2.25 GB = 288 GB）**：8 SSD 时吞吐 **3.41×** Linux swap（Figure 12a），执行时间缩短 **2.49×**；平均延迟降 **11.5×**，99.9th 尾延迟从 2395 μs 降到 **87.94 μs**（**27.2×**）；核数扩展近线性，Linux 在 >32 核饱和。
- **锁分解（Table 5）**：完整 ScaleSwap **14.81 GB/s** vs Linux **4.34 GB/s**；`lru_lock` 从 53.27% → 0.16%，`si_lock` 从 1.43% → 0%。
- **CPU 利用率（Table 2）**：8 SSD 下 kernel CPU 降约 **25%**，user CPU 略升，idle 升最多 **16%**。
- **内存开销（Table 3）**：每核预分配 1500 个 swap task（~17.57 MB total），峰值用量 6–13.7 MB，总内存与 Linux swap 几乎相同。
- **真实应用（5 个 memory-intensive app，8 SSD）**：BFS **2.4×**、DNA visualization **2.57×**、Python list **1.70×**、gray-scale **1.72×**、flip **1.91×**；micro-benchmark 增益更大因 stress 仅 0.29% user CPU。
- **Apache Spark + Common Crawl**：最大负载（100k records/core）达 **6.3 GB/s**，比 Linux swap **1.75×**；解决 PySpark 预处理阶段 kernel swap 前的 OOM。
- **vs [[TMO]]**：三应用并发 + 不同压缩比，ScaleSwap 优 **64%**（TMO 压缩 CPU 开销 + 压缩满后仍走慢 swap）。
- **vs [[ExtMem]]**（mmapbench）：8 SSD 时 **5.02×** ops/s；ExtMEM 随 SSD 增加几乎不提升，>32 线程饱和。
- **Delegation stress（Table 6）**：96/128 swap file 故意填满，吞吐仍 **84%** 峰值，执行时间 52s → 63s。

## Critical Analysis

### 论证链条

主链条闭合且层层递进：**测量证明 Linux swap 不随 SSD/核数 scale**（Figure 1/3，raw device 线性 vs swap 平坦）→ **定位根因为 `lru_lock` + `si_lock` 全局争用**（Table 5 breakdown + Figure 4 direct reclaim timeline）→ **三策略分别消除两类锁**（per-core LRU 先解决 53% 瓶颈，per-core metadata 消灭 `si_lock`，delegation 处理 rare cross-core）→ **micro + 5 apps + Spark 验证端到端收益**（3.4×/11.5×/1.75×）→ **与 [[TMO]]/[[ExtMem]] 对比界定问题边界**（机制层 vs 策略层/offload 层）。

最强证据是 Table 5 的 **ablation-by-component**：ScaleSwap-LRU 单独即可翻倍吞吐，完整系统再翻倍，直接支撑「锁是主因」而非「SSD 或 FS 不行」的 claim。

薄弱跳步在于 **从 96 GB DRAM 实验台外推到 production fleet**：测试床刻意用极小 DRAM 强迫重度 swap，生产机可能有 512 GB–2 TB DRAM + 适度 swap 作 safety net，此时 direct reclaim 频率和锁竞争强度可能远低于实验，绝对增益会缩小。论文未给出「swap 强度 vs 加速比」的连续曲线。

### 假设压力测试

**workload assumption**：评估偏重 anonymous page 密集、内存远超 DRAM 的场景（stress、Spark 预处理、DNA 640 GB）。对 file-backed mmap 为主、swap 几乎不触发的服务，或 [[TMO]]/zswap 已吸收大部分 cold page 的 proactive offloading 部署，ScaleSwap 的锁优化可能碰不到热路径。Spark 案例有代表性（预处理 OOM），但端到端 pipeline 中 swap 占比随 stage 变化，单一 benchmark 不够。

**resource bottleneck assumption**：默认瓶颈是 **swap metadata/LRU 锁 + direct reclaim 并行度**，而非 swap device 带宽或 [[NUMA]] 远程内存访问。8 SSD RAID-0 经 EXT4 swap file，未测 swap partition、[[XFS]]、或多 tenant 共享 swap array 的 I/O 隔离。delegation 的 NUMA 策略（先 node 内 round-robin）在跨 node 内存分配普遍的 workload 下可能增加远程访问，论文未量化。

**hardware/deployment assumption**：单机 128 核、8 本地 NVMe。云 VM 的 local SSD swap（Google 8×375 GB）核数可能远小于 128，或 swap 在远端存储上，core-centric 模型收益未知。也未测 ARM、不同 kernel 版本（6.6.8 patch 与 upstream 6.7+ MGLRU/新 swap 抽象的兼容性）。

**scaling assumption**：128 核单机结果外推到 **多机 disaggregated memory** 或 tiered memory（[[CXL]]、[[HeMem]]、[[NOMAD]]）时，OS swap 可能只是最后一层兜底；论文在 Related Work 中定性说可叠加，但无组合实验。从 128 核外推到 256+ 核时，7-bit page flag 的核号上限、247 swap file 上限可能成为新边界。

**correctness/SLO assumption**：delegation 的异步 swap-in metadata 更新可能导致短暂「空间不足」误报，但作者论证不会误报「有空间」（与 Linux 行为一致）。论文未做 crash consistency、swap device 故障恢复、或 delegator 线程 hung 时的系统行为测试；对 latency-sensitive 在线服务的 P99/P999 application latency 也未报告（只有 swap op 延迟）。

### 实验可信度

**强项**：baseline 公平——同机同 kernel 版本、同 128 swap file 配置；Table 5 锁时间分解是系统论文少有的直接证据；delegation 极端压力测试（96/128 file 满）支撑 rare path 开销 claim；对比 [[ExtMem]] 用其官方 mmapbench，对比 [[TMO]] 用多应用并发 + 压缩比 sweep。

**弱点**：
- DRAM 仅 **96 GB** 人为放大 swap 强度，缺少「DRAM/swap 比例」敏感性分析；
- 未与 **MGLRU**、memcg async reclaim（Alibaba backend reclaim）、或 Linux 6.7+ swap 重构（LWN 2024 swap abstraction）对比；
- 真实应用 benchmark 来自 prior study [51]（Sabre/OSDI'24 同期工作），非 production trace；
- TMO 对比侧重「压缩 + swap」混合路径，未隔离「同等 swap 量下纯 swap 机制」差异；
- 尾延迟只报 swap op 的 99.9th，未报 application-level tail；多 tenant 噪声、故障注入缺失。

### 系统性缺陷

- **可观测性**：论文未讨论 per-core swap 利用率、delegation 频率、per-core LRU 长度的监控接口；many-core 下 debug swap 停滞比全局 LRU 更难，论文未描述。
- **资源隔离**：per-core swap file 无 cgroup/tenant 级隔离语义；多 VM 或容器共享宿主机 swap array 时，一 tenant 填满若干核 swap space 可能迫使其他 tenant delegation，论文未讨论。
- **尾延迟**：direct reclaim 路径在 delegator 睡眠、task queue 积压时的 tail 行为未测量；cooperative swapping 在 CPU 已饱和时可能加剧争抢，论文未讨论。
- **运维成本**：247 swap file 的创建/扩容/监控、内核 patch 与 upstream 合并成本、swap entry layout 变更对现有工具的影响，论文未量化。
- **策略正交性**：ScaleSwap 优化 swap **机制吞吐**，不解决 **何时 swap**（[[TMO]] PSI、[[PageFlex]] policy 外置等）；二者应正交但论文未展示组合收益。
- **故障恢复**：delegator 崩溃、swap file 损坏、部分 SSD 失效时的降级行为——**论文未讨论**。

## 局限与 Future Work

- **局限 1**：评估集中在单机 128 核 + 8 本地 NVMe + 极小 DRAM，swap 强度高于多数 production 默认配置；绝对加速比能否在「轻度 swap」场景保持未知。
- **局限 2**：per-core swap space + per-core LRU 在进程迁移、共享内存、不均匀核负载下增加 delegation 和局部 LRU 低效风险；论文仅在 stress（每线程读写自己的页）上验证了 delegation 低开销。
- **局限 3**：需要内核多处数据结构修改（swap entry、page flag、LRU、delegator），upstream 路径与长期维护成本未评估；与 Linux 新 swap abstraction layer 的关系未展开。
- **Future work 1**：在 varying DRAM/swap ratio 和 varying swap intensity 下绘制加速比曲线，标定 ScaleSwap 相对 Linux 的 break-even 点——直接检验「锁瓶颈假设」的适用范围。
- **Future work 2**：与 [[TMO]]/[[PageFlex]]/MGLRU 组合：机制层（ScaleSwap）+ 策略层（offload policy）是否相乘，还是在 proactive offloading 减少 swap 流量后收益递减。
- **Future work 3**：在多 tenant VM/container、CXL tiered memory + SSD 最后一层的混合部署中测量 delegation 频率、fairness 和 application tail latency，并补充 delegator 故障与 swap device 失效的恢复语义。

## 相关

- **相关概念**：[[NVMe]]、[[LRU]]、[[Direct-Reclaim]]、[[NUMA]]、[[Swap]]、[[Memory-Tiering]]、[[Page-Cache]]、[[Kernel-Extensions]]
- **同类系统**：[[ZNSwap]]（[[ZNS]] SSD swap 协同）、[[TMO]]（transparent memory offloading）、[[ExtMem]]（用户态内存策略）、[[ScaleCache]]（多 SSD page cache 并发）、[[Infiniswap]]（RDMA remote paging）、[[FlashVM]]
- **同会议**：[[FAST-2026]]
- **对比**：ScaleSwap vs [[TMO]] 是「swap 机制并发」vs「offload 策略 + 压缩」；vs [[ExtMem]] 是「内核透明 swap」vs「应用参与策略」；vs [[ScaleCache]] 是同一锁瓶颈叙事在 swap 子系统 vs page cache 的平行拆解