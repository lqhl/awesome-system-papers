---
type: paper
name: RubikFS
full_title: "Towards Condensed and Efficient Read-Only File System via Sort-Enhanced Compression"
authors: [Hao Huang, Yifeng Zhang, Yanqi Pan, Wen Xia, Xiangyu Zou, Darong Yang, Jubin Zhong, Hua Liao]
venue: FAST
year: 2026
tags: [file-system, compression, read-only, deduplication, embedded]
source_pdf: "[[fast2026-huang.pdf]]"
source_md: "[[fast2026-huang]]"
---

# Towards Condensed and Efficient Read-Only File System via Sort-Enhanced Compression (FAST 2026)

> **一句话总结**：在只读压缩文件系统（IoT 镜像、Docker 容器）的 block 压缩前先用相似图分簇排序数据 chunk，相似数据被聚到同一 block 内最大化字典压缩收益，并按 hotness 分组减少读放大；相比 EROFS/Squashfs 压缩比提升最多 42.60%、无效读减少 70.70%。

## 问题

只读压缩文件系统（EROFS、Squashfs）按 block（如 1 MB）切片再独立压缩，是空间-性能的折中。但作者发现两个问题：
1. **数据混合**：bitstream 切块后相似数据被分到不同 block，字典压缩无法跨 block 找重复，于是和 Direct（整镜像不切块直接压缩）有显著差距。
2. **读放大**：大 block 把冷热数据混在一起，嵌入式设备内存有限被频繁 evict，重读代价高。

直觉的「先排序再切块」在去重备份场景已有 Finesse/Odess/Palantir，但它们只能识别高相似 chunk、且排序粒度与只读 FS 镜像构建不匹配。

## 核心方法

**RubikFS** 在 EROFS 之上加 4 个 userspace 组件构建有序镜像：

- **Data grouper**：按文件类型预分组（ELF Code / ELF Data / Binary / Text / Others），不同类型数据相似性低，分组处理把整体复杂度从 O(N²) 降一个量级。ELF 文件按 .rodata 切成 code/data 两半。
- **Data chunker**：固定大小切块（FSC）+ 完全去重，chunk size = min(4 KB, BlockSize/16) 平衡压缩比与页对齐。
- **Hotness grouper**：用启动期 kprobe 抓取 hot chunks（trace.txt 格式 (file_path, offset, size)），把每个数据组进一步切成 hot/cold 子组。
- **Similarity sorter**（核心）：对每个子组里的 chunk 用 gear hash 抽样取 1/P=1/128 个特征；构建相似图（边权 = 共享特征数 / 总特征数，0–1 连续值，区别于去重的 0/1）；用 [[METIS]] 子图分割成 size=64 的 cluster；intra/inter-subgraph 都按相似度排序；最后打包成 data stream 并生成 12 B/chunk 的 (orig_offset, packed_offset, size) 索引。

复杂度优化：用 hashtable 把特征散列到 bucket，相似图构建从 O(N²·M²) 降到 O(N)。

## 关键结果

- 6 个开源镜像（openEuler、4 个 OpenHarmony 板镜像、Friendica 容器）× 3 种压缩算法（[[LZ4]]、[[ZSTD]]、[[LZMA]]）：RubikFS 压缩比一致高于 EROFS/Squashfs，最多提升 42.60%；在小镜像（Harm-3516/3518/3861）上甚至超过 Direct，因为分簇能跨越 LZ4 的 64 KB 字典限制。
- Hotness grouper：12% hot data 配置下，1 MB block 的 runtime 减 65%、读取量降 70.70%。
- Sensitivity：data/hotness grouper 对压缩比的影响 < 1%（可忽略）。

## 相关

- **相关概念**：[[Content-Defined Chunking]]、相似度去重、Huffman / dictionary compression、[[METIS]] 图分割
- **同类系统**：[[EROFS]]、[[Squashfs]]、Finesse、Odess、Palantir
- **同会议**：[[FAST-2026]]
