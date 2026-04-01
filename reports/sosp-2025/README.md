# ACM Symposium on Operating Systems Principles (SOSP) 2025 论文概览

> 共 66 篇论文 | 生成日期: 2026-04-01

---

## 论文分类索引

### LLM 推理与服务系统（11 篇）

#### [Mercury: Unlocking Multi-GPU Operator Optimization for LLMs via Remote Memory Scheduling](./3731569.3764798.md)
- **作者**：Yue Guan et al.
- **要解决的问题**：多 GPU LLM 算子优化依赖手工调优，现有编译器的 local-memory-centric 模型要求输入数据完全复制到每个 GPU 后才能计算，无法探索异步执行模式
- **核心贡献**：提出 CommIR，将远程 GPU 显存作为 first-class schedulable tier，用 4 个原语统一计算、显存和通信调度，自动发现匹配或超越所有已知手工方案的策略，平均加速 1.56x
- **关键发现/观点**：远程 GPU 显存可以像本地 HBM 一样作为可调度的存储层；在此抽象下，设备间通信变成对更大聚合显存池中共享数据的访问，不同设备可以在错开的时间步访问共享数据，这一 shifted asynchronous schedule 能涵盖所有已知手工优化模式

#### [HedraRAG: Co-Optimizing Generation and Retrieval for Heterogeneous RAG Workflows](./3731569.3764806.md)
- **作者**：Zhengding Hu et al.
- **要解决的问题**：复杂 RAG workflow（多跳、迭代检索-生成）中 CPU-GPU pipeline stall 和冗余计算严重，现有系统将 LLM 生成和向量检索作为独立模块处理
- **核心贡献**：提出 RAGraph 图抽象统一异构 RAG 工作流，实现细粒度子阶段 pipeline、相似性感知的投机执行和部分 GPU 索引缓存，吞吐提升 1.5-5x
- **关键发现/观点**：异构 RAG 工作流存在三种可利用的规律性：生成和检索阶段可分解为细粒度子阶段进行并行 pipeline；同一请求内相邻阶段具有强语义相似性，可进行高精度投机执行；跨请求的向量索引访问遵循稳定的热点偏斜模式

#### [Characterizing Mobile SoC for Accelerating Heterogeneous LLM Inference (HeteroInfer)](./3731569.3764808.md)
- **作者**：Le Chen et al.
- **要解决的问题**：移动端 LLM 推理引擎只使用单一加速器（GPU 或 NPU），未能利用移动 SoC 的异构计算潜力
- **核心贡献**：首个同时利用移动端 GPU 和 NPU 的 LLM 推理引擎，通过层级和张量级异构执行实现 1.34-6.02x 端到端加速
- **关键发现/观点**：移动 NPU 性能对张量特征极度敏感——当张量特性与脉动阵列匹配时 NPU 表现卓越，否则不如 GPU；而 SoC 的统一内存架构允许 GPU 和 NPU 共同饱和内存带宽（~43 到 ~60 GB/s），使异构并行执行对 compute-bound 的 prefill 和 memory-bound 的 decode 都有收益

#### [DiffKV: Differentiated Memory Management for Large Language Models with Parallel KV Compaction](./3731569.3764810.md)
- **作者**：Yanqi Zhang et al.
- **要解决的问题**：现有 KV cache 压缩方法对 key 和 value 统一处理、对所有 token 使用相同精度、使用静态 per-head 预算，未能利用 KV cache 的内在异构性
- **核心贡献**：三层差异化压缩框架（key/value 精度、分层 token 重要性、per-head 动态稀疏性）+ GPU 端并行 KV compaction，实现 2.7-5.7x 压缩和 1.9-5.4x 吞吐提升
- **关键发现/观点**：KV cache 存在三层异构性：(1) key 对注意力输出的影响远大于 value（注意力分数跨 7 个数量级 vs value norm 跨 2 个）；(2) token 重要性高度不均匀，可分为高精度、低精度和可剪枝三个层级；(3) 注意力稀疏性在不同 head 和请求间动态变化

#### [Pie: A Programmable Serving System for Emerging LLM Applications](./3731569.3764814.md)
- **作者**：In Gim et al.
- **要解决的问题**：当前 LLM 服务系统（vLLM, SGLang）建立在单体 prefill-decode 循环上，无法支持 Tree-of-Thought、Agent workflow 等需要细粒度 KV cache 和解码控制的新兴应用
- **核心贡献**：将单体 LLM 服务循环分解为细粒度 API（embed, forward, sample），通过 WebAssembly 运行用户自定义 inferlet 程序，实现可编程 KV cache 管理和自定义解码
- **关键发现/观点**：现有系统不灵活的根本原因是应用控制逻辑与核心推理引擎的紧耦合，而非本质要求；应用特定的控制逻辑可以高效地与核心引擎解耦并在外部执行，只要暴露正确的细粒度接口

#### [Aegaeon: Effective GPU Pooling for Concurrent LLM Serving on the Market](./3731569.3764815.md)
- **作者**：Yuxing Xiang et al.
- **要解决的问题**：云端模型市场需同时服务数千模型，但 request 级自动扩缩容无法有效池化 GPU——LLM 请求执行时间长导致过多模型同时"活跃"，阻止资源回收
- **核心贡献**：token 级抢占式自动扩缩容 + prefill/decode 分离 + 97% 扩缩容延迟降低，在阿里云部署节省 82% GPU（1192→213）
- **关键发现/观点**：request 级自动扩缩容的池化效率受限于并发活跃模型数（E[m] = M*(1-e^{-λT})），由于 LLM 请求执行时间长，即使低到达率下活跃模型数仍然很高；token 粒度的抢占式调度可以在请求执行中途回收 GPU，将所需 GPU 预留量降至活跃模型数以下

#### [Jenga: Effective Memory Management for Serving LLM with Heterogeneity](./3731569.3764823.md)
- **作者**：Chen Zhang et al.
- **要解决的问题**：现代 LLM 架构异构化（混合 full attention、sliding window、Mamba 层），打破 PagedAttention 的同质性假设，导致严重内存碎片（最高 79.6% 浪费）
- **核心贡献**：引入 layer property 抽象和两级 LCM 内存分配器 + 可定制前缀缓存，内存浪费从 38.2% 降至 0.04%，吞吐提升 1.46-2.16x
- **关键发现/观点**：在异构 LLM 中，每层的内存行为（分配大小和页访问模式）可以从模型架构预先确定——embedding 大小是编译期常量，attention 机制有固定的 token 依赖模式——因此内存管理可以建模为 layer property 并逐层优化

#### [IC-Cache: Efficient Large Language Model Serving via In-context Caching](./3731569.3764829.md)
- **作者**：Yifan Yu et al.
- **要解决的问题**：超 70% 的 LLM 请求与历史请求高度语义相似，但直接复用缓存回复（语义缓存）因细微上下文差异导致质量从 50% 暴跌至 18% 胜率
- **核心贡献**：将历史请求-回复对作为 in-context example 注入小模型 prompt，实现 1.4-5.9x 吞吐提升和 28-71% 延迟降低，同时保持与大模型相当的回复质量
- **关键发现/观点**：历史请求-回复对不应作为可直接复用的缓存项，而应作为 in-context example 注入 prompt——利用 in-context learning 让小模型模仿大模型的推理轨迹，实现无需重训练的"实时能力增强"

#### [PrefillOnly: An Inference Engine for Prefill-only Workloads](./3731569.3764834.md)
- **作者**：Kuntai Du et al.
- **要解决的问题**：现有 LLM 推理引擎为所有层存储 KV cache，即使工作负载只需单个输出 token（推荐、信用评分、embedding），浪费 GPU 显存并限制最大输入长度和吞吐
- **核心贡献**：首个专为 prefill-only 工作负载设计的推理引擎，使用混合 prefilling 降低 57% GPU 显存，MIL 提升最高 7.9x，QPS 提升最高 4x
- **关键发现/观点**：Prefill-only 请求只生成一个输出 token，因此 (1) 推理过程产生的 KV cache 永远不会被 decode 复用，可立即丢弃，大幅减少活跃 GPU 显存；(2) 固定的输出长度使每个请求的完成时间精确可预测，可应用经典的 JCT-aware 调度

#### [KTransformers: Unleashing the Full Potential of CPU/GPU Hybrid Inference for MoE Models](./3731569.3764843.md)
- **作者**：Hongtao Chen et al.
- **要解决的问题**：CPU/GPU 混合推理大型 MoE 模型（如 671B DeepSeek-V3）吞吐极低，因为 CPU 未充分利用 AMX 指令、CPU-GPU 同步开销主导短 decode 步、CPU/GPU 执行因严格层依赖缺乏并行性
- **核心贡献**：通过 AMX 专用 kernel、单 CUDA Graph decode 调度、NUMA 感知张量并行和 Expert Deferral 机制实现 671B MoE 模型的实用本地部署，prefill 加速 4.62-19.74x，decode 加速 1.66-4.90x
- **关键发现/观点**：带残差连接的现代 Transformer 模型对延迟的中间计算具有固有鲁棒性——路由专家输出可以延迟到下一层再合并，而不显著影响模型精度；这打破了 MoE 和 attention 层之间的严格顺序依赖，使 CPU-GPU 并行执行成为可能

#### [METIS: Fast Quality-Aware RAG Systems with Configuration Adaptation](./3731569.3764855.md)
- **作者**：Siddhant Ray et al.
- **要解决的问题**：RAG 系统在多个配置旋钮（检索块数、合成方法、摘要长度）间存在质量-延迟权衡，静态配置无法适应查询复杂度的多样性
- **核心贡献**：两层架构——LLM profiler 先将配置空间剪枝 50-100x 保证质量，再通过 GPU 显存感知的 best-fit 调度选最优配置，延迟降低 1.64-2.54x，吞吐提升 1.8-4.5x
- **关键发现/观点**：RAG 查询的质量-延迟权衡空间可松耦合为两层——LLM profiler 能基于查询特征将配置空间缩小到一个"高质量"子集（50-100x 缩减），子集内质量差异足够小，调度器可以纯粹聚焦于延迟优化

---

### 大规模模型训练（5 篇）

#### [Robust LLM Training Infrastructure at ByteDance](./3731569.3764838.md)
- **作者**：Borui Wan et al.
- **要解决的问题**：万卡级 LLM 训练频繁遭遇硬件和软件故障（显式错误如 CUDA crash、隐式如 hang 和 silent data corruption），现有恢复机制太慢，数千 GPU 在诊断期间闲置
- **核心贡献**：ByteRobust 自动容错框架，通过分层检测、快速粗粒度机器隔离、热备节点、热代码更新和高频异步 checkpoint 达到 97% 有效训练时间率
- **关键发现/观点**：大规模场景下精确诊断故障根因代价过高（数千 GPU 闲置），快速隔离可疑机器（即使过度驱逐部分健康机器）的整体效率收益远大于 over-eviction 的成本；此外，频繁的故障停机时间可被复用为非关键代码更新的窗口

#### [Sailor: Automating Distributed Training over Dynamic, Heterogeneous, and Geo-distributed Clusters](./3731569.3764839.md)
- **作者**：Foteini Strati et al.
- **要解决的问题**：主流分布式训练框架假设同构 GPU 集群和均匀带宽，无法高效利用跨可用区和地理区域的异构多代 GPU 资源
- **核心贡献**：Sailor 联合优化资源分配和 3D 并行策略，使用动态规划 + 领域启发式剪枝，结合高精度模拟器（4.5% 误差），在同构/异构/地理分布场景下实现 1.15-5.9x 吞吐提升
- **关键发现/观点**：在异构集群中，资源分配和并行化策略必须联合优化——固定一个搜索另一个会错过全局最优；通过将 pipeline stage 资源分配分解为可复用子问题，动态规划加领域启发式剪枝可在数秒内找到近最优配置

#### [Mycroft: Tracing Dependencies in Collective Communication](./3731569.3764848.md)
- **作者**：Yangtao Deng et al.
- **要解决的问题**：集合通信库（如 NCCL）在 LLM 训练中是不透明的黑盒——当集合操作 hang 或变慢时，运维人员无法观察内部状态定位根因，且异常在 GPU 间快速传播
- **核心贡献**：Mycroft 轻量级追踪系统，在 NCCL 关键路径插桩（~1100 LoC，<1% 开销，46.8KB/iter/机器），暴露 flow 级和 chunk 级可观测性，在字节跳动生产环境中实现 100% 故障检测率
- **关键发现/观点**：集合通信操作有细粒度的内部控制流和数据依赖，只需在 CCL 关键路径点记录少量运行时状态即可重建全局状态机定位根因；由于异常在毫秒内传遍集群，仅采样少数 rank 即可提供完整检测覆盖

#### [DCP: Addressing Input Dynamism In Long-Context Training via Dynamic Context Parallelism](./3731569.3764849.md)
- **作者**：Chenyu Jiang et al.
- **要解决的问题**：现有 Context Parallelism 方法使用静态并行配置，无法适应训练数据中序列长度的巨大方差和多样的 attention mask 模式，导致 27-45% 通信冗余和严重负载不均衡
- **核心贡献**：DCP 将 attention 计算分解为细粒度数据/计算块，建模为超图划分问题，每个 batch 自适应生成并行配置以最小化跨设备通信
- **关键发现/观点**：Attention 计算可分解为细粒度的数据块和计算块，灵活映射到不同设备；将块到设备的分配建模为超图划分问题，可在满足内存和负载均衡约束的同时最小化通信

#### [TrainVerify: Equivalence-Based Verification for Distributed LLM Training](./3731569.3764850.md)
- **作者**：Yunchi Lu et al.
- **要解决的问题**：分布式 LLM 训练易出现静默的并行化 bug（错误梯度同步、张量分区错误、通信原语误用），浪费数百万美元 GPU 时间，传统差分测试无法区分数值噪声和真实错误
- **核心贡献**：首个分布式训练执行计划形式化正确性验证系统，使用符号 dataflow graph、分阶段验证和 shape reduction，可扩展至 671B 参数模型（DeepSeek-V3）跨 8192 GPU
- **关键发现/观点**：分布式训练的正确性编码在执行计划（训练迭代的 dataflow graph 表示）中；通过证明"并行化等价性"——并行化的 DFG 对所有输入产生与逻辑模型 DFG 等价的输出——可将验证聚焦于计划而非整个运行时栈

---

### 机器学习系统与编译器（3 篇）

#### [LithOS: An Operating System for Efficient Machine Learning on GPUs](./3731569.3764818.md)
- **作者**：Patrick H. Coppock et al.
- **要解决的问题**：数据中心 GPU 利用率极低（10-52%），现有 GPU 共享方案要么不透明（需修改 ML 框架）、要么粒度太粗（MIG/MPS）、要么导致队头阻塞
- **核心贡献**：首个 GPU OS 级多租户管理系统，提供 TPC 粒度空间调度、kernel 原子化、动态硬件 right-sizing 和透明 DVFS，完全透明于 ML 栈
- **关键发现/观点**：不同 GPU kernel 的并行扩展行为差异巨大——有的在少量 TPC 就饱和，有的需要更多——对频率的敏感度也不同（compute-bound vs memory-bound）；因此 TPC 粒度的 per-kernel 动态资源分配和功率管理可以大幅提升利用率和能效

#### [Tempo: Compiled Dynamic Deep Learning with Symbolic Dependence Graphs](./3731569.3764840.md)
- **作者**：Pedro F. Silvestre et al.
- **要解决的问题**：动态 DL 算法（LLM 推理、RL 训练）涉及跨时间步的张量时序依赖，eager 系统无法优化，graph-based 系统无法表达动态 shape，迫使用户使用低效变通方案
- **核心贡献**：引入带显式时间维度的 recurrent tensor 和符号依赖图（SDG），支持整程序编译优化（lifting、向量化、tiling、fusion）和多面体调度，LLM decode 加速最高 7x，RL 训练加速 54x
- **关键发现/观点**：动态 DL 算法的张量有隐式时间维度；通过使其显式化，动态依赖变成时间维度上的常规张量索引操作，动态结构可以用符号表达式简洁描述，从而启用标准编译器优化

#### [SAND: A New Programming Abstraction for Video-based Deep Learning](./3731569.3764847.md)
- **作者**：Juncheol Ye et al.
- **要解决的问题**：视频 DL 训练被 CPU 端预处理瓶颈主导（解码、采样、增强耗时是 GPU 训练的 2.2-6.5x），跨 epoch 和 job 的冗余解码进一步浪费资源
- **核心贡献**：SAND 基于 view 的编程抽象，将视频预处理建模为通过 POSIX 文件系统接口暴露的依赖图，支持跨 epoch/job 中间对象复用，训练加速 1.4-10.2x
- **关键发现/观点**：视频 DL 预处理管道可建模为存储级抽象——将训练数据对象（编码视频、解码帧、增强帧、batch）作为 first-class 文件系统实体；这给系统提供全局视图来识别跨任务和 epoch 的冗余操作并通过智能缓存消除

---

### 操作系统内核与内存管理（9 篇）

#### [Rearchitecting the Thread Model of In-Memory Key-Value Stores with uTPS](./3731569.3764794.md)
- **作者**：Youmin Chen et al.
- **要解决的问题**：高速内存 KV 存储的 Run-to-Completion 线程模型导致严重 cache thrashing 和倾斜负载下的竞争放大，限制 >10M ops/s 的吞吐
- **核心贡献**：uTPS Thread-Per-Stage 架构，基于 cache 驻留特性将请求处理分为 cache-resident 层和 memory-resident 层，配合线程分配和 LLC way 分区自动调优
- **关键发现/观点**：KV 请求处理阶段有根本不同的 cache 驻留特性和多核可扩展性——网络缓冲区和热数据可完全驻留 CPU cache，而索引遍历和冷数据访问不可避免造成 cache miss；只有更新阶段受竞争影响。将这些分到独立线程池并分配专用硬件资源可实现独立优化

#### [How to Copy Memory? Coordinated Asynchronous Copy as a First-Class OS Service](./3731569.3764800.md)
- **作者**：Jingkai He et al.
- **要解决的问题**：内存拷贝消耗 Google 数据中心 4-5% CPU 周期（I/O 密集型应用高达 66.2%）；Linux 内核不能用 SIMD 拷贝，用户空间不能用 DMA，同步 memcpy 阻塞计算
- **核心贡献**：Copier 将内存拷贝提升为 first-class OS 服务，使用异步队列抽象、AVX+DMA 混合调度和分层拷贝吸收，Redis 加速 1.8x，已部署于华为 HarmonyOS 5.0
- **关键发现/观点**：拷贝密集型应用中普遍存在"Copy-Use 窗口"——数据被拷贝和首次使用之间的时间间隔（通常是拷贝时长的 2-10x），因为程序批量拷贝数据但增量消费；这个窗口可被利用来通过异步执行将拷贝移出关键路径

#### [Scalable Address Spaces using Concurrent Interval Skiplist](./3731569.3764807.md)
- **作者**：Tae Woo Kim et al.
- **要解决的问题**：Linux mmap_lock 序列化所有地址空间分配和修改操作，在多核系统上造成高达 90% 执行时间浪费在锁竞争
- **核心贡献**：引入并发区间跳表数据结构统一区间映射和细粒度锁定，实现真正并行的 mmap/munmap/mprotect，在 VM 密集型应用上加速 1.27-4.53x
- **关键发现/观点**：地址空间操作的锁定区域是动态的（依赖当前映射状态），传统"先遍历再加锁"方法存在根本性竞态条件；将遍历和锁定统一到同一数据结构操作中可消除此竞态，实现安全的并发区间更新

#### [uFork: Supporting POSIX fork Within a Single-Address-Space OS](./3731569.3764809.md)
- **作者**：John Alistair Kressel et al.
- **要解决的问题**：单地址空间 OS 无法支持 POSIX fork（fork 需创建新地址空间），阻碍运行依赖 fork 的广泛多进程应用（Redis、Nginx、OpenSSH）
- **核心贡献**：利用 CHERI 硬件标记内存可靠识别和重定位 fork 子进程中的所有指针，引入 Copy-on-Pointer-Access 优化，fork 速度提升 3.7x，每进程内存降低 2.2x
- **关键发现/观点**：CHERI 的硬件有效性标签使运行时能可靠识别 fork 子进程内存中的所有绝对内存引用进行重定位，CHERI capability 提供轻量级地址空间内隔离——共同使完整 POSIX fork 语义在单地址空间内可实现

#### [cache_ext: Customizing the Page Cache with eBPF](./3731569.3764820.md)
- **作者**：Tal Zussman et al.
- **要解决的问题**：Linux page cache 使用刚性 LRU 近似，对多样化工作负载表现不佳，实现自定义驱逐策略需要深厚内核专业知识且上游合入极难
- **核心贡献**：eBPF 框架允许应用用数百行 eBPF 代码实现自定义 page cache 驱逐策略（LFU、LHD、S3-FIFO、MGLRU 等），支持 per-cgroup 隔离，框架开销 <2%
- **关键发现/观点**：从经典 LRU/MRU/LFU 到前沿 LHD/S3-FIFO/ARC/MGLRU，绝大多数缓存驱逐算法可以用单一统一抽象精确或近似实现：一组可变大小链表加操作这些链表的策略函数

#### [CortenMM: Efficient Memory Management with Strong Correctness Guarantees](./3731569.3764836.md)
- **作者**：Junyang Zhang et al.
- **要解决的问题**：OS 内存管理的双层抽象（VMA 树 + 页表）需要复杂的细粒度并发控制，在多核系统上造成严重扩展瓶颈，Linux 两年内因 per-VMA 锁产生 10 个 CVE
- **核心贡献**：消除 VMA 树的单层内存管理设计，直接操作页表通过事务接口，在 384 核上实现最高 26x 加速，并用 Verus/Rust 形式化验证锁协议正确性
- **关键发现/观点**：OS 内存管理中的软件层抽象（VMA 树）对现代 ISA 不再必要——当今主流架构（x86、ARM、RISC-V）已收敛到多级基数树页表，细微硬件差异可通过语言特性（C 宏或 Rust trait）而非额外软件抽象层来抽象

#### [Scalable Far Memory: Balancing Faults and Evictions](./3731569.3764842.md)
- **作者**：Yueyang Pan et al.
- **要解决的问题**：现有基于页的远端内存系统在高线程数下因 TLB shootdown 风暴、全局 LRU 竞争和内存分配器瓶颈而性能严重退化——48 线程时仅 10% 内存卸载就损失 50-75% 吞吐
- **核心贡献**：Mage 通过 always-asynchronous 解耦 fault-in 和 eviction 路径、跨批流水线驱逐执行和分区数据结构避免协调，达到 181 Gbps 吞吐（RDMA 线速的 94%），p99 延迟降低 94.5%
- **关键发现/观点**：基于页的远端内存系统中，fault-in 路径（需最小延迟）和 eviction 路径（需最大吞吐）有根本不同的优化目标，但现有系统通过共享数据结构和混合调度将它们耦合在一起；完全解耦并独立优化每条路径是可扩展远端内存的关键

#### [FlexGuard: Fast Mutual Exclusion Independent of Subscription](./3731569.3764852.md)
- **作者**：Victor Laforet et al.
- **要解决的问题**：自旋锁在过度订阅下性能灾难性崩溃（延迟比阻塞锁差 10000x），所有现有 spin-then-park 混合方法依赖启发式无法精确检测临界区抢占
- **核心贡献**：FlexGuard 使用 eBPF 精确检测临界区抢占（通过 sched_switch tracepoint 检查），确定性地在忙等和阻塞模式间切换，完全消除启发式调参
- **关键发现/观点**：通过 eBPF hook 内核 sched_switch tracepoint 并检查被抢占线程的指令地址、寄存器值和 per-thread 临界区计数器，可以确定性地回答一个线程是否在持有锁时被抢占——将之前的启发式猜测问题转化为精确可回答的问题

#### [Proto: A Guided Journey through Modern OS Construction](./3731569.3764811.md)
- **作者**：Wonkyo Choe et al.
- **要解决的问题**：OS 课程越来越不受欢迎且缺乏现实感，现有教学 OS 是"无头"系统仅限 shell 程序，缺少能激发学生动力的真实应用
- **核心贡献**：面向 Raspberry Pi 3 的应用驱动教学 OS，从裸机 I/O 增量构建到可运行 DOOM、视频播放和 NES 游戏的桌面系统，内核核心 8K SLoC
- **关键发现/观点**：如果"能运行什么应用"驱动 OS 构建而非"教什么概念"，每个引入的 OS 机制都有清晰的、学生可见的目的——应用本身成为学习动机和进度反馈

---

### 形式化验证与程序分析（7 篇）

#### [Prove It to the Kernel: Precise Extension Analysis via Proof-Guided Abstraction Refinement (BCF)](./3731569.3764796.md)
- **作者**：Hao Sun et al.
- **要解决的问题**：Linux eBPF 验证器的轻量抽象域（区间、三态）通过过度近似快速丢失精度，错误拒绝许多安全的扩展程序，而更精确的域在内核空间计算不可行
- **核心贡献**：BCF 将复杂精度推理卸载到用户空间 SMT 求解器生成形式化证明，内核仅执行线性时间证明检查——接受 78.7% 的 512 个被错误拒绝的真实 eBPF 程序
- **关键发现/观点**：生成精确证明是计算密集的（NP-complete），但验证已有证明的正确性可在线性时间完成；这种不对称性允许将昂贵的精度推理卸载到用户空间，同时在内核中仅保留高效的证明检查

#### [eBPF Misbehavior Detection: Fuzzing with a Specification-Based Oracle (Veritas)](./3731569.3764797.md)
- **作者**：Tao Lyu et al.
- **要解决的问题**：现有 eBPF fuzzer 依赖间接 bug oracle（KASAN、运行时状态检查），只能检测部分实现 bug，完全遗漏安全程序的错误拒绝和信息泄露等语义错误
- **核心贡献**：将 eBPF 指令语义和安全属性编码为 Dafny 规范，使用 SMT 求解器作为精确 oracle 与验证器交叉检查，发现 15 个新 bug 包括提权和 KASLR 绕过漏洞
- **关键发现/观点**：eBPF 程序安全性可精确归约为每条指令的前/后条件约束并通过 SMT 求解自动推理，构建无近似 oracle 与验证器结果交叉比较可暴露所有类别 bug

#### [Ghost in the Android Shell: Pragmatic Test-oracle Specification of a Production Hypervisor](./3731569.3764817.md)
- **作者**：Kayvan Memarian et al.
- **要解决的问题**：生产级 hypervisor 的完整形式化验证面临工程壁垒（专用工具、受限语言、高维护成本），无证明和完整证明之间缺少实用的中间方法
- **核心贡献**：证明完整功能正确性规范可用实现语言（C）编写为可执行测试 oracle，应用于 Google pKVM（~11K LoC），用 ~14K LoC 规范发现 5 个真实 bug
- **关键发现/观点**：完整功能正确性规范可以用实现语言本身（C）编写为嵌入生产代码的可执行测试 oracle——不需要专用的形式化工具或语言；尽管 C 表面上不适合做规范语言，"morally pure functions"编程风格可实现清晰可读的规范代码

#### [Atmosphere: Practical Verified Kernels with Rust and Verus](./3731569.3764821.md)
- **作者**：Xiangdong Chen et al.
- **要解决的问题**：OS 内核形式化验证成本过高（seL4：20 人年，20:1 证明代码比），SMT 求解器无法处理递归数据结构上的归纳证明，指针密集代码与 Rust 线性所有权模型冲突
- **核心贡献**：Atmosphere 用 Rust+Verus 构建的形式化验证微内核，证明代码比 3.32:1（vs seL4 的 20:1），完整验证 <20 秒，性能与 seL4 相当
- **关键发现/观点**：将递归数据结构的 tracked permission 从层次化父子嵌套展平为全局 flat map，可将递归规范（需归纳证明）转化为非递归全称量化，从根本上降低 SMT 求解难度同时保持指针密集设计的性能

#### [AutoMan: Facilitating Verified Distributed Systems Development](./3731569.3764822.md)
- **作者**：Zihao Zhang et al.
- **要解决的问题**：分布式系统形式化验证需要大量专家工作（如 IronFleet 的 ~8100 行 Multi-Paxos 实现），自动编译又牺牲正确性保证，低开发成本和形式正确性难以兼得
- **核心贡献**：AutoMan 结合从 TLA 风格 Dafny 规范的自动代码生成（减少 70-97% 手工工作量）和性能关键路径的选择性手工优化，保持端到端形式正确性
- **关键发现/观点**：TLA 状态机 refinement 有支持自动化的天然结构：每个 action predicate 独立映射到实现函数，将实现和验证分解为独立单元，其 refinement 证明义务通常足够简单可由 SMT 求解器自动处理；此外分布式系统性能通常由小部分组件主导（数据复制路径），选择性优化关键部分即可获得大部分性能收益

#### [TickTock: Verified Isolation in a Production Embedded OS](./3731569.3764856.md)
- **作者**：Vivien Rindisbacher et al.
- **要解决的问题**：Tock 嵌入式 OS（用于 Google Security Chip、Microsoft Pluton 2）依赖 MPU 进行进程隔离，但其单体 MPU 抽象将内核内存布局逻辑与硬件约束纠缠，导致复杂易错代码和多个未被发现的隔离破坏 bug
- **核心贡献**：将 Tock 的 MPU 抽象从单体重构为分层（TickTock），使用 Flux 精化类型在编译时形式化验证进程隔离，发现 6 个之前未知的隔离破坏 bug
- **关键发现/观点**：Tock 的单体 MPU 抽象将内核进程内存管理需求与底层 MPU 硬件约束纠缠在一起；将这些解耦为独立层（"硬件区域创建/配置" vs "进程内存逻辑布局"）同时消除了纠缠和内核视图与硬件状态之间的分歧

#### [KNighter: Transforming Static Analysis with LLM-Synthesized Checkers](./3731569.3764827.md)
- **作者**：Chenyuan Yang et al.
- **要解决的问题**：传统 OS 内核静态分析 checker 需手工编写，覆盖有限 bug 模式；直接用 LLM 扫描大型代码库成本过高且易幻觉
- **核心贡献**：多阶段流水线让 LLM 从历史补丁中学习 bug 模式并自动合成 Clang Static Analyzer checker，发现 92 个新 Linux 内核 bug（30 个 CVE）
- **关键发现/观点**：LLM 不应直接扫描代码找 bug，而应从历史 bug-fix 补丁中学习 bug 模式并合成可复用的静态分析 checker——结合 LLM 的模式学习能力和传统静态分析的可扩展性（checker 在 CPU 上运行，无需重复 LLM 调用）

---

### 存储系统（4 篇）

#### [Sleeping with One Eye Open: Fast, Sustainable Storage with Sandman](./3731569.3764804.md)
- **作者**：Yanbo Zhou et al.
- **要解决的问题**：现代 NVMe SSD 存储栈使用 busy-polling（SPDK）导致 CPU 100% 利用率和峰值功耗，现有节能替代方案都牺牲延迟或无法响应微秒级 I/O 突发
- **核心贡献**：Sandman 使用用户空间 monitorx/mwaitx 指令实现 3us 唤醒延迟的浅睡眠，结合双粒度调度和兄弟核配对睡眠，在保持 SPDK 性能的同时降低 39% 功耗和 33% 能耗
- **关键发现/观点**：现代处理器提供无特权用户空间 wait 指令（monitorx/mwaitx），利用 cache 一致性将核心置入浅睡眠（C-1 状态）并在目标内存地址写入时以仅 3us 退出延迟自动唤醒——无需系统调用或中断

#### [Aeolia: A Fast and Secure Userspace Interrupt-Based Storage Stack](./3731569.3764816.md)
- **作者**：Chuandong Li et al.
- **要解决的问题**：现有存储栈设计耦合了用户/内核空间与轮询/中断范式，"用户空间 + 中断"象限未被探索；轮询式用户空间栈（SPDK）无法在不可信任务间安全共享资源
- **核心贡献**：Aeolia 结合硬件用户中断、MPK 进程内可信实体隔离和 sched_ext 协调调度，实现接近 SPDK 的 I/O 性能且不牺牲资源共享和安全性
- **关键发现/观点**：与传统认知相反，轮询与中断的性能差距很小——之前归因于中断的大部分开销实际来自次优的内核线程调度策略（eager sleep 成本 1.8us vs 中断机制 0.6us）；使用 active-checking 调度策略，中断可以匹配轮询性能

#### [Managing Scalable Direct Storage Accesses for GPUs with GoFS](./3731569.3764857.md)
- **作者**：Shaobo Li et al.
- **要解决的问题**：现有 GPU Direct Storage 方案仍依赖主机 CPU 处理文件系统操作（元数据管理、块分配、路径解析），使主机 CPU 成为扩展瓶颈
- **核心贡献**：GoFS 是首个完全在 GPU 上运行的文件系统，卸载元数据管理和数据 I/O，使用 GPU 友好数据结构，实现近 SSD 峰值吞吐且零主机 CPU 核心消耗
- **关键发现/观点**：GPU 的大规模并行性（数千 CUDA 核心、数百 SM）不仅可加速应用计算，还可加速文件系统元数据管理和数据 I/O——前提是文件系统的核心数据结构以利用 GPU bulk-synchronous 并行计算范式的"GPU 友好"形式重新设计

#### [Analyzing and Enhancing ArckFS: An Anecdotal Example of Benefits of Artifact Evaluation](./3731569.3768291.md)
- **作者**：Jonguk Jeon et al.
- **要解决的问题**：ArckFS（SOSP 2023）的 Trio 架构在 inode 粒度共享和延迟验证设计中存在未文档化的多 inode 操作规则和 6 个实现 bug
- **核心贡献**：通过仔细的 artifact 评审发现 6 个 bug 并开发 ArckFS+ 修复所有问题，保持 ~97% 原始性能，展示 artifact evaluation 的具体价值
- **关键发现/观点**：Trio 的 inode 粒度共享和延迟验证设计对单 inode 操作是正确且高效的，但多 inode 操作（如跨目录 rename）需要原论文未阐述的额外排序和验证规则；这些缺失规则和相关实现 bug 是可修复的工程问题而非根本性架构缺陷

---

### 虚拟化与云基础设施（8 篇）

#### [Device-Assisted Live Migration of RDMA Devices](./3731569.3764795.md)
- **作者**：Artem Y. Polyakov et al.
- **要解决的问题**：RDMA 设备的 PCIe passthrough 打破 VM 热迁移，因为设备状态对 hypervisor 不可见，RDMA 命名空间无法在目标端重建，且跨设备 P2P（GPUDirect）一致性从未被解决
- **核心贡献**：12 条 Device Assist 原则实现 RDMA 设备透明热迁移——保留命名空间、包级静默代替排空、黑盒状态蒸馏、多设备 PCIe P2P 一致性的两阶段 suspend/resume 协议，已合入 Linux 6.7 和 QEMU 8.1
- **关键发现/观点**：RDMA 设备内部状态虽然复杂，但可以在设备层面作为不透明黑盒提取和恢复——设备自身知道哪些状态可重建（如从生产者/消费者索引推断活跃 QP 列表）、哪些已过时（如拥塞控制状态），从而实现精确的状态蒸馏

#### [Demeter: A Scalable and Elastic Tiered Memory Solution via Guest Delegation](./3731569.3764801.md)
- **作者**：Junliang Hu et al.
- **要解决的问题**：虚拟化云中基于 hypervisor 的分层内存管理因 2D 地址翻译产生昂贵 TLB flush（比 guest 多 4.7x），且无法利用 PEBS 硬件采样
- **核心贡献**：Demeter 将 TMM 完全委托给 guest VM，利用 EPT 友好的 PEBS 采样、guest 虚拟地址空间中的范围热度分类和双气球弹性供给，性能提升最高 2x，CPU 开销仅 0.64%
- **关键发现/观点**：三个观察使高效 guest 委托 TMM 成为可能：(1) PEBS v5 在虚拟化环境中实际可用且硬件隔离；(2) guest 虚拟地址空间保留了物理地址空间破坏的空间局部性；(3) 将所有 TMM 阶段委托给 guest 避免了 hypervisor 昂贵的 PTE.A/D 扫描和破坏性全 TLB flush

#### [Unlocking True Elasticity for the Cloud-Native Era with Dandelion](./3731569.3764803.md)
- **作者**：Tom Kuchler et al.
- **要解决的问题**：FaaS 平台面临冷启动/过度供给困境：避免冷启动延迟需预供给热沙箱占用 16x 实际所需内存，剩余冷启动仍导致 10-100x 的尾延迟
- **核心贡献**：Dandelion 通过声明式编程模型将应用分解为纯计算函数（在无 OS 轻量沙箱中运行，~100us 冷启动）和平台提供的通信函数，内存过度供给减少 96%，p99 延迟降低 46%
- **关键发现/观点**：云原生应用本质上由两类操作组成——纯计算和与外部服务的通信；显式分离这两类操作并在无 guest OS、网络栈或系统调用的沙箱中运行纯计算，可完全消除冷启动开销的根因

#### [Quilt: Resource-aware Merging of Serverless Workflows](./3731569.3764830.md)
- **作者**：Yuxuan Zhang et al.
- **要解决的问题**：Serverless workflow 函数间调用经过 HTTP/API 网关引入序列化、网络延迟和冷启动开销，对短生命周期函数（20% Lambda 函数执行时间 <100ms）尤为严重
- **核心贡献**：LLVM IR 级跨语言函数合并器，通过资源感知图聚类透明合并 serverless workflow 函数，延迟降低 45-71%，吞吐提升 2-13x
- **关键发现/观点**：Serverless 函数完全通过 REST API 和 JSON 编码字符串交互，因此在 LLVM IR 级合并只需处理字符串类型转换而非完整跨语言内存模型兼容性；同一 workflow 内的函数共享信任域，函数级隔离不必要

#### [Oasis: Pooling PCIe Devices Over CXL to Boost Utilization](./3731569.3764812.md)
- **作者**：Yuhong Zhong et al.
- **要解决的问题**：云数据中心 PCIe 设备（NIC、SSD）严重低利用（NIC 带宽 ~15%，SSD 容量 ~67%），资源搁浅、峰值过度供给和冗余容错加剧浪费
- **核心贡献**：已部署的 CXL 内存池可以近零额外成本在软件层面池化跨主机 PCIe 设备，仅 4-7us 附加延迟，通过利用 PCIe DMA 绕过 CPU cache 消除大部分一致性开销
- **关键发现/观点**：CXL 内存池已因内存池化获得经济合理性，同一基础设施可以近零边际成本解锁 PCIe 设备池化；由于 PCIe 设备通过 DMA 绕过 CPU cache 访问内存，非一致性 CXL 共享内存上的大部分 cache 一致性开销可安全消除

#### [PhoenixOS: Concurrent OS-level GPU Checkpoint and Restore with Validated Speculation](./3731569.3764813.md)
- **作者**：Xingda Wei et al.
- **要解决的问题**：GPU checkpoint/restore 目前是 stop-the-world 的——GPU 缺乏硬件 dirty bit 和 CoW 支持，导致多秒级停顿（如 Llama2-13B 恢复 6.2s）
- **核心贡献**：引入 validated speculation——从 GPU kernel 启动参数推断读写集（通过二进制插桩验证）——实现并发 GPU checkpoint（软 CoW/recopy）和 restore（按需数据加载），checkpoint 停顿降低 70-160%，serverless 冷启动加速 16x
- **关键发现/观点**：与对 OS 不透明的 CPU 执行不同，GPU 执行通过细粒度 API 调用（CUDA）中介，每个 kernel 访问的数据缓冲区通常编码在启动参数的可变指针参数中；这允许 OS 通过匹配启动参数指针和已分配缓冲区范围来推测每个 kernel 的读写集

#### [Tai Chi: A General High-Efficiency Scheduling Framework for SmartNICs](./3731569.3764851.md)
- **作者**：Bang Di et al.
- **要解决的问题**：SmartNIC 上数据平面和控制平面间的静态 CPU 分区浪费 67.5% 数据平面 CPU 周期，同时控制平面任务严重资源饥饿
- **核心贡献**：Tai Chi 混合虚拟化框架将控制平面封装为与数据平面共享 OS 的 vCPU，利用 ~3.2us I/O 预处理窗口隐藏虚拟化切换延迟，控制平面加速 4x 且数据平面开销仅 0.7%，已在阿里云生产部署 3+ 年
- **关键发现/观点**：SmartNIC 可编程 I/O 加速器在数据平面服务处理 I/O 包之前有 ~3.2us 预处理窗口（硬件预处理 + DMA 写入）；这个窗口可被利用来提前触发 vCPU 上下文切换，将 2us 虚拟化调度延迟完全隐藏在 I/O 预处理流水线中

#### [Moirai: Optimizing Placement of Data and Compute in Hybrid Clouds](./3731569.3764802.md)
- **作者**：Ziyue Qiu et al.
- **要解决的问题**：混合云部署因跨站点数据访问产生巨额成本——egress 费用、专线成本和数据复制存储（如 Twitter 300PB 复制成本 ~$90M/年）
- **核心贡献**：Moirai 联合优化 job 路由和数据放置，使用依赖驱动分组和基于 Job Access Density 的选择性复制（仅 0.2% 表），在 Uber 生产 trace 上成本降低 97%+
- **关键发现/观点**：大型数据湖中 job-table 依赖高度互联但结构可分析——通过挖掘查询模板访问模式（而非使用人为组织边界），可发现最优 job-data 分组，复制仅 0.2% 最高访问密度的表就足以大幅减少跨站点流量

---

### 分布式系统与数据管理（5 篇）

#### [Pesto: Cooking up High Performance BFT Queries](./3731569.3764799.md)
- **作者**：Florian Suri-Payer et al.
- **要解决的问题**：BFT 数据存储面临性能与表达力的根本矛盾：SMR-based BFT 数据库全序化所有操作丧失并行性，高性能 BFT KVS 只支持简单 GET/PUT 无法处理 SQL 查询
- **核心贡献**：Pesto BFT SQL 数据库使用按需快照同步（仅同步匹配查询谓词的活跃行）和语义感知 OCC（基于并发写入是否影响查询结果的冲突检测），吞吐匹配非复制数据库
- **关键发现/观点**：查询的一致性只需在该查询谓词涉及的特定数据上成立，而非整个数据库；这允许按需、谓词范围的副本状态同步而非全局全序化

#### [Running Consistent Applications Closer to Users with Radical](./3731569.3764831.md)
- **作者**：Nicolaas Kaashoek et al.
- **要解决的问题**：将强一致性应用部署到靠近用户的位置反而不能降低延迟——每次存储访问需要到中央数据存储的长距离往返，地理复制存储的协调开销抵消了接近性收益
- **核心贡献**：LVI 协议将投机执行与单程一致性协调请求并行化，实现 28-35% 延迟改善（理论最优的 84-89%）
- **关键发现/观点**：对于 serverless 函数，静态分析可以在执行前确定读写集，允许将一致性协调压缩为与投机执行并行运行的单向请求——用计算时间"隐藏"协调延迟

#### [Tiga: Accelerating Geo-Distributed Transactions with Synchronized Clocks](./3731569.3764854.md)
- **作者**：Jinkun Geng et al.
- **要解决的问题**：地理分布式 OLTP 系统需多次广域往返（WRTT）保证强一致性，现有合并协议快速路径仅在非冲突事务下有效，退回昂贵慢速路径
- **核心贡献**：Tiga 将并发控制和共识合并为单层，使用同步时钟主动为事务分配未来时间戳确保全局一致排序，实现 1-WRTT 提交，吞吐提升 1.3-3.5x
- **关键发现/观点**：与其乐观依赖事务到达顺序（跨地理分布服务器常常不一致），同步时钟可以主动为每个事务分配未来时间戳，使其全局顺序在到达任何服务器前就已确定；现代时钟同步精度（微秒）远小于跨区域传输延迟（数十毫秒），增加的余量可有效掩盖异构网络延迟

#### [Spirit: Fair Allocation of Interdependent Resources in Remote Memory Systems](./3731569.3764805.md)
- **作者**：Seung-seob Lee et al.
- **要解决的问题**：远端内存系统中本地 DRAM cache 和网络带宽是相互依赖的资源（更多 cache 减少带宽需求），但 DRF 等公平分配方案将其视为独立资源，无法利用互补偏好
- **核心贡献**：基于 CEEI/Walrasian 经济学的 Symbiosis 拍卖算法，实现 Pareto 最优、无嫉妒和共享激励兼容的相互依赖 cache-bandwidth 公平分配
- **关键发现/观点**：不同应用对 cache 和 bandwidth 表现出显著不同且互补的敏感性——带宽敏感和 cache 敏感的应用可以互相交换各自不太需要的资源类型以同时改善性能，这种依赖关系可通过运行时采样估计

#### [Mantle: Efficient Hierarchical Metadata Management for Cloud Object Storage](./3731569.3764824.md)
- **作者**：Jiahao Li et al.
- **要解决的问题**：云对象存储元数据服务因多轮 RPC 路径解析（平均路径深度 10-12 层）和目录更新的严重写竞争而性能低下
- **核心贡献**：Mantle 双层包含架构（轻量 IndexNode 实现单 RPC 路径解析 + 可扩展 TafDB 存储完整元数据）+ 细粒度访问/属性元数据分离 + delta 记录消除写竞争，Spark 作业完成时间降低 93.3%，在百度生产环境管理数十亿对象 1.5+ 年
- **关键发现/观点**：目录元数据（用于路径解析的访问元数据）仅占全部元数据的极小比例（目录仅占 8-18% 条目），每个目录的访问元数据仅 ~80 字节，单节点内存可缓存整个命名空间的所有目录元数据；目录 rename 主要发生在叶节点附近，上层路径前缀高度稳定可安全缓存

---

### 安全与可信计算（5 篇）

#### [The Design and Implementation of a Virtual Firmware Monitor (Miralis)](./3731569.3764826.md)
- **作者**：Charly Castes et al.
- **要解决的问题**：当前 TEE 部署中，供应商固件和安全 monitor 共享最高特权级且无隔离；固件代码库庞大（1M+ 行）、闭源，任何固件漏洞完全破坏平台安全保证
- **核心贡献**：引入 Virtual Firmware Monitor 概念，Miralis（6.2K 行 Rust）使用 trap-and-emulate 将未修改供应商固件从最高特权级降级到用户模式，通过快速路径卸载实现零性能开销
- **关键发现/观点**：虽然供应商固件运行在最高特权级，但绝大多数功能不需要无限制特权访问——主要执行可选硬件特性的软件仿真；在 VisionFive 2 平台上 99.98% 的 M-mode trap 仅有 5 种原因，均为标准 RISC-V 可选特性的通用仿真

#### [Tock: From Research to Securing 10 Million Computers](./3731569.3764828.md)
- **作者**：Leon Schuermann et al.
- **要解决的问题**：运行在资源受限微控制器（无虚拟内存，~100kB RAM）上的嵌入式系统缺乏组件间隔离，易受 bug 和攻击影响
- **核心贡献**：Tock 10 年经验报告，基于 Rust 类型系统的零开销内核扩展隔离（capsule）、无堆内核（Grant）的资源隔离，已部署在数千万设备上包括 Google 安全芯片
- **关键发现/观点**：Rust 所有权类型系统不仅是内存安全机制，还可以作为零运行时开销的隔离机制——在无虚拟内存的微控制器上通过编译时类型检查强制内核扩展的权限边界

#### [CHERIoT RTOS: An OS for Fine-Grained Memory-Safe Compartments on Low-Cost Embedded Devices](./3731569.3764844.md)
- **作者**：Saar Amar et al.
- **要解决的问题**：低成本嵌入式设备缺乏细粒度内存保护（仅 8 个 MPU 域），C/C++ 代码无空间/时间内存安全，现有隔离方法无法加固组件间接口
- **核心贡献**：CHERIoT RTOS 利用 CHERI capability（无 MMU）提供完整空间/时间内存安全、细粒度 compartmentalization 和接口加固，代码占用仅 25.9 KB，compartment 调用开销 209 周期
- **关键发现/观点**：在无 MMU 的嵌入式系统上，CHERI capability 单独就可以作为唯一隔离机制，同时实现细粒度空间/时间内存安全和组件隔离，面积和功耗开销与现有 MPU 方案相当

#### [TRIP: Coercion-resistant Registration for E-Voting (Votegral)](./3731569.3764837.md)
- **作者**：Louis-Henri Merino et al.
- **要解决的问题**：反强制电子投票方案基于假凭证将信任问题转移到注册阶段，需要可信硬件或与多个独立权威交互——不实用且缺乏可用性验证
- **核心贡献**：TRIP 物理凭证注册协议利用交互式零知识证明的 commit-challenge 排序产生密码学不可区分的真假凭证，150 人可用性研究中 83% 成功率
- **关键发现/观点**：交互式零知识证明的可靠性依赖 commit 和 challenge 的顺序——证明者先 commit 再挑战则证明可靠，反之证明者可伪造任何"证明"；这种顺序区别可物理化为隐私亭中不同的操作步骤序列，产生的纸质凭证密码学不可区分

#### [Orq: Complex Analytics on Private Data with Strong Security Guarantees](./3731569.3764833.md)
- **作者**：Eli Baum et al.
- **要解决的问题**：在 MPC 下执行带 join 的关系查询需要 O(n^{k+1}) 时间/空间（"级联效应"），使多表 join 查询不可行
- **核心贡献**：融合 join-aggregation 算子将多表 join 查询复杂度从 O(n^{k+1}) 降到 O(n log n)，首次在 MPC 下完成完整 TPC-H 基准测试（SF10），比先前工作加速最高 827x
- **关键发现/观点**：实际 MPC 应用中所有关系查询最终产生聚合结果（为保护隐私），这些查询有与数据分布无关的 O(n) 输出大小上界——当 join 后跟可分解聚合函数时，聚合可提前应用以避免物化笛卡尔积

---

### 系统可靠性与测试（6 篇）

#### [Orthrus: Efficient and Timely Detection of Silent User Data Corruption](./3731569.3764832.md)
- **作者**：Chenxiao Liu et al.
- **要解决的问题**："善变核心"导致的 Silent Data Corruption 在云 CPU 中静默损坏用户数据，现有检测方法要么太慢、太贵（>100% 开销）或需专用硬件
- **核心贡献**：混合验证方案，仅在不同 CPU 核心上重执行轻量数据路径操作（4.4% 吞吐开销），控制路径用 CRC 校验，结合版本化内存支持乱序验证，覆盖率 87-99%
- **关键发现/观点**：典型云应用天然分为控制路径（调度、I/O、分发——不修改用户数据）和数据路径（get/set/map/reduce——逻辑简单但直接处理用户数据），数据路径代码远小于控制路径（如 Memcached 小 20x），因此仅重执行数据路径操作就足以高效验证用户数据正确性

#### [Mitigating Application Resource Overload with Targeted Task Cancellation (Atropos)](./3731569.3764835.md)
- **作者**：Yigong Hu et al.
- **要解决的问题**：传统过载控制使用全局信号（队列长度、延迟）盲目丢弃请求，无法区分独占应用级资源的"元凶"请求和被它们阻塞的"受害者"请求
- **核心贡献**：Atropos 利用应用已有的取消机制（Go Context、Java 线程中断等）主动取消资源独占的元凶请求，在 6 个主流应用的 16 个过载场景中实现 96% 基线吞吐和 <0.01% 请求丢弃率
- **关键发现/观点**：76% 的现代软件已有内置任务取消机制（Go Context、Java thread interrupt、C++ stop_token），95% 提供开发者设计的安全取消入口点；系统可以直接复用现有应用取消逻辑安全终止问题请求

#### [Optimistic Recovery for High-Availability Software via Partial Process State Preservation (PHOENIX)](./3731569.3764858.md)
- **作者**：Yuzhuo Jing et al.
- **要解决的问题**：高可用软件面临二元恢复困境：完整进程重启丢弃所有状态（正确但慢，如 Redis 加载 6GB RDB 需 53.5s），完整 checkpoint（CRIU）保留 bug 状态
- **核心贡献**：PHOENIX 通过零拷贝内核级页表迁移选择性保留大型稳定数据结构，结合不安全区域检测和交叉检查验证，恢复时间从分钟级降到亚秒级（9-76x 改善）
- **关键发现/观点**：大多数生产软件故障仅损坏瞬态状态（局部变量、短生命周期堆对象）而非大型稳定全局数据结构；64 个真实 bug 研究显示 87.5% 的故障仅损坏瞬态状态——因为 bug 集中在复杂控制逻辑而大部分内存被简单、充分测试的数据结构占据

#### [Fawkes: Finding Data Durability Bugs in DBMSs via Recovered Data State Verification](./3731569.3764841.md)
- **作者**：Zhiyong Wu et al.
- **要解决的问题**：DBMS 数据持久性 bug（崩溃恢复后的数据丢失、不一致、日志损坏）难以检测——现有故障注入工具对文件系统/内核级调用缺乏精度
- **核心贡献**：Fawkes 使用上下文感知的文件系统/内核调用级故障注入、功能引导的故障触发和基于 checkpoint 的数据图验证，发现 8 个主流 DBMS 中 48 个未知持久性 bug（8 个 CVE）
- **关键发现/观点**：86% 的数据持久性 bug 只能在 SQL 数据修改语句执行的文件系统或内核级系统调用期间可靠触发；将故障注入点与 SQL 功能特征关联可实现持久性关键路径的系统化覆盖

#### [Loom: Efficient Capture and Querying of High-Frequency Telemetry](./3731569.3764853.md)
- **作者**：Franco Solleza et al.
- **要解决的问题**：高频遥测（百万记录/秒）面临三难困境：时序数据库因索引开销丢弃 9-77% 数据，日志存储缺乏灵活索引，采样丢失尾延迟调试所需的稀有关键事件
- **核心贡献**：Loom 使用混合 append-only 日志 + 分层稀疏索引（chunk 级直方图摘要 + 时间戳索引），单 CPU 核心写吞吐 9M 记录/秒，查询比 InfluxDB 快 7-160x
- **关键发现/观点**：可观测性查询高度规律——工程师主要关心时间范围、值范围、聚合（含百分位）和跨源关联；因此在固定大小 chunk 粒度维护轻量稀疏索引（直方图统计）而非逐记录精确索引，就足以大幅加速这些查询模式

#### [WASIT: Deep and Continuous Differential Testing of WebAssembly System Interface](./3731569.3764819.md)
- **作者**：Yage Hu et al.
- **要解决的问题**：正确实现 WASI 极其困难（语义复杂、规范模糊、平台依赖），现有测试工具无法通过依赖 WASI 调用序列探索深层系统状态
- **核心贡献**：WASIT 首个规范驱动的 WASI 差分测试框架，使用动态资源抽象和 SMT 约束求解生成语义有效的深层调用序列，发现 6 个主流 Wasm 运行时中 48 个新 bug（含 3 个 CVE）
- **关键发现/观点**：WASI 函数行为可通过抽象建模和运行时跟踪系统资源（文件描述符、套接字等）理解，无需访问实现源码；给 WASI 规范添加轻量语义注解（资源类型、输入约束、输出效果）即可自动生成探索深层系统状态的依赖调用序列

---

### 资源调度与硬件协同（3 篇）

#### [COpter: Efficient Large-Scale Resource-Allocation via Continual Optimization](./3731569.3764846.md)
- **作者**：Suhas Jayaram Subramanya et al.
- **要解决的问题**：基于数学规划的资源分配（LP/MILP）在大规模基础设施（25k+ GPU）上不可行——编译开销超过求解时间，求解器无法跨轮复用计算
- **核心贡献**：COpter 引入 continual optimization——将连续分配轮次视为相关问题——使用差分问题更新、无分解 PPA 求解器高效热启动和轻量整数舍入，比商业求解器加速 57-83x
- **关键发现/观点**：大规模资源分配问题在相邻调度轮次间缓慢演变——在足够短的间隔（2-5 分钟）内，绝大多数资源和请求不变（<0.01% 变量值变化）；现有方法每轮丢弃所有先前计算，但将轮次视为连接序列可使求解时间取决于变化的路径长度而非绝对问题规模

#### [Fast End-to-End Performance Simulation of Accelerated Hardware-Software Stacks (NEX+DSim)](./3731569.3764825.md)
- **作者**：Jiacheng Ma et al.
- **要解决的问题**：硬件加速器系统的全栈模拟（gem5 + RTL）极慢（5000-24000x 减速），评估设计变更需数小时，严重阻碍交互式开发
- **核心贡献**：NEX+DSim 通过最小化原则——原生运行可用组件、仅周期精确模拟不可用组件的性能关键方面——实现 6-879x 加速且平均 7% 误差
- **关键发现/观点**：对系统软件开发者而言，绝大部分模拟开销来自不必要地模拟已可用组件（如 CPU）和过度详细建模加速器的非性能关键方面；仅模拟不可用组件且只建模其性能关键方面（流水线结构、并行度、延迟、背压）可在保持足够精度的同时实现数量级加速

#### [Coyote v2: Raising the Level of Abstraction for Data Center FPGAs](./3731569.3764845.md)
- **作者**：Benjamin Ramhorst et al.
- **要解决的问题**：数据中心 FPGA 开发 ~75% 工作量用于基础设施（网络、I/O、主机通信）而非应用逻辑，现有 FPGA shell 缺乏运行时服务重配置和多租户应用流水线支持
- **核心贡献**：Coyote v2 三层分级架构（static/dynamic services/application），支持服务和应用的独立运行时重配置（比完整重编程快 ~100x），集成 RoCEv2 RDMA 和共享虚拟内存
- **关键发现/观点**：将 FPGA shell 的服务层从静态层分离为独立可重配置的中间层，大幅简化静态层（仅剩 CPU-FPGA 链路管理），实现服务和应用的无停机运行时重配置且不牺牲性能——类比传统 OS 将设备驱动与内核分离

---

## 研究趋势分析

**1. LLM 系统成为系统研究的绝对主导**

SOSP 2025 中近三分之一的论文（19/66）直接围绕 LLM 推理、服务或训练展开，这一比例在顶级系统会议中前所未有。LLM 系统研究已从"如何让模型跑得更快"的单一优化问题，演进为一个完整的系统生态：推理端出现了面向异构架构的内存管理（Jenga、DiffKV）、可编程服务引擎（Pie）、多模型 GPU 池化（Aegaeon）；训练端则聚焦于万卡级容错（ByteRobust）、异构集群调度（Sailor）和通信可观测性（Mycroft）。值得注意的是，LLM 系统研究正在与传统系统问题深度融合——如将远程内存抽象引入多 GPU 通信（Mercury）、将编译技术应用于动态计算图（Tempo）、将经济学公平分配理论应用于远端内存（Spirit）。

**2. 形式化验证进入"实用化"拐点**

本届会议出现了 7 篇形式化验证相关论文，覆盖从微内核（Atmosphere）到分布式系统（AutoMan）、嵌入式 OS（TickTock）、eBPF 验证器（BCF）、生产级 hypervisor（Ghost/pKVM）到分布式训练计划（TrainVerify）。一个共同趋势是降低验证成本：Atmosphere 将证明代码比从 seL4 的 20:1 降至 3.32:1；Ghost 用 C 语言而非专用工具编写可执行规范；AutoMan 自动生成 70-97% 的验证代码。eBPF 生态的两篇论文（BCF 和 Veritas）则从不同角度攻击验证器精度问题。LLM 辅助程序分析（KNighter）的出现预示着 AI+Verification 的交叉方向。

**3. 硬件-软件协同设计的新范式**

多篇论文利用新兴或未充分利用的硬件特性解决经典系统问题：CHERI capability 在嵌入式安全（CHERIoT）和单地址空间 fork（uFork）中的应用；用户空间硬件中断（Aeolia）和 monitorx/mwaitx 指令（Sandman）改变存储栈设计；eBPF 从内核扩展工具演变为通用系统构建块（cache_ext 自定义 page cache、FlexGuard 精确锁检测）；CXL 从内存池化扩展到 PCIe 设备池化（Oasis）。这些工作表明，现代硬件提供的特性远未被系统软件充分利用。

**4. "消除抽象层"成为性能突破的主要手段**

多篇论文的核心思路是消除或重构传统抽象层以获得性能提升：CortenMM 消除 VMA 树直接操作页表获得 26x 加速；GoFS 将文件系统从 CPU 搬到 GPU 消除主机瓶颈；Dandelion 将计算和通信分离消除 FaaS 冷启动根因；Quilt 在 LLVM IR 层合并 serverless 函数消除 API 网关开销。这反映了社区的共识：随着硬件能力的提升，许多传统软件抽象层已从"必要的简化"变为"不必要的开销"。

**5. 可靠性和可观测性成为生产系统的刚需**

系统可靠性不再是学术话题而是工程现实：ByteRobust 报告了万卡训练中的真实故障模式，Mycroft 解决了 NCCL 的黑盒调试问题，Orthrus 针对 CPU silent data corruption 提出实用检测方案，PHOENIX 将服务恢复时间从分钟级降到亚秒级。这些工作共同指向一个趋势：随着系统规模和复杂度的增长，"fail-stop"假设不再成立，系统必须能够处理静默故障、部分失败和快速恢复。

---

## 小实验室的机会窗口

### 1. eBPF 驱动的系统定制化

- **方向描述**：利用 eBPF 作为通用系统构建块，实现各类内核子系统的可编程化和策略定制
- **为什么小团队能做**：eBPF 程序通常数百行代码，不需要修改内核源码，开发和测试周期短；cache_ext 和 FlexGuard 已证明 eBPF 可以有效介入 page cache 和同步原语等核心子系统
- **哪些论文指向了这个空白**：cache_ext（page cache 驱逐策略定制）、FlexGuard（锁抢占检测）、BCF（eBPF 验证器精度提升）
- **具体的 open problems**：
  - eBPF 驱动的 I/O 调度策略定制（类似 cache_ext 对 block I/O scheduler 做的事）
  - 用 eBPF 实现应用感知的 NUMA 内存迁移策略
  - eBPF 辅助的细粒度功耗管理（结合 Sandman 的思路）
  - eBPF 验证器精度的系统性改进，特别是循环和指针运算场景

### 2. LLM 推理的工作负载特化

- **方向描述**：为特定 LLM 工作负载模式（prefill-only、RAG、agent）设计专用优化，而非通用推理引擎
- **为什么小团队能做**：PrefillOnly 证明了针对特定工作负载模式的简单优化可以获得数倍性能提升，不需要修改底层推理引擎；METIS 的配置自适应也是纯系统层面的优化
- **哪些论文指向了这个空白**：PrefillOnly（prefill-only 特化）、METIS（RAG 配置自适应）、IC-Cache（语义缓存增强小模型）、HedraRAG（RAG pipeline 优化）
- **具体的 open problems**：
  - 面向 Agent workflow 的推理引擎优化（频繁上下文切换、多轮短生成）
  - Embedding/分类等单 token 输出场景的极致内存优化
  - 跨请求 KV cache 共享的自适应策略（不同应用场景的最优共享粒度不同）
  - RAG 中检索和生成的端到端延迟建模与调度

### 3. 分布式训练的正确性验证与调试

- **方向描述**：为分布式训练提供形式化验证和高效调试工具
- **为什么小团队能做**：TrainVerify 证明基于符号执行的验证方法可以扩展到超大模型，核心算法工作量可控；Mycroft 仅用 ~1100 行代码即实现了关键路径追踪
- **哪些论文指向了这个空白**：TrainVerify（训练计划验证）、Mycroft（集合通信追踪）、ByteRobust（训练容错）
- **具体的 open problems**：
  - 自动检测分布式训练中的精度损失模式（不同并行策略导致的数值差异）
  - 轻量级的 gradient 正确性在线验证
  - 混合精度训练中 loss scaling 策略的形式化分析
  - 训练故障的自动根因定位（结合 Mycroft 的追踪和 TrainVerify 的验证）

### 4. 面向新硬件特性的 OS 机制

- **方向描述**：利用未被充分利用的硬件特性（CHERI、用户空间中断、CXL、AMX 等）重新设计 OS 子系统
- **为什么小团队能做**：多为纯软件工作，在模拟器或已有硬件上实验；uFork 和 Aeolia 证明了单一硬件特性可以催生全新系统设计
- **哪些论文指向了这个空白**：uFork（CHERI fork）、Aeolia（用户空间中断存储栈）、Sandman（monitorx/mwaitx 节能）、Oasis（CXL 设备池化）、FlexGuard（eBPF 锁检测）
- **具体的 open problems**：
  - CXL 3.0 共享内存上的新型并发数据结构
  - 用户空间中断在网络栈中的应用（类比 Aeolia 对存储栈的改造）
  - CHERI 在容器隔离中的应用（无需完整虚拟化的轻量隔离）
  - Intel AMX/ARM SME 在系统软件（非 ML）中的应用场景

### 5. 实用化形式化验证方法

- **方向描述**：降低形式化验证的工程门槛，使其可应用于更多生产系统
- **为什么小团队能做**：Atmosphere 证明 Rust+Verus 可将验证工作量降低一个数量级；Ghost 证明用 C 语言写可执行规范也是可行的；这些方法论可推广到新领域
- **哪些论文指向了这个空白**：Atmosphere（Rust+Verus 高效验证）、AutoMan（自动代码生成+选择性优化）、Ghost/pKVM（C 语言可执行规范）、TickTock（精化类型验证嵌入式 OS）
- **具体的 open problems**：
  - 将 Atmosphere 的 flat permission 技术推广到其他涉及递归数据结构的系统
  - 为常见系统组件（网络栈、文件系统、调度器）建立可复用的验证模板
  - LLM 辅助的证明生成（结合 KNighter 的思路）
  - 增量验证：系统演进时只重新验证变更部分而非全部
