---
type: paper
name: PolarStore
full_title: "PolarStore: High-Performance Data Compression for Large-Scale Cloud-Native Databases"
authors: [Qingda Hu, Xinjun Yang, Feifei Li, Junru Li, Ya Lin, et al.]
venue: FAST
year: 2026
tags: [cloud-database, compression, computational-storage, polardb, hardware-software-codesign]
source_pdf: "[[fast2026-hu.pdf]]"
source_md: "[[fast2026-hu]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# PolarStore: High-Performance Data Compression for Large-Scale Cloud-Native Databases (FAST 2026)

> **一句话总结**：基于「软件层 16 KB 页→4 KB 对齐块（保留算法/输入灵活性）+ 硬件层 PolarCSD 字节级二次压缩（借 [[FTL]] 免软件索引）」的双层压缩，配合 redo 旁路、lz4/zstd 页级自适应与 per-page log 三条 DB 路径优化，在 [[PolarDB]] 生产部署 100+ PB 上实现压缩比 **3.55**、存储成本降 **~60%**，Sysbench 性能与未压缩集群持平。

## 问题与动机

云原生 RDBMS（[[AWS-Aurora]]、Azure Hyperscale、[[PolarDB]]）普遍采用存算分离：RW/RO 计算节点共享远端存储，redo log 异步 apply 生成 page，计算弹性已解决，但**存储成本**在业务低谷期仍是用户痛点。数据压缩是直观降本手段，却长期卡在两类 trade-off：

1. **软件压缩**：B+-Tree 内嵌/page compression、[[LSM-Tree]] compaction、log-structured 块存储（如 [[Pangu]]）都能在算法和输入块大小上灵活调参，但 byte-level 索引带来复杂空间管理与 GC/I/O 放大；若退到 4 KB 索引粒度，408 GB 数据集上空间比 byte-level 多 **80.5%**（Figure 2a）。
2. **硬件压缩**：in-storage [[CSD]]、PCIe FPGA、Intel QAT 等把算力 offload 出去，但受 [[NVMe]] 4 KB LBA 与固化算法约束，无法对冷热数据分别选大块+zstd 或小快+lz4。

作者 claim：需要**软硬协同**同时拿到 byte-level 空间效率、参数灵活性和关键 I/O 路径上的低延迟，并能在数千台存储服务器规模下稳定运行。PolarStore 是 Alibaba Cloud PolarDB 共享存储层的答案，不是通用压缩库。

## 关键观察 / 隐含假设

- **观察 1：用户感知延迟几乎只绑在两条 I/O 路径上**——transaction commit 的 redo log write，以及 [[Buffer-Pool]] miss 时的 page read；其它后台 page write / compaction 不在 query critical path。
  - **依赖假设**：PolarDB 式存算分离 + redo-driven page generation 的 workload 形态；OLTP 以 16 KB（或 8 KB）页对齐访问为主。
  - **可能失效场景**：分析型全表扫描、非页对齐 I/O、或把压缩开销放在用户可见路径上的引擎设计（如 compute 节点内嵌压缩的 InnoDB/MyRocks）。

- 观察 2：双层压缩下，软件层 zstd 相对 lz4 的压缩优势会被硬件 gzip 大幅「吃掉」——算法层 zstd 比 lz4 省 58.9% 空间，经 PolarCSD gzip level 5 二次压缩后差距缩至 9.0%（Figure 5c），因为硬件 gzip 的 Huffman 阶段还能压缩 lz4 输出，而对已含 Huffman 的 zstd 增益有限。
  - **依赖假设**：软件层选 lz4/zstd，硬件层固定 gzip；二者编码结构互补而非叠加。
  - **可能失效场景**：更换硬件算法（如 zstd ASIC）、或单层软件压缩部署中仍应优先 zstd 的直觉在此失效。

- 观察 3：4 KB 软件对齐块使「省几个字节」可能等价于「少一次 4 KB I/O」——例如 lz4 压到 4097 B 需 8 KB I/O，zstd 压到 4096 B 只需 4 KB；此时 zstd 更高解压延迟仍可能总延迟更低。阈值 300 B/µs 来自「省 4 KB I/O ≈ 12–14 µs」的存储特性。
  - **依赖假设**：压缩后 I/O 按 4 KB ceiling 对齐计费；queue-depth 与延迟关系在评估阈值时稳定。
  - **可能失效场景**：更大页、不同对齐策略、或 NVMe 高 QD 下 per-I/O 延迟模型变化。

- 观察 4：CSD 的物理-逻辑空间解耦使 per-page log 可行——为每个 16 KB 页预留 4 KB 稀疏 log 空间，在常规 SSD 上约 25% 空间放大，在 CSD 上几乎无额外物理占用。
  - **依赖假设**：RO 节点 LSN 落后导致 redo log 分散、需多次随机读才能 consolidate page 的场景足够常见，值得用空间换尾延迟。
  - **证据强度**：**中**——P95 在 lag 1 s 实验设置下降 28.9–39.5%，但 >128 线程后 RO CPU 成为瓶颈，收益消失。

- **假设 1：集群内 chunk 间压缩比差异显著且持久**，单纯按 logical space 调度会导致部分节点 logical 满而 physical 空、另一些相反（Figure 9a：12.1% 节点 below-average ratio 浪费 1.72% logical space，78.6% above-average 浪费 9.17% physical space）。
  - **证据强度**：**强**——来自 500 host / 6000 PolarCSD1.0 的真实集群测量。

- 假设 2：每机 10–12 块 CSD 时，host-based open-channel FTL 的 CPU/内存 footprint 与存储软件争抢资源，是生产 slow I/O 主因之一（12 块 × 15.36 GB FTL 内存 ≈ 184 GB；每盘需 ~2 核）。
  - **证据强度**：**强**——18 个月 26 次 slow I/O，其中 12 次内存、9 次 CPU 争抢；5 次长时间 slow I/O 来自驱动 bug 扩大故障域。

## 核心方法

PolarStore 是 PolarDB 共享存储子系统，向上暴露块接口，核心是三块：**双层压缩**、**DB-oriented 优化**、**大规模部署治理**。

### 双层压缩（软件 + PolarCSD）

**软件层（轻量压缩）**：RW 节点写 16 KB 页时，leader 用 lz4/zstd 压成若干 **4 KB 对齐块**，3-way Raft 复制；空间管理分两级——centralized 128 KB chunk allocator + per-chunk bitmap 4 KB 分配；**hash table** 维护 uncompressed 16 KB 地址 → compressed 4 KB 地址映射，WAL 仅用于恢复。这样软件只需管粗粒度块，避免 byte-level 索引开销。

**硬件层（PolarCSD）**：标准 [[NVMe]] 接口，固化 **gzip level 5** 处理 4 KB 对齐输入，输出 byte-level 物理布局；扩展 page-mapping [[FTL]]，L2P 条目从 5 B 增至 8 B（12-bit length + 12-bit offset），实现 4 KB LBA → 变长 PBA。逻辑容量 7.68 TB，物理 NAND ≥3.2 TB（按平均硬件压缩比 2.4  provisioning）。

**灵活写接口**：`normal`（页对齐，默认双层）、`no-compression`（非对齐或用户指定）、`heavy compression`（归档：读-解压-合并-大块重压缩，牺牲随机读换更高压缩比）。

### DB-oriented 优化（回应观察 1–3）

- **Opt#1 redo 旁路**：redo log 走 **no-compression** + 独立 **Intel Optane** 设备，绕开软件与硬件双层压缩，匹配 log 小、可回收的特性。
- **Opt#2 lz4/zstd 页级自适应**（Algorithm 1）：仅在 CPU <20% 且页更新率 >30%（或首次写）时，对 lz4/zstd 各试压，比较 `benefit/overhead` 与 300 B/µs 阈值选型；高 CPU 时直接用 lz4 避免选型开销。
- **Opt#3 per-page log**：redo log 从内存淘汰时，把同一页的多条 log **预合并**进 dedicated 4 KB 稀疏区，page consolidation 单次读完成，降低 RO lag 场景的 read amplification。

### 大规模部署（PolarCSD2.0 + compression-aware scheduling）

**PolarCSD1.0 教训**：open-channel / host FTL 导致资源争抢与整机故障域；临时方案是每机减至 10 盘并**关闭软件压缩**。

**PolarCSD2.0**：改 **device-managed FTL**（ARM 核跑 L2P），单盘故障不拖死 host；NAND 3.84 TB、逻辑 9.6 TB；L2P 条目 7 B（offset 粒度 16 B 换 1 B 元数据）；PCIe 4.0。

**Compression-aware scheduling**：在 logical (x) × physical (y) 平面上把节点分四区，从 Zone A（physical 高/logical 低）迁 **低压缩比** chunk 到 Zone D/C/B，反向迁 **高压缩比** chunk；配合 TRIM 修正 physical 监控（启用后平均 physical 读数降 3%）。

## 设计取舍

- **取舍 1：软件 4 KB 对齐 vs 硬件 byte-level**——用软件粗索引换实现简单与 Raft 友好，把细粒度空间效率交给 CSD FTL；代价是软件层仍可能因 4 KB ceiling 浪费空间（观察 3 正是利用这一「缺陷」做算法选择）。
- **取舍 2：PolarCSD 算法固化 gzip**——换取量产可维护性与 FTL 内联加速；灵活性全部压在软件层，硬件无法 per-tenant 换算法。
- **取舍 3：Opt#1 用昂贵 Optane 旁路 redo**——用专用高性能介质换 commit 路径零压缩；容量有限，依赖 log 快速回收，不适合超大 log 或 log 也要求压缩的场景。
- **取舍 4：per-page log 的 4 KB/页逻辑预留**——仅 CSD 空间解耦下物理代价可接受；传统 SSD 上约 25% 放大，设计不可移植。
- **取舍 5：heavy compression 模式**——归档/快照顺序读友好，随机 page read 有 I/O 放大，明确不服务热数据。
- **边界条件**：在 PolarDB 共享存储、页对齐 OLTP、CSD 可定制部署时设计最优雅；迁移到通用云盘、compute 侧压缩、或无法定制 CSD 的环境需重做索引与调度假设。

## 实验与结果

- **生产规模**：PolarCSD1.0 部署 500+ 存储服务器 / 6000+ 设备；PolarCSD2.0 部署 1200+ 服务器 / 14400+ 设备；总数据 **>100 PB**。
- **空间与成本**（Table 2）：C1（仅硬件，ratio **2.35**）logical Cost/GB **0.62×** baseline P4510；C2（双层+全优化，ratio **3.55**）logical Cost/GB **0.37×** P5510 baseline，约 **60%** 存储降本；C2 物理介质成本 1.32× P5510。
- **端到端 DB 性能**（Sysbench，8 核 32 GB 实例，480 GB 数据，16 线程，I/O bound）：C2 与无压缩 N2（P5510）**吞吐/均值/P95 基本持平**；C1 比 N1 慢约 **10%**。
- **Ablation**（C2 上逐项加优化，OLTP-RW）：仅 PolarCSD → 吞吐 −7.4%；+软件双层 → −19.6%（redo 压缩拖累）；+bypass redo → −8.9%；+lz4/zstd 选择 → −2.1%；per-page log 在 RO lag 1 s 时 P95 降 **28.9–39.5%**（<128 线程）。
- **硬件代际**：PolarCSD2.0 相对 1.0，latency >4 ms 的 I/O 比例读/写各降约 **36.7× / 38.8×**。
- **调度**：C1 上 >90% 节点压缩比收敛到 [2.2, 2.7]；C2 上 87.7% 收敛到 [3.15, 3.85]。
- **对比 DB 层压缩**：同配置下 PolarDB+PolarStore vs InnoDB table compression / MyRocks，PolarDB 吞吐与延迟显著更优（压缩在共享存储层，不占用户 compute 配额）。

## Critical Analysis

### 论证链条

观察（索引粒度 vs 性能、硬件灵活性缺失、关键路径仅 redo+page read）→ 双层压缩 + 三条 Opt + 部署治理，逻辑链条闭合较好。生产 100 PB 与 A/B 集群（N1/N2 vs C1/C2）支撑「降本不伤性能」主 claim。薄弱环节在于：**性能持平**主要在与自家无压缩集群对比，且 Sysbench 16 线程、60 GB/节点的压力模型偏 I/O bound；对「软件压缩索引开销」的论证更多靠 408 GB 微基准（Figure 2）而非公开 trace replay。C1 曾被迫关软件压缩，说明 1.0 代硬件路径曾削弱双层故事，2.0 才完整验证。

### 假设压力测试

- **Workload**：金融/F&B/Wiki/航空四类生产 dump 验证了 lz4/zstd 比例差异，但未覆盖极端 write-heavy、小页、或 cross-region 复制延迟敏感型事务。
- **硬件**：强依赖自研 PolarCSD；gzip level 5 固定，若 NAND 代际或 FTL GC 行为变化，硬件层 2.4× 假设需重测。
- **规模**：compression-aware scheduling 的 chunk 迁移成本、迁移中 tail latency 影响论文未量化。
- **多租户**：同一存储池多用户压缩比差异被调度缓解，但 noisy neighbor 在 CPU 侧做软件压缩时的隔离论文未讨论。

### 实验可信度

- **强项**：生产集群成本账、代际硬件对比、逐项 ablation 分离 redo/page read/page write 内部延迟（Figure 13）。
- **局限**：Sysbench 基准较标准但线程数少；与 InnoDB/MyRocks 对比时压缩位置不同（存储层 vs compute 层），更像「架构优势」而非同等条件下的算法对决。
- **Ablation 可信度**：update 实验强制每次重选算法，作者承认高估 page write 延迟；真实 workload 下写路径开销可能更低。

### 系统性缺陷

- **故障与恢复**：压缩状态下 WAL/index 恢复路径有描述，但双副本不一致、部分压缩页损坏时的行为论文未讨论。
- **可观测性 / 运维**：slow I/O 根因分析来自内部 telemetry；TRIM 与 physical space 误报是部署后才暴露，说明监控语义曾长期不准。
- **供应商锁定**：PolarCSD 定制 FTL 与 gzip 固化使方案难迁移到商用 CSD 或纯软件盘。
- **尾延迟**：per-page log 在高并发 RO 下收益消失；论文未讨论压缩选型在 CPU 尖峰时的滞后效应。
- **安全与租户隔离**：论文未讨论。

## 局限与 Future Work

- **局限 1**：硬件压缩算法与 4 KB 输入在制造后不可改，未来更高压缩比可能依赖软件层或新代 ASIC，升级周期长。
- **局限 2**：C1 时期 host FTL 迫使关闭软件压缩，说明 co-design 对硬件代际敏感，早期部署无法享受完整双层收益。
- **局限 3**：与表级字典、列式编码、专用 page layout 等 DB 语义压缩正交，尚未叠加，压缩比上限可能未触顶。
- **Future work 1**：对 chunk 迁移与 compression-aware scheduling 做 tail latency / 迁移带宽的 production trace 测量，量化调度参数 \(c_l, c_h\) 的 SLO 敏感性。
- **Future work 2**：在 PolarCSD3.0 或可变硬件算法下重测「zstd 优势被吃掉」是否仍成立，决定 Opt#2 是否仍需页级双试压。
- **Future work 3**：论文提及 EC 尚不适合 redo、dedup 在 record-level DB 中收益有限——可评估 EC 用于冷 chunk + 双层压缩的组合成本模型。

## 相关

- **相关概念**：[[FTL]]、[[NVMe]]、[[LSM-Tree]]、[[Buffer-Pool]]、[[Disaggregation]]、[[Tail-Latency]]、[[Garbage-Collection]]
- **同类系统**：[[PolarDB]]、[[AWS-Aurora]]、InnoDB table/page compression、[[MyRocks]]、[[Pangu]]、Intel QAT、open-channel SSD / [[CSD]] 相关工作（FAST'20 PolarDB meets computational storage、FAST'22 B+-tree vs LSM on transparent compression）
- **同会议**：[[FAST-2026]]
- **对比**：存储层透明压缩（PolarStore）vs 计算层压缩（InnoDB/MyRocks）——后者把 CPU 开销计入用户实例账单
