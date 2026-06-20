---
type: paper
name: TGW
full_title: "TGW: Operating an Efficient and Resilient Cloud Gateway at Scale"
authors: [Yifan Yang, Lin He, Jiasheng Zhou, Xiaoyi Shi, Yichi Xu, et al.]
venue: ATC
year: 2025
tags: [cloud-gateway, dpdk, load-balancing, networking, production-system]
source_pdf: "[[atc2025-yang-yifan.pdf]]"
source_md: "[[atc2025-yang-yifan]]"
---

# TGW: Operating an Efficient and Resilient Cloud Gateway at Scale (ATC 2025)

> **一句话总结**：针对在线游戏/直播对 µs 级延迟与零重连的苛刻要求，腾讯云用 DPDK 软件集群而非可编程 ASIC 构建解耦的 TGW-EIP/TGW-CLB 网关，配合 VIP 粒度 live migration 与 taint telemetry，在 testbed 上单节点吞吐达 Tripod 的 2.9×、8M 连接 4s 零丢包迁移，生产环境承载 tens of Tbps 且多年 100% 可用。

## 问题与动机

云网关已从简单 NAT 演化为集弹性公网接入（elastic public access）、L4 负载均衡、入侵检测、有状态防火墙于一体的流量调度中枢。腾讯云网关流量年均增长 60%+，最大 region 需支撑上百集群、上千机器、tens of Tbps 吞吐。与搜索/电商/短视频为主的其他云不同，腾讯云的 killer service 是在线游戏和直播，对 RTT、抖动、丢包极其敏感——游戏用户要求端到端 RTT <100ms，意味着网关自身必须提供 µs 级处理延迟来补偿 Internet 与后端开销。

现有方案各有硬伤：固定功能交换机迭代慢、难以适配云内专有协议；[[DPDK]] 软件方案（如 Tripod）在 lab 验证后难以直接 scale 到超大规模；可编程交换机（Tofino/Sailfish 路线）有线速与 CapEx 优势，但 ASIC 资源紧耦合、生态碎片化，Intel 停产 Tofino 带来供应链风险；DPU/FPGA/smartNIC 在大规模网关部署中 CapEx/OpEx 过高。作者 claim 是：在效率、可扩展状态管理、故障恢复三者优先级递增的前提下，用长期运营的 DPDK 软件集群 + 工程化容灾机制，可以桥接学术原型与生产级云网关之间的 gap。

## 关键观察 / 隐含假设

- **观察 1**：腾讯云 workload 以短连接为主，长连接状态备份可以大幅节流。
  - **证据**：多周期 state synchronization 中，仅同步存活 ≥3s 的 flow，可减少 70–80% 复制量；建立/关闭中的连接不同步，依赖 peer LD 的 timeout 回收保持一致性。
  - **依赖假设**：HTTP 请求、Radius 查询等短流占主导，且 3s 阈值足以覆盖需要容灾的长连接。
  - **可能失效场景**：游戏/直播长连接占比上升、连接 churn 模式变化、或 3s 内即需 failover 的极端故障窗口，可能使备份覆盖不足。

- **观察 2**：ECMP + per-core flow affinity 下的「80/20 规则」是核心瓶颈，elephant flow 会打爆单核。
  - **证据**：每个 5-tuple flow 绑定单一 forwarding core；生产 trace 显示 heavy-hitter 导致部分 core 过载、丢包率升至 10⁻⁷~10⁻⁴；Sailfish 用可编程交换机吸收大象流，但剩余响应式流量仍在 x86 上形成瓶颈。
  - **依赖假设**：流量偏斜是结构性问题而非临时 anomaly；跨集群 live migration 比原地扩核更经济。
  - **可能失效场景**：更均匀的 flow 分布、更细粒度 per-packet 调度硬件、或 migration 本身引入的 proxy 放大在尾延迟敏感场景不可接受。

- **观察 3**：intra-cloud 流量约占 80%，同 tenant 跨 AZ 分流会造成明显延迟抖动。
  - **证据**：数据中心实例数占 45%+，intra-cloud 流量占约 80%；因此 Inter-AZ 采用 Active-Standby（不同 IP 段互为热备）而非 Active-Active，避免同 tenant 连接落到不同 AZ。
  - **依赖假设**：AZ 间 RTT 差异对游戏/直播 QoS 可感知；50% 冗余（一个 AZ 可承接对端全部流量）在成本上可接受。
  - **可能失效场景**：全球化 anycast 入口 + 多 AZ 主动分担更优时，Active-Standby 可能浪费容量；region 级灾难仍只能 DNS 重路由并打断全部连接。

- **观察 4**：大量 forwarding plane 故障根因在「特定 VIP 的异常流量模式」，而非组件本身。
  - **证据**：Decentralized migration 将受影响 VIP 均分到 k 个 buffer set（典型 k=10），把 blast radius 缩小 1/k；case study 通过 Drop Points 类型定位单 LD jitter 根因。
  - **依赖假设**：VIP 与服务类型一一对应，异常流量可隔离到 VIP 粒度；冷迁移在 buffer set 上可接受。
  - **可能失效场景**：跨 VIP 的协同攻击、控制面 bug、或 orchestrator 误判导致错误 VIP 切分。

- **假设 1**：DPDK 软件 forwarding plane 在总拥有成本上优于大规模可编程 ASIC 部署。
  - **证据强度**：中。8 年生产运营与 30+ region 部署是强证据；但论文也承认在 LD 上下游已小规模引入可编程交换机（~2 Tbps/集群），说明路线是混合而非纯软件。

- **假设 2**：dispatcher:processor = 1:2 及 4-LD 集群是普适运营甜点。
  - **证据强度**：中。来自多年 empirical tuning；曾试 8 LD/集群但发现 4 LD 故障域更小且足够，外推到其他云厂商 workload 需谨慎。

## 核心方法

TGW 在架构上按功能与状态需求解耦：**TGW-EIP** 部署在 region 入口，负责无状态弹性公网接入（VIP→DIP GRE 封装、anycast、多 ISP 选路）；**TGW-CLB** 部署在每个 AZ，负责有状态 L4 负载均衡（5-tuple / IP-pair / QUIC connectionID 等多种 flow affinity）。数据平面核心为 **Load Distributor (LD)**，配合 commodity router（[[BGP]]/[[ECMP]]）、本地 **operator**、全局 **orchestrator**、主动探测 **probers** 与分布式日志分析 **brains**，形成 management / control / data 三层松耦合结构（见图 1）。

**转发平面优化**直接回应观察 2 的效率需求。TGW-EIP 采用 run-to-completion (RTC)：单连接单核处理，最大化并行与低延迟。TGW-CLB 采用两阶段 pipeline：dispatcher 按服务规则（IP-pair、QUIC-aware 等）将包映射到 processing core，规避 NIC [[RSS]] 无法表达的业务级 affinity；每 dispatcher 配独立 ring buffer 避免锁。hash lookup 是实测瓶颈（占 20% CPU），通过 batch prefetch（batch≤64）、separate-chaining 哈希表、64B 对齐节点（每节点存 4 个 rule index）将 lookup CPU 降至 5%，L2/L3 cache hit 各提升 8%。

**Live migration**（§5）回应 elephant flow 过载与弹性扩缩容。流程分三阶段：(1) operator 将无状态配置复制到新集群，migration agent 按 **VIP 粒度**重组跨核的 connection state（单 LD 可达 240M states，直接聚合表开销不可接受）；(2) ≥90% 状态同步后，LD 发 BGP 宣告将 VIP 流量切到新集群；(3) 迁移期间旧集群不锁，新集群对未知流作 **LD proxy**——将包转发到旧集群所有 LD，仅首包处理 LD 响应，避免新连接丢包。为降低 proxy 放大，利用 backend vSwitch 的 source IP learning：新集群 GRE 隧道外层源 IP 保持为新 LD_IP，出方向流量经 vSwitch 学习后直连新集群，单流仅需代理首包 outbound 前的少量包。Testbed 上 8M 连接 **4s 收敛、零丢包**；生产上 1371 VIP / 130M 连接，95.6% 在 20s 内完成。

**多层故障容灾**（§6）优先级最高。State backup 采用多周期同步（观察 1）：≥3s 活跃流才复制、MTU 批次每 4min 插入/2s 导出、满批立即发送。Intra-AZ **Active-Active**——同 AZ 内 LD 共享状态表，BGP+BFD 毫秒级检测，故障后 consistent hash 最小化流量重分布；Inter-AZ **Active-Standby**——AZ 对互备状态但服务不同 IP 段，故障方以更短前缀宣告接管（longest-prefix match 保证正常时分流）；Inter-region 只能改 DNS 或引导客户端换 region，接受全连接打断。当备份机制失效（观察 4），**Decentralized migration** 将异常 VIP 拆到 k 个 standby buffer set 做并发冷迁移，典型 k=10。

**Taint-based telemetry**（§7）在 tenant 无感知前提下定位故障。TGW probers 每 5s 对 (VIP,VPort) 发 TCP SYN 半握手探测（防火墙规则阻止三次握手完成以节省 backend 资源）；LD 在 Trace Points 打 taint（含唯一 LD ID），在 >20 类 Drop Points 记录丢包原因；日志经 proxy 汇聚到分布式 brains，20s 流式聚合，**1 分钟内**完成检测—分析—决策闭环。历史日志 >10 TB/天存 DDBS，倒排索引支持秒级查询。

运营经验（§8）强调 blast radius 隔离、50% 冗余、4-LD 集群甜点、禁用 CPU C-State 切换（改用扩缩容）、odd-even routing 保证 IP-pair session persistence、multicast→unicast 状态同步以降低跨 region OpEx。深度实现细节回 [[atc2025-yang-yifan]] 或 [[atc2025-yang-yifan.pdf]]。

## 设计取舍

- **软件 DPDK vs 可编程硬件**：选择 DPDK 集群获得开发灵活性、供应链独立与可移植性（已部署到数十家外部大客户），牺牲线速 ASIC 的每 Gbps 成本与功耗优势；在 LD 上下游仍局部使用可编程交换机处理大象流。
- **RTC vs Pipeline 分离**：EIP 无状态走 RTC 极简低延迟；CLB 有状态走 pipeline 换灵活 affinity，代价是 dispatcher 成为额外 hop、需 empirical 核比例调优。
- **Live vs Cold migration**：关键业务坚持 live migration 避免重连；集群已崩溃或攻击隔离场景接受 cold migration 与连接打断。
- **Active-Standby vs Active-Active（跨 AZ）**：用容量冗余换 jitter 一致性；正常时每个 AZ 只处理本段流量，故障时单 AZ 承接双倍负载。
- **State sync 节流 vs 恢复速度**：3s/4min/2s 等经验参数大幅降低带宽与 CPU，但故障窗口内 young connection 可能丢失状态；论文未给出 young flow 丢失率的量化边界。
- **边界条件**：Gaming/live streaming、GRE 隧道 + VPC 解封装、腾讯云专有 port-segment 游戏房间配置是设计甜点；纯无状态 CDN 边缘、超大规模 L7 代理、或强依赖 P4 线速的新部署可能更适合 Sailfish/Luoshen 类混合方案。

## 实验与结果

- **单节点吞吐**：TGW-CLB（50 核 pipeline，O(1M) 静态规则 + O(100M) 动态连接状态）在 512B 包、99% CPU 下吞吐为 Tripod 的 **2.9×**（128B 为 2×，50% CPU 下达 3.1×）；1024B 包最大 **96.8 Gbps**。
- **单节点延迟**：多数负载下平均处理延迟 **66–105 µs**，随负载略升。
- **双集群迁移**：8M 连接从 cluster A 迁到 B，proxy 放大初期为 4×，利用 outbound learning **<4s 收敛、零丢包**。
- **双 LD 故障恢复**：LD2 宕机后 ECMP 立即将流量切到 LD1，预同步状态使请求几乎无中断；LD2 重启后 BGP 均分恢复。
- **生产吞吐与丢包**：大促一周 tens of Tbps；heavy-hitter 冲击下 worst-case 丢包率 **10⁻⁷~10⁻⁴**；集群间负载大体均衡，热备集群承接突发迁移。
- **生产 migration**：1371 VIP / 130M 连接，**95.6% VIP 在 20s 内**完成（24.5% <10s，71.1% 在 10–20s）；两集群 /24 VIP 段迁移 **2 min 收敛、零丢包、tenant 无感知**。
- **生产 failover**：4-LD 集群 3 Mpps，LD1 故障后其余 LD 立即均分接管；**130M 连接 13s 同步完**，单 NIC 峰值 350 Mbps。
- **可用性**：2021 上半年起 unavailability 降为 **0**；多年 **100% 可用性**（作者 claim）；30+ region、单 region 数百集群/数千机器。

## Critical Analysis

### 论证链条

论文的 observation → design → result 链条在「大规模有状态 L4 网关」这一问题上总体闭合：gaming/live streaming 的 µs 延迟与零重连需求 → 选择可深度调优的 DPDK 软件 + live migration + 多层冗余；80/20 与 per-core affinity → VIP 粒度 migration + decentralized VIP 隔离；短连接主导 → 多周期 state sync 节流。Testbed 微基准（vs Tripod）与生产 trace（Tbps、迁移、failover）形成互补，比纯 lab 论文更有说服力。

薄弱环节在于：(1) Tripod 是 2019 年 JSAC 框架，baseline 新鲜度有限，且未与 Maglev/Ananta/Sailfish 同平台对比；(2) 生产丢包率 10⁻⁴ 在游戏场景是否可接受，论文未与 tenant SLO 或 RTT/jitter 分布关联；(3) 「100% 可用性」是运营 claim，缺乏与业界通用 availability metric（如 99.99% 含计划内维护）的精确定义对照。

### 假设压力测试

- **Workload 漂移**：若 QUIC/HTTP3 长连接、AI 推理 east-west 流量占比上升，3s sync 阈值与 1:2 dispatcher 比例可能需重调；论文仅展示 QUIC-aware 调度能力，无 QUIC 主导场景下的 migration/failover 数据。
- **硬件代际**：测试床为 AMD EPYC 7K62 + 100G Mellanox；未讨论 DDR5/CXL、200G/400G NIC 或 NUMA 变化对 RTC/pipeline 的影响。
- **规模外推**：240M states/LD、130M 连接同步是 impressively large，但是否线性外推到更大 VIP 密度、更频繁 microburst，论文未做 sensitivity analysis。
- **多租户隔离**：Rate limit 与 VIP 级 decentralized migration 有隔离意识，但 proxy 放大期间同集群其他 tenant 的 tail latency 影响论文未量化。

### 实验可信度

- **Benchmark 代表性**：生产数据来自大促周与真实 failover/migration 记录，比 synthetic UDP 更有说服力；testbed 用 HTTP 故障恢复与 UDP 吞吐混合，覆盖有限。
- **Baseline 公平性**：与 Tripod 同用 50 核 DPDK，但 TGW 含多年工程优化（内存管理、OS 配置等），优势部分来自 operational tuning 而非单一算法创新，论文诚实列出但未 ablate 各优化贡献。
- **Ablation**：缺少对 batch hash、LD proxy、outbound learning、multi-cycle sync 各组件的独立开关实验；难以判断 marginal contribution。
- **Metrics**：吞吐、丢包率、迁移收敛时间覆盖较好；**尾延迟、jitter、migration 期间延迟分布**几乎未报告，对 gaming claim 是关键缺口。

### 系统性缺陷

- **Migration proxy 放大**：新集群初期 4× proxy 流量有实测，但对 tenant 感知延迟与安全面（放大攻击面）讨论较浅。
- **控制面复杂度**：orchestrator + operator + brains + BGP 前缀游戏 + 多周期 sync 参数交织，运维认知负担高；论文分享经验但未提供自动化调参或 formal invariant。
- **Region 级灾难**：只能 DNS 重路由且全连接打断，RTO 取决于客户端；论文承认 survivability > performance，但未讨论跨 region state 复制的可行性边界。
- **可观测性成本**：>10 TB/天日志、GBps 级聚合潜力，对较小云厂商可能不可承受；论文未讨论采样或分级 telemetry 的降级方案。
- **供应链立场**：批评 Tofino 风险的同时，自身仍依赖 DPDK/NIC 生态与腾讯内部运营经验，**外部移植**的隐性成本（「数十家大客户」）缺少独立第三方验证。

## 局限与 Future Work

- **局限 1**：核心参数（3s sync 阈值、4min batch、2s export、k=10 buffer set、4-LD 集群）均为 empirical，缺乏对不同 workload 的自适应或理论 grounding。
- **局限 2**：与可编程交换机/[[Disaggregation]] 网关（Sailfish、Luoshen）的端到端 TCO 对比不完整，局部 programmable switch 部署（2 Tbps）未纳入统一 evaluation。
- **局限 3**：Inter-region 故障只能断连恢复，无跨 region connection state 方案。
- **Future work 1**：在真实 gaming trace 上测量 migration/failover 的 **RTT/jitter 尾部分布**，验证 10⁻⁴ 丢包率与 proxy 放大是否满足 <100ms RTT SLO。
- **Future work 2**：对 batch hash、outbound learning、decentralized migration 做 component-level ablation，分离「算法设计」与「多年工程调优」的贡献。
- **Future work 3**：探索 hyper-converged gateway（CPU + ASIC + DPU）作为下一代 TGW 的渐进演进路径，在控制面 API 不变前提下替换 forwarding plane（论文 §2.2 已预留接口）。

## 相关

- **相关概念**：[[DPDK]]、[[Load-Balancer]]、[[ECMP]]、[[BGP]]、[[BFD]]、[[GRE]]、[[QUIC]]、[[Disaggregation]]
- **同类系统**：[[Sailfish]]、[[Luoshen]]、[[Tripod]]、[[Ananta]]、[[Maglev]]、[[Protego]]、[[Duet]]
- **同会议**：[[ATC-2025]]
- **对比**：TGW 代表「长期运营的纯软件 DPDK 集群 + 工程容灾」路线；Sailfish/Luoshen 代表「可编程交换机/超融合硬件加速」路线——前者胜在供应链与可移植性，后者胜在 CapEx/线速但受 ASIC 生态约束。