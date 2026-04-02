# USENIX Symposium on Operating Systems Design and Implementation (OSDI) 2025 论文概览

> 共 53 篇论文 | 生成日期: 2026-04-01

---

## 论文分类索引

### LLM 推理与 Serving（4 篇）

#### [[osdi25-zhu-kan|NanoFlow: Towards Optimal Large Language Model Serving Throughput]]
- **作者**：Kan Zhu et al.
- **要解决的问题**：现有 LLM 推理引擎顺序执行 compute/memory/network 操作，GPU 利用率仅约 40%，与理论最优吞吐差距巨大
- **核心贡献**：通过 nano-batch 拆分和 intra-device parallelism 实现异构操作在同一 GPU 上并行执行
- **关键发现/观点**：现代 LLM 推理在端到端层面实际是 compute-bound 而非传统认知的 memory-bound——拆分 batch 增加的权重加载开销可被计算完全隐藏

#### [[osdi25-he|WaferLLM: Large Language Model Inference at Wafer Scale]]
- **作者**：Congjie He et al.
- **要解决的问题**：GPU 内存带宽限制 LLM 推理性能，现有分布式 GEMM/GEMV 算法无法适配 wafer-scale 加速器的百万核 mesh 架构
- **核心贡献**：提出 PLMR 设备模型和 MeshGEMM/MeshGEMV 算法，在 Cerebras WSE-2 上实现 LLM 推理
- **关键发现/观点**：Wafer-scale 加速器的核心约束可统一为四个属性（Parallelism/Latency/Memory/Routing），违反任一属性即导致现有方案失效

#### [[osdi25-park-yeonhong|DecDEC: A Systems Approach to Advancing Low-Bit LLM Quantization]]
- **作者**：Yeonhong Park et al.
- **要解决的问题**：低比特量化导致 LLM 质量显著下降，尤其 activation outlier 对应的 salient channel 量化误差被放大
- **核心贡献**：利用 CPU 内存存储量化残差，运行时动态识别 salient channel 并选择性补偿
- **关键发现/观点**：Activation outlier 分布逐 token 动态变化，静态分析的 recall 仅约 20%；只有实时识别才能在有限 PCIe 带宽下最大化质量恢复

#### [[osdi25-zhang-dingyan|BLITZSCALE: Fast and Live Large Model Autoscaling with O(1) Host Caching]]
- **作者**：Dingyan Zhang et al.
- **要解决的问题**：MaaS 场景下模型扩容的数据平面速度不足（SSD 加载需数秒），主机缓存命中率低（40-75%）
- **核心贡献**：通过集群级 O(1) 缓存策略和 live migration 机制实现亚秒级模型扩容
- **关键发现/观点**：将每个模型的参数分片缓存在恰好一台主机上（O(1) 副本）比分散缓存更优——通过 RDMA 从远端主机加载比 SSD 加载快一个数量级

### LLM/DNN 训练（5 篇）

#### [[osdi25-wang-zheng|WLB-LLM: Workload-Balanced 4D Parallelism for Large Language Model Training]]
- **作者**：Zheng Wang et al. (Meta)
- **要解决的问题**：长上下文训练中文档长度偏斜导致 GPU 间严重负载不均（最慢 GPU 延迟是其他的 1.44 倍）
- **核心贡献**：选择性延迟极少量长文档并允许短文档拼接超过上下文窗口，实现 PP 和 CP 两个维度的负载均衡
- **关键发现/观点**：长文档虽影响最大但 token 占比很小（>75% token 来自不到半窗口的短文档），选择性延迟对数据随机性影响微乎其微

#### [[osdi25-lin-jinkun|Understanding Stragglers in Large Model Training Using What-if Analysis]]
- **作者**：Jinkun Lin et al. (ByteDance/NYU)
- **要解决的问题**：缺乏对真实大规模 LLM 训练中 straggler 问题的系统性量化分析
- **核心贡献**：基于 ByteDance 五个月 3079 个训练作业的 trace，通过 what-if 分析量化 straggler 影响并归因
- **关键发现/观点**：42.5% 的作业受 straggler 影响超 10%，全集群 10.4% GPU 小时被浪费；主因不是硬件故障，而是 PP stage 分区不均衡（39.3%）、序列长度不均衡（21.4%）和 Python GC

#### [[osdi25-jiang|Training with Confidence: Catching Silent Errors in Deep Learning Training]]
- **作者**：Yuxuan Jiang et al.
- **要解决的问题**：深度学习训练中的静默错误不触发异常但产生错误模型，高层指标（loss/accuracy）噪声大难以检测
- **核心贡献**：自动推断训练不变量（如 TP 中未分区层权重应一致），在运行时持续验证
- **关键发现/观点**：静默错误的根因在底层是确定性的、可早期检测的——选择合适的观测层级可以定义简洁精确的训练不变量，且不同训练程序可共享不变量

#### [[osdi25-ren|Enabling Efficient GPU Communication over Multiple NICs with FuseLink]]
- **作者**：Zhenghang Ren et al.
- **要解决的问题**：静态 GPU-NIC 绑定导致动态不均衡流量下 NIC 利用率仅 13%-82%
- **核心贡献**：利用 NVLink 作为 inter-server 网络扩展，通过 GPU relay 动态聚合多块 NIC 带宽
- **关键发现/观点**：Intra-server GPU 高速互联可作为 inter-server 网络的无缝扩展——通过虚拟地址重映射实现零拷贝 relay，将单 GPU inter-server 带宽从 50 提升至 212 GBps

#### [[osdi25-wang-zhuang|ZEN: Empowering Distributed Training with Sparsity-driven Data Synchronization]]
- **作者**：Zhuang Wang et al.
- **要解决的问题**：稀疏梯度同步中负载不均衡（50%+ 非零梯度集中在同一分区）和索引开销过大（通信量翻倍）
- **核心贡献**：数据无关的负载均衡分区方案和自适应稀疏编码格式
- **关键发现/观点**：稀疏梯度的非零元素分布高度偏斜，但可以通过数据无关的随机化分区实现近似均匀分布，避免数据依赖分析的高开销

### DNN 编译器与 Kernel 优化（4 篇）

#### [[osdi25-cheng|PipeThreader: Software-Defined Pipelining for Efficient DNN Execution]]
- **作者**：Yu Cheng et al. (Peking University/Microsoft Research)
- **要解决的问题**：GPU 异构专用单元（TensorCore/CUDA Core/TMA）间缺乏协同调度，硬件利用率低
- **核心贡献**：提出 sTask/sEU 抽象，将流水线调度从隐式硬件行为转为显式软件控制
- **关键发现/观点**：新硬件专用单元以 tensor tile 粒度处理数据，tile 级执行具有确定性性能特征，因此可以用软件精确编排异构单元间的流水线执行

#### [[osdi25-wu-mengdi|Mirage: A Multi-Level Superoptimizer for Tensor Programs]]
- **作者**：Mengdi Wu et al. (CMU)
- **要解决的问题**：现有方法只在单一层级（kernel 或 schedule）优化，无法发现 FlashAttention 式的跨层级联合优化
- **核心贡献**：统一的三层级图表示（µGraph）实现 kernel/block/thread 三级协同超优化
- **关键发现/观点**：GPU 三个计算层级的内存访问代价差异悬殊，真正有效的性能优化需要跨层级协同——这种协同可用统一的层级图捕获并自动搜索

#### [[osdi25-dong|QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems]]
- **作者**：Shouyang Dong et al.
- **要解决的问题**：异构 DLS 间 tensor 程序移植成本极高，纯 LLM 转译正确性不足（计算错误率 92.3%）
- **核心贡献**：LLM 生成程序骨架 + SMT solver 修复底层细节的 neural-symbolic 协作方法
- **关键发现/观点**：LLM 擅长高层骨架但底层细节易错，符号合成擅长修复但搜索空间受限——两者优势恰好互补，分解为小步 pass 可限制 LLM 错误范围

#### [[osdi25-jeong|Bayesian Code Diffusion for Efficient Automatic Deep Learning Program Optimization]]
- **作者**：Isu Jeong et al.
- **要解决的问题**：DL 编译器 auto-tuning 效率低，每个子图独立搜索导致大量冗余
- **核心贡献**：利用相似子图间参数接近性，将已优化子图参数传播给相似子图
- **关键发现/观点**：共享相同 sketch 的子图，其最优配置在搜索空间中的余弦距离显著小于不同 sketch 子图——一个子图的最优参数是其相似子图的良好初始点

### GPU/XPU 性能分析与调度（4 篇）

#### [[osdi25-shen-weihang|XSched: Preemptive Scheduling for Diverse XPUs]]
- **作者**：Weihang Shen et al.
- **要解决的问题**：各种 XPU 内置硬件调度器能力不足（非抢占式 FCFS），现有软件方案仅适用于特定 GPU
- **核心贡献**：XQueue 可抢占命令队列抽象 + 三级渐进式硬件模型，覆盖 10 种 XPU
- **关键发现/观点**：尽管 XPU 硬件能力差异巨大，其驱动程序普遍提供基于队列的编程模型——这种共性使得统一的可抢占命令队列抽象成为可能

#### [[osdi25-guan|KPerfIR: Towards an Open and Compiler-centric Ecosystem for GPU Kernel Performance Tooling]]
- **作者**：Yue Guan et al.
- **要解决的问题**：现有 GPU profiler 与编译器系统割裂，缺乏 intra-kernel 细粒度 profiling
- **核心贡献**：将 profiling 能力以 MLIR dialect 形式集成到 Triton 编译器中
- **关键发现/观点**：将 profiling 从"外部工具"转为"编译器原生能力"，可同时获得程序语义感知、可编程性和跨平台可移植性

#### [[osdi25-huang-songlin|NEUTRINO: Fine-grained GPU Kernel Profiling via Programmable Probing]]
- **作者**：Songlin Huang et al.
- **要解决的问题**：现有 GPU profiler 粒度不足（最细到 PC sampling），缺乏可编程性和跨平台能力
- **核心贡献**：在 parallel assembly 层进行 runtime probing 的类 eBPF GPU profiling 框架
- **关键发现/观点**：Parallel assembly（PTX/GCNAsm）是 AOT 和 JIT 编译路径的最高公共层——在此层做 probing 可同时实现细粒度、跨平台和可编程性

#### [[osdi25-li|Tintin: A Unified Hardware Performance Profiling Infrastructure]]
- **作者**：Ao Li et al.
- **要解决的问题**：HPC event multiplexing 引入不可忽视的测量误差，profiling scope 不灵活导致事件归因错误
- **核心贡献**：将 multiplexing 建模为弹性实时调度问题，引入 ePX 作为新的 OS primitive 统一管理异构 profiling
- **关键发现/观点**：不同事件在不同执行阶段的方差特征不同——将更多 HPC 时间分配给高方差事件可降低总体测量误差

### 存储与文件系统（6 篇）

#### [[osdi25-athlur|Okapi: Decoupling Data Striping and Redundancy Grouping in Cluster File Systems]]
- **作者**：Sanjith Athlur et al. (CMU/Google)
- **要解决的问题**：集群文件系统中数据条带化与冗余分组紧耦合，导致性能与空间效率冲突
- **核心贡献**：将条带化配置与冗余分组配置解耦，允许独立优化 IO 性能和数据可靠性
- **关键发现/观点**：64%-94% 的文件在 150 天内始终使用相同大小的读请求，而 EC 方案可能变化 4 次——条带宽度应保持稳定匹配访问模式，而分组宽度需独立灵活调整

#### [[osdi25-gao|Stripeless Data Placement for Erasure-Coded In-Memory Storage]]
- **作者**：Jian Gao et al.
- **要解决的问题**：Stripe 概念在高速内存存储中导致高 I/O fanout、内存浪费或 MDS 瓶颈
- **核心贡献**：基于 SBIBD 组合数学结构实现无条带纠删码数据放置
- **关键发现/观点**：SBIBD 结构保证任意两个主节点的备份节点集合最多只有一个交集——无需 stripe 即可通过 XOR 编码实现多节点故障容错

#### [[osdi25-sun|Scalio: Scaling up DPU-based JBOF Key-value Store with NVMe-oF Target Offload]]
- **作者**：Xun Sun et al.
- **要解决的问题**：JBOF 中 DPU CPU 成为扩展瓶颈（4 块 SSD 即饱和），而网络 I/O 利用率不到 1%
- **核心贡献**：利用 NVMe-oF target offload 将 SSD 读操作卸载到 HCA 硬件，绕过 DPU CPU
- **关键发现/观点**：JBOF 场景中网络 I/O 能力与 SSD I/O 性能存在三个数量级的差距——可用富余的网络 IOPS 替代紧缺的 CPU 周期

#### [[osdi25-cui|Decentralized, Epoch-based F2FS Journaling with Fine-grained Crash Recovery]]
- **作者**：Yaotian Cui et al.
- **要解决的问题**：F2FS checkpointing 时间开销大（占总执行时间 17%-47%）且恢复不完整（恢复率仅 90.9%）
- **核心贡献**：面向 F2FS 的 metadata-change-based journaling + 去中心化 per-inode log
- **关键发现/观点**：F2FS 的 out-of-place-update 特性意味着旧数据在更新后不被覆盖——只需 journal 元数据"变化量"即可正确恢复

#### [[osdi25-pan|Fast and Synchronous Crash Consistency with Metadata Write-Once File System]]
- **作者**：Yanqi Pan et al.
- **要解决的问题**：现有 PM 文件系统元数据 I/O 消耗 11%-97% 总 I/O 时间，无法充分利用 PM 带宽
- **核心贡献**：将文件操作元数据聚合为 checksum-protected package 并一次写入
- **关键发现/观点**：为每个文件操作生成专用的聚合元数据并附加 checksum，只需一个 ordering point——从根本上消除了跨元数据对象的 I/O 编排难题

#### [[osdi25-leblanc|PoWER Never Corrupts: Tool-Agnostic Verification of Crash Consistency]]
- **作者**：Hayley LeBlanc et al.
- **要解决的问题**：验证 crash consistency 依赖专用逻辑框架（如 Crash Hoare Logic），工具绑定且学习曲线陡峭
- **核心贡献**：仅在 write API 前置条件中编码 crash consistency，完全在标准 Hoare 逻辑内完成
- **关键发现/观点**：不需要新的逻辑形式来处理 crash consistency——只需在 write 方法上添加前置条件，要求调用者证明该写操作的所有可能 crash 状态都合法

### 内存系统（4 篇）

#### [[osdi25-liu|Tiered Memory Management Beyond Hotness]]
- **作者**：Jinshu Liu et al.
- **要解决的问题**：分层内存中"热度等于性能关键性"的假设根本性错误——高 MLP 顺序访问虽"热"但延迟被掩盖
- **核心贡献**：提出 AOL（Amortized Offcore Latency）指标，实现性能驱动而非热度驱动的分层策略
- **关键发现/观点**：内存访问的实际性能影响取决于延迟和 MLP 的综合效果——AOL = Latency/MLP 才是准确的性能衡量指标

#### [[osdi25-chai-siyuan|EMT: An OS Framework for New Memory Translation Architectures]]
- **作者**：Siyuan Chai et al.
- **要解决的问题**：Linux 内存管理硬编码 radix tree 假设，无法支持 hash-based 等新型翻译架构
- **核心贡献**：translation object/database/service 三层抽象 + basic/customizable 二层 API
- **关键发现/观点**：翻译架构对 OS 性能有深远影响且不能假设恒定——ECPT 硬件加速页表遍历 23.1%，但 OS 开销增加使端到端收益仅 2.3%

#### [[osdi25-wang-xiaoyang|FineMem: Breaking the Allocation Overhead vs. Memory Waste Dilemma]]
- **作者**：Xiaoyang Wang et al.
- **要解决的问题**：RDMA MR 注册代价高昂（480µs/4MB），粗粒度预分配导致大量内存碎片
- **核心贡献**：基于 RDMA Memory Window 的预注册隔离 + 两层 bitmap tree 并发分配
- **关键发现/观点**：RDMA MW 可以在预注册 MR 之上以极低开销（~1µs/4MB vs MR 的 ~480µs）生成细粒度 rkey，同时实现多系统间的内存访问隔离

#### [[osdi25-huang-yibo|Tigon: A Distributed Database for a CXL Pod]]
- **作者**：Yibo Huang et al.
- **要解决的问题**：CXL 内存延迟高于 DRAM 且硬件缓存一致性区域有限，需要新方法利用 CXL 原子操作同步跨主机数据访问
- **核心贡献**：通过 CAT（Cross-host Active Tuples）概念将跨主机共享数据限制在极小范围，避免 2PC
- **关键发现/观点**：任意时刻被不同主机并发读写的 tuple 集合（CAT）极小——1000 核系统的 CAT 仅约 7MB，只需在 CXL 内存中维护这个小集合即可替代大量跨主机消息交换

### 网络系统（4 篇）

#### [[osdi25-wang-weitao|Söze: One Network Telemetry Is All You Need for Per-flow Weighted Bandwidth Allocation]]
- **作者**：Weitao Wang et al.
- **要解决的问题**：大规模数据中心实现高精度加权带宽分配依赖集中式求解器，可扩展性和敏捷性不足
- **核心贡献**：仅用路径上最大逐跳排队延迟（maxQD）一个遥测信号实现去中心化加权分配
- **关键发现/观点**：排队延迟可被重新定义为加权公平份额的编码信号——每个流发送端可独立根据此信号调整速率，无需 per-flow 状态或拓扑知识

#### [[osdi25-pismenny|rxBisect: Disentangling the Dual Role of NIC Receive Rings]]
- **作者**：Boris Pismenny et al.
- **要解决的问题**：per-core Rx ring 的 I/O working set 超出 LLC 容量导致 DDIO 失效
- **核心贡献**：将传统 Rx ring 拆分为独立的 Allocation ring 和 Bisected reception ring
- **关键发现/观点**：传统 Rx ring 不必要地耦合了内存分配和数据包接收两个正交结构——解耦后可用小 Ax ring 维持小 I/O working set，大 Bx ring 吸收突发

#### [[osdi25-lyerly|Skybridge: Bounded Staleness for Distributed Caches]]
- **作者**：Robert Lyerly et al. (Meta)
- **要解决的问题**：Meta TAO 的异步复制导致无界 staleness，粗粒度 watermark 造成大量 spurious upstream refill
- **核心贡献**：Replication with Gap Detection 旁路通道 + bloom filter 分层检查
- **关键发现/观点**：在读偏斜工作负载中，复制延迟时 shard 上绝大多数缓存项实际未被写入——通过放松复制语义构建轻量旁路通道，反而能提供更可靠的整体一致性

#### [[osdi25-frank|Picsou: Enabling Replicated State Machines to Communicate Efficiently]]
- **作者**：Reginald Frank et al.
- **要解决的问题**：RSM 间通信缺乏形式化原语，All-to-All 广播消息量 O(n_s × n_r) 二次增长
- **核心贡献**：定义 C3B 原语，通过 QUACKs 累积仲裁确认实现高效 RSM 间通信
- **关键发现/观点**：RSM 间通信与 TCP 可靠传输在结构上高度相似——可利用全双工通信和累积确认高效检测消息投递成功或丢失

### 分布式系统与资源管理（4 篇）

#### [[osdi25-bhat|Low End-to-End Latency atop a Speculative Shared Log with Fix-Ante Ordering]]
- **作者**：Shreesha G. Bhat et al.
- **要解决的问题**：Durability-first shared log 的全局排序协调导致高 delivery latency，拖高端到端延迟
- **核心贡献**：Fix-ante ordering 预先确定全局顺序，使 shard 能投机预测记录位置并提前交付
- **关键发现/观点**：如果 shared log 在全局协调完成前就预测记录顺序并提前交付，下游计算可与协调并行——重叠两者的时间开销即可降低 e2e 延迟

#### [[osdi25-shen-weihai|Mako: Speculative Distributed Transactions with Geo-Replication]]
- **作者**：Weihai Shen et al.
- **要解决的问题**：跨地域分布式事务中协调与复制紧耦合，复制延迟成为关键路径
- **核心贡献**：彻底解耦事务协调与 geo-replication，前台投机执行 + 后台异步复制
- **关键发现/观点**：事务协调和复制应进一步解耦而非合并——完全解耦后可用投机执行掩盖跨地域复制的高延迟，TPC-C 吞吐达 3.66M TPS

#### [[osdi25-domingo|Kamino: Efficient VM Allocation at Scale with Latency-Driven Cache-Aware Scheduling]]
- **作者**：David Domingo et al. (Azure)
- **要解决的问题**：VM 分配系统的缓存无感知调度导致不必要的 cache miss 和高延迟
- **核心贡献**：LatCache 算法估算每个 AA 端到端延迟（融合缓存状态和队列状态）进行调度
- **关键发现/观点**：仅优化缓存命中率或仅做负载均衡都不够，需要将延迟本身作为调度的一等指标——因为不同请求类型的缓存命中延迟甚至高于其他类型的未命中延迟

#### [[osdi25-xu|Decouple and Decompose: Scaling Resource Allocation with DeDe]]
- **作者**：Zhiying Xu et al.
- **要解决的问题**：大规模资源分配 LP/MILP 求解时间达分钟到小时级别，无法满足实时决策需求
- **核心贡献**：通过解耦和分解将大规模约束优化问题转化为可并行求解的子问题
- **关键发现/观点**：资源约束和需求约束通过共享分配变量相互纠缠——引入中间层解耦后可实现高效并行求解

### 向量搜索与加密检索（3 篇）

#### [[osdi25-guo|PipeANN: Achieving Low-Latency Graph-Based Vector Search via Aligning Best-First Search with SSD]]
- **作者**：Hao Guo et al.
- **要解决的问题**：图索引 best-first search 与 SSD I/O 特性不匹配，on-disk 搜索延迟是内存的 4.18×
- **核心贡献**：PipeSearch 算法识别并打破计算与 I/O 间的伪依赖，实现异步并行
- **关键发现/观点**：Best-first search 中每一步要读取哪些邻居仅由内存中的 candidate pool 决定，无需等待正在进行的 I/O——这是伪依赖，打破后可实现 compute-I/O 重叠

#### [[osdi25-mohoney|Quake: Adaptive Indexing for Vector Search]]
- **作者**：Jason Mohoney et al.
- **要解决的问题**：动态偏斜工作负载下分区索引严重退化（Faiss-IVF 搜索时间增长至 165 小时）
- **核心贡献**：代价驱动的增量分区维护 + 基于几何概率的自适应分区扫描（APS）
- **关键发现/观点**：偏斜工作负载中少数高频大分区贡献了绝大部分延迟——只需针对性维护高成本分区即可以最小代价实现全局优化

#### [[osdi25-zhu-jinhao|Compass: Encrypted Semantic Search with High Accuracy]]
- **作者**：Jinhao Zhu et al.
- **要解决的问题**：加密搜索方案在安全性和搜索质量间存在根本矛盾，现有方案仅支持低精度关键词搜索
- **核心贡献**：首个在 ORAM 上高效运行 graph-based ANN 搜索的加密语义搜索系统
- **关键发现/观点**：通过预计算图结构的访问模式并批量化 ORAM 请求，可大幅减少加密图遍历的网络往返次数

### Serverless 与容器（2 篇）

#### [[osdi25-chai-xiaohu|Fork in the Road: Reflections and Optimizations for Cold Start Latency in Serverless Systems]]
- **作者**：Xiaohu Chai et al. (蚂蚁集团)
- **要解决的问题**：Serverless 冷启动瓶颈已从容器初始化转移到控制路径交互、内核资源竞争和用户代码初始化
- **核心贡献**：FRI 精简控制路径 + 资源池化/共享 + 层次化 seed 树复用用户代码初始化状态
- **关键发现/观点**：端到端冷启动延迟的瓶颈已不在容器初始化本身——三个被忽视的环节各可通过"精简接口、预分配资源、模板复用"系统性消除

#### [[osdi25-miemietz|MettEagle: Costs and Benefits of Implementing Containers on Microkernels]]
- **作者**：Till Miemietz et al.
- **要解决的问题**：Linux 容器依赖 seccomp-bpf、namespaces、cgroups 等机制限制进程权限，增加内核复杂度和攻击面
- **核心贡献**：在 L4Re capability-based 微内核上实现容器级隔离，TCB 从 2.7M 缩至 89K SLOC
- **关键发现/观点**：在 capability-based 微内核上，进程默认无 ambient authority，隔离是系统固有属性——Linux 容器的三大安全机制在微内核上要么不需要，要么可用更简洁方式实现

### 安全与隐私（3 篇）

#### [[osdi25-adam|Paralegal: Practical Static Analysis for Privacy Bugs]]
- **作者**：Justus Adam et al.
- **要解决的问题**：隐私合规检查依赖人工审计，现有工具需为库代码手动建模且策略与代码紧耦合
- **核心贡献**：利用 Rust ownership 类型系统自动近似库函数行为，marker 抽象解耦策略与代码
- **关键发现/观点**：Rust 的 ownership 类型系统从根本上控制了 aliasing 和 mutation——仅通过函数类型签名就能 sound 且 precise 地近似第三方库函数行为

#### [[osdi25-soleimani|Weave: Efficient and Expressive Oblivious Analytics at Scale]]
- **作者**：Mahdi Soleimani et al.
- **要解决的问题**：Oblivious analytics 的 shuffle 开销为 O(n log n)，大数据集上端到端慢一个数量级
- **核心贡献**：random-shuffle + 采样直方图 + balanced-shuffle 三阶段替代传统 shuffle，开销降至常数倍
- **关键发现/观点**：先通过 random shuffle 使数据均匀分布后，每个 worker 已持有全局分布的均匀采样——只需注入少量 fake traffic 即可使通信量独立于数据分布

#### [[osdi25-schuermann|Omniglot: Building Bridges — Safe Interactions with Foreign Languages]]
- **作者**：Leon Schuermann et al.
- **要解决的问题**：FFI 调用外部 C 库时内存安全、类型安全和别名规则均可被破坏
- **核心贡献**：在 FFI 边界运行时验证外部代码输出的合法性，而非证明外部代码本身正确
- **关键发现/观点**：维护 FFI 安全不需要推理外部代码正确性——只需在边界验证每次执行结果是否符合宿主类型系统要求，即可恢复所有安全不变量

### 程序分析与验证（4 篇）

#### [[osdi25-zhang-tony|Basilisk: Using Provenance Invariants to Automate Proofs of Undecidable Protocols]]
- **作者**：Tony Nuda Zhang et al.
- **要解决的问题**：在不可判定逻辑下手动推导分布式协议归纳不变量极其费力（Multi-Paxos 耗时数月）
- **核心贡献**：通过 provenance invariants 自动推导跨主机属性，大幅减少手动证明工作量
- **关键发现/观点**：追踪协议中数据的"来源"（provenance）可以系统性地生成跨主机不变量——这些不变量编码了"为什么这个值在这里"的因果关系

#### [[osdi25-yedidia|Deterministic Client: Enforcing Determinism on Untrusted Machine Code]]
- **作者**：Zachary Yedidia et al.
- **要解决的问题**：智能合约沙箱的语言级方案（WebAssembly）性能差且 TCB 庞大
- **核心贡献**：首次将 SFI 技术应用于保证确定性执行，直接在原生机器码上强制确定性
- **关键发现/观点**：SFI 的二进制分析技术不仅可用于内存隔离，也可用于确定性保证——通过静态验证消除非确定性指令即可实现接近原生性能的确定性执行

#### [[osdi25-lou|T2C: Deriving Semantic Checkers from Tests to Detect Silent Failures]]
- **作者**：Chang Lou et al.
- **要解决的问题**：分布式系统静默语义故障缺乏运行时检测手段，语义检查器编写成本高
- **核心贡献**：从测试代码中自动提取并泛化语义检查器，部署到生产环境
- **关键发现/观点**：测试代码中编码了丰富的语义信息——87% 的测试使用标准 assertion，其中 65% 满足泛化为生产检查器的条件

#### [[osdi25-zhang-tianren|KRR: Efficient and Scalable Kernel Record Replay]]
- **作者**：Tianren Zhang et al.
- **要解决的问题**：现有 whole-VM RR 在多核环境下开销随核心数超线性增长（8 核达 30×）
- **核心贡献**：Split-Recorder 架构只记录内核执行而非整个 VM，大幅降低记录开销
- **关键发现/观点**：内核虽最复杂但非运行时间最长的组件，且 kernel-bypass 使内核输入远小于 VM 输入——只记录内核即可有效诊断 bug 且开销大幅降低

### 量子计算（2 篇）

#### [[osdi25-giortamis|QOS: Quantum Operating System]]
- **作者**：Emmanouil Giortamis et al.
- **要解决的问题**：NISQ 设备保真度下降快、时空异构性大、QPU 利用率低（26.3%）、负载不均
- **核心贡献**：通过 Qernel 抽象统一纠错、估计、多路复用和调度四层，系统性权衡保真度/利用率/等待时间
- **关键发现/观点**：量子电路中的噪声并非均匀分布——部分 qubit 和 gate 是"噪声热点"，优先处理热点可以最高效地提升保真度

#### [[osdi25-tao|Quantum Virtual Machines]]
- **作者**：Runzhou Tao et al.
- **要解决的问题**：量子程序独占整台量子计算机运行，利用率仅 3-8%，排队等待数天
- **核心贡献**：利用量子硬件 qubit 拓扑的重复结构定义 qVM，实现空间+时间多路复用
- **关键发现/观点**：所有真实量子计算机的 qubit 拓扑都由基本重复区域排列而成——以此定义 qVM 可实现零虚拟化开销的直接执行

### 操作系统与运行时（3 篇）

#### [[osdi25-wang-yun|To PRI or Not To PRI: Device Passthrough Memory Management]]
- **作者**：Yun Wang et al. (阿里巴巴)
- **要解决的问题**：设备直通要求静态 pin VM 内存，阻止超售；PRI 硬件兼容性差且延迟高
- **核心贡献**：无需 PRI 硬件支持的软件方案，实现设备直通场景下的内存超售
- **关键发现/观点**：生产数据中 73.14% VM IOPS 低于 1000，仅 3.57% 超过 30000——大部分场景可通过软件预取和动态 IOPS 感知策略避免 IOPF

#### [[osdi25-wu-yuanpei|OS Rendering Service Made Parallel]]
- **作者**：Yuanpei Wu et al.
- **要解决的问题**：渲染服务采用顺序执行模型，无法利用多核；折叠屏/多屏帧率不足
- **核心贡献**：乱序执行 + 顺序提交的并行渲染框架，解决状态/绘制顺序/资源三重依赖
- **关键发现/观点**：渲染操作间的依赖可以像 CPU 乱序执行那样处理——乱序并行执行 + 顺序提交可在保证正确性的前提下充分利用多核

#### [[osdi25-zheng-yusheng|Extending Applications Safely and Efficiently]]
- **作者**：Yusheng Zheng et al.
- **要解决的问题**：现有应用扩展框架在安全性、隔离性和高效性间无法同时取得平衡
- **核心贡献**：基于 eBPF 思想的用户态应用扩展框架，支持细粒度安全/互联性权衡
- **关键发现/观点**：eBPF 的验证+沙箱执行模式可从内核态迁移到用户态应用——在 assembly 层实现扩展隔离可同时获得安全性和接近原生的性能

### 系统方法论（1 篇）

#### [[osdi25-park-sujin|Principles and Methodologies for Serial Performance Optimization]]
- **作者**：Sujin Park et al.
- **要解决的问题**：串行性能优化缺乏系统化框架，方案设计依赖经验
- **核心贡献**：三个基本原则（removal/replacement/reordering）和八种方法论，覆盖十年 OSDI/SOSP 所有优化技术
- **关键发现/观点**：优化串行性能的唯一途径是修改任务序列——修改方式只有移除、替换和重排三种，所有观察到的优化技术都可用这三个操作的组合解释

---

## 研究趋势分析

**1. LLM 系统成为绝对主导主题**

OSDI 2025 最显著的特征是 LLM 相关论文的全面爆发。不仅有专门的推理优化（NanoFlow、WaferLLM、DecDEC、BLITZSCALE）和训练优化（WLB-LLM、ZEN、FuseLink），更值得注意的是大量传统系统领域的论文也在积极讨论与 LLM 的关联——从文件系统（checkpoint 存储）到网络（梯度同步）到内存管理（KV cache）。这表明 LLM 已从"AI 系统"的细分领域升级为整个系统研究的核心驱动力。

**2. 编译器与硬件协同优化深化**

PipeThreader、Mirage、KPerfIR 三篇论文揭示了一个明确趋势：随着 GPU 内部异构性加深（TensorCore + CUDA Core + TMA），编译器需要从"同质执行单元"的假设转向"异构单元间软件定义流水线"的新范式。KPerfIR 和 NEUTRINO 则从 profiling 侧推动编译器与性能分析工具的深度集成，形成优化闭环。

**3. 投机执行与延迟隐藏成为通用范式**

Belfast（shared log 投机交付）、Mako（投机事务执行）、PipeANN（投机 I/O）、DecDEC（投机误差补偿）——来自完全不同领域的论文不约而同地采用了"先投机执行、后验证/回滚"的模式来隐藏延迟。这表明投机执行已从 CPU 微架构设计理念泛化为系统层面的通用优化策略。

**4. CXL 和异构内存架构从概念走向实践**

Tigon（CXL pod 数据库）、FineMem（disaggregated memory）、Tiered Memory Beyond Hotness（CXL 分层管理）表明 CXL 生态正在成熟。特别值得注意的是 AOL 指标对"热度等于性能关键性"这一长期假设的颠覆，预示着内存管理将从简单的冷热分层转向更精细的性能感知分层。

**5. 形式化验证门槛显著降低**

PoWER 证明 crash consistency 可在标准 Hoare 逻辑内完成，Basilisk 大幅自动化了分布式协议的不变量推导，T2C 从测试代码自动派生语义检查器。这些工作共同指向一个方向：形式化验证正在从"专家特权"转变为"实用工程工具"。

---

## 小实验室的机会窗口

### 1. 编译器驱动的 Kernel 自动优化

- **方向描述**：将 KPerfIR 的 intra-kernel profiling 数据反馈给 Triton/TVM 的 auto-tuning，实现 profile-guided 的自动 kernel 优化
- **为什么小团队能做**：基于开源 Triton + KPerfIR 即可开展，不需要大规模 GPU 集群；核心工作在编译器 pass 层面，3-5 人可完成原型
- **哪些论文指向了这个空白**：KPerfIR 展示了 profiling 数据但未实现自动优化闭环；PipeThreader 证明了软件定义流水线的巨大潜力但搜索策略是贪心的；Bayesian Code Diffusion 的参数传播思路可进一步集成
- **具体的 open problems**：如何从 KPerfIR 的 region timing 数据自动推导最优的 SWP stage 数和 barrier 放置位置？如何将 PipeThreader 的 sTask 抽象与 Triton 的 auto-tuner 集成？

### 2. 训练可靠性基础设施

- **方向描述**：构建可共享、可迁移的训练不变量库，集成到 PyTorch/DeepSpeed 的 callback 机制中
- **为什么小团队能做**：TrainCheck 已开源，核心工作是工程化集成和不变量库的社区建设，不需要大量计算资源；可以从小规模（2-8 GPU）验证开始
- **哪些论文指向了这个空白**：TrainCheck 证明了不变量可跨训练管线迁移；Understanding Stragglers 揭示了 Python GC 等被忽视的训练可靠性问题
- **具体的 open problems**：如何设计与 torch.compile 兼容的插桩方案？如何将数值稳定性检查（超越 hash）纳入轻量级不变量框架？

### 3. 性能感知的分层内存管理

- **方向描述**：将 AOL 指标推广到 GPU 异构内存层次（HBM/GDDR/host），为 LLM 推理的 KV cache 分层提供理论基础
- **为什么小团队能做**：AOL 的核心思想（延迟/MLP 比值）概念简洁，移植到 GPU 需要找到等价的硬件计数器；可在单节点 GPU 上验证
- **哪些论文指向了这个空白**：Tiered Memory Beyond Hotness 证明了 AOL 在 CPU 侧的有效性；DecDEC 展示了 CPU-GPU 异构内存利用的潜力
- **具体的 open problems**：GPU 上是否存在等价于 CPU MLP 的可观测指标？Prefill 和 decode 阶段的 MLP 特征差异如何量化？

### 4. 动态向量索引的在线维护

- **方向描述**：将 Quake 的代价驱动维护思路与 PipeANN 的 SSD pipeline 搜索结合，构建面向 RAG 的自适应向量存储
- **为什么小团队能做**：Quake 和 PipeANN 均已开源，核心创新在算法层面而非硬件层面；单机 SSD + 100M 向量级别即可做有意义的实验
- **哪些论文指向了这个空白**：Quake 解决了索引维护但搜索延迟逊于图索引；PipeANN 优化了搜索延迟但未考虑索引动态性；两者的结合是自然的研究方向
- **具体的 open problems**：PipeSearch 的投机 I/O 在分区索引动态变化时是否仍然有效？如何在 APS 的几何概率模型中考虑分区正在被 split/merge 的情况？

### 5. 跨平台 XPU 调度策略研究

- **方向描述**：基于 XSched 的 XQueue 抽象，研究 NPU/ASIC 上 LLM 推理的多任务调度策略
- **为什么小团队能做**：XSched 已开源且支持 10 种 XPU，Lv1 适配仅需数百行代码；Intel AI PC NPU 等设备价格可承受
- **哪些论文指向了这个空白**：XSched 提供了框架但调度策略较简单；Understanding Stragglers 中的 what-if 分析方法论可迁移到推理调度
- **具体的 open problems**：如何在 NPU 上实现 LLM prefill/decode 的优先级调度？XQueue 抽象能否扩展到支持 KV cache 的保存/恢复？
