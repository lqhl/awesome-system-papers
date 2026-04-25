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
---

# HotRAP: Hot Record Retention and Promotion for LSM-trees with Tiered Storage (ATC 2025)

> **一句话总结**：在 RocksDB 上加一个住在 fast disk 的小型 LSM-tree (RALT) 来 record-level 追踪 key 热度 + 双通道（hotness-aware compaction & promotion-by-flush）把热记录从 slow disk 拉到 fast disk，read-write balanced YCSB 比次优基线快 1.6×、Twitter 真实负载快 1.5×。

## 问题

LSM-tree 上 tiered storage 有两条路：tiering（上层在 fast disk、下层在 slow disk）写好但 read-hot 数据无法从下层提升；caching（整树在 slow disk + fast disk 缓存）读好但 compaction 全在 slow disk 拖累写。LogStore/MirrorKV 的 SSTable/block 级别 promotion 粒度太粗（一个 SSTable 含大量冷数据被一并搬上去），PrismDB 用 hash table 跟踪 key 又吃内存，且都只能借助 compaction 缓慢提升、跟不上热度时间窗。

## 核心方法

HotRAP 沿用 tiering 设计但加两件武器，基于 RocksDB（leveling compaction）：

- **RALT (Recent Access Lookup Table)**：一个住在 FD 的小 LSM-tree，仅存 (key, value-length, score-metadata)（不存 value）。支持插入访问记录、bloom-filter 查 hotness、按 range 扫描热 key、计算 range 内 hot set size。Memory 仅 0.056% data size、disk 1%。
- **Auto-tuning size limits**：用 counter c + tag t 区分 stable/unstable，每访问 R 字节衰减一次 counter；hot set size limit ≤ 0.85× FD last level，physical size limit 自适应；超限按 score 从低到高 evict。
- **Hotness-aware compaction**：FD→SD compaction 时，从 mutable promotion buffer 提取范围内记录加入输入；与 RALT iterator sort-merge 决定哪些写回 FD 哪些下沉 SD（retain + promote 同时完成）。
- **Promotion by flush**：read-heavy 时 mutable promotion buffer 满了后转 immutable；Checker 后台线程查 RALT 挑出 hot 记录、查 FD 各级 bloom filter 排除已有 newer version、把剩下的打成 immutable MemTable flush 到 L0。
- **Concurrency control**：通过 superversion + DB mutex + updated-key marking 保证 promotion 不会 shadow 更新版本。

具体 cost-benefit score 调整、写放大分析见 [[atc2025-qiu]]。

## 关键结果

- 5.2× over 次优 tiering baseline（read-only YCSB hotspot-5%）
- 2.1× over caching baseline（write-heavy）
- 1.6× over 两类 baseline（read-write balanced）
- 1.5× on Twitter production traces（cluster 17 最高 5.35×）
- uniform workload 下仅比 RocksDB-tiering 慢 4%（低 overhead）
- AWS i4i.2xlarge：本地 NVMe SSD (FD) + gp3 (SD)，比例 1:10

## 相关

- **相关概念**：[[LSM-Tree]]、[[Tiered-Storage]]、[[Hot-Cold-Separation]]、[[Compaction]]、[[KV-Store]]
- **同类系统**：[[RocksDB]]、PrismDB、SAS-Cache、LogStore、MirrorKV、SA-LSM
- **同会议**：[[ATC-2025]]
