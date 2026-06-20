---
type: concept
aliases: [quantization, Quantization, quantized, INT8, FP8, INT4, W8A8, W4A16, PTQ, QAT, post-training quantization, quantization-aware training, mixed-precision]
parent: "[[LLM-Inference]]"
last_updated: 2026-06-20
tags: [model-compression, llm-inference, efficiency]
---

# Quantization

> 用低精度数值表示权重 / activation / KV cache，以大幅降显存并提升算力为目标。FP16→INT8 约 2× 省，INT4 约 4× 省；Hopper / Blackwell tensor core 对 FP8 / MXFP4 有原生支持，算力直接翻倍。核心难点是在精度损失可控前提下，为不同对象（权重 / activation / KV）、不同粒度（per-tensor / per-channel / per-group / per-token）、不同时机（PTQ / QAT）选择方法论。

## 核心思想

按对象分类：weight-only（W8/W4，容易，可离线，GPTQ/AWQ/HQQ）；activation（难，动态分布 outlier，SmoothQuant/LLM.int8()）；KV cache（中等，影响长度/带宽，KIVI/KVQuant）；gradient（训练时难，反向误差累积，FP8 训练）。

按粒度：per-tensor（最粗）→ per-channel（标准）→ per-group（W4 常用，每 128 元素共享 scale）→ per-token（activation 动态 scale）。

按时机：PTQ（训练完再量化，calibration set 估 scale）；QAT（训练中模拟量化误差，精度好但成本高）；mixed-precision training（FP8 权重 + FP16 master copy，Hopper 世代主流）。

典型推理组合：W4A16（INT4 权重、FP16 activation，显存 4×）；W8A8 INT（算力 2×）；FP8 E4M3/E5M2（Hopper/Blackwell 原生）；MXFP4/NVFP4（Blackwell 4-bit 浮点，首个真正好用的 4-bit 训练精度）。

系统视角：dequant kernel 融合（W4A16 matmul 内上投 FP16）；KV cache 量化（更长 context / 更大 batch）；outlier 处理（SmoothQuant 重分配 scale）；per-layer 混合精度调度（[[Hawkeye-MLSys26]]、[[MixLLM-MLSys26]]）。

## 为什么重要

Quantization 是 LLM 推理加速的主路径——在算力与显存双重瓶颈下，低精度直接扩大可服务 batch、可承载 context、可降低$/token。这些论文共同假设：**量化误差不仅来自数值表示本身，还来自 scale 选择策略、硬件 kernel 约束、以及与 serving 栈其他优化（KV 管理、attention kernel、MoE routing）的叠加效应**。

Blackwell 世代把 4-bit 从「实验性」推向生产：[[ScaleSearch-MLSys26]] 证明 max-abs scaling 对 block-wise MSE 可显著次优，搜索邻近 scale 可削减 27% 误差；[[Kitty-MLSys26]] 2-bit KV + channel-wise INT4 近 8× 内存、2.1–4.1× 吞吐。但 [[DriftBench-MLSys26]] 警示 FP16→FP8 等精度迁移会引发 workload-dependent output flip（Math 平均 16.74%），基础设施 drift 是 safety-critical 场景的开放风险。

## 关键观察 / 隐含假设

- **观察 1：max-scaling 对 block-wise MSE 可显著次优，小范围 scale 搜索即可大幅削减误差。** [[ScaleSearch-MLSys26]] 合成高斯 tensor 上穷举 scale 搜索使 MSE 从 0.0990→0.0066（约 25% 相对降幅）；Llama 3.1 8B Key state offset 分布呈双峰结构，支撑「[-2,+6] 邻域搜索」归纳。
- **观察 2：精度迁移的 output flip 高度 workload-dependent，单 workload benchmark 会严重低估风险。** [[DriftBench-MLSys26]] 420 组配置显示 Math 平均 flip 16.74%、Safety 7.97%、Code 仅 0.09%（Math vs Code 186×）；workload 解释方差最大（η²=0.275）。
- **观察 3：FP8 MoE 中 Q/DQ 与轻量 data movement kernel 碎片开销可与 GEMM/通信同量级。** [[FP8FlowMoE-MLSys26]] 尤其在较小 batch 或高 [[Expert-Parallelism]] 时；casting-free + scaling-aware transpose 是消除路径。
- **观察 4：Blackwell attention forward 的 cycle 预算中 SMEM 读与 exponential 可与 MMA 同级，量化 attention 需 hardware-aware pipeline。** [[FlashAttention-4-MLSys26]] roofline 显示 softmax 中大量 `exp` 使 exponential unit 与 MMA 并列瓶颈；[[ScaleSearch-MLSys26]] ScaleSearchAttention 基于模拟框架，simulator-to-hardware gap 待验证。

## 设计空间与取舍

- **路线 1：Weight-only PTQ（GPTQ/AWQ/HQQ）**：离线完成、部署简单；牺牲是 activation 仍 FP16，算力增益有限（W4A16 matmul 需 dequant）。
- **路线 2：W8A8 / FP8 全链路量化**：tensor core 原生 INT8/FP8 matmul，算力 2×；牺牲是 activation outlier 需 SmoothQuant 等预处理，精度敏感层需 skip。
- **路线 3：KV cache 量化（[[Kitty-MLSys26]]、[[ScaleSearch-MLSys26]]、KIVI）**：扩 effective context / batch；牺牲是 attention 需接受量化 K/V，mixed-precision KV 依赖 attention sink 启发式（[[ScaleSearch-MLSys26]] 局限 4）。
- **路线 4：Scale 搜索替代 max-abs（[[ScaleSearch-MLSys26]]）**：NVFP4 block scale 邻域搜索 -27% 误差；牺牲是搜索范围线性增加量化开销，MXFP4 等稀疏 scale 格式收益有限。
- **路线 5：FP8 训练 cast-free 流（[[FP8FlowMoE-MLSys26]]、[[veScale-FSDP-MLSys26]]）**：消除 double quantization error；牺牲是 dense 层/optimizer state 仍高精度，长期收敛待验证。
- **路线 6：per-layer 混合精度自动调度（[[Hawkeye-MLSys26]]、[[OptiKit-MLSys26]]、[[CAGE-MLSys26]]）**：精度与性能 Pareto 搜索；牺牲是 profiling 与部署复杂度。
- **路线 7：端侧 / 特殊场景（[[ExecuTorch-MLSys26]]、[[ZK-APEX-MLSys26]]）**：torch.export 链路 PTQ/QAT、ZK proof 约束；牺牲是 backend delegate 一致性与覆盖率。

## 引用本概念的论文

- [[ScaleSearch-MLSys26|ScaleSearch]] — 搜索 NVFP4 block scale 邻域，量化误差 -27%；ScaleSearchAttention 端到端 FP4 attention+KV
- [[DriftBench-MLSys26|DriftBench]] — FP16→FP8 等精度迁移的 infrastructure drift 与 safety flip 风险
- [[FP8FlowMoE-MLSys26|FP8FlowMoE]] — casting-free FP8 MoE 训练流，scaling-aware transpose 消除 double quantization error
- [[Kitty-MLSys26|Kitty]] — 2-bit KV + channel-wise INT4，内存近 8×、吞吐 2.1–4.1×，精度接近 FP16
- [[MixLLM-MLSys26|MixLLM]]、[[HyperTinyPW-MLSys26|HyperTinyPW]]、[[veScale-FSDP-MLSys26|veScale-FSDP]] — FP8 / 混合精度训练 & 推理
- [[IntAttention-MLSys26|IntAttention]]、[[MAC-Attention-MLSys26|MAC-Attention]]、[[MorphServe-MLSys26|MorphServe]] — 量化 attention / 量化 serving
- [[Hawkeye-MLSys26|Hawkeye]]、[[OptiKit-MLSys26|OptiKit]]、[[CAGE-MLSys26|CAGE]] — 量化调度 / 自动量化
- [[FlashAttention-3-NeurIPS24|FlashAttention-3]]、[[FlashAttention-4-MLSys26|FlashAttention-4]] — FP8 block quantization / Blackwell attention 量化路径
- [[AttributionSparseActivation-MLSys26|AttributionSparseActivation]] — 运行时 neuron-level 稀疏激活与 PTQ 正交，W8A8 收益可叠加
- [[Shannonic-MLSys26|Shannonic]] — 量化后 tensor entropy-optimal 无损压缩，530B state 近 Shannon 极限
- [[ApproxMLIR-MLSys26|ApproxMLIR]] — compound AI 端到端 accuracy knob 含 LLM [[Quantization]] 与 BM25 检索近似
- [[ExecuTorch-MLSys26|ExecuTorch]] — torch.export 链路内 PTQ/QAT 与多 backend 量化 delegate
- [[ZK-APEX-MLSys26|ZK-APEX]]、[[LEANN-MLSys26|LEANN]] — ZK proof、edge 场景量化
- [[MoE-nD-arXiv26|MoE-nD]] — per-layer routing eviction ratio / K bits / V bits 联合压缩
- [[DeepSeek-V4-arXiv26|DeepSeek-V4]]、[[FluxMoE-arXiv26|FluxMoE]] — frontier MoE 量化部署
- [[SolidAttention-FAST26|SolidAttention]]、[[HipKittens-MLSys26|HipKittens]]、[[ProToken-MLSys26|ProToken]] — 量化 attention kernel 变体

## 已知局限 / 开放问题

- [[ScaleSearch-MLSys26]] 主要验证 NVFP4；ScaleSearchAttention 基于模拟框架，真实 Blackwell FP4 attention kernel 的 PPL/benchmark 待复现
- [[DriftBench-MLSys26]] 不含 drift-aware serving / 自动补偿；PRI 预测 aggregate flip rate，不预测 per-prompt flip
- FP8 MoE 长期收敛（671B+）与开启 overlap 的 production schedule 净收益未充分报告（[[FP8FlowMoE-MLSys26]]）
- mixed-precision KV 策略对非 causal 或弱 attention sink workload 泛化未验证（[[ScaleSearch-MLSys26]]）
- FA4 conditional rescaling 与 partial exp emulation 的训练语义影响未评估（[[FlashAttention-4-MLSys26]]）