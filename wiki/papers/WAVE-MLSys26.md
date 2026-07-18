---
type: paper
name: WAVE
full_title: "WAVE: A Symbolic Python DSL and Compiler for High Performance Machine Learning"
authors: [Harsh Menon, Oleksandr Zinenko, Gaurav Verma, Stanley Winata, Ivan Butygin, et al.]
venue: MLSys
year: 2026
tags: [kernel-dsl, gpu, amd, attention, gemm, compiler, mlir, wavefront]
source_pdf: "[[68d30a9594728bc39aa24be94b319d21.pdf]]"
source_md: "[[68d30a9594728bc39aa24be94b319d21]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# WAVE: A Symbolic Python DSL and Compiler for High Performance Machine Learning (MLSys 2026)

> **一句话总结**：在「matrix core 要求复杂的 per-thread block-strided 地址分布，而 Triton/TileLang 仍把地址算术与 kernel 逻辑纠缠，导致难维护且跨代际可移植性差」这一观察下，Wave 用 wave-level implicit indexing + symbolic constraints 让 compiler 推导 index sequence 并 lower 到 SIMT，在 AMD MI300/MI325/RX9070 上 attention 与 GEMM 相对 Triton/PyTorch 实现 **harmonic mean 8–102% 更快**，global memory coarsening 单独贡献 **~3×** 吞吐。

## 问题与动机

生成式 ML 把 GPU 设计推向越来越专精的 matrix/tensor core（Nvidia Tensor Core、AMD Matrix Core、TPU systolic array）。**未命中 matrix core 而回退到常规 VALU 路径，可能带来一个数量级的性能损失**。但激活这些单元要求：

1. 操作数按 lane/thread/workgroup 精确分布到寄存器或 LDS（shared memory）；
2. 每个 thread 在 global memory 中做非平凡的 offset 计算（tiling、swizzling、distribution）；
3. 同一代硬件上 matrix core 配置本身可变（如 AMD CDNA 支持 16×16×16 与 32×32×8 bfloat16 MMA）。

传统 SIMT（CUDA/HIP）与 block-level DSL（[[Triton]]、TileLang、cuTile）都把**计算逻辑与硬件-specific 地址算术写在一起**。kernel 难读、难维护、难跨 MI300→RX9070→未来代际迁移。与此同时，[[vLLM]]、[[SGLang]] 等 inference stack 需要**硬件解耦**的高性能 kernel 实现，否则每个模型×每个硬件代际都要维护一份手写地址逻辑，代码规模爆炸。

Wave 的定位是：Python 嵌入的 **wave-level（subgroup）kernel DSL**，把地址生成从作者代码中剥离，同时保留对 register-level 数据流的显式控制，经 torch.fx + MLIR/LLVM 编译到 AMD GPU（primary target）。

## 关键观察 / 隐含假设

- **观察 1：matrix core 的有效编程单位是 wavefront/subgroup，而非独立 thread**——VALU 与 matrix core 共享寄存器/LDS，且 MMA 指令需要多 thread 协同取数。
  - **依赖假设**：目标 workload 的 hot path 是 GEMM/attention 等可被 MMA 覆盖的 dense 线性代数；kernel 性能由能否稳定发出 `v_mfma`/`wmma` 决定。
  - **可能失效场景**：element-wise、不规则稀疏、或 NVIDIA Hopper/Blackwell 上 wgmma 直接操作 shared memory 的路径——论文承认后者只有 memory optimization 相关，MMA 路径需另设计。

- **观察 2：地址算术的模式高度结构化，可用 block-strided index sequence \((O, N, D)\) 紧凑表达，且应由 MMA layout 约束主导推导**。
  - **依赖假设**：用户通过 `WorkgroupConstraint` / `WaveConstraint` / `TilingConstraint` / `HardwareConstraint` 声明映射；compiler 用 provenance lattice（`mma > reduce > mem`）解决冲突。
  - **可能失效场景**：极度动态 indexing（不规则稀疏 tensor、复杂 control flow）超出 symbolic constraint 表达能力；论文 future work 才提 dependent-iterator / sparse 扩展。

- **观察 3：AMD Instinct/Radeon 是公开 tooling  underserved 的平台**——Triton 有生态，但 matrix core 低级优化与跨 CDNA→RDNA 可移植性仍痛。
  - **依赖假设**：MLIR `amdgpu` dialect + LLVM 后端足够成熟；主要客户 workload 是 LLM attention/GEMM/MoE。
  - **证据强度**：**强**——在 MI300/MI325/RX9070 三套硬件上评测，并集成进 [[SGLang]] attention backend；但 **Nvidia 路径基本未验证**。

- 观察 4：用更多 LDS 换 on-chip reuse 是 attention 上与 Triton 角力的有效杠杆——Wave 在 Llama-2-13B 等 case 用 25–34 KB 额外 LDS 换取 competitive 或更高吞吐，occupancy 略低于 Triton 但 end-to-end 更快。
  - **依赖假设**：workgroup LDS budget 未触达硬件上限；attention 的 KV 重用值得 staging。
  - **可能失效场景**：极大 head count / 极小 batch 使 occupancy 成为硬瓶颈；多 kernel 并发争用 LDS 时收益反转。

- **假设 1：late specialization（symbolic tile size、MMA type、threads_per_wave）足以覆盖 prefill/decode、BHSD/BSHD layout 等变体，无需 fork 源码**。
  - **证据强度**：**中**——同一 attention 源码生成 symbolic prefill 与 seq_len=1 decode；BSHD 仅交换 boundary indexing symbols；RX9070 移植只改 `threads_per_wave=32` 与 `MMAType.RDNA4_*`。

## 核心方法

Wave 两大设计原则：

1. **Implicit Indexing**：地址由 constraints 推导，作者不写 subscript/offset 算术。
2. **Symbolic Mapping**：tile size、wave size、MMA type、address space 等保持符号，编译末期再 specialize。

### DSL 与 device mapping

用户写 `@wave(constraints)` 装饰的 Python 函数，张量类型带符号 shape（如 `Memory[M, K, ADDRESS_SPACE_0, f16]`）。显式归约维用 `@iterate(K, init_args=[...])` 装饰器——**无显式 induction variable**，需要时用 symbol-bound tensor 构造 mask。

**Constraints 体系**（Listing 3）：
- `WorkgroupConstraint(dim, tile, axis)`：映射到 blockIdx 维度；
- `WaveConstraint(dim, elems_per_wave)`：workgroup 内二级 wave 切分；
- `TilingConstraint(dim, tile)`：顺序维（含 reduction K）的 loop tile；
- `HardwareConstraint(threads_per_wave, mma_type)`：选定 MMA 指令及其 per-thread 分布。

三级 tiling：workgroup → wave → register（由 MMA layout 隐式确定）。block size 预期非递增；tile 不可整除时 masking/padding（可配置 peel）。

支持 **dynamic value remapping**（MoE `expert_id` 等）：`IndexMapping` + `set_symbol` 把 runtime 值注入 symbolic subscript。

### Lowering pipeline

1. **Type inference**：forward sparse dataflow，join 操作数类型；MMA 投影掉 reduction 维；memory op 切换 address space。
2. **Index sequence construction**：每维 \((O, N, D)\) 表示 per-thread 访问 \(\{O + iD \mid 0 \le i < N\}\)；双向传播至 fixpoint；MMA 配置设定初始 vector width（如 K 维 \(D=4\)）。
3. **Expansion（SIMW→SIMT）**：对每维复制 `dim_scaling = T·W/V` 份 per-thread op；reduction 维链式累加。
4. **Optimization（§4）**：
   - **Global read coarsening**：合并 consecutive vector load 饱和 HBM 通道，必要时 spill 到 LDS 再 per-thread 分发；
   - **Schedule reordering**：software pipelining + subgroup ping-pong，重叠 MMA 与 memory；
   - **Workgroup reordering**：Morton/stripe 映射改善 L2 locality。
5. **Codegen**：torch.fx graph → MLIR（arith/vector/scf + amdgpu）→ LLVM JIT。

**Memory 模型**：global→shared **自动插入**；shared→register **显式 `read`**，compiler 推断 sync/coalescing。与 Triton 全自动 staging、Exo 全手动形成 hybrid。

### 集成

- PyTorch `nn.Module` 子类，零拷贝 tensor ABI + compilation cache；
- [[SGLang]] attention backend：extend / paged decode / prefill，ABI adapter 无额外 copy。

## 设计取舍

- **Implicit indexing vs 表达力**：extend attention kernel 论文称可少 **15 行** index 语句，但 irregular sparse、复杂 gather 需 future dependent-iterator 扩展；当前强项在 structured GEMM/attention。
- **Symbolic parametricity vs 优化力度**：保留符号 shape 便于一源码多模式（prefill/decode），但 expansion 要求 \(T, W, V\) 编译期具体化——inner loop 完全 unroll，不规则边界增加 predication 与 VGPR 压力（706×14336×4096 case）。
- **Hybrid memory staging**：global→LDS 自动、register 显式——比 Triton 更可控，比手写 CUDA 更省心；coarsening 仅对已 staging 的 load 启用，避免 LDS 膨胀伤 occupancy。
- **AMD-first vs retargetability**：MLIR 路径理论上可移植，但 Nvidia 上仅 memory opt 有意义；论文 primary 贡献锚定 CDNA3/RDNA4。
- **边界条件**：**对齐良好、M/N 较大的 LLM GEMM/attention** 最优雅；**小 M、高 predication、VGPR 受限** 时 occupancy 与 tail tile 开销显著。

## 实验与结果

**Setup**：MI300X、MI325X、RX9070XT；ROCm 7.0；Wave 3.7.0 + IREE/MLIR。Baselines：PyTorch eager/compile、Triton 3.4.0、TileLang、TVM Ansor/MetaSchedule。20 warmup + 100 measured；attention 对 Triton 与 Wave 各 **6 组配置** autotune 后取 uniform best。

**Attention（prefill，Figure 2–4）**：

| Layout | Hardware | vs PyTorch (eager) | vs Triton |
|--------|----------|-------------------|-----------|
| BHSD | MI300X | **5–294%** faster（HM **101.7%**） | **6–152%** faster（HM **37.8%**） |
| BSHD | MI325X | **20–166%** faster（HM **94.3%**） | **15% slower – 74% faster**（HM **8.2%** faster） |
| BHSD/BSHD | RX9070XT | 优于 PyTorch fused | LDS ~80% vs PyTorch 30–35%；更多 `ds.bpermute`/MFMA |

Wave 用额外 LDS（25–34 KB）换 reuse；Llama-2-13B 上 occupancy 与 Triton 相近（~0.64 waves/CU）但指令更少 barrier、更少 global traffic。

**GEMM \(C = AB^T\)，573 shapes（Figure 5–7）**：

- 相对 Triton/PyTorch compile：**predominantly faster**；大模型（GPT-OSS-20B、Llama-3.3-70B）**20–30%** 领先 Triton；小模型与 Triton 同档、PyTorch 库有时快 10–20%。
- vs TileLang：**~2×** 平均；vs TVM：**~10×**（TVM 难收敛 + 缺 AMD 低级优化）。
- 8192³ FP16：**~900 TFLOP/s**（峰值 940，compute-bound）；706×14336×4096：**~350–400 TFLOP/s**，L1/L2 bandwidth-bound。
- RX9070 移植：算法不变，仅改 `threads_per_wave`/`mma_type`；GEMM **4–47%** faster than PyTorch（HM **13.9%**）；32 WMMA vs PyTorch 16，更少 branch（2 vs 34）。

**Optimization ablation（Figure 8）**：

- 禁用 global memory opt：**2.7–4.4× slowdown**（HM **3.0×**）；Llama-2-13B 上 HBM 带宽 248→599 GB/s，TFLOPs 215.6→40.1。
- 禁用 scheduling opt：**24–35% slowdown**（HM **30%**）。

## Critical Analysis

### 论证链条

主链条：**matrix core 地址算术是独立、可推导、且应由 MMA layout 主导的结构化问题** → **constraint + index sequence 传播把地址从 kernel 逻辑解耦** → **expansion + MLIR 优化生成高效 MFMA/WMMA 内核** → **attention/GEMM 匹配或超越 Triton/PyTorch，且 CDNA→RDNA 仅需 retune 参数**。

Global coarsening ablation（3×）与 assembly 分析（`buffer_load_dwordx4` 12 vs 20、`v_mfma` 使用）有力支撑「compiler 推导的地址 + 目标感知优化」确实落地到硬件 primitive，而非仅 DSL 语法糖。

薄弱环节：**Nvidia 可移植性几乎未实验**；Triton baseline 在 attention 上使用 autotune 但 GEMM 部分依赖 ROCm AITER 库——baseline 强度因 kernel 而异；部分数字句子在 MinerU markdown 中有断裂（§6.2 BSHD 段落），精确 HM 应以 PDF 核对。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| Index sequence 可覆盖 LLM hot kernels | GEMM + attention + MoE appendix | 不规则稀疏、dynamic shape 超出 constraint |
| 额外 LDS 换吞吐 | Attention counter 分析 | LDS/occupancy 极限、多 tenant 并发 |
| Symbolic 一源码多模式 | prefill/decode、BHSD/BSHD swap | 需完全不同 algorithm（如 new attention variant）时仍要改 logic |
| AMD MLIR 后端足够 | 三平台实测 + SGLang 集成 | 新 uarch 指令变体、compiler bug 时回退成本高 |
| 6-config tuning 公平 | 明确 mirror Triton autotune | 更大 search space 可能进一步拉大或缩小 gap |

### 实验可信度

- **优势**：覆盖 **三种 AMD GPU**（datacenter + consumer）；573 GEMM shapes + 多 LLM attention shape；layout 变体（BHSD/BSHD）；optimization ablation + ISA/counter 分析；SGLang 生产路径集成。
- **局限**：**无 Nvidia baseline**；TVM/TileLang 作为弱 baseline 可能放大 Wave 优势；在线 serving latency / tail latency / 多 stream 并发 **未测**；prefill 为主，decode 路径仅通过 symbolic specialization 声称、未给独立 decode benchmark 表。
- **缺失**：compilation time 与 cache hit 外的 cold-start 成本仅一笔带过；与 hand-tuned AITER/rocBLAS 的全面对照不完整。

### 系统性缺陷

- **编译栈重量**：torch.fx → Sympy symbolic → MLIR → LLVM JIT，debug 需跨多层 IR；**论文未讨论** compile failure 率与用户-facing error 质量。
- **Occupancy / VGPR 敏感**：不规则 shape 上 predication + 高 VGPR（244 vs 192 in ablation）限制 active waves——论文识别但未给出 auto-tuning 与 occupancy 的 co-design。
- **Nvidia / 跨厂商**：Hopper wgmma 与 CDNA mfma 语义差异大；当前设计对 **单一厂商 AMD 生态** 最优，跨云部署需 duplicate tuning pipeline。
- **运维**：SGLang adapter 降低集成成本，但 Wave 作为新 DSL，团队需学习 constraint 体系与 MMA 类型枚举；**论文未讨论** 版本升级时 compilation cache 失效与 kernel 回归测试策略。
- **正确性**：masking/padding 处理 partial tile；**论文未提供** 与 reference 的 bitwise/numerical tolerance 系统报告。

## 局限与 Future Work

- **局限 1**（硬件范围）：评测锚定 **AMD MI300/MI325/RX9070**；Nvidia 仅讨论性说明，无性能数据。
- **局限 2**（表达力）：当前 primitives 面向 dense structured kernel；irregular/sparse tensor 需扩展 indexing symbols（论文指向 MLIR sparse tensor + TACO 式 dependent iterator）。
- **局限 3**（不规则 shape）**：小 M、partial macro-tile 导致 predication 与 occupancy 下降（706×14336×4096），距 roofline 仍有 gap。
- **局限 4**（实验边界）：attention 以 **prefill throughput** 为主；端到端 inference（含 KV cache 管理开销、decode batching）仅有 SGLang 集成声明，缺系统级 latency SLO 表。
- **Future work 1**：在 **Nvidia Hopper/Blackwell** 上测量：仅 memory opt 够否，或需重建 wave-level MMA 约束与 wgmma shared-memory 语义。
- **Future work 2**：对 **compilation time × autotune search × achieved TFLOPs** 做 Pareto 曲线，与 Triton autotune 分钟级成本对照，评估 DSL 在 CI/CD 中的可维护性。
- **Future work 3**：将 **occupancy-aware tile selection** 与 constraint solver 联合——在 LDS/VGPR/predication 约束下自动选 BLOCK\_M/N/K，减少手工 6-config tuning。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、[[MoE]]、[[KV-Cache]]、matrix core、index sequence、software pipelining
- **同类系统**：[[Triton]]、TileLang、cuTile、[[PyTorch]] compile、TVM/Halide、Exo、Helion
- **集成栈**：[[SGLang]]、[[vLLM]]、torch.fx、MLIR/LLVM
- **同会议**：[[MLSys-2026]]
- **对比**：Wave vs Triton——wave-level implicit indexing 解耦地址算术，trade 更多 LDS 换 reuse；vs TileLang/TVM——AMD 后端 + 低级 MFMA/LDS 优化带来数量级差距（但 baseline 实现成熟度不均）
