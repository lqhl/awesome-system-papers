# MOONCAKE: Trading More Storage for Less Computation – A KVCache-centric Architecture for Serving LLM Chatbot

**作者**：Ruoyu Qin (Moonshot AI & Tsinghua University), Zheming Li, Weiran He, Jialei Cui (Moonshot AI), Feng Ren, Mingxing Zhang, Yongwei Wu, Weimin Zheng (Tsinghua University), Xinran Xu (Moonshot AI)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/qin
**源文件**：[[fast2025-qin.pdf]]

---

## 一、背景

随着 LLM 在对话、Agent、长文本等场景中的广泛应用，推理服务面临日益多样化的工作负载。作为 MaaS 提供商，Moonshot AI 的 Kimi 需要在满足严格的延迟 SLO（TTFT 和 TBT）的前提下，最大化有效吞吐量。

当前 GPU 集群以高度集成的 DGX/HGX 节点形式提供，但 prefill 和 decoding 两个阶段的计算特性差异显著：prefill 是计算密集的，decoding 是访存密集的。此外，GPU 节点上大量的 CPU、DRAM、SSD 和 NIC 资源在推理场景下利用率很低，存在明显的资源浪费。

与此同时，长上下文推理（从 8k 到 128k 甚至百万 token）的需求快速增长，使得 KV Cache 的管理和调度成为推理系统的核心瓶颈。

---

## 二、要解决的问题

1. **Prefill/Decoding 阶段耦合导致性能干扰**：传统系统（如 vLLM）将 prefill 和 decoding 耦合在同一实例上，长上下文的 prefill 会严重干扰 decoding 的 TBT SLO。chunked prefill 缓解了干扰，但难以同时最大化 prefill MFU 并满足 TBT SLO。

2. **本地缓存容量严重不足**：现有 prefix caching 方案（如 vLLM prefix caching、SGLang RadixAttention）仅利用本地 HBM 或 DRAM 做缓存。以 LLaMA3-70B 为例，单节点 1TB DRAM 仅能存储约 3M token 的 KV Cache，不到理论最大 cache hit rate 的 50%。

3. **长上下文 TTFT 优化困难**：对于 128k token 级别的长请求，单节点处理 TTFT 过高。Sequence Parallelism (SP) 方案需要频繁跨节点通信，降低 MFU 并与 KV Cache 传输竞争网络带宽。

4. **KV Cache 热点不均衡**：系统 prompt 等热门缓存被几乎所有请求访问，而长文档缓存可能只被单个用户使用，导致缓存访问严重不均衡。

---

## 三、洞察与设计

**关键洞察**：GPU 集群中 CPU、DRAM、SSD 和 RDMA NIC 等非 GPU 资源被严重低估利用，这些资源可以被池化为分布式 KV Cache，通过"用更多存储换更少计算"的策略，使全局缓存容量达到 PB 级别，从而大幅提高 prefix cache 命中率并减少冗余计算。数学分析表明，当传输带宽 B 满足 B/G > 2ds / (gqa × (apd + bd²)) 时，从远端加载 KV Cache 比重新计算更快——对 LLaMA3-70B + A800 集群，100Gbps 网络即可满足条件。

基于此洞察，MOONCAKE 设计了三层架构：

### MOONCAKE Store（分布式 KV Cache 池）
- 将所有 KV Cache 存储为 paged blocks（16~512 token/block），每个 block 附带 hash key 用于去重
- 热门 block 自动复制到多节点以降低访问延迟
- 采用 LRU 策略淘汰冷 block
- 提供 put/get/change_replica 等对象接口
- 底层实现了高性能 Transfer Engine：topology-aware path selection、endpoint pooling、故障自动切换

### Prefill Pool（chunked pipeline parallelism）
- 将 prefill 集群独立于 decoding 集群
- 创新性地采用 Chunked Pipeline Parallelism (CPP)：将长上下文输入分成 chunk，由流水线组内不同节点并行处理
- CPP 仅在 pipeline stage 边界通信（可与计算重叠），比 SP 消耗更少网络资源
- 自然适配长短上下文，无需频繁动态调整节点分配

### KVCache-centric Conductor（全局调度器）
- 为每个请求选择最优的 prefill + decoding 实例对
- Cache-aware 调度算法：综合考虑 prefix cache 命中长度、预估执行时间、排队时间和传输时间
- 启发式热点迁移：当请求被调度到非最优 cache 节点时，自动触发 KV Cache 跨节点复制，实现热点自动扩散
- 不满足 SLO 的请求主动拒绝（HTTP 429）

---

## 四、实现细节

### Transfer Engine
- 基于 RDMA 的零拷贝传输，支持 DRAM-to-DRAM 和 GPU Direct RDMA
- **Topology-aware path selection**：每个服务器启动时生成拓扑矩阵并广播，将 NIC 按 NUMA 亲和性分为 preferred/secondary 列表；传输时优先选择 preferred NIC，避免跨 NUMA/PCIe Switch 瓶颈
- 单次传输内部分片为 16KB 粒度，多片可走不同 NIC 路径，充分利用多 NIC 带宽
- **Endpoint pooling**：使用 SIEVE 算法管理连接池，按需建立连接，限制活跃连接数
- **故障处理**：NIC 不可用时自动切换到备选路径，支持检测 RDMA context / completion queue 故障

### KV Cache 管理
- Block size 根据模型大小和最优网络传输大小设定（实验中设为 256 token）
- Hash key = block 自身 hash + prefix hash，用于去重和匹配
- 支持多副本，由调度策略控制副本数量

### 调度实现
- Prefill 时间预测：使用多项式回归模型，基于离线测试数据拟合，利用 Transformer 计算的规律性实现高精度预测
- 排队时间 = 所有排队请求的 prefill 时间之和
- TTFT 计算 = transfer time + queue time + prefill time，所有实例的 TTFT 并行计算
- Cache load balancing 中的阈值目前手动调整

### 部署规模
- 运行在数千节点上，每日处理超过 1000 亿 token
- 网络配置：A800 节点配 4×200Gbps NIC，H800 节点配 4×400Gbps NIC

---

## 五、实验结果

### 实验配置
- 硬件：8×A800-SXM4-80GB GPU/节点，4×200Gbps RDMA NIC
- 模型：LLaMA3-70B dummy model
- 基线：vLLM v0.5.1（原版、prefix caching、chunked prefill 三种配置）
- 三种工作负载：Conversation、Tool&Agent、Synthetic（来自真实 Kimi 流量和公开数据集）

### 端到端有效请求容量（16 节点）

| 工作负载 | TBT 阈值 | vs vLLM 提升 |
|----------|----------|-------------|
| Conversation | 100ms | +498% |
| Conversation | 200ms | +157% |
| Conversation | 300ms | +59% |
| Tool&Agent | 100ms | +64% |
| Tool&Agent | 200ms | +42% |
| Synthetic | 200ms | +40% |

### Prefill GPU 时间对比

| 工作负载 | vs vLLM 减少 | vs vLLM Prefix Caching |
|----------|-------------|----------------------|
| Conversation | 36% | 1.43× |
| Tool&Agent | 53% | 1.40× |
| Synthetic | 64% | 2.59× |

### MOONCAKE Store 全局 vs 本地缓存

| 工作负载 | Cache Hit Rate 提升 | Prefill GPU 时间减少 |
|----------|-------------------|-------------------|
| Conversation | 1.38× | 24% |
| Tool&Agent | 2.36× | 48% |
| Synthetic | 2.22× | 26% |

### Transfer Engine 性能
- 40GB 数据传输（128k token for LLaMA3-70B）：
  - 4×200Gbps：87GB/s，比 TCP 快 2.4×
  - 8×400Gbps：190GB/s，比 TCP 快 4.6×

### P/D Ratio
- 最优 P/D 比约为 1:1，此时有效请求容量最高
- 实际部署中固定 P/D ratio，仅在负载显著波动时切换节点角色

### 生产环境收益
- A800 集群：比之前系统多处理 115% 请求
- H800 集群：比之前系统多处理 107% 请求

---

## 六、批判性分析

1. **实验基线偏弱且版本较旧**：基线使用 vLLM v0.5.1，且 prefix caching 和 chunked prefill 无法同时开启。后续版本的 vLLM 已大幅改进（支持两者共存、P/D disaggregation），论文中的对比优势可能被高估。

2. **dummy model 的局限性**：所有可复现实验使用 dummy LLaMA3-70B（无真实权重计算），这意味着实验中的 GPU 时间分布可能与真实推理存在偏差，特别是在 prefill 阶段的计算密度和 memory bandwidth 竞争方面。

3. **生产数据不可验证**：论文声称在 A800/H800 集群上分别提升 115%/107%，但这一数据基于与"之前的系统"对比，未披露对比基线的具体实现和配置，难以独立验证。

4. **CPP 的适用范围未充分讨论**：Chunked Pipeline Parallelism 在长上下文场景表现好，但论文未深入分析 pipeline bubble 的大小、不同 chunk size 对 MFU 的影响，以及与 SP 在不同请求长度分布下的交叉点。

5. **缓存淘汰策略过于简单**：使用 LRU 淘汰，但在多种工作负载混合的场景下（如 conversation + tool&agent），LRU 可能导致频繁抖动。论文提到 SIEVE 算法用于 endpoint 管理，但未将其应用于更关键的 KV Cache 淘汰。

6. **调度器的阈值手动调整**：cache load balancing 中的 kvcache_balancing_threshold 目前手动调整，论文承认可以自适应但未实现。这在实际大规模部署中可能带来运维负担。

7. **网络带宽假设较强**：系统推荐最低 100Gbps 网络带宽，并且实验中使用 4×200Gbps 或 8×400Gbps 配置。这一硬件要求在许多场景下并非标配，限制了方案的普适性。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴
- **"用存储换计算"的思路**具有普遍意义：不仅适用于推理的 KV Cache，也可以推广到训练中的 activation checkpointing、模型并行中的中间结果缓存等场景。核心是识别集群中的"闲置资源"并将其转化为性能优势。
- **Transfer Engine 的设计**（topology-aware、multi-NIC aggregation、故障自动恢复）是一个通用的高性能数据传输组件，已在 Moonshot 的 checkpoint 传输服务中复用，值得其他分布式 AI 系统借鉴。

### 可迁移的技术点
- **分布式 KV Cache pool + cache-aware scheduling**：可以迁移到多租户推理平台，不同用户/请求共享 KV Cache 减少冗余计算
- **Chunked Pipeline Parallelism (CPP)**：比 Sequence Parallelism 更适合推理场景的长上下文并行策略，网络开销更小且无需动态弹性调度
- **启发式热点迁移**：不需要准确预测未来缓存使用，而是通过调度时的"顺带复制"自然实现热点扩散，这种设计哲学适用于很多分布式缓存系统

### 值得跟进的方向
1. **KV Cache 压缩与分布式缓存结合**：论文提到 KV Cache compression 和 cache-friendly attention 是正交优化，这两者的结合（如量化后的 KV Cache 在分布式 pool 中的管理）是一个明确的研究点
2. **跨请求 KV Cache 共享的安全性和隔离性**：在多租户场景下，如何在共享 KV Cache 的同时保证数据隔离
3. **自适应 P/D ratio 和弹性调度**：论文中 P/D ratio 固定，结合工作负载预测实现动态调整是一个工程和算法的结合点
4. **与 MoE 模型的结合**：MoE 模型的 KV Cache 结构与 dense model 不同（如 DeepSeek-V2 的 MLA），分布式 KV Cache 在 MoE 场景下的优化策略有待探索

---

## 八、总结

MOONCAKE 是 Moonshot AI 为 Kimi 构建的 KV Cache 中心化分离式推理架构，通过将 GPU 集群中闲置的 CPU/DRAM/SSD/NIC 资源池化为分布式 KV Cache，实现了"用存储换计算"的策略。系统包含三个核心组件：MOONCAKE Store（分布式缓存池 + 高性能 RDMA 传输引擎）、CPP-based Prefill Pool（长上下文流水线并行）、以及 KVCache-centric Conductor（缓存感知全局调度）。在真实 Kimi 流量和公开数据集上，MOONCAKE 比 vLLM 最高提升 498% 的有效请求容量。该系统已在数千节点上投入生产，每日处理超千亿 token。主要局限在于对高带宽 RDMA 网络的依赖（推荐 ≥100Gbps）以及实验基线的时效性。
