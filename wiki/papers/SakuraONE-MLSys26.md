---
type: paper
name: SakuraONE
full_title: "SakuraONE: An Open Ethernet-based AI HPC System and Its Observed Workload Dynamics in a Single-Tenant LLM Development Environment"
authors: [Fumikazu Konishi, Yuuki Tsubouchi, Hirofumi Tsuruta]
venue: MLSys
year: 2026
tags: [ai-hpc, ethernet, rocev2, sonic, workload-analysis, experience-report]
source_pdf: "[[ad61ab143223efbc24c7d2583be69251.pdf]]"
source_md: "[[ad61ab143223efbc24c7d2583be69251]]"
---

# SakuraONE: An Open Ethernet-based AI HPC System and Its Observed Workload Dynamics in a Single-Tenant LLM Development Environment (MLSys 2026)

> **一句话总结**：SAKURA internet 运营的 800-GPU H100 AI HPC 集群经验报告，ISC 2025 TOP500 排名第 49、Top-100 中唯一使用 800 GbE + SONiC 开源网络栈的系统，记录单租户 LLM 开发生命周期下的作业规模演化。

## 问题

日本产业界缺乏与美国 Big Tech 可比的 AI 基础设施；共享学术 HPC（ABCI 3.0、TSUBAME 4.0）难保商用稳定性。同时，传统 HPC 往往锁定 vendor-specific 封闭栈，缺开放、可解耦、灵活的 AI 网络方案。mid-scale（几百 GPU）生产集群的公开运维数据也很少，使得行业缺乏参照。

## 核心方法

SAKURAONE 设计与实测报告：

**系统架构**：
- 100 节点 × 8 H100 SXM (80GB) = 800 GPU，每节点双 Intel Xeon Platinum 8580+、1.5 TB DDR5。
- 2 PB all-flash Lustre，100 GB/s sustained。
- Rail-optimized leaf-spine 800 GbE [[RDMA]]/RoCEv2，基于 Edgecore AIS800-640 (Broadcom Tomahawk 5, 51.2 Tb/s)。
- 软件栈：Rocky Linux 9.4 + Slurm 22.05.9 + Singularity/Apptainer + Pyxis + CUDA 12.x。

**开放网络设计**：全栈用 SONiC NOS + SAI，避免 vendor lock-in；RoCEv2 + PFC + ECN + DCQCN 保证 lossless AI fabric；EVPN/VXLAN 支持多租户 overlay。

**NIC-GPU affinity**：10 × ConnectX-7，8 × 400 GbE 做 GPU fabric（PIX 到各 GPU 的 PCIe domain），2 × 400 GbE 专供存储 I/O（bonded），分离训练 vs I/O 流。

**单租户 LLM 项目 workload 分析**：小规模作业数量占多数但只消耗少量 GPU-time；大规模作业少但占 GPU-time 的多数。项目生命周期由大规模训练 → 中规模迭代 refinement 演化。

## 关键结果

- HPL Rmax 33.95 PFLOP/s（784 GPU，每 GPU 43.31 TFLOP/s，78.3% efficiency）。
- HPCG 396.295 TFLOP/s；HPL-MxP FP8 339.86 PFLOP/s。
- 目标：四个月内 continued-pretrain 70B 模型 on ~300B tokens，单集群可容多 concurrent 全规模训练。
- 填补了 mid-scale 生产 AI HPC 公开运维数据的空白。

## 相关

- **相关概念**：[[RDMA]]、Ethernet fabric、RoCEv2
- **同类系统**：ABCI 3.0、TSUBAME 4.0、BLOOM-176B 训练集群（Jean Zay）
- **同会议**：[[MLSys-2026]]
