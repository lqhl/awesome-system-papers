---
type: entity
kind: system
aliases: [DwarfStar, DS4, ds4]
status: active
last_updated: 2026-06-20
tags: [llm-inference, deepseek, local-inference, kv-cache, moe, ssd-streaming]
source_url: "https://github.com/antirez/ds4"
---

# DwarfStar

> antirez 的 `ds4` 项目：面向 DeepSeek V4 Flash / PRO 的本地 native inference engine，把模型加载、prompt rendering、tool calling、[[KV-Cache]] RAM/on-disk 状态、server API 与正确性验证做成端到端自包含 runtime，而非通用 GGUF wrapper。

## 是什么

DwarfStar（`ds4`）是 **模型特化、正确性优先** 的本地推理系统。它只支持项目发布的 DeepSeek V4 Flash / PRO GGUF，覆盖 Metal（主目标）、CUDA/ROCm 多后端；当模型无法完整驻留 RAM/GPU-addressable memory 时，non-routed weights 常驻，routed MoE experts 放在 GGUF 中，cache miss 时从 SSD 流式加载到 in-memory expert cache。server/agent 还支持 **disk KV checkpoint**，让长会话、重启与 session switch 可复用已 prefill 状态。

项目采取 opportunistic 策略：若 128GB/512GB 机器上出现更合适的新 open-weight 模型，目标模型可切换；但任意 DeepSeek/GGUF 文件不保证 tensor layout、quantization mix 或 MTP state 匹配。这与 [[vLLM]]/[[SGLang]] 的通用 serving 路径、[[KTransformers]] 的 CPU expert 执行路径形成对照——DwarfStar 窄而深，服务「高端个人机器跑 frontier-ish open-weight MoE」这一生态位。

**说明**：当前 `wiki/papers/*.md` 中尚无页面直接 wikilink `[[DwarfStar]]`；下列综合来自 [[DeepSeek-V4-arXiv26]]、[[MOE-INFINITY-arXiv24]]、[[FluxMoE-arXiv26]]、[[IceCache-arXiv26]]、[[MoE-nD-arXiv26]] 等相邻论文与既有 entity 元数据。

## 关键观察 / 隐含假设

- **观察 1：DeepSeek V4 的压缩稀疏 attention + FP4 routed expert 使个人机器上的 CPU/RAM/NVMe 成为可用推理层级。** [[DeepSeek-V4-arXiv26]] 在 1M context 下把单 token FLOPs 压到 V3.2 的 **27%**、KV 到 **10%**；异构 KV（压缩块 + SWA + on-disk prefix）打破 [[PagedAttention]] 的 layer 间 block 一致性假设。DwarfStar 是该模型侧路线在本地 runtime 上的系统化落点。
- **观察 2：MoE 本地部署的核心矛盾是 expert 与 KV 争用同一内存层次，但多数论文只优化其一。** [[FluxMoE-arXiv26]] 用 expert paging 把 HBM 让给 KV（vLLM 上最高 **3.0×**）；[[MOE-INFINITY-arXiv24]] 用 EAM 做 expert cache/prefetch（batch=1 时 TPOT 485ms→155ms）；[[KTransformers]] 把 expert 算在 CPU。DwarfStar 同时暴露 **SSD expert streaming** 与 **disk KV checkpoint** 两套 policy，但尚未统一资源仲裁——这是 wiki probe 识别的开放问题。
- **观察 3：personal-machine MoE 的有效场景是 batch size = 1、单用户、request 内 expert 激活稀疏。** [[MOE-INFINITY-arXiv24]] 明确把 cloud [[Continuous-Batching]] 排除在 scope 外；DwarfStar 同样非通用 server，而是本地 agent/coding 会话引擎。多租户、公平调度与 tail latency 不是其首要优化目标。
- **观察 4：正确性 gate 是窄平台的价值，而非 peak throughput。** DwarfStar 强调 official-vector/logit validation、long-context 测试与 attention/KV/logits drift 回归；[[DeepSeek-V4-arXiv26]] 亦投入 batch-invariant deterministic kernel 与 FP4 QAT 对齐。这些论文共同假设：本地 frontier 模型部署中，「能跑」与「可信」同样重要。
- **观察 5：KV 压缩路由正变得 per-layer、multi-axis，通用 serving 栈接入成本高。** [[MoE-nD-arXiv26]] 显示 per-layer eviction/K/V quant 路由在紧 budget 下可达 **14×** KV 压缩；[[IceCache-arXiv26]] 走语义 page layout。DwarfStar 若跟进 V4 的 CSA/HCA/SWA 异构 KV，需要 model-specific layout 而非 plug-in 式 [[PagedAttention]] 扩展。

## 演进时间线

- **2026（项目态）**：`ds4` 以 DeepSeek V4 Flash / PRO 为主目标，集成 SSD routed-expert streaming、disk KV session、Metal/CUDA/ROCm 后端与 correctness 回归体系（entity 元数据；无独立论文页 inbound）。
- **2026（模型/学术语境）**：[[DeepSeek-V4-arXiv26]] 发布 million-token 异构 KV 与 FP4 MoE 全栈；[[FluxMoE-arXiv26]]、[[MOE-INFINITY-arXiv24]]、[[KTransformers-SOSP25]] 定义 MoE offload 设计空间，为本地窄实现提供对照坐标。

## 相关概念

- [[MoE]]
- [[KV-Cache]]
- [[Quantization]]
- [[Prefix-Caching]]
- [[Expert-Offloading]]

## 相关论文

- [[DeepSeek-V4-arXiv26]] — 目标模型：CSA/HCA 稀疏注意力、FP4 MoE、异构 KV 与 on-disk prefix；通用 [[vLLM]]/[[SGLang]] KV 假设不适用
- [[MOE-INFINITY-arXiv24]] — personal-machine expert cache + EAM；NVMe/DRAM backing store 路线，与 ds4 SSD expert streaming 同设计空间
- [[FluxMoE-arXiv26]] — GPU expert paging 释放 KV 容量；cloud serving 视角，对照 ds4 的本地 SSD streaming
- [[KTransformers-SOSP25]] — CPU 执行 routed expert；对照 ds4 的「权重在 SSD/RAM、算在 GPU/CPU」切分
- [[MoE-nD-arXiv26]] — per-layer multi-axis KV 压缩；长 context 本地会话的 KV 压力建模参考
- [[IceCache-arXiv26]] — 语义 locality KV page 布局；与 disk/RAM KV tier 相关的压缩路线