---
type: concept
aliases: [Tensor Parallelism, tensor-parallel, TP, Megatron-style parallelism, intra-layer parallelism]
parent: "[[LLM-Inference]]"
introduced_by: "[[Megatron-LM-arXiv19]]"
last_updated: 2026-04-24
tags: [distributed-training, llm-inference, parallelism]
---

# Tensor-Parallelism

> 在 **单层内部** 把权重矩阵按列/行切到多个 GPU，每个 GPU 只算局部的 matmul，层边界做一次 AllReduce 把 partial sum 合起来。Megatron-LM 的原始方案：Attention 的 QKV projection 按列切、O projection 按行切；FFN 的上投影列切、下投影行切——正好让每层只需一次 AllReduce。代价是每层通信，所以 TP 通常只在 NVLink 域内用（单机 8 卡），跨节点走 [[Pipeline-Parallelism]] 或 [[Data-Parallel]]。

## 核心思想

考虑 FFN 的两个 matmul：`Y = GeLU(X W₁) W₂`。设 4 卡 TP：

- **W₁ 按列切**：`W₁ = [W₁⁽¹⁾, W₁⁽²⁾, W₁⁽³⁾, W₁⁽⁴⁾]`。每卡算 `Y_i = GeLU(X W₁⁽ⁱ⁾)`，得到 hidden 的不同列，无通信
- **W₂ 按行切**：`W₂ = [W₂⁽¹⁾; W₂⁽²⁾; W₂⁽³⁾; W₂⁽⁴⁾]`。每卡算 `Z_i = Y_i W₂⁽ⁱ⁾`，然后 `Z = ΣZ_i`（AllReduce）

Attention 类似：QKV projection 按 head 分组列切（天然适配 multi-head），O projection 行切。

每个 Transformer block 需要两次 AllReduce（Attention 出口 + FFN 出口）。

## 为什么只在高带宽域内用

每次 forward + backward 要 4 次 AllReduce × 每层 hidden × batch × seq_len 的数据量。对 70B Llama、4K seq、batch 4 而言，每步 TP 通信量 GB 级。NVLink 带宽 900 GB/s 够用，InfiniBand 100-400 Gbps 就是瓶颈。

所以 3D 并行的典型切法：**TP 在机内、[[Pipeline-Parallelism|PP]] 跨机器、[[Data-Parallel|DP]] 跨 PP stage**。

## 演进

- **Megatron-LM (2019)**：原始 TP 提法
- **Sequence Parallelism (2022)**：LayerNorm / Dropout 的输入按 seq 维度切，补充 TP 的 activation 内存未切问题
- **Context Parallelism (2024)**：长 context 下把 Q/K/V 按 seq 维度切，FA 要做 ring-style 通信（[[Context-Parallelism]]）
- **TP + EP 协同**：MoE 架构下 expert 的权重 TP 与 [[Expert-Parallelism]] 交叉切分

## 反面 / 替代

- **完全 DP + ZeRO**：不切权重，只切 optimizer / grad / param 分片。通信量小 per step 但需要 AllGather 参数，适合 small model or high-BW interconnect
- **[[FSDP]]**：ZeRO-3 的 PyTorch 原生实现，和 TP 正交组合
- **Expert Parallelism**：MoE 专用，把专家切到不同 GPU，通信模式不一样（[[AllToAll]]-heavy）

## 引用本概念的论文

- [[AXLearn-MLSys26|AXLearn]]、[[veScale-FSDP-MLSys26|veScale-FSDP]]、[[HexiScale-MLSys26|HexiScale]] — 训练框架的并行 runtime
- [[Chakra-MLSys26|Chakra]]、[[ProTrain-MLSys26|ProTrain]]、[[BOUTE-MLSys26|BOUTE]]、[[BOOST-MLSys26|BOOST]]、[[HetRL-MLSys26|HetRL]]、[[NEST-MLSys26|NEST]] — 训练调度 / 异构训练
- [[GhostServe-MLSys26|GhostServe]] — intra-node TP 下 chunk gather + parity 生成
- [[Zorse-MLSys26|Zorse]] — 异构集群上 TP 与 PP/DP 组合搜索
- [[OptiKit-MLSys26|OptiKit]]、[[MixLLM-MLSys26|MixLLM]]、[[LayeredPrefill-MLSys26|LayeredPrefill]]、[[DistCA-MLSys26|DistCA]] — 推理阶段 TP 切分
- [[PROMPTS-MLSys26|PROMPTS]] — 多 agent RAG 自动推荐 TPU ICI-mesh 分片（含 data/model/seq 轴），一次调用命中生产配置 87.5%
- [[ParallelKittens-MLSys26|ParallelKittens]]、[[FarSkip-Collective-MLSys26|FarSkip-Collective]]、[[EventTensor-MLSys26|EventTensor]] — TP 通信 kernel 优化
- [[FP8FlowMoE-MLSys26|FP8FlowMoE]]、[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — MoE / Disagg 里 TP 的角色
- [[DreamDDP-MLSys26|DreamDDP]] — 低带宽 geo-distributed 训练通信调度（与 TP 正交的 DP 优化）
- [[SHIP-MLSys26|SHIP]] — 72-LPU 分区 TP+PP 异构分区，QuadFour 拓扑直径 3 hop
- [[Hawkeye-MLSys26|Hawkeye]] — Tensor Core 非确定性 bit-exact 复现，支撑可验证 ML oracle
- [[TokenWeave-MLSys26|TokenWeave]] — fused AllReduce–RMSNorm + wave-aware token split，小 batch TP 推理 overlap 首次实用化
- [[Quirk-Sparing-MLSys26|Quirk-Sparing]] — 训练集群 sparing 策略建模中 compute block 越大 TP 收益越高，影响 goodput 最优 spare 配置
- [[RaidServe-MLSys26|RaidServe]] — irregular GPU 数 hybrid attention + cyclic [[KV-Cache]]，TP7 decode +78%
- [[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] — TP/EP 下 [[MoE]] padding 与 straggler tax 微观基准
- [[Charon-MLSys26|Charon]] — pass 注入 TP/PP/DP/FSDP/ZeRO/EP/SP 通信算子做端到端仿真
- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — Meta 生产模拟器：prefill/decode 阶段最优 TP 策略显著不同

## 相关概念

- 并行维度：[[Data-Parallel]]、[[Pipeline-Parallelism]]、[[Expert-Parallelism]]、[[Context-Parallelism]]
- 通信：[[AllReduce]]、[[Collective-Communication]]、[[NVLink]]
- 内存：[[ZeRO]]、[[FSDP]]
- 实现：[[Megatron]]、[[DeepSpeed]]
