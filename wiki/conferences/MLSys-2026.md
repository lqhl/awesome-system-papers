---
type: conference
venue: MLSys
year: 2026
paper_count: 79
first_generated: 2026-04-24
last_updated: 2026-04-24
---

# MLSys 2026

> 79 篇论文，[[KV-Cache]] / attention / [[Speculative-Decoding]] 三条 LLM 推理主线占 ~30%，[[MoE]] 训练与推理加 MoE 友好的调度是本届最密集的新共识，AI4AI（LLM 自动生成 kernel / HDL / 优化算法）正从 OSDI/SOSP 溢出到 MLSys，联邦学习与可审计 ML（ZK、GPU-CC、确定性复现）形成独立集群。

## 概览

**LLM 推理系统仍是中心引力场**。围绕 serving 的调度、disaggregation、attention kernel、KV cache、speculative decoding 占掉近一半的 proceedings。[[NVIDIA-Disagg-Study]] 这类「pragmatic take」式经验研究首次进场，与 [[LayeredPrefill]]、[[LAPS]] 等对 [[Chunked-Prefill]] 痛点的系统性修补呼应——MLSys 2026 已经过了「disaggregation 能否 work」的阶段，进入「哪些工作负载该 disagg、怎么 rate match」的细粒度优化时代。

**MoE 问题开始主导大模型系统设计**。从训练端的 [[FP8FlowMoE]]、[[MoEBlaze]]、[[FarSkip-Collective]] 到推理端的 [[CRAFT]]、[[EventTensor]]，再加上多个「MoE-aware」调度工作（[[LayeredPrefill]]、[[CRAFT]]），MoE 系统问题从 2024-2025 年的附带话题升级为与 dense LLM 并列的议题轴。

**AI4AI 急速扩张**：用 LLM agent 自动生成 GPU kernel（[[AccelOpt]]、[[PIKE]]、[[TritorX]]）、HDL（[[VeriMoA]]）、auto-tuning 优化器（[[LLaMEA-KernelTuner]]）、合成训练数据（[[Matrix]]）的工作形成独立 track。相比 2024-2025 年 FunSearch / AlphaEvolve 这类 hero demo，MLSys 2026 的 AI4AI 论文更强调「闭环可复现」：提供 benchmark（[[FlashInfer-Bench]]）、error-fixing 子 agent、多 backbone 对比。

**可审计 / 可信 ML 浮出水面**：[[Hawkeye]]（CPU bit-exact 复现 Tensor Core）、[[ZK-APEX]]（approximate unlearning 的 ZK 证明）、[[GPU-CC-Security]]（Hopper confidential computing 分析）、[[Privatar]]（VR 安全卸载）、[[DP-ZeRO]]（DP + ZeRO）共同构成「推理/训练过程可以被第三方验证」这一新研究方向。这在 OSDI/SOSP 原本是独立议题，现在开始渗透 MLSys。

**与往届的对比**：相比 MLSys 2025，本届 [[PagedAttention]] / [[vLLM]] 内部优化式论文明显减少，取而代之的是「跨 vLLM/SGLang 的 IR 层（[[SpanQueries]]）」、「vLLM 之外的替代 compile 路径（[[EventTensor]]、[[FlashInfer-Bench]]、[[Flashlight]]）」，说明社区已经把 vLLM/SGLang 当成基础设施而非研究目标。

## 论文分类

### LLM 推理服务与调度（13 篇）

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
- [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] — AI 生成 kernel 闭环框架，抗 reward-hacking + 动态 `apply()` 注入 vLLM/SGLang

### Attention / KV Cache 优化（8 篇）

- [[FlexiCache-MLSys26|FlexiCache]] — KV head 时域稳定性分级处理，GPU 显存降 70%、吞吐 1.38-1.55×
- [[Kitty-MLSys26|Kitty]] — 2-bit [[KV-Cache]] + channel-wise 精度提升 + Triton dequant kernel，8× 内存、2.1-4.1× 吞吐
- [[MAC-Attention-MLSys26|MAC-Attention]] — 匹配 pre-RoPE 查询复用 attn summary，128K 下 KV 访问降 99%、attn 14.3×
- [[SkipKV-MLSys26|SkipKV]] — reasoning 模型的句级 KV eviction + adaptive steering，2× 压缩下准确率 +6.7%
- [[BLASST-MLSys26|BLASST]] — FlashAttention online softmax 运行时 skip 低贡献 block，prefill 1.62×、decode 1.48×
- [[IntAttention-MLSys26|IntAttention]] — IndexSoftmax 32-LUT 实现纯整数 attention，Arm CPU 比 FP16 快 3.7×
- [[FlashAttention-4-MLSys26|FlashAttention-4]] — Blackwell B200 上 2-CTA MMA + TMEM + 软件 exp，BF16 1613 TFLOPS/s，cuDNN 比 1.3×
- [[MTraining-MLSys26|MTraining]] — Context Parallelism 下动态稀疏注意力的 Striped 布局 + Hierarchical Ring，Qwen2.5-3B 上下文到 512K

### Speculative Decoding 与新解码范式（7 篇）

- [[DAS-MLSys26|DAS]] — RL rollout 的 per-problem 滑动窗口 suffix tree drafter + long-tail budget 分配，rollout 延迟 -50%
- [[PRISM-MLSys26|PRISM]] — 按 draft step 拆分 draft model（类 MoE 条件计算），[[SGLang]] 吞吐 >2.6×
- [[SparseSpec-MLSys26|SparseSpec]] — self-speculation + PillarAttn 动态 sparse，从 verify 阶段白嫖 top-K，Qwen3 上 2.13×
- [[SpecDecodeBench-MLSys26|SpecDecodeBench]] — 首次生产级 [[vLLM]] 上系统评测，验证阶段开销主导、接受行为高度异质
- [[SpecDiff-2-MLSys26|SpecDiff-2]] — 离散扩散 drafter + streak-distillation + self-selection，5.5× 加速无损
- [[TiDAR-MLSys26|TiDAR]] — diffusion-AR 混合，单前向 diffusion drafting + AR verification，无损 4.71-5.91×
- [[CDLM-MLSys26|CDLM]] — block-wise causal mask + consistency 蒸馏把 diffusion LM 压成 block-causal，3.6-14.5× 降延迟

### MoE 训练与推理（5 篇）

- [[CRAFT-MLSys26|CRAFT]] — MoE expert replica 按层动态分配（MCKP DP），DeepSeek-R1/Kimi-K2 上比 EPLB 均匀复制 1.14-1.2×
- [[FarSkip-Collective-MLSys26|FarSkip-Collective]] — 改 skip 连接让下一 sub-block 用 partial activation 启动，all-to-all 与计算重叠，FCSD 蒸馏 <2.5% 精度差
- [[FP8FlowMoE-MLSys26|FP8FlowMoE]] — scaling-aware transpose 算子消除重复 cast，DeepSeek-V3 训练 +21%、单卡显存 -16.5 GB
- [[MoEBlaze-MLSys26|MoEBlaze]] — MoE token 路由无 per-expert buffer，on-the-fly gather/scatter 融合 + 与 SwiGLU checkpoint 协同，4× 加速
- [[EventTensor-MLSys26|EventTensor]] — 把 GPU 同步事件抽象成一等 tensor，symbolic shape + 数据依赖索引，ETC 编译器 MoE 1.23×

### 分布式训练与并行（10 篇）

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

### GPU Kernel / 编译器 / 硬件互联（5 篇）

- [[HipKittens-MLSys26|HipKittens]] — ThunderKittens 移植到 AMD CDNA3/4，8-wave ping-pong + chiplet swizzle，追平 AITER 手写汇编
- [[ParallelKittens-MLSys26|ParallelKittens]] — 多 GPU kernel 的 8 个 primitive + 统一模板，<50 行 device 代码匹配 Flux/Comet/CUTLASS
- [[Flashlight-MLSys26|Flashlight]] — TorchInductor 三类图重写，`torch.compile` 自动生成 FlashAttention 风格 Triton，对齐 FlexAttention
- [[Collective-NoC-MLSys26|Collective-NoC]] — ML 加速器的 collective-capable NoC + Direct Compute Access（借 tile FPU 做 in-network reduction），GEMM 3.8×
- [[PyLO-MLSys26|PyLO]] — 学习型优化器 VeLO / small_fc_lopt 从 JAX 移植到 PyTorch + 自定义 CUDA kernel，ViT 优化器 4× 提速

### LLM-driven 代码 / kernel / 数据生成（AI4AI）（6 篇）

- [[AccelOpt-MLSys26|AccelOpt]] — AWS Trainium NKI kernel 优化的 LLM beam search + optimization memory，gpt-oss + Qwen3-Coder 匹配 Claude 4 但成本 26× 低
- [[LLaMEA-KernelTuner-MLSys26|LLaMEA-KernelTuner]] — LLM + 进化算法生成 auto-tuning 优化器，比人工 baseline 高 72.4%
- [[PIKE-MLSys26|PIKE]] — multi-agent kernel 优化的 exploit-heavy + error-fixing + 粗粒度 step，KernelBench H100 2.88×
- [[TritorX-MLSys26|TritorX]] — Meta MTIA 的 Triton ATen kernel 自动生成，484 算子、20K+ OpInfo 通过率
- [[VeriMoA-MLSys26|VeriMoA]] — spec-to-HDL 的 Mixture-of-Agents，quality-guided global cache，VerilogEval 2.0 Pass@1 +15-30%
- [[Matrix-MLSys26|Matrix]] — Meta FAIR 的 P2P message-driven multi-agent 合成数据，31 节点 248 GPU 上 12,400 并发，6.8× Coral

### 量化（3 篇）

- [[CAGE-MLSys26|CAGE]] — Pareto-optimality 推导的 curvature-aware STE 校正，3-bit W+A 预训练匹配 4-bit QuEST
- [[MixLLM-MLSys26|MixLLM]] — 全局显著性给 ~10% 输出通道 8-bit、其余 4-bit，Llama 3.1 70B PPL 退化从 0.5 降到 <0.2
- [[HyperTinyPW-MLSys26|HyperTinyPW]] — 共享 micro-MLP 从 latent code 合成 PW 卷积权重，TinyML 6.31× 压缩

### Agent 系统、记忆与 alignment（5 篇）

- [[OpenHands-SDK-MLSys26|OpenHands-SDK]] — OpenHands 重构成 modular SDK，event-sourced state + opt-in sandbox + 100+ LLM 路由，SWE-Bench Verified SOTA
- [[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] — Dynamic Wavelet Matrix agent 记忆，压缩域 Hamming-ball 搜索，检索 31× 快、token 14× 少
- [[OSWorld-Human-MLSys26|OSWorld-Human]] — computer-use agent 延迟专项研究，planning/reflection 占总延迟 75-94%，369 任务人类金轨迹
- [[PARROT-MLSys26|PARROT]] — LLM sycophancy 鲁棒 benchmark，双盲对比 + 八状态分类，22 LLM 下 follow rate 4%-94% 20× 差异
- [[RLVR-LowData-MLSys26|RLVR-LowData]] — 程序生成 reasoning 数据集研究 RLVR 在 low data 下表现，mixed-difficulty 带 5× sample efficiency

### 扩散模型与视频生成（3 篇）

- [[StreamDiffusionV2-MLSys26|StreamDiffusionV2]] — 视频扩散直播系统，SLO-aware batching + sink-token rolling KV + motion-aware noise，4× H100 达 58.28 FPS
- [[Reparo-MLSys26|Reparo]] — VQGAN + 时空 ViT 生成式视频会议编解码，每帧独立，50-75% 丢包 PSNR 比 VP9+Tambur 高 11-16 dB
- [[db-SP-MLSys26|db-SP]] — 视觉 DiT 的 dual-balanced（head + block）sequence parallelism，Wan2.1-T2V-14B 端到端 1.25×

### 联邦学习与隐私 / 可审计 ML（6 篇）

- [[PLayer-FL-MLSys26|PLayer-FL]] — 借 model pruning 一阶重要性定义 federation sensitivity，第一个 epoch 决定哪些层 federate
- [[ProToken-MLSys26|ProToken]] — 联邦 LLM 的 token 级 client 归因，梯度加权 activation 内积，4×4 配置 98.62% 准确率
- [[FLoRIST-MLSys26|FLoRIST]] — stacked [[LoRA]] adapter 的 SVD + 能量阈值截断，vs. FLoRA 58×、vs. full FT 227× 通信
- [[Privatar-MLSys26|Privatar]] — 多用户 VR 把 avatar 重建 secure offload 到 PC，block-DCT 频域分割 + PAC Privacy，2.37× 并发
- [[ZK-APEX-MLSys26|ZK-APEX]] — 边缘个性化模型的 approximate unlearning ZK 证明，Halo2 ~2h 比重训验证快 10^7×
- [[GPU-CC-Security-MLSys26|GPU-CC-Security]] — 首个 NVIDIA Hopper GPU Confidential Computing 系统安全分析，上报多个问题

### Benchmark / 可复现性 / 经验报告（3 篇）

- [[Hawkeye-MLSys26|Hawkeye]] — 逆向 Tensor Core rounding/subnormal/累加顺序，CPU bit-exact 复现 FP16/BF16/FP8 16×16 MMA
- [[Chakra-MLSys26|Chakra]] — Meta+GATech+HPE 的分布式 ML 执行图 schema + 生成式合成 trace，obfuscated trace 给 HW 厂商 co-design
- [[SakuraONE-MLSys26|SakuraONE]] — 800-GPU H100 AI HPC 集群经验，TOP500 #49，Top-100 中唯一 800 GbE + SONiC 开源网络栈

### 边缘 / 专业领域应用（5 篇）

- [[EarthSight-MLSys26|EarthSight]] — LEO 卫星图像地面-轨道联合调度，多任务共享 backbone + 轨道 utility-driven filter，P90 延迟 51→21 min
- [[Spira-MLSys26|Spira]] — 首个 voxel-property-aware 稀疏卷积引擎，vs. TorchSparse++/Minuet 平均 1.68×
- [[CSLE-MLSys26|CSLE]] — Cyber Security Learning Environment，Docker Swarm 数字孪生 + MDP 仿真，15 套 twin / 34 RL 算法
- [[LEANN-MLSys26|LEANN]] — 端侧向量索引不存 embedding，查询现场重算 + 两级 PQ+精确 + 度数保留剪枝，188 GB→4 GB（50×）
- [[TransferEngine-MLSys26|TransferEngine]] — 跨 ConnectX-7 + AWS EFA 的统一 RDMA 点对点库，IMMCOUNTER 完成通知，trillion-param RL 权重 1.3s

## 研究趋势

**1. [[Chunked-Prefill]] 的「后时代」：调度轴开始从 token 重构为 layer / length / locality**。2024 Sarathi-Serve 定下的 chunked prefill 范式正被多角度挑战。[[LayeredPrefill-MLSys26|LayeredPrefill]] 直接把调度轴换成 layer-group 消除 MoE expert 重载；[[LAPS-MLSys26|LAPS]] 在 prefill 内部再按长度 disaggregate；[[SpanQueries-MLSys26|SpanQueries]] 把 chat/RAG/agent 统一到声明式表达式树以暴露 attention locality 优化空间；[[Stream2LLM-MLSys26|Stream2LLM]] 处理 streaming prompt 场景的 prefill 重叠。共同方向：chunk 只是工具，真正需要调度的是「模型层」「请求类型」「缓存局部性」这些 first-class 概念。

**2. MoE 从 "附带支持" 升级到 "一等系统问题"**。5 篇专攻 [[MoE]] 的论文外加 MoE-aware 调度（[[LayeredPrefill-MLSys26|LayeredPrefill]]、[[CRAFT-MLSys26|CRAFT]]）表明 MoE 系统已脱离「vanilla dense serving 的变种」成为独立议题。[[FarSkip-Collective-MLSys26|FarSkip-Collective]] 改架构让 all-to-all 与计算重叠，[[FP8FlowMoE-MLSys26|FP8FlowMoE]] 从 FP8 cast 链路切入，[[MoEBlaze-MLSys26|MoEBlaze]] 消掉 per-expert buffer，[[EventTensor-MLSys26|EventTensor]] 提供 megakernel 编译路径。注意：所有论文都把 Kimi-K2 / DeepSeek-V3 当作默认 baseline——1T 参数的开源 MoE 已经是「标准测试集」。

**3. Speculative decoding 走出 EAGLE 式 draft model 独霸格局**。7 篇 speculative 工作呈现明显分化：[[SpecDiff-2-MLSys26|SpecDiff-2]]、[[TiDAR-MLSys26|TiDAR]]、[[CDLM-MLSys26|CDLM]] 用扩散模型做 drafter 绕开 AR 延迟瓶颈；[[DAS-MLSys26|DAS]]、[[SparseSpec-MLSys26|SparseSpec]] 走 training-free 路线（suffix tree / self-speculation）；[[PRISM-MLSys26|PRISM]] 把 draft model 按 step 切成 MoE 式条件计算。[[SpecDecodeBench-MLSys26|SpecDecodeBench]] 直接把标题写成 "Performance or Illusion?" 对现有工作发起 reality check——表明社区已对 single-number 加速报道失去信任。

**4. AI4AI 成建制进入 MLSys**。6 篇 LLM agent 生成 kernel / HDL / 优化器的论文（[[AccelOpt-MLSys26|AccelOpt]]、[[PIKE-MLSys26|PIKE]]、[[TritorX-MLSys26|TritorX]]、[[VeriMoA-MLSys26|VeriMoA]]、[[LLaMEA-KernelTuner-MLSys26|LLaMEA-KernelTuner]]、[[Matrix-MLSys26|Matrix]]）外加 [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] 的基准框架，构成了独立子领域。与前一代 hero demo 不同，这届明显强调：开源 LLM 足够（gpt-oss、Qwen3-Coder 匹配 Claude）、必须提供 benchmark（否则无法证明 generalization）、error-fixing subagent 比大模型本身更重要。

**5. 可审计 / 可信 ML 从边缘变主流议题**。[[Hawkeye-MLSys26|Hawkeye]]（CPU 复现 Tensor Core）、[[ZK-APEX-MLSys26|ZK-APEX]]（unlearning ZK 证明）、[[GPU-CC-Security-MLSys26|GPU-CC-Security]]（Hopper CC 安全分析）、[[Privatar-MLSys26|Privatar]]（VR secure offload）、[[DP-ZeRO-MLSys26|DP-ZeRO]]（DP + ZeRO）共 5-6 篇。这些论文共同指向一个前提：AI 部署开始进入被监管、被审计、被挑战的环境，"训练/推理 is 正确" 不再是隐含假设。Hawkeye 的结论（Tensor Core 行为跨 Ampere/Hopper/Ada 完全可逆向）在审计和 compliance 领域是 enabling 级别的基础工作。

**6. 异构硬件 / 非 NVIDIA 开始有一席之地**。[[HipKittens-MLSys26|HipKittens]] 宣称 "消灭 CUDA moat"，在 AMD CDNA3/4 上追平 AITER 手写汇编；[[TransferEngine-MLSys26|TransferEngine]] 跨 ConnectX-7 + AWS EFA；[[AccelOpt-MLSys26|AccelOpt]] 在 AWS Trainium 上；[[TritorX-MLSys26|TritorX]] 在 Meta MTIA；[[AXLearn-MLSys26|AXLearn]] 声称 H100/TPU v5p/Trainium2 全等权；[[SakuraONE-MLSys26|SakuraONE]] 报告 800 GbE + SONiC 开源网络栈取代 InfiniBand。整届会议明显不把 H100 + NCCL + CUDA 当默认。

## 值得关注的方向

### 1. Span Query 风格的 declarative serving IR 研究

**为什么小团队能做**：[[SpanQueries-MLSys26|SpanQueries]] 证明 492 行改动就能让 2B 模型准确率超过 stock 8B——核心难度不在写代码，而在设计声明式语义。适合 1-2 人深挖数月。

**指向空白的论文**：[[SpanQueries-MLSys26|SpanQueries]] 只覆盖了 chat / RAG / inference-scaling / agent 四个场景的交换律；[[Stream2LLM-MLSys26|Stream2LLM]] 的 streaming prompt 语义没进 IR；[[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] 的 trace schema 是命令式的。

**Open problems**：能否把 agent 的 tool-calling 循环、speculative decoding 的 acceptance 逻辑也纳入 span query IR？在 MTraining 这类长上下文训练场景里 span query 能否表达 context parallelism 的 locality？

### 2. Speculative decoding 的 reality-check / benchmark 生产力

**为什么小团队能做**：[[SpecDecodeBench-MLSys26|SpecDecodeBench]] 的核心贡献不是新算法而是「对生产环境的严格测量」——单张 H100 或 2-4 张就能跑，主要工作是实验设计和数据收集。

**指向空白的论文**：[[SpecDecodeBench-MLSys26|SpecDecodeBench]] 暴露了 position / request / dataset 三层异质性但只给出粗粒度分析；[[DAS-MLSys26|DAS]] 专门针对 RL rollout 的长尾；[[SparseSpec-MLSys26|SparseSpec]] 与 [[TiDAR-MLSys26|TiDAR]] 走不同技术路线但缺乏对比。

**Open problems**：在 reasoning 模型（o1 / R1 风格长 CoT）上 speculative 的 acceptance 如何演化？long-context（>64K）下 draft 模型该不该共享 KV？扩散 drafter（SpecDiff-2 / TiDAR）在真实 vLLM 上的端到端开销如何？

### 3. Agent memory 的 benchmark 与系统化度量

**为什么小团队能做**：[[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] 用单机就跑完全部 benchmark（LoCoMo / LongMemEval）；[[OSWorld-Human-MLSys26|OSWorld-Human]] 的人类金轨迹标注是劳动密集而非算力密集。

**指向空白的论文**：[[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] 的 Dynamic Wavelet Matrix 给了一个具体内存数据结构，但没有与 vector DB / KV agent state / knowledge graph 的系统对比；[[OSWorld-Human-MLSys26|OSWorld-Human]] 发现 planning/reflection 占 75-94% 延迟但没给出 agent 内部 KV 复用的系统方案。

**Open problems**：agent workflow 里「trajectory cache」的正确抽象是什么（[[KV-Cache]] 的 agent 版本）？跨 agent session 的 long-term memory 是否应该像 [[LEANN-MLSys26|LEANN]] 那样不存而现算？

### 4. 可审计 ML 的轻量级工具链

**为什么小团队能做**：[[Hawkeye-MLSys26|Hawkeye]] 全部用公开 PTX benchmark；[[ZK-APEX-MLSys26|ZK-APEX]] 的 Halo2 proof 在单机 <0.7 GB 内存。

**指向空白的论文**：[[Hawkeye-MLSys26|Hawkeye]] 覆盖 FP16/BF16/FP8 16×16 MMA 但没覆盖 block-scaled fp4（Blackwell）、非方阵 MMA、Transformer Engine 的在线 rescaling；[[ZK-APEX-MLSys26|ZK-APEX]] 只做 unlearning，没做训练过程证明。

**Open problems**：能否给 [[MoE]] routing 做 ZK 证明（expert 选择不作弊）？能否在 confidential computing GPU 上运行带 attestation 的 speculative decoding？能否把 [[Hawkeye-MLSys26|Hawkeye]] 扩展成「任何 GPU kernel 的 spec 级可复现性」的通用工具？

### 5. MoE 调度在非训练 / 非推理的第三空间

**为什么小团队能做**：MoE 系统研究以往需要 trillion 参数模型，但 [[CRAFT-MLSys26|CRAFT]]、[[FarSkip-Collective-MLSys26|FarSkip-Collective]] 都用 DeepSeek-V2-Lite (16B) / Qwen-3-30B 做验证——2-4 张 H100 足够。

**指向空白的论文**：[[CRAFT-MLSys26|CRAFT]] 只处理 replication 不处理 routing；[[FarSkip-Collective-MLSys26|FarSkip-Collective]] 改架构需要额外蒸馏；[[EventTensor-MLSys26|EventTensor]] 解决编译但不解决调度。

**Open problems**：MoE + speculative decoding 如何协同（draft 和 verify 的 expert 激活重叠率？）？MoE + RAG 缓存命中（哪些 expert 用于哪类 query）？MoE continuous batching 的 expert 预取调度？

### 6. 异构 / 非 NVIDIA kernel 的 DSL 迁移研究

**为什么小团队能做**：[[HipKittens-MLSys26|HipKittens]] 只有 6 位作者，核心工作是 ThunderKittens 风格 DSL 到 CDNA 的移植；AMD MI300 在云平台已可租（Lambda / vast.ai）。

**指向空白的论文**：[[HipKittens-MLSys26|HipKittens]] 聚焦 AMD；[[ParallelKittens-MLSys26|ParallelKittens]] 聚焦多 GPU；[[Flashlight-MLSys26|Flashlight]] 聚焦 PyTorch。这三者没有统一抽象。

**Open problems**：ThunderKittens/ParallelKittens/HipKittens 能否提取共同 primitive 变成跨 vendor 的真正可移植 DSL？Trainium / TPU / MTIA 有没有「tile DSL」路径？「learned optimizer」这类非传统 kernel（[[PyLO-MLSys26|PyLO]]）是否需要单独的 DSL 抽象？
