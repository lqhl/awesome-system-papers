---
type: paper
name: Mantle
full_title: "Mantle: Efficient Hierarchical Metadata Management for Cloud Object Storage Services"
authors: [Jiahao Li, Biao Cao, Jielong Jian, Cheng Li, Sen Han, et al.]
venue: SOSP
year: 2025
tags: [cloud-storage, object-storage, metadata, raft, baidu]
source_pdf: "[[3731569.3764824.pdf]]"
source_md: "[[3731569.3764824]]"
---

# Mantle: Efficient Hierarchical Metadata Management for Cloud Object Storage Services (SOSP 2025)

> **一句话总结**:用于 COSS(云对象存储)的分层元数据服务,采用「per-namespace 单机 IndexNode + 共享 sharded TafDB」两层架构,用单 RPC path lookup 取代多轮递归遍历,配合 delta-record 无冲突更新和 IndexNode 内联 rename loop 检测,单命名空间支持 100 亿对象、180 万 lookups/s、5.88 万 mkdir/s,相对 Tectonic/InfiniFS/LocoFS 延迟降 6.6-99.1%、吞吐提 0.07-115×,已在百度对象存储 BOS 生产部署 2 年。

## 问题

S3/Azure Blob/GCS 这类 [[Cloud-Object-Storage]] 是现代云的主要存储后端,但元数据访问成了瓶颈:真实 namespace 有 20 亿+ entries、平均目录深度 11(最大 95),分析/ML 任务需要高并发的深路径访问 + 大量 shared-directory 修改。实测 path lookup 占 89% 元数据操作时间,shared-directory 的 mkdir/dirrename 在高并发下吞吐降 99%+。

DFS 已有的优化(元数据缓存、speculative 并行 resolve、LocoFS 的 tiering、CFS 的 single-shard relax isolation)由于 COSS 的 stateless proxy、受限 API、无客户端合作逻辑等约束,均无法直接移植。

## 核心方法

**两层架构**:
- **TafDB**:跨 namespace 共享的 sharded 数据库,存完整元数据(对象 + 目录)
- **IndexNode**:per-namespace 单机,仅存每个目录 ~80 字节的 access metadata(pid、dirname、id、permission、lock bit),用于单 RPC lookup 和 cross-directory 协调

**关键优化**:
1. **TopDirPathCache**:静态缓存高稳定路径前缀,用独立 lock-free Invalidator 响应目录更新做失效,无运行时 promotion/demotion
2. **Raft 读 offload**:把 lookup 分到 [[Raft]] follower 和 learner 副本,突破 leader 单点
3. **Delta record**:TafDB 用 out-of-place append 替换 in-place 更新,消除高并发下的事务冲突/重试
4. **Rename loop detection offload**:跨目录 rename 的环检测从分布式事务搬到 IndexNode 本地索引,单 RPC 完成 lock + validation

写入扩展靠 Raft log batching 和 follower write offloading 维持 IndexNode 吞吐。

## 关键结果

- 单 namespace 10 亿 entries,1.89M lookups/s
- 高竞争下 58.8K mkdir/s、38.0K dirrename/s
- vs Tectonic:延迟降 17.5-95.2%,吞吐提 1.20-20.90×
- vs LocoFS:延迟降 9.5-99.1%,吞吐提 1.16-116.00×
- vs InfiniFS:延迟降 6.6-98.8%,吞吐提 1.07-80.78×
- Spark 交互分析作业完成时间降 63.3-93.3%,AI 音频预处理降 38.5-47.7%
- 百度 BOS 生产运行 2 年,19 个 namespace,数十亿对象

## 相关

- **相关概念**:[[Metadata-Management]]、[[Raft]]、[[Distributed-Transaction]]
- **同类系统**:Tectonic、LocoFS、InfiniFS、CFS
- **同会议**:[[SOSP-2025]]
