---
type: paper
name: MP2
full_title: "Roaming Free in the VR World with MP2"
authors: [Yifei Xu, Xumiao Zhang, Yuning Chen, Pan Hu, Xuan Zeng, et al.]
venue: ATC
year: 2025
tags: [vr-streaming, multipath, wifi, qoe, centralized-control]
source_pdf: "[[atc2025-xu.pdf]]"
source_md: "[[atc2025-xu]]"
---

# Roaming Free in the VR World with MP2 (ATC 2025)

> **一句话总结**：第一个面向 free-roaming VR 的中心化多路径多用户协调系统，跨 AP/用户/层级统一调度，tail latency 降 35×、bitrate 升 1.56×、QoE 升 1.86×，用户研究 MOS 提升 99.1%。

## 问题

Free-roaming VR（多用户在大空间自由走动玩 VR）对 wireless streaming 提出三个新需求：mobility（跨 AP 切换）、scalability（多用户）、efficiency（带宽调度）。已有 XLINK + ALVR 等去中心化方案：(1) handover 时 Wi-Fi 唤醒慢导致 ~50ms 包间隔；(2) 多路径 + 多用户竞争导致 bitrate 剧烈抖动（double control loop 问题）；(3) AP 之间负载不均，缺全局视角。

## 核心方法

- **架构**：中心化 MP² Hub（控制 + 数据平面），客户端用 multipath QUIC tunnel；用户空间实现，无需 kernel 改动或专用硬件；客户端配双 Wi-Fi 网卡（一个传输、一个被动扫描）。
- **协调式无缝迁移**：path warmup（提前 100ms 发探测包唤醒目标 AP 的 radio）+ redundant transmission（迁移时双路径冗余 50ms）+ bitrate guidance（迁移前主动给所有用户下发 bitrate 上限避免 ABR 反应慢）。
- **决策算法**：
  - GMM 建模 VR 帧大小分布（3 个高斯分量已使 JS 距离 <0.10），利用高斯线性叠加性质给出 tail latency P 的闭式解（erf 函数）；
  - MCS-aware pruning：按 MCS 排序砍掉低质量链路；
  - Location-based partitioning：把 AP 分成地理 cell，每 cell 独立优化，复杂度从 M^K 降到 E·(p·M/E)^(K/E)；
  - Adaptive topology stabilization：QoE 增益超过阈值才切，避免抖动。
- 算法在 16AP×48client 规模下决策 <1 秒。

深度细节回 [[atc2025-xu]]。

## 关键结果

- 单用户切换：>20ms lag rate 从 1.2% 降到 0.4%，>50/100ms 完全消除。
- 多用户切换 + bitrate guidance：min bitrate 从 32.7 Mbps 升到 72.7 Mbps（+120%），max latency 从 68.9 ms 降到 12.6 ms（4.5×）。
- 16AP×48client emulation：>20ms lag rate 仅 0.26%（baseline 97.3%-98.9%），完全消除 >50ms latency；平均 bitrate 73.3 Mbps（+56.3%~242.5%）；QoE 是 2nd-place 的 1.86×。
- 20 名志愿者用户研究：MOS 提升最高 99.1%。

## 相关

- **相关概念**：[[Multipath-QUIC]]、[[ABR]]、[[Wi-Fi]]、[[VR-Streaming]]
- **同会议**：[[ATC-2025]]
