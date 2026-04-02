# Runtime Protocol Refinement Checking for Distributed Protocol Implementations

**作者**：Ding Ding, Zhanghan Wang, Jinyang Li, Aurojit Panda (NYU)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/ding
**源文件**：[nsdi2025-ding.pdf](../../papers/nsdi-2025/nsdi2025-ding.pdf)

---

## 一、背景

分布式协议（如 Raft、ZAB）是所有容错应用的核心，但将协议正确地实现为可部署的分布式协议实现（Distributed Protocol Implementation, DPI）仍然极具挑战。即使协议本身经过形式化验证（如 TLA+ model checking、Ivy 归纳不变量推导），实际部署的 DPI（如 Etcd、ZooKeeper、Redis Raft）仍然频繁出现安全性 bug——例如 Etcd 曾在某些场景下返回过期值，ZooKeeper 在 leader election 期间丢失更新。

现有的方法可分为几类：(1) 协议验证工具（TLA+、Ivy）只能证明协议正确，无法防止实现 bug；(2) 静态 refinement proof（IronFleet、Verus）能连接协议与实现，但对代码编写方式有严格限制，难以应用于高性能生产系统；(3) 运行时验证工具（D3S、Aragog、Oathkeeper）需要收集全局一致快照，引入额外的跨节点通信和协调开销，在节点故障时难以工作；(4) Fuzz testing 和 model checking 无法保证覆盖所有 bug。

---

## 二、要解决的问题

核心问题是：**如何在生产环境中检测 DPI 的协议实现 bug，同时不修改 DPI 代码、不引入跨节点通信、不影响容错保证？**

具体痛点包括：

1. **静态 refinement proof 不实用**：IronFleet、Verus 等要求限制代码编写方式和使用的库，无法直接应用于 Etcd、ZooKeeper 等已有系统。这些工具还依赖对 runtime 环境（如 syscall 语义）的假设，这些假设可能不成立。
2. **运行时验证需要全局协调**：检查 agreement 等全局性质需要收集一致性快照，引入通信开销和故障时的可用性问题。
3. **测试覆盖不完整**：Fuzz testing 和 model checking 只能在测试阶段发现 bug，无法保证所有 bug 在部署前被发现。
4. **Trace validation 假设过强**：最近的 trace validation 方法要求 DPI 添加额外的日志语句来标记 linearization points，且假设测试完成后才进行检查，无法用于在线部署。

---

## 三、洞察与设计

**关键洞察**：在 fail-stop 故障模型下，分布式协议的全局安全性质成立当且仅当每个活跃进程都正确实现了协议。因此，可以通过**独立地、本地地**检查每个 DPI 进程的行为是否符合协议规范来检测 bug，无需跨节点通信或协调。

基于这一洞察，论文提出了 Runtime Protocol Refinement Checking (RPRC) 方法，并实现了 Ellsberg 系统。其核心设计如下：

### 架构

- 每个 DPI 进程旁部署一个 co-located 的 Ellsberg 实例
- Ellsberg 实例通过 IPC channel 获取 co-located 进程的消息 trace（所有发送和接收的消息）
- 将 DPI 视为黑盒，不访问其内部状态
- Ellsberg 实例之间不通信

### RPRC 算法

Ellsberg 维护一组 simulation states S，遍历消息 trace：
- **收到 incoming message**：将消息加入所有 simulation state 的 pending set（或在满足 `apply_asap?` 条件时立即应用）
- **观察到 outgoing message m**：使用 `infer_inducing` 推断 m 对应的协议状态，然后通过 BFS 搜索从当前 simulation state 出发、通过重排 pending messages 是否能到达 m-inducing state。若不存在任何可达的 m-inducing state，则报告 bug

### 关键优化

1. **`apply_asap?`**：识别可以立即应用而不影响正确性的事件（类似 partial-order reduction），大幅减少 pending messages 和需要探索的调度数量。在实验中将 |S| 从平均数百个降至 1 个
2. **`reachable` 剪枝**：使用用户提供的 reachable 函数提前剪掉不可能到达 m-inducing state 的分支，pruning 率达 40-80%
3. **Lookahead**：前瞻下一个特定类型的 outgoing message 来进一步缩小 m-inducing state 集合

### 规范编写

用户需从 TLA+ 规范派生 Ellsberg 规范，包括：协议状态结构 ProtState、状态转移函数 apply、状态相等判断 equal、从 outgoing message 推断状态的 infer_inducing 函数，以及优化函数 apply_asap?、reachable 和 lookahead_type。论文提供了一个测试工具，利用 TLC bounded model checking 生成 trace 来验证 Ellsberg 规范与 TLA+ 规范的一致性。

---

## 四、实现细节

- **语言**：Go 实现，协议规范需用 Go 编写并与 Ellsberg 一起编译
- **总代码量**：约 4500 行 Go（含两个协议规范），测试工具约 500 行 Python
- **规范长度**：Raft 规范约 500 行，ZAB 规范约 2000 行；Etcd 的 Ellsberg 规范 952 行，RedisRaft 894 行，ZooKeeper 989 行，均短于对应的 baseline 规范（CCF Raft 1503 行，ZooKeeper TLA+ 1615 行）
- **消息映射**：每个 DPI 需要额外的 mapping 代码将实现消息映射到规范消息（Etcd 356 行，ZooKeeper 370 行，RedisRaft 380 行）
- **Trace 收集**：通过 IPC channel，需修改 DPI 的网络 API 函数（Etcd 11 个函数，ZooKeeper 31 个函数，RedisRaft 10 个函数）
- **`apply_asap?` 正确性验证**：使用 Z3 SMT solver 机械化检查四个充分条件（Order Preserving、Constraints Preserving、Expansion、Reorder Safety）

---

## 五、实验结果

实验平台：CloudLab C6525-25G 实例（16 核 AMD EPYC 7302P，128GB RAM，25Gbps NIC），3 节点和 5 节点集群。Ellsberg 实例限制使用 2 个核心，每秒处理一次 trace。

### Bug 检测（§6.2）

| DPI | Bug | 类型 |
|-----|-----|------|
| Etcd | #741 | Linearizable read |
| Etcd | #7331 | Leader election 后 stale read |
| Etcd | #12133 | Reconfiguration |
| Etcd | #7280 | Reconfiguration |
| ZooKeeper | #1154 | Data inconsistency |
| RedisRaft | #17 | Reconfiguration |
| RedisRaft | #19 | Linearizable read |
| RedisRaft | #52 | Lost updates |
| RedisRaft | #256 | Reconfiguration |
| RedisRaft | Unreported | Reconfiguration（新发现） |

Ellsberg 成功检测了所有 10 个 bug，包括 1 个之前未报告的 RedisRaft reconfiguration bug。

### 性能影响（§6.3）

| 指标 | 结果 |
|------|------|
| 延迟影响 | 最差情况 99th percentile 增加 10.7%（Redis read-heavy: 7.25ms → 8.03ms） |
| 吞吐量影响 | 无可观测影响 |
| 内存开销 | 最小（平均 |S|=1，0-5 个 pending messages） |
| 网络开销 | 无（Ellsberg 不使用网络） |
| CPU 占用 | 2 个核心（通过 taskset 限制） |

### Ellsberg 吞吐（§6.4）

| DPI | Ellsberg 吞吐 vs DPI 吞吐 |
|-----|---------------------------|
| Etcd | 2.0×–51.7× |
| ZooKeeper | 1.4×–29.7× |
| RedisRaft | 3.1×–25.5× |

处理 1 秒 trace 耗时：leader 节点 30-700ms，follower 节点 20-180ms。Bug 发现延迟约 1.7 秒。

### 优化效果

- **`apply_asap?`**：禁用后 pending messages 持续增长（Etcd 平均约 444 个 simulation states），启用后 |S| 始终为 1
- **`reachable` 剪枝**：ZooKeeper pruning 率 > 75%，Etcd 和 RedisRaft 在 40-80% 之间

---

## 六、批判性分析

1. **只能检测消息层面的 bug**：Ellsberg 只能检测导致错误消息发送（内容或顺序不一致）的 bug，无法检测死锁、活锁、数据损坏（不反映在消息中的）、性能退化等问题。论文虽然承认了这一点，但在 abstract 和 introduction 中给人的印象是一个通用的 bug 检测方案，实际能力远比预期更窄。

2. **"不修改 DPI"的说法需要打折扣**：虽然论文强调 Ellsberg 将 DPI 视为黑盒，但实际上需要修改 DPI 的网络 API 来建立 IPC channel（Etcd 11 个函数、ZooKeeper 31 个函数），并需要编写 356-380 行的消息映射代码。这并非零侵入。

3. **规范编写负担**：用户需要从 TLA+ 手动派生约 900-1000 行的 Ellsberg 规范，还需要编写需要深入理解协议的 `apply_asap?`、`reachable` 和 `lookahead_type` 函数。论文声称这比编写实现简单，但仍然需要相当的专业知识。且 `apply_asap?` 如果写错会导致漏报。

4. **Bug 检测实验的说服力有限**：所有测试的 bug 都是已知的历史 bug，通过在旧版本代码上复现或手动注入来验证。唯一的新发现（RedisRaft Unreported bug）是在 fuzzing loop 中发现的，这意味着 bug 本身在测试阶段就可以被发现——恰好说明了 RPRC 在这个案例中并没有体现出"部署后发现 bug"的核心价值。

5. **适用性限制比论文暗示的更大**：论文在 §3.5 承认对 MVCC 数据库不适用、对并发事务验证协议不适用，但这些在 abstract 中被完全忽略。此外，协议必须有能推断完整状态的消息，否则 simulation state 集合会无限增长——这个限制在多大范围内成立缺乏系统性分析。

6. **Shared-fate 假设的实际影响**：Ellsberg 要求与 DPI 进程共命运（co-located 且 shared-fate），这意味着当 Ellsberg 实例失败时其 DPI 进程也必须被杀死。这是一个影响可用性的强假设，论文没有讨论其对生产部署的实际影响。

---

## 七、总结

本文提出了 RPRC（运行时协议精化检查）方法和 Ellsberg 系统，通过在每个 DPI 进程旁部署一个本地检查器，对比消息 trace 与协议规范的模拟执行来检测实现 bug。核心贡献在于利用 fail-stop 模型下"局部正确即全局正确"的性质，避免了跨节点通信和协调。系统在 Etcd、ZooKeeper 和 Redis Raft 上成功检测了 10 个已知 bug（含 1 个新发现），性能开销很小（延迟增加 < 11%，吞吐无影响）。适用于 fail-stop 模型下基于 I/O automaton 的分布式协议，主要局限在于只能检测消息层面的 bug、需要手动编写规范、且对 DPI 有一定侵入性修改要求。
