# Quantum Virtual Machines

**作者**：Runzhou Tao, Hongzheng Zhu (University of Maryland, College Park); Jason Nieh (Columbia University); Jianan Yao (University of Toronto); Ronghui Gu (Columbia University)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/tao
**源文件**：[[osdi25-tao.pdf]]

---

## 一、背景

量子云计算服务（如 IBM Quantum、Amazon Braket）让用户可以按需使用量子计算机。当前的 NISQ (Noisy Intermediate-Scale Quantum) 设备通常拥有数十到上百个 qubit，但由于硬件噪声，实际程序只能使用其中很少一部分 qubit。经典云计算早已通过虚拟机（VM）实现了高效的多租户资源共享，但量子云计算的软件基础设施极为原始——用户提交的量子程序必须独占整台量子计算机串行执行，无论程序实际使用多少 qubit，造成严重的资源浪费和长时间排队等待。

---

## 二、要解决的问题

1. **资源利用率极低**：每个量子程序独占整台机器运行，大部分 qubit 闲置。例如 IBM 127-qubit Eagle 机器上，大多数程序只使用少量 qubit，利用率仅 3-8%。
2. **延迟高**：用户提交程序后需排队等待数天甚至一周才能获得结果，且 IBM 限制每个用户同时只能有少量（如 3 个）作业在队列中。
3. **现有多程序方案的局限**：已有的量子多程序方案依赖定制编译器在编译时合并多个程序，要求提前知道哪些程序会一起执行，无法独立编译，缺乏标准编译器的优化，且扩展性差（有些方案只支持两个程序并行）。

---

## 三、洞察与设计

**关键洞察**：所有真实量子计算机的 qubit 拓扑结构都是由一个基本重复区域（region）以网格方式排列而成的。例如 IBM Eagle 由重复的 I 形 7-qubit 区域组成（与 IBM Falcon 机器相同），Rigetti Aspen M-3 由八角形区域组成。利用这一重复结构，可以将量子虚拟机（qVM）定义为这些基本区域的整数倍，从而使 qVM 的拓扑天然匹配真实硬件，实现零虚拟化开销的直接执行。

基于此洞察，HyperQ 系统设计如下：

- **qVM 抽象**：qVM 以量子硬件的 coupling map 和 gate set 定义，与经典 VM 类比——是架构特定的（IBM Eagle 的 qVM 不能在 Rigetti 上运行，就像 x86 VM 不能在 ARM 上运行）。qVM 支持基本大小（如 7-qubit）、缩放大小（m×n 个基本单元）和分数大小（半个基本单元）。
- **编译兼容性**：qVM 作为编译后端 target 暴露给 Qiskit 等标准编译器，程序独立编译到 qVM，无需知道其他程序的存在。
- **故障隔离**：不同 qVM 之间保留未使用的 qubit 作为间隔，确保无直接连接，从而隔离 crosstalk 噪声。
- **空间调度**：将 qVM bin-pack 到机器的网格区域中（三维 bin-packing 问题）。
- **时间调度**：当长短程序并行时，短程序结束后其 qubit 可通过 mid-circuit reset 复用给新的 qVM，填充时间空隙。
- **噪声感知调度**：根据硬件各区域的噪声质量和程序的噪声敏感度，将噪声敏感程序分配到高质量区域，高噪声/噪声容忍程序放到低质量区域。

---

## 四、实现细节

- **qVM 聚合**：将一个 batch 中所有 qVM 的编译结果聚合为一个大的复合量子电路（composite quantum circuit），通过 qubit 翻译（虚拟 qubit → 物理 qubit 映射）、gate 方向调整（undirected → directed edges）和 reset 指令插入来实现。
- **qubit 编号方案**：基本单元、水平连接、垂直连接按 row-major 顺序分配 qubit 编号偏移，连接使用负编号 qubit 表示。
- **执行时间估算**：利用量子电路的 critical path length（按各 gate 的已知执行时间加权）来精确估算运行时间，这在量子程序中比经典程序容易得多（无循环、无缓存行为）。IBM Eagle 上单 qubit gate 约 60ns，双 qubit ECR gate 约 600ns，measurement 约 1.3μs，reset 约 1.8μs。
- **超时控制**：提交 batch job 时设置 1.5× 估算运行时间的超时限制，确保失败程序不会影响后续执行。
- **结果后处理**：维护 qVM classical bits 到复合电路输出的线性映射，拆分返回结果。
- **与 IBM Quantum Platform 集成**：复合电路作为普通 job 提交，无需云服务端修改。编译使用 Qiskit v1.0。

---

## 五、实验结果

实验在 IBM Brisbane 量子计算机（127-qubit Eagle）上进行，使用 QASMBench 的 small（29 个程序，2-10 qubit）和 small&med（49 个程序，2-27 qubit）基准集。

**吞吐量（总运行时间）**：

| 配置 | small-only (all-at-once) | small&med (all-at-once) |
|------|--------------------------|------------------------|
| IBM Quantum | 456s | 683s |
| HyperQ | 54s (8.4×) | 178s (3.8×) |
| HyperQ space+time | 47s (9.7×) | 139s (4.9×) |
| HyperQ noise-aware | 64s (7.1×) | 176s (3.9×) |

**利用率**：

| 配置 | small-only (all-at-once) | small&med (all-at-once) |
|------|--------------------------|------------------------|
| IBM Quantum | 3.3% | 7.8% |
| HyperQ space+time | 35% (11×) | 46% (5.8×) |

**延迟**（Poisson 到达模式下平均延迟）：

| 配置 | small-only | small&med |
|------|-----------|-----------|
| IBM Quantum | 159s | 248s |
| HyperQ space+time | 3.7s (43×) | 9.7s (26×) |

**Fidelity**（L1 距离，越低越好）：

| 配置 | all-at-once | poisson |
|------|-------------|---------|
| IBM Quantum | 0.55 | 0.55 |
| HyperQ | 0.55 | 0.57 |
| HyperQ noise-aware | 0.54 | 0.50 |

HyperQ noise-aware 调度在 Poisson 模式下 fidelity 比 IBM Quantum 提升约 10%。实际使用中，IBM Quantum 运行基准集需 19-40 小时，HyperQ 通常只需 2-3 小时。

---

## 六、批判性分析

1. **利用率上限受限于外部碎片**：127 qubit 的 Eagle 机器最多只能使用 85 个 qubit（9 个 qVM 区域），外部碎片率在 small&med 基准下达到 59%。论文对此轻描淡写，但这意味着即使在最优情况下也有 33% 的 qubit 完全无法利用——这是 qVM 设计中固定网格映射的固有代价。
2. **基准集规模偏小且偏简单**：small 类别的程序只有 2-10 qubit，medium 也只到 27 qubit，都远低于 127 qubit 的机器容量。这使得多程序 bin-packing 的收益被人为放大。缺少接近机器容量的大程序的混合负载评估。
3. **时间调度的 fidelity 代价被淡化**：HyperQ space+time 在 all-at-once 模式下 fidelity 降至 0.64（比 IBM Quantum 的 0.55 差 16%），论文将此归因于 mid-circuit measurement/reset 的噪声，并乐观地表示"未来硬件会改善"。但这恰恰说明时间调度在当前硬件上有实质性的 fidelity 成本。
4. **Poisson 到达率的选择缺乏依据**：1 job/second 的到达率是否反映真实云服务负载？论文没有引用实际工作负载特征数据。
5. **与定制编译器方案的比较不够直接**：论文声称优于已有多程序编译方案，但实验中只与 IBM Quantum 原生串行执行做对比，未与任何已有多程序方案做实验对比。
6. **单一硬件平台验证**：所有实验仅在 IBM Eagle 上进行。虽然讨论了 Rigetti 的 qVM 定义，但缺乏跨平台验证。

---

## 七、总结

HyperQ 将经典计算中成熟的虚拟机概念引入量子计算领域，利用量子硬件 qubit 拓扑的重复结构定义量子虚拟机（qVM），通过空间和时间复用实现多程序并行执行。在 IBM 127-qubit Eagle 上的实验表明，HyperQ 可将吞吐量和利用率提升近一个数量级，延迟降低最多 43 倍，同时通过 qubit 间隔隔离和噪声感知调度保持甚至改善 fidelity。主要局限在于固定网格映射带来的外部碎片、时间调度在当前硬件上的 fidelity 代价，以及仅在单一平台上验证。
