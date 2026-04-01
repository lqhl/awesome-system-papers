# Enabling Efficient GPU Communication over Multiple NICs with FuseLink

**作者**：Zhenghang Ren, Yuxuan Li, Zilong Wang, Xinyang Huang, Wenxue Li, Kaiqiang Xu, Xudong Liao, Yijun Sun, Bowen Liu (HKUST); Han Tian (USTC); Junxue Zhang (HKUST); Mingfei Wang (MetaX Integrated Circuits); Zhizhen Zhong (MIT); Guyue Liu (Peking University); Ying Zhang (Meta); Kai Chen (HKUST)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/ren
**源文件**：[osdi25-ren.pdf](../../papers/osdi-2025/osdi25-ren.pdf)

---

## 一、背景

分布式 ML 训练和推理的规模不断扩大，GPU 间通信带宽成为关键瓶颈。当前 GPU 集群的服务器内部署有高速 intra-server 连接（如 NVLink，可达 Tbps 级带宽），但 inter-server 通信依赖 RDMA NIC，单块 NIC 带宽远低于 intra-server 互联。为弥补这一差距，现有实践在每台服务器内堆叠多块 NIC（通常与 GPU 数量 1:1 配置），每块 GPU 通过 PCIe 静态绑定到一块直连 NIC。

然而，许多实际 ML 任务的 inter-server 通信流量是**动态且不均衡**的。静态 GPU-NIC 绑定在这些场景下导致部分 NIC 成为热点瓶颈，而其他 NIC 处于空闲状态，造成严重的带宽浪费。

---

## 二、要解决的问题

1. **静态 GPU-NIC 绑定导致 NIC 利用率低**：在 disaggregated LLM serving、MoE expert-parallel training、DLRM embedding 传输等动态流量场景中，NIC 利用率仅为 13%-82%，大量 NIC 带宽被浪费。

2. **多 NIC 传输受限于 PCIe 拓扑**：一个 GPU 想通过非直连（indirect）NIC 发送数据时，需经过 PCIe root complex 甚至跨 NUMA 路径，带宽大幅下降（直连 49.3 GBps vs 跨 UPI 仅 12.0 GBps）。

3. **GPU relay 引入的同步开销**：GPU 互联（NVLink）与 inter-server 网络（RDMA NIC）不兼容，中继数据需要频繁的设备同步，导致 NIC 吞吐提升有限。

4. **动态调度的竞争与中断风险**：利用空闲 NIC 时可能干扰正在通信的 peer GPU，抢占 NIC 带宽或耗尽 relay GPU 的显存，导致 OOM。

---

## 三、洞察与设计

**关键洞察**：Intra-server 高速 GPU 互联（NVLink）可以作为 inter-server 网络的无缝扩展——通过将 NVLink 集成到网络数据路径中，让 GPU 充当 relay 节点，将流量动态路由到空闲 NIC，从而聚合多块 NIC 的带宽。ML 应用的特性（有限数量的 inter-server 连接、大消息分 chunk 发送）使得运行时动态调度 NIC 流量成为可能。

FuseLink 的核心设计包括四个层面：

1. **高效 intra-server relay（D1 方案）**：利用 GPU 虚拟地址系统，将网络 buffer 的物理内存重映射（remap）到 relay GPU 上。当应用填充发送 buffer 时，数据通过 NVLink 直接写入 relay GPU 的内存，NIC 可立即读取，无需额外的内存拷贝或 CPU 参与。这是四种候选方案中 indirect NIC 吞吐最高的方案。

2. **Interruption-free relaying**：FuseLink 仅在 indirect NIC 空闲时使用其带宽，不对 peer GPU 的通信进行流量喷洒。同时采用优先级内存管理，设置 relay memory 上限，并在 relay GPU 显存紧张时优先释放 relay buffer。

3. **NIC contention mitigation**：通过 worker-aware NIC monitoring 监控各 NIC 的工作状态（busy/idle），为每块 NIC 上的 GPU worker 分配优先级。高优先级 worker 的直连 NIC 不会被低优先级流量抢占。

4. **Load-aware scheduling**：Receiver 在 credit 中附带 NIC 空闲状态，sender 综合双端 NIC 状态选择最优 NIC 发送数据。通过限制 indirect NIC 上的 outstanding 操作数量来控制潜在竞争。

---

## 四、实现细节

- **基于 NCCL 集成**：FuseLink 作为 NCCL 的网络插件实现，替换默认的 IB 网络层。通过拦截 NCCL proxy thread 的函数调用（连接建立、buffer 注册、收发操作）来集成，ML 应用无需修改代码。

- **Memory remapping 机制**：利用 CUDA 统一虚拟地址空间，将网络 buffer 的虚拟地址映射到 relay GPU 的物理内存。每个 buffer 只需在 NIC 注册一次，同时在 relay GPU 和原始 GPU 上都注册，以便在 NIC contention 时快速切回。

- **调度架构**：FuseLink scheduler 作为守护进程运行。GPU worker 通过 FIFO 队列提交网络操作，FuseLink 收集操作并向 RDMA NIC 提交 work request。通过轮询 RDMA completion queue 监控 NIC 状态。

- **Credit 机制**：Receiver 在 RDMA credit 中编码 idle NIC 信息，sender 据此决定使用哪块 NIC。这与 RDMA 原生 credit 机制兼容。

- **调度开销**：NIC 监控和选择延迟 0.9-1.6 μs，relay remapping 延迟 95-193 μs，相比 ML 通信时间开销很小。

---

## 五、实验结果

**实验平台**：Intel 8480C CPU，8 块 Nvidia Hopper GPU（八路 NVLink，200 GB/s），8 块 ConnectX-7 400 Gbps NIC。

**基线**：NCCL with PXN enabled。

### 微基准测试

| 指标 | Baseline (1 NIC) | FuseLink (6 NICs) |
|------|------------------|--------------------|
| 单 GPU inter-server 带宽 | ~50 GBps | **212 GBps** (4.31×) |

各设计模块的增量贡献：

| 设计 | 带宽 (GBps) | Speedup |
|------|------------|---------|
| Baseline | 49.27 | 1.0× |
| + Efficient relaying (§4.1) | 78.39 | 1.59× |
| + Eliminate interruption (§4.2) | 76.37 | 1.55× |
| + Reduce NIC contention (§4.3) | 178.59 | 3.62× |
| + Scheduling efficiently (§4.4) | 212.35 | 4.31× |

### 端到端评估

| ML 任务 | 配置 | 加速比 |
|---------|------|--------|
| Disaggregated LLM Serving (OPT-30B) | 8 instances, TP=1 | TTFT P50: 2.22×, P99: 1.94× |
| | 4 instances, TP=2 | TTFT P50: 1.42×, P99: 1.14× |
| | 2 instances, TP=4 | TTFT P50: 1.20×, P99: 1.09× |
| MoE EP Training (Mixtral 8×22B) | EP=8, TP=4 | 1.3× |
| DLRM Training (DeepFM) | 32 GPU workers | 最高 1.2× |

---

## 六、批判性分析

1. **加速比对 serving 实例数高度敏感**：LLM serving 的加速从 TP=4 时的 1.09×（P99）到 TP=1/8 instances 时的 2.73×，跨度很大。实际部署中 TP=4 或 TP=8 更常见（大模型需要），此时加速比偏低。论文倾向于强调 best case（8 instances, TP=1），但这并非大模型 serving 的典型配置。

2. **MoE 训练加速随迭代递减**：论文承认 gate layer 的 load balancing 机制会使流量逐渐趋于均衡，导致 FuseLink 的优势减弱。这意味着在训练后期，FuseLink 的实际收益可能远低于 1.3×，但论文没有报告稳态时的具体数字。

3. **OOM 风险仅提供"best-effort"解决方案**：论文坦承无法精确估算运行任务的显存占用，relay buffer 的分配可能引发 OOM。提出的方案（设上限 + 优先释放）只是缓解而非根治，在显存紧张的大模型训练场景下（本就是 FuseLink 的目标场景），这一风险不容忽视。

4. **仅适用于点对点通信**：论文明确指出 FuseLink 在 collective communication（如 ring allreduce）场景下流量均衡，无显著收益。然而 allreduce 在数据并行训练中占据主导地位，这限制了 FuseLink 的适用范围。

5. **Corner case 被轻描淡写**：NIC 调度存在 bounded suboptimal 的 tradeoff，即 sender 可能在 NIC 刚被占用时仍向其调度流量，然后被抢占。论文以"ML workload 消息大、间隔长"为由认为此情况罕见，但未提供量化分析。

6. **实验规模偏小**：端到端实验仅涉及 2-4 台服务器、32 GPU 的规模。论文提及 NVL72 等大规模 NIC 不均衡场景，但未在此类系统上验证。

---

## 七、AI Infra / MLSys 视角

1. **对 disaggregated serving 架构有直接价值**：随着 prefill-decode 分离、PD disaggregation 成为 LLM serving 的主流架构，跨阶段的 KV cache 传输正是 FuseLink 的最佳应用场景。未来可研究 FuseLink 与 KV cache 传输调度（如预测 decode 实例的空闲 NIC）的协同优化。

2. **Memory remapping 思路可迁移**：D1 方案通过虚拟地址重映射实现零拷贝 relay 的思路，可以借鉴到其他需要跨设备数据搬运的场景，如 disaggregated memory pool、offloading KV cache 到 host memory 等。

3. **MoE 训练中 all-to-all 加速**：Expert parallelism 正成为大规模 MoE 模型训练的标配，all-to-all 通信是其核心瓶颈。FuseLink 的 NIC 动态调度思路值得在更大规模（数百 GPU）和更多 MoE 架构（如 DeepSeek-V3 的 fine-grained expert）上进一步验证。

4. **可探索的延伸方向**：
   - 将 FuseLink 与 collective communication 结合：研究如何在混合并行（DP + TP + EP）中自动识别不均衡的通信模式并启用 FuseLink
   - 在 NVL72 等大规模 GPU domain 上的适配：72 GPU 共享 NIC 资源，调度空间和复杂度都大幅增加
   - 与 network-aware job placement/scheduling 的结合：在集群调度层面考虑 FuseLink 的能力，优化 GPU-NIC 拓扑感知的任务放置

---

## 八、总结

FuseLink 通过将 intra-server GPU 高速互联（NVLink）集成为 inter-server 网络的扩展，实现了动态多 NIC 带宽聚合，将单 GPU 的 inter-server 带宽从 ~50 GBps 提升至 212 GBps。其核心技术包括虚拟地址重映射实现零拷贝 relay、worker-aware NIC 监控与优先级调度、以及 NCCL 无缝集成。FuseLink 在流量不均衡的 ML 任务（LLM serving、MoE 训练、DLRM 训练）中表现出 1.04-2.73× 的加速，但其收益主要集中在点对点通信场景，对 collective communication 的适用性有限，且 OOM 风险管理仅为 best-effort 方案。
