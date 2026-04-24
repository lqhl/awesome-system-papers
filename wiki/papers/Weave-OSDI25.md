---
type: paper
name: Weave
full_title: "Weave: Efficient and Expressive Oblivious Analytics at Scale"
authors: [Mahdi Soleimani, Grace Jia, Anurag Khandelwal]
venue: OSDI
year: 2025
tags: [oblivious-analytics, mapreduce, tee, noise-injection, security]
source_pdf: "[[osdi25-soleimani.pdf]]"
source_md: "[[osdi25-soleimani]]"
---

# Weave: Efficient and Expressive Oblivious Analytics at Scale (OSDI 2025)

> **一句话总结**：把 oblivious MapReduce 的性能开销从 log-linear 砍到常数（~3×）——random-shuffle + 全局直方图 + 基于噪声注入的 balanced-shuffle 组合，端到端比 Opaque / Shuffle&Balance 快 4–10×，且不限制非关联 reducer 或排序分析。

## 问题

云上 MapReduce 即便数据加密 + TEE，worker 之间的通信量模式仍然会泄露敏感信息：split-based（只有含 COVID 记录的 mapper 往某 reducer 发货）+ distribution-based（高频疾病 → reducer 流量大）。Opaque 用 oblivious sort 限制只能 associative reduce；Shuffle&Balance 用 oblivious shuffle 禁掉基于排序的分析，而且两者都是 log-linear 开销，放大端到端执行时间一个量级以上。

作者形式化了一个新的安全定义 **IND-CDJA**（Indistinguishability under Chosen Dataset and Job Attack）：观察到的 mapper-reducer 通信量与内存访问分布，应与输入数据集的 key 分布独立。并证明在 map 函数可产生 c>1 条 intermediate 的一般情况下，bandwidth 开销必然无上界——但实际 MR job 几乎都是 c≤1（filter/count/join 等），在此假设下常数开销是可达的。

## 核心方法

Weave 用 load-balancing 家族作起点，引入来自 oblivious storage 的 **noise injection** 原语。

把 shuffle 阶段替换成三个新阶段：

1. **Random-shuffle**：每个 mapper 把 intermediate K-V 对按伪随机选 weaver 发出去。每个 weaver 在期望上收到 `n̂_k / w` 条 key=k 的记录，消除 split-based leakage。此阶段没有数据依赖的内存访问，不需要 EPC。
2. **Histogram**：每 weaver 构造本地直方图（pad 到 n̂_i 项，防止长度泄露），加密广播给其他 weaver，聚合成全局直方图 ĥ。直方图放 [[EPC]]（Enclave Page Cache）里保证内存访问 oblivious。为扩展性，引入采样因子 β < 1 只抽样 βn̂ 条构建近似 ĥ，再相应把 balanced-shuffle 的 fake 流量加 (1+δ) 倍（Chernoff bound 保证区分概率可忽略）。
3. **Balanced-shuffle**：每个 reducer 固定收 `α · n̂/r` 条（α 是常数，理论下界 2r/(r+1)）。先按 ĥ 贪心 bin-pack 真实 K-V 对，不够的用 fake 填满；fake 分配由所有 weaver 共享 PRG 做 w 面骰子独立决定（期望每 weaver 发 `kv_fake[j]/w` 条到 reducer j）。这样 weaver-reducer 流量完全独立于 key 分布。Reducer 收完后丢 fake、正常跑 reduce。

EPC 只用来放数据依赖的结构（kv_real/kv_fake 计数器、直方图），数据无关的扫描保持在普通内存，降低 EPC footprint。

支持非关联 reduce（median 等），因为架构不依赖 oblivious sort；也支持 sort-based / 用户自定义 partitioning。

## 关键结果

- 多种真实世界 workload 端到端加速 4–10×（对比 Opaque、Shuffle&Balance 等同安全级别系统）
- 性能对数据集大小、worker 数近似线性扩展
- 实现基于 Apache Spark，代码和 eval 数据集开源（yale-nova/weave）
- 关键常数：α 理论下界 2r/(r+1)，评估中 max-key 热度 < 5% 的 reducer 容量，可容忍大量常见 workload
- 构造性证明：对任意 IND-CDJA 安全方案，Weave 达到 noise-injection 类方案的最低网络开销下界

## 相关

- **相关概念**：[[Oblivious-Computation]]、[[TEE]]、[[MapReduce]]、[[Differential-Privacy]]、[[ORAM]]
- **同类系统**：Opaque、Shuffle&Balance、Obladi
- **同会议**：[[OSDI-2025]]
