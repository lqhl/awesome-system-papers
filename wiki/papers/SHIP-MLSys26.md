---
type: paper
name: SHIP
full_title: "SHIP: SRAM-Based Huge Inference Pipelines for Fast LLM Serving"
authors: [Andrew Bitar, Aravind Vellora Vayalapra, Baorui Zhou, Matt Boyd, Charlie Wang, "et al."]
venue: MLSys
year: 2026
tags: [llm-serving, sram, groq, pipeline-parallelism, low-latency]
source_pdf: "[[7647966b7343c29048673252e490f736.pdf]]"
source_md: "[[7647966b7343c29048673252e490f736]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# SHIP: SRAM-Based Huge Inference Pipelines for Fast LLM Serving (MLSys 2026)

> **一句话总结**：在「decode 受 HBM 带宽限制、大批次抬高 TPOT」这一观察下，Groq 把 weights+KV 全放 on-chip SRAM，经 QuadFour 拓扑把数千 LPU 以 [[Tensor-Parallelism]]+[[Pipeline-Parallelism]] 串成 SHIP，配合 dynamic chunked prefill、fused context-batch 与 SRAM+host DRAM 两级 [[Prefix-Caching]]，在 OpenRouter 一个月实测中端到端延迟领先各模型次快 provider，日服务数百亿 token。

## 问题与动机

LLM serving 在 prefill（compute-bound）与 decode（memory-bound）间持续拉扯 SLO：HBM GPU 要靠大批次抬高 operational intensity（OI），但 reasoning 模型生成可达非 reasoning 的 **2–10×** token 量，P:D 比与 context length（CL）剧烈波动（Groq Cloud 7 天样本），固定 chunk 的 [[Chunked-Prefill]] 仍难同时稳住 TTFT 与 TPOT。[[MoE]] 的 data-dependent expert routing 进一步削弱 batching 收益。

Groq 的切入点是用 on-chip SRAM 的 **>10×** 内存带宽换低 batch 低延迟：LPU 设计点是 latency-first，而非 HBM 体系的 throughput-first。但 SRAM 容量极小（LPUv1 单卡 **230 MB**），必须把整模型 weights+KV 切到 **数百至数千** LPU，且 collective 延迟在 low-batch 下无法被独立 compute 掩盖——这是 SRAM serving 与 DRAM serving 的根本架构差异。论文是 LPUv1（GlobalFoundries 14 nm）生产回顾，声称 Groq Cloud 为首个大规模 SRAM LLM 公网部署。

## 关键观察 / 隐含假设

- **观察 1（decode OI 天花板）**：Qwen3-32B / gpt-oss-120B 上，self-attention 随 batch 与 CL 增长迅速主导 decode OI，MoE routing 使 batch 需极大才能抬高 expert MatMul OI；HBM GPU 常需 OI 达数百才接近算力饱和（Figure 3）。
  - **依赖假设**：生产 traffic 下难以长期维持足够大的 batch 来「喂饱」HBM；低 batch decode 是常态而非边缘 case。
  - **可能失效场景**：NVL72 等超大 TP 域 + 极高 batch 的 throughput-first 部署；或 SWA 等结构显著改变 attention 占比时，带宽瓶颈权重会变化。

- **观察 2（collective 在 low-batch 下暴露）**：SRAM inference 的 collective tensor 典型仅 **32–256 KiB**，且 batch 小导致无法像 GPU 那样用独立 batch item 掩盖 sequential dependency；TP scaling 的 AllReduce 延迟占比更大（引 Davies et al. 2025）。
  - **依赖假设**：C2C hop **300 ns**、低直径拓扑、compiler 静态调度能把 collective 压到可接受比例。
  - **可能失效场景**：更大 TP 分区（如 136-LPU 直径 **5 hop**）、异构 PP stage 不平衡、或 next-gen 模型 collective 尺寸跳变。

- **观察 3（context 利用率低）**：Groq Cloud 生产样本中 reasoning / 非 reasoning 模型分别有 **92% / 97%** 请求总 token < **8Ki**（Appendix D.1），为按需 [[PagedAttention]] 与 [[Prefix-Caching]] 提供空间。
  - **依赖假设**：prompt 实际长度远小于 max context；prefix 在多轮 agent / coding 场景有高复用（文献报告 hit rate 可 >90%）。
  - **可能失效场景**：长文档 RAG、单次超长 prompt、或 org 间严格 cache 隔离（Groq 强制 org 级隔离）削弱 hit rate。

- **观察 4（P:D 与 CL 动态波动）**：10 分钟滑动平均 P:D 持续变化（Figure 2）；固定 prefill chunk 迫使 TTFT/TPOT/吞吐三角权衡。
  - **依赖假设**：scheduler 能在每个 pipeline step 根据实时 traffic 调整 prefill chunk（可小至 **1–2 token**）且不伤因果正确性。
  - **可能失效场景**：极端 decode-heavy + 超长 CL 同时出现——论文承认 reasoning production trace 下 SHIP it/s/u 明显下跌。

- **假设 1（确定性同步可扩展）**：数千 LPU lock-step 同步、compiler cycle-accurate 调度、无 host 介入的中段 PP 可维持效率与可调试性。
  - **证据强度**：**强**——生产部署 + collective microbenchmark；但 prefix cache PCIe 回灌与 host DRAM 加载引入需重同步的非确定性，论文称已 overlap 处理。

- **假设 2（peak FLOP/s 效率低于 GPU 仍可经济）**：LPUv1 **388 W**/卡 vs B200 DGX **1788 W**/GPU，省 HBM/CoWoS/scale-up switch，可部分弥补算力效率差距。
  - **证据强度**：**中**——BOM/功耗分析详尽，但缺 TCO 端到端 dollar-per-token 对比与多租户利用率数据。

## 核心方法

**LPU + SHIP 架构**：LPU 为 tensor streaming processor，compiler 静态调度全部 FU；确定性 SRAM 访问 + 无仲裁 C2C 总线使 compiler 拥有 cycle-accurate 全局视图。八卡/节点 K8 clique，跨节点 **QuadFour** 拓扑（每节点 32 条 C2C link 连四前四后邻居）：72-LPU TP 分区 **16.56 GB** SRAM、网络直径 **3 hop**；支持 TP+PP 异构分区与故障节点 skip（最多跳 **3** 个 down 节点，Table 1 给出带宽衰减）。

**高效 collective（§4.2）**：compiler 选 RedBcast / TiledRedBcast / PAARD；8/64 LPU 上 **32 KiB** AllReduce 达 **50%** 带宽饱和、**80 KiB** 达 **90%**；MatMul+AllReduce 可 cycle 级 overlap（Figure 6b），但 compute–C2C 带宽失配仍留 exposed C2C cycles。C2C 小 tensor hop 延迟 sub-µs（**300 ns**/hop），对比 NCCL 典型 **1–10 µs**。

**内存容量管理（§5）**：
- 自研 [[PagedAttention]]：page **128–512** token；host 前端发 mask encoding 沿 PP 传播。
- 两级 [[Prefix-Caching]]：on-chip SRAM + 每节点 **1 TB** DDR4（gpt-oss-120B 72 节点实例可达 **51 TB** DRAM cache pool）；BlockTrie + rolling hash；SRAM hit 近零 TTFT，DRAM hit 需 preload 到 SRAM。7 天实测 DRAM cache hit **50–75%**（Figure 7）。
- [[Speculative-Decoding]]：draft 作为额外 PP stage；Llama3.3-70B 上 Llama3.1-1B/3B draft 显著加速，8B draft 即使高 acceptance 也难赢 non-SD（Figure 8）。

**动态平衡 pipeline（§6）**：
- **Dynamic chunked prefill**：chunk 可小至 **1–2 token** 即饱和 self-attention；runtime 按 P:D 动态放大 chunk 降 TTFT。
- **Fused context-batch**：统一各 stage 延迟，消除长短 context 混批 bubble；按 max CL 选 B，再 fuse B×C 维。
- **Capacity-filling prefill**：decode 优先，KV 空余算力填 prefill（共享 KV 访问）。
- **MoE**：小 batch 下 per-token expert 执行保 pipeline 平衡，牺牲 expert weight reuse（OI≈1），靠 SRAM 带宽兜底。

对比 baseline **SGB200**：Qwen3-235B-A22B 上 [[SGLang]] on B200 DGX，TP=8，MBTB=16Ki（高吞吐）/ 2Ki（低延迟）；SHIP 配置 TP=16、PP=95、max concurrency=380。

## 设计取舍

- **取舍 1：latency-first low-batch vs throughput-first high-batch**：SRAM 带宽换容量，必须上千芯片 + 低直径网络；峰值 FLOP/s 效率让位给 TTFT/TPOT 稳定性。
- **取舍 2：确定性同步 vs 异步灵活调度**：全局 lock-step 简化 overlap、pipeline balance、debugging，但 variable CL / expert / prefix PCIe 需 mask + gather/scatter 映射为静态 shape，增加 runtime 复杂度。
- **取舍 3：decode 优先 vs prefill 优先**：SHIP 选 decode 优先 + capacity-filling prefill，换更稳 TPOT；reasoning 长 CL production trace 下 it/s/u 会跌，但 mean TTFT 仍低于 SGB200。
- **取舍 4：per-token MoE vs 大 batch expert batching**：LPUv1 选 pipeline 平衡；下一代更大容量后策略需切换——论文明确标注。
- **边界条件**：中等偏高 P:D（>**8**）、CL < **4Ki** 时 system throughput 最稳；极低 P:D + 极高 CL 为已知弱区；单模型实例巨型 SHIP vs GPU 数据并行多实例的 prefix 协调复杂度不同。

## 实验与结果

- **生产端到端延迟**：Groq Cloud 一个月（2025-09-26 至 10-26）OpenRouter 数据，多模型平均端到端延迟优于各模型次快 provider（Figure 1）。
- **Qwen3-235B-A22B 受控实验**：SHIP 在 P:D >**8** 维持稳定 system throughput；低 P:D 在 CL <**4Ki** 仍较好；SGB200 高 P:D+大 MBTB 峰值吞吐更高，但 P:D/CL 变化时衰减更陡。
- **TPOT**：SHIP ot/s/u 跨 P:D/CL 更稳且绝对值显著高于 SGB200（Figure 10b/e）；fused context-batch 抑制长 CL 对 decode 的拖累。
- **TTFT**：SHIP decode 优先下 fixed traffic it/s/u 仍稳；reasoning production sample it/s/u 下跌，但 mean TTFT 仍优于 SGB200 全实验配置。
- **Production traffic**：非 reasoning 样本 (avg **1.4Ki**, max **24.3Ki** CL)；reasoning (**3.4Ki**, **98.9Ki**)。SHIP 峰值相对跌幅小于 SGB200，绝对吞吐更高。
- **Collective**：8/64 LPU，32KiB AllReduce **50%** 饱和；C2C **235 GB/s** vs B200 NVLink **1800 GB/s**，小 tensor 下 LPU 仍更优。
- **功耗**：LPUv1 **388 W**/LPU vs B200 DGX **1788 W**/GPU；无 HBM/CoWoS/scale-up switch，host 仅管 pipeline 首尾。

## Critical Analysis

### 论证链条

观察（HBM decode 带宽瓶颈 + low-batch collective 敏感 + 动态 P:D/CL）→ 设计（SRAM + 巨型 PP/TP + 细粒度 scheduling + 两级 prefix cache）→ 结果（生产延迟领先 + 受控实验 TPOT 更稳）链条**大体闭合**。薄弱环节：(1) Figure 1 为 Groq 自家云 vs OpenRouter 第三方，缺同硬件公平 baseline；(2) 受控对比仅 Qwen3-235B-A22B + SGLang B200，未覆盖自家模型的全矩阵；(3) 「数百亿 token/日」证明规模，但未分解 revenue-weighted SLO 达标率。

### 假设压力测试

- **Workload**：生产 trace 偏 Groq 用户分布；超长单次 prompt（>100K）在 reasoning sample 中出现但占比未知——二次 CL 成本会使 capacity-filling prefill 策略吃紧。
- **硬件**：回顾的是 LPUv1 14nm；文内承认 C2C 带宽/radix 约束 peak FLOP/s，next-gen 4nm 已投产但本文未量化。
- **规模**：数千 LPU 单实例 prefix cache 协调简单于 GPU 多实例数据并行（论文论点），但单点故障需 partition rotation + host DRAM 权重缓存——运维路径复杂，缺 MTTR/availability 数字。
- **模型族**：MoE per-token 执行对 DeepSeek 类极稀疏 expert 是否仍优，仅 Qwen3-235B 一点证据；dense 与 SWA 混合架构靠 compiler 静态 balance，runtime traffic 变化时是否需重编译未讨论。

### 实验可信度

- **Baseline**：SGB200 代表性强（[[SGLang]] + B200），两种 MBTB 覆盖吞吐/延迟权衡；但未对比 [[vLLM]]、TensorRT-LLM 生产调优版，也未对比 NVIDIA NVL72 类大 TP。
- **Metric**：覆盖 system throughput、t/s、it/s/u、ot/s/u、端到端 latency；**缺** P99 TTFT/TPOT、多租户 fairness、成本 per token、精度/确定性回归测试。
- **Ablation**：SD draft 选择、prefix 两级、dynamic chunk 等有部分 figure 支撑，但 fused context-batch / capacity-filling 缺少独立开关 ablation。
- **外部效度**：OpenRouter 延迟对比受路由、地理、计费模型干扰——作者未控制；更适合作「用户体验」证据而非严格 bench。

### 系统性缺陷

- **尾延迟**：强调 mean/moving average，**论文未报告** P99 TPOT 或排队理论分析；decode-priority 在 burst prefill 下对尾延迟影响未知。
- **故障恢复**：QuadFour skip-node + token replay 机制描述清楚，但缺故障率、恢复时间、replay 对 SLO 的冲击量化。
- **资源隔离**：org 级 prefix cache 隔离明确；同 org 多租户 KV/SRAM 竞争与抢占策略未讨论。
- **可观测性 / 运维**：巨型 deterministic pipeline 的 debug、版本滚动、模型热切换复杂度极高——论文未讨论。
- **兼容性**：高度绑定 Groq compiler + LPU ISA；与标准 GPU 软件栈（[[vLLM]] ecosystem）不可移植，属预期内但限制结论泛化。

## 局限与 Future Work

- **局限 1**：LPUv1 peak FLOP/s 效率低于 GPU，C2C 带宽失配导致 exposed communication；低 P:D + 高 CL 区域吞吐明显受限。
- **局限 2**：reasoning production traffic 下 it/s/u 显著下降——长 CL 二次成本与 decode-priority 的冲突未完全解决。
- **局限 3**：回顾性生产论文，缺独立第三方同条件 benchmark；TCO/$/token 仅有功耗与 BOM 论据，无完整经济模型。
- **局限 4**：prefix cache、PCIe DRAM 加载破坏确定性，需额外同步与 overlap 工程，增加设计脆弱点。
- **Future work 1**（论文 §7.3）：prefill-decode / attention-FFN [[Disaggregation]]，GPU 存 KV、LPU 跑 MoE-FFN，缓解 KV 容量瓶颈——已指向 NVIDIA Groq 3 LPX 方向，待完整评估。
- **Future work 2**（论文 §6.1）：adaptive scheduling heuristic，在 reasoning 混合 workload 下动态平衡 decode/prefill，可客观验证 it/s/u 跌幅能否收窄。
- **Future work 3**（可验证延伸）：next-gen LPU（更大 SRAM、更高 C2C radix）在 P:D <8 且 CL >32Ki 区域的吞吐曲线，检验「带宽换容量」假设的经济拐点。
- **Future work 4**：同模型下 SHIP vs B200 NVL72 的 P99 TPOT、$/1M token、prefix hit rate 三维对比，补齐 OpenRouter 端到端证据与受控 lab 之间的鸿沟。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Chunked-Prefill]]、[[Prefix-Caching]]、[[Speculative-Decoding]]、[[MoE]]、[[Continuous-Batching]]、[[Disaggregation]]、[[Expert-Parallelism]]
- **同类系统**：[[SGLang]]、[[vLLM]]、Google TPU serving 回顾、Cerebras WSE-3 SRAM serving
- **同会议**：[[MLSys-2026]]
- **对比**：SRAM low-batch latency-first（SHIP）vs HBM high-batch throughput-first（GPU + [[SGLang]]）；aggregated serving vs [[Disaggregation]]（Splitwise、DistServe、NVIDIA Dynamo）
