---
type: paper
name: DSA-2LM
full_title: "DSA-2LM: A CPU-Free Tiered Memory Architecture with Intel DSA"
authors: [Ruili Liu, Teng Ma, Mingxing Zhang, Jialiang Huang, Yingdi Shan, et al.]
venue: ATC
year: 2025
tags: [tiered-memory, cxl, intel-dsa, page-migration, linux-kernel]
source_pdf: "[[atc2025-liu-ruili.pdf]]"
source_md: "[[atc2025-liu-ruili]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# DSA-2LM：采用 Intel DSA 的无 CPU 分层内存架构（ATC 2025）

> **原题**：DSA-2LM: A CPU-Free Tiered Memory Architecture with Intel DSA

> **一句话总结**：观察到 [[tiered memory]] 页迁移中 CPU `copy` 占 ~73% 周期且 [[Intel DSA]] 在 >32 KB 传输下可达 ~32 GB/s，DSA-2LM 在内核绕过 [[DMA]] 接口、用混合 4 KB/2 MB 页自适应 batch + 多 WQ 并发卸载迁移，在真 CXL 平台上比 [[MEMTIS]]/[[TPP]]/[[NOMAD]] 平均快 20%/30%/16%，1:16 fast/slow 比下最高 1.8×。

## 问题与动机

[[CXL]]、NVM 等慢速大容量内存让 **two-level tiered memory** 成为控制 DRAM 成本的可行路径，但系统要在三类开销间取舍：hotness 检测精度、迁移频率、页拷贝本身。作者引用 [[NOMAD]] 与自测：即便 [[MEMTIS]] 用直方图减轻拷贝，迁移时间仍有约 49% 花在 copy；在 Graph500 上迁移相关 CPU 开销可达 11%。更激进的检测（更短采样间隔、更多 counter、甚至 [[PEBS]]）会进一步吃掉应用 CPU 与带宽，反而拖慢端到端性能。

Intel 4/5 代 Xeon 标配的 **Data Streaming Accelerator (DSA)** 提供每设备约 32 GB/s、单 socket 四设备合计约 110 GB/s 的 memory copy 带宽，且提交 64 B descriptor 只需极少 CPU 周期。论文 claim：若能把 Linux 内核页迁移的 **critical copy path** 从 CPU 挪到 DSA，就能在不增加 CPU footprint 的前提下更频繁迁移，更快响应访问模式变化。难点在于：内核现有 DSA 走通用 [[DMA]] 接口，细粒度页迁移的 buffer pin/unmap 开销（单 4 KB 页多 88 ns）抵消硬件收益；DSA 又在 <32 KB 传输时不如 CPU；而启用 [[THP]] 的 tiered memory workload 中 2 MB Huge Page 可占 ~78% 页数，迁移列表是 4 KB 与 2 MB 混合。

## 关键观察 / 隐含假设

- **观察 1**：在 [[MEMTIS]] 的 `kmigrated` 路径上，perf 显示迁移相关周期中 **page copy (`migrate_page_list`) 占 ~34%，整体 migrating pages 占 ~73%**；copy 是 tiered memory 在混合 workload、hot start（serverless）等场景下的主导 CPU 瓶颈。
  - **依赖假设**：瓶颈主要在 **拷贝执行** 而非 hotness 元数据维护；把 copy 卸载后，更短迁移周期不会把系统推回「检测/调度」主导。
  - **可能失效场景**：若 placement 本身错误（hot 页长期留在 slow tier），仅加速 copy 无法挽回；[[SoarAlto-OSDI25]] 已表明 hotness ≠ performance-critical。

- **观察 2**：DSA 相对 CPU memcpy 的优势在传输 ≥32 KB 后才稳定出现；单 descriptor 同步提交时小页更慢，但 **pipeline + batching + 多 WQ** 可把吞吐推到平台峰值附近（workload B 达 106.3 GB/s，峰值 ~110 GB/s）。
  - **依赖假设**：迁移批次足够大、且 WQ/PE 资源可独占；默认 `limit_chans=8`、batch size 随 4 KB 页数自适应，Huge Page 切成 `2MB/limit_chans` 并行。
  - **可能失效场景**：极低迁移量、频繁小批次 promote/demote 时，descriptor 提交与等待 completion 的固定成本可能重新主导；多租户共享 DSA WQ 时论文未评测。

- **观察 3**：绕过 DMA、在内核直接用 **物理地址** 提交 DSA descriptor，单页提交约 6 ns，而 DMA 路径多 ~88 ns 的 map/unmap；且 DSA 支持 shared virtual memory，避免 tiered memory 场景下 VM 多租户的 memory pinning 困境。
  - **依赖假设**：内核迁移时使用已解析的物理页地址不会触发 fault；per-cpu 预分配 descriptor/completion 结构可消除动态分配开销。
  - **可能失效场景**：需要频繁 remap、COW、或迁移中与应用写并发（[[NOMAD]] 的 transactional migration）时的正确性边界；论文主要论证 copy 加速，对 TPM 失败率只做了间接讨论。

- **假设 1**：继承 [[MEMTIS]] 的 PEBS 采样 + 直方图 hotness 与页放置策略「足够好」，性能增益主要来自 **更快 copy** 而非更准 placement。
  - **证据强度**：**中**——端到端实验在多种 benchmark 上一致优于 MEMTIS/TPP/NOMAD，但未 ablate「仅换 copy 引擎 vs 同时缩短 kmigrated 唤醒间隔」的独立贡献。

## 核心方法

DSA-2LM 是 Linux 5.13/5.15 上的 **DSA-based two-level memory** 内核模块（~2K LoC mm 修改 + ~8K LoC 自 6.4 后移的 IDXD/IOMMU 驱动），整体沿用 MEMTIS 三阶段：**track → select → migrate**，但重写 migrate 的 copy 引擎。

**Hotness 与页选择**：继续用 MEMTIS 页直方图 + PEBS 粒度采样，阈值 \(T_{hot}/T_{cold}\) 动态调节以让 hot set 贴近 fast tier 容量；改进采样算法始终使用最近样本。因 copy 不再占 CPU，**缩短 `kmigrated` 周期唤醒**（如 200 ms 量级），采用更激进迁移。fast tier 空闲低于 3% 时触发 demotion，优先踢 cold 页。

**Kernel-direct DSA workflow**：暴露 `dsa_multi_copy_pages` / `dsa_copy_page_lists`；descriptor、`idxd_desc`、`dsa_completion_record` 均为 **per-cpu 全局变量**。提交后用内核 completion + MSI-X 中断唤醒 `idxd_wq_thread` 做真异步等待，避免用户态 UMONITOR/UMWAIT 或 `sched_yield` 模型。

**Adaptable concurrent migration（Algorithm 1）**：对混合 page list 两遍扫描——(1) 每个 2 MB Huge Page 切成 `limit_chans` 份（默认 256 KB）round-robin 到各 WQ；(2) 剩余 4 KB 页按 `nr_base_pages/limit_chans` 组 batch descriptor，按「短板效应」平衡各 WQ 总传输量（差异不超过 1 个 4 KB 页）。corner case 下 `batch_size < 2` 时直接逐页提交。

论文还将类似思路移植到 TPP/NOMAD/AutoNUMA（TPP+/NOMAD+/AutoNUMA+），说明 copy 引擎与具体 placement 策略可正交组合。实现与 sysfs/procfs 监控见 [[atc2025-liu-ruili]] 与 https://github.com/madsys-dev/DSA-2LM。

## 设计取舍

- **取舍 1**：**性能换通用性与可移植性**——绕过 DMA、绑死 IDXD 物理地址路径与 Xeon DSA 拓扑（每设备 4 PE + 1 WQ），换取 2.1×（均值）至 8×（峰值）于上一代 CBDMA 的吞吐；需大规模 backport 驱动而非只用主线内核 API。
- **取舍 2**：**更激进迁移换潜在带宽争用**——CPU-free copy 使缩短迁移周期「几乎免费」，在 fast/slow 比 1:16、hot set 剧烈变化时收益最大（平均 +28%，最高 1.8×），但也可能增加 slow tier 访问与 CXL 带宽占用；论文未量化对 co-located workload 的干扰。
- **取舍 3**：**继承 MEMTIS 检测栈换实现简洁**——不解决 PEBS/采样本身的 ~20% 开销问题，也不讨论 placement 质量；与 [[NeoMem]]（硬件 offload placement）正交，作者暗示可组合成 fully CPU-free 方案。
- **边界条件**：在 **DRAM+CXL 双 socket、THP 开启、DSA 硬件可得** 的数据密集型 batch 应用上最优雅；对 RSS 小于 fast tier（如 PageRank vs 16 GB 配置）或 AutoNUMA 保守策略场景，增益可能只有几个百分点。

## 实验与结果

- **平台**：双路 4th Gen Xeon Platinum（每 socket 1 TB DDR5 + 64 GB Montage CXL，load/store ~112 ns vs ~300 ns），32 核单 socket 绑核，THP 开启；fast tier 16/32 GB 或 cgroup 控制比例 1:2–1:16。
- **Copy microbench**：workload B（1000×4 KB + 24×2 MB）带宽 106.3 GB/s，为 CPU / DSA-raw（4 KB 用 CPU、2 MB 用 DSA）的 **14.38× / 2.19×**。
- **Profiling**：`migrate` 在 perf 中占比从 39.0% 降至 4.24%（约为原先的 2.51%）；Graph500 总 copy 时间 14.9 s → 1.39 s（9.3%），占执行时间 10.5% → 0.97%。
- **端到端**：Graph500 / XSBench / BTree / Pandas 等上，相对 MEMTIS、TPP、NOMAD **平均约 +20%、+30%、+16%**；最佳 case **+81.7%、+52.9%、+15.6%**。NOMAD+ 约 2/3 case 有 4%–16% 提升（迁移窗口缩短降低 TPM 失败）。
- **比例敏感性**：fast/slow 1:1 时提升不明显；1:8 时 Graph500 完成时间 −20.68%；比例越大 DSA 优势越明显。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Adaptive aggregate migration approaches platform bandwidth | workload B: 106.3 GB/s，CPU 14.38×、DSA-raw 2.19×（§4.2，Fig. 10） | continuous microbenchmark、CXL platform、约 110 GB/s peak | high |
| DSA reduces Graph500 copy-path time | total copy 14.9 s→1.39 s，share 10.5%→0.97%（§4.3，Fig. 12） | one Graph500 run on dual-socket CXL/THP configuration | high |
| DSA reduces sampled migration CPU share | perf migrating-pages 39.0%→4.24%（§4.3，Fig. 11） | kernel-function sampling，不是 total CPU utilization | high |
| DSA-2LM improves tiering at constrained fast tier | 1:16 对 MEMTIS average 28%、best 1.8×；1:2 all app 2.5–12%（§4.4，Fig. 13–14） | five workload、cgroup/memmap config、1:1 gain insignificant | high |
| Other placement integration is mixed | TPP Graph500 14.5/11.5%，XSBench 29.8/53.9%；NOMAD+ 4–16%（§4.4，Fig. 13） | 16/32 GB；PageRank 未纳入 | medium |

## 批判性分析

### 论证链条

观察（copy 占迁移 CPU 大头）→ 设计（DSA 卸载 + 混合页并发路径）→ 结果（microbench 饱和带宽、perf 中 migrate 占比骤降、端到端优于三类 SOTA）链条在 **「迁移频繁且 copy 是瓶颈」** 的前提下闭合。薄弱环节在于：(1) 同时改了 **copy 引擎 + 迁移频率**，未严格分离二者贡献；(2) 摘要「20/30/16%」与正文「up to 81.7/52.9/15.6%」混用，读者需区分平均与峰值；(3) 外推「production trace / 云混部」主要依赖 benchmark + 行业 workload 叙述，缺少真实多租户 trace。

### 假设压力测试

- **已证明**：在评测 CXL 机器、THP on、MEMTIS 类 hotness 下，DSA 加速 copy 能带来可观端到端收益；DSA 集成到 NOMAD 可减少 transactional migration 失败窗口（间接证据）。
- **可能失效**：访问模式极稳定、fast tier 足够大（1:1）时收益趋零；若瓶颈是 **错误 tier 上的慢速 load** 而非迁移 copy（参见 AOL/hotness 争议），DSA-2LM 不会优于 [[SoarAlto-OSDI25]] 类 placement 优化；非 Intel DSA 平台、无 THP、或内核版本无法 backport IDXD 时方案不可直接复用。
- **论文未覆盖**：多 VM / cgroup 竞争 DSA、迁移与应用写并发下的 tail latency、故障恢复与 descriptor 超时后的页一致性、DSA 设备故障降级路径。

### 实验可信度

- **Workload**：Graph500、PageRank、XSBench、BTree、Pandas 覆盖图、HPC、索引、数据分析，具代表性，但偏 **内存带宽/容量压力型 batch job**，缺在线 serving、数据库 buffer pool 等延迟敏感场景。
- **Baseline**：MEMTIS/TPP/NOMAD 是合理 SOTA；但 fast tier 约束方式不同（memmap vs cgroup），作者承认难以完全一致，分图比较；PageRank 因 RSS <16 GB 未进入 TPP/NOMAD 组图。
- **Ablation**：有 CPU / DSA-raw / DSA-opt 三档 copy 策略与 perf 分解，支持「aggregate path」必要性；缺少 WQ 数、batch 策略、唤醒间隔的独立 sensitivity 在端到端上的表格。
- **Metric**：以完成时间/吞吐为主，**无 p99 latency、迁移失败率、应用 CPU 利用率** 的系统化报告。

### 系统性缺陷

- **热检测路径仍占 CPU**：论文在引言承认 PEBS 等硬件采样可有 ~20% 降级；DSA-2LM 未动这一块，离「fully CPU-free tiered memory」仍有距离。
- **运维与兼容性**：8K LoC 驱动 backport + /misc 模块意味着升级内核成本高；论文未讨论与主线 6.x mm 子系统的长期合并路径。
- **资源隔离**：默认 `limit_chans=8` 占用多 WQ/PE，与其他 DSA 消费者（存储 CRC、网络 offload 等）的 QoS 冲突未评测。
- **可观测性**：提供 procfs 统计，但未给出生产级 tracing 或与 cgroup memory pressure 的联动策略。

## 局限与后续工作

- **局限 1**：评测绑定 **单款 CXL ASIC + 4th Gen Xeon**；结论对 AMD、无 DSA、或 CXL latency 更高一代设备的可迁移性未验证。
- **局限 2**：placement 仍假设 **hotness ≈ 应驻留 fast tier**，未处理 MLP/延迟敏感性；与 Colloid 的 latency-aware 方向正交但未实验组合。
- **局限 3**：对 **AutoNUMA** 等保守策略，DSA 集成往往只有 0%–12% 量级变化，说明「迁移不够激进」时硬件加速 copy 边际有限。
- **Future work 1**：与 [[NeoMem]] 等 **硬件 offload placement** 集成，量化 hotness 检测 + copy 双路径 CPU-free 后的剩余瓶颈。
- **Future work 2**：在 **NOMAD TPM / 并发写** 场景系统测量迁移窗口缩短对失败率、一致性、尾延迟的 trade-off，而非仅用端到端时间间接推断。
- **Future work 3**：在多租户云主机上测量 **DSA 与 DSA 争用 + CXL 带宽干扰**，验证 DMA pinning 动机在真实 VM 密度下是否成立。

## 相关

- **相关概念**：[[Tiered-Memory]]、[[CXL]]、[[Page-Migration]]、[[THP]]、[[DMA]]、[[PEBS]]、[[Intel-DSA]]、[[NUMA]]
- **同类系统**：[[MEMTIS]]、[[TPP]]、[[NOMAD]]、[[SoarAlto-OSDI25]]、[[Demeter-SOSP25]]、Nimble、Colloid、[[NeoMem]]、AutoNUMA
- **同会议**：[[ATC-2025]]
- **对比**：DSA-2LM 加速 **迁移执行**；[[SoarAlto-OSDI25]] 质疑 **hotness 放置准则**——二者解决 tiered memory 链条的不同环节，可组合而非替代。
