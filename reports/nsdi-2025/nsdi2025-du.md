# PRED: Performance-oriented Random Early Detection for Consistently Stable Performance in Datacenters

**作者**：Xinle Du (Huawei Technologies), Tong Li (Renmin University of China), Guangmeng Zhou, Zhuotao Liu, Hanlin Huang, Xiangyu Gao (Tsinghua University), Mowei Wang, Kun Tan (Huawei Technologies), Ke Xu (Tsinghua University)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/du
**源文件**：[nsdi2025-du.pdf](../../papers/nsdi-2025/nsdi2025-du.pdf)

---

## 一、背景

数据中心承载着多种对网络性能要求各异的服务：存储和数据挖掘需要高吞吐，而 Web 搜索和机器学习推理服务需要低延迟。为满足这些需求，学术界提出了大量拥塞控制算法（DCTCP、DCQCN、TIMELY、HPCC、Swift、BFC 等），但这些新算法的部署面临巨大挑战——需要修改内核、NIC 或交换机硬件，在由大量异构遗留设备组成的生产数据中心中难以落地。

Random Early Detection (RED) 作为最基本的 Active Queue Management (AQM) 机制，已被广泛集成到商用交换机中，是 DCTCP 和 DCQCN 等主流拥塞控制协议的核心依赖。然而，RED 的参数（标记概率斜率 λ 和最小阈值 minK）通常是静态配置的，无法适应数据中心网络高度动态的流量模式，导致在不同流量并发度和流量分布下性能不稳定。

---

## 二、要解决的问题

1. **静态 RED 无法适应动态流量并发度**：当并发流数量 N 增大时，交换机的稳态队列长度 q̇ 随之增长（由流体模型 Equation (1) 推导），导致短流 FCT 增大、甚至触发 TCP incast 吞吐坍塌。不同并发度需要不同的 λ 设置，但静态 RED 只能选择一个固定值。

2. **静态 RED 无法适应动态流量分布**：以小流为主的工作负载需要较大的稳态队列长度以维持链路利用率，而以大流为主的工作负载需要较小的稳态队列长度以降低延迟。静态 RED 无法同时满足两种需求。

3. **现有动态调整方案不稳定**：ACC（基于深度强化学习的 RED 自动调参方案）是最先进的动态方案，但存在两个根本问题：(a) DRL 的决策延迟（毫秒级）与并发度变化速度（微秒级）不匹配，无法实时响应 N 的变化；(b) DRL 预测本身存在误差率，在探索过程中会选择糟糕的 RED 参数，导致队列长度剧烈波动，尾部 FCT 严重退化。

---

## 三、洞察与设计

**关键洞察**：RED 的稳态队列长度 q̇ 由流体模型 (q̇ − minK)²(q̇ + Cd) = 2N/λ² 决定，其中 λ 可以单调地影响 q̇。这意味着可以将 RED 参数配置从传统的 two-point form (minK, maxK, maxP) 转化为等价的 point-slope form (minK, λ)，其中 λ = maxP/(maxK − minK)。这种形式下，只需调节单一变量 λ 就能线性地控制稳态队列长度，使动态调参变得可解释且可控。

基于这一洞察，PRED 设计了两个松耦合的子系统：

**Flow Concurrent Stabilizer (FCS)**：直接在交换机数据平面上计数并发流数 N，根据 f(N) = N 的映射函数以 MIMD 方式调整 λ，使稳态队列长度不随并发度变化而波动。FCS 包含三个模块：
- **Flow Counter**：基于五元组哈希和 bitmap 在每个 T_FCS 周期内计数新到达的流数 n
- **Flow Estimator**：取 N = max{n_last, n} 作为当前并发度估计，避免周期起始阶段的低估
- **f(N) 映射**：将 λ 乘以 f(N) 来补偿并发度变化

**Queue Length Adjuster (QLA)**：以 AIAD (Additive-Increase Additive-Decrease) 方式通过 A/B 测试逐步调整 λ_QLA，实现运行时的流量感知。QLA 包含三个模块：
- **Utility Function**：综合吞吐率 R/C 和队列长度 Φ(q̄) 的加权和（β=0.4）作为性能度量
- **Decision Maker**：使用两次受控试验（TCT）减少噪声影响——在连续 4 个 T_QLA 周期中分别尝试 λ±∆λ，只有当两次试验结果一致时才调整
- **minK Adjuster**：当 λ 趋近于 0（λ < λ_min = 0.05）时，转为调整 minK

最终 RED 参数由两个模块协同决定：λ = f(N) × λ_QLA。

---

## 四、实现细节

PRED 在 Barefoot Tofino 1 可编程交换机上实现原型：
- **数据平面**：约 350 行 P4 代码，部署 FCS 模块，占用 12 个 MAU stage 中的 11 个
- **控制平面**：约 300 行 Python 代码，部署 QLA 模块（因 Tofino 1 仅有 12 stage，QLA 额外需要 6 stage，总计需 17 stage）
- **存储开销**：每个端口仅需几个寄存器缓存 N 和 bitmap（如 128 bit bitmap + 8 bit 计数器）

关键实现技巧：
- **无需批量重置 bitmap**：利用时间间隔序列号（Interval_seq）参与哈希计算，使同一流在不同时间间隔自动获得不同哈希值，新值覆盖旧值即可
- **RED 表实现**：因 P4 不支持直接除法，将 RED 算法编程为查找表（key 为队列长度和流数，value 为标记概率）
- **队列长度采样**：数据平面多次采样队列长度并求和存入寄存器，控制平面读取后计算平均值

关键参数设置：
| 参数 | 值 | 说明 |
|------|------|------|
| T_FCS | 1.25 × RTT | 流计数周期 |
| T_QLA | 5 RTT (仿真) / 400 ms (测试床) | QLA 调整周期 |
| ∆λ | 0.025 | λ 试验步长 |
| ∆minK | 5 packets | minK 调整步长 |
| β | 0.4 | 吞吐-延迟权衡因子 |
| q_left | 15 packets | 效用函数稳定区间 |
| maxK | 500 KB | 最大阈值（固定保护值） |

Tofino 2/3 交换机支持 20 stage，可将 FCS 和 QLA 同时部署到数据平面，消除控制平面交互延迟。

---

## 五、实验结果

### 测试床实验（Barefoot Tofino 交换机，10 Gbps）

| 实验 | 关键结果 |
|------|---------|
| FCS 稳定性（2 sender, 变化 N） | PRED 和 FCS(N) 在 N 变化时保持队列长度稳定，吞吐约 9.4 Gbps |
| QLA 收敛（6 sender, WebSearch 负载） | PRED 在 ~10s 内收敛到最优 λ，FCT 逼近最优静态 RED |

### 大规模仿真（NS-3, 128-host leaf-spine, 10 Gbps）

**WebSearch 工作负载（90% 负载）**：

| 指标 | PRED | ECN | ECNSharp | CoDel |
|------|------|-----|----------|-------|
| 小流 99th FCT | 1.4 ms | - | 4.34 ms | 6.68 ms |
| 降幅 | - | - | 68% | 80% |

**与 ACC 对比（18-to-1, 混合工作负载）**：
- PRED 99th FCT 比 ACC 降低 34%（0.47 ms vs 0.63 ms）
- PRED 99th 队列长度为 54 packets，ACC 为 105 packets
- ACC 因 DRL 探索导致队列偶发剧增，PRED 保持稳定

**100 Gbps 1000+ 并发流（128-host, DataMining 负载, 80%）**：
- PRED 小流 99th FCT 240 µs，比 RED 降低 48%，比 CoDel 降低 66%
- PRED 小流平均 FCT 42 µs，比 RED 降低 52%

**与 HPCC 对比（20-to-1, 100 Gbps）**：
- HPCC 维持近零队列和 93% 吞吐；PRED 队列长度约 15 packets，吞吐率满载
- PRED 在突发到来时队列波动更小（HPCC 无慢启动导致突发时队列变化大）
- PRED 仅需修改交换机，HPCC 需修改 NIC 和交换机

### 微观分析

- PRED 将交换机队列长度降低 66%（从 25 降至约 15 packets）
- FCS 快速响应并发度变化但稳态队列偏高，QLA 可进一步优化但收敛慢——两者协同效果最佳
- PRED 调整范围上限：当并发长流 N > 32 时无法维持队列稳定（但生产中并发长流数通常远低于此）

---

## 六、批判性分析

1. **核心假设的局限性被轻描淡写**：PRED 的流体模型基于 N 条 long-lived 同步流的假设推导，但论文自己承认 f(N)=√N 因并发同步假设不成立而失效，最终选择 f(N)=N 是通过经验调参而非理论推导。这意味着 PRED 的"显式建模"优势相对于 ACC 的"黑箱预测"并没有论文宣称的那么大——两者都需要经验性调参。

2. **QLA 收敛速度是重大实际瓶颈**：在 Tofino 1 上 T_QLA = 400 ms，需要至少 4 × T_QLA = 1.6 秒才能完成一轮 A/B 测试。论文测试床实验显示 PRED 需要 ~10 秒才能收敛。数据中心流量模式在秒级甚至毫秒级就会发生显著变化，这种收敛速度在高度动态的生产环境中是否足够值得质疑。论文将希望寄托于 Tofino 2/3，但未实际验证。

3. **实验设计偏向 PRED 的强项**：与 ACC 的对比使用了人造的混合工作负载（纯小流 + 纯大流交替），这恰好是 ACC 探索机制表现最差的场景。论文未在更贴近现实的持续混合流量下进行对比。ACC 的训练和测试使用完全相同的 trace，相当于在最有利于 ACC 的条件下仍然让 ACC 表现差——但这其实说明论文对 ACC 的实现可能不够公平（action space 设计为 4×3×21 的离散空间，而非 ACC 原文的设计）。

4. **参数敏感性分析不充分**：PRED 引入了大量需要调优的参数（T_FCS, T_QLA, β, ∆λ, ∆minK, q_left, λ_min, maxK），论文声称这些参数"traffic-insensitive"但承认"fine-tuning these parameters remains essential"。对于一个声称优于 DRL 的白盒方案来说，参数空间并不比 ACC 更简单。附录中的敏感性分析仅覆盖了有限的参数组合。

5. **可部署性优势被夸大**：论文强调 PRED 只需修改交换机而不需修改端主机，但 PRED 需要可编程交换机（Tofino），而论文对比的 ECN/RED 方案只需普通商用交换机。在"异构遗留设备"的数据中心场景（论文 motivation 的核心）中，可编程交换机并不是标配。

6. **N > 32 的限制未充分讨论影响**：论文仅用一句"并发长流数通常较少"带过，但在 incast 场景（如分布式存储、MapReduce shuffle）中，数十乃至上百条并发流同时到达同一 ToR 交换机是常见的。

---

## 七、总结

PRED 提出了一种基于显式建模和 A/B 测试的 RED 参数动态调整方案，通过 FCS 和 QLA 两个松耦合模块分别应对流量并发度变化和流量分布变化，在不修改端主机的前提下实现了交换机级的自适应拥塞信号优化。在仿真和小规模测试床上，PRED 相比静态 RED 降低队列长度 66%、降低短流 FCT 高达 80%，相比 DRL-based ACC 降低尾部 FCT 34%。其主要局限在于 QLA 收敛速度受限于硬件实现（Tofino 1 控制平面延迟）、并发流数上限（N > 32 时失效）以及较多的超参数需要调优。
