# IMPRESS: An Importance-Informed Multi-Tier Prefix KV Storage System for Large Language Model Inference

**作者**：Weijian Chen, Shuibing He, Haoyang Qu, Ruidong Zhang, Siling Yang, Ping Chen (Zhejiang University); Yi Zheng, Baoxing Huai (Huawei Cloud); Gang Chen (Zhejiang University)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/chen-weijian-impress
**源文件**：[fast2025-chen-weijian-impress.pdf](../../papers/fast-2025/fast2025-chen-weijian-impress.pdf)

---

## 一、背景

现代 LLM 应用（如 RAG、多轮对话、few-shot prompting）通常在用户 query 前添加长上下文前缀以提升输出质量。这些前缀在不同请求间频繁重复，现有系统通过存储和复用前缀的 KV cache 来减少冗余计算，从而降低 Time-to-First-Token (TTFT)。

然而，当 GPU/CPU 内存不足以缓存所有前缀 KV 时，需要将 KV 存储到磁盘。从 SSD 加载 KV 到 GPU 的 I/O 延迟很难被计算隐藏，占总 TTFT 的 51%-98%，成为新的瓶颈。例如，OPT-30B 模型中一个 2,600 token 的前缀 KV 就需要 3.4GB 存储空间。

---

## 二、要解决的问题

1. **磁盘 I/O 成为 TTFT 瓶颈**：现有系统（如 AttentionStore）虽然将 KV 扩展到磁盘存储，但 SSD 到 GPU 的加载延迟无法被 query 计算有效隐藏，在高请求量或抢占式调度场景下尤为严重。

2. **现有 important token 识别方法 I/O 开销大**：要识别哪些 token 的 KV 是重要的，需要先将所有 prefix keys 加载到 GPU 计算 attention weights，这本身就产生了大量 I/O，抵消了选择性加载的收益。静态预标记方法又因为不同 query 对应的 important token 不同而导致精度下降。

3. **现有 chunk 存储和缓存策略未考虑 token 重要性**：KV 按连续 token 打包为 chunk 存储，导致读取 important KV 时不得不加载大量无关数据（读放大约 2.2×）。基于 recency/frequency 的缓存替换策略忽略了 chunk 内 important KV 的比例，导致 GPU cache 命中率低。

---

## 三、洞察与设计

**关键洞察**：同一 transformer 层内不同 attention head 的 important token index set 具有高度相似性（Jaccard similarity 平均超过 0.95），这种相似性在不同模型规模和不同 important token 选取比例下普遍存在。

基于此洞察，IMPRESS 设计了三层存储架构（GPU memory → CPU memory → Disk），核心思路是**只加载 important 的 prefix KV**，从根本上减少磁盘 I/O 量。系统包含两个关键组件：

1. **Similarity-Guided Important Token Identification (ITF)**：利用 head 间相似性，只加载 3 个 probe head 的 keys（而非所有 head），通过这少量 keys 计算 attention weights 识别 important token，再加载所有 head 中这些 token 的 KV。当 probe head 间相似度低于阈值时，回退到加载全部 keys。阈值基于随机选择的期望 Jaccard 值乘以系数 α=0.6 动态设定。

2. **Importance-Informed KV Management (PKM)**：
   - **KV Reordering**：定期（如每 10 分钟）异步地按 token 重要性对 chunk 内 KV 重排序，将 important KV 集中打包到更少的 chunk 中，减少读放大。通过在 radix tree 节点中添加 mapping list 维护原始 token 顺序，且限制重排序不跨 radix tree 节点。
   - **Score-Based Cache Management**：为每个 chunk 计算综合分数（access frequency × important KV ratio），优先将高分 chunk 缓存在 GPU memory，使用双 min-heap 管理 GPU/CPU 两级缓存的替换。

---

## 四、实现细节

- 基于 FlexGen 实现，因为其白盒模型实现便于修改 attention 层逻辑。
- 修改了 `mha` 函数实现 prefix KV 复用，利用 `attn_weight` 中的值评估 KV 重要性（采用 H2O 的方法：attention weight 矩阵每列的和作为 token importance）。
- 实现了 `PrefixKVLayer` 类存储重排序后的 KV 和 mapping list。
- 实现了 `TokenCache` 类支持 score-based 缓存策略。
- Probe head 固定选取每层前 3 个 head，相似度用三对 probe head 的平均 Jaccard index 衡量。
- KV reordering 的 mapping list 和 score-based cache 的 per-chunk score 额外空间开销小于 chunk 内存的 0.5%。Probe head keys 的冗余存储占总 KV 存储的 1.2%。

---

## 五、实验结果

**实验平台**：2× AMD EPYC 7763 (64 cores), 128GB DRAM, 1× NVIDIA A100 80GB, 1× 2TB Intel SSD (~5GB/s read), PCIe 4.0 ×16。

**模型**：OPT-6.7B, OPT-13B, OPT-30B; 额外验证了 Llama2-7B 和 Llama2-13B。

**数据集**：PIQA, RTE, COPA, OpenBookQA（前缀平均 4.8k-5.7k tokens）。

**基线**：ReComp（重算全部前缀）、AS-like（AttentionStore 重实现）、AS+H2O+LRU、AS+H2O+LFU。

| 指标 | IMPRESS 表现 |
|------|-------------|
| TTFT 降低 | 相比 SOTA 降低 1.2×-2.8× |
| I/O 时间降低 | 相比 SOTA 降低 1.5×-3.8× |
| 精度损失 | 平均仅 0.2%，最大不超过 1% |
| P99 尾延迟 | 在 RTE+OPT-30B 上为 2.95s（SOTA 为 5.9s） |
| GPU cache 命中率 | 从 68% 提升至 80% |
| Chunk 加载量 | KV reordering 平均减少 1.2× |

**各技术贡献占比（以 OPT-30B on RTE 为例）**：ITF 60%, KV Reordering 30%, Score-based Cache 10%。但在不同数据集/模型上比例差异大（如 OPT-13B on COPA：36%, 8%, 56%）。

Llama2 模型上也验证了 1.7×-2.7× 的 TTFT 加速。

---

## 六、批判性分析

1. **模型覆盖范围有限**：实验仅在 OPT 系列（6.7B-30B）和 Llama2（7B-13B）上验证，均为相对老旧且规模较小的模型。当前主流的 70B+ 模型以及使用 GQA/MQA 架构的模型（如 Llama3、Mistral）未被验证——GQA 中 head 数量大幅减少，可能显著影响 head 间相似性这一核心假设。

2. **数据集的代表性不足**：使用的四个 few-shot 评测数据集（PIQA、RTE 等）都是简短的多选题，前缀由人工拼接 few-shot examples 构成。这与真实生产环境中 RAG 检索的长文档前缀、多轮对话历史等场景差距较大。论文自己也承认缺乏开源的真实前缀复用数据集。

3. **FlexGen 作为基座的局限**：FlexGen 是一个面向单 GPU 离线推理的系统，不支持 continuous batching、tensor parallelism 等生产级特性。在 vLLM、TensorRT-LLM 等现代 serving 系统上的集成和性能表现完全未知。

4. **Important token 比例需要手动设定**：KV retention ratio（5%-50%）需要针对不同数据集手动选择（如 COPA 用 50%，其他用 25%），缺乏自动化方法。在生产环境中不同请求可能需要不同比例。

5. **Observation 的理论基础薄弱**：论文明确承认无法数学证明 head 间 important token 相似性在所有 LLM 和场景下成立，仅通过实验验证。对于为什么 OPT 的较深层相似性降低也缺乏深入分析。

6. **单 GPU 场景限制**：所有实验在单 A100 上进行，未讨论多 GPU 分布式推理场景下 IMPRESS 的表现和集成挑战。

7. **KV reordering 的异步执行频率（每 10 分钟）是经验值**，在请求模式快速变化的场景下可能不够及时，但论文未分析此参数的敏感性。

---

## 七、AI Infra / MLSys 视角

1. **核心 insight 对现代 KV cache 管理的启发**：head 间 important token 的高度相似性是一个有价值的发现。在当前 GQA/MQA 模型中，key/value head 已经被共享，这一观察可能以不同形式体现。值得在 Llama3、Qwen2 等 GQA 模型上系统性验证。

2. **与 prefill-decode disaggregation 的结合**：IMPRESS 专注 prefill 阶段的优化，天然适合与 DistServe、Splitwise 等 prefill-decode 分离架构结合。在 prefill 节点上部署 IMPRESS 的三层存储，可以在大规模服务中进一步降低 TTFT。

3. **与 KV cache offloading/compression 的协同**：IMPRESS 的 importance-aware 思路可与 KV quantization（如 KVQuant、KIVI）结合——对 important KV 保持高精度，对 unimportant KV 激进量化或直接丢弃，形成更精细的 KV cache 管理策略。

4. **可行的 follow-up 方向**：
   - 在 vLLM/SGLang 的 prefix caching 机制上实现 importance-aware 的选择性加载
   - 研究 GQA/MQA 架构下 probe head 策略的适配（head 数少时可能需要不同方法）
   - 将 importance score 作为 PagedAttention 中 page eviction 的信号
   - 探索在分布式 KV cache（如 Mooncake）中应用 importance-aware 的跨节点缓存策略

---

## 八、总结

IMPRESS 提出了一个三层（GPU/CPU/Disk）importance-aware 的 prefix KV 存储系统，通过利用 attention head 间 important token 的高度相似性实现低 I/O 开销的 important token 识别，结合 KV reordering 和 score-based cache management 减少磁盘读放大并提高缓存命中率。在 OPT 和 Llama2 模型上实现了最高 2.8× 的 TTFT 降低，精度损失不超过 0.2%。主要局限在于实验仅覆盖较小规模的旧模型、基于 FlexGen 而非生产级 serving 系统，且核心假设（head 间相似性）在 GQA/MQA 等现代架构上的适用性有待验证。
