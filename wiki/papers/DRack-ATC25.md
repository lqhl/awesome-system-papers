---
type: paper
name: DRack
full_title: "DRack: A CXL-Disaggregated Rack Architecture to Boost Inter-Rack Communication"
authors: [Xu Zhang, Ke Liu, Yuan Hui, Xiaolong Zheng, Yisong Chang, et al.]
venue: ATC
year: 2025
tags: [cxl, disaggregation, rack-architecture, networking, datacenter, inter-rack-communication]
source_pdf: "[[atc2025-zhang-xu.pdf]]"
source_md: "[[atc2025-zhang-xu]]"
---

# DRack: A CXL-Disaggregated Rack Architecture to Boost Inter-Rack Communication (ATC 2025)

> **一句话总结**：关键观察是跨 rack 流量占主导（Facebook 平均 87.1%）但 rack 内 NIC 长期闲置（>90% host 在 1s 内不发不收）；DRack 用 [[CXL]] 3.0 fabric 把 rack 内 NIC 与 memory 池化，让任意 host 借用闲置 NIC 并跨多 memory 设备 DMA，相比 ToR-centric 架构通信阶段平均减少 37.3%，Redis p99 尾延迟降 62.2%。

## 问题与动机

数据密集型应用（图计算、[[MapReduce]]、DNN 训练）按 [[BSP]] 范式在更多 rack 上 scale out，同时 GPU/FPGA 等算力提升使计算阶段产出数据的速率远高于单 host NIC 容量（数百 GB/s vs 100 Gbps），跨 rack 通信因此成为性能瓶颈。传统 ToR-centric rack 中，流量要两次经过 host NIC（egress/ingress）和可能 oversubscribed 的 ToR 上行，在 incast / 数据倾斜场景下尤为脆弱。

已有路线各有硬伤：**暴力加 NIC/交换机带宽**（EFLOPS、HPN、vClos）成本高且进一步压低本就偏低的链路利用率（Facebook 测量 99% 链路 <10% 负载）；**可重配置拓扑**（RDC、REACToR）受限于重配置延迟和流量突发不可预测（heavy hitter 在 100ms 内持续概率 <50%）；**调度/放置优化**（ShuffleWatcher、Crux、Varys）只能减少 contention，无法消除跨 rack 流量本身。作者 claim 需要一种**静态、无需额外跨 rack 带宽硬件、无需流量预测**的 rack 级架构来高效承载跨 rack 通信。

## 关键观察 / 隐含假设

- **观察 1：跨 rack 流量占主导，但 rack 内 NIC 利用率长期偏低。** Facebook 24h packet trace 显示 Hadoop / Frontend 集群分别有 86.7% / 97.3% 流量跨 rack；同时 >90% host 在任意 1s 窗口内不发不收。作者自己的 8-host 实验里平均 NIC 利用率 <20%。
  - **依赖假设**：workload 遵循计算-通信交替（BSP/MapReduce）、通信数据量在 host 间高度倾斜（图分区不均、DLRM embedding 热点），且多租户调度造成资源碎片（20%-45% 机器跑非分布式作业，NIC 完全空闲）。
  - **可能失效场景**：all-to-all 持续饱和、微服务间均匀小流量、或每 host 已绑定满带宽 NIC（θ=1 时 DRack 与 ToRack 性能趋同）；GPU 集群中每 GPU 已配 400G NIC 且持续满载时，池化收益缩小。
- **观察 2：池化 NIC 的总容量会超过单 host 的 PCIe 链路与本地 memory 带宽。** 例：16×200G NIC pool 接收吞吐 3200 Gbps，远超单 host PCIe5×16（~500 Gbps）或本地 DRAM 带宽；many-to-one incast 时单 host 成为 DMA 写入瓶颈。
  - **依赖假设**：必须同时 disaggregate memory，让 NIC pool DMA 跨多 memory 设备以吃满 NIC 容量；且 host CPU 能用 [[CXL]] memory semantics 直接 load/store memory pool，避免先 DMA 到本地 DRAM。
  - **可能失效场景**：memory pool 带宽仍不足（极端 incast 到少数 Section）、或应用强依赖本地 NUMA 低延迟访问且无法被 DRAM cache 掩盖时，计算阶段反而变慢。
- **假设 1：CXL 3.0 fabric + SR-IOV 可在不改 NIC 硬件的前提下实现 rack 级设备池化。** DRack 依赖 CXL switch 做地址重映射、CXL.io 兼容 PCIe NIC、SR-IOV 把每张物理 NIC 虚拟成每 host 一个 vNIC。
  - **证据强度**：中。原型用 FPGA + DoCE 模拟 CXL transactions，证明了机制可行，但商业 CXL 3.0 fabric 产品尚未部署，真实延迟/带宽/规模特性仍待验证。
- **假设 2：跨 rack 流量可用 MPTCP 在 vNIC 间均分，且 CPU 在 bulk synchronization 阶段有足够 core 处理多 subflow。** 论文承认 NIC 数量增加时 MPTCP 的 interrupt/MMIO/merge 开销上升，但认为同步阶段 CPU core 数通常超过 pooled NIC 数。
  - **证据强度**：中偏弱。ablation 显示 MPTCP 对 Redis p99 有显著贡献，但实验仅 2-NIC pool；16+ NIC rack 时开销曲线论文未测。
- **假设 3：应用可通过 socket 编程模型透明运行，intra-rack 通信用 pass-by-reference 即可，无需共享内存一致性。** kernel driver 把 SEND/RECV 翻译成 CXL.mem store/load；作者限定大消息同步场景，不要求 src/dst 同时访问同一 Buffer。
  - **证据强度**：中。Redis、训练、图计算等 evaluated workload 符合；细粒度共享状态或 RDMA verbs 应用需另做适配（论文未覆盖）。

## 核心方法

DRack 的核心是把 rack 从「每 host 绑定本地 NIC + 本地 memory」改成「rack 级共享 NIC pool + memory pool」，并用 [[CXL]] 3.0 fabric 作为 ToR tier 以下的互连层。这直接回应观察 1：闲置 NIC 可被任意 host 驱动，把 egress/ingress 瓶颈从单 host 扩散到整 rack；同时 ToR 角色上推——NIC pool 充当原 ToR 的上行，原 ToR 变 aggregation tier，可在合适布线下去掉 oversubscription，获得 rack 对之间的 full bisection bandwidth。

**NIC pool（设计 ➀）**：rack 内所有 NIC 通过 CXL interconnect 与 host 解耦，经 [[SR-IOV]] 每张物理 NIC 虚拟出 N 个 vNIC，每 host 持有全部 NIC 的 vNIC。发送时 host 经 MMIO ring doorbell，各 vNIC DMA 从 memory pool 读 TX buffer 发包；接收时各 vNIC DMA 写入均匀分布在 IS0 的 RX buffer，再经 completion queue 通知 host。跨 rack 流量用 [[MPTCP]] 拆 subflow 绑定不同 vNIC，解决 ECMP 单流单 NIC、packet spray 乱序的问题。

**Memory pool（设计 ➁）**：每 host 贡献一段 local memory（原型 12GB）加入 interleave set IS0（256B 粒度），剩余 memory（4GB）组成 per-host ISi 存 virt_queue、ref_queue 等高频结构。Fabric Address Space 由 Fabric Manager 管理 Section（2MB hugepage）分配。NIC DMA 跨 IS0 多设备读写，聚合带宽超过 NIC pool 容量，回应观察 2 的 PCIe/memory 瓶颈。

**Memory semantics 直访（设计 ➂）**：计算阶段 host CPU 用 CXL.mem load/store 直接访问 IS0 中的用户数据，无需先 DMA 到本地 DRAM。Intra-rack 通信采用 pass-by-reference：sender 把 packet 指针写入 receiver 的 ref_queue，receiver load 引用后经 TCP 栈校验——比 ToR-centric 的 pass-by-value 少一次拷贝，microbenchmark 显示 intra-rack 延迟降 15.9%。

**系统支撑**：(1) kernel driver 在 TCP/IP 栈下拦截 socket I/O，对 inter-rack 走 vNIC DMA、intra-rack 走 ref_queue，对应用透明；(2) CXL port 上的 **DRAM cache**（128B / 4KB 多粒度、region 级配置）掩盖远端 memory ~13µs 延迟（本地 2.2µs，R=6.4 最坏配置），ResNet 训练 cache hit >86.9%，但 Redis 随机访问 hit 仅 59.6%、收益有限。

**DCN 集成**：DRack 改变 Clos 边缘拓扑——CXL interconnect 插入 host 与 NIC pool 之间，NIC 到 aggregation switch 的布线遵循 `NIC i → switch (i mod m)` 原则，支持 n>m 或 m>n 两种 pod 配置（Appendix A.1）。与现有 job scheduler 正交：ShuffleWatcher 场景下单 host 1P 即可驱动整 rack NIC pool shuffle，吞吐提升 20.8%；Crux 高优先级 job 可借用低优先级 job host 的闲置 NIC，通信时间降 47.7%-49.5%。

实现细节见 [[atc2025-zhang-xu]]：8 颗 MPSoC FPGA + 服务器组成 quad-rack 原型，CXL-DoCE 把 AXI 信号封装为 Ethernet 帧模拟 CXL 3.0 MemRd/MemWr；DPDK 软件 emulator 模拟 NIC pool 与 ToR 交换机。

## 设计取舍

- **静态池化 vs 动态可重配置**：DRack 选择固定 CXL fabric + 池化，避免 RDC 类拓扑重配置延迟和流量预测；代价是无法针对瞬时 heavy hitter 做专用直连，依赖 MPTCP 和 memory 分布做负载均衡。
- **CXL.mem 直访 vs DMA 拷贝**：消除拷贝、统一地址空间，但远端访问延迟 ≥2.7× 本地（原型 R=6.4），必须依赖 DRAM cache 和 interleave；计算密集且随机访存的应用（Redis key lookup）cache 收益有限。
- **MPTCP 均流 vs 简单 ECMP/spray**：MPTCP 能吃满 NIC pool 且保序，但 subflow 数随 NIC 增长带来 kernel 开销；论文 trade-off 是 bulk sync 阶段 CPU 空闲足够。
- **Topology 上推 vs 运维惯性**：消除 core oversubscription 需重布线 aggregation 层，与现有 ToR-centric 运维流程不兼容；论文未讨论渐进迁移路径。
- **边界条件**：在 BSP/MapReduce 类突发跨 rack 同步、NIC 倾斜、多 job 碎片化的 cloud 环境优雅；在 θ=1（host 已能饱和单 NIC）、全 rack 同时通信、或强依赖 RDMA verbs / 低延迟本地 memory 的 workload 下收益收窄或变脆。

## 实验与结果

- **环境**：quad-rack 原型，每 rack 2 host（MPSoC FPGA，4-core ARM A53 @1.2GHz）；DRack NIC pool 2×8Gbps，memory pool 2×16GB（remote 13µs / local 2.2µs）；baseline ToRack 每 host 8Gbps NIC、16GB memory、ToR 2×8Gbps 上行（**无 oversubscription**）；跨 rack RTT 60µs。
- **主结果**：6 类真实应用（PageRank、Redis、ResNet/TinyStories 训练、MapReduce WordCount、DLRM 推理）通信阶段平均减少 **37.3%**；Redis p99 / 平均延迟分别降 **62.2%** / **29.2%**。
- **吞吐敏感**：PageRank 最坏（θ=0.125）降 58.5%，全 θ 平均 32.8%；ResNet 最坏 59.8%、平均 39.6%；LLM 训练平均 39.9%；DLRM 推理平均 37.4%。θ=1 时 host 无法额外利用 NIC pool，与 ToRack 趋同。
- **调度器叠加**：ShuffleWatcher + DRack 释放更多 core 跑 mapper，整体吞吐 +20.8%；Crux 高/低优先级 job 通信分别加速 47.7% / 49.5%。
- **Ablation（Figure 11）**：Redis p99——仅 NIC pool -32.9%，+memory pool -63.9%，DRAM cache 几乎无额外收益，+MPTCP -65.9%；ResNet/PageRank——NIC pool+MPTCP -12.7%，+memory pool 累计 -38.1%，DRAM cache 对 ResNet 再 -28.6%（PageRank 仅 -9.9%，hit 56.2%）。
- **Microbenchmark**：intra-rack pass-by-reference 比 pass-by-value 延迟低 15.9%；Gloo collective 在 oversubscription 比 1→2 时 DRack 仍保持增益，MPTCP 优于 ECMP 和 packet spray。

## Critical Analysis

### 论证链条

observation → design → result 链条在**机制层面**闭合：先用 Facebook trace + 自有实验确立「高跨 rack 流量 + 低 NIC 利用率」，再用 PCIe/memory 带宽算术说明为何仅池化 NIC 不够，从而引出 memory pool 与 CXL.mem 三件套。Ablation 逐步叠加 NIC pool、memory pool、DRAM cache、MPTCP，能对应到 incast 吸收、DMA 带宽、计算/locality、负载均衡四个子问题。

主要跳步在**生产规模外推**：原型仅 quad-rack、每 rack 2 host、8Gbps NIC、FPGA 低频 CPU；claim「 complement 现有 DCN」但 baseline ToR **故意去掉 oversubscription**，可能高估 DRack 相对真实 oversubscribed DCN 的收益。论文用 θ 因子模拟 NIC 瓶颈，但未在 production-scale（数百 host/rack、400G NIC、真实 oversubscribed Clos）上验证。

### 假设压力测试

**CXL 延迟对计算阶段的侵蚀**是最脆假设之一。原型刻意取 R=6.4 最大远端延迟仍看到净收益，但 evaluated app 以通信阶段为主；若计算/通信比更高、或 memory access 更随机（Redis 已显示 cache 帮助有限），rack 级 memory pool 可能拖慢整体 job。论文未给出 end-to-end job time（仅 communication stage），外推到「训练/图计算总时间」需谨慎。

**NIC 池化的安全与隔离**论文未讨论。任意 host 驱动他人 NIC 发送、共享 memory pool Section、SR-IOV vNIC 配置——多租户 cloud 需要防止 cross-tenant 流量注入、DMA 越界、QoS 劫持。DRack 假设 rack 内互相信任，与 public cloud 部署有 gap。

**MPTCP 可扩展性**：2-NIC ablation 有效，但论文自己承认 16+ NIC 时 subflow/interrupt 开销上升；与 HPN 等「每 GPU 一 NIC」趋势结合时，MPTCP merge 成本可能成为新瓶颈。需要测量 NIC 数 vs CPU 占用曲线。

**拓扑与布线**：full bisection 依赖特定 NIC-to-switch 映射和 pod 内 n/m 关系；m>n 时每 rack 只能连部分 aggregation switch（Figure 12b），跨 pod 仍走 core，论文未量化这种配置下的路径多样性损失。

### 实验可信度

**强项**：真实应用覆盖图、KV、训练、推理、MapReduce；有 microbenchmark、ablation、scheduler case study；latency ratio 对齐 CXL 文献而非仅绝对吞吐；baseline 与 DRack 同原型实现，减少模拟器偏差。

**弱项**：(1) 规模极小（8 host total），无 production trace replay；(2) ToR baseline 无 oversubscription，不代表 Facebook/Google 生产 DCN；(3) FPGA ARM @1.2GHz 不能代表 x86 server + 商业 CXL switch；(4) 指标偏 communication stage / p99，缺少 power、capex、fault recovery、multi-tenant interference；(5) 未与 GRIN、HPN、Marlin 等最强 baseline 对比，主要对比「同硬件 ToRack」。

### 系统性缺陷

- **故障恢复**：共享 memory pool Section、vNIC DMA in-flight、MPTCP subflow 状态——host/NIC/switch 故障后的重试、lease、Section 回收，论文未讨论。
- **可观测性**：流量经 CXL fabric、vNIC、MPTCP 多路径，传统 per-host NIC counter 失效；论文未给出 operator-facing telemetry 设计。
- **兼容性**：socket 透明层覆盖 evaluated apps，但 RDMA verbs、DPDK poll-mode、硬件 timestamping 等生产网络栈特性未覆盖；CXL FM 单点与升级路径未讨论。
- **部署成本**：需要 CXL 3.0 fabric switch、重布线 aggregation、每 host DRAM cache 硬件、kernel 定制——相对「调度优化」的 opex/capex trade-off 论文未量化。

## 局限与 Future Work

- **局限 1**：商业 CXL 3.0 fabric 尚未规模部署，原型为 FPGA + Ethernet 模拟，绝对性能数字不能直接映射到未来 ASIC 系统。
- **局限 2**：实验规模小（8 host、8Gbps NIC），且 ToR baseline 无 oversubscription，对生产 DCN 的代表性有限。
- **局限 3**：仅报告 communication stage 收益，未系统测量 CXL remote memory 对 computation stage 的负面影响及 DRAM cache 命中率随 workload 变化。
- **局限 4**：多租户安全、故障恢复、RDMA 栈兼容、运维可观测性均未覆盖。
- **Future work 1**：在真实 oversubscribed Clos + 400G NIC + 商业 CXL switch 上 replay Facebook/HPC trace，分离「NIC 池化」与「拓扑上推」各自贡献。
- **Future work 2**：测量 NIC pool 规模（4/8/16/32）vs MPTCP CPU 开销、tail latency、公平性，评估是否需要硬件 multi-path 替代 MPTCP。
- **Future work 3**：为共享 NIC/memory pool 设计 tenant isolation 与 fault-domain 机制，并做 security/fault injection 实验。
- **Future work 4**：端到端 job time + power/capex 模型，对比 DRack vs 加 NIC/加带宽/调度-only 方案的总拥有成本。

## 相关

- **相关概念**：[[CXL]]、[[Disaggregation]]、[[RDMA]]、[[MPTCP]]、[[SR-IOV]]、[[MapReduce]]、[[BSP]]
- **同类系统**：Marlin、DirectCXL、Pond、Unimem、GRIN、HPN
- **同会议**：[[ATC-2025]]
- **对比**（如有）：DRack 与 ToR-centric + 调度器（ShuffleWatcher、Crux）为叠加而非替代关系