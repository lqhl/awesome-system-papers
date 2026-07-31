---
type: paper
name: Merlin
full_title: "Merlin: An Efficient Adaptive Cache Eviction Algorithm via Fine-Grained Characterization"
authors: [Liujia Li, Jinhao Guo, Yi Fan, Jianyu Wu, Zhenlin Wang, et al.]
venue: OSDI
year: 2026
tags: [caching, cache-eviction, adaptive-systems, workload-characterization, multicore]
source_pdf: "[[osdi26-li-liujia.pdf]]"
source_md: "[[osdi26-li-liujia]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 基于细粒度刻画的自适应缓存淘汰（OSDI 2026）

> **原题**：Merlin: An Efficient Adaptive Cache Eviction Algorithm via Fine-Grained Characterization

> **一句话总结**：既有adaptive cache在少数LFU/LRU/scan类别间切换，base algorithms之间还互相干扰；Merlin按object同时刻画frequency、recency与相对cache-size locality，并解耦characterization/selection/eviction，在11 datasets、5,423 traces上把系统throughput提高1.4×–7.8×。

## 问题与动机

现代KV/CDN/page-cache workload由LFU-friendly、LRU-friendly、churn、scan等pattern混合并随时间变化。现有adaptive policy通常在两三个完整algorithm之间切换；它们只识别预设典型pattern，且各自metadata/admission/eviction会改变另一个算法看到的状态，真实trace上甚至输给static policy。

## 关键观察 / 隐含假设

- workload不能可靠归为单一全局类别，应在individual object粒度刻画access locality。
- frequency/recency是否有价值依赖cache capacity；相同trace在不同cache size下pattern可改变。
- 组件各做单一职责比并行运行完整base algorithms更稳，可避免shadow state interference。
- online history能代表近期访问，phase变化速度不超过characterizer反应速度。

## 核心方法

Merlin为对象维护低成本fine-grained signal，将frequency、recency/reuse与cache-size-aware position统一进pattern characterization；随后由独立policy adjustment将对象分配到适合的管理逻辑，而 eviction data structure只执行已选决策。此“刻画—调节—执行”解耦避免传统adaptive algorithm间共享状态和相互驱逐。

实现强调constant-size/采样式metadata与multicore scalability，目标是在高并发software cache中让adaptive收益大于管理开销。

## 实验与结果

- 11个real-world datasets、5,423 traces覆盖不同cache sizes与访问混合，比较static与adaptive eviction baselines。
- Merlin在hit rate上表现稳健，不只优化少数adversarial trace；下游KV/cache系统throughput提高1.4×–7.8×。
- pattern breakdown展示已有adaptive schemes在churn/scan/mixed phases下可低于其static component，支持“粗粒度分类+算法干扰”诊断。
- concurrency/metadata实验显示设计保有low overhead与high multicore scalability，避免hit-rate收益被锁竞争抵消。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 既有adaptive algorithm并不稳健 | §3 trace analysis | 11 datasets | 强 |
| object/cache-size-aware刻画提高hit rate | evaluation/ablation | 5,423 traces | 强 |
| 可转化为throughput收益 | system experiments | 指定cache backends | 强 |
| multicore overhead可控 | scalability experiments | 所测CPU/cache sizes | 中 |

## 批判性分析

### 论证链条

论文先用大规模trace反驳“adaptive天然优于static”，再把失败拆成characterization盲区与component interference；Merlin对应两因，论证结构清楚。广泛trace比只展示平均hit rate更有说服力。

### 假设压力测试

object-level metadata对极高cardinality/small-object cache可能仍昂贵；rapid phase change、TTL、variable object size和cost-aware eviction会增加状态维度。hit-rate最优不等于byte-hit、latency或backend-cost最优。

### 实验可信度

实验数据支持主要设计论断，但平台与工作负载范围仍限制其普遍性。

### 系统性缺陷

自适应policy复杂度提高debug/预测困难；对adversarial access可被迫频繁改变策略。throughput 1.4×–7.8×依赖miss penalty，不能直接泛化到所有cache system。

## 局限与后续工作

- 扩展到variable-size/cost/TTL-aware objectives与byte hit rate。
- 测突发phase change、adversarial trace及metadata budget极低场景。
- 在CDN、kernel page cache与distributed cache生产系统长期A/B验证tail latency。

## 相关

- **相关概念**：[[Cache-Eviction]]、[[LRU]]、[[LFU]]、[[Working-Set]]、[[Adaptive-Systems]]
- **同类系统**：[[ARC]]、[[LIRS]]、[[TinyLFU]]
- **同会议**：[[OSDI-2026]]
