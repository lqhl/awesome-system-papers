---
type: paper
name: libDSE
full_title: "Distributed Speculative Execution for Resilient Cloud Applications"
authors: [Tianyu Li, Badrish Chandramouli, Philip A. Bernstein, Samuel Madden]
venue: OSDI
year: 2026
tags: [durable-execution, fault-tolerance, speculation, microservices, distributed-systems]
source_pdf: "[[osdi26-li-tianyu.pdf]]"
source_md: "[[osdi26-li-tianyu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向韧性云应用的分布式推测执行（OSDI 2026）

> **原题**：Distributed Speculative Execution for Resilient Cloud Applications

> **一句话总结**：传统持久执行在任务图每一层都同步落盘，延迟随深度累加；libDSE 允许服务先发送尚未持久化的结果，用恢复依赖图、原子 action、轻量 sthread 和对外 barrier 保证故障后统一回滚，在持久化受限的长工作流中把尾延迟降到约十分之一，但代价是改造应用状态、故障时丢弃推测工作，以及自动 gRPC 集成最高约 25% 的吞吐损失。

## 问题与动机

持久执行（durable execution）系统会记录操作意图、中间结果和任务历史，故障后重放，让外部用户看起来像执行没有中断。问题是，只要任务可能不确定，系统通常必须等当前任务结果落盘后才能启动下游任务；否则重放可能产生不同结果，旧下游操作又已产生影响。于是一个有十层服务调用的 DAG 会串行等待十次持久化，延迟随深度线性增长。

libDSE 的出发点是把“最终必须可恢复”和“每一步都必须先同步落盘”分开。服务可以先消费和发送推测结果，把多次 I/O 等待并行起来；真正不可回滚的用户响应、付款或 legacy 数据库调用，必须等其全部上游依赖都持久化后才能发生。故障时，系统找出依赖丢失状态的所有推测结果并一起回滚。

这比单机推测难得多。每个 shared-nothing 服务都能独立失败，控制流本身也可能存在工作流引擎里；一次回滚会沿消息因果关系跨服务传播，并与仍在执行的异步 RPC 竞争。论文要求同时满足两点：内部不一致最终可修复（recoverability），外部实体永远看不到由故障造成的不一致（failure transparency）。它不承诺推测工作不丢失。

## 关键观察 / 隐含假设

- **观察 1：持久化等待可以跨服务重叠**。图 2 和 §2.3 指出，传统 durable workflow 把每层同步 I/O 放在关键路径上；若先传播结果，各服务可以并行持久化。
  - **依赖假设**：持久化是主要瓶颈，而且推测单元完成的概率远高于被故障打断的概率。
  - **可能失效场景**：视频转码、agentic exploration 等计算时间远大于落盘时间的任务，或只有一两个步骤的浅 CRUD，请求端到端收益会小很多。
- **观察 2：消费一条消息就建立了恢复因果关系**。这个边既能表达数据依赖，也能表达“工作流收到结果后决定调用谁”的控制依赖，因此不必要求确定性重放。
  - **依赖假设**：参与者之间所有影响状态的通信都经过 libDSE header；隐藏通道会让依赖图缺边。
  - **可能失效场景**：服务绕过封装直接写共享数据库、调用外部 API，或开发者漏用 action/barrier 时，协议无法自动恢复正确性。
- **观察 3：按 recoverable point 而非逐消息跟踪，能把常态开销压低**。依赖图片段只随本地 Persist 批量异步发给 coordinator，操作仍点对点执行。
  - **依赖假设**：这种粗粒度造成的保守回滚不常发生，恢复时损失额外工作可接受。
  - **可能失效场景**：高扇出图中一个失败点会让许多本来无关的工作共享恢复点，放大 rollback blast radius。
- **假设 1：失败模型足够受控**。组件是 fail-restart，能在有界时间内回来；消息通道可靠但可暂时分区；每个组件有私有持久存储；不考虑 Byzantine failure。
  - **证据强度**：中。这符合许多 Kubernetes 服务，但同时存在的旧、新 incarnation 还需要应用自己对持久存储做 fencing。
- **假设 2：应用状态能封装成具有线性恢复点的 StateObject**。
  - **证据强度**：中。日志型、single-primary 服务很适合；论文明确说 Dynamo 式最终一致系统缺乏单一恢复点，匹配较差。

## 核心方法

开发者先把可恢复状态封装成 `StateObject`，实现异步 `Persist`、`Restore` 和 `ListVersions`。每次状态访问放在原子执行单元 `action` 中：多个 action 可以并发，但它们不会与 Persist/Restore 交叠，因此一个 action 的效果要么整体留在某个可恢复版本中，要么整体被回滚。入站消息的 `StartAction` 检查发送方是否已回滚，出站消息的 `EndAction` 生成不透明依赖 header。

长时间占着 action 会阻止本地持久化，甚至让全局进度停住。libDSE 因此提供轻量推测线程 `sthread`：它从父 StateObject detach，携带当时的依赖集合，在原子区外等待 RPC、睡眠或重试，再通过类似消息接收的 merge 回到父对象。如果中间发生回滚，父对象会拒绝旧 sthread 的 merge，并从恢复状态重新派生任务。`Barrier()` 则等到 sthread 的全部上游依赖不再推测，适合放在向用户回包或调用不可回滚外部系统之前。

协议的核心是恢复依赖图。每个顶点由 `(StateObject id, global failure counter, local persistence counter)` 唯一标识，代表 `Restore` 能加载的一个恢复点；若恢复顶点 `u` 而不保留 `v` 会产生不一致，就添加边 `u → v`。同一 StateObject 的版本先后关系形成隐式边，接收消息形成跨服务边。依赖是按恢复点合并的，设计上可能产生 false sharing，但比逐消息记录简单。

Commit Ordering Rule 防止 domino effect：一个本地 persistence counter 为 `y` 的顶点，只能消费 counter 不大于 `y` 的消息；遇到更大的 counter 时先异步发起一次本地 Persist，再继续处理，而不用等 I/O 完成。这样每个 counter 前缀都是有限闭包，任一节点丢失 `k` 之后的状态时，其他节点也只需回滚自己 `k` 之后的进度。代价是频繁通信的服务会被动同步持久化节奏。

故障时，coordinator 删除失败组件没有报告为持久化的顶点，再反复删除指向丢失顶点的依赖者。它为这次 rollback 分配单调递增的 global failure counter；Recovery Partition Rule 只允许相同 failure counter 的 incarnation 通信，旧世界消息丢弃，来自未来世界的消息等待，从而避免恢复中的两个世界互相污染。

“coordinator 无状态”只适用于无故障路径的 boundary decision：持久图前缀不可变，所以其内存视图即使稍旧，宣布的闭包仍安全，重启后可从参与者重新计算。完整 coordinator 仍有可靠日志，用来保存成员变更、failure sequence 和 rollback decision；重启时必须重放日志，并等所有参与者上报依赖图后，才能再次回答当前 boundary。它不在普通 RPC 数据路径上，但变慢会推迟结果对外可见。

实现包含约 4,000 行 C#，集成 gRPC interceptor、ASP.NET 和 Kubernetes。作者以约 200 行 wrapper 做 speculative log，再在其上改造 FASTER KV（约 400 行）、DARQ workflow（约 200 行）和 event broker（约 800 行）；2PL + 2PC transaction store 与 TPC-C 逻辑约 2,000 行，主要是从头实现而非 libDSE 本身的改动。

## 设计取舍

- **用故障时回滚换无故障时不等待**：常见路径少了串行落盘，故障路径则会丢掉仍属推测的工作，并临时增加重试或事务 abort。
- **粗粒度恢复点换低元数据开销**：依赖图较小、恢复协议只需一轮集中决定，但 stale view 和 false sharing 会让 rollback 比理论最小集合更大。
- **集中 coordinator 换简单的一致决定**：普通服务通信仍是点对点，吞吐不经过 coordinator；其饱和或重启不会立刻停掉内部执行，却会阻止 barrier 越过和外部结果可见。
- **barrier 换渐进兼容**：legacy DB、支付接口等无需支持回滚，但每道 barrier 都重新把上游持久化等待放回关键路径；外部副作用密集的流程很难获得长推测窗口。
- **边界条件**：最适合深、持久化受限、故障较少、状态可日志化的工作流和事件管线；计算受限、浅链、最终一致存储或大量不可回滚外部调用不是理想对象。

## 实验与结果

- **TravelReservations 的深链延迟和吞吐**：Azure AKS 上以 10 workflows/s 运行 120 秒；当链长为 10 个服务时，从图 8 读取，libDSE p95 低于约 70 ms，关闭推测约 480 ms，Temporal 约 1 s。链长固定为 3 时，libDSE 可维持超过 5,000 workflows/s，而两个基线在约 1,500 workflows/s 附近进入延迟陡升区。曲线读数为近似值。
- **EventProcessing 同时减少延迟与写入**：三阶段 DARQ 工作负载以 50,000 events/s 运行 120 秒。group commit 为 10 ms 时，libDSE 的 p50/p95 约 35/46 ms，非推测 DARQ 约 127/145 ms；窗口为 500 ms 时，两者约为 0.5/1.0 s 与 6.5/8.2 s。后者写入量从约 1,200 MB 降到约 60 MB，因为短命中间状态在落盘前被消费并裁剪（图 9）。
- **2PC 提交延迟**：4 个 shared-nothing shard、修改版 TPC-C、100% 分布式事务、10 ms group commit 下，libDSE p50/p95 为 17.9/35.1 ms，关闭推测为 35.0/70.1 ms；纯内存 Orleans 仍为 27.3/75.5 ms（图 10）。Orleans 被手工放成相同分片，但软件栈仍不同。
- **恢复代价**：在第 30 秒杀死一个 Kubernetes event node 时，推测与非推测版本都约 10 秒恢复，主要耗在容器编排；绕过重启的四次模拟故障只产生数百毫秒延迟尖峰。2PC 中保守回滚使总 abort rate 比无故障非推测基线多 0.3%，这些事务可立即重试（图 11、图 12）。
- **集成开销与规模**：自动 gRPC interceptor 在饱和时使最大吞吐降低约 25%；手工处理 header 后，协议自身延迟近乎不变、吞吐下降少于 5%（图 13）。action 到 16 线程无性能下降，三个原语均达到每秒数百万次；coordinator 从 8 到 64 个服务的 median commit latency 少于一个 5 ms refresh interval，`d=0` 时约 2 ms（图 14、图 15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| DSE 能移除深工作流中逐层累加的持久化等待 | 图 8：10 服务时 p95 低于约 70 ms，Temporal 约 1 s | 10 台 Standard_D8s_v3、写路径、10 workflows/s、120 秒 | 强 |
| 推测不只降延迟，也能裁剪短命中间写入 | 图 9：500 ms 窗口下写入约 1,200 MB 降到约 60 MB | 三阶段 DARQ、50,000 events/s；入口数据仍提前持久化 | 强 |
| 跨服务推测可以用于分布式事务 | 图 10：p50/p95 17.9/35.1 ms，优于非推测 35.0/70.1 ms 和内存 Orleans 27.3/75.5 ms | 4 shard、修改版 TPC-C、100% 分布式事务 | 强 |
| 恢复的用户可见代价在所测负载中较小 | 图 11、图 12：模拟故障数百毫秒尖峰；abort rate 多 0.3% | 4 次模拟故障及一次 pod kill；未覆盖长期分区和高故障率 | 中 |
| libDSE 协议本身开销低，但透明集成不低 | 图 13：手工 header 吞吐损失少于 5%，interceptor 约 25% | FASTER KV 微基准、单服务饱和吞吐 | 强 |

## 批判性分析

### 论证链条

论文的主链条很清楚：任务图越深，串行 persistence 越贵；将结果标成推测可以重叠等待；显式依赖图再保证发生故障时回到闭包。Travel、event stream 和 2PC 三种实现覆盖了不同控制流，说明抽象不只服务单个 workflow engine。需要收窄的说法是“透明”：协议替应用隐藏了分布式依赖计算，但开发者仍要划分 StateObject、正确实现 Restore、标记 action/sthread，并把所有外部效果放到 barrier 之后。

### 假设压力测试

只要有一次未插桩的跨服务写或错误的 Restore，依赖图就不完整，论文的安全论证不再适用。网络分区时旧、新 incarnation 可暂时并存；libDSE 会通过 `Connect` 识别新 incarnation，却把“二者不能同时更新持久存储”的 fencing 责任留给服务实现者。高故障率、高扇出依赖图会反复丢弃大量推测工作；外部副作用很多时，连续 barrier 又会把同步持久化放回关键路径。最终一致、多主写存储没有单一线性恢复点，也不自然满足 StateObject 假设。

### 实验可信度

评测同时有端到端工作流、事件处理、分布式事务、真实 pod kill、模拟故障和微基准，且“关闭推测的同实现”能较好隔离 DSE 本身。作者还让 Orleans 使用相同分片并纯内存运行，避免其默认后端拖累。不过 Temporal 使用 Cassandra/CosmosDB，libDSE 使用本地 LRS SSD 且整体软件栈不同，跨系统倍数不能全归因于 speculation。集群只有 10 个工作节点，coordinator 只测到 64 个模拟服务；没有系统改变故障频率、依赖扇出、分区时长和 rollback 集合大小。协议也只有 correctness sketch，没有完整形式化证明或 model checking。

### 系统性缺陷

libDSE 不是 drop-in library。应用状态边界、恢复实现和外部效果分类都属于正确性关键代码，出错可能静默破坏 failure transparency。recoverable-point 粒度会造成 false sharing，中心 coordinator 的 stale view 又会保守扩大回滚；论文未提供运维者直接观察“某条响应为何还在推测”“某次故障将回滚多少服务”的诊断接口。coordinator 虽不挡内部吞吐，却会挡外部可见性，恢复后还必须等所有参与者响应；一个失联服务可延长 barrier tail latency。自动 interceptor 的约 25% 最大吞吐损失也表明易用性与性能之间仍有明显差距。

## 局限与后续工作

- **局限 1**：安全与活性只有非形式化 sketch；并发故障、重复 incarnation、长网络分区和 coordinator failover 的组合状态没有穷举验证。
- **局限 2**：开发者必须正确封装状态、实现版本恢复和持久存储 fencing，迁移 legacy 服务可能需要大规模重构。
- **局限 3**：实验规模为 10 个工作节点，coordinator 到 64 个服务；没有报告高扇出下的回滚放大、长期外部可见性尾延迟或故障风暴。
- **局限 4**：barrier 会在外部效果密集的流程中吃掉推测收益，最终一致和多主存储也难以映射到单一恢复点。
- **后续工作 1**：用 TLA+、Ivy 或 model checker 覆盖双重故障、分区、coordinator 重启和旧 incarnation 并存，并把反例转成故障注入测试。
- **后续工作 2**：在 100–1,000 个服务上扫描依赖扇出与故障率，报告 rollback work amplification、barrier p99 和恢复期间的外部不可见时间。
- **后续工作 3**：让语言运行时自动捕获状态和插入 action/barrier，并以静态检查发现未插桩消息、不可回滚副作用和缺失 fencing。
- **后续工作 4**：把恢复点细分或分层，在相同元数据预算下比较 false sharing、coordinator CPU 和恢复速度。

## 相关

- **相关概念**：[[Durable-Execution]]、[[Speculative-Execution]]、[[Distributed-Rollback]]、[[Fault-Tolerance]]、[[Microservices]]
- **同类系统**：Temporal、DARQ、Orleans、DPR
- **同会议**：[[OSDI-2026]]
- **源文档**：[[osdi26-li-tianyu]]、[[osdi26-li-tianyu.pdf]]
