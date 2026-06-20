---
type: paper
name: ASI-ARCH
full_title: "AlphaGo Moment for Model Architecture Discovery"
authors: [Yixiu Liu, Yang Nan, Weixian Xu, Xiangkun Hu, Lyumanshan Ye, et al.]
venue: arXiv
year: 2025
tags: [auto-research, neural-architecture-search, multi-agent, linear-attention, llm-agent, scaling-law]
source_pdf: "[[2507.18074v1.pdf]]"
source_md: "[[2507.18074v1]]"
---

# AlphaGo Moment for Model Architecture Discovery (arXiv 2025)

> **一句话总结**：ASI-ARCH 用 Researcher/Engineer/Analyst 多 agent 闭环在 linear attention 子领域以 DeltaNet 为 seed 自主跑完 **1,773 次实验 / ~20,000 GPU hours**，筛出 **106 个自称 SOTA 架构**；在 340M/15B token 验证下代表模型平均 benchmark 比 Gated DeltaNet 高约 **1–2 点**，并报告 SOTA 累计数与 GPU hours 近似线性的「科学发现 scaling law」——但论文未测推理效率、未做 pipeline ablation，且 SOTA 判定高度依赖 LLM judge 与窄 benchmark。

## 问题与动机

作者的核心悖论是：AI 系统能力指数增长，但 **AI 研究本身仍线性受限于人类认知带宽**。传统 [[Neural-Architecture-Search]] 只在人类预定义的 building block 空间里做组合优化，本质是 automated optimization 而非 automated innovation；近期 [[AI-Scientist-arXiv24]]、[[AlphaEvolve-arXiv25]]、[[FunSearch-Nature24]] 等多聚焦代码/算法/数学证明，尚未有人把 **神经网络架构创新** 的完整科研环——假设生成、代码实现、训练验证、洞察归纳——交给完全自主系统跑通。

作者选择 **linear attention** 作 testbed：该子领域知识密集、设计空间组合爆炸（[[Linear-Attention]]、SSM、[[Sparse-Attention]]、hybrid 等），且人类专家设计单款 SOTA 往往需数月迭代。ASI-ARCH 的 claim 不是「更好的 NAS 搜索器」，而是首个在架构发现域演示 **ASI4AI（Artificial Superintelligence for AI research）** 的系统：AI 能自主提出人类未写进 search space 的新机制，并用算力 scale 研究产出。

## 关键观察 / 隐含假设

- **观察 1**：在固定 DeltaNet 谱系与 sub-quadratic 约束下，**更多 GPU hours 能线性换来更多「超过 baseline 的架构」**——Figure 1 显示 SOTA 累计数与总计算小时强线性相关。
  - **依赖假设**：搜索策略、候选池更新、LLM 能力在 20k GPU hours 内保持稳定；SOTA 定义在 exploration 与 verification 两阶段前后一致；linear attention 设计空间的「好架构密度」足够高，使随机+进化采样不迅速饱和。
  - **可能失效场景**：换 seed 架构（非 DeltaNet）、换任务域（vision、MoE LLM）、或 LLM 代际变化后，斜率可能坍塌；单次运行上的相关性不能证明可复现的 universal scaling law。
- **观察 2**：top-50 候选池的 **raw loss / benchmark 持续改善**，而 composite fitness 因 sigmoid 饱和后平台化——说明系统在进步且 sigmoid 抑制了单指标 reward hacking。
  - **依赖假设**：探索阶段每 benchmark 仅 **500 samples** 的近似评估与全量评估单调相关；loss 低于 baseline 10% 即判 info leakage 的规则能过滤作弊实现。
  - **可能失效场景**：小样本 benchmark 排名与 15B 全量训练排名可能错位；sigmoid 也会掩盖后期真实增益幅度，使进化方向难以区分「微小改进」与「显著突破」。
- **观察 3**：106 个 model gallery 架构相对其余样本，**analysis 渠道贡献更高（44.8% vs 37.7%）**，cognition 仍占 ~49%，纯原创仅 ~6.6%——SOTA 更依赖对自身实验历史的抽象归纳，而非死记文献。
  - **依赖假设**：Analyzer 提供的 parent/sibling 对比足以模拟 ablation；LLM 对 design provenance 的三分类（cognition / analysis / original）可信。
  - **可能失效场景**：provenance 由 LLM 事后分类，无 ground truth；parent-child 代码 diff 与 motivation 文本可能不一致，分析结论会误导下一代 Researcher。
- **假设 1**：**LLM 同时写 motivation 与 code** 可避免 implementation drift，且 Engineer 的 error-log 自愈环能挽救大部分实现错误。
  - **证据强度**：**中**——对比 [[AlphaEvolve-arXiv25]] 的 discard-on-failure 策略，自愈确实减少浪费；但论文未量化「多少次迭代才训通」「多少 proposal 死于 novelty/sanity check」。
- **假设 2**：**linear attention + 20M/340M 语言建模 benchmark** 足以代表「架构创新」价值，无需 custom kernel 即可判定优劣。
  - **证据强度**：**弱**——Discussion 明确承认未写 Triton 等加速 kernel，**推理延迟/吞吐完全未测**；架构发现的终极目标在部署效率，当前评估偏训练期 proxy。

## 核心方法

ASI-ARCH 是围绕 **Researcher → Engineer → Analyst** 三角色 + **Cognition** 知识库的四模块闭环（Figure 4），所有实验写入中心数据库（MongoDB + FAISS 相似检索），多 agent 并行通过 API 共享历史。

### Fitness Function（反 [[Reward-Hacking]]）

$$\mathrm{Fitness} = \frac{1}{3}\left[\sigma(\Delta_{\mathrm{loss}}) + \sigma(\Delta_{\mathrm{benchmark}}) + \mathrm{LLM_{judge}}\right]$$

- 量化部分只关注相对 DeltaNet **±10%** 内的 loss/benchmark 差，经 sigmoid 压到 [0,1]，防止极端值 dominate；loss 低于 baseline 10% 直接丢弃（视为 information leakage）。
- [[LLM-as-Judge]] 按 1–10 分评 architectural innovation、复杂度、实现正确性、收敛性；校准锚点为 DeltaNet=5、Gated DeltaNet=10。
- 设计意图：纯 benchmark 优化会 hack 指标；加入定性 judge 模仿人类专家审稿。代价是 **评估环嵌入了与 Researcher 同族的 LLM 偏见**，且 judge 与 planner 可能共享训练分布偏好（gating、conv 等）。

### Researcher：提新架构

- **Seed selection**：维护 top-50 候选池；每步从 top-10 随机选 1 个 parent 直接改代码，从 11–50 抽 4 个 reference 仅作示例，平衡 exploitation 与 diversity。
- **动态摘要**：历史 architecture 的 motivation/result/analysis 用低温 LLM 现场摘要，**不存库**，同一历史每次呈现略有不同，刻意增加 context 随机性。
- **统一实现 agent**：先写 motivation 再写 code，保持设计推理一致；类名强制仍为 `DeltaNet`，保证与 FLAME 训练栈兼容。
- **Novelty & Sanity Check**：motivation embedding 检索 top-5 相似历史，再由 LLM 判是否真创新；静态检查强制 sub-quadratic、causal mask 正确、batch-agnostic。失败则带反馈 rewrite。

### Engineer：训练、评估与自愈

- 在真实代码环境用工具启动训练、改代码、读 log；失败则将 **完整 error log 回灌 agent** 迭代修复，而非 [[AlphaEvolve-arXiv25]] 式 AST 失败即丢。
- 训练期 QA：监控异常低 loss（leakage）或训练时长为 peer 2–3× 的架构，主动 kill 并要求修订。
- 量化评估后用 LLM-as-judge 做定性打分；探索阶段每 benchmark **限 500 samples** 加速筛选。

### Analyst：Cognition + Contextual Analysis

- **Cognition base**：从 ~100 篇 linear attention 经典论文抽取 1–3 条结构化 cognition（scenario / algorithm / context），按当前实验短板做 embedding 检索，相当于 RAG 式文献记忆。
- **Contextual Analysis**：把当前节点与 phylogenetic tree 上 **parent + sibling** 的实验结果一并喂给 Analyzer，意图模拟 ablation，推断组件贡献；结论归档供下轮 Researcher 使用。

### Exploration-then-Verification 与并行策略

| 阶段 | 规模 | 训练 | 评估 | 资源 |
|------|------|------|------|------|
| Exploration | ~20M params | 1B tokens | 500 samples/dataset | ~10k GPU h，1,773 次 |
| Verification | 340M params | 1B → 15B tokens | 全量 harness | ~10k GPU h，~400→106 SOTA |

并行策略：**cold start 前 200 次不更新候选池** 促广度探索；之后 **每 50 次才批量刷新 top-50**，避免过早收敛。底层 LLM 为 O3（规划/分析）+ GPT-4.1（训练/debug/dedup）混合。

## 设计取舍

- **创新广度 vs 验证成本**：两阶段 + 小模型快筛使 1,773 次探索可行，但引入 **scale transfer risk**——20M 上的优胜者未必在 340M/15B 保持排序。
- **单 agent 实现 vs 专业化分工**：统一 Researcher 减少 drift，但单 context 窗口要同时承担创意、代码、约束检查，复杂架构更易出隐性 bug。
- **LLM judge vs 纯客观指标**：降低 benchmark hacking，却把「什么是好架构」部分外包给主观模型；与 Researcher 同源模型，存在 **自指评估** 风险。
- **DeltaNet 单 seed vs 多起点**：单 baseline 使 fitness 与进化树可解释、实验可比，但强烈偏向 **Delta 谱系上的 gating/router 微创新**，难发现与 DeltaNet 正交的全新 family。
- **边界条件**：在 **sub-quadratic attention、中小语言模型、Fineweb-edu、GPT-2 tokenizer** 设定下框架最优雅；要迁移到 production LLM（长上下文、[[MoE]]、prefill/decode 分离）需重做约束、基准与工程栈。

## 实验与结果

- **探索**：1,773 次自主实验，~10,000 GPU hours（20M/1B）；1,350 个候选同时在 loss 与 benchmark 上 beat DeltaNet。
- **验证**：~400 个 340M 架构训练 1B tokens 后，**106 个** 被标为 SOTA 并公开至 Model Gallery；5 个代表模型在 **340M/15B** 上与 DeltaNet、Gated DeltaNet、Mamba2 对比。
- **主结果（Table 1，10 项平均）**：PathGateFusionNet **48.51**、ContentSharpRouter **48.34**、FusionGatedFIRNet **48.29**、HierGateNet **48.24**、AdaMultiPathGateNet **48.18**；均高于 Mamba2（47.84）、Gated DeltaNet（47.32）、DeltaNet（46.54）。单项如 FusionGatedFIRNet 在 LAMBADA ppl **33.44** vs Gated DeltaNet 38.69。
- **搜索动力学**：top-50 平均 raw benchmark ↑、raw loss ↓ 贯穿全程；fitness 快速上升后平台化，与 sigmoid 设计一致（Figure 6）。
- **复杂度**：参数分布在 400–800M 区间探索后稳定在 400–600M 为主，**无系统性堆参数换分**（Figure 8）。
- **组件偏好**：SOTA gallery 更集中使用 gating、convolution 等成熟 primitive，长尾冷门组件更少——呈现「在 proven parts 上迭代」而非纯追新。
- **Provenance（Table 3）**：gallery 的 analysis 占比 **44.8%** > 其余 **37.7%**；cognition ~49%，original ~6–10%。

## Critical Analysis

### 论证链条

作者链条为：**人类带宽瓶颈** → **NAS 只能搜人类空间** → **LLM 多 agent 闭环可自主假设+实现+验证** → **1,773 次实验产出 106 SOTA + 线性 scaling law** → **ASI4AI 可行**。中间最脆弱的一环是 **「SOTA」与「科学发现可线性 scale」的定义**：SOTA 先由 20M/抽样 benchmark 筛选，再经 340M 部分确认，仅 5 个做 15B 全量对比；读者看到的「106」与 Table 1 的「5 个代表」不是同一证据强度。Figure 1 的 scaling law 是 **单次 campaign 内累计曲线**，缺少不同算力预算下的独立重复实验，更像 **resource–yield 经验曲线**，而非严格控制下的定律。

### 假设压力测试

- **Workload**：全程固定语言建模 + commonsense QA；未测长上下文、代码、多模态或推理密集型任务。发现的 gating/router 模式可能只对 **DeltaNet 类 recurrent-linear hybrid** 有效。
- **硬件/部署**：训练用 FLAME + bf16，无 Triton/CUDA kernel 定制；**相同参数量下的推理 TFLOPs、内存带宽、prefill latency 未知**，难以判断能否替换生产中的 [[Flash-Attention]] / Mamba 栈。
- **规模外推**：最大验证 340M/15B tokens，相对当今 multi-billion LLM 仍差数量级；1–2 点的 average benchmark 提升是否保持到 7B+ 未验证。
- **正确性/SLO**：mask 与复杂度有静态检查，但无形式化验证；并行多 agent 写代码的 **可复现性、版本漂移、数据库竞态** 论文未讨论；运维上 20k GPU hours 的成本与失败实验处置策略也未透明化。

### 实验可信度

- **Benchmark 代表性**：探索阶段 500-sample 子集可能放大方差，使 1,350「promising」候选中部分为噪声；LM-Eval 平均与 Wiki/LAMBADA 等单项改进幅度不一致，需警惕 **aggregate metric 掩盖退化维度**。
- **Baseline 公平性**：对比 DeltaNet/Gated DeltaNet/Mamba2 使用相同训练协议是加分项；但 **106 个 SOTA 未与同期人类新架构（如其他 2025 linear attention 论文）** 系统对照，SOTA 声明范围偏窄。
- **Ablation 缺失**：作者承认未拆解 Cognition vs Analysis vs 自愈 Engineer vs LLM judge 各贡献多少；无法判断是 **pipeline 设计** 还是 **算力堆砌** 主导结果。
- **评估闭环**：LLM 既生成架构又评审架构，缺少人类专家盲评或 hold-out 物理指标（steps/sec、显存）；judge 校准仅两点（DeltaNet/Gated DeltaNet），**区分度可能不足**。

### 系统性缺陷

- **工程/product gap**：Discussion 直言未做 accelerated kernel，发现架构停留在 research PyTorch 层，离部署差一整条 **systems 工程链**（kernel fusion、量化、并行策略）。
- **搜索空间隐性边界**：强制 `DeltaNet` 类名、sub-quadratic、chunkwise 实现、固定 head/hidden 约束，使「Move 37」式突破更像 **受约束的局部突变**，而非开放架构发明。
- **可观测性**：开源 framework + cognitive traces 是加分项，但并行 1,773 实验的 **失败模式分类、human intervention 次数、API 成本** 未系统披露。
- **尾延迟/隔离**：非在线服务系统，论文未讨论；作为 [[Multi-Agent-System]] 长时间运行，agent 错误累积对数据库污染的防护机制未述。

## 局限与 Future Work

- **局限 1（论文承认）**：搜索仅从 **单一强 baseline DeltaNet** 初始化，进化树高度同源；多架构并行初始化可能发现不同 family，但算力需求陡增。
- **局限 2（论文承认）**：**无 pipeline 组件级 ablation**——Cognition、Analysis、自愈 Engineer、LLM judge 的边际价值未知。
- **局限 3（论文承认）**：**无推理效率基准**；未写 custom kernel，无法比较 discovered architecture 在真实 serving 约束下的优劣。
- **Future work 1**：在 **固定算力预算** 下对比 ASI-ARCH vs 人类专家 vs 传统 NAS 的 **Pareto 前沿**（质量、样本效率、多样性），验证 scaling law 可重复性。
- **Future work 2**：对 top-5 架构做 **组件级消融 + kernel 级实现 + 长上下文/大规模训练**，检验 20M proxy 排名是否 hold，并量化每 1% benchmark 提升对应的 inference 成本。
- **Future work 3**：将 Cognition/Analysis 模块抽象为可插拔策略，在 **非 attention 域**（MoE routing、diffusion block）做跨域迁移实验，测试 ASI4AI 框架是通用科研基础设施还是 linear attention 特化工具。

## 相关

- **相关概念**：[[Attention]]、[[Sparse-Attention]]、[[Neural-Architecture-Search]]、[[LLM-as-Judge]]、[[Multi-Agent-System]]、[[Reward-Hacking]]、[[MoE]]
- **同类系统**：[[AlphaEvolve-arXiv25]]、[[AI-Scientist-arXiv24]]、[[AI-Scientist-v2-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[FunSearch-Nature24]]、[[Auto-Research-arXiv25]]
- **baseline 架构**：DeltaNet、Gated DeltaNet、Mamba2（论文核心对照）
- **同主题**：[[Auto-Research]]