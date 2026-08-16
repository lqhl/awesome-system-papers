---
type: paper
name: Megalon
full_title: "Megalon: Efficient Data Sharing for Partly Coherent CXL Memory"
authors: [Jiyu Hu, Seokjoo Cho, Landon Johnson, Kiran Hombal, Shreesha Gopalakrishna Bhat, Marcos K. Aguilera, Ramnatthan Alagappan, Aishwarya Ganesan]
venue: OSDI
year: 2026
tags: [cxl, memory-coherence, shared-memory, key-value-store, page-cache]
source_pdf: "[[osdi26-hu-jiyu.pdf]]"
source_md: "[[osdi26-hu-jiyu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 在部分一致 CXL 内存上高效共享数据（OSDI 2026）

> **原题**：Megalon: Efficient Data Sharing for Partly Coherent CXL Memory

> **一句话总结**：MEGALON 针对一种尚未商品化、但被论文预计会出现的 [[CXL]] 形态——TB 级内存里只有数百 MB 具备硬件缓存一致性——把“大而冷”的对象索引复制到各 host DRAM，只把“小而热”的一致性记录留在小一致区，并用 LNR 共享日志处理索引顺序和记录切换；在三 host 的 NUMA 模拟器上，大数据集实验相对 HCMeta 提高 3.18–15.26 倍，但真实 CXL fabric、故障恢复和更多节点仍未验证。

## 问题与动机

CXL 3.x 允许多个 host 对同一外部内存直接 load/store。论文采用的硬件前提是：总内存可以达到数 TB，但 snoop filter 和 back-invalidation 难以覆盖全部地址，厂商最终只会给数百 MB 提供硬件缓存一致性。论文把这部分叫小一致区（small coherent region，SCR），把剩余的大非一致区叫 large non-coherent region（LNR）。数据放在 LNR 时，一个 host 写完后，另一个 host 的 CPU cache 可能仍保存旧值。

已有 HCMeta 方法把对象放在 LNR，把每对象一致性记录和 `key → object/record location` 索引都放在 SCR。[[Tigon-OSDI25|Tigon]] 就这样共享跨分区 tuple。问题是索引含 key 和指针，比锁与 counter 大得多；对象数量增加后，metadata 先挤爆 SCR。系统只能反复取消共享旧对象，再共享新对象，产生 churn。论文复现实验中，Tigon 在 20% cross-host transaction 下把数据集从 2.4M 增到 24M rows，吞吐下降约 10 倍（§2、图 1）。

MEGALON 不试图让整个 LNR 获得透明硬件一致性。它提供的是粗粒度对象共享库：应用把 1–4 KB 的 row、KV、blob 或 file page 作为对象，并通过库的 read/write 边界访问。它要解决的是“SCR 放不下线性增长的 metadata”以及由此产生的 churn，而不是任意指针、任意 cacheline 都透明一致的通用共享内存。

## 关键观察 / 隐含假设

- **观察 1：metadata 的两部分有相反特性。** 索引包含 object ID 和位置，体积大，但通常只在 create/delete/move 时更新；一致性记录只有 lock、free bit 和 counter，体积小，却在每次写时更新（§3.1–§3.2）。
  - **依赖假设**：普通 read/write 远多于索引 mutation。若工作负载频繁 insert、delete 或 relocation，共享日志会进入主路径。
  - **可能失效场景**：短命对象流、queue、日志型 KV 或大规模 rebalance 会使“大而冷的索引”变成大而热。
- **观察 2：只读共享对象不需要 per-object writer 状态。** 因此 SCR 容量可以由全数据集对象数，改为约束“近期被写的共享对象数”（§3.4.1、图 3）。
  - **依赖假设**：read-shared 与 read-write-shared 的每次转换都能被所有 reader 观察，并触发正确的 cache flush；只看转换前后的当前指针不够。
- **观察 3：一个有硬件一致性的 log tail 足以排序索引变化。** log entry 可放在 LNR，用 non-temporal access 或显式 flush；host 看到 SCR tail 前进后再 replay（§3.3）。
  - **依赖假设**：共享 tail 不成为争用点，慢 replica 能追上日志，LNR 写入在 tail 所定义的顺序中正确发布。
- **假设 1：每个 host 都能保存完整索引副本，系统规模主要是 8–16 nodes。** 论文指出当前 local-memory footprint 会随节点数增长，并把 partial view、索引分片和多日志留作扩展方案（§4）。
  - **证据强度**：弱到中。实际评测只有三个模拟 host，没有展示 8–16 nodes 的 tail contention、replay lag 或内存成本。

## 核心方法

MEGALON 的一致性记录包含 lock bit、free bit 和默认 30-bit counter。writer 先拿锁，把 counter 加一成为奇数，写 LNR 对象并 flush 自己的 cacheline，再把 counter 加一成为偶数并释放锁。reader 在读前后各取一次 counter；若读到奇数、两次不等，或本 host 保存的旧 counter 与当前值不等，就 flush 对象 cacheline 并重试。这类似 sequence lock：锁只串行 writer，reader 用前后检查发现并发写。每个 host 还保存每对象最近成功读取的 counter，以判断自己的 cache 是否可能过期（§3.1）。

split metadata 把索引变成每 host local DRAM 中的 hashmap，entry 指向 LNR 对象和可选的 SCR record；SCR 不再保存 key。以 100 MB SCR、40-byte key、4-byte record 为例，MEGALON 可保存约 25M records，而 HCMeta 每对象至少 52 bytes，只能覆盖约 1.9M 对象。local lookup 也比访问共享 SCR 索引延迟低、争用少，代价是每台机器都保存完整副本（§3.2、图 2）。

索引副本通过修改后的 [[NUMA]] Node Replication 共享日志保持一致。update 先以 CAS 预留 tail，再向 LNR circular log 写 entry；各 host 在读本地索引前检查 SCR 中的 head/tail，并 replay 尚未应用且已经写完整的 entry。日志只用于复制，不用于故障恢复；各 replica 都越过某 entry 后才推进 head 回收空间。每 host 的 update 还会 flat-combine，由一个线程追加，减少 tail 争用（§3.3、§4）。

对象创建时默认没有 record。第一次写要从 SCR 找 free record，并通过日志把指针写进所有索引副本；如果两个 host 竞争，日志顺序中的第一个成功，另一个释放自己多分配的 record。SCR 接近水位线时，后台线程随机采样并选择 counter 最低的 record 回收，把对象降为 read-shared。稳定期间，一致性走 record 快路径；allocation、deallocation、create 或 delete 期间则走第二条日志路径：host replay 事件时 flush 对应对象，正在进行的 read 还要检查其开始与结束之间是否发生过事件，否则“无 record→写入→又无 record”的 ABA 式变化会漏掉（§3.4）。

共享日志还支持三个优化。第一，record 可缩短；counter wrap 时写一条日志，令各 host flush，避免新旧 counter 相同。第二，索引可指向某 host 的 local DRAM；连续 `n` 次由同一 host 访问后把对象移回本地，远程访问再用 RPC 搬回 CXL。第三，read-shared 对象可在多个 host 保留本地副本；写入时通过日志把索引收敛到唯一 CXL copy，逻辑失效其他副本（§3.5）。

实现是约 8 KLoC C++ library，暴露 `read_start/read_end`、`write_start/write_end`、create 和 delete。KV store 提供 linearizable put/get；共享 page cache 把 `(inode, block-number)` 作为 4 KB 对象，并另在 SCR 保存 dirty bit。对象 slot 大小是编译期固定值。故障模型很弱：任何 host 或 CXL memory 失败都让整个系统失败；KV 不做 checkpoint，只有 page cache 可依靠文件系统和已经 `fsync` 的数据恢复（§4–§5）。

## 设计取舍

- **local DRAM 换 SCR 容量**：完整索引副本让 SCR 只随活跃写集合增长；代价是每 host 的 hashmap、host-side counter 和 replay 工作，节点越多总体成本越高。
- **共享日志换同步 RPC**：mode switch 不必等待所有 host ACK，churn 更便宜；代价是 read 前 tail check、事件订阅、log reclamation 和慢 replica 管理。
- **动态 record 换协议复杂度**：读多工作负载几乎不占 SCR；create/delete、record 切换和 counter wrap 都必须走 dual-path coherence，正确性状态空间明显大于固定 record。
- **应用显式边界换粗粒度性能**：1–4 KB 对象可少做 cacheline metadata；任何绕过 library 的裸指针访问都不受协议保护，动态大小对象也尚未实现。
- **可用性换简单实现**：log 是复制机制而不是恢复日志，系统没有 host 隔离、leader recovery、replica rejoin 或持久 KV 语义。

## 实验与结果

- 因 commercial CXL 3.0 尚不可用，实验在 4-socket Xeon Gold 6418H 上模拟：NUMA node 0 充当 CXL，node 1–3 各作为 24-core、64 GB DRAM 的 host，并降低 node 0 uncore frequency 模拟延迟；默认是 1 KB KV、200 MB SCR。baseline 为 HCMeta、带 local partition 的 HCMeta-local 和不现实的无限 SCR 版本（§6 Setup）。
- read-only、Zipf 0.99 下，MEGALON 不分配 record。数据集从约 2M 增到 24M objects 时吞吐维持约 24 MOps/s；24M 点相对 HCMeta 提高 15.26 倍，延迟约 1 μs，而 HCMeta/HCMeta-local 因 churn 升到约 26–34 μs，后者还多出数据搬移成本（§6.1–§6.2、图 4、图 5）。
- 24M objects 的 5% write 和 50% write 下，MEGALON 相对 HCMeta 吞吐分别提高 10.11 倍和 4.22 倍；200 MB 可容纳约 50M 个 4-byte records，是 HCMeta 无 churn 容量的 12 倍。把 18M 数据集的 SCR 继续缩小时，MEGALON 自己也 churn，但整体仍快 2.5–14.9 倍；5% write、高 skew、64 MB SCR 的一个点是 11 倍（§6.3–§6.4、图 6、图 7）。
- 一次 MEGALON churn 只分 record 并写日志，开销比 HCMeta 的 owner RPC 低 8.19 倍；10–90 byte key 只扩大 local index，不影响 SCR，而 HCMeta throughput 随 key 变大下降。24M objects 时 MEGALON 总内存 27.71 GB，比 HCMeta 的 25.76 GB 高 7.6%，吞吐却是 24.4 对 1.6 MOps/s，单位 GB 吞吐高 14.19 倍（§6.4–§6.6、图 8、图 9）。
- 最坏的 32 MB SCR、50% write、低 skew 设置中，把 record 从 32 bits 缩到 8 bits，让吞吐提高 6.29 倍；再缩会因 wrap log 变多而下降。把全部 metadata 都经日志复制的 AllLog 在 50% write 时比 split design 慢 4.14 倍，直接支持“热 record 应放 SCR”的判断（§6.7、§6.10、图 10、图 13）。
- 18M-object YCSB A/B/C/D/F 上，MEGALON 相对 HCMeta 分别快 3.93、9.12、14.18、4.55、3.18 倍；48 GB、4 KB-page 的用户态 page cache 在 write-heavy/read-heavy/read-only 下分别提高 1.88、4.47、5.68 倍。read-only 本地 data copy 还比普通 MEGALON 降低 1.3 倍访问延迟（§6.9、§6.11–§6.12、图 12、图 14、图 15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| split metadata 能显著推迟 HCMeta 的容量墙 | 图 5、图 6 | 三个 NUMA 模拟 host、1 KB KV、默认 200 MB SCR | 强 |
| 只为 read-write-shared 对象分 record 能减少 churn | 图 7、图 8 | 18M objects，多种 write ratio、Zipf 0.99/0.7 和 SCR size | 强 |
| 高频一致性记录不应全部通过日志复制 | 图 10、图 13 | 18M objects；record-size 与 AllLog 消融 | 强 |
| 机制能覆盖标准 KV workload，而非单一 microbenchmark | 图 14 | 五种 YCSB、18M objects、NUMA 模拟 CXL | 强 |
| 同一抽象可用于共享 page cache | 图 15 | 48 GB 数据、4 KB pages、三种读写比例 | 中 |

## 批判性分析

### 论证链条

论文的核心分解很干净：HCMeta 的容量问题来自“大索引”和“小 record”采用了同一种物理共享方式；把两者拆开后，再用动态 record 把限制从全数据集推到写工作集。key-size 实验验证大索引不再消耗 SCR，AllLog 消融验证频繁 record update 不适合复制，SCR sensitivity 又承认 MEGALON 仍有容量墙而不是声称彻底消除。就“减少 metadata churn”这个窄 claim 而言，设计与实验相互对应。

更大的跳步在硬件前提。论文研究的是未来 partly coherent CXL；实际平台既没有 commercial CXL 3.0，也没有真实 SCR/LNR。实验只说明降低 NUMA node 0 的 uncore frequency 来近似 CXL latency，没有说明关闭普通多 socket 的硬件 cache coherence。因此吞吐能反映执行 flush、日志和 churn 的软件成本，却不能充分复现 fabric switch、LNR 的 stale-cache 行为、SCR snoop 资源、真实带宽或设备故障。

### 假设压力测试

MEGALON 最适合“大量长寿命对象、索引变化少、写工作集小于总数据集”的 workload。若对象短命、key 热插入删除、读写 mode 高频振荡，日志事件、cache flush 和 record churn 会同时增加。论文用 Zipf 0.99/0.7 和 5%/50% write 压力测试了访问分布，却没有独立扫 insert/delete rate、对象 lifetime、hot-key writer contention、watermark 或后台随机回收策略。

扩展性也依赖每个 host replay 全部索引变化。中心 tail、每副本 reader-writer lock、flat-combining 单 append thread 和完整 hashmap 在三个 host 上不一定显出瓶颈。论文把目标写成 8–16 nodes，但未实测该范围；64 nodes、慢 host、replica 暂停或日志即将绕回时需要 partial view、sharding 或多个日志，这些仍是设想。

### 实验可信度

HCMeta、HCMeta-local 和 HCMeta-Unlimited 三个 baseline 能分别隔离 SCR 容量、数据搬移和 churn，评价矩阵还覆盖 key size、SCR size、skew、write ratio、AllLog、YCSB 与第二个 page-cache 应用，机制证据完整。内存账也避免了只报吞吐、不报 replication 成本的问题。

不足是所有实验都在同一台四路服务器、三个模拟 host 上完成，且主要报告 throughput 和 average latency；论文没有给重复次数、误差条、P99 或 tail churn。对照实现是作者在自研 KV store 中实现的 HCMeta，不是把完整 MEGALON 放进 Tigon 做交易级对比；因此结果支持共享层，不直接证明 ACID database 的端到端收益。

### 系统性缺陷

正确性依赖应用严格配对 `read_start/read_end` 和 `write_start/write_end`，并正确处理 retry。API 跨越实际 data access，异常退出、长读、取消和误用都可能把对象留在危险状态；论文没有展示形式化证明、race model checking 或在真正非一致内存上做故障注入。普通 NUMA coherence 还可能掩盖漏 flush 的实现错误。

系统把任一 host 或 CXL memory failure 定义为全局失败，shared log 又明确不做 recovery。未讨论 tail/head 持久化、writer 在“预留 tail 但未写完 entry”后崩溃、慢 replica 阻止回收、节点加入退出和 index bootstrap。page cache 可以依靠 disk 恢复已 `fsync` 数据，但这不是 MEGALON 自身的高可用方案。

## 局限与后续工作

- **局限 1**：真实 partly coherent CXL 尚不可用；NUMA 延迟模拟不能验证 fabric 和非一致 cache 的全部行为。
- **局限 2**：只评测三个 host，低于论文声称的 8–16 node 目标；多节点 tail contention、replay lag 和副本内存尚无数据。
- **局限 3**：固定 slot、编译期 object size 和显式访问 API 限制应用范围；系统没有故障容忍或持久 KV。
- **后续工作 1**：在真实 CXL prototype 或能关闭 host coherence 的 emulator 上，对转换、删除、counter wrap 注入并发 race，并用 linearizability checker 验证结果。
- **后续工作 2**：把 host 数从 3 扩到 16/64，分别扫描 insert/delete rate、slow replica 和 hot key，报告 tail contention、log lag、P99 以及 head 无法回收的时间。
- **后续工作 3**：实现 sharded index、multi-log 与 replica rejoin；对 append 中途 crash、CXL device reset 和 log corruption 给出可恢复协议。

## 相关

- **相关概念**：[[CXL]]、[[NUMA]]、[[Cache-Coherence]]、[[Replicated-Index]]、[[Shared-Log]]
- **同类系统**：[[Tigon-OSDI25]]、Node Replication、HCMeta
- **同会议**：[[OSDI-2026]]
