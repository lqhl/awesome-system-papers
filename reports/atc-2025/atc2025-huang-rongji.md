# Chitu: Avoiding Unnecessary Fallback in Byzantine Consensus

**作者**：Rongji Huang*, Xiangzhe Wang*, Xiaofeng Yan*, Lei Fan, Guangtao Xue, Shengyun Liu（上海交通大学，上海可信数据流通治理与 Web3 重点实验室）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/huang-rongji
**源文件**：[atc2025-huang-rongji.pdf](../../papers/atc-2025/atc2025-huang-rongji.pdf)

---

## 一、背景

Byzantine Fault Tolerant (BFT) 共识协议是区块链和去中心化应用的核心组件。现有 BFT 协议主要分为两大类：

1. **部分同步协议**（如 PBFT、HotStuff）：依赖单一 leader 协调共识，在 leader 正常且网络稳定时可快速确定性终止。但 leader 可能成为性能瓶颈，且网络不稳定时会触发昂贵的 view change 操作（至少耗时 Δ），甚至连续 view change 导致 liveness 丧失。

2. **异步协议**（如 Tusk、DAG-Rider）：不预选 leader，通过 random coin 实现概率性终止。但 coin-flipping 始终在关键路径上，增加了通信轮次和延迟。

近年来，基于 DAG 的 BFT 协议（如 Tusk、BullShark）成为主流趋势，将共识嵌入 DAG 的动态构建中，简化设计和实现。然而这些协议仍然存在上述根本性限制。

---

## 二、要解决的问题

1. **Leader 瓶颈问题**：部分同步协议中 leader 始终在关键路径上，无论系统状态如何。Leader 崩溃或变慢时，需等待超时 Δ 并触发 view change，延迟显著增加。

2. **随机化开销问题**：异步协议中 random coin 始终在执行路径上，即使所有节点正常、网络稳定，也必须经历多轮通信才能完成 coin-flipping，导致延迟远高于部分同步协议的最佳情况。

3. **现有 fast path 的局限**：一些协议（如 Bolt）引入了 fast path，但其 fast path 仍依赖 leader 和同步假设，本质上继承了部分同步协议的缺陷。

核心问题：**能否设计一种协议，在大多数节点一致时完全跳过 leader/random coin，仅在节点意见分歧时才回退到 fallback 机制？**

---

## 三、洞察与设计

**关键洞察**：leader 选举和 random coin 本质上都不是共识问题的固有需求——它们只是为了应对 FLP 不可能性而引入的 fallback 机制。如果正确节点仅通过消息交换就能达成一致（即每个 proposal 都变成 univalent 状态），则无需任何额外机制。只有当节点对某个 proposal 存在分歧（bivalent）时，才需要 fallback。

基于此洞察，论文提出 **Fair-Fallback 框架**：

- **Fast path**：节点首先尝试通过纯消息交换达成共识，无需任何特殊角色或同步假设。对于每个 proposal，如果至少 n-f 个节点观察到它（1-valent）或至少 n-f 个节点未观察到它（0-valent），则该 proposal 可通过 fast path 直接决定。
- **Fallback**：仅当某些 proposal 处于 bivalent 状态时，才回退到 random coin 或 leader 选举。
- **两条路径并发进行**，不存在显式切换，且保证无论走哪条路径都产生相同结果。

在此框架之上，论文提出 **Chitu** 协议，基于 certified DAG 结构：

- 每轮每个节点通过 Byzantine Reliable Broadcast (BRB) 广播一个 vertex
- 引入 **strong observe** 概念：vertex v 在 round r+2 strongly observe vertex u（round r），当且仅当 round r+1 中有至少 f+1 个 vertex 同时连接 v 和 u
- Fast path 判定：round r+1 的 n-f 个 vertex 足以判断 round r 中每个 vertex 是 1-valent 还是 0-valent
- **Adaptive wait 机制**：节点在收到 n-f 个 vertex 后不立即推进下一轮，而是继续等待已被 f+1 个节点 pre-accept 的 vertex 被 deliver，从而显著提高 fast path 的成功率

---

## 四、实现细节

**DAG 构建**：
- 每个 vertex 包含 round number、source node、transactions、edges（至少 n-f 条指向上一轮 vertex）
- BRB 协议分两阶段：VAL（广播 vertex）→ PREPARE（签名投票），收到 n-f 个 PREPARE 即 deliver
- 支持 weak edge：vertex 可跨轮连接到更早的 vertex，确保慢节点的 proposal 不被永久忽略

**Commit 规则**：
- **Fast path**：当 round r+1 deliver 了 n-f 个 vertex 后，检查 round r 中每个 vertex 的状态——被 n-f 个 vertex 观察则为 1-valent，被 n-f 个 vertex 未观察则为 0-valent；全部 univalent 则可 fast commit
- **Normal path**：通过 random coin 选出 leader vertex，递归决定之前未决的轮次。奇偶轮分开处理
- 两条路径通过 Invariant 4.1 保证一致性：fast path 决定的 1-valent vertex 集合 = normal path 通过 leader 决定的 strongly observed vertex 集合

**Adaptive wait**：
- 节点跟踪 pre-accepted vertex（被 f+1 个节点接收）
- 持续等待直到所有 pre-accepted vertex 被 deliver，或检测到 equivocation
- 等待期间转发 VAL 和 PREPARE 消息帮助其他节点

**实现**：Golang 编写，使用 noise 库做异步网络，SHA256 哈希，Ed25519 签名，BLS 门限签名实现 random coin。代码开源于 GitHub。

---

## 五、实验结果

实验平台：AWS EC2 t3.2xlarge（8 vCPU, 32 GiB RAM, 5 Gbps），5 个全球区域（Ohio, Singapore, Tokyo, Canada Central, Frankfurt），平均 RTT 135ms。对比基线：Tusk、BullShark。

| 场景 | Chitu 延迟 | Tusk 延迟 | BullShark 延迟 | Chitu 改进 |
|------|-----------|-----------|---------------|-----------|
| n=4, 无故障, 100 reqs/50ms | ~440ms | ~2519ms | - | **82.5% 降低** vs Tusk |
| n=10, 无故障, 100 reqs/50ms | ~485ms | ~2729ms | - | **82.2% 降低** vs Tusk |
| n=100, 无故障 | 延迟仍低于对比方案 | - | - | ~50% fast path commit |
| n=4, 1 crash fault | ~550ms | 显著增加 | >5s | fast path 100% 生效 |
| n=10, 3 crash faults | 类似 | 显著增加 | >5s | fast path 100% 生效 |
| n=10, 3 Byzantine faults | ~2x crash fault | - | - | 吞吐仅降 5.78% |

**Adaptive wait 效果**：
- 有 wait：99.5% fast path commit rate（100 reqs/50ms, n=4）
- 无 wait：仅 12% fast path commit rate，延迟高 1.75x（772ms vs 440ms）
- n=10 时无 wait 机制几乎没有 round 能走 fast path

---

## 六、批判性分析

1. **可扩展性是根本瓶颈**：论文自己承认 fast path 成功概率为 p^n（p 为单个 vertex 变为 univalent 的概率），随节点数指数下降。n=100 时 fast path commit 率已降至约 50%，更大规模部署会迅速失效。论文提出的"选子集做 proposer"的解决方案仅一笔带过，留给 future work，但这恰恰是实际部署最关键的问题。

2. **通信复杂度较高**：每轮 O(n²) 消息复杂度，总通信复杂度 O(n⁴)——与 Tusk 相同。论文以"用消息复杂度换更少通信轮次"来辩护，但在大规模场景下这是严重的限制。BRB 的 all-to-all 模式在 WAN 上的实际带宽开销未被充分讨论。

3. **Byzantine 攻击场景评估过于温和**：实验中 Byzantine 节点只是"发空 payload、不参与消息交换"，这是最简单的攻击模式。论文承认单个 Byzantine 节点就足以禁用 fast path，但实际的 message scheduling 攻击实验缺失。"攻击 feasible but not trivial" 的说法缺乏量化支持。

4. **Skewed distribution 实验暴露弱点**：3 个美国节点 + 1 个悉尼节点的场景下，几乎没有来自悉尼的 vertex 被 fast path commit，需要依靠 weak edge 间接提交。这意味着在真实 WAN 部署中（节点延迟差异大是常态），fast path 的优势会大打折扣。

5. **与 BullShark 的对比不够公平**：BullShark 默认 Δ=5s 导致 crash fault 时延迟飙升，但这是其实现的默认配置问题，不是协议本身的根本限制。合理调优后的 BullShark 表现可能会更好。

6. **Best case 4 message delays 的实际意义有限**：需要所有 vertex 都是 univalent 才能走 fast path，这在实际部署中是一个强条件。论文的核心卖点在很大程度上依赖于 adaptive wait 机制"人为"制造 fast path 条件。

---

## 七、总结

Chitu 提出了 Fair-Fallback 框架，核心思想是将 leader 选举和 random coin 从共识的关键路径上移除，仅在节点意见分歧时作为 fallback 使用。在此框架下设计的 Chitu 协议基于 certified DAG，通过 adaptive wait 机制实现了高比例的 fast path commit。在小规模（n=4~10）无故障场景下效果显著，延迟降低超过 80%。但其可扩展性受限于 fast path 成功率的指数下降，O(n⁴) 通信复杂度也限制了大规模部署。该工作更多是对共识协议设计空间的理论探索，距离替代现有主流方案尚有差距。
