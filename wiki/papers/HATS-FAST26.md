---
type: paper
name: HATS
full_title: "Holistic and Automated Task Scheduling for Distributed LSM-tree-based Storage"
authors: [Yuanming Ren, Siyuan Sheng, Zhang Cao, Yongkun Li, Patrick P. C. Lee]
venue: FAST
year: 2026
tags: [lsm-tree, kv-store, cassandra, load-balancing, compaction, tail-latency]
source_pdf: "[[fast2026-ren.pdf]]"
source_md: "[[fast2026-ren]]"
---

# Holistic and Automated Task Scheduling for Distributed LSM-tree-based Storage (FAST 2026)

> **一句话总结**：通过 coarse-grained 跨节点 read 分配 + fine-grained replica selection + 按读热度调控 compaction rate 的闭环调度，HATS 在 [[Cassandra]] v5.0 上把 YCSB 读密集 P99 延迟降低 **58.6%-59.9%**、吞吐 **2.41-2.90×**（vs C3 / DEPART），Facebook 真实负载 Get P99 降 78.9%/68.3%。

## 问题

[[LSM-Tree]]-based 分布式 KV（如 [[Cassandra]]）下 latency 抖动严重，根因有二：

1. **Latency 不平衡**：即使副本均匀分配请求，节点延迟仍可能差 4.24×；秒级窗口内 90.8% 时间偏离平均 0.5-2× 范围
2. **Read 与 compaction 紧耦合**：compaction 关闭时 read throughput 26.3→7.3 KOPS（差 3.6×），但若长期不 compact 又因层数过多读放大严重——必须共调度

C3、DEPART 等只处理 distribution 层 replica selection，没把 storage 层的 background task 算进来；纯资源指标也无法预测请求级延迟。

## 核心方法

闭环三步：

- **Coarse-grained Read Task Assignment**：扩展 Cassandra Gossip 协议，每 epoch（默认 60s 与 compaction 周期对齐）由一个 Raft 选举出的 scheduler node 收集各节点平均 read latency 与请求计数，构造 current state matrix，按 `L/Ti` 分类 high-load/low-load 节点，贪心从 high 转移到 low 形成 expected state，再 Gossip 散播。
- **Fine-grained Read Task Coordination**：coordinator 用 unified score `L/t_{i,j} - Q_{i+j}` 衡量副本节点的瞬时余量（结合 dynamic snitching EWMA 测量的瞬时延迟），把请求路由到 score 最高的副本，避免选最快副本带来的 oscillation。
- **Compaction Task Scheduling**：基于 [[DEPART]] 的 replica decoupling 把每个节点的 R 个副本拆成 R 个独立 LSM-tree；按 `E_{i,j}/Q_i` 的读比例分配 compaction rate（默认总 64MiB/s），最低层 compaction 不限速。设最低速率防止 write-heavy key range 饥饿。

实现：6K LoC 改 Cassandra v5.0；用产品级 Raft 库选 scheduler node。

## 关键结果

- YCSB 读重负载（B/C/D）throughput **2.41-2.90×**，P99 降低 **58.6-59.9%**（vs C3、DEPART）
- Facebook 生产负载：Get 平均/P99 latency 降低最高 68.0%/83.2%；总吞吐 **2.85×** vs mLSM
- 节点间 latency CoV 从 0.40 降到 0.11（Workload C），秒级窗口外偏率从 91.6% 降到 8.7%
- 写密集 Workload A 也获得 1.53× 吞吐，反驳「HATS 只对读有用」的质疑

## 相关

- **相关概念**：[[LSM-Tree]]、[[Compaction]]、[[Replica-Selection]]、[[Tail-Latency]]、[[Gossip]]、[[Raft]]
- **同类系统**：[[Cassandra]]、[[DEPART]]、[[C3]]、[[mLSM]]、[[ScyllaDB]]、[[TiKV]]
- **同会议**：[[FAST-2026]]
