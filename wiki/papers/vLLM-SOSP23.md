---
type: paper
name: vLLM
full_title: "Efficient Memory Management for Large Language Model Serving with PagedAttention"
authors: [Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph E. Gonzalez, Hao Zhang, Ion Stoica]
venue: SOSP
year: 2023
tags: [llm-serving, kv-cache, pagedattention, memory-management, continuous-batching]
source_pdf: "[[sosp23-kwon-pagedattention.pdf]]"
source_md: "[[sosp23-kwon-pagedattention]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Efficient Memory Management for Large Language Model Serving with PagedAttention (SOSP 2023)

> **一句话总结**：作者测量发现现有 LLM serving 系统仅 20–38% 的 [[KV-Cache]] 显存真正存 token state；据此用 OS 虚存分页思路提出 [[PagedAttention]]（非连续 block + block table + on-demand 分配 + copy-on-write 共享），并在其上构建 [[vLLM]]，在同等 normalized latency 下吞吐比 FasterTransformer/Orca 高 2–4×，长序列与 beam search 场景收益更大。

## 问题与动机

LLM 在线 serving 的核心矛盾是：**算力利用率低，但 GPU 显存先成为瓶颈**。自回归 [[Attention]] 的 decode 阶段每步只处理一个新 token，却要反复搬运整模型权重和不断增长的 [[KV-Cache]]，导致 GPU compute 严重 underutilized；提高吞吐的关键路径是 **batch 更多并发请求**。

然而 batch size 的上限几乎由 [[KV-Cache]] 决定，而不是权重。以 OPT-13B on A100-40GB 为例，权重约占 65%，[[KV-Cache]] 约占 30%，activation 只占很小比例；单请求单 token 的 KV 约 800 KB，max 2048 token 时单请求 KV 可达 1.6 GB。更糟的是，KV 随生成动态增长，输入/输出长度事先未知，生命周期也不固定——这与传统 DNN 中形状静态的 tensor 完全不同。

现有系统（FasterTransformer、[[Orca-OSDI22|Orca]] 一类实现）受 DL framework 连续内存假设约束，为每个请求 **按 max_seq_len 预分配连续 KV chunk**。这带来三类浪费（论文 Fig. 3）：为未来 token 预留的 reserved space、实际长度远小于上限的内部碎片、以及 buddy allocator 造成的外部碎片。论文在 §6.2 实验中量化：FasterTransformer 与自实现 Orca 只有 **20.4%–38.2%** 的 KV 显存真正用于存 token state（Fig. 2）。

第二个被忽视的点是 **解码算法带来的共享机会**。parallel sampling、beam search、shared system prompt 等场景下，多条序列共享大段 prefix KV，但连续内存方案无法表达 block 级共享，只能各自复制或频繁整块拷贝。论文 claim：在 beam search 中，共享可节省 37.6%–55.2% 的 KV block（Alpaca trace，§6.3）。

因此论文要解决的问题不是「把 attention 算得更快」，而是：**在 iteration-level batching 已经存在的 serving 栈上，把 KV 管理从连续预分配改成可共享、可增长、碎片可控的内存系统**，从而让更多请求同时 fit in GPU memory。

## 关键观察 / 隐含假设

- **观察 1：KV cache 是 serving 的主导内存瓶颈，且利用率极低。** 在 A100 上跑 13B 模型时，KV 占可用 serving 内存的大头；现有系统实测有效利用率仅 20.4%–38.2%。
  - **依赖假设**：workload 是典型 chat/completion 式 autoregressive serving，batch 提升能带来端到端吞吐增益，而不是被 prefill compute 或网络 I/O 主导。
  - **可能失效场景**：极短序列、KV 预算本就充裕时（论文在 OPT-175B + Alpaca 短序列上观察到系统转为 compute-bound，vLLM 相对 Orca Oracle 优势缩小）；或 prefill-heavy、多模态、MoE 等让非 KV 内存/算力先成为瓶颈的场景。
- **观察 2：KV 的生命周期与长度不可预知，使「连续预分配」在结构上就低效。** 输出长度取决于模型采样结果，请求到达时无法知道最终 seq len；按 max length 预留会在整个请求生命周期内占住内存。
  - **依赖假设**：用户/服务商会设置 max_seq_len 或 model context limit，系统按上限做 worst-case reservation；真实 trace（ShareGPT、Alpaca）中输入/输出长度分布高度偏斜（Fig. 11）。
  - **可能失效场景**：若服务允许动态扩展 context 且频繁触顶 max len，on-demand 分配优势会减弱；若所有请求都接近满长生成，内部碎片上界虽仍为一个 block，但 batch 压力依旧很大。
- **观察 3：compute–memory 剪刀差在加剧，memory 瓶颈会长期存在。** 论文引用 A100→H100 FLOPS 增长超过 2× 而 HBM 仍约 80GB 的上限，认为 KV memory pressure 会越来越大。
  - **依赖假设**：未来 serving 优化仍主要在单卡/单节点 HBM 预算内竞争 batch size，而不是被大规模 [[Disaggregation]]、极致 [[Quantization]] 或专用 KV tier 完全改写。
  - **可能失效场景**：权重/KV 大规模 offload、CXL/SSD KV tier、或 context 压缩使「有效 KV 字节数」大幅下降时，分页管理的边际价值会缩小。
- **观察 4：复杂解码算法存在大量可共享 prefix，但只在 block 粒度才易表达。** parallel sampling 可共享 prompt KV（Alpaca 上约 6–10% block 节省）；beam search 共享模式动态变化，类似 OS fork tree，最多可省 55% block。
  - **依赖假设**：生产流量确实使用 multi-sample / beam / few-shot prefix 等工作负载，而非纯 greedy single-sample。
  - **可能失效场景**：若线上几乎全是单样本 greedy decoding，共享收益接近 0，vLLM 的主要优势退化为碎片消除。
- **假设 1：为支持非连续 KV 付出的 attention kernel 额外开销可被更大 batch 抵消。** PagedAttention kernel 比 FasterTransformer 慢 20–26%（§7.1），但端到端吞吐仍显著更高。
  - **证据强度**：强。微基准与端到端实验一致，且 ablation 说明瓶颈在 memory capacity 而非单 kernel FLOPs。
- **假设 2：centralized block manager + per-iteration block table 广播，在 tensor-parallel serving 中足够。** 各 GPU worker 存不同 attention head 的 KV shard，但共享同一套 logical→physical 映射。
  - **证据强度**：中。论文在 OPT-66B/175B 多卡上验证，但未深入讨论 scheduler 单点、控制面延迟或超大规模集群下的扩展性。

## 核心方法

### PagedAttention：在非连续物理内存上做 exact attention

[[PagedAttention]] 把每条序列的 KV 切成固定 token 数的 **KV block**（默认 block size = 16）。逻辑上序列仍是连续 token 流，但物理上每个逻辑 block 通过 **block table** 映射到任意 physical block——类比 OS 的 virtual page → physical page。

Attention 计算相应改为 block-wise：query 与每个 key block 做点积得到局部 attention score，再对 value block 加权聚合（Eq. 4）。CUDA kernel 在迭代时按 block table 间接寻址读取 KV，因此 **不要求物理连续**，也不改变 attention 数学语义（无近似、无压缩）。

### KV Cache Manager：虚存式按需分配

[[vLLM]] 的 block engine 在 GPU（及 CPU swap 区）上预先划分等大 physical block pool，但 **不为整条序列预留 max length**。prefill 只为 prompt 所需 logical block 分配 physical block；decode 每填满一个 logical block 才分配新 physical block。单请求浪费上界被限制在 **最后一个未满 block**，从而把 Fig. 2 中的有效利用率推到接近 100%。

logical/physical 分离还使 **copy-on-write 共享** 自然成立：多个 logical block 可映射到同一 physical block，physical block 维护 ref count；当某序列要写入共享 block 时，分配新 physical block 并拷贝（parallel sampling §4.4）。beam search 中候选合并/淘汰时动态调整映射，避免 Orca 式频繁大块 KV 拷贝（§4.4, Fig. 9）。

### 与 iteration-level scheduling 协同

vLLM 采用与 [[Orca-OSDI22|Orca]] 同类的 **[[Continuous-Batching]]**：每个 decode iteration 重新组 batch，完成请求退出、新请求加入，避免 request-level padding。论文强调：**Orca 解决的是时间维 interleaving，PagedAttention 解决的是空间维 memory utilization**；二者互补，但细粒度调度也让内存管理更难，因此更需要分页式 KV。

调度策略为 FCFS；显存不足时对 **sequence group**（同一请求下的多条 beam/sample 序列）做 gang preemption。驱逐策略是 all-or-nothing：整条序列的 blocks 一起换出，利用「attention 需要完整历史 KV」这一语义。恢复支持两条路径：**swapping** 到 CPU DRAM，或 **recomputation**（把已生成 token 拼回 prompt 一次性重算 KV）。小 block size 时 recomputation 更优，大 block 时 swapping 更优（§7.3）。

### 多解码算法与分布式执行

通过 `fork` / `append` / `free` 三类原语统一 parallel sampling、beam search、shared prefix caching（§5.2）。shared system prompt 可预加载为常驻 physical block，用户请求直接映射（类似 shared library）。

分布式场景采用 Megatron 式 [[Tensor-Parallelism]]：attention 按 head 切分，各 worker 存部分 head 的 KV，但 **scheduler 侧单一 KV cache manager** 维护全局 block table，每 iteration 广播 token IDs + block table 给 workers（§4.6）。

### Kernel 层实现

针对 block table 间接访问，论文实现 fused reshape+block write、fused block read+attention、batched block copy 等 CUDA kernel（§5.1），在 FasterTransformer attention kernel 基础上改造以支持变长 batch 与非连续 KV。

## 设计取舍

- **用间接寻址换内存效率**：block table lookup + 非连续访存使 attention kernel 慢 20–26%，但换来 2–4× 端到端吞吐；这是典型的 memory-bound workload 取舍。
- **固定 block size 的统一池化**：消除外部碎片，但引入最后一个 block 的内部碎片，并影响 GPU 并行度与共享概率。默认 16 token/block 是碎片与并行度的折中（§7.2）；Alpaca 短序列上对过大 block 敏感。
- **Copy-on-write 而非 eager sharing**：共享只在写冲突时复制一个 block，避免 beam/search 中大规模 eager copy；代价是 ref count 管理与 COW 路径的实现复杂度。
- **All-or-nothing preemption + FCFS**：实现简单且符合 attention 访问模式，但可能不如更细粒度 page replacement 灵活；且 swapping 时会 **暂停接收新请求**（§4.5），影响 overload 下的尾延迟与可用性。
- **Centralized scheduler**：简化分布式 KV 映射一致性，但控制面可能成为 scale-out 瓶颈；论文未讨论多副本 scheduler 或去中心化 block allocation。
- **放弃 compaction**：论文认为 KV 体量太大，在线 compaction 不现实；依赖分页而非搬移整理碎片。

## 实验与结果

- **主结果**：在 ShareGPT / Alpaca 合成 trace、OPT-13B/66B/175B 与 LLaMA-13B 上，vLLM 在相似 normalized latency（端到端延迟 / 输出 token 数）下，吞吐比 FasterTransformer 与 Orca 高 **2–4×**；长序列、大模型、复杂解码收益更大（Abstract, §6）。
- **ShareGPT 饱和请求率**：相对 Orca (Oracle) 可维持 **1.7–2.7×** 更高 request rate，相对 Orca (Max) **2.7–8×**；相对 FasterTransformer 最高 **22×**（§6.2）。
- **batch 深度**：OPT-13B ShareGPT 下，vLLM 同时处理请求数为 Orca (Oracle) 的 **2.2×**、Orca (Max) 的 **4.3×**（Fig. 13）。
- **parallel sampling / beam search**：OPT-13B Alpaca 上，beam width 6 时相对 Orca (Oracle) 从 basic sampling 的 1.3× 提升到 **2.3×**；KV block 节省 parallel sampling **6.1%–9.8%**、beam search **37.6%–55.2%**（§6.3, Fig. 15）。
- **shared prefix**：LLaMA-13B 翻译任务，共享 1-shot prefix 吞吐 **1.67×** Orca (Oracle)，5-shot prefix **3.58×**（§6.4）。
- **chatbot 工作负载**：截断到 1024 prompt + 1024 output，vLLM 可维持 **2×** 于 Orca 各变体的 request rate；但实验 **不在对话轮次间保留 KV**（§6.5）。
- **kernel ablation**：PagedAttention attention kernel 比 FasterTransformer 慢 **20–26%**（Fig. 18a）；block size 16–128 在 ShareGPT 上较优，Alpaca 偏向 16–32（§7.2）。
- **正确性**：论文声明不影响 model accuracy，但实验 **不报告质量指标**，只评估吞吐/延迟。

## Critical Analysis

### 论证链条

论文链条清晰且闭合度高：**测量 KV 低利用率（Fig. 2）→ 归因于连续预分配与无法共享（§3）→ 用 OS 分页类比设计 PagedAttention + block manager（§4）→ 更大 batch（Fig. 13）→ 更高吞吐（Fig. 12）**。共享机制与 parallel/beam/prefix 实验（§6.3–6.4）直接支撑「block 级共享」这一独立贡献，而非仅碎片优化。

较弱的一环是 **与 Orca 的对比边界**：Orca 未开源，论文使用自实现 Orca + buddy allocator，并额外提供 Oracle/Pow2/Max 三档 reservation 假设。Orca (Oracle) 已知真实输出长度，属于不可达上界，但 vLLM 仍常能超出 1.7–2.7×，说明收益不仅来自「更准的 reservation」。不过，真实 Orca 的工程细节（调度、kernel、内存池）若有差异，结论幅度可能变化——读者应把 2–4× 看作「对论文所建模 Orca 的优势」，而非对某一固定二进制产品的保证。

另一跳步是 **从单卡 A100 实验外推到“LLM serving 普遍瓶颈”**：论文对 OPT/GPT/LLaMA 家族有代表性，但未覆盖当时已出现的更长 context、多模态、encoder-decoder 或大规模 PD 分离部署；§8 也承认分页并非对所有 GPU workload 适用。

### 假设压力测试

- **短序列 / KV 充裕**：OPT-175B + Alpaca 上，Orca (Oracle/Pow2) 也能批很多请求，vLLM 优势缩小甚至接近——说明 PagedAttention 的收益与「memory-bound 程度」强相关；不能默认在所有配置下都有数倍提升。
- **负载形态**：若线上主要是单样本 greedy、短 prompt，共享与 COW 价值有限，核心收益只剩碎片消除；此时与更简单 pool allocator 的差距可能缩小。
- **overload 行为**：swapping 时停止接新请求、FCFS gang preemption，在突发流量下可能造成 **队列堆积与尾延迟恶化**；论文用 normalized latency 评估饱和点，但对 P99 TTFT/TPOT、SLO 违约率讨论很少。
- **多轮对话**：chatbot 实验刻意不在轮次间缓存 KV，回避了「长会话占用 block pool」对多租户公平性的影响；这与真实 chat 产品差距较大，也限制了实验对 prefix caching 的结论外推。
- **硬件演进**：若 KV 大量迁到 CPU/CXL/远端（后续 [[LMCache-arXiv25]]、[[Disaggregation]] 路线），单卡 block pool 优化的相对重要性会下降，但 block 抽象本身可能仍有用。

### 实验可信度

- **Workload**：ShareGPT / Alpaca 长度分布有真实文本来源，但到达过程用 Poisson 合成，缺少生产级 multi-tenant、优先级、混部解码策略等特征；对「共享 prefix」的 WMT 翻译实验更有针对性，但规模小于主实验。
- **Baseline 公平性**：FasterTransformer 使用自建 dynamic batching scheduler，而非完整 Triton/Orca 产品栈；Orca 为作者复现。两者都与 vLLM 共享 iteration-level batching 思想，比较重点较集中在 **内存管理**，这是公平且刻意的，但不覆盖「完整生产 serving 栈」差距。
- **Ablation**：block size、swapping vs recomputation、kernel microbenchmark 较完整，能支撑「kernel 更慢但系统更快」「block size 16 合理」等设计判断。
- **缺失面**：无 cost-per-token、无 energy、无 multi-tenant isolation、无 failure/recovery、无 quality regression；正确性仅逻辑论证「exact attention」。

### 系统性缺陷

- **尾延迟与 SLO**：论文未系统评估 P99/P999 或 prefill-decode 分离场景；preemption 暂停接新请求对在线服务是显著运维风险。
- **控制面单点**：centralized scheduler + 每 iteration 广播 block table，在超大集群、极高 QPS 下的延迟与容错 **论文未讨论**。
- **可观测性 / 调试**：block table、COW、ref count 使内存状态更难直观排查；论文未提供 ops 视角。
- **与 [[Flash-Attention]] 的关系**：prefill 仍可用常规 attention，decode 用 PagedAttention；后续工程上如何与 IO-aware kernel 深度融合，当时尚未展开（后序工作已大量探索）。
- **兼容性成本**：需要 custom CUDA kernel 与非连续 KV 布局，模型/框架接入成本高于「连续 tensor + 现成 kernel」；论文以 8.5K Python + 2K C++/CUDA 实现，但长期维护负担显著。

## 局限与 Future Work

- **局限 1**：overload 下 swapping 会暂停接收新请求，且 preemption 策略较粗（FCFS + all-or-nothing），对延迟敏感服务可能不够友好。
- **局限 2**：chatbot 实验不跨轮缓存 KV，未回答真实多轮对话场景下的 memory–latency 权衡。
- **局限 3**：Orca 为复现 baseline，结论幅度依赖 reservation 模型假设；未与当时所有商业/开源 serving 栈逐项对齐。
- **Future work 1**：在真实生产 trace 上测量「memory-bound 比例」与 PagedAttention 边际收益，按 workload 分类给出 block size / swapping / recomputation 的自适应策略。
- **Future work 2**：将 block 级 KV 抽象与跨机 KV tier、[[Prefix-Caching]] / [[RadixAttention]]、[[Disaggregation]] 结合，验证分页语义在分布式 KV 池中的可扩展性与一致性。
- **Future work 3**：量化 preemption、COW、block table 广播对 **P99 尾延迟** 的影响，并设计不暂停入队的 backpressure 机制。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Prefix-Caching]]、[[Attention]]、[[Tensor-Parallelism]]
- **系统实体**：[[vLLM]]
- **同类系统**：[[Orca-OSDI22]]、[[SGLang-NeurIPS24]]（[[RadixAttention]]）、FasterTransformer
- **相关内核**：[[FlashAttention-NeurIPS22]]、[[Flash-Attention]]
- **后续方向**：[[DiffKV-SOSP25]]、[[LMCache-arXiv25]]、[[CacheBlend-EuroSys25]]、[[FlexiCache-MLSys26]]
- **同会议**：[[SOSP-2023]]
