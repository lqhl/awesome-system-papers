---
type: paper
name: TriInfer
full_title: "TriInfer: Hybrid Disaggregated Scheduling for Multimodal Large Language Model Serving"
authors: [Xianzhe Dong, Tongxuan Liu, Yuting Zeng, Weizhe Huang, Xiaoyang Zhao, "et al."]
venue: MLSys
year: 2026
tags: [mllm, inference, disaggregation, scheduling, serving]
source_pdf: "[[6974ce5ac660610b44d9b9fed0ff9548.pdf]]"
source_md: "[[6974ce5ac660610b44d9b9fed0ff9548]]"
---

# TriInfer: Hybrid Disaggregated Scheduling for Multimodal Large Language Model Serving (MLSys 2026)

> **一句话总结**：基于「MLLM encode/prefill/decode 三阶段 batch 饱和点与算术强度迥异、且最优 [[Disaggregation]] 随 TTFT/TBT SLO 变化」的观察，TriInfer 用 Hybrid EPD 可配置分片 + 双流 vision/language CUDA stream 并行 + SLO-aware stage-level batching，在 90% SLO 满足下相对 [[vLLM]]/[[SGLang]] 最高 **2.4×** goodput（POPE），并据历史 trace 自动选 E+P+D / EP+D / ED+P 及实例比例。

## 问题与动机

多模态大模型（MLLM）推理通常分三阶段：**encode**（vision tower 把图像变成数百～数千 visual token）、**prefill**（图文 prompt 一次性算 KV）、**decode**（自回归生成）。与纯 LLM 不同，单张图即可引入远超文本的 token 数与算力，三阶段在计算/内存特征、最优 batch size、SLO 敏感度上高度异构。

现有 serving 栈（[[vLLM]]、[[SGLang]]、TGI）多按 LLM 架构把 encode 与 prefill/decode **顺序** 绑在同一实例，未利用 vision 与 language 的跨模态并行；[[Continuous-Batching]]、[[Chunked-Prefill]]、stall-free scheduling 等 LLM 调度粒度偏粗，难精确控制 TBT，且**未计入 encode 延迟**。另一方面，[[Disaggregation]] 在 MLLM 上已有 E+P+D、EP+D、ED+P 等变体，但生产系统往往**固定一种**拓扑，无法随 workload 与 TTFT/TBT SLO 切换。

TriInfer 的 claim 是：把 encode/prefill/decode 提升为 first-class stage，在统一引擎上可配置实例角色，并据 trace 自动选解耦方式与实例比例，从而在满足 90% SLO attainment 的前提下最大化 per-GPU **goodput**（达到 ≥90% SLO 满足率的最大请求率）。

## 关键观察 / 隐含假设

- **观察 1：三阶段算术强度与最优 batch size 差异巨大，粗粒度混批会在某阶段过早饱和并线性拉高延迟。** LLaVA-1.5-7B 测量（Fig. 3）：encode 约在 **batch≈6** 图饱和，prefill **≈1** 请求即饱和，decode 需 **≈512** token 才饱和；超过饱和点后吞吐不再增长而延迟线性上升。FLOPs/访存分析（Table 2）显示 encode 介于 compute-bound prefill 与 memory-bound decode 之间（Fig. 2）。
  - **依赖假设**：评测用固定 prompt 长度（1024 token）、336×576 visual token/图；batch 执行时间与 batch size **单调增**，可用二分搜索反推 SLO 下的 image/token budget。
  - **可能失效场景**：动态分辨率（LLaVA-NeXT、Qwen2-VL）使 visual token 数剧变，饱和点漂移；多图/视频请求打破「单图单请求」简化；极小输出长度（MME）使 decode batching 收益消失。
  - **证据强度**：强。多 stage microbenchmark + 算术强度曲线直接支撑 stage-level batching 动机。

- **观察 2：vision encode 与 language prefill/decode 可在 GPU 上双流并行，缓解单流顺序执行时的算力/带宽闲置。** 受 [[NanoFlow]] 启发，独立 CUDA stream 跑 vision 与 language kernel；Fig. 12 显示 LLaVA-1.5-7B 在各 batch size 下双流相对顺序执行显著提升 encode 与 decode 吞吐。
  - **依赖假设**：vision tower 与 LLM 可共驻同一 GPU 且 HBM 够同时加载；两 stream 资源争用不致抵消并行收益。
  - **可能失效场景**：超大 vision encoder 或 TP 切分后跨 stream 同步复杂；encode 与 decode 内存峰值叠加导致 OOM；多租户隔离要求单 stream 确定性时不可并行。
  - **证据强度**：中到强。有 microbenchmark，但在线多请求交错下的 stream 干扰与尾延迟未单独报告。

- **观察 3：最优 MLLM 解耦拓扑（E+P+D、EP+D、ED+P）与实例比例随 TTFT/TBT SLO 与 workload 显著变化，静态选型会损失 goodput。** Fig. 5–6：EP+D 在 1EP+7D 时 TTFT 恶化，7EP+1D 时 decode 排队拉高 TBT；严格 TTFT 下 **E+P+D** 优势大，宽松 SLO 下 **ED+P** / **EP+D** 更优。TextCaps @8 req/s 上实例比扫描印证「无 universal winner」。
  - **依赖假设**：历史 trace 能代表未来到达率与 prompt/decode 长度分布；集群总实例数 **N 固定**；trace replay 数分钟即可估 goodput。
  - **可能失效场景**：workload 突变（论文承认会短暂次优）；冷启动无 trace；多模型混部时单 trace 不够；跨节点 KV/image cache 迁移占比上升时 Fig. 5 结论可能偏移。
  - **证据强度**：中。8 实例穷举排名显示启发式接近最优（Table 3），但仅小集群、有限 SLO 网格。

- **观察 4：LLM 式 stall-free / prefill-prioritized 调度在 MLLM 上难保 TBT SLO，因未把 encode 纳入执行时间预算。** Fig. 4：prefill 优先抬高尾 TBT；stall-free 混 prefill+decode 仍忽略 image encode 排队与执行。
  - **依赖假设**：用户同时约束 TTFT 与 TBT（90% token 间隔低于阈值）；每个请求至少两次 batch 迭代才出首 token（encode + prefill），故 E/EP/P 实例 batch 时限设为 **α·TTFT_max（α=0.5）**。
  - **可能失效场景**：仅关心吞吐、无 TBT SLO 的 offline batch；encode 被 prefix/image cache 命中消掉时两次迭代假设不成立。
  - **证据强度**：中。时间线示意图 + ablation（关 stage-level scheduling goodput 2.6→2.2）支持，但未与 Sarathi-Serve 等 MLLM 改造版 head-to-head。

- **假设 1：EP/PD 阶段间 KV cache 与 image cache 迁移延迟相对 decode 执行可忽略。**
  - **证据强度**：中。Latency breakdown（Fig. 11）显示迁移 <**1%** 总延迟，95% image 迁移 <**2ms**、KV <**8ms**；但实验偏好同节点 NVLink 部署，跨节点 InfiniBand 场景 Table 4 仍称 SLO violation 可忽略，样本与规模有限。

## 核心方法

TriInfer 是约 **10K Python + 3K C++/CUDA** 的在线 MLLM serving 系统，基于 Ray actor 多实例、RESTful OpenAI 风格 API、CUDA IPC + NCCL 传 KV/image cache，内核侧用 FlashAttention / FlashInfer 实现 [[PagedAttention]] 式分页 KV 与 **分页 image cache**。

### Request Processor 与 stage 抽象

入站请求先 tokenization / 图像预处理，再由 Stage Processor 拆成 **encode → prefill → decode**（及 migrate）细粒度 task，并预生成控制参数。把 CPU 密集调度前移到预处理，减轻 autoregressive 热路径负担；stage-centric 抽象声称可扩展到 video/audio 等额外阶段。

### Stage-level Batching（Algorithm 1）

按实例类型 **E / EP / P / D / ED / EPD / PD** 统一迭代调度：

1. 初始化 **image budget τ_e**、**token budget τ_t**（启动时按 SLO 二分搜索 profiling，Fig. 3 单调性假设）；
2. E/EP/P：batch 执行时限 **α·TTFT_max**；D/ED/EPD/PD：时限 **TBT_max**；
3. 每轮优先纳入所有进行中的 **decode**；再纳入未完成的 chunked prefill / encode；最后用等待队列填满 τ_t、τ_e。

这直接回应观察 1、4：分 stage 饱和点设预算，避免混批在 prefill/encode 上拖垮 decode 尾延迟。双流并行（§4.2）回应观察 2：vision stream 跑 encode，language stream 跑 prefill/decode。

### Migrate Scheduler

**Pull-based** 迁移：目标实例排队后向源实例异步拉 KV/image cache 页表与数据，完成后再释放源资源。默认 round-robin 选目标，支持 least-load、prefix hit 优先等。用于 E+P+D 等拓扑下的阶段 handoff 与负载均衡。

### Hybrid EPD Disaggregation（Algorithm 2）

部署层把通用实例组合成 **E+P+D**、**EP+D**、**ED+P** 三种工作流。冷启动用默认 EPD，同时采集 trace（分辨率、prompt/decode 长度、时间戳）。在 workload **相对稳定** 假设下：

1. 统计历史 trace 上 encode/prefill/decode token 负载 **W_e, W_p, W_d**；
2. 按 SLO 搜索各 stage 最大 batch，结合 D 实例 KV 容量（γ=0.9 显存给 cache）估满负载吞吐；
3. 按三阶段执行时间比例 **partition(N)** 得 **N_e, N_p, N_d**，再派生出 EP+D / ED+P 配置；
4. **Replay trace** 测 goodput，取最优拓扑。

搜索空间 **2·C(N−1,1) + C(N−1,2)**，相对暴力枚举理论加速显著；实测 profiling ~1 分钟、replay 数分钟。workload 漂移时周期性重跑；论文承认剧烈突变下会短暂次优，并计划 fast role switching / 动态扩缩容。

设计映射：观察 3 → Hybrid profiler；观察 1 → stage-level budget；观察 2 → dual-stream；观察 4 → TTFT/TBT 分实例时限。实现与算法细节见 [[6974ce5ac660610b44d9b9fed0ff9548]] / [[6974ce5ac660610b44d9b9fed0ff9548.pdf]]。

## 设计取舍

- **Hybrid 三拓扑 vs 单一 E+P+D**：赢得随 SLO/workload 切换最优 goodput（ablation：关 hybrid 3.9→2.6 req/s on TextCaps）；代价是部署/迁移/运维复杂度上升，且依赖 trace 与周期性重配置。
- **Stage-level SLO 预算 vs 峰值吞吐**：用 α=0.5·TTFT、TBT_max 硬限 batch 执行时间，保 90% SLO；牺牲部分可压榨的饱和 batch 空间（尤其 prefill 本可更大 batch）。
- **双流共驻 vs 完全 disagg encode**：同 GPU 并行提升利用率；牺牲显存峰值与 stream 调度复杂度，且与「encode 独立池」的 E+P+D 叙事部分重叠——系统同时支持两种思路，由 profiler 选择。
- **启发式 profiler vs 在线全局 planner**：几分钟级离线搜索，避免 latency-sensitive 推理中的重规划开销；牺牲对突发流量的即时响应，**N 固定**无法像 [[NVIDIA-Disagg-Study]] / Dynamo 那样动态 rate matching。
- **公平性取舍**：对比 vLLM/SGLang 时**关闭 prefix cache 与 CUDA Graph**；EPDServe/DistServe 核心逻辑**在 TriInfer 内重写**而非原版代码——利于统一 MLLM 支持，但削弱「击败第三方实现」的说服力。
- **边界条件**：在 **image-text MLLM、H20 32-GPU 集群、TTFT+TBT 双 SLO、production-like 到达过程** 下最优雅；极短 generation、纯文本、或强依赖 prefix cache 的生产负载需重新验证。

## 实验与结果

**平台**：4 台服务器 × 8× NVIDIA H20（141GB）、NVLink、2×200Gbps IB；CUDA 12.4；KV block=16，image block=576，fp16。

**模型**：LLaVA-1.5-7B、LLaVA-NeXT-7B、Qwen2-VL-7B。

**Workload**：TextCaps、POPE、MME、TextVQA、VizWiz；1/10 数据作 profiler trace，其余评测；到达过程来自生产 trace（Qin et al. Mooncake）缩放请求率；固定 decode token 数（`max_tokens` + `ignore_eos`）保证负载一致。

**Baselines**：[[vLLM]] 0.11.0、[[SGLang]] 0.5.3（各 32 实例 round-robin）；EPDServe 风格 **4E8P20D**、DistServe 风格 **12EP20D**（均在 TriInfer 内实现）。

### 主结果（90% SLO attainment → goodput）

- 相对 SOTA：**最高 2.4×** 吞吐（abstract）；分数据集 goodput vs vLLM/SGLang：**MME 1.2×、POPE 2.4×、TextCaps 1.5×、TextVQA 1.8×、VizWiz 1.7×**。
- Qwen2-VL-7B vs [[SGLang]]：**2.0×–7.9×** goodput；LLaVA-1.5 vs [[vLLM]]：**1.3×–3.7×**；LLaVA-NeXT vs [[vLLM]]：**1.2×–2.1×**。
- MME 提升最小：输出 token 极少，TBT 调度优化空间受限。

### Ablation（TextCaps，LLaVA-NeXT-7B）

- 关 Hybrid profiler，固定均分 **E+P+D**：goodput **3.9 → 2.6 req/s**。
- 再关 stage-level scheduling：**2.6 → 2.2 req/s**。

### 启发式最优性（8 实例穷举 35 种部署）

- Table 3：profiler 所选策略平均排名靠前，跨模型/数据集/SLO 网格稳定。

### 延迟与迁移

- Fig. 11（LLaVA-1.5，TextCaps，1E3P4D）：延迟主要在 decode，其次 prefill、encode；迁移 <**1%**。
- Table 4：多规模下 migration 所致 SLO violation 可忽略；跨节点优先放 EP 迁移（image cache 小于 KV）。

### 双流

- Fig. 12：双流相对顺序 round-robin 在各 batch size 提升 vision + language 吞吐。

## Critical Analysis

### 论证链条

主链条：**测量** 三阶段饱和点与算术强度分化（Fig. 2–3）+ 解耦拓扑随 SLO 变化（Fig. 5–6）→ **机制** 分 stage 预算与可选 E+P+D/EP+D/ED+P → **设计** Hybrid EPD + stage-level batching + dual-stream → **结果** 多模型多数据集 goodput 1.2×–7.9× 且 90% SLO。

链条在「异构 stage 需要异构调度」上闭合较好；ablation 定量分解了 hybrid 选型（−33% goodput）与 stage scheduling（−15%）的贡献。最弱环节是 **baseline 公平性与外推**：(1) 关闭 prefix cache / CUDA Graph 可能放大对 [[vLLM]]/[[SGLang]] 的优势；(2) EPDServe/DistServe 非原版而是 TriInfer 内实现，无法排除「实现调优不均」；(3) 从 8 实例穷举推广到 32 GPU 生产拓扑时，搜索空间与 queueing 行为是否仍接近最优未充分展开。

### 假设压力测试

**Workload**：数据集以 VQA/caption 为主，非 agent 式长链工具调用；到达过程虽来自生产 trace，但固定输出 token 数简化了真实 eos 行为。短输出（MME）已显示收益缩水；高 image 复用、强 prefix hit 场景未测（且实验故意关 prefix cache）。视频/音频阶段仅设计层面宣称可扩展，无实验。

**硬件**：H20 141GB 大显存集群 + NVLink/IB；迁移开销结论依赖 **同节点优先** 部署。更小显存 GPU 上 D 实例并发度公式（式 9 中 γ·(C−C_model)·N_r/(W_p+W_d)）可能迫使更小 batch，改变 stage 饱和权衡。未覆盖 Blackwell、消费级卡或纯以太网拓扑。

**规模**：vLLM/SGLang 用 32 实例，disagg baseline 用 32 实例特定 E/P/D 比；TriInfer 同样 32 GPU 但角色动态分配。更大集群下 profiler 组合数 **2·C(N−1,1)+C(N−1,2)** 仍可承受，但论文未给出 100+ GPU 的 replay 成本与收敛性。

**部署**：workload 稳定假设与「数分钟重配置」在小时级漂移下合理，对秒级 burst（促销、热点事件）可能滞后；**总 N 固定** 无法像动态 planner 那样随负载伸缩。多模型混部、多租户 SLO 隔离、故障切换均未讨论。

### 实验可信度

优点：三模型 × 五数据集 × 请求率扫描；明确 SLO 定义（TTFT + 90% TBT）；实现 disagg 强 baseline 并做组件 ablation；latency breakdown 与迁移 microbenchmark 支撑「迁移可忽略」主张；启发式 vs 穷举在小集群有排名证据。

限制：**prefix cache 与 CUDA Graph 禁用** 偏离生产默认；vLLM eager mode 可能进一步削弱 baseline；EPDServe/DistServe 非官方代码路径；未与 Sarathi-Serve、Mooncake、Rserve、Cornserve 等最新 MLLM disagg 工作直接对比；Table 1–5 部分数字在 markdown 中以图片形式存在，精确值依赖正文叙述；在线 tail latency（P99 TBT）报告不如 goodput 充分。

### 系统性缺陷

- **尾延迟与隔离**：stage-level 预算是均值/批执行时间导向，多租户混批时单请求被 chunk 或排队拖长的 **P99** 行为论文未系统给出。
- **故障恢复**：Ray actor 故障、迁移中途失败、部分实例卡死时的请求语义与 cache 一致性——**论文未讨论**。
- **可观测性 / 运维**：周期性拓扑切换、模型权重重载、profiler 失败回退的操作负担与监控接口未展开。
- **资源开销**：每实例独立 cache 与 on-demand 加载模型组件的内存碎片、冷启动延迟未量化。
- **正确性**：migrate 异步传 cache 的 page table 一致性依赖实现正确；无形式化验证或 chaos 测试描述。
- **兼容性**：仅 OpenAI 风格 REST；与现有 [[vLLM]]/[[SGLang]] 生态的直接替换成本未评估。

## 局限与 Future Work

- **局限 1**（论文自述）：workload 剧变时 profiler 决策会短暂次优；假设 workload 不会在极短时间尺度内剧烈变化。
- **局限 2**：集群总实例数由资源约束 **预先固定**，未做动态扩缩容或 fast role switching（列为 future work）。
- **局限 3**：评测聚焦 **image-text** MLLM；video/audio 仅停留在 stage 抽象，无端到端结果。
- **局限 4**：EPDServe、DistServe 以 TriInfer 内复现对比，非官方开源实现的直接 benchmark。
- **局限 5**：为公平关闭 **prefix cache 与 CUDA Graph**，与典型生产配置有差距。

- **Future work 1**：实现 **fast role switching** 与 **动态实例数调整**，量化对突发 workload 的 goodput 恢复时间 vs 当前数分钟级 redeploy。
- **Future work 2**：在 **开启 prefix cache / CUDA Graph** 的条件下重跑与 [[vLLM]]/[[SGLang]] 对比，分离「调度创新」与「禁用优化」带来的增益。
- **Future work 3**：跨节点为主部署时系统测量 KV vs image cache 迁移对 **P99 TBT** 的影响，验证 Table 4 在更大集群仍成立。
- **Future work 4**：将 profiler 与 [[NVIDIA-Disagg-Study]] 式 **rate matching / 在线 planner** 结合，在固定 N 与弹性 N 两种模式下画 goodput–SLO Pareto 曲线。

## 相关

- **相关概念**：[[Disaggregation]]、[[Continuous-Batching]]、[[Chunked-Prefill]]、[[KV-Cache]]、[[PagedAttention]]、[[LLM-Inference]]
- **同类系统**：[[vLLM]]、[[SGLang]]、DistServe、EPDServe、Sarathi-Serve、Mooncake、NanoFlow、Rserve、Cornserve、vLLM-Omni
- **同会议**：[[MLSys-2026]]、[[NVIDIA-Disagg-Study-MLSys26]]（PD 解耦设计空间）、[[GhostServe-MLSys26]]（serving 可靠性）
- **对比**：相对纯 LLM [[Disaggregation]]（DistServe 等）多 **encode 阶段** 与 **image cache** 迁移；相对固定 E+P+D 的 EPDServe，核心差异是 **SLO-aware 三拓扑自动选择** + **stage-level batching** + **双流共驻并行**