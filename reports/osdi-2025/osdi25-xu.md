# Decouple and Decompose: Scaling Resource Allocation with DeDe

**作者**：Zhiying Xu, Minlan Yu (Harvard University); Francis Y. Yan (University of Illinois Urbana-Champaign)
**会议**：OSDI 2025 (19th USENIX Symposium on Operating Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/osdi25/presentation/xu
**源文件**：[osdi25-xu.pdf](../../papers/osdi-2025/osdi25-xu.pdf)

---

## 一、背景

云计算系统中的资源分配（resource allocation）是保障多租户环境下服务质量的核心问题。典型场景包括集群调度（cluster scheduling）、流量工程（traffic engineering）和负载均衡（load balancing），这些场景通常将资源分配建模为线性规划（LP）或混合整数线性规划（MILP），并依赖 Gurobi、CPLEX 等商业求解器求解。

然而，随着云环境持续扩展，现代资源分配问题的规模（百万级变量）已经超出了商业求解器的处理能力——求解时间可达数十分钟甚至数小时，远不能满足秒级 SLO 的要求。这一"可扩展性危机"催生了大量利用启发式、近似算法或机器学习来加速求解的研究，但这些方法要么局限于特定领域，要么依赖特定的 workload 假设（如 POP 的"granular"假设），通用性不足。

---

## 二、要解决的问题

1. **商业求解器的扩展瓶颈**：Gurobi/CPLEX 等求解器在面对数千资源 × 数千需求的大规模问题时，求解时间达到分钟到小时级别，无法满足实时决策需求。
2. **已有加速方案的局限性**：
   - 领域定制方案（如 NCFlow、Teal）仅适用于特定场景（如 WAN 流量工程），不具备通用性。
   - POP 依赖"granular"假设（每个 demand 仅请求少量可互换资源），在现实 workload（如 33% 的 GPU 任务限定特定 GPU 类型）下该假设不成立，导致解质量下降。
   - 启发式方法（如 Gandiva）速度快但解质量差。
3. **约束耦合导致无法直接并行化**：资源约束和需求约束通过共享的分配变量 x_ij 相互纠缠，阻碍了问题的分解和并行求解。

---

## 三、洞察与设计

**关键洞察**：绝大多数现实世界的资源分配问题具有内在的**可分离结构（separable structure）**——目标函数是各资源/需求分配效用之和，约束条件分别独立作用于每个资源和每个需求。这一结构性质是 workload 无关的，可以作为通用加速的基础。

基于这一观察，DEDE 提出了 **decouple-and-decompose** 的两步方法：

### Decouple（解耦）
引入辅助变量 z 作为分配矩阵 x 的副本，将需求约束（及目标中的需求项）改写为关于 z 的表达式，同时添加一致性约束 x = z。这一等价变换使得资源约束只涉及 x，需求约束只涉及 z，从而在数学上解耦了两类约束。随后利用 ADMM（Alternating Direction Method of Multipliers）框架，通过增广 Lagrangian 将一致性约束融入目标函数，实现对 x 和 z 的交替优化。

### Decompose（分解）
由于目标函数和约束都具有可分离结构，x-minimization 步骤可以进一步分解为 n 个独立的 per-resource 子问题（每个只涉及 m 个变量），z-minimization 步骤可以分解为 m 个独立的 per-demand 子问题（每个只涉及 n 个变量）。这些子问题可以用现成求解器独立并行求解。

理论上，对于 LP，原始问题复杂度为 O((n·m)^2.373)，分解后降为 O(n·m^2.373)。

---

## 四、实现细节

- **Python 包**：`pip install dede`，基于 cvxpy 建模语言，提供兼容的 API（Variable、Parameter、Maximize 等），用户需显式区分资源约束和需求约束。
- **并行执行**：使用 Ray 框架实现真正的多进程并行，绕过 Python GIL 限制，支持多 CPU 核心并行求解子问题。
- **三阶段求解流程**：
  1. **Problem Parsing**：将不等式约束通过引入松弛变量转为等式约束。
  2. **Problem Building**：将约束组织为互不相交的 per-resource 和 per-demand 组，基于 cvxpy 构建子问题。
  3. **Problem Solving**：多核并行求解子问题，ADMM 迭代中仅更新参数，避免重建 cvxpy 问题的开销。
- **Warm-start**：默认使用上一轮优化结果作为初始解，加速收敛。
- **适用范围**：支持连续变量和整数/布尔变量（通过投影）；要求目标可分离且约束线性。

---

## 五、实验结果

实验平台：64 CPU cores (2× Intel Xeon Gold 6142)，部分实验使用 Nvidia Titan RTX GPU（供 Teal 使用）。

### 集群调度

| 方法 | Max-min 分配质量 | 计算时间 |
|------|---------|--------|
| DEDE | 0.94 (3s), 0.99 (10s) | 3-10s |
| Exact sol. | 1.00 | 156s |
| POP-4 | ~0.94 | 比 DEDE 慢 1.6× |
| POP-16 | 0.90 | 3.1s |
| Gandiva | 0.43 | 1.4s |

Proportional fairness 变体中，DEDE 在 100s 内达到归一化公平性 >1（超越 Exact sol.），POP-4 和 POP-16 分别需要 3053s 和 682s。

### 流量工程（1739 节点网络拓扑）

| 方法 | 满足需求比例 | 计算时间 |
|------|---------|--------|
| DEDE | 90.8% (30s), 92% (60s) | 30-60s |
| POP-4 | 92% | 1658s |
| POP-16 | 87.4% | 456s |
| POP-64 | 81.6% | 380s |
| Teal (GPU) | 89% | 1s |
| Pinning | 87.3% | 149s |

### 负载均衡（2048 shards, 256 servers, 整数规划）

| 方法 | 平均 shard 移动数 | 计算时间 |
|------|---------|--------|
| DEDE | 20.1 | 15s |
| POP-4 | 21.5 | 133s |
| Exact sol. | 20.9 | 4820s |
| Greedy | 73 | 2ms |

### 可扩展性

- DEDE 在 1-16 核时接近线性加速，64 核时达 18.2× 加速。
- DEDE* （理想并行）64 核达 61.7× 加速。
- Exact sol. 64 核仅 3.4× 加速。

---

## 六、批判性分析

1. **DEDE 与 DEDE* 的差距值得关注**：论文承认 DEDE 的实际加速比（18.2×/64核）远低于理想值（61.7×），原因包括 cache contention、straggler 效应和静态任务分配。然而论文在对比 POP 时，多处使用 DEDE* 的数据（"fair comparison"），这实际上有利于 DEDE 的呈现。真正公平的对比应该都用实际运行时间。

2. **ADMM 收敛性的理论保证有限**：对于整数变量和非凸问题，ADMM 的收敛性仅有经验证据支持，缺乏理论保证。负载均衡（MILP）场景中 DEDE 的表现虽好，但论文未充分讨论在什么条件下可能出现不收敛或收敛到差解的情况。

3. **可分离结构的普遍性可能被高估**：论文 Table 1 列出的"绝大多数"问题都是可分离的，但这些问题的选取本身可能存在采样偏差——作者可能倾向于选择符合其框架的问题。带有跨资源/跨需求耦合约束的实际场景（如用户级 GPU 配额、跨数据中心一致性约束）并未被充分覆盖。

4. **Penalty parameter ρ 的选择**：ρ 对 ADMM 收敛速度至关重要（类似学习率），但论文未详细讨论其调优策略，仅在附录中简要提及。对于一个声称"push-button"的通用工具，这是一个重要的工程细节缺失。

5. **与 Teal 的比较不完全公平**：Teal 在 GPU 上仅需 1 秒即可达到 89% 满足率，虽然论文指出 Teal 需要训练且对分布变化敏感，但对于固定拓扑的生产环境，Teal 的方案可能更实际。论文将 Teal 定位为"domain-specific"来淡化这一对比。

---

## 七、AI Infra / MLSys 视角

1. **GPU 集群调度的直接应用**：论文的 cluster scheduling 案例直接涉及异构 GPU 集群上的 LLM 推理作业调度（GPT-4、Llama 3、DeepSeek-V3）。随着 GPU 类型日益多样化（H100/A100/V100/B200），DEDE 的可分离分解方法对大规模异构集群的 job placement 具有实际价值。

2. **与 AI 训练/推理调度器的集成潜力**：DEDE 作为 Python 包且基于 cvxpy，可以较容易地集成到现有的 ML 平台调度器（如 Kubernetes scheduler、Yarn）中。其 warm-start 机制特别适合在线调度场景中的周期性重优化。

3. **可分离结构的 insight 可迁移**：
   - **KV Cache 分配**：多模型共享 GPU 内存时的 KV cache 分配问题可能具有可分离结构。
   - **流水线并行的 stage 分配**：将模型层分配到不同设备上的问题，资源约束（设备内存）和需求约束（层的计算需求）天然分离。
   - **MoE 路由优化**：Expert 到 GPU 的分配优化可能适用此框架。

4. **Future work 方向**：
   - 将 DEDE 扩展到带时间维度的调度问题（论文 §4.2 指出三维以上的 ADMM 可能有收敛问题，这是一个值得研究的方向）。
   - 探索用 GPU 加速 DEDE 子问题的求解（结合 Teal 的思路），实现更大规模的并行。
   - 在 serving 场景中，将 request routing 建模为资源分配问题并用 DEDE 加速。

---

## 八、总结

DEDE 通过发现现实世界资源分配问题普遍具有的可分离结构，提出了基于 ADMM 的 decouple-and-decompose 框架，将大规模资源分配问题分解为可独立并行求解的 per-resource 和 per-demand 子问题。在集群调度、流量工程和负载均衡三个代表性任务上，DEDE 相比 POP 实现了 2.2×-7.6× 的加速和 5.3%-12.6% 的解质量提升。其主要优势在于通用性（不依赖特定 workload 假设）和理论根基（基于 ADMM），局限性在于对非凸问题缺乏收敛保证、实际并行效率与理想值有差距、以及 ρ 参数需要调优。
