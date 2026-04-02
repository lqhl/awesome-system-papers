# FLB: Fine-grained Load Balancing for Lossless Datacenter Networks

**作者**：Jinbin Hu (Central South University, HKUST, Changsha University of Science and Technology), Wenxue Li, Xiangzhou Liu, Junfeng Wang, Bowen Liu (HKUST), Ping Yin (Inspur), Jianxin Wang, Jiawei Huang (Central South University), Kai Chen (HKUST)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/hu-jinbin
**源文件**：[atc2025-hu-jinbin.pdf](../../papers/atc-2025/atc2025-hu-jinbin.pdf)

---

## 一、背景

RDMA over Converged Ethernet (RoCE) 配合 Priority Flow Control (PFC) 已广泛部署于生产数据中心（如 Microsoft Azure、Alibaba Cloud、Google Cloud），以实现低延迟、无损传输。现代数据中心通常在任意一对端主机之间提供多条并行传输路径，因此负载均衡（Load Balancing）对于充分利用网络带宽至关重要。

然而，PFC 的 PAUSE/RESUME 机制会引发 Head-of-Line (HoL) blocking 和拥塞扩散问题——当 PFC PAUSE 逐跳反向传播时，可能导致全局网络瘫痪，单个流的性能退化可达 10×。在此背景下，如何在 PFC-enabled 无损网络中实现高效的负载均衡成为一个关键且未被很好解决的问题。

---

## 二、要解决的问题

现有负载均衡方案（主要为有损网络设计）在 PFC-enabled 无损数据中心网络中存在三个核心问题：

1. **重路由不灵活，导致负载不均和链路利用率低**：RDMA 网络中硬件加速的数据传输和 rate shaper 使得包间间隔极小，flowlet gap 难以出现。因此 CONGA、LetFlow 等 flowlet-based 方案无法灵活重路由，导致流量无法从拥塞路径迁移到空闲路径。

2. **细粒度多路径分发扩大了 PFC HoL blocking 的影响范围**：当拥塞流被 spray 到多条路径上时，PFC PAUSE 会传播到所有路径，阻塞更多无辜流（victim flows）。实验表明，packet spraying 下所有约 340 条路径都会被 PAUSE，而 ECMP 下仅约 70 条。

3. **端到端拥塞控制无法根治**：DCQCN、TIMELY、Swift 等拥塞控制协议无法完全阻止 PFC 触发，尤其在 bursty 场景下（每条 burst 流持续不到 1 RTT，来不及被拥塞控制调节）。且拥塞控制的缓慢速率收敛还会进一步降低链路利用率。

---

## 三、洞察与设计

**关键洞察**：在 PFC-enabled 无损网络中，拥塞流和非拥塞流需要被区别对待——拥塞流应当被**聚合隔离**到最少路径上（而非分散到更多路径），从而限制 PFC PAUSE 的影响范围；非拥塞流则可以自由利用剩余的多条并行路径来最大化链路利用率。

基于这一洞察，FLB 包含两个核心模块：

1. **Rerouting Module（正常条件下）**：无需预设阈值的灵活重路由。FLB 在 packet 粒度上工作，通过比较相邻包的到达时间间隔与路径延迟差，判断是否可以安全切换路径而不引发乱序。只有当新路径的延迟差小于包间时间间隔时才切换，并选择延迟最小的可行路径。PFC PAUSE 或拥塞控制降速本身会增大包间间隔，从而自然地触发重路由。

2. **Isolation Module（拥塞发生时）**：当目的端交换机出口队列超过隔离阈值时，生成 Congestion Notification Message (CNM) 发送给源端边缘交换机。源端交换机识别拥塞流，将其聚合到最少数量的隔离路径上，同时将非拥塞流重路由到其余路径。隔离路径数量根据拥塞流的总收敛速率与单链路带宽的比值确定。

此外，FLB 设计了一个**最小化速率控制**机制：发送端以线速启动，收到拥塞 CNM 后直接按 C/n 速率发送（C 为线速，n 为拥塞流数），收到非拥塞 CNM 后立即恢复，避免了 DCQCN 等协议的缓慢迭代收敛过程。

---

## 四、实现细节

- **硬件平台**：基于 Wedge 100BF-32X 可编程交换机，使用 P4 编程语言实现
- **Ingress Pipeline**：包含多个 match-action table，处理隔离标志设置、流表查询、转发端口选择
- **队列长度监测**：由于 P4 硬件平台无法从 ingress 读取 egress 队列，通过 SRAM 计数器模拟（统计入队/出队包数）
- **流表结构**：每条流表项 80 bit（16-bit flow ID + 8-bit path ID + 8-bit aging metric + 48-bit MAC 地址），flow ID 通过 CRC16 哈希五元组生成
- **Aging 机制**：每个包到达时重置其流的 aging metric，定时器周期性递增，用于测量包间间隔（无需存储时间戳）
- **内存消耗**：Leaf-Spine 拓扑下仅需 0.1 MB SRAM；3-tier Fat-tree 下为 0.12 MB
- **资源占用**：100K 并发流下，FLB 的各项交换机资源占用均不超过 10%（如 Match Crossbar 5.82%，Gateway 9.56%，SRAM 4.12%）
- **部署策略**：FLB 仅部署在边缘交换机上，通过 XPath 等显式源路由技术实现端到端路径控制
- **隔离阈值优化**：理论推导出阈值范围 K ∈ [2d×C, Q_PFC/n − 2d×C×(n−1))，确保隔离在 PFC 触发前生效且不造成链路空闲
- **CNM 实现**：复用现有 QCN 机制，通过逐跳流表查找将 CNM 传播到源端边缘交换机

---

## 五、实验结果

### 测试平台

| 项目 | 配置 |
|------|------|
| 服务器 | 20 台 Dell PRECISION TOWER 5820，Intel Xeon W-2255 10 核，64GB 内存 |
| 网卡 | Mellanox ConnectX-5 100GbE NIC |
| 交换机 | 2 台 P4 可编程交换机，22MB 共享缓存，32 端口 |
| 链路 | 3 条并行 40Gbps 路径 |
| 软件 | DPDK 20.08, Ubuntu 20.04.1 |

### 小规模测试台结果（WebSearch 工作负载）

| 指标 | FLB vs ECMP+DCQCN | FLB vs LetFlow+DCQCN | FLB vs MP-RDMA |
|------|-------------------|----------------------|----------------|
| AFCT 降低 | 48% | 42% | 30% |
| 99th-ile FCT 降低 | 最高 88% | — | — |
| PFC PAUSE 率降低 | 最高 96% | — | — |
| 链路利用率提升 | 166% | 144% | 28% |

### 大规模 NS3 仿真结果（10 Leaf + 10 Spine, 300 hosts）

| 工作负载 | FLB+RC vs 最优基线 AFCT 降低 |
|---------|---------------------------|
| WebServer (0.8 load) | 18%–76% (vs 各基线) |
| CacheFollower (0.8 load) | 类似趋势 |
| DataMining (0.8 load) | 65% vs ECMP, 36% vs MP-RDMA, 29% vs Proteus+DCQCN |

### Incast 场景

- FLB+RC 的 goodput 几乎不随 server 数量（25→200）变化
- 相比 CONGA+DCQCN 提升最高 45% goodput，相比其他方案提升最高 27%

### 多层拓扑（12-pod Fat-tree, 36 equal-cost paths）

- 相比 LetFlow+DCQCN：PFC PAUSE 降低 71%，AFCT 降低 76%，99th-ile FCT 降低 81%
- 相比 MP-RDMA：AFCT 降低 32%，99th-ile FCT 降低 45%

---

## 六、批判性分析

1. **测试台规模与实际部署差距大**：小规模测试台仅 20 台服务器、3 条并行路径、40Gbps 链路。虽然补充了 NS3 仿真（300 hosts），但现实大规模数据中心（数万服务器、100/400Gbps 链路）的表现仍存疑。特别是流表 CRC16 哈希在大规模场景下的冲突率、隔离阈值在复杂流量模式下的鲁棒性均未充分验证。

2. **CNM 传播延迟的影响被低估**：FLB 的隔离机制依赖 CNM 在 PFC 触发前到达源端边缘交换机。论文假设的网络延迟较短（5µs 链路延迟），但在多层拓扑中 CNM 需要逐跳查表转发，实际传播延迟可能更长。论文的理论分析（Appendix A）使用了保守估计，但未展示 CNM 延迟增大后的性能退化曲线。

3. **单一拥塞控制基线组合**：虽然对比了多种 LB+CC 组合，但未与最新的 PFC 替代方案（如 SRNIC 的 lossy RDMA）进行深入对比。论文以"lossy fabric 尚未大规模部署"为由回避了这一比较，但趋势上 lossy RDMA 正在获得越来越多关注。

4. **隔离阈值的动态自适应能力存疑**：论文给出了静态范围的理论推导，但实际网络中流量模式持续变化。固定的保守阈值在低负载时可能过早隔离、在高负载时可能反应不够快。虽然实验（§4.2）展示了优化阈值优于固定 20%/30% 阈值，但场景相对简单。

5. **流表规模和 hash 冲突**：流表使用 CRC16 哈希（16-bit flow ID），仅支持 65536 个唯一流 ID。在大规模数据中心中并发流可达百万级别，hash 冲突会导致错误的隔离/重路由决策。论文未讨论这一可扩展性瓶颈。

---

## 七、AI Infra / MLSys 视角

1. **对分布式训练通信的启发**：大规模分布式训练（如 AllReduce、All-to-All）产生大量并发 RDMA 流，极易触发 PFC 并引起 HoL blocking。FLB 的拥塞流隔离思路可以直接应用于训练集群的网络层——将 straggler 流隔离到专用路径，避免其阻塞其他 worker 的通信。

2. **与 collective communication 的协同优化**：当前 NCCL 等集合通信库对底层网络路由几乎无感知。FLB 的 CNM 信息如果能暴露给上层（例如通知通信库某条路径拥塞），可以实现跨层优化——训练框架可据此调整 pipeline parallelism 的调度或 gradient compression 策略。

3. **MoE 推理中的 All-to-All 通信**：Mixture-of-Experts 模型推理阶段的 All-to-All 通信是典型的 incast + outcast 混合模式，FLB 在 incast 场景下的稳定 goodput 表现值得关注。可以研究 FLB 在 MoE expert parallelism 场景下对 token dispatching 延迟的影响。

4. **可操作的后续研究方向**：
   - 将 FLB 的隔离机制与 RDMA-aware job scheduler 结合，在训练任务调度层面感知网络拥塞状态
   - 研究在 400G/800G 链路速度下 FLB 的可扩展性，特别是 P4 pipeline 的时序约束
   - 探索 FLB + lossy RDMA 的混合方案，在支持 PFC 和不支持 PFC 的集群间提供统一的负载均衡策略

---

## 八、总结

FLB 针对 PFC-enabled 无损数据中心网络提出了一种 PFC-aware 的细粒度负载均衡方案，核心思想是"正常时灵活重路由、拥塞时隔离拥塞流"。通过无阈值的 packet 级重路由和基于 CNM 的拥塞流隔离，FLB 在不依赖复杂拥塞控制的情况下实现了高链路利用率和低 HoL blocking。P4 硬件实现验证了方案的可行性，资源开销可控（<10%）。主要局限在于测试规模有限、流表 hash 空间较小（16-bit），以及在超大规模部署和超高速链路下的表现尚未验证。
