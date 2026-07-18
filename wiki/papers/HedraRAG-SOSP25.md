---
type: paper
name: HedraRAG
full_title: "HedraRAG: Co-Optimizing Generation and Retrieval for Heterogeneous RAG Workflows"
authors: [Zhengding Hu, Vibha Murthy, Zaifeng Pan, Wanlu Li, Xiaoyi Fang, Yufei Ding, Yuke Wang]
venue: SOSP
year: 2025
tags: [rag, llm-serving, vector-search, cpu-gpu, workflow]
source_pdf: "[[3731569.3764806.pdf]]"
source_md: "[[3731569.3764806]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# HedraRAG: Co-Optimizing Generation and Retrieval for Heterogeneous RAG Workflows (SOSP 2025)

> **一句话总结**：heterogeneous [[RAG]] 工作流（多轮检索/生成、分支/迭代）使 LangChain/vLLM+FAISS 式阶段割裂导致 CPU-GPU 流水线空置；HedraRAG 用 RAGraph 图抽象 + 动态变换（split/reorder/rewire），相对 SOTA 框架 **>1.5× 至 5×** 吞吐。

## 问题与动机

[[RAG]] 从两阶段（retrieve→generate）演化为 multi-hop、query rewrite、rerank、CoT 验证等**异构 DAG**。生成侧 [[vLLM]] continuous batching vs 检索侧 FAISS 偏好大静态 batch，阶段时长波动造成 hybrid pipeline stall（Figure 5）。现有框架把 LLM 与向量搜索当独立后端，缺运行时协同优化。

## 关键观察 / 隐含假设

- **观察 1**：优化机会在三维——跨请求 stage 并行、请求内语义相似复用、跨请求索引访问 skew。
  - **依赖假设**：embedding 连续阶段距离近可 speculative reorder；IVF 热点可 GPU 部分缓存。
  - **可能失效场景**：embedding 分布漂移大时 speculative 失效增加。
- **观察 2**：图变换（node split、edge add、dependency rewire）比固定 stage scheduler 探索空间大。
  - **依赖假设**：工作流可编译为 RAGraph；与 LangChain/LlamaIndex API 可桥接。
  - **可能失效场景**：高度动态 agent 图难以静态构图。
- **假设 1**：wavefront 子图批处理可对齐 CPU 检索与 GPU decode 节奏。
  - **证据强度**：中强；多 workflow benchmark 有 5× 上限。

## 核心方法

**RAGraph**：统一表示 heterogeneous RAG DAG。

**三类技术**：
1. **Fine-grained sub-stage partition + dynamic batching**——缓解变长 stage pipeline stall
2. **Semantic-aware reordering + speculative execution**——利用请求内相似性重叠依赖阶段
3. **Partial GPU index cache + async update**——捕捉跨请求 skew

动态对并发请求 wavefront 应用图变换并调度到 CPU–GPU pipeline。

## 设计取舍

- **取舍 1**：图优化复杂度 vs 框架通用性——依赖 RAGraph 构造器覆盖 workflow 模式。
- **取舍 2**：GPU 缓存有限 + PCIe 延迟——partial cache 需 runtime 自适应，静态策略失效。
- **边界条件**：简单两阶段 RAG 增益可能接近 **1.5×** 下限。

## 实验与结果

- 多类 workflow：**>1.5× 至 5×** vs 现有框架吞吐
- 兼容开源框架 graph API 集成
- 覆盖 multi-round、branching、iterative RAG 模式

## Critical Analysis

### 论证链条

动机图（CPU-GPU 不匹配）+ 三维机会 → RAGraph 变换 → 1.5–5×，结构合理。到生产 agent 平台跳步：质量回归（speculative reorder 是否影响答案正确性）论文侧重系统吞吐，accuracy ablation 需读者查 workload 细节。

### 假设压力测试

- **语义 speculative**：错误 overlap 可能导致 wasted GPU prefill——需 rollback 成本分析。
- **索引更新**：async cache 与 corpus 更新一致性窗口未充分讨论。
- **规模**：超大 IVF 上 partial GPU cache hit rate 敏感性未知。

### 实验可信度

UCSD 团队、多 workflow 覆盖；与 FlashRAG/LangChain 对比合理。缺与 disaggregated RAG（Chameleon/RAGO）在 multi-node 下的对比。

### 系统性缺陷

图变换搜索本身 CPU 开销、debug 复杂度高；论文未讨论 multi-tenant SLA 隔离与 cost-aware scheduling。

## 局限与 Future Work

- **局限 1**：极度动态 agent 图可能无法高效 RAGraph 化。
- **局限 2**：speculative 路径的质量-性能 trade-off 因任务而异。
- **Future work 1**：与 [[Pie]] 类 programmable serving 结合，inferlet 级 KV 策略 + HedraRAG 调度联合测量。
- **Future work 2**：corpus 高频更新下 cache invalidation 策略与 P99 检索延迟。

## 相关

- **相关概念**：[[RAG]]、[[vLLM]]、[[KV-Cache]]、[[Vector-Search]]、[[FAISS]]
- **同类系统**：LangChain、FlashRAG、Chameleon、RAGO、RAGCache
- **同会议**：[[SOSP-2025]]
