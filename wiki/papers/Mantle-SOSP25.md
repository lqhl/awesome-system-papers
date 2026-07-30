---
type: paper
name: Mantle
full_title: "Mantle: Efficient Hierarchical Metadata Management for Cloud Object Storage Services"
authors: [Jiahao Li, Biao Cao, Jielong Jian, Cheng Li, Sen Han, Yiduo Wang, Yufei Wu, Kang Chen, Zhihui Yin, Qiushi Chen, Jiwei Xiong, Jie Zhao, Fengyuan Liu, Yan Xing, Liguo Duan, Miao Yu, Ran Zheng, Feng Wu, Xianjun Meng]
venue: SOSP
year: 2025
tags: [object-storage, metadata, distributed-systems, cloud-storage, baidu-bos]
source_pdf: "[[3731569.3764824.pdf]]"
source_md: "[[3731569.3764824]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Mantle：云对象存储服务的高效分层元数据管理（SOSP 2025）

> **原题**：Mantle: Efficient Hierarchical Metadata Management for Cloud Object Storage Services

> **一句话总结**：Baidu 生产 COSS namespace 达数十亿对象、平均路径深度 ~11、lookup 占 metadata 延迟 89%+；Mantle 用 per-namespace IndexNode 单 RPC 路径解析 + sharded TafDB delta update，单 namespace 1.89M lookup/s、高争用下 58K mkdir/s，Spark/音频预处理 job 完成时间缩短 38–93%。

## 问题与动机

[[Cloud-Object-Storage]]（S3/BOS/GCS）是云应用主存储（AWS 调研 68% 用 S3），analytics/ML 依赖深层目录与高频 metadata 变更。典型 DBtable-based COSS metadata 需 **多轮 RPC 逐级 path resolution**，且跨 shard mkdir/rename 需分布式事务，在热点目录上 contention 严重。DFS 优化（client cache、speculative lookup）因 **stateless proxy、受限 REST API、无协作客户端** 难以套用。

## 关键观察 / 隐含假设

- **观察 1**：Baidu 五个生产 namespace 各 >20 亿条目，平均访问深度 >10，lookup 占 objstat/dirstat/delete 延迟 **63–92%**。
  - **依赖假设**：Spark/ML 等小对象 workload 使 metadata 成为端到端瓶颈（部分场景 >70%）。
  - **可能失效场景**：大对象顺序读主导 workload metadata 占比下降，Mantle 收益缩小。
- **观察 2**：目录元数据远少于对象（8–18%），可把 lightweight directory index 放单节点 IndexNode，bulk metadata 放 sharded TafDB，实现 **single-RPC lookup**。
  - **依赖假设**：IndexNode 可通过 Raft follower/learner  offload + TopDirPathCache 避免 CPU/单点瓶颈。
  - **可能失效场景**：极端热点目录更新使 IndexNode 仍成 write bottleneck——论文用 delta record + loop detection offload 缓解，但极限 scale 未公开。
- **观察 3**：COSS 无 cooperative client，优化必须在 metadata service 内部完成。
  - **依赖假设**：REST API 语义固定；proxy stateless 不可缓存会话。
  - **可能失效场景**：未来 S3 Express 类低延迟路径可能改变设计约束。

## 核心方法

**Two-layer architecture**：

1. **TafDB**：全量 metadata 的可扩展 sharded DB；**delta record** 代替 in-place update 降 abort；跨目录 rename 的 loop detection offload 到 IndexNode。
2. **IndexNode**：per-namespace 单服务器，缓存必要目录元数据；TopDirPathCache 缓存高稳定前缀；Invalidator 无锁失效；Raft 副本分担 lookup。

Baidu BOS 部署 **>2 年**，19 个内部 namespace。

## 设计取舍

- **Per-namespace IndexNode vs 纯分布式**：lookup 极致低延迟，但 namespace 级单点需精心 offload。
- **Delta append vs in-place**：写争用低，但存储放大与 compaction 成本——论文未详述长期磁盘开销。
- **Strong consistency 保持**：不像部分 DFS relaxed isolation；与 COSS API 语义一致。

## 实验与结果

- 单 namespace **100 亿** entries；**1.89M** lookups/s。
- 高争用：**58.8K** mkdir/s、**38.0K** dirrename/s。
- vs Tectonic/InfiniFS/LocoFS：metadata latency 降 **6.6–99.1%**，吞吐 **0.07–115×**（依 baseline/op）。
- 端到端：Spark analytics job 快 **63.3–93.3%**；AI 音频预处理 **38.5–47.7%**。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| IndexNode combines path-resolution metadata with single-RPC access | about 80 bytes/directory while TafDB retains full metadata (§4–5, Fig.5–6) | design evidence; baseline DBtable multi-RPC resolution | high |
| Deep-path lookup is measured as the main COSS cost | 89.9%/91.2%/63.1% for objstat/dirstat/delete (§3.1, Fig.3–4) | 512-thread mdtest and five Baidu namespaces | high |
| Mantle lowers lookup latency in mdtest | vs Tectonic 83.9–89.0%, InfiniFS 80.0–84.2%, LocoFS 16.4–74.5% (§6.3, Fig.12–13) | 1B entries/depth 10, 512 clients, authors’ reimplementations | high |
| Delta records improve tested contention operations | mkdir-s 1.96× vs InfiniFS; dirrename-e 26.2% over Tectonic (§6.3, Fig.14–15) | two operations and distinct contention scenarios | high |
| Application completion time improves in two workloads | Analytics 73.2/93.3/63.3%; Audio 47.7/40.1/38.5% vs three baselines (§6.2, Fig.10b) | specific Spark analytics and audio preprocessing | high |

## 批判性分析

### 论证链条

Production trace（深度、lookup 占比）→ two-layer + delta/offload → mdtest + 真实应用，链条强。IndexNode 单点容错依赖 Raft，但 **跨 namespace 故障域** 与运维 story 公开有限。

### 假设压力测试

- 扁平 bucket（浅路径）客户收益有限。
- TopDirPathCache 静态策略对频繁 rename 前缀可能失效——Invalidator 正确性关键但细节难独立审计。
- 115× 峰值需看具体 op/baseline，不宜作普遍 speedup 期望。

### 实验可信度

- 生产部署 + 真实 Baidu workload 可信度高。
- 与 Tectonic/InfiniFS/LocoFS 对比覆盖 research+industry systems。
- 开源承诺（mantle-opensource.github.io）利于复现。

### 系统性缺陷

- 论文未讨论 IndexNode 内存上限与 billion-entry namespace 冷启动。
- 多租户 fair-share、跨 region replication metadata 未讨论。
- Delta store 长期 compaction 运维成本未量化。

## 局限与后续工作

- **局限**：namespace 级 IndexNode 运维复杂；浅路径 workload 收益小；delta 存储开销未充分公开。
- **Future work**：跨 region IndexNode；自动化 cache 前缀选择；与 S3 Express 类架构对比。

## 相关

- **相关概念**：[[Cloud-Object-Storage]]、Object Metadata、[[S3]]、Distributed Transactions
- **同类系统**：Tectonic、InfiniFS、LocoFS、DynamoDB+S3
- **同会议**：[[SOSP-2025]]
