---
type: theme
topic: AI-Infra
paper_count: 18
first_generated: 2026-04-24
last_updated: 2026-06-20
tags: [topic-overview, llm-systems]
---

# AI-Infra 综述

> 18 篇论文覆盖五条主线：**[[MoE]] 推理与 expert placement**（Libra、INET4AI、FluxMoE、MOE-INFINITY、OD-MoE、CoX-MoE、ContextAwareMoE-CXLNDP）、**[[KV-Cache]] 跨请求复用与传输**（CacheGen、CacheBlend、LMCache）、**长上下文/稀疏注意力与长记忆**（NSA、MSA、AttnRes）、**KV 后处理与可编辑性**（PASTA、LLMSteer、Cartridges）、**KV 压缩与层感知策略**（IceCache、MoE-nD）。

## 论文列表

### MoE 推理与 Expert 管理（7 篇）

- [[Libra-ICLR26|Libra]] — speculative gating prediction (70-80%) + Two-Stage Locality-Aware Execution，prefill +19.2%
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — ILP + heuristic 联合优化均衡与搬运代价，搬运 −57%、MoE 延迟 −12.5%
- [[FluxMoE-arXiv26|FluxMoE]] — expert 权重 PagedTensor 分页 + 两层滑动窗口，Qwen3-Next-80B 上 3.0× 吞吐
- [[MOE-INFINITY-arXiv24|MOE-INFINITY]] — personal-machine request-level sparse expert cache，3.1-16.7× TPOT 改善
- [[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]] — CXL-NDP 执行 cold experts + prefill-guided placement，最高 8.7× decoding throughput
- [[OD-MoE-arXiv25|OD-MoE]] — shadow model SEP 预测 expert activation，cacheless edge loading，99.94% recall
- [[CoX-MoE-DAC26|CoX-MoE]] — AMX CPU-GPU co-execution + coalesced expert execution，最高 2.4× over MoE-Lightning

### KV Cache 跨请求复用与传输（3 篇）

- [[CacheGen-SIGCOMM24|CacheGen]] — KV cache 自定义量化 + 算术编码 3.5-4.3× 压缩，adaptive streaming 按带宽调级别
- [[CacheBlend-EuroSys25|CacheBlend]] — RAG 多 chunk selective KV recompute（<15% token），TTFT 降 2.2-3.3×
- [[LMCache-arXiv25|LMCache]] — GPU/CPU/SSD/remote 多 tier KV 中间件 + prefix reuse + PD disaggregation，最高 15× 吞吐

### 长上下文 / 稀疏注意力与长记忆（3 篇）

- [[NSA-ACL25|NSA]] — 压缩 + 选择 + 滑动窗口三分支原生可训练稀疏 attention，64K 解码 11.6×、backward 6.0×
- [[MSA-arXiv26|MSA]] — 端到端可微 sparse attention 替代 RAG retrieve-then-read，2×A800 跑通 100M token
- [[AttnRes-arXiv26|Attention Residuals]] — 层间残差升级为 softmax attention，Kimi Linear 48B 下游全面提升

### KV Cache 后处理与可编辑性（3 篇）

- [[PASTA-ICLR24|PASTA]] — post-hoc attention steering + head profiling，Llama-7B 平均 accuracy +22%
- [[LLMSteer-NeurIPSW24|LLMSteer]] — query-independent 双次 re-reading steering，兼容 prefix caching，质量差距缩小 65.9%
- [[Cartridges-ICLR26|Cartridges]] — self-study 离线训练紧凑 KV 表示，38.6× 更少内存、26.4× 更高吞吐

### KV Cache 压缩与检索（2 篇）

- [[IceCache-arXiv26|IceCache]] — semantic token clustering + [[PagedAttention]] page selection，36k context 99.0% accuracy
- [[MoE-nD-arXiv26|MoE-nD]] — per-layer routing 淘汰与 K/V bit 分配，136 MB 达到 14× 压缩且匹配 1.9 GB baseline

## 主题综述

### 主线一：MoE 推理从 load balancing 扩展到多层异构 placement

[[MoE]] 已成为 frontier LLM 默认架构，但 specialization 与 inference-time imbalance 的矛盾把研究重心从「均衡 expert 数」推向「expert 权重与 token 该放在哪层内存、哪类设备」。本 topic 里 [[Libra-ICLR26|Libra]] 与 [[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 互补攻击 prefill 阶段 LB：前者用 hidden state 慢演化做 speculative gating（70-80% vs Lina 20-30%），后者用 ILP 把单次 LB 搬运从 13036 expert 压到 2440。但 **decode 阶段单 token batch 与跨节点 LB** 仍是空白。

[[FluxMoE-arXiv26|FluxMoE]] 走第三条路：不做 LB，把冷 expert 当 [[PagedAttention]] 式虚存分页。与 [[MOE-INFINITY-arXiv24|MOE-INFINITY]]（request-level cache）、[[OD-MoE-arXiv25|OD-MoE]]（完全取消 cache）、[[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]]（CXL-NDP 就地算 cold expert）、[[CoX-MoE-DAC26|CoX-MoE]]（AMX CPU-GPU 共执行）对照，MoE inference 的关键抽象已从「一个 GPU cache」变成 **多层异构资源上的 expert placement 问题**。

### 主线二：KV Cache 从 GPU 临时对象演化为跨 tier 一等数据

[[CacheGen-SIGCOMM24|CacheGen]] → [[CacheBlend-EuroSys25|CacheBlend]] → [[LMCache-arXiv25|LMCache]] 构成 UChicago/Tensormesh 团队三部曲：传输压缩 → 多 chunk 语义融合 → 全栈中间件。核心观察是相邻 token KV 有 locality（delta 方差低 2.4-2.9×）、浅层量化更脆、RAG 多 chunk 的质量损失主要来自缺失 cross-attention 而非位置编码错误。LMCache 把「KV cache as first-class data object」推到工业现实——与 [[PASTA-ICLR24|PASTA]]/[[LLMSteer-NeurIPSW24|LLMSteer]]/[[Cartridges-ICLR26|Cartridges]] 的「KV 可编辑」路线汇合，形成 **持久化 + 可复用 + 可后处理** 的完整范式。

### 主线三：长上下文瓶颈从系统调度转向算法-系统协同

[[NSA-ACL25|NSA]] 强调稀疏 attention 必须 **原生可训练且硬件对齐**——仅降 FLOPs 不够，kernel 必须少搬 KV；[[MSA-arXiv26|MSA]] 用可微 routing key 把 [[RAG]] retrieve-then-read 压进单一 attention；[[AttnRes-arXiv26|AttnRes]] 则在深度维度用 attention 替代固定残差，缓解 PreNorm dilution。三篇共同假设：**长上下文的解法不能只靠 KV 分页或 offload，必须改信息聚合方式**；但各自评测边界不同（NSA 偏 64K MoE 训练/推理 kernel，MSA 偏 100M NIAH，AttnRes 偏下游任务质量）。

### 主线四：KV 压缩从 uniform policy 走向 query/layer aware

[[IceCache-arXiv26|IceCache]] 在 token/page 维度做 semantic clustering 提高 query-aware hit rate；[[MoE-nD-arXiv26|MoE-nD]] 在 layer 维度路由不同 `(keep ratio, K bits, V bits)`。两者都挑战「全局单一 KV budget knob」，暗示下一代系统会暴露 query、layer、head、page、precision 多个可调轴。

## 共同观察

**1. [[KV-Cache]] 与 expert 权重在 HBM 上竞争同一块预算，且竞争形态随 batch/阶段变化。** [[FluxMoE-arXiv26|FluxMoE]]/[[MOE-INFINITY-arXiv24|MOE-INFINITY]] 假设 MoE 推理的主要压力来自 expert 权重 materialization；[[CacheGen-SIGCOMM24|CacheGen]]/[[LMCache-arXiv25|LMCache]] 假设跨请求 KV 复用与传输才是 prefill 瓶颈；[[MoE-nD-arXiv26|MoE-nD]] 则把 KV 压缩做成 per-layer 路由。**适用边界**：HBM 充裕、短 context、dense 模型或强量化后权重已非主导时，paging/offload 收益会被 VMM 与 remap overhead 吃掉（[[FluxMoE-arXiv26|FluxMoE]] Critical Analysis 已指出）。

**2. Prefix/chunk 局部性是 KV 复用收益的前提，而非默认成立。** [[CacheBlend-EuroSys25|CacheBlend]]/[[LMCache-arXiv25|LMCache]]/[[LLMSteer-NeurIPSW24|LLMSteer]] 都依赖稳定 chunk 边界与高复用率；[[Cartridges-ICLR26|Cartridges]] 更进一步假设离线训练成本可被多 query 摊销。**适用边界**：一次性 prompt、多租户强隔离、chunking 策略频繁变化或长输出 multi-turn chat（decode 主导、共享少）时，离线 steering/cartridge 的 ROI 急剧下降。

**3. MoE routing 的可预测性是 prefetch/LB/offload 的共同隐含假设。** [[Libra-ICLR26|Libra]] 用 hidden state 慢演化、[[OD-MoE-arXiv25|OD-MoE]] 用 shadow model SEP、[[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 用 popularity 时间衰减——都假设 expert activation 在 request/token 尺度上可预测。**适用边界**：强 load-balancing 训练、conversation/code/math 混合 batch、高温采样或 router 对数值误差敏感的新架构下，预测精度与 recall 会同时下滑。

**4. 浅层 KV/attention 状态对质量更敏感，是压缩与稀疏化的硬约束。** [[CacheGen-SIGCOMM24|CacheGen]] 的分层量化、[[MoE-nD-arXiv26|MoE-nD]] 的 per-layer sensitivity table、[[NSA-ACL25|NSA]] 的多分支稀疏都暗含此规律。**适用边界**：任务高度依赖浅层 lexical detail 或长程精确对齐（代码跳转、表格、needle-in-haystack 变体）时，统一压缩/稀疏策略可能失效。

## 假设冲突与脆弱点

**1. Expert cache vs cacheless：历史复用值不值得为它占 HBM？** [[MOE-INFINITY-arXiv24|MOE-INFINITY]] 假设 personal-machine batch=1 下 request-level expert reuse 足以支撑 sparse cache；[[OD-MoE-arXiv25|OD-MoE]] 假设 shadow model 多层 ahead prediction 足以 **完全取消 cache** 且 99.94% recall。**脆弱点**：多用户 continuous batching 或长 context 挤压 expert cache 时，前者 working set 膨胀；router 对量化误差敏感时，后者 alignment 开销与 routing drift 可能反超收益。需在同一 trace 上测 cache hit rate vs shadow inference overhead vs end-to-end TPOT。

**2. KV 复用：full reuse、selective recompute 还是离线蒸馏？** [[CacheBlend-EuroSys25|CacheBlend]] 假设缺失 <15% token KV recompute 即可补偿 cross-attention；[[Cartridges-ICLR26|Cartridges]] 假设可用梯度下降 **完全替代 prefill** 生成紧凑 KV；[[PASTA-ICLR24|PASTA]] 则只做 post-hoc attention 重加权。**脆弱点**：chunk 彼此独立时可 full reuse；需要强 cross-chunk 推理时 Blend 必要；Cartridge 对窄域 extractive 任务可能不如 [[RAG]] 便宜。需按任务类型分解 TTFT、质量与离线成本三维权衡。

**3. MoE LB：复制 expert vs 分页权重 vs 远端 NDP 计算。** [[Libra-ICLR26|Libra]]/[[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 假设复制/搬运 expert 是主要代价；[[FluxMoE-arXiv26|FluxMoE]] 假设分页权重即可；[[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]] 假设 cold expert 应 **就地算** 而非搬回 GPU。**脆弱点**：网络带宽、CXL 延迟、GPU 算力与 expert 大小的比值决定最优策略；无单一方案在所有 MoE 规模与硬件上占优。

**4. 长上下文：训练原生稀疏 vs 运行时 KV 中间件。** [[NSA-ACL25|NSA]]/[[MSA-arXiv26|MSA]] 假设应改 attention 算子与训练目标；[[LMCache-arXiv25|LMCache]]/[[IceCache-arXiv26|IceCache]] 假设在 **不改模型** 前提下用系统层复用/压缩即可。**脆弱点**：NSA 在短 context 或 KV 已被其他机制压缩时收益下降；MSA 的 NIAH 高分不一定等于综合推理稳定；系统层方案对 thinking model 超长 CoT 的 silent correctness 未验证（连接 [[LLMSteer-NeurIPSW24|LLMSteer]] 的 steering 风险）。

**5. Prefix-caching 兼容 vs 质量增益：steering 能否不改变语义？** [[LLMSteer-NeurIPSW24|LLMSteer]] 假设 query-independent steering 可安全复用；[[PASTA-ICLR24|PASTA]] 的 query-dependent steering 与 prefix cache 不兼容但质量更高。**脆弱点**：被修改的 KV cache 是否产生与原始 prefill 不一致的输出，目前缺乏系统级 parity test；对多租户 eviction 频繁的部署，LLMSteer 的离线 re-reading 成本会重新显性化。

## 值得关注的方向

### 1. Decode 阶段 + 多节点的 MoE LB

**为什么小团队能做**：算法/系统问题，1-2 张 GPU + 开源 MoE 模型即可验证。

**指向空白的论文**：[[Libra-ICLR26|Libra]] 只优化 prefill；[[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 在单节点评估；[[OD-MoE-arXiv25|OD-MoE]] 的 cacheless 路线未与 LB 联合优化。

**具体 open problems**：decode 单 token batch 下 expert miss 代价 vs prefill 的差异；跨节点 LB 时网络带宽与 GPU 算力联合优化；请求级 vs token 级 LB 的公平性。

### 2. 算法-系统协同的 KV cache / sparse attention 设计

**为什么小团队能做**：[[MSA-arXiv26|MSA]] 证明 4B backbone + 158B token 预训练可在单节点 8×A100 承担。

**指向空白的论文**：[[MSA-arXiv26|MSA]]、[[AttnRes-arXiv26|AttnRes]]、[[NSA-ACL25|NSA]] 三条路线尚未在同一 serving 栈上对照。

**具体 open problems**：routing key projector 训练成本能否降到 8B + LoRA；block sparse 能否反向应用到序列维度；与 [[Speculative-Decoding]] 的组合稳定性。

### 3. KV Cache 可编辑性 pipeline 统一

**为什么小团队能做**：PASTA/LLMSteer 不需训练；Cartridges 冻结 LLM 只训 prefix K/V，单卡可跑。

**指向空白的论文**：[[PASTA-ICLR24|PASTA]]、[[LLMSteer-NeurIPSW24|LLMSteer]]、[[Cartridges-ICLR26|Cartridges]] 未与 [[PagedAttention]] 生产系统深度集成。

**具体 open problems**：profiling → steering → distillation 按 workload 自动选策略；thinking model 超长 CoT 的 Cartridge 压缩；steering 的 silent correctness parity test。

### 4. Query/layer aware KV 策略的轻量 calibration

**为什么小团队能做**：[[MoE-nD-arXiv26|MoE-nD]] 的 offline sensitivity table 与 [[IceCache-arXiv26|IceCache]] 的 DCI-tree 都可在单卡上标定。

**指向空白的论文**：两者正交但未组合；[[LMCache-arXiv25|LMCache]] 的多 tier 仍是全局 policy。

**具体 open problems**：layer sensitivity × semantic page 的联合布局；calibration prompt 长度与轴间偏好估计稳定性；与 PD disaggregation 传输格式的兼容性。
