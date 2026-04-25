---
type: paper
name: KVCacheInTheWild
full_title: "KVCache Cache in the Wild: Characterizing and Optimizing KVCache Cache at a Large Cloud Provider"
authors: [Jiahao Wang, Jinbo Han, Xingda Wei, Sijie Shen, Dingyan Zhang, et al.]
venue: ATC
year: 2025
tags: [llm-serving, kv-cache, cache-eviction, workload-characterization, alibaba]
source_pdf: "[[atc2025-wang-jiahao.pdf]]"
source_md: "[[atc2025-wang-jiahao]]"
---

# KVCache Cache in the Wild: Characterizing and Optimizing KVCache Cache at a Large Cloud Provider (ATC 2025)

> **一句话总结**：阿里通义生产 KVCache 复用 trace 首次系统刻画 + 工作负载感知淘汰策略；命中率 +3.9%、QTTFT 降 28.3%–41.9%。

## 问题

LLM serving 普遍用 [[KV-Cache]] cache 跨请求复用前缀 KV，但既有 KVCache 系统（[[vLLM]]、CachedAttention、Mooncake、Pensieve）的设计（命中粒度、淘汰策略 LRU/FIFO/LFU）都基于合成 workload 直觉。真实生产场景的 KVCache 复用率、复用时间分布、生命周期、cache 容量需求未被系统刻画过，导致设计空间盲选。

## 核心方法

收集阿里通义两周 trace（to-C ChatBot 类 Trace A、to-B API 类 Trace B），含 timestamp、chat_id、parent_chat_id、user_id、req_type、token hash 等（已脱敏）。系统刻画后提出 workload-aware eviction：

$$\text{Priority} = (\text{ReuseProb}_w(t, \text{life}), -\text{Offset})$$

按词典序比较。`ReuseProb_w` 后台采样 + 拟合 exponential 分布得到 reuse 概率（不同 workload category——request type × turn number——单独拟合）；`Offset` 反映 spatial locality，前缀 token 优先级更高。砍掉 GDFS 里的 frequency 项，因为 KVCache 生命周期短，频繁访问也会 die。性能优化用 per-workload LRU queue 把复杂度从 O(N) 降到 O(W)，eviction 开销 79µs（占 vLLM 调度 1.2%）。

## 关键结果

关键 trace 观察：
- ideal hit ratio 仅 62%（A）/ 54%（B），低于合成 workload 报告的 80%+；reuse 极度倾斜（10% block 贡献 77% reuse）。
- to-B 中 single-turn 贡献 97% 命中（共享 system prompt），颠覆「multi-turn 主导」直觉。
- 跨用户命中极低；reuse time 短（A 的 P80 < 10 分钟、B 的 P80 < 10 秒）；P99 lifespan 仅 97 秒（B）。
- GQA 模型上 KVCache cache 容量 4× HBM 即逼近 ideal hit ratio，可能不需要 SSD 层级。

性能：
- 集成进 vLLM。比 LRU/FIFO/LFU/S3-FIFO 高 1.5%–3.9% 命中率，比所有 baseline 平均高 8.1%–23.9%。
- QTTFT（队列 + TTFT）降低 28.3%–41.9%。
- Trace 样本已开源：https://github.com/alibaba-edu/qwenbailian-usagetraces-anon

## 相关

- **相关概念**：[[KV-Cache]]、Cache Eviction、Prefix Cache、LRU、LFU、GDFS、[[Continuous-Batching]]
- **同类系统**：[[vLLM]]、Mooncake、CachedAttention、Pensieve
- **同会议**：[[ATC-2025]]
