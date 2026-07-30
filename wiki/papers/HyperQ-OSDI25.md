---
type: paper
name: HyperQ
full_title: "Quantum Virtual Machines"
authors: [Runzhou Tao, Hongzheng Zhu, Jason Nieh, Jianan Yao, Ronghui Gu]
venue: OSDI
year: 2025
tags: [quantum-computing, virtualization, multiprogramming, cloud, scheduling]
source_pdf: "[[osdi25-tao.pdf]]"
source_md: "[[osdi25-tao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# HyperQ：量子虚拟机（OSDI 2025）

> **原题**：Quantum Virtual Machines

> **一句话总结**：NISQ 云量子计算无多租户、整机串行批处理导致利用率极低；HyperQ 用 repeating-region qVM + 时空 binpacking 合成 composite circuit 提交 IBM Eagle，相对 IBM Quantum 吞吐/利用率最高约一个数量级、平均延迟最高降 40×，且 noise-aware 调度有时还能提升 fidelity。

## 问题与动机

云量子服务把用户程序当作 batch job 整机串行执行，小电路只占少量 qubit，整机长期空闲；用户排队可达数天。现有 compile-time 多路复用需事先知道共执行程序集，无法像经典 VM 那样独立编译与动态调度。

## 关键观察 / 隐含假设

- **观察 1**：真实量子机（IBM Eagle、Rigetti 等）由 repeating region（如 I 形 7-qubit unit）网格铺成，可把 qVM 定义为 region 的倍数并映射到物理拓扑。
  - **依赖假设**：目标机器拓扑确实呈现可重复的 region 结构；编译目标 qVM 而非整机。
  - **可能失效场景**：拓扑不规则或代际变更使 region 抽象失效。
- **观察 2**：无 QRAM、无法 context switch，只能通过把多个 qVM 合成一个 composite circuit 作为单个 job 提交云端。
  - **依赖假设**：云 API 接受「大 job」且超时机制可回收（HyperQ 用 1.5× 估计门延迟作 timeout）。
  - **可能失效场景**：动态电路/条件门使执行时间难估计（论文列为 future work）。
- **假设 1**：qubit 间插入 unused qubit 即可有效隔离 crosstalk，保证 qVM 间 fault isolation。
  - **证据强度**：中——实验显示 fidelity 不劣于 baseline，但依赖当日 calibration 与具体噪声模型。

## 核心方法

**qVM 接口**：与真实 backend 同 gate set / coupling map；basic qVM 对应 repeating unit（Eagle 上 7-qubit I 形），scaled/fractional qVM 弹性分配 qubit。

**编译**：Qiskit virtual backend，程序独立编译到 rightsized qVM，无需知晓共驻程序。

**调度**：三维 binpacking——space scheduling（greedy 放置 qVM region）+ time scheduling（短 job 后追加 qVM 填满最长 batch 时间）+ 可选 noise-aware（避开最差 n 个 region）。

**执行**：重标号 virtual→physical qubit，提交 composite job；完成后拆分测量结果。

## 设计取舍

- **取舍 1**：合成大 job 提高利用率，但短程序需等 batch 内最长 qVM，略增 run time（相对 queue 等待可忽略）。
- **取舍 2**：greedy 调度保证不低于 FIFO 串行，但未必全局最优 binpack。
- **边界条件**：IBM Eagle 127-qubit、35 个 benchmark；Poisson 到达时增益小于 all-at-once（队列中可共调度 qVM 更少）。

## 实验与结果

- IBM Quantum Eagle，35 个程序：相对 IBM Quantum **吞吐最高 ~11×**（utilization **~11×**），**平均延迟最高 ~40×** 降低（all-at-once small-only）。
- Poisson 到达：吞吐/利用率约 **3×** 改进。
- Noise-aware：部分配置 fidelity 优于 IBM Quantum，同时保持高 utilization。
- qVM 隔离实验：共执行时 fidelity 不 compromised。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| HyperQ maps qVM to repeated physical region | virtual backend compilation then aggregate circuit（§3.1–3.2） | IBM Eagle/Falcon topology | high |
| all-at-once queue improves total run time | 456→47s/9.7× small-only；683→139s/4.9× small+med（§4.2，Table3） | 145/196 QASMBench queue、Brisbane/127q | high |
| estimated utilization improves | 3.3→35%/11×；7.8→46%/5.8×（§4.2，Table4） | IBM lacks per-qubit telemetry；fragmentation | high |
| Poisson latency is lower under empty queue | 159→3.7s/43×，noise-aware4.0s/40×（§4.2，Table5） | 1 job/s、no other user，非 public-cloud latency | high |
| fidelity effect is device/test-specific | L1 IBM.55、space.57、noise-aware.50（§4.2，Table6） | 4000-shot/single calibration；time all-at-once .64 | high |

## 批判性分析

### 论证链条

「小程序占整机 → repeating region 可映射 qVM → composite job 合法提交」链条在 IBM 栈上闭合。性能 claim 强依赖 queue waiting 主导延迟的测量设定；对单次 job 纯执行时间改善较小。

### 假设压力测试

非 IBM 拓扑、更大规模 fault-tolerant 机、或云厂商限制 composite job 大小时方案需重做。Dynamic circuits 破坏门延迟估计。Crosstalk 隔离用 spacer qubit 是否对所有噪声通道足够论文未穷举。

### 实验可信度

Baseline 为 IBM Quantum FIFO，公平且实用；模拟器与真实机混合评估需区分。Fidelity 指标与 workload 覆盖 35 程序，但仍是 NISQ 规模。

### 系统性缺陷

依赖云 API 与 calibration 数据新鲜度；scheduling 失败/timeout 的运维策略论文简述；多租户计费与 SLO 未讨论。

## 局限与后续工作

- **局限 1**：无真正抢占式 qVM，time multiplex 仅在 batch 内追加。
- **局限 2**：architecture-specific qVM，跨厂商不可移植。
- **Future work 1**：支持 conditional/dynamic circuit 的运行时间估计与调度。
- **Future work 2**：与更多云 backend（Braket 等）的端到端部署验证。

## 相关

- **同会议**：[[OSDI-2025]]
