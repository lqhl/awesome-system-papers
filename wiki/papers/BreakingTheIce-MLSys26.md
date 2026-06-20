---
type: paper
name: BreakingTheIce
full_title: "Breaking the ICE: Analyzing Cold Start Latency in vLLM"
authors: [Huzaifa Shaaban Kabakibo, Animesh Trivedi, Lin Wang]
venue: MLSys
year: 2026
tags: [vllm, cold-start, serverless, inference, profiling, autoscaling]
source_pdf: "[[32bb90e8976aab5298d5da10fe66f21d.pdf]]"
source_md: "[[32bb90e8976aab5298d5da10fe66f21d]]"
---

# Breaking the ICE: Analyzing Cold Start Latency in vLLM (MLSys 2026)

> **一句话总结**：首次把 [[vLLM]] 冷启动拆成 6 个可量化步骤并证明整体以 CPU 为主（H100→L40S 几乎无加速）；分步线性回归预测器在 22 个 dense 模型上 MSE 2.42 s、最大误差 2.08 s，为 serverless autoscaler 提供可解释启动成本模型。

## 问题与动机

Serverless LLM serving 在突发流量下频繁拉起冷容器，冷启动延迟往往比 warm instance 高几个数量级，直接拉高 TTFT。已有 ServerlessLLM、ParaServe、Medusa 等工作分别优化 checkpoint 加载、pipeline 重叠、state materialization 等**局部环节**，但缺少对 [[vLLM]] 端到端 engine initialization 的系统刻画。

论文 claim 这一 gap 在 [[vLLM]] 上尤其突出：代码库 ~280K 行 Python、V1 API 与 `torch.compile` 快速演进，近 1.5 年 9 个 major release 启动时间方差 >4×（v0.9→v0.10 甚至减半）。NVIDIA Dynamo、LLM-D、AIBrix 等容器化推理蓝图需要准确的 worker 启动成本模型来驱动 autoscaler，但现有 profiling 把启动当作整体生命周期的一环，未单独建模 engine 内部步骤。

本文**有意隔离**容器启动、远程存储、网络等分布式因素，专注 vLLM 从 engine 初始化到打印 "Application startup complete" 的 node-local 行为。完整测量协议与脚本见 [[32bb90e8976aab5298d5da10fe66f21d]] 或开源 profiler：https://github.com/upb-cn/vllm-startup-profiler

## 关键观察 / 隐含假设

- **观察 1：vLLM 启动可稳定分解为 6 个 foundational steps，且除 KVCache profiling 与 CUDA graph capture 外均以 CPU 为主导瓶颈。**
  - **证据**：Llama3.2-3B 总启动 20.32 s 的 breakdown（Fig. 2）；H100 vs L40S 对比中仅 CUDA Graph Capturing 有 1.2× 加速，其余步骤几乎无差异（Fig. 10）；换 AMD EPYC 9354→Intel Xeon 8568Y+ CPU 的影响大于换 GPU（Fig. 11）；per-core 利用率显示任意时刻仅 ~1 核满载（Fig. 12）。
  - **依赖假设**：v0.10.1.1 的 V1 架构下这 6 步仍代表未来 release 会优化而非消除的基础路径；测量日志粒度足以分离各 step。
  - **可能失效场景**：若未来 release 大幅并行化 bootstrapping / `torch.compile` / graph capture，或把更多步骤 offload 到 GPU/async pipeline，「CPU-bound 主导」结论会弱化；MoE、diffusion、SSM-hybrid 等架构可能引入新步骤或改变 profiling 行为。

- **观察 2：各 step 对特定参数呈稳定近线性缩放，可用少量特征做分步归因。**
  - **证据**：Tokenizer init ↔ tokenizer 文件大小（PCC=0.99）；weight loading ↔ 参数量×精度（PCC=1.0）；Dynamo 变换 ↔ compiled graph 总大小（PCC=0.96）；graph 加载 ↔ graph 大小（PCC=0.95）；KVCache profiling（禁用 compile 后）↔ dense 模型大小（PCC=0.92）；CUDA graph capture ↔ 模型大小与 batch size 数（PCC≈1.0）。
  - **依赖假设**：线性关系在训练/验证覆盖的 22 个模型、FP16、默认 runtime flag 下成立；compiled graph cache 已 warm（冷 cache 成本另计）。
  - **可能失效场景**：[[MoE]] 在 KVCache profiling 偏离线性（expert routing）；量化格式改变 weight volume；极大 batch size 配置数使 graph capture 成为绝对主导；新 attention 变体（MLA 等）改变 per-layer graph 复杂度与线性 proxy 的适用性。

- **观察 3：多数「直觉上可优化」的 I/O 与 GPU 升级对总启动影响有限，因为耗时集中在 CPU 侧编译与框架路径。**
  - **证据**：SSD 冷读仅让 weight loading 慢 0.5×，总启动只改善 1.04×（该步占 7–10%）；Tensorizer 比 Safetensors 快 53–60% 仍只压缩 Model Loading 子步；禁用 compile cache 时 graph storing 从 3–6 s 飙到 11–21 s，说明 compile 路径才是大头。
  - **依赖假设**：实验在 warm DRAM page cache 或高速 PCIe 5.0 SSD（25 GB/s read）下进行，I/O 不是全局瓶颈；生产部署的 checkpoint 已在本地或高速缓存。
  - **可能失效场景**：checkpoint 必须从慢速远程对象存储流式拉取、容器镜像层冷启动、或权重远大于 GPU 显存需分片加载时，Model Loading 占比会上升，观察 3 的「边际收益小」可能不成立。

- **假设 1：分步独立线性回归聚合后，可准确预测 unseen dense 模型的总启动时间，足以支撑 autoscaler 资源规划。**
  - **证据强度**：中强。验证集 MSE 2.42 s、最大误差 2.08 s（Llama3-3B），v0.11 上 MSE 2.62 s 仍成立；但训练需数小时自动化 profiling，且仅覆盖 non-MoE 模型与受控实验环境。

- **假设 2：六步分解与线性规律在 vLLM 快速版本迭代中保持方法论层面的 longevity——参数需重训，结构不需推倒重来。**
  - **证据强度**：中。作者论证这些 stage 是 inference engine 固有操作；v0.11 验证支持预测器仍准，但近 1.5 年 4× 方差说明单点数值不可移植，且 v0.11 的 ModelClass caching 等优化会改变 Framework Bootstrap 绝对值（论文未在 v0.11 上重跑全部分解）。

## 核心方法

论文贡献是 **measurement + decomposition + predictor**，而非新 inference runtime。方法链分三层：

**1. 六步分解与归因**（回应观察 1–2）：

| 步骤 | 功能 | 主导资源 | 关键缩放参数 |
|------|------|----------|--------------|
| Framework Bootstrap | 平台探测、依赖 import、模型元数据、Ray/multiprocessing worker | CPU | 与模型规模基本无关 |
| Tokenizer Initialization | 词表与 merge rules 加载 | CPU | tokenizer 文件大小 |
| Model Loading | 结构实例化 + checkpoint→GPU | CPU（传输 orchestration） | 参数量×精度；结构 init ~0.1 s |
| `torch.compile` | Dynamo bytecode 变换 + compiled graph 加载 | CPU | compiled graph 总大小 |
| [[KV-Cache]] Profiling | dummy forward 测峰值显存以分配 cache | GPU（forward） | dense：模型大小；[[MoE]]：非线性 |
| CUDA Graph Capturing | 录制 kernel 序列供 replay | GPU | 模型大小 × 待 capture 的 batch size 数 |

**2. 环境敏感性实验**（回应观察 3）：在 H100/L40S、AMD/Intel CPU、DRAM vs SSD、Safetensors/Run:ai Streamer/CoreWeave Tensorizer、compile cache on/off 等维度上重复分解，量化哪些优化**值得**投入 autoscaler 设计。

**3. 白盒分步预测器**（回应假设 1）：对 non-MoE 模型，每步独立拟合线性回归，输入为模型配置（层数、参数量、tokenizer 大小、graph 大小等）与环境特征，输出聚合为总启动时间。工作流：收集模型元数据 → 自动化跑 vLLM 采日志（数小时）→ 逐步训练 → 预测。设计刻意拒绝 monolithic black-box NN，以保留逐步可解释性，便于诊断 regression（如 [[vLLM]] issue #29676）和估计 sleep mode 等部分路径复用场景。

与 [[vLLM-SOSP23]] 的分工：后者刻画 steady-state serving（[[PagedAttention]]、[[Continuous-Batching]]）；本文刻画 **cold path**，回答「新 worker 多久能接请求」而非「接了之后吞吐多少」。

## 设计取舍

- **Engine-only scope vs 端到端 cold start**：隔离容器、网络、远程存储使因果归因清晰，但 serverless TTFT 仍包含镜像拉取、调度排队等论文未建模部分；autoscaler 需把 predictor 输出当作下界而非完整 SLA。
- **线性分步回归 vs 全局非线性模型**：可解释、易局部重训（某步 API 变了只重训该 regressor），但无法捕捉 step 间隐式耦合（如 profiling 阶段内嵌 compile overhead 曾导致测量失真，需显式 disable compile 才看清 intrinsic profiling）。
- **Non-MoE 预测器 vs 全覆盖**：放弃 MoE/SSM-hybrid 的 KVCache profiling 线性拟合，换得验证集 2 s 级误差；MoE 需更 expressive 模型，作者标为 ongoing work。
- **受控实验环境 vs production noise**：五次平均、固定 node、关闭部分 runtime flag 变异，提高可重复性；真实多租户、NUMA、后台负载、日志粒度误差（可达数百 ms）会抬高预测残差——论文在 §5 明确承认。
- **开源 profiler 负担 vs 闭源曲线**：公开脚本与 Zenodo artifact 利于复现，但完整复现需 ~600 GB 模型与多 GPU/多 CPU 节点（部分 figure 需跨机器），运维成本高。

## 实验与结果

- **规模**：22 个 LLM（dense/[[MoE]]/GQA/MLA 等）× NVIDIA H100/L40S × AMD EPYC 9354 / Intel Xeon 8568Y+ / Gold 5520+；主实验 vLLM v0.10.1.1，每配置 5 次平均
- **版本方差**：9 个 major release（OPT-6.7B @ H100）启动时间方差 >4×；v0.9→v0.10 约 2× 加速
- **预测器**：non-MoE 模型，5 个留作验证（Falcon-11B、Gemma-7B、Mistral-7B、Llama3-3B、Qwen-7B）；**MSE 2.42 s**，**最大误差 2.08 s**（Llama3-3B）；v0.11 验证 **MSE 2.62 s**
- **Compile cache**：禁用后 graph storing **11–21 s**（vs 缓存命中 **3–6 s**），与 graph 大小近线性（PCC=0.95）
- **存储**：SSD 冷读使 weight loading 慢 0.5×，**总启动仅 1.04×** 变化（该步占 7–10%）
- **加载 backend**：CoreWeave Tensorizer 达 Safetensors 的 **53–60%** 耗时；Run:ai Model Streamer 居中
- **GPU 升级**：H100→L40S 对总启动几乎无收益；仅 CUDA graph capture **1.2×**
- **CPU 升级**：换 CPU 对各 step 影响不一致但总体显著于换 GPU；单核饱和暗示并行化空间有限
- **Batch size 敏感性**：Llama2-7B 的 CUDA graph capture 从 3 个 batch size（0.33 s）到 60 个（1.8 s）近线性增长

## Critical Analysis

### 论证链条

observation → design 链条在「理解 vLLM 启动」这一 measurement paper 上是闭合的：六步分解直接来自 profiling 日志与对照实验；线性规律用 PCC 与 hold-out 模型验证；预测器是这些规律的直接聚合，而非独立 magic。

最脆的跳步是 **从受控 node-local 测量外推到 production serverless cold start**。论文诚实限定 scope（§5 Benchmarking Scope），但摘要与结论仍强调 autoscaler 应用——中间缺少把容器拉取、模型缓存命中、多副本并行启动叠加后的端到端验证。predictor 准确预测 engine init，不等于准确预测用户可见 TTFT。

第二个跳步是 **「六步在快速迭代中 longevity」**。方法论合理（这些操作确为现代 inference engine 共性），但 Fig. 1 的 4× 版本方差证明**绝对耗时与相对占比**会变；autoscaler 若缓存一次 profiling 结果数月，可能在新 minor release 后系统性偏差。v0.11 ModelClass caching（Get Model Info 4.47 s→0.12 s）说明单步可剧变，modular retrain 能缓解但需运营流程。

### 假设压力测试

**Workload**：生产 trace 峰值/均值比 2–20× 证明冷启动频繁，但论文未用真实 trace 驱动「何时扩容」仿真，仅提供延迟估计工具。burst 下并行启动多个 worker 时的 CPU/PCIe 争用未测。

**硬件**：仅 NVIDIA H100/L40S + 两款 x86 CPU；AMD GPU、消费级 GPU、ARM server、无 SSD 边缘节点上 CPU-bound 结论可能仍成立，但线性系数需全量重训。论文承认 predictor 绑定采集环境。

**模型**：22 个开源 HF 模型以 FP16 为主；INT4/INT8、超大 MoE（DeepSeek-V2-Lite 仅部分覆盖）、embedding-only、多模态 pipeline 可能新增步骤或改变 compile graph 规模 proxy。

**部署形态**：实验为单 worker 单 GPU 初始化；tensor parallel / pipeline parallel worker 群的启动同步、rank0 广播权重、分布式 compile cache 共享均未覆盖——而这正是 Dynamo/LLM-D 类系统的实际扩容单元。

### 实验可信度

**强项**：(1) 首次对 [[vLLM]] 全路径六步分解，填补社区 issue 级碎片化诊断的空白；(2) 22 模型 × 多硬件的 scaling 规律一致且可解释；(3) 预测器 hold-out 验证 + v0.11 交叉验证；(4) 对 compile cache、SSD、加载 backend 等「可操作 knob」有定量 ablation；(5) artifact 开源且可复现 figure 脚本。

**弱点**：(1) 主分解基于 v0.10.1.1，版本方差大但仅 Fig. 1 展示跨版本总时间，未逐步归因历史回归；(2) MoE profiling 非线性仅定性，预测器明确排除 MoE；(3) CPU 微架构归因「ongoing」，Fig. 11 步间 speedup 方向不一致说明单因子解释不足；(4) 日志粒度误差可达数百 ms，对 <1 s 子步（tokenizer、结构 init）相对误差大；(5) Docker/Python/PyTorch 版本、常见 runtime flag 声称无显著影响，但缺少公开敏感性矩阵。

### 系统性缺陷

- **并行启动与资源隔离**：论文未讨论多容器同节点启动时的 CPU、PCIe、磁盘带宽争用；autoscaler 若按单实例模型加总容量可能低估墙钟时间。
- **尾延迟与失败路径**：仅报告平均启动时间；OOM 重试、compile 失败回退、HF 元数据拉取超时等 tail 与 failure mode 未刻画。
- **可观测性落地**：分解依赖定制 profiling patch；生产集群是否愿意 fork vLLM 或等官方 OpenTelemetry startup tracing（issue #19318）集成，论文未给轻量 agent 方案。
- **运维成本**：predictor 训练需数小时 GPU 跑分；Dynamo 推荐的多小时离线 profiling 与此同类，对小团队仍是负担。
- **安全与供应链**：Get Model Info 涉及 HF 拉取；冷启动路径加载大量 Python 插件，论文未讨论 supply-chain 或沙箱开销。

## 局限与 Future Work

- **局限 1**：scope 仅限 engine initialization，不含容器、网络、远程存储——端到端 serverless cold start 需另建模型。
- **局限 2**：预测器对 [[MoE]]、SSM-hybrid、diffusion 的 KVCache profiling 非线性尚未纳入；线性假设在 MoE 上已显式失效。
- **局限 3**：测量噪声与日志粒度限制；背景负载、NUMA、调度器争用未系统量化。
- **局限 4**：CPU 性能差异的 microarchitectural 根因分析未完成，跨 CPU 迁移只能重训而非外推。
- **局限 5**：单 worker 设定不覆盖分布式 worker 群启动与 TP/PP 权重分片加载。
- **Future work 1**：将 predictor 嵌入真实 serverless orchestrator（LLM-D、Dynamo 等），用 production trace 做 closed-loop 仿真，验证 proactive scale-out 能否在 burst 前隐藏冷启动。
- **Future work 2**：重叠或并行化 `torch.compile`、[[KV-Cache]] profiling、CUDA graph capture（当前单核饱和暗示 headroom），测量 wall-clock 压缩上限。
- **Future work 3**：为 MoE 与动态 expert routing 建立 KVCache profiling 的非线性子模型，扩展预测器覆盖面。
- **Future work 4**：端到端 cold start 分解（容器 + engine + 网络），与本文 engine 模型拼接成可解释全栈 TTFT 预算。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[MoE]]、[[Chunked-Prefill]]、[[Pipeline-Parallelism]]
- **同类系统**：ServerlessLLM、ParaServe、Medusa、NVIDIA Dynamo、LLM-D、AIBrix、[[vLLM]] Production Stack
- **同会议**：[[MLSys-2026]]
- **对比**：[[vLLM-SOSP23]]（steady-state serving 优化 vs 本文 cold start 刻画）