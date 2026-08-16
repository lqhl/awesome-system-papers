---
type: concept
aliases: [RAG, Retrieval-Augmented Generation, retrieval augmented generation, retrieval-augmented generation, 检索增强生成]
last_updated: 2026-08-14
tags: [llm-inference, retrieval, serving, agent]
---

# RAG

> 检索增强生成（Retrieval-Augmented Generation，RAG）先从外部语料、向量库、图或工具中找证据，再把证据交给 LLM 生成答案。系统真正需要优化的是“查询理解—检索—排序—上下文组装—prefill—decode—引用与更新”的完整链条，而不是只把向量搜索或模型推理单独做快。

## 核心思想

一条典型 RAG 请求先把用户问题改写或向量化，再执行 lexical、dense、graph 或混合检索，经过过滤和 rerank 后选择 top-k 文档，最后把文档、指令和问题拼成 prompt。LLM 对这段 prompt 做 prefill，生成 [[KV-Cache]]，再 decode 答案。多跳 RAG 会重复这一过程；agent memory 还会把新观察写回索引，因此读、写、检索和生成形成一个有状态 workflow。

这个抽象有三条边界。第一，retriever 看到的是 embedding similarity、BM25 score 或图关系，generator 关心的是答案是否正确，两者目标并不相同。第二，检索到的文档可能重复，但排序、权限过滤和多轮组装会改变位置，使 [[Prefix-Caching|前缀缓存]]失效。第三，索引的容量、更新、I/O 和隐私成本不会因为接入 LLM 而消失。[[Terminus-MLSys26]]、[[ContextPilot-MLSys26]] 和 [[OdinANN-FAST26]] 分别从下游效用、上下文复用和在线更新暴露了这三类问题。

RAG 也不是唯一的外部记忆方式。[[Cartridges-ICLR26]] 把语料压进可训练 KV prefix，[[MSA-arXiv26]] 把 retrieval 变成模型后半层内部的稀疏注意力，[[DeepSeek-V4-arXiv26]] 与 [[NSA-ACL25]] 则用更长、更稀疏的 context 减少外部检索需求。这些路线可能缩短 pipeline，却要改模型、训练或失去自然的 citation/provenance；传统 RAG 的模块化、可更新与可核查仍有独立价值。

## 为什么重要

RAG 把多个本来独立的系统瓶颈串成串行关键路径。[[TeleRAG-MLSys26]] 在六条 pipeline 中观察到纯 CPU IVF 检索可占端到端时间的 41%–60%；[[HIPPOCAMPUS-MLSys26]] 在 agent memory 中报告 search 占 47%–85%。但 [[LEANN-MLSys26]] 的端侧问答恰好相反：生成常超过 20 s，检索只有毫秒到百毫秒，因此可以用一些重算时间换 50 倍索引压缩。两组结果并不矛盾，它们说明“RAG 的瓶颈”必须按模型、索引、设备、top-k 和并发重新测量。

RAG 还是长上下文 serving 的代表 workload。检索文档越多，prefill 越贵，[[KV-Cache]] 越大；请求之间虽然会反复命中同一批文档，却常因顺序改变而无法命中精确 prefix。[[ContextPilot-MLSys26]] 在 MultihopRAG 和 NarrativeQA 上测到精确 prefix hit 只有 4.6% 和 5.5%；对齐、去重与调度后，DeepSeek-R1 的 hit ratio 可从约 5%–6% 提高到 38%–60%。[[SpanQueries-MLSys26]] 则指出，真正缺失的接口是“哪些片段可交换”，而不是再做一个 RAG 专用 cache。

最后，检索质量和生成质量之间没有稳定的一一映射。[[Terminus-MLSys26]] 发现 Natural Questions 在 top-k 增到 20 后答案 EM 接近饱和，因而按 rank utility 早停可把吞吐提高 3.2 倍；但多跳推理、需要长尾证据或强 reranker 的任务未必满足这个分布。[[METIS-SOSP25]]、[[ApproxMLIR-MLSys26]] 把配置和近似预算做成 per-query 决策，正是因为固定 top-k、固定模型和固定索引策略很难覆盖所有请求。

## 关键观察 / 隐含假设

- **观察 1：检索与生成谁主导延迟取决于运行区间。** TeleRAG 和 HIPPOCAMPUS 看到 retrieval 主导；LEANN 看到 generation 主导。任何系统都应分别报告 retrieval、rerank、context assembly、prefill、decode 和排队，而不能只给端到端倍率。
- **观察 2：可复用文档很多，但位置不稳定。** [[ContextPilot-MLSys26]] 观察到 top 20% 文档贡献 49.6%–79.2% 的查询，却因 ranking 变化导致 prefix miss；[[SpanQueries-MLSys26]] 用可交换 span 重排，在受控 RAG microbenchmark 上把 TTFT 降 10–20 倍。前提是应用能正确声明片段顺序不影响语义。
- **观察 3：复用非 prefix KV 不是天然正确。** [[CacheBlend-EuroSys25]] 发现跨 chunk attention 只集中在约 10%–15% token，因而选择性重算可把 TTFT 降 2.2–3.3 倍；但完全近似复用在其他论文的多模型测试中可让准确率下降 9%–11%。高风险任务需要逐请求质量 guard，而不是只看平均 F1。
- **观察 4：阶段重叠可以缩短 TTFT，但会制造新的内存竞争。** [[TeleRAG-MLSys26]] 利用 query rewrite 前后 IVF cluster 覆盖率常大于 61%，在改写期间预取；[[Stream2LLM-MLSys26]] 边检索边 prefill，把 TTFT 改善 3.9–11 倍，但朴素 streaming 在多租户 memory pressure 下会让 P99 恶化 10 倍。
- **观察 5：检索目标应面向下游效用，而不只是 Recall@k。** [[Terminus-MLSys26]] 用 rank-weighted utility 和 Ranked Recall 对齐 RAG EM；[[MSA-arXiv26]] 直接在模型 latent space 学 routing，试图消除 retriever 与 generator 的目标错位。前者可插入现有系统，后者需要重新训练并失去部分模块化。
- **观察 6：索引 footprint、I/O 和更新是独立的生产约束。** [[LEANN-MLSys26]] 用查询时重算把 188 GB 索引压到 4 GB；[[Helmsman-OSDI26]] 用聚类扫描和多块 NVMe 避免大 top-k 的串行图 I/O；[[OdinANN-FAST26]] 用 direct insert 与 update combining 避免 merge 干扰前台搜索。三者分别优化冷端部署、高吞吐生产检索和新鲜度，不能只按 QPS 排名。
- **观察 7：长期 agent memory 需要结构而不只是 top-k dense 相似度。** [[Tag2Graph-MLSys26]] 用本体图补足隐式偏好和跨 session 时间关系，在匹配约 185 ms P95 的条件下把 Recall@10 从 0.58 提高到 0.70；[[HIPPOCAMPUS-MLSys26]] 用 token-ID 与二进制语义签名统一精确/近似检索。结构增加了召回能力，也带来 ontology 演化、validator 和写入成本。
- **隐含假设 1：检索到的文本可信且允许送进模型。** 多租户权限、删除请求、prompt injection、cache poisoning 和跨 session 泄漏会破坏这个假设。[[Compass-OSDI25]] 只解决了加密向量搜索的一部分；context cache 和 generator 仍需完整的访问控制与 provenance。
- **隐含假设 2：答案质量可以用有限 benchmark 的 EM/F1 或 LLM judge 代表。** 多跳、引用正确性、法律/医疗证据、开放 web 新鲜度和 agent 行为并未被现有系统统一覆盖。[[Cartridges-ICLR26]] 与 MSA 的平均 QA 分数不能替代 citation correctness。

## 设计空间与取舍

- **两阶段 retrieve-then-read 与模型内 retrieval**：传统 RAG 可单独更新语料、替换索引并返回证据；MSA 类模型内 routing 更贴近 generation objective，但要求训练和专用 runtime。Cartridge 把重复语料离线压成 KV prefix，吞吐高，却难定位答案来自哪一段原文。
- **lexical、dense、图与混合检索**：BM25 成本低且可解释，dense 检索覆盖语义相似，图检索适合关系与时间链，混合系统质量更稳但需要分数校准和更多运维。[[Tag2Graph-MLSys26]] 的收益集中在隐式偏好，不能外推为所有 factual query 都应建图。
- **索引放置**：全量 DRAM/GPU 延迟低、成本高；SSD 图索引容量大但受随机 IOPS 限制；聚类扫描能顺序吃带宽但会多读；LEANN 的重算索引省存储却消耗 encoder；[[PIMANN-ATC25]] 把 ANNS 放到 processing-in-memory，依赖特定 UPMEM 控制接口。
- **顺序执行与流水重叠**：等待完整检索结果最简单；TeleRAG 在 rewrite 阶段 lookahead prefetch，Stream2LLM 让 context 分块到达即 prefill，[[HedraRAG-SOSP25]] 把多轮/分支 workflow 统一成 RAGraph 后动态 split、reorder、rewire。重叠越激进，越需要 memory admission、cancel 和 backpressure。
- **精确 prefix、输入重排与近似 KV**：精确 prefix 质量稳定但命中低；ContextPilot 调整文档顺序并加 annotation；SpanQueries 让应用声明交换律；CacheBlend 重算少量受 cross-attention 影响的 token。三种路线分别把责任放在数据变换、应用语义和模型近似上。
- **固定 top-k、per-query 配置与动态早停**：固定配置易运维；METIS 用 profiler LLM 选 chunk 与 synthesis；ApproxMLIR 在 QoS-loss budget 下联合调 corpus、scoring 和模型；Terminus 根据搜索进度早停。动态策略收益高，但错误估计可能直接丢证据。
- **静态索引与在线更新**：重建可得到高质量图，但十亿级可能需要数天；OdinANN 接受 per-record 近似隔离和 2 倍磁盘空间，换取前台低波动。需要 read-your-writes 或全图快照的业务不能直接采用这条取舍。
- **明文与保密检索**：Compass 在 ORAM 上做加密 HNSW，跨区延迟仍为 0.57–1.28 s。保密会显著改变索引访问和 latency budget；只加密 embedding 也不等于 query、访问模式、上下文和答案都安全。

## 证据边界与相反结果

- **“检索是瓶颈”与“生成是瓶颈”都只在各自区间成立。** TeleRAG 适合大 IVF 索引与显存紧张；LEANN 适合端侧、长生成和低到中 QPS。高并发纯搜索不应照搬 LEANN 的“多花一点检索时间无所谓”。
- **重排上下文可能改变答案。** SpanQueries 需要应用保证 commute；ContextPilot 用 annotation 弥补重排；CacheBlend 是近似计算。法律、代码、时间序列和逐步证明中的顺序常有语义，不能默认可交换。
- **高 rank 文档不总能代表完整证据。** Terminus 的早停主要在 Natural Questions 与 Wikipedia-20M 上验证；多跳、反证、长文档 rerank 和需要多个低 rank 片段的任务可能需要更完整遍历。
- **向量检索系统论文常没有端到端 RAG。** [[FlowANN-OSDI26]]、[[PathWeaver-ATC25]] 和 [[PipeANN-OSDI25]] 主要证明 ANNS 内核性能；只有在相同 embedding、top-k、rerank、prompt 和 generator 下再测答案质量，才能把 QPS 转成 RAG 收益。
- **模型内记忆减少模块，却增加训练绑定。** MSA 在九个 QA benchmark 平均分领先多组 RAG，但只在 4/9 数据集绝对第一，并缺 citation correctness；DeepSeek-V4/NSA 的长上下文能力也不会自动解决语料更新、权限和证据追踪。
- **生产背景不等于所有数字都来自生产请求。** Helmsman 有约 40 台线上部署，SGLang 报告生产 cache hit，许多其余结果仍来自固定 benchmark、合成到达、微基准或离线 trace 回放。

## 引用本概念的论文

### Pipeline、上下文与推理协同

- [[CacheBlend-EuroSys25]] — 对多 chunk RAG 复用非 prefix KV，并选择性重算跨 chunk 影响大的 token；加速明显但不是逐请求语义等价。
- [[CacheGen-SIGCOMM24]] — 把远端 KV cache 压成可按带宽自适应传输的 bitstream，服务 RAG、长对话和企业文档复用。
- [[ContextPilot-MLSys26]] — 用 context index、对齐、去重和 annotation 提高跨 session RAG 的精确 KV 命中与 prefill 吞吐。
- [[HedraRAG-SOSP25]] — 用 RAGraph 表示多轮、分支和迭代 workflow，再联合调度 CPU 检索与 GPU 生成；简单两阶段 workload 的收益接近下界。
- [[LAPS-MLSys26]] — 按长度隔离 prefill 请求；超长单轮 RAG 是它明确指出会改变 long/short 比例的边界 workload。
- [[LLMSteer-NeurIPSW24]] — 对会被反复查询的固定 context 离线重读并调 attention；开放域 RAG 每次 chunk 不同会削弱摊销。
- [[METIS-SOSP25]] — per-query 估计 RAG 配置并联合 GPU batching，在四个 QA 数据集把生成延迟降低 1.64–2.54 倍；未覆盖 agentic multi-hop。
- [[SGLang-NeurIPS24]] — 以 RadixAttention 复用 RAG/agent 的公共 prefix；顺序变化和个性化 context 仍会造成 cache thrash。
- [[SpanQueries-MLSys26]] — 用声明式 span 和交换律表达 RAG fragment 复用；10–20 倍 TTFT 来自受控 microbenchmark，依赖正确语义标注。
- [[Stream2LLM-MLSys26]] — 让检索结果分块到达并与 prefill 重叠，同时用两阶段调度和 cost model 控制多租户内存竞争。
- [[TeleRAG-MLSys26]] — 在 query rewrite 时提前把高覆盖率 IVF cluster 搬到 GPU；61 GB 索引加 8B 模型可在 24 GB RTX 4090 上运行。

### 索引、搜索、I/O 与更新

- [[Compass-OSDI25]] — 在 Ring ORAM 上运行加密 HNSW，为机密 RAG 提供向量检索；它保护的主要是搜索路径，完整 pipeline 隐私仍未闭合。
- [[FlowANN-OSDI26]] — 用 CPU/GPU 分边和延迟同步隐藏图遍历依赖；RAG 只作为真实 query trace 之一，端到端生成质量仍需单独验证。
- [[Helmsman-OSDI26]] — 用聚类索引、SPDK 和多 NVMe 承接大 top-k 搜索；RedRAG 1024 维 workload 换 Gen5 后快 87%，有约 40 台生产部署背景。
- [[LEANN-MLSys26]] — 不保存 dense embedding，查询时重算并剪枝 HNSW；76 GB 语料索引从 188 GB 降至 4 GB，适合端侧低存储场景。
- [[OdinANN-FAST26]] — 用 direct insert、无 GC 的 update combining 和 per-record 快照维持 on-disk ANNS 新鲜度；强一致 read-your-writes 是边界。
- [[Oxbow-OSDI26]] — 用 RAG 作为文件系统应用评测；400-client 端到端平均延迟约 40 ms 未变，但单 probe 从 Ext4 的 122 µs 降到 61 µs，说明下游可能遮住存储收益。
- [[PIMANN-ATC25]] — 把 IVFPQ 放到 UPMEM 并细粒度仲裁共享总线；证明的是 ANNS substrate，不是完整 RAG pipeline。
- [[PathWeaver-ATC25]] — 优化多 GPU graph ANNS 的跨 shard path；只到 4 GPU/50M 向量，缺少真实 RAG query 分布和跨节点结果。
- [[PipeANN-OSDI25]] — 用 compute/I/O pipeline 加速磁盘 ANNS；没有测 embedding 与生成后的端到端 latency budget。
- [[Quake-OSDI25]] — 对动态倾斜和 embedding 版本变化做在线 split/merge 与自适应 nprobe，适合持续演化的 RAG 索引。
- [[Terminus-MLSys26]] — 以 rank-weighted utility 早停磁盘 graph search；相对无早停吞吐 3.2 倍且 NQ EM 变化很小，外推多跳需谨慎。

### 记忆替代、应用使用与质量治理

- [[ApproxMLIR-MLSys26]] — 把 corpus subset、term scoring、context 和模型选择放进统一近似预算；3%–9% QoS-loss budget 下 LLM+RAG 加速 2.64–3.04 倍，但硬件信息缺失。
- [[Auto-Research-arXiv25]] — 把 RAG 列为自动科研的知识获取组件；论文是生命周期愿景，未给 RAG 机制或端到端科研闭环证据。
- [[Cartridges-ICLR26]] — 把反复查询的语料蒸馏成可加载 KV prefix，平均少用 38.6 倍内存；语料频繁更新和 citation/provenance 是明显弱点。
- [[DeepSeek-V4-arXiv26]] — 用稀疏长上下文和异构 KV 管理降低对外部检索的部分依赖；RAG 只是能力谱系对照，不是该论文的系统组件。
- [[HIPPOCAMPUS-MLSys26]] — 在压缩域联合 token-ID 精确流和二进制语义签名，降低 agent memory 的频繁检索成本。
- [[MSA-arXiv26]] — 把 document routing、KV compression 与生成放进同一 backbone，使 retrieval 可训练；代价是专用训练/runtime 和较弱的证据追踪。
- [[NSA-ACL25]] — 用硬件友好的原生稀疏注意力扩展长 context；对外部化检索很强的 RAG，端到端瓶颈可能不再是 attention。
- [[NeuroSymbolicProof-OSDI26]] — 用 RAG 给 Isabelle proof search 提供相关示例；200-theorem 消融从 tree-only 12.5% 提到 tree+RAG 33.0%，但整篇成功率分母存在不一致。
- [[PROMPTS-MLSys26]] — 用 RAG 检索历史 TPU sharding 案例和专家文档，为 agent 生成 top-3 配置；编译器仍是防幻觉 safety net。
- [[Tag2Graph-MLSys26]] — 用本体图、dense 检索和 router 服务长期会话记忆，改善词面不重叠的隐式偏好召回。

## 已知局限 / 开放问题

- **需要统一的端到端评测。** 至少同时报告检索 P50/P99、TTFT、TPOT、吞吐、索引 footprint、更新成本、答案正确性、citation faithfulness 和每请求成本；只报 ANNS recall 或 LLM EM 都不够。
- **多跳与 agent workflow 仍缺稳定优化原则。** early stop、context reorder 和 prefix reuse 都可能漏掉后续步骤才需要的长尾证据。应在真实分支、工具等待、反思和回写 trace 上测试。
- **权限、删除与缓存一致性未闭合。** 文档撤权或删除后，向量索引、rerank cache、KV cache、GPU prefetch 和 agent memory 必须一起失效；现有论文很少给出可验证协议。
- **prompt injection 与 cache poisoning 仍是系统问题。** 外部文档可操纵 generator，也可能污染跨用户复用的 context/KV。需要 provenance 标签、tenant isolation、内容扫描和快速 rollback。
- **索引与模型一起演化时成本不清楚。** embedding 模型更新会使旧向量失效，generator 更新会改变 rank utility，ontology 和 learned router 也会 drift。应报告在线双版本、重建时间和服务降级策略。
- **模型内记忆与 RAG 的组合仍值得验证。** Cartridge/MSA 可提供全局语境，RAG 可提供新鲜且可引用的证据；未来工作应在相同训练、存储和 serving 预算下比较混合方案，而不是只比较单一质量分数。
