---
type: paper
name: Picsou
full_title: "Picsou: Enabling Replicated State Machines to Communicate Efficiently"
authors: [Reginald Frank, Micah Murray, Chawinphat Tankuranand, Junseo Yoo, Ethan Xu, et al.]
venue: OSDI
year: 2025
tags: [consensus, replicated-state-machine, byzantine-fault-tolerance, cross-cluster, blockchain]
source_pdf: "[[osdi25-frank.pdf]]"
source_md: "[[osdi25-frank]]"
---

# Picsou: Enabling Replicated State Machines to Communicate Efficiently (OSDI 2025)

> **一句话总结**：Picsou 提出 C3B 原语与 QUACK（quorum cumulative ACK），让 Raft/PBFT/Algorand 等异构 RSM 在 WAN 上无故障时每消息常数元数据、单次发送，微基准比 all-to-all 最高 **24×**，Etcd DR 等应用比 Kafka **2×**。

## 问题与动机

跨组织/跨集群的 RSM（etcd 灾备、政府数据对账、区块链互操作）需要 **高效可靠跨 log 通信**。Kafka 依赖第三方 RSM；all-to-all broadcast 在 WAN 上带宽成本极高。需求：形式化保证、故障鲁棒、常见情况低开销、CFT/BFT/PoS 通用。

## 关键观察 / 隐含假设

- **观察 1**：C3B 只需保证「发送方 transmit 后接收方至少一个 correct replica deliver」，不必 all-replica 送达——应用可在接收 RSM 内再广播/共识强化。
  - **依赖假设**：应用能验证 commit 证明（quorum 签名）；跨 RSM 有序性由应用层按需加强。
  - **可能失效场景**：需要严格全局有序跨集群流且不愿二次共识。
- **观察 2**：TCP 式 cumulative ACK + 全双工可移植到 many-to-many，但需 **QUACK** 防 Byzantine 诱发虚假重传。
  - **依赖假设**：UpRight 故障模型统一 commission/omission；stake 用 apportionment 数学。
  - **证据强度**：强——PBFT/Raft/Algorand 互操作实验。
- **假设 1**：leader-to-leader 单播在同步期足够，丢包靠 QUACK 重复检测触发选择性重传。
  - **证据强度**：中——failure 实验有，但 WAN 长期分区行为需运维验证。

## 核心方法

**C3B**：Eventual Delivery + Integrity；transmit/deliver 为 RSM 级原语。

**Picsou**：round-robin 分区发送、轮换 receiver；消息带 ⟨m,k,k'⟩ 与 quorum 证明；receiver 验证后 RSM 内广播；**QUACK** 累积确认已收到序列，重复 QUACK 暗示丢包；常数大小丢失位图支持并行恢复多 gap。

支持 reconfiguration 与 stake-weighted quorum。

## 设计取舍

- **取舍 1**：异步网络，不假设同步；换 generality。
- **取舍 2**：C3B 最小交付语义，换协议简单；有序/全副本由上层付费。
- **边界条件**：Byzantine 仍可迫使延迟上升，但不应无限 spurious resend（设计目标）。

## 实验与结果

- 微基准（consensus 非瓶颈）：vs all-to-all **3.2×**（4 节点）至 **24×**（19 节点）。
- Etcd DR、数据对账：vs Kafka **2×**。
- PBFT、Raft、Algorand 跨协议互通成功。

## Critical Analysis

### 论证链条

RSM 互操作需求 → C3B 形式化 → TCP 思想 + QUACK 适应 BFT → 微基准与应用验证。链条在评测拓扑闭合；超大规模 WAN 带宽计费未量化。

### 假设压力测试

- 接收方仅单 replica deliver 时，该 replica 崩溃需应用层处理冗余。
- 高吞吐流 QUACK 频率与 piggyback 开销可能上升。
- 与 Kafka 对比场景是否均摊了 Kafka 运维复杂度公平存疑。

### 实验可信度

多协议+真实应用案例好；缺与专用 replication 产品长期稳定性对比。

### 系统性缺陷

论文未讨论：跨域合规审计、消息过滤策略误配、QUACK 状态 GC 与内存上限。

## 局限与 Future Work

- **局限 1**：强有序/全副本交付非原生。
- **局限 2**：WAN 极端分区下的运维 playbook 简略。
- **Future work 1**：与 disaster recovery 策略自动编排集成。
- **Future work 2**：量化 stake 变化时 QUACK 正确性测试覆盖。

## 相关

- **相关概念**：[[RDMA]]（对比 WAN 传输成本语境）
- **同类系统**：Kafka、etcd、PBFT、Raft、Algorand
- **同会议**：[[OSDI-2025]]