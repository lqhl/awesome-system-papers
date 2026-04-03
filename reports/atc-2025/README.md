# USENIX Annual Technical Conference (ATC) 2025 论文概览

> 共 100 篇论文 | 生成日期: 2026-04-03

---

## 论文分类索引

### LLM 推理与服务（10 篇）

#### [[atc2025-gao|WEAVER: Efficient Multi-LLM Serving with Attention Offloading]]
- **作者**：Shiwei Gao et al.
- **要解决的问题**：多 LLM 服务平台中冷模型 GPU 内存严重浪费（利用率 43%），热模型 batch size 受限于单 GPU KV cache 容量
- **核心贡献**：提出 workload weaving，将热模型部分 attention 计算 offload 到冷模型 GPU 上，热模型吞吐最高提升 77%
- **关键发现/观点**：Attention 操作是非参数化的，只需传输最新 token 的 QKV tensor（数据量极小）就能在远程 GPU 执行，因此可以以极低通信开销借用冷模型空闲 GPU 的内存存储 KV cache 来扩大 batch size

#### [[atc2025-hu-junhao|DeepServe: Serverless Large Language Model Serving at Scale]]
- **作者**：Junhao Hu et al.
- **要解决的问题**：华为云 Ascend NPU 集群上的大规模 LLM 服务面临异构工作负载管理、PD 调度策略选择和大模型冷启动延迟三大挑战
- **核心贡献**：设计 Request-Job-Task 三层 serverless 抽象 + FlowServe 引擎 + 三层递进调度 + 秒级 NPU-fork 扩容，已在生产部署超一年
- **关键发现/观点**：PD-disaggregated 实例更适合长 prefill + 短 decode 请求，PD-colocated 适合短 prefill + 长 decode 请求，这一优势区间随 RPS 变化稳定，可通过离线 profiling heatmap 指导在线调度

#### [[atc2025-wang-jiahao|KVCache Cache in the Wild: Characterizing and Optimizing KVCache Cache at a Large Cloud Provider]]
- **作者**：Jiahao Wang et al.
- **要解决的问题**：缺乏对真实生产环境 KV Cache 复用特征的系统性刻画，现有系统普遍使用 workload-agnostic 驱逐策略
- **核心贡献**：基于阿里云真实 trace 刻画 KV Cache 复用特征，提出 workload-aware 缓存驱逐策略，命中率提升 1.5%–3.9%，QTTFT 降低最高 41.4%
- **关键发现/观点**：特定请求类别（请求类型 + 对话轮次）的 KV Cache 复用时间遵循可预测的指数分布，且该分布在相似流量模式下保持稳定，可用历史数据拟合来精确估计复用概率

#### [[atc2025-li-suyi-katz|KATZ: Efficient Workflow Serving for Diffusion Models with Many Adapters]]
- **作者**：Suyi Li et al.
- **要解决的问题**：T2I 扩散模型工作流中大量 adapter（ControlNet/LoRA）引入显著延迟开销，adapter 加载平均占端到端延迟 37%
- **核心贡献**：将 ControlNet 解耦为独立可扩展服务，利用 LoRA 在 denoising 初期无效的特性实现异步加载，3C/2L 配置下实现 7.8× 延迟降低
- **关键发现/观点**：LoRA 在 denoising 初期 semantics-planning 阶段几乎无效（cosine similarity > 0.99），可安全异步加载而不影响生成质量

#### [[atc2025-li-suyi-toppings|TOPPINGS: CPU-Assisted, Rank-Aware Adapter Serving for LLM Inference]]
- **作者**：Suyi Li et al.
- **要解决的问题**：多租户 LLM LoRA 服务中 adapter 加载中断 decoding 的累积开销平均占请求服务时间 29%，不同 rank 的异构性导致 batch 内延迟增加 28%
- **核心贡献**：利用闲置 CPU 在 adapter 加载期间提前执行 LoRA 计算 + rank-aware 调度器，请求延迟降低最高 1.7×，SLO 达成率 99%
- **关键发现/观点**：LoRA 计算极其轻量（约 1 GFLOPs），可在 CPU 上执行，而推理集群 CPU 大量闲置（75% 节点 < 10% 利用率），利用闲置 CPU 预执行 LoRA 可将 cold-start 加载延迟从关键路径上隐藏

#### [[atc2025-zhang-qihao|QFactory: Accelerating Quantized Large Language Model Serving with Qtile Graphs]]
- **作者**：Qihao Zhang et al.
- **要解决的问题**：细粒度量化算法引入的 dequantization 操作成为 LLM 解码推理新瓶颈，现有编译器对量化 kernel 支持效率不足
- **核心贡献**：提出 Qtile 抽象将量化信息编码为张量注解，实现 dequantization 的延迟执行和图级灵活放置，H100 上 kernel 级平均加速 1.66×
- **关键发现/观点**：Dequantization 不必在遇到量化张量时立即执行，而是可以作为注解沿计算图向后传播，在最有利的位置再执行，从而开辟更大的图级优化空间

#### [[atc2025-wang-yaoyu|GeneralSparse: Bridging the Gap in SpMM for Pruned Large Language Model Inference on GPUs]]
- **作者**：Yaoyu Wang et al.
- **要解决的问题**：现有 GPU SpMM 方案对不同剪枝方法产生的稀疏模式和不同稀疏率适配性差，缺乏自动化代码生成能力
- **核心贡献**：将 SpMM 优化分解为 memory access space 和 reduction space 两个正交空间，通过 cost model 驱动的离线搜索实现通用高效的剪枝 LLM 推理加速，相比 cuSPARSE 最高加速 20.82×
- **关键发现/观点**：GPU SpMM 的并行内存访问策略可抽象为"分盒子"过程，不同稀疏率需要不同归约算法组合，两者可分别建模为独立空间用 cost model 搜索最优组合

#### [[atc2025-yu|Torpor: GPU-Enabled Serverless Computing for Low-Latency, Resource-Efficient Inference]]
- **作者**：Minchen Yu et al.
- **要解决的问题**：Serverless 推理中 85% 的函数低频访问，early binding 导致 GPU 资源大量空闲浪费，频繁回收 GPU 资源又引入数十秒冷启动延迟
- **核心贡献**：提出 late binding——将空闲模型保持在主机内存，请求到达时动态 swap 到 GPU 池执行，已在阿里云部署实现用户成本降低 70%、平台 GPU 节省 65%
- **关键发现/观点**：主机内存容量远大于 GPU 内存（TB vs 数十 GB）且成本更低，可作为空闲模型的理想存储位置；通过 late binding 可同时实现按使用付费、高利用率和快速恢复

#### [[atc2025-tian|CLONE: Customizing LLMs for Efficient Latency-Aware Inference at the Edge]]
- **作者**：Chunlin Tian et al.
- **要解决的问题**：边缘设备（4-12GB RAM）部署 LLM 面临严格的内存、计算和能耗约束，现有压缩和调频方法各自独立优化
- **核心贡献**：算法-硬件协同设计：离线自动搜索逐层剪枝配置 + 在线 MoE router 动态融合 LoRA adapter + DQN-based token 级 DVFS，最高 11.92× 推理加速
- **关键发现/观点**：LLM decoder 层结构同质但对精度/延迟/能耗的贡献高度异构——前端层负责特征提取，后端层负责输出生成，中间层贡献最小；利用层间异构性做差异化剪枝和调频可显著优于均匀策略

#### [[atc2025-zheng|SAVE: Software-Implemented Fault Tolerance for Model Inference against GPU Memory Bit Flips]]
- **作者**：Wenxin Zheng et al.
- **要解决的问题**：边缘场景 GPU 内存 bit flip 可导致模型精度下降超 60%，现有方案要么需重训模型要么代价过高（TMR 需 3× 冗余）
- **核心贡献**：将计算值的每个 bit 分类为 robust/ranging/vulnerable 三类，选择性保护 vulnerable bit，在 <9% 延迟开销下抵御 4K bit flip
- **关键发现/观点**：由于非线性激活函数的存在，并非所有 bit 同等重要——大量 bit 翻转对推理结果影响极小（robust bits），只需重点保护少量 vulnerable bits 即可大幅降低保护代价

### 大模型训练与微调（12 篇）

#### [[atc2025-chen-tiancheng|CrossPipe: Towards Optimal Pipeline Schedules for Cross-Datacenter Training]]
- **作者**：Tiancheng Chen et al.
- **要解决的问题**：现有 pipeline parallelism 调度假设通信开销可忽略，直接用于跨数据中心训练时跨 DC 通信在关键路径上被放大 O(n_mb) 倍
- **核心贡献**：建立延迟-带宽感知的性能模型，将 pipeline scheduling 建模为约束优化，设计 solver-based 最优调度，跨 DC 训练时间降低最高 33.6%
- **关键发现/观点**：静态调度的关键路径上跨 DC 通信次数与 microbatch 数量成线性关系；通过动态重排 pipeline block 执行顺序可将跨 DC 通信从关键路径上移除

#### [[atc2025-feng|Optimus: Accelerating Large-Scale Multi-Modal LLM Training by Bubble Exploitation]]
- **作者**：Weiqi Feng et al.
- **要解决的问题**：MLLM 训练中 encoder 与 LLM backbone 异构性导致 pipeline 不平衡，超过 48% 的 GPU 周期空闲
- **核心贡献**：为 encoder 和 LLM 分别制定独立 3D 并行计划并共置在所有 GPU 上，将 encoder 计算填充到 LLM 的 bubble 中，3072 GPU 训练实现 20-21% 加速
- **关键发现/观点**：MLLM 训练中约 90% 的 bubble 在 LLM 阶段，而 encoder 计算量远小于 LLM；通过共置让所有 GPU 在 LLM bubble 期间执行 encoder 计算，从而消化空闲时间

#### [[atc2025-huang-kezhao|mTuner: Accelerating Parameter-Efficient Fine-Tuning on Multi-GPU Servers with Elastic Tensor]]
- **作者**：Kezhao Huang et al.
- **要解决的问题**：多 GPU PEFT 微调中静态内存调度无法利用 runtime tensor 的 peak-valley 波动，TP 中通信资源在计算阶段空闲
- **核心贡献**：提出 Elastic Tensor 抽象，在 valley 阶段渐进缓存冻结权重减少通信，在 peak 阶段释放扩大 batch size，PCIe 服务器上平均加速 28.3%
- **关键发现/观点**：PEFT 中大量冻结参数可作为"弹性缓冲"——在内存 valley 阶段缓存更多冻结权重以减少后续通信，在 peak 阶段丢弃以释放内存，静态权重和动态激活之间存在可交换性

#### [[atc2025-huang-yuzhou|Obscura: Concealing Recomputation Overhead in Training of Large Language Models with Bubble-filling Pipeline Transformation]]
- **作者**：Yuzhou Huang et al.
- **要解决的问题**：Pipeline 训练中 1F1B 调度存在大量 forward bubble 完全未利用，全 stage recomputation 引入约 33% 额外执行时间
- **核心贡献**：通过 pipeline 变换将 forward bubble 转化为 backward bubble，将 recomputation 开销隐藏在 bubble 中，相比全 recomputation 最高加速 1.33×
- **关键发现/观点**：1F1B pipeline 中 forward bubble 完全空置而 backward bubble 可隐藏 recomputation；通过将 adjusted stage 的 forward pass 前移到 warmup phase，可将 forward bubble 转化为 backward bubble

#### [[atc2025-he-yongjun|LLMStation: Resource Multiplexing in Tuning and Serving Large Language Models]]
- **作者**：Yongjun He et al.
- **要解决的问题**：LLM decoding 阶段 GPU 计算利用率极低（<10%），而 PEFT 微调与推理竞争同一 GPU 资源
- **核心贡献**：提出迭代级混合复用，通过 C++ stackless coroutine 实现可挂起的 Autograd 引擎、Fusion Engine 将 PEFT forward 与 decoding 批量融合，PEFT 吞吐提升 1.38–14.77×
- **关键发现/观点**：Decoding 阶段是 memory-bound（MFU<5%），PEFT forward/backward 是 compute-bound，二者具有互补的资源使用模式，可在迭代级别并行执行实现双赢

#### [[atc2025-wang-tuowei|JENGA: Enhancing LLM Long-Context Fine-tuning with Contextual Token Sparsity]]
- **作者**：Tuowei Wang et al.
- **要解决的问题**：LLM 长上下文 fine-tuning 中 activation memory 随序列长度线性增长，现有方法均无法有效减少 activation memory
- **核心贡献**：首次将 token 级别稀疏化引入 LLM 长上下文 fine-tuning，直接消除冗余 token 减少 activation memory，实现最高 1.93× 内存节省
- **关键发现/观点**：自然语言在长上下文场景中存在显著 token 冗余，且具有输入依赖性——哪些 token 重要取决于具体输入和具体层，且随序列长度增加稀疏比例更高（16K 时约 70%）

#### [[atc2025-lian|UCP: Universal Checkpointing for Large-Scale DNN Training with Reconfigurable Parallelism]]
- **作者**：Xinyu Lian et al.
- **要解决的问题**：大规模 LLM 训练的 checkpoint 与特定并行策略强耦合，无法在 DP/TP/PP/ZeRO 等策略之间自动转换
- **核心贡献**：引入与并行策略解耦的 atomic checkpoint 和基于 7 种 tensor 分片 pattern 的自动化重配置 pipeline，1T 参数模型约 4 分钟完成重配置
- **关键发现/观点**：所有主流并行策略对模型参数的处理方式可归纳为少数几种 tensor 分片 pattern，将 checkpoint 归一化到参数级别后任意策略间的转换可通过 pattern 匹配自动完成

#### [[atc2025-zhao-hairui|FlexPipe: Maximizing Training Efficiency for Transformer-based Models with Variable-Length Inputs]]
- **作者**：Hairui Zhao et al.
- **要解决的问题**：变长输入训练中不同迭代计算量和内存波动剧烈（平均计算吞吐仅 55%），静态 PP 分区导致大量 GPU 冗余
- **核心贡献**：提出 TwinLayer 机制实现低开销在线 PP 阶段调整（stall 仅 0.79s），配合 HBSA 算法决定调整时机，相比 SOTA 平均提升 1.25× 吞吐
- **关键发现/观点**：变长训练中"冗余"GPU（按最大长度分配但当前迭代不需要）可通过动态收缩 PP 阶段数来释放，转用于增加 DP 度

#### [[atc2025-zhang-junyi|PopFetcher: Towards Accelerated Mixture-of-Experts Training Via Popularity Based Expert-Wise Prefetch]]
- **作者**：Junyi Zhang et al.
- **要解决的问题**：MoE 训练中每层两次同步 All-to-All 通信占训练时间 56%–58%，是主要瓶颈
- **核心贡献**：利用 expert 选择的时序稳定性和跨层相关性，在 Attention 层期间异步预取下一层热门 expert，训练时间缩减 15%–94.5%
- **关键发现/观点**：MoE expert 选择分布具有显著时序局部性（sliding window 预测准确率约 70–77%）和跨层条件概率相关性，可在空闲网络链路上提前预取

#### [[atc2025-wu-tianyuan|GREYHOUND: Hunting Fail-Slows in Hybrid-Parallel Training at Scale]]
- **作者**：Tianyuan Wu et al.
- **要解决的问题**：大规模模型训练中 fail-slow（组件性能退化而非崩溃）问题缺乏系统性研究，现有 checkpoint-and-restart 代价过高
- **核心贡献**：三阶段非侵入式检测（精度 99%+）和基于 ski-rental 启发式的四级自适应缓解策略，256 H800 GPU 上实现 1.58× 端到端吞吐改善
- **关键发现/观点**：DP 的 gradient 同步流量远超 PP 的 activation 传输，因此可以通过在并行拓扑中交换角色——将拥塞链路从重流量 DP 组移至轻流量 PP 组——来缓解通信 fail-slow

#### [[atc2025-zhou|Hermes: Accelerating Model Training on Ascend Chips]]
- **作者**：Yuhang Zhou et al.
- **要解决的问题**：Ascend NPU 上大模型训练存在 profiling 开销高（1.77×）、瓶颈分析碎片化、优化选择缺乏系统指导三大问题
- **核心贡献**：提出层次化端到端训练优化系统，包含粗到细 profiling、inter/intra-operator 两层瓶颈分析和原因-优化自动匹配，100B PanGu-α 上实现 3.05× 加速
- **关键发现/观点**：训练流水线天然分层（框架→并行策略→硬件算子），先分析 inter-operator 并行效率再深入 intra-operator 执行效率的层次化方法可系统性覆盖所有瓶颈，且 37% 案例的根因是常被忽视的 CPU 端瓶颈

#### [[atc2025-zhan|AssyLLM: Efficient Federated Fine-tuning of LLMs via Assembling Pre-trained Blocks]]
- **作者**：Shichen Zhan et al.
- **要解决的问题**：联邦学习微调 LLM 时显存需求极高（7B 模型全参微调需 40GB+），85% 低端边缘设备无法参与
- **核心贡献**：从多个预训练模型的 block pool 中通过前向推理评估兼容性并动态组装，完全避免反向传播，实现 92% 显存降低和最高 30× 加速
- **关键发现/观点**：预训练 LLM 可分解为模块化 transformer block，通过 CKA+KL 散度联合评估 block 间兼容性，仅用前向推理即可组装出高质量模型——绕过了反向传播带来的显存瓶颈

### GPU 资源管理与调度（5 篇）

#### [[atc2025-wang-jiali|SIRIUS: Colocating ML Inference and Training with Fast GPU Memory Handover]]
- **作者**：Jiali Wang et al.
- **要解决的问题**：推理与训练混部时，现有方案无法在毫秒级时间尺度内完成显存移交，导致推理 SLO 严重违约或 GPU 利用率极低
- **核心贡献**：通过即时训练 batch 丢弃（<5ms）、安全显存所有权移交机制和 SLO 感知粗粒度再分配，实现推理与训练的高效 GPU 显存共享
- **关键发现/观点**：训练 batch 执行分为梯度计算（占 95%+ 时间但不修改参数）和模型更新（短暂但需原子执行）两个阶段；GC 阶段可安全丢弃当前 batch 立即释放显存

#### [[atc2025-fan|GPREEMPT: GPU Preemptive Scheduling Made General and Efficient]]
- **作者**：Ruwen Fan et al.
- **要解决的问题**：GPU 抢占调度中 wait-based 方案延迟高（5ms），reset-based 方案只适用于幂等 kernel
- **核心贡献**：发现 NVIDIA 开源驱动中未文档化的硬件时间片分配机制，将 BE 任务时间片设为 ~200µs 实现通用 context-switch 抢占，A100 上平均抢占延迟 < 40µs
- **关键发现/观点**：GPU 驱动中存在未公开的硬件时间片分配机制——将 BE 任务时间片缩短至极短可迫使其主动让出 GPU 资源，实现无需修改 kernel 的通用 yield 原语

#### [[atc2025-zhang-shulai|KRYPTON: Efficient Performance-Aware GPU Sharing with Compatibility and Isolation through Kernel Space Interception]]
- **作者**：Shulai Zhang et al.
- **要解决的问题**：现有 GPU 共享方案（API-remoting、MPS、MIG）在兼容性、隔离性、性能保障三方面无法同时满足
- **核心贡献**：在内核态拦截 GPU command buffer 和 ioctl，天然支持跨运行时（CUDA+Vulkan）兼容性和故障隔离，GPU 需求减少 32.1%
- **关键发现/观点**：所有 GPU 运行时最终都通过 UMD 将命令写入 command buffer，在内核态拦截该接口可绕过对不同用户态 API 的适配；时间和空间两个维度联合调整比单一维度可显著减少 GPU 碎片

#### [[atc2025-wang-yuke|GMI-DRL: Empowering Multi-GPU DRL with Adaptive-Grained Parallelism]]
- **作者**：Yuke Wang et al.
- **要解决的问题**：深度强化学习在多 GPU 上训练时 GPU 利用率仅约 18%，DRL 三个异构组件的计算特性差异巨大
- **核心贡献**：将 GPU 拆分为大小可调的 sub-GPU 单元（GMI），配合 task-aware 映射和 collective composition 通信优化，DGX-A100 上最高 2.34× 训练吞吐提升
- **关键发现/观点**：与其将计算适配到固定硬件资源，不如将硬件资源适配到计算需求——通过 GPU Multiplexing Instance 将大 GPU 按需拆分，为 DRL 异构任务分别分配合适的资源量

#### [[atc2025-kong|PPipe: Efficient Video Analytics Serving on Heterogeneous GPU Clusters via Pool-Based Pipeline Parallelism]]
- **作者**：Z. Jonny Kong et al.
- **要解决的问题**：异构 GPU 集群中低端 GPU 因整体推理延迟超 SLO 而无法使用（仅 8.1% 利用率）
- **核心贡献**：提出 pool-based pipeline parallelism，每个 partition 关联一个同类 GPU pool，低端 GPU 利用率从 8.1% 提升至 73.6%，吞吐提升最高 75.1%
- **关键发现/观点**：同一 DNN 模型不同层在不同 GPU 上的延迟比差异显著，通过让每种 GPU 运行它相对最擅长的层，可在最小化延迟膨胀的同时充分利用低端 GPU 资源

### 推荐系统与向量检索（6 篇）

#### [[atc2025-he-jiaao|HypeReca: Distributed Heterogeneous In-Memory Embedding Database for Training Recommender Models]]
- **作者**：Jiaao He et al.
- **要解决的问题**：DLRM 分布式训练中 embedding table 的 all-to-all 通信开销随 GPU 数量增加急剧上升，扩展性极差
- **核心贡献**：提出 Two-Fold Parallel Strategy（2FP），将高频 items 复制到 GPU 用数据并行、低频 items 留在 host memory 用模型并行，32 GPU 上实现 2.16–16.8× 加速
- **关键发现/观点**：Embedding 访问分布极度倾斜（2.2% items 覆盖 90% 访问），将热门 items 复制到每个 GPU 可削减高达 90% 的 all-to-all 通信量

#### [[atc2025-shan-jixi|Primus: Unified Training System for Large-Scale Deep Learning Recommendation Models]]
- **作者**：Jixi Shan et al.
- **要解决的问题**：字节跳动大规模 DLRM 训练面临跨 YARN/K8s 异构资源管理、TB 级多源数据编排和在线训练灾难性遗忘三大挑战
- **核心贡献**：统一资源调度 + DTGG 数据编排（加速 23×）+ MTRM 混合训练范式（memory tower 防遗忘），资源节省 17.1%、广告收入提升 0.4%-2.4%
- **关键发现/观点**：Batch 数据（历史离线）和 stream 数据（实时在线）在 DLRM 训练中承担本质不同的角色，通过在模型架构层面分离两者的学习路径可同时保留历史知识和捕捉最新趋势

#### [[atc2025-jha|HyCache: Hybrid Caching for Accelerating DNN Input Preprocessing Pipelines]]
- **作者**：Keshav Vinayak Jha et al.
- **要解决的问题**：DNN 训练的 CPU 端预处理流水线延迟可占 epoch 时间 65%，现有缓存方案存在"全有或全无"限制
- **核心贡献**：通过 partial caching、exclusive caching 和 ILP 驱动的 tier-aware caching，预处理吞吐最高提升 5.3×，端到端训练加速最高 1.67×
- **关键发现/观点**：预处理流水线不同步骤的输出大小和计算成本差异显著，内存和存储的访问延迟差异意味着同一步骤在不同存储层的缓存收益完全不同

#### [[atc2025-gan|SNARY: A High-Performance and Generic SmartNIC-accelerated Retrieval System]]
- **作者**：Qiaoyin Gan et al.
- **要解决的问题**：工业级 EBR 检索延迟随语料库规模线性增长，GPU 在 Top-K 阶段消耗 80% 延迟且最大 recall count 仅 1024
- **核心贡献**：基于 FPGA 的 HBM 存储 + 并行 Top-K + LSH 预过滤，比 Faiss（4× A100）延迟降低 79-87%、吞吐提升 14-24×
- **关键发现/观点**：检索延迟主要由语料库读取时间决定（L = M/B + C），直接通过 LSH 分桶缩减语料库规模 M 比在相似度计算环节做模糊化更有效

#### [[atc2025-kim|PathWeaver: A High-Throughput Multi-GPU System for Graph-Based Approximate Nearest Neighbor Search]]
- **作者**：Sukjin Kim et al.
- **要解决的问题**：大规模 ANNS 的多 GPU 扩展效率极低（4 GPU 仅 35–43% 效率），随机初始搜索点大量浪费且超过 80% 的距离计算无效
- **核心贡献**：流水线跨分片路径扩展 + 幽灵阶段 + sign bit XOR 预过滤，95% recall 下 4 GPU 扩展效率 62%
- **关键发现/观点**：分布式 sharding 搜索中各分片"独立搜索"是浪费——前一分片找到的接近 query 的节点可作为下一分片的更优起点，通信量极小但可大幅减少后续分片迭代次数

#### [[atc2025-wu-puqing|Turbocharge ANNS on Real Processing-in-Memory by Enabling Fine-Grained Per-PIM-Core Scheduling]]
- **作者**：Puqing Wu et al.
- **要解决的问题**：UPMEM 商用 PIM 上运行 ANNS 时实际利用率仅达理论上限的 18.2%，超过 65% 时间 PU 空闲
- **核心贡献**：通过 Persistent PIM Kernel 和 Per-PU Query Dispatching 实现细粒度调度，PIM 利用率提升至 65-83%，成本效率是 GPU 的 4.8×
- **关键发现/观点**：UPMEM 每个 PU 拥有一个未文档化的控制接口，完全绑定 DDR 总线；利用此接口实现对每个 PU 的细粒度仲裁，可打破"CPU 和 PU 只能在 batch 边界交互"的传统假设

### 编译器与计算优化（6 篇）

#### [[atc2025-wu-ruofan|PluS: Highly Efficient and Expandable ML Compiler with Pluggable Graph Schedules]]
- **作者**：Ruofan Wu et al.
- **要解决的问题**：嵌入式 ML 编译器将图变换规则硬编码，添加新优化代价高；模板式编译器依赖精确算子组合匹配
- **核心贡献**：基于循环特征的子图抽象，使不同算子组合但相同循环结构的子图复用同一 codegen schedule，相比 TorchInductor 加速 4.04×
- **关键发现/观点**：子图的 codegen schedule 主要由关键算子（MatMul、Reduce）的循环结构决定，而非所有算子的精确组合——结构相似但某些算子不同不改变循环骨架，可共享代码生成方案

#### [[atc2025-xia|Voltrix: Sparse Matrix-Matrix Multiplication on Tensor Cores with Asynchronous and Balanced Kernel Optimization]]
- **作者**：Yaqi Xia et al.
- **要解决的问题**：Tensor Core 专为稠密矩阵乘设计，面对 SpMM 时数据加载占 kernel 时间 80%+ 且工作负载不均衡
- **核心贡献**：通过 BMat bit-wise 压缩格式、warp-specialized 流水线和 persistent I/O co-balanced kernel，首次在非结构化 SpMM 上全面超越 CUDA Core 方法
- **关键发现/观点**：SpMM 在 Tensor Core 上的核心瓶颈不在计算本身而在数据搬运——只要能充分重叠数据加载与计算并同时实现输入输出两个维度的负载均衡，就能真正释放 Tensor Core 算力

#### [[atc2025-zhang-jiajian|WIC: Hiding Producer-Consumer Synchronization Delays with Warp-Level Interrupt-based GPU Communications]]
- **作者**：Jiajian Zhang et al.
- **要解决的问题**：GPU producer-consumer 模型中 consumer 端反复 polling 占通信开销 60%–90%，且 polling 线程阻止其他 warp 有效计算
- **核心贡献**：利用 UVM page fault 机制将等待的 warp 挂起、释放计算资源，producer 数据就绪后重新激活，平均 1.13× 加速
- **关键发现/观点**：当 consumer 开始 polling 时大量线程仍在执行独立计算任务，将 polling warp 挂起释放资源让这些任务与同步延迟重叠执行

#### [[atc2025-xie|FPRev: Revealing Floating-Point Accumulation Orders in Software/Hardware Implementations]]
- **作者**：Peichen Xie et al.
- **要解决的问题**：软硬件实现普遍不公开浮点累加顺序，导致相同代码在不同系统上产生不同数值结果
- **核心贡献**：利用浮点 swamping 现象构造特殊测试输入，将指数级搜索降至多项式时间，成功揭示 NumPy、PyTorch 及 Tensor Core 的未公开累加顺序
- **关键发现/观点**：通过构造 masked all-one array，利用 swamping 现象使输出值恰好等于未被遮蔽的加数个数，该值与 summation tree 的最低公共祖先子树大小直接对应，从而能从黑盒输出推断累加顺序

#### [[atc2025-landsberg|IRHash: Efficient Multi-Language Compiler Caching by IR-Level Hashing]]
- **作者**：Tobias Landsberg et al.
- **要解决的问题**：现有编译缓存（Ccache）对注释、空白等表面变化敏感导致 false miss，AST 级方案仅支持 C 语言且实现复杂
- **核心贡献**：在 LLVM IR 生成后、优化前进行哈希计算，以 561 行 C++ 实现跨 C/C++/Fortran/Haskell 编译缓存，准确率 99.87%，平均减少 19% 构建时间
- **关键发现/观点**：IR 能消除大量语法糖并通过常量折叠归一化语义等价代码，是准确率、节省潜力、跨语言通用性三者最优平衡点

#### [[atc2025-yin|HEC: Equivalence Verification Checking for Code Transformation via Equality Saturation]]
- **作者**：Jiaqi Yin et al.
- **要解决的问题**：现有编译器等价性验证工具碎片化，无法统一覆盖控制流变换和数据通路变换
- **核心贡献**：将静态数据通路规则与运行时动态生成的控制流重写规则混合，基于 e-graph equality saturation 实现 MLIR 等价性验证
- **关键发现/观点**：控制流变换的参数虽在编译前未知，但可从图表示中提取并动态生成对应规则——将两类规则统一在 e-graph 框架中即可实现全面验证

### 数据中心网络（10 篇）

#### [[atc2025-hu-jinbin|FLB: Fine-grained Load Balancing for Lossless Datacenter Networks]]
- **作者**：Jinbin Hu et al.
- **要解决的问题**：现有负载均衡方案在 PFC-enabled 无损 RDMA 网络中存在重路由困难、HoL blocking 扩散和 PFC 频繁触发三大问题
- **核心贡献**：在 P4 可编程交换机上实现无阈值 packet 粒度重路由 + 拥塞流隔离双模式负载均衡，PFC PAUSE 率降低 96%
- **关键发现/观点**：PFC 无损网络中拥塞流和非拥塞流需区别对待——拥塞流应聚合隔离到最少路径限制 PAUSE 扩散，非拥塞流自由利用多路径最大化利用率

#### [[atc2025-huang-hongjing|SwCC: Software-Programmable and Per-Packet Congestion Control in RDMA Engine]]
- **作者**：Hongjing Huang et al.
- **要解决的问题**：现有 RDMA 拥塞控制无法同时满足低控制环路延迟、高灵活性和高可编程性
- **核心贡献**：在 FPGA SmartNIC 中集成 RISC-V 核实现软件可编程 per-packet CCA，~3.1μs 控制环路延迟，100-160 行 C 代码即可实现主流 CCA
- **关键发现/观点**：NIC 上 CCA 的数据访问模式高度可预测——收到包后只访问该 QP 的上下文，用 QPN 作为 hint 在 RX 流水线处理期间提前预取可完全隐藏 DRAM 访问延迟

#### [[atc2025-peng-yajuan|Barre: Empowering Simplified and Versatile Programmable Congestion Control in High-Speed AI Clusters]]
- **作者**：Yajuan Peng et al.
- **要解决的问题**：AI 集群中 DCQCN 在 400 Gbps 和 AlltoAll 混合流量下参数调优困难、拥塞响应迟缓
- **核心贡献**：基于 BlueField-3 SmartNIC 通过 Fast Increase、Dual-lock、Inflight Monitor 三个解耦组件实现零 PFC 触发，NCCL AlltoAll 延迟降低 55.89%
- **关键发现/观点**：BlueField-3 的 CNP 响应间隔已达 1μs 级别，"小幅度、高频率"的 per-CNP 速率调整成为可能；以实时 RTT 动态调整速率增加间隔可更精准响应网络状态

#### [[atc2025-yang-yifan|TGW: Operating an Efficient and Resilient Cloud Gateway at Scale]]
- **作者**：Yifan Yang et al.
- **要解决的问题**：大规模公有云网关需同时应对高效转发（数十 Tbps）、可扩展状态管理（100M+ 连接）和快速故障恢复
- **核心贡献**：将 EIP 和 CLB 解耦为不同实例类型，配合无锁状态迁移和多层容错，单节点 2.9× 吞吐提升，多年 100% 可用性
- **关键发现/观点**：EIP（无状态）适合 RTC 模型，CLB（有状态）适合两阶段流水线模型——在转发平面层面解耦可针对各自特性实现最大化性能

#### [[atc2025-zhang-xu|DRack: A CXL-Disaggregated Rack Architecture to Boost Inter-Rack Communication]]
- **作者**：Xu Zhang et al.
- **要解决的问题**：数据中心 87% 的网络流量跨机架传输，但 NIC 出口带宽不足、核心网络过度订阅
- **核心贡献**：基于 CXL 3.0 将机架内 NIC 和内存解耦形成共享池，闲置 NIC 可被借用加速跨机架通信，通信时间平均降低 37.3%
- **关键发现/观点**：超过 90% 的主机在任意 1 秒内未进行收发操作，机架内存在大量闲置 NIC 带宽；将 NIC 池化让这些带宽可被通信密集型主机借用

#### [[atc2025-yuan|Internet Connection Splitting: What's Old is New Again]]
- **作者**：Gina Yuan et al.
- **要解决的问题**：BBR 和 QUIC 是否让传统 TCP 连接拆分 PEP 过时？这一假设尚无系统性验证
- **核心贡献**：发现 BBR 从 v1 到 v2/v3 显著增加了对丢包的敏感性，连接拆分对 BBRv2/v3 重新有益，提出 split throughput heuristic 方法论
- **关键发现/观点**：BBR 为了与 CUBIC 公平竞争在 v2/v3 中主动增加了丢包惩罚，使其重新变得像基于丢包的 CCA，能够从连接拆分的短反馈环中受益

#### [[atc2025-liao|Pallas: Towards Optimal Rack-scale µs-level CPU Scheduling through In-Network Workload Shaping]]
- **作者**：Xudong Liao et al.
- **要解决的问题**：Rack-scale µs 级 CPU 调度中混合长短请求的负载均衡和 HoL blocking 是核心难题
- **核心贡献**：通过 ToR 可编程交换机将混合工作负载主动分组为同质工作负载，P99 延迟降低最高 16×
- **关键发现/观点**：调度同质工作负载远比调度混合工作负载容易——当所有请求执行时间均匀时简单 FCFS 即可达到 tail-optimal；将异质负载变为同质负载应在网络层完成

#### [[atc2025-li-zhaoyi|SwitchGNN: Accelerating Distributed Graph Learning by Using Collaborative In-Network Multicast and Aggregation]]
- **作者**：Zhaoyi Li et al.
- **要解决的问题**：分布式全图 GNN 训练中跨 worker 图传播通信产生大量冗余流量，通信开销可占 epoch 时间 80%
- **核心贡献**：利用可编程交换机卸载 multicast/aggregation，通过 graph-aware multicast reordering 和 multi-level graph partitioning，128 worker 下 epoch time 减少最高 74%
- **关键发现/观点**：GNN 图数据的度数分布高度偏斜（20% 顶点占 80% 邻居），优先发送高度数顶点可平滑聚合流水线、避免突发队列积压

#### [[atc2025-awamoto|Opening Up Kernel-Bypass TCP Stacks]]
- **作者**：Shinichi Awamoto et al.
- **要解决的问题**：现有 kernel-bypass TCP 协议栈从未在统一硬件和统一应用下进行公平的全面对比
- **核心贡献**：构建统一测量框架 nophttpd，在 bulk transfer、小消息延迟、高并发连接、多核扩展性四个维度对比 6 个协议栈并开源 stackbench
- **关键发现/观点**：没有任何一个协议栈能在所有四个维度同时表现优异——架构设计决策（线程模型、执行模型）决定了根本性 trade-off

#### [[atc2025-wan|NetKeeper: Enhancing Network Resilience with Autonomous Network Configuration Update]]
- **作者**：Zhaoyang Wan et al.
- **要解决的问题**：企业网络运维中手动配置更新耗时易错，现有工具无法同时处理多模态意图且缺乏流量感知优化
- **核心贡献**：通过 LLM+DSL 统一处理多模态意图，并用多智能体 DRL 同时优化策略一致性、负载均衡和流量迁移
- **关键发现/观点**：网络配置更新是多目标优化问题；将不同配置参数分配给专门 agent 分解解空间，利用 DRL 在线学习适应动态网络

### 广域网、移动网络与流媒体（7 篇）

#### [[atc2025-basak|LEOCraft: Towards Designing Performant LEO Networks]]
- **作者**：Suvam Basak et al.
- **要解决的问题**：现有 LEO 卫星星座模拟工具无法扩展到数万颗卫星，六维设计参数空间暴力搜索面临维度灾难
- **核心贡献**：开源框架 LEOCraft，利用领域知识将六维搜索空间缩减为三维，支持 83K 颗卫星的大规模仿真，比 Hypatia 快最高 54.5×
- **关键发现/观点**：六个设计参数中高度/倾角/仰角影响覆盖率，而轨道数/每轨卫星数/相位偏移不影响——当 o >> n 且 p=0.5 时吞吐最优

#### [[atc2025-hu-liekun|STORM: a Multipath QUIC Scheduler for Quick Streaming Media Transport under Unstable Mobile Networks]]
- **作者**：Liekun Hu et al.
- **要解决的问题**：移动场景中 MPQUIC 因无法及时感知无线信号突变而导致尾延迟急剧上升
- **核心贡献**：通过信号水位线机制（SWM）实时感知链路质量 + 双队列区分可靠/不可靠数据调度，p99 延迟降低 98.2%
- **关键发现/观点**：E2E 延迟瓶颈在"最后一英里"无线链路（极端情况下占 RTT 的 99%），通过直接读取物理层信号指标（RSRP、SINR）实现即时感知，远比依赖传输层反馈更有效

#### [[atc2025-wang-liying|RHONE: Emulating Space Computing Networks]]
- **作者**：Liying Wang et al.
- **要解决的问题**：现有太空计算网络仿真工具无法同时实现卫星级保真度、星座级保真度和可扩展性
- **核心贡献**：通过 Hardware-in-the-loop chip mirroring 和 FEA 热模型实现 720 颗卫星的高保真仿真，误差 <5%
- **关键发现/观点**：COTS 芯片因过热导致的性能降级在相同温度下地面和太空表现一致——可在地面采集性能-温度映射再用轻量级容器镜像该行为

#### [[atc2025-xu|MP²: Roaming Free in the VR World]]
- **作者**：Yifei Xu et al.
- **要解决的问题**：自由漫游 VR 无线串流面临跨 AP 切换高延迟、多用户竞争和去中心化方案无法全局负载均衡三大挑战
- **核心贡献**：首个中心化多路径多用户 VR 编排系统，协调 AP 关联/路径选择/比特率指导，实现 35× 尾延迟改善
- **关键发现/观点**：中心化架构可收集全局跨层信息（Wi-Fi PHY 层和 VR 应用层），对 AP 关联、路径选择和比特率适配进行联合优化，去中心化方案因局部信息只能做局部最优决策

#### [[atc2025-zhao-yuankang|MARC: Motion-Aware Rate Control for Mobile E-commerce Cloud Rendering]]
- **作者**：Yuankang Zhao et al.
- **要解决的问题**：移动电商云渲染中用户在最活跃的运动交互阶段反而遭遇最高延迟（运动帧比非运动帧大 22%）
- **核心贡献**：基于在线测量推导动态 QoE 目标函数 + 多帧前瞻随机优化，淘宝百万级在线部署中 P99 帧延迟降低 20%、会话时长增加 9%
- **关键发现/观点**：用户 QoE 偏好随运动状态动态变化——运动阶段对延迟的敏感度比非运动阶段高 75.7%，需要 motion-aware 策略优先降低运动延迟

#### [[atc2025-meng|AnchorNet: Bridging Live and Collaborative Streaming with a Unified Architecture]]
- **作者**：Tong Meng et al.
- **要解决的问题**：TikTok 直播和连麦直播使用独立架构，模式切换时重建连接导致秒级卡顿
- **核心贡献**：将 RTC SFU 统一插入主播到 CDN 的发布路径作为"锚点"，配合 PCM 样本级音频拼接，视频 rebuffering 降低 60%-78%
- **关键发现/观点**：在 server 端流混合架构下，只要将 RTC SFU 统一插入发布路径，主播切换模式时始终维持同一 CDN 接入节点，将两条独立路径问题化简为单路径上的流拼接问题

#### [[atc2025-liu-jiacheng|SpaceExit: Enabling Efficient Adaptive Computing in Space with Early Exits]]
- **作者**：Jiacheng Liu et al.
- **要解决的问题**：卫星图像处理面临场景复杂度差异大、计算资源动态变化和下行带宽受限等多重挑战
- **核心贡献**：算法-系统协同的自适应推理系统，结合地理空间感知 early exit 检测器和资源自适应控制，goodput 提升最高 37.6%
- **关键发现/观点**：卫星图像复杂度与地理位置高度相关，通过融合视觉语义特征与预计算地理空间嵌入可可靠预测每张图像所需计算量，精准执行 early exit

### Serverless 与云计算（6 篇）

#### [[atc2025-barcelona-pons|Burst Computing: Quick, Sudden, Massively Parallel Processing on Serverless Resources]]
- **作者**：Daniel Barcelona-Pons et al.
- **要解决的问题**：FaaS 以单个函数调用为隔离单元，导致大规模并行协作任务面临 worker 启动离散、job 碎片化和细粒度跨节点通信三大摩擦
- **核心贡献**：提出 Burst Computing 模型，核心原语 flare 实现组级别调用，worker packing 打包到同一容器，PageRank 实现 13× 加速
- **关键发现/观点**：FaaS 阻碍 burst-parallel job 的根本是缺乏组感知——将隔离边界从单函数提升到 job 级别即可同时保证并行性和局部性利用

#### [[atc2025-chang|Poby: SmartNIC-accelerated Image Provisioning for Coldstart in Clouds]]
- **作者**：Zihao Chang et al.
- **要解决的问题**：容器冷启动延迟中镜像准备占 72%，解压占镜像准备时间 68.8% 且对同机应用造成严重干扰
- **核心贡献**：将完整镜像准备流程解耦卸载到 SmartNIC（RDMA 下载→硬件解压→PCIe 传输→Host 解包），平均冷启动加速 7-11×，减少 87.5% Host CPU 使用
- **关键发现/观点**：镜像准备的不同阶段各自适合不同硬件单元——在 SmartNIC 上先解压再传输，PCIe 传输的是少量大块数据而非大量小文件，避免了 PCIe 事务开销

#### [[atc2025-yao|Cosmic: Cost-Effective Support for Cloud-Assisted 3D Printing]]
- **作者**：Yuan Yao et al.
- **要解决的问题**：将 3D 打印实时控制算法搬到 serverless 平台上面临 warm start 调用延迟与时间约束的矛盾
- **核心贡献**：通过函数分组、投机执行和成本模型配置搜索，在 serverless 上实现比 VM 方案成本低 2.8×–6.3× 的 3D 打印控制
- **关键发现/观点**：连续两个时间窗口选择同组 cell 的概率较高，利用近似热传导预测下一个 cell 可达约 85% 准确率，投机预取可覆盖 invocation 延迟

#### [[atc2025-zhao-jianjun|RTSFaaS: Towards High-Performance Transactional Stateful Serverless Workflows with Affinity-Aware Leasing]]
- **作者**：Jianjun Zhao et al.
- **要解决的问题**：有状态 FaaS workflow 的事务一致性依赖频繁远程锁获取，并发控制开销占函数执行时间主要部分
- **核心贡献**：通过 affinity-aware lease assignment 将相关数据分配给特定 worker 独占缓存，配合 TPG 预先构建执行顺序，相比 Boki/Beldi 提升 5×/20× 吞吐
- **关键发现/观点**：将数据对象通过排他性租约分配给单一 worker，大多数事务可在本地缓存上执行而无需远程锁；跨 worker 访问通过预先构建的 TPG 序列化

#### [[atc2025-bartolomeo|2DFS: On-Demand Container Partitioning for Distributed ML]]
- **作者**：Giovanni Bartolomeo et al.
- **要解决的问题**：OCI 容器分层文件系统不适合 ML 模型分布式边缘部署——切分为 N 个 split 需构建 N 个独立镜像，构建时间呈指数增长
- **核心贡献**：扩展 OCI 规范引入独立可交换的 allotment 层，支持并行构建和按需语义化分区，构建速度比 Docker 快 56×
- **关键发现/观点**：ML 模型各 split 之间天然独立，可被单独构建和缓存，无需维护传统容器层的链式依赖关系

#### [[atc2025-ding|DShuffle: DPU-Optimized Shuffle Framework for Large-scale Data Processing]]
- **作者**：Chen Ding et al.
- **要解决的问题**：Spark Shuffle 中序列化+GC 占 64-69% 执行时间，朴素 DPU 卸载因频率低反而增加延迟
- **核心贡献**：将 Shuffle 分解为序列化/预处理/I/O 三阶段，利用 DPA 高并发内存访问加速序列化 + 细粒度流水线 + DPU 直接溢写，Sort Shuffle 阶段减少 62.7%
- **关键发现/观点**：DPU 的硬件特性（DPA 高并发内存访问、ARM 核心、PCIe P2P/RDMA）与 Shuffle 的三个阶段分别对应——关键在于三阶段流水线并行化来隐藏各阶段延迟

### 存储与文件系统（6 篇）

#### [[atc2025-duan-shaohua|Crash Consistency in Block-Level Caching Systems: An Open CAS Case Study]]
- **作者**：Shaohua Duan et al.
- **要解决的问题**：块级持久化缓存系统在各种崩溃场景下的实际一致性行为未经系统验证，隐式操作难以覆盖
- **核心贡献**：提出 WLOT 框架利用隐式缓存操作导致的 I/O 性能退化作为触发信号精确注入崩溃，发现 Open CAS 与 btrfs 存在静默数据丢失
- **关键发现/观点**：隐式缓存操作（eviction、cleaning）执行时会导致可观测的 I/O 吞吐量下降，这种性能退化信号可作为识别隐式操作运行状态的"隐式信息"

#### [[atc2025-hwang|Z-LFS: A Zoned Namespace-tailored Log-structured File System for Commodity Small-zone ZNS SSDs]]
- **作者**：Inhwi Hwang et al.
- **要解决的问题**：现有 LFS 在 ZNS SSD 上需额外 CNS SSD 存储 metadata，且对 small-zone ZNS 提供的数百个 active zone 利用率极低
- **核心贡献**：通过 metadata 生命周期分类实现全 ZNS 独立部署，基于写入强度的动态 active zone 分配，相比 F2FS 随机写提升 25.2×
- **关键发现/观点**：ZNS SSD 上 LFS metadata 可按生命周期分为 immutable（与 segment 同生命周期）和 mutable（独立更新）两类，分别用最优策略管理

#### [[atc2025-qiu|HotRAP: Hot Record Retention and Promotion for LSM-trees with Tiered Storage]]
- **作者**：Jiansheng Qiu et al.
- **要解决的问题**：LSM-tree 在分层存储上无法主动提升热数据，现有 record 级热度追踪因元数据量巨大（166GB 内存）不可行
- **核心贡献**：在 fast disk 上维护小型 LSM-tree 作为热度追踪结构（内存仅数据量 0.056%），hotspot 负载最高 5.2× 加速
- **关键发现/观点**：热度追踪元数据可存放在 fast disk 而非内存——将热度追踪结构设计为存储在 fast disk 上的小型 LSM-tree，以极低内存代价实现 record 级精细追踪

#### [[atc2025-zhang-qingyang|Mitigating Resource Usage Dependency in Sorting-based KV Stores on Hybrid Storage Devices via Operation Decoupling]]
- **作者**：Qingyang Zhang et al.
- **要解决的问题**：LSM-tree 的 flush/compaction 同时消耗 CPU（索引排序）和 I/O（数据读写），造成资源竞争和频繁 write stall
- **核心贡献**：将排序操作解耦为纯 CPU 密集型的索引合并和纯 I/O 密集型的数据追加，写密集负载下 2.3–4.9× 吞吐提升
- **关键发现/观点**：索引排序（CPU 密集）和数据读写（I/O 密集）在资源类型上天然可分离，解耦后两类任务可独立调度

#### [[atc2025-pan|SolFS: An Operation-Log Versioning File System for Hash-free Efficient Mobile Cloud Backup]]
- **作者**：Riwei Pan et al.
- **要解决的问题**：移动云备份的 delta 同步依赖哈希计算额外引入 170% 延迟和 224% CPU 能耗
- **核心贡献**：在 F2FS 内核中维护轻量级操作日志记录写操作 offset/length，完全无需哈希计算，同步时间缩短 71%
- **关键发现/观点**：文件系统天然拦截所有写操作，以极低开销记录 offset/length 元数据（25 字节/条）比记录数据本身便宜几个数量级

#### [[atc2025-yang-jingyuan|ShieldReduce: Fine-Grained Shielded Data Reduction]]
- **作者**：Jingyuan Yang et al.
- **要解决的问题**：外包存储中加密去重方案无法在加密数据上执行 delta compression 和 local compression
- **核心贡献**：在 SGX enclave 中实现去重+delta+local 完整压缩流程，核心创新是 bi-directional delta compression，存储节省比 DEBE 提升 2-10×
- **关键发现/观点**：Delta compression 可双向执行——让逻辑相邻的新数据块成为 base chunk 可重建物理局部性，降低后续备份 I/O 开销

### 内存系统与解耦架构（4 篇）

#### [[atc2025-liu-ruili|DSA-2LM: A CPU-Free Tiered Memory Architecture with Intel DSA]]
- **作者**：Ruili Liu et al.
- **要解决的问题**：Tiered memory 系统中页面迁移需要大量 CPU 参与，页拷贝占 migrate 过程 73.5% CPU 周期
- **核心贡献**：利用 Intel DSA 硬件加速器替代 CPU 执行页拷贝，通过 batching 和多 WQ 并行隐藏延迟，1:16 内存比下平均提升应用性能 28%
- **关键发现/观点**：DSA 在单次小数据量传输时慢于 CPU，但通过 batching 多个小页和多 WQ 并行可隐藏调用延迟；SVM 机制允许绕过内核 DMA 接口

#### [[atc2025-ji|Para-ksm: Parallelized Memory Deduplication with Data Streaming Accelerator]]
- **作者**：Houxiang Ji et al.
- **要解决的问题**：Linux ksm 内存去重消耗 14–65% CPU 且使同机应用性能下降最高 5.8×
- **核心贡献**：利用 RB 树 rebalancing 后 predecessor/successor 不变的性质实现 256 页批量并行搜索与插入，去重效率提升 31–50%
- **关键发现/观点**：RB 树 rebalancing 不改变已有节点的 predecessor/successor 关系，同一 batch 内不同 candidate page 的 (pred, succ) 对要么相同要么不相交，因此可安全并行搜索和插入

#### [[atc2025-grant|RCuckoo: Disaggregated Cuckoo Hashing]]
- **作者**：Stewart Grant et al.
- **要解决的问题**：完全解耦内存架构的 KVS 在写密集场景性能差，RDMA atomic 操作吞吐瓶颈（竞争时仅 3 MOPS）
- **核心贡献**：通过 locality-enhanced dependent hashing 使两个哈希位置概率性相邻，锁表压缩到 NIC 设备内存中，写密集场景比 FUSEE 吞吐提升最高 7×
- **关键发现/观点**：将 cuckoo hashing 两哈希位置距离设为可调参数后，绝大多数 cuckoo path 可被限制在小内存范围内；锁表缩小后放入 NIC 设备内存获得 3× 原子操作性能提升

#### [[atc2025-lu|HDTX: Fast Distributed Transactions for RDMA-based Disaggregated Memory]]
- **作者**：Haodi Lu et al.
- **要解决的问题**：RDMA 解耦内存架构下传统分布式事务协议需要多次 RTT（5 阶段），commit 阶段效率低
- **核心贡献**：通过 fast commit protocol 合并阶段 + RDMA Wait/Enable 原语自主执行释放，将事务从 5 RTT 压缩到 2 RTT，吞吐提升 84.7%
- **关键发现/观点**：采用 redo log 后 Validation 和 Commit 阶段无数据依赖可合并；redo log 已包含最新数据，数据同步可通过 RDMA Wait/Enable 卸载到 RNIC 自主执行

### 操作系统与虚拟化（8 篇）

#### [[atc2025-chen-le|µEFI: A Microkernel-Style UEFI with Isolation and Transparency]]
- **作者**：Le Chen et al.
- **要解决的问题**：UEFI 模块共享地址空间以最高权限运行，已签名模块中的内存安全漏洞可波及整个固件
- **核心贡献**：首次将微内核架构引入 UEFI，利用 trampoline injection 透明处理跨模块调用，x86 平台启动开销仅约 2%
- **关键发现/观点**：UEFI 所有模块对外调用都必须经过 System Table 这一中心数据结构，控制它就控制了所有模块交互

#### [[atc2025-jia|Rex: Closing the Language-Verifier Gap with Safe and Usable Kernel Extensions]]
- **作者**：Jinghao Jia et al.
- **要解决的问题**：eBPF 验证器与语言契约不一致（language-verifier gap），导致开发者需要大量 workaround
- **核心贡献**：通过 safe Rust 编译时安全 + 轻量运行时完全消除独立验证层，BMC 案例中代码量减少 36%、吞吐提升 5.43×
- **关键发现/观点**：内核扩展所需的安全属性可以完全建立在 Rust 语言级特性之上，配合轻量运行时处理终止性和栈安全，从而彻底消除对独立静态验证层的需求

#### [[atc2025-peng-yuke|ASTERINAS: A Linux ABI-Compatible, Rust-Based Framekernel OS with a Small and Sound TCB]]
- **作者**：Yuke Peng et al.
- **要解决的问题**：现有 Rust OS 在内核开发中大量使用 unsafe 代码（最高 93%），TCB 过大
- **核心贡献**：提出 framekernel 架构，将 OS 资源分为 sensitive/insensitive 两类，仅特权框架（10.5K LoC）允许 unsafe，TCB 占比仅 14.0%
- **关键发现/观点**：OS 资源可按是否会破坏内存安全细粒度分为 sensitive 和 insensitive 两类；只需将 sensitive 资源封装在特权框架内，insensitive 全部用 safe Rust

#### [[atc2025-tang|CONVEROS: Practical Model Checking for Verifying Rust OS Kernel Concurrency]]
- **作者**：Ruize Tang et al.
- **要解决的问题**：将 model checking 应用于真实 OS 内核并发验证面临形式化规约编写难和规约-代码不一致两大障碍
- **核心贡献**：多层多粒度规约方法和增强的 trace validation，在 ASTERINAS 12 个并发模块上发现 20 个 bug，spec-to-code ratio 仅 0.3-2.3
- **关键发现/观点**：OS 并发模块天然具有层次化可组合结构，利用这种结构将规约分为高层（设计正确性）和低层（代码细节）在不同粒度上增量组合验证

#### [[atc2025-li-wentong|PMR: Fast Application Response via Parallel Memory Reclaim on Mobile Devices]]
- **作者**：Wentong Li et al.
- **要解决的问题**：Android 内存回收路径中 page shrinking 与 writeback 串行执行且逐页 I/O 碎片化
- **核心贡献**：将 page shrinking 解耦为独立内核线程实现预取 + 应用感知批量 writeback，内存回收吞吐提升 82.8%，应用响应时间降低 43.6%
- **关键发现/观点**：内存回收瓶颈不在 I/O 硬件而在软件路径设计——串行执行和逐页碎片化 I/O 使现代 Flash 存储的并行能力无法被利用

#### [[atc2025-yelam|PageFlex: Flexible and Efficient User-space Delegation of Linux Paging Policies with eBPF]]
- **作者**：Anil Yelam et al.
- **要解决的问题**：内核默认 LRU 分页策略与最优策略间存在 14–38% 内存节省差距，但修改内核难以滚动部署
- **核心贡献**：通过 eBPF 将 paging 策略决策外部化到用户态，实现 <1% 开销的灵活分页策略定制
- **关键发现/观点**：分页策略决策不在应用关键路径上，可安全委托到内核外部执行，只需将决策的 per-page 权重传回内核

#### [[atc2025-zur|HyperTurtle: Accelerating Nested Virtualization]]
- **作者**：Ori Ben Zur et al.
- **要解决的问题**：嵌套虚拟化中 L2 vm-exit 必须经 L0 转发给 L1，产生大量冗余 world switch
- **核心贡献**：提出 hyperupcall 机制将 L1 hypervisor 关键处理逻辑封装为 eBPF 在 L0 直接执行，EPT fault 5.25× 加速
- **关键发现/观点**：L1 hypervisor 的关键 vm-exit 处理逻辑封装为 eBPF 并由 L0 直接执行，可完全绕过 L1 介入从根本上消除冗余 world switch

#### [[atc2025-patel|XRT: An Accelerator-Aware Runtime for Accelerated Chip Multiprocessors]]
- **作者**：Neel Patel et al.
- **要解决的问题**：现代服务器集成 DSA/IAA/QAT 等片上加速器，但运行时不感知加速器导致不必要的上下文切换和阻塞
- **核心贡献**：通过 notification-aware scheduler（利用 FIFO 特性轮询 2-3 周期判断完成）和 software fallback，最高 3.2× SLO 吞吐提升
- **关键发现/观点**：加速器按 FIFO 顺序处理 offload 请求，调度器只需轮询下一个预期完成的 completion record 即可以极低开销判断 offload 是否完成

### 系统安全与可信计算（6 篇）

#### [[atc2025-luo|MemoryTrap: Booby Trapping Memory to Counter Memory Disclosure Attacks]]
- **作者**：Chenke Luo et al.
- **要解决的问题**：JIT-ROP 攻击通过运行时内存披露绕过 ASLR 和 fine-grained 随机化
- **核心贡献**：在编译时向代码中密集插入不可读的 booby traps，利用 Intel MPK 实现 execute-only 代码页，运行时开销仅 1.85%
- **关键发现/观点**：JIT-ROP 攻击者必须以 4KB 页粒度遍历大量代码来收集 gadgets；若每隔 4KB 以内插入一个 booby trap，攻击者搜索时必然触发陷阱而正常执行通过 JMP 跳过

#### [[atc2025-manakkal|LITESHIELD: Secure Containers via Lightweight, Composable Userspace µKernel Services]]
- **作者**：Kaesi Manakkal et al.
- **要解决的问题**：容器共享宿主内核攻击面大（300+ syscalls），VM 隔离开销重
- **核心贡献**：将 guest kernel 功能拆分为可组合的用户态 µkernel 服务，user-to-host 接口压缩到 22 个 syscalls，Redis+YCSB 性能优于 native
- **关键发现/观点**：Guest kernel 大部分功能可从应用中解耦为独立用户态进程，通过共享内存 IPC 通信；多核 LLC cache-to-cache 传输（数十周期）可替代传统 IPC 路径

#### [[atc2025-weinhold|Separate but Together: Integrating Remote Attestation into TLS]]
- **作者**：Carsten Weinhold et al.
- **要解决的问题**：现有 TLS+远程证明方案存在 relay attack 风险或故障依赖性
- **核心贡献**：利用 TLS 1.3 DHE 共享秘密实现双重链接，TLS 证书和 TEE attestation 独立绑定到同一会话，零额外网络往返
- **关键发现/观点**：TLS 1.3 强制使用 Ephemeral DHE 产生临时共享秘密，将其包含在 attestation 的 linking hash 中可独立于 TLS 私钥绑定，实现真正的故障独立性

#### [[atc2025-schreiber|Bluetooth Low Energy Security Testing with Combinatorial Methods]]
- **作者**：Dominik-Philip Schreiber et al.
- **要解决的问题**：BLE 安全测试依赖 fuzzing，无法保证覆盖度且存在掩蔽效应
- **核心贡献**：基于 Covering Array 的组合安全测试方法，以更少测试用例（1.8K vs 7K）在 10 款 BLE 芯片上发现更多漏洞（16 vs 2）
- **关键发现/观点**：所有软件故障都由最多 6 个参数的组合触发（NIST 实证研究），BLE 数据包的多层嵌套结构可用 Covering Array 系统性覆盖

#### [[atc2025-duan-guanglin|Trochilus: Learning-Enhanced High-Throughput Pattern Matching Based on Programmable Data Plane]]
- **作者**：Guanglin Duan et al.
- **要解决的问题**：网络模式匹配需要 100 Gbps+ 吞吐，软件方案上限约 70 Gbps，可编程交换机受限于资源约束
- **核心贡献**：将 PCRE 模式无损转为 RNN（DFA≡RNN），再通过知识蒸馏压缩为可部署的轻量 Forest，实现 multi-Tbps 吞吐、~98% 准确率
- **关键发现/观点**：DFA 的前向计算在数学上等价于 RNN 前向传播（当 U=0, b=0 时），专家知识编码的模式规则可无损转换为神经网络

#### [[atc2025-wang-zihao|Minos: A Lightweight and Dynamic Defense against Traffic Analysis in Programmable Data Planes]]
- **作者**：Zihao Wang et al.
- **要解决的问题**：现有流量分析防御方案带宽开销过大（143%+），或吞吐上限仅 45 Gbps
- **核心贡献**：在 Tofino 可编程交换机上实现包头加密+动态流交错调度，几乎零额外带宽开销实现攻击准确率降至 20% 以下
- **关键发现/观点**：多用户并发传输的多条流本身可互相充当"dummy 流量"——当并发流数量达到 4-5 条时无需额外 dummy 包即可有效混淆

### 分布式系统可靠性（4 篇）

#### [[atc2025-gupta|Fast ACS: Low-Latency File-Based Ordered Message Delivery at Scale]]
- **作者**：Sushant Kumar Gupta et al.
- **要解决的问题**：现有消息系统在大规模 consumer fan-out 时吞吐量受限于单点 SSD 带宽瓶颈
- **核心贡献**：基于 RMA 内存缓存 + 分布式文件系统双层存储 + MST copy tree 跨集群路由，支持 Tbps 级 fan-out
- **关键发现/观点**：有序字节传递无需在网络上按序传输——将文件切成 4KB chunk 后乱序并行读取、客户端重组装，即可绕开服务端吞吐瓶颈

#### [[atc2025-huang-rongji|Chitu: Avoiding Unnecessary Fallback in Byzantine Consensus]]
- **作者**：Rongji Huang et al.
- **要解决的问题**：部分同步 BFT 协议中 leader 是性能瓶颈，异步 BFT 的 random coin 始终在关键路径上增加延迟
- **核心贡献**：提出 Fair-Fallback 框架，通过纯消息交换 fast path + adaptive wait 实现 99.5% fast commit，延迟比 Tusk 降低 82.5%
- **关键发现/观点**：Leader 选举和 random coin 本质是应对 FLP 不可能性的 fallback——只有当节点意见分歧时才需要；通过 adaptive wait 制造 univalent 条件绝大多数轮次可直接跳过

#### [[atc2025-rovelli|FiDe: Reliable and Fast Crash Failure Detection to Boost Datacenter Coordination]]
- **作者**：Davide Rovelli et al.
- **要解决的问题**：现有 crash 故障检测器超时值设置保守（数百 ms），制约 µs 级服务性能
- **核心贡献**：通过双域隔离（CPU 核隔离 + SDN 优先级流量 + XDP 网络处理）实现 < 30 µs crash 检测，Redis 吞吐提升 1.7×
- **关键发现/观点**：故障检测不可靠的根本原因是作为"模块"实现于共享环境中；若从底层构建专用隔离基底使心跳延迟有界，可在实践中近似实现"完美故障检测器"

#### [[atc2025-dong|Understanding and Detecting Fail-Slow Hardware Failure Bugs in Cloud Systems]]
- **作者**：Gen Dong et al.
- **要解决的问题**：现有故障注入工具无法有效检测 fail-slow 硬件引发的软件 bug，此类 bug 平均需数小时到数月才能发现
- **核心贡献**：提出 Sieve 框架，通过静态分析识别候选故障点并结合分组+上下文敏感策略注入，在 ZooKeeper/Kafka/HDFS 上检测到 7 个新 bug
- **关键发现/观点**：FSH 故障触发需两个条件——受保护的 I/O 操作和细粒度特性（粗粒度故障被已有容错机制处理）——可用于精准识别故障注入点并大幅剪枝搜索空间

### 软件测试与质量保障（6 篇）

#### [[atc2025-chen-yuanliang|CAFault: Enhance Fault Injection Technique via Abundant Fault-Dependent Configurations]]
- **作者**：Yuanliang Chen et al.
- **要解决的问题**：现有故障注入工具在固定默认配置下测试，忽略了不同配置会显著改变容错逻辑执行路径
- **核心贡献**：通过动态覆盖率差异分析自动构建配置-故障依赖模型，在 HDFS/MySQL-Cluster/ZooKeeper/IPFS 上发现 16 个新 bug
- **关键发现/观点**：在相同故障输入下若改变某配置项导致容错代码覆盖率变化，则该配置与故障之间存在隐式执行依赖——通过动态监测覆盖率差异可自动构建依赖模型

#### [[atc2025-guo|SyzMini: Optimizing Input Minimization in Kernel Fuzzing]]
- **作者**：Hui Guo et al.
- **要解决的问题**：Syzkaller 的 minimization 阶段消耗 57.5% 程序执行资源，one-by-one 尝试效率极低
- **核心贡献**：influence-guided call removal + type-informed argument simplification，minimization 执行开销降低 60.7%，bug 发现数提升 1.7-2×
- **关键发现/观点**：若两个 call 不共享任何全局内核状态可批量移除；fixed-size 参数（占约 80%）的简化不改变 mutation 搜索空间大小属于无效开销

#### [[atc2025-wu-zhiyong|DDLUMOS: Understanding and Detecting Atomic DDL Bugs in DBMSs]]
- **作者**：Zhiyong Wu et al.
- **要解决的问题**：Atomic DDL Bug 缺乏系统性认知，现有 DBMS 测试工具无法有效检测 DDL 恢复一致性问题
- **核心贡献**：通过元数据冲突引导的 DDL 合成和图基一致性分析，在 6 个 DBMS 上发现 73 个新 bug（9 个获 CVE）
- **关键发现/观点**：94% 的 Atomic DDL Bug 由 DDL 语句之间的元数据冲突触发，这一发现直接指导了测试用例生成策略

#### [[atc2025-yang-zao|BIN2WRONG: a Unified Fuzzing Framework for Uncovering Semantic Errors in Binary-to-C Decompilers]]
- **作者**：Zao Yang et al.
- **要解决的问题**：现有反编译器测试工具覆盖面窄，无法系统触发多维度组合引发的语义错误
- **核心贡献**：将源代码、编译器、优化选项、可执行文件格式四个维度编码为单一可变异测试用例，发现 7 个反编译器共 48 个语义 bug
- **关键发现/观点**：影响二进制代码的四个维度对反编译器 bug 触发具有同等重要性，联合变异产生的二进制多样性（10–17×）远超单独变异

#### [[atc2025-zhang-yunmo|Inferring Likely Counting-related Atomicity Program Properties for Persistent Memory]]
- **作者**：Yunmo Zhang et al.
- **要解决的问题**：PM 程序中"容器类数组 + 逻辑大小变量"需原子更新，现有工具无法识别 counting correlation 关系
- **核心贡献**：基于 access range invariant 的推断框架结合 Z3 SMT solver，在 4 个 PM 程序上发现 14 个 atomicity bug
- **关键发现/观点**：数组的逻辑大小虽无法直接从定义中获取，但所有读访问索引必然落在逻辑大小约束的有效范围内——这一不变量可被 SMT solver 高效验证

#### [[atc2025-wu-jiangchang|ATLAS: Unveiling Compiler Faults via Attribute-Guided Compilation Space Exploration]]
- **作者**：Jiangchang Wu et al.
- **要解决的问题**：现有编译器测试方法只能以全局编译选项统一作用于整个程序，无法对单个函数/变量进行细粒度控制
- **核心贡献**：通过向测试程序随机插入 C/C++ `__attribute__`，在 GCC/LLVM 上发现 73 个新 bug（58 个已确认）
- **关键发现/观点**：编译器属性为单个程序元素提供细粒度编译控制，能引导编译器进入仅靠全局编译选项无法到达的深层状态

### 系统性能分析与评测（4 篇）

#### [[atc2025-chen-chao|Swift: Fast Performance Tuning with GAN-Generated Configurations]]
- **作者**：Chao Chen et al.
- **要解决的问题**：Bayesian Optimization 调参每次迭代从随机池选择候选配置，质量不可控收敛慢
- **核心贡献**：将轻量级 GAN 集成到 BO 框架，以当前最优配置为目标训练 GAN 生成高质量候选配置，Flink/Spark 调优时间比 CherryPick 减少 61%
- **关键发现/观点**：配置向量"性能相似"不等于向量距离短，而是元素值分布相似；GAN 天然以 JS divergence 为目标函数恰好能生成分布相似的配置

#### [[atc2025-gong|Identifying and Analyzing Pitfalls in GNN Systems]]
- **作者**：Yidong Gong et al.
- **要解决的问题**：GNN 系统论文普遍不报告训练精度，导致反向传播实现缺陷长期隐藏；框架运行时开销被错误归因
- **核心贡献**：揭示 20+ 个 GNN 系统中的评估陷阱，提出 GRAPHPY 原型实现 GCN 内存节省 6.92×、首次单 GPU 训练 10 亿边图
- **关键发现/观点**：不报告训练精度掩盖了连锁设计缺陷（这些缺陷恰恰是"性能提升"的来源），框架开销在小数据集上主导总时间

#### [[atc2025-lamprou|The Koala Benchmarks for the Shell: Characterization and Implications]]
- **作者**：Evangelos Lamprou et al.
- **要解决的问题**：Shell 性能优化领域缺乏标准化 benchmark suite，结果不可比较
- **核心贡献**：构建 KOALA benchmark suite（126 个真实 shell 程序、14 个应用领域），对 4 个优化系统进行首个标准化对比评测
- **关键发现/观点**：真实 shell 程序在语法特征、运行时行为上存在极大多样性，不同优化系统在不同工作负载类型上表现差异显著

#### [[atc2025-wei|LogCrisp: Fast Aggregated Analysis on Large-scale Compressed Logs]]
- **作者**：Junyu Wei et al.
- **要解决的问题**：在高度压缩的日志上执行聚合分析面临全局 pattern 过滤效率差与局部 pattern 缺乏全局描述的两难
- **核心贡献**：通过 two-phase pattern extraction（Sketch+Spec 解耦）和整数查询转换，分析延迟比 CLP 快 15.32×
- **关键发现/观点**：超过 98% 的 fragment 边界是非字母数字字符，仅通过 NAU 字符即可高准确率定位 fragment 边界，将 pattern 清晰解耦为全局结构和局部细节

---

## 研究趋势分析

**AI 基础设施仍是绝对主题**。LLM 推理与训练相关论文占总数近 1/3（32 篇），覆盖从推理服务（adapter serving、量化加速、KV cache 优化）到训练系统（pipeline 调度、MoE 通信、checkpoint 管理）的完整链路。与往年不同的是，2025 年的 AI 系统研究从"单点优化"走向"系统性思考"：不再只是提出一个新的调度算法或压缩方法，而是面向真实生产环境中的多维约束（多模型共享 GPU、推理-训练混部、跨 DC 训练、fail-slow 检测）进行端到端设计。DeepServe、GREYHOUND、Hermes 等论文直接来自华为、阿里、字节跳动的生产实践，标志着工业界与学术界在 AI 系统研究上的深度融合。

**Adapter/LoRA Serving 成为推理侧新热点**。KATZ、TOPPINGS 两篇论文独立发现了 adapter 加载对推理延迟的严重影响（29-37%），并分别从 diffusion model 和 LLM 两个角度提出解决方案。这反映了从"单模型单请求"到"多 adapter 多租户"的部署范式转变——当 base model 被高效 serve 之后，围绕 adapter 管理的新瓶颈自然浮现。

**Pipeline Parallelism 的 Bubble 利用进入深水区**。CrossPipe、Optimus、Obscura、FlexPipe 四篇论文从不同角度（跨 DC 通信、多模态异构、recomputation 隐藏、变长输入）攻击 pipeline bubble 问题，说明社区已普遍认识到 1F1B 调度的局限性。这些工作的共同思路是"bubble 不是浪费，是可以被填充的计算资源"，但各自填充的内容不同。

**可编程网络硬件（SmartNIC/P4 交换机）的应用深度显著提升**。不再局限于简单的包处理加速，而是承担拥塞控制（SwCC、Barre）、工作负载整形（Pallas）、图计算聚合（SwitchGNN）、流量分析防御（Minos）等高层语义功能。BlueField-3 和 Tofino 成为研究平台标配，SwCC 和 Barre 分别代表了 FPGA+RISC-V 和 DPU PCC 两条技术路线。

**Rust 在系统软件中的地位持续巩固**。ASTERINAS（framekernel OS）、Rex（Rust 内核扩展）、CONVEROS（Rust OS 并发验证）三篇论文形成了从"用 Rust 写 OS"到"验证 Rust OS 正确性"的完整链路。Rex 尤其值得注意——它直接挑战了 eBPF 的基本设计哲学（独立验证器），提出用语言级安全替代验证器。

---

## 小实验室的机会窗口

### 1. LLM 推理的 workload-aware 缓存与调度策略

- **方向描述**：基于真实 trace 分析设计针对特定工作负载特征的 KV cache 管理、adapter 预加载和请求路由策略
- **为什么小团队能做**：核心是分析能力和算法设计，不需要大规模 GPU 集群；可基于开源推理框架（vLLM、SGLang）实现；关键在于获取或构造有代表性的 workload trace
- **哪些论文指向了这个空白**：KVCache Cache in the Wild 发现 KV cache 复用时间遵循可预测分布但现有系统忽略这一特征；KATZ 和 TOPPINGS 发现 adapter 加载是新瓶颈但缺乏跨 adapter 类型的统一调度框架
- **具体 open problems**：跨对话轮次的 KV cache 预热策略优化；LoRA adapter 的热度预测与 prefetch 机制；异构 adapter（ControlNet/LoRA/IP-Adapter）的统一调度框架

### 2. Pipeline Bubble 的通用分析与调度优化框架

- **方向描述**：构建 pipeline parallelism 的通用 bubble 分析工具和自动化调度优化器，而非针对特定场景的 ad-hoc 方案
- **为什么小团队能做**：主要是调度算法和 profiling 工具的开发，可在模拟器或小规模集群上验证；CrossPipe 已经证明 solver-based 方法可行，但缺乏统一框架
- **哪些论文指向了这个空白**：CrossPipe（跨 DC）、Optimus（多模态）、Obscura（recomputation）、FlexPipe（变长输入）四篇论文各自提出场景特定的 bubble 利用方案，但没有统一的建模和求解框架
- **具体 open problems**：将 bubble 填充问题形式化为通用约束优化问题（输入：计算图、硬件拓扑、通信延迟；输出：最优调度）；将 recomputation、communication overlap、异构 encoder 计算作为统一的"可填充任务"建模

### 3. 基于 Intel DSA/IAA 等片上加速器的系统优化

- **方向描述**：利用现代 CPU 集成的硬件加速器（DSA、IAA、QAT）优化系统软件中的数据搬运、压缩、加密等操作
- **为什么小团队能做**：只需要一台支持 DSA 的服务器（Intel Xeon 4/5 代），不需要 GPU 集群；DSA 驱动和 API 已成熟，开发门槛低；多个方向尚未充分探索
- **哪些论文指向了这个空白**：DSA-2LM 用 DSA 替代 CPU 做页面迁移、Para-ksm 用 DSA 加速内存去重、XRT 发现加速器调度存在严重问题——说明这类加速器在系统软件中的应用才刚开始
- **具体 open problems**：DSA 在日志压缩/解压中的应用（LogCrisp 的 pattern 解耦与 IAA 压缩结合）；加速器在 checkpoint I/O 中的应用（UCP 的大规模数据搬运）；多加速器协同调度（DSA+IAA+QAT 的统一运行时）

### 4. Rust OS 的并发正确性工具链

- **方向描述**：为 Rust 操作系统开发实用的并发验证和调试工具
- **为什么小团队能做**：CONVEROS 已证明 model checking 对 Rust OS 可行且投入可控（约 4 人月找到 20 个 bug），但工具链不成熟、自动化程度低；这是典型的"工具型研究"，不需要大量硬件
- **哪些论文指向了这个空白**：ASTERINAS 提供了一个活跃的 Rust OS 目标系统、CONVEROS 证明了 model checking 的有效性但 spec 编写仍需大量人工、Rex 展示了 Rust 安全性在内核扩展中的优势
- **具体 open problems**：自动化规约推断（从 Rust 类型系统和 trait 约束中提取并发规约）；RB 树等基础数据结构的通用并发验证模板；跨模块组合验证的可扩展性问题

### 5. 编译缓存与增量编译优化

- **方向描述**：利用 LLVM IR 或其他中间表示实现更智能的编译缓存和增量构建
- **为什么小团队能做**：IRHash 以 561 行 C++ 实现了跨语言编译缓存，说明方案可以很轻量；编译器基础设施（LLVM）成熟，开发门槛适中
- **哪些论文指向了这个空白**：IRHash 证明 IR 级哈希是准确率和通用性的最优平衡点、HEC 展示 e-graph 可用于编译变换验证——两者可结合实现"验证过的增量编译"
- **具体 open problems**：将 IRHash 扩展到 LTO（Link-Time Optimization）场景；结合 HEC 的等价性验证确保缓存命中的正确性；针对 AI 编译器（如 XLA、TorchInductor）的 IR 级缓存
