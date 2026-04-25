---
type: paper
name: HedraRAG
full_title: "HedraRAG: Co-Optimizing Generation and Retrieval for Heterogeneous RAG Workflows"
authors: [Zhengding Hu, Vibha Murthy, Zaifeng Pan, Wanlu Li, Xiaoyi Fang, et al.]
venue: SOSP
year: 2025
tags: [rag, llm-serving, vector-search, gpu-cache, graph-scheduling]
source_pdf: "[[3731569.3764806.pdf]]"
source_md: "[[3731569.3764806]]"
---

# HedraRAG: Co-Optimizing Generation and Retrieval for Heterogeneous RAG Workflows (SOSP 2025)

> **一句话总结**:用 RAGraph 图抽象统一刻画多样 [[RAG]] workflow,通过 node splitting/reordering/edge rewiring 做子图粒度调度,端到端吞吐比 LangChain/FlashRAG/vLLM 类框架快 >1.5×、最高 5×。

## 问题

现代 [[RAG]] 已从最初两段式(retrieval → generation)演进到 multi-hop、iterative、adaptive、HyDE/IRG 等多样 workflow——阶段数、每阶段时长、结构都动态变化。现有框架(LangChain、LlamaIndex、FlashRAG)把 [[vLLM]]-style 生成和 [[FAISS]]-style 检索当独立后端串起来,没 runtime 协调。两边 batching 逻辑冲突:LLM 偏爱 continuous token-level batching,vector search 偏爱大静态 batch;阶段长度参差不齐导致 pipeline stall;GPU 内存被 KV cache 占,IVF 索引装不下,被 PCIe 带宽卡在按需加载上。

## 核心方法

HedraRAG 核心是 **RAGraph**——把 RAG workflow 表达成图,节点是 Generation 或 Retrieval,边带 `all/each/key` 分发语义,支持嵌套与动态 spawn。系统在 RAGraph 上动态施加四类图变换(node splitting、reordering、edge addition、dependency rewiring),对应三个系统级优化:

- **Stage-level parallelism (跨请求)**:把 generation 切成 decoding step、retrieval 切到 single-cluster search 粒度,做 **fine-grained sub-stage partitioning + dynamic batching**,在 CPU-GPU hybrid pipeline 上做 load-aware 对齐,消解变长阶段引起的 stall。
- **Intra-request semantic similarity**:观察到连续 retrieval query 向量间距离小于 query 到 top-5 结果的距离;partial generation(22–50% token)embedding 已落在 top-1 结果范围内。利用此做 **semantic-aware reordering + speculative execution**,提前发起下一个 retrieval,与当前 generation 重叠。
- **Inter-request retrieval skewness**:IVF4096 下 top 20% cluster 吃掉 69% 计算。设计 **partial GPU index cache + async update**,只缓存 hot cluster、PCIe 异步刷新,GPU 在 generation 空档顺便做 retrieval 加速。

对开发者,HedraRAG 提供 `add_generation / add_retrieval / add_edge` 原语,兼容现有 RAG 框架。

## 关键结果

- 多种 RAG workflow(HyDE、IRG、multi-hop、branching 等)上端到端吞吐比 SOTA 框架高 >1.5×,最高 5×
- sub-stage partitioning 消除 coarse-grained 阶段顺序;dynamic batching 缓解 mismatch
- Speculative execution 让 multi-round workflow 重叠依赖阶段,显著降低单请求延迟
- GPU 部分缓存使得 hybrid 检索执行在有限显存下仍获显著加速,hotspot 动态迁移

## 相关

- **相关概念**:[[RAG]]、[[LLM-Serving]]、[[KV-Cache]]、[[PagedAttention]] 不直接但同系谱、Vector Search / [[ANN-Search]]、IVF index
- **同类工作**:[[vLLM]]、FlashRAG、LangChain、LlamaIndex、FAISS、Chameleon、RAGO、RAGCache、PromptCache、CacheBlend
- **同会议**:[[SOSP-2025]]
