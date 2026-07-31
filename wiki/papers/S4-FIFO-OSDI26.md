---
type: paper
name: S4-FIFO
full_title: "Learning-Augmented Heuristics: Simple, yet Smart, Robust and Interpretable Cache Eviction"
authors: [Haocheng Xia, William Nixon, Bintang Dwi Marthen, Pranav Bhandari, Juncheng Yang]
venue: OSDI
year: 2026
tags: [caching, cache-eviction, learning-augmented-systems, robustness]
source_pdf: "[[osdi26-xia.pdf]]"
source_md: "[[osdi26-xia]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 简单、智能且稳健的学习增强缓存淘汰（OSDI 2026）

> **原题**：Learning-Augmented Heuristics: Simple, yet Smart, Robust and Interpretable Cache Eviction

> **一句话总结**：LAH只异步学习静态heuristic的cache-level parameters，data plane仍走简单FIFO；S4-FIFO以4,140 traces预训练、1,035 production traces评测，平均miss ratio优于SOTA且worst trace仅比FIFO差0.8%，吞吐接近heuristics。

## 问题与动机

per-object learned cache频繁预测、critical-path metadata重，且objective mismatch会在未见trace灾难性退化。静态S3-FIFO快且稳，但参数无法适应workload。

## 关键观察 / 隐含假设

- 低频cache-level learning足以调queue proportions等少量参数，无需每object预测。
- heuristic data plane提供robust fallback与interpretability。
- production trace分布足以训练跨workload model。

## 核心方法

LAH分离control/data plane：异步model读取aggregate cache features，周期性输出S3-FIFO parameters；S4-FIFO增加可调第四queue与promotion/eviction配置，critical path只做queue operation。

## 实验与结果

- **设置**：1,035 production traces，对比FIFO、2Q、ARC、LRB、LHD、3L-Cache，以miss ratio和Cachelib throughput为指标（§6）。
- worst trace相对FIFO只+0.8%/+0.2%，其他smart policy可+20%–72%；3L-Cache simulator平均慢17.3×。
- S4-FIFO吞吐接近heuristics，[[LLM|LLM]]从features预测配置准确率83%/86%。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| cache-level learning兼顾平均与worst-case | 图 6–8 | production traces | 强 |
| data plane保持高吞吐 | Cachelib图 8 | 48 threads | 强 |

## 批判性分析

### 论证链条

将learning限制在parameter tuning，清楚避免per-object smart cache的复杂度与不稳。

### 假设压力测试

phase快于control update或trace/domain显著漂移时model会选错配置，但FIFO-like结构限制最坏损失。

### 实验可信度

trace规模与worst-case指标强；实际backend miss penalty、variable size/TTL尚未完整覆盖。

## 局限与后续工作

- variable-size、TTL、cost-aware cache与online drift detection。
- 长期production A/B测tail latency。

## 相关

- **相关概念**：[[Cache-Eviction]]、[[Learning-Augmented-Systems]]、[[FIFO]]
- **相关系统**：[[S3-FIFO]]、[[ARC]]、[[LRB]]
- **同会议**：[[OSDI-2026]]
