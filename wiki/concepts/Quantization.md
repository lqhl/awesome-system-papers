---
type: concept
aliases: [quantization, Quantization, quantized, INT8, FP8, INT4, W8A8, W4A16, PTQ, QAT, post-training quantization, quantization-aware training, mixed-precision]
parent: "[[LLM-Inference]]"
last_updated: 2026-04-24
tags: [model-compression, llm-inference, efficiency]
---

# Quantization

> 用低精度数值表示权重 / activation / KV cache，以大幅降显存 + 提算力为目标。FP16→INT8 2× 省，INT4 4× 省；Hopper / Blackwell 的 tensor core 对 FP8 / MXFP4 有原生支持，算力直接翻倍。核心难点是怎么在精度损失可控的前提下量化——不同对象（权重 / activation / KV）、不同粒度（per-tensor / per-channel / per-group / per-token）、不同时机（PTQ / QAT）有完全不同的方法论。

## 基本分类

### 按对象

| 量化对象 | 难度 | 典型方案 |
|---|---|---|
| Weight-only (W8, W4) | 容易，可离线 | GPTQ, AWQ, HQQ |
| Activation | 难，动态分布 outlier | SmoothQuant, LLM.int8() |
| KV cache | 中等，影响长度/带宽 | KIVI, KVQuant |
| Gradient (训练时) | 难，反向误差累积 | FP8 训练（Hopper/Blackwell） |

### 按粒度

- **per-tensor**：整张权重共享一个 scale，最粗
- **per-channel**：每输出通道独立 scale，标准做法
- **per-group**：每 g 个元素（如 128）共享 scale，W4 下常用
- **per-token**：activation 按 token 维度动态 scale

### 按时机

- **PTQ (Post-Training Quantization)**：训练完再量化，用小 calibration set 估 scale
- **QAT (Quantization-Aware Training)**：训练中就模拟量化误差，精度好但成本高
- **Mixed-precision training**：FP8 权重 + FP16 master copy，Hopper 世代的主流训练方式

## 引用本概念的论文

- [[AttributionSparseActivation-MLSys26|AttributionSparseActivation]] — 运行时 neuron-level 稀疏激活与 PTQ 正交，W8A8 下收益可叠加

## LLM 推理里的典型组合

| 配置 | 含义 | 收益 |
|---|---|---|
| W4A16 | INT4 权重、FP16 activation | 显存 4×、算力仍 FP16（matmul 先 dequant） |
| W8A8 INT | 权重和 activation 都 INT8 | 算力 2×（若 tensor core 支持 INT8） |
| FP8 (E4M3 / E5M2) | Hopper / Blackwell 原生 | 算力 2×、数值范围比 INT8 大 |
| MXFP4 / NVFP4 | Blackwell 的 4-bit 浮点 | 算力 4×、首个真正好用的 4-bit 训练精度 |

## 系统视角

- **Dequant kernel 融合**：W4A16 需要在 matmul kernel 里先把 W4 上投到 FP16 再乘，融合得好算力开销可忽略
- **KV cache 量化**：每 token 存更少 bits → 更长 context / 更大 batch，但 attention 要能接受量化 K/V
- **Outlier 处理**：activation 里少数 channel 的数值远大于其他（Ferrari tail），需要 SmoothQuant 式重分配 scale 到权重
- **量化感知调度**：不同层对精度敏感度不同，[[Hawkeye-MLSys26]] / [[MixLLM-MLSys26]] 这类工作做 per-layer 混合精度

## 引用本概念的论文

- [[FP8FlowMoE-MLSys26|FP8FlowMoE]]、[[MixLLM-MLSys26|MixLLM]]、[[veScale-FSDP-MLSys26|veScale-FSDP]]、[[HyperTinyPW-MLSys26|HyperTinyPW]]、[[Kitty-MLSys26|Kitty]] — FP8 / 混合精度训练 & 推理
- [[IntAttention-MLSys26|IntAttention]]、[[MAC-Attention-MLSys26|MAC-Attention]]、[[MorphServe-MLSys26|MorphServe]] — 量化 attention / 量化 serving
- [[Hawkeye-MLSys26|Hawkeye]]、[[OptiKit-MLSys26|OptiKit]]、[[CAGE-MLSys26|CAGE]] — 量化调度 / 自动量化
- [[ZK-APEX-MLSys26|ZK-APEX]]、[[LEANN-MLSys26|LEANN]] — 特殊场景（ZK proof、edge）下的量化
- [[Shannonic-MLSys26|Shannonic]] — 量化后 tensor 的 entropy-optimal 无损压缩，530B state 近 Shannon 极限
- [[ApproxMLIR-MLSys26|ApproxMLIR]] — compound AI 端到端 accuracy knob 含 LLM [[Quantization]] 与 BM25 检索近似
- [[ScaleSearch-MLSys26|ScaleSearch]] — 搜索 NVFP4 block scale 邻域，量化误差 -27%；ScaleSearchAttention 端到端 FP4 attention+KV
- [[DriftBench-MLSys26|DriftBench]] — FP16→FP8 等精度迁移的 infrastructure drift 与 safety flip 风险
- [[ExecuTorch-MLSys26|ExecuTorch]] — torch.export 链路内 PTQ/QAT 与多 backend 量化 delegate，端侧实验一致性

## 相关概念

- 上游：[[LLM-Inference]]、[[GEMM]]、[[Tensor-Core]]
- 互补：[[KV-Cache-Compression]]、[[Distillation]]、[[LoRA]]
- 硬件支持：[[NVLink]]、Blackwell / Hopper FP8 路径
