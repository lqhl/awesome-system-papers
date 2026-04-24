---
type: paper
name: Chakra
full_title: "Chakra: Advancing Performance Benchmarking and Co-design using Standardized Execution Traces"
authors: [Srinivas Sridharan, Taekyung Heo, Louis Feng, Zhaodong Wang, Matt Bergeron, et al.]
venue: MLSys
year: 2026
tags: [benchmark, trace, simulator, distributed-training, co-design]
source_pdf: "[[34173cb38f07f89ddbebc2ac9128303f.pdf]]"
source_md: "[[34173cb38f07f89ddbebc2ac9128303f]]"
---

# Chakra: Advancing Performance Benchmarking and Co-design using Standardized Execution Traces (MLSys 2026)

> **一句话总结**：Meta + Georgia Tech + HPE 提出的 Chakra——一个标准化的分布式 ML 执行图 schema、配套转换/可视化/模拟工具链，和基于生成式 AI 合成 trace 的方法，让 SW 公司把真实 workload 以 obfuscated trace 形式给 HW 厂商做 what-if co-design。

## 问题

ML 分布式训练的 HW-SW co-design 需要 workload benchmark，但：
- **MLPerf 等全量 benchmark** 只能在系统完全落地后做公平对比，太慢跟不上 AI 创新节奏。
- **IP 壁垒**：超大规模云厂商（DLRM@Meta 跑在 NVIDIA GPU 上）不能公开完整模型/数据，HW 厂商只能拿到 spreadsheet NDA 参数，导致过度优化少数用例。
- 不同 ML 框架（PyTorch、TensorFlow、FlexFlow）的 execution trace 格式各异，无法跨组织交换。

## 核心方法

**1. Chakra Execution Trace (ET) Schema**

- Graph 结构：node 有 `id / name / type / parent / attribute`；type enum 为 `COMP / MEM_LOAD / MEM_STORE / COMM_SEND / COMM_RECV / COMM_COLL / INVALID`。
- `attribute` 字段为 repeated AttributeProto（仿 ONNX），用 key-value 承载所有扩展元数据——minimal 但 extensible。
- 同时支持 pre-execution（不绑定具体系统，可做性能投影）和 post-execution（绑定真实系统）两种 trace 粒度。
- 每个 NPU 一份独立 trace。

**2. 生成式 AI 合成 trace**

- 聚焦通信部分先做。构造「master trace」——把一个 process group 内所有 rank 的 trace 无损压缩到一个 master 上，保证 replay 约束不被合成破坏。
- 分层生成模型：**Comm Type Generator**（从两类集合体分布中采样）+ **Message Size Generator**（每种 collective 用 GMM 拟合消息大小）+ 处理 GPU 数、序列长、split 模式等。
- 合成产物既能 obfuscate 生产数据（保 IP），又能投影到更大规模的未来系统。

**3. 开源工具链**

- **ET Converter**：PyTorch Execution Graph Observer / FlexFlow → Chakra ET（ONNX 和 TensorFlow 规划中）。
- **Visualizer**：graphviz/PDF 输出节点依赖。
- **Timeline Visualizer**：feed chrome://tracing，按 NPU 分泳道显示 compute/memory/communication。
- **Test Case Generator**：C++ 类库手工构造 trace（DP/MP/PP 示例）。
- **Trace Feeder**：C++ 库给 simulator 用（ASTRA-sim、SST 等）。

**4. 端到端 PoC**：PyTorch ET → Chakra ET → [[ASTRA-sim]] 驱动训练系统 simulation。

## 关键结果

- 开放 schema + 工具链已在 GitHub 开源，定位是 industry-wide 的 agile benchmark 生态基础。
- 合成 trace 在 replay 系统上可正确跑，分布与真实 trace 相匹配。
- 让 HW 厂商、学术界和 HW startup 能共同参与真实生产 ML workload 的 co-design，不再被 NDA 隔开。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]
- **同类系统**：MLPerf、ASTRA-sim、SST、FlexFlow、PyTorch Execution Graph Observer
- **同会议**：[[MLSys-2026]]
