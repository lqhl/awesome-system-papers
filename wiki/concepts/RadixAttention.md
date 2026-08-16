---
type: concept
aliases: [RadixAttention, radix attention, Radix Attention]
parent: "[[KV-Cache]]"
introduced_by: "[[SGLang-NeurIPS24]]"
last_updated: 2026-08-14
tags: [memory, attention, kv-cache, llm-inference, caching]
---

# RadixAttention

> RadixAttention 用压缩前缀树（radix tree）索引多个请求的 [[KV-Cache]]。新请求先找与已有 token 序列完全相同的最长前缀，只计算没有命中的后缀；调度器再优先执行共享前缀较长的请求，提高缓存复用率。

## 它解决什么问题

LLM 应用不再只有一次独立调用。少样本提示、多轮对话、agent、搜索树和结构化语言模型程序，常会重复同一段 system prompt、示例、对话历史或搜索分支。普通 serving 引擎即使能让一批序列共享物理 KV block，也不一定会长期保留已经结束的请求，更不知道以后哪个请求会复用它。

RadixAttention 把“是否共享过同一前缀”变成一个可查询的运行时索引。它管理的是**精确 token 前缀**，不是任意中间子串，也不是语义相似文本。只要文档顺序、模板标点或 tokenizer 结果不同，最长匹配就可能很短。

## 核心机制

[[SGLang-NeurIPS24]] 中的实现包含四部分：

1. **Radix tree 索引**：从根到节点的路径代表一段 token 序列，压缩边可以保存一串 token。相同前缀只存一份 KV。
2. **最长前缀匹配**：请求到达后沿树查找，命中部分直接复用，只对剩余 suffix 做 prefill。
3. **引用计数与叶节点 LRU**：正在运行的请求固定其路径；需要腾出显存时，从没有活动引用的叶节点开始按 LRU 驱逐。
4. **缓存感知调度**：在可运行请求中优先选择命中前缀更长的请求，使相邻请求尽量走同一棵子树，减少刚写入的 KV 被驱逐后又重算。

缓存 KV 和活动请求共享同一个分页显存池。等待队列足够大时，系统可以驱逐缓存，换取更大的 batch。这说明 RadixAttention 不是“无条件保留所有前缀”，而是在复用和当前吞吐之间动态取舍。

## 与相邻机制的区别

- **与 [[PagedAttention]] 的关系**：PagedAttention 解决 KV block 的物理放置、按需分配和 copy-on-write；RadixAttention 解决跨请求的 token 前缀如何查找、保留和调度。前者是内存布局，后者是缓存索引与策略，两者可以叠加。
- **与一般 [[Prefix-Caching]] 的关系**：RadixAttention 是精确前缀缓存的一种具体实现，并把 radix tree 与调度器、上层程序提示结合。并非所有 prefix cache 都使用相同树结构或淘汰策略。
- **与 RAG 文档去重的关系**：RadixAttention 不理解“这些文档内容相同但顺序不同”。[[ContextPilot-MLSys26]] 先重排、去重并标注文档，再让底层精确前缀缓存命中。
- **与动态 prompt 更新的关系**：[[Stream2LLM-MLSys26]] 处理同一请求的 prompt 随时间 append 或 update，只保留新旧序列的最长公共前缀；这与在多个静态请求之间找可复用前缀不同。

## 论文证据告诉了我们什么

### 1. 它最适合有稳定模板和分支结构的请求流

[[SGLang-NeurIPS24]] 在 MMLU、HellaSwag、ReAct agent、多轮对话和分支程序中测到 50%–99% 的 cache hit rate；缓存感知调度平均达到离线最优命中率的约 96%。Chatbot Arena 一个月 trace 中，LLaVA-NeXT-34B 和 Vicuna-33B 的命中率分别为 52.4% 和 74.1%，Vicuna 的平均首 token 延迟降低 1.7 倍。

同一论文报告，相对 vLLM 0.2.5、Guidance 和 LMQL，端到端吞吐最高提高 6.4 倍，单实例延迟最高降低 3.7 倍。但这个数字同时包含前端并行、RadixAttention 和结构化解码优化，且基线版本较早，不能写成“今天单独打开 RadixAttention 必然提高 6.4 倍”。

### 2. Decode 主导或前缀重复少时，收益会很小

SGLang 的短输出多轮对话加速明显，长输出版本几乎没有加速，因为时间主要花在 decode，省掉 prefill 也改变不了总时长。没有复用的 ShareGPT 流量中，树维护只占 74.3 秒运行时间中的 0.2 秒，说明平均开销很低；论文没有充分测量极短 prompt、高并发和频繁驱逐时的 P99 CPU 开销。

[[SPEX-OSDI26]] 提供了搜索型推理中的具体用法：多个 speculative reasoning 分支若一起送入 SGLang，可以复用共同祖先的 KV；若分支零散到达，小 batch 与低前缀复用会同时发生。SPEX 的主要贡献仍是推测未来搜索工作并隐藏 reward 屏障，RadixAttention 只是把共同前缀转成额外收益，论文没有把两者的贡献完全分开。

### 3. 精确匹配对 RAG 文档顺序很敏感

[[ContextPilot-MLSys26]] 的 MultihopRAG 实验中，原始 SGLang RadixCache 命中率为 8.49%；先把重复文档对齐后升到 20.56%，再配合调度升到 33.97%。另一些原始配置只有约 5% 命中。原因不是 radix tree 查找错误，而是检索器每次给相似文档排出不同顺序，token 前缀很快分叉。

ContextPilot 用自然语言 annotation 保存原始相关性顺序，论文多数任务的准确率持平或提高。但严格证据顺序、隐私隔离或模型不能稳定遵循 annotation 时，这种重排未必安全。因此“先重排来喂出更多 prefix hit”是应用层取舍，不是 RadixAttention 本身保证正确。

### 4. 缓存策略要用真实复用分布验证

[[KVCacheInTheWild-ATC25]] 发现不同请求类别的 KV 复用模式不同，并研究了 workload-aware 淘汰；它把与 radix tree、prefix cache 的联合评测列为后续工作。这个证据支持“LRU 不一定对所有流量最优”，但没有证明其策略已能直接替换 SGLang 的 leaf-LRU。

[[DriftBench-MLSys26]] 提醒，框架、硬件和量化路径变化可能让固定请求输出发生漂移，并把 PagedAttention、RadixAttention 与量化交互列为未覆盖因素。它没有单独测量 radix tree，因此只能作为正确性监控的开放问题，不能据此断言 RadixAttention 会导致漂移。

### 5. 稀疏或压缩 KV 需要新的元数据接口

[[MoE-nD-arXiv26]] 每层保留不同长度的 token KV；[[NSA-ACL25]] 在注意力内选择 block；[[ScaleSearch-MLSys26]] 研究 mixed-precision KV。这些工作都指出，若想与 PagedAttention 或 RadixAttention 组合，缓存索引还需表达“每层保留位置不同”“某些 block 精度不同”或“只访问选中 block”。论文只提出集成方向，没有给出可工作的联合系统或端到端结果。

[[vLLM-SOSP23]] 也把与跨机 KV tier、prefix cache 和 RadixAttention 的结合列为后续方向。它证明分页 block 是合适基础，但没有验证多节点 radix tree 的一致性与容错。

## 设计取舍

| 选择 | 好处 | 代价与边界 |
|---|---|---|
| 精确 token 匹配 | 不改变 attention 数学结果，复用正确性清楚 | 文档重排、模板微小变化都会失配 |
| 最长前缀优先调度 | 提高命中率并减少重复 prefill | 冷请求可能等待更久，存在饥饿风险 |
| 缓存与运行请求共用显存池 | 内存利用灵活，高负载可优先扩大 batch | cache hit 会随排队和显存压力波动 |
| 叶节点 LRU | 实现简单，不驱逐仍在使用的路径 | 未必适合不同类别、租户和复用分布 |
| 上层暴露 `fork` 与 prefix hint | 动态 agent、搜索树也能及时共享 | 需要前端和 runtime 协同，普通 API 看不到完整程序结构 |

## 批判性分析

RadixAttention 最有价值的地方，是把“程序调用之间的重复”从应用层偶然现象变成 serving runtime 的一等状态。它也揭示了一个更一般的结论：缓存命中不仅由保存了什么决定，还由请求顺序、worker affinity 和上层 prompt 组织方式决定。

但它的名称容易让人误以为改变了 attention 算法。实际上，它通常不改变模型计算公式，只是在 prefill 前跳过已有的精确前缀 KV。它也不能复用任意中间片段，更不能凭语义相似直接复用 KV。把所有“上下文复用”都归到 RadixAttention，会掩盖 ContextPilot 的重排、Stream2LLM 的动态失效，以及分布式 KV 传输各自解决的不同问题。

原始 SGLang 证据覆盖多类 benchmark 和一段生产 trace，但生产部署主要是单 worker、低流量模型。多副本、PD 分离、worker 弹性回收、跨地域和强租户隔离下，树的所有权、路由、失效和恢复仍没有完整答案。

## 局限与开放问题

- **公平性**：最长命中优先可能让没有热门前缀的请求饥饿，需要把命中收益与等待时间、租户优先级共同建模。
- **隔离与隐私**：跨用户共享 KV 是否允许、命中时间能否泄露其他请求的前缀，需要明确的 cache namespace 和威胁模型。
- **分布式一致性**：router 的元数据树、worker 的实际缓存和驱逐事件如何在故障、迁移与弹性扩缩容时保持一致？
- **动态内容**：RAG 文档版本变化、prompt 中间位置更新以及流式输入，会让简单精确前缀快速失效。
- **异构 KV**：每层稀疏、混合精度、远端存储和压缩 KV 如何共享同一索引，仍缺统一抽象。
- **现代基线**：SGLang 论文中的 6.4 倍结果不能直接外推到后续 vLLM、SGLang 和其他 engine 版本，需要在相同内核、调度和硬件上重测。

## 相关论文

- [[SGLang-NeurIPS24]]：提出 RadixAttention、leaf-LRU 与缓存感知调度。
- [[SPEX-OSDI26]]：搜索型推理把 speculative branches 合批，并利用共同前缀 KV。
- [[ContextPilot-MLSys26]]：通过文档对齐和调度，把集合重叠转化为精确前缀命中。
- [[Stream2LLM-MLSys26]]：处理持续变化 prompt 的最长公共前缀失效。
- [[KVCacheInTheWild-ATC25]]：测量真实复用分布，并指出固定 LRU 的适用边界。
- [[DriftBench-MLSys26]]：把 serving 栈变化下的输出漂移列为组合风险，未单独验证 RadixAttention。
- [[MoE-nD-arXiv26]]：暴露每层可变 KV 与现有 page/radix 元数据的不匹配。
- [[NSA-ACL25]]：提出稀疏 block 选择与 KV/page 管理的联合方向。
- [[ScaleSearch-MLSys26]]：提出 mixed-precision KV 与 radix/page 管理的集成问题。
- [[vLLM-SOSP23]]：提供分页 KV 基础，并把跨层、跨机前缀管理列为后续方向。

## 相关概念

- [[KV-Cache]]、[[Prefix-Caching]]、[[PagedAttention]]、[[Continuous-Batching]]、[[SGLang]]
