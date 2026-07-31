---
type: paper
name: SBB
full_title: "SBB: Eliminating Centralized Bottlenecks in Userspace Network Runtime"
authors: [Kang Hu, Shuqi Dong, Chuandong Li, Ran Yi, Zonghao Zhang, et al.]
venue: OSDI
year: 2026
tags: [networking, userspace-networking, scheduling, user-interrupt, multicore]
source_pdf: "[[osdi26-hu-kang.pdf]]"
source_md: "[[osdi26-hu-kang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 消除用户态网络运行时的中心化瓶颈（OSDI 2026）

> **原题**：SBB: Eliminating Centralized Bottlenecks in Userspace Network Runtime

> **一句话总结**：SBB 发现用户态网络 runtime 的 timer、NIC monitor 与 dispatcher 在多核下分别限制 preemption、CPU allocation 与 load balancing，于是用 per-core timer/NIC User Interrupt 去中心化通知，并以 task stealing 处理暂态不均衡、flow migration 处理持续不均衡；48 cores 同一 tail-SLO 下吞吐较 baseline 高 1.7–5.2 倍。

## 问题与动机

微秒级 RPC runtime 不只要绕过 kernel，还要同时完成三种 scheduling：preempt long request 防 head-of-line blocking；在 latency-critical（LC）与 best-effort（BE）间动态分 core；把 request 均衡到 worker。Shinjuku/Caladan 等通常分别依赖 central timer、monitor/iokernel 或 dispatcher。

中心组件在 16–48 cores 变成 serial bottleneck：dispatcher 每包约 200ns 将全系统封顶约 5 MRPS；多 dispatcher 又把 imbalance 移到 group 间；central UIPI 的发送率也受 NUMA 上限。SBB 的挑战是去中心化后仍维持接近 shared queue 的 scheduling quality。

## 关键观察 / 隐含假设

- **观察 1：preemption 和 CPU allocation 的中心化根因是缺少可直达用户态的 device event。** UINTR 可把 LAPIC timer 和 NIC interrupt 分别送到 owning worker，无需 timer/monitor core（§3.2）。
  - **依赖假设**：Intel Sapphire Rapids UINTR 与 NIC interrupt routing 可用，interrupt overhead 小于释放的 CPU/latency 收益。
  - **可能失效场景**：不支持 UINTR 的 CPU/NIC、virtualized cloud 隐藏 APIC，或超高 packet rate 导致 interrupt storm。
- **观察 2：task stealing 只适合 burst 型暂态 imbalance。** RSS 把过多 persistent flow 分到某 core 时，请求反复被 steal，cache-coherence traffic 激增；flow migration 应修正长期 assignment（图 4）。
  - **依赖假设**：可用短时间统计区分 temporary/persistent，并可及时重编 NIC steering。
- **观察 3：中心化并不天然比去中心化质量高。** 两级 policy 的 simulation 接近 JBSQ(2)，说明 local queue 在适当 migration 下可逼近 shared FCFS（图 4）。
  - **依赖假设**：flow size/distribution 与模拟和评测类似，migration 不破坏 packet ordering/connection state。
- **假设 1：微秒服务可改写为 SBB callback/runtime interface。**
  - **证据强度**：中；[[RocksDB|RocksDB]]/Memcached 与 synthetic 可移植，但完整 TCP features 和 legacy compatibility 未证明。

## 核心方法

每个 worker 独占 CPU、local run queue、timer 与 NIC Rx/Tx queue。Linux patch 将 LAPIC timer interrupt 通过 UINTR 直接交给当前 userspace worker，在 quantum 到期时自我 preempt；NIC arrival 也形成 UINTR，若 core 正跑 BE 即快速切回 LC。NIC automask 让 handler 只置 pending flag，bottom half 在 worker context dequeue/parse/execute，避免高负载 interrupt storm（图 5–6）。

load balancing 第一层用增强 stealing 处理局部 burst：idle worker 直接从 busy queue 取 packet，避免被偷 task 再入队和 multi-stealing，并降低无效探测/同步。第二层按 worker queue/flow load 识别持续热点，通过 NIC flow steering 把整个 flow 迁到较空 core，减少未来 stealing（§4.5）。

原型基于 DPDK 25.07 和 Linux 6.12.20，kernel patch 2,095 LOC、runtime 4,343 LOC，并实现轻量 TCP/UDP stack。timer 与 NIC 使用两种 UINTR vector，在 top/bottom-half 流程中协调 priority 和 masking。

## 设计取舍

- **scalability 换硬件依赖**：移除 central core，但绑定新 UINTR/interrupt-routing 能力和 kernel patch。
- **CPU efficiency 换 packet latency**：NIC UINTR 相对 polling 增加 0.49µs（E810），却允许 core 跑 BE；低 latency 极限 workload 可能不接受。
- **locality 换 work conservation**：stealing 会产生 inter-core coherence，flow migration 又有 NIC update 与 packet reordering 风险。
- **应用性能换兼容性**：需要 rewrite 到 runtime hooks，轻量 stack 缺 congestion control 等生产 TCP feature。
- **边界条件**：48-core 单 [[NUMA|NUMA]]、短 RPC、RSS flow imbalance 与 LC/BE 共置时最合适；64+ cores、跨 NUMA 或大量单包 flow 时同步成本增大。

## 实验与结果

- 16 workers、Fixed(1)、p99.9 slowdown SLO 50倍下 SBB 达 9.7 MRPS，较 TQ/Concord/Shinjuku 高 90%以上；High/Extreme-Bimodal 分别高 30%以上/40%以上（图 8a–c）。
- RocksDB light/heavy-tail 同 SLO 下吞吐较 prior work 高 20%–80%（图 8d–e）。LC+BE 共置、p99.9 少于 100µs时，LC throughput 较两种 Caladan 高 28%/15%，BE CPU efficiency 接近 Caladan-DL且 tail 更低（图 9）。
- Fixed(1) 从 16/32/48 workers 吞吐约 9.5/19/26.5 MRPS，即 48-core 为 2.8 倍；中心化 baseline 16→32 几乎不增长（图 11a）。bimodal 16→32 达近线性，48 仍较32高 35%以上（图 11b–c）。
- Memcached+swaptions、p99.9 50µs下 SBB 8→16 MRPS，Caladan 6→10.2 MRPS且32-core接近上限（图 11d）。
- E810 上 UINTR 相对 polling 多 0.49µs、占 end-to-end 4.7%；ConnectX-5 上多 8.1%。增强 stealing 单独使吞吐提高 30%，flow migration 进一步消除持久热点（图 12–13）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 去中心化 runtime 在多核下显著扩展 SLO throughput | 图 11：16→48 workers 9.5→26.5MRPS | 单机最多48 workers、特定NIC/CPU | 强 |
| UINTR 可低成本支持 CPU sharing/preemption | 图 12/表4：相对polling +0.49µs | E810/ConnectX-5、1µs synthetic app | 中 |
| 两级 balancing 优于纯 stealing | 图 4、13：接近JBSQ(2)，enhanced stealing +30%后migration再提升 | simulation与RSS flow workload | 中 |
| 实际 KV workload 也有收益 | 图 8–9：RocksDB +20%–80%，共置 +15%–28% | 简化 network stack、单机 load generator | 中 |

## 批判性分析

### 论证链条

论文把三个 central component 分别测出上限，再给 timer/NIC mechanism 与 two-level policy，论证映射清晰。最反直觉贡献是“decentralized 不必牺牲 balancing quality”，simulation 和 ablation 支持这一点。但所有三类 scheduling 同时端到端对统一强 baseline 的比较有限，因为现有系统本就只覆盖部分功能。

### 假设压力测试

UINTR 在 VM、不同 APIC/IOMMU/NIC 下未必可路由；interrupt moderation 会在 burst 中引入 wakeup delay。flow migration 与 stateful TCP/QUIC ordering、RSS hash 和 NIC table 容量可能冲突。跨 NUMA stealing/migration 的 cache/UPI 成本会高于当前单 socket。流量含大量 elephant flow 时，一个 flow 仍不能并行到多 core。

### 实验可信度

synthetic dispersion、RocksDB/Memcached、LC/BE、三种 scheduling 单项 scaling、机制 microbenchmark 与 policy ablation 覆盖广。公平性上使用统一轻量 stack有利，但也避开 Linux/full TCP 的复杂性；baseline各自只在擅长维度比较，硬件只到48 cores且SBB作者预期64后仍增长但未测。

### 系统性缺陷

2,095-line kernel patch、应用 rewrite和自有 stack提高部署成本。论文未充分讨论 worker crash、NIC reset、flow migration rollback、interrupt loss、priority inversion与multi-tenant isolation。去中心化状态也使全局 observability/debugging 更难，错误 local load estimate 可能振荡。

## 局限与后续工作

- **局限 1**：依赖 UINTR-capable Intel platform，跨 architecture/VM/SmartNIC 可移植性未知。
- **局限 2**：48 cores 后已出现 sublinear scaling，跨 NUMA 和完整 transport stack 未验证。
- **后续工作 1**：在 64–192 cores/多 NUMA 上分解 stealing、migration、UINTR 与 NIC-table cost，报告 P99.9 与 coherence traffic。
- **后续工作 2**：加入完整 TCP congestion control/QUIC，验证 flow migration 下 packet ordering、retransmission和 connection correctness。
- **后续工作 3**：故障注入 timer/NIC interrupt loss、worker crash 和 NIC reset，以 recovery latency、dropped request 与 SLO violation 衡量健壮性。

## 相关

- **相关概念**：[[Kernel-Bypass-Networking]]、[[User-Interrupt]]、[[Work-Stealing]]、[[Flow-Migration]]
- **同类系统**：[[Shinjuku]]、[[Caladan]]、[[Concord]]、[[DPDK]]
- **同会议**：[[OSDI-2026]]
