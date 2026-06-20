---
type: paper
name: DeepSeek-V4
full_title: "DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence"
authors: [DeepSeek-AI]
venue: arXiv
year: 2026
tags: [foundation, llm, moe, long-context, sparse-attention, quantization]
source_pdf: "[[arxiv26-deepseek-v4.pdf]]"
source_md: "[[arxiv26-deepseek-v4]]"
---

# DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence (arXiv 2026)

> **一句话总结**：在 [[Test-Time-Scaling]] 与 agent 长轨迹共同推高 context 需求的背景下，DeepSeek-V4 用 CSA+HCA 混合压缩稀疏注意力把 1M-token 下单 token 推理 FLOPs 压到 DeepSeek-V3.2 的 27%、[[KV-Cache]] 压到 10%，并配套异构 KV 管理、FP4 QAT、MegaMoE2 与 full-vocabulary OPD 全栈工程，使 1.6T/49B 激活的 V4-Pro-Max 在多数开源基准建立新 SOTA、CorpusQA 1M 达 62.0，但仍落后 Gemini-3.1-Pro 知识项与 Opus 4.6 的 MRCR 1M（83.5 vs 92.9）。

## 问题与动机

论文的核心 claim 不是「再训一个更大的 [[MoE]]」，而是把 **百万 token context 从实验室能力变成可 routinely deploy 的产品能力**。作者认为两条趋势叠加制造了硬瓶颈：

1. **[[Test-Time-Scaling]] / reasoning model**：更长 thinking trace 直接放大序列长度与 [[KV-Cache]] 体积。
2. **Long-horizon agent**：跨文档分析、多轮 tool call、保留完整 reasoning history 都需要远超 128K 的有效 context。

现有开源模型（含 [[DeepSeek-V3]] 系）在通用能力上已很强，但 vanilla [[Attention]] 的 $O(n^2)$ 计算与 KV 线性增长，使 1M context 在算力、显存、尾延迟上仍不可承受。DeepSeek-V3.2 的 [[Sparse-Attention]]（DSA）缓解了部分问题，但论文 Figure 1 显示在 1M 设定下仍远不够：V4 要把 **attention FLOPs + KV 存储** 同时砍一个数量级，否则 test-time scaling 与长程 agent 无法规模化。

因此 V4 是 **架构 + 训练 + 推理 + post-training 基础设施** 的 bundled release：preview 版放出 V4-Pro（1.6T total / 49B activated）与 V4-Flash（284B / 13B activated），均原生支持 1M context。

## 关键观察 / 隐含假设

- **观察 1：超长 context 下 attention 同时主导 FLOPs 与 KV，且二者可联动压缩**
  - **证据**：Figure 1 对比 V3.2，1M 时 V4-Pro 单 token FLOPs 为 27%、KV 为 10%；相对 BF16 GQA8 baseline，KV 约 2%。效率讨论节把收益归因于 CSA/HCA 序列压缩、混合精度 KV、indexer FP4、更小 top-k。
  - **依赖假设**：有效信息在序列上 **可分层压缩**——近端依赖靠 sliding window（$n_{\mathrm{win}}=128$），远端靠压缩块 +（CSA 层）top-k 稀疏选择即可覆盖任务需求。
  - **可能失效场景**：需要精确访问任意远距离单 token（经典 needle-in-haystack 变体）、强依赖未压缩细粒度共现的检索/证明任务；压缩块内因果性受限（query 不能看同块内其他 token，只能靠 SWA 补局部）。

- **观察 2：MoE EP 的通信时间可完全被计算掩盖，瓶颈在 compute/comm 比值而非裸带宽**
  - **证据**：§3.1 profiling 显示单层 MoE 通信总时长 < 计算；wave-based fine-grained EP 在 NVIDIA / Ascend 上 1.50–1.96× 加速。
  - **依赖假设**：每 token-expert 通信量（3h bytes FP8 dispatch + BF16 combine）相对 SwiGLU 计算量（6hd FLOPs）满足 $C/B \leqslant 2d \approx 6144$ FLOPs/Byte；集群有足够 **功耗余量** 支撑 compute+comm+memory 同时满载。
  - **可能失效场景**：RL rollout 等长尾小 batch、专家极度不均衡、或未来去掉 gate 投影后中间维变大导致比值恶化；论文也指出 push-based 细粒度通信仍受硬件信令延迟限制。

- **观察 3：混合异构 KV（压缩块 + SWA state + 未就绪 tail buffer）无法直接套 [[PagedAttention]]，必须 co-design layout 与 kernel**
  - **证据**：§3.6.1 明确写出 PagedAttention 对 layer 间 block 大小一致性的假设被 CSA/HCA/SWA 打破；采用 classical KV cache + fixed-size state cache，block 覆盖 $\mathrm{lcm}(m,m')$ 原始 token。
  - **依赖假设**：serving 框架愿意接受 **定制 KV 子系统**（含 on-disk prefix、SWA 三种策略 trade-off），而非复用 vLLM/SGLang 通用路径。
  - **可能失效场景**：多租户共享 prefix 命中率低、SSD 写放大严重（Full SWA Caching）、或需要严格 KV 迁移/弹性扩缩的标准化 serving 接口。

- **假设 1：压缩 + 稀疏不会显著伤害预训练收敛后的长程能力，只要训练课程与 indexer warmup 到位**
  - **证据强度**：**中**。32–33T token 课程含 4K→1M 渐进、前 1T dense attention、64K 起引入 sparse + indexer warmup；LongBench-V2 base 51.5（Pro）优于 V3.2 40.2。但 MRCR 在 128K 后仍有可见衰减（Figure 9），说明压缩并非无损。
  - **可能失效场景**：分布外超长文档、训练未覆盖的压缩率/稀疏模式、或 post-training RL 在 1M rollout 上的稳定性（论文强调 infra，但未给 1M RL 的质量消融）。

- **假设 2：领域专家 → full-vocabulary on-policy distillation（OPD）可替代 mixed RL 合模，且不会明显损伤统一模型**
  - **证据强度**：**中偏弱**。benchmark 上 Pro-Max 全面领先开源，但 agent 仍略逊 closed frontier；OPD 依赖 10+ teacher、centralized storage、hidden-state 缓存等重型工程，**可复现成本高**。
  - **可能失效场景**：teacher 分布冲突、student 容量不足以同时拟合多域 reverse KL；新域增量时是否必须重跑全流程——论文未讨论 continual OPD。

## 核心方法

### Hybrid CSA + HCA Attention

V4 在多数层 **交错** 两种注意力：

- **Compressed Sparse Attention (CSA)**：每 $m{=}4$ 个 token 的 KV 加权压缩为 1 条 entry（overlap 设计使有效压缩率 $\frac{1}{m}$）；再用 lightning indexer（低秩 query + ReLU score）做 top-k 选择（Flash top-k=512，Pro=1024），对选中压缩块做 shared-KV [[Attention|MQA]]；辅以 partial RoPE（末 64 维）、attention sink、grouped output projection。
- **Heavily Compressed Attention (HCA)**：更大压缩率 $m'{=}128$，**不做稀疏**，对全部压缩块做 dense MQA；用于需要全局但可容忍强压缩的层（Flash 前 2 层为纯 SWA，Pro 前 2 层为 HCA）。

二者均加 **sliding window branch**（128 token 原始 KV）弥补块内因果盲区。Indexer 与部分路径走 **FP4**，KV 存储为 RoPE 维 BF16 + 其余 FP8。

该设计直接回应「1M context 下 attention 与 KV 双瓶颈」：CSA 砍 FLOPs，HCA 砍 KV 体积，SWA 保底局部精度。

### mHC、Muon 与 V3 继承组件

- **Manifold-Constrained Hyper-Connections (mHC)**：扩展残差流到 $n_{hc}{\times}d$，把残差映射矩阵 $B$ 投影到 doubly stochastic 流形（Sinkhorn-Knopp, $t_{\max}{=}20$），约束谱范数 $\leqslant 1$ 以稳定深层堆叠；工程上 fused kernel + 选择性重计算，wall-time 开销约 6.7%（相对 1F1B pipeline）。
- **Muon optimizer**：大部分权重用 hybrid Newton-Schulz 正交化更新；embedding/head/RMSNorm/mHC 静态偏置仍用 AdamW；配合 ZeRO knapsack、MoE 梯度 BF16 同步、两阶段 all-to-all→local FP32 sum。
- **继承**：[[MoE|DeepSeekMoE]]、MTP、auxiliary-loss-free 负载均衡；改动包括 affinity $\sqrt{\mathrm{Softplus}}$、前几层 Hash routing MoE、序列级 balance loss。

### 训练与推理基础设施

- **MegaMoE2**：wave 级 EP 通信-计算重叠 fused kernel，开源为 DeepGEMM 组件。
- **TileLang**：DSL 融合算子；Host Codegen 把 Python 校验开销降到 $<1\,\mu$s；Z3 辅助整数分析；默认禁用 fast-math 以保 bitwise reproducibility。
- **Batch-invariant + deterministic kernels**：attention 双 kernel 策略；sparse attention / MoE backward 用 per-SM buffer 避免 atomicAdd 非确定性——服务于 RL/OPD 与调试。
- **FP4 QAT**：MoE expert 权重 + CSA indexer QK path；FP4→FP8 dequant 无损（利用 FP8 额外 exponent bit）；rollout 用真 FP4 权重对齐部署。
- **Contextual Parallelism**：两阶段通信处理 CP 边界上的压缩块对齐；支持 1M 训练。
- **异构 KV + on-disk prefix**：classical cache（按 $\mathrm{lcm}(m,m')$ 分块）与 state cache（SWA + 未压缩 tail）分离；CSA/HCA 压缩 KV 可落盘，SWA 提供 Full / Periodic / Zero 三策略权衡存储与重算。

### Post-Training：专家 → OPD

1. **Specialist Training**：分域 SFT + [[GRPO]] RL（math/code/agent/instruction），含 Non-think / Think High / Think Max 三档 reasoning effort；难验证任务用 **Generative Reward Model**（actor 兼 judge）。
2. **On-Policy Distillation**：10+ teacher 的 full-vocabulary reverse KL；teacher 权重 offload + hidden state 缓存 + mini-batch 单 head 轮换，TileLang 算 KL。
3. **Agent infra**：token 级 WAL 的 preemptible rollout；DSec sandbox（Function Call / Container / microVM / fullVM 统一 SDK，3FS + EROFS/overlaybd，trajectory log 支持抢占恢复）。

V4 在 tool-calling 场景 **跨 user turn 保留完整 thinking trace**（利用 1M window），并引入 Quick Instruction special tokens 复用 KV 做并行辅助任务（搜索意图、query 生成等）。

## 设计取舍

- **取舍 1：极致长 context 效率 vs 架构简洁与 serving 通用性**
  - 收益：1M 可部署、KV/FLOPs 数量级下降、可与 [[Prefix-Caching]] / on-disk 结合。
  - 代价：layer 间 KV 形态不一，**放弃** 直接套用 [[PagedAttention]]；推理栈、稀疏 kernel、padding 规则与压缩率 co-design，第三方复现与二次开发门槛高。作者自己在 §6 承认架构「relatively complex」。

- **取舍 2：压缩 + 稀疏 vs 检索保真度**
  - 收益：短中长序列均可调（更小 top-k 改善短文本效率）。
  - 代价：indexer top-k recall 并非 100%（FP4 QAT 后 top-k selector 仍 99.7% KV recall）；块内信息靠 SWA 128 补偿，对「同块远距离依赖」仍可能丢信号。

- **取舍 3：OPD 合模 vs mixed RL**
  - 收益：避免 weight merge 损伤，logit 级对齐更稳定（相对 token-level advantage 近似）。
  - 代价：训练管线更重（多 teacher、centralized storage、异步 load）；蒸馏偏差难以用单一 benchmark 分解到各 teacher。

- **边界条件**
  - **优雅场景**：长文档 QA、跨轮 agent（tool path）、shared-prefix 批量推理、MoE 大 batch 训练。
  - **变脆场景**：超低延迟短 prompt（压缩/indexer 固定开销）、高 churn 无 prefix 复用、需要标准 KV 迁移的 [[Disaggregation]] 部署、Terminus 类「伪 user 消息」agent 框架（论文明确不推荐 think 模型）。

## 实验与结果

- **效率（1M context）**：V4-Pro 单 token FLOPs = V3.2 的 **27%**，KV = **10%**；V4-Flash = **10% / 7%**；routed expert 权重 FP4，未来硬件理论还可再省 1/3 FP4×FP8 算力。
- **预训练 base（Table 1）**：V4-Flash-Base（13B act）在多数项超 V3.2-Base（37B act），LongBench-V2 **44.7 vs 40.2**；V4-Pro-Base 进一步全面领先（MMLU 90.1，LongBench-V2 **51.5**）。
- **Post-train Pro-Max vs frontier（Table 6）**：
  - Knowledge：SimpleQA-Verified **57.9**（开源领先，+20pt 量级），但仍低于 Gemini-3.1-Pro；MMLU-Pro **87.5**。
  - Reasoning：HMMT 2026 **95.2**，IMOAnswerBench **89.8**，Codeforces rating **3206**（人类 rank 23）；作者称首次开源匹敌 GPT-5.4 量级。
  - Long-context：CorpusQA 1M **62.0** > Gemini-3.1-Pro **53.8**；MRCR 1M **83.5** < Opus 4.6 **92.9**。
  - Agent：Terminal Bench 2.0 **67.9**（Verified 子集 ~72.0），SWE-Verified **80.6**，BrowseComp **83.4**；仍落后部分 closed（如 SWE-Verified Opus 4.6 80.8 vs GPT-5.4 75.1 等混杂，需看子集）。
- **Flash-Max**：以更小参数在 reasoning 上逼近 GPT-5.2 / Gemini-3.0-Pro（Table 7，LiveCodeBench Max **91.6**）。
- **真实任务**：内部 R&D coding Pass Rate **67%**（Sonnet 4.5 47%，Opus 4.5 70%）；85 人调研 **52%** 愿作默认 coding model；中文写作对 Gemini-3.1-Pro win rate **62.7%**；白领任务对 Opus 4.6-Max non-loss rate **63%**。
- **训练规模**：Flash 32T / Pro 33T tokens；序列课程 4K→16K→64K→1M；batch 最大 75.5M / 94.4M tokens。

## Critical Analysis

### 论证链条

论文的主线 **observation（1M 下 attention+KV 爆炸）→ design（CSA/HCA + 精度 + infra）→ result（FLOPs/KV 曲线 + 1M benchmark）** 在效率段闭合较好：Figure 1 与 §2.3.4 把机制与数量级对齐。能力段则部分依赖 **「更长 context + 更多 thinking token」** 的外推：Max mode 在 HLE、Terminal Bench 等显著提升（Figure 10），但需区分 **算力预算增加** 与 **架构本身** 的贡献。

较弱的一环是 **压缩稀疏注意力对真实 long-horizon agent 的充分性**：CorpusQA 领先 Gemini，但 MRCR 仍明显落后 Opus，说明「可部署 1M」≠「1M 检索无损」。作者用 SWA、sink、interleaved HCA 修补，但是否覆盖所有 agent trace 模式，实验只覆盖部分 harness（内部 bash/file-edit，512K agent eval cap）。

### 假设压力测试

| 假设 | 论文已证明 | 推断风险 |
|------|-----------|----------|
| 1M KV/FLOPs 可降一个数量级 | 有 analytic + Figure 1 | 短 prompt TTFT、indexer 固定成本可能被低估 |
| 压缩稀疏不毁长程能力 | LongBench/CorpusQA 提升 | MRCR 128K+ 衰减；needle 类任务未系统报告 |
| OPD 可替代 mixed RL | 端到端 benchmark 领先开源 | teacher 冲突、域外泛化、增量新域成本未测 |
| EP overlap 泛化到 RL rollout | 1.96× 长尾场景 | 极端 expert skew、跨机拓扑变化时是否仍成立 |
| FP4 部署对齐训练 | QAT + 真 FP4 rollout | 非 MoE/indexer 路径、CPU offload 等论文未讨论 |

### 实验可信度

- **强项**：base 模型对比统一 internal framework（Table 1）；效率指标有开源实现锚点；真实任务补充了 benchmark 盲区（中文写作、白领、内部 coding）。
- **弱点**：
  - 与 closed model 对比存在 **API 不可用**（K2.6/GLM-5.1 部分空白，GPT-5.4 长 context 未评），削弱「追近 frontier」结论的可比性。
  - Agent 评测 **高度依赖内部 tool schema**（`\|DSML\|` XML tool call），对外部框架迁移性未知。
  - Terminal Bench 2.0 环境争议被承认，仍报原始集数字。
  - 效率数字以 **equivalent FP8 FLOPs** 和 **累计 KV** 为主，**端到端 serving latency / 成本/$** 论文未给出生产级 SLA 表。

### 系统性缺陷

- **尾延迟**：batch-invariant dual-kernel 缓解 wave quantization，但 1M prefill 的 P99、磁盘 KV 命中失败时的重算延迟——论文未讨论。
- **资源隔离**：on-disk KV、DSec 大规模 sandbox 与训练抢占共存，运维复杂度高；故障模型除 rollout WAL 外 **论文未讨论** 在线 serving 降级。
- **可观测性**：deterministic kernel 利于调试，但压缩 indexer 的 miss 率、SWA 重算比例等 **生产 telemetry** 未涉及。
- **兼容性**：与通用 [[Continuous-Batching]] / [[Disaggregation]] 栈集成成本大；第三方在不掌握 TileLang/MegaMoE2 时难以复现完整性能。
- **正确性**：压缩注意力无形式化误差界；formal math 结果依赖 Lean agent 设置，与通用对话正确性不同维度。

## 局限与 Future Work

- **局限 1（作者承认）**：为控风险保留大量已验证 trick（SWA、sink、partial RoPE、Hash MoE 等），架构 **臃肿**；Anticipatory Routing、SwiGLU Clamping 有效但机理不清。
- **局限 2（从实验边界推出）**：1M 检索仍逊于最强 closed；知识类仍落后 Gemini-3.1-Pro；Flash 在复杂 agent 上明显弱于 Pro。
- **局限 3**：Preview 版本——完整训练细节、开放权重下的 reproducibility、与社区 serving 栈对接仍待观察。

- **Future work 1（可验证）**：在 **固定算力预算** 下对比 CSA/HCA vs 纯 DSA vs 线性 attention，扫 needle/recall vs compression rate $m,m'$ 的 Pareto 曲线。
- **Future work 2**：量化 **heterogeneous KV + on-disk SWA 策略** 在真实 prefix 分布下的 TTFT、$/1M-token、SSD 写放大——直接决定「routinely supported」是否成立。
- **Future work 3（作者方向）**：蒸馏简化架构、探索 embedding 等新高维稀疏、低延迟交互、多模态与更强数据合成。

## 相关

- **相关概念**：[[KV-Cache]]、[[MoE]]、[[Sparse-Attention]]、[[Attention]]、[[Quantization]]、[[Expert-Parallelism]]、[[Prefix-Caching]]、[[PagedAttention]]、[[Test-Time-Scaling]]、[[RAG]]
- **同类系统 / 模型线**：[[DeepSeek-V3]]（前驱）、[[MSA-arXiv26]]（另一条长上下文稀疏路线）、[[AttnRes-arXiv26]]（残差路径重构，与 mHC 精神相关）、[[MoE-nD-arXiv26]]、[[FluxMoE-arXiv26]]
- **基础设施对照**：[[fabric-lib-MLSys26]]（跨厂商 P2P RDMA，可支撑大规模 disaggregated serving）、[[vLLM]]、[[SGLang]]（通用 serving 栈，KV 管理假设与 V4 不同）
- **主题**：[[Foundation]]
- **深度细节**：回读 [[arxiv26-deepseek-v4]] / [[arxiv26-deepseek-v4.pdf]]