---
type: paper
name: Meta-LLM-Deploy
full_title: "Optimizing Deployment Configurations for LLM Inference: Challenges and Insights"
authors: [Meta Inference Team]
venue: MLSys
year: 2026
tags: [llm-inference, deployment, simulator, parallelism, disaggregation, production, meta, llama]
source_pdf: "[[c7e1249ffc03eb9ded908c236bd1996d.pdf]]"
source_md: "[[c7e1249ffc03eb9ded908c236bd1996d]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Meta-LLM-Deploy：优化 LLM 推理的部署配置：挑战和见解（MLSys 2026）

> **原题**：Optimizing Deployment Configurations for LLM Inference: Challenges and Insights

> **一句话总结**：Meta Llama 近 **10 亿** MAU 推理需在硬件（H100/H200/MI300X）、5D 并行（TP/PP/EP/CP/DP）、runtime（continuous batching vs disaggregation）与优化技法组成的 **数百万** 配置中满足 TTFT/TTIT SLO；轻量 benchmark 驱动模拟器（±**5%** 误差、分钟级搜百万组合）提炼生产洞察，在线场景 disagg 吞吐 **1.5–2.2×** vs continuous batching，整体配置优化带来约 **2.5×** 吞吐提升，多数在线服务已迁 disagg 省 **~30%** 容量。

## 问题与动机

单条 Llama3-70B 请求成本远高于传统推荐模型（Table 1）。生产 workload 在 input/output 长度、session [[KV-Cache]] 累积、多模态、SLO 上极度异构；硬件平台从 weak/strong scale-out 到 scale-up（NVLink Switch、TPU pod）成本性能差可达 **2–3×**。

手工启发式无法跟上 [[MoE]]、MLA 等架构与优化技法迭代。需要 **系统化设计空间探索**：在 latency SLO 约束下最大化 throughput（QPS_cluster）。

## 关键观察 / 隐含假设

- 观察 1：prefill 计算密集、decode 内存带宽密集——最优并行 phase-specific；disaggregated runtime 可为两阶段选不同 P（如 70B online：prefill PP4-TP2，decode TP8）。
  - **依赖假设**：模拟器 operator 插值（100K+ microbench/硬件）足够预测端到端；通信与 runtime overhead 可叠加在关键路径。
  - **可能失效场景**：P99 尾延迟受网络抖动，模拟器偏 median/mean；新算子未 benchmark 时需 simulation 估计。

- 观察 2：严格 TTFT/TTIT 的在线场景，disagg 一致优于 continuous batching（70B 1.5–1.8×，405B 1.8–2.2× QPS_cluster），因 decode batch 可远大于 mixed batch（如 112 vs 28）。
  - **依赖假设**：KV 传输与 pool 运维成本可接受——Meta 多数在线已切换 disagg。
  - **可能失效场景**：离线吞吐 sole objective 时差距缩小，70B 上 cont.batch 甚至略胜，disagg 运维不划算。

- 观察 3：异构硬件映射（算力型 prefill GPU + 带宽型 decode GPU）可达与同质最佳相当的 QPS_cluster，建模估 15–25% 成本效率提升。
  - **证据强度**：**中**——依赖真实卡价与可用池；跨地域调度复杂。

- **观察 4：MoE 在 scale-out 上 EP 可显著提升吞吐，但 expert load imbalance 需经验 token 分布建模；simulator 纳入 empirical routing。**
  - **可能失效场景**：routing 漂移或 cold expert 时 benefit 缩水。

- **假设 1：组合空间可激进剪枝（违 SLO/内存、非 2 幂并行度等）后仍保留最优附近解。**
  - **可能失效场景**：GB200 NVL72 等非 8 卡拓扑需扩展搜索规则。

## 核心方法

**问题形式化**：给定模型 M、workload D、硬件 H、并行 P、runtime R，最大化 QPS_cluster s.t. TTFT/TTIT ≤ SLO。

**模拟器**（Fig. 7）：
1. Micro-benchmark 建 \(F(op, H, shape)\) 分段线性插值。
2. 按 P 实例化算子图，加 collective 与 runtime 开销。
3. Continuous batching：prefill/decode 耦合计 TTIT；disagg：独立池再算 accelerator ratio 平衡。
4. 扩展：speculative decoding（acceptance rate）、MoE imbalance、power-capped 硬件变体、TCO。

**搜索**：百万级 (H,P,R) 剪枝后分钟级；输出 Pareto frontier 与 SLO-aware 排名。

**验证**：多样并行场景模拟 vs 实测 **±5%**（Fig. 8）。

## 设计取舍

- **Benchmark-driven 模拟 vs cycle-accurate/ML 模拟**：快、准于中位数决策，牺牲 tail 与未见 shape 外推精度。
- **Disagg 默认在线最优 vs 运维现实**：KV 传输、池容量、故障域增加——Meta 用 **~30%** 容量节省论证 ROI。
- **Insight 论文 vs 开源工具**：分享方法论与结论，模拟器本身未作为产品开源（相对 Agrawal 等公开 sim）。
- **Llama/MoE 周期绑定**：结论方向性可迁移，数值随下一代模型/卡刷新。

## 实验与结果（Case studies，模拟器）

**§4.2 Runtime**：在线 strict SLO 下 disagg QPS 显著高于 cont.batch；离线生成两者趋同 deep PP + 超大 batch。

**§4.3 并行**：prefill 增 TP 降延迟但通信使 QPS **sub-linear**（TP4PP2 vs TP2PP4：latency 更低但 QPS **−20%**）；decode 高 TP 利带宽聚合。

**§4.4 异构**（405B online）：GPU-A prefill + GPU-B/C decode 达同质最佳 **QPS=67**，估 **15–25%** cost efficiency。

**§4.5 MoE**：EP 在 scale-out 提升明显；需 imbalance 建模。

**§4.6 平台**：错选 weak vs strong scale-out 可 **2–3×** 成本效率损失或 SLO fail。

**生产**：整体部署优化 **~2.5×** throughput；在线 majority → disaggregated runtime。

## 批判性分析

### 论证链条

论文从生产痛点出发：Llama 级推理在硬件、5D 并行、runtime 与优化技法交织下形成 **数百万** 配置组合，手工启发式无法跟上架构迭代。核心论证是 **benchmark 驱动轻量模拟器** 可在分钟级搜索百万组合、以 ±5% 误差预测端到端吞吐，从而在 TTFT/TTIT SLO 约束下量化 QPS_cluster。由此导出三条可行动结论：（1）prefill 计算密集、decode 带宽密集 → **phase-specific 并行** 优于一刀切；（2）严格 SLO 的在线场景 **[[Disaggregation]]** 一致优于 continuous batching（70B **1.5–1.8×**、405B **1.8–2.2×**）；（3）异构硬件映射与平台选型可带来 **15–25%** 乃至 **2–3×** 成本效率差异。整体部署优化约 **2.5×** 吞吐、在线 majority 迁 disagg 省 **~30%** 容量，形成「模拟器探索 → 生产验证 → 方法论输出」闭环。与 Vidur/Sarathi-Serve 等互补：后者优化「怎么跑」，本文优化「部署什么配置」。

### 假设压力测试

- **模拟器精度假设**：operator 插值 + collective/runtime 叠加可预测 median 吞吐；**压力点**在 P99 尾延迟、网络抖动、未见 shape 外推——模拟器偏 mean/median，tail 决策需谨慎。
- **Disagg 最优假设**：KV 传输与双池运维成本可接受；**失效场景**为离线 sole-throughput 目标（70B 上 cont.batch 甚至略胜），此时 disagg 运维 ROI 不成立。
- **剪枝保留最优假设**：违 SLO/内存、非 2 幂并行度等激进剪枝仍保留最优附近解；**失效场景**为 GB200 NVL72 等非 8 卡拓扑，搜索规则需扩展。
- **异构/MoE 假设**：真实卡价与 empirical routing 可用；**压力点**在 expert load 漂移、cold expert、跨地域调度——结论方向可迁移，数值依赖 Meta 内部 cost model，外推需自备价格表与 routing 分布。
- **可复现性假设**：10 万+ microbench 方法论可迁移；**压力点**在 Meta Inference Team 一手数据、精确 SLO/卡型抽象，开源生态无法直接跑同款 explorer，对 [[vLLM]]/SGLang 指导停留在配置层而非 runtime 代码层。

### 实验可信度

- **验证强度**：多样并行场景模拟 vs 实测 **±5%**（Fig. 8），对 capacity planning 类中位数决策可信度高；**近十亿 MAU** 生产迁移（在线 majority → disagg、整体 **~2.5×**）提供罕见规模的外部效度。
- **证据边界**：论文以 case study + 生产洞察为主，非 microbenchmark 竞赛；disagg 倍数、异构节省等数字来自模拟器在特定 workload/SLO 下的排名，非全空间穷举证明。
- **可重复性**：方法论与剪枝逻辑可复用，但模拟器本体与 benchmark 数据集未开源，独立团队需自建 operator 库与 workload 表才能复现 Meta 数值。
- **遗漏风险**：multi-tenant 干扰、弹性池缩放、KV tiering 等未联合建模；结论绑定 Llama/MoE 周期，随下一代模型/卡刷新需重跑探索。

## 局限与后续工作

- 开源或标准化配置探索工具与 benchmark 数据集。
- 更强 tail latency / multi-tenant 干扰建模。
- Agentic 超长 context、实时语音等新兴 workload 属性表扩展。
- 与自动弹性池缩放、KV tiering 的联合优化。

## 相关

- **Runtime**：continuous batching、[[Disaggregation]]、DistServe、Splitwise
- **并行**：Tensor/Pipeline/Expert/Context/Data Parallelism
- **硬件**：H100、H200、MI300X、NVLink Switch
- **模型**：Llama、[[MoE]]、MLA
- **方法**：roofline、design space exploration、Agrawal simulator 类工作
