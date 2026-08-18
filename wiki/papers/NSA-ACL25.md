---
type: paper
name: NSA
full_title: "Native Sparse Attention: Hardware-Aligned and Natively Trainable Sparse Attention"
authors: [Jingyang Yuan, Huazuo Gao, Damai Dai, Junyu Luo, Liang Zhao, "et al."]
venue: ACL
year: 2025
tags: [sparse-attention, long-context, attention-kernel, llm-training, llm-inference, area/ai-infra]
source_pdf: "[[arxiv25-yuan-nsa.pdf]]"
source_md: "[[arxiv25-yuan-nsa]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# NSA：原生稀疏注意力：硬件对齐且原生可训练的稀疏注意力（ACL 2025）

> **原题**：Native Sparse Attention: Hardware-Aligned and Natively Trainable Sparse Attention

> **一句话总结**：NSA 的核心判断是长上下文稀疏注意力必须同时满足“原生训练”和“硬件友好”：用压缩、选择、滑动窗口三分支把每个 query 激活的 token 数压到远小于上下文长度，在 27B MoE 模型上保持或超过 Full Attention 质量，并在 64K context 下报告解码 11.6x、forward 9.0x、backward 6.0x 的加速。

## 问题与动机

论文要解决的是长上下文 [[Attention]] 的双重瓶颈：训练和 prefill 阶段 attention 主要受计算量支配，decode 阶段每生成一个 token 都要读取整段 [[KV-Cache]]，主要受 HBM 带宽支配。作者给出的动机数字是：64K context 解码时，softmax attention 计算可占总延迟 70-80%。因此只降低理论 FLOPs 不够，稀疏模式还必须让 GPU kernel 真的少搬 KV、少做矩阵乘。

现有 [[Sparse-Attention]] 方法在作者看来有两类断点。第一类是只优化一个阶段：H2O 这类方法偏 decode，MInference 偏 prefill，端到端 workload 一旦换成长文档 summarization、repo-level code completion 或 long CoT reasoning，另一个阶段仍接近 Full Attention 成本。第二类是只做 inference-time sparsity：模型先在 Full Attention 下预训练，再推理时剪掉 KV 或选 top-k token，稀疏结构没有进入训练轨迹，可能损伤 retrieval head 或长程依赖。

NSA 的 claim 因此不是“任意 sparse pattern 都能快”，而是“稀疏模式要在模型架构、训练图、GQA/MQA 内存共享和 Triton kernel 上一起设计”。这篇论文把 sparse attention 从 inference trick 推向一类可预训练架构，并试图证明这种架构在长上下文质量上不是退化版 dense attention。

## 关键观察 / 隐含假设

- **观察 1：长上下文 attention 的瓶颈随阶段变化。** 训练和 prefilling 里大批量矩阵乘的 arithmetic intensity 高，倾向 compute-bound；autoregressive decoding 每步只处理一个 query，却要读取长 [[KV-Cache]]，倾向 memory-bandwidth-bound。论文据此把 training/prefill 的目标设为减少计算，把 decode 的目标设为减少 KV 读取。
  - **依赖假设**：目标模型使用现代 GPU 上常见的 GQA/MQA 或类似共享 KV 架构，并且上下文足够长，attention 已成为主要瓶颈。
  - **可能失效场景**：短上下文、batch 很小但非 KV-bound、KV 已被其他系统机制压缩/缓存、或者硬件从 HBM 带宽转向更高带宽内存层级时，NSA 的相对收益会下降。
- **观察 2：稀疏选择必须和 GQA/MQA 的共享 KV 访问对齐。** Quest 等方法按 query head 独立选择 KV，在 MHA 下能减少每个 head 的访问，但在 GQA/MQA 中同组 query head 共享 KV，真实读取量接近这些 head 选择集合的 union。作者据此要求同一 GQA group 内共享 block selection。
  - **依赖假设**：未来主流长上下文模型继续使用 GQA/MQA 来降低 decode KV 带宽；如果模型回到 per-head KV 或采用完全不同的 attention memory layout，这个设计点的价值会变。
  - **证据强度**：中。论文的 kernel 和效率实验直接围绕 GQA group 设计，但没有展示不同 GQA group size、MHA、MQA 之间的敏感性曲线。
- **观察 3：attention score 在序列上有 blockwise clustering。** Figure 8 可视化显示 Full Attention transformer 的 attention map 有空间连续块状结构，临近 key 往往有类似重要性。NSA 用连续 token block 做 selection，而不是 token-level random gather。
  - **依赖假设**：这种块状分布能跨任务、层、模型规模和更长 context 保持，且 block 级选择不会漏掉离散的关键 token。
  - **可能失效场景**：信息高度离散的 retrieval、代码符号跳转、长表格/结构化数据、或需要跨多个稀疏位置做精确对齐的任务，可能更需要 token-granular selection。
- **假设 1：原生稀疏预训练可以弥补稀疏带来的表达损失。** 论文认为 inference-only pruning 会偏离 Full Attention 预训练轨迹，而 NSA 从预训练开始就让模型学习稀疏路径，因此能形成任务适配的 sparse pattern。
  - **证据强度**：中偏强。27B MoE、270B tokens、LongBench/AIME 的结果支持这个方向，但只覆盖一个主要模型族和一个训练设置。
- **假设 2：compressed attention score 足以作为 selected blocks 的重要性信号。** NSA 不另建复杂 indexer，而复用压缩分支的 attention score 推导 block importance，降低额外开销。
  - **证据强度**：中。Figure 7 显示 auxiliary loss-based selection 与 heuristic block selection 在 3B 模型上 loss 更差，但没有完全拆开“compression score 质量”和“三分支架构正则化”的贡献。

## 核心方法

NSA 把每个 query 可看的历史 K/V 重映射为三类更小的表示集合，然后分别做 attention，再用 gate 融合输出。形式上，它不是简单地删掉 KV cache，而是为每个 query 构造 compressed、selected、sliding-window 三个分支；每个分支有独立的 keys/values，最后由输入特征经过 MLP + sigmoid 得到的门控权重加权求和。

**Token Compression** 对应“全局但粗粒度”的路径。历史 K/V 被按连续块聚合，论文默认 compression block size 为 32、stride 为 16，用带 intra-block position encoding 的可学习 MLP 把一块 K/V 压成一个 compressed K/V。这个分支让每个 query 仍能低成本扫到全局上下文，回应的是“长上下文需要 global awareness，但不能完整扫所有 token”的假设。

**Token Selection** 对应“少量精细 token”的路径。只靠 compressed token 可能丢细节，所以 NSA 再把原始 K/V 划成 selection blocks，默认 block size 为 64、selected block count 为 16，其中包含固定激活的初始块和本地块。块重要性来自 compression 分支已经算出的 attention score；当 compression block 和 selection block 粒度不同，作者按空间覆盖关系把 compression score 汇总成 selection score。对 GQA/MQA，NSA 会把同组 query heads 的 selection score 聚合，让它们选择同一组 KV blocks，从而减少 [[KV-Cache]] union 读取。

**Sliding Window** 对应“局部精确性”的路径。NSA 保留一个默认 512 token 的本地窗口，并把它作为独立分支，而不是让 compression/selection 分支顺便处理局部上下文。作者的理由是本地模式学习很快，容易 shortcut 掉远程 compression/selection 的学习；单独的 window 分支可以让其他分支更专注于全局和中程信息。这个设计增加了一点结构复杂度，但避免了“稀疏分支被局部模式压制”的训练问题。

**硬件对齐 kernel** 主要针对 selected attention 分支。[[Flash-Attention]]/[[FlashAttention-2-ICLR24|FlashAttention-2]] 的 dense tiling 通常按连续 query blocks 加载，但 sparse selection 下同一 query block 内不同位置可能需要不同 KV blocks，直接套用会造成不规则访问。NSA 改成以 GQA group 为基本单位：对同一个位置，加载同组所有 query heads 和共享的 sparse KV block indices；随后连续加载被选中的 K/V blocks 到 SRAM，在 Triton grid 上调度外层 query/output 循环。compression 和 sliding-window 分支则可以复用 FlashAttention-2 风格的连续 block kernel。

这个方法的关键不是每个子模块都新，而是三者的组合：compression 给全局摘要和 selection signal，selection 保留关键细节且按 block/GQA 对齐硬件，sliding window 保住本地精度，gate 让模型在训练中学习不同信息源的权重。

## 设计取舍

- **训练友好 vs 完全可微。** NSA 被称为 natively trainable，因为 sparse architecture 直接进入预训练并提供 backward operators；但 top-k block selection 本身仍有离散边界，未被选中的 block 不会得到同等梯度信号。论文证明了端到端训练可行，但没有完全消除稀疏选择的优化不连续性。
- **硬件效率 vs selection 粒度。** 连续 block selection 让 Tensor Core、coalesced load 和 GQA 共享 KV 都更舒服，但牺牲 token-level 精度。block 越大越硬件友好，越小越接近精确 selection；论文默认 64-token selection block 是一个工程点，不一定是所有模型/任务的最优点。
- **三分支表达力 vs 架构/实现复杂度。** Compression、selection、sliding window 加 gate 能覆盖全局、关键细节和局部上下文，但也要求模型结构、KV projection、kernel、训练框架一起改。相比 inference-only KV pruning，NSA 更像新 attention layer，不是一个可以无痛插入任意已有模型的 serving 插件。
- **统一生命周期优化 vs 现有系统兼容性。** NSA 同时覆盖 training、prefill、decode，这是它强于很多 sparse 方法的地方；代价是需要从预训练开始采用该架构。对已经训练好的 Full Attention 模型，NSA 不能直接给出“零训练迁移”的收益。

## 实验与结果

- **模型与训练设置**：实验使用 27B total / 3B active 的 [[MoE]] transformer，30 层、hidden size 2560、GQA groups = 4、64 attention heads；MoE 有 72 routed experts 和 2 shared experts，top-k experts = 6。实验节写明在 8K 文本上预训练 270B tokens，再用 YaRN 做 32K continued training 和 SFT。
- **通用 benchmark**：NSA 在 9 个通用评测平均分 0.456，高于 Full Attention 的 0.443；7/9 指标超过 Full Attention。提升主要来自 BBH、GSM8K、DROP、HumanEval 等项，MMLU 和 MBPP 略低。
- **LongBench**：在相同平均激活 token budget 约 2560 的设置下，NSA 平均 0.469，高于 Full Attention 0.437、Exact-Top 0.423、Quest 0.392、InfLLM 0.383、H2O 0.303。多跳 QA 中 HPQ 比 Full Attention 高 0.087，2Wiki 高 0.051；代码 LCC 高 0.069；但 MFQA-en、GovRpt、PassR-zh 等子项并非全胜。
- **Needle-in-a-Haystack**：64K context 下，NSA 在不同深度位置达到 100% retrieval accuracy。这个结果支持 compression + selection 的 global scan / local precision 组合，但 NIAH 本身是较窄的 synthetic retrieval 测试。
- **CoT reasoning**：用 DeepSeek-R1 蒸馏的 10B tokens、32K 数学推理 traces 做 SFT 后，NSA-R 在 AIME 24 上 8K generation limit 得分 0.121，高于 Full Attention-R 的 0.046；16K 下 0.146 vs 0.092。这个结果说明 NSA 至少能承载长 reasoning trace 的后训练，但只覆盖一个 benchmark 和 supervised distillation 设置。
- **训练/prefill kernel 效率**：在 8-GPU A100 上，Triton NSA attention 相比 Triton FlashAttention-2，64K context 报告 forward 9.0x、backward 6.0x；速度优势随 context length 增长。
- **decode 内存访问**：Table 4 用“等效 token 读取量”估算 decode 阶段 KV 访问，Full Attention 在 64K 需读 65536 token，NSA 为 5632 token，对应 11.6x expected speedup；8K、16K、32K 分别是 4x、6.4x、9.1x。

## 批判性分析

### 论证链条

论文的主链条比较闭合：先指出 inference-only sparse attention 在阶段覆盖、GQA/MQA 访问和训练图上有缺口；再用 compression/selection/window 三分支对应全局摘要、关键细节、本地上下文；最后用质量评测和 Triton kernel 证明“可以训练且实际快”。最强的部分是它没有只停在 FLOPs 复杂度，而是明确把 arithmetic intensity、KV access volume、GQA group sharing 放进算法设计。

跳步主要在“质量提升”的解释上。NSA 在 LongBench 和 AIME 上超过 Full Attention，作者将其解释为原生稀疏训练能学习 task-optimal sparse pattern，并可能过滤噪声。但实验不能完全排除其他因素：三分支 gate 的归纳偏置、训练随机性、MoE backbone 与稀疏 attention 的相互作用、或 long-context adaptation pipeline 细节都可能贡献收益。论文证明了 NSA 不明显伤质量，甚至可提升，但“为什么提升”的因果分解还不够充分。

### 假设压力测试

NSA 最依赖的 workload 假设是长上下文成为常态，而且 attention/KV 是主瓶颈。对短上下文、retrieval 外部化很强的 [[RAG]] 系统、或者大量请求共享 prefix 的 serving 场景，瓶颈可能转向调度、prefix cache 命中、专家加载或网络通信，NSA 的端到端收益需要重新测量。

硬件假设也很明确：A100 + Triton + GQA/MQA + blockwise SRAM/HBM 层级。H100/Blackwell 的 TMA、WGMMA、FP8/FP4 路径，AMD MI300X，或 TPU 上的稀疏访问代价不同，64-token block 与 loop scheduling 未必仍最优。NSA 的思路大概率可迁移，但具体 speedup 不能直接外推。

模型假设方面，论文只在一个 27B MoE 主设置上做完整验证。更小 dense 模型、更大 trillion-scale [[MoE]]、不同 tokenizer/position encoding、million-token context、以及 agent 多轮状态混合输入，都可能改变 blockwise attention locality。尤其是代码库、表格和形式化证明类任务，重要 token 的分布可能比自然语言更离散。

### 实验可信度

基线选择总体合理：LongBench 中和 H2O、InfLLM、Quest、Exact-Top 在相同 activated-token budget 下对比，能说明 NSA 不是只靠“多看 token”。训练支持方面，作者也诚实地只和 Full Attention 对比，因为其他 sparse baselines 不支持同样训练流程。

但实验边界需要读者记住。通用 benchmark 多数样本短于 local window，不能证明长上下文优势；LongBench 排除了一些低分 subset，虽然有理由，但会影响整体代表性；AIME 评测使用 16 samples 平均分，但只用 AIME 24 一个数学集。效率实验是 microbenchmark/attention-kernel 视角，没有展示完整 serving stack 下的 continuous batching、mixed prefill/decode、prefix cache、tensor parallel 或 expert parallel 干扰。

### 系统性缺陷

论文没有充分讨论部署集成成本。NSA 需要自定义 attention layer、三分支 KV、门控、selection metadata 和 Triton kernels；这会影响现有训练框架、checkpoint 格式、推理引擎和调试工具。对 [[vLLM]] / [[SGLang]] 这类 serving 系统，是否能和 paged KV manager、prefix caching、continuous batching、speculative decoding 组合，论文没有给端到端答案。

尾延迟和隔离也未展开。Sparse block selection 的不同 query 可能有不同 block index，虽然 NSA 试图让同组 head 共享选择，但跨 batch、跨 sequence 的 index 分布仍可能造成 kernel load imbalance。论文强调平均 speedup，没有细分 P95/P99 latency、multi-tenant fairness、或 pathological request 下的 worst-case behavior。

最后，NSA 的“trainable sparsity”仍是一种工程上可训练，而不是数学上完全平滑的 sparse routing。top-k 边界、未选 block 的梯度缺失、gate 饱和、compression score 误导 selection 等问题在大规模训练中可能表现为脆弱超参，论文目前主要通过 loss 曲线和下游质量说明其可控。

## 局限与后续工作

- **局限 1：验证范围集中在一个主模型族。** 需要在 dense LLM、不同 GQA group size、不同 [[MoE]] routing、不同 position encoding 和更大 context 上复现质量与速度曲线。
- **局限 2：decode 端到端系统收益未充分证明。** Table 4 的 11.6x 来自等效 KV token 读取量和 memory-bound 假设；还需要在真实 serving engine 中测 TTFT、TPOT、P95/P99 latency、HBM traffic、SM occupancy 和 batch scheduler 交互。
- **局限 3：blockwise locality 可能不是所有任务的规律。** 需要对代码、数学证明、表格、知识图谱、多文档引用等任务测量 attention block entropy 和 missed-critical-token rate。
- **局限 4：架构迁移成本高。** NSA 不能直接用于已经训练好的 Full Attention 模型；从零预训练或长期 continued training 的成本决定了它更适合 frontier model builder，而不是普通部署方。
- **Future work 1：做 production-trace replay。** 用真实长上下文请求 trace 比较 Full Attention、NSA、inference-only sparse attention，在相同 serving stack 中报告吞吐、TTFT/TPOT、P99、HBM traffic、GPU 利用率和失败案例。
- **Future work 2：建立 block selection 的可解释诊断。** 对每层/每头记录 selected block recall、compression score calibration、gate 分布，找出哪些任务需要更细粒度 token selection。
- **Future work 3：跨硬件重调 block/kernel 参数。** 在 H100/Blackwell/MI300X 上系统搜索 compression block size、selection block size、selected block count、window size，判断 NSA 的默认 32/16/64/16/512 是否只是 A100 最优点。
- **Future work 4：和 KV/page 管理合并设计。** 把 NSA 的 selected blocks 暴露给 [[PagedAttention]] 或 [[RadixAttention]] 风格的 KV manager，看能否让 sparse attention、prefix reuse 和 page placement 共享同一套 block abstraction。

## 相关

- **相关概念**：[[Sparse-Attention]]、[[Attention]]、[[KV-Cache]]、[[Flash-Attention]]、[[MoE]]
- **相关系统 / 论文**：[[FlashAttention-2-ICLR24]]、[[FlashAttention-3-NeurIPS24]]、[[DeepSeek-V4-arXiv26]]、[[vLLM]]、[[SGLang]]
- **同类方法**：H2O、InfLLM、Quest、MInference、SeerAttention、HashAttention、ClusterKV
- **同会议**：[[ACL-2025]]
- **对比方向**：[[Flash-Attention]] 是 exact dense kernel 路线，NSA 是硬件对齐的 trainable sparse architecture；inference-only [[KV-Cache]] pruning 方法更容易部署到既有模型，但不能减少训练成本，也很难证明长上下文质量不降。
