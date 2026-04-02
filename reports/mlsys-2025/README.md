# MLSys 2025 论文概览

> 共 61 篇论文 | 生成日期: 2026-04-02

---

## 论文分类索引

### LLM 推理 — Attention 优化与长上下文（8 篇）

#### [[16ec6494e9b5a4138de7238761d715b4|LeanAttention: Hardware-Aware Scalable Attention Mechanism for the Decode-Phase of Transformers]]
- **作者**：Rya Sanovar et al. (Microsoft)
- **要解决的问题**：Decode 阶段 GPU SM 占用率低，FlashDecoding 的 fixed-split 策略产生 partially filled waves
- **核心贡献**：通过证明 softmax re-scaling 的结合律，将 Stream-K 风格均匀工作分配引入 decode attention，平均加速 1.73×
- **关键发现/观点**：Softmax re-scaling 操作具有结合律，可作为 reduction operator 合并任意大小 KV 块的 partial outputs，从而像 Stream-K 一样均匀分配工作给所有 SM

#### [[66a026c0d17040889b50f0dfa650e5e0|Flex Attention: a Programming Model for Generating Optimized Attention Kernels]]
- **作者**：Juechu Dong et al. (UMich / Meta)
- **要解决的问题**：FlashAttention 仅支持有限的 attention 变体，新变体需手写 CUDA kernel，组合爆炸无法扩展
- **核心贡献**：基于 PyTorch compile + Triton 的两层编程模型，通过 `score_mod` 和 `mask_mod` 接口支持任意变体组合，性能达手写 kernel 的 0.68-1.43×
- **关键发现/观点**：Attention 变体的核心差异仅体现在对 score 矩阵的逐元素修改，可分解为"不变的计算模板"+"可定制的 score/mask 修改函数"

#### [[dbf02b21d77409a2db30e56866a8ab3a|FlashInfer: Efficient and Customizable Attention Engine for LLM Inference Serving]]
- **作者**：Zihao Ye et al. (UW / CMU / NVIDIA)
- **要解决的问题**：异构 KV cache 存储格式、多种 attention 变体爆炸、输入动态性导致的负载不均衡
- **核心贡献**：统一的 Block-Sparse Row 格式抽象、composable formats 优化共享前缀、JIT 编译可定制模板、动态负载均衡调度器，已集成 SGLang/vLLM 等主流框架
- **关键发现/观点**：所有主流 KV cache 存储格式（page table、radix tree、sparse mask）本质上都可统一表示为 BSR 矩阵，通过 composable formats 组合多种粒度优化数据复用

#### [[2d04d97593c8c33d415337f408ed0e1b|SampleAttention: Near-Lossless Acceleration of Long Context LLM Inference with Adaptive Structured Sparse Attention]]
- **作者**：Qianchao Zhu et al. (Zhipu.AI / PKU / CUHK)
- **要解决的问题**：长上下文推理 TTFT 极高（1M token 需 1555 秒），固定稀疏率无法兼顾效率和精度
- **核心贡献**：以 Cumulative Residual Attention 为指导的自适应 sparse attention，两阶段采样-过滤机制动态确定稀疏率，最高 5.29× 加速
- **关键发现/观点**：Cumulative Residual Attention 是模型精度的鲁棒指标，attention 矩阵的重要元素集中在 column stripe 和 slash stripe 两种结构化模式中

#### [[cc8c6b9d89f7a898a29f58869b238e46|LServe: Efficient Long-Sequence LLM Serving with Unified Sparse Attention]]
- **作者**：Shang Yang et al. (MIT / NVIDIA)
- **要解决的问题**：缺乏统一框架同时加速 prefilling 和 decoding 的稀疏注意力，静态与动态稀疏未结合
- **核心贡献**：统一 block sparse attention 框架结合静态稀疏（streaming heads）、动态稀疏（hierarchical paging）和 KV cache 量化，prefilling 最高 2.9× 加速
- **关键发现/观点**：静态稀疏（head 级 streaming/retrieval 分类）与动态稀疏（query-aware page pruning）正交，可在 block sparse attention 中实现乘法级加速

#### [[75bb91b908e6924763c9f2bbe87e921e|Context Parallelism for Scalable Million-Token Inference]]
- **作者**：Amy Yang et al. (Meta)
- **要解决的问题**：长上下文 prefill 延迟过高，跨节点 Tensor Parallelism 因 AllReduce 通信量大扩展性差
- **核心贡献**：将 ring attention 从训练扩展到推理，提出 pass-KV 和 pass-Q 两种变体及自适应切换，1M token prefill 77 秒（128 GPUs, 93% 并行效率）
- **关键发现/观点**：GQA 模型中 KV head 数远小于 Q head 数，不同推理阶段 Q 和 KV 的相对大小会逆转，可根据 KV cache 命中率动态选择传输 Q 还是 KV 来最小化通信

#### [[f4f55846501f3336f293fd8b6de10770|TurboAttention: Efficient Attention Approximation for High Throughputs LLMs]]
- **作者**：Hao Kang et al. (Microsoft / Georgia Tech)
- **要解决的问题**：FlashAttention 不兼容量化执行，Softmax 中 FP32 瓶颈仅为 Tensor Core 性能的 3%
- **核心贡献**：FlashQ（block-wise progressive quantization + head-wise mixed precision）和 SAS（稀疏激活 softmax），1.2-1.8× attention 加速、4.4× KV cache 压缩
- **关键发现/观点**：不同 attention head 对量化敏感度差异很大，可对不敏感 head 用 2-bit 压缩；Softmax 指数运算可分解为 LUT + 多项式近似消除 FP32 瓶颈

#### [[d3cf1559a8795eb1ed2b3ad52409ac7d|MAS-Attention: Memory-Aware Stream Processing for Attention Acceleration on Resource-Constrained Edge Devices]]
- **作者**：Mohammadali Shakerdargah et al. (Alberta / Huawei)
- **要解决的问题**：边缘加速器异构计算单元（MAC、VEC）未被并行利用，片上缓存极其有限
- **核心贡献**：半同步流处理方案利用 MAC 和 VEC 异构并行重叠 MatMul 和 Softmax，模拟硬件 1.70× 加速，真实 NPU 1.42× 加速
- **关键发现/观点**：Attention 中 MatMul（计算密集）和 Softmax（逐元素）天然映射到不同硬件计算单元，可作为两个独立流进行流水线并行

---

### LLM Serving 系统架构（9 篇）

#### [[5c20ca4b0b20b0bd2f1d839dc605e70f|XGrammar: Flexible and Efficient Structured Generation Engine for Large Language Models]]
- **作者**：Yixin Dong et al. (CMU / NVIDIA / SJTU / UCB)
- **要解决的问题**：Constrained decoding 每步需扫描整个词表检查语法合法性，CFG 的递归需维护栈状态无法预计算
- **核心贡献**：自适应 token mask 缓存、context expansion、持久化执行栈，将 per-token 开销从毫秒级降至微秒级，end-to-end 最高 80× 加速
- **关键发现/观点**：绝大多数 token 的语法合法性仅取决于栈顶节点（context-independent），仅约 1% 的 token 是 context-dependent，可大规模预计算

#### [[678773d96b5822e93348aeb5c80d4dc5|NEO: Saving GPU Memory Crisis with CPU Offloading for Online LLM Inference]]
- **作者**：Xuanlin Jiang et al. (PKU / UCB / Harvard)
- **要解决的问题**：GPU 显存限制 batch size 导致算力浪费，现有 offloading 方案不适合在线推理
- **核心贡献**：非对称流水线将部分 decoding attention 卸载到 CPU，T4 上最高 7.5× 加速，H100 上 14-26% 提升
- **关键发现/观点**：Decoding attention 是 memory-bandwidth-bounded，GPU 和 CPU 在内存带宽上的差距（600 vs 200 GB/s）远小于算力差距，CPU 可胜任部分工作

#### [[698cfaf72a208aef2e78bcac55b74328|FlexInfer: Flexible LLM Inference with CPU Computations]]
- **作者**：Seonjin Na et al. (Georgia Tech / Meta / Intel Labs)
- **要解决的问题**：PCIe 传输在 offloading 方案中占 96-98% 执行时间，CPU AMX 加速硬件完全闲置
- **核心贡献**：Phase-aware 执行规划器为 prefill 和 decode 分别选择最优策略，相比 FlexGen 降低 75-76% 延迟
- **关键发现/观点**：Prefill 是 compute-intensive（GPU offloading 仍有益），decode 是 memory-bound（CPU 因无需 PCIe 传输和足够内存带宽反而更快）

#### [[78834433edc3291f4c6cbbd2759324db|Marconi: Prefix Caching for the Era of Hybrid LLMs]]
- **作者**：Rui Pan et al. (Princeton / AWS)
- **要解决的问题**：Hybrid LLMs 中 SSM state 无法部分复用，仅精确匹配可复用，细粒度 checkpoint 导致内存爆炸
- **核心贡献**：首个面向 Hybrid LLM 的 prefix caching 系统，审慎准入 + FLOP-aware eviction，4.5-34.4× token hit rate 提升，最高 71.1% P95 TTFT 降低
- **关键发现/观点**：SSM state 的复用潜力可通过前缀复用场景分类估计——仅缓存分支点和最后解码位置的 state，不同层类型的 cache entry 在内存/计算收益上差异显著

#### [[bc82dbfbfa43232be85b8d9838f49c3e|SOLA: Optimizing SLO Attainment for Large Language Model Serving with State-Aware Scheduling]]
- **作者**：Ke Hong et al. (Tsinghua / Infinigence AI / PKU / SJTU)
- **要解决的问题**：TTFT 与 TPOT 存在分布偏差，某指标远好于 SLO 而另一指标严重超标
- **核心贡献**：每 iteration 级别动态调整排序函数、执行请求数和 token 数，90% attainment 下 goodput 平均提升 1.08-1.27×
- **关键发现/观点**：TTFT 和 TPOT 的 SLO 满足程度存在系统性不对称，调度器感知实时延迟状态和系统级 SLO 统计后可在 iteration 级做精细 trade-off

#### [[c2a0e26dd9ee7d57e92bb1c24b39659a|ThunderServe: High-Performance and Cost-Efficient LLM Serving in Cloud Environments]]
- **作者**：Youhe Jiang et al. (Cambridge / PKU / ETH Zurich)
- **要解决的问题**：云环境异构 GPU 和低带宽网络使 phase splitting 部署困难，KV cache 传输开销不可忽略
- **核心贡献**：两层层次优化（Tabu Search + LP）联合优化 GPU 分组和请求路由，配合 KV cache 4-bit 量化，最高 2.5× 延迟降低和 2.1× 吞吐提升
- **关键发现/观点**：Prefill 和 decode 对硬件需求不同，云上异构 GPU 可将高算力 GPU 分给 prefill、高带宽 GPU 分给 decode，phase designation 调整无需重新加载模型参数

#### [[cbc4ab80cd77aa0eb87da062fbcddb46|Seesaw: High-Throughput LLM Inference via Model Re-Sharding]]
- **作者**：Qidong Su et al. (Toronto / Stanford / CentML)
- **要解决的问题**：单一并行策略次优，TP 在 prefill 通信开销大，PP 在 decode 权重重复加载
- **核心贡献**：动态模型 re-sharding（prefill 用 PP、decode 用 TP），配合 tiered KV cache buffering，低端 GPU 平均 1.36×、最高 1.78× 加速
- **关键发现/观点**：Prefill 处理大量 token 通信占比大（PP 更优），decode 每步一个 token 权重加载占比大（TP 更优），两阶段对并行策略偏好存在根本性差异

#### [[96894468eb44631a32d7ebd56f9892c7|FastTree: Optimizing Attention Kernel and Runtime for Tree-Structured LLM Inference]]
- **作者**：Zaifeng Pan et al. (Pittsburgh / AWS)
- **要解决的问题**：Radix tree KV cache 共享导致冗余 HBM 访问，tensor core 利用率极低（<1%）
- **核心贡献**：Binary edge assignment 启发式将共享前缀的 query 分组为 GEMM，5.1× kernel 加速和 2.4× 端到端吞吐提升
- **关键发现/观点**：Tree-structured KV cache 共享可指导计算优化——聚合共享前缀的 query 同时减少 HBM 流量并实现 GEMM 级 tensor core 效率

#### [[b5dc49f44db2fadc5c4d717c57f4a424|Optimizing LLM Queries in Relational Data Analytics Workloads]]
- **作者**：Shu Liu et al. (UCB / TUM / Stanford)
- **要解决的问题**：关系型数据默认行列顺序导致 LLM KV cache prefix 命中率低，最优重排序计算复杂度指数级
- **核心贡献**：GGR 算法利用贪心递归和表统计信息在 <15 秒内求解，实现 1.5-3.4× 延迟加速和最高 32% API 成本节省
- **关键发现/观点**：Batch 数据分析中表结构和内容推理前已知，可利用关系型数据的重复模式通过智能重排行序和字段序来最大化 KV cache prefix 复用

---

### 模型压缩、量化与稀疏化（8 篇）

#### [[437bc4ccafd3fc6d4289bd10940be42b|APOLLO: SGD-like Memory, AdamW-level Performance]]
- **作者**：Hanqing Zhu et al. (UT Austin / Meta)
- **要解决的问题**：AdamW 优化器占据大量显存，制约 LLM 训练的可扩展性
- **核心贡献**：将优化器状态压缩到 SGD 级别，预训练中超越 AdamW perplexity，3× 吞吐提升，首次实现 12GB 显存预训练 7B 模型
- **关键发现/观点**：AdamW 的 element-wise 学习率自适应存在大量冗余，可粗化为 channel-wise 或 tensor-wise 的结构化学习率更新而不影响性能

#### [[54dd9e0cff6d9214e20d97eb2a3bae49|HyC-LoRA: Memory Efficient LoRA Fine-tuning with Hybrid Activation Compression]]
- **作者**：Yujin Wang et al. (Tsinghua)
- **要解决的问题**：LoRA 微调中 buffered activation 占 76.6-93.3% 内存，成为瓶颈
- **核心贡献**：Intra-operator 和 inter-operator 两层混合压缩实现全算子最低 2-bit 压缩，端到端内存最高 3.97× 压缩
- **关键发现/观点**：非线性算子的 buffered activation 由主干输出和 LoRA adapter 输出聚合而成，可仅量化主干输出并在反向传播时利用已缓存的 LoRA 中间结果重构

#### [[9032e5c9ec394ce768a2fa9bdc56af6c|MiLo: Efficient Quantized MoE Inference with Mixture of Low-Rank Compensators]]
- **作者**：Beichen Huang et al.
- **要解决的问题**：MoE 模型极端 INT3 量化导致严重精度损失，INT3 缺乏硬件支持
- **核心贡献**：Calibration-free INT3 量化 + 自适应 mixture of low-rank compensators，不同层/专家根据 Kurtosis 和激活频率分配不同 rank
- **关键发现/观点**：Dense 层（attention）和 sparse expert 层的量化敏感度和误差特性不同，layer-specific low-rank compensation 可高效恢复精度

#### [[fbe2b2f74a2ece8070d8fb073717bda6|QServe: W4A8KV4 Quantization and System Co-design for Efficient LLM Serving]]
- **作者**：Yujun Lin et al. (MIT / NVIDIA)
- **要解决的问题**：INT4 量化方法在云端大 batch 场景无法加速，W4A4 中 dequantization 开销占 20-90%
- **核心贡献**：QoQ 量化算法（W4A8KV4）与 GPU 系统协同设计，A100 上 1.2-2.4× 吞吐提升，L40S 上 1.5-3.5×
- **关键发现/观点**：量化 GEMM 的效率瓶颈不在 tensor core 而在低吞吐 CUDA core（dequantization 操作），通过 compute-aware weight reordering 消除 main loop 中的 CUDA core 操作

#### [[af2d9fb5bcee19ef2dfa70d843520c97|Self-Data Distillation for Recovering Quality in Pruned Large Language Models]]
- **作者**：Vithursan Thangarasa et al.
- **要解决的问题**：结构化剪枝导致严重质量下降，标准 SFT 引入灾难性遗忘
- **核心贡献**：用未剪枝模型重写微调数据集，剪枝模型在蒸馏数据上恢复 91.2% 质量（vs SFT 的 81.7%）
- **关键发现/观点**：分布偏移是灾难性遗忘的根因，用未剪枝模型重写训练数据可保持语义等价性同时维持原始知识分布对齐

#### [[26289c647c6828e862e271ca3c490486|Rethinking Key-Value Cache Compression Techniques for Large Language Model Serving]]
- **作者**：Wei Gao et al. (NTU / Shanghai AI Lab)
- **要解决的问题**：KV cache 压缩算法的加速在生产级框架上不可复现，压缩导致响应变长抵消吞吐收益
- **核心贡献**：揭示三个被忽视的问题：生产级框架吞吐收益缩水、响应长度分布变化、特定任务质量崩溃，提供 throughput predictor 和 negative sample benchmark
- **关键发现/观点**：KV cache 压缩的实际效果不能仅通过内存缩减和整体准确率衡量——吞吐量、响应长度分布变化和逐样本质量三个维度共同决定压缩是否有效

#### [[afd6374c7f2839cba22f537f15f4f760|Efficient LLM Inference using Dynamic Input Pruning and Cache-Aware Masking]]
- **作者**：Marco Federici et al. (Qualcomm AI Research)
- **要解决的问题**：SwiGLU 激活函数缺乏硬零值稀疏性，使现有动态稀疏方法失效
- **核心贡献**：DIP-CA 无需预测器通过 magnitude-based top-K 实现 SwiGLU 动态稀疏，46% 内存减少和最高 93% 吞吐提升
- **关键发现/观点**：SwiGLU 激活值虽无硬零值，但幅度分布呈极端长尾特性，少量神经元比其他高数个数量级，可通过 magnitude-based top-K 剪枝实现稀疏

#### [[e2ec2530db26b54d0b3b060c1e4a1bda|Enabling Unstructured Sparse Acceleration on Structured Sparse Accelerators (TASD)]]
- **作者**：Geonhwa Jeong et al. (Georgia Tech / NVIDIA)
- **要解决的问题**：非结构化稀疏模型无法利用结构化稀疏硬件，为特定硬件做结构化剪枝需大量重训练
- **核心贡献**：TASD 框架将非结构化稀疏张量分解为结构化稀疏张量之和，模拟器最高 83% EDP 改善，真实 GPU 最高 39% 加速
- **关键发现/观点**：任何非结构化稀疏张量都可通过分配律分解为结构化稀疏张量之和；DNN 对内部计算的小误差具有天然容忍性，有限项数的近似分解足以维持精度

---

### 分布式训练与并行策略（10 篇）

#### [[10e400a587ff6925e4e26333b419ff55|Balancing Pipeline Parallelism with Vocabulary Parallelism]]
- **作者**：Man Tsung Yeung et al. (Sea AI Lab)
- **要解决的问题**：PP 中 vocabulary 层造成计算和内存不均衡，大 vocabulary size（256k）时尤为突出
- **核心贡献**：将 vocabulary 层沿词表维度均匀分区到所有 pipeline 设备，借助 online softmax 减少通信屏障，5-51% 吞吐提升
- **关键发现/观点**：Vocabulary 层的 softmax 通信屏障可通过 online softmax 思想重排——先局部 max/sum 再轻量级全局校正，将通信屏障从 3 个减少到 1 个

#### [[53d3f45797970d323bd8a0d379c525aa|PipeFill: Using GPUs During Bubbles in Pipeline-Parallel LLM Training]]
- **作者**：Daiyaan Arfeen et al. (CMU / AWS)
- **要解决的问题**：Pipeline bubble 导致 GPU 严重空闲，大规模训练时 bubble 比例可超 60%
- **核心贡献**：利用 bubble 执行独立 fill job，对主任务 <2% slowdown 前提下将 8K GPU 训练利用率最高提升 63%
- **关键发现/观点**：Pipeline bubble 由 PP 内部数据依赖造成，可利用空闲时段执行完全独立的任务而不影响主任务

#### [[9f73d65a4186198152357be871345771|Scaling Deep Learning Training with MPMD Pipeline Parallelism (JaxPP)]]
- **作者**：Anxhelo Xhebraj et al. (NVIDIA)
- **要解决的问题**：SPMD 模型无法表达灵活 pipeline schedule（1F1B、Interleaved），GPipe 需全量 activation 存储
- **核心贡献**：`pipeline_yield` 标注实现自动 stage 推断，单控制器 runtime 自动通信推断，比 SPMD PP 加速 51.2%
- **关键发现/观点**：Pipeline parallelism 本质是 MPMD（不同 stage 在不同时间），在 SPMD 之上分层 MPMD 调度正确分离关注点，支持灵活 schedule 同时保持 SPMD 编译

#### [[270339c997293ca2988c62f4308e389f|Rubick: Exploiting Job Reconfigurability for Deep Learning Cluster Scheduling]]
- **作者**：Xinyi Zhang et al. (ECNU / Alibaba)
- **要解决的问题**：用户静态选择执行计划不了解集群动态，不同执行计划的多维资源需求差异巨大
- **核心贡献**：首次将执行计划规划与集群资源调度统一为联合优化问题，通过轻量级性能模型，平均 JCT 降低 3.2×
- **关键发现/观点**：不同训练策略（3D parallelism、ZeRO-DP、ZeRO-Offload）对多维资源需求本质不同，同一模型在不同资源约束下最优执行计划不同，执行计划本身是可调度维度

#### [[c6ee784cbe46d854843e4c883a3321ef|TileLink: Generating Efficient Compute-Communication Overlapping Kernels using Tile-Centric Primitives]]
- **作者**：Size Zheng et al. (ByteDance Seed)
- **要解决的问题**：算子分解性能不佳，核融合需 2000 行 CUDA，MoE 等动态工作负载缺乏支持
- **核心贡献**：Tile-centric primitives 解耦通信和计算设计空间，端到端平均 1.32× 加速，MoE 最高 20.76×，代码量从 2000 行减至 200 行
- **关键发现/观点**：通信和计算的优化空间本质正交——可使用不同 tile size/order/resource mapping，解耦后各自独立优化，通过 tile 粒度 barrier 同步

#### [[e27ea0cd50b798ff8942caf9203f0992|COMET: Fine-Grained Computation-Communication Overlapping for Mixture-of-Experts]]
- **作者**：Shulai Zhang et al. (ByteDance)
- **要解决的问题**：MoE 分布式执行中通信占总时间 47%，粗粒度重叠存在效率下降和 bubble
- **核心贡献**：通过 shared tensor 依赖分析实现细粒度通信-计算流水线，单层 1.96× 加速、通信隐藏率 86.5%，已在字节万卡集群生产部署
- **关键发现/观点**：MoE 层中通信和计算的数据依赖可通过分析共享缓冲区来解耦——shared tensor 沿特定维度独立，可分解和重排序实现细粒度流水线

#### [[5431dca75a8d2abc1fb51e89e8324f10|Radius: Range-based Gradient Sparsity for Large Foundation Model Pre-training]]
- **作者**：Mingkai Zheng, Zhao Zhang (Rutgers)
- **要解决的问题**：大规模预训练中梯度同步通信是主要瓶颈，现有 top-k 与 AdamW 不兼容
- **核心贡献**：基于梯度索引时间稳定性的稀疏化通信，allgather 替换为 allreduce，19% 端到端加速且不损失性能
- **关键发现/观点**：经过约 15-20% 训练步后，具有最大绝对值的梯度在向量中的索引位置在时间上高度稳定

#### [[d5a655b8b373737b4f2aea8f78e5e754|Training Ultra Long Context Language Model with Fully Pipelined Distributed Transformer (FPDT)]]
- **作者**：Jinghan Yao et al.
- **要解决的问题**：长序列训练中 activation 显存峰值过高，现有序列并行 GPU 需求过大
- **核心贡献**：序列 chunking + host memory offloading + double buffer pipeline，16× 最大序列长度提升（8B 模型 4GPU 达 2M tokens），55%+ MFU
- **关键发现/观点**：Attention 的 O(N²) 计算复杂度足以掩盖 PCIe 搬运延迟，可通过 chunk 级在线 attention 将 KV cache offload 到 host memory 并 prefetch，近零开销

#### [[3b3889d313ba9476c12c2d77ea66b24f|REAL: Efficient RLHF Training of Large Language Models with Parameter Reallocation]]
- **作者**：Zhiyu Mei et al. (Tsinghua / OpenPsi)
- **要解决的问题**：RLHF 工作流中多模型多任务导致 GPU 空闲，固定全局并行策略无法适应异构计算需求
- **核心贡献**：参数重分配技术为不同模型函数调用动态分配 GPU 资源和并行策略，最高 3.58× 加速
- **关键发现/观点**：RLHF 工作流中不同模型函数调用具有截然不同的计算特性，可通过参数重分配在函数调用间动态重新分配 GPU 资源

#### [[a66caa1703fe34705a4368c3014c1966|LUMOS: Efficient Performance Modeling and Estimation for Large-Scale LLM Training]]
- **作者**：Mingyu Liang et al.
- **要解决的问题**：现有 trace-based 方法遗漏 inter-stream GPU 依赖，高层分析模型缺乏执行细节
- **核心贡献**：完整捕获四类任务依赖（含 inter-stream GPU events），3.3% 精度（vs dPRO 的 14%），支持 DP/PP 变更的 what-if 分析
- **关键发现/观点**：完整捕获 inter-stream GPU 依赖（cudaEventRecord/cudaStreamWaitEvent）和运行时同步对准确模拟 LLM 训练执行图至关重要

---

### 生成模型推理（3 篇）

#### [[414fd191b3246a19a55741b938380136|DiffServe: Efficiently Serving Text-to-Image Diffusion Models with Query-Aware Model Scaling]]
- **作者**：Sohaib Ahmad et al. (UMass / Adobe)
- **要解决的问题**：扩散模型 serving 无法根据 query 难度差异化处理，质量-延迟 trade-off 无法动态适配
- **核心贡献**：对抗训练的 EfficientNet discriminator 识别 easy query 用轻模型快速处理，MILP 联合优化资源分配，最高 24% FID 改善和 19-70% SLO violation 降低
- **关键发现/观点**：20-40% 的"easy" query 可用轻量 diffusion model 生成相当或更优的质量，无需使用重模型

#### [[a2fe4bb50fc6f3564cee1551d6309fea|ScaleFusion: Scalable Inference of Spatial-Temporal Diffusion Transformers for High-Resolution Long Video Generation]]
- **作者**：Jiacheng Yang et al. (Toronto / AWS)
- **要解决的问题**：ST-DiT back-to-back 依赖阻止通信-计算重叠，跨机通信占 30-50% 延迟
- **核心贡献**：Intra-layer scheduling 利用时空独立性切片，inter-layer promotion 重叠通信与前层计算，4 机平均 1.40× 加速
- **关键发现/观点**：ST-DiT 具有时空独立性——spatial 层的 temporal 切片独立，temporal 层的 spatial 切片独立，slice 级执行打破 back-to-back 依赖

#### [[f189e7580acad0fc7fd45405817ddee3|VoLUT: Efficient Volumetric Streaming Enhanced by LUT-Based Super-Resolution]]
- **作者**：Chendong Wang et al.
- **要解决的问题**：3D 点云超分辨率计算开销过大，无法在移动设备实时处理
- **核心贡献**：Dilated interpolation + LUT refinement 两阶段流水线，首次移动设备实时 3D SR（30+ FPS），比 GradPU 加速 46400×，带宽降低 70%
- **关键发现/观点**：3D SR 可分解为基本采样 + 轻量级 refinement，refinement 阶段的 DNN 可离线转化为 LUT，用查表替代推理实现数量级加速

---

### 联邦与协作学习（4 篇）

#### [[185087ea328b4f03ea8fd0c8aa96f747|Photon: Federated LLM Pre-Training]]
- **作者**：Lorenzo Sani et al. (Cambridge / Flower Labs)
- **要解决的问题**：跨数据中心训练通信瓶颈，联邦优化数据效率下降，硬件异构与容错
- **核心贡献**：首个支持 LLM 联邦预训练的完整系统，Adaptive Local Parallelism，通信量减少 64-512×，收敛速度达 DiLoCo 的 2×
- **关键发现/观点**：Federated Averaging 对超参数具有天然鲁棒性，可在每个 client 使用硬件决定的小 batch size 配合极高 learning rate，不牺牲数据效率下大幅减少通信频率

#### [[96f39c8de84678cb2a908cd52bfd7819|FedProphet: Memory-Efficient Federated Adversarial Training via Robust and Consistent Cascade Learning]]
- **作者**：Minxue Tang et al. (Duke)
- **要解决的问题**：联邦对抗训练在内存受限边缘设备上需要大模型，memory swapping 引入严重延迟
- **核心贡献**：对抗级联学习 + 强凸正则化确保每个模块鲁棒性传播到整体，Adaptive Perturbation Adjustment 协调异构客户端
- **关键发现/观点**：如果每个 cascade module 的输出特征在对抗攻击下有界扰动（通过强凸正则化），整个 backbone 模型即获得对抗鲁棒性且保持低目标不一致性

#### [[7c180af017258d239bac6248d1eb26ac|Venn: Resource Management for Collaborative Learning Jobs]]
- **作者**：Jiachen Liu et al. (UMich / UIUC)
- **要解决的问题**：协作学习多任务资源竞争被忽视，随机设备-任务匹配无法处理交叉/包含/嵌套竞争模式
- **核心贡献**：Intersection Resource Scheduling 问题建模 + 竞争感知调度 + tier-based 设备匹配，JCT 加速 1.88-2.27×
- **关键发现/观点**：CL 任务间的资源竞争呈交叉集合结构，稀缺资源应优先分配，交叉资源根据任务队列长度和已分配量的比值决策

#### [[f37347375d8b54e3203e5d24aeb6c58c|FLStore: Efficient Federated Learning Storage for Non-Training Workloads]]
- **作者**：Ahmad Faraz Khan et al.
- **要解决的问题**：FL 非训练工作负载（调度、个性化、聚类）通信延迟占总延迟 98.9%，传统缓存策略不适应 FL 顺序访问
- **核心贡献**：Serverless 缓存框架统一计算和数据平面，非训练延迟降低 50-99%、成本降低 88-99%
- **关键发现/观点**：FL 的迭代式训练使非训练工作负载具有顺序、可预测的数据访问模式，可通过定制缓存策略将命中率从 0% 提升到 98-100%

---

### 云基础设施与 ML-for-Systems（4 篇）

#### [[42e2b24104bc92d724ce45c0c2f91e1d|PROTORAIL: A Risk-Cognizant Imitation Agent for Adaptive vCPU Oversubscription in the Cloud]]
- **作者**：Lu Wang et al. (Microsoft)
- **要解决的问题**：云平台超额订阅策略无法自适应平衡收益和风险
- **核心贡献**：基于原型的模仿学习框架 + 主动知识反馈去风险化，9.4% 利用率提升和 0% hot node 率
- **关键发现/观点**：不同 VM/服务的 CPU 使用轨迹存在近似对称性，可聚类为少数几个等价类（prototypes）

#### [[9de62e421d58234dbf773abf43268630|LAVA: Lifetime-Aware VM Allocation with Learned Distributions and Adaptation to Mispredictions]]
- **作者**：Jianheng Ling et al. (Google)
- **要解决的问题**：One-shot VM lifetime 预测累积误差，点预测无法捕获多模态分布
- **核心贡献**：Reprediction 机制持续更新剩余生命周期，GBDT 模型嵌入 Borg binary（9μs），NILAS 非侵入式集成
- **关键发现/观点**：VM lifetime 应建模为概率分布并随 VM 运行持续更新，而非固定点预测，reprediction 纠正累积预测误差

#### [[e01c431bbb83153632c0dcfaf8ccda0a|A Bring-Your-Own-Model Approach for ML-Driven Storage Placement in Warehouse-Scale Computers]]
- **作者**：Chenxi Yang et al. (Google)
- **要解决的问题**：单体 ML 模型在数据中心存储放置中的部署难题——单点故障、跨层信息隔离、工作负载变化速度不匹配
- **核心贡献**：BYOM 跨层设计：应用层训练轻量模型预测 job 重要性，存储层自适应算法最终决策，最高 3.47× TCO savings
- **关键发现/观点**：将"预测工作负载特性"和"做出放置决策"分层处理比单体 ML 模型更实际、更鲁棒

#### [[d1f9e4a9f109b6e8b75ed362736f22ec|AIOpsLab: A Holistic Framework to Evaluate AI Agents for Enabling Autonomous Clouds]]
- **作者**：Yinfang Chen et al. (UIUC / Microsoft / UCB / IISc)
- **要解决的问题**：缺乏端到端 AIOps agent 评测框架，评估场景不够真实
- **核心贡献**：首个交互式 AIOps agent 评测框架，包含 Orchestrator、Agent-Cloud Interface 和双类型故障库，最优 agent 整体准确率仅 59.32%
- **关键发现/观点**：真正评估 AIOps agent 需在活的云环境中交互式评测，需包含具有真实根因的功能性故障而非仅症状注入

---

### 边缘计算与低功耗部署（4 篇）

#### [[259a5df46308d60f8454bd4adcc3b462|MEADOW: Memory-Efficient Dataflow and Data Packing for Low Power Edge LLMs]]
- **作者**：Abhishek Moitra et al. (Yale / IBM)
- **要解决的问题**：低功耗 FPGA 上 LLM 推理因带宽受限延迟严重
- **核心贡献**：TPHS 流水线 dataflow 消除片外中间数据传输 + Weight Packing 无损压缩权重，1.5-2.5× 延迟降低
- **关键发现/观点**：LLM decoder 中 Q+SM(QK^T)×V 层的中间结果在 head 维度独立，可按 token 并行、按 head 顺序流水线执行，完全消除片外中间读写

#### [[8cb5b08f912600de3de07c6503599ba8|Lightweight Software Kernels and Hardware Extensions for Efficient Sparse DNNs on MCUs]]
- **作者**：Francesco Daghero et al. (PoliTO / Bologna)
- **要解决的问题**：MCU 平台缺乏高效 N:M 结构化稀疏支持，纯软件实现指令开销大
- **核心贡献**：xDecimate ISA 扩展合并索引解压 + 间接字节加载为单指令，2× 额外加速仅 5% 面积开销，集成 RISC-V CV32E40P
- **关键发现/观点**：稀疏 kernel 的瓶颈不在计算而在间接寻址——索引解压和 activation 加载，单指令合并可将内循环从 22 条减至 12 条

#### [[b0131b6ee02a00b03fc3320176fec8f5|Efficient On-Device Machine Learning with a Biologically-Plausible Forward-Only Algorithm (Bio-FO)]]
- **作者**：Baichuan Huang, Amir Aminifar (Lund University)
- **要解决的问题**：反向传播存在四个生物学不合理性，资源受限设备上能耗极高
- **核心贡献**：每层固定随机辅助分类器实现完全本地化训练，消除所有四个不合理性，能效提升最高 19.8×
- **关键发现/观点**：为每层配置固定随机矩阵作为辅助分类器，可将全局误差信号完全本地化，每层仅凭自身激活值和固定随机投影即可计算梯度更新

#### [[40b8fb4f90004405e14b1ede6ab42373|Pitot: Interference-Aware Edge Runtime Prediction with Conformal Matrix Completion]]
- **作者**：Tianshu Huang et al. (CMU / Bosch)
- **要解决的问题**：边缘系统工作负载运行时间难以准确预测，工作负载间干扰复杂
- **核心贡献**：矩阵补全 + two-tower 神经网络 + Conformalized Quantile Regression，5.2% 预测误差
- **关键发现/观点**：运行时间可在对数空间建模，干扰效应可在 embedding 空间分解为多种干扰类型的叠加

---

### 数据管道与 ML 工程（5 篇）

#### [[136b9a13861308c8948cd308ccd02658|YOUMU: Efficient Columnar Data Pipeline for LLM Training]]
- **作者**：Tianle Zhong et al. (UVA / UofT / CUHK)
- **要解决的问题**：Parquet 列式存储与训练所需的细粒度随机访问不匹配，有效带宽利用率仅 0.1%
- **核心贡献**：基于 page-level I/O 的训练数据管道，避免格式转换，内存开销比分布式内存方案低 80%
- **关键发现/观点**：以 page（KB-MB 级）为粒度进行随机访问比 column chunk（GB 级）提供数量级更高的 shuffle 随机性，同时匹配 SSD 最优随机访问粒度

#### [[703f727ec10190b2fddcf8e24f52df48|AdaParse: An Adaptive Parallel PDF Parsing and Resource Scaling Engine]]
- **作者**：Carlo Siebenschuh et al. (UChicago / Argonne)
- **要解决的问题**：没有通用 PDF 解析器兼顾质量与效率，不同 PDF 复杂度差异巨大
- **核心贡献**：层级分类流水线自动选择最适合的解析器 + DPO 对齐人类偏好，限制 5% 文档用 Nougat 下实现 17× 吞吐且质量略优
- **关键发现/观点**：大部分科学 PDF 是"简单"文档，轻量级工具可获得与计算密集型解析器相当甚至更好的质量

#### [[5321b1dabcd2be188d796c21b733e8c7|The Hidden Bloat in Machine Learning Systems (Negativa-ML)]]
- **作者**：Huaifeng Zhang, Ahmed Ali-Eldin (Chalmers)
- **要解决的问题**：ML 框架共享库中 68-91% 为 GPU 代码但现有去膨胀工具未涉及 GPU 代码分析
- **核心贡献**：通过 hook cuModuleGetFunction 检测使用的 GPU kernel，以 cubin 粒度去除未使用代码，GPU 代码缩减最高 75%
- **关键发现/观点**：所有 GPU kernel 启动都必须先经过 CPU 侧 cuModuleGetFunction 调用，可通过监控这个单一函数以极低开销检测所有使用的 kernel

#### [[7fd522b89ac21009b7bbe7560a9a5add|Supply-Chain Attacks in Machine Learning Frameworks]]
- **作者**：Yue Gao et al. (Wisconsin / Google DeepMind)
- **要解决的问题**：ML 生态特有的供应链威胁被忽视，ML 包依赖数量远超传统软件
- **核心贡献**：提出利用 Python 运行时内存共享的 ML 特定攻击，通过覆写全局/局部变量实现后门注入、管道篡改且不触发传统检测
- **关键发现/观点**：Python 的 import 机制使任何被导入的包都能访问和修改下游应用的全局对象和栈变量，形成"同等信任"的内存共享模型

#### [[8144a9d62e506af0fcdeac0e456b2710|On Distributed Larger-Than-Memory Subset Selection With Pairwise Submodular Functions]]
- **作者**：Maximilian Böther et al.
- **要解决的问题**：十亿级数据分布式子集选择无法依赖中心化机器，内存和顺序贪心计算瓶颈
- **核心贡献**：两阶段分布式算法（Bounding + Distributed Greedy），无需中心化子集组装即可扩展到 13B 数据点
- **关键发现/观点**：对 pairwise submodular 函数，utility bounds 迭代收紧时可完全分布式剪枝——当 max utility lower bound > k-th largest upper bound 时，该点必在最优子集中

---

### 图神经网络系统（3 篇）

#### [[0badcb4e95306df76a719409155e46e8|Graph Learning at Scale: Characterizing and Optimizing Pre-Propagation GNNs]]
- **作者**：Zichao Yue et al. (Cornell / NVIDIA)
- **要解决的问题**：PP-GNN 的训练数据加载占 68-92% 训练时间，输入数据从 400GB 膨胀至 1.6TB
- **核心贡献**：高效批处理 + 双缓冲预取 + 分块重新洗牌，吞吐量比基线提升 15×，比优化过的 MP-GNN 快平均 9.9×
- **关键发现/观点**：PP-GNN 的训练数据是纯 dense tensor，不涉及图拓扑稀疏访问，可用完全不同于 MP-GNN 的数据加载策略

#### [[3619b2fc65a5538a24b48efc089da709|GSplit: Scaling Graph Neural Network Training on Large Graphs via Probabilistic Splitting]]
- **作者**：Sandeep Polisetty et al.
- **要解决的问题**：Data parallel GNN 训练中不同 GPU 采样的 micro-batch 间 k-hop 邻居大量重叠
- **核心贡献**：基于预采样统计的概率划分算法实时划分 mini-batch 为不重叠 splits，比 DGL 快最高 4.4×
- **关键发现/观点**：随机采样 mini-batch 中顶点和边被采样的概率可通过预采样统计估计，利用概率权重离线划分可在线阶段以常数时间完成 split 分配

#### [[36e2967f87c3362e37cf988781a887ad|SparseTransX: Efficient Training of Translation-Based Knowledge Graph Embeddings Using Sparse Matrix Operations]]
- **作者**：Md Saidul Hoque Anik, Ariful Azad (Texas A&M)
- **要解决的问题**：大规模知识图谱嵌入训练的 embedding 梯度计算瓶颈，scatter/gather 操作效率低
- **核心贡献**：将 KGE 训练中碎片化的 scatter/gather 统一为稀疏关联矩阵与嵌入矩阵的 SpMM，CPU 最高 5.3× 加速
- **关键发现/观点**：翻译模型的核心计算可用稀疏关联矩阵与嵌入密集矩阵的 SpMM 统一表达，天然适配高性能 SpMM 优化

---

### 智能体、仿真与决策系统（3 篇）

#### [[4f31327e046913c7238d5b671f5d820e|AI Metropolis: Scaling Large Language Model-based Multi-Agent Simulation with Out-of-Order Execution]]
- **作者**：Zhiqiang Xie et al. (Stanford / Georgia Tech)
- **要解决的问题**：LLM 多智能体仿真全局同步引入大量 false dependency，并行度低
- **核心贡献**：乱序执行思想引入仿真调度，时空依赖图消除 false dependency，500 智能体规模接近理论最优，1.3-4.15× 加速
- **关键发现/观点**：仿真中的时间因果关系可在不全局同步的情况下维护，远距离智能体的动作无需等待彼此完成

#### [[0f8426558905746fc38da5e335700aec|SwiftVI: Time-Efficient Planning and Learning with MDPs]]
- **作者**：Kasper Overgaard Mortensen et al. (Aarhus / Copenhagen)
- **要解决的问题**：Value Iteration 每次迭代对所有动作执行冗余计算，action elimination 维护上下界导致计算翻倍
- **核心贡献**：基于优先队列的高效 VI 算法系列，VIH 以最简洁设计取得最佳综合性能，动作空间大的 MDP 加速显著
- **关键发现/观点**：适当初始上界值使上界函数序列单调递减，每个动作的 Q 值也单调递减，通过 max-heap 实现隐式 action elimination

#### [[703f727ec10190b2fddcf8e24f52df48|Know Where You're Uncertain When Planning with Multimodal Foundation Models]]
- **作者**：Neel P. Bhatt et al. (UT Austin)
- **要解决的问题**：多模态基础模型中感知不确定性和决策不确定性混为一体，无法定位故障来源
- **核心贡献**：解耦感知和决策不确定性的形式化框架，conformal prediction + 形式化验证，规范满足概率提升至 95.9%
- **关键发现/观点**：感知和决策的不确定性本质不同——前者源于视觉编码置信度，后者源于计划是否满足时序逻辑规范，两者可被独立解耦量化

---

## 研究趋势分析

**LLM 推理系统是绝对主导主题。** 本届 MLSys 中 Attention 优化和 Serving 架构相关论文共 17 篇，占总数近 28%。这反映了社区的核心关切已从"如何训练"逐步转向"如何高效服务"。FlashInfer、Flex Attention 等工作试图建立统一的 Attention 编程抽象，而非继续手写 kernel 的军备竞赛；SampleAttention、LServe 则聚焦长上下文稀疏化，表明百万级 token 上下文的高效支持已成为刚需。

**Prefill/Decode 分离（Disaggregation）成为新的系统设计范式。** ThunderServe、Seesaw、NEO、FlexInfer 等多篇论文不约而同地指出 prefill（compute-intensive）和 decode（memory-bandwidth-bound）对硬件的需求本质不同，并提出了各自的分离方案。这一观察正在从学术洞察演变为工程共识。值得注意的是 Marconi 进一步将这一思想延伸至 Hybrid LLM（Attention + SSM），预示着 serving 系统需要为更多样的模型架构做准备。

**通信-计算重叠从"能做"进化为"怎么做好"。** TileLink 和 COMET 分别从编译器和系统层面解决 MoE 等复杂工作负载的细粒度通信隐藏问题。特别是 TileLink 提出的 tile-centric primitives 将通信和计算的设计空间正式解耦，COMET 已在字节跳动万卡集群生产部署。这标志着通信优化从 ad-hoc 的手工实现走向系统化、可编程的方向。

**量化和稀疏化进入"系统协同设计"阶段。** QServe 揭示了量化 GEMM 的真正瓶颈在 CUDA core 而非 tensor core，TASD 用数学分解桥接非结构化稀疏和结构化硬件，DIP 攻克了 SwiGLU 的动态稀疏难题。这些工作的共同特征是不再停留在算法层面的压缩率/精度 trade-off，而是深入到硬件执行层面寻找真正的性能瓶颈。Rethinking KV Cache Compression 更是直接挑战了"压缩=加速"的天真假设。

**联邦学习开始触及 LLM 预训练。** Photon 首次实现了联邦 LLM 从零预训练，标志着联邦学习从传统的小模型 fine-tuning 场景向大模型预训练场景的重要突破。结合 FLStore 对非训练工作负载的优化和 Venn 对多任务资源竞争的建模，联邦学习的系统基础设施正在快速成熟。

---

## 小实验室的机会窗口

### 1. LLM Serving 的 Workload-Aware 调度与优化

- **方向描述**：针对特定工作负载模式（如关系型数据批量分析、树结构 KV 共享、SLO 异质性）设计专用调度策略
- **为什么小团队能做**：不需要训练大模型或大规模 GPU 集群，核心是调度算法和系统设计。可以在单机或小集群上验证。分析性工作（如 Rethinking KV Cache Compression）也不需要大量资源
- **哪些论文指向了这个空白**：Optimizing LLM Queries 证明了利用数据结构特征优化 prefix caching 的巨大潜力；SOLA 展示了 iteration 级细粒度调度的收益；Rethinking KV Cache Compression 揭示了大量被忽视的负面效应
- **具体 open problems**：
  - 面向 RAG 场景的 KV cache 调度（大量短前缀 + 动态文档检索）
  - 多租户 SLO 异质性下的公平性与效率平衡
  - KV cache 压缩算法的自适应选择（不同 query 类型选择不同压缩策略）

### 2. Attention 稀疏模式的自动发现与编译

- **方向描述**：自动分析 attention 矩阵的稀疏模式，生成针对性的稀疏 kernel
- **为什么小团队能做**：Flex Attention 已提供了可编程的 attention 框架，SampleAttention 和 LServe 证明了结构化稀疏模式的存在。关键贡献是分析和编译工具，不需要大量计算资源
- **哪些论文指向了这个空白**：SampleAttention 发现 column stripe + slash stripe 两种模式；LServe 区分 streaming/retrieval heads；Flex Attention 提供编程接口但未自动化模式发现
- **具体 open problems**：
  - 自动化识别不同模型/层/头的最优稀疏模式
  - 面向 Hybrid LLM（Attention + SSM）的统一稀疏策略
  - 训练过程中的稀疏模式演化规律及其对推理优化的指导

### 3. ML-for-Systems：轻量级预测模型在基础设施中的应用

- **方向描述**：将轻量级 ML 模型嵌入系统关键路径（调度器、缓存管理器、资源分配器）
- **为什么小团队能做**：核心是 GBDT、小型 DNN 等轻量级模型的训练和部署，不需要大模型或大量 GPU。LAVA 的 GBDT 推理仅 9μs，BYOM 使用简单的 gradient boosted trees。关键在于问题建模和系统集成
- **哪些论文指向了这个空白**：LAVA 展示了 VM lifetime reprediction 的巨大价值；BYOM 提出跨层 ML 决策的设计模式；Pitot 将矩阵补全引入性能预测
- **具体 open problems**：
  - 面向 LLM serving 的请求延迟预测（预测 TTFT/TPOT 分布而非点估计）
  - 自适应缓存准入决策（如 Marconi 的 SSM state caching 可扩展到更多场景）
  - 存储放置决策中的多层级联 ML 方法

### 4. 边缘 LLM 推理的硬件-软件协同优化

- **方向描述**：面向资源受限设备（FPGA、NPU、MCU）的 LLM/Transformer 推理优化
- **为什么小团队能做**：不需要设计芯片，可以在现有边缘硬件或模拟器上验证。MAS-Attention 在真实 NPU 上验证，xDecimate 在 RISC-V 模拟器上验证。核心是对硬件特性的深入理解和 dataflow 优化
- **哪些论文指向了这个空白**：MEADOW 展示了 FPGA 上的 dataflow 优化空间；MAS-Attention 利用异构计算单元并行；xDecimate 证明了 ISA 扩展的巨大潜力；Bio-FO 探索了无反向传播的训练方式
- **具体 open problems**：
  - 面向 NPU 的动态稀疏 Attention（结合 DIP 和 MAS-Attention 的思路）
  - 端侧 Hybrid LLM（SSM + Attention）的 memory-aware 调度
  - 极低比特量化（2-3 bit）在边缘加速器上的高效实现

### 5. 性能建模与训练配置自动化

- **方向描述**：构建准确的训练性能模型，支持并行策略和资源配置的自动优化
- **为什么小团队能做**：LUMOS 和 Rubick 都证明了轻量级性能模型的有效性。核心是 trace 采集和执行图模拟，可在少量 GPU 上完成。成果可直接应用于降低大规模训练的调试和配置成本
- **哪些论文指向了这个空白**：LUMOS 解决了 inter-stream 依赖遗漏问题但仅支持单机；Rubick 的性能模型仅覆盖有限策略空间；PipeFill 的 bubble profiling 启发了更精细的空闲时间利用
- **具体 open problems**：
  - 跨节点分布式训练的端到端精确性能建模
  - MoE 模型的动态负载预测（expert 选择的不均匀性）
  - 训练配置空间的高效搜索（结合 Bayesian optimization 和性能模型）
