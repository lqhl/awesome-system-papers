---
type: paper
name: KVCacheInTheWild
full_title: "KVCache Cache in the Wild: Characterizing and Optimizing KVCache Cache at a Large Cloud Provider"
authors: [Jiahao Wang, Jinbo Han, Xingda Wei, Sijie Shen, Dingyan Zhang, Chenguang Fang, Rong Chen, Wenyuan Yu, Haibo Chen]
venue: ATC
year: 2025
tags: [llm-serving, kv-cache, prefix-caching, workload-characterization, cache-eviction, production-traces, area/ai-infra]
source_pdf: "[[atc2025-wang-jiahao.pdf]]"
source_md: "[[atc2025-wang-jiahao]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# KVCacheInTheWild：KVCache 缓存实际应用：在大型云提供商处表征和优化 KVCache 缓存（ATC 2025）

> **原题**：KVCache Cache in the Wild: Characterizing and Optimizing KVCache Cache at a Large Cloud Provider

> **一句话总结**：阿里通义一周生产 trace 显示真实 [[KV-Cache]] 复用率（ideal hit 54%–62%）低于合成 workload、single-turn API 与 ephemeral lifespan 主导设计空间；据此提出的 workload-aware 指数分布淘汰策略在 [[vLLM]] 上比 LRU 等 baseline 多 1.5%–3.9% 命中率，QTTFT 降 28.3%–41.9%。

## 问题与动机

[[KV-Cache]] 复用（也称 [[Prefix-Caching]] / prompt cache）已成为 [[LLM-Inference]] 标配：共享 token 前缀时跳过 prefill 计算，降低 TTFT 并提升吞吐。现有系统（[[vLLM]]、CachedAttention、[[SGLang]]、Mooncake、Pensieve）的命中粒度与淘汰策略（LRU/FIFO/LFU）多基于合成数据集或「multi-turn 主导复用」的直觉设计。

论文指出三类盲区：(1) 生产 workload 到底有多少 [[KV-Cache]] 可复用、哪类请求贡献最大；(2) reuse time / reuse probability 分布如何影响 cache policy；(3) [[KV-Cache]] block 的 lifespan 与所需 cache 容量有多大。ShareGPT、Mooncake trace 等公开数据缺少 timestamp、request type、user ID、multi-turn 链路（Table 1），无法回答这些问题。

作者从阿里通义（TONGYI）收集两周生产 trace（to-C Trace A、to-B Trace B），在隐私约束下保留 timestamp、chat_id、parent_chat_id、user_id、req_type、token hash 等字段，先做系统刻画，再据此优化 eviction policy。贡献边界是 **characterization-first**：主 claim 是「真实 workload 特征与合成假设显著不同」，policy 改进是 characterization 的直接推论，而非全新 cache 架构。

## 关键观察 / 隐含假设

- **观察 1：生产 ideal cache hit ratio 中等且低于合成 workload，复用高度倾斜。** Trace A/B 在无限容量下 ideal hit 分别为 62% 和 54%，低于合成数据集上常报告的 80%+；10% 的 [[KV-Cache]] block 贡献 77% 复用。19% 用户（A）/ 4% 用户（B）贡献 >90% 命中。
  - **依赖假设**：一周 representative day 能代表工作日 steady-state；SipHash 四 token 粒度 hash 足以近似真实 prefix 匹配行为。
  - **可能失效场景**：reasoning model、agent 长链、多模态 burst 等新 workload 可能改变复用结构；不同云厂商/模型的 system prompt 模板化程度不同，to-B single-turn 主导结论未必外推。

- **观察 2：single-turn 与 multi-turn 对复用的贡献被误解；跨用户复用极低。** to-B Trace B 中 multi-turn 占比 <0.1%，但 single-turn 贡献 97% cache hit——主要来自 API 程序硬编码的共享 system prompt + 高 QPS（>10）快速复用。跨用户 hit heatmap 几乎只在 diagonal 上有信号，inter-user 复用可忽略。
  - **依赖假设**：to-B 客户普遍在程序内固定 system prompt，而非广泛采用第三方 prompt library 模板。
  - **可能失效场景**：prompt marketplace / RAG 共享知识库普及会抬高 inter-user hit；to-C 场景 multi-turn 仍占主导（Trace A），不能把 B 的结论直接套到 chatbot。

- **观察 3：temporal / spatial locality 是 workload-aware 的，且给定 category 下 reuse time 服从可拟合的指数分布。** 对每个 request category（req_type × turn number），reuse time 概率可用近期历史拟合 exponential CDF；相似流量时段（白天 vs 夜间、不同工作日同时段）分布稳定。Spatial locality 上，从请求头部 cache 收益最大；file/search 类 single-turn 几乎无 spatial locality（system prompt 随用户输入变化）。
  - **依赖假设**：serving gateway 能在运行时识别 request category；后台周期性采样足以跟踪分布漂移。
  - **可能失效场景**：Trace B >99% 为 1-turn API，category 信息贫乏，policy 实质上退化为 LRU；multimodal 类别预测难度高于 text（论文 Appendix 亦承认）。

- **观察 4：[[KV-Cache]] lifespan 极短，所需 cache 容量中等。** Trace B 的 P99 lifespan 仅 97 秒；Trace A 90% block 在 612 秒内不再被复用。GQA 模型（Qwen2-7B 等）上，Trace A 需约 4× per-GPU 可用 HBM 逼近 ideal hit，Trace B 在 2× HBM 上用标准 LRU 即接近 ideal——可能无需 CPU-RDMA-SSD 多层存储。
  - **依赖假设**：GQA/MLA 等低 per-token KV 占主导；MHA 大模型仍需要大 cache 和更好 policy（论文有提及但未深入优化）。
  - **可能失效场景**：超长 context（>12K tokens 尾请求）、MHA 模型、batch 极大导致单实例 QPS 低时，「小 cache 够用」结论会变弱。

- **假设 1**：LFU / frequency-heavy policy 不适合 [[KV-Cache]] 复用。
  - **证据强度**：强。短 lifespan 下「历史上频繁访问」不等于「未来会复用」；实验显示 LFU hit ratio 显著差于 LRU，与观察一致。

## 核心方法

### Production trace characterization（生产痕迹表征）

Trace 记录含 timestamp、chat_id、parent_chat_id（multi-turn 链）、user_id、req_type（Text/File/Multimodal/Search/API）、input/output token 数、四 token SipHash。Trace A 为 to-C 多类型；Trace B 为纯 API to-B。分析维度覆盖：ideal hit ratio、single/multi-turn 贡献、cross-user vs intra-user hit、reuse time / spatial locality（stride × offset heatmap）、block lifespan、per-request KV size（相对 HBM 归一化）、达到 ideal hit 所需容量。

### Workload-aware eviction policy（工作负载感知淘汰策略）

在现有 CPU-GPU 分层 cache 机制（与 CachedAttention / Pensieve 类似的 async layer-wise swap）上，替换 workload-agnostic LRU/FIFO/LFU。核心 priority：

$$\text{Priority} = (\text{ReuseProb}_w(t, \text{life}), -\text{Offset})$$

按词典序比较，越低越先淘汰。

1. **ReuseProb_w(t, life)**：对 workload category $w$，用后台近期 trace 样本拟合 exponential reuse CDF；$t$ 为距上次访问时间，$\text{life}$ 为预期 lifespan _regulator，避免 long-tail 分布给已「死亡」block 过高概率。
2. **Offset**：前缀 block 优先级更高，回应 spatial locality（请求头部 prefix 更可能跨请求共享）。
3. **去掉 Frequency**：与 GDFS 不同，明确剔除 frequency 项，因 ephemeral lifespan 使历史频次失去预测力。

性能优化：每个 workload 维护按 last-access-time 排序的 priority queue；淘汰时先取各 workload 的 LRU 候选再比较，复杂度从 $O(N)$ 降到 $O(W)$（$W$ 为 category 数，通常几十）。实测 eviction 延迟 79 µs，占 [[vLLM]] 调度开销 1.2%。

实现集成于 [[vLLM]]，并接入 Mooncake 式 global scheduler 做跨实例 KV-aware routing；但 workload-aware policy 本身仅作用于单实例，全局层扩展留作 future work。

## 设计取舍

- **Characterization-driven policy vs 通用 cache 理论**：放弃 GDFS 的 frequency×cost/size，改用领域特定的 exponential reuse model。收益是更贴合 LLM serving 的短生命周期；代价是依赖 request category 标注与在线分布拟合，Trace B 等低多样性 workload 收益有限。

- **Intra-user hit 优先 vs global prefix sharing**：刻画结论支持按用户隔离的 hit 检查（与部分系统一致），而非跨用户全局匹配。简化隐私与一致性，但放弃潜在的 shared prompt library 收益。

- **On-GPU 小 cache vs 多层存储**：Trace B 结论暗示 GPU HBM 可能足够，可省 CPU/SSD 层级成本与运维复杂度；但 Trace A / MHA 模型仍需要更大 CPU cache，policy 优化在容量受限时更有价值。

- **Trace replay 评测 vs 全规模生产回放**：匿名 trace 用随机 token 列表复现 hash 与 multi-turn 结构，保 cache pattern 但非真实语义负载。降低隐私风险，但 compute/latency 数字未必等于真实模型上的生产表现。

- **公平性**：论文承认恶意客户端可用长相同前缀垄断 cache（与现有系统相同），fairness 需与 scheduling 协同（如 FairRide），论文未实现。

## 实验与结果

- **Testbed**：8× NVIDIA A800-80GB；模型 Qwen2-7B（1 GPU）、Llama2-13B（1 GPU）、Llama3-70B（4 GPU TP）；trace 按时间模式缩放以适配 testbed QPS。
- **Baselines**：LRU、FIFO、LFU、S3-FIFO、vanilla GDFS；CPU cache 容量以 #CPU Cache / HBM 归一化变化。
- **命中率**：workload-aware（WA）比最强 baseline 高 **1.5%–3.9%**，比所有 baseline 平均高 **8.1%–23.9%**；容量越大 WA 优势越小（大 cache 容忍差 policy）。WA 在 Trace A 上更有效，Trace B 上接近 LRU。
- **延迟**：QTTFT（queued TTFT）降低 **28.3%–41.9%**（相对最强 baseline）。
- **Ablation**（Qwen2-7B, Trace A, CPU/HBM=1）：指数分布 reuse prob 单独 +1% hit；加 lifespan regulator 再 +2.4%。
- **GDFS 对比**：retrofit GDFS 未充分利用 LLM serving 的 category 分布与 lifespan，弱于 WA。
- **开源**：匿名 trace 样本 https://github.com/alibaba-edu/qwenbailian-usagetraces-anon

## 批判性分析

### 论证链条

论文链条清晰：**生产 trace 证明合成假设偏差** → **偏差直接映射到 policy 设计**（Table 2：exponential reuse → prob-based priority；spatial locality → offset；ephemeral lifespan → 去 frequency + life regulator）→ **vLLM 回放验证 hit/QTTFT 改进**。

最强环节是 characterization 对 design 的约束力。例如「single-turn API 主导 to-B hit」直接推翻 multi-turn-only 优化思路；「97s P99 lifespan」解释 LFU 失效并支持小 cache；「category 级指数分布可预测」为 workload-aware 提供可测量接口。这比单纯报告 +3.9% hit 更有长期价值。

薄弱环节在于 **policy 增益相对 characterization 偏小**。+1.5%–3.9% vs best baseline 说明 LRU 在不少场景已「足够好」；论文自己也指出 Trace B 上 WA ≈ LRU。因此主贡献更应定位为 **设计空间测量与假设修正**，而非颠覆性新系统。

### 假设压力测试

**Workload 漂移**：仅一周 trace、两种典型场景（chatbot + API），未覆盖 reasoning（o1 类）、tool-agent 高频短请求、多租户 prompt 模板化等新兴形态。作者明确承认 workload evolving，characterization 需定期重做。

**Category 可得性**：WA policy 假设 runtime 知道 req_type 与 turn number。Trace B 几乎全是 1-turn API，$W$ 很小，拟合退化为「带 offset 的 LRU」。若生产 gateway 丢失 type 信息或 turn 链断裂，policy 优势会缩水。

**Scale 外推**：容量分析用「最小实例数、最大 per-instance QPS」估计上界，合理；但实验 trace 经过 downscale，未验证百万 QPS、跨地域副本、PD disaggregation 下的分布是否保持。Global scheduler 只用 Mooncake 式 KV-aware routing，WA policy 未扩展到集群层。

**模型与 attention**：主要按 GQA 估算 KV size；MHA（Llama2-13B）cache 需求大得多，论文说 policy 仍重要但未给出与 capacity 曲线的完整对比。与 [[KV-Cache-Compression]]、sliding-window 等正交优化兼容，但未联合评测。

### 实验可信度

**优点**：真实生产 trace（业界少有的 type+time+UID+turn 深度）；ideal hit / lifespan / locality 等多维刻画互为支撑；ablation 分解三项技术贡献；与多种 cache policy 和 GDFS 对比；实现于 [[vLLM]] 并报告微秒级 overhead。

**局限**：
- CachedAttention / Pensieve 未开源，作者自实现「类似」CPU-GPU cache，与 SOTA 的数值对齐仅在 synthetic workload 上校准，生产 trace 上无 apples-to-apples 对比。
- 匿名 token 合成输入保留 cache **pattern** 但非真实 prefill 计算特征；QTTFT 对模型计算量、batching 敏感，绝对数字迁移需谨慎。
- Trace 缩放可能改变竞争强度、eviction 压力与 tail latency；论文未报告 P99/P999 QTTFT 或 ITL。
- 仅单集群、单模型 per trace 的分析日；跨模型混部、多 tenant 干扰未测。

### 系统性缺陷

- **全局与分层**：单实例 WA + Mooncake scheduler 的组合未证明在 multi-instance 下 hit 叠加还是互相稀释；CPU-GPU-SSD 层级运维成本、故障恢复、stale KV 语义论文未讨论。
- **分布拟合运维**：exponential 拟合需后台采样、周期更新 hyperparameter $H(w)$；分布漂移、冷启动、节假日流量突变时的退化行为未量化。论文未讨论错误拟合导致 hit 低于 LRU 的风险。
- **安全与隔离**：intra-user hit 策略缓解部分隐私 concern，但同一 user 下不同应用混用 cache 的隔离、prompt injection 通过 shared prefix 影响他人 session 等，论文未覆盖。
- **可观测性**：79 µs eviction overhead 有报告，但缺少 production 级 metrics（per-category hit、fit error、eviction reason）与调参指南。

## 局限与后续工作

- **局限 1**：结果基于一家云厂商一周量级 trace，代表性有限；reasoning 等新 workload 未刻画。
- **局限 2**：primary focus 是 eviction policy；global scheduling、admission control、fairness、压缩等组件仅点到为止。
- **局限 3**：Trace B 上 policy 收益边际，说明 workload-aware 设计需要足够 category 多样性才值得复杂度。
- **局限 4**：MHA 与大 context 场景的容量–policy 联合优化证据不足。

- **Future work 1**：对 reasoning / agent / 多模态 trace 重复 Table 1 级刻画，检验 exponential reuse 假设是否仍成立。
- **Future work 2**：将 WA priority 扩展到 global scheduler 与 [[Disaggregation]] 场景，测量跨实例 hit 与一致性开销。
- **Future work 3**：在线监测拟合误差，当 reuse 分布偏离 exponential 或 category 不可分时自动 fallback 到 robust policy（如 LRU/S3-FIFO），并量化 worst-case 退化。
- **Future work 4**：与 [[Prefix-Caching]]、[[KV-Cache-Compression]]、radix-tree 类结构（如 [[RadixAttention]]）联合评测，明确 policy 收益在完整 serving stack 中的占比。

## 相关

- **相关概念**：[[KV-Cache]]、[[Prefix-Caching]]、[[PagedAttention]]、[[Continuous-Batching]]、[[RadixAttention]]、[[Disaggregation]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Mooncake、CachedAttention、Pensieve、Prompt Cache、RAGCache
- **相关论文**：[[LMCache-arXiv25]]、[[CacheGen-SIGCOMM24]]、[[CacheBlend-EuroSys25]]
- **同会议**：[[ATC-2025]]
