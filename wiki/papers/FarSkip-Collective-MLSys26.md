---
type: paper
name: FarSkip-Collective
full_title: "FarSkip-Collective: Unhobbling Blocking Communication in Mixture of Experts Models"
authors: [Yonatan Dukler, Guihong Li, Deval Shah, Vikram Appia, Emad Barsoum]
venue: MLSys
year: 2026
tags: [moe, expert-parallelism, communication-overlap, training, inference, knowledge-distillation]
source_pdf: "[[698d51a19d8a121ce581499d7b701668.pdf]]"
source_md: "[[698d51a19d8a121ce581499d7b701668]]"
---

# FarSkip-Collective: Unhobbling Blocking Communication in Mixture of Experts Models (MLSys 2026)

> **一句话总结**：基于「MoE EP 下 Dispatch/Combine all-to-all 与下一子层计算形成硬依赖、造成 GPU 空泡」的观察，FarSkip-Collective 用 partial/outdated activation 启动下一子层计算以打破 blocking；FCSD 自蒸馏在 <10B tokens 内全层转换 16B–109B [[MoE]] 且平均精度 drop ≤2.5%（Llama 4 Scout within 1%）；Megatron 训练 EP 通信重叠 **88.4%**，[[vLLM]]/[[SGLang]] 推理 TTFT 最高 **+18.5%**、通信重叠 **97.6%**。

## 问题与动机

[[MoE]] 已成为前沿 LLM 默认架构，但 Expert Parallelism（[[Expert-Parallelism|EP]]）下的 Dispatch/Combine all-to-all 与 [[Tensor-Parallelism|TP]]/CP 的 all-reduce 在计算图中形成 **blocking communication**——collective 必须等上一子块输出就绪才能启动，下一子块又必须等 collective 完成，导致 GPU 暴露 idle time。硬件算力持续提升使通信在端到端 workload 中占比越来越大（尤其 inference）。

现有缓解路线分两类：(1) **bit-exact overlap**（AsyncTP、pipeline 等）不改模型数学形式，靠算子分解与调度重叠；(2) **架构修改**（Ladder-residual、Kraken、TPSA 等）用 outdated/partial activation 打破依赖，但此前多限于 **dense TP**、**小规模**或 **部分层** 修改。在 100B+ 前沿 [[MoE]] 上、**全层** 修改 connectivity 后是否仍能保持能力，论文 claim 此前未得到验证。

FarSkip-Collective 的 claim 是：通过修改残差连接让下一子层在 collective 进行时即可用可用 activation 启动计算，从架构层面消除 blocking 依赖；再用 FCSD 自蒸馏恢复精度；最后在 Megatron / [[vLLM]] / [[SGLang]] 上显式实现异步 collective 调度以兑现重叠收益。

## 关键观察 / 隐含假设

- **观察 1**：典型 MoE transformer layer 存在三处 blocking 通信空泡——(a) post-attention TP/CP collective、(b) Dispatch all-to-all、(c) Combine all-to-all（shared expert 存在时 (c) 可部分重叠）。
  - **依赖假设**：EP 训练走 token permutation + all-to-all；推理在 [[vLLM]]/[[SGLang]] 走 activation replicate + all-reduce（非 all-to-all），但 attention 侧仍有 blocking all-reduce。
  - **可能失效场景**：不同 EP 实现（如纯 all-reduce vs all-to-all）、无 shared expert 的 MoE 设计、或 CP/PP 主导瓶颈时，三泡相对权重会变。
  - **证据强度**：强。背景节与 Figure 2 执行图直接对应标准 Megatron MoE 路径。

- **观察 2**：未训练的 connectivity 修改会灾难性掉点——Qwen3-30B-A3B 全层 FarSkip 后 MMLU 跌至随机基线、HumanEval+ **0%**；但 KL 自蒸馏可在远小于从头预训练的成本（论文称 ~100–1000× 更便宜）内恢复。
  - **依赖假设**：参数 layout 不变，仅输入 activation 路径改变；原 checkpoint 可作为 teacher 做 logit-level KL；instruction-tuning 数据 + 原模型概率分布提供足够细粒度对齐信号。
  - **可能失效场景**：无高质量 teacher（需从头预训练 FarSkip 架构）、任务对单步 outdated activation 极敏感（长链推理、工具调用）、或 embedding/LM-head 未充分对齐时后期训练不稳定。
  - **证据强度**：强。Figure 3 无训练曲线 + Table 1/2 蒸馏对比 + Appendix 从头预训练 loss 曲线一致支撑。

- **观察 3**：partial + outdated 组合使每个子块输入最多落后 **一个 sub-block**，在最大化 overlap 窗口的同时控制精度损失；修改 **早期层** 比修改 **尾部层** 伤害更大（corruption cascade + 残差中可访问历史层比例更低）。
  - **依赖假设**：Attention 用 partial activation（含 shared-expert、不含 routed expert）可 overlap Combine；MoE 用 outdated activation（缺当前 attention 输出）可 overlap Dispatch；shared-expert 计算与 routed expert collective 可并行。
  - **可能失效场景**：通信时长大于整个 sub-block 计算时长时，单 block skip 不够（论文明确留作 future work）；无 shared-expert 的 MoE 失去 Combine overlap 窗口；极稀疏超大 EP 下 Dispatch 主导时 partial 策略需重调。
  - **证据强度**：中到强。有 connectivity 公式、Figure 2 重叠窗示意、Fig. 3 首/尾层对比；但「最多一个 sub-block」是设计选择而非穷举最优。

- **假设 1**：重叠收益要求「下一 residual 之前的计算时长 > collective 时长」；否则即使打破依赖也无法填满 idle window。
  - **证据强度**：中。训练 88.4% overlap 与推理 97.6% overlap 间接支持；但论文未系统报告 communication/compute ratio 与 overlap 百分比的解析关系。

- **假设 2**：PyTorch API 层（`async_op=True`、`torch.cuda.Stream`、autograd Sequence Number 重排）足以在多种硬件上实现高重叠，无需定制通信 kernel。
  - **证据强度**：中。MI325X/MI300X 上结果充分，但重叠会分流 SM 导致纯计算略慢——论文承认 tradeoff，未量化「重叠带来的 compute slowdown vs 空泡消除」净效应分解。

## 核心方法

### FarSkip-Collective 架构

标准残差：$o_k = o_{k-1} + f_k(o_{k-1})$，$f_k$ 内 collective 阻塞 $o_k$，进而阻塞 $f_{k+1}$。FarSkip 改为在 collective 进行时立即用可用 activation $o^*_k$ 计算 $f_{k+1}(o^*_k)$，待 $o_k$ 就绪后再 far-skip 加到更后层 residual。

两种 $o^*_k$ 来源（论文 Eq. 8a/8b）：

- **Outdated (8a)**：$o^*_{mlp} = o_{k-1}$——MoE 子块输入缺当前 attention 输出，使 Dispatch 可与 attention 并行。
- **Partial (8b)**：$o^*_{attn} = o_{k-1} + \text{shared-expert}_{k-1}$——attention 输入不含 routed expert（需 Combine 聚合），使 Combine 可与 shared-expert + attention 计算并行。

数学上这是 **dropping connections**：下一子块输入不含最新 communicated block，但 $f_{k+2}$ 及之后层最终仍能访问完整 $f_k$ 输出。参数 shape 与 kernel layout **不变**，同一 checkpoint 可加载到 FarSkip connectivity（需重训/蒸馏适配输入分布）。

### FCSD（FarSkip-Collective Self-Distillation）

转换流程：先全层启用 FarSkip connectivity → 用原模型作 teacher 做 **KL logit distillation**（优于纯 SFT，Table 2 显示 SFT 在生成任务 catastrophic forgetting）。关键工程细节：

- 训练 token **<10B**（相对从头预训练 ~100–1000× 省）
- batch size / learning rate 大 sweep（batch {2^16, 2^17, 2^18}，LR {2e-5, 4e-5, 8e-5}）
- **Early stopping**：MBPP+ 每 1000 step 验证，patience 20、性能 delta 2%——因后期 KL 易出现 mode-collapse 大梯度
- 中间层 L2 alignment、冻结 embedding 等变体收益不显著（Table 2）

已转换模型：DeepSeek-V2-Lite (16B-A3B)、Qwen3-30B-A3B、Llama 4 Scout (109B-A17B)，均 instruction-tuned/chat checkpoint。

### 显式重叠实现

**训练（Megatron-LM）**：DeepSeek V3 recipe（shared expert + MLA + EP、attention 无 TP）。将 attention 拆为 (a) q,k,v 准备、(b) core-attention + output projection，在 (a) 与 (b) 之间异步 launch collective。MoE forward 顺序：attention(a) → sync 上层 Combine（若需要）→ gating → async Dispatch → attention(b) → sync Dispatch → routed experts → async Combine → shared experts。

Backward 难点：naive async 会在 launch 后立即 sync。创新两点：(1) **stateful async all-to-all autograd Function** + backward hook 在真正需要梯度时才 sync；(2) **hijack autograd Sequence Number**，延后「通向 collective 输入」的 backward 节点，先跑 sub-block 内节点以扩大重叠窗。深度实现见 [[698d51a19d8a121ce581499d7b701668]]。

**推理（[[vLLM]] / [[SGLang]]）**：MoE 侧 all-reduce async-op，在下次 MoE 计算前 sync；attention output projection 的 RowParallelLinear all-reduce 同理。MLA prefill/generation 分路径处理。HIP/CUDA-graph 兼容通信（PyNCCL binding）。

## 设计取舍

- **架构修改 vs bit-exact overlap**：打破数学依赖，需蒸馏恢复精度；收益是 overlap 不依赖算子切分粒度，且 MoE EP 的 all-to-all 与 attention 可跨子块重叠。代价是 **非 bit-exact**、部署需换 checkpoint。
- **单 block skip vs 多 block skip**：每输入最多落后一个 sub-block 保精度；更激进 multi-block skip 可应对超长 collective，但能力损失未知——论文列为 future work。
- **Partial+Outdated 组合 vs 纯一种**：混合策略针对 MoE 双 collective（Dispatch/Combine）各开一个窗口；实现与调试复杂度高于单一策略。
- **PyTorch API 层 vs 定制 kernel**：可移植、易接入上游框架；牺牲对 NCCL/硬件拓扑的极致调优，且重叠占用部分 SM 拖慢纯计算。
- **FCSD vs SFT**：KL 对齐 teacher 分布更细、对 curated SFT 数据依赖更低；但后期训练不稳定，必须 early stopping——运维需监控 code-gen proxy。
- **边界条件**：prefill/训练 EP-heavy、多节点 wide-EP、通信占比高时最优雅；单节点 decode memory-bandwidth-bound、小 batch 小 message 时收益变薄（论文 Fig. 7 显示 multi-node 大 batch decode 才显著）。

## 实验与结果

**模型能力（Table 1，11 个下游数据集）**：

- 三模型全层 FarSkip + FCSD：平均精度 drop **≤2.5%** vs 原 instruction-tuned release
- Llama 4 Scout 109B：平均 **within 1.0%**
- HumanEval+ 等生成任务与原版 on par；SFT baseline 显著更差
- 从头预训练 16B MoE 50B tokens：loss 2.205 vs 2.187，下游平均 54.7 vs 54.4（Appendix）

**蒸馏消融（Table 2，Qwen3-30B，500M tokens）**：KL 最优；KL+中间 L2、冻结 embedding 无显著增益；仅转换尾部 75% 层明显更易（HEval+ 等）

**训练重叠（Table 3，EP=8，1×MI325X 8GPU）**：

- DeepSeek-V2-Lite：forward overlap **87.6%**、backward **89.0%**、综合 **88.4%**；端到端 **+11%**
- DeepSeek-V3 (L=6 proxy 71B)：forward **92.9%**、backward **84.1%**；端到端 **+4%**
- 4 node × 8 GPU，EP=32 strong scaling：**1.22×** 端到端加速（Fig. 5）

**推理**：

- [[vLLM]] prefill（FP8，EP=8，TP=8，BS=2）：DeepSeek-V2 235B TTFT **+8.2%–16.8%**；Llama 4 Scout **+12.2%–18.5%**；all-reduce overlap **95.3% / 97.6%**（vs 常规 0%）
- [[SGLang]] DeepSeek-V3 671B prefill：最高 **1.34×** TTFT（TP=8，EP=8）
- 2-node decode（TP=16，EP=16，BS=1024）：FarSkip 在各 prompt length 下一致加速（Fig. 7）

## Critical Analysis

### 论证链条

论文的 observation → design → result 链条在「EP MoE 训练 + vLLM/SGLang 推理」主路径上闭合较好：blocking bubble 图示直接导出 partial/outdated 输入设计；无训练灾难性掉点证明必须蒸馏；FCSD 恢复 Table 1 精度后，Megatron/vLLM 实现才报告 overlap 百分比与端到端加速。

最脆的跳步是 **从 overlap 百分比到端到端 speedup 的归因**。88.4% all-to-all overlap 仅对应 EP collective 时间片，全层端到端仅 +4%–11%（单节点训练），说明 routed expert 与 gating 仍不可重叠，且 SM 争用、非 EP 部分未优化。推理 TTFT +18.5% 是亮眼 headline，但依赖 FP8 + fused MoE kernel 特定栈，且对比基线是否同样启用 graph/异步需细读实现（论文称 regular 0% overlap）。

第二个跳步是 **100B+ 能力保留 claim 的评测边界**。11 个数据集 + 生成样例（Appendix B）覆盖广但仍是公开 benchmark 代理；对 agentic 长链、多轮 tool use、极低延迟 serving 下 outdated activation 是否引入系统性行为漂移，论文未测。

### 假设压力测试

**通信/计算比**：单 block skip 假设 collective 短于下一子块计算。极稀疏超大 MoE、跨节点 400Gbps 仍不够时，需 multi-block skip——论文承认但未实现。此时架构修改收益上限受限于 compute 侧窗口长度。

**推理 vs 训练路径分裂**：训练用 all-to-all EP；vLLM/SGLang 推理用 replicated activation + all-reduce。FarSkip 在两种 collective 上都 work，但 overlap 机制与瓶颈不同；将训练侧 88.4% 数字外推到所有部署形态需谨慎。

**Decode 单节点**：论文诚实指出 memory-bandwidth-bound 下计算主导、通信 message 小，FarSkip 收益有限；真正显著在 multi-node wide-EP 大 batch。若生产以单卡/单节点低延迟 decode 为主，headline TTFT 数字可能不代表稳态吞吐。

**蒸馏成本与稳定性**：<10B tokens 仍非零成本；KL 后期不稳定依赖 MBPP+ early stopping——换模型族或 code 能力弱的 teacher 时 proxy 是否仍敏感未验证。SFT 失败说明 connectivity shift 大，但 FCSD 超参（大 batch、高 LR）需 per-model sweep，自动化转换流水线复杂度论文未量化。

**硬件与作者利益**：AMD 作者，基准 MI325X/MI300X；与 NVIDIA 集群上 NCCL/graph 行为差异可能改变 overlap 比例。计划开源实现与 checkpoint 尚未在写作时验证社区可复现性。

### 实验可信度

**强项**：三档规模（16B/30B/109B）全层转换 + 从头预训练小模型；训练 forward/backward overlap 分开报告；推理含 TTFT 与 decode、单节点与多节点；与 Ladder-residual/Kraken 等定位清晰；实现细节（autograd hijack）可审计。

**弱点**：与 bit-exact overlap（AsyncTP 等）无同栈 head-to-head；端到端训练 speedup 偏小（4%–11%）与 88% overlap 之间的差距未充分分解；11 数据集平均 within 1%–2.5% 掩盖 per-task 回归；生产流量、在线 A/B、tail latency SLO 缺失；图表部分依赖 MinerU OCR，精确曲线值需谨慎引用。

### 系统性缺陷

- **正确性**：非 bit-exact；distilled 模型行为与原版 probabilistically close 但非等价，安全/对齐关键应用需独立验证——论文未讨论。
- **运维**：需维护 FarSkip checkpoint 分支、FCSD 训练管线、early stopping 监控；与上游 Megatron/vLLM/SGLang 合并冲突风险——论文称计划开源但未给升级策略。
- **多租户/隔离**：异步 collective 与额外 stream 是否影响同节点其他 job 的 NCCL 行为、尾延迟——论文未讨论。
- **可观测性**：overlap 比例如何在线监控、退化到 blocking 的 fallback——论文未描述。
- **兼容性**：依赖 shared-expert MoE 结构最大化 Combine overlap；无 shared expert 或不同 attention（非 MLA）需重新设计 $o^*$；PP 与 FarSkip 交互仅部分讨论（用 L=6 proxy 隔离 PP）。

## 局限与 Future Work

- **局限 1**：仅单 block far-skip；通信长于 sub-block 时 overlap 饱和——需 multi-block 变体与能力代价评估。
- **局限 2**：FCSD 对超参敏感且后期 KL 不稳定，依赖 MBPP+ early stopping，缺少自动化转换保证。
- **局限 3**：早期层修改伤害大，全层转换必要性 vs 部分层转换的速度-精度 tradeoff 在生产中未系统量化。
- **局限 4**：单节点 decode 收益有限；论文主要证明 wide-EP multi-node 场景——与许多 latency-sensitive 部署默认配置不完全对齐。
- **局限 5**：与 bit-exact overlap 方案的联合或对比不足，难以判断「改架构」是否为最优 Pareto 点。
- **Future work 1**：multi-block far-skip + 通信时长预测，自适应选择 skip 深度。
- **Future work 2**：在 agentic 长上下文、多轮推理、在线 RL rollout 等延迟敏感 workload 上测量 outdated activation 的行为漂移与 SLO 影响。
- **Future work 3**：与 [[Pipeline-Parallelism|PP]]、[[Disaggregation]]（prefill/decode 分离）组合时的调度与蒸馏策略。
- **Future work 4**：自动化 FCSD 超参选择与稳定性监控，降低 per-model sweep 人工成本。

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[Tensor-Parallelism]]、communication overlap、[[Knowledge-Distillation]]、[[Megatron|Megatron-LM]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Megatron-LM、DeepSeek-V2/V3、Llama 4 Scout、Ladder-residual、Kraken、TPSA
- **同会议**：[[MLSys-2026]]
- **源材料**：[[698d51a19d8a121ce581499d7b701668]]、[[698d51a19d8a121ce581499d7b701668.pdf]]