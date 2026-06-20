---
type: paper
name: GeneralSparse
full_title: "GeneralSparse: Bridging the Gap in SpMM for Pruned Large Language Model Inference on GPUs"
authors: [Yaoyu Wang, Xiao Guo, Junmin Xiao, De Chen, Guangming Tan]
venue: ATC
year: 2025
tags: [llm-inference, spmm, sparsity, pruning, gpu, auto-tuner]
source_pdf: "[[atc2025-wang-yaoyu.pdf]]"
source_md: "[[atc2025-wang-yaoyu]]"
---

# GeneralSparse: Bridging the Gap in SpMM for Pruned Large Language Model Inference on GPUs (ATC 2025)

> **一句话总结**：剪枝后 LLM 的 matmul 变成模式各异、层间稀疏率不同的 [[SpMM]]，而固定 kernel 无法同时适配；GeneralSparse 把 GPU 并行访存与 reduction 抽象成可搜索的 memory access / reduction space，用 cost model + 自动代码生成选策略，在 A100 上对剪枝权重 SpMM 平均比 cuSPARSE 快 17–20×、端到端推理比 dense cuBLAS 快 2.33×。

## 问题与动机

[[Pruning]] 是压缩 LLM 权重、降低推理算力与显存占用的有效手段，但剪枝后 decoder 层内四个核心 matmul（QKV Projection、Output Projection、MLP1、MLP2）会转为 [[SpMM]]。作者测量显示：即便已用 cuSPARSE 做 SpMM，在 magnitude-pruned 模型上 SpMM 仍占端到端推理约 **70%** 时间，四个 matmul 合计约 **80%**。

现有 GPU SpMM 方案在三个维度上都不完整（Table 1）：

1. **稀疏模式 (sparsity pattern)**：ASpT 面向局部稠密列、Sputnik 面向行长度方差小、SparTA 面向 structured sparsity——各自只适配一类剪枝产物；random vs magnitude pruning 会导致性能波动（Figure 4）。
2. **稀疏率 (sparsity level)**：LLM 不同深度层敏感度不同，常见做法是顶/底层 70%、中间层 90%；但 DgSPARSE 等 auto-tuner 的 reduction 选择与稀疏率耦合不足。
3. **自动实现**：TVM 不支持 SpMM，AlphaSparse 做 SpMV，TACO 偏 CPU——缺少面向 GPU SpMM 的自动 kernel 生成器。

作者 claim 的边界是：聚焦 **pruned LLM weight SpMM on GPU**，通过统一抽象 + intelligent auto-tuner 同时解决 pattern、level、implementation 三缺口；不是重新发明剪枝算法，也不是完整 LLM serving stack。

## 关键观察 / 隐含假设

- **观察 1：GPU 上的并行访存策略可抽象为 sparse/dense 矩阵的「分箱 (dividing box)」过程。** block/warp/thread 三级把矩阵区域分给并行单元；不同分箱策略对应 Sputnik 等手工设计，但固定策略在不同剪枝矩阵上性能差异可达数倍（Figure 4）。
  - **依赖假设**：SpMM 性能瓶颈主要在访存 irregularity 与 load imbalance，而非纯算术吞吐；CSR 等稀疏格式仍是主要存储形态。
  - **可能失效场景**：当 dense 侧列数 N 很大、计算占比上升时，访存/reduction 调优收益下降（论文在 SuiteSparse col=32/64 时已观察到）；若稀疏模式高度结构化且能映射到 [[Tensor-Core]]，专用 TC kernel 可能反超。

- **观察 2：reduction 算法与稀疏率强相关，单一 thread 顺序 reduction 无法在所有层上最优。** 高稀疏率（~90%）时 thread-level TOTAL reduction 更合适；较低稀疏率（~70%）时 warp/block-level reduction 更能利用并行度（Figure 5）。
  - **依赖假设**：层间稀疏率分布遵循「顶/底低、中间高」的 sensitivity-aware pruning 惯例；thread offset range ≥2 可作为选 thread reduction 的可靠启发式。
  - **可能失效场景**：uniform sparsity、极低稀疏率（<50%）或混合精度/量化剪枝改变每行非零数分布时，基于 offset range 的规则可能失效；论文未覆盖 INT8/INT4 权重。

- **观察 3：剪枝后 SpMM 仍是 LLM 推理主瓶颈，优化 SpMM 能直接传导到端到端收益。** 在 FasterTransformer 集成后，MatMul/SpMM 时间仍是 OPT-66B 双卡 tensor parallel 下的主瓶颈。
  - **依赖假设**：attention、通信等其它算子未被同等幅度优化；batch size 与序列长度在实验设定（prompt 64、output 512）下代表目标 workload。
  - **可能失效场景**：[[Flash-Attention]]、[[Disaggregation|PD-disaggregation]]、[[KV-Cache]] 优化或极短输出场景会改变算子占比；多 GPU 通信主导时 kernel 级 20× 加速无法线性转化为端到端 20×。

- **隐含假设：offline 搜索 + 线性回归 cost model 足以在「每个权重矩阵一次」的前提下选到近优策略。**
  - **证据强度**：中。cost model 在训练集上约 90% 准确率，30–50 次迭代、10–30 秒搜索可达最优策略 90% 性能；但 SuiteSparse 上仍有少量矩阵 slowdown，作者归因于 cost model 未覆盖更细粒度策略。

## 核心方法

GeneralSparse 由四部分组成（Figure 6）：memory access space、reduction space、cost model、code generator。

**Memory Access Space** 把 sparse/dense 矩阵如何映射到 GPU worker（thread/warp/block）形式化。sparse 侧设计两个正交维度：row-based（single-row / multiple-row）与 split-based（row-nonsplit / row-split），分别回应「行间相似可合并处理」与「行内非零分布极不均需切分均衡负载」；dense 侧按列粒度均匀分块，因为列间独立。sparse/dense 通过 column-based integration 对齐：thread-group 复用同一组 sparse 非零、加载不同 dense 列，兼顾 sparse 复用与 dense coalescing。

**Offset abstraction** 用 thread/warp/block offset 表达上述分箱，并与 dense 的 block/warp/thread column 联动。随后做 format adjustment：sort、pad、interleaved storage、向量化 load，减少 irregular 访存。workflow 是先定 dense 列分箱决定 thread-group 规模，再对 sparse 非零做三级 offset 分箱，最后 format 微调。

**Reduction Space** 提供两类与 single/multiple-row 对齐的算法族。**TOTAL**（THREAD/WARP/BLOCK_TOTAL）用 MAD + shuffle/shared memory 做同行累加，适合 single-row。**BITMAP** 用位图标记跨行边界，配合 Algorithm 1 做并行归约，适合 multiple-row。**SEGMENT** 处理 BITMAP 后残留的跨段 head/tail。三类算法可按 thread→warp→block 组合（Figure 11），并与 row-split/nonsplit 对齐：row-split 常需低层 TOTAL 后再做高层 reduction。

**策略选择**：基于 sparse allocation 的 single-row / row-split 判断与 thread offset range（由稀疏率设定 ≥2 或 <2）做规则化 reduction 选择（Figure 12）。

**Cost Model**：把 SpMM 视为 division + post-processing 的组合优化问题，用稀疏矩阵统计特征（行数、列数、平均每行非零等）经线性回归估计 division cost \(c_{ij}\) 与 reduction cost \(d_{ij}\)，offline 遍历合法组合取 \(\min (c_{ij}+d_{ij})\)。每个 memory access/reduction 算法有独立回归公式。

**Code Generator**：递归从 block→warp→thread 构造并行循环骨架（Figure 13），在 thread action 中做向量化 load 与 thread-group sparse 复用，再插入对应 reduction。Code optimizer 识别 offset 的 linear/branch/cyclicity/quasilinear 模式，用算术表达式替代内存读 offset，降低访存开销。

集成路径：为每个稀疏权重矩阵 offline 生成并编译定制 kernel，运行时像库函数一样调用；已接入 FasterTransformer C++ API，也可通过库调用嵌入其它框架。

## 设计取舍

- **搜索空间抽象换实现可控性**：memory access / reduction space 覆盖大量手工 kernel 设计点，但实现依赖自动代码生成而非手写模板全集；换取的是 per-matrix 定制，代价是 offline 搜索、编译与 per-matrix 代码体积。
- **规则 + 线性 cost model 换低开销 tuning**：不做 runtime autotuning 或深度学习 cost model；30–50 次迭代即可收敛，适合「每层权重固定、服务期长」的 LLM 推理，但对频繁换模型/换剪枝方案的 dev loop 仍有几分钟级编译成本（Llama-65B 约十余分钟）。
- **CUDA-core 通用 SpMM 换 TC 专用加速**：不依赖 structured sparsity 的 tensor core 路径，因此在 (8,8) structured、70% 稀疏、相对稠密时会被 SparTA/Flash-LLM/TC-GNN/DTC-SpMM 反超；但在 unstructured magnitude/random 剪枝上更 consistently 领先。
- **CSR + format adjustment 换存储转换成本**：相比 SparTA 把矩阵转为 TC-friendly format，GeneralSparse 在访存阶段做 sort/pad/interleave，减少全局写回（Figure 17 profiling），但 format adjustment 本身有预处理成本——论文把其摊进 offline 流程。

**边界条件**：最适合 unstructured / 层间稀疏率变化的 pruned LLM weight SpMM；在 structured 大块稀疏 + 相对低密度时，应预期 TC 方案竞争；SuiteSparse 等科学计算矩阵能获益，但 col 较大时加速比收敛。

## 实验与结果

**环境**：NVIDIA A100（主）、V100（补充），CUDA 12.1，FP16/FP32；kernel 级用 OPT-30B/66B 剪枝权重矩阵 + SuiteSparse 1168 矩阵；端到端用 FasterTransformer 集成。

**Kernel 级（剪枝 LLM 权重，magnitude/random，70%/90%）**：
- 比 cuSPARSE 平均加速 **17.15 / 19.14 / 20.82×**（batch col=8/32/64）
- 比 Sputnik / SparTA / Flash-LLM 平均 **1.84 / 1.57 / 1.30×**（col=8）；col=64 时最高 **3.37 / 1.27 / 1.38×**
- 比 SparseTIR 平均 **1.21 / 1.34 / 1.33×**；TACO 不支持 GPU FP16
- structured pruning granularity (8,8)、70% 时，**低于** SparTA、Flash-LLM、TC-GNN、DTC-SpMM

**Kernel 级（SuiteSparse，FP32）**：
- 比 cuSPARSE 平均 **6.39 / 4.38 / 7.46×**（col=8/32/64）
- 比 Sputnik / DgSPARSE / ASpT 平均 **2.32 / 1.37 / N.A.**（col=8）
- 少数矩阵出现 slowdown；col=8 时效果最好

**Ablation**：固定「每行一个 thread block + thread 顺序 reduction」为 base；灵活 GPU allocation + format adjustment（Op1）主要提升 magnitude 90%（行非零方差大）；多级 reduction（Op2）主要提升 70% 稀疏矩阵。

**Profiling**：相对 Sputnik，Active warps/SM 显著上升（load balance 改善）；相对 SparTA，Memory Bandwidth 与 L1/TEX throughput 上升（减少 reduction 写回）。

**端到端（magnitude pruning，顶/底 70%、中间 90%，prompt 64 / output 512）**：
- 模型：OPT-30B/66B、Llama-7B/13B/65B、Llama-3.1-8B/70B
- 比 dense cuBLAS 平均 **2.33 / 1.58×**（batch 8/32）
- 比 cuSPARSE / Flash-LLM 平均 **1.50 / 1.20×**（batch 8）、**1.48 / 1.23×**（batch 32）
- BoolQ 精度：OPT-30B **69.69%→67.20%**，OPT-66B **70.46%→68.01%**
- 剪枝后 OPT-30B/66B/65B 在 batch 32 可避免 OOM；部分矩阵上 cuSPARSE 甚至比 dense 更慢

**Offline 成本**：搜索 30–50 迭代、10–30 秒；代码生成数秒到两分钟；单矩阵编译数秒；Llama-7B 全模型编译数分钟，Llama-65B 约十余分钟。

## Critical Analysis

### 论证链条

主链条清晰：剪枝 → 多样 SpMM pattern/level → 固定 kernel 不够用 → 抽象 search space + auto generator → kernel 大幅加速 → FasterTransformer 端到端收益。Figure 4/5 的 micro-measurement 直接支撑「需要 adaptive memory access 与 hierarchical reduction」；Figure 16/17 profiling 解释了相对 Sputnik/SparTA 的根因。

薄弱处在于 **端到端增益远小于 kernel 增益**（20× vs 2.33×），论文用算子占比解释合理，但没有系统化回答：在不同 batch、序列长度、attention 占比、多卡通信下，SpMM 优化何时仍值得单独投入。structured pruning 下输给 TC 方案这一反例被报告但未纳入主 claim 的边界表述，容易让读者高估「普适 20×」。

### 假设压力测试

**稀疏模式漂移**：实验覆盖 magnitude、random、部分 structured granularity，但未覆盖 N:M sparsity、block-sparse attention 权重、动态稀疏（runtime pruning）等生产可能出现的模式。若剪枝算法更新导致行长度分布或列聚集性变化，offline 选出的策略可能 stale——论文未讨论 online re-search 触发条件。

**硬件代际**：结果集中在 Ampere A100/V100。Hopper/Blackwell 的 warp scheduling、L2、TC 稀疏指令不同，cost model 的线性回归系数需重训；论文未验证。

**与 serving 栈协同**：只替换 FasterTransformer 中 matmul/SpMM，未与 [[Flash-Attention]]、[[Quantization]]、[[Continuous-Batching]]、[[Speculative-Decoding]] 等组合评估。若 attention 已被高度优化或权重进一步量化到 INT4，SpMM 是否仍是 70% 瓶颈需要重测。

**正确性**：剪枝精度掉 2–3 个点在 BoolQ 上可接受，但未覆盖更广泛 benchmark，也未讨论 format adjustment（sort/pad）是否影响数值一致性——对 SpMM 而言通常无影响，但论文未显式验证。

### 实验可信度

**强项**：baseline 面广（库、手工设计、auto-tuner、compiler、TC 方案）；同时报 kernel 与端到端；给出 ablation、profiling、V100 迁移、SuiteSparse 泛化；主动披露 structured 场景落败与 SuiteSparse 少量 slowdown。

**不足**：
- 端到端只对比 dense cuBLAS、cuSPARSE、Flash-LLM，未与 SparTA 等最强 kernel competitor 做同框架端到端对比
- 吞吐 metric 为 tokens/GPU-second，未系统报告 TTFT/TPOT 尾延迟
- cost model「90% 准确率」缺少误选策略导致的性能损失分布
- 生产 trace（请求长度分布、并发、多租户）缺失，实验偏 offline benchmark

### 系统性缺陷

**部署复杂度**：per-matrix kernel 生成 + 编译使工程集成重于单一 cuSPARSE 调用；论文称 runtime 直接调库，但未讨论二进制体积、编译缓存、CI/CD、多 GPU 上 kernel 版本一致性与可观测性——**论文未讨论**。

**尾延迟与隔离**：未报告 P99 latency、batch 间干扰、kernel launch 开销在小 batch 下的表现。

**故障与更新**：模型热更新、剪枝率变更、A/B 切换时的重编译延迟是生产痛点，论文只给离线时间量级，未给滚动升级方案。

**多卡扩展**：OPT-66B 双卡 TP 实验显示 SpMM 仍主导，但通信开销存在；未量化 GeneralSparse 与 NCCL/TP 通信的 overlap 或干扰。

## 局限与 Future Work

- **局限 1**：structured / TC-friendly 稀疏在相对低密度时不占优。Future work：把 TC 路径纳入 search space，或 hybrid 调度「unstructured 用 GeneralSparse、structured 用 SparTA/DTC-SpMM」并报告切换阈值。
- **局限 2**：cost model 在 SuiteSparse 子集上失效。Future work：细化策略粒度或引入 learned cost model，量化误选率与性能损失上界。
- **局限 3**：端到端对比 baseline 偏少，且未覆盖新硬件。Future work：在 Hopper 上与 Flash-LLM/SparTA 做同框架 E2E；用生产 trace 测 SpMM 占比随负载变化。
- **局限 4**：offline 编译成本对快速迭代不友好。Future work：amortize 编译 via kernel cache、按层族聚类共享策略、或 lightweight online fallback（cuSPARSE）当 miss 时。
- **局限 5**：与 [[Quantization]]、[[MoE]]、[[Expert-Parallelism]] 的组合未探索。Future work：在 INT8/INT4 权重或 MoE expert 稀疏化场景重测 SpMM 是否仍为瓶颈。

## 相关

- **相关概念**：[[SpMM]]、[[Pruning]]、[[Quantization]]、[[Attention]]、[[Tensor-Parallelism]]
- **同类系统**：[[Flash-LLM]]、Sputnik、SparTA、cuSPARSE、SparseTIR、TACO
- **同会议**：[[ATC-2025]]
- **对比**：GeneralSparse 走 CUDA-core 通用 SpMM auto-tuning；SparTA/Flash-LLM/DTC-SpMM 走 structured sparsity + [[Tensor-Core]]——二者互补而非单纯替代