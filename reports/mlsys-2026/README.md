# MLSys 2026 论文概览

> 共 79 篇论文 | 生成日期: 2026-04-23

---

## 论文分类索引

### LLM 推理系统 — 调度、批处理与 disaggregation（10 篇）

#### [[02522a2b2726fb0a03bb19f2d8d9524d|Stream2LLM]]
- **作者**：Rajveer Bachkaniwala et al.
- **要解决的问题**：把 streaming context retrieval 从单请求 demo 推到多租户生产部署，需要同时应对动态负载、KV 显存竞争、append/update 两种 streaming 模式差异。
- **核心贡献**：在 vLLM v1 上实现两阶段解耦调度（priority/resource）、LCP-based cache invalidation 与硬件感知 recompute-vs-swap 成本模型，crawler/ANNS 负载 TTFT 最高 10.8–11×。
- **关键发现/观点**：多租户 streaming 场景下「调度决策」与「资源获取」必须解耦，且 append/update 两种 streaming 模式的 cache 管理可被 longest-common-prefix invalidation 这一统一抽象覆盖。

#### [[1f0e3dad99908345f7439f8ffabdffc4|HELIOS]]
- **作者**：Avinash Kumar et al.
- **要解决的问题**：Early-Exit LLM 吞吐收益远低于算力节省，原因是单模型 EE 仍需全权重驻留、无法放大 batch。
- **核心贡献**：动态候选 Model Repository + greedy 层级加载 + 置信违背计数，相对单模型 EE-LLM 吞吐 1.48×、batch 最大 15.14×，内存节省 67%。
- **关键发现/观点**：不同 EE-LLM 的早退分布互补（联合早退率从 73% 抬到 92%），且低置信 token 即便走完全部层也多半不改变预测，因此「模型选择 + 层级加载」可以运行时自适应决定。

#### [[202cb962ac59075b964b07152d234b70|Beyond the Buzz — Disaggregation]]
- **作者**：Tiyasa Mitra et al.
- **要解决的问题**：disaggregated LLM inference 缺乏在数据中心规模全空间的系统评估，难以给工程决策明确指导。
- **核心贡献**：用 NVIDIA 高保真 simulator 在数十万个设计点评估 DeepSeek-R1 / Llama-3.1 族，给出 Pareto 最优组合：prefill Chunked-Pipeline-Parallel + decode 高 TP + dynamic rate matching。
- **关键发现/观点**：Prefill 与 decode 两阶段在计算特性、SLA 维度、最优分片上差异足够显著，值得用独立硬件池分别服务，但收益高度非均匀，依赖流量模式/模型规模/SLO，必须靠全空间搜索 + 动态 rate matching 稳定拿到 Pareto 最优。

#### [[3416a75f4cea9109507cacd8e2f2aefc|Span Queries / CIDRA]]
- **作者**：Paul Castro et al.
- **要解决的问题**：vLLM 等推理服务器假设严格有序输入，对 RAG/agent/nested generation 等允许部分排列的负载缓存复用几乎失效。
- **核心贡献**：Span Query IR（带 commutativity 注释的表达式树）+ 492 行 vLLM 修改 + CIDRA ReRoPE，RAG/nested generation 微基准 TTFT 10–20×，缓解 lost-in-the-middle。
- **关键发现/观点**：chat、RAG、ITS、agentic workload 不是四类独立场景，而是同一棵带 commutativity 注释的表达式树的特例；一旦显式表达「哪些子树彼此可交换」，cache locality 与 attention locality 可用同一套高层重写规则同时优化。

#### [[8613985ec49eb8f757ae6439e879bb2a|OPTIKIT]]
- **作者**：Nicholas Santavas et al.
- **要解决的问题**：企业把 LLM 从模型部署到满足 SLO 的服务需要把量化、calibration、benchmark、tuning 串起来，现有工具只覆盖片段。
- **核心贡献**：eBay 生产框架 OPTIKIT，Ray actor 三层架构 + declarative recipe + steady-state regression + Bayesian TPE tuner，Qwen-7B / Mistral-24B / Llama-70B 上 per-GPU 吞吐 1.25–2.87×，SLO 违约减少 82%，人工工时从 80–100h 压到 15–25h。
- **关键发现/观点**：LLM 生产部署的瓶颈不是算法而是工作流——每个子任务单独看都成熟，真正稀缺的是把它们按正确顺序串起来并在 SLO 约束下自动收敛的流水线；因此标准化 + 声明化就能把专家经验物化为平台能力。

#### [[8f14e45fceea167a5a36dedd4bea2543|SuperInfer]]
- **作者**：Jiahuan Yu et al.
- **要解决的问题**：GH200 紧耦合 Superchip 让 offload 变得可行，但现有调度 SLO-unaware，vLLM PagedAttention 只能跑到 NVLink-C2C 带宽的 5%。
- **核心贡献**：RotaSched（OS 风格抢占式 rotary + Virtual Lag Time + LVF）+ DuplexKV（block-first 布局 + batched memcpy），TTFT SLO 达成率相对 vLLM 最高 +74.7%，NVLink-C2C 带宽利用率推到 95%。
- **关键发现/观点**：GH200 下 LLM 推理栈可类比为 OS——请求即线程，HBM 即缓存，DRAM 即主存；抢占应从 OOM 兜底升级为 SLO 进度驱动的主动 rotation；且 KV layout 必须从 layer-first（64KB 段）转为 block-first（≥8MB 段）才能吃满 NVLink-C2C。

#### [[ec5decca5ed3d6b8079e2e7e7bacc9f2|LAPS]]
- **作者**：Jianshu She et al.
- **要解决的问题**：PD disaggregation 假设所有 prefill 都 compute-bound，但真实多轮对话中 81% prefill 其实是 memory-bound 的短 re-prefill，长短混批导致 HoL blocking。
- **核心贡献**：LAPS 在 PD 内再做时间/空间 disaggregation，长短 prefill 独立队列 + AWD + bucketized CUDA Graph + instance pressure controller，多轮对话 RPS +20%、P99 -20%、SLO 违约近零。
- **关键发现/观点**：Prefill 阶段不是同质的——长 prefill 是 GEMM compute-bound、短 re-prefill 是 KV-cache memory-bound，两者互斥占用资源；这正是 PD disaggregation 中 prefill↔decode 张力的内部翻版，可复用同一设计哲学再拆一次。

#### [[a97da629b098b75c294dffdc3e463904|BatchLLM]]
- **作者**：Zhen Zheng et al.
- **要解决的问题**：离线大批 LLM 推理（搜索 snippet、广告等）共享大量长 prefix，vLLM radix+LRU 命中率远低于最优，且无法充分拼满 chunked prefill。
- **核心贡献**：显式全局 DP 前缀一层化 + prefix-sharing group 按 R_group 重排 + memory-centric token batching + 水平融合 prefix+distinct attention Triton kernel，A100/MI200 上相对 vLLM 1.3–10.8×。
- **关键发现/观点**：离线大批 prompt 全部事先已知，批的长度/前缀分布可一次性算清楚，因此隐式 LRU cache 完全可被显式全局的 prefix 组织方式替代；调度器有自由度刻意推迟长 prefill 以拼出高利用率 token-batch。

#### [[d9d4f495e875a2e075a1a4a6e1b9770f|BOUTE]]
- **作者**：Youhe Jiang et al.
- **要解决的问题**：异构模型路由（RouteLLM）与异构 GPU 部署（ThunderServe）被独立优化，但 routing 改系统负载、部署改模型延迟特征，二者构成循环互依。
- **核心贡献**：把 routing 阈值 + GPU 分配 + 并行策略形式化为多目标优化，用 GP + qNEHVI + 5 项结构化先验求解，Llama3.1-8B/70B × 四类异构 GPU 上延迟最高 2.57× 降低、成本平均 38% 节省。
- **关键发现/观点**：异构模型与异构 GPU 天然互补——小模型在 5090 上比 H100 低 33% 延迟，大模型在 H100 上比 5090 低 50% 延迟；把小模型放到 5090 就能释放 H100 预算给大模型，且最优路由比例会随之迁移，因此两种异构性必须联合优化。

#### [[fc490ca45c00b1249bbe3554a4fdf6fb|MorphServe]]
- **作者**：Zhaoyuan Su et al.
- **要解决的问题**：主流 LLM 服务假设模型精度固定、负载平稳，真实突发流量下 SLO 违约严重，静态量化又牺牲质量。
- **核心贡献**：MorphServe 在运行时 token 级替换 FP16/INT8/INT4 层 + 块级 KVC 动态挂载释放，Vicuna/Llama2/Llama3/CodeLlama × Azure/BurstGPT trace 上 P95 TTFT 降 2.2–3.9×、SLO 违约 -92.45%、精度损失 ≤3%。
- **关键发现/观点**：量化对不同 transformer 层的影响近似可加、敏感度差异巨大，可按 Layer Importance Score 形成固定切换顺序；FP16→INT4 节省的权重内存恰好可复用为 KV cache 容量，使得负载维度上可沿 Pareto 前沿弹性移动。

---

### Attention 与 KV cache 优化（7 篇）

#### [[5ef059938ba799aaa845e1c2e8a762bd|MAC-Attention]]
- **作者**：Jinghan Yao et al.
- **要解决的问题**：长上下文 decode 是 IO-bound，KV 压缩/驱逐在长生成下会累积精度损失；现有「跨 step 复用 attention summary」又依赖字面前缀或静态 sparsity。
- **核心贡献**：Match–Amend–Complete 方案，双 ring buffer + pre-RoPE L2 匹配历史 query + 局部高质量带重算，LongBench v2/RULER/LongGenBench 上精度持平或超过 full attention，attention 阶段最高 46×、端到端 2.6×。
- **关键发现/观点**：单一 decode 流中 query 有强时间冗余，且匹配必须在 pre-RoPE 语义空间完成（否则 RoPE 相位破坏相似度）；softmax 概率质量集中在 cursor 附近，因此只需重算匹配位置附近的「高质量带」就能把复用误差压到与 full attention 不可分。

#### [[72b32a1f754ba1c09b3695e0cb6cde7f|FlashAttention-4]]
- **作者**：Ted Zadouri et al.
- **要解决的问题**：Blackwell GPU tensor core 算力翻倍但 SMEM/exp/FMA 近乎不变，FA3 的 register-resident pipeline 无法利用 TMEM/2-CTA，attention 瓶颈漂移到非 matmul 单元。
- **核心贡献**：TMEM 全异步 MMA + ping-pong + 多项式近似 exp 分流 FMA + 2-CTA DSMEM 减半 backward SMEM 流量，B200 BF16 attention 1613 TFLOPS（71% 峰值），相对 Triton 2.7×/cuDNN 1.3×，CuTe-DSL 把 kernel 编译从 55s 压到 2.5s。
- **关键发现/观点**：Blackwell 上 tensor core 相对 SMEM/MUFU/FMA 呈非对称扩张，「每条路径都塞满 MMA」不再是最优目标；真正跑满 MMA 必须用异步 MMA + TMEM 作为并行媒介把 softmax/rescaling 搬到与 MMA 平行的硬件单元，且可用多项式近似把一部分 exp 从 MUFU 分流到 FMA 翻倍 exp throughput。

#### [[76dc611d6ebaafc66cc0879c71b5db5c|FlexiCache]]
- **作者**：Nazmul Takbir et al.
- **要解决的问题**：长上下文 + 长生成下 KV cache 爆炸，现有 sparse/eviction/hybrid 要么不能动态适配，要么 GPU 全量驻留，要么损精度。
- **核心贡献**：把 head 分 stable(75%)/unstable(25%)，stable head top-K 页驻留 GPU 每 16 步重排，unstable head 全量驻留每步重排；H100 + vLLM 长上下文长生成 GPU 内存节省 ~70%，在线 TPOT 1.6–2.1×，精度保留 ≥99%。
- **关键发现/观点**：KV head 的 top-K 页集合在连续 decode step 间的重合度（temporal stability）在 head 之间差异巨大，且该差异是模型内禀的（同模型 unstable head 跨任务一致度 >0.8），因此可离线一次 profile 做 head 分类，中间时间尺度替代「逐步重排 vs 永久丢弃」的二选一。

#### [[92cc227532d17e56e07902b254dfad10|SkipKV]]
- **作者**：Jiayi Tian et al.
- **要解决的问题**：Reasoning LLM 长 CoT decode 让 KV cache 暴增，token 级 eviction 会保留碎片化 token，压缩后反而生成更长，batch padding 再腐蚀有效 KV 预算。
- **核心贡献**：句子级 PSS 评分驱动 KV eviction + adaptive steering 抑制非执行思考 + batch grouping 压缩 padding，DeepSeek-R1-Distill 上相对 R-KV 精度 +26.7%、生成长度 1.6× 缩短、吞吐 1.7×。
- **关键发现/观点**：LRM 的推理轨迹具有天然的句子级语义结构，真正有害的冗余是整句/整段的语义重复（「Wait, let me double-check」）而不是孤立 token，因此句子粒度 eviction 能同时保留推理链连贯性并剔除过度思考片段。

#### [[c20ad4d76fe97759aa27a0c99bff6710|IntAttention]]
- **作者**：Wanli Zhong et al.
- **要解决的问题**：商品 ARM 边缘 CPU 上 INT8 GEMM 加速 attention 后，softmax 的 dequant/exp/requant 占 57–65% 延迟，现有整数化 softmax 需 QAT/calibration。
- **核心贡献**：IndexSoftmax（稀疏感知整数 clipping + 32 字节 UINT8 LUT exp + 整数归一化 + UINT8 概率存储），RK3588/M2 上 Llama-3.2-1B/Qwen3-1.7B 与 ViT 家族端到端 2.1–3.7×，能耗 -61%，精度几乎无损。
- **关键发现/观点**：softmax 的 exp 在 row-wise max-subtraction 后输入具有强稀疏性，每行只有少量大值真正贡献到归一化分母，因此 exp 的有效输入域可被 clip 到一个紧凑整数区间并用 32-entry UINT8 LUT 完全取代浮点 exp。

#### [[d82c8d1619ad8176d665453cfb2e55f0|BLASST]]
- **作者**：Jiayi Yuan et al.
- **要解决的问题**：稀疏 attention 要么靠额外代理 token 打分有预计算开销，要么静态模式掉精度，且 prefill/decode 被独立优化。
- **核心贡献**：在 FlashAttention block-wise online softmax 中用 $\tilde m_i - m_i < \ln(\lambda)$ 判跳过整块，配合 $\lambda = a/L$ 自动校准，Llama-3.1-8B/Qwen3-8B 上 ~75% 稀疏度下 prefill 1.62×、decode 1.48×，正交可叠加 XAttention/RocketKV。
- **关键发现/观点**：在 FlashAttention online softmax 中判断一个 block 是否可跳过所需的全部统计量（running max 与 block local max 的差）已被顺手算出，不需要额外代理打分；这个「免费判据」恰好把稀疏模式与精确 attention 在同一 kernel 内统一起来。

#### [[e369853df766fa44e1ed0ff613f563bd|Kitty]]
- **作者**：Haojun Xia et al.
- **要解决的问题**：长上下文 LLM 推理中 KV cache 超过模型权重，现有 4-bit KV 量化与 FP16 持平，但 2-bit 后 MATH/AIME 等长链推理断崖式掉分。
- **核心贡献**：Key cache 12.5–25% 高 magnitude channel 保 INT4 其余 INT2 + Value per-token + sink + local 滑动窗口，Dense-Sparse Decomposition 存为两个统一 2-bit 张量 + boost index，Qwen3/LLaMA3 2-bit KV 精度损失从 KIVI 8–15 分压回 0–2 分，8× batch / 2.1–4.1× 吞吐。
- **关键发现/观点**：Key cache 不同 channel 的重要性极度不均匀，且该重要性可用极轻量的启发式（channel 平均绝对值）在运行时一遍扫描估出；混精只保留 12.5–25% channel 在 INT4 就能恢复绝大部分精度，再通过 Dense-Sparse Decomposition 把混精 page 拆成统一精度张量以保持 GPU kernel coalesced 访存。

---

### Speculative decoding 与 diffusion LM（6 篇）

#### [[14bfa6bb14875e45bba028a21ed38046|SpecDiff-2]]
- **作者**：Jameson Sandler et al.
- **要解决的问题**：用 DLM 做 speculative decoding drafter 时，AR 风格对齐只能把第一个位置 acceptance 拉高，窗口靠后位置急剧退化。
- **核心贡献**：Streak-Distillation（训练时优化 product-of-accepts）+ Self-Selection Acceptance（推理时 DLM 多采样 + verifier batch 打分），70B+ verifier 平均 4.22× 加速、最高 5.5×。
- **关键发现/观点**：Speculative decoding 的真实吞吐目标 Tokens/Draft = E[Σ_m Π_j α_j] 是位置乘积形式，DLM 一次 forward 给出的 γ 个位置边际分布彼此独立，因此必须显式按 product-of-accepts 对齐每一个位置；而 DLM 多次采样的边际成本接近 0 提供了天然的 self-selection 杠杆。

#### [[65ded5353c5ee48d0b7d48c591b8f430|PRISM]]
- **作者**：Xuliang Wang et al.
- **要解决的问题**：SOTA drafter 越做越大带来的延迟抵消 acceptance 提升，context alignment 训练成本又随 draft 步数急剧膨胀。
- **核心贡献**：PRISM 在 drafter 内沿「自回归 step 维度」做 conditional computing，M 个处理模块按满射映射到 K 个 draft 步共享 KV cache；SGLang 上 LLaMA-2-7B 六基准相对 EAGLE-2/HASS 平均 TPS +14.2%/+6.1%，相对 vanilla 最高 3.29×。
- **关键发现/观点**：Speculative decoding 预测难度在 draft 步序列上非均匀，后面的步越来越难、acceptance rate 单调下降，因此应把 draft 步的计算路径沿时间轴（而非 MoE 的 token 轴）路由到不同参数子集，既扩 capacity 又不增加单步活跃参数。

#### [[67c6a1e7ce56d3d6fa748ab6d9af3fd7|TiDAR]]
- **作者**：Jingyu Liu et al.
- **要解决的问题**：AR LLM decode 受顺序依赖拖累，纯扩散 LM 并行好但与 KV cache 不兼容且质量有 gap，speculative decoding 又受 drafter 容量与 draft-verify 串行限制。
- **核心贡献**：TiDAR 基于混合 attention mask 的单一模型，在一次 forward 内并行完成 diffusion drafting + AR rejection sampling，保留精确 KV cache；1.5B/8B 模型相对 Qwen2.5/Qwen3 吞吐 4.71×/5.91×。
- **关键发现/观点**：GPU memory-bound 解码阶段单步前向的延迟被权重与 KV 读取占据，序列长度从 1 加到几十上百 slot 几乎不增加延迟（「free token slots」）；这意味着可以在单次前向里免费塞入几十个 mask token 做扩散 drafting，把扩散并行度与 AR 分布质量以零额外 forward 代价同时拿到。

#### [[6f4922f45568161a8cdf4ad2299f6d23|SparseSpec]]
- **作者**：Yilong Zhao et al.
- **要解决的问题**：Reasoning LLM decode 长度急剧增大，attention 成为 77%+ 延迟，现有 draft-model/training-free sparse 方案要么要训练、要么静态稀疏。
- **核心贡献**：PillarAttn + Unified Batch Scheduler + Delayed Verification + Dynamic KV-Cache Manager，以 verify 阶段 attention score 作为 draft sparsity 的 zero-overhead oracle，vLLM-V1 + Qwen3 家族 AIME/LiveCodeBench 相对 vLLM 最高 2.13×。
- **关键发现/观点**：Speculative decoding 的 verify 阶段本就要做一次 full attention，其产生的 attention score 天然是「哪些 token 是 critical token」的 ground truth；改造 kernel 把 score 导出并在 draft 阶段 TopK 就可以零额外开销获得动态自适应的稀疏模式，且该稀疏模式在后续 k 步 draft 内具备时间局部性可复用。

#### [[7cbbc409ec990f19c78c75bd1e06f215|CDLM]]
- **作者**：Minseo Kim et al.
- **要解决的问题**：开源 DLM 推理慢，去噪步数 ≈ 生成长度 L，双向 attention 又无法与 KV cache 兼容。
- **核心贡献**：distillation + consistency + DLM 三目标联合 LoRA + block-wise causal mask，Dream-7B/LLaDA-8B 上 decode 步数减 3.4–7.9×、延迟 3.6–14.5×、吞吐最高超 AR baseline 4.2×。
- **关键发现/观点**：视觉 consistency models 可跨离散 token 轨迹泛化——DLM 逐步 unmask 构成一条去噪轨迹，让模型在「中间状态」与「block 完成态」上产生一致预测，就能跳过中间步一次性敲定多个 token；同时 block-causal mask 不损失局部 bidirectional 能力（关键 infill 发生在当前 block 内），与精确 KV cache 可同时兼得。

#### [[f0935e4cd5920aa6c7c996a5ee53a70f|Speculative Decoding — Performance or Illusion?]]
- **作者**：Xiaoxuan Liu et al.
- **要解决的问题**：现有 SD 论文的 speedup 数字都来自 prototype、batch=1，不清楚在生产 vLLM + continuous batching + CUDA Graph 下还剩多少收益。
- **核心贡献**：在 vLLM v0.10.1.1 上系统评测 n-gram/EAGLE/EAGLE-3/Draft-Model/MTP × 4 模型 × 6 数据集 × batch 1–128，提供 trace simulator，给出现实 end-to-end 收益与 oracle 上限。
- **关键发现/观点**：Verification 主导 SD 执行时间（42–95%）而 drafting 并非瓶颈，因此「加强 drafter」不如「降低被拒绝 token 的验证浪费」；acceptance pattern 在 request 内外与数据集间高方差，若存在 oracle 能提前知道每步接受 token 数并按位置选更优 proposer，当前 SD 距离上限还有 2× 以上空间。

---

### MoE 训练与推理（5 篇）

#### [[02e74f10e0327ad868d138f2b4fdd6f0|Layered Prefill]]
- **作者**：Gunjun Lee et al.
- **要解决的问题**：chunked prefill 在 MoE 下每个 chunk 要完整穿透所有 decoder 层，导致专家权重重复加载、sparsity erosion 与 chunk size 两难。
- **核心贡献**：把并发控制粒度从 token 维度迁移到 layer 维度，Qwen3-30B-A3B/GPT-OSS-20B 上 TTFT 降 70%、E2E 降 41%、MoE 权重搬运 -39%、per-token 能耗 -22%。
- **关键发现/观点**：chunked prefill 的冗余来自于把「并发控制粒度」和「模型穿透粒度」耦合在同一个 token 维度上；若把并发控制迁移到 layer 维度，每层对同一 prompt 只执行一次，MoE 权重的重复加载就被物理消除，而 stall-free 性质仍能保留。

#### [[072b030ba126b2f4b2374f342be9ed44|FP8-Flow-MoE]]
- **作者**：Fengjuan Wang et al.
- **要解决的问题**：BF16-centric dataflow 中实现 FP8 MoE 训练需要大量 Q/DQ cast 吞掉 FP8 算力收益，朴素保留 FP8 又会在 row/col 量化 layout 切换时产生 double quantization error。
- **核心贡献**：Direct (scaling-aware) Transpose + 融合 permute/padding/SwiGLU 量化 kernel，把 end-to-end cast 次数从 12 次压到 2 次，DeepSeek-V3 671B 相对 BF16 最高 +16% 吞吐，无收敛损失。
- **关键发现/观点**：当 scaling factor 被约束为 2 的幂时，row-wise 与 column-wise 两种 FP8 量化 layout 之间的转换不再涉及 rounding，只需在 FP8 编码上调整 exponent bit 即可精确互转，完全无需 dequantize/requantize。

#### [[17e62166fc8586dfa4d1bc0e1742c08b|CRAFT]]
- **作者**：Adrian Zhao et al.
- **要解决的问题**：EPLB 等主流 MoE 推理系统对每层每 GPU 均匀复制热门 expert，系统性 over-replicate，小集群上 goodput 反而比纯 placement 差。
- **核心贡献**：把 expert replica 分配形式化为 Multiple-Choice Knapsack，按各层 replication benefit 曲线精细分配，SGLang 上 DeepSeek-R1/Kimi-K2 相对 EPLB 平均 1.14× goodput、replica 用量减 7×。
- **关键发现/观点**：MoE 各层对 replication 的收益曲线差异极大（peak/mean 从 2.5 到 27×），且所有层 replication balancedness 增益都呈 sublinear 趋势且各自存在饱和点；replica 应被当成稀缺资源按层粒度按收益分配，而不是均匀撒到每个 GPU。

#### [[2b44928ae11fb9384c4cf38708677c48|MoEBlaze]]
- **作者**：Jiyuan Zhang et al.
- **要解决的问题**：MoE 训练中 routed-token buffer 与 SwiGLU 中间激活占用大量激活内存（DeepSeek 配置下单层 FFN 激活近 100 GB），限制 batch/sequence 规模。
- **核心贡献**：MoEBlaze 用轻量索引替代物化 routed-token buffer + 原子-free 三步并行 dispatch + fused SwiGLU GEMM + SiLU recompute，H100 相对 MegaBlocks 取 1.4–6.2× 训练加速、2–4× 激活内存节省。
- **关键发现/观点**：per-expert 物化 routed-token buffer 并非必需——只要维护轻量 token↔expert 映射索引，MLP 计算可 on-the-fly 从原始未置换 activation 直接 gather/scatter，跳过中间排列缓存；且 SwiGLU 中间结果是 memory-bandwidth bound，recompute 比保存更划算。

#### [[698d51a19d8a121ce581499d7b701668|FarSkip-Collective]]
- **作者**：Yonatan Dukler et al.
- **要解决的问题**：MoE 每层有 attention all-reduce + dispatch/combine all-to-all 三处阻塞通信，现有 partial/outdated-connectivity 方案只在 dense+TP 小模型上验证。
- **核心贡献**：FarSkip，attention 走 partial、MoE 走 outdated 激活，Combine 与下一层 attention、Dispatch 与 attention 本体重叠，配合 FCSD self-distillation，16B/30B/109B MoE 上 ≤10B tokens 蒸馏恢复 97.5–99% 能力，all-to-all 重叠 88%、训练端到端 1.04–1.22×。
- **关键发现/观点**：现代 Transformer 残差主干下，第 k 层 sub-block 的输入由所有先前 sub-block 的 residual 累加构成，即便把本层 communicated output 推迟到再下一层（「far-skip」）而不是作为直接输入，第 k+1 层仍能访问 (k-1)/k 比例的历史信息——残差为 communication hiding 留下了一条几乎免费的信息旁路。

---

### 分布式训练系统（9 篇）

#### [[28dd2c7955ce926456240b2ff0100bde|AXLearn]]
- **作者**：Mark Lee et al.
- **要解决的问题**：现有大模型训练框架在生产下新增架构/特性的工程成本随规模线性或平方膨胀，且很难同时跨 GPU/TPU/Trainium 保持性能。
- **核心贡献**：Apple 开源 AXLearn（JAX/XLA），层次化 Config + Config Modifier + Mesh Rules + InvocationContext，把新增 RoPE/MoE 的 LoC-Complexity 从 O(NM) 压到 O(1)，跨 GPU/TPU/Trainium 服务数十亿用户。
- **关键发现/观点**：神经网络层天然具有组合性，只要父子层在 I/O 接口上达成一致，任何子层都可被「原位替换」，不必通过 subtyping 修改父层；因此只要系统所有模块严格遵循 encapsulation，新增特性 F 的代价就与系统模块数无关——O(1) LoC-Complexity。

#### [[37693cfc748049e45d87b8c7d8b9aacd|NEST]]
- **作者**：Irene Wang et al.
- **要解决的问题**：现有 device placement 系统把内存可行性视为事后过滤、把网络简化为 flat/2D mesh，并行策略间缺乏结构化组合，难以扩展到 hierarchical/oversubscribed 真实集群。
- **核心贡献**：level-wise 网络抽象 + 内存/ZeRO 动作内嵌 DP 状态 + SUB-GRAPH/GRAPH-GLOBAL 正交分解统一动态规划，TPUv4 与 H100 Spine-Leaf 上相对 Alpa 2.43×、Mist 1.49×，可扩展到 1024 GPU。
- **关键发现/观点**：并行策略可按正交维度分层为层内 SUB-GRAPH（TP/EP/SP/CP）与层间 GRAPH-GLOBAL（PP/DP/ZeRO），hierarchical 网络的关键属性是「同节点/同机架/跨机架」等离散距离类；把「前向 deferred 距离」抽象为 level 使搜索保留最优子结构，内存约束必须作为状态一等公民而非事后检查。

#### [[642e92efb79421734881b53e1e1b18b6|veScale-FSDP]]
- **作者**：Zezhou Wang et al.
- **要解决的问题**：现有 FSDP 只支持 element-wise/row-wise 分片，不真正支持任意块粒度，与 Shampoo/Muon 矩阵优化器和 block-wise FP8 量化冲突；FSDP2 又引入大量 Copy-In/Out 开销。
- **核心贡献**：RaggedShard DTensor placement + structure-aware NP-hard buffer planner + 零拷贝 Distributed Buffer，1024 GPU 上 LLaMA-3 70B / GPT-OSS 120B MoE 相对 FSDP1/2、DeepSpeed、Megatron-FSDP 吞吐 +11–66%、显存节省 16–30%。
- **关键发现/观点**：FSDP 需要的不是「一种更好的 shard」，而是「能表达原子不可切块粒度」的抽象；一旦每个参数能声明自己的原子块，分片可以在块约束下自由决定每 device 放几个块，从而天然兼容 block-wise 量化与矩阵优化器，不需额外 buffer。

#### [[9a1158154dfa42caddbd0694a4e9bdc8|HexiScale]]
- **作者**：Ran Yan et al.
- **要解决的问题**：现有 LLM 训练框架假设同构 GPU + 对称并行度，在跨代际/型号异构集群 + 带宽差两个数量级的网络下要么强制 over-sharding 要么闲置高带宽链路。
- **核心贡献**：支持 DP/PP/TP 三维完全非对称并行 + 非对称梯度同步 + 两阶段图分区调度，7B–30B LLaMA 异构集群相对 Galvatron 2.1×/Metis 1.6×，MFU 仅比同构 Ethernet 低 0.3–3.5%。
- **关键发现/观点**：异构集群的并行策略必须在 data/pipeline/tensor 三个维度上都允许完全非对称（不同 pipeline 不同 batch/TP、不同 stage 不同层数/TP），才能让每块 GPU 按算力/显存/带宽承担恰到好处的负载；在此自由度下 GPU 到 pipeline 的划分天然匹配带宽敏感的图分区问题。

#### [[9f61408e3afb633e50cdf1b20de6f466|DreamDDP]]
- **作者**：Zhenheng Tang et al.
- **要解决的问题**：跨数据中心 Local SGD 训练 LLM 把 H 步本地更新后的全模型 all-reduce 视为硬同步点，无法与 BP 重叠，且直接开 buffer 会把几百 GB 参数翻倍撞显存墙。
- **核心贡献**：PLSGD + in-place 同步 + DFS 调度 + 气泡填充，32 GPU ResNet/GPT-2/Llama-2 175M 上相对 ASC-WFBP 1.49–3.91×、相对 FLSGD 1.16–1.56× 加速，收敛曲线对齐 S-SGD。
- **关键发现/观点**：LSGD 的「H 步整体同步」并非收敛必要条件——把全模型同步拆成「每步同步一部分层、H 步内每层都同步过一次」理论上仍达 O(1/R) 收敛，实践中偏差甚至更小；加上 BP 顺序依赖使层粒度 in-place 同步能在 BP 气泡中自然重叠，无需新 buffer。

#### [[93db85ed909c13838ff95ccfa94cebd9|DistCA — Core Attention Disaggregation]]
- **作者**：Yonghao Zhuang et al.
- **要解决的问题**：长上下文 LLM 训练 attention 占 90%+ 开销，document packing 下 FLOPs 随 chunk 构成呈二次差异导致 DP/PP stragglers。
- **核心贡献**：把 CA 从模型其余部分剥离到 attention server 池，token 级动态切分 + 跨 DP/PP 重组 + ping-pong 通信隐藏，8B × 512 H200 × 512K context 上相对 WLB-ideal 最高 1.35×，per-microbatch 内存发散从 55% 降到 2.1%。
- **关键发现/观点**：Core Attention 有两个独立调度友好的属性——(1) Statelessness（无可训练参数、FlashAttention 不物化 P 矩阵）；(2) Composability（可任意 token 粒度切分，kernel 吞吐只取决于 aggregate token 数而与来源无关），因此可跨 DP replica / PP stage 重新 batch 到 high-occupancy kernel。

#### [[a3c65c2974270fd093ee8a9bf8ae7d0b|ProTrain]]
- **作者**：Hanmei Yang et al.
- **要解决的问题**：DeepSpeed/Colossal-AI/FSDP 暴露 140+ 显存参数且相互耦合，且 profiler 漏算 transient/unhookable memory 使得 cost model 不准。
- **核心贡献**：Hierarchical Chunk Management + Interleaved Block Management + Memory-Aware Profiler + 四参数穷举自动调优，4/16× RTX 3090/A100 上相对 DeepSpeed/Colossal-AI/FSDP 吞吐 1.43–2.71×，RTX 3090×4 可训从 15B 推到 34B。
- **关键发现/观点**：尽管 ZeRO+offloading+checkpointing+swapping 的原始参数空间巨大且耦合，但只要抽象成带可预测调度结构的结构化空间（chunk/block 粒度执行顺序确定 + interleaved block 使非确定性变确定性），就能一次 profiling 建立高保真 cost model，把搜最优配置转化为可分析求解的带约束优化。

#### [[e2c420d928d4bf8ce0ff2ec19b371514|MTraining]]
- **作者**：Wenxuan Li et al.
- **要解决的问题**：长上下文训练中 attention 占 90%+，block-sparse attention 方案在分布式 Context Parallel/Ring Attention 下 worker-level 与 step-level 严重不平衡，实际加速只有理论 1/3。
- **核心贡献**：Vertical-Slash 动态稀疏 pattern + Balanced Sparse Ring Attention（striped + block-level）+ Hierarchical Balanced Sparse Ring Attention，32 GPU A100 Qwen2.5-3B 32K→512K，相对 Dense 最高 6× 训练加速。
- **关键发现/观点**：带 RoPE 的 attention 在训练中稳定呈现 Vertical-Slash 稀疏结构（E[z] 仅依赖相对位置，由 cos/sin 基函数构成，outlier 贡献 vertical），且 backward 梯度稀疏模式与 forward 几乎一致；slash 成分在 block-wise GPU 计算下占主导，只要把 Q/K 按 stripe 沿对角线切分就能在 worker 与 step 两维同时拉平负载。

#### [[fe9fc289c3ff0af142b6d3bead98a923|BOOST]]
- **作者**：Zhengyang Wang et al.
- **要解决的问题**：低秩 bottleneck 架构在标准 Megatron 风格 TP 下 chunk 数翻倍、通信量爆炸 5×，GEMM 在 r 维 shard 导致算术强度塌陷，反而比 Full-rank 还慢。
- **核心贡献**：Bottleneck-aware TP（chunk 边界平移到低秩窄腰）+ Online RMSNorm（statistic reduce 与下一个 GEMM 的 all-reduce fuse）+ Linear Grouping + comm-free checkpointing，LLaMA-2 1B–30B × 最多 16 A100 对 Full-rank 1.46–1.91×。
- **关键发现/观点**：bottleneck 架构有一根「天然窄腰」（rank r 中间通道），把 TP chunk 边界整体平移一个 bottleneck 层，使每个 chunk 以 up-projection 起、down-projection 止，所有跨 GPU 同步只发生在低秩 [b,s,r] 激活上而所有 sharding 都发生在大维度上——通信走低秩路径、计算走大维度路径。

---

### RL 训练系统（4 篇）

#### [[6c8349cc7260ae62e3b1396831a8398f|CSLE]]
- **作者**：Kim Hammar
- **要解决的问题**：现有自主安全 RL 平台都是纯仿真环境，没有真实虚拟化执行层，学到的策略能否迁移到真实运营系统未知。
- **核心贡献**：Docker Swarm + OVS + NetEm 数字孪生 + 系统辨识 + 仿真 RL + 管理层三系统框架，四个安全 use case 上 sim-to-twin gap 几乎为零且 RL 策略显著优于 threshold/Snort。
- **关键发现/观点**：把「在仿真中学」和「在真实系统中评估」通过数字孪生 + 系统辨识解耦，可同时回避在线学习的危险性与纯仿真的不真实性——数字孪生运行与目标系统相同的软件/配置/拓扑但跑在虚拟化硬件上，从中采集的真实测量能驱动出简化 MDP/POMDP 用于 RL 高效训练。

#### [[7f1de29e6da19d22b51c68001e7e0e54|Learning from Less — RLVR 小数据]]
- **作者**：Justin Bauer et al.
- **要解决的问题**：现有 RLVR scaling law 都是大模型+多数据+多算力，缺乏在低数据+低算力+小模型（4B LoRA）下数据组成对 RLVR 效果的系统刻画。
- **核心贡献**：三套 procedurally-generated 推理数据集（Counting/Graph/Spatial）+ 多模型校准的 Easy/Medium/Hard 难度分层 + 六配置 × 三数据集 18 组实验，发现「Mixed-100 ≈ Easy-500」5× 样本效率。
- **关键发现/观点**：当模型规模、算力、训练步数钉死后，RLVR 收益不再由样本总量主导而由难度分布主导——易题同质样本只能给出低幅度同质化的 advantage 信号，掺入 medium/hard 样本后 GRPO 组内 reward 方差扩大，等价于每个 step 获得的有效信息增加，从而「难度多样性可以 substitute 数据量」。

#### [[7f39f8317fbdb1988ef4c628eba02591|HetRL]]
- **作者**：Yongjun He et al.
- **要解决的问题**：现有 RL 训练系统假设同构高端 GPU + 同构网络，把 LLM 异构调度思路直接搬到 PPO/GRPO 四模型六任务的 RL workflow 会搜索爆炸。
- **核心贡献**：HetRL（verl 扩展）把 RL 调度写成 constrained joint optimization，用 5 层多粒度搜索 + nested successive halving + 双层 swap GA 求解，64 GPU 异构集群相对 verl 最高 9.17×/平均 3.17× 吞吐。
- **关键发现/观点**：RL 调度搜索空间虽指数级巨大但具有天然层次结构——task grouping、coarse GPU 分组、tasklet 到 device 的精细映射处于不同抽象层，每层候选数量可控，较粗层的 cost 模型评估足以指导较细层继续探索的方向。

#### [[f899139df5e1059396431415e770c6dd|DAS]]
- **作者**：Zelei Shao et al.
- **要解决的问题**：RL post-training rollout 占总时间 70%+，长尾请求决定 makespan，而传统 SD 针对小 batch serving 优化，EAGLE 类 drafter 又随 policy drift 必须频繁重训。
- **核心贡献**：per-problem sliding-window suffix tree 作非参数 drafter + length-aware budget（闭式解按长度给长尾更多 draft 预算）+ 启发式层次化长度档位，集成 VeRL 后 math RL 8-GPU rollout 时间 -50%、code RL -25%。
- **关键发现/观点**：RL rollout 独特属性——(1) 同一批 prompt 跨 epoch 反复出现，历史轨迹有稳定 prompt 级模式；(2) 长尾序列决定 step makespan，对不同长度请求投入相同 draft 预算是浪费；(3) policy drift 具有局部性（相邻 epoch 相似度高），因此 sliding-window 历史 + per-problem suffix tree 足以支撑 draft。

---

### GPU kernel、编译与自动调优（8 篇）

#### [[07e1cd7dca891345f7ba84e9b0bc6f44|Event Tensor / ETC]]
- **作者**：Hongyi Jin et al.
- **要解决的问题**：现有 megakernel 方案难以同时处理 dynamic shape（continuous batching）与 data-dependent dynamism（MoE routing），且 warmup 时间长。
- **核心贡献**：Event Tensor IR 抽象与 ETC 编译器把 megakernel 中细粒度同步事件升格为一等张量，支持 static/dynamic 两种调度 lowering，B200 上 GEMM+RS/MoE 1.18–1.40× 加速，warmup 123–583s 压到 35s。
- **关键发现/观点**：megakernel 中 SM 级别 task 完成所产生的「event」天然形成多维结构，可以把这些事件升格为 IR 中的一等张量（Event Tensor），这样张量基础设施（符号 shape、index 表达式）能直接复用到细粒度同步上，同时表达 shape dynamism 与 data-dependent dynamism。

#### [[2a38a4a9316c49e5a833517c45d31070|HipKittens]]
- **作者**：William Hu et al.
- **要解决的问题**：AMD CDNA3/CDNA4 GPU 硬件已接近 NVIDIA，但主流 tile-DSL（ThunderKittens）假设的硬件特性（TMA、wgmma、register reallocation）在 AMD 上缺失。
- **核心贡献**：基于 TK 抽象但为 AMD 重写 register pinning、bank-aware swizzle、8-wave ping-pong、XCD 感知 chiplet swizzling，MI355X BF16/FP8 GEMM 与 AITER 汇编打平，GQA backwards 1.8–3× 超越 Triton/CK。
- **关键发现/观点**：TK 的「tiles + bulk operators」前端抽象可跨厂商，但下层「实例化这些抽象的算法」——调度、memory movement、cache 感知——必须根据 AMD 硬件特性（2× 寄存器、小 MFMA shape、L2/LLC 3× 带宽差、缺 TMA/mbarrier）重新设计，尤其要用大 output tile + 深流水线替代 wave specialization。

#### [[3295c76acbf4caaed33c36b1b5fc2cb1|ParallelKittens]]
- **作者**：Stuart H. Sul et al.
- **要解决的问题**：跨 GPU 通信成为 B200 级训练/推理关键瓶颈，现有方案要么绑死算子模板，要么用 NCCL/NVSHMEM 引入巨大设计开销。
- **核心贡献**：8 个 tile 级 P2P/in-network 通信原语 + PGL 多 GPU layout + LCSC 编程模板，8×H100 上 DP/TP/SP/EP 四类 workload 显著加速（SP 最高 4.08×），<50 行 device 代码达到 Flux/Comet/CUTLASS 同级。
- **关键发现/观点**：multi-GPU AI kernel 性能可用一个 cost model 分解到三个独立设计选择：传输机制（TMA/copy engine/register）、调度策略（inter-SM vs intra-SM）、抽象设计开销；框架只要在这三轴暴露最优选项，各类 workload 的最优 overlap 实现就退化为「按 workload 特性挑组合」。

#### [[a3f390d88e4c41f2747bfa2f1b5f87db|LLaMEA for Auto-Tuning]]
- **作者**：Floris-Jan Willemsen et al.
- **要解决的问题**：GPU auto-tuning 搜索空间离散/不规则/约束密集，传统 SA/GA/PSO 并不为此场景设计，超参依赖重，人工设计新算法跟不上硬件演化。
- **核心贡献**：LLaMEA（LLM + EA）+ Kernel Tuner 搜索空间信息注入 prompt，4 kernel × 6 GPU × 24 搜索空间上自动合成优化器 HybridVNDX/AdaptiveTabuGreyWolf，相对调过 7 天超参的 GA/SA/DE 平均 +72.4%。
- **关键发现/观点**：把 LLM 提出 + EA 筛选做成闭环可把 LLM 的创造性噪声转化为高质量优化器（LLM 不必每次正确），且 auto-tuning 问题具备共性结构（离散、约束密集、评估昂贵）使同一批生成算法能跨 kernel/GPU 泛化；关键是把搜索空间特征显式写入 prompt，让 LLM 合成特化策略。

#### [[a87ff679a2f3e71d9181a67b7542122c|Spira]]
- **作者**：Dionysios Adamopoulos et al.
- **要解决的问题**：点云 Sparse Conv 的 voxel indexing 预/后处理开销大，现有 MinkowskiEngine/SpConv2/TorchSparse++/Minuet dataflow 粒度粗。
- **核心贡献**：z-delta one-shot search + packed-native voxel indexing + adaptive hybrid dataflow + network-wide concurrent indexing，3 网络 × 3 数据集 × 6 GPU 平均 1.68×/最高 3.04× 加速。
- **关键发现/观点**：voxel 坐标有三条未被充分利用的结构性质——(1) Integer Property（坐标是 stride 整数倍，排序后相邻，可用 O(1) 线性扫描替代二分）；(2) Bounded Property（范围可打包进单 32-bit 整数）；(3) Neighboring Property（submanifold 卷积 kernel map 列密度与 offset L1-norm 强相关，应按列动态选 output- vs weight-stationary）。

#### [[b53b3a3d6ab90ce0268229151c9bde11|FLASHLIGHT]]
- **作者**：Bozhi You et al.
- **要解决的问题**：FlexAttention 只能表达 softmax(score_mod(S))V 静态模板，对 differential attention、AlphaFold Evoformer 等变体无能为力。
- **核心贡献**：TorchInductor 扩展三类 IR + 三类融合 pass，自动从 idiomatic PyTorch 合成 FlashAttention 级 Triton kernel，B200/A100 上 Evoformer 5–8×、DiffAttn 1.5–5×，AlphaFold2 端到端 6–9% 提速。
- **关键发现/观点**：只要让 GEMM 参与 TorchInductor 通用 reduction IR，并把 kernel 融合抽象成「computation sketch」上的几条 rewrite 规则（dimension demotion、ring-homomorphism 驱动的 online softmax、tiling-aware dimension elimination），FlashAttention 风格的 tiled+fused kernel 就可以被通用编译 pass 从任意 PyTorch attention 代码自动合成，不需专门 template。

#### [[c45147dee729311ef5b5c3003946c48f|PyLO]]
- **作者**：Paul Janson et al.
- **要解决的问题**：学习型优化器（VeLO）研究上已有十年但社区几乎不用——只有 JAX 实现、权重没分发渠道，且 per-parameter MLP 使单步开销是 Adam 的 150×。
- **核心贡献**：PyTorch 库 + CUDA fused kernel + HuggingFace 分发 + 分布式 optimizer step，VeLO optimizer step 从 757ms 压到 100ms（H100 PyLO-CUDA++ 再降 2×），ViT-B/16 ImageNet 78.45% 超 Adam+cosine。
- **关键发现/观点**：LO 朴素实现的瓶颈不是算法而是 PyTorch 通用模块对「每个参数张量跑一个小 MLP」这种特殊计算模式的不适配；memory bandwidth 才是真瓶颈而非 compute，把两个 fused kernel + 寄存器存特征 + 重算换带宽堆起来就能消除 kernel launch 与临时张量分配。

#### [[c8ffe9a587b126f152ed3d89a146b445|FlashInfer-Bench]]
- **作者**：Shanli Xing et al.
- **要解决的问题**：LLM-generated GPU kernel 现有 benchmark（KernelBench/TritonBench）样例少、workload 不真实、reward hacking 严重，且很难零代码塞进 vLLM/SGLang。
- **核心贡献**：FlashInfer Trace schema（Definition+Workload+Solution+Evaluation）+ 真实 SGLang 流量数据集 + 防作弊 benchmark + flashinfer_bench.apply() 零代码替换，B200 上 240 solution × 9600 evaluation。
- **关键发现/观点**：「kernel 生成 → 评测 → 部署」三段被人工流程切断的根本原因是缺一种自包含、可序列化、人和 agent 都能读写的 kernel 通用语言；一旦把四样东西约束到同一个 JSON schema，agent 提交、benchmark 执行、引擎分发就能在同一对象上无损流转，把人工集成成本压到接近零。

---

### LLM agent、记忆与自动化系统（9 篇）

#### [[19ca14e7ea6328a42e0eb13d585e4c22|AccelOpt]]
- **作者**：Genghan Zhang et al.
- **要解决的问题**：新型 AI 加速器（AWS Trainium）上 kernel 优化缺乏专家知识与成熟启发式，LLM agent 可用但搜索空间巨大、查询成本高。
- **核心贡献**：beam search + optimization memory + planner/executor/summarizer 三 agent + NKIBench，14 个 NKI kernel 上用开源 Qwen3-Coder-480B + gpt-oss-120b 以 ~$210 把 Trainium 平均峰值占比 49%→61%，与 $5800 Claude Sonnet 4 相当。
- **关键发现/观点**：LLM 自身已具备通用性能优化的概念性知识（loop transform、tile size、memory hierarchy），只是缺乏特定加速器的实操经验；不必注入硬件专家手写 heuristic，给它一个反复尝试-profile-总结的闭环，它就能从自己产生的 slow-fast kernel 对里自蒸馏出加速器特定策略。

#### [[35f4a8d465e6e1edc05f3d8ab658c551|VeriMoA]]
- **作者**：Heng Ping et al.
- **要解决的问题**：已有 multi-agent HDL 生成方案受噪声传播（错误沿 pipeline 级联）与推理空间受限（单通道 spec→HDL）影响，在 Verilog 这种 low-resource DSL 上有限。
- **核心贡献**：MoA 之上加入 quality-guided global caching + 多路径 C++/Python 中间表示，VerilogEval 2.0/RTLLM 2.0 上对 8 种 LLM Pass@1 升 15–30 点，7B+VeriMoA 超 32B+VeriMaAS。
- **关键发现/观点**：每个 agent 调用的中间结果都持久化到 cache 并按质量分排序后供后续 agent 选择，能从架构上保证深层拿到的参考始终 ≥ 浅层，从而打破 multi-agent 的级联噪声放大；再叠加「用 LLM 更熟悉的高资源语言（C++/Python）作中间表示」引入异构推理路径，两件事结合才能同时解决质量与多样性。

#### [[54229abfcfa5649e7003b83dd4755294|PIKE]]
- **作者**：Kirill Nagaitsev et al.
- **要解决的问题**：现有基于 LLM 的 GPU kernel 优化系统把所有 multi-agent 设计（islands、crossover、archive、parallel 采样）捆绑报告，缺乏对 explore/exploit、agent 角色、步骤颗粒度的系统消融。
- **核心贡献**：PIKE 框架系统消融 OpenEvolve 各组件，得出「exploit-heavy mutation-only beam search + 错误修复 agent」是最优配方，KernelBench Level 3-pike 上 2.88× geomean，超越 torch.compile(1.64×)、TensorRT(1.41×)、METR(1.40×)。
- **关键发现/观点**：在 LLM 多智能体 kernel 优化中，LLM 单步生成的代码改动幅度本就远超传统 EA 的「小变异」，每一步都是近似大跳跃式重写；只要配一个错误修复 agent 兜底，激进的 exploit-heavy 搜索会压倒广撒网的 exploration——「让模型大胆改、然后兜底修」胜过让模型小心翼翼变异。

#### [[5fd0b37cd7dbbb00f97ba6ce92bf5add|OpenHands SDK]]
- **作者**：Xingyao Wang et al.
- **要解决的问题**：社区 software agent（OpenHands V0）演化为 monorepo 后出现 sandbox 强制化、配置爆炸、核心不可扩展等技术债，缺少生产级 SDK 范式。
- **核心贡献**：OpenHands V1 SDK（sdk/tools/workspace/agent_server 四包 + 事件溯源 ConversationState + LocalWorkspace/RemoteWorkspace 接口同构 + MCP/安全/confirmation/condenser），SWE-Bench Verified 72.8%/GAIA 67.9%，附 31 项 feature SDK 矩阵对比。
- **关键发现/观点**：成熟的 software agent 框架应遵循四条设计原则——沙箱 opt-in 而非默认、状态集中且 immutable（只有 ConversationState 可变，支持 deterministic replay）、agent core 必须从 application 分离、composability 分部署层与能力层两级。

#### [[6364d3f0f495b6ab9dcf8d3b5c6e0b01|OSWorld-Human]]
- **作者**：Reyna Abhyankar et al.
- **要解决的问题**：Computer-Use Agent 评测只看成功率，无法揭示 SOTA agent 延迟长到 40 分钟级的问题，也不提供 step 效率参考基线。
- **核心贡献**：对 Agent S2 做首次 CUA 延迟剖析（planning+reflection 占 75–94%），为全部 369 OSWorld 任务贡献人工 single/grouped 金标准轨迹，并提出 WES+/WES- 双指标把 SOTA 实际效率再缩水 2.4×。
- **关键发现/观点**：在 agentic CUA 的 observe→plan→ground→act→reflect 单步循环中，planning 与 reflection 的 LLM 调用会随 step 数单调变长（prompt 包含全部历史截图+推理），因此效率瓶颈可同时从两端打开——降低每次 LLM 调用延迟 + 压缩总 step 数，两条路在延迟上都是乘法收益且相互独立。

#### [[093f65e080a295f8076b1c5722a46aa2|LEANN]]
- **作者**：Yichuan Wang et al.
- **要解决的问题**：大规模向量检索索引（HNSW）要保留全量 FP32 embedding，存储占原文 2.5×+，个人设备装不下；PQ 高压缩比下精度崩塌。
- **核心贡献**：high-degree preserving graph pruning + 查询时按需 encoder 重算 embedding + two-level search + dynamic batching，索引压到原文 5% 以下（相对 HNSW 节省 ~98%），保持 ≥90% Recall，RAG pipeline 延迟 <20%。
- **关键发现/观点**：SOTA proximity graph 的 best-first 遍历每次查询只访问 N 中 O(log N) 个节点，因此没必要物化所有 embedding——只需用原编码器在查询时对被访问节点「按需重算」，用计算换存储；且 HNSW 中少数高度数节点承担主要导航，其他边可激进剪枝。

#### [[d645920e395fedad7bbbed0eca3fe2e0|HIPPOCAMPUS]]
- **作者**：Yi Li et al.
- **要解决的问题**：现有 agentic memory（RAG/KG/Hybrid）长 horizon 下 retrieval 开销与 token 占用爆炸，dense vector ANN 退化、KG 遍历组合爆炸，search 占端到端 47–85%。
- **核心贡献**：Dynamic Wavelet Matrix + Signature DWM via random indexing + Hamming-ball 搜索，LoCoMo/LongMemEval 上精度持平/超越 SOTA，端到端延迟 31× 降、token 占用 14× 降、构建时间 5.3× 降，写入无需 LLM。
- **关键发现/观点**：LLM 原生输入就是离散 token-id 序列，没必要再投影到稠密 float embedding 空间做 ANN；用对离散符号序列原生友好的 succinct data structure（Wavelet Matrix）直接在压缩域做 rank/select，再结合 random indexing 把语义检索退化成位级 Hamming-ball 搜索，就能把检索从 GPU-heavy 的浮点运算彻底转成 CPU 上的 bitwise 操作。

#### [[e2ef524fbf3d9fe611d5a8e90fefdc9c|TritorX]]
- **作者**：Alec M. Hammond et al.
- **要解决的问题**：每款新 AI ASIC（MTIA）从零构建 PyTorch ATen 后端需要手写成百上千 kernel、数月工时，现有 LLM-for-kernel 瞄准极致性能而非覆盖率且易 reward hack。
- **核心贡献**：FSM 驱动的 agent（Init → Generate → Linter → Compile/Execute/Test → Debug）+ 自定义 Triton MTIA Linter + summarization LLM + OpInfo full-sample 测试，用 CWM-32B/GPT-OSS-120B 为 MTIA 自动生成 85% ATen 覆盖率（481/568），E2E 模型 79–87%。
- **关键发现/观点**：现成开源 LLM 不熟悉 MTIA 特定语义，但只要把 linter/compiler/debugger 的结构化反馈以 in-context 方式反复喂回 LLM，模型就能在单次 session 内渐进「蒸馏」出 MTIA 特化约束并产出可通过测试的 kernel——硬件专属文档不必事先塞进 prompt，工具链精确错误信息才是最有效的硬件知识载体。

#### [[f4b9ec30ad9f68f89b29639786cb62ef|Matrix]]
- **作者**：Dong Wang et al.
- **要解决的问题**：多 agent 合成数据生成（Coral/Tau2）依赖集中式 orchestrator 与批级调度，在上万并发任务时成为热点，agentic 控制流复杂性与数据生成规模难以共存。
- **核心贡献**：P2P agent 架构 + row-level scheduling + 可序列化 Orchestrator 消息 + Ray Actor 无状态 agent + 分布式 LLM/Container 服务层 + Ray object store offloading，Coral/NaturalReasoning/Tau2 相对 baseline 吞吐 2–15×。
- **关键发现/观点**：多 agent 工作流的全部状态（控制流位置、对话历史、中间结果）都可以序列化进单一 orchestrator 消息中在 agent 之间点对点传递；一旦做到这点，agent 自身就可以无状态、任意水平扩展，集中式 orchestrator 不再必要；配合 row-level scheduling 就能彻底消除 batch barrier 带来的空闲时间。

---

### 量化、稀疏与边缘推理（6 篇）

#### [[2723d092b63885e0d7c260cc007e8b9d|MixLLM]]
- **作者**：Zhen Zheng et al.
- **要解决的问题**：LLM PTQ 在 4-bit 精度损失明显、反量化拖慢大 batch GEMM，outlier-separation 混精方案通常仅 layer 内 input-feature 维度做、系统实现低效。
- **核心贡献**：在 output-feature 维度做全局显著性混合精度（top-N channel INT8，其余 INT4）+ two-step dequantization + fast I2F bias trick + group-tile 流水，Llama-3.1-70B PPL 抬升从 SOTA 的 0.5 级压到 <0.2，A100 上 W4A8/W8A8 全面超越 SOTA W4A16。
- **关键发现/观点**：不同 output channel 对模型最终 loss 的贡献差异极大且只能在全局视角下识别（v_proj 71% channel 落入全局 top 10%，gate_proj 只 0.73%）；output channel 的 MatMul 结果天然独立，可被拆成两路不同 bit-width 的子 MatMul 再 scatter 拼回，使混精系统实现比 input-feature 维度更友好。

#### [[6512bd43d9caa6e02c990b0a82652dca|HYPERTINYPW]]
- **作者**：Yassien Shaalan et al.
- **要解决的问题**：TinyML 中 separable 1D CNN 的 1×1 pointwise mixer 占 flash 大头（堆 8 层即超 64 kB），已有 PTQ/prune 只做层内压缩，HyperNetworks 的 per-input 生成无法兼容 MCU 实时推理。
- **核心贡献**：共享 micro-MLP generator + per-layer code 在 load time 一次合成所有 PW mixer（保留 PW1 INT8），ECG 三数据集 225 kB 预算下对 1.4 MB RegularCNN1D 实现 6.31× flash 压缩，稳态 INT8 推理无变化。
- **关键发现/观点**：TinyML 中多个 1×1 PW 层存在显著的 cross-layer 冗余，同一组共享低维因子 + 每层 tiny 身份编码就能表达大部分 PW mixer；早期 PW1 对形态敏感独立保留 INT8，其余由 generator 在 load time 合成一次并缓存，就能让推理路径完全走标准 INT8 kernel、延迟抖动为零。

#### [[6ea9ab1baa0efb9e19094440c317e21b|ProfInfer]]
- **作者**：Bohua Zou et al.
- **要解决的问题**：端侧 LLM 推理引擎缺少细粒度 profiler：要么需重编译、要么粒度过粗、要么不能关联 operator 语义与硬件计数器。
- **核心贡献**：基于 eBPF uprobe + perf_event 对 llama.cpp/GGML 做细粒度 tracing，构建 ProfDAG/ProfTime/ProfStat 三视图，Orange Pi 5/RUBIK Pi 3 上 overhead <4%(BCC)/<2%(libbpf)，揭示 KV cache 增长瓶颈、MoE 磁盘 I/O 瓶颈、CPU vs GPU 拐点。
- **关键发现/观点**：llama.cpp/GGML 运行时里，token 生成、graph 计算、operator 计算、后端选择等核心行为都对应稳定的 C/C++ 函数边界，入参是结构良好的 C struct；因此无需改源码或重编译，只要 eBPF uprobe 挂函数并在内核态解引用参数，就能从低层事件流重建 LLM 推理完整高层语义。

#### [[9bf31c7ff062936a96d3c8bd1f8f2ff3|EARTHSIGHT]]
- **作者**：Ansel Kaplan Erol et al.
- **要解决的问题**：LEO 卫星星座多任务影像分析中，现有 OEC 方案把卫星当孤岛节点、任务彼此独立推理，无法在 1–5W 功耗与 10–15 分钟下行窗口内送出高优先级影像。
- **核心贡献**：地面调度器 look-ahead 仿真 + DNF schedule 压缩 + 在轨 multi-task shared backbone + utility-driven filter ordering + CPU-xPU 流水，高优先级影像 P90 延迟从 51 分钟降到 21 分钟，功耗 171%→61%。
- **关键发现/观点**：卫星在轨决策不必依赖自身孤立信息——地面站拥有的全局上下文（查询分布、历史影像统计、下行窗口预测、各星功耗）远比卫星本地丰富，把「粗粒度长期调度策略」下放给地面离线计算、把「细粒度实时执行决策」留给卫星在线自适应，是带宽/功耗双约束下近最优的星座级响应分工。

#### [[d3d9446802a44259755d38e6d163e820|db-SP]]
- **作者**：Siqi Chen et al.
- **要解决的问题**：DiT 视频扩散长序列 block-wise sparse attention 与 Sequence Parallelism 结合时，Ulysses/Ring/USP 都会产生 head-level 与 block-level 两层不平衡，8 GPU 加速比只能 6×。
- **核心贡献**：head-level greedy + block-level biased greedy 的两层分层分区 + reusing threshold + reward factor + 稀疏感知的 U_xR_y 策略动态切换，8× A800/H800 Wan2.1-T2V-14B/CogVideoX1.5-5B attention 1.40×、端到端 1.25×。
- **关键发现/观点**：尽管 head-level 与 block-level 两层不平衡在原始问题中耦合，但每一层单独做 greedy 分区就能把 sparse imbalance ratio 压到接近 1（head ≤1.10、block ≤1.05）；不需要昂贵的联合搜索，而可以把双层联合优化近似分解为两个顺序子问题。

#### [[d67d8ab4f4c10bf22aa353e27879133c|CAGE]]
- **作者**：Soroush Tabesh et al.
- **要解决的问题**：QAT 长期停留在 STE + 启发式 patch，非凸场景下收敛分析都留有「不消失量化误差项」，低比特（W3A3/W2A2）预训练 perplexity 与 FP16 仍有显著差距。
- **核心贡献**：把 QAT 形式化为 Pareto 多目标优化 $\nabla f(x^*) + \lambda(x^* - Q(x^*)) = 0$，以 decoupled correction 方式把量化误差 $x-Q(x)$ 直接叠加到 Adam 更新上，Llama-style 6 尺寸 × 3 精度预训练中 CAGE W3A3 > QuEST W4A4，理论 $\mathcal{O}(1/\sqrt{T})$ 无量化常数项。
- **关键发现/观点**：由于量化算子 Q 不可逆，传统 QAT 目标「找 x* 使 ∇f(Q(x*))=0」在一般非凸场景下无解，应换一个可达的最优性概念——Pareto 最优性；其 KKT 条件 ∇f(x*) + λ(x* - Q(x*)) = 0 中的 x-Q(x) 恰好是 QAT 循环中免费可得的量化误差，可作为梯度修正信号而无需新的前向/反向计算。

---

### 安全、隐私、联邦学习与系统验证（8 篇）

#### [[3988c7f88ebcb58c6ce932b957b6f332|ProToken]]
- **作者**：Waris Gill et al.
- **要解决的问题**：联邦学习训练出的 LLM 生成响应时无法追溯每个 token 主要由哪个客户端的数据驱动，自回归依赖与神经元爆炸使传统 provenance 不适用。
- **核心贡献**：利用 FL 聚合的线性分解 + 只监控最后 N 个 transformer block + 梯度 × 激活相关性打分，4 模型 × 4 领域 × 6/55 客户端 backdoor 归因 98.62%，per-token 同步完成。
- **关键发现/观点**：FedAvg 风格聚合在参数空间线性（θ_global = Σρ_i θ_i），因此每个神经元激活前输出严格等于各客户端同位置输出的加权和，这是 provenance 可追踪的数学基础；加上「Transformer 后几层集中存放任务特定知识」与「token logit 对层激活的梯度即相关性权重」两个经验观察，就能把归因压到 O(N) 层级。

#### [[4e732ced3463d06de0ca9a15b6153677|PRIVATAR]]
- **作者**：Jianming Tong et al.
- **要解决的问题**：多用户 VR avatar 重建在头显算力受限下必须卸载到局域网中不可信 GPU，各向同性 DP 噪声在高维 latent 上会摧毁效用。
- **核心贡献**：horizontal frequency partitioning 把高能量基频留本地、低能量非基频卸载 + distribution-aware PAC-Privacy anisotropic 噪声，Meta Quest Pro 上 2.37× 用户、+9% 能耗、8.3% loss 增加、e-PSR 随机猜水平。
- **关键发现/观点**：人脸 texture 的能量在 block DCT 下极度不均衡（基频占 94.9% 能量），同一用户的表情 latent 分布短时间内几乎静态；把基频留本地保障质量，只把低能量非基频卸载到不可信设备，并用各向异性 PAC noise 按真实分布校准，避免 LDP 各向同性噪声淹没小值维度。

#### [[735b90b4568125ed6c3f678819b6e058|ZK-APEX]]
- **作者**：Mohammad M Maheri et al.
- **要解决的问题**：edge personalized 部署下 provider 需要验证每个 client 确实执行了删除请求，但 retraining 和 gradient ascent 等方法 ZK 证明开销巨大手机上无法完成。
- **核心贡献**：ZK-APEX 把 unlearning 形式化为 provider-side 稀疏 mask 选择 + client-side Group-OBS 二阶闭式补偿的线性算子，ZK-SNARK 电路只校验三组线性恒等式，ViT-B/16 达 ~99% 个性化精度 + 2 小时证明 + 400MB proof + 手机可执行，相对 retraining 加速 >10^7。
- **关键发现/观点**：神经网络中某一类信息往往在参数空间中局部化，因此「遗忘」可以简化为对 forget-set 最 salient 的少量参数做 masking，而「保留个性化」则可以用 OBS 二阶曲率补偿从闭式线性公式解出来；这个线性零训练步的 unlearning operator 恰好规避了 SGD 随机性（抵御 forging attack）又天然匹配 ZK-SNARK 对线性算子的偏好。

#### [[73278a4a86960eeb576a8fd4c9ec6997|Hawkeye]]
- **作者**：Erez Badash et al.
- **要解决的问题**：verifiable ML 需要 bit-exact 重演，但 NVIDIA Tensor Core 内部 pipeline（累加树、内部 mantissa、rounding、subnormal）闭源，非结合浮点让 auditor 无法在 CPU 上精确重算。
- **核心贡献**：5 类针对性微分探针测试逆向出 Ampere/Hopper/Lovelace × FP16/BF16/FP8 Tensor Core mma 数值 pipeline，构建 CPU simulator 在 100K 随机 16×16 tile 上 100% bit-exact。
- **关键发现/观点**：Tensor Core 的 mma 指令虽是硬件黑盒，但其浮点数值行为（累加分组结构、内部 mantissa 位宽、对齐 shift 的 rounding mode、subnormal 归一化、最终截断）的每一维都可通过精心构造的「微分探针」独立探测出来，且跨架构/精度切换时变化有限，可用同一套 test suite 重建。

#### [[812b4ba287f5ee0bc9d43bbf5bbe87fb|H100 GPU-CC Security Study]]
- **作者**：Zhongshu Gu et al.
- **要解决的问题**：NVIDIA Hopper GPU-CC 缺公开规范、组件闭源且架构跨异构 legacy，AI/ML 部署无法判断是否真正满足机密计算要求。
- **核心贡献**：对 H100 GPU-CC 系统反向工程——辨识 FSP/GSP/SEC2/CE + 40+ 密钥、拆解 CEC→FSP→GSP→SEC2 信任链 + BAR0 防火墙 + 五级证书链 attestation，发现 RMAPI metadata 明文暴露、CPU-GSP DMA timing 侧信道、SEC2 semaphore 未加密等问题并披露 PSIRT。
- **关键发现/观点**：GPU-CC 的安全性不是由单个引擎决定，而是由「CPU 信任域 ↔ 不受信任 PCIe ↔ GPU 信任域」之间每条数据路径上「加密/签名/staging buffer/metadata」组合的最弱环节决定；NVIDIA 为维持 legacy 兼容在多条路径上只加密 payload 而留下 queue header、地址表、pointer、semaphore 等明文 metadata。

#### [[d2ddea18f00665ce8623e36bd4e3c7c5|PLayer-FL]]
- **作者**：Ahmed Elhussein et al.
- **要解决的问题**：现有 partial-FL 依赖架构特定、人工预设层划分，没有跨架构通用、跨任务稳健的层级联邦指标。
- **核心贡献**：定义 federation sensitivity $F_l = \sum_{k\le l} \tfrac{1}{n_k}\sum_p (\theta_p \nabla\theta_p)^2$，第 1 个 epoch 后识别 sensitivity 突增点作为联邦边界，7 个 cross-silo benchmark 上 Macro-F1/fairness/incentivization 平均秩全最佳，与 FedAvg 同阶复杂度。
- **关键发现/观点**：借用模型剪枝的一阶参数重要性近似，某层在联邦中「是否值得 share」可以通过 (θ_p ∇θ_p)² 累积到该层的标量度量；且该 sensitivity 的 pattern 在第 1 个 epoch 后就稳定显现——非 IID 客户端浅层 loss 面平坦/表征相似，深层陡峭/表征分化，突增点对应最佳边界，一次计算即可决定结构。

#### [[da4fb5c6e93e74d3df8527599fa62642|DP-ZeRO]]
- **作者**：Zhiqi Bu et al.
- **要解决的问题**：ZeRO 是 DP 向大规模扩展的关键路径，但 DP 库 module hook 与 ZeRO tensor hook 不兼容，per-sample gradient 与参数分片冲突，mixed-precision loss scaling 与 per-sample clipping 会双重缩放。
- **核心贡献**：把数学梯度分片（layer-wise vs element-wise）与 ZeRO 硬件分片解耦 + hook 融合 + mixed-precision BK + bf16 + 关闭 loss scaling，256 A100 上首次 DP 训成 GPT-100B，速度达到非 DP ZeRO 95%+，一行 PrivacyEngine 集成 DeepSpeed/FSDP。
- **关键发现/观点**：DP 只改变反向传播（clipping 因子 + Gaussian noise），而 ZeRO 的分布式效率收益主要来自模型状态分片与通信调度，这两部分与「算哪种梯度」完全正交；只要让 DP back-propagation 自身的速度/内存开销接近标准反传，DP-ZeRO 整体效率就自动等同于标准 ZeRO。

#### [[eccbc87e4b5ce2fe28308fd9f2a7baf3|FLoRIST]]
- **作者**：Hariharan Ramesh et al.
- **要解决的问题**：现有 federated LoRA 方案无法同时满足数学正确聚合、异构 rank 支持、低通信、低 server 计算；尤其 FlexLoRA 需要显式 ΔW full SVD，server FLOPs 在 LLaMA-7B 达 2209B。
- **核心贡献**：对 B_stack/A_stack 分别 SVD + 中间矩阵 P SVD + 能量阈值截断得到最优全局 rank，TinyLLaMA/LLaMA-3.2-1B/LLaMA-7B × Dolly/Alpaca/Wizard 上 MMLU 最佳，server 计算相对 FlexLoRA ~350× 少、下行通信数量级减少。
- **关键发现/观点**：聚合后的全局更新矩阵 $\Delta W = \sum_k \tfrac{n_k}{N} B_k A_k$ 具有低内禀维度——即使各 client 用 rank 高达 64，$\Delta W$ 的奇异值通常在前 8–10 个就快速衰减；因此 server 完全没必要显式构造完整 $\Delta W$，双 SVD + 低维中间矩阵就能得到真实奇异值并按能量阈值选出全局最优 rank。

---

### 网络、硬件与系统基准（7 篇）

#### [[34173cb38f07f89ddbebc2ac9128303f|Chakra]]
- **作者**：Srinivas Sridharan et al.
- **要解决的问题**：分布式 ML 系统 HW-SW 协同设计缺乏跨厂商/跨框架通用执行轨迹 schema，生产模型 IP 无法共享使模拟器和学术 benchmark 无法代表真实 workload。
- **核心贡献**：Chakra execution-trace schema 与配套工具链（converter、visualizer、test case generator、trace feeder、生成式合成模型），ASTRA-sim-v2 上完成端到端 PoC，奠定 MLCommons 轨迹交换基础。
- **关键发现/观点**：协同设计所需的信息（compute/memory/communication 算子的尺寸与依赖）与「模型本身/数据集」可以解耦——这些信息在 PyTorch/TF 执行过程中已经自然产生，只要编码算子维度和依赖而不编码权重、层定义、数据，就能在保留性能建模全部要素的同时天然脱敏模型 IP。

#### [[3def184ad8f4755ff269862ea77393dd|PARROT — Sycophancy Benchmark]]
- **作者**：Yusuf Çelebi et al.
- **要解决的问题**：现有 LLM 评测难以捕捉「在权威错误压力下答案切换 + 置信反转」的渐进式知识塌缩，且没有覆盖多家 provider 的可重复工程化评测基础设施。
- **核心贡献**：双路径 prompt + 锚定 logprob 校准 + 八态行为分类 + 开源评测工具，22 模型 × 1302 MMLU 题 × 27K 评估上揭示从 GPT-5(4%) 到 Qwen2.5-1.5B(94%) 近 20× follow rate 跨度。
- **关键发现/观点**：Sycophancy 不是单一指标（answer flip）能描述的二元现象，而是沿「答案切换 + 置信度反转」两个维度同时演化的渐进式知识塌缩；同一 follow rate 可来自「正确滑向错误」或「错误转向另一错误」，需配对 baseline/manipulated 双路径 + token 级 logprob 校准 + 八态分类才能分离。

#### [[42a0e188f5033bc65bf8d78622277c4e|Lightweight Collective NoC]]
- **作者**：Luca Colagrande et al.
- **要解决的问题**：tile-based ML 加速器上片上集合通信（broadcast/reduction/barrier）缺乏硬件加速，算术 reduction 成本一直被视为过高。
- **核心贡献**：在 FlooNoC 之上扩展 multicast/reduction router + Direct Compute Access（NoC 直接借用 Snitch cluster 内 SIMD FPU 做网内算术 reduction），16.5% router 面积（<1% tile）换 multicast/reduction 2.9×/2.5×、GEMM 3.8×、1.17× 能效。
- **关键发现/观点**：计算 tile 内 FPU 阵列已是大块面积投资且在等数据时常常空闲；与其在 NoC 里再造一组算术单元，不如让 NoC 直接「借用」cluster 内 FPU（类似 DMA 借用内存端口），即 Direct Compute Access，网内算术 reduction 几乎无额外硬件开销。

#### [[65b9eea6e1cc6bb9f0cd2a47751a186f|Reparo]]
- **作者**：Tianhong Li et al.
- **要解决的问题**：传统视频 codec 在互联网丢包下必须靠 FEC 冗余才能解出 I/P 帧，冗余率选择两难、帧间依赖把单点丢包级联放大。
- **核心贡献**：把帧 VQGAN tokenize 成 32×32 token、按空间分散打包、用 spatio-temporal ViT 在 token 空间对缺失做 masked image generation，worst 10% PSNR 比 VP9+Tambur 高 11.5–16.4 dB，33ms 实时预算。
- **关键发现/观点**：对于视频会议这种高度受限的视觉域（人脸/说话头），一个小规模视觉 token codebook 就足以充分表达所有可能内容，因此丢失的 token 可以由生成模型基于剩余 token + 历史帧 + 领域先验「脑补」重建，无需 FEC 冗余字节——即「用语义级冗余替代比特级冗余」。

#### [[ad61ab143223efbc24c7d2583be69251|SAKURAONE]]
- **作者**：Fumikazu Konishi et al.
- **要解决的问题**：中等规模（100–1000 GPU）开放栈 LLM 集群缺少公开的性能与运营数据，SONiC/RoCEv2 栈在生产 LLM 训练下无公开可用性证据。
- **核心贡献**：SAKURAONE（100 × 8×H100 + 800 GbE SONiC/RoCEv2 + 2 PB Lustre），Top500 第 49，MLPerf GPT-3 175B 时间仅比 DGX H100 Eos 差 2–17%，9 个月医疗 LLM 项目 telemetry 描绘 LLM 开发负载双重性。
- **关键发现/观点**：只要把 ECN/PFC/shared buffer 按交换机 buffer 容量精细调过，800 GbE Ethernet + RoCEv2 就能在生产 AI fabric 中追上 InfiniBand 的效率，关键瓶颈不在协议本身而在 cross-layer（firmware/kernel/RDMA stack）协调；且对 LLM 项目，即便单租户单项目，工作负载在数量上由小作业主导、在 GPU-occupied time 上由大作业主导——这是 LLM 开发固有双重性而非多租户特有。

#### [[c51ce410c124a10e0db5e4b97fc2af39|TransferEngine]]
- **作者**：Nandor Licker et al.
- **要解决的问题**：新型 LLM 部署（disaggregated inference、MoE dispatch、RL weight sync）需要点对点高吞吐 RDMA，但 NCCL collective 抽象不合适，DeepEP/NVSHMEM/Mooncake/NIXL 都绑死 ConnectX 或在 EFA 上不可用。
- **核心贡献**：Rust 实现 + libfabric/libibverbs 双后端 + 8 个 tile 级 API + IMMCOUNTER，Perplexity 生产上 1T 模型 RL 权重同步 1.3s（>100× 现有框架）、MoE decode dispatch/combine 在 ConnectX-7 超过 DeepEP、EFA 首次可用；单 NIC 378 Gbps single WRITE。
- **关键发现/观点**：ConnectX RC 与 EFA SRD 之间存在关键的功能交集——两者都能提供 reliable-but-unordered 的交付语义（RC 可忽略有序保证，SRD 本身无序）；只要 LLM P2P 通信库主动放弃顺序保证，就能在异构 RDMA 硬件上构造统一的 WRITE/WRITEIMM 抽象，并通过独立的 IMMCOUNTER 原语替代依赖顺序的完成通知。

#### [[ec8956637a99787bd197eacd77acce5e|StreamDiffusionV2]]
- **作者**：Tianrui Feng et al.
- **要解决的问题**：视频扩散模型离线单批 81 帧推理使 TTFF 5s+ 无法满足直播 SLO，长时运行还会出现 sink 老化、RoPE 相位漂移与运动撕裂。
- **核心贡献**：SLO-aware batching + 动态 sink token/RoPE 刷新/滚动 KV + motion-aware noise + 多管道流水并行 + 动态 DiT block scheduler + Stream-VAE，4×H100 上 14B 模型 58 FPS、TTFF 0.47s、1s SLO miss rate 0.2%。
- **关键发现/观点**：直播场景下因果视频 DiT 天然位于 memory-bound 区间（H100 上 4 帧 chunk 算术强度 ≈0.84 ≪ ridge 660），因此必须围绕「显存流量塑形」而非「算力利用率」——把固定大 chunk 换成可调小 chunk、用 batch 而非 sequence 提升带宽利用率、用 pipeline 而非 sequence parallelism 扩多卡。

---

## 研究趋势分析

**1. 推理侧的"二次拆分"与工作流型调度成为主旋律。** 本届最密集的议题是 LLM serving 内部的结构重组——从粗粒度的 PD disaggregation 延伸到更细粒度的阶段/模式/精度拆分。[[ec5decca5ed3d6b8079e2e7e7bacc9f2|LAPS]] 把 PD 架构里的 prefill 再拆成长短两类独立池；[[202cb962ac59075b964b07152d234b70|Beyond the Buzz — Disaggregation]] 证明 disaggregation 的最优形态高度依赖流量与 SLO，必须靠动态 rate matching 维持；[[8f14e45fceea167a5a36dedd4bea2543|SuperInfer]] 进一步把推理比作 OS，用抢占式 rotary 调度顶住 GH200 级紧耦合内存层次的复杂度；[[fc490ca45c00b1249bbe3554a4fdf6fb|MorphServe]] 则在 "拆分" 的正交轴上加了一个「精度-容量」维度，token 级 swap 层权重与 KV。共同点是：静态并行度与静态精度都不再够用，调度器必须沿多个正交维度实时重新平衡。

**2. KV cache 从"存储压缩"走向"时间结构利用"。** 早年的 KV 优化围绕量化与驱逐，本届论文转向挖掘时间/序列/head 级的结构冗余：[[5ef059938ba799aaa845e1c2e8a762bd|MAC-Attention]] 利用单 decode 流中 query 的时间冗余，在 pre-RoPE 空间复用历史 attention summary；[[76dc611d6ebaafc66cc0879c71b5db5c|FlexiCache]] 发现不同 head 的 top-K 页重合度稳定且模型内禀，从而可以用中间时间尺度的迁移替代"每步重排 vs 永远丢弃"的二选一；[[92cc227532d17e56e07902b254dfad10|SkipKV]] 看到 reasoning 轨迹的真正冗余发生在句子级而非 token 级；[[d82c8d1619ad8176d665453cfb2e55f0|BLASST]] 则发现 FlashAttention online softmax 本身就隐含稀疏判据。这些工作共享一个观察：KV cache 的有用维度不是大小，而是"哪些时间-head-语义子结构真正贡献信息"，对这个结构做细粒度利用比做统一压缩更划算。

**3. Speculative decoding 从"更大 drafter"转向"更懂 workload 的 verify 阶段"。** [[f0935e4cd5920aa6c7c996a5ee53a70f|Speculative Decoding — Performance or Illusion?]] 直接指出 verification 占 42–95% 执行时间，因此"加强 drafter"不如"降低被拒绝 token 的浪费"；[[6f4922f45568161a8cdf4ad2299f6d23|SparseSpec]] 正是这一洞察的落地——verify 阶段反正要做一次 full attention，其 attention score 天然是 critical-token oracle；[[67c6a1e7ce56d3d6fa748ab6d9af3fd7|TiDAR]] 发现 GPU 解码阶段存在"free token slots"，可以在单次 forward 里免费塞入 diffusion drafting；[[f899139df5e1059396431415e770c6dd|DAS]] 则把 SD 用在 RL rollout 上，因 RL 独特的 prompt 反复出现与长尾 makespan 属性而摒弃参数化 drafter 改用 per-problem suffix tree。Drafter 与 verifier 正被重新分工：drafter 可以轻量，verifier 要产出可被下一步复用的副产品。

**4. Agent 从"prompt engineering"切向"系统软件"。** 多篇论文把 agent 当作带状态/调度/SLA 的分布式系统对待：[[5fd0b37cd7dbbb00f97ba6ce92bf5add|OpenHands SDK]] 重构后把 ConversationState 变为唯一可变状态、支持 deterministic replay；[[f4b9ec30ad9f68f89b29639786cb62ef|Matrix]] 把 orchestrator 消息序列化实现 P2P 无状态 agent 以消除集中式热点；[[d645920e395fedad7bbbed0eca3fe2e0|HIPPOCAMPUS]] 把 agent memory 从 dense embedding+ANN 换成 succinct data structure 上的 bitwise 检索，把 GPU-heavy 操作彻底移回 CPU；[[6364d3f0f495b6ab9dcf8d3b5c6e0b01|OSWorld-Human]] 把 CUA 评测从成功率扩展到 wall-clock 效率，暴露出 planning+reflection 占 75–94% 延迟的系统级瓶颈。此外 [[35f4a8d465e6e1edc05f3d8ab658c551|VeriMoA]]、[[19ca14e7ea6328a42e0eb13d585e4c22|AccelOpt]]、[[54229abfcfa5649e7003b83dd4755294|PIKE]]、[[e2ef524fbf3d9fe611d5a8e90fefdc9c|TritorX]] 把 agent 做进工具链本身——agent 正在成为"给硬件写后端、给 HDL 写代码、给 kernel 写优化"的廉价替代品。

**5. 异构性从负担变成一等公民。** 过去异构意味着需要被同质化掩盖；本届异构被当作可被调度器主动利用的维度。[[d9d4f495e875a2e075a1a4a6e1b9770f|BOUTE]] 把异构模型与异构 GPU 联合优化，使"小模型跑在消费级 GPU、大模型跑在 H100"这一互补性显式成为优化目标；[[9a1158154dfa42caddbd0694a4e9bdc8|HexiScale]] 要求 DP/PP/TP 三维都支持完全非对称并行；[[7f39f8317fbdb1988ef4c628eba02591|HetRL]] 把异构 GPU 思想带入 RL 训练；[[c51ce410c124a10e0db5e4b97fc2af39|TransferEngine]] 则在 RDMA 层统一 ConnectX RC 与 EFA SRD——关键手段是"主动放弃顺序保证"以换取最大公约数接口。这些工作共享一条方法论：异构环境下的最优策略不是"最小化异构性"，而是"在异构维度上显式建模每个资源的比较优势"。

**6. FP8/低比特正从"推理 trick"走向"训练一等公民"。** [[072b030ba126b2f4b2374f342be9ed44|FP8-Flow-MoE]] 用 2 的幂 scaling factor 让 FP8 layout 转换变成 exponent-bit 整数操作，去除 12 次 cast；[[2723d092b63885e0d7c260cc007e8b9d|MixLLM]] 把混精扩到 output-feature 维度以对齐 GPU GEMM 友好的并行维；[[d67d8ab4f4c10bf22aa353e27879133c|CAGE]] 在理论上把 QAT 的目标从 ∇f(Q(x))=0 换为 Pareto 最优，解决了非凸 QAT 长期没有严格收敛的核心问题；[[e369853df766fa44e1ed0ff613f563bd|Kitty]] 把 2-bit KV cache 从"灾难级掉分"抢救回可用精度。低比特的底层硬件支持已到位，现在是数据流与优化理论追赶硬件的阶段。

**7. 安全/隐私与系统协同设计重新活跃。** 不再是合规层加封装的模式，而是把隐私约束当成系统设计的输入：[[da4fb5c6e93e74d3df8527599fa62642|DP-ZeRO]] 把 DP 与 ZeRO 的 hook 全栈融合，首次 DP 训成 GPT-100B；[[735b90b4568125ed6c3f678819b6e058|ZK-APEX]] 把 unlearning 形式化成线性算子以完美匹配 ZK-SNARK；[[73278a4a86960eeb576a8fd4c9ec6997|Hawkeye]] 用微分探针逆向 Tensor Core 数值 pipeline 以支撑 verifiable ML；[[812b4ba287f5ee0bc9d43bbf5bbe87fb|H100 GPU-CC Security Study]] 指出 GPU-CC 的弱点在于 legacy 兼容留下的明文 metadata。这些工作意味着可验证 ML 与机密计算正从理论走向工程可部署。

---

## 值得关注的方向

**1. 在 vLLM / SGLang 插件层复现"二次拆分"类研究。**
- **方向描述**：LAPS / Span Queries / BLASST / FlexiCache 这类工作共同的范式是"在既有推理引擎上加一层薄调度层或 kernel hook"，改动量通常在几百到几千行，而收益可达 1.2–2× end-to-end。
- **为什么小团队能做**：不需要自研推理引擎，主流 vLLM v1 / SGLang 都已稳定；评测负载可用公开 trace（ShareGPT、LongBench、AIME）；H100 单卡或 4×A100 已足够复现大多数数字。
- **哪些论文指向这个空白**：[[3416a75f4cea9109507cacd8e2f2aefc|Span Queries]] 用 <500 行 vLLM 修改演示了上层 IR 能撬动的巨大价值；[[d82c8d1619ad8176d665453cfb2e55f0|BLASST]] 证明 kernel 里已有的 online softmax 状态就是免费稀疏 oracle；[[ec5decca5ed3d6b8079e2e7e7bacc9f2|LAPS]] 把"PD 内部再拆一次"作为 pattern。
- **具体 open problems**：(a) 把 LAPS 的"长短 prefill 拆分"推广到带 retrieval 的 agentic trace；(b) 给 Span Query IR 加 ITS / MCTS-style 的执行计划；(c) 把 [[76dc611d6ebaafc66cc0879c71b5db5c|FlexiCache]] 的 head 稳定性分类扩展到 MoE expert 稳定性分类，用同样的"中间时间尺度迁移"思想做 expert replica。

**2. 基于 eBPF / uprobe 的推理可观测性工具。**
- **方向描述**：把 [[6ea9ab1baa0efb9e19094440c317e21b|ProfInfer]] 的思想推广到 vLLM/SGLang/TGI，做细粒度、低侵入、可解析 operator 语义的 profiler；进一步衔接 [[6364d3f0f495b6ab9dcf8d3b5c6e0b01|OSWorld-Human]] 的 agent 级 wall-clock 拆解。
- **为什么小团队能做**：eBPF/bpftrace 工具链成熟，不需要改内核或推理引擎源码；观测数据集可用公开 workload；单机即可做实验。
- **哪些论文指向这个空白**：[[6ea9ab1baa0efb9e19094440c317e21b|ProfInfer]] 在 llama.cpp/GGML 上验证了 <4% overhead；[[6364d3f0f495b6ab9dcf8d3b5c6e0b01|OSWorld-Human]] 指出 agent 级延迟瓶颈根本没有统一 profiler。
- **具体 open problems**：(a) vLLM continuous batching 内部跨 request 的事件归因（哪次 kernel 属于谁）；(b) 把 profiler 做成可与 FlashInfer-Bench trace schema 双向转换的工具，进而让 agent 自动定位 kernel 瓶颈。

**3. 用 LLM agent 自动生成硬件后端 kernel（非 NVIDIA 平台）。**
- **方向描述**：沿 [[19ca14e7ea6328a42e0eb13d585e4c22|AccelOpt]] / [[e2ef524fbf3d9fe611d5a8e90fefdc9c|TritorX]] / [[a3f390d88e4c41f2747bfa2f1b5f87db|LLaMEA]] 的路径，为 AMD CDNA、Apple silicon、Trainium 之外的新兴加速器（寒武纪、Graphcore、OneDNN CPU）自动生成 ATen 后端覆盖。
- **为什么小团队能做**：AccelOpt 用 ~$210 开源模型就达到了 $5800 Claude Sonnet 4 的水平；关键瓶颈是工具链（linter/compiler/profiler）而非模型算力；在消费级 AMD GPU（MI210/W7900）或 Apple M3 Max 上都能验证。
- **哪些论文指向这个空白**：[[2a38a4a9316c49e5a833517c45d31070|HipKittens]] 证明 AMD 硬件已接近 NVIDIA，只缺软件；[[e2ef524fbf3d9fe611d5a8e90fefdc9c|TritorX]] 证明硬件专属文档可以不入 prompt，工具链反馈就是最好的"知识载体"。
- **具体 open problems**：(a) 给 AMD ROCm 或 Apple MLX 做类似 TritorX 的 85% ATen 覆盖 agent；(b) 把 [[a3f390d88e4c41f2747bfa2f1b5f87db|LLaMEA]] 的 LLM+EA 闭环应用到 PyTorch inductor tile 调优；(c) 跨加速器的 OpInfo 级测试套件复用。

**4. 低秩 / bottleneck 架构的训练与推理系统工程。**
- **方向描述**：LoRA 类方法已经普及，但 [[fe9fc289c3ff0af142b6d3bead98a923|BOOST]] 揭示"低秩"作为架构主干时 TP/通信需要完全重做；[[eccbc87e4b5ce2fe28308fd9f2a7baf3|FLoRIST]] 进一步揭示聚合空间本身的低秩结构。这是一个仍然欠缺系统层工作的方向。
- **为什么小团队能做**：低秩模型参数量小，1B–3B 规模用 1–2 台 8 GPU 节点即可训练；bottleneck 架构的消融实验代价明显低于全精度 7B 训练。
- **哪些论文指向这个空白**：[[fe9fc289c3ff0af142b6d3bead98a923|BOOST]]、[[eccbc87e4b5ce2fe28308fd9f2a7baf3|FLoRIST]]、[[c45147dee729311ef5b5c3003946c48f|PyLO]] 共同指出"bottleneck 是天然的通信/内存优化窄腰"。
- **具体 open problems**：(a) 在 FSDP/TP 栈里原生支持 bottleneck-aware sharding；(b) 低秩推理加速（把 BOOST 的思想搬到推理侧，把所有 AllReduce 推到低秩位置）；(c) 把 FLoRIST 的双 SVD 思想用到 federated continual learning。

**5. Agent 记忆与 RAG 的"去向量化"方向。**
- **方向描述**：[[d645920e395fedad7bbbed0eca3fe2e0|HIPPOCAMPUS]] 和 [[093f65e080a295f8076b1c5722a46aa2|LEANN]] 都在挑战 "dense embedding + ANN" 的默认假设，一个用 succinct data structure 直接在 token-id 域做位运算，另一个用 graph pruning + 按需重算 embedding。这条路线开辟了 CPU 上运行 agent 记忆 / 个人 RAG 的可能。
- **为什么小团队能做**：完全不需要 GPU；索引结构、检索算法都可以在 Rust/C++ 单机实现；评测集（LoCoMo / LongMemEval / BRIGHT）公开。
- **哪些论文指向这个空白**：除了上述两篇，[[3416a75f4cea9109507cacd8e2f2aefc|Span Queries]] 进一步暗示 cache 与 retrieval 本质上是同一种 locality。
- **具体 open problems**：(a) 把 Wavelet Matrix 思想推广到 multimodal token（音频、视频 token）；(b) LEANN 的 encoder re-compute 模型做量化-感知设计以进一步压低 latency；(c) 把 succinct memory 与 LLM 内部 KV cache 在同一 IR 中统一索引。

**6. Small-data RLVR / RL post-training 在小模型上的方法论研究。**
- **方向描述**：[[7f1de29e6da19d22b51c68001e7e0e54|Learning from Less]] 揭示在 4B LoRA + 500 样本级别 RLVR 的数据组成规律，这是一类小团队可负担的 RL 研究范式。
- **为什么小团队能做**：4B 模型 LoRA 单 H100 可跑，数据集可 procedurally generate（Counting / Graph / Spatial），对应的 open-ended reward 用规则即可验证；全套实验 20 组 × 数小时 ≪ 主流 RL 训练成本。
- **哪些论文指向这个空白**：[[7f1de29e6da19d22b51c68001e7e0e54|Learning from Less]] 本身；[[f899139df5e1059396431415e770c6dd|DAS]] 暗示 RL rollout 的长尾/重复结构值得更细粒度的样本预算分配。
- **具体 open problems**：(a) 把"难度多样性 ≈ 数据量"的 claim 推广到代码/数学/agent 场景；(b) 研究 GRPO 的 reward 方差与 rollout 多样性如何与 SD 长尾预算调度（DAS）协同；(c) 在 LoRA rank 很低时的 RL 稳定化技巧。

**7. 基于 Verilog / HDL 的低预算硬件敏捷研发。**
- **方向描述**：[[35f4a8d465e6e1edc05f3d8ab658c551|VeriMoA]] 证明 7B 开源模型 + 缓存式 multi-agent 可以打过 32B 单模型，这让 HDL 级硬件快速原型对小团队变得可行。
- **为什么小团队能做**：Verilog 仿真工具（Verilator、Icarus）本地即可跑；VerilogEval/RTLLM 等 benchmark 公开；7B 模型在消费级 GPU 即可 inference。
- **哪些论文指向这个空白**：[[35f4a8d465e6e1edc05f3d8ab658c551|VeriMoA]]；和 [[42a0e188f5033bc65bf8d78622277c4e|Lightweight Collective NoC]] 的 FlooNoC 开源栈结合，小团队可以尝试"LLM 生成的 NoC 变体 + RTL 仿真 + 功耗估计"闭环。
- **具体 open problems**：(a) 把 VeriMoA 的 quality-guided cache 推广到 Chisel/SpinalHDL 等更高层 DSL；(b) 在 FlooNoC 仿真平台上用 LLM agent 自动搜索 collective router 参数（带宽 / 面积 trade-off）。

**8. 视频生成的流式系统方向。**
- **方向描述**：[[ec8956637a99787bd197eacd77acce5e|StreamDiffusionV2]] 与 [[65b9eea6e1cc6bb9f0cd2a47751a186f|Reparo]] 共同暗示"用生成模型做实时视频"已接近可部署状态，但整体系统工程（SLO-aware batching、motion-aware noise、VAE 流式化）还非常欠缺标准化。
- **为什么小团队能做**：4×H100 即可复现 StreamDiffusionV2 的主要数字；Reparo 在单卡即可跑；视频会议 trace（MIT talking-head）公开。
- **哪些论文指向这个空白**：[[ec8956637a99787bd197eacd77acce5e|StreamDiffusionV2]]、[[65b9eea6e1cc6bb9f0cd2a47751a186f|Reparo]]、[[d3d9446802a44259755d38e6d163e820|db-SP]]（视频扩散的稀疏 SP）。
- **具体 open problems**：(a) 把 StreamDiffusionV2 的 SLO-aware batching 扩展到多用户共享 GPU；(b) Reparo 的"语义级冗余"思想用于实时 screen share 或游戏流；(c) db-SP 在 8 GPU 以上的可扩展性与成本。

---

## 面向量化公司 AI Lab 的针对性梳理

本节面向「量化公司 AI Lab / AI Infra 小组」的工作定位重新切片相同的 79 篇论文。该类团队通常承担三件事：(1) 偏工程的 MLOps 平台（任务提交、数据集/模型管理、实验复现）；(2) 基于 MLOps 做 agent / auto research 加速研究；(3) 训练时序预测模型（transformer 或 diffusion）。

### 一、MLOps 平台工程

**可直接借用/集成**

- [[28dd2c7955ce926456240b2ff0100bde|AXLearn]]：Apple 开源的生产级训练框架，通过严格 encapsulation 把新增特性的代码复杂度从 O(NM) 压到 O(1)。若计划自建或重构训练框架，这是目前架构最干净的公开参考。
- [[8613985ec49eb8f757ae6439e879bb2a|OPTIKIT]]：eBay 生产级 LLM 自动优化流水线，把量化/calibration/benchmark/tuning 串成 declarative recipe + Bayesian TPE，人工工时从 80–100h 压到 15–25h。对"把模型交付为服务"这条产品线可直接抄。
- [[6ea9ab1baa0efb9e19094440c317e21b|ProfInfer]]：基于 eBPF uprobe 对 llama.cpp/GGML 做零侵入细粒度 profiling，overhead <4%。思路可直接迁移到内部推理/训练服务，不改源码、不重编译，适合做 MLOps 平台的诊断层。
- [[642e92efb79421734881b53e1e1b18b6|veScale-FSDP]]：ByteDance 生产 FSDP，原生支持 block-wise 量化 + Shampoo/Muon 等矩阵优化器。若已用或打算用 Muon/SOAP 训时序大模型，这比 PyTorch FSDP2 更友好。
- [[a3c65c2974270fd093ee8a9bf8ae7d0b|ProTrain]]：自动显存管理，一次 profiling 搜出 ZeRO/offload/checkpoint 的 140+ 参数最优组合，4×3090/A100 上可训模型从 15B 推到 34B。对"让算法同学不用手调训练参数"这条产品线可直接集成。
- [[34173cb38f07f89ddbebc2ac9128303f|Chakra]]：执行轨迹 schema，编码算子尺寸 + 依赖但不编码权重/数据。量化公司模型与数据集是强 IP，Chakra 让内部可共享 workload 描述而不泄漏 model。

**值得 follow-up 的 research**

1. **量化 workload 的内部执行轨迹基础设施**：以 Chakra schema 为底层，把 [[6ea9ab1baa0efb9e19094440c317e21b|ProfInfer]] 的 eBPF tracing + 特有的回测/特征 pipeline 行为编码成统一轨迹，既可做性能建模也可做"workload fingerprint"对比。量化行业目前无公开方案。
2. **"PD disaggregation 二次拆分"思路外推到任务调度**：[[ec5decca5ed3d6b8079e2e7e7bacc9f2|LAPS]] 把 prefill 再拆成长短两池，[[202cb962ac59075b964b07152d234b70|Beyond the Buzz — Disaggregation]] 证明静态配比必死。这个"运行时看流量再拆资源池"的范式可自然延伸到回测 vs 在线推理 vs 离线训练的混布。

### 二、Agent / Auto Research 加速研究

**可直接借用/集成**

- [[5fd0b37cd7dbbb00f97ba6ce92bf5add|OpenHands SDK]]：生产级 software agent SDK，事件溯源 ConversationState + deterministic replay + sandbox opt-in，SWE-Bench Verified 72.8%。做 auto research 的最佳底座——不自己造轮子，把"跑实验、改超参、写回测脚本"包装成 agent 的 tool。
- [[f4b9ec30ad9f68f89b29639786cb62ef|Matrix]]（Meta FAIR）：P2P multi-agent 架构，orchestrator 消息可序列化，agent 无状态 + row-level scheduling。上千并发实验时集中式 orchestrator 必成瓶颈，此设计范式应提前内化。
- [[19ca14e7ea6328a42e0eb13d585e4c22|AccelOpt]]：LLM agent + beam search + optimization memory + planner/executor/summarizer 三角色，用 $210 的开源模型（Qwen3-Coder-480B + gpt-oss-120b）达到 $5800 Claude Sonnet 4 的 kernel 优化水平。结论是"给 agent 一个 profile-反馈闭环比堆模型大小更划算"。
- [[54229abfcfa5649e7003b83dd4755294|PIKE]]：系统消融 OpenEvolve 各组件，"exploit-heavy mutation-only beam search + 错误修复 agent"胜过复杂的 islands/crossover。PoC 两周可复现，把目标从 kernel 优化换成"因子挖掘脚本/回测参数"即是内部可用的版本。
- [[e2ef524fbf3d9fe611d5a8e90fefdc9c|TritorX]]：FSM 驱动的 agent 循环（Init→Generate→Linter→Compile/Test→Debug），用工具链的结构化错误信息代替硬件专属文档喂 prompt，85% ATen 覆盖率。通用范式：任何"大量样板代码 + 明确测试/编译反馈"的场景（DataLoader、回测策略、特征代码）都能套这个模板。
- [[a3f390d88e4c41f2747bfa2f1b5f87db|LLaMEA]]：LLM + EA 闭环自动合成 GPU auto-tuning 算法。内部 AutoML/HPO 组件的未来形态——让 LLM 每轮生成一个特化搜索算法。
- [[d645920e395fedad7bbbed0eca3fe2e0|HIPPOCAMPUS]] + [[093f65e080a295f8076b1c5722a46aa2|LEANN]]：agent memory / RAG 完全不用 dense embedding + ANN，纯 CPU bitwise 或 on-demand recompute。研究型 agent 需要长期记忆（历史实验、论文、代码片段）时不吃 GPU。

**值得 follow-up 的 research**

1. **把 AccelOpt/PIKE 范式应用到「自动因子挖掘」或「自动回测参数搜索」**：reward 定义清楚（Sharpe、IC、回测 PnL），开源模型 + evolutionary search + 错误修复 agent。专有数据 + MLSys 方法论的结合，对外构成"MLSys on finance"的研究空白。
2. **把 TritorX 的「工具链反馈 = 知识载体」思想做成内部平台能力**：给自研的 feature/backtest DSL 配 linter + executor，让 agent 写策略代码。真正稀缺的不是模型，是高质量 tool feedback。
3. **研究型 agent 的长对话 planning/reflection 压缩**：[[6364d3f0f495b6ab9dcf8d3b5c6e0b01|OSWorld-Human]] 揭示 CUA agent 的 planning+reflection 占 75–94% 延迟，这对研究型 agent 是直接警报。方向：借鉴 [[d645920e395fedad7bbbed0eca3fe2e0|HIPPOCAMPUS]] 的 CPU-side succinct memory 做 agent 记忆管理。

### 三、时序模型（Transformer / Diffusion）训练与推理

MLSys 2026 几乎没有"时序预测"专门论文，但大量 LLM 系统优化可以平移——这里没人做，是公开的研究空白。

**可直接借用/集成（训练侧）**

- [[72b32a1f754ba1c09b3695e0cb6cde7f|FlashAttention-4]]：Blackwell/B200 上 attention 1613 TFLOPS（71% 峰值），CuTe-DSL 把 kernel 编译从 55s 压到 2.5s。长 context 时序 transformer 可直接用。
- [[93db85ed909c13838ff95ccfa94cebd9|DistCA]]：把 Core Attention 剥离为独立 server 池，token 级跨 DP/PP 重组。若时序 foundation model 上 100K+ 长度训练，这是直接需要的。
- [[e2c420d928d4bf8ce0ff2ec19b371514|MTraining]]：Vertical-Slash 动态稀疏 + Balanced Sparse Ring Attention，32K→512K，Dense 最高 6×。长时间窗时序训练直接对应。
- [[d3d9446802a44259755d38e6d163e820|db-SP]]：视频 DiT 的 block-wise sparse attention + SP 两层不平衡分区。时序 diffusion 可直接对应（视频与时序在 token 序列 DiT 结构上同构）。

**可直接借用/集成（推理侧）**

- 实盘延迟敏感场景的 diffusion 加速：
  - [[7cbbc409ec990f19c78c75bd1e06f215|CDLM]]：consistency + distillation + block-causal mask，decode 步数减 3.4–7.9×、延迟 3.6–14.5×。
  - [[14bfa6bb14875e45bba028a21ed38046|SpecDiff-2]] + [[67c6a1e7ce56d3d6fa748ab6d9af3fd7|TiDAR]]：扩散 drafter + AR verifier 混合。
  - [[ec8956637a99787bd197eacd77acce5e|StreamDiffusionV2]]：SLO-aware batching、motion-aware noise、滚动 KV、pipeline 并行。对实时时序 diffusion 推理（逐 tick 预测）直接映射。
- 量化与部署：
  - [[d67d8ab4f4c10bf22aa353e27879133c|CAGE]]：QAT 的 Pareto 优化形式化，低比特预训练理论 O(1/√T) 无量化常数项。上 W4A4 时序 transformer 的新理论基础。
  - [[e369853df766fa44e1ed0ff613f563bd|Kitty]]：2-bit KV cache 而不掉精度（高 magnitude channel 保 INT4）。
  - [[c20ad4d76fe97759aa27a0c99bff6710|IntAttention]]：全整数 attention pipeline，ARM CPU 2.1–3.7×。部署到交易机器若不用 GPU 这是 baseline。

**值得 follow-up 的 research**

1. **时序 Diffusion 的实时推理系统**：把 [[7cbbc409ec990f19c78c75bd1e06f215|CDLM]] + [[ec8956637a99787bd197eacd77acce5e|StreamDiffusionV2]] + [[14bfa6bb14875e45bba028a21ed38046|SpecDiff-2]] 的思路合起来，针对"每 tick 产生预测分布"的场景做。公开 benchmark 几乎没有，自家数据 + 场景即是系统论文的独有资产，可以以"tick-level streaming inference for diffusion-based forecasting with X ms SLO on Y GPU"立论。
2. **KV cache 优化平移到时序 foundation model**：[[76dc611d6ebaafc66cc0879c71b5db5c|FlexiCache]]（head temporal stability）、[[5ef059938ba799aaa845e1c2e8a762bd|MAC-Attention]]（query 时间冗余）、[[d82c8d1619ad8176d665453cfb2e55f0|BLASST]]（online softmax 免费稀疏）都源自 LLM。时序数据的 autocorrelation 结构可能比 LLM 的 query 相似性更强，head 稳定性/block 稀疏/query 复用在时序下很可能比 LLM 更显著——做一个系统化对比即是一篇论文。
3. **[[65b9eea6e1cc6bb9f0cd2a47751a186f|Reparo]] 的"语义级冗余"思路迁移到时序缺失值/异常填补**：把时间序列 tokenize（VQ-VAE 风格），用 masked generation 做 imputation，相比 ARIMA/KNN 是生成式的，相比标准 diffusion 是单步的。baseline 清晰、迁移干净。
4. **异构集群训时序 diffusion foundation model**：[[9a1158154dfa42caddbd0694a4e9bdc8|HexiScale]]（三维非对称并行）+ [[7f39f8317fbdb1988ef4c628eba02591|HetRL]]（异构 RL 调度）+ [[072b030ba126b2f4b2374f342be9ed44|FP8-Flow-MoE]]（FP8 训练）的思路平移到混布集群（A100 + L40S + 消费卡）训时序模型。

### 优先推荐三篇

若时间有限，以下三篇 ROI 最高：

1. [[8613985ec49eb8f757ae6439e879bb2a|OPTIKIT]] —— MLOps 交付流水线最完整的公开模板。
2. [[19ca14e7ea6328a42e0eb13d585e4c22|AccelOpt]] —— 开源模型做 auto research 的最清晰成本/收益证明。
3. [[ec8956637a99787bd197eacd77acce5e|StreamDiffusionV2]] —— 流式 diffusion 推理的系统设计，几乎就是时序预测实盘的路线图。
