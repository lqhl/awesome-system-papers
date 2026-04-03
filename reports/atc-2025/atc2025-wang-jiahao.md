# KVCache Cache in the Wild: Characterizing and Optimizing KVCache Cache at a Large Cloud Provider

**作者**：Jiahao Wang, Jinbo Han, Xingda Wei, Sijie Shen, Dingyan Zhang, Chenguang Fang, Rong Chen, Wenyuan Yu, Haibo Chen（上海交通大学 & 阿里巴巴）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wang-jiahao
**源文件**：[[atc2025-wang-jiahao.pdf]]

---

## 一、背景

LLM 推理服务已成为云计算的核心工作负载。在 LLM 推理过程中，每次请求都需要计算 KV Cache（KV$），而当两个请求共享相同的输入前缀时，其 KV$ 是一致的，因此可以通过缓存 KV$ 来避免重复计算，降低延迟、提升吞吐。现有系统（如 vLLM、CachedAttention、Mooncake）已广泛采用 KV$ 缓存机制。

然而，KV$ 缓存策略的有效性高度依赖工作负载特征，而业界对真实生产环境中 KV$ 复用模式的理解仍然有限。此前的研究大多基于合成数据集（如 ShareGPT），缺乏时间戳、用户 ID、请求类型、多轮对话信息等关键维度，无法支撑精细化的缓存策略设计。

---

## 二、要解决的问题

1. **缺乏真实 workload 的 KV$ 复用特征刻画**：现有 trace 要么缺少时间戳（ShareGPT），要么缺少请求内容（Mooncake），无法全面分析 KV$ 的复用率、复用时间分布、生命周期等关键指标。
2. **缓存策略与工作负载脱节**：现有系统普遍采用 workload-agnostic 策略（如 LRU、FIFO），忽略了不同请求类型（API vs. Chat）、不同对话轮次之间 KV$ 复用特性的显著差异。
3. **对缓存容量需求缺乏量化依据**：部署 CPU-RDMA-SSD 多级缓存层次结构成本高昂，但缺少对 KV$ 生命周期和容量需求的系统性分析来指导容量规划。

---

## 三、洞察与设计

**关键洞察**：对于特定的请求类别（请求类型 + 对话轮次），KV$ 的复用时间遵循可预测的指数分布，且该分布在相似流量模式下保持稳定——这意味着可以利用历史数据拟合的概率分布来精确估计每个 KV$ block 未来被复用的概率。

论文基于阿里云（ALIYUN）的两个代表性生产 trace 进行了系统性刻画：

- **Trace A（to-C）**：面向消费者的 ChatBot 场景，以 Text 类型为主（78%），多轮对话比例 ~47%
- **Trace B（to-B）**：面向企业的 API 调用场景，100% API 请求，多轮比例极低（0.08%）

主要发现：

1. **单轮请求的 KV$ 复用同样重要**：在 to-B 工作负载中，单轮请求贡献了 97% 的缓存命中（通过共享 system prompt）
2. **复用分布高度倾斜**：10% 的 KV$ block 贡献了 77% 的复用
3. **跨用户复用极少**：大多数缓存命中来自同一用户的请求
4. **KV$ 生命周期短暂**：Trace B 中 P99 生命周期仅 97 秒；对于 GQA 模型，2× GPU HBM 的 CPU 缓存即可接近理想命中率
5. **每类请求的复用时间遵循指数分布**，且同一时段内分布稳定

基于以上发现，论文提出 workload-aware 缓存驱逐策略，核心思路：用拟合的指数分布计算每个 KV$ block 的未来复用概率作为优先级，同时考虑空间局部性（前缀位置）和短生命周期（用 lifespan 参数约束概率计算的时间窗口）。

---

## 四、实现细节

**优先级计算**：

```
Priority = (ReuseProb_w(t, life), -Offset)
```

- `ReuseProb_w(t, life)`：基于 workload w 的拟合指数分布 CDF，计算该 block 在 `[t, t+life)` 时间窗口内被复用的概率，其中 t 是距上次访问的时间
- `Offset`：block 在请求中的前缀位置，越靠前优先级越高（空间局部性）
- 不使用频率（Frequency）特征，因为 KV$ 生命周期短，高频访问的 block 可能很快"死亡"

**性能优化**：

- 同一 workload 内的 block 天然按 last access time 排序（指数分布的单调性），每个 workload 维护一个按时间排序的优先队列
- 驱逐时只需比较各 workload 队首元素，复杂度从 O(N) 降至 O(W)（W 为 workload 类别数，通常为数十个）
- 单次驱逐延迟约 79µs，仅占 vLLM 调度开销的 1.2%

**分布拟合**：后台周期性采样最近一小时的历史数据，为每个请求类别拟合指数分布参数。

**集成**：基于 vLLM 实现 CPU-GPU 两级 KV$ 缓存，并集成 Mooncake 的全局调度器（跨实例 KV$ 感知调度）。

---

## 五、实验结果

**测试环境**：8× NVIDIA A800-80GB GPU，NVLink 400GB/s，PCIe Gen4

**评估模型**：Qwen2-7B（1 GPU）、Llama2-13B（1 GPU）、Llama3-70B（4 GPU）

| 指标 | WA vs. 最佳 baseline | WA vs. 所有 baseline |
|------|------|------|
| Cache Hit Rate 提升 | +1.5%–3.9% | +8.1%–23.9% |
| QTTFT 降低 | 28.3%–41.9% | — |

关键结果：

- WA 在缓存容量有限时效果最显著，容量增大后优势减小
- 在 Trace A（workload 信息丰富）上效果优于 Trace B（>99% 为单轮 API，workload 区分度低）
- 消融实验：分布拟合（+1% hit rate）+ lifespan 约束（额外 +2.4% hit rate）
- LFU 表现最差，因为高频访问的 block 可能很快过期，污染缓存空间

**KV$ 容量需求**：

| 模型 | 注意力机制 | 理想缓存容量（相对 HBM） |
|------|------|------|
| Qwen2-7B | GQA | ~2× HBM |
| Llama3-70B | GQA | ~4× HBM |
| MHA 模型 | MHA | 显著更大 |

---

## 六、批判性分析

1. **Trace 覆盖时间太短**：仅一周的 trace 数据，且来自单一云厂商（阿里云）。作者声称 workload 具有代表性，但不同厂商、不同业务场景的分布可能有显著差异。例如 coding assistant、reasoning 模型等新型工作负载完全未覆盖。

2. **指数分布假设的鲁棒性存疑**：论文展示的拟合效果看起来不错，但只展示了少数几个请求类别的分布。当请求类别数量增多、每类样本变少时，拟合质量是否依然可靠？论文未讨论冷启动问题（新出现的请求类别如何处理）。

3. **性能改进的实际意义有限**：相比最佳 baseline（通常是 LRU），hit rate 仅提升 1.5%–3.9%。虽然 QTTFT 改进达 28%–41%，但这部分改进主要来自 CPU-GPU 两级缓存机制本身，而非驱逐策略的差异。论文未做 ablation 区分两者贡献。

4. **评估规模受限**：由于 GPU 资源不足，trace 被缩放以适配测试集群，这种缩放方法（引用 [51]）是否完整保留了 workload 的并发特征和缓存压力模式值得商榷。

5. **忽略了 reasoning 和 agent 类新型工作负载**：论文发表于 2025 年，但未覆盖 Chain-of-Thought reasoning、multi-step agent 等已在生产中大规模部署的工作负载。这些工作负载的 KV$ 复用模式可能与传统 Chat/API 有本质区别（如极长输出、工具调用穿插）。

6. **公平性问题被一笔带过**：论文承认恶意用户可以通过发送大量共享前缀的请求垄断缓存，但仅指出这是"正交问题"。对于生产系统而言，这是一个必须解决的实际问题。

---

## 七、AI Infra / MLSys 视角

**启发与借鉴**：

- **Workload-aware 设计思路具有通用性**：论文的核心方法论——先刻画真实 workload 特征，再设计针对性优化——适用于 AI Infra 的多个层面，如 GPU 显存管理、batch scheduling、prefill-decode 分离调度等。
- **KV$ 生命周期短且可预测**这一发现直接挑战了当前一些系统设计的假设。许多系统（如 Mooncake）投入大量精力建设 RDMA/SSD 多级存储层次，但对于 GQA 模型 + to-B 工作负载，GPU HBM + 少量 CPU 内存可能就够了。

**可迁移的技术思路**：

- 基于请求类别的概率分布拟合 → 可应用于 prefill/decode 调度中的请求优先级排序
- 空间局部性分析 → 可指导 partial KV$ 缓存策略（只缓存前缀部分即可获得大部分收益）

**值得跟进的方向**：

1. **Reasoning/Agent 工作负载的 KV$ 特征刻画**：论文明确承认未覆盖 reasoning 工作负载。Reasoning 模型的输出极长、输入相对固定，KV$ 的复用模式可能完全不同。
2. **Prefix caching 与 disaggregated serving 的协同优化**：在 prefill-decode 分离架构下，KV$ 的传输成本成为关键瓶颈，workload-aware 的传输调度策略是一个自然延伸。
3. **跨模型的 KV$ 复用**：论文聚焦单模型场景，但云上同一集群可能部署多个模型（如同一 base model 的不同 LoRA 变体），跨模型 KV$ 共享是一个有价值的研究问题。
4. **与 MLA/GLA 等新注意力机制的结合**：论文讨论了 GQA vs. MHA 的容量差异，但未涉及 DeepSeek-V2 的 MLA 等更激进的 KV$ 压缩方案对缓存策略的影响。

---

## 八、总结

本文对阿里云真实 LLM 推理 workload 的 KV Cache 复用特性进行了首次系统性刻画，揭示了多个此前基于合成数据未发现的关键特征：单轮请求复用的重要性、复用分布的可预测性、KV$ 生命周期的短暂性。基于这些发现，提出了 workload-aware 驱逐策略并集成到 vLLM 中，在有限缓存容量下取得了 1.5%–3.9% 的命中率提升和最高 41.4% 的 QTTFT 降低。论文的主要价值在于 trace 分析和特征刻画，为 KV$ 缓存系统的设计提供了实证依据；策略改进本身相对增量，且受限于单一厂商 trace 和传统工作负载类型。
