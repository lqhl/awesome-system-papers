---
type: paper
name: μShell
full_title: "μShell: A Microkernel-based FPGA Shell Architecture"
authors: [Jiyang Chen, Anubhav Panda, Harshavardhan Unnibhavi, Atsushi Koshiba, Pramod Bhatotia]
venue: OSDI
year: 2026
tags: [fpga, microkernel, partial-reconfiguration, accelerator-composition, capability-isolation]
source_pdf: "[[osdi26-chen-jiyang.pdf]]"
source_md: "[[osdi26-chen-jiyang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-23
---

# 面向模块化加速器的微内核 FPGA Shell（OSDI 2026）

> **原题**：μShell: A Microkernel-based FPGA Shell Architecture

> **一句话总结**：现有 FPGA shell 把应用固化为单个 vFPGA 上的整体 bitstream，导致共享模块重复部署和频繁重配置；μShell 将硬件模块拆到多个 vFPGA，用 capability-enforced IPC 动态连接，并由组件感知调度器复用已加载模块，在 Alveo U280 上仅带来 3.3% 吞吐下降，同时将重配置次数最多减少 79%。

## 问题与动机

云 FPGA 通常把动态区域划分为多个隔离的 vFPGA，但现有 shell 多按“一个应用对应一个 vFPGA”设计。现实应用往往由多个独立任务组成，并且不同应用之间会复用相同函数。将这些任务静态合并为单一 accelerator 会重复实例化共享逻辑；修改一个模块也需要重新综合整体设计。

单一 vFPGA 还限制了 accelerator 的规模。Coyote v2 在 U280 上划分八个 vFPGA 时，每个区域只有整卡约 10.8%–12.5% 的资源。应用切换时若整体重配置，毫秒级甚至更高的重配置延迟会进入调度路径。论文因此提出：能否像微内核管理进程一样，把 FPGA accelerator 管理为可共享、可组合的硬件组件。

## 关键观察 / 隐含假设

- **观察 1：应用组件具有可复用性。** 对 Vitis Vision Library 的分析显示，最多 93% 的应用对共享函数，超过 20% 的应用对相关性高于 0.5（图 2）。部分共享模块可占应用资源使用量的 80%（图 5）。
  - **依赖假设**：模块接口和 bitstream 能够独立部署，且共享模块主要是无状态 accelerator。
  - **可能失效场景**：状态跨请求持续存在、模块接口不兼容或每个租户都需要定制逻辑时，复用收益会下降。
- **观察 2：模块间直接数据通路优于 CPU 驱动同步。** 对目标工作负载，直接通信最高达到 CPU 顺序调用方式的 3.7 倍（图 3）。
  - **依赖假设**：应用是流式 dataflow，模块间数据量和流水线并行性足以抵消路由与验证开销。
  - **可能失效场景**：小消息、强同步或共享互连拥塞时，动态 IPC 的开销可能超过收益。
- **假设 1：FPGA 不支持实用的抢占和上下文保存。** μShell 等待当前执行完成后再更新 capability，并依赖 accelerator reset 清理残留状态。
  - **证据强度**：强。设计和 §4.1 明确把非抢占性作为组件共享与调度约束。
  - **风险**：长运行或无法可靠 reset 的 stateful accelerator 会阻塞调度，并可能带来状态泄漏风险。

## 核心方法

μShell 将静态 shell 扩展为硬件—OS 协同系统。每个 vFPGA 配置一个 Capability Enforcement Unit（CEU），数据互连使用 AXI4-Stream Switch 在 vFPGA 与 host memory 之间建立动态路径（图 8）。CEU 的 send、receive 和 memory gateway 分别校验组件间通信端点及 DMA 地址范围。

OS 侧的 Capability Control Manager 为应用维护 capability space，支持创建、委派和撤销。应用只能把受限 capability 委派给 dataflow 节点；CEU 在硬件路径上执行检查，未授权请求会被丢弃并通知 OS。应用结束或进程退出时，相关 capability 被回收。

应用通过 C++ API 构造 dataflow graph：`create_task` 创建硬件任务，`create_buffer` 创建输入输出缓冲区，`connect` 描述依赖，`execute` 提交执行。运行库把图转换为 capability、MMU 页表、vFPGA 映射和 IPC 配置，开发者不必手工管理低层连接。

组件感知调度器采用非抢占策略。它先按优先级选择应用；同一优先级下，优先选择与空闲 vFPGA 上已加载逻辑重叠最多的应用，以减少 partial reconfiguration。等待超过阈值的请求会提升优先级，降低饥饿和尾延迟。由于当前 PR 工具链要求每个“逻辑—vFPGA”组合单独生成 bitstream，系统需要维护多个 bitstream 版本。

## 设计取舍

- **共享换取重配置成本**：μShell 仅支持安全复用无状态 accelerator；stateful 逻辑需要不共享或承担完整 reset 的工程成本。
- **动态性换取硬件资源**：CEU 和中心互连带来额外 LUT、寄存器和路由延迟。互连资源随 vFPGA 数量近似二次增长，八个 vFPGA 时 shell 额外资源达到 6.6%。
- **统一抽象换取 bitstream 管理复杂度**：任意 vFPGA 可承载组件的目标尚未完全实现；当前每个逻辑仍须针对每个 vFPGA 生成 bitstream，且原型采用均匀分区。

## 实验与结果

- 在 AMD Alveo U280、AMD EPYC 7413、Linux 6.9 上，μShell 使用五个由 FFT、quantization、AES-CTR、SHA256、RSA、RLE 组成的 kernel-level 流水线。相较 Coyote v2，平均 I/O 吞吐低 3.3%；单体版 μShell 与 Coyote 差异在 ±1.4% 内（图 11）。
- 在 8、12、16 个实例、每 20 ms 到达的排队负载下，组件感知调度使端到端延迟降低约 24%–35%，平均响应时间降低 21%–33%，P95 响应时间降低 28%–39%（图 12）。
- 重配置次数稳定在 5–7 次，Coyote v2 约为其 3–5 倍；deadline miss 降低 46%–64%（图 12）。
- 当所需组件已在 vFPGA 中时，μShell 只需更新 buffer 和 capability；单次对象或内存更新约 2–3 μs，而 Coyote 的 PR 约 58 ms（图 13）。
- API 使 host 代码的 cyclomatic complexity 降低 25.0%–51.2%，SLOC 变化为 -2.0% 至 +23.4%（表 5）。三 vFPGA 配置下，CEU 与互连仅占 LUT 的 1.4%、寄存器的 0.9%（表 6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 动态组件组合不会明显损害吞吐 | μShell 比 Coyote 平均低 3.3%（图 11） | U280、五个 kernel-level workload、host DRAM | 强 |
| 组件复用能减少调度代价 | 重配置次数减少约 3–5 倍，端到端延迟降低 24%–35%（图 12） | 三类共享组件应用、合成到达率、最多 16 实例 | 中 |
| capability 与动态 IPC 可在硬件上实现 | CEU/互连资源开销及吞吐结果（§5.1、§6.1、表 6） | 单 FPGA，最多八个 vFPGA；未测多 FPGA | 中 |
| API 降低控制代码复杂度 | cyclomatic complexity 降低 25.0%–51.2%（表 5） | 五个应用的等价 host 代码 | 中 |

## 批判性分析

### 论证链条

论文从模块重用和直接数据通路的测量出发，设计 CEU、动态 IPC 和组件感知调度，主结果也覆盖吞吐、重配置和尾延迟，整体链条闭合。调度实验的 PR 因 Coyote 多 vFPGA 中断处理问题而采用预加载组件并注入测得延迟，能保留重配置时间因素，但没有验证真实 PR 控制路径的并发与故障行为。

### 假设压力测试

收益依赖共享模块足够多且可 reset。论文的五个应用主要是 kernel-level workload，不包含完整端到端应用；生产环境中的模块状态、租户隔离和请求突发可能改变复用比例。中心互连在 vFPGA 数量增大时近似二次扩展，八个 vFPGA 的结果不能直接外推到更大规模。调度器不支持抢占，长任务会阻塞高优先级请求。

### 实验可信度

Coyote v2 是合理且实现成本可控的主要基线，但其他 shell 未在 U280 上比较。吞吐结果覆盖五个应用和三种数据大小，调度结果覆盖多种负载强度；不过 PR 被模拟，且没有多 FPGA、HBM 直连、真实生产 trace 或故障恢复实验。deadline 公式和优先级分配是实验设定，miss-rate 优势对这些设定的敏感性没有充分消融。

### 系统性缺陷

每个逻辑—vFPGA 对需要独立 bitstream，编译和发布管理仍可能成为主要运维成本。共享 stateful accelerator 需要可靠清空分布在 BRAM、寄存器等位置的状态，论文依赖 HLS reset 机制，未给出对任意 RTL 的覆盖保证。CEU 发现违规请求后会暂停执行并 drain stream，但恢复、租户级审计和错误隔离的完整行为未展开。互连拥塞、公平性以及 capability 表和硬件寄存器的一致性也未在高并发下评估。

## 局限与后续工作

- **局限 1**：原型采用固定、均匀的 vFPGA 分区，不能充分利用可变大小逻辑；论文也未解决 PR 区域不可互换带来的 bitstream 数量增长。
- **局限 2**：仅评估单 U280 FPGA，未验证跨 FPGA 的组件组合与网络通信。
- **后续工作 1**：结合可变 PR 区域和编译—物理布局解耦技术，测量 bitstream 数量、编译时间和碎片化对调度收益的影响。
- **后续工作 2**：对 stateful accelerator 实现形式化的状态清理或上下文保存，并在租户切换、异常终止和长任务下验证隔离与恢复。

## 相关

- **相关概念**：[[Partial-Reconfiguration]]、[[Capability-Based-Isolation]]、[[Dataflow]]、[[FPGA-Virtualization]]
- **同类系统**：[[Coyote]]、[[AmorphOS]]、[[vFPIO]]、[[Nyx]]
- **同会议**：[[OSDI-2026]]
