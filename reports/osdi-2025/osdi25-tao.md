# Quantum Virtual Machines

**作者**：Runzhou Tao, Hongzheng Zhu（University of Maryland, College Park）; Jason Nieh, Ronghui Gu（Columbia University）; Jianan Yao（University of Toronto）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation），July 7–9, 2025, Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/tao
**源文件**：[osdi25-tao.pdf](../../papers/osdi-2025/osdi25-tao.pdf)

---

## 一、背景

量子云计算使用户可以通过云平台按需访问量子计算机（如 IBM Quantum、Amazon Braket）。当前一代量子计算机以 NISQ（Noisy Intermediate-Scale Quantum）设备为主，量子比特数在数十到数百之间。IBM 等厂商提供公共服务，用户提交量子程序（quantum circuit）作为批处理作业，由云端按顺序串行执行。

与经典云计算相比，量子云的软件基础设施相当原始：没有多路复用、没有虚拟化、也没有有效的资源共享机制。IBM 最近运行了其第 3 万亿次量子程序，体现出极高的用户需求，但基础设施瓶颈导致用户往往需要等待数天才能获得结果。

---

## 二、要解决的问题

**核心问题：量子计算机资源利用率极低，且缺乏多租户支持。**

1. **独占执行导致浪费**：每个量子程序不论大小都独占整台量子计算机。由于噪声约束，大多数程序只能使用少量量子比特（例如 2–27 qubit），127 qubit 的 IBM Eagle 机器绝大部分时间处于空闲状态。

2. **串行调度导致高延迟**：程序按队列顺序一个接一个执行。云服务还限制每用户同时挂起的作业数（通常仅 3 个），用户需等待数天甚至一周才能获得结果。

3. **现有 multiprogramming 方案的局限**：已有研究提出在编译时合并多个量子程序，但这要求提前知道哪些程序会一起执行，无法支持独立编译和运行时动态调度；部分方法仅支持两路并行，无法扩展到大型机器；且无一考虑时间复用或保真度（fidelity）优化。

---

## 三、核心设计

**HyperQ** 是首个为量子计算机引入虚拟机抽象的系统，定义了量子虚拟机（**qVM**）并在运行时动态多路复用量子硬件。

### 关键 Insight：量子计算机的重复拓扑结构

真实量子计算机均以某一固定形状的 qubit 区域（region）为基本单元，在硬件上以网格方式重复排列。例如：
- IBM Eagle（127 qubit）：I 形区域，重复平铺为 3×3 网格（共 9 个区域）
- Rigetti Aspen M-3（80 qubit）：八边形区域

qVM 的大小被定义为该重复单元的整数倍，从而可直接映射到硬件上对应的物理 qubit 区域。相邻 qVM 之间保留未使用的 qubit，以物理隔离方式抑制 crosstalk 噪声。

### qVM 接口

qVM 提供与真实量子计算机后端相同的接口（virtual coupling map + instruction set），对量子编译器（如 Qiskit）透明呈现为一个较小的虚拟机器。程序编译器不需要知道有哪些其他程序会同时运行，可独立将各自程序编译到各自 qVM。

### 调度算法

HyperQ 的调度分两步：

1. **空间调度（Space Scheduling）**：将 qVM 分配到硬件上的不同物理区域，实现空间复用。本质是一个二维 bin packing 问题，按 FIFO 顺序贪心分配，使同一批次（batch）尽可能多地容纳 qVM。

2. **时间调度（Time Scheduling）**：在空间调度的基础上，将运行时间不同的 qVM 进行时间复用。短程序执行完毕后，通过 mid-circuit measurement + reset 重置该区域 qubit，立即运行下一个 qVM，而不等待同批次中最长程序完成。执行时间通过电路关键路径长度（按门延迟加权）估算。

3. **Noise-Aware 调度**：评估硬件各区域的错误率，将高噪声或对噪声不敏感的 qVM 调度到低质量区域，把高质量区域留给对保真度敏感的程序。

### 性能保证

HyperQ 提供形式化的调度保证：任意程序在 HyperQ 下被执行的时间量子（time quanta）编号不会高于串行方式。即 HyperQ 对每个程序的延迟都不差于现有方案，并在吞吐量上大幅领先。

---

## 四、实现细节

- **兼容性**：完全兼容现有量子云服务（IBM Quantum Platform）和编译工具（Qiskit v1.0）。用户将 qVM 作为 Qiskit 的后端编译目标，无需修改程序和编译器。

- **qVM 聚合**：将批次中所有 qVM 合并为一个大的 composite quantum circuit，提交给云端执行。具体步骤：
  1. **Qubit 平移**：将各 qVM 的 virtual qubit 映射到对应的 physical qubit，通过线性扫描完成。
  2. **门方向调整**：将 qVM 中的无向边指令转换为符合实际硬件方向的有向边指令。
  3. **Reset 插入**：在时间复用时，于相应 qubit 序列开头插入 reset 和 barrier 指令，保证前一 qVM 的量子态不干扰后续 qVM。
  4. **超时机制**：估算批次运行时间上限（1.5× 估算值），防止程序失败导致硬件资源泄露，满足资源控制属性。

- **结果后处理**：根据 qVM classical bits 与 big circuit 输出的线性映射，将云端返回的测量结果拆分为各 qVM 的独立输出。

- **实验平台**：IBM Quantum Platform，IBM Brisbane 127-qubit Eagle 芯片；编译主机为 Intel Core i9-12900K（3.2GHz）+ 32GB RAM。

---

## 五、实验结果

基准测试使用 QASMBench，分为 small（2–10 qubit）和 medium（11–27 qubit）两类工作负载，共 29 个 small 程序和 49 个 small+medium 程序，分别重复 5/4 次排队。测试两种到达模式：all-at-once（全部一次性提交）和 Poisson 到达（1 job/s）。

### 吞吐量（Table 3）

| 到达模式 | 配置 | small-only 总运行时 | small&med 总运行时 | 提升倍数 |
|---------|------|------|------|------|
| all-at-once | IBM Quantum | 456s | 683s | - |
| all-at-once | HyperQ | 54s | 178s | 8.4x / 3.8x |
| all-at-once | HyperQ space+time | 47s | 139s | **9.7x / 4.9x** |
| poisson | HyperQ | 143s | 230s | 3.2x / 3.0x |

### 利用率（Table 4）

| 到达模式 | 配置 | small-only | small&med |
|---------|------|------|------|
| all-at-once | IBM Quantum | 3.3% | 7.8% |
| all-at-once | HyperQ space+time | **35%** | **46%** |
| poisson | HyperQ | 10% | 26% |

### 延迟（Table 5，平均，秒）

| 到达模式 | 配置 | small-only total | small&med total | 提升倍数 |
|---------|------|------|------|------|
| all-at-once | IBM Quantum | 229s | 342s | - |
| all-at-once | HyperQ | 30s | 101s | 7.6x / 3.4x |
| poisson | HyperQ | 3.7s | 12s | **43x / 20x** |

### 保真度（Table 6）

| 配置 | avg L1（all-at-once）| avg L1（poisson）|
|------|------|------|
| IBM Quantum | 0.55 | 0.55 |
| HyperQ | 0.55 | 0.57 |
| HyperQ noise-aware | 0.54 | **0.50** |

- 空间调度不引入额外噪声（平均 L1 与 IBM Quantum 相当）
- 时间调度因 mid-circuit measurement/reset 引入额外噪声（L1 略升至 0.64），但随硬件改进可降低
- Noise-aware 调度在 Poisson 到达模式下保真度提升约 10%

**真实体验**：直接使用 IBM Quantum 运行两个基准分别耗时 19 小时和 40 小时；HyperQ 通常仅需 2–3 小时，有时短至 5 分钟。

---

## 六、批判性分析

1. **利用率数字的欺骗性**：论文将"利用率提升 11x"作为亮点，但 IBM Quantum 基线利用率仅 3.3%，绝对值如此之低在很大程度上是因为量子程序本身很小（2–27 qubit vs. 127 qubit 机器），而非调度问题。HyperQ 的利用率上限也受外部碎片化限制——127-qubit Eagle 最多只能用到 85 个 qubit（9 个 qVM 区域），并非真正意义上的高利用率。

2. **基准规模过小，代表性存疑**：实验仅使用 2–27 qubit 的小程序，而真正的量子杀手级应用（如 Shor 算法、大规模量子化学）需要数百至数千 qubit。在这些场景下，一个程序就会占满整台机器，HyperQ 的收益趋近于零。

3. **噪声实验的合理性存疑**：为验证隔离性，论文使用"100 个随机 X/CX 门"的程序做对比实验（成功率 85% vs 81% vs 85%），差异仅 4 个百分点，且未报告置信区间。这一实验的统计显著性不够有力，难以支撑强隔离性的核心主张。

4. **前提假设过于乐观**：延迟评估假设"queue initially empty, no jobs from other users"，而实际上 IBM Quantum 公共队列竞争激烈。在 Poisson 模型下，HyperQ 将 3 个用户级并发作业合并为 1 个大作业，队列等待时间优势主要来自减少了排队次数，并非真正加速了执行。若系统负载高，HyperQ 的优势会大幅缩水。

5. **时间调度的实用价值受限**：Time scheduling 引入 mid-circuit measurement/reset，在当前 NISQ 硬件上这两个操作的错误率显著高于普通门，导致保真度下降（L1 从 0.55 升至 0.64）。作者承认需等待硬件进步，但这是当前方案的核心缺陷，而非轻描淡写的"future work"。

6. **可扩展性未经验证**：所有实验均在单台 127-qubit IBM Brisbane 机器上完成，未验证多机调度、跨机优化等场景，也未讨论 HyperQ 作为服务的控制平面开销。

---

## 七、总结

HyperQ 提出了量子虚拟机（qVM）抽象，利用真实量子计算机固有的拓扑重复结构，在运行时将多个量子程序通过空间+时间复用并行执行于同一台量子计算机上。相较于 IBM Quantum 的串行方案，HyperQ 将吞吐量和利用率提升达一个数量级，延迟最高降低 43 倍，且不损害保真度（噪声感知调度甚至可改善约 10% 的保真度）。其核心优势在于兼容现有编译器和云服务、无需硬件修改，代价是适用场景局限于使用少量 qubit 的 NISQ 小程序，面对未来大规模量子程序时效益将显著下降。
