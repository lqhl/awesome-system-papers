---
type: paper
name: SplitConn
full_title: "Internet Connection Splitting: What's Old is New Again"
authors: [Gina Yuan, Thea Rossman, Keith Winstein]
venue: ATC
year: 2025
tags: [networking, congestion-control, bbr, quic, performance-enhancing-proxy]
source_pdf: "[[atc2025-yuan.pdf]]"
source_md: "[[atc2025-yuan]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Internet Connection Splitting: What's Old is New Again (ATC 2025)

> **一句话总结**：基于「split throughput ≈ min(两段独立 end-to-end throughput)」这一启发式，在 mininet 上系统重测 [[Performance-Enhancing-Proxy|PEP]] 相关性——[[BBR]]v1 几乎不需要拆分（~85% 链路利用率），但为公平共存而增强丢包敏感的 BBRv2/v3 在 188 个网络配置里 split 收益 ≥3× 且利用率 ≥50%，其中 79% 落在 CUBIC 不受益的 middle-mile/对称丢包场景；同名 [[CUBIC]]/BBR 在 Linux TCP 与三套 [[QUIC]] 实现间行为差异巨大，故 PEP 远未因 BBR/QUIC 而过时。

## 问题与动机

1990 年代起，运营商在卫星、蜂窝和无线 last-mile 上广泛部署透明 [[TCP]] PEP（performance-enhancing proxy）：在路径中点拦截三次握手，把一条端到端连接拆成两段独立 [[Congestion-Control|拥塞控制]] 与 ACK/重传域，缩短 loss/拥塞反馈环路，缓解长 RTT + 随机丢包对 loss-based 算法（如 [[CUBIC]]）的吞吐伤害。

近十年两件发展让社区普遍认为 PEP「正在退场」：(1) Google 2016 年推出的 [[BBR]] 以带宽/RTT 建模为主、弱化丢包信号，且已控制大量互联网流量——业内 anecdote（如 AWS 切 BBR 后 mobile PEP 收益下降）暗示 PEP 部署锐减；(2) [[QUIC]] 端到端加密使透明 connection-splitting 不可行，但 Google 等大流量源大规模部署 QUIC 后并未观测到相对 TCP+PEP 的明显性能退化，似乎说明端到端方案已「足够好」。

作者 claim 的边界很明确：这不是再推销 PEP 产品，而是用可控 emulation 重新检验「BBR + QUIC 是否让 connection-splitting 在 sustained throughput 维度上 obsolete」。论文聚焦**长流 goodput**，不覆盖 startup、jitter、重传开销或多流公平性。深度测量细节回 [[atc2025-yuan]] 或 [[atc2025-yuan.pdf]]。

## 关键观察 / 隐含假设

- **观察 1**：在理想分段条件下，长流 split throughput 可由两段 path 各自独立测得的 end-to-end throughput 取最小值近似。
  - **证据**：对 BBRv3 在 80 ms 总延迟、10 Mbit/s 瓶颈、0%/4% 总丢包的多组 split 配置，heuristic 预测与 PEPsal 实测趋势一致；平均误差 ±4%，最大 ±14%，略偏高估。
  - **依赖假设**：瓶颈可由「测得吞吐最低的那段」标识；PEP 两侧队列/突发发送行为不主导结果；每段可用 delay/bandwidth/loss 三参数刻画。
  - **可能失效场景**：瓶颈靠近 sender 远端、小队列 + 突发发送导致 send buffer 饱和；蜂窝带宽波动、ACK 聚合、多流竞争、非独立丢包——heuristic 未建模这些因素。

- **观察 2**：BBR 算法演进改变了 split 收益，而非消灭它——BBRv1 高利用率使 split 无利可图，BBRv2/v3 为与 loss-based CC 公平共存而回归丢包敏感后，end-to-end 利用率在 lossy 场景下降，split 相对收益重新出现。
  - **证据**：Fig. 4 热图显示 BBRv1 在 10 Mbit/s、0–4% loss、1–100 ms delay 下几乎始终高利用率；BBRv3 在相同空间出现与 CUBIC 类似的 utilization 塌陷区。三类代表场景（Fig. 1）中 BBRv3 split 后可达高瓶颈利用率，而 BBRv1 split/unsplit 几乎无差。
  - **依赖假设**：Linux kernel fork 上的 Google BBRv2/v3 实现能代表生产流量演进方向；长流 HTTPS bulk transfer 能代表 PEP 传统优化目标。
  - **可能失效场景**：仍大量部署 BBRv1 的 CDN（Akamai、Meta、Cloudflare TCP）短期看不到 split 收益；短流/Web 页面、视频 ABR 等 metric 可能讲述不同故事。

- **观察 3**：BBRv3 在 CUBIC 不受益的网络类上仍可从 split 获利，尤其 middle-mile 双段丢包与对称高延迟场景。
  - **证据**：7875 种 (s1,s2) 组合穷举中，满足「split 改善 ≥3× 且 split 利用率 ≥50%」的：CUBIC 942 个、BBRv3 188 个、BBRv1 0 个。CUBIC 全部落在 Class I（不对称 + lossy last-mile）；BBRv3 仅 21% 在 Class I，其余在 Class II（两段都丢包、不对称延迟）和 Class III（两段都丢包、对称延迟 >1 ms）。
  - **依赖假设**：卫星/无线 ad-hoc 的 middle-mile 丢包可用静态 random loss 近似；PEP 放在非 edge 位置仍有部署可行性。
  - **可能失效场景**：真实 middle-mile 丢包常与 FEC/专有卫星协议绑定，简单 TCP split 能否替代需 field trial；参数空间不反映真实路径分布，数字本身不宜外推为「全网 X% 路径需要 PEP」。

- **假设 1**：「algorithm/implementation/version」三元组比「BBR vs CUBIC」或「QUIC vs TCP」更能预测性能与 split 行为。
  - **证据强度**：强。Google quiche 与 Linux TCP 同 CCA 最相似；Cloudflare quiche BBR 基线性能与 Linux 差异巨大；picoquic BBRv3 对 delay 反应矛盾；部分 QUIC CUBIC 在 TCP CUBIC 不受益的 Class II/III 场景反而可能受益（Fig. 6）。
  - **可能失效**：差异可能部分来自 QUIC 传输机制（0-RTT、stream multiplexing）而非纯 CC 实现；论文未完全解耦。

- **假设 2**：单流 isolation 实验足以支撑「CC 对 loss/delay 响应」层面的 split 收益推断。
  - **证据强度**：中。经典 TCP friendliness 传统支持单流分析；但 split 连接高吞吐可能加剧多流不公平，论文明确未测 inter-flow fairness。

## 核心方法

核心贡献是 **split throughput heuristic** 加上可复用的 emulation cache，使「PEP 是否值得部署」从「为每对路径跑真实 splitter」降为「测 150 个单段配置 + 组合推理」。

**网络模型**：每段用 `(delay, bandwidth, loss)` 描述。compose 规则：delay 相加（短段 1 ms 时取较长段 delay）；bandwidth 取 min；loss 在小丢包率下近似相加。参数空间为 5×6×5=150 组合——带宽 10–50 Mbit/s、单向延迟 1–100 ms、随机丢包 0–4%，意在覆盖 Wi-Fi last-hop 到卫星 RTT 的 PEP 典型场景。

**测量基础设施**：CloudLab mininet 两拓扑——单段缓存 end-to-end 吞吐；双段 + 中间 router 用 PEPsal 做透明 TCP split 验证。链路用 `tc-netem`（delay/loss）+ `tc-htb`（带宽）+ RED 队列引入拥塞丢包。客户端拉取「瓶颈 10 秒可传数据量」的 HTTPS payload，报告 application-layer goodput（median n=20）。

**CCA 覆盖**：Linux TCP 的 CUBIC、BBRv1（5.15 kernel）、BBRv2/v3（Google kernel fork）；QUIC 侧 Google quiche、Cloudflare quiche、IETF picoquic 各自的 CUBIC/BBR 实现（Table 2，共 13 组）。TCP split 用 PEPsal 拦截 SYN；QUIC 无法透明拆分，split 行为完全由 heuristic 从各段 end-to-end 测量外推。

**分析流程**：先 cache 150 个单段 `throughput(s)`，再对 7875 个 `(s1,s2)` 计算 `pred_split = min(t1,t2)`、`pred_e2e = throughput(compose(s1,s2))`，用 split improvement 与 utilization 阈值筛选受益场景并聚类为 Class I/II/III。§6 用 BBRv3 在固定 end-to-end path 上的多种 split 切分验证 heuristic 精度。

该方法直接回应观察 1：把探索空间从「CCA × 拓扑 × PEP 位置」压缩到「CCA × 150 段参数」，并顺带解决 QUIC 无法插透明 PEP 的测量盲区——与作者同组的 [[Sidekick-NSDI24]] / Sidecar 路线（协议无关、显式 in-network assistance）形成问题背景呼应。

## 设计取舍

- **启发式简洁性 vs 物理精度**：不建模 PEP 队列、瓶颈相对 sender 位置、突发性与 buffer 占用，换取对 7875 组合的可扩展扫描；§6 表明趋势可靠但绝对值可能高估 ≤14%。
- **Emulation vs 真实网络**：mininet + 单流 HTTPS 可复现、可穷举，但缺少多流、真实蜂窝波动、运营商 policer、Wi-Fi 链路层 ARQ 等；结论宜读作「机制级假说」而非 deployment guide。
- **长流吞吐 vs 全栈性能**：PEP 历史上也优化 TTFB、抖动、重传效率；论文主动只评 sustained throughput，可能低估「BBRv1 不需要 split」在交互式业务上的适用面，也可能高估「split 有益」在短流主导 CDN 上的普适性。
- **透明 PEP vs 端到端原则**：PEP 破坏 [[End-to-End-Argument|端到端论证]]、加剧协议僵化（ossification），论文不做伦理辩护，只论证性能层面尚未被 BBR/QUIC 替代；未来方向是 protocol-agnostic assistance（如 MASQUE、HTTP datagrams、Sidekick 类方案）。
- **穷举参数空间 vs 真实分布**：7875 组合均匀枚举，不加权真实 Internet 路径分布；作者强调识别「网络类」而非计数「多少路径」。

## 实验与结果

- **BBR 演进反转 split 收益**：BBRv1 end-to-end 在 loss/delay 扫参下近满利用率（~85%+），split 几乎无提升；BBRv2/v3 end-to-end 在 lossy 区域塌陷，但 split 后维持较高利用率。例：100 ms 0% 段 + 1 ms 4% 段 → split 利用率 0.82，compose 后 e2e 仅 0.49，split 显著更优。
- **BBRv3 受益场景 ⊃ CUBIC**：filter「split ≥3× 且 util ≥50%」后 CUBIC 942 场景（全 Class I），BBRv3 188 场景（Class I 38 + Class II 72 + Class III 78）。Fig. 1 三类代表设置中，CUBIC 仅 (a) lossy last-mile 受益；(b)(c) 仅 BBRv3 split 后达到高利用率而 unsplit 极低。
- **Heuristic 验证**：BBRv3 在 80 ms/10 Mbit/s、0% 与 4% 总丢包路径上，e2e 预测各 split 切分一致（0.86 / 0.58 utilization）；split 预测捕捉「高带宽配高延迟更好、lossy 段配低带宽更差」趋势，median n=40。
- **QUIC 实现碎片化**：Fig. 5 热图显示 Cloudflare/picoquic CUBIC 对 loss 退化更平缓，可能在 Class II/III 比 Linux TCP CUBIC 更受益于 split；各 BBRv3 QUIC 实现 end-to-end 行为不一致，split 趋势无单一结论。Google quiche 与 Linux TCP 同 CCA 最接近。
- **BBRv1 内核时间线**：2016–2024 共 13 个 Linux kernel 的 BBRv1 split 行为无显著差异；BBRv2/v3 仍快速演化中。
- **成本**：150 配置 cache + 搜索剪枝（utilization <5% 链路率可跳过）；开源 benchmark 在 GitHub `StanfordSNR/connection-splitting`。

## Critical Analysis

### 论证链条

论文链条清晰：提出「split ≈ min(段吞吐)」→ 用 150 点 cache 穷举 7875 组合 → 发现 BBR 版本间 split 收益反转 → 发现 BBRv3 新受益类 → 用 QUIC 实现差异解释「QUIC 不需 PEP」说法不可靠。从 mechanism（缩短反馈环路）到 BBRv3 loss sensitivity 回归，逻辑自洽。

最脆的跳步是 **从 emulation 单流结论到「PEP remain relevant for the foreseeable future」**。作者诚实列出 heuristic 与单流限制，但 Abstract/Conclusion 语气偏强；真正闭合需要 production trace（卫星/5G/跨国 backhaul）上的 A/B，以及多流公平性、故障恢复、加密流量占比变化下的净收益。论文定位为 first step，这一外推合理但证据尚未到位。

### 假设压力测试

**BBR 部署版本分裂**：大量 CDN 仍用 BBRv1 for TCP，而 Google 公网已推 BBRv3。若运营商按「BBR 已解决 satellite 问题」下架 PEP，实际伤害的是 BBRv2/v3 流量而非 BBRv1——论文对版本敏感性的强调正是为了对抗这种 over-generalization。

**QUIC 渗透持续**：QUIC 无法透明 split，若 QUIC 占比继续上升且其实现逐渐收敛到「loss 不敏感的高利用率」，则 PEP  relevant 市场会缩小到「仍走 TCP + BBRv2/v3 + lossy path」子集。论文反而用实现差异说明「现在还不能断言 QUIC 已够好」，但若未来出现标准 conformance test suite 且实现趋同，Finding 3 的警示会减弱。

**Workload 漂移**：测量全是长流 bulk HTTPS。交互式 RPC、视频点播 startup、HTTP/3 多路复用短流组合可能改变「是否需要中间 ACK 点」的答案；BBRv1 在短流上是否仍高 utilization，论文未覆盖。

**部署政治与 ossification**：即使性能获益成立，透明 PEP 仍面临端到端纯粹主义、NAT/防火墙交互、TLS 1.3/eSNI 下中间人不可行、多租户隔离与可观测性缺失。论文承认争议性，但未量化运维成本；与 [[Sidekick-NSDI24]] 的显式协助路线对比时，「老 PEP 仍有效」不等于「老 PEP 应回归」。

### 实验可信度

**强项**：(1) heuristic 有独立双段 PEP 验证，不是纯理论；(2) CCA 覆盖版本 + 实现矩阵在 CC 论文中少见；(3) 开源 artifact；(4) 对 BBR 版本叙事直接回应社区 anecdote（Frode Kileng @ IETF PANRG）。

**弱点**：(1) 仅单流，未测 split 是否牺牲共存公平性——而 BBR 争议核心本就是 fairness；(2) QUIC split 纯属外推，误差上界未知；(3) 参数空间偏小（max 50 Mbit/s、max 4% loss、无带宽波动）；(4) 未与真实卫星/蜂窝 trace 对照，Class II/III 的「可替代专有 FEC 协议」主张证据不足；(5) 与 RFC 3135 时代 PEP 测量比，缺少 field deployment 数据支撑「foreseeable future」。

Baseline 选择公平：Linux TCP CUBIC/BBR 代表主流；三套 quiche/picoquic 代表生产与标准化实验实现。未测 Windows/macOS TCP、未测 kernel 以外 TCP offload，对「Internet 性能」是合理下界而非全集。

### 系统性缺陷

- **多流与公平性**：论文未讨论。Split 连接可能更激进占满瓶颈，与未 split 流共存时的 tail latency / starvation 风险未知；BBRv3 公平性本身仍在争论中。
- **故障与语义破坏**：透明 split 改变端到端语义（MSS/option 协商、TLS 会话绑定、路径 MTU 发现），论文未评估；对现代加密 Web 流量，透明 PEP 往往根本插不进去。
- **可观测性**：运营商难以区分「该路径需要 PEP」与「CCA 实现 bug」；论文呼吁 heatmap 式 conformance test，但未提供运维 playbooks。
- **尾延迟与启动**：论文未讨论；PEP 对 last-mile 丢包的 TTFB 改善曾是卖点，只看 sustained throughput 可能错过 PEP 的另一面价值，也可能错过 QUIC 0-RTT 的优势。
- **成本**：PEP 设备、license、与 QUIC 迁移机会成本——论文未讨论。

## 局限与 Future Work

- **局限 1**：单流环境，无法陈述 inter-flow fairness 或 tenant 隔离；split 高吞吐的「不公平收益」可能抵消链路利用率增益。
- **局限 2**：仅 sustained throughput，未测 startup、jitter、重传开销、短流；对 satellite interactive 业务结论不完整。
- **局限 3**：简化三参数网络模型 + mininet emulation，未验证真实 5G mmWave 波动、GEO/LEO 切换、policer 等；7875 组合无真实路径分布加权。
- **局限 4**：QUIC split 行为未实测，heuristic 对 QUIC 的外推误差未单独量化；加密下透明 PEP 不可部署，与「relevant」之间仍有工程鸿沟。
- **局限 5**：论文未讨论透明 PEP 与 TLS/QUIC 部署现实、ossification 风险、中间盒运维成本的净社会收益。
- **Future work 1**：在真实 satellite/cellular production trace 上对比 TCP BBRv3 ± PEP vs QUIC（按 implementation/version 标注），测 bulk + 短流 + 多流公平性与 tail latency。
- **Future work 2**：建立 CCA conformance/regression test suite（论文建议的 utilization heatmap 「permissible zones」），量化「同名 BBRv3」在不同栈的可比性。
- **Future work 3**：扩展 heuristic 模型（队列长度、bottleneck 相对 PEP 位置、带宽 波动），并在自定义 QUIC explicit splitter 上验证外推误差。
- **Future work 4**：评估 protocol-agnostic in-network assistance（MASQUE proxy、QUIC tunneling、Sidekick/Sidecar 类显式协助）能否在不含 ossification 代价下达到 split PEP 的 80% 收益。

## 相关

- **相关概念**：[[BBR]]、[[CUBIC]]、[[QUIC]]、[[TCP]]、[[Congestion-Control]]、[[Performance-Enhancing-Proxy]]、[[Middlebox]]、[[End-to-End-Argument]]
- **同类系统**：PEPsal、[[Sidekick-NSDI24]]、Sidecar（HotNets 22）、Secure Middlebox-Assisted QUIC
- **同会议**：[[ATC-2025]]
- **对比**：与 [[KernelBypassTCP-ATC25]] 同属 ATC'25「基础传输认知 reset」——前者重审 kernel-bypass TCP 无 universally winning stack，本文重审「BBR/QUIC 让 PEP 过时」同样不成立
