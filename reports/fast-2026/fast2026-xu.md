# MlsDisk: Trusted Block Storage for TEEs Based on Layered Secure Logging

**作者**：Erci Xu (SJTU), Xinyi Yu, Lujia Yin, Xinyuan Luo (NICE Lab, XMU), Shaowei Song, Qingsong Chen, Shoumeng Yan (Ant Group), Jiwu Shu (THU), Hongliang Tian (Ant Group), Yiming Zhang (SJTU & NICE Lab, XMU)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/xu
**源文件**：[[fast2026-xu.pdf]]

---

## 一、背景

可信执行环境（TEE，如 Intel SGX、AMD SEV）允许用户在不可信基础设施上安全运行敏感应用。TEE 可以保障内存数据的硬件级安全，但磁盘上的持久化数据仍依赖软件栈保护。安全虚拟磁盘是解决此问题的关键组件，需要提供四项安全保证——机密性（Confidentiality）、完整性（Integrity）、新鲜性（Freshness）和一致性（Consistency），合称 CIFC。

当前最先进的方案 SGX-PFS 使用 Merkle Hash Tree（MHT）保护就地更新（in-place update）的磁盘数据。每次写操作需要从叶节点到根节点的级联更新，加上用于崩溃一致性的恢复日志，写放大因子可达 2×H（H 为 MHT 高度），导致严重的 I/O 性能瓶颈。

---

## 二、要解决的问题

1. **SGX-PFS 写性能极差**：MHT 级联更新和恢复日志导致写放大严重。实验显示，仅提供加密的 CryptDisk 在吞吐量上比 SGX-PFS 高 2.5×–4.1×，说明 MHT 是性能瓶颈的主因。

2. **朴素日志方案（NaiveLog）不可用**：虽然 append-only 日志可以消除 MHT 级联更新（写性能比 SGX-PFS 高 13.4×–16.6×），但它缺少两个关键功能：
   - **无索引**：读操作需全量扫描所有 batch，时间复杂度无界。
   - **无垃圾回收（GC）**：旧数据无法回收，空间消耗无界。

3. **在日志结构存储中保证 CIFC 极其困难**：引入索引和 GC 会带来复杂的状态交互和并发访问，直接移植成熟的 LSM-tree（如 LevelDB/RocksDB）无法保证完整的 CIFC 属性（Speicher 仅实现 CIF，LevelDB 的崩溃一致性已被证明不可靠）。

---

## 三、洞察与设计

**关键洞察**：日志结构存储（log-structured storage）的索引和 GC 机制之所以难以保证安全性，根本原因是数据与元数据紧密耦合，导致安全推理极其复杂。如果将复杂的日志结构存储分解为多个层次化的抽象，每层仅暴露 CIFC 兼容的 API 并构建在下层原语之上，就可以将安全推理限制在每个独立层内，从而系统性地解决这一问题。

基于此洞察，MlsDisk 采用三个核心设计思想：

1. **分层架构（MI-1）**：四层设计（L3–L0），每层构建在下层提供的 CIFC 兼容原语之上：
   - **L3（Block I/O Layer）**：对外暴露标准块设备接口（Read/Write/Sync），负责用户数据的加密和持久化，通过 L2 维护 LBA→(HBA, key, MAC) 索引
   - **L2（KV Store Layer）**：基于 LSM-tree 的事务性 KV 存储（TxKV），作为 L3 的索引引擎，WAL 和 SSTable 均以 L1 的 TxLog 形式持久化
   - **L1（Log Store Layer）**：事务性日志存储（TxLogStore），管理 append-only 日志文件（TxLog），每个 TxLog 集成 MHT 保护内容，元数据通过 L0 的 EditJournal 持久化
   - **L0（Journal Layer）**：CIFC 兼容的日志抽象（EditJournal），使用 CryptoChain（链式 MAC 的 append-only 日志）和 CryptoBlob（周期性快照）两种密码学结构，作为整个系统的信任根

2. **日志结构方法（MI-2）**：所有层均以 append-only 方式持久化数据，将随机小写合并为大顺序写。

3. **元数据解耦（MI-3）**：每层仅保护自己的数据，将元数据的持久化和安全保护委托给下层，避免 SGX-PFS 和 NaiveLog 中数据/元数据紧耦合的问题。

**安全推理的递归归约**：L3 的安全性归约到 L2 和 L1 → L2 归约到 L1 → L1 归约到 L0 → L0 归约到 root key 的安全性。root key 由 TEE 在运行时保护。

---

## 四、实现细节

- **语言与规模**：Rust 实现，总计约 17.9 KLoC。核心四层分别为 L0: 1.7K, L1: 4.0K, L2: 2.8K, L3: 3.4K。OS 适配层：Occlum 0.4K, Linux 5.2K, Asterinas 0.4K。
- **平台集成**：支持三种 OS 环境——Occlum（Intel SGX LibOS）、Linux（AMD SEV 的 guest OS，基于 Rust-for-Linux 和 device mapper）、Asterinas（Rust 内核）。
- **GC 策略**：经典贪心策略，以 16 MiB segment 为粒度回收。引入 Reverse Index Table（RIT）支持 HBA→LBA 反向查找，与 LBT 共享同一 WAL 通过 column-family 保证原子更新。
- **延迟回收优化**：将无效块的回收搭载在 TxKV compaction 过程中，避免写路径上的索引查询，写吞吐提升 31%。
- **两级缓存**：L2 缓存 SSTable 数据块，L0 缓存 TxLog 的 MHT 节点，消除 SGX-PFS 中 MHT 节点与数据块争抢缓存的问题，读性能提升 18%。
- **崩溃恢复**：自底向上逐层恢复（L0→L1→L2→L3），每层利用下层已恢复的一致状态重建自身。
- **可扩展安全属性**：可扩展支持 irreversibility（防全盘回滚，通过 master sync ID + O(1) trusted store）和 atomicity（防 eviction attack，通过检测 transient snapshot）。
- **开源**：https://github.com/asterinas/mlsdisk

---

## 五、实验结果

**测试平台**：
- SGX：24-core Intel Xeon (Icelake) 3.50GHz, 4×SAMSUNG SATA SSDs (MegaRAID), 256GB 内存 (128GB SGX EPC)
- SEV：32-core AMD EPYC 3.7GHz, Dell NVMe SSD, 512GB 内存

**基线**：CryptDisk（仅加密+完整性）、PfsDisk（SGX-PFS，完整 CIFC）

| 实验类型 | MlsDisk vs PfsDisk | MlsDisk vs CryptDisk |
|---------|-------------------|---------------------|
| FIO 微基准（写） | 7.3×–21.1× 提升 | 随机写 1.1×–8.9× 提升；顺序写有 ~10% 开销 |
| FIO 微基准（读） | 1.4×–2.4× 提升 | 随机读有 6.1%–10.7% 开销；顺序读有 ~7.9% 开销 |
| Trace-driven 工作负载 | 1.4×–3.6× 提升 | 写密集型（wdev）约 2.5× 提升 |
| Filebench | 1.4×–2.3× 提升 | oltp（随机小写）显著提升；顺序负载略低 |
| YCSB (BoltDB) | — | 4.2×–5.5× 提升 |
| YCSB (PostgreSQL) | — | 1.3×–4× 提升 |
| YCSB (SQLite/RocksDB) | — | 与 CryptDisk 持平（自身已为顺序写） |

**其他关键结果**：
- 磁盘老化（90% 利用率）：WAF 从 1.025 升至 1.115，仍比 CryptDisk 快 8.2×
- 额外磁盘空间开销：约 2% 元数据 + 10% over-provisioning
- Cleaning 间隔 90s 时，吞吐量基本不受影响

---

## 六、批判性分析

1. **写优势依赖工作负载**：MlsDisk 的核心优势在于将随机写转化为顺序写。对于已经是顺序写的负载（fileserver、videoserver），MlsDisk 不仅没有优势，反而比简单的 CryptDisk 更慢。YCSB 实验中 SQLite 和 RocksDB 的结果也证实了这一点——它们本身就采用日志结构，MlsDisk 的日志化带来的是额外开销而非收益。论文在呈现结果时倾向于突出随机写场景的大幅提升，对顺序负载下的性能退化轻描淡写。

2. **空间开销被低估**：论文声称元数据仅占约 2% 额外空间，但额外需要 10% 的 over-provisioning 用于延迟回收。这意味着实际额外空间开销约 12%，对于大规模存储场景并不算小。且当 over-provisioning 空间不足时（高利用率），性能退化明显。

3. **单线程评估的局限性**：FIO 配置为 numjobs=1, ioengine=sync，所有评估都是单线程同步 I/O。真实 TEE 应用（数据库、分析系统）通常涉及并发 I/O，但论文完全没有评估多线程场景。L1 的事务隔离机制（非通用 Isolation）在高并发下的表现是未知数。

4. **LSM-tree compaction 的尾延迟问题**：论文承认 compaction 是主要开销源（L2 延迟分解中 compaction 占比显著），但没有提供尾延迟（P99/P999）数据。LSM-tree 的 compaction 抖动是工业界的已知痛点，在安全存储场景下尤其值得关注。

5. **安全分析的形式化程度有限**：论文的安全分析基于层层归约的 claim，但未提供形式化证明。对于声称"CIFC-compliant by design"的系统，缺乏形式化验证是一个显著的缺陷，尤其考虑到 LevelDB 的崩溃一致性问题正是因为缺乏形式化分析而被遗漏的。

6. **SGX-PFS 基线公平性存疑**：论文为 SGX-PFS 实现了可调缓存大小（原始实现为固定大小），但 SGX-PFS 的架构可能并非为大缓存优化。此外，SGX-PFS 读数据块时逐个读取而非批量读取——这看起来更像是实现层面的低效，而非架构层面的根本限制。

---

## 七、AI Infra / MLSys 视角

1. **对 TEE-based 机密计算训练/推理的启发**：随着机密计算在 AI 领域的应用（如隐私保护的联邦学习、安全推理服务），checkpoint 存储和模型权重的安全持久化是实际问题。MlsDisk 的分层安全日志方法可以为 TEE 环境下的大规模模型 checkpoint 提供高效的安全存储方案，尤其适合写密集型的 checkpoint 场景。

2. **日志结构化 + 安全的设计范式可迁移**：在分布式训练场景下，parameter server 或 gradient 聚合服务的状态持久化也需要安全保证。MlsDisk 的元数据解耦思想（MI-3）可以启发安全分布式存储系统的设计——将安全机制与数据管理正交化。

3. **可跟进的方向**：
   - TEE 环境下的安全 KV 存储性能优化（MlsDisk 的 L2 层本身就是一个 CIFC-compliant KV store，可独立使用）
   - 在 GPU TEE（如 NVIDIA Confidential Computing）场景下，MlsDisk 的设计能否适配 GPU 显存与主机存储之间的安全数据交换
   - 多线程/异步 I/O 下的安全虚拟磁盘性能优化

---

## 八、总结

MlsDisk 通过分层安全日志的设计理念，将复杂的日志结构存储与安全机制分解为四层模块化抽象（L3 块 I/O → L2 KV 索引 → L1 事务日志 → L0 密码学日志），每层构建在下层的 CIFC 兼容原语之上，既简化了安全推理，又通过 out-of-place logging 大幅提升了写性能。在提供与 SGX-PFS 等价的安全保证下，MlsDisk 在微基准上实现 7.3×–21.1× 的写性能提升，在真实工作负载上实现 1.4×–3.6× 的提升。其核心优势场景是随机写密集型工作负载；对于顺序 I/O 为主的场景，性能优势有限甚至略有退化。单线程评估和缺乏形式化安全证明是其主要局限。
