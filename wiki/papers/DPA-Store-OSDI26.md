---
type: paper
name: DPA-Store
full_title: "DPA-Store: An Ordered Network Data Path Key-Value Store"
authors: [Frederic Schimmelpfennig, Jan Sass, Reza Salkhordeh, Martin Kröning, Stefan Lankes, et al.]
venue: OSDI
year: 2026
tags: [key-value-store, smartnic, learned-index]
source_pdf: "[[osdi26-schimmelpfennig.pdf]]"
source_md: "[[osdi26-schimmelpfennig]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 网络数据路径上的有序键值存储
> **原题**：DPA-Store: An Ordered Network Data Path Key-Value Store

## 问题与动机

远程内存 [[Key-Value-Store|KV store]] 需要点查和 range query：host-based 系统受内核栈与 [[PCIe|PCIe]] 限制，hash-based SmartNIC offload 不支持范围查询，[[RDMA|RDMA]] tree 又把地址与索引状态推给 client。目标是在无状态 client 下兼顾有序语义和网络路径性能。

## 关键观察 / 隐含假设

- BlueField-3 DPA 可直接从 NIC buffer 取请求，并在片上遍历紧凑 learned index。
- 高频轻量 traversal 适合 DPA，结构变化等重操作适合 host。
- 假设 key distribution 能由有界误差模型有效近似，值可留在 host replica。

## 核心方法

[[DPA-Store]] 在 DPA memory 中放置 lock-free learned-index tree；到 leaf 后从 host-side replica 取 value。写入先在 DPA 批量缓冲，结构更新交给 host，再以 transaction 方式 stitch 回 SmartNIC；NIC read cache 减少重复 DMA。

## 实验与结果

在 1 台 BlueField-3 server、6 台 client、100 Gb/s 网络和 5000 万 key dataset 上，DPA-Store 达到 33 MOPS GET 与 13 MOPS RANGE throughput；INSERT 最高 12.1 MOPS，相对有状态 RDMA baseline ROLEX 具有竞争力（§4，图 9–15）。边界是单节点 remote in-memory ordered KV workload。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| DPA 可承载有序索引快路径 | GET 达 33 MOPS | BlueField-3、单 server | 强 |
| range support 不必依赖有状态 client | RANGE 达 13 MOPS | 所测 dataset/queue depth | 强 |

## 批判性分析

### 论证链条
论文按计算性质拆分 DPA/host，并以复制、批处理与 transactional stitch 解决跨层一致性，直接回应 PCIe round-trip 与 DPA 容量约束。

### 假设压力测试
分布快速漂移、长 value、热点写入或跨节点扩展可能增加 retraining、DMA 与结构更新成本。

### 实验可信度
真实 SmartNIC、多 dataset 和 ROLEX 对比有说服力；单 NIC 平台且部分结果依赖硬件改进推演，跨代际泛化有限。

## 局限与后续工作

- 验证 scale-out sharding、故障恢复与 replication。
- 研究在线 model retraining 和 skewed mixed workload 的最坏尾延迟。

## 相关

- [[OSDI-2026]]
- [[SmartNIC]]
- [[Learned-Index]]
