---
type: paper
name: Soul
full_title: "Efficient and Scalable Synchronization via Generalized Cache Coherence"
authors: [Yanpeng Yu, Seung-seob Lee, Lin Zhong, Anurag Khandelwal]
venue: OSDI
year: 2026
tags: [cache-coherence, synchronization, disaggregated-memory, cxl]
source_pdf: "[[osdi26-yu-yanpeng.pdf]]"
source_md: "[[osdi26-yu-yanpeng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 把锁下沉到广义缓存一致性协议

> **原题**：Efficient and Scalable Synchronization via Generalized Cache Coherence

> **一句话总结**：分离式共享内存中的传统锁会在高延迟网络上重复执行一致性通信；Soul 把锁看成缓存一致性在时间和空间上的推广，用 wait queue 延长权限、用 shared memory list 绑定锁与数据，在 8 个 Ethernet compute blade 上把读密集 KV store 提升到 37.1 Mops，同时只用一次 coherence transaction 获取锁和数据。

## 问题与动机

Page-based 分离式共享内存（disaggregated shared memory）把 compute blade 的少量本地 DRAM 当作远端内存的 cache，并用目录式协议维持跨 blade 一致性。普通多核机器的 cache-to-cache 通信约为 20–100 ns，而论文所用 Ethernet-based MIND 的 page coherence 延迟约为 5–10 µs。把原有 pthread、MCS、Cohort 等锁直接叠在这层协议上，会让一次 lock 操作触发多次跨 blade coherence transaction。

这个开销会进入应用主路径。Twitter KV workload 上，Cohort lock 的请求延迟从单 blade 的少于 10 µs 增到 8 blade 的大于 1 ms，且大部分时间花在同步。另一个方向是绕过 coherence，单独建立 lock service；纯软件服务比交换机加速的 memory access 慢，而 programmable switch 的计算和存储又不足以同时实现复杂锁、数据搬移和 locality 优化（§2，图 1–3）。

论文提出一个更直接的问题：既然锁和 cache coherence 都要维持“单写者或多读者”（single-writer/multiple-reader，SWMR），能否小幅扩展 coherence protocol，让它原生完成锁语义，从而不再让锁层和一致性层重复通信？

## 关键观察 / 隐含假设

- **观察 1：锁是 coherence 在时间上的推广。** 普通协议只保证 requestor 在一次 instruction 期间拥有某种 cache permission；critical section 需要把这段权限维持到显式 release。把不兼容请求放入 wait queue，就能延迟 invalidation 或 downgrade（§3.1，图 4）。
- **观察 2：锁是 coherence 在空间上的推广。** 固定 cache line 只保护一个 page/line，而 critical section 可能覆盖任意大小、甚至不连续的共享状态。Shared memory list 把多个 region 绑定为一个 coherence domain，使锁和相关数据一起移动或失效（§3.2，图 5）。
- **观察 3：协议融合带来传统 lock service 难做的两项优化。** Acquisition 可以在同一次 coherence transaction 中返回锁与数据；release 后，若没有冲突 request，锁和数据仍留在本地 cache，继续利用 temporal locality（§3.3）。
- **假设 1：底层是可扩展的目录式 coherence。** GCP 的正确性论证覆盖 MSI、MESI、MOSI、MOESI，但部署需要修改 cache controller 和 directory；它不是只替换用户态 lock library 就能在任意现有机器上工作（§3.4、§4）。
- **假设 2：应用使用明确的 reader-writer critical section。** 当前 Soul 只提供基本 acquire/release，对 timeout、try-lock、显式 abort 等 API 留待未来；application-level nested-lock deadlock 仍由程序员处理（§4.3、§7）。
- **假设 3：网络提供可靠、按序且无丢包的 coherence transport。** Ethernet 实现依赖 lossless RoCE/PFC 和 RDMA RC，因此没有处理 message loss 或 reordering；compute/memory blade failure 也沿用 MIND 的不可恢复模型（§4.4）。

## 核心方法

**GCP 的时间推广。** `GCP_acquire(addr, perm)` 请求 Shared 或 Modified permission。如果现有持有者与请求冲突，directory 不立即 invalidation，而是把请求转到 wait queue；持有者调用 `GCP_release` 后才处理队首，再由 `GCP_is_acquired` 告知请求成功。为避免 thread 被换出或 lock line 被驱逐后意外丢锁，GCP 加入“已驱逐但仍被锁定”的 transient state；新请求仍按 permission compatibility 排队（§3.1，表 1）。

**GCP 的空间推广。** `GCP_create` 把若干 `(address, size)` region 组成不重叠的 shared memory list，`GCP_destroy` 再拆回普通 line。创建和销毁会广播到所有 blade、directory，并 flush 涉及的 cache。Wait queue 本身已经保证锁正确性；memory list 只是把 lock-protected data 合并到同一次移动中的性能优化（§3.2）。

**Soul 的 queue transfer。** 在 Ethernet 上把 wait queue 放在 switch directory 会增加 dequeue round trip，并消耗 ASIC 资源。Soul 让 queue 只驻留在当前 writer，或在多个 reader 后等待的下一个 writer；reader 从不保存 queue。Writer release 时把 queue 直接传给下一个 writer。Directory 和 holder 各维护 version counter，只有两者一致时才允许原子 transfer，避免转移期间的新请求落在错误队列（§4.1，图 6–7）。

**Metadata placement。** 每 page 的 queue 长度最多为 compute blade 数 $n$，compute kernel 侧约需 $n\log n$ bits；directory 再用 $2\log n$ bits 记录 holder 和 version。8-blade 配置下，kernel 和 switch metadata overhead 分别少于 0.2% 和 8%。Shared memory list 放在 compute kernel 而不是 switch，每个 page 增加 9 bytes，开销不超过 0.3%（§4.1–§4.2）。

**兼容标准 lock API。** 用户态 shim 提供 C 的 `pthread_rwlock` 和 Rust 的 `std::sync::RwLock`。先用普通软件锁在单 blade 内区分 thread，再用 GCP 做 blade 间锁；同一 blade 最多连续复用 global lock 64 次，以避免远端 starvation。Rust API 知道受保护 object，可自动建立 shared memory list；C pthread API 缺少 object 信息，默认只能保护 lock 所在 page（§4.3，图 8、表 2–3）。

**资源与故障管理。** In-kernel lock manager 拒绝重叠 memory list，并默认只允许 GCP page 占本地 DRAM cache 的 6%；超过上限时回退到 coherence 上的 `pthread_rwlock`。Process crash 后回收其 GCP metadata；switch state 随 MIND 复制并恢复，但 compute 或 memory blade failure 不恢复（§4.4）。

## 设计取舍

- **在协议层融合换取部署侵入性。** 一次 transaction 可以同时拿到锁和数据，但必须修改 compute kernel 的 cache controller 与 programmable-switch directory；“应用透明”不等于“基础设施无需改动”。
- **把 queue 放在 writer 换取转移协议。** 本地 dequeue 避免网络等待和 switch 存储，却需要 versioned queue transfer；高 churn 下的 retry 次数没有单独测量。
- **共享数据绑定换取更新成本。** Stable Rust object 可以自动受益；critical section 中大小变化的 object 必须 `destroy`、`create`、全局广播和 flush，正确但昂贵。
- **Hierarchical locking 换取 thread 语义。** GCP 只认识 blade/cache，单机软件锁补上 thread 粒度；64 次 local reuse 是公平与 locality 的固定折中，论文没有做参数敏感性实验。
- **现实硬件验证和未来互连模拟分开。** Soul 的主系统在 4KB-page、5–10 µs Ethernet coherence 上运行；SoulCXL 只在 gem5 中使用 300 ns optimistic round trip，不能当作 CXL 3.0 实机结果。

## 实验与结果

- **平台、工作负载与基线**：Ethernet 实验有 8 个 compute-blade VM，每个 512 MB DRAM cache、10 个 application core，连接 6.4 Tbps Tofino switch 和一个 memory blade；应用使用 MIND-KVS 的 Twitter cluster 3/10/53、YCSB A/B/C，以及 Kyoto Cabinet 的 1/10 warehouse TPC-C。基线包括 Pthread、Percpu、MCS、Cohort，以及按 FissLock 逻辑重实现并加入 cohorting 的 Lock Service；原 FissLock 因兼容问题没有直接运行（§5）。
- **MIND-KVS**：8 blade 的 read-only YCSB-C 上，Soul 达 37.1 Mops，对 Pthread、Cohort、MCS 和 Lock Service 高 2–3 个数量级，并随 blade 近线性扩展；Percpu 在纯读时接近 Soul，但加入 1% write 的 Twitter cluster 3 后明显下降。Cluster 10/53、YCSB-A/B 等写密集 workload 即使用 Soul 也不随 blade 扩展，说明 Ethernet inter-cache latency 仍是硬边界（§5.1，图 9）。
- **Kyoto Cabinet**：Soul、Cohort 和 Lock Service 的吞吐相近，且 blade 越多吞吐越低。原因是 TPC-C 通过一个 global exclusive lock 串行 transaction，既不能利用多 reader，也不能把细粒度 bucket data 与锁一起移动；该结果说明 GCP 并非对所有同步 workload 都有数量级收益（§5.1，图 10）。
- **机制与消融**：8 blade 单锁 microbenchmark 中，Soul 的 lock+4KB data acquisition 平均为 100–200 µs，比最快 layered lock 低约一个数量级，并且不论 read/write 比都只触发一次 coherence transaction。去掉 locality optimization 会让 latency 增加 1–2 个数量级；去掉 combined-data optimization 会多一次远端 data fetch（§5.2–§5.3，图 11–12）。
- **正确性与 CXL case study**：Murphi 对由 ProtoGen 生成的 MSI/MESI/MOSI/MOESI 模型检查 mutual exclusion 和 deadlock freedom，但状态空间只有一个 address、两个 data value、三个 blade。SoulCXL 在 gem5 的 16 host、128 core、300 ns CXL 模型中，相对最近基线在 Twitter workload 最多快 1.7×、YCSB 最多 2.0×；它把 memory list 限制成 64B–2MB、2 的幂大小的单段连续区域，regular 64B line 增加 4 bits（§3.4、§6，图 13–16）。

## 论断—证据表

| 论断 | 直接证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Layered lock 的重复 coherence 是主要瓶颈 | Cohort 请求延迟从少于 10 µs 增至大于 1 ms；microbenchmark 同时报 transaction 数和 latency | MIND 的 page-based Ethernet coherence | 强 |
| GCP 能用一次 transaction 获取锁与数据 | 8-blade microbenchmark 中 Soul 始终为一次 transaction，latency 100–200 µs | 单锁、4KB data；未覆盖复杂 nested critical section | 强 |
| Soul 可显著提升读密集真实应用 | YCSB-C 达 37.1 Mops，较多数基线高 2–3 个数量级 | 细粒度 KV bucket；写密集与 global-lock workload 不扩展 | 强 |
| 两项 coherence-aware optimization 都重要 | 分别关闭 locality 与 combined-data 后 CDF 明显右移 | 消融是单锁 microbenchmark，不是端到端应用分解 | 中强 |
| GCP 可推广到 CXL coherence | gem5 上 Twitter/YCSB 最多 1.7×/2.0×，metadata 面积估计少于 0.7% | 模拟、optimistic 300 ns、简化成单连续 region | 中 |

## 批判性分析

### 论证链条

论文从 transaction 数解释应用退化，再把 SWMR 统一成时间和空间两种推广，随后用 model checking、完整 MIND 实现、microbenchmark 和应用结果逐层验证，论证链条很完整。尤其是 Kyoto Cabinet 和写密集 workload 的负结果，准确划出了收益来源：Soul 消除的是冗余 coherence，不会消除共享数据本身的串行化或远端 writer 传递延迟。

### 假设压力测试

应测试 shared object 在 critical section 中频繁扩缩时，`destroy/create + broadcast + flush` 是否抹掉收益；让 GCP pages 超过 6% cache，观察回退后是否出现性能断崖。网络层需要注入 packet loss、reordering、PFC pause 和 switch failover，而不只依赖 lossless RoCE 假设。对 queue transfer，应构造 writer/reader 快速交替与 blade failure，检查 version retry、公平和锁恢复。

### 实验可信度

真实 programmable switch、8 个 blade、两类应用和 transaction-level 归因让 Ethernet 结论可信；model checking 又补上协议状态机证据。但“unmodified application”需要限定：Kyoto Cabinet 可通过 pthread shim 使用，MIND-KVS 则被 port 成 Rust、将 bucket 对齐到 4KB，并用 Soul API 把 bucket data 与锁组合。FissLock 也不是原系统，而是作者重实现并增强的 Lock Service。CXL 部分完全基于 trace replay 和 gem5，没有实机噪声、真实 controller 复杂度或多 socket contention。

### 系统性缺陷

Soul 只支持基本 reader-writer acquire/release，缺少 try-lock、timeout、abort、condition variable 等常用语义；动态 object 的 memory list 维护也不透明。系统只能从 process 和 switch failure 中回收状态，compute/memory blade failure 不可恢复。每个 GCP line 的 wait queue 随 blade 数增长，directory metadata 上限和 queue-transfer traffic 只评到 8 blade；更大 rack 上的 ASIC 容量与 tail latency 未知。最根本地，方案要求改变 coherence substrate，云厂商必须共同部署 kernel、switch 或 CXL controller 修改，采用门槛远高于纯用户态 lock。

## 局限与后续工作

- 在真实 CXL 3.x hardware 上实现 GCP，测量 controller area、protocol state、tail latency 和多 host contention，而不只依赖 gem5。
- 扩展 try-lock、timeout、condition variable 和可取消请求，并对每种语义重新做 model checking。
- 允许 writer 原地更新 shared memory list，避免动态 Rust object 每次全局 flush；同时验证 overlap region 的安全检查成本。
- 扩到更多 blade，报告 per-line queue、switch metadata、queue-transfer retry、P99 latency 和 hot-lock fairness。
- 注入 transport、switch、compute 和 memory failure，设计不停止整个 coherence domain 的锁恢复协议。

## 相关

- **相关概念**：cache coherence、reader-writer lock、[[Disaggregated-Memory]]、[[RDMA]]、programmable switch
- **底层与未来互连**：MIND、[[CXL]]、RoCE
- **同会议**：[[OSDI-2026]]
