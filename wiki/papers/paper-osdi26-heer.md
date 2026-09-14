---
type: paper
name: BALBOA
full_title: "RoCE BALBOA: Service-Enhanced RDMA Offload Engine for Data Center SmartNICs"
authors: [Maximilian Jakob Heer, Benjamin Ramhorst, Yu Zhu, Luhao Liu, Zhiyi Hu, Jonas Dann, Gustavo Alonso]
venue: OSDI
year: 2026
tags: [rdma, roce, smartnic, fpga, in-network-computing]
source_pdf: "[[osdi26-heer.pdf]]"
source_md: "[[osdi26-heer]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向数据中心 SmartNIC 的可扩展 RoCE RDMA 卸载引擎（OSDI 2026）

> **原题**：RoCE BALBOA: Service-Enhanced RDMA Offload Engine for Data Center SmartNICs

> **一句话总结**：商业 RNIC 把传输层做成不可修改的硬件黑盒，BALBOA 用可拆分的 FPGA 状态表、数据/控制分离流水线和 HBM 重传缓冲，在 Alveo U55C 上实现可与商业 NIC 互通的 100 Gbps RoCEv2 RC 子集，同时让 AES、DPI 和 RDMA-to-GPU 预处理能够进入线速数据路径。

## 问题与动机

RDMA 已用于内存解聚、键值服务和分布式训练，但商业 RNIC 的传输逻辑固定在 ASIC 中。研究者无法直接改造拥塞控制、重传、访问控制或数据包处理路径，只能把逻辑放回 CPU，或使用延迟较高的旁路协处理器。现有 FPGA 网络栈则常在协议完整性、交换机互通、100G 吞吐和 GPU DMA 之间取舍。

BALBOA 的目标是提供一个可用于真实数据中心网络研究的开放 RDMA 基础设施。作者选择实现 RoCEv2 Reliable Connection（RC）模式及 RDMA WRITE/READ 等常用单边操作，而不是覆盖全部 verbs，以控制实现范围，同时保留对重传、乱序检测、CRC 和交换机兼容性的支持。

## 关键观察 / 隐含假设

- **观察 1：协议合规和可扩展性并非必然冲突，瓶颈在状态访问与流水线组织。** 论文把 IP/UDP/InfiniBand 头处理拆成可流水化函数，并用 512-bit AXI4-Stream、250 MHz 时钟提供 128 Gbps 内部带宽（§4.2）。
  - **依赖假设**：HLS 生成的流水线能在目标 FPGA 上稳定完成 timing closure，且 100G 流量以足够大的批量到达。
  - **可能失效场景**：更高端口速率、复杂可变长扩展头或频繁 backpressure 可能重新暴露 HLS 的布线和时序成本。
- **观察 2：双向线速处理要求 RX/TX 共享连接状态但不能互相阻塞。** BALBOA 将 Connection、PSN、MSN 状态放入双口 BRAM，并将 READ 与 WRITE 数据流分开，再用独立仲裁器合并（§4.3–§4.4）。
  - **依赖假设**：默认工作负载以 RC 单边操作为主，QP 状态规模可以放入可扩展的 BRAM/HBM 组织。
  - **可能失效场景**：大量小消息、复杂双向竞争、QP 数远超默认 500，或需要更丰富的 verbs 时，仲裁和状态端口压力可能成为瓶颈。
- **假设 1：RoCEv2 的 Go-Back-N 重传窗口足以覆盖研究和部署需求。** 每个 flow 默认允许 16 个 outstanding packets，4K MTU 下重传缓存约 64 KB；论文没有评估选择性重传或严重拥塞下的效率。
- **假设 2：应用卸载能够保持非阻塞。** RX 路径上的处理一旦停顿就可能造成网络丢包，因此线速预处理必须 initiation interval 为 1；数据扩张操作还需要显式处理带宽和 backpressure（§5.3）。

## 核心方法

BALBOA 的核心是模块化 RoCEv2 数据面。每个协议头由独立的 HLS 函数处理，模块之间通过标准 AXI4-Stream 连接。数据、控制和 completion 三类流分离：数据路径保持连续传输，控制路径负责 QP/PSN 状态查找、命令同步和完成事件。这种组织既便于替换流控模块，也让应用逻辑可以插入包处理流水线。

状态架构将 RX 与 TX 对连接状态的访问解耦。发送的数据会在 HBM 中保留，直到远端确认，以支持 RC 所需的 Go-Back-N 重传。论文测得从发现需要重传到形成完整 MTU 包并送往 Ethernet 模块的总延迟为 1.86 µs，其中从 HBM 取回 payload 需 1.732 µs（§4.4）。

流控目前采用 ACK 驱动的固定滑动窗口。它被设计成独立模块，未来可以替换为 DCQCN、TIMELY 或其他拥塞控制算法。ICRC 校验则用针对 512-bit、320-bit 和 32-bit beat 的并行流水线实现，避免依赖慢速的预计算表（§4.5–§4.6）。

在协议增强方面，AES-CTR 作为数据面 bump-in-the-wire 模块插入，利用 QPN 与包计数器组合构造 IV；ML-DPI 则复制数据到并行路径，识别恶意可执行文件，并将结果反馈给 BTH 处理阶段。应用卸载通过 AXI 数据/控制接口接入，论文展示了 Neg2Zero、Logarithm 和 Modulus 三个推荐模型预处理算子，并使用 RDMA-to-GPU DMA 绕过主机内存。

## 设计取舍

- **取舍 1：只实现 RC 单边操作。** 这覆盖常见数据中心使用方式并降低开发量，但不能代表完整 RoCEv2 能力；UC、多种双边 verbs 和更复杂可靠性策略仍需扩展。
- **取舍 2：用 HBM 保存重传 payload。** HBM 提供容量和带宽，避免再次从主机经 PCIe 取数，但重传延迟受 HBM 和 FPGA 互连限制，且占用外部内存带宽。
- **取舍 3：把 RX 卸载约束为 non-stalling。** 该约束保护线速和交换机互通，却限制了需要数据扩张、随机访存或可变执行时间的服务。
- **边界条件**：开放接口适合硬件协议研究和固定流水线算子；对动态策略、复杂软件状态或强隔离的多租户服务，论文没有给出运行时资源管理和故障恢复机制。

## 实验与结果

- 在 Alveo U55C、ConnectX-5/7、CISCO Nexus 9000 交换机组成的 100G 集群中，BALBOA 与商业 NIC 均在 RDMA WRITE 的 32 KB 缓冲区附近达到 100G 饱和；小消息延迟略高于 ASIC，但 P95 尾延迟稳定（图 4）。
- RDMA READ 在中等缓冲区下略落后于商业 ASIC，原因是 FPGA 250 MHz 的 PCIe 请求发布和追踪能力较弱；较大缓冲区仍可达到线速（图 4c）。
- 多 QP 实验显示，数百个 QP 交错发送时，仲裁器能公平分配带宽并保持聚合吞吐饱和（图 5）。
- AES-CTR 数据面实现增加 11 个时钟周期、约 44 ns 延迟并保持 100 Gbps；同一功能在 16 核 EPYC 7302P 上只能达到 100G 的小部分（图 6）。
- DPI 模型对完整 payload 的可执行文件检测率为 97.83%，对部分嵌入的可执行文件为 89.35%；44 ns/AXI beat 的推理延迟被并行包处理流水线隐藏，吞吐和端到端延迟未见下降（图 7）。
- 基础栈占 U55C 的 3.4% LUT、5.1% BRAM，启用 AES 和 DPI 后 LUT 仍低于 12.15%，估算功耗为 1.745 W（表 3）。与同条件 Limago 100G TCP 栈相比，LUT 少 18%，但 FF 和 BRAM 更多。
- RDMA-to-GPU 预处理在受 PCIe switch 限制的 70 Gbps 链路上达到 8500 MB/s，而最多 8 个 CPU 核的预处理为 1190 MB/s；直接写 GPU 相比经过主机内存额外节省约 20–135 µs（图 9–10）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 开放 FPGA RDMA 栈可以在交换网络中达到 100G 并与商业 RNIC 互通 | §6.1，图 4 | U55C、100G、4K MTU、单层和两层交换拓扑；主要覆盖 RC 单边操作 | 强 |
| 解耦状态和流能同时支持双向吞吐与多 QP 扩展 | §4.3–§4.5，图 5 | 默认最多 500 QP，测试为交错批量流；未覆盖极端小消息和更大 QP 数 | 中 |
| 数据面服务可在线速执行而不增加端到端瓶颈 | §5.2，图 6–7 | AES-CTR 与特定 ternary DPI 模型；模型准确率和安全策略不等于完整访问控制 | 中 |
| FPGA 数据面预处理能消除 CPU 预处理瓶颈 | §8.2，图 9–10 | DLRM 三个无状态算子，MI210，FPGA-GPU PCIe 路径上限 70 Gbps | 中 |

## 批判性分析

### 论证链条

论文的主要链条是闭合的：固定 RNIC 限制协议研究，BALBOA 将状态、流水线和服务接口开放；硬件测量证明基本 RoCE 数据面达到线速，案例证明开放接口能承载安全和应用逻辑。较大的跳步是从两个协议增强和一个 DLRM 管线推到“任意”网络或应用卸载。论文只证明了固定、流式、易流水化算子的可行性。

### 假设压力测试

RDMA READ 的中等消息吞吐已经暴露了 FPGA PCIe 请求发布能力的边界。类似问题可能出现在需要大量主机交互的服务中。DPI 只对有限 payload 类别和离线训练模型评测，模型漂移、对抗 payload、误报后的隔离路径均未测量。500 QP 是设计默认值，不是大规模生产 trace 的结果；HBM 容量推算到 500,000 QP 也没有对应的仲裁、状态访问和 PCIe 压力实验。

### 实验可信度

实验包含商业 RNIC、真实交换机、异构 FPGA/RNIC 连接和 P95 延迟，足以支撑“可互通的研究平台”这一较窄结论。基线覆盖 ConnectX-5/7 和 CPU 软件实现，但没有与可编程 DPU 的同等 per-flow 加密路径进行可复现比较。应用案例受 PCIe switch 的 70 Gbps 上限影响，因而不能直接说明更高 GPU 链路上的收益。

### 系统性缺陷

开放硬件带来了编译、综合、部署和版本管理成本。论文展示了仿真框架和 traffic sniffer，但未讨论服务之间的资源隔离、运行时重配置期间的连接语义、故障恢复、密钥管理、DPI 模型更新或多租户安全边界。AES-CTR 的 IV 构造解决了包级同步问题，却没有构造完整的认证加密方案；仅加密 payload 也不能防止元数据泄露或篡改。

## 局限与后续工作

- **局限 1**：RoCEv2 支持集中在 RC 和单边 WRITE/READ，完整 verbs、UC 和更复杂的可靠传输尚未验证。
- **局限 2**：当前流控是固定窗口 ACK 机制；拥塞控制替换接口已预留，但 DCQCN、RTT 驱动或 ML 拥塞控制没有硬件实验。
- **局限 3**：RDMA-to-GPU 案例仅使用三个无状态预处理算子，且测量受到 70 Gbps PCIe switch 限制。
- **后续工作 1**：在真实训练 trace 上比较 BALBOA、CPU、DPU 和 GPU kernel preprocessing，分别报告 P99 延迟、功耗、GPU 利用率和 PCIe 链路占用。
- **后续工作 2**：实现可验证的认证加密与密钥轮换，并测量丢包、重排序和多租户场景下的正确性与隔离开销。
- **后续工作 3**：将可替换拥塞控制和选择性重传部署到交换机网络，测量 100G/200G 多层拓扑中的公平性、收敛时间和尾延迟。

## 相关

- **相关概念**：[[RDMA]]、[[SmartNIC]]、[[In-Network Computing]]、[[GPU Direct RDMA]]
- **同类系统**：[[Corundum]]、[[Limago]]、[[Coyote]]、[[StRoM]]
- **同会议**：[[OSDI-2026]]
- **对比**：[[BALBOA-vs-Limago]]
