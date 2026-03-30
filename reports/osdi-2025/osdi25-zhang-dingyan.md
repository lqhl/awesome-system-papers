# BLITZSCALE: Fast and Live Large Model Autoscaling with O(1) Host Caching

## 论文基本信息

- **标题**: BLITZSCALE: Fast and Live Large Model Autoscaling with O(1) Host Caching
- **作者**: Dingyan Zhang, Haotian Wang, Yang Liu, Xingda Wei, Yizhou Shan (Huawei Cloud), Rong Chen, Haibo Chen（上海交通大学 / 华为云）
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/zhang-dingyan

## 研究背景与动机

大语言模型（LLM）的推理即服务（Model-as-a-Service, MAAS）面临两个核心挑战：

1. **需求不可预测**：请求到达率在秒级内波动可达 5 倍（如 BurstGPT traces）
2. **模型参数巨大**：Llama3-8B 约 16GB，Qwen2.5-72B 约 144GB，单 GPU 无法容纳

传统自动扩缩容方案存在根本矛盾：
- **快速扩缩** 需要预缓存模型参数 → 内存消耗大
- **低内存占用** 依赖 SSD 按需加载 → 扩缩速度慢（Llama3-8B SSD 加载需 12.8 秒）

ServerlessLLM 等系统尝试用多级缓存（SSD → Host DRAM → GPU）加速，但 Host 缓存命中率仅 40-75%，因为 MAAS 平台同时服务数百个不同模型，无法在每台机器上缓存所有模型。

## 要解决的核心问题

如何在**不依赖缓存命中率**的前提下，实现 LLM 服务的**亚秒级自动扩缩容**？同时保持 O(1) 内存占用（无论服务多少模型）。

## 主要贡献

1. **数据平面加速**：利用 GPU-GPU/CPU 计算网络（100-400Gbps RDMA，甚至 16Tbps NVLink）传输模型参数，速度与 Host 缓存相当，但无需预缓存
2. **O(1) 主机缓存**：即使没有已部署实例，也可通过全局参数池广播，每个模型仅需 1 份缓存
3. **Live Scaling（活体扩缩）**：打破传统的"实例级"扩缩抽象，实现"层级别"细粒度扩缩，允许缩容实例在参数未完全加载时就开始服务部分请求
4. **无干扰的多播规划器**：在线生成高效的多播计划，避免扩缩流量与正常推理流量的网络干扰
5. **Zigzag 流水线调度**：在扩缩期间协调预填充和解码操作，50% 尾部延迟降低

## 研究方法与设计

### 关键洞察一：计算网络可用于扩缩

MAAS 系统的 GPU 间网络（RDMA 200Gbps，NVLink 16Tbps）用于推理数据传输，但**即使在重负载下也仅利用了不到 7.4%**。这一空闲带宽可用于加速参数加载。

### 关键洞察二：O(1) 主机缓存

通过全局参数池（Global Parameter Pool）：聚合所有机器的主机内存，足以缓存 MAAS 服务的所有模型。每个模型仅需在任意一台机器的 CPU 内存中保留一份，扩缩时直接通过计算网络多播。

### 关键洞察三：细粒度活体扩缩

打破"实例必须加载完所有参数才能服务请求"的约束。BLITZSCALE 将模型层分为两部分：
- **已加载层**：缩容实例执行计算
- **待加载层**：通过 Zigzag 流水线调度，缩容实例先执行部分层的计算，同时继续加载剩余参数

### 系统架构

```
Gateway → Load Monitor → Scale Planner → Global Parameter Manager
                                        ↓
                                  Live Execution Scheduler
                                        ↓
                              Model Executor (per GPU server)
```

**Scale Planner**：为每次扩缩生成多播计划，确定从哪些源（已部署实例或主机缓存）通过什么路径将参数传给目标实例。

**Live Execution Scheduler**：协调预填充和解码请求在已部署和缩容实例间的分配，使用 Zigzag 流水线最大化 GPU 利用率。

### 多播规划挑战

1. **在线规划**：源和目标随扩缩需求动态变化，需毫秒级决策
2. **干扰避免**：扩缩流量不能干扰正常推理的 KVCache 传输
3. **NP 难题**：一般多播规划在异构网络上已知 NP-hard

解决方案：利用模型服务中数据流的静态性（参数按固定顺序加载），设计一个**模型感知的多播规划器**，快速生成近最优、无干扰的计划。

## 关键实现细节

- **全局参数管理器**：维护模型→参数源的映射表（GPU 显存或 CPU 内存）
- **串行转发多播**：无论接收方数量如何，参数传输的边际成本接近零
- **Zigzag Pipeline**：交替执行已加载层的计算和待加载层的参数加载，50% 尾部延迟降低
- **支持 PD Disaggregation**：兼容预填充/解码分离的 LLM 服务架构

## 实验结果与分析

### 与 ServerlessLLM 对比（BurstGPT Trace）

| 指标 | ServerlessLLM | BLITZSCALE | 提升 |
|------|--------------|------------|------|
| TTFT（首 token 时间） | 基线 | 缩短 47-75% | ~2-4x |
| TBT（token 间时间） | 基线 | 缩短最高 94% | ~16x |
| GPU 时间节省（vs 无扩缩） | N/A | 减少 49% | — |

### 真实工作负载评估

在 AzureConv、AzureCode traces 上，使用 Llama3-8B、Mistral-24B、Qwen2.5-72B 模型：

- **TTFT**：比 ServerlessLLM 缩短 47-75%
- **TBT**：比 ServerlessLLM 缩短最高 94%
- **GPU 资源节省**：相比 DistServe/vLLM（不支持扩缩，按峰值负载预留）减少 49% GPU 使用

### 网络利用率分析

- 即使在重负载（DistServe PD 分离）下，计算网络仍有 40%+ 空闲带宽
- 加载 72B 模型（需要 576Gbps/GPU）超出典型 SSD（2-10Gbps/GPU）和 PCIe（256Gbps/GPU），但计算网络可以满足

## 潜在问题与局限性

1. **NVLink 依赖**：最优性能需要 NVLink，在纯 PCIe 环境下（如 A100 PCIe 版）收益可能受限
2. **粗粒度参数同步**：使用串行转发多播，若网络某链路故障，可能影响部分接收方
3. **Zigzag 调度的复杂性**：在层级别协调计算和通信，需要精细的调度器设计，部署复杂度高
4. **多播基础设施要求**：需要网络设备支持 RDMA 多播，在非 NVLink 环境下配置可能复杂
5. **72B 模型需要 4 GPU/实例**：论文坦承"172B 模型至少需要 4 GPU/实例"，小型部署可能不适用
6. **实验规模**：在单 DGX 节点测试，多节点集群上的网络干扰情况未充分验证

## 未来工作方向

- 探索自适应多播路径选择算法
- 与请求调度器联合优化
- 支持更多 LLM 架构变体（如 MoE）

## 个人评注

1. **核心洞察精准**：将"空闲的计算网络"用于"参数分发"是一个聪明的系统优化思路，既不增加内存压力也不损失性能。

2. **"O(1) 缓存"的表述有误导性**：严格来说，全局参数池中每个模型仍需一份缓存（分布在不同机器上），并非 O(1) 的绝对内存占用。更准确的表述是"O(1) per-model caching"或"无需逐实例缓存"。

3. **Live Scaling 的贡献可能被低估**：Zigzag 流水线调度是一个朴素但有效的想法——允许部分加载实例先工作，是实现真正"活体扩缩"的关键。

4. **实验完整性**：覆盖了多个模型、多个 traces，但主要对比了 ServerlessLLM，未与更多近期工作（如 Sentinel、ElasticLLM）对比。

5. **开源**：GitHub 开源，链接为 https://github.com/blitz-serving/blitz-scale，这是加分项，有利于复现和后续研究。

6. **轻微夸大**：摘要称"up to 94% lower tail latency reductions"，但这个数字是在特定配置（BurstGPT+Qwen2.5-72B）下达成的，在其他配置下提升幅度较小。
