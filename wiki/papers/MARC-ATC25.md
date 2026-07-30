---
type: paper
name: MARC
full_title: "MARC: Motion-Aware Rate Control for Mobile E-commerce Cloud Rendering"
authors: [Yuankang Zhao, Furong Yang, Gerui Lv, Qinghua Wu, Yanmei Liu, et al.]
venue: ATC
year: 2025
tags: [cloud-rendering, rate-control, qoe, webrtc, e-commerce, rtc]
source_pdf: "[[atc2025-zhao-yuankang.pdf]]"
source_md: "[[atc2025-zhao-yuankang]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# MARC：移动电子商务云渲染的运动感知速率控制（ATC 2025）

> **原题**：MARC: Motion-Aware Rate Control for Mobile E-commerce Cloud Rendering

> **一句话总结**：淘宝 1.8B 帧测量表明移动电商云渲染中用户 motion / non-motion on-off 行为使 QoE 偏好动态变化，而 motion 帧 P99 send duration 达 non-motion 的 1.9×；MARC 在 [[WebRTC]] 内按帧级感知 motion 状态、用 N=10 步随机优化差异化码率，100 万+ session A/B 中 session freeze rate 降 71%、interaction ratio 升 20%。

## 问题与动机

移动电商（淘宝 3D 虚拟形象/商品展示）越来越多采用 **cloud rendering**：云端 [[Unreal-Engine]] 渲染高保真 3D 画面，经 [[WebRTC]] 以视频流送到手机，用户通过 tap/pinch/drag 等 gesture 交互。技术栈与 cloud gaming 相似（edge server、硬件编码器、pacing、FEC、[[Congestion-Control]]），但作者 claim 的 QoE 需求并不相同——不是「所有帧都要 50–150ms 一致低延迟」，而是 **intra-session 偏好随用户操作阶段切换**。

论文的 production pain point 很具体：即使用了 Pudica、SQP、GCC 等 cutting-edge RTC 优化，用户在 **最 actively engaged 的 motion phase** 仍频繁遭遇 latency spike，导致 early session abandonment。根因是现有 **rate controller** 对 motion frame 与 non-motion frame 使用同一套 bitrate 决策逻辑，无法区分两类帧在延迟/画质上的不同权重。

测量基础：2024.02–03 淘宝移动云渲染平台，200,846 sessions、1.8B frames、>100K users、>16,000 小时视频。系统配置为 1560×720@30fps、H.264 CBR、max 8 Mbps、infinite GOP（99.9% P-frame）。深度架构与实现细节回 [[atc2025-zhao-yuankang]] 或 [[atc2025-zhao-yuankang.pdf]]。

## 关键观察 / 隐含假设

- **观察 1：motion phase 下用户对 frame latency 的敏感度显著高于 non-motion，且对 bitrate 也更敏感。**
  - **证据**：session duration 对 latency 的线性回归斜率在 motion phase 比 non-motion 陡 75.7%；对 bitrate 斜率陡 37.8%。motion frame latency 持续升高会单调拉低 session duration，而 non-motion latency 超过 ~42ms 后 session duration 趋于稳定。bitrate >5 Mbps 后 motion 与否对 session duration 影响很小。
  - **依赖假设**：session duration / motion phase duration 能代理用户 engagement；server-side 测量的 frame latency（send duration + OWD≈RTT/2）能代表用户感知的 motion-to-photon 主导分量（论文称 client 侧优化后 MTP 中 frame latency 占 ~78%）。
  - **可能失效场景**：不同电商场景（静态商品旋转 vs 复杂 avatar 换装）、不同分辨率/帧率、或 client 侧渲染/解码瓶颈上升时，latency 权重可能重分配；高码率饱和区（>5 Mbps）下 motion-aware 差异化收益会缩小。

- **观察 2：用户行为呈典型 on-off 模式——短 motion burst + 长 non-motion 停顿。**
  - **证据**：74% motion phase 持续 2–4 帧（30fps 下 67–133ms），15% 为 5–9 帧；70% non-motion phase ≤15 帧（0.5s），30% 为长停顿。Fig. 3 展示典型「频繁换视角 → 停住细看」pattern。
  - **依赖假设**：e-commerce 3D 浏览的 interaction pattern 稳定，且 server 能在收到 motion command 后准确标记下一编码帧为 motion frame。
  - **可能失效场景**：cloud gaming 持续操控、云桌面连续滚动、VR/AR 长时 motion 等 workload 中 motion phase 更长，frame-level 33ms 决策窗是否仍足够需重新验证。

- **观察 3：相同 target bitrate 下，motion frame 实际更大、send duration 更长，是 motion phase 尾延迟恶化的直接机制。**
  - **证据**：P50 之后 motion frame size 系统性大于 non-motion（平均约 22%）；P99 send duration motion 82ms vs non-motion ~43ms（1.9×）。OWD P95 仅 29.5ms，send queue 是主因。无丢包 session 中 motion P99 send duration 仍达 72ms（占 lossy session 的 87.8%），说明不是 loss 主导。
  - **依赖假设**：CBR 编码下 frame content variability 导致 motion 帧更难压到目标码率；pacing rate 来自 [[Congestion-Control]] 估计，encoder 超产会堆积 sender queue。
  - **可能失效场景**：content-aware encoding、QP 级 frame size 控制、或 VBR/ABR 替代 CBR 后，「motion 帧更大」的结构性差异可能减弱；极端带宽骤降或长队列下 pacing rate 预测误差会放大。

- **假设 1：从 session-duration 线性回归斜率反推的 QoE 权重（motion latency penalty γ=1.275）可泛化为在线优化目标。**
  - **证据强度**：中。有 1.8B 帧相关性支撑，且 λ_m 消融显示 Pareto 前沿随 motion 权重移动；但 engagement 是 observational correlation，非因果 A/B 前验证，且 QoE 函数形式（concave q_R、quadratic q_L）是工程选择。

- **假设 2：短窗（N=10 帧）Markov motion 预测 + 历史 pacing/RTT 外推足以支撑 MPC 优化。**
  - **证据强度**：中。下一帧类型预测准确率 94–96%，但 motion **起始**预测准确率仅 ~36.8%；好在 motion 多连续出现，跟拍预测准确率提升 72%。predicted vs ground-truth motion 的 send duration CDF 几乎重合。论文未覆盖剧烈 cellular 带宽波动下的 predictor 失效。

## 核心方法

MARC（Motion-Aware Rate Control）完全部署在 **server-side [[WebRTC]] / Pixel Streaming 栈**（1,246 行 C++），客户端零改动。核心是把 §2 的三条 requirement——motion awareness、frame-level decision、differentiated bitrate——落成一个 **dynamic QoE-driven MPC** 问题。

**1. Motion frame 识别**：修改 UE Pixel Streaming 插件，用户 motion event 经 Datachannel 到达 server 后，由 WebRTC `PeerConnectionInterface` helper 通知 MARC，将 **下一帧** 标记为 motion frame。这是整个 motion-aware 链路的输入边界。

**2. Dynamic QoE objective**：从 Fig. 2 回归斜率归一化得到 motion 相对 non-motion 的 latency 权重比 1.275（quality 敏感度比 1.378）。每帧：

$$\mathrm{QoE}(i) = q_R(R_i) - \gamma(i) \cdot q_L(L(i)), \quad \gamma(i) \in \{1, 1.275\}$$

$q_R$ 为 concave diminishing-return 函数（借鉴 Vantage），$q_L$ 为 quadratic penalty（$L_{max}=150$ms）。该设计直接回应观察 1：motion 帧对延迟惩罚更重，non-motion 帧可换更高画质。

**3. Time-based sending model**：显式建模 frame enqueue → pacing 发送 → departure 全过程。编码间隔 $I$（30fps 下 33.3ms），帧大小 $d(R_i)$ 对 motion/non-motion **分别线性拟合**（回应观察 3：同码率下 motion 帧更大）。Queue 演化 $b(i)$、send duration $s(i)$、平均 pacing rate $C(i)$ 组成约束，总延迟 $L(i)=OWD(i)+s(i)$。这使优化器能看见「高码率 motion 连发 → queue 膨胀 → 后续帧 queueing delay」的耦合，而非像固定 bandwidth ratio 策略那样反应滞后。

**4. N-step stochastic optimization**：每编码完一帧，State Predictor 预测未来 $N=10$ 帧的 $\hat{M}$、$\widehat{OWD}$、$\hat{C}$，用 NLopt SLSQP 在连续码率空间 $[0,8]$ Mbps 上最大化 $\sum \mathrm{QoE}$，warm-start 上一帧解。决策必须在下一帧间隔内完成（实测 mean 24.6µs、max 5.4ms）。这回应观察 2 的短 motion burst：session 级或秒级 rate control 来不及在 2–4 帧窗口内降码率。

**5. State Predictor**：
- **Motion**：$M$ 位历史帧类型的 Markov 模型，离线统计 $2^M$ 状态转移概率，在线 hash lookup + Bernoulli 采样；空间 $O(2^M)$ 可跨 session 共享。
- **Pacing rate**：用近期 pacing rate 近似未来 $C(i)$，假设短窗内稳定（motion sequence 内 std <0.08）。
- **OWD**：smoothed RTT/2。

Case study（Fig. 6–7）展示关键行为：队列高时 motion 帧主动压低 bitrate/bandwidth ratio；队列空且处于 non-motion 时提高码率。相对 Latency-First（72% bandwidth）同延迟下平均码率 +26.1%；相对 Quality-First（95% bandwidth）queueing latency −59.2%，码率仅 −4.5%。

与同类工作的分界：[[Congestion-Control]]（GCC、Copa、SQP）负责带宽探测与 pacing rate，不直接优化 engagement-shaped QoE；Vidaptive 等虽动态调码率，但对 motion/non-motion 无差异化，且多为 reactive（检测到 send duration 超标才降），缺少 motion 前瞻。MARC 与作者同组的 Jitbright（jitter buffer 优化）互补，分别优化 transport 上游码率决策与 downstream playout。

## 设计取舍

- **Server-only vs client-assisted**：全部逻辑在云端，移动端零 CPU/电量开销，利于大规模部署；代价是 motion 识别依赖 Datachannel 事件到帧标记的时序假设，无法利用 client 侧 viewport/attention 信号。
- **连续码率 MPC vs 离散 ABR ladder**：连续空间 + 梯度优化更细粒度，但依赖 $d(R)$ 线性近似和 NLopt 收敛；编码器 CBR 模式下实际 frame size 仍有偏差，优化器需用历史 encoder output 校准。
- **固定 γ 权重 vs 在线学习**：γ 来自一次性大规模回归，部署简单、可解释；但不同商户/3D 内容/用户群可能需要重标定（论文 §6 讨论 porting 时需重做 engagement study）。
- **N=10 lookahead vs 更长视野**：N<10 尾延迟变差，N>10 收益递减且 COBYLA/SLSQP 耗时上升；选 10 是性能/开销折中，不是理论最优。
- **Markov motion 预测 vs 复杂时序模型**：极简预测保证 33ms 内可完成，motion onset 预测差（36.8%）被连续 motion 结构部分弥补；论文承认可用 transformer 等改进 pacing/RTT 预测，留作 future work。
- **不改 encoder 内部 vs QP/重编码控制**：仅用 encoder API 调 target bitrate，工程侵入小；牺牲了对 frame size 的硬约束能力，motion 帧「同码率更大」只能统计建模而不能从源头压制。

## 实验与结果

**Trace-driven simulation**（200K+ sessions trace 回放；bandwidth estimation 统一用 WebRTC，公平比较 rate control 策略）：

- Motion 帧 P95 send duration + queueing latency：相对 Zoom/Duo/WebRTC/Vidaptive 等降 **30%–55%**。
- Motion 帧 P95 frame latency：降 **22%–60%**（相对各 baseline 33–101ms 不等）。
- 同画质下 MARC 平均码率比 Duo 高 **35%**；即使 $\lambda_m=0$（无显式 motion 权重），MARC 仍靠 queue-responsive optimization 取得最高平均码率 + 更低尾延迟。
- Session 级 P95 frame latency：可调 $\lambda_s$ 扫出 Pareto 前沿，全面优于 baselines；median session QoE 超 baseline **3%–36%**，P95 QoE 高 **1.3%–21%**。
- 画质：PSNR 48.13→47.74（−1%）、VMAF 96.4→95.7（−1%），吞吐需求与 WebRTC 差 <3%。

**Predictor ablation**：

- 无 motion 预测时 median send duration **翻倍**；predicted vs ground-truth motion 几乎重合。
- Motion onset 难预测，但 consecutive motion 跟拍准确；约 2% non-motion 被误判为 motion，导致 non-motion median target bitrate 低 3%。

**Overhead**：客户端 0；服务端 per-session CPU +**1.3%**（渲染节点仍 GPU-bound，~10 sessions/GPU）。

**Production A/B**（2024.04.04–11，>**1M sessions**，MARC vs WebRTC default）：

- Frame latency：median −**29%**，P99 −**20%**；motion 帧 MTP>150ms 比例 −**20%**。
- Session freeze rate：平均 −**71%**（variance 也下降）。
- Session duration：**+9%**；interaction ratio（motion 时间占比）：**+20%**。

## 批判性分析

### 论证链条

论文的 observation → design → result 链条在 **淘宝云渲染** 这一特定 workload 上闭合得较好。三条测量观察直接映射到三个 design requirement；case study（Fig. 6）与 trace simulation 展示机制而非仅报 aggregate metric；production A/B 用 freeze rate、interaction ratio 等 engagement 指标闭合「降延迟 → 用户更愿意交互」的叙事。

最脆的跳步是 **从 session-duration 相关性到 causal QoE 最大化**。回归斜率导出 γ=1.275 在统计上合理，但 engagement 与 latency/bitrate 共变（活跃用户可能同时更容忍延迟或更频繁 motion）。A/B 结果支持 MARC 有效，却不能严格证明「正是 γ 数值最优」——λ_m 消融显示方向正确，但最优权重可能因内容而异。

第二个跳步是 **cloud rendering 结论外推到 cloud gaming / 云桌面**。论文在 §6 声称 porting 只需重标定 QoE mapping，但 cloud gaming 往往要求全程低延迟，motion/non-motion 二分法可能退化；长 motion phase 下 frame-level MPC 与秒级策略差距也会缩小。

### 假设压力测试

**Workload 漂移**：测量集中在淘宝 avatar/换装类 3D 场景。家具 AR 预览、3D 商品自动旋转（弱 interaction）、或直播带货式连续操作，on-off 比例与 motion 帧占比（全量仅 3.4%）会改变 predictor 与 γ 的有效性。

**网络环境**：A/B 在真实移动网络，但 edge-deployed OWD 很低（P95 29.5ms）。跨地域、WiFi 拥塞、弱网高 RTT 场景下，OWD 在 $L(i)$ 中权重上升，send-queue 优化收益可能相对下降；pacing rate 近似「近期恒定」在剧烈带宽波动时可能低估 queueing（论文 §6 承认）。

**Encoder / content**：CBR + infinite GOP + H.264 是特定栈。换 AV1、VBR、或 content-aware QP 后 motion 帧 size gap 可能变化，$d(R)$ 双线性模型需重训；若 encoder 能精确命中 target size，MARC 仍有用（论文 §6 强调 QoE 偏好差异仍存在），但 queue-driven implicit prioritization 会减弱。

**Motion 标注语义**：「收到 command → 标记下一帧」对 tap/drag 合理，但对连续手势是否覆盖整个 motion phase、是否存在 command 丢失/乱序，论文未做 sensitivity analysis。

### 实验可信度

**强项**：(1) 1.8B 帧 + 1M session 生产数据在 RTC rate control 领域极少见；(2) trace replay 喂 **exact future bandwidth** 的 controlled case study 能隔离 rate control 逻辑；(3) baselines 覆盖 WebRTC default、SQP、Vidaptive、Zoom/Duo/GoTo 商业模型；(4) predictor ablation、λ 扫描、N  horizon、solver 选择均有微观验证；(5) 画质指标说明不是「一味压码率」。

**弱点**：(1) Online A/B 仅对比 WebRTC default，未在 production 中并排 SQP/Vidaptive；(2) engagement 提升（+9%/+20%）未报告统计显著性或分 cohort 分析；(3) freeze count 来自 WebRTC stats，与商业 KPI（转化、GMV）仅间接关联；(4) simulation 中禁用 Vidaptive frame-skipping 保证公平，但可能低估 Vidaptive 在允许跳帧时的竞争力；(5) 因果上无法分离 MARC 与同期其他系统变更（尽管 A/B 随机分桶）。

### 系统性缺陷

- **多 tenant / 公平性**：论文未讨论单 edge 节点多 session 共享带宽时，MARC 逐 session 优化是否加剧资源争用；§6 提及 Minerva 类 VoD fairness 与 interactive state-dependent QoE 不同，但未实验。
- **故障与降级**：NLopt 不收敛、predictor 表缺失、Datachannel 延迟时的 fallback 策略论文未描述；max 5.4ms 优化耗时在极端负载下是否触发 frame drop 未测。
- **可观测性**：1,246 行 C++ 嵌在 Pixel Streaming + WebRTC，运维需理解 QoE 权重、queue 模型与 predictor 状态；论文未提供 debug playbook。
- **安全与隐私**：测量声明仅性能数据、脱敏；motion command 频率本身可能推断用户行为，论文未讨论。
- **兼容性**：依赖 UE Pixel Streaming 插件改动和 WebRTC fork；迁移到非 UE 渲染器或其他 RTC 栈需重新集成 motion 标注路径。论文未讨论。

## 局限与后续工作

- **局限 1**：QoE 模型仅含 quality + latency 两维，未纳入 rebuffer、码率切换平滑度、freeze 显式惩罚、内容复杂度等；Appendix B 显示 QoE 函数形式对决策影响大，简化模型可能漏掉多维 tradeoff。
- **局限 2**：Motion onset 预测准确率 ~37%，依赖 consecutive motion 结构兜底；对「单次短 tap」为主的 workload，前瞻降码率可能不及时。
- **局限 3**：Pacing rate / RTT 预测为短窗启发式，在极端 queue 或带宽剧变时可能低估 $L(i)$；论文建议 transformer 类时序预测，尚未验证。
- **局限 4**：γ 权重来自单一平台、单一时期的相关性分析；跨应用 porting 需重做 engagement study（作者承认），但缺少自动在线校准机制。
- **局限 5**：Production A/B 仅 vs WebRTC baseline；SQP/Vidaptive 在相同淘宝流量上的长期对照缺失。
- **Future work 1**：在 cloud desktop、远程 VR/AR 等 alternating manipulation workload 上重标定 γ 并测量 A/B engagement，验证 motion-aware 范式是否普遍优于 unified low-latency controller。
- **Future work 2**：将 action space 扩展到 QP 控制或 iterative re-encoding，量化能否进一步压缩 motion 帧 size tail 而不牺牲 queue model 简洁性。
- **Future work 3**：多用户 edge 节点下的 QoE fairness——当多个 MARC session 共享上行/encoder 预算时，state-dependent 权重是否可作为调度杠杆。
- **Future work 4**：用因果推断（如 instrumental variable、switchback）分离 latency→engagement 的因果效应，并在线学习 $\lambda_m, \lambda_s$ 而非固定离线回归值。

## 相关

- **相关概念**：[[QoE]]、[[WebRTC]]、[[Congestion-Control]]、[[Rate-Control]]、[[Cloud-Gaming]]、[[Real-Time-Communication]]、[[Motion-to-Photon-Latency]]
- **同类系统**：GCC、Copa、SQP、Pudica、Vidaptive、Jitbright（同作者 jitter buffer 优化）
- **同会议**：[[ATC-2025]]
- **源材料**：[[atc2025-zhao-yuankang]]、[[atc2025-zhao-yuankang.pdf]]
