---
type: paper
name: RASK
full_title: "\"Range as a Key\" is the Key! Fast and Compact Cloud Block Store Index with RASK"
authors: [Haoru Zhao, Mingkai Dong, Erci Xu, Zhongyu Wang, Haibo Chen]
venue: FAST
year: 2026
tags: [cloud-storage, ebs, indexing, range-key, alibaba-cloud]
source_pdf: "[[fast2026-zhao.pdf]]"
source_md: "[[fast2026-zhao]]"
---

# "Range as a Key" is the Key! Fast and Compact Cloud Block Store Index with RASK (FAST 2026)

> **一句话总结**：[[Alibaba-Cloud]] EBS 索引吃掉节点 ~57.1% 内存、最差集群因索引内存不够浪费 ~35% 物理存储；trace 分析显示 65–81.5% 写请求其实是连续的 range（CW），RASK 用 [[ART]] + log-structured leaf 把 range 直接做 key，在四份生产 trace 上内存最多省 **98.9%**、吞吐最多 **31.0×**、尾延迟降 **48.2–97.4%**，还把 [[RocksDB]] 集成后吞吐推到原 skiplist 的 **6.46×**。

## 问题

云块存储（AWS EBS、Alibaba Cloud EBS、Azure Managed Disks、GCP Persistent Disk）必须把 LBA→DataFile 索引 fully in-memory 才能保证 I/O 延迟。随着用户增长 + QLC SSD 容量爆炸，索引成为节点 DRAM 主消费者：Alibaba Cloud EBS-index 占 ~57.1% 内存（LBAIndex 17.2% + CompressIndex 39.9%），最坏 ~10% 集群因内存不够无法索引导致 ~35% 物理存储被废。

加内存贵且不可持续。换更省的 [[ART]]/[[B-Tree]]/PGM-Index 也没用——LBAIndex 已比这些 SOTA 还省。Trace 揭示真正机会：**写请求倾向于 range** —— 65–81.5% 写属于"连续写序列"（Consecutive Write, CW），背后原因是 FS journaling、Redis server log、MySQL InnoDB log 等天然连续写。Meta 的 trace 里 90.3% 写跨过 4 块。但既有 range-aware 索引（interval tree、HINT、segment tree）只为"intersection 查询"设计，不会自动剔除被覆盖的旧 range；把 B-tree 改成 eager/lazy range 处理则要么写慢要么读慢。

## 核心方法

RASK = [[ART]] 内部节点 + log-structured leaf（叶子全局有序、内部 append-only），叶子条目是 range 而非 block。两大挑战：

**Challenge-1: Range Overlap**。新 range 可能 cover/部分重叠老 range。RASK 三招：
- **Log-structured leaf**：写直接 append，GC 推迟到 leaf 满时批量回收 fully covered ranges。Leaf 既是 GC 单元又限制 memory 上限。
- **Two-stage GC**：Stage-1 仅删除"和新 range 同 left bound"的覆盖项（实测覆盖 73.8% 可回收条目），快速释放空间让写恢复；Stage-2 慢路径彻底扫剩余覆盖项。
- **Ablation-based search**：从 leaf 末尾反向扫，每个 range 只覆盖 target 的"未找到部分"，自然规避旧版本数据，避免误读 outdated value。

**Challenge-2: Range Fragmentation**。leaf 容量有限导致 user range 跨多 leaf。
- **Range-conscious split**：选 split point 时既平衡两侧 entry 数，也最小化 range 跨界条数（split point 不能落在任何 range 内）。
- **Workload-aware merge & resplit**：split 不能预知未来；当新 range 频繁跨 leaf 时动态合并相邻 leaf 再按新工作负载 resplit，让 leaf 的 range space 跟随实际访问模式。

**配套优化（§3）**：在 EBS 写路径用 SegmentCache（128 块）做 I/O compaction，把多个写合并成 CW 后再发给 LBAIndex，使写计数降 58.4–77%；compress unit (CU) 改为按 CW 自适应（>4 块按 CW 压、<4 块沿用 4-block CU），CU 索引计数降 69.1–91.1%；trace 显示 95.7% 读对 CU 起点 4 块以内对齐，扩大 CU 不会显著放大读。

## 关键结果

- 相比 10 个 SOTA 索引（含 LBAIndex / B-tree / [[ART]] / PGM-Index / interval tree / segment tree），内存最多 **45.3–98.9%** 节省。
- 吞吐 **1.37–32.0×**；尾延迟降 **48.2–97.4%**。
- 集成进 [[RocksDB]] 替换 skiplist 后 KV 吞吐 **6.46×** 提升，验证泛化到 DFS metadata service 等场景。
- Trace 公开：Alibaba Cloud EBS traces 已开源到 Tianchi。RASK 代码开源在上海交大 IPADS 仓库。

## 相关

- **相关概念**：[[ART]]、[[B-Tree]]、[[LSM-Tree]]、[[Range-Index]]、[[Cloud-Block-Storage]]
- **同类系统**：interval tree、HINT、segment tree、PGM-Index、LBAIndex（Alibaba Cloud EBS 原索引）、[[RocksDB]]
- **应用**：[[Alibaba-Cloud]] EBS、Tencent EBS、Google/Meta 块存储、flash cache、DFS metadata service
- **同会议**：[[FAST-2026]]
