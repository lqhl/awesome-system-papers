---
type: paper
name: CrossPool
full_title: "CrossPool: Efficient Multi-LLM Serving for Cold MoE Models through KV-Cache and Weight Disaggregation"
authors: [Zhuoren Ye, Tianyu Wo, Dinghao Xue, Mingming Zhang, Yuchen Teng, Chunming Hu, Renyu Yang]
venue: arXiv
year: 2026
tags: [multi-model-serving, moe, kv-cache, gpu-pooling, disaggregation, cold-model]
source_pdf: "[[arxiv26-ye-crosspool.pdf]]"
source_md: "[[arxiv26-ye-crosspool]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# CrossPool：通过 KV 缓存和权重分解为冷 MoE 模型提供高效的多 LLM 服务（arXiv 2026）

> **原题**：CrossPool: Efficient Multi-LLM Serving for Cold MoE Models through KV-Cache and Weight Disaggregation

> **一句话总结**：面向 cold MoE multi-LLM serving，CrossPool 把 **FFN 权重池** 与 **KV-cache 池** 拆到不同 GPU 组（权重与 KV 仍均在 GPU HBM），层间传 hidden state 而非 KV；配合 P95/P99 聚合 KV 规划、层间 pipeline 与 persistent kernel，在 5×A100 上相对 kvcached（Chimera）P99 TBT 最高降 **10.4×**，长 context 可支撑范围显著大于 Static Partition / kvcached。

## 问题与动机

MaaS 平台同时托管大量 [[MoE]] 模型，但 OpenRouter 统计 ~**90%** 模型为 cold、流量极 skew（与 [[Weaver-ATC25]]、[[Aegaeon-SOSP25]] 同类观察）。cold 模型常驻 GPU 时 **权重稳定占用 HBM**，而 [[KV-Cache]] 随请求动态增长又在 decode 结束后释放——低 RPS 时各模型 active KV 很少同时 peak，按 per-model worst-case 预留 KV 浪费显存。

现有 multi-LLM 系统（MuxServe、kvcached/Chimera）在 **单体 GPU memory pool** 内共置权重与 KV，且对 MQA/MLA 等 KV-head-limited 模型常用 DP attention：高并发时 aggregate KV 容量大，但 **cold、低并发** 下单请求只能看到 **1/GPU 或 1/replica** 的 KV 容量（论文 Fig. 2）。权重进一步挤占 per-GPU KV 空间，长 context MoE 在同等硬件下可用 context 骤降甚至 OOM。

CrossPool 的 claim：把 **FFN 权重**（MoE 参数主体，Table 1 中占 **94–95%**）与 **attention + 非 FFN 模块 + KV** 分到两个 GPU pool，pool 边界交换 **hidden state**（大小与 batch×hidden 相关，不随 context 增长），从而在同一硬件预算下扩大 **共享 KV pool** 的有效容量。

## 关键观察 / 隐含假设

- **观察 1：权重与 KV 生命周期不同，cold 模型 KV peak 不同步。** 低 RPS 下四模型 1 小时 active KV 叠加曲线显示 aggregate demand 远小于 per-model peak 之和。
  - **依赖假设**：部署目录大、单模型请求稀疏；保留 cold 模型 online 有业务价值。
  - **可能失效场景**：精选少量热模型、高并发 agent session——aggregate KV 接近线性叠加，pooling 收益消失。
- **观察 2：MQA/MLA + DP 在 cold traffic 下造成 algorithm-system mismatch。** Type II attention（n_heads \< G）在低并发时只有带 active request 的 replica 暴露 KV。
  - **依赖假设**：评测模型含 GLM-4.7-Flash、DeepSeek-V2-Lite（MLA）等；DP attention 是生产默认。
  - **可能失效场景**：高并发或改 TP 布局后 mismatch 减轻。
- 观察 3：MoE FFN 占参数绝大多数，attention 必须本地访问 KV。 传 KV 跨 pool 会使 attention 通信 bound；传 hidden state 可接受但 每层每 token 两次跨 pool。
  - **依赖假设**：NVLink + NVSHMEM 带宽足够；layer-wise pipeline + persistent kernel 可隐藏大部分 exposed latency。
  - **可能失效场景**：PCIe 异构集群、弱卡算力不匹配导致 pipeline bubble；论文 limitation 承认 A-to-F / F-to-A 仍在 critical path。
- **假设 1：Prefill 与 decode 分离，CrossPool 只优化 decode 侧 colocation。** 实现上 prefill 走独立 temporal-multiplexing engine（对齐 [[Aegaeon-SOSP25]] 思路）。
  - **证据强度**：中。评测聚焦 decode TBT / 长 context scalability。
- **假设 2：三个 cold MoE 共 ~154 GB 权重可在 weights pool 内容纳，KV pool 单独规划。**
  - **证据强度**：中。5×A100-40GB 同构 NVLink testbed；未测 CPU/NVMe tier。

## 核心方法

**双 pool 架构**：KV-cache pool 跑 attention、非 FFN 模块与 KV（基于 [[SGLang]] v0.5.10）；weights pool 跑各模型 FFN（FusedMoE）。FFN 层在 KV pool 侧替换为 **proxy layer**，经 NVSHMEM 异步传 hidden state。

**KV-cache planner + virtualizer（C1）**：离线用 per-model prompt/output/service-time 样本、到达率 λ、per-token KV bytes κ(M)，按公式估计 aggregate active KV K_pool(t)，取 **P95/P99 Monte Carlo quantile** 定 shared pool page budget 与 parallelism plan。在线用 **CUDA VMM** 虚拟化 KV 地址空间，attention kernel 仍见 paged KV 接口；pool 耗尽时 **admission control** 排队/拒绝新请求，不中断 active decode。

**Layer-wise pipeline scheduler（C2）**：维持两个 in-flight batch（可不同模型、不同层数），在 KV pool 跑 batch B1 attention 时 weights pool 可跑 batch B2 的 FFN，重叠跨 pool 延迟。

**Persistent kernels + control lowering（C3）**：attention / FFN 子图分别 CUDA graph capture；GPU-resident persistent kernel 轮询队列、dispatch graph、发起 inter-pool 通信，减少 host 侧 per-layer 控制。

## 设计取舍

- **GPU 内 disaggregation vs CPU/NVMe offload**：简化通信语义、保性能，但 **总 HBM 硬上限** 决定可 colocate 模型数；不缓解「集群总显存 \< 模型集权重和」。
- **Hidden state 边界 vs KV 边界**：避免 context-length 比例通信，但每层双次 transfer；pipeline 未完全隐藏 A-to-F / F-to-A（论文 §6 limitation）。
- **Cold MoE catalog vs 热模型频繁切换**：优化长尾共存，非交互式 switch latency。
- **绑定 SGLang + 同构 NVLink 五卡**：可复用 FlashAttention/FlashInfer 与 FusedMoE；移植 [[vLLM]]/异构 PCIe 需重做 transport 与 planner。
- **Decode-only colocation**：prefill 另引擎，端到端 TTFT 未作为主轴。

## 实验与结果

- **平台**：5×NVIDIA A100-40GB，NVLink；三 MoE：Qwen3-30B-A3B、GLM-4.7-Flash、DeepSeek-V2-Lite（合计 ~154 GB 权重）；prefill-decode disaggregation，对比 **decode 侧**。
- **Baselines**：(1) Static Partition（SGLang 静态 placement + MIG）；(2) **kvcached**（Chimera 弹性 KV pooling，权重与 KV 仍单体 pool）。
- **长 context scalability（LongAlign）**：随 context bin 增大，Static / kvcached 出现 capacity cliff（vertical drop）；CrossPool 在支持范围内保持正 max RPS，因共享 KV pool 更大。
- **ShareGPT TBT（0.2–1.0 RPS/model）**：相对 kvcached，0.8 RPS 时 P99 TBT 降 **7.36×**（GLM-4.7-Flash）等；1.0 RPS 时三模型 P99 降 **2.1× / 5.0× / 2.2×**；DeepSeek-V2-Lite 最高 **10.4×**。相对 Static Partition，CrossPool 在同等硬件下换更长 context 能力，TBT 仍具竞争力。
- **Ablation（0.5 RPS，三模型）**：无优化 disagg baseline **55.42** tok/s；仅 persistent kernel **77.86**（1.41×）；仅 pipeline **60.83**（1.10×）；二者 **111.40**（2.01×）。

## 批判性分析

### 论证链条

「cold skew + 权重/KV 生命周期差 + DP 低并发 KV 浪费」→ 双 GPU pool + hidden-state 边界 → planner 扩大共享 KV → 长 context cliff 后移 + ShareGPT TBT 优于 kvcached，链条在 **三 cold MoE、五同构 A100、低 RPS** 设定下闭合。Ablation 证明 pipeline 与 persistent kernel 对 disaggregation overhead 都必要。

### 假设压力测试

- **Warm small catalog**：5–8 个常用模型、10 人 agent 同时活跃时，K_pool(t) 近似求和，共享 pool 优势收窄，调度问题变为 **抢占与 SLO**。
- **资源紧缺需 offload**：权重全在 GPU，总 HBM 不够时无法靠 CrossPool 扩 catalog，必须 CPU/SSD tier（[[LMCache-arXiv25]]、[[DwarfStar]] 路线）。
- **异构 GPU**：仅同构 A100；PCIe/算力差异使 pipeline 与 transfer 隐藏窗口未知。
- **Model switch / agent handoff**：优化 cold 共存吞吐，未报告 **模型切换冷启动** 或 per-user session 公平性。
- **Pipeline imbalance**：不同 MoE 层耗时差异使短模型等长模型（论文 §6）；placement 时需按 compute profile 分组。

### 实验可信度

- Baseline 选择贴切（Static vs 弹性 kvcached）；同总 GPU 预算、同三模型 placement 对比公平。
- 缺公开 trace/code；prefill 路径与 decode 引擎分离使端到端生产复现需额外集成。
- 未测 heterogeneous GPU、权重 offload、多租户 fairness。

### 系统性缺陷

- A-to-F / F-to-A 仍在 critical path，更深 staging 未实现。
- Admission reject/queue 对 tail SLO 与用户体验未系统量化。
- 依赖 SGLang 专有集成，跨框架成本高。

## 局限与后续工作

- **局限 1**：通信未完全隐藏；异构模型 pipeline imbalance。
- **局限 2**：仅 GPU 内 pool，无 Host/SSD weights 或 KV tier。
- **局限 3**：cold、低 RPS、同构 NVLink 五卡；agent / 热切换未覆盖。
- **Future work 1**：更细粒度 pipeline staging，重叠 A-to-F 与 FFN compute。
- **Future work 2**：按 attention/FFN profile 分组 cold 模型再 colocate。
- **Future work 3**：与 [[LMCache-arXiv25]] / CPU weights tier 联合，面向真正 memory-constrained 集群。

## 相关

- **相关概念**：[[KV-Cache]]、[[MoE]]、[[Disaggregation]]、[[PagedAttention]]、[[LLM-Inference]]
- **同类系统**：[[Aegaeon-SOSP25]]、[[Weaver-ATC25]]、MuxServe、kvcached（Chimera）、[[SGLang]]
- **对照（资源层级）**：[[LMCache-arXiv25]]、[[FluxMoE-arXiv26]]、[[DwarfStar]]
