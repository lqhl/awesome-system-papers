---
type: paper
name: SkySync
full_title: "SkySync: Accelerating File Synchronization with Collaborative Delta Generation"
authors: [Zhihao Zhang, Huiba Li, Lu Tang, Guangtao Xue, Jiwu Shu, Yiming Zhang]
venue: FAST
year: 2026
tags: [file-sync, sky-computing, storage-metadata, checksum-reuse, delta-sync]
source_pdf: "[[fast2026-zhang-zhihao.pdf]]"
source_md: "[[fast2026-zhang-zhihao]]"
---

# SkySync: Accelerating File Synchronization with Collaborative Delta Generation (FAST 2026)

> **一句话总结**：现代存储栈（[[BTRFS]]/[[ZFS]]/dm-verity/HDFS/[[Ceph|BlueStore]]/MeGA 等）已为完整性/去重/校验维护了大量块级 checksum；SkySync 把这些**已有**元数据当作 delta 同步的 weak checksum 直接复用，用 [[CRC32C]] 的代数性质做轻量级组合算 chunk-level checksum，相比 [[rsync]]/[[dsync]] 计算开销降低 **89.3%**，client/server sync 性能提升 **1.1×–2×**，网络流量持平。

## 问题

Sky computing 让数据在多云间穿梭，跨云 delta sync 越来越关键。但 [[rsync]]（FSC-based）和 [[dsync]]（CDC-based）的 delta generation 三步——chunking / checksum 计算 / chunk searching——里 checksum 计算 + searching 占总同步时间高达 **95%**：rsync 的 client/server 双端 byte-by-byte rolling Adler32 + MD5 极重；dsync 虽换更轻 rolling 算法，仍要算文件每个字节的 weak checksum。即便用 AVX-512 SHA-NI 等硬件加速，因 rolling hash 不规则访存、缓存利用率低、prefetch 失效，提升有限。Dropbox（rsync-like）/Seafile（dsync-like）即使运行在已有 BTRFS/ZFS checksum 的盘上也得**重算**——因为 boundary-shift problem 让现有 fixed-size checksum 无法直接当 chunk-level checksum 用。

## 核心方法

**洞察**：跨四类存储系统（block device / file system / dedup system / distributed system）已有大量 checksum 元数据可被「适配 + 组合」复用为 sync 的 chunk checksum。

**Storage-Layer Metadata Mining（§3.1）**：枚举可挖掘的元数据来源——dm-verity（MD5/SHA via cryptsetup）、fs-verity + EXT4/F2FS/BTRFS/ZFS（CRC32C/XXHASH/SHA/BLAKE2）、MeGA/MFDedup（CRC32C/MD5/SHA）、HDFS/BlueStore/MooseFS/SeaweedFS（块级 checksum API）。各家用户态工具（btrfs-progs、zbd、cryptsetup）即可 dump。

**CRC32C Combining（§3.2.1）**：基于 [[CRC32C]] 在 GF(2) 上的线性性质 $\text{CRC}(A \cdot B) = \text{CRC}(A \cdot 0^{|B|}) \oplus \text{CRC}(0^{|A|} \cdot B)$，用 storage-layer 的 4KB 块 checksum 通过若干 XOR + 追加零位推出 CDC 切出的变长 chunk $C_R$ 的 checksum。SkySync 只对**差异字节** $x, y$（chunk 边界处的小段）真算 CRC32C，剩下都是 metadata 上的轻量代数操作。该方法泛化到任何具备 XOR-friendly 代数结构的多项式 checksum。

**Streamlined Chunk Searching（§3.2.2）**：rsync/dsync 用 16-bit hash code → 32-bit weak → strong 三级跳指针。SkySync 用预分配的 flat-array Cuckoo hash table，从 chunk 现成的 CRC32C 直接派生两个 candidate bucket（无需独立的 hash 函数），bucket 是 sub-array 存多 chunk metadata，极简化访问。

**协议增强**：分别在 [[rsync]] 和 [[dsync]] 协议上实现 FSC-/CDC-based SkySync，在 communication 协议里加入「拉 storage-layer checksum」步骤，并优化 checksum 算法选择。

## 关键结果

- 计算开销最高减少 **89.3%**（相比 rsync/dsync）。
- Client / server sync 性能 **1.1×–2×** 提升（10MB 与 100MB 数据集，inter-/intra-cloud 场景）。
- 网络流量保持与 rsync/dsync 一致——不改变 delta 内容，只是换计算来源。
- 已有硬件加速（AVX-512 / SHA-NI）即便加上去也提升有限，反衬 SkySync「砍计算量本身」路线的优势。

## 相关

- **相关概念**：[[CRC32C]]、[[Content-Defined-Chunking]]、[[Cuckoo-Hashing]]、[[Delta-Sync]]、[[Sky-Computing]]
- **同类系统**：[[rsync]]、[[dsync]]、NetSync、WebR2sync+、[[ParaSync-FAST26|ParaSync]]（同作者另一篇）
- **同会议**：[[FAST-2026]]
