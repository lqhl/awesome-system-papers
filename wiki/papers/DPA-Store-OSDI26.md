---
type: paper
name: DPA-Store
full_title: "DPA-Store: An Ordered Network Data Path Key-Value Store"
authors: [Frederic Schimmelpfennig, Jan Sass, Reza Salkhordeh, Martin Kröning, Stefan Lankes, André Brinkmann]
venue: OSDI
year: 2026
tags: [key-value-store, smartnic, learned-index, dpa, rdma]
source_pdf: "[[osdi26-schimmelpfennig.pdf]]"
source_md: "[[osdi26-schimmelpfennig]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 网络数据路径上的有序键值存储（OSDI 2026）

> **原题**：DPA-Store: An Ordered Network Data Path Key-Value Store

> **一句话总结**：DPA-Store 发现 BlueField-3 DPA 的优势是 176 个可并发处理 packet 的轻量线程，弱点却是约 465 ns 的本地内存访问与很慢的 host-to-DPA 写路径，因此把可读的 learned-index 内层节点和写缓冲留在 NIC，把 value 与昂贵的 retraining/split 放到 host，再用 RCU 式 pointer stitch 保持 DPA 查找无锁；主 B3140L/100 Gb/s、64-bit key/value 配置达到 33 MOPS GET、13 MOPS RANGE 和 12.1 MOPS UPDATE，但 INSERT 只有 1.7 MOPS，UDP 重试也不提供 exactly-once write，因此“无状态 client”只表示 client 不保存远端索引，并不表示没有 transport 与顺序责任。

## 问题与动机

远程内存 KV store 如果只做 point lookup，可以用 hash table 放在 SmartNIC 上，把 host OS 和 [[PCIe]] 往返从 fast path 移走；但 hash 不支持有序 RANGE。B-tree 可以做 RANGE，却需要每层多次随机访存。若 SmartNIC 每层都 DMA host tree，HONEYCOMB 一类系统会付出多轮 PCIe delay；若让 [[RDMA]] client 自己遍历，SHERMAN、ROLEX 等系统又要求每个 client 保存 remote address 或 learned cache，增加扩容、一致性与故障处理复杂度（§1–§2）。

BlueField-3 的 on-path Data Path Accelerator（DPA）提供 16 个 RISC-V core、每核 16 hardware thread，packet 可直接进入 DPA cache；但 application 实际只能用 189/256 个 thread，DPA-addressable memory 只有 1 GiB，而且一次 DPA DRAM access 平均约 465 ns，约是普通 host DRAM 的 5 倍。DPA 到 host 的 DMA 更慢，论文引用约 910 ns（§2.3、§3、§4.2.6）。这使“把整棵普通树搬到 NIC”既放不下，也会被 memory latency 限制。

DPA-Store 的核心目标是：client 不持有树结构，用一个 UDP request 完成 GET/INSERT/UPDATE/DELETE，并支持 RANGE；读 fast path 不进入 host CPU，写结构调整又不阻塞 DPA traversal。它是单节点内存系统，不讨论 replication、server crash 后恢复或持久性。

## 关键观察 / 隐含假设

- **观察 1：在 DPA 上，减少 cache-line access 比减少 tree level 更重要。** 同 fan-out 的 B+ tree 在 node 内 binary search 会触发多次独立访问；piecewise-linear model 把候选缩到连续窗口，默认 inner/leaf error bound 为 4/8，验证预测位置最多扫描 2 个 DPA cache line 和 3 个 host-side leaf cache line。这里不是每层的总访存数：计入 metadata、model 和 child pointer 后，论文的 GET 模型假设每个半满 inner node 平均访问 4.5 条 cache line（图 1、图 12、§3.1.1、§4.2.6）。
  - **依赖假设**：key distribution 能用较小误差的 linear segment 表示，metadata 仍可放入 1 GiB DPA memory。
  - **可能失效场景**：osmc 在为节省空间把 error bound 放大到 16 后，B+ tree throughput 反而更高；learned index 不是所有 distribution 都胜出。
- **观察 2：查找适合高并发 DPA，retraining、split 与 allocation 适合 host。** 读路径只需要小模型、scan 与最后一级 DMA；写入先进入每 leaf 16-entry buffer，host 再批量 rebuild（图 3–4、§3）。
  - **依赖假设**：insert buffer 能吸收写 burst，host patcher 与 DPA stitcher 的处理速度长期追得上 mutation rate。
  - **可能失效场景**：INSERT-heavy workload 会持续产生新 node copy，BlueField-3 的 host-to-DPA path 只有约 120 MB/s，buffer 很快形成 backpressure。
- **观察 3：树更新只需在最后一步原子接回旧树。** host 在旁边构造新 subtree，先发 COPY，再用一个 CONNECT pointer swap 生效；旧 subtree 等所有 traverser 进入下一 request 后才回收（图 6–8、§3.2）。
  - **依赖假设**：BlueField-3 的 cache coherence、atomic pointer 和 packet counter 足以实现跨 DPA thread 的 RCU/epoch 语义。
- **观察 4：极小 DPA context 让简单 cache 比精确 hotness 更划算。** 每个 traverser 只有 96-entry cache 和 256-bit Bloom filter；random admission 在 Zipf `α=1` 下约 25% hit，而命中可到 50% 的 Space-Saving variant 因每请求多一次读写，最终 GET throughput 没更高（§3.1.2）。
  - **依赖假设**：key popularity 有足够 skew，client 的一致 hash 能把同一 key 送到 home traverser。
- **假设 1：允许 UDP duplicate 与 client-side ordering。** DPA-Store 不记录 request ID；GET/RANGE 可安全 retry，同参数 write 最终会被 patcher 合并，但 delayed duplicate 可能越过另一笔冲突 write。需要跨 key 或严格 write order 时，client 必须自行串行化（§3.1.3）。
- **假设 2：64-bit key/value 和短 RANGE 能代表目标 workload。** 评测的 value 只有 8 bytes，RANGE 每个 packet 最多带 64 对 KV，ROLEX 对比只取 10 个相邻 key；大 value 与长 scan 会改变 DMA、MTU 与带宽瓶颈。

## 核心方法

### 1. DPA 上的 request fast path

client 按 key hash 选择 UDP port，BlueField hardware steering 把 packet 送到对应 traverser。默认使用 176 个 traverser，占满 11 个 DPA physical core。thread 在 NIC DRAM 中走 learned-index inner node，到 leaf 后先查 16-entry insert buffer；若没有最新值，再按 leaf model 预测 host replica 中的位置，用 DMA 读连续 key window 和 value。RANGE 到 leaf 后顺序读取，跨 leaf 时对下一个 key 重新从 root 下降（图 3–4、§3.1）。

### 2. 为慢 DPA memory 定制 learned index

每个 inner node 有 7 个 PLA segment，segment 首 key 与 metadata 放一个 cache line；计算 model 时预取 segment 和 pivot。pivot 与 child pointer 分开存，使 scan 多个 pivot 后只读一次 pointer。DPA 没有 floating point，因此 slope/intercept 用 fixed point，中间量扩到 128 bit 以覆盖完整 64-bit key space（§3.1.1）。

这是一种有边界的空间—时间交换。小 `ε` 减少 scan，却增加 model 和空隙；50M entry 时 NIC metadata 从 wiki 的 147 MB 到 face 的 672 MB不等，后者 index overhead 达 104%。把 face/osmc 的 `ε` 放宽到 16，可降到 332/228 MB，但会增加 scan（表 1）。

### 3. 每线程 hot-entry cache 与过载回退

每个 home traverser 独占自己的 cache，不需要跨线程 coherence。UPDATE/DELETE 在响应前 invalid cache slot，Bloom bit 不清除，因而允许残留 false positive；false positive 只多一次 bucket probe，不会返回错 value。若单个 hot key 把 256-packet receive queue 填满，client 可 timeout 后换 hash 重试到 non-home traverser，但这条路径绕过 GET cache，write 还需跨线程 invalidation（§3.1.2–§3.1.3）。

### 4. host patch 与 NIC stitch

mutation 先 append 到 leaf buffer，并立即对后续 read 可见；append 成功就是 delivered-request history 中的 linearization point。buffer 填满后，traverser DMA 一个 patch request 给 host。默认 4 个 patcher merge operations、retrain leaf，必要时自底向上 split/retrain parent；host 不维护 parent pointer，而是重新从 root 找 parent 并加锁（图 6、§3.2.1）。

host 先把新 node 作为 COPY stitch 发给 4 个 DPA stitcher，最后用 CONNECT stitch 原子换 parent pointer。tree 在一级 inner node 下按 stitcher 分区；root split 用 UID probe 和 queue fence 保证 copy/connect 顺序。旧 node 用所有 traverser 的 packet counter 做 epoch reclamation，直到旧 request 都离开后才释放（图 7–8、§3.2.2–§3.2.3）。

### 5. “无状态 client”的准确含义

client 不保存 tree node、remote address 或 learned model，这比 ROLEX 的 stateful learned cache 简单。但 client 仍要做 shared key hash、控制 in-flight queue、timeout/retry、在 overload 时改 hash，并在应用需要时串行化 write。DPA-Store 使用 UDP，不实现 flow/congestion control，也不提供 exactly-once；论文只保证已送达 request 的 tree visibility 与 linearization，不保证 packet delivery 或 crash durability（§3.1.3）。

## 设计取舍

- **索引在 NIC、value 在 host**：1 GiB DPA memory 可容纳更大 key set，GET 却仍至少在 leaf 走 host DMA；大 value 会把 PCIe/data movement 变成更强瓶颈。
- **小误差 learned model 换 metadata**：减少每层访问，在难拟合 distribution 上可能比 compact B+ tree 更慢且更占空间。
- **buffered write 换即时可见与异步维护**：write 很快对 read 可见，但 INSERT 造成的 node copy 受 host-to-DPA bandwidth 限制；buffer 满时 request 被 re-enqueue。
- **RCU stitch 换无锁 read**：traverser 不停顿，代价是双份 subtree、UID/fence、epoch reclamation 和 host/DPA 两侧 allocator 状态。
- **UDP 换很小的 DPA state**：省掉 TCP window/retransmission metadata，可靠性、duplicate suppression、flow control 与 write ordering 被推给 client。
- **per-thread cache 换简单 coherence**：home routing 让 invalidation便宜，极端 skew 会把一个 traverser 变成 hotspot；绕行又放弃 cache benefit。

## 实验设置

- 一台 server 通过 100 Gb/s Dell switch 连接 6 台 client。server 是 32-core AMD EPYC 9354P、128 GB DDR5 和 BlueField-3 B3140L；client 是 dual-socket 32-core EPYC 7301、ConnectX-5，并用 DPDK 发包。BlueField 设为 NIC mode，ARM core 关闭（§4.1）。
- SOSD key 包括 sparse、dense4x、Facebook、Amazon、Wikipedia、OpenStreetMap；通常预装 25M entry，内存表用 50M。key/value 均为 64 bit，skew workload 用 Zipf `α=0.99`。
- 默认 176 traverser、4 host patcher、4 DPA stitcher；GET client queue depth 为 32（最多 5,952 个 in-flight），INSERT/RANGE 为 18。长/短 benchmark 分别取 4/8 次平均，throughput standard deviation 少于 5%，latency 少于 9%。
- 主要系统 baseline 是同一 server/NIC stack 上的 ROLEX；它是 stateful-client one-sided RDMA learned index，功能相近但把结构与 retraining 成本放在不同位置。

## 实验与结果

- **主配置的 GET 与 RANGE 上限**：B3140L 主测试配置达到 33 MOPS GET 与 13 MOPS RANGE（摘要、§4）。uniform sparse 的 GET 是 26.3 MOPS，Zipf cache 后是 32.1 MOPS；这些数字来自单 server、100 Gb/s、8-byte key/value，不代表大对象或 scale-out throughput。另一个不限制 in-flight、由 B3220 DPA client 发包的硬件对照在 skew GET 达 48.5 MOPS，不能与主配置混成同一上限（图 11、图 14）。
- **learned index 消融**：在 sparse/sparseBig/amzn 上，learned tree 的 GET throughput 分别约 26.3/24.8/24.9 MOPS，高于 canonical B+ tree 的 21.5/18.8/20.1；osmc 因 `ε=16` 扫描窗口变大，B+ tree 20.8 MOPS 反而高于 learned tree 14.6 MOPS。B+ tree p50 仍普遍更差（图 12、§4.2.5）。
- **cache、prefetch 与深度**：skewed popularity 下 hot cache 最多提高 30% throughput，但因 load 向少数 traverser 集中，tail latency 上升；optimistic prefetch 单独提高 19%。基于 465/910 ns memory latency 的模型预测 31.05 MOPS，与测量接近（图 11、§4.2.4、§4.2.6）。
- **UPDATE 快、INSERT 慢**：UPDATE-only 不复制新 node，最高 12.1 MOPS；INSERT-only 需要 retrain/COPY，最高只有 1.7 MOPS。50M sparse bulk load 的 host tree 1.643 s 完成，向 DPA 复制 192 MB 需 1.605 s，只有约 120 MB/s；改成 host-push FlexIO 也没改善，定位到 BlueField-3 写路径而非 protocol 方向（图 13、§4.2.7–§4.2.8）。
- **thread 与硬件敏感性**：把 traverser 和 stitcher 混在同一个 DPA core 会让 INSERT throughput 下降 14%，所以 189 个可用 thread 中用 176 traverser、4 stitcher并留下 9 个。B3220 dual-port 在 skew GET 达 48.5 MOPS，B3140L 为 39.9 MOPS；uniform GET 与 mutation/RANGE 几乎不变，且 B3220 没测 latency（图 9、图 14、§4.2.2、§4.2.9）。
- **对 ROLEX**：在 uniform YCSB 上，DPA-Store 的 sparse/amzn GET、所有 RANGE-only（每次 10 key），以及 amzn/osmc 的 YCSB-A throughput 更高，并在所有图示 workload 有更低 p50；ROLEX 在 osmc GET 与 INSERT-only 明显更快。这个对比证明 stateless-index client 可以有竞争力，也同时暴露 DPA-Store 的 INSERT 短板（图 15、§4.3）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| learned index 能减少慢 DPA memory access | 图 12：三个 dataset throughput 高于 canonical B+ tree；prefetch 另增 19% | osmc 大 `ε` 时 B+ tree 反胜；baseline 没有 interpolation | 强但非普遍 |
| DPA/host 分工可让 read 无锁且 write 立即可见 | 图 3、6–8 的 buffer/patch/stitch；YCSB mixed workload 正常运行 | correctness 依赖 BlueField coherence、atomic pointer 和 epoch；无 crash test | 中到强 |
| stateless-index client 仍可匹敌 stateful RDMA client | 图 15：部分 GET/mixed 与全部 RANGE throughput 胜 ROLEX，p50 全部更低 | 单 server、uniform、64-bit KV；双方架构成本不同 | 强 |
| host-to-DPA 写路径是 INSERT 主瓶颈 | 图 13：UPDATE 12.1 MOPS、INSERT 1.7 MOPS；pull/push 都约束；bulk copy 120 MB/s | 一代 BlueField-3；未来硬件的 62 MOPS 等数字只是模型 | 强 |
| hot cache 可提高 skewed GET | 图 11：最高约 30% throughput 增益 | `α=0.99`，同时使 traverser queue 与 tail latency更不均 | 强 |

## 批判性分析

### 论证链条

论文从 DPA memory latency 与 1 GiB capacity 出发，选择 learned index、host value replica 和批量结构更新；B+ tree、`ε`、cache、prefetch、thread allocation、bulk copy 与 ROLEX 实验逐项验证，链条相当完整。最重要的负结果也没有隐藏：INSERT 只有 1.7 MOPS，osmc 上 B+ tree 更快。需要克制的是硬件改进推断：若 DPA memory 到 100 ns，模型预测可超过 62 MOPS，但这不是实机结果，也没有计入 packet matching 或其他瓶颈。

### 假设压力测试

value 从 8 byte 增到 KB/MB 后，每次 GET 的 host DMA 与 response packet 会主导；RANGE 超过 64 对需要多 packet，跨 leaf 还会重新下降。Zipf 热点提高 cache hit，也可能让单 home traverser 的 256-entry queue 溢出。持续 INSERT 会让 16-entry leaf buffer、patcher、stitcher 和 120 MB/s copy chain饱和。key distribution phase change 会触发更多 split/retraining，并改变 learned error。client 或 network duplicate 若与同 key write 交错，会破坏应用期待的顺序。

### 实验可信度

真实 BlueField-3、六个 SOSD distribution、uniform/skew、读写混合、强 ROLEX baseline、硬件型号对照和多项负结果让硬件结论可信；重复次数与 standard deviation 也有报告。范围仍窄：单 server、100 Gb/s、固定小 KV、UDP/DPDK client，没有长 RANGE、大 value、loss/reordering、server failure、production trace、p99.9 或能耗。ROLEX client 存 metadata，DPA-Store client 不存，但 DPA-Store获得更复杂 NIC hardware，资源成本未统一量化。

### 系统性缺陷

论文把 tree consistency 讲得细，却不提供 durability、replication 或 recovery；NIC/server reset 会怎样处理 DPA buffer 中已 ack 但尚未 patch 的 write，论文未讨论。UDP 没有 congestion control 和 exactly-once，client timeout/alternate hash 只是 heuristic。root split、stitch UID/fence、host parent lock、DPA/host dual allocation 与 global epoch 增加较大 correctness surface；没有故障注入。1 GiB DPA memory 与部分 dataset 高达 104% metadata overhead 限制 scale，且 ARM 因 NIC mode 被禁用，控制面必须依赖 host。

## 局限与后续工作

- **局限 1**：单节点、内存态、无 replication；只保证 delivered request 的 consistency，不保证 transport exactly-once 或 crash durability。
- **局限 2**：INSERT 被 BlueField-3 host-to-DPA path 限到 1.7 MOPS，write-heavy workload明显输给 ROLEX。
- **局限 3**：评测只有 64-bit value 与短 RANGE；大对象、多 packet response 和 scale-out sharding未覆盖。
- **局限 4**：client 虽不保存 index，仍承担 hash、flow control、retry 与 write ordering，协议并非真正“零状态”。
- **后续工作 1**：注入 packet loss/duplicate/reorder、DPA reset、host crash 和 stitcher stall，验证 ack write 的恢复与 linearizability。
- **后续工作 2**：扫描 value size、RANGE length、Zipf exponent 与 mutation burst，报告 goodput、p99/p99.9、queue drop 和 patch backlog。
- **后续工作 3**：在更快 host-to-DPA path 上实测而非模型外推，并把 DPA memory、packet matcher、PCIe 和 NIC bandwidth 的 roofline 分开。
- **后续工作 4**：加入多 server range-aware sharding 与 replication，量化 client 仍保持无索引状态时的 reconfiguration cost。

## 相关

- **相关概念**：learned index、SmartNIC、RCU、[[PCIe]]、[[RDMA]]
- **相关系统**：ROLEX、SHERMAN、HONEYCOMB
- **同会议**：[[OSDI-2026]]
