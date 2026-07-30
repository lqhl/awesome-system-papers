---
type: paper
name: LocalityAwareBeamScheduling
full_title: "Locality-Aware Beam Scheduling for Efficient Test-Time Compute with a Consumer-Grade GPU"
authors: [Hsing-Ti Wang, Hung-Tso Shiao, Chia-Lin Yang]
venue: MLSys
year: 2026
tags: [test-time-compute, kv-cache, beam-search, offloading, consumer-gpu]
source_pdf: "[[44f683a84163b3523afe57c2e008bc8c.pdf]]"
source_md: "[[44f683a84163b3523afe57c2e008bc8c]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# LocalityAwareBeamScheduling：使用消费级 GPU 进行局部感知波束调度以实现高效测试时计算（MLSys 2026）

> **原题**：Locality-Aware Beam Scheduling for Efficient Test-Time Compute with a Consumer-Grade GPU

> **一句话总结**：在 consumer GPU 上 step-wise beam search 使 [[KV-Cache]] 占内存 **>70–80%**、layer-wise offloading 的 I/O stall 达 **85%**；LBS 利用 inter-token / inter-beam locality 重排 beam 执行并 balanced prefetch，KV 传输量 **>95%** 削减，OPT/LLaMA/Qwen-7B 端到端 **3.4–9.7×** 加速。

## 问题与动机

[[LLM]] 推理正从「静态扩模型」转向 **test-time compute (TTC)**：在推理阶段分配额外算力探索多条 reasoning path（step-wise beam search、tree search 等），以提升数学推理、代码生成等复杂任务质量。与此同时，部署重心也在从 datacenter 下沉到 **consumer-grade GPU**（隐私、定制、成本）。

在典型 **single-batch、本地推理** 场景下，[[KV-Cache]] 往往只占 GPU 内存一小部分（<1/10 权重），研究长期聚焦权重压缩与 layer-wise offloading（FlexGen、llama.cpp、DeepSpeed-Inference）。但 TTC 下每条 decoding path 维护独立 KV cache，内存随 beam 数线性增长；宽 exploration 时 cache 可数倍于权重，成为主导瓶颈。

现有 offload 框架虽支持 KV 与权重一并换出，但默认 **token-by-token、全 beam 同步推进** 的执行顺序在 cache 溢出后反复 reload 同一 KV 段，PCIe 传输主导 runtime。KV sparsity / token eviction（H2O、InfiniGen）面向长 context 衰减场景，不适用于 TTC 短序列多路径；datacenter 多卡 KV 分片（NVLink、Mooncake）在 consumer 环境不可用。论文声称这是**首次系统刻画并针对 TTC workload 的 KV cache 瓶颈**提出调度优化。

## 关键观察 / 隐含假设

- **观察 1（KV 主导内存与 I/O）**：OPT-6.7B、seq=2048、RTX 4090 上，16 beam 时 KV 占 GPU 内存 **>55%**，32 beam **>70%**，64 beam **>80%**；溢出后 layer-wise offloading 的 I/O stall 占端到端 latency **最高 85%**（Figure 4）。
  - **依赖假设**：beam 宽度与 step length 足够大，使多路径 KV 总和超过 24 GB 级显存；PCIe Gen4 x8 带宽成为换出后的主导瓶颈。
  - **可能失效场景**：小 beam（≤8）、短输出、或权重本身已占满显存时，offload 未触发，调度收益趋近于零；NVLink 统一内存或更大 VRAM（48 GB+）会削弱 I/O 瓶颈叙事。

- **观察 2（inter-token locality）**：step-wise beam search 每步内多 token 独立扩展、仅步末同步；同 beam 连续 token 生成需访问**同一路径上全部历史 KV**，步内按 beam（组）顺序执行可让组内 cache 常驻 GPU 至该步结束（Figure 6）。
  - **依赖假设**：步长（32/64/128 token）足够长，使「组内顺序解码」的 reuse 窗口大于「全 beam 交替」的 reload 次数；调度重排不改变 pruning 语义（作者声称步内顺序可任意重排而不影响精度）。
  - **可能失效场景**：极短 step（单 token beam search）退化为无 locality；动态显存碎片使组大小频繁变化，增加 kernel launch 次数。

- **观察 3（inter-beam locality）**：跨 decoding step，存活 beam 共享 prefix，KV 段高度重叠（Figure 8）；共享 prefix 的 beam 划入同组可避免重复 host→device 传输。
  - **依赖假设**：pruning 后 beam 树仍保留足够 prefix 重叠；贪心按 KV block 交集选 beam 的近似足够接近最优分组。
  - **可能失效场景**：高 beam width 导致 prefix 快速分化、重叠率下降；最优分组为 NP-hard 级枚举，贪心在 adversarial tree 上可能显著次优。

- **假设 1（权重常驻 GPU）**：实验模型（OPT/LLaMA/Qwen 6.7–7B）权重可完全放入 GPU，优化仅针对 KV offload；与 PowerInfer、llama.cpp 等权重 offload 正交。
  - **证据强度**：**强**——实验设定明确，但未测权重+KV 联合预算下的 trade-off。

- **假设 2（layer-wise offloading 为公平 baseline）**：与 HuggingFace / FlexGen / DeepSpeed 广泛采用的 per-layer swap + prefetch 对比，能代表 consumer TTC 的朴素实现。
  - **证据强度**：**中**——baseline 合理且可复现，但未与 FastTTS（同期 vLLM 系 TTC 加速）或专用 serving stack 对比。

## 核心方法

**Locality-Aware Beam Scheduling (LBS)** 将 step 内执行从「全 beam token-by-token 同步」改为 **beam-by-beam（按组）**：

1. **动态分组（#Beam / BeamSet）**：每 decoding step 查询 GPU runtime 剩余显存，决定每组可容纳 beam 数；贪心构造 BeamSet——从未分配 beam 出发，迭代加入与当前组 **KV block 交集最大** 的 beam，直至触及内存预算（Algorithm 1）。

2. **组内 inter-token 复用**：一组 beam 的 KV 一次性从 host 载入 GPU，组内按 beam 顺序完成该步全部 token，新生成 KV 写回 host 保持同步；组完成后再换下一组。分析模型显示 64 beam、step=128 时总传输从 baseline **53,012 GB** 降至 **540 GB** 量级（Figure 7）。

3. **Balanced grouping + prefetch**：单纯缩小组会增多 CUDA kernel launch 次数（每组独立 tensor layout），重复从 DRAM 加载权重。LBS 固定轮数 ⌈N/B⌉，将 beam **均分**到各轮（如 16 beam、容量 7 → [5,5,6] 而非 [7,7,2]），在执行组 i 时预取组 i+1 的 (B−|Gi|) 个 beam KV，overlap 传输与计算。I/O 占比从 **70–90%** 降至 **<15%**（Figure 11）。

Offloading 机制仍为 **per-layer**，与现有框架兼容；贡献在**执行顺序与分组策略**，非新 cache 数据结构。

## 设计取舍

- **取舍 1：贪心分组 vs 最优枚举**：指数级搜索不可行，贪心最大化 prefix overlap；可能牺牲全局最优 I/O，换取 O(beam²) 可接受开销。
- **取舍 2：Balanced grouping vs 最大组填充**：均分组略损单组内 locality，但腾出 prefetch 槽位；评估认为 prefetch 收益大于 locality 损失。
- **取舍 3：调度层优化 vs 框架重写**：不改 attention kernel 或 page 管理，依赖 layer-wise offload 基础设施；通用性强，但无法利用 [[PagedAttention]] 级细粒度页复用。
- **边界条件**：在 RTX 4090/3080 Ti、PCIe、7B 级模型、4–64 beam、step 32–128 设定下最有效；生产多请求 serving、[[Continuous-Batching]]、权重亦需 offload 时论文未覆盖。

## 实验与结果

**平台**：Intel i9-14900KF + RTX 4090 (24 GB) / RTX 3080 Ti (12 GB)，128 GB DDR4，PCIe Gen4 x8；prompt 128 token，生成 1920 token；beam width=2，beam size 2–32，step length 32/64/128。

**端到端加速（相对 layer-wise offloading）**
- OPT-6.7B：**3.39–9.72×**（beam 增大收益更明显）
- LLaMA-2-7B：**3.60–8.74×**
- Qwen-7B：**4.17–7.99×**
- RTX 3080 Ti：OPT-2.7B 最高 **6.85×**，Qwen-4B **3.52×**

**KV 传输量**：相对 baseline **>95%** 削减；仅 inter-token locality 即可压至 **<5%**（64 beam OPT：step 32/64/128 分别为 3.7%/1.8%/0.9%）；启用 inter-beam prefix reuse 再降 **>2×**（Figure 10）。

**Runtime 分解**：layer-wise I/O **70–90%** → LBS **<15%**；OPT-6.7B 64 beam 时 I/O 从 86% 降至 10%。Ablation：inter-token 单独可将 I/O 降至 baseline 的 **5–10%**；加 prefetch 与 inter-beam 后部分配置 **<2%**（Figure 12）。

**小 beam 区**：beam 较小时 KV 可全驻 GPU，各方法性能接近——与「瓶颈仅在 offload 触发后成立」一致。

## 批判性分析

### 论证链条

观察（TTC 下 KV 主导 + I/O stall）→ 设计（两类 locality + 分组调度 + balanced prefetch）→ 结果（传输 **>95%** 削减、**3–10×** E2E）链条**闭合良好**。分析模型（Eq. 1–5）与实测传输量趋势一致（Figure 7 vs 10），增强可信度。薄弱环节：**加速比高度依赖 beam 规模与是否触发 offload**——小 beam 无差异，论文主结论应理解为「宽 exploration + 内存压力」 regime，而非所有 TTC 场景 universal speedup。另外，调度不改变 token 选择语义这一 claim 依赖 step-wise beam search 的步内独立性，对语义分段 step（如 `\n\n` 边界）未单独验证。

### 假设压力测试

- **Workload**：固定长度生成（1920 token）、单请求；未测变长输出、多轮对话、或带 verifier/PRM 的完整 TTC pipeline（结论 section 承认为 future work）。
- **硬件**：consumer PCIe；Apple Silicon 统一内存、cloud L4、或 [[Disaggregation]] 多卡 setting 未测。权重常驻假设在 13B+ 或量化失败模型上可能不成立。
- **规模**：最多 64 beam；Snell et al. 显示 accuracy 可扩至 256 beam——更大 beam 下贪心分组质量与 kernel launch 开销未表征。
- **Baseline**：未与 **FastTTS**（同期、基于 vLLM 的 TTC 数据复用） head-to-head；若 vLLM 已有更强 prefix 共享，LBS 相对收益可能缩小。

### 实验可信度

- **Baseline 选取**：layer-wise offloading 是 consumer 推理常见路径，对比公平；in-GPU 在小 beam 作上界，大 beam OOM 符合预期。
- **Ablation**：inter-token、inter-beam、prefetch 三分解与 Figure 12 一致，支持设计因果叙述。
- **Metric 缺口**：主报 E2E latency 与 I/O 占比，**无任务 accuracy / pass@k**——调度不应改输出，但缺少显式 equivalence 检验（beam 搜索路径一致性）。无 tail latency、能耗、CPU 占用。理论 53,012 GB 与实测归一化趋势一致，但绝对值依赖模拟参数（7 GB KV budget 等），外推需谨慎。

### 系统性缺陷

- **Kernel launch 放大**：组数增加使每层 attention/FFN kernel 序列重复执行；论文用 balanced grouping 缓解，但未给 launch overhead 绝对毫秒或 P99 分解。
- **动态显存**：#Beam 依赖运行时 `get_budget()`，碎片化或 concurrent allocation 可能导致组大小抖动——论文未讨论稳定性。
- **与生产栈集成**：未嵌入 HuggingFace/vLLM 调度器；与 [[Prefix-Caching]]、[[PagedAttention]] block 级 dedup 的叠加关系未验证。
- **多租户 / 隔离**：单 batch 假设；论文未讨论。
- **正确性**：offload 时 host/GPU 双写同步；故障恢复、partial transfer 论文未讨论。

## 局限与后续工作

- **局限 1**：假设权重全驻 GPU；未联合优化权重与 KV 的 GPU 内存预算（与 PowerInfer、llama.cpp 正交但未实验组合）。
- **局限 2**：贪心 BeamSet 非最优；极高 beam 或低 prefix 重叠时收益上界未知。
- **局限 3**：实验限于 step-wise beam search 与 7B 级模型；完整 TTC（verifier、PRM、revision）pipeline 未评估。
- **Future work 1**（论文提出）：权重+KV 联合 offload 下的内存分配策略。
- **Future work 2**（论文提出）：将调度框架接入含 verifier/PRM 的端到端 TTC。
- **Future work 3**（可验证延伸）：与 FastTTS、[[PagedAttention]] prefix sharing 对比，在 128+ beam 与 13B+ 权重 offload 场景测量 net speedup；用 task metric 验证 beam 调度前后输出等价性。

## 相关

- **相关概念**：[[KV-Cache]]、[[Attention]]、[[Speculative-Decoding]]、[[Prefix-Caching]]
- **同类系统**：FlexGen、llama.cpp、DeepSpeed-Inference、FastTTS
- **同会议**：[[MLSys-2026]]
- **对比**：layer-wise KV offload（baseline）vs locality-aware 执行调度（LBS）vs datacenter 多卡 KV 分片（DistServe、Mooncake）
