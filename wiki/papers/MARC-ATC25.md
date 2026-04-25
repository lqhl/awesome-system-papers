---
type: paper
name: MARC
full_title: "MARC: Motion-Aware Rate Control for Mobile E-commerce Cloud Rendering"
authors: [Yuankang Zhao, Furong Yang, Gerui Lv, Qinghua Wu, Yanmei Liu, et al.]
venue: ATC
year: 2025
tags: [cloud-rendering, rate-control, qoe, webrtc, e-commerce]
source_pdf: "[[atc2025-zhao-yuankang.pdf]]"
source_md: "[[atc2025-zhao-yuankang]]"
---

# MARC: Motion-Aware Rate Control for Mobile E-commerce Cloud Rendering (ATC 2025)

> **一句话总结**：基于淘宝 1.8B 帧测量发现移动云渲染中用户「motion / non-motion」on-off 模式下 QoE 偏好动态变化，MARC 在 WebRTC 中按帧级感知 motion 状态做差异化码率决策，实测 session freeze rate 降 71%、interaction rate 升 20%。

## 问题

移动电商云渲染（如淘宝 3D 商品/虚拟形象）通过 WebRTC 把云端 Unreal Engine 渲染的帧流送到手机，需在 motion-to-photon 延迟和画质间权衡。作者在淘宝 200K+ 会话、1.8B 帧的大规模测量中发现：

- 用户行为呈 **on-off 模式**：短暂 motion phase（如旋转/缩放，74% 持续 2-4 帧）和较长 non-motion phase（30% 超过 15 帧）交替出现。
- motion frame 的 P99 send duration 是 non-motion 的 1.9 倍（82ms vs 43ms），因 motion 帧编码出来更大（CBR 下 P50 后明显偏离）。
- session duration 对 motion frame 的延迟敏感度比 non-motion 高 75.7%，对码率敏感度高 37.8%。

但现有 RTC 速率控制器（GCC、Copa、Pudica、SQP）对 motion / non-motion 帧用同一套决策逻辑，要么过于激进引发队列堆积，要么过于保守牺牲画质，无法对齐 QoE 偏好。

## 核心方法

MARC 在 WebRTC 框架内做 **frame-level（30fps 即 33ms 决策窗）** 的 motion-aware 码率控制：

1. **Dynamic QoE Objective**：从测量的 session-duration 线性回归斜率反推权重，定义 `QoE(i) = q_R(R_i) − γ(i)·q_L(L(i))`，其中 motion 帧 γ=1.275、non-motion γ=1（即 motion 帧的延迟惩罚系数高 27.5%）。
2. **Time-based Sending Model**：显式建模 frame enqueue / departure / pacing rate，跟踪 buffer state `b(i)` 在 pacing rate 下的演化，把延迟解析为 queueing + send + OWD。
3. **State Predictor**：短窗预测未来 N=10 帧的 motion 标志、pacing rate、propagation delay。
4. **Stochastic Optimization**：N-step lookahead 把 cumulative QoE 最大化问题用梯度法在帧间隔内求解，输出连续码率（不是离散梯级）。
5. 对 motion / non-motion 分别拟合 `d(R)=encoded frame size` 的线性模型，承认 motion 帧同码率下更大。

深度细节回 [[atc2025-zhao-yuankang]] 或 [[atc2025-zhao-yuankang.pdf]]。

## 关键结果

- 大规模 A/B 测试覆盖 100 万+ 用户 session：相比 GCC/Copa/Pudica/SQP 等基线，MARC 把 motion 帧的 P99 send duration + queueing latency 降 30%-55%，P99 frame latency 降 22%-60%。
- session freeze rate 降 71%；session duration 升 9%；interaction rate（motion 帧占比）升 20%。
- 客户端零开销，服务端单 session 仅 +1.3% CPU。
- 与 Quality-First 策略相比 queueing latency 降 59.2%，码率仅降 4.5%；与 Latency-First 相比同延迟下平均码率升 26.1%。

## 相关

- **相关概念**：[[QoE]]、[[WebRTC]]、[[Congestion-Control]]、[[Rate-Control]]
- **同类系统**：Pudica、SQP、GCC、Copa（cloud gaming RTC）
- **同会议**：[[ATC-2025]]
