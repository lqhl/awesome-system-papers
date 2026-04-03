# DRack: A CXL-Disaggregated Rack Architecture to Boost Inter-Rack Communication

**作者**：Xu Zhang, Ke Liu (SKLP, ICT, CAS; UCAS), Yuan Hui, Xiaolong Zheng (Huawei), Yisong Chang (SKLP, ICT, CAS; UCAS), Yizhou Shan (Huawei Cloud), Guanghui Zhang (Shandong University), Ke Zhang, Yungang Bao, Mingyu Chen, Chenxi Wang (SKLP, ICT, CAS; UCAS)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zhang-xu
**源文件**：[[atc2025-zhang-xu.pdf]]

---

## 一、背景

现代数据中心采用 ToR（Top-of-Rack）交换机为核心的机架架构，数据密集型应用（图计算、数据分析、DNN 训练）通常以 BSP 或 MapReduce 范式运行，涉及大量跨机架通信。Facebook 的生产数据显示，平均 87.1% 的网络流量需要跨机架传输。与此同时，GPU、FPGA 等加速器大幅提升了计算吞吐，使得通信阶段产生的数据量远超单个 NIC 的带宽容量（如计算吞吐达数百 GBps，而 NIC 仅 100Gbps）。这导致跨机架通信在主机 NIC 出口和过度订阅的核心网络处成为瓶颈。

---

## 二、要解决的问题

1. **NIC 出口瓶颈**：计算阶段产生的中间数据量巨大，单个主机 NIC 带宽不足以快速传输，导致计算资源空闲等待。
2. **核心网络过度订阅**：ToR 上行链路带宽有限，跨机架流量在聚合层产生拥塞。
3. **NIC 入口瓶颈**：多对一流量模式下，目标主机的单个 NIC 和 PCIe 链路成为接收瓶颈，导致 ToR 交换机出口端丢包（incast）。
4. **现有方案的局限**：拓扑重配置方案依赖难以预测的流量模式（短期突发流量持续时间不超过 100ms 的概率超过 50%）；暴力硬件升级（每台主机配备更多 NIC）代价高昂且加剧利用率不足；作业调度器无法完全避免跨机架流量。

---

## 三、洞察与设计

**关键洞察**：尽管跨机架流量巨大，但机架内主机 NIC 的带宽利用率却很低——Facebook 数据集显示超过 90% 的主机在任意 1 秒内未进行收发操作，实验表明平均 NIC 利用率不足 20%。原因有二：（1）应用语义导致计算不规则性和数据倾斜，使各主机通信量差异巨大；（2）资源碎片化——20%-45% 的机器运行非分布式作业，其 NIC 完全闲置，BSP 范式下计算阶段 NIC 也处于空闲状态。如果这些闲置 NIC 能被同机架的其他主机借用，跨机架通信就可以被加速。

基于此洞察，DRack 提出三个核心设计：

1. **NIC 池化（NIC Pool）**：将机架内所有主机的 NIC 解耦，形成机架级 NIC 池，任何主机都可以使用池中的 NIC 发送跨机架流量。通过 SR-IOV 将每个物理 NIC 虚拟化为多个 vNIC，分配给不同主机。
2. **内存池化（Memory Pool）**：将主机的本地内存解耦，形成机架级内存池（IS0），以 256B 粒度交织分布在所有内存设备上，聚合带宽超过 NIC 池容量，使 NIC 池的 DMA 读写可以并行访问多个内存设备，充分发挥吞吐能力。
3. **内存语义访问（Memory Semantics）**：利用 CXL.mem 使主机处理器在计算阶段直接 load/store 内存池中的数据，无需先通过 DMA 拷贝到本地内存。

DRack 选择 CXL 3.0 作为实现基础，因为 CXL 天然支持设备池化（CXL Fabric）和内存语义（CXL.mem），并通过 CXL.io 兼容现有 PCIe NIC。架构上，CXL 互连层成为新的 ToR 层，NIC 池充当上行链路，原始 ToR 交换机被提升为聚合层，从而在不增加硬件的情况下实现机架对之间的全二分带宽。

---

## 四、实现细节

**CXL 互连与 Fabric Manager (FM)**：FM 负责管理物理地址到内存设备的映射和交织粒度配置。内存池映射到统一的 Fabric 物理地址空间（FAS），组织为 2MB 大页 Section，K=512 个连续 Section 组成一个 Region。

**内存池管理**：每台主机 12GB 本地内存加入 IS0（256B 交织），剩余 4GB 作为 ISi 存储延迟敏感的数据结构（描述符队列、sk_buff 等）。后台 daemon 使用 buddy system 管理 Section 分配，应用通过 daemon 申请 Buffer，创建页表项映射虚拟地址到 Fabric 地址。

**NIC 池管理**：每个支持 SR-IOV 的 NIC 虚拟化为 N 个 vNIC（如 Intel 82599 支持 64 个），每台主机分配 M 个 vNIC。TX 路径：主机将 TX Buffer 均匀分布在 IS0 上，填充描述符到 TX virt_queue，通过 MMIO 触发 vNIC DMA 读取发送。RX 路径：预分配 RX Buffer 均匀分布在 IS0 上，vNIC DMA 写入后通过 MSI 中断通知主机。

**通信协议**：
- **机架内**：基于 CXL.mem 的 pass-by-reference 语义。发送方将数据引用存入接收方的 ref_queue，接收方被中断后加载引用，通过 TCP 栈验证后直接访问内存池中的数据，消除数据拷贝。
- **跨机架**：利用 MPTCP 将流拆分为多个 subflow，每个 subflow 绑定一个 vNIC，NIC 池并行 DMA 读取发送。接收端 vNIC 将数据 DMA 写入 IS0 中均匀分布的 RX Buffer。

**软件运行时**：内核驱动在 TCP/IP 栈下层透明地将 socket 系统调用（SEND/RECV）转换为 CXL.mem load/store 或 vNIC 操作，对应用完全透明。使用 write-around cache 策略避免不必要的 cache 污染。

**DRAM Cache**：每台主机 CXL 端口附加 1GB DRAM cache，缓存远程内存数据以隐藏 CXL 访问延迟（远程/本地延迟比高达 6.4x）。Tag 存储在片上内存中，支持多种缓存粒度（128B 和 4KB），按 Region 配置。TCP 栈处理完毕后显式调用 release 刷新 cache。

**原型实现**：使用 8 块定制 MPSoC FPGA（Zynq UltraScale+，4 核 ARM A53@1.2GHz）模拟 4 机架系统，每机架 2 台主机。通过 CXL-DoCE 协议层实现 CXL-like load/store，NIC 池和网络拓扑在服务器上用 DPDK 软件模拟。远程/本地内存延迟比配置为 R=6.4（最保守设定），跨机架网络 RTT 60µs。

---

## 五、实验结果

实验平台：4 机架 × 2 主机/机架的 FPGA 原型，对比基线为相同硬件的 ToR-centric 架构（ToRack）。

### 吞吐敏感型应用

| 应用 | 指标 | DRack 改善（平均） | DRack 改善（最佳） |
|------|------|------|------|
| PageRank（图处理） | 通信时间 | 32.8% | 58.5% |
| ResNet18 训练 | 通信时间 | 39.6% | 59.8% |
| TinyStories-33M 训练 | 通信时间 | 39.9% | - |
| DLRM 推理 | Embedding 层延迟 | 37.4% | - |

### 延迟敏感型应用

| 应用 | 指标 | DRack 改善 |
|------|------|------|
| Redis Cluster | p99 尾延迟 | 62.2% |
| Redis Cluster | 平均延迟 | 29.2% |

### 作业调度器集成

| 调度器 | 场景 | DRack 效果 |
|------|------|------|
| ShuffleWatcher | MapReduce shuffling | 节省 CPU 核心，总吞吐提升 20.8% |
| Crux | 多作业 DNN 训练 | 通信时间分别降低 47.7% 和 49.5% |

### 组件贡献分解

- **NIC 池**：Redis p99 延迟降低 32.9%，为主要贡献者
- **内存池**：进一步降低 Redis p99 延迟至 63.9%，ResNet 通信时间降低 38.1%
- **DRAM Cache**：对空间局部性好的应用效果显著（命中率 > 86.9% 时 ResNet 额外降低 28.6%），对随机访问模式效果有限（Redis 命中率仅 59.6%）
- **MPTCP**：Redis 额外降低延迟至 65.9%，解决单流绑定单 NIC 的负载不均问题

### 微基准测试

- 机架内通信延迟降低 15.9%（pass-by-reference 消除一次数据拷贝）
- 集合通信（AlltoAll, AllGather, Ring, Halving-Doubling）在不同过度订阅比下均优于 ToRack
- MPTCP 相比 ECMP 和 Packet Spray 更好地利用 NIC 池带宽

---

## 六、批判性分析

1. **原型规模极小，可扩展性存疑**：每机架仅 2 台主机、4 核 ARM A53@1.2GHz，与生产环境（每机架数十台主机、数百核 CPU/GPU）差距巨大。论文声称 DRack 可以通过添加更多设备灵活扩展，但未验证 CXL 交换机在数十台主机规模下的延迟和带宽表现。CXL Fabric 的交换延迟随拓扑复杂度增长，可能显著削弱收益。

2. **FPGA 模拟与真实 CXL 差距大**：使用 CXL-DoCE（Ethernet 封装的 AXI 信号）模拟 CXL 协议，与真实 CXL 3.0 硬件在协议开销、并发度、cache 一致性等方面存在本质差异。论文聚焦延迟比而非绝对延迟，但实际 CXL 交换机的排队延迟、仲裁开销等在模拟中被简化。

3. **NIC 利用率低的观察可能不具普适性**：论文引用的 Facebook 数据集是 2015 年的，采样率 1:30000。当前 GPU 集群（如 HPN、EFLOPS）为每个 GPU 配备 400Gbps NIC 且利用率较高。论文也承认这些集群"加剧了链路利用率不足"，但这恰恰说明不同工作负载下 NIC 利用率差异巨大，DRack 的适用场景需要更精确界定。

4. **忽略了 CXL 互连的故障域扩大问题**：NIC 和内存的解耦使得 CXL 交换机成为单点故障。一个 CXL 交换机故障将导致整个机架所有主机的 NIC 和部分内存不可用，而传统架构中单台主机故障只影响自身。论文未讨论故障隔离和容错机制。

5. **MPTCP 开销的轻描淡写**：论文在 Discussion 中提到 NIC 数量增加时 MPTCP 开销（中断、MMIO、子流合并的内核处理）会增大，但以"CPU 核心在通信阶段通常空闲"一笔带过。在异构工作负载混合部署场景下，CPU 核心不一定空闲，这个假设可能不成立。

6. **安全和隔离问题被忽略**：共享内存池意味着不同租户的数据存储在同一物理内存空间，论文未讨论内存隔离、安全保障和多租户场景下的性能干扰问题。

---

## 七、AI Infra / MLSys 视角

**对 AI 系统的启发**：

1. **分布式训练通信优化**：DRack 在 all-reduce 和 Parameter Server 架构下分别降低通信时间约 40%，核心思路——借用同机架闲置 NIC——对 GPU 集群有潜在价值。当前大模型训练中，机架内通常混合部署不同并行策略的作业（TP 内机架、DP/PP 跨机架），不同作业的通信模式和时间点存在差异，NIC 池化有机会提升整体带宽利用率。

2. **CXL 在推理场景的应用**：DLRM 推理中 Embedding 表的跨主机访问延迟降低 37.4%，这对推荐系统等 Embedding 密集型推理服务有直接参考价值。CXL 内存池可以作为大规模 Embedding 表的共享存储层，替代目前的 RDMA 远程访问方案。

3. **值得跟进的方向**：
   - **GPU 直连 CXL NIC 池**：当前原型仅验证了 CPU 场景，GPU 集群中 GPU 通常通过 NVLink/NVSwitch 互连，如何将 CXL NIC 池与 GPU 直连（如通过 CXL-GPU 桥接）是一个有价值的研究问题。
   - **KV Cache 共享**：LLM 推理中 KV cache 占用大量显存/内存，CXL 内存池的 pass-by-reference 语义天然适合跨实例 KV cache 共享（如 prefix caching、PagedAttention 的跨机共享）。
   - **MoE 路由的 NIC 负载均衡**：MoE 模型的 Expert Parallelism 导致 all-to-all 通信量高度不均衡，DRack 的 NIC 池+MPTCP 组合有可能缓解热点 expert 的通信瓶颈。

4. **最有价值的切入点**：将 DRack 的内存池化思想应用于 disaggregated serving 架构——在 prefill-decode 分离的 LLM serving 系统中，prefill 阶段计算密集而 NIC 空闲，decode 阶段需要频繁跨节点读取 KV cache。DRack 的 NIC 借用机制和 CXL.mem 直接访问语义可以有效加速 prefill 到 decode 的 KV cache 传输。

---

## 八、总结

DRack 提出了一种基于 CXL 的机架级资源解耦架构，通过将 NIC 和内存从主机边界解耦形成共享池，使闲置 NIC 可以被其他主机借用以加速跨机架通信。配合 DRAM Cache 隐藏 CXL 延迟和 MPTCP 均衡流量负载，DRack 在不增加硬件带宽的前提下，通信时间平均降低 37.3%，尾延迟降低 62.2%。其核心贡献在于揭示了"NIC 利用率低但跨机架流量大"的矛盾并提出了池化解决方案。主要局限在于原型规模极小（8 台 FPGA 主机）、基于模拟而非真实 CXL 硬件、且未充分讨论大规模部署下的故障隔离和多租户安全问题。
