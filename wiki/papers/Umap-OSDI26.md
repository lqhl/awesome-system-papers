---
type: paper
name: Umap
full_title: "Umap: Revisiting Memory-mapped I/O on Distributed File Systems for Efficient Matrix Access (Operational Systems)"
authors: [Yongchao He, Guangyan Zhang, Zane Cao, Wenfei Wu]
venue: OSDI
year: 2026
tags: [distributed-file-system, memory-mapped-io, user-space-cache, matrix-access, disaggregated-storage]
source_pdf: "[[osdi26-he-yongchao.pdf]]"
source_md: "[[osdi26-he-yongchao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Umap：为分布式文件系统重做文件映射式矩阵访问（OSDI 2026）

> **原题**：Umap: Revisiting Memory-mapped I/O on Distributed File Systems for Efficient Matrix Access (Operational Systems)

> **一句话总结**：Linux mmap 把 4 KB page fault、内核锁和延迟 write-back 原样带到 DFS，导致文件后备矩阵（file-backed matrix，FBM）比本地文件系统慢 3–10×，还会引发 livelock 和 OOM；Umap 在用户态用请求合并、并发感知 cache protocol 和按需扩容 cache 重做这条路径，在 32-thread random access 中比本地 Optane 上的 mmap 读快 2.8×、写快 8.3×，并在 18 个月生产部署中把已观察到的相关 job termination 降为 0。

## 问题与动机

FBM 通过 mmap 把大文件映射成普通地址空间，让 NumPy、[[PyTorch]]、[[vLLM]] 等程序用指针访问超过物理内存的数据。操作系统按需装入 page、自动 cache 和 write-back，程序接口很简单。问题是，这套虚拟内存路径是为本地低延迟存储设计的；现代集群把存储放到 GPFS、NFSv4 等分布式文件系统（DFS）后，page fault 会变成网络 RPC、metadata lookup 和 distributed lock。

论文在金融回测、科学计算和 AI 共用的生产集群中观察到三类问题：

- mmap 固定发出 4 KB 小 I/O。Direct I/O 从 4 KB 增到 64 KB 时能把 DFS throughput 提高约 3 倍，mmap 却基本不变（§2.2、图 2）；
- 多线程 page replacement 既争 Linux `tree_lock`，又向 DFS 并发申请 distributed lock。32 threads 时，任务 88.9% 的时间处于 iowait；剩余时间中又有 76.1% 花在锁上（图 3、表 1）；
- Linux page cache 会一直扩张到内存吃紧。64 GB cgroup 中并发映射 1–16 个 16 GB 文件时，mapped data 从 16 GB 增到 256 GB；一旦超过内存，完成时间急剧上升（图 4）。

更难处理的是运维不可见性。Page fault、dirty-page flush 和 DFS coherence 都藏在 kernel path 中；生产 job 曾在 iowait 中几十分钟没有进展，scheduler 把它误判成 deadlock 并杀掉。论文报告部署前金融 job 每天约有 10 次这类 livelock，每次损失约 100 core-hours（§6.2）。Umap 的目标不只是加速，而是把隐式 VM 行为变成可调、可观察的显式 I/O 和 cache 管理。

## 关键观察 / 隐含假设

- **观察 1：瓶颈是访问粒度与 DFS 语义不匹配，不是网络带宽不够。** 生产节点的远端带宽大于 25 GB/s，仍比本地 mmap 慢 3–10×；4 KB RPC 和 metadata/lock 才是主要放大项（§1–§2.3）。
  - **设计含义**：保留 4 KB cache block，但先在队列中寻找连续 block，再发更大的 DFS I/O。
  - **依赖假设**：同时存在足够多 pending request，且 random matrix access 仍有一定空间局部性，才能形成合并机会。
- **观察 2：快速远端 I/O 会把内核锁暴露成新瓶颈。** I/O 延迟从 local storage 级别下降到接近 memory access 后，750–2,500 cycles 的 lock cost 不再能被慢 I/O 隐藏；mmap 在 8–16 threads 后反而退化（§2.2、§6.3）。
  - **设计含义**：Cache hit 和大多数 state transition 必须避开全局锁，不能只把 storage 换成更快的 [[RDMA]] network。
- **观察 3：Mapped size 不是有效 working-set estimate。** Sequential scan 的数据通常只访问一次，不应因文件很大就 cache 整个文件；重复 random access 才需要按 reuse distance 增长 cache（§4.3）。
  - **依赖假设**：过去访问序列足以近似未来 reuse，kswapd 的 memory-pressure signal 也能及时触发回收。
  - **可能失效场景**：访问 phase 突变或循环 reuse distance 很大时，旧容量可能过大，缩得太快又会 thrash。
- **观察 4：Throughput 比单次 4 KB latency 更重要。** 目标工作负载是 offline training、scientific kernel、backtesting 和 model loading；它们关心 JCT/aggregate throughput，而不是一个随机 load 的 latency（§3、§6.5）。
  - **边界**：论文明确说 latency-critical、少于 4 KB 的 random I/O 仍应使用 local [[NVMe|NVMe]] mmap。
- **假设 1：跨节点同时修改同一映射很少。** Umap 每个节点维护独立 cache，只在显式同步时写回，不提供隐式 cross-node coherence（§3、§5）。
  - **证据强度**：强，但适用面窄。Data-parallel/read-mostly FBM 符合；shared mutable matrix 可能读到 stale data。
- **假设 2：POSIX DFS 足以承载显式 write-back。** Umap 不修改 GPFS/NFSv4，靠普通 POSIX I/O 实现 DFS-agnostic runtime。
  - **风险**：论文没有给出 process crash、partial write、node reboot 下 dirty block 的 durability 和 recovery protocol。

## 核心方法

### 1. Cache Manager 与地址映射

Umap 提供与 `mmap()` 类似的 `umap()` 接口。每个映射文件有一张 Cache Entry Table（CET）：文件按固定 cache block（CB）大小切段，CET entry 指向当前承载该段的 CB；未装入的 entry 指向一个全局 sentinel CB。4-byte pointer 和 4 KB CB 下，CET metadata 约为文件大小的 `1/1024`（§3、图 5）。

Cache Manager（CaM）有全局 CB pool、tracker 和后台 maintainer。Hit 时通过 CET 直接返回 CB；miss 时 tracker 选一个新建或可复用的 CB，maintainer 准备其状态，Communication Manager 再异步从 DFS 装入。这个 indirection 让 runtime 可以限制物理 cache，而不让 mapped file size 直接决定 RAM 用量。

### 2. PIAO 合并与公平的多通道调度

Communication Manager（CoM）为每个文件维护一对队列（§4.1、图 6）：

- PIAO queue 按 file-segment rank 排序，新的相邻 rank 可以合并为一条较大 I/O；
- FIFO queue 按到达时间保留 request，dequeue 总是从 FIFO 开始，因此等待合并不会让早到 request 永久饥饿；
- 多个 I/O channel 从一个 min-heap 取工作，heap key 是每个文件队列已经发送的 bytes，优先服务累计传输量最少的队列。

合并利用空间局部性，多通道利用 NIC parallel queue，least-first scheduling 则防止大文件独占网络。消融中，只有 CoM 可把单线程 throughput 提高 3.5×，但 8 threads 后不再扩展；再加入 CaM 才接近线性伸缩（§6.4、图 13a）。

### 3. Shadow copy 的显式读写同步

每个 CB 有 data buffer 和同样大小的 shadow buffer。应用访问 data buffer；CB 被换给另一文件段时，Umap 先断开旧 CET mapping，原子交换 `data_ptr`/`shadow_ptr`，后台把 shadow 中的旧数据写回，同时把新 segment 读进新的 data buffer（§4.1、图 7）。Atomic state transition 防止 write-after-read hazard。

这条路径把 Linux deferred flusher 换成 runtime 控制的 POSIX write 和同步 DFS metadata update。它可以 overlap communication 与 computation，也避免很多 dirty page 同时触发 distributed flush；代价是 Umap 自己必须管理 dirty state、write ordering 和 failure recovery。

### 4. 并发感知的无锁 cache protocol

每个运行线程第一次触发 replacement 时取得 thread-local `tid`；每个 CB 的 reference map（rmap）记录正在引用它的线程。Rmap 非空的 CB 不会被 evict；线程离开某 CB 时迁移记录，线程死亡则由 CaM 检查并清理，避免永久 pin（§4.2.1）。

CB 有三种状态（图 8）：active 表示正被线程引用且 CET 仍指向它；semi-active 表示无人引用但 CET 仍命中，可以快速重新激活；inactive 才能用于 replacement，且已从 CET 断开。只有 semi-active→inactive 需要真正 flush/解绑；其他 hit 和状态转换不搬数据。CaM 维持少量 inactive CB，数量低于 logical core 数时才补充回收，让 fast path 不争 Linux 式全局 replacement lock（§4.2.2）。

### 5. 按 reuse distance 懒扩容

Lazy-expansion tracker 把访问序列中，同一 segment 两次出现之间的距离视为需要保留的 cache 容量。首次访问的 segment 走 LRU replacement，不据此扩容；已经见过但仍 miss，说明容量小于 observed reuse distance，才分批增加 CB（算法 1、Theorem 1）。因此单遍 file scan 理论上只需一个 CB，重复 random access 才会增长到能避免再次 miss 的容量。

Tracker 还维护不立即生效的 virtual capacity。访问变化时先在该虚拟 cache 上试算更小容量；Linux kswapd 报 memory pressure 后，才真正释放 current capacity 与 virtual capacity 的差。这是根据历史序列得到的在线 heuristic，不是对未来 workload 的最优保证。

### 6. 集成与一致性

Source-compatible 模式用 wrapper/macro 把 `mmap` 换成 `umap`；binary-compatible 模式通过 `LD_PRELOAD` 拦截 libc mmap，对 DFS path 透明替换（§5）。实现只要求 POSIX file API，不改 application 或 DFS。

接口兼容不等于语义完全相同。Umap 明确采用 mmap-style weak consistency：每个节点的 local cache 只在显式同步时更新 DFS，不做跨节点 implicit coherence。这个选择避免 page-granularity distributed locking，也是性能来源之一；调用方必须保证 concurrent cross-node writes 很少或自行协调。

## 设计取舍

- **批量吞吐换单次延迟。** PIAO 等待相邻 request、CoM 排队并调度 channel，可提高网络利用率，却让单个小 I/O 比 mmap+local NVMe 更慢（图 16）。
- **显式 cache 换可控内存。** Runtime 可按 reuse 扩容和按 kswapd 回收；代价是 CET、双 buffer、rmap、state machine 和后台线程。
- **弱一致性换掉 distributed lock。** Read-mostly/partitioned FBM 很合适，多个节点重叠写同一区域则需要额外 protocol。
- **Shadow write-back 换 failure surface。** 它避免 kernel flush storm，但 dirty state 和 data/shadow pointer 在 crash 时如何恢复，论文没有说明。
- **通用 POSIX API 换 DFS-specific optimization。** GPFS/NFSv4 都能运行；不利用某个 DFS 的 placement、lease、batch API，也无法消除所有 metadata cost。
- **矩阵 workload 换简单 policy。** 该设计依赖较大 request set、重复或局部访问；对 sparse pointer chasing、低并发 latency-critical access 未必合算。

## 实验设计

Testbed 每节点有两张 200 Gbps ConnectX-6 NIC（storage/compute traffic 各一张）、1.82 TB DRAM、双 Intel Xeon 8260（128 logical cores）、3.84 TB Optane NVMe SSD 和 8×A100。远端 backend 分别是共享 GPFS 和 NFSv4；microbenchmark 映射 1–128 GB FBM，扫描 1–32 threads、random/sequential/strided access（§6.1）。

Baseline 是本地 Optane/ext4 上的 Linux mmap-IO 与 FastMap。作者没有在主结果中保留 mmap/FastMap+DFS，因为它们慢几个数量级。这个选择给 Umap 一个较强的“远端 DFS 对本地 NVMe”目标，但也意味着主图同时改变 runtime 和 storage backend；只有 Figure 2 的 direct/mmap characterization、以及 GPFS/NFSv4 间对比，能进一步分离原因。

Real workload 包括：预处理成 matrix format 的 ImageNet training（AlexNet/ResNet/VGG，最多 8 GPU）、[[vLLM]] model loading、OpenBLAS 六个 `2^15 × 2^15` float64 kernel、以及 2020–2025 四个国家市场数据上的 backtrader。指标是 throughput 和 JCT。ImageNet 去掉 decompression，finance 因 production restriction 没跑 FastMap；这些都是解释结果时需要保留的边界。

## 实验与结果

- **AI workload 接近 in-memory，但收益受计算占比限制。** ImageNet training 中，Umap+DFS 相对 mmap/FastMap+local LFS 加速 1.2×–1.9×；computation 已占主导。[[Serverless|Serverless]] [[LLM|LLM]] weight loading 的大 I/O、1–8 threads 更适合 CoM，Umap 相对 mmap 加速 2.3×（§6.2、图 9）。
- **Scientific 与 finance 展示两种收益上限。** OpenBLAS 的 `O(n^3)` computation 和高 cache reuse 让 Umap 只缩短 JCT 13%–28%；I/O-intensive backtrader 最高加速 6.7×，同时 memory utilization 从 mmap 的接近 100% 降到 8%–31%（§6.2、图 10–11）。Finance 只与 mmap 比，没有 FastMap。
- **并发 random access 是最强 microbenchmark。** 128 GB FBM、32 threads 下，Umap+GPFS 相对 mmap+local LFS 的 read/write throughput 为 2.8×/8.3×；mmap 在 8–16 threads 后退化，Umap 到约 190 Gbps 后受 200 Gbps NIC 限制。单线程小 random read 则比本地 mmap/FastMap 低约 20%，说明收益不是无条件成立（§6.3、图 12）。
- **Cache 与通信机制都有独立贡献。** 只有 CoM 时单线程提高 3.5×、8 threads 后停滞；CoM+CaM 才线性增长。Spatial-locality parameter 从 0 增到 1 时，PIAO 平均 merged I/O 从 17.2 KB 增到 127.9 KB。32-thread write 下，Umap memory 少于 mmap 的 10.4%；64 GB cgroup、16–256 GB total mapping 中，任务时间在所有 memory-to-file ratio 下保持稳定（§6.3–§6.4、图 13–14）。
- **Profile 支持“锁和 flush 是根因”。** 32-thread write 中，mmap+DFS 的 iowait/JCT 为 88.9%，non-iowait lock ratio 为 76.1%；Umap 分别为 15.0%/1.2%。CPU cycles 从 `3.4×10^12` 降到 `6.3×10^10`（作者概括为 CPU usage 少 98.2%），CPU migration 少 56.3%。多 process sequential read 时，一个 process 可用大于 95% 带宽，`N` 个 active process 约均分，结束后立即重分配（§6.4、表 1、图 15）。该 fairness 只指 network bandwidth，不包括 memory isolation。
- **生产运行证明了 operational value，但不是 randomized A/B。** 部署前金融 job 约每天 10 次 livelock，thread 最多 90% 时间 iowait，scheduler 误杀每次浪费约 100 core-hours；部署 Umap 后，18 个月内没有观察到相关 livelock 或 job termination，摘要还报告消除了 OOM-induced failure（§6.2、§8）。论文没有给出同时期 workload volume、版本变化和 control cluster，因而强力支持“该环境能稳定运行”，不能单独量化 Umap 的因果 availability 增益。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| Page-granularity mmap 与 block-oriented DFS 存在结构性 mismatch | §2.2、图 2–4：3–10× slowdown、小 I/O 不扩展、88.9% iowait | GPFS/NFSv4、matrix random access、特定 Linux/DFS client | 强 |
| CoM 与 CaM 共同提高并发 throughput | 图 12–14：32 threads 读/写 2.8×/8.3×，CoM-only 不扩展 | 128 GB FBM、200 Gbps GPFS；baseline 在 local Optane | 强 |
| Lazy expansion 以少内存保持性能 | 图 11–13：finance 8%–31%，microbenchmark 少于 mmap 的 10.4% | 所测 reuse pattern、64 GB cgroup；没有 adversarial phase change | 强 |
| Umap 改善真实 workload JCT | 图 9–11：AI 1.2×–2.3×、OpenBLAS 13%–28%、finance 最高 6.7× | ImageNet 预处理、FastMap 未跑 finance、单套硬件 | 强 |
| 显式 path 消除已观察到的生产故障 | §6.2、§8：约 10 incidents/day→18 months 0 termination | 单一内部 cluster，无并行 control 和公开 trace | 中到强 |

## 批判性分析

### 论证链条

论文把三个 production symptom 分别映射到机制：4 KB network I/O→PIAO/multi-channel CoM，replacement lock→rmap/FSA CaM，greedy page cache→lazy expansion；ablation 又显示 CoM 单独提高单线程但不能扩展，加入 CaM 才解决多线程。这条 observation→design→measurement 链很完整。Table 1 的 iowait/lock profile 与 18 个月 deployment 进一步说明，这不是只在 fio 上成立的优化。

需要收紧的 claim 是“drop-in”和“DFS-agnostic”。Umap 可以用 `LD_PRELOAD` 降低改代码成本，也只依赖 POSIX API；但它不提供跨节点 implicit coherence，per-access latency、cache allocation 和 write-back timing 也与 Linux mmap 不同。API 形状兼容不代表所有 mmap application 的 observable semantics 都兼容。

### 假设压力测试

PIAO 的收益随 pending concurrency 和 locality 增加；完全随机、单线程读已经显示 20% regression。若应用只有少量 latency-sensitive access，排队合并得不偿失。若 remote storage 不是有 distributed metadata/locking 的 DFS，而是 EBS/block storage 或 local filesystem，论文也明确说同类病理不一定存在（§8）。

Weak consistency 是更大的 correctness boundary。多个 node 若重叠写同一 FBM，local cache 可能长期看不到对方更新；显式 synchronization 的 API、ordering 和 error behavior 没有展开。Shadow buffer 让计算和 flush overlap，但 process 在 pointer swap、old segment flush 或 new segment fetch 中途 crash 时，哪些 bytes durable、重启如何识别 dirty data，论文没有 fault experiment。

### 实验可信度

两种 DFS、真实 200 Gbps fabric、micro/AI/scientific/finance 四类 workload、机制消融、resource profile 和长期 deployment，证据覆盖很好。尤其单线程 read 的负结果和 network-only fairness 边界写得清楚。

主要混合变量是 storage medium：大部分 headline 将 Umap+remote DFS 与 mmap/FastMap+local Optane 比，而不是相同 backend 上只换 runtime。这个比较有现实意义——目标就是让 disaggregated storage 追上本地——但 2.8×/8.3× 不能全部解释成某一个 Umap mechanism。ImageNet 已去 decompression，finance 不含 FastMap，生产结果没有公开 arrival/access trace，也限制了复现和外推。

### 系统性缺陷

CET、双 buffer、rmap、thread-liveness checking、inactive list、PIAO/FIFO 和 background maintainer 形成一套新的用户态 memory/storage subsystem。论文没有测 fork/exec、process crash、DFS outage、partial write、disk-full、mapping truncation、`msync`/`fsync` error、scheduler restart 或 binary interposition compatibility；这些路径对声称的 operational predictability 很重要。

Lazy expansion 理论针对已经观察到的 access sequence。Phase-changing workload 先扩到旧 reuse distance，再依赖 virtual cache 与 kswapd 缩回；回收响应时间、跨文件 memory fairness 和 cgroup 下多 process 争用没有系统量化。Figure 15 只证明 CoM 的 bandwidth fairness，不能推出 memory isolation。

## 局限与后续工作

- **局限 1**：只适用于带 distributed metadata/locking 的 network filesystem；local/block storage 和低并发小 I/O 未必受益。
- **局限 2**：每节点独立 cache、无 implicit cross-node coherence，不适合重叠写 shared mapping。
- **局限 3**：Headline baseline 同时改变 runtime 与 backend；ImageNet/finance 也各有 preprocessing 或 baseline omission。
- **局限 4**：生产 availability 是单 cluster 前后对比，没有公开 workload denominator、control cluster 或故障分类时间线。
- **局限 5**：未验证 dirty write-back、process/node crash、DFS error 和 `LD_PRELOAD` 边角语义。
- **局限 6**：Lazy capacity、cross-file memory fairness 和 phase change 的收敛时间缺少 sensitivity study。
- **后续工作 1**：在同一 GPFS/NFS backend 上对 mmap、FastMap、Umap 做 controlled breakdown，并同时报告 request size、RPC/metadata count、CPU、network bytes 和 JCT。
- **后续工作 2**：注入 process kill、node reboot、DFS timeout、partial write、ENOSPC 和重复 flush，验证 dirty-block durability、ordering、idempotence 与 recovery time。
- **后续工作 3**：重放 locality/concurrency/phase-change 网格，画出 Umap 相对 mmap 的 throughput–single-access-latency break-even surface。
- **后续工作 4**：在 API 中显式声明 read-only、partitioned-write、shared-write mode；unsupported coherence case 应 fail fast，而不是静默读旧值。
- **后续工作 5**：对多个 cgroup/process 做 memory+bandwidth joint fairness，报告 cache growth/reclaim delay、OOM、JCT slowdown 和 noisy-neighbor isolation。

## 相关

- **相关概念**：[[Memory-Mapped-IO]]、[[Page-Cache]]、[[Disaggregation]]、[[RDMA]]、file-backed matrix
- **相关系统**：GPFS、NFSv4、FastMap、[[vLLM]]、[[PyTorch]]
- **同会议**：[[OSDI-2026]]
