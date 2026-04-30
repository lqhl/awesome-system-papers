---
type: paper
name: DeepSeek-V4
full_title: "DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence"
authors: [DeepSeek-AI]
venue: arXiv
year: 2026
tags: [foundation, llm, moe, long-context, attention, quantization, rl, post-training]
source_pdf: "[[DeepSeek_V4.pdf]]"
source_md: "[[DeepSeek_V4]]"
---

# DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence (arXiv 2026)

> **一句话总结**:1.6T 参数(49B 激活)的 DeepSeek-V4-Pro 与 284B 参数(13B 激活)的 DeepSeek-V4-Flash,两个 [[MoE]] LLM,原生支持 1M-token context;通过 Compressed Sparse Attention (CSA) + Heavily Compressed Attention (HCA) 混合注意力架构,将 1M context 下的单 token 推理 FLOPs 压到 DeepSeek-V3.2 的 27%、KV cache 压到 10%,并在 Max 模式下在多数开源基准上建立新 SOTA,追近 Gemini-3.1-Pro / GPT-5.4。

## 问题

reasoning 模型(DeepSeek-R1、o1 系列)带起来的 test-time scaling 范式和 agentic/长文档场景,共同推高了上下文长度需求。但原生 [[Transformer]] 的注意力计算复杂度 $O(n^2 \cdot d)$ 和 [[KV-Cache]] 随 context 线性膨胀两个事实,让 1M token 级别的推理在现有硬件上不可承受。DeepSeek-V3.2 已经用 DeepSeek Sparse Attention 缓解了一部分,但 DeepSeek-V4 想把 1M context 变成 "routinely supported" 的日常能力——这要求 attention、KV 存储、训练基础设施、post-training pipeline 全线重做。

## 核心方法

**Hybrid CSA + HCA Attention**。这是架构核心创新:
- **Compressed Sparse Attention (CSA)**:先把 KV entries 在序列维度按 $m$ 倍压缩成 $C^{\text{Comp}}$,再在压缩后的 entries 上跑 DeepSeek Sparse Attention 的 lightning indexer + top-k 选择。本质是 "先降维、再稀疏",叠加两种压缩
- **Heavily Compressed Attention (HCA)**:更激进的压缩率 $m' \gg m$,但保留 dense attention,不做 top-k。适合需要全序列全局信息的层
- 所有 attention 层都用 Shared KV MQA + Grouped Output Projection + partial RoPE(仅后 64 维)+ sliding window attention branch + attention sink

**Manifold-Constrained Hyper-Connections (mHC)**。把残差流从 $\mathbb{R}^d$ 扩展到 $\mathbb{R}^{n_{hc} \times d}$,引入三个线性映射 $A, B, C$;关键创新是把 $B$ 约束到 Birkhoff polytope(doubly stochastic matrix manifold),保证谱范数 ≤ 1,从根本上稳定深层堆叠的信号传播。动态参数化 + sigmoid 约束使得训练稳定性显著提升。

**Muon Optimizer**。沿用 Muon(Jordan et al., 2024)替代 AdamW,对大多数模块使用。Hybrid Newton-Schulz 迭代(前 8 步激进系数 + 后 2 步稳定系数)、与 ZeRO 的兼容策略(knapsack 分配 + BF16 梯度 + all-to-all → local FP32 sum)、保留 AdamW 用于 embedding/RMSNorm 参数。

**继承自 V3 的组件**。[[MoE]] 架构 DeepSeekMoE、Multi-Token Prediction(MTP)、auxiliary-loss-free 负载均衡。V4 里把 affinity score 激活从 Sigmoid 改为 $\sqrt{\text{Softplus}(\cdot)}$;前几个 Transformer block 的 dense FFN 换成 Hash routing 的 MoE。

**Infrastructure 亮点**。
- **Fine-Grained EP Mega-Kernel**:把 MoE 的 Dispatch / Linear-1 / Linear-2 / Combine 四阶段按 expert wave 细粒度 pipeline,单 fused kernel 在 NVIDIA 和华为 Ascend 上都拿到 1.50-1.96× 加速,开源为 MegaMoE
- **TileLang**:用 DSL 写 kernel,SMT solver(Z3)做整数约束推理;host codegen 把 per-invocation overhead 从几十微秒压到 <1 微秒
- **Batch-invariant + Deterministic Kernels**:dual-kernel 策略让 split-KV attention 保持 batch invariance,MoE backward 用 per-rank buffer 隔离避免 atomicAdd 非确定性
- **FP4 Quantization-Aware Training**:MoE expert 权重和 CSA 的 QK path 都走 FP4;FP4→FP8 dequantization 无损(因 FP8 E4M3 比 FP4 E2M1 多 2 个 exponent bit)
- **Heterogeneous KV cache + on-disk storage**:为 shared prefix 复用设计异构 KV 结构

**Post-Training Pipeline**。两阶段:
1. **Specialist Training**:为每个 domain(math / code / agent / instruction following)独立 SFT + GRPO RL 训专家模型
2. **On-Policy Distillation (OPD)**:用 full-vocabulary reverse KL 把 10+ 专家融到统一 student,通过 teacher hidden state 缓存 + per-mini-batch teacher head rotation 解决 100k+ vocab 下的显存爆炸

**DSec Sandbox**。为 agentic RL 设计的生产级 sandbox 平台,四种 substrate(Function Call / Container / microVM-Firecracker / fullVM-QEMU)统一 Python SDK;基于 3FS + EROFS / overlaybd 的分层存储;trajectory log 支持 preemption-safe 恢复。

## 关键结果

- **1M-context 效率**: DeepSeek-V4-Pro 在 1M token 下单 token 推理 FLOPs = DeepSeek-V3.2 的 27%、KV cache = 10%;Flash 更极致(10% FLOPs / 7% KV)。相对 BF16 GQA8 baseline,KV cache 仅约 2%
- **Knowledge**: SimpleQA-Verified 57.9(V4-Pro-Max)vs Opus-4.6 46.2 / K2.6 45.3,开源新 SOTA;Chinese-SimpleQA 84.4 领跑开源;MMLU-Pro 87.5
- **Reasoning**: HMMT 2026 Feb 95.2、IMOAnswerBench 89.8、Apex Shortlist 90.2,多数开源 SOTA;Codeforces rating 3206,人类 rank 23
- **Long-context**: CorpusQA 1M 62.0 超过 Gemini-3.1-Pro 53.8;MRCR 1M 83.5 接近 Opus 4.6 的 92.9
- **Agent**: Terminal Bench 2.0 67.9(Verified 子集 ~72.0);SWE-Verified 80.6;BrowseComp 83.4
- **实用验证**: R&D coding benchmark 上 Pass Rate 67%,介于 Sonnet 4.5(47%)和 Opus 4.5(70%)之间;DeepSeek 内部工程师调研中 52% "已用作默认 coding model"
- **训练规模**: V4-Flash 32T tokens、V4-Pro 33T tokens

## 相关

- **前驱**: [[Transformer]]（架构骨架）、DeepSeek-V3（大部分组件继承,含 DeepSeekMoE、MTP）
- **核心概念**: [[MoE]]、[[KV-Cache]]、[[Speculative-Decoding]]、[[Disaggregation]]
- **同 topic**: [[Foundation]]
- **相邻方向**: [[MSA-arXiv26]]（另一条长上下文路线:sparse attention 替代 RAG）、[[AttnRes-arXiv26]]（attention 替代固定残差,精神上与 mHC 呼应）
- **基础设施对照**: [[fabric-lib-MLSys26]]给出了跨厂商 P2P RDMA 抽象,可为 DeepSeek-V4 这种 1T 级模型的 disaggregated serving 提供下层通信原语
