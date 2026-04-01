# ZEN: Empowering Distributed Training with Sparsity-driven Data Synchronization

**作者**：Zhuang Wang (Rice University), Zhaozhuo Xu (Stevens Institute of Technology), Jingyi Xi (unaffiliated), Yuke Wang, Anshumali Shrivastava, T. S. Eugene Ng (Rice University)
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/osdi25/presentation/wang-zhuang
**源文件**：[osdi25-wang-zhuang.pdf](../../papers/osdi-2025/osdi25-wang-zhuang.pdf)

---

## 一、背景

分布式训练是大规模深度学习模型训练的标准范式，需要多个 GPU 之间同步梯度张量。随着 GPU 计算能力的快速提升，梯度同步的频率增加，通信成为主要瓶颈。然而网络带宽的增长远未跟上计算能力的提升，计算与通信之间的矛盾日益加剧。

深度学习模型中广泛存在高度稀疏的梯度张量——例如推荐模型 DLRM 的 embedding table 稀疏度超过 93%，GNN 的邻接矩阵稀疏度超过 99%，NLP 模型的 word embedding 稀疏度超过 97%。此外，gradient compression 算法（如 DGC）通过只选择 top-k 梯度也会引入人工稀疏性。利用这种稀疏性可以显著减少同步流量，但现有方案未能充分挖掘这一潜力。

---

## 二、要解决的问题

1. **缺乏对稀疏张量同步的系统性设计空间探索**：现有方案（AGsparse、SparCML、OmniReduce）各自在不同维度上做了设计选择，但没有系统分析什么是最优方案。

2. **负载不均衡**：稀疏张量中非零梯度的分布高度偏斜（skewed），简单的均匀分区会导致严重的通信不平衡。例如将张量均分为 128 个分区时，某些模型超过 50% 的非零梯度集中在同一分区。

3. **索引开销过大**：使用 COO 格式表示稀疏张量时，每个非零梯度需附带一个索引，导致通信量翻倍。现有稀疏格式（COO、tensor block、bitmap）在不同密度下均有明显不足。

4. **数据依赖的负载均衡方案成本过高**：理想的负载均衡需要分析所有 worker 的索引分布，但这种 data-dependent 方案的计算开销比迭代时间高出数个量级，不可行。

---

## 三、洞察与设计

**关键洞察**：稀疏张量在聚合后会显著变密（densification），且不同 GPU 上同一张量的非零梯度存在部分重叠（partial overlap）。在实际分布式训练中，Balanced Parallelism（Point-to-point + Incremental aggregation + Parallelism + Balanced communication）几乎总是优于 Hierarchical Centralization，因为增量聚合能有效利用重叠来减少冗余流量，而均衡的并行分区避免了通信热点。

基于此洞察，ZEN 的核心设计包含三个层次：

1. **最优同步方案选择**：论文提出四个正交设计维度（communication、aggregation、partition、balance），构建完整设计空间，证明最优方案必为 Balanced Parallelism 或 Hierarchical Centralization 之一。运行时根据稀疏度 profiling 结果比较两者的理论通信时间公式，自动选择最优方案。

2. **Data-independent Hierarchical Hashing**：使用两级哈希实现负载均衡——第一级哈希（h₀）决定每个索引属于哪个分区（保证跨 GPU 一致性），第二级哈希决定分区内的存储位置。结合四项技术：communication-oriented memory management、multiple hash functions for rehash、consistent hierarchical hashing、lock-free read-after-write，实现 GPU 上高效并行计算且无信息损失。

3. **Hash Bitmap 编码**：针对 Pull 阶段设计新的稀疏格式。由于 h₀ 已将索引空间确定性地划分到各 server，每个 server 只需对其局部索引集 I_i 构建 bitmap，总 bitmap 大小恒为 |G|/32（不随 server 数量线性增长），大幅降低索引传输开销。

---

## 四、实现细节

- 约 900 行 Python + 250 行 CUDA + 500 行 ColossalAI hack 代码
- 哈希函数使用 MurmurHash，不同 seed 生成不同哈希函数，训练开始时广播 seed 确保一致性
- Hierarchical hashing 算法参数：k=3（rehash 轮数），r₁=2|G|d_G（parallel memory），r₂=r₁/10（serial memory）
- GPU 内使用 NVLink + ReduceScatter/AllGather 同步 dense 张量；跨机使用 ZEN 的稀疏同步
- 梯度张量在 DDP 中先融合为 128MB 的 bucket 再应用 DGC 和 ZEN
- 通过 PyTorch DDP 的 custom_comm_hook 接口集成
- Hash bitmap 的索引集 I_i 离线计算并排序，在 h₀ 不变时可复用
- Imbalance ratio 理论保证：Push 和 Pull 的不平衡度均为 1+Θ(√(n·log n / (|G|·d_G)))，实际始终 < 1.1
- 内存开销 < 150MB（< 1% GPU 显存）

---

## 五、实验结果

**实验环境**：
- 16 台 AWS EC2 p3.16xlarge（8×V100 16GB，NVLink，25Gbps 网络）
- 16 台 AWS EC2 p3dn.24xlarge（8×V100 32GB，NVLink，100Gbps RDMA/EFA）

**Workloads**：
- 自然稀疏模型：LSTM、DeepFM、NMT
- 梯度压缩模型（DGC top-5%）：Llama3.2-3B、OPT-2.7B、Gemma2-2B（TP=8）

**Baselines**：AllReduce、AGsparse、SparCML、OmniReduce

| 场景 | 最佳 baseline | ZEN vs 最佳 baseline | ZEN vs AllReduce |
|------|-------------|---------------------|-----------------|
| LSTM (25Gbps, 16机) | SparCML | 1.67× | 3.1× |
| DeepFM (25Gbps, 16机) | OmniReduce | 1.44× | — |
| NMT (25Gbps, 16机) | OmniReduce | 1.51× | — |
| LSTM (100Gbps) | SparCML | 1.44× | — |
| DeepFM (100Gbps) | OmniReduce | 1.25× | 1.33× |
| NMT (100Gbps) | OmniReduce | 1.32× | 1.38× |
| Llama3.2-3B (25Gbps) | OmniReduce | 1.68× | 2.02× |
| OPT-2.7B (25Gbps) | OmniReduce | 1.66× | 2.10× |
| Gemma2-2B (25Gbps) | OmniReduce | 1.61× | 2.04× |
| Llama3.2-3B (100Gbps) | OmniReduce | 1.32× | 1.64× |

**通信加速**（25Gbps，16机）：
- LSTM：6.77× over AllReduce，5.16× over OmniReduce
- Gemma2-2B：3.51× over AllReduce

**其他关键结果**：
- 模型精度：自然稀疏场景下与 AllReduce 完全一致；梯度压缩场景下与 AGsparse 迭代级 loss 曲线一致
- Hashing 计算开销约 6ms，对比 25Gbps 下 270ms 的通信节省可忽略；100Gbps 下仅占通信节省的 9%
- Hash bitmap 在 Algorithm 1 基础上额外提升 13%-34% 的通信加速

---

## 六、批判性分析

1. **实验硬件偏旧**：全部实验使用 V100 GPU 和 25/100Gbps 网络。当前主流训练集群已使用 A100/H100 配合 400/800Gbps InfiniBand/RoCE，计算-通信比显著不同。在高带宽网络下，通信瓶颈可能不再突出，ZEN 的收益需重新评估。论文虽在 100Gbps 下做了部分实验，但远不是当前 SOTA 硬件水平。

2. **自然稀疏模型的代表性有限**：LSTM、DeepFM、NMT 都是相对小型且老旧的模型。论文声称聚焦 embedding 层的自然稀疏性，但当前主流 LLM 训练中 embedding 层的通信占比极小。真正的通信瓶颈在于 dense 的注意力/MLP 梯度——ZEN 对此无能为力。

3. **LLM 实验规模不足且场景受限**：LLM 实验仅使用 2-3B 模型、TP=8 + DP 的混合并行，batch size per TP group 仅为 1。实际 LLM 预训练使用更大的 batch size 和更高的 TP degree，DGC 等 gradient compression 方案在 LLM 预训练中几乎不被使用（因为会影响收敛）。论文选择的 workload 存在 cherry-picking 嫌疑。

4. **Balanced Parallelism 最优性的条件被弱化**：Theorem 1 的证明假设每个节点只有一个 GPU、节点间全互联。实际集群中节点内有 8 GPU（通过 NVLink 连接）、节点间网络拓扑可能非全连接。论文在实现中确实区分了 intra-node 和 inter-node，但理论最优性与实际部署之间的 gap 未被充分讨论。

5. **对 NCCL 的对比不够公平**：ZEN 实现在 ColossalAI 之上，而 AllReduce baseline 使用的是 NCCL。NCCL 高度优化了 kernel fusion、pipelining 等细节。单纯比较"通信时间"时，ZEN 的 CUDA kernel 实现质量与 NCCL 的优化水平差距未被讨论。

6. **Hash bitmap 的适用范围窄**：Hash bitmap 仅在 Pull 阶段有效，且其优势取决于 h₀ 产生的均匀分区。当密度极高时（聚合后 > 50%），稀疏同步本身的意义就很有限。

---

## 七、AI Infra / MLSys 视角

1. **稀疏通信的系统性分析框架有价值**：论文提出的四维设计空间（communication × aggregation × partition × balance）为稀疏通信方案的比较和分析提供了统一框架。这种方法论可以推广到其他通信场景（如 MoE 的 all-to-all、KV cache 的分布式传输）。

2. **Hierarchical hashing 技术可迁移**：Data-independent 的 hierarchical hashing 在 GPU 上实现无损负载均衡的技术，可以应用于：
   - MoE 模型中 expert 间的 token routing 均衡
   - 分布式推理中 KV cache 的 hash-based sharding
   - Embedding table 的分布式 lookup 负载均衡

3. **值得跟进的 Future Work**：
   - **高带宽网络下的验证**：在 800Gbps InfiniBand + H100/B200 集群上验证 ZEN 的实际收益
   - **与 quantized communication 的结合**：DGC 只是梯度压缩的一种，结合量化（1-bit Adam、FP8 通信等）可能进一步减少通信量
   - **MoE 训练中的应用**：MoE 模型的 all-to-all 通信天然存在负载不均衡问题，ZEN 的 hashing 方案可能有用
   - **稀疏 attention 的分布式通信**：随着稀疏 attention 机制（如 Native Sparse Attention）的发展，稀疏通信优化的需求可能重新增长

4. **最有价值的切入点**：将 ZEN 的 hierarchical hashing + hash bitmap 技术适配到 MoE 模型的 expert parallelism 场景。MoE 的 all-to-all 通信具有类似的负载不均衡问题（热门 expert 接收更多 token），且 token routing 的稀疏模式天然适合 hash-based 方案。

---

## 八、总结

ZEN 是一个面向稀疏梯度同步的分布式训练通信优化系统。其核心贡献在于：(1) 系统性地探索了稀疏张量同步的设计空间，证明了 Balanced Parallelism 和 Hierarchical Centralization 是两种最优方案；(2) 提出了 data-independent 的 hierarchical hashing 算法在 GPU 上高效实现无损负载均衡；(3) 设计了 hash bitmap 编码减少索引传输开销。在 V100 集群上实现了最高 5.09× 的通信加速和 2.48× 的训练吞吐量提升。主要局限在于实验硬件偏旧、自然稀疏模型代表性有限、LLM 场景的适用性存疑——其最大价值在于 embedding-heavy 的推荐模型和 GNN 训练场景，以及使用 gradient compression 的训练流程。
