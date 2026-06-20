---
type: paper
name: BOUTE
full_title: "BOUTE: COST-EFFICIENT LLM SERVING WITH HETEROGENEOUS LLMS AND GPUS VIA MULTI-OBJECTIVE BAYESIAN OPTIMIZATION"
authors: [Youhe Jiang, Fangcheng Fu, Eiko Yoneki]
venue: MLSys
year: 2026
tags: [llm-serving, routing, heterogeneous-gpu, mobo, cost-efficiency]
source_pdf: "[[d9d4f495e875a2e075a1a4a6e1b9770f.pdf]]"
source_md: "[[d9d4f495e875a2e075a1a4a6e1b9770f]]"
---

# BOUTE: COST-EFFICIENT LLM SERVING WITH HETEROGENEOUS LLMS AND GPUS VIA MULTI-OBJECTIVE BAYESIAN OPTIMIZATION (MLSys 2026)

> **一句话总结**：heterogeneous model routing 与 heterogeneous GPU deployment 双向依赖，孤立优化次优；BOUTE 用 **MOBO** 联合优化路由阈值 **τ** 与每模型 GPU 类型/数量/并行度，在同等成本与质量下 P95 延迟最高降 **33%**（heterogeneous vs 12×H100 homogeneous），或成本降 **15–61%**（均 **38%**）保性能。

## 问题与动机

[[LLM]] serving 需同时决定 **路由到哪个模型** 与 **如何部署到 GPU**。[[RouteLLM]]/HybridLLM 等做 query-level routing；ThunderServe/Helix 等用异构 GPU 降本。但 routing 改变各模型负载，deployment 决定各模型可达延迟——二者 circular dependency，分开优化在 GSM8K 案例上可差 **10%+ P95**（Approach 1 vs 3）。

BOUTE 从服务商视角 co-optimize routing + deployment under latency & quality constraints。

## 关键观察 / 隐含假设

- **观察 1：仅 routing + 均分 GPU（6+6 on 12 H100）会使大模型瓶颈，P95 **28.2s** 差于单大模型 **25.6s**。** 按负载调 allocation（4+8）可降至 **20.5s**。
  - **依赖假设**：阈值路由可稳定预测「小模型够用」比例。
  - **可能失效场景**：分布漂移导致路由阈值过时。

- **观察 2：同预算下 6×RTX5090 + 10×H100 vs 12×H100，小模型放 5090、大模型多 H100，路由比从 40/60→30/70，P95 **17.1s**（**33%↓**），质量 **91.2>90**。
  - **依赖假设**：小模型在 5090 上 **~1.5×** 更低 P95，大模型在 H100 上 **~2×** 优于 5090（同成本 24×5090 vs 8×H100 实验）。
  - **可能失效场景**：不同云实例价目/可用 SKU 改变 Pareto 前沿。

- **观察 3：MOBO 在 latency–quality 目标下给 Pareto 最优 **(τ, deployment)**，服务商可选运营点。**
  - **依赖假设**：离线 profiling 足够代表在线负载；MOBO 样本效率可接受。
  - **可能失效场景**：新模型上线需重跑 BO；非平稳 traffic 需再优化。

- **假设 1**：threshold router（与 RouteLLM 一致）足以表达 routing policy。**
  - **证据强度**：**中**——简单可优化，但不如 learned router 灵活。

## 核心方法

**决策变量**：路由阈值向量 **τ**；每模型 GPU 类型、卡数、[[TP]]/[[PP]]/[[DP]] 配置。

**目标**：最小化成本或 latency，约束 response quality（GSM8K 等）。

**MOBO**：多目标 Bayesian optimization 探索 Pareto frontier；结合 workload characterization §3 洞察初始化。

## 设计取舍

- **联合优化 vs 复杂度**：搜索空间大，靠 MOBO 而非穷举。
- **Threshold router vs 神经网络 router**：可解释、易进 BO，可能损失细粒度 routing。
- **静态 co-design vs 在线 adapt**：部署期优化为主，traffic 变需重跑。
- **边界条件**：Llama3.1-8B/70B 等；价目基于特定云 GPU 小时费。

## 实验与结果

- vs SOTA serving：**157%** peak / **59%** avg 性能提升（同成本质量），或成本 **15–61%** 降（**38%** avg）保目标。
- Characterization：Approach 1→2→3 阶梯改进 P95 **28.2→20.5→17.1s**。
- MOBO 找 Pareto 部署优于分离启发式。

## Critical Analysis

### 论证链条

双向依赖 characterization 有力 → 形式化 co-optimization → MOBO 求解 → 显著降本/降延迟，闭合。MOBO 是否全局最优依赖 surrogate 质量。

### 假设压力测试

>3 模型、MoE、disaggregated prefill/decode 时 action space 爆炸。质量 metric 单数据集可能不代表生产。RTX5090/H100 相对性能随 batch/并发变。

### 实验可信度

强基线 ThunderServe/Helix 等；真实价目约束。缺：长周期在线 A/B、router 校准漂移。

### 系统性缺陷

论文未讨论 BO 失败安全 fallback、多租户 fairness、SLO 违约惩罚。运维重优化频率与自动化未量化。

## 局限与 Future Work

- **局限 1**：路由策略族有限；动态 learned router 未联合。
- **局限 2**：依赖离线 profile，online shift 敏感。
- **Future work 1**：在线 contextual BO 用 live telemetry 微调 **τ** 与 allocation。
- **Future work 2**：与 [[MorphServe]] 等 morph 模型族扩展 action space。

## 相关

- **相关概念**：[[LLM-Routing]]、[[Tensor-Parallelism|Tensor-Parallel]]、[[Disaggregation]]、[[Cost-Efficiency]]
- **同类系统**：[[RouteLLM]]、ThunderServe、Helix
- **同会议**：[[MLSys-2026]]