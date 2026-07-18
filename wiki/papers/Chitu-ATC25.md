---
type: paper
name: Chitu
full_title: "Chitu: Avoiding Unnecessary Fallback in Byzantine Consensus"
authors: [Rongji Huang, Xiangzhe Wang, Xiaofeng Yan, Lei Fan, Guangtao Xue, Shengyun Liu]
venue: ATC
year: 2025
tags: [byzantine-consensus, bft, dag-bft, asynchronous-consensus, blockchain]
source_pdf: "[[atc2025-huang-rongji.pdf]]"
source_md: "[[atc2025-huang-rongji]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# Chitu: Avoiding Unnecessary Fallback in Byzantine Consensus (ATC 2025)

> **一句话总结**：Chitu 的关键观察是 leader / random coin 并非 consensus 的内在步骤，只有当 correct nodes 对 proposal 产生 bivalent 分歧时才需要 fallback；它把这个 Fair-Fallback 规则嵌入异步 certified DAG，在常见收敛场景下 4 个 message delays 提交并绕过 random coin，AWS WAN 上相比 Tusk 端到端延迟最多降低 82.5%，但 fast-path 命中率随节点数和恶意调度压力变脆。

## 问题与动机

BFT state-machine replication 的主流协议在 latency 与 liveness 模型之间有一个长期张力。部分同步协议如 [[PBFT]]、[[HotStuff]] 和 [[BullShark]] 把单个 leader 放在 normal path 上：leader 正常且网络足够同步时延迟可预测，但 leader slow / crashed / partitioned 时需要 view change，WAN 里固定 timeout 或最大网络延迟假设会直接变成不可用窗口。异步协议如 [[Tusk]]、[[DAG-Rider]] 和 [[HoneyBadgerBFT]] 不依赖同步假设，却通常把 random coin 或 leader-after-the-fact 放在提交路径上，因此 termination 是概率性的，且无故障时也要付更多通信轮次。

论文的核心问题不是“再优化一次 DAG-BFT”，而是重新问：在一个 consensus instance 里，什么时候真的需要 leader、timer 或 random coin？作者认为这些机制只是用来打破 bivalent proposal 的 fallback，不应在 correct nodes 已经通过消息交换形成一致观察时仍然处在关键路径上。这个视角把 Red Belly 和 MyTumbler 的 fast termination 抽象为一个更一般的 Fair-Fallback 框架。

Chitu 是该框架在异步 certified DAG 上的实例化。它继承 [[Tusk]] / [[DAG-Rider]] 的 DAG construction 和 random-coin fallback，但增加了 leaderless fast path：如果一轮中的每个 vertex 都能被判定为 1-valent 或 0-valent，就立即提交 1-valent 集合；只有出现 bivalent vertex 时才依靠后续 leader vertex / random coin 决定。目标是在不牺牲异步 liveness 的前提下，把 common case latency 拉近部分同步协议的 normal case。

## 关键观察 / 隐含假设

- **观察 1：fallback 不是 consensus 的内在步骤，而是 bivalence 的处理手段**。论文用 one-shot consensus / binary agreement 的 valency 语言说明：若所有 proposal 仅靠 message exchange 已经变成 univalent，leader election、timer 或 random coin 不会改变最终结果，只会增加 latency。
  - **依赖假设**：常见部署中 adversarial scheduler 不是持续全能的；多数时间 correct nodes 的消息观察会自然收敛。
  - **可能失效场景**：一个 Byzantine node 只要能把自己的 proposal 精确维持在“被多于 f 但少于 n-f 个下一轮 vertex observe”的区间，就能让该轮 fast path 失败；论文也承认这种攻击可行但 timing 不容易。

- **观察 2：DAG 可以同时承载 proposal、notification 和 fallback leader，无需显式 path switch**。在 Chitu 中，round r 的 vertex 是 proposal，round r+1 的边又相当于对 round r proposal 的 notification；后续 leader vertex 则通过 strongly observe 规则决定未决轮次。
  - **依赖假设**：certified DAG 的 BRB 成本可以接受，且每个节点维护本地 DAG 后能一致判断 path / observe / strongly observe。
  - **可能失效场景**：节点数扩大时，all-to-all BRB、签名集合、DAG path 检查和边传播会把收益从 message delay 转移成 bandwidth / CPU / metadata 压力。

- **观察 3：fast path 的关键不是“越快进入下一轮越好”，而是“在不破坏 liveness 的情况下多等一点边”**。Adaptive wait 等待 pre-accepted vertex 被 deliver，并转发 VAL / PREPARE 消息，让更多上一轮 vertex 被下一轮足够多节点 observe，从而提高 1-valent 概率。
  - **证据强度**：强。n=4、每客户端 100 reqs/50ms 时，wait 机制把 fast-path commit 比例从 12% 提高到 99.5%，latency 从 772ms 降到 440ms；重载下仍约 92.5%。
  - **可能失效场景**：Byzantine nodes 可以利用 wait 机制迫使节点 deliver n 个 vertex 再前进；大 payload、低带宽或高度异构 WAN 下，“pre-accepted implies soon deliverable”这个信号会变弱。

- **假设 1：round-level fast path 概率在目标规模内足够高**。论文自己指出，如果单个 vertex 变成 univalent 的概率是 p，则整轮 fast path 近似是 p^n；n 增大时会快速衰减。
  - **证据强度**：中。小规模结果很强，n=10 仍有明显收益；但 n=100 的 fast-path 比例已经显著下降，论文建议未来改成 proposer subset + validator set。

- **假设 2：latency 是比 communication complexity 更值得优化的主目标**。Chitu 用 O(n^3) message complexity 和 O(n^4) communication complexity 换更少 message delays；Tusk message complexity 为 O(n^2)，communication complexity同为 O(n^4)。
  - **证据强度**：中。AWS WAN 实验支持 latency 改善，但没有系统展开 CPU、network egress cost、signature verification、DAG metadata 和 cloud burst bandwidth 对成本的影响。

## 核心方法

**Fair-Fallback 框架**把 consensus 拆成 fast path 与 fallback，但两者不是“切换式”的两套协议。Fast path 只靠消息交换判断 proposal 是否 univalent；fallback 可以是 random coin、leader election 或 timer，用于处理 bivalent proposal。安全性靠两个 invariant：fast-path commit 条件必须蕴含 fallback commit 条件；fast-path abort 条件必须排斥 fallback commit 条件。这样即使某些节点先 fast-path decide，另一些节点之后 normal-path decide，最终 1-valent 集合也一致。

**DAG construction**沿用 certified DAG 思路。每个节点每 round 提议一个 vertex，包含 round number、source、transactions 和指向上一轮至少 n-f 个 vertex 的 edges。Vertex 通过两阶段 [[Reliable-Broadcast|BRB]] 传播：VAL 后收集 PREPARE，收到 n-f 个 PREPARE 后 deliver 到本地 DAG。BRB 保证 Byzantine proposer 不能让 correct nodes deliver 不同 vertex，这是 fast path 和 fallback 能共享本地 DAG 视图的基础。

**Fast path commit rule**把 round r 的 vertex 分成三类：被 round r+1 中至少 n-f 个 vertex observe 则为 1-valent；被至少 n-f 个 vertex 不 observe 则为 0-valent；介于两者之间则为 bivalent。若 round r 的所有 vertex 都已 univalent，节点可以立即 decide 该轮并提交 1-valent vertex。这里的“立即”仍受顺序提交约束：round r 只有在所有前序 round 已提交后才真正 commit。

**Normal path / fallback**使用 random coin 选择 leader vertex，类似 [[Tusk]]。Leader vertex 若被后续至少 f+1 个 vertex observe，或被后续 valid leader observe，则有效。Chitu 将 odd rounds 与 even rounds 分开处理，因为相邻轮 leader 不一定存在 DAG path；一个 valid leader 递归决定同奇偶性的前序未决轮次。对于被 leader 强观察的 vertex 判为 1-valent，否则判为 0-valent。

**Strongly observe**是连接两条路径的关键定义：round r' 的 vertex v strongly observes round r 的 vertex u，若存在至少 f+1 个 round r+1 vertex 同时连接 v 与 u。若 u 被 round r+1 的 2f+1 个 vertex observe，则任何 round r+2 及之后的 vertex 都 strongly observes u；若 u 被少于 f+1 个 round r+1 vertex observe，则之后任何 vertex 都不可能 strongly observe u。这个交集性质保证 fast path 和 normal path 会对同一 vertex 给出一致状态。

**Adaptive wait**解决“刚好只连 n-f 条边导致 bivalent 增多”的工程问题。节点 deliver n-f 个 round-r vertex 后，不立刻进入 r+1，而是继续等待所有 pre-accepted vertex，即已被 f+1 个节点看到的 vertex；等待期间转发 VAL 和 f+1 PREPARE，促使它们被所有 correct nodes deliver，或暴露 equivocation 后停止等待。这个机制不引入固定 timeout，却会增加边数，提高 fast-path 命中率。

**Weak edges**用于处理慢节点长期掉队。若某节点的 vertex 没被下一轮普通边纳入，后续 vertex 可以用 weak edges 连接更早 round 的 vertex；只要承载 weak edge 的 vertex 被提交，旧 vertex 也能被间接提交。这在 skewed geography 实验中用于提交 Sydney 节点的落后 proposal。

## 设计取舍

- **latency 换 communication / implementation cost**：Chitu 用更重的 all-to-all BRB、更多边和 adaptive forwarding 换 common case 少走 random coin。对 WAN latency 敏感的 blockchain workload 合理，但对带宽、CPU 或 egress 成本敏感的部署可能不划算。
- **leaderless common case 换更严格的 round-level 条件**：只要一轮内存在 bivalent vertex，整轮 fast path 就不能完成；节点数越大，p^n 衰减越明显。
- **adaptive wait 提高 fast-path 率，也扩大可被拖慢的面**：等待 pre-accepted vertex 比固定 timeout 更 responsive，但 Byzantine 节点可以利用它让所有 correct nodes 多做转发和 deliver。
- **certified DAG 简化安全证明，也保留了重认证成本**：BRB 避免 equivocation 复杂性，但每个 vertex 携带签名集合和上一轮边，metadata 规模随 n 上升明显。
- **odd/even leader separation 保证路径存在性，但可能延迟提交**：即使某个后续 round 走 fast path，如果更早同奇偶轮还未被 fallback 决定，commit 仍需等待 sequential ordering。

## 实验与结果

- **实验设置**：Go 实现，noise networking，SHA256，Ed25519，BLS threshold signature 生成 random coin；AWS EC2 t3.2xlarge，8 vCPU、32 GiB RAM、5 Gbps burst bandwidth，Ubuntu 22.04.4；节点跨 Ohio、Singapore、Tokyo、Canada Central、Frankfurt，平均 RTT 135ms；request size 1000B。
- **复杂度对比**：分析表给出 Chitu best / normal / worst case 分别为 4 / 9 / 15 message delays；Tusk 为 14.5 / 14.5 / 25。Chitu message complexity 为 O(n^3)，高于 Tusk 的 O(n^2)，communication complexity 二者都是 O(n^4)。
- **fault-free latency**：n=4 时，每客户端 100 reqs/50ms 下 Chitu 440ms vs Tusk 2519ms，端到端延迟降低 82.5%；n=10 时 485ms vs 2729ms，降低 82.2%。未饱和时 Chitu latency 约 500ms。
- **wait ablation**：n=4 同一负载点，adaptive wait 让 fast-path commit 比例达到 99.5%；没有 wait 只有 12%，latency 为 772ms vs 440ms。重负载下 wait 版本 fast-path 比例下降但仍约 92.5%；n=10 时无 wait 几乎没有 round 能走 fast path。
- **crash faults**：预先关闭 f 个节点时，Chitu 反而能确定性绕过 random coin，因为每个 live vertex 恰好被 n-f 个下一轮 vertex observe，没有 bivalent；轻负载 latency 小幅升到约 550ms。BullShark 因 leader timeout 在关键路径上，平均 latency 超过 5s，默认 Delta 为 5s。
- **Byzantine faults**：n=10，Canada Central 一个节点、Frankfurt 两个节点 Byzantine；实验强制关闭 fast path 并让 wait 机制被恶意利用。未饱和时平均 latency 约为 crash-fault 情况的 2x；peak throughput 从 65.7 ktps 降到 61.9 ktps，下降 5.78%。
- **skewed distribution**：n=4 分布在 N. Virginia、Ohio、N. California、Sydney。美国三个节点能推进 DAG，Sydney 明显掉队；Chitu 仍低于 Tusk / BullShark，并通过 weak edges 提交 Sydney 的旧 vertex，但 Sydney 侧 latency 高。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Chitu 降低 fault-free WAN latency | n=4 为 440 ms 对 Tusk 2519 ms，n=10 为 485 ms 对 2729 ms（§5.1，Fig. 7–8） | AWS five-region、1000 B request、100 req/client/50 ms，不是 production trace | high |
| Adaptive wait 提高 fast-path completion | n=4 时 99.5% 对无 wait 的 12%，latency 440 ms 对 772 ms（§5.1，Fig. 10） | fault-free implementation ablation；重载下约 92.5% | high |
| 预先注入 crash fault 时可避免 random coin | disabled f node 时 live vertex 恰好被 n-f node observe，light-load latency 约 550 ms（§5.2，Fig. 11–13） | fault 在 run 前注入，不覆盖任意 crash timing/recovery | high |
| 构造性 Byzantine 情景下吞吐降幅有限 | n=10、三 Byzantine node：61.9 对 crash case 65.7 ktps，下降 5.78%（§5.3，Fig. 15） | 特定 empty-proposal/no-exchange 攻击，不是 general adversarial bound | high |
| fast path 有规模边界 | 作者的 `p^n` 模型中 n=100 时约 50% vertex fast-path commit（§5.1，Fig. 9） | 独立性假设的分析，proposer subset 尚属 future work | medium |

## Critical Analysis

### 论证链条

论文的主链条比较闭合：leader / coin 只负责处理 bivalence，而不是 consensus 的必要步骤；DAG 的边可以表示 notification；strongly observe 的交集性质让 fast path 与 fallback 给出一致 1-valent 集合；adaptive wait 则提升 common case 的 univalent 概率。这个链条既有形式化证明 sketch，也有 ablation 支撑 wait 机制的必要性。

需要注意的是，论文把“无故障 / crash / skew / 人造 Byzantine”实验组合成“典型场景”的证据，但没有证明真实 blockchain production workload 中 bivalent proposal 的分布确实低。Chitu 的性能优势高度依赖 fast-path 命中率；如果真实网络经常出现局部拥塞、mempool payload 差异或恶意 timing，系统会更频繁退回 normal path。

### 假设压力测试

最大压力点是 p^n。Chitu 要 round-level fast path 成功，必须每个 vertex 都 univalent；节点数增长时，哪怕单个 vertex 的 univalent 概率很高，整轮成功率也会指数下降。论文在 n=100 仍展示 latency 优势，但也承认 fast-path 比例下降，并把 proposer subset 留作 future work。这意味着 Chitu 更像“中小 validator set 的低延迟协议”，而不是直接可扩到大规模 permissionless validator set 的最终形态。

第二个压力点是 adaptive wait 的安全-性能边界。它没有固定 timeout，这是优点；但它把“被 f+1 节点看到”作为值得等待的信号。若 Byzantine nodes 能构造大量 pre-accepted 但昂贵的 vertex，或用空 payload / 异步转发拖慢 round advancement，wait 就从优化器变成攻击面。论文的 Byzantine 实验覆盖了恶意利用 wait 的一种场景，但还没有系统探索不同 payload size、带宽瓶颈和签名验证开销下的 worst-case cost。

第三个压力点是 deployment heterogeneity。Skewed experiment 表明 Sydney 节点几乎跟不上美国三节点的 DAG construction；Chitu 可以通过 weak edges 让它最终提交，但这更像 availability fallback，不是低延迟保证。若 validator geography 更分散，fast path 可能自然偏向低 RTT clique，弱节点的 proposal 延迟会成为 fairness / inclusion-latency 问题。

### 实验可信度

实验选择 [[Tusk]] 和 [[BullShark]] 很合理：前者代表异步 random-coin DAG，后者代表部分同步 leader-based DAG。AWS 五区域也比单机或单 region 更接近 blockchain WAN。wait ablation 是整篇最有说服力的部分，因为它直接验证了 Chitu 的关键工程机制，而不是只比较 end-to-end latency。

不足在于 baseline 与实现成本没有完全拆开。Tusk / BullShark 使用 Narwhal 的公开实现和 worker separation，Chitu 是作者自己的 Go 实现；论文没有足够细地报告 CPU utilization、bandwidth、signature verification breakdown、DAG metadata size、BLS coin cost、GC / memory pressure。由于 Chitu 有更高 message complexity，缺少这些成本指标会让“latency 降低”难以转换为“单位成本吞吐更好”。

Benchmark 也偏 synthetic。客户端按固定 reqs/50ms 发送 1000B request，不能覆盖真实 blockchain mempool 的 burst、transaction dependency、validator stake distribution、DoS traffic、block propagation variance 或 production trace。Byzantine 实验是有价值的下界测试，但攻击模型是作者构造的三个条件，不等于系统性 adversarial evaluation。

### 系统性缺陷

论文未充分讨论 membership change、validator churn、checkpoint / recovery、DAG pruning、observability、operator tuning、network backpressure、client retry 和 mempool integration。Chitu 的证明聚焦 consensus core；真实部署还需要回答：节点落后很久后如何 catch up，weak edges 会不会让 DAG retention 变贵，adaptive wait 的日志和告警如何解释，恶意 pre-accepted vertex 如何限流。

另一个工程风险是 fairness。Chitu 的 fast path 倾向提交被多数下一轮 vertex observe 的 proposal；慢 region 或慢 proposer 会更多依赖 weak edges 间接提交。安全性没有问题，但 inclusion latency 可能系统性偏向低 RTT / 高带宽节点。对 permissionless blockchain 来说，这可能影响 MEV、公平排序或 validator 激励。

## 局限与 Future Work

- **局限 1：fast-path 命中率随 n 增长快速下降**。Future work：实现 proposer subset + validator set 版本，测量不同 committee size 下 p、p^n、latency、fairness 和 Byzantine disable 成本。
- **局限 2：adaptive wait 的 adversarial cost 尚未被充分界定**。Future work：给 wait 引入可验证的 cost budget / rate limit，评估 payload size、bandwidth cap、签名验证和 malicious pre-acceptance 对 round advancement 的影响。
- **局限 3：通信复杂度高**。Future work：用 gossip、threshold aggregation 或 uncertified DAG 降低 O(n^3) message / O(n^4) communication 开销，同时保持 fast path 与 fallback 的一致性 invariant。
- **局限 4：实验 workload 不是真实 production trace**。Future work：在公开 blockchain trace 或真实 validator latency trace 上重放，报告 fast-path disable rate、inclusion latency distribution、tail latency 和单位成本吞吐。
- **局限 5：系统运维面缺失**。Future work：补齐 DAG pruning、checkpointing、catch-up、membership change、metrics 和 failure diagnosis，并验证这些机制不会破坏 Fair-Fallback 的证明前提。

## 相关

- **相关概念**：[[Byzantine-Fault-Tolerance]]、[[Consensus]]、[[DAG-BFT]]、[[Reliable-Broadcast]]、[[Random-Coin]]、[[Threshold-Signature]]、[[State-Machine-Replication]]、[[Blockchain]]
- **同类系统**：[[Tusk]]、[[DAG-Rider]]、[[BullShark]]、[[HotStuff]]、[[PBFT]]、[[Red-Belly|Red Belly]]、[[MyTumbler]]、[[Narwhal]]
- **同会议**：[[ATC-2025]]
