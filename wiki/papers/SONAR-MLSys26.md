---
type: paper
name: SONAR
full_title: "SONAR: Benchmarking Topology and Collaboration in Decentralized Learning"
authors: [Abhishek Singh, Joyce Yuan, Yichuan Shi, Rishi Sharma, Ramesh Raskar, Jonas Blanc, Martin Jaggi]
venue: MLSys
year: 2026
tags: [decentralized-learning, federated-learning, topology, benchmarking, p2p]
source_pdf: "[[9fc3d7152ba9336a670e36d0ed79bc43.pdf]]"
source_md: "[[9fc3d7152ba9336a670e36d0ed79bc43]]"
---

# SONAR: Benchmarking Topology and Collaboration in Decentralized Learning (MLSys 2026)

> **一句话总结**：模块化 decentralized learning benchmark 框架，把 topology 当 first-class variable；发现 ring/torus 等稀疏结构可达与 dense graph 相当精度且通信成本低得多，并识别 adaptive collaboration 的 **collaborator collapse** 失败模式。

## 问题

FedML/FedScale/FLOWER 等聚焦 centralized FL，缺少对 P2P communication graph 的可控测量。topology 如何影响 convergence、robustness、privacy 缺乏系统级 reproducible 评估。

## 核心方法

**SONAR 四层架构**：orchestration、topology engine（random/static/adaptive）、communication（gRPC/MPI/WebRTC）、telemetry（ML/system/collaboration metrics）。

支持 ring/torus/grid、within-domain、Erdős–Rényi 等 topology；live training + real gRPC overhead（非纯仿真）。

## 关键结果

- Domain-shifted data：structured collaboration AUC **68.1** vs random **59.8**（**+14%**）
- 36 nodes、4 malicious（11%）：ring 维持 **60%** accuracy，dense graph 近零
- ring/torus 在远低于 fully-connected 的 bytes/round 下达到相当或更优 AUC
- similarity-based Top-K 选邻居可触发 collaborator collapse（小 K 孤立 clique，大 K 跨域 over-mix）

## 相关

- **相关概念**：[[Disaggregation]]（正交：decentralized vs disaggregated inference）
- **同类系统**：FedML、FedScale、DecentralizePy、COALA
- **同会议**：[[MLSys-2026]]