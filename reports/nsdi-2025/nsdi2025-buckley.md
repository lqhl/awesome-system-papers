# Learnings from Deploying Network QoS Alignment to Application Priorities for Storage Services

**作者**：Matthew Buckley (Google & University of Toronto), Parsa Pazhooheshy (Google & University of Toronto), Z. Morley Mao, Nandita Dukkipati, Hamid Hajabdolali Bazzaz, Priyaranjan Jha, Yingjie Bi, Steve Middlekauff (Google), Yashar Ganjali (University of Toronto)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/buckley
**源文件**：[nsdi2025-buckley.pdf](../../papers/nsdi-2025/nsdi2025-buckley.pdf)

---

## 一、背景

在数据中心网络中，应用通过 RPC（Remote Procedure Call）进行通信，不同 RPC 对网络延迟的敏感度差异巨大。网络交换机使用 QoS（Quality of Service）位（通常是 IP 头中的 DSCP 字段）来区分流量优先级，为不同流量分配缓冲区和调度权重。理想情况下，应用层的优先级应与网络层的 QoS 配置精确对齐。

然而在实践中，Google 观察到严重的"race-to-the-top"现象：当应用遭遇网络拥塞和 SLO 违规时，开发者倾向于将流量提升到更高的 QoS 等级，认为更高 QoS 必然带来更低延迟。这种行为导致高优先级 QoS 队列过载，反而使所有流量的性能变得不可预测，形成 priority inversion（优先级反转）。

Google 此前提出了 Aequitas 系统来解决这一问题，本文聚焦于 Aequitas 在 Google 存储系统（覆盖约 75% 非 ML 相关 RPC 流量）中的大规模部署经验。

---

## 二、要解决的问题

1. **QoS 配置与应用优先级严重错位**：图 5 显示，在 Spanner 中，大量 BE（Best-Effort）RPC 使用 QoS_m 甚至 QoS_h，NC（Non-Critical）RPC 也大量使用 QoS_h，而 QoS_l 几乎无人使用。这种错位在多数集群中普遍存在。

2. **Priority inversion 导致性能不可预测**：高权重 QoS 队列因过载反而比低权重队列延迟更高，SLO 无法按队列权重合理设定。

3. **粒度不够细**：传统做法是在应用或 job 层面设定 QoS，但同一 job 内不同 RPC 的优先级差异巨大（图 3-4 显示大流量 job 通常使用多种优先级），需要 RPC 级别的 QoS 对齐。

4. **大规模部署的工程挑战**：不同存储系统有各自的优先级概念，客户端对 QoS 降级极其抗拒，无法一次性全量部署。

---

## 三、洞察与设计

**关键洞察**：在 Weighted Fair Queuing（WFQ）机制下，更高权重的 QoS 队列并不总是提供更好的服务。当 QoS_i（高权重）相对于 QoS_j（低权重）过载时，将部分流量从 QoS_i 迁移到 QoS_j 反而能获得更好的服务速率。这意味着 QoS 的价值不取决于队列权重本身，而取决于队列的负载与权重之比。

基于此洞察，Aequitas 的设计方案为：

- **RPC 级别的 QoS 对齐**：将 RPC 按应用语义分为 PC（Performance-Critical）、NC（Non-Critical）、BE（Best-Effort）三类，1:1 映射到 QoS_h、QoS_m、QoS_l 三个队列。
- **静态映射 + 元数据驱动**：利用各存储系统现有的 RPC 元数据（源/目标 IP、应用优先级、请求 QoS）进行分类，无需用户额外输入。
- **区分网络区域**：仅对 intra-cluster 流量生效，WAN 流量因涉及 BwE 带宽管理而暂不处理。
- **客户端/服务端实现的选择**：LL（Lower Level）存储使用服务端实现（对用户透明），UL（Upper Level）系统使用客户端实现（让用户可见 QoS 变更，便于调试）。

---

## 四、实现细节

- **QoS 对齐机制**：Aequitas 拦截 RPC，根据优先级选择正确的网络通道。对于 LL 存储的服务端实现，RPC 的前几个包使用原始 QoS，到达 LL 服务器后 Aequitas 选择新 QoS，后续包使用更新后的 QoS。
- **渐进式部署**：支持按客户端、按集群、按比例（如 50%）启用。通过随机采样对 RPC 进行 A/B 对比，控制混淆变量。
- **分析工具链**：主要使用 Dapper（分布式追踪系统）进行细粒度分析，导出自定义注解（RPC 优先级、请求 QoS、Aequitas 选择的 QoS）。使用 Monarch（时间序列数据库）进行高层级监控，验证 Dapper 采样分析的一致性。Dapper 分析限制为均匀采样的 trace，并按采样率的倒数加权。
- **unhealthy mix 检测**：定义了基于 QoS 权重比的"健康"阈值（如 QoS_h:QoS_m 权重比为 8:4，则 QoS_h:QoS_m 流量比超过 2:1 即为 unhealthy）。
- **异常处理机制**：支持特殊客户端绕过 Aequitas 映射规则。

---

## 五、实验结果

所有实验均在 Google 生产环境进行，采用 50% 随机采样对比 aligned（遵循 Aequitas）与 misaligned（不遵循）流量。延迟数值已标准化（除以 misaligned 流量 p99 标准差）以保密。

**发现 1：Priority（而非 RPC size）是正确的网络调度单位**

| 优先级 | p50 RNL 改善 (mean) | p99 RNL 改善 (max) | p99 总 RPC 延迟改善 (max) |
|--------|--------|--------|--------|
| BE | +0.02 (轻微退化) | +1.55 (轻微退化) | -1.82 (改善) |
| NC | +0.02 (轻微退化) | +1.75 (轻微退化) | -3.65 (改善) |
| PC | -0.17 (改善) | **-263.95 (大幅改善)** | **-2419.51 (大幅改善)** |

- PC RPC 的 p99 RNL 最大改善是 NC 最大退化的 **150 倍以上**
- PC 的总 RPC 延迟改善表明网络是这些 RPC 的瓶颈

**发现 2：更低的 QoS 不意味着更高的延迟**

在 QoS_m 严重过载（QoS_m:QoS_l = 10.69:1，阈值为 4:1）的集群中，BE 流量降级到 QoS_l 后：
- 平均 p99 RNL 降低 0.35 个标准差
- 最大 p99 RNL 降低 **18.51 个标准差**

**发现 3：All can win（非零和博弈）**

客户端 c̄ 全量部署后，NC RPC 的 RNL 降低 **31.04%**（尽管 NC 流量在部署前已对齐）。所有优先级的流量均受益。

**Query Service 部署结果**：

| 指标 | NC 变化 | PC 变化 |
|------|---------|---------|
| 平均 p99 RNL | +16.24% | **-3.77%** |
| 最大 p99 RNL | **-68.91%** | **-36.45%** |
| p99 RNL 标准差 | **-68.62%** | **-70.03%** |

- Aequitas 已部署至 LL 存储超过 3 年，Query Service 超过 2.5 年，效果持续稳定
- Spanner 当前约 72% RPC 已对齐，覆盖约 84% 响应字节和 78% 请求字节

---

## 六、批判性分析

1. **缺乏真正的 A/B 实验**：作者承认这不是真正的 A/B 实验，仅通过随机采样近似。但随机采样无法控制所有混淆变量——例如，当 aligned 和 misaligned 流量共享同一网络路径时，aligned 流量的 QoS 改善会间接影响 misaligned 流量的性能（因为减少了高优先级队列的负载），使得 misaligned 流量的基线并非"无 Aequitas"状态。这系统性地低估了 Aequitas 的效果，但也意味着论文报告的数字难以精确解读。

2. **标准化隐藏了绝对量级**：所有延迟数据都用标准差标准化，虽然保护了 Google 的保密性，但读者无法判断这些改善在绝对值上是否有业务意义。"263.95 个标准差"的改善是 μs 级还是 ms 级？对 SLO 的实际影响是什么？

3. **静态 3 级映射的局限性**：论文将所有流量简化为 BE/NC/PC 三级，1:1 映射到 QoS 队列。但实际应用的优先级分布可能更细粒度（如 5-10 级），强制压缩到 3 级会导致同一队列内的 priority inversion。论文未讨论这一限制。

4. **仅覆盖 intra-cluster 流量**：论文承认 WAN 场景更复杂（涉及 BwE 交互），但将其留作 future work。考虑到跨集群 RPC 的网络延迟远大于集群内延迟，这部分恰恰是 QoS 优化最有价值的场景。

5. **race-to-the-top 的根因未解决**：Aequitas 通过强制映射来纠正 QoS 配置，但 race-to-the-top 的根因是用户缺乏工具来理解 QoS 与延迟的关系。如果 Aequitas 的映射本身出错（如某些集群的负载模式不符合静态映射的假设），用户将无法自救。

6. **部署时间跨度过长**：论文描述的渐进式部署跨越多年，但未明确量化 Aequitas 全部署后 fleet-wide 的整体改善（仅展示了个别客户端和 Query Service 的结果）。对于一个影响"数百万 RPC/秒"的系统，缺少 fleet-wide 的综合评估是明显的不足。

---

## 七、AI Infra / MLSys 视角

1. **对 AI 推理系统的启发**：大规模 LLM serving 系统中同样存在请求优先级差异——交互式推理（如 ChatGPT 实时对话）需要低延迟，而批处理推理（如离线评估）可容忍更高延迟。Aequitas 的 RPC 级别 QoS 对齐思路可以迁移到 GPU 集群的网络调度中，为不同优先级的推理请求分配差异化的网络资源（尤其是在分布式推理中 tensor parallelism 通信和 KV cache 传输的场景）。

2. **分布式训练的通信优化**：在数据并行 + 流水线并行的混合训练中，不同通信模式（AllReduce 梯度聚合 vs. 流水线 stage 间的 activation 传递 vs. checkpoint 写入）的延迟敏感度差异显著。基于 Aequitas 的思路，可以对这些通信按优先级映射到不同 QoS 队列，避免大规模 checkpoint 写入挤占关键路径上的梯度通信带宽。

3. **"lower QoS ≠ higher latency"的启示**：这一发现对 AI 集群的网络资源分配策略有直接指导意义。当高优先级网络队列因集中的 AllReduce 流量过载时，将非关键通信（如日志、监控、预取）主动降级到低优先级队列反而能改善所有流量的性能。

4. **可操作的研究方向**：将 Aequitas 的静态优先级映射扩展为动态映射——根据 GPU 集群的实时负载和训练 job 的 critical path 分析，动态调整通信优先级。这在 MoE 模型的 expert parallelism 场景中尤其有价值，因为 expert 路由的动态性导致通信模式高度不可预测。

---

## 八、总结

本文详细记录了 Google 在 planet-scale 生产网络中部署 Aequitas（RPC 级别 QoS 对齐系统）的经验。核心贡献是三个经过生产验证的发现：（1）Priority 而非 RPC size 是正确的网络调度单位；（2）更低的 QoS 权重不一定意味着更高延迟（取决于队列负载比）；（3）QoS 对齐不是零和博弈，所有优先级的流量都可以受益。论文的价值主要在于 operational insight 而非系统创新——Aequitas 的设计本身较简单（静态 3 级映射），但部署过程中遇到的工程挑战（用户抗拒 QoS 降级、渐进式部署策略、增量变更下的效果推断）和从中提炼的经验教训，对任何在大规模网络中部署 QoS 策略的团队都有参考价值。主要局限在于未覆盖 WAN 流量、缺乏 fleet-wide 综合评估、以及静态映射在面对动态负载时的灵活性不足。
