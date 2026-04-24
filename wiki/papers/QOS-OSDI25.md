---
type: paper
name: QOS
full_title: "QOS: Quantum Operating System"
authors: [Emmanouil Giortamis, Francisco Romão, Nathaniel Tornow, Pramod Bhatotia]
venue: OSDI
year: 2025
tags: [quantum-computing, operating-system, scheduling, resource-management, nisq]
source_pdf: "[[osdi25-giortamis.pdf]]"
source_md: "[[osdi25-giortamis]]"
---

# QOS: Quantum Operating System (OSDI 2025)

> **一句话总结**：QOS 是第一个模块化的量子操作系统，围绕 Qernel 抽象统一组合 error mitigation、fidelity 估计、多路复用和调度四层，fidelity 最高提升 456.5×、QPU 利用率 9.6×、等待时间减 5×。

## 问题

今天的量子处理器（QPU）运行在 NISQ（Noisy Intermediate-Scale Quantum）范式下：噪声大、比特数小（几十到 100s）、同型号不同机器甚至同机器不同校准日噪声都不同。给 QPU 编程/跑任务还面临：

1. **Fidelity 随比特数骤降**：4→24 量子比特 GHZ 电路 fidelity 下降 98.9%
2. **时空异构**：同型号 IBM Falcon 6 台机器跑 12-qubit GHZ 最佳与最差 fidelity 差 38%；同一 Perth 机器 120 天中 20 天 fidelity 单日下滑 >5%
3. **利用率 vs fidelity 天生冲突**：要 ≥0.75 fidelity 27-qubit QPU 平均只能用 26.3%，不能像经典 CPU 那样跑满
4. **负载不均**：IBM 同尺寸 QPU 间待处理任务数差 57×，因为用户手动挑 fidelity 最高的机器

现有研究/产品（IBM Cloud、AWS Braket、若干学术点方案）碎片化：fidelity 提升工具不带运行时、multi-programming 只有 FIFO/随机、调度启发式写死——没有把这些能力统一暴露给上层的"量子操作系统"。

## 核心方法

QOS 用 Qiskit 实现，四层模块+跨层协同围绕一个共同抽象 **Qernel**（封装电路静/动态属性：qubit 数、depth、gate type、SupermarQ feature vector 等）：

- **Error Mitigator**：组合三类技术（circuit cutting & knitting、qubit freezing、qubit reuse）并在 budget b 下贪婪挑 hotspot（如度数高的 qubit）。工作流示例：先 freeze 高度数节点，再 circuit-cut 两个 gate 出 2 个小片，最后 qubit reuse 压到 2-qubit——综合协同比任何单技术都好。Map-reduce 分布式后处理 8^k 个 bit-string 组合
- **Estimator**：不做昂贵模拟，而用分析模型/回归给 (Qernel, QPU) 打 fidelity 分。读取 QPU 校准数据（readout error、gate error、T2 相干时间、crosstalk），对电路逻辑→物理 transpile 后乘以各项错误概率（基于 Mapomatic）
- **Multi-programmer**：引入 **compatibility score** 和 **effective utilization** 概念，把兼容的多个小 Qernel 空间共置到同 QPU，加 buffer zone 抑制 crosstalk，在 utilization 和 fidelity 间权衡
- **Scheduler**：第一个 fidelity-aware 多目标调度器。用加权公式 c·fidelity + (1−c)·waitingTime，或遗传算法生成 Pareto 前沿

QOS API（`run(circ, cnfgs)`、`results(jID)`）把这些复杂度藏到 hardware-agnostic 接口后面，mechanism 与 policy 严格分离。

## 关键结果

所有数字基于 IBM 27-qubit QPU、70,000 benchmark 实例、7,000 真实量子 run：

- Error mitigator 提升 fidelity **2.6-456.5×**（随问题规模）
- Multi-programmer 给定 utilization 目标下相比 baseline 提升 fidelity **1.15-9.6×**
- Scheduler fidelity 权重 c=0.7 时 waiting time 降 **5×**，fidelity 只损失约 2%；genetic-algorithm policy c=0.5 时 waiting 2×、fidelity −4%
- 最大 QPU 负载差异从 57× 缩到 15.2%

## 相关

- **相关概念**：[[Quantum-Computing]]、[[NISQ]]、[[Error-Mitigation]]、[[Circuit-Cutting]]、[[Multi-Programming]]、[[Fidelity]]
- **相关工作**：CutQC、QVM（circuit cutting）、FrozenQubits、Mapomatic、QucloudN（量子 multi-programming）
- **同会议**：[[OSDI-2025]]
