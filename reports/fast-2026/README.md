# USENIX Conference on File and Storage Technologies (FAST) 2026 论文概览

> 共 44 篇论文 | 生成日期: 2026-04-08

---

## 论文分类索引

### AI 存储基础设施（8 篇）

#### [[fast2026-hu-shipeng|Bidaw: Enhancing Key-Value Caching for Interactive LLM Serving via Bidirectional Computation–Storage Awareness]]
- **作者**：Shipeng Hu et al.
- **要解决的问题**：交互式 LLM 服务中，两级存储 KV 缓存系统的计算引擎与存储层相互不感知，导致 I/O 引发请求阻塞和性能层命中率极低（仅约 20%），响应延迟最高增加 3.8×。
- **核心贡献**：提出 Bidaw，通过 I/O 感知调度和基于模型回答长度预测的驱逐策略，实现最高 3.58× 延迟降低和 1.83× 吞吐提升。
- **关键发现/观点**：在交互式对话中，用户下次 KV 访问的加权重用距离下界与上一轮模型回答长度呈强正相关（Spearman 系数 0.94–0.98），因为更长回答需要用户更多阅读时间，从而增大重用距离。

#### [[fast2026-liu-yang|CacheSlide: Unlocking Cross Position-Aware KV Cache Reuse for Accelerating LLM Serving]]
- **作者**：Yang Liu et al.
- **要解决的问题**：Agent 场景中固定 prompt 段在不同推理步骤中绝对位置漂移导致位置编码失配（PMKD），现有 PDC 和 PIC 方案均无法高效复用 KV cache。
- **核心贡献**：提出 RPDC 范式和 CacheSlide 系统，TTFT 降低 3.11–4.3×，吞吐量提升 3.5–5.8×。
- **关键发现/观点**：Agent 工作流中可复用段之间的相对顺序始终固定，仅绝对位置因动态段长度变化而偏移；使用低位置敏感性编码（CoPE）可将位置偏差控制在极小范围内，实现近无损复用。

#### [[fast2026-liu-weijie|AdaCheck: An Adaptive Checkpointing System for Efficient LLM Training with Redundancy Utilization]]
- **作者**：Weijie Liu et al.
- **要解决的问题**：LLM 分布式训练中，不同并行策略组合产生复杂多样的状态冗余模式，现有 checkpointing 系统无法识别和利用这些冗余，checkpoint 体积过大、保存频率过低。
- **核心贡献**：通过 tensor redundancy 抽象统一建模并行训练状态冗余，将 checkpoint 体积缩减 6–896×，实现每步一 checkpoint，故障浪费时间缩减最高 88.93×。
- **关键发现/观点**：并行训练中大量模型状态存在跨 worker 冗余（空间维度），且混合精度训练中相邻迭代间 checkpoint 差异仅为半精度梯度（时间维度，大小为完整状态的 1/7），可同时从两个维度大幅压缩 checkpoint 体积。

#### [[fast2026-liu-yubo|Accelerating Model Loading in LLM Inference by Programmable Page Cache]]
- **作者**：Yubo Liu et al.（华为）
- **要解决的问题**：LLM 推理冷启动时，内核原生预取策略无法利用 SSD 高并发能力（实测平均带宽仅峰值 17%），模型加载成为推理启动的主要瓶颈。
- **核心贡献**：提出 PPC 框架和 MAIO 优化策略，通过可中断激进预取、XPU 亲和性加载和 Burn-after-Reading 驱逐，模型加载延迟降低最高 79%。
- **关键发现/观点**：相同 LLM 推理服务（相同模型、相同并行配置）的模型加载 I/O 模式完全可复现，可预构建 I/O 模板在不修改推理框架的前提下精确感知 I/O 行为并实现自适应缓存优化。

#### [[fast2026-hao|Fast Cloud Storage for AI Jobs via Grouped I/O API with Transparent Read/Write Optimizations]]
- **作者**：Yingyi Hao et al.
- **要解决的问题**：AI 训练/推理作业对存储带宽要求极高，分离式架构下 storage fabric 带宽是硬瓶颈，提升存储带宽成本按比例增长。
- **核心贡献**：AITURBO 通过 grouped I/O API 获取 AI 作业语义，利用空闲 compute fabric 和 host DRAM 作为存储中转缓冲，checkpoint 写入快 3.9–58.8×，已部署于华为生产云。
- **关键发现/观点**：AI 作业中主机 DRAM 和高带宽 compute fabric 在大部分时间空闲，可被存储系统用作快速中转缓冲区；通过简单的 grouped I/O API，存储层可获得足够语义自动推导出优于应用层手动优化的 I/O 计划。

#### [[fast2026-desai|Preparation Meets Opportunity: Enhancing Data Preprocessing for ML Training With Seneca]]
- **作者**：Omkar Desai et al.
- **要解决的问题**：GPU 算力增长使 ML 训练中数据存储与摄入管线成为瓶颈，多并发训练任务独立预处理导致大量重复计算。
- **核心贡献**：Seneca 通过基于性能模型的缓存分区和机会主义数据采样，最高将 DSI 吞吐量提升 3.45×，多任务 makespan 减少 45.23%。
- **关键发现/观点**：随机采样的统计特性使缓存命中率可被精确估算，且训练任务的采样顺序不必严格遵循预定伪随机序列——用缓存中已有的样本替代未缓存样本，可在不影响训练精度的前提下提高缓存命中率。

#### [[fast2026-zeng|GPU Checkpoint/Restore Made Fast and Lightweight]]
- **作者**：Shaoxun Zeng et al.（清华大学）
- **要解决的问题**：现有系统级 GPU C/R 方案无法同时实现低延迟、低运行时开销和增量 checkpoint。
- **核心贡献**：提出 GCR，通过 hybrid C/R 和 shadow execution + dirty template 增量 checkpoint，延迟降低 63.6–72.1%，运行时开销 <1%，增量 checkpoint 大小减少 86.6%。
- **关键发现/观点**：GPU kernel 的 dirty buffer 地址可表达为 kernel 参数的函数，因此可通过符号执行生成 dirty template，在 CPU 上以微秒级开销并行识别 dirty buffer，完全不影响 GPU 执行路径。

#### [[fast2026-zheng|SolidAttention: Low-Latency SSD-based Serving on Memory-Constrained PCs]]
- **作者**：Xinrui Zheng et al.（上海交通大学）
- **要解决的问题**：内存受限 PC 上长上下文 LLM 推理时，KV cache 远超可用内存，SSD offloading 因动态 attention sparsity 产生细粒度不规则随机 I/O，与 SSD 特性严重冲突。
- **核心贡献**：提出 SolidAttention，通过 KV Interleaving、Speculative Prefetcher 和 DAG-based Scheduler，实现 2.4×–3.1× 加速，KV cache 内存节省最高 62×。
- **关键发现/观点**：跨层连续迭代间的 block selection 相似度约 81%，可基于历史结果投机预取下一层所需 KV blocks；K/V 向量交错排列可在不损精度的前提下将传输粒度翻倍、I/O 操作数减半。

### SSD / Flash 与 I/O 栈优化（7 篇）

#### [[fast2026-ahn|ScaleSwap: A Scalable OS Swap System for All-Flash Swap Arrays]]
- **作者**：Taehwan Ahn et al.
- **要解决的问题**：Linux swap 系统在 all-flash swap array 上存在严重扩展性瓶颈，随核数和 SSD 数增加性能几乎不提升，根因是 all-to-all 模型导致的锁争用。
- **核心贡献**：ScaleSwap 将 Linux swap 重构为 core-centric 的 one-to-one 模型，在 128 核 + 8 NVMe SSD 环境下实现 3.4× 吞吐提升和 11.5× 延迟降低。
- **关键发现/观点**：Linux swap 的扩展性瓶颈根源在于 all-to-all 的资源管理模型；将 swap 资源按核独占分配，采用 one-to-one 模型，可从根本上消除锁争用，释放 all-flash swap array 的全部带宽。

#### [[fast2026-pan|UnICom: A Universally High-Performant I/O Completion Mechanism for Modern Computer Systems]]
- **作者**：Riwei Pan et al.
- **要解决的问题**：中断的 sleep/wake-up 开销占 I/O 延迟约 33%，而轮询在与计算密集型线程混合时会抢占 CPU；现有方案无法在低延迟和高 CPU 效率之间同时达到最优。
- **核心贡献**：UnICom 通过 TagSched、TagPoll 和 SKIP 三个组件，在内核空间统一实现轮询低延迟与中断高效性，混合负载下比 BypassD 提升 I/O IOPS 高达 88.8%。
- **关键发现/观点**：syscall 模式切换延迟（~150ns）相比磁盘 I/O 延迟（~4000ns）可忽略不计，因此可以在内核空间实现高效 I/O 完成机制同时绕过大部分 I/O 栈，无需完全 bypass kernel。

#### [[fast2026-seo|DPAS: A Prompt, Accurate and Safe I/O Completion Method for SSDs]]
- **作者**：Dongjoo Seo et al.
- **要解决的问题**：现有混合轮询方法基于 epoch 统计的睡眠时长预测对延迟突变响应慢、精度差，无法区分设备延迟变化与 OS 调度引起的过度睡眠。
- **核心贡献**：DPAS 用最近两次 I/O 的二元睡眠结果驱动乘法自适应控制器，动态切换 polling/hybrid polling/interrupt 三种模式，在 CPU 竞争和 I/O 干扰并存场景下优于所有现有方法。
- **关键发现/观点**：I/O 完成检测的睡眠结果只有两种（undersleep 或 oversleep），利用最近两次 I/O 的二元结果对就能以极低开销实时跟踪延迟下包络线，天然区分设备延迟变化与预测误差。

#### [[fast2026-song|Characterizing and Emulating FDP SSDs with WARP]]
- **作者**：Inho Song et al.
- **要解决的问题**：FDP NVMe 接口在不同厂商 SSD 上效果差异巨大且不可预测，商用设备内部参数不透明，缺乏系统性跨设备研究和开放研究平台。
- **核心贡献**：提出 WARP（首个开源 FDP SSD 仿真器），首次跨设备表征揭示了 Noisy RUH 和 Save Sequential 两个新现象。
- **关键发现/观点**：FDP 的 WAF 收益不是接口本身的固有属性，而是工作负载生命周期与 RUH 隔离对齐程度、厂商固件策略三者交互作用的涌现结果；当出现 Noisy RUH 干扰或 Save Sequential 对抗模式时，FDP 收益完全消失。

#### [[fast2026-kim-jungae|Unleashing Zoned UFS: Cross-Layer Optimizations for Next-Generation Mobile Storage]]
- **作者**：Jungae Kim et al.
- **要解决的问题**：Zoned UFS 在商用智能手机部署面临写缓冲区 SRAM 需求超移动预算、跨层写入顺序违反、大 zone GC 开销过重三大挑战。
- **核心贡献**：首次在 Google Pixel 10 Pro 量产部署 ZUFS，碎片化条件下维持 2× 以上写吞吐优势，游戏加载提速 14%，滑动 jank 降低 57%。
- **关键发现/观点**：ZUFS 的性能潜力必须跨越整个移动存储栈（设备固件、SCSI/UFS 驱动、block layer、F2FS、Android 框架）协同优化；细粒度 slot 动态共享可替代静态缓冲区分配，SGBM 硬件开销仅占芯片面积 0.4%。

#### [[fast2026-kim-jeeyun|DOGI: Data Placement with Oracle-Guided Insights for Log-Structured Systems]]
- **作者**：Jeeyun Kim et al.
- **要解决的问题**：Log-structured 存储系统中现有数据放置技术在 WAF 优化上与理论最优存在显著差距。
- **核心贡献**：DOGI 通过近最优 oracle 基线揭示瓶颈，设计混合预测 + ML-assisted GC 块重定位 + 动态 group 配置，平均降低 WAF 15.5%，推理延迟仅 0.39μs。
- **关键发现/观点**：预测模型精度与最优 group 数量存在强耦合——group 越多对预测准确率要求越高；热/冷数据行为规律明显可用简单启发式处理，只需将 ML 算力集中在中间温度数据块上。

#### [[fast2026-zhan|Rearchitecting Buffered I/O in the Era of High-Bandwidth SSDs]]
- **作者**：Yekang Zhan et al.
- **要解决的问题**：PCIe 5.0 时代 SSD 带宽达 10+ GB/s，page cache 管理开销已超过其收益，成为 buffered I/O 写性能瓶颈。
- **核心贡献**：提出 WSBuffer，引入大粒度 scrap-page 结构替代 page cache 写缓冲角色，相比主流文件系统实现最高 3.91× 吞吐提升和 82.80× 延迟降低。
- **关键发现/观点**：在高带宽 SSD 时代，内存相对 SSD 的带宽优势已不足以抵消 page cache 管理开销；只需用内存缓冲 SSD 不擅长处理的小写入和非对齐写入，就能同时获得 buffered I/O 的编程便利性和 direct I/O 的高带宽。

### 云存储与虚拟化（7 篇）

#### [[fast2026-baron|McQueen: Apple's Geo-Distributed Object Store at Exabyte Scale]]
- **作者**：Benjamin Baron et al.（Apple）
- **要解决的问题**：McQueen 1.0 在 exabyte 规模下存储成本过高（复制因子 2.40）、store 生命周期管理复杂、元数据系统无法全局扩展。
- **核心贡献**：McQueen 2.0 通过五区域 XOR-5 分段编码与 LRC 结合，将复制因子从 2.40 降至 1.50，保持 "11 nines" 持久性 SLA。
- **关键发现/观点**：使用 bitwise XOR 将对象切分为 4 数据段 + 1 校验段分布到 5 个区域，可在仅维持 RF=1.50 的情况下实现单区域故障容忍，相比全量跨区域复制（RF=2.0）大幅降低成本。

#### [[fast2026-chen|How Soon is Now? Preloading Images for Virtual Disks with ThinkAhead]]
- **作者**：Xinqi Chen et al.
- **要解决的问题**：云 EBS lazy loading 导致 VD 创建时首次访问未加载数据块产生显著尾延迟（P99 达 7s），贡献了 39.35% 的 slow I/O 事件。
- **核心贡献**：ThinkAhead 利用同镜像 VD 的高度访问相似性主动预加载数据块，hit rate 提升最高 7.27×，尾延迟降低最高 98.7%。
- **关键发现/观点**：从同一镜像创建的 VD 在启动阶段展现出极高的访问模式相似性（84.8% 的公共镜像 cosine similarity > 0.9），且初始加载阶段仅访问极小比例的 LBA 空间。

#### [[fast2026-yang|Here, There and Everywhere: The Past, the Present and the Future of Local Storage in Cloud]]
- **作者**：Leping Yang et al.（阿里巴巴）
- **要解决的问题**：云虚拟化环境中如何让高性能 NVMe SSD 充分发挥性能，同时兼顾裸金属支持、CPU 效率、弹性和可用性。
- **核心贡献**：系统回顾阿里云本地存储三代演进，RISTRETTO 通过 ASIC/SoC 协同设计在不消耗宿主机 CPU 的前提下实现近物理性能（单 VD 900K IOPS）。
- **关键发现/观点**：ASIC 擅长固定逻辑高吞吐处理，SoC 擅长可编程灵活逻辑；将两者协同设计在同一 PCIe 扩展板上，可同时获得低成本高效率和灵活性，无需占用宿主机 CPU。

#### [[fast2026-zhao|"Range as a Key" is the Key! Fast and Compact Cloud Block Store Index with RASK]]
- **作者**：Haoru Zhao et al.（上海交通大学）
- **要解决的问题**：EBS-index 以单个 block 为粒度建立索引，海量条目消耗约 57.1% 节点内存，制约物理存储利用率。
- **核心贡献**：RASK 采用 ART trie + log-structured leaf 混合结构，通过 ablation-based search 和 workload-aware merge/resplit，内存节省最高 98.9%、吞吐提升最高 37.8×。
- **关键发现/观点**：阿里云 EBS trace 显示 65.0%–81.5% 的写操作属于时间相近、空间连续的连续写序列（CW），>85.4% 的读操作从 CW 起始位置开始；以 block range 而非单个 block 作为索引键，理论上可减少 58.4%–91.1% 的索引条目。

#### [[fast2026-wang|Cost-efficient Archive Cloud Storage with Tape: Design and Deployment]]
- **作者**：Qing Wang et al.
- **要解决的问题**：磁带库 drive 数量极少（4 个 drive 服务 1000 盒磁带），频繁换带导致 drive thrashing 和有效带宽减半。
- **核心贡献**：TapeOBS 通过全异步 HDD 缓冲池、lifetime-based placement、batched EC 和请求重排，已存储数百 PB 数据，TCO 相比 HDD 方案降低约 5×。
- **关键发现/观点**：归档存储 SLA 允许小时级延迟，所有磁带读写都可以异步化；异步化后可在 HDD 缓冲池中积攒并批量调度请求，使磁带访问模式与其硬件特性完全对齐。

#### [[fast2026-qiu|RosenBridge: A Framework for Enabling Express I/O Paths Across the Virtualization Boundary]]
- **作者**：Shi Qiu et al.
- **要解决的问题**：XRP、GDS 等 near-data processing 优化依赖 host kernel NVMe driver hook，无法穿越虚拟化边界，VM 内应用完全无法使用；虚拟化存储栈软件开销高达 87%。
- **核心贡献**：RosenBridge 通过 virtio-ndp 设备将 guest 的 uBPF NDP 程序 offload 到 host 用户态 QEMU，吞吐量最高提升 461.8%、CPU 消耗降至 10%。
- **关键发现/观点**：将 NDP 优化 offload 到 host 用户态（QEMU 进程）而非 host kernel，既能消除多次存储栈遍历和 VM-exit 开销，又比 kernel offload 更安全——uBPF 在用户态沙箱中运行，天然继承进程级隔离。

#### [[fast2026-ye|Cache-Centric Multi-Resource Allocation for Storage Services]]
- **作者**：Chenhao Ye et al.（UW-Madison）
- **要解决的问题**：多租户存储系统中，现有多资源分配框架（如 DRF）假设资源需求独立，无法处理缓存这一非线性资源及其与其他资源需求的关联。
- **核心贡献**：HARE 算法首个将缓存纳入多资源分配框架，通过两阶段 harvest-redistribute 利用租户间缓存敏感度异质性，在 HopperKV 上最高提升 1.9× 吞吐。
- **关键发现/观点**：不同租户对缓存的敏感度存在异质性——将缓存从不敏感租户转移到敏感租户，后者因 miss ratio 下降会释放 I/O、网络等其他资源，释放量多于补偿量，差值可重新分配以整体提升吞吐。

### 文件系统（6 篇）

#### [[fast2026-huang|Towards Condensed and Efficient Read-Only File System via Sort-Enhanced Compression]]
- **作者**：Hao Huang et al.
- **要解决的问题**：只读压缩文件系统中块划分导致不相似数据混入同一压缩块，字典压缩无法跨块消除冗余，压缩率显著低于理论上限。
- **核心贡献**：RubikFS 在镜像构建流程中引入相似性排序，在 6 个开源镜像上实现最高 42.60% 压缩率提升和 70.70% 读放大缓解。
- **关键发现/观点**：块压缩的瓶颈来自字典压缩无法跨块发现冗余；如果压缩前按相似性对数据 chunk 排序聚类，使相似 chunk 落入同一压缩块，效果可逼近直接压缩整个镜像。

#### [[fast2026-jia|CETOFS: A High-Performance File System with Host-Server Collaboration for Remote Storage]]
- **作者**：Wenqing Jia et al.（中科院计算所）
- **要解决的问题**：Disaggregated NVMe SSD 场景下，内核文件系统软件栈延迟占总延迟 65–66%，且 host 端并发控制被网络延迟放大。
- **核心贡献**：CETOFS 将数据路径移至用户态，权限检查、并发控制和 redo logging 卸载到远程服务器端，单线程延迟降低最多 52%，并发共享文件写吞吐提升最高 19×。
- **关键发现/观点**：远程存储服务器端拥有可用计算能力，将权限检查、并发控制和日志写入卸载到 target 端后 host 到 target 之间只需一次数据传输，从根本上消除多次网络往返。

#### [[fast2026-liu-qingyuan|Sharpen the Spec, Cut the Code: A Case for Generative File System with SYSSPEC]]
- **作者**：Qingyuan Liu et al.（上海交通大学）
- **要解决的问题**：文件系统开发中 82.4% 的 commit 用于 bug 修复和维护，直接用自然语言 prompt 引导 LLM 生成文件系统不可行。
- **核心贡献**：SYSSPEC 用三层结构化规约引导 LLM 生成和演进文件系统，原型 SPECFS 在强模型上达到 100% 模块生成准确率，成功集成 10 个 Ext4 特性，开发效率提升 3–5×。
- **关键发现/观点**：用借鉴自形式化方法的结构化规约（Hoare logic 前置/后置条件、Rely-Guarantee 接口契约）替代自然语言 prompt，可为 LLM 提供无歧义蓝图，使生成和演进复杂文件系统成为可能。

#### [[fast2026-wang-li|CoFS: A Filesystem for Fast Container Startup]]
- **作者**：Li Wang et al.
- **要解决的问题**：容器冷启动中镜像拉取占 76% 时间，on-demand pulling 方案因 FUSE 用户态路径遍历多次上下文切换带来严重性能开销。
- **核心贡献**：CoFS 利用容器镜像只读固定特性，在镜像构建时预构造 MPHF，使内核空间能以 O(1) 完成文件查找，lookup 性能提升 73%–86%。
- **关键发现/观点**：容器镜像是一次构建、只读固定的文件系统树，文件集合在构建时已完全确定；可预先构造 MPHF 将元数据查找完全搬到内核空间，彻底消除 FUSE 用户态 lookup 往返。

#### [[fast2026-park|Lockify: Understanding Linux Distributed Lock Management Overheads in Shared Storage]]
- **作者**：Taeyoung Park et al.
- **要解决的问题**：共享磁盘文件系统（GFS2、OCFS2）在低竞争场景下随节点数增加文件创建吞吐量骤降高达 86%，根源在于 DLM 跨节点通信延迟。
- **核心贡献**：Lockify 通过 self-owner notification 和异步 ownership 管理，在 GFS2 上最高实现 6.4× 目录创建吞吐提升。
- **关键发现/观点**：创建新文件或目录时，对应的锁对象尚不存在，不需要查询远程 directory node 来确定 owner——创建者可以直接声明自身为 owner，从而消除不必要的跨节点通信往返。

#### [[fast2026-gupta|Advancing Data Integrity in Linux]]
- **作者**：Anuj Gupta et al.（Samsung）
- **要解决的问题**：Linux 数据完整性支持存在三个核心缺口：Flexible PI 放置、用户态 PI 接口、以及文件系统利用设备 PI 能力。
- **核心贡献**：在 BTRFS 上实现 52% 写放大缩减和 23% SSD 寿命延长，在 XFS 上首次引入数据 checksum，部分已合入 Linux 6.9/6.14 内核。
- **关键发现/观点**：PI-capable 设备已在每个 LBA 旁提供了 per-block metadata 字段，文件系统可直接利用这一硬件能力生成和验证 checksum，无需维护独立的、开销昂贵的 checksum 元数据结构。

### 分布式存储与数据管理（5 篇）

#### [[fast2026-bian|Discard-Based Garbage Collection for Distributed Log-Structured Storage Systems in ByteDance]]
- **作者**：Runhua Bian et al.（字节跳动 & 清华大学）
- **要解决的问题**：Append-only 分布式存储的 compaction-only GC 存在写放大与空间放大之间的根本性两难权衡，在 exabyte 规模下导致每月数百万美元额外 TCO。
- **核心贡献**：DisCoGC 引入 discard 机制直接回收大块连续垃圾空间，在生产集群实现约 20% TCO 降低且不影响前台性能。
- **关键发现/观点**：ByteDance 工作负载中超过一半的写操作修改大于 256 KiB 的连续范围且覆写间隔仅数秒，这导致 LogFile 中出现大段连续过时数据，可通过 discard 直接回收而无需搬移有效数据。

#### [[fast2026-ren|Holistic and Automated Task Scheduling for Distributed LSM-tree-based Storage]]
- **作者**：Yuanming Ren et al.
- **要解决的问题**：分布式 LSM-tree KV 存储中，即使请求频率均衡，节点间读延迟差异仍高达 4.24×；后台 compaction 与前台读请求的资源竞争在秒级造成频繁延迟尖峰。
- **核心贡献**：HATS 通过粗粒度读任务分配、细粒度协调和自适应 compaction 调度三层协同，在 Facebook 工作负载上实现 2.90× 吞吐提升和 88.7% P999 尾延迟降低。
- **关键发现/观点**：延迟波动根源在于分布层（前台）和存储层（后台 compaction）任务的紧耦合；细粒度 unified score 机制使路由自动偏向 compaction 状态良好的节点，无需显式感知 compaction 状态。

#### [[fast2026-hu|PolarStore: High-Performance Data Compression for Large-Scale Cloud-Native Databases]]
- **作者**：Qingda Hu et al.（阿里云）
- **要解决的问题**：大规模云原生数据库的存储压缩面临根本性矛盾——软件压缩索引管理开销大，硬件压缩灵活性不足。
- **核心贡献**：PolarStore 通过软件-硬件协同双层压缩架构，在超过 100PB 生产部署中实现 3.55 压缩比和约 60% 存储成本削减。
- **关键发现/观点**：软件层将数据压缩到 4KB 对齐块，硬件层（CSD）利用已有 FTL GC 机制将 4KB 块进一步压缩到字节级——字节级索引的复杂性完全由硬件 FTL 免费承担。

#### [[fast2026-wang-shuyang|FailureMiner: A Joint Key Decision Mining Scheme for Practical SSD Failure Prediction and Analysis]]
- **作者**：Shuyang Wang et al.
- **要解决的问题**：SSD 故障预测中数据极度不平衡导致误报率高，属性级特征选择会误删有用属性组合，现有可解释性方法无法捕捉多属性联合的细粒度故障模式。
- **核心贡献**：FailureMiner 通过边界保留下采样和联合关键决策集提取，precision 提升至 82.2%（提升 38.6%），已在腾讯数据中心部署超 1 年。
- **关键发现/观点**：SSD 故障模式往往体现在多个监控属性的联合异常中，从决策树中提取联合关键决策（多阈值组合）比属性级分析更能准确捕捉故障模式；健康样本中靠近故障边界的样本对模型训练至关重要。

#### [[fast2026-zhang-kai|An Efficient Cloud Storage Model with Compacted Metadata Management for Performance Monitoring Timeseries Systems]]
- **作者**：Kai Zhang et al.（CUHK）
- **要解决的问题**：云端性能监控时序系统将本地存储模型迁移到对象存储后，metadata 高度冗余（>70% tag 重复）和 read amplification 严重。
- **核心贡献**：CloudTS 采用元数据-数据分离的双结构设计，通过 Patricia Trie 去重和 TMMC 压缩索引，相比 Cortex 平均降低 36% 查询延迟。
- **关键发现/观点**：时序系统中元数据（tag）和数据的访问模式有根本差异——元数据被频繁访问且高度冗余；将两者分离管理并对元数据进行全局去重和压缩索引，可同时减少 read amplification 和存储开销。

### CXL 与内存系统（3 篇）

#### [[fast2026-an|Xerxes: Extensive Exploration of Scalable Hardware Systems with CXL-Based Simulation Framework]]
- **作者**：Yuda An et al.（北京大学）
- **要解决的问题**：支持 CXL 3.0+ 完整特性的硬件尚不可用，现有仿真工具无法准确建模 PBR 拓扑和 DMC 设备端一致性管理，rack 级 CXL 系统的设计空间无法被探索。
- **核心贡献**：Xerxes 首个能全面仿真 CXL 3.1 关键特性，采用互连层与设备层解耦的双层架构，验证误差低至 0.1%–10%。
- **关键发现/观点**：CXL 3.0+ 从层次化主机中心转变为图结构 peer-to-peer 架构，仿真框架必须将互连层与设备层解耦，用图建模拓扑、用 peer 模型建模设备，才能准确预测新架构性能。

#### [[fast2026-yoon|Cylon: Fast and Accurate Full-System Emulation of CXL-SSDs]]
- **作者**：Dongha Yoon et al.（Virginia Tech）
- **要解决的问题**：CXL-SSD 研究缺乏同时具备 full-stack 执行、近 bare-metal 速度和准确设备建模的模拟平台；QEMU 每次访问约 15µs vs 真实 sub-µs。
- **核心贡献**：Cylon 首个基于 FEMU 的 CXL-SSD full-system 模拟器，通过 Dynamic EPT Remapping 让 cache hit 走直通路径，cache hit 延迟较 QEMU 提升约 92×。
- **关键发现/观点**：CXL-SSD 性能本质上是双模态的（cache hit sub-µs，cache miss tens-of-µs）；通过动态操纵 EPT 权限位，可让 cache hit 走"直通"路径、cache miss 走"陷入"路径，忠实再现延迟不对称性。

#### [[fast2026-wei|DMTree: Towards Efficient Tree Indexing on Disaggregated Memory via Compute-side Collaborative Design]]
- **作者**：Guoli Wei et al.
- **要解决的问题**：内存解耦架构上现有 range index 在 RDMA 资源利用上存在根本权衡：B+-tree 有 ~32× 读放大导致带宽瓶颈，ART 的大量小粒度 RDMA 请求导致 IOPS 瓶颈。
- **核心贡献**：DMTree 将 fingerprint 存储和 lock 操作从内存服务器卸载到计算服务器之间的空闲 RDMA 资源，最高实现 5.7× 性能提升。
- **关键发现/观点**：内存服务器的 RDMA 网络资源容易成为瓶颈，而计算服务器之间的 RDMA 资源始终未饱和；可将数据定位和锁操作卸载到计算服务器，利用计算侧空闲网络资源缓解存储侧瓶颈。

### 纠删码与修复优化（2 篇）

#### [[fast2026-cheng|LESS is More for I/O-Efficient Repairs in Erasure-Coded Storage]]
- **作者**：Keyun Cheng et al.（CUHK）
- **要解决的问题**：现有修复友好型纠删码无法同时兼顾减少修复 I/O 量、减少 I/O seek 次数、以及在数据块和校验块间均衡降低修复开销。
- **核心贡献**：LESS 提出分层扩展子条带构造方法，以小且可配置的 sub-packetization 同时减少修复 I/O 和 seek，单块修复时间比 RS 减少最高 50.8%。
- **关键发现/观点**：修复性能同时取决于修复 I/O 量和 I/O seek 数，追求理论最优修复 I/O 的指数级 sub-packetization 引入的大量 seek 会抵消数据访问量减少的收益；用小而可配置的 sub-packetization 实现接近最优的修复 I/O 比追求理论最优更有实际价值。

#### [[fast2026-niu|DRBoost: Boosting Degraded Read Performance in MSR-Coded Storage Clusters]]
- **作者**：Xiao Niu et al.（清华大学）
- **要解决的问题**：MSR 码因大 chunk 尺寸与实际对象尺寸严重不匹配，仅支持全 chunk 重建，降级读延迟比正常读高出 1–2 个数量级。
- **核心贡献**：DRBoost 通过部分 chunk 重建、重建友好编码布局和无碎片存储布局，将降级读延迟降低 1–2 个数量级，使 MSR 码降级读性能优于 RS 码 1.62–3.12×。
- **关键发现/观点**：MSR 码的 sub-stripe 具有独立容错能力，且部分 chunk 重建过程中存在 sub-stripe reuse 和 request reuse 两种重用机会，可大幅减少修复带宽。

### 文件同步（2 篇）

#### [[fast2026-zhang-zhihao-parasync|ParaSync: Exploiting Fine-Grained Parallelism for Efficient File Synchronization]]
- **作者**：Zhihao Zhang et al.（厦门大学）
- **要解决的问题**：CDC 文件同步的分块（占总时间 49.5%–75.1%）、块匹配、增量重建三个阶段均存在严重并行瓶颈。
- **核心贡献**：ParaSync 利用 CRC32C 代数线性性质实现近线性分块扩展，设计流式块匹配和绝对偏移 patch，LAN 下实现 2.3×–3.7× 端到端加速。
- **关键发现/观点**：CRC32C checksum 具有线性代数性质，合并块的 checksum 可通过组合子块 checksum 高效推导，无需重新读取原始数据，使 checksum 计算与块边界确定解耦，实现真正的并行分块。

#### [[fast2026-zhang-zhihao|SkySync: Accelerating File Synchronization with Collaborative Delta Generation]]
- **作者**：Zhihao Zhang et al.（厦门大学）
- **要解决的问题**：Delta sync 的校验和计算和分块搜索占总同步时间的 71.2%–93.7%，是跨云同步的主要瓶颈。
- **核心贡献**：SkySync 复用存储层已维护的校验和元数据避免重复计算，利用 CRC32C 线性性质组合变长分块校验和，在 BTRFS 上计算开销降低最高 89.3%。
- **关键发现/观点**：现代存储层为数据完整性、去重等目的已维护丰富的校验和元数据；这些元数据可被复用于 delta 生成，从而避免重复计算——存储层元数据读取比重新计算快数倍甚至数十倍。

### 存储缓存与分层（2 篇）

#### [[fast2026-tu|Getting the MOST out of your Storage Hierarchy with Mirror-Optimized Storage Tiering]]
- **作者**：Kaiwei Tu et al.（UW-Madison）
- **要解决的问题**：性能差距缩小的现代异构存储层级中，纯 Tiering 收敛慢写放大严重，纯 Mirroring/Caching 浪费容量或无法处理写密集负载。
- **核心贡献**：MOST 通过对少量热数据跨设备镜像并用概率路由调整负载，在 10 秒内适应工作负载变化（vs 迁移方案 800 秒），比 Colloid 提升 1.24× 吞吐。
- **关键发现/观点**：只需对少量热数据进行跨设备镜像，就能通过即时的概率路由调整实现负载均衡——路由调整是即时的（改变概率即可），而迁移是昂贵且缓慢的。

#### [[fast2026-meignan-masson|uCache: A Customizable Unikernel-based IO Cache]]
- **作者**：Ilya Meignan-Masson et al.（TU Munich）
- **要解决的问题**：OS 级 IO 缓存性能差且缺乏灵活性，用户态缓存实现复杂且与应用深度耦合——二者间存在性能-灵活性-复杂度三角困境。
- **核心贡献**：uCache 基于 OSv unikernel 实现，缓存插入比 mmap 快最高 55×，随机查找快 46–78×，vmcache TPC-C 仅比专用内核模块慢 3%。
- **关键发现/观点**：OS 级缓存与用户态缓存的差距根源不在缓存算法，而在于传统 OS 架构中应用与内核的隔离边界；unikernel 将两者共置于单一地址空间，消除系统调用和上下文切换开销，同时允许应用直接定制缓存机制。

### 磁盘向量检索（1 篇）

#### [[fast2026-guo|OdinANN: Direct Insert for Consistently Stable Performance in Billion-Scale Graph-Based Vector Search]]
- **作者**：Hao Guo, Youyou Lu（清华大学）
- **要解决的问题**：DiskANN 的 buffered insert 在 merge 阶段导致严重搜索性能波动（中位延迟升至 1.54×）、极高内存消耗和过长 merge 时间。
- **核心贡献**：OdinANN 用 direct insert 替代 buffered insert，通过 GC-free update combining 和 approximate concurrency control，实现稳定搜索性能和 DiskANN 29.3% 的内存消耗。
- **关键发现/观点**：Buffered insert 的 batch merge 并不能有效降低插入开销，因为每个向量的邻居搜索本质上无法批处理；既然 batch 收益有限，不如逐条直接插入磁盘索引，将开销均匀分摊避免 merge 性能波动。

### 可信存储（1 篇）

#### [[fast2026-xu|MlsDisk: Trusted Block Storage for TEEs Based on Layered Secure Logging]]
- **作者**：Erci Xu et al.（上海交通大学）
- **要解决的问题**：TEE 环境下安全虚拟磁盘需同时保证机密性、完整性、新鲜性和一致性（CIFC），但现有 MHT 方案写放大严重，朴素日志方案无法安全支持索引和 GC。
- **核心贡献**：MlsDisk 将复杂存储分解为四层模块化抽象，每层构建在下层 CIFC 兼容原语之上，在等价安全保证下实现 7.3×–21.1× 写性能提升。
- **关键发现/观点**：日志结构存储中索引和 GC 难以保证安全性的根因是数据与元数据紧密耦合；将其分解为多层次化抽象，每层仅暴露 CIFC 兼容 API，可将安全推理限制在每个独立层内。

---

## 研究趋势分析

**AI 存储基础设施成为 FAST 2026 最大主题。** 8 篇论文（18%）直接服务于 LLM 训练与推理，涵盖 KV cache 管理（Bidaw、CacheSlide、SolidAttention）、checkpoint 优化（AdaCheck、GCR）、模型加载加速（PPC）、AI 作业 I/O 优化（AITURBO）和数据预处理（Seneca）。这标志着存储社区已从被动支撑 AI 工作负载转向主动设计 AI-native 存储系统。值得注意的是，这些工作不仅优化吞吐量，更关注长尾延迟和稳定性——这反映了 AI 从实验走向生产部署的需求变化。

**工业界深度参与，系统论文越来越强调真实部署验证。** Apple（McQueen）、字节跳动（DisCoGC）、阿里云（PolarStore、RASK、RISTRETTO）、华为（AITURBO、PPC、TapeOBS）、腾讯（FailureMiner）、Google/Samsung（Zoned UFS on Pixel 10 Pro）等大厂贡献了大量具有 exabyte 级或数百 PB 级真实部署经验的论文。这些论文的价值不仅在于技术方案，更在于揭示了工业界面临的真实问题规模和约束条件。

**软硬件协同设计成为主流方法论。** PolarStore（软件 4KB 对齐 + CSD 字节级 FTL）、RISTRETTO（ASIC + SoC 协同）、Gupta（FS-PI 利用设备 PI 硬件）、Zoned UFS（跨设备固件到 Android 框架的全栈协同）都表明，纯软件优化的空间正在缩小，未来的存储系统创新越来越依赖于跨层次的协同设计。

**CXL 生态工具链正在成熟。** Xerxes 和 Cylon 分别提供了 CXL 3.1 功能仿真和 CXL-SSD 全系统模拟能力，DMTree 则展示了 CXL disaggregated memory 上的索引设计。这三篇论文反映出 CXL 研究正从概念验证走向系统性的架构探索，但硬件可用性仍是瓶颈。

**LLM 正在改变传统系统研究方法论。** SYSSPEC 用结构化规约引导 LLM 生成文件系统，DOGI 用 ML 辅助数据放置决策，FailureMiner 用决策树挖掘故障模式——AI 不仅是存储系统的服务对象，也在成为构建和优化存储系统的工具。这种双向关系可能重塑存储研究的工作方式。

---

## 小实验室的机会窗口

### 1. LLM KV Cache 管理策略研究

- **为什么小团队能做**：KV cache 管理本质上是调度和缓存策略问题，不需要大规模 GPU 集群，在单机或小规模集群上即可实验验证。Bidaw、CacheSlide、SolidAttention 都在中等规模硬件上完成了评估。
- **哪些论文指向了这个空白**：Bidaw 发现了回答长度与重用距离的相关性；CacheSlide 提出了 RPDC 范式但仅验证了 CoPE 编码；SolidAttention 的投机预取基于 81% 的跨层相似度假设。
- **具体的 open problems**：
  - 多轮对话中 KV cache 的最优驱逐策略是否存在统一的理论框架？不同对话模式（问答、代码生成、Agent 工具调用）下的最优策略差异有多大？
  - RPDC 范式在更多位置编码方案（RoPE variants、ALiBi）上的表现和适用边界是什么？
  - SSD offloading 场景下，attention sparsity 预测的误差容忍度和精度-性能权衡的 Pareto 前沿在哪里？

### 2. 文件同步与 Delta 压缩的代数优化

- **为什么小团队能做**：ParaSync 和 SkySync 都基于 CRC32C 的代数线性性质实现了突破，这类工作核心在于算法设计而非大规模工程。所需硬件仅为普通服务器，数据集可用公开 benchmark。
- **哪些论文指向了这个空白**：ParaSync 仅利用了 CRC32C 的线性性质；SkySync 仅复用了 BTRFS 的 checksum。
- **具体的 open problems**：
  - 其他 checksum/hash 函数（如 xxHash、BLAKE3 的 tree hash 模式）是否存在类似的可组合性质可用于加速同步？
  - 能否将 SkySync 的思路推广到更多存储层（ZFS、XFS reflink、对象存储的 ETag/checksum），建立通用的 metadata-reuse delta sync 框架？
  - CDC 分块的最优粒度如何根据网络带宽和延迟自适应调整？

### 3. 存储系统的 LLM 辅助开发与验证

- **为什么小团队能做**：SYSSPEC 已证明用结构化规约引导 LLM 生成文件系统是可行的，这条路线的关键在于规约设计而非算力。小团队可以选择特定子系统（如 log-structured 存储、缓存管理器）进行深入探索。
- **哪些论文指向了这个空白**：SYSSPEC 聚焦于文件系统，但其三层规约方法论可推广到其他存储子系统。
- **具体的 open problems**：
  - 结构化规约能否扩展到并发更复杂的系统（如分布式一致性协议、MVCC 存储引擎）？
  - 如何自动从现有代码和测试用例中提取规约，而非手动编写？
  - LLM 生成的存储系统代码如何进行形式化验证或 fuzzing，建立可信度？

### 4. I/O 完成机制与调度策略

- **为什么小团队能做**：UnICom 和 DPAS 都是 Linux 内核层面的优化，需要的硬件仅为 NVMe SSD + 多核服务器。核心贡献在于调度算法和控制论思想的应用，实验规模可控。
- **哪些论文指向了这个空白**：DPAS 的二元控制器思想简洁高效但仅验证了 SSD 场景；UnICom 的内核级集中式轮询在异构存储（SSD+PM+CXL）上的表现未知。
- **具体的 open problems**：
  - 在 CXL 设备（延迟介于 DRAM 和 SSD 之间）上，最优 I/O 完成机制是什么？现有中断/轮询/混合策略是否需要重新设计？
  - 能否将 DPAS 的自适应控制思想推广到更广泛的系统参数调优（如 compaction 调度、cache 分配）？

### 5. 纠删码的实际部署优化

- **为什么小团队能做**：LESS 和 DRBoost 都是编码理论与系统实现结合的工作，核心在于数学构造和系统设计，在小规模集群（8–16 节点）即可验证。
- **哪些论文指向了这个空白**：LESS 解决了 sub-packetization 与 seek 的权衡；DRBoost 解决了 MSR 码的部分重建。两者都未考虑 CXL/disaggregated memory 场景。
- **具体的 open problems**：
  - 在 CXL 内存池场景下，纠删码的修复策略如何利用 byte-addressable 特性？传统 block-level 修复是否过于粗糙？
  - 如何为 AI checkpoint 等具有已知结构（tensor shape、并行策略）的数据设计 workload-aware 纠删码？
