---
type: paper
name: Reparo
full_title: "Reparo: Loss-Resilient Generative Codec for Video Conferencing"
authors: [Tianhong Li, Vibhaalakshmi Sivaraman, Pantea Karimi, Lijie Fan, Mohammad Alizadeh, Dina Katabi]
venue: MLSys
year: 2026
tags: [video-conferencing, generative-codec, packet-loss, fec, realtime]
source_pdf: "[[65b9eea6e1cc6bb9f0cd2a47751a186f.pdf]]"
source_md: "[[65b9eea6e1cc6bb9f0cd2a47751a186f]]"
---

# Reparo: Loss-Resilient Generative Codec for Video Conferencing (MLSys 2026)

> **一句话总结**：Reparo 用 VQGAN token 编解码 + spatio-temporal ViT 在丢包时生成缺失 token，每帧独立编码、恒定码率；相对 VP9+Tambur 在高中低丢包下 10% worst PSNR 高 11.5–16.4 dB，不可渲染帧从 8–29% 降至 0.2–2%。

## 问题

视频会议中 FEC 需在不可预测的突发丢包下选冗余量：过多浪费带宽，过少导致帧不可解码并级联恶化（P-frame 依赖 I-frame）。传统 codec 码率波动大，重传在 RTT 长时不可用。

## 核心方法

**Reparo** 五模块 pipeline：
1. **Encoder/Decoder**：VQGAN 将帧 patch 量化为 codebook token indices（共享 codebook，只传 index）
2. **Packetizer**：相邻 token 分到不同 packet，利于 recovery
3. **Bitrate controller**：确定性 self-drop token 适配目标码率（容忍 50% token 丢失）
4. **Loss recovery**：spatio-temporal ViT，用当前帧 received token + 前 6 帧 context 生成 [M] 缺失 token
5. 每帧 **独立编码**，无帧间依赖；receiver 无需 ACK

训练时同时模拟 self-drop 与 packet loss（$r_d$ 0–0.6，$r_p$ 0–0.8）。

## 关键结果

- 10% worst PSNR：低/中/高丢包 **33.4 / 32.9 / 31.6 dB**，比 VP9+Tambur 高 **11.5 / 16.4 / 14.7 dB**
- 不可渲染帧：Reparo **0.2% / 0.8% / 2.0%** vs VP9+Tambur **8.0% / 13.1% / 29.2%**
- 无丢包时 PSNR 与 baseline 相当或更好；恒定码率下 **35 dB vs 33.4 dB**
- V100 GPU 实时 30fps 512×512；5 小时 / 84 人验证集

## 相关

- **相关概念**：FEC、generative model、video codec
- **同类系统**：WebRTC ULPFEC/flexFEC、Tambur、VP9、GRACE
- **同会议**：[[MLSys-2026]]