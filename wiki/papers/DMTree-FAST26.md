---
type: paper
name: DMTree
full_title: "DMTree: Towards Efficient Tree Indexing on Disaggregated Memory via Compute-side Collaborative Design"
authors: [Guoli Wei, Yongkun Li, Haoze Song, Tao Li, Lulu Yao, Yinlong Xu, Heming Cui]
venue: FAST
year: 2026
tags: [disaggregated-memory, range-index, rdma, tree-index, fingerprint]
source_pdf: "[[fast2026-wei.pdf]]"
source_md: "[[fast2026-wei]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# DMTree: Towards Efficient Tree Indexing on Disaggregated Memory via Compute-side Collaborative Design (FAST 2026)

> **一句话总结**：观察到 DM range index 的 private compute-side caching 让 memory server NIC 成为 [[RDMA]] IOPS/带宽瓶颈而 compute 间链路长期空闲，DMTree 用 compute-side collaborative cache（共享 fingerprint 表）与 collaborative locking 把精确定位和加锁卸到 compute pool，在 10 亿条 32B KV 上相对 Sherman/ROLEX/SMART/CHIME/dLSM 取得最高 **5.7×** insert 吞吐、**4.5–5.2×** search 吞吐，并接近单 RDMA 理论上限。

## 问题与动机

[[Disaggregation|Disaggregated memory]] (DM) 把 compute 与 memory 拆成独立资源池，compute server 算力多、内存少，memory server 内存大、CPU 极少（实验仅分配 1 core），跨池通信依赖 one-sided [[RDMA]]。数据库、in-memory KVS 等应用既要点查/写，也要 range scan，因此 **range index** 是 DM 上的关键路径组件。

现有 DM range index——Sherman（[[B-Tree|B+-tree]]）、ROLEX（learned index）、SMART（ART）、dLSM（[[LSM-Tree]]）、CHIME/FP-B+-tree——几乎都采用 **private compute-side caching**：每台 compute server 私有缓存内部树或模型，不与 peer 共享。作者认为这不是局部优化问题，而是 **RDMA 资源利用范式** 的根本困境：优化一种资源必然恶化另一种。

- **连续 range 存储**（Sherman、ROLEX）：leaf 粗粒度连续存 32 个 KV，点查需读整 leaf → **带宽瓶颈**，search 仅达 expected（单 RDMA 读单条 KV）的 **16.3–18.8%**。
- **精确定位**（SMART/ART）：每条 KV 独立 leaf，消除 read amplification，但 scan/insert 需大量小 RDMA → **IOPS 瓶颈**，scan 仅 Sherman 的 **35.5%**，insert 仅 expected 的 **35.8%**。
- **LSM-tree**（dLSM）：顺序写减轻网络压力，但 compaction 压在 memory server 的极少 CPU 上 → **CPU 瓶颈**，高并发 insert 跌至 expected 的 **14.9–41.4%**。
- **fingerprint/hash 混合**（CHIME、FP-B+-tree）：兼顾 range 存储与 leaf 内精确定位，但 fingerprint 表访问与 leaf 加锁仍消耗 memory server IOPS；FP-B+-tree search 仅 expected 一半，CHIME/FP-B+-tree insert 仅 **23.9–45.4%** expected。

论文 claim：在「连续 range 存储 + leaf 内精确定位」这一正确方向上，瓶颈已从数据结构本身转为 **如何把 auxiliary metadata 的 RDMA 流量从 memory server 挪走**；而 compute server 之间的 RDMA 资源长期 underutilized，因为多路请求在 memory server NIC 处汇聚饱和。

## 关键观察 / 隐含假设

- **观察 1**：DM range index 的性能天花板由 memory server 侧 NIC 的 **IOPS 与带宽** 共同决定，且二者难以在同一 private-cache 范式下同时优化。
  - **依赖假设**：index 以 one-sided RDMA 直接访问远端内存为主；memory server CPU 极弱，不宜承担 locate/lock 等辅助逻辑；workload 同时包含 point ops 与 scan。
  - **可能失效场景**：若应用只需点查、scan 极少，ART 类设计的 IOPS 代价可能可接受；若 memory server 配备更强 CPU 或 smart NIC offload，「必须把逻辑放在 compute」的前提变弱。

- **观察 2**：高并发下 memory server NIC 先饱和，compute server 间 RDMA 利用率很低（FP-B+-tree insert 时 compute IOPS 利用率约 **17.5%**），存在可转移的「空闲网络预算」。
  - **依赖假设**：compute pool 有多台 server（实验 6 compute + 1 memory）；compute 间同样具备 RDMA 能力；瓶颈确实在 memory 侧汇聚而非 compute 本地 CPU。
  - **可能失效场景**：单 compute server 部署、或 compute 间无直连 RDMA 时 collaborative 设计失效；若 fingerprint 表过大导致 compute 内存成为新瓶颈，则无法继续 offload。

- **观察 3**：FP-B+-tree 类结构在 DM 上的额外 RDMA（读 fingerprint、RDMA_CAS 加锁）是 write/update 性能的主要拖累，而非 leaf 内 fingerprint 遍历的 CPU 成本（search 中 fingerprint traversal 仅占延迟 **5%**）。
  - **依赖假设**：leaf span=32、1-byte fingerprint；锁与 fingerprint primary 可共置在 compute 内存；RDMA NIC 顺序写可把 unlock 与写 fingerprint 合并。
  - **可能失效场景**：大 value 跨 cache line 需额外 CRC 字段；极高冲突写导致 collaborative lock 在 compute 间形成新热点；fingerprint 缓存不一致触发频繁 primary 同步（write 路径 FP sync 占延迟 **17.9%**）。

- **假设 1**：把 fingerprint 表和 lock 字段 primary 放在 compute server、通过 consistent hashing 分配所有权，在 scale-out/failover 时仍能保持可接受的同步与恢复成本。
  - **证据强度**：**中**——§3.2.3 与 §4.3 描述了 membership 变更与 primary 重建流程，但 evaluation 未做 compute server failure 压力测试。

- **假设 2**：optimistic fingerprint/cache 一致性（version ID + CRC，不一致时回源 primary 或远程重遍历）在并发写下足够正确且重试成本可控。
  - **证据强度**：**中**——机制设计完整，但实验聚焦吞吐与 P99，未单独报告 inconsistency 触发率或重试放大。

## 核心方法

DMTree 在 **FP-B+-tree** 骨架上实现 **compute-side collaborative design**，回应观察 2/3：利用空闲的 compute 间 [[RDMA]]，把精确定位与锁从 memory server 卸载。

**数据结构**：B+-tree 式多级指针 + leaf 连续存 span=32 条 KV + 1-byte fingerprint 表；leaf 带 right sibling 指针支持 scan。index 分布在 memory pool，compute 侧维护 cache 并通过 one-sided RDMA 访问远端 leaf/KV。

**Compute-side collaborative cache**（回应观察 3 的额外 RDMA）：
- **Private internal cache**：每台 compute 仅缓存 bottom-level internal nodes（更新频率低——填满 32 slot 才 split），上层 internal 节点本地重建；更新时只同步被改的 bottom-level 节点，降低一致性成本。
- **Collaborative fingerprint storage**：每个 leaf 的 fingerprint 表在某一 compute server 上为 **primary**，其他 server 可缓存副本。Search/insert 先从 peer compute 读 fingerprint（或本地 cache），定位 slot 后再对 memory server 发 **单次** KV RDMA；写路径只同步更新 primary fingerprint，cached copy **异步** 更新。Primary 所有权由 `consistent_hash(fp_offset)` 决定，支持 virtual node 负载均衡与 server 下线时重分配。
- **一致性**：internal entry 存 primary fingerprint 指针；leaf entry、internal entry、fingerprint 表各带 8-byte **version ID**（leaf range 变更时递增）与 **CRC**（跨 cache line 的大 entry）。Search 时版本不匹配则 invalidate 并远程重遍历；读写冲突用 optimistic CRC 校验重读。

**Compute-side collaborative concurrency**（回应 IOPS 瓶颈）：
- Lock 字段与 primary fingerprint 表共存在 compute server；加锁用跨 compute 的 **RDMA_CAS**；**embedded unlocking** 把 lock byte 放在 fingerprint 表末尾，insert 时写回 fingerprint 的 RDMA_WRITE 在 NIC 顺序写语义下自动完成 unlock，将 update 路径 5 次 RDMA 中的 **3 次**（lock、读 fingerprint、unlock）移出 memory server。
- Internal node 锁仍放 memory server（更新稀少）。同 server 内冲突锁可本地消解；读写冲突走 CRC optimistic 路径。

**附加优化**：scan 时用 fingerprint 过滤空 slot 省带宽；继承 Sherman/SMART 的 read delegation 与 write combining，但限制 batch 大小以防尾延迟恶化。

## 设计取舍

- **取舍 1：compute 间协作 vs 实现与一致性复杂度**。收益是 memory server IOPS 从瓶颈侧释放，insert/update 接近理论 RDMA 次数；代价是 fingerprint 多副本、primary 选举、version/CRC 校验与不一致回源，系统状态从「memory 为唯一真相」变为「memory + compute metadata 双真相源」。
- 取舍 2：FP-B+-tree 骨架 vs 更激进的 hash-only 设计。连续 leaf 保留 scan 友好性（相对 SMART 3.2× scan 吞吐），fingerprint 避免 Sherman 式 read amplification；代价是 leaf 分裂/合并时既要改 memory leaf 又要改 compute fingerprint primary，路径比纯 B+-tree 长。
- 取舍 3：compute 内存换网络性能。默认每 compute server 需 5.4 GB（2.3 GB internal tree + 3.1 GB fingerprint），高于 Sherman（2.1 GB）但远低于 SMART（22.5 GB）。内存不足时 FIFO 驱逐 internal cache，新 fingerprint 退回 memory server——性能仍优于 SMART 的 thrashing，但 collaborative 优势减弱。
- **边界条件**：Zipfian **update** 场景下 dLSM 因本地 memtable 可处理大部分写而吞吐极高，DMTree 并非全能最优；极大 scan length（1000）时带宽重新成为 scan 瓶颈，DMTree 与 SMART 差距缩小；CHIME 在受限 compute cache 下靠 hotness-aware 机制仍表现稳健。

## 实验与结果

- **Testbed**：6 compute + 1 memory server；双路 40-core Xeon Gold、128 GB DRAM、100 Gbps ConnectX-6；memory server 1 CPU core；预加载 **10 亿** 条 32B KV（24B key + 8B value pointer），每实验 **1 亿** 次操作；YCSB micro-benchmark 与 A–F 混合负载；Uniform 与 Zipf(0.99)。
- **Search**：相对 Sherman/ROLEX **4.5–5.2×**；相对 dLSM **2.8–3.1×**；与 SMART/CHIME 接近 expected single-RDMA 上限。
- **Insert**：相对 Sherman/ROLEX **3.7–4.3×**；相对 SMART/CHIME **2.3–3.5×**；相对 dLSM **2.1–5.7×**（最高值）；整体最高 **5.7×** 于 baselines。
- **Update**（Uniform）：相对全部 baseline **1.4–4.3×**；Zipfian 下 SMART/CHIME 因请求聚合也不错，DMTree 仍优 **1.1–1.5×**。
- **Scan**：相对 SMART **3.2×**；相对 Sherman/CHIME **1.1–1.3×**（fingerprint 过滤空 entry）；与 ROLEX 接近。
- **Tail latency**（72 threads/compute）：search P99 比 Sherman/ROLEX 低 **64%**；insert P99 低 **28–80%**；scan P99 比 SMART 低 **70%**；限制 batch 队列使 Zipfian search P99 比 SMART/CHIME 低 **26–31%**。
- **YCSB A–F**：search/write-heavy 工作负载 **3.8–9.7×** 于 Sherman/ROLEX；scan-heavy E 与 ROLEX 类似；整体优于 CHIME **1.1–1.7×**。
- **开销**：write 路径额外 fingerprint traversal + sync 占延迟 **19.4%**；memory server 上 10 亿条 KV DMTree 用 **60.1 GB** vs Sherman **54.2 GB**（version/CRC 字段）；ablation 显示 collaborative cache 带来 **1.2–1.9×**、collaborative concurrency **1.5–1.6×**；compute IOPS 利用率从 **17.5%** 提到 **32.9%**。
- **敏感性**：KV 变大时 scan 从 IOPS-bound 转向 bandwidth-bound；scan length 1000 时 DMTree 比 SMART **3.5–3.9×**；compute cache 从 20 GB 缩到 2.5 GB 时 SMART 吞吐跌 **72%**，DMTree 仍稳定。

## Critical Analysis

### 论证链条

动机测量（Sherman/ROLEX 带宽瓶颈、SMART IOPS 瓶颈、FP-B+-tree 仍压 memory NIC）→ 发现 compute 间 RDMA 空闲 → 提出把 fingerprint 与 lock offload 到 compute pool → DMTree 在 micro-benchmark 与 YCSB 上全面领先。链条在「**单 memory server、多 compute、index 隔离评测、32B 小 KV**」设定下较闭合：ablation 逐步叠加 RDMA opt、collaborative cache、collaborative concurrency，且 Figure 17 显示 memory server IOPS 压力确实下降。

薄弱跳步：(1) 从「compute 间 RDMA 空闲」到「协作副本一致性开销可忽略」缺少 inconsistency/retry 率量化；(2) 最高 **5.7×** 出现在 insert vs dLSM 的特定对比点，而 Zipfian update 下 dLSM 反而极强，整体「全面最优」需按 workload 细分；(3) failure/recovery 仅有设计描述，未进入实验主链条。

### 假设压力测试

- **多 memory server / 分片 index**：实验仅 1 台 memory server，network 汇聚模型最直接；分布式 DMTree 分片后 compute 间 fingerprint 路由与跨片 scan 成本论文未展开——**论文未覆盖**。
- **CXL 替代 RDMA**：§4.3 认为 compute-side collaborative 仍有价值，但更低延迟可能让软件并发开销先于 IOPS 饱和，DMTree 相对收益可能缩小——仅有讨论，无 CXL 实测。
- **大 value / 宽 cache line**：>64B entry 需 per-entry CRC，memory 开销与读放大上升；scan 过滤空 fingerprint 的收益随 value 变大而下降（128B 时 DMTree 与 SMART scan 接近）。
- **高度倾斜写冲突**：collaborative lock 把热点从 memory NIC 移到 primary fingerprint 所在 compute server，可能形成新的 lock hotspot——Zipfian update 实验显示 DMTree 仍优，但极端同一 leaf 竞争未单独 ablate。
- **生产级语义**：delete 逻辑删除 + 后台回收；与完整 transactional KVS（复制、崩溃恢复、范围事务）集成路径论文未讨论。

### 实验可信度

- **Benchmark 代表性**：10 亿 KV + YCSB 是 DM index 论文常见设定，与 Sherman/SMART/CHIME 可比；32B pointer-value 模式有利于 index 优化、弱化 value 带宽，代表 metadata-heavy KVS，不代表大 payload 服务。
- **Baseline 公平性**：六套开源 DM index 同台，coroutine（dLSM 除外）、span 参数按各论文推荐配置，CHIME 的 Masked-CAS 因驱动版本替换——作者已说明；ROLEX 用 CHIME 实现并预训练，避免在线 retrain 干扰。
- **Ablation**：从 FP-B+-tree 逐步加三项设计，支撑「瓶颈在 memory IOPS」叙事；缺少对 consistent hashing、version/CRC、embedded unlock 的独立开关。
- **Metrics**：吞吐与 P99 覆盖主路径；**未测** recovery time、metadata 不一致率、多 memory server scale-out、foreground 延迟隔离、长期运行内存碎片。

### 系统性缺陷

- **状态复杂度**：primary fingerprint + 异步 cache + version/CRC 使调试与运维显著难于 Sherman 式「memory 为 sole source of truth」——论文未讨论可观测性（primary 迁移、invalidation 率）。
- **尾延迟与隔离**：batch 限制缓解队列堆积，但 collaborative 路径多一跳 peer RDMA，极端 cache miss 时延迟上界论文未给出。
- **故障恢复**：§4.3 描述探测失败与 primary 重选，但无 failover 实验；compute 故障时 fingerprint 重建依赖远端 KV 校验，恢复时间与可用性边界未知。
- **资源隔离**：多 tenant 共享 compute fingerprint 存储时的公平性与干扰——**论文未讨论**。
- **兼容性**：依赖 RDMA_CAS/CAS 语义与 NIC 顺序写；迁移到 [[CXL]] load/store 需重新验证 lock 与 fingerprint 原子性。

## 局限与 Future Work

- **局限 1**：评测以 **index 隔离** 为主，未嵌入完整 DM KVS 的 replication、logging、GC 等端到端路径，生产 critical path 增益待验证。
- **局限 2**：默认 **单 memory server** 拓扑，未验证 memory pool 横向扩展时 collaborative metadata 路由是否成为新瓶颈。
- **局限 3**：compute 侧额外 **5.4 GB** 内存与 memory 侧 **~11%** 空间开销（version/CRC）是明确成本；极小内存 compute node 上需退回 memory-side fingerprint。
- **局限 4**：Zipfian update-heavy 场景下 dLSM 本地写路径仍极具竞争力，DMTree 的「全面最优」对 workload 敏感。
- **Future work 1**：在 **多 memory server + 真实 production trace** 上测量 fingerprint primary 热点、跨 compute RDMA 流量与 P99 tail，验证 collaborative 设计是否随规模线性扩展。
- **Future work 2**：对 **compute server failure / primary 切换** 做故障注入 benchmark，量化 metadata 重建时间与查询可用窗口。
- **Future work 3**：在 **[[CXL]] 池化内存** 上复现实验，验证当 IOPS/带宽不再瓶颈时，software concurrency（lock、CRC、cache coherence）是否成为下一主导因素，并评估 collaborative 设计是否需简化。

## 相关

- **相关概念**：[[RDMA]]、[[Disaggregation]]、[[CXL]]、[[B-Tree]]、[[LSM-Tree]]、Fingerprint-Index、Consistent-Hashing、Read-Amplification
- **同类系统**：[[Sherman]]、[[SMART]]、[[CHIME]]、[[ROLEX]]、[[dLSM]]、[[FP-B+-tree]]、[[FUSEE]]
- **同会议**：[[FAST-2026]]
- **对比**：DMTree 在 range scan + point op 均衡场景相对 Sherman/SMART 的 bandwidth–IOPS 权衡；与 dLSM 在 write-heavy / Zipfian update 上形成互补而非全面替代
