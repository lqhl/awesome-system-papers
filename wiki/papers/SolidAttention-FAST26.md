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
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# SolidAttention: Low-Latency SSD-based Serving on Memory-Constrained PCs (FAST 2026)

> **一句话总结**：AIPC（8–16GB DRAM、6–8GB VRAM、batch=1）上长上下文 [[KV-Cache]] 比 INT4 权重还大 4×，dynamic [[Sparse-Attention]] + SSD offload 又因 token 粒度随机 I/O 与 SSD 顺序大块读写冲突而无法 overlap；SolidAttention 用 K/V token 交错凑传输块、基于 81% 层间选择相似度的 speculative prefetch、以及 DAG microtask 调度共设计算法与存储，128k 上下文推理加速 **3.1×**、KV 内存降至 **2%**（最多省 98%），精度与全内存 baseline 持平。

## 问题与动机

本地 LLM 部署（[[llama.cpp]]、Ollama）在隐私、定制化和成本上吸引力大，但主流 AIPC 硬件（8–16GB DRAM、6–8GB VRAM 的 iGPU 或入门独显）与 128k 默认上下文严重不匹配：Llama-3.1-8B INT4 权重约 4GB，而 128k token 的 [[KV-Cache]] 单独就要 **16GB+**，约为权重的 **4×**，挤占系统内存且无法与「全量 KV 驻内存」的现有引擎假设兼容。

缓解路径各有硬伤。**KV cache [[Quantization]]**（INT4 等）在 Qwen-2.5-7B 上平均精度从 71.39 跌到 18.63，outlier 敏感。**Dynamic [[Sparse-Attention]]**（[[InfLLM]]、Quest）每步只算 top-k block，但为保留动态选择能力，**完整 KV 必须留在内存**，稀疏只省算力不省容量。**SSD offload**（[[FlexGen]]）靠 zigzag batching 用并发请求的 compute 掩盖 I/O——适合 throughput-oriented 云/批处理，在 AIPC 本地 **batch=1** 时 I/O 完全暴露：加载 1k token KV（~128MB）约 **40ms**，可占单步 decode 近一半。

作者判断根因是 **sparse attention 的细粒度不规则访问** 与 **SSD 偏好 coarse-grained 顺序 I/O** 的结构性冲突；现有工作把算法与存储管理割裂，导致 overlap 失败。SolidAttention 的核心 claim 是：必须 **co-design** 稀疏 attention 算法与 SSD 存储管理，对齐访问粒度并细粒度编排 compute-I/O，才能在内存受限 PC 上做到低延迟长上下文 serving。

## 关键观察 / 隐含假设

- **观察 1：SSD 带宽随传输单元增大而陡升，token 粒度 offload 严重浪费带宽。** Figure 1b 显示 consumer NVMe 在传输单元 <128KB 时随机读吞吐远低于峰值；FlexGen 等按 token 加载，需靠高并发 compute 才能 hide latency。
  - **依赖假设**：实验机上的 Samsung 990 PRO（PCIe 4.0，~7.5GB/s）能代表 AIPC 常见 NVMe；读主导、写放大可忽略（论文实测 write overhead negligible）。
  - **可能失效场景**：PCIe 5.0/CXL-SSD、统一内存 iGPU 路径绕过显式 DMA 时，瓶颈可能从 SSD 带宽转向 compute 或 sync；极慢 eMMC/UFS 存储上 coarse-grain 收益更大但绝对延迟仍可能不可接受。

- **观察 2：相邻 decode iteration 间，同层 KV block 选择平均约 81% 相似（LongBench 多模型）。** 这使「用上一轮选择预测下一轮」的 speculative prefetch 在统计上可行；init block（[[StreamingLLM]] attention sink）与 local block（最近 token 滑窗）则 100% 必选，可 deterministic preload。
  - **依赖假设**：目标 workload 是连续 autoregressive decode，层间 attention pattern 具 temporal locality；block-wise representative（沿用 [[InfLLM]] 的 identifier）足以近似 block 重要性。
  - **可能失效场景**：强工具调用导致 context 结构突变、多轮大幅改写 system prompt、或需要 recall 远距离冷门事实时，19% misprediction 的补块 I/O 可能集中爆发；论文未按 task 类型细分 misprediction 分布。

- **观察 3：K 与 V 向量同 shape，token 级交错可把传输单元翻倍而不增加每 block token 数。** 相比增大 block size（32→256 token 时 PassageRetrieval recall 明显下降，Figure 6），interleave 不牺牲 representative 精度，attention kernel 用 stride=2H 即可逻辑分离 K/V。
  - **依赖假设**：推理框架支持 strided tensor access（PyTorch、[[llama.cpp]]）；预拼接 K/V 投影权重的一次 matmul 不破坏数值行为；strided access overhead ≤2%。
  - **可能失效场景**：自定义 fused kernel 硬编码 contiguous layout、或 GQA/MQA 下 K/V head 数不一致时需额外适配；论文仅在 Llama/Qwen 家族验证。

- 观察 4：AIPC 本地 serving 的瓶颈是 latency 而非 throughput，request concurrency ≈ 1。 Figure 2 显示 FlexGen 式 batch overlap 在低并发下无法隐藏 SSD 延迟；SolidAttention 必须把 overlap 做到 单请求、单层、microtask 粒度。
  - **依赖假设**：用户主要关心 interactive decode latency（batch=1，max output 512）；DRAM 预算可压到 16GB 仍代表「内存受限 PC」。
  - **证据强度**：强。实验显式设 batch=1，并与 Offload+Sparse、FlexGen 对比。

- **假设 1**：1k token 的 context budget（输入 ≥4k 时固定为 1k；更短输入为长度 25%）足以在 LongBench 等长上下文任务上保持与 dense baseline 接近的精度。
  - **证据强度**：中。Table 1 与 LongBench 子集支持；但 budget 从 1k 提到 4k 时 I/O 不再能被 compute 完全 hide（Figure 18），精度-延迟 trade-off 由运维方承担。

## 核心方法

SolidAttention 在 [[llama.cpp]] 上实现，整份 [[KV-Cache]] 驻 SSD，GPU/DRAM 只保留当前层约 **1k token** 的 buffer；三块协同：

**Block-wise dynamic sparsity（沿用并细化 InfLLM/Quest 范式）**：KV 按 context 维切成 block（默认 **32 token/block**），分 init / local / selected 三类；decode 时对 representative 与 query 算相似度，取 top-k selected block，与 init、local 一并参与 [[Attention]]。Context budget 一半给 init+local，一半给 selected。

**KV Consolidator**：离线预拼接 K、V 投影权重，单次 matmul 产出 token 级交错 KV；SSD↔CPU↔GPU 传输均以交错块为单元，I/O 次数减半、有效传输粒度翻倍。Self-attention 通过 stride=2H 读取，无需物理 reorder 或重写 kernel。

**Speculative Prefetcher**：记录每层上一轮 selected block 集合，在本层 q proj 完成后即按历史预测发起 SSD 预取；init/local 确定性预取。Misprediction 时补 load missing block，错误预取块 **out-of-order overwrite**——attention 只要求同位置 K/V 对齐，不要求全局 token 顺序，避免昂贵 reorder。

**SSD-aware Scheduler**：将单层 attention 拆为 q proj、kv proj、store、prefetch、select、load、attention 等 microtask，建模为 DAG；识别 critical path，非关键 I/O 尽早发射以与 kv proj 等 overlap；用 LST 做 latency-aware 优先级（selected block prefetch 优先于 init/local transfer）。Non-critical store 与下一层 prefetch 共享 sync point，减少 CPU-GPU-SSD 握手频率。在 unified memory（Intel Arc iGPU）上可进一步削减显式 DRAM↔VRAM 同步。

**实现细节**：~25k 行 C++/CUDA（12k GPU kernels + 1k llama.cpp adapter），CUDA + SYCL 双后端；**liburing** 异步 SSD I/O；专用 CPU core 分别负责 I/O 与 SSD-GPU 协调；32KB per-layer write buffer 合并写、缓解 wear。

## 设计取舍

- **用 block-wise sparsity + 固定 1k budget 换内存**：不把 KV 量化到 INT4，精度接近 Origin（平均 score 57.67 vs 57.82 on Llama-3.2-3B）。代价是长上下文 recall 依赖 sparsity 质量；block size 32 是精度（vs 256 的 recall 下滑）与 SSD 利用率（vs 16 的 ~14% 吞吐损失）的折中。

- **用 speculative prefetch 换实现复杂度与带宽敏感度**：81% 命中率下大幅削减 blocking latency（2.9–3.9×），但错预取仍消耗 SSD 带宽；后台 I/O 争用时吞吐可降 **58%**（4GB/s 背景读），比 Offload+Sparse 更敏感——因为系统已把带宽吃满。

- **用极小 DRAM buffer 换部署门槛**：只缓存单层 1k token KV，内存降 **61.9–62×**；代价是每层 decode 都依赖 SSD 读路径，故障恢复、多请求并发、与权重 offload（[[PowerInfer]] 等）同时启用时的 I/O 争用论文标为 future work。

- **边界条件**：单用户、长输入（16k–128k）、NVMe 正常、batch=1 时设计最优雅；短 context（<4k）或 context budget 提到 4k 时 I/O 成为硬瓶颈；多租户并发、HDD/慢闪存、或需 bitwise 等价于 dense attention 的场景不适用。

## 实验与结果

- **硬件**：CUDA 后端 RTX 4070 Laptop 8GB + Ultra 9 185H；SYCL 后端 Intel Arc 140T iGPU + Ultra 7 255H；均 64GB DDR5 + Samsung 990 PRO；实验将 DRAM 限制 **16GB**。模型：Llama-3.2-3B、Llama-3.1-8B、Qwen-2.5-7B（权重 INT4，KV FP16）；另测 Qwen2.5-14B。
- **Baseline**：Offload（全 KV 放 SSD）、Offload+Sparse（+[[InfLLM]]）、[[FlexGen]]（attention score 稀疏，扩展支持 Llama/Qwen）。
- **吞吐**：128k 输入下相对 Offload+Sparse 加速 **2.8× / 3.1× / 2.4×**（三模型）；16k 下相对 FlexGen 最高 **58.9×**（FlexGen 在 16GB 限制下 >16k OOM）。SYCL 上 **1.9–2.5×**。
- **内存**：KV 占用降至约 **2%**（**61.9–62×** 缩减）；Qwen2.5-14B 128k 下 **98%** KV 内存节省 + **1.7×** 吞吐。
- **精度**：OpenCompass + LongBench，SolidAttention 与 Origin 平均分差 <1 pt；Quant baseline 在 Qwen 上崩溃。
- **Ablation**：相对全内存 InDRAM，SSD offload 版本吞吐仅 **≤11%** 下降；speculative prefetch 降 blocking latency **2.9–3.9×**；KV interleave 降 attention latency **22%**；fine-grained overlap **+25%**，sync reuse **+22%**。
- **敏感性**：context budget 4k 时 attention latency 陡升（I/O 无法 hide）；block size 32 优于 16 约 **14%**；慢 SSD（KIOXIA BG6）在 4k budget 下 P99 延迟升 **45%**；背景 I/O 下平均延迟升 **2.4×**、P99.9 升 **2.9×**。
- **能耗**：GovReport ~10k token 摘要，**3.68 J/token** vs llama.cpp **5.37**（**-46%**），尽管峰值功率更高（SSD 活动）。

## Critical Analysis

### 论证链条

主链条闭合：测量证明 (1) KV 随长度线性压垮 AIPC 内存、(2) SSD 厌恶细粒度读、(3) 低并发下 FlexGen 式 overlap 失效、(4) 层间 block 选择 81% 稳定 → 三块设计分别对齐粒度、提前 I/O、细粒度调度 → 128k 下 3.1× 加速且精度不掉。Ablation 把 prefetch、interleave、scheduler 的边际贡献分开量化，支撑「co-design 必要」而非单点技巧。

最脆跳步是 **1k context budget 的精度-延迟外推**：论文证明 1k budget 在评测集上接近 Origin，但当用户把 budget 提到 4k 换质量时，I/O 瓶颈再现（Figure 18），系统优势大幅缩水——作者诚实报告但未给出 adaptive budget 或 quality guardrail。

### 假设压力测试

**81% 选择相似度**：在代码补全、多文档 RAG 交替、或 tool result 大量插入时，层间 pattern 可能更 volatile；论文未报告 per-task misprefetch rate 或 worst-case latency。**已证明** LongBench 统计；**推断**极端 agent 场景可能退化。

**16GB DRAM 限制 vs 64GB 物理机**：实验机实际 64GB，仅软件限制 16GB 模拟「受限 PC」。真实 8GB 机器上 OS + 应用争抢可能更严，单层 buffer + liburing 线程的 pinned memory 开销未单独量化。

**与 in-DRAM 对比的公平性**：InDRAM+Sparse 用 InfLLM 但不 offload；SolidAttention 在 ≤11% 吞吐差距内接近 in-memory，claim 有力。但未与 **[[Quantization]] KV + 全内存** 或 **host memory tiering**（如 [[LMCache-arXiv25]] 式 CPU DRAM 层）在同等内存预算下对比。

**已证明 vs 推断**：128k WikiText-2 截断 prompt 上的吞吐 — **已证明**；真实用户对话 trace 的 tail latency — **未覆盖**；SSD 磨损长期影响 — **未讨论**（有 32KB write coalescing 但无 endurance 模型）。

### 实验可信度

Baseline 选择贴合问题：Offload+Sparse 代表「已有稀疏 + SSD」直接组合；FlexGen 代表 throughput-oriented 参照。batch=1、max output 512 对齐 AIPC 交互场景。扩展 FlexGen 到 Llama/Qwen 是合理工程，但 FlexGen 原设计并非为 128k single-user 优化，58.9× 差距部分来自 FlexGen 在受限内存下的 page-fault 行为（作者有分析）。

弱点：(1) 输入多用 WikiText-2 截断，与真实长文档分布有 gap；(2) 缺少 P95/P99 端到端 token latency 的系统级报告（§8.5.3 有部分 SSD 尾延迟）；(3) 仅三模型家族 + 单用户；(4) 实验机 64GB 物理内存与目标 8–16GB 市场机仍有距离；(5) 未与 IMPRESS、CachedAttention 等 FAST'25 KV tiering 或 [[Bidaw-FAST26]] 等 bidirectional 感知 offload 对比。

### 系统性缺陷

- **SSD 争用脆弱性**：后台 4GB/s 读时吞吐降 58%，且与 baseline 差距收窄 — 论文有测但无 QoS 隔离或 I/O priority 机制。
- **单请求架构**：未讨论 [[Continuous-Batching]]、多会话并发、[[Prefix-Caching]] 共享；整 KV 放 SSD 时多租户隔离与 cache 失效策略论文未涉及。
- **正确性边界**：sparsity + speculative prefetch 无 bitwise 等价保证；misprefetch overwrite 依赖 attention 对顺序不敏感，若接入需要位置严格对齐的变体（某些 [[Sparse-Attention]] kernel）需重新验证。
- **可观测性/运维**：25k LOC 自定义调度 + liburing，缺 operator-facing prefetch hit rate、blocking breakdown、SSD health 指标；故障时 fallback 到全内存或 dense attention 未描述。
- **与权重 offload 共存**：Related work 指出 [[PowerInfer]] / MoE prefetch 可能与 KV I/O 争用带宽 — **论文未实验**。
- **写放大与寿命**：承认 KV 频繁写 SSD，靠 32KB buffer 缓解，但无长期 wear 数据。

## 局限与 Future Work

- **局限 1**：依赖 block-wise sparsity；更大 block 或 token-granularity sparse（H2O 等）直接接入会重现细粒度 I/O 问题。
- **局限 2**：speculative prefetch 对选择模式突变敏感；无在线 hit rate 监控与自适应预测策略。
- **局限 3**：实验以单用户、batch=1、WikiText-2 截断为主；未覆盖 production chat trace、多模态、或 thinking model 极长 chain。
- **局限 4**：context budget 与 block size 全局固定（1k / 32），缺少 per-request 质量-延迟旋钮。
- **Future work 1**：集成 RetrievalAttention、ClusterKV 等 semantic clustering，在同等 budget 下提高 representative 质量、降低所需 selected block 数 — 论文已在 related work 点名。
- **Future work 2**：与 expert/weight offload（PowerInfer、FlexInfer）统一 I/O 调度，测量 KV vs weight 带宽仲裁策略。
- **Future work 3**：在真实 8GB 机器、慢 SSD、高背景 I/O 下测 P99 latency 与 endurance；评估 PCIe 5.0 / ZNS 等新兴存储上的收益边界。
- **Future work 4**：探索 host DRAM tier（热 block 留内存、冷 block 放 SSD）与 speculative prefetch 的组合，缩小与全内存 ≤11% 差距。

## 相关

- **相关概念**：[[KV-Cache]]、[[Sparse-Attention]]、[[Attention]]、[[Quantization]]、[[Flash-Attention]]、[[PagedAttention]]
- **同类系统**：[[FlexGen]]、[[InfLLM]]、Quest、SnapKV、[[StreamingLLM]]、[[llama.cpp]]、CachedAttention、IMPRESS、[[PowerInfer]]、[[LMCache-arXiv25]]
- **同会议**：[[FAST-2026]]、[[Bidaw-FAST26]]、[[CacheSlide-FAST26]]
- **对比**：相对 FlexGen 面向高并发 throughput；相对 InfLLM 解决「稀疏省算力但不省内存」；相对 KV quant 用 sparsity 保精度
