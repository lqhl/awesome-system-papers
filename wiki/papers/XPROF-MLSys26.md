---
type: paper
name: XPROF
full_title: "XPROF: An Open, Scalable, and Extensible Profiling System for the Modern ML Stack"
authors: [Robert Hundt, Naveen Kumar, Jose Baiocchi Paredes, Scott Goodson, Clive Verghese, "et al."]
venue: MLSys
year: 2026
tags: [profiler, openxla, distributed-training, roofline, traceviewer]
source_pdf: "[[c74d97b01eae257e44aa9d5bade97baf.pdf]]"
source_md: "[[c74d97b01eae257e44aa9d5bade97baf]]"
---

# XPROF: An Open, Scalable, and Extensible Profiling System for the Modern ML Stack (MLSys 2026)

> **一句话总结**：OpenXLA 生态的统一 ML profiler，用 TraceMe 低开销 host 插桩 + GTC 跨芯片同步 + roofline 分析，在数千芯片 TPU 集群上 profiling 开销 <1%，下载量 10 个月增长 17×。

## 问题

优化千亿参数 LLM 在数千加速器上的端到端性能，需要模型开发者、框架/编译器工程师、硬件架构师同时理解 host-device 全栈行为。传统 profiler（perf、pprof、Nsight）要么只看 CPU、要么只看 GPU，难把硬件事件关联回高层模型代码，也无法在数千芯片规模下保持低开销和可操作的优化建议。

## 核心方法

XPROF 是 Google 开发、现属 OpenXLA 项目的全栈 profiler，核心设计：

- **Unified host-device profiling**：单一系统同时采集 CPU 与 TPU/GPU，把低层硬件事件链回 JAX/TensorFlow 高层代码。
- **TraceMe**：低开销 CPU 插桩原语，只标注关键区域，trace 体积约 KB/s 级，避免 Dynamo/Pin 式细粒度爆炸。
- **Deep compiler/hardware integration**：与 XLA 编译器和硬件后端深度集成，关联 HLO op 与硬件 perf counter。
- **GTC 分布式同步**：硬件 Global Timestamp Counter 跨数千芯片 cycle-accurate 对齐，精确诊断跨芯片通信与 host-device 交互。
- **MapReduce 式后端**：分布式采集与后处理，TraceViewer 动态渲染 GB 级 trace。
- **PJRT C API 扩展**：可插拔架构，第三方加速器厂商可接入。

工具分层：Overview / Input Pipeline Analyzer / Framework Op Stats / Roofline（高层）→ Graph Viewer / HLO Op Profile / Memory Viewer / Host pprof（中层）→ Trace Viewer / Device Perf Counters / Power & Thermals / Utilization Viewer（低层）。

## 关键结果

- 数千芯片监控，TPU 上 workload 开销 <1%。
- 在 Google 内部与 MLPerf 提交中实现显著效率提升。
- 开源下载量 10 个月增长 17×。
- 开源：https://github.com/openxla/xprof

## 相关

- **相关概念**：roofline model、XLA、distributed profiling、TraceMe
- **同类系统**：PyTorch Profiler、NVIDIA Nsight Systems、TensorBoard Profiler
- **同会议**：[[MLSys-2026]]