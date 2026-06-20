---
type: paper
name: Behdin-SemanticJobSearch
full_title: "Scaling Up Large Language Models Serving Systems for Semantic Job Search"
authors: [Kayhan Behdin, Qingquan Song, Sriram Vasudevan, Jian Sheng, Xiaojing Ma, Z Zhou, Chuanrui Zhu, Guoyao Li, Chanh Nguyen, Sayan Ghosh, Hejian Sang, Ata Fatahi Baarzi, Sundara Raman Ramachandran, Xiaoqing Wang, Qing Lan, Vinay Y S, Qi Guo, Caleb Johnson, Zhipeng Wang, Fedor Borisyuk]
venue: MLSys
year: 2026
tags: [semantic-search, ranking, slm, pruning, sglang, linkedin, production]
source_pdf: "[[c16a5320fa475530d9583c34fd356ef5.pdf]]"
source_md: "[[c16a5320fa475530d9583c34fd356ef5]]"
---

# Scaling Up Large Language Models Serving Systems for Semantic Job Search (MLSys 2026)

> **一句话总结**：LinkedIn 语义职位搜索用 decoder-only cross-encoder [[SLM]] 对 (query, job) 打 `pyes` 分，需 **3.15M items/s** 级吞吐；结构化剪枝（600M→375M）+ RL 职位描述摘要（**>10×** 上下文压缩）+ [[SGLang]] prefill-only  serving 优化（批 tokenization、in-batch prefix cache、去 decode），离线 per-GPU 吞吐 **4.6×**、端到端系统约 **10×**，NDCG@10 降 **<2%**。

## 问题与动机

语义搜索用 [[LLM]] 做 relevance judge 质量好，但工业部署受延迟与吞吐约束。LinkedIn Semantic Job Search：EBR 召回 → cross-encoder SLM 精排（无额外 rerank）→ 拍卖层；7B teacher 蒸馏 0.6B SLM，prompt 含 metadata + 长 `desci`（中位 **~900** token，max **>2100**，占 prompt **94%**）。

目标：**3.15M items/sec** 全局 scoring 能力；标准 chatbot serving（prefill+decode、sampling）与极高 RPS prefill-only 负载不匹配。

## 关键观察 / 隐含假设

- **观察 1：OSSCAR 剪 50% MLP 神经元 + 去掉末 8 层 transformer，600M→375M，NDCG@10 损失 **<1%**（加轻量 SFT ~16 H100·h 可恢复）。**
  - **依赖假设**：末层对 ranking 最不敏感；in-domain 40M token calibration 数据足够。
  - **可能失效场景**：新特征域或 multilingual 职位；激进剪枝 **>45%** 可能触及质量悬崖。

- **观察 2：纯 prompt 摘要不够；需 RL 对齐 SLM——reward = 长度惩罚 + 摘要 vs 原文 SLM 输出 KL；GSPO + P2 penalty（w=0.4）实现 **93%** 描述长度压缩、p50 描述占 prompt 从 **94%→54%**，NDCG 降 **<2%**。**
  - **依赖假设**：冻结 SLM 作 reward model；离线 1.7B actor 可流式更新摘要。
  - **可能失效场景**：非英语职位摘要倾向英语；**>95%** 压缩 precipitous 质量跌。

- **观察 3：prefill-only + 共享 query prefix 使 in-batch prefix caching（LogSumExp 合并两次 attention）与批 tokenization 成为主导优化；去 decode/sampling 单请求 33ms→20ms。**
  - **依赖假设**：每 query 批内多 item 共享前缀；仅需末 token yes/no logits。
  - **可能失效场景**：item 级特征差异大、前缀不可共享的 facet。

- **假设 1：系统层（Couchbase 分数缓存 TTL 15min **>50%** 命中、PID 动态 depth、traffic shaping）与模型压缩同等重要。**
  - **证据强度**：**高**——peak depth 250→131（**48%** GPU/查询），shaping 单 H100 1600→2000 items/s。

## 核心方法

**模型压缩**：OSSCAR 结构化剪枝 MLP；逐层去掉 transformer block（末层最安全）；组合后 **375M**。

**上下文压缩**：1.7B actor + verl/GSPO；reward 式 (4) 平衡长度与 SLM KL；生产用 summarized `desci` 离线/近线（Spark/Flyte + Flink）预计算。

**SGLang serving 优化**：
- scoring path：跳过 decode/sampling，仅末 token 概率。
- batch tokenization；GPU 向量化 gather 减 CPU↔GPU 小 copy。
- `gc.freeze()` 消除 100–300ms GC 尖刺；p99@100 RPS **6220ms→454ms**（**92.7%**）。
- in-batch prefix cache：suffix 对 prefix KV 做 dense paged attention + 对自身的 causal attention，LSE 合并。

**流式/产品层**：item score cache、Dynamic Ranking Depth（PID）、traffic shaping 削峰填谷。

## 设计取舍

- **直接部署 SLM vs 蒸馏到 MLP/BERT**（Pinterest 等）：坚持自然语言 cross-encoder 可解释性，用压缩+系统优化换在线可行。
- **FP8 W8A8**：质量 OK 但吞吐仅 **+10%**，小模型非 MLP-bound，放弃量化复杂度。
- **无 uncompressed 在线 A/B**：v1 无法大规模上线，对比基线主要是 EBR 而非 uncompressed SLM。
- **单阶段 SLM 精排**：无第二 rerank——业务上未见收益。

## 实验与结果

**离线引擎**（H100，SGLang 0.4.6，Poisson 请求至 p95 **500ms**）：
- 600M 全文 → 375M 全文：**+27%** 吞吐。
- 375M + 摘要：相对 600M 全文 **4.6×** 吞吐，质量 **<2%** NDCG 损失。
- 摘要使均 prompt **900→220** tokens（**4×**）。

**Serving 微优化**：批 tokenization、去 decode、内存同步优化、in-batch prefix（bs=50 约 **+33%**）。

**生产**：SLM v2 vs EBR 在线 A/B（Table 9）；压缩栈支撑全量语义精排上线；摘要+剪枝+系统优化合计约 **10×** 系统吞吐（abstract）。

## Critical Analysis

**强项**：罕见的 **ranking-specific** 全栈案例——剪枝、RL 摘要、prefill-only runtime 协同，数字贴近 **3.15M items/s** 真实约束；强调 tokenization/GC 等「非性感」瓶颈，对高 RPS SLM 部署有参考价值。

**弱点**：大量结果在离线 bench 与内部 A/B，缺乏公开数据集复现；RL 摘要依赖 proprietary SLM reward；**10×** 是系统级乘积，单点技术难拆；cross-encoder 仍 O(items) 线性扩展，缓存与 depth 控制是必要遮羞布。

**与学术 prompt compression 差异**：item 描述海量异构、需 ranking-aligned 而非通用语义保持——这点论证充分。

## 局限与 Future Work

- 更 token-efficient 摘要语言、multilingual actor 对齐。
- FP8/投机推理在更大 SLM 上重评。
- 与 embedding-first cascade 的 cost-quality 边界。
- 开源 ranker 与摘要 pipeline 有限，外推依赖 LinkedIn 栈。

## 相关

- **Serving**：[[SGLang]]、[[vLLM]]、prefill-only、prefix caching
- **压缩**：OSSCAR、GSPO、SmoothQuant
- **应用**：semantic search、cross-encoder ranking、EBR
- **对比**：Pinterest LLM judge 蒸馏路线