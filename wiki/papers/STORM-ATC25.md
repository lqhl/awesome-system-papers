---
type: paper
name: STORM
full_title: "STORM: a Multipath QUIC Scheduler for Quick Streaming Media Transport under Unstable Mobile Networks"
authors: [Liekun Hu, Changlong Li]
venue: ATC
year: 2025
tags: [multipath-quic, mobile-networking, streaming-media, scheduling, reliability-aware]
source_pdf: "[[atc2025-hu-liekun.pdf]]"
source_md: "[[atc2025-hu-liekun]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# STORM: a Multipath QUIC Scheduler for Quick Streaming Media Transport under Unstable Mobile Networks (ATC 2025)

> **一句话总结**：STORM 的关键观察是移动场景下 [[MPQUIC]] 的高尾延迟主要来自最后一公里无线链路突发退化，以及 reliable / unreliable 数据在同一调度队列里互相阻塞；它用 signal-watermark 跨层反馈和 reliability-aware Dual-Q 调度，在真实移动设备上把 99th percentile packet delay 降低 98.2%，并把不稳定网络下流媒体帧率提升 1.95x。

## 问题与动机

[[Multipath-Transport]] 对移动端流媒体很诱人：手机、车载终端或 360 度视频客户端通常同时有 WiFi、LTE/5G 等接口，单路径带宽不够时，多路径可以把吞吐撑起来。问题是流媒体不是只要平均吞吐，视频会议、VR/MR、cloud gaming 更怕尾延迟和卡顿。论文的起点是一个反直觉现象：MPQUIC 在静止、稳定链路下能提升帧率，但在用户移动时，加入第二条路径可能让体验比单路径更差。

作者在 Xiaomi 12S Pro 上把视频会议跑到 MPQUIC，发现移动时 multipath 的 tail latency 可到 4.59s，是静止场景的 5.37x，也比原始单路径更糟。根因不是 QUIC 本身不适合流媒体，而是现有 scheduler 的控制信号太慢：minRTT、拥塞窗口、历史 QoE 都是在丢包和排队已经发生之后才显现，无法在无线信号快速变差时及时停用或降载坏路径。

第二个动机来自 [[QUIC]] 的可靠性分层。流媒体里 I-frame、控制数据等关键数据需要可靠传输，部分 P/B frame 或 masking stream 可以不可靠传输。MPQUIC 虽然能同时承载 STREAM 和 DATAGRAM，但传统 scheduler 没有把 reliability 当成一等调度维度。burst loss 触发大量 reliable retransmission 后，不可靠数据在队列里积压；积压的不可靠数据随后又挡住新的 reliable 关键数据，形成 mutual blockage。

因此 STORM 的目标不是一般性地提高 multipath throughput，而是在移动不稳定无线网络下让 streaming media 的关键数据更快到达。它选择了一个偏系统工程的路线：把无线模块的信号强度暴露给传输层，同时把可靠数据和不可靠数据拆成不同调度对象。

## 关键观察 / 隐含假设

- **观察 1：不稳定移动场景下的尾延迟瓶颈主要在最后一公里无线链路，而不是 core network。** 论文通过接近 traceroute 的方式定位进入 core network 后的 first-hop IP，用它近似测量设备到基站/AP 的无线链路 RTT。在地下商场、地铁、酒店、高铁等场景里，最坏 E2E RTT 达 3781ms，其中 wireless link RTT 达 3750ms。
  - **依赖假设**：first-hop RTT 能足够代表 base station / AP 到设备的无线段延迟；测试场景覆盖了常见移动端信号退化模式。
  - **可能失效场景**：如果瓶颈来自运营商 core、云边入口、跨区域路由或服务器排队，单靠无线信号反馈可能过早降载健康路径，甚至把问题误归因到 last mile。

- **观察 2：RSSI/RSRP/SINR 的快速下降与 burst loss 有强相关，transport-layer 指标反应太晚。** Fig. 3 显示 RSSI 在约 -70dBm 时 loss rate 基本低于 10%，但降到 -80dBm 后出现 60%-80% loss 的密集簇，个别可到 100%。作者据此认为 scheduler 应该在信号变差时立即调整，而不是等 RTT、loss 或 QoE 指标累计出来。
  - **依赖假设**：OS API 暴露的 WiFi / cellular signal 指标新鲜、可用，并且与用户实际数据路径对应。
  - **可能失效场景**：多 SIM、VPN、WiFi mesh、弱信号但低负载、强信号但 AP 拥塞等场景会削弱 signal strength 到 packet outcome 的映射。

- **观察 3：可靠与不可靠数据混排会放大尾延迟。** 在 MPQUIC vs fully reliable MPQUIC-R 的实验里，MPQUIC 的 median 和 third quartile packet delay 更好，但最大 packet delay outlier 反而到 MPQUIC-R 的 1.65x。Case-2 中区分 STREAM/DATAGRAM 后，默认 scheduler 下关键数据最大等待时间只降低 11.79%，DAMS 甚至增加 39.93%；Case-3 强制 unreliable data 等 reliable queue 清空后，关键数据等待显著下降。
  - **依赖假设**：应用能正确标注 critical / non-critical data，且不可靠数据丢弃不会破坏整体语义。
  - **可能失效场景**：如果 workload 中所有数据都强依赖、不可丢，或应用无法提供 frame priority / deadline，RAS 的收益会明显下降。

- **假设 1：跨层暴露无线信号比纯传输层估计更值得。**
  - **证据强度：中。** 论文展示了 signal capture 与 actual signal 的平均 bias 约 1.14%，并通过 ablation 证明 SWM 重要；但它没有证明所有 Android 机型、运营商、WiFi 芯片和 OS reporting policy 下都有同等新鲜度。

- **假设 2：移动端常见流媒体 workload 有足够清晰的 priority / deadline / reliability metadata。**
  - **证据强度：中。** 视频会议、低延迟直播、360 度视频三个应用能映射到 STORM API，但这更像 prototype-friendly 的应用集合；现有商用媒体栈是否愿意改 API、暴露 GOP 内部语义，论文讨论较少。

## 核心方法

STORM 由两个核心组件组成：Signal-Watermark Mechanism (SWM) 和 Reliability-Aware Scheduling (RAS)。SWM 解决 scheduler 看不见无线链路突然退化的问题，RAS 解决 reliable / unreliable 数据在同一发送逻辑中互相阻塞的问题。二者共同嵌入 [[MPQUIC]] sender / receiver workflow：移动设备侧采集 signal，生成 PATH_ALERT 反馈；sender 侧根据 feedback 调整路径启停和数据分配。

SWM 在移动设备 wireless module 上加 adapter layer，每 100ms 通过 Android 的 WifiManager / TelephonyManager 读取 RSSI、RSRP、SINR，并用 atomic variables 暴露给 MPQUIC。为避免阻塞 QUIC event loop，信号采集在独立线程中进行。蜂窝链路用 RSRP 和 SINR 的 weighted geometric mean 归一化成 base quality，WiFi 则主要用 RSSI；随后用 loss trend modulation factor 惩罚继续上升的丢包，得到 $Q \in [0,1]$。

SWM 用三个 watermark 控制路径状态：Good=0.45、Warning=0.32、Outage=0.21。低于 Warning 生成 warning feedback，用于降低该路径的流量份额；低于 Outage 生成高优先级 outage feedback，要求 sender 停止在该路径调度。恢复采用 Fast Suppression / Slow Recovery：信号变差立即反馈，信号恢复则需要稳定超过阈值，默认 $T_{rec}=400ms$。watermark 还会按后续 burst loss 自适应调整，避免固定阈值在设备或环境变化后失效。

RAS 把应用数据放进 Dual-Q：Reliable Queue (RQ) 以 block 管理可靠数据，每个 block 带 priority 和 deadline；Unreliable Queue (UQ) 以 stream 管理不可靠数据，并按 deadline 排序。可靠 block 的分配目标是让两条路径上的数据尽量同时到达，而不是简单平均切分。分配公式同时考虑 path bandwidth、one-way delay 和 SWM feedback 形成的 $F_i$，因此坏信号路径即使带宽估计还没降下来，也会被提前降载。

对可靠数据，RAS 还用 residual time、block size、当前带宽与最低所需带宽的 gap 来计算 urgency。若一个 block 已经不可能在 deadline 内完成，scheduler 会延后它，优先让仍有机会按时到达的数据完成。最终权重结合 bandwidth gap、block priority 和剩余数据比例，避免已经发送大半的 block 因体积小而被不公平地拖后。

对不可靠数据，RAS 不再让它和 reliable blocks 竞争快路径。它利用 reliable block 在快慢路径上完成时间不同造成的 slow-path time hole，把 UQ stream 注入慢路径空洞中。这样做牺牲了不可靠数据的即时吞吐自由度，但限制了它阻塞 reliable data 的范围：即使出现冲突，也只会影响一个 retransmission window，而不是让一批 DATAGRAM 堵住后续 key frames。

Dynamic Multipath Management 负责处理 outage feedback。STORM 没有复用 MPQUIC 既有 PATH_STANDBY / PATH_AVAILABLE 语义，因为 STANDBY 路径仍可能残留 in-flight data，且在可用路径 cwnd 耗尽时仍会被使用。它新增 PATH_ALERT 帧承载 SWM feedback。路径被停用后，RAS 会对未确认 reliable data 做 deadline-aware reinjection；若按剩余路径带宽已经赶不上 deadline，则丢弃，unreliable data 直接丢弃不重注入。

实现上，STORM 基于 Alibaba XQUIC，利用 RFC9221 QUIC DATAGRAM 和 MPQUIC draft 里的 multipath 能力。核心改动是 1342 行 C 代码和 102 行 Java adapter，不需要 root 或 kernel recompilation。上层应用需要调用 `STORM_send` 并提供 deadline、priority、reliability 等 metadata；这比 proxy 方案侵入应用更多，但保留了调度所需语义。

## 设计取舍

- **跨层信号 vs 纯端到端抽象**：SWM 打破了传输层只看 RTT/loss/cwnd 的抽象，收益是更早感知无线退化；代价是依赖 OS / device API、信号指标语义和 Android JNI 路径，跨平台通用性弱于纯 MPQUIC scheduler。
- **应用显式 metadata vs 透明 proxy**：STORM 要求应用提供 deadline、priority 和 reliability，因而能做更细调度；代价是不能完全透明部署，对现有媒体应用需要 API 集成和语义标注。
- **保护 reliable critical data vs 最大化 aggregate utilization**：UQ 只利用 slow-path time hole，可能让可丢弃数据的吞吐更保守；换来的是关键 reliable block 的尾等待时间更低。
- **快速 suppress vs 慢恢复**：路径坏掉时立即停用降低 burst loss，恢复时等待 400ms 稳定性降低振荡；代价是在信号实际已恢复时会短时浪费可用带宽。论文也指出 mobility 更高时 $T_{rec}$ 可能需要变大。
- **deadline-aware discard vs 完整交付**：对赶不上 deadline 的 reliable block 延后或放弃重注入，符合实时媒体 QoE，但对语义不能容忍丢关键 block 的应用不适合。

## 实验与结果

- **动机实验**：移动场景下 MPQUIC 的 tail latency 到 4.59s，是静止场景的 5.37x；视频会议中 5G+WiFi 的平均 FPS 比单 5G 低 18.4%，最坏时 multipath 掉到 10fps 而单 5G 仍有 25fps。
- **last-mile evidence**：多场景 breakdown 中，最坏 E2E RTT 3781ms，wireless link RTT 3750ms，支撑“最后一公里无线链路是主要延迟瓶颈”的 claim。
- **microbenchmark completion rate**：30Mbps、每 100ms 六个 GOP-like blocks、300ms deadline 的实验里，带宽从充足降到 <10,15> Mbps 时 MPQUIC completion rate 从 99.9% 掉到 26.1%；<5,10> Mbps 下 MPQUIC 和 DAMS 近乎无法按时完成，而 STORM completion rate 平均只下降 49.3%。
- **高优先级等待时间**：带宽不足时 MPQUIC 和 DAMS 的最大等待时间分别上升 44.3x 和 54.5x，最坏到 11s；<5,10> Mbps 下 STORM 最大等待时间为 MPQUIC 的 49.6%、DAMS 的 45.3%。
- **RTT variation**：一条路径固定 30ms、另一条从 30ms 到 180ms 时，STORM completion rate 始终高于 MPQUIC 和 DAMS；在 <30,120> RTT 组合下，STORM 比 MPQUIC 和 DAMS 分别高 37.3% 和 37.6%。
- **ablation**：关闭 SWM 让 goodput 下降 26.6%、rebuffering time 增加 6.8x；关闭 RAS 让 goodput 下降 15.7%、rebuffering time 增加 2.9x，说明 signal feedback 和 reliability-aware scheduling 都是必要组件。
- **overhead**：RAS Dual-Q 平均处理时间 5.03ms，占总传输时间 68.1ms 的 7.4%；JNI 最重调用平均 78us，每 100ms 一次，折合每秒约 780us CPU 时间；SWM feedback 算法是 O(1)。
- **真实应用 QoE**：在视频会议、低延迟直播、360 度视频的真实移动测试中，STORM 在 changing signal strength 下把 video conference 中低于 24fps 的 unsmooth ratio 相比 MPQUIC 改善 95.1%、相比 DAMS 改善 96.8%；stall duration 相比 MPQUIC 和 DAMS 分别改善 83.0% 和 85.2%。
- **360 度视频**：STORM 的 median user-perceived ratio 为 0.81，median PSNR 为 46.1dB，相比没有 SWM 的 STORM-U 提升 11.1% 和 7.7%。
- **transport tail**：真实应用里 STORM 平均 retransmission ratio 为 1.5%，STORM-U 为 4.1%；相对 MPQUIC，99th percentile packet delay 降低 98.2%。Appendix 中绝对 CDF 显示 STORM 的 90% latency 低于 68.2ms，99% 低于 129.8ms；MPQUIC 90% 低于 89.8ms，但 99% 到 758.6ms，DAMS tail 可到 6.60s。

## Critical Analysis

### 论证链条

论文的 observation -> design -> result 链条总体闭合。last-mile breakdown 支撑 SWM，reliable / unreliable mutual blockage 支撑 RAS，ablation 也显示两者都不是装饰性组件。尤其是 STORM-U 的结果很有价值：只有 RAS 不够，signal feedback 对移动突发退化确实关键。

但论证里有一个外推需要小心：作者把多个真实移动场景中的无线段延迟占比解释为“移动 MPQUIC 的主要瓶颈总在 last mile”。这对他们测试的手机、城市网络和 server placement 成立，但并不自动覆盖跨运营商、跨国 CDN、edge congestion 或 WiFi AP 过载场景。更稳妥的结论是：当移动端 signal fluctuation 触发 burst loss 时，last-mile signal 是比 transport feedback 更早的控制信号。

RAS 的逻辑也比较强，因为它不是只在 intuition 上说“关键帧优先”，而是用 Case-1/2/3 展示了仅仅把 uncritical data 标成 DATAGRAM 不足以解决 blocking。真正的关键在于调度对象和队列结构变化：可靠数据以 block 对齐到达，不可靠数据只填 time hole。

### 假设压力测试

第一个压力点是 signal freshness。论文测得 captured vs actual signal bias 平均 1.14%，并讨论最多 300ms capture-to-feedback delay 仍可接受；但 Android signal reporting 是设备和厂商相关的，未来如果 OS 为省电或隐私降低 reporting frequency，SWM 会退化成另一个滞后信号。

第二个压力点是 workload metadata。STORM 的优势依赖应用告诉传输层哪些数据是 reliable、unreliable、deadline 和 priority。对自研视频会议、直播、360 度视频这类 prototype 能做到，但通用浏览器、WebRTC stack、加密媒体 pipeline 或第三方 SDK 未必愿意暴露足够细的 frame semantics。

第三个压力点是 two-path assumption。论文公式和 time-hole 直觉主要围绕两条路径展开。手机常见是 WiFi+cellular，设定合理；但如果扩展到 WiFi+5G+satellite、多 SIM、多 WiFi radio，Dual-Q 与 time-hole scheduling 是否仍简单有效没有证明。

第四个压力点是 fairness / coexistence。STORM 面向单设备 QoE，坏路径降载、好路径优先会改变每条接入链路上的 traffic pattern。论文没有讨论与其他 flow 的公平性，也没有讨论多个 STORM clients 同时在同一 AP 或 cellular cell 里使用 signal-aware scheduling 会不会产生同步振荡。

### 实验可信度

实验覆盖不错：有 controlled lab microbenchmark、trace replay deep dive、真实移动应用三类。baseline 包括 MPQUIC、minRTT、DAMS、fully reliable variants、STORM-U，能分离 SWM 和 RAS 的效果。指标也覆盖了 completion rate、waiting time、goodput、rebuffering、FPS、stall、SSIM/PSNR、UPR、retransmission、latency percentile。

主要不足是规模和异质性。真实设备基本围绕 Xiaomi 12S Pro、Tencent Cloud Asia、若干校园/城市移动位置展开；这对系统论文已经不弱，但还不是大规模 production trace。参数 Good/Warning/Outage、RSRP/SINR weights、$T_{rec}$ 虽有 sensitivity study，却仍可能需要按设备、运营商、速度、WiFi deployment 重新调。

另一个实验边界是应用工作负载比较“配合”STORM：GOP priority、deadline、unreliable B frame 或 masking stream 都能自然映射到 API。论文没有展示 metadata 错标、priority 估计错误、deadline 太激进或应用无法提供 semantic hints 时的退化曲线。

### 系统性缺陷

STORM 的部署复杂度集中在三处。第一是跨层 adapter：虽然 Android 只需 102 行 Java，不需要 root，但 iOS、桌面 OS、浏览器 sandbox 或车载定制系统的可行性不同。第二是 QUIC stack 改动：新增 PATH_ALERT 和调度逻辑要求 endpoint 支持，不能只靠网络中间盒升级。第三是应用 API 改动：`STORM_send` 的 metadata 设计使性能来自应用语义，而不是完全透明的传输替换。

论文没有深入讨论故障恢复和可观测性。例如 PATH_ALERT 丢失、feedback 乱序、signal API 返回异常、path state 与 congestion controller state 不一致时系统如何调试。它也没有讨论安全或隐私：把无线信号状态反馈给 sender 是否会暴露用户移动或位置信息，尤其当 sender 是云服务时。

隔离性也未展开。RAS 优先可靠关键数据对单应用 QoE 有利，但如果同一 MPQUIC connection 中多个 stream 属于不同 tenant 或不同应用模块，priority API 可能变成资源争用点。论文默认应用是可信的、单一 QoE 目标明确的媒体应用。

## 局限与 Future Work

- **局限 1：平台依赖。** SWM 依赖 Android wireless signal API 和 JNI adapter；需要验证 iOS、Linux laptop、车载 OS、不同 baseband / WiFi chipset 上 signal freshness 与 overhead 是否类似。
- **局限 2：应用需要暴露语义。** STORM 不是透明 multipath replacement；它需要 deadline、priority、reliability metadata。后续可以测量自动从 codec / RTP / WebRTC metadata 推断这些字段时损失多少性能。
- **局限 3：两路径设计边界。** 当前叙述和公式主要围绕双路径。可验证的后续问题是：在三条以上异构路径中，time-hole injection 是否仍优于更一般的 deadline-aware optimization。
- **局限 4：参数泛化不足。** Good/Warning/Outage、$w_{rsrp}$、$w_{sinr}$、$\gamma$、$T_{rec}$ 都有默认值和局部 sensitivity study，但缺少跨运营商、速度、设备的自动调参评估。
- **局限 5：公平性和多客户端交互未讨论。** Future work 可以在同一 WiFi AP 或 cellular cell 内运行多个 STORM clients，测量是否产生同步 path deactivation、带宽抢占或对非 STORM flows 的伤害。
- **Future work 1：production trace validation。** 用真实移动视频会议或直播 trace 回放，比较 STORM、STORM-U、DAMS、Chorus/XLink 类 QoE-driven scheduler 在不同 mobility class 下的 latency/QoE/fairness。
- **Future work 2：semantic degradation test。** 系统性注入错误 priority、过紧 deadline、缺失 reliability 标注，量化 STORM 对应用 metadata 质量的敏感度。
- **Future work 3：privacy-preserving feedback。** 设计只暴露 coarse path health 而不暴露细粒度 signal trajectory 的 PATH_ALERT variant，测试是否保留主要性能收益。

## 相关

- **相关概念**：[[Multipath-Transport]]、[[MPQUIC]]、[[QUIC]]、[[Streaming-Media]]、[[Congestion-Control]]、[[Deadline-Aware-Scheduling]]、[[Reliability-Aware-Scheduling]]、[[Wireless-Link-Bottleneck]]
- **同类系统**：[[MPTCP]]、[[DAMS]]、[[Chorus]]、[[XLink]]、[[POLYCORN]]、[[CellFusion]]
- **同会议**：[[ATC-2025]]
- **源材料**：[[atc2025-hu-liekun]]、[[atc2025-hu-liekun.pdf]]
