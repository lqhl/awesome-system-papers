---
type: paper
name: ShieldReduce
full_title: "ShieldReduce: Fine-Grained Shielded Data Reduction"
authors: [Jingyuan Yang, Jun Wu, Ruilin Wu, Jingwei Li, Patrick P. C. Lee, et al.]
venue: ATC
year: 2025
tags: [storage, deduplication, delta-compression, sgx, secure-storage]
source_pdf: "[[atc2025-yang-jingyuan.pdf]]"
source_md: "[[atc2025-yang-jingyuan]]"
---

# ShieldReduce: Fine-Grained Shielded Data Reduction (ATC 2025)

> **一句话总结**：在 Intel SGX enclave 里跑 dedup + delta compression + local compression 完整 pipeline，提出 bi-directional delta compression 维持 base chunk 物理局部性，相比 forward-only baseline 上传吞吐 +3.5×、压缩比追平明文细粒度 reduction。

## 问题

外包备份要同时做存储节省和数据机密性。已有 encrypted deduplication（convergent encryption / message-locked encryption）牺牲机密性以保留 dedup，但加密后高熵无法再做 delta + local compression。把完整 fine-grained data reduction 放进 [[SGX]] enclave 是直接路线，但 delta compression 要管理 base chunks——SGXv2 EPC 上限 512 GiB 还是装不下、放磁盘按需加载又有 ECall/OCall（8000 cycles vs syscall 150 cycles）和 disk I/O 双重开销。LoopDelta 等已有 backward delta 只为缓解 chunk fragmentation，没考虑 storage-perf trade-off 与安全。

## 核心方法

- 基于 DEBE 扩展：第一阶段 frequency-based dedup 用小指纹索引在 enclave 内做、第二阶段全量索引在 enclave 外。
- **Bi-directional delta compression**：以 batch（128 chunks）为单位，先做 locality detection，q/n（base chunk 跨容器数 / batch 大小）≤ 阈值 t 走 forward delta；否则走 offline backward delta，把新数据当 base、把旧 base + 已 delta 化的 chunks 都重新 delta 到新 base。
- **Hybrid inline/offline**：物理局部性强时 inline forward delta + local compress 直接写盘；局部性弱时只 local compress 入盘并把映射记到 backward index，离线再做 backward delta。
- **Tunable α**：offline reduction target，按已删数据量门限决定哪些 old base chunk 跳过 backward 不做（牺牲存储换性能）。
- 索引设计：fingerprint index / feature index / delta index / backward index，敏感字段用 AES-256 加密。

深度细节回 [[atc2025-yang-jingyuan]]。

## 关键结果

- Linux/Web/Docker/SimOS 四类备份：α=0 时压缩比 25.8/58.6/14.9/63.6，与 ForwardDelta 明文基线持平；Web 数据集上比 SecureMeGA 多 3.6× 压缩。
- 上传吞吐：比 ForwardDelta 快 1.1-3.5×；与 SecureMeGA 持平时多 3.6× 离线压缩节省。
- 多客户端：聚合上传 826.7 MiB/s（4 客户端，redundant 数据集）、聚合下载 1024.6 MiB/s。
- CPU 利用率比 DEBE 多 1.1-11.6%，主要花在 feature 提取 + delta compression。

## 相关

- **相关概念**：[[Deduplication]]、[[SGX]]、[[Trusted-Execution]]
- **同会议**：[[ATC-2025]]
