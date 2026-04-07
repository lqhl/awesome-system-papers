---
status: todo
date: 2026-04-05
keywords:
  - LLM Serving
  - Disaggregated Inference
  - Measurement
  - Counter-Consensus
  - Empirical Study
target: MLSys 2027
---

# When Does Disaggregation Win? A Crossover Audit of P/D Serving for Production LLM Workloads

> **一句话定位**：Prefill-decode disaggregation（DistServe、Splitwise、Mooncake）在 2024-2025 成为 LLM serving 的新正统，但其代价-收益在真实生产 workload 下从未被系统审计过。本工作用严格的实证方法构建 **disaggregation crossover map**，回答 "什么时候 disagg 真的赢，什么时候 co-located chunked-prefill 反而更好"。

---

## 一、核心观察与研究动机

### 1.1 Disaggregation 已成为新正统

2024 年 DistServe（OSDI'24）和 Splitwise 开创 prefill-decode 分离的设计范式；2025 年 Mooncake（FAST'25）证明其在 Kimi 生产环境可行；到 2026 年，**"大规模 MoE 部署应该用 disaggregation"已经成为 MLSys 社区的默认假设**。

| 系统 | 会议 | 核心 claim |
|---|---|---|
| DistServe | OSDI'24 | TTFT/TPOT 分别优化，goodput 提升 2.0-7.4× |
| Splitwise | ISCA'24 | Phase splitting 比混合部署效率更高 |
| Mooncake | FAST'25 | KV-centric disaggregation，生产级 1.38-2.36× cache hit rate |
| Beyond the Buzz | MLSys'26 | 数据中心规模 disagg 设计空间探索 |
| SGLang PD | 2025 | 推荐用 PD disaggregation 部署大规模 MoE |

### 1.2 但它的代价从未被严格审计

Disaggregation 有三类隐性成本：
1. **KV transfer cost**：跨机 KV cache 传输（即使 NVLink/IB 也有 10-100ms 量级开销）
2. **Coordination overhead**：prefill/decode pool 间的调度同步
3. **Pool fragmentation**：prefill/decode GPU 比例固定后，流量分布变化导致 idle GPU

现有工作**只在 disaggregation 有利的场景做对比**：长 output、大模型、稳态高 QPS。但真实生产流量分布是：
- **Short-output chat**（如 ChatGPT 对话）：短 prefill + 短 decode
- **Agentic tool calling**：频繁短 LLM 调用 + 长 idle 等待
- **Bursty arrivals**：流量峰谷比 10-100x
- **Mixed sizes**：同一集群服务多种模型规模

**在这些场景下，disaggregation 可能反而输给优化良好的 chunked-prefill co-located serving。** 这是本工作要验证的假设。

### 1.3 为什么这个审计现在才值得做

1. **基础设施成熟**：vLLM chunked-prefill 2024 中达到生产级；Mooncake 2025 开源；DistServe 开源代码可用
2. **公开 trace 齐全**：Mooncake trace（2024）、Azure LLM Inference trace、LMSYS-Chat-1M、BurstGPT
3. **Agentic 时代削弱 disaggregation 前提**：prefix caching 使 prefill 开销大幅降低，disagg 的核心收益（独立优化 prefill）被部分侵蚀
4. **社区正在寻找 disagg 的边界**：Beyond the Buzz (MLSys'26) 指出 disagg 收益取决于流量模式，但没给出具体 crossover 图

---

## 二、研究问题

> **在现代 LLM 生产 workload（chat、agentic、mixed）下，disaggregated serving（DistServe/Mooncake）相对 co-located chunked-prefill serving 的 crossover 边界在哪里？有多少比例的真实 workload 实际上更适合 co-located？**

### 2.1 具体子问题

| # | 问题 | 预期发现 |
|---|---|---|
| Q1 | KV transfer 开销在不同网络拓扑下占 disagg 总延迟多少？ | Intra-rack NVLink ~5%，inter-rack IB ~15-30% |
| Q2 | 多少 output length 以下 co-located 更快？ | 预计 <128 output tokens |
| Q3 | 模型规模对 crossover 的影响？ | 小模型（7B）disagg 几乎不赢；大模型（70B+）通常赢 |
| Q4 | Bursty 到达下 prefill/decode pool 的 idle 时间？ | 流量变异系数 > 1 时可能高达 20-40% |
| Q5 | Agentic workload（prefix cache 高命中）下 disagg 的增量收益？ | 大幅下降（prefix cache 已让 prefill "免费"） |
| Q6 | Chunked prefill 的 chunk size 调优后，disagg 的优势能被追平多少？ | 在 mixed workload 下 50-70% 的场景会被追平 |

### 2.2 核心 testable hypothesis

**H1**: 在 output length < T 的场景下，co-located chunked-prefill 的 goodput-under-SLO 不低于 disaggregated serving（T 是待定的 crossover 阈值）

**H2**: 对于 7-13B 模型，在任何 output length 下，co-located ≥ disagg

**H3**: Bursty workload 下，pool fragmentation 吃掉 disagg 至少 15% 的 raw throughput advantage

**H4**: Agentic workload（> 80% prefix cache hit rate）下，disagg 的 TTFT 优势 <10%

**H5**: 在真实生产 trace 上，**40-60% 的 request 分布**处在"co-located 更好"的区域

如果所有 5 个假设都被数据支持，本工作提供了**让 disagg 正统性被重新评估的实证基础**；如果只有部分被支持，本工作提供了第一份 rigorous crossover map，仍具发表价值。

---

## 三、方法论

### 3.1 实验矩阵

**模型维度**：
- Llama-3-8B（小模型代表）
- Llama-3-70B（大模型代表）
- Qwen3-14B（中等规模 + GQA）
- Qwen3-32B / DeepSeek-V2.5-Lite（MoE 代表）

**Workload 维度**：
- Synthetic Poisson arrivals（建立 baseline）
- Mooncake trace（真实 LLM 推理流量）
- Azure LLM Inference trace（生产级多租户）
- LMSYS-Chat-1M（真实对话分布）
- BurstGPT（高 burstiness）
- **自构造 agentic trace**（短对话 + 频繁 tool call，基于 OpenHands trajectory）

**硬件维度**：
- 4× H100（1 节点）
- 8× H100（1 节点 NVSwitch）
- 16× H100（2 节点 IB）
- 可选：32× H100 extended study

**Disaggregation 配置**：
- Prefill:Decode = 1:1, 1:3, 3:1, 1:7（pool ratio sweep）
- KV transfer protocol：Mooncake LMCache、NIXL、基于 NCCL 的 naive

### 3.2 Baseline 系统

**Disaggregated baselines**：
- DistServe（官方开源）
- Mooncake（官方开源）
- **LLM-d** / vLLM v1 的原生 disagg 模式（若稳定）

**Co-located baselines**：
- vLLM v1 + chunked-prefill（2024 年以来的 SOTA co-located）
- SGLang + Sarathi-Serve-style chunked prefill
- TensorRT-LLM + inflight batching

**关键**：chunked-prefill 的 chunk size 需要单独调优（不能用 default），否则会给 disagg 虚假优势。

### 3.3 评估指标

**主要指标**：
- **Goodput under SLO**（SLO attainment rate × throughput）- 这是生产环境真实关心的指标，非 raw throughput
- **P50/P95/P99 TTFT**
- **P50/P95/P99 TPOT**
- **End-to-end latency distribution**

**诊断指标**（用于解释 crossover 原因）：
- GPU idle ratio per pool
- KV transfer 占总延迟百分比
- Chunked prefill 的 step-level decode TPOT penalty
- Cache hit rate（为 agentic workload）

**统计严谨性**：
- 每个配置 ≥ 3 seeds
- 报告 95% confidence intervals
- 用 Pareto frontier 展示多指标 tradeoff
- **Per-request category breakdown**（短/中/长 prefill × 短/中/长 decode 的 3×3 矩阵）

### 3.4 Crossover Map 构建

对每个 (model × workload × hardware) 组合，绘制**二维 crossover chart**：
- X 轴：average output length
- Y 轴：arrival rate (QPS)
- 热力图颜色：(disagg_goodput / colocated_goodput) 比值
- 标注 crossover 等值线（比值 = 1.0）

**最终产出**：一张或一组 "decision chart"，告诉从业者："如果你的 workload 处于 (output_len, QPS, burstiness, model_size) 区域 X，建议部署 disagg；否则 co-located。"

---

## 四、与现有工作的差异化

### 4.1 vs. "Beyond the Buzz" (NVIDIA, MLSys'26)

NVIDIA 的论文是**基于模拟器的设计空间探索**：
- 纯模拟，无真实系统验证
- 聚焦"当 disagg 赢时应该如何配置"
- 没有给出 disagg 失败的 regime 边界

**本工作的差异**：
- 实系统、真实 trace、实测 goodput
- 聚焦 **"disagg 在什么时候不赢"** 的实证边界
- 产出 practitioners 可直接使用的 decision chart

### 4.2 vs. DistServe / Mooncake 自己的 evaluation

**这些系统自己的 evaluation 有三个方法论问题**：
1. 只在对自己有利的 workload 测试（通常 long output + steady high load）
2. Baseline 是 **vanilla vLLM 或老版本**，而非 tuned chunked-prefill
3. 指标是 **raw throughput**，不是 **goodput under SLO**

**本工作明确修正这三点**，这是"为什么这个审计没人做"的关键——原作者无动力自我审计，第三方审计才有独立价值。

### 4.3 vs. "SD: Performance or Illusion?" (MLSys'26)

这是最接近的**counter-consensus 发表模板**：
- 同样揭示学术 benchmark 与生产现实的差距
- 同样强调 batch size 的影响
- 同样提出修正视角

**本工作是对 disaggregation 范式的类似审计**，继承其方法论严谨性。

### 4.4 vs. Rethinking KV Cache Compression (MLSys'25)

NTU 的论文揭示 KV 压缩在 LMDeploy（生产系统）上效果大幅退化。**本工作对 disaggregation 做类似事情**，但范围更大、影响更深（disagg 是系统架构决策，KV 压缩只是单一优化）。

### 4.5 论文 positioning table

| 论文 | 范围 | 方法 | 发现类型 |
|---|---|---|---|
| DistServe (OSDI'24) | 提出 disagg | 系统构建 | Positive（disagg 赢） |
| Mooncake (FAST'25) | 生产部署 | 实测 | Positive（生产可行） |
| Beyond the Buzz (MLSys'26) | 设计空间 | 模拟 | Conditional（depend on workload） |
| **This work** | **边界条件** | **实测 + trace** | **Counter（disagg 不总是赢）** |
| SD: Illusion (MLSys'26) | SD 边界 | 实测 | Counter（SD 不总是赢） |

---

## 五、可行性与风险分析

### 5.1 强可行性信号

1. **基础设施全部 ready**：vLLM、DistServe、Mooncake 都开源且可部署
2. **Trace 公开**：Mooncake trace、Azure trace、LMSYS-Chat-1M 都是 public
3. **硬件需求可控**：4-16 GPU 足够（核心实验），不需要大集群
4. **不需要 build 新系统**：纯 benchmarking + analysis
5. **无模型训练**：所有模型都是开源 pre-trained

### 5.2 关键风险与缓解

| 风险 | 严重度 | 缓解策略 |
|---|---|---|
| Disagg 在所有 regime 都赢 | **高** | Phase 0 快速验证一个 short-output 场景；若 disagg 仍赢，pivot 到 "what regimes show minimal disagg wins" |
| Baseline 实现不 fair（chunked-prefill 没调好） | **高** | 花 2 周专门调 chunked-prefill；与 vLLM 社区合作验证配置 |
| DistServe/Mooncake 复现失败 | 中 | 用多个开源实现（dist-serve, Mooncake, LLM-d）交叉验证 |
| 审稿人："我们已经知道了" | 中 | 提供**定量 crossover chart**（不止定性结论）；强调 per-regime breakdown |
| 工业团队已内部做过 | 低 | 他们**无动机发表**（会伤自己系统），第三方发表仍有价值 |
| Trace 的代表性被质疑 | 中 | 用 ≥3 种 public trace + 1 种自构造 agentic trace，robustness 分析 |
| NVLink/IB 带宽差异影响结果 | 低 | 报告两种拓扑下的 crossover 曲线 |

### 5.3 最大不确定性：H1-H5 的验证

Phase 0 必须在 1-2 周内快速验证 H1 或 H2 至少一个显示 crossover 存在。

**Decision gate**：
- 若 H1 或 H2 至少一个在 quick test 中看到 crossover → 继续全 workload sweep
- 若两者都看不到 crossover（disagg 全胜） → 重定位为 "when does disagg win the least" 的 Pareto analysis
- 若 baseline 配置有问题导致 crossover 虚假出现 → 投入时间重调 baseline

---

## 六、实验规划

### Phase 0：Quick Sanity Check（2 周）

**目标**：快速验证 crossover 是否存在

- [ ] 搭建 vLLM v1（chunked-prefill tuned）+ DistServe 双 baseline
- [ ] 在 Llama-3-8B 上跑 **4 个 extreme corner**：
  - 短 prefill + 短 output + low QPS
  - 短 prefill + 短 output + high QPS
  - 长 prefill + 长 output + low QPS
  - 长 prefill + 长 output + high QPS
- [ ] 检查是否在 corner 1 看到 co-located > disagg
- [ ] 如果 corner 1 看到 crossover，进入 Phase 1；否则重新评估

### Phase 1：Controlled Benchmark（4 周）

**目标**：建立 synthetic workload 下的 crossover map

- [ ] 完整 model × workload × hardware matrix 实验
- [ ] Output length sweep（16, 64, 256, 1024, 4096 tokens）
- [ ] QPS sweep（low / medium / high / burst）
- [ ] Prefill/Decode pool ratio sweep
- [ ] KV transfer protocol 对比（Mooncake vs NCCL-naive）
- [ ] 生成第一版 crossover chart

### Phase 2：Real Trace Evaluation（4 周）

**目标**：在真实 trace 上验证 Phase 1 的 crossover 边界

- [ ] Mooncake trace replay
- [ ] Azure LLM Inference trace replay
- [ ] LMSYS-Chat-1M replay
- [ ] BurstGPT replay
- [ ] 自构造 agentic trace（OpenHands-derived）
- [ ] 对每个 trace 计算 "应该用 disagg 的比例 vs 应该用 co-located 的比例"

### Phase 3：Diagnostic Analysis + Workload Router（3 周）

**目标**：解释 crossover 原因 + 提出 actionable 决策工具

- [ ] 分解 disagg 的开销（KV transfer / coordination / fragmentation）
- [ ] 分解 co-located 的开销（chunked-prefill TPOT penalty / batch interference）
- [ ] **训练一个 workload classifier**：给定请求特征（predicted output length, current load），输出 "route to disagg pool" or "route to co-located pool"
- [ ] 在 real trace 上验证 router 的决策质量

### Phase 4：Hybrid System Proposal（3 周，可选）

**目标**：提出 "best of both worlds" 的 hybrid 架构

- [ ] 维护两个 pool（disagg + co-located），用 router 动态分流
- [ ] 在 mixed workload 上对比 pure-disagg / pure-colocated / hybrid
- [ ] 如果 hybrid 显著优于两者，作为本工作的 constructive contribution

### Phase 5：论文撰写（3 周）

---

## 七、论文定位与贡献

### 7.1 核心 Claim

> Disaggregated prefill-decode serving 的优势被学术和工业社区高估：在 **40-60% 的真实 LLM serving workload** 下，优化良好的 co-located chunked-prefill serving 在 goodput-under-SLO 指标上匹配或超过 disagg。本工作提供第一份严格的 disaggregation crossover map，证明 disagg 的收益取决于一组**被系统低估**的 workload 特征（output length、burstiness、prefix cache 命中率、pool ratio 适配性），并提出一个 workload-aware router 可在 hybrid pool 架构下综合两者优势。

### 7.2 贡献列表

1. **方法论贡献**：第一份对 P/D disaggregation 的 rigorous 第三方审计 + 可复现 benchmark harness
2. **实证贡献**：定量 crossover map，涵盖 4 模型 × 5 workload × 3 硬件配置
3. **诊断贡献**：disaggregation 开销的细粒度分解（KV transfer / coordination / fragmentation）
4. **工程贡献**：workload-aware router + hybrid pool 系统原型
5. **社区资产**：开源 benchmark 代码 + trace processing pipeline + decision chart（可直接被生产团队引用）

### 7.3 论文结构

1. **Introduction**：Disagg 已成正统的 narrative + "但何时实际赢" 的追问
2. **Background**：Disagg 范式、chunked prefill 演进、goodput-under-SLO 的必要性
3. **Methodology**：实验矩阵、baseline 调优、trace 处理、统计方法
4. **The Disagg Cost Breakdown**：KV transfer / coordination / fragmentation 量化
5. **The Crossover Map**：核心实证结果（chart + per-regime breakdown）
6. **Real Trace Analysis**：5 种 trace 上的 disagg-vs-colocated 分布
7. **Hybrid Router**：workload classifier + hybrid pool 架构 + 端到端对比
8. **Discussion**：对社区的建议 + disagg 的真实 design space

---

## 八、诚实的 MLSys 可发表性评估

### 8.1 优势

1. **方法论模板存在且被 MLSys 接纳**：SD Illusion、Rethinking KV Compression 都是 MLSys 2025-2026 接收的同类型论文
2. **社区需求真实**：很多团队在"要不要上 disagg"这个决策上犹豫，没有 rigorous 参考
3. **Counter-consensus 是永续机会**：每次新正统形成就产生对应的审计空白
4. **小实验室可 own**：大厂没动机审计自己的正统架构
5. **即使 negative result 也有价值**：crossover chart 本身就是社区资产
6. **硬件门槛低**：4-16 GPU 即可完成

### 8.2 风险

1. **Baseline fairness 是 make-or-break**：如果 chunked-prefill 没调好，整个 crossover 都是假的
2. **可能被审稿人说"已知"**：需要用 quantitative chart 反驳
3. **DistServe/Mooncake 团队可能反驳**：需要在 camera-ready 前邀请他们看数据
4. **Agentic workload 的 trace 真实性**：OpenHands trajectory 可能不够 representative

### 8.3 审稿人质疑的预判

**Q1**：*"vLLM 的 chunked-prefill 本身就吃掉了 disagg 的优势吗？"*

回应：是的，这正是我们要实证的点。DistServe 原论文的 baseline 是 2023 年的 vLLM（无 chunked prefill），一年后 co-located 技术的演进可能已让 disagg 的相对优势被部分追平。本工作用 **2025-2026 SOTA 的 chunked prefill**作为 fair baseline。

**Q2**：*"你们的 disagg 实现是不是没有充分优化？"*

回应：用官方开源实现（DistServe、Mooncake）+ 与作者确认配置 + 报告多个实现下的结果。

**Q3**：*"crossover map 不就是 'depends on workload' 的废话？"*

回应：(a) 我们给出 quantitative chart 而非 qualitative 结论；(b) 识别出被系统性低估的 4 个 workload 特征；(c) 提供 workload router 把 "depends" 变成 actionable decision。

### 8.4 总体判断

| 维度 | 评分 | 说明 |
|---|---|---|
| 问题重要性 | ⭐⭐⭐⭐⭐ | Disagg 是当下最大的 serving 架构决策 |
| 新颖性 | ⭐⭐⭐⭐ | 视角新颖（counter-consensus），方法严谨 |
| 技术深度 | ⭐⭐⭐ | 测量 + router，不是重量级系统 |
| 可复现性 | ⭐⭐⭐⭐⭐ | 开源 benchmark + public trace |
| 社区影响 | ⭐⭐⭐⭐⭐ | 直接影响生产团队决策 |
| 可行性 | ⭐⭐⭐⭐⭐ | 小集群 + 3-4 个月 |

**结论**：这是一个**高 ROI、低风险的 MLSys 2027 target**。与过去三个 deprecated idea 的核心差异：
- **不与大团队正面 PK**（disagg 原作者无动机自我审计）
- **不依赖 novelty race**（counter-consensus 是永续空白）
- **不需要工程里程碑**（benchmarking + analysis 即可）
- **即使 negative result 也发表**（crossover chart 本身是贡献）

### 8.5 备选 / 并行路径

**并行 paper 选项**：与 "Attention Is Not the Bottleneck" 组合。两者都需要 Nsight profiling + vLLM infrastructure，可共享实验基础设施。可拆分为两篇 paper，也可组合成一篇 "LLM Serving Audit" 综合论文。

**Fallback**：若 disagg crossover 不存在（即 disagg 在所有测试的 regime 都赢），pivot 为 "disagg 赢的真实幅度 vs 其论文 claim 的偏差" 分析——同样是 counter-consensus 叙事，同样可发表。

---

## 九、立即行动项（Phase 0 启动）

1. **Week 1**：
   - [ ] 拉起 vLLM v1 + chunked-prefill baseline（4×H100）
   - [ ] 与 vLLM 社区确认 chunked-prefill 最佳配置
   - [ ] 拉起 DistServe 或 Mooncake 开源版
   - [ ] 设计 4 corners 快速测试脚本
2. **Week 2**：
   - [ ] 跑 4 corners 实验
   - [ ] 分析是否看到 crossover
   - [ ] 若看到 → 写 Phase 1 详细计划
   - [ ] 若没看到 → 讨论 pivot 方案

**Go/No-Go 决策点**：Week 2 结束

---

## 附录：关键参考文献

| 论文 | 会议 | 为何相关 |
|---|---|---|
| DistServe | OSDI'24 | Disagg 开创者，baseline |
| Splitwise | ISCA'24 | Phase splitting 另一视角 |
| Mooncake | FAST'25 | 生产级 disagg，开源 baseline |
| Beyond the Buzz | MLSys'26 | 最接近工作，但是模拟不是实测 |
| SD: Performance or Illusion? | MLSys'26 | Counter-consensus 发表模板 |
| Rethinking KV Compression | MLSys'25 | 另一个 counter-consensus 模板 |
| Sarathi-Serve | OSDI'24 | Chunked prefill 技术基础 |
| vLLM / PagedAttention | SOSP'23 | Co-located baseline 基础 |

## 附录：关键开源 artifacts

- vLLM v1: https://github.com/vllm-project/vllm
- DistServe: https://github.com/LLMServe/DistServe
- Mooncake: https://github.com/kvcache-ai/Mooncake
- SGLang: https://github.com/sgl-project/sglang
- Mooncake trace: https://github.com/kvcache-ai/Mooncake/blob/main/FAST25-release/traces
- Azure LLM Inference trace: https://github.com/Azure/AzurePublicDataset
- BurstGPT: https://github.com/HPMLL/BurstGPT
