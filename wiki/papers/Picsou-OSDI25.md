---
type: paper
name: Picsou
full_title: "Picsou: Enabling Replicated State Machines to Communicate Efficiently"
authors: [Reginald Frank, Micah Murray, Chawinphat Tankuranand, Junseo Yoo, Ethan Xu, Natacha Crooks, Suyash Gupta, Manos Kapritsos]
venue: OSDI
year: 2025
tags: [consensus, replicated-state-machine, byzantine-fault-tolerance, cross-cluster, blockchain]
source_pdf: "[[osdi25-frank.pdf]]"
source_md: "[[osdi25-frank]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Picsou：使复制状态机能够高效通信（OSDI 2025）

> **原题**：Picsou: Enabling Replicated State Machines to Communicate Efficiently

> **一句话总结**：Picsou 提出 C3B 原语与 QUACK（quorum cumulative ACK）；在无故障常态下以单次发送和常数额外计数器实现跨 RSM 通信。其性能结果依赖于所测协议、网络和 RSM 配置。

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
- **边界条件**：Byzantine 仍可迫使延迟上升；无故障的单次发送结论不覆盖重传和 φ-list 元数据。

## 实验与结果

**指标、基线与边界**：C3B throughput；Picsou vs ATA/OTU/LL/Kafka；File RSM、GCP、4–19 replicas/RSM、0.1 kB 或 1 MB message（§6.1，Fig.7）。

- 无故障 File-RSM 微基准中，vs ATA：每 RSM 4 replicas 时为 **2.5×**（0.1 kB）和 **3.2×**（1 MB），19 replicas 时为 **6.6×** 和 **12.1×**（§6.1，Fig.7）。
- US-West 至 Hong Kong 的 geo-replication（170 Mbit/s、133 ms RTT、1 MB）中，vs ATA 为 **12×**（n=4）至 **44×**（n=19）（§6.1，Fig.8(ii)）。
- 5-replica Etcd DR 中，Picsou 使约 **70 MB/s** 的 Raft disk goodput 饱和；该配置下 ATA 受 **50 MB/s** 跨区链路限制（§6.3，Fig.10(i)）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| 无故障微基准的 C3B throughput 随 RSM 规模扩大而优于 ATA | 4 replicas 为 2.5×/3.2×，19 replicas 为 6.6×/12.1× | File RSM、无 failures、0.1 kB/1 MB、4–19 replicas/RSM | §6.1，Fig.7 | high |
| 特定跨区配置下的收益高于 ATA | 12×（n=4）与 44×（n=19） | US-West↔Hong Kong、170 Mbit/s、133 ms RTT、1 MB | §6.1，Fig.8(ii) | high |
| crash 注入会降低 throughput，但仍优于若干协议 | 每 RSM crash 33% 时下降 22.8%–30.5%，仍比 ATA/OTU/LL 高至少 2× 至 8.9× | 1 MB、φ-list 256、受控 crash 注入 | §6.2，Fig.9(i) | high |
| Etcd DR 受 Raft disk goodput 而非单一跨区链路限制 | 5 条 50 MB/s 通路使约 70 MB/s disk goodput 饱和 | 5-replica/RSM、put transactions、单向 DR；vs ATA/OST | §6.3，Fig.10(i) | high |
| 异构 bridge 的吞吐损失受限于被测配置 | Algorand→ResilientDB 为 135 blocks/s；最坏吞吐下降少于 15% | 论文实现的 Algorand/PBFT ResilientDB bridge，不泛化到任意实现 | §6.3 | high |

## 批判性分析

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

## 局限与后续工作

- **局限 1**：强有序/全副本交付非原生。
- **局限 2**：WAN 极端分区下的运维 playbook 简略。
- **Future work 1**：与 disaster recovery 策略自动编排集成。
- **Future work 2**：量化 stake 变化时 QUACK 正确性测试覆盖。

## 相关

- **相关概念**：[[RDMA]]（对比 WAN 传输成本语境）
- **同类系统**：Kafka、etcd、PBFT、Raft、Algorand
- **同会议**：[[OSDI-2025]]
