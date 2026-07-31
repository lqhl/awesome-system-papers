---
type: paper
name: Duhu
full_title: "Duhu: Shared Disaggregated Memory for Distributed Data Processing Frameworks"
authors: [Qiutong Men, Tao Wang, Jongryool Kim, Hane Yie, Emmanuel Amaro, Marcos K. Aguilera, Aurojit Panda]
venue: OSDI
year: 2026
tags: [cxl, disaggregated-memory, distributed-data-processing, object-store, ray]
source_pdf: "[[osdi26-men.pdf]]"
source_md: "[[osdi26-men]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向分布式数据处理框架的共享解耦内存

> **原题**：Duhu: Shared Disaggregated Memory for Distributed Data Processing Frameworks

## 一句话总结

Duhu 在无跨主机硬件 coherence 的 CXL shared disaggregated memory 上提供 immutable pass-by-reference object store：数据由 worker 直接 load/store，mutable metadata 由 segment owner 串行管理；Ray FlexShuffle 的四阶段 job 最多提速 3.39 倍。

## 问题与动机

Ray、Spark 等 DDF 以 in-memory object store 解耦 producer/consumer，却仍采用 pass-by-value：consumer 必须把 immutable intermediate object 经网络复制到 local memory，再 serialization/deserialization。多 consumer 时同一 object 被复制多份，浪费 CPU、network 和容量。

Shared disaggregated memory（SDM）允许多个 host load/store 同一 CXL memory pool，理论上可传 reference；但现有 CXL 2.0 Type-3 blade 没有跨 host cache coherence。未来全局 directory coherence 又有“coherence tax”：write 等最慢 sharer invalidation、每 cache line 有协议 bandwidth、petabyte memory 的 directory storage/complexity 难扩展。Duhu 选择在 software-defined incoherent SDM 上承担最小 coordination，并保持 DDF API/调度/lineage fault tolerance 基本不变。

## 关键观察 / 隐含假设

### 关键观察

- DDF object data 写一次后 immutable、访问频繁且体积大；metadata（location、reference bitmap、allocator）可变、较小且访问少，二者应使用不同 coherence 策略。
- 让每个 segment 只有一个 metadata owner，可用 message passing 代替跨 host coherent locking，避免共享 mutable cacheline。
- immutable data 只需 creator 用 non-temporal write 落到 SDM，reader 第一次取得 reference 前 invalidate cache；之后可无协调直接读取。
- shuffle 的逻辑重分区可只改 metadata/reference，不必反复物理搬 intermediate data。

### 隐含假设

- DDF object immutable，且已有 lineage/recomputation 能恢复 memory-blade 丢失的数据。
- 所有 node 将 segment 映射到相同 virtual address，pointer 可直接跨 worker 使用；运行环境足够统一。
- SDM latency/bandwidth（原型 600–800 ns、约 10 GB/s）适合避免复制或 partial access，不适合所有小/hot object。
- orchestrator 能可靠检测 node/blade failure 并通知 Duhu；node failure 不损坏 SDM 内容。

## 核心方法

### Segment ownership 与 Duhu-RM

SDM 被切成 segment，每个 segment 的 channel、WAL、metadata hash map 和 data 同 fate，且恰有一个 node owner。各 node 上 Duhu Reference Manager（Duhu-RM）提供类 KV API：`CreateObj`、`GetObj`、`GetID`、`DropRef`；cluster-wide ID 编码 segment，node-local `DuhuPtr` 可直接解引用。非 owner 的 metadata operation 通过 RPC 请求 owner，同一 object 的请求固定 dispatch 到同一 thread 保序。

object creator 先在 local memory 构造，再异步以 cache-line-aligned non-temporal write 写 SDM并 fence。`GetObj` 在返回 pointer 前 invalidate 对应 local cacheline，防止读到该地址之前 object 的 stale cache。各 node 的 reference 由 bitmap/count 维护，只有全部 `DropRef` 后才回收；DuhuPtr destructor 可自动释放。

### Duhu-Channel

每对 client/server 用 SDM 中 cache-line-sized ring slot 传少于 63 B 的 request/response，ownership bit 标示当前端，version bit 用于 recovery；request 与 response 共用 slot 降低 working set。因为 incoherent write 不能唤醒另一 host，active channel 轮询 SDM，idle 后 backoff；sender 再用传统 network message 仅作 notification。数据平面走 SDM，信号平面走网络。

### 故障恢复

每个 metadata RPC 在修改前写/flush segment WAL，operation 设计为 idempotent。owner node failure 后新 owner 扫 metadata 重建 allocator，按 channel 回放最后 `k` 条 WAL；slot version 与 WAL version 相同才说明 client 尚未复用 slot。`GetRef/DropRef` 的 bitmap 操作天然幂等，allocation 通过 object ID 查表避免重复；其他 owner 清除失败 node 的 reference bit。

memory blade failure 使同 segment data/metadata 一起丢失，DDF lineage 重算；残留 pointer 访问触发 SIGBUS，Duhu 转入 DDF unavailable-object handler。恢复关键路径主要受 metadata dictionary scan 与 WAL replay 的 SDM access 限制。

## 实现与集成

Duhu 以 C++ 实现并修改 Ray 单个 object-manager module：远端访问时才把 sealed local object lazy 搬到 SDM，`GetRef` 返回 SDM pointer，`FreeObject` 调 `DropRef`。只在 local consumer 使用的 object 不会无谓进入慢 SDM。作者还修改 Modin 并实现 FlexShuffle。

## 实验与结果

**证据定位**：§8.2–§8.3、图 6–15；包括 shuffle、TPC-H、RPC、fan-out 与 partial-access benchmark。

四 node CXL SDM prototype 上，作者比较 vanilla Ray/Exoshuffle、Duhu-Ray/FlexShuffle，并用 [[NUMA|NUMA]] 模拟更快未来硬件。

- 32 map/32 reduce、4 个 shuffle stage、8–64 GiB data 下，FlexShuffle JCT 最多提高 3.39 倍；第一 reduce 要初次复制到 SDM，后续 stage 因仅 metadata 重组快 3.59–13.81 倍。
- 64 GiB case 初次复制占主导，FlexShuffle 反而慢 1.01 倍，清楚显示 break-even boundary。
- 无 SDM 而在各 local store 保留 reference 所需副本会 spill SSD，单 shuffle stage JCT 高 13.34–24.69 倍。
- 更快 NUMA-SDM emulation 比 CXL FlexShuffle 再快 1.10 倍，并始终比 Exoshuffle 快 2.43–5.79 倍。
- Modin TPC-H 平均提速仅 1.08 倍，最佳 query 平均 1.26 倍、最高 1.30 倍；小于 10 s 且 fit local store 的 query 最坏慢 1.2 倍。
- fan-out 时 Duhu-Ray blocking time 低 2.80–4.29 倍，因为 Ray 要向 3 个 server 各复制一份。
- 只读取 array 的 1/10000 时，Duhu JCT 比全量读取低 4.45 倍；Ray 因传输全 object 几乎不变。但真正 compute 时 local Ray 可只用 Duhu 的约 0.29 倍时间。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| pass-by-reference 可消除 shuffle 重复搬运 | 后续 reduce stage 快 3.59–13.81 倍，四阶段 JCT 最多 3.39 倍 | 首次 object 仍须复制到 SDM，单阶段/大数据可无收益 | 强 |
| incoherent SDM 也可安全共享 immutable object | non-temporal publish、first-read invalidate、owner metadata、WAL recovery | 正确性依赖 immutable API 与 cache instruction 语义 | 强 |
| 可较小改动集成现有 DDF | Ray 改动集中在 object manager，应用不变 | FlexShuffle/Modin 为发挥新语义仍需框架/应用优化 | 强 |
| Duhu 适合 partial/fan-out access | fan-out blocking 降 2.80–4.29 倍；partial JCT 随读取比例降低 | 对全量 sequential compute，SDM 比 local DRAM 慢 | 强 |
| 新硬件会扩大收益 | NUMA emulation 比原型快 1.10 倍且胜 Exoshuffle 2.43–5.79 倍 | NUMA 并非真实多 host CXL fabric，属于推断 | 强 |
## 批判性分析

### 论证链条

Duhu 对 coherence 的切分很干净：高带宽 immutable data 直接共享，小而 mutable metadata 单 owner 协调；避免为所有 cacheline 支付 global coherence tax。channel 把 SDM 当 payload medium、network 当 doorbell，是贴合硬件限制的混合设计。评估没有隐藏负结果，明确展示初次复制、小 query 与 local compute 边界。

### 假设压力测试

- prototype 只有 4 nodes，segment owner、channel polling、network notification 与 recovery 在数十/数百 node 的 scalability 未验证。
- reference counting 依赖所有 DDF path 正确 DropRef；partition 或 leaked process 可能延迟回收，node failure 清 bitmap 又依赖 orchestrator accuracy。
- shared pointer/identical virtual mapping 限制语言 runtime、heterogeneous node 与 process isolation；并非所有 object 可零拷贝消费。
- object 必须 immutable，mutable dataset、iterative in-place update 或 transactional state 不适用。
- TPC-H 平均仅 1.08 倍且小 query 慢 1.2 倍，实际系统必须有 local/SDM hybrid placement，而论文策略较初步。
- SIGBUS 与 DDF lineage 的跨层恢复虽合理，但 node/blade failure experiment 与恢复时间数据不足。

### 实验可信度

真实四节点 CXL prototype、Ray/Modin 与未来 NUMA emulation 揭示了正负边界；但 scale 较小、failure recovery 缺少实测，且 NUMA 不能替代真实跨 host fabric。

## 局限与后续工作

- **局限**：immutable object、固定 virtual mapping 与小规模 owner/channel 架构限制适用面。
- **后续工作**：应实现 hybrid replication/placement，并在更大 CXL fabric 上实测 hotspot 和 failure recovery。

后续应实现 size/fanout/reuse-aware local replica policy；扩展到更大真实 CXL fabric并评估 owner hotspot；优化 recovery metadata layout；支持 controlled replication 与 read caching；用 capability/offset handle 替代固定 virtual pointer以改善隔离；并在 Spark/ML pipeline 和多租户 workload 中验证 memory saving、tail latency 与 failure recovery。

## 相关概念

- [[CXL]]
- [[Disaggregated-Memory]]
- [[Object-Store]]
- [[Ray]]
- [[Data-Shuffle]]
