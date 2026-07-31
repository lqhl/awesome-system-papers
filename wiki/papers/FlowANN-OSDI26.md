---
type: paper
name: FlowANN
full_title: "Disentangling Graph Dependencies for Efficient Billion-Scale GPU Vector Search"
authors: [Haoru Zhao, Jingkai He, Jingyao Zeng, Mingkai Dong, Dong Du]
venue: OSDI
year: 2026
tags: [vector-search, anns, gpu, graph, cpu-gpu-offloading]
source_pdf: "[[osdi26-zhao.pdf]]"
source_md: "[[osdi26-zhao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 解耦图依赖实现十亿规模 GPU 向量搜索（OSDI 2026）

> **原题**：Disentangling Graph Dependencies for Efficient Billion-Scale GPU Vector Search

> **一句话总结**：FlowANN把graph search的step barrier拆成node discovery→later expansion依赖，利用中间window异步从CPU取edges，并在GPU只缓存short-window tier；十亿规模单GPU相对SOTA平均4.08×–45.7×、最高172.6×且不降accuracy。

## 问题与动机

billion graph量化后仍需258–350GB，无法fit 80–96GB GPU；按step同步host fetch使GPU每轮stall。

## 关键观察 / 隐含假设

- node先作为neighbor被discover，数步后才被选为parent expansion，存在fetch window。
- 不同edges window长度不同，长window适合host tier、短window需GPU cache。
- deferred neighbor不改变best-first search最终语义，额外candidate成本可界定。

## 核心方法

tiered graph按estimated window placement edges；discover时xCopier发async host fetch，GPU继续其他nodes，dynamic coordinator在expansion deadline前同步。adaptive batching/cache处理query width和[[PCIe|PCIe]] bandwidth；理论分析界定fetch latency带来的额外work。

## 实验与结果

- **设置**：三种billion datasets、single H20/GPU，对比GPU/CPU-offload ANNS，以QPS/latency、recall为指标（§8）。
- 平均4.08×–45.7×，最高172.6×，search accuracy不变。
- 无tiering仍比baseline快1.5×–50.6%；preprocess新增4.9%–8.4%。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| node-level依赖隐藏host fetch | 图 13、§8 | graph ANNS | 强 |
| 单GPU支持billion scale | end-to-end | PCIe/H20 | 强 |

## 批判性分析

### 论证链条

从strict step dependency转成discovery-expansion window是核心洞察，no-tiering ablation隔离了pipeline贡献。

### 假设压力测试

低window/high-degree或PCIe contention会让fetch错过deadline；dynamic updates使window/profile过期。

### 实验可信度

三datasets与强speedup有力，single-GPU offline search为主，online tail/multi-tenant未充分覆盖。

## 局限与后续工作

- dynamic graph、SSD tier与online P99。
- multi-GPU/shared PCIe contention。

## 相关

- **相关概念**：[[ANNS]]、[[Vector-Search]]、[[Graph-Search]]、[[CPU-GPU-Offloading]]
- **同会议**：[[OSDI-2026]]
