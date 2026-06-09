---
type: entity
kind: system
aliases: [DwarfStar, DS4, ds4]
status: active
last_updated: 2026-06-09
tags: [llm-inference, deepseek, local-inference, kv-cache, moe, ssd-streaming]
source_url: "https://github.com/antirez/ds4"
---

# DwarfStar

> DeepSeek V4 Flash / PRO 优先的本地 native inference engine，目标不是通用 GGUF runner，而是围绕一个 frontier-ish open-weight [[MoE]] 模型，把模型加载、prompt rendering、tool calling、[[KV-Cache]] RAM/on-disk 状态、server API、coding agent 和测试验证做成端到端可用系统。

## 是什么

DwarfStar 是 antirez 的 `ds4` 项目。GitHub 页面把它描述为 DeepSeek 4 Flash / PRO 的 local inference engine，支持 Metal、CUDA 和 ROCm；README 进一步说明它是 self-contained runtime，不是另一个引擎的 wrapper。

它当前把 DeepSeek V4 Flash / PRO 作为主要目标，因为这些模型在能力、尺寸、KV cache 效率和 2-bit routed expert 量化上适合高端个人机器。项目也明确采取 opportunistic 策略：如果 128GB/512GB 机器上出现更合适的新 open-weight 模型，目标模型可以切换。

## 系统特点

- **模型特化而非通用运行时**：只支持项目发布的 DeepSeek V4 Flash / PRO GGUF；任意 DeepSeek/GGUF 文件不保证 tensor layout、quantization mix、metadata 或 MTP state 匹配。
- **多后端**：Metal 是主目标；另有 NVIDIA CUDA / DGX Spark 路径，以及 Strix Halo ROCm 路径。
- **SSD streaming routed experts**：当模型不能完整驻留 RAM/GPU-addressable memory 时，non-routed weights 常驻，routed MoE experts 放在 GGUF 文件中，cache miss 时从 SSD 加载到 in-memory expert cache。
- **on-disk KV session**：server/agent 支持 disk KV cache checkpoint，让长会话、重启和 session switch 可以复用已经 prefill 的状态。
- **正确性优先**：项目强调 official-vector/logit validation、long-context tests，以及对 attention/KV/logits drift 的解释和回归测试。

## 与本 wiki 的关系

DwarfStar 是 [[DeepSeek-V4-arXiv26]] 这类模型侧压缩路线的本地系统化落点：DeepSeek V4 的 routed expert 稀疏性、FP4/2-bit expert 量化和压缩 [[KV-Cache]] 让高端个人机器上的 CPU/RAM/NVMe 变成可用推理层级。

在 [[MoE]] expert offload / KV offload 研究里，它的价值不是通用性，而是提供一个窄但真实的 trace platform：可以同时观察 expert cache miss、SSD expert streaming、disk KV checkpoint、token latency、prompt replay 和 correctness gate。

## 相关

- **相关论文**：[[DeepSeek-V4-arXiv26]]、[[FluxMoE-arXiv26]]、[[MOE-INFINITY-arXiv24]]、[[MoE-nD-arXiv26]]、[[IceCache-arXiv26]]
- **相关概念**：[[MoE]]、[[KV-Cache]]、[[Quantization]]
- **外部链接**：[antirez/ds4](https://github.com/antirez/ds4)

