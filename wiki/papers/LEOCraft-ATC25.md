---
type: paper
name: LEOCraft
full_title: "LEOCraft: Towards Designing Performant LEO Networks"
authors: [Suvam Basak, Amitangshu Pal, Debopam Bhattacherjee]
venue: ATC
year: 2025
tags: [networking, leo-satellite, simulation, optimization, constellation-design]
source_pdf: "[[atc2025-basak.pdf]]"
source_md: "[[atc2025-basak]]"
---

# LEOCraft: Towards Designing Performant LEO Networks (ATC 2025)

> **一句话总结**：面向 [[Starlink]] / [[Kuiper]] 等大型 LEO 星座的 flow-level 设计探索框架，用 process 级并行 + Variable Neighborhood Search 把 6 维参数空间剪枝成 3 维，比黑盒 metaheuristic 快 5×，可处理 83K 卫星跨多 shell 的超大星座（>2× SpaceX 长期方案）。

## 问题

LEO 巨型星座（Starlink Gen2 计划 30K 卫星，Kuiper 3,236）正在改变互联网基础设施，但学术界缺工具：

- 现有 [[Hypatia]]（基于 ns-3 packet 仿真）和 StarryNet（基于 Docker 容器 + thread 并行）受 [[CPython-GIL]] 和 ns-3 单核限制，单 shell 1,584 卫星仿真都要数小时；xeoverse 不开源；
- 设计参数高维（6 个：高度 h、倾角 i、仰角 e、轨道数 o、每轨星数 n、phase offset p），加上 24 小时动态，brute-force grid search 要数年；
- 已有研究多局限单 shell，多 shell 间 ISL 互连和聚合性能被认为是 "open problem"。

## 核心方法

**LEOCraft** 是一个 flow-level 探索 + 优化 + 可视化框架：

- **System design**：把卫星 / 地面站建模成独立块，用 [[multiprocessing]] 绕开 GIL，把瓶颈从软件层移到硬件；
- **Network model**：节点 = 卫星 + GS，边 = ISL + GSL；GSL 容量用 Shannon 公式 + FSPL 路径损耗，ISL 默认 50 Gbps；
- **Performance metrics**：throughput（multi-commodity flow LP，Yen 算法 n=20 最短路）、stretch（路径距离 / geodesic）、coverage；按路由方向把流分成 LG / HG / NS / EW / NESW 五类；
- **Traffic matrices**：高人口 TM、高 GDP TM、capital TM、global flight TM，基于 gravity model；
- **优化策略**：通过 5 个 takeaway（LEO 动态波动 <6.5%；h 太低/太高都坏；i 应对齐 GS 分布；e 太极端不行；o>>n 且 p=0.5 最好）把 6 维降到 3 维（h, i, e），用 [[Variable-Neighborhood-Search]]（VNS）随机步长收敛；
- **初始解**：i≈30°（100 大城市中位纬度 29.6°）、e 在 10-20°。

## 关键结果

- 比黑盒 metaheuristic（[[Simulated-Annealing]] / [[Differential-Evolution]] / [[APSO]]）快 ~5×。
- Starlink Gen1 三 shell 3,888 卫星在 desktop PC 上仅 ~2.5 分钟（Hypatia 仅 RTT 测量就要数小时）。
- 测试规模到 83K 卫星 + 1K 地面站，是 SpaceX 长期方案 2× 以上。
- 揭示 inter-shell ISL 可提升 throughput，并量化其代价。

## 相关

- **相关概念**：[[LEO-Satellite-Network]]、[[ISL]]、[[Variable-Neighborhood-Search]]
- **实体**：[[Starlink]]、[[Kuiper]]、[[OneWeb]]
- **同会议**：[[ATC-2025]]
