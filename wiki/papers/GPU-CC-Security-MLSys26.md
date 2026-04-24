---
type: paper
name: GPU-CC-Security
full_title: "Blueprint, Bootstrap, and Bridge: A Security Look at NVIDIA GPU Confidential Computing"
authors: [Zhongshu Gu, Enriquillo Valdez, Salman Ahmed, Julian James Stephen, Michael V. Le, "et al."]
venue: MLSys
year: 2026
tags: [confidential-computing, gpu, security, hopper, trusted-execution]
source_pdf: "[[812b4ba287f5ee0bc9d43bbf5bbe87fb.pdf]]"
source_md: "[[812b4ba287f5ee0bc9d43bbf5bbe87fb]]"
---

# Blueprint, Bootstrap, and Bridge: A Security Look at NVIDIA GPU Confidential Computing (MLSys 2026)

> **一句话总结**：对 NVIDIA Hopper GPU Confidential Computing (GPU-CC) 做首个系统化安全剖析，重构其架构（FSP/GSP/SEC2/CE 引擎）、启动链（secure boot + 32 个派生密钥）和 CPU↔GPU 数据桥梁，发现并向 PSIRT 上报多个安全问题。

## 问题

GPU-CC 在 Hopper H100 起把可信边界从 CPU 延到 GPU，让 AI pipeline 在 TEE 下跑，但 NVIDIA 只有高层白皮书和法律化专利，大量技术细节（FSP/GSP/SEC2 具体职责、boot 顺序、密钥派生、BAR0 Decoupler 覆盖范围、RPC/DMA/UVM/memory scrubbing/fault delivery 数据路径安全性）都不公开。对 ML system 研究者而言，评估 GPU-CC 能否满足应用的 threat model 几乎无据可依。

## 核心方法

三阶段系统分析：

**Blueprint（静态架构）**：用开源 NVIDIA kernel/UVM driver 插桩跟踪控制流，对闭源 CUDA runtime/user-mode driver 用 preload 库间接观察，再与专利文本交叉验证，厘清四类引擎：
- **FSP (Foundation Security Processor)**: RISC-V，secure boot 锚点，验证 GSP-FMC/GSP-RM 签名。
- **GSP (GPU System Processor)**: RISC-V + AES，控制面；SPDM Responder 与 driver 建主密钥，跑 RMAPI RPC。
- **SEC2 (Secure Processor)**: CPR 建立、device attestation、memory scrubbing、secure workload 提交。
- **CE (Copy Engine)**: 数据搬运 + AES 加解密，每个 logical CE 和 driver 协商 4 把 session key（user/kernel × h2d/d2h）。

**Bootstrap（启动链）**：CEC1736 EROT → FSP BROM → FSP → GSP → SEC2 的信任链。SPDM 主密钥派生出 32 个 session key（GSP 6 + SEC2 10 + CE 32 = 总共多份见表 1）。BAR0 Decoupler 启用后扫描 0x400000 个 4B 寄存器显示 99.78% 返回 0、0.02% 返回非零值（1042 个）、0.19% 返回错误码——相比非 GPU-CC 模式（7.94% values / 80.25% errors）大部分被隔离，但剩余可读寄存器仍是潜在攻击面。Device attestation 靠 DIK (Device Identity Key) 签的证书链 + 从 NVIDIA RIM service 拉 golden measurement 比对。

**Bridge（运行时数据桥）**：逐一审查 RPC、memory transfer、UVM、memory scrubbing、fault delivery、CUDA 操作六类数据路径的保护实现，在 GPU-CC threat model（host OS/hypervisor/PCIe/BMC 全不可信，但不含物理脱封）下评估各路径是否真正保护了明文 payload。

## 关键结果

- 首次公开完整 GPU-CC 架构图，把 FSP/GSP/SEC2/CE 四引擎的职责、互通、密钥派生、BAR0 Decoupler 行为量化实测出来。
- 扫描 16 MB BAR0 空间，GPU-CC 模式下 99.78% 寄存器被 firewall 归零，仅 1042 个字段返回非零值，建议 NVIDIA 透明化这些字段的功能。
- 枚举 32 个会话密钥（表 1），对 GSP/SEC2/CE 每条通道绑定不同 key 保证前/后向独立、replay 攻击被 IV 阻断。
- 所有发现已通过 NVIDIA PSIRT 负责披露。

## 相关

- **相关概念**：[[KV-Cache]]
- **同会议**：[[MLSys-2026]]
