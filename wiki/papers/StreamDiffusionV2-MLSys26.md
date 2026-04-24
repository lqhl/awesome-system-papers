---
type: paper
name: StreamDiffusionV2
full_title: "StreamDiffusionV2: A Streaming System for Dynamic and Interactive Video Generation"
authors: [Tianrui Feng, Zhi Li, Shuo Yang, Haocheng Xi, Muyang Li, "et al."]
venue: MLSys
year: 2026
tags: [video-diffusion, streaming, pipeline-parallelism, real-time, slo]
source_pdf: "[[ec8956637a99787bd197eacd77acce5e.pdf]]"
source_md: "[[ec8956637a99787bd197eacd77acce5e]]"
---

# StreamDiffusionV2: A Streaming System for Dynamic and Interactive Video Generation (MLSys 2026)

> **一句话总结**：StreamDiffusionV2 把视频扩散模型改造为 training-free 的直播系统，用 SLO-aware batching + 多 GPU pipeline orchestration + sink-token rolling KV cache + motion-aware noise scheduler，4× H100 上 14B 模型达 58.28 FPS、首帧 0.5 秒。

## 问题

图像扩散直播（StreamDiffusion）帧间抖动严重；视频扩散（WAN、CausVid、Self-Forcing）时间一致性好但 offline-throughput 导向——固定 1×T×H×W 的大输入（T=81+ 帧）违反实时 SLO。四个具体挑战：

1. **TTFF 违约**：480p 1.3B 模型 81 帧 chunk 在 H100 上理论 TTFF 5.31s
2. **长时漂移**：sink tokens、RoPE、KV cache 为有界上下文设计，小时级直播积累漂移
3. **高速运动撕裂**：训练集偏慢动作，固定 noise schedule 在快速运动时出现 ghosting/blur
4. **GPU scaling 差**：sequence parallelism 通信开销大，naive pipeline parallelism FPS 提升有限

## 核心方法

**效率层**：
- **SLO-aware batching scheduler**：把 1×T×H×W 改为 B×T'×H×W，T' 取小值（几帧）满足 DDL，按硬件负载自适应 B
- **多 GPU pipeline orchestration**：DiT blocks 跨设备 ring 分段，每个 micro-step 产出 clean latent；结合 stream-batch 把 n 个 denoising step 当作 batch multiplier
- **DiT block scheduler**：运行时按实测延迟再平衡各 rank（VAE 首尾 rank 负担重），减少 pipeline bubble
- **Stream-VAE**：短 chunk（4 帧）+ 3D conv intermediate feature caching
- **异步通信 overlap**：双 CUDA stream（compute + comm）

**质量层**：
- **Adaptive sink + RoPE refresh**：按 prompt embedding 余弦相似度动态更新 sink set；帧索引过阈值后重置 RoPE phase
- **Motion-aware noise scheduler**：用 L2 帧差估计运动幅度 d_t，归一化+EMA 平滑；高运动用保守去噪，慢/静态用激进 refinement

## 关键结果

- 4× H100：**58.28 FPS @ 14B 模型**、**64.52 FPS @ 1.3B 模型**，不用 TensorRT / quantization
- 4 步去噪增强质量仍保持 31.62 FPS (14B) / 61.57 FPS (1.3B)
- TTFF 0.47s @16 FPS、0.37s @30 FPS——相比 CausVid 快 18×、相比 Wan2.1-1.3B 快 280×
- 支持 4× H100 (NVLink) 与 4× RTX 4090 (PCIe) 异构部署

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Flash-Attention]]、Sequence-Parallelism
- **同类系统**：StreamDiffusion、StreamV2V、CausVid、Self-Forcing、Distrifusion、PipeFusion
- **同会议**：[[MLSys-2026]]
