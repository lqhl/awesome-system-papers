---
type: paper
name: STORM
full_title: "STORM: a Multipath QUIC Scheduler for Quick Streaming Media Transport under Unstable Mobile Networks"
authors: [Liekun Hu, Changlong Li]
venue: ATC
year: 2025
tags: [multipath, quic, mobile, streaming-media, scheduler]
source_pdf: "[[atc2025-hu-liekun.pdf]]"
source_md: "[[atc2025-hu-liekun]]"
---

# STORM: a Multipath QUIC Scheduler for Quick Streaming Media Transport under Unstable Mobile Networks (ATC 2025)

> **一句话总结**：通过 signal-watermark 机制 + reliability-aware 调度，让 MPQUIC 在移动不稳定网络下尾包延迟降低 98.2%、流媒体帧率提升 1.95×。

## 问题

移动设备上 MPQUIC 用多条无线链路（WiFi、4G/5G）聚合带宽，但当某条路径信号变差时，端到端尾延迟反而比单路径更糟（实测车载场景 4.59s，单路径的 6.38×）。两个根因：1) 现有调度器只看 RTT/拥塞滑窗，对突发链路退化反应迟缓——「最后一公里」无线链路才是真正瓶颈，core network 不是；2) MPQUIC 同时承载可靠（关键帧）与不可靠（非关键帧）数据，但调度器不区分，重传可靠包阻塞不可靠包，再被排队的不可靠包反过来阻塞后续可靠包。

## 核心方法

两大组件 + 工作流：

- **Signal-Watermark Mechanism (SWM)**：与 WiFi/蜂窝模块 co-design，在 adapter layer 用 100ms 周期采集 RSRP/SINR/RSSI，通过加权几何平均 + 丢包趋势调制因子算出 quality index $Q \in [0,1]$。设三档 watermark（Good 0.45 / Warning 0.32 / Outage 0.21），低于 Warning 触发警告反馈调整流量比例，低于 Outage 触发 path 停用。Fast Suppression / Slow Recovery 防抖：跌落立即反馈，恢复需在 Good 之上稳定 $T_{rec}$=400ms。Watermark 自适应——根据后续实际 burst loss 微调阈值。
- **Reliability-Aware Scheduling (RAS)**：Dual-Q 架构。Reliable Queue (RQ) 把关键数据按 block 管理，每 block 独立 priority/deadline；Unreliable Queue (UQ) 把不可靠数据按 stream 管理，按 deadline 排序。可靠 block 跨双路径分配满足 $\frac{Size_1}{bw_1 F_1} + OWD_1 = \frac{Size_2}{bw_2 F_2} + OWD_2$，其中 $F_i$ 由 SWM 反馈降低问题路径的份额。基于带宽 gap + priority 计算 weight。不可靠 stream 只在快路径 block 完成、慢路径仍空闲的「time hole」中注入，避免和可靠流互堵。
- **Dynamic Multipath Management** + 新增 PATH_ALERT 帧承载 SWM 反馈，path 被停用时对未确认数据做 deadline-aware 重注入。

基于 Alibaba XQUIC 实现，新增 1342 行 C 代码 + 102 行 Java 适配层（用 WifiManager/TelephonyManager），无需 root。深度细节回 [[atc2025-hu-liekun]]。

## 关键结果

- 不稳定网络下尾包延迟降低 98.2%
- 流媒体帧率提升 1.95×（vs minRTT/DAMS）
- 重传率平均降低 12.8%
- 视频会议 1080p@30Mbps 下移动场景仍稳定
- SWM 反馈延迟仅 ~1.14% 偏差（caputred vs actual）
- RAS 平均处理时间 5.03ms（占总传输 7.4%），SWM 反馈 O(1)，JNI 每秒额外 CPU 仅 780µs

## 相关

- **相关概念**：[[Multipath-Transport]]、QUIC、[[Congestion-Control]]、[[Streaming-Media]]
- **同类系统**：MPTCP、DAMS、minRTT scheduler
- **同会议**：[[ATC-2025]]
