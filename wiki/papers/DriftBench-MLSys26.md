---
type: paper
name: DriftBench
full_title: "DriftBench: Measuring and Predicting Infrastructure Drift in LLM Serving Systems"
authors: [Gianluigi Vitale]
venue: MLSys
year: 2026
tags: [llm-serving, monitoring, infrastructure-drift, safety, quantization]
source_pdf: "[[4c56ff4ce4aaf9573aa5dff913df997a.pdf]]"
source_md: "[[4c56ff4ce4aaf9573aa5dff913df997a]]"
---

# DriftBench: Measuring and Predicting Infrastructure Drift in LLM Serving Systems (MLSys 2026)

> **一句话总结**：基于「workload 决定 drift 敏感度（Math 16.74% vs Code 0.09%，186×）且硬件/精度 drift 可外推、框架/模型不可外推」的观察，DriftBench 用 236,985 对 prompt-response × 105 配置测 flip rate，PRI 在未见硬件 R²=**0.909**、未见精度 R²=**0.763**；生产 H100/FP16→B200/FP8 升级拦截 **23.85%** safety flip，Evidently 零告警。

## 问题与动机

生产 LLM serving 频繁做基础设施变更：GPU 代际升级（H100→B200）、[[Quantization]] 降本（FP16→FP8/FP4）、框架迁移（[[vLLM]]→[[SGLang]] / TensorRT-LLM）。隐含假设是**同权重、同输入应功能等价**；实践中输出会 flip，而吞吐/延迟/perplexity 等常规验收指标往往仍通过。

作者将 **infrastructure drift** 定义为：在输入与模型权重不变时，因 serving stack（硬件架构、数值精度、推理框架）变化导致的**功能正确性**改变，用 flip rate 量化。这与 data drift（输入分布变）、concept drift（数据生成过程变）正交——现有 ML 监控（Evidently、WhyLabs、Arize 等）统计 input-output 分布，无法捕捉 kernel 实现、浮点舍入顺序、量化 rounding 等计算路径差异。

动机案例包括 Anthropic 2025 年跨 Trainium/GPU/TPU 部署 Claude 时数周间歇性质量退化。DriftBench 要填补的是 **pre-deployment gating 与 post-deployment monitoring 之间的空白**：在上线前系统测量并预测基础设施迁移的功能风险，而非提出 drift 修复算法（论文明确 mitigation 为 open challenge）。

## 关键观察 / 隐含假设

- **观察 1**：Drift 幅度高度 **workload-dependent**，单 workload benchmark 会严重低估风险。420 组 configuration×workload 测量显示 Math 平均 flip **16.74%**、Safety **7.97%**、Code 仅 **0.09%**（Math vs Code **186×**；Safety vs Code **88×**）。全局 ANOVA 中 workload 解释方差最大（F=53.60，η²=0.275），precision/framework 主效应在全局层面不显著，但分层后 precision 对 safety、framework 对 math 显著。
  - **依赖假设**：五类 workload（Code/Math/Safety/Chat/Long-context）及各自 evaluator（pass@1、exact match、LlamaGuard-3、embedding similarity、F1）能代表生产关心维度；baseline 固定为 H100/FP16/[[vLLM]]，所有 target 与之对比。
  - **可能失效场景**：agent 多轮 tool-use、结构化 JSON、多模态、RAG 带检索上下文等未覆盖任务；evaluator 本身（LlamaGuard recall 85.21%）会引入 label noise；生产 temperature>0 时 flip 幅度约降为 deterministic 的 **~23%**（论文 4.2），但方向性风险仍在。
  - **证据强度**：强。236,985 评测 + Wilson 95% CI + 分层 ANOVA 一致。

- **观察 2**：基础设施因子分裂为 **systematic**（硬件、精度）与 **idiosyncratic**（框架、模型）两类 drift。PRI 在 held-out dimension 上：未见硬件 R²=**0.909**、未见精度 R²=**0.763**（predict-once 可部署）；未见 framework R²=**0.479**、未见 model R²=**0.118**（必须重新实测）。
  - **依赖假设**：GPU 规格与精度格式构成相对连续的参数空间，interaction features（hardware×precision、framework×workload）能捕捉非加性效应；训练集覆盖 4 GPU × 3 precision × 3 framework × 5 model 的 105 可行配置（计划 625 中 **84%** 可行）。
  - **可能失效场景**：仅 4 个 GPU 平台、3 种精度，physics-enhanced 特征在 held-out 测试上 R²>0.99 却被判为过拟合（附录 A.1）；新框架（DeepSpeed-Inference、TGI）几乎必然落入 idiosyncratic 区；TPU/Inferentia 等非 GPU 加速器未验证 dichotomy 是否成立。
  - **证据强度**：中到强。held-out dimension 协议严谨，但样本多样性有限，framework/model 低 R² 也可能部分来自数据稀疏而非本质不可预测。

- **观察 3**：Safety-critical 部署中，**双向 flip** 使 net accuracy 极具误导性。生产案例 H100/FP16/[[SGLang]]→B200/FP8/[[SGLang]]：520 AdvBench prompts 上 **23.85%** 分类翻转（65 safe→unsafe，59 unsafe→safe），净 unsafe 率仅 +1.15%（314→320）——aggregate metric 看似 benign。
  - **依赖假设**：LlamaGuard-3-8B 二分类 + 人工标注校验（85.21% recall）足以刻画 safety boundary 变化；同一框架（SGLang→SGLang）可隔离硬件+量化效应。
  - **可能失效场景**：guardrail 模型与 serving 模型不同源时，flip 可能混合 evaluator drift；contradictory refusal（先拒答再给有害步骤）等模式需人工判读，自动化指标难全覆盖。
  - **证据强度**：强。有完整 case study 与 concrete prompt-response 对；Evidently 对照（3% functional flip vs 2% embedding shift、0 failure flagged）支撑监控缺口 claim。

- **假设 1**：Deterministic decoding（seed=42，temperature=0，greedy）可把采样噪声与 infrastructure 效应分离，测得的是 drift **上界**。
  - **证据强度**：中。控制实验在 minor/major 软件版本更新上零 functional flip；stochastic 验证（temp=0.7，N=5）显示 drift 仍存在但幅度降 **77%**，论文建议生产用 ~0.23× scaling factor 估算。

## 核心方法

**测量框架**：DriftBench 在 2,257 prompts × 105 configurations 生成 **236,985** prompt-response 对。配置空间：5 模型（Llama-3.1-8B/70B、Mistral-7B、Mixtral-8x7B、Qwen-7B）、4 GPU（H100/H200/B200/MI300X）、3 框架（[[vLLM]] 0.11.0、[[SGLang]] 0.5.2、TensorRT-LLM 1.0.0）、3 精度（FP16/FP8/FP4）。单请求、无 batching 干扰，固定软件环境，确保观测 drift 可归因于基础设施。

**Flip rate（Track 1）**：对有 ground truth 的任务（Code/Math/Safety/Long-context），correct↔incorrect **双向**计 flip；比 lexical similarity 更贴近运维语义（代码能否跑通、safety 边界是否维持）。Chat 无 GT，用 embedding cosine shift（SDR，阈值 0.30）测 semantic drift。

**PRI（Portability Risk Index）**：XGBoost 回归 drift rate，56 维特征 = one-hot（hardware/precision/framework/model/workload）+ pairwise interaction + 1 derived feature。训练 80/20 + 5-fold CV；**部署相关指标**是 held-out dimension R²（整类 hardware/framework/model/precision 从训练集剔除），而非 random split 的 R²=0.987。操作流程：PRI 先 screening——systematic 变更可 predict-once + 100 prompts 确认；idiosyncratic 变更 block 直至全量实测；组合变更高风险需直接 measurement（Scenario C）。

**三类 flip taxonomy**：(1) Safety flips（guardrail 失效，最高风险）；(2) Correctness flips（可验证任务算错）；(3) Semantic drift（离题、非语言输出等，perplexity 不可见）。方法映射：观察 1 → 五 workload 分层评测；观察 2 → PRI interaction + held-out dimension；观察 3 → 双向 flip 为主指标。实现与 31 个验证脚本见 [[4c56ff4ce4aaf9573aa5dff913df997a]] / [[4c56ff4ce4aaf9573aa5dff913df997a.pdf]]；开源 DriftBench CLI 与 AE artifact。

## 设计取舍

- **测量优先于缓解**：只做 risk assessment 与 pre-deployment gating，不提出 drift compensation——降低 scope，但运维仍需自行决定 canary/回滚/多配置路由。
- **Deterministic 换因果可归因**：消除采样 confounder，代价是高估生产 stochastic serving 下的 flip（论文给出 ~4× 折算经验）；保守策略适合 safety gating。
- **Aggregate PRI 换部署效率**：可预测 configuration 级 drift rate，不能预测**哪些 prompt**会 flip——省全矩阵 420 次实测，但高 flip 场景仍需 workload-specific 全量或 canary。
- **固定 baseline 换可比性**：所有配置对比 H100/FP16/[[vLLM]]，便于横向比较，但生产迁移路径若非以此为起点，需重定 baseline 或补测。
- **边界条件**：单机 1–4 GPU、decoder-only 7B–70B 最贴合；framework/model 变更、FP4 on B200（12.7% flip）、combined hardware+precision 升级最脆；纯 code workload 上 infrastructure 变更往往可乐观放行。

## 实验与结果

- **规模**：236,985 对 × 105 配置 × 525 configuration×workload 实验；Chat 用 SDR，其余四 workload 共 420 flip-rate 测量。
- **PRI held-out dimension**：Hardware R²=**0.909**，Precision R²=**0.763**，Framework R²=**0.479**，Model R²=**0.118**；训练 R²=1.000，random-split test R²=**0.987**（论文强调后者非外推指标）。
- **Workload 敏感度**：Math **16.74%**、Safety **7.97%**、Long-context **1.55%**、Code **0.09%**；Chat SDR **12.4%**。
- **高风险配置**：B200+FP4 **12.7%** flip；Llama-3.1-70B Math FP16→FP8 **11.2%**；Qwen Safety vLLM→TensorRT-LLM **9.8%**；生产 H100/FP16→B200/FP8 Safety **23.85%**（拦截部署）。
- **vs 现有监控**：H100/FP16→FP8、100 prompts 上 DriftBench 检 **3%** functional flip，Evidently **2%** embedding shift、**0** failure flagged。
- **PRI feature importance**：workload_safety **33.4%** + framework_tensorrt **25.1%** = **58.5%**；hardware 主效应 <**0.3%**（但 interaction 支撑 hardware held-out 预测）。
- **Ablation**：hardware-only R²=**-0.018**；linear R²=**0.235**；无 interaction 的 RF R²=**0.756** vs 完整 XGBoost R²=**0.998**（test 0.987）。
- **Stochastic 补充**：temp=0.7 下 aggregate drift 从 8.3%→1.9%（**-77%**），Math 仍 **5.6%**、Safety **2.7%** residual。
- **部署指引（论文 4.3）**：systematic 变更可用 PRI + 100 prompts 验证（H100→H200 预测 2.1%、实测 2.3%）；建议 workload-specific drift budget（safety 0.5–1.0%，code 0.1–0.5%）。

## Critical Analysis

### 论证链条

「基础设施变更可改变功能正确性，且现有监控看不见」→「多 workload flip rate 测量揭示 186× 差异与 systematic/idiosyncratic 分裂」→「PRI 在 hardware/precision 上外推、在 framework/model 上失败」→「生产 23.85% safety flip 被拦截」链条在论文声明的 **单机开源 LLM serving** scope 内基本闭合。作者没有把 PRI 低 R² 的 framework 维粉饰成可用，与 Table 2 / Scenario B/C 叙事一致。

薄弱跳步在于：**从 105 配置矩阵外推到任意生产迁移路径**。许多真实升级同时变 hardware+precision+framework（论文 production case 仍固定 SGLang），PRI 对组合变更的误差界未系统给出；held-out test R²=0.987 与 held-out dimension R² 差距大，读者若误用前者会高估 PRI。

另一跳步：**flip rate 作为唯一 gating 指标是否足够？** 7.97% 平均 safety drift 与 23.85% 个案并存，说明 configuration-specific 效应远大于 workload 均值；PRI 捕捉 aggregate trend，对「是否放行本次具体升级」仍需实测兜底。

### 假设压力测试

- **Workload 变化**：未覆盖 agentic 多步、function calling、MoE 路由、speculative decoding（论文 future work 点名）。若 draft model 与 target 在不同基础设施上行为不一致，flip 机制更复杂，DriftBench 五类 workload 可能不够。
- **硬件/部署变化**：仅 4 GPU、单机 NVLink/Infinity Fabric；175B+ 分布式、[[Disaggregation]] prefill/decode 分离、dynamic batching、continuous batching 下 kernel 与舍入路径可能不同。论文承认云 TPU/Inferentia 需 empirically validate dichotomy。
- **精度与量化栈**：FP16/FP8/FP4 为主；INT8/INT4、per-layer mixed precision（[[Hawkeye-MLSys26]]、[[MixLLM-MLSys26]] 路线）未测。量化与 [[PagedAttention]] / [[RadixAttention]] 交互可能引入额外非确定性。
- **Evaluator 依赖**：Safety 靠 LlamaGuard-3；guardrail 与 served model 不同步时，flip 可能部分来自 judge drift 而非 served output 功能变化——论文用 85.21% recall 人工校验缓解但未消除。
- **时间维度**：一次性 snapshot 测量；框架小版本、CUDA driver、cuDNN 升级导致的 gradual drift 未建模——与 [[SpecDecodeBench-MLSys26]] 强调的「生产 engine 版本敏感」类似风险。

### 实验可信度

- **Baseline 公平性**：对比 Evidently 仅 100 prompts、单一 H100→FP8 过渡，方向正确但样本小；未与 MLPerf accuracy 子集、Robustness Gym、量化评测（如 LLM-FP4）等更强 baseline 对比 functional consistency。
- **Benchmark 代表性**：HumanEval/GSM8K/AdvBench/LMSYS/LongBench 是标准集，但不同于企业私有 prompt 分布；Chat 用 embedding threshold 0.30，与 functional flip 不可直接横比。
- **PRI 验证**：held-out dimension 协议优于 random split，值得肯定；但 4 GPU × 3 precision 稀疏，physics features 过拟合被拒说明数据量制约 claims 上限——R²=0.909 是「当前数据下诚实的上限」而非「硬件 drift 本质上高度可预测」的定理。
- **Production case**：单模型单路径（Llama-3.1-8B-Instruct），说服力强；缺少多租户、多模型混部、在线 A/B 的长期跟踪。

### 系统性缺陷

- **无 mitigation / 在线闭环**：测量后如何 canary、灰度、自动回滚、双栈 serving，论文仅给 qualitative guidance（drift budget、block deploy），无 CI/CD 集成实现（列为 future work）。
- **尾延迟与吞吐**：刻意不评 performance regression，运维需另跑 [[SpecDecodeBench-MLSys26]] / MLPerf 类 benchmark——功能与性能正交但生产 gate 通常要 jointly 决策。
- **Per-prompt 预测缺失**：23.85% flip 下运营商无法知道哪 124 条 prompt 会变；routing 高熵 prompt 到稳定配置需未来「prompt-level sensitivity features」。
- **可观测性集成**：与 Evidently/WhyLogs/Arize 的 embedding/statistical pipeline 如何并存、告警语义如何统一，论文未讨论。
- **成本模型**：全矩阵测量 236,985 次推理的成本与 PRI 节省的 15→3 配置验证（附录 I）仅在 illustrative scenario 出现，缺 enterprise-scale ROI 曲线。
- **单作者独立研究**：实验全在 cloud GPU（RunPod）；无工业 co-author，production validation 为单案例 self-reported，外部复现依赖开源 artifact。

## 局限与 Future Work

- **局限 1**：贡献边界是 **measurement + risk prediction**，不含 drift-aware serving、自动补偿或权重校准。
- **局限 2**：Scope 限于单机 1–4 GPU、decoder-only 7B–70B、[[vLLM]]/[[SGLang]]/TensorRT-LLM；84% 配置可行率，部分组合因框架限制未测。
- **局限 3**：PRI 预测 aggregate flip rate，不预测 per-prompt flip；framework/model held-out R²<0.48 时不能替代全量评测。
- **局限 4**：Deterministic 测量为 conservative upper bound；生产 stochastic sampling 需额外验证（论文给 ~0.23× 经验缩放，非严格理论保证）。
- **Future work 1**：Drift-aware serving、automated drift compensation、CI/CD pre-deployment gating 与 prompt-level drift prediction（entropy、decision boundary proximity 等特征）。
- **Future work 2**：扩展 coverage——更多框架（DeepSpeed-Inference、ExLlamaV2、TGI）、分布式 175B+、TPU/Inferentia/Gaudi、speculative decoding 与 [[Quantization]] stacking。
- **Future work 3**：在 8–10+ GPU 平台与 INT8/INT4/FP6 精度上扩充训练数据，检验 systematic drift 能否从 R²≈0.9 推到 >0.95（附录 A.1 指出当前数据多样性是根本瓶颈）。

## 相关

- **相关概念**：[[Quantization]]、[[PagedAttention]]、[[RadixAttention]]、[[Continuous-Batching]]、[[Disaggregation]]、[[KV-Cache]]
- **同类系统**：[[vLLM]]、[[SGLang]]、TensorRT-LLM、Evidently AI、WhyLabs、Arize AI
- **同会议**：[[MLSys-2026]]
- **对比**：相对 data/concept drift 监控，DriftBench 测固定输入下的 functional flip；相对 [[SpecDecodeBench-MLSys26]]（SD 性能 illusion）与 MLPerf（吞吐/延迟），DriftBench 补 **cross-stack output consistency** 维度；相对量化精度论文，强调 serving 路径变化对 safety 的灾难性案例（23.85% flip）