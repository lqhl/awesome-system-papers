---
type: paper
name: Xerxes
full_title: "Xerxes: Extensive Exploration of Scalable Hardware Systems with CXL-Based Simulation Framework"
authors: [Yuda An, Shushu Yi, Bo Mao, Qiao Li, Mingzhe Zhang, et al.]
venue: FAST
year: 2026
tags: [cxl, simulator, interconnect, coherence, pcie]
source_pdf: "[[fast2026-an.pdf]]"
source_md: "[[fast2026-an]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Xerxes: Extensive Exploration of Scalable Hardware Systems with CXL-Based Simulation Framework (FAST 2026)

> **一句话总结**：在尚无 [[CXL]] 3.1 硬件时，Xerxes 用 graph interconnect + peer-centric device 两层架构首次从第一性原理模拟 PBR、DMC 与 [[PCIe]] 6.0 全双工；真实 CXL expander 验证带宽误差 0.1–10%、loaded-latency 平均 4.3%，并揭示 tree 拓扑 root 瓶颈、DCOH snoop filter 需 LIFO 而非 LRU、读写混合可近 2× 带宽等三条可指导 rack-scale 设计的观察。

## 问题与动机

[[CXL]] 3.0/3.1 把互连从 PCIe 派生的严格树状 hierarchy（HBR）推进到支持任意 non-tree fabric 的 Port-Based Routing（PBR），并把 coherence 从 host-centric 的 HDM-H 扩展到 Device-Managed Coherence（DMC），理论上可支撑最多 4096 endpoint 的 rack-scale、peer-to-peer 内存池。但这类系统目前几乎无法买到完整硬件，研究只能依赖仿真或 emulation。

现有工具在方法论上集体失效：**NUMA emulation**（remote socket 模拟 CXL memory）在协议语义上与真实 CXL 不匹配，且 socket 数量远小于 4096，无法探索大规模 fabric；**计算中心型仿真器**（[[gem5]]、GPGPUsim）假设 host-centric 内存层次与 centralized directory coherence，难以插入可主动发起 snoop 的 CXL device，且 gem5 对现代 [[PCIe]] 支持陈旧；**网络中心型仿真器**（BookSim、Garnet）擅长拓扑路由但无 memory/coherence 语义；**行为级 CXL 工具**（MESS、CXLMemSim）用预标定的 latency-bandwidth 曲线向运行时注入延迟，适合评估「已知设备对应用的影响」，却无法预测新拓扑、新 DCOH policy 或 PBR 多路径下的性能。

作者 claim：需要一种**从零构建、模块化、可组合**的 CXL fabric 仿真框架，既能对已有 CXL 2.0 硬件做 predictive 校准，又能在无硬件条件下探索 PBR/DMC/PCIe 6.0 等 emergent feature 的设计空间。

## 关键观察 / 隐含假设

- **观察 1**：传统 tree/chain 拓扑在 scale-up 时会在 root/bridge 路径形成共享瓶颈，性能退化接近 chain，而非随 endpoint 数量线性扩展。
  - **依赖假设**：随机或均匀跨 memory endpoint 的访问模式；switch port 带宽为固定上界；PBR 路由按最短路径或等价竞争模型。
  - **可能失效场景**：workload 高度 locality 使流量集中在少数 leaf；spine-leaf 的 leaf 端口竞争在特定 tenant 混合下仍可能成为新瓶颈；fully-connected 在物理上不可部署于真实 rack。
- **观察 2**：HDM-DB 模式下 device-side inclusive snoop filter（SF）收到的请求流以 **cache miss 为主**，与 CPU L1/L2 上「hot data 常驻」的访问模式相反，因此 LRU/FIFO 类策略更容易驱逐仍被 peer cache 持有的 hot line。
  - **依赖假设**：90/10 skew workload、requester local cache 能装下全部 hot data、SF 与 local cache 同容量；bus 配置为 infinite bandwidth 以隔离 SF policy 效应。
  - **可能失效场景**：多 requester 争用、SF 容量小于 working set、或 coherence traffic 与数据 traffic 在真实 fabric 上争用带宽时，policy 排序可能改变。
- **观察 3**：[[PCIe]]/CXL 物理层的 **full-duplex** 使读写混合流量可同时占用正反两个方向，在 header overhead 较低时带宽可接近 2×；header/payload 比升高时收益迅速衰减。
  - **依赖假设**：单 bus、四 memory endpoint、随机 R:W 比例；half-duplex 作为对照且 turnaround 可配置。
  - **可能失效场景**：真实应用 burstiness 导致一个方向长期空闲；多 switch hop 与 coherence snoop 占用控制通道后，全双工利用率未必由 R:W mix 单独决定。
- **假设 1**：component-level 延迟参数（requester 10 ns、switch port-to-port 25 ns、PCIe port 25 ns 等）经公开资料与少量硬件点校准后，可外推到未见过的拓扑与 DMC 路径。
  - **证据强度**：**中**——CXL 2.0 点验证误差低，但 PBR/DMC 仅与理论 round-trip 对比（PBR 平均 10.4%、DMC dirty write 1.4%），尚无硅片 ground truth。

## 核心方法

Xerxes 围绕三条原则组织：**模块化**（interconnect 与 device 解耦）、**graph-based connectivity**（原生支持 PBR 的 arbitrary topology）、**peer-centric device model**（host 与 accelerator 均为可主动发请求的 agent）。对应两层：

**Interconnect layer** 在初始化时把系统建成图，默认提供最短路径路由；**switch** 按 PBR 规范维护 port ID（12-bit，最多 4096 endpoint）与转发表；**bus** 建模 [[PCIe]] 6.0 全双工，分别跟踪正反方向传输并做带宽分配，可切换 half-duplex 与 turnaround overhead。该层回应「传统 simulator 无法表达 non-tree + 多 hop peer-to-peer」的观察。

**Device layer** 将 host/accelerator 统一为 **Requester**（request queue、address translation/interleaving、cache coherence unit）。DMC 的具体实现是 device-side **inclusive snoop filter**（DCOH）：跟踪 peer sharer/owner，冲突时发 Back-Invalidate Snoop（BISnp），收集 Back-Invalidate Response（BIRsp）后授权；victim 选择与 CXL **InvBlk**（一次失效 2–4 条连续 cacheline）均可插拔。该层回应 DMC 需要 distributed、device-initiated coherence 而非 centralized directory 的假设。

**与现有仿真器集成**：通过 Xerxes Wrapper 接入 [[gem5]] `MemCtrl`（UpInterface/DownInterface 转换 packet、复用 event queue；DMC 经 SLICC `CohInterface` 失效 host cache）、DRAMsim3（cycle-based clock 推进）、SimpleSSD（event 格式转换）。用户可用配置文件搭系统，也可在两层分别扩展自定义 component。

## 设计取舍

- **取舍 1：predictive component model vs. behavioral Lat-BW 注入**。Xerxes 选择建模 packet、路由、coherence 状态机与物理层 duplex，仿真更慢于 MESS 但可探索「尚未存在的拓扑/DCOH」；MESS 在已知曲线上更快甚至略快于 vanilla gem5，却无法回答 PBR 多路径或 InvBlk 长度这类架构问题。
- **取舍 2：modular 两层 vs. 深度改写 gem5**。不改造 gem5 内部互连，而是用 wrapper 外挂 CXL fabric，降低侵入性、保留 gem5 CPU/缓存细节，但端到端时序依赖跨模拟器事件同步，复杂度落在 wrapper 正确性上。
- **取舍 3：graph 全连接 vs. 仿真成本**。fully-connected 在 N=64 时内存占用陡增（链路数二次增长），作者仍证明 runtime <90 s、内存多数拓扑 <200 MB，但密集拓扑探索成本显著高于 chain/tree。
- **边界条件**：对 CXL 2.0 expander + DRAMsim3 endpoint 校准最强；对 rack-scale AI trace（Bert、Pagerank、YCSB-F）主要在 **tree 扩容** 场景下展示 congestion 趋势，而非多种 fabric 下的生产级 SLO 验证。论文未讨论 multi-tenant 隔离、错误注入与 RAS。

## 实验与结果

- **硬件验证**（Montage MXC CXL 2.0 expander，PCIe 5.0×16 有效约 ×8 带宽）：idle/peak bandwidth 误差 **0.1–10%**；loaded-latency 曲线平均误差 **4.3%**，优于 NUMA emulation（曲线形态不符）、MESS（9.3%）、CXLMemSim（16.6%）。
- **SPEC CPU2017**（gcc/mcf，以 CXL memory 带来的 execution time overhead 为指标）：Xerxes-standalone 最低 **+0.7%**；gem5-Xerxes 亦优于 NUMA/gem5-garnet；gem5-MESS 在 mcf 上可达 **-28.3%** 偏差。
- **仿真开销**：gem5-Xerxes 相对 vanilla gem5 平均仅 **+2%**；gem5-garnet **+22.5%**；MESS **-6%**（绕过详细 DRAM）。
- **拓扑 DSE**（N–N requester/memory，合成随机访问）：chain/tree 带宽受单 port 限制不随 scale 提升；ring 最高约 **2×** port；spine-leaf **N/2×**；fully-connected **N×**。真实 trace（BTree、redis、silo 等）上 ring **1.72×**、spine-leaf/FC 最高 **3.63×** 吞吐 vs. chain/tree。
- **DMC**：skew workload 下 LIFO vs FIFO 带宽 **+5%**、invalidation **-16%**；InvBlk 长度 **2** 最优，更长因 cache lookup 与带宽竞争无额外收益。
- **全双工**：零 header overhead 时 1:1 读写混合带宽近 **2×** read-only；header=payload 时混合收益归零；真实 trace mix degree 每增 0.1 带宽约 **+9%**。

## Critical Analysis

### 论证链条

论文的「问题 → 两层架构 → 三类探索」链条整体闭合：先用 CXL 2.0 硬件证明 interconnect+bus+endpoint 模型可信，再用同一框架推导 PBR/DMC/duplex 在理论上可计算的路径延迟，最后把合成 micro-benchmark 结论延伸到多条 memory trace。薄弱环节在于 **第三步外推**：tree 扩容实验（图 14）只覆盖单 requester + 多 memory endpoint，与多 requester fabric 竞争场景不同；fully-connected 的 3.63× 增益在物理部署上不可直接映射为产品建议，更像上界参考。

### 假设压力测试

- **Workload**：探索大量使用随机地址或 replay trace；若生产 CXL pool 以 capacity tiering + 显式 placement（如 [[Pond]]、TPP 类策略）为主，root 瓶颈严重程度可能低于论文随机模型。
- **硬件代际**：验证平台为 CXL 2.0 / PCIe 5.0；论文将 PCIe 6.0 全双工与 DMC 要求当作参数化扩展，真实 retimer、链路不对称（论文硬件中 MCIO 占一半 lane）会改变 duplex 收益。
- **规模**：仿真 scale 至 64 node、4096 endpoint 为协议上限；fully-connected 二次链路增长意味着论文证明的是「仿真器可扩展」，而非「该拓扑在经济上可建」。
- **正确性**：聚焦平均带宽/延迟与 invalidation 计数；**论文未讨论** coherence 协议 corner case、乱序、故障恢复对性能的影响。

### 实验可信度

- **Baseline 强度**：对比 NUMA、MESS、CXLMemSim、gem5-garnet 覆盖面广；行为级工具在验证阶段被喂入 hardware ground-truth 曲线，属于「公平下的 best-case 对手」，Xerxes 仍显著更准，支撑 predictive 主张。
- **Ablation**：SF victim policy 与 InvBlk 长度有独立 sweep；拓扑实验区分 bandwidth 与 hop-based latency，并报告 Xerxes 自身 simulation cost（图 12），说明工具开销可控。
- **缺口**：PBR/DMC 无硅片验证，仅理论对照；端到端应用仅 2 个 SPEC + 若干 trace replay，不含多租户或 OS 页迁移路径；与 [[Cylon-FAST26|Cylon]] 等 CXL-SSD 全系统路径正交，未覆盖 storage endpoint。

### 系统性缺陷

- **尾延迟与可预测性**：报告平均延迟与吞吐为主，tree/chain 高 hop 下 latency 可达低 hop 的 **2×**，但 P99/P999 与 coherence storm 未表征。
- **资源隔离**：多 requester 实验存在，但未讨论 QoS、公平性或 malicious peer 对 DCOH 的压力。
- **运维与可观测性**：开源框架与 artifact 完整，但论文未讨论配置错误、routing table 不一致等运维风险。
- **集成复杂度**：gem5 wrapper 路径依赖 SLICC 与 MemCtrl 语义，移植到新 gem5 版本或 non-gem5 CPU 模型的工程成本**论文未量化**。

## 局限与 Future Work

- **局限 1**：CXL 3.1 的 PBR、DMC 缺乏真实硬件对照，当前验证是「组件校准 + 理论路径」组合，对复杂 multi-switch 争用下的绝对数值仍需谨慎解读。
- **局限 2**：device 侧仅实现一种 inclusive SF 与若干 victim/InvBlk policy，未覆盖 HDM-D、多种 DCOH 微架构或 security/RAS 特性。
- **局限 3**：与 MESS/CXLMemSim 的对比凸显 accuracy–speed 光谱，但最快配置（MESS）在 mcf 上误差极大，论文未给出「何种研究问题应用哪种工具」的决策树。
- **Future work 1**：按作者 §6，扩展 interconnect/device layer 以支持 Unified Bus（UB）等同类 coherent fabric，并用 UMMU 替换 SF——可客观验证「Xerxes 模块化是否真能跨协议复用」。
- **Future work 2**：在 Xerxes 上接入 OS 级 memory tiering / disaggregated FS（与 [[DMTree-FAST26|DMTree]]、[[CetoFS-FAST26|CetoFS]] 方向结合），测量 page migration 与 DMC back-invalidate 的交互延迟。
- **Future work 3**：当 CXL 3.1 硬件可用后，用同一拓扑与 SF policy 实验复现仿真预测，量化 predictive gap——这是检验本文最核心的 falsifiable 命题。

## 相关

- **相关概念**：[[CXL]]、[[PCIe]]、[[Port-Based-Routing]]、[[Device-Managed-Coherence]]、[[Snoop-Filter]]、[[Disaggregation]]、HDM-DB、PBR
- **同类系统**：MESS、CXLMemSim、[[gem5]]、Garnet、DRAMsim3、SimpleSSD、[[Cylon-FAST26|Cylon]]、[[FEMU]]
- **同会议**：[[FAST-2026]]
- **对比**：Xerxes 专注 **CXL fabric + coherence 协议** 的 predictive 仿真；MESS/CXLMemSim 偏 **应用级 delay injection**；[[Cylon-FAST26|Cylon]] 偏 **CXL-SSD full-system**；NUMA emulation 仅适合早期 capacity 粗估。
