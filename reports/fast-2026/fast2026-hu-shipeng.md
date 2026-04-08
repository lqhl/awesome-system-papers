# Bidaw: Enhancing Key-Value Caching for Interactive LLM Serving via Bidirectional Computation–Storage Awareness

**作者**：Shipeng Hu, Guangyan Zhang (Tsinghua University), Yuqi Zhou (China University of Geosciences Beijing), Yaya Wei, Ziyan Zhong (China Telecom Omni-channel Operation Center), Jike Chen (Tsinghua University)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/hu-shipeng
**源文件**：[[fast2026-hu-shipeng.pdf]]

---

## 一、背景

在交互式 LLM 服务（如虚拟伴侣 Replika、语言学习 Duolingo、智能客服等）中，LLM 与用户进行多轮对话，每轮生成回答都需要加载之前所有轮次的 KV tensor。由于 GPU 显存有限，历史 KV 在每轮计算完成后通常会从 GPU 中删除，若不缓存则需重复计算——在平均 22.4 轮的对话中，冗余计算可占总计算量的 93.1%。

为避免冗余计算，现有工作（CachedAttention、FlashGen）将历史 KV 缓存在由 host memory（性能层）和 SSD（容量层）组成的两级存储系统中。但这种方案面临严重的性能瓶颈：与理想情况（所有 KV 均从 host memory 加载）相比，现有方案的响应延迟最高增加 3.8×，吞吐量最高下降 2.0×。

---

## 二、要解决的问题

现有两级存储 KV 缓存方案的核心问题是**计算引擎与两级存储相互不感知**，导致两个具体问题：

1. **I/O 导致的请求阻塞**：计算引擎在调度请求时不考虑 KV 加载延迟的巨大差异（来自不同存储层的带宽差距和 KV 大小差异，变异系数 >90%）。当一个 KV 加载时间长的请求被调度时，后续加载快的请求也被阻塞等待。

2. **性能层命中率低**：两级存储在驱逐 KV 时只依赖自身的历史访问信息，不利用计算引擎侧的用户对话模式。由于交互式对话的间歇性访问特征，KV 访问的时间局部性很差（80% 的加权重用距离超过性能层容量），导致现有驱逐策略（LRU、FIFO、queue-enhanced）的命中率仅约 20%。

---

## 三、洞察与设计

**关键洞察**：在交互式 LLM 服务中，某个用户下一次 KV 访问的加权重用距离下界与该用户上一轮模型回答的长度呈强正相关（Spearman 系数 0.94–0.98）。这是因为更长的模型回答需要用户花更多时间阅读/理解并构思下一个问题，期间其他用户的请求会插入，从而增大加权重用距离。

基于计算引擎与存储系统之间的双向感知，Bidaw 设计了两个核心机制：

### 计算引擎侧：I/O 感知的请求调度

- **双队列分离**：将请求分为 "ready queue"（KV 在性能层）和 "preparing queue"（KV 在容量层），GPU 只从 ready queue 调度，避免慢 I/O 阻塞快请求。
- **disk-HRRN 策略**：在 preparing queue 中按 response ratio = 1 + waiting_time / KV_size 排序，优先加载小 KV 请求以快速进入 ready queue，同时通过等待时间机制防止大 KV 请求饥饿。
- 从 preparing queue 提升到 ready queue 的请求按**原始到达时间**插入，避免尾延迟恶化。

### 存储侧：基于上一轮回答的驱逐策略

- 利用上述洞察，根据模型回答长度预测每个用户下次 KV 访问的加权重用距离下界。
- 将加权重用距离划分为三个区间：small（<性能层大小，命中率 1.0）、promising（有命中潜力）、extreme（命中率 0.0）。
- 通过 ghost cache（模拟 Belady 最优策略）估算各 promising 分桶的命中率，结合用户历史访问分布和下界预测，计算每个用户的 overall hit potential，驱逐 hit potential 最低的 KV。

---

## 四、实现细节

- **存储高效 tensor 缓存**：对 MHA 模型，分析 GPU 推理过程中各中间 tensor 的「节省计算量/存储开销」比（cost efficiency），发现 tensor 6（normalized activation，只需一步即可转为 KV）的 cost efficiency 最高（51.0 vs KV tensor 的 30.5），因此缓存该 tensor 代替 KV tensor。对 GQA 模型，KV 本身已较小，直接缓存 KV 更优。
- **混合粒度 GPU 内存分配**：为历史 KV 和用户 query 分配大块（256 tokens），为输出 token 分配小块（16 tokens），充分利用 CPU-GPU 传输带宽，同时避免碎片化。
- **低优先级 CUDA stream**：storage-efficient tensor 到 KV 的转换在单独的低优先级 CUDA stream 上执行，利用空闲 SM（>30% 空闲），不影响正常推理。
- **Inclusive caching**：性能层数据在容量层维护副本，驱逐时无需写回。
- 基于 vLLM 实现，采用 continuous batching。

---

## 五、实验结果

**实验环境**：1× A800 80GB GPU，200GB host memory，RAID-5 SSD（1.5 GB/s），PCIe Gen4。

**模型**：OPT-6.7B、Qwen-7B、OPT-13B、Qwen-14B、OPT-30B。

**工作负载**：自有交互对话工作负载（百万轮级别，平均 22.4 轮/用户）+ 公开 ShareGPT。

| 指标 | 结果 |
|------|------|
| 响应延迟降低 | 最高 3.58×（vs FlashGen，OPT-13B） |
| 吞吐量提升 | 1.43×–1.83×（不同模型） |
| 性能层 miss rate 降低 | 最高 57.6%（vs queue-enhanced）、69.9%（vs LRU/FIFO） |
| 请求排队时间 | 平均 2.45s vs 5.76s（FCFS），降低 57.5% |
| P90/P95/P99 尾延迟 | 分别降低 52.96%/49.30%/47.03%（vs CachedAttention） |
| ShareGPT 公开负载 | 吞吐量提升 1.40×，延迟降低最高 56.9% |
| 调度开销 | 平均 0.62ms/次 |
| 驱逐开销 | 平均 0.35ms/次 |
| Tensor 转换开销 | 数十毫秒，可忽略 |

**消融实验**（OPT-30B）：I/O 感知调度降低延迟 1.58×；加驱逐策略提升吞吐 1.25×；加 storage-efficient tensor 再提升 1.10×。

---

## 六、批判性分析

1. **工作负载代表性存疑**：核心实验基于未公开的自有交互对话工作负载（平均 query 36 tokens、response 45 tokens），这是非常短的对话场景。在 ShareGPT 上效果明显下降（吞吐提升从 1.83× 降至 1.40×），论文承认是因为模拟时间戳导致 previous-answer-based 驱逐失效。但这恰好说明该驱逐策略**依赖真实时间戳**，在缺乏精确时间信息的场景下价值有限。

2. **关键洞察的适用范围**："回答越长→重用距离越大"的相关性建立在用户需要「阅读/理解回答」的假设上。在 API 调用场景（agent-to-agent、自动化 pipeline）中，用户侧无思考时间，该洞察不成立。论文虽提到目标是 interactive serving，但未充分讨论这一边界条件。

3. **实验规模受限**：全部实验在单 GPU 服务器上进行，模型最大仅 OPT-30B。当前主流部署多为多 GPU 甚至多节点，tensor parallelism 下 KV 的存储和加载模式会显著不同。论文未讨论扩展性。

4. **SSD 带宽假设偏低**：实验使用 SATA SSD RAID-5（1.5 GB/s），远低于现代 NVMe SSD（单盘 7 GB/s+）。虽然论文补充了 5 GB/s 模拟实验表明仍有效，但随着存储带宽继续提升，两层间的带宽差距缩小，Bidaw 的调度优势会递减。

5. **Storage-efficient tensor 优化的通用性**：该优化仅适用于 MHA 模型，对 GQA 模型（当前主流：Llama 3、Qwen2 等）无效。论文将此作为一项核心技术贡献，但实际适用面有限。

6. **基线实现公平性**：CachedAttention 和 FlashGen 均为闭源，论文自行复现。复现质量直接影响比较结果的可信度，但论文未提供验证复现正确性的证据。

---

## 七、AI Infra / MLSys 视角

1. **计算与存储协同设计的范式价值**：Bidaw 的核心思路——让计算引擎和存储系统双向感知——在 AI Infra 中有广泛适用性。当前 disaggregated serving（如 DistServe、Splitwise）中 prefill 和 decode 节点之间的 KV 传输同样面临调度与缓存协同问题，可借鉴双队列分离和 I/O 感知调度的思路。

2. **利用 LLM 输出预测访问模式**：这是一个有意思的 cross-layer 设计点。在更广泛的场景中，可以利用 LLM 的输出特征（长度、内容类型、置信度）来预测后续的系统行为，如 prefetch、资源分配等。

3. **可迁移的研究方向**：
   - 将 I/O 感知调度扩展到分布式 KV cache（如 Mooncake 的 RDMA memory pool），在异构网络延迟下做请求路由
   - 在 agent/multi-turn RAG 场景中，对话模式更复杂（含工具调用、长时间等待），驱逐策略需要更丰富的信号
   - Storage-efficient tensor 的思路可推广到 checkpoint、migration 等场景：不一定要存完整 KV，存更紧凑的中间表示即可

4. **局限性**：当前 LLM serving 趋势是 GQA + 长上下文 + disaggregated architecture，Bidaw 的 MHA tensor 优化和单机两级存储架构与主流方向有偏差。最有价值的切入点是将双向感知的设计理念迁移到 disaggregated memory pool 场景。

---

## 八、总结

Bidaw 通过在计算引擎和两级存储之间建立双向感知，系统性地解决了交互式 LLM 服务中 KV 加载的两大瓶颈：I/O 导致的请求阻塞和性能层低命中率。其 I/O 感知调度（双队列 + disk-HRRN）和基于模型回答长度的驱逐策略设计简洁有效，在自有工作负载上实现了最高 3.58× 延迟降低和 1.83× 吞吐提升。主要局限在于核心洞察强依赖交互式场景的真实时间戳、storage-efficient tensor 优化不适用于 GQA 模型、以及单 GPU 实验规模对多机部署的代表性不足。
