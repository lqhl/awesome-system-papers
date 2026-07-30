---
type: paper
name: ProToken
full_title: "ProToken: Token-Level Attribution for Federated Large Language Models"
authors: [Waris Gill, Ahmad Humayun, Ali Anwar, Muhammad Ali Gulzar]
venue: MLSys
year: 2026
tags: [federated-learning, llm, provenance, attribution, privacy]
source_pdf: "[[3988c7f88ebcb58c6ce932b957b6f332.pdf]]"
source_md: "[[3988c7f88ebcb58c6ce932b957b6f332]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# ProToken：联合大型语言模型的标记级归因（MLSys 2026）

> **原题**：ProToken: Token-Level Attribution for Federated Large Language Models

> **一句话总结**：在 FedAvg 线性可分解前提下，ProToken 仅追踪后期 transformer block 的 attention output projection 与 MLP 末层，用 token logit 对 hidden state 的梯度加权 client 激活做 per-token 归因；16 组配置平均准确率 **98.62%**，55 client 规模仍 **>92%**，且全程不访问 raw data。

## 问题与动机

联邦 fine-tune 产出的 global LLM 部署后，医生、风控员等使用者看到异常输出时，无法判断是哪家机构（client）的数据「污染」了哪段生成——调试、公平激励、恶意 participant 识别、信任审计都因此受阻。分类模型上的 neuron provenance（TraceFL 等）无法直接迁移：LLM 是自回归变长生成，且输出可能来自 **预训练先验** 而非联邦更新，责任边界天然模糊。

作者 claim 是：在 **不违反 FL 数据本地化** 的前提下，对给定 prompt 的完整 response 做 **token-level client attribution**，定位主要责任方。该问题在 cross-silo 医疗/金融等协作场景中尤其关键，但此前无针对 federated LLM 生成 provenance 的工作。

## 关键观察 / 隐含假设

- **观察 1**：FedAvg / FedProx 等加权聚合在参数层面是线性的——global neuron 在固定输入下的 pre-activation 可写为各 client 对应 neuron 输出的加权和（Eq. 3–4），为「把 global forward 拆回 client」提供数学基础。
  - **依赖假设**：参与 round 的 client 模型与 global 结构一致；聚合系数 ρᵢ 已知（通常按 |Dᵢ| 比例）；分析在 **单轮聚合后** 的 global 模型上进行。
  - **可能失效场景**：非线性聚合、个性化层（如 [[PLayer-FL-MLSys26]] 式 partial FL）、[[LoRA]] adapter 异构、或 client  dropout 导致 round 间参与集变化时，线性分解前提需重新论证。

- **观察 2**：Transformer 后期 block 编码更多 task-specific 知识；在 attention output projection 与 MLP 末层追踪 provenance，足以捕获 domain 信号，同时把计算从「全参数 × 全 client × 全 token」降到可接受量级（1B 模型、5 client、100 token 的 naive 全 neuron 追踪需 **~5000 亿** 次计算）。
  - **依赖假设**：instruction fine-tune 的 client 特异性主要沉淀在 **最后 N=2 个 block** 的两类线性层；早期层贡献可被梯度加权或层选择吸收。
  - **可能失效场景**：极短 response、强依赖 early-layer 语法改写的任务、或 base model 与 fine-tune 领域差距极大时，后期层信号可能不足；论文 RQ3 显示加深监控层主要增 latency 而非改 top-1 正确率，暗示信号已集中，但 **未** 在「仅早期层有贡献」的合成场景验证。

- **观察 3**：同一 client 在「无关」neuron 上也可能有高激活（如医学 neuron 在生成 "the" 时仍活跃）；用 **∂logit_xj / ∂hℓ** 与 client 激活的内积（Eq. 7）可把归因聚焦到 **因果影响** 当前 token 的维度。
  - **依赖假设**：一阶 gradient × activation 足以近似 transformer 非线性链上的 token 责任；greedy decoding 下 argmax token 的 logit 梯度可代表生成决策。
  - **可能失效场景**：sampling / beam search、logit processor、或 [[Quantization]] 改变梯度行为时，权重机制需重标定；论文 ablation 在 **无梯度** 时 per-layer 均值仅 **35.71%**，说明方法对 gradient 质量敏感。

- **假设 1**：评估可用 backdoor trigger（`!!!BadMagic!!!` → 固定 sentinel refusal）构造 **可验证 ground truth**，且该协议能代表真实「单 client 主导异常输出」场景。
  - **证据强度**：**中**——trigger→sentinel 链路提供 oracle label，16 配置与 55-client 实验均依赖此监督；作者明确承认 **benign / mixed-client diffuse contribution** 无 oracle，当前数字是「可验证条件下」的性能上界。

- **假设 2**：存在 **trusted central server** 存储各 client 模型、运行 post-hoc provenance，且审计用途下可接受 **model-level**（非 sample-level）归因带来的 client 可识别性下降。
  - **证据强度**：**强（在该 threat model 内）**——算法 1–2 假定 server 能 swap client 权重到 global forward 路径；untrusted coordinator、端到端差分隐私部署 **明确 out of scope**。

## 核心方法

**线性分解 + 选择性层注入**：对每个生成 token xⱼ，global 模型先 forward 并记录选定层 ℓ∈L 的 inputℓ_G 与 hidden hℓ_G；再对每个 client i，用 **client 权重 θℓ_i** 在同一 global input 上计算 hℓ_i，等价于观察「若该层只用 client i 参数，激活会是什么」。这与观察 1 直接对应，且 **不读取** client 原始数据。

**Layer set L**：默认每个 block 取 self-attention **output projection** 与 MLP **最后一层线性**，且只监控 **最后 N=2** 个 transformer block（回应观察 2）。成本近似 **O(K · T · |L|)**，T 为生成 token 数、K 为 client 数。

**Gradient-weighted provenance**：对当前 token 计算 gℓ_xj = ∂logit_xj / ∂hℓ_G（Eq. 6），client i 在层 ℓ 的分数为 Pℓ_i,xj = ⟨hℓ_i, gℓ_xj⟩（Eq. 7），跨层求和得 per-token 分（Eq. 8），再对 response 内所有 token 累加（Eq. 9），最后 softmax 得 client 概率分布（Eq. 10–11）。该设计把 autoregressive 依赖「摊平」为逐步累加，并用观察 3 的 relevance 过滤噪声 neuron。

**部署形态**：ProToken 是 **post-hoc audit/debug 层**，不修改 FedAvg/FedProx 训练协议；实现基于 Flower + HuggingFace Transformers，开源于 https://github.com/SEED-VT/ProToken。

## 设计取舍

- **取舍 1**：为 tractability 只分析选定线性子模块 + 后期层，接受对完整非线性 end-to-end 网络只做 **近似** 归因，换取 55 client 规模仍可运行的审计延迟（Gemma 上 3–18 层监控约 **1.1–1.9 s/sequence**）。
- **取舍 2**：用序列级 **求和** 聚合 per-token 分数（而非更复杂的时序模型），简化实现并匹配 backdoor 场景「整段 sentinel 由少数 client 主导」的评估，但可能稀释「仅个别 token 由某 client 主导」的细粒度责任。
- **取舍 3**：归因能力以 **削弱 client 匿名性** 为代价——即使不碰 raw data，也能把生成行为链到具体 model update；论文建议 access-controlled、purpose-limited 调用，并与 DP 等机制组合。
- **边界条件**：在 trigger-grounded、contributing vs non-contributing 二元分离明显的设定下表现极佳；对多 client 温和混合贡献同一 benign 回答、或输出完全来自 base model 先验时，方法 **未给出** 定量表现。

## 实验与结果

- **主结果（RQ1）**：4 架构（Gemma-3-270M、SmolLM2-360M、Llama-3.2-1B、Qwen2.5-0.5B）× 4 领域（医疗/金融/数学/代码），6 client、10 轮 FedAvg，平均归因准确率 **98.62%**（单配置 40–100%）；contributing client 概率与 non-contributing **完全分离**（Fig. 3）。
- **梯度加权（RQ2）**：Round-10 per-layer 平均，有梯度 **66.34%** vs 无梯度 **35.71%**（**1.86×**）；证明 relevance filtering 是可靠归因的必要组件而非锦上添花。
- **计算开销（RQ3）**：监控层数从最后 3 层扩到近乎全层，Gemma 延迟约 **+29%**，但 top-1 准确率保持 **100%**；相对 TraceFL 式全 neuron 追踪，复杂度降 **数量级**。
- **规模（RQ4）**：55 client（25 恶意 + 30 良性）、每轮随机 10 client 参与、15 轮，Gemma **92.00%**、Qwen **95.24%**（相对 6-client 98.62% 仅温和下降）；responsible vs non-responsible 概率分布仍清晰分离。
- **隐私边界**：仅使用 model parameters、activations、gradients；**不**访问本地训练样本。

## 批判性分析

### 论证链条

观察（FedAvg 线性可分解 + 后期层集中 task signal + gradient 可滤噪）→ 层选择 + activation–gradient 内积 + per-token 累加 → 在 backdoor oracle 下 98.62% / 92%+ 准确率，链条在 **「单/少数 client 主导的可验证异常输出」** 子问题内较闭合。关键跳步是：从 backdoor 评估外推到一般 debugging / fair reward——论文诚实标注为 future work，但 Abstract 仍用「real-world deployment」措辞，读者应把数字读成 **审计探针** 而非生产默认性能。

### 假设压力测试

- **生成策略**：实验用 **greedy decoding**；生产常用 temperature / top-p / beam，token 选择路径变化会改变 gradient 目标，归因稳定性 **未测**。
- **模型规模**：最大 1B 级 instruct 模型；7B+ 联邦 LLM 的 |L|、hidden dim、审计延迟与 Flower 多 client 内存 **未覆盖**。
- **混合贡献**：55-client 实验虽有 25 个 contributor，但仍是 trigger 监督下的二元标签；真正 diffuse benign blending（多医院共同塑造一段医学建议）**无 ground truth**，方法可能输出「模糊概率」而非论文展示的清晰分离。
- **先验混淆**：作者承认无法从单次生成区分「client 更新」vs「预训练知识」；motivating example 中 "I'm" 等 token 各 client 归因接近，靠 **整句累加** 才拉开差距——对短回答或高先验占比文本，区分力可能下降。

### 实验可信度

- **Baseline 空缺**：作为首个 federated LLM token provenance 工作，缺少与 TraceFL / FedDebug 等分类 provenance 的「公平移植」对比，也缺少简单 heuristic（如仅比对 client loss、或全局 vs local logits）——高准确率部分反映问题新颖而非压倒性 superiority。
- **评估协议**：backdoor 提供干净 label，但 **5（16 配置）/ 20（RQ2）** 量级 test input 偏少；range 40–100% 暗示部分配置脆弱，论文未深入剖析失败案例（domain × model 交互）。
- **Metric**：主指标是 top-1 client hit rate on poisoned samples；**未**报告 per-token 归因校准、假阳性率（benign 输出误指 client）、或审计 **$/query** 成本随序列长度曲线——系统落地需这些面。

### 系统性缺陷

- **运维**：post-hoc 需保存每 client 每轮模型、对每次调查重跑 multi-client forward + backward；storage 与 **调查延迟** 随 K、T 线性涨，论文将 provenance 定位为 on-demand，但 **未** 给 SLA 或并行化工程数据。
- **尾延迟 / 故障**：部分 client 模型缺失、版本不一致、或 round 间参数漂移时如何归因——**论文未讨论**。
- **与 [[Quantization]] / [[LoRA]]**：联邦 LLM 常配合参数高效 fine-tune 或压缩通信；ProToken 在 adapter-only 或 quantized weight 下是否仍满足线性分解 **未验证**。
- **法律与激励**：fair reward 需要连续贡献度而非二元 culpability，softmax 概率是否满足 Shapley 类公理 **未讨论**。

## 局限与后续工作

- **局限 1**：评估几乎完全依赖 trigger–sentinel backdoor；benign、多 client 混合、无 oracle 场景缺乏基准，当前准确率不宜外推为通用 provenance F1。
- **局限 2**：trusted server + model-level attribution；untrusted aggregator、强匿名需求下的可证明归因 **未解决**。
- **局限 3**：greedy、小模型（≤1B）、FlowerTune 量级数据；更大规模 FL LLM 与多样 decoding 策略下的成本/精度折衷 **未测量**。
- **Future work 1**：构建 **无 backdoor** 的混合贡献 benchmark（合成可控混合比例 + 人工标注子集），测量 attribution 校准而非仅 top-1 accuracy。
- **Future work 2**：在 **7B+** 模型与 sampling decoding 下 profile 端到端审计延迟，并评估 checkpoint 仅存 Δweight 时的近似归因误差。
- **Future work 3**：与 DP、secure aggregation 组合，量化 **归因精度 vs 隐私预算** 的 Pareto 前沿，闭合 deployment trade-off。

## 相关

- **相关概念**：[[LoRA]]、[[Quantization]]、[[Attention]]
- **同类系统**：FedAvg、FlowerTune、TraceFL、FedDebug
- **同会议**：[[MLSys-2026]]、[[PLayer-FL-MLSys26]]
- **对比**：相对 TraceFL 全层全 neuron 分类 provenance，ProToken 用后期层 + gradient 加权把 federated **生成式** LLM 归因降到 O(K·T·|L|)；相对中心化 LLM input attribution，对象是 **client model update** 而非 prompt token
