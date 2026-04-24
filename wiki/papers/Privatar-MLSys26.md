---
type: paper
name: Privatar
full_title: "Privatar: Enabling Privacy-Preserving Real-Time Multi-User VR through Secure Offloading"
authors: [Jianming Tong, Hanshen Xiao, Krishnakumar Nair, Hao Kang, Ziqi Zhang, et al.]
venue: MLSys
year: 2026
tags: [privacy, vr, offloading, differential-privacy, pac-privacy]
source_pdf: "[[4e732ced3463d06de0ca9a15b6153677.pdf]]"
source_md: "[[4e732ced3463d06de0ca9a15b6153677]]"
---

# Privatar: Enabling Privacy-Preserving Real-Time Multi-User VR through Secure Offloading (MLSys 2026)

> **一句话总结**：多用户 VR 里把 avatar 重建从头显卸载到不可信 PC 扩算力，用 block-DCT 频域分割（Horizontal Partitioning，base 频带留本地）+ 分布感知最小扰动（DAMP，用 PAC Privacy 代替 local DP，省 17.6× 噪声），在 Meta Quest Pro 上支持 2.37× 并发用户、重建 loss 仅多 5.7–6.5%。

## 问题

多用户 VR（演唱会、球赛、电影）需要对每个参与者实时重建高保真 avatar。每副头显要为所有其他用户跑 VAE decoder，8 层 transposed conv 占 decoder 99.4% FLOPs，Quest Pro 的 902 GFLOPS 只能撑 2 用户 @60 FPS。

卸载到同网下的不可信 PC 能扩算力，但暴露面部表情/身份 → 隐私泄漏。三类通用解法都不够：
- **密码学**：HE 慢 1000×；MPC 需 GB 级通信，做不到实时
- **TEE**（Intel SGX / AMD SEV）：只得 1.79× 吞吐，CPU 慢
- **Local Differential Privacy**：个人数据单发释放无法 aggregate，isotropic 噪声按最大维度的 worst-case sensitivity 标定，低方差维度被巨量噪声淹没——实测加够 DP 噪声后重建 loss 膨胀 105×

## 核心方法

两个 insight 对应两层设计：

**Insight-1（频域能量极不均）**：facial unwrapped texture 做 block-DCT（B=4，16 个频率分量）后，**base 频带占 94.9% 能量**，其余 15 个合占约 5%。

→ **Horizontal Partitioning (HP)**：把 VAE encoder/decoder 沿频域拆成两条独立 path
- *Local path*（可信头显）：facial mesh + base 频带（高能量，高辨识力）
- *Offloaded path*（不可信 PC）：剩余低能量频带，加噪后卸载
- 下采样到 1/B 分辨率，去掉 `log2(B)` 层，每分量计算量降到 1/B²
- 攻击者永远拿不到完整信息，对 expression identification 攻击提供**经验保护**

**Insight-2（用户表情分布缓变）**：人不会突然做出比历史最大表情还夸张 2× 的表情；实测训练集的 latent code 分布与任意 2 秒（120 帧）窗口分布几乎相同。

→ **Distribution-Aware Minimal Perturbation (DAMP)**：首次把 **PAC Privacy**（Xiao & Devadas 2023）用于时序面部数据。DP 加的是 isotropic 噪声（按最大维度 sensitivity），DAMP 按每维度的真实方差定制**各向异性**噪声——高方差多噪、低方差少噪，对齐实际数据分布。在线持续更新分布跟踪长期漂移。

- 噪声总能量（covariance）降 **10³ 级**
- 每个发布样本的扰动误差降 **17.6×**
- 保持同等 provable privacy 保证（PAC），对抗任意计算无界攻击者

HP 的经验保护 + DAMP 的形式化保护组合使用：HP 缩小敏感数据暴露面 → DAMP 需要的噪声更少。

## 关键结果

在 Meta Quest Pro 上：

- 并发用户数 **2.37×** vs SoTA quantization / sparsity / 本地重建
- 重建 loss 仅 +5.7~6.5%
- 能耗仅 +9%
- 吞吐-loss Pareto 前沿全面领先
- 抗 NN-based expression identification attack（empirical）+ 对任意黑盒攻击 provable 保护
- 开源：https://github.com/georgia-tech-synergy-lab/Privatar

## 相关

- **相关概念**：Differential-Privacy、PAC-Privacy、DCT、VAE、TEE、Homomorphic-Encryption
- **同类系统**：Intel SGX、AMD SEV-SNP、各类 HE/MPC 方案
- **同会议**：[[MLSys-2026]]
