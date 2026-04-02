# WLB-LLM: Workload-Balanced 4D Parallelism for Large Language Model Training

**作者**：Zheng Wang (UC San Diego & Meta), Anna Cai (Meta), Xinfeng Xie (Meta), Zaifeng Pan (UC San Diego), Yue Guan (UC San Diego), Weiwei Chu (Meta), Jie Wang (Meta), Shikai Li (Meta), Jianyu Huang (Meta), Chris Cai (Meta), Yuchen Hao (Meta), Yufei Ding (UC San Diego & Meta)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/wang-zheng
**源文件**：[[osdi25-wang-zheng.pdf]]

---

## 一、背景

大语言模型（LLM）的训练规模持续增长，Meta 训练 LLaMA3-405B 使用了 16K H100 GPU 数月时间。当前主流的大规模 LLM 训练采用 4D 并行策略，即 Data Parallelism (DP)、Pipeline Parallelism (PP)、Context Parallelism (CP) 和 Tensor Parallelism (TP) 的组合。随着模型规模和上下文窗口不断增大（128K+），训练效率的每一点提升都意味着可观的资源节省。

在长上下文训练中，输入文档长度分布高度偏斜——大量短文档和少数极长文档共存。由于 attention 计算量与文档长度呈二次方关系，而现有框架将所有 token 同质对待、按固定长度打包和分片，导致 GPU 间出现严重的负载不均衡。在 Meta 内部 8K GPU 的 405B 训练任务中，最慢 GPU 的计算延迟是其他 GPU 的 1.44 倍，所有其他 GPU 必须等待最慢的完成，造成大量算力浪费。

---

## 二、要解决的问题

1. **PP 层面的 micro-batch 间负载不均**：固定长度打包策略下，包含单个长文档的 micro-batch 比包含多个短文档的 micro-batch 计算量大得多（attention 二次复杂度），导致不同 DP/PP worker 工作量差异显著。

2. **CP 层面的序列分片不均**：现有 per-sequence sharding 将整个打包序列等分为 chunks 分配给 CP worker。当序列由多个文档拼接而成时，包含长文档尾部的 chunk 需要 attend 更多前序 token，导致 CP worker 间负载不均。

3. **简单打乱重打包的局限**：跨多个 global batch 打乱文档虽能改善均衡，但破坏数据采样随机性、影响模型收敛（实验显示 8 个 global batch 的打包导致训练 loss 增加 1.6%）；且无法解决 CP 层面的文档内部分片不均问题。ILP 求解器虽可得最优解，但延迟过高（4 global batch 时每 batch 需 25 秒）。

---

## 三、洞察与设计

**关键洞察**：长文档虽然对负载均衡影响最大，但其 token 只占训练数据的很小比例（超过 75% 的 token 来自不到一半上下文窗口长度的短文档）。因此，可以选择性地延迟极少量长文档的执行来实现近似最优的负载均衡，而对数据随机性的影响微乎其微。同时，micro-batch 的总延迟不仅由 attention 决定，GEMM、通信等线性复杂度操作也占显著比重，这意味着可以通过允许短文档拼成更长序列（超过固定上下文窗口）来匹配长文档的总延迟。

基于以上洞察，WLB-LLM 在两个并行层级分别设计解决方案：

### PP 层面：变长打包 + Outlier 延迟

- **变长打包**：打破固定序列长度约束，允许 micro-batch 有不同长度。优化目标从仅均衡 attention 工作量转为均衡总工作量（attention + linear + communication），通过离线 profiling 获得延迟预测函数 $W_a(\cdot)$ 和 $W_l(\cdot)$。
- **Outlier 文档延迟**：设置多级等待队列，将极长文档（长度超过阈值 $L_i$）暂存。当某队列积累了足够多的 outlier（等于 micro-batch 数量），再均匀分配到各 micro-batch，确保每个 micro-batch 获得相同数量的 outlier。
- **启发式打包算法**：贪心策略，$O(N \log N)$ 复杂度，每 batch 开销仅 20ms（<0.65% 训练延迟），平均每个 token 仅延迟 0.5 个 iteration。

### CP 层面：细粒度 per-document sharding + 自适应选择

- **Per-document sharding**：将每个文档分别切分为 $2 \times CP\_size$ 个 chunk，对称分配给 CP worker，确保每个 worker 不仅 token 数相同，attention 计算量也相同。设计无 padding 方案处理文档长度不整除的情况。
- **自适应 sharding 选择**：per-document sharding 在短文档上会降低 kernel 效率（FlashAttention tile size = 128，短 chunk 浪费计算；且无法利用 TMA load multicast）。因此在运行时根据输入序列的文档组成，预估两种 sharding 策略的 attention kernel 延迟，选择更快的方案。

---

## 四、实现细节

- 基于 Meta 内部广泛使用的 4D 并行训练框架构建
- DP 层使用 FSDP；PP 层使用 interleaved 1F1B schedule，新增变长 pipeline 支持
- CP 层基于 AllGather-based CP（Llama3 训练方案），扩展实现 per-document sharding
- TP 层使用 1D tensor parallelism + sequence parallelism + 计算通信重叠
- Outlier 队列超参数 $L_i$ 通过在小样本上评估均衡度和 per-token delay 的 tradeoff 自动调优
- Kernel 延迟估计：考虑 tile padding、TMA multicast 等因素，基于离线 profiling 数据预测 TFLOPS
- 开源了 CP 优化部分：https://github.com/Ash-Zheng/WLB-LLM-CP

---

## 五、实验结果

**实验平台**：32 节点，每节点 8×H100 SXM 80GB（NVLink intra-node，RoCE inter-node）

**模型与配置**：

| 模型规模 | 上下文窗口 | GPU 数 | 4D 配置 (TP,CP,PP,DP) |
|---------|-----------|--------|----------------------|
| 550M | 64K/128K | 32 | (2,2,4,2) / (2,4,4,1) |
| 7B | 64K/128K | 32/64 | (4,2,4,1) / (8,2,4,1) |
| 30B | 64K/128K | 64/128 | (8,2,4,1) / (8,4,4,1) |
| 70B | 64K/128K | 256 | (16,4,4,1) |

**端到端加速**：

| 对比方案 | 平均加速 |
|---------|---------|
| WLB-LLM vs. Plain-4D | **1.23×** |
| WLB-LLM vs. Fixed-4D | **1.19×** |
| Fixed-4D vs. Plain-4D | 1.03× |

**关键结果**：
- 128K 上下文窗口比 64K 提升更大（平均 1.30× vs. 1.15×）
- 上下文窗口扩大到 160K 时加速达 1.40×
- 7B-128K 分解：CP per-doc +2%，CP adaptive +5%，PP var-len & delay +28%，全部组合 +33%
- 打包开销：2 个 outlier queue 时 imbalance degree 从 1.44 降至 1.05，per-batch 开销仅 20ms
- 模型收敛：WLB-LLM 的 loss 曲线与单 global batch 固定打包几乎一致，无收敛损失

---

## 六、批判性分析

1. **实验规模与生产环境的差距**：论文动机来自 8K GPU 的 405B 模型训练，但实验最大仅用 256 GPU 训练 70B 模型。在数百/数千 GPU 规模下，通信开销占比更高、调度更复杂，WLB-LLM 的实际收益是否能保持 1.23× 尚不清楚。论文虽用 "our internal LLM training framework" 暗示了生产部署，但未给出大规模实验数据。

2. **Outlier delay 的隐含假设**：论文认为延迟极长文档对训练质量影响可忽略，但仅在 550M 模型上验证了收敛（52K steps）。对于百亿级模型、数十万步训练，长文档往往是稀缺且信息密度高的样本（如书籍、长代码），系统性延迟这些样本是否影响特定下游任务的质量（如长上下文理解）未被讨论。

3. **自适应 CP sharding 的 overhead 分析不完整**：论文展示了 per-batch 打包开销（20ms），但自适应 sharding 选择需要在每次 forward 的 AllGather 后实时估计 kernel 延迟并做决策，这部分开销未量化。此外，同一 pipeline 内不同 micro-batch 可能选择不同 sharding 策略，是否引入额外的实现复杂性和同步开销也未讨论。

4. **基线选取偏保守**：Fixed-4D 基线限制在单 global batch 内打包（为保证公平），这使得 WLB-LLM 的优势被放大。如果允许 Fixed-4D 使用 2-4 个 global batch（Table 2 显示 imbalance 从 1.41 降至 1.11），差距会缩小。论文也未与 DynaPipe 等已有 variable-length batching 工作做实验对比。

5. **变长 pipeline 的 memory 影响**：允许 micro-batch 有不同序列长度意味着 activation memory 不再均匀，峰值内存可能显著增加。论文仅用 $S_{max}$ 上界约束，但未分析实际内存波动和对 GPU memory 利用率的影响。

---

## 七、AI Infra / MLSys 视角

1. **负载感知调度的普适性**：WLB-LLM 的核心思想——根据输入特征动态调整计算资源分配——不仅适用于训练，同样适用于 LLM 推理场景。当前 vLLM 等推理引擎在处理变长 prefill 请求时也面临类似的负载不均问题，per-request workload estimation + adaptive scheduling 是一个直接可迁移的方向。

2. **混合 sharding 策略**：论文在 Discussion 中提出了一个有价值的 future work——对同一序列中的长文档和短文档分别使用 per-document 和 per-sequence sharding。这种 per-document granularity 的混合策略如果能高效实现，将进一步消除 kernel efficiency 和 load balance 的 tradeoff。

3. **MoE 训练的负载均衡协同**：论文简要讨论了与 Expert Parallelism 的兼容性，但 MoE 模型中 token routing 的不均衡和 attention 的不均衡可能存在交互效应。联合优化 EP load balance 和 WLB-LLM 的 document packing 是一个有意义的研究方向。

4. **Kernel-系统协同设计**：论文揭示了 FlashAttention tile size、TMA multicast 等硬件特性对系统层 sharding 决策的影响。随着 Blackwell 架构引入新特性，kernel profiling + 系统自适应决策的模式会越来越重要，值得构建更通用的 cost model 框架。

5. **最具价值的切入点**：将 WLB-LLM 的 workload-aware packing 思想扩展到 prefill-decode disaggregated serving 场景——在 prefill 集群中，不同请求的 prompt 长度差异同样导致严重的 GPU 利用率不均，且对延迟更敏感。

---

## 八、总结

WLB-LLM 系统性地识别并解决了 4D 并行 LLM 训练中两个层级的负载不均问题：PP 层面通过变长打包和 outlier 文档延迟实现 micro-batch 间负载均衡，CP 层面通过 per-document sharding 和自适应策略选择实现分片间负载均衡。该系统在 550M 到 70B 模型、64K 到 160K 上下文窗口的配置下均取得一致的加速（平均 1.23×），且不影响模型收敛。其核心局限在于大规模生产环境下的验证数据缺失，以及 outlier delay 对长文档学习质量的潜在影响尚需更充分的评估。
