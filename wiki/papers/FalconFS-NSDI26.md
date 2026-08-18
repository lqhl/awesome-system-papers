---
type: paper
name: FalconFS
full_title: "FalconFS: Distributed File System for Large-Scale Deep Learning Pipeline"
authors: [Jingwei Xu, Junbin Kang, Mingkai Dong, Mingyu Liu, Lu Zhang, et al.]
venue: NSDI
year: 2026
tags: [distributed-file-system, deep-learning, metadata, stateless-client, small-files, area/storage-systems]
source_pdf: "[[nsdi2026-xu-jingwei.pdf]]"
source_md: "[[nsdi2026-xu-jingwei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# FalconFS：面向大规模深度学习流水线的分布式文件系统（NSDI 2026）

> **原题**：FalconFS: Distributed File System for Large-Scale Deep Learning Pipeline

> **一句话总结**：自动驾驶 DL pipeline 会随机遍历数百 PB、3000 亿小文件，使 client metadata cache 既昂贵又低命中；FalconFS 反而采用无状态客户端，把 path resolution 移到 server，以 hybrid indexing、lazy namespace replication 和 request merging 实现常见操作 one-hop，在 10,000 NPU 生产集群运行一年，训练吞吐比 CephFS/Lustre 最高高 11.81/1.23 倍。

## 问题与动机

传统 DFS 用 client-side inode/dentry cache 减少 path walk，但 DL training 每个 epoch 随机访问每个文件一次，目录 working set 可达十亿级。在 1,000 clients 上只缓存十亿目录的 10%，按 Linux VFS 每目录 800 bytes 计算也要总计 80 TiB，仍会因末级目录 miss 产生 request amplification。

labeling pipeline 又以目录为批次 burst 访问；把同一目录的 inode 共置会瞬间压垮单个 metadata server。FalconFS 因此挑战“client cache 必然提高 DFS 性能”这一传统假设。

## 关键观察 / 隐含假设

- **观察 1**：DL training 是 massive-directory random traversal，client cache hit 与容量近似成正比；10%→100% cache 才获得 1.46 倍 throughput（§2.3）。
  - **依赖假设**：dataset 以大量独立小文件和 epoch traversal 组织；packing/sharding 数据会改变瓶颈。
- **观察 2**：DL cluster client:metadata-server 比超过 40:1，共享 server-side dentry 比每个 client 重复缓存更省；自定义 entry 少于 100 B，而 VFS 约 800 B（§3）。
- **观察 3**：多数 dataset 文件名散列已足够均衡，只有 Linux/FSL 等重复热 filename 需要少量 path-walk exception（§6.6）。
- **假设 1**：namespace 比 file inode 小，适合复制到所有 metadata server；极高目录更新率或超大 namespace 会放大同步成本。

## 核心方法

FalconFS 采用 **stateless-client architecture**：client 直接发送完整 path，不保留 metadata cache；server 本地完成 path resolution。VFS shortcut 绕开本地 dentry/inode path walk，同时保留 POSIX-like interface。

**Hybrid metadata indexing**默认按 filename hash 定位 inode，使同目录文件分散；对高频冲突 filename 用 exception table 切换到 path-walk redirection，避免 full-path hashing 导致整个 subtree rename。

**Lazy namespace replication**把目录树复制到所有 metadata server，常见 path 可本地验证；更新通过 invalidation-based synchronization 延迟传播。**Concurrent request merging**合并 WAL 和相同路径请求，提高 server concurrency，但增加单请求 latency。

## 设计取舍

- **取舍 1**：删除 client cache 换 one-hop 和低 client memory，代价是 metadata server 保存 replicated namespace。
- **取舍 2**：batch/merge 换 peak throughput，低并发时 latency 高于 Lustre；rmdir 需广播并等待最慢 server。
- **边界条件**：目标是小文件/metadata-bound DL pipeline，不替代针对大文件 data path 优化的 3FS；FUSE prototype 单 client concurrency 受限，部分评测改用 LibFS。

## 实验与结果

- 生产 workload：数百 PB、超过 3000 亿小文件、十亿目录；系统已在华为 10,000 NPU 自动驾驶集群运行一年（§1–2）。
- 小于等于 64 KiB 文件，吞吐比 CephFS 高 7.35–21.23 倍、比 JuiceFS 高 2.94–23.53 倍、比 Lustre 高 1.12–1.85 倍；大文件最终受 43/16 GiB/s SSD read/write bandwidth 限制（图 13）。
- 100M 文件随机 traversal 下，相比 CephFS/Lustre 吞吐高 2.92–4.72/2.08–3.34 倍，请求数减少且不随 client cache budget 变化（图 14）。
- 去掉 invalidation 后 mkdir throughput 降 86.9%；再去掉 request merging 额外降 91.8%（图 16）。
- MLPerf Storage、10M×112 KiB 文件中，90% accelerator utilization 下 FalconFS 支撑 80 GPU，Lustre 32 GPU；80–128 GPU 时训练吞吐比 CephFS/Lustre 高 11.09–11.81/0.99–1.23 倍（图 18）。
- labeling trace replay runtime 比其他 DFS 降 23.8–86.4%；rmdir 和 two-hop corner case 仍分别受广播与 36.8–49.6% throughput loss 影响（图 16–17）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| client cache 对随机 DL traversal 是负担 | 图 2、14：cache budget 与请求放大/吞吐 | 小文件目录树 | 强 |
| stateless client 可显著提升训练 I/O | 图 18：CephFS/Lustre 与 80–128 GPU | MLPerf Storage ResNet-50 | 强 |
| 设计具有生产可用性 | 10,000 NPU、运行一年 | 华为自动驾驶单一部署域 | 中强 |

## 批判性分析

### 论证链条

论文从生产 trace 提出与传统 cache wisdom 相反的 observation，再用 NoBypass、no-invalidation、no-merge 三层消融支持设计。工作负载—抽象—机制—端到端训练证据闭合较好。

### 假设压力测试

若 dataset 被 WebDataset/Parquet 等大对象打包，metadata 不再是瓶颈；若 namespace 更新频繁、rename/rmdir 密集，复制和广播的代价可能超过 client cache。通用 home/source-tree workload 只验证分布均衡，没有端到端性能。

### 实验可信度

CephFS、Lustre、JuiceFS baseline 和生产规模说明较充分，但 FalconFS 用 LibFS 绕过 FUSE concurrency bottleneck，部署可比性需谨慎；摘要中的 small-file 5.72/12.81 倍与 prepublication 正文部分数字存在版本差异，本文采用最终正文细分结果。

### 系统性缺陷

metadata server 复制 namespace 带来内存与 reconfiguration 状态；rmdir cost 随 server 数增长。论文重点是 throughput，对权限缓存、复杂 POSIX rename、failure recovery tail 和跨地域部署讨论有限。

## 局限与后续工作

- **局限 1**：优化对象高度特定于 small-file DL pipeline，不能外推到 metadata locality 强或大文件 workload。
- **局限 2**：rmdir 广播、two-hop exception 和低并发 latency 是明确边界。
- **后续工作 1**：自动检测 dataset layout，在 stateless path 与 packed-object/direct data path 间切换。
- **后续工作 2**：测量 namespace size、update rate、MNode count 对 replica memory、invalidation tail 和 recovery time 的三维曲线。

## 相关

- **相关概念**：distributed file system、metadata caching、AI storage
- **同类系统**：[[AITurbo-FAST26]]、[[LiqSD-FAST25]]
