---
type: paper
name: TileLoom
full_title: "TileLoom: Automatic Dataflow Planning for Tile-Based Languages on Spatial Dataflow Accelerators"
authors: [Wei Li, Zhenyu Bai, Heru Wang, Pranav Dangi, Zhiqiang Zhang, Cheng Tan, Huiying Lan, Weng-Fai Wong, Tulika Mitra]
venue: OSDI
year: 2026
tags: [spatial-accelerator, dataflow, mlir, compiler, autotuning]
source_pdf: "[[osdi26-li-wei.pdf]]"
source_md: "[[osdi26-li-wei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向空间数据流加速器的自动数据流规划（OSDI 2026）

> **原题**：TileLoom: Automatic Dataflow Planning for Tile-Based Languages on Spatial Dataflow Accelerators

> **一句话总结**：TileLoom 假设空间数据流加速器的核心瓶颈来自跨核放置、片上通信和分布式存储，而非单个 tile 内的计算；它把 tile 网格映射到空间与时间维度，自动规划广播、缓存和 NoC 资源，在 Tenstorrent Wormhole/Blackhole 上对 FlashAttention 获得 1.88–2.06× 加速、对未融合 Mamba 基线获得 10–55× 加速，并在 GEMM 上达到接近甚至超过 TTNN 的性能。

## 问题与动机

空间数据流加速器把计算核心、scratchpad 和 NoC 暴露给软件，减少对统一缓存和共享内存的依赖。这个组织方式可以提供很高的片上带宽，但性能取决于 tile 实例如何放置、按什么顺序执行，以及数据在核心之间如何转发。错误的映射会造成 NoC 拥塞、负载不均衡或重复访问片外内存。

现有 tile 语言通常只描述单个 block 内的计算，跨核心的 grid 调度仍由厂商编译器和手写库决定。TileLoom 从 Triton 或 Helion kernel 出发，在 MLIR 中补上跨核的时空映射、数据复用和通信规划，并把结果交给 Tenstorrent 的 TT-Metalium 后端生成可执行程序。

## 关键观察 / 隐含假设

- **观察 1：空间数据流架构把 grid-level 调度变成编译器必须解决的问题。** GPU 的硬件调度器和缓存通常隐藏了 block 放置与跨 block 复用；空间阵列没有同等程度的隐式机制，因此映射空间同时决定计算并行度、NoC 流量和片外带宽消耗（§1、图 1）。
  - **依赖假设**：硬件的核心阵列、网络和存储层级足够稳定且可描述，编译器可以据此静态推断代价。
  - **可能失效场景**：动态请求、运行时分支、共享设备上的干扰或硬件细节未被 `df` 描述时，静态代价模型可能错误排序。
- **观察 2：tile 访问的仿射依赖关系可以暴露空间与时间复用。** 若访问地址不依赖某个空间索引，同一 tile 可沿该维度广播；若不依赖某个时间循环，同一 tile 可跨 wave 保留在本地 buffer（§2.3）。
  - **依赖假设**：前端能把地址算术正规化为仿射表达式，且 tile 生命周期和 buffer 容量可静态分析。
  - **可能失效场景**：非仿射索引、稀疏或数据相关访问会削弱复用分析；较大的 hoist 范围也可能让 buffer 占用超过模型估计。
- **观察 3：模型不必精确到 cycle，只要能识别 compute-bound 与 memory-bound 区间并可靠排序。** 实测 GEMM 吞吐与模型预测的几何平均误差为 17%，但模型仍能捕捉瓶颈转变（图 11）。
  - **证据强度**：中。候选排序在本文硬件和 kernel 集合上有效，但尚未证明能跨厂商或跨代际稳定工作。

## 核心方法

TileLoom 将 tile 程序先降到与硬件无关的 MLIR，再枚举逻辑 tile grid 到物理核心阵列的映射。每个逻辑并行维度可以映射到一个或多个空间维度；剩余维度变成按 wave 执行的时间循环。映射顺序也属于搜索空间，因为它改变 tile 在 mesh 上的布局以及可用的通信路径（§2.2）。

数据移动规划基于仿射访问分析。TileLoom 为每个 load 判断空间复用和时间复用机会，并枚举逐核 global load、单维广播和多维广播等方案。对时间复用，编译器尝试把 load 提升到更外层循环；跨越不依赖的循环不会增加 live tile 数量，跨越有依赖的循环则扩大 buffer footprint。容量不够的候选会被剪枝（§2.3）。这些设计直接回应了观察 2。

`df` 是 TileLoom 的硬件描述 MLIR dialect。它分层描述核心阵列和互连、分布式 memory 及其连接方式，以及核心内的矩阵/向量/标量单元和吞吐率。这样，换用不同的阵列拓扑、memory 层级或核心配置时，映射 pass 不需要硬编码新的架构规则（§2.4）。

性能模型把计算、memory 和 NoC 代价合并。它用粗粒度的单核心吞吐估计计算时间，用链路和 memory 接口上的竞争估计传输时间，并假设 load–compute–store 采用 double buffering 流水重叠（§2.5）。模型先选出 top-k 候选；可选的硬件 profiling 再从这些候选中选出最终映射，以抵消未建模的微架构细节。这个两阶段设计回应了观察 3。

## 设计取舍

- **静态规划换取可预测性**：编译期决定放置和通信，降低运行时调度负担，但对动态形状、动态控制流和运行时拥塞的适应性有限。
- **显式硬件描述换取可移植性**：`df` 避免把拓扑和带宽写死在优化 pass 中；代价是用户或工具必须提供足够准确的硬件参数。本文的 Tenstorrent 参数还需要微基准测试恢复。
- **top-k profiling 换取模型鲁棒性**：top-1 不需要额外 profiling，top-5 在 8×8 mesh 上比 top-1 高 7%，但编译和测量成本近似线性增加；top-2 已获得 4.7% 的增益（表 4）。

## 实验与结果

- 在非因果 FlashAttention 上，覆盖 64–128 个 head、序列长度 1024–16384 的配置，TileLoom 相比 TTNN 在几乎所有配置上达到 1.88–2.06×（图 5）；收益来自 key tile 的片上复用和 DRAM 流量减少。
- Flash Decode 的 query 长度为 1，跨 query 的空间并行消失，主要难点变成 KV 分片和跨核 gather-reduce。面对专门优化的 TTNN 实现，TileLoom 平均达到约 85% 的 TTNN 性能（图 6）。
- Mamba Chunk Scan 使用融合的 Helion kernel，而 TTNN 基线由多个未融合操作组成；TileLoom 获得 10–55× 加速（图 7）。该差距同时包含 kernel fusion 和数据流规划收益，不能归因于后者单独贡献。
- GEMM 在 M、K、N 为 256–16384 的范围内接近 TTNN。Wormhole 上约为 TTNN 的 0.95×，Blackhole 上为 1.10×；后者的计算吞吐相对片外带宽增长更快，因而更容易受数据移动影响（图 8、§3.2.6）。
- 禁用空间复用后，GEMM 的 DRAM 访问平均减少约 70% 的效果消失；时间复用在保持 memory-bound 的配置上最高带来 1.12× 加速（表 3、图 10）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 自动时空映射能在规则与不规则 GEMM 上接近厂商库 | 图 8、图 9；Wormhole 约 0.95×，Blackhole 约 1.10× TTNN | Tenstorrent 两代芯片，GEMM 形状范围有限 | 强 |
| 片上复用是 memory-bound kernel 的主要收益来源 | 表 3、图 10；DRAM 访问减少约 70%，时间复用最高 1.12× | Wormhole GEMM，特定 memory-bound 配置 | 中 |
| 粗粒度性能模型足以筛选候选 | 图 11；预测误差几何平均 17%，且能识别瓶颈转换 | 主要验证于 GEMM，未证明跨架构泛化 | 中 |
| TileLoom 可替代大量手写数据流实现 | 图 5–9；多个 kernel 达到竞争性能 | Flash Decode 仍为 TTNN 的约 85%，后端仍依赖 TT-Metalium | 中 |

## 批判性分析

### 论证链条

论文的主链条在固定形状、固定硬件上是闭合的：仿射访问揭示复用，`df` 提供拓扑和带宽，候选规划再由模型排序。结果也显示，在 irregular GEMM 中，固定的 1D/2D 模板会因形状变化而失效，搜索确实能找到更合适的映射（图 9）。

但“减少手写库依赖”仍有边界。TileLoom 使用 Triton/Helion 前端调优、定制 lowering、TT-Metalium 后端和硬件微基准测试，自动化主要集中在跨核数据流规划；单核指令级优化仍由后端承担。Mamba 的巨大加速还混入了融合与未融合基线差异。

### 假设压力测试

方法依赖仿射地址和静态 tile 生命周期。数据相关稀疏性、动态路由或形状频繁变化时，复用关系与 buffer footprint 可能需要运行时信息。模型把 global load 视为足够随机并按链路共享带宽，这一假设对有突发性、热点 bank 或多租户干扰的流量未必成立。

论文评估的是单卡 Tenstorrent Wormhole 和 Blackhole，以及缩小的 8×8、4×8 mesh 和 1×8 ring。`df` 在语法上可表达其他拓扑，但论文没有在第二家真实硬件上验证迁移成本和预测质量。因此跨厂商可移植性目前是设计目标，不是实验结论。

### 实验可信度

GEMM、FlashAttention、Flash Decode 和 Mamba 覆盖了不同的数据复用与归约模式；空间/时间复用消融和 top-k 实验也能对应设计分解。主要不足是基线强度不完全一致：Flash Decode 使用高度专门化 TTNN，Mamba 则使用未融合 TTNN 组合。论文报告了吞吐和编译时间，但没有系统报告功耗、尾延迟、并发租户隔离或故障恢复。

### 系统性缺陷

候选组合会随并行维度、广播方式和 hoist 层级增长，top-k profiling 只是限制了硬件测量数量，未消除前端调优和候选生成的编译成本。`df` 参数需要通过微基准恢复，硬件代际变化可能要求重新校准。论文也未讨论编译缓存、版本兼容、运行时监控和 NoC 拥塞异常下的回退机制。

## 局限与后续工作

- **局限 1**：模型误差仍有 17% 的几何平均值，当前验证主要集中在 GEMM；对动态或非仿射工作负载的适用性未证明。
- **局限 2**：TileLoom 尚未复现所有 TTNN 的微架构级 GEMM 优化，Wormhole GEMM 仍约为 TTNN 的 0.95×。
- **后续工作 1**：在多个真实空间数据流硬件上固定同一组 kernel，测量 `df` 描述迁移、模型误差和 top-k 成本，验证“架构无关”是否成立。
- **后续工作 2**：加入动态形状与运行时拥塞反馈，比较静态映射和运行时重规划在 P99 延迟、编译成本及吞吐上的边界。

## 相关

- **相关概念**：[[MLIR]]、[[Dataflow Architecture]]、[[NoC]]、[[Triton]]、[[Roofline Model]]
- **同类系统**：[[Timeloop]]、[[MAESTRO]]、[[AMOS]]、[[LISA]]
- **同会议**：[[OSDI-2026]]
