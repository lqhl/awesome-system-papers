# WLB-LLM: Workload-Balanced 4D Parallelism for Large Language Model Training

**作者**：Zheng Wang (UC San Diego, Meta), Anna Cai (Meta), Xinfeng Xie (Meta), Zaifeng Pan (UC San Diego), Yue Guan (UC San Diego), Weiwei Chu (Meta), Jie Wang (Meta), Shikai Li (Meta), Jianyu Huang (Meta), Chris Cai (Meta), Yuchen Hao (Meta), Yufei Ding (UC San Diego, Meta)
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会），Boston, MA，2025 年 7 月
**DOI**：https://www.usenix.org/conference/osdi25/presentation/wang-zheng
**源文件**：[osdi25-wang-zheng.pdf](../../papers/osdi-2025/osdi25-wang-zheng.pdf)

---

## 一、背景

大语言模型（LLM）的规模持续扩张，训练成本极高。Meta LLaMA3-405B 使用 16K 块 H100 GPU 训练数月。为支撑如此规模的训练，业界已形成以 **4D 并行**（Data Parallelism + Pipeline Parallelism + Context Parallelism + Tensor Parallelism）为核心的分布式训练范式。其中 Context Parallelism（CP）是近年为解决超长上下文（128K+）内存压力而引入的新维度。

然而，随着上下文窗口增大，训练数据中文档长度差异极大，部分极长文档会导致 GPU 间负载严重不均衡。论文在 8K GPU 规模、128K 上下文的 405B LLM 训练任务上实测，发现最慢 GPU 的计算延迟是最快 GPU 的 **1.44 倍**，由此造成大量计算资源空等浪费。

---

## 二、要解决的问题

**根本原因**：4D 并行框架对所有 token 一视同仁，按等长分配，但注意力计算的工作量与文档长度的**平方**成正比，导致含长文档的 micro-batch 工作量远高于含多个短文档的 micro-batch。

具体存在两层不均衡：

1. **PP 层（Pipeline Parallelism）的不均衡**：现有框架将输入文档打包成固定长度的 micro-batch，短文档组合 vs. 单个长文档之间计算量相差悬殊。由于 PP 的关键路径被最慢 micro-batch 决定，且不均衡在多级并行间传播放大，影响最终 end-to-end 延迟。

2. **CP 层（Context Parallelism）的不均衡**：CP 将序列切分成等长 chunk 分发到各 Worker，但当序列由多个文档打包而成时，文档尾部 token（需要 attend 更多前序 token）集中在某些 CP Worker，造成注意力计算严重失衡。

**朴素修补方案（固定长度 packing）的局限**：
- 跨多个 global batch 重新打包虽能降低不均衡，但破坏数据加载随机性，导致训练 loss 增加（8 个 global batch 时 loss 上升 1.6%）
- ILP 最优求解器开销无法接受（4 个 global batch 时每 batch 求解耗时 25 秒）
- 固定长度约束无法平衡"文档长度 = 上下文窗口"的极端情形

---

## 三、核心设计

WLB-LLM 针对两个并行层级分别设计解决方案：

### PP 层：可变长 Packing + Outlier 文档延迟

**关键洞察**：micro-batch 的总工作量不只是注意力计算，还包括 GEMM、element-wise 算子和 collective 通信（线性增长），而注意力则是平方增长。因此可以让若干短文档拼合为超过上下文窗口长度的 micro-batch，使其线性部分的延迟补足与长文档的差距。

- **变长 Packing**：放宽固定长度约束，允许各 micro-batch 有不同总序列长度，优化目标改为最小化各 micro-batch"总工作量"（注意力 + 线性算子）的最大值
- **Outlier 文档延迟**：对极长文档（outlier）放入多级等待队列，积累足够数量后再均匀分发到各 micro-batch。由于极长文档只占总 token 的少数比例，每个 token 平均延迟仅 0.5 个迭代，对数据随机性影响极小
- **启发式贪心算法**：运行时在毫秒级内完成 packing，overhead < 0.65%

### CP 层：细粒度 Per-Document Sharding + 自适应策略选择

**Per-Document Sharding**：将每个文档独立切分成 `2×CP_size` 份，每个 CP Worker 获得每个文档的对称两份 chunk，从而保证各 Worker 的注意力计算量完全相同。支持 padding-free 实现（余数按 round-robin 分发）。

**内核效率与 sharding 粒度的权衡**：细粒度 sharding 在文档较短时会引发：
- FlashAttention tile 级别计算浪费（tile size = 128，短于此的 Q 被 pad）
- NVIDIA Hopper TMA 多播（load multicast）无法充分利用

**自适应策略选择**：通过离线 profiling 建立注意力内核延迟模型，在每个 micro-batch 的 AllGather 之后预测 per-sequence 和 per-document sharding 的延迟，动态选择更优方案。

---

## 四、实现细节

- **整体框架**：在内部 4D 并行框架上构建，DP 采用 FSDP，PP 采用 interleaved 1F1B pipeline schedule，CP 采用基于 AllGather 的方式（与 LLaMA3 训练一致）
- **变长 Pipeline**：为支持 PP 层的可变长 packing，实现了 variable-length pipeline，允许 micro-batch 间序列长度不同
- **延迟预测**：离线 profiling 注意力内核在不同 Q_len / KV_len 下的 TFLOPs 及 TMA 效应，运行时用于 CP 自适应策略选择
- **硬件环境**：32 节点 × 8 H100 SXM 80GB GPU，节点内 NVLink，节点间 RoCE（RDMA over Converged Ethernet）
- **实验规模**：550M、7B、30B、70B 四档，上下文窗口 64K/128K，全部使用 bfloat16

---

## 五、实验结果

### 端到端加速（vs. Plain-4D）

| 模型 | 上下文窗口 | Plain-4D | Fixed-4D | WLB-LLM |
|------|-----------|---------|---------|---------|
| 550M | 64K | 1.00× | ~1.06× | ~1.21× |
| 550M | 128K | 1.00× | ~1.03× | ~1.41× |
| 7B | 64K | 1.00× | ~1.01× | ~1.21× |
| 7B | 128K | 1.00× | ~1.04× | ~1.33× |
| 30B | 64K | 1.00× | ~1.02× | ~1.12× |
| 30B | 128K | 1.00× | ~1.05× | ~1.26× |
| 70B | 64K | 1.00× | ~1.01× | ~1.06× |
| 70B | 128K | 1.00× | ~1.05× | ~1.20× |

- 平均加速 **1.23×**，Fixed-4D 仅 1.03×
- 160K 上下文时加速达 **1.40×**，趋势随窗口扩大而增强

### 优化分解（7B-128K）

| 优化组合 | 加速比 |
|---------|--------|
| Plain-4D（基准） | 1.00× |
| + CP Per-Document Sharding | 1.02× |
| + CP Adaptive Selection | 1.05× |
| + PP Var-Len & Outlier Delay | 1.28× |
| WLB-LLM（全部） | 1.33× |

### Packing 不均衡度与 Overhead 对比（7B-128K）

| 方法 | 不均衡度 | Packing Overhead (ms/batch) |
|------|---------|---------------------------|
| Original Packing | 1.44 | 0 |
| Fixed-Len Greedy (1 batch) | 1.41 | 4 |
| Fixed-Len Greedy (8 batch) | 1.08 | 5 |
| Fixed-Len Solver (4 batch) | 1.09 | 25313 |
| **WLB-LLM (2 queues)** | **1.05** | **20** |

### 模型收敛

WLB-LLM 训练 loss 曲线与 Fixed-4D（单 global batch）几乎重合，不影响模型质量。

---

## 六、批判性分析

**1. 实验规模与生产规模差距**：论文在 32 节点（256 GPU）上测试，而实际问题的发现来自 8K GPU 的 405B 训练任务。两者规模相差约 32 倍，实验结论是否在更大规模下成立并未验证。论文的加速数字（1.23×）仅来自小规模集群。

**2. 基线选取偏弱**：Fixed-4D 被刻意限制在单 global batch 范围内以"保证收敛质量"，但这人为削弱了对比对手。如果 Fixed-4D 采用与 WLB-LLM 相当的窗口（仅延迟少量 outlier），差距可能更小。论文未尝试展示 Fixed-4D 在更积极配置下与 WLB-LLM 的收敛+性能综合权衡曲线。

**3. CP 层优化贡献有限**：Per-Document Sharding + Adaptive Selection 仅贡献 1.05× 加速，与 PP 层的 1.28× 相比悬殊。Section 5 占据篇幅过多，工程价值与写作比重不匹配。作者自己也承认自适应 sharding 仍有优化空间（混合策略）。

**4. Outlier 延迟对模型质量影响未深入分析**：虽然作者声称每个 token 平均延迟 0.5 个迭代，但 outlier 文档（极长文档）往往代表特定数据分布（如书籍、代码文件）。对这些文档的系统性延迟处理是否会影响模型在长文本任务上的表现，论文未做针对性评估。

**5. 论文仅测试语言建模 loss，未做下游任务评估**：Loss 曲线对齐不等于下游能力不受损，特别是对长文本理解任务（如 SCROLLS、LongBench）。

**6. MoE 兼容性仅定性讨论**：论文提到 WLB-LLM 与 Expert Parallelism 兼容，但 MoE 场景的 token 路由本身产生负载不均，与 WLB-LLM 的 packing 优化之间的交互效果并未实验验证。

---

## 七、AI Infra / MLSys 视角

**核心价值**：这是一篇来自 Meta 与 UCSD 合作的工程驱动型研究，解决了大规模 LLM 训练中的实际性能瓶颈。1.23× 的平均加速在百亿参数模型训练中可直接转化为数千万美元的算力节省。

**对 AI Infra 研究的启发**：

- **工作量感知调度是分布式训练的下一个重要方向**：当前主流框架（Megatron、DeepSpeed）对 token 同质化处理，这种假设在长上下文时代越来越不成立。WLB-LLM 的洞察——"不均衡的根源是 attention 的 input-dependent 计算复杂度"——有广泛的迁移价值。
  
- **变长 micro-batch 对 pipeline 调度的影响值得深挖**：WLB-LLM 引入变长 micro-batch 后，1F1B pipeline 中气泡率和内存峰值的变化并未详细分析。变长 pipeline 与更复杂的 schedule（如 ZB-H1、V-cycle schedule）的结合是有价值的研究方向。

- **延伸至推理场景**：prefill 阶段同样存在类似的注意力计算不均衡问题（不同请求长度差异大），WLB-LLM 的 per-document sharding 思路可以迁移到 chunked prefill + disaggregated inference 的 context parallelism 设计中。

- **可操作的 Future Work**：
  1. 在 MoE + 4D 并行场景下同时优化 token routing 负载和 document packing，两种不均衡来源的联合优化
  2. 将 WLB-LLM 的思路应用于 RLHF/PPO 训练，其中不同 trajectory 长度差异更大，不均衡更严重
  3. 在 prefill disaggregation 框架（如 Mooncake、Splitwise）中引入 context-level workload-aware sharding

---

## 八、总结

WLB-LLM 系统性识别并解决了 4D 并行 LLM 训练中因文档长度差异导致的双层工作量不均衡问题：在 PP 层通过变长 packing 和 outlier 文档延迟实现近最优的 micro-batch 工作量平衡，在 CP 层通过细粒度 per-document sharding 和自适应策略选择消除 CP Worker 间的注意力计算不均衡。在 550M–70B 多规模模型上实现平均 1.23× 加速且不影响模型收敛，是长上下文 LLM 训练基础设施的重要工程贡献。主要局限在于实验规模有限（256 GPU vs. 8K GPU 的目标场景），以及 CP 层优化的实际收益相对有限。
