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
---

# QOS: Quantum Operating System (OSDI 2025)

> **一句话总结**：QOS 用 Qernel 统一抽象串联可组合 error mitigation、fidelity 估计、compatibility 多编程与多目标调度，在 IBM 27-qubit 上 7000+ 真实运行、7 万+ benchmark 实例显示 fidelity **2.6×–456.5×**、利用率最高 **9.6×**、等待时间最高 **5×** 缩短（平均仅牺牲 1%–3% fidelity）。

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
  - **证据强度**：中——9.6× utilization 场景下 1.15×–9.6× fidelity tradeoff 报告。

## 核心方法

**Qernel**：统一执行单元，串联四层 modular 组件：

1. **Error mitigator**：组合 circuit cutting、qubit reuse、freezing 等（首次非平凡组合）。
2. **Estimator**：分析模型预测各 QPU fidelity。
3. **Multi-programmer**：compatibility scoring + effective utilization。
4. **Scheduler**：多目标 fidelity-aware，平衡负载与等待。

基于 Qiskit/Python，开源。

## 设计取舍

- **取舍 1**：模块化 mechanism/policy 分离，换实现复杂度。
- **取舍 2**：scheduler 可牺牲 1%–3% fidelity 换 5× 等待降低。
- **边界条件**：127-qubit 等大机扩展性论文部分依赖模拟/采样。

## 实验与结果

- IBM 27-qubit：7000+ runs，70k+ instances。
- Fidelity：2.6×–456.5×（随问题规模）；estimator 识别高 fidelity QPU。
- Utilization：最高 9.6×（目标利用率下 fidelity 1.15×–9.6×）。
- 等待时间：最高 5× 降低，平均 fidelity 损失 1%–3%。

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