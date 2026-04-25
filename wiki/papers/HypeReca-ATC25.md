---
type: paper
name: HypeReca
full_title: "HypeReca: Distributed Heterogeneous In-Memory Embedding Database for Training Recommender Models"
authors: [Jiaao He, Shengqi Chen, Kezhao Huang, Jidong Zhai]
venue: ATC
year: 2025
tags: [recommender-system, embedding-table, dlrm, distributed-training, kv-store]
source_pdf: "[[atc2025-he-jiaao.pdf]]"
source_md: "[[atc2025-he-jiaao]]"
---

# HypeReca: Distributed Heterogeneous In-Memory Embedding Database for Training Recommender Models (ATC 2025)

> **一句话总结**：把 [[DLRM]] 训练里的 embedding table 抽象成分布式异构 in-memory KV 库，用去中心索引 + 2-fold parallel 复制热点 item，32 GPU 上相比 HugeCTR/TorchRec/TFDE 端到端 2.16–16.8× 加速。

## 问题

DLRM（推荐模型）embedding table 上千亿参数，传统做法把 embedding 切到多机 host memory + dense 部分 GPU 数据并行，每 batch 之间靠 all-to-all 交换 embedding vector。NVIDIA 在 MLPerf DLRM 排行榜上从 8 到 112 GPU 仅加速 2.89×，沟通成为瓶颈。已有跨 table 的混合并行只能 table 粒度复制，错过了 item 内的 skewness。直接 RDMA 一对一拉 embedding vector（~500B）带宽利用率不到 10%。

## 核心方法

把 embedding 抽象成 KV 数据库（Prefetch / Pull / Push / Update 接口），由两条主线优化：

1. **去中心化索引（DIT）+ 异步并行 pipeline**：embedding vector 按 chunk 分块，每个 process 持有索引哈希表的一部分（按 ID 末几位分片）。索引和实际 embedding lookup 解耦，把索引塞进 data loader 线程异步做。多线程访问 hash table 时按 shard 切片成 pipeline，单 lock 一次跑完整 shard 内所有 ID，吃掉锁竞争——32 CPU 线程能匹配 8 GPU 索引吞吐。fetch 时 receiver 先在本地把一批 embedding 聚到连续 buffer 再 send，避开小请求 RDMA 的瓶颈。
2. **2-Fold Parallelism (2FP)**：peep 100 个 batch 拿到 item 频率分布——Criteo Kaggle 上 2.2% 热门 item 占 90%+ 访问，Taobao 上 13% 占 86%。把这部分热门 item 单独放进 GPU 上的 R chunk **数据并行**（all-reduce 同步），其余 item 在 host memory 模型并行（all-to-all）。建 latency 性能模型 $L = \mathbb{R} C_{ar} + N(1-\rho(\mathbb{R})) C_{a2a}$，三分查找最优 R 大小。32 GPU 上理论 all-to-all 减 92%，整体通信延迟降 9.2× / 5.2×。

无需修改训练算法，强一致；同时去掉了 deduplication 步骤（重复 item 都在 R 里）。

## 关键结果

- 32 GPU 跨 4 节点 + commodity Infiniband，相比 HugeCTR / TorchRec / TFDE 端到端 2.16–16.8× 加速，模型质量保持一致。
- Criteo / Taobao 数据集均显著受益；batch size 越大、R 越值得加大。
- DIT pipeline 在 8 GPU 节点 32 线程下索引吞吐能跟上 GPU 计算速度（159k items/10ms × 8 GPU）。

## 相关

- **相关概念**：[[DLRM]]、embedding-table、all-to-all、[[RDMA]]、data-parallelism
- **同类系统**：HugeCTR、TorchRec、TFDE、GSET、Persia
- **同会议**：[[ATC-2025]]
