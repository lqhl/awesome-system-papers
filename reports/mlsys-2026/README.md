# Conference on Machine Learning and Systems (MLSys) 2026 论文概览

> 共 58 篇论文 | 生成日期: 2026-04-08

---

## 论文分类索引

### LLM Serving 与推理系统（8 篇）

#### [[202cb962ac59075b964b07152d234b70|Beyond the Buzz: A Pragmatic Take on Inference Disaggregation]]
- **作者**：Tiyasa Mitra et al. (NVIDIA)
- **要解决的问题**：缺乏对 disaggregated LLM inference 设计空间的系统性探索，何时该用 disaggregation、最优分片策略和 GPU 比例如何选择均不清楚。
- **核心贡献**：通过模拟数十万个设计点，系统揭示 disaggregation 收益的决定因素，提出 Chunked Pipeline Parallelism（CPP），提供清晰的设计决策框架。
- **关键发现/观点**：Disaggregation 使 prefill 和 decode 能独立选择最优并行策略和 batch size；这种独立优化空间越大（模型越大、GPU 越多），优势越明显；且固定 GPU 比例会导致严重性能退化，动态 rate matching 是必要条件。

#### [[d9d4f495e875a2e075a1a4a6e1b9770f|BOUTE: Cost-Efficient LLM Serving with Heterogeneous LLMs and GPUs via Multi-Objective Bayesian Optimization]]
- **作者**：Youhe Jiang et al. (Cambridge, SJTU)
- **要解决的问题**：路由策略（将查询分发到不同模型）和 GPU 部署配置（异构 GPU 选型）存在循环依赖，孤立优化导致全局次优。
- **核心贡献**：用多目标 Bayesian Optimization 联合求解路由策略和异构 GPU 部署配置，在相同预算下降低 39.7% 成本或延迟降至 1/2.57。
- **关键发现/观点**：小模型在消费级 GPU（RTX 5090）上比 H100 快 1.5×，大模型在 H100 上快 2×，异构 GPU 与异构模型路由天然互补，协同优化可显著提升性价比。

#### [[fc490ca45c00b1249bbe3554a4fdf6fb|MorphServe: Efficient and Workload-Aware LLM Serving via Runtime Quantized Layer Swapping and KV Cache Resizing]]
- **作者**：Zhaoyuan Su et al. (Harvard, UVA)
- **要解决的问题**：全精度模型在突发负载下 SLO 违规严重，静态量化在低负载时也不可逆地损失精度，现有系统无法动态调整模型精度和 KV cache 容量。
- **核心贡献**：运行时量化层替换（LayerSwapper）和弹性 KVC 扩缩容（KVResizer），SLO 违规降低 92.45%，精度退化仅 0.11%–2.18%。
- **关键发现/观点**：Transformer 各层对量化的敏感度近似独立且可叠加——量化某一层引入的额外 perplexity 在不同组合下近乎恒定，因此可离线建立固定的层替换优先级序列，运行时按序替换无需在线重新计算。

#### [[1f0e3dad99908345f7439f8ffabdffc4|HELIOS: Adaptive Model and Early-Exit Selection for Efficient LLM Inference Serving]]
- **作者**：Avinash Kumar et al. (UT Austin / NVIDIA)
- **要解决的问题**：EE-LLM serving 依赖单一模型，无法提前退出的"难 token"必须遍历所有剩余层，且需加载所有层权重而无法增大 batch size。
- **核心贡献**：利用多模型 early exit 互补性和贪心层加载策略，实现最高 15.14× batch size 增大和 1.48–2.13× 吞吐提升。
- **关键发现/观点**：在一个模型上无法提前退出的 token 往往可以在另一个模型上成功退出（联合可从 74% 提升至 92%）；低置信度 token 遍历后续层后预测仍不变的概率高达 85–92%，可安全提前退出。

#### [[8f14e45fceea167a5a36dedd4bea2543|SuperInfer: SLO-Aware Rotary Scheduling and Memory Management for LLM Inference on Superchips]]
- **作者**：Jiahuan Yu et al. (UIUC)
- **要解决的问题**：现有 LLM serving 栈在 GH200 Superchip 上 KV cache offloading 有效带宽仅约 10 GB/s（理论峰值 900 GB/s 的不到 5%），根因是 PagedAttention 的碎片化小粒度传输。
- **核心贡献**：RotaSched 旋转调度器 + DuplexKV 全双工传输引擎，将 NVLink-C2C 利用率从 5% 提升至接近硬件上限，TTFT SLO attainment 最高提升 74.7%。
- **关键发现/观点**：PagedAttention 的 layer-first 布局导致每次传输仅 64KB，核心瓶颈不在 C2C 硬件带宽而在大量小粒度 kernel launch 的 overhead；改为 block-first 布局后单次传输可达 4MB+，进入高效传输区间。

#### [[a97da629b098b75c294dffdc3e463904|BatchLLM: Optimizing Large Batched LLM Inference with Global Prefix Sharing and Throughput-oriented Token Batching]]
- **作者**：Zhen Zheng et al. (Microsoft / ISCAS)
- **要解决的问题**：vLLM 的 LRU-based implicit prefix caching 无法实现全局最优 KV 复用（token saving ratio 仅 35.8% vs 最优 58.1%），以 request 数为阈值的 batching 导致 GPU 利用率低谷。
- **核心贡献**：全局显式 prefix 识别 + throughput-oriented token batching + horizontal fused Attention kernel，在工业 workload 上加速约 1.3×，微基准测试加速 1.3×–10.8×。
- **关键发现/观点**：大批量/离线场景中所有 prompt 提前已知，可利用全局信息进行 ahead-of-time 的 prefix 识别和请求重排，远优于运行时 LRU 缓存策略；sharing degree 越高差距越大（sd=16 时 92.6% vs 6.3%）。

#### [[8613985ec49eb8f757ae6439e879bb2a|OptiKIT: Meeting SLOs, Slashing Hours: Automated Enterprise LLM Optimization]]
- **作者**：Nicholas Santavas et al. (eBay)
- **要解决的问题**：LLM 优化高度依赖少数专家，手动优化一个模型需要 80–100 小时；现有工具碎片化，无端到端统一框架。
- **核心贡献**：基于 Ray 的端到端 LLM 优化 Pipeline，将工程时间从 80–100 小时压缩至 15–25 小时，最高实现 2.87× per-GPU 吞吐提升。
- **关键发现/观点**：LLM 优化各阶段可被抽象为统一的 staged pipeline，通过声明式配置和动态资源分配实现自动化编排；SLO 惩罚项驱动的贝叶斯调优比"追求最大吞吐"更有实用价值。

#### [[6ea9ab1baa0efb9e19094440c317e21b|ProfInfer: An eBPF-based Fine-Grained LLM Inference Profiler]]
- **作者**：Bohua Zou et al. (TU Munich / Huawei / SJTU)
- **要解决的问题**：边缘 LLM 推理引擎（如 llama.cpp）缺乏 operator 级别的细粒度可观测性，现有 profiler 要么侵入性强要么与 LLM 语义脱节。
- **核心贡献**：基于 eBPF 的三层（token/graph/operator）非侵入式 LLM 推理 profiler，<4% 开销，揭示 MatMul 主导（>97%）、KV cache 增长、线程负载不均等关键洞见。
- **关键发现/观点**：llama.cpp 软件栈存在分层函数调用接口，可通过 eBPF uprobe/uretprobe 在不修改源码的情况下精确关联"模型语义 → 算子执行 → 硬件行为"三个层次。

### Speculative Decoding 与高效生成（6 篇）

#### [[14bfa6bb14875e45bba028a21ed38046|SpecDiff-2: Scaling Diffusion Drafter Alignment for Faster Speculative Decoding]]
- **作者**：Jameson Sandler et al. (University of Virginia)
- **要解决的问题**：Diffusion drafter 与 AR verifier 的分布不对齐——diffusion 学习联合分布，AR 评估逐位置条件概率，现有 AR 蒸馏方法只对齐第一个位置。
- **核心贡献**：Streak-distillation（优化整个 draft 窗口的期望接受 streak）和 self-selection acceptance，在 72B 模型上实现最高 5.5× 无损加速，超越 EAGLE-2 约 30–55%。
- **关键发现/观点**：Diffusion drafter 的 position-wise 接受率在不同位置差异显著，靠近 prefix 的早期位置对齐较好而后续位置快速退化；因此必须在整个 draft 窗口上优化对齐，而非仅优化单一位置。

#### [[67c6a1e7ce56d3d6fa748ab6d9af3fd7|TiDAR: Think in Diffusion, Talk in Autoregression]]
- **作者**：Jingyu Liu et al. (UChicago / NVIDIA)
- **要解决的问题**：AR 模型解码阶段 memory-bound，每步仅产出一个 token，GPU 计算资源大量闲置；Diffusion LLM 并行解码质量随并行度增加急剧下降。
- **核心贡献**：序列级混合架构，通过 structured attention mask 在单次 forward pass 中同时完成 diffusion 并行草拟和 AR rejection sampling 验证，1.5B 和 8B 规模分别实现 4.71× 和 5.91× 吞吐加速。
- **关键发现/观点**：GPU memory-bound 区间存在大量"free token slots"——单次 forward pass 中额外携带若干 token 几乎不增加延迟，可零成本地同时执行 diffusion 草拟和 AR 验证。

#### [[6f4922f45568161a8cdf4ad2299f6d23|SparseSpec: Accelerating Large-Scale Reasoning Model Inference with Self-Speculative Decoding and Sparse Attention]]
- **作者**：Yilong Zhao et al. (UC Berkeley / MIT / UW)
- **要解决的问题**：推理语言模型输出数万 token，KV-Cache 访问随输出长度二次增长，现有 SD 方案要么需额外训练要么使用静态 sparsity pattern 无法适应推理过程中剧烈变化的语义上下文。
- **核心贡献**：无训练、无损的 RLM 推理加速框架，利用 verification 阶段 full attention score 零开销指导 draft 阶段动态稀疏 attention（仅加载 5% KV-Cache），在 Qwen3 系列上实现最高 2.13× 吞吐提升。
- **关键发现/观点**：Self-speculative decoding 的 verification 阶段已计算所有 token 的 attention score，这些 score 可零额外开销地复用作为下一轮 draft 的动态 sparsity pattern，且注意力 pattern 具有空间局部性可稳定若干步。

#### [[f0935e4cd5920aa6c7c996a5ee53a70f|Speculative Decoding: Performance or Illusion?]]
- **作者**：Xiaoxuan Liu et al. (UC Berkeley)
- **要解决的问题**：现有 SD 评估基于研究原型而非生产级引擎，且几乎全在 batch size=1 下测试，无法反映真实部署场景。
- **核心贡献**：首个基于生产级推理引擎（vLLM）的 SD 系统性评估框架，揭示 SD 加速在高 batch size 下显著下降、verification 占 42%–95% 开销，通过 oracle 模拟量化理论上界（最高 4.9×）。
- **关键发现/观点**：SD 端到端加速受限于 verification 执行代价和 token acceptance rate 的高度变异性；不同 SD 方法（EAGLE、n-gram、draft-model）在不同 token 位置上表现互补，自适应组合可逼近 4.9× 理论上界。

#### [[f899139df5e1059396431415e770c6dd|DAS: Beat the Long Tail — Distribution-Aware Speculative Decoding for RL Training]]
- **作者**：Zelei Shao et al. (UIUC / UCSD / Together AI / Stanford)
- **要解决的问题**：RL post-training 中 rollout 阶段占训练时间超 70%，生成长度的长尾分布使少数超长 trajectory 主导 batch makespan，而神经 drafter 因 policy drift 快速失效。
- **核心贡献**：用基于 suffix tree 的非参数化 drafter（从近期 rollout 历史构建）替代神经 drafter，配合长度感知 budget 分配，在数学推理任务中实现 >50% rollout 加速。
- **关键发现/观点**：同一 prompt 在不同 RL epoch 间的 trajectory 具有显著词汇和结构相似性，近期 rollout 历史可作为高质量非参数化 draft 来源；per-problem suffix tree 随模型更新自动演化而无需重训练。

#### [[7cbbc409ec990f19c78c75bd1e06f215|CDLM: Consistency Diffusion Language Models for Faster Sampling]]
- **作者**：Minseo Kim et al. (SNU / UC Berkeley / Together AI)
- **要解决的问题**：开源 Diffusion Language Models 推理效率低下，双向注意力无法使用 KV cache，且高质量生成需要大量 refinement 步数。
- **核心贡献**：将 consistency modeling 引入 DLM，通过 block-wise causal attention 微调实现精确 KV cache，consistency-guided distillation 实现多 token 并行 finalize，延迟降低 3.6×–14.5×。
- **关键发现/观点**：DLM 的 block-wise 解码轨迹上存在 temporal consistency 特性，同一 block 内不同去噪阶段的预测分布应一致，可通过 consistency 训练将多步 refinement 压缩为少步"跳跃"。

### Attention 与 KV Cache 优化（8 篇）

#### [[72b32a1f754ba1c09b3695e0cb6cde7f|FlashAttention-4: Algorithm and Kernel Pipelining Co-Design for Asymmetric Hardware Scaling]]
- **作者**：Ted Zadouri et al. (Princeton / Together AI / Meta / NVIDIA)
- **要解决的问题**：Blackwell GPU tensor core 吞吐翻倍但 shared memory 带宽和指数运算单元提升远少，FA-3 无法直接移植。
- **核心贡献**：针对 Blackwell 非对称硬件扩展的算法-kernel 联合设计，在 B200 上达到 1613 TFLOPS/s（71% 利用率），比 cuDNN 9.13 快 1.3×，用 CuTe-DSL（Python）实现编译速度提升 20–30×。
- **关键发现/观点**：Blackwell GPU 的 tensor core 激进扩展使 attention 真正瓶颈转移到 shared memory 带宽和指数运算单元，后两者比 MMA 计算分别多耗时 25–60%，必须通过算法-kernel 联合重设计来缓解。

#### [[b53b3a3d6ab90ce0268229151c9bde11|Flashlight: PyTorch Compiler Extensions to Accelerate Attention Variants]]
- **作者**：Bozhi You et al. (UT Austin / Microsoft Research / Georgia Tech)
- **要解决的问题**：FlashAttention 依赖手写 kernel 库无法自动支持新 attention 变体；FlexAttention 的静态模板无法表达 Differential Attention、Evoformer 等更通用的 data-dependent attention。
- **核心贡献**：通过统一 Reduction IR、代数变换和 tiling 感知维度消除，自动将任意 PyTorch attention 代码 fuse 成 FlashAttention 风格的 Triton kernel；Evoformer 加速 ≥5×，端到端 AlphaFold2 推理提升 6–9%。
- **关键发现/观点**：矩阵乘法本质上是广义 reduction 操作，一旦打破 GEMM 与其他操作的 fusion boundary，可通过维度分析自动发现跨操作的 fusion 机会，无需静态模板。

#### [[d82c8d1619ad8176d665453cfb2e55f0|BLASST: Dynamic Blocked Attention Sparsity via Softmax Thresholding]]
- **作者**：Jiayi Yuan et al. (Rice / UC Davis / NVIDIA)
- **要解决的问题**：现有动态稀疏 attention 需要昂贵的预计算来确定稀疏模式，抵消理论加速收益；阈值固定无法自适应不同上下文长度。
- **核心贡献**：零预计算开销的动态稀疏 attention，复用 FlashAttention online softmax 的 running maximum 做 block 级剪枝，~75% 稀疏率下实现 1.48×–1.62× 加速。
- **关键发现/观点**：FlashAttention block 遍历时已维护 running maximum；若某 block 的局部最大值显著低于当前 running maximum（差超过 ln(λ)），该 block 对最终输出贡献接近零，可直接跳过——无需任何额外计算。

#### [[5ef059938ba799aaa845e1c2e8a762bd|MAC-Attention: A Match–Amend–Complete Scheme for Fast and Accurate Attention Computation]]
- **作者**：Jinghan Yao et al. (Ohio State / Microsoft / Anyscale)
- **要解决的问题**：长上下文 decode 阶段需反复从 HBM 读取整个 KV cache，现有压缩方法要么引入不可逆近似误差要么丢弃 token 后无法回忆。
- **核心贡献**：Match–Amend–Complete 三阶段 training-free 方案，通过在 pre-RoPE 空间匹配语义相似 query 并复用其 attention 结果，命中时 O(1) 复杂度，KV 访问减少高达 99%，端到端加速最高 2.6×。
- **关键发现/观点**：相邻 decode token 的 pre-RoPE query 向量具有高度时间冗余性，且必须在 pre-RoPE（而非 post-RoPE）空间做匹配，因为 RoPE 的位置旋转会放大语义相似 query 间的距离。

#### [[76dc611d6ebaafc66cc0879c71b5db5c|FlexiCache: Leveraging Temporal Stability of Attention Heads for Efficient KV Cache Management]]
- **作者**：Nazmul Takbir et al. (UC Irvine)
- **要解决的问题**：长上下文长生成场景下 KV cache 占大量 GPU 显存，现有 sparse attention 要么永久丢弃 KV 导致精度损失要么保留全部不节省显存。
- **核心贡献**：发现 KV head 的 top-K page 选择具有模型固有的时间稳定性差异，将 head 分为 stable（75%）和 unstable（25%），差异化管理，GPU 显存节省 70%、吞吐 1.38–1.55×。
- **关键发现/观点**：不同 attention head 的 top-K page 选择具有截然不同的时间稳定性，且这种模式是模型固有属性（跨 8 个任务平均重叠度 0.83），只需一次离线 profiling 即可确定。

#### [[e369853df766fa44e1ed0ff613f563bd|Kitty: Accurate and Efficient 2-Bit KV Cache Quantization with Dynamic Channel-wise Precision Boost]]
- **作者**：Haojun Xia et al. (University of Sydney / Together AI / Microsoft)
- **要解决的问题**：2-bit KV cache 量化导致严重精度退化（KIVI-K2V2 平均下降 15.76 分），现有混合精度方案不足以弥合差距。
- **核心贡献**：Channel-wise precision boost（仅 12.5%–25% 关键 channel 保持 INT4，其余 INT2），配合 dense-sparse decomposition，支持 8× 更大 batch size 和 2.1×–4.1× 吞吐提升。
- **关键发现/观点**：Key cache 中不同 channel 的量化敏感度差异极大，少量 channel 对注意力分数的影响远超其他 channel；仅需保留这少量关键 channel 在较高精度即可在接近 2-bit 开销下恢复接近 FP16 精度。

#### [[92cc227532d17e56e07902b254dfad10|SkipKV: Selective Skipping of KV Generation and Storage for Efficient Inference with Large Reasoning Models]]
- **作者**：Jiayi Tian et al. (UCSB / USC / Intel Labs)
- **要解决的问题**：大型推理模型的长 CoT 推理导致 KV cache 线性膨胀；现有 token 级 eviction 在 multi-batch 下精度大幅退化，且反而引发更长冗余推理链。
- **核心贡献**：句子级冗余 KV 跳过 + 自适应 steering 抑制冗余生成 + batch grouping，相比 R-KV 在 multi-batch 下最高提升 26.7% 精度、减少 48% 生成长度，吞吐提升 9.6×。
- **关键发现/观点**：错误推理输出中高相似度句子是正确输出的 1.7 倍、非执行性思维是 2.6 倍，冗余以句子粒度存在而非 token 粒度；token 级 eviction 会破坏关键推理步骤的上下文连贯性。

#### [[d3d9446802a44259755d38e6d163e820|db-SP: Accelerating Sparse Attention for Visual Generative Models with Dual-Balanced Sequence Parallelism]]
- **作者**：Siqi Chen et al. (清华大学)
- **要解决的问题**：Block-wise sparse attention 与 sequence parallelism 结合时存在双层工作负载不均衡（head-level 和 block-level），最繁忙 GPU 比平均多出 16–51% 工作量。
- **核心贡献**：两级 greedy partitioning + mask 复用 + 运行时动态策略选择，在 Wan2.1 和 CogVideoX1.5 视频生成模型上平均 1.38× attention 加速，最高 1.42× 端到端加速。
- **关键发现/观点**：Head-level 和 block-level 的 greedy partitioning 各自独立就能达到高均衡度（ρ_s ≤ 1.1 和 ≤ 1.05），联合优化可解耦为两个顺序子问题避免联合搜索；相邻 denoising step 的 sparse mask 高度相似，50 步中只需 5 次重新分区。

### MoE 系统（4 篇）

#### [[02e74f10e0327ad868d138f2b4fdd6f0|From Tokens to Layers: Redefining Stall-Free Scheduling for LLM Serving with Layered Prefill]]
- **作者**：Gunjun Lee et al. (Seoul National University)
- **要解决的问题**：Chunked prefill 在 MoE 模型中将 prompt 沿 token 维度切分，导致 expert 权重被重复加载多次，MoE 稀疏性优势被侵蚀。
- **核心贡献**：Layered Prefill 将切分维度从 token 改为 layer，每层只处理完整 prompt 一次，最多 39% expert load traffic 减少、41% 端到端延迟降低。
- **关键发现/观点**：Chunked prefill 中 prompt 被切成 N 个 chunk 每 chunk 遍历所有层加载 expert 权重，导致总加载量随 chunk 数线性增长；改为沿 layer 维度切分后每层只处理完整 prompt 一次，从根本上消除重复加载。

#### [[17e62166fc8586dfa4d1bc0e1742c08b|CRAFT: Cost-Aware Expert Replica Allocation with Fine-Grained Layerwise Estimations]]
- **作者**：Adrian Zhao et al. (Amazon / University of Toronto)
- **要解决的问题**：EPLB 等 MoE expert replication 方案对所有层均匀分配副本，在 60 层 MoE 中消耗大量 GPU 显存（KV cache 减少 75%），且边际收益递减。
- **核心贡献**：通过逐层收益估算和动态规划求解，以比 EPLB 少 7–8 倍副本实现接近甚至超越的 throughput（平均 1.14×，最高 1.2×）。
- **关键发现/观点**：MoE 各层的 expert 负载分布呈现显著差异——high-skew 层的最热 expert 负载可达均值的 27 倍，对复制收益极大；而 low-skew 层几乎无需复制，复制资源应按层粒度差异化分配。

#### [[2b44928ae11fb9384c4cf38708677c48|MoEBlaze: Breaking the Memory Wall for Efficient MoE Training on Modern GPUs]]
- **作者**：Jiyuan Zhang et al. (Meta)
- **要解决的问题**：MoE 训练中 token routing 需要为每个 expert 分配独立 buffer 存储路由后的 token，在长序列大 batch 下显存开销极大（DeepSeek 配置下单层约 94GB）。
- **核心贡献**：轻量索引数据结构替代 materialized routing buffer（on-the-fly gather）及 activation checkpoint 与 kernel fusion 联合优化，单 GPU 最高 4× 显存节省和 6.2× 训练加速。
- **关键发现/观点**：Token routing 不需要真正 materialize 完整的路由后 buffer，只需维护轻量索引（expert-token 映射），在 expert 计算时通过 on-the-fly gather 直接从原始 activation tensor 读取即可完全消除中间 routing buffer 的显存开销。

#### [[072b030ba126b2f4b2374f342be9ed44|FP8-Flow-MoE: A Casting-Free FP8 Recipe without Double Quantization Error]]
- **作者**：Fengjuan Wang et al. (浙江实验室)
- **要解决的问题**：现有 FP8 MoE 训练在 GEMM 和通信边界频繁插入 Q/DQ 转换（最多 12 次），侵蚀 FP8 理论效率；消除 Q/DQ 则引入 double quantization error。
- **核心贡献**：将 scaling factor 约束为 2 的幂次实现 casting-free FP8 数据流，显式 cast 从 12 次降至 2 次；671B DeepSeek-V3 上最高 21% 吞吐提升和 16.5 GB/GPU 内存节省。
- **关键发现/观点**：当 scaling factor 被约束为 2 的幂次时，row-wise 到 column-wise 的量化格式转换只需调整 FP8 编码的 exponent bits，无需 dequantize → transpose → requantize，从根本上消除 double quantization error。

### 分布式训练与框架（7 篇）

#### [[28dd2c7955ce926456240b2ff0100bde|AXLearn: Modular, Hardware-Agnostic Large Model Training]]
- **作者**：Mark Lee et al. (Apple / Duke University)
- **要解决的问题**：现有 ML 训练框架采用继承机制，添加新功能需修改整个层级，复杂度随模型变体数量线性增长；且系统要么绑定 GPU 要么绑定 TPU。
- **核心贡献**：纯组合式设计（Config tree + Config Modifier + Mesh Rules）实现 O(1) 功能集成复杂度，基于 JAX/XLA 支持 GPU/TPU/Trainium 硬件无关训练。
- **关键发现/观点**：神经网络本质上是组合式的，如果用组合（composition）而非子类化（subtyping）构建系统，新功能的集成复杂度可以从 O(N) 降低到 O(1)，使跨模型变体的代码复用变得可行。

#### [[37693cfc748049e45d87b8c7d8b9aacd|NEST: Network- and Memory-Aware Device Placement for Distributed Deep Learning]]
- **作者**：Irene Wang et al. (Georgia Tech / UW)
- **要解决的问题**：现有设备放置框架忽略层级化异构网络拓扑，内存约束检查后置，且搜索在 64+ GPU 时不可扩展（Alpa 需 48 小时以上）。
- **核心贡献**：Level-wise 网络抽象和结构化动态规划，在 TPU v4 和 H100 拓扑上相比 SOTA 基线实现 1.16–2.43× 吞吐提升，搜索效率比 Alpa 快 90×。
- **关键发现/观点**：分布式训练并行策略可正交分为"子图级"（tensor/expert parallelism）和"全图级"（pipeline/data/ZeRO），前者代价可离线预刻画；网络拓扑通过 level-wise 抽象映射为 DP 状态变量可恢复最优子结构性质。

#### [[93db85ed909c13838ff95ccfa94cebd9|DistCA: Efficient Long-Context Language Model Training by Core Attention Disaggregation]]
- **作者**：Yonghao Zhuang et al. (CMU / UCSD / UC Berkeley / StepFun)
- **要解决的问题**：长上下文训练中 document packing 导致 attention 计算量在 DP/PP 中分布严重不均，已有方案无法同时解决计算不均和内存不均。
- **核心贡献**：将无状态、可组合的 core attention 从模型中解耦，独立调度到 attention server pool 上执行，512 H200 GPU 上最高 1.35× 端到端训练吞吐提升。
- **关键发现/观点**：Core attention 具有无状态性（无可训练参数）和可组合性（任意 token 粒度切分后可合并为高占用率 fused kernel），这两个特性是 disaggregation 可行且高效的充分条件。

#### [[e2c420d928d4bf8ce0ff2ec19b371514|MTraining: Distributed Dynamic Sparse Attention for Efficient Ultra-Long Context Training]]
- **作者**：Wenxuan Li et al. (Cambridge / Microsoft Research / University of Surrey)
- **要解决的问题**：动态稀疏 attention 扩展到 Context Parallelism 时，不同 GPU worker 的 FLOPs 分布严重不均衡（最大/平均比达 3.17×），节点间通信带宽成为瓶颈。
- **核心贡献**：Vertical-Slash 稀疏训练模式 + Striped 布局负载均衡 + 层次化 Ring Attention 通信优化，32 A100 GPU 上将 Qwen2.5-3B 上下文从 32K 扩展到 512K 并实现 6× 训练吞吐提升。
- **关键发现/观点**：带 RoPE 位置编码的 attention 权重训练过程中呈现稳定的 Vertical-Slash 局部性模式（slash 源于期望值仅依赖相对位置，vertical 源于 outlier），该模式同时传导到反向传播梯度，使动态稀疏可无损应用于训练。

#### [[7f39f8317fbdb1988ef4c628eba02591|HetRL: Efficient Reinforcement Learning for LLMs in Heterogeneous Environments]]
- **作者**：Yongjun He et al. (ETH Zürich / AWS)
- **要解决的问题**：现有 LLM RL 训练系统仅为同构 GPU 集群设计，无法高效利用全球各地分散的异构 GPU 资源。
- **核心贡献**：首个面向异构 GPU 和网络的 LLM RL 训练系统，通过多级搜索框架结合嵌套 Successive Halving 和遗传算法，64 GPU 异构平台上平均 3.17× 吞吐提升（最高 9.17×）。
- **关键发现/观点**：RL 工作流中 generation（内存带宽瓶颈）和 training（计算瓶颈）的计算特征恰好与异构 GPU 的能力差异形成匹配机会，任务-硬件异构性对齐可比同构部署更高效。

#### [[fe9fc289c3ff0af142b6d3bead98a923|BOOST: Bottleneck-Optimized Scalable Training Framework for Low-Rank Large Language Models]]
- **作者**：Zhengyang Wang et al. (UC Santa Barbara / Argonne National Lab)
- **要解决的问题**：直接将 Megatron-LM 风格 tensor parallelism 应用于低秩 bottleneck 架构会导致通信量增加 5–6.5×、GPU arithmetic intensity 降至 full-rank 的 0.2×。
- **核心贡献**：Bottleneck-aware Tensor Parallelism（BTP），将 collective 操作放在低秩维度 r 处而非全隐藏维度 d，实现相比 full-rank TP 1.46–1.91×、相比 vanilla low-rank TP 1.87–2.27× 的加速。
- **关键发现/观点**：低秩 bottleneck 架构在维度 r 处产生天然"窄通道"；将 TP 同步点放在窄通道上可将通信负载从 O(d) 降至 O(r)，同时沿大维度 d 分片保持 GEMM reduction dimension 足够大，使计算停留在 compute-bound 区域。

#### [[da4fb5c6e93e74d3df8527599fa62642|DP-ZeRO: Zero Redundancy Distributed Learning with Differential Privacy]]
- **作者**：Zhiqi Bu et al. (AWS AI)
- **要解决的问题**：差分隐私训练无法与 ZeRO 分布式优化器兼容（hook 机制冲突、梯度分片与 per-sample gradient 矛盾），导致大模型 DP 训练在单 GPU 显存上不可行。
- **核心贡献**：DP-ZeRO 首次将 ZeRO 三个阶段与 DP 结合，实现与标准 ZeRO 相当吞吐（83–98%），支持扩展到 100B 参数、256 GPU。
- **关键发现/观点**：DP 优化仅修改反向传播（per-sample gradient clipping + noising），而 ZeRO 的 all-gather/reduce-scatter 发生在反向传播之外，二者可解耦——正确处理交互即可继承 ZeRO 全部效率优势。

### 模型量化与压缩（4 篇）

#### [[2723d092b63885e0d7c260cc007e8b9d|MixLLM: LLM Quantization with Global Mixed-precision between Output-features]]
- **作者**：Zhen Zheng et al. (Microsoft)
- **要解决的问题**：4-bit 量化在高信息密度模型上精度下降明显，现有混合精度方法按 layer 局部确定 outlier 比例，忽略不同 layer 对模型最终 loss 贡献差异。
- **核心贡献**：Output feature 维度的全局混合精度量化，通过 Taylor 展开估计 output channel 全局 salience，在 A100 上同时实现 SOTA 精度（W4.4A8 PPL 增量 <0.2）和 1.90× 加速。
- **关键发现/观点**：不同 output feature 对模型最终 loss 的贡献差异巨大，全局视角下集中在少数层（v_proj、down_proj 中 50–70% channel 被选为 8-bit，gate_proj 仅 0.73%）；output feature 维度天然解耦使混合精度计算可并行执行。

#### [[d67d8ab4f4c10bf22aa353e27879133c|CAGE: Curvature-Aware Gradient Estimation for Accurate Quantization-Aware Training]]
- **作者**：Soroush Tabesh et al. (ISTA / Red Hat AI)
- **要解决的问题**：QAT 中 STE 对非各向同性 Hessian 引入系统性梯度偏差，现有 QAT 方法的收敛上界包含不可消除常数项。
- **核心贡献**：将 QAT 重构为多目标优化（任务损失 + 量化误差的 Pareto 最优），在 STE 梯度上添加曲率感知修正项，W3A3 精度匹配 QuEST W4A4，对 AdamW/Muon/Shampoo/SOAP 均有效。
- **关键发现/观点**：STE 等效于将量化误差以恒等矩阵方式反馈，仅在损失为各向同性二次函数时精确；将 QAT 显式建模为双目标优化后，Pareto 最优点满足 ∇f(x*) + λ(x*−Q(x*)) = 0，修正项推动参数朝量化格点收敛。

#### [[c20ad4d76fe97759aa27a0c99bff6710|IntAttention: A Fully Integer Attention Pipeline for Efficient Edge Inference]]
- **作者**：Wanli Zhong et al. (SUSTech / Peng Cheng Lab)
- **要解决的问题**：INT8 量化加速 QK⊤ 和 PV 后，softmax 路径（dequantize → softmax → requantize）成为新瓶颈，占量化后 attention 总延迟的 57–65%。
- **核心贡献**：首个全整数 attention pipeline（IndexSoftmax：32 条目 UINT8 LUT 指数近似 + 整数归一化），在 ARMv8 边缘处理器上最高 3.7× 加速和 61% 能耗降低。
- **关键发现/观点**：Softmax 中指数函数具有内在稀疏性——输入减小时 exp(·) 快速趋近零，实际只有少量高值 logits 主导归一化，因此可在整数域用固定 32 条目 LUT 替代浮点指数运算。

#### [[6512bd43d9caa6e02c990b0a82652dca|HYPERTINYPW: Once-for-All Channel Mixers — Generative Compression for TinyML]]
- **作者**：Yassien Shaalan
- **要解决的问题**：在 MCU（32–64 KB flash）上部署可分离 1D CNN 时，多个 pointwise 卷积层的权重是 flash 主要瓶颈，传统量化/剪枝仅攻击单层内冗余。
- **核心贡献**：用共享微型 MLP 生成器从逐层编码在加载时一次性合成 PW 权重，6.31× 压缩（~225 kB vs 1.4 MB），PTB-XL 上 F₁ 保留 99.97%，不引入运行时推理开销。
- **关键发现/观点**：不同 PW 层的权重之间存在大量跨层冗余，可通过共享潜在基统一表示，每层只需存储微小编码向量即可在加载时重建所有 PW 权重。

### GPU Kernel、加速器与通信（5 篇）

#### [[2a38a4a9316c49e5a833517c45d31070|HipKittens: Fast and Furious AMD Kernels]]
- **作者**：William Hu et al. (Stanford / AMD / UC San Diego)
- **要解决的问题**：AMD GPU 硬件性能已达 NVIDIA 水平，但 kernel 开发依赖手写汇编，缺乏高级编程抽象，NVIDIA 上成功的优化模式在 AMD 架构上直接失效。
- **核心贡献**：提出开发者控制的寄存器调度、8-wave ping-pong / 4-wave interleave 调度模式和 chiplet-aware 缓存优化三大原语，BF16/FP8 GEMM 比 Triton 快 1.3–3.0×，attention backward 比 AITER 快最高 2.3×。
- **关键发现/观点**：Tile-based 编程抽象可跨 GPU 厂商复用，但实例化这些抽象的算法必须根据 AMD 架构特性重新设计——AMD 的静态寄存器分配使 NVIDIA 上的 wave specialization 仅达峰值 80%，chiplet 层次化缓存若不加以利用则会损失大量带宽。

#### [[3295c76acbf4caaed33c36b1b5fc2cb1|ParallelKittens: Systematic and Practical Simplification of Multi-GPU AI Kernels]]
- **作者**：Stuart H. Sul et al. (Stanford)
- **要解决的问题**：多 GPU 计算-通信重叠 kernel 缺乏通用设计原则，手工优化高度定制难以复用，NCCL/NVSHMEM 的双向同步和 peer 访问引入最高 1.79× 设计开销。
- **核心贡献**：提炼出 8 个核心原语和 LCSC 编程模板，用不到 50 行增量代码实现匹配或超越手工优化 kernel 的性能（data/tensor parallelism 最高 2.33×，sequence parallelism 最高 4.08×）。
- **关键发现/观点**：设备端通信（TMA/Register Op）只需少量 SM 即可饱和互联带宽；intra-SM overlapping 在 K ≥ 2197 时可完全隐藏通信；NCCL 双向同步和 NVSHMEM peer 访问引入 1.79× 和 4.5× 不必要开销，绕过这些库是高性能关键。

#### [[73278a4a86960eeb576a8fd4c9ec6997|Hawkeye: Reproducing GPU-Level Non-Determinism]]
- **作者**：Erez Badash et al. (Pearl Research Labs / Stanford)
- **要解决的问题**：GPU Tensor Core 的累加顺序、舍入模式、中间精度等未被文档化，导致无法在 CPU 上精确复现其计算，是可验证机器学习的核心障碍。
- **核心贡献**：通过系统化黑盒探测逆向工程 Ampere/Hopper/Lovelace 多种精度下 Tensor Core 全部数值行为，CPU 模拟器在 100,000 个随机 16×16 tile 上实现 100% bit-exact 复现。
- **关键发现/观点**：Tensor Core 的数值行为虽未公开文档但是确定性的硬件逻辑，可通过构造特殊矩阵输入的黑盒探测逐项精确揭示——例如 Ampere 采用两阶段 8+8 累加、截断舍入、24-bit 内部精度。

#### [[42a0e188f5033bc65bf8d78622277c4e|A Lightweight High-Throughput Collective-Capable NoC for Large-Scale ML Accelerators]]
- **作者**：Luca Colagrande et al. (ETH Zurich)
- **要解决的问题**：Tile-based ML 加速器片上缺乏 multicast/reduction 硬件支持，软件 collective 通信随 mesh 规模增大急剧退化。
- **核心贡献**：Direct Compute Access (DCA) 范式——让 NoC 借用 tile 内现有 FPU 执行 in-network reduction，以 16.5% router 面积开销实现 multicast 2.9×、reduction 2.5× geomean speedup。
- **关键发现/观点**：Tile 内已有算术单元可被 interconnect 直接借用（DCA），无需在 router 中复制昂贵的浮点运算逻辑即可以极低面积开销支持高吞吐的 in-network collective 操作。

#### [[c51ce410c124a10e0db5e4b97fc2af39|TransferEngine: RDMA Point-to-Point Communication for LLM Systems]]
- **作者**：Nandor Licker et al. (Perplexity AI)
- **要解决的问题**：LLM 新兴工作负载需要灵活 P2P 通信，现有方案绑定 ConnectX 专有能力，在 AWS EFA 上不可用或性能极差。
- **核心贡献**：识别 ConnectX RC 和 EFA SRD 的共同能力（可靠无序交付），构建统一 IMM_COUNTER 同步原语，支持 disaggregated KV cache 传输、RL 万亿参数权重更新（比现有框架快 100×）、MoE dispatch/combine（EP≥16 超越 DeepEP）。
- **关键发现/观点**：ConnectX RC 和 EFA SRD 虽然传输协议不同（保序 vs 不保序），但都支持"可靠的无序交付"；只要上层协议放弃消息排序依赖（改用 counter-based 完成通知），就能在两者之上构建统一抽象。

### AI for Systems（4 篇）

#### [[19ca14e7ea6328a42e0eb13d585e4c22|AccelOpt: A Self-Improving LLM Agentic System for AI Accelerator Kernel Optimization]]
- **作者**：Genghan Zhang et al. (Stanford / AWS)
- **要解决的问题**：新兴 AI 加速器（如 AWS Trainium）缺乏成熟 kernel 优化经验，人工专家难以快速积累，现有 LLM kernel 优化系统无法从自身探索中积累迁移知识。
- **核心贡献**：Beam search + 三角色 agentic workflow + 优化记忆，在 NKIBench 上将 Trainium 平均峰值吞吐量占比从 49% 提升至 61%，开源模型匹配 Claude Sonnet 4 性能但成本降低 26 倍。
- **关键发现/观点**：LLM 已内化大量通用性能优化知识（循环变换、代数化简等），即使对于陌生的新兴加速器也可通过让 LLM agent 自主探索将通用知识迁移到新硬件平台，无需人工提供硬件特定优化配方。

#### [[54229abfcfa5649e7003b83dd4755294|PIKE: Optimizing PyTorch Inference with LLM-Based Multi-Agent Systems]]
- **作者**：Kirill Nagaitsev et al. (Northwestern / LBNL)
- **要解决的问题**：缺乏系统性框架比较 LLM-based 多智能体 PyTorch kernel 优化系统的不同策略，尤其 explore-exploit 权衡如何影响优化效果。
- **核心贡献**：PIKE 逻辑框架通过消融实验发现 exploit-heavy 策略配合 Error Fixing Agent 最优，在 KernelBench H100 上取得 2.88× geomean 加速，超越 torch.compile（1.64×）和 TensorRT（1.41×）。
- **关键发现/观点**：Exploit-heavy 策略配合专门的 Error Fixing Agent 比 explore-heavy 策略效果显著更好，因为激进变换虽容易出错但经修复后能达到更高的优化峰值。

#### [[e2ef524fbf3d9fe611d5a8e90fefdc9c|TritorX: Agentic Operator Generation for ML ASICs]]
- **作者**：Alec M. Hammond et al. (Meta / FAIR)
- **要解决的问题**：为新加速器（如 MTIA ASIC）逐一手写 PyTorch ATen 算子内核成本极高，数百个算子覆盖不全导致新硬件平台实用性受阻。
- **核心贡献**：Coverage-first 的 agentic 内核生成系统，通过 FSM 驱动的 LLM + linter + 编译器反馈循环，为 MTIA 实现 84.7% ATen 算子覆盖（481/568 算子通过 20,000+ 测试），数小时内完成新加速器后端搭建。
- **关键发现/观点**：LLM 不需要预先获得完整硬件规格文档——只要有足够的编译器、linter 和调试器执行反馈，LLM 就能通过 in-context learning 逐步蒸馏出硬件特定的 Triton 语义。

#### [[a3f390d88e4c41f2747bfa2f1b5f87db|BLADE/LLaMEA: Automated Algorithm Design for Auto-Tuning Optimizers]]
- **作者**：Floris-Jan Willemsen et al. (Leiden University)
- **要解决的问题**：HPC auto-tuning 的大规模离散搜索空间使现有优化器需耗时数天的超参调优；缺乏能自动适配应用结构特征的定制化优化策略。
- **核心贡献**：首次将 LLM 驱动的自动算法设计引入 auto-tuning，LLM 生成的优化器在 4 个 GPU kernel × 6 种 GPU 上平均比人工设计算法提升 72.4%。
- **关键发现/观点**：LLM 具备从搜索空间描述中提取结构特征（离散、含约束、不规则）并据此生成定制化启发式算法的能力；最优算法均充分利用了离散邻域搜索 API，这是人工设计算法所不具备的。

### 联邦学习与隐私（3 篇）

#### [[3988c7f88ebcb58c6ce932b957b6f332|ProToken: Token-Level Attribution for Federated Large Language Models]]
- **作者**：Waris Gill et al. (Virginia Tech / UMN)
- **要解决的问题**：联邦 LLM 中无法确定哪个 client 的训练数据对某个回复贡献最大；自回归生成的 token 级联依赖使归因信号难以拆解。
- **核心贡献**：首次实现联邦 LLM 的 token 级归因，利用 FL 聚合的线性性分解各 client 贡献，在 16 种配置下达到 98.62% 平均归因准确率。
- **关键发现/观点**：FL 聚合（FedAvg）在参数层面是线性的，因此全局模型每个神经元输出可分解为各 client 对应输出的加权和；Transformer 后几层集中了最多任务相关信号，通过梯度加权内积可自动过滤无关激活。

#### [[eccbc87e4b5ce2fe28308fd9f2a7baf3|FLoRIST: Singular Value Thresholding for Efficient and Accurate Federated Fine-Tuning of Large Language Models]]
- **作者**：Hariharan Ramesh et al. (University of Arizona)
- **要解决的问题**：现有联邦 LoRA 方法要么存在聚合噪声，要么通信开销随客户端数线性增长，要么需构造完整 ΔW 矩阵导致计算开销极高（FlexLoRA 慢约 350×）。
- **核心贡献**：在低秩空间内高效执行 SVD 并用能量阈值截断，服务端计算比 FlexLoRA 快约 350×，通信量比 FLoRA 少 39×，准确率保持最优或持平。
- **关键发现/观点**：聚合后全局 LoRA 更新矩阵 ΔW 的有效维度远低于客户端总 rank——奇异值在前 8–10 个分量后快速衰减至可忽略，存在大量冗余可通过能量阈值截断大幅压缩。

#### [[d2ddea18f00665ce8623e36bd4e3c7c5|PLayer-FL: A Principled Approach to Personalized Layer-wise Cross-Silo Federated Learning]]
- **作者**：Ahmed Elhussein et al. (Columbia / New York Genome Center)
- **要解决的问题**：现有 Partial FL 方法以 ad-hoc 方式预设哪些层联邦化，无法自动适配不同架构和任务；non-IID 数据下许多客户端参与 FL 后性能反不如纯本地训练。
- **核心贡献**：基于 federation sensitivity 指标自动识别模型中泛化层与特化层的转折点，跨 CNN/Transformer/FCN 架构通用，在 7 个数据集上 F1 平均排名最优。
- **关键发现/观点**：相同初始化在不同 non-IID 数据上独立训练的模型，早期层收敛到相似的平坦区域（泛化），后期层高度分化（特化）；这一转折点在仅一个 epoch 后就能通过梯度信息可靠检测。

### Agent 与多智能体系统（4 篇）

#### [[5fd0b37cd7dbbb00f97ba6ce92bf5add|The OpenHands Software Agent SDK: A Composable and Extensible Foundation for Production Agents]]
- **作者**：Xingyao Wang et al. (All Hands AI)
- **要解决的问题**：OpenHands V0 的单体架构存在强制沙箱化不灵活、可变配置导致不确定状态、缺乏可组合扩展架构四个核心痛点。
- **核心贡献**：基于事件溯源、不可变组件和四包模块化设计的完整架构重构，在 SWE-Bench Verified 上达到 72.8%（Claude Sonnet 4.5），提供覆盖 16 项竞品独缺功能的生产级 SDK。
- **关键发现/观点**：Agent 核心组件（LLM、Tool、Agent 本身）必须不可变，所有可变状态集中在唯一的 ConversationState（事件溯源），这是实现确定性重放、故障恢复和跨环境一致性的必要条件。

#### [[6364d3f0f495b6ab9dcf8d3b5c6e0b01|OSWorld-Human: Benchmarking the Efficiency of Computer-Use Agents]]
- **作者**：Reyna Abhyankar et al. (UC San Diego / Gensee AI)
- **要解决的问题**：计算机使用代理端到端延迟远超人类，现有 benchmark 仅评估准确率，缺乏衡量路径效率的人类参考标准。
- **核心贡献**：构建 OSWorld-Human 数据集（369 任务的人类最优轨迹）和 WES 指标，揭示 LLM 规划/反思调用占 CUA 总延迟 75%–94%，最优 agent 仍比人类多走 1.4–2.7 倍步数。
- **关键发现/观点**：CUA 延迟的绝对主因是 LLM 调用（规划和反思），且随步数增加 prompt 包含完整历史导致后期步骤延迟可达早期 3 倍——这是一个随上下文线性增长的系统性瓶颈。

#### [[d645920e395fedad7bbbed0eca3fe2e0|HIPPOCAMPUS: An Efficient and Scalable Memory Module for Agentic AI]]
- **作者**：Yi Li et al. (UT Dallas / HPE Labs)
- **要解决的问题**：现有 agentic AI 记忆系统中 vector similarity search 或 graph traversal 占端到端检索时间 47–85%，精度与效率无法兼得。
- **核心贡献**：基于 Dynamic Wavelet Matrix 的双重表示（token-ID 无损内容 + binary signature 近似语义），检索延迟降低最高 31×、token 开销降低最高 14×。
- **关键发现/观点**：LLM 以整数 token-ID 序列为原生表示，将记忆也表示为 token-ID 序列并用 succinct data structure 直接在压缩域检索，可从根本上避免 embedding 生成和高维向量相似度搜索的开销。

#### [[f4b9ec30ad9f68f89b29639786cb62ef|Matrix: Peer-to-Peer Multi-Agent Synthetic Data Generation Framework]]
- **作者**：Dong Wang et al. (FAIR at Meta)
- **要解决的问题**：现有多 Agent 框架依赖中心化 orchestrator，并发数千到数万任务时成为瓶颈；批级调度导致慢任务阻塞整个 batch。
- **核心贡献**：去中心化 P2P 多 Agent 架构，将编排状态序列化为消息在无状态 Agent 间传递（行级调度），在合成数据生成场景中实现 2–15.4× 吞吐量提升。
- **关键发现/观点**：每个任务的完整状态（控制流、中间结果、对话历史）可被序列化为消息在 Agent 之间传递，从而将编排职责从中心节点分散到每个 Agent 本地——Agent 无状态、编排逻辑随数据流动，消除中心化瓶颈。

### 视觉生成与多媒体系统（2 篇）

#### [[65b9eea6e1cc6bb9f0cd2a47751a186f|Reparo: Loss-Resilient Generative Codec for Video Conferencing]]
- **作者**：Tianhong Li et al. (MIT CSAIL)
- **要解决的问题**：传统视频编解码器帧间依赖导致一帧丢失引发后续大量帧无法解码，FEC 冗余量难以选择，在有损网络上用户体验严重下降。
- **核心贡献**：首个将生成式深度学习应用于视频会议丢包恢复的系统，通过 VQGAN token 化实现帧独立编码、接收端 ViT 生成丢失 token；worst 10% PSNR 比 VP9+Tambur 高 14–16 dB。
- **关键发现/观点**：视频会议内容高度结构化（人脸/身体），生成式模型可利用对人物外貌和运动的"领域知识"仅凭部分 token 和历史帧重建丢失内容——接收端生成可完全替代发送端冗余。

#### [[ec8956637a99787bd197eacd77acce5e|StreamDiffusionV2: A Streaming System for Dynamic and Interactive Video Generation]]
- **作者**：Tianrui Feng et al. (UT Austin / UC Berkeley / Stanford / MIT)
- **要解决的问题**：现有视频扩散模型为离线系统，直接用于实时直播会导致首帧延迟高达数秒至百秒、长时生成质量漂移。
- **核心贡献**：首个将视频扩散模型适配到实时直播场景的 training-free 推理系统，4×H100 上 14B 模型 58.28 FPS、TTFF 低至 0.37s。
- **关键发现/观点**：视频扩散模型的流式推理处于 memory-bound 区域（arithmetic intensity ~0.2–0.84），增大 batch size 来提升带宽利用率比追求计算并行更有效。

### 其他系统（3 篇）

#### [[35f4a8d465e6e1edc05f3d8ab658c551|VERIMOA: A Mixture-of-Agents Framework for Spec-to-HDL Generation]]
- **作者**：Heng Ping et al. (USC / Iowa State / Cisco AI Research)
- **要解决的问题**：现有 multi-agent HDL 生成框架存在噪声传播和推理空间受限两大缺陷，LLM 本身的 HDL 知识不足限制直接生成效果。
- **核心贡献**：Quality-guided caching + multi-path generation（C++/Python 作为中间表示），在 VerilogEval 2.0 和 RTLLM 2.0 上实现 15–30% Pass@1 提升，使 7B 小模型超越 32B 模型。
- **关键发现/观点**：LLM 对 C++ 和 Python 等高资源语言的参数化知识远比 HDL 丰富，将 spec-to-HDL 分解为 spec → 高级语言 → HDL 的两阶段过程可充分利用这一优势。

#### [[9bf31c7ff062936a96d3c8bd1f8f2ff3|EARTHSIGHT: A Distributed Framework for Low-Latency Satellite Intelligence]]
- **作者**：Ansel Kaplan Erol et al. (Georgia Tech / KAIST)
- **要解决的问题**：低轨卫星每天覆盖 2 亿平方公里影像，传统先下行再分析导致数小时到数天延迟；现有星载推理系统将卫星孤立处理忽略星座级协调。
- **核心贡献**：地面站全局查询调度 + 星载多任务共享 backbone + 自适应 filter 排序三层协同，P90 尾延迟从 51 分钟降至 21 分钟，功耗降低约 65%。
- **关键发现/观点**：地面站拥有全局上下文（查询优先级、传输窗口预测），轨道端拥有实时资源状态，两者协同决策优于任一端独立决策。

#### [[c45147dee729311ef5b5c3003946c48f|PyLO: Towards Accessible Learned Optimizers in PyTorch]]
- **作者**：Paul Janson et al. (Concordia / Mila / Eleuther AI)
- **要解决的问题**：Learned optimizer 因 per-step 计算开销过大（朴素实现数百次 kernel launch）、缺乏 PyTorch 实现和权重共享机制，几乎无人在实际训练中使用。
- **核心贡献**：遵循 `torch.optim` 接口的 PyTorch 库 + 自定义 CUDA 融合 kernel（将 optimizer step 从 74–252 次 kernel launch 压缩为 2 次），开销降低 80–88%，VeLO 在 ViT-B/16 上达到 78.39%（Adam 77.22%）。
- **关键发现/观点**：Learned optimizer 的 per-step 瓶颈是内存带宽而非算力——朴素实现中中间结果反复写回 global memory；两阶段融合 kernel 让中间数据全留在寄存器和 shared memory，彻底消除内存带宽瓶颈。

---

## 研究趋势分析

**LLM 推理系统的全面深化**。MLSys 2026 最显著的趋势是 LLM 推理优化从单点技术走向全栈协同。Speculative decoding 方向出现了 5 篇论文，从 diffusion-based drafter（SpecDiff-2、TiDAR）到 training-free 动态稀疏（SparseSpec），再到针对 RL 训练场景的非参数化 drafter（DAS），以及首个生产级系统评估（"Performance or Illusion?"），表明该方向正从研究原型走向实际部署。KV cache 管理同样呈现多路径并进态势：FlexiCache 利用时间稳定性、Kitty 攻克 2-bit 量化、SkipKV 从推理模型的句子级冗余入手、MAC-Attention 发现 query 时间冗余。这些工作共同指向一个清晰的信号：KV cache 优化正从"一刀切"转向精细化的、上下文感知的管理策略。

**MoE 系统的工程化浪潮**。4 篇 MoE 论文覆盖了从训练显存（MoEBlaze）、低精度训练（FP8-Flow-MoE）到推理调度（Layered Prefill）和 expert replication（CRAFT）的完整链路。值得注意的是，这些工作的出发点都不是算法创新，而是发现现有系统软件栈在 MoE 架构上存在严重的效率缺陷——routing buffer 的显存浪费、FP8 cast 的冗余、chunked prefill 对 expert 的重复加载、均匀副本分配的浪费。这反映了社区对 MoE 的关注点正从"MoE 算法设计"转向"让 MoE 在实际硬件上高效运行"。

**AI for Systems 的方法论成熟**。4 篇 AI-for-Systems 论文（AccelOpt、PIKE、TritorX、BLADE/LLaMEA）展现了 LLM 驱动系统优化的方法论收敛：都采用 multi-agent + 编译器/执行器反馈循环的 agentic 范式，且都强调 exploit > explore。TritorX 的"coverage-first"理念尤其值得关注——LLM 不需要完整文档，只要有足够的编译器反馈就能为全新加速器生成 84.7% 的算子后端。这一结论如果泛化成立，将根本改变新硬件平台的软件栈开发模式。

**硬件感知设计成为必选项**。从 FlashAttention-4 应对 Blackwell 的非对称硬件扩展、HipKittens 为 AMD 重新设计调度模式、SuperInfer 发现 GH200 上 C2C 带宽利用率仅 5%、TransferEngine 统一 ConnectX 和 EFA 的通信抽象，到 NEST 将网络拓扑纳入设备放置，这些工作表明"硬件无关"的抽象正在被"硬件感知"的精细设计替代。通用框架提供跨平台能力（如 AXLearn），但性能关键路径必须针对具体硬件特性深度定制。

**分布式训练的新挑战**。训练系统论文的关注点从"如何分布式训练"转向更具体的约束：长上下文下的计算不均衡（DistCA、MTraining）、异构 GPU 资源利用（HetRL）、低秩架构的通信瓶颈（BOOST）、隐私约束下的分布式训练（DP-ZeRO）。这些工作的共同特征是发现"朴素应用现有并行策略"在新约束下严重失效，需要根据具体约束重新设计系统架构。

---

## 小实验室的机会窗口

### 1. 推理模型（Reasoning Model）专用 KV Cache 优化

- **方向描述**：针对推理模型（DeepSeek-R1、Qwen3 等）长 CoT 输出的特殊模式设计专用压缩和管理策略。
- **为什么小团队能做**：只需单卡或少量 GPU 即可实验，核心是对推理过程的观察和分析而非大规模工程；SkipKV 已证明句子级冗余是可利用的信号。
- **哪些论文指向了这个空白**：SkipKV 发现推理模型输出中高相似度句子和非执行性思维远多于正确输出，但仅探索了句子级跳过；FlexiCache 的 head 时间稳定性分析尚未针对推理模型验证。
- **具体 open problems**：推理模型中"有效推理步骤"与"冗余自我验证"的实时检测；不同推理策略（CoT、self-consistency、tree-of-thought）对 KV cache 访问模式的影响；结合推理结构的自适应精度分配。

### 2. LLM 驱动的自动 Kernel 优化工具

- **方向描述**：利用 LLM agent 自动优化给定 workload 的 GPU/TPU kernel，不局限于特定硬件。
- **为什么小团队能做**：核心是 prompt 工程和 agent 流程设计而非模型训练；开源 LLM 已可胜任（AccelOpt 证明开源模型匹配 Claude Sonnet 4 但成本降低 26 倍）；KernelBench 等 benchmark 提供标准评测。
- **哪些论文指向了这个空白**：AccelOpt 发现自主积累的"优化记忆"可跨 kernel 迁移；PIKE 发现 exploit-heavy + error fixing 是最优策略；TritorX 证明编译器反馈比文档更有效。
- **具体 open problems**：优化知识在不同硬件平台间的迁移能力评估；自动选择 explore vs exploit 策略的元学习；将 profiling 数据（如 ProfInfer 的输出）作为 agent 输入以指导优化方向。

### 3. 联邦学习下的高效 LLM 微调

- **方向描述**：在通信带宽受限和数据隐私约束下高效地联邦微调 LLM。
- **为什么小团队能做**：FLoRIST 的核心算法是低秩 SVD + 能量截断，数学清晰、实现简单；PLayer-FL 仅需一个 epoch 即可确定哪些层需要联邦化；实验在少量 GPU 上即可完成。
- **哪些论文指向了这个空白**：FLoRIST 发现全局 LoRA 更新的有效维度极低但实验仅限 8 客户端；ProToken 首次实现 token 级归因但仅验证了 16 种配置；PLayer-FL 的 federation sensitivity 指标尚未在 LLM 上验证。
- **具体 open problems**：FLoRIST 的能量阈值 τ 的自动选择策略；联邦 LoRA 聚合中的 rank 自适应——能否根据各 client 数据分布差异动态分配不同 rank；ProToken 归因与 PLayer-FL 层选择的结合。

### 4. Speculative Decoding 的自适应组合

- **方向描述**：根据输入和 token 位置动态选择最优 SD 策略，逼近理论上界。
- **为什么小团队能做**：不需要训练新 drafter 模型，核心是选择策略和调度逻辑；"Performance or Illusion?" 已提供 oracle 分析框架和 vLLM 集成基础。
- **哪些论文指向了这个空白**：SD 评估论文证明不同方法（EAGLE、n-gram、draft-model）在不同位置上互补，自适应组合可逼近 4.9× 上界；DAS 发现非参数化 suffix tree drafter 在 RL 场景中可匹配神经 drafter。
- **具体 open problems**：轻量级的在线策略选择（在哪个 token 位置切换到哪种 drafter）；将非参数化（suffix tree）和参数化（EAGLE）drafter 统一到一个调度框架中；生产级 batch serving 下 SD 策略选择（目前评估主要在 batch=1）。

### 5. Agent 系统的效率优化

- **方向描述**：从系统层面减少 LLM agent 的端到端延迟和 token 消耗。
- **为什么小团队能做**：不需要训练模型，核心是系统设计和 prompt 工程；HIPPOCAMPUS 仅用 CPU 原生指令即可实现 31× 检索加速；OSWorld-Human 已提供人类基准数据。
- **哪些论文指向了这个空白**：OSWorld-Human 发现 LLM 调用占 CUA 延迟 75–94% 且随上下文线性增长；HIPPOCAMPUS 证明 succinct data structure 可替代向量检索；Matrix 的 P2P 架构消除了中心化瓶颈。
- **具体 open problems**：agent 中间推理的增量式上下文管理（避免每步重传完整历史）；轻量级的行动规划缓存（相似任务的轨迹复用）；将 HIPPOCAMPUS 的 wavelet matrix 记忆集成到开源 agent 框架（如 OpenHands）中评估端到端效果。
