---
type: paper
name: BEAM
full_title: "BEAM: Joint Resource–Power Optimization for Energy-Efficient LLM Inference Under SLO Constraints"
authors: [Hyunjae Lee, Sangjin Choi, Seungjae Lim, Youngjin Kwon]
venue: MLSys
year: 2026
tags: [llm-serving, energy-efficiency, dvfs, slo, vllm, pipeline-parallelism]
source_pdf: "[[43ec517d68b6edd3015b3edc9a11367b.pdf]]"
source_md: "[[43ec517d68b6edd3015b3edc9a11367b]]"
---

# BEAM: Joint Resource–Power Optimization for Energy-Efficient LLM Inference Under SLO Constraints (MLSys 2026)

> **一句话总结**：作者测量发现 batching（资源轴）与 DVFS（功耗轴）共享同一 SLO latency slack 且强耦合——最优频率随 batch 形态移动；据此在 [[vLLM]] 上事件驱动联合调 GPU 频率、chunk size、microbatch，在 TTFT/TBT SLO 满足率 ~95% 下较 vanilla vLLM GPU 能耗降 **51%**、较 Window-DVFS **30%**。

## 问题与动机

[[LLM]] serving 在 per-request SLO（TTFT、TBT）满足后仍留有 **latency slack**——最早可完成时间与 deadline 之间的窗口，本可换能耗。现有路线只优化单轴：传统 serving 用 [[Continuous-Batching]] 等 batching 提升资源效率（花 slack 作 queueing delay），energy-aware 系统用 DVFS 降频（花 slack 作更慢执行）。二者共享**同一有限 slack 预算**，固定一轴优化另一轴只能到局部最优。

论文用 Fig.1/2 量化耦合：~2000 aggregate input tokens 的 batch 相对单 token batch，per-token latency/energy 各降约 **144–145×**；而 energy-optimal GPU frequency 的「谷底」会随 batch 计算强度整体平移——大 compute-bound batch 与小 memory-bound batch 的最优频点截然不同。DynamoLLM 虽首次联合两轴，但在 **5 秒级** cluster 粒度调 TP/instance/DVFS，对突发 workload 反应太慢。

BEAM（Batch-Energy Adaptive Manager）目标：在 **毫秒级**、**单节点**、**per-request SLO** 约束下，把 slack 同时花在资源轴与功耗轴，找 `Energy = Time × Power` 的全局最小。

## 关键观察 / 隐含假设

- **观察 1：资源效率与功耗效率两轴强耦合，最优 DVFS 依赖 batch 形态。** chunk size / microbatch count 改变单次 forward 的 token 数与计算强度，从而移动整条 energy valley 曲线（Fig.2：16-token vs 512-token batch 最优频点不同）。
  - **依赖假设**：能耗可用 per-shard `(num_tokens, frequency) → latency/energy` 二维 profile 近似；三旋钮效应主要通过 resulting token batch size 体现。
  - **可能失效场景**：非 [[Pipeline-Parallelism]] 部署（无 chunk/microbatch 旋钮）、MoE 路由使 batch 形态与 token 数脱钩、或 GPU 代际功耗曲线形状变化时 LUT 需重 profile。
- **观察 2：SLO slack 是单一有限时间池，现有系统只花在一轴上。** 传统 serving 大 batch + 满频；DVFS-only 固定 batch 降频——都错过「换 batch 曲线后再选频」的全局最优。
  - **依赖假设**：per-request TTFT/TBT deadline 足够松，存在可 reclaim 的 slack；用户愿接受接近 deadline 的 P90 延迟以换能耗（Fig.7 显示 BEAM 把 P90 推向 SLO 边界）。
  - **可能失效场景**：极紧 SLO、tail-sensitive 应用、或 saturation 下 slack 趋零（论文 Fig.9：~6400 tps 时所有方法 TTFT 违约）。
- **观察 3：prefill（compute-intensive）与 decode（memory-bound）目标冲突且资源纠缠。** 大 prefill chunk 利于能效但恶化 TBT；两阶段需分离 SLO（TTFT vs TBT）与专用调度器。
  - **依赖假设**：prefill+decode 共置在同一 PP 集群；事件（新 prefill 到达、请求完成）足以刻画需重决策的状态变化。
  - **可能失效场景**：[[Disaggregation]] 后 prefill-only 节点无 TBT 约束（论文称 S1 可简化）；极高频 arrival 使事件触发过于密集。
- **观察 4：事件驱动控制优于 5 秒窗口式 periodic DVFS。** 突发时 BEAM 立即升频+调 chunk；Window-DVFS 因历史负载滞后，burst 中 TTFT 违约、burst 后仍维持高功耗（Fig.8）。
  - **证据强度**：**强**——合成 Poisson burst 实验直接对比；但真实 trace 仅 1 小时段，P99 尾延迟未系统报告。
- **假设 1**：离线 ~30 分钟 sparse profiling + LUT 查表可在运行时 sub-ms 完成 joint search，MAPE 误差下 SLO 仍可控。
  - **证据强度**：**中**——TTFT MAPE 最高 **27%**、TBT **19%**（Tab.1），SLO 满足率 ~95% 说明可用但非无损；未见 worst-case 误差下的安全 guard 分析。

## 核心方法

BEAM 是叠在 [[vLLM]] v0.11+ 上的 **event-driven、phase-aware controller**（~1100 LOC），三原则对应三项挑战：

**P1 Event-driven**：仅在 (1) 新 prefill 到达、(2) 任意请求完成 时触发决策；steady-state 零控制开销。State Monitor Hook 拦截 vLLM 调度事件，分发给 S1 或 S2。

**P2 Phase-aware schedulers**：
- **S1 Prefill Scheduler**：新 prefill 到达时，在候选 `(chunk size c, frequency f)` 上 bounded exhaustive search（Alg.1）。用离线 LUT 的 per-shard `L(c,f)`、`E(c,f)` 经 Equation 1 解析组合整 pipeline 的 TTFT、TBT、总能耗；剪枝 SLO 违约者，选能耗最小可行点。须同时满足 incoming prefill 的 TTFT **与** ongoing decode 的 TBT。
- **S2 Decode Scheduler**：进入/更新 decode-only 状态时，在 `(microbatch count m, frequency f)` 上搜索（Alg.2）。活跃 decode 数 D 时 token/microbatch `b=⌈D/m⌉`，用 Equation 2 预测 TBT 与能耗；高 m 利 pipeline 利用、低 m 利计算效率。

**P3 Model-driven joint optimization**：离线 Profiler 不把三维旋钮全笛卡尔积 profile，而是抓住 insight——chunk/microbatch 效应主要经 **num_tokens** 体现。对 `(num_tokens, frequency)` 做 sparse 2D 测量（小 token 区 tile-quantized 采样、大 token 区只测 S1 可能选的 chunk），约 **30 分钟** 建 Perf–Energy LUT；S1/S2 共享同一 LUT，可组合（composable per-shard）。

**实现**：调度决策嵌在 vLLM 异步调度环，不阻塞 GPU kernel；DVFS 经 NVML `nvmlDeviceSetGpuLockedClocks` 在 **后台线程** 执行（~7–10 ms，非阻塞）。能耗用 sidecar 每 **200 ms** 轮询 `nvmlDeviceGetTotalEnergyConsumption`。

与 DynamoLLM 对比：BEAM 不做 cluster TP/instance 重配，专注单节点 **chunk + microbatch + DVFS** 细粒度旋钮；论文称可与 cluster-level 方案及 [[Disaggregation]] 架构模块化叠加（prefill 侧只跑 S1、decode 侧只跑 S2）。

## 设计取舍

- **取舍 1：事件驱动 vs periodic window**——换即时响应 burst 与零 steady-state 开销；代价是仅两类事件，中间 GPU 利用率漂移不触发重优化。
- **取舍 2：解析模型 + LUT search vs 在线 profiling**——换 sub-ms 决策（S1/S2 各 <1 ms）；代价是 TTFT 预测 MAPE 可达 **27%**，靠 SLO 剪枝兜底而非硬实时保证。
- **取舍 3：PP 旋钮 vs 通用 TP-only 部署**——chunk/microbatch 是 PP 特有，换大模型 memory scaling 下的细粒度能效控制；无 PP 时只剩 DVFS 单轴，收益接近 ablation「DVFS Only」。
- **取舍 4：Reclaim slack 换能耗 vs 保留延迟余量**——BEAM 主动把 P90 TTFT/TBT 推向 SLO 边界（Fig.7）；TBT 满足率 **94.5%** 略低于 Window-DVFS，换 **30%** 相对能耗降幅。
- **边界条件**：在 **A100、PP 重型配置（TP=2, PP=4）、中等负载（~1800–4000 tps）** 收益最大；低负载 aggressively 降频，近饱和时行为收敛 vanilla vLLM；需 **privileged Docker + NVML clock lock** 权限。

## 实验与结果

- **端到端（ServeGen 衍生 1h bursty trace，19:00–20:00，~1800 tps）**：
  - Llama 3.3-70B（8×A100，TP=2, PP=4）：能耗为 vanilla vLLM 的 **49%**（即 **-51%**），较 Window-DVFS **-30%**；TTFT SLO **94.9%**、TBT **94.5%**（较 Window-DVFS -0.1pp / -0.9pp）
  - Qwen2.5-32B（4×A100，TP=2, PP=2）：能耗 **53%** of vanilla；TTFT **98.2%**、TBT **100%**
- **Burst 敏感性（4→20 req/s 合成突发）**：BEAM 突发时立即升频+调 chunk，subsiding 后降频；Window-DVFS burst 中 TTFT 违约、结束后仍高功耗（Fig.8）
- **负载 ramp（2–6.4 req/s，~2000–6400 tps）**：低负载 exploit slack；高负载重配高性能旋钮；~6400 tps 全体 TTFT 违约（容量上限，Fig.9）
- **Ablation（Poisson 3 req/s，512 in / 64 out）**：DVFS Only → **73%** 能耗；加 S1 chunk → 再省 **~2%**；加 S2 microbatch（完整 BEAM）→ 再省 **~19%**（Fig.10）
- **模型保真度（Tab.1）**：TBT MAPE **9.2–18.8%**，TTFT **11.0–27.0%**；多模型/并行配置
- **Pareto（Fig.11）**：固定 TTFT SLO 1s、TBT 160–240 ms，BEAM 相对 Window-DVFS 支配更优 energy-latency 前沿；PP-heavy（TP=2, PP=4）比 TP-heavy 更节能
- **开销（Tab.2）**：S1/S2 scheduler **<1 ms**；DVFS actuation **7–10 ms**（异步，不阻塞调度）

## Critical Analysis

### 论证链条

链条 **observation（两轴耦合 + slack 单池）→ design（事件 + 分 phase + 2D LUT joint search）→ result（-51% / -30% 能耗，~95% SLO）** 整体闭合。较强环节是 **ablation 分解**：S2 decode microbatch 单独贡献 ~19% 能耗降幅，说明 PP decode 轴不是装饰；burst 时间线直观展示 event-driven 相对 5s window 的机制优势。

较弱环节：(1) 把 **1 小时单段 trace** 的能耗结论外推到 7×24 production——论文未给多日 trace、tenant 混部或 seasonal drift；(2) **SLO 满足率 <100%** 被表述为「negligible loss」，但对 contractual SLO 或 P99 敏感业务是否可接受未量化；(3) 最优性 claim 基于 bounded search over 离散 knob 网格，未证明全局最优。

### 假设压力测试

- **LUT 可组合性**：假设 shard 独立、效应经 num_tokens 汇总；跨 stage bubble 交互、[[Chunked-Prefill]] 与 PP bubble 叠加的建模误差可能是 TTFT MAPE 27% 来源——论文未 ablate 模型复杂度。
- **NVML DVFS 粒度与延迟**：7–10 ms 异步调频在 ms 级 decode step 上可能多步运行在次优频率；burst 上升沿是否因 DVFS lag 漏省能耗 **论文未单独测量**。
- **PP 必要性**：主实验 TP=2, PP=4；Fig.11 显示 PP-heavy 更优，但许多生产部署偏 TP-heavy 或 [[Disaggregation]]——BEAM 在 TP-only 或 prefill/decode 分离集群上的收益未被端到端验证（仅 related work 讨论性描述）。
- **Window-DVFS baseline 公平性**：作者刻意剥离 DynamoLLM 的 cluster 重配，只留单节点 5s DVFS——有利于突出 BEAM 细粒度优势，但与「完整 DynamoLLM」生产对比会低估 cluster 方案。
- **SLO 定义**：TTFT/TBT 阈值固定，未测不同 SLO 松紧下能耗–违约率 frontier 的 knee point（除 Fig.11 部分 TBT sweep）。

### 实验可信度

- **Workload**：ServeGen m-small 衍生 trace + 多种合成 Poisson 场景，覆盖 burst/ramp/ablation；**缺** 多租户、长上下文、tool-call 等新兴 traffic。
- **Baseline**：Vanilla vLLM（满频默认调度）与 Window-DVFS 合理；**未与** GreenLLM、ThrottleLL'em、[[LLMStation-ATC25]] 等 energy-aware serving 端到端对比。
- **Scale**：最大 8×A100、70B；单节点；无 multi-node PP/EP 扩展数据。
- **Metric**：P90 TTFT/TBT、SLO attainment %、总能耗较全；**缺** P99/P999 尾延迟、per-request 能耗方差、DVFS 切换次数分布、thermal throttling 干扰。
- **Ablation**：组件分解清楚（Fig.10）；对 **offline profile 稀疏策略**、**事件类型仅 2 种** 的 sensitivity 不足。

### 系统性缺陷

- **尾延迟**：主动 reclaim slack 可能抬高 tail；论文 histogram 展示 P90 靠近 SLO，**未报** P99 违约率或最长 TTFT/TBT。
- **运维与权限**：需 privileged container、nvidia-persistenced、clock lock；多租户集群上 per-GPU 调频的隔离与公平性 **论文未讨论**。
- **可观测性**：S1/S2 决策日志在 artifact 中有，但生产 debug（为何选某 (c,f)、模型误差导致 near-miss SLO）**论文未讨论**。
- **兼容性**：深度绑定 vLLM V1 scheduler + NVML；迁移到 [[SGLang]]、自研 runtime 或云厂商禁 DVFS 环境成本高。
- **正确性**：仅 latency SLO，无能效–精度权衡（量化、speculative 等）联合验证。

## 局限与 Future Work

- **局限 1**：预测模型 TTFT MAPE 最高 **27%**，SLO 满足率 ~95% 非硬保证；饱和负载下与 baseline 一同违约。
- **局限 2**：评估限于单节点 A100 + PP 配置；cluster-level 旋钮（instance count、TP 重配）与 BEAM 正交叠加的实际收益未实测。
- **局限 3**：DVFS 7–10 ms 异步延迟、仅两类触发事件，对极短 decode step 或超高 QPS 微突发可能不够细。
- **Future work 1**：在真实 multi-day production trace 上测量「P99 延迟 / SLO 违约率 / 能耗」三目标 frontier，量化 slack reclamation 的 tail 代价。
- **Future work 2**：与 [[Disaggregation]] 架构端到端集成——prefill-only / decode-only 节点分别部署 S1/S2，并与 cluster scheduler（DynamoLLM 类）分层协同。
- **Future work 3**：在线校正 LUT 或 hybrid event+micro-window 策略，压测 DVFS actuation lag 与模型 drift 下的 robust guard（fallback 满频策略）。

## 相关

- **相关概念**：[[Continuous-Batching]]、[[Chunked-Prefill]]、[[Pipeline-Parallelism]]、[[KV-Cache]]、[[Disaggregation]]
- **同类系统**：[[vLLM]]、DynamoLLM、GreenLLM、ThrottleLL'em
- **互补方向**：[[LLMStation-ATC25]]（并行策略）、[[FlexiCache-MLSys26]]（KV/显存）
- **同会议**：[[MLSys-2026]]
- **对比**：单轴 batching vs 单轴 DVFS vs joint fine-grained control；event-driven vs periodic window control