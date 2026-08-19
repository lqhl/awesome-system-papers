---
type: theme
topic: AI-Infra
theme_kind: area
member_tag: area/ai-infra
paper_count: 64
first_generated: 2026-04-24
last_updated: 2026-08-19
tags: [topic-overview, llm-systems]
---

# AI-Infra 综述

> 64 篇论文覆盖混合专家模型训练与专家放置、[[KV-Cache|键值缓存]]、长上下文、生产推理服务、机器学习编译器与运行时、图形处理器（graphics processing unit，GPU）可靠性，以及由智能体驱动的系统优化；共同趋势是把模型状态、硬件布局、生产故障和智能体可操作性提升为一等系统对象。

## 阅读提示

- **混合专家模型（mixture of experts，MoE）**：每个输入只激活部分专家子网络，以减少计算量；系统必须决定专家权重放在哪里，以及如何避免少数专家过载。
- **键值缓存（key-value cache，KV cache）**：大语言模型生成过程中保存的注意力中间状态。它能避免重复计算，却会持续占用高带宽内存（high-bandwidth memory，HBM）。
- **首个词元时间（time to first token，TTFT）**与**每输出词元时间（time per output token，TPOT）**：分别衡量用户等到第一个输出和后续每个输出的延迟。
- **预填充（prefill）**与**解码（decode）**：前者一次处理输入上下文，后者逐步生成输出；两阶段的计算、内存与批处理瓶颈并不相同。
- **智能体（agent）**：能够读取环境、调用工具并迭代修改系统的模型程序。本页既讨论智能体运行所需的基础设施，也讨论如何让智能体优化编译器、内核和训练框架。
- **中央处理器（central processing unit，CPU）**执行通用计算，**神经网络处理器（neural processing unit，NPU）**专用于张量计算，**动态随机存取存储器（dynamic random-access memory，DRAM）**是主机内存。**Compute Express Link（CXL）**是连接处理器、加速器和内存设备的高速互连标准。

## 核心论文

### 混合专家模型推理与专家管理（8 篇）

- [[Libra-ICLR26|Libra]] — 以推测式门控预测（命中率 70%–80%）配合两阶段局部性感知执行，使预填充性能提高 19.2%。
- [[LatencyOptimal-MoELB-INET4AI25|Latency-Optimal MoE LB]] — 结合整数线性规划（integer linear programming，ILP）与启发式算法，同时优化负载均衡和权重搬运代价；搬运量降低 57%，混合专家层延迟降低 12.5%。
- [[FluxMoE-arXiv26|FluxMoE]] — 用 PagedTensor 对专家权重分页，并设置两层滑动窗口；在 Qwen3-Next-80B 上达到 3.0 倍吞吐。
- [[MOE-INFINITY-arXiv24|MOE-INFINITY]] — 面向个人计算机和单请求负载，用稀疏专家缓存使每输出词元时间改善 3.1–16.7 倍。
- [[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]] — 让基于 CXL 的近数据处理（near-data processing，NDP）执行冷专家，并根据预填充结果放置专家；解码吞吐最高提高 8.7 倍。
- [[OD-MoE-arXiv25|OD-MoE]] — 用影子模型的稀疏专家预测器（sparse expert predictor，SEP）预测专家激活，无需缓存即可从边缘存储加载，召回率达到 99.94%。
- [[CoX-MoE-DAC26|CoX-MoE]] — 使用高级矩阵扩展（Advanced Matrix Extensions，AMX）实现 CPU 与 GPU 协同执行，并合并专家计算；相较 MoE-Lightning 最高加速 2.4 倍。
- [[MoE-Lightning-ASPLOS25|MoE-Lightning]] — CGOPipe 协同流水化 CPU 注意力、GPU 专家计算与权重输入输出，在 GPU 受限时最高加速 10.3 倍。

### 键值缓存的跨请求复用与传输（4 篇）

- [[CacheGen-SIGCOMM24|CacheGen]] — 以定制量化和算术编码将键值缓存压缩 3.5–4.3 倍，并根据带宽自适应调整流式传输精度。
- [[CacheBlend-EuroSys25|CacheBlend]] — 对检索增强生成（retrieval-augmented generation，RAG）的多个文本块选择性重算少于 15% 的词元键值状态，使首个词元时间降低 2.2–3.3 倍。
- [[LMCache-arXiv25|LMCache]] — 在 GPU、CPU、固态硬盘和远端存储之间提供多层键值缓存中间件，支持前缀复用以及预填充与解码解聚，吞吐最高提高 15 倍。
- [[APE-ICLR25|APE]] — 独立保存上下文键值状态并校准注意力；在 128K 上下文中将预填充开销降低 28 倍，端到端最高加速 4.5 倍。

### 长上下文、稀疏注意力与并行生成（5 篇）

- [[NSA-ACL25|NSA]] — 以压缩、选择和滑动窗口三个分支实现可原生训练的稀疏注意力；64K 上下文解码加速 11.6 倍，反向传播加速 6.0 倍。
- [[MSA-arXiv26|MSA]] — 用端到端可微的稀疏注意力替代 RAG 的“先检索、后阅读”流程，在 2 张 A800 上处理 1 亿词元。
- [[AttnRes-arXiv26|Attention Residuals]] — 用归一化指数函数（softmax，将一组分数转成权重）注意力替代固定的层间残差连接，使 Kimi Linear 48B 的下游任务表现全面提升。
- [[MagicDec-ICLR25|MagicDec]] — 利用压缩后的键值状态进行自推测，挑战“大批次无法从推测解码获益”的判断；长上下文最高加速 2.51 倍。
- [[Multiverse-NeurIPS25|Multiverse]] — 由模型生成映射、处理和归约控制结构，使推理过程动态并行，最高加速约 2 倍。

### 键值缓存的后处理与可编辑性（3 篇）

- [[PASTA-ICLR24|PASTA]] — 先分析注意力头，再于推理后调整注意力方向；Llama-7B 的平均准确率提高 22%。
- [[LLMSteer-NeurIPSW24|LLMSteer]] — 用与查询无关的两次重读调整键值状态，兼容前缀缓存，并将质量差距缩小 65.9%。
- [[Cartridges-ICLR26|Cartridges]] — 通过离线自学习训练紧凑的键值表示，内存占用减少 38.6 倍，吞吐提高 26.4 倍。

### 键值缓存压缩与检索（2 篇）

- [[IceCache-arXiv26|IceCache]] — 将语义相近的词元聚类，再通过 [[PagedAttention|分页注意力]] 选择缓存页；在 36K 上下文上达到 99.0% 准确率。
- [[MoE-nD-arXiv26|MoE-nD]] — 逐层选择淘汰策略并分配键与值的量化位数；用 136 MB 达到 14 倍压缩，并匹配 1.9 GB 基线的质量。

### 推理服务、结构化生成与云资源系统（10 篇）

- [[NEO-MLSys25|NEO]] — 把部分请求的注意力计算和键值状态卸载到本机 CPU；在 T4、A10G、H100 上分别最高提高 7.5 倍、26% 和 14%。
- [[SuperServe-NSDI25|SuperServe]] — 通过 SuperNet 即时激活子模型，并由 SlackFit 利用请求的延迟余量；在突发负载轨迹上，服务等级目标达成率最高提高 2.85 倍。
- [[BlendServe-ASPLOS26|BlendServe]] — 联合优化前缀共享以及计算与内存访问的重叠，离线吞吐最高提高 1.44 倍。
- [[LLMQueryReordering-MLSys25|LLMQueryReordering]] — 联合重排查询和扩展字段，以提高前缀缓存命中率；作业完成时间（job completion time，JCT）最高改善 3.4 倍。
- [[SkyServe-EuroSys25|SkyServe]] — 跨故障域复制竞价实例，并在实例失效时回退，推理服务成本最高节省 44%。
- [[SkyWalker-EuroSys26|SkyWalker]] — 利用不同地域的日周期错峰，同时保持前缀局部性，实际总成本降低 25%。
- [[Agentix-NSDI26|Agentix]] — 把智能体程序而非单个模型请求作为调度对象，在延迟相同时将程序吞吐提高 4–15 倍。
- [[FlashInfer-MLSys25|FlashInfer]] — 提供可组合的键值格式、即时编译（just-in-time，JIT）注意力和兼容计算图的调度，使词元间延迟降低 29%–69%。
- [[XGrammar-MLSys25|XGrammar]] — 预先检查词表并持久保存解析器栈，使语法处理最高加速 100 倍。
- [[XGrammar2-CAIS26|XGrammar-2]] — 通过 TagDispatch 和 Cross-Grammar Cache 支撑动态智能体工具协议，语法编译最高加速超过 6 倍。

### 强化学习训练资源系统（1 篇）

- [[RLBoost-NSDI26|RLBoost]] — 将无状态的轨迹采样（rollout）放到可抢占 GPU，训练吞吐提高 1.51–1.97 倍，成本效率提高 28%–49%。

### 面向智能体的框架与自动系统优化（8 篇）

- [[PithTrain-arXiv26|PithTrain]] — 以约 1.1 万行 Python 原生混合专家训练栈、显式调用和任务技能降低编程智能体操作框架的成本；在 5 组 H100 或 B200 配置中有 4 组匹配或超过 Megatron-LM，并在 ATE-Bench 中最多减少 70% 的智能体交互轮数和 64% 的 GPU 活跃时间。
- [[SkVM-SOSP26|SkVM]] — 把技能视为自然语言代码，以能力感知的预先编译（ahead-of-time，AOT）和即时编译、环境绑定及资源感知运行时，适配异构模型与评测脚手架。
- [[VibeTensor-arXiv26|VibeTensor]] — 由编程智能体生成横跨 C++、CUDA、自动微分和前端的深度学习运行时；系统能够运行，但训练仍比 PyTorch 慢 1.7–6.2 倍。
- [[FlashInfer-Bench-MLSys26|FlashInfer-Bench]] — 用真实推理服务轨迹、正确性基准和 `apply()` 接口构成从内核生成到部署的闭环。
- [[SOL-ExecBench-arXiv26|SOL-ExecBench]] — 包含 235 个 B200 问题，并用硬件理论上限分数（speed-of-light score，SOL Score）衡量实现效率；检测到 14.5% 的提交存在奖励欺骗。
- [[AdaExplore-arXiv26|AdaExplore]] — 从失败中提炼可跨任务复用的 Triton 技能，并用树搜索保持候选实现的结构多样性。
- [[AVO-arXiv26|AVO]] — 让智能体取代固定的变异算子，在 B200 上连续演化注意力内核 7 天，性能超过 cuDNN 和 FA4。
- [[CAKE-arXiv26|CAKE]] — 让编译器与智能体共同演化带类型的调度中间表示（intermediate representation，IR）；在匹配的全新起点实验中，明显优于直接生成 CUDA 或 PTX。

### 机器学习编译器、训练与部署运行时（7 篇）

- [[Relax-ASPLOS25|Relax]] — 以跨层中间表示和符号形状支持动态模型部署，覆盖 NVIDIA、AMD、Apple、移动端与 WebGPU。
- [[GraphPipe-ASPLOS25|GraphPipe]] — 将线性流水线推广为阶段有向无环图（directed acyclic graph，DAG），使多分支深度神经网络训练最高加速 1.6 倍。
- [[Tilus-ASPLOS26|Tilus]] — 提供图块级 GPU 领域特定语言（domain-specific language，DSL），支持任意 1–8 位数据类型和显式布局。
- [[Axe-arXiv26|Axe]] — 用 `(Shard, Replica, Offset)` 命名轴布局统一表达线程、内存与设备网格。
- [[EventTensor-MLSys26|Event Tensor]] — 将图块同步提升为一等张量，使编译器能生成依赖形状或数据的动态巨型内核。
- [[MPK-OSDI26|MPK]] — 把多 GPU 推理降解为流式多处理器级任务图和持久巨型内核。
- [[TapML-ISSTA25|TapML]] — 通过基于轨迹的测试裁剪和渐进式后端迁移，覆盖 105 个模型、27 种架构和 5 个平台。

### 大语言模型推理服务综述（1 篇）

- [[Miao-LLMServingSurvey-CSUR26|高效生成式 LLM Serving 综述]] — 从算法、计算内核、运行时到分布式推理服务建立分类体系；不含统一复现实验。

### 生产级大语言模型推理服务与键值缓存管理（5 篇）

- [[BlitzScale-OSDI25|BlitzScale]] — 结合计算互连多播、全局主机缓存和逐层在线扩缩容，降低大型模型扩容时首个词元时间与词元间时间的尾延迟。
- [[KVCacheInTheWild-ATC25|KVCache Cache in the Wild]] — 用通义生产轨迹重新评估真实环境中的键值状态复用率、生命周期和淘汰策略。
- [[DiffKV-SOSP25|DiffKV]] — 根据键与值、词元和注意力头的重要性实施差异化压缩，并在 GPU 上紧凑整理缓存。
- [[LMetric-OSDI26|LMetric]] — 以新增预填充词元数与批次大小的乘积为代价指标，联合优化前缀亲和性和负载均衡。
- [[SolidAttention-FAST26|SolidAttention]] — 面向内存受限的人工智能个人计算机，协同设计稀疏注意力、固态硬盘键值布局和推测式预取。

### 端侧异构执行、调度与可观测性（5 篇）

- [[ProfInfer-MLSys26|ProfInfer]] — 使用 [[eBPF]] 用户态探针和性能监控计数器（performance monitoring counter，PMC），从词元、计算图和算子三个层次分析 llama.cpp 与 GGML 的性能。
- [[XSched-OSDI25|XSched]] — 用 XQueue 抽象统一 GPU、神经网络处理器（neural processing unit，NPU）、专用集成电路和现场可编程门阵列的软件抢占与带宽调度。
- [[Sirius-ATC25|SIRIUS]] — 在推理与训练共址时快速收缩训练显存，并把 GPU 内存交接给推理任务。
- [[HeteroInfer-SOSP25|HeteroInfer]] — 联合移动端 GPU、NPU 与统一内存架构（unified memory architecture，UMA），加速异构大语言模型推理。
- [[Sereno-OSDI26|Sereno]] — 把推测解码的草稿层变成后台推理主动让出内存带宽的位置。

### GPU 状态、可靠性与数据系统（5 篇）

- [[SAVE-ATC25|SAVE]] — 根据模型不同位对错误的敏感度，选择性防护 GPU 内存中的位翻转。
- [[PhoenixOS-SOSP25|PhoenixOS]] — 推测并验证 GPU 内核的读写集合，从而并发执行检查点保存与恢复。
- [[SDCHunter-OSDI26|SDCHunter]] — 用确定性重放定位生产级大语言模型训练中会造成静默数据损坏（silent data corruption，SDC）的 GPU。
- [[FlowANN-OSDI26|FlowANN]] — 解耦基于图的近似最近邻（approximate nearest neighbor，ANN）发现与扩展，把短边和长边分别放在 GPU 与 CPU 上处理。
- [[He-GPUKernelFusion-SOSP26|Taming Dynamism on GPUs]] — 通过跨流式多处理器协作和即时归约处理动态内核融合；当前只有公开元数据。

## 主题综述

### 生产系统：从单次推理优化转向管理状态生命周期

[[BlitzScale-OSDI25]] 管理模型权重激活，[[KVCacheInTheWild-ATC25]]、[[DiffKV-SOSP25]] 与 [[LMetric-OSDI26]] 管理键值状态的生成、压缩、保留和放置，[[PhoenixOS-SOSP25]]、[[SAVE-ATC25]]、[[SDCHunter-OSDI26]] 则覆盖检查点、位翻转和静默数据损坏。这些工作共同表明，生产级人工智能基础设施的主要对象已从单个计算内核扩展为跨请求、跨设备、跨故障长期存在的状态。

### 端侧系统：峰值浮点运算能力不再决定用户体验

[[HeteroInfer-SOSP25]] 处理 GPU 与 NPU 的张量形状和同步差异，[[Sereno-OSDI26]] 处理后台推理与前台应用对动态随机存取存储器的争用，[[SolidAttention-FAST26]] 把长上下文键值状态延伸到固态硬盘，[[ProfInfer-MLSys26]] 则提供算子级观测。四者共同依赖共享内存与异构执行环境，因此不能只按每秒浮点运算次数或每秒生成词元数排序。

### 智能体基础设施：技能开始获得编译、运行与框架契约

[[SkVM-SOSP26]] 将模型、评测脚手架和环境之间的不匹配形式化为编译目标，并从技能工作流中提取并行性；[[PithTrain-arXiv26]] 则反向改造由智能体操作的训练框架，用紧凑代码、显式调用、Python 错误追踪和任务技能降低探索与调试成本。两者共同把智能体与环境的接口变成系统优化对象，但证据主要覆盖短任务的可移植性和效率，尚未证明数小时到多日任务中的持久状态、上下文压缩与崩溃恢复能力。

这条主线与 [[Agent-Systems|智能体系统]] 交叉，但研究对象不同：AI-Infra 关注模型、计算内核、编译器与训练或推理资源，Agent-Systems 关注程序、工具、会话状态、工作流和运行安全。SkVM 同时属于二者；PithTrain 主要改造由智能体操作的软件，因此只作为 Agent-Systems 的邻接证据。

[[FlashInfer-Bench-MLSys26]]、[[SOL-ExecBench-arXiv26]]、[[AdaExplore-arXiv26]]、[[AVO-arXiv26]] 与 [[CAKE-arXiv26]] 进一步组成“契约—评测—搜索—编译”的闭环：先用真实工作负载和硬件性能上界限定目标，再让智能体从失败和候选演化谱系中学习，最后把反复出现的错误固化为验证器和中间表示。这里的关键系统对象不再只是计算内核，而是智能体能否可靠读取并改进的评测环境。

### 编译器抽象从算子扩展到跨层程序

[[Relax-ASPLOS25]] 统一计算图、张量程序与库调用，[[Axe-arXiv26]] 统一线程、内存与设备布局，[[EventTensor-MLSys26]] 和 [[MPK-OSDI26]] 则把优化单位扩展到图块依赖和持久巨型内核。四者共同挑战“一算子一内核”的边界；但优化范围越接近完整计算图，编译成本、动态控制、故障隔离和生产可观测性就越难兼顾。

### 主线一：混合专家推理从负载均衡扩展到多层异构放置

[[MoE]] 已成为前沿大语言模型的常见架构，但专家专业化与推理时负载不均的矛盾，使研究重心从“均衡专家数量”转向“专家权重与词元应放在哪层内存、哪类设备”。本主题中，[[Libra-ICLR26|Libra]] 与 [[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 从互补角度优化预填充阶段的负载均衡：前者利用隐藏状态缓慢变化的特征做推测式门控，准确率为 70%–80%，而 Lina 为 20%–30%；后者用整数线性规划把单次负载均衡涉及的专家搬运量从 13036 降至 2440。但解码阶段的单词元批次和跨节点负载均衡仍是空白。

[[FluxMoE-arXiv26|FluxMoE]] 走第三条路：不做负载均衡，而是像分页注意力管理虚拟内存一样为冷专家权重分页。与 [[MOE-INFINITY-arXiv24|MOE-INFINITY]] 的请求级缓存、[[OD-MoE-arXiv25|OD-MoE]] 的无缓存方案、[[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]] 的 CXL 近数据冷专家计算、[[CoX-MoE-DAC26|CoX-MoE]] 的 CPU 与 GPU 协同执行对照后可以看到，混合专家推理的关键抽象已从“一个 GPU 缓存”变成“如何在多层异构资源上放置专家”。

### 主线二：键值缓存从 GPU 临时对象演化为跨层级一等数据

[[CacheGen-SIGCOMM24|CacheGen]]、[[CacheBlend-EuroSys25|CacheBlend]] 与 [[LMCache-arXiv25|LMCache]] 构成芝加哥大学和 Tensormesh 团队的三部曲，依次解决传输压缩、多文本块语义融合和全栈中间件问题。它们的核心观察包括：相邻词元的键值状态具有局部性，其差分方差低 2.4–2.9 倍；浅层状态对量化更敏感；RAG 多文本块的质量损失主要来自缺少跨块注意力，而不是位置编码错误。LMCache 将“键值缓存是一等数据对象”推向工业实现，并与 [[PASTA-ICLR24|PASTA]]、[[LLMSteer-NeurIPSW24|LLMSteer]]、[[Cartridges-ICLR26|Cartridges]] 的键值可编辑路线汇合，形成持久化、可复用、可后处理的完整范式。

### 主线三：长上下文瓶颈从系统调度转向算法与系统协同

[[NSA-ACL25|NSA]] 强调稀疏注意力必须能够原生训练并与硬件匹配：只减少浮点运算量不够，计算内核还必须减少键值状态搬运。[[MSA-arXiv26|MSA]] 用可微的路由键把 [[RAG]] 的“先检索、后阅读”过程合并进单个注意力算子；[[AttnRes-arXiv26|AttnRes]] 则在网络深度方向用注意力替代固定残差，缓解预归一化架构中早期信息逐层稀释的问题。三篇共同假设，长上下文不能只靠键值分页或卸载解决，还必须改变信息聚合方式；但各自评测边界不同：NSA 偏重 64K 上下文的混合专家训练和推理内核，MSA 偏重 1 亿词元的“大海捞针”（needle in a haystack，NIAH）任务，AttnRes 偏重下游任务质量。

### 主线四：键值压缩从统一策略走向查询与层级感知

[[IceCache-arXiv26|IceCache]] 在词元和缓存页维度进行语义聚类，提高针对当前查询的命中率；[[MoE-nD-arXiv26|MoE-nD]] 则逐层选择不同的 `(keep ratio, K bits, V bits)`，即保留比例以及键和值的量化位数。两者都挑战“全局只有一个键值缓存预算旋钮”的设计，暗示下一代系统会暴露查询、层、注意力头、缓存页和数值精度等多个可调轴。

## 共同观察

**1. [[KV-Cache|键值缓存]]与专家权重竞争同一块高带宽内存预算，而且竞争关系随批次和执行阶段变化。** [[FluxMoE-arXiv26|FluxMoE]] 与 [[MOE-INFINITY-arXiv24|MOE-INFINITY]] 假设混合专家推理的主要压力来自将专家权重载入可计算位置；[[CacheGen-SIGCOMM24|CacheGen]] 与 [[LMCache-arXiv25|LMCache]] 假设跨请求键值复用与传输才是预填充瓶颈；[[MoE-nD-arXiv26|MoE-nD]] 则逐层选择键值压缩策略。**适用边界**：当高带宽内存充裕、上下文较短、模型为稠密架构，或强量化已使权重不再主导内存时，分页与卸载收益会被虚拟内存管理和地址重映射开销抵消；[[FluxMoE-arXiv26|FluxMoE]] 的批判性分析已经指出这一点。

**2. 前缀和文本块具有局部性，是键值复用获益的前提，而不是默认事实。** [[CacheBlend-EuroSys25|CacheBlend]]、[[LMCache-arXiv25|LMCache]] 与 [[LLMSteer-NeurIPSW24|LLMSteer]] 都依赖稳定的文本块边界和较高复用率；[[Cartridges-ICLR26|Cartridges]] 更进一步假设离线训练成本可以由多次查询分摊。**适用边界**：面对一次性提示、多租户强隔离、频繁变化的分块策略，或由解码主导且共享较少的长输出多轮对话时，离线调整或训练这种紧凑键值表示的投资回报率会急剧下降。

**3. 混合专家路由可以预测，是预取、负载均衡和卸载共同依赖的隐含假设。** [[Libra-ICLR26|Libra]] 利用隐藏状态缓慢变化，[[OD-MoE-arXiv25|OD-MoE]] 使用影子模型的稀疏专家预测器，[[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 对专家热度进行时间衰减；三者都假设专家激活在请求或词元尺度上可预测。**适用边界**：强负载均衡训练、对话与代码及数学混合批次、高温度采样，或路由器对数值误差敏感的新架构，都可能使预测精度与召回率同时下降。

**4. 浅层键值与注意力状态对质量更敏感，这是压缩和稀疏化的硬约束。** [[CacheGen-SIGCOMM24|CacheGen]] 的分层量化、[[MoE-nD-arXiv26|MoE-nD]] 的逐层敏感度表、[[NSA-ACL25|NSA]] 的多分支稀疏机制都暗含这一规律。**适用边界**：任务高度依赖浅层词法细节或长距离精确对齐时，例如代码跳转、表格或“大海捞针”变体，统一的压缩或稀疏策略可能失效。

**5. 智能体的环境成本既来自运行环境不匹配，也来自软件结构。** [[SkVM-SOSP26]] 显示，技能在模型、评测脚手架与环境之间迁移会产生适配和串行执行成本；[[PithTrain-arXiv26]] 显示，注册表、跨语言扩展和不透明错误会增加每轮上下文、智能体交互轮数与 GPU 重跑。**适用边界**：两篇论文主要评测受控且在数小时内完成的任务；更低的操作成本不能直接推出长周期任务更可靠、任务成功率更高或生产维护总成本更低。

## 假设冲突与脆弱点

**1. 专家缓存与无缓存方案：历史复用是否值得占用高带宽内存？** [[MOE-INFINITY-arXiv24|MOE-INFINITY]] 假设个人计算机上批次为 1 时，请求级专家复用足以支撑稀疏缓存；[[OD-MoE-arXiv25|OD-MoE]] 则假设影子模型可以提前预测后续多层激活，因而能完全取消缓存并达到 99.94% 召回率。**脆弱点**：多用户连续批处理或长上下文挤压专家缓存时，前者的活跃权重集合会膨胀；路由器对量化误差敏感时，后者的对齐开销与路由漂移可能反超收益。需要在同一轨迹上比较缓存命中率、影子模型推理开销和端到端每输出词元时间。

**2. 键值复用：完整复用、选择性重算还是离线蒸馏？** [[CacheBlend-EuroSys25|CacheBlend]] 假设只需重算少于 15% 词元的键值状态，即可补偿缺失的跨文本块注意力；[[Cartridges-ICLR26|Cartridges]] 假设梯度下降生成的紧凑键值状态可以完全替代预填充；[[PASTA-ICLR24|PASTA]] 则只在推理后重新加权注意力。**脆弱点**：文本块彼此独立时可以完整复用；需要强跨块推理时，选择性重算更有必要；对于窄领域抽取任务，训练这种紧凑键值表示可能不如 [[RAG]] 便宜。需要按任务类型分别衡量首个词元时间、质量和离线成本。

**3. 混合专家负载均衡：复制专家、分页权重还是远端近数据计算？** [[Libra-ICLR26|Libra]] 与 [[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 假设复制或搬运专家是主要代价；[[FluxMoE-arXiv26|FluxMoE]] 假设对权重分页即可；[[ContextAwareMoE-CXLNDP-arXiv25|ContextAwareMoE-CXLNDP]] 假设冷专家应在远端就地计算，而不是搬回 GPU。**脆弱点**：网络带宽、CXL 延迟、GPU 算力与专家大小之间的比例决定最优策略；没有单一方案能在所有混合专家规模和硬件上占优。

**4. 长上下文：训练原生稀疏模型还是使用运行时键值中间件？** [[NSA-ACL25|NSA]] 与 [[MSA-arXiv26|MSA]] 假设应修改注意力算子和训练目标；[[LMCache-arXiv25|LMCache]] 与 [[IceCache-arXiv26|IceCache]] 假设不改模型，仅在系统层复用或压缩即可。**脆弱点**：上下文较短或键值状态已被其他机制压缩时，NSA 的收益会下降；MSA 在“大海捞针”任务上的高分不一定代表综合推理稳定；系统层方案尚未验证推理模型超长思维链（chain of thought，CoT）的静默正确性，这也关联 [[LLMSteer-NeurIPSW24|LLMSteer]] 调整缓存的风险。

**5. 前缀缓存兼容性与质量增益：调整键值状态能否保持语义？** [[LLMSteer-NeurIPSW24|LLMSteer]] 假设与查询无关的调整可以安全复用；[[PASTA-ICLR24|PASTA]] 的查询相关调整不兼容前缀缓存，但质量更高。**脆弱点**：被修改的键值缓存是否会产生与原始预填充不一致的输出，目前缺少系统级一致性测试；在频繁淘汰缓存的多租户部署中，LLMSteer 的离线重读成本会重新显现。

**6. 智能体可读性：显式扁平代码还是可复用抽象？** [[PithTrain-arXiv26]] 通过自包含模型文件和直接调用降低单模型功能集成成本；[[SkVM-SOSP26]] 则让编译器和运行时适配既有技能，而不要求重写目标软件。**脆弱点**：PithTrain 未评测修改在不同模型间传播，SkVM 未评测大型训练框架的原生执行与调试路径；需要在同一组局部修改、跨模型修改和版本升级任务上比较一次性智能体投入、重复代码与回归缺陷。

## 值得关注的方向

### 1. 解码阶段与多节点混合专家负载均衡

**为什么小团队能做**：这是算法与系统协同问题，用 1–2 张 GPU 和开源混合专家模型即可验证。

**指向空白的论文**：[[Libra-ICLR26|Libra]] 只优化预填充；[[LatencyOptimal-MoELB-INET4AI25|INET4AI]] 只在单节点评估；[[OD-MoE-arXiv25|OD-MoE]] 的无缓存路线尚未与负载均衡联合优化。

**具体待解决问题**：解码阶段单词元批次下专家未命中的代价与预填充阶段有何不同；跨节点负载均衡如何联合优化网络带宽与 GPU 算力；请求级与词元级负载均衡如何保证公平性。

### 2. 算法与系统协同的键值缓存和稀疏注意力设计

**为什么小团队能做**：[[MSA-arXiv26|MSA]] 证明，40 亿参数的骨干模型和 1580 亿词元预训练可由单节点 8 张 A100 承担。

**指向空白的论文**：[[MSA-arXiv26|MSA]]、[[AttnRes-arXiv26|AttnRes]]、[[NSA-ACL25|NSA]] 三条路线尚未在同一推理服务栈上对照。

**具体待解决问题**：路由键投影器的训练成本能否降到 80 亿参数模型加低秩适配（low-rank adaptation，LoRA）；块稀疏能否反向应用到序列维度；与[[Speculative-Decoding|推测解码]]组合时是否稳定。

### 3. 统一键值缓存的可编辑流程

**为什么小团队能做**：PASTA 和 LLMSteer 不需要训练；Cartridges 冻结大语言模型，只训练前缀的键值状态，单卡即可运行。

**指向空白的论文**：[[PASTA-ICLR24|PASTA]]、[[LLMSteer-NeurIPSW24|LLMSteer]]、[[Cartridges-ICLR26|Cartridges]] 未与 [[PagedAttention]] 生产系统深度集成。

**具体待解决问题**：如何根据工作负载在性能分析、状态调整和蒸馏之间自动选策略；如何压缩推理模型超长思维链的紧凑键值表示；如何为状态调整建立静默正确性一致测试。

### 4. 查询与层级感知键值策略的轻量校准

**为什么小团队能做**：[[MoE-nD-arXiv26|MoE-nD]] 的离线敏感度表与 [[IceCache-arXiv26|IceCache]] 的动态聚类索引（DCI-tree）都可在单卡上标定。

**指向空白的论文**：两者优化维度正交但尚未组合；[[LMCache-arXiv25|LMCache]] 的多层存储仍采用全局策略。

**具体待解决问题**：如何联合布局逐层敏感度与语义缓存页；校准提示长度如何影响不同调节轴之间的偏好估计稳定性；如何兼容预填充与解码解聚的传输格式。

### 5. 面向智能体的机器学习系统可扩展评测

**为什么小团队能做**：可从开源训练框架、单节点冒烟工作负载和公开编程智能体起步，不需要训练前沿模型；主要成本是构造可执行任务、版本化环境与人工复核。

**指向空白的论文**：[[PithTrain-arXiv26]] 固定使用单一智能体，且任务偏向局部修改；[[SkVM-SOSP26]] 覆盖技能可移植性和短任务，却没有跨小时状态与恢复实验。

**具体待解决问题**：按依赖深度、受影响模型数和上下文压缩次数对 ATE-Bench 分层；跨 3 种智能体与评测脚手架检验框架排名；注入内存耗尽、进程重启、损坏检查点与过期技能，联合报告成功率、最佳状态保持率、智能体交互轮数、GPU 时间和回归缺陷。
