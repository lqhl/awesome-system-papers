---
type: paper
name: Privatar
full_title: "Privatar: Enabling Privacy-Preserving Real-Time Multi-User VR Through Secure Offloading"
authors: [Jianming Tong, Hanshen Xiao, Krishnakumar Nair, Hao Kang, Ziqi Zhang, Ashish Sirasao, G. Edward Suh, Tushar Krishna]
venue: MLSys
year: 2026
tags: [vr, privacy, offloading, avatar, differential-privacy]
source_pdf: "[[4e732ced3463d06de0ca9a15b6153677.pdf]]"
source_md: "[[4e732ced3463d06de0ca9a15b6153677]]"
---

# Privatar: Enabling Privacy-Preserving Real-Time Multi-User VR Through Secure Offloading (MLSys 2026)

> **一句话总结**：Privatar 用频率域 Horizontal Partitioning + Distribution-Aware Minimal Perturbation，在 Meta Quest Pro 上并发 avatar 数 **2.37×**（+3 users），重建损失仅 **5.7–6.5%**、能耗 +**9%**，并提供可证明隐私与抗 expression identification 攻击。

## 问题

多用户 VR 需在 headset 实时解码众人 avatar latent，decoder（尤其 texture transposed conv）占 **99.4%** FLOPs，Quest Pro 60 FPS 仅支撑约 **2** 用户。offload 到同网不可信设备会泄露表情/身份，HE/MPC/TEE 要么太慢要么吞吐不足，local DP 各向同性噪声又毁画质（fully offload 重建 loss **105×**）。

## 核心方法

**HP（Horizontal Partitioning）**：DCT 将 unwrapped texture 分 16 频带，**94.9%** 能量留在 on-device 基频 + mesh；仅 offload 低能量分量，敌手只见不完整视图。

**DAMP**：跟踪用户表情缓慢漂移的在线分布，用 PAC privacy 按维最小噪声，较 local DP 噪声降 **17.6×** 同级别保证。

**组合**：HP 降敏感度 + DAMP 形式化保证；威胁模型为 local DP 级（仅信自己 headset）。

## 关键结果

- Meta Quest Pro：**2.37×** 吞吐（约 +3 并发用户），重建 loss **+5.7–6.5%**，能耗 **+9%**
- 低噪声下 ML 攻击 expression 识别 **86.15%**；Privatar 下显著降低
- 优于 quantization/sparsity/全本地 baseline 的 throughput-loss Pareto

## 相关

- **相关概念**：[[Quantization]]、[[Disaggregation]]
- **同类系统**：VAE avatar pipeline（Lombardi et al.）
- **同会议**：[[MLSys-2026]]