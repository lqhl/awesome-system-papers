---
type: paper
name: AnchorNet
full_title: "AnchorNet: Bridging Live and Collaborative Streaming with a Unified Architecture"
authors: [Tong Meng, Wei Zhang, Dong Chen, Zhen Wang, Quanqing Li, et al.]
venue: ATC
year: 2025
tags: [live-streaming, webrtc, codec-switching, cdn, deployed-system]
source_pdf: "[[atc2025-meng.pdf]]"
source_md: "[[atc2025-meng]]"
---

# AnchorNet: Bridging Live and Collaborative Streaming with a Unified Architecture (ATC 2025)

> **一句话总结**：基于 DualNet 暴露的「双 publishing path + 双 codec」是模式切换卡顿主因这一观察，AnchorNet 以 [[WebRTC]] SFU 作为唯一 [[CDN]] publisher 统一 RTP 上行与 RTMP ingest，并用 sample-level 音频拼接消除 AAC/Opus 的 encoder delay 毛刺，生产 A/B 将切换 rebuffering 降 60–79%、viewer 日活时长 +3.83%。

## 问题与动机

TikTok 等平台的 **collaborative streaming**（multi-guest live）要求频道在 **传统单人 live** 与 **多人 co-broadcast** 之间频繁切换，且观众应感知尽可能少的音频毛刺与视频卡顿。第一代架构 **DualNet** 为工程便利将两种模式解耦实现：live 走 broadcaster 直推 [[RTMP]] + AAC 到 [[CDN]]；collaborative 走 co-broadcaster 间 [[WebRTC]]/RTP + Opus，经 MCU server-side mixing 转码后再 ingest CDN。

这种解耦在切换时带来四类痛点：（1）CDN ingestion node 可能因 MCU 调度与 PoP/ISP 拓扑变化而切换，需 splice 两路 RTMP；（2）两条独立 publishing path、多 transport、多 congestion controller，首次切换常触发 slow start；（3）live 用 AAC、collaborative 用 Opus，codec 切换伴随 encoder priming silence 与帧长不一致；（4）live SDK 与 RTC SDK 分仓维护，优化需跨组件协调，形成 implementation ossification。作者 claim 的核心问题不是「要不要 server-side mixing」，而是在 **保留 server-side mixing** 的前提下，如何让 **同一频道会话内** 的模式切换足够平滑。

## 关键观察 / 隐含假设

- **观察 1**：DualNet 切换卡顿主要来自 **路径与状态不连续**，而非单纯 bitrate 不足。证据包括 CDN node 重选、独立 congestion controller 慢启动、out-of-order frame 到达，以及 micro-benchmark 中 DualNet 每次切换出现秒级 stall（§3.2、§6）。
  - **依赖假设**：观众侧仍通过单一 HTTP FLV 流订阅；host 在同一会话内反复 invite/hangup guest。
  - **可能失效场景**：若改为端到端 [[WebRTC]] 分发或 viewer 直接拉多路 RTP，「统一 publisher」收益结构会变。

- **观察 2**：**viewer 数量通常比 co-broadcaster 高一个数量级以上**，server-side mixing 的算力成本可被大量观众摊销；而 broadcaster-side mixing 在 Xiaomi 14 上 9 人 co-broadcast 时 host CPU 额外 +25%、峰值达 90%（§2.1）。
  - **依赖假设**：典型频道是「少量 co-broadcaster + 海量 passive viewer」，而非大规模互动会议室。
  - **可能失效场景**：高互动、低观众比的小房间，或低端机 host 占比很高时，server-side 延迟与 client-side 灵活性的 tradeoff 可能逆转。

- **观察 3**：**live 流量仍远大于 collaborative**，因此把 CDN publisher 角色放在 SFU 而非 MCU，避免 live 路径绕 MCU 回环；collaborative 的 mixed stream 由 MCU 回送 SFU 再 RTMP push（§4.1）。
  - **依赖假设**：live 是主 workload；MCU 多集中部署，SFU-MCU 往返会增加 collaborative 延迟。
  - **可能失效场景**：collaborative 占比持续上升，或 edge MCU 未铺开时，远离 MCU 集群的地区平均 E2E 延迟可比 DualNet 高 ~170 ms（§7.2）。

- **假设 1**：**RTMP + AAC 仍是 CDN ingest 的最低摩擦路径**；全 Opus 虽可减少 transcoding，但会抬高 live 模式全时长 MCU 成本（§4.3）。
  - **证据强度**：**强**——基于 TikTok 现网 CDN 供应商兼容性与成本核算，但对外部平台可迁移性一般。

- **假设 2**：**音频毛刺是模式切换 QoE 的关键瓶颈**；视频可在 UI layout 变化时注入人工 rebuffering 做 A/V sync，而音频必须 sample-level 无缝（§5、§8.1）。
  - **证据强度**：**中**——micro-benchmark 显示 AnchorNet 切换零 audio stall，但主观 MOS 与多 guest 场景论文未系统测量。

## 核心方法

AnchorNet 的设计原则是 **从 broadcaster 到 CDN 的 publishing path 唯一且会话连续**。RTC SFU 充当「anchor」：两种模式下都由 SFU 作为唯一 CDN publisher，保证同一 ingestion node、连续 sequence number，broadcaster 侧只维护 **一条 RTP 上行** 与一套 user-space congestion control（§4.1–4.2）。

协议选择上，broadcaster→SFU 统一 **RTP**（collaborative 与 live 共用 RTC 栈）；SFU→CDN 继续 **RTMP** 以兼容第三方 CDN。Collaborative 路径上，SFU 转发 co-broadcaster RTP；MCU 做 server-side mixing + Opus→AAC transcoding，再把 mixed stream 送回 host 所连 SFU，而非像 DualNet 那样 MCU 直推 CDN（§4.1）。Broadcaster 不再直连 CDN，多 CDN 故障定位与临时 blacklist 可集中在服务端（§4.4）。

**音频 stream splicing** 是区别于「只统一路径」的核心机制。视频在帧边界切换即可；音频受 encoder delay、MDCT 重叠窗、AAC(2048)/Opus(960) 帧长不一致影响，朴素切换会在 ingress 产生 leading silence、丢弃 egress tail samples（§5.1）。四项 sample-level 技术配合 broadcaster–server 协调：

1. **Extra Priming**：令 `(N_priming + N_extra) mod frame_size = 0`，使可安全跳过的 leading 帧全是 silence。
2. **Duplicate Trailing Samples**：host 用 ring buffer 把 egress codec 尾部样本复制进 ingress codec，避免切换时丢有效样本。
3. **Rescale Trailing Opus at MCU**：退出 collaborative 时将 buffer 中 0.5–1.5 帧的 Opus PCM 重采样为整帧 AAC 输入，偏差控制在半帧（~20 ms）内。
4. **Reconstruct Overlapped MDCT Window**：collaborative→live 时 MCU 从 SFU 取若干 live 帧填充 pre-encode buffer，使最后一帧 transcoded AAC 与后续 live 帧窗连续。

部署层还使用 **adaptive playback speed** 吸收 live/collaborative 间 E2E 延迟差，并在 UI 切换时允许 **人工 video rebuffering** 换音频无缝（§8.1）。算法与状态机细节见 [[atc2025-meng]]。

## 设计取舍

- **统一路径 vs 额外 hop**：SFU↔MCU 回环增加 collaborative 延迟，但换来切换时不必重建 CDN 会话；论文用 CDN/viewer jitter buffer + playback speed 消化，并预期 edge MCU 缓解（§4.1、§7.2）。
- **Server-side mixing vs client/viewer mixing**：放弃更低 E2E 延迟与 UI 灵活性，换取 viewer 只订阅一路 mixed stream、带宽与 signaling 可扩展；与 Tencent TRTC、Alibaba ApsaraVideo 同类选择一致（§2）。
- **AAC+Opus 双 codec vs 单 codec**：保留 AAC CDN 生态，接受 collaborative 路径 MCU transcoding；明确拒绝全 Opus 以降低 live 长时长转码成本（§4.3）。
- **RTP 统一上行 vs 保留 RTMP live ingest**：live 模式从 kernel RTMP 切到 user-space RTP/CC，带来略高 GPU（+0.8%）与内存（+0.31%），但 live 模式 rebuffer 降 11–13%、push FPS +3.11%（§7.1）。
- **边界条件**：固定 publishing topology 在「超低延迟电商」「高端机少量 guest」等场景可能不如未来的 hybrid mixing（broadcaster-side 小人数 / viewer-side 高价值用户）灵活（§8.3）。

## 实验与结果

- **Micro-benchmark**（2 co-broadcasters，同办公室 WiFi，6 次切换）：AnchorNet 切换过程 **零 audio stall**，video stall 也最低；DualNet 每次秒级 audio+video stall；Competitor-1（viewer-side mixing + 统一 RTC）仍有 ~100 ms audio pause；Competitor-2 首次进 collaborative 长 stall，之后接近 AnchorNet（§6）。
- **生产 A/B**（2024Q4，4 周，AnchorNet vs DualNet 用户量近似）：live→collaborative 切换 viewer rebuffer count **-60.1%**、duration **-60.3%**（audio **-64.5%/-67.4%**）；collaborative→live 达 **-78.5%/-78.9%**（audio **-76.3%/-77.1%**）。
- **Engagement**：host 日活 **+0.53%**，co-broadcaster **+2.15%**，viewer **+3.83%**；Figure 10 显示 co-broadcaster 在 collaborative 模式停留更久。
- **Live-only 副作用**：纯 live 模式 video/audio rebuffer **-13.47%/-11.02%**，push FPS **+3.11%**；host CPU **-1.33%**（硬件编解码优先），GPU **+0.8%**。
- **Server cost**：单 stream mixing 任务中位 **<0.4 logical core + 220 MB**；128-thread 机器上 ~100 MCU 可支撑 **15–30K** 并发 collaborative channel（§7.2）。
- **E2E delay**：全球平均与 DualNet 相当（DualNet 为抗切换卡顿预留大 jitter buffer）；个别远离 MCU 国家 collaborative 延迟 **+170 ms**（§7.2）。

## Critical Analysis

### 论证链条

Observation（DualNet 双路径/双 codec 导致切换 rebuffer）→ Design（SFU 统一 publisher + RTP 会话连续 + 音频 sample splicing）→ Result（生产 A/B 60–79% rebuffer 下降 + engagement 上升）整体闭合较好。弱环节在于：**viewer engagement +3.83% 的因果链**：论文承认 viewer session 时长包含多次切换，但 rebuffer 下降「不能直接解释」viewer 时长增加（§7.1），更像相关性而非 isolating 实验。另外，架构统一也改善了 **纯 live 模式**（-13% rebuffer），说明收益部分来自 RTP/CC 升级，不全是「模式切换」本身。

### 假设压力测试

- **Scale**：A/B 是十亿级平台，但 micro-benchmark 仅 2 guest、理想 WiFi；多 guest（论文测到 9 人 CPU 压力）、跨国弱网、频繁 codec/profile 变化时，rescaling 与 MDCT 重建是否仍无感知毛刺，**论文未覆盖**。
- **Workload 迁移**：若 collaborative 占比上升或平台推进 end-to-end WebRTC/LEB 分发，固定 RTMP+HTTP FLV 路径的成本优势可能缩小（§8.2 亦承认 WebRTC CDN 价格可达传统方案 2×）。
- **Hardware**：server-side mixing 假设 viewer 设备可解码单路 mixed stream；对超低端 viewer 仍 OK，但若转向 per-co-broadcaster 拉流则架构需重做。

### 实验可信度

- **强项**：4 周生产 A/B、95% 统计显著、与 predecessor DualNet 对照，Deployed Systems track 价值高。
- **基线**：未与内部「仅修 DualNet 切换逻辑」或「全 RTC 栈」做同等工程投入对照；外部 Competitor-1/2 来自 packet dump 逆向，公平性有限。
- **指标**：聚焦 rebuffer count/duration 与 daily active time，缺少切换瞬间 MOS、首帧延迟分布尾部分位数、MCU 故障时降级路径。
- **Ablation**：四项音频技术作为整体交付，**未拆分**各技术对 60–79% 收益的独立贡献。

### 系统性缺陷

- **尾延迟与地理差异**：MCU 集中部署使部分区域 collaborative E2E +170 ms；论文计划 edge MCU，但当前依赖 jitter buffer 与 playback speed，对延迟敏感场景可能不够。
- **故障恢复 / 多 CDN**：提到 AnchorNet 将 ingest 故障定位集中在服务端，但 **未展开** SFU/MCU 失效、partial cluster 降级、切换中 host 断线等恢复语义。
- **资源隔离**：多频道共享 MCU 时的 noisy neighbor、混流任务突发 CPU 峰值（P90）对 SLO 的影响 **论文未讨论**。
- **可观测性**：跨 broadcaster、SFU、MCU、CDN 的切换 trace 与 debug 故事仅点到 ossification 减轻，缺少 open telemetry 级细节。
- **正确性**：rescaling 引入最多半帧时间扭曲；作者称「minimal negative influence」，但无客观音频质量指标（PESQ/POLQA）支撑。

## 局限与 Future Work

- **局限 1**：架构固定 server-side mixing + SFU publisher，collaborative 延迟受 SFU-MCU 拓扑约束；论文承认在远离 MCU 地区劣于 DualNet 的 jitter 策略（§7.2）。
- **局限 2**：音频优化假设 AAC(HE-AAC v1) 与 Opus(48 kHz) 配置如 Table 1；其他 profile/采样率需重新标定 priming 与 buffer 尺寸（§5.3 称方法可泛化，但无实验）。
- **Future work 1**：**hybrid stream mixing spot**——少人数高性能机 offload 到 broadcaster-side，高价值低延迟场景试用 viewer-side RTP 拉流（§8.3）；可用 cohort A/B 量化每种策略的 cost–QoE frontier。
- **Future work 2**：**edge MCU 部署与延迟闭环测量**，验证 collaborative 延迟 +170 ms 能否在不增大切换 rebuffer 的前提下收回。
- **Future work 3**：对四项 splicing 技术做 **component ablation** 与主观/客观音频质量评估，明确 rescaling 与 MDCT 重建的感知边界。

## 相关

- **相关概念**：[[WebRTC]]、[[RTMP]]、[[CDN]]、[[Congestion-Control]]、[[QoE]]、[[Codec-Switching]]、[[MDCT]]
- **同类系统**：DualNet（TikTok 一代）、[[LiveNet]]、Tencent TRTC、Alibaba ApsaraVideo RTC；RTC 会议架构中的 [[SFU]] / MCU
- **同会议**：[[ATC-2025]]
- **对比**：server-side mixing（AnchorNet/DualNet/TRTC）vs viewer-side mixing（Competitor-1）vs 双连接解耦架构（Competitor-2/DualNet）