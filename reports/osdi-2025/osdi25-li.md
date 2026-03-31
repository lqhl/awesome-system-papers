# Tintin: A Unified Hardware Performance Profiling Infrastructure to Uncover and Manage Uncertainty

**作者**：Ao Li, Marion Sudvarg, Zihan Li, Sanjoy Baruah, Chris Gill, Ning Zhang（Washington University in St. Louis）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/osdi25/presentation/li
**源文件**：[osdi25-li.pdf](../../papers/osdi-2025/osdi25-li.pdf)

---

## 一、背景

硬件性能计数器（Hardware Performance Counters, HPCs）是现代处理器提供的微架构事件测量机制，广泛应用于性能调优、资源编排、功耗分析、入侵检测等场景。Linux 的 `perf_event` 子系统是事实上的 HPC profiling 基础设施，被 PAPI、Intel EMON、VTune 等工具使用。

然而，现有 profiling 工具面临两个根本性挑战：（1）**测量精度问题**——感兴趣的事件类型（通常数十到数百种）远超可用 HPC 数量（通常 2-6 个/核），不得不采用 event multiplexing（时分复用），引入不可忽视的插值误差；（2）**归因灵活性问题**——现有工具仅支持 per-task 或 per-core 粒度的 profiling scope，无法灵活定义代码区域级别的 scope，且不同 scope 之间存在冲突导致事件饥饿。

---

## 二、要解决的问题

1. **Event multiplexing 引入显著误差**：当事件数超过 HPC 数量时，Linux `perf_event` 采用 round-robin 时分复用，通过插值估算总计数。实验显示，multiplexing 后报告的 LLC-load-misses 方差显著增大，平均误差可达 9.01%，最大误差超过 53%。现有的离线方法（多次运行程序分别测量不同事件子集再合并）不适用于在线决策场景（如动态资源编排）。

2. **Profiling scope 定义不灵活**：`perf_event` 只支持将事件绑定到 task（进程/线程）或 core，无法精确定义到代码区域（函数、基本块）级别。这导致事件被错误归因——例如 DMon 性能诊断工具在 Top-Down 分层分析时，因无法精确限定 scope 而将问题代码段的 Back-end Bound 行为淹没在其他正常代码中。

3. **Overlapping scope 冲突**：不同 scope 之间缺乏协调，per-core 事件优先调度后，per-task 事件可能被拒绝（starvation），导致部分事件完全无法被测量。

4. **误差不透明**：现有工具不向用户空间报告测量不确定性，应用程序无法知道 HPC 数据的置信度。

---

## 三、核心设计

Tintin 是一个内核级 HPC profiling 基础设施，由三个模块化组件构成，围绕两个关键 insight 设计：

### Insight 1：运行时量化并管理 multiplexing 不确定性

- 利用事件到达率的方差作为插值误差的代理指标
- 不同事件在不同执行阶段具有不同的方差特征，可通过动态调度分配更多 HPC 时间给高方差事件来降低整体误差
- 将不确定性信息报告给用户空间，首次让应用程序能感知测量置信度

### Insight 2：通过 indirection 统一异构 profiling 需求

- 提出 **Event Profiling Context (ePX)** 作为新的 OS 一等对象（first-class object）
- ePX 封装了特定 profiling scope 关联的所有事件，支持灵活定义（execution instance 或 code segment 级别）
- 多个 ePX 可以共享事件类型但独立维护计数和不确定性
- 统一管理所有 ePX，解决 overlapping scope 冲突

### 三组件架构

1. **Tintin-Monitor**：测量 HPC 数据同时实时计算不确定性，使用 Trapezoidal Area Method (TAM) 做插值，用加权 Welford 方法增量更新方差
2. **Tintin-Scheduler**：将 event multiplexing 建模为 elastic real-time scheduling 问题，求解最优 utilization 分配以最小化总不确定性
3. **Tintin-Manager**：管理 ePX 生命周期，翻译异构 scope 请求为统一格式，处理 scope 切换和冲突解决

---

## 四、实现细节

**Tintin-Monitor 实现**：
- 使用 Linux 内核的 `hrtimer` 驱动，复用 `perf_event` 已有的 PMU 硬件读写接口
- 方差初始化通过 warm-up 期间的 round-robin 调度完成，之后每次 HPC 读取时用 Welford 方法增量更新
- 全部使用 64-bit 整数运算避免内核浮点操作，手动调优运算顺序防止溢出

**Tintin-Scheduler 实现**：
- 将多 HPC 的 elastic scheduling 问题转化为：将多个 HPC 拼接成单一虚拟资源，顺序分配事件时间片，防止同一事件被分配到多个 counter
- 优化求解复杂度：原始 solver 是 O(n²)，通过先按不确定性排序（高不确定性事件不会产生负 utilization）实现单遍计算，整体复杂度降为 O(n log n)
- 设置最小调度量子为 hyperperiod 的 1/10，避免过小时间片带来的不稳定估计
- 支持 event group：一组事件作为整体调度，保证同时测量

**Tintin-Manager 实现**：
- ePX 的所有 API 实现为系统调用（共 9 个），并提供 C 封装
- 通过 LLVM compiler pass 自动在编译期插入 ePX 进入/退出的系统调用，支持函数级和基本块级粒度
- ePX 切换时：代码区域 scope 通过插桩 syscall 触发，execution instance scope 通过监听 CPU scheduling 事件触发
- 通过 `procfs` 接口在 Tintin 和传统 `perf_event` 之间切换，兼容现有应用

**代码开源**：内核部分 https://github.com/WUSTL-CSPL/tintin-kernel，用户态部分 https://github.com/WUSTL-CSPL/tintin-user

---

## 五、实验结果

实验平台：双路 Intel Xeon Gold 6130 (Skylake)，16 物理核/CPU，32GB RAM，Hyper-Threading 关闭。默认 hyperperiod 4ms，scheduling quantum 0.4ms。

### Case Study 1：Pond 云资源编排

| 指标 | 结果 |
|------|------|
| Flexible Scope | Tintin 在 100 组实验中 95 组优于 EMON 基线，平均预测分数提升 0.51 |
| Elastic Scheduling | 64/100 组实验优于 round-robin，平均预测分数提升 0.15 |
| 加入 Uncertainty 信息 | 55/100 组实验进一步改善，平均分数提升 0.02 |
| Scope 冲突解决 | 计数误差仅从 3.11% 增至 3.56%，预测准确度降低 < 0.01，overhead < 2.4% |

### Case Study 2：DMon 性能诊断

- Linux `perf_event`：10 次实验中 9 次未能正确识别 Back-end Bound 问题（报告为 Frontend_Bound 39.0%）
- Tintin：目标函数一致报告 96.8% Backend_Bound，准确识别数据局部性问题

### Case Study 3：Diamorphine Rootkit 入侵检测

| 方法 | AUC |
|------|-----|
| Linux `perf_event` | 0.57 |
| Tintin (无 uncertainty) | 0.66 |
| Tintin (含 uncertainty) | 0.70 |

### 测量精度（SPEC 2017 + PARSEC）

| 方法 | 平均误差 | 最大误差 |
|------|---------|---------|
| Linux `perf_event` | 9.01% | 53.27% |
| CounterMiner | 8.80% | 56.21% |
| Uncertainty-First | 6.51% | — |
| Tintin Elastic | 2.91% | < 5%（多数） |

**精度提升 3.09×**（相对于 state of the art）。

### 运行时开销

| 方法 | 平均开销 | 最大开销 |
|------|---------|---------|
| BayesPerf (CPU) | 最高 31.3% | — |
| Linux `perf_event` | 1.9% | 12.7% |
| Tintin | 2.4% | 7.6% |

### 可扩展性

- Hyperperiod：1ms 时误差仅 0.2%，15ms 时 1.01%，overhead < 5%
- Scheduling quantum：0.5ms 时误差稳定在 0.6%，更小量子 overhead 增加明显（0.05ms 时 > 7.5%）
- 事件数量：512 事件时误差 < 5.4%；1024 事件时可能导致内核无响应（排序时间超过 jiffy）

---

## 六、批判性分析

1. **Ground truth 获取方式的局限性**：论文通过将单个事件 pin 到专用 HPC 来获取 ground truth，但这只验证了单事件计数精度，无法验证多事件同时测量时的整体系统行为。在真实场景中用户关心的是所有事件同时准确测量，而非某个事件的单独精度。

2. **Case study 的说服力有限**：
   - Pond 实验使用的是开源 emulation layer 而非真实 Pond 系统，模型和数据都是自行重建的，与原始论文中的效果可能存在差距
   - DMon 的改善主要归功于 ePX 提供的精确 scope，而非 multiplexing 优化——这更像是一个 API/抽象层面的改进而非系统层面的突破
   - Rootkit 检测的 AUC 从 0.57 提升到 0.70，绝对值仍然不高，论文自己也承认 HPC-based 入侵检测存在固有局限

3. **可扩展性瓶颈**：1024 事件时内核无响应是一个严重的 robustness 问题。虽然论文声称实际使用通常 < 256 事件，但作为内核基础设施，任何可能导致系统不响应的代码路径都不应存在。这暴露了在内核关键路径（CPU context switch）中执行 O(n log n) 排序的设计缺陷。

4. **PMU 架构限制未解决**：论文承认某些 PMU 限制某些事件只能分配到特定 HPC（restricted assignment），elastic scheduling 的最优性不再成立。在 Intel 等主流平台上这种限制普遍存在，削弱了最优性保证的实际价值。

5. **仅支持源码级别的 scope 定义**：当前 ePX 依赖编译期 LLVM pass 插入 syscall，不支持二进制级别的 instrumentation（论文将其留为 future work）。这大大限制了对闭源软件和生产环境的适用性。

6. **Uncertainty 报告的实际价值存疑**：在三个 case study 中，uncertainty 信息带来的增量改善很小（Pond 仅 +0.02，rootkit AUC 仅 +0.04）。这说明 elastic scheduling 本身已经将不确定性压得很低，再向应用层暴露其意义有限——这反而是对 "uncertainty-aware application" 这个 selling point 的自我削弱。

---

## 七、AI Infra / MLSys 视角

1. **GPU/Accelerator Profiling 的启发**：Tintin 的核心思想——运行时量化 profiling 不确定性并据此调度测量资源——可以直接迁移到 GPU profiling 场景。NVIDIA GPU 的 SM performance counters 同样面临 multiplexing 问题（NSight 需要多次 kernel replay），如果能在 GPU driver 层实现类似的 uncertainty-driven scheduling，将显著提升 AI workload 的在线性能分析能力。

2. **对分布式训练 profiling 的价值**：在大规模分布式训练中，profiling 开销和精度的 tradeoff 更加关键。Tintin 的 ePX 抽象可以扩展到跨节点场景，为不同的 collective communication 阶段、不同的 pipeline stage 定义独立的 profiling context，实现更精准的性能瓶颈定位。

3. **AI 推理系统的资源编排**：Tintin + Pond 的 case study 展示了 HPC-based latency sensitivity 预测在内存资源编排中的应用。类似方法可用于 LLM serving 系统中的 KV cache 管理——通过实时监测内存访问模式和 cache miss 特征，动态决定 KV cache 的 offload/prefetch 策略。

4. **可操作的 Future Work**：
   - 将 elastic scheduling 理论扩展到 GPU PMU 的受限分配场景（restricted counter assignment）
   - 在 eBPF 框架中实现 uncertainty-aware profiling，降低内核侵入性
   - 结合 Tintin 的 uncertainty 信息与 ML 编译器的 auto-tuning，实现 measurement-uncertainty-aware 的性能模型训练

---

## 八、总结

Tintin 是一个内核级硬件性能计数器 profiling 基础设施，通过三个模块化组件解决了 event multiplexing 误差和 profiling scope 不灵活两个长期存在的问题。其核心贡献包括：运行时不确定性量化与报告机制、基于 elastic real-time scheduling 的最优事件调度算法（精度提升 3.09×），以及 ePX 作为新的 OS 抽象统一管理异构 profiling 需求。系统在 SPEC 2017 和 PARSEC 基准上验证了低开销（2.4%）和高精度，并通过 Pond、DMon、Rootkit Detection 三个 case study 展示了实际应用价值。主要局限在于可扩展性（1024 事件时内核不响应）、仅支持源码级 scope 定义、以及 restricted PMU assignment 下最优性保证失效。
