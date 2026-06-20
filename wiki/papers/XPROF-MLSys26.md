---
type: paper
name: XPROF
full_title: "XPROF: An Open, Scalable, and Extensible Profiling System for the Modern ML Stack"
authors: [Robert Hundt, Naveen Kumar, Jose Baiocchi Paredes, Scott Goodson, Clive Verghese, Prasanna Rengasamy, Kelvin Le, Jiya Zhang, Charles Alaras, Yin Zhang, Kan Cai, Jiten Thakkar, Sai Ganesh Bandiatmakuri, Yogesh SY, Aniruddha N Udipi, Vikas Aggarwal]
venue: MLSys
year: 2026
tags: [profiler, openxla, xla, tpu, gpu, distributed, performance]
source_pdf: "[[c74d97b01eae257e44aa9d5bade97baf.pdf]]"
source_md: "[[c74d97b01eae257e44aa9d5bade97baf]]"
---

# XPROF: An Open, Scalable, and Extensible Profiling System for the Modern ML Stack (MLSys 2026)

> **一句话总结**：面向 OpenXLA/JAX 全栈的 XPROF 统一 host（TraceMe）与 device（XLA/HLO/硬件计数器）剖析，千芯片规模开销 **<1%**，GTC 跨芯周期级对齐；PJRT C API 插件可扩展加速器，提供 roofline、HLO graph、TraceViewer 等分层工具，支撑 Google 内部效率优化与 MLPerf 成绩。

## 问题与动机

十亿参数级 [[LLM]] 训练/推理跨 **数千 accelerator**、数月运行，瓶颈可能落在 compiler fusion、collective、input pipeline、功耗节流等任一环节。传统 perf 工具难把 **硬件事件映射回模型代码**，且全量 tracing 在 AI hypercomputer 上数据爆炸。

XPROF 目标：让 model 研究者到硬件架构师都能在 **各自领域** 获得可行动优化建议，而非仅 raw trace。

## 关键观察 / 隐含假设

- **观察 1：host 侧细粒度 Dynamo/Pin 类 instrumentation 在超算规模 ROI 低——缺 accelerator 上下文且数据量失控。**
  - **依赖假设**：ML 性能主战场在 device；CPU 只需覆盖 JIT、调度、数据加载等「必要区域」。
  - **可能失效场景**：input-bound 小模型或重度 Python 逻辑时 host 仍关键——XPROF 用 Input Pipeline Analyzer + host pprof 补充。

- **观察 2：TraceMe「connect-the-dots later」——运行时只传 thread-local 小 id，后处理拼接端到端子 trace，可把 host trace 压到 **KB/s** 级。**
  - **证据强度**：**中高**——非阻塞 CAS 激活、thread-local 块、FIFO 收集，设计针对 framework hot path。
  - **可能失效场景**：极高频小 op 全量 TraceMe 仍可能膨胀，需 verbosity 控制。

- **观察 3：XLA 编译期注入 HLO metadata + TPU ISA trace slot，可把 device 周期精确对应到 HLO op 与源码，是 root-cause 关键。**
  - **依赖假设**：profile 请求时 JIT module/debug info 可用；TPU v2+ 硬件 trace 启用时零开销 no-op 未启用。
  - **可能失效场景**：非 XLA 路径（纯 PyTorch eager）需 PJRT 插件另行接入。

- **假设 1：MapReduce 式分布式收集 + TraceViewer 动态渲染可支撑 GB 级 trace 交互，工作负载开销仍 **<1%**（TPU 千芯）。**
  - **可能失效场景**：极长窗口全计数器采样仍可能扰动；论文强调可配置采集范围。

## 核心方法

**工作流**：ProfileRequest（gRPC/HTTP 或代码注解）→ Collector 多源采集 → 持久化 → Analysis Server 符号化/聚合 → Web UI 或 Python API。

**三层工具**（Table 1）：
- **High**：Overview、Input Pipeline Analyzer、Framework Op Stats、**Roofline**。
- **Mid**：HLO Graph Viewer、HLO Op Profile、Memory Viewer、host pprof。
- **Low**：Trace Viewer（host+device 时间线）、host/device perf counters、power/thermal telemetry、Utilization Viewer、Memory Profile。

**TraceMe**：C++/Python RAII/context manager；默认只 trace 昂贵 op；可嵌 JAX graph id；原子全局开关 + TLS 块分配。

**Device**：runtime always-on hooks（init/schedule/shutdown）；XLA 插入 trace 指令；GTC 跨芯片同步；compiler 生成 FLOPS/bytes 成本模型。

**可扩展性**：开源 **PJRT C API extension**，第三方 accelerator 接入统一 profiler 生态。

## 设计取舍

- **深度 XLA 集成 vs 通用 PyTorch profiler**：对 JAX/OpenXLA 栈极致友好，PyTorch 原生栈非主路径（虽提及 Kineto 类比）。
- **按需采集 vs always-on device hooks**：runtime 常开轻量 hook，重 profile 仍按需——平衡漏抓 mid-flight program 与开销。
- **建议式 Overview vs 纯专家工具**：默认页指向 next step，降低学习曲线，可能简化极端 case。
- **Google/TPU 起源**：GPU/Nsight 集成有，但叙事与案例偏 TPU/MLPerf。

## 实验与结果

论文以 **设计 + 生产影响** 为主，非 microbenchmark 竞赛：

- **Overhead**：数千芯片 monitoring **<1%** workload impact（abstract/§1）。
- **影响**：Google 内部显著效率提升、MLPerf 提交获胜（§1）；TraceMe **KB/s** 级 host 体积。
- **开源**：https://github.com/openxla/xprof

具体数值案例分散在 success stories（compiler placement、collective 瓶颈、thermal throttling 关联等），强调 **actionable** 优化闭环而非单一 speedup 数字。

## Critical Analysis

**强项**：少有的 **full-stack ML profiler** 产品级论述——从 TraceMe 低开销哲学到 HLO↔hardware symbolization 到 roofline/power；PJRT 插件化对多硬件时代重要；MapReduce 后端匹配 hyperscale 训练现实。

**弱点**：论文偏系统说明，独立研究者难量化「相对 Nsight/Kineto 快多少」；对 PyTorch 2 `/torch.compile` 生态覆盖有限；深度绑定 XLA 语义，非 XLA 用户收益递减；部分工具 Google 内部基础设施依赖（Grain、TPU ISA）外推需适配。

**受众**：OpenXLA/JAX/TPU 用户首选；GPU 用户可作参考架构。

## 局限与 Future Work

- 与 PyTorch Kineto、NVIDIA Nsight 更系统对比与互操作。
- 自动优化建议（非仅链接工具）的 ML 化。
- 更长窗口 continuous profiling 与存储成本。
- 多 framework 统一 symbolization（torch.export、FX graph）。

## 相关

- **Stack**：OpenXLA、XLA、JAX、PJRT
- **工具**：TraceMe、roofline model、TensorBoard profile、PyTorch Kineto
- **场景**：distributed training、MLPerf、LLM pretrain