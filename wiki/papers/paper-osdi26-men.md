---
type: paper
name: Duhu
full_title: "Duhu: Shared Disaggregated Memory for Distributed Data Processing Frameworks"
authors: [Qiutong Men, Tao Wang, Jongryool Kim, Hane Yie, Emmanuel Amaro, Marcos K. Aguilera, Aurojit Panda]
venue: OSDI
year: 2026
tags: [shared-disaggregated-memory, cxl, distributed-data-processing, object-store, ray]
source_pdf: "[[osdi26-men.pdf]]"
source_md: "[[osdi26-men]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-09-14
---
# 面向分布式数据处理的共享解耦内存对象存储（OSDI 2026）

> **原题**：Duhu: Shared Disaggregated Memory for Distributed Data Processing Frameworks

> **一句话总结**：DDF 传统的 pass-by-value 会为不可变中间对象反复付出网络传输和本地复制成本；Duhu 在缺少跨节点缓存一致性的 CXL 共享解耦内存上，用分段元数据所有权、Duhu-Channel、缓存刷新和引用计数实现 pass-by-reference，并在四阶段 shuffle 上将 JCT 最多降低 3.39×。

## 问题与动机

Ray、Spark 等分布式数据处理框架通常通过内存对象存储传递不可变中间数据。消费者访问对象前，框架会把对象复制到消费者节点的本地内存。这种 pass-by-value 语义既消耗网络带宽和序列化 CPU，也让同一对象在多个节点上形成副本，实际内存需求超过作业数据本身。

共享解耦内存（shared disaggregated memory，SDM）允许多个节点通过 load/store 访问同一份数据，因此提供了 pass-by-reference 的机会。但当前 CXL 2.0 类设备不提供跨节点全局缓存一致性；即使未来硬件支持一致性，也会引入目录、带宽和尾延迟成本。Duhu 的目标是在不修改 DDF 核心逻辑的前提下，让对象数据共享，同时由软件处理元数据协调和缓存安全。

## 关键观察 / 隐含假设

- **观察 1**：DDF 中对象数据通常只写入一次、之后不可变，而对象元数据（引用者、分配状态、回收状态）持续变化；数据访问量通常远大于元数据访问量（§1、§3）。
  - **依赖假设**：工作负载主要传递不可变中间对象。
  - **可能失效场景**：需要原地更新、细粒度共享写入或强一致可变对象时，Duhu 的数据一致性方案不适用。
- **观察 2**：多阶段 shuffle 中，后续阶段可以只重组分片描述，而不再次搬运完整数据。FlexShuffle 用 offset/length slice 替代物理分区传输（§8.2.1）。
  - **依赖假设**：消费者能够随机或部分访问共享对象，且 SDM 容量足以容纳中间结果。
  - **可能失效场景**：数据几乎全部顺序扫描、对象很小或本地内存足够时，远端 SDM 的更高延迟可能超过复制收益。
- **假设 1**：节点故障不会破坏仍存活节点可访问的 SDM 内容；内存 blade 故障则由 DDF 的 lineage 重算对象（§3）。证据强度：中；协议覆盖了恢复路径，但依赖外部编排器和 DDF 的重算能力。

## 核心方法

Duhu 将 SDM 划分为多个 segment，每个 segment 由一个节点独占负责元数据操作。对象的 metadata 和 data 放在同一 segment 中。其他节点通过 RPC 请求 owner 执行分配、获取引用和释放引用，从而避免多个节点直接修改非一致元数据。每个 Duhu-RM 维护 WAL；同一对象的请求被 dispatcher 串行路由到同一线程，以便恢复时按序重放。

Duhu-Channel 用 SDM ring buffer 传输小型 RPC 请求和响应，用传统网络只发送通知。这样大部分 payload 不经过网络协议栈；在缺少 SDM 写入通知机制时，网络仍承担唤醒对端的职责。缓存一致性依赖对象不可变性：创建时使用 non-temporal write 将完整对象刷入 SDM，首次 GetObj 时失效相关 cache line，确保读到当前对象而非前一对象残留的缓存副本（§4.1、§5）。

Duhu 用节点级引用位图避免现有 DDF 的本地垃圾回收误删共享对象。GetObj 增加节点引用，DropRef 清除引用；所有引用释放后才回收 SDM 空间。Ray 集成只需修改 object manager 中的 PushLocalObject、GetRef 和 FreeObject，并采用 lazy copy：只有远端访问或本地内存压力出现时才把对象放入 Duhu。

基于 pass-by-reference，作者实现 FlexShuffle：map task 将未分区结果写入 Duhu，并为每个 partition 生成 slice；reduce task 根据 slice 直接读取共享结果。后续 shuffle 阶段只改变 slice 元数据，避免重新传输数据。

## 设计取舍

- **取舍 1**：放弃硬件全局缓存一致性以换取更低的批量数据传输开销和更好的可扩展性，但把缓存刷新、元数据串行化和 RPC 恢复责任转移到软件。
- **取舍 2**：segment owner 简化一致性和恢复，却使跨 owner 的 GetObj、DropRef 等操作产生 RPC，并让对象放置影响性能。
- **边界条件**：共享数据适合大型、不可变、部分访问或跨多阶段复用的对象；小对象、短查询和高频复用对象更适合保留本地副本。论文也指出未来需要混合复制策略。

## 实验与结果

- 四节点 CXL 原型集群（每节点 512 GB、本地 4×Xeon Gold 6530、100 Gbps 网络；SDM 128 GB，约 600–800 ns 延迟、约 10 GB/s 带宽）上，FlexShuffle 的四阶段 shuffle JCT 最多比 Exoshuffle 低 3.39×（图 6）。后续 reduce stage 快 3.59–13.81×，但 64 GB 场景首轮复制成本导致总体略慢 1.01×（图 7）。
- 在没有 Duhu、只能把数据保存在本地对象存储并溢出 SSD 的对照中，单阶段 FlexShuffle JCT 高出 13.34–24.69×（图 8）。
- Modin TPC-H（scale factor 10，3.4 GB Parquet）中，Duhu-Ray 平均查询时间改善 1.08×，最佳查询最多改善 1.30×；四个小查询反而约慢 1.2×（图 10–11）。
- Duhu-Channel 在约 3 million RPS 下达到 3.8 μs 延迟；RDMA 在 1 million RPS 时延迟为 11.74 μs（图 12）。200 MB fan-out 基准中，Duhu-Ray 阻塞时间比 Ray 少 2.80–4.29×（图 13）。
- 对 6.4 GB 数组只读取小片段时，Duhu-Ray 的 JCT 最多比读取完整数组低 4.45×；但单纯计算时间仍慢于本地 Ray，说明收益来自减少数据搬运而非提升远端访问本身（图 14–15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| pass-by-reference 能显著减少多阶段 shuffle 的数据搬运 | FlexShuffle 后续阶段快 3.59–13.81×，总体 JCT 最多低 3.39×（图 6–7） | 四节点、32 map/32 reduce、最高 64 GB shuffle、原型 CXL | 强 |
| 软件协调能在无全局缓存一致性的 SDM 上提供安全共享 | non-temporal write、首次 cache invalidation、segment owner、WAL 和引用计数（§4–6） | 不可变对象；节点/内存 blade 故障依赖外部编排器和 lineage | 中 |
| Duhu 对现有 DDF 的收益取决于对象规模和访问模式 | TPC-H 平均 1.08×，小查询约慢 1.2×；部分访问 JCT 最多低 4.45×（图 11、14） | Ray/Modin、固定 SDM 原型和有限查询集 | 强 |

## 批判性分析

### 论证链条

从“对象不可变且复制昂贵”到“共享一份对象并由软件维护元数据”的链条是闭合的；FlexShuffle 也展示了只有 pass-by-reference 才能自然实现的 shuffle 组织方式。性能收益主要来自避免网络和本地副本，而不是 SDM 访问比本地 DRAM 更快。论文没有证明 Duhu 在可变对象或更广泛 DDF API 上的适用性。

### 假设压力测试

原型 SDM 只有 128 GB、四个节点，且本地内存并非瓶颈。生产集群中更大的节点数会增加 segment owner RPC、网络通知连接数和故障恢复扫描成本。对象创建仍先在本地内存完整初始化，再复制到 SDM，因此超出本地可用内存的大对象无法直接创建。论文提出了直接在 SDM 创建和磁盘直接读入的方向，但尚未实现。

### 实验可信度

实验覆盖 shuffle、TPC-H、fan-out、部分访问和对象生命周期，并比较了 TCP、RDMA 与 Duhu-Channel。NUMA 模拟表明更低延迟、更高带宽的未来 SDM 会进一步放大收益，但 NUMA 并不等价于真实多节点 CXL。TPC-H 中 Ray 查询 5 因内存耗尽被排除，且四容器配置会造成双方显著干扰，结果因此更像受控可行性验证，而非生产规模结论。

### 系统性缺陷

Duhu 依赖对象不可变、正确的 DropRef 调用和外部故障编排；DDF 或应用的引用生命周期错误可能造成泄漏或悬空指针。segment metadata 扫描和 WAL replay 主导节点故障恢复时间，但没有给出完整端到端恢复时间矩阵。论文也未系统评估多租户隔离、热点对象复制、跨内存单元负载均衡、监控和运维成本。

## 局限与后续工作

- **局限 1**：对象必须先完整存在于本地内存，随后才能复制到 SDM，削弱了 Duhu 对超大对象的帮助。
- **局限 2**：当前评测依赖早期 FPGA CXL 原型；更快硬件由 NUMA 模拟，不能替代真实 CXL 多节点测量。
- **后续工作 1**：实现 SDM 原位创建和 direct I/O，并在不同本地内存容量下测量峰值内存、CPU 搬运和 JCT。
- **后续工作 2**：为小对象和热点对象加入基于访问频率、对象大小和复用距离的本地复制策略，验证其对尾延迟和 SDM 热点的影响。

## 相关

- **相关概念**：[[CXL]]、[[Shared Disaggregated Memory]]、[[Distributed Shared Memory]]、[[Object Store]]
- **同类系统**：[[Ray]]、[[Exoshuffle]]、[[Pond]]、[[Pasha]]
- **同会议**：[[OSDI-2026]]
