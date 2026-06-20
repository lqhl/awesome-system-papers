---
type: paper
name: HARE
full_title: "Cache-Centric Multi-Resource Allocation for Storage Services"
authors: [Chenhao Ye, Shawn (Wanxiang) Zhong, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau]
venue: FAST
year: 2026
tags: [resource-allocation, multi-tenant, cache, fairness, drf]
source_pdf: "[[fast2026-ye.pdf]]"
source_md: "[[fast2026-ye]]"
---

# Cache-Centric Multi-Resource Allocation for Storage Services (FAST 2026)

> **一句话总结**：基于「cache 改变 miss ratio → 连带改变 I/O/网络/DB unit 需求」这一 demand correlation 观察，HARE 用 harvest/redistribute 两阶段在租户间交易 cache 与 cache-correlated 资源、优先收割系统级 dominant 资源，最大化 min normalized throughput；在 HopperKV（[[Redis]]+[[DynamoDB]]）上最高 **1.9×**、BunnyFS（NVMe FS）上最高 **1.4×**，cache 不敏感时退化为 [[DRF]]。

## 问题与动机

现代 multi-tenant 存储服务要同时管理硬件资源（网络、I/O 带宽）和软件资源（如 [[DynamoDB]] read/write unit），还要在 [[Redis]]/Memcached 等共享 cache 上做多租户隔离。作者 claim 的核心缺口是：**现有框架把 cache 与其他资源割裂处理**。

- **Equal partition** 能保证 sharing incentive（每租户至少拿到 1/x 独占资源时的性能），但忽略需求异构，大量资源闲置。
- **[[DRF|Dominant Resource Fairness]]** 在 cache-oblivious 场景表现良好，但假设资源需求相互独立、与分配量线性相关；cache 的 miss ratio 对容量非线性，且更多 cache 会降低对 I/O、网络、DB read unit 等 **cache-correlated** 资源的需求——无法塞进 DRF 的 demand vector。
- **纯 cache partition 框架**（[[Memshare]]、FairRide、LAMA 等）只优化 miss ratio，不感知其他资源；CoPart 仅处理 LLC 与 memory bandwidth 这一对相关性。[[Spirit]] 同期工作也只覆盖 cache+network 双资源。

因此需要统一框架：把 cache 作为一等资源，与多种 cache-correlated 资源 **holistic** 分配，在维持 fairness 的同时提升整体吞吐。论文用两个系统验证通用性：**HopperKV**（云原生 KV，Redis 缓存 DynamoDB）和 **BunnyFS**（基于 [[uFS]] 的 NVMe 本地文件系统）。

## 关键观察 / 隐含假设

- **观察 1**：cache 具有 **非线性性能** 与 **demand correlation**——2× cache 不等于 2× 吞吐；增大 cache 会降低 miss ratio，从而减少对下层资源（I/O、网络、DB RU）的需求，且不同资源被 cache hit 节省的程度不同（由 cache-saving constant α_i 刻画）。
  - **依赖假设**：每租户对 cache 的敏感度（MRC 形状）可在线估计且在一段时间内相对稳定；α_i 可通过 hit/miss 两种路径的资源记账推导。
  - **可能失效场景**：workload 剧烈突变（working set 瞬间换血）、MRC 估计误差大（尤其 miss ratio 极低时）、或 cache replacement 策略不满足 inclusion property 时，trading deal 的补偿计算会失真。

- **观察 2**：租户间 **cache 敏感度异构** 是主要收益来源——高 locality 租户多拿 cache 能省下大量下层资源；write-heavy 或 sequential 租户对 cache 几乎无感，应成为 cache donor。当所有租户 dominant resource 相同时，纯 [[DRF]] 无法从 cache 重分配获益。
  - **依赖假设**：系统总 cache 容量不足以让所有 working set 同时 fit；存在可盈利的 cache↔资源交易对。
  - **可能失效场景**：所有租户 working set 都能放进 baseline cache（论文 microbenchmark 中 T1≤3M keys 时 HARE 直接退回 DRF）；或租户数极多导致每租户 cache 过小、MRC 梯度噪声主导。

- **观察 3**：瓶颈会随 cache 分配 **动态迁移**——disk I/O-bound 的租户拿到更多 cache 后可能变成 network-bound；多资源场景下必须优先收割 **系统级最稀缺的 harvest**，否则 redistribute 阶段收益被卡死。
  - **依赖假设**：每租户吞吐由 min_i T_i(r_c, r_i) 决定（DRF 式 dominant bottleneck）；rate limiter 能有效执行各资源配额。
  - **证据强度**：**强**——filesystem 两租户示例与 HopperKV 多资源模型在实验中一致；但 CPU cycles 在 HopperKV 中被显式排除在分配范围外（假设 Redis 非 CPU-bound）。

- **假设 1**：sharing incentive 可用 **normalized throughput ≥ 1**（相对 weighted/equal baseline）形式化，且 max-min normalized throughput 是合理优化目标。
  - **证据强度**：**中**——理论分析与 fairness space 可视化支持；但 HARE 是 greedy 算法，不保证全局最优，只保证 ≥ baseline 且 ≥ equal-cache-partition 的 [[DRF]]。

## 核心方法

### HARE 算法（Harvest-Redistribute）

HARE 扩展 [[DRF]]，输入每租户的 **miss ratio curve (MRC)**、demand vector ⟨d_1,…,d_n⟩、cache-saving constants ⟨α_1,…,α_n⟩。单请求对资源 i 的平均消耗为 `(1 - α_i + α_i · m(r_c)) · d_i`，吞吐 T_i = r_i / 该成本；实际吞吐 T = min_i T_i。

**Harvest 阶段**：从 equal（或 weighted）baseline 出发，迭代在租户 t1、t2 间做 cache chunk 交易——t2 获得 Δr_c cache 后 relinquish 部分资源，t1 失去 cache 需 compensation；差额进入 harvest pool。每轮先选系统级 dominant resource（harvest 相对总量最稀缺者），再选在该资源上最 profitable 的 deal。重复至无正收益交易。

**Redistribute 阶段**：将 harvest 按各租户当前持有量加权分配，等比抬高所有租户吞吐。对 non-dominant 闲置资源，HARE 采用 **conserving redistribution**（不同于 [[DRF]] 的策略性保留），给租户额外「余量」以吸收 burst 和估计误差。

当所有租户 cache 敏感度一致、harvest 无交易时，HARE **gracefully degrades** 到 [[DRF]]。

### HopperKV：云 KV cache 层

回应观察 1–3 的工程实例。架构：每租户独立 [[Redis]] 实例（LRU 隔离）+ Redis Module（HOPPER.GET/SET）+ allocator daemon。

- **资源范围**：Redis cache、network bandwidth、DynamoDB RU/WU；write-through，WU 为 cache-independent（α=0），network 与 RU 为 cache-correlated。
- **在线 MRC**：spatially-sampled **ghost cache**（采样率 1/32，<1% 误差、<25ns/key 开销），利用 LRU inclusion property 维护 miss ratio table。
- **demand 学习**：Module 同时记账 actual 与 hypothetical hit/miss 用量，推导 demand vector 与 α。
- **动态与鲁棒**：每 ~20s 基于滑动窗口（~1min）重算；仅当预测收益 >5% 才切换分配；cache 以 16MB chunk 平滑迁移；MRC **salting**（+1% 常数）防止极低 miss ratio 估计误差导致 RU 配额的灾难性 under-allocation。

### BunnyFS：本地 NVMe 文件系统

验证 HARE 跨场景通用性。基于 semi-microkernel [[uFS]]，通过 shared memory 服务请求；管理 page cache、I/O bandwidth、worker CPU cycles（step 3 内存拷贝，cache-independent）。worker 维护 per-tenant LRU + ghost cache；allocator 线程周期性运行 HARE。读优化为主，写按 uncacheable read 处理。

## 设计取舍

- **Greedy trading vs 全局最优**：MRC 形状任意使最优分配 NP-hard；HARE 选每轮最 profitable deal，可能收敛到局部最优，但保证不低于 baseline 和 equal-cache [[DRF]]。
- **Conserving redistribution vs strategy-proofness**：[[DRF]] 故意保留 non-dominant 闲置资源以防虚报；HARE 为鲁棒性把这些资源也分给租户，牺牲 strategy-proofness（论文明确非重点）。
- **Per-tenant cache partition vs global LRU**：HopperKV/BunnyFS 坚持分区以保证 isolation 和 sharing incentive；NonPart/global LRU 可提效率但论文展示最多 **3×** slowdown 且破坏 fairness（Redis LRU 不看 value size 加剧不公）。
- **单节点 scope**：HopperKV 聚焦单机 multi-tenancy；多节点需上层 placement（类比 Pisces），论文列为 future work。
- **边界条件**：在异构 locality、混合 read/write/scan、资源配额通过 rate limiter 可 enforcement 时最优雅；纯 CPU-bound、极低 miss ratio 且估计噪声大、或 cache 迁移期间 warmup 窗口可能短暂降吞吐。

## 实验与结果

**HopperKV**（AWS EC2，baseline：2GB cache、50MB/s network、1K RU/s、1K WU/s）对比 baseline、[[DRF]]（equal cache）、Memshare+[[DRF]]、NonPart：

- **两租户 microbenchmark**：同 dominant resource（RU）时 [[DRF]] 无增益，Memshare+DRF 最高 **~50%** 退化；HARE 最高 **+63%** min normalized throughput。T1 working set 增至 4M keys 时 HARE **+56%**（[[DRF]] 无改进）。
- **16 租户 YCSB scaling**：13/16 租户在 HARE 下拿到最佳吞吐，normalized **1.6–2.7×**；[[DRF]] **1.2–1.9×**；NonPart 6/16 租户最高 **3×** slowdown。
- **动态 stress test**（4 租户 workload 每分钟变化）：HARE 稳定 **~1.7–1.9×**，DRF ~1.3×；cache 迁移带来收敛延迟但 smooth migration 避免剧烈振荡。
- **Twitter production traces**（6 集群）：除 T1（working set 极小、已饱和 client）外，HARE 至少 **+38%**，[[DRF]] 仅 **+16%**，Memshare+DRF 伤害 T3 **4%**。
- **Tail latency**：HARE 主要优化吞吐，但 p999 与 alternatives 持平或更好（MRC salting 给低 miss 租户额外 RU 容量吸收 burst）。
- **算法开销**：每轮 O(n)，实测微秒级，相对秒级重分配周期可忽略。

**BunnyFS**（Intel Xeon + Optane NVMe，2GB cache、4 vCPU、2GB/s I/O，最高 32 租户）：

- **Scaling**：[[DRF]] 仅 **+10%**；HARE **+40%** 多数租户；NonPartCache+DRF 因 sequential 租户污染 global LRU 且低 miss 租户被 starve，fairness 被破坏。
- **Dynamic**（4 租户 working set 随时间缩小）：HARE 持续优于 fair baseline/DRF；35s 后 T4 working set 可 fit cache 时 NonPartCache+DRF 仍因 eviction 干扰低于 baseline。

## Critical Analysis

### 论证链条

观察（cache demand correlation + 租户敏感度异构）→ MRC/demand vector/α 建模 → harvest 沿等吞吐 contour 交易 cache → 优先收割 dominant harvest → weighted redistribute：逻辑链闭合良好。Figure 3 的 performance/fairness space 可视化直接支撑「max-min normalized throughput」目标。

薄弱环节在于：**最强数字来自受控 microbenchmark 和作者自研系统**；HopperKV 的 baseline 是 equal partition + 专用 Redis 实例，与生产 ElastiCache 集群（cluster mode、复制、故障转移）仍有距离。把「16 租户 YCSB 2.7×」外推到「云存储服务普遍 2×」需警惕——Group A write-heavy 租户作为 cache donor 的模式是否普适于真实 trace 尚依赖 Twitter 子集验证（仅 6 trace、1GB cache）。

论证中一步未完全实验闭合：**多资源 deal 向量化后只优化 dominant harvest 的标量差额**，论文承认 multi-resource trade-off 可能 suboptimal，但未给出与最优/穷举的 gap 量化。

### 假设压力测试

- **MRC 准确性**：ghost cache + 1/32 采样在论文 workload 上 <1% 误差；但 scan-heavy（YCSB-E-like）或 admission 变化时 MRC 可能滞后；salting 缓解极低 miss 场景，却轻微偏向低 miss 租户（作者承认 bounded）。
- **Workload 稳定性**：20s 重分配 + 1min 窗口假设变化在秒级以上；突发 traffic shift 时 cache migration warmup 可能造成 transient degradation（Section 4.3 有机制但未量化 worst-case 尾延迟）。
- **部署拓扑**：HopperKV 单机、每租户一 Redis；真实云环境常见共享 Redis cluster、跨 AZ DynamoDB、弹性 RU 上限——rate limiter 模型是否仍准确论文未覆盖。
- **写路径与一致性**：write-through 使 WU 与 cache 无关；read-heavy cache 优化结论能否推广到 write-heavy DB fronting 需打折。
- **BunnyFS 读偏向**：写被当作 uncacheable read，未探索 write-back / metadata cache 交互；NVMe microkernel 场景与分布式 storage service 的瓶颈结构不同。

### 实验可信度

- **Benchmark 代表性**：YCSB 变体 + Twitter trace 覆盖多种 skew/size/write ratio，优于纯合成；但缺少 Meta/Facebook 级 CDN cache trace 或共享 block storage 生产负载。
- **Baseline 强度**：对比 baseline、[[DRF]]、Memshare+DRF、NonPart 较完整，且均移植到同一 HopperKV 代码库，公平性较好。未与 [[Spirit]]（SOSP'25，cache+network auction）、Moirai/Centaur/Argon 等「单相关资源」方案同台；Spirit 目标场景是 remote memory 而非 DB fronting cache，但理念相近。
- **Ablation**：有 varying working set / hotness / tenant count / dynamic / trace；缺「去掉 dominant harvest 选择」「去掉 MRC salting」「去掉 smooth migration」等机制分解。
- **Metric**：聚焦 min normalized throughput 与绝对吞吐，与优化目标一致；p999 有报告但非主优化目标；**成本（DynamoDB RU 账单）、故障恢复、多节点** 未讨论。

### 系统性缺陷

- **Isolation 与 SLO**：per-tenant Redis 实例隔离 cache，但 daemon 集中决策；单 allocator 故障影响全局，论文未讨论 HA。
- **尾延迟保证**：无 queueing-theoretic 约束纳入 harvest 阶段（列为 future work）；rate limiter 下 burst miss 仍可能 throttle。
- **可观测性/运维**：4K LoC Module+daemon，但生产需持续监控 MRC 漂移、deal 收敛状态；论文未描述 operator 界面或 rollback 策略。
- **兼容性**：需 Redis Module 与定制 API（HOPPER.GET/SET），非 drop-in ElastiCache replacement。
- **公平性定义**：normalized throughput 相对 static baseline，若租户付费权重不同需 weighted baseline（论文支持扩展但未评测）。

## 局限与 Future Work

- **局限 1**：HARE greedy，非最优；MRC 任意形状下最优分配计算困难，论文只保证 ≥ baseline/DRF。
- **局限 2**：HopperKV 单节点；BunnyFS 读优化、写处理简化；CPU 未纳入 HopperKV 分配 scope。
- **局限 3**：动态场景下 cache 迁移有收敛延迟，快于 20s 的 workload 切换可能跟不上。
- **Future work 1**：将 queueing 模型嵌入 harvest，过滤会导致 tail-latency spike 的 deal——可量化 p99.9 vs 吞吐权衡。
- **Future work 2**：多节点 HopperKV 上层 placement allocator，测量跨节点 cache 与 RU 配额联动收益。
- **Future work 3**：在真实 ElastiCache/DynamoDB 生产集群做 longitudinal study，验证 MRC 采样开销与 RU 账单节省。

## 相关

- **相关概念**：[[DRF]]、[[Multi-Tenant-Resource-Allocation]]、Miss-Ratio-Curve、Ghost-Cache、Demand-Vector、Sharing-Incentive
- **同类系统**：[[Memshare]]、[[Spirit]]、CoPart、FairRide、RobinHood、[[Redis]]、[[DynamoDB]]、HopperKV、BunnyFS、[[uFS]]
- **同会议**：[[FAST-2026]]
- **对比**：[[Spirit]] 用 Walrasian auction 处理 cache↔network 互依；HARE 用 greedy harvest/redistribute 覆盖任意多种 cache-correlated 资源，并证明可退化到 [[DRF]]