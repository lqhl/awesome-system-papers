---
type: paper
name: Tintin
full_title: "Tintin: A Unified Hardware Performance Profiling Infrastructure to Uncover and Manage Uncertainty"
authors: [Ao Li, Marion Sudvarg, Zihan Li, Sanjoy Baruah, Chris Gill, Ning Zhang]
venue: OSDI
year: 2025
tags: [profiling, hardware-counters, operating-systems, linux-kernel, real-time-scheduling]
source_pdf: "[[osdi25-li.pdf]]"
source_md: "[[osdi25-li]]"
---

# Tintin: A Unified Hardware Performance Profiling Infrastructure to Uncover and Manage Uncertainty (OSDI 2025)

> **一句话总结**：Tintin 把 HPC multiplexing 误差量化为 runtime uncertainty、用弹性实时调度最小化它，并通过 ePX 统一异构 profiling scope；相对 Linux perf 插值精度提升 3.09×，开销 ≤2.4%，Pond 延迟预测准确率 +64%。

## 问题与动机

现代 CPU 有上千种可编程 HPC 事件，但每核仅 2–6 个物理计数器。`perf_event` 时间片轮转 + 插值估计带来不透明误差；scope 仅限 per-task/per-core，代码区域、重叠 scope 会 starvation 或误归因——DMon、Pond 等在线决策系统因此误测。

## 关键观察 / 隐含假设

- **观察 1**：multiplexing 下事件计数方差与插值误差强相关——可为每个事件维护 incremental variance（Welford），作为 ground truth 不可得时的 uncertainty 代理。
  - **依赖假设**：未监控区间事件率变化可用线性/trapezoid 插值 + 方差外推近似；毫秒级相位变化可被 1ms 粒度捕获。
  - **可能失效场景**：极短突发、非平稳过程方差非线性缩放失效；architectural skid/corruption（论文明确 out of scope 部分）。
- **观察 2**：高方差事件分配更多 HPC 时间片可最小化总体 uncertainty——问题等价于 elastic real-time scheduling，可证最优。
  - **依赖假设**：事件 utilization 分配与 future unmonitored time 成比例关系成立。
  - **可能失效场景**：事件数远超计数器且全部高方差时，任何调度都误差大。
- **假设 1**：应用能消费 uncertainty（规则阈值或 ML 特征）并改进决策。
  - **证据强度**：中强；Pond +64%、rootkit AUC +22.8%、DMon push-button 案例有支撑。

## 核心方法

三模块：**Tintin-Monitor**（TAM 插值 + variance uncertainty）、**Tintin-Scheduler**（最小化 Σ wᵢVᵢ(1-Uᵢ)² 的拟线性调度）、**Tintin-Manager**（**ePX** Event Profiling Context 统一管理重叠 scope，联合调度事件）。

扩展 perf API：显式 scope + uncertainty 回传 user space——据作者称首个向应用报告 HPC 不确定性的基础设施。

## 设计取舍

- **取舍 1**：不消除 polling vs sampling 的固有误差——与 multiplexing uncertainty 正交，兼容两者。
- **取舍 2**：内核 hrtimer 驱动 monitor——精度与开销平衡，依赖 perf 底层 PMU 接口。
- **边界条件**：仅硬件事件；SMT 减半有效计数器；watchdog 占 1 个 HPC。

## 实验与结果

- SPEC2017 + PARSEC：相对 perf 插值 3.09× 更准确；运行时开销 ≤2.4%。
- Pond：latency sensitivity 预测准确率 +64%（加入 uncertainty 特征）。
- DMon：灵活 ePX 改善 data locality 诊断。
- Diamorphine rootkit：分类 AUC +22.8%。

## Critical Analysis

### 论证链条

「方差代理 uncertainty → 最优调度 → 应用侧消费」在 case study 与 benchmark 上形成闭环。3.09× 精度提升是特定 benchmark/事件集上的倍数，外推为「所有在线 HPC 应用必然更好」需更多 production trace。

### 假设压力测试

- **已证明**：multiplexing 是 leela_r 等 workload 计数不稳定主因之一；uncertainty-first 调度优于 round-robin。
- **可能失效**：事件数接近 CounterMiner 150+ 时仍不够；ePX 联合调度在极高并发 profiler 下的公平性论文未充分展开。
- **论文未覆盖**：ARM 大规模部署、虚拟化嵌套 PMU、energy/power 联合优化。

### 实验可信度

Case study 替换现有工具链，集成成本「minimal」自述；SPEC 子集代表性尚可但非全 1623 Haswell 事件。缺长期 production A/B（仅功能验证级 case study）。

### 系统性缺陷

Variance 非真误差上界；应用需改逻辑才能用 uncertainty；ePX 语义学习曲线；与第三方 perf 工具生态兼容性论文未讨论。

## 局限与 Future Work

- **局限 1**：architectural uncertainty（skid、HT corruption）不处理。
- **局限 2**：ground truth 不可得，uncertainty 是启发式代理。
- **Future work 1**：在 cloud autoscaler 上 measurement——uncertainty-aware DVFS/资源编排的误调率下降多少。
- **Future work 2**：与 eBPF 可编程 scope 的联合设计与开销对比。

## 相关

- **相关概念**：hardware performance counters、perf_event、elastic scheduling
- **同类系统**：Linux perf、PAPI、DMon、Pond
- **同会议**：[[OSDI-2025]]