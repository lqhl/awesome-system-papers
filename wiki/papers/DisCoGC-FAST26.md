---
type: paper
name: DisCoGC
full_title: "Discard-Based Garbage Collection for Distributed Log-Structured Storage Systems in ByteDance"
authors: [Runhua Bian, Liqiang Zhang, Jinxin Liu, Jiacheng Zhang, Jianong Zhong, et al.]
venue: FAST
year: 2026
tags: [garbage-collection, log-structured, ssd, write-amplification, bytedance]
source_pdf: "[[fast2026-bian.pdf]]"
source_md: "[[fast2026-bian]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Discard-Based Garbage Collection for Distributed Log-Structured Storage Systems in ByteDance (FAST 2026)

> **一句话总结**：基于 ByteDrive 生产 trace 发现 SAR/offline 类 workload 产生长连续 stale range，DisCoGC 用 discard 直接释放垃圾空间、辅以低频 compaction 控碎片，在混合生产集群上把 logical write amplification 降 32%、total write amplification 降 25%、TCO 降约 20%，且前台延迟无回退。

## 问题与动机

ByteStore 是字节自研的 SSD-based 分布式 append-only 存储底座，承载 ByteDrive（块存储）、TOS、NAS、ByteGraph、ByteNDB 等上层服务。论文聚焦 **ByteDrive + ByteStore** 栈：ByteDrive 把随机写转成 append-only 写到 LogFile，上层通过 LSM-Tree 索引最新 LBA 映射，底层 ChunkServer 用自研 UFS 管理 chunk replica。

周期性 [[Garbage-Collection|GC]] 是 append-only 系统的刚需。早期 ByteDrive 采用 **compaction-only GC**：扫描 segment 的 LSM-Tree 找 stale range，把 LogFile 中仍有效的数据搬到新 LogFile 再删旧的。作者 claim 的根本痛点是 **space amplification 与 write amplification 负相关**——为降空间必须更激进 compaction，但 logical write amplification（LWA）暴涨，叠加 SSD 内部 GC 带来的 physical write amplification（PWA），总 WA = LWA × PWA，每月额外 TCO 达数百万美元量级。更激进 compaction 还会与前台 I/O 争抢带宽和 CPU。

单纯把 compaction 调得更激进并不能降 TCO：空间省了，写放大和 SSD 磨损反而更糟。作者因此问：**能否在不搬有效数据的前提下直接回收 stale 物理空间？** 这指向 Linux/SSD 生态里早已存在的 discard/trim 语义，但把它嵌进多层云存储栈（Volume → Segment → LogFile → UFS）并不 trivial。

## 关键观察 / 隐含假设

- **观察 1**：SAR（搜索/广告/推荐：倒排索引构建、AI 模型下载/推理）和 offline（Spark 等分布式计算）workload 呈现 **高顺序写 + 秒级频繁覆盖**，在 LogFile 上形成 **长且连续的 stale range**。
  - **依赖假设**：上层应用通过 Ext4 等文件系统写 ByteDrive volume，写模式在 segment 层可被聚合成大块 sequential write（>256 KiB 占比高）；overwrite 热点在秒级时间窗内局部化。
  - **可能失效场景**：online 类 workload 写高度碎片化（>60% 为 4 KiB），热点每 ~5 秒概率性迁移，产生稀疏、小块 garbage，discard 收益有限。
- **观察 2**：多层存储栈的 allocation unit **层间不对齐**（EC stripe、4 KiB block + 32 B sector header、UFS cluster = 4×4064 B），直接 discard 会在边界留下不可回收垃圾（boundary loss）。
  - **依赖假设**：boundary loss 可用「相邻 discard 范围小幅重叠扩展」+「EC stripe unit 与 cluster 对齐」缓解，且重叠不会破坏正确性（discard 对同一 range 可重入）。
  - **可能失效场景**：极度碎片化 garbage 使 boundary extension 的 MiB 级重叠成本上升；EC 配置变更后对齐假设需重新验证。
- **观察 3**：discard 与 compaction **互补**——discard 零搬移回收大段垃圾但制造 LogFile/chunk 稀疏碎片；compaction 合并碎片但写放大高。SSD trim IOPS 远小于 write IOPS（Model B 仅 3%），不及时 trim 会触发激进 SSD GC。
  - **依赖假设**：生产集群可通过 batching、并行度上限、discard IOPS flow control 把 discard 元数据开销压住；trim filter/merger 能把 trim 命令数约束在 SSD 能力内。
  - **可能失效场景**：discard burst 超过 flow control 容量时，discard ratio 跌破 80% 且 SSD 使用率持续 >85%，需 SRE 人工介入（增并行、限 offline I/O 或扩容）。
- **假设 1**：**TCO 主要由 space amplification 和 write amplification 共同决定**，且二者 trade-off 的改善可直接换算为 ~20% TCO 节省。
  - **证据强度**：**中**——生产监控有 LWA/PWA/空间利用率数据，但 TCO 公式和成本分项未完全公开。

## 核心方法

DisCoGC（**Discard-and-Compaction combined GC**）在 BlockServer 侧协调两种机制：**高频轻量 discard** 为主回收路径，**低频 compaction** 处理碎片和 metadata 压力。

### Discard 执行路径

自顶向下异步穿透四层（Fig. 11）：
1. BlockServer 扫描 segment LSM-Tree，找已失效且未 discard 的 LogFile range
2. 经 ByteStore SDK 下发 discard 到对应 chunk replica
3. ChunkServer UFS 定位 cluster，改 MetaPage 释放 cluster
4. BlockServer 记录已成功 discard 的 range，防重复

与 compaction 不同，discard **不读、不写有效数据**，时间复杂度对 garbage range 大小近似常数。

### 边界丢失缓解（§4.2）

两类 boundary loss：
- **EC loss**：BlockServer 发出的 discard 粒度任意，但 SDK 必须按完整 EC stripe（如 4+1、16 KiB stripe）discard
- **Cluster loss**：UFS allocation unit 是 cluster（4 个 4064 B data sector），4 KiB 对齐的 EC stripe 与 cluster 不对齐

对策：
- **Boundary extension**：新 discard 若邻接已 discard range，向相邻方向扩展至多几 MiB，利用 discard 可重入性消除两侧边界垃圾
- **Discard-friendly EC stripes**：stripe unit size 设为 `n × 4 × 4064 B`，与 UFS cluster 对齐

### Discard batching 与调度（§4.3）

- 同一 LogFile 的多个 discard range **合并为一次请求**（batch size 1–64，生产调优后约 10，极端 burst 到 32/64）
- **并行度感知调度**：segment 粒度生成 discard task，并行上限 P；周期性选 top-k 最大 discard range 的 segment
- **Flow control**：限制最大 discard IOPS，防止 MetaPage 更新风暴冲击前台

### Compaction 与 discard 协同（§4.4）

Garbage ratio 计算考虑 boundary loss：每边界估计损失 LPB = 半个 EC stripe 长度。

Compaction 双模式独立调度（分钟级间隔）：
- 默认：选 garbage ratio 最高的 top-k segment，回收 boundary loss 和小块不可 discard 垃圾
- metadata 压力模式：LogFile 数超阈值时，改选 LogFile 最多的 segment，优先降碎片

DisCoGC 会带来 2%–10% 更高的 PWA（碎片导致更频繁 SSD GC），但 LWA 大幅下降，**NAND 总写入字节仍减少**，延长 SSD 寿命。

### Trim filter 与 merger（§4.5）

SSD trim 分两阶段：前台写 trim log + 后台更新 LBA-PBA 表；超过阈值（如 128 MiB）的 trim 会 flush write cache，延迟飙升。

- **Trim filter**：仅对 ≥128 KiB range 发 trim，减少 trim 次数
- **Trim merger**：把 LBA 相邻的小 range 合成一次 trim

Model A（trim IOPS 160K）filter 反而有害；Model B（trim IOPS 仅 6K）filter+merger 把 PWA 从极高降到 1.65–1.74。

### 工程实现要点（§5）

- 分阶段上线：offline 集群 → per-volume 开关 → mock discard（只记状态不真释放）→ 全量
- Crash consistency：per-segment discard LogFile + WAL，维护 issued / successfully discarded range
- 内存：4 KiB 粒度的 issued/failed bitmap，用 roaring bitmap 压缩，failed bitmap 稀疏时总内存降 25%–45%

## 设计取舍

- **取舍 1**：用 discard 换 LWA，接受 LogFile/chunk 稀疏化带来的 metadata 膨胀和 2%–10% PWA 上升；靠低频 compaction 和 trim 优化兜底。
- **取舍 2**：flow control 和 batching 限制 discard 吞吐，在 burst 时可能暂时积压垃圾（discard ratio <1），换取前台 CPU/SSD IOPS 稳定。
- **取舍 3**：boundary extension 以少量「重复 discard」和 MiB 级重叠换取边界空间回收，避免维护跨层 boundary loss 追踪结构的高内存开销。
- **边界条件**：对 SAR/offline 等高顺序、高覆盖 workload 最优雅；online 碎片化 workload 仍有 2%–5% TCO 收益但不足以单独 justify 工程投入；trim 策略必须 per SSD model 调参，Model A/B 行为差异巨大。

## 实验与结果

- **生产集群**（混合 online/SAR/offline，双 24C48T、256 GiB、200 Gbps、16 SSD）：baseline space amplification 1.37 vs DisCoGC 1.23（约低 10%）；LWA 降 **32%**；PWA 最高升 10%；总 WA 降 **25%**；**TCO 降约 20%**；latency 和 per-TiB-volume 带宽无劣化；>90% invalid range >128 KiB，>70% >1 MiB
- **Trace replay**（online / SAR / offline + FIO 32 MiB 随机写）：DisCoGC 的 space amplification–LWA 曲线整体左下移；SAR TCO 降 **>25%**；online 最差仍降 2%–5%；各 workload 前台写延迟（avg/p99）无显著变化
- **Factor ablation**（固定 space amplification：online 1.2、SAR 1.05、offline 1.2）：+Discard+flow control → LWA 降 8.4%–13.9%，discard ratio 0.45–0.88；+Batch(64) → 再降 2.7%–11.7%，discard ratio ≈1；+BoundExt → 再降 5.5%–16.1%
- **Sensitivity**：SSD 空间使用率只影响 PWA 不影响 LWA；discard IOPS limit 越高 LWA 越低但延迟变差（与前台争 CPU）
- **Trim**：Model A trim 降 PWA 1.4→1.3；Model B 无 filter 时 trim IOPS 打满导致系统濒临失败，128 KiB filter 后 PWA 显著下降
- **资源**：vs compaction-only，CPU 降到 **82.9%**，内存升到 **102.9%**（discard bitmap 开销可控）

## Critical Analysis

### 论证链条

论文链条清晰：**trace 刻画 garbage 形态 → discard 针对大连续垃圾的设计 → 多层工程挑战逐一拆解 → 生产+离线双重验证**。最强证据来自生产监控（数月级、exabyte 规模集群），比纯 FIO 更有说服力。

潜在跳步：(1) **20% TCO** 由 WA 和 space amplification 改善外推，成本模型未公开，读者无法独立复核分项贡献；(2) 生产实验是 **mixed workload 整体对比**，未做严格的 per-tenant A/B 隔离；(3) 声称 online workload「不值得单独投入」与「混合集群仍有 20% 收益」之间的归因——收益可能主要来自 SAR/offline 占比，而非 online 本身。

### 假设压力测试

- **Workload 漂移**：若业务从索引/模型下载转向大量 4 KiB 随机写（典型 OLTP），discard ratio 下降，系统更多 fallback 到 compaction，DisCoGC 优势收窄至论文报告的 2%–5% 区间。
- **硬件代际**：论文 SSD trim IOPS 跨两个型号差 27×（160K vs 6K），结论高度依赖具体 SSD；新盘若 trim 能力增强，filter/merger 的必要性可能下降甚至适得其反（Model A 已显示 filter 有害）。
- **规模外推**：LogFile 上限 2 GiB、bitmap 按 4 KiB 粒度跟踪；极大规模 segment 或极高 LogFile 数时 metadata 与内存压力需独立测量——论文只报告 offline trace 下 102.9% 内存。
- **多租户干扰**：online trace 显示多容器共享 volume 导致热点每 5 秒迁移；discard scheduling 的 top-k segment 策略在极端租户混部下是否公平，论文未讨论 QoS 隔离。

### 实验可信度

- **Benchmark 代表性**：三类 ByteDance 生产 trace（合计数百 TiB 写入）+ FIO 合成，覆盖顺序/随机两端；但 **缺少公开 trace**，外部复现困难。
- **Baseline 公平性**：compaction-only 作为 baseline 合理，且在同一 space amplification 目标下对比 WA 曲线，控制变量较好。
- **Ablation 完整性**：discard / batch / boundary extension 逐步叠加，支撑设计分解；trim 部分按 SSD model 分开展开，诚实地暴露 model 差异。
- **缺失维度**：尾延迟只在 avg/p99 层面报告，未深入 discard burst 期间的极端 tail；跨层故障恢复（BlockServer 宕机后 discard WAL replay 耗时）未量化；与 open-channel SSD、ZNS 等近年方案无直接对比。

### 系统性缺陷

- **运维复杂度**：per-volume 开关、discard ratio 监控告警、SRE runbook（增并行 / 限 offline / 迁移 volume）说明系统并非「set-and-forget」，需要持续调参。
- **正确性风险**：discard 元数据主要在 BlockServer 内存 + WAL；论文论证了 crash consistency，但 **未讨论 Byzantine 或 silent corruption 场景** 下 discard 与 EC 重建的交互。
- **可观测性**：有 discard ratio、invalid range 分布监控，但缺少对 boundary loss 实际累积量的在线度量，调优 EC stripe 对齐是否最优难以持续验证。
- **兼容性**：深度绑定 ByteStore UFS 的 cluster 布局和 EC 配置；移植到标准 Ext4/XFS + 商用块存储需重新解决对齐与 trim 路径，论文未提供通用框架。

## 局限与 Future Work

- **局限 1**：DisCoGC 对碎片化 online workload 收益有限（2%–5%），作者明确建议此类场景不值得工程投入。
- **局限 2**：trim 优化效果强依赖 SSD 型号，缺乏统一的 auto-tuning 机制；Model A 上 filter 反而降低性能。
- **局限 3**：discard 元数据（bitmap + WAL）带来内存开销和 crash recovery 路径，虽可控但未与 compaction-only 的恢复延迟做端到端对比。
- **Future work 1**：对目标 workload 做 **write sequentiality + overwrite frequency** 的自动化准入评估，避免盲目部署。
- **Future work 2**：研究 **discard ratio 与 SSD 使用率的联合反馈控制**，减少 SRE 手动调 discard parallelism/IOPS 的需求。
- **Future work 3**：在 open-channel / [[ZNS]] / FDP 等暴露更多放置语义的设备上，测试 discard 与 device-level GC 的跨层协同是否仍有冗余（对比 [[DOGI-FAST26]]、[[WARP-FAST26]] 等方向）。

## 相关

- **相关概念**：[[Garbage-Collection]]、[[Write-Amplification]]、[[Log-Structured-Storage]]、[[Erasure-Coding]]、[[TRIM]]、[[Compaction]]、[[LSM-Tree]]、[[Disaggregation]]
- **同类系统**：[[ByteStore]]、[[ByteDrive]]、IPLFS、F2FS、RocksDB、SpanDB
- **同会议**：[[FAST-2026]]
- **对比**：与单层 filesystem trim（IPLFS）或 Slack Space Recycling 不同，DisCoGC 面向 **多层云块存储栈** 的 production GC 协调；与 [[DOGI-FAST26]]（placement 降 WA）正交，可叠加思考
