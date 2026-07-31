---
type: paper
name: ZENO
full_title: "Accelerating Confidential Databases with Crypto-free Mappings"
authors: [Wenxuan Huang, Zhanbo Wang, Mingyu Li]
venue: OSDI
year: 2026
tags: [confidential-computing, databases, tee, encryption, transactions]
source_pdf: "[[osdi26-huang-wenxuan.pdf]]"
source_md: "[[osdi26-huang-wenxuan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 用免密码映射加速机密数据库（OSDI 2026）

> **原题**：Accelerating Confidential Databases with Crypto-free Mappings

> **一句话总结**：ZENO 挑战“离开 TEE 的每个中间值都必须是 ciphertext”的默认，把 untrusted DBMS 中的值改为 data-independent FID、在 privacy zone 以 O(1) array 映射到 plaintext，只在 mapping eviction 时异步 block encryption；相对 HEDB，TPC-H 在 ARM S-EL2/x86 TDX 最高快 53.1/94.7 倍且 storage 少 38.9%–52.8%。

## 问题与动机

现代 confidential database 为保留 DBA 的 plan inspection/debug 能力，不把整个 DBMS 放入 TEE，而只把 expression operator 放进 privacy zone。每次 SUM/comparison RPC 都要 decrypt operands、compute、encrypt result；`N` 行 SUM 需 `2N−2` decrypt 和 `N−1` encrypt。AES-GCM 的 12B nonce+16B tag 还把 4B integer 扩成 32B。

HEDB profile 中 crypto 占 10.5%–62.6% latency，ciphertext expansion/I/O 占 13.9%–25.5%，storage 为 plaintext 的 1.4–3.1 倍（图 2）。论文的关键重构是：ciphertext 在 split CDB 实际兼任“不可信域里的 opaque pointer”；保护与 indirection 可分离，pointer 无需自身做昂贵 encryption。

## 关键观察 / 隐含假设

- **观察 1：DBMS 无需理解 sensitive value，只需持有不可推断内容的 identifier。** 64-bit FID 作为 direct array index，在 privacy zone 取 plaintext，metadata 从28B降到8B（§4.1）。
  - **依赖假设**：FID allocation/access pattern 不泄露超出 threat model 的 schema、equality、frequency 或 lifetime 信息。
  - **可能失效场景**：攻击者可通过 stable FID 关联行/版本，或 operator/query trace 本身泄露敏感 access pattern。
- **观察 2：只需 external synchrony，而非双向 state equality。** invariant 是“DBMS 可见的每个 FID 都映射到有效最新 plaintext”；mapping store 多出的 orphan 不影响 correctness（§5）。
  - **依赖假设**：FID 在旧 DBMS reference [[Garbage-Collection|GC]] 前不复用，WAL ordering 与 recovery严格保持。
- **观察 3：ciphertext cache 仍受 key lookup和 expansion 限制。** hash get/put 平均334.9/2,649.4 cycles，而 direct FID 为113.8/316 cycles（§7.2）。
  - **依赖假设**：mapping array 的 working set/locality 足够好；大于 TEE memory 时 prefetch/partition 能隐藏 eviction。
- **假设 1：HEDB dual-zone threat model与 crypto-free identifier 一样安全。**
  - **证据强度**：中；论文给 security analysis，但 access-pattern leakage、rollback和 side-channel 仍继承 TEE/CDB 边界。

## 核心方法

integrity zone 运行 commodity PostgreSQL，表中 sensitive field 替换为 FID；privacy zone 包含 proxy、plaintext operator、mapping store 与 WAL。mapping store 是按 partition 划分的紧凑 array，FID 由 partition prefix+offset 组成并直接 indexing；temporary/permanent entry 分离，DBMS table/storage layout 与 mapping partition 对齐，并配合 LRU/sequential prefetch 保持跨域 spatial locality（图 3）。

plaintext 只在 trusted memory 使用。mapping entry 被逐出时，以较大 block 异步加密到受保护 storage，而非 query critical path 逐 field AES-GCM。这样同时移除 per-operator crypto 与 field metadata expansion。

transaction update 采用 MVCC-like out-of-place entry：旧 FID mapping 保留到 PostgreSQL VACUUM，abort 时 DBMS 仍引用旧值。commit 将 encrypted mapping-store WAL record 嵌入 DBMS WAL stream并排在 transaction commit record 前；crash 若只恢复新 mapping 而 commit 未落盘，形成不可达 orphan而非错误 visible state（图 4）。

## 设计取舍

- **hot-path speed 换 trusted state 容量**：plaintext mapping store 成为重要 TEE-resident state，大数据需 eviction/prefetch。
- **8B FID 换 equality/access leakage 与 lifetime管理**：比 ciphertext 小，但稳定 identifier 可能提供关联信号。
- **external synchrony 换 orphan/GC complexity**：允许额外 mapping 简化 crash protocol，却需全局 scan 和与 VACUUM 协调。
- **split maintainability 换跨域 RPC**：仍保留 dual-zone/context-switchless polling；ZENO 未达到 plaintext performance。
- **边界条件**：operator-heavy、field小、crypto/IO expansion 主导时收益最大；large plaintext、random working set或TEE memory很小时 lookup/eviction主导。

## 实验与结果

- PostgreSQL 15.5、ARM Secure EL2 与 Intel TDX 上，TPC-C 100 warehouses、300s measurement 中，ZENO 将 HEDB 相对 plaintext 的 throughput loss 分别减少18.1%–49.8%和51.5%–73.8%（图 5）。
- TPC-H SF=3、总 memory 6GB下，HEDB 平均慢 plaintext 10.0/23.8 倍，ZENO 为2.3/4.5倍；较HEDB平均快4.4/5.3倍，单 query 最高53.1/94.7倍（图 6）。
- 九个 anonymized industrial query、每表1M synthetic rows中，ARM/TDX 平均较HEDB快4.6/2.9倍，最高6.0/3.6倍（图 7）。storage 在TPC-C/TPC-H/industrial少38.9%/52.8%/42.4%（表 3）。
- factor ablation 中 batching -5.8%、decrypt cache -21.8%、O(1) FID lookup -25.7%、8B reduced expansion -53.0%、partition locality 再 -16.6% geomean execution time（图 8）。
- embedded mapping WAL 令 TPC-C TPS 低2.6%、每 commit 增18.3µs；2.6GB WAL recovery 26.3s中 mapping replay 4.1s（15.6%）（§7.2）。random access仍最高快HEDB 2.3倍，1GB memory下为2.2倍（图 9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| FID mapping 大幅降低 split-CDB analytical overhead | 图 6：平均4.4/5.3倍，最高53.1/94.7倍 | TPC-H SF3、ARM S-EL2/TDX、6GB预算 | 强 |
| 收益来自 lookup与expansion双重消除 | 图 8：FID -25.7%，compact FID再 -53.0% | cumulative ablation、TPC-H geomean | 强 |
| transactional semantics 代价较小 | 图 5、§7.2：loss减少且commit仅 -2.6% | TPC-C、同步commit、单机crash replay | 中 |
| 方法适用于工业查询 | 图 7：平均4.6/2.9倍 | anonymized schema+synthetic 1M rows，不是真实data/trace | 中 |

## 批判性分析

### 论证链条

把 ciphertext 重新解释为 pointer 并拆分 protection/indirection，是清晰的新抽象；factor analysis 确认 direct lookup 与 compact representation 都不可缺。ZENO 没有宣称消除所有 encryption，而是把它移到 eviction/storage path。安全等价比性能论证更依赖 threat-model 定义：FID 可见性是否可接受是采用前必须独立审查的核心。

### 假设压力测试

stable/direct FID 暴露 equality、update frequency、partition和近似 cardinality；如果原HEDB ciphertext使用随机 nonce隐藏这些关联，泄漏面可能扩大。mapping store 超内存、uniform random access或adversarial scan会产生 trusted/untrusted paging与crypto backlog。FID reuse、VACUUM 与 crash交错若有bug可能把旧 ID 指向新 secret。

### 实验可信度

两种 TEE architecture、OLTP/OLAP/industrial、storage、factor/transaction/recovery/skew/memory sensitivity覆盖全面，HEDB是强直接baseline。TPC-H SF3较小，工业数据是synthetic且schema anonymized；未报告 multi-node replication、backup/PITR、online schema change、long-run orphan accumulation和安全 side-channel experiment。

### 系统性缺陷

mapping store+WAL 成为新的敏感 durability subsystem；6.1K C/C++虽不大但需与 PostgreSQL MVCC/VACUUM 紧耦合。privacy zone polling占core，array corruption/replay/FID exhaustion、partition rebalance和key rotation未充分展开。集成GaussDB说明工程价值，但论文未给部署规模/production SLO数据。

## 局限与后续工作

- **局限 1**：访问模式与FID关联泄漏边界强依赖 threat model，未提供obliviousness。
- **局限 2**：单机PostgreSQL，不覆盖replication、distributed transaction、backup/restore和schema migration。
- **后续工作 1**：形式化比较HEDB ciphertext与FID的 leakage function，并用query-trace inference实验量化敏感属性可推断度。
- **后续工作 2**：在SF100+/mapping working set大于TEE memory下测P99 query、eviction encryption backlog和prefetch miss。
- **后续工作 3**：扩展到streaming replication/PITR并注入commit、WAL flush、VACUUM、failover各点crash，验证external-synchrony invariant。

## 相关

- **相关概念**：[[Confidential-Computing]]、[[Trusted-Execution-Environment]]、[[Encrypted-Database]]、[[MVCC]]
- **同类系统**：[[HEDB]]、[[PostgreSQL]]、[[GaussDB]]
- **同会议**：[[OSDI-2026]]
