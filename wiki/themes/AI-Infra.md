---
type: theme
topic: AI-Infra
paper_count: 18
first_generated: 2026-04-24
last_updated: 2026-06-09
tags: [topic-overview, llm-systems]
---

# AI Infra

> AI 基础设施综述。18 篇论文覆盖六条主线：**[[MoE]] 推理效率**（Libra、INET4AI、FluxMoE、MOE-INFINITY、OD-MoE、CoX-MoE、ContextAwareMoE-CXLNDP）、**KV Cache 跨请求复用与传输**（CacheGen、CacheBlend、LMCache）、**跨厂商通信抽象**（fabric-lib）、**长上下文/长记忆的算法-系统协同**（MSA、AttnRes）、**[[KV-Cache]] 后处理与可编辑性**（PASTA、LLMSteer、Cartridges），以及 **KV Cache 压缩/检索**（IceCache、MoE-nD）。

## 论文列表

### MoE 推理与 Expert 管理（7 篇）

- [[Libra-ICLR26|Libra]] — MoE 推理 LB，speculative gating prediction (70-80% 准确率) + Two-Stage Locality-Aware Execution，prefill +19.2%
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — ILP + heuristic 联合优化均衡和搬运代价，搬运 −57%、LB 频率 ×2、MoE 延迟 −12.5%
- [[FluxMoE-arXiv26|FluxMoE]] — 把 expert 权重当虚存分页，两层滑动窗口 + GPU 压缩 + CPU offload，Qwen3-Next-80B 上 3.0× 吞吐（BS=256, 4K context）
- [[MOE-INFINITY-arXiv24|MOE-INFINITY]] — personal-machine MoE offloading，request-level sparse expert cache，3.1-16.7× TPOT 改善
- [[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]] — CXL-NDP 执行 cold experts，prefill-guided placement + per-expert mixed precision，最高 8.7× decoding throughput
- [[OD-MoE-arXiv25|OD-MoE]] — cacheless edge-distributed expert loading，shadow model SEP 预测 expert activation，99.94% recall
- [[CoX-MoE-DAC26|CoX-MoE]] — AMX CPU-GPU co-execution + coalesced expert execution，最高 2.4× over MoE-Lightning、7.1× over FlexGen

### KV Cache 跨请求复用与传输（3 篇）

- [[CacheGen-SIGCOMM24|CacheGen]] — 首个聚焦 KV cache 传输时大小优化的工作，自定义量化 + 算术编码 3.5-4.3× 压缩，adaptive streaming 按带宽自适应调压缩级别（SIGCOMM 2024）
- [[CacheBlend-EuroSys25|CacheBlend]] — RAG 多 chunk 场景的 selective KV recompute：非 prefix chunk 只更新 <15% token 的 KV（cross-attention 补偿），TTFT 降 2.2-3.3×（EuroSys 2025）
- [[LMCache-arXiv25|LMCache]] — 同一团队的 full-stack KV cache 层：GPU/CPU/SSD/remote 多 tier 持久化 + prefix reuse + PD disaggregation，最高 15× 吞吐（arXiv 2025）

- [[fabric-lib-MLSys26|fabric-lib]] — 跨厂商 P2P RDMA 库，统一 ConnectX RC 与 EFA SRD，支撑 disaggregated KV transfer / RL weight sync (1T 模型 1.3s) / MoE dispatch
- [[AttnRes-arXiv26|Attention Residuals (Kimi)]] — 把残差从固定权重升级为 softmax attention，缓解 PreNorm dilution；1.4T tokens 训练 Kimi Linear 48B 后下游全面提升
- [[MSA-arXiv26|MSA: Memory Sparse Attention]] — 端到端可微的 sparse attention 替代 RAG retrieve-then-read，2×A800 跑通 100M token，1M NIAH 94.84%

### KV Cache 后处理与可编辑性（3 篇）

- [[PASTA-ICLR24|PASTA]] — post-hoc attention steering，用户指定重点 token，模型级 head profiling 选出 steering head 做乘法重加权，Llama-7B 平均 accuracy +22%（ICLR 2024）
- [[LLMSteer-NeurIPSW24|LLMSteer]] — query-independent attention steering，两次 contextual re-reading 取高 attention 交集做加权，兼容 prefix caching，速度比 AutoPASTA 快 4.8×，质量差距缩小 65.9%
- [[Cartridges-ICLR26|Cartridges]] — 用 self-study（合成对话 + context distillation）把长文档离线训练成紧凑 KV 表示，38.6× 更少内存、26.4× 更高吞吐、可拼接复用（ICLR 2026）

### KV Cache 压缩与检索（2 篇）

- [[IceCache-arXiv26|IceCache]] — semantic token clustering + [[PagedAttention]] page selection，用 DCI-tree 提高 relevant page hit rate；36k context 下 99.0% full-cache accuracy、0.11s TPOT
- [[MoE-nD-arXiv26|MoE-nD]] — per-layer routing eviction ratio / K bits / V bits，LongBench 4-task 上 136 MB cache 达到 14× compression 且匹配 1.9 GB full cache baseline

## 主题综述

### 主线一：MoE 推理的两个相邻问题（+ expert paging 的第三条路）

[[MoE]] 已成为 2024+ frontier LLM 的事实架构（DeepSeek-V3、Qwen3MoE、GLM-4.5、Kimi-K2），但放弃严格 load-balancing loss 换 expert specialization 后，inference-time 的 expert load imbalance 急剧恶化。本主题里 [[Libra-ICLR26|Libra]] 与 [[LatencyOptimal-MoELB-INET4AI25|INET4AI 工作]] 互补地攻击同一痛点：

- **Libra 关注「准确预测 + 隐藏开销」**：通过 hidden state 的层间慢演化做投机 gating prediction（70-80% accuracy vs Lina 20-30%），并把 LB 计算放到 [[MoE]] local computation 窗口里同步执行
- **INET4AI 关注「搬运代价本身」**：发现 EPLB 单次 LB 搬 13036 个 expert，引入延迟 ~10× 收益；用 ILP/heuristic 把搬运压到 2440，使 LB 可以 2× 频繁

两者结合给出了「MoE prefill 阶段 LB」的较完整答案：Libra 决定**复制什么到哪里**、INET4AI 决定**如何最便宜地复制**。但 **decode 阶段 + 多节点的 LB** 仍是空白。

[[FluxMoE-arXiv26|FluxMoE]] 从另一个角度攻击 MoE 推理效率：不做 LB，而是把冷 expert 权重从 HBM 驱逐到压缩 GPU backend 或 CPU DRAM，腾出空间给 [[KV-Cache]]。其核心创新是 **PagedTensor**——把 [[PagedAttention]] 的分页抽象推广到 expert 权重，virtual→physical 映射在 kernel 启动前异步完成，消除 in-kernel 地址算术。Qwen3-Next-80B 上拿到 vLLM 的 3.0× 吞吐。但与 [[DeepSeek-V4-arXiv26|DeepSeek-V4]] 的 FP4 量化 + CSA/HCA 方向对照，FluxMoE 的适用窗口在收窄。

2024-2026 的新增 MoE offloading 论文把问题从「expert load balancing」扩展到「expert 权重到底放在哪、什么时候搬、是否还需要 cache」。[[MOE-INFINITY-arXiv24|MOE-INFINITY]] 利用 personal-machine batch=1 的 request-level sparse expert reuse 做 expert cache；[[OD-MoE-arXiv25|OD-MoE]] 走相反方向，用 shadow model 多层 ahead prediction 完全取消 cache；[[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]] 把 cold expert 放到 CXL-NDP 就地计算；[[CoX-MoE-DAC26|CoX-MoE]] 则针对 throughput batch inference，指出 micro-batching 会把 expert GEMM 打碎成 memory-bound 小任务，改用 AMX CPU-GPU co-execution。这四篇共同说明：MoE inference 的关键抽象已经从「一个 GPU cache」变成多层异构内存/计算资源上的 expert placement。

### 主线二：KV Cache 跨请求复用与传输 — UChicago LMCache 团队的演进三部曲

[[CacheGen-SIGCOMM24|CacheGen]]（SIGCOMM 2024）→ [[CacheBlend-EuroSys25|CacheBlend]]（EuroSys 2025）→ [[LMCache-arXiv25|LMCache]]（arXiv 2025）构成了一条清晰的工程演进路线——来自同一 UChicago/Tensormesh 团队（Yuhan Liu, Jiayi Yao, Kuntai Du, Junchen Jiang），从传输优化 → 多 chunk 语义融合 → 全栈 KV cache 中间件，三步走完成了 KV cache 从「GPU 内临时对象」到「跨 tier 持久化一等数据」的范式转变。

[[CacheGen-SIGCOMM24|CacheGen]] 是起点：观察到了 KV cache 跨节点复用时的**网络传输瓶颈**——几十 GB 的原始 KV tensor 在 commodity 网络上传输耗时 100ms-10s+。创造性地把 KV cache 从 tensor 编码为 bitstream（custom quantization + arithmetic coding），类似视频 codec 的思路，并做自适应 streaming。3.5-4.3× 压缩，TTFT 降 3.2-3.7×。

[[CacheBlend-EuroSys25|CacheBlend]] 解决了一个更具体的问题：RAG 场景中多个 text chunk 的 KV cache 如何复用？Prefix caching 只复用第一个 chunk（prefix），其余 chunk 不是 prefix 因此 cross-attention 缺失。CacheBlend 发现只需 recompute <15% token 的 KV 就能补偿 cross-attention，且这个开销可以被下一层 KV fetch 的 pipeline 完全隐藏。TTFT 降 2.2-3.3×，吞吐 2.8-5×。

[[LMCache-arXiv25|LMCache]] 是集成之作：把 CacheGen 的压缩、CacheBlend 的 selective recompute、以及 KV cache 的持久化/传输/管理统一成一个开源中间件层。支持 GPU/CPU/SSD/remote 多 tier、Ethernet/RDMA/NVLink 多传输、vLLM/SGLang 多引擎。15× 吞吐提升，工业界广泛部署。标志着「KV cache as first-class data object」从学术概念变为工业现实——正呼应了 Junchen Jiang 2026 年博客「Stop Calling It KV Cache」的宣言。

### 主线三：跨厂商通信抽象

随着 [[Disaggregation|disaggregated inference]] 和 [[MoE]] 普及，LLM 系统的瓶颈从「单 GPU 算力」迁移到「跨 GPU/节点的 [[KV-Cache]] 与 expert token 的 P2P 通信」。

[[fabric-lib-MLSys26|fabric-lib]] 是这一趋势的代表作：发现 NVIDIA ConnectX RC 与 AWS EFA SRD 的最大公约数是「reliable but unordered delivery」，构建跨厂商 P2P RDMA 库，配合新颖的 IMMCOUNTER 完成通知原语。在三个 production 场景（KV transfer、RL weight sync、MoE dispatch）都达到 SOTA：1T 模型权重 1.3 秒同步、ConnectX-7 上 MoE decode latency 超过 DeepEP、EFA 上首次实现可用 MoE。

### 主线四：长上下文 / 长记忆的算法-系统协同

[[MSA-arXiv26|MSA]] 把 [[RAG]] 的 retrieve-then-read pipeline 替换为单一可微的 sparse attention：每个文档生成压缩 routing key + content KV，runtime cosine similarity top-k；配合 document-wise [[RoPE]] 让 64K 训练外推到 100M token；2×A800 实测跑通 100M context，1M NIAH 准确率 94.84%（baseline 24.69%）。

[[AttnRes-arXiv26|Attention Residuals]] 同样体现「把信息聚合从固定权重升级为可学习 attention」的思想，但作用在**深度维度**上：层与层之间的残差从固定 1.0 权重相加，改为 softmax attention 选择性聚合。Block AttnRes 配合 cross-stage caching 把通信压到 O(Nd)，实战中把 Kimi Linear 48B 的下游能力全面提升（GPQA-Diamond +7.5、Math +3.6）。

### 主线五（新兴）：KV Cache 的后处理与可编辑性

这三篇论文构成一条清晰的演化轨迹——从「修改已有 KV cache 以改善质量」到「用训练替代 prefill 生成 KV cache」：

**阶段一：Post-hoc Attention Manipulation（PASTA, ICLR 2024）**

[[PASTA-ICLR24|PASTA]] 首次证明可以通过 post-hoc 修改 attention score 来显著改善 LLM 输出质量——不改模型权重、只重加权 attention head。核心洞察是只有少数 attention head 对 steering 有效，通过多任务 model profiling 选出这些 head 后，steering 泛化到未见任务。Llama-7B 上 4 个任务平均 accuracy 提升 22%。但 PASTA 的 steering 是 query-dependent 的，这意味着每次请求需要重新 steering，与 prefix caching 不兼容。

**阶段二：Prefix-Caching 兼容的 Query-Independent Steering（LLMSteer, 2024）**

[[LLMSteer-NeurIPSW24|LLMSteer]] 解决了 PASTA 的兼容性问题：通过对同一段 context 用两个不同 prefix prompt 做 offline 的「contextual re-reading」，找出两次阅读中一致高 attention 的 token 做 weighting。因为 steering 是 query-independent 的且在 offline 完成，结果 KV cache 可以被所有后续 query 复用，天然兼容 prefix caching。在 SQuAD/TriviaQA/GSM8K 上把 Llama-8B 与 70B 的质量差距缩小 65.9%，延迟仅比 8B baseline 略高。值得注意的是作者包括 [[vLLM]] 的 Kuntai Du 和 LMCache 的 Junchen Jiang——暗示这条线正在向生产系统渗透。

**阶段三：用训练替代 Prefill（Cartridges, ICLR 2026）**

[[Cartridges-ICLR26|Cartridges]] 是这一演化逻辑的极致：既然 KV cache 可以 post-hoc 修改（PASTA 证明了），也可以离线修改（LLMSteer 证明了），那为什么不直接离线训练一个更小的 KV cache 来完全替代 prefill？Cartridge = 对一份文档用梯度下降训练出的紧凑 KV 表示，配合 self-study（合成对话 + context distillation）保证通用性。38.6× 内存压缩、26.4× 吞吐提升，甚至可以把模型 context length 从 128K 外推到 484K。多个 Cartridge 无需联合训练即可拼接——这在思路上已经接近 **KV cache 的「对象存储化」**。

**三篇共同指向一个更宏大的趋势——Junchen Jiang 在 2026 年 LMCache 博客中称之为「KV cache 不再是一个 cache」**：它正在从一次性的临时计算结果，演化为持久、可编辑、可复用的一等数据对象。这和我们仓库里 [[KvCacheMultiTier]] proposal 的「KV cache 作为存储层次问题」是同一股大潮的不同切面。

### 主线六：KV Cache 压缩从 uniform policy 走向 query/layer aware routing

[[IceCache-arXiv26|IceCache]] 和 [[MoE-nD-arXiv26|MoE-nD]] 都是在挑战「统一 KV 策略」：IceCache 认为按 token 顺序构造 page 会把语义相关 token 打散，所以把 [[PagedAttention]] page 变成 semantic cluster；MoE-nD 认为每层对 eviction/quantization 的敏感度完全不同，所以用 offline sensitivity table 给每层路由不同 `(keep ratio, K bits, V bits)`。

两者对应两个正交方向：IceCache 在**序列/token 维度**上提高 query-aware retrieval hit rate，MoE-nD 在**层/压缩轴维度**上分配 memory budget。它们都暗示下一代 KV 系统不会只有一个全局 budget knob，而会暴露 query、layer、head、page、precision 等多个可调维度，再由轻量 calibration 或 runtime retrieval 决定实际布局。

## 值得关注的方向

### 1. Decode 阶段 + 多节点的 MoE LB

**为什么小团队能做**：算法/系统问题，理论分析为主，不需要超大规模。关键资源是 1-2 张 H100/A100 + open-source MoE 模型。

**指向这个空白的论文**：
- [[Libra-ICLR26|Libra]] 明确说自己只优化 prefill；decode 的 token-by-token 特性给 LB 带来不同约束
- [[LatencyOptimal-MoELB-INET4AI25|INET4AI 工作]] 也在单节点设定下评估
- [[fabric-lib-MLSys26|fabric-lib]] 的 MoE dispatch 给跨节点提供了底层通信能力，但调度层未触及

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

### 4. KV Cache 的可编辑性：从 Post-hoc Steering 到离线训练替代

**为什么小团队能做**：PASTA / LLMSteer 不需要训练（只做 attention score 运算），Cartridges 需要 offline 训练但 a) 冻结 LLM 只训 prefix K/V、b) 用 8B 模型 + 单卡就可以跑 self-study。三条路都适合小规模实验。

**指向这个空白的论文**：
- [[PASTA-ICLR24|PASTA]] 的 head profiling 策略是一次性开销，但泛化到新架构（GQA/MQA）未经验证
- [[LLMSteer-NeurIPSW24|LLMSteer]] 只在 10K token 内测试，且仅针对单份 context 的场景
- [[Cartridges-ICLR26|Cartridges]] 的 self-study 对每份文档都要重新跑合成数据生成 + 训练——成本能否进一步压缩？
- 三者都未与 [[PagedAttention]] 生产系统（vLLM / SGLang）深度集成

**具体 open problems**：
- 能否把 PASTA 的 head profiling + LLMSteer 的 re-reading + Cartridge 的 offline training 三条路统一成一个 **KV cache 后处理 pipeline**：profiling → steering（快速但效果有限）→ distillation（慢但压缩比高），按 workload 自动选策略？
- Cartridge 的 offline training 成本（数十 GPU-minutes per document）能否通过 shared prefix initialization 或 meta-learning 大幅降低？
- 对 thinking model（R1 / QwQ）的超长 CoT trace 做 Cartridge-style 压缩——能否把 100K token 的思考过程压到 1K token 的 Cartridge 而不损失推理能力？
- steering / editing 是否会引入**silent correctness 问题**——被修改的 KV cache 是否会产生与原始 prefill 不一致的输出？这连接 SOSP-2025 的 silent failure 主题和 [[KvCacheMultiTier]] proposal 的 consistency 问题
