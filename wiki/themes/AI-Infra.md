---
type: theme
topic: AI-Infra
theme_kind: area
member_tag: area/ai-infra
paper_count: 64
first_generated: 2026-04-24
last_updated: 2026-08-18
tags: [topic-overview, llm-systems]
---

# AI-Infra 综述

> 64 篇论文覆盖 MoE 训练与 expert placement、[[KV-Cache]]、长上下文、生产 serving、ML compiler/runtime、GPU 可靠性以及 agent-driven systems optimization；共同趋势是把模型状态、硬件 layout、生产故障和 agent 可操作性提升为一等系统对象。

## 核心论文

### MoE 推理与 Expert 管理（8 篇）

- [[Libra-ICLR26|Libra]] — speculative gating prediction (70-80%) + Two-Stage Locality-Aware Execution，prefill +19.2%
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — ILP + heuristic 联合优化均衡与搬运代价，搬运 −57%、MoE 延迟 −12.5%
- [[FluxMoE-arXiv26|FluxMoE]] — expert 权重 PagedTensor 分页 + 两层滑动窗口，Qwen3-Next-80B 上 3.0× 吞吐
- [[MOE-INFINITY-arXiv24|MOE-INFINITY]] — personal-machine request-level sparse expert cache，3.1-16.7× TPOT 改善
- [[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]] — CXL-NDP 执行 cold experts + prefill-guided placement，最高 8.7× decoding throughput
- [[OD-MoE-arXiv25|OD-MoE]] — shadow model SEP 预测 expert activation，cacheless edge loading，99.94% recall
- [[CoX-MoE-DAC26|CoX-MoE]] — AMX CPU-GPU co-execution + coalesced expert execution，最高 2.4× over MoE-Lightning
- [[MoE-Lightning-ASPLOS25|MoE-Lightning]] — CGOPipe 联合 CPU attention、GPU expert 与权重 I/O，受限 GPU 上最高 10.3×

### KV Cache 跨请求复用与传输（4 篇）

- [[CacheGen-SIGCOMM24|CacheGen]] — KV cache 自定义量化 + 算术编码 3.5-4.3× 压缩，adaptive streaming 按带宽调级别
- [[CacheBlend-EuroSys25|CacheBlend]] — RAG 多 chunk selective KV recompute（<15% token），TTFT 降 2.2-3.3×
- [[LMCache-arXiv25|LMCache]] — GPU/CPU/SSD/remote 多 tier KV 中间件 + prefix reuse + PD disaggregation，最高 15× 吞吐
- [[APE-ICLR25|APE]] — 独立 context KV + attention calibration，128K context prefill 降 28×、端到端最高 4.5×

### 长上下文 / 稀疏注意力与并行生成（5 篇）

- [[NSA-ACL25|NSA]] — 压缩 + 选择 + 滑动窗口三分支原生可训练稀疏 attention，64K 解码 11.6×、backward 6.0×
- [[MSA-arXiv26|MSA]] — 端到端可微 sparse attention 替代 RAG retrieve-then-read，2×A800 跑通 100M token
- [[AttnRes-arXiv26|Attention Residuals]] — 层间残差升级为 softmax attention，Kimi Linear 48B 下游全面提升
- [[MagicDec-ICLR25|MagicDec]] — compressed-KV self-speculation 挑战“大 batch 无推测收益”，长 context 最高加速 2.51×
- [[Multiverse-NeurIPS25|Multiverse]] — 模型生成 Map/Process/Reduce 控制结构，动态并行 reasoning 最高约 2×

### KV Cache 后处理与可编辑性（3 篇）

- [[PASTA-ICLR24|PASTA]] — post-hoc attention steering + head profiling，Llama-7B 平均 accuracy +22%
- [[LLMSteer-NeurIPSW24|LLMSteer]] — query-independent 双次 re-reading steering，兼容 prefix caching，质量差距缩小 65.9%
- [[Cartridges-ICLR26|Cartridges]] — self-study 离线训练紧凑 KV 表示，38.6× 更少内存、26.4× 更高吞吐

### KV Cache 压缩与检索（2 篇）

- [[IceCache-arXiv26|IceCache]] — semantic token clustering + [[PagedAttention]] page selection，36k context 99.0% accuracy
- [[MoE-nD-arXiv26|MoE-nD]] — per-layer routing 淘汰与 K/V bit 分配，136 MB 达到 14× 压缩且匹配 1.9 GB baseline

### Serving、结构化生成与云资源系统（10 篇）

- [[NEO-MLSys25|NEO]] — 部分请求的 attention/KV 卸载到本机 CPU，T4/A10G/H100 最高提高 7.5×/26%/14%
- [[SuperServe-NSDI25|SuperServe]] — SuperNet 即时子模型激活 + SlackFit，burst trace 上 SLO attainment 最高提高 2.85×
- [[BlendServe-ASPLOS26|BlendServe]] — 联合 prefix sharing 与 compute-memory overlap，离线吞吐最高提高 1.44×
- [[LLMQueryReordering-MLSys25|LLMQueryReordering]] — 联合重排行与字段扩大 prefix cache 命中，JCT 最高改善 3.4×
- [[SkyServe-EuroSys25|SkyServe]] — 跨 failure domain 的 spot replication 与 fallback，最高节省 44% serving cost
- [[SkyWalker-EuroSys26|SkyWalker]] — 利用 region 日周期错峰并保持 prefix locality，实际总成本降低 25%
- [[Agentix-NSDI26|Agentix]] — 把 agent program 作为调度对象，相同 latency 下 program throughput 提高 4–15×
- [[FlashInfer-MLSys25|FlashInfer]] — composable KV format + JIT attention + graph-compatible scheduling，inter-token latency 降 29%–69%
- [[XGrammar-MLSys25|XGrammar]] — vocabulary 预检与 persistent parser stack，grammar processing 最高 100×
- [[XGrammar2-CAIS26|XGrammar-2]] — TagDispatch + Cross-Grammar Cache 支撑动态 agent tool protocol，编译最高 6×以上

### RL 训练资源系统（1 篇）

- [[RLBoost-NSDI26|RLBoost]] — 将无状态 rollout 放到可抢占 GPU，训练吞吐提高 1.51–1.97×、成本效率提高 28%–49%

### Agent-native Framework 与自动系统优化（8 篇）

- [[PithTrain-arXiv26|PithTrain]] — 以约 11 KLoC Python-native MoE 训练栈、显式调用和 task skills 降低 coding agent 的框架操作成本；5 组 H100/B200 配置中 4 组匹配或超过 Megatron-LM，ATE-Bench 最多减少 70% Agent Turns 和 64% Active GPU Time
- [[SkVM-SOSP26|SkVM]] — 把 skill 当自然语言代码，以 capability-aware AOT/JIT、environment binding 和 resource-aware runtime 适配异构模型与 harness
- [[VibeTensor-arXiv26|VibeTensor]] — coding agent 生成跨 C++/CUDA/autograd/frontend 的 DL runtime；能运行但训练仍慢 PyTorch 1.7–6.2×
- [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] — 真实 serving trace、正确性 benchmark 与 `apply()` 组成 kernel generate→deploy 闭环
- [[SOL-ExecBench-arXiv26|SOL-ExecBench]] — 235 个 B200 problems + hardware SOL Score；检测到 14.5% submission reward hacking
- [[AdaExplore-arXiv26|AdaExplore]] — 从失败提炼跨任务 Triton skills，并用 tree search 保持结构多样性
- [[AVO-arXiv26|AVO]] — agent 取代固定 variation operator，7 天 B200 attention evolution 超过 cuDNN/FA4
- [[CAKE-arXiv26|CAKE]] — compiler-agent 共演 typed schedule IR，matched clean start 明显优于直接 CUDA/PTX

### ML Compiler、训练与部署 Runtime（7 篇）

- [[Relax-ASPLOS25|Relax]] — cross-level IR + symbolic shape，跨 NVIDIA/AMD/Apple/移动/WebGPU 部署动态模型
- [[GraphPipe-ASPLOS25|GraphPipe]] — 将线性 pipeline 推广为 stage DAG，多分支 DNN 训练最高 1.6×
- [[Tilus-ASPLOS26|Tilus]] — tile-level GPU DSL 支持任意 1–8 bit 类型与显式 layout
- [[Axe-arXiv26|Axe]] — `(Shard, Replica, Offset)` named-axis layout 统一线程、memory 与 device mesh
- [[EventTensor-MLSys26|Event Tensor]] — 将 tile synchronization 升为一等 tensor，编译 shape/data-dependent dynamic megakernel
- [[MPK-OSDI26|MPK]] — 把多 GPU inference 降成 SM-level task graph 与 persistent megakernel
- [[TapML-ISSTA25|TapML]] — trace-based test carving + 渐进 backend migration，覆盖 105 模型/27 架构/5 平台

### LLM Serving 综述（1 篇）

- [[Miao-LLMServingSurvey-CSUR26|高效生成式 LLM Serving 综述]] — 从算法、kernel、runtime 到 distributed serving 建立 taxonomy；不含统一复现实验

### 生产 LLM Serving 与 KV 管理（5 篇）

- [[BlitzScale-OSDI25|BlitzScale]] — compute-fabric multicast + 全局 host cache + layer-wise live scaling，降低大型模型扩容的 TTFT/TBT tail。
- [[KVCacheInTheWild-ATC25|KVCache Cache in the Wild]] — 用通义生产 trace 重估真实 KV reuse、lifespan 和 eviction policy。
- [[DiffKV-SOSP25|DiffKV]] — 按 K/V、token 和 head 重要性实施差异化压缩与 on-GPU compaction。
- [[LMetric-OSDI26|LMetric]] — 用新增 prefill token 数与 batch size 的乘积联合优化 prefix affinity 和负载均衡。
- [[SolidAttention-FAST26|SolidAttention]] — 为内存受限 AIPC 协同设计 sparse attention、SSD KV layout 与 speculative prefetch。

### 端侧异构执行、调度与可观测性（5 篇）

- [[ProfInfer-MLSys26|ProfInfer]] — 用 [[eBPF]] uprobe 和 PMC 对 llama.cpp/GGML 做 token、graph、operator 三层 profiling。
- [[XSched-OSDI25|XSched]] — 以 XQueue 抽象统一 GPU、NPU、ASIC、FPGA 的软件抢占与带宽调度。
- [[Sirius-ATC25|SIRIUS]] — 在 inference/training 共址时快速收缩训练显存并完成 GPU memory handover。
- [[HeteroInfer-SOSP25|HeteroInfer]] — 联合 mobile GPU、NPU 与 UMA 加速异构 LLM inference。
- [[Sereno-OSDI26|Sereno]] — 把 speculative decoding 的 draft layer 变成后台推理的内存带宽让出点。

### GPU 状态、可靠性与数据系统（5 篇）

- [[SAVE-ATC25|SAVE]] — 按模型 bit vulnerability 选择性保护 GPU memory bit flip。
- [[PhoenixOS-SOSP25|PhoenixOS]] — 推测并验证 GPU kernel 读写集，实现 concurrent checkpoint/restore。
- [[SDCHunter-OSDI26|SDCHunter]] — 用 deterministic replay 定位生产 LLM training 中的 SDC-defective GPU。
- [[FlowANN-OSDI26|FlowANN]] — 解耦 graph ANN discovery/expansion，把短边与长边分别放到 GPU/CPU。
- [[He-GPUKernelFusion-SOSP26|Taming Dynamism on GPUs]] — 以 cross-SM cooperation 和 just-in-time reduction 处理动态 kernel fusion；当前仅有公开 metadata。

## 主题综述

### 生产系统：从单次推理优化转向状态生命周期

[[BlitzScale-OSDI25]] 管理模型权重激活，[[KVCacheInTheWild-ATC25]]、[[DiffKV-SOSP25]] 与 [[LMetric-OSDI26]] 管理 KV state 的生成、压缩、保留和 placement，[[PhoenixOS-SOSP25]]、[[SAVE-ATC25]]、[[SDCHunter-OSDI26]] 则覆盖 checkpoint、bit flip 和 silent corruption。这些工作共同表明，生产 AI infrastructure 的主要对象已从单个 kernel 扩展为跨请求、跨设备、跨故障的长期状态。

### 端侧系统：峰值 FLOPS 不再决定用户体验

[[HeteroInfer-SOSP25]] 处理 GPU/NPU shape 与同步差异，[[Sereno-OSDI26]] 处理后台 inference 与前台应用的 DRAM contention，[[SolidAttention-FAST26]] 把长 context KV 延伸到 SSD，[[ProfInfer-MLSys26]] 则提供算子级观测。四者共同依赖共享内存与异构执行环境，结论不能只按模型 FLOPS 或 token/s 排序。

### Agent 基础设施：skill 开始获得 compiler/runtime 与 framework contract

[[SkVM-SOSP26]] 将 model、harness 和 environment mismatch 形式化为编译目标，并从 skill workflow 提取并行性；[[PithTrain-arXiv26]] 则反向改造被 agent 操作的训练框架，用紧凑代码、显式调用、Python traceback 和 task skill 降低探索与调试成本。两者共同把 agent–environment interface 变成系统优化对象，但证据主要覆盖短任务的 portability/efficiency，尚未证明数小时到多日任务中的持久状态、context compaction 与 crash recovery。

[[FlashInfer-Bench-MLSys26]]、[[SOL-ExecBench-arXiv26]]、[[AdaExplore-arXiv26]]、[[AVO-arXiv26]] 与 [[CAKE-arXiv26]] 进一步组成“契约—评测—搜索—编译”的闭环：先用真实 workload 与硬件 bound 限定目标，再让 agent 从失败和 lineage 学习，最后把反复出现的错误固化为 verifier 与 IR。这里的关键系统对象不再只是 kernel，而是 agent 能否可靠读取和改进的 evaluation environment。

### Compiler 抽象从 operator 扩展到跨层 program

[[Relax-ASPLOS25]] 统一 graph、tensor program 与 library call，[[Axe-arXiv26]] 统一线程、memory 与 device layout，[[EventTensor-MLSys26]] 和 [[MPK-OSDI26]] 则把优化单位推到 tile dependency 和 persistent megakernel。四者共同挑战“一算子一 kernel”的边界，但越向整图扩展，compile cost、动态 control、故障隔离和 production observability 越难保持。

### 主线一：MoE 推理从 load balancing 扩展到多层异构 placement

[[MoE]] 已成为 frontier LLM 默认架构，但 specialization 与 inference-time imbalance 的矛盾把研究重心从「均衡 expert 数」推向「expert 权重与 token 该放在哪层内存、哪类设备」。本 topic 里 [[Libra-ICLR26|Libra]] 与 [[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 互补攻击 prefill 阶段 LB：前者用 hidden state 慢演化做 speculative gating（70-80% vs Lina 20-30%），后者用 ILP 把单次 LB 搬运从 13036 expert 压到 2440。但 **decode 阶段单 token batch 与跨节点 LB** 仍是空白。

[[FluxMoE-arXiv26|FluxMoE]] 走第三条路：不做 LB，把冷 expert 当 [[PagedAttention]] 式虚存分页。与 [[MOE-INFINITY-arXiv24|MOE-INFINITY]]（request-level cache）、[[OD-MoE-arXiv25|OD-MoE]]（完全取消 cache）、[[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]]（CXL-NDP 就地算 cold expert）、[[CoX-MoE-DAC26|CoX-MoE]]（AMX CPU-GPU 共执行）对照，MoE inference 的关键抽象已从「一个 GPU cache」变成 **多层异构资源上的 expert placement 问题**。

### 主线二：KV Cache 从 GPU 临时对象演化为跨 tier 一等数据

[[CacheGen-SIGCOMM24|CacheGen]] → [[CacheBlend-EuroSys25|CacheBlend]] → [[LMCache-arXiv25|LMCache]] 构成 UChicago/Tensormesh 团队三部曲：传输压缩 → 多 chunk 语义融合 → 全栈中间件。核心观察是相邻 token KV 有 locality（delta 方差低 2.4-2.9×）、浅层量化更脆、RAG 多 chunk 的质量损失主要来自缺失 cross-attention 而非位置编码错误。LMCache 把「KV cache as first-class data object」推到工业现实——与 [[PASTA-ICLR24|PASTA]]/[[LLMSteer-NeurIPSW24|LLMSteer]]/[[Cartridges-ICLR26|Cartridges]] 的「KV 可编辑」路线汇合，形成 **持久化 + 可复用 + 可后处理** 的完整范式。

### 主线三：长上下文瓶颈从系统调度转向算法-系统协同

[[NSA-ACL25|NSA]] 强调稀疏 attention 必须 **原生可训练且硬件对齐**——仅降 FLOPs 不够，kernel 必须少搬 KV；[[MSA-arXiv26|MSA]] 用可微 routing key 把 [[RAG]] retrieve-then-read 压进单一 attention；[[AttnRes-arXiv26|AttnRes]] 则在深度维度用 attention 替代固定残差，缓解 PreNorm dilution。三篇共同假设：**长上下文的解法不能只靠 KV 分页或 offload，必须改信息聚合方式**；但各自评测边界不同（NSA 偏 64K MoE 训练/推理 kernel，MSA 偏 100M NIAH，AttnRes 偏下游任务质量）。

### 主线四：KV 压缩从 uniform policy 走向 query/layer aware

[[IceCache-arXiv26|IceCache]] 在 token/page 维度做 semantic clustering 提高 query-aware hit rate；[[MoE-nD-arXiv26|MoE-nD]] 在 layer 维度路由不同 `(keep ratio, K bits, V bits)`。两者都挑战「全局单一 KV budget knob」，暗示下一代系统会暴露 query、layer、head、page、precision 多个可调轴。

## 共同观察

**1. [[KV-Cache]] 与 expert 权重在 HBM 上竞争同一块预算，且竞争形态随 batch/阶段变化。** [[FluxMoE-arXiv26|FluxMoE]]/[[MOE-INFINITY-arXiv24|MOE-INFINITY]] 假设 MoE 推理的主要压力来自 expert 权重 materialization；[[CacheGen-SIGCOMM24|CacheGen]]/[[LMCache-arXiv25|LMCache]] 假设跨请求 KV 复用与传输才是 prefill 瓶颈；[[MoE-nD-arXiv26|MoE-nD]] 则把 KV 压缩做成 per-layer 路由。**适用边界**：HBM 充裕、短 context、dense 模型或强量化后权重已非主导时，paging/offload 收益会被 VMM 与 remap overhead 吃掉（[[FluxMoE-arXiv26|FluxMoE]] Critical Analysis 已指出）。

**2. Prefix/chunk 局部性是 KV 复用收益的前提，而非默认成立。** [[CacheBlend-EuroSys25|CacheBlend]]/[[LMCache-arXiv25|LMCache]]/[[LLMSteer-NeurIPSW24|LLMSteer]] 都依赖稳定 chunk 边界与高复用率；[[Cartridges-ICLR26|Cartridges]] 更进一步假设离线训练成本可被多 query 摊销。**适用边界**：一次性 prompt、多租户强隔离、chunking 策略频繁变化或长输出 multi-turn chat（decode 主导、共享少）时，离线 steering/cartridge 的 ROI 急剧下降。

**3. MoE routing 的可预测性是 prefetch/LB/offload 的共同隐含假设。** [[Libra-ICLR26|Libra]] 用 hidden state 慢演化、[[OD-MoE-arXiv25|OD-MoE]] 用 shadow model SEP、[[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 用 popularity 时间衰减——都假设 expert activation 在 request/token 尺度上可预测。**适用边界**：强 load-balancing 训练、conversation/code/math 混合 batch、高温采样或 router 对数值误差敏感的新架构下，预测精度与 recall 会同时下滑。

**4. 浅层 KV/attention 状态对质量更敏感，是压缩与稀疏化的硬约束。** [[CacheGen-SIGCOMM24|CacheGen]] 的分层量化、[[MoE-nD-arXiv26|MoE-nD]] 的 per-layer sensitivity table、[[NSA-ACL25|NSA]] 的多分支稀疏都暗含此规律。**适用边界**：任务高度依赖浅层 lexical detail 或长程精确对齐（代码跳转、表格、needle-in-haystack 变体）时，统一压缩/稀疏策略可能失效。

**5. Agent 的环境成本既来自 runtime mismatch，也来自软件结构。** [[SkVM-SOSP26]] 显示 skill 在 model、harness 与 environment 间迁移会产生适配和串行执行成本；[[PithTrain-arXiv26]] 显示 registry、跨语言扩展和不透明错误会增加 Per-Turn Context、Agent Turns 与 GPU 重跑。**适用边界**：两篇都主要测受控、小时内任务；更低操作成本不能直接推出 long-horizon reliability、更高任务成功率或更低生产维护总成本。

## 假设冲突与脆弱点

**1. Expert cache vs cacheless：历史复用值不值得为它占 HBM？** [[MOE-INFINITY-arXiv24|MOE-INFINITY]] 假设 personal-machine batch=1 下 request-level expert reuse 足以支撑 sparse cache；[[OD-MoE-arXiv25|OD-MoE]] 假设 shadow model 多层 ahead prediction 足以 **完全取消 cache** 且 99.94% recall。**脆弱点**：多用户 continuous batching 或长 context 挤压 expert cache 时，前者 working set 膨胀；router 对量化误差敏感时，后者 alignment 开销与 routing drift 可能反超收益。需在同一 trace 上测 cache hit rate vs shadow inference overhead vs end-to-end TPOT。

**2. KV 复用：full reuse、selective recompute 还是离线蒸馏？** [[CacheBlend-EuroSys25|CacheBlend]] 假设缺失 <15% token KV recompute 即可补偿 cross-attention；[[Cartridges-ICLR26|Cartridges]] 假设可用梯度下降 **完全替代 prefill** 生成紧凑 KV；[[PASTA-ICLR24|PASTA]] 则只做 post-hoc attention 重加权。**脆弱点**：chunk 彼此独立时可 full reuse；需要强 cross-chunk 推理时 Blend 必要；Cartridge 对窄域 extractive 任务可能不如 [[RAG]] 便宜。需按任务类型分解 TTFT、质量与离线成本三维权衡。

**3. MoE LB：复制 expert vs 分页权重 vs 远端 NDP 计算。** [[Libra-ICLR26|Libra]]/[[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 假设复制/搬运 expert 是主要代价；[[FluxMoE-arXiv26|FluxMoE]] 假设分页权重即可；[[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]] 假设 cold expert 应 **就地算** 而非搬回 GPU。**脆弱点**：网络带宽、CXL 延迟、GPU 算力与 expert 大小的比值决定最优策略；无单一方案在所有 MoE 规模与硬件上占优。

**4. 长上下文：训练原生稀疏 vs 运行时 KV 中间件。** [[NSA-ACL25|NSA]]/[[MSA-arXiv26|MSA]] 假设应改 attention 算子与训练目标；[[LMCache-arXiv25|LMCache]]/[[IceCache-arXiv26|IceCache]] 假设在 **不改模型** 前提下用系统层复用/压缩即可。**脆弱点**：NSA 在短 context 或 KV 已被其他机制压缩时收益下降；MSA 的 NIAH 高分不一定等于综合推理稳定；系统层方案对 thinking model 超长 CoT 的 silent correctness 未验证（连接 [[LLMSteer-NeurIPSW24|LLMSteer]] 的 steering 风险）。

**5. Prefix-caching 兼容 vs 质量增益：steering 能否不改变语义？** [[LLMSteer-NeurIPSW24|LLMSteer]] 假设 query-independent steering 可安全复用；[[PASTA-ICLR24|PASTA]] 的 query-dependent steering 与 prefix cache 不兼容但质量更高。**脆弱点**：被修改的 KV cache 是否产生与原始 prefill 不一致的输出，目前缺乏系统级 parity test；对多租户 eviction 频繁的部署，LLMSteer 的离线 re-reading 成本会重新显性化。

**6. Agent 可读性：显式扁平代码还是可复用抽象？** [[PithTrain-arXiv26]] 以自包含 model file 和直接调用降低单模型 feature integration 成本；[[SkVM-SOSP26]] 则通过 compiler/runtime 适配既有 skill，而不要求重写目标软件。**脆弱点**：PithTrain 未测 cross-model propagation，SkVM 未测大型训练框架的 native/debug 路径；需要在同一组局部修改、跨模型修改和版本升级任务上比较一次性 agent effort、重复代码与回归缺陷。

## 值得关注的方向

### 1. Decode 阶段 + 多节点的 MoE LB

**为什么小团队能做**：算法/系统问题，1-2 张 GPU + 开源 MoE 模型即可验证。

**指向空白的论文**：[[Libra-ICLR26|Libra]] 只优化 prefill；[[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 在单节点评估；[[OD-MoE-arXiv25|OD-MoE]] 的 cacheless 路线未与 LB 联合优化。

**具体 open problems**：decode 单 token batch 下 expert miss 代价 vs prefill 的差异；跨节点 LB 时网络带宽与 GPU 算力联合优化；请求级 vs token 级 LB 的公平性。

### 2. 算法-系统协同的 KV cache / sparse attention 设计

**为什么小团队能做**：[[MSA-arXiv26|MSA]] 证明 4B backbone + 158B token 预训练可在单节点 8×A100 承担。

**指向空白的论文**：[[MSA-arXiv26|MSA]]、[[AttnRes-arXiv26|AttnRes]]、[[NSA-ACL25|NSA]] 三条路线尚未在同一 serving 栈上对照。

**具体 open problems**：routing key projector 训练成本能否降到 8B + LoRA；block sparse 能否反向应用到序列维度；与 [[Speculative-Decoding]] 的组合稳定性。

### 3. KV Cache 可编辑性 pipeline 统一

**为什么小团队能做**：PASTA/LLMSteer 不需训练；Cartridges 冻结 LLM 只训 prefix K/V，单卡可跑。

**指向空白的论文**：[[PASTA-ICLR24|PASTA]]、[[LLMSteer-NeurIPSW24|LLMSteer]]、[[Cartridges-ICLR26|Cartridges]] 未与 [[PagedAttention]] 生产系统深度集成。

**具体 open problems**：profiling → steering → distillation 按 workload 自动选策略；thinking model 超长 CoT 的 Cartridge 压缩；steering 的 silent correctness parity test。

### 4. Query/layer aware KV 策略的轻量 calibration

**为什么小团队能做**：[[MoE-nD-arXiv26|MoE-nD]] 的 offline sensitivity table 与 [[IceCache-arXiv26|IceCache]] 的 DCI-tree 都可在单卡上标定。

**指向空白的论文**：两者正交但未组合；[[LMCache-arXiv25|LMCache]] 的多 tier 仍是全局 policy。

**具体 open problems**：layer sensitivity × semantic page 的联合布局；calibration prompt 长度与轴间偏好估计稳定性；与 PD disaggregation 传输格式的兼容性。

### 5. Agent-native ML systems 的可扩展评测

**为什么小团队能做**：可从开源训练框架、单节点 smoke workload 和公开 coding agent 起步，不需要训练 frontier model；主要成本是构造可执行任务、版本化环境与人工复核。

**指向空白的论文**：[[PithTrain-arXiv26]] 固定单一 agent 且任务偏局部修改；[[SkVM-SOSP26]] 覆盖 skill portability 和短任务，却没有跨小时状态与恢复实验。

**具体 open problems**：按依赖深度、受影响模型数和 context compaction 次数分层 ATE-Bench；跨 3 种 agent/harness 检验 framework ranking；注入 OOM、进程重启、坏 checkpoint 与过期 skill，联合报告成功率、best-state 保持率、Agent Turns、GPU time 和回归缺陷。
