# BLITZSCALE: Fast and Live Large Model Autoscaling with O(1) Host Caching

**作者**：Dingyan Zhang, Haotian Wang†, Yang Liu†, Xingda Wei（上海交通大学）；Yizhou Shan（华为云）；Rong Chen, Haibo Chen（上海交通大学）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会，2025 年 7 月 7–9 日，波士顿）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/zhang-dingyan
**源文件**：[osdi25-zhang-dingyan.pdf](../../papers/osdi-2025/osdi25-zhang-dingyan.pdf)

---

## 一、背景

大语言模型（LLM）推理服务正在以 Model-as-a-Service（MAAS）的形式大规模部署，平台管理数百个模型并为多个客户提供服务。为了同时实现高 goodput 和高硬件利用率，MAAS 系统依赖**自动扩缩容（autoscaling）**：按长期平均需求配置实例，在请求突发时动态扩容新实例，规避 SLO 违约。

然而，LLM 推理的请求到达具有强烈的秒级突发性（5× 需求量变化仅需 2 秒），且由于自回归生成的特性，单请求的内存/计算占用难以预测。这使得 autoscaling 的**速度**成为决定 SLO 达成率的关键因素。

---

## 二、要解决的问题

现有 autoscaling 方案面临两个核心瓶颈：

**1. 数据平面慢**：扩容的本质是把模型参数加载到新 GPU。当前 GPU 服务器的本地 SSD 带宽仅 2–10 Gbps/GPU，加载 Llama3-8B 需约 12.8 秒，Qwen2.5-72B 等大模型更慢。以 ServerlessLLM 为代表的系统引入**宿主机 DRAM 缓存**来加速，但命中率仅 40–75%——因为 MAAS 同时托管大量模型，100% 命中需要将所有模型都缓存在每台主机的 DRAM 里，根本不可行。

**2. 扩容是 stop-the-world 的**：现有系统以实例为最小粒度进行扩缩容，新实例在**全部参数加载完毕之前无法处理请求**。这意味着队列中的请求在整个加载期间都在等待，形成长尾延迟。

这两个问题叠加的结果：即使使用主机缓存的 AllCache 最优设置，高带宽需求（如 500 ms 内完成 72B 模型扩容需要 576 Gbps/GPU）也远超实际可用带宽。

---

## 三、核心设计

BLITZSCALE 提出两个互补的核心技术，分别解决"慢"和"stop-the-world"两个问题。

### 3.1 基于计算网络的 O(1) 缓存快速数据平面

**关键洞察**：GPU 集群已有高速计算网络（100–400 Gbps RDMA、16 Tbps NVLink），这些链路在 serving 期间的利用率极低（即使在 prefill-decode 分离的重网络负载下，利用率仅约 7.4%），完全可以借用来传输模型参数。

**网络带宽对比**：

| 链路类型 | 带宽/GPU |
|---------|---------|
| 本地 SSD | 2–10 Gbps |
| Host-GPU PCIe | 128–256 Gbps |
| GPU-GPU RDMA（跨机） | 100–400 Gbps |
| GPU-GPU NVLink（机内） | 256 Gbps–1.6 Tbps |

如果已有实例在运行该模型，BLITZSCALE 直接从这些 GPU 通过网络**多播（multicast）**参数，无需任何缓存。如果没有 GPU 实例运行该模型，只需在整个集群的宿主机中保留**一份**参数拷贝，通过广播多播即可服务所有新实例——这就是 O(1) 缓存：每个模型只需一份 host 缓存，整个集群的聚合主机内存足以缓存所有 MAAS 服务的模型。

**模型感知的多播规划器（Model-Aware Multicast Planner）**：

最优多播计划生成是 NP-hard 问题，且源/目标实例是动态决定的，无法离线计算。BLITZSCALE 设计了一个近似在线规划器：
- 将多播抽象为**链式串行转发**（每个节点转发给下游），单次 bulk 传输不随接收者数量增加而变慢
- 在异构网络（NVLink + RDMA 混合）上以**贪心+降序带宽**的方式生成多播链，优先发给高带宽节点以加快整体吞吐恢复速度
- 通过**干扰感知**的规划（利用模型 serving 的静态数据流特征），确保参数传输不与 serving 流量共用瓶颈链路，避免 1.5× 扩容时延和 50% TBT 劣化

### 3.2 基于层级细粒度的实时扩容（Live Scaling）

**关键洞察**：Transformer 模型是逐层执行的，可以将扩容粒度从实例级细化为层级，在参数尚未全部加载时就开始服务请求。

**协议**：
1. 新实例（inst.1）开始加载参数时，将所有排队和新请求**重定向**到 inst.1
2. 一旦 inst.1 的**第一层**加载完毕，立即开始执行来自请求批次中已有参数的层
3. 请求在两个实例间协作执行，inst.0 执行 inst.1 尚未加载的层，inst.1 执行已加载的层

**ZigZag 调度**：

最简单的"尽力而为"调度在 inst.1 初始时容量极小（只有 1 层参数），大量请求仍堆积在 inst.0，无法有效均衡负载。ZigZag 的关键思路是**延迟在 inst.0 上调度请求**，等待 inst.1 加载更多层后再以更激进的流水线配置（如(2,5)而非(1,6)）重新分配，使两端的执行时间重叠。

调度问题形式化为整数线性规划（ILP），目标是最小化平均延迟。对于层数较多的大模型（如 80 层的 Qwen-72B），还提供一种基于分布式优先队列的 ILP-free 实现：target 维护优先队列（FCFS + 已加载层优先），source 仅在自身无排队时才拉取请求执行。

### 3.3 全局参数池与扩容策略

BLITZSCALE 维护一个**全局参数池**，集中追踪所有已部署 GPU 和宿主机 CPU 上的参数位置。系统初始化时将每个模型的一份参数均匀分发到集群各主机的 CPU 内存中，并随 GPU 实例的部署/回收实时更新参数位置。

---

## 四、实现细节

- **通信库**：基于 P2P RDMA + NVLink 自研通信库（类似 DeepEP），绕过 NCCL 群组通信建立时的百毫秒延迟，预建立全连接池
- **CUDA 上下文池**：预创建带有已加载 kernel（cuModule）的 CUDA 上下文池，避免每次扩容时 ~500ms 的 cuContextCreate 开销
- **轻量运行时**：用 C++ + native CUDA API 实现，避免 PyTorch dlopen 初始化开销（vLLM 初始化需 13,800ms，BLITZSCALE 仅需约 1,400ms）
- **容错**：节点故障时自动触发扩容，并重新分发失效节点上缓存的参数以维持全局参数池不变量

---

## 五、实验结果

**实验集群**：

| 集群 | GPU | GPU-GPU 机内 | GPU-GPU 机间 | Host-GPU |
|-----|-----|------------|------------|---------|
| Cluster A（4×8 GPU） | A800 80GB | 1.6 Tbps NVLink | 100 Gbps RDMA | 128 Gbps PCIe |
| Cluster B（2×8 GPU） | A100 80GB | 256 Gbps PCIe | 100 Gbps RDMA | 128 Gbps PCIe |

**测试负载**：BurstGPT（72B Qwen2.5）、AzureCode（8B Llama3）、AzureConv（24B Mistral）

**端到端性能（vs. ServerlessLLM）**：

| 工作负载 | TTFT P95 降低 | TBT P95 降低 |
|---------|-------------|------------|
| BurstGPT × 72B | 75.5% | 7.4% |
| AzureCode × 8B | 47.3% | 94.1% |
| AzureConv × 24B | 48.1% | 1.8% |

**资源效率（vs. DistServe）**：
- BLITZSCALE 达到与 DistServe（Full，按峰值配置）相同的 SLO，GPU 用时少 **50%**
- 与 DistServe（Half，按均值配置）相比，TTFT 短 95.8%，TBT 短 1%
- 与 ServerlessLLM 相比，GPU 总用时低 **19.46%**，同时 TTFT 短 48.1%

**主机缓存用量**：
- BLITZSCALE 最多只需 O(1) 份主机缓存（小于 1 份规范化单位）
- ServerlessLLM 随参与主机数量线性增长，容易"污染"有限的主机内存

**消融实验（AzureCode × 8B，TBT P95）**：
- 基线（S-LLM）→ +Network：降低 10.6%
- +Network → +Multicast：再降低 0.5%
- +Multicast → +ZigZag（live）：再降低 94.1%（Cluster B 网络较慢，live scaling 效果最显著）

---

## 六、批判性分析

**1. 评估规模较小，可扩展性存疑**：实验最大规模是 Cluster A 的 4×8=32 块 A800 GPU，72B 模型最多 8 个实例（每实例需 4 GPU）。在真实 MAAS 环境中，单个集群可能有数百台机器，多播链规划的质量和网络干扰规避是否还能保持效果，论文未作充分论证。

**2. 多模型并发扩缩容的干扰**：论文的实验场景均为单模型多实例扩缩容，而真实 MAAS 同时服务数百个模型，多个模型同时触发 autoscaling 时，计算网络会被多个多播流量争抢。论文虽声称规划器是"干扰感知"的，但没有给出多模型并发扩容的实验数据。

**3. ZigZag 的 SLO 改善来源不够清晰**：消融实验显示 ZigZag 在 AzureCode（Cluster B，网络较慢）贡献最大（TBT 降低 94.1%），但在 BurstGPT（Cluster A）上贡献很小。论文将此解释为 Cluster A 网络更快所以 stop-the-world 时间已较短，但没有给出 ZigZag 相对于 fast stop-the-world 的具体延迟对比，难以独立评估 live scaling 的价值。

**4. TTFT vs. TBT 的不对称改善**：BLITZSCALE 在 TTFT 上相比 TBT 有更大的改善，作者解释为 decode 实例可以提前预扩容所致，这是策略层面的优化而非 BLITZSCALE 核心机制的贡献，两者被混在一起报告，容易误导读者。

**5. O(1) 缓存假设的隐含条件**：O(1) 缓存成立的前提是"集群聚合主机内存 ≥ 所有服务模型参数总量"。对于大规模 MAAS（数百个模型，每个模型数十到数百 GB 参数），这个假设需要仔细验证；论文对此未作定量分析。

**6. 与 λScale 的对比缺乏实验**：论文通过文字区分 BLITZSCALE 与并发工作 λScale 的差异（λScale 牺牲吞吐换取更快扩容速度），但两者没有直接实验对比，难以客观评估两种设计取舍的实际优劣。

---

## 七、AI Infra / MLSys 视角

**核心 Insight 的迁移价值**：

1. **计算网络带宽的"免费午餐"**：BLITZSCALE 的核心观察——LLM serving 期间计算网络利用率极低（~7.4%）——对 AI Infra 研究有重要启发。除了 autoscaling，这一空闲带宽还可用于 KV Cache 迁移（参见 Llumnix）、模型 checkpoint 传输、甚至在线 fine-tuning 参数同步等场景，值得系统性探索。

2. **层级粒度的 serving 抽象**：将 serving 从实例粒度细化到层粒度，不仅适用于扩容场景，也对模型并行、异构硬件混合执行、以及 speculative decoding 的系统设计有借鉴意义。

3. **O(1) 全局缓存 + 多播链**：这种"一份拷贝 + 网络广播"的思路对其他需要快速分发大 Blob 的系统（如 MoE expert 路由、多租户模型切换）有参考价值。

**值得跟进的研究方向**：

- **MoE 模型的 expert-level 动态加载**：论文提到 MoE expert 扩缩容作为 future work，这是 DeepSeek-MoE 等大模型场景下的实际需求，结合 BLITZSCALE 的网络多播机制可以设计 expert-granularity 的弹性 serving
- **多模型并发 autoscaling 的网络调度**：如何在数百个模型同时触发扩容时保证多播规划的公平性和隔离性
- **扩容策略与数据平面的协同优化**：当前论文将 scaling policy 设为正交问题，但实际上预测性扩容与快速数据平面结合可以进一步降低 SLO 违约率

---

## 八、总结

BLITZSCALE 通过两个互补创新解决 MAAS autoscaling 的根本问题：（1）利用集群计算网络的闲置带宽实现参数多播，将数据平面从 SSD 瓶颈解放出来，只需 O(1) 主机缓存；（2）将 scaling 粒度细化到层级，通过 ZigZag 协作调度在参数加载过程中逐步恢复服务能力。系统在真实 LLM 工作负载上实现最高 94% 的尾延迟降低和 49% 的 GPU 节省。主要局限在于多模型并发扩容的干扰分析不足，以及 O(1) 缓存假设在超大规模 MAAS 下的可行性尚待验证。
