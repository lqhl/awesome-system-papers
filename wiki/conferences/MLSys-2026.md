---
type: conference
venue: MLSys
year: 2026
paper_count: 135
first_generated: 2026-04-24
last_updated: 2026-06-20
---

# MLSys 2026

> 136 篇论文（136 PDF，含 1 份 EventTensor 重复稿对应单一 wiki 页），[[KV-Cache]] / attention / [[Speculative-Decoding]] / serving 调度四条 LLM 推理主线占 ~35%，[[MoE]] 训练与推理加 serving tax 分析成建制议题，AI4AI（LLM 自动生成 kernel / HDL / 优化算法）与 Agent 系统（SDK / 记忆 / 安全）并列扩张，联邦学习与可审计 ML（ZK、GPU-CC、确定性复现）形成独立集群。

## 概览

**LLM 推理系统仍是中心引力场，且从「单点优化」走向「全栈编排」**。17 篇 serving 论文覆盖调度、disaggregation、冷启动、serverless 弹性、多模型路由与声明式 IR。[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]]、[[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]]、[[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] 三类「pragmatic take」式经验研究首次密集进场——MLSys 2026 已经过了「disaggregation 能否 work」的阶段，进入「哪些工作负载该 disagg、怎么 rate match、MoE 税多少」的细粒度优化时代。[[BreakingTheIce-MLSys26|BreakingTheIce]]、[[FaaScale-MLSys26|FaaScale]] 则把 serverless 冷启动与秒级弹性扩缩推上议程。

**MoE 问题开始主导大模型系统设计**。6 篇专攻 [[MoE]] 的论文外加 MoE-aware 调度（[[LayeredPrefill-MLSys26|LayeredPrefill]]、[[CRAFT-MLSys26|CRAFT]]）表明 MoE 系统已脱离「vanilla dense serving 的变种」成为独立议题轴。所有论文都把 Kimi-K2 / DeepSeek-V3 当作默认 baseline——1T 参数的开源 MoE 已经是「标准测试集」。

**RAG 从应用补丁升级为推理一等公民**。[[TeleRAG-MLSys26|TeleRAG]]、[[ContextPilot-MLSys26|ContextPilot]]、[[SpanQueries-MLSys26|SpanQueries]]、[[LEANN-MLSys26|LEANN]]、[[Terminus-MLSys26|Terminus]] 五条线分别优化 retrieval-to-generation 间隙、context reuse、声明式 locality、端侧索引与 early termination——RAG 不再是 serving 的附带场景，而是与 prefill/decode 并列的调度维度。

**AI4AI 与 Agent 系统同步扩张**。7 篇 LLM agent 生成 kernel / HDL / 数据的工作（[[AccelOpt-MLSys26|AccelOpt]]、[[PIKE-MLSys26|PIKE]]、[[TritorX-MLSys26|TritorX]]、[[VeriMoA-MLSys26|VeriMoA]]、[[LLaMEA-KernelTuner-MLSys26|LLaMEA-KernelTuner]]、[[Matrix-MLSys26|Matrix]]、[[RocketPPA-MLSys26|RocketPPA]]）外加 [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] 基准框架，与 8 篇 Agent SDK / 记忆 / 安全论文（[[OpenHands-SDK-MLSys26|OpenHands-SDK]]、[[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]]、[[ADR-MLSys26|ADR]] 等）构成两个平行子领域。相比 hero demo 时代，这届更强调闭环可复现与生产安全。

**可审计 / 可信 ML 与异构硬件同步浮出水面**。[[Hawkeye-MLSys26|Hawkeye]]、[[ZK-APEX-MLSys26|ZK-APEX]]、[[GPU-CC-Security-MLSys26|GPU-CC-Security]]、[[DP-ZeRO-MLSys26|DP-ZeRO]] 共同构成「训练/推理过程可被第三方验证」方向；[[HipKittens-MLSys26|HipKittens]]、[[WAVE-MLSys26|WAVE]]、[[fabric-lib-MLSys26|fabric-lib]]、[[SakuraONE-MLSys26|SakuraONE]] 则表明社区不再把 H100 + NCCL + CUDA 当唯一默认。

**与往届的对比**：相比 MLSys 2025 的 79 篇初版综述，本届完整 proceedings 几乎翻倍。PagedAttention / vLLM 内部优化式论文减少，取而代之的是跨框架 IR（[[SpanQueries-MLSys26|SpanQueries]]）、替代 compile 路径（[[EventTensor-MLSys26|EventTensor]]、[[Flashlight-MLSys26|Flashlight]]）、容错 serving（[[GhostServe-MLSys26|GhostServe]]、[[RaidServe-MLSys26|RaidServe]]）与基础设施 drift 监测（[[DriftBench-MLSys26|DriftBench]]）——说明社区已把 vLLM/SGLang 当成基础设施而非研究目标。

## 论文分类

### LLM 推理服务与调度（17 篇）

- [[LayeredPrefill-MLSys26|LayeredPrefill]] — 把 prefill 调度轴从 token 换成 layer-group，消除 [[Chunked-Prefill]] 在 [[MoE]] 上的冗余 expert 重载，TTFT 降 70%
- [[Stream2LLM-MLSys26|Stream2LLM]] — 在 [[vLLM]] 上扩展 streaming prompt，LCP 缓存失效 + 成本感知抢占，RAG TTFT 降至 1/11
- [[HELIOS-MLSys26|HELIOS]] — multi-model 协同 + greedy 层加载，EE-LLM 吞吐 1.48×、batch size 15.14×
- [[LAPS-MLSys26|LAPS]] — prefill 阶段内部再按长度 disaggregate，隔离长/短 prefill，[[SGLang]] 对比降 30% 延迟
- [[BatchLLM-MLSys26|BatchLLM]] — 微软大批量 offline 推理，global prefix 树 + 内存中心 token batching，比 vLLM/SGLang 1.3-10.8×
- [[BOUTE-MLSys26|BOUTE]] — 多目标 Bayesian 优化联合选择异构模型和异构 GPU，cost 降 15-61%
- [[SuperInfer-MLSys26|SuperInfer]] — GH200 Superchip 上 OS-style rotary scheduler + DuplexKV 全双工 KV，SLO 达成率 +74.7%
- [[MorphServe-MLSys26|MorphServe]] — runtime 按负载切换层精度 + KV 弹性，SLO 违规降 92.45%
- [[OptiKit-MLSys26|OptiKit]] — eBay 端到端 LLM 优化框架，Ray actor + 压缩 + SLO 基准，吞吐 2.8×
- [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] — 数十万设计点系统评测 disaggregation，[[Disaggregation]] 对 prefill-heavy + >10B 模型收益最大
- [[ProfInfer-MLSys26|ProfInfer]] — eBPF uprobe 挂 llama.cpp 三层 + PMC 计数器，开销 <4%
- [[SpanQueries-MLSys26|SpanQueries]] — 声明式 span query IR 统一 RAG/agent/inference-scaling，492 行改动让 vLLM TTFT 降 10-20×
- [[BreakingTheIce-MLSys26|BreakingTheIce]] — 系统剖析 [[vLLM]] serverless 冷启动，量化模型加载/编译/KV 初始化各阶段瓶颈
- [[FaaScale-MLSys26|FaaScale]] — serverless LLM 快速弹性扩缩，RDMA 权重广播 + 分层冷启动，秒级 scale-out
- [[Meta-LLM-Deploy-MLSys26|Meta-LLM-Deploy]] — 系统探索 LLM 部署配置空间（并行/量化/disagg），给出生产可行 design point 地图
- [[Behdin-SemanticJobSearch-MLSys26|Behdin-SemanticJobSearch]] — 语义招聘搜索的 SLM 压缩 + prefill-only [[SGLang]] 服务栈，延迟与成本双优化
- [[TokenWeave-MLSys26|TokenWeave]] — 分布式推理中 RMSNorm+AllReduce 计算通信重叠，tensor parallel 吞吐提升

### RAG 与检索增强推理（5 篇）

- [[TeleRAG-MLSys26|TeleRAG]] — IVF 检索预取 + KV 复用协同优化 RAG 推理，降低 retrieval-to-generation 间隙
- [[ContextPilot-MLSys26|ContextPilot]] — 长上下文推理的 context reuse 调度，prefix 局部性感知减少重复 prefill
- [[Terminus-MLSys26|Terminus]] — 向量检索 rank-aware early termination，磁盘 I/O 降 40%+ 且 recall 无损
- [[LEANN-MLSys26|LEANN]] — 端侧向量索引不存 embedding，查询现场重算 + 两级 PQ+精确，188 GB→4 GB（50×）
- [[ApproxMLIR-MLSys26|ApproxMLIR]] — 面向 compound ML 系统的 accuracy-aware 编译器，RAG 等多阶段 pipeline 端到端近似优化

### KV Cache 与 Attention 优化（11 篇）

- [[FlexiCache-MLSys26|FlexiCache]] — KV head 时域稳定性分级处理，GPU 显存降 70%、吞吐 1.38-1.55×
- [[Kitty-MLSys26|Kitty]] — 2-bit [[KV-Cache]] + channel-wise 精度提升 + Triton dequant kernel，8× 内存、2.1-4.1× 吞吐
- [[MAC-Attention-MLSys26|MAC-Attention]] — 匹配 pre-RoPE 查询复用 attn summary，128K 下 KV 访问降 99%、attn 14.3×
- [[SkipKV-MLSys26|SkipKV]] — reasoning 模型的句级 KV eviction + adaptive steering，2× 压缩下准确率 +6.7%
- [[BLASST-MLSys26|BLASST]] — FlashAttention online softmax 运行时 skip 低贡献 block，prefill 1.62×、decode 1.48×
- [[IntAttention-MLSys26|IntAttention]] — IndexSoftmax 32-LUT 实现纯整数 attention，Arm CPU 比 FP16 快 3.7×
- [[FlashAttention-4-MLSys26|FlashAttention-4]] — Blackwell B200 上 2-CTA MMA + TMEM + 软件 exp，BF16 1613 TFLOPS/s，cuDNN 比 1.3×
- [[MTraining-MLSys26|MTraining]] — Context Parallelism 下动态稀疏注意力的 Striped 布局 + Hierarchical Ring，Qwen2.5-3B 上下文到 512K
- [[OPKV-MLSys26|OPKV]] — plugin-driven 可召回稀疏 KV 框架，PagedAttention 兼容的 recallable sparsity
- [[ScaleSearch-MLSys26|ScaleSearch]] — 搜索 block floating point scale 配置，NVFP4 attention/KV 精度-吞吐 Pareto 优化
- [[AttributionSparseActivation-MLSys26|AttributionSparseActivation]] — 基于 attribution 的运行时稀疏激活，LLM 推理按需跳过低贡献神经元

### Speculative Decoding 与新解码范式（9 篇）

- [[DAS-MLSys26|DAS]] — RL rollout 的 per-problem 滑动窗口 suffix tree drafter + long-tail budget 分配，rollout 延迟 -50%
- [[PRISM-MLSys26|PRISM]] — 按 draft step 拆分 draft model（类 MoE 条件计算），[[SGLang]] 吞吐 >2.6×
- [[SparseSpec-MLSys26|SparseSpec]] — self-speculation + PillarAttn 动态 sparse，从 verify 阶段白嫖 top-K，Qwen3 上 2.13×
- [[SpecDecodeBench-MLSys26|SpecDecodeBench]] — 首次生产级 [[vLLM]] 上系统评测，验证阶段开销主导、接受行为高度异质
- [[SpecDiff-2-MLSys26|SpecDiff-2]] — 离散扩散 drafter + streak-distillation + self-selection，5.5× 加速无损
- [[TiDAR-MLSys26|TiDAR]] — diffusion-AR 混合，单前向 diffusion drafting + AR verification，无损 4.71-5.91×
- [[CDLM-MLSys26|CDLM]] — block-wise causal mask + consistency 蒸馏把 diffusion LM 压成 block-causal，3.6-14.5× 降延迟
- [[ReSpec-MLSys26|ReSpec]] — RL 训练中优化 speculative decoding 的 drafter-verifier 对齐，rollout 吞吐提升
- [[DataflowIsAllYouNeed-MLSys26|DataflowIsAllYouNeed]] — SambaNova RDU 数据流 decode 架构，speculative + 流水线并行突破 AR 串行瓶颈

### MoE 训练与推理系统（6 篇）

- [[CRAFT-MLSys26|CRAFT]] — MoE expert replica 按层动态分配（MCKP DP），DeepSeek-R1/Kimi-K2 上比 EPLB 均匀复制 1.14-1.2×
- [[FarSkip-Collective-MLSys26|FarSkip-Collective]] — 改 skip 连接让下一 sub-block 用 partial activation 启动，all-to-all 与计算重叠，FCSD 蒸馏 <2.5% 精度差
- [[FP8FlowMoE-MLSys26|FP8FlowMoE]] — scaling-aware transpose 算子消除重复 cast，DeepSeek-V3 训练 +21%、单卡显存 -16.5 GB
- [[MoEBlaze-MLSys26|MoEBlaze]] — MoE token 路由无 per-expert buffer，on-the-fly gather/scatter 融合 + SwiGLU checkpoint 协同，4× 加速
- [[EventTensor-MLSys26|EventTensor]] — 把 GPU 同步事件抽象成一等 tensor，symbolic shape + 数据依赖索引，ETC 编译器 MoE 1.23×
- [[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] — 系统量化 MoE serving 的 expert/TP/EP 组合税，揭示 hidden communication 与内存开销

### 分布式训练、RL 与弹性并行（17 篇）

- [[AXLearn-MLSys26|AXLearn]] — Apple JAX/XLA 模块化训练框架，RoPE/MoE 10 行代码配置，H100/TPU v5p/Trainium2 全兼容
- [[DistCA-MLSys26|DistCA]] — Core Attention Disaggregation，无参数 softmax(QK)V 剥离到独立 attention server 池，512 H200 / 512K context 上 +35%
- [[HetRL-MLSys26|HetRL]] — 跨地区异构 GPU 集群跑 PPO/GRPO，5-level 搜索 + 遗传算法，比 verl/OpenRLHF 平均 3.17×
- [[HexiScale-MLSys26|HexiScale]] — 全 asymmetric 的 DP/TP/PP 三维并行 + 分层 graph partition，异构集群 MFU 追平同构高端
- [[DreamDDP-MLSys26|DreamDDP]] — Local SGD 整模型同步拆成 layer-wise partial sync，32-GPU 低带宽下 1.49-3.91×
- [[DP-ZeRO-MLSys26|DP-ZeRO]] — 把 Book-Keeping per-sample 梯度裁剪嫁接进 DeepSpeed/FSDP ZeRO-1/2/3，首次让 DP 训练达 GPT-100B / ViT-10B 规模
- [[NEST-MLSys26|NEST]] — level-wise 网络抽象 + memory modeling 的 DP 解 7 种并行联合优化，比 Alpa/TopoOpt/Mist 2.43×
- [[ProTrain-MLSys26|ProTrain]] — 把 ZeRO + tensor swap + gradient checkpoint 统一到自动搜索，比 DeepSpeed/Colossal-AI/FSDP 1.43-2.71×
- [[veScale-FSDP-MLSys26|veScale-FSDP]] — ByteDance 新 FSDP backend，RaggedShard + Distributed Buffer，生产 10K+ GPU，吞吐 +5-66%
- [[BOOST-MLSys26|BOOST]] — 低秩瓶颈架构专用 TP（在窄瓶颈做 collective），vs. full-rank 1.46-1.91×、vs. vanilla TP 1.87-2.27×
- [[FlexTrain-MLSys26|FlexTrain]] — 弹性 hybrid-parallel 训练，pipeline stage 动态伸缩 + 资源感知重调度
- [[FCP-MLSys26|FCP]] — foundation model 的 scalable context parallelism，长上下文 load balancing + ring attention 协同
- [[Guard-MLSys26|Guard]] — 分布式训练 straggler 检测 + grey node 健康管理，MoE 集群 goodput 提升
- [[Quirk-Sparing-MLSys26|Quirk-Sparing]] — 大集群 LLM 训练的 sparing 策略，最小化可靠性投入对 goodput 的影响
- [[Zorse-MLSys26|Zorse]] — 异构 GPU 集群 LLM 训练效率优化，pipeline + ZeRO 联合调度
- [[FreeScale-MLSys26|FreeScale]] — 序列推荐模型的分布式训练 load balancing，embedding + RDMA 通信优化
- [[PROMPTS-MLSys26|PROMPTS]] — 多 agent 规划自动调优 LLM 训练 sharding，TPU 集群吞吐提升

### 推理容错、能效与多模态 Serving（8 篇）

- [[GhostServe-MLSys26|GhostServe]] — 轻量级 serving 侧 checkpoint，erasure-coded KV shadow 实现透明容错
- [[RaidServe-MLSys26|RaidServe]] — 高吞吐 resilient serving，tensor parallel + KV 冗余，故障下吞吐保持
- [[SHIP-MLSys26|SHIP]] — SRAM-based huge inference pipeline（Groq 风格），超低延迟 LLM serving
- [[BEAM-MLSys26|BEAM]] — LLM serving 联合资源-功耗优化，DVFS + SLO-aware 调度
- [[TriInfer-MLSys26|TriInfer]] — 多模态大模型 hybrid disaggregated 调度，prefill/decode 与模态感知路由
- [[FlashAgents-MLSys26|FlashAgents]] — 多 agent LLM 系统的 streaming prefill 重叠加速
- [[AgenticCache-MLSys26|AgenticCache]] — embodied agent 的 cache-driven 异步 planning，推理与规划并行
- [[LocalityAwareBeamScheduling-MLSys26|LocalityAwareBeamScheduling]] — test-time compute 的 locality-aware beam 调度，consumer GPU KV offload 优化

### GPU Kernel、编译器与 DSL（10 篇）

- [[HipKittens-MLSys26|HipKittens]] — ThunderKittens 移植到 AMD CDNA3/4，8-wave ping-pong + chiplet swizzle，追平 AITER 手写汇编
- [[ParallelKittens-MLSys26|ParallelKittens]] — 多 GPU kernel 的 8 个 primitive + 统一模板，<50 行 device 代码匹配 Flux/Comet/CUTLASS
- [[Flashlight-MLSys26|Flashlight]] — TorchInductor 三类图重写，`torch.compile` 自动生成 FlashAttention 风格 Triton，对齐 FlexAttention
- [[Collective-NoC-MLSys26|Collective-NoC]] — ML 加速器的 collective-capable NoC + Direct Compute Access，GEMM 3.8×
- [[PyLO-MLSys26|PyLO]] — 学习型优化器 VeLO 从 JAX 移植到 PyTorch + 自定义 CUDA kernel，ViT 优化器 4× 提速
- [[WAVE-MLSys26|WAVE]] — 符号化 Python DSL + 编译器，AMD GPU 上高性能 attention/GEMM kernel 生成
- [[CATWILD-MLSys26|CATWILD]] — TPU fleet 级 XLA compiler autotuning，生产 workload 端到端加速
- [[DynaFlow-MLSys26|DynaFlow]] — torch.compile 透明 intra-device 算子调度重叠，融合与并行自动编排
- [[XPROF-MLSys26|XPROF]] — OpenXLA 开放可扩展 profiler，分布式训练 roofline + traceviewer 集成
- [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] — AI 生成 kernel 闭环框架，抗 reward-hacking + 动态 `apply()` 注入 vLLM/SGLang

### AI4AI：LLM 生成 Kernel / HDL / 数据（7 篇）

- [[AccelOpt-MLSys26|AccelOpt]] — AWS Trainium NKI kernel 优化的 LLM beam search + optimization memory，gpt-oss + Qwen3-Coder 匹配 Claude 4 但成本 26× 低
- [[LLaMEA-KernelTuner-MLSys26|LLaMEA-KernelTuner]] — LLM + 进化算法生成 auto-tuning 优化器，比人工 baseline 高 72.4%
- [[PIKE-MLSys26|PIKE]] — multi-agent kernel 优化的 exploit-heavy + error-fixing + 粗粒度 step，KernelBench H100 2.88×
- [[TritorX-MLSys26|TritorX]] — Meta MTIA 的 Triton ATen kernel 自动生成，484 算子、20K+ OpInfo 通过率
- [[VeriMoA-MLSys26|VeriMoA]] — spec-to-HDL 的 Mixture-of-Agents，quality-guided global cache，VerilogEval 2.0 Pass@1 +15-30%
- [[Matrix-MLSys26|Matrix]] — Meta FAIR 的 P2P message-driven multi-agent 合成数据，31 节点 248 GPU 上 12,400 并发，6.8× Coral
- [[RocketPPA-MLSys26|RocketPPA]] — 统一 LLM 做 EDA 的 power/performance/area 优化，Verilog 生成与评估闭环

### 量化、压缩与边缘/端侧推理（7 篇）

- [[CAGE-MLSys26|CAGE]] — Pareto-optimality 推导的 curvature-aware STE 校正，3-bit W+A 预训练匹配 4-bit QuEST
- [[MixLLM-MLSys26|MixLLM]] — 全局显著性给 ~10% 输出通道 8-bit、其余 4-bit，Llama 3.1 70B PPL 退化从 0.5 降到 <0.2
- [[HyperTinyPW-MLSys26|HyperTinyPW]] — 共享 micro-MLP 从 latent code 合成 PW 卷积权重，TinyML 6.31× 压缩
- [[CORE-MLSys26|CORE]] — 移动端 LLM 统一 DVFS 调度，llama.cpp 能耗-延迟联合优化
- [[ExecuTorch-MLSys26|ExecuTorch]] — PyTorch 统一端侧推理方案，backend delegation + 量化，跨 mobile/embedded 部署
- [[Shannonic-MLSys26|Shannonic]] — ML workload 的 entropy-optimal 压缩，联邦/推理场景通信与存储双降
- [[PipelinedSharding-MLSys26|PipelinedSharding]] — 客户端 VRAM 受限的 xLM 推理，CPU-GPU pipeline offload 支持 VLM/MoE

### Agent 系统、记忆与安全（8 篇）

- [[OpenHands-SDK-MLSys26|OpenHands-SDK]] — OpenHands 重构为模块化 SDK，采用 event-sourced state、opt-in sandbox 与 100+ LLM 路由，达到 SWE-Bench Verified SOTA
- [[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] — Dynamic Wavelet Matrix agent 记忆，压缩域 Hamming-ball 搜索，检索 31× 快、token 14× 少
- [[OSWorld-Human-MLSys26|OSWorld-Human]] — computer-use agent 延迟专项研究，planning/reflection 占总延迟 75-94%，369 任务人类金轨迹
- [[PARROT-MLSys26|PARROT]] — LLM sycophancy 鲁棒 benchmark，双盲对比 + 八状态分类，22 LLM 下 follow rate 4%-94% 20× 差异
- [[RLVR-LowData-MLSys26|RLVR-LowData]] — 程序生成 reasoning 数据集研究 RLVR 在 low data 下表现，mixed-difficulty 带 5× sample efficiency
- [[ADR-MLSys26|ADR]] — 企业 agentic AI 安全检测，解析 Cursor/Cline 本地缓存重建 MCP tool call 攻击面
- [[Tag2Graph-MLSys26|Tag2Graph]] — ontology-guided 对话 RAG 长期 agent 记忆，个性化检索图结构
- [[BOA-MLSys26|BOA]] — 原则性 LLM jailbreak 安全测试，搜索式 red-team 发现系统性漏洞

### 扩散、视频与多模态生成（4 篇）

- [[StreamDiffusionV2-MLSys26|StreamDiffusionV2]] — 视频扩散直播系统，SLO-aware batching + sink-token rolling KV + motion-aware noise，4× H100 达 58.28 FPS
- [[Reparo-MLSys26|Reparo]] — VQGAN + 时空 ViT 生成式视频会议编解码，每帧独立，50-75% 丢包 PSNR 比 VP9+Tambur 高 11-16 dB
- [[db-SP-MLSys26|db-SP]] — 视觉 DiT 的 dual-balanced（head + block）sequence parallelism，Wan2.1-T2V-14B 端到端 1.25×
- [[SwiftGS-MLSys26|SwiftGS]] — 3D Gaussian Splatting 算法-系统协同优化，CUDA kernel + 渲染管线加速

### 联邦学习、隐私与可审计 ML（9 篇）

- [[PLayer-FL-MLSys26|PLayer-FL]] — 借 model pruning 一阶重要性定义 federation sensitivity，第一个 epoch 决定哪些层 federate
- [[ProToken-MLSys26|ProToken]] — 联邦 LLM 的 token 级 client 归因，梯度加权 activation 内积，4×4 配置 98.62% 准确率
- [[FLoRIST-MLSys26|FLoRIST]] — stacked [[LoRA]] adapter 的 SVD + 能量阈值截断，vs. FLoRA 58×、vs. full FT 227× 通信
- [[Privatar-MLSys26|Privatar]] — 多用户 VR 把 avatar 重建 secure offload 到 PC，block-DCT 频域分割 + PAC Privacy，2.37× 并发
- [[ZK-APEX-MLSys26|ZK-APEX]] — 边缘个性化模型的 approximate unlearning ZK 证明，Halo2 ~2h 比重训验证快 10^7×
- [[GPU-CC-Security-MLSys26|GPU-CC-Security]] — 首个 NVIDIA Hopper GPU Confidential Computing 系统安全分析，上报多个问题
- [[DISAGG-MLSys26|DISAGG]] — 联邦学习分布式 secure aggregator，sublinear 通信的高效隐私聚合
- [[G-HEMP-MLSys26|G-HEMP]] — 多 GPU 大规模 GCN 同态加密推理，CKKS 并行化突破内存墙
- [[Hawkeye-MLSys26|Hawkeye]] — 逆向 Tensor Core rounding/subnormal/累加顺序，CPU bit-exact 复现 FP16/BF16/FP8 16×16 MMA

### Benchmark、仿真与集群经验（8 篇）

- [[Chakra-MLSys26|Chakra]] — Meta+GATech+HPE 的分布式 ML 执行图 schema + 生成式合成 trace，obfuscated trace 给 HW 厂商 co-design
- [[SakuraONE-MLSys26|SakuraONE]] — 800-GPU H100 AI HPC 集群经验，TOP500 #49，Top-100 中唯一 800 GbE + SONiC 开源网络栈
- [[DriftBench-MLSys26|DriftBench]] — LLM serving 基础设施 drift 测量与预测，量化/配置变更的安全影响
- [[Charon-MLSys26|Charon]] — 统一细粒度 LLM 训练/推理模拟器，operator-level design space exploration
- [[SONAR-MLSys26|SONAR]] — 去中心化学习拓扑与协作 benchmark，P2P 联邦场景系统评测
- [[Acela-MLSys26|Acela]] — 数据中心固件升级的 cost-aware 持续时间预测，quantile GBDT 偏 mild overprediction
- [[MPG-MLSys26|MPG]] — Google TPU fleet 效率优化，goodput 驱动的系统级调度与 profiling
- [[AIRS-MLSys26|AIRS]] — 资源受限环境（TPU）live inference 扩展，search quality 感知的 batching + archive 缓存

### 专业领域与非 LLM 系统（9 篇）

- [[EarthSight-MLSys26|EarthSight]] — LEO 卫星图像地面-轨道联合调度，多任务共享 backbone + 轨道 utility-driven filter，P90 延迟 51→21 min
- [[Spira-MLSys26|Spira]] — 首个 voxel-property-aware 稀疏卷积引擎，vs. TorchSparse++/Minuet 平均 1.68×
- [[CSLE-MLSys26|CSLE]] — Cyber Security Learning Environment，Docker Swarm 数字孪生 + MDP 仿真，15 套 twin / 34 RL 算法
- [[fabric-lib-MLSys26|fabric-lib]] — 跨 ConnectX-7 + AWS EFA 的统一 RDMA 点对点库，IMMCOUNTER 完成通知，trillion-param RL 权重 1.3s
- [[OutOfCoreUMAP-MLSys26|OutOfCoreUMAP]] — GPU 上 massive-scale out-of-core UMAP，kNN 图构建突破显存限制
- [[GriNNder-MLSys26|GriNNder]] — 全图 GNN 训练的存储卸载，NVMe + PyG 突破 GPU 内存容量墙
- [[Catur-MLSys26|Catur]] — 云规模 VM NUMA placement 强化学习，学习 norm 后泛化到新集群拓扑
- [[Gohil-UncertaintyAware-MLSys26|Gohil-UncertaintyAware]] — ML-for-systems 的不确定性估计，OOD 检测 + graceful degradation 保障生产可靠性
- [[QBL-MLSys26|QBL]] — 对抗性多臂老虎机数据库索引选择，sublinear regret 实用调优

## 研究趋势

**1. [[Chunked-Prefill]] 的「后时代」：调度轴从 token 重构为 layer / length / locality / modality**。2024 Sarathi-Serve 定下的 chunked prefill 范式正被多角度挑战。[[LayeredPrefill-MLSys26|LayeredPrefill]] 把调度轴换成 layer-group 消除 MoE expert 重载；[[LAPS-MLSys26|LAPS]] 在 prefill 内部再按长度 disaggregate；[[SpanQueries-MLSys26|SpanQueries]] 把 chat/RAG/agent 统一到声明式表达式树；[[TriInfer-MLSys26|TriInfer]] 将 disagg 扩展到多模态 MLLM；[[Stream2LLM-MLSys26|Stream2LLM]] 处理 streaming prompt 场景。共同方向：chunk 只是工具，真正需要调度的是「模型层」「请求类型」「缓存局部性」「模态」这些 first-class 概念。

**2. MoE 从 "附带支持" 升级到 "一等系统问题"**。6 篇专攻 MoE 的论文外加 MoE-aware 调度与 [[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] 的定量分析表明 MoE 系统已成独立议题。[[FarSkip-Collective-MLSys26|FarSkip-Collective]] 改架构让 all-to-all 与计算重叠，[[FP8FlowMoE-MLSys26|FP8FlowMoE]] 从 FP8 cast 链路切入，[[MoEBlaze-MLSys26|MoEBlaze]] 消掉 per-expert buffer，[[EventTensor-MLSys26|EventTensor]] 提供 megakernel 编译路径，[[CRAFT-MLSys26|CRAFT]] 解决 expert replica 动态分配。

**3. Speculative decoding 走出 EAGLE 式 draft model 独霸格局，且开始接受 reality check**。9 篇 speculative 工作呈现明显分化：[[SpecDiff-2-MLSys26|SpecDiff-2]]、[[TiDAR-MLSys26|TiDAR]]、[[CDLM-MLSys26|CDLM]] 用扩散模型做 drafter；[[DAS-MLSys26|DAS]]、[[SparseSpec-MLSys26|SparseSpec]] 走 training-free 路线；[[PRISM-MLSys26|PRISM]] 把 draft model 按 step 切成 MoE 式条件计算；[[ReSpec-MLSys26|ReSpec]] 把 speculative 推进到 RL 训练环。[[SpecDecodeBench-MLSys26|SpecDecodeBench]] 直接把标题写成 "Performance or Illusion?"——社区已对 single-number 加速报道失去信任。

**4. 分布式训练从「同构大集群」扩展到异构、弹性、长上下文**。17 篇训练论文覆盖 ZeRO/FSDP 变体（[[veScale-FSDP-MLSys26|veScale-FSDP]]、[[DP-ZeRO-MLSys26|DP-ZeRO]]）、异构调度（[[HexiScale-MLSys26|HexiScale]]、[[HetRL-MLSys26|HetRL]]、[[Zorse-MLSys26|Zorse]]）、attention disagg（[[DistCA-MLSys26|DistCA]]）、context parallel（[[FCP-MLSys26|FCP]]、[[MTraining-MLSys26|MTraining]]）与弹性 pipeline（[[FlexTrain-MLSys26|FlexTrain]]）。训练系统研究正与 RL rollout（[[HetRL-MLSys26|HetRL]]、[[DAS-MLSys26|DAS]]）和 serving 需求（[[DistCA-MLSys26|DistCA]]）双向渗透。

**5. AI4AI 成建制进入 MLSys，且 benchmark 成为入场券**。7+1 篇 LLM agent 生成代码的工作外加 [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] 构成独立子领域。与前一代 hero demo 不同，这届明显强调：开源 LLM 足够（gpt-oss、Qwen3-Coder 匹配 Claude）、必须提供 benchmark（否则无法证明 generalization）、error-fixing subagent 比大模型本身更重要（[[PIKE-MLSys26|PIKE]]、[[AccelOpt-MLSys26|AccelOpt]]）。

**6. Agent 系统从 demo 走向 SDK + 记忆 + 安全三角**。[[OpenHands-SDK-MLSys26|OpenHands-SDK]] 把 agent 框架产品化；[[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]]、[[Tag2Graph-MLSys26|Tag2Graph]] 给出具体记忆数据结构；[[OSWorld-Human-MLSys26|OSWorld-Human]] 量化 planning/reflection 延迟瓶颈；[[ADR-MLSys26|ADR]]、[[BOA-MLSys26|BOA]] 分别从企业安全与 red-team 角度切入。Agent 系统论文数量（8 篇）已与 speculative decoding（9 篇）接近。

**7. 可审计 / 可信 ML 从边缘变主流议题**。[[Hawkeye-MLSys26|Hawkeye]]（CPU 复现 Tensor Core）、[[ZK-APEX-MLSys26|ZK-APEX]]（unlearning ZK 证明）、[[GPU-CC-Security-MLSys26|GPU-CC-Security]]（Hopper CC 安全分析）、[[DriftBench-MLSys26|DriftBench]]（serving 基础设施 drift）共 9 篇联邦/隐私/可审计集群。这些论文共同指向：AI 部署开始进入被监管、被审计、被挑战的环境。

**8. 异构硬件 / 非 NVIDIA 开始有一席之地**。[[HipKittens-MLSys26|HipKittens]] 宣称 "消灭 CUDA moat"；[[WAVE-MLSys26|WAVE]] 面向 AMD；[[fabric-lib-MLSys26|fabric-lib]] 跨 ConnectX-7 + AWS EFA；[[AccelOpt-MLSys26|AccelOpt]] 在 AWS Trainium；[[TritorX-MLSys26|TritorX]] 在 Meta MTIA；[[AXLearn-MLSys26|AXLearn]] 声称 H100/TPU v5p/Trainium2 全等权；[[SakuraONE-MLSys26|SakuraONE]] 报告 800 GbE + SONiC 开源网络栈取代 InfiniBand。

## 共同观察

**1. LLM 推理瓶颈已从「单算子 FLOPs」迁移到「编排税 + 内存税 + 同步税」**。多篇论文独立量化三类开销：[[EventTensor-MLSys26|EventTensor]] 测得 decode 每 kernel launch 5–10 µs、细粒度 op 边界同步吃掉 inter-kernel overlap；[[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] 报告 MoE decode 相对 FLOP 对齐稠密基线常见 **2–3×** serving tax；[[BreakingTheIce-MLSys26|BreakingTheIce]] / [[FaaScale-MLSys26|FaaScale]] 把冷启动拆成权重加载 / 编译 / KV 初始化各阶段。适用边界：大 batch prefill-heavy datacenter 场景下 compute 仍可能主导（[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] 的 prefill pool 饱和时），但 agent / coding / 低 batch 交互负载下编排与同步占比最高——[[OSWorld-Human-MLSys26|OSWorld-Human]] 甚至发现 planning/reflection 占端到端延迟 75–94%，系统优化需上移到 workflow 层。

**2. [[vLLM]] / [[SGLang]] 已被当作基础设施而非研究对象，改动集中在 scheduler / IR / backend 插件层**。17 篇 serving 论文几乎全部 fork 现有引擎：[[SpanQueries-MLSys26|SpanQueries]] 492 行 Python、[[Stream2LLM-MLSys26|Stream2LLM]] 扩 streaming prompt、[[LAPS-MLSys26|LAPS]] / [[LayeredPrefill-MLSys26|LayeredPrefill]] 改 prefill 调度轴、[[ProfInfer-MLSys26|ProfInfer]] 用 eBPF 挂 llama.cpp。[[DriftBench-MLSys26|DriftBench]] 进一步把「量化 / 并行 / 路由配置 drift」当作生产风险监测对象。共识成立前提是社区继续以 PagedAttention + continuous batching 为默认栈；若下一代 engine 推翻 block 粒度或 prefix-only 缓存语义，[[SpanQueries-MLSys26|SpanQueries]] / [[ContextPilot-MLSys26|ContextPilot]] 类工作需重做。

**3. 生产 workload 异质性（RAG / agent / reasoning / multi-model）打破了「线性 chat history + prefix cache」默认假设**。[[SpanQueries-MLSys26|SpanQueries]] 指出 RAG 第二次检索 prefix hit 仅 33%；[[TeleRAG-MLSys26|TeleRAG]] / [[ContextPilot-MLSys26|ContextPilot]] 分别优化 retrieval-to-generation 间隙与 context reuse；[[HELIOS-MLSys26|HELIOS]] / [[BOUTE-MLSys26|BOUTE]] 处理 multi-model 路由；[[SkipKV-MLSys26|SkipKV]] / [[MAC-Attention-MLSys26|MAC-Attention]] 面向 reasoning 长 CoT。观察在 fragment/candidate 跨请求稳定、且 KV working set 小于 GPU 容量时最稳；每次检索全新文档或 inner generate temperature=0 单候选时，commutative / span 优化收益趋零（[[SpanQueries-MLSys26|SpanQueries]] 自述）。

**4. [[MoE]] 已成独立系统议题轴，且 Kimi-K2 / DeepSeek-V3 级开源模型是默认评测基线**。6 篇 MoE 专文 + MoE-aware 调度（[[CRAFT-MLSys26|CRAFT]]、[[LayeredPrefill-MLSys26|LayeredPrefill]]）共享观察：expert routing 引入 data-dependent 依赖、all-to-all 与 padding/straggler 抬高 tax、EP/TP 组合空间远大于稠密模型。[[FP8FlowMoE-MLSys26|FP8FlowMoE]] / [[FarSkip-Collective-MLSys26|FarSkip-Collective]] 分别从 cast 链路与架构改 skip 连接切入。适用边界：极小 batch 单请求 decode tax 可低至 ~1.05×（[[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] Mixtral），不能外推到所有 serving 配置。

**5. 分布式训练研究同步拥抱异构、弹性与 RL rollout，且 straggler / goodput 与 serving SLO 开始互相渗透**。[[HetRL-MLSys26|HetRL]] / [[HexiScale-MLSys26|HexiScale]] / [[Zorse-MLSys26|Zorse]] 处理跨地区异构 GPU；[[FlexTrain-MLSys26|FlexTrain]] / [[Guard-MLSys26|Guard]] 做弹性 pipeline 与 grey node 管理；[[DistCA-MLSys26|DistCA]] 把 attention 剥离成独立 server 池；[[DAS-MLSys26|DAS]] / [[ReSpec-MLSys26|ReSpec]] 把 speculative decoding 推进 RL 环。观察在 ≥128 GPU 预训练 / RL 集群上最稳；单机微调或 torch.compile 路径下 [[DP-ZeRO-MLSys26|DP-ZeRO]] 类框架收益与 paper 假设可能偏离。

**6. 可审计 / 可信 ML 从合规边缘进入主会议集群**。9 篇联邦 / 隐私 / 可审计论文共享前提：部署环境将被第三方验证、配置 drift 可被挑战、GPU 执行需可复现。[[Hawkeye-MLSys26|Hawkeye]] 逆向 Tensor Core 做 bit-exact CPU 复现；[[ZK-APEX-MLSys26|ZK-APEX]] 给 unlearning 做 ZK 证明；[[GPU-CC-Security-MLSys26|GPU-CC-Security]] 剖析 Hopper CC 攻击面；[[DriftBench-MLSys26|DriftBench]] 监测 serving 基础设施 drift。共识在「需要向监管者证明行为」的 edge / enterprise 场景成立；纯内部 benchmark 竞赛仍可能忽略这些约束。

## 互相冲突的假设

**1. Prefill/decode [[Disaggregation]] 是否普适？** [[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] 在数十万设计点上结论：prefill-heavy（ISL ≫ OSL）+ >10B 模型收益最大，decode-heavy 且 latency 不紧时 co-located 往往更好，固定 ctx:gen GPU 比会在 Pareto 一侧极好另一侧崩溃。相对地，[[LAPS-MLSys26|LAPS]] / [[DistCA-MLSys26|DistCA]] / [[TriInfer-MLSys26|TriInfer]] 把 disagg 当作解决长/短 prefill 隔离、attention 池化、多模态路由的默认工具。**仲裁测量**：在同一 trace 上同时扫 ISL/OSL 分布、FTL/TTL SLA、是否 prefix cache / speculative，对比 disagg vs [[Chunked-Prefill]] piggyback 的 Pareto 面积——尤其 MLA 模型 chunk 重算 overhead（[[NVIDIA-Disagg-Study-MLSys26|NVIDIA-Disagg-Study]] 观察 5）可能逆转结论。

**2. Serving 优化应下沉到 kernel/megakernel 还是留在 scheduler/IR 层？** [[EventTensor-MLSys26|EventTensor]] 假设低 batch decode 的 launch + 边界同步是主瓶颈，需 compiler-first megakernel（MoE 1.23×、warmup 3.5×）。[[SpanQueries-MLSys26|SpanQueries]] 假设同类瓶颈在 cache locality 与 attention haystack 长度，492 行 scheduler 改动即可 TTFT 10–20×，无需重写 GEMM。**仲裁测量**：在 batch 1–32、seq 4K–128K、MoE vs dense 矩阵上分解 TTFT 为 launch / KV miss / attention FLOPs / collective，判断哪项占 >50%。

**3. [[Speculative-Decoding]] 端到端加速是否接近论文宣称的 2–5×？** [[TiDAR-MLSys26|TiDAR]] / [[SpecDiff-2-MLSys26|SpecDiff-2]] / [[PRISM-MLSys26|PRISM]] 报告 4–5× 级无损加速；[[SpecDecodeBench-MLSys26|SpecDecodeBench]] 在生产 [[vLLM]] 上显示 batch 1→128 时 EAGLE 从 1.73× 跌至 1.21×，verification 主导且 draft-model KV 可让 per-token 内存 **1.77×**。**仲裁测量**：固定生产 batch 分布（非实验室 bs=1）、报告 p50/p99 TPOT、并分解 draft/verify/reject 时间；reasoning 模型需单独 trace（[[SpecDecodeBench-MLSys26|SpecDecodeBench]] case study 显示 acceptance 高度位置异质）。

**4. [[KV-Cache]] 压缩 / eviction 能否「免费」换吞吐？** [[Kitty-MLSys26|Kitty]]（2-bit KV + 2.1–4.1× 吞吐）、[[FlexiCache-MLSys26|FlexiCache]]（显存 -70%）、[[SkipKV-MLSys26|SkipKV]]（2× 压缩下准确率 +6.7%）假设 head/channel/句级稳定性允许激进压缩；[[MAC-Attention-MLSys26|MAC-Attention]] / [[BLASST-MLSys26|BLASST]] 走 runtime skip 而非存储压缩。相对地 [[DriftBench-MLSys26|DriftBench]] 警告量化与配置 drift 可 silently 改变行为。**仲裁测量**：同一长上下文 QA / reasoning / code 任务上对齐 PPL、task accuracy、tail latency 三指标，而非只报平均 TPOT。

**5. MoE routing skew 帮还是害？** [[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] 观察 skew routing 可减少激活 expert、反直觉加速；[[CRAFT-MLSys26|CRAFT]] / [[MoEBlaze-MLSys26|MoEBlaze]] 假设 skew 带来 padding/straggler 必须靠 replica 动态分配或无 buffer gather/scatter 消除；[[FarSkip-Collective-MLSys26|FarSkip-Collective]] 则改架构让 all-to-all 与计算重叠。**仲裁测量**：在真实 trace（非均匀 synthetic token 分布）上同时测 EP AllToAll 时间、active expert 数、P99 step latency，分离「带宽节省」与「straggler 惩罚」两项。

**6. AI4AI 自动 kernel 生成是否已可替代人类专家？** [[AccelOpt-MLSys26|AccelOpt]] / [[PIKE-MLSys26|PIKE]] / [[LLaMEA-KernelTuner-MLSys26|LLaMEA-KernelTuner]] 报告匹配或超越人工 baseline；[[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] 强调 reward hacking 与动态 `apply()` 注入才是闭环关键；[[EventTensor-MLSys26|EventTensor]] 承认 compiler-generated GEMM tile 仍不如 cuBLAS。**仲裁测量**：在 FlashInfer-Bench / KernelBench 上报告 pass@k、% of roofline、跨硬件迁移成功率，而非单次 best speedup。

**7. Agent 系统瓶颈在 serving 还是在 planning/memory？** [[MorphServe-MLSys26|MorphServe]] / [[SuperInfer-MLSys26|SuperInfer]] / [[OptiKit-MLSys26|OptiKit]] 假设 GPU serving 调度与 KV 是 SLO 主因；[[OSWorld-Human-MLSys26|OSWorld-Human]] 测得 planning/reflection 占 75–94% 延迟；[[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] / [[AgenticCache-MLSys26|AgenticCache]] 假设异步 planning + 记忆结构才是突破口。**仲裁测量**：端到端 agent trace 上做 latency waterfall，区分 LLM call 内 TTFT/TPOT vs 工具 / 规划 / 记忆检索；高 fan-out nested generation 场景下 [[SpanQueries-MLSys26|SpanQueries]] 与 [[FlashAgents-MLSys26|FlashAgents]] 结论可能同时成立但作用于不同段。

## 值得关注的方向

### 1. Span Query 风格的 declarative serving IR 研究

**为什么小团队能做**：[[SpanQueries-MLSys26|SpanQueries]] 证明 492 行改动就能让 2B 模型准确率超过 stock 8B——核心难度不在写代码，而在设计声明式语义。适合 1-2 人深挖数月。

**指向空白的论文**：[[SpanQueries-MLSys26|SpanQueries]] 只覆盖了 chat / RAG / inference-scaling / agent 四个场景；[[Stream2LLM-MLSys26|Stream2LLM]] 的 streaming prompt 语义没进 IR；[[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] 的 trace schema 是命令式的；[[ApproxMLIR-MLSys26|ApproxMLIR]] 面向 compound pipeline 但未统一 serving API。

**Open problems**：能否把 agent 的 tool-calling 循环、speculative decoding 的 acceptance 逻辑也纳入 span query IR？在 [[MTraining-MLSys26|MTraining]] 这类长上下文训练场景里 span query 能否表达 context parallelism 的 locality？

### 2. Speculative decoding 的 reality-check / benchmark 生产力

**为什么小团队能做**：[[SpecDecodeBench-MLSys26|SpecDecodeBench]] 的核心贡献不是新算法而是「对生产环境的严格测量」——单张 H100 或 2-4 张就能跑，主要工作是实验设计和数据收集。

**指向空白的论文**：[[SpecDecodeBench-MLSys26|SpecDecodeBench]] 暴露了 position / request / dataset 三层异质性但只给出粗粒度分析；[[DAS-MLSys26|DAS]] 专门针对 RL rollout 的长尾；[[SparseSpec-MLSys26|SparseSpec]] 与 [[TiDAR-MLSys26|TiDAR]] 走不同技术路线但缺乏对比；[[ReSpec-MLSys26|ReSpec]] 把 speculative 推进到训练环但缺乏 serving 端到端数据。

**Open problems**：在 reasoning 模型（o1 / R1 风格长 CoT）上 speculative 的 acceptance 如何演化？long-context（>64K）下 draft 模型该不该共享 KV？扩散 drafter（[[SpecDiff-2-MLSys26|SpecDiff-2]] / [[TiDAR-MLSys26|TiDAR]]）在真实 vLLM 上的端到端开销如何？

### 3. Agent memory 的 benchmark 与系统化度量

**为什么小团队能做**：[[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] 用单机就跑完全部 benchmark（LoCoMo / LongMemEval）；[[OSWorld-Human-MLSys26|OSWorld-Human]] 的人类金轨迹标注是劳动密集而非算力密集。

**指向空白的论文**：[[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] 的 Dynamic Wavelet Matrix 给了一个具体内存数据结构，但没有与 vector DB / KV agent state / knowledge graph 的系统对比；[[Tag2Graph-MLSys26|Tag2Graph]] 的 ontology-guided 图记忆缺乏 serving 延迟分析；[[OSWorld-Human-MLSys26|OSWorld-Human]] 发现 planning/reflection 占 75-94% 延迟但没给出 agent 内部 KV 复用的系统方案。

**Open problems**：agent workflow 里「trajectory cache」的正确抽象是什么（[[KV-Cache]] 的 agent 版本）？跨 agent session 的 long-term memory 是否应该像 [[LEANN-MLSys26|LEANN]] 那样不存而现算？[[FlashAgents-MLSys26|FlashAgents]] 的 streaming prefill 能否与 [[AgenticCache-MLSys26|AgenticCache]] 的异步 planning 统一？

### 4. 可审计 ML 的轻量级工具链

**为什么小团队能做**：[[Hawkeye-MLSys26|Hawkeye]] 全部用公开 PTX benchmark；[[ZK-APEX-MLSys26|ZK-APEX]] 的 Halo2 proof 在单机 <0.7 GB 内存；[[DriftBench-MLSys26|DriftBench]] 的 drift 监测可在现有 serving 栈上叠加。

**指向空白的论文**：[[Hawkeye-MLSys26|Hawkeye]] 覆盖 FP16/BF16/FP8 16×16 MMA 但没覆盖 block-scaled fp4（Blackwell）、非方阵 MMA、Transformer Engine 的在线 rescaling；[[ZK-APEX-MLSys26|ZK-APEX]] 只做 unlearning，没做训练过程证明；[[DriftBench-MLSys26|DriftBench]] 聚焦量化 drift 但未覆盖 MoE routing 变化。

**Open problems**：能否给 [[MoE]] routing 做 ZK 证明（expert 选择不作弊）？能否在 confidential computing GPU 上运行带 attestation 的 speculative decoding？能否把 [[Hawkeye-MLSys26|Hawkeye]] 扩展成「任何 GPU kernel 的 spec 级可复现性」的通用工具？

### 5. MoE 调度在非训练 / 非推理的第三空间

**为什么小团队能做**：MoE 系统研究以往需要 trillion 参数模型，但 [[CRAFT-MLSys26|CRAFT]]、[[FarSkip-Collective-MLSys26|FarSkip-Collective]] 都用 DeepSeek-V2-Lite (16B) / Qwen-3-30B 做验证——2-4 张 H100 足够。

**指向空白的论文**：[[CRAFT-MLSys26|CRAFT]] 只处理 replication 不处理 routing；[[FarSkip-Collective-MLSys26|FarSkip-Collective]] 改架构需要额外蒸馏；[[EventTensor-MLSys26|EventTensor]] 解决编译但不解决调度；[[MoE-Serving-Tax-MLSys26|MoE-Serving-Tax]] 定量分析但未给出自动优化器。

**Open problems**：MoE + speculative decoding 如何协同（draft 和 verify 的 expert 激活重叠率？）？MoE + RAG 缓存命中（哪些 expert 用于哪类 query）？MoE continuous batching 的 expert 预取调度？

### 6. Serverless / 冷启动 / 容错 serving 的轻量方案

**为什么小团队能做**：[[BreakingTheIce-MLSys26|BreakingTheIce]] 和 [[GhostServe-MLSys26|GhostServe]] 的核心是测量 + 轻量机制，不需要大规模集群；[[ProfInfer-MLSys26|ProfInfer]] 用 eBPF 挂 llama.cpp，开销 <4%。

**指向空白的论文**：[[BreakingTheIce-MLSys26|BreakingTheIce]] 剖析 vLLM 冷启动但未给出通用 warm-pool 策略；[[FaaScale-MLSys26|FaaScale]] 的 RDMA 权重广播依赖特定网络栈；[[RaidServe-MLSys26|RaidServe]] 的 KV 冗余与 [[GhostServe-MLSys26|GhostServe]] 的 erasure coding 未统一抽象。

**Open problems**：serverless LLM 的「分层冷启动」（权重 / KV / compiler cache）最优策略是什么？容错 serving 能否在 tensor parallel 和 pipeline parallel 之间做 trade-off 而不牺牲 SLO？[[BEAM-MLSys26|BEAM]] 的 DVFS 能否与 [[MorphServe-MLSys26|MorphServe]] 的 runtime 精度切换协同？
