---
type: paper
name: Z-LFS
full_title: "Z-LFS: A Zoned Namespace-tailored Log-structured File System for Commodity Small-zone ZNS SSDs"
authors: [Inhwi Hwang, Sangjin Lee, Sunggon Kim, Hyeonsang Eom, Yongseok Son]
venue: ATC
year: 2025
tags: [file-system, zns-ssd, log-structured, storage, f2fs]
source_pdf: "[[atc2025-hwang.pdf]]"
source_md: "[[atc2025-hwang]]"
---

# Z-LFS: A Zoned Namespace-tailored Log-structured File System for Commodity Small-zone ZNS SSDs (ATC 2025)

> **一句话总结**：为商用小 zone ZNS SSD 设计的 LFS，让元数据 append-only 摆脱额外 CNS SSD，并通过推测式日志流管理 + 冲突感知分配，相对 F2FS 提升 33.4×、相对 eZNS+F2FS 提升 3.5×。

## 问题

ZNS SSD 把物理空间切成必须顺序写、显式 RESET 才能重用的 zone，去掉了 SSD 内部 GC 与大 OP 区，但已有 LFS（如 F2FS）的设计暴露三个挑战：1) F2FS 的 metadata 块对齐、定址固定、原地更新——必须搭配 CNS SSD 才能跑，增加成本；2) F2FS 多日志流（hot/warm/cold × data/node）只用 6 个 active zone，远没用满 small-zone ZNS SSD 上百个 active zone；3) small-zone SSD 中 zone 与 die/channel 是细粒度静态映射，并发写到同 die/channel 会互相冲突拖性能。eZNS 等 ZNS interface 提供了 logical zone 抽象但与 F2FS 缺乏跨层感知。

## 核心方法

三大策略：

- **Append-only metadata management**：观察到 ZNS 上 LFS metadata 因 segment 不可原地修改而呈现两种生命周期——immutable（如 segment summary，与 segment 同生共死）vs mutable（如 SIT/NAT，频繁更新）。Z-LFS 把 immutable metadata 直接 append 到对应 segment 末尾、随 GC 一起清理；mutable metadata 用 delta logging：只把变更 entry 打包成 4KB 日志块循环写入两个 metadata log zone，到阈值后异步 merge 到一对 metadata table（备用切换保证一致性）。
- **Speculative log stream management**：维护全局 active zone pool。监控每个日志流的写入量 $W_i$，按 $A_i = A \times W_i / W_T$ 动态调整其 active zone 配额，高强度流 scale-up，低强度流 scale-down（FINISH zone 后台释放）。data 与 node 流分别配额（因为它们通常不并发，checkpointing 时 data 阻塞）。
- **Conflict-aware zone allocation**：把连续 zone（数 = channel 数）组成 superzone 避免 channel 冲突；映射到同一 die 的 superzones 组成 interference group (IG)；分配时优先选不同 IG 的 superzone。Segment 被切成 subsegment 散布到 superzone 内多个 zone，保留顺序写约束并提升 zone-level 并行。

基于 F2FS 在 Linux 5.17.4 实现，分别管理 SIT/NAT 的 delta log 与 merge 区。深度细节回 [[atc2025-hwang]]。

## 关键结果

- vs F2FS：顺序/随机写吞吐最高 12.4×/25.2×，文件创建吞吐 27.7×
- vs F2FS_SS（静态条带化）：顺序/随机写 47%/30% 提升
- vs eZNS+F2FS（state-of-the-art）：随机写 3.5×、文件创建 1.6×
- 顺序读 +50%（散布数据 + 利用 zone 级并行）
- 随机写 P99.9 尾延迟降低 99.9%（vs F2FS）、56.4%（vs F2FS_SS）
- 元数据空间开销仅 0.02% ZNS SSD 容量
- RocksDB fillseq/fillrandom/overwrite 上同步获益
- 开源：https://github.com/Z-LFS/Z-LFS

## 相关

- **相关概念**：[[Log-Structured-File-System]]、ZNS SSD、[[Garbage-Collection]]、F2FS
- **同类系统**：F2FS、ZenFS、eZNS、ZNS+
- **同会议**：[[ATC-2025]]
