---
type: paper
name: LEOCraft
full_title: "LEOCraft: Towards Designing Performant LEO Networks"
authors: [Suvam Basak, Amitangshu Pal, Debopam Bhattacherjee]
venue: ATC
year: 2025
tags: [networking, leo-satellite, simulation, optimization, constellation-design, flow-level-simulation]
source_pdf: "[[atc2025-basak.pdf]]"
source_md: "[[atc2025-basak]]"
---

# LEOCraft: Towards Designing Performant LEO Networks (ATC 2025)

> **一句话总结**：LEOCraft 把 [[LEO-Satellite-Network]] 设计问题的核心假设压成「24 小时动态波动小、需求地理分布可预测、+Grid 拓扑参数可被规则剪枝」，用 flow-level 模型、process 级并行和 [[Variable-Neighborhood-Search]] 在 3 维参数上搜索，使星座优化约 5x 快于黑盒 metaheuristic，并能评估 3,888 颗卫星约 2.5 分钟、扩展到 83K 卫星 + 1K ground stations。

## 问题与动机

论文关心的不是单条 [[Satellite-Network]] 路由协议，而是更上游的 constellation design：给定卫星预算、ground station 位置和 traffic demand matrix，如何选择 shell 数量、轨道高度 h、倾角 i、最低仰角 e、轨道数 o、每轨卫星数 n、相邻轨道 phase offset p，使吞吐、覆盖和延迟更好。这个问题在 [[Starlink]]、[[Kuiper]]、[[OneWeb]] 进入千到万颗卫星规模后变得像一个真正的 network design problem，而不是 1990s 那种几十颗卫星的几何覆盖优化。

现有公开工具卡在两个地方。[[Hypatia]] 是 packet-level / ns-3 路线，适合看协议细节但大规模慢；[[StarryNet]] 用 Docker container 和 Python thread 模拟节点，受容器数量和 [[CPython-GIL]] 影响；xeoverse 声称更快但不开源。LEOCraft 的定位是补一个开源、flow-level、可批量跑设计空间的工具，让研究者能在 operator 黑盒之外探索「为什么某个星座长这样」。

论文的设计目标也很清楚地收窄到 throughput-first。作者承认 constellation operator 可能有覆盖、极区、maritime、aviation、低延迟、碰撞风险等多目标，但本文主要把 throughput 作为可销售带宽和 revenue proxy。这让问题变得可计算，也让结论的外推需要很小心：LEOCraft 证明的是某组模型下的设计趋势，不是所有商业 LEO 网络的全局最优设计。

## 关键观察 / 隐含假设

- **观察 1**：在 Starlink 第一 shell 的 24 小时、5 分钟粒度仿真里，coverage 基本稳定，throughput 周期性波动约 150 Gbps，约为最大吞吐的 7%，论文总结为 LEO dynamics 带来的性能波动在 6.5% 以内；stretch 小幅波动，hop count 通常最多变 2 跳。
  - **依赖假设**：优化目标是 day-level 平均或稳态性能，而不是 handoff 时刻的 tail latency、packet loss、route churn 或短时间 SLO。
  - **可能失效场景**：如果 workload 对秒级抖动敏感，或者 routing / transport 层受到 handoff、queue buildup、packet reordering 影响，那么「忽略时间维度」会把关键风险折叠掉。

- **观察 2**：作者把 6 个单 shell 参数分成影响 coverage 的 GROUP-I（h, i, e）和主要改变 topology 的 GROUP-II（o, n, p）；当 h / i / e 接近较优区域时，足够大的 constellation（论文给出 >= 300 satellites）里 larger o、o >> n、p = 0.5 通常提升 HG route path diversity 和 throughput。
  - **依赖假设**：默认 [[ISL]] 是 +Grid，每颗卫星 4 条 ISL，routing 使用 20 shortest paths，throughput 用 [[Multi-Commodity-Flow]] LP 计算；这些建模选择会偏好路径多样性。
  - **可能失效场景**：换成 [[XGrid]]、动态 ISL selection、不同 k-shortest routing、对 collision risk 或 control-plane churn 加惩罚后，o >> n 与 p = 0.5 未必仍是主导结论。

- **观察 3**：需求具有强地理偏置。对 100 个高人口城市，throughput 和 coverage 在约 40° inclination 附近达到高点；作者还用 100 大城市纬度中位数 29.6° 作为 VNS 初始解的 intuition，并在 appendix 里说明 high-population、GDP-weighted、capital、flight TMs 的趋势大体一致。
  - **依赖假设**：ground station 可以用城市 proxy 表示用户需求，且 demand matrix 的 gravity model 足以代表真实市场。
  - **可能失效场景**：maritime、polar service、military、enterprise backhaul、in-flight Wi-Fi 等目标市场会把需求移到海洋、极区或航线走廊，最优 inclination / elevation 可能改变。

- **假设 1**：GSL 是主要瓶颈，且可以用 Shannon + FSPL、Ka-band FCC 参数、visible satellites 平均分配 bandwidth 来近似。
  - **证据强度**：中。论文的 ISL utilization 可视化显示很多 ISL 未用或低利用，支持 GSL bottleneck 的方向；但真实系统有 beam scheduling、frequency reuse、terminal association、weather fading 和 interference mitigation，论文明确未建模 interference。

- **假设 2**：flow-level simulation 足以给 constellation design 排序。
  - **证据强度**：中。LEOCraft 的 computed RTT 与 Hypatia ping 在三组 GS pairs 上接近，说明几何路径和传播延迟模型有 sanity check；但 throughput claim 依赖 LP 和 traffic matrix，不覆盖 congestion control、packet loss、handover protocol 或 failure recovery。

## 核心方法

LEOCraft 的输入是每个 shell 的 s, o, n, h, i, e, p 以及 GS locations 和 traffic matrix。它自动生成 TLE，把 constellation 建成 graph：nodes 是 satellites 和 ground stations，edges 是 [[GSL]] 与 [[ISL]]。GSL capacity 来自 FSPL + Shannon capacity，ISL capacity 默认 50 Gbps，且可配置。

性能指标分三类。Throughput 被建模成 ground-station pairs 之间的 [[Multi-Commodity-Flow]]：对每个 flow 用 [[Yen-k-Shortest-Paths]] 取 n = 20 条路径，再用 LP 决定每条路径承载多少 demand，同时约束每条 link capacity。Latency 用 stretch 近似，即 satellite path distance / geodesic distance，并按 LG、HG、NS、EW、NESW 五类路由报告 median stretch 和 hop count。Coverage 用每个 GS 可见 satellites 数量的 log 聚合，体现边际收益递减。

搜索策略先用大量单维实验找 shape，而不是直接丢给黑盒优化。作者得到 5 个 takeaway：LEO dynamics 小幅周期波动；h 太低覆盖不足、太高 GSL 变长且 bandwidth 被更多 GS 分享；i 应匹配 GS 纬度和路由方向；e 太低会产生 over-the-horizon GSL 和巨大 path loss、太高会带来 coverage gap；o / n / p 控制 +Grid mesh 形状，在大 constellation 中 o >> n 且 p = 0.5 通常更好。

基于这些 observation，LEOCraft 把搜索从 6 维剪到 3 维：固定 o 为最大值、p = 0.5，让 n 由 satellite budget 和 o 决定，然后只优化 h, i, e。优化器使用 [[Variable-Neighborhood-Search]]，每轮随机 step size，初始点取 i 约 30°、e 在 10-20°，以贴近人口分布和低 elevation 的 path diversity。

系统实现上，LEOCraft 的关键是把 satellites、GSes、routes、evaluation functions 变成独立 block，通过 process pool executor 分发到多个 CPU。这个设计绕过 [[CPython-GIL]]，也避免把整个 constellation 当成一个 monolithic simulator。它牺牲 packet-level fidelity，换来能在 commodity workstation 上批量跑 constellation designs。

## 设计取舍

- **Flow-level 而非 packet-level**：收益是能跑几千到几万颗卫星的 design exploration；代价是看不到 packet drops、handoff disruption、TCP dynamics、queueing 和 failure behavior。
- **Throughput-first objective**：收益是 LP 目标清晰，结果能直接对比；代价是覆盖公平性、tail latency、collision risk、极区服务、deployment cost 等目标被放到次要位置。
- **Domain-knowledge pruning**：收益是把优化从 h/i/e/o/n/p/t 大空间收缩到 h/i/e；代价是把 +Grid、p = 0.5、o 最大化这些经验结论固化进搜索器，可能错过不符合该结构的拓扑。
- **Ground-station proxy demand**：收益是没有真实 Starlink 用户位置也能跑；代价是真实 user terminal association、beam capacity、移动用户和市场策略都被简化成城市级 gravity model。
- **Inter-shell ISL**：收益是多 shell 吞吐接近 single dense shell；代价是不同 altitude 的 orbital period 会让 phase offset 漂移，需要周期性 handoff 来维持 inter-shell topology。

## 实验与结果

- Starlink Gen1 三个 shell、3,888 颗卫星的 performance evaluation 在普通 desktop PC 上约 2.5 分钟；作者对比称 [[Hypatia]] 仅测 Starlink 单 shell 1,584 颗卫星 RTT 就需要数小时。
- 搜索剪枝后，SA、DE、A-PSO、VNS 的平均运行时间分别降低约 2.1x、4.2x、2.2x、13.7x；带 domain knowledge 的 VNS 比剪枝后的最快 metaheuristic 平均快约 2.2x，比 naive approaches 平均快约 4.9x。
- 优化质量没有明显牺牲：3,888 颗卫星场景下，各优化器得到的 throughput 标准差约 ±60 Gbps，NS route median stretch 差异在 0.3 内，作者认为小于 LEO dynamics 自身波动。
- 单 dense shell 对 throughput 更好：Starlink 三 shell 分别优化约 7.5 Tbps，合并成 3,888 颗的 single shell 约 8 Tbps；Kuiper 三 shell 分别优化约 6.6 Tbps，合并 single shell 约 7.4 Tbps。
- Inter-shell ISL 可弥补 sparse multi-shell 的吞吐损失：Starlink / Kuiper 三 shell 加 inter-shell links 后约 8.01 / 7.34 Tbps，接近 single dense shell；但两 shell / 三 shell 需要约 13 / 4 小时一次 handoff 来维护拓扑。
- 与 [[Hypatia]] 的 RTT sanity check 中，LEOCraft computed RTT 与 Hypatia ping 接近；在 synthetic single-shell latency benchmark 中，LEOCraft 比 Hypatia 快约 1.7-54.5x，且规模越大差距越明显。
- 最大规模测试为 20 个 shell、83K satellites、1K ground stations，作者称在 Intel Xeon Silver 4309Y、128 GB memory 上一周内完成仿真。
- Traffic matrix appendix 显示 high-population、GDP-weighted、capital、global flight TMs 下参数趋势大体一致；但 global flight TM 因 8,384 flights 与 100 城市 GS 连接，局部每颗卫星服务 100+ flights，throughput 更低。

## Critical Analysis

### 论证链条

论文的链条是闭合的：先指出公开工具无法支持大规模 constellation design；再用 flow-level model 和 process parallelism 解决速度；然后通过大量参数扫描抽取 search-space shape；最后把这些 shape 编进 VNS，展示 search time 降低且解质量接近黑盒优化。作为「design exploration framework」论文，这条线很干净。

最需要小心的是结论层级。论文强证明的是 LEOCraft 在自己的 flow-level model 下能快速重现实验趋势，并产生可解释的 constellation design heuristics；弱证明的是这些 heuristics 能指导真实 operator 的部署。真实网络的 beam policy、terminal distribution、regulatory limits、weather、handoff cost 和 business objective 都可能改变 objective landscape。

### 假设压力测试

时间维度的剪枝最脆。6.5% throughput fluctuation 是吞吐均值附近的 constellation-level measurement，不等价于用户体验稳定。如果 route churn 造成短时 packet loss，或者 inter-shell handoff 引入 link setup delay，tail latency 和 transport recovery 可能比平均吞吐更重要。

o >> n、p = 0.5 的结论也和 routing / topology abstraction 绑定很深。20 shortest paths + LP 会奖励 path diversity；真实系统如果只使用单路径、少量备选路径、policy routing，或者为了降低 ISL handoff 选择不同 topology，这个结论需要重测。

需求模型是另一个压力点。100 most populous cities 很适合说明 residential broadband 与 urban GS placement，但 OneWeb maritime、polar Starlink、aviation corridors 这类 workload 会改变 latitude distribution 和 GSL contention。论文在 appendix 里做了 flight TM，但仍是由 flights 到 100 城市 GS 的 proxy，不是真实 aircraft-to-gateway topology。

### 实验可信度

LEOCraft 和 Hypatia 的 RTT 对比是有帮助的 sanity check，因为它验证了几何路径距离与 propagation delay 的一阶模型。但 throughput 没有相同强度的外部验证：LP 求的是理想可分流的 flow allocation，现实系统还需要 routing granularity、link scheduling、beam steering、terminal association 和 congestion control。

优化实验比较公平地纳入 SA、DE、A-PSO、VNS，并报告剪枝前后运行时间与解质量。不过 hyperparameters 是通过 synthetic constellation trials 经验设置的，且 VNS 是与剪枝策略最天然匹配的 local search，因此 5x search speedup 更像「domain-shaped search beats generic search」而不是 VNS 本身通用优越。

### 系统性缺陷

论文明确不建模 interference，而真实 LEO broadband 的 spot beams、frequency reuse、beam splitting/merging、antenna count 和 weather fading 会直接影响 GSL capacity。由于 LEOCraft 的 throughput 常常受 GSL bottleneck 主导，这个缺口会影响设计排序。

运维风险也只被部分覆盖。Inter-shell ISL handoff 需要周期维护 topology，但论文没有进一步建模 handoff protocol、failure recovery、route reconvergence、observability 或 control-plane load。83K satellites 的一周级仿真证明了可运行，不等于 interactive optimization 或 CI-style design iteration 足够快。

## 局限与 Future Work

- **局限 1**：GSL capacity model 未纳入 interference、weather、beam scheduling、terminal association 和 operator policy。
- **Future work 1**：加入可配置 beam / frequency reuse / weather loss model，比较这些因素是否改变 h / i / e / o / p 的排序。
- **局限 2**：traffic matrices 主要是城市、GDP、capital 和 flight proxy，缺少真实 user terminal、maritime、polar、enterprise backhaul traces。
- **Future work 2**：用公开 measurement 或合成但可校准的 regional demand traces 重跑 search-space characterization，报告 optimal inclination / elevation 的漂移。
- **局限 3**：throughput-only 优化可能高估 single dense shell 的吸引力，因为它不把 collision risk、coverage obligation、launch/deorbit constraint 和 tail latency 放进目标函数。
- **Future work 3**：做 multi-objective optimizer，同时输出 Pareto frontier：throughput、median/tail RTT、coverage fairness、handoff rate、collision-risk proxy 和 satellite altitude constraints。
- **局限 4**：inter-shell ISL 只展示吞吐和 handoff interval，没有 packet-level disruption 或 route reconvergence cost。
- **Future work 4**：把 LEOCraft 找出的候选设计导入 [[Hypatia]] 或 packet-level emulator，对 handoff windows 做 micro-benchmark。
- **局限 5**：默认 +Grid topology，把 topology design 放在未来工作。
- **Future work 5**：扩展 PlusGridShell 为 [[XGrid]] 或 learned topology builder，做 trajectory + topology joint optimization，并验证 search pruning 是否仍成立。

## 相关

- **相关概念**：[[LEO-Satellite-Network]]、[[ISL]]、[[GSL]]、[[Multi-Commodity-Flow]]、[[Variable-Neighborhood-Search]]、[[CPython-GIL]]
- **同类系统**：[[Hypatia]]、[[StarryNet]]、[[xeoverse]]
- **相关实体**：[[Starlink]]、[[Kuiper]]、[[OneWeb]]、[[Telesat]]
- **同会议**：[[ATC-2025]]
