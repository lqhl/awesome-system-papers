---
type: paper
name: SpanQueries
full_title: "Using Span Queries to Optimize for Cache and Attention Locality"
authors: [Paul Castro, Nick Mitchell, Nathan Ordonez, Thomas Parnell, Mudhakar Srivatsa, Antoni Viros i Martin]
venue: MLSys
year: 2026
tags: [kv-cache, rag, llm-inference, vllm, prefix-caching, agent]
source_pdf: "[[3416a75f4cea9109507cacd8e2f2aefc.pdf]]"
source_md: "[[3416a75f4cea9109507cacd8e2f2aefc]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Using Span Queries to Optimize for Cache and Attention Locality (MLSys 2026)

> **一句话总结**：观察到 chat/RAG/nested generation 的 [[KV-Cache]] 复用差异本质是输入块是否可交换（commutativity），而非 workload 类型本身；提出 span query 声明式 IR 用 `+`/`✶` 显式标注交换律，在 [[vLLM]] 上仅改 492 行即可把非 chat 场景 TTFT 降 **10–20×**，并借 map-reduce 式 attention locality 优化让 **2B** 模型准确率超过 stock **8B**。

## 问题与动机

[[vLLM]] 等推理服务器围绕 chat completion 的 **prefix-based** [[Prefix-Caching]] 优化：历史线性追加，prefix 稳定，cache hit rate 随会话趋近 100%。但 RAG、judge-generator、agentic 等新兴 workload 的复用模式不同——块仍跨请求复用，**顺序却随请求变化**（如 RAG 第二次检索 `[F2, F3]` 而非 `[F1, F2]`），prefix 一错位即 miss，hit rate 趋向 0%。

既有方案各有边界：CacheBlend 因不知 order 是否重要而保守优化 order-matters 场景；Block Attention 硬编码 RAG 单一场景。作者 claim 的核心不是再做一个 RAG 特化补丁，而是：**chat、RAG、inference-time scaling、agentic 均为同一表达式树的特例**，关键区分是用户能否声明「A,B 与 B,A 等价」。边界是：需要客户端/workflow 层能表达 span query 语义；不解决 decode 阶段吞吐或跨节点 KV 共享。

## 关键观察 / 隐含假设

- **观察 1**：非 chat workload 的 KV 复用失败，根因不是「没有复用」，而是 **复用块在序列中的位置变化** 导致 vLLM 的 prefix-only 扫描失效——RAG 第二次请求仅 33% hit（6 token 中 2 个），nested generation 的 judge 请求仅 29% hit 且随 assistant 输出增长趋向 0%。
  - **依赖假设**：[[PagedAttention]] block 粒度缓存 + prefix-only lookup 是生产服务器的常态行为；fragment/candidate 内容跨请求稳定（embedding 检索结果或相同 system prompt 可复用）。
  - **可能失效场景**：每次检索结果完全不同、inner generate temperature 极高导致输出永不重复、或 block size 与 token 边界严重不对齐时，即使允许重排也难获 hit。

- **观察 2**：order 是否可交换是 **应用语义** 而非系统可推断属性——RAG fragment 顺序、judge 审阅 candidate 顺序，有的 commute 有的不 commute；CacheBlend 隐式假设 order matters 是合理保守策略，但会错过 commute 场景的巨大收益。
  - **依赖假设**：用户/workflow 作者能正确标注 `+`（commutative join）与 `✶`（non-commutative join）；错误标注会导致语义错误或「优化后准确率下降」。
  - **证据强度**：**中**——论文在 RAG 默认 desugar R→`+`、chat 默认 `✶`，但 nested generation 是否 commute 明确留给用户。

- **观察 3**：vLLM 存在 **dual output paradox**——发给 client 的 output 与写入 KV cache 的 output 可能不一致（partial block 不缓存），chat 客户端通过重发 history 可规避，nested generation 则无法靠 prefix 复用 inner generate 的 assistant 输出。
  - **依赖假设**：通过 high-level optimizer 的 **plus distribution**（把 `+` 分布进 `G` 内部）可结构性对齐 query 结构与 server 行为，使未来复用与 cache 内容一致。
  - **可能失效场景**：inner generate 输出长度不对齐 block 边界时，仍需 **crop** 尾部 token 才能避免 paradox，牺牲部分生成内容。

- **假设 1**：用括号 special token 序列化 expression tree、在 scheduler 层暂停 block hash 累积，即可在 **不改 vLLM 核心 attention 逻辑** 的前提下实现 span 级 cache 命中与 ReRoPE repositioning。
  - **证据强度**：**强**——492 行 Python 改动 + microbenchmark 验证；但 special token 语义依赖对现有 token 的 **overload**，可能影响模型精度（论文承认并选择接受）。

## 核心方法

Span query 是 over operators `C, R, F, +, ✶, S, A, U, G` 的声明式表达式树 IR，回应观察 2 的「统一抽象 + 显式交换律」。

**High-level optimizer（回应观察 2、3）**：固定点迭代执行 tree rewrite——`C` desugar 为 `G`+`✶`；`R` desugar 为 `G1`（max_tokens=1 预填充 fragment）+`+`；`+` 链简化；**plus distribution** 把 commutative join 推入 generate 内部，解决 dual output paradox。优化后 RAG 成为 nested generation 特例（Figure 9）。

**Query tokenization**：用 special token（`(`、`)`、pad）把树 parenthesize 为线性 token 序列；`)` 带 back-pointer 指向子树起点，避免 vLLM 维护解析栈。回应假设 1 的「最小侵入」。

**Low-level optimizer**：block alignment（pad 使 special token 落 block 边界）；nested generation 场景对未填满 block 的 inner output **crop**，在 cache miss 与 accuracy 间取舍。

**vLLM scheduler 改动**：block 首 token 为 `(` 时 **暂停** hash 链累积；为 `)` 时恢复——使同内容 span 在不同位置可独立 hash 命中。GPU runner 层实现 **CIDRA**（Concurrent In-place Duplicating ReROPE Algorithm）：构建 repositioning 依赖图，out-degree>1 时 duplicate block，强连通分量分析后 batch 执行 ReRoPE；峰值吞吐约 **500 tokens/ms**。

**Attention locality 扩展（无需改 server）**：对 commute 的 judge/generator，把 8-way 单层 judge rewrite 为 3 层 2-way tree reduction（map-reduce），缩短单次 attention 的「haystack」长度，缓解 lost-in-the-middle。

## 设计取舍

- **声明式 IR vs 客户端 ad-hoc 拼接**：用 span query 集中表达 connectivity 与 ordering，换客户端需学习新抽象；语言 surface syntax 明确 defer 到 future work。
- **Special token overload vs 新 token fine-tune**：选 reuse 现有 token 降低 vLLM 改动，牺牲潜在精度风险；新 token 需 fine-tune 成本更高。
- **Crop inner output vs 深改 vLLM partial-block 缓存**：为保持 492 行改动预算，接受 crop 最后一 token 的 accuracy/cache 权衡。
- **Commutative 优化 vs 语义安全**：错误 `+` 标注会导致无效优化或错误结果；系统不自动推断 commute。
- **边界条件**：RAG fragment 可交换、inner generate 高温多候选、bulk 请求 working set 小于 KV 容量时收益最大；inner temperature=0 且 fan-out=1 时相对 stock [[vLLM]] 几乎无 TTFT 收益。

## 实验与结果

平台基于修改版 [[vLLM]]；RAG microbenchmark 用 2857 token/文档（vLLM Python 源文件均值长度）、1–32 文档；nested generation 用 judge/generator 模式。

- **RAG TTFT**：span query + cache hit 相对 stock vLLM 达 **10–20×** 量级降低（Figure 13b）；cache miss 时因 span 内 attention sparsity 仍显著快于 baseline（论文称约 **3×** prefill 节省）。
- **Nested generation TTFT**：inner fan-out=24、非零 temperature 时 **12–13×** 更快；fan-out=1 时 **7–32%** 提升；temperature=0 时收益近 0（prefix 缓存已足够）。
- **CIDRA**：repositioning 峰值 **~500 tokens/ms**；overhead 随 fan-out 非单调（与 batch 形状相关）。
- **Bulk execution**：对 2Wiki / NaturalQuestions 做 greedy temporal clustering，小 fragment（~100 token）场景 speedup 与单 query microbenchmark 一致（Table 4）。
- **Attention locality**：needle-in-haystack microbenchmark（granite3.3 2B/8B，1000 runs）；attention-optimized 2B 在 hay 变长时优于 unoptimized 8B（Figure 17）。
- **工程成本**：[[vLLM]] 共 **492 行** Python 新增/修改（总代码库 ~260k LoC）。

## Critical Analysis

### 论证链条

观察（prefix miss 根因是位置变化 + commute 是语义属性）→ span query IR + `+`/`✶` → desugar/distribute → special-token 序列化 + hash 暂停 + CIDRA：主链条闭合。最强证据在 **可控 microbenchmark**（固定文档长、扫 document 数与 fan-out）；RAG 与 nested generation 两条线互相印证「commute 时重排 + span hash」有效。薄弱环节：生产 trace（真实 agent 会话、多 tenant 交错）缺失；把 10–20× 外推到所有 agentic workload 需假设 fragment 稳定复用且用户正确标注 commute。

Attention locality 是 **涌现属性**——原目标为 KV cache，tree reduction 缓解 lost-in-the-middle 逻辑独立且不需 server 改动，但实验仅限单一 needle-in-haystack 任务与 granite3.3，未与 Chain-of-Agents、长文档 QA 等 benchmark 对照。

### 假设压力测试

- **语义标注**：错误 `+` 会导致错误优化；论文无自动验证或 runtime check。
- **模型/token**：overload special token 可能影响非 span 请求精度；论文未系统报告 downstream task accuracy 下降幅度。
- **Partial block**：crop 策略在长 candidate 场景可能裁掉语义关键尾部；更深 vLLM 改动或 fine-tune 才可消除。
- **Concurrency**：CIDRA 处理多请求重叠 repositioning，但 p99 TTFT 在 nested generation 高 fan-out 时不稳定（论文承认需进一步工作）。
- **与更强 baseline**：CacheBlend、Block Attention、[[SGLang]] structured program 未同台端到端对比；10–20× 主要相对 **stock vLLM**。

### 实验可信度

- **Benchmark**：RAG/nested microbenchmark 刻意放大 commute 收益；2Wiki/NQ 片段很短，处于 Figure 13b 最左端，与大规模 corpus 场景有 gap。
- **Baseline**：stock vLLM 公平作为「无 span 语义」对照；缺 CacheBlend/Block Attention 同等实现。
- **Ablation**：有 cache hit/miss、fan-out、temperature 分解；缺「无 CIDRA」「无 plus distribution」「无 block alignment」逐项消融。
- **Metric**：主报 TTFT；**端到端 latency、吞吐、准确率损失、tail stability** 覆盖不均——p99 问题已自述。

### 系统性缺陷

- **客户端生态**：需 workflow 层产出 span query；与 OpenAI chat API 直连的客户端无法受益。
- **可观测性/运维**：论文未讨论 span query 失败诊断、错误标注检测、与现有监控集成。
- **多节点 KV**：改动集中在单节点 scheduler/GPU runner；未讨论 disaggregated prefill 或跨 replica cache 一致性。
- **资源隔离**：bulk clustering 启发式改变请求调度顺序，可能影响 fairness——论文未讨论。
- **兼容性**：绑定 vLLM block hash 与 RoPE 实现；其他 server（TensorRT-LLM、[[SGLang]]）需移植整套栈。

## 局限与 Future Work

- **局限 1**：inner generate 未填满 block 时需 crop，或接受 cache miss；dual output paradox 未从根上消除。
- **局限 2**：span query 语言 surface、自动 commute 推断、树结构直接送入 vLLM（免 special token）均 defer；special token 精度影响未量化。
- **局限 3**：nested generation 高 fan-out 时 p99 TTFT 不稳定；bulk scheduling 仅用 greedy heuristic。
- **Future work 1**：分析 nested generation 结构，绕开 KV cache，用 gather/scatter 式 scheduler 分离 inner/outer generate（作者 conclusion 明确提出，类似 SQL 执行计划）。
- **Future work 2**：在真实 agent trace 上测量 commute 标注错误率与 TTFT/accuracy 权衡，建立自动验证或 lint。
- **Future work 3**：与 CacheBlend、Block Attention、[[SGLang]] 在同 workload 上做控制变量对比，剥离 IR 抽象 vs 底层 repositioning 各自的贡献。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Prefix-Caching]]、[[RAG]]、[[Attention]]、[[Sparse-Attention]]、[[Chunked-Prefill]]
- **同类系统**：[[vLLM]]、[[SGLang]]、CacheBlend、Block Attention
- **同会议**：[[MLSys-2026]]
