---
type: paper
name: MDK
full_title: MDK: Rethinking the data center memory reclamation problem
authors: [Shaurya Patel, Suli Yang, Yawen Wang, Kan Wu, Alexandra Fedorova, Margo Seltzer, Kimberly Keeton]
venue: OSDI
year: 2026
tags: [memory-reclamation, datacenter-memory, memory-tiering, optimal-policy, performance-slo]
source_pdf: "[[osdi26-patel.pdf]]"
source_md: "[[osdi26-patel]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-09-14
---

# 重新思考数据中心内存回收（OSDI 2026）

> **原题**：MDK: Rethinking the data center memory reclamation problem

> **一句话总结**：数据中心内存回收的目标是尽量释放 DRAM 同时保证每个时间窗口的性能 SLO，而非在固定容量下最小化总缺页；MDK 用满足窗口化 promotion rate 约束的离线最优策略 OPP、Memory Performance Curves（MPC）和线性时间生成器重建了策略设计工具链，MPC 生成比模拟快 12.5–208 倍，PAW/PACE 在部分负载上比 AGE 多节省最多 10% 内存。

## 问题与动机

传统页面替换假设内存容量固定，目标是在容量约束下最小化整个执行过程的 miss ratio。数据中心的内存回收则主动把运行中作业的冷页迁移到压缩内存、SSD 或 CXL 内存，为调度器腾出 DRAM，目标变成在不违反应用性能 SLO 的情况下让服务器容纳更多作业。

论文聚焦一个具体问题：最大化平均内存节省，同时要求每个监测窗口内的 promotion rate 不超过阈值。promotion rate 是非强制缺页数与窗口内访问过的唯一页面数之比。由于 SLO 在离散窗口上检查，缺页总量较低并不能保证每个窗口都安全；缺页集中在一个窗口仍可能造成尾延迟或吞吐违规。

因此，固定容量替换中的 OPT、MRC 和 inclusion property 不能直接复用。论文提出 Memory Designer’s Kit（MDK），用于给新回收策略提供最优上界、可比曲线和快速参数扫描。

## 关键观察 / 隐含假设

- **观察 1：窗口化性能约束会改变“最优”回收决策。** 在 Cassandra 访问轨迹中，传统 OPT 和 VMIN 虽可减少总 promotion，却把未来缺页集中到同一窗口，违反 2% 或 50% 的目标；OPP 能在整个执行期间保持约束（图 4、表 1）。
  - **依赖假设**：性能代理可以由页面访问轨迹计算，并且 promotion rate 能代表应用性能退化。
  - **可能失效场景**：不同内存层的缺页成本差异很大，或应用性能主要受 CPU、网络和锁竞争影响时，promotion rate 可能不能替代 PSI 或尾延迟。
- **观察 2：越早回收不一定越差，关键是把未来重新访问分散到窗口中。** OPP 在允许的未来窗口 promotion 预算内尽早回收页面；这比等待固定 age 阈值更能积累内存节省（§3.2）。
  - **依赖假设**：页面大小相同，且页面回收带来的节省可按离开 DRAM 的时间线性累计。
  - **可能失效场景**：页面大小不均、迁移有固定批处理开销，或频繁换入换出产生的带宽压力成为主导成本。
- **观察 3：策略参数的单调性可以替代逐参数模拟。** 若更激进的参数包含较不激进参数的 eviction sequence，并在相同时间做相同回收，则可用 critical parameter 累积计算完整 MPC（§3.3–§3.4）。
  - **证据强度**：强。论文对 VMIN 和 OPP 给出构造性说明，并以模拟验证误差不超过 1%。
  - **可能失效场景**：在线反馈、随机决策、多参数之间不可比较，或策略状态因参数不同而分叉时，两个单调性不成立。

## 核心方法

MDK 的 MPC 横轴是目标 promotion rate，纵轴是平均内存节省。它使用散点表达可达到的离散 operating points，避免暗示策略能实现任意中间值。MPC 让设计者可以直接比较同一性能约束下的内存收益，并看到策略的性能上限和参数 cliffs（§3.1）。

OPP 是一个两遍离线算法。第一遍统计每个时间窗口访问过的唯一页面数；第二遍在每个窗口末尾检查页面的下一次访问，只有在该未来窗口仍有 promotion 预算时才回收。它把 promotion rate 作为未来窗口的硬约束，而不是只优化全局缺页数。附录 C 用 first-difference 反证法证明，在论文定义的轨迹模型下 OPP 最大化平均内存节省。

MDK 进一步定义 eviction decisions 和 eviction times 两个性质，作用类似传统替换分析中的 inclusion property。满足性质的单参数策略只需为每次访问计算 critical parameter、该次访问引起的 promotion 和 memory savings，再按参数激进程度做累积。生成器对单参数策略为线性时间；OPP 需要两遍扫描。

论文用该工具构造三种策略。PAW 根据页面过去的 reuse distance，在超过阈值且等待至少一分钟后回收；PACE 在 reuse distance 足够大时立即回收，否则退化到 AGE 的当前空闲时间阈值；L-OPP 用每个工作负载单独训练的 gradient-boosted tree 模仿 OPP 的回收决定。PACE 的两个参数通过 suffix-sum 动态规划联合扫描，避免模拟超过 10,000 个参数组合。

## 设计取舍

- **离线最优换取未来信息依赖**：OPP 适合作为上界和训练标签，不能直接在线部署。其有效性还依赖离线轨迹与运行时窗口边界一致。
- **立即回收换取更高节省**：PAW/PACE 可能更早释放页面，但若历史 reuse distance 不能预测未来访问，promotion 会升高；Memcached 和 FeedSim 上 AGE 的保守策略反而更好。
- **多参数换取适应性**：PACE 可以覆盖 AGE 的行为，但参数调优更容易在同一轨迹上过拟合。论文没有证明训练集和未知轨迹之间的泛化。
- **轨迹级分析换取指标范围限制**：页面表访问位扫描每 30 秒采样一次，无法记录同一周期内的重复访问；该采样对 promotion rate 尚可，但不适合频率型策略或需要精确访问次数的指标。

## 实验与结果

- 使用 CloudSuite 和 DCPerf 的 8 个工作负载，在 Intel Xeon E5-2696、256 GB RAM 上采集轨迹，并在 64 核 AMD EPYC 7B13、128 GB RAM 上进行模拟和 MPC 生成（§5.1、表 2）。
- MDK 生成的 MPC 与模拟结果平均绝对误差均在 1% 内；OPP 的 MPC 生成比模拟 10 个参数设置快 12.5–208 倍，原因是生成器为线性时间而模拟近似二次时间（§5.2、表 2）。
- 在 Cassandra 上，OPP 在 1% promotion rate 下达到 40% 平均内存节省；VMIN 即使放宽到 10% 也达不到相同节省（图 7）。
- PAW 在 GraphX、NGINX 和 TaoBench 上最多比 AGE 多节省 10%，但在访问不可预测的 Memcached、FeedSim 上可能明显落后 AGE（图 7）。
- PACE 的最优离线参数始终不差于 AGE，通常多节省 1–4%；Cassandra 和 GraphX 上提升达到 8–10%（图 7）。这些是用同一轨迹调参和评估得到的潜在上界。
- Linux GraphX Page Rank 端到端实验中，PAW 比 AGE 多节省 4% 内存且没有性能损失；两者实际 promotion rate 约 1.5%，低于离线设定的 4% 阈值，因为运行时间变化导致窗口边界和回收时刻改变（§5.4.3、表 3）。
- L-OPP 在独立测试轨迹上保持约 1% promotion rate，并在 DjangoBench 上略优于 AGE；TaoBench 和 FeedSim 的 precision 较低，导致 promotion rate 过高（图 8）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 传统 OPT/VMIN 不适合窗口化 promotion rate 约束 | 表 1、图 4 | Cassandra；离线页面轨迹；固定时间窗口 | 强 |
| OPP 在给定轨迹模型下提供最优上界 | §3.2、附录 C | 已知未来访问；统一页面大小；promotion rate 约束 | 强 |
| MDK 可准确且快速生成 MPC | §5.2、表 2 | 8 个 CloudSuite/DCPerf 工作负载；误差小于 1%；加速 12.5–208 倍 | 强 |
| PACE/PAW 能超过 AGE | 图 7、表 3 | 主要为离线同轨迹调参；Linux 端到端仅验证 GraphX | 中 |

## 批判性分析

### 论证链条

论文从数据中心 SLO 的窗口化约束出发，说明全局 miss ratio 最优不等于回收问题最优，再用 OPP 把未来窗口预算纳入决策，最后用 OPP 的上界启发 PAW、PACE 和 L-OPP。这个链条在论文定义的 promotion-rate 问题内是闭合的。

主要跳步是把 promotion rate 作为可推广的性能代理。论文承认 PSI、STAR 等指标需要不同的离线模型，但只对 promotion rate 给出完整的 OPP 和生成器实现。因而“MDK 可泛化”更多是框架层面的设计主张，不等于其他代理已经具有同样的最优性证明。

### 假设压力测试

OPP 假设未来访问已知，适合上界分析，不代表在线策略可达到该曲线。PAW 和 PACE 依赖历史 reuse distance 的稳定性；访问模式突变时，立即回收会把缺页集中到窗口中。PACE 虽能退化到 AGE，但找到合适的 `(P, A)` 仍需要在线调参或代表性训练轨迹。

论文的 trace 由 30 秒周期的页表访问位扫描得到。运行时实验显示，即使策略选择来自离线 MPC，实际 promotion rate 也会因程序运行速度不同而改变。这说明窗口化指标不仅依赖访问序列，还依赖采样周期、回收延迟和应用执行速度。

### 实验可信度

实验覆盖 8 个工作负载、模拟准确性、生成速度和一次 Linux 端到端验证，足以支持 MDK 原型和离线比较。PACE 的结果存在同轨迹调参与评估，论文也明确指出这会放大过拟合风险。L-OPP 虽使用独立执行的测试轨迹，但按工作负载分别训练，未展示跨应用泛化。端到端实验没有覆盖 CXL、压缩内存、多租户竞争或 PSI 约束，因此不能直接推出生产环境的收益。

### 系统性缺陷

MDK 当前主要处理统一大小页面和单应用页面轨迹。它没有完整建模迁移带宽、SSD I/O 队列、CXL 延迟差异、后台回收 CPU 开销或多应用间的公平性。策略参数依赖应用特征，在线 tuner 的稳定性、控制震荡和故障恢复也未被评估。论文提出的快速 MPC 依赖单调性；不满足这些性质的随机或复杂多参数策略仍需专用算法或昂贵模拟。

## 局限与后续工作

- **局限 1**：promotion rate 只适合部分硬件和应用组合；PSI 等运行时指标尚未纳入完整的离线最优分析。
- **局限 2**：PACE 的收益是同轨迹最优调参结果，未知轨迹上的收益和安全阈值尚未验证。
- **局限 3**：页面访问采样忽略采样周期内的重复访问，限制了频率敏感策略和指标。
- **后续工作 1**：构建带置信区间的离线 MPC 到在线 promotion-rate 预测模型，并在多个应用、不同运行速度和不同扫描周期上验证覆盖率。
- **后续工作 2**：把迁移成本、CXL/SSD 异构延迟和多租户资源竞争加入目标函数，比较 promotion rate、PSI 与 STAR 约束下的最优策略。
- **后续工作 3**：用时间分离的训练/测试轨迹评估 PACE 与 L-OPP，并测试跨工作负载特征迁移，而不是为每个应用单独拟合。

## 相关

- **相关概念**：[[Memory Reclamation]]、[[Memory Tiering]]、[[Miss Ratio Curves]]、[[Working Set]]
- **同类系统**：[[TMO]]、[[g-swap]]、[[FlexMem]]
- **同会议**：[[OSDI-2026]]
