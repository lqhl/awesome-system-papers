---
type: paper
name: MlsDisk
full_title: "MlsDisk: Trusted Block Storage for TEEs Based on Layered Secure Logging"
authors: [Erci Xu, Xinyi Yu, Lujia Yin, Xinyuan Luo, Shaowei Song, Qingsong Chen, Shoumeng Yan, Jiwu Shu, Hongliang Tian, Yiming Zhang]
venue: FAST
year: 2026
tags: [tee, secure-storage, log-structured, lsm-tree, sgx, cifc]
source_pdf: "[[fast2026-xu.pdf]]"
source_md: "[[fast2026-xu]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# MlsDisk：基于分层安全日志记录的 TEE 可信块存储（FAST 2026）

> **原题**：MlsDisk: Trusted Block Storage for TEEs Based on Layered Secure Logging

> **一句话总结**：观察到 SGX-PFS 的 in-place [[Merkle-Hash-Tree]] 使每次写产生 H 级联更新（加 recovery journal 可达 2H 写放大），而 NaiveLog 虽能 13–16× 提速却因无 index/GC 不可实用；MlsDisk 用四层 layered secure logging 把用户数据 out-of-place append、索引与 GC 拆开，MHT 仅留在 <2% 的 metadata TxLog 上，在完整 CIFC 下对 SGX-PFS 取得 7.3–21.1×（FIO）与 1.4–3.6×（trace-driven）提升。

## 问题与动机

[[TEE]]（Intel [[SGX]]、AMD [[SEV]] 等）能保护 enclave/VM 内内存，但持久化仍依赖不可信 host 磁盘。常见做法是构建 **trusted virtual disk**，向上暴露标准 block 接口，向下与 host 交互。

现有方案的安全–性能谱系大致是：
- **CryptDisk**（[[dm-crypt]] + [[dm-integrity]]）：只保证 confidentiality + integrity（CI），无法防 rollback。
- **SecureFS**：在 trusted memory 里 pin slab table 加 freshness，仍 in-place，性能接近 CryptDisk。
- **SGX-PFS**（SOTA）：用全盘 [[Merkle-Hash-Tree]] 保护 in-place 数据，提供完整 **CIFC**（confidentiality / integrity / freshness / consistency），但每次写要从 leaf 级联更新祖先节点的 key/MAC，高度 H 的 MHT 带来 H 倍写放大，recovery journal 再翻倍到约 **2H**；作者实测 MHT block I/O 是主导开销，CryptDisk 在 trace/FIO 随机写下吞吐分别为 SGX-PFS 的 4.1× / 2.5×。

论文的核心问题是：**能否在保持与 SGX-PFS 等价的 CIFC 前提下，摆脱全盘 in-place MHT 的性能枷锁？** 直接转向 out-of-place logging 的 strawman **NaiveLog** 用 chained-MAC batch 链实现 CIFC 且随机写可超 RawDisk，但缺少 index 导致读要扫全 log（时间 unbounded），缺少 GC 导致空间 unbounded；而直接把 [[RocksDB]]/[[LevelDB]] 或 [[Speicher]] 式 LSM 搬进 TEE，索引/compaction/GC 的状态机使 CIFC 证明极其困难（Speicher 自认 consistency 不足，LevelDB 事务协议也被证明不可靠）。

## 关键观察 / 隐含假设

- **观察 1：SGX-PFS 的性能瓶颈是 MHT 级联更新 + 随机写，而非 MAC 计算本身。**
  - **依赖假设**：4 KiB block、height-H 的 MHT、每次写触发 leaf-to-root 更新；integrity 校验主要在 read 路径，CPU MAC 可达 tens of GB/s。
  - **可能失效场景**：若 workload 以大块顺序 overwrite 为主、或 MHT 极浅且 cache 命中率极高，SGX-PFS 相对劣势缩小；论文未覆盖这种极端 skew。

- **观察 2：out-of-place append 可消除数据面的 MHT 级联，但 index 与 GC 的安全分析复杂度才是实用化的真正障碍。**
  - **依赖假设**：用户数据与 metadata 可解耦；metadata 体量远小于用户数据（论文称 append-only log 占比 <2%），因此 metadata 上的 MHT 开销可接受。
  - **可能失效场景**：极小磁盘 + 高 churn workload 使 metadata/compaction 占比上升；或 index 记录数爆炸导致 L2 compaction 成为新瓶颈（§10.5 已显示 disk aging 会让 WAF 从 1.025 升到 1.115）。

- **观察 3：分层抽象 + 事务化结构操作，可以把 CIFC 证明归约到 root key，而不必对 monolithic log-structured 设计做全局形式化。**
  - **依赖假设**：每层只保护本层 data payload，metadata 全部由下层 CIFC-compliant primitive 托管；L1 提供 ACD 事务，L0 EditJournal 是 root-of-trust。
  - **可能失效场景**：跨层 crash 时若 L0 journal 未提交对应 edit，已落盘用户数据会变成「orphan」——论文认为这是安全特性，但应用可能看到「写成功却读不到」的语义；多 writer 并发场景 L1 明确不提供 general Isolation。

- **假设 1：威胁模型与 SGX-PFS 相同——privileged/active/online adversary，但不考虑 DoS、side-channel、整盘 offline rollback（后者靠 §8 扩展补救）。**
  - **证据强度**：强——与 baseline 对齐，安全 claim 可横向比较；但意味着结论不自动适用于需防 eviction/整盘回滚的生产部署（§10 主实验未启用 §8 扩展）。

- **假设 2：100 GB 盘 + 1.5 GB cache + 10% over-provisioning 足以代表 TEE 安全存储的典型部署。**
  - **证据强度**：中——对 SGX EPC 紧张环境合理，但未测 cache 远小于 metadata 工作集、或磁盘接近满且 cleaning 不及时（§10.6 显示无 cleaning 时第 4 轮起性能崩塌）时的 tail behavior。

## 核心方法

MlsDisk（**M**ulti-**l**ayered, **l**og-**s**tructured secure disk）用 **layered secure logging** 把 log-structured 存储与安全机制拆成四层，每层向上暴露 CIFC-compliant API，向下只依赖下层 primitive。三条主线（MI-1 分层、MI-2 全层 log-structured、MI-3 metadata 与 data 解耦）直接回应上述观察。

**L3 — Block I/O (BIO)**：标准 `Read/Write/Sync` block 接口。写路径：从 BVT 顺序分配 HBA → AES-GCM 加密 + MAC → append 到 host → 在 LBT 更新 `⟨LBA, (HBA, key, MAC)⟩`，RIT 维护反向映射。读路径：查 L2 index 取 HBA/key/MAC → 读盘校验返回。用户数据 **不做 chaining**，避免 NaiveLog 的读扫描问题。

**L2 — TxKV**：自实现 [[LSM-Tree]]（MemTable + SSTable + WAL），刻意不移植 [[LevelDB]]/[[RocksDB]] 以避免已知 crash consistency 漏洞。WAL/SSTable 均实例化为 L1 TxLog；flush/compaction 等结构操作走 L1 事务，保证 L2-wide consistency。LBT/RIT 用 column-family 共享同一 WAL，GC 时双索引原子更新。

**L1 — TxLogStore**：append-only **TxLog** + 内存 **TxLogTable**（log ID、length、root MHT、bucket）。TxLog 内嵌 [[Merkle-Hash-Tree]] 保护 log 内容——因 log 仅占存储 <2%，MHT 写放大不再像 SGX-PFS 那样支配全盘。TxLogTable 的持久化交给 L0，避免循环依赖。提供 ACD（atomicity/consistency/durability），通过禁止同 log 并发写、lazy deletion、随机 log ID 降低冲突，**不提供 general isolation**。

**L0 — EditJournal**：系统 root-of-trust。**CryptoChain**（chained-MAC append，轻量无 per-append MHT）记录 TxLogTable 的增量 edit；周期性 flush **CryptoBlob** snapshot，恢复时从最近 snapshot replay 后续 edit。活跃 snapshot 与当前 journal block 驻留 TEE secure memory 以检测 rollback。

**Crash recovery**：自 L0 向上：恢复 EditJournal → 重建 TxLogTable/TxLog valid length → replay WAL 重建 MemTable → 加载 SSTable → 恢复 LBT/RIT/BVT。若 L0 未 commit 某次事务 edit，对应用户数据即使已写盘也视为未分配（一致性优先）。

**GC 与优化**：16 MiB segment 级 greedy GC（类 [[LFS]]/[[F2FS]]）；BVT 用 BAL 记录增量 alloc/dealloc 避免整表重写；**delayed reclamation** 在 TxKV compaction 淘汰旧 index 记录时回调回收 HBA（写路径免查全 LBT，+31% 随机写吞吐）；**two-level cache** 把 TxLog MHT 节点与 SSTable 数据分 cache（+18% 随机读）。

**可选扩展（§8，主实验未开）**：master sync ID + 外部 trusted store 实现 **irreversibility**（防整盘 rollback）；per-KV/per-SST sync ID 实现 **sync atomicity**（防 [[AtomicDisk]] 所揭示的 eviction attack）。

## 设计取舍

- **收益 vs MHT 范围**：把 MHT 限制在 metadata TxLog，换取用户数据 sequential append 与低 WAF；代价是 L2 compaction、L0 journaling、GC 事务带来额外 CPU/空间开销，且需 ~10% over-provisioning 支撑 delayed reclamation。
- **收益 vs 实现复杂度**：四层抽象 + 自研 LSM/TxLogStore（核心 ~12 kLoC Rust，加 OS 适配共 ~18 kLoC）换可模块化的 CIFC 证明；代价是运维/调试链长于单一 SGX-PFS 库，且 Linux 适配依赖 [[Rust-for-Linux]] device mapper。
- **收益 vs 隔离语义**：L1 放弃 general isolation、靠命名与锁规避冲突，简化安全分析；代价是高并发多 writer 同 key 场景需上层串行化，论文未量化这类 tail latency。
- **边界条件**：随机写、写密集 trace（wdev）、B+Tree DB（BoltDB YCSB 4.2–5.5×）最优雅；顺序读/写密集 FS workload（fileserver、videoserver）可能略慢于 CryptDisk（6–10%）；[[SQLite]]/[[RocksDB]] 因已有 WAL/LSM 顺序写，收益有限。

## 实验与结果

- **平台**：Intel SGX（Occlum）+ AMD SEV（Linux）；100 GB 逻辑盘，1.5 GB cache；baseline 为 CRYPTDISK（CI）与 PFSDISK（SGX-PFS）。
- **FIO microbench**：较 PFSDISK 写吞吐 **7.3–21.1×**（SGX），读 **1.4–2.4×**；较 CRYPTDISK 随机写 **1.1–8.9×**（SGX）/ **1.1–6.8×**（SEV），顺序写/读仅慢 7–10%。
- **Trace-driven**（5 条 datacenter block trace）：较 PFSDISK **1.4–3.6×**；写密集 wdev 较 CRYPTDISK ~**2.5×**。
- **Filebench**（4 workloads）：较 PFSDISK **1.4–2.3×**；oltp（小随机写）明显优于 CRYPTDISK，fileserver/videoserver 略逊。
- **YCSB on SEV/Ext4**：BoltDB **4.2–5.5×**，PostgreSQL **1.3–4×**；SQLite/RocksDB 与 CRYPTDISK 接近。
- **Sensitivity**：disk utilization 升高时 WAF 1.025→1.115，仍比 CRYPTDISK 快 **8.2×**（近满盘）；无 GC cleaning 时第 4 轮随机写性能崩塌，90s cleaning interval 可维持吞吐；delayed reclamation +31% 写、two-level cache +18% 读。
- **Latency breakdown**：随机写下用户 block 加密已超过合并 I/O 成为 L3 主延迟；L2 compaction 为写路径主导开销。

## 批判性分析

### 论证链条

动机实验（Fig. 2–3）清晰建立「MHT 级联 → 写放大 → 吞吐差」→ NaiveLog 验证 out-of-place 潜力 → 指出 index/GC 安全鸿沟 → 四层设计逐层归约 CIFC（Claim 1–4）→ 多平台多 workload 验证，主链条闭合较好。最强证据在 **随机写 microbench** 与 **trace/Filebench 写密集场景**，与「sequentialize physical writes + 缩小 MHT 范围」的设计直接对应。较弱环节是把 **SGX-only 的 PFSDISK 对比**外推为「所有 TEE 安全存储 SOTA」——SEV 实验只有 CRYPTDISK baseline；以及 CIFC 形式化归约虽清晰，但论文以 claim + 文字证明为主，未见独立 verifier 或机器 checked proof。

### 假设压力测试

- **Metadata 占比 <2%**：高 metadata churn（极小盘、超多 TxLog、频繁 compaction）可能让 L1 MHT 开销从「可忽略」变为瓶颈；disk aging 实验只覆盖用户数据 WAF，未单独拆 metadata 放大。
- **1.5 GB cache**：随机读性能随 cache 增大而升（Fig. 14），SGX EPC 或 SEV 内存紧张时，two-level cache 收益可能打折；论文未测 cache << working set 的生产极限。
- **Delayed reclamation + 10% over-provisioning**：空间效率换写路径性能；磁盘长期高 utilization 且无 cleaning 时 Fig. 16 显示 threaded logging 导致断崖式下降——运维必须调 cleaning interval，论文未给出自适应策略。
- **Threat model 缺口**：主评估未启用 irreversibility/atomicity；若攻击者利用 eviction 或 offline 整盘 rollback，基础 MlsDisk 与 SGX-PFS 同样不设防。Side-channel（access pattern）明确排除，对加密磁盘仍可能泄漏 LBA 访问模式。
- **L1 无 isolation**：多租户 block 设备若上层 FS 并发写同一 LBA，依赖「禁止同 TxLog 并发写」等启发式，极端竞争下的正确性与性能论文未讨论。

### 实验可信度

- Baseline 选取合理：CRYPTDISK 代表 CI-only 工业实践，PFSDISK 代表 CIFC SOTA；并说明 Graphene/SecureFS 性能相近故用 CRYPTDISK 代表。
- 公平性：统一 100 GB 容量、调大 SGX-PFS cache 至 1.5 GB；benchmark 刻意触发 TxKV compaction 以测最坏情况之一，对 MlsDisk 偏「严苛」而非偏袒。
- 缺口：缺少 **tail latency / P99**、多进程并发、长时间 aging + 混合读写、启用 §8 扩展后的性能开销、与 [[AtomicDisk]]/[[Speicher]] 的直接端到端对比；安全实验仅为分析而非渗透测试；YCSB 只在 SEV 上跑。正确性依赖分层恢复叙述，未见 fault injection 系统性验证。

### 系统性缺陷

- **尾延迟与 foreground interference**：background GC/compaction/cleaning 对 sync 密集 workload（varmail 与 CRYPTDISK 同退化）的影响未量化 P99；论文未讨论。
- **空间放大**：metadata ~2% + 10% over-provisioning + GC 前无效块滞留，实际可写容量显著低于逻辑 100 GB；tenant 计费场景需明示。
- **可观测性/运维**：四层 TxLog/EditJournal 状态对管理员不透明；故障诊断需理解 L0–L3 恢复顺序，复杂度高于 monolithic SGX-PFS。
- **跨平台一致性**：Occlum/SGX 与 Linux/SEV 适配代码路径不同（Table 1：Linux 适配 5.2 kLoC），行为等价性仅靠测试覆盖，无形式化保证。

## 局限与后续工作

- **局限 1**：基础威胁模型不含整盘 rollback、eviction、side-channel；§8 扩展在评估中默认关闭。
- **局限 2**：L1 TxLogStore 不提供 general isolation；NaiveLog 式全历史扫描被移至 recovery-only 的 L0，但 L0 journal 仍需周期性 snapshot 控制恢复时间。
- **局限 3**：顺序 IO 场景相对 CRYPTDISK 有 6–10% 开销；无 cleaning 时碎片化可导致性能断崖；SQLite/RocksDB 等已 log-structured 的上层收益有限。
- **Future work 1**：测量 production TEE 磁盘 trace 下的 metadata 比例、compaction 占空比与 tail latency，验证 <2% MHT 假设在真实 churn 下是否成立。
- **Future work 2**：将 irreversibility/atomicity 与性能联合 benchmark，量化对 sync-heavy workload 的开销；与 [[Nimble]] 类 external trusted store 集成的工程路径。
- **Future work 3**：在 EPC/内存受限配置下扫 cache size，给出可部署的 minimum memory guideline；自适应 GC/cleaning 策略避免 threaded logging 悬崖。

## 相关

- **相关概念**：[[TEE]]、[[Merkle-Hash-Tree]]、[[LSM-Tree]]、CIFC、Authenticated-Encryption、Log-Structured-Storage、Write-Ahead-Log、[[dm-crypt]]
- **同类系统**：SGX-PFS、[[Speicher]]、SecureFS、CryptDisk、[[Occlum]]、[[AtomicDisk]]、[[Nimble]]
- **同会议**：[[FAST-2026]]
- **对比**：SGX-PFS 用全盘 in-place MHT 换 CIFC；MlsDisk 用分层 out-of-place log + 局部 MHT；Speicher 扩展 [[RocksDB]] 但 consistency 不足；AtomicDisk 专注 eviction/sync atomicity，与 MlsDisk §8.2 扩展同脉络
