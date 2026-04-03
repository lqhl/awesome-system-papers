# AssyLLM: Efficient Federated Fine-tuning of LLMs via Assembling Pre-trained Blocks

**作者**：Shichen Zhan, Li Li*, Chengzhong Xu（University of Macau, State Key Laboratory of Internet of Things for Smart City）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zhan
**源文件**：[[atc2025-zhan.pdf]]

---

## 一、背景

联邦学习（Federated Learning, FL）为在保护数据隐私的前提下微调大语言模型（LLM）提供了有效途径。然而，LLM 微调的显存需求极高——例如全参数微调 Llama-7B 需要超过 40GB 内存，即使使用 LoRA 等 PEFT 方法仍需 15GB 以上。现实中大量边缘设备（手机、IoT 设备等）内存仅 4-16GB，无法参与微调过程。这种"内存墙"（memory wall）问题导致大量低端设备被排除在 FL 之外，降低了训练数据的多样性和丰富性，进而影响模型性能。

实验显示，在 200 个客户端中，85% 的 Llama-7B 客户端和 60% 的 OPT-6.7B 客户端因内存不足无法参与，导致准确率分别下降 14.7% 和 19.1%。

---

## 二、要解决的问题

现有降低 FL 微调内存开销的方案存在以下不足：

1. **PEFT 方法（LoRA/QLoRA/Adapter）**：虽然降低了可训练参数量，但仍需存储前向传播的中间激活值（占主要内存开销），且不完整的模型更新导致性能退化，高压缩比带来更大的精度损失。QLoRA 在 100% 参与率下仍有 5.3% 精度下降。

2. **无反向传播（BP-free）方法（FwdLLM）**：通过前向梯度估计替代反向传播，将内存需求降至 3.8GB，但梯度估计的不精确性导致约 5.8% 的性能下降，在 non-IID 场景下问题更加突出。

3. **系统级内存优化（Recomputation/Swapping）**：梯度重计算和参数交换能有效降低内存，但引入大量额外 I/O 和计算开销，训练时间增加 1.78×-3.17×（从 8.73 小时增至 27.6 小时）。

核心矛盾：现有方法无法同时实现低内存开销、高模型精度和高训练效率三个目标。

---

## 三、洞察与设计

**关键洞察**：预训练 LLM 可以被分解为模块化的 transformer block，通过仅使用前向推理操作从多个预训练模型的 block pool 中选择和组装最兼容的 block，就能构建出针对下游任务的高质量模型——完全绕过反向传播过程，从根本上消除 BP 相关的内存开销。

基于此洞察，AssyLLM 的核心设计思路是：将多个预训练 LLM 拆分为离散的 block（起始 block/中间 block/终止 block），形成一个共享 block pool。在每轮联邦学习中，各客户端基于本地数据通过前向推理评估 block 间的兼容性，选择最优 block 进行组装，最终在服务器端通过加权投票聚合形成全局模型。

系统包含四个核心组件：

1. **Block Comparator**：结合 CKA（Centered Kernel Alignment）和 layer-correlation（COR，基于 KL 散度）两个指标评估 block 兼容性。实验证明单独使用任一指标都不够——高 CKA 不保证最优选择，高 COR 也不够，两者结合才能可靠地选出最佳 block。

2. **Elastic Adapter**：解决来自不同预训练模型的 block 在维度、语义和注意力机制上的不匹配问题。通过轻量级线性变换处理维度对齐，cross-attention 机制处理语义不一致，以及注意力输出的 pooling/扩展处理注意力机制差异。仅在显著不匹配时才激活 adapter，多数中间层只需简单投影矩阵。

3. **Block Quanter**：block 级混合精度量化方法。通过权重稀疏性分析和激活敏感性分析（随机扰动 + 掩码两种方法），再加上自底向上的敏感性重评估，为关键权重分配高精度、非关键权重分配低精度。整个过程离线完成。

4. **Block Swapper**：基于 block 相关性的内存交换策略，结合 LRU 策略决定换出哪个 block。引入 pre-loading（预加载）和 pre-swapping（预换出）机制，通过流水线化显著降低 I/O 延迟。

---

## 四、实现细节

- **平台**：混合平台——2 块 Nvidia A100 GPU 模拟高内存客户端，Nvidia Jetson TX2（8GB）和 Jetson Nano（4GB）作为真实边缘设备
- **模型池**：5 个预训练 LLM——Llama-7B、OPT-6.7B、BERT-base、Vicuna-7B、RoBERTa-large，涵盖 decoder-only 和 encoder-only 架构
- **Block 分割策略**：浅层和深层（语义差异小）分为较大 block（6-8 层），中间层（语义变化大）分为较小 block（2-4 层）。五个模型分别切为 6/6/4/6/6 个 block，共 28 个 block
- **FL 设置**：200 客户端分为 5 组（10%/64GB、15%/32GB、15%/16GB、30%/8GB、30%/4GB），FedAvg 聚合，Dirichlet 分布（α=1）分配数据
- **量化**：Block Quanter 使用 GPTQ 的 INT8/INT4 混合精度
- **训练参数**：学习率 0.01（高于标准值，因为只训练轻量 adapter），CKA 计算 batch size 32，组装过程通常少于 100 个 epoch，每轮评估 3 个候选 block，重复 5 轮
- **代码规模**：每个组件 300-600 行 Python，模块间通过共享接口协调，无紧耦合
- **开源**：https://github.com/zhanshichen/AssyLLM

---

## 五、实验结果

**数据集**：BoolQ（二分类问答）、PIQA（物理推理）、OpenBookQA（常识推理）

### 与算法级基线对比

| 方法 | BoolQ Acc (%) | BoolQ Speedup | PIQA Acc (%) | PIQA Speedup | OBQA Acc (%) | OBQA Speedup |
|------|------|------|------|------|------|------|
| FT-practical | 61.37 | 1× | 66.23 | 1× | 44.21 | 1× |
| FT-oracle | 75.11 | 1.45× | 79.22 | 1.37× | 57.29 | 1.47× |
| LoRA | 71.32 | 3.72× | 74.14 | 4.10× | 53.55 | 3.43× |
| QLoRA | 69.88 | 4.83× | 70.30 | 4.99× | 50.90 | 4.31× |
| FedAdapter | 72.96 | 6.32× | 75.81 | 6.87× | 54.78 | 6.02× |
| FwdLLM | 71.98 | 9.83× | 74.51 | 10.21× | 54.89 | 9.15× |
| **AssyLLM** | **78.12** | **12.92×** | **83.39** | **14.67×** | **62.47** | **10.97×** |

### 与系统级基线对比

| 方法 | BoolQ Acc/Speedup | PIQA Acc/Speedup | OBQA Acc/Speedup |
|------|------|------|------|
| Recomputation | 74.91 / 0.65× | 78.96 / 0.68× | 56.88 / 0.51× |
| Swapping | 74.35 / 0.43× | 78.13 / 0.51× | 56.19 / 0.41× |
| **AssyLLM** | **78.12 / 12.92×** | **83.39 / 14.67×** | **62.47 / 10.97×** |

### 关键数字

- **内存**：相比全微调降低 92%，相比 PEFT 降低 63.6%，最低 4GB 即可参与
- **能耗**：相比全微调降低 95.01%，相比 PEFT/BP-free 降低最高 88.1%
- **通信**：相比全微调降低 99.1%（只需上传 block 选择索引 + 轻量 adapter）
- **Block Quanter**：相比 FP16 减少 70.2% 内存，仅 1.1% 精度损失
- **Block Swapper**：pre-loading 减少 30.21% 本地时间，加上 pre-swapping 共减少 68.12%
- **Non-IID 鲁棒性**：在 α=0.1（极端 non-IID）下仍比基线高 27.2%，自身仅下降 4.6%

---

## 六、批判性分析

1. **精度提升的归因可疑**：AssyLLM 的精度提升（比 oracle 全微调还高 3-6%）主要归因于"更多低端设备参与带来数据多样性"，但实验中 oracle 基线假设所有设备都有足够内存。AssyLLM 超越 oracle 意味着 block 组装本身产生了额外收益，这与"block 组装是全微调的近似替代"的叙事不一致。论文未充分解释为什么组装出的模型会比在同样数据上全参数微调的模型更好。

2. **评估任务过于简单**：BoolQ（二分类）、PIQA（物理推理）、OBQA（常识选择题）都是相对简单的分类/选择任务，不涉及复杂的生成任务。Block 组装方法在需要深层语义连贯性的生成任务（如摘要、对话、代码生成）上是否同样有效，缺乏验证。

3. **模型规模偏小**：实验仅涉及 7B 级模型，而当前主流 LLM 已达 70B-405B。论文在 Discussion 中承认扩展到更大模型面临挑战，但未提供任何 13B+ 的实验数据。Block pool 的内存开销随模型数量线性增长，大模型场景下 Block Swapper 的 I/O 开销可能成为严重瓶颈。

4. **Block pool 组成的敏感性未充分探讨**：论文选择了 5 个特定模型（包括 BERT-base 和 RoBERTa-large 这两个相对较小的 encoder-only 模型），但未系统研究 block pool 组成对性能的影响。为什么混合 decoder-only 和 encoder-only 模型会有效？从 Figure 14 看，生成的 21 个组装模型精度分布在 55%-80% 之间，方差很大，说明 block 选择的质量高度依赖于具体组合。

5. **Speedup 指标有误导性**：12-30× 的 speedup 是相对于 FT-practical 和系统级基线的端到端聚合时间。但 AssyLLM 需要额外的离线步骤——Block Quanter 的离线量化、block pool 的预处理和分发——这些成本未计入 speedup。

6. **联邦场景的实际假设过强**：假设所有客户端都能存储和访问完整的（量化后的）block pool，但即使 INT4 量化后仍需 11GB+。对于 4GB 设备，Block Swapper 需要频繁换入换出，实际性能可能远低于模拟实验。

7. **与现有模型融合工作缺乏对比**：模型组装/模型融合（model merging/model soup）是近年热门方向，论文未与这些方法对比，也未讨论 AssyLLM 与它们的关系。

---

## 七、AI Infra / MLSys 视角

1. **Block 级模块化组装的启发**：将预训练模型视为可拆卸的 block 库，通过前向推理评估兼容性并组装，这个思路对 AI Infra 中的模型定制化部署有借鉴价值。例如，在 serving 场景中，可以根据请求类型动态组装不同配置的模型，实现更细粒度的"模型路由"。

2. **Block 级量化的实用价值**：Block Quanter 提出的"权重对 block 输出激活的影响"作为量化敏感性指标，比传统逐层分析更高效。这种粗粒度但有效的量化策略可以迁移到推理系统中，用于异构硬件上的自适应精度部署。

3. **值得跟进的方向**：
   - **大模型场景验证**：在 70B+ 模型上验证 block 组装的可行性，特别是 block 间语义鸿沟是否随模型规模增大而加剧
   - **Block pool 自动构建**：基于 task embedding 或 domain alignment 自动选择最优 block pool 组合，替代当前的手动选择
   - **与 MoE 架构的结合**：block 组装的思路与 Mixture-of-Experts 有天然相似性，可以探索将 block selection 机制融入 MoE routing
   - **推理端应用**：将 block 组装从训练阶段扩展到推理阶段，实现按需组装的轻量化模型服务

4. **最有价值的切入点**：将 block-level assembly 与 speculative decoding 或 early exit 结合——根据输入难度动态选择不同深度/组合的 block 路径，在推理效率和质量之间取得更好的平衡。

---

## 八、总结

AssyLLM 提出了一种新颖的联邦 LLM 微调范式：将多个预训练模型拆分为 block，通过前向推理评估兼容性并动态组装，从根本上避免了反向传播的内存开销。四个核心组件（Block Comparator/Elastic Adapter/Block Quanter/Block Swapper）分别解决了兼容性评估、异构组装、内存压缩和高效换入换出问题。在 7B 级模型和简单分类任务上，AssyLLM 实现了 92% 的内存降低和最高 30× 的加速，同时精度超越所有基线。但其在大模型、复杂生成任务和真实大规模边缘部署场景下的有效性仍待验证，block pool 的组成策略也需要更系统的研究。
