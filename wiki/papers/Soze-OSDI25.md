---
type: paper
name: Soze
full_title: "Söze: One Network Telemetry Is All You Need for Per-flow Weighted Bandwidth Allocation at Scale"
authors: [Weitao Wang, T. S. Eugene Ng]
venue: OSDI
year: 2025
tags: [datacenter-network, weighted-fairness, int, congestion-control, transport]
source_pdf: "[[osdi25-wang-weitao.pdf]]"
source_md: "[[osdi25-wang-weitao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-17
---

# Söze: One Network Telemetry Is All You Need for Per-flow Weighted Bandwidth Allocation at Scale (OSDI 2025)

> **一句话总结**：Söze 以每 flow 的 path maxQD INT signal 驱动 sender 端加权分配。22 个 TPC-H DAG jobs 的 NS-3 模拟中，作者报告 weighted Söze 的 JCT 为 baseline 的平均 **0.79×**、最低 **0.59×**；这些是 JCT factor，不是“降低 79%/59%”。

## 问题与动机

现代云应用需要按权重分配瓶颈带宽（关键路径、straggler、coflow 等），但交换机 per-flow 队列与权重粒度受限，集中式 allocator 通信与计算成本高。瓶颈随路径与竞争流变化，难以全局最优且快速反应。

## 关键观察 / 隐含假设

- **观察 1**：INT 的 queueing delay 是所有 sender 共享的标量信号；其稳态值可编码 weighted fair-share，且对 arrival rate 与 B 的关系可去中心化验证（式 3–4）。
  - **依赖假设**：交换机支持 INT（至少 queueing delay 字段），ACK 路径能带回 telemetry；瓶颈在观测的那一跳。
  - **可能失效场景**：多瓶颈路径上单一 telemetry 可能不足以代表全局公平点；非 commodity INT 字段时需改映射。
- **观察 2**：把 weighted allocation 拆成「链路饱和」+「各流 rate/weight 相等」两条件，每流只需 O(1) 信息而非 O(n) 交换权重和。
  - **依赖假设**：收敛算法参数（m、p、α、β）与 RTT/CWND 更新间隔匹配数据中心 RTT 尺度。
  - **可能失效场景**：极短流或权重剧烈抖动时收敛时间可能违反 agility 目标。
- **假设 1**：目标 delay 函数 T(x) 单调递减，可与观测 delay 比较并乘性调速（Algorithm 1）。
  - **证据强度**：强——单交换机与多跳扩展有收敛证明（附录）。

## 核心方法

单交换机：用 INT queueing delay 作广播信道；每流按 `U(r/w, D)` 调整速率直至满足式 1 的 weighted fair allocation。

任意拓扑：在瓶颈 hop 应用相同机制（§3.2），流无需知道拓扑。

实现：可嵌入 TCP/eRPC；每包或每 RTT 更新。

## 设计取舍

- **取舍 1**：不用交换机精确 per-flow WFQ，用端主机算法换 ASIC 队列限制与可编程调度复杂度。
- **取舍 2**：依赖 INT 语义而非显式权重聚合，牺牲对非 INT 环境的可移植性。
- **边界条件**：权重细粒度、主机侧 instant 调整；交换机仅 tag delay。

## 实验与结果

**指标、基线与边界**：job completion time、convergence、utilization；weighted Söze vs non-weighted/fair allocation、Timely 或 water-filling；NS-3 fat-tree TPC-H DAG jobs 或指定 eRPC testbed workload（§5）。

- 22 个 TPC-H DAG jobs 的 NS-3 fat-tree simulation 中，weighted Söze JCT 为 baseline 的平均 **0.79×**、最低 **0.59×**；single execution-path jobs 无收益（§5，Fig.11）。
- 10k flows、K4→K16 fat-tree sweep 中 average convergence **0.3 ms**（约 10 RTTs）；同 1024-server topology 上 water-filling solve 从 10 flows 的 **1.81 ms** 增至 1M flows 的 **31.1 s**（§5，Fig.19）。
- eRPC 三 sender incast churn 中 Söze 的 utilization/收敛优于 Timely，但论文未给通用倍率（§5，Fig.12）。

## Claim–Evidence Map

| Claim | Evidence | Baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| weighted Söze 改善被测 TPC-H DAG JCT | 0.79× average、0.59× minimum JCT factor | 22 jobs、NS-3 fat-tree、critical-path-distance weight；vs non-weighted policy | §5，Fig.11 | high |
| 收敛扩展性在模拟拓扑下较好 | 10k flows 0.3 ms≈10 RTTs；water-filling 1.81 ms→31.1 s | K4→K16/1024 hosts、flow-count sweep | §5，Fig.19 | high |
| 动态事件处理来自特定 microbenchmark | 10 ms weight changes、20 ms bottleneck change，在 10 RTTs 内处理 | 6-flow/two-switch、WRR+delay-AIMD | §5，Fig.17 | high |
| eRPC incast 结果仅覆盖 3-host churn | 更高 utilization/更快收敛 | 每 50 s add/terminate flow；vs Timely | §5，Fig.12 | high |
| 控制开销是 telemetry/implementation 尺度而非 runtime gain | 2-byte maxQD field、Tofino 9 LoC、Linux 241 LoC | INT-capable switches、ACK feedback | §3–4 | high |

## Critical Analysis

### 论证链条

「delay 稳态 ↔ 链路饱和」+「delay 编码 wfs」→ 分布式乘性更新 → weighted MMMF，数学链条在单跳清晰；多跳依赖瓶颈识别假设，实验覆盖需对照论文 §3.2 拓扑实验。

### 假设压力测试

多瓶颈、ECMP 重路由、incast 与背景 TCP 竞争时是否仍收敛？权重动态变化快于 RTT 尺度时的稳定性论文部分讨论。INT 精度与量化误差对 fine-grained weight 的影响未充分 ablation。

### 实验可信度

TPC-H 代表 analytics shuffle，但 ML training（[[Tensor-Parallelism]] 通信模式）等场景需另测。Baseline 需对照最新 DCQCN/TE 系统是否公平配置权重语义。

### 系统性缺陷

论文未讨论与 PFC/ECN 交互、故障下权重饥饿、可观测性与运维调参；恶意 sender 伪造对 INT 的信任模型未展开。

## 局限与 Future Work

- **局限 1**：多瓶颈路径上「一条 INT」是否充分仍依赖网络条件。
- **Future work 1**：与生产 TE/scheduler 协同的权重 API 与 SLO 验证。
- **Future work 2**：在 GPU cluster ML 通信 trace 上测量收敛时间与 tail latency。

## 相关

- **同会议**：[[OSDI-2025]]
