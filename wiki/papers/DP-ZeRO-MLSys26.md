---
type: paper
name: DP-ZeRO
full_title: "Zero Redundancy Distributed Learning with Differential Privacy"
authors: [Zhiqi Bu, Ruixuan Liu, Justin Chiu, Sheng Zha, George Karypis]
venue: MLSys
year: 2026
tags: [differential-privacy, zero, distributed-training, mixed-precision, large-models]
source_pdf: "[[da4fb5c6e93e74d3df8527599fa62642.pdf]]"
source_md: "[[da4fb5c6e93e74d3df8527599fa62642]]"
---

# Zero Redundancy Distributed Learning with Differential Privacy (MLSys 2026)

> **一句话总结**：DP-ZeRO 把 Book-Keeping per-sample gradient clipping 算法嫁接进 DeepSpeed/FSDP 的 ZeRO-1/2/3 + fp16 mixed-precision 流水，首次让 DP 训练做到 GPT-100B、ViT-10B 规模，速度与内存几乎匹配非 DP ZeRO。

## 问题

Differentially-Private (DP) 深度学习需要 per-sample gradient clipping + noising，在单卡上 Book-Keeping (BK) 算法已做到 1.03-1.08× 标准训练开销。但上到多卡：

- **DDP**：要缓存 per-sample gradient，内存爆炸，还比非 DP 慢 2-9×；且装不下 > 单卡模型。
- **Pipeline Parallel (GPipe)**：He et al. 把 DP 接 PP 做 GPT3-175B 微调 0.1% 参数，但 pipeline bubble 浪费 GPU。
- **ZeRO / mixed-precision**：标准 LLM 训练的 SOTA，但与 DP 从未成功组合过——per-sample clip 需要完整的 per-sample gradient，而 ZeRO 把 optimizer state/gradient/parameter 都分片了，loss scaling 在 DP 下也非 trivial。

## 核心方法

DP-ZeRO 把 DP 数学与 ZeRO 系统解耦，仅改 back-propagation 阶段：

1. **BK-based DP 后向**：利用 mixed ghost norm（per-sample gradient norm 几乎免费）+ book-keeping trick（单次完整 BP，不做两次）；只在 back-prop 阶段注入 per-sample clip `C_i` 和 Gaussian noise。
2. **数学分区 vs 硬件分区解耦**：DP 的 `M` 组参数分区（all-layer / layer-wise clipping）在数学上决定精度，ZeRO 的 `N_d` 卡数分区决定硬件；二者可正交（Figure 2 区分）。
3. **Mixed-precision DP**：正确处理 fp16 下的 loss scaling，使 DP 也能享受 ≈50% 内存节省和 ≈20% 通信加速。
4. **与 ZeRO-1/2/3 完全兼容**：ZeRO-1 分 optimizer state、ZeRO-2 加分 gradient、ZeRO-3 加分 parameter，内存降到 $16\Psi/N_d$ 级，DP 版本保持相同 scaling。
5. **泛化到通用层类型**（linear、conv、embedding、normalization），可插 DeepSpeed 或 PyTorch FSDP，一行代码切换。

## 关键结果

- 首次训练 GPT-100B、ViT-10B、ViT-Gigantic、GPT2-XL **全参数** DP 训练（而非只调 0.1%）。
- 速度与内存接近标准 ZeRO：DP 占主要开销的 back-prop 在 BK 下只比标准贵一点，forward 和 communication 开销完全一致。
- 多节点场景（inter-node 3-24× 慢于 intra-node）下 DP-ZeRO 因通信开销相对占比变高，与 ZeRO 速度差距更小。
- Codebase 将开源，支持 classification / NLU 等通用任务。

## 相关

- **相关概念**：Differential Privacy、Per-sample Gradient Clipping、ZeRO、Mixed-Precision Training、Ghost Clipping、Book-Keeping
- **同类系统**：Opacus、TensorFlow-Privacy、GhostClip、DeepSpeed、FSDP
- **同会议**：[[MLSys-2026]]
