---
type: theme
topic: AI-Infra
paper_count: 5
first_generated: 2026-04-24
last_updated: 2026-04-24
tags: [topic-overview, llm-systems]
---

# AI Infra

> AI 基础设施综述。当前 5 篇收录全部聚焦 LLM 推理系统，呈现两条主线：**[[MoE]] 推理负载均衡**（Libra、INET4AI）和**跨论文/跨厂商的 KV / 通信抽象**（TransferEngine、MSA、AttnRes 的 block-cache 设计）。

## 论文列表

- [[TransferEngine-arXiv25|TransferEngine (pplx-garden)]] — 跨厂商 P2P RDMA 库，统一 ConnectX RC 与 EFA SRD，支撑 disaggregated KV transfer / RL weight sync (1T 模型 1.3s) / MoE dispatch
- [[Libra-arXiv26|Libra]] — MoE 推理 LB，speculative gating prediction (70-80% 准确率) + Two-Stage Locality-Aware Execution，prefill +19.2%
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — ILP + heuristic 联合优化均衡和搬运代价，搬运 −57%、LB 频率 ×2、MoE 延迟 −12.5%
- [[AttnRes-arXiv26|Attention Residuals (Kimi)]] — 把残差从固定权重升级为 softmax attention，缓解 PreNorm dilution；1.4T tokens 训练 Kimi Linear 48B 后下游全面提升
- [[MSA-arXiv26|MSA: Memory Sparse Attention]] — 端到端可微的 sparse attention 替代 RAG retrieve-then-read，2×A800 跑通 100M token，1M NIAH 94.84%

## 主题综述

### 主线一：MoE 推理的两个相邻问题

[[MoE]] 已成为 2024+ frontier LLM 的事实架构（DeepSeek-V3、Qwen3MoE、GLM-4.5、Kimi-K2），但放弃严格 load-balancing loss 换 expert specialization 后，inference-time 的 expert load imbalance 急剧恶化。本主题里 [[Libra-arXiv26|Libra]] 与 [[LatencyOptimal-MoELB-INET4AI25|INET4AI 工作]] 互补地攻击同一痛点：

- **Libra 关注「准确预测 + 隐藏开销」**：通过 hidden state 的层间慢演化做投机 gating prediction（70-80% accuracy vs Lina 20-30%），并把 LB 计算放到 [[MoE]] local computation 窗口里同步执行
- **INET4AI 关注「搬运代价本身」**：发现 EPLB 单次 LB 搬 13036 个 expert，引入延迟 ~10× 收益；用 ILP/heuristic 把搬运压到 2440，使 LB 可以 2× 频繁

两者结合给出了「MoE prefill 阶段 LB」的较完整答案：Libra 决定**复制什么到哪里**、INET4AI 决定**如何最便宜地复制**。但 **decode 阶段 + 多节点的 LB** 仍是空白。

### 主线二：跨厂商通信抽象与 KV 优化

随着 [[Disaggregation|disaggregated inference]] 和 [[MoE]] 普及，LLM 系统的瓶颈从「单 GPU 算力」迁移到「跨 GPU/节点的 [[KV-Cache]] 与 expert token 的 P2P 通信」。

[[TransferEngine-arXiv25|TransferEngine (pplx-garden)]] 是这一趋势的代表作：发现 NVIDIA ConnectX RC 与 AWS EFA SRD 的最大公约数是「reliable but unordered delivery」，构建跨厂商 P2P RDMA 库，配合新颖的 IMMCOUNTER 完成通知原语。在三个 production 场景（KV transfer、RL weight sync、MoE dispatch）都达到 SOTA：1T 模型权重 1.3 秒同步、ConnectX-7 上 MoE decode latency 超过 DeepEP、EFA 上首次实现可用 MoE。

### 主线三：长上下文 / 长记忆的算法-系统协同

[[MSA-arXiv26|MSA]] 把 [[RAG]] 的 retrieve-then-read pipeline 替换为单一可微的 sparse attention：每个文档生成压缩 routing key + content KV，runtime cosine similarity top-k；配合 document-wise [[RoPE]] 让 64K 训练外推到 100M token；2×A800 实测跑通 100M context，1M NIAH 准确率 94.84%（baseline 24.69%）。

[[AttnRes-arXiv26|Attention Residuals]] 同样体现「把信息聚合从固定权重升级为可学习 attention」的思想，但作用在**深度维度**上：层与层之间的残差从固定 1.0 权重相加，改为 softmax attention 选择性聚合。Block AttnRes 配合 cross-stage caching 把通信压到 O(Nd)，实战中把 Kimi Linear 48B 的下游能力全面提升（GPQA-Diamond +7.5、Math +3.6）。

## 值得关注的方向

### 1. Decode 阶段 + 多节点的 MoE LB

**为什么小团队能做**：算法/系统问题，理论分析为主，不需要超大规模。关键资源是 1-2 张 H100/A100 + open-source MoE 模型。

**指向这个空白的论文**：
- [[Libra-arXiv26|Libra]] 明确说自己只优化 prefill；decode 的 token-by-token 特性给 LB 带来不同约束
- [[LatencyOptimal-MoELB-INET4AI25|INET4AI 工作]] 也在单节点设定下评估
- [[TransferEngine-arXiv25|TransferEngine]] 的 MoE dispatch 给跨节点提供了底层通信能力，但调度层未触及

**具体 open problems**：
- decode 阶段单 token batch 下 expert miss 的代价 vs prefill 不同——是否值得做更激进的 prefetch？
- 跨节点 LB 时网络带宽和 GPU 算力的联合优化（INET4AI 思路扩展到 inter-node）
- MoE decode 的「请求级」LB（不同请求 expert 偏好不同）vs token 级 LB

### 2. 算法-系统协同的 KV cache / sparse attention 设计

**为什么小团队能做**：[[MSA-arXiv26|MSA]] 证明了 4B backbone + 158B token 预训练就能做出 SOTA 级别长记忆模型——单节点 8×A100 可承担。

**指向这个空白的论文**：
- [[MSA-arXiv26|MSA]] 的 latent state-based + end-to-end trainable 路线
- [[AttnRes-arXiv26|AttnRes]] 在深度维度上的 sparse attention
- [[KV-Cache]] 概念页里梳理的多种压缩/sparse 方案

**具体 open problems**：
- MSA 的 routing key projector 训练成本能否降到 8B 模型 + LoRA？
- block-wise sparse attention（AttnRes 思想）能否反向应用到序列维度的稀疏化（部分 layer 用 dense、部分用 block sparse）？
- 与 [[Speculative-Decoding]] 的组合：spec model 用 sparse attention 做 draft 是否更稳？

### 3. 跨厂商 RDMA 抽象的下游应用

**为什么小团队能做**：TransferEngine 已开源/即将开源，可以基于它做上层调度/RL 框架的实验。

**指向这个空白的论文**：
- [[TransferEngine-arXiv25|TransferEngine]] 给出了 KV/RL/MoE 三个 use case，但还有大量 LLM serving 场景未覆盖（agent / multi-turn / 多模态）
- 与 [[vLLM]] / [[SGLang]] 的深度集成尚未完成

**具体 open problems**：
- multi-turn agent 场景下的 KV state 共享与回收 over P2P RDMA
- 多模态推理（vision encoder + LLM decoder 在不同卡上）的 P2P data flow 设计
- RL fine-tuning 中 reward model serving 与 actor rollout 的 P2P 异步耦合
