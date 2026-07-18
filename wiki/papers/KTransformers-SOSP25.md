---
type: paper
name: KTransformers
full_title: "KTransformers: Unleashing the Full Potential of CPU/GPU Hybrid Inference for MoE Models"
authors: [Hongtao Chen, Weiyu Xie, Boxin Zhang, Jingqi Tang, Jiahao Wang, Jianwei Dong, Shaoyuan Chen, Ziwei Yuan, Chen Lin, Chengyu Qiu, Yuening Zhu, Qingliang Ou, Jiaqi Liao, Xianglin Chen, Zhiyuan Ai, Yongwei Wu, Mingxing Zhang]
venue: SOSP
year: 2025
tags: [llm-inference, moe, cpu-gpu-hybrid, expert-offloading, amx]
source_pdf: "[[3731569.3764843.pdf]]"
source_md: "[[3731569.3764843]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-16
---

# KTransformers: Unleashing the Full Potential of CPU/GPU Hybrid Inference for MoE Models (SOSP 2025)

> **一句话总结**：AMX kernel、单 CUDA Graph 异步调度与 Expert Deferral 面向低并发 CPU/GPU hybrid MoE；batch=1 评测中，full-accuracy decode 相对 Fiddler 为 **2.42–4.09×**、相对 Llama.cpp 为 **1.25–1.76×**，Deferral 额外最高 **45%**（§6）。

## 问题与动机

[[MoE]] 稀疏激活适合低并发本地部署：[[Attention]]+共享专家留 GPU，路由专家 offload 到 CPU DRAM（Fiddler 思路）。但 671B DeepSeek-V3/R1 在 1×A100+2×Xeon 上仅 70/4.68 tok/s，GPU <30%——CPU 算力未释放（AMX 仅 7% 峰值）且 decode 同步开销巨大（Fiddler 7000+ kernel launch/token，占 GPU 时间 73%）。

## 关键观察 / 隐含假设

- **观察 1**：prefill 高 arithmetic intensity 场景下，AMX 需配合专用 memory layout（block quant、64B align、tiling-aware submatrix）才能接近峰值；decode 低 ARI 应退回 AVX-512。
  - **依赖假设**：Intel AMX 硬件可用；权重 layout 可离线重排。
  - **可能失效场景**：ARM SME 路径、无 AMX 的 CPU；专家极度不均衡时 AVX/AMX 切换策略需调整。
  - **证据强度**：强——microbenchmark 1.69–4.30× vs PyTorch oneDNN。
- **观察 2**：MoE 层内 attention 与 expert 顺序执行导致 CPU/GPU 互等，双端利用率低（74%/28%）。
  - **依赖假设**：defer 部分 routed experts 到下一层 attention 计算期间执行，不改变有效计算图语义近似可接受。
  - **可能失效场景**：高并发 batch 时 defer 破坏 batching 效率；对精度敏感任务 0.5% 仍不可接受。
  - **证据强度**：中——多 benchmark 平均 <0.5%，但是近似优化。
- **假设 1**：整段 decode 可封装进单个 CUDA Graph（CUDA spin 处理动态 shape），避免 per-layer per-batch graph 爆炸。
  - **证据强度**：强——1.23× decode 加速，VRAM 开销可控。

## 核心方法

1. **ARI-aware hybrid kernel**：prefill 用 AMX MoE kernel + NUMA-aware tensor placement；decode 用 AVX-512。
2. **Async CPU-GPU scheduling**：单 CUDA Graph 覆盖 decode，CPU 任务异步提交。
3. **Expert Deferral**：每层只算 immediate experts，deferred experts 与下一层 attention 重叠。

11K 行 C++ + HuggingFace 兼容接口，开源已广泛部署。

## 设计取舍

- **取舍 1**：Expert Deferral 牺牲最多 0.5% 精度换 33–45% 吞吐——非严格等价推理。
- **取舍 2**：聚焦低并发本地场景，高并发 cloud batching 非目标。
- **边界条件**：shared expert 架构的 MoE；无 shared expert 需 offline popularity profiling。

## 实验与结果

- Full-accuracy decode：相对 Fiddler **2.42–4.09×**，相对 Llama.cpp **1.25–1.76×**（§6.1–6.2，Fig.12）。
- Expert Deferral：decode 额外最高 **45%**；相对 Llama.cpp 的总体范围 **1.66–2.56×**（§6.3，Fig.12）。
- 精度边界：DeepSeek-V3 默认 defer 6 的 LiveBench 平均 accuracy drop **0.5%**；同数 affected experts 的 skipping 为 **13.3%**（§6.3，Fig.13）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| DS-3 CPU MoE kernel 达到 21.3 TFLOPS | 为 PyTorch 实现的 3.98×（§6.2，Fig.3） | DS-3 CPU MoE microbenchmark | high |
| full-accuracy decode 快于两个基线 | vs Fiddler 2.42–4.09×，vs Llama.cpp 1.25–1.76×（§6.1–6.2，Fig.12） | batch 1、32-token prompt、最多 512 decode、A100 | high |
| NUMA-aware partitioning 提高 decode throughput | 相对 NUMA-oblivious baseline 最多 1.63×（§3.3，§6.4，Fig.14） | dual-socket 主机 | high |
| Expert Deferral 仅在 decode 中带来额外吞吐 | 额外最高 45%（§4.1–4.2，§6.3，Fig.12） | batch=1/local；不用于 prefill | high |
| Deferral 的质量损失小于跳过专家 | DS-3 defer 6 LiveBench 平均 drop 0.5%，skipping 13.3%（§6.3，Fig.13） | 2024-11-25 LiveBench、10 samples、temperature 0.3 | high |

## Critical Analysis

### 论证链条

profiling 瓶颈 → 三组件各对应一瓶颈，链条清晰。Expert Deferral 是少数「改执行顺序而非纯工程」的设计，有 taste 价值，但本质是近似。

### 假设压力测试

- 0.5% 平均掩盖 per-task 退化；HumanEval 等个别 benchmark 需单独核对。
- 高并发 serving（vLLM 类 continuous batching）完全未覆盖。
- PCIe 5.0、多 GPU 场景下 CPU offload 是否仍最优？

### 实验可信度

Microbenchmark + 端到端 DeepSeek-V3 showcase 有说服力。Baseline 包含 Fiddler、Llama.cpp 等实际竞品。生产「数百台机器」声明缺系统级数字。

### 系统性缺陷

论文未讨论：defer 对 latency SLA 的影响；多租户安全（本地部署优先级低）；与 [[GPTQ]]/[[AWQ]] 等量化栈组合行为。

## 局限与 Future Work

- **局限 1**：Expert Deferral 非 bit-exact。
- **局限 2**：低并发假设，cloud scale-out 未验证。
- **Future work 1**：自适应 defer 比例，按在线 perplexity/logit 监控闭环调节。

## 相关

- **相关概念**：[[MoE]]、[[KV-Cache]]、[[Attention]]、expert offloading
- **同类系统**：[[vLLM]]、Fiddler、Llama.cpp、[[SGLang]]
- **同会议**：[[SOSP-2025]]
