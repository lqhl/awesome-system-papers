# BLITZSCALE: Fast and Live Large Model Autoscaling with O(1) Host Caching

**作者**：Dingyan Zhang, Haotian Wang, Yang Liu, Xingda Wei (上海交通大学), Yizhou Shan (华为云), Rong Chen, Haibo Chen (上海交通大学)
**会议**：OSDI 2025 (19th USENIX Symposium on Operating Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/osdi25/presentation/zhang-dingyan
**源文件**：[[osdi25-zhang-dingyan.pdf]]

---

## 一、背景

Model-as-a-Service (MAAS) 是当前大模型推理服务的主流部署形式：云平台管理 GPU 集群，为每个用户部署的模型动态分配 GPU 实例。由于模型种类多（开源模型家族数百个，加上用户上传的微调模型）、请求到达率波动剧烈（2 秒内可突增 5 倍），静态分配 GPU 要么资源浪费严重，要么在突发流量下大量违反 SLO。模型自动扩缩容（autoscaling）是解决这一矛盾的关键机制——在请求突增时快速扩展新实例，在负载降低时回收资源。

自动扩缩容的核心瓶颈在于**数据平面**（data plane）——将模型参数加载到新实例 GPU 的过程。当前最先进的系统 ServerlessLLM 采用 SSD 加载 + 主机内存缓存的方案，但 SSD 带宽仅 2-10 Gbps/GPU，远不能满足亚秒级扩容需求；而主机内存缓存命中率仅 40-75%（因为要缓存所有模型到每台机器的 DRAM 根本不现实），缓存未命中时只能退回到慢速 SSD 加载。

---

## 二、要解决的问题

1. **数据平面速度不足**：以 Llama3-8B 为例，SSD 加载需要 12.8 秒，而维持 SLO 要求扩容时间低于 500ms（对应 576 Gbps/GPU 的参数传输带宽）。即使从主机缓存加载（256 Gbps PCIe），对大模型（72B）仍然不够快。

2. **主机缓存命中率低**：MAAS 系统同时服务数百甚至数千个模型，主机 DRAM 容量有限，缓存未命中率达 20-46%。尤其是需要多实例同时扩容时，涉及更多主机，未命中概率更高。

3. **停世界（stop-the-world）问题**：现有系统中，新扩展的实例必须等待所有参数加载完毕才能开始服务请求。即使网络足够快（如 200 Gbps RDMA），对于 72B 这样的大模型，仍然需要数百毫秒到数秒的停机时间，导致 SLO 违反。

4. **网络干扰**：在 PD 分离（prefill-decode disaggregation）架构下，扩容产生的参数传输流量会与 KV Cache 迁移流量竞争带宽，导致扩容时间增加 1.5 倍、尾部 TBT 劣化 50%。

---

## 三、洞察与设计

**关键洞察**：GPU 集群中用于计算的高速互联网络（RDMA 200 Gbps、NVLink 1.6-3.6 Tbps）在推理服务期间严重低利用——即使在网络密集型的 PD 分离工作负载峰值下，仍有超过 40% 的网络容量空闲。这意味着可以"借用"计算网络来加速扩容数据平面，且不需要（或仅需 O(1) 份）主机缓存。

基于这一洞察，BLITZSCALE 提出两个核心设计：

### 1. 基于计算网络的快速参数多播（Fast Data Plane）

- **网络替代 SSD/主机缓存**：当模型已有部署实例时，直接通过 RDMA/NVLink 从现有实例多播参数到新实例，完全不需要缓存。当无部署实例时，只需 O(1) 份主机缓存（全集群只需一份），通过串行转发多播即可覆盖任意数量的接收者。
- **无干扰多播规划器**：利用三个观察——(a) NVLink 速度极快可抽象为逻辑组，(b) 参数加载是带宽密集型操作适合贪心构建串行转发链，(c) RDMA 双向特性使得同链路上的入站和出站流量互不干扰——设计了服务感知的贪心规划算法，快速生成近似最优且不干扰服务工作负载的多播计划。
- **NVLink 分片并行传输**：在源和目标节点都有多 GPU 时，利用 NVLink AllGather 将传输时间降低到 1/N（N 为节点内 GPU 数）。

### 2. 基于层级协作执行的 Live 扩容（Live Data Plane）

- **细粒度层级扩容抽象**：打破传统实例级别的粗粒度扩容抽象，改为逐层扩容。新实例加载了前 k 层参数后，就可以立即执行这 k 层的计算，将结果（activation）传回旧实例完成剩余层。
- **ZigZag 调度**：通过 ILP 公式化或无 ILP 的优先级队列方法，动态决定每个请求批次在新旧实例间的 pipeline 配置（各执行多少层）。关键思路是"延迟调度"——让新实例多加载几层后再分配请求，使得 pipeline 更平衡，整体延迟更低。

---

## 四、实现细节

- **系统规模**：24,000 行 Rust + C++ 代码，使用 FlashInfer 作为 GPU kernel 库。选择原生语言是因为 Python 难以实现细粒度调度。
- **全局参数池**：维护模型参数在所有 GPU 和主机 CPU 上的位置映射。系统初始化时将每个模型的一份参数均匀分布到集群各主机的 CPU 内存中，保证 O(1) 缓存。
- **扩容规划算法（Algorithm 11）**：三步贪心——(1) 剪枝源节点避免服务干扰；(2) 按 NVLink 分组目标节点；(3) 贪心构建多条串行转发链，优先分配高带宽节点以加速吞吐提升。
- **ZigZag 调度**：支持 ILP 求解（Llama3-8B 约 40ms）和无 ILP 的优先级队列方法（适用于 80 层的 Qwen-72B 等大模型）。新实例维护分布式优先级队列，按 FCFS + 已加载层优先的策略调度。
- **LLM 特化**：支持 PD 分离和 PD 共置两种模式；decode 实例通过预扩容（与 prefill 同时扩容）隐藏扩容开销；控制平面通过 GPU checkpoint/restore 和 Rust/C++ 原生实现将启动时间降至极低。

---

## 五、实验结果

**测试平台**：

| 集群 | GPU | GPU-GPU (intra) | GPU-GPU (inter) | Host-GPU | SSD-GPU |
|-------|------|------------------|------------------|----------|---------|
| A (4×8) | A800 80GB | 1.6 Tbps NVLink | 100 Gbps RDMA | 128 Gbps PCIe | 10 Gbps |
| B (2×8) | A100 80GB | 256 Gbps PCIe | 100 Gbps RDMA | 128 Gbps PCIe | 10 Gbps |

**工作负载**：BurstGPT、AzureCode、AzureConv 三个真实世界 trace
**模型**：Llama3-8B、Mistral-24B、Qwen2.5-72B

**主要结果**：

| 对比 | 指标 | 改善幅度 |
|------|------|----------|
| vs. ServerlessLLM | TTFT | 47-75.5% 更短 |
| vs. ServerlessLLM | TBT | 5.1-94.1% 更短 |
| vs. AllCache (理想缓存) | TTFT | 21.1-47.3% 更短 |
| vs. DistServe (半量 GPU) | TTFT | 95.8% 更短 |
| vs. DistServe (全量 GPU) | GPU 时间 | 节省 49% |
| vs. ServerlessLLM | GPU 时间 | 节省 19.46% |
| vs. ServerlessLLM | 主机缓存 | 仅需 O(1) vs. 按主机数线性增长 |

**消融实验**：
- +Network（用计算网络替代 SSD）：全面改善
- +Multicast（多播优化）：在 AzureCode/AzureConv 上有效（需多实例同时扩容场景）
- +ZigZag（live 扩容）：在慢速网络集群（Cluster B）上最为有效

**详细观察**：
- BLITZSCALE 扩容 6 个 24B prefill 实例仅需 1,200ms，AllCache 需要 ~2,000ms
- Live 扩容过程中，加载仅几层后即可逐步输出 token
- 额外的网络使用量可忽略不计

---

## 六、批判性分析

1. **实验规模偏小**：集群最大仅 4×8=32 GPU（Cluster A），与实际 MAAS 系统（数百到数千 GPU）有数量级差距。多播链的效率、干扰避免策略在大规模集群中是否仍然有效，缺乏验证。贪心规划算法在更复杂的网络拓扑（多层 spine、跨机房）下的表现未知。

2. **网络利用率低的前提可能脆弱**：论文声称推理期间网络利用率低（峰值下仍有 40% 空闲），但这一观察高度依赖具体的部署配置和工作负载。随着 expert parallelism（MoE）、speculative decoding、跨实例 KV cache 共享等技术的普及，推理网络利用率可能大幅提升，BLITZSCALE 的带宽借用前提可能不再成立。

3. **扩容策略过于简单**：论文承认扩容策略（何时扩、扩多少）是正交问题并留作未来工作，但实际上扩容速度与策略紧密耦合。一个能在 500ms 内完成扩容的系统和一个需要 10s 的系统，最优策略可能完全不同。当前用的简单阈值策略能否充分发挥快速扩容的优势，存疑。

4. **ZigZag 调度的 ILP 形式化假设较强**：非 LLM 场景下假设相同 batch size 的每层执行时间相同，LLM 场景需要额外的 profiling 参数来处理 prefill/decode 的非对称性。在连续批处理（continuous batching）下，batch 大小持续变化，ZigZag 调度的实际效果可能不如论文中固定 batch 的分析。

5. **与 Lambda Scale 的对比不够充分**：论文在 Related Work 中提到并发工作 λScale 也使用网络加速扩容，但仅做了定性比较（λScale 牺牲吞吐、是 stop-the-world），没有定量实验对比。作为最直接的竞争者，这个缺失令人遗憾。

6. **PD 分离场景下 decode 实例无法 live 扩容**：论文承认由于入站带宽竞争，decode 实例在 PD 分离下无法做到无干扰 live 扩容，只能通过"先变异 prefill 实例为 decode 实例"间接实现。这个 workaround 增加了系统复杂度，且在极端场景（如仅需要扩 decode 不需要扩 prefill）下可能失效。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴

1. **"借用"空闲计算网络**的思路具有广泛适用性。在 AI 集群中，训练和推理往往使用同一套高速互联，但不同时段/不同任务的网络利用模式差异很大。这种"错峰利用"的思想可以扩展到 checkpoint、模型更新（在线学习/微调）、KV cache 跨实例共享等场景。

2. **层级协作执行（live scaling）**的思路值得关注。在模型并行度动态调整（如 MoE 的 expert 动态扩缩）、在线 A/B 测试（同一请求在不同模型版本间切换）等场景中，类似的"部分加载即可部分服务"的设计可以减少切换开销。

3. **O(1) 缓存 + 网络多播**的参数分发模型为 serverless AI 提供了新的资源管理范式——不再需要在每台机器上维护大量缓存，而是将参数视为可通过网络按需获取的资源。

### 值得跟进的方向

1. **MoE 模型的弹性 expert 扩缩**：BLITZSCALE 当前只做实例级扩缩，但 MoE 模型可以通过增减 expert 副本来细粒度调整容量。结合网络多播和 live scaling 技术，实现 expert 级的弹性扩缩容是一个有价值的研究方向。

2. **跨任务网络带宽调度**：如何在推理服务、扩容、checkpoint、KV cache 迁移等多种网络密集型操作间动态分配带宽，避免干扰并最大化整体效用，是一个开放问题。

3. **与 prefill-decode 分离架构的深度整合**：当前 BLITZSCALE 的 live scaling 在 decode 端有局限。如何设计一种统一的、对 prefill 和 decode 都友好的弹性架构，值得探索。

---

## 八、总结

BLITZSCALE 通过两个关键创新解决了模型自动扩缩容的数据平面瓶颈：(1) 利用推理期间低利用的 GPU 计算网络进行 O(1) 缓存的高效参数多播，(2) 将扩容抽象从实例级细化到层级，实现 live 扩容——新实例在参数未完全加载时就可以通过 ZigZag 协作调度分担旧实例的负载。在真实 trace 下，系统相比 ServerlessLLM 实现了高达 94% 的尾延迟降低和 19.46% 的 GPU 资源节省。主要局限在于实验规模有限、网络利用率低的前提可能随推理技术演进而变化、以及扩容策略与机制的协同优化尚未充分探索。
