---
type: paper
name: UCCL-Tran
full_title: "UCCL-Tran: An Extensible Software Transport Layer for GPU Networking"
authors: [Yang Zhou, Zhongjie Chen, Ziming Mao, ChonLam Lao, Shuo Yang, Pravein Govindan Kannan, Xizhi Zhang, Jiaqi Gao, Yilong Zhao, Yongji Wu, Kaichao You, Fengyuan Ren, Zhiying Xu, Costin Raiciu, Ion Stoica]
venue: OSDI
year: 2026
tags: [gpu-networking, rdma, software-transport, multipath, collective-communication]
source_pdf: "[[osdi26-zhou-yang.pdf]]"
source_md: "[[osdi26-zhou-yang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向 GPU 网络的可扩展软件传输层（OSDI 2026）

> **原题**：UCCL-Tran: An Extensible Software Transport Layer for GPU Networking

> **一句话总结**：论文观察到 ML 通信以大块数据为主，而且 GPU 服务器常有可预留的 CPU core，因此 UCCL-Tran 保留 NIC 的 GPUDirect 数据搬运，只把拥塞控制、路径选择和部分可靠性逻辑移到 host software；它在无拥塞实机上达到 ConnectX-7 的 collective 性能，在跨机架 flow collision 下把 all-to-all bus bandwidth 最多提高 4.54 倍，并把真实 DeepSeek-V2-Lite 训练吞吐最多提高 7.5%。

## 问题与动机

GPU 网络的应用需求变化很快：训练从 allreduce 扩展到 allgather、reduce-scatter，多级并行和 MoE all-to-all；serving 又出现 prefill/decode disaggregation 和瞬时 incast。可是 [[RDMA]] NIC 的拥塞控制（congestion control，CC）、可靠传输和单路径策略通常固化在 ASIC 或 firmware 中，硬件更新周期远慢于 workload。论文列举的实际后果包括：低 flow entropy 让 DCQCN 不适合大模型训练，单 connection 的单路径容易 collision，热点 expert 会形成短时 incast，go-back-N 在丢包后浪费带宽，不同厂商 NIC 的 control semantics 也不一致（§1–§2.2）。

把整个网络栈搬回 CPU 又会失去 RDMA 的关键价值。GPU server 可有 8 块 400 Gbps NIC，双向带宽合计 3.2 Tbps；若 CPU 逐 packet 搬 payload 或做每包决策，很快成为瓶颈。UCCL-Tran 因而把“软件传输”限定得很清楚：**payload 仍由 NIC datapath 在 GPU memory 与网络之间 DMA，host CPU 只处理小 control header 和 transport decision**。它不是用 CPU 或 simulator 替代 NIC 数据面。

系统还要面对 vendor capability 不一致。NVIDIA NIC 有 UC，可以关闭硬件 reliability/CC；Broadcom 只能用关闭 CC 的 RC，可靠性仍留在 NIC；AWS EFA 主要暴露 UD/SRD，没有 UC。论文的挑战不是设计一个只适配单卡的协议，而是利用这些现有 primitive 做一层可替换的 host transport，同时保持 bulk collective 的 line rate。

## 关键观察 / 隐含假设

- **观察 1：ML collective 的大 message 和 MTU-sized packet 能摊薄 QP context swap 与软件控制成本。** 在 16 块 400G NIC 的 CX_IB 实机上，把 RC QP 从每 NIC 60 个增至 60K 个，all-to-all bandwidth 只下降约 17%，UC 几乎不降；这与面向几十 byte CPU RPC 的既有 QP scalability 结论不同（图 6）。
  - **依赖假设**：主要数据是 1 MB–1 GB bulk transfer，GPUDirect 让 GPU–NIC payload 不穿过 CPU root complex。
  - **可能失效场景**：小 message、高 packet rate、CPU-based RPC 或无法使用 GPUDirect 时，QP fetch、MMIO 和 per-chunk control 更难摊薄。
- **观察 2：多路径的价值主要来自避免 flow collision，而不是让 NIC datapath 本身更快。** 同机架、基本无 congestion 的 CX_IB 上，UCCL-Tran UC/RC 与 ConnectX-7 几乎相同；跨机架 fat-tree 上，基于 per-path RTT 的动态选择才显著领先单路径或少量 QP（图 7、图 10、§6.1）。
  - **依赖假设**：交换网络用 QP number 或 UDP port 提供足够 ECMP entropy，且 path RTT 能在发送前反映 congestion。
  - **可能失效场景**：rail-optimized topology 已经隔离 collision、网络只有一条有效路径，或 ECMP hash/policy 不允许软件制造独立路径时，收益会缩小。
- **观察 3：transport control 不必逐 packet 执行。** 默认每 32 KB data chunk 做一次 CC、load balancing 和 reliability decision，实际 400G NIC 上一颗 CPU core 可跑满单向带宽；packet-level simulation 则显示这种 coalescing 对 sender-driven transport 可能带来 17.9% completion-time 损失（图 14、表 5）。
  - **依赖假设**：拥塞反应以 RTT 为时间尺度，32 KB 内的 packet 可以共享 control decision，host core 能独占运行而少受 interrupt/jitter 干扰。
  - **证据强度**：中。实机证明效率，控制精度的最大规模结果来自 simulation，不能直接证明生产网络稳定性。
- **观察 4：GPU server 的 CPU 常有余量，可以换取 GPU/network 利用率。** 论文引用公开报告的 cluster CPU utilization 为 20%–45%，另用一次 private conversation 得到 [[Megatron|Megatron-LM]] 平均使用 128 core 的 14.5%；DeepSeek-V2-Lite 实验中 UCCL-Tran 每块 active 400G NIC 让总 CPU 用量从 2.3 增至 4.3 core（§1、表 2）。
  - **依赖假设**：scheduler 能预留并隔离这些 core，CPU 不是 data loading、storage、compression 或 control-plane 的瓶颈。
  - **可能失效场景**：CPU oversubscription、[[NUMA|NUMA]] 放置错误、虚拟机 steal time 或多 tenant 干扰会把 transport jitter 直接变成网络 tail latency。

## 核心方法

**层次与 threading model。** UCCL-Tran（图中简称 uTran）作为 `libnccl-net.so` 插在 [[NCCL]]/RCCL 与 NIC primitive 之间，应用仍调用 allreduce、all-to-all 或 SendRecv。plugin 通过 shared memory 把 connect、memory registration、send/recv/flush/poll 请求交给一组 user-space engine thread；每个 engine 以 run-to-completion 方式执行 TX、RX、pacing、timeout 和 retransmission，并用 DRR 在 connection 间调度（图 2、§3）。实现有 28.4 KLoC C++；大多数 backend 不改 collective library，EFA/UD 的 scattered receive 需要约 170 LoC NCCL 修改（§5）。

**按 NIC 能力拆开 control header 与 GPU payload。** 首选 UC：`write_with_imm` 让 NIC 对 GPU data chunk 做 segmentation/reassembly 和 GPUDirect DMA，同时把 32-bit immediate data 作为 control header 交给 receiver CPU；它绕过 NIC 内建的 CC、reliability 和 reorder。没有 UC 时，Broadcom path 使用关闭 CC 的 RC，仍由硬件保证可靠性。EFA 的 UD path 用 scatter-gather 在发送时合并 CPU header 与 GPU payload，接收时再分别 DMA 到 CPU/GPU；因为 UD 不做 reassembly，乱序 payload 先落到 GPU buffer，随后由融合进 NCCL reduction kernel 的 scattered memcpy 归位（图 3–4、§3.1）。这些 fallback 的可扩展范围不同，不能把 UC 的“全软件 reliability”外推到 RC。

**多 QP packet spraying。** UC/RC 默认让一对 NIC 共享 256 个 QP，各 QP 借助 ECMP 形成不同 path；UD 用 source/destination QP 的组合获得同样的 path entropy。每次发送先从两个随机 path 中选 RTT 较低者，再运行 CUBIC 或 Swift 决定发送量和 pacing。sequence/ACK、GPU reordering buffer、duplicate ACK 和 timeout 处理多路径乱序与丢包。QP 在同一 NIC pair 的多个 GPU connection 间共享，避免每条 connection 重复烧 256 个 QP（图 5、§3.2、§4.1）。

**让 host transport 跑到 line rate。** connection splitting 把一条 connection 的 QP 分给多个 engine，每个 engine 有独立 CC/LB state，plugin 把 message 发给当前最空闲的 engine；SRQ/SCQ 降低多队列 polling 成本。control coalescing 默认一条 32 KB chunk 做一次决定，UC/RC 让 NIC 把 chunk 分段成 packet；UD 用 chained posting 一次 MMIO 提交最多 32 个 verb。这样 ASIC backend 一 core 可处理 400 Gbps 单向，两 core 可处理 400 Gbps 双向（§3.3、§6.4）。

**可扩展策略接口。** `onChunkSize`、`onSelectPath`、`onRxACK`、`onRxCredit` 等 hook 让开发者替换窗口、pacing、路径、重传和 receiver credit policy（附录 A）。论文用三个 case 展示这一点：per-path RTT packet spraying；面向 [[MoE]] incast 的 receiver-driven EQDS；在 GPU memory 保存 reorder state 的 selective retransmission。当前软件能看到 hardware timestamp 导出的 RTT 和 packet loss，但 NIC 不向它暴露 ECN、packet trimming 等 header signal，这是明确的 HW–SW interface 限制（§3.4、§4）。

**非 RDMA 路径不是同一种数据面。** 对普通 ENA NIC，UCCL-Tran 在 AF_XDP/UDP 上实现可靠多路径，CPU 做 reassembly，再用 `cudaMemcpy` 把 message 送进 GPU；由于没有 GPUDirect，超过 16 MB 时它和 kernel TCP 都遇到瓶颈（附录 C.3）。这证明 API 可跨非 RDMA backend，不证明该路径保留了 RDMA datapath 的零拷贝性质。

## 设计取舍

- **用 CPU core 换 transport programmability**：默认每 NIC 多用 2 个 engine core，EQDS 还需 1 个 pacer core；在 CPU 富余的专用训练机上合理，在 CPU 紧张或 multi-tenant 环境中未必。
- **用粗控制换 line rate**：32 KB coalescing 大幅减少 verb 和 decision 次数，却会延迟 loss/CC 反应；严重 congestion 时需要缩小 chunk，论文没有实现完整 adaptive policy。
- **用大量 QP 换 path entropy**：256 QP 缓解 collision，但增加 NIC context swap、MMIO 和 CPU–NIC [[PCIe|PCIe]] traffic；论文观测到额外开销，却没有给 production NIC resource isolation policy。
- **用 portability 换不一致的能力**：UC 可把 CC 和 reliability 都搬到软件，RC 只能搬 CC/LB，UD 要额外 GPU reassembly，AF_XDP 甚至回到 CPU copy；“统一软件传输层”不代表各 backend 的语义和成本相同。
- **边界条件**：large-message collective、可预留 host core、有多条 ECMP path、NIC 支持 GPUDirect 与必要 verb 时最合适；tiny P2P、GPU-initiated IBGDA、CPU oversubscription 或单路径 fabric 时会变脆。

## 实验与结果

- **实机、网络与基线**：四个 testbed 都使用真实 NIC/GPU。CX_ETH 是 6 台跨机架服务器，每台 8×400G ConnectX-7 和 8×H100；AMD 是 4 台 rail-optimized 跨机架服务器，每台 8×400G Thor-2 和 8×MI300X；EFA 是 4 台跨机架 p4d，每台 4×100G EFA 和 8×A100；CX_IB 是 2 台同机架服务器，每台 8×400G ConnectX-7 和 8×H100（表 1）。collective 使用 1 MB–1 GB NCCL/RCCL-tests，metric 为 bus bandwidth；baseline 分别是 NCCL RC、RCCL/Thor-2 与官方 AWS NCCL-EFA/SRD。UCCL-Tran 默认每 NIC 额外使用 2 core，receiver-driven CC 再加 1 core（§6）。
- **不同真实网络上的 collective**：CX_ETH 上相对 ConnectX-7 使用 4/8/16 QP，UCCL-Tran 的 allreduce 最多快 2.32/1.60/1.24 倍，all-to-all 最多快 1.79/3.82/4.54 倍；AMD rail topology 上 allreduce 相当，all-to-all 最多快 1.68/1.61/1.78 倍；EFA 上相对 SRD，allreduce 最多快 1.27 倍、all-to-all 最多快 3.27 倍，但至少 256 MB allreduce 不再占优。CX_IB 无拥塞时，UC/RC 基本追平 ConnectX-7，UC 在大于 128 MB allreduce 上最多慢不到 4%（图 7–10、§6.1）。
- **应用层结果的真实与仿真边界**：在 AMD 实机上端到端训练 16B DeepSeek-V2-Lite，并把 routed expert 数设为 32/64/128，UCCL-Tran 将每 GPU TFLOPS 最多提高 7.5%。DeepSeek-V3 serving 不是完整模型部署，而是在 EFA 实机上按公开 trace 模拟 compute time 和 hidden-state message；prefill latency 从 157.2 ms 降到 138.9 ms，即 1.13 倍，decode 从 13.6 ms 降到 9.6 ms，即 1.42 倍（图 11、§6.2）。
- **可扩展 transport case**：CX_IB 实机把 15-to-1 incast 与 16-NIC permutation victim traffic 同时运行，message 为 1 MB、每 sender 最多 4 个 inflight；EQDS 相对 InfiniBand 将 incast P99/P99.9 FCT 降低 1.73/1.72 倍，将 victim permutation 降低 4.50/4.88 倍（图 12）。loss test 在 AMD 两 GPU 上给 UCCL-Tran 软件注入丢包：drop ratio 为 1/16384 或 1/4096 时 goodput 只降约 1%，但“硬件下降 26%–42%”来自 Flor 的既有结果，不是同机同次对照；更高 drop ratio 的比较也有同样边界（图 13、§6.3）。
- **CPU 与组件开销**：DeepSeek 训练中，每 active 400G NIC 的 CPU 用量从 NCCL 的 2.3 core 增到 UCCL-Tran 的 4.3 core；CX_IB 上一 core 跑满 400G 单向，两 core 跑满 50 GB/s 双向。connection splitting 让 allreduce/all-to-all 的最大 bus bandwidth 从 45.7/39.9 提到 48.9/48.5 GB/s。heavy all-to-all 的 P99 ACK turnaround 达 36 µs，已接近论文引用的 10–40 µs datacenter RTT 上沿，说明 software control 并非总是“可忽略”（表 2–4、图 14、§6.4–6.5）。
- **大规模证据的口径**：图 6 的 60K QP 是在 16 块真实 400G NIC 上制造 QP cache 压力，用来**模拟** 241 GPU×256 path 或 961 GPU×64 path 的 QP 数量，不是数百 GPU 实测；部分 EFA/CX_IB 图关闭 NVLink+SHM，把同机 GPU 当作 virtual server，也没有生成真实多机架拓扑。唯一的 1024-NIC 实验是 htsim packet-level simulation：32 KB+RTT 让 sender-driven permutation completion time 比 4 KB+ECN 增 17.9%，receiver-driven 增 2.8%；改为 16 KB 后 sender-driven 只增 4.1%（表 5、附录 C.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| host software control 可以保留 RDMA NIC 的 bulk datapath 性能 | CX_IB 上 UC/RC 基本追平 ConnectX-7，图 10 | 2 台、共 16 块 GPU 与 16 块 NIC、同机架、无明显 congestion、1 MB–1 GB collective、预留 CPU core | 强 |
| 动态多路径能缓解真实跨机架 flow collision | CX_ETH all-to-all 最多 4.54 倍；AMD 最多 1.78 倍；图 7–8 | 4–6 台服务器、fat-tree 或 rail topology；倍率依 baseline QP 数和 message size | 强 |
| transport 改进能传到 ML 应用 | 训练 TFLOPS/GPU 最多提高 7.5%；serving latency 降低 1.13/1.42 倍，图 11 | 训练是真实 16B 模型；serving 是 EFA 上 trace-driven emulation | 中到强 |
| 软件接口能容纳 receiver-driven CC 与 selective retransmission | EQDS tail latency 最多 4.88 倍；software loss injection goodput，图 12–13 | incast 是 microbenchmark；硬件 loss baseline 引自 Flor，非同平台 A/B | 中 |
| 两个 host core 足以驱动一块 400G NIC 的双向 bulk traffic | 图 14、表 2–4 | ConnectX-7 ASIC segmentation/reassembly；额外 CPU、MMIO、PCIe 成本未折算为 GPU cluster cost | 强 |

## 批判性分析

### 论证链条

论文的中心拆分是成立的：无拥塞 CX_IB 证明“把 control 搬到 CPU”没有破坏 bulk RDMA datapath；跨机架实验再证明 software policy 能实现硬件缺少的多路径选择；EQDS 和 loss recovery 展示 API 不只服务一套 LB。需要限制 headline 的解释：4.54 倍不是软件数据面比 ASIC 快，而是 CX_ETH 上 16-QP ConnectX-7 baseline 在大 message 下遭遇 collision 和 CC backoff；在无 collision 网络，两者接近。同样，“最高 4.9 倍 tail latency”来自人为构造的 incast+permutation microbenchmark，不是 DeepSeek serving 的 request tail。

### 假设压力测试

最脆弱的假设是 CPU 一直有隔离且稳定的余量。训练 pipeline 若同时做 data preprocessing、checkpoint、storage、compression 或控制面工作，预留每 NIC 2–3 core 的 opportunity cost 会升高；论文只用平均 utilization 和单一训练 workload 支撑，没有注入 CPU contention 或 NUMA misplacement。第二个假设是 traffic 足够大：实验集中在 1 MB–1 GB，无法说明 disaggregated serving 中大量短 P2P message 的 latency。第三个假设是 QP/port entropy 真能映射到独立 path；不同 ECMP、adaptive routing 或 cloud virtualization 可能让 256 QP 落到少数 path。最后，GPU-initiated IBGDA 已绕开 host proxy；论文只提出 CPU-assisted 兼容方案，并引用其约 10% penalty，没有实现。

### 实验可信度

论文的优点是跨 NVIDIA、Broadcom、AWS EFA、AMD/NVIDIA GPU 和 Ethernet/InfiniBand 做了真实 prototype 测量，并在无 congestion 与有 collision 的网络分别回答“开销”和“收益”。但物理规模最多 6 台服务器；禁用 NVLink/SHM 只增加 network traversal，不能复现数百 host 的 path contention、failure 和 fairness。DeepSeek-V2-Lite 是实训，DeepSeek-V3 是 trace emulation；二者不应合称完整 production application。loss recovery 没有真实交换机丢包的同平台 hardware A/B，1024 NIC 只出现在 packet simulator。性能比较还给 UCCL-Tran 更多 CPU core，论文没有做等 CPU budget 或成本归一化。图 15 的 ConnectX-7 QP attribution 在 camera-ready 时只能取回最多 128 QP 的旧日志，对 256 QP trend 是作者推断。

### 系统性缺陷

28.4 KLoC user-space transport 加上 QP sharing、timeout、reorder、credit 和 clock synchronization，会把原本由 NIC 管理的状态带进 host 运维面。论文讨论 packet loss，却没有评测 engine crash、process restart、stale memory registration、connection teardown、sequence wrap、GPU reset 或 shared-QP 故障隔离；也没有 multi-tenant access control 和 malicious plugin 安全模型。backend 行为明显 vendor-specific：EFA 无 hardware timestamp 时靠 software timestamp 减估算的 host queue delay，连续 QP number 的性能原因也只是推测；RC backend 不能替换 hardware reliability。软件提供了更好的 observability 位置，但论文没有实现生产级 tracing、alert 或 recovery 工具。

## 局限与后续工作

- **局限 1：实体集群规模小。** 在至少 128 台、跨多级 fabric 的集群上测 all-to-all throughput、P99/P99.9 FCT、path fairness、QP cache 和 CPU jitter，不能再用 virtual server 代替。
- **局限 2：CPU 机会成本未闭合。** 固定 GPU 数量后逐步注入 preprocessing、storage I/O、interrupt 和 co-tenant load，报告 GPU throughput、transport tail 和每 NIC core-hours 的退化曲线。
- **局限 3：可靠性证据不完整。** 在可控交换机上对 UC selective retransmission、RC go-back-N/NACK 做同硬件 A/B，并加入 burst loss、reordering、PFC on/off 和 engine crash。
- **后续工作 1：验证短消息与 GPU-initiated 通信。** 对 1 KB–1 MB P2P、DeepEP/IBGDA 与 CPU-assisted IBGDA 测 latency、CPU/GPU cycles，并明确何时应绕过 UCCL-Tran。
- **后续工作 2：收敛统一 HW–SW interface。** 让 NIC 在单 QP 上接受 software-selected flow entropy，并通过 CQE 暴露 ECN/packet-trim signal；用相同 API 比较 control precision、QP resource 和 portability。

## 相关

- **相关概念**：[[RDMA]]、[[Congestion-Control]]、[[GPU-Networking]]、[[Multipath]]、[[GPUDirect]]
- **相关系统**：[[NCCL]]、Flor、ZeroNIC、EQDS、AWS EFA SRD
- **相关工作负载**：[[MoE]]、allreduce、all-to-all、prefill/decode disaggregation
- **同会议**：[[OSDI-2026]]
