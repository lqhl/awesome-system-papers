---
type: paper
name: HDTX
full_title: Fast Distributed Transactions for RDMA-based Disaggregated Memory
authors: [Haodi Lu, Haikun Liu, Yujian Zhang, Zhuohui Duan, Xiaofei Liao, Hai Jin, Yu Zhang]
venue: ATC
year: 2025
tags: [distributed-transactions, rdma, disaggregated-memory, occ, replication]
source_pdf: "[[atc2025-lu.pdf]]"
source_md: "[[atc2025-lu]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# HDTX：基于 RDMA 的分解内存的快速分布式事务（ATC 2025）

> **原题**：Fast Distributed Transactions for RDMA-based Disaggregated Memory

> **一句话总结**：在 [[RDMA]] + [[Disaggregation|disaggregated memory]] 假设下，DM node 几乎无 CPU 可跑事务逻辑、RTT 与带宽是主导瓶颈；HDTX 用 redo log + visibility control 把 commit 压到 2 RTT，用 RDMA Wait/Enable 把 Release 下放到 memory node RNIC，并用 decentralized priority locking 调度 mission-critical dtxn，TPC-C 上比 FORD/FaRM 延迟降 72.1%/88.3%、吞吐升 84.7%/2.08×。

## 问题与动机

[[Disaggregation|Memory disaggregation]] 把 compute 与 memory 拆成独立 pool，经 [[RDMA]] 或 CXL 互联，能提升利用率与扩缩弹性，但 correlated object 的并发访问仍需要 distributed transaction（dtxn）保证一致性。问题在于：传统 RDMA dtxn 系统（[[FaRM]]、FaSST、DrTM+H）为 monolithic server 设计，默认 memory node 有足够 CPU 做 buffer polling、锁管理与数据复制；DM 架构下 memory node 通常只有极弱算力，只能做分配与网络初始化。

SOTA FORD 虽针对 DM 做了 one-sided [[RDMA]] 优化，commit 仍需 3 RTT，且 undo log 方案在 commit/release 间要发两轮最新数据，高负载下 [[RDMA]] 带宽压力大。论文进一步指出三类结构性痛点：(1) OCC + primary-backup replication（PBR）的多阶段协议带来过多 RTT（FaRM 5、FORD 3）；(2) commit 阶段无法在 DM node 本地同步 replica，只能由 coordinator 跨节点搬运 log 与数据；(3) mission-critical dtxn 需要 priority scheduling，但 DM node 没有 CPU 做全局锁管理。

作者 claim 的边界是：面向 **one-sided RDMA + 弱算力 memory node + 2-way replication** 的 OLTP 风格 KV/hash table workload，在 fail-stop 非 Byzantine 模型下，把 dtxn critical path 压到最少 RTT，同时不牺牲 serializability 与 remote persistence。论文不讨论 CXL 语义、SmartNIC 通用 offload 框架，也不覆盖复杂 SQL 或跨数据中心 geo-replication。

## 关键观察 / 隐含假设

- **观察 1：DM dtxn 的性能天花板首先由 network RTT 数量决定，而不是本地 CPU 算力。** Table 2 归纳 FaRM（5 RTT）、DrTM+H（4 RTT）、FORD（3 RTT）；作者分析 IBTA ordering 规则（Table 1）后发现 Validation 与 Commit 无数据依赖，可与 primary/backup commit 合并，从而把 commit path 压到 2 RTT。
  - **依赖假设**：workload 以短事务、小对象（默认 max 1 KB）为主；coordinator 与 memory node 间 RTT 稳定且 one-sided primitive 批处理有效；低到中读写冲突下 Validation&Commit 合并的 rollback 开销可接受。
  - **可能失效场景**：极高 read-write conflict 时 Validation 失败会浪费已写入的 redo log 带宽；跨 WAN 或 RTT 本身很大的环境，绝对延迟收益会缩小；对象很大或事务跨很多 replica 时，单 RTT 内 batched primitive 数量可能触达 NIC/驱动限制。

- **观察 2：redo log 比 undo log 更适合在 RDMA ordering 约束下做 fast commit。** undo log 要求 Atomic（visibility）与 Write（in-place update）严格顺序，第二操作需 Fence，额外 +1 RTT；redo log 可先写 log 再标 invisible，数据更新可异步在 Release 完成，Write+Atomic 同 send queue 天然有序（Table 1）。
  - **依赖假设**：failure recovery 可接受先持久化 redo log、后异步 apply 到 datastore；visibility bit 与 63-bit lock 共占 8-byte 原子域；read path 只需检查 version + visibility，不必持有 write lock。
  - **可能失效场景**：需要立即读到自己写入的场景若误用旧版本语义会出问题——论文用 visibility 控制规避，但 long-running read 与 GC 策略未展开；undo log 在 monolithic 环境 recovery 更直观，DM 上 redo + async release 的运维可理解性更差。

- **观察 3：Release 阶段的瓶颈是跨节点重复搬运最新数据，而 redo log 已在 memory node 上，可用 RNIC 做 node-local copy。** FORD 等系统 coordinator 在 Release 仍要把 latest data 发到 memory node；HDTX 用 RDMA Wait/Enable 预排 primitive chain，coordinator 仅发一个 RDMA Send 携带 copy 元数据，memory RNIC 自主完成 log→data 复制、版本更新、visibility 恢复与解锁。
  - **依赖假设**：RNIC 支持 Wait/Enable 事件驱动编排且 pipeline 开销小于省下的跨节点 Write；memory node 在初始化时用单 CPU thread 预置 WQ 模板，后台线程批量补充 primitive；redo log 与 application data 在同一 memory node 地址空间。
  - **可能失效场景**：不同 NIC 代际对 Wait/Enable 支持差异大，论文仅在 Mellanox ConnectX-3 上验证；RNIC pipeline 变慢时 Figure 10 显示 offloading 仍有净收益，但极端小对象/high QPS 下 fixed Send 激活成本可能上升；论文未讨论多租户下 RNIC 资源隔离。

- **观察 4：priority scheduling 不必 centralize 到 memory CPU，decentralized Lamport Bakery + RDMA FAA 即可在 compute pool 全局生效。** 64-bit lock 编码 normal/priority 双队列 ⟨Nc,Nm,Pc,Pm⟩，高优先级请求走优先 FIFO；多次失败可动态升 priority；lease（默认 1 ms）+ CAS 处理 overflow 与 deadlock。
  - **依赖假设**：mission-critical 事务比例可控（实验 20%）；锁竞争主要来自 write-write conflict；各 coordinator 时钟漂移在商用网络 ±0.5 ns/μs 量级内，lease 机制有效。
  - **可能失效场景**：大量事务同时升 priority 会退化为 FIFO 竞争；normal queue max 32768、priority max 16384，极端热点 key 可能触发 overflow reset 造成短暂抖动；论文未量化 priority inversion 对 normal txn 的公平性影响。

- **隐含假设：实验集群（5 节点、双副本 DCPMM、单 computing node 为主）足以代表 production DM dtxn 行为。**
  - **证据强度**：中。覆盖 TPC-C/SmallBank/TATP 与 microbenchmark，并做 thread/compute-node/contention sensitivity；但网络为 40/56 GbE ConnectX-3，规模远小于现代 100/200/400 Gb 数据中心，且只有 2 memory node。

## 核心方法

HDTX 由 computing pool 中的 coordinator 与 memory pool 中的 hash table KV 组成；初始化时 memory node 用极少 CPU 建连并预置 RNIC offload 模板，coordinator 缓存 metadata 以支持后续 one-sided 访问。事务 API 为 `Tx_begin` → `Tx_execution`（可多次扩展 read-write set）→ `Tx_commit`。

**Fast Commit Protocol (FCP)** 回应观察 1–2。协议压缩为三阶段：(1) **Execution & Locking**——batched RDMA FAA + Read 在一个 RTT 内加锁并取数；(2) **Validation & Commit**——并行做 read-set version 校验、向所有 replica 写 redo log、Atomic 标 invisible，成功即 commit point；(3) **Background Release**——异步更新数据。相对 FORD 的 undo+log-before-validation，HDTX 把 log 写到 Validation&Commit，冲突时丢弃 redo log，作者称 rollback 开销与 FORD 相当。write-only dtxn 可进一步优化到 1 RTT。

**RDMA-enabled Release offloading** 回应观察 3。每个 memory node 维护两个 WQ：WQ1 收 coordinator 的 RDMA Send（copy 元数据），WQ2 预置 Wait→Enable→Write/FAA 链。Send 完成触发 Wait，RNIC 拉取更新后的 Write 元数据并执行 local redo→data copy、version bump、visibility/lock release。后台线程批量 replenishment，避免 Release 占用 coordinator critical path。

**Decentralized priority-based locking** 回应观察 4。锁获取用 RDMA FAA 对 Nm 或 Pm 段加一获 token，轮询 Bakery 条件；等待间隔与 pending 请求数成正比以降低 busy polling。释放用 FAA 递增 Nc/Pc；死锁检测依赖 lease 超时（2× lease 且数据可读）后 CAS 移交锁；computing node fail-stop 时靠 redo log + lease 由其他 coordinator 接管未完成 dtxn。

持久化方面，实验用 Intel Optane DCPMM（App Direct）+ RDMA Flush（write-then-read last byte）保证 remote durability。故障模型为 fail-stop，网络分区时仅 primary partition 服务以保证强一致。深度协议与算法见 [[atc2025-lu]] 或 [[atc2025-lu.pdf]]。

## 设计取舍

- **redo log + async visibility 换更少 RTT**：获得 2 RTT commit 与更低锁持有时间，代价是 Release 完成前读者依赖 visibility/version 间接判断一致性，系统状态机更复杂；Validation 失败时仍消耗 log 写带宽。
- **RNIC offload 换 coordinator 带宽**：Release 不再跨节点传 latest data，节省最高 19.1% [[RDMA]] 带宽，但绑定特定 Wait/Enable 编排能力，初始化与 replenishment 增加工程复杂度；论文未讨论 RNIC 故障时的降级路径。
- **decentralized priority lock 换 memory-side scheduler**：无需 DM CPU 参与调度即可服务 mission-critical txn，但 lock 编码把 visibility 与锁塞进同一 8-byte 字，队列容量受 canary 限制；公平性与 starvation 边界主要靠 lease + 动态升 priority 缓解，缺少 formal SLO 证明。
- **OCC + PBR 换实现简洁**：保持与 FaRM/FORD 同族的正确性叙事（serializability），但不适合极高冲突场景；论文自己指出高冲突时 FORD/HDTX 都会因 pre-validation logging 浪费带宽，只是 HDTX 更快完成 commit。
- **边界条件**：对 80% 只读的 TATP，HDTX 与 FORD 接近，说明优化主要惠及 read-write 密集事务；对象上限 1 KB、hash table 访问模型对复杂 secondary index 不友好；单 GB 级 metadata cache 假设在 compute node 普遍成立。

## 实验与结果

- **主基准（16 threads × 7 coroutines，单 computing node，2 memory node 双副本）**：TPC-C 上 vs FORD 平均延迟 −72.1%、P99 −60.9%、吞吐 +84.7%；vs DM-compatible [[FaRM]] 平均延迟 −88.3%、P99 −82.7%、吞吐 2.08×。SmallBank 同样有显著优势；TATP 因 80% 只读且 backup 可读，三者接近。
- **FCP 微基准（64 coordinators，每 txn 2 objects，skewed/uniform）**：开启 FCP 在写比例升高时延迟增长更缓，skewed 分布下最高降 67.7% 平均延迟；高 read-write conflict 下 rollback 开销仍小于收益。
- **Release offloading（背景 [[RDMA]] 负载，对象 64B–1KB，每 txn 4 objects）**：相对无 offloading，带宽 −19.1%、吞吐 +18.5%。
- **Priority locking（20% mission-critical，skewed，不同写比例）**：相对 RDMA CAS（FORD 类）mission-critical 平均延迟 −57.1%、tail −50.2%；相对 RDMA FAA（DSLR 类）平均 −52.8%、tail −63.3%；CAS/FAA 基线无法按用户指定优先级调度。
- **扩展性**：TPC-C thread 从 4→16，16 thread 时 vs FORD 吞吐 +72.7%、延迟 −56.7%，vs FaRM 吞吐 1.98×、延迟 −78.1%。3 个 computing node（共 420 coordinators）跑 TPC-C 时 vs FORD 吞吐 +81.8%、延迟 −64.1%，vs FaRM 2.06× / −79.9%。
- **争用敏感度**：warehouse 从 20 降到 8 的高冲突场景，Validation 失败率仅从 8.1% 升到 9.8%；vs FORD/FaRM 延迟 −61.8%/−83.4%，吞吐 +83.2%/2.3×。

## 批判性分析

### 论证链条

主链条清晰：DM 缺 CPU → 不能把 monolithic dtxn 的 multi-phase commit/sync/scheduling 原样搬过来 → 分别用 FCP、RNIC offload、decentralized priority lock 对应 C.1–C.3 → microbenchmark 分解 + OLTP macrobenchmark 验证。从 Table 2 的 RTT 递减到 TPC-C 延迟/吞吐提升，逻辑闭合。

薄弱跳步在于 **绝对性能优势有多少来自 2 RTT，多少来自特定硬件/基准配置**。例如 TATP 与 FORD 打平说明 read-mostly 场景下 HDTX 的 commit 优化不是决定性因素；论文把 FaRM 改成 DM-compatible one-sided 版本作基线，公平性较好，但是否弱于原始 two-sided FaRM 在更大 memory CPU 下的表现未讨论。另一个跳步是 **正确性论证依赖 redo+log+visibility 的组合直觉**，Section 4.7 有 serializability 文字证明，但缺少形式化不变式或故障注入下的 end-to-end 验证。

### 假设压力测试

**已证明**：在 5 节点 ConnectX-3 集群、TPC-C/SmallBank/TATP、2-way DCPMM replication 下，HDTX 相对 FORD/FaRM 的延迟与吞吐优势稳定，高冲突时仍保持优势（warehouse=8）。

**可能失效（推断）**：
- **CXL 或更强 memory-side MCU**：若 future DM node 有足够 CPU 做 local sync，RNIC offload 的带宽收益可能缩小，FCP 的 RTT 优势仍可能保留。
- **更高冲突 OLTP 或 long transaction**：Validation&Commit 合并会导致更多 wasted redo log；论文承认与 FORD 类似，但未量化 abort 率上升时的 crossover point。
- **多副本 / 跨 rack 拓扑**：实验仅 2 memory node；更多 replica 时单 RTT 内 batched Write/Atomic 压力上升，2 RTT claim 可能需要 per-replica pipelining 重测。
- **新 NIC 代际与 cloud 多租户**：Wait/Enable 行为、RNIC 队列深度、tenant 间 RNIC 干扰论文未覆盖。
- **优先级语义**：生产环境 mission-critical 比例、优先级继承、跨服务依赖未定义；大量升 priority 可能伤害 normal txn tail，论文未报告 fairness metric。

### 实验可信度

**强项**：baseline 选 DM 场景最直接的 FORD，并实现 DM-compatible [[FaRM]]；三项技术均有独立 microbenchmark；thread、compute node、contention 三维 sensitivity 较完整；关键数字（72.1%、88.3%、2.08×、67.7%、19.1%）与摘要一致。

**不足**：
- 规模小（5 servers、最多 3 compute nodes），网络 40/56 GbE 偏旧，外推到现代 100G+ 大规模 DM 需谨慎。
- 缺少与更新的 DM dtxn 工作（如 Motor OSDI'24）的直接对比。
- tail latency 主要报告 P99 与 mission-critical 子集，缺少更长尾（P99.9）、故障恢复路径上的延迟测量。
- 能耗、CPU 占用、memory node 侧运维复杂度未报告。

### 系统性缺陷

- **实现与运维复杂度**：RNIC WQ 预置、后台 replenishment、visibility+lock 共编码、lease/deadlock 处理使调试难度显著高于 FORD 式 undo+log；论文未讨论可观测性（tracing 未完成 Release、锁队列状态）。
- **故障恢复**：对 computing node 在 Validation&Commit 后 fail、memory node 在 Release 中 fail、网络分区恢复有协议描述，但**无 fault-injection 实验**量化恢复时间与可用性。
- **隔离与多租户**：单租户 benchmark；RNIC offload 模板、锁 overflow reset 对邻租户影响未讨论。
- **兼容性**：强依赖 InfiniBand RDMA Wait/Enable 语义；移植到 RoCE v2 生态或其他 vendor 需重新验证 Table 1 ordering 与 offload 链。
- **持久化成本**：DCPMM + RDMA Flush 保证 durability，但 flush 开销与 write amplification 相对 DRAM-only DM 未单独 ablation。

## 局限与后续工作

- **局限 1**：规模与硬件代际受限。Future work：在 100G/200G NIC、更多 memory node 与 multi-rack 拓扑上复测 RTT 与带宽收益，并与 [[Motor]] 等更新 DM dtxn 系统对比。
- **局限 2**：高冲突下 Validation&Commit 合并的 wasted log 未建模。Future work：扫 abort rate–conflict 曲线，找出 FCP 相对 FORD 的 crossover，并评估 defer-logging 或 conditional commit 是否更优。
- **局限 3**：优先级调度缺少 fairness/SLO 保证。Future work：在混合 priority 分布下测 normal txn P99、starvation 率，并对比 central metadata service（轻量 memory-side CPU）方案。
- **局限 4**：故障与恢复仅协议级描述。Future work：对 coordinator crash、RNIC hang、partial Release、网络 partition 做 fault injection，测 commit latency 尾部分布与 recovery time。
- **局限 5**：对象模型固定在 ≤1KB hash KV。Future work：variable-size object、range transaction、secondary index 对 FCP 与 offload 链的影响。
- **局限 6**：论文承认 aborted dtxn 仍浪费 log 带宽（与 FORD 类似）。Future work：late logging、validate-before-log 或 hybrid undo/redo 策略在 DM 约束下的 RTT–bandwidth Pareto 前沿。

## 相关

- **相关概念**：[[RDMA]]、[[Disaggregation]]、[[OCC]]、[[Primary-Backup-Replication]]、[[Distributed-Transaction]]、[[Serializability]]
- **同类系统**：[[FaRM]]、FaSST、DrTM+H、FORD、DSLR、Motor、Xenic、FUSEE
- **相关论文**：[[Hermes-ATC25]]（同团队 RDMA PM 复制）、[[RCuckoo-ATC25]]（RDMA disaggregated KVS 设计空间）
- **同会议**：[[ATC-2025]]
