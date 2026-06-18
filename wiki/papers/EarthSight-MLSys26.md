---
type: paper
name: EarthSight
full_title: "EarthSight: A Distributed Framework for Low-Latency Satellite Intelligence"
authors: [Ansel Erol, Seungjun Lee, Divya Mahajan]
venue: MLSys
year: 2026
tags: [edge-computing, satellite, multi-task-learning, orbital-edge, scheduling]
source_pdf: "[[9bf31c7ff062936a96d3c8bd1f8f2ff3.pdf]]"
source_md: "[[9bf31c7ff062936a96d3c8bd1f8f2ff3]]"
---

# EarthSight: A Distributed Framework for Low-Latency Satellite Intelligence (MLSys 2026)

> **一句话总结**：把卫星影像分析建模为地面-轨道联合决策：multi-task shared backbone + 地面 query scheduler 预测优先级/compute budget + 星上 utility-driven filter ordering；相对 SERVAL，单图 compute **1.9×** 更快，P90 端到端延迟 **51→21 分钟**。

## 问题

LEO 卫星 downlink 窗口短、带宽有限，全量下传再分析延迟数小时至数天。现有 onboard ML 把每颗卫星当孤立节点，多任务重复推理耗电，且无法利用星座级全局上下文。

## 核心方法

1. **Multi-task inference**：domain-clustered EfficientNet backbone + 可稀疏执行的 task head，amortize backbone cost
2. **Ground-station scheduler**：R-tree 匹配 AOI、DNF 聚合 query、look-ahead 模拟 downlink 窗口预测 p* 与 rejection rate
3. **In-orbit runtime**：utility U_φ = (accuracy × selectivity × logical impact) / cost，greedy filter ordering + adaptive confidence threshold α

## 关键结果

- 三场景硬件增强仿真：平均 compute time/image **1.9×** 更快
- P90 首联系到交付延迟 **51→21 分钟**（vs SERVAL baseline）

## 相关

- **相关概念**：[[Quantization]]（edge 部署相关）
- **同类系统**：SERVAL、Orbital Edge Computing、Spire/Pelican onboard ML
- **同会议**：[[MLSys-2026]]