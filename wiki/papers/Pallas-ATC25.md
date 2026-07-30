---
type: paper
name: Pallas
full_title: Towards Optimal Rack-scale µs-level CPU Scheduling through In-Network Workload Shaping
authors: [Xudong Liao, Han Tian, Xinchen Wan, Chaoliang Zeng, Hao Wang, Junxue Zhang, Mengyu Ma, Guyue Liu, Kai Chen]
venue: ATC
year: 2025
tags: [rack-scheduling, programmable-switch, tail-latency, workload-shaping, microservices]
source_pdf: "[[atc2025-liao.pdf]]"
source_md: "[[atc2025-liao]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Pallas：通过网络内工作负载调整实现最佳机架级 µs 级 CPU 调度（ATC 2025）

> **原题**：Towards Optimal Rack-scale µs-level CPU Scheduling through In-Network Workload Shaping

> **一句话总结**：观察到混合长短请求在 rack 内使 application-agnostic JSQ 跨服务器倾斜（~3× tail slowdown）且服务器内 HoL blocking 使 cFCFS/TS/DARC 比理想 PS 慢 ~50×，而同质 workload 上简单 cFCFS 可近最优；Pallas 在 ToR 交换机做 application-aware workload shaping + WRR 组内均衡 + cFCFS 内部调度，中负载 P99 比 RackSched-DARC 低 8.5×，RocksDB 高负载低两个数量级，并靠 request bouncing / burst cloning 应对动态 workload。

## 问题与动机

在线 KV store、in-memory DB、FaaS、搜索排序等 **µs 级 SLO** 服务需要 rack 内数百至上千 core 的横向扩展。[[RackSched]] 等 prior work 用可编程 ToR 交换机做 inter-server [[Load-Balancing]]，服务器侧用 [[Shinjuku]] / [[Persephone-SOSP23|Perséphone]] 等 dataplane OS 做 intra-server 调度。作者 claim：这条路线在 **异构执行时间** workload 下无法稳定维持低 [[Tail-Latency]]。

动机实验（§2）揭示两个结构性失败模式：

1. **跨服务器负载倾斜**：RackSched 的 Join-the-Shortest-Queue (JSQ) 只看队列深度、不看请求实际 CPU 需求；且队列状态需约 **10 µs RTT** 回传，调度决策基于过期信息。8 台服务器上实测 tail slowdown 可差 **~3×**。
2. **服务器内 Head-of-Line Blocking**：application-agnostic 派发使每台服务器同时收到长短混合请求；cFCFS、TS（[[Shinjuku]] preemption）、DARC（[[Persephone-SOSP23|Perséphone]] core 隔离）在 short:long 比例 10%–90% 时均远离理想 Processor Sharing，**~50× slowdown**。

核心问题：能否在 rack 尺度上，对多样 workload 同时做到近最优 tail latency 与高吞吐？Pallas 的回答是——**不要把混合调度难题留给每台服务器，而在网络侧先把 workload 塑造成同质组**。

## 关键观察 / 隐含假设

- **观察 1**：同质 workload 极易近最优调度；混合 workload 极难。Bimodal 实验中，当 short 请求比例为 0% 或 100% 时，RackSched+cFCFS 与理想 RS-PS 尾延迟相当；比例居中时 practical 算法全面崩溃（§2，Figure 2b）。
  - **依赖假设**：执行时间可按 **request type** 聚类，同 type 请求 CPU 需求统计相似（Memcached/Redis header、RPC protobuf 等可暴露 type）。
  - **可能失效场景**：Lucene 等复杂查询，执行时间与 type 弱相关；高度动态、不可预测的 per-request 执行时间使 EWMA 分组失效。

- **观察 2**：µs 级调度下，跨 RTT 获取队列/core 状态本质上滞后；组内若 workload 已同质化，**按请求计数** 的 weighted round-robin 即可近似最优均衡，无需实时 JSQ。
  - **依赖假设**：shaping 后组内执行时间方差足够小，使「请求数 ∝ 负载」成立；fractional server 分配下少数 hybrid 服务器可接受 DARC 兜底。
  - **可能失效场景**：组内 EWMA 均值仍高度重叠的 n-modal workload；burst 使组内瞬时过载超出 20 µs 检测粒度。

- **观察 3**：M/G/K 可分解为多个确定性 M/D/K' 子问题——Wierman 等证明轻尾确定性负载下 **cFCFS tail-optimal**，组间 round-robin near-optimal（§3）。
  - **依赖假设**：shaping 能把 rack 负载切成若干 **确定性轻尾** 子队列；理论结论可外推到有 EWMA 噪声的真实 trace。
  - **可能失效场景**：重尾或强 burst 使「确定性」近似不成立；仅测到 8 台服务器、单机 10 worker core 的规模。

- **假设 1**：目标服务为 **stateless 或 replicated stateful**（微服务、流处理、复制缓存/存储），单请求默认可放在 **单个 packet** 内。
  - **证据强度**：**强**——RocksDB in-memory GET/SCAN、TPC-C silo profile、合成 bimodal/trimodal 均在此假设下评测；论文明确 stateful master 调度超出范围。

- **假设 2**：部署环境具备 **Intel Tofino 级可编程 ToR**，control plane 可 10 ms 读寄存器、离线仿真选策略；服务器基于 [[Persephone-SOSP23|Perséphone]] 扩展，回写实际执行时间供 EWMA 监控。
  - **证据强度**：**中**——完整 P4 原型（763 行，SRAM 2.8%、SALU 10.4%）已落地，但 production 多租户 dataplane 共存、与现有 P4 程序集成论文标为 future work。

## 核心方法

Pallas 将 rack-scale 调度拆为 **三层协同**（Figure 1b），核心创新是 **in-network workload shaping**——在请求到达服务器前，按估计执行时间切分 serving group，把 HoL 与跨服务器倾斜前移到网络侧解决。

**1. Workload Shaper（ToR dataplane）**

根据 packet header 的 8-bit `Type` 字段分类请求；服务器在 response header 回写 32-bit 实际执行时间，交换机 EWMA 更新 per-type 估计。离线阶段用 **customized k-means** 生成多组 group mapping 候选，以 **P99 latency 仿真** 选最优策略，平衡 **组内同质性 vs 整机利用率**（更多 group 降低 HoL 但增加碎片 idle）。资源按公式 (1) 按各 group CPU demand 比例分配 core，允许 fractional server（如 1.2 台 server's 12 cores），并将多 group 尽量合并到同一物理机以减少 hybrid 服务器数量。

**2. Intra-group Load Balancer（ToR dataplane）**

组内用 **weighted round-robin**，权重与各服务器在该 group 预留 core 数成正比。刻意避免 µs 尺度追踪数百 core 状态（需 RTT，信息陈旧），依赖 shaping 使「请求计数均衡 ≈ 负载均衡」。

**3. Intra-server Scheduler（Perséphone 扩展）**

绝大多数服务器只服务单一同质 group，采用简单 **cFCFS**；少数 multi-group 服务器回退 **DARC**。Workload 监控集中在交换机，hybrid 服务器无需重复估计。

**4. Long-term adaptation（control plane，10 ms）**

周期性比较各 group 实时 demand 与分配资源，累计偏差超阈值 **δ=10** 时增量更新策略表，限制受影响服务器数量。策略切换期启用 **request bouncing**：若新到达短请求优先级高于队列中 pending 长请求，则 **清空本地队列、将长请求弹回交换机** 重调度，避免过渡期 HoL（Figure 6）。

**5. Short-term burst handling（dataplane，τ=20 µs）**

组级 burst 检测借鉴 heavy-change detection；超阈值后 **request cloning** 把过载短请求克隆到当前最空闲的 under-utilized group，克隆包 `flag.clone=2` 在目标服务器无 idle core 时 **直接 drop**（no-regret，优于 rack-scale cycle stealing）。全局唯一 `req.index` 过滤较慢的重复响应。深度实现见 [[atc2025-liao]]。

## 设计取舍

- 取舍 1：网络侧塑形 vs 服务器侧复杂调度——用 ToR 可编程逻辑 + 离线策略生成换取服务器侧 cFCFS 简洁性；牺牲对 无 type 头、难聚类 workload 的通用性，换取 tail-optimal 路径。
- **取舍 2：同质性 vs 利用率**——k-means + 仿真显式接受「少量 hybrid 服务器 + DARC」以换更高 core 利用率；TPC-C 将 Payment+OrderStatus 合并而非完全拆开即为例证。
- 取舍 3：静态 WRR vs 动态 JSQ——放弃实时最短队列，避免 10 µs RTT 陈旧性；在 light-tailed 指数 workload 上与 RackSched 性能接近（Appendix D.1），说明 shaping 收益集中在 高离散度 场景。
- **取舍 4：Burst cloning 的 no-regret drop**——克隆请求在忙 core 上直接丢弃，保证 burst 处理绝不比不处理更差，但可能浪费部分计算；与 [[NetClone]] 式通用克隆相比更精准、开销更低。
- **边界条件**：单 rack、8 服务器 × 10 worker core、只读 RocksDB、open-loop DPDK client 时表现最佳；跨 rack、多 packet 请求、强 stateful 一致性需求时设计变脆。

## 实验与结果

- **Testbed**：10 台机器（8 server + 2 client），Intel Tofino，每台 2×12-core Xeon E5-2630 v2，100G ConnectX-4，DPDK 22.11；对比 **RS-DARC**（RackSched 框架 + [[Persephone-SOSP23|Perséphone]] DARC，因 Shinjuku 仅支持 Intel NIC）。
- **Normal Bimodal（90% 10 µs / 10% 100 µs）**：1.9 Mrps 时 P99 比 RS-DARC 低 **16×**；250 µs SLO 下吞吐高 **1.5×**；1.8 Mrps 时 RS 1112 µs vs Pallas 211 µs。
- **Port Bimodal（50/50）**：0.7 Mrps 尾延迟低 **8.5×**；300 µs SLO 吞吐高 **1.4×**。
- **Trimodal**：1200 µs SLO 吞吐 **2.0×**；0.18 Mrps 尾延迟低 **2.3×**。
- **TPC-C（profiled silo）**：200 µs SLO 下达 **2.5 Mrps**，比 RS 高 **1.7×**；最优分组为 Payment+OrderStatus / Delivery+StockLevel / NewOrder 三组。
- **RocksDB in-memory**：Normal（90% GET 12 µs / 10% SCAN 650 µs）稳至 1 Mrps；Port 高负载 0.22–0.23 Mrps 尾延迟低 **两个数量级**，整体 **5.5×**；SCAN 资源分配远优于 RS 的「每机预留 1 core 给短请求」策略。
- **动态 workload**：Port→Normal Bimodal / Port→Normal RocksDB 切换时，adaptation + bouncing + burst 使短请求 P99 平稳；无 reconfiguration 时短请求尾延迟显著恶化。
- **组件 ablation**：burst handling 在 bursty gamma 短请求下平均再降 **6.1×** tail latency；2/4/8 服务器近线性扩展；优于 R2P2 (JBSQ)、Draconis (in-switch cFCFS)、Horus。

## 批判性分析

### 论证链条

Observation（混合 workload 下 JSQ 倾斜 + 服务器 HoL → ~50× gap）→ Design（网络塑形 → 同质组 + WRR + cFCFS）→ Theory（M/D/K + cFCFS tail-optimal）→ Implementation（Tofino P4 端到端）→ Evaluation（多合成 + RocksDB + 动态 + 竞品）链条整体闭合。薄弱跳步在于：**「EWMA + type 分组 ≈ 确定性轻尾 M/D/K」** 主要靠仿真选策略间接验证，未单独 ablate 分组误差对 tail 的敏感性；**near-optimal** claim 相对的是 RS-DARC 而非全空间最优策略。

### 假设压力测试

- **论文已证明**：离散度高的 bimodal/trimodal/TPC-C/RocksDB 上显著优于 RS-DARC 及 R2P2/Draconis/Horus；动态比例变化与 µs burst 下机制有效；监控开销相对 10 ms 间隔可忽略。
- **可能失效**（推断）：
  - **Type 不可分或执行时间高度重叠**：论文承认 Lucene 类 workload 需 ML 估计，当前 header 方案不足。
  - **Stateful / 单主服务**：无 stickiness 与一致性协议，无法直接用于 shard master。
  - **多 rack / 跨 AZ**：仅讨论 hierarchical 扩展设想，未测 core switch 协同与跨 rack 策略一致性。
  - **多资源瓶颈**：内存、磁盘、NIC 成为主导时，纯 CPU-demand shaping 可能错误分组。
  - **生产租户混布**：与现有 ToR P4 程序共存、UDP reserved port 触发逻辑的运维复杂度论文未实测。

### 实验可信度

- **Workload 代表性**：合成分布 + TPC-C profile + RocksDB 只读 GET/SCAN 覆盖 KV/OLTP 典型 µs 服务，但缺少端到端微服务调用图、多租户干扰、写路径 RocksDB。
- **Baseline 公平性**：RS-DARC 替代 Shinjuku 有理由（NIC 兼容 + Figure 2b 显示 DARC≈TS），但可能低估「强 intra-server 方案 + 更好 JSQ 变体」上限；与 Draconis 等对比仅在 port bimodal 单场景（Figure 14）。
- **Ablation**：shaping / bouncing / burst 有分项实验；缺少「错误分组策略」「EWMA 窗口敏感性」「clone drop 率 vs 收益」量化。
- **Metric**：主报 P99 latency vs rps，未系统覆盖 **SLO violation rate、迁移开销、故障恢复、策略错误时的降级行为**。

### 系统性缺陷

- **尾延迟之外**：request bouncing 在切换期丢弃并重排队列，长请求可能经历额外网络往返；论文未量化 bouncing 对 long tail 的副作用。
- **隔离与多租户**：按 group 预留 core 类似硬分区，跨 group 资源借用仅通过 burst cloning，日常低负载时碎片利用率问题论文只在 policy 生成阶段讨论，未给长期 production utilization 数据。
- **可观测性 / 故障恢复**：策略表错误、交换机 control plane 延迟、EWMA 漂移时的行为论文未讨论；δ 阈值误配可导致过度重配置（δ=1）或迟钝（δ=20），仅附录给出敏感性曲线。
- **兼容性**：默认单 packet 请求；多 packet 需嫁接 RackSched request affinity，尚未集成。

## 局限与后续工作

- **局限 1**：仅支持 stateless / replicated stateful；依赖 request type 与执行时间的统计相关性；单 rack 部署；不处理 memory/disk 等多资源 multiplexing。
- **局限 2**：复杂 workload（如 Lucene）需更强监控（论文建议 ML）；生产环境需与现有 dataplane / control plane 基础设施协同，论文未实现。
- **Future work 1**：层次化 multi-rack / datacenter 塑形——需测量 core switch 与 ToR 协同延迟、跨 rack 分组策略一致性及频繁 workload shift 下的 control plane 负载。
- **Future work 2**：多资源 µs 服务调度与 **hardware cFCFS**（Flow Director 等）结合，量化 shaping 收益能否覆盖额外 NIC 调度开销。
- **Future work 3**：对 type 不可信或 adversarial header 场景做 robust grouping（防租户伪造 Type 破坏组内同质性）——论文完全未覆盖安全面。

## 相关

- **相关概念**：[[Tail-Latency]]、[[Load-Balancing]]、[[Programmable-Switch]]、[[Head-of-Line-Blocking]]、[[KV-Cache]]
- **同类系统**：[[RackSched]]、[[Shinjuku]]、[[Persephone-SOSP23]]、[[Shenango]]、[[NetClone]]、R2P2、Draconis、Horus
- **同会议**：[[ATC-2025]]
- **对比**：Pallas 以 application-aware shaping 预防 HoL，相对 RackSched 的 reactive JSQ + 复杂 intra-server 调度是不同设计范式
