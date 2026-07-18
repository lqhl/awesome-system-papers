---
type: paper
name: LESS
full_title: "LESS is More for I/O-Efficient Repairs in Erasure-Coded Storage"
authors: [Keyun Cheng, Guodong Li, Xiaolu Li, Sihuang Hu, Patrick P. C. Lee]
venue: FAST
year: 2026
tags: [erasure-coding, distributed-storage, repair, reed-solomon, hdfs]
source_pdf: "[[fast2026-cheng.pdf]]"
source_md: "[[fast2026-cheng]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# LESS is More for I/O-Efficient Repairs in Erasure-Coded Storage (FAST 2026)

> **一句话总结**：观察到网络带宽增速远超磁盘 random I/O、而 I/O-optimal MSR 编码（如 [[Clay-Codes]]）的指数级 sub-packetization 会带来海量非连续 seek，LESS 通过层叠 extended sub-stripe 在 $\alpha \in [2, n-k]$ 可配置范围内同时降低 repair I/O 与 I/O seeks，在 [[HDFS]] 上把 single-block repair 相比 Clay 最高降 83.3%、full-node recovery 降 36.6%。

## 问题与动机

[[Erasure-Coding]] 是 [[HDFS]]、Ceph、Facebook f4 等分布式存储取代 replication 的主流容错手段，但单块修复（single-block repair）需从同 stripe 读取 $k$ 个完整 block，repair I/O 与 repair bandwidth 都被放大。过去十年编码理论与系统社区大量工作聚焦降低 repair 成本，但多数方案在 **repair I/O minimization** 与 **I/O seek 开销** 之间做了尖锐取舍。

作者的核心判断是：随着 InfiniBand、[[RDMA]]、[[CXL]] 等高速互联普及，网络带宽已不再是 repair 的唯一瓶颈；在 random-access 场景下，**本地磁盘 I/O（含 seek 次数）** 往往主导端到端 repair 时间。现有 repair-friendly 编码各有硬伤：

- **I/O-optimal MSR 编码**（如 Clay）：理论上最小化 repair I/O，但要求指数级 sub-packetization $\alpha = (n-k)^{\lceil n/(n-k)\rceil}$，修复时需大量非连续 sub-block 读取，seek 开销抵消 I/O 收益。
- **[[Locally-Repairable-Codes|LRC]]**（如 Azure-LRC）：单块修复 I/O 低，但 non-[[MDS]]，存储冗余高于 [[Reed-Solomon-Code|RS]]。
- **小 $\alpha$ 的 MDS 编码**（Hitchhiker、HashTag、Elastic Transformation）：$\alpha$ 可控，但 Hitchhiker/HashTag 往往只优化 data block；HashTag+ 需 $\alpha \ge 4$ 且为 $n-k$ 倍数；ET 的变换限制进一步构造空间。

论文要构造一族 **MDS、general $(n,k)$、systematic、小且可配置 $\alpha$** 的编码，在 data 与 parity block 上**均衡**降低 repair I/O 与 I/O seeks，并兼顾 single-block 与部分 multi-block repair 场景。

## 关键观察 / 隐含假设

- **观察 1**：repair 端到端性能由 **repair I/O 量** 与 **I/O seek 次数** 共同决定，单独最小化前者不一定带来更快修复。
  - **依赖假设**：存储节点使用 HDD 或类似 random-access 成本高的介质；block 尺寸在 MiB 级（HDFS 64–128 MiB、f4 256 MiB），repair 以本地读为主；网络带宽可被 Wondershaper 等工具限速到与磁盘可比的数量级（实验默认 1 Gbps）。
  - **可能失效场景**：全 NVMe/SSD 集群且 seek 成本可忽略时，Clay 的极低 repair I/O 可能重新占优；repair 完全受跨节点带宽限制（如跨地域、弱网）时，seek 论点变弱。

- **观察 2**：生产环境中 **single-block failure 占绝对多数**（Facebook warehouse 对 (14,10) stripe 统计约 98%），但 wide-stripe（大 $n,k$）使同 stripe 多块失败更常见，repair 方案不能只优化单块。
  - **依赖假设**：失败块在 stripe 内位置随机；full-node recovery 时各 stripe 丢失块位置不同（论文按随机 node ID 分配模拟）。
  - **可能失效场景**： correlated failure（整机架、批量坏盘）导致同 group 多块失败比例上升时，LESS 的 multi-block 局部修复收益可能变大；若失败高度集中在不同 block group，则大量回退 conventional repair。

- **假设 1**：在 $k > \lceil n/3 \rceil$ 的常见 RS 配置下，LESS 的 repair I/O 严格小于 conventional RS repair（需读 $k$ 个完整 block）。
  - **证据强度**：**强**——式 (7) 给出闭式 repair I/O，Table 2 对 (14,10) 数值验证；但论文未在所有 $(n,k)$ 组合上穷举证明「严格小于」的边界条件。

- **假设 2**：编码与解码的计算开销相对带宽与 I/O 可忽略（与 [6,9,18,19] 等先前工作一致），因此优化编码结构即可转化为 wall-clock repair 收益。
  - **证据强度**：**中**——Exp#B3 显示 LESS ($\alpha=4$) 单线程 encoding 1.6 GiB/s vs RS 2.8 GiB/s，作者称仍高于 1 GiB/s 且瓶颈在 I/O；宽 stripe (124,120) 编码吞吐进一步降至 1.1 GiB/s，大规模部署时计算是否成为新瓶颈论文未充分讨论。

## 核心方法

LESS 参数为 $(n, k, \alpha)$，其中 $2 \le \alpha \le n-k$。核心思想是 **layering extended sub-stripe**：把每个 block 切成 $\alpha$ 个 sub-block，组织成 $\alpha+1$ 个 extended sub-stripe $X_z$，每个 $X_z$ 本身是 tolerating $n-k$ failures 的 Vandermonde-based [[Reed-Solomon-Code|RS]] stripe，且每个 sub-block **恰属于两个** extended sub-stripe（重叠结构保证第 $\alpha+1$ 个 stripe 可由前 $\alpha$ 个的 parity-check equation 线性组合隐式满足）。

构造三步（回应观察 1 的 seek 问题）：

1. **Grouping**：$n$ 个 block 均分为 $\alpha+1$ 个 block group $G_z$，各组大小差至多 1（式 3）。
2. **Layering**：前 $\alpha$ 个 $X_z$ 包含 $G_z$ 全部 sub-block 加第 $z$ 条 sub-stripe；$X_{\alpha+1}$ 包含 $G_{\alpha+1}$ 及满足 $g_i = j$ 的跨组 sub-block。每个 $X_z$ 大小为 $|X_z| = n + (\alpha-1)|G_z|$（式 4）。
3. **MDS 编码**：为 $n\alpha$ 个 sub-block 选取 [[Galois-Field|GF]] 中互不相同的 coding coefficient $\nu_{i,j}$（Theorem 1 给出域大小充分条件；实现用 primitive element 乘法式 6 生成，常见 $(n,k,\alpha)$ 在 GF($2^8$)/GF($2^{16}$) 上 brute-force 验证一次），仅显式编码前 $\alpha$ 个 extended sub-stripe 的 parity sub-block。

**Single-block repair**（回应观察 2 的单块主导）：失败 block $B_i \in G_z$ 的所有 sub-block 都在 $X_z$ 内，只需从 $X_z$ 读取 $|X_z|-n+k$ 个 sub-block 重构，I/O seek 上界为 $k+\alpha-1$（同一 group 内 sub-block 可连续读）。例如 $(6,4,2)$ LESS 读 6 个 sub-block，比 (6,4) RS 读 4 个完整 block 省 25% repair I/O。

**Multi-block repair**：当 $\lfloor (n-k)/\alpha \rfloor \ge 2$ 且所有失败块落在同一 $G_z$ 时，仍在 $X_z$ 内局部修复；否则回退 conventional repair（读 $k$ 个完整 block）。$(14,10,2)$ 同组双块失败读 15 个 sub-block，比 RS 省 25% repair I/O。

**可配置 $\alpha$**：增大 $\alpha$ 降低 repair I/O（式 7）但增加 seek（$k+\alpha-1$），在 data access 与 seek 之间提供连续 trade-off；Table 1 显示 LESS 在 MDS、general $(n,k)$、systematic、小 $\alpha$、data/parity 均优化上相对既有编码填齐了空白格。

实现基于 [[OpenEC]] 中间件 + Hadoop 3.3.4 [[HDFS]] + Jerasure，新增约 8.7K LoC C++，沿用 HDFS packet-level pipelined 编码。

## 设计取舍

- **取舍 1：near-minimum repair I/O vs I/O-optimal MSR**。LESS 不追求 Clay 级别的最小 repair I/O（$(14,10)$ 上 Clay avg 3.25 blocks vs LESS $\alpha=4$ avg 4.64 blocks），换取 $\alpha \le n-k$ 的小 sub-packetization 和固定 $k+\alpha-1$ seek 上界。收益是 HDD/I/O-bound 环境下 wall-clock 大幅领先 Clay；代价是在 seek 成本极低时理论 repair I/O 不如 Clay。
- **取舍 2：层叠 RS 的简洁性 vs 编码吞吐**。基于 Vandermonde RS 保持工程可理解性与 MDS/systematic 性质，但 sub-packetization 使单 stripe 编码路径更长——256 KiB packet 下 1.6 GiB/s vs RS 2.8 GiB/s。作者认为相对 I/O 瓶颈可接受；宽 stripe 或多 stripe 并行编码时影响待验证。
- **取舍 3：局部 multi-block repair vs 通用性**。仅同 block group 内多块失败可局部优化；跨 group 多块失败完全走 conventional repair，不额外优化 repair bandwidth。
- **边界条件**：在 $k \le \lceil n/3 \rceil$ 的「窄 stripe」配置下，式 (7) 的 repair I/O 优势可能不成立；$\alpha=2$ 时 repair I/O 改善温和（(14,10) 数值 avg 7.36 vs RS 10.00），更大 $\alpha$ 才显著拉开差距。

## 实验与结果

- **数值分析 (14,10)**：LESS $\alpha=4$ 平均 repair I/O 比 RS/Hitchhiker/HashTag($\alpha=4$)/ET($\alpha=4$) 降 53.6%/38.1%/23.1%/20.7%；平均 I/O seeks 比 Clay 降 **95.5%**（13 vs 286）。$\alpha \ge 3$ 时 repair I/O 优于除 Clay 外所有 baseline，且 seeks 可控。
- **Wide-stripe**：(124,120) LESS $\alpha=4$ repair I/O 比 RS 降 59.5%（48.6 vs 120 blocks），额外 seeks 仅 +3（123 vs 120）。
- **双块 repair**：LESS 在 27.3–32.8% 的失败组合上优于 RS，(14,10) $\alpha=2$ 平均 repair I/O 降 7.4%；(124,120) $\alpha=2$ 降 10.8%。
- **HDFS testbed（15 机 HDD，默认 1 Gbps 限速，(14,10)，64 MiB block）**：LESS $\alpha=4$ single-block repair 时间比 RS/Hitchhiker/HashTag/ET/Clay 降 50.8%/35.9%/21.5%/21.5%/33.9%；full-node recovery 降 48.3%/34.3%/17.8%/19.4%/36.6%。
- **10 Gbps 带宽**：Clay seek 开销暴露，LESS $\alpha=4$ 比 Clay single-block repair 快 **83.3%**，比 RS 快 28.6%。
- **小 packet（128 KiB）**：LESS 比 Clay 快 50.4%，比 RS 快 59.1%——Clay 处理海量 sub-block 的 CPU/I/O 管理开销更严重。
- **编码吞吐**：256 KiB packet 下单线程 RS 2.8 GiB/s，LESS $\alpha=4$ 1.6 GiB/s；论文称仍 >1 GiB/s 且非瓶颈。

## Critical Analysis

### 论证链条

观察（网络快于磁盘 I/O + Clay 的 seek 惩罚）→ 设计目标（小 $\alpha$ 下同时压 repair I/O 与 seeks）→ LESS 层叠 extended sub-stripe 使单块修复限定在一个 RS stripe 内 → 数值分析验证 I/O/seeks 指标 → HDFS testbed 验证 wall-clock。链条在 **I/O-bound、HDD、MiB 级 block** 设定下闭合较好；作者用 10 Gbps 与 1 Gbps 两组实验支撑「带宽升高后 LESS 相对 Clay 优势更大」的论点，与动机一致。

薄弱跳步：(1) 从 sub-block 级 I/O 指标到 repair time 的映射默认 seek 与读量线性可加，未单独 ablate seek vs volume；(2) full-node recovery 只修 20 个跨 stripe 块，未测整机海量 block 修复时的调度/并行交互；(3) 未与 LRC 做端到端时间对比（Table 1 定性比较 redundancy，缺实测）。

### 假设压力测试

- **全闪存集群**：若单次 random read 延迟接近顺序读，Clay 的极低 repair I/O 可能反超 LESS 的「适度 I/O + 少 seek」策略——论文未在 SSD/NVMe 上验证。
- **计算受限场景**：宽 stripe + 大 $\alpha$ + 小 packet 时，Jerasure 对多层 RS 编码的 CPU 成本可能接近 I/O；Exp#B3 仅单线程单 stripe，未测 repair 路径解码开销。
- **非均匀失败**：correlated 多块失败若跨 group，LESS 大量回退 conventional repair，相对 RS 的增益主要来自单块场景；对 (14,10) 双块 repair 仅 28.6% 组合受益可作为下界提示，但生产 trace 驱动的 failure 模型论文未用。
- **域大小与系数搜索**：Theorem 1 充分条件可能要求大域；Table 4 显示部分 $(n,k,\alpha)$ 在 GF($2^8$) 有 $n$ 上界（如 $n-k=4,\alpha=3$ 时 $n \le 17$），超参部署需查表或搜索，工程摩擦论文轻描淡写。

### 实验可信度

- **Benchmark 代表性**：(14,10) 对齐 Facebook f4 与多篇 FAST 工作，合理；testbed 为 15 机本地千兆/万兆以太网 + 7200 RPM HDD，代表典型 Hadoop 归档/温存储，但不代表 Ceph/RDMA 全闪生产池。
- **Baseline 公平性**：与 RS、Clay、Hitchhiker、HashTag、ET 同台 OpenEC/HDFS 实现，较公平；Clay 在 10 Gbps 下惨败部分因其设计假设与实验设定叠加，需读者自行判断「公平」是否等于「生产 relevant」。
- **Ablation**：$\alpha$ 扫描在数值与 testbed 中均有，支撑 trade-off 论点；缺少对 grouping/layering 各步骤的独立消融（整方案绑定）。
- **Metrics**：覆盖 repair I/O、seeks、repair time、full-node recovery、encoding throughput；**未测** degraded read、repair bandwidth（跨节点传输量）、tail latency、恢复期间对 foreground I/O 的干扰。

### 系统性缺陷

- **部署复杂度**：需在现有 RS 栈上实现 sub-packetization、extended sub-stripe 布局与系数表；比纯 RS 复杂，但比 Clay 的指数 $\alpha$ 更易落地。primitive element 搜索一次性，但 GF 域与 Jerasure 集成仍有运维成本——论文未量化。
- **尾延迟与隔离**：论文未讨论 repair 与正常读写争用磁盘时的 QoS、优先级或 throttling。
- **故障恢复**：仅 block/node 级 repair，未讨论 coordinator 故障、网络分区、修复中断重试的一致性语义。
- **可观测性**：未描述如何监控 per-stripe $\alpha$ 选择、repair 路径（局部 vs conventional）分布。
- **与 LRC/副本混合部署**：未讨论在已有 Azure-LRC 或 replication 集群中迁移到 LESS 的兼容性。

## 局限与 Future Work

- **局限 1**：repair I/O 非理论最优；在 seek 极便宜时 Clay 等 [[MSR-Codes|MSR]] 编码可能仍有 I/O 量优势（作者明确不追求 I/O-optimal）。
- **局限 2**：multi-block repair 仅覆盖同 block group 子集；跨 group 场景无专门优化。
- **局限 3**：编码吞吐低于 RS，宽 stripe 下差距扩大；论文未评估多线程/硬件加速能否完全弥补。
- **Future work 1**：在 NVMe/SSD 与真实 production failure trace 上测量 seek vs repair I/O 的相对权重，给出 $\alpha$ 的自适应选择策略（可基于 per-cluster 带宽与磁盘模型）。
- **Future work 2**：将 LESS 布局与 repair pipelining（如 ParaRC）、minimum-I/O recovery 算法结合，看编码层与算法层增益是否可叠加。
- **Future work 3**：评估 degraded read 路径——LESS 的 sub-block 布局是否像 Clay 一样恶化正常读，或能否沿用局部 stripe 读取降低读放大。

## 相关

- **相关概念**：[[Erasure-Coding]]、[[Reed-Solomon-Code]]、[[MDS]]、[[MSR-Codes]]、[[Sub-Packetization]]、[[Locally-Repairable-Codes]]、[[Degraded-Read]]
- **同类系统**：[[Clay-Codes]]、[[Hitchhiker]]、[[HashTag]]、[[Elastic-Transformation]]、[[Azure-LRC]]、[[OpenEC]]
- **同会议**：[[FAST-2026]]
- **对比**：LESS 相对 Clay 用略高 repair I/O 换极少 seeks；相对 Hitchhiker/HashTag 覆盖 parity block 且 $\alpha$ 更灵活；相对 LRC 保持 MDS 最小冗余
