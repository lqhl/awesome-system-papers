---
type: paper
name: Hawkeye
full_title: "Hawkeye: Reproducing GPU-Level Non-Determinism"
authors: [Erez Badash, Dan Boneh, Ilan Komargodski, Megha Srivastava]
venue: MLSys
year: 2026
tags: [verifiable-ml, gpu-simulation, tensor-core, reproducibility, floating-point]
source_pdf: "[[73278a4a86960eeb576a8fd4c9ec6997.pdf]]"
source_md: "[[73278a4a86960eeb576a8fd4c9ec6997]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Hawkeye: Reproducing GPU-Level Non-Determinism (MLSys 2026)

> **一句话总结**：NVIDIA Tensor Core 的 rounding、subnormal 与累加顺序在架构间不一致，使 CPU 重放无法 bitwise 比对；Hawkeye 用 PTX `wmma.mma` 定向测试逆向 Ampere/Hopper/Lovelace 的 16×16 MMA 语义，在 CPU 上 **100%** bit-exact 复现 FP16/BF16/FP8（10 万随机 tile + 4096×4096 MatMul），为可验证 ML 提供零 GPU 开销 oracle。

## 问题与动机

[[MLSys-2026]] 语境下，ML-as-a-service（SageMaker、Vertex AI、Replicate 等）要求客户信任服务商按约定完成训练/推理，但 **verifiable ML** 的前提是计算可复现。现代 [[LLM]] 工作流大量依赖 [[Tensor-Core]] 做 [[MatMul]]，而浮点加法非结合性叠加硬件未公开的 rounding、subnormal 处理与累加顺序，使 **同一输入+seed 在不同 GPU 上可产生不同输出**——例如 FP16 向量点积在 L40S（Lovelace）得 **0**、A100（Ampere）得 **0.0020**，误差会沿训练/推理链放大。

作者 claim：审计方若能在 CPU 上 **bit-exact** 复现 GPU 上的 Tensor Core MatMul，则任何与 oracle 的不一致只能归因于错误执行，而非硬件非确定性。现有路线各有硬伤：（1）关闭非确定性特性（如 Verde）显著降速；（2）Srivastava et al.（NeurIPS 2024）记录 rounding 决策，存储成本高；（3）TOPLOC 等启发式断言数值差「足够小」，无对抗场景保证。Hawkeye 走第四条路：**不改原 GPU kernel**，只需知道执行所用 GPU 架构，即可在 CPU 上精确模拟 Tensor Core 算术。

## 关键观察 / 隐含假设

- 观察 1：Tensor Core 的非确定性主要来自 16×16 tile MMA 内部流水线，而非单元素 IEEE 754 乘法本身。 论文用 `(2¹¹−1)²` 溢出 FP16 范围的乘积验证：Ampere 上单乘积在 dot-product 路径中 不丢精度（结果精确为 4190209），说明问题在 累加顺序与内部对齐 rounding，而非乘法单元。
  - **依赖假设**：审计粒度落在 **wmma 16×16 MMA 指令**（`D = C + A·B`）层面；更高层算子（conv、[[Attention]]）可分解或另行逆向。
  - **可能失效场景**：使用非 Tensor Core 路径（CUDA core fallback）、融合 kernel 在 MMA 前后插入额外 cast/融合算子时，仅复现 MMA 不足以覆盖端到端数值。

- 观察 2：累加顺序是 架构相关但静态确定 的——可用「计算中性子群」穷举搜索恢复。 Ampere FP16 仅 `{accumulator, P[1..8]}` 构成非平凡中性子群，对应 两阶段金字塔累加（先 9 项、再与 P[9..16] 合并）；Hopper 则为 单阶段 17 项一次累加。无动态排序证据。
  - **依赖假设**：NVIDIA 未在 driver/firmware 更新中改变已测架构的 MMA 微架构语义；测试用的 inline PTX kernel 与生产 cuBLAS/cuDNN 调用同一 HMMA 指令。
  - **可能失效场景**：新架构（Blackwell 及以后）、不同 driver 版本、或 vendor 在固件层修改累加树；论文仅实证 Ampere/Hopper/Lovelace。

- 观察 3：内部累加精度与 rounding 模式可通过可控指数差的 dot-product 探针隔离。 Ampere FP16 内部 significand 24 bit（含隐式位）；Hopper 25 bit。对齐移位时 round towards zero（截断）；乘积 延迟归一化；subnormal 乘积 不重归一化；最终写回输出精度同样 towards zero。
  - **依赖假设**：探针构造的 16 元 tile 能触发与大规模 MatMul 相同的内部路径；BF16 在 Ampere 上 **执行策略与 FP16 同构**，仅多出 FP32 动态范围外的 extended-range 累加与最终 cast。
  - **可能失效场景**：BF16 中间值超 FP32 有限范围时的饱和行为（论文测到可暂存中间溢出、最终 cast 为 ∞）；FP8 E4M3 仅在 Hopper 上完整表征，其他格式/架构组合未同等深度展开。

- 观察 4：一旦 16×16 tile 语义被捕获，大规模 MatMul 可组合 tile 达到端到端 bit-exact。 10 万随机 16×16 tile + 4096×4096 矩阵乘法 100% 与 GPU custom kernel 一致。
  - **依赖假设**：大矩阵由 **确定性 tile 调度** 组成（无跨 tile 融合改变累加语义）；审计只需 **单次** CPU 重放，可容忍慢速参考实现。
  - **可能失效场景**：生产库使用与 isolated MMA 不同的 tiling、split-K、或 atomic 累加顺序；分布式 [[Tensor-Parallelism]] 下 all-reduce 顺序与单卡语义不同。

- **假设 1：知道「哪张 GPU / 哪代架构」足以选择正确 simulator，无需捕获运行时 micro-scheduling。**
  - **证据强度**：强（针对 isolated MMA + 三架构三精度）；弱（针对完整 PyTorch/[[vLLM]] 推理栈，论文明确留作 future work）。

- **假设 2：可验证 ML 的主要瓶颈是 MatMul 层非确定性，非线性 element-wise 算子已有可行 CPU oracle（如 pyxis-roc sass-math）。**
  - **证据强度**：中。引言区分了 software vs hardware non-determinism，但未在完整模型上前向验证「MatMul oracle + element-wise oracle = 端到端 bit-exact」。

## 核心方法

Hawkeye 是 **characterize-then-simulate** 平台：先用 custom CUDA kernel 经 inline PTX 直接调用 `wmma.mma.sync`（编译为 HMMA SASS），对 16×16×16 的 `D ← C + A·B` tile 做属性隔离测试，再把结论编码为 CPU simulator（开源：[gpu-simulator](https://github.com/badasherez/gpu-simulator)）。

### 测试套件（Target Tests）

| 测试 | 目的 | Ampere FP16 结论（代表） |
|------|------|--------------------------|
| Summation Dependency & Order | 恢复部分积累加顺序 | 两阶段：C+P[1..8] → +P[9..16] |
| Internal Precision Detection | 内部 significand 宽度 | 24 bit（Hopper 25 bit） |
| Rounding Mode Detection | 对齐移位丢弃低位的方式 | Round towards zero |
| Normalization Stage Detection | 乘积是否先归一化再累加 | 延迟归一化 |
| Subnormal Behavior Detection | subnormal 乘积是否重归一化 | 不重归一化，降精度 significand 直入累加 |

**计算中性子群测试**（Algorithm 4）是核心逆向工具：对 16 个乘积索引的子集 S，构造「S 内项 engineered 求和为 0」与「S 内项置零」两种场景，若 bitwise 结果相同则 S 为中性子群，从而恢复硬件分组结构。

### 恢复的 Ampere FP16 流水线

对应 Algorithm 12–14 与 Figure 1：

1. **乘法**：FP16×FP16 → 扩展内部精度（`mraw ≪ 3`），不立即归一化到 FP16；
2. **分组累加**：按金字塔两阶段 `GroupSum`；对齐时 `mi ≫ Δe` **截断**而非 IEEE nearest-even；
3. **最终写回**：内部高精度 accumulator **towards zero** 降到输出格式。

Hopper 差异：单阶段累加全部 16 个乘积 + C；内部 25 bit。Lovelace 实证与 Ampere 同构。BF16 额外处理：中间可超 FP32 有限范围暂存，最终 cast 回 FP32（溢出 → ∞）；最小有效乘积贡献可达 **2⁻¹⁵⁶** 量级（Hopper 对应 max exponent 阈值 **−133**）。

### 与可验证 ML 工作流的关系

Hawkeye **不修改** 服务商 GPU kernel，审计方离线用 CPU simulator 作为 oracle，对比服务端公布的 MatMul 中间/最终输出。相对 Srivastava et al. 的 rounding 日志方案，provider 侧 **零存储/零算力开销**；相对禁用非确定性，**保留生产性能路径**。

## 设计取舍

- **黑盒逆向测试 vs 官方文档/微架构白皮书**：赢得对闭源 Tensor Core 流水线的可验证刻画，不依赖 NVIDIA 公开全部细节；代价是每新架构/精度需重复全套探针，且无法证明「已覆盖所有 corner case」以外的行为。
- **16×16 tile 精确模拟 vs 端到端 NN 复现**：tile 级 **100%** 成功率与清晰算法（Algorithm 12–14）；牺牲对 conv、flash [[Attention]]、fusion、分布式 reduce 的即时覆盖——论文将集成进完整模型架构标为 future work。
- **CPU 参考实现 vs GPU 整数化加速**：Apple M4 Pro 上 4096×4096 需 **~40–53 s**（Table 1），仅适合 **一次性审计**；赢得部署简单、与 verifier 算力解耦；牺牲交互式或在线逐 token 验证的延迟。
- **Bit-exact oracle vs 近似/heuristic 验证**：消除「正确但不相等」的歧义，支撑 cryptographic proof system 所需的确定性计算假设；边界是 **必须已知架构**，且对抗方若换用未表征硬件则 oracle 失效。
- **边界条件**：在 **NVIDIA Tensor Core + FP16/BF16/FP8(E4M3) + 孤立 MMA tile** 下最优雅；生产 MatMul 若走 cuBLAS 内部不同指令变体或 TF32/FP32 accumulate 路径，需额外表征。

## 实验与结果

- **Bit-exact 率**：Ampere / Hopper / Lovelace × FP16 / BF16 / FP8 — **10 万**随机 16×16 tile **100%** 与 GPU custom kernel 一致。
- **大矩阵**：4096×4096 MatMul CPU simulator vs GPU **100%** bitwise 匹配（各架构/精度）。
- **CPU 性能基线**（Apple M4 Pro，10 次平均，Table 1）：
  - FP16 Ampere：**50.8 s**（σ 3.2）
  - FP16 Hopper：**47.2 s**（σ 2.5）
  - BF16 Ampere：**52.5 s**（σ 2.9）
  - BF16 Hopper：**48.2 s**（σ 2.6）
  - FP8 Hopper：**40.6 s**（σ 0.6）
- **架构差异可建模**：同一 FP16 `A·Bᵀ` 在 L40S 得 **0**、A100 得 **0.0020**——Hawkeye 分别为两架构维护独立 simulator，而非统一近似。
- **BF16 极端值**：中间累加可暂超 FP32 max finite（≈3.4×10³⁸）只要最终结果落回范围内；否则饱和为 **∞**（Algorithm 10）。

## Critical Analysis

### 论证链条

主链条：**测量** 跨 GPU 的 MatMul 数值分歧（L40S vs A100 等）→ **归因** 非确定性来自 Tensor Core 累加/rounding 而非单步 IEEE 乘法 → **机制** 五类定向测试恢复 Ampere/Hopper/Lovelace 静态累加树与内部精度 → **实现** CPU simulator → **验证** 10 万 tile + 4096² MatMul 100% bit-exact。

链条在 **tile 级 MMA** 上闭合严密：中性子群搜索 + 多组 rounding 探针形成互证。最弱跳步在 **tile → 完整 ML 工作流**：论文未将 simulator 嵌入真实训练/推理框架，也未展示「捕获一次 GPU 执行 trace → CPU 复现全模型 logits」的端到端案例。从 16×16 外推到 cuBLAS 分块 MatMul 依赖「大矩阵仅为 tile 组合」假设，**未被 production library 实验直接证明**。

### 假设压力测试

**Workload**：聚焦 MatMul——与 [[LLM]] 主体计算一致，但未覆盖 MoE routing、自定义 CUDA fusion、[[Flash-Attention]] 的 online softmax 与 MMA 交错。分布式训练中 gradient all-reduce 顺序、ZeRO 分片聚合可能引入额外非确定性，论文未讨论。

**硬件**：仅 NVIDIA Ampere / Hopper / Ada Lovelace；AMD MI、Google TPU、Apple AMX 等完全未涉及。新 SKU（H100 vs H800）、driver/CUDA 版本、功耗降频导致的调度差异是否改变 MMA 语义——论文假设 **不变**，证据仅覆盖论文实验环境。

**规模**：4096² 验证组合正确性，但万亿参数训练的单步 MatMul 形状、batch、split-K 与 isolated 16×16 测试的对应关系需工程映射；论文未提供从 PyTorch `torch.matmul` 到 MMA tile 的自动 trace 工具。

**部署 / 对抗**：审计方需服务商披露 **GPU 型号**；恶意方可声称用 A100 实际用未表征 GPU，或在中途替换 kernel。Heuristic 路线（TOPLOC）在「正常」负载下更轻量，Hawkeye 在 **已知架构 + 愿意离线重放** 时提供更强保证，但集成成本高。

### 实验可信度

**优点**：测试设计针对性强（中性子群、指数扫描、c 递增探针），结论多组实验交叉验证（如 towards-zero 同时在对齐移位与最终写回被排除 nearest-even）；跨三架构三精度；随机 fuzz 规模大（10⁵ tile）；开源代码可复现。

**限制**：
- **Baseline 对比弱**：未与 Srivastava et al.、Verde、TOPLOC 在相同 verification task 上比延迟、存储、检出率。
- **生产路径缺失**：实验用 custom PTX kernel，非 cuBLAS/cuDNN/[[vLLM]] 实际调用栈；生产是否存在额外 TF32 accumulate、split-K atomic 等路径未知。
- **端到端指标无**：无审计延迟、trace 体积、与 zkML（zkLLM、Artemis）集成的实测数据。
- **Table 1** 仅 CPU 参考实现耗时，无 GPU simulator 对比，也无 MatMul 次数与总审计 wall-clock 估算。

### 系统性缺陷

- **尾延迟 / 在线验证**：4096² 数十秒级 CPU 执行只适合离线抽查；逐 token 推理审计的 TPOT 影响论文未讨论。
- **可观测性**：审计需捕获足够细粒度的 MatMul 输入/输出或中间 tile；生产系统默认不暴露此接口，trace 注入与隐私冲突论文未覆盖。
- **故障恢复**：simulator 与 GPU 不一致时的诊断流程（driver 版本漂移、silent 语义变更）论文未讨论。
- **运维成本**：每新 GPU 代际需重新跑全套 characterize；与 ML 栈快速迭代（新 dtype、新 kernel）的维护负担高。
- **资源隔离**：CPU oracle 重放是 CPU 密集型任务，与 GPU 服务商资源模型正交；大规模并行审计的调度论文未讨论。
- **兼容性**：依赖 inline PTX 与特定 `wmma` 变体；PyTorch `torch.use_deterministic_algorithms` 等软件层确定性与此工作互补但集成路径未给出。

## 局限与 Future Work

- **局限 1**（论文自述）：仅覆盖 **部分 NVIDIA Tensor Core 架构**；其他 vendor / 加速器需重做测试套件。
- **局限 2**：表征粒度为 **16×16 MMA tile**；conv、[[Attention]]、norm fusion 等高层算子需额外逆向。
- **局限 3**：**未集成** 到现有 ML 框架或 verifiable ML proof system（zkSNARK、commit-and-prove 等）；分布式训练 settings 的系统挑战未解决。
- **局限 4**：CPU simulator **性能基线**（~50 s / 4096²），未优化为整数化或 GPU 加速参考实现。
- **局限 5**：审计前提包括 **已知 GPU 架构**；异构集群或多 backend 切换场景未验证。

- **Future work 1**：将 Hawkeye simulator 挂入 PyTorch/[[vLLM]] 执行路径，测量 **端到端 logits bitwise 匹配率** 与 trace 开销，闭合 tile→model 跳步。
- **Future work 2**：对 **Blackwell** 及新 MMA 变体（含 NVFP4/新 FP8 格式）跑同一套 target tests，建立架构语义版本库与 driver 回归测试。
- **Future work 3**：与 **zkLLM / Artemis / Verde** 结合，量化「MatMul oracle + 证明系统」相对纯 cryptographic approach 的 prover/verifier 成本。
- **Future work 4**：characterize **cuBLAS/cuDNN** 实际 tile 调度与 split-K atomic 顺序，验证生产 MatMul 是否等价于 isolated MMA 组合。

## 相关

- **相关概念**：[[Quantization]]、[[Tensor-Parallelism]]、[[Attention]]、[[MatMul]]、[[Floating-Point]]
- **同类系统**：Srivastava et al. optimistic verifiable training（NeurIPS 2024）、Verde、zkLLM、Artemis、TOPLOC、pyxis-roc sass-math
- **同会议**：[[MLSys-2026]]、[[ZK-APEX-MLSys26]]、[[GPU-CC-Security-MLSys26]]、[[DriftBench-MLSys26]]
- **对比**：相对 **rounding 日志** 方案，Hawkeye 把存储/开销压到审计方一次性 CPU 成本；相对 **禁用非确定性**，保留 Tensor Core 性能；相对 **TOPLOC 启发式**，提供 bit-exact 形式保证但集成范围更窄
