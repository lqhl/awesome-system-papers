---
type: entity
kind: system
aliases: [SGLang]
status: active
last_updated: 2026-08-14
tags: [llm-inference, serving, scheduling]
---

# SGLang

> SGLang 是面向结构化语言模型程序的开源推理系统：前端把多次生成、分支、约束输出等程序结构显式交给运行时，后端用 [[RadixAttention]]、缓存感知调度和高性能执行复用这些结构。

## 是什么

[[SGLang-NeurIPS24]] 把语言模型程序（LM Program）视为一串有依赖的模型调用，而不是彼此独立的 completion。Python 前端提供 `gen`、`select`、`fork`、`join`、图像输入和 regex 约束等 primitive；interpreter 可以异步提交调用并在真正取结果时同步。这个接口使 few-shot、agent、Tree-of-Thought、多轮对话、[[RAG]] 和结构化 JSON 的共享前缀与并行分支不再隐藏在字符串拼接里。

后端 SRT 的核心机制是 RadixAttention。它用 radix tree 把 token prefix 映射到 [[KV-Cache]]，在不同请求、不同 program call 之间做最长前缀匹配，只计算没有命中的 suffix。活动请求与缓存 token 共用一个分页内存池；ref count 保护正在使用的节点，LRU 从叶节点驱逐。scheduler 优先处理可复用 prefix 更长的请求，使执行顺序接近对 radix tree 做深度优先遍历。

另一项原始机制是 compressed FSM。regex 转成有限状态机后，连续只有唯一合法后继的边可以压缩成一段 token；运行时一次跳过多个确定 token，再 retokenize 保持 tokenizer 对齐。它主要适合 JSON 和固定格式，不等于任意 grammar 引擎，也不适合把开放式推理过程强行压缩。

今天的 SGLang 还经常作为通用高性能 engine 使用，论文未必使用它的 DSL。[[DCP-OSDI26]] 修改其 pipeline scheduler，[[Strata-OSDI26]] 集成分层 KV cache，[[UEP-OSDI26]] 替换 MoE 通信路径，[[ReSpec-MLSys26]] 把它放进 RL rollout。读这些结果时要区分“改进 SGLang 本身”“借 SGLang 承载新机制”和“只把 SGLang 当 baseline”。

## 关键观察 / 隐含假设

- **观察：LM program 的 prefix 局部性可以跨调用利用。** 原始论文在 MMLU、HellaSwag、agent、多轮对话和分支 workload 中测到 50%–99% cache hit rate，在线 cache-aware scheduling 平均达到离线最优 hit rate 的约 96%。但长输出对话中 decode 主导，论文也报告几乎没有加速（[[SGLang-NeurIPS24]]）。
- **观察：前端信息和后端执行必须一起设计。** `fork` 的 prefix hint、分支异步提交和 radix tree 插入顺序共同决定复用率；只保留一棵被动 cache tree 不能得到相同结果。这个结论适用于愿意暴露 program structure 的应用，普通 OpenAI-compatible 请求能提供的信息更少。
- **观察：缓存感知排序会和公平性冲突。** 优先最长共享 prefix 可以减少 prefill，却可能让冷 prefix 或新租户长期等待。原始论文明确承认 starvation 风险，但没有给出 P99、公平份额或多租户隔离结果（[[SGLang-NeurIPS24]]）。
- **观察：引擎已经成为研究底座，性能归因必须做消融。** [[DCP-OSDI26]] 在 SGLang 0.4.1 上动态选择 prefill chunk，并重排 decode microbatch；4×A100 PCIe 的结果支持“低带宽互连上 PP 可优于 TP”，不等于 SGLang 默认 scheduler 有同样能力。[[UEP-OSDI26]] 在保持 model code 不变时把所测 SGLang MoE 吞吐最多提高 40%，收益来自 host proxy 通信抽象，而不是 RadixAttention。
- **观察：层级存储会放大 layout 与调度耦合。** [[Strata-OSDI26]] 在生产 SGLang 中用 GPU 线程搬运并转置大量碎片 KV page，再让 scheduler 用 decode 填 I/O 空洞；H200 长上下文实验在相同平均 TTFT 下，相对 TensorRT-LLM-HiCache 最高提高 3.75 倍吞吐。这个数字依赖长上下文、H200 和论文配置，不能当作一般 SGLang 相对 TensorRT-LLM 的结论。
- **观察：特殊应用常需要修改 engine 的调度单位。** [[SPEX-OSDI26]] 修改 SGLang 前端，让 Tree-of-Thought 请求逐个异步返回，并按 prefix 复用调度；DFS query throughput 提高 1.8–3 倍、BFS 提高 1.2–1.9 倍。不过约 1.2 倍稳定收益来自会改变实际搜索空间的 early termination，不能全部归为语义不变的 engine 加速。
- **观察：框架迁移不是纯性能替换。** [[DriftBench-MLSys26]] 在相同权重与输入下测 vLLM、SGLang、TensorRT-LLM 的输出 flip，发现 drift 对 workload 极敏感；Math 平均 16.74%，Code 仅 0.09%。这要求上线前按实际任务做功能回归，而不是只看 perplexity 或吞吐。
- **假设：prefix 可由精确 token 串识别。** RadixAttention 对公共 system prompt、few-shot template 和多轮历史很有效；内容语义相同但 token 顺序或位置不同仍会 miss。[[ContextPilot-MLSys26]]、[[CacheBlend-EuroSys25]]、[[CacheSlide-FAST26]] 分别从 context 对齐、非前缀 chunk 和位置漂移方向扩展了这一边界。
- **假设：radix metadata 与 KV 生命周期可以可靠共存。** 分层存储、preemption、speculative rollback、跨 worker cache 和 engine crash 会增加一致性状态。原始论文主要证明稳态性能，没有完整覆盖恢复、隐私侧信道和 metadata 重建。

## 演进时间线

- 2024 NeurIPS：[[SGLang-NeurIPS24]] — 提出 LM Program 前端、RadixAttention、cache-aware scheduling、compressed FSM 和 API speculative execution；在论文 workload 中相对 vLLM/Guidance/LMQL 吞吐最高 6.4 倍、单实例延迟最高降低 3.7 倍。
- 2025–2026：[[Libra-ICLR26]]、[[CRAFT-MLSys26]] — 把 SGLang 用作 MoE load balancing 与 expert replication 的实验和部署底座；这些论文的增益来自各自的 MoE 机制。
- 2026 MLSys：[[ReSpec-MLSys26]] — 在 VeRL 与 SGLang 上做自适应 speculative rollout 和在线 drafter 对齐，Qwen2.5 3B–14B 的 RL 端到端训练在所测配置中加快 1.5–4.5 倍。
- 2026 MLSys：[[WAVE-MLSys26]] — 把 Wave 生成的 AMD Attention backend 接入 SGLang；跨 MI300/MI325/RX9070 的证据支持 AMD 可移植性，但 NVIDIA 路径没有同等验证。
- 2026 OSDI：[[DCP-OSDI26]] — 在 4×A100 PCIe 上为 SGLang 加入动态 chunked prefill 与 delay scheduling，缩小 PP 的动态 bubble。
- 2026 OSDI：[[ECHO-OSDI26]] — 面向原生稀疏 Attention，把完整 KV 放 host DRAM，并在 SGLang 对照下依靠更大并发提高吞吐；结果针对 DSA、H20/H200 和长上下文。
- 2026 OSDI：[[SPEX-OSDI26]] — 用 SGLang 承载投机式 Tree-of-Thought 搜索，暴露应用语义和 engine callback 之间的接口需求。
- 2026 OSDI：[[Strata-OSDI26]] — 在 SGLang 中加入 GPU-assisted KV I/O、HiRadixTree 与 I/O-aware scheduling，把 radix prefix 索引扩展到 GPU/CPU/SSD 层级。
- 2026 OSDI：[[UEP-OSDI26]] — 以 host proxy 统一不同 GPU/NIC 的 MoE token transfer；SGLang 无需修改 model code，但每 GPU 最多使用 4 个 CPU core。
- 2026 OSDI：[[RollArt-OSDI26]]、[[RLinf-OSDI26]] — 将 SGLang 作为 RL generation worker 的一种执行后端，说明 engine 已进入训练与 rollout 控制面，而不仅是在线 API 服务。

## 设计边界与使用建议

- **不要照搬原始峰值。** [[SGLang-NeurIPS24]] 的 vLLM baseline 是 v0.2.5；6.4 倍是多个 workload 中的最高值，不是今天任意模型上的固定差距。
- **先判断有没有精确 prefix。** few-shot、固定 agent template、多轮历史和分支搜索通常有收益；低重复、长输出或每请求都不同的上下文，RadixAttention 可能只留下很小管理开销。
- **把命中率和公平性一起看。** 只报 cache hit 或 mean TTFT 会隐藏冷请求 starvation；应同时报告 P99、每租户等待时间和 cache 占用。
- **区分 engine 与应用语义。** SPEX 的 early termination、ReSpec 的在线 drafter、稀疏 Attention 的 top-k 都可能改变搜索或模型路径；这些收益不能全归因于 SGLang runtime。
- **记录版本和 backend。** SGLang 的 scheduler、kernel、MoE、speculative decoding 和 KV manager 快速演进；相同名字在 AMD、NVIDIA、PD 共置与分离环境中不是同一执行路径。
- **验证恢复与隔离。** radix tree、共享 KV pool 和多层缓存让性能更好，也扩大了 cache 泄漏、ref-count 错误、worker crash 后 metadata 不一致的风险面。

## 相关概念

- [[RadixAttention]]、[[KV-Cache]]、[[Prefix-Caching]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Disaggregation]]、[[MoE]]、[[Speculative-Decoding]]

## 相关论文

- [[SGLang-NeurIPS24]] — 原始系统论文，定义前端语言与 RadixAttention 的共同设计。
- [[CacheBlend-EuroSys25]] — 处理非前缀 RAG chunk 的 KV 复用，补足精确 prefix cache 的边界。
- [[CacheSlide-FAST26]] — 研究 agent prompt 片段位置漂移与 SSD spill，指出原生 SGLang/vLLM 同层 load-write 串行的限制。
- [[ContextPilot-MLSys26]] — 在 SGLang/vLLM 前增加 context 对齐与去重，在所测 workload 中把 KV hit ratio 从约 5% 提到 38%–60%。
- [[CRAFT-MLSys26]] — 在 SGLang 类 MoE serving 中按层选择 expert replica，平均 goodput 提高 1.14 倍且 replica 数减少 7.25–7.5 倍。
- [[ReSpec-MLSys26]] — 把 SGLang speculative decoding 放进非平稳 RL rollout，并在线更新 drafter。
- [[WAVE-MLSys26]] — 为 SGLang 提供 AMD GPU Attention backend。
- [[DCP-OSDI26]] — 修改 SGLang 的 PP prefill/decode 调度，不改变模型权重或请求语义。
- [[ECHO-OSDI26]] — 以 SGLang 为主要基线，研究原生稀疏 Attention 的 host KV pool。
- [[SPEX-OSDI26]] — 修改 SGLang async return 接口以承载投机式 Tree-of-Thought。
- [[Strata-OSDI26]] — 将 radix prefix 管理扩到分层 KV storage，并联合 I/O 与请求调度。
- [[UEP-OSDI26]] — 用 CPU proxy 替换 MoE 通信数据面，保持 SGLang model code 不变。
- [[RollArt-OSDI26]] — 把 SGLang 作为异步 agentic RL generation backend 之一。
- [[DriftBench-MLSys26]] — 量化从 vLLM 迁到 SGLang 等基础设施变更的功能输出风险。
