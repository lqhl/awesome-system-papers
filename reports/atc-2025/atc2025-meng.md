# AnchorNet: Bridging Live and Collaborative Streaming with a Unified Architecture

**作者**：Tong Meng, Wei Zhang*, Dong Chen, Zhen Wang, Quanqing Li, Changqing Yan, Wei Yang, Chao Yuan, Le Zhang, Jianxin Kuang, Jianlin Xu（ByteDance）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/meng
**源文件**：[[atc2025-meng.pdf]]

---

## 一、背景

直播已成为主流社交媒体平台（TikTok、Instagram、Twitch 等）的核心功能。在传统的单主播直播（live streaming）基础上，连麦直播（collaborative streaming）作为增强互动性的新模式日益流行——观众可以被邀请成为连麦主播（co-broadcaster），与主播进行音视频互动，同时向各自的频道观众播出。

连麦直播为直播架构带来了新挑战：需要决定在哪里做流混合（broadcaster 端、server 端还是 viewer 端）、需要 WebRTC 协议栈支持更低延迟的主播间通信、以及需要在两种直播模式之间平滑切换。TikTok 采用 server 端流混合方案服务超过 10 亿用户，其第一代架构 DualNet 将两种模式解耦实现，导致模式切换时体验不佳。

---

## 二、要解决的问题

DualNet 架构在两种直播模式切换时存在以下核心问题：

1. **CDN 接入节点切换**：直播模式通过 DNS 查询 edge CDN 节点，连麦模式由 MCU 服务器接入不同 CDN 节点，导致切换时需要重新寻址，引发卡顿
2. **发布路径不一致**：两种模式使用不同的传输协议（RTMP vs RTP）和不同的音频编码器（AAC vs Opus），切换时需要建立新连接、重启拥塞控制器，造成 rebuffering
3. **音频编解码固有问题**：编码器延迟（encoder delay / priming）导致切换时产生前导静音；AAC 和 Opus 帧大小不一致（2048 vs 960 samples）导致尾部样本无法对齐
4. **实现僵化**：解耦架构使得两种模式对应独立代码仓库，优化需要跨组件协调，开发维护成本高

---

## 三、洞察与设计

**关键洞察**：在 server 端流混合架构下，只要将 RTC SFU 统一插入主播到 CDN 的发布路径中作为"锚点"，就能让主播在切换模式时始终维持同一个 CDN 接入节点和同一个传输会话，从而将两条独立路径问题化简为单路径上的流拼接问题。

基于这一洞察，AnchorNet 的核心设计：

- **统一发布路径**：RTC SFU 始终作为主播到 CDN 之间的中介。直播模式下，SFU 直接转发主播的 RTP 流并通过 RTMP 推送到 CDN；连麦模式下，MCU 混合各主播的流后回传给 SFU，再由同一 SFU 推送到同一 CDN 节点
- **统一上行协议**：主播在两种模式下都使用 RTP 协议上行到 SFU，避免协议切换和连接重建，同时还能利用用户态拥塞控制算法
- **CDN 接入协议兼容**：SFU 到 CDN 仍使用 RTMP，保持与现有 CDN 提供商的兼容性
- **音频编码选择**：保留 DualNet 的双编码器方案（主播端 live 用 AAC、collaborative 用 Opus；server 端统一输出 AAC 到 CDN），避免全 Opus 方案带来的高额 MCU 转码成本

---

## 四、实现细节

### 音频流拼接技术

这是 AnchorNet 的技术核心，通过四种 PCM 样本级操作消除模式切换时的音频毛刺：

1. **Extra Priming（额外启动样本）**：在新编码器启动时补充额外的静音样本，使得 priming 样本数恰好是帧大小的整数倍。例如 AAC 的 priming 为 5058 samples、帧大小 2048，补充 1086 个静音样本使总数为 6144 = 3 × 2048，这样前 3 帧全为静音帧可安全丢弃

2. **Duplicate Trailing Samples（尾部样本复制）**：主播端维护一个 ring buffer 存储最近输入到 egress 编码器的样本（大小等于 encoder delay），模式切换时将这些样本复制到 ingress 编码器，避免 egress 编码器缓冲区中的有效音频信号丢失

3. **Rescale Trailing Opus Samples（尾部样本缩放）**：MCU 在连麦模式结束时，通过上采样或下采样将剩余 Opus 解码样本调整为恰好一个 AAC 帧大小，确保输入是帧大小的整数倍。偏差控制在半个 AAC 帧以内（约 20ms）

4. **Reconstructing Overlapped MDCT Window（重建 MDCT 窗口）**：从连麦切回直播时，MCU 用直播模式的首帧数据填充 pre-encode buffer，重建最后一个转码 AAC 帧的 MDCT 重叠窗口，避免窗口边界处的音频伪影

### 部署优化

- **AV 同步**：利用 UI 布局切换（全屏→网格）的视觉遮蔽效应，注入人工视频 rebuffering 来对齐音视频
- **自适应播放速度**：切换到连麦时适当减速播放以避免缓冲耗尽，切换到直播时加速以降低延迟
- **自适应码率**：根据上行带宽和设备性能（电量、温度等）调整视频分辨率和码率

---

## 五、实验结果

### Micro-Benchmark（3 台小米 14 手机，同一 WiFi）

| 方案 | 音频卡顿 | 视频卡顿 | 特点 |
|------|---------|---------|------|
| AnchorNet | 0 ms | 最低 | 统一路径 + 音频拼接 |
| DualNet | 秒级 | 秒级 | 解耦架构 |
| Competitor-1（viewer 端混合） | ~100 ms 音频暂停 | 较低 | 统一 RTC 栈 |
| Competitor-2（server 端混合） | 首次切换长卡顿 | 首次切换长卡顿 | 类似 DualNet 的解耦设计 |

### 大规模 A/B 测试（2024 Q4，4 周）

| 指标 | 直播→连麦 | 连麦→直播 |
|------|----------|----------|
| 视频 rebuffering 次数 | −60.1% | −78.5% |
| 视频 rebuffering 时长 | −60.3% | −78.9% |
| 音频 rebuffering 次数 | −64.5% | −76.3% |
| 音频 rebuffering 时长 | −67.4% | −77.1% |

| 用户参与度 | 提升 |
|-----------|------|
| 主播每日活跃时长 | +0.53% |
| 连麦主播每日活跃时长 | +2.15% |
| 观众每日观看时长 | +3.83% |

直播模式（非切换场景）额外收益：视频 rebuffering −13.47%，音频 rebuffering −11.02%，推流帧率 +3.11%（得益于用户态拥塞控制）。

### Server 端开销

- 端到端延迟：全球平均与 DualNet 相当（DualNet 使用更大 jitter buffer 抵消了 AnchorNet 的 SFU-MCU 往返延迟）；距 MCU 集群远的地区连麦延迟多约 170ms
- 每个流混合任务：中位数 < 0.4 CPU 核 + 220 MB 内存；128 线程 / 500 GB 服务器可支撑 15K~30K 并发连麦频道

---

## 六、批判性分析

1. **Micro-benchmark 的理想化条件**：3 台手机同一 WiFi 的测试环境完全排除了真实网络波动，而论文也承认 A/B 测试的增益远不如 benchmark 极端。这种先用理想条件展示大幅优势、再用"生产环境更复杂"解释为什么实际增益打折的叙述方式，容易高估系统的纯粹架构贡献

2. **竞品对比不够公平**：Competitor-1 和 Competitor-2 只通过 packet dump 推断架构，没有控制其 CDN 部署规模、jitter buffer 策略等变量。Competitor-2 的首次切换长卡顿很可能是实现层面的 bug（audio mode 切换触发模块重启），不能说明其架构方案本身的劣势

3. **A/B 测试的归因问题**：AnchorNet 同时改变了传输协议（RTMP→RTP 上行）、拥塞控制（kernel→user-space）和音频拼接策略，无法分离各因素的独立贡献。直播模式下 13.47% 的 rebuffering 降低完全来自用户态拥塞控制，与架构统一无关

4. **MCU 集中部署的延迟代价被轻描淡写**：论文承认部分地区连麦延迟增加 170ms，但将其归为"未来通过边缘部署优化"。对于实时互动场景，170ms 的额外单向延迟（往返 340ms）是显著的体验退化

5. **成本分析缺失**：论文未给出 RTC 服务器部署成本与 CDN 成本的定量对比，"positive ROI" 的声称缺乏数据支撑。server 端混合的 MCU 成本是核心 trade-off，仅给了单任务资源消耗数据

6. **音频拼接技术的通用性存疑**：四种拼接技术高度依赖 AAC/Opus 的特定配置参数（priming samples、frame size），换用其他编码器需要重新推导和验证，但论文声称这些技术"universally applicable"

---

## 七、总结

AnchorNet 是 TikTok 的第二代直播架构，通过将 RTC SFU 统一插入主播到 CDN 的发布路径，解决了 DualNet 解耦架构在直播与连麦模式切换时的卡顿问题。其核心技术贡献是四种 PCM 样本级音频拼接技术，消除了编码器延迟和帧大小不一致导致的音频毛刺。大规模 A/B 测试验证了 rebuffering 降低 60%~78% 和用户参与度提升。主要局限在于 MCU 集中部署带来的额外延迟，以及系统设计与 TikTok 特定规模和基础设施的强耦合，对其他平台的参考价值需要结合各自的部署条件判断。
