---
type: paper
name: IntAttention
full_title: "IntAttention: A Fully Integer Attention Pipeline for Efficient Edge Inference"
authors: [Wanli Zhong, Haibo Feng, Zirui Zhou, Hanyang Peng, Shiqi Yu]
venue: MLSys
year: 2026
tags: [quantization, attention, edge-inference, softmax, arm, int8]
source_pdf: "[[c20ad4d76fe97759aa27a0c99bff6710.pdf]]"
source_md: "[[c20ad4d76fe97759aa27a0c99bff6710]]"
---

# IntAttention: A Fully Integer Attention Pipeline for Efficient Edge Inference (MLSys 2026)

> **一句话总结**：INT8 GEMM 加速后，dequantize→softmax→requantize 占 attention 延迟 **57–65%**；IntAttention 用 IndexSoftmax（整数裁剪 + **32** 项 UINT8 LUT + 整数归一化）打通 QK→P(UINT8)→PV 全整数路径，**无需重训练** plug-in；Armv8 上较 FP16 最高 **3.7×** 加速、**61%** 能耗降，精度接近 baseline。

## 问题与动机

边缘设备偏好 INT8 矩阵乘，但标准 attention 在 INT32 logits 后必须浮点 softmax，再量化 P 给 PV——**混合精度**打断数据流。Fig. 2：FP32 时 softmax 路径占 **13–19%**；INT8 GEMM 后升至 **57–65%**，成为主导瓶颈。

GPU 方向（FlashAttention-3、TurboAttention）依赖 warp 专精与 FP8，不适用于 commodity Arm NEON 等整数单元。目标：**全整数执行、即插即用、无 QAT、便携高效**。

## 关键观察 / 隐含假设

- **观察 1：softmax 输入经 row-wise max-subtraction 后，绝大多数 logits 落在近零 exp 区，整数域 clip 可跳过无效 exp 计算。**
  - **依赖假设**：固定离线选 clip 阈值 c（默认 **6.6**），无需 per-tensor 动态统计（对比 EXAQ）。
  - **可能失效场景**：极尖峰 attention（少量 head 超长尾）clip 可能改 mass 分布。

- **观察 2：有界区间 \([0,c]\) 上 exp 可用 **\(2^b\)** 项 UINT8 LUT（b=5→32 项）替代，LUT 与输出 P 均 UINT8，同内存预算比 EXAQ INT2/3 分辨率 **4×**。**
  - **证据强度**：**中高**——语言/视觉 benchmark 平均优于 EXAQ INT3 约 **1.4%**。

- **观察 3：P 用 UINT8×255 而非 INT8×127，更好保留小概率质量，对 PV 聚合 fidelity 关键。**
  - **可能失效场景**：极低温度或尖锐分布时 8-bit P 仍有限。

- **假设 1：per-tensor 对称 INT8 量化 Q/K/V 足以与 IndexSoftmax 耦合；超参 (b,c) 在 broad plateau 鲁棒。**
  - **可能失效场景**：Qwen3 等对 attention 量化更敏感（论文承认 perplexity gap 较大但仍改善）。

## 核心方法

**流水线**：动态 INT8 Q,K,V → INT32 \( \hat Q \hat K^\top \) → **IndexSoftmax** → UINT8 \(\hat P\) → INT8 PV GEMM → 反量化输出。

**IndexSoftmax**：
1. 整数 max-subtraction + sparsity-aware clip（式 7–9）。
2. LUT gather 近似 \(\exp\)（式 10–12）。
3. 整数 scale normalization（32-bit 累加 + 逐元素 scale），无浮点除法路径。

与 I-BERT/I-ViT/I-LLM 等不同：**无 QAT、无迭代整数 refinements、无 per-step 全局统计**。

## 设计取舍

- **近似 softmax vs 精确**：换 **3.7×** 速度与 **61%** 能耗，多数任务 perplexity/accuracy 与 Quantized-Only 持平或略优。
- **固定 (b,c) vs 动态 clip**：降 edge CPU 上 global reduction 开销，牺牲极端分布自适应。
- **UINT8 P vs INT8 P**：signed 浪费动态范围，Table 5 显示 cosine/L1 明显变差。
- **优化重心转移**：IndexSoftmax 后 softmax 仅占 **14–22%**，瓶颈回到 QK/PV GEMM——论文诚实指出下一步在 matmul kernel。

## 实验与结果

**平台**：RK3588S2、Apple M2（Armv8）。

**速度**：IntAttention vs FP16 **2.1–3.7×**（RK3588）；vs Quantized-Only **1.6–2.0×**。M2 上 vs FP16 **2.4–2.8×**。

**能耗**（RK3588）：**39.18%** of FP16（**−61%**）；较 Quantized-Only **−37%**。

**精度**：LLaMA/OPT WikiText、Qwen3、DeiT/ViT/CaiT ImageNet——多数 ≥ Quantized-Only baseline；ablation IndexSoftmax vs EXAQ 语言/视觉 Tables 3–4。

**超参**：\(b,c\) 在 \(b≥4, c∈[5.5,7.7]\) 平台稳定；推荐 **(5, 6.6)**。

## Critical Analysis

### 论证链条

观察（INT8 GEMM 加速后，dequantize→softmax→requantize 占 attention 延迟 **57–65%**；GPU 方向依赖 warp 专精与 FP8，不适用于 commodity Arm NEON）→ 设计（IndexSoftmax：整数裁剪 + **32** 项 UINT8 LUT + 整数归一化，打通 QK→P(UINT8)→PV 全整数路径，无需 QAT）→ 结果（Armv8 较 FP16 **2.1–3.7×**、能耗 **−61%**，精度接近 Quantized-Only baseline）链条**闭合良好**。论文精准击中 INT8 attention 的 **softmax 孤岛**问题；IndexSoftmax 后 softmax 仅占 **14–22%**，瓶颈诚实回到 QK/PV GEMM。

主要跳步是把 microbench 加速外推到「边缘 LLM 端到端可部署」。仍是近似 attention，无训练时校准；固定离线 clip 阈值 \(c=6.6\) 与 \((b,c)=(5,6.6)\) 在 broad plateau 鲁棒，但极尖峰 attention 或 Qwen3 等对 attention 量化更敏感模型仍有 perplexity gap（论文承认但仍改善）。与 TurboAttention/EXAQ 同属 LUT softmax，但 IntAttention 强调 **归一化也整数化** 与 **无 per-step 全局统计**，更偏 edge scalar core 而非 datacenter GPU——定位清晰，却也意味着不直接解决 datacenter serving 路径。

### 假设压力测试

- **分布假设**：row-wise max-subtraction 后绝大多数 logits 落在近零 exp 区，固定 clip \(c\) 可跳过无效 exp；极尖峰 attention（少量 head 超长尾）可能改 mass 分布。
- **量化耦合**：per-tensor 对称 INT8 量化 Q/K/V 足以与 IndexSoftmax 耦合；per-channel/block 量化未探索——可能是进一步精度或速度的空间。
- **P 表示**：UINT8×255 优于 INT8×127 保留小概率质量；极低温度或尖锐分布时 8-bit \(\hat P\) 仍有限。
- **融合路径**：未与 [[FlashAttention]] 式 tiling/fusion 结合；IndexSoftmax 后瓶颈回到 matmul kernel，下一步优化重心在 GEMM 而非 softmax。
- **长上下文 decode**：评测以中等序列长度 attention microbench 为主，长 context [[LLM]] decode 路径、与 [[KV-Cache]] 量化集成未覆盖。

### 实验可信度

- **强项**：RK3588S2、Apple M2 双平台；速度、能耗、WikiText perplexity、ImageNet accuracy 与 Quantized-Only baseline 对照完整；ablation IndexSoftmax vs EXAQ 语言/视觉 Tables 3–4 支持 UINT8 LUT + 整数归一化设计；超参 \(b,c\) 平台 \((b≥4, c∈[5.5,7.7])\) 稳定性有扫描。
- **Baseline 选取**：FP16 与 Quantized-Only（INT8 GEMM + 浮点 softmax）是公平对照，直接隔离 softmax 孤岛贡献；plug-and-play、无 QAT 的部署叙事与实验设置一致。
- **Metric 缺口**：代码「later version」发布，复现性待定；无端到端长 context LLM generation latency/quality；未与 SageAttention/TurboAttention 在相同 edge SoC 上 head-to-head。正确性方面，近似 attention 对下游任务（代码、推理链）的系统性偏差未测，仅 perplexity/accuracy 代理。

## 局限与 Future Work

- 更强 INT8/INT4 GEMM 与 IntAttention 协同。
- per-channel/block 量化与 group-specific clip。
- 与 speculative decoding、[[KV-Cache]] 量化集成。
- 开源实现与更多 LLM 规模端到端评测。

## 相关

- **量化 attention**：SageAttention、TurboAttention、EXAQ、I-BERT
- **硬件**：Arm NEON、edge inference
- **概念**：softmax、INT8 quantization、plug-and-play inference