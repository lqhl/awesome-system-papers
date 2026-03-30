# FuseLink: Enabling Efficient GPU Communication over Multiple NICs

## 论文基本信息

- **标题**: Enabling Efficient GPU Communication over Multiple NICs with FuseLink
- **作者**: Zhenghang Ren, Yuxuan Li, Zilong Wang 等（香港科技大学 lead），联合中科大、Meta、MIT、Peking University、HKUST
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/ren

## 研究背景与动机

分布式 ML 任务的性能受 GPU 通信带宽限制。为满足 GPU 间通信需求，现代 GPU 集群采用多 NIC 配置：每 server 安装多张 RDMA NIC（如 8×400 Gbps），同时通过 NVLink 在 server 内连接 GPU（如 8-lane NVLink 提供 Tbps 级别带宽）。

**现状**：现有系统采用静态 GPU-NIC 绑定——每 GPU 固定使用特定 PCIe 连接的 NIC。这在流量均衡的 ML 任务（如 3D parallel training）中表现良好，但**动态流量**的 ML 任务会导致：
- 某些 NIC 过载（bottleneck）
- 其他 NIC 空闲（资源浪费）

**三类动态流量 ML 任务的流量不均衡**：
1. **Disaggregated LLM Serving**：prefill/decode 相分离，请求大小和到达时间随机 → NIC 利用率仅 13%-53%
2. **Expert-Parallel MoE Training**：不同 expert 被激活的概率不同，all-to-all 通信流量差异大 → NIC 利用率 29%-65%
3. **DLRM（Deep Learning Recommendation Model）Training**：embedding lookup 体积因 GPU worker 而异 → NIC 利用率 59%-82%

**根本瓶颈**：PCIe topology 限制了 GPU 通过 indirect NIC 通信的带宽（需经过 PCIe root complex 或跨 NUMA）。

## 要解决的核心问题

**核心问题**：静态 GPU-NIC 绑定无法适应动态流量 ML 任务，导致 NIC 利用率低下和通信性能瓶颈。

**关键观察**：
- 动态流量 ML 任务中存在大量空闲 NIC 资源
- NVLink 提供高带宽的 server 内 GPU 间连接，可用于 relay
- GPU relay 配合智能调度可将流量引导到空闲 NIC

**核心挑战**：
1. Multi-NIC 传输受 PCIe 带宽限制（单 GPU PCIe 接口总带宽有限）
2. Indirect NIC（无直接 PCIe 连接）吞吐量次优
3. Relay GPU 的介入可能引入同步开销和竞争

## 主要贡献

1. **FuseLink 设计**：一种 GPU 通信框架，通过集成 server 内高速连接（NVLink）到 inter-server 网络，实现高效 multi-NIC 传输
2. **核心机制**：
   - 利用 NVLink 进行 relay，避免 indirect NIC 的 suboptimal PCIe 路径
   - Priority-based memory management 和网络请求调度避免对计算和通信任务的干扰
   - 高效的 traffic monitoring 和 scheduling 策略
3. **NCCL 集成**：FuseLink 作为独立网络层集成到 NCCL，使 ML 应用无缝受益无需修改代码
4. **端到端评估**：在真实 GPU 集群上评估，展示了显著的性能提升

## 研究方法与设计

### FuseLink 总体架构

```
GPU Server A                    GPU Server B
┌─────────────────────┐        ┌─────────────────────┐
│ GPU0 ←→ NIC0 (direct) │ ←────→ │ NIC0 ←→ GPU0       │
│ GPU0 ←→ GPU1 ←→ NIC1 │ ←────→ │ NIC1 ←→ GPU1 ←→ GPU0 │
│ GPU1 ←→ NIC1 (direct) │ ←────→ │ NIC1 ←→ GPU1       │
│ GPU2 ←→ GPU3 ←→ NIC2 │ ←────→ │ NIC2 ←→ GPU3 ←→ GPU2 │
└─────────────────────┘        └─────────────────────┘
```

### 设计目标

1. **Maximizing multi-NIC efficiency**：通过空闲 NIC 聚合带宽
2. **Avoiding contention and interruption**：不干扰正在进行的计算和通信任务
3. **Readily deployable**：适配现有硬件和 ML 框架

### 关键技术

#### 1. 高效 Relay（§4.1）

**问题**：Relay GPU 将数据转发到 indirect NIC 时，NVLink-to-PCIe 转换需要频繁 device 同步，严重拖慢数据路径。

**解法**：Active relay planning with memory remapping
- Relay 前先将数据 staging 到 relay GPU
- 利用 NVLink 的高带宽直接路由到最优 GPU
- 配合 zero-copy 传输减少同步开销

Table 2 显示 relay 优化（§4.1）使 inter-server 带宽从 49.27 GBps 提升到 78.39 GBps（1.59×）。

#### 2. 消除中断风险（§4.2）

**问题**：利用 relay GPU 和多个 NIC 会与正在进行的任务竞争内存和带宽资源。

**解法**：Priority-based memory management
- 在 relay GPU 上为 relay 流量分配专门的高优先级 buffer pool
- Relay 任务与计算任务共享 GPU 时，优先保证计算任务的内存配额

配合 network request scheduling 确保 relay 请求不会抢占正在进行的通信任务的资源。

#### 3. 减少 NIC 争用（§4.3）

**解法**：Multi-NIC transmission via efficient aggregation
- 利用 §4.1 的 relay 路径，聚合多个 indirect NIC 的带宽
- 在 relay GPU 侧通过精心规划的路径选择最小化 PCIe 争用

Table 2 显示此优化带来了最大的性能提升（从 76.37 到 178.59 GBps，3.62× vs baseline）。

#### 4. 高效调度（§4.4）

**问题**：动态调度 traffic 到 NIC 需要识别空闲 NIC 资源并高效调度，同时要考虑 contention 和 interruption 的避免。

**解法**：
- **Traffic monitoring**：实时监控 NIC 发送/接收负载状态（通过 RDMA 的 credit 机制）
- **Intelligent scheduling**：基于负载状态和拓扑信息，动态选择最优 NIC 和 relay 路径
- 将 relay planning 和 NIC selection 联合优化

Table 2 显示此优化使带宽达到 212.35 GBps（4.31× vs baseline）。

### 与现有 GPU 通信框架的对比

| 特性 | NCCL | 现有 GPU-NIC 绑定 | FuseLink |
|---|---|---|---|
| NIC 利用方式 | 仅 direct NIC | 静态绑定 | 动态聚合 |
| Relay 支持 | 无 | 无 | NVLink relay |
| 流量调度 | 静态 | 静态 | 动态 |
| Multi-NIC 聚合 | 无 | 部分（suboptimal PCIe） | 完整（通过 NVLink） |

## 关键实现细节

### RDMA Credit 机制利用

FuseLink 利用 RDMA 的 credit 机制来传递空闲 NIC 信息：
- Receiver 端的 credit 包含接收方可用 NIC 的负载状态
- Sender 端根据 credit 信息选择最优 NIC 发送数据
- Credit 更新是异步的，不阻塞主数据路径

### PCIe Topology 感知

FuseLink 在初始化时探测 server 内 PCIe topology：
- 识别 direct NIC（直接 PCIe 连接）
- 识别 indirect NIC（需 relay）
- 为每 GPU-NIC pair 选择最优路径

### NCCL 集成

FuseLink 作为独立网络层替换 NCCL 的默认网络实现：
- 保留 NCCL 的通信原语（all-reduce、broadcast 等）
- 在底层实现 FuseLink 的 multi-NIC 调度
- 应用无需修改代码

## 实验结果与分析

### 测试环境
- Nvidia Hopper GPUs（8-lane NVLink）
- 8×400 Gbps NICs per server
- 两 server 拓扑（模拟真实 ML 集群配置）

### 关键结果

#### Inter-Server GPU 带宽
- **Baseline（NCCL 静态绑定）**：49.27 GBps
- **FuseLink**：**212.35 GBps**（4.31× 提升）
- 超过了 8-lane NVLink 带宽（通过聚合多个 NIC 实现）

#### 端到端 ML 任务评估

1. **LLM Serving（TTFT）**：1.04–2.73× 改善
2. **MoE Training（throughput）**：1.3× 提升
3. **DLRM Training**：1.2× 提升

### 设计消融实验（Table 2）

| 优化阶段 | Bandwidth | Speedup |
|---|---|---|
| Baseline | 49.27 GBps | 1.0 |
| + Efficient relaying | 78.39 GBps | 1.59 |
| + Eliminate interruption | 76.37 GBps | 1.55 |
| + Reduce NIC contention | 178.59 GBps | 3.62 |
| + Scheduling efficiently | 212.35 GBps | 4.31 |

有趣的是，Eliminate interruption（§4.2）反而使性能略降（78.39→76.37），论文解释是因为 priority 机制引入了一定开销，但在更高负载下避免了更严重的性能降级。

### Traffic Imbalance 下的表现

在 MoE training 和 DLRM 的 traffic trace 下，FuseLink 持续优于 baseline 和 naive multi-NIC 策略。

## 潜在问题与局限性

1. **硬件依赖性强**：FuseLink 高度依赖 NVLink 的高带宽 relay 能力，对于没有 NVLink 的平台（如 AMD GPU clusters、CPU-only clusters）不适用
2. **仅评估了两 server 拓扑**：真实 ML 集群是多 server 环形或 torus 拓扑，FuseLink 在多跳跨 server 通信下的性能未经测试
3. **Credit 机制的开销**：RDMA credit 的传递是异步的，但仍需一定频率的更新；高并发下 credit 信息的陈旧可能导致次优调度决策
4. **Relay buffer 的内存开销**：FuseLink 需要在 relay GPU 上预留 dedicated buffer pool，这在 GPU 内存已高度紧张的 ML 训练场景中可能成为问题
5. **PCIe topology 探测的可靠性**：FuseLink 依赖初始化时的 PCIe topology 探测，但服务器重启、热插拔或 firmware 更新可能导致 topology 变化，论文未讨论容错机制
6. **与 GPUDirect RDMA 的交互**：现代 GPU 集群通常使用 GPUDirect RDMA 绕过 CPU 直接 GPU-NIC 传输，FuseLink 与 GPUDirect 的兼容性未评估
7. **跨多租户场景的隔离性**：多 tenant 环境中的 security/isolation 问题（一个 tenant 的 relay 流量是否会影响其他 tenant）未讨论

## 未来工作方向

1. 将 FuseLink 扩展到多 server 拓扑（ring/torus）
2. 探索与 GPUDirect RDMA 的集成
3. 自适应 topology 探测和变化处理
4. 在更大规模集群（64+ GPUs）上的评估

## 个人评注

### 优点

1. **问题切中实际**：动态流量 ML 任务（LLM serving、MoE、DLRM）是当前 AI 基础设施中最重要的工作负载，流量不均衡问题在实际部署中普遍存在
2. **设计有层次感**：从 relay 优化→中断消除→争用减少→智能调度的逐步深化，每个阶段都有明确的 motivation 和 ablation 验证
3. **与 NCCL 的深度集成**：保留 NCCL API 使现有 ML 应用零成本受益，是一个务实的设计决策
4. **实验数据充分**：Table 2 的消融实验清晰地展示了每个设计决策的贡献，从 49.27 GBps 到 212.35 GBps 的 4.31× 提升具有说服力

### 不足与可疑之处

1. **Inter-server 带宽"超过 NVLink"的说法需要澄清**：FuseLink 达到 212.35 GBps，超过了 8-lane NVLink 的带宽（通常约 300 GB/s per direction？）。但 NVLink 的实际双向带宽和 PCIe NIC 的实际可用带宽取决于具体配置，论文对此的解释不够清晰。212 GBps 是否在 PCIe 物理限制内？
2. **Relay 优化的数据有反向变化**：Table 2 中 +Eliminate interruption（§4.2）反而使带宽从 78.39 降到了 76.37 GBps，论文解释这是因为 overhead，但这一优化反而带来了轻微性能损失，其价值在什么场景下才能体现？论文没有清楚说明
3. **LLM Serving 的改善幅度波动大**：TTFT 改善从 1.04× 到 2.73×，波动范围超过 2.5 倍。对于追求稳定性的 production 系统，这个方差可能限制 FuseLink 的实际部署意愿
4. **端到端任务只测试了两个 server**：真实 LLM serving 和 MoE training 涉及数十到数百个 GPU servers，在多跳场景下 relay 路径会显著延长，可能引入不可忽视的延迟
5. **Credit 机制的信息陈旧问题**：Credit 的更新是异步的，但流量模式可能快速变化（如 burst of requests）。在高度动态场景下，陈旧的 credit 信息可能导致调度决策失误，论文对此的讨论不足
6. **论文数据与实际硬件规格的一致性**：Nvidia Hopper H100 的 NVLink 带宽约为 900 GB/s bidirectional，8-lane 配置下每 GPU 可用约 400 GB/s。但 PCIe Gen5 ×16 的带宽约为 128 GB/s，8×400 Gbps NIC 总带宽约 400 GB/s。这意味着 single GPU 通过 8 NIC 聚合确实可以超过单 GPU 的 PCIe 可用带宽，理论上 FuseLink 的设计是合理的
