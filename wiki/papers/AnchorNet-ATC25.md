---
type: paper
name: AnchorNet
full_title: "AnchorNet: Bridging Live and Collaborative Streaming with a Unified Architecture"
authors: [Tong Meng, Wei Zhang, Dong Chen, Zhen Wang, et al.]
venue: ATC
year: 2025
tags: [live-streaming, webrtc, codec, deployed-system, tiktok]
source_pdf: "[[atc2025-meng.pdf]]"
source_md: "[[atc2025-meng]]"
---

# AnchorNet: Bridging Live and Collaborative Streaming with a Unified Architecture (ATC 2025)

> **一句话总结**：TikTok 的第二代直播架构，用 RTC SFU 作为统一 CDN publisher 替代解耦的 DualNet，配合 sample-level 音频拼接技术，将切换 live/co-broadcast 模式时的 rebuffering 减少 60%+，用户参与度提升最高 3.83%。

## 问题

TikTok 第一代 DualNet 架构把 live streaming（broadcaster 直推 RTMP+AAC 到 CDN）和 collaborative streaming（co-broadcasters 走 RTP+Opus，通过 MCU server-side mixing 后转码到 RTMP/AAC）解耦，导致：CDN ingestion node 切换、不同 publishing path（多协议、独立 congestion controller 慢启动）、不同 codec 间编码器 priming silence/帧大小不一致带来音频毛刺、组件间 ossification。需要在保持 server-side mixing 设计选择的前提下，做到模式切换流畅。

## 核心方法

- **统一 publishing path**：RTC SFU 作为唯一的 CDN publisher（既是 live 也是 co-broadcast）；MCU 转码后的 mixed stream 反馈给 SFU 再转 RTMP 推到 CDN；broadcaster 只维持一条 RTP 上行连接，跨模式不重连。
- **音频拼接（sample-level）**：四项技术解决 codec 编码器 priming（AAC HE-AAC v1 priming 5058 samples vs 帧 2048）和 frame size 不一致问题：
  1. **Extra Priming**：让 priming + extra 是 frame_size 整数倍，确保跳过的全是 silence
  2. **Duplicate Trailing Samples**：broadcaster 在切换时把 egress codec 的尾部样本复制到 ingress codec ring buffer
  3. **Rescale Trailing Opus Samples at MCU**：把不足整帧的尾部样本重采样到正好 1 帧
  4. **Reconstruct MDCT Window**：MCU 从 SFU 取若干 live frame 用于重建 overlapped MDCT 窗
- AAC 用于 RTMP/CDN ingest（兼容性），Opus 仅在 broadcaster 间 RTC 阶段用。
- 部署经验：A/V sync injection、adaptive playback speed 弥补 SFU-MCU 多走一跳的延迟差。

详细的拼接算法见 [[atc2025-meng]]。

## 关键结果

- Live → collaborative 切换：viewer rebuffer count -60.1%/duration -60.3%（音频 -64.5%/-67.4%）
- Collaborative → live：rebuffer count -78.5%/duration -78.9%
- User engagement：host +0.53%、co-broadcaster +2.15%、viewer +3.83%
- Live mode 也因 user-space congestion control 让 video rebuffer -13.47%、audio -11.02%、push FPS +3.11%
- 单 MCU 任务中位数 < 0.4 logical core + 220 MB；100 个 MCU 可承载 15–30K 并发 collab channels
- 部署一年以上，服务超 10 亿用户

## 相关

- **相关概念**：[[WebRTC]]、[[RTMP]]、[[Codec-Switching]]、[[MDCT]]、[[CDN]]
- **同类系统**：LiveNet、PCDN、TRTC、Tencent ApsaraVideo RTC
- **同会议**：[[ATC-2025]]
