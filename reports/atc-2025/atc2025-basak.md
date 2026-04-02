# LEOCraft: Towards Designing Performant LEO Networks

**作者**：Suvam Basak, Amitangshu Pal (Indian Institute of Technology Kanpur); Debopam Bhattacherjee (Microsoft Research India)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/basak
**源文件**：[[atc2025-basak.pdf]]

---

## 一、背景

低轨道 (LEO) 卫星星座正在彻底改变全球互联网接入方式。SpaceX 的 Starlink 和 OneWeb 已部署数千颗卫星，在 100 多个国家提供宽带服务。随着激光 Inter-Satellite Links (ISLs) 技术的成熟，LEO 卫星网络可以在太空中形成高带宽、光速级延迟的 mesh 网络，承载长距离互联网流量。SpaceX 和 Amazon Kuiper 正在规划第二代巨型星座（分别为 30,000 和 3,236 颗卫星），但目前尚无运营商实现了完整规模的 ISL mesh 网络部署，这为网络研究社区提供了影响这些网络设计的短暂窗口。

---

## 二、要解决的问题

1. **缺乏合适的工具**：现有 LEO 网络模拟平台存在根本性的可扩展性问题。Hypatia 基于 ns-3 包级仿真，无法利用多 CPU，仿真数千颗卫星需要数小时；StarryNet 基于 Docker 容器模拟，受限于 Docker bridge 上限（1,023 容器）和 CPython GIL 瓶颈；xeoverse 声称性能更优但代码未公开。社区缺乏能处理数万颗卫星的大规模轨道和拓扑优化工具。

2. **高维优化难题**：LEO 星座设计涉及六个参数（高度 h、倾角 i、仰角 e、轨道数 o、每轨卫星数 n、相位偏移 p），加上 24 小时内多个 epoch 的性能波动评估，暴力搜索面临维度灾难，可能需要数年计算时间。

3. **设计知识不透明**：Starlink 和 OneWeb 依赖专有系统，其设计选择和目标流量矩阵对社区不可见，研究者难以理解这些"新太空"网络为何如此设计。

---

## 三、洞察与设计

**关键洞察**：LEO 星座的六个设计参数可以根据其对覆盖率的影响分为两组——GROUP-I（h, i, e）影响覆盖率，GROUP-II（o, n, p）不影响覆盖率。当 GROUP-I 参数接近最优时，GROUP-II 中只要轨道数 o 远大于每轨卫星数 n（o >> n）且相位偏移 p = 0.5，就能产生最高吞吐量。这意味着六维搜索空间可以大幅缩减为仅优化三个参数（h, i, e）。

基于此洞察，LEOCraft 的设计包含以下核心模块：

- **LEO 星座构建器**：根据设计参数自动生成 TLE（Two Line Element），构建包含卫星、地面站、ISL 和 GSL 的网络图。
- **流级仿真引擎**：采用基于进程的并行（ProcessPoolExecutor），绕过 GIL 瓶颈，将独立计算任务（覆盖区域计算、路由计算等）分配到所有可用 CPU。Starlink 三个 shell 3,888 颗卫星的评估仅需约 2.5 分钟。
- **优化框架**：集成 Variable Neighborhood Search (VNS)、Simulated Annealing、Differential Evolution、Adaptive Particle Swarm Optimization，并利用领域知识剪枝搜索空间。
- **可视化模块**：生成交互式星座视图，展示拓扑演化和端到端路由变化。

性能评估采用多商品流线性规划最大化吞吐量，使用 Yen's 算法计算 k=20 条最短路径，通过 Gurobi 求解 LP。

---

## 四、实现细节

- **并行架构**：LEOConstellationSimulator 创建与 CPU 核心数对应的 worker 进程池，进程在整个仿真期间保持活跃以减少创建开销。每个 LEO 网络组件（卫星、地面站等）作为独立块运行，通过格式化的 API 交换数据。
- **网络建模**：GSL 带宽基于 Shannon 信道容量定理计算，大气路径损耗使用 Free-Space Path Loss (FSPL) 模型估算。ISL 容量保守设为 50 Gbps。
- **搜索空间缩减**：利用五个 key takeaway 将搜索空间从六维缩减到三维（h, i, e），其中：时间维度可忽略（性能波动 <6.5%）；o >> n 且 p=0.5 为最优拓扑配置；i 利用对称性限制在 0°-90°。
- **VNS 优化**：初始解选 i ≈ 30°（对应 100 最大城市的中位纬度 29.6°）、e 在 10°-20° 之间，每次迭代随机步长探索邻域。
- **流量矩阵**：支持四种直观的流量需求矩阵——高人口 TM、高 GDP 人口 TM、国家首都 TM、全球航班 TM，均基于重力模型。
- **模块化设计**：扩展仅需继承并覆盖特定方法（如 `build_ISLs()` 实现 ×Grid 拓扑），典型修改约 100 行代码。代码开源于 GitHub（MIT License），依赖 Gurobi 求解 LP。

---

## 五、实验结果

**实验平台**：16 核 Intel i9-12900 + 64GB 内存（优化实验）；Intel Xeon Silver 4309Y (16核) + 128GB 内存（大规模仿真）。

| 实验 | 关键结果 |
|------|---------|
| 优化加速 | 使用领域知识后，VNS 比 SA/DE/A-PSO 的原始版本分别快 ~2.1×/4.2×/2.2×/13.7×；VNS+领域知识比最快的原始元启发式至少快 ~4.9× |
| 单 shell vs 多 shell | Starlink 3,888 颗卫星合并单 shell 吞吐量 8 Tbps > 三个独立 shell 优化后的 7.5 Tbps |
| Inter-shell ISL | 三 shell + inter-shell ISL 吞吐量达 8.01 Tbps（Starlink）/ 7.34 Tbps（Kuiper），接近单 shell，但需每 ~4-13 小时 handoff |
| 与 Hypatia 延迟对比 | LEOCraft 计算的 RTT 与 Hypatia 的 ping 结果高度吻合 |
| 仿真速度 | LEOCraft 比 Hypatia 快 1.7× 到 54.5×，差距随星座规模增大而增大 |
| 大规模可扩展性 | 83K 颗卫星的 mega-constellation 仿真在单台工作站上一周内完成 |

---

## 六、批判性分析

1. **仅优化吞吐量**：论文聚焦于最大化吞吐量作为唯一目标函数，但实际星座设计需要多目标权衡（延迟、覆盖率、公平性、成本）。论文承认这是未来工作，但在当前框架下得出的"最优设计"可能在其他维度表现不佳。

2. **流量模型的现实性存疑**：使用基于人口和 GDP 的重力模型作为流量矩阵，与真实 Starlink 用户分布可能差异很大。论文无法验证这些 TM 与实际流量的吻合度，因为真实数据是专有的。所有设计结论（如最优倾角 ~40°）都强依赖于 TM 的选择。

3. **流级仿真 vs 包级仿真的局限性被低估**：论文将 LEOCraft 与 Hypatia 定位为"互补"而非竞争，但在验证中仅比较了 RTT——这恰好是流级仿真能准确预测的指标。对于拥塞、队列延迟、TCP 行为等关键场景，流级仿真可能给出误导性结果，这一点未被充分讨论。

4. **+Grid 拓扑假设的局限**：论文假设所有星座使用 +Grid 拓扑（每颗卫星 4 条 ISL），这是当前 Starlink 的做法，但 ×Grid 等替代拓扑已被证明在某些场景下更优。框架虽然支持扩展，但所有实验结论都绑定在 +Grid 假设上。

5. **搜索空间缩减的通用性未验证**："o >> n 且 p = 0.5 最优"这一关键结论来自特定 TM 和 +Grid 拓扑下的观察。当 TM 偏向极地区域（如航运场景）或使用不同拓扑时，该结论是否仍成立？论文在附录中展示了不同 TM 下的相似趋势，但仅限于"100 最大城市"的 GS 分布。

6. **Inter-shell ISL 的 handoff 问题被简化**：论文发现多 shell 需要每 4-13 小时 handoff 以维持拓扑，但 handoff 期间的性能影响（中断时间、路由重收敛）未被量化。

---

## 七、总结

LEOCraft 是一个开源、模块化的 LEO 星座设计探索和优化框架，通过进程级并行和流级仿真实现了大规模可扩展性（测试至 83K 颗卫星），并利用领域知识将搜索空间从六维缩减到三维，使优化速度提升约 5 倍。其主要贡献在于系统化地揭示了各设计参数对网络性能的影响规律，为网络研究社区提供了影响下一代巨型星座设计的实用工具。主要局限在于仅优化吞吐量单一目标、流量模型的现实性难以验证、以及流级仿真在细粒度网络行为分析上的天然不足。
