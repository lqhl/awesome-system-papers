# MLSys 2026 论文概览

> 共 53 篇论文 | 生成日期: 2026-04-05

---

## 论文分类索引

### LLM 推理服务与调度（9 篇）

#### [[02e74f10e0327ad868d138f2b4fdd6f0|From Tokens to Layers: Redefining Stall-Free Scheduling for LLM Serving with Layered Prefill]]
- **作者**：Gunjun Lee et al. (Seoul National University)
- **要解决的问题**：Chunked prefill 在 MoE 模型中沿 token 维度切分 prompt，导致每个 chunk 重复遍历所有层并重复加载 expert 权重，造成严重的带宽浪费。
- **核心贡献**：提出 layered prefill，将调度切分维度从 token 转向 layer，每层只处理完整 prompt 一次，expert load traffic 减少 39%，TTFT 降低 70%。
- **关键发现/观点**：沿 layer 维度切分模型，每一层只需处理完整 prompt 一次，从根本上消除了 chunk 带来的 expert 重复加载问题，同时仍能维持 stall-free decoding。

#### [[17e62166fc8586dfa4d1bc0e1742c08b|CRAFT: Cost-Aware Expert Replica Allocation with Fine-Grained Layerwise Estimations]]
- **作者**：Adrian Zhao et al. (U of Toronto / Amazon)
- **要解决的问题**：EPLB 的 uniform replication 策略在每层为每个 GPU 分配相同数量的 expert 副本，在大规模 MoE 模型中消耗大量 GPU 显存。
- **核心贡献**：通过逐层收益估算和 MCKP 动态规划求解最优副本分配，在副本数减少 7-8 倍的条件下实现接近或超越 EPLB 的吞吐量。
- **关键发现/观点**：MoE 各层的 expert 负载分布差异显著，部分层高度偏斜而另一些层均匀，复制资源应按层粒度差异化分配而非 uniform replication。

#### [[1f0e3dad99908345f7439f8ffabdffc4|HELIOS: Adaptive Model and Early-Exit Selection for Efficient LLM Inference Serving]]
- **作者**：Avinash Kumar et al. (NVIDIA / UT Austin)
- **要解决的问题**：现有 EE-LLM serving 仅依赖单一模型，无法提前退出的 token 必须遍历所有层，GPU 显存占用与 vanilla 解码相同。
- **核心贡献**：利用多模型 early exit 的互补性实现贪心层加载和动态模型切换，吞吐量提升 1.48x，显存节省 67.4%。
- **关键发现/观点**：不同模型的 early exit 具有互补性——一个模型上无法提前退出的 token 往往可在另一个模型上成功退出，且低置信度 token 的预测保持不变的概率高达 85%-92%。

#### [[202cb962ac59075b964b07152d234b70|Beyond the Buzz: A Pragmatic Take on Inference Disaggregation]]
- **作者**：Tiyasa Mitra et al. (NVIDIA)
- **要解决的问题**：缺乏系统性的大规模 disaggregated inference 设计空间探索，何时该用 disaggregation、如何做 rate matching 均不清楚。
- **核心贡献**：首个在数据中心规模系统性探索 LLM disaggregated inference 设计空间的工作，通过模拟数十万个设计点揭示收益取决于流量模式和模型规模。
- **关键发现/观点**：Disaggregation 的收益本质上来自将 prefill 和 decode 解耦使每个阶段能独立选择最优的并行策略和 batch size；模型越大、GPU 越多，优势越明显。

#### [[a97da629b098b75c294dffdc3e463904|BatchLLM: Optimizing Large Batched LLM Inference with Global Prefix Sharing and Throughput-oriented Token Batching]]
- **作者**：Zhen Zheng et al. (Microsoft / ISCAS)
- **要解决的问题**：大批量离线推理中 LRU-based prefix caching 无法实现全局最优 KV 复用，token batching 不充分导致 GPU 利用率低。
- **核心贡献**：利用所有 prompt 提前已知的全局信息，提出显式 prefix 识别、throughput-oriented token batching 和 fused attention kernel，microbenchmark 加速 1.3x-10.8x。
- **关键发现/观点**：在大批量/离线场景中所有 prompt 特征处理前就已知，可利用全局信息做 ahead-of-time 的 prefix 识别和请求重排，远优于运行时的隐式 LRU 缓存。

#### [[d9d4f495e875a2e075a1a4a6e1b9770f|BOUTE: Cost-Efficient LLM Serving with Heterogeneous LLMs and GPUs via Multi-Objective Bayesian Optimization]]
- **作者**：Youhe Jiang et al. (Cambridge / SJTU)
- **要解决的问题**：LLM 路由策略与异构 GPU 部署配置存在循环依赖，孤立优化导致全局次优。
- **核心贡献**：用 Multi-Objective Bayesian Optimization 联合优化路由和部署配置，相比现有方案降低 15-61% 成本或延迟降至 1/2.57。
- **关键发现/观点**：小模型在消费级 GPU 上性价比更高，大模型在高端 GPU 上性价比更高——异构 GPU 部署与异构模型路由天然互补，协同可显著提升 serving 成本效率。

#### [[fc490ca45c00b1249bbe3554a4fdf6fb|MorphServe: Efficient and Workload-Aware LLM Serving via Runtime Quantized Layer Swapping and KV Cache Resizing]]
- **作者**：Zhaoyuan Su et al. (University of Virginia / Harvard)
- **要解决的问题**：LLM 推理面临动态突发负载，全精度服务在流量尖峰时 SLO 违规严重，静态量化在低负载时也承受不可逆精度退化。
- **核心贡献**：通过运行时逐层量化替换和弹性 KV cache 扩缩容的反馈控制回路，SLO 违规降低 92.45%，精度退化 <2.18%。
- **关键发现/观点**：Transformer 各层对量化的敏感度近似独立且可叠加——量化某层引入的额外 perplexity 在不同量化组合下保持近乎恒定，可离线建立固定的层替换优先级序列。

#### [[8613985ec49eb8f757ae6439e879bb2a|OptiKIT: Meeting SLOs, Slashing Hours — Automated Enterprise LLM Optimization]]
- **作者**：Nicholas Santavas et al. (eBay)
- **要解决的问题**：企业 LLM 优化依赖少数专家手动调优（80-100 小时/模型），工具碎片化，缺乏覆盖量化-评估-benchmark-调优全流程的统一框架。
- **核心贡献**：基于 Ray 的端到端 LLM 优化框架，自动化量化、评估、benchmark 和调优，最高 2.87x per-GPU 吞吐提升，工程时间缩减到 15-25 小时。
- **关键发现/观点**：LLM 优化各阶段（压缩/评估/benchmark/调优）虽技术各异，但可被抽象为统一的 staged pipeline，通过声明式配置和动态资源分配实现自动化编排。

#### [[6ea9ab1baa0efb9e19094440c317e21b|ProfInfer: An eBPF-based Fine-Grained LLM Inference Profiler]]
- **作者**：Bohua Zou et al. (TU Munich / Huawei)
- **要解决的问题**：LLM 推理引擎缺乏细粒度可观测性，现有 profiler 侵入性强（13% 开销），eBPF 与 LLM 语义脱节。
- **核心贡献**：基于 eBPF 实现 token/graph/operator 三级粒度的非侵入式 LLM 推理 profiler，<4% 开销，将系统级追踪与 LLM 推理语义对齐。
- **关键发现/观点**：llama.cpp 的分层函数调用接口可通过 eBPF uprobe 动态挂载探针，无需修改源码即可精确关联"模型语义 → 算子执行 → 硬件行为"三层信息。

### Speculative Decoding 与加速解码（6 篇）

#### [[14bfa6bb14875e45bba028a21ed38046|SpecDiff-2: Scaling Diffusion Drafter Alignment for Faster Speculative Decoding]]
- **作者**：Jameson Sandler et al. (University of Virginia)
- **要解决的问题**：Diffusion drafter 的联合分布与 AR verifier 的条件分布存在根本性对齐缺陷，现有蒸馏方法仅优化第一个位置的对齐。
- **核心贡献**：通过 train-time streak-distillation 和 test-time self-selection，实现最高 5.5x 无损加速，平均超越 EAGLE-2 约 30-55%。
- **关键发现/观点**：Diffusion drafter 的 position-wise acceptance rate 在不同位置差异显著，必须在整个 draft 窗口上优化对齐；diffusion 一次 denoising 可生成所有位置的 marginal 分布，能以近零成本采样多条 draft 路径。

#### [[6f4922f45568161a8cdf4ad2299f6d23|SparseSpec: Accelerating Large-Scale Reasoning Model Inference with Self-Speculative Decoding and Sparse Attention]]
- **作者**：Yilong Zhao et al. (UC Berkeley / MIT / UW / Cornell / Tsinghua / NVIDIA)
- **要解决的问题**：推理模型生成极长 CoT，KV-Cache 访问成为 memory-bound 瓶颈；现有 speculative decoding 使用静态 sparsity pattern 无法适应动态语义变化。
- **核心贡献**：无损、无需训练的推理加速框架，利用 verification 阶段的 full attention score 零开销指导 draft 阶段的 dynamic sparse attention，最高 2.13x 吞吐提升。
- **关键发现/观点**：Verification 阶段的 full attention 已计算了所有 token 的 attention score，可零额外开销复用为下一轮 draft 的 dynamic sparsity pattern，且注意力 pattern 在相邻步间具有时间局部性。

#### [[67c6a1e7ce56d3d6fa748ab6d9af3fd7|TiDAR: Think in Diffusion, Talk in Autoregression]]
- **作者**：Jingyu Liu et al. (University of Chicago / NVIDIA / Georgia Tech)
- **要解决的问题**：AR 模型解码阶段 memory-bound，GPU 计算利用率低；Diffusion LLM 并行解码多 token 时质量严重下降；Speculative decoding 受限于串行草拟和低接受率。
- **核心贡献**：提出序列级混合架构，在单次 forward pass 中同时完成 diffusion 并行草拟和 AR rejection sampling 验证，1.5B/8B 模型分别实现 4.71x/5.91x 吞吐加速。
- **关键发现/观点**：GPU 在 memory-bound 区间存在大量"free token slots"——在单次 forward pass 中额外携带若干 token 几乎不增加延迟，可被用于同时完成草拟和验证。

#### [[f0935e4cd5920aa6c7c996a5ee53a70f|Speculative Decoding: Performance or Illusion?]]
- **作者**：Xiaoxuan Liu et al. (UC Berkeley)
- **要解决的问题**：现有 SD 评估基于研究原型和 batch size=1，结论不可靠；不同 SD 变体缺乏系统性横向对比。
- **核心贡献**：首个在生产级引擎 (vLLM) 上的系统评估，揭示 SD 加速在现实 batch size 下显著低于理想化评估，不同方法互补，理论上界最高 4.9x。
- **关键发现/观点**：SD 的端到端加速受限于 verification 阶段的执行代价（始终是最大开销）和 token acceptance rate 的高度变异性；不同 SD 方法在不同 token 位置表现互补，自适应组合可逼近理论上界。

#### [[f899139df5e1059396431415e770c6dd|DAS: Beat the Long Tail — Distribution-Aware Speculative Decoding for RL Training]]
- **作者**：Zelei Shao et al. (UIUC / UCSD / Together AI / PrimeIntellect / Stanford)
- **要解决的问题**：RL post-training 中 rollout 阶段的长尾延迟——少数超长 trajectory 决定整个 batch makespan；神经 drafter 因 policy drift 在 RL 中失效。
- **核心贡献**：用基于 suffix tree 的非参数化 drafter 替代神经 drafter 适应 policy drift，配合长度感知 budget 分配策略，数学推理上 >50% rollout 加速。
- **关键发现/观点**：同一 prompt 在不同 RL epoch 间的 trajectory 具有显著词汇和结构相似性，近期 rollout 历史可作为非参数化 draft 的可靠来源，且长尾分布意味着应将 speculative 资源集中于长序列。

#### [[7cbbc409ec990f19c78c75bd1e06f215|CDLM: Consistency Diffusion Language Models for Faster Sampling]]
- **作者**：Minseo Kim et al. (Seoul National University / UC Berkeley / Together AI)
- **要解决的问题**：开源 Diffusion Language Models 推理慢——双向注意力无法用 KV cache，高质量生成需与序列长度相当的去噪步数。
- **核心贡献**：通过 consistency modeling 引入 DLM，同时解决 KV cache 不兼容和步数过多两大瓶颈，实现 3.6x-14.5x 延迟降低。
- **关键发现/观点**：DLM 的 block-wise 解码轨迹上存在 temporal consistency——同一 block 内不同去噪阶段的预测分布应一致，可通过 consistency 训练将多步 refinement 压缩为少步跳跃。

### Attention 机制与长上下文（7 篇）

#### [[72b32a1f754ba1c09b3695e0cb6cde7f|FlashAttention-4: Algorithm and Kernel Pipelining Co-Design for Asymmetric Hardware Scaling]]
- **作者**：Ted Zadouri et al. (Princeton / Together AI / Meta / Colfax / NVIDIA / Georgia Tech)
- **要解决的问题**：Blackwell GPU 的 tensor core 吞吐翻倍但 shared memory 带宽和指数运算单元未增长，非对称硬件扩展导致 attention 瓶颈从矩阵乘法转移到 non-matmul 操作。
- **核心贡献**：针对 Blackwell GPU 非对称硬件扩展重新设计流水线，在 B200 上达 1613 TFLOPS/s（71% 利用率），全部用 CuTe-DSL (Python) 实现。
- **关键发现/观点**：Blackwell GPU 上 tensor core 吞吐的激进扩展使 attention 的真正瓶颈不再是矩阵乘法，而是 shared memory 带宽和指数运算单元，这种非对称扩展要求算法和 kernel 联合重新设计。

#### [[5ef059938ba799aaa845e1c2e8a762bd|MAC-Attention: A Match-Amend-Complete Scheme for Fast and Accurate Attention Computation]]
- **作者**：Jinghan Yao et al. (Ohio State / Microsoft / Anyscale)
- **要解决的问题**：LLM 长上下文 decode 阶段每生成一个 token 都需从 HBM 重新读取不断增长的 KV cache，是主要延迟瓶颈。
- **核心贡献**：提出 training-free 的 Match-Amend-Complete 三阶段方案，匹配命中时实现 O(1) 复杂度，KV 访问减少高达 99%，端到端加速最高 2.6x。
- **关键发现/观点**：解码过程中相邻 token 的 query 向量在 pre-RoPE 语义空间中具有高度时间冗余性，语义相似的 query 对共享前缀产生高度相关的 attention 分布，因此可直接复用此前计算过的 attention 结果。

#### [[d82c8d1619ad8176d665453cfb2e55f0|BLASST: Dynamic Blocked Attention Sparsity via Softmax Thresholding]]
- **作者**：Jiayi Yuan et al. (Rice University / UC Davis / NVIDIA)
- **要解决的问题**：动态稀疏 attention 方法需要昂贵的预计算来确定稀疏模式，往往抵消理论加速。
- **核心贡献**：零预计算开销的动态稀疏 attention，复用 FlashAttention 的 running maximum 做 block 级剪枝，74.7% 稀疏率下 prefill 1.62x 加速。
- **关键发现/观点**：FlashAttention 的 block-wise online softmax 中已跟踪的 running maximum 可直接用于剪枝决策——若某 block 局部最大值显著低于 running maximum，该 block 对最终输出贡献接近零，无需任何额外预计算。

#### [[d3d9446802a44259755d38e6d163e820|Accelerating Sparse Attention for Visual Generative Models with Dual-Balanced Sequence Parallelism (db-SP)]]
- **作者**：Siqi Chen et al. (清华大学)
- **要解决的问题**：将 sequence parallelism 应用于 block-wise sparse attention 时，存在 head-level 和 block-level 的双层工作负载不均衡。
- **核心贡献**：通过两级 greedy partitioning 及动态策略选择，在视频生成模型上实现平均 1.25x 端到端加速和 1.40x attention 加速。
- **关键发现/观点**：Head-level 和 block-level 的 greedy partitioning 各自独立即可达到近乎完美的均衡，可将联合优化解耦为两个顺序子问题，无需昂贵的联合搜索。

#### [[e2c420d928d4bf8ce0ff2ec19b371514|MTraining: Distributed Dynamic Sparse Attention for Efficient Ultra-Long Context Training]]
- **作者**：Wenxuan Li et al. (Cambridge / Microsoft Research / Surrey)
- **要解决的问题**：动态稀疏 attention 在 Context Parallelism 下的 worker/step 级负载不均衡和通信瓶颈。
- **核心贡献**：通过 Vertical-Slash 稀疏模式 + Striped 布局负载均衡 + 层次化 ring attention 通信优化，在 32 GPU 上实现 6x 训练吞吐提升。
- **关键发现/观点**：带 RoPE 位置编码的 attention 权重在训练中呈现稳定的 Vertical-Slash 局部性模式——slash 结构源于 attention 期望值仅依赖相对位置，vertical 结构源于 outlier，且该模式传导到反向梯度矩阵。

#### [[b53b3a3d6ab90ce0268229151c9bde11|Flashlight: PyTorch Compiler Extensions to Accelerate Attention Variants]]
- **作者**：Bozhi You et al. (UT Austin / Microsoft Research / Georgia Tech)
- **要解决的问题**：FlashAttention 依赖手写 kernel 无法自动支持新 attention 变体；FlexAttention 表达能力受限；PyTorch 编译器将 GEMM 与周围计算隔离。
- **核心贡献**：通过统一 reduction IR、代数变换和 tiling 感知维度消除，自动将任意 attention 变体 fuse 成 FlashAttention 风格的高性能 Triton kernel。
- **关键发现/观点**：矩阵乘法本质上是广义 reduction 操作，可统一建模到与 pointwise/reduction 相同的 IR 框架中；一旦打破 GEMM 与其他操作的 fusion boundary，就能自动发现跨操作的 kernel fusion。

#### [[93db85ed909c13838ff95ccfa94cebd9|DistCA: Efficient Long-Context Language Model Training by Core Attention Disaggregation]]
- **作者**：Yonghao Zhuang et al. (CMU / UCSD / StepFun / UC Berkeley / MBZUAI)
- **要解决的问题**：长上下文训练中 document packing 导致 attention 计算量差异巨大，在 DP 和 PP 中产生 straggler 效应。
- **核心贡献**：将无状态、可组合的 core attention 从模型其余部分解耦，独立调度到 attention server pool，在 512 H200 GPU 上最高 1.35x 吞吐提升。
- **关键发现/观点**：Core attention 具有无状态性和可组合性——无可训练参数，中间状态极小，可在 token 粒度任意切分并重新 batch，因此可被高效 disaggregate 并独立调度。

### KV Cache 优化（3 篇）

#### [[76dc611d6ebaafc66cc0879c71b5db5c|FlexiCache: Leveraging Temporal Stability of Attention Heads for Efficient KV Cache Management]]
- **作者**：Nazmul Takbir et al. (UC Irvine)
- **要解决的问题**：长上下文+长生成场景下 KV cache 占据大量 GPU 显存；现有方法要么永久丢弃 KV 导致精度损失，要么保留全部 KV 不节省显存。
- **核心贡献**：发现 KV head 的 top-K page 选择具有模型固有的时间稳定性差异，据此分类管理，GPU 显存节省 70%、吞吐 1.38-1.55x，精度 99%+。
- **关键发现/观点**：不同 KV head 的 top-K page 选择呈现截然不同的时间稳定性——某些 head 连续步间高度重叠且缓慢衰减，另一些持续剧烈变化，且这种模式是模型固有属性，跨任务高度一致。

#### [[92cc227532d17e56e07902b254dfad10|SkipKV: Selective Skipping of KV Generation and Storage for Efficient Inference with Large Reasoning Models]]
- **作者**：Jiayi Tian et al. (UCSB / USC / Intel Labs)
- **要解决的问题**：推理模型的长 CoT 导致 KV cache 巨大；现有 token 级 eviction 在 multi-batch 下精度大幅下降，且反而导致更长的推理链。
- **核心贡献**：Training-free KV cache 压缩框架，通过句子级冗余检测跳过 KV 存储、自适应 steering 抑制冗余生成，相比 R-KV 最高 26.7% 精度提升和 9.6x 吞吐。
- **关键发现/观点**：CoT 推理的冗余存在于句子级而非 token 级——错误推理包含 1.7x 更多高相似度句子和 2.6x 更多非执行思维，因此句子粒度的语义感知 eviction 优于 token 级。

#### [[e369853df766fa44e1ed0ff613f563bd|Kitty: Accurate and Efficient 2-Bit KV Cache Quantization with Dynamic Channel-wise Precision Boost]]
- **作者**：Haojun Xia et al. (University of Sydney / UIUC / Together AI / Microsoft)
- **要解决的问题**：2-bit KV cache 量化精度严重退化，现有混合精度方案效率低且不硬件友好。
- **核心贡献**：通过 channel-wise precision boost（仅 12.5-25% channel 保持 INT4）和 dense-sparse decomposition，实现近 8x KV cache 压缩，精度退化 <2.18%，吞吐提升 2.1-4.1x。
- **关键发现/观点**：Key cache 中不同 channel 的量化敏感度差异极大——少量 channel 对注意力分数的影响远超其他 channel，只需将这些关键 channel 保持 INT4 即可恢复接近 FP16 精度。

### 模型量化与低精度计算（4 篇）

#### [[072b030ba126b2f4b2374f342be9ed44|FP8-Flow-MoE: A Casting-Free FP8 Recipe without Double Quantization Error]]
- **作者**：Fengjuan Wang et al. (Zhejiang Lab)
- **要解决的问题**：现有 FP8 MoE 训练在 GEMM 边界频繁插入 Q/DQ 转换（一次 pass 多达 12 次），侵蚀 FP8 的理论效率；简单移除 Q/DQ 会导致 double quantization error。
- **核心贡献**：通过 scaling-aware transpose（将 scaling factor 约束为 2 的幂次）消除 double quantization error，显式 cast 从 12 次降至 2 次，671B DeepSeek-V3 上最高 21% 吞吐提升。
- **关键发现/观点**：当 scaling factor 被约束为 2 的幂次时，row-wise 到 column-wise 的量化格式转换只需调整 FP8 编码的 exponent bits，无需经过 dequantize-transpose-requantize 过程，从根本上消除 double quantization error。

#### [[2723d092b63885e0d7c260cc007e8b9d|MixLLM: LLM Quantization with Global Mixed-precision between Output-features]]
- **作者**：Zhen Zheng et al. (Microsoft)
- **要解决的问题**：4-bit 量化精度差而 5-bit 缺乏硬件支持；现有 salience 识别按 layer 局部确定 outlier 比例，忽略不同 layer 对模型最终 loss 的贡献差异。
- **核心贡献**：提出 output feature 维度的全局混合精度量化（top 10% 8-bit + 其余 4-bit），在 A100 上实现 SOTA 精度（W4.4A8 PPL 增量 <0.2）和 1.88x 平均加速。
- **关键发现/观点**：不同 output feature 对模型最终 loss 的贡献差异巨大，且这种差异在全局视角下比 layer 局部视角更显著；某些 layer（如 v_proj、down_proj）集中了大量高 salience channel。

#### [[c20ad4d76fe97759aa27a0c99bff6710|IntAttention: A Fully Integer Attention Pipeline for Efficient Edge Inference]]
- **作者**：Wanli Zhong et al. (SUSTech / Peng Cheng Laboratory)
- **要解决的问题**：INT8 量化加速 QK^T 和 PV 后，softmax 路径成为瓶颈，占量化 attention 总延迟 57%-65%，打断端到端整数数据流。
- **核心贡献**：首个全整数、即插即用的 attention 流水线，通过 32 条目 UINT8 LUT 指数近似+整数归一化消除 softmax 浮点开销，在 ARMv8 上最高 3.7x 加速。
- **关键发现/观点**：Softmax 中指数函数具有内在稀疏性——实际只有少量高值 logits 主导归一化项，绝大多数元素贡献可忽略，因此可在整数域用固定分辨率 LUT 替代浮点指数运算。

#### [[d67d8ab4f4c10bf22aa353e27879133c|CAGE: Curvature-Aware Gradient Estimation for Accurate Quantization-Aware Training]]
- **作者**：Soroush Tabesh et al. (ISTA / Red Hat AI)
- **要解决的问题**：STE 在 QAT 中引入系统性梯度偏差，缺乏收敛保证，导致低比特量化精度损失严重。
- **核心贡献**：从多目标优化视角提出 Pareto 修正项，实现 W3A3 精度匹配 QuEST W4A4，方法轻量、优化器无关，具有 O(1/√T) 收敛保证。
- **关键发现/观点**：QAT 本质上是同时最小化任务损失和量化误差的多目标优化问题，两个目标通常冲突，应寻求 Pareto 最优解而非让量化点落在损失驻点上。

### 分布式训练系统（6 篇）

#### [[28dd2c7955ce926456240b2ff0100bde|AXLearn: Modular, Hardware-Agnostic Large Model Training]]
- **作者**：Mark Lee et al. (Apple / Duke University)
- **要解决的问题**：现有训练系统通过子类化实现模块化，导致新功能集成复杂度为 O(N)；系统深度绑定特定硬件。
- **核心贡献**：通过严格封装和纯组合式设计实现 O(1) 功能集成复杂度，基于 JAX/XLA 实现 GPU、TPU、Trainium 硬件无关训练，已在 Apple 内部支撑数百工程师。
- **关键发现/观点**：神经网络本质上是组合式的，用组合（composition）而非子类化（subtyping）构建系统，新功能集成复杂度可从 O(N) 降低到 O(1)。

#### [[37693cfc748049e45d87b8c7d8b9aacd|NEST: Network- and Memory-Aware Device Placement for Distributed Deep Learning]]
- **作者**：Irene Wang et al. (Georgia Tech / UW)
- **要解决的问题**：现有设备放置框架拓扑无感知、内存建模后置、搜索不可扩展，且不支持 expert parallelism 等新兴策略的联合优化。
- **核心贡献**：首个将网络拓扑、内存约束和多种并行策略统一建模的设备放置框架，实现 1.16x-2.43x 吞吐提升。
- **关键发现/观点**：并行策略可沿正交维度分为"子图级"（如 TP/EP）和"全图级"（如 PP/DP/ZeRO），前者可离线预刻画后在全局搜索中复合使用；网络拓扑通过 level-wise abstraction 恢复最优子结构性质。

#### [[7f39f8317fbdb1988ef4c628eba02591|HetRL: Efficient Reinforcement Learning for LLMs in Heterogeneous Environments]]
- **作者**：Yongjun He et al. (ETH Zurich / AWS)
- **要解决的问题**：现有 LLM RL 训练系统仅为同构环境设计，无法利用分散的异构 GPU 资源。
- **核心贡献**：首个面向异构 GPU/网络的 LLM RL 训练系统，通过多级搜索框架分解 NP-hard 联合优化问题，平均 3.17x throughput 提升。
- **关键发现/观点**：RL 工作流中不同任务（generation/inference/training）的计算/内存/通信特征截然不同，这种异构性恰好与硬件异构性形成匹配机会——将不同特征任务分配到不同能力 GPU 上可更高效利用资源。

#### [[2b44928ae11fb9384c4cf38708677c48|MoEBlaze: Breaking the Memory Wall for Efficient MoE Training on Modern GPUs]]
- **作者**：Jiyuan Zhang et al. (Meta / Thinking Machines Lab)
- **要解决的问题**：MoE token routing 需要为每个 expert 分配独立 buffer，显存占用巨大（单层约 94GB）；SwiGLU 等激活函数需 materialize 多个中间张量。
- **核心贡献**：用轻量索引数据结构替代 materialized routing buffer，配合 activation checkpoint 与 kernel fusion，单 GPU 上 MoE 训练显存最高 4x 节省和 6.2x 加速。
- **关键发现/观点**：Token routing 并不需要真正 materialize 完整的路由后 token buffer，只需维护轻量级索引数据结构，就可以通过 on-the-fly gather 直接从原始 activation tensor 读取数据。

#### [[fe9fc289c3ff0af142b6d3bead98a923|BOOST: Bottleneck-Optimized Scalable Training Framework for Low-Rank Large Language Models]]
- **作者**：Zhengyang Wang et al. (UC Santa Barbara / Argonne National Laboratory)
- **要解决的问题**：低秩 bottleneck 架构在多 GPU 训练中使用 vanilla TP 导致通信量爆炸（5-6.5x 增长）和 GPU 利用率低下。
- **核心贡献**：提出 Bottleneck-aware Tensor Parallelism (BTP)，在低秩维度放置 collective、沿大维度分片，实现 1.46-1.91x 加速（vs full-rank TP）。
- **关键发现/观点**：Bottleneck 架构在低秩维度 r 处产生天然"窄通道"，若将 TP 同步点放在这些窄通道上，通信负载从 O(d) 降至 O(r)；同时沿大维度分片保持 GEMM 在 compute-bound 区域。

#### [[c45147dee729311ef5b5c3003946c48f|PyLO: Towards Accessible Learned Optimizers in PyTorch]]
- **作者**：Paul Janson et al. (Concordia University / Mila / Eluther AI)
- **要解决的问题**：Learned optimizer（如 VeLO）仅有 JAX 实现且 per-step 计算开销极大（数百次 kernel launch），无法在主流 PyTorch 生态中使用。
- **核心贡献**：构建 PyTorch 原生的 learned optimizer 库，通过 CUDA 融合 kernel 将 optimizer step 开销降低 80-88%，并集成 HuggingFace Hub。
- **关键发现/观点**：Learned optimizer 的 per-step 瓶颈在于内存带宽而非算力——将 feature 构建、归一化和 MLP 推理融合为两个 kernel，让中间数据留在寄存器和 shared memory 中，可消除此瓶颈。

### GPU Kernel、编译器与硬件（5 篇）

#### [[2a38a4a9316c49e5a833517c45d31070|HipKittens: Fast and Furious AMD Kernels]]
- **作者**：William Hu et al. (Stanford / AMD / UCSD)
- **要解决的问题**：AMD GPU 上高性能 kernel 极度依赖手写汇编，无法规模化；编译器在 AMD 上性能不足；NVIDIA 的 wave specialization 调度模式在 AMD 静态寄存器分配下失效。
- **核心贡献**：首次系统性地为 AMD GPU 设计 tile-based C++ DSL 编程原语，包括开发者控制的寄存器调度和 chiplet-aware 缓存优化，在主流 AI 工作负载上达到或超越手写汇编性能。
- **关键发现/观点**：Tile-based 编程抽象是跨 GPU 厂商通用的，但实例化这些抽象的算法必须根据 AMD 的架构特性（静态寄存器分配、异构矩阵指令布局、chiplet 层次化缓存）重新设计。

#### [[3295c76acbf4caaed33c36b1b5fc2cb1|ParallelKittens: Systematic and Practical Simplification of Multi-GPU AI Kernels]]
- **作者**：Stuart H. Sul et al. (Stanford University)
- **要解决的问题**：缺乏通用的多 GPU kernel 设计原则，手工优化编程复杂度高，NCCL/NVSHMEM 的设计开销导致通信性能损失。
- **核心贡献**：系统分析多 GPU kernel 性能的三个关键维度，提炼 8 个核心原语和 LCSC 编程模板，用不到 50 行增量代码实现匹配或超越手工优化 kernel 的性能。
- **关键发现/观点**：多 GPU kernel 的性能由三个可解耦的设计维度决定：数据传输机制、调度策略和设计开销，每个维度都有明确的最优选择条件。

#### [[73278a4a86960eeb576a8fd4c9ec6997|Hawkeye: Reproducing GPU-Level Non-Determinism]]
- **作者**：Erez Badash et al. (Pearl Research Labs / Stanford)
- **要解决的问题**：GPU Tensor Core 的数值行为不透明，无法在 CPU 上精确复现其计算结果，阻碍了可验证机器学习方案的实现。
- **核心贡献**：通过系统化黑盒探测逆向工程了 NVIDIA Tensor Core 在多架构和多精度下的数值行为，构建 CPU 模拟器实现 100% bit-exact 复现。
- **关键发现/观点**：虽然 Tensor Core 内部实现未公开，但其数值行为（累加顺序、内部精度、舍入模式）是确定性的固定硬件逻辑，可通过精心设计的探测测试逆向工程出来。

#### [[54229abfcfa5649e7003b83dd4755294|PIKE: Optimizing PyTorch Inference with LLM-Based Multi-Agent Systems]]
- **作者**：Kirill Nagaitsev et al. (Northwestern / LBNL)
- **要解决的问题**：缺乏多智能体 PyTorch 优化系统的统一比较框架；LLM-based kernel 优化中 explore-exploit 权衡未被系统性研究。
- **核心贡献**：提出 PIKE 逻辑框架用于比较多智能体优化系统，exploit-heavy 策略配合 Error Fixing Agent 在 KernelBench 上取得 2.88x 平均加速（vs torch.compile 1.64x）。
- **关键发现/观点**：在 LLM-based kernel 优化中，exploit-heavy 策略显著优于 explore-heavy，因为前者每步做更大更激进的代码变换，配合 Error Fixing Agent 修复后能达到更高的优化峰值。

#### [[42a0e188f5033bc65bf8d78622277c4e|A Lightweight High-Throughput Collective-Capable NoC for Large-Scale ML Accelerators]]
- **作者**：Luca Colagrande et al. (ETH Zurich)
- **要解决的问题**：片上 tile-based manycore 加速器中 collective communication 缺乏硬件加速，软件 multicast/reduction 可扩展性差。
- **核心贡献**：提出 Direct Compute Access (DCA) 范式，让互连 fabric 借用 tile 内现有 FPU 执行 in-network reduction，仅 16.5% router 面积开销实现 multicast 2.9x 和 reduction 2.5x 加速。
- **关键发现/观点**：每个 compute tile 已内置算术单元，让 NoC 直接借用这些现有计算资源执行 in-network reduction，就可以以极低面积开销实现高吞吐量的片上 collective 操作，无需在 router 中复制浮点运算逻辑。

### Agent 系统与框架（4 篇）

#### [[5fd0b37cd7dbbb00f97ba6ce92bf5add|The OpenHands Software Agent SDK: A Composable and Extensible Foundation for Production Agents]]
- **作者**：Xingyao Wang et al. (All Hands AI)
- **要解决的问题**：OpenHands V0 单体架构存在强制沙箱化的灵活性缺失、可变配置导致不确定状态、缺乏可组合扩展架构。
- **核心贡献**：基于事件溯源、不可变组件和四包模块化设计的架构重构，SWE-Bench Verified 上达到 72.8%，提供类型安全工具系统和灵活 LLM 抽象。
- **关键发现/观点**：软件工程 Agent 的核心与其应用必须严格分离，Agent 组件应当是不可变的，所有可变状态应集中在唯一的会话状态对象中，这样才能实现确定性重放和跨环境一致性。

#### [[6364d3f0f495b6ab9dcf8d3b5c6e0b01|OSWorld-Human: Benchmarking the Efficiency of Computer-Use Agents]]
- **作者**：Reyna Abhyankar et al. (UCSD / Gensee AI)
- **要解决的问题**：CUA 的端到端延迟远超人类（数十分钟 vs 数分钟），缺乏系统的延迟分析和效率基准。
- **核心贡献**：首次系统分析 CUA 延迟来源（LLM 调用占 75%-94%），构建 369 个任务的人类最优轨迹数据集和 WES 效率指标。
- **关键发现/观点**：CUA 延迟主要来自 LLM/VLM 调用（规划和反思），且因 prompt 包含完整历史而随步数线性增长，后期步骤延迟可达初始步骤的 3 倍。

#### [[d645920e395fedad7bbbed0eca3fe2e0|HIPPOCAMPUS: An Efficient and Scalable Memory Module for Agentic AI]]
- **作者**：Yi Li et al. (UT Dallas / HPE Labs)
- **要解决的问题**：现有 agentic AI 记忆系统的检索延迟过高（vector search 占 47-85% 端到端时间），token 消耗过大。
- **核心贡献**：基于 Dynamic Wavelet Matrix 的记忆系统，用 binary signature + token-ID 双重表示替代 dense embedding，检索延迟降低最高 31x、token 开销降低最高 14x。
- **关键发现/观点**：LLM 以 integer token-ID 序列为原生表示，将记忆也表示为 token-ID 序列而非 dense embedding，可利用 succinct data structure 直接在压缩域上高效检索，从根本上避免 embedding 生成和向量搜索的开销。

#### [[f4b9ec30ad9f68f89b29639786cb62ef|Matrix: Peer-to-Peer Multi-Agent Synthetic Data Generation Framework]]
- **作者**：Dong Wang et al. (FAIR at Meta)
- **要解决的问题**：多 Agent 合成数据生成中，中心化 orchestrator 在并发数千至数万任务时成为性能瓶颈；批级调度中慢任务阻塞整个 batch。
- **核心贡献**：去中心化 P2P 多 Agent 框架，将编排状态序列化为消息传递，Agent 无状态化 + 行级调度消除 bubble effect，2-15x 吞吐提升。
- **关键发现/观点**：每个任务的完整状态可序列化为消息在 Agent 间传递，从而将编排职责从中心节点分散到每个 Agent 本地——Agent 无状态，编排逻辑跟随数据流动。

### LLM 驱动的自动化（3 篇）

#### [[35f4a8d465e6e1edc05f3d8ab658c551|VERIMOA: A Mixture-of-Agents Framework for Spec-to-HDL Generation]]
- **作者**：Heng Ping et al. (USC / Iowa State / Cisco AI Research)
- **要解决的问题**：现有多 agent HDL 生成框架存在噪声传播（错误逐层累积）和推理空间受限（过早收敛到局部最优）。
- **核心贡献**：提出 quality-guided caching 和 multi-path generation（用 C++/Python 作为中间表示），实现 15-30% Pass@1 提升，使 7B 小模型超越 32B 大模型。
- **关键发现/观点**：LLM 对 C++ 和 Python 等高资源语言拥有远比 HDL 丰富的参数化知识，将 spec-to-HDL 分解为 spec→高级语言→HDL 的两阶段过程，可充分利用 LLM 在高级语言上的流畅性。

#### [[e2ef524fbf3d9fe611d5a8e90fefdc9c|TritorX: Agentic Operator Generation for ML ASICs]]
- **作者**：Alec M. Hammond et al. (Meta / FAIR)
- **要解决的问题**：新加速器平台需要为数百个 PyTorch ATen 算子手写内核，成本极高。
- **核心贡献**：通过 FSM 驱动的 LLM + linter + 编译器反馈循环，为 MTIA 加速器自动生成 481 个通过全部 OpInfo 测试的 ATen 算子内核，达到 84.7% 覆盖率。
- **关键发现/观点**：LLM 不需要预先知道硬件的全部规格文档——只要有足够的编译器、linter 和调试器的执行反馈，LLM 就能通过 in-context learning 逐步蒸馏出硬件特定的 Triton 语义。

#### [[a3f390d88e4c41f2747bfa2f1b5f87db|Automated Algorithm Design for Auto-Tuning Optimizers]]
- **作者**：Floris-Jan Willemsen et al. (Leiden University)
- **要解决的问题**：Auto-tuning 的优化算法依赖人工设计和超参调优（7 天），无法自动适配搜索空间的特殊结构。
- **核心贡献**：首次将 LLM 驱动的自动算法设计引入 auto-tuning 领域，LLM 生成的优化器平均比人工设计算法提升 72.4%。
- **关键发现/观点**：LLM 具备从问题描述和搜索空间信息中提取结构特征并生成定制化优化策略的能力，将 LLM 代码生成与进化算法选择机制结合可自动发现比人工设计更优的优化器。

### 联邦学习与隐私计算（3 篇）

#### [[3988c7f88ebcb58c6ce932b957b6f332|ProToken: Token-Level Attribution for Federated Large Language Models]]
- **作者**：Waris Gill et al. (Virginia Tech / U of Minnesota)
- **要解决的问题**：联邦 LLM 中自回归生成的归因难题——LLM 生成变长 token 序列且 token 之间存在级联依赖，追踪所有神经元的 provenance 计算量爆炸。
- **核心贡献**：利用 FL 聚合的线性性、Transformer 层级结构和梯度加权实现 per-token provenance tracking，16 种配置下达到 98.62% 平均归因准确率。
- **关键发现/观点**：FL 聚合（如 FedAvg）在参数层面是线性的，全局模型每个神经元的输出可分解为各 client 的加权和；通过梯度可自动过滤与当前 token 无关的神经元激活。

#### [[d2ddea18f00665ce8623e36bd4e3c7c5|PLayer-FL: A Principled Approach to Personalized Layer-wise Cross-Silo Federated Learning]]
- **作者**：Ahmed Elhussein et al. (Columbia University / New York Genome Center)
- **要解决的问题**：现有 Partial FL 方法以 ad-hoc 方式预设哪些层联邦化，缺乏原则性和跨架构通用性。
- **核心贡献**：提出 federation sensitivity 指标，在第一个 epoch 后自动识别泛化层与特化层的转折点，跨 CNN/Transformer/FCN 通用。
- **关键发现/观点**：相同初始化但在不同 non-IID 数据上独立训练的模型，其早期层收敛到相似的泛化解，后期层高度特化——这一转折点仅需一个 epoch 即可通过梯度信息可靠检测。

#### [[da4fb5c6e93e74d3df8527599fa62642|Zero Redundancy Distributed Learning with Differential Privacy (DP-ZeRO)]]
- **作者**：Zhiqi Bu et al. (AWS AI)
- **要解决的问题**：ZeRO 分布式优化器与差分隐私长期不兼容——hook 机制冲突、梯度分片与 per-sample gradient norm 计算矛盾。
- **核心贡献**：首次将 ZeRO1/2/3 与 DP 结合，实现 83-98% 的标准 ZeRO 吞吐量，成功扩展到 100B 参数和 256 GPU。
- **关键发现/观点**：DP 仅修改反向传播过程（per-sample gradient clipping + noising），而 ZeRO 的核心操作发生在反向传播之外或可与 DP 解耦，因此二者本质上可以兼容。

### 视频生成与流媒体系统（3 篇）

#### [[65b9eea6e1cc6bb9f0cd2a47751a186f|Reparo: Loss-Resilient Generative Codec for Video Conferencing]]
- **作者**：Tianhong Li et al. (MIT CSAIL)
- **要解决的问题**：传统视频编解码器的帧间依赖导致丢包时长时间画面冻结，FEC 冗余量难以选择。
- **核心贡献**：首个将生成式模型应用于视频会议丢包恢复的系统，通过 VQGAN token 化实现帧独立编码，消除帧间依赖和 FEC 冗余开销。
- **关键发现/观点**：视频会议场景的视觉内容高度结构化（人脸/手势），生成式模型可仅凭部分 token 和历史帧在接收端重建丢失内容，无需发送端添加任何冗余信息。

#### [[ec8956637a99787bd197eacd77acce5e|StreamDiffusionV2: A Streaming System for Dynamic and Interactive Video Generation]]
- **作者**：Tianrui Feng et al. (UT Austin / UC Berkeley / MIT / Stanford / Nunchaku AI / Shizuku AI)
- **要解决的问题**：视频扩散模型无法满足实时直播的严格延迟约束——首帧延迟高达数秒至百秒，长时间生成质量漂移。
- **核心贡献**：首个将视频扩散模型适配到实时直播场景的 training-free 推理系统，在 4xH100 上实现 14B 模型 58.28 FPS，TTFF 低至 0.5s。
- **关键发现/观点**：视频扩散模型的自回归流式推理处于 memory-bound 区域——硬件算力增速远快于带宽增速（V100→GB100 算力增 17x、带宽仅增 7x），因此通过增大 batch size 提升带宽利用率比追求计算并行更有效。

#### [[9bf31c7ff062936a96d3c8bd1f8f2ff3|EARTHSIGHT: A Distributed Framework for Low-Latency Satellite Intelligence]]
- **作者**：Ansel Kaplan Erol et al. (Georgia Tech / KAIST)
- **要解决的问题**：卫星影像分析延迟高（数小时到数天），已有轨道边缘计算系统缺乏星座级协调。
- **核心贡献**：将卫星影像分析定义为地面-轨道分布式决策问题，通过全局查询调度和星载 multi-task 推理，P90 尾延迟从 51 分钟降至 21 分钟。
- **关键发现/观点**：地面站拥有全局上下文（用户查询/历史/星座传输预测），轨道端拥有实时资源状态，两者协同可比任一端独立决策获得更优的影像优先级排序。

---

## 研究趋势分析

**MoE 系统优化成为主导主题。** MLSys 2026 中 MoE 相关论文覆盖了从训练（FP8-Flow-MoE、MoEBlaze）到推理（Layered Prefill、CRAFT）的完整栈。社区已从"MoE 是否可行"转向"如何在生产环境中高效部署 MoE"。核心挑战从模型设计转移到系统工程：expert 权重的重复加载、routing buffer 的显存占用、副本分配的资源浪费。这些问题的共性在于 MoE 的稀疏性在系统层面并未被充分利用——现有系统仍以 dense model 的方式处理 MoE 的通信和调度。

**Speculative Decoding 进入成熟反思期。** 本届会议同时出现了 SD 的新方法（SpecDiff-2、SparseSpec、TiDAR）和系统性评估工作（SD: Performance or Illusion?）。后者揭示了 SD 在生产 batch size 下加速远低于理想化评估的现实，标志着社区从"更高 acceptance rate"转向"端到端 serving 效率"。值得注意的新方向是将 SD 引入 RL 训练的 rollout 加速（DAS），以及利用 diffusion model 做并行草拟（TiDAR、SpecDiff-2）——这些工作暗示 SD 的未来不在于单纯的 draft-verify 范式，而在于与其他生成范式的深度融合。

**Attention 优化从单点突破走向系统化。** FlashAttention-4 继续推动单 GPU attention 性能极限，但更显著的趋势是 attention 优化的系统化：BLASST 发现 FlashAttention 已有信息可零成本用于稀疏剪枝，Flashlight 将 GEMM 统一到 reduction IR 实现自动 fusion，DistCA 将 attention 作为无状态服务独立调度。这表明 attention 优化正从"写更快的 kernel"演进为"重新定义 attention 在系统中的角色"。同时，长上下文场景下的稀疏 attention 训练（MTraining）和推理（MAC-Attention、SparseSpec）形成了完整的链条。

**异构性成为系统设计的第一性原则。** 多篇论文的核心洞察都建立在"异构性"之上：HetRL 利用任务-硬件异构性匹配、BOUTE 利用模型-GPU 异构性互补、MorphServe 利用层间量化敏感度异构性做动态适配、FlexiCache 利用 KV head 时间稳定性异构性做差异化管理。这种从"假设同构"到"拥抱异构"的范式转变正在渗透到训练、推理和部署的各个环节。

**Agent 基础设施开始关注效率与可扩展性。** Agent 领域从功能展示转向工程优化：HIPPOCAMPUS 将检索延迟降低 31x，Matrix 用 P2P 架构消除 orchestrator 瓶颈，OSWorld-Human 首次量化 CUA 的效率差距。这些工作表明 Agent 系统正在从"能不能做"过渡到"能不能在生产环境中做"——延迟、吞吐量和资源效率开始成为核心评价指标。

---

## 小实验室的机会窗口

### 1. KV Cache 的语义感知压缩与管理

现有 KV cache 优化多在 token 级或 page 级操作，SkipKV 揭示了句子级冗余检测的优势，FlexiCache 发现了 head 级时间稳定性的模型固有属性，Kitty 证明了 channel 级敏感度差异。这些不同粒度的 insight 尚未被统一为一个自适应框架。

- **为什么小团队能做**：仅需少量 GPU 做推理实验，核心是分析和算法设计，不需要训练大模型
- **哪些论文指向了这个空白**：SkipKV、FlexiCache、Kitty 各自在不同粒度发现了异构性，但缺乏跨粒度的统一理论
- **具体的 open problems**：
  - 如何自动发现最优压缩粒度（token vs 句子 vs page）的选择策略？
  - 推理模型的 CoT 冗余模式是否可以在生成早期预测，从而做到 proactive 而非 reactive 的 KV 压缩？
  - FlexiCache 的 head 稳定性分类是否可以扩展到 MoE 模型的 expert-specific KV cache 管理？

### 2. LLM 驱动的 Kernel / 算子自动生成

TritorX 证明 LLM + 编译器反馈循环可以为新硬件自动生成 84.7% 的 ATen 算子，PIKE 发现 exploit-heavy 策略配合 Error Fixing Agent 可超越传统编译器。但两者都聚焦于 NVIDIA/Meta 硬件。

- **为什么小团队能做**：核心投入是 LLM API 调用和编译器集成，不需要大规模集群；可以从特定硬件（如 RISC-V 加速器、FPGA）的小算子集开始
- **哪些论文指向了这个空白**：TritorX（新硬件算子生成）、PIKE（LLM-based kernel 优化）、Automated Algorithm Design（LLM 生成优化算法）
- **具体的 open problems**：
  - TritorX 的 FSM 驱动流程能否泛化到非 Triton 后端（如 MLIR、TVM）？
  - 如何构建 kernel correctness 的形式化验证层，替代当前依赖测试用例的正确性保证？
  - Exploit-heavy 策略在什么条件下会退化？是否存在自适应的 explore-exploit 切换机制？

### 3. Speculative Decoding 的自适应组合

SD: Performance or Illusion? 揭示了不同 SD 方法在不同 token 位置的互补性，SparseSpec 展示了 verification 阶段信息的零成本复用，DAS 证明非参数化 drafter 可以适应 policy drift。但目前没有系统将这些互补方法动态组合。

- **为什么小团队能做**：基于现有开源 SD 实现（vLLM 已集成多种方法），核心是设计调度和选择策略，不需要训练新模型
- **哪些论文指向了这个空白**：SD: Performance or Illusion?（互补性分析）、SparseSpec（信息复用）、DAS（非参数化 drafter）
- **具体的 open problems**：
  - 如何在运行时根据当前 token 位置、batch size、sequence length 动态选择最优 SD 方法？
  - DAS 的 suffix tree drafter 能否从 RL rollout 场景泛化到通用推理场景？
  - 不同 SD 方法的 verification overhead 能否被共享或摊销？

### 4. 非对称硬件下的算法-系统联合设计

FlashAttention-4 因 Blackwell 的非对称扩展（compute 翻倍但 SMEM 和 SFU 没变）必须重新设计算法，HipKittens 因 AMD 的静态寄存器分配必须重新设计调度。这种"算法必须适配硬件微架构"的趋势在新一代硬件上会加剧。

- **为什么小团队能做**：可以从单个算子（如 attention、GEMM、reduce）出发，聚焦特定硬件平台做深入优化，不需要全栈系统
- **哪些论文指向了这个空白**：FlashAttention-4（Blackwell 非对称扩展）、HipKittens（AMD 特性）、IntAttention（ARM 边缘推理）
- **具体的 open problems**：
  - 如何构建硬件微架构特征的自动探测工具（类似 Hawkeye 对 Tensor Core 的逆向工程），使算法设计者无需依赖厂商文档？
  - CuTe-DSL 的 Python 编译模式能否为其他硬件后端提供类似的生产力提升？
  - 边缘设备（ARM、RISC-V）上的 LLM 推理是否需要完全不同于 GPU 的 attention 算法？

### 5. Agent 记忆与检索的高效数据结构

HIPPOCAMPUS 证明用 token-ID + succinct data structure 替代 dense embedding 可将检索延迟降低 31x。但当前方案仅覆盖精确匹配和前缀匹配，语义模糊检索能力有限。

- **为什么小团队能做**：核心是数据结构和算法设计，需要的 LLM 调用量可控；可以在开源 Agent 框架（如 OpenHands）上快速验证
- **哪些论文指向了这个空白**：HIPPOCAMPUS（token-ID 记忆）、OSWorld-Human（CUA 效率瓶颈在 LLM 调用）、Matrix（编排状态序列化）
- **具体的 open problems**：
  - 如何在 token-ID 表示上实现近似语义匹配，同时保持 succinct data structure 的效率优势？
  - Agent 记忆的写入模式（哪些信息值得存储）是否可以从任务成功/失败反馈中自动学习？
  - Matrix 的状态序列化方案能否与 HIPPOCAMPUS 的记忆系统结合，实现跨 Agent 的高效共享记忆？
