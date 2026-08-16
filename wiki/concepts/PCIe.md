---
type: concept
aliases: [PCI-Express, Peripheral-Component-Interconnect-Express]
last_updated: 2026-08-14
tags: [hardware, io, accelerator, interconnect]
---

# PCIe

> PCI Express（PCIe）是 CPU 与 GPU、NIC、DPU、NVMe SSD 等设备之间的主机互连；系统能得到多少有效带宽和多低尾延迟，取决于真实拓扑、传输粒度、DMA/doorbell/完成路径和共享争用，而不只取决于 generation 与 lane 数。

## 核心思想

PCIe 是点到点、交换式互连。Root complex 把 CPU/memory hierarchy 连接到 endpoint，PCIe switch 可以让多个设备共享上行链路。`GenN × lanes` 给出编码后的理论方向带宽，但一次实际传输还要经过 transaction layer packet（TLP）、flow control、IOMMU/address translation、DMA engine、queue、doorbell 与 completion。小请求、频繁 MMIO、同步等待和过多 software crossing 都会让有效吞吐远低于线速。

设备通常通过 BAR 暴露 MMIO register/doorbell，通过 DMA 直接读写 host 或 peer device memory。CPU 发命令、设备搬数据、completion 再通知 CPU/GPU，是三条不同成本的路径。数据量小但 round trip 多时，控制路径可能主导；数据量大时，共享 switch、root complex、host memory channel 或 device copy engine 可能先饱和。

PCIe 是 full-duplex，H2D 与 D2H 理论上可并行，但两个方向常共享 endpoint internal resource、switch uplink 或 memory system。[[Nixie-OSDI26]] 利用双向交换隐藏 GPU working-set 搬移，这依赖具体消费级 GPU/host topology；不能仅由“PCIe 可双向”推出任意平台都能同时达到两个方向峰值。

[[CXL]] 复用 PCIe 的电气/物理基础与部分枚举管理，但提供 cache/memory semantic protocol。二者不是同义词：PCIe device I/O 主要由 command、DMA 和 MMIO 驱动；CXL.cache/CXL.mem 允许 load/store 与 coherence。把 CXL memory 简化成“更快的 PCIe DMA”会漏掉一致性、memory ordering 和 fabric 管理成本。

## 为什么重要

AI 系统频繁把模型权重、[[KV-Cache]]、embedding、activation 与 checkpoint 放在 host memory 或 SSD，再跨 PCIe 按需取回。[[DirectKV-OSDI26]]、[[ECHO-OSDI26]]、[[Strata-OSDI26]]、[[KAIROX-OSDI26]] 和 [[Wang-LocalMoEInference-OSDI26]] 采用不同的 zero-copy、稀疏访问、分层缓存或权重预取，但都受同一事实约束：小传输难吃满链路，过量搬移会压过计算，只有可以和计算 overlap 的流量才可能被隐藏。

PCIe 也会把控制面拖进关键路径。[[MoonBright-OSDI26]] 测到传统 GPU `cudaMalloc` 的 page-table build/transfer 远重于 physical allocation；[[CoPilotIO-OSDI26]] 发现 GPU 轮询 NVMe CQ 会占 SM 与显存；[[DPA-Store-OSDI26]] 则发现每层都从 SmartNIC DMA host tree 会累积多轮 PCIe delay。共同方向是减少 round trip、把工作移到更合适的处理器，并批量提交控制操作。

最后，PCIe 是许多论文结论的硬件边界。[[DCP-OSDI26]] 的 PP 优势针对 PCIe 4.0 GPU，换 NVLink/NVSwitch 后 TP 成本可能下降；[[Syncopate-OSDI26]] 只测 NVLink H100，没有 PCIe-only 结果；[[WiseCode-OSDI26]] 的高带宽推算也可能遇到未测的 PCIe array bottleneck。明确这些边界比简单把“PCIe”列进相关概念更重要。

## 关键观察 / 隐含假设

- **标称带宽不是 application bandwidth。** [[CoPilotIO-OSDI26]] 在四块 SSD、8 KB random read 下用 24 个 SM 饱和约 25 GB/s，而 GPU polling baseline 需要 72 个以上 SM；瓶颈包含 completion control 和 memory traffic，不是 link rate 一个数字。
- **控制 round trip 可以比数据搬移更贵。** [[MoonBright-OSDI26]] 将 page-table construction 放到 GPU 侧，并延迟 TLB consistency；[[Helmsman-OSDI26]] 每批 NVMe command 对每盘只敲一次 doorbell。
- **位置决定 round trip 数。** [[DPA-Store-OSDI26]] 把 learned-index inner node 和 read fast path 放在 BlueField DPA，避免每层 NIC–host 往返；但 DPA memory 慢、容量小，insert/retraining 仍留 host。
- **小传输需要合并或避免搬移。** [[KAIROX-OSDI26]] 指出约 8 KB neuron 无法有效利用 PCIe；[[Strata-OSDI26]] 以大块 I/O 和 GPU 重排处理层级 KV 碎片；[[DirectKV-OSDI26]] 则让 kernel 直接读取 host KV，避免 staging copy。
- **overlap 是有条件的。** [[FlowANN-OSDI26]]、[[Nixie-OSDI26]]、[[Wang-LocalMoEInference-OSDI26]] 都依赖可预测的 computation window；短 prompt、fetch 长尾或链路突发争用会使隐藏失败。
- **不同方向可能有不同瓶颈。** PCIe full-duplex 为 Nixie 的交换提供机会，但 endpoint copy engine、host DRAM 与 switch oversubscription 仍可能让 H2D/D2H 互相影响；论文的单机结果不能变成协议保证。
- **共享 topology 是系统资源。** 多 GPU、SSD、NIC 可以各自有空闲 queue，却共同争用 root complex 或 switch uplink。[[Hetu-v2-OSDI26]] 只用 endpoint P2P bandwidth 建模，未跟踪共享 path 上的拥塞。
- **proxy/offload 是资源交换，不是免费消除开销。** CoPilotIO 以 CPU core 换 GPU SM；[[UEP-OSDI26]] 以每 GPU 的 CPU proxy 换可移植通信；DPA-Store 以 NIC thread/memory 换 host round trip。
- **实验互连决定并行策略结论。** DCP 的 PCIe 结果、Syncopate 的 NVLink-only 结果和 [[EcoServe-OSDI26]] 的普通 PCIe/低速网络集群分别回答不同问题，不能互相替代。

## 设计空间与取舍

- **Host staging / peer-to-peer / direct host access**：staging 易做连续重排和缓存，却多一次 copy；P2P 减少 host traffic，但受 topology、IOMMU 与 device support 限制；direct host access 省显式 copy，却把远端 latency 放进每次 demand access。
- **Fine-grained demand / coalesced transfer**：细粒度减少 overfetch；合并提高 payload efficiency 和 doorbell amortization，却增加等待、buffer 与无用数据。
- **Synchronous / asynchronous / pipelined**：同步最简单却暴露 RTT；异步让多请求并行；pipeline 只有在依赖图中存在足够独立计算时才能真正隐藏传输。
- **CPU control / GPU control / DPU control**：CPU 生态成熟但可能经过内核和跨 socket；GPU 可按需提交，却不适合浪费 SM 轮询；DPU 靠近 NIC，但计算、DRAM 与 host-to-DPA bandwidth 受限。
- **MMIO doorbell per request / batched doorbell**：逐请求延迟直观；batch 减少 PCIe transaction，却可能增加排队延迟。最优 batch 随 SLO 与 IOPS 变化。
- **Pinned memory / pageable memory**：pinning 避免 fault 与重复 DMA mapping，代价是长期占用 host capacity、影响 reclaim；pageable path 通用，却有 fault、migration 和 registration 开销。
- **Topology-aware placement / transparent runtime**：显式绑定 CPU、buffer 与 device 可预测，但部署复杂；完全透明更易用，却可能跨 root complex/NUMA 绕路。
- **PCIe collective / NVLink/NVSwitch collective**：PCIe 普及且便宜，collective latency/带宽较弱；专用 fabric 更强但成本高。模型并行策略必须随互连重选。

## 引用本概念的论文

### 数据搬移与内存分层

- [[DirectKV-OSDI26]] — GPU kernel 直接读取 CPU-resident KV cache，减少显式 D2H/H2D staging；多 GPU 和 host bandwidth 争用尚未覆盖。
- [[ECHO-OSDI26]] — 稀疏注意力只搬选中的 KV block；主实验假定约 1 TB host pool 与 PCIe 基本独占。
- [[Strata-OSDI26]] — 分层 KV cache 通过大块 I/O、GPU 重排和 decode 填 prefill load bubble；48 GB/s 结果依赖 pinned/local host memory。
- [[KAIROX-OSDI26]] — 按持续热点与一次性尖峰决定 neuron transfer，避免约 8 KB 碎片化搬运压过收益。
- [[Wang-LocalMoEInference-OSDI26]] — 将 expert weight 搬运与长 prompt 的 prefill 计算重叠；4K 及以下 prompt 中 setup/transfer 可反而更慢。
- [[BatchGen-OSDI26]] — 大规模批推理将 host DRAM 作为容量层，依赖每节点 2 TB 内存与足够 PCIe bandwidth。
- [[Cocoon-OSDI26]] — 历史放 DRAM/CXL 时，CPU GEMV 可减少跨 PCIe 搬整段历史，但用更慢 CPU 计算交换。
- [[Nixie-OSDI26]] — 利用 PCIe 双向带宽交换 GPU working set，结论限于所测消费级 GPU 与单机 time-slicing。
- [[Prism-OSDI26]] — GPU memory balloon 以 host DRAM 和同机互连换快速模型激活。
- [[POEGA-OSDI26]] — evolving graph 的 GPU-centric 执行没有单独报告 PCIe bytes 与尾延迟，是关键证据缺口。
- [[VTC-OSDI26]] — virtual tensor 在单 A100 PCIe/H100 NVL 上消除部分数据搬运，尚无 multi-GPU 证据。
- [[Weave-OSDI26]] — RL post-training 的组大小和切换成本受 host memory、NUMA 与 PCIe congestion 约束。

### I/O、控制与 near-device processing

- [[CoPilotIO-OSDI26]] — GPU 写 NVMe SQ、CPU poll CQ，并按负载启用 GPU co-polling；以 CPU core 换 GPU compute。
- [[DPA-Store-OSDI26]] — 将 ordered KV traversal 放到 BlueField-3 DPA，避免多轮 NIC–host tree walk；写路径受 host-to-DPA bandwidth 限制。
- [[Helmsman-OSDI26]] — 以 SPDK 批量提交 NVMe command，并按盘合并 doorbell，服务大 top-k 全闪存 ANNS。
- [[MoonBright-OSDI26]] — 在设备侧构造 GPU page table，避免 CPU runtime/driver/PCIe 的长串行 allocation control path。
- [[UEP-OSDI26]] — GPU/CPU command FIFO 把 head 与 tail 分置两侧，避免 poller 反复跨 PCIe 读取不利位置。
- [[UCCL-Tran-OSDI26]] — 多 QP 增加 path entropy，也增加 NIC context、MMIO 与 CPU–NIC PCIe traffic。
- [[Oxbow-OSDI26]] — 在 kernel、userspace 和 computational storage 间协作；全 CSD 路线会为前台请求增加 PCIe crossing。
- [[Espresso-OSDI26]] — 以 CXL JBOF 共享 SSD processor；controller/DRAM 在 PCIe 4.0/5.0 SSD BOM 中是重要成本。
- [[Spice-OSDI26]] — 在单机 PCIe 5.0 SSD 上恢复 serverless snapshot；结果不能外推普通云盘和完整控制面。
- [[M3U-OSDI26]] — pass-through device IOPF 需要额外 PCIe transaction 与 interrupt，平均需求分页延迟约为 vCPU fault 的两倍。
- [[GraCE-OSDI26]] — selective CUDA Graph 比较表明，小对象 pointer copy 可能比 HBM data copy 更不利；这里的 PCIe 与垃圾收集无关。

### 并行策略、网络与评测边界

- [[DCP-OSDI26]] — 在 PCIe 4.0 GPU 上重审 PP；NVLink/NVSwitch 上结论可能反转。
- [[EcoServe-OSDI26]] — 面向普通 PCIe GPU 与 10/25 Gbps network，减少跨 instance KV 搬移。
- [[FlowANN-OSDI26]] — 用 discovery–expansion window overlap CPU/GPU 图边 fetch；共享 PCIe 长尾会扩大额外工作。
- [[Hetu-v2-OSDI26]] — 分层 SPMD model 未追踪 endpoint 间共享 PCIe/IB path congestion。
- [[Syncopate-OSDI26]] — 只在 NVLink H100 上评测，没有 PCIe-only 或跨节点结果。
- [[StriaTrace-OSDI26]] — 在 kernel timeline 中追踪 PCIe/NVLink transfer，把互连事件与 request/KV 状态对齐。
- [[BALBOA-OSDI26]] — 200G 结论只有 synthesis 候选路径，缺少真实 PHY、PCIe、HBM 的端到端验证。
- [[LiteSwitch-OSDI26]] — CXL memory stall 工作以 PCIe/CXL 平台为基础，但核心关注 load-to-use latency 而非 DMA 吞吐。
- [[NEMO-OSDI26]] — 把 PCIe/CXL accelerator memory 纳入 memory observability 的目标环境。
- [[DGC-OSDI26]] — RDMA marker testbed 使用 BlueField-3 PCIe 4.0×16；这只是实验配置，不是 DGC 贡献。
- [[WiseCode-OSDI26]] — 高带宽存储集群结论主要来自单盘与推算，真实 array 可能遇到 CPU/PCIe 瓶颈。
- [[Oasis-SOSP25]] — 研究 PCIe device pooling 的共享与隔离。
- [[RDMA-LiveMigration-SOSP25]] — 在 RDMA device live migration 中处理 PCIe/pass-through 状态与性能边界。
- [[Xerxes-FAST26]] — 用于 CXL/PCIe storage simulation 与系统评估。

## 已知局限 / 开放问题

- OS 与 runtime 缺少统一、动态的 PCIe topology/traffic model；endpoint 带宽无法表达共享 switch uplink、root complex、IOMMU 与 host memory contention。
- 多租户带宽隔离不能只依赖 device queue priority。GPU、NIC、SSD 的独立控制器看不到共同 PCIe path，需要跨设备 admission 与 telemetry。
- 细粒度 direct access 与大块 coalescing 之间缺少能同时考虑 overfetch、排队、tail SLO 与能耗的在线控制。
- P2P、IOMMU、SR-IOV、confidential VM 与 live migration 组合后，安全隔离、可撤销 DMA 和故障恢复仍有大量未验证角落。
- PCIe generation 变化会移动瓶颈而非自动消除它：更快 link 可能让 host DRAM、GPU copy engine、doorbell rate 或 software completion 先饱和。
- 论文应报告真实 topology、单/双向 throughput、transfer-size distribution、PCIe bytes、P99/P99.9 和共置干扰；只写“PCIe 5.0”不足以复现实验边界。
