# Maat: Analyzing and Optimizing Overcharge on Blockchain Storage

**作者**：Zheyuan He, Zihao Li, Ao Qiao, Jingwei Li, Feng Luo, Sen Yang, Gelei Deng, Shuwei Song, XiaoSong Zhang, Ting Chen, Xiapu Luo（电子科技大学、香港理工大学、南洋理工大学）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/he
**源文件**：[fast2025-he.pdf](../../papers/fast-2025/fast2025-he.pdf)

---

## 一、背景

区块链（如 Ethereum）采用交易费机制（Transaction Fee Mechanism, TFM）来分配链上资源（存储、网络、计算）的成本，核心计量单位是 gas。每条交易的总费用 = gas 消耗量 × gas 价格。TFM 的设计初衷是防止 DoS 攻击，同时公平反映资源消耗。

Ethereum 用户在 2023 年共支付了约 24 亿美元的交易费。Ethereum 联合创始人 Vitalik 曾公开表示，高额手续费是阻碍平台广泛应用的最大障碍。已有三种降低交易费的方案：EIP-4844（引入 blob 临时存储）、SuperStack（优化合约字节码）和 EIP-2929（根据实际存储访问模式调整 gas 定价）。

Ethereum 的世界状态通过 Merkle Patricia Trie（MPT）管理所有账户状态，并通过多层缓存机制（CoW cache、SSAS cache、MPT cache、bytecode cache）加速状态的读取和修改。存储操作分为 Read states、Update states 和 Persist states 三类。

---

## 二、要解决的问题

论文发现 Ethereum 的 gas 定价与实际存储工作负载之间存在严重不一致，导致用户被过度收费（overcharge）。具体存在三类问题：

1. **Issue \#1：同一 block 内重复访问同一对象**。当一个对象在同一 block 的多笔交易中被多次访问时，后续访问实际命中 CoW cache（内存操作），但仍按磁盘费（disk fee, 2600 gas）收费，而非内存费（memory fee, 100 gas）。

2. **Issue \#2：跨 block 但在 SSAS cache 范围内重复访问同一对象**。SSAS cache 缓存了最近 128 个 block 访问过的对象，但 Ethereum 对这些已缓存对象仍按磁盘费收费。

3. **Issue \#3：部署重复合约的冗余磁盘费**。当部署的合约字节码与已有合约相同时，只需引用现有字节码副本即可，但 Ethereum 仍收取完整的磁盘写入费用。

实际影响巨大：在 Ethereum 上约 70.4% 的交易（1.17 亿笔）受到过度收费影响，涉及总交易费的 42.0%（约 1.47 亿美元）。在 BSC 上影响更大，92.8% 的交易受影响。

---

## 三、洞察与设计

**关键洞察**：Ethereum 的 gas 定价是基于 opcode 级别的粗粒度计费，没有区分同一 opcode 对应的不同存储操作（内存 vs 磁盘）。而实际上，由于多层缓存机制的存在，大量被收取磁盘费的操作实际只触发了内存访问。通过在存储操作（storage operation）级别而非 opcode 级别进行细粒度的 gas 计量，可以让收费与实际资源消耗对齐。

基于此洞察，Maat 的架构包含三个组件：

- **Collector**：细粒度数据采集模块，在存储操作级别（而非 opcode 级别）捕获 gas 费用和高层语义（account loads/stores、slot loads/stores、bytecode loads/stores）。将每个 opcode 的 gas 分解为四个维度：memory loading/storing 和 disk loading/storing。

- **Optimizer**：部署四条优化规则（O1-O4）：
  - **O1**：同一 block 内对同一对象的重复读取，从 disk fee 降为 memory fee
  - **O2**：同一 block 内对同一对象的重复写入，从 disk fee 降为 memory fee
  - **O3**：跨 block 但在 128 block 内对同一对象的重复读取，降为 memory fee
  - **O4**：部署重复合约时，将费用从完整磁盘写入费降为一次磁盘查询费（gdiskload = 2600 gas）

- **Resource Pre-allocation**：为保证所有节点的存储操作行为一致，预分配 230 MiB 内存（128 blocks × 每 block 最大 1.80 MiB）作为缓存，确保优化规则在异构节点和不同客户端实现上一致生效。

---

## 四、实现细节

Maat 基于 go-ethereum v1.12.2 实现，代码量 2,717 行，采用多线程设计：

- **Collector()**：通过 hook go-ethereum 中对应的存储组件函数来收集高层语义操作及其费用。例如 hook `snapshot` 包的 `Account()` 和 `Storage()` 获取 SSAS cache 访问信息，hook `vm` 包的 `gasCall()` 获取 Call 操作的费用信息。

- **Handler()**：通过 Go channel 将 Collector 收集的信息传递给 Optimizer。

- **Optimizer()**：对每个存储操作的高层语义，搜索对应的缓存（O1-O3）或状态存储（O4），命中则按规则调整 gas 费用。

- **WAL 机制**：为应对客户端异常终止导致缓存数据丢失的问题，Maat 对预分配缓存实现了 Write-Ahead Log。

关键 gas 定价参照 EIP-2929 规范：memory fee 为 100 gas，O4 的磁盘查询费为 2600 gas。

---

## 五、实验结果

**实验平台**：Intel Xeon Gold 5218R CPU（2.1 GHz, 12 cores）, 64 GB RAM, 4 TB SSD。

### Ethereum 优化效果（block \#18M - \#19M, 约 1M blocks）

| 指标 | Maat | EIP-2929 Baseline |
|------|------|-------------------|
| 总优化 gas | 2.01 × 10¹² | 0.67 × 10¹² |
| 总优化费用 (USD) | 1.12 亿 | 0.39 亿 |
| 每周平均节省 | 5.6M USD | ~1.9M USD |
| 优化率 | 32% | 11% |
| 每笔交易节省 | 12,730 gas / 0.71 USD | 4,247 gas / 0.25 USD |

### BSC 优化效果（block #34.15M - #35.15M, 约 1M blocks）

| 指标 | Maat | Baseline |
|------|------|----------|
| 总优化 gas | 4.56 × 10¹² | 1.66 × 10¹² |
| 总优化费用 (USD) | 771 万 | 274 万 |
| 优化率 | 31% | 11% |

### 各优化规则贡献

| 规则 | 优化 gas 占比 |
|------|--------------|
| O1（block 内重复读） | 13% |
| O3（跨 block 缓存读） | 11% |
| O2（block 内重复写） | 6% |
| O4（重复合约部署） | 3% |
| 全部组合 | 33% |

### 性能开销

| 指标 | 数值 |
|------|------|
| 时间开销 | 平均 1.4%（~1.3 ms/block） |
| 内存开销 | 平均 5.6%（~0.29 GiB） |

Maat 已成功移植到 50 条流行区块链，均无需额外代码适配。

---

## 六、批判性分析

1. **优化规则依赖于特定缓存实现假设**。O1-O3 的前提是所有节点都维护相同的缓存行为。虽然论文通过 resource pre-allocation 技术缓解了这个问题，但这本质上是要求所有节点统一预分配 230 MiB 内存。对于资源受限的轻节点或嵌入式环境，这一假设是否合理没有讨论。

2. **O4 的 tradeoff 分析不够严谨**。论文声称 93% 的合约是重复的，因此 O4 对大多数用户有利。但这个统计是在特定 1M block 范围内的，缺乏长期趋势验证。随着 DeFi 生态的发展，如果新合约部署比例上升，O4 带来的额外 gdiskload 收费可能影响更多用户。

3. **评估时间窗口有限且单一**。Ethereum 仅评估了 2023.8-2024.1 约 4 个月的数据。交易模式具有周期性和趋势性变化（如牛熊市、热门项目上线），仅用一段时期的数据无法验证优化效果的鲁棒性。

4. **对矿工/验证者收入影响的论证偏弱**。论文以"EIP-1559 也减少了 33% 收入但区块链继续繁荣"来论证安全性，但 EIP-1559 的通过经历了极大的社区争议，且两者的经济机制不同。简单类比不足以说明 Maat 的可行性。

5. **未考虑 OS 级缓存等非区块链存储组件**。论文明确承认了这一局限，但对于追求公平定价的系统来说，忽略 OS page cache 意味着仍有一部分"磁盘费"实际是由 OS 缓存服务的。

6. **安全性证明过于形式化而缺乏实际攻击分析**。论文证明了优化规则在共识层面的一致性，但未分析是否存在利用降低后的 gas 费进行新型攻击的可能（如利用 O3 的 128 block 窗口构造恶意访问模式来降低攻击成本）。

---

## 七、总结

Maat 是一个针对区块链存储过度收费问题的优化工具。通过识别三类 gas 定价与实际存储工作负载之间的不一致（block 内重复访问、跨 block 缓存命中、重复合约部署），并在存储操作级别进行细粒度 gas 调整，Maat 在 Ethereum 上实现了 32% 的交易费优化（每周节省约 560 万美元），性能开销仅 1.4%，并成功扩展到 50 条 EVM 兼容链。其主要局限在于优化规则依赖特定缓存假设、评估窗口有限，且未充分分析降低 gas 费后可能引发的新安全风险。该工作已促成 Ethereum 社区提出 EIP-7863 提案。
