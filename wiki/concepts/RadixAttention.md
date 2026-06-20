---
type: concept
aliases: [RadixAttention, radix attention, Radix Attention]
parent: "[[KV-Cache]]"
introduced_by: "[[SGLang-NeurIPS24]]"
last_updated: 2026-06-20
tags: [memory, attention, kv-cache, llm-inference, caching]
---

# RadixAttention

> 用 radix tree（压缩前缀树）管理跨请求的 [[KV-Cache]] 共享。新请求到达时做最长前缀匹配，匹配路径上的 KV 直接复用，仅 prefill 未命中 suffix；结合 LRU eviction 与 cache-aware scheduling，最大化 LM Program 场景下的 prefix 复用率。

## 核心思想

[[vLLM-SOSP23|vLLM]] 的 [[PagedAttention]] + block table 支持 copy-on-write prefix 共享，但共享段通常要求从序列**第一个 token** 开始对齐。LM Program（agent、few-shot、branch-solve-merge、多轮对话）中，不同请求更常共享**中间某段 context** 或多次调用共享模板/历史，而非整段前缀。

RadixAttention 把 KV cache 组织为 radix tree：节点对应 token 序列段，边可带 token 子串；从根到节点的路径是可复用 KV segment。底层仍用 PagedAttention-style block 分配，radix tree 是更高一层的 cache 索引。与被动 [[Prefix-Caching]] 的区别在于：**frontend 通过 `fork` prefix hint、cache-aware scheduling 主动暴露程序结构**，使 agent/tree-of-thought 等动态结构仍保持高 hit rate。

[[SGLang-NeurIPS24|SGLang]] 在 MMLU、HellaSwag、ReAct agent 等场景测得 **50%–99%** cache hit；cache-aware scheduling 平均达 offline DFS 最优的约 **96%**。生产 Chatbot Arena trace 上 LLaVA-NeXT-34B hit **52.4%**、Vicuna-33B **74.1%**。

## 为什么重要

RadixAttention 把 serving 优化对象从「单次 chat completion」扩展到 **Language Model Program 的执行引擎**。瓶颈不是 decode FLOPs，而是多次 LLM 调用间重复 prefill 同一模板、历史或检索块。[[FlashAgents-MLSys26|FlashAgents]] 指出多 agent 顺序依赖使下游必须等上游 decode 完成才 prefill；intra-turn radix cache 让同 turn 并发下游共享 instruction template，相对 sequential 最高 **3.5×**（并发 2）。

这些论文共同假设：**跨调用 KV 复用需要程序结构可见性**——纯 API 级请求流无法达到 radix tree 的收益上限。同时，radix cache 与 running request **共享 memory pool**：waiting queue 足够大时会 evict 全部 cache 换更大 batch，收益高度依赖 workload 局部性而非「永远保留 prefix」。

## 关键观察 / 隐含假设

- **观察 1：LM Program 产生多层次 prefix 重叠，但 long-output multi-turn 收益有限。** [[SGLang-NeurIPS24|SGLang]] 报告短输出多轮对话加速明显，long-output 几乎无加速——decode 主导时 radix cache 帮不上忙。
- **观察 2：cache-aware scheduling 提高 hit，但可能饿死冷请求。** [[SGLang-NeurIPS24|SGLang]] 按最长共享前缀优先，Theorem 3.1 证明 offline DFS 最优，在线接近最优；论文承认 starvation 风险，fair scheduling 集成留作 future work。
- **观察 3：精确 prefix 对 RAG 重排极其脆弱，radix tree  alone 不够。** [[ContextPilot-MLSys26|ContextPilot]] 在 MultihopRAG 上 RadixCache hit 约 **8.5%**，alignment 后 **20.6%**——说明 radix 索引正确，但输入顺序未对齐时仍大量 miss。
- **观察 4：离线全局可知时，runtime LRU radix 次优。** [[BatchLLM-MLSys26|BatchLLM]] 在工业批量场景用 ahead-of-time 全局 prefix 树 + 重排，token 节省 **58.1%** vs vLLM LRU **35.8%**；定位是 offline/batch，与在线 radix LRU 互补。
- **观察 5：同 turn 并发下游无法复用「进行中」的持久 radix 树。** [[FlashAgents-MLSys26|FlashAgents]] 用**临时** intra-turn radix 树与持久 RadixAttention 分离，prefill trigger 时批量 materialize 共享节点。
- **观察 6：动态 prompt 更新需 LCP 失效，而非静态 prefix 语义。** [[Stream2LLM-MLSys26|Stream2LLM]] 针对 streaming ANNS update mode 用 LCP 保留未变前缀 block，机制不同于 radix 的静态共享，但解决同类「序列演化」问题。

## 设计空间与取舍

- **Radix tree vs block table prefix scan**：radix 支持任意最长前缀匹配与细粒度跨序列共享；[[vLLM]] prefix cache 实现更简单，对 commute 场景需 [[SpanQueries-MLSys26|SpanQueries]] 等 IR 扩展。
- **持久 radix vs 临时 intra-turn tree**：[[FlashAgents-MLSys26|FlashAgents]] 模块化降低对 SGLang 核心树语义的侵入，但双树状态增加运维复杂度。
- **cache-aware 调度 vs 公平性 / 吞吐**：最长前缀优先提高 hit；高负载时 evict 全部 cache 换 batch（[[SGLang-NeurIPS24|SGLang]] 设计取舍）。低局部性时 tree 维护开销可能 thrash。
- **单 worker affinity vs 分布式 meta-tree**：[[SGLang-NeurIPS24|SGLang]] Appendix 用 router meta-tree + worker sub-tree 做 data parallel 扩展；跨地域、PD 分离、[[Disaggregation]] 下一致性未充分验证。
- **精确 token match vs fuzzy semantic match**：[[SGLang-NeurIPS24|SGLang]] future work 提及 embedding 近似前缀复用，需权衡准确率。
- **与 [[PagedAttention]] 关系**：radix 是索引层，paging 是物理 block 层；[[MoE-nD-arXiv26|MoE-nD]] 指出 per-layer variable-length retained-token 需要更通用 page metadata 才能与 radix/prefix cache 插件化组合。

## 引用本概念的论文

- [[SGLang-NeurIPS24]] — 提出 RadixAttention + cache-aware scheduling + frontend co-design，相对 [[vLLM]] v0.2.5 吞吐最高 **6.4×**。
- [[ContextPilot-MLSys26|ContextPilot]] — 对比 RadixCache/LMCache，证明 RAG 场景需 context 层 alignment 才能把 radix 潜力转化为 hit。
- [[BatchLLM-MLSys26|BatchLLM]] — 离线批处理的全局 prefix 树，相对在线 LRU radix 显著更高 token 节省。
- [[FlashAgents-MLSys26|FlashAgents]] — intra-turn 临时 radix tree，多 agent 同 turn 共享 template prefill。
- [[Stream2LLM-MLSys26|Stream2LLM]] — streaming prompt 的 LCP 失效，与静态 [[RadixAttention]] 形成动态更新对照。
- [[SpanQueries-MLSys26|SpanQueries]] — 扩展 [[Prefix-Caching]] 语义至可交换 span，与 radix 的严格前缀匹配互补。
- [[LMCache-arXiv25|LMCache]] — 跨节点 KV 层可与 engine radix/prefix cache 互补，但未联合评测。
- [[KVCacheInTheWild-ATC25|KVCacheInTheWild]] — 生产 trace 刻画 prefix 复用假设，建议与 radix-tree 结构联合评测 eviction policy。
- [[ScaleSearch-MLSys26|ScaleSearch]] — 讨论与 [[RadixAttention]] 集成长 context decode 的 mixed-precision sink cache（见 paper 页）。
- [[DriftBench-MLSys26|DriftBench]] — serving benchmark 语境下的 radix/prefix 行为评测（见 paper 页）。

## 已知局限 / 开放问题

- cache-aware scheduling 的 starvation 与多租户 fair scheduling 未集成（[[SGLang-NeurIPS24|SGLang]]）。
- 多副本、跨地域、[[Disaggregation]] 下 radix cache 一致性与 KV transfer 语义缺失。
- 与 [[vLLM]] 现代 prefix caching 的公平对比需更新 baseline；SGLang 论文对 v0.2.5 的 **6.4×** 不能自动外推到 2025–2026 引擎。
- fuzzy semantic prefix matching 的质量边界未验证（[[SGLang-NeurIPS24|SGLang]] future work）。
- RadixAttention 与 DRAM/disk 多层 KV（FlexGen 方向）、[[LMCache-arXiv25|LMCache]] remote tier 的 Pareto 曲线未建立。
- worker crash 后 radix 节点 ref count 与 cache 一致性、跨用户侧信道风险，论文未系统讨论。