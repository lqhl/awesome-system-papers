---
type: paper
name: QOS
full_title: "QOS: Quantum Operating System"
authors: [Emmanouil Giortamis, Francisco Romão, Nathaniel Tornow, Pramod Bhatotia]
venue: OSDI
year: 2025
tags: [quantum-computing, scheduling, error-mitigation, nisq, resource-management]
source_pdf: "[[osdi25-giortamis.pdf]]"
source_md: "[[osdi25-giortamis]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-17
---

# QOS: Quantum Operating System (OSDI 2025)

> **一句话总结**：QOS 用 Qernel 串联 error mitigation、fidelity 估计、compatibility 多编程与调度。在 IBM 27-qubit 的主要评测中，error mitigator 对 Qiskit 的 fidelity 提升跨 12/24-qubit 被测点为 **2.6×/456.5×**；多编程的 effective utilization 为平均 **+7.2%**、最高 **+10.1%**，不是 9.6×。

## 问题与动机

NISQ QPU 噪声大、容量小、时空异构强；用户手动选机、无系统级 multi-programming。单点论文（仅 mitigation 或仅调度）无法处理 **fidelity vs utilization vs queue** 的根本张力——27-qubit 上为保 0.75 fidelity 利用率平均仅 26.3%，同型号 QPU fidelity 可差 38%，负载可差 57×。

## 关键观察 / 隐含假设

- **观察 1**：电路越大 fidelity 指数恶化（4→24 qubit 平均 -98.9%），需 OS 层自动 mitigation 组合。
  - **依赖假设**：mitigation 预算有限，需在 runtime overhead 与 fidelity 间 tradeoff。
  - **可能失效场景**：远超 QPU 宽度电路仍无法映射。
- **观察 2**：QPU 性能时空波动使「永远选最好机」导致严重负载失衡，但性能差未必配得上排队成本。
  - **依赖假设**：在线 fidelity estimator 无需昂贵模拟即可指导调度。
  - **证据强度**：强——120 校准日 Perth 数据波动。
- **假设 1**：兼容电路可安全共置（compatibility score + effective utilization），否则 multi-programming 毁灭 fidelity。
  - **证据强度**：中——9.6× 是相对 solo 的 fidelity 指标；effective utilization 的报告值为平均 +7.2%、最高 +10.1%。

## 核心方法

**Qernel**：统一执行单元，串联四层 modular 组件：

1. **Error mitigator**：组合 circuit cutting、qubit reuse、freezing 等（首次非平凡组合）。
2. **Estimator**：分析模型预测各 QPU fidelity。
3. **Multi-programmer**：compatibility scoring + effective utilization。
4. **Scheduler**：多目标 fidelity-aware，平衡负载与等待。

基于 Qiskit/Python，开源。

## 设计取舍

- **取舍 1**：模块化 mechanism/policy 分离，换实现复杂度。
- **取舍 2**：模拟 workload 中 formula scheduler c=.7 可牺牲约 2% fidelity 换约 5× 等待降低。
- **边界条件**：127-qubit 等大机扩展性论文部分依赖模拟/采样。

## 实验与结果

**指标、基线与边界**：average waiting time 与 fidelity；formula scheduler c=.7 vs full-fidelity priority；由 70,000 benchmark circuits 和 7,000+ cloud job runs 构造的 representative workload（§9.6，Fig.13）。

- mitigation（budget b=3）相对 Qiskit/CutQC/FrozenQubits 的 mean fidelity：12-qubit 为 **2.6×/1.6×/1.11×**，24-qubit 为 **456.5×/7.6×/1.67×**；对应 classical overhead 为 **16.6×/2.5×**，quantum overhead 为 **31.3×/12×**（§9.2，Figs.8–10）。
- 9 benchmarks 的 multi-programming 在 30/60/88% utilization 下，相对 solo fidelity 平均 **9.6×**、相对 baseline M/P **1.15×**；effective utilization 平均 **+7.2%**、最高 **+10.1%**，相对 solo 的 fidelity loss 平均 **9.6%**（§9.4，Fig.11）。
- 模拟 workload 中，formula c=.7 相对 full-fidelity priority 约 **5×** 更低等待、约 **2%** 更低 fidelity；GA c=.5 为 2×/4%（§9.6，Fig.13）。

## Claim–Evidence Map

| Claim | Evidence | Metric / baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| mitigation 提高 fidelity 但有显著执行开销 | 12/24-qubit 的 2.6×/456.5× vs Qiskit；classical/quantum overhead 如上 | error mitigator、budget b=3；12/24-qubit，不泛化端到端 QOS | §9.2，Figs.8–10 | high |
| 多编程在指定 utilization 阈值改善 fidelity | vs solo 9.6×、vs baseline M/P 1.15×；effective utilization +7.2%/+10.1% | 9 benchmarks、30/60/88% utilization；solo fidelity loss 平均 9.6% | §9.4，Fig.11 | high |
| cross-layer 组件在同利用率下提升 fidelity | 48% higher fidelity | 27-qubit QPU、9 benchmarks、8/16/24 initial qubits；vs CutQC + baseline M/P | §9.5，Fig.12 | high |
| scheduler 在模拟 workload 中交易 fidelity 与等待 | c=.7 约 5× lower wait、约 2% lower fidelity | 70k circuits/7k job runs derived workload；vs full-fidelity priority | §9.6，Fig.13 | high |
| 动机中的硬件异质性不是 QOS 的端到端收益 | 4→24 qubit fidelity -98.9%；9 benchmark utilization 26.3% | IBM Kolkata 27q/各诊断 workload；不作为 QOS gain | §3.1–3.4，Figs.3–4 | high |

## Critical Analysis

### 论证链条

NISQ 约束 → 单点优化不够 → Qernel 统一四层 → 真实设备大规模评估。链条在 IBM Falcon 类设备闭合；离子阱等其他技术需重标定 noise model。

### 假设压力测试

- mitigation 组合开销可能吞噬队列收益（论文有 budget 但生产 SLA 未知）。
- compatibility 估计错误时 co-run 灾难性降 fidelity。
- 云计费模型变化后「等待时间」权重可能改变。

### 实验可信度

真实硬件 7000 runs 是亮点；benchmark 实例多。与完全手动专家调优对比需细看附录。

### 系统性缺陷

论文未讨论：多租户公平性、作业抢占、与经典 HPC 混合调度、fault recovery 跨校准周期。

## 局限与 Future Work

- **局限 1**：绑定 NISQ 规模，逻辑 qubit 时代需重构。
- **局限 2**：mitigation 与调度 policy 最优性未证明。
- **Future work 1**：更大 QPU（127+）与跨提供商 federated scheduling。
- **Future work 2**：与经典 OS 协同的 hybrid workflow scheduler。

## 相关

- **相关概念**：Scheduling、Fault Tolerance
- **同类系统**：Qiskit Runtime、IBM Cloud quantum queue
- **同会议**：[[OSDI-2025]]
