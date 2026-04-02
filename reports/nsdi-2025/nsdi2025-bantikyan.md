# Pineapple: Unifying Multi-Paxos and Atomic Shared Registers

**作者**：Tigran Bantikyan (Northwestern), Jonathan Zarnstorff (Unaffiliated), Te-Yen Chou (CMU), Lewis Tseng (UMass Lowell), Roberto Palmieri (Lehigh University)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/bantikyan
**源文件**：[[nsdi2025-bantikyan.pdf]]

---

## 一、背景

大规模面向用户的应用（如 Facebook TAO、WeChat PaxosStore、Microsoft OneDrive）越来越依赖线性化（linearizable）存储系统来保证高可用和强一致性。强一致性显著降低了应用开发和维护的复杂度，因此现代应用偏好强一致性而非弱一致性模型。

实现线性化存储的常见方案是使用共识算法（consensus），Multi-Paxos 和 Raft 是最广泛采用的 leader-based 共识算法，已被 Google Spanner、Azure Storage、Redis、CockroachDB、etcd 等生产系统采用。然而 leader-based 设计的核心瓶颈在于所有操作都需经过 leader 节点，leader 容易成为性能瓶颈。

目标工作负载是大规模 Web 应用中的 key-value 存储。Facebook 的数据显示 97% 的操作是 reads/writes/deletes，只有 0.2% 的操作涉及写入。因此优化 read 和 write 的性能对实际系统意义重大。

---

## 二、要解决的问题

1. **Leader 瓶颈**：Multi-Paxos/Raft 中所有操作必须经过 leader，导致 leader 成为吞吐量和尾延迟的瓶颈。PQR 只将 reads 卸载到 follower，writes 和 RMW 仍须经过 leader。

2. **阻塞操作执行（Blocking Operation Execution）**：为提升性能，一些系统（EPaxos、Gryff、PQR）将 ordering 和 execution 分离，但这导致操作执行阻塞——需要等待依赖解析或已提交的 log entry。这种阻塞特性在存在慢节点（网络抖动、GC 暂停等）时尤其有害，会导致长尾延迟和吞吐量下降。

3. **Gryff 的局限**：Gryff 将 EPaxos 和 atomic shared registers 统一，但有两个关键不足：(a) RMW 存在阻塞执行（因使用 EPaxos 的依赖追踪），导致尾延迟较高和吞吐量较低；(b) 不支持多 key 操作（one-shot transactions），无法满足 scan、range query、跨 key 原子更新等常见需求。

4. **多 key 操作的正确性挑战**：简单地对每个 key 分别使用 ABD 读写无法保证多 key 操作的线性化——可能出现"不可比较"（incomparable）的操作结果，违反线性化语义。

---

## 三、洞察与设计

**关键洞察**：Atomic shared registers 的写操作完全定义了对象状态（不依赖先前状态），因此其 total ordering 不需要是"稳定的"（stable）——ordering 可以在后续被修改而不影响正确性。这与 SMR 的"稳定"ordering 形成对比。基于这一观察，可以用成熟的逻辑时间戳（logical timestamps）技术将 Multi-Paxos 和 ABD atomic registers 统一起来：用 ABD 处理单 key reads/writes（不需要稳定 ordering），用 Multi-Paxos 处理需要稳定 ordering 的 one-shot transactions（包括 RMW），并通过统一的时间戳机制让两者无缝协作。

### 核心设计

**Pstamps（Pineapple Timestamps）**：Pineapple 设计了统一的时间戳结构 pstamp = (tag, slot)，其中 tag 是 ABD 使用的逻辑时间戳，slot 是 Multi-Paxos 的 log slot index。两个组件通过 pstamp 交互——都用 pstamp 来判断哪个操作更新。

**操作路径**：
- **Read（1-2 RTT）**：走 ABD 的 get-put 两阶段协议。n=3 时总是 1 RTT 完成；n≥5 时无并发冲突也可 1 RTT。
- **Write（2 RTT）**：走 ABD 协议，任何 follower 节点都可处理。Get 阶段获取最大 tag，Put 阶段传播新值。
- **One-shot Transaction / RMW（3 RTT）**：走 Multi-Paxos，由 leader 处理。Get 阶段读取最新值并执行 f(·)，然后通过 Paxos 共识确定 slot 顺序，最后 Put 阶段传播结果。

**非阻塞操作执行**：Pineapple 的所有操作都具有"非阻塞执行"特性——节点在与 leader 或 quorum 通信后可立即执行操作，无需等待依赖解析。这是因为 ABD 的语义天然非阻塞，而 Multi-Paxos 的单 leader 设计也保证了顺序执行无阻塞。

**Multi-key 操作的正确性**：通过 leader 决定多 key 操作的顺序，避免了 leaderless 方案（如扩展 ABD/Gryff）中多 key 操作可能出现的 incomparable 问题。

---

## 四、实现细节

- **ABD 组件（Algorithm 1）**：每个节点维护 Storage[key] = {value, pstamp}。Write 的 Get 阶段发送 GET-TAG 获取最大 pstamp，生成新 pstamp = (tag_max.ts+1, node_id, slot_max)，然后 Put 阶段传播。Read 的 Get 阶段发送 GET-VALUE 获取最大 pstamp 对应的值，Put 阶段将该值传播至 quorum 以确保 real-time ordering。

- **Multi-Paxos 组件（Algorithm 2）**：Leader 处理 RMW/one-shot transactions。Get 阶段从 quorum（含自身）获取最新值和 pstamp，执行 f(·) 生成新值，递增 slot index 生成新 pstamp = (tag_max, slot+1)，Put 阶段传播结果。

- **Leader 切换处理**：pstamp 中加入 ballot number 和 leader ID。当发现更大 ballot 时触发 Paxos Phase 1 选举新 leader。Reads 在 leader 变更期间需要 backoff 并重试，确保不返回不一致的值。

- **Quorum 大小**：标准的 ⌊n/2⌋+1 majority quorum（比 Gryff/EPaxos 的 fast quorum f+⌊(f+1)/2⌋ 更小）。

- **与 etcd 集成**：替换 etcd 的 Raft 共识层为 Pineapple，在 5 节点 etcd 部署上评估。

---

## 五、实验结果

### 实验环境
- **WAN**：5 个 AWS 区域（VA、CA、IR、JP、SY），节点间延迟 36ms-145ms
- **LAN**：CloudLab c6525-25g 节点
- **对比系统**：Multi-Paxos、Multi-Paxos with lease、PQR、EPaxos、Gryff

### 关键结果

| 场景 | 指标 | Pineapple 表现 |
|------|------|----------------|
| WAN, n=3, 读重负载 | Read 延迟 | 1 RTT 完成（与 Gryff 相同，优于 Multi-Paxos 和 PQR） |
| WAN, n=5, 平衡负载 | 吞吐量 | 比最近竞争者（PQR/EPaxos）高 10%-20% |
| WAN, n=5, 平衡负载 | 吞吐量（batched） | 比最近竞争者高 3x-4x |
| WAN, 25% 冲突 | RMW p99 延迟 | 比 Gryff 改善约 30ms |
| LAN, n=5, 平衡负载 | p50/p90 延迟 | 比 EPaxos/PQR 改善 10%-20% |
| etcd 集成, YCSB-C (100% reads) | p50/p90 延迟 | 比原始 Raft 降低约 20% |
| etcd 集成, YCSB-A 变体 (50% reads) | p50 延迟 | 比原始 Raft 降低超过 50% |
| etcd 集成, YCSB-B (95% reads) | p50/p90 延迟 | 降低 40%-50% |

### Trade-offs
- Pineapple 的 RMW/one-shot transactions 需要 3 RTT（比 Multi-Paxos 的 2 RTT 多一轮），在 RMW 占比高时性能受限
- 高冲突场景下（25%），Pineapple 的 read 尾延迟可能高于 Multi-Paxos with lease 和 PQR
- etcd 集成中，Pineapple 未实现 Raft 的 heartbeat-based batching 优化，导致吞吐量未超过 Raft

---

## 六、批判性分析

1. **RMW 开销被轻描淡写**：Pineapple 的 one-shot transaction 需要 3 RTT，比 Multi-Paxos 多一整轮。论文将"blind write"和 one-shot transaction 的适用范围描述得很广，但实际上许多应用需要 conditional writes（如 CAS），这些操作走 3-RTT 路径。论文在 etcd 实验中承认"p90 延迟和吞吐量受限于高 RMW 比例"，但实际 etcd 的使用场景中 CAS 操作非常普遍。

2. **etcd 集成实验不够充分**：etcd 实验只使用了 YCSB 工作负载，未评估 etcd 的实际使用模式（如 Kubernetes 场景中频繁的 watch、lease 续约、CAS 操作）。论文承认 Pineapple 未实现 Raft 的 disk batching 优化，这使得吞吐量比较不够公平——Pineapple 获得的延迟优势一部分可能被吞吐量的损失抵消。

3. **WAN 实验的 leader 放置偏向性**：论文的多组 WAN 实验中，leader 放置位置不一致（有时在 VA、有时在 CA、有时在 IR），这使得跨实验的横向比较变得困难。虽然不同放置确实能展示不同方面，但论文未充分说明为什么选择特定的放置策略。

4. **Gryff 吞吐量对比可能不公平**：附录 C 明确指出 Gryff 的实现不支持 client batching，因此吞吐量比较中排除了 Gryff。这意味着论文中"3x-4x throughput improvement"主要是相对于 PQR 和 Multi-Paxos 的，而非对最相关的竞争者 Gryff。

5. **正确性证明只覆盖单 key 场景**：论文正文的算法和证明集中在单 key 操作。多 key 操作和 leader change 的处理放在附录，而多 key 场景下的正确性证明只是简单声称"直接从单 key 扩展"。实际上多 key 操作的 Get 阶段需要从 quorum 读取多个 key 的值，这可能引入更复杂的并发问题。

6. **"non-blocking execution"的实际意义有限**：论文将其定位为核心优势，但实际上 Multi-Paxos/Raft 本身就是 non-blocking execution。Pineapple 的贡献在于将这一特性扩展到了 follower 处理的 reads/writes，但在 leader 处理的 RMW 上与 Multi-Paxos 并无本质区别。

---

## 七、总结

Pineapple 通过统一 Multi-Paxos 和 ABD atomic registers，将单 key reads 和 writes 从 leader 卸载到 follower 节点，使用逻辑时间戳（pstamp）无缝连接两个组件。其核心优势是所有操作都具有非阻塞执行特性，改善了尾延迟和吞吐量。在 WAN 和 LAN 的广泛评估中，Pineapple 在读写混合工作负载下持续优于 Multi-Paxos、EPaxos 和 PQR，并在 etcd 集成中将中位延迟降低超过 50%。主要局限在于 one-shot transactions/RMW 需要 3 RTT，在 RMW 比例高的工作负载中性能不如 leader-based 方案。该系统基于成熟技术构建（Multi-Paxos + ABD + 逻辑时间戳），设计简洁，适合集成到现有的 leader-based 共识系统中以优化读写密集型 Web 应用的性能。
