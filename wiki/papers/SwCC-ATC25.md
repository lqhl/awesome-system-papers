---
type: paper
name: SwCC
full_title: "SwCC: Software-Programmable and Per-Packet Congestion Control in RDMA Engine"
authors: [Hongjing Huang, Jie Zhang, Xuzheng Chen, Ziyu Song, Jiajun Qin, Zeke Wang]
venue: ATC
year: 2025
tags: [rdma, congestion-control, smartnic, fpga, risc-v, programmable-nic]
source_pdf: "[[atc2025-huang-hongjing.pdf]]"
source_md: "[[atc2025-huang-hongjing]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-17
---

# SwCC: Software-Programmable and Per-Packet Congestion Control in RDMA Engine (ATC 2025)

> **一句话总结**：SwCC 将 RISC-V CC core 集成到 FPGA RDMA engine。U280/100Gbps testbed 中，其 control-loop RTT 与 ConnectX-5 都约 **3.1 µs**；这说明相近而非一般性优于 ASIC。五种代表 CCA 的实现为 **95–164 LoC**。

## 问题与动机

论文要解决的是 [[RDMA]]/RoCE 数据中心里的一个张力：拥塞控制算法迭代很快，但真正跑在线上的 RDMA NIC 往往只支持少数 hardwired CCA。ASIC NIC 的 CC loop 很短，却很难在制造后升级；CPU/Soft-RoCE 很容易改算法，却要穿过 PCIe、内核栈和软件调度，控制环延迟进入十几到几十微秒；FPGA SmartNIC 能低延迟运行 transport，但用 Verilog/Chisel/P4 写 CCA 的工程门槛太高；BlueField-3 PCC 这样的 SoC SmartNIC 支持 C-style 编程，但 DPA memory/cache 和单线程性能无法支撑 per-packet CCA。

作者的核心 claim 边界比较明确：SwCC 不是提出新的 CCA，而是提出一个可编程 RDMA engine substrate，让开发者能用 C 写不同类别的 CCA，并且不牺牲 NIC-offloaded CC 的低 control-loop latency。这个 claim 对 ML/datacenter workload 尤其重要，因为 burstier traffic、400/800 Gbps line rate 和 PFC avoidance 会让“控制反馈多久到达 sender”变成性能和 queue buildup 的主导因素之一。

动机实验展示，手动增加 CNP processing delay 会显著拉长 switch queue draining time；论文给出的对比是 CPU-based CC 的 control-loop delay 约 23 µs，可能让 queue draining time 比 NIC-based CC 增加 7.8×。所以 SwCC 的目标不是单纯“让 SmartNIC 可编程”，而是在 per-packet trigger interval、控制环 RTT、算法覆盖面和编程门槛之间找一个实现上可落地的交点。

## 关键观察 / 隐含假设

- **观察 1：per-packet CC 的时间预算比通用 SmartNIC memory latency 更小。** 100 Gbps line rate 下 1 KB packet interval 只有 89 ns，而 BlueField-3 DPA memory access 被论文描述为约 300 ns；如果每个 packet event 都依赖普通 memory/cache path，RISC-V core 会被 memory stall 吃掉。
  - **依赖假设**：未来重要 CCA 需要 packet-level 或接近 packet-level 的触发，而不只是 rate-based periodic controller。
  - **可能失效场景**：如果生产部署主要使用 coarse-grained rate CCA，或 NIC/SoC memory subsystem 已经做到足够低延迟，SwCC 的 QP-aware memory 复杂度收益会下降。

- **观察 2：多数 CCA 可以拆成 TX function 与 RX function。** RX side 主要处理 ACK/CNP/token/INT 等事件并更新 QP context；TX side 主要根据 QP context 决定是否发包、如何发包。这个拆分让每个 core 只连接 TX 或 RX 路径，降低 FPGA routing pressure。
  - **依赖假设**：CCA 的共享状态可以收敛到 per-QP context，且 TX/RX 并发访问可用简单 run-to-completion + hardware lock 处理。
  - **可能失效场景**：跨 QP 的全局 fairness、tenant-level policy、multi-path coordination 或需要复杂 shared state 的 CCA，可能突破“每个 event 只处理一个 QP context”的简化模型。

- **观察 3：CC core 访问的数据结构很规整，不需要通用 cache。** 事件触发前，硬件已经知道 QPN、packet header、opcode、event type 等信息；SwCC 因此把 QP context 和 packet header 预先写入 RISC-V CSR，让 core 以 1-cycle CSR access 读写 hot data。
  - **依赖假设**：CCA hot state 足够小，能放进 64 个 reserved CSR 和 128B QP context slot；复杂 CCA 不会频繁访问 large per-flow history。
  - **证据强度**：中。论文用 DCQCN/TIMELY/HPCC/Swift/Homa 覆盖 ECN、timestamp、INT、token 和 rate/window/credit 策略，但这些仍是作者选择的代表性 CCA，不等价于所有未来算法。

- **假设 1：extensible CC header 的部署成本可以接受。** SwCC 允许在 RoCEv2 BTH 后追加 0-64B custom header，非 INT CCA 可让 switch 当 payload 处理；但如果 CCA 需要远端自定义 metadata，通信双方都要 SwCC-enhanced NIC，INT CCA 还需要 programmable switch。
  - **证据强度**：中。机制完整，但评估主要证明可实现和性能，较少讨论 partial deployment、interoperability、MTU/header overhead 和生产运维。

- **假设 2：FPGA prototype 上的 co-design 规律能外推到 ASIC。** 论文在 U280 FPGA 上实现 250 MHz SwCC，并用 simulation 估计 ASIC 设计在 800 Gbps 下 QP-aware memory 只需 2.4 GHz，而 naive cache 需 8 GHz。
  - **证据强度**：弱到中。FPGA 实测说明设计方向有效，但 ASIC frequency、power、area、verification、firmware update path 和 vendor integration 仍未被实证覆盖。

## 核心方法

SwCC 把可编程 CC controller 放进 [[RDMA]] engine 内部，而不是放在 host CPU、普通 SoC DPA 或纯 HDL transport 里。硬件路径包括 RX parser、packet retransmission、packet filter、RX CC、TX CC、WQ handler、DMA、header/packet fabricator 和 QP-aware memory subsystem；软件侧暴露 `PktHeader`、`QPContext`、`pollEventSync`、`updatePkt`、`updateContext`、`postEvent` 等 API，让开发者写 TX/RX C functions，而不直接处理低层 NIC wiring。

第一个关键设计是 **TX/RX separated multi-core**。SwCC 用一组 TX CC cores 和一组 RX CC cores 分别运行 CCA 的发送侧和接收侧逻辑，QPN mod N 把每个 QP 映射到固定 TX/RX core。这个设计回应观察 2：多数 CCA 的逻辑天然能切成 TX/RX 两半，因此单个 core 不必连接全部 NIC resources。实验里，TX/RX separation 把 CC core routing wires 减少约 50%，在 Vivado 默认策略下最高提升 16% achievable frequency。

第二个关键设计是 **QP-aware memory subsystem**。它不把 QP state 当普通 cache line，而是让每个 128B slot 保存一个 QP 的完整 context；on-chip table 总计 128 KB，可容纳约 1K QP context，off-chip/on-NIC memory 用作 backing store，并用简单 LRU swap。这里的核心不是 cache policy 多聪明，而是数据模型更贴近 RDMA CC：CC event 几乎总是围绕当前 QPN 的 context 展开。

第三个关键设计是 **CSR-based fast path + QPN prefetch**。事件触发前，硬件把 event type、QP context 和必要 packet header 字段写入 RISC-V CSR；CC core 执行时直接操作 CSR，避免 runtime 访问 QP context table。RX path 在 RX parser 看到 QPN 时就提前 prefetch context，尝试用 parser、PSN update 和 packet filter 的约 60 ns 处理时间遮住 memory miss；TX path 在 WQ handler slicing request 时也用 QPN hint prefetch。这回应观察 1 和观察 3：per-packet controller 不能被普通 memory access 支配。

第四个设计是 **可扩展 CC signal 与 selective triggering**。SwCC 在 RoCEv2 BTH 后加入最多 64B extensible CC header，支持 ECN、timestamp/RTT、token、INT 等信号；packet filter 读取 opcode，由用户用 32-bit one-hot CSR 指定哪些 packet type 触发 RX event。这样，DCQCN 可以围绕 CNP/DATA/timer，TIMELY/HPCC 可围绕 ACK，Homa 可围绕 DATA/GRANT/RESEND/BUSY，不必让所有 packet 都进 CC core。

最后，SwCC 用 hardware lock 处理 TX/RX cores 对同一 QP context 的并发访问。事件是 run-to-completion，硬件只在 entry 未被占用时触发 core，core 完成后释放 lock bit。这是一个很“worst-is-better”的选择：不暴露软件 atomic，也不支持复杂 lock dependency，但换来实现简单和低 per-event overhead。完整实现细节回 [[atc2025-huang-hongjing]]。

## 设计取舍

- **可编程性 vs NIC datapath 专用化**：SwCC 让 CCA 用 C 写，但不是通用 SmartNIC runtime。它把可编程边界限制在 TX/RX CC functions、QP context、PktHeader 和几个 API 内，牺牲通用性换取 per-packet 低开销。
- **低延迟 vs 状态模型限制**：CSR fast path 很快，但天然偏向 small, per-QP, fixed-layout state。需要大历史窗口、复杂 ML policy、跨 flow optimization 的 CCA 可能不适合。
- **灵活信号 vs 兼容性成本**：不使用 extensible header 的 CCA 可以和现有 commercial NIC 通信；一旦 CCA 需要自定义 metadata，两端都要 SwCC-like NIC，INT 场景还要 programmable switch。
- **简单 concurrency vs policy 表达力**：hardware lock + run-to-completion 避免软件同步开销，但如果 controller 需要跨 QP atomic update、全局 rate allocator 或 tenant-level coordination，这个模型会变脆。
- **FPGA prototype vs production NIC**：U280 原型证明 datapath 和 timing 可行，但真实 NIC 产品还要面对 ASIC verification、firmware delivery、multi-tenant isolation、operator tooling 和长期兼容性。

## 实验与结果

**指标、基线与边界**：control-loop RTT、RDMA WRITE throughput、FCT；SwCC vs ConnectX-5 RoCE/Soft-RoCE/naive cache；U280 FPGA、100Gbps testbed，Soft-RoCE FCT 单独在 10Gbps（§5）。

- **平台**：三台服务器通过 Wedge100BF-32X P4 switch 连接；每台服务器有双 Intel Xeon Silver 4214、256GiB DDR4、Xilinx U280 FPGA 和 Mellanox ConnectX-5。SwCC 基于 FpgaNIC 复用 PCIe/CMAC，RoCEv2 stack + riscvmini 3-stage RISC-V core，逻辑频率 250 MHz，约 6K 行 Chisel3。
- **control-loop delay**：1 KB RDMA WRITE 下，SwCC 和 ConnectX-5 RoCE 的平均 control-loop delay 都约 3.1 µs；Soft-RoCE 明显更高且抖动更大，论文摘要和动机中给出约 23 µs 量级。
- **throughput**：SwCC-8 与 RoCE-8 都在 512B 以上 packet size 达到 100 Gbps line rate；SwCC-1 在单 flow/core 设置下约为 RoCE-1 的 1.1-1.5×。Soft-RoCE-24 最高只有约 24 Gbps。
- **TX/RX separation**：两 core 情况下，functional separation 让 routing wires 减少约 50%；不同 core 数下最高提升 16% assessed Fmax。
- **QP-aware memory**：在 1K/10K/100K QP 随机访问实验中，相比 128 KB naive 4-way cache，QP-aware memory 的 QP context access time 至少降低 50%；DCQCN controller execution cycles 比 Soft-RoCE 少约 3×，比 BlueField-3 PCC 少约 11.4×。
- **small-packet bottleneck**：100K flows、每 flow 1K 个 1 KB RDMA WRITE 请求时，单 pair CC core 下 naive cache 的小包 throughput 约为 QP-aware memory 的 40%，说明 memory stall 确实会变成 controller bottleneck。
- **programmability**：五个代表 CCA 都能用少于 200 行 C 实现：TIMELY 102 LoC、DCQCN 140 LoC、HPCC 148 LoC、Swift 164 LoC、Homa 95 LoC，覆盖 rate/window/credit 和 ECN/timestamp/INT/token。
- **resource usage**：SwCC-1 占 U280 约 51K LUTs、62K REGs、220 BRAMs、4 URAMs；SwCC-8 占约 112K LUTs、124K REGs、220 BRAMs、32 URAMs，LUT 占比仍低于 10%。
- **end-to-end congestion**：SwCC vs RoCE 的 DCQCN 对比中，RoCE 在拥塞后会暂停发送约 90 µs，SwCC 按 DCQCN rate adjustment 继续调节，FCT 略优；SwCC vs Soft-RoCE 在 10 Gbps 设置下，Soft-RoCE 在 TIMELY/DCQCN/HPCC 上的 FCT 分别约为 SwCC 的 14×、39×、42×。

## Claim–Evidence Map

| Claim | Evidence | Metric / baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| FPGA SwCC 的 control loop 与 CX5 可比 | 两者约 3.1 µs；≥512B 达 100Gbps | U280/100Gbps；vs ConnectX-5 RoCE | §5.2–5.3 | high |
| 单 flow 优势不等于 equal-core 对比 | SwCC-1 为 RoCE-1 的 1.1–1.5×；SwCC-8/RoCE-8 line rate | TX/RX RISC-V 对比 CX5 1 PU；core allocation 不同 | §5.3 | high |
| QP-aware memory 的收益依赖 QP/flow 配置 | access time ≥50% lower；naive cache throughput约40% | 1K/10K/100K QPs；100K flows、1K×1KB writes、one core pair | §5.4，Fig.11 | high |
| ASIC 数字是模拟频率需求 | naive up to 8GHz vs QP-aware 2.4GHz | single-QP 1KB、800Gbps simulated potential ASIC | §5.4，Fig.11d | high |
| Soft-RoCE FCT 结论只在 10Gbps | 14×/39×/42×；RTT约30µs vs5µs | TIMELY/DCQCN/HPCC、10Gbps | §5.7.2，Figs.13–14 | high |

## Critical Analysis

### 论证链条

论文的 observation → design → result 链条总体闭合。作者先证明四类现有方案分别缺低延迟、缺可编程性、缺灵活性或缺 per-packet 性能，然后把瓶颈具体化为 RISC-V core 的 memory/context access，再用 QP-aware memory、CSR fast path 和 QPN prefetch 降低 cycles。实验也确实围绕这些关键设计做了 ablation：TX/RX separation 测 frequency/routing，QP-aware memory 测 access time/cycles/throughput，API/CCA 覆盖用 LoC 和 CCA 种类证明。

更强的地方在于它没有声称“软件随便写也能快”。SwCC 实际上把软件自由度压缩到 RDMA CC 最常见的数据路径形状里：per-QP context、packet/event header、TX/RX function、run-to-completion。这让 claim 更可信，也让设计边界更清楚。

主要跳步在“nearly all kinds of existing CCAs”和“ASIC design can easily scale”两处。前者由五个代表算法支撑，但没有覆盖需要 global coordination、multi-path state、complex scheduling 或 ML policy 的 CCA；后者由 frequency simulation 和资源估算支撑，但没有 ASIC 实作、power model、area layout、verification 或 firmware update evidence。

### 假设压力测试

workload assumption 是这篇论文最关键的压力点。SwCC 特别适合大量 QP、低 RTT、packet-level signal、small message、burst-sensitive 的 RDMA 网络。如果 workload 主要是大 message bulk transfer，或 CCA 触发周期本来就是几十微秒，per-packet programmability 的收益会小很多。相反，如果 workload 有极大量 concurrent QP，128 KB on-chip QP table 和 LRU swap 行为会更重要，论文虽然测到 100K QP random access，但没有展示 skewed/tenant-mixed/long-tail QP churn 下的 tail behavior。

hardware assumption 也比较强。U280 FPGA、ConnectX-5、Wedge100BF P4 switch 组成了清晰 testbed，但真实云网络可能有多代 NIC、不同 switch support、PFC/ECN 配置差异、multi-tenant isolation 和运维策略。SwCC 的 extensible header 对 INT-based CCA 尤其依赖 programmable switch；对需要双方识别 custom metadata 的 CCA，则会遇到 incremental deployment 问题。

correctness/SLO assumption 在论文里相对少。SwCC 实现了 packet retransmission 和 QP context lock，但没有深入讨论故障恢复、core crash/hang、bad user CCA、event FIFO backpressure、context corruption、tenant 隔离、debug/telemetry 或在极端拥塞时的 tail latency。一个可编程 NIC substrate 要进入生产，通常需要比“能跑 CCA”更多的 guardrails。

### 实验可信度

基准选择是合理的：ConnectX-5 RoCE 代表 hardwired ASIC NIC，Soft-RoCE 代表 CPU software flexibility，RDMA-HLS/Tonic/NanoTransport 代表 FPGA/HDL path，BlueField-3 PCC 代表 SoC SmartNIC programmable path。作者还实现了五种 CCA，并给了 artifact appendix 和 GitHub 入口，复现实验路径比很多系统论文更完整。

但公平性有两个限制。第一，SwCC 与 RoCE 的 end-to-end 对比无法运行完全相同的 NIC CCA，因为 commercial NIC 内部算法不公开；作者也承认不能 devise identical algorithm。因此 SwCC 略优于 RoCE 的 FCT 不应被读成算法层面胜利，更应读成“SwCC 没有因为可编程性显著变慢”。第二，Soft-RoCE 对比在 10 Gbps 下运行，因为它无法到 100 Gbps line rate；这能证明 CPU path 很慢，但不能完全刻画 high-speed production RDMA 的所有竞争方案。

metrics 覆盖了 latency、throughput、frequency、resource、LoC 和简单 end-to-end congestion behavior。缺口是 tail latency under high concurrency、multi-tenant fairness、fault/recovery、observability、power/cost-normalized comparison，以及真实 production traces。尤其对一个 programmable substrate，bad CCA 或 heavy CCA 的 admission control 很重要，论文没有系统讨论。

### 系统性缺陷

SwCC 的最大系统风险是“可编程性制造了新的责任边界”。开发者可以写 CCA，但谁验证它不会死循环、不会写坏 context、不会饥饿某类 QP、不会在拥塞时放大队列？论文的 API 很简洁，但没有 sandbox、static checking、runtime quota 或 rollback 机制。

第二个风险是运维和可观测性。CC bug 往往表现为 tail latency、queue buildup、PFC storm、吞吐振荡或偶发 FCT regression；SwCC 把这部分逻辑放到 NIC RISC-V core 里后，需要 operator 能看到 event rate、core stall、QP table miss、lock contention、header parse error 和 per-CCA decision。论文没有给出这类 telemetry。

第三个风险是兼容性。SwCC 兼容现有 NIC 的前提是所选 CCA 不需要 extensible header；否则要双端升级。INT-based CCA 还需要 programmable switch 改写 metadata placement，因为现有 switch 通常只能把 INT metadata 加到 packet 末尾。这会让“支持各种 CCA”和“容易部署各种 CCA”之间出现差距。

## 局限与 Future Work

- **局限 1：生产 workload 覆盖不足。** 论文用 microbenchmark、dumbbell congestion 和几个 CCA 证明机制有效，但没有使用真实 data center RDMA traces、multi-tenant workload 或 ML training/serving burst trace。
- **局限 2：可编程安全性未展开。** 论文展示 API 与 LoC，但没有讨论 CCA verification、resource quota、bad program isolation、rollback、debug 和 operator-facing telemetry。
- **局限 3：ASIC 外推仍是估算。** 800 Gbps 结果来自 simulation/frequency requirement，缺少 ASIC area/power/timing closure 和 verification cost。
- **局限 4：compatibility 取决于 CCA。** 纯 ECN/rate-style CCA 更容易渐进部署；token/INT/custom header CCA 需要远端 SwCC NIC 或 programmable switch。
- **Future work 1：用生产 RDMA trace 压测 QP-aware memory。** 在 skewed QP popularity、tenant churn、mixed message size 和 heavy-tail flow lifetime 下测 QP table miss、lock contention、event queueing 和 tail latency。
- **Future work 2：给 CCA program 加 safety contract。** 例如限制 event handler cycles、禁止未声明 context access、静态检查 TX/RX state ownership，并在 NIC 上暴露 per-CCA stall/drop/backpressure counters。
- **Future work 3：研究 partial deployment 策略。** 定量比较无 custom header、双端 SwCC、INT programmable switch 三种模式的兼容性、性能和运维成本。
- **Future work 4：ASIC-style cost model。** 把 core count、CSR count、QP table size、off-chip memory bandwidth、power 和 area 纳入设计空间，寻找不同 line rate 下的最小可行配置。

## 相关

- **相关概念**：[[RDMA]]、[[Congestion-Control]]、[[SmartNIC]]、[[FPGA]]、[[RISC-V]]、[[RoCEv2]]、[[PFC]]、[[INT]]
- **同类系统**：[[BlueField-3]] PCC、[[Soft-RoCE]]、[[ConnectX-5]]、Tonic、NanoTransport、RDMA-HLS、[[FpgaNIC]]
- **相关算法**：[[DCQCN]]、[[TIMELY]]、[[HPCC]]、Swift、Homa
- **同会议**：[[ATC-2025]]
