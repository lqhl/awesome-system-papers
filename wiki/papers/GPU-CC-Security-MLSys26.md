---
type: paper
name: GPU-CC-Security
full_title: "Blueprint, Bootstrap, and Bridge: A Security Look at NVIDIA GPU Confidential Computing"
authors: [Zhongshu Gu, Enriquillo Valdez, Salman Ahmed, Julian James Stephen, Michael V. Le, Hani Jamjoom, Shixuan Zhao, Zhiqiang Lin]
venue: MLSys
year: 2026
tags: [confidential-computing, gpu-security, nvidia, tee]
source_pdf: "[[812b4ba287f5ee0bc9d43bbf5bbe87fb.pdf]]"
source_md: "[[812b4ba287f5ee0bc9d43bbf5bbe87fb]]"
---

# Blueprint, Bootstrap, and Bridge: A Security Look at NVIDIA GPU Confidential Computing (MLSys 2026)

> **一句话总结**：通过 instrument 开源驱动与 nvTrust，重建 H100 GPU-CC 的 FSP/GSP/SEC2/CE 蓝图、secure boot+SPDM 密钥派生、以及 CVM↔GPU 各数据路径加密机制，量化 BAR0 firewall（99.78% 寄存器读零）并负责任披露 PSIRT。

## 问题

NVIDIA GPU-CC 对用户透明，但规格封闭、栈复杂，研究者难判断 threat model 下 CPU-GPU 统一 TEE 是否真保护 in-flight 数据。

## 核心方法

**Blueprint**：FSP（secure boot）、GSP（SPDM+RPC+DMA keys）、SEC2（CPR/attestation/scrub/secure channel）、CE（h2d/d2h AES+IV 防 replay）。

**Bootstrap**：GSP-FMC→GSP-RM chain；Table 1 列 44 类 derived keys；device attestation DIK→AK→measurement vs RIM golden。

**Bridge**：逐路径分析 RPC、UVM、CUDA launch、memory scrub 等在 GPU-CC mode 下的加密/完整性；BAR0 Decoupler 阻断 CPR 直访。

## 关键结果

- BAR0 扫描：非 CC 7.94% 返回 value；GPU-CC 下 **99.78%** 读零，仅 0.02%（1042）仍非零
- 平台：8×H100 SXM5 + AMD SEV-SNP CVM；driver 550/570
- 已向 NVIDIA PSIRT 披露全部 findings

## 相关

- **相关概念**：[[RDMA]]（I/O 威胁模型相关）
- **同类系统**：Intel TDX、AMD SEV、Graviton/HIX 学术 GPU-CC
- **同会议**：[[MLSys-2026]]