---
type: paper
name: FiDe
full_title: "FiDe: Reliable and Fast Crash Failure Detection to Boost Datacenter Coordination"
authors: [Davide Rovelli, Pavel Chuprikov, Philipp Berdesinski, Ali Pahlevan, Patrick Jahnke, Patrick Eugster]
venue: ATC
year: 2025
tags: [failure-detection, distributed-systems, consensus, datacenter, sdn]
source_pdf: "[[atc2025-rovelli.pdf]]"
source_md: "[[atc2025-rovelli]]"
---

# FiDe: Reliable and Fast Crash Failure Detection to Boost Datacenter Coordination (ATC 2025)

> **一句话总结**：FiDe 的核心判断是 crash failure detector 的瓶颈不在 heartbeat 算法而在不可靠的 OS/网络 substrate；它用 system-driven 的 FiDe domain（CPU 隔离 + LKM/XDP + SDN 双冗余 multicast TE）把 crash detection 压到平均 4.58µs、最坏 26.54µs（比 uKharon-FD 快 7.2×），并据此设计 N-1 容错的 HSUC/HUC consensus，使 Redis/Zookeeper 无故障时吞吐最高 +2.23×、延迟最低 0.46×。

## 问题与动机

[[Failure-Detector]] 是 [[Consensus]]、[[Replication]]、[[Zookeeper]]、[[Redis]] 等 coordination service 的 liveness 基础，但 datacenter 里的 crash FD 长期困在 timeout 两难：设太短会假阳性（false suspicion），设太长又会拖慢 µs-scale 服务的故障恢复。更糟的是，多数 quorum-based 协议在 timely failure removal 失败时会因 correct replica 数跌破 quorum 而整体 stall。

论文区分了两类 FD 路线。多层级 / gray FD（Falcon、uKharon、Panorama）通过 internal observation 在应用/OS/网络多层布探针，覆盖 partial failure、deadlock 等 subtle failure，但要"监视监视者"、常需数百行 application-specific 代码，探针自身也会引入 jitter，往往靠主动 kill 来兜底假阳性。另一类是 RDMA / kernel-bypass 路线（uKharon-FD、X-Lane、DARE），追求低延迟交互，但论文测量显示 RDMA 在 70 亿 packet 后 latency 会突刺到 243µs，说明仅靠 fast path 不足以保证 **stable** end-to-end interaction。

FiDe 的 claim 边界很明确：只针对 **crash-stop process failure**，不直接覆盖 gray failure、fail-slow、Byzantine；目标服务是 replication cluster 通常 3–9 节点、对可用性要求高的 core coordination service（[[Redis]]、[[Zookeeper]]、etcd 类），而不是大规模 blockchain。价值主张是：把 FD 从"挂在不可靠系统上的 module"变成"为 detection 定制的 system component"，从而把 FiDe 当作 practical approximation of perfect failure detector P，在无故障路径上也能简化并加速 consensus。

## 关键观察 / 隐含假设

- **观察 1：crash FD 的 reliability/timeliness 上限由 end-to-end interaction 的 jitter 决定，而不是 heartbeat 逻辑本身。** 论文用 2.3 万亿 packet、数周 stress-ng/iPerf 并发负载测试显示，FiDe 的 peer-to-peer latency 上界 < 45µs 且稳定，而 Falcon 会随 CPU load 剧烈跳动、RDMA 虽平均接近 50µs 但会出现周期性突刺。
  - **依赖假设**：通过 CPU core 隔离（isolcpus + IRQ shielding + C0 + hugepage）、LKM active pacemaker 发心跳、接收端 XDP + 专用 NIC queue，可以把 processing jitter 压到相对 latency 可忽略；XDP + core isolation 贡献了 > 90% jitter 降幅。
  - **可能失效场景**：未预留专用 core / 优先级队列、内核升级改变 XDP/eBPF 行为、NIC driver 不支持稳定 XDP、或 host 侧存在不可屏蔽的 hardware interrupt 时，timeout 下界会回升，strong accuracy 难维持。

- **观察 2：datacenter 网络 jitter 可通过 SDN 流量工程 + 双冗余 vertex-disjoint multicast tree 做到可预测。** FiDe controller 为每个 sender 分配两棵内部节点不相交的有向 multicast tree，结合最高优先级队列和端到端 rate-limit，给定 (σ_max, π_min) 后保证 λ_min 与 δ_max 上界；单棵树故障时 controller 切换备用树。
  - **依赖假设**：部署环境有 SDN-capable switch（论文用 Arista 7280CR）、controller 能动态改路由/队列；FiDe traffic 可占用最高优先级队列和约 50 Mbit/s/host 带宽；fat-tree 拓扑足够规则以构造 vertex-disjoint tree。
  - **可能失效场景**：非 SDN 网络、priority queue 被其他 control traffic 挤占、controller 故障或 rule update 延迟高、多 switch 深拓扑（tree height=3）会把 A_avg 从 6.34µs 拉到 20.89µs 且 critical compound failure 频率升到约 1/6 年。

- **观察 3：external observation（单点 OS watchdog + 稳定 heartbeat）比 internal multi-level probes 更适合 crash failure 的 non-intrusive 检测。** LKM 在 `do_exit` kprobe pre-handler 上可在进程"官宣退出"前触发 active detection；passive detection 则靠 heartbeat 单调递增序列在 eBPF map 中被 poll。
  - **依赖假设**：FiDe process 与 monitored application 同 host；FiDe LKM 不会遭遇 partial OS failure；crash 即 process table 消失这一 OS 语义足够。
  - **可能失效场景**：application hang/deadlock 但进程未 exit（需 gray FD 补位）；FiDe process 自身 bug 被论文假设为可形式化验证消除；应用与 FiDe 走不同网络路径时可能出现 false negative，需 piggyback 把应用消息捎到同一路径。

- **观察 4：若 FiDe 近似 P，consensus 可在无故障时走更简单、N-1 crash 容错的算法路径。** HSUC/HUC 容忍 N-1 crash（vs [[Raft]]/Zab 的 minority），HUC 利用 heartbeat piggyback 把 leader decision 直接广播，failure-free 时只需 2 个 message delay。
  - **依赖假设**：FiDe 的 strong accuracy 在实践中成立；集群规模小（实验最多 9 Redis / 7 Zookeeper 节点）；HSUC/HUC 不接受 slow process，所有 non-crashed 进程必须参与。
  - **可能失效场景**：slow follower 会让 HSUC/HUC stall 直到 FiDe 报 crash 或接入 gray FD；piggyback 大小（最大 1418B）和 heartbeat 周期（benchmark 用 100µs）构成吞吐上界（约 32 Mbit/s）；大规模集群下 hierarchical leader 与 multicast fan-out 成本未评估。

## 核心方法

FiDe 把系统切成 **best-effort domain**（普通应用进程）和 **FiDe domain**（特权 detection substrate）。应用无需注入探针，只通过 Listing 1 的 lean C API 做 monitor/join/piggyback；detection 逻辑完全在 dedicated FiDe process + LKM + SDN controller 中。

**Reactive uninterrupted processing** 是 FiDe domain 的核心。FiDe process 绑定独立 CPU core，屏蔽 IRQ、保持 C0、使用 hugepage；LKM 用 active pacemaker loop 直接构造 SKB 发心跳，绕过常规网络栈抖动；接收侧为 FiDe traffic 保留专用 NIC queue，收包 IRQ 打到 FiDe core，再用 [[XDP]] eBPF hook 尽早交付。论文把这称作 system-driven 而非 system-tailored：不是给现有栈打补丁，而是为 detection 重建稳定 pipeline。

**Fast-track redundant networking** 由 FiDe controller 驱动。每个 monitoring 关系对应一组 TE 参数化的 directed multicast tree；timeout 按 `TO(i,j) = HB_i + λ_min + 2·δ_max` 计算，使 heartbeat 在超时前必达。两棵 vertex-disjoint tree 加 recovery 机制把网络 failure 下的 false positive 概率压到极低；若双树在 recovery window 内同时失效（critical compound failure），FiDe 可配置为 graceful shutdown 以保护 reliability guarantee。

**Failure detection workflow** 分 passive 与 active。整 host crash 时 heartbeat 停止，远端 FiDe 在 eBPF map 看到重复 heartbeat 值即报 failure；单 application crash 时 LKM watchdog 立即发 active notification，远端 XDP hook 触发 `on_failure` upcall。论文强调这是 external observation：一个 timely observer 盯 OS 级 process liveness，而不是在应用内部布网。

**FiDe-based coordination primitives** 把 FiDe 当 P 的实践近似，提出三条算法并用 TLA+/TLC 验证：
- **OSRB**（Optimistic Stabilizing Reliable Broadcast）：lazy relay + `STABILIZE` 限制 retransmit buffer，避免无限缓冲。
- **HSUC**（Hierarchical Stabilizing Uniform Consensus）：leader 多播 proposal、收集 ACK、OSRB 广播 decision；failure-free 3 message delays，容忍 N-1 crash。
- **HUC**（Heartbeat Uniform Consensus）：利用 FCURB（fail-consistent uniform RB）把 decision piggyback 到 heartbeat，省掉显式 ACK 轮；failure-free 2 message delays，同样 N-1 crash。Alg. 1 的核心是 FCURB 的 fail-consistency：failure notification 之前所有 correct 进程必已 deliver piggyback 消息。

实现上 FiDe 本体 4032 LoC C（LKM + XDP + userspace API），HSUC/HUC 分别 910/810 LoC Redis module；Zookeeper 实验通过改配置参数模拟算法复杂度，未改内部代码。

## 设计取舍

- **专用系统资源换 µs-scale reliability**：每 host 预留 1 个满负载 CPU core（实验机 1/56≈1.79%）和最高优先级网络队列 + ~50 Mbit/s 带宽。收益是 timeout 可低至 45–48µs；代价是多 tenant 混部、core 较少的边缘节点上部署成本更明显。
- **external observation 换 coverage**：不检测 deadlock、fail-slow、partial failure，应用几乎零侵入（Redis 集成仅 6 行 API）。收益是 crash path 极简且 jitter 低；代价是必须与 Panorama/Falcon 等 gray FD 组合才能覆盖完整 failure spectrum。
- **synchrony assumption 换 algorithmic simplicity**：FiDe 在 controlled slice 内 enforce bounded jitter，使 P-based HSUC/HUC 在实践可行。收益是 N-1 容错 + 更短 message path；代价是 critical compound failure、kernel 异常或极端负载仍可能破坏假设，且 HSUC/HUC 对 slow process 不如 [[Raft]]/Zab 宽容。
- **SDN 中心化 TE 换可预测网络**：controller 预注册后分配 tree/queue/rate-limit，避免 congestion 后再反应。收益是 δ_max 可纳入 timeout 公式；代价是 controller 成为 control plane 依赖，switch rule update 延迟与 scale 未充分展开。
- **piggyback 换 consensus 轮次**：HUC 把 decision 塞进 heartbeat，吞吐受 σ≈400B 和 HB=100µs 约束。收益是 failure-free 延迟最低；代价是消息大小和 multicast 周期直接 cap 吞吐，不适合大 payload replication。

## 实验与结果

- **测试环境**：SAP 生产 datacenter 6 台服务器（Intel Xeon E5-2680 v4、1TB RAM、Mellanox ConnectX-4 / Intel XL710 10GbE、双路径 mini fat-tree、Arista 7280CR）；对比 Falcon、X-Lane、uKharon-FD（RDMA on RoCE）、RedisRaft、原生 Redis/Zookeeper。
- **Interaction stability（RQ1）**：2.3T packets 跨数周；FiDe p2p latency 上界 < 45µs，比 X-Lane/RDMA/Falcon 稳定 ≥ 5.4×；RDMA 平均 ~50µs 但最大 243µs，Falcon 随 CPU load 大幅跳动。
- **Crash detection（RQ2）**：应用 crash 平均检测 4.58µs、最大 26.54µs；uKharon-FD 为 17.39 / 193.56µs，X-Lane 为 354.75 / 718.54µs，Falcon 为 496.29 / 169000µs。FiDe 在 timeout=48µs 时零假阳，uKharon-FD/X-Lane 需 ~800µs。
- **Redis/Zookeeper integration（RQ3/RQ4）**：50 并发客户端、100 万 SET；scale 到 9 Redis / 7 Zookeeper 节点。HUC 吞吐 vs RedisRaft 平均 1.22×、最高 1.7×，延迟最低 0.46×；vs Zookeeper 平均 1.71×、最高 2.23×，延迟最低 0.57×。HSUC 随节点数增加呈典型下降；HUC benchmark 未用 traffic prioritization，主要吃 accuracy 而非 latency enhancement。
- **Network fault / deployment（RQ5）**：理想单 switch 部署 critical compound failure 约 1/22.7 年；tree height 3 时 A_avg 升至 20.89µs、freq_CCF 约 1/6 年。FiDe 可靠性估计比 Ethernet+TCP 报文损坏概率高 3 个数量级以上。
- **Overhead**：kprobe watchdog 开销 ns 级；网络带宽 host 侧约 50 Mbit/s，网内最多 k×50 Mbit/s（k 为 FiDe process 数）。与 Panorama 组合可把 crash detection 平均加速约 400×。

## Critical Analysis

### 论证链条

论文主链条清晰：现有 crash FD 受 jitter 限制 → timeout 不可靠 → coordination service 只能走保守 quorum 路径 → 通过 system-driven substrate 把 interaction 变得稳定可界 → 低 timeout 下仍保持 strong accuracy → 可把 FiDe 当 P 的近似来简化 consensus → Redis/Zookeeper 无故障性能提升。

最可能的跳步在 **"FiDe ≈ P" 到生产可用** 之间。作者用 2.3T packet 稳定性、crash injection 分布和 critical compound failure 概率论证 reliability，但这仍是特定硬件/拓扑/负载下的 empirical bound，不是异步模型里的理论 P。把 1/22.7 年的 CCF 估计外推成"多年 uptime 内可忽略"对 maintenance window、control plane 变更、固件升级期间的行为需要额外假设。

第二条跳步是 **无故障 consensus 增益能否抵消部署成本**。HUC 的 2.23× Zookeeper 吞吐是在改配置模拟、未动 Zab 内部实现的前提下得到；真实 Zookeeper 还有 session、watch、磁盘 log 等路径，论文只评 SET latency/throughput。Redis 原生 baseline 不提供一致性，因此"几乎总优于 native Redis"并不 surprising。

### 假设压力测试

**Slow process 是最明显的脆弱点。** HSUC/HUC 明确不区分 slowdown 与 crash，一个慢 follower 会阻塞 consensus 直到 FiDe 报 crash；论文建议接 gray FD，但这会重新引入 internal observation 复杂度和 kill 语义，部分抵消 FiDe 的简洁性。Raft/Zab 虽也不主动驱逐 slow replica，但至少能在 majority 存活时继续服务。

**资源专属性限制了"普通 cloud 混部"场景。** 每 host 1 core + 最高优先级队列 + SDN 配置在 over-provisioned critical service 集群可行（论文也指出 etcd/ZK 部署指南本就鼓励隔离），但在高密度虚拟化、smartNIC 队列共享、无 SDN 的 legacy fabric 上，FiDe domain 的假设可能不成立，需要回退到更大 timeout 或丧失 accuracy。

**规模假设绑定小集群。** 3–9 节点实验与 Zookeeper 官方建议一致，但 hierarchical leader（HSUC）和 per-sender multicast tree 的 controller 复杂度随 N 增长；论文未探索 blockchain 级 N。piggyback 吞吐上界 (~32 Mbit/s) 对 metadata-only coordination 足够，对大块 state replication 可能不够。

**网络/applicaton 路径一致性依赖 piggyback。** 若应用数据面与 FiDe 控制面分离，可能出现"FD 仍活着但应用 partition"的 false negative；piggyback 缓解此问题，但把应用消息大小绑定到 TE 分配的 pbsize，超过 1418B 会被拒绝。

### 实验可信度

对 **crash FD 本体**，baseline 选取合理：uKharon-FD 代表最快已知 RDMA FD，X-Lane 代表端到端稳定交互，Falcon 代表 multi-level 路线。2.3T packet 稳定性测试规模远超 prior work（10× X-Lane 数据量，1000× 典型性能论文），说服力强。crash detection 分布（Fig. 5）显示 FiDe 在 99.999th percentile 仍窄，支撑"timely + reliable" claim。

对 **系统增益**，RedisRaft/Zookeeper 对比更能说明 FiDe 作为 building block 的价值，但：
- benchmark 是 failure-free、单 leader 灌流，未测 failure recovery、leader failover、并发 client 下的 tail latency。
- Zookeeper 变体是"配置级模拟"而非生产 Zab 替换，外部效度有限。
- 未与 Mu、Hovercraft、DARE 等 µs-scale SMR 直接比，尽管 related work 讨论很多。

metric 覆盖了 latency、吞吐、假阳率、scale-out detection time、CCF 概率和 integration LOC，但缺少故障注入下 consensus liveness recovery time、TE controller failover、kernel upgrade、以及多 FiDe cluster 共存时的 queue 争用。

### 系统性缺陷

**运维与升级路径论文讨论较浅。** FiDe 把 kernel 升级视为 failure，要求 infrequent update；但 production 中 rolling upgrade、eBPF/XDP 程序热替换、SDN rule 批量变更对 timeout 稳定性的影响未实测。

**Controller 单点与一致性论文未展开。** TE allocation、tree recovery 都依赖 FiDe controller；其 HA、状态持久化、与 switch 配置延迟相关的 recovery window 只在附录概率模型中间接出现。

**可观测性不足。** 对 tail latency spike、TE reallocation、piggyback reject、CCF graceful shutdown 的 operator-facing 信号论文未描述。

**兼容性绑定 Linux 5.9+、Mellanox mlx4 XDP、特定 SDN 能力**，移植到其他 NIC/OS 需重做 stability tuning；论文也承认各优化项的分解贡献留作 future work。

## 局限与 Future Work

- **局限 1：只覆盖 crash-stop，不处理 gray/fail-slow/Byzantine。** 可验证后续：与 Panorama 组合时的 end-to-end tail latency、误杀率、以及 piggyback 传播 gray observation 能否保持 2 个数量级以上加速。
- **局限 2：HSUC/HUC 对 slow process 不友好。** 可测量不同 slowdown 强度下 consensus stall 时长，并评估"FiDe + gray FD kill"与原生 Raft 在相同 SLO 下的可用性/吞吐折中。
- **局限 3：实验绑定小集群、SAP 生产硬件与 SDN 环境。** 需要在无 SDN、GPU/RDMA 混部、更大 N（>9）和 geo-distributed 拓扑上复测 detection time 与 CCF 频率。
- **局限 4：能耗与 core 占用默认较高。** 论文提出提高 heartbeat interval、与 Caladan/Shenango 类 interference-aware scheduler 结合、共享 priority queue 等方向；应量化 100µs→ms 级 HB 对 detection time 与 consensus 吞吐的 tradeoff。
- **局限 5：TE/controller 正确性与运维未充分验证。** Future work 可形式化 controller 状态机、测 switch rule update 延迟对 recovery 的影响，并做 chaos test（双树失效、controller partition、XDP 程序崩溃）。

## 相关

- **相关概念**：[[Failure-Detector]]、[[Consensus]]、[[XDP]]、[[SDN]]、[[Heartbeat]]、[[Traffic-Engineering]]、[[RDMA]]、[[Raft]]、[[State-Machine-Replication]]
- **同类系统**：Falcon、uKharon、X-Lane、Panorama、RedisRaft、Zab
- **同会议**：[[ATC-2025]]
- **对比**：FiDe 把 crash FD 做成 system component 并据此简化 consensus；Falcon/uKharon 走 multi-level internal observation 换更广 coverage；X-Lane 只做稳定交互不专精 crash detection