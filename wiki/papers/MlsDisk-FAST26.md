---
type: paper
name: MlsDisk
full_title: "MlsDisk: Trusted Block Storage for TEEs Based on Layered Secure Logging"
authors: [Erci Xu, Xinyi Yu, Lujia Yin, Xinyuan Luo, Shaowei Song, et al.]
venue: FAST
year: 2026
tags: [tee, secure-storage, log-structured, lsm-tree, sgx]
source_pdf: "[[fast2026-xu.pdf]]"
source_md: "[[fast2026-xu]]"
---

# MlsDisk: Trusted Block Storage for TEEs Based on Layered Secure Logging (FAST 2026)

> **一句话总结**：把 TEE 安全虚拟磁盘从 SGX-PFS 的 in-place Merkle Hash Tree 换成四层抽象的 log-structured 设计，在保留 CIFC（confidentiality/integrity/freshness/consistency）的前提下，对 SGX-PFS 取得 7.3-21.1× FIO microbench 提升与 1.4-3.6× trace-driven 提升。

## 问题

[[TEE]]（SGX、SEV 等）保证内存级安全，但落盘还得靠软件防护。SOTA 是 SGX-PFS：用 [[Merkle-Hash-Tree]] 包住所有数据块，每次写都得从 leaf 级联更新到 root，再加 recovery journal，写放大达到 2H。CryptDisk 只保证 CI 但不防 rollback；SecureFS 加 freshness 但仍 in-place。NaiveLog（strawman）把所有写做成 chained-MAC log，性能好但没有 index 也没有 GC，读 unbounded、空间 unbounded。难点在于：直接把 LevelDB/RocksDB 这种全功能 LSM 移植进 TEE，难以严格证明 CIFC（[[Speicher]] 就只做到 CIF）。

## 核心方法

MlsDisk = layered secure logging：把 log-structured 存储与安全机制拆成四层互相 build-on，每层只为自己的数据 payload 加密签名，metadata 交由下层托管。

- **L3 Block I/O (BIO)**：暴露标准 block 接口；用户数据 4 KiB 分块，加密 + AES-GCM MAC，HBA 顺序分配；维护 LBT(LBA→HBA)、RIT(逆向)、BVT(bitmap) 等元数据，全部交给 L2/L1 持久化。
- **L2 KV Store (TxKV)**：自实现的 [[LSM-Tree]]（MemTable + SSTable + WAL），结构操作（compaction 等）走事务，所有 SSTable/WAL 实例化为 L1 的 TxLog。
- **L1 Log Store (TxLogStore)**：append-only TxLog + TxLogTable，TxLog 内嵌 [[Merkle-Hash-Tree]]，提供 ACD（无 Isolation，靠命名/写互斥规避冲突）。
- **L0 Journal (EditJournal)**：CryptoChain（chained-MAC append）+ CryptoBlob（周期 snapshot）持久化 L1 的 TxLogTable。是整套系统的 root-of-trust。

安全推理通过 4 个 claim 链式归约到 root key：每层 CIF 都建立在下层 CIF 之上。Crash recovery 从 L0 反向重建到 L3。GC 用 LFS/F2FS 风格 greedy + delayed reclamation，事务原子性由 L1 兜底。两个扩展：master sync ID 防整盘 rollback（irreversibility）；per-KV/SST sync ID 防 eviction attack（atomicity）。

## 关键结果

- FIO microbench 较 SGX-PFS：7.3-21.1× 写吞吐。
- Trace-driven workload：1.4-3.6× 提升。
- Append-only log 仅占总存储 <2%，消除 SGX-PFS 的全盘 MHT 写放大。
- Rust 实现，集成到 Linux+SEV、Occlum+SGX、Asterinas。
- 模块化层次便于安全证明（每层独立证明 CIF）。

## 相关

- **相关概念**：[[TEE]]、[[Merkle-Hash-Tree]]、[[LSM-Tree]]、Authenticated-Encryption、Log-Structured-Storage
- **同类系统**：SGX-PFS、Speicher、SecureFS、CryptDisk、Occlum
- **同会议**：[[FAST-2026]]
