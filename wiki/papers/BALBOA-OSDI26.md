---
type: paper
name: BALBOA
full_title: "RoCE BALBOA: Service-Enhanced RDMA Offload Engine for Data Center SmartNICs"
authors: [Maximilian Jakob Heer, Benjamin Ramhorst, Yu Zhu, Luhao Liu, Zhiyi Hu, Jonas Dann, Gustavo Alonso]
venue: OSDI
year: 2026
tags: [rdma, smartnic, fpga, roce, in-network-computing]
source_pdf: "[[osdi26-heer.pdf]]"
source_md: "[[osdi26-heer]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向数据中心 SmartNIC 的服务增强 RDMA 卸载引擎（OSDI 2026）

> **原题**：RoCE BALBOA: Service-Enhanced RDMA Offload Engine for Data Center SmartNICs

> **一句话总结**：现有 commercial RNIC transport 不可改、research FPGA stack 又常缺 100G/交换机互通/完整可靠性；BALBOA 以 512-bit streaming pipeline、解耦 QP state、完整 ICRC/retransmission 和标准 AXI extension slot 实现开源 RoCEv2 100 Gbps stack，性能匹配 ConnectX，并以 line-rate AES/DPI 与 direct-to-GPU DLRM preprocessing 展示可编程性。

## 问题与动机

RDMA 已承担大量 cloud traffic，但 ConnectX/BlueField 等 NIC 的 RoCE transport、congestion control、access policy 基本是 fixed function。研究者若想加入 encryption、telemetry、custom retransmission 或 application preprocessing，只能在 host software/slow ARM core 实现，破坏低 latency/CPU bypass；已有 FPGA RDMA prototype 又常省略 ICRC、retransmission、switch compatibility、GPU DMA 或只支持少量 QP，无法作为真实 data center testbed。

BALBOA 的目标是同时满足 100G、RoCEv2 protocol adherence、低 FPGA resource 与 openness。它不是只跑 FPGA-to-FPGA 的简化 protocol，而要插入现有 RNIC/switch cluster，支持 hundreds of QPs、CPU/GPU DMA、packet loss/retransmission，并给 service logic 留时序和 LUT空间。

## 关键观察 / 隐含假设

- **观察 1**：100G 与 extensibility 并非必然冲突；将 IP/UDP/IB header、ICRC、retransmission、flow control 拆成独立 streaming stage，可用 deep pipeline 同时获得 timing closure 和可替换接口（§4.2–§4.3）。
  - **依赖假设**：extension 能保持 initiation interval 1 或通过 parallel metadata path 不阻塞 512-bit stream。
  - **可能失效场景**：variable-latency/stateful service、packet expansion 或随机 memory lookup 会产生 backpressure。
- **观察 2**：QP state 若由 RX/TX 共用单口 memory 会阻塞双向 line rate；Connection/PSN/MSN 分表放 dual-port BRAM 可让两个方向并行（§4.3）。
  - **依赖假设**：QP state fits on-chip BRAM；默认约 500 QP，规模增加会消耗稀缺资源或需外部 memory。
- **观察 3**：data 与 control/completion stream 分离，让 datapath 操作数据时 parallel path 更新 length/PSN/decision，service enhancement 不必重写整个 transport FSM（图 1）。
  - **依赖假设**：两条 stream 的 ordering 和 completion join 永远一致。
- **假设 1**：250 MHz×512-bit 提供 128 Gbps raw headroom 足以吸收 protocol gap 并维持 100G；未来 200G 可凭 400 MHz timing result迁移。
  - **证据强度**：100G hardware 已验证；200G 只是 synthesis/平台升级推断。

## 核心方法

BALBOA 在 Coyote v2/AMD Alveo U55C shell 上实现完整 bidirectional RoCEv2。RX/TX pipeline 以 AXI4-Stream 串接 IP、UDP、IB/BTH、ICRC、request/ACK/NAK、retransmission 和 arbitration，512-bit bus@250 MHz；header FSM 用 HLS 编写，模块可独立 simulation/替换（图 1、§4）。

QP 的 connection、packet sequence number、message sequence number 保存在 dual-port BRAM；shared timer 检查 timeout。payload 与 command/state stream 分开，RX/TX 独立推进；retransmission buffer 把 command 与 data 生命周期解耦，并在 loss/reorder 中重发。ICRC pipeline 处理 RoCE 对 header field 的规范化和 streaming CRC，使 commercial RNIC/switch 能互通。

扩展 slot 分 on-path、parallel-path 与 application offload：AES-CTR 可在 payload path 加解密并同步修改 metadata；ML-based DPI 从 packet feature parallel inference/aggregate decision，用于 NIC-level access control；application slot 可在 RDMA-to-GPU 路径上做 Neg2Zero、Logarithm、Modulus 等 DLRM preprocessing（§5/§8）。

## 设计取舍

- **on-chip state 换规模**：BRAM 保证 deterministic line rate，但默认 500 QP 与 cloud RNIC 的大规模 connection capacity 仍有差距。
- **HLS 可维护性换细粒度控制**：更容易添加 service，却可能比 hand RTL 用更多 FF/BRAM，并依赖工具 version/timing。
- **line-rate slot 换 service expressiveness**：只适合 streaming/bounded-latency operator；复杂 control plane 仍需 host/soft core。
- **open FPGA 换成本/功耗/部署**：相对 ASIC 可修改，但 FPGA NIC 并不是普通 server 的默认配置。
- **安全边界**：AES-CTR 展示 confidentiality datapath，不等于完整 key exchange、replay protection、tenant policy 和 authenticated encryption。

## 实验与结果

- FPGA/RNIC/switch hardware cluster 中，BALBOA 与 commercial ConnectX-5/7 互通，单/多 QP 下达到 100 Gbps line rate，并支持 switched network、loss/retransmission；摘要报告 throughput/latency 匹配 commercial ASIC（§6.1–§6.2）。
- AES-CTR 与 ML-DPI 均能集成 transport pipeline 并维持 100G throughput；AES end-to-end pipeline latency 约 11 cycles，DPI 可在 line rate 对 traffic 分类（§6.3）。
- complete stack 支持默认 500 QPs；相同 U55C/500-flow 条件下 LUT 比开源 100G TCP stack Limago 少 18%，但 FF 为 102,988 vs 72,974、BRAM 为 101 vs 约 78 BRAM36-equivalent（§7）。
- DLRM preprocessing testbed 为 Alveo U55C、AMD MI210、EPYC 7V13，FPGA→GPU [[PCIe|PCIe]] switch 上限约 70 Gbps/8500 MB/s（§8.2）。
- CPU vanilla preprocessing 即使用 8 cores 也只有 1190 MB/s，BALBOA on-datapath/direct-to-GPU 达 8500 MB/s，约 7.1× throughput；绕过 CPU staging 节省约 20–135 μs latency（图 9/10）。
- 完整 design 在最高约 400 MHz 可通过 synthesis timing，作者据此给出未来 200G upgrade path，但未在 200G hardware 上运行（§4.2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 开源 FPGA RoCE stack 可与 commercial RNIC/switch 100G 互通 | §6.1–§6.2 | U55C、ConnectX-5/7、100G switched cluster | 强 |
| transport pipeline 可加入 service 而不丢 line rate | §6.3 | AES-CTR 与一项 ML-DPI implementation | 强 |
| 架构给 application offload 留出可用 FPGA resource | §7、表 3 | U55C、默认 500 QP；与 Limago resource 对比 | 中 |
| on-path preprocessing 显著优于 CPU staging | 图 9/10 | 三个 DLRM operator、MI210、PCIe 上限 70G | 强 |
| 可平滑升级到 200G | §4.2 | 400 MHz synthesis timing，无 200G end-to-end hardware | 弱 |

## 批判性分析

### 论证链条

论文把 research stack 的现实缺口定义为“性能、合规、可扩展三者缺一”，再通过真实 RNIC/switch 互通与 service case 证明，主张比只报 FPGA loopback 更强。AES、DPI、DLRM 三例说明 extension interface 不止纸面设计。但“matches commercial ASIC”主要针对 100G throughput/latency，不包含 connection scale、congestion ecosystem、reliability maturity 与 power。

### 假设压力测试

默认 500 QP 对实验足够，对多租户 cloud host 可能不足。扩大 BRAM state、retransmission buffer 与 timer 会影响 routing/timing closure。100G line rate 在实验 traffic pattern 下成立；大量 small messages、bidirectional loss、ECMP reorder、PFC storm 与 QP churn 可能让 control path 而非 payload bus 成为瓶颈。

### 实验可信度

硬件互通、多 QP、encryption/DPI、resource 和 real application offload 维度齐全。缺少长时间 soak、随机 packet fault、congestion control、thousands-QP scale、power 与成本。DLRM case 只测三个 stateless operator，CPU baseline 1190 MB/s 是否使用最优 vectorization/GPU kernel preprocessing不明确。

### 系统性缺陷

开放 transport 将 protocol correctness 和 security责任交给研究者；extension 错误可能破坏 PSN/length/ICRC，且缺少 isolation/verifier。AES-CTR 无 authentication 可能受 bit-flipping/replay；key management未讨论。FPGA bitstream deployment、partial reconfiguration、tenant隔离与 rollback 是生产运维主要风险，论文只展示开发接口。

## 局限与后续工作

- **局限 1**：500-QP 默认规模、100G 单端口与 U55C resource 不能代表 hyperscale ASIC RNIC。
- **局限 2**：没有完整 congestion control、security key lifecycle 与 multi-tenant isolation evaluation。
- **局限 3**：200G 只通过 timing推断，未做硬件/PCIe端到端验证。
- **后续工作 1**：在 500→100k QP、不同 message size、loss/reorder/PFC 下测 line rate、tail latency、BRAM/HBM 与 retransmission correctness。
- **后续工作 2**：实现 AEAD、key rotation 和 replay window，并验证 service metadata 与 ICRC/PSN 的组合正确性。
- **后续工作 3**：以 200/400G FPGA、GPU direct 与 programmable congestion control 做跨交换机长时 soak，对比 ConnectX 的功耗/性能/故障率。

## 相关

- **相关概念**：[[RDMA]]、[[RoCEv2]]、[[SmartNIC]]、[[FPGA]]、[[In-Network-Computing]]
- **同类系统**：[[StRoM]]、[[ConnectX]]、[[BlueField]]、[[Limago]]
- **同会议**：[[OSDI-2026]]
