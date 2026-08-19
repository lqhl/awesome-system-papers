---
type: paper
name: CacheSlide
full_title: "CacheSlide: Unlocking Cross Position-Aware KV Cache Reuse for Accelerating LLM Serving"
authors: [Yang Liu, Yunfei Gu, Liqiang Zhang, Chentao Wu, Guangtao Xue, et al.]
venue: FAST
year: 2026
tags: [llm-serving, kv-cache, agent, positional-encoding, vllm, area/agent-systems]
source_pdf: "[[fast2026-liu-yang.pdf]]"
source_md: "[[fast2026-liu-yang]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# CacheSlide：解锁交叉位置感知 KV 缓存重用以加速 LLM 服务（FAST 2026）

> **原题**：CacheSlide: Unlocking Cross Position-Aware KV Cache Reuse for Accelerating LLM Serving

> **一句话总结**：Agent prompt 中可复用片段保持相对顺序但绝对位置随 updated 段漂移；论文定义 RPDC 范式，用 CoPE 预训练的 CCPE 压低 PMKD、用 Weighted Correction Attention 只重算约 26% token 恢复 cross-attention，并用 SLIDE 打破 [[vLLM]] 层内 load-write 锁与 dirty-page spill 瓶颈，在 Reflexion/MemGPT/SWE-Agent 上实现 3.11–4.3× 延迟降低、3.5–5.8× 吞吐提升，精度几乎无损。

## 问题与动机

[[LLM]] 已广泛进入 agent 场景：MemGPT、Reflexion、SWE-Agent、AutoGen 等系统把 prompt 拆成 **system prompt（静态前缀）+ updated prompt（每轮变化）+ fixed prompt（历史/记忆，静态后缀）**。每轮推理即使大部分文本不变，[[KV-Cache]] 仍要从头 prefill，而 prefill 成本随 context 长度线性增长，直接推高 TTFT 和资源消耗。

已有 [[KV-Cache]] 复用分两类。**Position-Dependent Caching (PDC)**——ContextCache、PromptCache——只允许在固定绝对位置复用；updated 段长度一变，后续 fixed 段绝对位置就漂移，prefix-only 复用失效。强行把 fixed/updated 段重排会破坏 agent 语义：MemGPT 把最近 memory 放头部以获得更多 [[Attention]]（lost-in-the-middle 效应）；SWE-Agent 的 updated slot 与 immutable slot 存在数据依赖，不能交换顺序。PromptCache 虽能为每段预计算 KV，但不恢复段间 cross-attention，还需为不同绝对位置维护多份 cache，存储开销大。

**Position-Independent Caching (PIC)**——[[CacheBlend-EuroSys25]]、EPIC——把复用段位置全部从 0 编码，引入 **Positionally Misaligned KV Drift (PMKD)**：[[RoPE]] 对每个 token 分配唯一位置，绝对位移 1000 token 时 cached/recomputed KV 的 CKSim 余弦相似度跌 > 90%。为恢复精度，PIC 在 prefill 预选 token 子集重算，但 multi-head [[Attention]] 各 head 关注不同 token，哪些 token 真正影响输出要到 decode 才显现，prefill 预选无法保证稳定精度。系统层上，[[vLLM]]/[[SGLang]] 同层 KV load 与 write 串行（load-before-write lock），PIC 的 partial update 在 spill 到 SSD 时触发 LRU 误择和随机写，写放大严重。

Window padding（强制 updated 段定长以固定后续段位置）是另一种思路，但会丢失关键信息：MemGPT 上 working window=1K/2K/3K 时 F1 相对 baseline 降 > 78.1%。真实 agent 输入的 updated 段 token 数波动大且不可预测。论文因此提出介于 PDC 与 PIC 之间的 **Relative-Position-Dependent Caching (RPDC)**。

## 关键观察 / 隐含假设

- **观察 1：Agent prompt 中大量 KV 可复用，且复用段保持相对顺序、绝对位置漂移。** GitHub agent 日志与 MemGPT/SWE-Agent 模板分析显示，输入中可复用 KV 占比高且方差大；典型结构是 system + updated + fixed history，updated 段长度变化使 fixed 段起始绝对位置从 (101, 401) 漂到 (251, 451)，但 fixed 段之间相对顺序不变。
  - **依赖假设**：部署 workload 是单任务、多轮交互模式（同一用户/同一问题的连续推理），prompt 模板稳定，reuse/fixed 段边界可由模板预先标注。
  - **可能失效场景**：多租户混部、动态 prompt 拼装、无固定模板的多 agent 编排、跨任务 KV 共享时，chunk 角色划分和 hash 命中都会变脆。

- **观察 2：PMKD 是位置编码敏感性问题，低敏感编码可大幅缓解。** 用 CKSim 度量同一文本段在不同 prefix 长度下的 KV 相似度：RoPE 在 shift 0–1000 token 时 CKSim 跌 > 90%；CoPE（语义边界索引，相邻 token 可共享 position）仅跌 28%，且 ∆pos 映射斜率更平缓。
  - **依赖假设**：目标任务上 CoPE 经 task-specific 预训练后，cached 与 real position 的偏差足够小，使 fixed 段内/段间 attention 可近无损复用。
  - **可能失效场景**：未做 CoPE 适配的模型、跨任务泛化、极长 context 下边界模式漂移，CCPE 学到的 encoding pattern 可能失效。论文用 LoRA adapter 做 CoPE 支持，baseline 仍用原生 RoPE/ALiBi，存在公平性争议空间。

- **观察 3：跨层 KV 相似度递增，只需在 layer 1 选 top-k 高偏差 token 并在深层加权融合即可恢复 cross-attention。** 对 fixed 与 updated 段交界处的 attention，论文假设约 26% token（top-k 比例）+ CKSim 阈值 τ≈0.12 足以恢复质量；每 4 层用 CKSim gating 动态替换已收敛 token。
  - **依赖假设**：[[Attention]] 稀疏性成立，fixed↔updated 的 cross-attention 依赖集中在少数高 KV deviation token；层间表示平滑，layer 1 选的 token 在深层仍需要修正。
  - **可能失效场景**：dense reasoning、工具返回的大段结构化输出、多 updated slot 交错时，26% 固定比例可能不够；论文未给 per-request adaptive ratio 或 correctness fallback。

- **观察 4：PIC 类 partial KV update 的系统瓶颈是层内 I/O 与 spill 写放大，而非纯 compute。** [[vLLM]] 0.8.5 上同层 load-before-write 使 recompute 与 load 无法 overlap；KV spill 时 LRU 可能驱逐含 selected token 的 dirty page，导致碎片化随机写。
  - **依赖假设**：实验硬件（A100 80GB、500GB DRAM、2TB NVMe、PCIe Gen4）能代表 production spill 场景；batch/beam 增大时 storage pressure 是主要尾延迟来源。
  - **证据强度**：中。ablation 显示 LWD 降 layer-wise 等待 26.7–51.5%，dirty-page eviction 降 write stall 66.9–73.5%，WAF 降 3.11–3.62×，但缺少 P99 与多节点 trace。

- **假设 1**：Agent 设计者不会为最大化 KV 复用而牺牲 prompt 语义与 attention 布局。
  - **证据强度**：强。论文用 MemGPT/SWE-Agent 真实模板论证重排不可行，这是 RPDC 存在的核心前提。

## 核心方法

CacheSlide 在 [[vLLM]] 0.8.5 上实现 RPDC，由 CCPE、Weighted Correction Attention、SLIDE 三部分组成。

**Chunked Contextual Position Encoding (CCPE)** 回应观察 1–2。按 agent 模板把 prompt 切成 reuse chunk 与 recompute chunk；对 reuse chunk 在 task-specific 预训练阶段用 CoPE 编码并统计最高频 encoding pattern e*，prefill 时为 reuse chunk 分配 e* 对应的固定 position range，使 cached 与 real position 的 ∆pos 最小化，最大化 CKSim。未命中 hash 的 reuse chunk 用 e* 做首次 prefill 并入库。recompute chunk 仍按当前输入的 CoPE 实时编码。这不同于 [[Prefix-Caching]] 的严格前缀约束，也不同于 PIC 的全零位置重置。

**Weighted Correction Attention (WCA)** 回应观察 3。CCPE 对齐后，fixed 段内/段间 attention 可近无损复用；剩余问题是 fixed↔updated 的 cross-attention。Layer 1 对全 prompt 重算 KV，按 ∥K_recompute − K_reuse∥² 选 top-k（默认 26%）token 集合 S_k；layer 2–L 只对 S_k 重算并与 cached KV 做 deviation-aware 加权融合 K ← α·K_recompute + (1−α)·K_reuse。每 4 层检查 CKSim，低于 τ=0.12 的 token 从 S_k 移除并补入下一个最大偏差 token。相比 [[CacheBlend-EuroSys25]] 的固定 18% 浅层重算，WCA 多了跨层 gating 与显式融合权重；相比 EPIC 的每 block 64 个边界 token，WCA 是全局比例选择。

**SLIDE**（Spill-aware, Load–write decoupling Intra-layer, Dirty-page Eviction）回应观察 4 与 PIC 系统缺陷。Prefill 时在 layer i 并行启动 KV load 与 selected-token recompute；若 recompute 先完成，把选中 token 写到新分配 page（通过 [[PagedAttention]] `append_slot`/`promote`），打破 load-before-write 锁。Layer 2 起按 page 是否含 selected token 标记 dirty/clean，维护 per-page selected-token 计数。Spill 时先驱逐 clean page，再按 selected-token 数降序驱逐 dirty page 并做 write coalescing，降低 WAF 与 prefill 尾延迟。Decode 阶段优先覆写含 selected token 的原 slot，再分配新 page。

端到端流程：CCPE 分块并 hash 查找 reuse KV → WCA prefill 恢复 cross-attention → SLIDE 并行 I/O 与 spill 管理 → decode 覆写压缩 footprint。

## 设计取舍

- **用 CoPE 预训练换位置鲁棒性**：为 RPDC 引入 LoRA-based CoPE adapter，baseline 仍用原生 RoPE/ALiBi。收益是 PMKD 可控；代价是每类 agent 任务需预训练 encoding pattern，且 CoPE 与原生 PE 的双栈切换增加部署复杂度。论文未讨论与已有 production 模型权重的兼容性边界。

- **用固定 top-k/τ 换实现简单**：26%/0.12 来自 QPS heatmap 峰值，但写死为全局超参。收益是调参成本低、行为可预测；代价是不同模型深度、不同 agent 更新幅度下可能需要 per-workload tuning，缺少请求级 risk-aware fallback 到 full recompute。

- **用模板驱动分块换自动化**：reuse/recompute chunk 由 agent prompt template 标注，不是运行时自动发现。收益是精度高、hash 稳定；代价是每接入新 agent 需人工定义 chunk 边界，通用性弱于纯内容 hash 的 [[LMCache-arXiv25]] 式方案。

- **用额外 page 与 dirty 跟踪换 I/O overlap**：SLIDE 为 selected token 预分配 promoted page，decode 再覆写。收益是层内并行与 spill 友好；代价是短期 VRAM 峰值上升，block table/slot_mapping 管理更复杂。论文报告相对 PromptCache VRAM 仍降 1.63–1.9×，因只存每 fixed 段一份 KV。

- **边界条件**：单任务、多轮、模板稳定、batch/beam 带来 spill 时 CacheSlide 优势最大；一次性短 prompt、无 fixed 段、或 KV 全在 GPU 无 spill 时，收益主要来自 WCA 计算节省，SLIDE 价值下降。

## 实验与结果

- **设置**：基于 [[vLLM]] 0.8.5；单 A100 80GB（70B 用 2×A100）；500GB DRAM、2TB NVMe SSD。模型：Mistral-7B、MPT-30B、Llama-3 70B（CoPE 经 LoRA adapter）。Agent：Reflexion（HotPotQA）、MemGPT（Multi-Session Chat）、SWE-Agent（SWE-Agent-Bench）。指标：TTFT、Rouge-L、Success Rate、F1、QPS。
- **相对 ContextCache (PDC)**：TTFT 降 2.4–3.3×，精度几乎无损；ContextCache 只能复用 system prompt 前缀。
- **相对 [[CacheBlend-EuroSys25]] (PIC)**：TTFT 再降 1.21–2.11×，accuracy 提升 1.97–2.28×；CacheBlend 不缓存 fixed 段间 attention，且无 SLIDE。
- **相对 PromptCache (PDC)**：TTFT 降 1.12–2.45×，accuracy 提升 1.41–3.95×；PromptCache 存储开销大且忽略 cross-attention。
- **并行/beam**：batch 2→6 时相对最佳 baseline TTFT 优势从 1.2× 到 2.3×；beam width 2→6 时 1.1× 到 2.1×。PromptCache spill 最重，CacheBlend 次之，CacheSlide 最稳。
- **SLIDE ablation**：LWD 降 layer-wise 并行等待 26.7–51.5%（batch 2–6）；dirty-page eviction 降 write stall 66.9–73.5%（batch 4–16）；SSD WAF 降 3.11–3.62×；VRAM 相对 PromptCache 降 1.71× 平均。
- **吞吐稳定性**：batch=8 时相对 CacheBlend/EPIC 吞吐高 49.6–82.2%，吞吐标准差 σ 降 58.6–77.4%。
- **论文总结数字**：端到端延迟降 3.11–4.3×，吞吐升 3.5–5.8×，accuracy loss negligible。

## 批判性分析

### 论证链条

主链条清晰：agent prompt 有可复用 fixed 段且相对顺序固定 → PDC 因绝对位置刚性失效、PIC 因 PMKD 损精度 → RPDC 保持相对顺序并最小化位置偏差 → CCPE 压低 PMKD → 只需恢复 fixed↔updated cross-attention → WCA 稀疏重算+融合 → PIC 式 partial update 带来系统 stall → SLIDE 解耦 I/O 与 dirty spill。Figure 10 Pareto 前沿支撑「更快且更准」的 claim。

最脆的跳步是 **CoPE adapter 是否公平地扩展了方法能力而非只改模型行为**。CacheSlide 开 CoPE、baseline 关 CoPE，accuracy 对比混入了 PE 变更因素；尽管作者论证 CCPE 主要服务于 reuse 对齐，仍需 ablation「同 PE 下的 RPDC+WCA」来分离系统创新与编码变更。

### 假设压力测试

**模板依赖**：RPDC 要求预先知道哪些 chunk reuse。对 AutoGen 式动态拼装、RAG 检索段插入、或用户自定义 system prompt 频繁变更的场景，chunk 角色划分成本可能抵消 reuse 收益。论文未与纯 content-hash 的 [[LMCache-arXiv25]] 或 [[CacheBlend-EuroSys25]] 在无模板场景对比。

**固定 26%/0.12**：在 SWE-Agent 多 updated slot、长工具输出、或 thinking model 长 chain 上，cross-attention 可能更分散。论文 QPS heatmap 覆盖 Mistral-7B 与 Llama-70B 两点，未展示失败 case 或 per-task 最优 ratio 方差。

**单节点 A100**：未测 [[Disaggregation]]、多 GPU KV 迁移、跨请求 cache 共享、多租户隔离。SLIDE 的 dirty-page 策略在分布式 KV store 上如何映射，论文未讨论。

**已证明 vs 推断**：CKSim/PMKD 测量在 MemGPT+ShareGPT 上完成 — **已证明**位置编码敏感性差异；3.11–4.3× 延迟在三个 agent benchmark 上 — **已证明**特定设置下的平均收益；production agent trace 上的 hit rate 与尾延迟 — **未覆盖**，需推断。

### 实验可信度

Baseline 选择合理且实现来源明确（Kimi Context Caching、OpenAI Prompt Caching、[[LMCache-arXiv25]] for CacheBlend/EPIC）。batch size=1、无 beam 的主实验对 TTFT 公平；并行/beam 实验单独展示 SLIDE 价值，设计连贯。

弱点包括：(1) 数据集规模偏小（HotPotQA 子集、10k 对话、12-repo SWE bench）；(2) 质量指标 F1/Rouge-L/Success Rate 不能证明 agent 任务的功能正确性（如 SWE patch 是否真能通过 CI）；(3) 缺少 P95/P99 TTFT、per-turn breakdown、cache hit rate 分布；(4) CoPE-on vs RoPE-off 的混淆；(5) 未与最新 [[SGLang]] radix/cache 或 vendor Prompt Caching API 的生产配置对比。

### 系统性缺陷

- **引擎侵入**：修改 [[PagedAttention]] init、block table、slot_mapping、layer-wise promote/overwrite，与 [[Continuous-Batching]]、[[Chunked-Prefill]]、speculative decode 的交互论文未讨论。
- **正确性边界**：无 bitwise 等价保证；KV 与 model version、tokenizer、CoPE adapter、chunk 边界强绑定，失效策略论文未写清。
- **可观测性/运维**：dirty page 计数、spill 决策、WCA token 选择缺少 operator-facing 接口；故障时如何 fallback 到 full precompute 未说明。
- **尾延迟**：报告均值与 σ 改善，但无 P99；高 batch spill 场景下 SSD 抖动可能仍主导。
- **隐私/隔离**：跨用户复用 fixed 段 KV 的权限与泄漏风险论文未讨论。

## 局限与后续工作

- **局限 1**：依赖 agent 模板标注 chunk 角色，接入新 agent 需人工配置，通用性弱于 position-agnostic 方案。
- **局限 2**：CoPE adapter 预训练按任务类型进行，跨任务迁移与多任务混部行为未充分评估。
- **局限 3**：实验限于单节点 [[vLLM]] 0.8.5 + A100，未覆盖分布式 serving、[[Disaggregation]]、更新版 engine。
- **局限 4**：WCA 超参全局固定，缺少请求级自适应 recompute 与质量 guardrail。
- **Future work 1**：在真实 production agent trace 上测量 chunk reuse 分布、PMKD 实测、P99 TTFT，验证 RPDC 经济性边界。
- **Future work 2**：请求级 adaptive top-k/τ，结合 online CKSim 监控，在偏差超阈值时自动 fallback full prefill。
- **Future work 3**：将 SLIDE 的 load-write decoupling 与 dirty-aware spill 推广到 [[LMCache-arXiv25]] 式多级/跨节点 KV store。
- **Future work 4**：同 PE 公平 ablation，分离 CCPE 编码收益与 WCA+SLIDE 系统收益；覆盖 thinking model、多模态 agent 等更长 updated 段 workload。

## 相关

- **相关概念**：[[KV-Cache]]、[[Prefix-Caching]]、[[PagedAttention]]、[[Attention]]、[[Sparse-Attention]]、[[LoRA]]、[[Chunked-Prefill]]
- **同类系统**：[[vLLM]]、[[SGLang]]、[[CacheBlend-EuroSys25]]、[[LMCache-arXiv25]]、EPIC、PromptCache、ContextCache
- **Agent 场景**：MemGPT、Reflexion、SWE-Agent
- **同会议**：[[FAST-2026]]
- **对比**：相对 [[CacheBlend-EuroSys25]] 面向 RAG 多 chunk PIC，CacheSlide 面向 agent 多段 RPDC；相对 [[Prefix-Caching]] 解锁非前缀 fixed 段复用
