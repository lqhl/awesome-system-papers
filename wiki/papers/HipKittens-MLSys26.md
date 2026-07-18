---
type: paper
name: HipKittens
full_title: "HipKittens: Fast and Furious AMD Kernels"
authors: [William Hu, Drew Wadsworth, Sean Siddens, Stanley Winata, Daniel Y. Fu, et al.]
venue: MLSys
year: 2026
tags: [gpu-kernels, amd, dsl, compiler, gemm, attention]
source_pdf: "[[2a38a4a9316c49e5a833517c45d31070.pdf]]"
source_md: "[[2a38a4a9316c49e5a833517c45d31070]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# HipKittens: Fast and Furious AMD Kernels (MLSys 2026)

> **一句话总结**：观察到 AMD 上 NVIDIA 式 wave specialization 因静态寄存器分配仅达峰值 80%、HIPCC 限制 AGPR 作 MFMA 输入，HipKittens 保留 ThunderKittens tile DSL 但改用 8-wave ping-pong / 4-wave interleave + 显式寄存器 pin + chiplet-aware grid swizzle，在 MI325X/MI355X 上追平 AITER 汇编，GQA backward 1.8–2.5×、汇编未覆盖形状 1.2–10× 于全部基线。

## 问题与动机

AMD MI355X 等 CDNA4 GPU 在峰值算力与 HBM 带宽上已具竞争力，但 **peak kernel 生态仍高度依赖 AITER/Composable Kernel 等手写汇编库**，难以覆盖 AI workload 广度——论文称 AITER Llama GQA backward 仅 SoTA 的 **30%**，PyTorch SDPA 仅 **24%**（MI355X）。NVIDIA 侧 [[Flash-Attention]] 生态已收敛到 ThunderKittens、CuTe DSL、Gluon 等 **tile-based C++ embedded DSL**，用少量 opinionated primitive 覆盖 GEMM、attention、MoE 等算子。

核心开放问题：**ThunderKittens 式 tile + bulk operator 抽象是 NVIDIA 特有，还是能跨厂商泛化？** 若可泛化，instantiation（调度、寄存器、swizzle、grid schedule）在 AMD 上需要哪些不同原语？

直接迁移的障碍有三类：(1) **编译器约束**——HIPCC 禁止 AGPR 作 matrix instruction 输入，attention backward 等混合 workload 被迫插入冗余 `v_accvgpr_read`；(2) **矩阵 layout 复杂度**——AMD MFMA 无 NVIDIA 16×16 复合结构，shared memory bank conflict 与 phase ordering 因指令而异；(3) **调度范式错配**——NVIDIA wave specialization（producer-consumer）在 MI355X BF16 GEMM 上仅峰值 **80%**（Table 2），因 AMD **静态寄存器分配**使 producer wave 占寄存器不算力，限制每 thread block 的 output tile size 与 arithmetic intensity。

论文目标：给出 **首个系统化的 AMD AI kernel 设计原则**，封装为 HipKittens (HK) 开源框架，验证能否用统一 tile DSL 在 CDNA3/CDNA4 上实现与 AITER 汇编竞争的性能，并在汇编未覆盖场景显著领先编译器基线。

## 关键观察 / 隐含假设

- **观察 1（wave specialization 在 AMD 结构性失效）**：同一 BF16 GEMM（M=N=K=8192），B200 上 ThunderKittens/CUTLASS 用 producer-consumer 可达峰值；MI355X 上仅当 **零 producer**（无 wave specialization）且 output tile 256×256 时才能追平峰值，producer 数量增加则 TFLOPS 单调下降（Table 2）。
  - **依赖假设**：瓶颈是 AMD 将 SIMD 512 寄存器 **静态划分**给所有 resident wave，producer 不贡献 MFMA 却消耗寄存器预算；NVIDIA 的 TMA、register reallocation、mbarrier、更大 per-SM SRAM 等特性在 AMD 上缺失或不等价。
  - **可能失效场景**：未来 AMD 引入动态寄存器重分配或更强 async copy 后，producer-consumer 可能重新可行；memory-bound 小 tile kernel 上 register pressure 不那么主导时，差异可能缩小。

- **观察 2（8-wave ping-pong 是多数 workload 的「足够好」调度）**：每 CU 4 SIMD，每 SIMD 驻留 2 wave 轮换 compute↔memory，用 conditional barrier 交替；对 compute/memory 大致平衡的 GEMM、FP8 GEMM、attention forward 可 **匹配 AITER 汇编**；GQA non-causal backward 8-wave 比 PyTorch SDPA/CK/AITER 快 **1.8×**，4-wave interleave 进一步到 **2.3×**（Table 3、Fig. 8）。
  - **依赖假设**：MFMA 与 VMEM/LDS pipeline 可通过 wave 级交替充分隐藏 latency；8-wave 允许大 tile primitive（类似 wave specialization 可读性），4-wave 需小 tile 细粒度 interleave 以饱和 imbalanced workload。
  - **可能失效场景**：极端 compute-heavy 或 memory-heavy 且单 pattern 无法动态 adapt 时，固定 8-wave 可能不如 workload-specific 汇编 interleave；4-wave 代码膨胀（Table 3 hot loop 更大）增加维护成本。

- **观察 3（显式寄存器 pin 是 attention backward 达峰的关键）**：4-wave MHA non-causal backward 用 HIPCC 管理寄存器仅 **855 TFLOPS**，AITER 汇编 **1018 TFLOPS**；HK pin AGPR 作 MFMA A/B 输入后匹配 AITER（Table 1）。
  - **依赖假设**：backward 需混用多种 MFMA shape（16×16×32、32×32×16）与 row/column layout shared load；编译器寄存器 lifetime 与 AGPR 限制是主要损失源，而非算法本身。
  - **可能失效场景**：LLVM/HIPCC 未来修复 AGPR 路径后 pin 收益下降；更复杂 kernel（多 stage pipeline + 大量 scalar ops）手动 pin 的工程负担可能不可扩展。

- **观察 4（chiplet 架构下 naive grid schedule 严重浪费 L2/LLC）**：MI355X 8 XCD × 32 CU，naive row-major block 分配对 M=N=K=9216 BF16 GEMM 仅 **36% L2 hit**；单独优化 L2 会损害 LLC；Algorithm 1 联合调 window height W 与 chunk size C 可 **+19%** 性能（Table 4），coprime tile 数与 XCD 数时收益更突出。
  - **依赖假设**：L2 miss ~300ns、LLC miss ~500ns，L2 带宽约为 LLC **3×**；硬件按 round-robin 将 thread block 分配到 XCD。
  - **可能失效场景**：非 GEMM、非规则 output tiling、或 monolithic GPU 无 chiplet 时 Algorithm 1 收益有限；W/C 需 per-shape 调参，缺乏自动 cost model。

- **假设 1（tile 抽象可跨 NVIDIA/AMD 统一 front-end）**：PyTorch 风格 bulk operator（mma、exp、add 等）+ tile 类型足以让开发者表达多数 AI kernel，vendor 差异下沉到 layout/swizzle/schedule 实现。
  - **证据强度**：**中强**——HK 在 GEMM/attention/RoPE/LayerNorm 等 suite 验证，且 training sanity check（Llama 1B、BERT 110M、10B token Slim Pajama）perplexity 匹配 PyTorch/AITER；但 AMD shared memory swizzle 需对 **HBM 地址**做（非 NVIDIA TMA 式 shared 地址 swizzle），instantiation 差异仍显著。

- **假设 2（汇编库 AITER 代表「可复现 peak」但不可扩展）**：AITER 在常见形状上极强，但 d=64 attention、GQA backward 等场景覆盖不全，留下 HK 1.2–10× 领先空间。
  - **证据强度**：**中**——对比基于 ROCm 7.0 preview Docker、500 warmup + 100 measure；AITER 自身也在演进，且论文作者含 AMD 合作者，baseline 选择可能存在利益相关，但 Figure 7–9 覆盖多形状。

## 核心方法

HipKittens 在 ThunderKittens 代码基上为 AMD CDNA3/4 重设三类 primitive，front-end 仍用 **tile + bulk operator**（§3.1）。

**1. 可编程内存（寄存器 + shared + global）优化**

- **显式寄存器 pin**：开发者用 `register ranges` 将 tile 绑定到指定 VGPR/AGPR，绕过 HIPCC，接口与 compiler-managed tile 一致（§3.2.1、Appendix D.3）。直接回应观察 3，使 backward 等 register-heavy workload 达峰。
- **异构 MFMA shape 的 tile layout**：AMD 各 matrix instruction layout 无统一 16×16 building block（Fig. 3），HK 在 tile 创建时自动处理 phase/bank 差异；register 默认最小 MFMA shape 以最大化调度自由度（§3.2.2）。
- **Shared memory swizzle**：针对常见共现 layout（如 16×32 row + column load）提供 bank-conflict-free swizzle（Fig. 4）；证明 **单一 swizzle 无法覆盖所有 AMD 指令粒度**（ds_write_b64 vs ds_read_b128 冲突，Appendix D.1）。
- **Global async load**：CDNA3/4 支持 HBM→LDS `buffer_load`；swizzle 在 **HBM 侧地址**完成，而非 TK 的 shared 地址 swizzle（§3.2.2）。

**2. Compute–memory 重叠：8-wave ping-pong 与 4-wave interleave**

回应观察 1，HK **不采用** NVIDIA 主导 wave specialization，而提供两种可复用 pattern（§3.3.2）：

- **8-wave ping-pong**：每 thread block 8 wave（每 SIMD 2 wave），分两组各 4 wave，组内 wave 在 compute（MFMA）与 memory（prefetch）间 ping-pong，`s_barrier` 控制交替；适合 GEMM、attention forward 等平衡 workload。GEMM hot loop 见 Appendix E.1。
- **4-wave interleave**：每 SIMD 1 wave，单 wave 内细粒度交错 compute/memory 指令，饱和 MFMA 与 LDS pipeline；代码更长（Table 3）但 GQA backward 等 imbalanced workload 更快。

辅以 LLVM `sched_barrier` / `sched_group_barrier` / `s_setprio` hints（Appendix D.4）在 cluster 级约束指令序，避免完全手工逐条调度。

**3. 非可编程 cache：chiplet-aware grid schedule**

Algorithm 1 两步：(1) **XCD grouping**——flatten 2D grid，重映射使连续 C 个 block ID 落在同一 XCD，降 cross-chiplet traffic；(2) **hierarchical windowed traversal**——按高度 W 的垂直窗口遍历，优化 L2 tile reuse。W 优先拉高 L2 hit（带宽 3× LLC），C 协调跨 XCD LLC reuse（§3.4）。MI355X 经验上 L2 tile **8×4 或 4×8** 利用率最佳。

**Kernel suite**：BF16/FP8 GEMM、GQA/MHA attention fwd/bwd（causal/non-causal，d=64/128）、fused dropout-residual-LayerNorm、RoPE；开源 https://github.com/HazyResearch/HipKittens 。

与 [[ParallelKittens-MLSys26|ParallelKittens]] 的分工：后者解决 **multi-GPU** overlap，HK 聚焦 **单卡 AMD** peak kernel primitive；二者同属 ThunderKittens 家族。与 Triton/Mojo/TileLang 对比：HK 保留 C++ 细粒度控制而非 Python DSL 编译路径，并针对 AMD 寄存器/chiplet 约束提供一等公民抽象（§B.1）。

## 设计取舍

- 取舍 1：保留 tile 可读性 vs 汇编级 interleave：8-wave 用大 tile、代码紧凑，多数场景匹配 AITER；4-wave 用最小 base tile、hot loop 膨胀，换 imbalanced workload 上额外 ~28%（2.3× vs 1.8× on GQA bwd）。开发者需在两种 pattern 间手动选择，无自动 selector。
- **取舍 2：显式寄存器 pin vs 编译器托管**：pin 达 peak backward，但增加寄存器分配认知负担；HK 保留双路径供选择。完全 pin 大型 kernel 的可维护性论文未系统评估。
- **取舍 3：手工 swizzle 子集 vs 全 layout 自动生成**：只为常见 co-occurring layout 提供 swizzle，降低代码爆炸；边缘 MFMA shape 需开发者自行处理或接受 bank conflict。
- **取舍 4：chiplet swizzle 调参 (W,C) vs 通用 cost model**：Algorithm 1 简单可调，但 GEMM shape 变化需重新 empirical tune；tail region（xy > limit）保持原序，避免小 problem 破坏。
- **边界条件**：在 MI325X（65KB shared）上 GEMM 无法 shared double-buffer，退化为 **register double-buffer + ds_write**（Appendix E.1）；设计对 CDNA3/4 chiplet 最优雅，monolithic 或未来 NVIDIA 移植不适用；benchmark 以 **TFLOPS 平均**为主，未覆盖 tail latency 或多租户 serving。

## 实验与结果

**平台**：MI325X (CDNA3)、MI355X (CDNA4)；ROCm 7.0 preview Docker；500 warmup + 100 measure；输入 N(0,1)。Baselines：AITER、Composable Kernel、PyTorch (compiled/SDPA)、Triton、HipBLASLT。

**GEMM（BF16/FP8）**
- HK **与 AITER/HipBLASLT 竞争**；单一 **8-wave** schedule 泛化多 problem shape。
- vs Triton：**1.3–3.0×**（§4.1）。

**Attention forward（GQA/MHA，causal/non-causal，d=64/128）**
- 平均优于全部 AMD 基线，含 AITER 汇编：vs AITER **1.0–2.1×**，vs PyTorch SDPA **1.3–4.5×**，vs CK **1.0–1.4×**，vs Triton **1.2–4.5×**。
- 8-wave ping-pong；与 [[Flash-Attention]]-3 在可比设置下 **竞争**（§4.2）。

**Attention backward**
- GQA：**1.8–2.5×** 于 baselines（Fig. 8）；MHA 与 AITER 汇编 **竞争**（Fig. 15）。
- 关键：多 MFMA shape + pinned AGPR + 异构 shared load pattern。

**Memory-bound（dropout-residual-LayerNorm、RoPE）**
- vs AITER/PyTorch compiled：**1.1–2.2×**；compiled LayerNorm L2 hit 比 HK 低 **23%**（§B.2）。

**汇编未覆盖 / memory-bound 场景**
- d=64 attention、GQA backward 等：**1.2–10×** 于可用 baselines（Abstract、§4）。

**Chiplet ablation（Table 4）**
- Naive row-major L2 hit **36%** → tuned schedule **+19%** end-to-end GEMM performance。

**Training sanity**
- Llama 1B、BERT 110M 在 Slim Pajama 10B token 后 perplexity 与 PyTorch/AITER **一致**（§4 末段）。

**未报告**：端到端 LLM serving 吞吐/TPOT、多卡、功耗、编译时间、kernel 自动 shape 选择、非 BF16/FP8 精度全面矩阵。

## Critical Analysis

### 论证链条

论文 narrative 清晰：**测量 AMD 与 NVIDIA 调度差异（Table 2）→ 提出 8-wave/4-wave 替代 wave specialization → 用 AGPR pin 解决 compiler gap（Table 1）→ chiplet schedule 挖 cache（Table 4）→  broad kernel suite 验证**。tile 抽象可移植性主张由「同一 front-end、不同 instantiation」与 training perplexity match 支撑，链条在 **single-GPU AMD AI kernel** 范畴内较闭合。

最脆跳步是 **「HK 原则可导向跨厂商统一软件栈」**（§5）：实验仅 AMD；NVIDIA 侧仍由 ThunderKittens/[[FlashAttention-4-MLSys26|FA-4]] 等独立演进，未证明同一 codebase 双端维护成本低于两套 specialist。第二跳步是把 **TFLOPS micro-benchmark 优势**外推到 **生产推理栈端到端收益**——未测 vLLM/SGLang 集成、continuous batching 下算子占比、或 ROCm 栈其他瓶颈（通信、框架 overhead）。

### 假设压力测试

- **Workload**：固定 batch/head 配置（如 batch 16、64 query heads、8 KV heads）；长序列、变长 batch、speculative decoding、MoE expert GEMM 未覆盖。GQA backward 大领先部分源于 AITER 该路径不成熟——随 AITER 补齐，倍数可能收缩。
- **硬件**：MI325X/MI355X CDNA3/4；RDNA 消费卡、未来 CDNA5、或 AMD 修复寄存器模型后 8-wave 是否仍最优未知。Chiplet swizzle 对非 8-XCD 拓扑需重写。
- **编译器生态**：结论部分依赖「Triton/HIPCC 在 AMD 上系统性不足」（§B.2）；ROCm 7.x 持续更新可能侵蚀 HK 相对编译器的领先幅度，但不必然消除 pin/swizzle/chiplet 需求。
- **合作结构**：多位作者来自 AMD，AITER baseline 版本与调优细节外部难以完全复现；「30% SoTA」等数字需随 AITER 更新而变。

### 实验可信度

- **强项**：多 workload（GEMM/attn/fused ops）、多 shape、CDNA3+4 双平台；ablation 覆盖 wave specialization（Table 2）、schedule 对比（Table 3）、grid schedule（Table 4）、register pin（Table 1）；training perplexity 提供 correctness 信号而不仅是 TFLOPS。
- **弱点**：(1) 主指标 TFLOPS/s 平均，缺 P99、power、code size 系统对比；(2) attention forward vs FA-3 对比条件（硬件代际、精度、sequence length）需仔细对齐，论文 claim「competitive」但非全面胜出；(3) Triton/Mojo baseline 可能未充分 inline asm 调优（§B.2 承认生态 brittleness，但也可能低估优化后 compiler）；(4) 10× 上界来自少数汇编空白场景，不宜作为通用 speedup 宣传。

### 系统性缺陷

- **可维护性**：4-wave kernel 代码量显著大于 8-wave（Table 3）；手动 pin + sched hints + 双 swizzle 路径对普通 ML 工程师门槛高，论文未讨论 onboarding 成本 vs AITER 黑盒调用。
- **自动化**：W/C chiplet 参数、8-wave vs 4-wave 选择无 profiler 指导；每新 MFMA shape 可能需新 swizzle 推导（虽有 phase/bank solver，Appendix D.2）。
- **框架集成**：提供 Python bindings 但 **未演示** PyTorch/vLLM 插件路径、CUDA Graph 兼容性、或 dynamic shape serving；HK 仍是 kernel library 而非 inference stack。
- **多卡与通信**：论文未讨论；[[ParallelKittens-MLSys26|ParallelKittens]] 补 NVIDIA 多卡，AMD 侧同类工作空白。
- **正确性边界**：training sanity 仅 10B token、两模型；FP8 在 AMD PyTorch 上仍 experimental；numerical edge case（deterministic backward、extreme head dim）论文未讨论。
- **运维/可观测性**：论文未讨论。

## 局限与 Future Work

- **局限 1**：instantiation 仍 vendor-specific——AMD swizzle、AGPR pin、chiplet schedule 无法直接复用到 NVIDIA；「统一 DSL」停留在抽象层，非单 binary 跨平台。
- **局限 2**：4-wave interleave 牺牲 programmability，代码膨胀；论文未提供从 8-wave 到 4-wave 的机械化降级/升级工具。
- **局限 3**：Chiplet Algorithm 1 需 per-GEMM-shape 调 W/C；缺乏 analytical cost model 或 autotuner（对比 Triton autotune 或 CK profiler）。
- **局限 4**：实验以 micro-benchmark TFLOPS 为主，缺少端到端 LLM training/inference 与框架集成数据；FP6 kernel 仅初步探索（Appendix F），作者称 expect additional improvements。
- **局限 5**：对编译器生态的批评基于 2025 ROCm 7.0 时间点，随 HIPCC/Triton 改进，部分 gap 可能缩小，论文未给出持续跟踪机制。
- **Future work 1**：将 HK primitive 嵌入 PyTorch/ROCm 官方 kernel 路径或 vLLM AMD backend，测量 **端到端 serving** 而非 isolated TFLOPS，验证「追平 AITER」是否转化为用户可见 latency/$/token。
- **Future work 2**：基于 roofline + register pressure model **自动选择** 8-wave vs 4-wave 与 W/C，减少 per-kernel 手工调参。
- **Future work 3**：与 [[ParallelKittens-MLSys26|ParallelKittens]] 类比，系统化 **AMD multi-GPU** tile DSL（Infinity Fabric/NIC overlap），检验 chiplet 原则是否延伸到 inter-GPU scheduling。
- **Future work 4**：在 HIPCC 修复 AGPR 或引入 register reallocation 后复测 pin 与 wave specialization 收益，界定「硬件演进使 HK 原语过时」的临界点。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、[[Quantization]]
- **同类系统**：ThunderKittens、[[ParallelKittens-MLSys26|ParallelKittens]]、[[FlashAttention-4-MLSys26|FlashAttention-4]]、CuTe DSL、Gluon、Triton、TileLang、Mojo、AITER、Composable Kernel
- **同会议**：[[MLSys-2026]]
- **对比**：NVIDIA wave specialization + TMA（FA-3/TK）vs AMD 8-wave ping-pong + AGPR pin + chiplet swizzle（HK）
