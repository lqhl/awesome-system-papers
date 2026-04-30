---
type: theme
topic: Foundation
paper_count: 3
first_generated: 2026-04-24
last_updated: 2026-04-30
tags: [topic-overview, foundation, milestones]
---

# Foundation 综述

> 本 topic 收录开创性/里程碑工作--那些被后续所有论文奉为共同祖先、无法被时间淘汰的基石论文。三篇覆盖 **架构奠基(Transformer 2017)→ LLM Serving 基础设施(vLLM 2023)→ 开源 frontier 综合(DeepSeek-V4 2026)**,构成「定义架构 → 定义推理系统 → 定义能力边界」的 milestone 链。

## 论文列表

### 架构基石（1 篇）

- [[Transformer-NeurIPS17|Attention Is All You Need]] — Vaswani et al. 2017。提出完全基于 self-attention 的 Transformer,WMT 2014 EN-DE 28.4 BLEU / EN-FR 41.8 BLEU,抛弃 RNN/CNN;Multi-Head + Scaled Dot-Product + 正余弦位置编码,是几乎所有现代 LLM 的共同祖先

### LLM Serving 基础设施（1 篇）

- [[vLLM-SOSP23|vLLM / PagedAttention]] — Kwon et al., SOSP 2023。把 [[KV-Cache]] 当 OS 虚存分页管理——切 block + block table + on-demand 分配 = 零碎片 + copy-on-write 前缀共享。几乎所有后续 KV cache / LLM serving 论文的 baseline 或集成目标。PagedAttention 已成为 LLM serving 事实标准

### 开源 Frontier 综合（1 篇）

- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — DeepSeek-AI 2026。1.6T [[MoE]] 模型(49B 激活),原生 1M-token context。混合 CSA+HCA 注意力把 1M context 下的推理 FLOPs 压到 V3.2 的 27%、[[KV-Cache]] 压到 10%;Muon optimizer + mHC + FP4 QAT;post-training 走 specialist RL + full-vocabulary on-policy distillation;在多数开源基准上建立新 SOTA

## 主题综述

### 一条 9 年的架构传承线

从 [[Transformer-NeurIPS17|Attention Is All You Need]] 到 [[DeepSeek-V4-arXiv26|DeepSeek-V4]],**主干架构几乎没变**:stacked self-attention + position-wise FFN + 残差连接 + LayerNorm。DeepSeek-V4 论文 Abstract 明确写 "retain the Transformer architecture",这本身就是 foundation 论文的"合格证"--能在十年尺度上被继承的架构极为稀有。但壳子里的每个组件几乎都被重做了一遍:
- **FFN 层**: dense → DeepSeekMoE 稀疏路由 + 前几层 Hash routing;[[MoE]] 从"加速实验"变成 frontier model 的默认选择
- **Attention**: 原生 $O(n^2)$ dense → CSA(压缩 + sparse top-k)与 HCA(重度压缩 + dense)的 hybrid 组合,把 1M context 的算力需求压到原来的零头
- **残差连接**: 固定 1.0 权重相加 → Manifold-Constrained Hyper-Connections,约束到 Birkhoff polytope 保证谱范数 ≤ 1,让极深堆叠稳定
- **位置编码**: 正余弦 / learned absolute → partial RoPE(仅后 64 维)+ attention sink

### 同一主干、两个完全不同的工程量级

[[Transformer-NeurIPS17|Attention Is All You Need]] 整篇论文 10 页,训练 8×P100 GPU 3.5 天,65M-213M 参数;而 [[DeepSeek-V4-arXiv26|DeepSeek-V4]] 技术报告 50+ 页,Infrastructure 单独占一整章(EP mega-kernel、TileLang DSL、batch-invariant deterministic kernels、FP4 QAT、DSec sandbox),训练 33T tokens,1.6T 参数。这种体量差反映了过去 9 年 LLM 发展的核心矛盾:**算法进步相对缓慢,系统工程承载能力指数增长**。DeepSeek-V4 的许多"创新"其实是在把 2017 年那张 Figure 1 同样的架构图,做到 2026 年硬件上仍能跑的工程形态。

### foundation 的意义是跨时间的锚点

之所以把这两篇放到同一个 foundation topic 里,不是因为它们题材相近,而是因为它们都**被后续论文广泛引用为共同起点**--Transformer 几乎被每一篇 ML / LLM 论文引用,DeepSeek-V4 刚发布就会成为今后 1-2 年开源社区的 baseline。与 [[AI-Infra]] 等专题不同,foundation 的意义**不在于技术集群归类,而在于提供跨时间的锚点**:做 KV cache 优化的读 Transformer 对 attention 的定义,研究 1M context 的读 DeepSeek-V4 对 CSA+HCA 的权衡,研究 MoE 训练的同时读这两篇--一篇给你 building block,一篇给你 state-of-the-art baseline。

## 值得关注的方向

### 1. 从 Transformer 2017 起跳,找"尚未被 DeepSeek-V4 做完"的空白

**为什么小团队能做**:对照两篇论文的 delta 就能定位尚未工程化的空档。Transformer 论文末尾列了 "Making generation less sequential is another research goal" -- 9 年后 [[Speculative-Decoding]] 做了一部分,但很多原始 open problem 仍然成立。

**指向这个空白的论文**:
- [[Transformer-NeurIPS17|原 Transformer 论文]] 结尾的 "local, restricted attention" 和 "extend to images, audio, video" 两个 future work,**都已被 [[DeepSeek-V4-arXiv26|DeepSeek-V4]] 的 CSA + sliding window 吸收**--证明 foundation 论文的 future work section 是 open problem 富矿
- DeepSeek-V4 只在 text 上做 1M context;vision / audio / code 的 long-context 工程化仍有空间

**具体 open problems**:
- Transformer 原文 Table 1 里的 "restricted self-attention(邻域 $r$)" 给出 $O(r \cdot n \cdot d)$ 复杂度和 $O(n/r)$ path length,这在 1M context 下如何和 DeepSeek-V4 的 CSA+HCA hybrid 做更细粒度组合?
- Transformer 正余弦位置编码 "extrapolate to longer sequences" 的原始假设,在 1M 尺度下是否仍成立?RoPE、ALiBi、mHC 的各自外推边界在哪里?

### 2. Foundation 级工作的"可复现与 benchmark 化"

**为什么小团队能做**:读懂 foundation 论文、复现其关键结果、构建对比 benchmark 是典型的学术原型工作,不需要 frontier GPU 资源。

**指向这个空白的论文**:
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] 开源了权重和部分 infrastructure(MegaMoE、TileLang、DSec)但完整训练 pipeline 不可能被小团队复现--可构建**压缩版可复现 benchmark**,如用 1B-10B 参数验证 mHC / CSA / HCA 各自贡献
- [[Transformer-NeurIPS17|原 Transformer]] 的 ablation Table 3 给出 5 个变量(A-E)的 control experiment--这种严格 ablation 在 frontier 论文里越来越稀有

**具体 open problems**:
- 在相同算力预算下,mHC 相对普通残差带来的 quality gain 具体有多大?(DeepSeek-V4 论文给了定性描述但缺对照实验)
- CSA 的 "先压缩再稀疏" vs HCA 的 "只压缩不稀疏",在不同层深度上的最优混合比例是什么?
- FP4 QAT 在非 DeepSeek 架构(如 Llama、Qwen)上的无损性保持能到多深?

### 3. 把 foundation 级方法"反向投射"到小模型

**为什么小团队能做**:DeepSeek-V4 的许多技术(Muon、mHC、CSA、FP4 QAT、specialist → OPD)单独拆开就是独立可发论文的主题,在 1-8B 模型上验证成本可接受。

**指向这个空白的论文**:
- DeepSeek-V4 把 Muon optimizer 用在超大规模上,但 Muon 在 small / medium 模型、特别是数据受限场景下的 scaling law 仍待研究
- On-policy distillation(OPD)在 DeepSeek-V4 里用了 10+ teacher,小团队可以研究 2-3 teacher 的简化版在 3-8B 模型上的效果

**具体 open problems**:
- Muon 的 Newton-Schulz 迭代系数 $(a, b, c)$ 是否能 task-adaptive?
- OPD 的 "full-vocabulary reverse KL" vs 传统 distillation(forward KL / token-level),在什么规模下差异才显著?
- mHC 的 doubly stochastic 约束在小模型上是否仍必要,或可放松为 stochastic(行归一化即可)?
