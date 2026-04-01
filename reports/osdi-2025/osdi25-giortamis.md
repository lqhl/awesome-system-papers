# QOS: Quantum Operating System

**作者**：Emmanouil Giortamis, Francisco Romão, Nathaniel Tornow, Pramod Bhatotia（Technical University of Munich）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/osdi25/presentation/giortamis
**源文件**：[osdi25-giortamis.pdf](../../papers/osdi-2025/osdi25-giortamis.pdf)

---

## 一、背景

量子计算利用叠加和纠缠原理，有望在组合优化、密码学等领域实现指数级加速。当前量子处理器（QPU）已通过 IBM、AWS、Google、Azure 等云平台以 quantum-as-a-service 的方式对外提供服务。然而，当前 QPU 处于 NISQ（Noisy Intermediate-Scale Quantum）阶段，qubit 数量有限（数百量级）、噪声严重、硬件异构性高，且噪声特性随校准周期不可预测地变化。这些特性使得量子资源管理面临与经典计算截然不同的挑战：执行保真度（fidelity）随电路规模急剧下降（4→24 qubit 下降 98.9%），QPU 间保真度差异可达 38%，同一 QPU 在不同校准日的保真度波动可达 96.5%。

---

## 二、要解决的问题

1. **保真度下降**：NISQ 设备噪声累积使得大电路难以获得高保真度结果，且现有纠错技术各自独立、缺乏组合框架，指数级开销难以控制。
2. **时空异构性**：不同 QPU（即便同型号）噪声特性不同（空间），同一 QPU 每次校准后噪声也发生不可预测变化（时间），用户难以选择合适的 QPU。
3. **QPU 利用率低**：为保证高保真度，电路尺寸受限，27-qubit QPU 在保持 ≥0.75 fidelity 时平均利用率仅 26.3%。同时，简单的 multi-programming 会因 crosstalk 严重降低保真度。
4. **负载不均衡**：用户手动选择"最佳"QPU 导致热门 QPU 排队时间长达其他 QPU 的 57 倍，而性能差异并不总能justify 如此大的负载差异。
5. **缺乏统一系统**：现有方案各自为政（独立的纠错、独立的调度、独立的 multi-programming），缺少统一的、可组合的操作系统层。

---

## 三、洞察与设计

**关键洞察**：量子电路中的噪声并非均匀分布——部分 qubit 和 gate 是"噪声热点"（hotspot），对整体保真度的影响远超其他部分；同时，量子计算中保真度、利用率和等待时间之间存在根本性的多目标冲突，但这些冲突可以通过跨层协同优化来系统性地权衡。

基于这一洞察，QOS 设计了四层模块化架构，以 **Qernel 抽象**作为统一的执行单元贯穿各层：

1. **Error Mitigator（纠错层）**：组合 circuit cutting/knitting、qubit freezing 和 qubit reuse 三类技术。核心策略是用预算 b 限制指数开销，贪心地优先处理噪声热点。先用 qubit freezing 移除高连接度的热点 qubit，再用 circuit cutting 切分电路，最后用 qubit reuse 进一步缩减 qubit 需求。后处理采用 MapReduce 架构在经典节点上并行完成 knitting 计算。

2. **Estimator（估计层）**：不执行电路即预测各 QPU 上的保真度。提供数值计算策略（基于 readout error、gate error、T2 decoherence、crosstalk 的乘法模型）和回归模型策略两种可选方案。

3. **Multi-programmer（多路复用层）**：引入"有效利用率"概念（同时考虑空间占用和时间占用），定义 Qernel 兼容性评分（综合有效利用率、entanglement ratio、parallelism），并在共存电路间设置 buffer zone（1-2 个空闲 qubit）以降低 crosstalk。

4. **Scheduler（调度层）**：支持 formula-based 和 NSGA-II 遗传算法两种策略，多目标优化保真度、等待时间和利用率。

---

## 四、实现细节

- 基于 Qiskit Python SDK 实现，使用最高优化等级（level 3）进行电路编译，每次执行 8192 shots。
- Qernel 数据结构存储静态属性（电路宽度、深度、non-local gate 数、6 维 Supermarq 特征向量）和动态属性（执行状态、保真度估计、结果）。
- Error mitigator 预算默认 b=3，开销为 O(2^b) 到 O(8^b)；后处理的 knitting 阶段将 8^k 个 bitstring-weight pair 分配到 k 个经典节点上做 tensor product（支持 GPU/TPU 加速），再 reduce 为最终结果。
- Multi-programmer 兼容性公式：qc = αu_eff + βER_b + γPA_b，默认 α=0.25, β=0.25, γ=0.5，阈值 qc≥0.75。提供 restrict policy（无映射重叠时直接合并）和 re-evaluation policy（重叠时重新转译并评估）。
- Scheduler 的 formula-based 评分：score = c·(f2-f1)/f1 - (1-c)·(t2-t1)/t1 + β·(u2-u2)/u1，默认 c=β=0.5。遗传算法策略使用 NSGA-II 生成 Pareto front 后由同一公式选择最终方案。
- 代码开源：https://github.com/TUM-DSE/QOS

---

## 五、实验结果

**实验平台**：IBM Falcon r5.11 27-qubit QPU（主要使用 Kolkata），经典部分使用 64 核 AMD EPYC 7713P + 512GB 内存。数据集包含 7000+ 次量子运行、70,000+ benchmark 实例。9 个 benchmark 覆盖 QAOA、GHZ、BV、VQE 等。

| 组件 | 指标 | 结果 |
|------|------|------|
| Error Mitigator | 电路深度降低 | 平均 46%（vs Qiskit），38.6%（vs FrozenQubits），29.4%（vs CutQC） |
| Error Mitigator | CNOT 数量降低 | 平均 70.5%（vs Qiskit），66%（vs FrozenQubits），56.6%（vs CutQC） |
| Error Mitigator | 保真度提升（12 qubit） | 2.6×（vs Qiskit），1.6×（vs CutQC），1.11×（vs FrozenQubits） |
| Error Mitigator | 保真度提升（24 qubit） | 456.5×（vs Qiskit），7.6×（vs CutQC），1.67×（vs FrozenQubits） |
| Error Mitigator | 经典/量子开销（24 qubit） | 2.5× / 12× |
| Estimator | QPU 选择准确性 | 自动选择的 QPU 保真度与手动选最佳 QPU 持平或更优 |
| Multi-programmer | 保真度提升 | 9.6×（vs 无 multi-programming），1.15×（vs baseline [16]） |
| Multi-programmer | 有效利用率 | 平均高 7.2%，最高高 10.1% |
| Multi-programmer | 保真度损失 vs solo | 平均 9.6% |
| QOS 整体 vs 组合 baseline | 保真度 | 同利用率下高 48% |
| Scheduler（formula） | 等待时间 vs 保真度 | c=0.7 时等待时间降 5×，保真度仅降 ~2% |
| Scheduler（genetic） | 等待时间 vs 保真度 | c=0.5 时等待时间降 2×，保真度降 ~4% |
| Scheduler | QPU 负载均衡 | 最大负载差异 15.2% |

---

## 六、批判性分析

1. **456.5× 的保真度提升数字误导性极强**：24-qubit 电路在 Qiskit 基线上的绝对保真度极低（接近 0），此时微小的绝对提升都会产生巨大的相对倍数。论文未提供 24-qubit 场景下的绝对保真度值，读者无法判断提升后的结果是否实际可用。

2. **实验规模受限于单一硬件平台**：所有实验在 IBM Falcon 27-qubit QPU 上完成，且仅使用超导量子比特技术。论文声称系统是"hardware-agnostic"的，但未在其他架构（如离子阱、光量子）上验证。27 qubit 的 QPU 规模在 2025 年已显过时（IBM 已有 1000+ qubit 设备），系统在更大规模 QPU 上的表现仅通过假想的 1000-qubit QPU 模拟验证，缺乏真实硬件实验。

3. **Scheduler 评估基于 trace-based 模拟而非真实部署**：workload 来自 10 天的 IBM Cloud 监控数据，scheduler 的评估完全基于回放模拟。在真实多用户竞争环境中，调度决策与 QPU 状态的交互效应未被验证。

4. **Multi-programming 的 crosstalk 量化过于简化**：仅使用 entanglement ratio 和 parallelism 两个 Supermarq 特征向量来近似 crosstalk 影响，未使用实际的 crosstalk characterization 数据。buffer zone 限制为最多 2 个 qubit，这在更大 QPU 上是否足够值得商榷。

5. **Error mitigator 的技术组合并非普适最优**：论文仅组合了 circuit cutting、qubit freezing 和 qubit reuse 三种技术，而将其他技术（如 measurement error mitigation、zero-noise extrapolation）排除在外。贪心选择策略是否能在所有电路结构上接近最优缺乏理论保证。

6. **缺乏与 IBM 官方运行时优化的公平对比**：IBM 自身也在持续改进其云端服务的错误缓解和调度机制，论文使用的 Qiskit v0.41 可能不代表 IBM 平台的最新能力。

---

## 七、总结

QOS 是首个面向量子计算的整体性操作系统，通过 Qernel 抽象统一了纠错、保真度估计、多路复用和调度四个层次，系统性地权衡了保真度、利用率和等待时间之间的冲突。在 IBM 27-qubit QPU 上的实验表明各组件均优于独立基线，且跨层协同带来了额外增益。主要局限在于实验规模受限于 27-qubit 单一平台，大规模 QPU 和非超导架构上的适用性有待验证；部分高倍数改进建立在极低基线之上，实际意义需结合绝对值审慎判断。
