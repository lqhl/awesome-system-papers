---
type: paper
name: Conflux
full_title: "The LogDrive: Composable Durability for Cloud-Based Shared Logs"
authors: [Gardner Vickers, Lucas Bradstreet, Mahesh Balakrishnan, Prince Mahajan, David Mao, et al.]
venue: OSDI
year: 2026
tags: [shared-log, cloud-storage, durability, state-machine-replication, metadata-service]
source_pdf: "[[osdi26-vickers.pdf]]"
source_md: "[[osdi26-vickers]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-14
---

# 面向云存储的可组合持久化共享日志（OSDI 2026）

> **原题**：The LogDrive: Composable Durability for Cloud-Based Shared Logs

> **一句话总结**：云数据库适合承载元数据却成本过高，直接复用共享日志又难以做复制；Conflux 将排序交给带软状态 sequencer 的 AtomicLog，将持久化交给可条带化、可复制的 LogDrive，在代表性负载下把元数据成本降低约 10 倍、K2 总成本降低约 3 倍，同时保持约 130 ms 的 p99 写延迟。

## 问题与动机

K2 是 Confluent 构建的、以 S3 保存数据的 Kafka 风格发布订阅系统。数据平面可以用大批量对象写入获得低成本，但每条 topic 的索引仍需要频繁的小元数据更新。直接使用 DynamoDB 虽然运维简单，却可能占据 K2 总成本的约 75%；自行运行 FoundationDB、etcd 或其他数据库则带来部署、故障恢复和跨数据平面运维的负担。

共享日志能把多个小更新批量写入云存储，并让每个服务器维护本地状态副本，从而把读取转成本地查询。现有共享日志的 append 接口同时负责排序和持久化：把一次 append 转发给多个日志时，各副本可能分配不同时间戳，无法直接构成复制层。论文因此把排序与持久化拆成两个层次。

## 关键观察 / 隐含假设

- **观察 1：共享日志的排序接口妨碍 RAID 式复制。** 多个底层日志可能为同一条记录分配冲突位置，延迟重试还可能制造重复记录；并发 append 又要求额外排序。论文在 §2.1 用复制两个共享日志的反例说明了这一点。
  - **依赖假设**：上层能够提供稳定的应用级地址，并保证一个地址至多写入一个值。
  - **可能失效场景**：需要覆盖写、多个 sequencer 并发分配地址，或故障恢复无法判断已分配但未完成的槽位时，LogDrive 的弱语义不足以支撑正确性。
- **观察 2：元数据工作负载适合批量追加和本地重放。** K2 生产记录平均约 165 字节，写读比例约为 1:3；共享日志可以把多个 topic 更新合并成一次云存储写入，服务器通过本地数据库服务大多数读取（§6）。
  - **依赖假设**：状态机可确定性重放，且快照和日志截断的成本低于逐请求访问云数据库。
  - **可能失效场景**：状态机很大、读取强依赖最新远端状态，或写入无法批量化时，云存储访问和本地副本维护的收益会下降。
- **假设 1：窗口内写入数量有可靠上界。** AtomicLog 通过滑动窗口限制 contiguous tail 与 non-contiguous tail 的距离，LogDrive 的 `weakTail(K)` 只扫描窗口即可。该上界若被应用违反，孔洞集合可能无法完整描述地址空间。
  - **证据强度**：强。§3 和附录给出窗口扫描性质及形式化证明，但假设由调用方负责维护。
- **假设 2：sequencer 可以是软状态，故障时切换整个 Loglet。** sequencer 不保存负载数据；它失效后 AtomicLog 暂停 append，由 VirtualLog seal 当前日志、读取尾部并切换到新 Loglet（§4）。
  - **证据强度**：中。协议沿用 Delos 的虚拟日志思路，生产系统验证了切换，但单个 sequencer 故障会牺牲当前 Loglet 的 append 可用性。

## 核心方法

**LogDrive** 是带编号的随机读写地址空间。每个地址只允许写入一个值；`weakTail(K)` 返回 non-contiguous tail 和前方的 hole set。它不要求 tail 扫描具备线性一致性，只要求结果等价于操作期间某次无序、非原子扫描。弱语义使其可以直接架在 S3、DynamoDB 和 S3Express 等存储 API 上（§3.1–§3.2）。

**StripedLogDrive** 把全局地址映射到多个 LogDrive，实现 RAID-0 式吞吐扩展。各分片并行执行 `weakTail`，再合并尾部和孔洞。**QuorumLogDrive** 将写入发送到多个副本，等待写 quorum；读取访问与写 quorum 相交的读 quorum，并在发现部分写入时做 read repair。这样可以把单 AZ 的 S3Express 或单区域的 DynamoDB 组成跨 AZ、跨区域的持久化层（§3.3–§3.4）。

**AtomicLog** 在 LogDrive 之上加入软状态 sequencer 和窗口化写入。客户端先获取槽位，再写 LogDrive，最后按地址顺序完成槽位；append 的线性化点是 `completeSlot`。虽然底层 `weakTail` 本身不线性一致，窗口写入保证了它返回的 tail 可作为线性一致的 `checkTail`（§4）。seal 位保存在云存储中，避免 sequencer 失效后出现两个 tail 来源。

**Conflux** 在 AtomicLog 上复用 Delos 的 VirtualLog 和状态机复制。每个服务器维护 RocksDB 本地副本，更新写入共享日志后按序重放；只读请求先检查日志尾部，再从本地状态返回。快照每 10 分钟写入 S3。K2 进一步把每个 topic 的 DataRef 列表视为细粒度日志，形成“日志上的日志”结构（§5.1–§5.3）。

## 设计取舍

- **弱语义换取可组合性。** LogDrive 不提供多值写入保护，也不要求 `weakTail` 线性一致，把正确性责任移到 AtomicLog 的单值地址和窗口协议。收益是可以用普通云存储 API 实现；代价是任意应用不能直接把它当作完整共享日志。
- **云成本换取延迟。** 默认批处理超时为 100 ms，Conflux-over-DynamoDB 的 p99 写延迟约 130 ms，约为直接 DynamoDB 方案的 6.5 倍，但元数据成本下降一个数量级。
- **高可用切换换取故障时的局部不可用。** sequencer 或持有槽位的客户端失败会使当前 AtomicLog 无法继续 append，VirtualLog 需要 seal 并切换 Loglet。切换不要求停机，但会增加重配置和运维路径。
- **组合自由度换取协议复杂度。** quorum、striping、快照、read repair、VirtualLog 和状态机复制可以叠加；故障恢复、观测和参数配置也随层数增加。

## 实验与结果

- 在代表性负载（2K writes/s、6K reads/s、平均记录 165 B）下，Conflux-over-DynamoDB 比直接 DynamoDB strawman 的元数据成本低约 10 倍；加入 K2 数据平面后，总成本降低超过 3 倍。模型假设压缩比为 5 倍，数据平面成本为每小时 2.37 美元（图 13、§6.2）。
- Conflux 的默认窗口大小为 16、批处理超时 100 ms、大小阈值 60 KB；不同后端的 p99 吞吐—延迟曲线见图 9。DynamoDB、S3 和 S3Express 均可作为 LogDrive 后端。
- 三个跨区域 DynamoDB 副本可以配置为 `(3,3)` 或 `(2,3)` quorum；S3Express 副本可以跨 AZ/区域组合。图 10 展示了不间断地在 DynamoDB、S3Express 以及不同 quorum 之间切换，图 11 展示 `(2,3)` 配置在一个区域存储不可访问时继续运行。
- 生产 K2 集群使用 114 个 broker（108 个服务请求）和 20 个 Conflux shard，每个 shard 3 台服务器；一次运行达到约 9 GB/s produce 与 27 GB/s fetch。produce p99 约 600 ms，fetch p99 约 300 ms；Conflux 元数据 append p99 约 130 ms（图 14–15、§6.3）。
- DynamoDBLogDrive 由一名工程师约一周完成。早期单分区访问触及限流，改用 StripedLogDrive 后解决，说明窄 API 和模拟测试确实降低了更换后端的工程成本（§6.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| LogDrive 可以在不同云存储上实现并组合 | S3、DynamoDB、S3Express 实现与图 9–11 | AWS 环境，固定窗口和批处理参数 | 强 |
| 组合后的共享日志可提供可用的状态机复制基础 | AtomicLog/VirtualLog 设计、线性化论证、仿真故障测试（§4、§4.1） | 依赖单值写入、窗口上界和确定性状态机 | 中高 |
| 批量日志写入能显著降低元数据成本 | 图 13、§6.2 的 2K/6K 负载成本模型 | 165 B 记录、5 倍压缩、特定 AWS 价格 | 强 |
| 系统适合生产级云发布订阅服务 | K2 生产集群的图 14–15 与后端切换 | 单区域部署、特定 broker 数量和请求负载 | 中高 |

## 批判性分析

### 论证链条

论文的主链条是闭合的：共享日志复制难以组合，促使作者定义弱而可实现的 LogDrive；AtomicLog 用顺序完成槽位重新获得线性一致的日志接口；VirtualLog 和状态机复制再把它用于 Conflux。附录证明了 striping、quorum 和 `checkTail` 的关键性质，模拟器也确实发现过 S3 分页和 seal 顺序问题。

不过，成本收益依赖批量化、压缩和本地读取三个条件。论文的主成本比较使用了一个较简单的 DynamoDB strawman，并明确说该 strawman 没有实现完整并发控制，因此成本优势应被理解为特定工作负载下的下界比较，而不是对所有元数据数据库的普遍结论。

### 假设压力测试

窗口上界由上层协议保证。客户端崩溃、长时间暂停或高并发突发可能使窗口持续满载，造成 append 阻塞。sequencer 失效也不是透明恢复：VirtualLog 可以切换，但当前 Loglet 的未完成槽位、seal 和尾部读取仍需经历故障处理。

QuorumLogDrive 的正确性要求每个地址只写一个值。它适合追加日志，不适合把同一地址当作普通可覆盖寄存器。跨区域 quorum 提升持久性，却把写延迟绑定到最慢的 quorum 成员；论文给出了区域距离约 60 ms 和 120 ms 的设置，但没有系统比较 quorum 成员变化、网络抖动和长期尾延迟。

### 实验可信度

实验覆盖了三个存储后端、不同 quorum、后端切换、区域故障和生产流量，足以支持“可插拔、可组合”的工程论断。另一方面，成本实验是模型估算，生产运行主要展示一个 K2 集群；没有给出不同批处理超时、记录大小、压缩比、快照周期和 topic 分布下的完整敏感性分析，也没有将 Conflux 与一个功能完整的自管数据库做同等成本与运维比较。

### 系统性缺陷

每个 Conflux shard 仍需多台 EC2 实例、EBS 和 Kubernetes；云存储只承载硬状态，并没有消除所有运维成本。VirtualLog 的 membership 条件寄存器固定使用 DynamoDB，跨云迁移并非完全不依赖特定服务。论文对多租户隔离、快照失败后的恢复时间、日志增长与 trim 失败、read repair 的成本以及异常数据损坏的处理讨论有限。

## 局限与后续工作

- **局限 1：成本结论对负载形状敏感。** 需要在不同记录大小、写读比例、批处理延迟和压缩率下重新计算成本—延迟曲线。
- **局限 2：sequencer 是单点可用性边界。** 可验证的后续方向是让多个 sequencer 共享槽位分配状态，并测量其对 append 延迟和恢复复杂度的影响。
- **局限 3：重配置和恢复的长期行为未充分量化。** 应在重复区域故障、部分 quorum 超时、快照落后和大量未完成槽位下报告恢复时间、数据重放量和尾延迟。
- **局限 4：LogDrive 的单值约束限制了通用性。** 可以研究带版本或条件写入的扩展，但需重新证明 quorum read/write repair 与 AtomicLog 的线性化性质。

## 相关

- **相关概念**：[[Shared-Log]]、[[State-Machine-Replication]]、[[Quorum-Replication]]、[[RAID]]
- **同类系统**：[[Delos]]、[[Corfu]]、[[DynamoDB]]、[[Kafka]]
- **同会议**：[[OSDI-2026]]
