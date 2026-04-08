# Cache-Centric Multi-Resource Allocation for Storage Services

**作者**：Chenhao Ye, Shawn (Wanxiang) Zhong, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau, University of Wisconsin–Madison
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/ye
**源文件**：[[fast2026-ye.pdf]]

---

## 一、背景

现代存储系统广泛使用缓存来提升性能和降低成本。Facebook 报告 70% 的 Web 请求由 CDN 缓存服务，AWS 应用普遍在后端数据库前部署 ElastiCache。随着存储系统从传统本地基础设施迁移到云环境，共享的资源类型不断扩展——不仅包括硬件资源（网络、I/O 带宽），还包括软件基础服务资源（如 DynamoDB 的 read units 和 write units）。

在多租户存储系统中，如何在多个租户之间公平且高效地分配多种资源（包括缓存）是一个重要的挑战。现有的多资源分配框架——以 Dominant Resource Fairness (DRF) 为代表——假设资源需求是相互独立的，无法处理缓存这一特殊资源类型。

---

## 二、要解决的问题

1. **缓存的非线性性能特征**：与 I/O、网络等传统资源不同，缓存大小与吞吐量之间不存在线性关系（2× cache ≠ 2× throughput），miss ratio 与缓存大小呈复杂的非线性关系，因此 DRF 的 demand vector 模型无法直接适用。

2. **缓存与其他资源的需求关联（Demand Correlation）**：分配更多缓存会降低 miss ratio，从而减少对下游资源（I/O、网络、DB read units）的需求。这种关联性在 DRF 中被完全忽略，因为 DRF 假设各资源需求相互独立。

3. **现有缓存分配框架缺乏多资源感知**：大多数缓存分区框架（如 Memshare、FairRide）只优化 miss ratio，不考虑缓存与其他资源之间的交互，导致分配次优。CoPart 虽然考虑了缓存关联，但仅限于 CPU last-level cache 和 memory bandwidth 的单一关联场景。

4. **公平性与效率的矛盾**：Equal partition 保证公平但效率低；DRF 改善了效率但排除了缓存；Non-partitioned cache 可能提升全局效率但无法保证 sharing incentive（即租户共享系统不应比独占 1/x 资源更差）。

---

## 三、洞察与设计

**关键洞察**：不同租户对缓存的敏感度（cache sensitivity）存在异质性——有的租户从更多缓存中受益巨大（miss ratio 显著下降），有的则几乎不受影响。利用这种异质性，可以将缓存从不敏感的租户转移到敏感的租户，使敏感租户因 miss ratio 下降而释放其他资源（I/O、网络），这些"收割"的资源再重新分配给所有租户，实现整体吞吐量提升而不损害公平性。

基于此洞察，论文提出 **HARE (Harvest-Redistribute)** 算法，一个以缓存为中心的多资源分配算法：

### Harvest 阶段
- 迭代式地在租户之间进行 cache-resource trading：从缓存不敏感的租户取走缓存，给予其他资源作为补偿以维持相同吞吐量；将多余缓存给缓存敏感的租户，该租户因 miss ratio 下降而释放其他资源
- 关键：释放的资源 > 补偿的资源，差值即为"收割"的资源
- 多资源场景下，优先收割系统级瓶颈资源（dominant resource），即 harvest 中相对最稀缺的那个

### Redistribute 阶段
- 将收割的资源按各租户现有份额的比例加权分配，使所有租户吞吐量等比例提升

### 通用关联模型
- 引入 cache-saving constant α_i 描述缓存命中对不同资源的节省程度（α=1 表示命中完全跳过该资源，α=0 表示缓存无影响）
- 支持多种 cache-correlated resource 和 cache-independent resource

---

## 四、实现细节

### HopperKV：云原生 KV 存储
- 基于 Redis 修改，缓存 DynamoDB 的数据，管理四种资源：Redis cache size、network bandwidth、DynamoDB read units、write units
- **架构**：每个租户一个独立 Redis 实例 + 自定义 Redis Module（C++ .so 插件）+ 全局 Allocator Daemon
- **Ghost Cache**：使用空间采样（spatial sampling, 1/32 采样率）的 ghost cache 在运行时高效构建 Miss Ratio Curve (MRC)，CPU 开销 <25ns/key，精度误差 <1%
- **动态适应**：每 20 秒运行一次 HARE，基于滑动窗口（过去 1 分钟）统计；新分配仅在预测优势 >5% 时应用，避免振荡
- **平滑迁移**：缓存配额以 16MB 为单位逐块迁移，待上一块预热后再迁移下一块
- **MRC 加盐**：给 MRC 添加 1% 小常量，防止极低 miss ratio 时的估计误差导致资源分配为零
- 代码量：4K 行 C++，开源

### BunnyFS：高性能本地文件系统
- 基于半微内核 uFS 架构，管理 NVMe SSD
- 管理三种资源：page cache、I/O bandwidth、worker threads CPU cycles
- 使用 SPDK 进行高性能块 I/O
- 同样使用 ghost cache + HARE 算法，分配频率为每 1-2 秒
- 代码量：在 uFS 基础上增加/修改 4K 行 C++，开源

### HARE 算法复杂度
- 每次 trading iteration O(n)，总复杂度 O(n × trading_iterations)
- 实际运行时间在微秒级，分配频率在秒级，开销可忽略

---

## 五、实验结果

### HopperKV 实验

| 实验 | 对比基线 | HARE 提升 | 关键发现 |
|------|---------|----------|---------|
| 微基准（变 working set） | Equal Partition | 最高 63% | 两租户 dominant resource 相同时 DRF 无提升，HARE 仍有效 |
| 微基准（变 hotness） | Equal Partition | 最高 38% | Memshare 牺牲公平性，HARE 兼顾效率和公平 |
| 扩展性（16 租户 YCSB） | Equal Partition | 1.6×–2.7× | 13/16 租户在 HARE 下达到最佳；DRF 1.2×–1.9×；NonPart 6/16 租户性能下降 3× |
| 动态工作负载 | Equal Partition | 最高 1.9× | 平滑迁移机制保证工作负载变化时性能稳定 |
| Twitter 真实 trace | Equal Partition | ≥38%（排除饱和租户） | DRF 仅 16%，Memshare+DRF 使个别租户性能下降 4% |

### BunnyFS 实验

| 实验 | HARE vs Baseline | HARE vs DRF | 关键发现 |
|------|-----------------|-------------|---------|
| 扩展性（32 租户） | 最高 1.4× | DRF 仅 10% 提升 | NonPartCache+DRF 违反 sharing incentive |
| 动态工作负载 | 持续优于 DRF | DRF 前 35 秒无提升 | 所有租户同为 I/O-bound 时 DRF 无效，HARE 仍有效 |

### 尾延迟
- HARE 在 p999 尾延迟上与竞争方案持平或更优，得益于 MRC salting 技术吸收 miss 突发

---

## 六、批判性分析

1. **贪心算法的最优性缺失**：论文坦承 HARE 是贪心算法，可能不是最优解，但以"计算困难"为由轻描淡写。实际上论文没有量化 HARE 解与最优解的差距——在复杂的多租户多资源场景下，这个差距可能是显著的。

2. **实验规模偏小**：HopperKV 最大测试 16 租户、BunnyFS 32 租户。真实云存储系统往往服务成百上千租户，在该规模下 HARE 的 trading iteration 数量、收敛时间和稳定性均未得到验证。

3. **工作负载代表性问题**：微基准实验使用的是精心设计的两租户场景，能清晰展示 HARE 优势。但实际工作负载的多样性远超实验覆盖范围——例如论文没有测试 write-heavy 为主的混合负载、突发性极强的工作负载、或 MRC 形状高度不规则的场景。

4. **Ghost Cache 精度假设**：论文称采样率 1/32 精度误差 <1%，但这一结论依赖于特定的访问模式。对于高度不规则的访问分布（如多模态热度），ghost cache 的 MRC 估计可能偏差更大，而 HARE 的分配质量高度依赖 MRC 准确性。

5. **公平性定义的局限**：论文将公平性定义为 max-min normalized throughput，但未讨论 strategy-proofness。论文承认 HARE 不关注 strategy-proofness，这意味着租户可能通过伪造工作负载特征来获取更多资源——这在多租户云环境中是一个实际威胁。

6. **缺乏与 CoPart/Spirit 的直接对比**：论文在 Related Work 中提到 CoPart 和 Spirit 与 HARE 共享相似的 vision，但实验中未与这两者进行直接性能对比，仅进行了定性比较。

7. **单节点限制**：HopperKV 仅在单节点上演示，多节点扩展被留作 future work。但实际云 KV 存储都是分布式的，跨节点的缓存-资源关联和分配协调是一个完全不同量级的问题。

---

## 七、AI Infra / MLSys 视角

1. **GPU 显存作为"缓存"的类比**：HARE 的核心思想——利用缓存敏感度的异质性进行资源交易——可以直接迁移到 GPU 多租户推理场景。例如在 KV cache 管理中，不同请求的 KV cache 敏感度不同（长上下文 vs 短上下文），可以借鉴 HARE 的 harvest-redistribute 思路在请求间动态分配 GPU 显存和计算资源。

2. **多资源关联在训练系统中的应用**：分布式训练涉及 GPU compute、HBM、网络带宽、CPU、host memory 等多种资源，且存在类似的需求关联（如更大的 gradient accumulation 减少通信频率，类似于更大缓存减少 I/O）。HARE 的 cache-saving constant 概念可以推广为通用的 resource-saving model。

3. **MRC 构建技术的借鉴**：Ghost cache 的空间采样技术可用于在线学习 GPU kernel 的 cache 行为、prefetch buffer 的效用曲线等，以低开销获得资源效用信息。

4. **可操作的研究方向**：
   - 将 HARE 应用于 multi-tenant LLM serving 中的 KV cache + GPU compute + network 联合分配
   - 在 GPU 集群调度中引入缓存关联模型（如 checkpoint cache、model cache 与计算资源的交互）
   - 研究非贪心的多资源分配算法，探索近似最优解

---

## 八、总结

HARE 是首个将缓存作为核心组件纳入多资源分配框架的算法，通过 harvest-redistribute 两阶段方法利用租户间缓存敏感度的异质性，在不损害公平性的前提下提升整体吞吐量。论文通过 HopperKV（云 KV 存储，最高 1.9× 提升）和 BunnyFS（本地 NVMe 文件系统，最高 1.4× 提升）两个系统验证了 HARE 的通用性。主要局限在于贪心算法缺乏最优性保证、实验规模偏小、以及缺少 strategy-proofness 保证。
