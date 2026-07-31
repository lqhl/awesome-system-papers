---
type: paper
name: TileLoom
full_title: "TileLoom: Automatic Dataflow Planning for Tile-Based Languages on Spatial Dataflow Accelerators"
authors: [Wei Li, Zhenyu Bai, Heru Wang, Pranav Dangi, Zhiqiang Zhang, et al.]
venue: OSDI
year: 2026
tags: [compiler, spatial-dataflow, accelerator, mlir, triton]
source_pdf: "[[osdi26-li-wei.pdf]]"
source_md: "[[osdi26-li-wei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 空间数据流加速器的自动数据流规划（OSDI 2026）

> **原题**：TileLoom: Automatic Dataflow Planning for Tile-Based Languages on Spatial Dataflow Accelerators

> **一句话总结**：TileLoom 将Triton式tile program自动展开为spatiotemporal mapping，并以MLIR硬件表示统一描述core、memory和NoC topology；在两代Tenstorrent系统上，多种kernel达到接近vendor TTNN library的性能，部分operator提升1.88×–2.06×。

## 问题与动机

spatial dataflow accelerator用分布式scratchpad与NoC转发数据，聚合片上bandwidth很高，但性能高度依赖tile在哪些cores、按何时序执行，以及数据在DRAM/L1/NoC如何复用。现有compiler多优化单tile codegen，跨core mapping仍靠vendor hand-tuned library，限制programmability和architecture portability。

## 关键观察 / 隐含假设

- tile-based language已经显式给出局部iteration/data access，是构造跨core reuse的合适输入，而非从任意tensor graph恢复。
- dataflow target可用spatial dimensions、compute unit throughput、distributed memory与affine interconnect mapping统一表达。
- 候选mapping的性能可由hierarchical compute/memory/network model筛选，再对少量top candidates codegen。
- static shape/kernel重复执行足以摊销planning；dynamic/irregular workload可能不适合。

## 核心方法

TileLoom在MLIR接收tile loops，生成spatial mapping（哪些tile instances分布到2D cores）和temporal order（单core执行顺序）。data reuse analysis对loop重排、multicast/forward和local buffering产生候选，既考虑parallelism也避免NoC/DRAM热点。

硬件IR用`df.spatial_dim`、`df.core`、`df.memory`、`df.interconnects`及matrix/vector units描述scaleout、capacity、bandwidth、topology和throughput。performance model分层估算compute、memory与network cost，考虑pipelined load/compute/store与并发link traffic，选取mapping后lower到Tenstorrent backend。

## 实验与结果

- 在两代Tenstorrent spatial accelerators上评估GEMM、[[Attention|attention]]及多个tile kernels，对比TTNN vendor library。
- 整体性能comparable to vendor libraries；部分attention/dataflow kernels相对TTNN提高1.88×–2.06×（图 6）。
- 相对未优化mapping，dataflow planning可有10×–55× speedup（图 7），说明mapping而非单tile codegen是主要性能杠杆。
- GEMM平均达到约70% peak hardware throughput；某配置达0.95× TTNN，性能模型预测与hardware measurement另有accuracy验证（§3.3）。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 自动mapping可接近hand-tuned library | §3.2 | 两代Tenstorrent、多kernel | 强 |
| hardware IR支持architecture-specific planning | 两个target描述 | 同一vendor两代架构 | 中 |
| reuse/NoC modeling带来大幅收益 | 图 7与ablation | 相对naive mapping | 强 |
| performance model可指导选择 | §3.3 | GEMM/所测shapes | 中 |

## 批判性分析

### 论证链条

论文抓住spatial accelerator真正难点是“跨tile mapping”，以硬件IR+搜索model把Triton programmability带到不同执行范式。与vendor library接近比相对naive的55×更重要，证明自动化不是只赢弱baseline。

### 假设压力测试

Tenstorrent两代仍共享相似NoC/scratchpad抽象，尚不能证明可移植到Cerebras/Dojo/optical dataflow等差异更大的硬件。性能模型面对contention、bank conflict与runtime jitter会失真。候选空间随loop维度/shape增大可能爆炸。

### 实验可信度

实验覆盖主要机制与代表性负载，但平台和基线范围仍限制结论的普遍性。

### 系统性缺陷

TileLoom主要覆盖kernel，不等于整图compiler：跨operator fusion、global memory scheduling、dynamic shapes和multi-program interference未充分处理。接近TTNN的kernel集合也可能偏向适合现有abstraction的workload。

## 局限与后续工作

- 增加不同vendor/topology backend，验证hardware IR的真正portability。
- 支持dynamic shape、irregular sparse kernel和跨operator pipeline/fusion。
- 报告compile/search time并设计profile-guided online re-planning。

## 相关

- **相关概念**：[[Spatial-Dataflow]]、[[MLIR]]、[[Tiling]]、[[Data-Reuse]]、[[Network-on-Chip]]
- **相关系统**：[[Triton]]、[[Tenstorrent]]、[[TTNN]]
- **同会议**：[[OSDI-2026]]
