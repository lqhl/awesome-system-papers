---
type: paper
name: FlashAttention-2
full_title: "FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning"
authors: [Tri Dao]
venue: ICLR
year: 2024
tags: [attention, gpu-kernel, transformer, long-context, llm-training]
source_pdf: "[[iclr24-dao-flashattention2.pdf]]"
source_md: "[[iclr24-dao-flashattention2]]"
---

# FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning (ICLR 2024)

> **一句话总结**：在 [[FlashAttention-NeurIPS22|FlashAttention]] 已把 attention 变成 IO-aware exact kernel 的前提下，FA2 通过 profiling 发现瓶颈已从 HBM IO 转向 **GPU work partitioning**——长序列下 batch×head 并行不足、warp 内 split-K 带来 shared memory 通信；据此减少非 matmul FLOPs、沿 sequence length 增加 thread-block 并行、warp 内改为 split-Q，在 A100 上相对 FA1 约 **2×**，attention forward 最高 **230 TFLOPs/s（73% 峰值）**，GPT-style 训练最高 **225 TFLOPs/s/GPU（72% MFU）**。

## 问题与动机

长 context [[Transformer]] 训练与推理的核心瓶颈仍是 [[Attention]]：标准实现物化 `N×N` 的 `S=QK^T` 与 `P=softmax(S)`，显存与 HBM 访问均为 `O(N^2)`。[[FlashAttention-NeurIPS22|FlashAttention]] 用 tiling + [[Online-Softmax|online softmax]] + backward recomputation 把中间态留在 SRAM，实现 exact attention 的 2–4× wall-clock 加速与 10–20× 显存节省，已被大规模训练广泛采用。

但 FA1 的 **算力利用率** 仍远低于 optimized GEMM：A100 上 forward 仅 30–50% 理论峰值 TFLOPs/s，backward 仅 25–35%，而 GEMM 可达 80–90%。随着 context 从 2k 扩到 32k–100k（GPT-4、MPT、Claude 等），attention 虽不再 quadratic 占显存，却仍未「像 GEMM 一样快」。作者 claim：FA1 的主要剩余问题不是算法近似或 IO 模型错误，而是 **thread block / warp 级 work partitioning 次优**——要么 SM occupancy 低，要么 shared memory 读写过多。

FA2 的定位是：在保持 exact attention 语义、不引入 sparse/linear 近似的前提下，把 FA1 的 kernel 实现推到更接近 GEMM 的效率曲线，尤其服务 **长序列 + 小 batch** 这一 emerging workload。

## 关键观察 / 隐含假设

- **观察 1（瓶颈迁移）**：FA1 的 forward/backward 在 A100 上分别只达 30–50% / 25–35% 理论峰值，而 GEMM 可达 80–90%；profiling 显示 thread block 与 warp 间分工导致 low occupancy 或多余 shared memory 读写。
  - **依赖假设**：在 FA1 已解决 `O(N^2)` HBM 物化之后，**compute scheduling / on-chip communication** 成为主导瓶颈，而非继续削减 HBM 访问 alone 就能显著提速。
  - **可能失效场景**：极短序列、极大 batch×head 数时 FA1 已能占满 SM，FA2 的 sequence-parallel 收益变小；非 NVIDIA Ampere 架构上 Tensor Core vs non-matmul 吞吐比、shared memory 容量/带宽不同，16× matmul 优势未必成立。

- **观察 2（长 context workload 形状）**：长序列训练往往伴随 **小 batch size 或少量 head**，FA1 仅按 batch×heads 发 thread block（每 block 处理一个 head），总 block 数常 < 80，无法占满 A100 的 108 个 SM。
  - **依赖假设**：目标 deployment 包含「单卡/少卡、长 context、prefill 或训练 step 中 effective batch 不大」的场景，且这些场景值得单独优化。
  - **可能失效场景**：推理 decode 阶段 `seqlen=1`、超大 micro-batch 多卡数据并行时，sequence 维并行几乎无收益；多 query / grouped-query 变体下 head 复用模式改变并行粒度。

- **观察 3（非 matmul 的隐性代价）**：A100 FP16/BF16 matmul 理论 312 TFLOPs/s，非 matmul FP32 仅 19.5 TFLOPs/s——每个 non-matmul FLOP 等价于约 **16×** matmul FLOP 的时间成本；online softmax 的 rescale、统计维护虽占总 FLOPs 比例小，却拖慢整体吞吐。
  - **依赖假设**：GPU 上 attention kernel 应尽可能把时间花在 Tensor Core GEMM 上；减少 rescale 次数、只存 logsumexp 等「算法微调」在 wall-clock 上有可测收益。
  - **证据强度**：**强**——有明确硬件峰值对比与 ablation 支撑的 forward/backward 加速。

- **假设 1（exact attention 仍是主路径）**：大规模训练仍优先标准 dense attention，而非 Longformer / Performer 等近似方案。
  - **证据强度**：**中**——作者以 industry adoption 为动机，但本文实验未与强 approximate baseline 对比 wall-clock。

- **假设 2（手工 block size 调参可接受）**：head dim 64/128 下在 `{64,128}×{64,128}` 四类 tile 手工选择足够，无需 autotuning 即可部署。
  - **证据强度**：**中**——覆盖常见 LLM head dim，但新架构（FA 未出现的 head dim、FP8、变长序列）需重新调参；论文明确将 autotuning 留给 future work。

## 核心方法

FA2 继承 [[Flash-Attention]] 的 IO-aware tiling 与 exact 语义，三重改动均直接对应上述观察：

**1. 算法层减少 non-matmul FLOPs（回应观察 3）**

在 online softmax 更新中维护 **unscaled** 的 partial output `Õ`，仅在每个 Q row block 循环结束时用 `diag(ℓ)^{-1}` 一次性缩放；forward 只保存 **logsumexp `L = m + log(ℓ)`**，backward 亦只需 `L` 而非分别存 row-max 与 exp-sum。数学上与 FA1 等价，但减少中间 rescale 与统计维护，让 Tensor Core GEMM 占比更高。

**2. 沿 sequence length 扩展 thread-block 并行（回应观察 2）**

- **Forward**：外层循环遍历 Q 的 row blocks，各 block 由独立 thread block 处理，与 batch、head 维并行正交；Phil Tillet 的 Triton FA 已验证「外 Q 内 K」循环顺序 + sequence 并行的有效性，FA2 在 CUDA/CUTLASS 路径系统化实现。
- **Backward**：按 **column block** 并行，多 block 更新同一 `dQ` 时用 **atomic add** 合并——这是为 occupancy 付出的代价。
- **Causal mask**：对「列索引全大于行索引」的 block 直接 skip（约一半 block），单 block 内仅对必要位置施 mask；相对无 mask 约 1.7–1.8× 加速。

**3. Warp 内从 split-K 改为 split-Q（回应观察 1）**

FA1 在 thread block 内把 K/V 分给 4/8 个 warp（split-K），各 warp 算 QK 切片后须写 shared memory、同步、归约再乘 V。FA2 改为 **split-Q**：Q 切片 per warp，K/V 全体 warp 可见，每 warp 独立完成 `Q_slice · K^T` 再乘共享 V 切片，**消除 warp 间 shared memory 归约**。Backward 同样避免 split-K，但 Q/K/V/O/dO/dQ/dK/dV 依赖链仍需要部分同步。

**4. MQA / GQA 支持**

对 [[KV-Cache]] 友好的 multi-query / grouped-query attention，通过 head 索引映射复用 K/V，backward 对隐式复制的 head **累加 dK、dV**——与推理侧 KV 共享假设一致。

实现基于 CUTLASS 3.x，block size 按 head dim 与 SM shared memory 手工选取；深度算法与伪代码见 [[iclr24-dao-flashattention2]]。

## 设计取舍

- **取舍 1：occupancy vs backward 原子竞争**：sequence-parallel backward 用 atomic add 更新 `dQ`，提升 SM 利用率，但在高并行度下可能引入 atomic 争用与非确定性累加顺序（浮点下通常可接受，但调试与性能预测更难）。
- **取舍 2：split-Q vs 寄存器/共享内存压力**：消除 warp 通信的同时，每个 warp 需持有 Q 切片，block tile 过大时 register spilling 或 shared memory 超限会直接让 kernel 无法 launch——论文在 64/128 tile 间手动权衡。
- **取舍 3：保持 exact + 单卡 kernel 聚焦**：不合并 sparse/block-sparse 算法变体，不处理多 GPU attention 通信；换取实现清晰与 FA1 生态兼容。
- **边界条件**：在 **长序列、小到中等 batch×head** 时收益最大；短序列或 SM 已饱和时 FA2≈FA1；H100 上未用 TMA/新 Tensor Core 仍有 **335 TFLOPs/s**，说明 FA2 是 **Ampere 架构优化**，Hopper 需 [[FlashAttention-3-NeurIPS24|FlashAttention-3]] 等后续工作。

## 实验与结果

- **Attention microbenchmark（A100 80GB）**：seq 512–16k，固定总 token 16k，hidden 2048，head dim 64/128，有/无 causal mask。FA2 相对 FA1 **1.7–3.0×**，相对 Triton FA forward **1.3–1.5×**、backward **~2×**，相对 PyTorch 标准 attention **3–10×**。
- **硬件利用率**：forward 最高 **230 TFLOPs/s（~73%** A100 理论峰值**）**；backward 最高约 **63%** 峰值；FA1 约 25–40%。
- **端到端训练（8×A100，GPT-style 1.3B/2.7B，2k/8k context）**：相对无 FlashAttention baseline 最高 **2.8×**；相对 FA1 最高 **1.3×**；达 **225 TFLOPs/s/GPU（72% MFU）**。
- **H100（无特殊指令）**：forward+backward 最高 **335 TFLOPs/s**；论文估计 TMA + 4th-gen Tensor Core 可再 **1.5–2×**。
- **Causal mask**：skip 无效 block 带来约 **1.7–1.8×** 相对 dense 计算路径的额外收益（与 FA1 类似，FA2 保留并优化）。

## Critical Analysis

### 论证链条

观察（FA1 利用率低、profiling 指向 partitioning）→ 三处实现改动（non-matmul 削减、sequence 并行、split-Q）→ microbenchmark 与 GPT 训练结果，链条在 **kernel 级** 较闭合：Fig. 4–6 直接展示 FA2 吞吐与 occupancy 改善，Table 1 证明 attention 加速可传导至端到端训练。

薄弱环节在于 **从「attention 更快」到「长 context 训练必然更划算」** 的外推：端到端仅 1.3B/2.7B、8k context、8 卡 A100，未覆盖 70B+、tensor/pipeline parallel、或与 [[Continuous-Batching|continuous batching]] 推理栈的集成收益。论文亦未量化 atomic `dQ`、手工 tile 选型带来的 **尾延迟或性能方差**。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效 |
|------|-----------|----------|
| 长序列 + 小 batch 常见 | GPT-style 8k 训练加速 | Decode `N=1`、超大 batch 预训练 |
| Ampere 上 non-matmul 极贵 | 16× 峰值比 + 算法 tweak | AMD GPU、CPU、非 Tensor Core 路径 |
| Exact dense 优于近似 | 与 FA1/PyTorch 对比 | 极长 seq 下 IO-aware sparse 是否更优未测 |
| 手工 tile 足够 | head 64/128 | 新 head dim、FP8、Blackwell 需重调 |

**推断**：FA2 是 **FA1 的 Ampere 实现续篇**，不是新的 attention 算法；价值在工程上把 exact attention 推到「接近 GEMM」的效率，为 [[FlashAttention-3-NeurIPS24|FA3]]（异步 + FP8）铺路。

### 实验可信度

- **Benchmark 设计较合理**：固定总 token 数扫 seq 长度，分离 causal/head dim，符合长 context prefill 形状；baseline 含 FA1、Triton FA、xformers CUTLASS、PyTorch，覆盖面够强。
- **MFU 计算沿用 Megatron 公式**，attention FLOPs 在 causal 下 arguably 应减半——论文坦诚这一点，使绝对 TFLOPs/s 数字略偏保守或与其他论文不可直接比，但不影响 FA2 vs FA1 相对结论。
- **Ablation 偏少**：三处改动打包交付，缺少「仅 sequence 并行」「仅 split-Q」「仅 softmax tweak」的独立分解，难以量化各因素边际贡献。
- **正确性**：claim exact attention，证明引用 FA1 Theorem 1；无数值误差对比表，但算法等价性论证标准。

### 系统性缺陷

- **多 GPU / 分布式 attention**：论文未讨论 sequence parallel FA2 与 ZeRO、tensor parallel 的交互；长 context 训练常需 context parallelism，FA2 单卡 kernel 优化不自动解决跨卡通信。
- **推理全链路**：未报告 decode 阶段、[[KV-Cache]] paging（如 [[PagedAttention-SOSP23|PagedAttention]]）或 prefill/decode 混合 batch 的延迟分布。
- **可维护性**：依赖 CUTLASS 3.x 与手工 per-head-dim 调参，新硬件需移植；autotuning 未实现，运维上仍是「专家调 kernel」。
- **尾延迟与确定性**：backward atomic add、kernel 变体选择对 p99 的影响 **论文未讨论**。
- **兼容性与生态**：MQA/GQA 已支持，但 FP8、block-sparse、sliding window 等需与 FA3/后续版本叠加。

## 局限与 Future Work

- **局限 1**：优化主要针对 **单 GPU Ampere（A100）**；H100 结果未启用 TMA/WGMMA，利用率仍远低于 GEMM，需硬件特化后续工作（已由 FA3 部分承接）。
- **局限 2**：block size **手工调参**，head dim 或 SMEM 变化时需重新选择，缺乏编译器/autotuner 集成。
- **局限 3**：实验规模限于 **≤2.7B 参数、≤8k 训练 context**，未验证超大规模或 production trace 下的 MFU 与稳定性。
- **Future work 1**：**H100 TMA + 4th-gen Tensor Core + FP8** 的 kernel 特化（可测量：Hopper 上 FA2 vs FA3 利用率曲线）。
- **Future work 2**：**Autotuning block size** 与 compiler（Triton/DSL）协同，减少 per-GPU 手工劳动（可测量：未见 head dim 上的自动选型 vs 手工最优的差距）。
- **Future work 3**：与 **local/dilated/block-sparse attention** 算法层结合，在保持 IO-aware 原则下扩更长 context（可测量：sparse pattern 下的有效 TFLOPs/s 与内存）。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、[[Online-Softmax]]、[[KV-Cache]]、[[Quantization]]
- **前序工作**：[[FlashAttention-NeurIPS22|FlashAttention]]
- **后续工作**：[[FlashAttention-3-NeurIPS24|FlashAttention-3]]、[[FlashAttention-4-MLSys26|FlashAttention-4]]
- **同类系统**：PyTorch SDPA、xformers、Triton attention（论文 baseline，无独立 wiki 页）
- **同主题**：[[Foundation]]、[[AI-Infra]]
- **对比**：[[FlashAttention-NeurIPS22|FlashAttention]]（IO-aware 奠基） vs **FlashAttention-2**（parallelism / partitioning） vs [[FlashAttention-3-NeurIPS24|FlashAttention-3]]（Hopper 异步 + FP8）