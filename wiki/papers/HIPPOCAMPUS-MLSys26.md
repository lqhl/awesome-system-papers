---
type: paper
name: HIPPOCAMPUS
full_title: "HIPPOCAMPUS: An Efficient and Scalable Memory Module for Agentic AI"
authors: [Yi Li, Lianjie Cao, Faraz Ahmed, Puneet Sharma, Bingzhe Li]
venue: MLSys
year: 2026
tags: [agent, memory, wavelet-matrix, retrieval, succinct-data-structure]
source_pdf: "[[d645920e395fedad7bbbed0eca3fe2e0.pdf]]"
source_md: "[[d645920e395fedad7bbbed0eca3fe2e0]]"
---

# HIPPOCAMPUS: An Efficient and Scalable Memory Module for Agentic AI (MLSys 2026)

> **一句话总结**：HIPPOCAMPUS 用 Dynamic Wavelet Matrix (DWM) 把 agent 记忆存为「token-ID 流 + 二进制 signature」双表征，在压缩域做 Hamming-ball 搜索，检索延迟降最多 31×，per-query token 降 14×，对齐 LoCoMo / LongMemEval 精度。

## 问题

Agentic AI（AutoGPT、BabyAGI、ReAct 等）在 observe-plan-act-learn 循环里频繁读写外部记忆。现有 contextual memory 三类（RAG dense vector、knowledge graph、hybrid）有共同瓶颈：

- **插入慢**：要 embed、chunk、summarize；
- **检索慢**：vector 相似度或多跳图查询；ReadAgent 85% 延迟花在检索、MemoryBank 81%、A-Mem/MemoryOS 约一半。
- **Trade-off**：MemGPT / A-Mem 精度高但 latency 和 token 成本高；MemoryBank 轻量但 recall 差。

没有系统同时占据「高精度 + 低延迟 + 低 token 成本」象限。

## 核心方法

放弃 token-centric、embedding-heavy 表征，拥抱 compression-native 数据结构：

1. **双表征**：
   - **Content DWM**：lossless token-ID 序列的比特矩阵，支持 access/rank/select 精确恢复原文；
   - **Signature DWM**：每 token 经 Random Indexing (LSH) 投影为紧凑二进制 signature，同样存 DWM。

2. **Dynamic Wavelet Matrix**：把经典静态 Wavelet Matrix 扩展为 append-only。每新符号 s 做 O(l) = O(log σ) 的逐层 bit 追加，每层位置由 rank 操作递推；避免 agent 流式写入下频繁重建。

3. **Hamming-ball 查询**：query 经同一 random indexing 变 signature，在 Signature DWM 上做 rank/select 找相近 signature 的 co-occurrence，拿 metadata 中 start/end 索引（α, β）再到 Content DWM 精确取回。搜索全在压缩域、bitwise、native CPU 指令可加速。

## 关键结果

- 端到端检索延迟降 最多 **31×**，per-query token 降 **14×**。
- 精度在 LoCoMo、LongMemEval 两个 long-horizon agent benchmark 上与现有 SOTA 持平甚至更高。
- 线性 scale 随 memory 大小增长，适合 long-horizon 部署。

## 适用域与局限

- **关键 baseline 缺失**：latency/token 对比只和同类 memory module（MemGPT / MemoryOS / A-Mem 等）比，没有和「整段历史塞长 context + prompt caching」这个 2026 年最自然的替代方案比。
- **Scale 上界被长 context 消解**：LoCoMo ~16K、LongMemEval ~100K token 都在 Claude / Gemini / GPT 家族原生 context 能吃下的区间，prompt caching 把「每次 query 重付 history token 费」这个成本论点削薄。
- **Scale 下界不适合 corpus 检索**：10⁹+ token（例如百万篇 arxiv）规模下任一 signature 出现会破百万次，Hamming-ball + `select` 遍历爆炸，这个 regime 仍应 FAISS + document-level encoder embedding。
- **"Lost in the middle" 论点贬值**：2025+ 长 context 模型 needle-in-haystack 已接近 100%，论文 intro 引用的 2023 年结论的说服力在衰减。
- **真正 sweet spot 论文没 pitch**：on-device 小模型（如手机端 Llama-3.2 3B context 仅 8–32K）的外置记忆；agent 多步循环里高频 memory query 的 n × iterations 累积成本；memory 更新频率 > prompt cache TTL 的 cache-hostile 场景。

DWM 作为 append-only succinct 索引（把经典静态 Wavelet Matrix 扩展为 O(log σ) 增量 append）本身是漂亮的数据结构贡献，但 "agent memory module" 这个 framing 在 2026 年 LLM 生态里 target 不够精确 —— 有「用 2023 年的问题定义回答 2026 年的实验环境」之感。

## 相关

- **相关概念**：Agent Memory、RAG (Retrieval-Augmented Generation)、Knowledge Graph、Locality-Sensitive Hashing、Succinct Data Structure、Wavelet Matrix
- **同类系统**：ReadAgent、MemoryBank、MemGPT、A-Mem、MemoryOS、MemOS、LangChain memory、CrewAI memory
- **同会议**：[[MLSys-2026]]
