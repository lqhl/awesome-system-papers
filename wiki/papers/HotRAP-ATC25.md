---
type: paper
name: HotRAP
full_title: "HotRAP: Hot Record Retention and Promotion for LSM-trees with Tiered Storage"
authors: [Jiansheng Qiu, Fangzhou Yuan, Mingyu Gao, Huanchen Zhang]
venue: ATC
year: 2025
tags: [lsm-tree, tiered-storage, kv-store, rocksdb, hot-data]
source_pdf: "[[atc2025-qiu.pdf]]"
source_md: "[[atc2025-qiu]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# HotRAP: Hot Record Retention and Promotion for LSM-trees with Tiered Storage (ATC 2025)

> **一句话总结**：在 tiering 式 [[LSM-Tree]] 上，热读记录会沉在 slow disk 而 compaction 又太慢跟不上热度窗口；HotRAP 用住在 fast disk 的 on-disk 小 LSM-tree（RALT）做 record-level 热度追踪，并以 hotness-aware compaction + promotion-by-flush 双通道及时 promote/retain 热记录，在 read-write balanced YCSB 上比次优基线快 **1.6×**、Twitter 生产 trace 上快 **1.5×**，uniform workload 开销仅 **<4%**。

## 问题与动机

[[LSM-Tree]] 天然分层，与 [[Tiered-Storage]]（小容量 fast disk + 大容量 slow disk）高度契合。现有两条路线各有硬伤：

- **Tiering**：上层在 fast disk (FD)、下层在 slow disk (SD)。append-only 写入天然留在 FD，写性能好；但 read-hot 记录一旦 compaction 下沉 SD，几乎无法回到 FD，读延迟被 SD 主导。
- **Caching**：整棵 LSM-tree 在 SD，FD 作 block/cache。热读可缓存到 FD，但 **所有 compaction 发生在 SD**，写重负载下 SD 成为瓶颈；且双写/一致性维护带来额外开销。

Prior work（LogStore、MirrorKV、PrismDB 等）试图在 tiering 上补读性能，但有三类共性缺陷：① SSTable/block 级 promotion **粒度太粗**，冷记录被 piggyback 到宝贵的 FD；② record-level 热度追踪若放内存，metadata 规模可轻易超过实例内存（Twitter trace 下 1TB 热集需 ~167GB 内存追踪）；③ 只能借 **compaction 被动提升**，read-heavy 时 compaction 稀少，热记录在 SD 积累太久，错过热度时间窗。

作者 claim：不必放弃 tiering 的写优势，也无需全盘接受 caching 的 SD compaction 税——在 tiering 框架内做 **细粒度、及时、可负担** 的热记录 retention/promotion 即可。HotRAP 基于 [[RocksDB]]（leveling compaction）实现这一思路。

## 关键观察 / 隐含假设

- **观察 1**：tiering 与 caching 的读写 trade-off 不是连续谱上的微调，而是 **结构性对立**——tiering 写优读劣、caching 读优写劣；Table 1 的 RO/RW/WH 实验矩阵印证这一二分（§1，§4.2）。
  - **依赖假设**：FD:SD 容量比约 **1:10**、FD 带宽/IOPS 显著优于 SD（AWS Nitro SSD ~83K IOPS vs gp3 ~10K）；point lookup 为主，scan 非热点路径。
  - **可能失效场景**：FD 与 SD 性能差距缩小（同代 NVMe + 高速云盘）；写放大或 retention 使 FD 长期满载，promotion 收益递减。

- **观察 2**：record-level 热度 metadata 不能放内存——按 Twitter trace 小 value 比例估算，1TB FD 热集对应 **>166GB** 内存追踪开销，超过典型 i4i.2xlarge 的 64GB（§2.4，Figure 与文字分析）。
  - **依赖假设**：把 RALT 做成 FD 上的小型 [[LSM-Tree]] 可摊平 metadata 成本；仅存 (key, value-length, score) 使 RALT disk 占用约 **1%** data size、内存约 **0.056%** data size。
  - **可能失效场景**：极小 record + 极高热点比例使 RALT 自身 compaction/eviction I/O 成为 FD 主导负载；key 极长时 physical size 占比上升。

- **观察 3**：仅靠 compaction 提升热数据 **延迟过高**；read-heavy 下 mutable promotion buffer 会膨胀，需要第二条 **promotion-by-flush** 路径把 SD 读到的热记录批量 flush 到 L0（§3.1，Figure 2）。
  - **依赖假设**：64MiB promotion buffer + RALT hotness check 能在不制造大量 tiny SSTable 的前提下，把热记录延迟压到「仍在热度窗口内」；MVCC/superversion 机制可保证 flush 不 shadow 更新版本。
  - **可能失效场景**：热点集合大于 FD hot set size limit（≈0.85× FD last level，实验中 ~7GB）；update-heavy 且读写 key 分布相同（UH workload）时，正常写入已把新版本留在 FD，主动 promotion 几乎无收益。

- **假设 1**：访问偏斜遵循 hotspot / Zipfian 等 **可重复访问** 模式；热 key 在两次访问间被访问的期望数据量低于阈值 R（默认 R = FD size）时可被 RALT 稳定识别。
  - **证据强度**：**强**——hotspot-5% 达 ~95% FD hit rate；dynamic workload 实验显示 hotspot 扩张/收缩/漂移后 hit rate 可恢复（§4.6）；Twitter trace 上 sunk+hot read 比例与 speedup 正相关。

- **假设 2**：工作负载以 **point get** 为主；scan 不记入 RALT、不进入 promotion buffer，与 RocksDB-tiering 行为一致（§5）。
  - **证据强度**：**中**——全部 benchmark 为 YCSB point ops 与 Twitter KV trace；range scan 优化明确标为 future work，论文未评测。

## 核心方法

HotRAP 在标准 tiering LSM-tree 上叠加 **RALT** 与 **promotion buffer**，提供两条热记录驻留 FD 的路径（Figure 1–2）。深度实现见 [[atc2025-qiu]]。

**1. RALT（Recent Access Lookup Table）**

住在 FD 的轻量 [[LSM-Tree]]，记录每次访问的 key、value length、hotness metadata（tick/score），**不存 value**。四类操作：插入访问记录（先 unsorted memory buffer 再 flush）、bloom-filter 查 hotness、range 扫描热 key、range 估算 hot set size。查热用 per-SSTable bloom（14-bit，FPR ≪1%）避免随机读；compaction 时与 data iterator **sort-merge** 决定输出写 FD 还是 SD。

**2. Auto-tuning size limits（Algorithm 1）**

用 counter `c` + tag `t` 区分 stable/unstable key：首次访问 `t=0`，再次命中 `t=1` 变 stable；每访问 R 字节 HotRAP data 全体 counter 衰减。超限按 score（exponential smoothing）evict 10% 记录。hot set size limit ≤ **0.85× FD last level**（控制 retention 写放大）；physical size limit 随 stable/unstable 比例自适应。默认 R=FD size、D_hs=0.05R、c_max=5。

**3. Hotness-aware compaction**

FD→SD（及 SD 内层间）compaction 时：从 mutable promotion buffer 提取 compaction range 内记录加入输入；consult RALT 更新分数；对输出逐条与 RALT iterator merge——热记录 **写回 FD**（retain），SD 中的热记录 **提升到 FD**（promote）。同步调整 RocksDB cost-benefit score：benefit 从 FileSize 改为 (FileSize − HotSize)，HotSize 由 RALT range 查询（允许 ~10% 高估）。

**4. Promotion by flush**

SD 上的 point read 先把 key-value 插入 **mutable promotion buffer**（64MiB，与 target SSTable size 对齐）；满后转 immutable，后台 Checker 线程查 RALT 筛热记录，再查 FD 各级 bloom filter 排除可能有更新版本的 key，打包成 immutable MemTable flush 到 L0。热记录总量 < 半 SSTable 时回退到 mutable buffer 避免 tiny SSTable。并发通过 superversion 快照 + DB mutex + updated-key marking（Figure 4）保证正确性；promotion buffer 插入前还检查 SD SSTable compaction 状态，abort 率 <1%。

**5. 与 block cache 的关系**

promotion buffer 主要服务 SD 读批处理；记录进入 FD 后由 block cache 服务。设计与 Leaper、Range Cache 正交——Table 6 显示 HotRAP 已把热记录推到 FD，再叠 Range Cache 主要降 FD IOPS 而非吞吐。

## 设计取舍

- 取舍 1：on-disk RALT vs in-memory hotness table——用 FD 上小型 LSM-tree + bloom 换 ~95% 内存节省，代价是 RALT 自身 read/write amplification（实验约 30/20）及 compaction 时额外 sort-merge CPU；实测 RALT 仅占 3.7%–11.2% CPU、5.2%–9.7% I/O。
- 取舍 2：retention 写放大 vs 读命中——热记录留 FD 使 FD compaction 次数增约 (1−p)/p（p 为末层冷数据比例）；通过 hot set cap（0.85× last level）限制 SD 额外写放大约 3.3×。uniform workload 几乎不 promote，开销 4%。
- **取舍 3：固定 64MiB promotion buffer**——避免大热点时 buffer 本身成为第二级 cache；大热点依赖 flush 后进 FD + block cache。热点 > max hot set（~7GB）时性能明显下降（§4.6）。
- 取舍 4：tiering 框架 vs caching 双写——保留 tiering 写路径，不接受 caching 的 SD compaction 与双写一致性税；读极致场景仍不及全 FD 上界（RocksDB-FD），Zipfian 下 hit rate 仅 79%。
- **边界条件**：UH（50% read + 50% update，读写同分布）接近 RocksDB-tiering；scan workload 无优化；sequential flooding 类「极稀疏复访」热 key 可能逃过 RALT（§5）。

## 实验与结果

- **Testbed**：AWS EC2 i4i.2xlarge（8 vCPU、64GiB RAM）；FD = 本地 Nitro SSD，SD = gp3；tier 比例 **10:1**（初始 SD 100GB / FD 10GB）；16 线程、direct I/O。
- **Baselines**：RocksDB-tiering、RocksDB-CL（CacheLib）、SAS-Cache、PrismDB、RocksDB-FD（上界）；HotRAP block cache 256MiB，基线多 64MiB 补偿 RALT 内存。
- **YCSB hotspot-5%**：非写重负载下接近 RocksDB-FD，FD hit rate **~95%**；RO 比次优 tiering **5.2×**；RW **1.6×**；WH 比 caching **2.1×**；UH 与 RocksDB-tiering 持平。
- **YCSB uniform**：比 RocksDB-tiering 慢 **4.0%**；no-hotness-check ablation 促进 **204×** 记录、compaction I/O **167.7×**（Table 5）。
- **Zipfian / WH**：与 RocksDB-FD 有 gap（hit 79%、SD compaction 饱和）；仍优于其他 tiering/caching 设计。
- **Tail latency**：hotspot-5% RO 低于除 RocksDB-FD 外所有系统；WH 下因更高吞吐导致更频繁 compaction，**tail 高于 RocksDB-tiering**（Figure 7）。
- **Twitter traces**：相对次优最高 **1.5×**；cluster 17（高 sunk+hot read 比例）达 **5.35×** vs RocksDB-tiering；低 sunk/hot 比例 trace 开销可忽略。
- **Ablation**：禁用 hotness-aware compaction → hit 72% vs 94.8%，promotion 6.5×、compaction 1.36×（Table 4）；禁用 promotion-by-flush → read-heavy hit rate 上升极慢（Figure 13）。
- **Scale**：1.1TB 数据集（1TB SD + 100GB FD）趋势与 110GB 一致（Figure 15）；dynamic hotspot 扩张至 8% 超过 max hot set 时性能降低但仍可适应漂移。

## Critical Analysis

### 论证链条

Observation（tiering 写优读劣 + 粗粒度/内存/延迟三限）→ Design（on-disk RALT + 双通道 promote/retain）→ Implementation（RocksDB + MVCC 正确性）→ Evaluation（YCSB 矩阵 + Twitter + ablation + dynamic + 1.1TB）整体闭合。最薄弱跳步是 **「RALT stable/unstable 算法 ≈ 真实生产偏斜」**：形式化证明省略，主要靠 hotspot/Zipfian/Twitter 间接验证；**near tiering-caching Pareto frontier** 的 claim 在 RO 仍落后 RocksDB-FD、WH tail 变差时被实验部分承认但未系统量化 trade-off 曲面。

### 假设压力测试

- **论文已证明**：常见 skew（hotspot/Zipfian）+ 多种 read-write ratio 下相对 PrismDB/SAS-Cache/RocksDB-tiering/CL 显著更优；RALT 成本可控；dynamic hotspot 可适应；promotion 正确性机制 abort <1%。
- **可能失效**（推断）：
  - **Update-heavy 同分布读写**：新版本已由写入路径留在 FD，HotRAP 机制基本 idle——论文已展示 UH 无收益，但未讨论「读写分布不同但更新极频繁」的中间态。
  - **热点大于 FD budget**：8% hotspot 超过 ~7GB cap 后性能显著下降；生产 FD 占比更小时问题更严重。
  - **Scan / range query 主导**：scan 不追踪热度，range cache 类收益完全缺失；论文明确 future work。
  - **Sequential flooding / 极低复访率热 key**：auto-tuning 依赖「热 key 在 D_hs 窗口内至少两次访问」；极端顺序访问模式需增大 D_hs，论文称 Twitter trace 中不常见但未实测对抗性 trace。
  - **SD 性能提升或 FD 故障**：云盘 IOPS 持续上升会缩小 tiering 价值；论文未讨论 FD 失效降级策略。

### 实验可信度

- **Workload 代表性**：YCSB + Twitter KV trace 覆盖典型偏斜 KV；缺少混合 scan、多租户干扰、写放大长期稳态、跨 region 云存储延迟。
- **Baseline 公平性**：memory budget 对基线 +64MiB block cache 合理；PrismDB/SAS-Cache 改进有限可能反映实现调优而非设计上限，但作者亦指出其 block/SSTable 粒度与慢 promotion 问题。Range Cache 用 RocksDB row cache **模拟**，非原版实现。
- **Ablation**：hotness-aware compaction、promotion-by-flush、hotness-check 三项关键设计均有定量 ablation；缺少 RALT eviction 比例、D_hs/c_max 敏感性、promotion buffer 尺寸的 sweep。
- **Metric**：主报平均吞吐与 P99 get latency（末 10% 窗口）；**未系统覆盖** 写 tail、recovery、crash consistency、长期 disk 空间膨胀（duplicate until merge）、运维复杂度。

### 系统性缺陷

- **写放大与 FD 寿命**：retention 明确增加 FD/SD 写放大（§3.8 有公式），实验 disk usage 170GB vs no-hot-aware 178.6GB 显示 merge 有效，但 **长期 churn workload** 下 FD 磨损与空间回收节奏论文未讨论。
- **尾延迟**：WH 下更高 tail（Figure 7）说明吞吐-promotion-compaction 正反馈可能伤害 SLO；论文归因于更频繁 compaction，未给出 mitigation。
- **隔离与多租户**：单 DB、单 workload；RALT/promotion buffer 与租户 QoS、I/O 隔离无关，论文未讨论。
- **可观测性 / 故障恢复**：RALT 与主 LSM-tree 双结构的一致性、Checker 线程积压、FD 满时 eviction 行为，论文未给 ops 视角；代码开源但 production 集成成本未评估。
- **兼容性**：声称 RALT 可移植为独立库；promotion-by-flush 依赖 [[MVCC]] superversion——对无 MVCC 的 LSM 实现需重做并发协议。

## 局限与 Future Work

- **局限 1**：auto-tuning 假设热 key 随机复访；sequential flooding 需增大 D_hs。scan/range query 与 tiering 行为相同，无加速。
- **局限 2**：hot set 受 FD last level 上限约束；热点规模超过 cap 时只能服务部分热 key。UH workload 下主动 promotion 收益接近零。
- **局限 3**：实验规模限于单节点 AWS i4i、direct I/O；未覆盖 disaggregated storage、副本一致性、多副本读路径。
- **Future work 1**：维护 **promoted range** 元数据，使 range scan 可跳过 SD——需测量 range 热度追踪的 metadata 与 compaction 交互开销。
- **Future work 2**：对 **FD 容量动态变化**（弹性本地盘、CXL 扩展）做 hot set limit 在线重配，量化 promotion 风暴与 hit rate 瞬态跌落。
- **Future work 3**：在 **写尾延迟敏感** workload 上联合调度 compaction 与 promotion-by-flush，验证能否在保持 RW 吞吐增益的同时压住 WH P99。

## 相关

- **相关概念**：[[LSM-Tree]]、[[Tiered-Storage]]、[[Compaction]]、[[KV-Store]]、[[Hot-Cold-Separation]]、[[Bloom-Filter]]、[[MVCC]]
- **同类系统**：[[RocksDB]]、PrismDB、SAS-Cache、LogStore、MirrorKV、SA-LSM、Range Cache、CacheLib
- **同会议**：[[ATC-2025]]
- **对比**：HotRAP 在 tiering 写路径上补 record-level 读优化，相对 caching 设计避免 SD compaction 瓶颈，相对 LogStore/MirrorKV/PrismDB 解决粒度、内存、延迟三限
