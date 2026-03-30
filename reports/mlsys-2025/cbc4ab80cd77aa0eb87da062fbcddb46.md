# Seesaw: High-Throughput LLM Inference via Model Re-Sharding
## 论文信息
- **作者**: Qidong Su, Weihao, Xin Li, Muralidhar Andoorveedu, Chenhao Jiang, Zhanda Zhu, Kevin Song, Christina Giannoula, Gennady Pekhimenko
- **单位**: University of Toronto, Vector Institute, CentML Inc, Stanford
- **会议**: MLSys 2025
- **PDF**: cbc4ab80cd77aa0eb87da062fbcddb46.pdf
- **页数**: 14
- **链接**: https://github.com/mit-han-lab/omniserve

## 1. 研究背景与动机

大语言模型（LLM）已被广泛应用于交互式应用（如 ChatBot）和离线推理任务（如信息抽取、数据库查询、知识图谱处理）。离线推理任务以高吞吐量为优化目标，与交互式应用低延迟优先的目标形成鲜明对比。

LLM 推理分为 Prefill 阶段（处理输入 prompt 生成首个 token）和 Decoding 阶段（自回归逐 token 生成）。这两个阶段具有根本不同的计算特性：

- **Prefill 阶段**：多个输入 token 同时处理，计算和通信为主要瓶颈。Tensor parallelism 因 all-reduce 通信开销大，性能差于 Pipeline parallelism。
- **Decoding 阶段**：每次仅处理一个 token，权重加载开销占比高。Pipeline parallelism 因 micro-batch 导致重复加载权重，性能差于 Tensor parallelism。

因此，单一的静态并行策略无法同时优化 Prefill 和 Decoding 两个阶段的效率。

## 2. 研究问题与核心挑战

### 2.1 静态并行策略的根本局限

论文通过实验量化分析揭示：
- 在 Prefill 阶段，Tensor parallelism 的 all-reduce 通信开销随并行度增加而急剧上升（呈线性甚至超线性增长），导致其性能显著差于 Pipeline parallelism。
- 在 Decoding 阶段，Pipeline parallelism 将 batch 拆分为 micro-batch，导致每个 GPU 需要重复加载模型权重，权重加载开销显著增加，性能差于 Tensor parallelism。

### 2.2 分离式 Prefill-Decoding 的局限

Disaggregated prefill-decode（如 DistServe、Mooncake）将 Prefill 和 Decoding 分配到不同 GPU 实例。然而：
- 70B 模型在 8×40GB GPU 上的唯一分离策略（4 GPUs Prefill + 4 GPUs Decoding）导致 Prefill 吞吐量为 Decoding 的 6 倍以上，造成严重吞吐量不匹配。
- 分离式部署复制模型权重，造成与 Data parallelism 相似的缺陷（有限的 KV Cache 空间、增加的数据传输）。

### 2.3 动态重分片的开销

即使采用 model re-sharding 动态切换并行策略，频繁的 Prefill-Decoding 阶段切换也会引入大量开销：
- 模型权重需要重新加载
- KV Cache 需要重新分片
- 连续批处理（Continuous batching）下切换频繁

## 3. 主要贡献

1. **动态 Model Re-Sharding**：为 Prefill 和 Decoding 阶段分别选择最优的并行策略（Pipeline parallelism 用于 Prefill，Tensor parallelism 用于 Decoding），并在两阶段间动态切换。
2. **层级 KV Cache 缓冲（Tiered KV Cache Buffering）**：利用 CPU 内存作为 KV Cache 的辅助存储，使 Prefill 阶段可以连续计算大批量，无需等待 Decoding。
3. **Transition-Minimizing Scheduling**：仅在 CPU KV Cache 满或空时才触发阶段切换，将切换频率降到最低，同时保持 Decoding 阶段的最大 batch size。
4. **异步 Pipeline**：将 KV Cache 的 CPU-GPU 传输与计算重叠，最小化重分片开销。

## 4. 核心方法与设计

### 4.1 运行时建模

论文建立了每个阶段平均每个序列运行时间的数学模型：

$$T_{total} = \frac{T_{linear}^{dm}}{PP \cdot DP} + \frac{T_{attn}^{dm}}{PP \cdot DP} + T_{comp} + T_{comm}(TP)$$

关键洞察：
- $T_{comm}(TP)$ 随 TP 增加单调递增（all-reduce 带宽下降）
- Prefill 阶段 $T_{linear}^{dm}$ 可忽略，$T_{comm}$ 主导 → Pipeline/Data parallelism 更优
- Decoding 阶段 $T_{linear}^{dm}$ 占比高，$T_{comm}$ 较低 → Tensor parallelism 更优

### 4.2 层级 KV Cache 缓冲

```
Prefill 阶段: GPU 计算 → KV Cache offload 到 CPU 内存
Decoding 阶段: CPU KV Cache swap-in → GPU Decoding
```

CPU 内存作为所有 GPU 的共享 KV Cache 存储。Swap-out 在 Prefill 计算期间异步执行，Swap-in 在 Decoding 开始前预取。两级设计使：
- Prefill 可连续计算大批量，不受 GPU 内存约束
- Decoding 时每个 GPU 获取所需的 KV shard

### 4.3 Transition-Minimizing Scheduling

仅在以下条件满足时切换阶段：
- Prefill → Decoding：CPU KV Cache 满了（此时需要腾出空间）
- Decoding → Prefill：CPU KV Cache 完全转移到 GPU（继续 Prefill 有空间）

这确保了切换频率最小化，同时 Decoding 阶段始终以最大 batch size 运行。

### 4.4 数据布局优化

KV Cache 采用 HND（head, num_tokens, dim）布局而非 NHD，因为 Tensor parallelism 沿 head 维度分片，HND 布局保证内存访问连续性。

## 5. 实现细节

Seesaw 基于单调度器多 worker 架构构建：
- **调度器**：管理请求、组织 batch、发送指令
- **Worker**：每个 GPU 一个 worker，维护任务队列
- **共享内存 KV Cache**：通过 OS 共享内存在所有 GPU 间共享
- **异步预取器**：后台线程管理 KV Cache 的异步传输

## 6. 实验结果

**硬件**：A10/L4（AWS EC2，PCIe 连接），A100（PCIe 和 NVLink）
**模型**：LLaMA3-15B（4 GPUs），CodeLLaMA-34B（8 GPUs），LLaMA2-70B（8 GPUs）

### 6.1 端到端吞吐量

**A10（PCIe）**：
- Seesaw 相比 vLLM 最高达到 1.78× 加速，平均 1.36×
- ShareGPT 数据集（输入输出等长）：1.36-1.78×
- ArXiv Summarization（长输入短输出）：1.18-1.35×

**L4（PCIe）**：平均加速 1.29×，最高 1.52×

**A100 + NVLink**：仍实现 13-46% 的加速（相比 vLLM），因为即使 NVLink 带宽高，all-reduce 通信仍不可忽视

### 6.2 消融实验

- 仅用 Intra-layer 调度（无 Inter-layer）：平均 1.26× 加速
- 加上 Inter-layer 调度：再增加 1.08× 加速
- 说明两层调度协同有效

### 6.3 强扩展性

4 台机器（32 A100 GPUs）相比 1 台机器（8 A100 GPUs）达到 3.60× 加速，接近理想的 4× 线性扩展。

## 7. 潜在问题与局限性

1. **仅支持离线批处理场景**：Seesaw 专为高吞吐量离线任务设计，不适合延迟敏感的交互式场景。
2. **内存开销**：CPU 内存需要额外空间存储完整的 KV Cache，对 CPU 内存容量有较高要求（每 GPU 80GB）。
3. **不支持 TensorRT-LLM 比较**：论文未与 TensorRT-LLM 直接比较，仅与 vLLM 和 SGLang 比较。
4. **超参数敏感性**：切换策略（CPU KV Cache 满/空阈值）对性能有显著影响，需要针对硬件配置调优。
5. **Sequence Parallelism 未涵盖**：论文假设 Sequence Parallelism（SP）不适用，与 Long Context 场景存在一定脱节。

## 8. 未来工作

1. 探索稀疏模式与 model re-sharding 的结合
2. 研究与投机解码（speculative decoding）的联合优化
3. 将 Seesaw 与连续批处理更紧密集成
4. 扩展到更多并行策略（Sequence Parallelism、Expert Parallelism 等）

## 9. 个人评注

Seesaw 是一项扎实的 LLM 推理系统工程工作。其核心贡献——识别 Prefill 和 Decoding 对并行策略的不同偏好，并通过动态重分片实现阶段特定的优化——是一个简洁而重要的洞察。

论文最有价值的部分在于对 Tensor/Pipeline 并行策略在两个阶段性能差异的量化分析。这种"观察差异→建模分析→系统设计"的路径是 MLSys 论文的经典范式，且论文在每一步都做了充分的实验验证。

层级 KV Cache 缓冲的设计体现了良好的工程直觉：通过 CPU 内存作为桥梁，使 Prefill 和 Decoding 可以在不互相阻塞的情况下独立运行。这一设计的巧妙之处在于：不需要对 GPU 内存进行改造，仅利用 CPU 内存作为缓冲区即可实现阶段解耦。

但需要指出的是，Seesaw 与分离式 Prefill-Decoding（DistServe、Mooncake）的对比略显不公平——论文强调分离式方法的局限性（吞吐量不匹配），但这些方法的设计目标是交互式服务的低延迟，而非离线批处理的高吞吐量。两种方法针对的场景本就不同。

总体而言，对于需要在资源受限环境（特别是 PCIe 连接的低带宽 GPU 集群）上进行高吞吐量 LLM 推理的实践者，Seesaw 提供了有价值的参考。
