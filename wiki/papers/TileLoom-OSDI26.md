---
type: paper
name: TileLoom
full_title: "TileLoom: Automatic Dataflow Planning for Tile-Based Languages on Spatial Dataflow Accelerators"
authors: [Wei Li, Zhenyu Bai, Heru Wang, Pranav Dangi, Zhiqiang Zhang, Cheng Tan, Huiying Lan, Weng-Fai Wong, Tulika Mitra]
venue: OSDI
year: 2026
tags: [compiler, spatial-dataflow, accelerator, mlir, triton]
source_pdf: "[[osdi26-li-wei.pdf]]"
source_md: "[[osdi26-li-wei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 空间数据流加速器的自动数据流规划（OSDI 2026）

> **原题**：TileLoom: Automatic Dataflow Planning for Tile-Based Languages on Spatial Dataflow Accelerators

> **一句话总结**：空间数据流加速器没有 GPU 那样替程序自动调度 block、缓存跨核数据的硬件，性能取决于 tile 在核阵列上的位置、时间顺序和显式通信；TileLoom 用统一硬件描述、仿射复用分析和性能模型把 Triton/Helion kernel 自动映射到 Tenstorrent，在 Wormhole/Blackhole 上让 [[Flash-Attention|FlashAttention]] 达到 TTNN 的 1.94/1.98 倍、GEMM 达到 0.95/1.10 倍，但目前真正执行过的后端只有同一厂商的两代芯片。

## 问题与动机

传统 GPU 把一组 thread block 动态分给 SM，并由共享 cache 隐式保留不少跨 block 复用。[[Spatial-Dataflow|空间数据流加速器]]则把许多带本地 scratchpad 的核连成片上网络（NoC），数据由软件明确地从 DRAM 搬到某个核，再转发或广播给其他核。以论文使用的 Wormhole 为例，64 个核的本地 SRAM 聚合峰值带宽约 24.5 TB/s，高于 H100 的约 6 TB/s L2 带宽；但只有映射得当，这个资源才有用。

用户不仅要写“一个 tile 怎样算”，还要决定整个逻辑 tile grid 怎样铺到物理核阵列、每个核按什么顺序执行多个 tile、哪些数据从 DRAM 重复读取、哪些经 NoC 广播、哪些长期留在本地。错误映射会造成负载不均、网络拥塞或 DRAM 热点。厂商 TTNN 的手写库能处理热门算子，却难以覆盖新 kernel，也把策略锁在具体硬件上。

TileLoom 把现有 tile-based DSL 当作入口：Triton 或 Helion 已描述单个 block 的计算和完整 launch grid，编译器只需补上跨核层的调度。其目标不是重新生成最底层矩阵指令，而是自动承担 GPU 硬件 scheduler/cache 在空间架构上缺失的职责，再复用厂商 backend 完成核内优化与代码生成。

## 关键观察 / 隐含假设

- **观察 1：tile program 已经暴露跨核复用所需的仿射访存关系**。若某次 load 的地址不依赖空间维度 `x`，同一行或列的核就在读相同 tile；若不依赖时间循环 `tx`，同一核可跨 wave 复用（§2.2–§2.3）。
  - **依赖假设**：frontend 能把地址运算 affinize 成 tile index 的仿射函数。
  - **可能失效场景**：数据相关索引、稀疏 gather/scatter、动态 shape 和不规则控制流难以用这套分析枚举复用。
- **观察 2：显式 core、memory 和 interconnect 使静态性能预测比带不透明 cache/scheduler 的机器更可行**。候选映射的 compute、DRAM、NoC traffic 和双缓冲 overlap 都能从硬件描述估算（图 2、图 4）。
  - **依赖假设**：带宽、吞吐和拓扑参数足够稳定，粗粒度模型能正确排序候选。
  - **可能失效场景**：bank conflict、未公开的核内调度细节、其他任务造成的拥塞或运行时抖动会让排序失真；论文的模型吞吐预测几何平均仍差 17%。
- **观察 3：空间复用和时间复用必须一起搜索**。同一个 A tile 可以先沿一排核广播，再被每个核跨多个 `tn` wave 保留；更长的保留时间减少 DRAM 访问，却扩大本地 buffer live range（§2.3）。
  - **依赖假设**：kernel 会重复执行相同静态 schedule，规划和编译成本能够摊销。
  - **可能失效场景**：一次性 kernel、shape 高频变化或抢占式多租户环境可能在计划完成前就改变资源条件。
- **假设 1：一套分层 `df` 硬件表示足以覆盖不同空间架构**。
  - **证据强度**：弱到中。论文展示了 2D mesh 和一个未执行的 1D triple-ring 描述，但端到端实验仅覆盖 Tenstorrent Wormhole 与 Blackhole。
- **假设 2：厂商 backend 能把选中的跨核计划高质量地降到硬件**。
  - **证据强度**：中。TT-Metalium 实验有效，但 TileLoom 仍依赖它处理 block/core-level optimization、同步与低层指令，尚未证明换厂商只需替换描述文件。

## 核心方法

TileLoom 的 frontend 枚举 Triton/Helion 的 block shape，把 kernel 规范化为 dataflow-agnostic [[MLIR]]。逻辑 tile grid 表示成 `affine.parallel`，核内顺序计算保留为 `scf.for`，所有 load/store 地址必须成为 loop index 的仿射函数。这一步只表达“有哪些 tile”，还不绑定任何物理核。

时空映射（spatiotemporal mapping）把逻辑并行维度切到硬件空间维度，其余工作变成时间 wave。例如 8×8 mesh 的外层 `affine.parallel(x,y)` 对应 64 个核，后续 `affine.for(tx,ty)` 表示每个核依次处理的 tile。编译器枚举逻辑维度到空间维度的选择、多个空间维度的 tiling 顺序，以及剩余时间循环的顺序；这些选择共同决定负载、邻近关系和复用机会。

数据移动规划读取仿射地址依赖。空间上相同的数据可由少量 producer 从 DRAM 加载，再沿行、列或 wavefront 广播；时间上相同的数据可把 load 提到外层循环并留在本地。TileLoom 为每个 load 枚举直接全局读取、不同广播模式和合法 hoist level，计算 buffer footprint，先删除超过本地容量的候选。空间与时间复用是正交选择，不是固定使用某一种 GEMM template。

自定义 `df` dialect 分层描述硬件。`df.spatial_dim`、`df.core` 和 `df.interconnects` 描述核阵列与每条 link 的仿射连接；`df.memory` 与 `df.mux` 描述本地 SRAM、DRAM bank、容量和可达关系；`df.mat`、`df.vec`、`df.scalar` 描述核内功能单元形状与吞吐。修改 topology、memory hierarchy 或 compute unit 时可以替换这一描述，但实际 backend 仍需单独实现。

性能模型从最内层向外估算候选。它按功能单元吞吐计算 tile 的 compute time，用双缓冲近似 load–compute–store pipeline，再按多个传输是否共享 NoC link/bank 分摊有效带宽。模型可直接选择 top-1，也可只保留 top-k，完整 codegen 后在真实硬件 profile 这些候选。`k` 越大，越容易修复模型误排，编译与试跑成本也近似线性增长。

最终的 dataflow-aware MLIR 已写明 buffer、copy、broadcast endpoint 和 schedule。TileLoom 做 lifetime analysis 后降到 Tenstorrent TT-Metalium，由厂商低层 API 完成核内计算、同步、分配和硬件指令生成。因此论文解决的是跨 tile/core 的计划，不等于从任意 tensor graph 到任意空间芯片的完整独立编译栈。

## 设计取舍

- **只要求 tile DSL，而不接受任意程序**：复用 Triton/Helion 的生态，也让仿射分析可控；代价是动态、不规则和跨 operator graph 不在当前表达范围内。
- **枚举 schedule 后用模型排序**：搜索比固定 1D/2D heuristic 更能适应 irregular shape，但候选空间随 loop 维度、broadcast pattern 和 hoist level 组合增长。
- **粗粒度硬件模型加可选实机 profile**：top-1 可以纯静态部署，top-k 能补偿私有微架构信息缺失；后者引入硬件占用和额外编译时间。
- **复用 TT-Metalium backend**：减少核内 codegen 工作，并能接近手写库；可移植性的最难一段仍由厂商 backend 承担。
- **边界条件**：最适合 shape 稳定、访存仿射、重复运行且内存/NoC 受限的 dense kernel；短命、计算受限、稀疏或强运行时变化的 workload 收益较弱。

## 实验与结果

- **平台与总体结果**：Wormhole 为 8×8 核、108 MB SRAM、288 GB/s DRAM、64 FP16 TFLOPS；Blackhole 为 12×10 核、180 MB SRAM、512 GB/s、162 TFLOPS。表 2 的 top-1 全为模型直接选择、没有最终实机 tuning：FlashAttention 相对 TTNN 分别为 1.94/1.98 倍，FlashDecode 为 0.84/0.87 倍，GEMM 为 0.95/1.10 倍（§3.1–§3.2）。
- **不同 baseline 不能混为一谈**：non-causal FlashAttention 在 64–128 heads、sequence 1,024–16,384 的多数配置中快 1.88–2.06 倍，原因是复用 K tile、少读 DRAM（图 5）。Mamba Chunk Scan 为 27.23/16.27 倍，shape sweep 中达 10–55 倍，但 TTNN 没有 fused kernel，基线是多个 TTNN operator 拼接；这个倍数同时包含 fusion 与 dataflow planning，不能当成纯 mapping 收益（图 7、表 2）。
- **硬件代际改变最佳价值点**：Wormhole 到 Blackhole 的 FP16 算力增加 2.53 倍，off-chip bandwidth 只增加 1.78 倍，因而后者更容易受内存限制。GEMM 从 Wormhole 上 TTNN 的 0.95 倍变成 Blackhole 的 1.10 倍；FlashDecode 因 query length 为 1、映射空间小且 TTNN 有专用 reduction，仍只达到 0.84/0.87 倍（§3.2.2、§3.2.6）。
- **复用消融**：Wormhole GEMM 禁用空间复用、让所有核直接读 DRAM 后，TileLoom 在五个方阵 shape 上快 1.42–2.12 倍，并平均减少 70% DRAM access；时间复用在特意保持 memory-bound 的 GEMM 上最多再快 1.12 倍（表 3、图 10）。
- **模型与 tuning 成本**：模型预测 GEMM throughput 的几何平均误差为 17%（图 11）。8×8 mesh 上，top-1 相对 TTNN 为 -6.1%，几何平均编译时间 5.75 秒；top-2 为 -1.4%/11.17 秒，top-5 为 +0.9%/27.66 秒。top-5 比 top-1 提高约 7%，大部分收益在前 2–3 个候选已取得（表 4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 自动跨核规划可以匹配或超过手写 vendor kernel | 表 2：FlashAttention 1.94/1.98 倍；GEMM 0.95/1.10 倍；FlashDecode 0.84/0.87 倍 | Triton/Helion 的四类 dense kernel；Tenstorrent 两代单卡 | 强 |
| 空间复用确实减少 DRAM bottleneck | 表 3：五个 GEMM 快 1.42–2.12 倍，DRAM access 平均减少 70% | Wormhole 方阵 GEMM；大 shape 更偏 compute-bound | 强 |
| 静态模型足够筛出少量好候选，但不是精确模拟器 | 图 11、表 4：预测误差 17%；top-2 回收多数 top-5 收益 | GEMM 与三种 Wormhole topology；未覆盖共享多租户流量 | 强 |
| 统一硬件表示能支持架构可移植性 | `df` 描述覆盖 2D mesh 和示例 1D triple-ring | 只有 Wormhole/Blackhole 真机，且二者同属 Tenstorrent | 中弱 |
| Mamba 上的大倍数证明 tile DSL 便于生成 fused kernel | 表 2、图 7：相对 unfused TTNN 为 16.27–27.23 倍，shape 中 10–55 倍 | 没有 fused vendor baseline，无法分离 fusion 与 mapping | 中 |

## 批判性分析

### 论证链条

论文从“空间硬件把调度与数据移动责任交给软件”出发，把逻辑 tile grid 映射、复用分析、硬件描述和 cost model 连成一条完整编译路径。FlashAttention、GEMM 直接对比强 TTNN kernel，说明自动规划并非只赢 naive baseline。Mamba 的大倍数则应收窄解释：它证明 TileLoom 能承接一个 fused tile kernel，但没有证明 dataflow planner 单独贡献 10–55 倍。

### 假设压力测试

所有地址必须 affinize 是核心限制。稀疏 [[Attention|attention]]、[[MoE|MoE]] token routing、图计算和 data-dependent gather 会破坏静态复用判断；dynamic shape 还会让编译成本难以摊销。模型假设稳定的独占 link/bank 资源，若多租户共享 NoC 或 DRAM，离线选出的广播可能反而制造热点。Blackhole 的结果也说明收益受 compute-to-bandwidth ratio 支配；计算受限设备上，减少流量不一定转化成速度。

### 实验可信度

评测给出两代真机、强 vendor baseline、irregular GEMM、两种 reuse 消融、模型误差和 top-k 开销，证据比只跑模拟器扎实。局限是只有四类 kernel、没有整模型或多 operator pipeline，也没有能耗、多程序干扰和端到端编译时间分解。所谓跨架构实验仍是同一厂商、相似 mesh；1D triple-ring 只有语法示例。Mamba 的 unfused baseline 与 TileLoom fused kernel 不同，不能用于比较 vendor 最佳实现。

### 系统性缺陷

TileLoom 需要用 microbenchmark 反推私有硬件的 matrix/vector throughput、NoC 和 DRAM 有效带宽；换设备并非只写几行 `df`。backend 也只有 TT-Metalium，生命周期分析、同步和底层 codegen 的正确性依赖厂商栈。搜索空间可能组合爆炸，但论文没有报告候选数量、planning 内存或高维 kernel 的 worst case。系统也未讨论运行时 shape cache、计划版本、编译失败回退、设备故障和多租户隔离；这些都会影响生产部署。

## 局限与后续工作

- **局限 1**：真机只覆盖 Tenstorrent Wormhole/Blackhole，尚不能证明 `df` 表示与 planner 可直接迁移到 Cerebras、Dojo、Trainium 或 ring-based accelerator。
- **局限 2**：输入要求 tile-level、static affine access；dynamic shape、sparse/irregular access、跨 operator fusion 和完整模型没有评测。
- **局限 3**：Mamba 的 10–55 倍包含 fused 与 unfused 实现差异；性能模型仍有 17% 几何平均误差。
- **局限 4**：论文只给 top-k 编译时间，没有给完整候选数、frontend autotuning 总成本、缓存命中率或并发硬件 profile 成本。
- **后续工作 1**：接入至少一个非 Tenstorrent backend，在相同 kernel/shape 上报告需要新增的描述、lowering 代码量和性能差距。
- **后续工作 2**：加入 dynamic/sparse benchmark，按 shape churn 测量编译缓存命中率、摊销时间和 fallback 性能。
- **后续工作 3**：以 fused TTNN 或同等手写 Mamba kernel 为 baseline，分别关闭 fusion、空间复用和时间复用，分离三者贡献。
- **后续工作 4**：在 NoC/DRAM background traffic 下测模型 ranking regret 和 tail latency，并把运行时拥塞反馈纳入小预算重规划。

## 相关

- **相关概念**：[[Spatial-Dataflow]]、[[MLIR]]、[[Tiling]]、[[Data-Reuse]]、[[Network-on-Chip]]
- **相关系统**：[[Triton]]、Tenstorrent TTNN、TT-Metalium
- **同会议**：[[OSDI-2026]]
- **源文档**：[[osdi26-li-wei]]、[[osdi26-li-wei.pdf]]
