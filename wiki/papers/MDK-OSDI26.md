---
type: paper
name: MDK
full_title: "MDK: Rethinking the data center memory reclamation problem"
authors: [Shaurya Patel, Suli Yang, Yawen Wang, Kan Wu, Alexandra Fedorova, Margo Seltzer, Kimberly Keeton]
venue: OSDI
year: 2026
tags: [memory-reclamation, datacenter, performance-modeling, cache-policy, linux]
source_pdf: "[[osdi26-patel.pdf]]"
source_md: "[[osdi26-patel]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 重新定义数据中心内存回收的设计工具

> **原题**：MDK: Rethinking the data center memory reclamation problem

## 一句话总结

MDK 指出数据中心 proactive reclamation 是“在每个 SLO window 满足性能上限时最大化平均内存节省”，与固定 cache 下最小化 miss ratio 的传统问题相反；它提供最优 OPP、Memory Performance Curve 和最多快 208 倍的曲线生成器，并据此设计出最多多省 10% 内存的新策略。

## 问题与动机

传统 page replacement 在内存已满时被动 eviction，目标是在固定 capacity 下最小化全生命周期 miss ratio。数据中心为放置更多 job，会在尚无 pressure 时主动把 cold page 降到 [[CXL|CXL]]、compressed memory 或 SSD；目标变成最大化可持续 memory savings，约束则是在每个 10 s/2 min measurement window 不违反 application SLO proxy。

这次“目标—约束翻转”使传统工具失效。Belady OPT/VMIN 可能把未来 fault 聚集在同一 window，虽然总 miss 少却违反 promotion-rate SLO；MRC 以 cache size 为横轴也无法表达 variable-size proactive policy。没有 optimal bound、统一 tradeoff curve 与快速 evaluator，就难以判断 AGE 等生产策略还有多少 headroom。

## 关键观察 / 隐含假设

### 关键观察

- 数据中心性能是按 window 执行 SLO，故总 miss ratio 不能替代 per-window constraint。
- Google promotion rate（非 compulsory fault / window 内 unique pages）可由 PTE access bit 统一测量，并与 Cassandra tail latency 正相关。
- 最优 policy 不应只看 next reuse distance；还必须预算 next-access window 剩余可允许 promotion 数，并把 fault 分散到时间上。
- 若更 aggressive parameter 包含较温和 parameter 的 eviction decision/time，可像 MRC inclusion property 一样一次 trace 生成整条 tradeoff curve。

### 隐含假设

- page 大小统一，30 s access-bit sampling 足以表达 promotion rate；同 window 内重复访问不重要。
- promotion cost 相对均匀；若 tier latency 异构，PSI/STAR 等 proxy 可能更合适。
- offline trace 能代表未来 workload；作者的 PAW/PACE 最佳参数使用 evaluation trace，本身是潜力上界。
- 平均 memory savings 能转化为 scheduler 可使用的长期 capacity，而非短暂碎片。

## 核心方法

### 内存性能曲线

MPC 横轴是 target performance proxy（本文为 promotion rate），纵轴是 memory optimization target（average savings）。由于 policy parameter 到这两个量不是 surjective，图以 scatter 而非连线，避免暗示不可达 operating point。它用于回答“容忍 1%→2% promotion 能多省多少内存”和“相同 constraint 哪个 policy 更好”。

### 最优性能代理策略

OPP 是 two-pass offline policy。第一遍计算每 window 的 unique page count `U_w`；第二遍在每次 access 后考虑立刻 reclaim page，并查看其 next access 所在 window `B`。只有加入该 page future fault 后 `F_B/U_B` 不超过 target，才回收并增加 `F_B`。因此 OPP 在不超预算的前提下尽早 reclaim，最大化 page-size×reclaimed-duration 的平均 savings；附录证明 optimality。

OPT 与 VMIN 只优化 total/future distance，可能在同一 window 产生 100% promotion，超过示例 50% target；OPP 会在多个将于同一 window 重用的 page 中保留足够数量，明确把 performance constraint 作为一等资源预算。

### 理论性质与快速生成

Eviction Decisions property：更 aggressive parameter 的 eviction sequence 包含温和 parameter sequence。Eviction Times property 更强：共同 eviction 还发生在同一时刻。对每次 access，生成器只计算最温和但会导致该 fault 的 critical parameter，并记录对应 savings；随后按 aggressiveness prefix-sum promotions/savings，单遍构造所有 parameter point。

policy 只需实现 parameter space/order、critical parameter、memory savings、accumulation 等少量函数；single-parameter implementation 少于 87 LoC。AGE 不满足同时间 property，需自定义 savings accumulation；PACE 展示两参数也可专门扩展。

## 新策略

- AGE：等待 page 未访问超过 age 后回收，保守但适合不可预测 workload。
- PAW（Prior Age with Wait）：利用历史 reuse distance，在 access 后更早决定回收；重复 pattern 下优于 AGE，无 pattern 时可能明显更差。
- PACE（Prior Age and Current Elapsed）：结合 prior reuse 与当前 elapsed，两参数空间包含 AGE 行为，最佳配置按构造不差于 AGE。
- L-OPP：以 OPP decision 为 label，用 6 个历史 reuse distance 训练 gradient-boosted tree；展示 optimal oracle 可直接生成 imitation policy，但低 precision 会违反 target。

## 实验与结果

MDK 是 C++ simulator/library。Linux 5.10 kernel thread 每 30 s 扫 PTE access bit、记录 page ID/window 并清 bit；评估 CloudSuite/DCPerf 8 个 workload。Linux end-to-end 以 SSD swap、关闭 hugepage。

- MPC 与逐配置 simulation 的 average savings/promotion mean absolute error 均少于 1%。
- 对最慢的 OPP，MDK 全曲线比串行模拟 10 个 parameter 快 12.5–208 倍；前者 linear，后者随配置数呈 quadratic work。
- Cassandra 在 1% promotion target 下 OPP 可省 40% 内存，而 VMIN 即使容忍 10% 仍达不到，显示传统 optimal 不对应新问题。
- PAW 在 GraphX、NGINX、TaoBench 等重复型 workload 比 AGE 最多多省 10%，但 Memcached/FeedSim 等不可预测 workload 中 AGE 更好。
- PACE 最佳配置通常多省 1–4%，Cassandra/GraphX 达 8–10%；该结果在同 trace 选参，存在 overfitting。
- Linux GraphX PageRank 中 PAW 相对 AGE 多省 4% 且性能无损；两者实测 promotion 约 1.5%，低于 offline 预期 4%，因实际 runtime 改变 window alignment。
- L-OPP 在 DjangoBench 略优于 AGE且维持约 1% promotion；TaoBench/FeedSim 因 model precision 低产生过高 promotion。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 传统 OPT 不适用于 windowed reclamation | 表 1/图 4：OPT、VMIN 聚集 fault 并违反 target，OPP 不违反 | 在本文 promotion-rate formulation 下成立 | 强 |
| OPP 给出有意义 upper bound | Cassandra：1% target 下省 40%，显著高于 VMIN/AGE | 需要完整未来 trace，不能直接部署 | 强 |
| MDK 可快速准确生成 MPC | 与 simulation 误差少于 1%，快 12.5–208 倍 | 依赖 policy 满足性质；目前主要是整数参数 | 强 |
| optimal insight 可导出实际策略 | PAW/PACE offline 最多多省 10%；PAW Linux 多省 4% | online parameter tuning 未解决，收益依赖 predictability | 强 |
| offline MPC 与真实系统仍有差距 | GraphX 实测 promotion 1.5% 而预期 4% | runtime/window shift 需要 confidence/self-tuning | 强 |
## 批判性分析

### 论证链条

论文的核心价值是纠正 problem formulation，而不仅提出一条 eviction heuristic。OPP、MPC、policy property 和 generator 形成完整 designer workflow：先看 optimal headroom，再快速比较 idea，最后部署验证。作者也明确区分 offline potential 与在线可实现性，并报告 PAW 在不规则 workload 中失败、L-OPP 违反 target 等负面结果。

### 假设压力测试

- 本文只完整解决 average savings + promotion rate；PSI、STAR、tail memory、variable fault cost 虽宣称可泛化，却需要新的 model/optimal policy。
- trace 每 30 s 只记录 unique accessed page，无法评估 frequency-aware policy，也忽略同 window repeated promotion。
- PACE 最佳参数在同一 evaluation trace 调优，8–10% 是 oracle-tuned upper bound，而非可部署收益。
- OPP 的 exact timestamp 版本在附录只给 bounded-gap 讨论，window discretization 对 optimality 至关重要。
- 单 application trace 忽略多 tenant contention、shared tier bandwidth 与 cluster scheduler coupling。
- Linux case study仅一个 GraphX workload，且 offline promotion prediction 明显偏离实测。

### 实验可信度

8 个 workload、simulation accuracy、generator speed 和一个 Linux end-to-end case 形成分层验证；但可部署策略收益多为同 trace oracle tuning，真实系统证据仍只有 GraphX。

## 局限与后续工作

- **局限**：完整工具目前围绕 average savings 与 promotion rate，offline trace 对 online window 的预测会漂移。
- **后续工作**：应加入 self-tuning/confidence bound，并扩展 PSI、STAR、multi-tenant 与多参数策略。

后续应把 MPC generator 放入 Senpai 类 online tuner；为 trace/runtime shift 给出 confidence bound；扩展 PSI/STAR、tail memory 与 heterogeneous tier cost；支持 hugepage/variable page size 和 multi-parameter generic generator；用 production multi-tenant trace把 savings 映射为新增 job placement；并训练跨 workload、可校准 constraint violation risk 的 learned policy。

## 相关概念

- [[Memory-Reclamation]]
- [[Memory-Tiering]]
- [[Working-Set]]
- [[Cache-Replacement]]
- [[Datacenter-Resource-Management]]
