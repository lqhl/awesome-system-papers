---
type: paper
name: Jenga
full_title: "Jenga: Enhancing LLM Long-Context Fine-tuning with Contextual Token Sparsity"
authors: [Tuowei Wang, Xingyu Chen, Kun Li, Ting Cao, Ju Ren, Yaoxue Zhang]
venue: ATC
year: 2025
tags: [llm-fine-tuning, long-context, token-sparsity, activation-memory, peft]
source_pdf: "[[atc2025-wang-tuowei.pdf]]"
source_md: "[[atc2025-wang-tuowei]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Jenga: Enhancing LLM Long-Context Fine-tuning with Contextual Token Sparsity (ATC 2025)

> **一句话总结**：长上下文微调的真正瓶颈是随序列长度线性增长的 activation，而非 [[LoRA]] 已优化的参数/optimizer 状态；JENGA 利用长文本中 attention 高度稀疏且重要 token 随输入与层动态变化的 **Contextual Token Sparsity**，在 block 粒度剔除冗余 token 并配合轻量 predictor 与 permutation-free kernel，在单卡 A800 上相对 SOTA 实现最高 **1.93×** 显存节省、**1.36×** 加速，且 perplexity / LongBench 与 LoRA 基本持平。

## 问题与动机

预训练 LLM 的固定 context window（如 Llama2 4K）与部署侧越来越长的输入需求之间存在鸿沟，需要通过长序列微调扩展窗口。但长序列使 **activation memory**（前向中间结果 + 反向梯度）迅速超过 model states：论文引用 GPT-3 175B 在 s=64K 时 activation 可达 model states 的 **71.6×**。

现有高效微调路线各有盲区：

- **PEFT**（[[LoRA]] 等）冻结主干、只更新少量低秩矩阵，显著降低 optimizer state，但低秩矩阵深嵌 transformer block，反向传播路径与 full fine-tuning 几乎相同，activation 不降反升（论文 Figure 3）。
- **Hidden-dimension 稀疏 attention**（LongLoRA 的 S2-Attn 等）减少计算量，但整条 token 序列仍参与前向/反向；只要某 token 被任一 head 用到，其 activation 就必须保留——作者称之为 **Shadowy Activation**。Table 1 显示 LongLoRA 在 Llama2-7B / 4K 下 activation  footprint 约 41.3 GB，与 LoRA 的 39.2 GB 几乎无差别，而 JENGA 降至 **31.3 GB**。

作者 claim：需要一种在 **token 粒度** 直接减少参与计算的 token 数量、从而同时优化 memory 与 compute 的长上下文微调系统。深度实现细节见 [[atc2025-wang-tuowei]]。

## 关键观察 / 隐含假设

- **观察 1（Activation 主导瓶颈）**：长上下文微调中，activation 随 batch size × sequence length 增长，在 s≥8K 后普遍超过固定规模的 model states；PEFT 与 attention 稀疏均无法触及这一瓶颈。
  - **依赖假设**：实验采用 mixed-precision（FP16 参数/梯度 + FP32 optimizer state），且测量峰值出现在 forward 刚结束时刻；未默认启用 activation recomputation / offload（除非 extension 实验）。
  - **可能失效场景**：极短序列（s≤4K）时 activation 占比下降，token 剔除收益变小；多卡 tensor parallel 已分摊 vocab loss gradient 时，segment-based peak cutting 的边际收益可能缩小。

- **观察 2（长文本 attention 天然稀疏）**：attention score 中低于最大值 30% 的比例随序列长度上升——Llama2 从 4K 的 **38.6%** 增至 16K 的 **69.6%**；Figure 4 显示重要 token 呈网格状分布，且随输入文本与层深度变化。
  - **依赖假设**：RedPajama / PG19 / Proof-Pile 等自然语言长文档能代表目标微调 workload；block-wise 剔除（默认 block size 64）下，重要 token 的 informativeness 分数与无关 token 差距足够大，不会被 block 内平均掉。
  - **可能失效场景**：代码、数学证明、结构化日志等低冗余长上下文；需要密集 cross-token 依赖的任务（如细粒度引用对齐）；极深层的稀疏分布变化可能导致 layer-specific threshold 需频繁重调。

- **观察 3（Shadowy Activation 限制 hidden-dim 稀疏）**：LongLoRA 等只在 hidden dimension 上近似 full attention，但无法把 token 从计算图中移除，activation 节省为零甚至略增。
  - **依赖假设**：activation 占用与「参与计算的 token 数 × 层数」强相关，而非仅与 FLOPs 相关。
  - **可能失效场景**：若配合 activation recomputation，shadow 问题被转嫁为额外计算，JENGA 的相对 memory 优势需重新测量。

- **假设 1（离线训练的 Q/K predictor 可泛化到微调 runtime）**：每层一对低秩矩阵 predictor，在 <400 epoch 内收敛，平均 recall **95.13%**，用 \(\hat{I}(Q)\hat{I}(K)^T\) 近似 block informativeness。
  - **证据强度**：**中**——在 LongAlign / RedPajama 上可视化与 ground truth 接近，但未见跨架构零样本迁移或分布外长文档的系统评估。

## 核心方法

JENGA 是端到端长上下文微调系统（3000+ 行 Python/C++），与多种 LLM 架构兼容，可叠加其他优化。核心围绕 **Contextual Token Sparsity** 展开三项设计：

**1. Information-driven Token Elimination**（回应观察 2、3）

- 定义 token 信息量 \(I(T_j) = \sum_{i \neq j} Q_i K_j\)，在 [[Attention]] score 上按 head 聚合（只累加正 score），再 block-wise 取 max 得到 block informativeness。
- 沿 token 维聚合 score block 后与 **layer-specific threshold** 比较（Algorithm 1：先 profile 初始化，再有限差分梯度微调），不同层 sparsity 模式差异大（Figure 7）。
- 同样逻辑延伸到 MLP：ReLU 结构用 ReLU 输出，SiLU 结构用 gate×up 乘积评估 neuron/token 活跃度——与已有 activation sparsity 工作衔接。
- 设计意图：在 block 粒度安全剔除「无重要 token」的块，保留含少量重要 token 的块以维护精度。

**2. Context-aware Pattern Prediction**（回应观察 2 的动态性）

- 完整 attention score 的 \(O(s^2)\) 存储/计算不可接受；每层部署 Q/K 两个轻量 predictor（三层低秩矩阵 + ReLU），输入为 block 代表 embedding。
- **Elastic size transformation**：跟踪 predictor 中间激活的 zero frequency，周期性剪枝 inactive neuron，平均参数减 **64.6%**、计算/内存各约减半。
- 离线训练集成进 [[Flash-Attention]] kernel，在线推导 \(O(s^2/b^2)\) 主导但可通过增大 block size 缓解；predictor 权重复杂度 \(O(bh^2)\) 与序列长度无关。

**3. High-performance Kernel Optimization**（回应层间动态 sparsity 的系统开销）

- **Permutation-free**：不物化重排后的 token，直接从原始输入 selective load；attention 输出 inplace 加到原输入，融合 padding 与 residual；反向时通过 output − self-attn 恢复输入 embedding。相对 naive 实现 **10×–50×** kernel 加速。
- **Segment-based peak cutting**：loss gradient 按序列切段计算，每段算完即释放 activation，峰值降至 1/N；在 Llama 大 vocab + 长序列下额外节省约 **15%** 内存（Figure 19），且与多卡 vocab parallel 正交。

**扩展**：(a) **2D-Sparsity**——token 剔除后再对剩余 token 应用 hidden-dim 稀疏（如 LongLoRA 风格），最高 **2.04×** 加速；(b) **Sparsity-sensitive Offload**——按层 sparsity ratio 自适应 CPU↔GPU 搬运，平均 **1.22×** 加速。

## 设计取舍

- **取舍 1（精度 vs 稀疏度）**：block-wise 剔除宁可多留少量无关 token，也不冒险丢掉 block 内重要 token；换取稳定 perplexity（PG19 / Proof-Pile 仅 +0.1~0.2 PPL）但稀疏度上限受 block size 约束。
- **取舍 2（动态 sparsity vs 系统复杂度）**：每层、每输入不同 sparsity pattern → 需要 predictor 离线训练 + layer threshold 调优 + 定制 CUDA kernel；工程门槛显著高于纯 [[LoRA]] 或静态稀疏 pattern。
- **取舍 3（近似 informativeness vs 精确 attention）**：predictor 用 \(\hat{I}(Q)\hat{I}(K)^T\) 分解近似，避免 materialize full score matrix；5% 左右 recall 损失被换取线性内存复杂度的在线 score 推导。
- **边界条件**：在 RedPajama 类冗余自然语言、单卡 48–80 GB GPU、s=4K–64K 微调场景下效果最好；与 recomputation/offload 正交叠加时收益可能来自不同瓶颈维度，需分别 profiling。

## 实验与结果

- **显存**：相对 LoRA 平均节省 **38.2%**（4K）/ **50.5%**（8K）；相对 LongLoRA 类似幅度；端到端最高 **1.93×**；单 A800 无 recomputation/offload 时，OPT 1.3B 可训练序列从 16K→**32K**，OPT 350M 从 32K→**64K**。
- **速度**：4K 序列相对 LoRA 平均加速 **10.8%**（A800）/ **8.6%**（A40）；更长序列 + recomputation 场景最高 **1.36×**；2D-Sparsity 扩展最高 **2.04×**。
- **精度**：Llama2-7B 在 PG19 / Proof-Pile 上 PPL 与 LoRA 差距 <3%；LongBench 18 项任务分数与 Origin 互有胜负，整体 comparable（Table 6）。
- **Ablation**：Attention block 平均省 **38.3%**（Llama2）/ **38.0%**（OPT）activation；MLP block 省 **51.1%** / **54.8%**；predictor recall **95.13%**；permutation-free kernel 是端到端提速的关键底座。
- **规模**：覆盖 OPT 125M–6.7B、Llama2-7B、Llama3-8B；硬件含 1×A800、1×A40、4×4090，强扩展性线性（Figure 21）。

## Critical Analysis

### 论证链条

观察链闭合度较高：先用 Table 2 / Figure 3 建立 activation 瓶颈 → 用 Figure 1 + Table 1 证明 hidden-dim 稀疏不省 activation（Shadowy Activation）→ 用 Table 3 / Figure 4 论证 token-level 剔除可行 → 三项技术分别解决 identify / predict / system overhead → Figure 12–14 验证 memory+speed，Table 6–7 验证精度。

薄弱跳步：(1) 「自然语言冗余」主要证据来自 attention score 统计，未对比代码/表格/多模态长上下文；(2) block size 64 的选择对精度与稀疏度的敏感性缺少系统 sweep；(3) 与 activation recomputation（如 checkpointing）的 **正交叠加后总收益** 在端到端主实验中刻意排除，外推到 production 训练栈需谨慎。

### 假设压力测试

- **Workload**：RedPajama + PG19 + Proof-Pile 偏书籍/论文；LongBench 覆盖 QA、摘要、代码等但 JENGA 相对 LoRA 在 gov_report、repobench 等任务有可见回落（Table 6），暗示低冗余或结构化任务可能更伤精度。
- **硬件**：主内存数字来自 A800 80GB；24GB 4090 仅用于 scalability，未报告极限序列长度下的 OOM 边界。
- **规模**：最大 8B 级；未验证 70B+ 或更大 batch 下 predictor 训练成本与 threshold 调优是否可承受。
- **部署**：论文聚焦 **fine-tuning** 而非 inference；token 剔除规律能否零成本迁移到 serving 未讨论。

### 实验可信度

- **Baseline 强度**：LoRA + LongLoRA 是合理 SOTA 代表，但未与 activation recomputation、offload、或同时做 PEFT+recompute 的工业栈（如 DeepSpeed ZeRO + checkpoint）对比——后者可能缩小 1.93× 的相对优势。
- **公平性**：speedup 主对比 LoRA；LongLoRA 因「正交稀疏维度」仅作参考，合理但读者不易直接量化「JENGA vs LongLoRA 端到端」。
- **Ablation**：三项技术均有独立拆解（Figure 14–19），支持「predictor 开销小」「kernel 关键」「segment cutting 削峰」等 claim。
- **Metric**：覆盖 memory peak、step time、PPL、LongBench；**未报告** 微调收敛步数差异、训练稳定性（loss 曲线）、或多 seed 方差。

### 系统性缺陷

- **尾延迟 / 步间抖动**：per-layer 动态 token 数可能引入 kernel 分支与负载不均；论文未讨论。
- **可观测性**：layer threshold、block 剔除率、predictor 误剔除率缺少 production 级监控接口描述。
- **故障恢复**：predictor 权重与 threshold 的版本一致性、checkpoint 兼容性论文未讨论。
- **正确性**：剔除 token 后 position embedding / RoPE 是否仍与保留 token 的原序列位置对齐——实现细节在 artifact 中，正文假设 permutation-free 不破坏语义，需读代码验证。
- **运维成本**：每层 predictor 需离线预训练（最长约 3h/实验脚本），新增 artifact 依赖（GitHub Pairshoe/Jenga-AE）。

## 局限与 Future Work

- **局限 1**：block-wise 剔除对低冗余长上下文（代码、精确引用）的鲁棒性证据不足；LongBench 部分任务已出现回落。
- **局限 2**：主实验刻意排除 recomputation/offload，与真实大规模训练配置之间有 gap。
- **局限 3**：predictor 需针对模型/数据离线训练，跨模型迁移性未验证。
- **Future work 1**：在代码、对话、多租户混合 trace 上测量 contextual sparsity 比例，建立 workload-aware 的 block size / threshold 自动选择。
- **Future work 2**：与 activation recomputation、[[Quantization]]、ZeRO offload 做正交叠加的端到端测量，明确各瓶颈维度下的 Pareto 前沿。
- **Future work 3**：探索微调阶段学到的 sparsity pattern 是否可蒸馏为 inference 阶段的动态 token pruning，衔接 [[Sparse-Attention]] / prompt compression 路线。

## 相关

- **相关概念**：[[Attention]]、[[LoRA]]、[[Flash-Attention]]、[[Sparse-Attention]]、[[KV-Cache]]、[[Quantization]]
- **同类系统**：LongLoRA（hidden-dim 稀疏 PEFT）、Long Exposure（同作者组，shadowy sparsity 分析）
- **同会议**：[[ATC-2025]]
- **对比**：JENGA（token-level 剔除，省 activation）vs LongLoRA（shifted local [[Attention]]，省 compute 不省 activation）vs [[LoRA]]（省参数，不省 activation）
