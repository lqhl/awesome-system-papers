---
type: paper
name: FLB
full_title: "FLB: Fine-grained Load Balancing for Lossless Datacenter Networks"
authors: [Jinbin Hu, Wenxue Li, Xiangzhou Liu, Junfeng Wang, Bowen Liu, Ping Yin, Jianxin Wang, Jiawei Huang, Kai Chen]
venue: ATC
year: 2025
tags: [datacenter-network, load-balancing, rdma, pfc, congestion-control, lossless-network]
source_pdf: "[[atc2025-hu-jinbin.pdf]]"
source_md: "[[atc2025-hu-jinbin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# FLB：无损数据中心网络的细粒度负载平衡（ATC 2025）

> **原题**：FLB: Fine-grained Load Balancing for Lossless Datacenter Networks

> **一句话总结**：FLB 的关键观察是 fine-grained load balancing 在 [[PFC]] lossless DCN 中会把真正拥塞的 flow 扩散到更多 path, 反而放大 HoL blocking；它用 threshold-free rerouting 维持正常态利用率、用 congested-flow isolation 收缩拥塞影响面，在 testbed 中最多减少 96% PFC PAUSE, 在大规模模拟中让 FLB+RC 相比 LetFlow+DCQCN / MP-RDMA / Proteus+DCQCN 分别降低 70% / 36% / 29% AFCT。

## 问题与动机

[[RDMA]] over Converged Ethernet 依赖 [[PFC]] 提供 lossless 语义，但 PFC 的 PAUSE/RESUME 是逐跳 back-pressure: 一旦某个下游 ingress queue 被暂停，PAUSE 可以沿 path 向上游传播，把无辜 flow 一起堵住。与此同时，datacenter fabric 又天然有多条等价 path, 单 path 的 [[ECMP]] hash 碰撞会浪费带宽，所以 [[RoCE]] 部署仍然需要 load balancing。

论文指出一个反直觉点：很多为 lossy DCN 设计的细粒度 LB 在 lossless DCN 中不是“更细就更好”。Flowlet 方案如 [[CONGA]] / [[LetFlow]] 依赖 packet gap 避免乱序，但 RDMA hardware pacing 和 rate shaper 会让固定 flowlet timeout 下 gap 很少出现，导致 rerouting 不够灵活。更激进的 packet-level 或 multipath transport 又会把同一个 congested flow 分散到多个 path; 一旦它触发 PFC, 更多 upstream port 被 PAUSE, 更多 non-congested flow 变成 victim。

FLB 因此不是单纯做更好的 congestion-aware routing, 而是把问题拆成两个状态：正常态要足够灵活地换路以提高利用率；拥塞态要反过来收缩拥塞 flow 的 path footprint, 防止 PFC 的 HoL blocking 被 multipath 机制放大。

## 关键观察 / 隐含假设

- **观察 1**：Lossless RDMA 环境里 flowlet gap 不可靠。论文在 20-server testbed 上复现 ECMP, LetFlow, ECMP+DCQCN, LetFlow+DCQCN 和 MP-RDMA, 发现拥塞出现后 uncongested flow 不能及时从 congested path 切到 idle path; 原因是 RDMA bypass OS, 加上 rate shaper 平滑发送，固定 50us flowlet timeout 下很少形成可安全切换的 gap。
  - **依赖假设**：目标环境有硬件 RDMA、较稳定的 pacing/rate shaping, 且运营者不愿为更激进 rerouting 承担乱序代价。
  - **可能失效场景**：如果 transport 本身能快速 reorder, 或应用/网卡已接受 per-packet reordering, flowlet gap 稀缺就不再是同等强的约束。
- **观察 2**：Fine-grained spreading 会扩大 [[PFC]] 的影响面。论文在 31-to-1 incast NS3 设置中看到，ECMP 让约 70 条 path 被 PAUSE, packet spraying 让约 340 条 path 都被 PAUSE; 小规模 testbed 里，让 congested flow `f2` 跨三个 path 后，所有 path 上的 `f0` / `f1` 都被 HoL blocking 拖累。
  - **依赖假设**：PFC 仍是 production lossless fabric 的主机制，且拥塞通常集中在 receiver-facing egress 或 many-to-one burst。
  - **可能失效场景**：无 PFC 的 lossy RDMA fabric、端到端 selective retransmission 成熟的部署、或以多级网络中间 bottleneck 为主的 workload, 会削弱“把 culprit flow 收缩到少数 path”这一策略的收益。
- **观察 3**：End-host congestion control 不能完全挡住微突发。作者强调 bursty short flows 持续时间可能小于 1 RTT, DCQCN 这类迭代式 rate control 来不及在 PFC 触发前收敛；burst 结束后，慢速 rate increase 还会继续损害 link utilization 和 tail latency。
  - **依赖假设**：微突发和 incast 是主导风险，且 switch-local 反应比 end-host loop 更及时。
  - **证据强度**：中到强。论文给了 bursty testbed 和大规模模拟，但真实 production trace 只以公开 workload 分布近似，没有展示来自生产集群的 PFC 事件 trace。
- **假设 1**：Source edge switch 能准确、及时地识别 congested flow 并维护 per-flow state。FLB 的 CNM 携带 flow ID 和 congested-flow count `n`, source edge switch 据此写 isolation table。
  - **证据强度**：中。P4 prototype 证明资源占用可控，但论文没有充分展开 hash collision、CNM loss/reordering、route churn、多租户隔离和长期 stale state 对正确性的影响。
- **假设 2**：Isolation threshold 可以被配置到“早于 PFC、又不饿死链路”的区间。附录用 `Q_PFC`, path delay `d`, line rate `C`, congested flow count `n` 推导阈值范围。
  - **证据强度**：中。论文用固定阈值对比证明 optimized threshold 有收益，但推导假设 uniform link capacity 和可估计的 worst-case inflight bytes; 生产里的 dynamic buffer, 多 priority class 和 headroom 配置会让这个范围更难稳定。

## 核心方法

FLB 部署在 source edge switch, 包含 rerouting module 和 isolation module。正常态下，它仍然像细粒度 LB 一样利用多 path; 拥塞态下，它把被 CNM 标记的 congested flow consolidate 到少数 isolation path, 其余 uncongested flow 只走 normal path。这个状态切换是论文的核心抽象：不要让“高利用率需要 spreading”这个原则在 PFC 触发后继续成立。

**Threshold-free rerouting** 回应观察 1。对新 flow, FLB 选择未被 isolation 占用的最低 delay path。对已有 flow, 它比较当前 packet 和上一个 packet 的到达间隔 `Delta t` 与候选 path 的 one-way delay 差值；只有当更快 path 的 delay advantage 小于 `Delta t` 时才切换，避免后发 packet 先到造成乱序。它不是等待固定 flowlet timeout, 而是把“是否能安全换路”变成每个 packet 的动态条件。Path delay 通过 edge switch 周期采样 one-way delay 并减去历史 base delay 来消除时钟不同步影响。

**Congested flow isolation** 回应观察 2。Downstream switch 的 egress queue 超过 isolation threshold 后生成 CNM, 回传 flow ID 和 congested-flow count `n`。Source edge switch 把这些 flow 记录进 isolation table, 并按照总收敛速率与单链路带宽估计 isolation path 数量。直觉上，如果每个 congested flow 最终应该被压到 `C/n`, 那么所有 congested flow 只需要足够承载这部分总速率的少数 path; 这样 PFC 最多影响 isolation path, 不会把 normal path 上的 innocent flow 一起暂停。

**Minimal rate control** 回应观察 3。FLB 可以配合既有 [[DCQCN]] / [[Swift]] / [[PCN]], 但作者额外提出 FLB+RC: sender 初始按 line rate 发送一个 BDP 数据，收到 congestion CNM 后暂停该 flow, 并把后续 rate 直接设为 `C/n`; 收到 non-congestion CNM 后恢复。它避免了迭代式 convergence, 但把公平性和正确性更强地绑定到 CNM 中 `n` 的准确性。

实现上，FLB 基于 Wedge 100BF-32X P4 switch。因为该 P4 target 的 ingress pipeline 不能直接读 egress queue length, 作者用 SRAM 计数 enqueue/dequeue 来近似 queue size。每个 flow entry 存 16-bit flow ID, 8-bit selected path ID, 8-bit aging metric 和 48-bit MAC; 100K concurrent flows 下 SRAM 约 0.1MB, 三层 Fat-tree 中 path ID 增长后约 0.12MB。资源占用整体低于 10%, 但 Gateway 9.56% 和 ALUInstruction 8.2% 已经接近该设计声称的主要硬件成本。

## 设计取舍

- **正常态灵活性 vs 拥塞态隔离**：FLB 保留 per-packet rerouting 的利用率优势，但一旦 flow 被判定为 congested, 就主动牺牲该 flow 的 path diversity, 换取其他 flow 不被 PFC PAUSE 连坐。
- **避免乱序 vs 反应速度**：基于 delay gap 的切换条件比固定 flowlet timeout 更灵活，但高发送速率下 `Delta t` 很小，真正大幅换路常常仍依赖 PAUSE 或 rate reduction 先制造 packet gap。
- **Switch-local 控制 vs 端到端简单性**：FLB+RC 让 end-host rate control 变简单，却把复杂度前移到 programmable switch: queue-size tracking, per-flow state, CNM construction, hop-by-hop source MAC lookup 和 explicit source routing。
- **阈值提前触发 vs 吞吐损失**：isolation threshold 太高会来不及阻止 PFC, 太低会过早暂停 culprit flow。论文给出推导和 deep dive, 但 production 中这个参数可能需要随 buffer/headroom/workload 动态调优。
- **Edge-only 部署 vs 路由可控性**：作者主张只在 edge switch 部署即可。Leaf-spine 中这很自然；多层 Fat-tree 则需要 edge 维护 end-to-end path ID 并使用类似 XPath 的 explicit source routing, 这提高了部署依赖。

## 实验与结果

- **Problem demonstration**：31-to-1 incast 模拟中，ECMP 约 70 条 path 被 PAUSE, packet spraying 约 340 条 path 被 PAUSE, 支撑“multipath spreading 放大 PFC 影响面”的核心观察。
- **Testbed Web Search workload**：20 台 Dell server, Mellanox ConnectX-5 100GbE NIC, P4 switch, 默认 40Gbps link, bottleneck load 0.6。相比 ECMP+DCQCN / LetFlow+DCQCN / MP-RDMA, FLB 分别降低 48% / 42% / 30% AFCT; 99th percentile FCT 最高改善 88%。
- **Bursty-flow testbed**：link capacity 从 10Gbps 到 100Gbps 变化时，FLB 最多减少 96% PFC PAUSE; link utilization 相比 ECMP / LetFlow / ECMP+DCQCN / LetFlow+DCQCN / MP-RDMA 最多提高 95% / 78% / 166% / 144% / 28%。
- **Deep dive**：bursty flow arrival interval 低至 5us 时，FLB 仍能保护 `f0` / `f1`; 相比 MP-RDMA, `f0` / `f1` throughput 提高 24% / 20%, path throughput 最高提高 19%。Optimized isolation threshold 相比 20% / 30% fixed threshold, PAUSE rate 降低 82% / 89%, link utilization 最高提高 40%。FLB+RC 比纯 FLB 再降低 15% AFCT。
- **Large-scale NS3 realistic workloads**：10 leaf x 10 spine, 每 leaf 30 hosts, 3:1 over-subscription, 40Gbps links, 9MB switch buffer; load 0.5 到 0.8。Data Mining 在 0.8 load 下，FLB+RC 相比 ECMP / LetFlow / ECMP+DCQCN / LetFlow+DCQCN / MP-RDMA / Proteus+DCQCN / LetFlow+PCN 分别降低 65% / 58% / 76% / 70% / 36% / 29% / 18% AFCT。
- **Incast and multi-tier**：25 到 200 servers incast 下，FLB+RC goodput 最高比其他方案高 27%。12-pod Fat-tree 中，Web Server workload 下相比 LetFlow+DCQCN / LetFlow+Swift / MP-RDMA / LetFlow+PCN, FLB+RC 分别压低 71% / 55% / 45% / 37% PAUSE rate, 降低 76% / 40% / 32% / 28% AFCT; Hadoop Cluster 下平均和 99th FCT 最多降低 92% / 83%。
- **Hardware cost**：100K concurrent flows 下，FLB 的 Match Crossbar 5.82%, SRAM 4.12%, Gateway 9.56%, ALUInstruction 8.2%; 比 ECMP 和 LetFlow 高，但仍在单个 P4 target 可接受范围内。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Fixed timeout is inflexible in paced RDMA | 50 us timeout leaves f1 on congested P2（§2.1） | 20 server/two-P4/3×40Gbps constructed burst，3 path | high |
| Spreading culprit flow expands PFC scope | 31-flow experiment：ECMP pauses about 70 path、packet spraying about 340（§2.2，Fig. 4b） | packet-spraying example，非每种 multipath | high |
| FLB improves Web Search FCT on testbed | AFCT lower 48/42/30%，p99 gain up to 88% vs three baseline（§4.1，Fig. 8） | 20 Dell/ConnectX-5、40Gbps、load .6 | high |
| Isolation lowers PAUSE/utilization loss | PFC PAUSE up to 96% lower；util +95/+78/+166/+144/+28%（§4.1，Fig. 9） | author-controlled burst、10–100Gbps bottleneck | high |
| FLB+RC scales in NS3 workload | Data Mining load .8 AFCT −65/−58/−76/−70/−36/−29/−18%（§4.3，Fig. 15） | NS3 10 leaf/10 spine/30 host、40Gbps/3:1 oversubscription | high |

## 批判性分析

### 论证链条

论文的 strongest part 是 problem framing: 它不是说既有 LB 不够聪明，而是指出 lossless fabric 中 LB 与 [[PFC]] 的反馈方向可能相反。作者先证明 flowlet 方案不够灵活，再证明 packet/multipath spreading 会扩大 PFC PAUSE scope, 最后把设计自然导向“正常态分散、拥塞态收缩”。这个 observation -> design 的链条比较闭合。

较弱的跳步在于“congested flow”识别。实验中的 culprit flow 比较清晰，多为 many-to-one receiver egress 拥塞；真实 workload 中，如果拥塞来自多个热点、上游 oversubscription、共享 buffer 抢占或多 priority class 交互，CNM 里携带的 flow ID 未必等价于真正 root cause。论文证明了 mechanism 在目标场景有效，但没有充分证明它能在更混杂的 production pathologies 中稳定归因。

### 假设压力测试

如果 PFC 部署继续是主流，FLB 的问题定义很扎实；但如果 lossy RDMA 或无 PFC fabric 成熟，FLB 的价值会从“必要的安全机制”退化成“特定 legacy fabric 优化”。作者也承认有无 PFC 的研究线，但认为当前 production 仍以 lossless fabric 为主。

另一个压力点是 path delay measurement。FLB 通过 base delay 消除时钟不同步，并在 symmetric/asymmetric topology 下测了 out-of-order degree; 但 path delay 本身是 sampled and piggybacked, 在快速拥塞变化或 route churn 中可能滞后。若 delay stale, rerouting module 可能既不能及时避开 bad path, 也可能过度保守。

Isolation path 数量的 `C/n` 逻辑简洁，但隐含 bottleneck 是一个 uniform-capacity egress link, 且所有 congested flows 的 fair share 一样。多瓶颈、多租户权重、非均质链路、priority group 共享 buffer 时，这个计算可能不再代表正确隔离规模。

### 实验可信度

实验覆盖面不错：small testbed 用真实 P4 switch 和 ConnectX-5 NIC, large-scale 用 NS3 覆盖 realistic workload, incast 和 Fat-tree。作者没有只报吞吐，也覆盖 PFC PAUSE, link utilization, average/99th FCT, out-of-order degree, threshold sensitivity 和 hardware resource。

主要限制是 testbed 规模仍小，只有 20 servers 和 3 parallel paths; 大规模结论来自模拟。Workload 使用 Web Search, Cache Follower, Hadoop, Data Mining 这类经典分布，而不是生产 PFC trace。对照基线包括 ECMP, LetFlow, MP-RDMA, Proteus, PCN, Swift/DCQCN 组合，但没有深入比较同样强调 in-network reordering/support 的 [[ConWeave]] 或更现代的 production RDMA LB 系统。

### 系统性缺陷

FLB 引入 per-flow switch state 和 CNM 控制面依赖。论文说 inactive entry 通过 timeout 清理，CNM loss 时也依赖 timeout 释放，但没有评估 timeout 选择对 tail latency、误隔离时长和 state pressure 的影响。16-bit flow ID 由 CRC16 hash 生成，在 100K concurrent flows 下理论上存在 collision 风险；论文没有说明 collision handling。

可观测性和运维复杂度也没有展开。Production operator 需要知道哪些 flow 被隔离、为什么隔离、isolation path 是否成为新热点、CNM 是否丢失或延迟、threshold 是否过低造成吞吐损失。论文证明了 dataplane 可实现，但没有给出调试或安全降级机制。

最后，FLB+RC 的 line-rate start + CNM 后 `C/n` rate setting 很像把拥塞控制简化为 switch-signaled fair share。它在本文 workload 上有效，但如果 `n` 不稳定、短流极多、RTT 差异大或 host/NIC 对 pause/resume 响应不一致，公平性和 oscillation 风险需要额外验证。

## 局限与后续工作

- **局限 1**：FLB 的核心收益绑定在 PFC-enabled lossless DCN; 对无 PFC 或具备强 reordering 支持的 fabric, 设计动机会明显变弱。
- **局限 2**：真实部署需要 programmable edge switch, per-flow table, queue-size SRAM approximation, CNM propagation 和可能的 explicit source routing; 论文未评估 mixed vendor switch、route churn 或故障恢复。
- **局限 3**：Congested-flow attribution 在实验中相对干净。多热点、多优先级、多租户和共享 buffer 复杂交互下，CNM flow ID 是否能稳定指向 root cause 仍未证明。
- **局限 4**：实验缺少 production PFC trace, 长时间运行下的 state churn, hash collision, CNM loss 和 observability 评估。
- **Future work 1**：用真实生产 PFC/ECN/CNM trace replay FLB, 量化误隔离率、隔离持续时间、state churn 和 tail latency, 而不只看 aggregate FCT。
- **Future work 2**：设计并评估 multi-bottleneck / weighted-tenant 版本的 isolation path sizing, 替代单一 `C/n` fair-share 假设。
- **Future work 3**：给 FLB 增加 operator-facing telemetry: per-flow isolation reason, path occupancy, threshold margin, CNM loss/retry, stale entry age, 并测试这些信号能否定位 PFC storm。
- **Future work 4**：在支持 in-network reordering 或 lossy RDMA 的 fabric 上重测 FLB, 判断“拥塞态收缩 path footprint”是否仍然是正确抽象。

## 相关

- **相关概念**：[[RDMA]]、[[RoCE]]、[[PFC]]、[[Priority Flow Control]]、[[HoL Blocking]]、[[Datacenter Load Balancing]]、[[Congestion-Control]]、[[Flowlet]]、[[Incast]]
- **同类系统**：[[ECMP]]、[[CONGA]]、[[LetFlow]]、[[MP-RDMA]]、[[Proteus]]、[[DCQCN]]、[[Swift]]、[[PCN]]、[[HPCC]]、[[ConWeave]]、[[BFC]]
- **同会议**：[[ATC-2025]]
