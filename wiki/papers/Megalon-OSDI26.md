---
type: paper
name: Megalon
full_title: "Megalon: Efficient Data Sharing for Partly Coherent CXL Memory"
authors: [Jiyu Hu, Seokjoo Cho, Landon Johnson, Kiran Hombal, Shreesha Gopalakrishna Bhat, et al.]
venue: OSDI
year: 2026
tags: [cxl, memory-coherence, shared-memory, key-value-store, page-cache]
source_pdf: "[[osdi26-hu-jiyu.pdf]]"
source_md: "[[osdi26-hu-jiyu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 部分一致 CXL 内存上的高效数据共享（OSDI 2026）

> **原题**：Megalon: Efficient Data Sharing for Partly Coherent CXL Memory

> **一句话总结**：未来 TB 级 CXL memory 可能只有数百 MB hardware-coherent region；Megalon 将大而少更新的 object index 复制到各 host DRAM，只把小而频繁更新的 coherence record 放 coherent region，并用共享日志处理 index order、record 动态分配和 counter wrap，在 large-dataset YCSB 上相对 HCMeta 提升 3.18×–14.18×。

## 问题与动机

CXL 3.x 允许多 host load/store 同一 memory，但 vendor/practitioner 预计 snoop filter/back-invalidation 只能覆盖几百 MB，而总 pool 达数 TB。论文把它称为 partly coherent model：small coherent region（SCR）和 large non-coherent region（LNR）。LNR object 仍进入 CPU cache，跨 host write 后读者可能看到 stale cacheline。

Tigon/HCMeta 将 data 放 LNR、每 object coherence record 与 key→location index 放 SCR，以 software coherence 弥补；但 index+record 随 object 数线性增长，很快挤爆 SCR，只能反复 unshare/reshare object。24M object/20% cross-host 时 Tigon throughput 因 churn 下降 10×。Megalon 问的是：metadata 也放不下时，如何仍共享大量 object？

## 关键观察 / 隐含假设

- **观察 1**：index 包含 key/location，体积大但更新少；coherence record 只有 lock+counter，体积小却每 write 更新。两者无需采用同一共享机制（§3.1）。
  - **依赖假设**：object create/delete/move 远少于 read/write，log replay 不是主路径。
  - **可能失效场景**：insert/delete-heavy、频繁 object relocation 时，replicated index 和 shared log 会变热。
- **观察 2**：read-only shared object 不需要 per-object write counter/lock；只给 read-write-shared object 动态分配 record，可把 SCR capacity 推迟到写 working set 而非全 dataset（§3.4）。
  - **依赖假设**：系统能正确识别从 read-shared 到 read-write-shared 的 transition，并在所有 host清 stale cache。
- **观察 3**：SCR 只需保存 shared-log tail，log entries 本身可在 LNR；host 通过 tail 排序 index update，allocation transition 时以 log event 走第二条 coherence path（§3.2/§3.4）。
  - **依赖假设**：tail atomic/coherent，读 log entry 时显式 flush/bypass cache，且 log replay可追上。
- **假设 1**：每 host 有足够 local DRAM 保存完整 index replica；当前实现目标 8–16 nodes。
  - **证据强度**：明确边界；node 数增加会线性放大 aggregate memory 和 replay work。

## 核心方法

Megalon index replica 位于每 host DRAM，映射 object ID→LNR/local location 与 optional SCR record pointer。write 对 record lock、更新 data、counter++；read 前后检查 counter，发现 intervening write 就 flush/invalidate host cache并 retry。local index lookup 避免访问 physically shared index（§3.1）。

所有 index mutation 先原子推进 SCR log tail，再 append LNR log。host 在读 index 前检查 tail、replay missing entry。这个顺序也用于 allocate/deallocate coherence record：read-only object 首次被写时分 record；SCR满时把低写频 object 降为 read-shared、释放 record。allocation status 改变期间 dual-path coherence 依赖 log event 触发 cache flush，而稳定期间走快的 record path（§3.4）。

counter 可缩到少量 bits；wrap event 写 log，所有 host flush 对应 cache，避免旧 counter value 与新值混淆。index 还能指向 host-local partition 或 local data copy，借 log 在 CXL/local DRAM 间移动 object（§3.5）。

作者以约 8K C++ library 实现 linearizable KV store 和 shared file-system page cache。page cache 将 `(inode,block)` 视为 4 KB object，dirty bit 仍在 SCR，转 read-shared 前先 writeback。failure model 是任一 host/CXL failure 让全系统 fail；KV store 不持久化（§4–§5）。

## 设计取舍

- **local DRAM 换 SCR capacity**：每 host 复制大 index，换掉 HCMeta 的 SCR bottleneck；总 metadata 随 host 数线性增长。
- **eventual replica sync 换 read-path检查**：read index 前可能 replay log，burst mutation 会增加 tail latency。
- **动态 record 换 protocol复杂度**：allocation/deallocation/counter wrap 都需第二 coherence path，正确性比固定 record 更难。
- **粗粒度 object coherence**：适合 DB row/KV/page，不追踪 object 内 false sharing；应用必须通过 pre/post API。
- **failure 边界**：没有 host isolation 或 durable KV recovery，不能直接作为 fault-tolerant shared store。

## 实验与结果

- 因无 commercial CXL 3.0，使用 4-socket Xeon Gold 6418H [[NUMA|NUMA]] emulator：node 0 模拟 CXL，node 1–3 为 host、各 24 cores/64 GB local DRAM；SCR 默认 200 MB，KV object 默认 1 KB（§6）。
- 18M-object read-only Zipf 0.99 下 Megalon 因不分配 record、无 churn，large dataset throughput 相对 HCMeta 最高 15.26×（图 4/5）。
- 24M objects 下，5% write 时相对 HCMeta 约 10.11×，50% write 时约 4.22×；200 MB SCR 可为约 50M read-write objects 保留 record，是 HCMeta无 churn capacity 的 12×（图 6）。
- 即使 Megalon record 也不 fit SCR，它仍因 churn 次数更少且每次 churn 低 8.19× cost，整体比 HCMeta 高 2.5×–14.9×（§6.4、图 8）。
- coherence record 从 32 bits 缩到 8 bits 后 throughput最高改善 6.29×；把所有 metadata 都经 log replica 的 AllLog 在 50% write 下比 Megalon低 4.14×，支持 split mechanism（图 10/13）。
- YCSB A/B/C/D/F 相对 HCMeta 分别高 3.93×、9.12×、14.18×、4.55×、3.18×；48 GB page cache 的 write-heavy/read-heavy/read-only 高 1.88×、4.47×、5.68×（图 14/15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| split metadata 避免 large dataset 的 HCMeta churn | 图 5/6 | NUMA-emulated CXL、200 MB SCR、1 KB KV | 强 |
| dynamic record 在 SCR不足时仍优于 unshare/reshare | §6.4、图 8 | synthetic Zipf read-write，多种 skew/write ratio | 强 |
| frequently updated record 应留 SCR 而非全走 log | 图 13 | 18M objects、read-only/5%/50% writes | 强 |
| 机制适用于标准 KV workload | 图 14 | YCSB A–F、18M objects | 强 |
| 机制可推广到 shared page cache | 图 15 | 48 GB/4 KB pages、三种 read/write mix | 中 |

## 批判性分析

### 论证链条

“大冷 index、小热 record”这一 asymmetry 清楚导出 split design；AllLog ablation 又验证不能简单复制全部 metadata。read-only、write、Megalon自身也 churn、key size、record size、YCSB/page cache覆盖较完整。论文真正解决的是 metadata capacity/churn，不是一般 CXL coherence或 fault tolerance。

### 假设压力测试

NUMA emulator 无法复现 CXL fabric switch、device-side snoop filter、link retry 与真实 SCR/LNR latency/bandwidth asymmetry。insert/delete-heavy workload 会让 log/index replication变热；8–16 node 之外 tail contention和每 host replay可能扩展不良。read/write mode oscillation会频繁 allocation transition，依赖 eviction policy 的稳定性。

### 实验可信度

baseline 包括 HCMeta、local、unlimited SCR，能隔离 churn；micro 到 YCSB/page cache且数字明确。但硬件尚不存在，核心 hardware assumption 只能模拟；三 host 远小于预期 fabric规模，未报告 p99、log lag、cache-flush stall 和多 writer hotspot。SCR capacity固定 200 MB 的结论对 vendor implementation敏感。

### 系统性缺陷

fail-stop 时任何 host/CXL failure 让全系统停止，KV 无 checkpoint；shared tail、log 与 replica version 都是 recovery-critical state。application 要正确调用 pre/post hook，绕过 library 的 raw pointer access 会破坏 linearizability。log wrap/reclamation、slow host、host加入/离开和 replica bootstrap 未充分讨论。

## 局限与后续工作

- **局限 1**：只在 NUMA emulation/3 hosts 评测，真实 partly coherent CXL 尚不可用。
- **局限 2**：index replica memory 与 log replay 随 host 数线性增长，当前目标 8–16 nodes。
- **局限 3**：全系统 fail-stop、KV不持久化，缺少高可用与 recovery protocol。
- **后续工作 1**：在 CXL prototype/emulator 中分别控制 SCR latency、LNR cache behavior 与 fabric contention，复现实验并报告 p99。
- **后续工作 2**：实现 sharded/multi-log 与 partial index view，在 3→64 hosts 上测 tail contention、replica lag 与 memory。
- **后续工作 3**：注入 host crash/slow replica/log corruption，设计 durable tail、log [[Garbage-Collection|GC]] 与 replica rejoin，验证 linearizability。

## 相关

- **相关概念**：[[CXL]]、[[Cache-Coherence]]、[[Shared-Memory]]、[[Replicated-Index]]、[[Write-Ahead-Log]]
- **同类系统**：[[Tigon]]、[[Node-Replication]]、[[DudeTM]]
- **同会议**：[[OSDI-2026]]
