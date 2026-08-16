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
last_reviewed: 2026-08-14
---

# Duhu：让分布式数据处理框架直接共享解耦内存（OSDI 2026）

> **原题**：Duhu: Shared Disaggregated Memory for Distributed Data Processing Frameworks

> **一句话总结**：Duhu 把 Ray 一类框架的不可变中间对象放进所有 worker 都能直接 load/store 的共享解耦内存（shared disaggregated memory，SDM）；大对象只存一份、传递引用，可变 metadata 则交给单一 segment owner 管理，因此即使跨主机没有硬件 cache coherence，也能避免重复网络复制，并让四阶段 FlexShuffle 最多缩短 3.39 倍 JCT。

## 问题与动机

Ray、Spark 等分布式数据处理框架（DDF）会把 task 的不可变中间结果放进 object store。这样 producer 和 consumer 不必同时运行，scheduler 可以灵活放置 task，node 失败后也能根据 lineage 重算对象。但现有系统仍是传值（pass-by-value）：远端 consumer 必须先把整个对象经网络复制到自己的 local memory，再开始处理（§1–§2.1）。

当一个大对象被多个 worker 消费时，这个模型同时浪费三类资源：网络要重复传相同 bytes，CPU 要做 serialization/deserialization，内存要保存多份副本。对象若大于 local object store，还会 spill 到 SSD。Ray 的 RPC 虽然可以只传 object ID，但 handler 最终仍会从 object store 拉一份本地 copy，所以它只是“消息里传 reference”，不是“计算直接访问同一份数据”。

[[CXL]]、OpenCAPI 一类 SDM 让多个 compute node 用普通 load/store 访问外部 memory blade，看起来可以直接传 pointer。但 Duhu 刻意不依赖跨主机全局 cache coherence。当前 CXL 2.0 Type-3 memory expander 没有这种能力；未来 directory coherence 也会付出论文所谓的 coherence tax（§2.2–§2.3）：

- writer 要等所有 sharer 的 invalidation ACK，最慢 node 决定尾延迟；
- 每个 cache line 都带额外 coherence traffic，即使对象写一次后再也不改；
- petabyte 级 memory pool 若逐 cache line 维护 directory，会消耗大量 SRAM，并增加 fabric 复杂度。

Duhu 的问题因此不是“如何再实现一套通用 shared memory”，而是“能否利用 DDF 对象的特殊语义，只为真正可变的部分协调”。

## 关键观察 / 隐含假设

- **观察 1：object data 与 metadata 的行为完全不同。** data 很大、读取频繁，但创建完成后 immutable；location、reference bitmap、allocator 和 recovery state 很小，却会不断变化。Duhu 直接共享前者，只协调后者（§3.1）。
  - **依赖假设**：对象只能 write once，`CreateObj` 完成后任何 worker 都不能原地修改它。mutable tensor、in-place dataframe 或 transactional state 不适用。
- **观察 2：incoherent memory 的 stale cache 问题只在 publish 和地址复用时出现。** creator 用 non-temporal write 把完整对象写到 SDM；reader 第一次取得该地址时先 invalidate 本地 cache line。对象之后不变，就无需每次读取都同步（§4.1）。
  - **依赖假设**：CPU 的 non-temporal instruction、cache invalidation 与 fence 对外部 memory 的语义正确，并且对象按 cache line 对齐。
- **观察 3：每个 segment 只有一个 metadata owner，比跨 node lock 更简单。** 非 owner 通过 RPC 请 owner 修改 metadata，避免多个 incoherent CPU cache 同时写一个 hash map（§4）。
  - **依赖假设**：orchestrator 能及时、唯一地重新分配 failed owner，不会同时产生两个 active owner。
- **观察 4：shuffle 常常只改变逻辑分区，不必搬动底层数据。** 如果 reducer 可以拿到“原对象 reference + offsets/lengths”，后续 stage 只重组 slice metadata（§8.2.1）。
  - **依赖假设**：consumer 能接受 scatter/gather 风格的 slice access；若算法需要完整连续 local array，仍可能复制或承受 SDM latency。
- **观察 5：DDF 已经知道何时放弃 local object reference。** Duhu 把现有 garbage-collection path 接到 `DropRef`，可在最后一个 node 放弃引用后回收唯一的共享 copy（§4.2）。
  - **依赖假设**：所有代码路径都正确释放 reference，node failure 也能由 orchestrator 通知其他 owner 清理 bitmap。

## 核心方法

### segment、ID 与 Duhu-RM

Duhu 把 SDM 划成 segment。每个 segment 包含四个同生共死的区域：Duhu-Channel ring、write-ahead log（WAL）、metadata hash map 和 object data。metadata 记录 object address、size 以及哪些 node 持有 reference；object 与 metadata 放在同一 memory unit，blade failure 时一起丢失，恢复不需要合并跨 unit 状态（§3.2、§4、图 3）。

每个 compute node 运行一个 Duhu Reference Manager（Duhu-RM），每个 segment 在任一时刻至多有一个 owner。owner 可以直接读写该 segment 的 metadata；其他 node 必须通过 Duhu-Channel 调 owner 的 `Alloc`、`GetRef`、`DropRef` 等 RPC。同一个 object 的请求总是 dispatch 给同一 thread，从而保持与 WAL 相同的执行顺序（§3.2）。segment 把“中央 metadata manager”拆散到多个 node，但一个 segment 内仍然串行归属单 owner。

DDF 看到的 API 类似普通 immutable object store：`CreateObj`、`GetObj`、`GetID`、`DropRef`。cluster-wide `ID` 编码 object 所在 segment，用于路由；node-local `DuhuPtr` 才能直接解引用。所有 node 把 SDM segment 映射到相同 virtual address，所以 pointer 不需再做 address translation。`DuhuPtr` destructor 自动调用 `DropRef`；reference 归零后 owner 才回收空间（§3.2.1、§4.2、图 2）。

### 安全地直接读取 object data

worker 先在 local memory 中完整构造 object，再调用 `CreateObj`。Duhu 分配 cache-line-aligned SDM space，并用 non-temporal store（例如 `_mm512_stream_si512`）异步复制，最后用 store fence 保证 publish 前数据已经到达 SDM。复制完成前，其他 worker 不会获得 reference（§4.1）。

地址以后可能被另一个新对象复用，而 reader 的 CPU cache 里还留着旧对象 bytes。`GetObj` 因此在返回 `DuhuPtr` 前 invalidate 覆盖该对象的 local cache lines。之后对象 immutable，同一 reader 可以直接 load，不需要跨 node coordination。这个协议只解决一致性，不会把 SDM 变成本地 DRAM：原型访问延迟为 600–800 ns、带宽约 10 GB/s，所以全量顺序计算仍可能更慢。

### Duhu-Channel

Duhu-Channel 是一条连接两个 Duhu-RM 的 client/server RPC channel（§5、图 5）。它在 SDM 中放一个由 64-byte、cache-line-aligned slot 组成的 ring，最多同时容纳 `n-1` 个 request。每个 slot 含：

- ownership bit（`OBit`），表示现在由 client 还是 server 读写；
- version bit（`VBit`），用于 crash replay 时判断 slot 是否已被 client 复用；
- size 与少于 63 bytes 的 request/response payload。更大数据未来可传 SDM reference。

多个 client thread 用 CAS 移动 `CHead` 并预留 slot，再用 non-temporal write + fence 发布 request。server 按 `SHead` 轮询、invalidate 对应 cache line、读取 request 并 dispatch；response 写回同一个 slot，减少 working set。持续 polling 会抢 SDM bandwidth，所以 channel 空闲一段时间后停止轮询；下一次 sender 用普通 network message 只做 doorbell notification。也就是说，payload 走共享内存，唤醒走网络，因为 incoherent SDM write 本身不能触发另一台机器的 `MWAIT`（§5.1）。

### node 与 memory-blade 故障

每个 metadata RPC 在执行前先写入并 flush WAL，接口本身设计成幂等。owner node 失败后，orchestrator 把 segment 交给新 owner。新 owner 先扫描 metadata hash map，重建 object set 与 allocator free list；再按每条 channel 取最近 `k` 个 WAL entry，因为 ring 最多只有 `k` 个 outstanding request（§6.3.1）。

重放前，新 owner 比较 WAL 中的 `VBit` 和当前 slot：相同表示 client 尚未复用 slot，仍可能在等 response；不同则丢弃旧 entry。`GetRef`/`DropRef` 对 bitmap 的位操作天然幂等；`CreateId` 重放时返回 WAL 里已经生成的 key；`Alloc` 先按 object ID 查 metadata，避免重复分配。其他 segment owner 同时清除 failed node 持有的 reference bit，防止永久泄漏。

memory blade failure 会让该 unit 上的 data 与 metadata 都消失。Duhu 不复制 object，而是依赖 Ray/Spark 的 lineage recovery 重算。若某个 worker 仍解引用指向 failed blade 的 `DuhuPtr`，操作系统应产生 `SIGBUS`，Duhu 捕获后调用 DDF 的 unavailable-object handler（§6.2）。这把容错责任明确分给 DDF，但也要求 OS、orchestrator 与 framework 三层配合。

论文没有实测 recovery latency。§6.3.2 只分析它主要由 metadata dictionary scan、每 channel 最近 `k` 条 WAL 的查找与 replay 决定；这些步骤都受 600–800 ns SDM read、cache invalidation、non-temporal write 和 fence 限制。

### Ray 集成与 FlexShuffle

Ray 集成只修改 object manager module：`PushLocalObject` 在需要远端访问时才 lazy allocate/copy 到 SDM，`GetRef` 返回 SDM pointer，`FreeObject` 接到 `DropRef`。只被 creator 本地使用的 object 保持在 local memory；local store 出现 pressure 时也可以搬到 Duhu（§7）。应用代码无需改变，但要利用 FlexShuffle 的新执行方式仍需修改 shuffle operator。

Exoshuffle 的 mapper 先物理切分 output，每个 reducer 再把自己的 partition 拉到 local store。FlexShuffle 的 mapper 把一份未分区 output 放入 Duhu，只为每个 partition 生成 offsets/lengths 组成的 slice；reducer 用 slice 直接访问原 object。多阶段 shuffle 中，第一阶段仍要把初始 data 搬到 SDM，后续阶段只产生新 slice，避免再次传整个 intermediate data（§8.2.1）。

## 设计取舍

- **不做 global coherence 换显式软件协议**：bulk immutable data 不付 directory tax；publish、first read、metadata update、recovery 都必须正确使用 cache instruction 与 fence。
- **单 segment owner 换简单一致性**：metadata 不需 distributed lock；owner hot spot、channel 数量和 failover scan 可能限制大规模 cluster。
- **唯一共享 copy 换较慢的计算访问**：fan-out、partial read 和 memory pressure 受益；小对象、短 query、顺序扫描更适合 local DRAM。
- **reference counting 换显式生命周期**：可安全回收共享地址；漏掉 `DropRef`、orchestrator 误报或 network partition 都会影响空间安全或可用性。
- **固定 virtual mapping 换零 translation pointer**：DDF dereference 简单；heterogeneous address space、sandbox、多语言 runtime 和强进程隔离更难支持。
- **lineage recovery 换少副本**：正常情况省 memory；blade failure 后恢复时间取决于 DDF 重算，而且 dangling pointer 处理需要 `SIGBUS` integration。
- **lazy local-to-SDM copy 换首个远端 consumer 等待**：纯本地对象不付 SDM 成本；fan-out 的第一个 consumer 仍在关键路径等待 producer copy。

## 实验与结果

- **硬件与比较边界**：实验使用 4 台 server，每台有 4 个 Intel Xeon Gold 6530、512 GB DRAM 和 ConnectX 100 Gbps NIC；外接 128 GB FPGA CXL memory pool，延迟 600–800 ns、带宽约 10 GB/s。SDM 分为 16 个 segment，每个有 65,536 个 WAL slot；WAL+metadata 每 segment 8 MB、总计约 128 MB。container 有 12 cores/30 GB，其中 8 cores 做计算。作者把 aggregate network bandwidth 限到和 SDM 相同的 80 Gbps，且说明 local memory 在这些实验中不是瓶颈（§8.1）。
- **四阶段 shuffle 主结果**：32 map + 32 reduce task、每 instance 各 2 个 task，数据量为 8/16/32/64 GB，对应 local object store 0.75/1.5/3/6 GB。FlexShuffle 相对 Exoshuffle 最多把 JCT 缩短 3.39 倍；但在 64 GB case 中，JCT 是 Exoshuffle 的 1.01 倍，即约慢 1%，因为第一 reduce stage 把所有 data 初次复制到 SDM 的成本主导。后续 reduce stage 不再搬 data，单 stage 快 3.59–13.81 倍（§8.2.1、图 6–7）。
- **“只传 slice”需要真正的 SDM**：作者还让普通 local object store 保留所有 unpartitioned data，模拟没有 SDM 的 FlexShuffle。副本挤出内存并 spill SSD 后，即使只有一个 shuffle stage，JCT 也高 13.34–24.69 倍。用单机远端 [[NUMA]] node 模拟更快 SDM时，FlexShuffle 比 CXL prototype 再快 1.10 倍，并比两节点 Exoshuffle 快 2.43–5.79 倍；该实验最多 32 GB，NUMA coherence/拓扑也不等于真实多主机 CXL，因此只能说明硬件变快后的方向（§8.2.1、图 8–9）。
- **TPC-H 收益取决于工作集**：Modin 使用 scale factor 10、3.4 GB compressed Parquet、每 node 5 GB local object store，并且每台物理 server 只运行一个 container；vanilla Ray 在 Q5 常因 OOM crash，所以作者把 Q5 排除。其余 query 平均只提速 1.08 倍；收益最大的四个 query 平均提高 1.26 倍、单次最高 1.30 倍。小于 10 s 且能放进 local store 的 query 反而受 SDM latency 影响，最慢四个平均慢约 1.2 倍（§8.2.2、图 10–11）。
- **RPC 与 fan-out microbenchmark**：Duhu-Channel 在 3 M RPS 时 latency 为 3.8 μs；[[RDMA|RDMA]] baseline 在 1 M RPS 时为 11.74 μs，但作者为公平化接口只允许 RDMA 一次一个 outstanding request，这不是高度 pipeline 的 RDMA 上界。fan-out 每组由一个 producer 生成 200 MB array、四台 server 各一个 consumer；16/32/64 组时 Duhu-Ray blocking time 比 Ray 低 2.80–4.29 倍，因为 Ray 要向三个 remote consumer 各传一份（§8.3.1–§8.3.2、图 12–13）。
- **partial access 的优势和计算代价同时存在**：128 task 从 6.4 GB float array 随机读取全部、`1/1000` 或 `1/10000`。在 `1/10000` case 中，图 14 的 Duhu-Ray JCT 约为 Ray 的 `1/4.45`，因为 Ray 仍先传整个 object；§8.3.3 的正文把比较对象写得含糊，但图中的 `4.45×` 对应同一访问比例下的 Duhu-Ray/Ray，而不是 Duhu-Ray partial/full。另一方面，在 `1/1000` 和 `1/10000` case 中，local Ray 的纯 compute time 约为 Duhu-Ray 的 0.29 倍，只是总 JCT 仍由 Ray 的 data transfer 主导。object lifetime 越长，Ray 后续从 local cache 复用的收益也越大；所有 consumer 读同一 small hotspot object 时，两者接近。这些结果说明没有固定赢家，部署策略要同时看 size、fan-out、reuse、access fraction 与 local pressure（§8.3.3–§8.3.4、图 14–17）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| incoherent SDM 可以安全共享 immutable object | non-temporal publish、first-access invalidation、single-owner metadata 与 WAL replay（§4–§6） | 依赖 immutable API、cache instruction、相同 virtual mapping 和准确 orchestrator；没有并发/failure checker | 中到强 |
| pass-by-reference 能消除多阶段 shuffle 的重复搬运 | 四阶段 JCT 最多缩短 3.39 倍，后续 stage 快 3.59–13.81 倍（图 6–7） | 第一阶段仍复制；64 GB case 慢 1.01 倍；FlexShuffle 是为 Duhu 新设计的 operator | 强 |
| Duhu 可较小改动接入现有 DDF | Ray 改动集中在 object manager，application 不变（§7） | 论文未报告 LOC；FlexShuffle 和 Modin 优化仍需框架级工作 | 中 |
| Duhu 特别适合 fan-out 与 partial access | fan-out blocking 低 2.80–4.29 倍；`1/10000` 随机访问 JCT 约低 4.45 倍（图 13–15） | SDM compute 慢；small/hot/reused object 可能由 local Ray 获益 | 强 |
| 更快 SDM 会扩大收益 | NUMA emulation 比原型快 1.10 倍、比 Exoshuffle 快 2.43–5.79 倍（图 9） | 单机 NUMA 不是多主机 CXL，最多 32 GB，结论是推断 | 中 |

## 批判性分析

### 论证链条

论文最强的地方是从 DDF 对象的 immutable 语义出发，而不是先假设 SDM 应提供通用 coherence。data/metadata 分流后，直接读、reference lifetime 和 metadata RPC 三个问题都有对应机制。FlexShuffle 又展示了 pass-by-reference 不只是“把 Ray 的 copy 换成较慢内存”，还可以改变 operator：后续 stage 只改 slice。端到端 TPC-H 只有 1.08 倍平均收益，反而帮助界定了真正适用的 workload。

### 假设压力测试

若 object 会原地修改，first-read invalidation 立刻不够；若同一 virtual address 不能保留，`DuhuPtr` 也不能直接跨 node 使用。若 orchestrator 在 network partition 中错误宣布 node dead，其他 owner 会清掉它的 reference bit，随后可能回收它仍在读取的 object；论文的 failure model 默认故障通知准确，没有讨论 fencing failed-but-alive node。segment owner 也是潜在热点：大量 object 的 `GetRef/DropRef` 若集中到一个 segment，所有请求会经过一个 owner 和相应 channels。

### 实验可信度

真实四节点 CXL prototype、Ray/Modin、负面结果、microbenchmark 和 NUMA sensitivity 让性能结论比较可信。作者还限制网络总带宽匹配 SDM，避免单纯给 baseline 更差链路。不过规模只有四台 server；RDMA baseline 只允许一个 outstanding request；Q5 因 vanilla Ray crash 被排除；最重要的 node/blade recovery 没有任何时间、数据正确性或资源泄漏实验。论文只做了 recovery cost analysis，不能证明实现真的覆盖 crash timing。

### 系统性缺陷

Duhu 把原本由硬件 coherence 隐藏的责任分散到 Duhu-RM、Duhu-Channel、orchestrator、OS `SIGBUS` handler 和 DDF lineage。任何一层漏掉 fence、reference 或 failure transition 都可能产生 stale read、use-after-free 或泄漏。reference metadata 以 node bitmap 表示 sharer，也让最大 node 数、多个 process/reference 的本地聚合和动态 membership 成为必须处理的问题。固定 virtual mapping 进一步限制隔离与可移植性。性能上，系统缺少自动 local/SDM placement；论文自己的 TPC-H 和 lifetime 实验已经说明“默认放 SDM”会伤害常见小对象与重复访问。

## 局限与后续工作

- 在几十到几百 node 的真实 CXL fabric 上测 segment-owner hotspot、channel 数量、polling bandwidth、tail latency 与 metadata footprint。
- 注入 owner crash、stalled channel thread、network partition、blade removal 和 orchestrator 误判，测 recovery time、重复响应、dangling pointer 与 leaked reference。
- 给 owner reassignment 加 fencing epoch，保证被误判或恢复的旧 owner 不能继续修改 metadata。
- 设计 size/fan-out/reuse/access-fraction-aware 的 hybrid placement：small/hot object 留 local DRAM，大且被多 node 部分读取的 object 放 SDM。
- 用 offset/capability handle 或可重定位 pointer 替代固定 virtual address，改善多语言 runtime、sandbox 与 heterogeneous node 支持。
- 扩展 direct-to-SDM creation 和 disk-to-SDM I/O，消除当前先落 local memory 再 copy 的第一阶段成本；论文在 §10 只提出方向，尚未实现。

## 相关

- **相关概念**：[[CXL]]、[[NUMA]]
- **同会议**：[[OSDI-2026]]
