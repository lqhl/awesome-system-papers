---
type: paper
name: Lockify
full_title: "Lockify: Understanding Linux Distributed Lock Management Overheads in Shared Storage"
authors: [Taeyoung Park, Yunjae Jo, Daegyu Han, Beomseok Nam, Jaehyun Hwang]
venue: FAST
year: 2026
tags: [distributed-lock, dlm, shared-disk, gfs2, ocfs2, nvme-of]
source_pdf: "[[fast2026-park.pdf]]"
source_md: "[[fast2026-park]]"
---

# Lockify: Understanding Linux Distributed Lock Management Overheads in Shared Storage (FAST 2026)

> **一句话总结**：观察到 Linux 内核 [[DLM]] 在文件/目录创建时即使低争用也因远程 directory node 通信而严重退化（5 客户端比 1 客户端吞吐掉 86%），Lockify 用 self-owner notification + asynchronous ownership management 把 DLM 延迟从总延迟的 47% 降到 8%，整体吞吐提升 **~6.4×**，逼近 emulated RDMA 方案的 87–88%。

## 问题与动机

[[NVMe-over-Fabrics]] 推动存储 [[Disaggregation]]，云厂商用 [[GFS2]]、[[OCFS2]]、VMFS 等 shared-disk 文件系统让多客户端共享远端块设备；协调依赖 [[DLM]] 的 owner/directory node 模型。传统认知是：DLM 只在 **高锁争用** 时拖后腿，而 HA 场景（primary/backup 仅 primary 活跃）和 trace 显示 **76.1–97.1% 文件很少被多客户端同时访问**，因此低争用下 DLM 应该「几乎免费」。

作者 claim 这条直觉在 **metadata 密集创建路径** 上不成立。实测（单 active 客户端 + 最多 5 个 idle 客户端，NVMe-over-TCP 共享存储）：

- 普通 4KB 顺序/随机读写吞吐 **几乎不随客户端数变化**（I/O 延迟掩盖锁开销）。
- 35,000 次文件/目录创建吞吐 **最多掉 86%**，且问题在 Linux kernel DLM 与 OCFS2 的 O2CB 上均复现。

根因不是 lock acquisition 本身（仅占创建延迟 ~15%），而是 Figure 1 所示 DLM 协议：创建前必须 hash 定位 directory node → 远程查 owner → 向 owner 请求锁；客户端越多，directory node 落在远端的概率越高，TCP 往返成为主导（5 客户端 GFS2 下 DLM 操作占创建总延迟 **47%**）。O2CB 无 directory node，需广播所有客户端查 owner，5 客户端时更慢。

论文目标：在 **不改动 DLM 去中心化、无单点故障** 前提下，针对「新建 lock object」这一可优化窗口，消除不必要的远程往返，而非重做整个 DLM 或转向 centralized metadata（[[Lustre]]、[[Ceph]] 不受此 specific bottleneck 影响，但引入其他争用形态）。

## 关键观察 / 隐含假设

- **观察 1：低争用 ≠ 低 DLM 开销——瓶颈是 directory node 远程查找的概率，而非锁冲突频率。**
  - **依赖假设**：workload 频繁 `create` 新文件/目录；集群有多个已挂载客户端（即使仅一个 active）；DLM 通信走 TCP（与 NVMe-over-TCP 测试床一致）。
  - **可能失效场景**：客户端数极少（单节点永远 local directory+owner）；创建极少、读写为主；或 centralized DLM/FS 架构。创建路径占比低的应用几乎感受不到收益。

- **观察 2：新建文件/目录时 DLM 本就会把 creator 设为 owner——查询 directory node 在语义上是冗余的。**
  - **依赖假设**：文件系统通过扩展接口 `dlm_lock(..., NOTIFY)` 能准确区分「新建对象」与「已存在对象」；父目录排他锁已持有，防止并发同名创建破坏一致性。
  - **可能失效场景**：FS 错误设置 NOTIFY flag 会导致 owner 表不一致；多客户端同时对同一 parent 下同名对象发 self-owner notification 的 corner case 依赖父目录锁 + 延迟释放策略，论文仅 case study 论证，未做大规模 fuzz。

- **观察 3：异步更新 directory node 的 owner 表 + wait-list 重传，可在不阻塞 create 路径的前提下维持 DLM-level consistency。**
  - **依赖假设**：directory node 最终会确认 notification；网络偶发丢包/延迟可通过 timer 重发；crash recovery 时标准 DLM recovery + wait-list 重发足以对齐新 directory node。
  - **可能失效场景**：持续网络分区、directory node 长时间不可达时 wait-list 行为与重传风暴论文未量化；**背景网络拥塞** 实验明确未测（§5.2 末注），高争用 TCP 环境下 kernel DLM 会更差，Lockify 相对收益可能更大也可能暴露重传开销。

- **假设 1：优化目标场景是「多客户端挂载、常态低争用、偶发 metadata 爆发」的 HA / 共享存储部署，而非 HPC 高争用 parallel FS。**
  - **证据强度**：强——motivation 测量与 Postmark/Filebench 低争用配置直接对准该假设；高争用 mdtest（5 客户端同 parent）下 OCFS2 仅 **1.09–1.11×**，说明假设边界清晰。

- **假设 2：5 节点 testbed + GFS2/OCFS2 足以代表 Linux shared-disk 生态的主要 pain point。**
  - **证据强度**：中——覆盖两种代表性 FS 与两种 DLM（kernel DLM、O2CB），但未含 VMFS、cluster LVM/MD；规模外推到数十上百节点需假设 hash 分布与网络拓扑仍类似。

## 核心方法

Lockify 实现于 Linux 6.6.23 内核 DLM 之上，对 [[GFS2]]/[[OCFS2]] 做极小补丁，核心是利用「创建时无 prior owner」这一 DLM 既有语义。

**Self-Owner Notification（回应观察 2）**：发起 create 的节点不再向 directory node **查询** owner，而是直接 **通知** 自己为 owner，本地立即授予锁并返回文件系统；directory node 异步更新 lock-owner table 并回确认。跳过 table lookup，CPU 也更省。

**Extended Lock Acquisition Interface**：新增 `NOTIFY` flag。仅新建对象走 fast path；对已存在对象的 open/read/write 仍走标准 directory lookup → owner request（§3 已证此类路径通信开销相对 I/O 可忽略）。把「何时可 self-own」的语义留在 FS 侧，DLM 改动面可控。

**Asynchronous Ownership Management（回应观察 3）**：
- 每笔 notification 插入 **wait-list**，未在时限内收到确认则重发。
- Crash recovery：在标准 DLM recovery（各 client 向新 directory node 上报 ownership）之外，额外重发 wait-list 中未确认项。
- **Parent directory lock contention**：保持父目录锁直到 (1) ownership 更新完成且 (2) 子实体创建完成；与标准 DLM 不同之处在于 file op 与 ownership 更新 **并发** 进行，不增加额外通信，但依赖父目录锁串行化同目录并发创建。

一致性验证：75 个 xfstests 通用 NFS 建议用例，GFS2/OCFS2 在 kernel DLM 与 Lockify 下通过数 **完全相同**（GFS2 70/75，OCFS2 67/75），表明未引入新的 FS 合规失败。

## 设计取舍

- **收益 vs 一致性风险**：用 optimistic local grant + 异步 directory 更新换取 create 路径零等待；代价是短暂窗口内 directory node 视图滞后，靠 wait-list、重传、recovery 与父目录锁兜底；非形式化验证。
- **收益 vs 适用范围**：仅优化 **新建 lock object**；parent directory 已有 owner 时（高争用同目录创建）无法消除查 owner 往返——OCFS2 高争用仅 **1.09–1.11×** 即受此限。
- **收益 vs FS 耦合**：需要 FS 正确调用 `NOTIFY`；错误集成后果严重，但接口设计刻意最小化补丁范围。
- **边界条件**：**5 客户端、1 active** 的 mdtest/Postmark 最优雅，接近 1-client 理想（Postmark 达理想吞吐 **93–96%**）；**5 客户端全 active 同 parent** 时 GFS2 仍获 **5.2–5.4×**（因其内部去重 parent lock 请求队列），OCFS2 几乎无感；**单客户端** 集群 Lockify **无收益**（本就全 local）。

## 实验与结果

- **低争用 mdtest**（35k 文件/目录，5 客户端 1 active）：Lockify vs kernel DLM — GFS2 **~6.4×**（目录/文件创建），OCFS2 **~2.9×**；DLM 侧延迟占比从 **46.7%** 降至 **8%**（1-client 基准 **4.4%**）。
- **高争用 mdtest**（5 客户端同 parent）：GFS2 **5.2× / 5.4×**；OCFS2 **1.09–1.11×**（parent lock 主导）。
- **Postmark**（500 files，500k transactions）：GFS2 **2.0×**，OCFS2 **1.7×**。
- **Filebench fileserver**：**1.07–1.14×**（I/O 为主，metadata 优化边际小）；**webproxy**：GFS2 **2.5×**，OCFS2 **1.08×**。
- **NFS 对照**：客户端数不影响吞吐，但绝对吞吐极低，说明 shared-disk + DLM 与 NFS client-server 是不同性能曲线，不宜直接替换。
- **vs emulated [[RDMA]] DLM**（单客户端零通信 + NVMe-over-RDMA 存储）：Lockify（5-client TCP）达 **87–88%** 吞吐，论证纯 TCP 集群可逼近硬件辅助低延迟 DLM 的 metadata 创建性能（**非真实 RDMA DLM 实现**，见批判节）。

## Critical Analysis

### 论证链条

Motivation（§3）的 latency breakdown + PDF of lock acquisition time 有力支撑「通信而非争用」叙事，与 Figure 2/5 跨 FS/DLM 的趋势一致，观察 → 设计动机闭合良好。设计三组件各自对应可测瓶颈：self-owner 消 step 3–4 同步等待，NOTIFY 限定 fast path，wait-list 处理异步一致性。Evaluation 从 micro → real-world → xfstests → RDMA 对比层层递进，主 claim「低争用 metadata 创建可大幅加速」证据充分。

薄弱跳步：将 mdtest 的 **6.4×** 概括为「overall throughput ~6.4× compared to kernel DLM and O2CB」略宽泛——摘要/结论混用了 microbenchmark 峰值与多 workload 标量；真实负载加速多为 **1.7–2.5×**。把 emulated RDMA 对比说成「comparable」依赖 **人为消除多客户端通信** 的理想下界，不能证明与 [[Citron]] 等真 RDMA DLM 在 high-contention 下等价。

### 假设压力测试

- **客户端规模**：5 节点已足够展示 hash 远端概率问题，但 production HA 集群更大时，若仍仅单 active writer，Lockify 收益逻辑仍成立；若多 active metadata worker，parent lock 与 NOTIFY 正确性压力上升，论文高争用 OCFS2 结果已是预警。
- **网络环境**：无背景流量；云环境 NVMe-oF + DLM 共享 TCP 栈时，Lockify 异步路径可能更少受拥塞影响（论文自述），但 wait-list 重传对 directory node 的风暴效应 **未测量**。
- **Workloads**：偏重 create-heavy；LevelDB/RocksDB 式小文件随机写、或 largely read-only 共享镜像场景收益有限。
- **硬件**：NVMe-over-TCP + 56Gbps；[[RDMA]] 普及的集群可能直接部署 Citron 类方案，Lockify 的定位是 **「只有 TCP 的 cluster FS 栈」** 的 software fix。

### 实验可信度

- Baseline 合理：vanilla kernel DLM（优于 O2CB 故主对比弃 O2CB）、NFS 作架构对照、emulated RDMA 作上界参考。
- 公平性：同一 testbed、同一 kernel 6.6.23、GFS2/OCFS2 默认配置；Lockify 与 DLM 共用 TCP，排除存储路径差异（除 RDMA 小节）。
- 缺口：无 tail latency / P99；无故障注入（network partition、directory node crash 期间 create 延迟）；无 >5 客户端扩展曲线；Filebench webproxy 对 OCFS2 提升小，作者承认需 **进一步 FS 级优化**，但未展开瓶颈。xfstests 通过数相同 **不等于** 覆盖所有 crash consistency 场景，只是 regression 信号。

### 系统性缺陷

- **尾延迟与可观测性**：论文未讨论 NOTIFY fast path 与 wait-list 重传对 P99 create 的影响；运维如何观测未确认 notification 比例、wait-list 深度 **论文未讨论**。
- **资源隔离**：idle 客户端仍参与 DLM 集群成员关系，间接拉低 baseline 吞吐——这恰是论文动机，但也意味着 **挂载数本身** 成为性能变量；Lockify 缓解但未消除「集群越大 hash 越散」的根本统计问题，只是把 critical path 变本地。
- **故障恢复复杂度**：recovery 路径叠加 wait-list 重发，逻辑正确性靠 case study；大规模故障时 directory node 重建与 notification 风暴的 CPU/网络开销 **未量化**。
- **兼容性**：绑定 kernel DLM + NOTIFY 接口；其他 DLM（O2CB）或 userspace FS 需另做移植；与 [[CetoFS-FAST26|CetoFS]] 等解聚 FS 路线的关系论文未讨论（scope 外但部署选型时会相遇）。

## 局限与 Future Work

- **局限 1**：单客户端集群无收益；高争用同 parent 创建时 OCFS2 几乎不加速；parent directory lock 仍是硬瓶颈。
- **局限 2**：仅评估 GFS2/OCFS2、5 节点、无背景网络拥塞；RDMA 对比为 **仿真** 而非实现；NFS 绝对性能差但架构不同，不能作为「DLM FS 普遍慢」的唯一对照。
- **局限 3**：依赖 FS 正确使用 `NOTIFY`；异步 owner 更新的短暂不一致窗口靠工程机制而非形式化证明。
- **Future work 1**：在拥塞网络、更大集群（>5 clients）、更多 shared-disk FS 上测量 wait-list 重传开销与 tail latency，验证收益是否随规模单调。
- **Future work 2**：与 FS 级 parent lock 去重（GFS2 已有）正交优化 OCFS2 等高争用路径；探索能否将 self-owner 思想扩展到其他「creator 即初始 authority」的 distributed metadata 操作。
- **Future work 3**：真实 [[RDMA]] kernel DLM 实现出现后，与 Lockify 做同拓扑对比，厘清 TCP-only 优化在硬件低延迟时代的剩余价值。

## 相关

- **相关概念**：[[DLM]]、[[Distributed-Lock]]、[[Shared-Disk-FS]]、[[NVMe-over-Fabrics]]、[[Disaggregation]]、[[RDMA]]、metadata performance、crash consistency
- **同类系统**：[[GFS2]]、[[OCFS2]]、[[Lustre]]、[[Ceph]]、[[CXFS]]、[[Citron]]（RDMA range lock）、[[CetoFS-FAST26|CetoFS]]（解聚远程 FS 另一 FAST'26 路线）
- **同会议**：[[FAST-2026]]
- **对比**：Lockify 优化 decentralized kernel DLM 的 create fast path；[[Citron]] 面向 high-contention + one-sided RDMA；centralized [[Lustre]]/[[Ceph]] 规避 distributed directory node 查找但引入不同 metadata 争用形态