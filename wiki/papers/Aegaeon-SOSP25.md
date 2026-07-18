---
type: paper
name: Aegaeon
full_title: "Aegaeon: Effective GPU Pooling for Concurrent LLM Serving on the Market"
authors: [Yuxing Xiang, Xue Li, Kun Qian, Yufan Yang, Diwen Zhu, Wenyuan Yu, Ennan Zhai, Xuanzhe Liu, Xin Jin, Jingren Zhou]
venue: SOSP
year: 2025
tags: [multi-model-serving, gpu-pooling, serverless, llm-marketplace, autoscaling]
source_pdf: "[[3731569.3764815.pdf]]"
source_md: "[[3731569.3764815]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# Aegaeon: Effective GPU Pooling for Concurrent LLM Serving on the Market (SOSP 2025)

> **一句话总结**：Aegaeon 用 token-level preemption 与全栈 scaling optimization 汇聚长尾模型；在 16×H800 testbed 的 10-GPU decoding pool 中承载 70 models，在 Alibaba beta deployment 中将 H20 provisioning 从 1,192 降至 213（82%），但 7 models/GPU 只适用于 decoding pool（§7.1–7.2/7.5，Fig. 11/18）。

## 问题与动机

[[LLM-Inference]] 市场（Hugging Face 百万模型、阿里 Model Studio 数千模型） invocation 极稀疏且 burst。Dedicated GPU 浪费；MuxServe/ServerlessLLM 等 multiplexing 受 HBM 限制每 GPU **2–3** 模型；request-granularity auto-scaling 因长请求使多模型同时 active，排队严重（Theorem 3.1：3.7 rps 时 100 模型中 **46.55** active）。

## 关键观察 / 隐含假设

- **观察 1**：token-level 可在长请求中间 preempt 缩放，缓解 HOL——不必等整请求结束才腾 GPU。
  - **依赖假设**：prefill/decode 分离调度；TTFT/TBT per-token SLO 可定义。
  - **可能失效场景**：极长 decode 若抢占过频，scaling overhead 可能反超收益；T0→T3 优化将被测 preemptive auto-scaling latency 最多降低 97%（§5、§7.3，Fig. 7–10/15）。
- **观察 2**：token-level scaling 需 KV swap-out、GC、engine reinit、KV swap-in 等序列，朴素实现 tens of seconds 不 practical。
  - **依赖假设**：组件重用、显式内存管理、细粒度 KV 同步可把 overhead **-97%**。
  - **可能失效场景**：超大 TP 模型组件重用率下降。
- **假设 1**：Model Studio workload 的长尾统计可代表目标市场；94.1% models 只承载 1.35% requests（§1、§2.2，Fig. 1）。
  - **证据强度**：中；production trace 支持该时窗，但论文未报告采样时窗，也未证明 beta 三个月中分布稳定。

## 核心方法

**Aegaeon**：

- **Token-level scheduler**：prefill grouped FCFS 优化 TTFT；decode weighted RR 优化 TBT 违约数
- **Auto-scaling 优化**：engine 组件重用、GPU/host 显式内存+cache/prefetch、细粒度 [[KV-Cache]] 同步
- 与 [[ServerlessLLM]]、MuxServe 正交提升 pooling 上限

## 设计取舍

- **取舍 1**：激进抢占 vs SLO——调度启发式非最优（论文承认 intractable）。
- **取舍 2**：深度绑定 inference engine 内部实现——移植成本高。
- **边界条件**：2×H800 nodes、16 GPUs（6 prefill + 10 decoding）、6B–14B models、synthetic Poisson arrivals、TTFT 10 秒/TBT 100 毫秒；不同配置下相对 baseline 达到 2–2.5× arrival tolerance 或 1.5–9× goodput。

## 实验与结果

- **Workload skew**：94.1% models 仅承载 1.35% requests，最多 17.7% GPUs 被 sporadic cold models 占用；并发 serving 少于 0.1 RPS/GPU（§1、§2.2，Fig. 1；Alibaba Model Studio trace，采样时窗未披露）。
- **Active-model analysis**：M=100、每模型 λ=0.037 RPS、平均 service time 16.79 秒时，request-level policy 的 E[m]=46.55（§3.1，Theorem 3.1，Fig. 4；independent Poisson arrivals 的数学/模拟边界）。
- **SLO goodput**：ShareGPT、0.1 RPS/model 时，Aegaeon goodput 为 ServerlessLLM 的 2×，70 models / 10 decoding GPUs；0.5 RPS/model 时可承载 request rate 为 2.5×（§7.1–7.2，Fig. 11；2 nodes/16×H800，90% SLO threshold）。
- **Scaling latency**：unoptimized 13B engine initialization 最高 26.9 秒；T0→T3 将 preemptive auto-scaling latency 最多降低 97%，未完全隐藏时也少于 1 秒（§5.1–5.3、§7.3，Fig. 7–10/15；不是单独 KV swap 的降幅）。
- **Beta deployment**：47 models 下 H20 GPUs 从 1,192 降至 213（82%）；70 小时观察中 utilization 从 13.3%–33.9% 增至 48.1%，未观察到 SLO violation/service disruption（§7.5，Fig. 18；跨 region、保留 peak/fault redundancy，非 randomized experiment）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| Model Studio workload 的长尾使 dedicated GPU allocation 浪费 | §1, §2.2, Fig. 1 | Alibaba production trace；时窗未披露；不外推所有市场 | strong |
| Request-level scaling 在 Poisson 模型下产生大量 active models | §3.1, Theorem 3.1, Fig. 4 | M=100；λ=0.037；service 16.79s；模拟非生产对照 | medium |
| Aegaeon 在 decoding pool 中达到 7 models/GPU 并提高 SLO goodput | §7.1–7.2, Fig. 11 | 16×H800；10 decoding GPUs；6B–14B；ShareGPT/Poisson | strong |
| Full-stack optimizations 将 preemptive scaling latency 最多降低 97% | §5.1–5.3, §7.3, Fig. 7–10/15 | tested model sizes；T0→T3 ablation；chart-dependent | medium |
| Beta deployment 将 H20 provisioning 从 1,192 降至 213 | §7.5, Fig. 18 | 47 models；cross-region Alibaba；70h SLO observation | strong |

## Critical Analysis

### 论证链条

Theorem 3.1 + 生产 CDF → token-level 必要性 → 全栈优化 → 7 模型/GPU + 82% GPU 省，生产验证强。学术 lab 复现依赖阿里引擎细节与 trace 不可得部分。

### 假设压力测试

- **SLO 定义**：per-token deadline 与用户体验映射在极长生成时是否仍准。
- **模型异构**：72B TP=8 与 1.8B 混部时 memory fragmentation。
- **冷模型**：SSD 加载延迟与 prefetch 命中率随 catalog 增长。

### 实验可信度

阿里巴巴生产部署是亮点；学术 baseline 对比充分。缺公开 trace 使第三方完全复现困难。

### 系统性缺陷

抢占频繁时的质量隔离（慢模型拖累快模型）、故障模型 partial load、多租户 billing 论文未讨论。与 [[PhoenixOS]] GPU snapshot 协同可进一步降 scaling 成本——未探索。

## 局限与 Future Work

- **局限 1**：调度最优性启发式，恶劣 SLO 组合可能失效。
- **局限 2**：引擎深度集成阻碍跨框架（vLLM/SGLang）移植。
- **Future work 1**：公开 anonymized market trace 驱动开源复现 pooling 上限。
- **Future work 2**：token-level scaling + [[DiffKV]] 压缩 KV swap 带宽需求。

## 相关

- **相关概念**：[[LLM-Inference]]、[[KV-Cache]]、[[GPU-Pooling]]、[[Serverless]]、[[Multi-Tenancy]]
- **同类系统**：ServerlessLLM、MuxServe、BlitzScale、ParaServe
- **同会议**：[[SOSP-2025]]
