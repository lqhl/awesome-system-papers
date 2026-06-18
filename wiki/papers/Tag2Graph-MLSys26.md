---
type: paper
name: Tag2Graph
full_title: "Ontology-Guided Long-Term Agent Memory for Conversational RAG"
authors: [Shuang Cao, Rui Li]
venue: MLSys
year: 2026
tags: [rag, agent-memory, conversational-ai, retrieval, personalization]
source_pdf: "[[70efdf2ec9b086079795c442636b55fb.pdf]]"
source_md: "[[70efdf2ec9b086079795c442636b55fb]]"
---

# Ontology-Guided Long-Term Agent Memory for Conversational RAG (MLSys 2026)

> **一句话总结**：Tag2Graph-Learner 从多轮对话中在线学习用户偏好本体（User→PREFERS_GENRE→Romance 等），配合 graph×dense 一致性正则与可学习 router，在 Implicit Preference Recall 上把 Recall@10 从 0.58 提到 0.70、nDCG@10 从 0.41 到 0.51，成本仅为 long-context 的 18%。

## 问题

多 session 对话里，用户常隐式引用早期偏好（「周末看什么？」其实指几周前说的 Titanic），但 vanilla dense RAG 与 long-context 都依赖词面重叠，Recall@10 在 60+ turn 后跌到 0.28。三大挑战：

1. **Dense 检索对隐式偏好失效**：embedding 距离大，不是语义无关而是缺 lexical anchor
2. **Graph 与 dense 模态错位**：个性化 query 上 top-10 平均只重叠 3.2 条，简单加权融合不稳
3. **Serving 预算**：long-context 仅略好于 dense（0.60 vs 0.58 Recall@10），但 P95 310 ms、成本高 5×+

## 核心方法

三阶段 pipeline（ingest → query/retrieve → feedback）：

**Tag2Graph-Learner**：BERT-base BIO tagger 过生成三元组 → 2 层 MLP 门控 → 离线 LLM 校验 canonical relation；重复共现的 assertion 晋升为 typed edge（PREFERS_GENRE、LIKES 等），低置信只进 vector store 不改 graph hot path。

**Graph×Dense Consistency**：统一打分 \(s = w_g s_g + w_d s_d + w_p s_p\)（默认 0.55/0.35/0.10）；只在**已被验证引用**的 evidence 上对齐 graph 与 dense 分布，减少 47% 跨模态分歧，避免全候选对齐的算力爆炸。

**Learnable Router**：graph-first vs dense-first + 小预算探测，用时间切分日志 + counterfactual replay 离线训练，P95 185 ms guard 内选 plan。

## 关键结果

- 内部 benchmark（implicit slice）：Recall@10 0.706 / nDCG@10 0.514 vs dense-only 0.580 / 0.410；faithfulness 0.93 vs 0.86
- LoCoMo 隐式子集：0.576 / 0.451，优于 HippoRAG（0.531/0.412）与 MemoRAG（0.504/0.387）
- 成本归一化 1.31× dense-only，约为 long-context 的 0.18×（约 81% 节省）
- 消融：去掉 Tag2Graph promotion → 0.621 Recall@10；去掉 consistency → 0.662；静态 router → 0.674

## 相关

- **相关概念**：[[KV-Cache]]（非核心，但 long-context baseline 对比）
- **同类系统**：HippoRAG、MemoRAG、DH-RAG（文中 baseline，wiki 待建）
- **同会议**：[[MLSys-2026]]
- **对比**：结构增强 RAG vs 纯 dense / long-context serving 成本