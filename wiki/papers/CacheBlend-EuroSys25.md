---
type: paper
name: CacheBlend
full_title: "CacheBlend: Fast Large Language Model Serving for RAG with Cached Knowledge Fusion"
authors: [Jiayi Yao, Hanchen Li, Yuhan Liu, Siddhant Ray, Yihua Cheng, Qizheng Zhang, Kuntai Du, Shan Lu, Junchen Jiang]
venue: EuroSys
year: 2025
tags: [llm-serving, rag, kv-cache, cache-reuse, selective-recompute, prefix-caching, area/ai-infra]
source_pdf: "[[eurosys25-yao-cacheblend.pdf]]"
source_md: "[[eurosys25-yao-cacheblend]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# CacheBlend：通过缓存知识融合为 RAG 提供服务的快速大型语言模型（EuroSys 2025）

> **原题**：CacheBlend: Fast Large Language Model Serving for RAG with Cached Knowledge Fusion

> **一句话总结**：CacheBlend 抓住 RAG 多 chunk 输入里“非 prefix chunk 的 KV cache 可复用但缺 cross-attention”的缝隙，假设 cross-attention / KV deviation 只集中在约 10-15% token 上，通过 selective KV recompute 加 KV loading pipeline，在 3 个模型、4 个数据集上把 TTFT 降低 2.2-3.3x、吞吐提升 2.8-5x，质量接近 full KV recompute。

## 问题与动机

RAG 服务的输入通常不是一个长而稳定的 prefix，而是“多个检索 chunk + 用户 query”的组合。很多 chunk 会跨请求复用，但每次组合方式不同；对这些长 context 做完整 prefill 会直接拉高 TTFT。论文给出的量级是：4K token 输入上，Llama-34B / Llama-70B 在单张 A40 上 prefill 可到约 3 秒 / 6 秒，prefill 因而成为用户等待 first token 和系统吞吐的主瓶颈。

已有 [[Prefix-Caching]] 的正确性很好，因为 prefix 的 [[KV-Cache]] 不依赖后续 token；[[vLLM]]、[[SGLang]]、RAGCache 都属于这一类思路。但 RAG 的关键上下文常常来自多个相互独立的文本块，只有第一个 chunk 是 prefix。论文用 Musique 和 2WikiMQA 显示，增加检索 chunk 数会显著改善 F1，直到 lost-in-the-middle 开始伤害质量；这说明“只缓存第一个 chunk”在多 hop QA / 多文档摘要中天然不够。

另一个极端是 full KV reuse：把每个 chunk 的 KV cache 独立预计算后拼起来，再用 position buffer 或 positional recovery 保持位置语义。这个方法接近 zero-prefill，但它忽略非 prefix chunk 对前文 chunk 的 cross-attention。CacheBlend 的核心问题因此被限定得很清楚：不是压缩 context，也不是替代 retriever，而是在多个已缓存 chunk 被拼进同一个输入时，怎样快速融合这些 cache，使生成质量接近 full prefill。

这篇论文的贡献更像一个系统化的中间点：比 full KV reuse 多做少量 recompute，补回关键 cross-attention；比 full KV recompute 少算绝大多数 token；再利用 KV 从 CPU RAM / SSD 进 GPU 的 loading 时间把这部分 recompute 尽量藏掉。

## 关键观察 / 隐含假设

- **观察 1：RAG 中多个可复用 chunk 同时出现，且这些 chunk 对质量有实质作用。** 论文在 Musique 和 2WikiMQA 上用 top-k chunk 数量展示 F1 随 chunk 增加而上升，说明多 chunk 不是冗余 prompt 装饰。
  - **依赖假设**：生产 RAG workload 有足够高的 chunk 复用率，检索 chunk 的边界和 hash 稳定，context token 占 prefill 成本的大头。
  - **可能失效场景**：高度个性化、一次性文档、实时生成上下文、chunking 策略频繁变化，都会让 KV cache hit rate 降低。

- **观察 2：full KV reuse 的主要质量损失来自缺失 chunk 间 cross-attention，而不是单纯的位置编码错误。** 论文用 Messi / Ronaldo 的例子和 attention matrix 可视化说明，两个 chunk 单独预计算后会完全缺失它们之间的 attention，forward attention matrix 也随之偏离 full prefill。
  - **依赖假设**：目标任务确实需要跨 chunk 联合推理；如果 chunk 彼此独立，或者 prompt template 才是主要复用对象，full KV reuse 已经可能足够。
  - **可能失效场景**：单 chunk RAG、prompt-template reuse、可以由每个 chunk 独立回答再 rerank 的任务，CacheBlend 的质量优势会变小。

- **观察 3：需要修正的 KV deviation 是稀疏的。** Figure 6 / 7 表明，优先 recompute 高 KV deviation token 能最大幅降低 attention deviation，且大约 10-15% token 的 deviation 明显高于其他 token。
  - **依赖假设**：[[Attention]] 在这些 transformer RAG workload 中保持稀疏，跨 chunk 依赖集中在少数 token 上。
  - **证据强度**：中。论文跨 3 个模型和 Musique 做了 measurement，但没有覆盖更长 context、更强长上下文模型、代码/表格等结构化文档。

- **观察 4：HKVD token 在相邻层之间高度相关。** Figure 8 用 Spearman rank correlation 说明上一层高 KV deviation 的 token 很可能仍是下一层候选，因此可以渐进过滤，而不必每层 full prefill 后再选 token。
  - **依赖假设**：token embedding 在 transformer 层间变化相对平滑，KV deviation 的排序可跨层迁移。
  - **可能失效场景**：非 transformer 架构、层间表征剧烈变化的模型、特殊 attention / MoE 变体、极深模型中后层语义突变，都可能削弱这个相关性。

- **假设 1：KV loading latency 足以隐藏 selective recompute。** 论文给出 Llama-7B、4K context、15% recompute 时每层 recompute 约 3 ms，而从 NVMe SSD load 一层 KV 约 16 ms；但 Llama-70B 上 15% recompute 约 7 ms，SSD load 约 4 ms，已经不能完全隐藏。
  - **证据强度**：中。这个假设是系统收益的关键，但它强依赖模型大小、batching、存储设备、GPU、IO jitter 和 cache 所在层级。

## 核心方法

CacheBlend 把每个可复用 text chunk 的 [[KV-Cache]] 当作可独立存储的对象。请求到来后，系统按应用逻辑把输入切成 chunks，用类似 [[vLLM]] block hashing 的方式查询 KV cache store；命中的 chunk 不直接拼接后交给 decode，而是交给 fusor 做“带少量修正的拼接”。

Selective KV recompute 是 fusor 的核心。对每一层，CacheBlend 只对选中的 token 计算新的 Q/K/V；未选中的 token 继续使用预计算 KV。随后它把新算出的 selected-token K/V 与未选 token 的 cached K/V 合并，让 selected token 的 attention 仍然能看见所有 token，最后产生下一层输入。这样 compute overhead 近似与 recompute ratio 成正比：如果每层更新 15% token，就大致只付出 full prefill 的一小部分计算。

问题在于：真正应该更新的是高 KV deviation token，但 KV deviation 的 ground truth 需要 full recompute 才知道，直接求会抵消优化收益。CacheBlend 的折中是 HKVD gradual filtering：先在早期层选择比目标比例更大的候选 token，再在后续层只在上一层候选中计算 deviation 并逐步收窄。这个设计回应的是“HKVD token 跨层相关”的观察，用局部 recompute 的结果近似追踪哪些 token 最需要修正。

系统层面，CacheBlend 的 Loading Controller 估计两个延迟：给定模型、context length 和 recompute ratio 的 recompute delay，以及从某个存储设备加载一层 KV 的 loading delay。它用这些估计决定 recompute ratio，且保留一个经验下限 `r*`，论文中默认约 15%，以避免为了 latency 过度牺牲质量。固定 recompute ratio 时，controller 还可以选择最便宜、同时不会增加 TTFT 的存储层级。

实现上，CacheBlend 在 [[vLLM]] 上增加约 3K 行 Python / PyTorch 代码，暴露 `fetch_kv(text, layer_id)`、`prefill_layer(input_dict, KVCache)`、`synchronize()` 三个接口。它用两个线程把第 i 层 partial prefill 与第 i+1 层 KV loading pipeline 起来；miss 的 KV 在运行时生成后可后台写回 CPU RAM 或 SSD，cache 满时用 LRU 淘汰。论文版本只处理单级存储和单请求内 fusion，未做跨节点共享。

## 设计取舍

- **用近似质量换 prefill 速度**：CacheBlend 不保证生成结果 bitwise 等同 full KV recompute，而是用少量 selective recompute 让 F1 / Rouge-L 接近 full prefill。这个选择适合 RAG serving，但对强正确性任务需要额外 guardrail。
- **用 workload locality 换存储成本**：预计算和保存 chunk KV 只有在 chunk 反复命中时才划算；cache miss、chunk 版本变化、tokenizer / model 版本变化都会带来额外管理成本。
- **用系统 pipeline 掩盖算法开销**：把 recompute 藏在 KV loading 里很漂亮，但它也把性能绑定到 IO 行为。存储太快时 hide 不住 compute，存储太慢或 jitter 太大时又会拖慢 TTFT。
- **用引擎内改造换通用性**：CacheBlend 能接入 [[vLLM]] 的 layer-level prefill，但需要侵入推理引擎内部接口。迁移到 DistServe、StableGen 或 disaggregated serving 不只是换一层 API。
- **用单级 cache 简化设计**：论文只讨论 CPU RAM 或 SSD 这类单级存储与 LRU，避开了多级 cache、跨 GPU / 跨节点一致性、租户隔离和写回失败处理。

## 实验与结果

- **实验设置**：模型覆盖 Mistral-7B、Yi-34B、Llama-70B，其中 Yi-34B 和 Llama-70B 使用 8-bit quantization；硬件是 Runpod 节点、128 GB RAM、2 张 A40、1 TB NVMe SSD（测得 4.8 GB/s）。Mistral-7B / Yi-34B 用 1 GPU，Llama-70B 用 2 GPU。
- **数据集与任务**：2WikiMQA 200 条、Musique 150 条用于 multi-hop QA；SAMSum 200 条、MultiNews 60 条用于 summarization / few-shot 场景。扩展 RAG workload 用 Musique 和 2WikiMQA 各 1500 原始 query，再由 GPT-4 生成 4500 相似 query，top-6 chunk、512 token chunk、跳过前 1K 冷启动请求。
- **baseline**：Full KV recompute、[[Prefix-Caching]]、PromptCache 风格 full KV reuse、LangChain MapReduce、MapRerank。值得注意的是，prefix caching baseline 被给予了“RAM/SSD 到 GPU 无 loading delay”的理想化假设，对 baseline 是有利的。
- **主结果**：相对 full KV recompute / prefix caching，CacheBlend 的 TTFT 降低 2.2-3.3x；在相近 TTFT 下，吞吐相对 full recompute 提升 2.8-5x，相对 prefix caching 最高提升 3.3x。
- **质量结果**：相对 full KV recompute 和 prefix caching，整体质量下降不超过约 0.01-0.03；相对 full KV reuse，F1 / Rouge-L 提升约 0.15-0.35。论文也报告 QA 上比 full KV reuse 高 0.1-0.2 absolute F1，summarization 上高 0.03-0.25 Rouge-L。
- **recompute ratio sensitivity**：在 Yi-34B 上，5%-18% selective recompute ratio 即可让质量损失最多约 0.002，同时带来 4.1-6.6x TTFT reduction（相对 full recompute）和 3.4-6.1x（相对 prefix caching）。
- **chunk / batch / storage sensitivity**：chunk 数量、chunk 长度变化下，为保持 <=0.015 F1 loss 所需的 compute time reduction ratio 相对稳定；batch 越大，prefill 越成为主导瓶颈，CacheBlend 越有空间；RAM 和较慢 SSD 上都能保持较低 TTFT 与小质量损失。

## 批判性分析

### 论证链条

论文的主链条基本闭合：RAG 需要多个 chunk，prefix-only cache 无法复用非 prefix chunk；full reuse 忽略 cross-attention 会伤质量；cross-attention 引起的 KV deviation 具有稀疏性和跨层相关性；因此 selective recompute 少数 HKVD token 可以恢复大部分质量；如果 KV loading 足够慢，额外 recompute 又可以被 pipeline 掩盖。

最强的地方是它没有把“缓存更多 KV”包装成无条件收益，而是明确提出了 full KV reuse 的质量失败机制。最脆的地方也在这里：实验证明的是一组 RAG / QA / summarization benchmark 上的平均指标接近 full recompute，不是逐请求语义等价，也不是对所有多 chunk 任务的 correctness guarantee。

### 假设压力测试

CacheBlend 依赖的 workload locality 很强。扩展 workload 用 GPT-4 生成相似 query 来模拟 chunk reuse，这能制造可控 reuse，但离真实企业 RAG 的文档更新、权限过滤、租户差异、retriever drift 还有距离。如果真实 hit rate 低，CacheBlend 会退化为额外复杂的 prefill 系统。

HKVD 稀疏性也需要继续压测。论文把 10-20% recompute 作为经验区间，但 dense reasoning、代码/表格、多模态 caption、长链条 causal reasoning 可能让跨 chunk 依赖更分散。此时固定 `r* = 15%` 可能不够，controller 需要能按请求检测风险并 fallback 到更高 ratio 或 full recompute。

Pipeline 假设在不同部署下方向不一定一致。较慢 SSD 能隐藏 7B 的 recompute，却可能拉高绝对 TTFT；更快的 CPU RAM / HBM 会让 loading 不再是遮蔽物；disaggregated serving 中 KV 从远端节点加载时，网络抖动可能主导尾延迟。论文展示了 RAM 和 slower disk 的平均表现，但没有给 P99 / IO jitter 下的结果。

### 实验可信度

baseline 选择总体合理，并且 prefix caching 的理想化 loading 假设对 CacheBlend 不偏袒。Full KV reuse 使用 PromptCache 风格实现，也抓住了论文要击败的核心对照。不过没有比较 PromptCache 的 scaffolding scheme，因为 RAG runtime 需要人工选择重要 chunk；这个排除是可以理解的，但也意味着 full KV reuse 类方法的 best-effort 空间没有完全展开。

数据集覆盖 QA 和 summarization，但规模偏小，且质量指标是 F1 / Rouge-L。它们能说明平均答案相似度，却不能证明 factual correctness、引用正确性、拒答行为或 hallucination rate。对 RAG 系统来说，更有说服力的实验会包括 production trace、真实 cache hit distribution、query-level failure cases、以及 CacheBlend 和 full recompute 输出不一致时的人工评估。

系统指标也偏平均值。TTFT 和 throughput 很关键，但缺少 P95/P99、GPU utilization、cache eviction hit rate、write-back amplification、KV store 容量压力和多租户隔离开销。由于 CacheBlend 把 IO 和 compute pipeline 到一起，尾延迟比均值更容易暴露问题。

### 系统性缺陷

CacheBlend 对 serving engine 的侵入不小：它需要 layer-wise prefill、selected-token masking、KV fetch synchronization 和后台写回。论文说实现约 3K 行，但没有讨论调试复杂度、和 [[Continuous-Batching]] / [[Chunked-Prefill]] / disaggregated prefill-decode scheduler 的交互，也没有说明 partial prefill 请求和普通请求共存时的调度策略。

正确性与运维边界也留白较多。KV cache 与 model weights、tokenizer、RoPE scaling、chunking 策略、retriever 版本强绑定；一旦任意一项变化，旧 cache 必须可靠失效。论文未讨论 cache corruption、写回失败、权限隔离、敏感文档 KV 泄漏、租户间 cache 共享策略和 observability。

还有一个小的不确定点：Loading Controller 文字中“选择 cheapest device”的不等式表述看起来可能有方向混淆；从前文 pipeline 逻辑看，要隐藏 recompute 应该需要 loading delay >= recompute delay，或至少两者匹配。这个不影响主设计理解，但说明 controller 细节最好回原始实现核对。

## 局限与后续工作

- **局限 1：仅覆盖 transformer LLM。** 论文明确说 §4.3 的 insight 只适用于 transformer；Mamba、Griffin 等架构需要另行研究。
- **局限 2：模型和部署覆盖有限。** 实验只有 Mistral-7B、Yi-34B、Llama-70B，且部分使用 8-bit quantization；没有覆盖更新的 serving engines、更多 quantization 设置、MoE、超长上下文模型。
- **局限 3：没有分布式 KV cache。** 论文未研究跨 compute nodes 共享 KV cache，这恰好是大型 RAG serving 很可能遇到的场景。
- **局限 4：缺少 production trace。** 当前复用模式主要由 benchmark 和合成相似 query 构造，不能直接说明真实企业知识库的 hit rate、更新率、权限过滤和尾延迟。
- **Future work 1：请求级 adaptive recompute。** 用可观测的 deviation / uncertainty 指标决定每个请求、每层、每个 chunk 的 recompute ratio，并在高风险时自动 fallback 到 full recompute。
- **Future work 2：production KV-cache study。** 在真实 RAG trace 上测 chunk reuse distribution、cache footprint、TTL、eviction policy、P99 TTFT 和质量偏差，检验 CacheBlend 的经济性边界。
- **Future work 3：多级 / 分布式 KV store。** 把 GPU HBM、CPU RAM、local SSD、remote SSD / object store 统一进 controller，并显式建模网络 jitter、租户隔离和版本失效。
- **Future work 4：质量 guardrail。** 对 CacheBlend 输出和 full recompute 或高 ratio recompute 做抽样对比，学习何时 selective recompute 会产生语义级错误，而不仅是 F1 / Rouge-L 下降。

## 相关

- **相关概念**：[[KV-Cache]]、[[Prefix-Caching]]、[[RAG]]、[[Attention]]、[[Sparse-Attention]]、[[Chunked-Prefill]]
- **同类系统**：[[vLLM]]、[[SGLang]]、[[CacheGen-SIGCOMM24]]、[[LMCache-arXiv25]]、PromptCache、RAGCache
- **后续工作**：[[LMCache-arXiv25]] 可以看作 CacheBlend 团队把 KV cache reuse / offload 做成更完整 cache layer 的方向延伸
- **同会议**：[[EuroSys-2025]]
