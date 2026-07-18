---
type: paper
name: DataflowIsAllYouNeed
full_title: "Dataflow Is All You Need"
authors: [Darshan Gandhi, Pushkar Nandkar, David Koeplinger, Nasim Farahini, Romy Tsoupidi, et al.]
venue: MLSys
year: 2026
tags: [dataflow, llm-inference, decode, speculative-decoding, sambanova, rdu]
source_pdf: "[[33e75ff09dd601bbe69f351039152189.pdf]]"
source_md: "[[33e75ff09dd601bbe69f351039152189]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Dataflow Is All You Need (MLSys 2026)

> **一句话总结**：基于「GPU decode 瓶颈不纯是 HBM 带宽上限，而是 kernel 同步与 compute-communication 未重叠导致有效带宽仅 ~21%」的观察，SambaNova 在 SN40 RDU 上用数据流原生异步执行实现 KernelLooping、BatchStreaming、ScheduleOffloading 三项协同优化，decode 达 roofline **45–78%**、[[Speculative-Decoding]] 端到端 **>6×**，16 片 SN40 在可比 HBM 带宽下比 DGX H100 快 **1.7×**。

## 问题与动机

开源大模型 context 窗口扩到 128K、chain-of-thought / reasoning 把输出:input token 比推到约 **10:1**，使 **decode 阶段**（memory-bandwidth-bound、低 operational intensity）成为推理吞吐与 PerfTCO 的主战场。Prefill 是 compute-bound；decode 的 Time-Per-Output-Token（TPOT）则由读权重与 [[KV-Cache]] 的 HBM 带宽主导。Context caching 进一步把优化重心从 prefill 挪到 decode。

作者在 GPU 上量到一条刺眼数字：Llama3.1-8B 在 8×H100 上约 **300 tokens/s**，但只用到总 HBM 带宽（24 TB/s）的 **21%** 来加载权重和 KV；4× GPU 扩到 8× 仅 **1.42×** 提速。Figure 2 的 TPOT breakdown 显示 GEMM 扩展尚可，但 AllReduce、RMSNorm、SDPA 等算子扩展差，且 collective **不与计算重叠**——MoE 相关工作报告约 **68%** 时间花在非重叠通信上。

Megakernel（Spector et al. 2025 等）通过大段融合减 kernel launch，但中间仍访问 HBM，且多聚焦单 GPU；NVSHMEM 等 GPU-GPU 通信仍经 global memory，对 decode 这类带宽敏感 workload 额外增 HBM traffic。更糟的是，[[Speculative-Decoding]] 在 GPU 上 draft 模型占每步 **72%** 时间（Llama3.1 8B draft + 70B target，k=9），而小模型在 GPU 上本身效率极低——整体 SD 加速被 draft 拖垮。CUDA Graphs 又与 [[MoE]] 动态 expert routing 不兼容。

论文 claim：要真正消除这些系统开销，需要 **dataflow 执行模型**——在 SambaNova SN40 RDU 上，大子图跨 chip 异步执行、chip 间经 on-chip PMU 直传、不经 HBM，计算/访存/通信由构造重叠。三项编译/运行时优化（KernelLooping、BatchStreaming、ScheduleOffloading）是这一架构假设下的 co-design 产物，而非可原样移植到 GPU 的 patch。

## 关键观察 / 隐含假设

- **观察 1**：GPU decode 低效的主因是 **kernel 边界强制同步** 与 **compute-communication 缺乏细粒度重叠**，而非 HBM 物理带宽本身已饱和。Llama3.1-8B 在 H100 上每层 decoder 拆成 **10** 个 kernel（K1–K10），32 层共 **320** 次调用/ token；megakernel 的 counter-based 依赖跟踪经 global memory 同步，报告开销 **>200 µs**、可占 sub-ms 推理预算 **>20%**。
  - **依赖假设**：decode 稳态下 operational intensity 低，任何「空泡」时间直接等价于丢带宽；[[Tensor-Parallelism]] allreduce 等 collective 占 TPOT 显著比例且当前栈默认串行化。
  - **可能失效场景**：若 workload 转向长 prefill、高 batch 使 GEMM 变 compute-bound，同步开销占比下降，dataflow 相对优势收窄；若 GPU 栈未来实现真正细粒度 async collective overlap（DeepEP、Comet 等方向），「GPU 必然低效」论断需重测。
  - **证据强度**：强。NVIDIA Nsight + TensorRT-LLM profiling、多 GPU scale 曲线、与 MoE 通信文献一致。

- **观察 2**：[[Speculative-Decoding]] 的端到端收益受 **draft 模型绝对速度** 强烈约束；小模型在 GPU 上扩展极差，使 SD 的 wall-clock 仍被 draft 主导。
  - **依赖假设**：draft/target 规模比大（如 8B draft + 70B target）；k 较大（实验常用 k=9）；acceptance rate AR 足够高使多跑 draft 仍划算。Table 1 显示 AR 随 k 增大而下降，HumanEval > AlpacaEval。
  - **可能失效场景**：draft 与 target 分布失配、AR 极低时，ScheduleOffloading 与 BatchStreaming 对 draft 的优化无法弥补无效 speculation；极大 target（405B）在 H100 上 OOM，比较基线缺失。
  - **证据强度**：中到强。有 acceptance rate 测量 + SD 时间分解；但 DGX H100 数字来自 standalone draft/target benchmark 外推（equation 4），作者承认对 SD overhead 与长序列效应 **偏乐观**。

- **观察 3**：数据流硬件上，**轻量级 producer-consumer handshake**（纳秒级、与计算流水线化）可替代 SIMT 架构经 HBM 的昂贵同步，使 KernelLooping（跨层 pipeline）、BatchStreaming（跨样本 pipeline）、chip-to-chip AllReduce（不经 HBM）在编译器层可泛化实现。
  - **依赖假设**：SN40 有 520 MB/socket on-chip SRAM、P2P 直连接口、AGCU 硬件 graph orchestration；整层 decoder 可融合为单 kernel K0；权重需按层打包以配合 KernelLooping 的 HBM 读取模式。
  - **可能失效场景**：模型结构非重复 decoder block（新 attention 变体、动态 shape）时 Pattern Matching 失败；on-chip SRAM 放不下融合子图时需 spill 到 HBM，破坏「中间不访 HBM」前提；多 tenant 混部时 ScheduleOffloading 的静态 schedule 链与动态 batch 交错，论文未评估。
  - **证据强度**：强（架构 + 编译 pass 描述 + HBM 利用率 trace）；跨硬件泛化性证据仅限 SN40-16。

- **假设 1**：在 **可比 aggregate HBM 带宽** 下，消除同步与重叠通信足以让 SN40 在 speculative decode 上显著超越 DGX H100，而不依赖更高峰值 FLOPs。
  - **证据强度**：中。Table 3 列出 SN40-16 与 8×H100 带宽相近；但 SN40 还有大容量 on-chip memory、不同数值格式与编译栈，「仅带宽可比」是简化。

## 核心方法

论文围绕 SN40 RDU 的数据流执行模型展开三项优化，均映射到上述观察。

**SN40 系统概要**：每 socket 638 TFLOPs BF16、520 MB SRAM、64 GB HBM @ 1.6 TB/s；1040 PCU（systolic/streaming compute）+ 1040 PMU（512 KB 可编程 on-chip memory）经 RDN 互联；AGCU 提供 HBM/DDR/host/remote RDU 访问与 **P2P chip-to-chip 直传**（不经 HBM），并支持硬件 graph orchestration 无 host 参与地 launch kernel。编译器输出 PEF（Processor Execution Format），含 kernel 序列与 schedule。

**KernelLooping（编译器）**：识别重复 decoder 调用序列，折叠为带外循环的单一 kernel，吸收迭代间数据依赖、在片上 double-buffer 中间结果。Llama3.1-8B：H100 **320** 次/ token → SN40 **4** 次/ token（embedding + 32 层 looped decoder + classifier + sampling）。AllReduce 与 Down GEMM、Add 异步流水线，数据经 P2P 直写远端 PMU。用户 decorator 标定 loop 范围；编译器分两阶段 Pattern Matching + Transformation（concat input、引入 iterator、按层次分配 buffer）。Geomean **1.6×**，Qwen2.5-72B 近 **2×**；Figure 11 HBM 利用率 trace 显示消除周期性带宽空洞。

**BatchStreaming（编译器）**：batching 在 decoder 层边界引入「等同层全部样本完成才进下一层」的人为同步，小 draft 模型每层仅数微秒，warm-up 成本每层重复。LoopBuffer（多 PMU 组成的虚拟 scratchpad）在层间提供非阻塞通道：一样本完成即写入、下一层可读即消费，样本在层间流水线交错（Figure 7）。batch=1 无收益；batch 2→8 收益递增，16 时 1B/3B 略回落（warm-up 已充分摊销）。

**ScheduleOffloading（运行时）**：默认每 token 生成后 control 回到 host。运行时动态拼接 PEF 内 schedule，使 SN40 硬件编排连续生成 M 个 token（Figure 9），M 由 speculation window k 与 I/O 启发式决定、实践中 ≤ k、收益在 M≈20 plateau。对 SD：draft 连续 k 次运行与 target 验证可 offload，减 host 调度开销；兼容 [[MoE]] 动态 routing——对比 CUDA Graphs 的静态 capture 限制。k=9、生成 9 token 时 draft-only 提速显著，小模型更大。

设计映射：观察 1 → KernelLooping + 层内/跨层 async fusion；观察 2 → BatchStreaming 加速 draft + ScheduleOffloading 减 host 气泡；观察 3 → 全三项依赖 dataflow handshake 与 P2P。深度实现见 [[33e75ff09dd601bbe69f351039152189]] / [[33e75ff09dd601bbe69f351039152189.pdf]]。

## 设计取舍

- **专用 dataflow 栈换可移植性**：优化深度绑定 SN40 编译器、PMU/PCU 拓扑与 P2P 协议；无法作为 [[vLLM]] / TensorRT-LLM 插件直接复现。收益是整层融合 + 跨 chip async collective 的结构性重叠。
- **激进融合换编译与 checkpoint 成本**：KernelLooping 要求权重按层打包、compiler metadata 驱动 checkpoint 预处理；用户需 annotation loop 区域。编译本身开销可忽略（只编译一个 decoder graph），但 **迁移新模型有人工标注与权重重排成本**。
- **ScheduleOffloading 换动态性边界**：M 的上界与 k 绑定，过长 unroll 的 PEF schedule memory 线性增长（虽仅数 MB）；MoE 虽兼容，但极动态 workload（runtime shape、频繁图切换）是否仍优于 CUDA Graphs 需个案验证。
- **Roofline 建模换分析简洁性**：equation 3 假设纯 HBM-bound；大 batch 时 Figure 15 显示「SN40-Excess」上升——compute-bound 行为与 I/O 未完全捕获。
- **边界条件**：memory-bound decode、TP 多卡、SD with 小 draft 时最优雅；长 context 下 draft KV 膨胀削弱 SD 相对优势（Section 5.6）；405B 等超大模型在 H100 上无法作为对照。

## 实验与结果

- **平台**：SN40-16 vs DGX H100（8×H100）；TensorRT-LLM benchmark vs SN40 10 prompts 稳态 TPOT。模型覆盖 GPT-OSS、DeepSeek-R1、Llama、Mixtral、Qwen 等 dense/MoE/hybrid、GQA/MLA 等 attention（Table 2）。
- **KernelLooping**：多架构/ batch/ 序列长度 geomean **1.6×**；Qwen2.5-72B 大 batch 近 **2×**。
- **BatchStreaming**：Llama 1B/3B/8B draft，batch 2–16 显著提速；1B/3B 对 batch 更敏感（更高 compute-to-memory 比）。
- **ScheduleOffloading**：k=9 生成 9 token，小模型、小 batch 提速最高；大 batch 相对收益下降（host 占比变小）。
- **端到端 SD**：三项合计 **>6×** vs 无优化 target；SN40-16 达 roofline **45–78%**（模型越大效率越高）；Llama3.1 70B + 8B draft SN40 比 H100 **快 60–80%**；16 SN40 vs DGX H100 speculative decode **1.7×**（可比 HBM 带宽）。
- **Batched SD（Table 4）**：draft:target 越大、k 越大通常越快；但 batch↑ 或序列 4K→32K 时 SD speedup **递减**（draft KV 与 weight load 摊销变差）。
- **部署**：cloud.sambanova.ai 全模型上线；第三方 benchmark（Artificial Analysis、OpenRouter）可查 TTFT/吞吐。

## Critical Analysis

### 论证链条

「GPU decode 有效带宽低源于同步与未重叠通信」→「dataflow 原生 async + 三项优化」→「roofline 45–78%、SD >6×、比 H100 1.7×」在 **SambaNova 自有硬件 + 自家编译栈 + decode-heavy SD workload** 下链条较闭合。KernelLooping / BatchStreaming / ScheduleOffloading 分别有独立 ablation，支持「开销可分解」叙事。

薄弱跳步在于：**H100 数字部分由 SN40 trace 驱动的 optimistic 估计（equation 4）**，未在同一 SD 栈上端到端复现；因此「1.7×」是强结论但 baseline 可能偏乐观。另一跳步：将「21% HBM 利用率」外推为「GPU 架构根本局限」——未排除 TensorRT-LLM / NCCL 实现层改进后利用率显著上升的可能。

### 假设压力测试

- **Workload 变化**：实验以 decode 稳态、SD 为主；prefill-heavy 或极短输出场景论文非重点。Reasoning 模型 10:1 输出比是动机，但长序列下 draft KV 膨胀使 SD 优势缩小——论文有测量但未给 production trace 验证。
- **硬件变化**：结论绑定 SN40 P2P + 大 SRAM；迁移到其他 dataflow（Groq、Cerebras）或下一代 GPU（更强 async copy、NVLink SHARP）需重测。仅比 aggregate HBM 带宽忽略 on-chip memory 容量差异。
- **模型变化**：声称泛化 dense/MoE/hybrid/GQA/MLA，但 KernelLooping 依赖重复 block 结构；新架构（linear attention、SSM hybrid）可能破坏 pattern。Checkpoint 重排对每新模型族有工程税。
- **多租户 / SLO**：batch streaming 与 schedule 链在单 job 内流水线化；混部、抢占、尾延迟隔离论文未讨论。

### 实验可信度

- **Baseline 公平性**：H100 用 TensorRT-LLM 公开 benchmark，属强工业基线；但 SD 对比用外推而非统一 runtime，对 H100 可能有利（未计 CPU draft↔target 调度）。405B 在 H100 OOM 使最大模型对比单向。
- **Ablation**：三项优化分别有 Figure 10–13；Figure 14–15 有 roofline 与 time breakdown。缺少「仅 fusion 无 looping」「仅 ScheduleOffloading 无 BatchStreaming」的完全 factorial，但主结论仍有多维支撑。
- **Metric**：主报 decode throughput / TPOT；TTFT、P99 tail、per-dollar TCO 非重点。生产部署引用第三方 benchmark，增强外部可信度但细节不可复现。

### 系统性缺陷

- **供应商锁定与可复现性**：全文基于 SambaNova 商业云与 RDU，开源社区无法独立验证 SN40 数字；与 GPU 论文的开放生态不对称。
- **Host 与 SD 算法开销**：Figure 15 显示 Host slice（acceptance、logits）随 batch 仍占可观比例；ScheduleOffloading 减 token 级 host 往返，但未消除 CPU 侧 speculation 逻辑。
- **尾延迟与可观测性**：未报 P99 TPOT 或 acceptance 波动对用户体验的影响；k 增大时 AR 下降带来性能方差（Table 1 已暗示）。
- **故障恢复 / 多租户**：硬件 orchestration 长 schedule 链在 fault、preemption 下的行为论文未讨论。
- **与 megakernel 路线关系**：承认 megakernel 进展但未 head-to-head 同模型同 batch 对比最新 GPU megakernel 实现。

## 局限与 Future Work

- **局限 1**：评估绑定 SN40-16 与 TensorRT-LLM on H100，跨栈 SD 对比依赖 optimistic 建模，非统一 serving runtime。
- **局限 2**：roofline 为 HBM-centric，大 batch 时 compute 与 excess I/O 未完全解释；未系统报告 tail latency、多租户隔离。
- **局限 3**：KernelLooping 需模型结构重复性与 checkpoint 预处理；新模型族有持续编译/权重工程成本。
- **Future work 1**：在 GPU 上实现同等粒度的跨层 looping + async collective（或测量 megakernel + NVSHMEM 改进后 HBM 利用率能否逼近 SN40），分离「架构」与「软件栈」贡献。
- **Future work 2**：长 context（32K+）production trace 下量化 batched SD 的 speedup 衰减曲线，并联合 acceptance rate 方差做 SLO-aware k 选择。
- **Future work 3**：ScheduleOffloading 与 [[Continuous-Batching]]、[[Disaggregation]]（prefill/decode 分离）共存时的 schedule 拼接与 host 边界——论文未覆盖 PD 分离部署。

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[KV-Cache]]、[[MoE]]、[[Tensor-Parallelism]]、[[Continuous-Batching]]、[[Disaggregation]]
- **同类系统**：TensorRT-LLM、[[vLLM]]、[[SGLang]]、megakernels（Mirage、FlashDMoE）、CUDA Graphs、Groq/Cerebras 类 dataflow 推理
- **同会议**：[[MLSys-2026]]
- **对比**：相对 GPU megakernel 强调多 chip async P2P 不经 HBM；相对 CUDA Graphs 强调 MoE 与 SD 动态 schedule 兼容；相对纯带宽对标，额外依赖大 on-chip SRAM 与编译期层融合
