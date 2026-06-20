---
type: paper
name: Aegaeon
full_title: "Aegaeon: Effective GPU Pooling for Concurrent LLM Serving on the Market"
authors: [Yuxing Xiang, Xue Li, Kun Qian, Yufan Yang, Diwen Zhu, Wenyuan Yu, et al.]
venue: SOSP
year: 2025
tags: [multi-model-serving, gpu-pooling, serverless, llm-marketplace, autoscaling]
source_pdf: "[[3731569.3764815.pdf]]"
source_md: "[[3731569.3764815]]"
---

# Aegaeon: Effective GPU Pooling for Concurrent LLM Serving on the Market (SOSP 2025)

> **一句话总结**：模型市场长尾导致 17.7% GPU 服务 1.35% 请求；request-level auto-scaling 受 LLM 长请求影响 active model 过多（100 模型中平均 **46.55** active），HOL blocking 限制每 GPU **<3** 模型；Aegaeon **token-level** 抢占式缩放 + 全栈加速，每 GPU **7** 模型，生产 **1192→213 GPU（-82%）**。

## 问题与动机

[[LLM-Inference]] 市场（Hugging Face 百万模型、阿里 Model Studio 数千模型） invocation 极稀疏且 burst。Dedicated GPU 浪费；MuxServe/ServerlessLLM 等 multiplexing 受 HBM 限制每 GPU **2–3** 模型；request-granularity auto-scaling 因长请求使多模型同时 active，排队严重（Theorem 3.1：3.7 rps 时 100 模型中 **46.55** active）。

## 关键观察 / 隐含假设

- **观察 1**：token-level 可在长请求中间 preempt 缩放，缓解 HOL——不必等整请求结束才腾 GPU。
  - **依赖假设**：prefill/decode 分离调度；TTFT/TBT per-token SLO 可定义。
  - **可能失效场景**：极长 decode 若抢占过频，swap overhead 反超收益——靠 **97%** 开销削减缓解。
- **观察 2**：token-level scaling 需 KV swap-out、GC、engine reinit、KV swap-in 等序列，朴素实现 tens of seconds 不 practical。
  - **依赖假设**：组件重用、显式内存管理、细粒度 KV 同步可把 overhead **-97%**。
  - **可能失效场景**：超大 TP 模型组件重用率下降。
- **假设 1**：生产 skew（94.1% 模型仅 1.35% 请求）在 beta 三个月仍成立。
  - **证据强度**：强；真实部署 1192→213 GPU。

## 核心方法

**Aegaeon**：

- **Token-level scheduler**：prefill grouped FCFS 优化 TTFT；decode weighted RR 优化 TBT 违约数
- **Auto-scaling 优化**：engine 组件重用、GPU/host 显式内存+cache/prefetch、细粒度 [[KV-Cache]] 同步
- 与 [[ServerlessLLM]]、MuxServe 正交提升 pooling 上限

## 设计取舍

- **取舍 1**：激进抢占 vs SLO——调度启发式非最优（论文承认 intractable）。
- **取舍 2**：深度绑定 inference engine 内部实现——移植成本高。
- **边界条件**：vs ServerlessLLM/MuxServe **2–2.5×** arrival rate 或 **1.5–9×** goodput。

## 实验与结果

- 实验：**2–2.5×** 更高 arrival rate 或 **1.5–9×** goodput vs ServerlessLLM、MuxServe
- 每 GPU 支持 **7** 模型（vs **<3**）
- 生产 beta（数十模型 1.8B–72B）：GPU **1192 → 213（-82%）**
- Auto-scaling overhead **-97%**

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