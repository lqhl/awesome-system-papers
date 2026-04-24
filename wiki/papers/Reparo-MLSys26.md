---
type: paper
name: Reparo
full_title: "Reparo: Loss-Resilient Generative Codec for Video Conferencing"
authors: [Tianhong Li, Vibhaalakshmi Sivaraman, Pantea Karimi, Lijie Fan, Mohammad Alizadeh, Dina Katabi]
venue: MLSys
year: 2026
tags: [video-conferencing, generative-model, codec, loss-recovery, vqgan, vision-transformer]
source_pdf: "[[65b9eea6e1cc6bb9f0cd2a47751a186f.pdf]]"
source_md: "[[65b9eea6e1cc6bb9f0cd2a47751a186f]]"
---

# Reparo: Loss-Resilient Generative Codec for Video Conferencing (MLSys 2026)

> **一句话总结**：用 VQGAN tokenizer + 时空 ViT 生成式恢复丢失 token 做视频会议编解码，摆脱 FEC 的冗余权衡和帧间 I/P 依赖，每帧独立编码，在高丢包率（50%-75% bad state）下 worst-10% PSNR 比 VP9+Tambur 高 11.5–16.4 dB，未渲染帧率从 29.2% 降到 2.0%，V100 GPU 实时 30fps。

## 问题

视频会议要求实时回放，丢包恢复不能靠重传。传统方案两类：
- **重传**：只适合 RTT 短的场景。
- **FEC**（ULPFEC、flexFEC、Tambur 的 streaming code）：冗余率选太高浪费带宽，选太低无法解码。互联网丢包 bursty 且不可预测，冗余率很难定。
- 更糟：传统 codec（VP8/VP9/H.264/H.265/AV1）用 I/P 帧依赖压缩，丢掉一帧导致后续几十上百帧 freeze，直到强制 keyframe。
- 已有 neural codec（GRACE/DVC）仍有 delta coding 的时域依赖。

## 核心方法

**核心思想**：用生成模型填补丢失像素，训练时学"人脸与物体如何出现"这类视觉先验；推理时由已收到的 token 作为条件引导生成，避免 hallucination 与已有像素冲突。

五个组件：

**1. Neural Codec（VQGAN tokenizer）**：
- Encoder CNN 把每帧切 patch，每 patch 映射到 codebook 中最近邻 token；decoder CNN 反过来。
- 512×512 帧压成 32×32 token，codebook 1024 个 token，每 token 10 bit index；收发两端共享 codebook（预训练后冻结，不传输）。
- **每帧独立编码**，无时域依赖——丢帧不扩散。

**2. Packetizer**：
- 确定性把 32×32 token 分到 4 个 packet，位置 (i,j) 的 token 分到 packet `2·(i mod 2) + j mod 2`，避免相邻 token 进同一包（丢包时邻居能辅助恢复）。
- Header 4 byte，带 frame index / packet index / packet size。

**3. Bitrate Controller (self-drop)**：
- 基于 frame/packet index 确定性丢 token 以匹配目标比特率。Reparo 对 50% token loss 只轻微损 PSNR。
- 默认 30 fps、每帧 4 packet、每 packet 324 byte → 311.04 Kbps。

**4. Loss Recovery Module**：
- Spatio-temporal Vision Transformer，输入是当前帧 + 过去 T=6 帧的 token，丢失位置插 `[M]` mask token。
- 时空 attention **顺序** 做（先跨时间再跨空间），降内存从 $O(T^2h^2w^2)$ 到 $O(Th^2w^2 + T^2hw)$。
- 训练时随机采样 self-drop rate $r_d \in [0, 0.6]$ 和 packet drop rate $r_p \in [0, 0.8]$ 注入模拟丢失；reconstructive cross-entropy loss 只算当前帧 missing token。
- 推理时每 33 ms deadline 聚合收到的 packet，未到的视为丢失；对每个 missing 位置取 $p(z_{ij} | z^M)$ argmax。

**5. Decoder**：重建的 token 网格喂回 VQGAN decoder 输出 RGB。

**三大附加优势**：
- **Efficient compression**：只传 token index。
- **Constant bitrate**：帧间处理对称，不像传统 codec I-frame 和 P-frame 大小差异导致 bitrate 抖动。
- **One-way communication**：receiver 不需发 ACK 给 sender，直接生成。

## 关键结果

- **5 小时 / 84 人 / 412 clips** 的数据集（远大于 Gemino 的 5 人 25 clips）。
- **PSNR（worst 10%）**：Reparo 在 low/medium/high loss 下 33.4 / 32.9 / 31.6 dB，VP9+Tambur 为 21.9 / 16.5 / 16.9 dB——领先 **11.5 / 16.4 / 14.7 dB**。
- **非渲染帧率**：Reparo 0.2% / 0.8% / 2.0%，VP9+Tambur 8.0% / 13.1% / 29.2%。
- **Rate-limited 场景**：Reparo 35 dB vs. VP9+Tambur 33.4 dB（Reparo 能稳定打满 link capacity，VP9 的 bitrate variability 被迫降平均 bitrate 避丢包）。
- **PSNR 分布稳定**：Reparo 90%+ 帧落在 32.5–37 dB 范围，基本不随 loss level 变化。
- V100 GPU（≈ Apple M2 Max）两块实时跑 30 fps 512×512（transmitter + receiver 各一块）。

## 相关

- **相关概念**：[[VQGAN]]、[[Vision-Transformer]]、[[Generative-Model]]、[[Forward-Error-Correction]]、[[Video-Codec]]、[[Tokenization]]
- **对比系统**：ULPFEC、flexFEC、Tambur、GRACE、VP8/VP9/H.264/H.265/AV1
- **同会议**：[[MLSys-2026]]
