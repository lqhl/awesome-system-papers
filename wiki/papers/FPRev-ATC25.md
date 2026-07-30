---
type: paper
name: FPRev
full_title: "Revealing Floating-Point Accumulation Orders in Software/Hardware Implementations"
authors: [Peichen Xie, Yanjie Gao, Yang Wang, Jilong Xue]
venue: ATC
year: 2025
tags: [floating-point, reproducibility, testing, tensor-core, numerical-analysis]
source_pdf: "[[atc2025-xie.pdf]]"
source_md: "[[atc2025-xie]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# FPRev：揭示软件/硬件实现中的浮点累加顺序（ATC 2025）

> **原题**：Revealing Floating-Point Accumulation Orders in Software/Hardware Implementations

> **一句话总结**：浮点累加顺序在 [[NumPy]]/[[PyTorch]]/[[BLAS]] 后端中普遍未文档化且因非结合性导致跨平台结果不一致；FPRev 用 masked all-one array（±M 掩码 + swamping）黑盒探测，将累加顺序还原为 summation tree，复杂度从 brute-force 的 O(4ⁿ/n^1.5·t(n)) 降至 Ω(n·t(n))–O(n²·t(n))，并首次支持 [[Tensor-Core]] 的 multi-term fused summation（multiway tree）；case study 显示 sum 可跨 CPU/GPU 复现，但 dot/matmul 等 BLAS op 不可。

## 问题与动机

浮点加法不满足结合律，但业界对 summation、dot product、matrix multiplication 等 accumulation-based operations（AccumOps）**没有统一的累加顺序规范**。同一算子在 [[Intel MKL]]、[[OpenBLAS]]、[[cuBLAS]]、[[NumPy]]、[[PyTorch]] 及不同 CPU/GPU 上可能采用不同顺序以追求 SIMD、cache、多线程或 [[Tensor-Core]] 吞吐，而实现方几乎从不公开顺序。后果是：在航空航天、银行、科学计算、[[LLM]] 训练等要求数值复现的场景，跨版本/跨硬件的微小差异都可能 disqualify 软件。

作者 claim：需要一个**非侵入式、确定性**的诊断工具，能从黑盒实现中还原累加顺序（summation tree），供开发者（1）以 revealed order 为 spec 复现行为，（2）比较两系统实现是否等价。FPRev 即为此工具，并扩展到 matrix accelerator 的非标准 multi-term fused summation。

## 关键观察 / 隐含假设

- **观察 1**：用 ±M 掩码构造的 masked all-one array 能把累加顺序编码进单一标量输出。
  - **证据**：对输入 A^{i,j}（除位置 i、j 为 M、-M 外全为 1.0），当 M 足够大时 M+σ=M、-M+σ=-M（σ≤n-2），仅 M+(-M) 消去后剩余的 1 会贡献到和；输出 = 未被 mask 的 1 的个数 = n - l^{i,j}，其中 l^{i,j} 为 summation tree 中叶子 i、j 的 LCA 子树大小（Section 4.1–4.2）。
  - **依赖假设**：实现使用标准 IEEE-754 加法（或可被同样 mask 逻辑刻画）；M 的动态范围远大于 n；累加顺序对给定实现与硬件**唯一且确定**。
  - **可能失效场景**：[[Tensor-Core]] 低精度 multi-term fused summation（对齐截断后定点加，组内顺序无关）需 multiway tree 扩展；FP8 等低动态范围类型需缩小 summand 并缩放输出（Algorithm 5）；累加器精度不足时 n 过大（float32 约 2²⁴）会无法精确表示「n-2 个 1」的和。

- **观察 2**：主流数值库的 **summation 在同类硬件上顺序一致，BLAS 类 AccumOps 则不一致**。
  - **证据**：NumPy 1.26 在三种 CPU 上 float32 sum 顺序相同（n<8 顺序；8≤n≤128 为 8-way stride + pairwise；n>128 增加 way 数以用多线程）；但 dot/matvec/matmul 在 CPU-1/2 与 CPU-3 上顺序不同（Section 6.1）。PyTorch 2.3 在 V100/A100/H100 上 sum 一致，其他 BLAS op 不一致（Section 6.2）。
  - **依赖假设**：测试的库版本与硬件与论文一致；实现顺序不随输入值或运行时随机化变化。
  - **可能失效场景**：auto-tuner（[[TVM]]、[[Triton]]）按硬件选配置会改变顺序；未来库版本或编译优化可能改变 tree；论文未覆盖 ARM CPU、AMD GPU、多节点 collective。

- **假设 1**：被测 AccumImpl 的累加顺序**不依赖 summand 取值、非随机**（Section 3.2 明确 out of scope）。
  - **证据强度**：**强**——论文以此限定问题形式化，case study 中库行为符合；但未系统测试 value-dependent reduction（如某些 adaptive 算法）。

- **假设 2**：on-demand 计算 l^{i,j} 时，实际库多采用 cache-friendly 顺序，使 FPRev 接近 Ω(n·t(n)) 而非最坏 O(n²·t(n))。
  - **证据强度**：**中**——最坏情况为右到左顺序（Section 5.1.3）；性能实验显示 n=8192 时 FPRev ~1s vs BasicFPRev >100s（Section 7.2），但未对所有 BLAS 后端做最坏顺序证明。

## 核心方法

**问题形式化**：n 个浮点数的求和对应一棵 rooted full binary tree（summation tree），n-1 个内节点各表示一次加法；其他 AccumOps 可抽象为对中间结果的 summation 调用。

**NaiveSol（对照）**：枚举 Catalan 数级别的所有顺序并用随机输入验证，O(4ⁿ/n^1.5 · t(n))，n=16 可超 24 小时，且不同顺序可能对某些输入产生相同输出。

**BasicFPRev**：对全部 0≤i<j<n 构造 A^{i,j}，计算 l^{i,j}=n-SUMIMPL(A^{i,j})，按 l^{i,j} 升序自底向上用 union-find 合并子树（Algorithm 2），总复杂度 Θ(n²·t(n))。

**FPRev 优化**：不再预计算全部 l^{i,j}，而在递归 BUILDSUBTREE 中按需计算；对固定最小标签 i，考察 L_i={l^{i,j}} 的升序，用 J_l={j: l^{i,j}=l} 确定兄弟或子树合并（Algorithm 3–4）。复杂度 Ω(n·t(n))（顺序求和 best case）至 O(n²·t(n))（右到左 worst case）。

**[[Tensor-Core]] / multiway tree**：低精度矩阵乘中，w 个乘积经对齐截断后在定点域一次 fused 加，顺序在组内无关。FPRev 用 w-way 节点建模；构建时比较 BUILDSUBTREE(J_l) 返回子树叶子数与 max(L_{min(J_l)})：相等则为兄弟（新建父节点），否则为父（连边到已有根）。V100/A100/H100 上 half-precision matmul 分别揭示 5-way、9-way、17-way tree，与 prior work 的 (4+1)/(8+1)/(16+1)-term fused summation 一致。

**可视化与复现**：输出 summation tree（如 NumPy n=32 的 8-way + pairwise），开发者可据此在新实现中复制数值行为。低动态范围/低精度累加器场景用 Algorithm 5（tiny summand ε、子树压缩）缓解。

## 设计取舍

- **取舍 1**：选择**确定性数值探测**而非源码分析或 trace 分析——获得对黑盒、编译优化后、并行实现的可移植性，代价是无法处理随机或值相关顺序，且探测成本随 n 多项式增长。
- **取舍 2**：用 swamping 掩码而非 order-independent reproducible summation（如 Demmel-Nguyen 算法）——保留与高效工业实现相同的顺序与性能，而非强制一致但慢数个数量级的算法。
- **取舍 3**：将 matrix accelerator 建模为 multiway tree 而非标准二叉 FMA 链——覆盖 [[Tensor-Core]] 非 IEEE 行为，但组宽 w、截断位数仍随架构变化，需 per-GPU 重新探测。
- **边界条件**：对「仅需 sum 复现」的 CPU/GPU 组合，FPRev 证明 NumPy/PyTorch sum 可安全作 spec；涉及 MKL/cuBLAS 的 matmul/dot 则必须 per-platform 探测或接受不可复现。探测本身要调用 O(n)–O(n²) 次被测算子，对 O(n³) matmul 的 wall-clock 成本显著（RQ2：n=256 时 FPRev 仍比 BasicFPRev 快 82.1×，但绝对时间随 n³ 增长）。

## 实验与结果

- **正确性**：在三种 CPU、三种 NVIDIA GPU 上成功还原 NumPy/PyTorch 多种 AccumOps 的 summation tree，并与已知 Tensor Core 融合宽度结论交叉验证。
- **效率 RQ1**：相对 NaiveSol，n=16 时 BasicFPRev/FPRev <0.01s（NaiveSol >24h）；n=8192 时 FPRev ~1s vs BasicFPRev >100s（NumPy/PyTorch/JAX summation on Xeon E5-2690 v4）。
- **效率 RQ2**：n=256 时 FPRev 相对 BasicFPRev 加速 13.0×（dot）、32.3×（matvec）、82.1×（matmul）（NumPy float32 on 同 CPU）。
- **效率 RQ3**：PyTorch matmul 在多种 CPU/GPU 上 FPRev 一致优于 BasicFPRev。
- **复现性发现**：NumPy/PyTorch **summation 跨测试平台一致**；**dot、matvec、matmul 等 BLAS 后端 op 跨 CPU 核数或 GPU 代际不一致**——直接支撑「不能假设 BLAS 可复现」的 claim。
- **Tensor Core**：V100 5-way、A100 9-way、H100 17-way；A100 上 HMMA.16816 指令形状 K=16 但硬件实为 (8+1)-term fused summation。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| FPRev substantially reduces tree-recovery time for library summation | At `n=16`, FPRev and BasicFPRev each take under 0.01 s while NaiveSol takes over 24 h; at `n=8192`, FPRev takes about 1 s versus BasicFPRev over 100 s (§7.2, Fig. 5) | float32 summation in NumPy 1.26, PyTorch 2.3, and JAX 0.4 on a 24-vcore Xeon E5-2690 v4; this is tool runtime, not AccumOp throughput | high |
| The on-demand algorithm's advantage grows with the operation cost | At `n=256`, FPRev is 13.0×/32.3×/82.1× faster than BasicFPRev for NumPy float32 dot/matvec/matmul (§7.3, Fig. 6) | single Xeon E5-2690 v4; each result is the mean of 10 runs, and speedup measures recovery-tool cost for those three APIs | high |
| Cross-device reproducibility is operation-specific in the measured libraries | NumPy float32 `sum` has identical accumulation orders on the tested CPUs and PyTorch float32 `sum` on the tested GPUs, whereas BLAS-backed operations do not (§6.1–§6.2, Tables 1–2) | NumPy 1.26 on three listed x86 CPUs and PyTorch 2.3 on V100/A100/H100; it does not establish behavior for other versions, vendors, or nondeterministic kernels | high |
| FPRev recovers a hardware-specific multiway Tensor Core accumulation structure | Half-precision PyTorch matmul reveals 5-way/9-way/17-way trees on V100/A100/H100, corroborating prior (4+1)/(8+1)/(16+1)-term fused-summation findings (§6.2, Fig. 4) | cuBLAS-backed half-precision matmul with the paper's tested devices and `n=32` visualization; it does not characterize every Tensor Core instruction or precision mode | high |
| FPRev's construction is practical but has a workload-dependent probe cost | The paper gives a best-to-worst complexity range of Ω(`n·t(n)`) to O(`n²·t(n)`); RQ2 shows the cost rises with dot/matvec/matmul complexity (§5.1.3, §7.3) | deterministic, value-independent AccumImpls only; the result is not a bound for random reductions, atomics, or value-dependent algorithms | high |

## 批判性分析

### 论证链条

观察（非结合性 + 未公开顺序 → 复现风险）→ 设计（mask 输出编码 LCA 子树大小）→ 算法（l^{i,j} 自底向上建树）→ 工具（FPRev + multiway 扩展）→ 实证（库 case study + 复杂度实验）链条整体闭合。关键跳步在于：**从 tree 等价推出跨输入数值等价**——论文在 Section 4.4 用反证法证明对 mask 输入还原 tree 的正确性，但未证明「同 tree 则对所有输入行为一致」（对确定性 IEEE 加法这是标准结论，对 Tensor Core fused 路径依赖 multiway 扩展的正确性证明）。Case study 将「sum 一致」外推为「可安全用于 reproducible software」在**同类硬件、固定版本**下合理，但未覆盖 OS/驱动/编译标志变化。

### 假设压力测试

- **值相关或并行非确定性顺序**：论文明确排除；实际中 OpenMP reduction schedule、GPU atomic 加法等可能违反，FPRev 会失效或需扩展。
- **新数值格式**：FP8/BF16/[[Quantization]]、microscaling（MXFP4/6）需验证 l^{i,j} 性质是否仍成立；作者给出 Algorithm 5 方向但未完整评估。
- **大规模 n**：float32 累加器约 1.67×10⁷ 上界；更大 n 需子树压缩，论文描述 mitigation 但未给出端到端 benchmark。
- **生产 workload**：只测了库级 API 与固定精度；混合精度训练、fusion kernel、自定义 CUDA 是否可探测未充分讨论。

### 实验可信度

- **Benchmark 代表性**：NumPy/PyTorch/JAX 是主流 Python 栈，三种 x86 CPU + 三代 NVIDIA GPU 有跨度；缺 ARM、AMD GPU、云实例多租户噪声。
- **Baseline 公平性**：NaiveSol/BasicFPRev/FPRev 对比清晰；与 Varity、pLiner 等等价性测试工具比的是「揭示顺序」而非「仅判是否等价」，定位不同。
- **Ablation**：BasicFPRev vs FPRev 的 on-demand 优化有充分 scaling 曲线；multiway 分支主要靠 case study 与文献对照，缺少独立 synthetic accelerator 模型。
- **Metric**：以 wall-clock 探测时间与 tree 可视化为主，未量化「错 tree 概率」或「对真实科学计算误差的影响」。

### 系统性缺陷

- **探测成本**：对 matmul 等 O(n³) 实现，FPRev 的多次调用在 n 较大时仍可能昂贵；论文未讨论 CI 中在线探测的预算。
- **运维与版本漂移**：库小版本升级可能静默改变 BLAS 后端顺序；论文未讨论持续监控或 regression 集成。
- **尾延迟 / 隔离**：未涉及。
- **可观测性**：工具输出 tree，但未讨论与 profiler、SASS 反汇编的联合工作流（Section 6.2 有少量 SASS 对照）。
- **故障恢复**：未讨论。
- **安全与合规**：面向 reproducibility 合规场景的应用论证充分，但未评估探测过程对生产系统的影响（仅调用 API，风险较低）。

## 局限与后续工作

- **局限 1**：动态范围与累加器精度限制可探测的 n 与 dtype；FP8 等需 ModifiedFPRev，大 n 需子树压缩（Section 8.1）。
- **局限 2**：不覆盖随机化、值相关累加顺序；order-independent 高效算法仍非本工具目标。
- **局限 3**：BLAS 后端跨平台不可复现是实证结论，但论文未提供自动「修复」或 wrapper，仅提供 spec 供手工复现。
- **Future work 1**：扩展探测 [[Tensor-Core]] 的 rounding mode、累加器位宽、block FMA 行为（作者提议用 2ⁿ+1.75-2ⁿ 类实验）。
- **Future work 2**：支持 microscaling block 内顺序 + block 级 tree 的两层构造（Section 8.2）。
- **Future work 3**：随机化 pivot 选择以降低 FPRev 期望复杂度；应用于 AllReduce 等 collective 的预定顺序（若满足确定性假设）。

## 相关

- **相关概念**：[[Floating-Point]]、[[Reproducibility]]、[[Tensor-Core]]、[[Quantization]]
- **同类系统/库**：[[NumPy]]、[[PyTorch]]、[[BLAS]]、[[cuBLAS]]、[[Intel MKL]]、[[OpenBLAS]]
- **同会议**：[[ATC-2025]]
- **对比**：与 Varity（随机等价性测试）、pLiner（差分定位非复现代码）互补——FPRev 产出可执行的顺序 spec 而非仅 pass/fail
