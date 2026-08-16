---
type: paper
name: DINGO
full_title: "Scaling the IO wall with Declarative IO"
authors: [Sanjith Athlur, Sara McAllister, Theo Gregersen, Timothy Kim, Yiwei Chen, Sarvesh Tandon, Lucy Wang, Daniel S. Berger, Saurabh Kadekodi, Arif Merchant, Benjamin Berg, Nathan Beckmann, Rashmi Vinayak, George Amvrosiadis, Gregory R. Ganger]
venue: OSDI
year: 2026
tags: [distributed-storage, hdd, maintenance-io, io-scheduling, caching]
source_pdf: "[[osdi26-athlur.pdf]]"
source_md: "[[osdi26-athlur]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用声明式 IO 跨越存储 IO 墙（OSDI 2026）

> **原题**：Scaling the IO wall with Declarative IO

> **一句话总结**：DINGO 让维护任务提前声明“需要读哪些数据、最晚何时完成、是否只需候选数据中的一部分”，再把不同任务对同一块数据的读取排到一起；HDFS 原型少读 26%，100 PB 仿真少用 28%–51% 的维护读 IO，并在论文的容量模型中把可支持的 HDD 从 36 TB 提高到 64 TB。

## 问题与动机

HDD 容量仍在增长，但单盘带宽和 IOPS 没有同比增长。结果是每 TB 能分到的 IO 越来越少：盘虽然装得下数据，却来不及完成可靠性和空间管理工作。论文把这个容量受 IO 限制的现象称为 **IO 墙（IO wall）**。在论文采用的模型里，若前台应用固定占一半磁盘时间、维护读需求为 2 MB/s/TB，命令式系统到 36 TB 盘就触及上限（图 1、图 3）。

缓存也不能直接解决它。容易复用的前台读大多已被 DRAM/SSD cache 吸收，真正到达 HDD 的请求越来越多是 scrubbing、reconstruction、rebalancing、[[Garbage-Collection|garbage collection]]、transcoding、fsck、geo-replication 等扫描型维护任务。六家 hyperscaler 的数据表明，这些任务至少占 after-cache HDD IO 的 45%–70%；“至少”很重要，因为未归类的上层维护 IO 被计入了应用 IO（§3.2）。

这些任务单独看几乎没有短期复用，但任务之间会读到相同 block。例如 scrubbing 会扫过所有数据，天然与其他任务重叠。问题在于各任务来自不同团队和软件层，普通 `read/get` 只表达“现在读这个 block”，既看不到 deadline，也看不到访问顺序和数据选择的自由度，所以相同数据常相隔几天才被读取。

## 关键观察 / 隐含假设

- **观察 1：维护 IO 不只是大，而且随容量增长。** Hyperscaler B 的数据估计，每增加 1 TB HDD 容量，维护任务会多占约 0.9% 的磁盘时间（§3.3）。因此不能指望“盘越大、平均数据越冷”自动摊薄维护成本。
  - **隐含假设**：未来的故障率、编码方式和维护频率与测量期相近；如果介质可靠性或维护算法发生根本变化，这个斜率会变。
- **观察 2：跨任务重用存在，但传统 cache 捕获它的代价过高。** Google trace 中，允许在 24 小时内重排可看到约 24% 的重复读，窗口扩大到 7 天后约为 42%；要仅靠 LRU cache 吃掉 1 EB 集群中 24 小时窗口的全部重用，需要至少 66.5 PB，也就是集群容量约 6%（图 7）。
  - **隐含假设**：公开 trace 的 block 复用结构可以代表维护任务；论文把 4 KB block 的 LRU stack distance 外推到了 1 EB 集群。
- **观察 3：维护任务有三种可利用的自由度。** 时间自由度是“deadline 前完成即可”；顺序自由度是“先读哪个集合都可以”；数据自由度是“候选数据中只需任选一部分”，例如 rebalancing 只需搬够一定容量，不必指定每一个 block（§3.4、图 9–10）。
  - **可能失效场景**：紧急重建、短 deadline、必须读取唯一数据、或调用方无法在 callback 到达时取得计算资源。
- **假设 1：声明只作用于已经 sealed 的不可变 block。** DINGO 面向 append-only 存储；删除仍可能发生，新 append 不进入旧声明，权限和映射在真正读取时重查（§4.4）。
  - **证据强度**：中。HDFS 符合这一模型，但原地更新、事务对象和复杂快照语义没有被覆盖。
- **假设 2：主要瓶颈是维护读。** DINGO 的调度额度和优化目标都是 read IO；write、CPU、network 与 compute admission 没有进入同一优化器。
  - **证据强度**：中。原型证明读量下降，但 clustered transcoding write 仍会暂时抬高前台延迟（图 15）。

## 核心方法

### 1. 声明接口：交出“何时、顺序、选哪些”的决定权

核心接口是：

```text
declare(read_sets: list<BlockSet>,
        sets_needed,
        deadline,
        callback(sets_selected, overloaded))
```

一个 `BlockSet` 是必须一起处理的一组 `BlockId`，例如一个文件片段或一个 [[Erasure-Coding|纠删码]] stripe。默认要完成 `read_sets` 中全部集合；若设置 `sets_needed`，系统只需从候选集合中恰好选择指定数量。`deadline` 给出最后完成时间。DINGO 可以多次调用 callback，每次告诉任务“现在读这些集合最容易复用”。callback 不直接返回数据，任务仍通过原来的命令式接口读取，因此继续使用已有的 lease、一致性、权限和失败处理机制（图 8）。

文件级声明会在提交时由 metadata service 翻译成 block snapshot。此后新创建或 append 的 block 不会自动加入；任务若需要它们，必须再声明。整个 `BlockSet` 已删除时，DINGO 可以省略 callback；若 callback 中夹有已删除 block，普通读按原系统语义失败。系统过载而无法保证 deadline 时，callback 设置 `overloaded=true`，任务可以回退到命令式读取（§4.2、§4.4）。

### 2. IO Planner：先保 deadline，再找重叠

DINGO 在 append-only 文件系统旁增加集中式 IO Planner（图 12）。每个 scheduling quantum，它对每个 declaration 计算按 deadline 完成所需的平均 IO rate，然后从高到低调度，直到用完本 quantum 的磁盘额度。同一 quantum 内已经被其他 declaration 选择的 block 被视为“免费”，不再占额度；在同一 declaration 内，优先选择含最多免费 block 的 `BlockSet`（图 13）。

全局最优重用是 NP-hard，所以这个启发式明确把按期完成放在最优重用之前。若所有声明都达到应有进度，剩余额度默认不提前做更多工作，而是留给高优先级 IO；提前读可能反而错过未来更好的重叠（§5.1）。

### 3. Dispatcher：把长 quantum 拆成短缓存窗口

若一个小时 quantum 内所有可复用 block 都要一直留在 cache，空间会很大。Dispatcher 因而把已选 `BlockSet` 分成若干有重叠的 dispatch group，在 quantum 内分批发 callback；cache 只需保留当前 group。朴素分组需要比较所有集合，复杂度为二次方。DINGO 按 EC group 建反向索引，只在可能共享 stripe 的集合中找重叠，把处理 scheduled `BlockSet` 的复杂度降为线性（§5.2）。

Planner 还给 cache 发 directive：当前 round 的 block 进入专用区域并暂时 pin，既避免在第二个任务读取前被驱逐，也避免维护流量把普通 replacement policy 误导成“热点”。在 2 MB/s/TB 的维护读速率下，pin 1 分钟的保守上界是每 TB 磁盘 120 MB cache；pin 2 分钟则是 240 MB/TB，即 1 EB 集群共 240 TB，约比图 7 的纯 cache 方案小两个数量级。

## 正确性与故障边界

- **删除与 metadata 变化**：真正读取仍走原接口，所以 stale mapping、权限变化和 block 删除由原系统与任务处理；正确性不变，但实际 cache hit 可能减少。
- **相关磁盘故障**：多盘同时坏时，reconstruction 关系到数据丢失，应直接走紧急命令式 IO，不等待声明调度。
- **计算资源暂不可用**：任务错过 callback 只会失去这次重用，之后仍可读到数据；论文没有给 compute admission 方案。
- **过载与亚稳态**：若大量 deadline miss 触发命令式回退，而集群容量又是按“预期有重用”配置，新增 IO 会让系统更难恢复，形成类似 cache collapse 的 metastable failure。论文指出了风险，但没有实现闭环保护。

## 实验设计

### HDFS 原型

原型基于 HDFS，baseline 除加入 transcoding 支持外保持不变。10 台节点各有 64 cores、128 GB RAM、3 TB HDD 和 40 GbE [[RDMA|InfiniBand]]；集群开始时存有 18 TB 数据、使用率 80%，其中 25% 为三副本，75% 为 RS-3-2-1024k。每盘只给 10 GB 内存，即 2 GB/TB。工作负载按 Hyperscaler A 缩小为 rebalancing、reconstruction、scrubbing、transcoding 四类，时间和容量都缩小 8 倍，实验持续 81 小时，DINGO read quota 为 120 MB/s（§6.1、表 1）。

### 数据中心仿真

仿真器模拟 100 PB、80% 使用率的集群，文件为 7.5 GB、block 为 256 MB，数据采用三副本或 6-of-9、30-of-33 纠删码；以 3 小时为步长运行 30 天。两个 workload mix 来自两家 hyperscaler，共含 reconstruction、scrubbing、garbage collection、transcoding、FSCK、geo-replication、rebalancing 等八类工作。仿真器在对应 HDFS 实验上的 IO savings 与实测相差少于 5%（§6.1、表 2）。原型和仿真器均由作者开源。

## 实验与结果

- **原型确实少读。** 完成同一批逻辑维护工作时，baseline 每个 logical byte 读 1 个 disk byte，DINGO 只读 0.74，减少 26%；Planner 预测为 28%，2 个百分点差距来自 cache miss、metadata 操作和噪声（图 14）。
- **集中限速改善了所测前台读。** 加入约占 disk read 30% 的 Alibaba-trace-like 前台负载后，baseline 与 DINGO 吞吐分别为 6.36 和 6.82 MB/s；平均 P50 为 167 和 86 ms，最差 P50 为 587 和 423 ms；平均 P99 为 1181 和 832 ms，最差 P99 为 6877 和 4969 ms（图 15）。但某些分钟两者可相差约 6 倍，DINGO 的 transcoding 写突发仍会伤害 P50。
- **容量收益来自条件化仿真，并接近宽松下界。** 在 48 TB 盘、维护读 2 MB/s/TB 时，命令式方案花 64% disk-head time；Cluster A 中 DINGO 最低为 34.8%，可识别最多 45% 的重复读取。若维护 IO 最多只能用一半磁盘时间，命令式系统支持 36 TB，DINGO 在 Cluster A/B 分别支持 64/58 TB，也就是 1.7/1.5 倍（图 16）。即使 `Optimal` 知道全部未来声明且不受 deadline 和 per-quantum IO 限制，DINGO 在两个 cluster 仍处于这个不可实现下界的 5% 内；这说明所测 workload 上接近最好，但不是可部署调度器之间的公平比较。
- **收益既来自复用，也来自避免无效工作。** 短 deadline 的 reconstruction 常决定先读什么，灵活任务随后搭便车；rebalancing 因候选数据多，在仿真中全部读取都能复用。另有 26% 的 scrubbing 声明在执行前数据已被删除，因此不必读取（图 17）。借此，Cluster B 把 scrubbing 提高 4 倍几乎不增加总读；Cluster A 把 rebalancing 提高 4 倍后，总维护读仍比命令式 baseline 少 45%；两个 cluster 都能在相同读 IO 下做 2 倍 garbage collection。这里只计算读，写入成本仍在（图 19）。
- **对 demand、deadline 和动态额度均有敏感性证据。** 维护读需求从 1 增到 3.5 MB/s/TB 时，DINGO 在 Cluster A/B 分别少用 39%–51% 和 28%–46% disk-head time（图 18）；transcoding deadline 从 1 天放宽到 7 天，Cluster A 总 disk utilization 再降 7%。DINGO 也能跟随昼夜变化的 IO quota，始终不超过分配阈值（图 20–21）。
- **控制面能算完，但很重。** 1 EB、2 MB/s/TB 的配置下，Dell R640（240 GB RAM）能在 15 分钟内算完一个 1 小时 quantum，峰值内存 205 GB（§6.2）。这证明单机计算可行，也说明离轻量控制面很远。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 维护任务已经主导许多集群的 after-cache HDD IO | §3.2、图 4–6：六家为至少 45%–70%，三家给出任务拆分 | 企业身份和大部分原始 trace 不公开；剩余 IO 中仍可能含维护工作 | 强 |
| 传统 cache 很难吃掉跨天重用 | 图 7：24 小时约 24% 重复读，1 EB 需 66.5 PB cache | Google 单一公开 trace，按 4 KB LRU stack distance 估算 | 中 |
| 声明式调度能在真实原型中减少物理读 | 图 14：HDFS 原型少读 26% | 10 节点、18 TB、四类任务、81 小时 | 强 |
| DINGO 能支持 1.7 倍容量 HDD | 图 16：36 TB 提至 64 TB | 100 PB 仿真；固定 workload、应用/维护各占一半 IO 的容量模型 | 中 |
| Planner 可扩展到 1 EB | §6.2：一小时计划少于 15 分钟，峰值 205 GB | 单服务器离线仿真；未测 HA、恢复和线上声明 churn | 中 |

## 批判性分析

### 论证链条

论文的主链条很清楚：先用六家 hyperscaler 数据证明维护 IO 已成为容量瓶颈，再用 Google trace 证明重用存在但距离太远，然后用新接口暴露自由度，最后由原型证明机制、由仿真回答容量尺度问题。最容易被误读的是“支持 1.7 倍 HDD”：它不是在 64 TB 生产盘上的部署结果，而是由 100 PB 仿真、固定维护需求和“维护最多占 50% 磁盘时间”的模型推出来的容量边界。

### 假设压力测试

收益同时依赖长 deadline、较多 block overlap、可靠 callback 和可用 cache。若任务 deadline 很短、数据几乎不重叠、计算资源不能及时响应，DINGO 会退化成普通读，仍付出声明和控制面成本。更危险的是集群按预期重用来超配容量后发生大面积 deadline miss：回退流量会继续抬高负载。论文承认这一亚稳态，却没有给出 admission control、安全余量或恢复实验。

### 实验可信度

原型直接测了 disk bytes 和前台 P50/P99，仿真又在缩放后的同类实验上校准到 5% 内，这种“实机机制 + 大规模模型”的组合较可信。限制是原型只有 18 TB、四种任务，大规模收益仍主要来自参数化仿真；企业 trace 无法独立复核；`Optimal` 还去掉了 DINGO 必须满足的 deadline 和 quantum 约束，只能当宽松下界。论文也没有比较“统一 rate limiter + 少量人工协同”这类迁移成本较低的中间方案。

### 系统性缺陷

Declarative IO 需要不同团队改造任务、维护 declaration 生命周期并处理 callback，论文没有量化迁移成本。集中 Planner 在 1 EB 已需 205 GB 内存，其故障恢复、状态复制、重复 callback、控制面分区和大量声明更新都未做 fault injection。调度目标只有 read IO；图 15 的写突发说明仅控制读带宽不能完整保护前台 SLO。最后，权限与 metadata 在 callback 后重查虽然保住正确性，却可能让计划中的复用失效。

## 局限与后续工作

- **局限 1**：只面向 sealed immutable block；原地更新、事务快照和跨对象一致性没有实现或评测。
- **局限 2**：1.7 倍容量主要由仿真得出，缺少 48–64 TB 设备上的长期生产部署。
- **局限 3**：Planner 的 HA、过载恢复和 metastability 只做了定性讨论。
- **局限 4**：只减少维护读，不减少任务写入，也没有联合调度 CPU、network 和 compute slot。
- **后续工作 1**：在可公开复现的 trace 上扫描 deadline、overlap、cache pin 时长和 declaration churn，找出 savings 跌破容量安全线的边界。
- **后续工作 2**：把 write bandwidth、CPU、network 和前台 tail-latency SLO 放入同一调度器，并复现实验中的 transcoding burst。
- **后续工作 3**：实现 replicated Planner，注入 crash、partition、重复 callback 和集中 deadline miss，测量恢复时间及恢复产生的额外 IO。
- **后续工作 4**：选择一种未修改 API 的全局 rate limiter 作为强 baseline，分别量化“集中限速”和“跨任务重用”带来的收益。

## 相关

- **相关概念**：[[Erasure-Coding]]、[[Garbage-Collection]]
- **同会议**：[[OSDI-2026]]
- **Artifact**：论文公开了 HDFS 原型与仿真器（§6.1）。
