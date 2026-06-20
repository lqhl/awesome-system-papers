---
type: paper
name: AssyLLM
full_title: "AssyLLM: Efficient Federated Fine-tuning of LLMs via Assembling Pre-trained Blocks"
authors: [Shichen Zhan, Li Li, Chengzhong Xu]
venue: ATC
year: 2025
tags: [federated-learning, llm-fine-tuning, model-assembly, edge-computing, memory-optimization]
source_pdf: "[[atc2025-zhan.pdf]]"
source_md: "[[atc2025-zhan]]"
---

# AssyLLM: Efficient Federated Fine-tuning of LLMs via Assembling Pre-trained Blocks (ATC 2025)

> **一句话总结**：FedLLM 的瓶颈是 BP 激活占满 4–16 GB 边端内存、导致 60–85% 客户端无法参与；AssyLLM 把多个预训练 LLM 拆成 block 池，客户端用 inference + CKA/COR 兼容性打分选 block 组装下游模型，仅对少量 Elastic Adapter 做轻量训练，在 BoolQ/PIQA/OBQA 上比 memory-constrained 基线高 18.26%、加速 30×、内存降 92%。

## 问题与动机

[[Federated-Learning]] 微调 LLM（FedLLM）的价值在于边端数据不出域，但本地 fine-tuning 的内存墙把大量低端设备挡在门外。论文用 200 客户端、五档内存预算（4–64 GB）的模拟 FedLLM 环境测量：Llama-7B 全量微调要 45+ GB，OPT-6.7B 要 32+ GB，结果 85% Llama 客户端和 60% OPT 客户端无法参与，相比 oracle 全参与场景精度掉 14.7–19.1%。

现有省内存路线各有硬伤。[[LoRA]] / [[QLoRA]] / FedAdapter 等 [[PEFT]] 仍要 15+ GB，主因是 forward 激活而非可训练参数本身；QLoRA 虽把参与率提到 70%，但比 oracle 仍低 5.3%。BP-free 路线如 FwdLLM 把内存压到 3.8 GB、实现 100% 参与，但 forward gradient 估计不准，精度比 oracle 低约 5.8%，non-IID 时误差累积更严重。系统层 recomputation / swapping 能保住精度并全参与，但 BoolQ 上训练时间从 8.73 h 涨到 27.6 h（1.78–3.17×），用 I/O 和重算换内存。

作者的核心 pivot 是：既然 block 选择只需少量 inference，能否把「微调」重定义为「从多个预训练 LLM 的 block 池里搜索并组装任务专用模型」，从而绕开大部分 BP 相关内存开销，同时让更多客户端贡献本地数据？

## 关键观察 / 隐含假设

- **观察 1：FedLLM 精度损失的主因是参与率，而不只是单客户端算力不足。** Figure 1 显示 memory budget 直接决定能参与的客户端比例，进而影响聚合数据多样性；FT-practical 在 BoolQ/PIQA/OBQA 上比 FT-oracle 低 13–19 个百分点。
  - **依赖假设**：被排除的 4–8 GB 客户端持有与高端设备互补的 local data；把它们拉进来能显著提升全局模型，而不是只引入噪声。
  - **可能失效场景**：若低端客户端数据质量差、标签噪声高，或 Dirichlet non-IID 极端偏斜，全参与未必单调提升精度。
- **观察 2：不同预训练 LLM 的中间层表征分布显著不同，但 block 级输出仍可用 CKA + layer-correlation 度量兼容性。** t-SNE 显示 OPT vs Llama、OPT vs RoBERTa 同输入下中间特征簇分离；单独 CKA 或 COR 都不足以选最优 block（分别可掉 9.1% / 3.4%），二者结合才稳定。
  - **依赖假设**：下游任务收益来自「跨架构 block 混搭」带来的表达力扩展，且 LLM 冗余足以容忍 moderate 结构/语义不一致。
  - **可能失效场景**：需要严格连贯生成、长上下文推理或单一架构 inductive bias 的任务；encoder-only block 拼进 decoder-only 生成链可能伤害 coherence——论文任务以 QA 分类为主，未覆盖 open-ended generation。
- **观察 3：block 选择阶段的内存主导项是 block pool，而非 BP 激活。** 五模型 block 池 FP16 要 42.2 GB；INT8/INT4 统一量化分别带来明显精度波动（INT4 掉 5.8% 且方差 8.9%）。Block Quanter 按 weight 对 block 输出 activation 的敏感度做混合精度，比 layer-wise 方案更省分析开销。
  - **依赖假设**：block 输出 activation 对权重扰动敏感度的离线分析可迁移到联邦各轮的在线选择；关键权重集合在任务间相对稳定。
  - **可能失效场景**：任务分布快速漂移、block pool 扩容或频繁换模型时，离线敏感度图需重算，edge 上 preparation cost 上升。
- **假设 1：「无 BP」主要指 block 搜索路径；少量 Elastic Adapter 训练仍可接受。** 多数拼接只需线性投影；仅语义/attention 严重不匹配时才训练 cross-attention adapter，并冻结 backbone。这仍是在 forward-dominant 流程里嵌了一条窄 BP 通道。
  - **证据强度**：中。论文证明 adapter 参数很少、激活可丢弃，但没有给出相对 FwdLLM 的严格内存 accounting 分解。
- **假设 2：服务器维护共享 block 池，客户端每轮只下载当前 assembled candidate 并上传 top-K block 索引 + 轻量 adapter。** 通信量比传 LoRA 权重小 99.1%，但初始 block 池分发和版本一致性依赖中心侧存储。
  - **证据强度**：强。索引级上传在 Table 4/5 的 FL 设定下可测；但论文未讨论 block 池更新、模型 license 混用、以及 cold-start 分发延迟。

## 核心方法

AssyLLM 把联邦 fine-tuning 拆成多轮 **block assembly search**，流程见 Figure 7：预训练 LLM 手工切成 starting / intermediate / terminating blocks 构成池；每轮客户端拿到当前 assembled model \(N_s\)，在本地 corpus 上对候选 block \(B_{nl}\) 做两次 inference（assembled model vs 源 LLM 前 \(l\) 层），用输出激活算兼容性分，选 top-K 上传；服务器按 compatibility 加权投票（类 FedAvg）把获胜 block 叠到 \(N_s\) 上，直到选出 terminating block 或触达深度上限。

四个模块分别对应设计挑战：

**Block Comparator** 用 CKA 衡量 assembled block 与源 block 最终激活对齐，用 COR（逐层 activation 分布的 KL 散度之和）补足中间层差异。兼容性分指导每轮搜索，避免只靠启发式层号拼接。

**Elastic Adapter** 处理跨模型拼接的三类 mismatch：维度（线性投影）、语义（cross-attention，用前一 block 输出作 Q、后一 block 作 K/V）、attention head 数（pool/expand）。论文强调多数中间拼接只需 projection，trainable adapter 仅在最终少数关键拼接点启用，从而大部分时间可丢弃中间激活——这是内存收益的关键机制。

**Block Quanter** 对 block 池做 offline 混合精度：先按 weight sparsity 过滤，再用 random perturbation / masking 评估对 block 输出 activation 的影响，bottom-up 保留高相关权重为 INT8、其余 INT4（结合 GPTQ）。相对统一 INT8/INT4，在 BoolQ 上实现约 70% 内存节省且精度只降 1.1%。

**Block Swapper** 在设备 memory budget 内管理 block 驻留：LRU + block correlation 决定换出对象；pre-loading 与 memory-aware pre-swapping 流水化 I/O。swap 次数增加时，pre-loading 降本地时间 30.21%，叠加 pre-swapping 再降 68.12%。

实现上混合 A100 仿真（高内存客户端）与 Jetson TX2/Nano 真机（4–8 GB）。200 用户按 Figure 13 分四组内存；non-IID 数据用 Dirichlet \(\alpha=1\)。细节见 [[atc2025-zhan]]。

## 设计取舍

- **用搜索式组装换传统梯度更新**：避免大规模 BP 激活，但放弃对单一 base model 全参数或 even LoRA 子空间的直接优化；最终模型是离散路径上的 assembled artifact，不是连续权重空间里的最优解。
- **heterogeneous block pool 换表达力与内存**：引入 Llama、OPT、Vicuna、BERT、RoBERTa 共 28 blocks，增强任务适配，但 block 池常驻或换入成本远高于单模型 PEFT；Block Quanter + Block Swapper 是为此付出的系统复杂度。
- **兼容性启发式换可证明收敛**：CKA/COR 是 representation similarity 代理，不是任务 loss 梯度；选择过程无收敛定理，依赖联邦投票稳定重复好 block。
- **窄 adapter BP 换拼接可行性**：完全 BP-free 会保留 FwdLLM 的梯度估计误差；AssyLLM 只在 mismatch 严重时开 adapter 训练，在内存与精度间折中，但工程上仍要维护「何时开 adapter」的分支逻辑。
- **边界条件**：QA / 分类式下游、7B 级模型、中心服务器持有完整 block 池时设计最顺；超大模型、纯 on-device pool、或 strict latency SLO 的在线联邦更新会更脆。

## 实验与结果

- **主精度（vs algorithm baselines，non-IID）**：BoolQ 78.12%、PIQA 83.39%、OBQA 62.47%，比 FT-practical 高 16.75–18.26%；比 [[LoRA]] / [[QLoRA]] / FedAdapter 高 8.24–13.09%；比 FwdLLM 高 6.14–8.88%。值得注意的是 BoolQ 上 AssyLLM 甚至略高于 FT-oracle（75.11%），作者归因于更高参与率带来的数据多样性。
- **主速度**：相对 algorithm baselines 加速 10.97–14.67×；相对 recomputation / swapping 达 26.75–30.04×（后者 speedup <1×，因 I/O 与重算拖慢）。
- **内存与参与率**：比全量微调峰值内存降 92%，比 PEFT 基线再降 63.6%；最低 4 GB 设备可参与，而 QLoRA 仍需约 15+ GB。
- **non-IID 鲁棒性**：Dirichlet \(\alpha\) 变尖锐时，基线最多掉 14%，AssyLLM 掉 4.6%，仍领先基线 27.2%；因 local data 主要驱动 block 选择而非直接改 block 权重。
- **资源成本（BoolQ）**：能耗降 95.01%，通信降 99.1%（相对全量微调）；相对 PEFT/BP-free 也有 88.1% / 94.2% 量级节省。
- **消融**：CKA-only −9.1%、COR-only −3.4%；Elastic Adapter +3.02–5.17%；Block Quanter FP16→mixed 内存 −70.2%、精度 −1.1%；Block Swapper 流水优化显著降低 swap 延迟。
- **组装多样性**：搜索过程生成 21 个 assembled LLM，块数与大小分布广泛（Figure 14），说明路径搜索空间非平凡。

## Critical Analysis

### 论证链条

论文链条清晰：先量化 FedLLM memory wall → 证明 PEFT/BP-free/系统法三角不可兼得 → 提出 inference-only block search → 用四组件解决 pool 兼容性、异构拼接、pool 体积、swap I/O → 在精度/速度/内存/通信上同时取胜。Observation 与 module 映射明确，ablation 支持 CKA+COR、Elastic Adapter、Block Quanter、Block Swapper 各自必要性。

最大跳步在 **「组装模型 ≡ fine-tuned LLM」** 的隐含等同。实验任务是 BoolQ / PIQA / OBQA 等短序列 QA，metric 是 top-1 accuracy，本质上接近分类/选择式评估；这有利于 block 混搭，但不能直接外推到 generative fine-tuning、tool use、对话安全对齐等需要全链路一致性的场景。论文声称「避免 repetitive finetuning」，但实际仍有多轮联邦搜索 + 少量 adapter 训练，与「一次组装即交付」之间有距离。

另一跳步是 **相对 FT-oracle 的精度优势**。AssyLLM 在部分数据集上超过无内存限制的 full fine-tuning，作者解释为参与率提升；但 FT-oracle 与 AssyLLM 优化的是不同模型族（单一 Llama-7B vs 异构组装），比较并非同架构同参数量下的公平 upper bound，更像「更多数据 + 更大假设空间」的收益，而非纯粹 memory 优化的结果。

### 假设压力测试

**Block pool 组成策略**是最大未闭合环节。Discussion 承认「选哪些预训练 LLM 入池」仍靠经验（架构多样性），不同组合波动明显；扩展到 13B/30B 时 pool 体积与 swap I/O 压力非线性上升。没有 task embedding 或 domain proxy 指导 pool 构建时，生产部署可能要先在中心侧做昂贵搜索。

**异构拼接合法性**在真实部署中可能遇阻：Llama、OPT、Vicuna 权重许可不同；BERT/RoBERTa encoder block 与 decoder stack 拼装的部署工具链（tokenizer、position embedding、chat template）论文未讨论。系统正确性上，assembled 模型是否保留原模型 safety alignment 与行为可预测性，论文未覆盖。

**non-IID 实验强度中等**：Dirichlet \(\alpha\) sweep 有用，但仍是 200 客户端模拟 + 三个 NLP benchmark，缺少真实移动联邦 trace（电量、网络抖动、掉线、异步聚合）。Block Swapper 在 eMMC/UFS 慢存储上的尾延迟，论文只在 Jetson 上部分验证。

**「无 BP」表述需打折**：Elastic Adapter 训练仍是 localized backprop；若下游任务频繁触发 semantic mismatch 分支，内存优势会向 PEFT 方案收敛。论文没有给出「adapter 触发率 × 内存峰值」的敏感性曲线。

### 实验可信度

优点：baseline 覆盖面好（FT-oracle/practical、[[LoRA]]、[[QLoRA]]、FedAdapter、FwdLLM、recomputation、swapping），同时报 accuracy 与 speedup；non-IID、组件消融、真机 Jetson 与 A100 仿真结合，不是纯模拟器数字。通信/能耗指标对 FL 论文少见且有说服力。

短板：任务面偏窄，全是英文 QA，序列长度 256–512；没有 perplexity、生成质量、instruction-following、多轮对话或更大模型（>7B）结果。FT-oracle 基线固定 Llama-7B INT8，而 AssyLLM 可利用多模型 block，**比较对象不完全同构**。FwdLLM、FedAdapter 等 FL 基线的超参是否与 AssyLLM 同等调优，论文宣称调优但细节有限。

精度提升幅度部分来自 **对比 FT-practical 而非 FT-oracle**；若只看相对 oracle 的增益，BoolQ 上 +3 points 仍不错，但 18.26% 的 headline 需要读者记住 baseline 是 memory-limited 场景。21 个 assembled model 如何选取最终部署模型（server 侧 compatibility 过滤）会影响 reported test accuracy 的可复现性。

### 系统性缺陷

- **可观测性与运维**：assembled 模型由多源 block 组成，线上行为 debug、版本回滚、A/B 对照比单 checkpoint 困难；论文未讨论 lineage tracking 与兼容性回归测试。
- **故障恢复**：联邦轮次中客户端掉线、block 索引冲突、swap 失败或 partial pool 不一致时的聚合语义，论文未讨论。
- **尾延迟与 SLO**：Block Swapper 优化的是 swap 次数与平均时间，没有端到端联邦轮次 deadline、慢客户端 straggler 处理或异步聚合策略。
- **隔离与安全**：不同租户是否共享同一 block 池、adapter 是否泄漏本地表征、assembled 模型是否可能组合出未预期的能力组合，论文未讨论。
- **部署路径**：组装完成后如何导出为单一 Hugging Face 权重、如何与 [[vLLM]] / [[SGLang]] 等 serving 栈对接，论文未讨论。

## 局限与 Future Work

- **局限 1**：block pool 构建缺乏 principled 策略，组合波动大；更大 LLM 下 pool 内存与 I/O 仍是硬瓶颈。
- **局限 2**：任务评估局限在短序列 QA，未验证生成式联邦微调、工具调用或安全对齐场景。
- **局限 3**：「无 BP」依赖少量 Elastic Adapter；严重异构拼接时内存/复杂度优势可能缩小。
- **局限 4**：异构权重混用的 license、tokenizer 对齐、部署一致性论文未触及。
- **Future work 1**：用 task embedding、domain-aligned pretraining 或 proxy task 自动构造 block pool，并测量 pool 大小 vs 精度饱和点。
- **Future work 2**：在 13B/30B 与真实移动 trace 上测 Block Swapper 尾延迟、掉线率与能耗，建立 memory budget–participation–accuracy 的可扩展曲线。
- **Future work 3**：与 Harmony、Oort 等 non-IID / client selection 机制正交组合，验证是否进一步放大参与率收益。
- **Future work 4**：定义 assembled model 的 export、serving 与 rollback 接口，并评估对生成质量与安全性的长期影响。

## 相关

- **相关概念**：[[Federated-Learning]]、[[LoRA]]、[[Quantization]]、[[PEFT]]、FedAvg、CKA、Adapter-Tuning
- **同类系统**：FedAdapter、FwdLLM、[[QLoRA]]、FedHybrid、Harmony
- **同会议**：[[ATC-2025]]
- **对比**：相对 FwdLLM 用精确但窄的 adapter BP 换 BP-free 梯度估计误差；相对 recomputation/swapping 用离散 block search 换连续权重优化与训练时间