# Efficient Multi-WAN Transport for 5G with OTTER

**作者**：Mary Hogan (Oberlin College), Gerry Wan (Google), Yiming Qiu (University of Michigan), Sharad Agarwal (Microsoft), Ryan Beckett (Microsoft), Rachee Singh (Cornell University), Paramvir Bahl (Microsoft)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/hogan
**源文件**：[[nsdi2025-hogan.pdf]]

---

## 一、背景

5G 网络正经历从专有硬件到云化软件的根本性转变。传统上，蜂窝网络功能（NFs）运行在专用硬件上，而 5G 的 cloudification 趋势将这些 NFs 拆分为软件化组件，部署在运营商边缘、云边缘和云数据中心上。例如，Nokia 的 5G Core 运行在 AWS 上，Microsoft 的 5G Core 运行在 Azure DC 上，AT&T 将 5G 网络迁移到 Azure。

这种云化意味着 5G 流量不再仅在运营商 WAN 内部流转，而是需要跨越运营商 WAN 和云 WAN 两个域。同时，5G New Radio（5G NR）正在解锁超低延迟和高带宽的无线模式（如 URLLC 要求 ~1ms 延迟和 99.999% 可靠性，eMBB 支持多 Gbps 数据速率），使得 WAN 成为 5G 端到端性能的瓶颈。

---

## 二、要解决的问题

1. **跨域路径优化缺失**：现有流量工程（TE）系统仅在单个 WAN 内部优化，无法捕获跨两个 WAN 的端到端路由性能目标。运营商 WAN 和云 WAN 各自独立做路由决策，导致次优的端到端路径（如论文 Figure 2 所示，独立决策的路径 P1 劣于全局最优路径 P2）。

2. **计算放置与网络路由脱节**：5G NFs 的部署位置（边缘 vs DC）和网络路径选择共同影响性能，但现有系统（如 5G NRF）仅考虑计算负载，不感知网络性能。CDN 式的目标选择也无法满足 5G 的细粒度需求。

3. **粗粒度 QoS 不匹配 5G 多样化需求**：现有 TE 系统仅支持少量优先级类别（如高/低优先级），无法表达 5G 流量的细粒度服务目标（如 AR/VR 要求 <20ms RTT，远程手术要求高可靠性，视频流需要 100+ Mbps 吞吐量）。论文 Figure 3 展示了严格优先级分配导致低优先级流无法满足需求，而更灵活的分配可以同时满足两者。

4. **动态流放置需求**：5G 流量具有动态和不可预测的特性，而传统 TE 基于周期性（如每 5 分钟）的批量预测分配，无法实现按需流放置。

---

## 三、洞察与设计

**关键洞察**：5G 云化使运营商和云提供商形成了新的经济利益共同体——运营商不仅是接入提供者，还是云的客户（用于托管 5G NFs 和应用）。这种利益对齐使得跨 WAN 协作成为可能，且运营商作为云客户拥有对两个 WAN 叠加层的网络性能可见性，无需共享私有 WAN 数据即可实现跨域路径优化。

基于此洞察，OTTER（Overlay Traffic Transport and Efficient Resource allocation）设计为跨运营商和云 WAN 的 overlay 网络系统，包含两个核心组件：

- **Controller（控制器）**：接收 5G 流的 QoS 需求（通过标准化 API），将流量需求映射为网络路径和计算资源。核心是一个线性规划（LP）优化器，联合优化流的目标计算节点和网络路径，最大化分配流量的同时最大化每个流的服务需求满足度。引入 demand function 将性能指标映射为 tolerance coefficient，支持任意细粒度的服务目标。

- **Orchestrator（编排器）**：管理云资源并实现转发机制。利用云原生功能（VPN gateway、VNet peering、用户自定义路由）构建 multi-WAN overlay，无需部署自定义 BGP speaker 或数据包转发器。

关键设计决策：
- 作为 overlay 运行于现有 TE 之上，不需要修改底层 WAN TE 或 BGP 协议
- 使用贪心启发式 + 周期性 LP 优化的混合策略实现按需流放置
- PER+PATHPIN 策略：对延迟/抖动敏感流锁定路径，避免重优化导致的服务中断

---

## 四、实现细节

**Orchestrator 实现**：
- 使用 HashiCorp Terraform 构建，约 4,100 行 HCL 代码（2,600 行模块部署 + 600 行 GCP 资源 + 900 行 Azure 资源）
- GCP 模拟运营商 WAN，Azure 作为云 WAN
- 跨 US 8 个区域部署，GCP 侧包含 8 个 VPC（全网格 peering）、32 个 VPN 网关、64 条 VPN 隧道；Azure 侧包含 64 台 32 核 VM、72 个 VNet

**Measurement Coordinator**：
- 约 1,200 行 C# 代码
- 使用 iPerf3 测量吞吐量（TCP CUBIC，60 并行连接），sockperf 测量 RTT 和 jitter
- 测量结果存入 Azure Cosmos DB NoSQL 数据库

**Optimizer**：
- 约 500 行 LP 代码，使用 Gurobi 求解器
- 运行在 16 核 3GHz CPU、48GB 内存的 VM 上
- 通过限制候选目标数量（选择 n 个最优目标）和调整优化周期来控制求解时间

**流分配策略**：
- GREEDY：按到达顺序贪心分配到最佳路径
- PER：GREEDY + 周期性全量 LP 重优化
- PER+PATHPIN（最终选择）：PER 但对 RTT/jitter 敏感流锁定路径和目标
- PER+DSTPIN：PER 但对敏感流仅锁定目标

---

## 五、实验结果

### Orchestrator 评估（两个商业云 WAN 上的真实部署）

在 GCP 和 Azure 之间 64 对 Src-Dst 对上进行 24 小时测量：

| 指标 | 平均改善 | 最大改善 |
|------|---------|---------|
| 吞吐量 | +13% | +136%（6-10 Gbps），峰值 >20 Gbps |
| RTT | -15% | -56%（最大减少 42ms） |
| Jitter | -45% | -99%（减少超过 10ms） |
| Packet Loss | 从 0.06% 降至 <0.001% | 最大减少 >0.4% |

### Controller 评估（模拟实验）

- 拓扑参数基于真实测量值，8 源、8 目标（2 DC + 6 边缘），每对 8 条路径
- 流到达率 20K-40K flows/s，平均持续时间 10s
- 8 种 5G 应用 profile（基于 3GPP 标准）

| 对比维度 | 结果 |
|---------|------|
| PER+PATHPIN vs GREEDY | 分配字节量多 26%-45% |
| PER+PATHPIN vs OPT（不可达上界） | 仅少 ~10% |
| 考虑资源约束 vs 不考虑 | 不考虑导致实际分配减少 23%-50% |
| RTT 满足率 | PER+PATHPIN 47% 流完美满足 vs GREEDY 41% |
| 可扩展性 | 支持到 512K flows/s 无显著性能下降 |

---

## 六、批判性分析

1. **运营商 WAN 用 GCP 模拟的可信度问题**：论文将 GCP 作为运营商 WAN 的替代品进行评估，但真实运营商 WAN 的拓扑、延迟特性和路由策略与公有云网络存在显著差异。论文对此仅轻描淡写提到"we substitute the operator WAN with GCP"，未充分讨论这种替代对结果的影响。

2. **Controller 评估基于合成流量**：虽然 Orchestrator 在真实云上部署评估，但 Controller 的核心算法评估完全基于合成的 Poisson 到达流量和随机应用 profile。真实 5G 流量的到达模式、空间分布和需求组合可能与此有很大差异，论文未提供来自实际 5G 部署的 trace 验证。

3. **成本和部署复杂度被低估**：跨 US 8 区域的 OTTER 部署需要 32 个 VPN 网关、64 条 VPN 隧道、72 个 VNet、64 台 VM 等大量云资源。论文未分析这些资源的成本，也承认"optimizing for WAN costs is not a priority"。对于实际运营商而言，部署和运维成本可能是采用的关键障碍。

4. **13% 平均吞吐量改善的实际价值**：虽然最大改善达 136%，但平均仅 13%。论文以"best case"数字作为亮点（6-10 Gbps 提升），但中位改善可能对许多 Src-Dst 对来说并不显著。从图 6a 可以看到，部分 Src-Dst 对的改善接近零甚至为负。

5. **LP 求解延迟与"按需"流放置的矛盾**：论文强调 5G 需要按需流放置，但 LP 优化器的求解需要时间，期间只能退化为 GREEDY 分配。虽然 GREEDY+周期性重优化是合理的折中，但论文未充分量化求解延迟在高负载下的具体影响。

6. **与现有 TE 系统的交互分析不足**：论文在 §8 中讨论了 OTTER 不会负面影响现有 TE，但这只是定性讨论。在高负载场景下，OTTER 的 overlay 路由决策可能导致底层 TE 的流量矩阵预测失准，引发 TE 与 OTTER 之间的振荡，论文未提供相关实验。

---

## 七、总结

OTTER 针对 5G 云化带来的跨域流量性能挑战，提出了基于 multi-WAN overlay 的流量传输和资源分配系统。其核心贡献在于联合优化计算放置和网络路径选择的 LP 算法，以及利用云原生功能构建可扩展 overlay 的工程实践。在真实商业云部署中实现了 13% 平均吞吐量提升和 15% RTT 降低等改善。系统的主要局限在于使用 GCP 替代真实运营商 WAN 的评估方式，以及未考虑部署成本。该工作适用于拥有云化 5G 基础设施的大型运营商场景。
