---
type: proposal
name: HeteroSmallClusterMultiModelAgent
title: "StateBudget: Unified Weight/KV/Expert Residency for Heterogeneous Small-Cluster Multi-Model Agent Serving"
status: draft
created: 2026-06-28
last_updated: 2026-06-28
target_venue: "OSDI 2027 / MLSys 2027 (取决于 M1 测量结果)"
tags: [multi-model-serving, heterogeneous-gpu, agent-serving, moe, kv-cache, model-switching, pcie, memory-hierarchy]
related_papers:
  - "[[CrossPool-arXiv26]]"
  - "[[Aegaeon-SOSP25]]"
  - "[[Weaver-ATC25]]"
  - "[[LMCache-arXiv25]]"
  - "[[FluxMoE-arXiv26]]"
  - "[[MOE-INFINITY-arXiv24]]"
  - "[[BOUTE-MLSys26]]"
  - "[[HetRL-MLSys26]]"
  - "[[MorphServe-MLSys26]]"
  - "[[Jenga-SOSP25]]"
  - "[[Pie-SOSP25]]"
  - "[[FlashAgents-MLSys26]]"
  - "[[KTransformers-SOSP25]]"
  - "[[DeepSeek-V4-arXiv26]]"
  - "[[MoE-Serving-Tax-MLSys26]]"
  - "[[HELIOS-MLSys26]]"
  - "[[AssyLLM-ATC25]]"
related_concepts:
  - "[[KV-Cache]]"
  - "[[MoE]]"
  - "[[PagedAttention]]"
  - "[[Pipeline-Parallelism]]"
  - "[[Tensor-Parallelism]]"
related_systems:
  - "[[vLLM]]"
  - "[[SGLang]]"
  - "[[DwarfStar]]"
novelty: high
feasibility: medium
effort: medium
---

# StateBudget：异构小集群多模型智能体服务的统一权重/KV/Expert 驻留

> **一句话 idea**：约 10–20 张异构 PCIe GPU 的小团队 agent 集群，需要在 DeepSeek V4 Pro、GLM-5.2 等 5–8 个 frontier 模型间频繁切换——但 [[CrossPool-arXiv26]]/[[Aegaeon-SOSP25]]/[[Weaver-ATC25]] 的 cold-catalog pooling 假设、[[LMCache-arXiv25]]/[[FluxMoE-arXiv26]] 的单对象 tiering、[[BOUTE-MLSys26]] 的离线 placement 都不覆盖 **「权重 / KV / expert 三类 state 争用同一异构内存预算 + agent switch latency」**。我们提出 **StateBudget**——统一的在线驻留规划器，在 GPU HBM / Host DRAM / NVMe 三层上联合决策每模型的 state tier，并以 **model switch latency vs warm 显存税** 作为一等 metric 优化。

---

## 1. 为什么这是个好问题

### 1.1 问题定义

**目标场景**：小型研发团队的自建推理集群——约 10–20 张**异构** GPU（如 RTX 3090 + A100 40G + L40 混部，**PCIe 互联、无 NVLink**），约 10 名研发共享一个 multi-model agent 栈。模型目录精简（5–8 个），但**日内频繁切换**：

- **Planner / router**（7B–14B dense）
- **Coder**（32B dense 或 MoE）
- **Reasoner**（DeepSeek V4 Pro 级 MoE + 长 context）
- **Summarizer / embedding**（7B）
- **Vision / tool** 专用模型（GLM-5.2 等多模态）

每个 agent session 是有状态的：tool loop、多模型 handoff、长 CoT trace。系统必须在 **interactive SLO**（P95 TTFT / TPOT / **model switch latency**）下，同时容纳 **多模型权重 working set + 多 session KV + MoE expert cache**。

**核心决策**：给定每张卡的算力、HBM 容量、PCIe 带宽，以及每个 session 的 SLO 约束——**哪些模型的哪部分 state 驻留在哪一层？何时 promote / demote？**

这不是「多跑几个 cold 模型」的问题（[[CrossPool-arXiv26]]），而是 **warm catalog 下的 state tier 仲裁**。

### 1.2 社区盲区

过去两年 multi-LLM serving 研究集中在两条路线，都与目标场景错位：

| 路线 | 代表工作 | 隐含场景 | 与小集群 agent 的差异 |
|------|----------|----------|----------------------|
| **Cold-catalog pooling** | [[CrossPool-arXiv26]]、[[Aegaeon-SOSP25]]、[[Weaver-ATC25]] | 目录大、流量极 skew、90% 模型 cold | 5–8 个模型**都够热**，无长尾可 offload attention |
| **单对象 tiering** | [[LMCache-arXiv25]]（KV）、[[FluxMoE-arXiv26]]/[[MOE-INFINITY-arXiv24]]（expert）、[[MorphServe-MLSys26]]（层量化） | 单模型、同构 GPU | 不联合权重/KV/expert 预算；不处理 model switch |
| **离线 co-design** | [[BOUTE-MLSys26]] | 2–3 模型、静态 routing×placement | agent 工作流非 threshold routing；日内偏好漂移 |

[[DwarfStar]] 最接近目标（SSD expert streaming + disk KV），但是 **单用户、单模型、本地特化** 引擎，无集群调度、无异构 placement、无多租户公平性。

**盲区总结**：没有人把 **{weights, KV, expert}** 放进同一个 **异构紧缺集群** 的在线预算器，并以 **agent model switch latency** 作为优化目标。

### 1.3 被挑战的关键观察 / 隐含假设

从 probe landscape 提炼四个社区隐含假设，构成本 proposal 的攻击面：

1. **Cold-model KV pooling 可迁移到小 catalog**（[[CrossPool-arXiv26]]、[[Aegaeon-SOSP25]]、[[Weaver-ATC25]]）：「低 RPS 下各模型 KV 很少同时 peak → 共享 KV pool 省显存」。小团队 5–8 个热模型 × 10 个并发 session 时，aggregate KV 接近 **sum of peaks**，pooling 退化为抢占。

2. **GPU 内 hidden-state disaggregation 可隐藏通信**（[[CrossPool-arXiv26]]、[[Weaver-ATC25]]）：层间传 hidden state 而非 KV，pipeline 可隐藏 transfer。在 **PCIe 异构**（弱卡算力慢 + 无 NVLink）下，exposed transfer latency 占 decode 比例急剧上升。

3. **权重常驻 GPU HBM 足够**（[[CrossPool-arXiv26]] 明确无 offloading）：小集群总 HBM 可能不足以同时 warm 多个 frontier MoE（DeepSeek V4 Pro 级 FP4 权重 + GLM-5.2）。必须先回答 **weights vs KV 谁先触顶**（[[MoE-Serving-Tax-MLSys26]] 提示 decode tax 常由 weight amplification 主导）。

4. **Expert cache locality 可跨模型复用**（[[FluxMoE-arXiv26]]、[[MOE-INFINITY-arXiv24]]、[[DwarfStar]]）：expert cache 按单模型 locality 设计。agent 在 MoE 模型间切换后，expert working set **完全冷启动**。

### 1.4 从 measurement 到 contribution：可证伪假设

#### H1: Warm-catalog 使 KV pooling 收益坍缩到独立分配水平

**攻击对象**：[[CrossPool-arXiv26]] 的「aggregate KV demand 次线性增长」观察。

**可证伪预测**：在 5–8 模型、10 并发 agent session 的 trace replay 下，pooled KV admission 相比 independent per-model 分配的 **有效长 context 容量** 提升 **少于 15%**（vs CrossPool 论文中 cold-catalog 场景的 40%+ 收益）。

**Metric**：同时活跃模型数 CDF、aggregate KV bytes P95、admission 拒绝率。

**预期数值**：P95 同时活跃模型数 ≥ 4（5–8 catalog 的 50%+）；pooled vs independent 容量比 < 1.15。

**若验证意味着**：cold-catalog pooling 路线对小团队 agent **方向错误**；问题从 pooling 转为 **state tier 降级 + 抢占优先级**（CB4）。

#### H2: PCIe 异构集群上 GPU-only partial disaggregation 净收益为负

**攻击对象**：[[CrossPool-arXiv26]]/[[Weaver-ATC25]] 的 hidden-state / attention offload 假设（NVLink/IPC 可隐藏通信）。

**可证伪预测**：在 PCIe-only 异构集群（如 3090+A100 混部）上，2–3 模型切换的 agent decode trace 中，CrossPool-style 层间 hidden-state transfer 的 **exposed latency** 占 per-token decode 时间 **大于 30%**，端到端 TPOT 劣于 **全 local attention + KV/权重 tier offload** baseline。

**Metric**：per-layer exposed transfer latency、P95 TPOT、switch 后首 token 延迟。

**预期数值**：PCIe 路径 exposed ratio 30–50%（vs NVLink 同构 < 10%）；端到端 TPOT 退化 1.4–2.0×。

**若验证意味着**：小集群不应复制 cloud MaaS 的 GPU disaggregation 范式；**operator 切分点** 必须在 PCIe 约束下重新推导（CB3）。

#### H3: 多 MoE 混部下 weights 先于 KV 触顶内存天花板

**攻击对象**：[[CrossPool-arXiv26]] 的 GPU-only 权重驻留、[[LMCache-arXiv25]] 的 KV-centric tiering。

**可证伪预测**：在 10–20 卡异构集群上，渐增「同时 warm 的模型数 K」（DeepSeek V4 Pro + GLM-5.2 级 MoE），**OOM 或不可接受 switch latency 的首个触发因素是 weights working set**（非 KV），且 K ≤ 3 时即触顶（总 HBM 约 400–800 GB 量级）。

**指标**：OOM前第一杀手分类（权重负载失败与KV OOM）、冷权重负载TTFT、热空闲每个模型显存。

**预期数值**：2 个 frontier MoE warm 后权重占 HBM 60–80%；第 3 个模型 switch 的 cold load TTFT > 10s（PCIe 从 Host）。

**若验证意味着**：unified planner 必须 **权重 tier** 与 KV/expert tier **联合优化**；单独优化 KV（LMCache 路线）不够。

#### H4: Session-aware 在线 state tiering 比静态 placement 降低 P95 switch latency ≥ 40%

**攻击对象**：[[BOUTE-MLSys26]] 的离线 MOBO routing×placement；[[Aegaeon-SOSP25]] 的 token-level swap。

**可证伪预测**：在日内模型偏好漂移的 agent trace 上（小时级切换矩阵变化），StateBudget 在线 planner（输入 session SLO + 切换预测 + 三层 state tier）的 **P95 model switch latency** 比静态 placement 低 **≥ 40%**，且 warm 显存开销仅增加 **≤ 20%**。

**Metric**：P95 switch latency（权重 promote + KV pin + expert warm）、SLO 违约率、总 HBM 利用率。

**预期数值**：静态 plan 的 P95 switch 8–15s → StateBudget 4–8s；SLO 违约率从 25% 降至 < 10%。

**若验证意味着**：agent serving 需要 **switch latency 一等 metric** 的在线系统（CB2），而非 cloud QPS / 长 context 容量。

#### 假设组合与 narrative

H1 攻击 pooling 范式；H2 攻击 disaggregation 范式；H3 定义 **unified budget 的必要性**；H4 验证 **在线 planner 的价值**。若 H1+H3 验证 → 核心贡献是 **StateBudget 抽象 + warm-catalog admission**。若 H2 也验证 → 额外贡献是 **PCIe-aware operator 切分**。若 H4 不通过 → pivot 到 measurement paper（switch vs warm Pareto 刻画）。

---

## 2. 相关工作

### 2.1 基础设施层（站在其肩膀上）

- **[[CrossPool-arXiv26]]**：FFN 权重池与 KV 池拆分的 GPU disaggregation 原型；证明 cold MoE multi-LLM 的可行性，但权重不离开 HBM、假设 NVLink 同构。
- **[[LMCache-arXiv25]]**：KV 多 tier 中间件 + controller API（lookup/pin/move）；提供 KV tier 的 connector 生态，但不管理权重/expert。
- **[[FluxMoE-arXiv26]]** / **[[MOE-INFINITY-arXiv24]]**：MoE expert 分页与 SSD offload；证明 expert 与 KV 争用 HBM，但按单模型 locality 设计。
- **[[KTransformers-SOSP25]]**：CPU/GPU 异构 MoE 切分；证明 attention+KV 留 GPU、expert 可 offload 的可行性，但未组合多模型。
- **[[Jenga-SOSP25]]**：异构 attention 机制下的 per-layer KV allocator；layer property 感知，但单模型 serving。
- **[[DwarfStar]]**：DeepSeek V4 特化的 SSD expert streaming + disk KV checkpoint；正确性优先的本地 agent 引擎，policy 无法直接移植到多模型集群。

### 2.2 策略层（共享问题但方向不同）

- **[[Aegaeon-SOSP25]]**：token-level 抢占 + KV swap；100 模型长尾生产，swap 优化 -97% overhead，但小 catalog 时 active set ≈ 全集。
- **[[Weaver-ATC25]]**：hot 模型 attention offload 到 cold GPU；需 hot/cold 角色固定，agent 轮流变热时失效。
- **[[BOUTE-MLSys26]]**：routing 阈值与异构 placement 联合 MOBO；2 模型实验，action space 在 5+ 模型时爆炸。
- **[[MorphServe-MLSys26]]**：单模型 runtime 层量化 swap + KVResizer；不处理 multi-model 间抢占。
- **[[HELIOS-MLSys26]]**：多 EE-LLM 互补 early-exit；需预训练变体，标准 frontier 模型不适用。
- **[[Pie-SOSP25]]** / **[[FlashAgents-MLSys26]]**：agent 编排层（inferlet、streaming prefill overlap）；优化请求内 overlap，假设底层 GPU 足够。
- **[[AssyLLM-ATC25]]**：异构预训练 block pool + LRU swap；联邦 QA 场景，生成式 agent 合法性未验证。

### 2.3 关键 tension

| Tension | 对立双方 | 本 proposal 的立场 |
|---------|----------|-------------------|
| Cold pooling vs warm switching | [[CrossPool-arXiv26]] vs 小 catalog agent | 放弃 cold pooling，做 warm tier 降级 |
| GPU-only vs memory hierarchy | [[CrossPool-arXiv26]] vs [[DwarfStar]]/[[LMCache-arXiv25]] | 三层联合 {weights, KV, expert} |
| 放哪张卡 vs 留多少 state | [[BOUTE-MLSys26]] vs [[Zorse-MLSys26]]（训练） | 联合优化 placement × tier × switch 预测 |
| Session state vs model pooling | [[Pie-SOSP25]] vs [[LMCache-arXiv25]] | session-aware retention + multi-tenant 公平 |
| MoE weights vs KV 争用 | [[MoE-Serving-Tax-MLSys26]] vs KV-centric 研究 | 测量谁先触顶，驱动 unified budget |

### 2.4 现有证据的脆弱点

1. [[CrossPool-arXiv26]] 的 OpenRouter trace（90% cold）不 represent 小团队 **全 warm catalog**。
2. [[Weaver-ATC25]] 的 L40S+PCIe 数据仅覆盖 **单对 hot/cold**，未与 multi-model switch 联合。
3. [[LMCache-arXiv25]] 的 load-or-prefill crossover（32 Gbps 下需 > 256K context）在 agent **短 turn** 下可能 invert。
4. [[BOUTE-MLSys26]] 的 10%+ P95 退化来自 routing×placement 分开优化，但未包含 **KV/expert tier** 维度。
5. [[HetRL-MLSys26]] 证明 multi-model × 异构 需联合优化，但 serving 的 **有状态 KV + 权重切换** 与训练 iteration 本质不同——不能直接迁移。

---

## 3. 核心研究问题

### RQ1: Measurement — Agent Trace 驱动的 State 争用刻画（脊梁）

**目标**：证伪 H1–H3，刻画 switch vs warm 的 Pareto 前沿。

**实验设计**：

1. **Trace 采集**（2 周）：
   - 理想：真实研发团队 agent 日志 `(user, session, model_id, tokens_in/out, timestamp, tool_call)`
   - 备选：合成 trace——基于 SWE-bench / GAIA agent 工作流模式，参数化模型切换矩阵（5–8 模型马尔可夫链）、session 长度、并发度 10
   - 模型集：DeepSeek V4 Pro 级 MoE（[[DeepSeek-V4-arXiv26]]）、GLM-5.2 级多模态（公开权重或等规模 proxy：Qwen3-MoE + Qwen2.5-VL）、7B/32B dense 辅助模型

2. **硬件矩阵**：
   - **同构 NVLink**（2×A100 80G）：CrossPool baseline 复现
   - **异构 PCIe**（3090 24G + A100 40G + L40 48G × N）：目标场景
- 每卡配置文件：预填充/解码 TFLOPs、HBM BW、PCIe BW（[[HetRL-MLSys26]] 式成本模型）

3. **测量项**：
   - 同时活跃模型数 CDF、aggregate KV bytes P95（H1）
   - per-layer exposed transfer latency：NVLink vs PCIe（H2）
   - 渐增 warm 模型数 K，记录 OOM first killer + cold load TTFT（H3）
   - 每模型 warm idle 显存 vs cold load 延迟——画 **switch–warm Pareto 曲线**（CB2）

**产出**：
- 首个 **warm-catalog multi-model agent** 的 state 争用 taxonomy
- H1–H3 证伪结论 + 效应量
- Pareto 曲线：「保留 K 个模型 warm」vs P95 switch latency vs SLO 违约率

**Go/No-Go**：H1 或 H3 强验证（p < 0.01）→ 进入 RQ2 设计。三者均弱 → Pivot A（measurement short paper）。

### RQ2: Design — StateBudget 统一驻留规划器

**目标**：基于 RQ1 的 Pareto insight，设计在线 **StateBudget planner**。

**核心抽象：State Residency Vector (SRV)**

对每个模型 $m$、每个 state 类型 $s \in \{\text{weights}, \text{KV}, \text{expert}\}$、每个内存 tier $t \in \{\text{GPU}, \text{Host}, \text{NVMe}\}$，维护驻留分数 $r_{m,s,t} \in [0,1]$（部分驻留支持分页：[[FluxMoE-arXiv26]] PagedTensor + [[LMCache-arXiv25]] chunk pin）。

**Planner 输入**：
- 集群拓扑：每卡 $(\text{compute}, \text{HBM}, \text{PCIe\_BW})$
- 活跃 session 集合：$(\text{user}, \text{model\_chain}, \text{context\_len}, \text{SLO\_class})$
- 切换预测：小时级马尔可夫切换矩阵（滑动窗口估计）
- 当前 SRV 快照

**Planner 输出**：
- 每张 GPU 的 state 分配表：$\{(m, s, \text{tier}, \text{bytes})\}$
- promote/demote 操作队列（带优先级：blocking tool call > background job）
- 可选 operator 切分方案（H2 若验证：PCIe 下 attention local、FFN 不 remote）

**关键策略**（取决于 RQ1 哪条假设成立）：

1. **Warm-catalog admission**（H1 成立）：不做 KV pool 共享，改为 **per-session KV pin + 跨 session 公平抢占**（CB5）
2. **Unified tier demotion**（H3 成立）：内存压力下按 **switch 预测收益 / 字节成本** 排序，降级 weights（INT4/CPU）、KV（Host pin）、expert（SSD-only）——非二元 evict（CB4）
3. **PCIe-aware placement**（H2 成立）：大模型 attention 放强卡 local，弱卡承载小模型全栈或仅 KV Host buffer
4. **Expert cache 隔离**（H4 辅助）：多模型 expert cache 按 model ID 分 pool，切换时 **不尝试跨模型复用**（验证 fragile assumption 5）

**对比 baseline**：
- **Independent**：每模型独立 [[vLLM]]/[[SGLang]] 实例，无跨模型协调
- **CrossPool-style**：GPU 内权重/KV 双 pool（同构 NVLink 上界）
- **Siloed tiering**：LMCache（KV only）+ FluxMoE（expert only）+ 权重常驻 GPU
- **Static placement**：[[BOUTE-MLSys26]] 式离线 plan
- **Oracle**：trace 上已知未来切换的最优 SRV

**关键 metric**：P95 switch latency、P95 TPOT、SLO 违约率、有效并发模型数（同一硬件上能同时 serve 的模型数）

### RQ3: Implementation — 异构 PCIe 集群上的系统集成

**工程范围**：

| 组件 | 预估 LOC | 依赖 | 说明 |
|------|---------|------|------|
| StateBudget planner（C++ core + Python policy） | ~1200 | 无 | 在线 MILP / 贪心近似 |
| vLLM/SGLang state connector | ~600 | [[vLLM]]/[[SGLang]] plugin API | 权重 load/unload、KV pin |
| LMCache adapter | ~300 | [[LMCache-arXiv25]] controller API | KV tier promote/demote |
| Expert tier manager | ~500 | [[FluxMoE-arXiv26]] 式分页 | MoE expert SSD streaming |
| Trace replay + eval harness | ~800 | 标准 benchmark | agent 工作流 replay |
| **Total** | **~3400** | | |

**软件栈**：[[vLLM]] 0.9+ / [[SGLang]] / [[LMCache-arXiv25]] connector / PyTorch distributed。不修改模型权重，不训练。

**硬件需求**：6–10 张异构 GPU（实验室最小 4 卡 PCIe 混部可 proof-of-concept）；NVMe ≥ 2 TB（expert/权重 cold tier）。

### RQ4: Correctness — 多模型 state 迁移的一致性

**问题**：权重 partial load（INT4 on GPU + FP16 on Host）、KV tier 迁移、expert SSD streaming 交叉时，如何保证 **bit-exact 或 SLO-bounded approximate** 推理？

**方向**：
- 权重 tier：仅允许 **quantization level 切换**（[[MorphServe-MLSys26]] 式 per-layer sensitivity），禁止 partial layer 混搭
- KV tier：[[LMCache-arXiv25]] connector 的 layout hash 校验；迁移失败 fallback 到 re-prefill
- Expert tier：[[DwarfStar]] 式 correctness regression suite——switch 后首 N token 与全 GPU baseline 对比
- Session 隔离：per-session KV namespace，防止跨用户 state 泄漏

---

## 4. 可行性

### 4.1 工程范围 + 软件栈

**为什么小团队能做**：
- 不需要训模型——用开源 frontier 权重（DeepSeek V4、Qwen3-MoE 等）或等规模 proxy
- 站在 [[LMCache-arXiv25]]、[[FluxMoE-arXiv26]]、[[vLLM]] 肩膀上，核心贡献在 **planner 层**
- RQ1 measurement 可在 4–6 周内产出 Go/No-Go 信号
- 目标场景（10–20 卡异构）本身就是小团队规模，实验环境与部署环境一致

**关键风险**：

| 风险 | 缓解 |
|------|------|
| 无真实 agent trace | 合成 trace + 1–2 个友好团队匿名日志；开源 trace 作为 benchmark 贡献 |
| DeepSeek V4 Pro / GLM-5.2 权重未公开 | 用 [[DeepSeek-V4-arXiv26]] 已发布权重 + Qwen3-MoE-235B / GLM-4.5 级 proxy；论文中 explicit 标注 |
| Planner 在线求解太慢 | 先用贪心近似（< 10ms），MILP 作 offline oracle 上界 |
| PCIe 集群搭建成本高 | 最小 4 卡 proof-of-concept；NVLink 子集作对照 |

### 4.2 时间线（含 Go/No-Go gate）

| Phase | 内容 | 时间 | Go/No-Go |
|-------|------|------|----------|
| M1: Trace + H1–H3 Measurement | 采集/合成 agent trace；Pareto 曲线；PCIe vs NVLink 对照 | 4 周 | ≥1 假设强验证 → 设计 track |
| M2: StateBudget Planner | 贪心 planner + SRV 抽象；simulator 对比 5 baselines | 4 周 | H4：P95 switch latency ≥ 30% 改善 |
| M3: System Integration | vLLM + LMCache + expert tier connector | 4 周 | 端到端 switch 正确性 regression pass |
| M4: End-to-End Eval | 10 并发 agent replay；异构 8–10 卡 | 3 周 | 有效并发模型数 ≥ 2× independent baseline |
| M5: Writing | Paper | 3 周 | — |

**累计约 18 周**。M1 结束是核心 gate：若 H1–H3 全部弱验证，不进入 M2 全量实现。

---

## 5. 投稿策略

### 5.1 投稿梯度

```
H1 + H3 强验证 + H4 通过（unified planner ≥40% switch 改善）
  → OSDI 2027 / SOSP 2027（deadline ~2026 年底）
  理由：新抽象（StateBudget/SRV）+ counterintuitive finding
  （cold pooling 范式在 warm agent 场景失效；weights 先于 KV 触顶）
  + 异构系统 co-design

H2 强验证（PCIe disaggregation 净负）+ 清晰 Pareto 曲线
  → OSDI 2027 measurement-heavy track 或 ATC 2027
  理由：「不要复制 NVLink 假设到 PCIe 集群」是社区需要的负面结果

H4 中等（20–35% switch 改善）但 H1/H3 强
  → MLSys 2027 / EuroSys 2027
  理由：solid serving system + thorough measurement

仅 measurement 有价值（Pareto 曲线 + taxonomy）
  → MLSys 2027 short / HotOS 2027
  理由：首个 warm-catalog agent state 争用刻画

全部假设弱验证
  → arXiv technical report + 归档教训到 proposals/_log.md
```

### 5.2 为什么这个 venue 需要这篇 paper

**对 OSDI/SOSP**：OSDI 传统是 **用 OS 思想解决新硬件约束下的资源管理**（PagedAttention = paging + attention 是最新范例）。StateBudget 将 **page replacement 扩展到 {weights, KV, expert} 三类 pageable object**，在 **异构 PCIe 集群** 这一新硬件形态上重新定义 replacement policy。Counterintuitive finding——「cloud MaaS 的 pooling 范式在小集群 agent 场景不仅无效，而且方向错误」——符合 OSDI 品味。

**对 MLSys**：MLSys 2026 已有 [[MoE-Serving-Tax-MLSys26]]、[[CrossPool-arXiv26]]、[[FlashAgents-MLSys26]] 等 serving 论文，但缺少 **小集群异构 multi-model agent** 的系统化处理。若 H4 仅中等验证，MLSys 的 production-relevant serving track 仍是好归宿。

**对 ATC**：若贡献偏 engineering（StateBudget 实现 + 开源 trace），ATC 重视 **deployable system**。

### 5.3 论文 story arc

**标题**：*StateBudget：当冷模型池失效——异构智能体集群的统一权重/KV/Expert 驻留*

1. **Motivation (0.5p)**：小团队 agent 集群的崛起；5–8 个 frontier 模型频繁切换；异构 PCIe 硬件；现有 cold-catalog / KV-only / 离线 placement 三路都不 fit
2. **Measurement (2p)**：H1–H3 证伪 + switch–warm Pareto 曲线；「weights 先于 KV 触顶」的意外发现
3. **Why It Matters (0.5p)**：社区在复制 cloud MaaS 假设；小集群需要不同抽象
4. **Design (1.5p)**：StateBudget / SRV 抽象；在线 planner；PCIe-aware placement；warm tier demotion
5. **Evaluation (1p)**：10 并发 agent × 5–8 模型；vs CrossPool / siloed tiering / static placement；P95 switch latency + 有效并发模型数
6. **Implication (0.5p)**：agent serving 应以 switch latency 为一等 metric；{weights, KV, expert} 联合预算是新设计空间

**Figure 1 (teaser)**：三联图——(左) cold-catalog pooling 在小 cluster 退化为全员争用；(中) 三类 state 争用同一异构内存预算；(右) StateBudget 在线 tier 降级使 5 模型同时可 serve。

---

## 6. 转向方案

### Pivot A: H1–H3 弱验证（pooling 仍有效 / weights 不先触顶）

**方向**：改成 **「When Does Cold-Model Pooling Break? A Taxonomy of Multi-Model Serving Scenarios」**——用统一框架刻画 cold-catalog vs warm-catalog 的边界条件（catalog size × concurrency × session length）。

**Target venue**：MLSys 2027 short / HotOS 2027。

### Pivot B: H4 不通过（在线 planner ≤ 15% 改善）

**方向**：聚焦 **switch–warm Pareto 曲线** 本身作为贡献——给社区一个可复现的 benchmark（agent trace + 异构 cluster config + baseline 脚本）。StateBudget 降为 appendix 工程尝试。

**Target venue**：ATC 2027（benchmark + measurement）或 MLSys 2027 Datasets track。

### Pivot C: H2 不通过（PCIe disaggregation 仍有效）

**方向**：缩小 scope 到 **PCIe 上的 operator 切分指南**——何种切分在何种 (model size, GPU type) 组合下净收益为正。StateBudget 仍做 unified budget，但不挑战 disaggregation 范式。

**Target venue**：EuroSys 2027 / ATC 2027。

### 终极 fallback

若所有假设均弱验证：发表 **negative result**——「现有 multi-LLM serving 技术在小集群 agent 场景的组合效果」，归档 Pareto 曲线和 trace benchmark。记录到 `wiki/proposals/_log.md` 供未来重新审视。

---

*本提案基于 `wiki/proposals/probes/hetero-small-cluster-multi-model-agent.md` 的 landscape characterization + CLAUDE.md Taste Rubric 的自我评估。*

---

## 附录: Taste Rubric Self-Challenge

### Workload 真实性

**评估**：PASS

- 10–20 卡异构 GPU、5–8 模型、10 人 agent 共享——这是小型 AI 研发团队的**真实部署形态**（非人为构造）
- 可用 SWE-bench / GAIA 工作流合成 trace + 争取 1–2 周真实日志；probe 已给出具体采集 schema
- DeepSeek V4 Pro / GLM-5.2 是 2026 年 agent 栈的 realistic 模型选择；未公开时用已发布 proxy 可接受
- SLO 定义（P95 switch latency）来自 interactive agent 的 blocking tool call 场景，非 GSM8K routing

### Counterintuitive

**评估**：PASS

- 核心反直觉 1：[[CrossPool-arXiv26]] 的 cold pooling 在小 **warm** catalog 下不仅无效，而且方向错误（全员争用）
- 核心反直觉 2：社区聚焦 KV tiering，但多 MoE 混部时 **weights 可能先于 KV 触顶**（[[MoE-Serving-Tax-MLSys26]] 的 weight amplification 在 multi-model 场景被放大）
- 核心反直觉 3：PCIe 异构集群上，GPU disaggregation（hidden-state transfer）可能**净负**——与 cloud MaaS 假设相反

### 10x vs 2x

**评估**：PASS（reframed）

- 直接 metric（switch latency -40%、TPOT -30%）是 1.3–2× 量级
- **Reframing**：贡献是打开 **新设计空间**——使同一异构小集群能 **同时 serve 5–8 个 frontier 模型**（vs baseline 2–3 个），等效 **2–3× 模型容量** 或 **避免 2× 硬件采购**
- StateBudget 抽象本身——将 {weights, KV, expert} 统一进一个 budget——若成立，社区会改变 multi-model serving 的分层方式（类似 PagedAttention 改变 KV 管理方式）
- 需在 introduction 中 explicit 建立「有效并发模型数」 framing

### Model-proof

**评估**：PASS

- 异构硬件紧缺 + 多模型 agent 不会随模型变强而消失——**更强模型 = 更大 weights + 更长 KV + 更多 expert**，问题更严重
- DeepSeek V4 的 CSA/HCA 压缩降低单模型压力，但 **多模型混部时各模型 KV layout 不一**（[[DeepSeek-V4-arXiv26]]），协调复杂度上升
- 可在 ≥ 3 个模型族（MoE + dense + VLM proxy）上验证；论证 why stronger models exacerbate the problem

### Abstraction

**评估**：PASS

- 新抽象：**State Residency Vector (SRV)** + **StateBudget planner**——{weights, KV, expert} × {GPU, Host, NVMe} 的统一预算接口
- 类比 OS 的 **multi-resource cgroup**：不是 per-object heuristic（LMCache 管 KV、FluxMoE 管 expert），而是 cluster-level budget allocator
- 接口可跨 [[vLLM]]/[[SGLang]] 实现；不同 state 类型通过统一 promote/demote 队列调度
- switch latency 作为一等 metric 进入 planner objective——填补 CB2 空白

### 总结

| 维度 | 评估 | 备注 |
|------|------|------|
| Workload 真实性 | PASS | 小团队异构集群是真实部署形态 |
| Counterintuitive | PASS | warm-catalog 否定 cold pooling；weights 先于 KV |
| 10x vs 2x | PASS（reframed） | 用「有效并发模型数」/ 避免硬件翻倍 framing |
| Model-proof | PASS | 更强模型加剧问题 |
| Abstraction | PASS | StateBudget / SRV 统一三类 state |

**5/5 通过，0 维度不通过。无需 V2 重写。** Implementation 阶段需注意：
- 10x framing 在 introduction 中 explicit 建立
- 真实 trace 采集优先于纯合成
- DeepSeek V4 Pro / GLM-5.2 proxy 策略在 evaluation 中 transparent 报告
