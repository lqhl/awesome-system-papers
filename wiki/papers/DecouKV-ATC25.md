---
type: paper
name: DecouKV
full_title: "Mitigating Resource Usage Dependency in Sorting-based KV Stores on Hybrid Storage Devices via Operation Decoupling"
authors: [Qingyang Zhang, Yongkun Li, Yubiao Pan, Haoting Tang, Yinlong Xu]
venue: ATC
year: 2025
tags: [lsm-tree, kv-store, hybrid-storage, persistent-memory, compaction, write-stall]
source_pdf: "[[atc2025-zhang-qingyang.pdf]]"
source_md: "[[atc2025-zhang-qingyang]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# DecouKV：通过操作解耦减轻混合存储设备上基于排序的 KV 存储的资源使用依赖性（ATC 2025）

> **原题**：Mitigating Resource Usage Dependency in Sorting-based KV Stores on Hybrid Storage Devices via Operation Decoupling

> **一句话总结**：基于「flush/compaction 内 CPU 耗在 index sort、I/O 耗在 data 读写，且 hybrid 盘上快慢设备瓶颈交替」的测量，DecouKV 把 index（DRAM IndexTable）与 data（fast device 上 AOF）解耦成 CPU-bound merge 与 I/O-bound append/flush，配合 IMQ/DFQ 队列自调与 elastic high-level capacity，在 PM+SATA 混合部署下写吞吐 2.3–4.9× 于 [[RocksDB]]，P99 尾延迟降 74.3%–91.4%，CPU 利用率提升 25.4%–32.3%。

## 问题与动机

[[LSM-Tree]] KV 存储（[[RocksDB]]、LevelDB、Cassandra 等）依赖 flush 与 [[Compaction]] 等 sorting-based 操作把内存中的 KV pair 有序落盘。随着 NVMe SSD、[[Persistent-Memory]]（PM）等 fast device 普及，业界广泛采用 **hybrid storage**：热数据放 fast device、冷数据放 SATA SSD/HDD，以有限昂贵容量换成本与性能平衡（NoveLSM、MatrixKV、SpanDB、PrismDB 等）。

作者 claim 的根本痛点不是「写放大」本身，而是 sorting 操作引发的 **operation coupling**，进而导致 **resource usage dependency**——系统无法按当前空闲资源类型主动调度后台任务：

1. **操作内资源交织**：flush 里序列化（Bloom filter、index block）吃 CPU，数据写吃 I/O；compaction 里 merge sort 吃 CPU，读写吃 I/O。单任务内 CPU/I/O 绑在一起，无法利用「CPU 闲而 I/O 忙」或反之的碎片时间。
2. **操作间依赖链**：固定 level capacity 阈值使 $L_{i-1}\to L_i$ sorting 可能连锁触发 $L_i\to L_{i+1}$，系统只能被动响应，无法在资源空闲时选择「现在该 sort 哪一层」。
3. **操作间争用**：高写负载下多路 sorting 并发，同类资源密集型任务互相抢 CPU 或带宽，加剧 [[Write-Stall]]。

在 hybrid 部署上问题更严重：论文用 RocksDB 测量发现 fast device（PM/NVMe）上 compaction **>60%** 时间在 CPU，slow device（SATA/HDD）上 **<30%** 在 CPU、大量 I/O wait；L0/L1 在 PM、高层在 SATA 时，1500s 写负载下 CPU 与 disk 利用率呈 **相反波动**（fast 上 CPU 94%/disk 48%，slow 上 disk 88%/CPU 21%），平均利用率低、写停顿显著。

现有两类缓解策略均不够根本：**固定差异化数据管理**（MatrixKV、PrismDB 等）把特定 level 绑在 PM，减轻部分交织但仍保留 level 间依赖，且静态布局与动态资源消耗错位；**表层 scheduling**（ADOC、SILK 等）调频率/线程/批次，未识别 sorting 的 CPU vs I/O 资源本质，同类资源任务扎堆调度反而加剧瓶颈（ADOC 在 hybrid 上波动比 RocksDB 更大）。

## 关键观察 / 隐含假设

- **观察 1**：在 sorting 操作内，CPU 开销主要来自 index/metadata 处理，I/O 开销主要来自 data 读写——二者可在数据结构层面分离。
  - **依赖假设**：fast device 上无序 data 的随机读性能足够好，去掉 Bloom filter 与有序 [[SSTable]] 布局不会显著伤害读路径；index 仅存 key + (file, offset) 足以定位 value。
  - **可能失效场景**：value 极大时 I/O 主导，解耦收益下降（论文 §4.5：16KB value 时优势收窄）；fast device 随机读劣于顺序读的环境（低端 NVMe、高并发随机读）可能放大 AOF 无序访问代价；极短 value（256B）时 CPU 需求上升，单资源类型瓶颈削弱调度空间。

- **观察 2**：hybrid 盘上不同设备的 sorting 瓶颈类型不同（fast→CPU-bound，slow→I/O-bound），且随 level 迁移 **交替出现**，造成时间维度上的资源碎片。
  - **依赖假设**：部署遵循常见 tiering——低层/WAL 在 fast device、高层在 slow device；fast device 容量约为 dataset 的 ~10%；写密集负载能周期性触发两层设备上的后台任务。
  - **可能失效场景**：全 NVMe 或 fast device 占比很高时瓶颈可能趋同；读密集时后台 idle，交替瓶颈观察不适用；多租户共享 hybrid 池时设备争用会扭曲单 store 内的 CPU/I/O 画像。

- **观察 3**：level 间固定 amplification factor（典型 10×）把 sorting 变成被动连锁反应；临时放宽高层 capacity 可在不牺牲正确性的前提下打断依赖链，且 decoupled 设计能控制由此带来的 write amplification 与读开销。
  - **依赖假设**：高层数据更冷、读访问少；flush 到 $HL_0$ 的文件大小可通过 DFTS 调节，从而约束相邻 level 大小比；index merge 能减少 duplicate key 带来的额外写放大。
  - **可能失效场景**：读密集且高层仍被频繁扫描时，elastic capacity 放大 level 会提高读成本；长期放松阈值可能导致 level 膨胀与空间回收延迟，论文对数月 aging 未测。

- **假设 1**：IMQ/DFQ 队列长度 + Score$_{IM}$/Score$_{DF}$ 能可靠反映 CPU/I/O 压力，并驱动 IMTN、DFTS、high-level capacity 的 auto-tuning。
  - **证据强度**：**中**——load 与 YCSB-A 上 DFTS/IMTN 调整轨迹与瓶颈判断一致（Figure 16），但阈值（Score$_{IM}$>1.5、Score$_{DF}$>3）来自实验网格搜索，缺少跨硬件/负载的 sensitivity 系统化报告。

- **假设 2**：高层仍保留传统 leveled compaction + SSTable（未完全 decouple），因为 slow device 随机读差且 DRAM 不足以承载全部 index decoupling。
  - **证据强度**：**强**——设计显式分层，ablation 显示 elastic HL 对 load 贡献大于 YCSB-A；但 hybrid 收益的上界因此部分仍受 slow device compaction 制约。

## 核心方法

DecouKV 在 [[LSM-Tree]] 框架内做 **operation decoupling**，把原 flush/compaction 拆成可独立调度的 CPU 密集与 I/O 密集任务，并用队列反馈闭环调度。

**Index/Data 物理分离**（回应观察 1）：fast device 上用 **Append-Only File（AOF）** 存 KV value（无序）；DRAM 中用 **IndexTable**（可 merge 的 skip list）存 key → (8B file id, 8B offset)。IndexTable 不存 value，同内存可容更多 entry；异步 insert 先记地址再 append，降低 I/O 阻塞前台。省掉 WAL（崩溃时从 AOF 重建 index）与 fast tier 上的 Bloom filter（依赖 fast device 随机读带宽）。

**三类解耦任务**（回应观察 1、2）：
- **Index merge（CPU-intensive）**：两个满 IndexTable 在 DRAM 内 merge skip list，不改 AOF；多线程并行改指针，用 CAS 维护 **Merging Index Set** 保证并发读正确性。
- **Data append（I/O-intensive）**：前台写只追加 AOF。
- **Data flush（I/O-intensive）**：IndexTable 达 DFTS 后顺序扫 index，从 AOF 拉 value，写成 slow device 上有序 [[SSTable]]，再删除旧 IndexTable/AOF。slow tier 仍有序以保随机读性能。

**IMQ / DFQ 队列调度**（回应观察 2、假设 1）：小 IndexTable 入 **Index Merge Queue（IMQ）**，大 IndexTable 入 **Data Flush Queue（DFQ）**。$Score_{IM}=L_{IMQ}/IMTN$ 反映 CPU 压力，$Score_{DF}=L_{DFQ}$ 反映 I/O 压力。CPU-bound 时增大 IMTN、减小 DFTS（把任务从 flush 推回 merge）；I/O-bound 时反向调节；双队列拥堵则触发 write stall；60s 双空闲则同时收紧参数以提升数据有序度。参数步进与 RocksDB 默认量级对齐（IMTN 默认 2，DFTS 默认 32MB）。

**Elastic capacity high levels**（回应观察 3）：slow device 高层保留 leveled compaction，但 **放宽 level 放大因子**，在 I/O 拥堵时推迟 $HL_{i+1}$ compaction，转而调度 CPU 侧 index merge，打断连锁触发。通过 DFTS 控制写入 $HL_0$ 的 chunk 大小，抑制 write amplification；热数据留 fast tier 降低大 level 读惩罚。

实现开源（GitHub: QingyangZ/DecouKV），基于 RocksDB 魔改，对比 MatrixKV、ADOC、PrismDB、SplitDB。架构与恢复细节见 [[atc2025-zhang-qingyang]]。

## 设计取舍

- **Fast tier 无序 AOF vs 传统 SSTable**：换取 flush 路径纯 append、去掉 sort CPU；代价是依赖 fast device 随机读，去掉 Bloom 后在慢速或拥塞 fast device 上读性能可能回落。
- **Index 全 DRAM vs PM/SSD 持久 index**：merge 零 I/O、调度灵活；代价是 IndexTable + TableCache 内存高于 RocksDB MemTable（YCSB-A 峰值约多 23% IndexTable 内存，总内存与 MatrixKV/ADOC 相近），大规模 keyspace 下 DRAM 压力未充分展开。
- **高层保留耦合 compaction vs 全栈 decouple**：slow device 随机读与内存限制迫使高层仍用传统 sort；收益是工程可落地，代价是 hybrid 收益下界仍受 slow tier compaction 牵制。
- **Auto-tuning 启发式 vs workload-aware 离线模型**：无需 trace 训练、部署简单；代价是阈值与步进（±2 IMTN、×2 DFTS）可能对突发负载反应滞后，且双资源同时瓶颈时只能 stall。
- **边界条件**：写密集、PM/NVMe+SATA hybrid、value ~1–4KB、≥4 CPU core 时最优雅；纯读、skew 极高（PrismDB in-place 优势）、value 极端大小、CPU 极少（2 core）或极多（16 core 后 I/O 饱和）时优势收窄或消失。

## 实验与结果

**Setup**：2×20-core Xeon、128GB DRAM；128GB Optane DCPMM + NVMe 作 fast device，960GB SATA SSD 作 slow device；dataset 默认 100GB，fast tier 配额 10%；4 核 + 4 compaction 线程；RocksDB v9.3.0。

- **资源利用率（insert/update，1500s）**：vs RocksDB/MatrixKV/ADOC，insert 平均 CPU 利用率 +32.3%/+25.4%/+27.3%，update +47.9%/+36.9%/+39.4%；CPU 波动幅度显著缩小；disk 利用率 insert +17.6%–31.6%，update +8.0%–19.9%。
- **微基准吞吐（Figure 13）**：vs RocksDB insert/update **4.3×/4.6×**；read/scan **1.2×/1.5×**；vs MatrixKV insert **1.6×**、update **2.2×**；vs ADOC insert **2.2×**、update **2.1×**。
- **延迟**：insert 平均延迟 vs RocksDB **-76%**；P90 insert **1.579ms**（RocksDB 9.454ms）；P99 insert **3.227ms**（RocksDB 37.557ms），降幅 **74.3%–91.4%**；update P99 优势较弱（14.48ms vs ADOC 21.075ms）。
- **YCSB（100M ops，1KB KV）**：写密集 load/A/F vs RocksDB **2.3–4.9×**；读密集 B/C/D/E uniform **1.2–2.3×**、zipfian **1.2–1.9×**；高 skew zipfian 写密集时 PrismDB 可占优，DecouKV 仍整体较强。
- **Ablation（DecouKV-D / -DS / full）**：decoupling 单独已大幅提升；scheduling 对 pure load 贡献更大；elastic HL 对 load 额外有益。
- **扩展**：500GB dataset load **5.2×** RocksDB；Nutanix 生产 trace（57% update）**1.3–2.0×**；NVMe+SATA 替代 PM 仍 **1.4–2.4×**；崩溃恢复 10GB **8.76s**（RocksDB 8.12s）。

## 批判性分析

### 论证链条

主链条较闭合：**RocksDB on hybrid 的 CPU/disk 交替波动测量**（Figure 4）→ **operation coupling 三分类解释波动根因** → **index/data 分离 + 三类任务 + 队列反馈** 针对性打断交织与争用 → **资源利用率上升与写吞吐/尾延迟大幅改善**（Figure 11–13、Table 1）→ **ablation 分解 decoupling / scheduling / elastic HL 贡献**（Figure 15–16）。

较强证据是「瓶颈交替」与「解耦后 CPU/I/O 可交叉填充」的对应关系，以及 DecouKV-D 单独已显著优于 RocksDB，说明 decoupling 本身而非仅调参在起作用。

薄弱跳步在于：**从单机 100–500GB 实验外推到 general production KV**：实验固定 10% fast tier、四核后台、direct I/O；真实服务可能有更大 block cache、更多 tenant、不同 value size 分布与 PM 退役后的 CXL SSD 拓扑，论文仅部分覆盖（NVMe 替换 PM、Nutanix trace 单条）。

### 假设压力测试

- **Workload**：写密集收益最大；YCSB zipfian 写场景 PrismDB slab in-place 可赢，说明 **热 key 高度集中且可驻留 fast tier in-place** 时 decoupling 优势不唯一；scan-heavy 仅 modest gain。
- **Value size**：1KB/4KB 最优，16KB（I/O 主导）与 256B（CPU 主导）时收益下降，ADOC 在极端点仍具竞争力——**论文已用 Figure 18 证明**，说明解耦调度需要两类资源都不过度失衡。
- **CPU 规模**：2 core 时优势有限，16 core 后 I/O 饱和——解耦旨在「填满碎片」，资源过少或过多都会钝化调度价值。
- **Fast device 演进**：实验重度依赖 Optane PM（已停产）；NVMe 替换后仍有收益但幅度变小，且未测 CXL 扩展内存作 index 载体、或多 socket NUMA 下 IndexTable 局部性。

### 实验可信度

- **Benchmark 代表性**：微基准 + YCSB + Nutanix trace 覆盖较广，但缺少 Meta/Google 级长期 mixed workload、故障注入下 tail latency、多实例共盘干扰。
- **Baseline 强度**：RocksDB/MatrixKV/ADOC/PrismDB/SplitDB 选取合理；MatrixKV/ADOC 在 pure load 上已较强，DecouKV 在 load 上仅 **1.4–1.6×**，主要碾压体现在 read-write mixed 与 update-heavy。
- **Ablation**：D / DS / full 三级有用，但缺少「仅 elastic HL」「仅队列无 decouple」（后者理论上不可行）等更细粒度开关；IMTN/DFTS 最优阈值敏感性仅部分展示。
- **Metric 覆盖**：吞吐、平均/尾延迟、CPU/disk 利用率较全；**write amplification、空间放大、compaction 次数、foreground isolation、多租户 fairness** 未系统报告；update P99 相对 ADOC 优势不明显，与 Figure 11 残余波动一致。

### 系统性缺陷

- **内存与恢复**：IndexTable 全 DRAM + TableCache 结构使内存 footprint 随 key 数线性增长；大规模 crash 后 AOF 顺序扫重建 index 的时间随 fast tier 容量线性扩展，仅 10GB 点测。
- **正确性/并发**：Merging Index Set + 并行 skip list merge 逻辑复杂，论文以功能测试为主，**未讨论形式化验证或长期并发 stress 下的 rare race**。
- **可观测性/运维**：IMQ/DFQ、动态 IMTN/DFTS、elastic HL 使性能行为比 RocksDB 更难预测；论文未提供 tuning playbook 或 tracing 接口。
- **兼容性与生态**：深度魔改 RocksDB，与现有 compaction filter、column family、tiered compaction 插件、云托管 KV 栈的集成成本未知——**论文未讨论**。
- **尾延迟**：写路径大幅改善，但 update P99 在部分基线下差距收窄；资源碎片未完全消除时仍可能出现 stall（双队列拥堵路径）。

## 局限与后续工作

- **局限 1（论文承认）**：高层 slow device 无法采用与低层相同的 decoupling，hybrid 场景下仍残留部分 operation coupling 与 I/O-bound compaction。
- **局限 2（论文承认）**：高 skew workload 下 PrismDB 等 in-place / slab 策略可优于 DecouKV；SplitDB 在 zipfian 读密集场景表现更好。
- **局限 3（论文承认）**：value size 过大或过小、CPU 过少时收益下降；双资源同时饱和时只能回退 write stall。
- **局限 4（可从实验边界推出）**：Optane PM 硬件已停产，结论向 CXL SSD / 纯 NVMe hybrid 迁移需重新标定队列阈值与 fast tier 容量比例；长期运行下的空间回收、HL 膨胀与 WA 累积未测。
- **Future work 1**：对 slow tier 探索轻量 index/data 部分解耦或 byte-addressable 介质上的零拷贝 merge（借鉴 MioDB、ListDB），减少高层 I/O-bound compaction 对整体的拖累。
- **Future work 2**：在多 tenant、共盘、异构 value size 混合的 production trace 上测量 IMQ/DFQ 调度稳定性，并系统化 IMTN/DFTS/HL capacity 的 sensitivity surface。
- **Future work 3**：补齐 write amplification、foreground QoS、崩溃恢复时间与内存峰值随 dataset scaling 的曲线，验证 elastic HL 是否会在月级 aging 下引入读放大或空间不可控。

## 相关

- **相关概念**：[[LSM-Tree]]、[[Compaction]]、[[Write-Stall]]、[[Persistent-Memory]]、[[Tiered-Storage]]、[[KV-Store]]、[[SSTable]]、[[Write-Amplification]]
- **同类系统**：[[MatrixKV]]、[[ADOC]]、[[PrismDB]]、[[SplitDB]]、SpanDB、NoveLSM、[[WiscKey]]
- **同会议**：[[ATC-2025]]
- **对比**：与 MatrixKV/ADOC 代表「固定差异化管理 / 表层 scheduling」路线形成直接对照；与 [[HotRAP-ATC25]] 同属 ATC'25 hybrid/tiered [[LSM-Tree]] 优化，但 HotRAP 聚焦读热 promotion，DecouKV 聚焦写路径资源解耦
