---
type: paper
name: Behdin-SemanticJobSearch
full_title: "Scaling Up Large Language Models Serving Systems for Semantic Job Search"
authors: [Kayhan Behdin, Qingquan Song, Sriram Vasudevan, Jian Sheng, Xiaojing Ma, Z Zhou, et al.]
venue: MLSys
year: 2026
tags: [semantic-search, slm, model-compression, sglang, prefill-only]
source_pdf: "[[c16a5320fa475530d9583c34fd356ef5.pdf]]"
source_md: "[[c16a5320fa475530d9583c34fd356ef5]]"
---

# Scaling Up Large Language Models Serving Systems for Semantic Job Search (MLSys 2026)

> **一句话总结**：LinkedIn 语义职位搜索用 0.6B→375M cross-encoder SLM + RL 描述摘要（10× 上下文 压缩）+ [[SGLang]] prefill-only  serving 优化，在线 **2000 items/s/GPU**、相对未优化版本 **10×** 吞吐，NDCG@10 损失 <2%。

## 问题

语义搜索 cross-encoder 需对海量 (query, job) 打分，目标 **3.15M items/s** 级吞吐。全自然语言 prompt 中 job description 占 **~94%** token（median ~900，max >2100），attention 二次复杂度拖累延迟。未压缩 0.6B SLM 无法大规模上线，用户长期只能用 EBR 检索。

## 核心方法

**Ranking SLM**：decoder-only cross-encoder，`pyes = softmax(logit_yes, logit_no)` 末 token 分类；7B teacher 蒸馏 → 0.6B。

**Model compression**：
- OSSCAR 剪 MLP 50% hidden neuron + 去掉末 8 个 transformer block → **375M**（-45%），SFT 恢复精度
- **RL 摘要 actor**（GSPO + 长度惩罚 P2）：1.7B LM 离线压缩 description，reward = KL(SLM 输出|全文 vs 摘要) + 长度项；p50/p99 长度降 **93%**，NDCG 降 <2%

**[[SGLang]] serving 优化**（prefill-only scoring）：
- Batch tokenization、跳过 decode/sampling、GPU 向量化末 token prob、gc.freeze()
- In-batch prefix caching：同 query 多 item 一次 forward（LogSumExp 合并 attention）
- 流式：Couchbase 分数缓存（>50% hit）、PID dynamic ranking depth、traffic shaping

## 关键结果

- 离线（H100）：prune + summarize **4.6×** 吞吐 vs 600M 全文；仅 prune **1.27×**
- 在线：**2000 items/s/GPU**（375M + 摘要），较 SLM v1 **>10×**；traffic shaping 再 +25% capacity
- 质量：压缩后 NDCG@10 降 <2%；vs LiRank DCNv2 **+46.7%** NDCG@10；vs EBR 显著降 Poor Match Rate
- 开源：fmchisel（剪枝/蒸馏）、多项 SGLang PR（#5141 batch tokenization、#8840 skip decode 等）

## 相关

- **相关概念**：[[Quantization]]、structured pruning、prefill-only、cross-encoder ranking
- **同类系统**：[[SGLang]]、LiRank、EBR retrieval
- **同会议**：[[MLSys-2026]]