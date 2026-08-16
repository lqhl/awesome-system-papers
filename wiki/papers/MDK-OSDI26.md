---
type: paper
name: MDK
full_title: "MDK: Rethinking the data center memory reclamation problem"
authors: [Shaurya Patel, Suli Yang, Yawen Wang, Kan Wu, Alexandra (Sasha) Fedorova, Margo Seltzer, Kimberly Keeton]
venue: OSDI
year: 2026
tags: [memory-reclamation, datacenter, performance-modeling, cache-policy, linux]
source_pdf: "[[osdi26-patel.pdf]]"
source_md: "[[osdi26-patel]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 数据中心内存回收策略设计工具（OSDI 2026）

> **原题**：MDK: Rethinking the data center memory reclamation problem

> **一句话总结**：MDK 把数据中心主动回收重新表述为“在每个观测窗口都不超过性能代理上限时，最大化平均内存节省”，并提供 Memory Performance Curve、离线 oracle OPP、两条可加速曲线生成的单调性质和一个比逐配置模拟快 12.5–208 倍的 generator；它帮助 PAW/PACE 在部分 trace 上比 AGE 多省最多 10% 内存，但 OPP 的严格最优性只适用于 PTE access-bit trace 把窗口内访问视为同一时刻的模型，论文附录明确证明精确时间戳下它并不最优。

## 问题与动机

传统 page replacement 的前提是内存容量固定：内存满了才被动 eviction，目标是在这个容量下减少整个运行期的 cache miss。数据中心的目标反过来：为了在 server 上再放 job，系统在没有 memory pressure 时也主动把 cold page 移到 compressed memory、SSD 或 [[CXL]] tier；它要尽量节省 DRAM，同时让每个 10 秒或数分钟的 SLO window 都不过度伤害应用（§1、§2.1）。

这不是换一个 eviction heuristic 就能解决的问题。传统 OPT/VMIN 最小化总 miss，却可能把多个 future fault 集中到同一 window，违反 promotion-rate SLO。Miss Ratio Curve（MRC）以固定 cache size 为自变量，也不能表达“容量随时间变化、performance proxy 是约束、memory savings 是目标”的 proactive policy（图 4、表 1、§2.5）。

论文聚焦一个具体 formulation：最大化 **average memory savings**，约束每个 `T_proxy` window 的 **promotion rate** 不超过 target。promotion rate 采用 g-swap 定义：该窗口内 non-compulsory fault page 数除以 unique accessed page 数。作者用 Cassandra/YCSB 测到 promotion rate 越高，tail latency 也越高（图 3）；但 PSI、STAR、tail memory、异构 fault cost 等其他合理 formulation 只讨论了扩展方向，没有实现。

MDK 是离线策略设计工具，不是线上 reclamation daemon。它要回答四个问题：理论 headroom 多大、怎样画统一 tradeoff、哪些 policy 能一次 trace 算完整曲线，以及 oracle insight 能否导出实用策略。

## 关键观察 / 隐含假设

- **观察 1：数据中心 SLO 是逐窗口约束，生命周期总 miss 不能代替它。** OPT/VMIN 可拥有较少总 fault，却在某个 window 达到 100% promotion；一个 policy 必须把 future fault budget 当作每个 window 的一等资源（表 1、图 4、§3.2.1）。
  - **依赖假设**：promotion rate 与应用 SLO 有稳定关系，且每个 promotion 的成本大致相同。
  - **可能失效场景**：SSD、compressed memory 与 CXL 的 fault/access cost 相差很大时，同一个 promotion ratio 不能表示实际 stall；PSI 或 STAR 更合适。
- **观察 2：在同一 future window 内，应优先更早 reclaim、因而能保存更久的页面。** OPP 给每个 window 预算可产生的 fault 数，并在不超预算时尽早回收；这是它最大化 average savings 的关键（§3.2.2、附录 C）。
  - **依赖假设**：trace 只有 access-bit scan window，窗口内所有 access 被视为同时发生。这样，同一 future window 的不同 page 有相同 next-access time。
  - **可能失效场景**：精确时间戳下，同一 window 后段才访问的 page 可能比前段 page 产生更多 savings；贪心 OPP 会过早用掉 fault slot。附录 D 的反例中 OPP 保存 100，最优保存 170。
- **观察 3：若 aggressive 参数包含所有温和参数的 eviction decision，完整曲线可以做 prefix accumulation。** 若共同 decision 还发生在同一时间，memory savings 也能直接累加；这分别是 eviction-decisions 与 eviction-times property（图 5、§3.3）。
  - **依赖假设**：policy 参数有明确 aggression order，且至少满足 decision property。learned policy、任意多参数 policy 不一定满足。
- **观察 4：optimal oracle 的价值是揭示 headroom，不是直接部署。** 图 7 中 OPP 与 AGE 的巨大距离提示“等待 page 变冷”太保守，由此产生 access 后更早回收的 PAW/PACE（§5.4）。
  - **依赖假设**：历史 reuse distance 对未来有预测力；Memcached、FeedSim 等无重复 pattern 的 workload 已显示 PAW 会明显输给 AGE。
- **假设 1：offline trace 可以指导未来 online 参数。** PACE 的最佳 `(P,A)` 用同一 evaluation trace 选择，展示的是 oracle-tuned upper bound；实际 unseen phase 的选参问题没有解决。
- **假设 2：平均节省会变成可调度容量。** cluster scheduler 通常要求 savings 至少持续数分钟才能放新 job，MDK 的 average savings 没有直接编码持续性、碎片或多 tenant 合并效果。

## 核心方法

### 1. 内存性能曲线（Memory Performance Curve，MPC）

MPC 横轴是 performance proxy，本文为 promotion rate；纵轴是 memory objective，本文为 average memory savings。它回答“允许 1% 而不是更低 promotion，可多省多少内存”或“同一 constraint 下哪个 policy 更好”（§3.1）。

policy parameter 同时决定横纵两个量，因此不是每个中间点都可达。MDK 用 scatter 而不连线，避免把两个可行 configuration 之间的空白误画成可选 operating point。纵向 cliff 表示几乎不增加 promotion 就能多省内存，横向 plateau 表示再放宽 SLO 也没有 savings（图 7、§5.4.1）。

### 2. OPP：按 future window 分配 fault budget

Optimal Performance Proxy（OPP）是 two-pass offline algorithm。第一遍统计每个 window 的 unique access 数 `U_w`；第二遍在每个观测窗口结束、处理本窗口被观察到的 page 时，查看它下一次访问落入的 window `B`。若把该 page 回收后，`B` 中已预留 fault 加一仍不超过 `target × U_B`，就立即 reclaim，并占用 `B` 的一个 fault slot；否则保留 page（§3.2.2）。

它与 VMIN 的差别不只是看 next reuse distance：多个 page 将在同一 window 重新使用时，OPP 只选择预算容许的一部分，把 promotion 限制逐 window 保住。因为 average savings 与 page 留在 DRAM 外的时间成正比，access-bit trace 模型下尽早 reclaim 是最佳选择。

### 3. “最优”结论的严格边界

附录 C 的 first-difference proof 假定 access-bit collector 只能知道一个 page 在某个 scan window 被访问，并把 window 内所有 access 都放在 window start。此时同一个 future window 的候选有同一 next-access time，先做的合法 eviction 至少和后做的一样省，所以 greedy OPP 可交换成任意最优 schedule 而不减 savings。

附录 D 放开这一假定后直接给出反例：两个 page 都在 window 2 重用，fault budget 只有 1；OPP 在 `t=10` 回收 A、`t=110` fault，省 100，而真正最优应在 `t=20` 回收 `t=190` 才访问的 B，省 170。论文只证明 OPP 与精确时间戳最优的总 gap 小于 `F_total × window_size`，不再是 exact optimum。

### 4. 两条性质与 MPC generator

对 control parameter `R`，MDK 把 eviction 记成 page sequence 和 `(page,time)` sequence（§3.3）：

- **Eviction decisions**：更 aggressive 的参数包含温和参数做出的所有 eviction。
- **Eviction times**：这些共同 eviction 还在同一时刻发生；它比 decision property 更强。

generator 对每个 access 只计算“最温和但会让它 fault”的 critical parameter，把 promotion 与该 eviction 的 savings 记在那里；随后按 aggressiveness 顺序做 cumulative sum，即可一次 trace 得到完整 MPC（Listing 1、§3.4）。VMIN/OPP 同时满足两条性质；AGE 只满足 decision property，必须自定义 savings accumulation，因为 aggressive age 会更早 evict。

single-parameter policy 要实现参数空间、aggression order、critical parameter、memory saving 与 accumulation 等五个函数，论文实现均少于 87 LoC。当前 framework 只支持 integer control parameter；PACE 是专门写的二维 suffix-sum generator，不是通用多参数框架。

### 5. 用 oracle insight 设计三种 policy

- **PAW（Prior Age with Wait）**：若上一次 reuse distance 超过阈值 `P`，并且当前 access 后已等 1 分钟，就 reclaim。它比 AGE 更早，又用短 wait 保护高频 page。
- **PACE（Prior Age and Current Elapsed）**：若 prior age 大于 `P` 就立即 reclaim，否则等当前 idle time 达到 `A` 再 reclaim。`P=∞` 时退化为 AGE，所以同 trace 选到最佳 `(P,A)` 时按构造不会比 AGE 差（Listing 2）。
- **L-OPP**：用 OPP 2% target 的 decision 作 label，以最近六个 reuse distance 训练 gradient-boosted tree。每 workload 单独训练，前 80% train、后 20% validation，再用第二次运行的 trace 测试；first-use page 回退 AGE（§5.4.2）。

### 6. Trace 与 Linux 验证路径

Linux 5.10 kernel thread 每 30 秒扫描 PTE accessed bit，记录 page ID 与 period，再清 bit。应用全部驻留 DRAM、关闭 hugepage。这个格式只知道一个 page 在 period 内“至少被访问一次”，不知道频率和精确时间；它正好符合 OPP proof，却不适合 frequency-aware policy（§4）。

MDK 用 C++ simulator 覆盖 LRU、OPT、VMIN、AGE、PAW、PACE、L-OPP、OPP，并为 AGE、OPP、VMIN、PAW、PACE 实现 generator。线上 case 只把 AGE 与 PAW 放入 Linux，用 SSD swap 验证一个 GraphX PageRank workload。

## 设计取舍

- **可证明模型换时间精度。** access-bit window 让 OPP 可精确最优，也符合现有低成本 telemetry；代价是丢掉窗口内顺序和重复访问。
- **统一 proxy 换硬件差异。** promotion rate 易从 PTE 观测，却假定 fault cost相近；它不能直接代表不同 CXL、compressed memory、SSD 的 stall。
- **exact curve 换 policy 限制。** 单调性质能在线性时间生成精确 MPC，但不满足性质的 learned/复杂策略仍要 simulation。
- **offline oracle 换部署可行性。** OPP、VMIN 和 PACE 最佳配置都使用 future 或完整 trace，只能当 headroom，不是 online result。
- **平均 savings 换 placement 语义。** 这个指标不关心 savings 是否连续至少五分钟、是否形成可用的大块容量，也不含 migration traffic。
- **简化页模型换现实特性。** uniform 4 KiB page、关闭 hugepage、单应用 trace 避开 THP、共享页、variable object size 和多 tenant tier contention。

## 实验设置

- 八个 workload 来自 CloudSuite 与 DCPerf：GraphX、NGINX、Memcached、Cassandra、DjangoBench、TaoBench、MediaWiki、FeedSim（表 2、§5.1）。trace 与 Linux case 在 E5-2696、256 GB、Linux 5.10 上收集；generator/simulator benchmark 在 64-core EPYC 7B13、128 GB 上运行。
- PTE 每 30 秒扫描一次，hugepage 关闭。simulation 以十个 one-parameter setting 比较；PACE 比较十五个 setting。generator speedup baseline 是这些 setting **串行**运行，作者说明平行 simulation 可以缩短 wall time。
- offline PAW/PACE 直接在 evaluation trace 选最优参数；L-OPP 才分 training/validation，并用同 workload 第二次 execution 测试。Linux end-to-end 只测 GraphX PageRank 与 SSD swap。

## 实验与结果

- **MPC 准确性**：AGE、OPP、VMIN、PAW、PACE 的 generator 与逐配置 simulator 相比，average savings 和 promotion rate 的 mean absolute error 都不超过 1%；差异来自 rounding（§5.2）。
- **生成速度**：最慢的 OPP 需要两遍 trace，但完整 MPC 仍比串行模拟十个参数快 12.5–208 倍。两者都随 page access event 数增长，论文把 generator 称为 linear、逐 setting simulation 总工作称为 quadratic；比较没有使用 parallel simulation（表 2、§5.2）。
- **OPP headroom**：在 Cassandra 1% promotion 下，OPP average savings 达 40%，VMIN 即使到 10% promotion 也达不到；GraphX 中 AGE 最 aggressive 也不超过约 10%，而 OPP 曲线约为 30%–40%。FeedSim/MediaWiki 的 OPP 则较平，说明不是所有 workload 都能靠放宽 target 多省内存（图 7、§5.4.1）。
- **PAW 与 PACE**：PAW 在 GraphX、NGINX、TaoBench 等有重复 pattern 的 workload 比 AGE 最多多省 10%，但在 Memcached、FeedSim 等不规则 workload 明显更差。PACE 的 same-trace 最佳点在多数 workload 多省 1%–4%，Cassandra/GraphX 多省 8%–10%；这是 oracle-tuned upper bound，不是 unseen trace result（图 7、§5.4.2）。
- **L-OPP 的正负结果**：第二次 execution trace 上，L-OPP 在 DjangoBench 比 AGE 略好、在 MediaWiki 低于 AGE但优于 PAW，两个展示点约维持 1% promotion。TaoBench/FeedSim 因 offline precision 低而产生过高 promotion，结果被正文省略；这证明 OPP label 可用于训练，不证明 learned policy 已可部署（图 8、§5.4.2）。
- **Linux GraphX**：PAW 的平均内存使用为 `9.11±0.84 GB`，AGE 为 `9.52±0.27 GB`，运行时间 16.9/17.1 分钟，PAW 约多省 4% 且无可见性能损失；但两者实际 promotion 约 1.5%，远低于 offline 选择参数时预期的 4%，因为 runtime 改变了 window alignment（表 3、§5.4.3）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 传统 OPT/VMIN 不是逐窗口 reclamation 问题的最优解 | 表 1、图 4：二者在单 window 聚集 promotion，OPP 保持 target | 只针对 average savings + promotion rate formulation | 强 |
| OPP 提供该 trace 模型下的可证明 upper bound | 附录 C first-difference proof；图 7 始终高于其他 policy | 只对 windowed access-bit trace exact；精确时间戳有 100 对 170 的反例 | 强但边界窄 |
| 两条 eviction property 可准确、快速构造 MPC | generator MAE 不超过 1%，相对十 setting 串行 simulation 快 12.5–208 倍 | integer/少量参数、满足 decision property 的 policy；baseline 未并行 | 强 |
| oracle headroom 能启发更好的 practical heuristic | PAW/PACE 部分 workload 多省最多 10%；Linux PAW 多省约 4% | PACE same-trace 选参；Linux 只测一个 GraphX workload | 中 |
| offline MPC 不能直接预测 online operating point | GraphX 实际 promotion 约 1.5%，预期 4%；无性能损失但 window 对不齐 | 单个 end-to-end case，没有在线 self-tuning | 强 |

## 批判性分析

### 论证链条

论文最强的贡献是重新定义问题，而不只是再给一条 page heuristic：传统目标/约束翻转后，OPP 给 headroom，MPC 给 tradeoff，property/generator 降低试错成本，PAW/PACE/Linux case 展示 workflow。链条总体完整。标题和摘要的“provably optimal”如果不读附录会被过度理解；严格说，它是对论文 30 秒 access-bit trace abstraction 的 optimal policy，精确 access trace 下只是有 bounded gap。这一限定应成为所有 OPP headroom 解释的前提。

### 假设压力测试

promotion cost 不均匀时，保留一个 SSD fault 与保留一个 CXL access 的价值不同，按 fault 数分 budget 会作出错误选择。窗口从 30 秒改到 10 秒或 2 分钟，会同时改变 `U_w`、fault clustering、reuse distance 和 optimal schedule。job phase 与 trace 不同，PAW/PACE 的 reuse 参数会漂移；PACE 有两个参数，same-trace 10% 增益尤其容易 overfit。多 tenant 共享 bandwidth、swap device 或 CXL pool 时，即使每应用 promotion 都合规，总体仍可能 overload。

### 实验可信度

八个真实 benchmark、多个 policy、simulator cross-check、runtime benchmark、正负 learned result 与一个 Linux case，使 MDK 作为离线 toolkit 的证据充分。作者也披露 parallel simulation、same-trace tuning 和 online/offline promotion mismatch。可部署结论仍很弱：Linux 只有 GraphX，关闭 hugepage，只用 SSD，未报告 trace collector overhead、tail latency 数值、重复次数或 production workload。图 7 的 oracle curve 不能当 online policy throughput。

### 系统性缺陷

MDK 不负责从 curve 选择线上参数、检测 phase change、给 confidence bound，或把 savings 交给 cluster scheduler。30 秒 PTE walk 对 256 GB/更大内存的 CPU 与 cache 开销未测；清 accessed bit 也会影响其他 reclaim/[[NUMA|NUMA]] mechanism。single-application trace 没有共享页、容器迁移和共同 tier pressure。framework 当前只支持 integer one-parameter policy，PACE 要约 300 LoC 特化，L-OPP 又退回 simulation，说明“新 policy 少量函数即可加入”的接口并不普遍。

## 局限与后续工作

- **局限 1**：OPP exact optimality依赖窗口内同时访问假设；精确时间戳只保证 gap bound。
- **局限 2**：完整实现只覆盖 average savings + promotion rate；PSI、STAR、tail memory 和异构 cost 尚无 model 或 optimal policy。
- **局限 3**：PAW/PACE 参数依赖 workload，PACE 结果用同 trace 调参与评测；没有在线 tuner。
- **局限 4**：Linux 只测 GraphX、SSD、4 KiB page；实际 promotion 与 offline MPC 明显不一致。
- **后续工作 1**：对 exact timestamp、不同 page/fault cost 求真正 weighted optimal schedule，并与 OPP 的 bounded-gap 实测比较。
- **后续工作 2**：把 MPC generator 接入 online tuner，按窗口输出 promotion confidence interval、参数变更和 SLO violation rate。
- **后续工作 3**：在 THP、CXL、compressed memory、SSD 上实现同一 workload，对 promotion rate、PSI、STAR 与 tail latency 的相关性做校准。
- **后续工作 4**：用 production multi-tenant trace验证 durable savings、tier bandwidth 和 cluster placement，报告实际新增 job 数而不只 average GB。

## 相关

- **相关概念**：[[CXL]]、memory reclamation、cache replacement、working set
- **相关方法**：OPT、VMIN、AGE、OPP、PAW、PACE
- **同会议**：[[OSDI-2026]]
