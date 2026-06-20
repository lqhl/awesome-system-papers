---
type: paper
name: FlashAttention-4
full_title: "FlashAttention-4: Algorithm and Kernel Pipelining Co-Design for Asymmetric Hardware Scaling"
authors: [Ted Zadouri, Markus Hoehnerbach, Jay Shah, Timmy Liu, Vijay Thakkar, Tri Dao]
venue: MLSys
year: 2026
tags: [attention, blackwell, gpu-kernel, flash-attention, cute-dsl]
source_pdf: "[[72b32a1f754ba1c09b3695e0cb6cde7f.pdf]]"
source_md: "[[72b32a1f754ba1c09b3695e0cb6cde7f]]"
---

# FlashAttention-4: Algorithm and Kernel Pipelining Co-Design for Asymmetric Hardware Scaling (MLSys 2026)

> **一句话总结**：Blackwell B200 上 tensor core 吞吐翻倍（2.25 PFLOPS）但 SMEM/MUFU 不变，roofline 显示 SMEM traffic 与 exponential 可超 MMA 25–60%；FA-4 用 TMEM 全异步 MMA pipeline、FMA 多项式部分模拟 exp、conditional [[Online-Softmax|online softmax]] rescaling 与 2-CTA backward 减半 dQ atomic，BF16 最高 **1613 TFLOPs/s**（**71%** 峰值），比 cuDNN 9.13 快 **1.3×**、Triton 快 **2.7×**，CuTe-DSL 编译快 **20–30×**。

## 问题与动机

[[FlashAttention-NeurIPS22|FlashAttention]] → [[FlashAttention-2-ICLR24|FA2]] → [[FlashAttention-3-NeurIPS24|FA3]] 把 exact [[Attention]] 从 HBM IO 瓶颈逐步推向接近 GEMM 的 GPU kernel 效率：tiling + online softmax、沿 sequence 并行、Hopper 上 TMA/WGMMA warp specialization 与 FP8。但 FA3 主要面向 **Hopper H100**；AI 算力已快速迁移到 **Blackwell B200/GB200** datacenter GPU，硬件演进呈现 **asymmetric scaling**——BF16 tensor core 峰值从 1 PFLOPS 升到 2.25 PFLOPS（约 **2×**），而 shared memory 读带宽（128 B/cycle/SM）、MUFU exponential 吞吐（16 ops/cycle/SM）基本不变。

作者的核心诊断是：在 Blackwell 上，attention 的瓶颈已从「matmul 不够快」转向 **non-matmul 资源**——SMEM operand 重复读取与 softmax 的 `exp` 在 roofline 上可占 **25–60%** 多于 MMA compute。同时 Blackwell 引入 TMEM（每 SM 256 KB，MMA 异步写 accumulator）、**128×128** MMA tile（Hopper 为 64×128）、**2-CTA MMA**（CTA pair 协作、各 stage 一半 operand B），简单 port FA3 既吃不满新硬件，也可能因 Hopper MMA 指令缺乏前向兼容而无法运行。

FA4 的定位是：**算法与 kernel pipeline 协同设计**，显式识别并缓解 SMEM traffic、exponential、atomic reduction 等非 matmul 瓶颈；同时用 **CuTe-DSL（Python embedded）** 全栈实现，降低 C++ template 编译成本。这与 SageAttention 系列（INT8/FP4 量化、偏 consumer GPU）不同——FA4 坚持 **exact BF16/FP16 dense attention**，面向 datacenter training/prefill 场景，并与 cuDNN 9.13+ 形成竞合关系（论文称已与 cuDNN 团队合入部分技术）。

## 关键观察 / 隐含假设

- **观察 1：Blackwell 上 attention forward 的 cycle 预算中，SMEM 读与 exponential 可与 MMA 同级甚至更高，而非 matmul 独占。** Roofline（§3.1.1）在 `M=N=d=128` 时 MMA/exp 各约 1024 cycles、SMEM 768 cycles；`M=256, N=d=128` 时 SMEM 升至 1536 cycles，MMA/exp 各 2048 cycles。B200 tensor core 8192 ops/cycle/SM vs MUFU 16 ops/cycle/SM，差距约 **512×**，softmax 中大量 `exp` 使 exponential unit 成为与 MMA 并列的瓶颈。
  - **依赖假设**：workload 为 training 或长序列 prefill，Q/K/V 以 BF16 在 SMEM/TMEM 间 block-wise 流动，head dim 64–192、seq len ≥4k 时 tile 足够大使 roofline 简化模型成立。
  - **可能失效场景**：decode（query 极短）时并行度不足，kernel 退化为 memory/latency-bound；B300/GB300 已将 MUFU 翻倍至 32 ops/cycle，exp 瓶颈权重会下降，FMA 模拟 exp 的收益需重测。

- **观察 2：Blackwell MMA 异步写 TMEM（而非 register），使 softmax 与 matmul 的 overlap 调度空间大于 FA3，但 register pressure 从 accumulator 转向「整行 128 元素 softmax 状态」。** 每 Q tile 128 token，两个 softmax warpgroup 各处理整行，消除 Hopper 上 inter-warp shuffle 降 row max；P 经 TMEM 传递可把 rescale 移到独立 correction warpgroup，移出 exponential critical path。
  - **依赖假设**：TMEM 分区（S/P 共享、两 tile S 与 P overlap）在 head dim 128 下可行；BF16 下每 thread 需 ~128 input + 64 output register，四 warpgroup（2 softmax + 1 correction + 1 MMA/TMA）不 spill。
  - **可能失效场景**：更大 head dim（如 256）或更小 tile 破坏 TMEM 分区假设；partial exp emulation 增加 register bandwidth，若 emulation 比例过高会 spill 抵消收益（论文因此只 emulate 10–25% 元素）。

- **观察 3：Backward pass 在 `M=N=d=128` 下 SMEM traffic（3328 cycles）比 MMA（2560）高约 **30%**，比 exponential（1024）更主导；2-CTA MMA 可减半 operand B 的 SMEM stage，并通过 DSMEM 交换 dS 使 dQ MMA 的 reduction 维自然 split，从而 halve global atomic adds。**
  - **依赖假设**：CTA 以 pair 启动、cluster 内 DSMEM 延迟可隐藏；dQ 沿 KV 外循环的 atomic reduction 是 backward 非确定性与性能热点。
  - **可能失效场景**：GQA 下 dK/dV 也有 inter-CTA reduction；deterministic mode 需 semaphore lock，负载不均时 stall 严重（论文用 SPT/LPT + head/batch swizzle 缓解，但仍可达 nondeterministic 1-CTA 的约 **75%** 吞吐）。

- **假设 1：benchmark 以单卡 B200、固定总 token 32k、BF16、MHA/MQA/GQA 与 DeepSeek V3 式 (192,128) head 为主，microbenchmark TFLOPs/s 可代表 datacenter LLM training attention 层效率。**
  - **证据强度**：中强——覆盖 seq 1k–32k、causal/non-causal、forward/backward、deterministic ablation，baseline 含 PyTorch、FA2、Triton、Gluon、cuDNN 9.13；弱——无端到端 training、无 multi-GPU、无 decode serving trace。

- **假设 2：exact dense attention 仍是长 context 主力 primitive；低精度 attention（SageAttention FP4 等）与 FA4 服务不同部署点（accuracy vs peak TFLOPs）。**
  - **证据强度**：中。论文承认量化路线在 consumer Blackwell 上有效，但强调 datacenter 仍以 BF16 exact 为主；未与 SageAttention3 等同卡对比。

## 核心方法

FA4 在 [[FlashAttention-2-ICLR24|FA2]]/[[FlashAttention-3-NeurIPS24|FA3]] 的 block-wise exact [[Attention]] 骨架上，针对 Blackwell asymmetric scaling 做四层 co-design：

**1. Forward pipeline：TMEM 异步 MMA + ping-pong softmax（回应观察 1–2）**

延续 FA3 双 tile ping-pong：一 tile 跑 MMA 时另一 tile 做 softmax。Blackwell 差异在于 accumulator 在 TMEM、tile 为 128×128，两个 softmax warpgroup（各 128 thread）各持整行，显式 `bar.sync` 避免 exponential critical section 重叠。P 写入 TMEM 后由 **correction warpgroup** 异步做 output rescale，把 `e^{m_{j-1}-m_j} O_{j-1}` 移出 softmax 热路径。TMEM 分区选「两 tile S 与 P overlap」，以便 pipeline 启动时立即算两个 S tile，并留空间传递 rescale 统计量。为减 register pressure，P 的前 3/4 一次存储并触发 MMA，最后 1/4 分存。

**2. Exponential 瓶颈缓解：FMA 软件模拟 + conditional rescaling（回应观察 1）**

- **Partial exp emulation**：用 Cody-Waite range reduction + Horner FMA 多项式（degree-3）算 `2^x`；整数部分用 IEEE754 exponent 位操作。仅 **10–25%** 元素走 FMA，其余仍用 MUFU.EX2，避免全量 emulation 的 register spill。Table 2：degree-3 在 BF16 上与 hardware 在 99% 输入上差 ≤1 ULP，因 BF16 量化误差主导。
- **Conditional online softmax rescaling**：继承 [[Online-Softmax|online softmax]] 的 running max `m` 与 normalizer `ℓ`；仅当 `m_j - m_{j-1} > τ`（默认 `τ=log2(256)=8`）才做中间 rescale，最终用真实 `m_final`、`ℓ_final` 校正。为减 warp divergence，任一 thread 需 rescale 则整 warp rescale。显著减少非 matmul vector mul。

**3. Backward：TMEM 调度 + 2-CTA MMA + DSMEM（回应观察 3）**

Backward 共 5 个 MMA（重算 S、dP、dV、dQ、dK）。FA3 因 register 限制几乎串行 compute graph；FA4 用 TMEM 存最多 4 个 128×128 accumulator tile，S/P 共享一块，dP/dS/dQ 共享另一块，使 **dQ/dK MMA 与上一 iteration 的 softmax** overlap。2-CTA 模式下 `M=256, N=K=128`，每 CTA 只 stage 一半 B，SMEM traffic 约减半；dQ 步通过 **DSMEM** 交换半块 dS，每 CTA 形成 `(M/2 × 2N)` operand，accumulate `(M/2, d)`，**global atomic 次数减半**。Pipeline 重排：当前 tile 先算 dP，再与上一 tile 的 dQ MMA 并行算当前 dS elementwise。

**4. Scheduling 与实现框架**

- **LPT（longest-processing-time-first）**：causal mask 下 mblock 逆序 + head section swizzle（控制 L2 KV 容量）；varlen 用预处理 kernel 按 worktile 执行时间排序 batch。在 H200 上验证对 FA3 亦有效（MHA **4–8%**、MQA **7–14%** FLOPs 增益）。Deterministic backward 额外用 **SPT**（shortest-processing-time-first）排 dQ reduction 顺序。
- **CuTe-DSL**：全 kernel Python 编写，JIT 到 PTX→SASS；单 kernel 编译比 FA3 C++ template 快 **20–30×**（Table 4）。暴露 block-sparse、mask、varlen、scheduling 为可组合 primitive，FlexAttention / block-sparse 变体可在其上扩展而无需改核心框架。

## 设计取舍

- **Partial vs full exp emulation**：全量 FMA 模拟可提高 exp 吞吐，但 register 与 latency 成本可能 spill；论文选择 10–25% 经验比例，在 MMA/exp roofline 交点取平衡。

- **Conditional rescaling 阈值 τ**：更大 τ 减少 rescale 次数但增大中间数值 slack，依赖最终 normalization 校正；`τ=8` 对应最大 256× 中间 scale 误差，对 BF16 attention 可接受，但未给出训练 loss 敏感性实验。

- **1-CTA vs 2-CTA backward**：2-CTA 减 SMEM 与 atomic，但要求 CTA pair 固定启动、DSMEM 同步、dQ tile shape 特殊（`M=128, 2N=256`），实现与调度复杂度显著高于 1-CTA；负载不均时 deterministic lock 开销更大。

- **Deterministic vs nondeterministic backward**：RL 等需可复现梯度时启用 semaphore 串行化 dQ（及 GQA 下 dK/dV）归约；SPT/LPT/swizzle 把性能损失压到 nondeterministic 1-CTA 的约 **75%**，但仍非免费午餐。

- **CuTe-DSL vs CUTLASS C++**：编译与原型速度大幅提升，但依赖 NVIDIA 生态与 CuTe-DSL 成熟度；部分操作用 custom PTX escape hatch，长期 API 稳定性由框架演进决定。

- **边界条件**：中长序列（≥4k）、head dim 64/128/(192,128)、B200/GB200 datacenter GPU 收益最大；短序列、decode、consumer Blackwell（不同 SFU 比例）、非 NVIDIA 硬件需重新 roofline 与 pipeline 设计。

## 实验与结果

- **Forward BF16（B200）**：最高 **1613 TFLOPs/s**（约 **71%** 理论峰值）；相对 cuDNN 9.13 **1.1–1.3×**、Triton **2.1–2.7×**；causal 增益更大（LPT scheduler）。DeepSeek V3 式 head (192,128) causal 上 FA4 仍领先 cuDNN。
- **Backward BF16**：长序列上 consistently 超过 baseline；2-CTA 相对 1-CTA 体现 SMEM/atomic 优化。Roofline：`M=N=d=128` 时 SMEM **3328** cycles > MMA **2560** > exp **1024**。
- **Deterministic backward ablation**：SPT + LPT + reverse mblock + batch/head swizzle 最优；相对 naive 顺序显著提升，达 nondeterministic 1-CTA 约 **75%** 吞吐。
- **编译时间**：单 kernel FA4 CuTe-DSL 比 FA3 C++ template 快 **20–30×**（FA2/FA3 常需预编译数百 variant）。
- **Benchmark 设定**：B100 180GB SXM6（附录 A.1 写明；主文图表标 B200）、CUDA 13.1、FA2 2.8.3、Triton 3.6、PyTorch 2.10、CuTe-DSL 4.4.1；seq 1k–32k，总 token 32k，hidden 2048，warmup 5 + repeat 10 取平均。代码开源（flash-attention 仓库 `flash_attn/cute`）。

## Critical Analysis

### 论证链条

论文链条大体闭合：**测量** Blackwell asymmetric scaling 使 non-matmul 资源成为 attention 瓶颈 → **归因** roofline 量化 SMEM/exp 可超 MMA 25–60% → **设计** TMEM async pipeline、partial exp emulation、conditional rescaling（forward）与 2-CTA+DSMEM（backward）逐一对应瓶颈 → **结果** 71% 峰值利用率、1.3× cuDNN / 2.7× Triton。

最强环节是 **hardware trend → roofline → mechanism** 的一一映射：tensor core 翻倍而 SMEM/MUFU 不变，直接支撑「不能只 port FA3」；TMEM 异步写直接支撑 correction warpgroup 与更大 tile；backward SMEM 主导直接支撑 2-CTA。Forward/backward 分设 roofline（Table 1/3）并配图 1–3 说明 pipeline，比纯「换更大 tile」更有说服力。

薄弱环节是 **从 microbenchmark 到 production training/inference**。论文没有端到端 LLM step time、loss 曲线或真实 trace；cuDNN 9.14+ 已吸收 FA4 多项技术（作者自述），**1.3× over cuDNN 9.13** 的领先幅度可能随 vendor library 迭代缩小（Figure 4 脚注已提示）。把「attention primitive 达 71% 峰值」外推为「Blackwell 部署全面解锁长 context」仍缺一步。

### 假设压力测试

**硬件代际**：结论绑定 Blackwell（TMEM、128×128 async MMA、2-CTA、DSMEM）。Hopper 无法直接运行部分指令；B300/GB300 MUFU 翻倍会改变 exp emulation 是否划算。AMD/TPU 上 asymmetric scaling 形态不同，co-design 需重做。

**Workload**：固定总 token 32k 的 synthetic grid 利于 TFLOPs 对比，但与 **[[Continuous-Batching]]** 下混合 prefill/decode、**[[KV-Cache]]** 增长、**[[PagedAttention]]** 非连续 KV 布局的生产 serving 分布不同。论文主文优化 training/prefill；decode memory-bound 场景未系统评估。

**数值正确性**：conditional rescaling 与 partial exp emulation 在 BF16 ULP 层面与 hardware 接近，但 **大规模 training 收敛、RL 确定性 backward 的梯度误差累积** 未报告。Deterministic mode 的 lock 顺序对数值无影响，但对 wall-clock 敏感。

**竞争格局**：cuDNN 为闭源且与作者合作合入技术；Triton/Gluon baseline 是否用到最新 B200 指令、cuDNN 版本差异（9.13 vs 9.19）使「FA4 最快」的 claim 带时间戳。SageAttention3 等 FP4 路线在另一 accuracy–speed 前沿，论文未同卡对比。

### 实验可信度

**优点**：forward/backward、causal/non-causal、多种 head dim（含 DeepSeek V3 配置）、deterministic ablation、与 FA2/Triton/Gluon/cuDNN/PyTorch 对比；roofline 与 pipeline 图支持机制解释；开源 + CuTe-DSL 降低复现门槛。

**不足**：
- 主文标 B200、附录 A.1 写 B100 180GB，硬件表述不一致，外部复核需注意。
- 无 error bar 或方差报告。
- 无端到端 training/inference、无 multi-GPU attention（如 ring attention）实验。
- cuDNN 快速追平后，相对优势可能主要体现在「开源可定制 + 更快编译」而非 raw TFLOPs。
- Inference decode、[[Disaggregation]]、与 [[vLLM]]/[[SGLang]] 集成成本论文未讨论。

### 系统性缺陷

- **Serving SLO**：未评估 TTFT/ITL/tail latency、动态 batching 下 occupancy；LPT/varlen 预处理有成本，在生产 metadata 路径上是否摊销未测。
- **可维护性**：深度绑定 Blackwell PTX/CuTe-DSL；NVIDIA 驱动、CuTe-DSL 版本、compiler 行为变化可能影响 pipeline overlap（FA3 已有 compiler 不配合先例）。
- **资源隔离与多 tenant**：单 kernel 性能为主，未讨论 SM 共享、功耗封顶、多 job 并存时的有效吞吐。
- **运维**：与 PyTorch/[[Flash-Attention]] 生态集成在推进中；deterministic backward 的 semaphore 与 GQA 路径增加调试面。
- **正确性边界**：支持 MQA/GQA、causal、varlen、deterministic；更复杂变体（sliding window、attention sink、FP8/FP4）主文未覆盖。

## 局限与 Future Work

- **局限 1**：优化目标为 **Blackwell datacenter training/prefill**；decode、[[PagedAttention]]、split-KV 等 inference 路径非主文重点，FA3 appendix 式 inference 讨论在 FA4 中未同等展开。
- **局限 2**：**cuDNN 合入 FA4 技术**后，闭源库与开源实现性能差距缩小；论文优势更多体现在开发效率（CuTe-DSL）与可组合 primitive，而非持久 TFLOPs 垄断。
- **局限 3**：实验以 **attention microbenchmark** 为主，缺少端到端 training 吞吐、loss、真实 activation 分布下的数值稳定性验证。
- **局限 4**：roofline 简化模型忽略 L2、register bandwidth、FP math 等，极端 tile/head dim 下瓶颈可能转移；B300/GB300 硬件未测。
- **局限 5**：conditional rescaling 与 partial exp emulation 的 **训练语义影响**（尤其 FP32 master weight、混合精度 policy）未评估。

- **Future work 1**：在 **B300/GB300**（MUFU 翻倍）与 consumer Blackwell 上重跑 roofline，测量 exp emulation 比例是否仍最优，或应回退纯 MUFU/新指令。
- **Future work 2**：构建 **decode + varlen + paged KV** benchmark，用 TTFT/ITL 与 effective throughput 替代 TFLOPs/s，评估 LPT 预处理与 2-CTA backward 在 serving 栈中的净收益。
- **Future work 3**：系统测量 **deterministic backward + conditional rescaling** 在大规模 RL/LLM training 中的梯度误差与收敛，对比 nondeterministic FA4 与 FA3。
- **Future work 4**：对 **tile shape × 2-CTA × exp emulation 比例 × τ** 做 autotuning，减少手工 roofline 调参；并评估 CuTe-DSL 编译缓存对 CI/多 variant 部署的影响。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、[[Online-Softmax]]、[[KV-Cache]]、[[Quantization]]
- **前序 / 演进**：[[FlashAttention-NeurIPS22|FlashAttention]]、[[FlashAttention-2-ICLR24|FlashAttention-2]]、[[FlashAttention-3-NeurIPS24|FlashAttention-3]]
- **同类系统 / 组件**：cuDNN 9、CUTLASS/CuTe-DSL、Triton、Gluon、FlexAttention
- **Serving 生态**：[[vLLM]]、[[SGLang]]、[[PagedAttention]]、[[Continuous-Batching]]
- **同会议**：[[MLSys-2026]]
- **同主题**：[[Foundation]]、[[AI-Infra]]
- **对比**：[[FlashAttention-3-NeurIPS24|FA3]]（Hopper 异步 + FP8）→ **FA4**（Blackwell asymmetric scaling + TMEM/2-CTA + CuTe-DSL） vs SageAttention 系列（低精度量化路线）