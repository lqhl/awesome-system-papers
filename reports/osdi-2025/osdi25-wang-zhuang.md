# ZEN: Empowering Distributed Training with Sparsity-driven Data Synchronization

**作者**：Zhuang Wang (Rice University), Zhaozhuo Xu (Stevens Institute of Technology), Jingyi Xi (unaffiliated), Yuke Wang, Anshumali Shrivastava, T. S. Eugene Ng (Rice University)
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会，2025 年 7 月，波士顿）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/wang-zhuang
**源文件**：[osdi25-wang-zhuang.pdf](../../papers/osdi-2025/osdi25-wang-zhuang.pdf)

---

## 一、背景

分布式训练已成为训练大规模深度学习模型的标准范式。在数据并行、张量并行以及两者混合的场景下，梯度同步（gradient synchronization）是不可或缺的步骤。近年来，GPU 计算能力大幅提升，而网络带宽的增长明显滞后，使得梯度同步成为分布式训练的主要性能瓶颈。

深度学习模型中广泛存在梯度稀疏性：
- 推荐系统 Embedding 表（DLRM）稀疏度超过 93%
- 图神经网络邻接矩阵稀疏度超过 99%
- NMT、LSTM 等 NLP 模型词嵌入稀疏度超过 97%
- 通过梯度压缩算法（如 DGC top-k 稀疏化）可进一步将梯度传输量降低 99%

现有系统（Ring-Allreduce、OmniReduce、AGsparse、SparCML）要么只针对密集张量设计，要么在利用稀疏性方面存在根本性缺陷，导致通信效率不佳。

---

## 二、要解决的问题

1. **稀疏张量通信缺乏最优方案**：Ring-Allreduce 假设张量为密集格式，完全忽略稀疏性；AGsparse 等方案虽然处理稀疏格式，但无法充分利用不同 GPU 上 non-zero 梯度的重叠（overlap）来减少流量。

2. **非零梯度分布不均导致通信不平衡**：OmniReduce 等方案将张量均匀分区，但非零梯度在分区间的分布极度偏斜（skewness ratio 可超过 70），导致某些 server 成为通信瓶颈。

3. **索引（index）表示开销巨大**：稀疏格式（COO）需为每个非零梯度携带索引，在聚合后张量密度升高时（densification），索引开销甚至使传输量高于密集格式的 2 倍。

4. **数据依赖方案计算开销不可接受**：实现负载均衡需要知道所有 GPU 上 non-zero 梯度的全局分布，数据依赖的计算代价比单次训练迭代时间高出数个数量级。

---

## 三、核心设计

### 设计空间分析

论文首先揭示了稀疏张量的三个关键特性：
- **C1 - 重叠率（overlap ratio）可变**：不同 GPU 上 non-zero 梯度的索引集合存在重叠，重叠程度因模型和批次而异。
- **C2 - 聚合后密度升高（densification）**：聚合来自 $n$ 个 GPU 的稀疏张量后，密度系数 $\gamma^n_G$ 随 GPU 数量增大，但始终小于 $n$（表示部分重叠）。
- **C3 - 分布高度偏斜（skewed distribution）**：将张量均匀分区后，超过 60% 的 non-zero 梯度集中在一个分区中。

基于这三个特性，论文提出了稀疏张量同步的四个设计维度：
- **Communication**：Ring / Hierarchy / Point-to-point
- **Aggregation**：Incremental aggregation / One-shot aggregation
- **Partition**：Centralization / Parallelism
- **Balance**：Balanced / Imbalanced

### 最优同步方案（Theorem 1）

通过理论分析，论文证明最小化通信时间的方案只有两个候选：
- **Balanced Parallelism**：[Point-to-point, Incremental aggregation, Parallelism, Balanced communication]
- **Hierarchical Centralization**：[Hierarchy, Incremental aggregation, Centralization]

在实际分布式训练中，由于重叠率通常较高，Balanced Parallelism 优于 Hierarchical Centralization。

### ZEN 系统

ZEN 在运行时通过前几个 iteration 的轻量级 profiling，对比两个方案的理论通信时间公式，自动选择最优方案。核心创新集中在实现 Balanced Parallelism 的两个子组件：

**1. 数据无关的分层哈希算法（Hierarchical Hashing, Algorithm 1）**

目标：将 $n$ 个 GPU 的 non-zero 梯度索引集合 $I_i$ 路由到 $n$ 个 server，使每个 worker 发往每个 server 的负载均衡（Push 均衡），同时每个 server 收到的聚合梯度数量也均衡（Pull 均衡）。

四项关键技术：
- **Technique 1 - 通信导向内存管理**：将 hash 内存分为 parallel memory 和 serial memory，避免并发写冲突导致信息丢失。
- **Technique 2 - 多哈希函数**：哈希冲突时依次尝试 $k$ 个哈希函数，将冲突率控制在 1% 以内（$k=3$ 时），大幅减少串行写的需要。
- **Technique 3 - 跨 worker 一致分层哈希**：第一级哈希函数 $h_0$ 所有 worker 共享（决定分区归属），第二级哈希函数各 worker 独立，保证相同索引路由到相同 server，避免聚合不完整。
- **Technique 4 - 无锁读后写机制**：写入后立即回读验证，检测并发写冲突，触发重哈希或串行写。

**2. Hash Bitmap 编码方案**

在 Pull 阶段（server 返回聚合结果给 worker），索引表示开销是 COO 格式的主要问题。ZEN 提出 hash bitmap：
- Server $i$ 只维护索引集合 $I_i = \{idx \mid h_0(idx) = i\}$（由 $h_0$ 决定，worker 和 server 都可以离线预计算，无需传输）
- 用 bitmap 标记 $I_i$ 中哪些索引有 non-zero 值
- 每个 worker 收到的 bitmap 总大小恒为 $|G|/32$（与 server 数量无关），消除了索引传输随 server 数线性增长的问题

---

## 四、实现细节

- 代码规模：约 900 行 Python + 250 行 CUDA C + 500 行 ColossalAI 修改
- 使用 MurmurHash 作为通用哈希函数，训练开始时广播随机 seed 保证一致性
- 通过 PyTorch DDP 的 `custom_comm_hook` 接口接入，与梯度计算 overlap
- 梯度张量先在 DDP 的 communication bucket 中融合，再应用稀疏同步方案
- 节点内（intra-machine）通信采用 NCCL ReduceScatter/AllGather（利用 NVLink）；节点间（inter-machine）通信使用 ZEN 的稀疏方案
- 并行内存大小设置为 $r_1 = 2|G|d_G$，串行内存 $r_2 = r_1/10$，重哈希次数 $k=3$
- GPU 内存占用 < 150MB（< 1% V100 显存）

---

## 五、实验结果

**实验平台**：
- 16 台 AWS p3.16xlarge（各 8 块 V100 16GB，NVLink，25 Gbps 网络）
- 16 台 AWS p3dn.24xlarge（各 8 块 V100 32GB，NVLink，100 Gbps RDMA/EFA）

**Workload**：

| 类型 | 模型 | 数据集 | Batch Size |
|------|------|--------|-----------|
| 自然稀疏 | LSTM | One Billion Word | 128 |
| 自然稀疏 | DeepFM | Criteo | 1024 |
| 自然稀疏 | NMT | IWSLT 2014 De-En | 64 |
| 梯度压缩（DGC top-5%） | Llama3.2-3B | RedPajama | TP=8 |
| 梯度压缩（DGC top-5%） | OPT-2.7B | RedPajama | TP=8 |
| 梯度压缩（DGC top-5%） | Gemma2-2B | RedPajama | TP=8 |

**主要结果（25 Gbps 网络）**：

| 对比场景 | ZEN vs AllReduce | ZEN vs 最佳 Baseline |
|----------|-----------------|---------------------|
| LSTM（16机） | 3.1× 吞吐提升 | 1.67× vs SparCML |
| DeepFM（16机） | - | 1.44× vs OmniReduce |
| NMT（16机） | - | 1.51× vs OmniReduce |
| Llama3.2-3B | 2.02× | 1.68× vs OmniReduce |
| OPT-2.7B | 2.10× | 1.66× vs OmniReduce |
| Gemma2-2B | 2.04× | 1.61× vs OmniReduce |

**通信时间加速**（16 机，25 Gbps）：LSTM 达到 6.77× over AllReduce，Gemma2-2B 达到 3.51× over AllReduce；ZEN vs OmniReduce 最高 5.16×。

**计算开销**：哈希计算在 25 Gbps 网络下约 6ms，仅占通信节省量（270ms）的 2.2%；100 Gbps RDMA 下也只占通信节省的 9%。

---

## 六、批判性分析

**1. 实验规模偏小，难以代表超大规模训练**

实验最多使用 16 台 8-GPU 机器（128 GPUs），而现实中 LLM 训练通常在数千卡规模。论文证明了稀疏方案在大 GPU 数量下相对 AllReduce 优势扩大，但 128 GPU 规模的结论能否外推到千卡？Balanced Parallelism 的负载均衡误差随 $\sqrt{n \log n / |G| d_G}$ 增大，在更多 GPU 时是否仍可控需要更多实证支撑。

**2. LLM 实验设计存在疑问**

LLM 实验（Llama3.2-3B 等）使用 TP=8（仅限单节点内），跨机通信只有 embedding 层梯度的稀疏同步。这意味着 ZEN 优化的仅是 LLM 训练中的一小部分通信（embedding 同步），而不是 attention/FFN 层的梯度，后者占训练通信的绝大部分。论文对此没有清晰说明，可能给读者造成"ZEN 显著加速了 LLM 全部通信"的错误印象。

**3. DGC 算法本身的收敛问题被轻描淡写**

论文声称 ZEN 不引入额外精度损失，模型收敛曲线与 AGsparse 相同。但 DGC 本身是有损压缩，且 top-k 稀疏化配合 TP 的全局 top-k 计算（论文描述为先 gather samples 再全局 top-k）在 TP 环境下的合理性没有充分讨论，能否真正等价于 AllReduce 的梯度聚合存疑。

**4. 哈希冲突率声称不足 1% 的证明不充分**

论文称使用 $k=4$ 个哈希函数时冲突率 < 1%，但这基于特定的参数（parallel memory 大小 $r_1 = 2|G|d_G$）和测试模型，而非普遍保证。对于极度稀疏（$d_G < 0.1\%$）或密度意外升高的场景，这一保证是否仍然成立没有验证。

**5. 基线对比不完全公平**

论文使用 AGsparse、SparCML（2019-2021 年工作）和 OmniReduce 作为基线，未包含更近期的工作（如 Ok-Topk、Flare）。其中 Flare 和 Libra 基于可编程交换机，论文以"依赖特定硬件"为由排除，但未给出软件方案最优性的充分论证。

---

## 七、AI Infra / MLSys 视角

**核心 Insight 的迁移价值**

ZEN 提出的设计空间分析框架——将稀疏通信拆解为通信模式、聚合策略、分区方式、负载均衡四个维度——是一个可复用的方法论，适合扩展到其他稀疏通信场景（如 MoE 专家路由通信、稀疏 Attention 的 KV 传输）。

**Hierarchical Hashing 在 AI Infra 中的潜在应用**

分层哈希实现数据无关负载均衡的思路可迁移到：
- **MoE 路由负载均衡**：expert capacity 分配问题和 Balanced Parallelism 形式上等价，ZEN 的哈希方法可能比当前的 token dropping 或辅助损失方案更有理论保证
- **KV Cache 分布式存储**：在 disaggregated inference 场景下，稀疏 KV 的均衡分布同样面临类似问题

**值得跟进的研究方向**

1. **超大规模（> 1K GPU）验证**：ZEN 的哈希均衡性随规模增大的实际表现，以及与 RDMA one-sided 操作的结合
2. **与梯度累积、异步训练的结合**：稀疏梯度在异步场景下的 staleness 和覆盖问题
3. **Hash Bitmap 思路用于稀疏 Attention**：FlashAttention 在 Sparse Attention 模式下传递 block sparsity mask 的效率问题与 hash bitmap 有相似结构
4. **将设计空间分析扩展到 MoE all-to-all 通信**：当前 MoE all-to-all 同样存在负载不均问题，Balanced Parallelism 的理论框架直接适用

---

## 八、总结

ZEN 通过系统分析稀疏张量的统计特性，理论证明了最优稀疏梯度同步方案（Balanced Parallelism 和 Hierarchical Centralization），并基于数据无关的分层哈希算法和 Hash Bitmap 编码方案实现了接近理论最优的通信效率，在自然稀疏和梯度压缩场景下分别实现了最高 5.09× 通信加速和 2.48× 训练吞吐提升。其主要局限在于：实验规模（128 GPU）偏小，LLM 实验仅优化了 embedding 层这一小部分通信，对于 attention/FFN 密集梯度场景的适用性未得到验证。
