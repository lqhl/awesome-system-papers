---
type: paper
name: KTransformers
full_title: "KTransformers: Unleashing the Full Potential of CPU/GPU Hybrid Inference for MoE Models"
authors: [Hongtao Chen, Weiyu Xie, Boxin Zhang, Jingqi Tang, Jiahao Wang, et al.]
venue: SOSP
year: 2025
tags: [llm-inference, moe, cpu-gpu-hybrid, expert-offloading, amx]
source_pdf: "[[3731569.3764843.pdf]]"
source_md: "[[3731569.3764843]]"
---

# KTransformers: Unleashing the Full Potential of CPU/GPU Hybrid Inference for MoE Models (SOSP 2025)

> **一句话总结**：AMX 专用 kernel + 单 CUDA Graph 异步调度 + Expert Deferral 重排流水线，671B [[MoE]] 在单 A100+双 Xeon 上 prefill **4.62–19.74×**、decode **1.25–4.09×**（Deferral 再 **1.45×**，精度损失 <0.5%）。

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

- Full accuracy：prefill **4.62–19.74×**、decode **1.25–4.09×** vs Fiddler/Llama.cpp 等
- + Expert Deferral：decode 累计 **1.66–4.90×**
- DeepSeek-V3：CPU/GPU 利用率 74/28% → 100/37%，decode +33%
- 单服务器+消费级 GPU 可跑 trillion-scale MoE

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