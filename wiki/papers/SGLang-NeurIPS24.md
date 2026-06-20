---
type: paper
name: SGLang
full_title: "SGLang: Efficient Execution of Structured Language Model Programs"
authors: [Lianmin Zheng, Liangsheng Yin, Zhiqiang Xie, Chuyue Sun, Jeff Huang, et al.]
venue: NeurIPS
year: 2024
tags: [llm-serving, kv-cache, radix-attention, structured-generation, domain-specific-language]
source_pdf: "[[neurips24-zheng-sglang.pdf]]"
source_md: "[[neurips24-zheng-sglang]]"
---

# SGLang: Efficient Execution of Structured Language Model Programs (NeurIPS 2024)

> **一句话总结**：观察到 LM Program（agent、few-shot、branch-solve-merge）天然产生大量可复用 prefix，而通用 [[vLLM]] 类引擎按请求丢弃 [[KV-Cache]]；SGLang 用 Python embedded DSL + **RadixAttention**（radix tree LRU 跨调用共享）+ **compressed FSM**（一次 decode 多 token 的 constrained decoding）做 frontend-runtime co-design，在 Llama-7B 等 workload 上相对 vLLM/Guidance/LMQL 吞吐最高 **6.4×**、延迟最高 **3.7×** 降低。

## 问题与动机

LLM 使用方式正从单次 chat 转向 **Language Model Program（LM Program）**：一次任务包含多次相互依赖的 LLM 调用、Python 控制流、并行分支，以及结构化输入/输出（JSON、选项选择、多模态）。典型场景包括 ReAct agent、tree-of-thought、branch-solve-merge、[[RAG]] pipeline、多轮对话和 regex 约束的 JSON 解码。

作者 claim 现有方案在两个层面断裂：

1. **编程层**：用 OpenAI-like API 手写 LM Program 需要大量 string manipulation、输出解析和并行控制；同等功能的 SGLang 程序代码量约为 naive API 方案的 **2.1×** 更少（Fig. 2 示例）。
2. **执行层**：[[vLLM]]、TGI、TensorRT-LLM 等通用推理引擎不知道 workload 结构，每个 generation call 结束后丢弃 [[KV-Cache]]，无法系统化复用跨调用的共享 prefix；constrained decoding 也通常逐 token mask，错过「确定性多 token 路径」可一次前向的机会。

SGLang 的核心命题是：**把 LM Program 的多调用结构显式暴露给 runtime**，让调度、缓存和 constrained decoding 都能利用程序语义，而不是把每次调用当成独立请求。

## 关键观察 / 隐含假设

- **观察 1：LM Program 在 batch 执行时产生大量、多层次的 prefix 重叠。** 论文在 MMLU（5-shot 示例共享）、HellaSwag（few-shot + 问题前缀两级共享）、ReAct/generative agent（模板与历史调用共享）、multi-turn chat（历史共享）、fork/self-consistency（分支共享）等场景测量到 **50%–99%** 的 cache hit rate；cache-aware scheduling 平均达到最优 hit rate 的约 **96%**（Fig. 13）。
  - **依赖假设**：请求流中存在足够强的 prefix 局部性，且同一 worker 上并发执行的 program instance 会重复相似 context，而非完全随机的一次性 prompt。
  - **可能失效场景**：长输出 multi-turn chat 中 decode 时间主导、共享很少，论文自己也报告「几乎无加速」；若 tenant/workload 彼此无关，radix tree 会频繁 miss 并承受 eviction 开销。

- **观察 2：regex/JSON 约束下，FSM 存在大量 singular-transition 边，语义上等价于一次可跳过的多 token 常量串。** 例如 `{"summary": "` 在常规模型 tokenizer 下虽跨多个 token，但每一步只有一个合法后继；现有系统因 FSM 与 model runner 未深度集成，只能逐 token 解码。
  - **依赖假设**：实际结构化输出可用 regular expression 表达，且压缩边经 retokenization 后仍与模型 tokenizer 对齐。
  - **可能失效场景**：复杂 choice hierarchy（如 `Excellent|Above Average|...`）会在 compressed edge 上扭曲概率分布（Appendix B.3）；非 regex 可表达的 grammar（如 JSON with nested optional fields 的某些变体）需要更强约束机制。

- **观察 3：frontend 知道 fork/前缀结构，能给 runtime 提供可复用 hint；intra-program parallelism 与 cache 复用必须协同设计。** `fork` 时 interpreter 先发 prefix hint 再发 suffix，使 radix tree 插入与 cache-aware scheduling 更简单；禁用 frontend parallelism 或 hint 会显著拉低吞吐（Fig. 8c ablation）。
  - **依赖假设**：用户愿意用 SGLang DSL 编写程序，或上层框架（如 DSPy）可编译到 SGLang backend；程序的控制流不会频繁阻断静态分析/并行。
  - **可能失效场景**：强 data-dependent control flow 使 compiler mode 无法 trace（Appendix D）；API-only 模型无法做 RadixAttention/compressed FSM，只能依赖 API speculative execution。

- **假设 1：把 cached KV 与 running request 放在同一 memory pool，并在高负载时优先 batch size 而非保留 cache，是合理默认。**
  - **证据强度**：中。论文证明 waiting queue 足够大时会 evict 全部 cache 以扩大 batch；这对吞吐有利，但意味着 cache 收益高度依赖负载形态，不是「永远保留 prefix」。

- **假设 2：cache-aware scheduling 按最长共享前缀优先近似 offline DFS 最优顺序，在线场景仍足够好。**
  - **证据强度**：中强。Theorem 3.1 给出 offline 最优性；在线实验接近最优 hit rate。但论文明确承认 greedy 调度可能导致 **starvation**，公平性集成留作 future work。

## 核心方法

SGLang 分为 **frontend language** 与 **backend runtime**，可独立使用，但 co-design 时收益最大。

**Frontend（Python embedded DSL）** 提供 `gen`、`select`、`+=`/`extend`、`fork`/`join`、`image`/`video` 等 primitive；`gen` 支持 `regex` 约束输出。执行默认走 **interpreter mode**：每个 prompt state 由 stream executor 异步提交 primitive，类似 launch CUDA kernel；取结果时再同步。程序也可 trace 成计算图走 compiler mode（Appendix D），但当前对 data-dependent control flow 有限制。

**RadixAttention** 回应观察 1：用 **radix tree** 维护 token 序列到 [[KV-Cache]] 的映射，边可带 token 子串；节点带 ref count，与 [[Continuous-Batching]] 共存；采用 **LRU leaf-first eviction**，cached KV 与 active request 共享 paged memory pool（与 [[PagedAttention]] 兼容）。新请求到达时做最长前缀匹配，只 prefill 未命中 suffix。调度器按 matched prefix length 排序，优先执行共享前缀更长的请求，近似 radix tree 的 DFS 遍历。

**Compressed FSM** 回应观察 2：先把 regex 转成字符级 FSM，再合并连续 singular-transition 边为 compressed edge；解码时沿压缩边 **Jump Forward** 多 token，并用原 tokenizer **retokenize** 保证与模型输入格式一致。对 batch 请求复用预处理后的 FSM，否则吞吐会低 **2.4×**。

**API speculative execution** 面向 GPT 等黑盒 API：第一个 `gen` 可忽略 stop 条件多生成若干 token，后续 primitive 若匹配则复用，减少重复 input token 计费与往返延迟；论文在 Wikipedia 三字段抽取任务上把 input token 成本降到约 **1/3**，但依赖 few-shot prompt engineering 保证匹配准确率。

**Frontend-runtime co-design** 回应观察 3：`fork` 的 prefix hint、intra-program 并行提交、以及与 radix tree 插入顺序的配合，是 RadixAttention 能在 agent/tree-of-thought 等动态结构下仍然高 hit rate 的关键，而不是仅靠被动 prefix cache。

## 设计取舍

- **跨调用 KV 复用 vs 显存留给更大 batch**：cache 与 running request 共用 pool；当 waiting queue 足够大时，系统会 evict 全部 cached tokens 以换取更大 batch。收益是峰值吞吐，代价是低局部性时 cache 不稳定、hit rate 波动大。

- **cache-aware 调度 vs 公平性**：最长前缀优先提高 hit rate 和吞吐，但可能饿死短前缀或冷启动请求；论文承认尚未与 fair scheduling（如 vLLM fairness 工作）集成。

- **regex + compressed FSM vs 概率正确性**：Jump Forward 加速显著（JSON benchmark 吞吐 **1.6×**），但对复杂 choice 约束可能产生错误 token 序列；workaround 是把选项写进 prefill prompt，未从机制上解决 distorted probability。

- **专用 runtime vs 通用引擎**：SGLang Runtime（SRT）深度集成 RadixAttention/FSM，比把 LM Program 直接跑在通用 [[vLLM]] API 上更快，但需要维护独立 stack、与快速演进的 engine 生态并行；同时论文也强调可与 DSPy 等高层框架组合。

- **RadixAttention 默认开启 vs 管理开销**：无复用场景（ShareGPT 100 requests）树维护仅占 **0.2s / 74.3s（<0.3%）**，因此默认开启合理；但在极端高 churn、短 prompt 场景，CPU 侧树操作与 eviction 仍可能变成尾延迟因素——论文未讨论。

- **边界条件**：长输出对话、跨 worker 无 affinity 的数据并行、API-only 模型、强 data-dependent 程序最适合分别依赖 decode 主导、分布式 meta-tree 调度、API speculative、interpreter-only 路径；compressed FSM 最适合常量前缀多的 schema，不适合开放文本生成。

## 实验与结果

- **端到端（open-weight）**：Llama-7B 上相对 Guidance（llama.cpp）、[[vLLM]] v0.2.5 API server、LMQL（HF Transformers），吞吐最高 **6.4×**（Fig. 5），单实例延迟最高 **3.7×** 降低（Fig. 6）；Mixtral-8x7B、Llama-70B tensor parallel 趋势类似（Fig. 7、Fig. 12）。
- **Workload 细分**：MMLU/HellaSwag 主要靠 RadixAttention；JSON 靠 compressed FSM；Tree-of-thought/Skeleton-of-thought 同时受益于 intra-program 并行 + cache；multi-turn chat（short output）收益明显，**long output 几乎无加速**。
- **多模态**：LLaVA-v1.5-7B 吞吐 **0.18 → 1.15 image/s**；LLaVA-NeXT-34B 视频 **0.02 → 0.10 frame/s**（相对作者原始 HF 实现最高约 **6×**）；同图多问题复用 image token 的 KV hash。
- **生产部署**：Chatbot Arena 一个月 trace 显示 LLaVA-NeXT-34B hit rate **52.4%**、Vicuna-33B **74.1%**，Vicuna first-token latency 平均 **1.7×** 降低。
- **Ablation**：RadixAttention 各组件（tree structure、cache-aware schedule、frontend parallelism、fork hint）均必要；随机/FCFS 调度明显变差；compressed FSM 需 batch 级 FSM 复用。
- **API 模型**：GPT-3.5 三字段抽取，API speculative execution 减少约 **3×** input token 成本。
- **分布式**：data parallel 下 router meta-tree + worker sub-tree，MMLU 上报告线性扩展与接近最优 hit rate（Appendix A.4）；与后续 Preble 等并发工作相关。

## Critical Analysis

### 论证链条

论文主链条清晰：**LM Program 的结构化多调用 → 大量可复用 prefix 与可压缩约束路径 → 通用引擎丢弃结构信息 → SGLang 用 DSL 暴露结构 + 三类 runtime 优化 → 多 benchmark 与生产 trace 验证加速**。

最强环节是 RadixAttention 与 workload 结构的对应：不仅展示 6.4× 峰值，还用 hit rate ablation（Fig. 8a/b）证明性能随 cache hit 单调改善，并把 scheduling 与 Theorem 3.1 的 offline 最优性联系起来，使「前缀共享是瓶颈」这一判断较可信。

较弱环节在于 **把「LM Program 范式」推广到所有 LLM serving**。实验大量来自 replay trace 的 agent/benchmark 程序，真实生产流量中一次性短 query 占比、跨 session 隔离、多租户混合时 radix cache 是否仍高 hit，证据主要来自 Chatbot Arena 的单一 worker 部署，外推到大规模多租户集群仍需谨慎。

### 假设压力测试

**Workload 维度**：论文已证明对 few-shot、agent template、RAG context、短输出多轮对话友好；对长输出对话、低重复 prompt、强个性化 context，收益会迅速下降。若未来 agent 转向更长链、更少共享 system prompt，RadixAttention 的 LRU 可能频繁 thrash。

**硬件/规模维度**：实验主要在 A10G/A100 上与 7B–70B 模型；radix tree 在 CPU 维护，GPU 侧仍是 paged KV。极大规模 data parallel 下，router meta-tree 与 weakly consistent eviction 的 affinity 策略决定跨 worker 复用效率，论文只给出 MMLU 四 worker 初步结果，未覆盖 WAN、PD 分离或 [[Disaggregation]] 场景。

**模型/模态维度**：compressed FSM 假设 regex 足以表达输出约束；对 tool-call XML、grammar beyond regex、或 reasoning model 的 free-form chain-of-thought，优化路径不同。多模态用 image hash 作为 radix key，若近重复图像或动态裁剪，复用率可能下降。

**API/black-box 维度**：API speculative execution 本质是启发式批处理，准确率高时省费显著，但错误匹配会导致语义错误或额外重试——论文未量化 misprediction rate 与容错成本。

### 实验可信度

**优点**：覆盖 agent、推理、few-shot、JSON、RAG、multi-turn、多模态、API 模型；包含 component ablation、overhead microbenchmark、生产 hit rate；baseline 在多数设置下计算相同结果（不启用改变输出的优化）。

**疑点**：
- [[vLLM]] baseline 为 **v0.2.5**（2023 末），远早于论文发表时的 vLLM prefix caching 能力；与今天 vLLM 对比会低估 baseline，论文结论在「对当时 SOTA 通用引擎」成立，但不自动等于「对 2025–2026 引擎仍领先 6.4×」。
- Guidance/LMQL 使用 llama.cpp / HF Transformers 后端，且缺少 batching、tensor parallel、部分功能，导致后五个 benchmark 被排除——主对比实质常是 **SGLang SRT vs vLLM**，DSL 相对 LMQL/Guidance 的编程收益与 runtime 收益混在一起。
- 吞吐实验用「足够大的 batch」测最大吞吐，延迟实验用单实例无 batching；生产 SLO 常同时约束 P99 latency 与 fairness，论文未报告 tail latency 或 starvation 量化。
- 生产数据来自 Chatbot Arena「每模型单 worker、低流量」配置，hit rate 高不一定代表高 QPS 多副本场景。

### 系统性缺陷

- **公平性与租户隔离**：cache-aware 调度可能饿死冷请求；论文未讨论 per-tenant cache 隔离、优先级反转或付费 tier，多租户 SaaS 中共享 radix tree 的隐私与侧信道风险也未涉及。
- **尾延迟与故障恢复**：未分析 tree 锁竞争、eviction 抖动、fork 并行下的调度长尾；RadixAttention 节点 ref count 与 batch 生命周期绑定，worker crash 后 cache 一致性论文未讨论。
- **可观测性与运维**：生产章节给 aggregate hit rate，但未定义 cache 命中率如何按 workload 切片、如何诊断 thrash、如何做 capacity planning。
- **正确性**：compressed FSM 在特定 regex 下可能输出语义错误等级；API speculative execution 的 silent mismatch 风险未被形式化。
- **编译器路径**：compiler mode 与 GPT-4 辅助 code movement 仍偏研究原型（15 模板中 12 成功，3 因语义误解失败），尚未成为默认可靠优化。

## 局限与 Future Work

- **局限 1（论文承认）**：cache-aware scheduling 可能导致 starvation，需与 fair scheduling 结合。
- **局限 2（论文承认）**：compiler 不支持 data-dependent control flow；compressed FSM 对 distorted probability 仅部分 workaround。
- **局限 3（实验边界）**：long-output multi-turn chat 收益有限；LMQL/Guidance 非公平后端使「编程系统」横向对比不完整。
- **局限 4（部署边界）**：生产证据来自单 worker Chatbot Arena；多副本、跨地域、PD 分离下的 radix cache 一致性未充分验证。

- **Future work 1**：将 RadixAttention 扩展到 DRAM/disk 多层存储（论文引用 FlexGen 方向），并测量 hit rate–latency–cost 的 Pareto 曲线。
- **Future work 2**：在在线调度中集成公平性约束（如 [[vLLM]] fairness / SLO-aware scheduling），量化吞吐收益与 P99 latency、starvation rate 的 trade-off。
- **Future work 3**：对 compressed FSM 做 token-level 概率校正或 grammar 超越 regex，测量 structured output 正确率与加速比。
- **Future work 4**：增强 SGLang compiler 的静态调度与 memory planning，使 prefix 重排（code movement）在语义保持上可验证，而非依赖 GPT-4 启发式。
- **Future work 5**：fuzzy semantic matching within RadixAttention（论文结论段提及），探索 embedding 近似前缀复用对准确率与加速的影响。

## 相关

- **相关概念**：[[RadixAttention]]、[[KV-Cache]]、[[Prefix-Caching]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Tensor-Parallelism]]、[[RAG]]、[[Speculative-Decoding]]
- **同类系统**：[[vLLM]]、Guidance、LMQL、DSPy、LangChain
- **基于 SGLang 的后续工作**：[[Libra-ICLR26|Libra]]（SGLang v0.4.10 MoE LB）、[[BatchLLM-MLSys26|BatchLLM]]（全局 prefix tree vs LRU）、[[LMCache-arXiv25|LMCache]]（跨层 KV movement）
- **对比**（按需）：[[vLLM-vs-SGLang]]
- **同会议**：[[NeurIPS-2024]]