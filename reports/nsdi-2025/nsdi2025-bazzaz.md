# Preventing Network Bottlenecks: Accelerating Datacenter Services with Hotspot-Aware Placement for Compute and Storage

**作者**：Hamid Hajabdolali Bazzaz, Yingjie Bi, Weiwu Pang (Google); Minlan Yu (Harvard University); Ramesh Govindan (University of Southern California); Neal Cardwell, Nandita Dukkipati, Meng-Jung Tsai, Chris DeForeest, Yuxue Jin (Google); Charlie Carver (Columbia University); Jan Kopański, Liqun Cheng, Amin Vahdat (Google)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/bazzaz
**源文件**：[nsdi2025-bazzaz.pdf](../../papers/nsdi-2025/nsdi2025-bazzaz.pdf)

---

## 一、背景

数据中心网络中，ToR（Top-of-Rack）交换机上行链路的持续高利用率会形成"热点"（hotspot），导致应用延迟显著增加。Google 的数据中心承载了大规模的分布式存储（Colossus 文件系统、RamStore、Bigtable）和查询处理系统（QuerySys），这些服务的性能对网络延迟高度敏感。随着数据中心的异构升级（存储容量和网络带宽不同步扩容），网络供需失衡问题日益突出。传统的拥塞控制、流量工程和负载均衡等网络内机制只能在已有带宽内优化流量分布，无法从根本上解决 ToR 链路带宽不足的问题。

---

## 二、要解决的问题

1. **ToR 热点的普遍性与持久性**：Google 数据中心中，ToR 热点主要发生在 ToR 上行链路（而非 fabric 层），且可持续数小时甚至数天，影响大量应用。
2. **网络供需失衡**：数据中心基础设施分层异构升级，导致同一机架内存储容量与 ToR 上行带宽不匹配——存储扩容后网络带宽未同步升级（Low-Uplink 机架），成为热点的主要来源。
3. **传统方案失效**：拥塞控制和负载均衡只能在现有带宽内重新分配流量，无法增加可用带宽；流量工程受限于所有上行链路均已饱和的情况。
4. **调度器忽略网络**：现有的集群调度器（如 Borg）在任务放置时不考虑网络利用率，存储系统在 chunk 放置时也不考虑 ToR 带宽容量，导致工作负载集中在带宽不足的机架上。

---

## 三、洞察与设计

**关键洞察**：ToR 热点的根源不是网络层面的流量分配问题，而是计算/存储资源放置与网络带宽供给之间的结构性失衡。由于数据中心基础设施异构升级，某些机架的存储容量远超其 ToR 上行带宽的承载能力。因此，只有在资源放置层面（调度器和文件系统）引入网络感知，才能从根本上解决热点问题。

基于这一洞察，论文设计了两个互补的热点感知放置策略：

### UTP（Utilization-aware Task Placement）

在 Borg 调度器中引入 ToR 利用率感知：
- **主动放置**：为每个候选服务器计算一个 ToR 利用率评分，在不影响其他调度目标的前提下，偏好 ToR 利用率较低的服务器。利用 Borg 已有的多目标评分框架，将 ToR 利用率作为低优先级的负载均衡维度。
- **被动迁移**：当 ToR 利用率超过 75% 阈值时，贪心选择该机架上延迟容忍且网络带宽消耗最大的任务进行迁移，同时尊重可用性 SLO。
- 设计原则：最小化对 Borg 的改动，不将网络作为一等资源类型，仅调整已有的负载均衡目标。

### CCP（Capacity-aware Chunk Placement）

在 Colossus 文件系统中引入 ToR 容量感知：
- 将机架按 ToR 上行带宽与存储容量的比值分为 High-Uplink、Medium-Uplink、Low-Uplink 三类。
- 新 chunk 放置时优先选择 High-Uplink 机架，避免向带宽不足的机架写入更多数据。
- 使用静态的 ToR 上行容量信息（而非实时网络数据），实现简单可靠。

---

## 四、实现细节

### 测量基础设施

- 每 30 秒采集每个 ToR 的上行/下行利用率，使用加权有效利用率（weighted-effective utilization）考虑不同 QoS 等级的流量影响。
- 定义关键指标：**Hotspot-inflation**（75% 利用率阈值下的延迟膨胀倍数）、**Load-tolerance**（延迟翻倍时对应的最大 ToR 利用率）。
- 通过 Dapper 追踪系统关联单个操作的延迟与其涉及的 ToR 利用率。

### UTP 实现

- 修改 Borg 的服务器评分函数，加入 ToR 利用率维度，综合考虑瞬时 ToR 利用率和峰值任务需求。
- 在 Borg 已有的随机候选集采样框架内工作——由于平均 ToR 利用率低，随机样本中大概率存在低利用率服务器。
- 迁移决策：75% 阈值触发 → 贪心选择最大带宽消耗的延迟容忍任务 → 检查可用性预算。

### CCP 实现

- 对 Colossus 的 chunk 放置启发式进行最小修改，增加 ToR 容量类别作为放置偏好。
- 依赖静态配置信息（机架的 ToR 上行容量 vs 存储容量），无需实时网络遥测。

---

## 五、实验结果

论文基于 Google 生产环境进行了全量部署和评估：

### UTP 效果

| 指标 | 变化 |
|------|------|
| 热点 ToR 数量 | **减少 90%**（全集群部署后） |
| 热点 ToR 占比 | -44.6%（中位数） |
| p98 ToR 利用率 | -18.5% |
| 服务事故（网络热点相关） | **减少 70%**（月度） |
| 任务迁移次数（对比纯被动方案） | 减少约 50%（主动+被动 vs 纯被动） |
| 网络密集型任务调度到热点 ToR 的概率 | 纯被动方案高 7× |

### QuerySys 延迟改善

| 基准测试 | p95 延迟改善 |
|----------|-------------|
| Shuffle Flush | 最高约 13% |
| Materialize | 显著改善 |
| TPC-H | 不显著（该工作负载对 ToR 利用率不敏感） |

### CCP 效果（15 天试点）

| 指标 | 变化 |
|------|------|
| p95 网络延迟 | **减少 50–80%** |
| p95 总存储访问延迟 | **减少 30–60%** |

### 存储操作对 ToR 利用率的敏感度

| 操作类型 | 2× Load-tolerance | Hotspot-inflation |
|----------|-------------------|-------------------|
| HDD Read | 95% | 1.5× |
| HDD Write | 50% | ~4× |
| SSD Read | 55% | 2.5× |
| RamStore Read | 30% | 3× |

---

## 六、批判性分析

1. **实验规模与可复现性**：所有实验在 Google 生产环境中进行，外部研究者无法复现。论文未提供具体的集群规模、机架数量、工作负载特征等关键参数，难以判断结论的泛化性。

2. **CCP 评估不够充分**：CCP 仅在单个集群进行了 15 天试点，而 UTP 则进行了全集群部署。考虑到 CCP 改变了数据的物理分布且影响长期持久，其评估应更加充分——特别是对存储可靠性、数据均衡性、以及长期运行后的碎片化影响缺乏讨论。

3. **"90% 减少热点"的解读**：论文报告 UTP 减少了 90% 的热点 ToR，但 Table 2 显示热点 ToR 占比仅减少 44.6%（中位数）。这两个数字的差异暗示基线中热点 ToR 的绝对数量可能就很少，90% 的相对减少可能被放大表述。

4. **缺少对负面影响的深入分析**：论文声称 UTP 不影响任何现有 Borg 目标，但仅以"corresponding graphs are omitted for brevity"一笔带过。对于如此大规模的调度策略变更，bin packing 效率、资源碎片化、调度延迟等指标应当详细报告。

5. **75% 阈值的选择缺乏理论支撑**：热点阈值 75% 是基于经验和运维需求（25% 预留给升级扩容）设定的，而非基于排队论或工作负载特征的系统分析。论文未讨论不同阈值对性能的敏感度。

6. **因果关系论证偏弱**：论文用 before/after 部署对比来展示效果，但数据中心环境变量众多（工作负载变化、其他基础设施升级等）。Figure 16 就明确提到 UTP 部署后平均利用率因"unrelated workload change"而上升，这说明时间序列对比中存在混杂因素。

---

## 七、AI Infra / MLSys 视角

1. **ML 训练集群的网络热点问题**：论文在 Future Directions 中明确指出 ML 工作负载（同步通信、单点故障敏感）需要专门的网络故障容忍策略。当前大规模 LLM 训练中，all-reduce/all-to-all 等集合通信高度依赖网络带宽均匀性，ToR 热点会导致严重的 straggler 问题。UTP 的思路（在调度层面感知网络拓扑和利用率）可以直接迁移到 ML 训练任务的放置策略中。

2. **推理集群的启发**：LLM 推理服务（如 vLLM）中，prefill 和 decode 阶段的网络需求差异巨大。类似 UTP 的 ToR 感知放置可以帮助分离网络密集型（prefill、KV cache 传输）和计算密集型（decode）任务，避免相互干扰。

3. **Checkpoint 与模型加载**：大模型的 checkpoint 写入和模型加载是典型的存储密集型操作，CCP 的思路（感知 ToR 容量进行数据放置）对 checkpoint 存储策略有直接借鉴价值。

4. **可操作的研究方向**：
   - 将 UTP/CCP 的思路扩展到 GPU 集群调度器（如 Kubernetes + GPU operator），在 Pod 调度时考虑 ToR/Spine 利用率
   - 研究 ML 集合通信模式下的最优任务拓扑放置，结合网络利用率实时信息
   - 探索 disaggregated inference 架构中，prefill/decode 节点的网络感知放置策略

---

## 八、总结

本文通过对 Google 数据中心网络热点的系统性测量，揭示了 ToR 热点的根本原因是计算/存储资源放置与网络带宽供给之间的结构性失衡，而非网络层面的流量调度问题。基于这一洞察，论文提出了两个轻量级的热点感知放置策略（UTP 用于任务调度、CCP 用于存储 chunk 放置），以最小的系统改动实现了显著效果：减少 90% 的热点 ToR、降低 70% 的相关服务事故、以及 30-80% 的存储延迟优化。论文的核心价值在于证明了"在调度层引入简单的网络感知即可获得巨大收益"这一实用洞察，但其结论的泛化性受限于 Google 特有的基础设施规模和工作负载特征。
