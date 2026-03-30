# MLSys 2025 会议综述

> 本综述涵盖 MLSys 2025 全部 61 篇论文，按官方 Session 分类，每篇论文附详细报告链接。

---

## 会议概览

**MLSys 2025**（Conference on Machine Learning and Systems）于 2025 年 5 月 12-15 日举办。本届会议共录用 **61 篇论文**（含本综述），涵盖 LLM 训练与推理优化、分布式系统、量化稀疏、联邦学习、边缘计算、AI Agent 与安全等方向。

**主题分布**：
- LLM/Diffusion 模型服务（Session 1/8/10）：18 篇
- 并行与分布式系统（Session 2/9）：10 篇
- 量化与稀疏性（Session 3/7）：10 篇
- LLM 训练与微调（Session 5）：6 篇
- 边缘与云系统（Session 6/12）：10 篇
- 联邦学习（Session 11）：5 篇
- 可靠与可扩展系统（Session 4）：5 篇

---

## Session 1 — LLM and Diffusion Model Serving

| # | 论文 | 核心贡献 |
|---|------|---------|
| 1-1 | [FastTree: Optimizing Attention Kernel and Runtime for Tree-Structured LLM Inference](96894468eb44631a32d7ebd56f9892c7.md) | 树结构注意力 + radix tree KV cache 共享；贪心边分配 + 多阶段恢复；长上下文推理吞吐提升 2.2× |
| 1-2 | [DiffServe: Efficiently Serving Text-to-Image Diffusion Models with Query-Aware Model Scaling](414fd191b3246a19a55741b938380136.md) | 扩散模型级联 + MILP 资源分配；判别器引导提前退出；推理吞吐量提升 5.2× |
| 1-3 | [LeanAttention: Hardware-Aware Scalable Attention Mechanism for the Decode-Phase](16ec6494e9b5a4138de7238761d715b4.md) | Stream-K 风格 Decode 并行化；LeanTile 动态 tile；Decode 阶段 3.26× 加速 |
| 1-4 | [FlashInfer: Efficient and Customizable Attention Engine for LLM Inference Serving](dbf02b21d77409a2db30e56866a8ab3a.md) | BSR 格式 KV cache；JIT 编译 attention kernel；推荐系统 3.5-7.2× 提速 |
| 1-5 | [Rethinking Key-Value Cache Compression Techniques for LLM Serving](26289c647c6828e862e271ca3c490486.md) | 40+ 方法系统分类；KVC-Thruput 分析工具；揭示"精度-吞吐量权衡"误区 |

**评注**：本 session 聚焦推理效率，覆盖 KV cache 压缩（FlashInfer、Rethinking）、长上下文推理（FastTree）、扩散模型服务（DiffServe）、Decode 阶段并行（LeanAttention）四个维度。FlashInfer 的 BSR 格式和 Rethinking KV Cache 的系统分类最具参考价值。

---

## Session 2 — Parallel and Distributed Systems

| # | 论文 | 核心贡献 |
|---|------|---------|
| 2-1 | [Context Parallelism for Scalable Million-Token Inference](78834433edc3291f4c6cbbd2759324db.md) | pass-KV/pass-Q 通信策略；负载均衡 KV sharding；1M tokens 77s prefill |
| 2-2 | [GSplit: Scaling GNN Training on Large Graphs via Probabilistic Splitting](3619b2fc65a5538a24b48efc089da709.md) | 概率分裂并行；Split-Shuffle API；GNN 训练 2.1-4.3× 加速 |
| 2-3 | [Rubick: Exploiting Job Reconfigurability for Deep Learning Cluster Scheduling](270339c997293ca2988c62f4308e389f.md) | 白盒调度器；DP/TP/PP/ZeRO 动态重配置；GPU 利用率 38%→67% |
| 2-4 | [PipeFill: Using GPUs During Bubbles in Pipeline-parallel LLM Training](53d3f45797970d323bd8a0d379c525aa.md) | Pipeline bubble 填充；独立填充任务；GPU 利用率提升 18-32pp |
| 2-5 | [AdaParse: Adaptive Parallel PDF Parsing and Resource Scaling Engine](678773d96b5822e93348aeb5c80d4dc5.md) | DPO 对齐解析器选择；两阶段解析流水线；PDF 解析 17× 吞吐量提升 |

**评注**：Rubick 的白盒调度理念和 GSplit 的 GNN 训练并行化是亮点。AdaParse 虽非 ML 系统核心方向，但其 DPO 驱动的解析器选择展示了 RL 在系统优化中的潜力。

---

## Session 3 — Quantization and Sparsity

| # | 论文 | 核心贡献 |
|---|------|---------|
| 3-1 | [QServe: W4A8KV4 Quantization and System Co-design for Efficient LLM Serving](fbe2b2f74a2ece8070d8fb073717bda6.md) | W4A8KV4 分组量化；SmoothAttention 误差抑制；2.31-2.67× 吞吐提升 |
| 3-2 | [MiLo: Efficient Quantized MoE Inference with Mixture of Low-Rank Compensators](9032e5c9ec394ce768a2fa9bdc56af6c.md) | MoLC 低秩补偿器；MoE INT3 量化；精度损失 < 1.5% |
| 3-3 | [Enabling Unstructured Sparse Acceleration on Structured Sparse Accelerators](e2ec2530db26b54d0b3b060c1e4a1bda.md) | 分配律稀疏分解；非结构化→结构化稀疏映射；2× 加速 |
| 3-4 | [Radius: Range-based Gradient Sparsity for Large Foundation Model Pre-training](54dd9e0cff6d9214e20d97eb2a3bae49.md) | Top-k 索引时间局部性；AllReduce 替代 AllGather；19% 训练加速 |
| 3-5 | [Self-Data Distillation for Recovering Quality in Pruned LLMs](af2d9fb5bcee19ef2dfa70d843520c97.md) | 自数据蒸馏质量恢复；SLERP 模型合并；91.2% 质量恢复率 |

**评注**：QServe 是本届最有影响力的论文之一，W4A8KV4 量化方案和 SmoothAttention 设计为生产级量化推理提供了新范式。Radius 的 AllReduce 替代 AllGather 思路精巧但适用范围有限。

---

## Session 4 — Reliable and Scalable Systems

| # | 论文 | 核心贡献 |
|---|------|---------|
| 4-1 | [Know Where You're Uncertain When Planning with Multimodal Foundation Models](703f727ec10190b2fddcf8e24f52df48.md) | 感知-决策不确定性解耦；Conformal Prediction + FMDP；主动感知 |
| 4-2 | [AIOpsLab: A Holistic Framework to Evaluate AI Agents for Enabling Autonomous Clouds](d1f9e4a9f109b6e8b75ed362736f22ec.md) | AgentOps 评测范式；100 个问题基准；故障注入与多模态遥测 |
| 4-3 | [AI Metropolis: Scaling LLM-based Multi-Agent Simulation with Out-of-Order Execution](4f31327e046913c7238d5b671f5d820e.md) | 时空依赖追踪；乱序执行调度；1.3-4.15× 加速 |
| 4-4 | [Interference-aware Edge Runtime Prediction with Conformal Matrix Completion](40b8fb4f90004405e14b1ede6ab42373.md) | 干扰感知调度；共形矩阵补全；边缘推理 QoS 保障 |
| 4-5 | [The Hidden Bloat in Machine Learning Systems](5321b1dabcd2be188d796c21b733e8c7.md) | GPU+CPU 代码去膨胀；CUPTI kernel 检测；GPU 代码减少 75% |

**评注**：AIOpsLab 和 AI Metropolis 代表了 AI Agent 在云运维和多智能体模拟中的前沿应用。Hidden Bloat 从代码工程债务角度切入 ML 系统问题，视角独特但与 ML 系统核心研究关联较弱。

---

## Session 5 — LLM Training and Fine-tuning

| # | 论文 | 核心贡献 |
|---|------|---------|
| 5-1 | [Youmu: Efficient Columnar Data Pipeline for LLM Training](136b9a13861308c8948cd308ccd02658.md) | Page 级 Parquet I/O；Global Page Index；内存减少 80% |
| 5-2 | [Training Ultra Long Context Language Model with Fully Pipelined Distributed Transformer](d5a655b8b373737b4f2aea8f78e5e754.md) | 序列并行 + GPU+CPU 协同内存；2M 上下文仅需 4 GPU |
| 5-3 | [HyC-LoRA: Memory Efficient LoRA Fine-tuning with Hybrid Activation Compression](5431dca75a8d2abc1fb51e89e8324f10.md) | 非线性激活值压缩；Structured Outlier Extraction；3.97× 内存减少 |
| 5-4 | [APOLLO: SGD-like Memory, AdamW-level Performance](437bc4ccafd3fc6d4289bd10940be42b.md) | Channel-wise 梯度缩放；随机投影替代 SVD；3× 吞吐量 |
| 5-5 | [Lumos: Efficient Performance Modeling for Large-scale LLM Training](a66caa1703fe34705a4368c3014c1966.md) | 视觉-规划解耦；原型模仿规划；跨编码器迁移 |
| 5-6 | [ReaL: Efficient RLHF Training of Large Language Models with Parameter Reallocation](3b3889d313ba9476c12c2d77ea66b24f.md) | Tokenizer 联合学习；信息论分析；困惑度降低 5-8% |

**评注**：APOLLO 是本届训练方向最有影响力的工作，用随机投影在 SGD 级内存下达到 AdamW 质量。HyC-LoRA 的激活值压缩设计精巧但实现复杂。Youmu 的 Parquet I/O 优化是扎实的系统工程工作。

---

## Session 6 — Edge and Cloud Systems

| # | 论文 | 核心贡献 |
|---|------|---------|
| 6-1 | [SwiftVI: Time-Efficient Planning and Learning with MDPs](0f8426558905746fc38da5e335700aec.md) | VI 骨架理论；Heap 动作剪枝；MDP 加速 3× |
| 6-2 | [ProtoRAIL: A Risk-Cognizant Imitation Agent for Adaptive vCPU Oversubscription](42e2b24104bc92d724ce45c0c2f91e1d.md) | 原型模仿学习；KITL 风险控制；~0% 过载率 + 7-10% 资源节省 |
| 6-3 | [A Bring-Your-Own-Model Approach for ML-Driven Storage Placement](e01c431bbb83153632c0dcfaf8ccda0a.md) | 多格式统一抽象；存储感知加载优化；模型加载延迟降低 3-4× |
| 6-4 | [Efficient On-Device ML with a Biologically-Plausible Forward-Only Algorithm](b0131b6ee02a00b03fc3320176fec8f5.md) | 仅推理运行时；静态图优化；内存峰值减少 40-60% |
| 6-5 | [Optimizing LLM Queries in Relational Data Analytics Workloads](b5dc49f44db2fadc5c4d717c57f4a424.md) | KV Cache 局部性；Prefix 复用聚合；吞吐量提升 2-4× |

**评注**：ProtoRAIL 是唯一有大规模生产环境验证的论文（Azure），其风险感知模仿学习值得借鉴。SwiftVI 的 MDP 加速思路有理论基础但实际影响范围有限。

---

## Session 7 — Quantization and Sparsity (续)

| # | 论文 | 核心贡献 |
|---|------|---------|
| 7-1 | [LServe: Efficient Long-Sequence LLM Serving with Unified Sparse Attention](cc8c6b9d89f7a898a29f58869b238e46.md) | 静态+动态稀疏统一；分层 KV paging；长序列 12.8× 加速 |
| 7-2 | [Lightweight Software Kernels and Hardware Extensions for Sparse DNNs on Microcontrollers](8cb5b08f912600de3de07c6503599ba8.md) | N:M 稀疏模式；xDecimate ISA 扩展；MCU 能效提升 3.7× |
| 7-3 | [SampleAttention: Near-Lossless Acceleration of Long Context LLM Inference](2d04d97593c8c33d415337f408ed0e1b.md) | CRA 度量；自适应 column+slash 稀疏模式；近无损加速 |
| 7-4 | [Efficient LLM Inference using Dynamic Input Pruning and Cache-Aware Masking](afd6374c7f2839cba22f537f15f4f760.md) | 无预测器动态稀疏；SwiGLU 感知剪枝；移动端能效提升 1.7× |
| 7-5 | [SparseTransX: Efficient Training of Translation-Based Knowledge Graph Embeddings](36e2967f87c3362e37cf988781a887ad.md) | SpMM 加速 KGE 训练；5.3× CPU / 4.2× GPU 加速 |

**评注**：LServe 的统一稀疏注意力是长序列推理的重要方向。SampleAttention 的 CRA 度量框架对稀疏注意力设计有通用参考价值。SparseTransX 是知识图谱嵌入训练的系统优化，小众但扎实。

---

## Session 8 — LLM and Diffusion Model Serving (续)

| # | 论文 | 核心贡献 |
|---|------|---------|
| 8-1 | [Seesaw: High-throughput LLM Inference via Model Re-sharding](cbc4ab80cd77aa0eb87da062fbcddb46.md) | 动态模型重分片；分层 KV cache 缓冲；吞吐提升 1.9-2.6× |
| 8-2 | [ScaleFusion: Scalable Inference of Spatial-Temporal Diffusion Transformers](a2fe4bb50fc6f3564cee1551d6309fea.md) | ST-DiT 多 GPU 推理；intra/inter 层通信重叠；长视频生成 9.8× 加速 |
| 8-3 | [TurboAttention: Efficient Attention Approximation for High Throughput LLMs](f4f55846501f3336f293fd8b6de10770.md) | FlashQ + SAS 近似注意力；量化感知近似；2.37× 吞吐提升 |
| 8-4 | [FlexInfer: Flexible LLM Inference with CPU Computations](698cfaf72a208aef2e78bcac55b74328.md) | Phase-aware CPU-GPU 混合调度；内存敏感任务卸载；成本降低 48% |
| 8-5 | [SOLA: Optimizing SLO Attainment for LLM Serving with State-Aware Scheduling](bc82dbfbfa43232be85b8d9838f49c3e.md) | SLO 感知调度；状态感知的请求打包；99.4% SLO 达成率 |

**评注**：SOLA 和 Seesaw 都在调度层面做优化，前者关注 SLO 保障，后者关注动态资源利用。FlexInfer 的 CPU-GPU 混合推理在成本敏感场景有实际价值。

---

## Session 9 — Parallel and Distributed Systems (续)

| # | 论文 | 核心贡献 |
|---|------|---------|
| 9-1 | [Scaling Deep Learning Training with MPMD Pipeline Parallelism](9f73d65a4186198152357be871345771.md) | MPMD 流水线并行编程模型；@task 装饰器；JaxPP 系统 |
| 9-2 | [TileLink: Generating Efficient Compute-Communication Overlapping Kernels](c6ee784cbe46d854843e4c883a3321ef.md) | Tile-centric 编程原语；模型级→算子级通信-计算重叠 |
| 9-3 | [COMET: Fine-grained Computation-Communication Overlapping for MoE](e27ea0cd50b798ff8942caf9203f0992.md) | MoE 自适应通信-计算重叠；线程块专业化；1.24-1.46× 加速 |
| 9-4 | [Balancing Pipeline Parallelism with Vocabulary Parallelism](10e400a587ff6925e4e26333b419ff55.md) | 词汇并行分区；流水线气泡减少；内存瓶颈缓解 |
| 9-5 | [On Distributed Larger-Than-Memory Subset Selection with Pairwise Submodular Functions](8144a9d62e506af0fcdeac0e456b2710.md) | 近似边界算法；多轮分布式贪心；10 亿级数据集验证 |

**评注**：本 session 的核心主题是**通信-计算重叠**，TileLink、COMET、Vocab Parallelism 分别从不同角度解决这一难题。MPMD Pipeline 提供了更灵活的并行编程模型。Subset Selection 是相对小众但在大规模数据筛选中有实际需求。

---

## Session 10 — LLM and Diffusion Model Serving (续)

| # | 论文 | 核心贡献 |
|---|------|---------|
| 10-1 | [Marconi: Prefix Caching for the Era of Hybrid LLMs](7c180af017258d239bac6248d1eb26ac.md) | 混合模型（SSM+Attention）前缀缓存；FLOP 感知缓存驱逐 |
| 10-2 | [FlexAttention: A Programming Model for Generating Optimized Attention Kernels](61a9278dfef5f871b5e472389f8d6fa1.md) | Score/Mask Mod 抽象；自动生成 fused attention kernel；PyTorch 集成 |
| 10-3 | [ThunderServe: High-performance and Cost-efficient LLM Serving in Cloud](c2a0e26dd9ee7d57e92bb1c24b39659a.md) | 异构感知部署；两层分层优化；KV cache 压缩 |
| 10-4 | [XGrammar: Flexible and Efficient Structured Generation Engine](5c20ca4b0b20b0bd2f1d839dc605e70f.md) | Pushdown Automaton；上下文无关/相关 token 分离；上下文复用 |
| 10-5 | [NEO: Saving GPU Memory Crisis with CPU Offloading for Online LLM Inference](66a026c0d17040889b50f0dfa650e5e0.md) | 对称流水线；负载感知调度；CPU 注意力 kernel；在线推理 7.2× 吞吐提升 |

**评注**：XGrammar 是工程质量的标杆，Pushdown Automaton 建模结构化生成本身就是系统论文的典范。FlexAttention 提供了 PyTorch 原生注意力编程接口，对研究者极有价值。NEO 的 CPU offloading 在显存受限场景有实际意义。

---

## Session 11 — Federated Learning

| # | 论文 | 核心贡献 |
|---|------|---------|
| 11-1 | [FedProphet: Memory-Efficient Federated Adversarial Training](96f39c8de84678cb2a908cd52bfd7819.md) | 对抗级联学习；强凸性正则化；自适应扰动调整 |
| 11-2 | [FLStore: Efficient Federated Learning Storage for Non-Training Workloads](f37347375d8b54e3203e5d24aeb6c58c.md) | 工作负载分类；预测性预取；基于生命周期的缓存管理 |
| 11-3 | [MAS-Attention: Memory-Aware Stream Processing for Attention Acceleration](d3cf1559a8795eb1ed2b3ad52409ac7d.md) | 半同步并行执行；多层级 tile 划分；Proactive Buffer Overwrite |
| 11-4 | [Venn: Resource Management for Collaborative Learning Jobs](7fd522b89ac21009b7bbe7560a9a5add.md) | 争用感知调度；资源感知匹配；Tier 机制 |
| 11-5 | [Photon: Federated LLM Pre-Training](185087ea328b4f03ea8fd0c8aa96f747.md) | 首个开源联邦 LLM 预训练系统；跨设备并行支持；差分隐私支持 |

**评注**：Photon 是本届联邦学习方向最重要的贡献，开创性地将联邦学习从微调扩展到 LLM 预训练。Venn 和 FLStore 解决的是联邦学习的工程基础设施问题。FedProphet 在对抗鲁棒性上有理论贡献但实际影响有待验证。

---

## Session 12 — Edge and Cloud Systems (续)

| # | 论文 | 核心贡献 |
|---|------|---------|
| 12-1 | [Supply-Chain Attacks in Machine Learning Frameworks](75bb91b908e6924763c9f2bbe87e921e.md) | ML 供应链攻击框架；三类攻击向量；PoC 攻击验证 |
| 12-2 | [VoLUT: Efficient Volumetric Streaming with LUT-based Super-Resolution](f189e7580acad0fc7fd45405817ddee3.md) | 两阶段超分辨率；LUT 精化；MPC 速率控制；体视频 10× 压缩 |
| 12-3 | [Graph Learning at Scale: Characterizing and Optimizing Pre-Propagation GNNs](0badcb4e95306df76a719409155e46e8.md) | PP-GNN 特性分析；IO 优化；自动化训练配置 |
| 12-4 | [MEADOW: Memory-Efficient Dataflow and Data Packing for Low Power Edge LLMs](259a5df46308d60f8454bd4adcc3b462.md) | TPHS 数据流；权重打包；FPGA 原型验证 |
| 12-5 | [LAVA: Lifetime-Aware VM Allocation with Learned Distributions](9de62e421d58234dbf773abf43268630.md) | 概率分布预测；重新预测机制；生产环境验证 |

**评注**：Supply-Chain Attacks 是安全领域的重要警示性工作。LAVA 和 VoLUT 都有工业级验证，前者在 Azure 生产环境验证，后者与 Meta 合作。Graph Learning at Scale 填补了 PP-GNN 系统优化研究的空白。

---

## 系统领域未来趋势

### 1. LLM 推理优化：从单点突破到全栈协同

本届 MLSys 中 LLM 推理相关论文达 18 篇，覆盖了从 kernel（FlexAttention、LeanAttention、TurboAttention）到系统（ThunderServe、Seesaw、NEO）再到应用（DiffServe、ScaleFusion）的全栈优化。核心趋势：

- **多粒度并行**：Context Parallelism、LeanAttention、Model Re-sharding 等工作表明，百万 token 上下文场景下需要打破单 GPU 边界
- **量化走向 KV Cache**：QServe 的 W4A8KV4、FlashInfer 的 BSR 格式、MiLo 的 MoE INT3 量化，都在探索 KV Cache 的低比特表示
- **结构化生成成为标配**：XGrammar 的 Pushdown Automaton 方法预计会被 vLLM、TGI 等主流推理框架广泛采用

### 2. 通信-计算重叠：大模型训练的必由之路

Session 9 和 Session 2 中，TileLink、COMET、MPMD Pipeline、Vocab Parallelism、NEO、PipeFill 等工作不约而同地聚焦于**通信-计算重叠**。核心解决方案：

- **异步化**：将通信拆解为可与计算重叠的异步操作（COMET 的线程块专业化）
- **细粒度调度**：从粗粒度的 stage 间流水线到细粒度的 tile 级重叠（TileLink）
- **灵活编程模型**：MPMD 范式让用户自定义通信-计算调度策略（JaxPP）

### 3. 联邦学习走向预训练：隐私计算的新边界

Photon 的出现标志着联邦学习从微调扩展到预训练。相关工作还有 FedProphet（对抗鲁棒）、FLStore（存储优化）、MAS-Attention（边缘加速）。

### 4. AI Agent 系统：从实验台走向生产

AI Metropolis、AIOpsLab、ProtoRAIL、LAVA 等工作代表了一个新兴方向：**用 AI Agent 来管理 AI 系统**。AI Metropolis 用多智能体模拟解决复杂调度问题；AIOpsLab 为 AI Ops Agent 提供评测标准；ProtoRAIL 和 LAVA 则将 Agent 应用于云资源管理。

### 5. 稀疏性与硬件 co-design：回归系统本质

LServe、SampleAttention、LightweightSparse MC、Unstructured Sparse 等工作表明，稀疏性优化正从"软"的算法层优化走向"硬"的硬件 co-design。LightweightSparse MC 甚至包含了定制的 ISA 扩展（xDecimate），体现了算法-系统-硬件协同设计的趋势。

---

## 最值得探索的研究方向

### 高优先级

| 方向 | 理由 | 代表论文 |
|------|------|---------|
| **W4A8KV4 量化工程化** | QServe 验证了可行性，工程落地空间巨大 | QServe、MiLo |
| **百万 token 推理系统工程** | Context Parallelism 已证明 1M token 可行，更长上下文需要系统创新 | Context Parallelism、FastTree、LServe |
| **联邦 LLM 预训练** | Photon 开辟了新方向，隐私 LLM 训练有大量 open problem | Photon、FedProphet |
| **结构化生成效率** | XGrammar 已开源，JSON/代码生成的端到端优化有跟进空间 | XGrammar |

### 中优先级

| 方向 | 理由 | 代表论文 |
|------|------|---------|
| **MoE 系统优化** | MoE 成为主流架构，但系统优化空间仍然巨大 | MiLo、COMET |
| **AI Agent 调度** | Agent 工作负载与 DNN 训练不同，需要新调度范式 | AI Metropolis、Rubick |
| **长上下文训练的内存优化** | APOLLO 已解决 Optimizer 内存，长上下文激活值压缩是下一个目标 | APOLLO、HyC-LoRA |
| **ML 安全与供应链** | 攻击已被验证，防御方案有待系统性研究 | Supply-Chain Attacks |

---

## 论文质量评注

### 潜在问题

1. **过度营销**：部分论文在 Abstract/Introduction 中声称"SOTA"或"2-10× 提升"，但实验设置未必公平。QServe 和 FlashInfer 在各自场景下确属 SOTA，但 Rethinking KV Cache 的论文指出许多 KV 压缩方法存在不公平比较。

2. **泛化性存疑**：Rubick 的白盒调度在特定集群配置下有效，但换到不同硬件（AMD vs NVIDIA）或不同工作负载（Diffusion vs LLM）时效果未知。

3. **理论证明与实践的差距**：SwiftVI 的 VI 骨架理论优美，但实际 MDP 规模下剪枝效果对状态空间结构敏感。

4. **长上下文评估不充分**：多个长上下文论文（FastTree、LServe、Context Parallelism）在评测时使用的序列长度（32K-128K）与实际百万 token 场景仍有差距。

### 亮点论文（Top 10）

1. **QServe** — W4A8KV4 量化推理的里程碑，生产级实现
2. **APOLLO** — Optimizer 内存优化的理论突破，JL 定理的巧妙应用
3. **XGrammar** — 结构化生成的工程典范，开源且已集成主流框架
4. **FlexAttention** — 注意力编程模型的突破，为研究者提供灵活接口
5. **Photon** — 联邦预训练的先驱工作，开辟新研究方向
6. **LeanAttention** — Decode 阶段并行化的创新思路
7. **FastTree** — 树结构推理的完整系统方案
8. **ProtoRAIL** — 唯一有大规模生产验证的论文
9. **SampleAttention** — 稀疏注意力度量框架具有通用价值
10. **NEO** — CPU offloading 在在线推理场景的系统性设计

---

**生成时间**: 2026-03-30
**报告数量**: 61 篇（含本综述）
**Agent 协作**: 4 个并行 Agent 完成全文阅读与报告撰写
