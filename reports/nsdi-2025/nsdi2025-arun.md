# Shoal++: High Throughput DAG BFT Can Be Fast and Robust!

**作者**：Balaji Arun (Aptos Labs), Zekun Li (Aptos Labs), Florian Suri-Payer (Cornell University), Sourav Das (UIUC), Alexander Spiegelman (Aptos Labs)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/arun
**源文件**：[[nsdi2025-arun.pdf]]

---

## 一、背景

Byzantine Fault Tolerant (BFT) 共识协议是区块链系统、数字欧元等多国数据主权项目以及机密数据共享框架的核心。当前实用的 partially synchronous BFT 协议面临一个基本的延迟-吞吐量权衡：

- **传统 BFT 协议**（如 PBFT、Jolteon）：通过单一 leader 实现低延迟（3 message delays），但吞吐量受限于单个节点的带宽和计算能力。
- **DAG-BFT 协议**（如 Bullshark、Shoal）：通过将数据分发与共识分离，让每个 replica 都充当 proposer，实现高吞吐量和可扩展性，但延迟显著更高（Bullshark 期望 12 md，Shoal 期望 10.5 md）。

随着区块链系统（Aptos、Sui 等）在生产环境中大规模部署，同时需要高吞吐量和低延迟的需求日益迫切。

---

## 二、要解决的问题

现有 DAG-BFT 协议的端到端延迟过高，主要来源于三个阶段：

1. **Queuing Latency（排队延迟）**：DAG 按轮次推进，每轮需要 3 md 完成 Reliable Broadcast。刚错过当前轮次的交易需等待下一轮，平均排队延迟 1.5 md。
2. **Anchoring Latency（锚定延迟）**：非 anchor 节点必须等到被某个已提交的 anchor 引用才能被排序。Bullshark 每隔一轮才设置 anchor 候选，平均锚定延迟 4.5 md；Shoal 改进到每轮一个 anchor，降至 3 md。
3. **Anchor Commit Latency（anchor 提交延迟）**：anchor 至少需要 2 轮 DAG（6 md）才能被 Direct Commit Rule 确认——1 轮认证 anchor 本身，1 轮收集 f+1 个认证引用。

此外，concurrent 的 uncertified DAG 方案（如 Mysticeti）虽声称能降低延迟，但去除证书后 DAG 变得脆弱，偶发消息丢失即可导致关键路径上的数据同步，延迟剧增（实验中 1% 丢包可导致 10x 延迟恶化）。

---

## 三、洞察与设计

**关键洞察**：DAG-BFT 的高延迟并非源于 certified DAG 本身，而是源于过于保守的 commit rule 和稀疏的 anchor 调度。通过在不牺牲 certification（即不降低鲁棒性）的前提下，分别优化延迟的三个组成部分，可以大幅缩小 DAG-BFT 与传统 BFT 之间的延迟差距。

Shoal++ 针对三个延迟阶段分别提出优化方案：

### 1. Fast Direct Commit Rule（降低 Anchor Commit Latency：6 md → 4 md）

观察到：如果 2f+1 个（未认证的）提案已经引用了某个 anchor，即使它们尚未完成认证，anchor 的命运实际上已经确定——其中至少 f+1 个来自正确 replica，最终必然形成证书。因此 Shoal++ 允许 replica 在观察到 2f+1 个 weak votes（未认证提案引用）后即可提交 anchor，将 commit 延迟降至 4 md（3 md 认证 anchor + 1 md 接收提案）。同时保留原始 f+1 certified Direct Commit Rule 作为 fallback。

### 2. More Anchors per Round（消除 Anchoring Latency）

Shoal++ 尝试将尽可能多的节点设为 anchor。每轮所有节点都可作为 anchor 候选，按预定义顺序串行提交。为解决"慢 anchor 阻塞后续 anchor"的问题，引入两个机制：
- **Round Timeouts**：每轮在观察到 2f+1 节点后额外等待一小段时间，鼓励 replica 同步推进，形成更密集连接的 DAG。
- **Dynamic Anchor Skipping**：动态跳过明显不再需要的 anchor 候选。当某个 anchor 的共识实例确认了一个更高轮次的 anchor 时，中间的 virtual anchor 候选被跳过。

### 3. Multiple Parallel DAGs（降低 Queuing Latency：1.5 md → 0.5 md）

运行 k=3 个交错的 DAG 实例，每个 DAG 偏移 1 md。由于单个 DAG 每轮需要 3 md，3 个 DAG 确保每 1 md 就有某个 DAG 的新轮次可用。各 DAG 独立运行，输出通过 round-robin 交织成统一的全序日志。

---

## 四、实现细节

- **实现语言与框架**：基于 Aptos 开源代码库用 Rust 实现，使用 Tokio 异步运行时、BLS12-381 签名、RocksDB 持久化存储、Noise 认证协议。
- **Weak Votes 追踪**：每个 replica 维护 `weak_votes[round][source]` 二维计数器，收到未认证提案时递增对应 parent 的计数，达到 2f+1 即可触发 Fast Commit。
- **DAG 内联数据流**：放弃 Narwhal 的 worker 层，将交易数据直接嵌入 DAG 提案中。虽然理论上牺牲了 worker 层的水平扩展能力，但避免了数据哈希引用导致的额外 2 md 数据拉取延迟。3 个并行 DAG 的小批量高频提交近似实现了流式数据分发效果。
- **Distance-based Priority Broadcast**：周期性测量 replica 间点对点延迟，调整广播顺序，优先发送给距离远的 replica，使消息到达更均匀。
- **Reputation 机制**：继承 Shoal 的 leader reputation，根据历史表现选择 anchor 候选，动态排除慢节点。
- **多 DAG 交织**：3 个 DAG 实例各自独立运行，输出日志段（log segment）通过 round-robin 依次追加到全局日志。如果某个 DAG 提交更快，其多余的 segment 需等待其他 DAG 追上。

---

## 五、实验结果

**实验平台**：Google Cloud Platform，100 个 replica 分布在全球 10 个区域，n2d-standard-64 VM（64 vCPU, 256 GB 内存），区域间 RTT 25ms–317ms。交易大小 310 字节，batch size 500。

### 无故障场景（100 replicas）

| 协议 | 低负载延迟 | 50k tps 延迟 | 最大吞吐量 |
|------|-----------|-------------|-----------|
| Shoal++ | 775 ms | ~900 ms | ~140k tps |
| Shoal | 1.45 s | 1.7 s | ~75k tps |
| Bullshark | 1.9 s | 2.4 s | ~75k tps |
| Mysticeti | ~775 ms | 高负载显著恶化 | ~140k tps |
| Jolteon | 900 ms | N/A | ~2.1k tps |

- Shoal++ 是唯一在 100k tps 下仍保持亚秒延迟的系统。
- 并行 DAG 技术同样适用于 Bullshark/Shoal，使其吞吐量匹配 Shoal++。

### 延迟分解

- Fast Commit Rule：理论改进 2 md，实际因网络不对称略小。
- More Anchors：贡献最大，平均节省 3 md 锚定延迟。
- Parallel DAGs：进一步降低排队延迟并显著提升吞吐量。

### 故障场景

- **33/100 crash**：Shoal++ 延迟约增至 2x（需跨更多区域凑齐 quorum），但 reputation 机制快速适应。Bullshark 和 Mysticeti 因无 reputation 机制延迟剧增。
- **1% 消息丢包（5 个节点）**：Shoal++ 延迟仅增至 1.3x；Mysticeti 延迟飙升 10x（uncertified DAG 需关键路径上数据同步）。

---

## 六、批判性分析

1. **延迟指标的公平性**：论文报告的是 50th percentile（中位数）延迟，25/75 分位数作为 error bar。对共识系统而言，尾延迟（p99/p999）往往更关键，但论文未报告。特别是 More Anchors 技术中的 dynamic skipping 和 round timeout 可能导致尾延迟恶化，论文对此缺乏分析。

2. **Round Timeout 的调参敏感性**：论文使用 600 ms 的 round timeout，声称"在实践中相对于 3 md 认证延迟可忽略"。但这个参数高度依赖网络拓扑，论文未提供敏感性分析。在更大规模或更不稳定的网络中，timeout 的选取可能成为性能瓶颈。

3. **Mysticeti 比较的公平性问题**：Shoal++ 和 Bullshark/Shoal/Jolteon 共用同一代码库（Aptos），而 Mysticeti 使用独立代码库（且不使用持久化存储）。尽管论文承认了这一点，但存储层差异可能显著影响延迟和吞吐量的对比结果。

4. **并行 DAG 的资源开销被淡化**：论文承认 Shoal++ 消耗更多 CPU、内存和磁盘资源，但未给出量化数据。在资源受限的生产环境中，3 倍的 DAG 实例带来的开销可能非常可观。

5. **Anchor Skipping 的连锁效应**：当 anchor 被 skip 时，其 causal history 中的交易排序被延迟到未来 anchor 提交时。论文未分析在高 skip rate 场景下，交易确认延迟的方差和最坏情况表现。

6. **实验规模的局限性**：100 个 replica 的评估与实际大型区块链部署（数千节点）仍有差距。Distance-based Priority Broadcast 等优化在更大规模下的表现存疑。

---

## 七、总结

Shoal++ 通过三个互补的优化（Fast Direct Commit Rule、多 anchor 调度、并行 DAG 实例），将 certified DAG-BFT 的期望端到端延迟从 10.5 md（Shoal）降至 4.5 md，接近传统 BFT 的 3 md 理论最优，同时保持了 DAG-BFT 的高吞吐量和鲁棒性。实验表明 Shoal++ 在 100 节点全球部署中实现亚秒延迟和 140k tps，且在故障场景下表现远优于 uncertified DAG 方案。其主要局限在于额外的资源开销、round timeout 调参敏感性，以及尾延迟分析的缺失。并行 DAG 技术作为一个通用框架，可独立应用于任意 BFT 协议以降低排队延迟，具有较好的可推广性。
