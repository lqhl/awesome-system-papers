---
type: paper
name: Quake
full_title: "Quake: Adaptive Indexing for Vector Search"
authors: [Jason Mohoney, Devesh Sarda, Mengze Tang, Shihabur Rahman Chowdhury, Anil Pacaci, et al.]
venue: OSDI
year: 2025
tags: [vector-search, ann, adaptive-indexing, numa, rag]
source_pdf: "[[osdi25-mohoney.pdf]]"
source_md: "[[osdi25-mohoney]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Quake: Adaptive Indexing for Vector Search (OSDI 2025)

> **一句话总结**：Quake 在分层 partitioned ANN 上用成本模型驱动在线 split/merge + Adaptive Partition Scanning（APS）按查询自适应 nprobe + NUMA 并行，动态倾斜负载下查询延迟比 HNSW/DiskANN/SVS 低 1.5–13×、更新延迟低 18–126×。

## 问题与动机

[[RAG]]、推荐、语义搜索的向量检索负载是动态倾斜的：热门实体查询集中、插入/删除成 burst，embedding 版本滚动。图索引（HNSW/DiskANN）更新贵；分区索引（Faiss-IVF/SCANN）更新便宜但固定 nprobe 在结构变化后 recall 崩塌，且查询延迟比图索引高一个量级（MSTURING10M 上 IVF 44ms vs HNSW 6.8ms）。

## 关键观察 / 隐含假设

- **观察 1**：分区总延迟 C=Σ A_lj·λ(s_lj)——热且大的 partition 主导成本；split/merge 的 ΔC 可在估计-验证两阶段保证单调改进（ΔC<−τ）。
  - **依赖假设**：滑动窗口 W 上 access frequency 能预测未来；balanced split / proportional-access 估计在真实 split 后仍近似。
  - **可能失效场景**：突发分布漂移快于 W；merge 后 receiver partition 膨胀超预期。
- **观察 2**：APS 用查询中间 top-k + 分区几何估计 recall，动态停扫——SIFT1M 上 nprobe 接近 oracle，latency 仅多 17–29%。
  - **依赖假设**：分区 refinement（邻域 k-means）控制 overlap；recall estimator 在 index 结构变化时仍校准。
  - **可能失效场景**：极低 recall target 或极高维下 estimator 保守/激进失衡。
- **假设 1**：NUMA 亲和调度 + work stealing 可把 memory-bound 分区扫描扩展到接近图索引吞吐。
  - **证据强度**：强；MSTURING100M 上 20× vs 单线程、4× vs 非 NUMA。

## 核心方法

**多级分区索引**：顶层 centroid 逐层下钻，底层存向量；insert/delete 局部追加/compact。

**Adaptive maintenance**：按 C 选 split/merge/add-level/remove-level；estimate→verify→commit 工作流；λ(s) 离线 profiling。

**APS**：扫描过程中更新 recall estimate，超 target 即 early terminate；欧氏/内积均支持。

**NUMA**：分区跨 node 分布，亲和调度 + node 内 work stealing。

发布 WIKIPEDIA-12M workload + 可配置 workload generator。

## 设计取舍

- **取舍 1**：维护触发仍部分手动/批量（每 N query）——在线调度策略标为 future work。
- **取舍 2**：多级结构 + maintenance 增复杂度，换动态负载鲁棒性。
- **边界条件**：主要评测 Wikipedia/SIFT/MSTURING；与 SPANN 等需 retuning 的 early termination 对比。

## 实验与结果

- 动态 workload：查询延迟 1.5–38× 低于 HNSW/DiskANN/SVS；更新 4.5–126× 更快。
- APS vs oracle nprobe：+17–29% latency；优于 SPANN/LAET/Auncel 等 early termination。
- NUMA：MSTURING100M 上线性扩展趋势；20× vs 单线程。
- WIKIPEDIA-12M：Faiss-IVF/SCANN 固定 nprobe 下 recall/latency 随时间退化（Figure 1b）。

## Critical Analysis

### 论证链条

「倾斜→热 partition 成本爆炸→成本模型维护+APS」对 partitioned ANN 的痛点准确。把 adaptive indexing 从数据库 领域迁到向量检索并加 NUMA，工程完整度高。收敛到 local minimum 有技术报告证明，但全局最优无保证。

### 假设压力测试

- **已证明**：动态 Wikipedia 类 workload 上全面优于静态 nprobe 与多种图/分区 baseline。
- **可能失效**：超大规模（十亿级）维护开销；GPU/磁盘 ANN 场景未覆盖；λ(s) profiling 跨硬件需重标定。
- **论文未覆盖**：与 DiskANN 内存模式的混合索引；APS 在 adversarial query 下的 recall 保证形式化。

### 实验可信度

Baseline 七类、公开 workload generator 加分；APS ablation 细。部分超参（τ、r_f）需 tuning；与商业向量库（Milvus/Pinecone）生产配置差距未测。

### 系统性缺陷

Maintenance 成本在极高更新率下可能主导；多级 k-means split 非平凡；论文依赖 technical report 补全 ΔC 公式；生产 24/7 在线维护 SLO 未讨论。

## 局限与 Future Work

- **局限 1**：Maintenance 调度策略未完全自动化。
- **局限 2**：Cost model 估计假设在剧烈漂移时可能失效。
- **Future work 1**：自动化 maintenance 调度与 scope 限制策略。
- **Future work 2**：十亿级向量与 SSD/GPU tier 的 Quake 扩展测量。

## 相关

- **相关概念**：[[RAG]]、ANN、vector search
- **同类系统**：HNSW、DiskANN、Faiss-IVF、SCANN、SpFresh、DeDrift
- **同会议**：[[OSDI-2025]]
