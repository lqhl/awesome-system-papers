---
title: "HIPPOCAMPUS: An Efficient and Scalable Memory Module for Agentic AI"
authors: [Yi Li, Lianjie Cao, Faraz Ahmed, Puneet Sharma, Bingzhe Li]
year: 2026
venue: MLSys
tags: [agentic-memory, llm-agent, succinct-data-structure, wavelet-matrix, semantic-hashing]
---

# HIPPOCAMPUS: An Efficient and Scalable Memory Module for Agentic AI

**作者**：Yi Li, Lianjie Cao, Faraz Ahmed, Puneet Sharma, Bingzhe Li
**单位**：The University of Texas at Dallas; Hewlett Packard Labs
**会议**：MLSys 2026
**链接**：https://proceedings.mlsys.org/paper_files/paper/2026
**源文件**：[[d645920e395fedad7bbbed0eca3fe2e0.pdf]]

---

## 1. 背景

Agentic AI 是从静态 LLM prompting 走向自主感知—规划—行动—学习闭环的一种新型系统形态。AutoGPT、BabyAGI、ReAct 等系统证明:把 LLM 与目标驱动的循环耦合,可以解锁单轮 prompt 无法实现的复杂任务执行能力。在这一范式下,**memory** 是除"感知"和"规划"之外的核心组件 —— 它是 agent 在跨轮次、跨任务、跨长时间窗口中保持上下文连贯性的持久基底。

由于 LLM 的上下文窗口长度受限(且 "Lost-in-Middle" 效应表明长上下文中段信息会被忽略),把所有历史塞进 prompt 既不经济也不可靠。一种更工程化的解法是 **contextual memory**:把历史外部化到一个独立存储中,通过显式 retrieval 把"当前最相关"的片段注入 prompt。LangChain、CrewAI 等主流 framework 都内置了这类 memory 模块。

近期 contextual memory 的主流技术路线包括:

- **RAG-based**:把对话/事件 chunk 化、做 embedding,存入 dense vector DB,query 时做 ANN search
- **KG-based**:把内容抽成 entity-relation triple,存入 Neo4j 等图数据库,query 时多跳遍历
- **Hybrid**(如 A-Mem、MemoryOS、MemOS):结合两者,辅以 LLM 生成的 summary 或 metadata

---

## 2. 要解决的问题

作者通过对 ReadAgent、MemoryBank、MemGPT、A-Mem、MemoryOS、MemOS 六种 SOTA agent memory 系统的实测(LoCoMo benchmark),指出当前方案在三个核心维度上**无法同时优化**:

1. **检索准确率**(F1):MemGPT、MemoryOS、MemOS 等高质量系统得分高,但代价巨大
2. **每查询 token 消耗**:embedding-heavy 系统每个 query 要拉入 8K–17K token 的中间表示
3. **端到端延迟**:MemGPT 平均 ~33s 才返回一次结果,完全不能匹配 agent 的高频 observe-plan-act-learn loop

延迟分解显示,**search 阶段就占掉端到端时间的 47%–85%** —— 检索基底本身才是性能瓶颈,而非 LLM inference。同时,memory 写入侧(chunking、embedding、summary、graph index 维护)也带来不可忽视的额外开销。

具体痛点可归纳为:

- Dense vector ANN 在长 horizon 部署下随 memory 增长而退化,且 embedding 计算本身是 GPU 重负载
- KG 多跳遍历延迟随 graph 复杂度组合爆炸
- Hybrid 方案叠加了两者的开销,反而更慢
- 写入路径依赖 LLM(summary、note 生成),进一步挤占 token 预算

理想的 agent memory 系统应该是:**同时高准确率、低 token 占用、低延迟,并能随历史长度线性扩展。**

---

## 3. 洞察与设计

**关键洞察**:LLM 原生的输入就是离散 token-id 序列,没必要把它们再投影到稠密 float embedding 空间去算近似最近邻。如果用一个**对离散符号序列原生友好的 succinct data structure**(Wavelet Matrix)直接在压缩域上做 rank/select 查询,再结合 random indexing 把语义检索退化成**位级 Hamming-ball 搜索**,就能把检索从 GPU-heavy 的浮点运算彻底转成 CPU 上的 bitwise 操作 —— 单条对比从矩阵内积变成一次 XOR + POPCOUNT 指令。

基于此,HIPPOCAMPUS 采用 **dual-representation** 策略:

- **Content DWM**(Dynamic Wavelet Matrix):无损保存 token-id 序列,支持任意位置的精确 `access(i)` 重建原始内容
- **Signature DWM**:保存每个 token 的 d 比特二进制语义签名(via random indexing),支持快速近似 Hamming 搜索

两者通过 `metadata.{α, β}`(每个 memory entry 对应的起止 token 索引)co-index。

**Memory 构建流程**(Figure 5):

1. 原始对话经 content serialization 转成 token 序列
2. 同步抽取 metadata(speaker、timestamp、α、β)
3. 每个 token-id 转成二进制后写入 Content DWM
4. 同时通过 random indexing(每个 vocabulary token 预先分配 sparse {-1, 0, +1}^D 基向量,在 sliding window 内累加得到上下文 embedding,再取 top-d 维做 sign 阈值化)生成 d-bit signature,写入 Signature DWM

**Memory 查询流程**(Figure 6):

1. 用一个轻量 LLM prompt 从 query 中抽取若干 keyword
2. 把 keyword 通过相同 random indexing 流程映射成 signature
3. 在 Signature DWM 上做 Hamming-ball 搜索,得到候选 metadata block
4. 用 metadata 中的 (α, β) 在 Content DWM 上用 `access(i)` 还原原始 token 序列
5. detokenize 后作为 retrieval 结果返回

这种"先用紧凑签名快速过滤、再做精确无损还原"的两段式设计,把 semantic search 与 content fidelity 完全解耦,既避免了 embedding 计算开销,也没有 KG 多跳遍历的组合爆炸。

---

## 4. 实现细节

**Dynamic Wavelet Matrix (DWM)**:对 σ-字符表的 n 个符号,DWM 由 ⌈log₂σ⌉ 个 bit-vector 组成,每个 B^k 存储所有符号在第 k 位的取值。论文的核心技术贡献是把传统 **静态** wavelet matrix 改造成 **append-only** 的动态版本:

- **Append**(Algorithm 隐含在 Section 3.2.1):从 MSB 到 LSB 逐层下沉,在每一层调用 `rank_0` 或 `rank_1` 找到下一层的插入位置。单次 append 复杂度 O(log σ + log n)
- **Rank**(Algorithm 1):给定 symbol c 和位置 i,从 MSB 起维护区间 `[p_L, p_R)`,根据 c 当前位是 0 还是 1,把区间映射到下一层的 zero/one 子区间(用 `rank_0/rank_1` + 该层 0 总数 Z_k 做偏移),最后区间长度即为 c 在前缀 [0, i) 中的出现次数。复杂度 O(l)
- **Select**(Algorithm 2):先用 rank 算出全局 occurrence,然后从最下层往上"提升",每层用 `select_0/select_1` 找到对应位的全局位置。复杂度 O(l)
- **Access**(Algorithm 3):给定全局位置 i,从 MSB 起逐层读取该位置的 bit,根据 bit 值更新下一层位置,最终拼出符号。复杂度 O(l)

**Hamming-Ball Search 在 Signature DWM 上的执行**:对一组 query signature {c_1, ..., c_m},先选最稀有的 c_min(rank 值最小),然后:

1. `select(c_min, j)` 枚举每次出现的全局位置 i
2. 用 metadata 索引找到包含 i 的 entry [α, β]
3. 对其余 c_k 用 `rank(c_k, β) - rank(c_k, α) > 0` 验证是否在同一 entry 中出现
4. 通过校验的 entry 进入候选集

**Random Indexing 细节**:

- 每个 vocabulary token v 预分配 D 维(默认 1024)sparse {-1, 0, +1} 基向量,只有 t 个非零位(一半 +1,一半 -1)
- 流式扫过对话,在每个 token 周围维护 window W(i),累加 `e_i = Σ_{j∈W(i)} r_{S[j]}`
- 取 |e_i| 中 top-d(默认实验中 d ≪ D)做 sign 阈值化得到 d-bit signature
- Hamming 距离 = `XOR + POPCOUNT`,直接调用 CPU 原生指令

**实验环境**:HPE DL380a Gen11(2× Intel Xeon Platinum 8470 + 4× H100 + 1TB DDR4),Python 3.10、PyTorch 2.7、CUDA 12.9。注意 HIPPOCAMPUS 本身并不需要 GPU,GPU 主要用于跑 baseline 的 embedding 模型。

---

## 5. 实验结果

**Benchmark**:LoCoMo(每个 conversation 32 sessions、~600 turns、~16K tokens)与 LongMemEval-S/M(500 题,5 类记忆能力)。

**LoCoMo 端到端准确率**(F1 / BLEU-1 / LLM-as-a-Judge):

| 任务 | 最佳 baseline | HIPPOCAMPUS |
|---|---|---|
| Single-Hop | MemOS 39.24 / 40.76 / 2.75 | 34.36 / 30.04 / **3.08** |
| Multi-Hop | MemOS 30.11 / 30.91 / 2.56 | **31.97 / 31.85 / 3.22** |
| Temporal | A-Mem 34.63 / 34.87 / 2.18 | **38.30 / 37.35 / 2.94** |
| Open-Domain | MemoryOS 41.51 / 41.43 / 2.59 | **48.38 / 46.80 / 2.97** |

注意:Single-Hop 上 F1 略低于 MemOS,但 LLM-judge 仍最高;其余三类任务 HIPPOCAMPUS 全维度领先。

**LoCoMo 效率**:

- 平均端到端 query 延迟 ≈ **1.08s**,MemGPT ≈ 33.6s(31× faster)
- 平均每 query token 消耗 ≈ **1.3K**,MemGPT ≈ 16.9K(13× lower);MemoryOS ≈ 8.1K(6× lower)
- search 阶段在端到端时间中只占很小一部分,与 baseline 中 search 占 80%+ 形成强烈对比

**LongMemEval-S**:HIPPOCAMPUS 在全部 6 个子任务(single-session-preference、single-session-assistant、temporal-reasoning、multi-session、knowledge-update、single-session-user)上 F1、Accuracy、LLM-judge 均为 SOTA。如 Single-session-user 上 accuracy 68.57 vs MemOS 51.43。LongMemEval-M(Appendix C)趋势一致。

**Memory 构建开销**(Appendix E,Table 5):

| 系统 | Build time (min) | Token consumption |
|---|---|---|
| MemoryOS | 4458.96 | 41540 |
| Nemori | 477.66 | 27637 |
| MemGPT | 59.49 | 50674 |
| MemOS | 70.00 | 21055 |
| A-Mem | 35.69 | 19926 |
| **HIPPOCAMPUS** | **6.70** | **0** |

构建期 5.3× 快于最快 baseline,且 token 消耗为 0(因为没有 LLM-based summary/note 生成)。

**Ablation**(Appendix D):D ∈ {256, 512, 1024, 2048},d ∈ {16, 32, 64, 128}。准确率随 D、d 增大而轻微提升但很快饱和;search time 大致随 d 线性增长。论文给的默认配置 D=1024、d=64 平衡了速度和准确率。

**理论分析**(Appendix F、G):

- 构建复杂度 O(n log n),空间 O(n log σ)
- Query 复杂度 O(n · d / w)(w 为机器字长),最坏情况线性,但常数因子远小于 dense vector
- 通过 Charikar (2002) 的随机超平面 hashing 理论,证明 Hamming distance / d 集中在 θ/π 附近,选 d = O(ε⁻² log(N/δ)) 即可保证 (ε, δ)-approximate cosine similarity search

---

## 6. 批判性分析

1. **Query 复杂度仍然是 O(n)**:论文反复强调"不像 KG 那样组合爆炸",但 HIPPOCAMPUS 的 Hamming-ball 检索本质上是对 Signature DWM 中**所有** signature 做线性扫描。当 memory 真的扩展到百万 token 级,即使每条对比只是一次 XOR + POPCOUNT,绝对延迟仍会线性增长。论文的 evaluation memory size 上限只到 16K tokens(LoCoMo 单 conversation 大小),并未真正展示 long-horizon scalability。Appendix F 的"线性 vs HNSW 的 log n"对比对 HIPPOCAMPUS 反而是 **不利的** —— FAISS HNSW 在大 n 下有 sublinear 优势,这一点被论文淡化处理。

2. **Single-Hop 任务上不敌 MemOS**:F1 34.36 vs MemOS 39.24 是显著差距(~12% relative),论文用 LLM-judge 略高(3.08 vs 2.75)来叙述"质量更好",但 LLM-judge 本身的可信度比 F1/BLEU 弱得多。这暴露了 binary signature 在精确匹配任务上的固有损失,而 paper 没有正面分析。

3. **Random Indexing 的 vocabulary 假设**:每个 vocabulary token 预分配一个 fixed sparse 基向量,意味着 token-id 改变(换 tokenizer)就要重建 signature DB。这对实际部署中切换 LLM 是个隐性 lock-in,论文未讨论。

4. **Keyword 抽取依赖额外 LLM 调用**:Memory 构建期号称 "0 token",但 query 期需要先用 LLM "extract a small set of keywords from the natural language query"。这部分 token cost 看似被算到了 query 预算里,但论文给的 1.3K token / query 是否包含这部分 keyword extraction 的 prompt 未明说。如果不含,则真实成本被低估。

5. **Sliding window 大小、stop word 处理、tokenizer 影响等关键工程细节缺失**:Random indexing 的质量严重依赖 W(i) 大小、token 频率分布,但论文 Section 3.3 的形式化描述里 W 大小、t(基向量非零位数)都未给出实验值。

6. **BLEU-1 与 F1 的提升幅度不对称**:看 LongMemEval-S 表 2,HIPPOCAMPUS 的 F1 / Accuracy 比 MemOS 几乎翻倍(如 Single-session-user 19.48 vs 13.63;68.57 vs 51.43),但论文正文对这种**异常大幅领先**未做交叉验证或异常排查。在 NLP benchmark 上,不依赖 LLM rewriting 的方案能比 LLM-heavy 方案高出 30%+ 是值得怀疑的;读者应警惕 baseline 配置是否做到位(例如 prompt 是否一致)。

7. **DWM 的 dynamic rank/select 实现细节缺失**:论文声称 dynamic 版本下 rank/select 仍是 O(log n),但具体的底层 bit-vector 数据结构(B-tree、blocked structure 等)只字未提。Append 的实际常数因子、是否会触发 block split / 重平衡、内存峰值如何控制,都没有 microbenchmark。这是工程实现里最关键的部分,缺失意味着 reproducibility 风险高。

---

## 7. AI Infra / MLSys 视角

这篇论文对 AI Infra / MLSys 研究者有几条值得跟进的启示:

1. **Embedding-free retrieval 的方向**:大多数 RAG / agent memory 设计默认 dense vector embedding 是必经之路,导致 GPU 在 retrieval path 上长期高占用。HIPPOCAMPUS 证明对**对话历史**这一类高度结构化的文本流,token-id + bitwise hashing 也能 work。可以延伸思考:在 KV-cache offload、long-context attention 加速、agent reflection memory 等场景,是否也有类似的"用低维 binary representation 替代 dense vector"的空间?

2. **Succinct data structure 在 ML 系统中的复兴机会**:Wavelet matrix、Bloom filter、succinct trie 在 information retrieval 领域是经典工具,但 ML system 社区基本忽视。HIPPOCAMPUS 是把这一类紧凑数据结构应用到 LLM serving / memory 管理的一次实证。可以延伸到:KV-cache 索引、prompt prefix 共享检测、distributed parameter server 的稀疏 lookup 等场景。

3. **Dynamic/streaming 版本的经典数据结构是值得做的工程贡献**:论文最实质的技术增量其实是把静态 Wavelet Matrix 改成 append-only。这一思路可推广 —— 把更多静态 succinct DS(如 FM-index、CSA)做成 streaming 版本,服务于 agent 的连续运行场景,可能是个独立的 research line。

4. **CPU bitwise primitives 在 LLM-era 的重要性被低估**:论文展示了 POPCOUNT 这种 CPU 指令在 LLM agent 链路里能直接消除 GPU embedding 的瓶颈。在 agent serving 系统里,合理把 CPU 用起来(尤其是 latency-critical path)有显著价值。这与 vLLM 等 GPU-only 优化方向是互补的。

5. **可以进一步研究的具体问题**:
   - HIPPOCAMPUS 的 O(n) 检索在百万 token 级 memory 上是否仍然 acceptable?能否引入 hierarchical signature index(类似 IVF)实现 sublinear?
   - Random indexing 基向量是 vocabulary-bound 的,如何让它对**不同 LLM 模型共享**(跨 tokenizer 通用)?
   - 把 DWM 嵌入到 vLLM 的 PagedAttention 设计里,是否能减少 KV-cache 的元数据开销?
   - 与现有 retrieval-aware decoding 工作(如 retrieval-augmented training、long-context model)的组合实验。

6. **写入路径无 LLM 调用是大杀器**:Table 5 显示 HIPPOCAMPUS 构建零 token 消耗,这对 agent 长期运行的成本至关重要 —— 如果每条新对话都要付 LLM 钱去 summarize,token bill 会随时间不可控膨胀。这一点对 production agent 系统的设计哲学有指导意义:**写入路径应该尽量做到 LLM-free**。

---

## 8. 总结

HIPPOCAMPUS 的核心贡献是给 agentic memory 提供了一个 **embedding-free**、**LLM-free build path**、**bitwise-only retrieval** 的新型存储基底。技术上,它把静态 Wavelet Matrix 扩展为 append-only Dynamic Wavelet Matrix,并通过 random indexing 把语义检索降维成 Hamming-ball 搜索,从而把 dense vector / KG 系统普遍存在的"检索瓶颈"从端到端时间中基本消除。在 LoCoMo 与 LongMemEval 上,系统在保持(并在多数任务上超越)SOTA 准确率的同时,把端到端延迟降低 31×、token 占用降低 14×,构建时间降低 5.3×。

适用场景:对话历史长、写入频繁、对延迟敏感的 production agent(客服、个人助理、long-running automation),尤其在 CPU-only 或 GPU 资源紧张的部署中价值最大。主要局限是 query 复杂度仍线性、Single-Hop 这种精确匹配任务上略弱于 LLM-rewriting-based 方案、对 tokenizer 切换不友好、超大 memory(百万 token+)下的 scalability 未经验证。
