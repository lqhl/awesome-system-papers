---
type: paper
name: Chakra
full_title: "Chakra: Advancing Performance Benchmarking and Co-design using Standardized Execution Traces"
authors: [Srinivas Sridharan, Taekyung Heo, Louis Feng, Zhaodong Wang, Matt Bergeron, Wenyin Fu, Shengbao Zheng, Brian Coutinho, Saeed Rashidi, Changhai Man, Tushar Krishna]
venue: MLSys
year: 2026
tags: [benchmark, distributed-training, co-design, execution-trace, simulation]
source_pdf: "[[34173cb38f07f89ddbebc2ac9128303f.pdf]]"
source_md: "[[34173cb38f07f89ddbebc2ac9128303f]]"
---

# Chakra: Advancing Performance Benchmarking and Co-design using Standardized Execution Traces (MLSys 2026)

> **一句话总结**：Chakra 用开放图 schema 标准化 ML 执行 trace（ET），配套 converter/visualizer/generative 合成与 ASTRA-sim 仿真，让厂商在不泄露模型细节下做 HW-SW co-design 与性能投影。

## 问题

MLPerf 等全量 benchmark 适合已部署系统对比，但 AI 创新节奏要求更敏捷的 co-design 方法。厂商间无法共享完整 workload（IP 限制），硬件方只能猜参数，学术与初创难以参与真实生产 workload 设计。各框架 ET 格式不一，缺少统一交换 schema 与 toolchain。

## 核心方法

**Chakra ET schema**：最小可扩展节点（compute/memory/comm + dependency），支持 pre/post-execution 采集。

**采集与合成**：扩展 PyTorch Execution Graph Observer 采集真实 trace；用 hierarchical generative model 从生产 trace 学习分布并合成可脱敏 ET。

**开源工具链**：ET converter（PyTorch/FlexFlow→Chakra）、visualizer、timeline visualizer、test case generator、trace feeder（供 simulator 解析）。

**用例**：replay benchmark、ASTRA-sim-v2 性能投影（扩 NPU 数、变网络带宽），以及 embedding sharding / iteration latency 等组件级建模。

## 关键结果

- 端到端 PoC：PyTorch ET → Chakra ET → ASTRA-sim 驱动训练仿真
- Transformer 在 2D-torus 上扩 NPU 可持续提升性能；MLP-MP 受 exposed communication 主导，扩 NPU 反而变慢
- 网络带宽敏感性：MLP-MP 在最低带宽下 exposed comm 可达总计算 **128×**
- 合成 collective trace 可在训练集群上正确 replay

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Expert-Parallelism]]
- **同类系统**：MLPerf、ASTRA-sim、PARAM replay
- **同会议**：[[MLSys-2026]]