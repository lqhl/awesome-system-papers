---
type: paper
name: PrefillOnly
full_title: "PrefillOnly: An Inference Engine for Prefill-only Workloads in Large Language Model Applications"
authors: [Kuntai Du, Bowen Wang, Chen Zhang, Yiming Cheng, Qing Lan, et al.]
venue: SOSP
year: 2025
tags: [llm-inference, prefill, scheduling, kv-cache, discriminative-ml]
source_pdf: "[[3731569.3764834.pdf]]"
source_md: "[[3731569.3764834]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# PrefillOnly：大型语言模型应用程序中仅预填充工作负载的推理引擎（SOSP 2025）

> **原题**：PrefillOnly: An Inference Engine for Prefill-only Workloads in Large Language Model Applications

> **一句话总结**：推荐/风控/embedding 等只生成 **1 个 token** 的 prefill-only workload 被 [[vLLM]] 按任意长 decode 管理 KV；PrefillOnly 用 hybrid prefilling 仅保留单层 KV + shortest-prefill-first 调度，QPS 最高 **4×** 且不抬高 avg/P99 latency。

## 问题与动机

除 ChatGPT 类生成外，LinkedIn/Meta 等大规模部署 **判别式 LLM**（推荐、信用验证、标注、embedding）：每请求只需 **一个 output token** 的 logits/隐藏态。现有引擎仍存 **全层全 token [[KV-Cache]]** 并为不确定 decode 长度调度，浪费 GPU memory 与 batch 容量。

Prefill-only 也出现在 [[Disaggregation]] 的 prefill node、embedding（append EOS 取 last hidden state）等场景。

## 关键观察 / 隐含假设

- **观察 1**：prefill-only 几乎不 reuse 多层 KV（仅 decode 1 token），理论上可只保留 **最后一层或单层** KV active footprint。
  - **依赖假设**：hybrid prefilling 能在单 forward pass 完成且 attention 层不 chunk 以保 kernel 效率。
  - **可能失效场景**：若框架强制全层 KV 给后续算子，单层策略需深度集成。
- **观察 2**：输出长度固定为 1 → **JCT 可预先估计**，可用 shortest-job-first 类调度。
  - **依赖假设**：continuous prefill time estimation 能跟踪 prefix cache 变化。
  - **可能失效场景**：prefix cache 剧烈抖动使 estimate 失真，SPF 优势下降。
- **观察 3**：naive 单层 KV 不省内存，因 non-attention 层 temporary tensors 仍大；需 **non-attention chunked + attention unchunked** 的 hybrid。
  - **依赖假设**：大部分内存来自 non-attention 层（§4.1 measurement）。
  - **证据强度**：强。动机与消融针对该设计点。

## 核心方法

1. **Hybrid prefilling**：non-attention 层 chunk-by-chunk；attention 层整段执行；单 forward pass 后可 offload/discard 多余 KV。
2. **Single-layer KV retention**：降低 active memory，减少跨 GPU KV 通信。
3. **Shortest prefill first (SPF)**：基于预计算/连续更新的 prefill time；带 fairness 防 starvation（§6.3）。
4. **Continuous prefill time estimation**：每 scheduling step 重估 waiting queue。

## 设计取舍

- **Prefill-only specialization vs general engine**：极致优化窄 workload，不替代通用 [[vLLM]]。
- **Hybrid vs chunked prefill**：平衡 memory 与 attention kernel 性能。
- **SPF vs FCFS**：降平均等待，需 fairness 修补。

## 实验与结果

- vs 通用 LLM engine：**4×** larger queries/s，avg 与 **P99** latency 不升。
- LinkedIn 等 production 动机；多种 GPU/模型配置（详见 source_md）。
- 与 prefix caching、长输入 profile 协同（§6.3 ablation）。

## 批判性分析

### 论证链条

「单 token 输出 → KV/调度可专门化」→ hybrid prefilling + SPF → QPS/latency，在 prefill-only trace 上闭合。与混合 generative+discriminative 同一集群共置时的干扰未充分讨论。

### 假设压力测试

- 若业务改为生成短序列（2–10 tokens），引擎需降级或切换 general path。
- Hybrid prefilling 实现复杂，bug 可能导致 silent 数值错误——需严格 parity test（论文应有，wiki 读者应查 §6）。
- SPF 在 prefix-heavy skew 下可能对长 prefill 请求不公平——fairness 修饰效果需看具体 trace。

### 实验可信度

- LinkedIn 作者参与增 production face validity。
- Baseline 应为 vLLM 类 SOTA；需确认 compare 公平（同 memory budget）。
- 4× QPS 峰值依赖 workload mix；不宜当作所有 LLM API 通用提升。

### 系统性缺陷

- 论文未讨论与 PD-disaggregation cluster scheduler 的全局协同。
- 单一层 KV 对 tensor parallel 切分的影响未详述。
- Multi-tenant SLO 隔离未讨论。

## 局限与后续工作

- **局限**：仅 prefill-only；hybrid 实现复杂；与 general serving 混部未验证。
- **Future work**：自动 workload 分类路由；与 [[Jenga-SOSP25]]/远端 KV 协同；embedding+generative 统一 scheduler。

## 相关

- **相关概念**：[[LLM-Inference]]、[[KV-Cache]]、[[vLLM]]、[[Continuous-Batching]]、[[Disaggregation]]
- **同类系统**：[[vLLM]]、[[SGLang]]、chunked prefill 实现
- **同会议**：[[SOSP-2025]]
