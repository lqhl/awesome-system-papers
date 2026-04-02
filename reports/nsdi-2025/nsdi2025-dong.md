# Evolution of Aegis: Fault Diagnosis for AI Model Training Service in Production

**作者**：Jianbo Dong*, Kun Qian*, Pengcheng Zhang*, Zhilong Zheng, Liang Chen, Fei Feng, Yichi Xu, Yikai Zhu, Gang Lu, Xue Li, Zhihui Ren, Zhicheng Wang, Bin Luo, Peng Zhang, Yang Liu, Yanqing Chen, Yu Guan, Weicheng Wang, Chaojie Yang, Yang Zhang, Man Yuan, Hanyu Zhao, Yong Li, Zihan Zhao, Shan Li, Xianlong Zeng, Zhiping Yao, Binzhang Fu, Ennan Zhai, Wei Lin, Chao Wang, Dennis Cai（Alibaba Cloud）
**会议**：NSDI 2025（22nd USENIX Symposium on Networked Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/nsdi25/presentation/dong
**源文件**：[[nsdi2025-dong.pdf]]

---

## 一、背景

大规模 AI 模型训练（如 LLM 训练）需要数千到上万块高端 GPU（A100、H100）通过高速网络（rail-optimized network、NVLINK）协同工作，训练过程通常持续数周。作为公有云训练服务提供商，阿里云需要为各类客户提供稳定的模型训练服务。然而，大规模训练集群的故障率远高于传统云计算场景：每周会发生 100-230 次关键故障，GPU 平均无故障时间仅 200-400 天。更严峻的是，由于训练的同步特性，单点故障会级联扩散至整个集群，使得故障根因定位极具挑战。

传统云计算的诊断系统（网络监控、RDMA Pingmesh、带内诊断）聚焦于网络层面的源-目的路径诊断，无法处理模型训练场景中故障从单点扩散到全集群的问题。现有的训练专用方案也各有局限：SuperBench（Microsoft）仅支持离线诊断，耗时数小时；MegaScale（ByteDance）需要深度耦合客户模型代码，不适用于公有云多租户场景。

---

## 二、要解决的问题

1. **故障扩散导致根因隐藏**：模型训练依赖 collective communication 同步，任何单点故障都会导致所有 host 报告 CCL timeout 错误，真正的根因被大量二次错误淹没，传统的源-目的路径追踪方法完全失效。

2. **离线诊断代价过高**：当运行时无法定位故障时，需要隔离所有相关 host 进行离线诊断，这严重浪费 GPU 资源、降低集群利用率，并延长用户等待时间。

3. **无法修改客户代码**：作为公有云服务提供商，不能要求客户定义 "critical code segments" 或在模型代码中嵌入监控模块——客户模型架构各异、代码高度保密，这一约束排除了 MegaScale 类方案。

4. **硬件故障率高且类型复杂**：高端 GPU 故障率远高于传统硬件（45.6% 故障与 GPU 相关），加上复杂的 intra-host 网络拓扑（PCIe、NVLINK）和 rail-optimized 长距离光纤链路，故障类型多样且定位困难。

5. **73% 的任务在初始化阶段就失败**：大量故障在训练任务启动前就已存在（组件更新残留、上次使用后的遗留问题），但缺乏交付前的系统性检查机制。

---

## 三、洞察与设计

**关键洞察**：Collective Communication Library（CCL）位于计算与通信的边界，是训练框架中模块化的独立组件，可以在不修改客户代码的前提下被替换。通过定制 CCL 收集运行时统计信息（collective launch count、work request/completion count），可以精确区分故障发生在计算阶段还是通信阶段，从而实现对故障根因的实时在线定位。

### Aegis 的两阶段演进设计

**Phase-1：增强现有诊断系统**
- **Basic Error Diagnosis**：从系统日志（dmesg、NIC driver、switch syslog 等）中总结关键错误模式，区分 CriticalError（直接隔离 host）和 DistError（分布式错误需进一步分析）。核心策略是"先排查 host 侧关键故障"——实践中 71% 的分布式故障最终与网络无关。
- **Offline Diagnosis**：作为兜底方案，设计拓扑感知的并行离线定位——按物理网络拓扑将 host 分成子集并行运行参考模型，逐步二分缩小故障范围。

**Phase-2：Procedure-aware Diagnosis（CCL 定制）**
- 定制 CCL 记录三类轻量级指标：CL（collective launch count）、WR（work request count）、WC（work completion count）。
- **计算故障场景**：故障 GPU 无法发起下一次 collective operation，表现为 CL 值落后于同组其他 GPU。
- **通信故障场景**：所有 GPU 的 CL 相同但某个 GPU 的 WR > WC，说明该 GPU 相关的 work request 传输失败，进而用 NetDiag 定位网络设备。

**Performance Degradation Diagnosis**
- **Basic Correlating Diagnosis**：选取 20+ 监控指标，使用 Z-Score 异常检测（λ+2δ 阈值）跨 host 对比，识别产生显著不同指标值的异常节点。
- **Enhanced Procedure-aware Diagnosis**：进一步定制 CCL 记录通信持续时间（TD）和网络吞吐量（N），用阈值（α=0.8, β=1.5）区分计算降级和通信降级。

**Check Before Delivery（CBD）**
- 在资源交付给客户前执行系统性检查，包括配置检查（<1min）、单机测试（3min）和多机测试（6min），总计不超过 10 分钟。拦截 1-2% 的问题 host。

---

## 四、实现细节

- **诊断流程**（Algorithm 1）：CriticalError → 直接隔离；DistError ≤ 2 hosts → 直接隔离；DistError > 2 hosts → RootDiag 按源/目的聚类分析 → ConfigCheck + NetDiag → 全部失败则 OfflineDiag。
- **离线并行定位**：单机自检（CPU/GPU/PCIe/NVLINK stress test）完全并行；多机诊断选择与客户模型计算通信模式匹配的参考模型，按拓扑分割子集并行训练，逐步收敛到故障 host。
- **CCL 定制部署**：需要为所有 CCL 发布版本提供对应的定制版本，以支持不同客户环境（不同 CUDA、driver、CCL 版本）。
- **Z-Score 异常检测**：周期 T=10 分钟的流式计算，经过与 LOF、Isolation Forest、DBSCAN 的对比验证，简单 Z-Score 在精度和召回率上表现相当，且计算开销最低。
- **CBD 任务列表**：配置检查（Host/GPU/NIC）→ 单机测试（GPU kernel/NVLINK/HBM/PCIe/CPU）→ 多机测试（collective communication/compute-comm overlap），轻量版 CBD 可在 1 分钟内完成。

---

## 五、实验结果

Aegis 在阿里云内部 LLM 训练项目上部署超过 16 个月，训练规模增长超 40 倍。

| 指标 | Phase-1 效果 | Phase-2 效果 | 最终效果 |
|------|-------------|-------------|---------|
| GPU 空闲时间（因诊断等待） | 降低 71% | 再降低 91% | 总计降低 97% |
| 运行时诊断比例 | ~77% | 接近 100% | 几乎所有故障在线诊断 |
| 训练任务重启次数 | — | — | 降低 84%（CBD 贡献） |
| 性能降级程度 | — | — | 降低 71% |

其他关键数据：
- 集群规模：O(1K) hosts，O(10K) GPUs
- A100 平均故障间隔约 400 天，H100 约 200 天
- 45.6% 故障与 GPU 相关，10.4% PCIe 错误，9.2% NVLINK 故障
- 光模块/光纤故障率比 DAC 高 1.2-10 倍
- 73% 的失败任务在前 10 分钟（初始化阶段）就崩溃
- CBD 拦截 1-2% 的问题 host
- 每周执行超过 O(10K) 次链路热修复

---

## 六、批判性分析

1. **评估数据局限性**：由于保密原因，所有评估数据来自阿里云内部 LLM 训练项目，而非外部客户。内部团队与诊断系统开发团队协作更紧密，可能高估了 Aegis 在真实多租户场景中的表现。外部客户的异构环境、多样化模型架构是否会带来新的诊断盲区未被验证。

2. **CCL 定制的版本维护成本被轻描淡写**：论文承认需要为所有 CCL 版本提供定制版本，但未量化这一工程负担。随着 NCCL 版本迭代加速（NCCL 2.x 频繁发布），以及 AMD RCCL、Intel oneCCL 等异构 CCL 的出现，版本维护的长期可持续性存疑。

3. **97% 的 idle time 减少缺乏分解**：该数字是 Phase-1（71%）和 Phase-2（91%）的叠加效果，但论文没有明确说明这两个百分比的基准是否一致。训练规模在此期间增长了 40 倍，如果基准随规模变化，百分比的可比性值得质疑。

4. **Z-Score 异常检测的假设过于理想**：假设"少数节点异常、多数节点正常"，但论文在 §5.1 Limitation 中承认当大量 host 同时出现指标变化时该方法失效。实际上，网络拥塞、congestion control bug 等系统性问题并不罕见（论文自身就报告了 NIC congestion control bug 案例），这意味着基础方法的覆盖范围可能比展示的更窄。

5. **缺少与同类系统的定量对比**：论文将 Aegis 与 SuperBench、MegaScale 进行了定性比较，但没有在相同工作负载上的定量对比。Figure 5 的定位图仅是概念性的，不足以证明 Aegis 的综合优势。

6. **"silent packet loss only > 1KB" 的案例过于特殊**：论文用这个案例说明增强 RDMA Pingmesh 的必要性，但这种故障模式的发现更像是运气而非系统性方法。论文未讨论还有多少类似的 "unknown unknowns" 无法被当前框架覆盖。

7. **CBD 的 10 分钟开销对某些场景不可接受**：论文自己也承认完整 PaaS 模式下 10 分钟额外开销"仍然无法忍受"，因此提供了 1 分钟的轻量版。但轻量版能覆盖多少比例的故障未给出数据。

---

## 七、AI Infra / MLSys 视角

1. **CCL 作为可观测性注入点的通用价值**：Aegis 最有启发性的设计选择是将 CCL 作为诊断信息的采集层。这一思路可以推广到更多场景——例如在 CCL 层注入 profiling 信息以支持自适应并行策略调整、通信调度优化等。未来的分布式训练框架（如 Megatron、DeepSpeed、ColossalAI）可以考虑在 CCL 接口层标准化诊断/遥测接口。

2. **Procedure-aware 诊断思路对训练系统自动调优的启发**：CL/WR/WC 三个指标本质上刻画了计算-通信的流水线状态。这些信息不仅可用于故障诊断，还可以用于：
   - 自动检测 pipeline bubble 并触发动态负载均衡
   - 识别 straggler 并进行运行时 migration
   - 为 auto-parallelism 系统提供实时反馈信号

3. **Check Before Delivery 模式对 GPU 云服务的普适意义**：随着 GPU 云服务成为主流，CBD 式的交付前检查应该成为标准流程。可以进一步探索：
   - 基于历史故障数据的预测性维护（predictive maintenance），在 host 交付前评估其故障概率
   - 将 CBD 检查结果纳入调度决策，优先分配"健康分"高的 host

4. **值得跟进的研究方向**：
   - **跨层联合诊断**：Aegis 目前分别处理硬件故障、网络故障、性能降级，但实际中这些问题经常交织。如何构建统一的因果推断框架，从 CCL 指标 + 系统指标 + 网络指标联合推断根因，是一个有价值的研究问题。
   - **LLM-assisted 故障诊断**：利用 LLM 理解非结构化日志、关联多源信息，辅助故障模式识别和根因分析，特别是处理论文中提到的 "unknown unknowns"。
   - **异构加速器集群的诊断泛化**：随着 AMD MI300、Intel Gaudi、国产加速器的部署，如何使诊断系统适配异构硬件是紧迫的工程问题。

---

## 八、总结

Aegis 是阿里云为大规模 AI 模型训练云服务构建的故障诊断系统，通过两阶段演进（增强现有系统 → 定制 CCL 实现 procedure-aware 诊断），在不修改客户代码的前提下实现了接近 100% 的运行时故障在线定位。系统还覆盖了性能降级诊断（Z-Score 异常检测 + CCL 增强）和交付前检查（CBD）。在阿里云生产环境中部署超过 16 个月，将诊断导致的 GPU 空闲时间降低 97%、训练重启次数降低 84%、性能降级降低 71%。其核心贡献在于发现 CCL 是计算与通信边界上理想的诊断信息注入点，但评估仅基于内部项目、CCL 版本维护的长期成本有待观察。
