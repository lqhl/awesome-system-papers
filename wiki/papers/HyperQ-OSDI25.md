---
type: paper
name: HyperQ
full_title: Quantum Virtual Machines
authors: [Runzhou Tao, Hongzheng Zhu, Jason Nieh, Jianan Yao, Ronghui Gu]
venue: OSDI
year: 2025
tags: [quantum-computing, virtualization, scheduling, cloud]
source_pdf: "[[osdi25-tao.pdf]]"
source_md: "[[osdi25-tao]]"
---

# Quantum Virtual Machines (OSDI 2025)

> **一句话总结**：把经典 VM 概念引入量子云——HyperQ 定义架构特定的 qVM 抽象，通过空时 binpacking 在 IBM 127-qubit Eagle 上让多个量子程序并行执行，吞吐和延迟都提升一个数量级。

## 问题

量子云计算（IBM Quantum 等）目前跑任务是严格串行的：每个程序不管多小都独占整台量子计算机。NISQ 设备单个程序通常只用少数几个 qubit，大量硬件资源被浪费；同时用户排队常常要等几天。

已有的量子「multiprogramming」工作都依赖定制编译器在编译期把多个程序合并，这要求预先知道哪些程序会共同执行，无法独立编译执行。而且这些定制编译器缺少 Qiskit 等主流工具的优化。量子硬件又没有 QRAM 支持 context switch，无法保存/恢复量子态。

## 问题的核心方法

HyperQ 定义 quantum virtual machine (qVM) 抽象：qVM 的 coupling map 和 gate set 固定对应物理机器的一个重复区域（如 IBM Eagle 上的 I 形 7-qubit 区域，也就是 IBM Falcon 整机）。用户把程序独立编译到 qVM 作为 backend，与 Qiskit 等现有编译器全兼容。

qVM 还有 scaled（m×n 倍基本单元）和 fractional（半 qVM）两种尺寸，自适应程序的 qubit 需求。fault isolation 靠在不同 qVM 之间保留未使用 qubit 的间隔来抑制 crosstalk 噪声。

由于没有 context switch，HyperQ 通过三维 binpacking（space + time）把一批 qVM 打包成一个复合量子电路提交给云服务：space scheduling 贪心把 qVM 放到物理机的不同 region；time scheduling 在短 qVM 执行完后把其他 qVM 追加到该 region 以填充时间空隙。还支持 noise-aware scheduling——把噪声 resilient 的 qVM 放到 noise 高的 region，保留好 region 给噪声敏感的任务，甚至能提升 fidelity。

## 关键结果

- 相对 IBM Quantum 基线：吞吐量最高提升 11× （small-only + all-at-once + space+time），small&med 提升 4.4-5.8×
- 利用率从 3.3% 提升到 35%（small-only），从 7.8% 提升到 46%（small&med）
- 即使在 Poisson arrival 场景下，吞吐也维持 3× 以上改进
- Noise-aware 调度能同时提升 fidelity 和利用率

## 相关

- **同会议**：[[OSDI-2025]]
