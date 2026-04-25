---
type: paper
name: SolidAttention
full_title: "SolidAttention: Low-Latency SSD-based Serving on Memory-Constrained PCs"
authors: [Xinrui Zheng, Dongliang Wei, Jianxiang Gao, Yixin Song, Zeyu Mi, Haibo Chen]
venue: FAST
year: 2026
tags: [llm-inference, kv-cache, ssd-offload, attention-sparsity, aipc]
source_pdf: "[[fast2026-zheng.pdf]]"
source_md: "[[fast2026-zheng]]"
---

# SolidAttention: Low-Latency SSD-based Serving on Memory-Constrained PCs (FAST 2026)

> **一句话总结**：AIPC（8–16GB DRAM + 6–8GB VRAM）跑长上下文 LLM 时 [[KV-Cache]] 比模型权重还大 4×，SSD offload 又因 token 粒度的细碎 I/O 跟 SSD 顺序大 I/O 特性冲突；SolidAttention 用「KV interleave 凑成块 + 基于历史的 speculative prefetch + SSD-aware microtask scheduler」共设计稀疏 attention 算法和存储管理，128k 上下文下推理加速 **3.1×**、KV cache 内存占用降至 **2%**（最多省 98%），且不掉精度。

## 问题

本地部署 LLM（[[llama.cpp]]、Ollama）面临的硬约束：8B 模型 + 128k token 上下文要 16GB+ KV cache（INT4 量化），是模型权重的 **4×**。已有路径都不够：
- **激进量化** KV cache 到 INT4/INT2 通常严重掉精度。
- **Dynamic attention sparsity**（[[InfLLM]]、Quest）虽然只算少量 KV，但**整体 KV 必须留在内存**才能动态选——失去了节省内存的机会。
- **SSD offload**（[[FlexGen]]）走 throughput-oriented 路线靠 batch overlap 隐藏 I/O——但 AIPC 本地场景 batch=1，I/O 完全暴露成主导延迟（加载 1k token KV 块 ~40ms，占 decode 步近一半）。
- 根因：sparse attention 的 token 粒度随机访问 vs SSD 偏好的 coarse-grained 顺序——必须**协同设计**。

## 核心方法

SolidAttention 三组件，整 KV cache 驻 SSD，按需 dynamically load 进 GPU。

**KV Consolidator（§4）**：在 token 粒度把 K 和 V 向量**交错**（K 和 V 同 shape），单元从 K 单独 / V 单独 变成 KV 交错块——SSD 单次传输大小翻倍、I/O 次数减半，但 attention 计算只需用 stride=2H 的 strided access 看（PyTorch / [[llama.cpp]] 原生支持），无需重排和改 GPU kernel。模型加载阶段把 K 和 V 投影权重**预拼接**成统一 tensor，单次 matmul 直接产出交错布局，省去运行时 reorder。block size 选 128 平衡 representative vector 精度（>256 召回率明显下降）和 SSD 带宽（SSD 在 128KB+ 才接近峰值）。

**Speculative Prefetcher（§5）**：观察到层间 KV block 选择跨 iteration 平均 **81% 相似**，把上一次该层的选择当作下一次的预测，提前从 SSD 预取——把"选择→attention"间的空窗变成可被 prefetch 填满的 I/O 窗口。错预的块（19% 误差）走 **out-of-order overwrite**：缺的块从 SSD 补，错的块直接被覆盖——self-attention 对 KV 全局顺序无要求，无需昂贵 reorder。Init blocks（attention sink）和 local blocks（最近 token）100% 必选，做 deterministic preload。

**SSD-aware Scheduler（§6）**：把 attention 模块拆成 microtasks，按数据依赖和 GPU compute / SSD I/O 异步排程；把 non-critical 任务**合并到 critical path 的同步点**复用 sync barrier，减少同步频率。在 unified memory 架构（iGPU）下进一步省去 DRAM↔VRAM 显式同步。

**实现**：~25k 行 C++/CUDA（12k GPU kernels + 1k llama.cpp adapter），CUDA + SYCL 双后端，liburing 做 SSD I/O，专用核分别管 I/O 和 SSD↔GPU 协调；32KB per-layer write buffer 缓解 SSD 写放大与 wear。

## 关键结果

- 128k token 上下文下端到端推理 **2.4–3.1×** 加速（vs Offload+InfLLM）；vs FlexGen 在 16k token 高达 **58.9×**（FlexGen 在低并发下退化严重）。
- KV cache 内存占用降到 **2%**（最多省 98%）—— Llama-3.2-3B / Llama-3.1-8B / Qwen-2.5-7B 各省 **61.9× / 62.0× / 61.9×**。
- INT4 量化的 Qwen2.5-14B 在 SYCL 后端上 KV 减 98% + 1.7× 吞吐提升，验证大模型可扩展。
- speculative prefetcher 单独贡献 blocking latency 降 **2.9–3.9×**；KV interleave 单独减 attention 延迟 22%；fine-grained overlap + sync reuse 各贡献 25% / 22%。
- 能耗：3.68 J/token，比 [[llama.cpp]] 改善 46%。

## 相关

- **相关概念**：[[KV-Cache]]、[[Attention-Sparsity]]、[[SSD-Offload]]、[[Speculative-Prefetching]]、[[Microtask-Scheduling]]
- **同类系统**：[[FlexGen]]、[[InfLLM]]、Quest、SnapKV、[[StreamingLLM]]、[[llama.cpp]]、Ollama
- **同会议**：[[FAST-2026]]
