---
type: paper
name: MOST
full_title: "Getting the MOST out of your Storage Hierarchy with Mirror-Optimized Storage Tiering"
authors: [Kaiwei Tu, Kan Wu, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau]
venue: FAST
year: 2026
tags: [storage-hierarchy, tiering, mirroring, cachelib, load-balancing]
source_pdf: "[[fast2026-tu.pdf]]"
source_md: "[[fast2026-tu]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# MOST：以镜像优化的存储分层充分利用存储层次结构（FAST 2026）

> **原题**：Getting the MOST out of your Storage Hierarchy with Mirror-Optimized Storage Tiering

> **一句话总结**：现代两层存储（Optane/NVMe、NVMe/SATA、本地/远端 NVMe）性能比仅 1.25–2.2:1，纯 migration-based tiering 调负载慢且写放大严重；MOST 在经典 tiering 上为少量热数据（配置上限 ~20%，实测常 <2%）建 mirror，用 offloadRatio 反馈控制器在两层间概率路由读写，在 I/O 密集与 bursty workload 上吞吐比 Colloid/HeMem/Orthus 高最多 **2.34×**、P99 延迟降最多 **75%**，dynamic workload 设备写入量比 Colloid 少最多 **84%**，负载突变收敛 <**10s**（Colloid 限流迁移时需 **800s+**）。

## 问题与动机

数据中心 flash cache（[[CacheLib]] 等）普遍把多块异构设备叠成 **performance / capacity** 两层：Optane、PCIe NVMe、NVMe-oF、SATA SSD 等。与「DRAM 远快于 HDD」的经典层级不同，Table 1 显示两层 **延迟与带宽大量重叠**——16 KB 读带宽比 Optane vs PCIe 3.0 NVMe 仅 **1.5:1**，本地 vs 远端 PCIe 4.0 NVMe 仅 **1.25:1**，且比例随访问大小、读写比、并发度变化。

作者 claim：在这种 **非严格层级** 上，既要 **空间效率** 又要 **峰值聚合带宽**，现有两类方案都不够：

- **Single copy**（striping、hotness-based tiering）：每块数据只存一份。Striping 静态权重难匹配异构容量与动态负载；HeMem、BATMAN、Colloid 等 tiering 靠 **跨层 migration** 把热数据挪到快盘、冷数据挪到慢盘以均衡带宽。但存储层数据集远大于内存、写带宽低、读写互扰、磨损敏感——migration 收敛慢、foreground 干扰大、动态 workload 下写流量惊人（§2.3）。
- **Multiple copy**（full mirroring、inclusive caching、[[Orthus]] NHC）：能读负载均衡，但要么容量利用率极低（Orthus 在 random read-only 2.0× 强度下 mirror **690 GB** 才追上 Cerberus **50 GB** mirror 的吞吐），要么写路径受限（Orthus 写回策略无法 scale write、dirty copy 限制读路由）。

论文要回答：**能否像 tiering 一样省空间，又像 mirroring 一样用路由而非迁移快速调负载？** 实现载体是 CacheLib 上的用户态存储管理层 **Cerberus**（~1.5k LOC）。

## 关键观察 / 隐含假设

- **观察 1：两层设备性能差距小到「忽略慢层带宽」会浪费系统峰值。** Optane/NVMe 与 NVMe/SATA 在 micro-benchmark 中，performance 层饱和后 capacity 层仍有可观带宽；HeMem 类 classic tiering 热数据只从 performance 层服务，高负载吞吐在 1.0× 强度（performance 层带宽饱和点）封顶。Colloid 能 offload，但靠 migration，2.0× 强度下 migration 触发 SSD 后台活动导致 latency spike，吞吐反而不如 HeMem。
  - **依赖假设**：workload 会周期性或持续地把 performance 层推到饱和，且 capacity 层在饱和点仍有未被利用的带宽。
  - **可能失效场景**：两层性能差极大（如 NVMe+HDD）且热集很小，capacity 层对尾延迟贡献过大时，offload 可能得不偿失；或 workload 极冷，performance 层永不饱和，MOST 退化为近似 HeMem。

- 观察 2：动态 / bursty workload 下，migration 调负载的收敛时间与 hotset 规模、迁移带宽上限强相关，而 mirror + 路由的收敛时间与 hotset 无关。 Figure 5–6：负载从低到高突变时，Colloid++ 需 promote/demote 数百 GB（read-only 一天可达 performance 层 6.6 DWPD、capacity 层 3.1 DWPD，后者把 0.37 DWPD 额定寿命的 1 TB SATA 从 3 年缩到 129 天）；限迁移 100 MB/s 时收敛 >800s。Cerberus 在 <10s 内靠调整 offloadRatio 完成重平衡，且 hotset 从 20% 扩到 80% 时收敛时间几乎不变。
  - **依赖假设**：存在可识别的热数据段（segment 级频率计数），且 mirror 热集规模远小于 working set；burst 间隔短于 migration 收敛时间。
  - **可能失效场景**：working set 几乎全热（需 mirror 比例逼近 100% 才均衡）、或热集快速全盘轮换导致 mirror class 频繁换入换出，路由优势被 migration/metadata 开销抵消。

- 观察 3：少量 mirror + subpage 级 dirty tracking 可同时解决读负载均衡与写负载均衡，而 full mirroring / Orthus 写路径不行。 Mirrored class 内 4 KB subpage 的 invalid/location bit 让对齐写可像读一样按 offloadRatio 路由到单层；无 subpage 时写小于 2 MB segment，负载下降后需整段迁回 performance 层（Figure 7c）。Selective cleaning 按 rewrite distance 过滤高频写块，避免 blind cleaning 吃掉 25% 吞吐。
  - **依赖假设**：写多为设备访问粒度对齐（如 4 KB）；mirror class 占总容量比例小，metadata（极端 50% mirror 时 2 TB 层级仅 **128 MB**）可忽略。
  - **可能失效场景**：大量 sub-page / 非对齐写、或 mirror 比例被迫很大时，subpage 位图与 cleaning 线程成本上升；写密集且两副本频繁 diverge 时，读负载均衡退化为「只读 valid copy」。

- **假设 1：用 Linux block layer 采样的 end-to-end latency（200ms EWMA 窗口，θ=0.05）足以驱动 offloadRatio 与单向 migration，无需预知设备带宽比或 workload 分布。**
  - **证据强度**：中强。多静态/动态 workload、两种层级、生产 trace 上鲁棒；但未在设备性能剧烈漂移（GC 风暴、网络分区）下做长期稳定性证明。

- **假设 2：CacheLib 用户态 block 管理层能代表更广义存储栈（文件系统、数据库 buffer pool）的 tiering 问题。**
  - **证据强度**：中。实验隔离了 storage management layer micro-benchmark，也用 SOC/LOC + Meta production trace 做了端到端验证；但未嵌入真实 FS/DB 一致性语义。

## 核心方法

**MOST**（Mirror-Optimized Storage Tiering）在逻辑上将数据分为两类（Figure 1）：

1. **Mirrored class**：最热 segment 在 performance 与 capacity 两层各有一份副本，用于 **快速负载均衡**。
2. **Tiered class**：单副本；warm 在 performance 层，cold 在 capacity 层，保持经典 tiering 的空间效率。

**OffloadRatio 反馈控制器**（Optimizer，单 pinned 线程，每 200ms 调参）是核心。比较 smoothed end-to-end latency \(L_P\) 与 \(L_C\)：
- \(L_P > (1+\theta) L_C\) → 增大 offloadRatio，更多 mirrored 读/写/新分配落到 capacity；
- \(L_P < (1-\theta) L_C\) → 减小 offloadRatio；
- 近似相等 → 停止 migration。
低负载时 offloadRatio→0，行为接近 classic tiering（尽量打 performance 层）；高负载时 performance 层排队使 \(L_P\) 升高，自动 offload 到 capacity 直到两层延迟均衡。offloadRatio 到上限仍不均衡时，才 **扩大 mirrored class**（上限配置为总容量 **20%**；Figure 7a 显示 working set 占 95% 时实际 mirror 仅 **1.8%** 仍够均衡）。

**Mirror-class migration** 用 segment 级 read/write counter（类似 [[HeMem]]）识别热段：从 performance tiered 选最热 segment 复制到 capacity mirror；mirror 满则与 mirror 中最冷段 swap。Migration regulation 遵循「只从当前高延迟设备迁出」：performance 慢时禁止迁入 performance、允许迁入 capacity，反之亦然——避免 classic tiering 式双向抢带宽。

**Dynamic write allocation**：新数据先进 tiered class；分配位置以 offloadRatio 概率选 capacity，避免 performance 饱和时仍默认写快盘（classic tiering 的 load-unaware 分配）。

**Subpage management**：mirrored segment 按 4 KB 跟踪 clean / invalid-on-P / invalid-on-C 三态；对齐写可负载均衡。后台 **selective cleaning** 优先清理 rewrite distance 大的块，避免刚写又要读的块被过早同步。

**Tail latency protection**：用户可设 offloadRatioMax，限制 mirrored 热数据被 offload 到 tail 更差的 capacity 层。

**Cerberus** 实现于 [[CacheLib]] storage management layer（替换默认 striping），对上层 LOC（log-structured 大对象）和 SOC（4 KB bucket 小对象）透明提供 block 接口。同层还实现了 striping、Orthus、HeMem、BATMAN、Colloid/Colloid+/Colloid++ 作对比基线。

## 设计取舍

- **少量 mirror vs 全量 mirror（Orthus）**：Cerberus 用 ~1–20% mirror 换接近 Orthus 的读带宽与远优的容量利用率；代价是 mirror class 管理、subpage metadata、cleaning 线程与 Optimizer 复杂度（256 线程 micro-benchmark CPU 比 Colloid++ 高 **0–1.5%**）。
- **路由调负载 vs migration 调负载**：路由瞬时生效、写放大低，但 mirror 副本可能短暂不一致，读必须跟踪 valid copy；migration 保持单副本语义简单，但动态场景收敛慢且磨损大。
- **Segment 粒度（2 MB）**：平衡 metadata（每 segment 76 B）与设备带宽（Table 1 小 IO 降带宽）；更小 segment metadata 爆炸，更大则 performance 层空间浪费。
- **概率路由 vs 精确负载追踪**：实现简单、无先验 workload，但 offloadRatio 阶跃调整（ratioStep=0.02）可能振荡；依赖 θ 容忍区间换稳定性。
- **边界条件**：最适于 **两层异构 flash、I/O 密集、skewed hotset、burst 明显** 的 cache / lookaside 场景；三层及以上、强一致性多副本、tenant 级 QoS 隔离论文仅讨论为 future work（§5）。

## 实验与结果

**测试床**：40 核 Xeon、64 GB DRAM、Ubuntu 20.04；层级 (1) Optane P4800X 750 GB + Samsung 960 NVMe 1 TB，(2) NVMe + SATA 870 1 TB。设备微基准见 Table 1。

**Storage management layer micro-benchmark**（20% hotset、90% 访问概率、750 GB–1.2 TB working set）：
- 静态 random read-only：Cerberus 高低负载均优；2.0× 强度总 migration/mirror 写入 **50 GB** vs Colloid **134 GB**、Colloid++ **62 GB**；Orthus 吞吐相近但 mirror **690 GB** vs Cerberus **50 GB**。
- 静态 random write-only / sequential write / read-latest：Cerberus 显著优于 Orthus（写不均衡）、HeMem/Colloid（不 offload 写或 migration 干扰）；sequential write 下 Colloid+ 因无效 migration 更差。
- Dynamic bursty（15 分钟周期 2 分钟 burst）：read-only burst 吞吐 **1.53×** HeMem；write-only 高负载 **1.48×** HeMem；Colloid 平均 migrate **252 GB** 到 performance、**229 GB** 到 capacity，Cerberus 仅 mirror **~86 GB** 到 capacity。

**Ablation（§4.3）**：mirror class 占 95% working set 时仍只需 **1.8%** 总容量 mirror；无 subpage 时负载骤降后收敛慢；selective cleaning vs 全量 cleaning：吞吐 **-25%** vs clean 比例仅多 **5%**。

**CacheLib 端到端**（CacheBench + Meta production trace A–D，Table 4–5）：
- 静态 SOC/LOC：Cerberus 在 Optane/NVMe 最高 **1.36×**、NVMe/SATA **1.54×** vs 最佳基线。
- 生产 workload：平均吞吐 vs Colloid **1.24×**（Optane/NVMe）、**1.17×**（NVMe/SATA）；大值 log-structured 的 C/D workload 增益最大。
- 延迟：平均 **-14%**、P99 GET **-19%** vs 最佳基线；Optane/NVMe 上平均 **-20%**、P99 **-26%**；Workload D P99 从 **272 ms**（striping）降到 **27.76 ms**（Cerberus，Optane/NVMe）。
- Dynamic cache（95% GET）：Cerberus 无 migration 尖峰即可跟随 burst。
- YCSB lookaside：最高 **1.43×** 吞吐、P99 **-30%** vs 最佳系统。

## 批判性分析

### 论证链条

主链条清晰：**测量证明现代两层 flash 性能比窄且随 workload 变**（Table 1）→ **定性 + Table 2 归纳 single-copy migration 与 multiple-copy caching 的缺口**（动态适应性、写带宽、容量）→ **MOST 用「小 mirror + tiering + offloadRatio」把负载均衡从 migration 改成路由**（§3）→ **micro-benchmark 覆盖读写模式与强度 + dynamic burst + 生产 trace 端到端**（§4.1–4.4）→ **ablation 支撑 mirror 比例、subpage、selective cleaning 必要性**（§4.3）。

最强证据是 **dynamic workload 的双指标对比**：吞吐随 burst 提升（1.48–1.53×）同时 migration 写入量降一个数量级（86 GB vs 252+229 GB），并把设备寿命模型量化到 DWPD/年限——把「路由 vs 迁移」从定性推到可运维结论。

薄弱跳步：**从 CacheLib block 层外推到通用 FS/DB**：实验未覆盖 crash consistency、多租户 block 共享、或 erasure coding 等多副本语义。Related work 将 ML-based tiering、PolyStore、分布式 cache 划为 orthogonal，但未实验证明 MOST 在三层及以上、NVMe+HDD 宽差距层级仍占优。

### 假设压力测试

**workload assumption**：评估偏重 **skewed hotset（20% 占 90% 访问）、cache/lookaside、Meta flash cache trace**。对均匀随机、冷数据主导、或 range scan 密集（YCSB-E 因 CacheLib 不支持被排除）的场景，mirror 收益可能缩小。生产 trace 仅四组，且 C/D 大 value log-structured 最受益——小对象 flat 场景 Cerberus 仅略优于 Colloid++。

**resource bottleneck assumption**：默认瓶颈是 **两层间带宽未聚合 + migration 太慢**，而非 DRAM cache 命中、网络栈、或 CacheLib 上层索引锁。实验刻意限制 DRAM（200 MB–1 GB）以 stress flash 层；真实部署 DRAM 更大时，storage management layer 压力下降，绝对增益可能缩小。

**hardware/deployment assumption**：单机双设备、本地块设备；NVMe-oF 仅在 Table 1 微基准出现，主实验是本地 Optane/NVMe/SATA。远端盘尾延迟、网络抖动下 offloadRatio 反馈是否稳定未专门测试。仅 **64 GB DRAM** 的 server 配置与大规模 cache 节点不完全一致。

**scaling assumption**：mirror class 上限 20% 在论文 workload 下够用，但 **working set 接近全热或 hotset 快速漂移** 时，mirror 扩容会逼近 Orthus 的空间代价；论文 Figure 7a 显示极端 working set 下 mirror 比例仍低，但未给出「hotset 占 100% 访问」的 stress test。

**correctness/SLO assumption**：mirror 单写副本 + 异步 cleaning 在 cache 场景可接受；论文明确 consistency、WAL、multi-tenant QoS 为 future work。未讨论 cleaning 或 migration 中途崩溃后的副本一致性；tail latency protection 依赖用户设 cap，默认自动策略在 capacity 尾延迟极差时可能伤害热数据 SLO。

### 实验可信度

**强项**：基线覆盖全面（striping、Orthus、HeMem、BATMAN、Colloid 三变体），且对 Colloid 做了 **Colloid+/++** 公平增强（写延迟、参数鲁棒性）；HeMem quantum 针对存储调到 **200ms**；报告 migration 字节数、DWPD、收敛时间而不只吞吐；生产 trace + YCSB 补充 synthetic micro。

**弱点**：
- 两层层级为主，**三层扩展**只有讨论无实验；
- Orthus 对比揭示空间效率，但 Orthus 是作者同组先前工作，调参熟悉度可能不对称；
- CPU 开销仅一条 note（0–1.5%），无 breakdown；
- 缺少与 **Nomad**（临时双副本迁移）、**AutoTiering** 等 storage-specific 系统的直接数值对比；
- 长期运行（天数/月）下 offloadRatio 振荡、磨损均衡、mirror class 碎片化未评估。

### 系统性缺陷

- **实现与运维**：Cerberus 是 CacheLib 用户态层，需应用走 CacheLib 路径；非 CacheLib 栈需重新实现 MOST 元数据（segment/subpage/cleaning）。
- **尾延迟与隔离**：Optimizer 以平均 end-to-end latency 为目标，非 per-tenant SLO；burst 时 offload 到 SATA 可能拉高热 key P99——虽有 offloadRatioMax，但自动 trade-off 论文未充分量化。
- **故障恢复**：migration regulation、cleaning 中断、单副本失效后的重建策略 **论文未讨论**。
- **可观测性**：offloadRatio、mirror class 占用、subpage diverge 比例等运维指标未描述。
- **写放大形态**：dynamic 场景总写入比 Colloid 少最多 **84%**，但 mirror 本身仍引入初始复制写；极端 write-only 下收益来自写路由而非读 mirror，与 read-heavy cache 假设部分绑定。

## 局限与后续工作

- **局限 1**：仅系统论证两层 MOST；多 tier mirror + 更复杂优化策略留作 future work（§5）。
- **局限 2**：块级透明管理，无 tenant 感知；性能隔离、fairness、QoS 需 request hint 扩展。
- **局限 3**：一致性仅提纲式提及 WAL，无完整 crash/recovery 研究。
- **Future work 1**：在 **三层及以上**（如 Optane + NVMe + SATA）测量 mirror 应放在哪两层、offloadRatio 是否需向量而非标量。
- **Future work 2**：与 **Nomad** 式 transient copy、erasure coding（EC-CACHE）等「有限冗余」方案做写入量与收敛时间的 head-to-head。
- **Future work 3**：生产级 **tenant-aware MOST**——按 tenant 限制 offload、绑定 mirror quota，并测 tail latency SLO 是否可证。

## 相关

- **相关概念**：[[Storage-Tiering]]、[[Mirroring]]、[[Load-Balancing]]、[[Heterogeneous-Storage]]、[[RDMA]]
- **同类系统**：[[CacheLib]]、[[Orthus]]、[[HeMem]]、[[Colloid]]、BATMAN、AutoTiering、Nomad、Kangaroo
- **同会议**：[[FAST-2026]]
- **对比**：[[Orthus]] 用全性能层 duplicate 做 NHC 读 offload；MOST 用少量 cross-tier mirror + tiering 同时改善读写动态性与空间效率
