---
type: paper
name: Incr
full_title: "Incr: Faster Re-execution via Bolt-on Incrementalization"
authors: [Yizheng Xie, Evangelos Lamprou, Jerry Xia, Nikos Vasilakis]
venue: OSDI
year: 2026
tags: [shell, incremental-computing, memoization, dependency-tracking, sandboxing]
source_pdf: "[[osdi26-xie-yizheng.pdf]]"
source_md: "[[osdi26-xie-yizheng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 以外挂增量化加速程序重执行（OSDI 2026）

> **原题**：Incr: Faster Re-execution via Bolt-on Incrementalization

> **一句话总结**：Incr在不改shell code/annotation下隔离跟踪command effects与dependencies，缓存可复用intermediates并对修改传播失效；real scenarios平均34.2×、最高373.3×，10,282 Bash tests中99.9%行为一致。

## 问题与动机

开发修改很小，shell/polyglot pipeline仍从头执行；传统build/dataflow需开发者声明依赖，non-idempotent side effects又使简单memoization不安全。

## 关键观察 / 隐含假设

- subprocess filesystem effects可在sandbox观察并推断依赖。
- unchanged command在inputs/effects一致时可复用保存结果。
- 初次执行tracing/storage开销由多次重跑摊销。

## 核心方法

analysis phase用isolated effect tracing和probes记录read/write/environment，推断dependency graph；re-execution比较program/input变化，只执行affected closure并commit缓存effects。eager streaming、introspection和storage compaction降低time/space。

## 实验与结果

- **设置**：real shell/data/ML scenarios与Bash suite，对比full re-execution，以speedup、cache size和behavior equivalence为指标（§8）。
- 平均34.2×、最高373.3×；初次runtime平均2.01×，cache平均6.05× input。
- 10,279/10,282 tests一致；storage compaction平均省55.7%，speedup只降1.9%。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| bolt-on incrementalization大幅加速重跑 | 图 5、§8 | filesystem-centric scripts | 强 |
| 语义基本保持 | 表 3 | Bash tests | 强 |

## 批判性分析

### 论证链条

dependency/effect记录同时回答reuse与non-idempotence，结果覆盖收益和首轮/存储代价。

### 假设压力测试

network、database、clock/randomness和外部不可回滚effect会限制复用；cache可达input 55.44×。

### 实验可信度

大量tests与real scenarios有力，但99.9%仍有3处差异，不能视作完全transparent。

## 局限与后续工作

- external service transaction plugins与严格effect coverage。
- cost model自动关闭不划算cache。

## 相关

- **相关概念**：[[Incremental-Computation]]、[[Memoization]]、[[Dynamic-Dependency-Tracking]]
- **同会议**：[[OSDI-2026]]
