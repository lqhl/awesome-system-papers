---
type: paper
name: uCache
full_title: "uCache: A Customizable Unikernel-based IO Cache"
authors: [Ilya Meignan-Masson, Masanori Misono, Viktor Leis, Pramod Bhatotia]
venue: FAST
year: 2026
tags: [io-cache, unikernel, mmap, nvme, page-cache]
source_pdf: "[[fast2026-meignan-masson.pdf]]"
source_md: "[[fast2026-meignan-masson]]"
---

# uCache: A Customizable Unikernel-based IO Cache (FAST 2026)

> **一句话总结**：观察到 [[mmap]]/[[Page-Cache]] 在 [[NVMe]] 高并发下因全局锁与 TLB shootdown 严重失速，而 userspace cache（[[vmcache]]、[[SPDK]]）虽快但缺乏文件系统通用性；uCache 基于 [[OSv]] [[Unikernel]] 单地址空间，用共享 VMA + 策略 hookpoint + lock-free PTE 操作 + uVFS/uStore 把 OS 级 cache 做成应用可定制，相对 mmap 最高 **55×** 插入吞吐、相对 SPDK 仅 **3.5%** 平均 IO 开销，并在 TPC-C / TPC-H 真实用例中接近专用方案。

## 问题与动机

数据密集型云应用（KV store、[[DuckDB]] 类分析库、[[DBMS]] buffer manager）普遍依赖 load/store 风格的 IO cache 来摊薄持久化访问。长期存在两难：

- **OS 级 cache**（[[mmap]] + kernel page cache）：编程简单、透明，但 Linux 实现在高带宽 [[NVMe]] 上遭遇全局锁、慢 page fault、TLB shootdown、VMA 管理扩展性差；POSIX `madvise`/`mlock` 粒度粗，无法表达事务语义（未提交事务页被驱逐）、非硬件页大小（8KiB/16KiB）、或云 object store 等非文件系统后端。
- **Userspace cache**：可定制替换策略、可用 kernel-bypass（[[SPDK]]），但需 pin/unpin 或 userfaultfd 等复杂集成，往往独占设备、难复用成熟文件系统，且每应用一套实现。

作者的核心 claim 不是「再优化 Linux page cache」，而是：**在 unikernel 上重新定义 OS 级 IO cache 抽象**，同时保留 mmap 式透明访问与应用级语义注入能力。边界是：单节点、单地址空间、需接受 unikernel 部署模型；不解决多节点共享存储一致性。

## 关键观察 / 隐含假设

- **观察 1**：out-of-memory 随机访问下，Linux mmap 的 page fault 路径在 >16 线程后几乎不再扩展，而 IO 本身并非唯一瓶颈——页表操作、TLB invalidation、全局锁占显著比例。
  - **依赖假设**：workload 以 cache miss + eviction 为主（论文 microbenchmark 刻意跑满 1TiB 文件 / 100GiB 物理内存），代表内存受限的随机访问，而非纯 cache hit 场景。
  - **可能失效场景**：工作集完全驻留内存时，uCache 相对 mmap 的优势可能大幅缩小；论文对「高 hit ratio、低争用」路径着墨较少。

- **观察 2**：userspace 高性能来自应用与 cache 的紧耦合（事务锁页、列式预取、自定义 resident set），但传统 OS 隔离使这种知识只能通过昂贵 syscall（`madvise`、自定义 kernel module [[exmap]]）或完全 userspace 重实现传递。
  - **依赖假设**：应用愿意（或能够）在 unikernel 镜像里与 cache 库静态链接，策略回调可直接访问应用符号；部署环境可跑定制 unikernel 镜像（AWS/GCP custom image）。
  - **可能失效场景**：需要 fork-per-connection（如 PostgreSQL）、多租户混部、或无法改镜像的 legacy 部署；此时 unikernel 模型成为硬门槛。

- **观察 3**：kernel-bypass IO（SPDK）与 OS 文件系统栈在性能上 dichotomy，但云应用仍需要 ext4 等成熟 FS 做元数据/兼容。
  - **依赖假设**：可通过「控制路径走 FS、数据路径 bypass block layer」的混合 uStore（MiniFS + per-core NVMe queue pair）同时拿到两者；文件块布局在打开后静态（预分配、无 sparse、无并发 resize）。
  - **证据强度**：**中**——NVMe 微基准接近 SPDK，但原型仅 ext4 + 预分配文件，S3/远程 Parquet 只在讨论中提出、未完整评测。

- **假设 1**：消除 syscall / 特权边界后，callback 式策略扩展无需 [[eBPF]] 沙箱即可安全且高效。
  - **证据强度**：**弱至中**——性能上成立（无 verifier 开销），但论文承认 unikernel 内应用以特权运行，仅依赖 hypervisor 间隔离；恶意或 buggy 策略可破坏整个 VM。

## 核心方法

uCache 在 [[OSv]] 上实现为约 2000 LoC C++ 库，介于应用与存储之间，分三层回应上述观察。

**共享 VMA + 双模接口（回应观察 2）**：每个 cache region 对应单一 VMA（非 Linux 式多 VMA 切分），内部按应用选定 Buffer 粒度（4KiB–64KiB，可非硬件页大小）管理。`mmap(file, bufSize, uStore, residentSet)` 创建映射；日常用 load/store 透明访问，也可用 `ensureCached`/`evict`/`prefetch`/`msync` 显式控制。`setPolicy()` 在 page fault 路径注册 hook：`needToEvict`、`chooseEvictionVMAs`、`chooseEvictionBuffers`、`isEvictable`、`choosePrefetchBuffers` 等，粒度从 global 到 per-Buffer；默认 CLOCK，可换 resident set 数据结构（FIFO 用 queue、CLOCK 用 hash table）。

**Lock-free cache manager（回应观察 1）**：插入用 CAS 写 PTE 物理地址（present 位后置 1），并发 fault 时 loser 轮询等待；驱逐先 writeback、清 present、IPI 做 TLB shootdown，再 CAS 清 PTE，失败则乐观回滚。页表中间级预分配，额外内存约 0.2%。支持多页 Buffer 的批量 PTE 更新，使非 4KiB 粒度与 batch eviction 可扩展。

**uVFS / uStore（回应观察 3）**：uVFS 以 Buffer 对象为粒度抽象 `uOpen/uRead/uWrite/uAread/uAwrite`，解耦 cache 与后端。应用可插自定义 uStore；内置 NVMe uStore 借鉴 SPDK（zero-copy、per-core queue pair、polling/interrupt 可选），MiniFS 把 `uOpen/uClose` 和 LBA 查询委托给 [[ext4]]（lwext），数据路径直连驱动。offset→LBA 映射缓存为数组，元数据开销约文件大小的 0.2%，但限制原型仅支持预分配、非 sparse、打开期间无结构变更的文件。

**三个用例验证设计闭环**：
1. **mmap drop-in**：几乎不改代码替换 mmap。
2. **[[vmcache]] 移植**：删 ~400 LoC、改 ~100 LoC，用 `isEvictable()` 与 DB 锁协调，保证事务安全驱逐。
3. **DuckDB Parquet**：~100 LoC 接入列式预取逻辑，本地 Parquet 加速；远程 S3 需 HTTPFS + uVFS 适配（future）。

## 设计取舍

- **Unikernel 共生 vs 通用 OS 兼容**：为去掉 syscall 与共享符号，放弃标准 Linux 进程模型；换来 mmap 式简单性 + userspace 级策略控制。多进程、fork、内核模块生态均不可用。
- **策略 callback 原生执行 vs 安全隔离**：选择极致性能（类似 unikernel 内联 eBPF），牺牲策略代码错误时的故障域隔离；论文引用 MPK 等作为潜在补救，未集成。
- **MiniFS 混合路径 vs 纯 SPDK**：保留 ext4 兼容性，但原型绑定单一 FS、静态文件布局；灵活 uStore 接口已设计，工程覆盖仍窄。
- **边界条件**：在 NVMe 本地、多线程、内存配额紧张、随机访问时设计最优雅；纯顺序扫描、极小文件、或需动态 truncate/sparse 文件时，LBA 缓存与预分配假设可能变脆。

## 实验与结果

实验平台：单路 AMD EPYC 9654P（96 核，OSv 限 64 核）、768GiB RAM、Kioxia CM-7 NVMe，VM 直通透传；线程 pin 到核，THP 关闭。

- **Cache 插入 microbenchmark**（1TiB 文件 / 100GiB 内存，持续 fault+evict）：uCache 相对 Linux mmap 最高 **55×**（64 线程只读 4KiB）；线程扩展近线性（15.5k→14k ops/s per thread）。延迟分解：IO 占 89–98%，TLB flush 占 0.4–6.8%，页表/分配仅占 ~1–4%。
- **NVMe uStore**：相对 SPDK 平均 **3.5%** 开销；相对 libaio 平均快 **50%**、最高 **150%**（32 线程 batch 128）。
- **mmap 替换（随机 KV）**：128GiB 配额 **≥46×**、16GiB 配额最高 **78×**；缩内存时 uCache 保留 43% 峰值性能 vs mmap 仅 25%。
- **vmcache + TPC-C**（5000 warehouse ≈1TiB，128GiB cache，64 线程）：uCache **~118k tps**，[[exmap]] **~121k**（≈3% 差距），madvise 版 **~90k**。
- **DuckDB Parquet + TPC-H**（SF=300 ≈80GiB，20GiB cache，64 线程）：平均 **1.98×**；Q4 **4.89×**、Q6 **6.59×**、Q17 **3.17×**；原版 OOM 的 Q7/Q9/Q18/Q21 可跑通。
- **内存 footprint**：1TiB 区域 + 128GiB 物理 cache + 4KiB Buffer → 元数据 **2.25GiB**（物理内存 **1.7%** 增量）。

## Critical Analysis

### 论证链条

观察（mmap 不可扩展 + 语义鸿沟）→ unikernel 去隔离 → 共享 VMA/hookpoint → lock-free PTE → uVFS 解耦 IO：逻辑链闭合良好。最强证据在 **故意制造 worst-case fault storm** 的 microbenchmark 和作者自己擅长的 **vmcache/TPC-C** 线；mmap 替换与 DuckDB 用例证明「少改代码也能受益」。薄弱环节在于：多数对比是 **Linux mmap vs OSv+uCache**，而非同一 OS 内 ablation；mmap 差多少有一部分来自 OSv vs Linux 栈差异，论文未完全剥离。

把 microbenchmark 的 55× 外推为「消除 data-intensive 应用 IO cache 瓶颈」略激进——该数字对应持续 miss+evict；真实 DB 热点页命中后，瓶颈可能回到计算或网络。DuckDB 平均 1.98× 更贴近实务，但也依赖 Parquet 列式预取与有限 cache 尺寸。

### 假设压力测试

- **部署**：公有云需 custom unikernel image + NVMe passthrough；无 fork 阻碍 PostgreSQL 式多进程架构（论文承认，引 uFork 等为 future）。
- **存储后端**：S3/远程 object store 是动机之一，但评测几乎全在本地 ext4+NVMe；HTTPFS+uVFS 仍待验证。
- **文件语义**：预分配、非 sparse、无并发 resize——analytics load 常见，但通用 FS 工作负载（日志追加、稀疏文件、在线 DDL）可能踩原型限制。
- **规模**：OSv 64 核上限、单 socket 评测；未测 multi-tenant、多 VM 共盘、或 disaggregated storage 下一致性。
- **安全/运维**：策略回调与 cache manager 同特权；论文未讨论可观测性、在线升级、故障注入下的行为。

### 实验可信度

- **Benchmark 代表性**：TPC-C/TPC-H、随机 KV、Parquet 列扫均贴近 claim 的 data-intensive 场景；缺 production cloud trace（如 S3 读放大、多租户干扰）。
- **Baseline 强度**：对比 mmap、SPDK、libaio、vmcache+madvise、vmcache+exmap 较完整；未与 [[TriCache]]、Aquila、libDBOS、最新 [[eBPF]] cache 策略（FetchBPF、PageFlex、cache_ext）同台。
- **Ablation**：有 NVMe uStore vs SPDK、Buffer 尺寸、延迟分解；缺「去掉 lock-free」「去掉 hookpoint 仅用默认 CLOCK」等设计分解实验。
- **Metric**：侧重吞吐/tps/查询时间；**尾延迟、隔离性、恢复时间、CPU 效率**几乎未报。

### 系统性缺陷

- **多节点一致性**：明确不提供跨节点同步；disaggregated architecture 需应用层或外部服务协调——与 mmap 同级，但 cloud 共享存储场景下仍是硬缺口。
- **Crash consistency**：与 mmap 相同，durability 仍靠应用 + `msync`/`writeback`；`isEvictable` 可辅助 DB 日志语义，但无新的一致性协议。
- **可观测性 / 运维**：论文未讨论 metrics、tracing、策略热更新；unikernel 镜像调试成本高于 Linux。
- **资源隔离**：单地址空间内策略 bug 可损坏全局状态；hypervisor 仅隔离 VM 间。
- **兼容性成本**：端口到 uCache 分两步——先 port 到 unikernel，再按需加 policy；mmap drop-in 简单，语义定制仍需理解 hookpoint 模型。

## 局限与 Future Work

- **局限 1**：原型仅 ext4、预分配非 sparse 文件、打开后不可并发改文件结构；LBA 全量缓存限制大文件/动态布局场景。
- **局限 2**：unikernel 无 fork、策略无沙箱、评测单机本地 NVMe 为主——云原生多租户与远程存储仅停留在设计层面。
- **局限 3**：内存元数据随映射区域线性增长（约 16 bytes/Buffer 槽位），超大映射有 1–2% 级物理内存税，极端 scale 需重新设计 resident set / LBA 索引。
- **Future work 1**：量化 HTTPFS/S3 uStore + Parquet 远程缓存的端到端收益与一致性代价。
- **Future work 2**：在相同 hardware 上做「Linux + exmap/eBPF」vs「OSv + uCache」控制变量实验，剥离 OS 栈差异。
- **Future work 3**：结合 MPK/uFork/hypervisor NVMe pass-through（NVMePass）测量云部署下的尾延迟与多租户干扰。

## 相关

- **相关概念**：[[mmap]]、[[Page-Cache]]、[[Unikernel]]、[[NVMe]]、[[Buffered-IO]]、Virtual Memory Area
- **同类系统**：[[vmcache]]、[[exmap]]、[[SPDK]]、[[DuckDB]]、TriCache、Aquila、libDBOS、CO-PAGER、FetchBPF
- **同会议**：[[FAST-2026]]
- **对比**：OS-level mmap vs userspace SPDK——uCache 试图占据中间地带；与 [[WSBuffer]]（改 Linux kernel page cache 写路径）正交，前者换 runtime 模型，后者保留通用 OS