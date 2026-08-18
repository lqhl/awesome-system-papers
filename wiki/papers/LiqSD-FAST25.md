---
type: paper
name: LiqSD
full_title: "Liquid-State Drive: A Case for DNA Block Device for Enormous Data"
authors: [Jiahao Zhou, Mingkai Dong, Fei Wang, Jingyao Zeng, Lei Zhao, Chunhai Fan, Haibo Chen]
venue: FAST
year: 2025
tags: [dna-storage, block-device, metadata, garbage-collection, emerging-storage, area/storage-systems]
source_pdf: "[[fast2025-zhou-jiahao.pdf]]"
source_md: "[[fast2025-zhou-jiahao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# LiqSD：面向海量数据的 DNA 块设备（FAST 2025）

> **原题**：Liquid-State Drive: A Case for DNA Block Device for Enormous Data

> **一句话总结**：DNA 的 strand 写、strand collection 读和 spot 擦除粒度相差多个数量级，使传统原地更新和单层映射表无法扩展到 EB 容量；LiqSD 用 SSD 中的 GB 级 L0 DTL、DNA 中的 PB 级 L1 DTL、共生元数据和延迟失效构造块接口，在模拟器与真实 trace 上把写放大最多降低 2,927 倍、读放大最多降低 7 倍，但当前一次 4 KiB 读写仍分别约需 49/74 分钟。

## 问题与动机

DNA 具有极高密度和世纪级保存寿命，但现有工作多暴露 key-value 接口，并把 key 和映射留在传统介质中。块设备接口更简单，也能直接承载文件系统和数据库；真正困难的是 DNA 不能原地修改，且写、读、擦除分别以 strand、strand collection（SC）和 spot 为粒度。

对 EB 级设备，4 KiB LBA→PBA 映射会形成 PB 级 DNA Translation Layer（DTL）。把它全部放 SSD 不现实，放 DNA 又会让每次更新触发昂贵读改写；out-of-place update 还需要同样巨大的有效位图和反向映射支持 GC。

## 关键观察 / 隐含假设

- **观察 1**：DNA 的最小写粒度远小于读和擦除粒度，适合追加 patch，不适合覆盖。论文据此让 L1 DTL entry 以 strand patch 追加，并把同一区间的 patch 放进一个 SC（§3.1、§4.1）。
  - **依赖假设**：未来 DNA 硬件仍保留强烈的读写粒度不对称；若细粒度原地修改成熟，双层 DTL 的必要性会下降。
- **观察 2**：EB 数据对应的 L1 DTL 是 PB 级，但用 SC 粒度分段后，索引这些 section 的 L0 DTL 只有 GB 级，可放在 [[NVMe|SSD]]（§4.1）。
  - **可能失效场景**：容量、block size、SC 容量或寻址格式改变会重新决定元数据层级。
- **观察 3**：每次更新立即查旧 PBA 并写 invalid strand，会把 DNA read 放进 write critical path；延迟到以后读取该 L1 section 时批量失效更便宜（§4.3）。
  - **依赖假设**：cache 与 [[Garbage-Collection|GC]] 能正确容忍 valid/obsolete 暂时不一致。
- **假设 1**：读写放大比当前绝对延迟更能代表未来 DNA 技术。证据强度中等；它避免绑定某代设备，却掩盖了当前 49/74 分钟级操作仍不适合在线块设备。

## 核心方法

**双层 DTL**把数据层、PB 级 L1 DTL 和 GB 级 L0 DTL 分开。L1 以 log-structured patch 更新 LBA→PBA；L0 记录 logical section→physical section，常驻 SSD。写新 block 时追加数据和 patch，不读旧映射。

**共生元数据（symbiotic metadata）**把反向映射塞进 block 最后一条 strand 的 OOB，把有效位编码为保留的 invalid strand。GC 读取数据时顺带得到 LBA 和有效性，避免访问独立 PB 级元数据结构。

**延迟失效（delayed invalidation）**让旧 block 先进入 obsolete 状态，等对应 L1 section 被读取时再合并 patch 并补 invalid strand。定制 GC 用带 old/new PBA 的 GC patch 防止 obsolete block 被错误复活；cache 用 timestamp 验证候选 block 是否仍为最新版本。

## 设计取舍

- **取舍 1**：以 3.1% 额外空间和复杂的四状态 block/三状态 section 管理，换取几乎消除 write critical path 上的 DNA read。
- **取舍 2**：把少量频繁更新的元数据与 cache 放 SSD，换取 DNA 容量的可用性；这不是纯 DNA 设备，而是 DNA+SSD 分层系统。
- **边界条件**：论文基于模拟器统计合成/测序数据量，没有真实 EB 设备；GC 在高 valid-block 比例时可能无法回收，MSR Proj 在写入量达到容量 0.8 时耗尽空间。

## 实验与结果

- 双路 Xeon Gold 5317、188 GB DRAM、7 TB NVMe 上运行 DNA 模拟器，使用 Alibaba Cloud、MSR Cambridge 和 ECMWF/ext4 trace（§6.1）。
- microbenchmark 中 No-DTL random update 的 write amplification 达 12,276,148，LiqSD 略高于 1；随机读时 LiqSD read amplification 约 6,200（图 10）。
- 真实 trace 中，LiqSD 相比 baseline 写成本最多降低 2,927 倍、读成本最多降低 7 倍；论文结论报告 3.1% 空间开销（图 12、§7）。
- eager invalidation 的 read amplification 比 delayed invalidation 高 7–15,194 倍，因为每次写都需先读 L1 DTL（图 13）。
- 绝对时间估算仍很高：当前技术下平均 block read 约 49 分钟、write 约 74 分钟；99.3% 以上 L1 DTL read cache hit 才避免额外串行 DNA 访问（§6.6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 双层 DTL 能把频繁更新的根索引降到 SSD 可容纳规模 | §4.1：1 EB、4 KiB block 下轻量元数据约 5 GiB | 依赖论文的 DNA chip/SC 参数 | 中 |
| 延迟失效显著降低更新读成本 | 图 13：eager read amplification 高 7–15,194 倍 | 模拟器和三类 trace | 强 |
| LiqSD 已接近实用在线块设备 | §6.6：单 block 读写仍约 49/74 分钟 | 当前 DNA 技术 | 弱 |

## 批判性分析

### 论证链条

论文从介质粒度不对称推导 patch-based DTL，再从元数据规模推导两级索引，逻辑完整。最强贡献是把“DNA storage 能不能有块接口”具体化为 metadata/GC/crash consistency 问题；但标题中的 drive 更接近未来架构研究，而非当前可部署设备。

### 假设压力测试

若 workload 频繁随机读、L1 section cache hit 低，读取映射和数据需要两个串行 DNA read；若 valid data 长期接近容量，log-structured update 和 GC 也无法创造空间。论文的真实 trace 只验证访问分布，不验证真实生化错误、退化、污染和设备并发。

### 实验可信度

读写放大、GC 和 delayed-invalidation ablation 能支持架构比较；但所有数据访问均为模拟计数，SSD latency 被视为相对 DNA 可忽略，实际端到端设备、能耗、美元成本和生化失败恢复没有测量。

### 系统性缺陷

LiqSD 的 crash consistency 依赖 SSD 中的持久化元数据和写入顺序；DNA 与 SSD 生命周期、备份和替换策略论文仅讨论原则。当前操作时延决定它只适合冷数据或 archival workload，不能泛化为普通 SSD/HDD 替代。

## 局限与后续工作

- **局限 1**：没有真实 DNA block-device prototype，生化过程仅由参数化模拟器表示。
- **局限 2**：容量压力高且数据大多有效时 GC 无法回收；缺少 over-provisioning 与 admission policy 的系统分析。
- **后续工作 1**：在可重复的小规模 DNA 实验台上测量 patch 合并、invalid strand 和 GC 的端到端错误率、成本与恢复时间。
- **后续工作 2**：按 hot/cold、read-only/read-write 分类选择 block size、cache 和 invalidation policy，并报告 trace 驱动的成本曲线。

## 相关

- **相关概念**：[[NVMe]]、DNA storage、out-of-place update、garbage collection
- **同类系统**：[[RASK-FAST26]]、[[SysSpec-FAST26]]
