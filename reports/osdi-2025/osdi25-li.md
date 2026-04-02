# Tintin: A Unified Hardware Performance Profiling Infrastructure to Uncover and Manage Uncertainty

**作者**：Ao Li, Marion Sudvarg, Zihan Li, Sanjoy Baruah, Chris Gill, Ning Zhang（Washington University in St. Louis）
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/li
**源文件**：[[osdi25-li.pdf]]

---

## 一、背景

硬件性能计数器（Hardware Performance Counters, HPCs）是现代处理器中用于测量微架构事件（如 cache miss、branch misprediction 等）的核心机制，广泛应用于性能调优、资源编排、入侵检测等场景。Linux 的 perf_event 子系统是事实上的 HPC 访问接口，被 PAPI、Intel EMON、VTune 等工具广泛使用。

然而，现有 HPC profiling 基础设施在**测量**和**归因**两个维度都存在根本性不足：测量层面，事件数量（数十到数百种）远超可用 HPC 数量（通常 2-6 个），依赖 event multiplexing 的时分复用会引入不可忽视的误差；归因层面，现有工具只支持按 task 或 core 粒度的 profiling scope，无法满足函数级、代码段级等灵活的归因需求。

---

## 二、要解决的问题

1. **Event multiplexing 引入的测量误差**：当事件数超过 HPC 数量时，perf_event 以 round-robin 方式时分复用 HPC，通过插值估算总计数。实验表明，multiplexing 后报告的 LLC-load-misses 标准差可达非 multiplexing 情况的数倍，严重影响依赖 HPC 数据做在线决策的应用（如动态资源编排）。

2. **Profiling scope 不灵活导致事件归因错误**：perf_event 只支持 per-task 和 per-core 两种粒度。对于需要 profiling 特定代码区域（如循环体、函数）的场景，用户被迫采用整个 task 级别的 profiling，导致目标代码段的事件被其他代码段的事件淹没。DMon 就是典型案例：它需要逐层 profiling Top-Down 指标，但因 scope 不灵活导致 Back-end Bound 问题被 Front-end 事件掩盖。

3. **Overlapping scopes 导致事件饥饿**：当不同用户/应用的 profiling scope 在时间和事件类型上重叠时，perf_event 因不感知 scope 之间的关系，会导致后注册的事件被拒绝调度（starvation）。例如 per-core 事件优先于 per-task 事件，即使它们监控相同的事件类型。

4. **误差不可见**：现有工具不向用户报告 multiplexing 引入的不确定性，应用无法判断 HPC 数据的可信度。

---

## 三、洞察与设计

**关键洞察**：

1. **Multiplexing 误差可以在运行时通过方差来量化，并反馈给应用用于决策**。插值的本质假设是事件率线性变化，而实际的非线性程度可以通过观测到的事件率方差来近似，从而估计误差上界。
2. **不同事件在不同执行阶段表现出不同的方差特征，为差异化调度提供了机会**。例如 L1-dcache-load-misses 可能在某段时间剧烈波动，而 bus-cycles 保持稳定——将更多 HPC 时间分配给高方差事件可以降低总体误差。
3. **引入一层间接层（indirection）可以统一管理异构的 profiling 需求**。通过将 profiling scope 提升为一等 OS 对象（Event Profiling Context, ePX），可以统一定义、管理和调度来自不同应用、不同粒度的 profiling 请求。

基于这些洞察，Tintin 采用三组件模块化设计：

- **Tintin-Monitor**：在测量 HPC 数据的同时，利用加权 Welford 方法增量计算事件率的方差，以此作为不确定性的代理指标。使用 Trapezoid Area Method (TAM) 进行插值，是在线插值中精度最高的方法。
- **Tintin-Scheduler**：将 event multiplexing 建模为弹性实时调度问题（elastic real-time scheduling），根据 Tintin-Monitor 报告的方差为每个事件分配差异化的 HPC 时间份额，目标是最小化总体预期误差。算法被证明是最优的，复杂度为准线性。
- **Tintin-Manager**：引入 ePX 作为新的 OS primitive，提供统一的 API 来定义任意粒度的 profiling scope（函数级、basic block 级、跨线程聚合等），并在内核中集中管理所有 ePX，解决 scope 冲突。

---

## 四、实现细节

- **内核修改**：Tintin 作为 Linux 内核基础设施实现，三个组件均在内核空间运行。代码开源：[tintin-kernel](https://github.com/WUSTL-CSPL/tintin-kernel) 和 [tintin-user](https://github.com/WUSTL-CSPL/tintin-user)。
- **Tintin-Monitor**：通过 Linux hrtimer 触发，拦截 perf_event 的 HPC 读取函数，在读取原始计数的同时执行 TAM 插值和方差更新。方差用 Welford 增量算法更新，避免重新遍历历史数据。为避免内核中的浮点运算，使用 scaling factor + 64 位整数除法实现定点精度。
- **Tintin-Scheduler**：将弹性调度问题转化为：每个事件有一个 utilization 值（占用 HPC 的时间比例），loss 函数 ℒ_i(U_i) 表示 multiplexing 带来的误差（与方差成正比，与 utilization 成反比）。通过求解约束优化问题（总 utilization ≤ HPC 数量），得到最优的 utilization 分配。扩展了经典弹性调度理论到多 HPC 场景。支持 event grouping（保证同组事件同时调度）。
- **Tintin-Manager API**：提供 8 个系统调用（tintin_create_context、tintin_enable/disable_context、tintin_add/remove_event、tintin_set_event_weight、tintin_associate_contexts、tintin_read_with_uncertainty）。配合 LLVM compiler pass 可自动在函数/basic block 边界插入 instrumentation。
- **默认参数**：hyperperiod = 4ms（对齐 Linux 调度间隔），scheduling quantum = 0.4ms。

---

## 五、实验结果

**平台**：dual Intel Xeon Gold 6130 (Skylake)，每 CPU 16 物理核，32GB RAM，Hyper-Threading 关闭，每核 4 个通用 HPC。

### Case Study 1: Pond 资源编排

| 指标 | 结果 |
|------|------|
| Profiling scope 改进 | Tintin 在 100 组实验中 95 组优于 EMON 基线，平均预测准确度提升 0.51 |
| Elastic scheduling | 100 组中 64 组优于 round-robin，平均预测分数提升 0.15 |
| Uncertainty 信息 | 加入 uncertainty 后 55/100 组进一步改善，平均分数提升 0.02 |
| Scope 冲突 | 冲突场景下计数误差仅从 3.11% 升至 3.56%，预测准确度平均下降仅 0.01 |

### Case Study 2: DMon 性能调试

- 使用 perf_event 时，DMon 10 次实验中 9 次**无法**正确识别 Back-end Bound 问题（被 Front-end 事件掩盖）
- 使用 Tintin 的 loop-level ePX，目标函数 Backend_Bound 占比一致超过 91.1%，可靠检出数据局部性问题

### Case Study 3: Diamorphine rootkit 入侵检测

| 方法 | AUC |
|------|-----|
| Linux perf_event | 0.57 |
| Tintin (elastic scheduling) | 0.66 |
| Tintin + uncertainty | 0.70 |

### 综合 Benchmark（SPEC 2017 + PARSEC）

| 方法 | 平均误差 | 最大误差 |
|------|---------|---------|
| Linux perf_event | 9.01% | 53.27% |
| CounterMiner | 8.80% | 56.21% |
| Uncertainty-First (heuristic) | 6.51% | — |
| **Tintin (elastic scheduling)** | **2.91%** | **< 5% (大多数)** |

### 运行时开销

| 方法 | 平均开销 | 最大开销 |
|------|---------|---------|
| Linux perf_event | 1.9% | 12.7% |
| **Tintin** | **2.4%** | **7.6%** |
| BayesPerf (CPU) | — | 31.3% |

### 可扩展性

- Hyperperiod 1ms 时误差仅 0.2%，overhead < 5%
- Scheduling quantum 0.5ms 时精度趋于稳定（误差 0.6%）
- 事件数可扩展至 512（误差 < 5.4%），1024 时会导致内核无响应

---

## 六、批判性分析

1. **实验平台单一**：所有实验仅在 Intel Skylake 上进行，而论文声称支持跨架构（ARM 等）。ARM 平台的 PMU 特性、HPC 数量和行为可能有显著差异，缺乏验证使跨平台的通用性声明缺少支撑。

2. **Case study 的改善幅度参差不齐**：Pond 的 flexible scope 改进显著（0.51），但 uncertainty 信息仅带来 0.02 的边际提升；入侵检测的 AUC 从 0.57 到 0.70，虽有改善但绝对值仍偏低（接近随机猜测的 0.5）。论文将这些统一包装为 Tintin 的成功，但实际上不同场景的收益差异很大。

3. **方差作为误差代理的假设较强**：Tintin-Monitor 假设事件率方差可以作为插值误差的良好代理，但这依赖于事件率变化的近似线性性。对于高度非线性的工作负载（如频繁的执行阶段切换），方差可能低估或高估实际误差。论文未深入讨论这一假设的失效场景。

4. **1024 事件导致内核无响应**：Tintin-Scheduler 在事件数达到 1024 时会因排序耗时过长导致 CPU 调度器 miss deadline。虽然论文声称实际场景通常不超过 256 个事件，但这是一个潜在的可靠性问题，尤其在多个 ePX 同时活跃的复杂场景下。

5. **Ground truth 的获取方式有局限**：通过 pin 单个事件到专用 HPC 获取 ground truth，但这种方法本身会改变其他事件的调度行为。论文未讨论这种观察者效应对评估准确性的影响。

6. **系统调用开销未单独量化**：Tintin-Manager 引入了 8 个新系统调用，对于高频 profiling 场景（如 basic block 级别），系统调用本身的开销可能不可忽视，但论文未将其与 Tintin-Monitor/Scheduler 的开销分离评估。

---

## 七、AI Infra / MLSys 视角

1. **GPU profiling 的启发**：GPU 同样面临性能计数器有限但事件类型众多的问题（如 NVIDIA 的 SM warp scheduler 相关指标）。Tintin 的 uncertainty-aware multiplexing 思路可以迁移到 GPU profiling 场景，特别是在 Nsight Compute 等工具中引入类似的不确定性量化和报告机制。

2. **分布式训练中的性能归因**：大规模分布式训练（如 FSDP、Megatron-LM）需要精确归因通信、计算和内存操作的性能瓶颈。Tintin 的 ePX 概念——将 profiling scope 定义为一等对象——可以启发分布式训练 profiler 设计更灵活的归因粒度（如按 pipeline stage、按 tensor parallel group 归因）。

3. **推理服务中的在线资源调度**：vLLM 等推理框架需要实时监控 memory bandwidth、cache 行为来做调度决策（如 batch size 调整、KV cache eviction）。Tintin 将 uncertainty 反馈给应用的机制，可以帮助推理引擎在 HPC 数据不可靠时采取保守策略，避免因错误的性能数据做出糟糕的调度决策。

4. **值得跟进的方向**：将 elastic scheduling 的思想应用于 heterogeneous profiling（同时 profiling CPU + GPU + NPU 的场景），以及将 uncertainty-aware 的理念引入 ML workload 的 auto-tuning 系统（如 TVM、Triton），在 profiling 数据有噪声时做更鲁棒的搜索决策。

---

## 八、总结

Tintin 是一个面向 Linux 内核的 HPC profiling 基础设施，通过三个模块化组件解决了 event multiplexing 误差和 profiling scope 不灵活两大核心问题。其主要贡献是：(1) 首次在运行时量化并报告 HPC 测量的不确定性；(2) 将 event scheduling 建模为弹性实时调度问题并给出最优解；(3) 引入 ePX 作为新的 OS primitive 统一管理异构 profiling 需求。在 SPEC 2017 和 PARSEC benchmark 上，Tintin 以仅 2.4% 的额外开销将 multiplexing 误差从 ~9% 降至 ~3%。主要局限在于评估仅限 Intel Skylake 平台、事件数超过 512 时可扩展性受限，以及方差作为误差代理的理论假设在极端工作负载下可能不成立。
