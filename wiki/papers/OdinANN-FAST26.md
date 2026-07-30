---
type: paper
name: OdinANN
full_title: "OdinANN: Direct Insert for Consistently Stable Performance in Billion-Scale Graph-Based Vector Search"
authors: [Hao Guo, Youyou Lu]
venue: FAST
year: 2026
tags: [vector-search, ann, graph-index, on-disk-index, concurrency]
source_pdf: "[[fast2026-guo.pdf]]"
source_md: "[[fast2026-guo]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# OdinANN：直接插入，在十亿级基于图的向量搜索中保持稳定的性能（FAST 2026）

> **原题**：OdinANN: Direct Insert for Consistently Stable Performance in Billion-Scale Graph-Based Vector Search

> **一句话总结**：在 billion-scale on-disk graph [[ANNS]] 中，buffered insert 的 merge 阶段无法 batch 邻居搜索、却会和前端 search 抢 SSD 带宽（median latency 飙至 1.54×、merge 3% 向量需 125GB 内存）——OdinANN 用 **direct insert** + **GC-free update combining**（2× 磁盘换无 GC 的 out-of-place 合并写）+ **approximate concurrency control**（per-record 快照而非全图原子性），把 search P50 波动压到 1.07×（[[DiskANN]] 2.44×），SIFT1B 上同时达 5000 QPS search + 1100 QPS insert、~3ms 中位延迟，内存峰值仅为 DiskANN 的 29.3%。

## 问题与动机

[[ANNS]] 是 [[RAG]]、多模态检索、推荐的基础设施；十亿级向量无法放进单机内存，on-disk graph index（[[DiskANN]]、[[Starling]] 等）用磁盘存 full graph、内存存 [[Product-Quantization|PQ]] 压缩向量做导航，在成本与性能间取得平衡。但生产系统持续产生新向量，**index rebuild** 在 billion-scale 上要数天，无法保持结果新鲜；因此 [[FreshDiskANN]] 等方案转向 **online index update**。

当前唯一支持更新的 on-disk graph index（[[DiskANN]] / FreshDiskANN）采用 **buffered insert**：新向量先写入 in-memory index，search 同时遍历内存与磁盘两层索引；当内存索引达到阈值（如 on-disk 规模的 6%）触发 **merge**，分两步把更新落盘——(1) in-memory merge：对每条 buffered vector 在 on-disk index 上执行 Algorithm 2 找邻居；(2) 批量 commit 磁盘写。

作者在 100M [[BIGANN]] 上并发 buffered insert + search 的实测揭示 merge 是性能稳定性的根本瓶颈，而非「batch 不够大」能解决的：

1. **Search 延迟剧烈波动**：merge 的 in-memory merge 阶段要对 on-disk index 做大量随机读找邻居，与前端 search 争 SSD 读带宽，median latency 平均升至 **1.54×**。
2. **内存随规模线性爆炸**：merge 6%（600 万）向量时峰值内存超 **32GB**（> on-disk index 55GB 的 50%）；billion-scale 上 merge 仅 3% 就需 **125GB**（in-memory index + 缓冲磁盘 delta）。
3. **Merge 吞吐有硬顶**：增大 batch 只能减少 merge 次数，in-memory merge 吞吐恒定在 ~**3000 QPS**——因为每条 insert 的邻居搜索无法 batch，必须逐条执行。

作者的核心论点是：**direct insert**（每条向量立即写入 on-disk index）能把 insert 成本均匀摊到时间线上，消除 merge 尖峰；且 buffered insert 的 batch 收益本就有限，direct insert 在吞吐上并不先天吃亏。难点在于：(a) 单次 insert 要更新目标向量及其数十到数百个 neighbor record 的 bi-directional edge，in-place 写带来海量随机 SSD 写，log-structured layout 则因 10% 新记录使索引膨胀 12.8×、有效记录仅 7.9% 而需频繁 logical [[Garbage-Collection]]；(b) insert 与 search 若按 operation 级加锁，search path 上的 near-root record 会成为全局锁热点。

## 关键观察 / 隐含假设

- **观察 1：Buffered insert 的性能问题集中在 merge 的 in-memory merge 阶段，而非磁盘 commit 阶段；该阶段与前端 search 共享 on-disk 读带宽，造成可观测的 latency spike**。
  - **依赖假设**：insert 速率在 800–1200 QPS 量级（与 [[SPFresh]] 等 prior work 一致）；search 并发高（论文用 32 线程、目标 ~5000 QPS）；单机 commodity SSD（非 CXL/近数据计算）是部署基线。
  - **可能失效场景**：insert 速率极低时 merge 稀少，buffered insert 的波动问题不明显；若 insert 与 search 分到不同 NVMe 设备或有多副本读路径，带宽争用可能被掩盖；论文未测 multi-tenant 混合 workload。

- **观察 2：Graph index 的 disk record 是固定大小（vector + 最多 R 个 out-neighbor ID），out-of-place 更新后旧 slot 可直接标记为 free 复用，无需 log-structured 的 logical GC**。
  - **依赖假设**：out-degree 全局上限 R 固定（SIFT 用 96、SIFT1B 用 128）；page 内 record 数 n 可配置，默认每 page 留 ⌊n/2⌋ 个空 slot（2× 空间、2× 写放大）；insert 时 search path 上的 page 已被读入，可优先在同 page 合并多条 record update（Rule #2 on-path partial-empty）。
  - **可能失效场景**：DEEP 等更大向量（384B vs 128B）每 page record 更少（5 vs 7），update combining 收益下降（论文 §4.2.2 已观测）；若 insert 热点集中在少数 page，overprovision 空间可能提前耗尽触发 Rule #3 新 page 分配；长期高 delete 率需 merge 回收，与 insert 路径不同。

- **观察 3：Graph ANNS 的 search 和 insert 本质都是 approximate 操作——search 返回 approximate top-k，insert 用 search path 上的 explored set 作为 approximate neighbor set——因此不需要全图 operation 级原子性与隔离，per-record consistent snapshot 足够**。
  - **依赖假设**：近似邻居集的质量损失可被 graph 连通性与后续 insert 弥补；delta pruning（O(R) 替代 O(R²) triangle inequality 检查）在绝大多数情况下不破坏图特性；用户可接受 recall 随在线 insert 缓慢下降（论文观测 PQ pruning 导致 accuracy 随时间下降）。
  - **可能失效场景**：高并发 insert 下 approximate snapshot 可能链接到次优邻居，图质量劣化需更多 search I/O（论文测得相同 recall 下多 ~4.5% disk page access）；对 recall SLO 极严的 production（如金融合规检索）可能不可接受；论文未给出 recall 劣化与 insert 速率的定量 bound。

- **假设 1：2× 磁盘空间换 ~128GB 峰值内存节省是 cost-effective 的（1TB SSD ~$100 < 128GB DRAM ~$200）**。
  - **证据强度**：**中**——有 PCPartPicker 价格趋势引用和 billion-scale 实测（OdinANN 2× disk、DiskANN 多 128GB peak memory），但未计入运维复杂度、FTL 物理 GC 与长期空间碎片。

- **假设 2：Delete 仍可用 buffered delete（仅记 ID），merge delete 的两遍全索引顺序扫描对 frontend search 干扰远小于 merge insert**。
  - **证据强度**：**中**——§4.7 显示 delete merge 期 search 干扰小；但 first pass 为省内存只加载每节点 20 个最近邻居，带来 ~2.5% accuracy 损失（可配置 trade-off）。

## 核心方法

OdinANN 基于 [[DiskANN]] 实现，保留 on-disk adjacent-list graph layout + in-memory PQ navigation，但将 insert 路径从 buffered 改为 **direct**，delete 仍 buffered。三大操作：

**Vector search**（Algorithm 1）：best-first graph traversal，beam width=4。与 DiskANN 不同：(1) **approximate concurrency**——仅在读单条 record 时持 per-record ID-to-location 锁，保证该 record 快照一致，不保证全图同一时刻视图；(2) 含 delete 时用 **dynamic candidate pool**——pool 中最多容纳 l 个「未删除」向量，把 deleted 节点仅当导航跳板不计入结果，避免 top-k 不足。

**Direct insert**（Algorithm 2 + §3.2–3.3）：对目标向量 q 先 search 得 explored set，prune 到 ≤R 个邻居，双向加边。磁盘写路径：

1. **GC-free update combining**（§3.2）：不在原 record 位置 in-place 改，而是写到 page 内预留 free slot（out-of-place）。三条 allocation rule 优先级：全空 page → insert search path 上已缓存的 partial-empty page（<m 条有效 record）→ 分配新 page。旧 slot 标记 invalid 供后续复用，无 logical GC。默认 m=⌊n/2⌋，空间与写放大均为 **2×**。

2. **Approximate concurrency control**（§3.3）：insert 把 search 得到的 neighbor set 视为 approximate snapshot，不做 OCC 式重搜验证。临界区内持 involved records 的 write lock + 待写 pages 的 page write lock；reload 邻居 record 防 update loss，再 out-of-place 写盘。两项优化缩短临界区：
   - **Async disk I/O**：search 阶段把 explored pages 放入 write-back cache，临界区内 reload 走 cache、写只落 cache，后台线程异步刷盘。
   - **Delta neighbor pruning**：默认只检查新 insert 邻居与其余邻居的 triangle inequality（O(R)），仅当无法 prune 时 fallback O(R²) 全对检查。

**Buffered delete + two-pass merge**（§3.4）：delete 只把 ID 记入内存 set（4–8B/vector），search 完成 on-disk 阶段后用全局 RW lock 过滤结果。Merge 触发条件：deleted 比例达阈值（如 10%）或 search 平均 disk I/O 比无 delete 基线高 1.1×。两遍顺序扫描：pass1 加载 deleted 向量邻居 ID（可截断为 20 个省内存）；pass2 流式替换 deleted ID 为邻居 ID、prune 超 R 的 out-degree、写回。Merge 期间 insert 可继续 direct insert（避开正在 merge 的 page）或暂存小 in-memory index。

**Consistency**（§3.5）：merge 时打 index snapshot；两次 merge 间用 journaling 记 delta；journal flush 可滞后于 on-disk insert，通过 rollback 删除 ID 大于 journal 的 record 维护 consistent prefix。每条 record 带 metadata（ID、transaction ID）支持恢复。

## 设计取舍

- **Direct insert vs buffered insert**：换来 search latency **稳定性**（P50 波动 1.07× vs 2.44×）和 **内存大幅下降**（峰值 29.3% of DiskANN），代价是单条 insert latency 更高（~**11.1ms** median vs buffered 的摊销更低感知）和 **2× 磁盘空间**。
- **Approximate isolation vs 强一致**：per-record 快照 + approximate neighbor set 显著降低 near-root 锁争用（P90/P99 search latency 比 DiskANN 低 34.6%/19.5%），代价是 index quality 略降（相同 recall 多 ~4.5% page reads）和理论上的邻居链接次优。
- **2× overprovision vs log-structured**：消除 logical GC 对 search 的停顿，写放大 2× 可控；log-structured 在 10% insert 下索引 12.8× 膨胀且 92% 无效。
- **Buffered delete vs direct delete**：delete merge 干扰小、内存 footprint 低（仅 ID），但 merge 时需两遍全表扫描；first pass 邻居截断省内存但损失 ~2.5% accuracy。
- **边界条件**：图 index 在 **高 insert + 高 search 并发** 的 online 场景最优雅；**超大向量**（DEEP）因每 page record 少，update combining 收益减弱；**双 region / 分布式** 部署未讨论；insert 期间若 SSD 写带宽饱和，direct insert 的均匀摊销假设可能失效。

## 实验与结果

**Setup**：单机 2×28-core Xeon Gold 6330、512GB RAM、Samsung PM9A3 3.84TB SSD；数据集 SIFT100M、DEEP100M、SIFT1B（800M 初始 + 200M insert）；baseline [[DiskANN]]（buffered insert，merge 阈值 6%/3%）和 cluster-based [[SPFresh]]；[[io_uring]] I/O；32 search 线程（SPFresh 8–16）。

- **SIFT100M，再 insert 100M 并发 search**（insert 800–1200 QPS）：OdinANN P50 latency 平均低 DiskANN **13.3%**，波动 **1.07×**（DiskANN **2.44×**）；P90/P99 低 **34.6%/19.5%**；吞吐高 DiskANN **1.15×**、SPFresh **1.99×**；accuracy 为 DiskANN 的 99.1%–100%（in-memory index 空时），始终高于 SPFresh；峰值内存为 DiskANN **29.3%**、SPFresh **86.8%**；每次 search 读 **41** pages（SPFresh **198**）。
- **SIFT1B**：OdinANN median latency 为 DiskANN **85.7%**、SPFresh **62.1%**；同时 **5000 QPS search + 1100 QPS insert**，median ~**3ms**；DiskANN 仍 >200GB 峰值内存且有 P99 spike。
- **Breakdown**（100K insert，27 线程）：Baseline（in-place + 基本 ACC）吞吐极低；+Async I/O latency **80.8%**；+overprovision 吞吐 **5.12×**、latency **27.1%**；+delta prune 再吞吐 **2.59×**、latency **39.7%**；完整 OdinANN **2000 QPS insert、11.1ms** median。
- **Disk space**：最终 200M 向量索引，OdinANN 空间放大 SIFT/DEEP **1.98×/2.29×**（近理论 2×）；为 SPFresh 磁盘占用的 **84.8%/49.7%**。
- **Delete workload**（100M 向量替换）：OdinANN delete merge 对 search 干扰极小；merge 频率可低于 DiskANN（20% vs 6% 阈值）；merge 期内存低于 DiskANN（只加载 20 neighbors/deleted node）。
- **R 参数**：R=96 在 SIFT100M 上平衡 search latency 与 insert 吞吐；R 增大改善 search 但降低 insert 性能。

## 批判性分析

### 论证链条

论文的 observation → design → result 在「**merge 尖峰是 buffered insert 的原罪**」这一主线上较闭合：§2 用 DiskANN 时间线定量展示 bandwidth interference、内存线性增长、in-memory merge 吞吐瓶颈三条证据；direct insert 作为对策逻辑直接；GC-free combining 回应 challenge 1 的 in-place vs LSM 两难；approximate CC 回应 challenge 2 的锁争用。§4.2–4.3 的 latency CDF、吞吐、内存与 §4.4 的逐步消融支撑各组件贡献。

薄弱环节在于把 **单机 SSD 实验**外推为「billion-scale production 稳定」：SIFT1B 仍在单节点完成，未测多副本、分片、网络盘；「5000 QPS + 1100 QPS 同时」是特定线程与硬件配置下的点，未给出 saturation curve；accuracy 随 insert 时间下降被归因于 PQ pruning，但未严格隔离「approximate CC / delta prune」的独立 recall 损失（§4.5 仅 ~4.5% I/O 增加作为 proxy）。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| Merge 是 buffered insert 主导瓶颈 | DiskANN 100M 实测 timeline + 3000 QPS merge 顶 | 极低 insert 率；独立 insert/search 设备；merge 阈值极小使内存可承受 |
| 2× disk 比 128GB RAM 更划算 | 价格引用 + 1TB 级实测 | 云盘按 IOPS 计费；全闪存集群磁盘本就紧张；长期 delete+insert 后空间碎片 |
| Per-record 近似隔离足够正确 | Algorithm 正确性论述 + 与 DiskANN accuracy 对比 | 极高 insert 并发导致图退化；需强一致 read-your-writes 的 RAG 场景 |
| Delta pruning 不破坏图特性 | Fallback 到全 O(R²) prune；~4.5% extra I/O | 特殊向量分布使 triangle inequality 假设失效；R 更大时 fallback 更频繁 |
| Direct insert ~11ms 可接受 | 引用生产系统 ~10ms indexing latency | 流式 embedding 管道要求 sub-ms ingest；insert 与 search 争写带宽时 tail 恶化 |

### 实验可信度

- **优势**：Baseline 是同一 DiskANN 代码路径改造的 OdinANN，对比公平；覆盖 100M 与 1B 规模、insert+search+delete 三类 workload；消融从 Baseline 逐步叠加清晰。
- **局限**：**仅与 DiskANN、SPFresh 对比**，未含 [[PipeANN]]、[[Starling]] 等更新不支持但 search 更强的 graph index 作 latency 参照；SPFresh 线程数少于 OdinANN（8–16 vs 32），吞吐对比可能偏乐观；accuracy 用 recall@k，未报告 tail latency SLO、insert 失败率；所有实验单节点单 SSD，无故障注入与 recovery 耗时测量。
- **Ablation**：§4.4 在无并发 search 下测 insert，未测 ACC + async I/O 对 **search P99** 的交互；overprovision rule #1/#2/#3 各自贡献未拆分。

### 系统性缺陷

- **尾延迟与隔离**：论文报告 median 稳定性，但 billion-scale 实验中 DiskANN 的 **P99 spike** 仅定性提及；OdinANN 在写回 cache 刷盘、background I/O 线程 backlog 下的 **insert/search P99** 未系统呈现；**多 tenant** 隔离、公平性论文未讨论。
- **故障恢复**：journaling + snapshot rollback 有设计描述，但 **crash recovery 时间**、rollback 期间可用性、部分写 torn page 等边界未实验验证。
- **可观测性**：无讨论如何在 approximate 语义下向用户暴露「结果可能略滞后于最新 insert」；merge delete 进度与 search quality 关联缺少 ops 指标。
- **长期图质量**：accuracy 随时间下降被承认，但 **何时必须 rebuild**、direct insert 下 graph 是否收敛到稳定 recall 未给出；PQ 用于 insert pruning 与 full-precision search 的精度差可能累积。
- **部署成本**：2× disk + ~58–84GB 内存/十亿向量（PQ table + hash tables + location-to-ID）的 TCO 分析有限；未讨论与分布式 [[Milvus]]/[[SPANN]] 等 sharding 方案的关系。

## 局限与后续工作

- **局限 1**（论文自述）：direct insert 单条 latency（~11.1ms）高于 buffered insert 的摊销感知，虽作者认为与生产 ~10ms 目标一致。
- **局限 2**（论文自述）：delta pruning 可能损失 index quality，§4.5 显示相同 recall 需多 ~4.5% disk I/O；更准确的 pruning 算法留作 future work。
- **局限 3**（论文自述）：delete merge 的 first pass 为省内存只加载部分邻居，造成 ~2.5% accuracy 损失；「更准确且省内存的 delete 方法」待优化。
- **局限 4**（实验边界）：仅在单机 commodity SSD 上评估；未覆盖 replication、多节点 query routing、CXL/[[SmartSSD]] 等硬件 offload。
- **Future work 1**：在 **production trace**（insert/delete 速率波动、query 分布漂移）上测量 recall 劣化曲线与 rebuild 触发条件，而非合成 steady-rate workload。
- **Future work 2**：量化 **approximate concurrency** 与 **delta prune** 对 recall 的独立贡献，并探索 stronger validation（轻量 OCC 或 periodic repair）是否能在不恢复 merge 尖峰的前提下收回 ~4.5% I/O。
- **Future work 3**：将 GC-free combining 与 **更大向量 / 更小 page occupancy**（DEEP 场景）结合，研究 adaptive m 或 per-dataset overprovision 策略，避免 Rule #3 新 page 分配退化到接近 in-place 写放大。

## 相关

- **相关概念**：[[ANNS]]、[[Vector-Search]]、[[Graph-Index]]、[[Product-Quantization]]、[[Garbage-Collection]]、[[Concurrency-Control]]、[[RAG]]、[[io_uring]]
- **同类系统**：[[DiskANN]]、[[FreshDiskANN]]、[[SPFresh]]、[[SPANN]]、[[Starling]]、[[HNSW]]、[[Milvus]]
- **同会议**：[[FAST-2026]]
- **对比**：OdinANN vs [[DiskANN]]（direct insert 消除 merge 尖峰）；vs [[SPFresh]]（graph vs cluster 在 updatable billion-scale 上的 latency/accuracy trade-off）
