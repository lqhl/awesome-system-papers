---
type: paper
name: StreamDiffusionV2
full_title: "StreamDiffusionV2: A Streaming System for Dynamic and Interactive Video Generation"
authors: [StreamDiffusionV2 authors]
venue: MLSys
year: 2026
tags: [video-generation, diffusion, real-time, streaming, slo]
source_pdf: "[[ec8956637a99787bd197eacd77acce5e.pdf]]"
source_md: "[[ec8956637a99787bd197eacd77acce5e]]"
---

# StreamDiffusionV2: A Streaming System for Dynamic and Interactive Video Generation (MLSys 2026)

> **一句话总结**：离线 video DiT 用大 chunk **1×T×H×W** 无法满足直播 **TTFF**/逐帧 DDL；StreamDiffusionV2 训练无关地采用 SLO-aware **B×T′×H×W** 微批、sink-token rolling KV、motion-aware noise、pipeline+DiT block 动态均衡，在 4×H100 达 **0.5s TTFF**、14B **58.28 FPS** / 1.3B **64.52 FPS**，1s SLO miss **0.2%**。

## 问题与动机

视频扩散模型（WAN 等）为 offline throughput 优化，固定 81+ 帧 chunk 违反直播 SLO（低 [[TTFF]]、严格 per-frame deadline）。需在异构 GPU 上 training-free 适配交互式长序列，保时间一致性与画质。

## 关键观察 / 隐含假设

- **观察 1：短帧 chunk（few frames/step）控 per-step 延迟；调 stream batch **B** 适应负载，才能 meet DDL 又吃满 GPU。**
  - **依赖假设**：VAE 可 streaming 设计降 TTFF（0.47s@16FPS, 0.37s@30FPS vs CausVid/Wan 高 **18–280×** TTFF）。
  - **可能失效场景**：极高运动场景 noise 调度失配时画质降。

- **观察 2：因果 DiT 短序列使 SP comm overhead 占 **40–120ms**（**20–40×** 本方案），传统 Ulysses/Ring 不适合直播。**
  - **依赖假设**：pipeline parallel + stream batch 比 SP 更适合短 chunk。
  - **可能失效场景**：超宽分辨率 compute 回升时需重平衡。

- **观察 3：pipeline 首尾 rank 扛 VAE 编码解码导致 bubble；推理时 DiT block scheduler 按实测时间重分块可削 stall。**
  - **依赖假设**：4×H100 NVLink / 4×4090 PCIe 均可用。
  - **可能失效场景**：PCIe 多卡 comm 更重，FPS 降（仍 **~16–24 FPS** @480p/512²）。

- **假设 1**：sink-token guided rolling KV 保长序列时间一致性。**
  - **证据强度**：**中**——VBench 等质量指标 + 在线 v2v 实验。

## 核心方法

**SLO-aware batching scheduler**：小 **T′** + 动态 **B**。

**Pipeline orchestration**：跨 denoising steps 与网络阶段；near-linear FPS scaling。

**Sink-token rolling KV cache** + **motion-aware noise controller**（帧差估计运动调 denoise）。

**DiT block scheduler**：动态 block 分配减 pipeline bubble。

## 设计取舍

- **Training-free vs 蒸馏加速**：部署快，上限受 base model 步数约束。
- **Pipeline vs SP**：换通信模式，短 chunk memory-bound 友好。
- **多 GPU vs 单卡创作者**：企业/个人分级硬件目标。
- **边界条件**：Wan-T2V 1.3B/14B；1–4 denoising steps；512²/480p。

## 实验与结果

- TTFF：**~0.5s**；30FPS 流下显著低于 CausVid/Wan2.1-1.3B。
- 4×H100：14B **58.28 FPS** @512²，1.3B **64.52 FPS**；480p 14B **39.24 FPS**。
- 在线 v2v：1s SLO miss **0.2%**；jitter mean **21ms** (σ **30ms**)。
- Comm：比 Ulysses/Ring **20–40×** 低 overhead。

## Critical Analysis

### 论证链条

直播 SLO 与 offline chunk 矛盾 → 系统组件针对 TTFF/FPS/一致性 → 异构硬件实测，工程闭环好。画质 vs 步数/运动控制的长期 drift 需更多用户 study。

### 假设压力测试

14B 与 1.3B 共享 VAE **~30%** 时间使吞吐接近——换 VAE 后 scaling 规律变。Blackwell 等算力/memory 比变影响 memory-bound 判断（Appendix 讨论）。

### 实验可信度

多 GPU 配置、在线指标完整。缺：与 [[db-SP]] 稀疏 attention 联合、成本$/stream。

### 系统性缺陷

论文未讨论失败帧恢复、CDN 集成、版权/内容安全 pipeline。多租户 GPU 切片未谈。

## 局限与 Future Work

- **局限 1**：质量-运动极端场景调参敏感。
- **局限 2**：强依赖 WAN 族模型与 VAE 占比。
- **Future work 1**：与 sparse attention/量化协同测 FPS–质量前沿。
- **Future work 2**：auto **B,T′** 来自 live QoS 反馈。

## 相关

- **相关概念**：[[DiT]]、[[KV-Cache]]、[[Pipeline-Parallelism|Pipeline-Parallel]]、[[Video-Generation]]
- **同类系统**：CausVid、Wan2.1
- **同会议**：[[MLSys-2026]]