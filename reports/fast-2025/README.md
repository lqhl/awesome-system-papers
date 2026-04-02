# USENIX Conference on File and Storage Technologies (FAST) 2025 论文概览

> 共 36 篇论文 | 生成日期: 2026-04-02

---

## 论文分类索引

### AI/ML 系统存储（5 篇）

#### [[fast2025-chen-weijian-impress|IMPRESS: An Importance-Informed Multi-Tier Prefix KV Storage System for LLM Inference]]
- **作者**：Weijian Chen et al.
- **要解决的问题**：LLM 推理中大型 prefix KV cache 从 SSD 加载造成 I/O 瓶颈，占 TTFT 的 51-98%；识别重要 token 需要先加载所有 prefix key，形成先有鸡还是先有蛋的 I/O 困境
- **核心贡献**：三层（GPU/CPU/Disk）importance-aware KV 存储系统，通过 probe heads 以最小 I/O 识别重要 token，按重要性重排 KV 以减少读放大，实现 1.2-2.8× TTFT 降低
- **关键发现/观点**：同一 Transformer 层内的 attention heads 在重要 token 集合上有 >0.95 的 Jaccard 相似度，因此只需少量 probe heads 即可为所有 heads 识别重要 token，从根本上降低 importance identification 的 I/O 开销

#### [[fast2025-qin|MOONCAKE: Trading More Storage for Less Computation — KVCache-centric LLM Serving]]
- **作者**：Ruoyu Qin et al. (Moonshot AI)
- **要解决的问题**：LLM 推理中 prefill 和 decoding 的计算密度不匹配；KV cache 本地缓存容量不足；GPU 集群的非 GPU 资源（CPU/DRAM/NIC）大量闲置
- **核心贡献**：分布式 KV cache pool（MOONCAKE Store）+ prefill/decoding 分离集群 + cache-aware 调度，prefill 使用 chunked pipeline parallelism，decoding 通过 RDMA 从分布式 cache pool 消费 KV cache
- **关键发现/观点**：当 B/G 超过阈值时，网络带宽加载 KV cache 比重新计算 attention 更快；将集群闲置的 CPU/DRAM/NIC 资源池化为 PB 级分布式 cache，比仅依赖本地 HBM 更高效

#### [[fast2025-chen-weijian-leap|LeapGNN: Accelerating Distributed GNN Training Leveraging Feature-Centric Model Migration]]
- **作者**：Weijian Chen et al.
- **要解决的问题**：分布式 GNN 训练中远程 feature fetching 占训练时间的 44-83%，成为严重通信瓶颈
- **核心贡献**：Feature-centric GNN 训练框架，利用 micrograph 开发图分区局部性、vertex feature 预聚合消除冗余请求、micrograph 合并降低同步开销，实现 1.3-4.2× 加速
- **关键发现/观点**：GNN 模型参数比顶点特征数据小 13.4-2368 倍；利用 micrograph 中的图分区局部性使 feature-centric 训练比 model-centric 更高效，数据局部性提升 1.59-10.60 倍

#### [[fast2025-tian-bing|FusionANNS: Towards High-throughput and Low-latency Billion-scale Vector Search via CPU/GPU Collaborative Filtering]]
- **作者**：Bing Tian et al.
- **要解决的问题**：SSD-based ANNS 系统吞吐量低；天真地结合 PQ 压缩和 GPU 加速反而恶化性能；不可预测的 re-ranking 数量造成 I/O 浪费
- **核心贡献**：多层索引架构将 posting list 结构与向量内容解耦，使所有 PQ 向量可放入 GPU HBM；CPU/GPU 协同过滤；启发式提前终止的 re-ranking
- **关键发现/观点**：IVF 索引的边界复制导致 8× 索引膨胀；通过只在 GPU HBM 中存储去重的 PQ codes、将 ID lists 保留在主存，billion 级向量可以放入入门级 GPU，消除 CPU-GPU 数据交换瓶颈

#### [[fast2025-qiu|GeminiFS: A Companion File System for GPUs]]
- **作者**：Shi Qiu et al.
- **要解决的问题**：GPU 存储访问要么经 CPU 中转（瓶颈），要么设备直连但无文件系统抽象；GPU ML 工作负载有可预测的 I/O 模式且数据大多只读
- **核心贡献**：Companion filesystem，GVDK 格式将 L1/L2 映射表嵌入文件；共享 NVMe 驱动（SNVMe）支持 GPU 直接访问；GPU 原生 warp 级 page cache
- **关键发现/观点**：GPU ML 工作负载 I/O 可预测且大多只读；元数据可以嵌入文件并预计算，消除动态分配需求；GPU 可以直接访问 NVMe 同时保持文件系统抽象

### 新型存储硬件与近数据计算（7 篇）

#### [[fast2025-chen-menglei|GPHash: An Efficient Hash Index for GPU with Byte-Granularity Persistent Memory]]
- **作者**：Menglei Chen et al.
- **要解决的问题**：将 hash index 迁移到 GPU + PM 面临三大挑战：warp divergence 和非合并内存访问、高崩溃一致性开销、GPU 内存与 PM 间 20× 带宽差距
- **核心贡献**：GPU 特化 hash index：warp 协同执行（32 slot/bucket 一次 warp 访问）、无锁崩溃一致性（CAS + slot state）、bucket 粒度冻结缓存
- **关键发现/观点**：GPU warp 可以在一次网络往返中协同访问 32 个 slot，只需将 bucket 结构设计为匹配 warp 宽度（32 线程）；CAS 原子操作匹配 PM 的 8 字节原子写入单元，实现无日志崩溃一致性

#### [[fast2025-cui|PIMLex: A High-Performance Learned Index with Processing-in-Memory]]
- **作者**：Lixiao Cui et al.
- **要解决的问题**：Learned indexes 的内存带宽瓶颈（>60% 执行时间在内存停顿）PIM 可以解决，但映射到 PIM 硬件面临容量限制、弱计算能力（无浮点）和倾斜负载不平衡
- **核心贡献**：解耦两层索引：search layer（anchor keys）驻留 PIM 提供粗粒度位置提示，data layer 留在 DRAM；hotness-aware 副本机制平衡 PIM 模块间负载
- **关键发现/观点**：PIM 的优势是极高内存带宽但弱计算能力；用更多内存访问换更少计算（查找表替代浮点运算、全局二分搜索替代 model-based search）使 learned index 与 PIM 硬件特性对齐

#### [[fast2025-huang|HaSiS: A Hardware-assisted Single-index Store for Hybrid OLTP/OLAP]]
- **作者**：Kecheng Huang et al.
- **要解决的问题**：多索引 HTAP 系统需要维护独立的行列索引和异步 ETL，导致数据新鲜度延迟（30ms 到分钟级）、写放大和 2× 存储开销
- **核心贡献**：利用 CSD 透明压缩存储大页 B+ 树 + 稀疏列填充（4KB 对齐 mini-pages + 零填充），解耦页大小与写放大，实现即时数据新鲜度的单索引 HTAP
- **关键发现/观点**：CSD 的透明压缩使稀疏数据布局（部分填充的 4KB 块 + 零填充）零空间浪费存储成为可能；这使得大页列存储无写放大，解决传统 OLTP/OLAP 格式不匹配问题

#### [[fast2025-park|SODE: Selective On-Device Execution of Data-Dependent Read I/Os]]
- **作者**：Chanyoung Park et al.
- **要解决的问题**：数据依赖的读重提交（遍历磁盘 B 树）在每次重提交时产生微秒级软件栈开销；纯 in-storage 和纯 in-kernel 路径都非最优
- **核心贡献**：混合自适应执行：根据设备繁忙度选择 on-device vs in-kernel 路径；乐观元数据缓存避免逐次 PCIe 往返；并行重提交过滤器利用多核
- **关键发现/观点**：On-device 执行的收益取决于设备核心可用性和存储物理邻近性——混合执行根据设备负载自适应，避免过载设备核心导致的尾延迟

#### [[fast2025-zhu|HiDPU: DPU-Oriented Hybrid Indexing for Disaggregated Storage]]
- **作者**：Wenbin Zhu et al.
- **要解决的问题**：DPU 内存（MB 级）不足以支撑 PB 级页表（需 64GB）；DPU 计算弱（无浮点单元）；PCIe 访问宿主内存比板载内存慢 18-628×
- **核心贡献**：三层混合索引：Accurate Segment（强连续性，线性 O(1)）、LPTHash（弱连续性）、PTHash（随机）；learned index 路由器；Pilot Cache；23KB DPU 内存支持 1.2PB
- **关键发现/观点**：逻辑-物理地址映射具有不同程度的连续性特征；按连续性分段并匹配最优索引结构（连续用线性、随机用 hash），可以在极小内存预算下实现高效地址翻译

#### [[fast2025-ren|PolyStore: Exploiting Combined Capabilities of Heterogeneous Storage]]
- **作者**：Yujie Ren et al.
- **要解决的问题**：异构存储（PM+NVMe+SATA）管理使用层级缓存方式，浪费累积写带宽并造成快速设备瓶颈；DRAM 缓存未适配设备异构性
- **核心贡献**：水平存储架构：Poly-index 实现细粒度（2MB）设备映射、动态带宽感知放置、异构感知 DRAM 缓存、跨设备协调持久化
- **关键发现/观点**：新兴存储设备不再有严格的快-慢层级关系；水平并行布局配合细粒度分发可释放层级方式所牺牲的累积带宽

#### [[fast2025-zhan|OrchFS: Rethinking Request-to-IO Transformation for Full Utilization of High-Bandwidth SSDs]]
- **作者**：Yekang Zhan et al.
- **要解决的问题**：SSD 文件系统仅利用 SSD 原始带宽的 1/4-1/3，原因是对齐不匹配、page cache 开销和 I/O 并发不足
- **核心贡献**：重新设计 request-to-IO 转换：将写入分为 SSD-page 对齐 IO（直接、多线程）、NVM-page 对齐 IO 和非对齐碎片；HRtree 统一映射；嵌入式并行 IO 引擎
- **关键发现/观点**：SSD 不断增长的带宽只有在 IO 对齐、直接且并发时才能完全利用；NVM 的字节寻址性是处理剩余非对齐写入的理想互补——SSD-page 未对齐有 10.71× 性能惩罚（16KB 未对齐），NVM 可以吸收这一开销

### 文件系统设计与优化（7 篇）

#### [[fast2025-ha|ScaleLFS: A Log-Structured File System with Scalable Garbage Collection for Commodity SSDs]]
- **作者**：Jin Yong Ha et al.
- **要解决的问题**：现代 LFS 的串行 GC 无法利用多核 CPU 和高带宽 SSD；天真的并行 GC 在段选择、元数据更新、写分配和文件级保护处引入锁竞争
- **核心贡献**：三组件并行 GC：每核专用 collector（DGC）、通过 atomic test-and-set 的并发 victim 选择、page 级保护替代文件级锁；实现 3.5-7× 吞吐提升
- **关键发现/观点**：现代硬件提供的并行度足以被 GC 利用；消除 victim 选择、元数据更新和 page 访问周围的细粒度锁后发现，GC 带宽才是真正的瓶颈，而非锁竞争

#### [[fast2025-kim-juwon|D2FS: Device-Driven Filesystem Garbage Collection]]
- **作者**：Juwon Kim et al. (KAIST)
- **要解决的问题**：F2FS 的 GC 造成 80% 性能损失；SSD 设备级 GC 和文件系统级 GC 独立运行，产生双重写放大
- **核心贡献**：Coupled GC：设备 GC 同时进行 LBA 重映射；migration upcalls 通知 host 更新 filemap；虚拟 overprovisioning 确保设备 GC 在文件系统需要空间前完成
- **关键发现/观点**：设备 GC 本身已很高效（仅 20% 开销）；如果在设备 GC 时耦合 LBA 重映射，文件系统级 GC 变得不必要——可以将整个 GC 责任卸载到设备固件

#### [[fast2025-yoo|DJFS: Directory-Granularity Filesystem Journaling for CMM-H SSDs]]
- **作者**：Seung Won Yoo et al.
- **要解决的问题**：事务锁阻塞所有元数据操作；现有多事务方案有冲突和复杂性问题；CMM-H 的 64B 粒度利用不足
- **核心贡献**：Per-directory 事务模型 + path-based 选择 + 事务合并 + 冲突解决；64B differential logging via CXL.mem；CMM-H DRAM cache 中的 100MB journal
- **关键发现/观点**：真实应用（Exim、RocksDB、SQLite、MySQL 等）共享三个属性：进程在自己的目录中工作（D）、文件更新需要父目录变更（U）、相关文件在同一目录（S）——目录是并行提交的天然事务边界

#### [[fast2025-pan|GogetaFS: Merged Metadata Management in Deduplication FS]]
- **作者**：Yanqi Pan et al.
- **要解决的问题**：去重文件系统维护独立的 FP2P 和 L2P 映射并各自保证崩溃一致性，造成 18-38% I/O 开销
- **核心贡献**：LFP mapping 合并指纹和逻辑到物理映射；Overflow FP Table 处理 extent 级数据；无锁 GLT 无需崩溃一致性保证（从 LFP 重建）
- **关键发现/观点**：非密码学指纹已经足够小（8B），将其嵌入文件系统 L2P 条目创建的元数据比独立的 FP2P 索引更小；可以免费复用文件系统的崩溃一致性机制

#### [[fast2025-liu-jing|Ananke: Fast, Transparent Filesystem Microkernel Recovery]]
- **作者**：Jing Liu et al. (Microsoft Research)
- **要解决的问题**：微内核文件系统崩溃（p-crash）在应用期望和持久化磁盘状态之间创建状态间隙；先前恢复方法要么强制昂贵的 sync，要么重用损坏的内存
- **核心贡献**：P-crash log tracking：在 p-log 中记录操作日志 + target status bitmap；AIM 算法根据持久化状态决定对每个操作进行 ignore/act/modify
- **关键发现/观点**：在微内核架构中，OS 内核在进程崩溃时仍存活可以协调恢复；不需要 sync 所有状态，只需记录操作元数据并根据已持久化的内容智能重放/省略操作

#### [[fast2025-wang|NVLog: Boosting File Systems Elegantly via Transparent NVM Write-ahead Log for Disk File Systems]]
- **作者**：Guoyu Wang et al.
- **要解决的问题**：NVM 文件系统在非同步场景下比磁盘 FS 更慢；覆盖方案引入开销；小写入受页粒度写放大之苦
- **核心贡献**：将 NVM WAL 作为 VFS page cache 的旁路（非覆盖 FS）；仅 log-append；Active Sync 根据历史自适应 fsync 模式；NVM-Disk 一致性协议
- **关键发现/观点**：DRAM page cache 对大多数场景已经非常高效；NVM log 应该聚焦于"记录"（append-only）而非"检索"（索引）——sync 写到 NVM，async 写到磁盘，通过显式时间排序防止版本混淆

#### [[fast2025-wu|MedFS: Pursuing Low Update Overhead via Metadata-Enabled Delta Compression for LFS on Mobile]]
- **作者**：Chao Wu et al.
- **要解决的问题**：Delta 压缩的维护 I/O 开销高；需要外部硬件依赖；F2FS inline area 大量未使用空间
- **核心贡献**：DCI 将 delta chunks 嵌入 inode inline area；DCM 配合热度聚类；后台恢复实现自适应压缩
- **关键发现/观点**：移动设备文件更新平均仅改变 13.8% 的内容；inode inline area 94% 未使用且 inode cache 命中率高达 99.97%，可通过搭载 inode 回写实现零成本 delta 持久化

### 存储安全与一致性（5 篇）

#### [[fast2025-burke|On Scalable Integrity Checking for Secure Cloud Disks]]
- **作者**：Quinn Burke et al.
- **要解决的问题**：Merkle hash tree 对高速 NVMe 存储造成显著性能开销（1TB 磁盘最高 75% 吞吐损失），且开销随容量对数增长
- **核心贡献**：Dynamic Merkle Trees（DMTs）根据工作负载访问模式自适应重构为非平衡树，使用 splay 操作将高频访问数据移近根节点，实现最高 2.2× 吞吐提升
- **关键发现/观点**：真实存储工作负载呈高度倾斜的 Zipfian 分布，寻找最优 hash tree 在数学上等价于 Huffman 编码问题——应用 Huffman 编码原则产生的树最小化了期望 hash 计算次数

#### [[fast2025-tian-hongliang|AtomicDisk: A Secure Virtual Disk for TEEs against Eviction Attacks]]
- **作者**：Hongliang Tian et al. (Ant Group)
- **要解决的问题**：SGX-PFS 存在 eviction attack 漏洞，cache 驱动的快照可被重放，产生不可检测的中间磁盘状态
- **核心贡献**：引入 sync atomicity 属性和增强的 MHT（committed/uncommitted 状态追踪）；恢复 journal 仅为已提交块保留旧版本
- **关键发现/观点**：TEE 存储缺少对用户主动 sync 操作和自动 cache eviction 的区分；在 journal 中将 evicted writes 标记为 uncommitted 允许崩溃恢复丢弃未授权快照

#### [[fast2025-jeon|AWUPF Rediscovered: Atomic Writes to Unleash Pivotal Fault-Tolerance in SSDs]]
- **作者**：Jiyune Jeon et al.
- **要解决的问题**：SSD 的 AWUPF 能力被主机软件忽略，仍依赖 journaling 双写，导致写放大和性能下降
- **核心贡献**：为 PoseidonOS Log-RAID 设计双路径更新策略：小元数据更新（<AWUPF 大小）绕过 journaling 直接原子写，大更新走传统 journal 路径
- **关键发现/观点**：SSD AWUPF 保证单次原子写入；适合 AWUPF 粒度的元数据更新可以直接写入而无需 journaling，将崩溃一致性卸载到硬件

#### [[fast2025-jiao|Silhouette: Leveraging Consistency Mechanisms to Detect Bugs in PM File Systems]]
- **作者**：Bing Jiao et al.
- **要解决的问题**：PM 文件系统 bug 检测工具产生指数级 crash plans（100K-3M 个）；现有工具缺乏对崩溃一致性机制的语义理解
- **核心贡献**：基于不变量的 crash plan 缩减：将 in-flight stores 分为受标准机制保护/不受保护；2CP 启发式缩减搜索空间
- **关键发现/观点**：PM 文件系统使用标准崩溃一致性机制（journaling、log-structured、replication），其具有显式阶段不变量；受保护的 stores 无需 crash 探索，只需对未保护 stores 选择性生成 crash plan

#### [[fast2025-kim-jieun|OPIMQ: Order Preserving IO Stack for Multi-Queue Block Device]]
- **作者**：Jieun Kim et al. (KAIST)
- **要解决的问题**：多队列块设备打破了 journaling/事务所需的存储顺序保证；当前解决方案要么基于单队列，要么牺牲复合事务
- **核心贡献**：通过 FTL 映射表排序将存储顺序与物理写入顺序解耦：epoch pinning 维护流内顺序，双流写处理流间依赖
- **关键发现/观点**：存储顺序可以与物理数据刷新顺序解耦——在 FTL 映射表层面保证顺序而非数据持久化层面；set unblocking 在保持正确性的同时释放并行性

### KV 存储与缓存（3 篇）

#### [[fast2025-duan|AegonKV: A High Bandwidth, Low Tail Latency, and Low Storage Cost KV-Separated LSM Store with SmartSSD-based GC Offloading]]
- **作者**：Zhuohui Duan et al.
- **要解决的问题**：KV 分离 LSM store 的 GC 面临三方权衡：Direct GC 与前台 I/O 竞争（40% 吞吐损失），Compaction-triggered GC 存储开销膨胀（5.4-14.4× 更多 I/O）
- **核心贡献**：将 GC 卸载到 SmartSSD 的 FPGA，使用 ValidMap bitmap 追踪数据有效性，FPGA 计算单元执行设备内过滤和压缩，延迟验证避免写回竞争
- **关键发现/观点**：SmartSSD 的内部 P2P 带宽和 FPGA 使 GC 操作无需消耗主机 CPU/PCIe 带宽；通过轻量级 bitmap 追踪有效性并将 GC 完全移出关键路径，传统 GC 的三方权衡不再成立

#### [[fast2025-gan|Revisiting Network Coding for Warm Blob Storage]]
- **作者**：Chuang Gan et al.
- **要解决的问题**：Warm blob 存储使用纠删码保证持久性，但 Clay codes 高 sub-packetization 导致小 blob 读放大，非系统 MSR 码低 sub-packetization 但所有读都需要解码 k 个 parity block
- **核心贡献**：基于 MSR 的混合架构，split-merge-encode 和 merge-split-encode 策略利用 blob 内和 blob 间访问局部性消除读放大
- **关键发现/观点**：真实 warm blob 工作负载有两个关键局部性：(1) 单个小 blob 以 token 粒度访问，(2) 多个同时访问的小 blob 有 blob 间局部性；利用这些局部性意味着非系统码的读放大在实践中被自然消除

#### [[fast2025-zhou-wenbin|3L-Cache: Low Overhead and Precise Learning-based Eviction Policy for Caches]]
- **作者**：Wenbin Zhou et al.
- **要解决的问题**：对象级学习驱逐策略 CPU 开销极高（LRB 172×、HALP 23× vs LRU）；训练/预测浪费；不同工作负载需要参数重调
- **核心贡献**：训练数据过滤 + 双向采样（尾部和头部）+ 自动调参；在所有数据集上平衡 recall 的同时将 CPU 开销从 172× 降至 3.4-6.4× LRU
- **关键发现/观点**：训练频率可以大幅降低而不损失精度（LRB 从每百万请求 2³ 降到 2⁻³，CPU 降低 48% 而 miss ratio 变化极小）；72% 的缓存对象仅被访问一次，驱逐率理论上可从当前的 1.56-25% 提升到 72%

### 数据压缩与去重（2 篇）

#### [[fast2025-udayashankar|VectorCDC: Accelerating Data Deduplication with Vector Instructions]]
- **作者**：Sreeharsha Udayashankar et al.
- **要解决的问题**：CDC 算法消耗大量资源；现有向量加速（SS-CDC）对 hash-based 算法有根本限制；non-hash 算法缺乏向量化
- **核心贡献**：首次为无 hash CDC 算法（AE、RAM）实现向量加速，通过树状极值字节搜索和打包范围扫描，实现 24-26 GB/s 吞吐
- **关键发现/观点**：Non-hash CDC 算法可以分解为两个天然可向量化的子阶段（极值字节搜索和范围扫描），没有 hash 算法固有的数据依赖性，实现 16-46× 加速

#### [[fast2025-li|Archer: Adaptive Memory Compression with Page-Association-Rule Awareness]]
- **作者**：Changlong Li et al.
- **要解决的问题**：移动设备内存压缩按页进行，导致 CPU 利用不足和内存压力下的优先级反转；无页关联感知
- **核心贡献**：关联规则挖掘用于内存压缩：FSG 收集页访问模式，FP-Growth 发现关联页，ACR 以可变粒度批量压缩关联页
- **关键发现/观点**：移动设备约 26% 的匿名内存页具有高共访问关系（>80% 概率）；批量压缩关联页在不增加读放大的情况下提高 CPU 效率

### 容器与云存储（2 篇）

#### [[fast2025-liu-yubo|FlacIO: Flat and Collective I/O for Container Image Service]]
- **作者**：Yubo Liu et al. (Huawei)
- **要解决的问题**：容器 lazy loading 有 1.6×-3.1× I/O 放大（chunk 级加载 vs page 级访问），产生 10K-90K 网络包；冷启动仍是瓶颈
- **核心贡献**：Runtime Image 抽象：服务特定的启动所需根文件系统快照；probe-based tracing 收集启动 I/O；RTPC 将数据直接注入 page cache
- **关键发现/观点**：确定性启动所需数据相对完整镜像很小；如果启动数据被预组织为连续布局并建立索引，冷启动可以用单次大 I/O 替代大量小 I/O

#### [[fast2025-satija|Cloudscape: A Study of Storage Services in Modern Cloud Architectures]]
- **作者**：Sambhav Satija et al. (UW-Madison, NetApp)
- **要解决的问题**：缺乏真实云架构模式的实证数据；存储服务选择缺乏社区经验指导；研究方向与实际部署不对齐
- **核心贡献**：首个大规模研究：分析 396 个真实 AWS 架构，揭示存储服务使用模式；数据集和分析工具开源
- **关键发现/观点**：S3（68% 使用率）已成为默认存储服务和云系统中的主要数据交换机制；AWS 视频是理解生产架构的未开发数据源

### 新兴存储介质——DNA 存储（2 篇）

#### [[fast2025-zhou-jiahao|LiqSD: Liquid-State Drive — DNA Block Device for Enormous Data]]
- **作者**：Jiahao Zhou et al. (上海交大 IPADS)
- **要解决的问题**：DNA 存储更新代价极高（需读取整个擦除单元、擦除、回写）；PB 级翻译层管理困难；GC 元数据开销高
- **核心贡献**：双层 DTL（L0 在 SSD，L1 在 DNA）+ 共生元数据（GC 信息嵌入块）+ 延迟失效（推迟 L1 DTL 读取）；随机操作写放大降至约 1.006
- **关键发现/观点**：DNA 读/写/擦除粒度的极端不对称性（strand 300nt vs SC 24MiB vs spot）使双层 DTL 成为可能：小 L0 在快速 SSD 上，大 L1 通过 strand 写入更新 DNA，实现 7 个数量级的写放大降低

#### [[fast2025-brunmayr|DNA Data Storage: A Generative Tool for Motif-based DNA Storage]]
- **作者**：Samira Brunmayr et al.
- **要解决的问题**：Motif-based DNA 存储需要设计同时满足多种生物约束（GC 含量、同聚体、发夹结构）的 DNA 序列，现有工具要么不支持所有约束，要么在约束复杂度下严重退化
- **核心贡献**：基于 MDP 的生成工具，使用参数化奖励函数引导 DNA motif 构建，无需回溯或穷举搜索即可快速生成满足约束的序列
- **关键发现/观点**：Motif 序列构建可以建模为 MDP，每个核苷酸选择由 log-score penalties 的加权组合引导；这种方法在生成过程中自然产生满足所有约束的序列，无需显式约束检查

### 分布式系统（2 篇）

#### [[fast2025-gao|ShiftLock: Mitigate One-sided RDMA Lock Contention via Handover]]
- **作者**：Jian Gao et al.
- **要解决的问题**：RDMA 锁在高竞争场景下产生大量重试风暴（>94% 操作为重试），backoff 策略无法充分缓解
- **核心贡献**：使用 RDMA Dynamic Connections 和双边 RDMA 消息传递实现分布式 MCS 锁交接，扩展原子操作支持读写语义，lease-based 容错恢复
- **关键发现/观点**：在 RDMA 系统中，客户端 CPU 处于空闲状态（不管理锁），可以使用非阻塞双边 RDMA 消息传递进行锁交接，而非昂贵的单边重试风暴——将 N-to-1 锁服务器瓶颈转换为可扩展的点对点协调

#### [[fast2025-yang|Oasis: An Out-of-core Approximate Graph System via All-Distances Sketches]]
- **作者**：Tsun-Yu Yang et al.
- **要解决的问题**：ADS 图处理理论成熟但工程瓶颈不可行：内存开销（图大小的 30-60 倍）；现有方法仅关注内存；传统 out-of-core 系统不适配
- **核心贡献**：首个 out-of-core ADS 系统：分区构建、无锁边布局、活跃数据分离、选择性 ADS 访问；内存节省 13.8× 仅增加 1.79× 构建时间
- **关键发现/观点**：ADS 的大规模数据膨胀恰好匹配廉价大容量存储的特点；ADS 的极端加速可以抵消存储 I/O 延迟——分区 + 选择性加载将 I/O 从 O(Vk log V · P · I) 降至 O(2·Vk log V)

### 区块链存储经济（1 篇）

#### [[fast2025-he|Maat: Analyzing and Optimizing Overcharge on Blockchain Storage]]
- **作者**：Zheyuan He et al.
- **要解决的问题**：以太坊 gas 定价在 opcode 粒度计费，不区分操作是否命中缓存（内存开销）还是需要磁盘访问（磁盘开销），导致 70.4% 交易被多收，年总额约 1.47 亿美元
- **核心贡献**：存储操作级（而非 opcode 级）的细粒度 gas 优化系统，应用四条优化规则消除同块或跨近期块的缓存命中计费
- **关键发现/观点**：以太坊多层缓存层级（CoW cache、SSAS cache 等）意味着许多被收取"磁盘访问"费用的操作实际命中缓存；细粒度追踪哪些存储操作实际为缓存命中，允许与真实资源消耗对齐的精确计费

---

## 研究趋势分析

### 1. 存储系统全面拥抱 AI/ML 工作负载

FAST 2025 最显著的趋势是存储社区对 AI/ML 工作负载的深度关注。36 篇论文中有 5 篇直接面向 AI/ML 系统的存储问题（IMPRESS、MOONCAKE、LeapGNN、FusionANNS、GeminiFS），涵盖了 LLM 推理的 KV cache 管理、GNN 训练的 feature 存储优化、向量检索的存储层级设计以及 GPU 原生文件系统。这标志着存储研究从传统的"通用存储优化"向"AI 工作负载特化存储"的范式迁移。特别值得注意的是 MOONCAKE 来自 Moonshot AI 的生产系统实践，表明工业界已在将 KV cache 视为一种可以跨节点共享的分布式存储资源。

### 2. 计算-存储边界的持续模糊化

近数据计算（near-data processing）从概念走向实用化是另一个突出趋势。PIMLex 将 learned index 映射到 PIM 硬件、AegonKV 将 GC 卸载到 SmartSSD 的 FPGA、HiDPU 在 DPU 上实现混合索引、SODE 自适应选择 on-device 或 in-kernel 执行、HaSiS 利用 CSD 透明压缩——这些工作共同揭示了一个方向：存储不再只是"存"数据的被动组件，而是能主动参与计算的智能单元。关键挑战从"能不能在存储设备上计算"转向了"什么计算应该放在存储设备上"。

### 3. 异构存储的水平化与协同设计

传统的异构存储管理采用"快设备做缓存、慢设备做持久层"的层级模型，但 PolyStore 和 OrchFS 表明这种模型在新硬件面前已经过时。PM、NVMe、CXL-attached DRAM（如 CMM-H）、传统 SSD 之间不再是简单的快-慢关系，而是各有带宽、延迟、持久性和粒度的特化优势。DJFS 利用 CMM-H 的 64B 粒度实现目录级 journaling，OrchFS 利用 NVM 吸收非对齐写入来释放 SSD 带宽——未来的存储系统需要在设计时就考虑多种介质的协同，而非事后叠加。

### 4. GC 问题的系统性重思考

三篇论文（ScaleLFS、D2FS、AegonKV）分别从并行化、设备卸载和计算存储卸载三个角度重新审视了 GC 问题，反映出 GC 仍然是存储系统的核心痛点。D2FS 的 insight 尤为深刻：设备级 GC 已经非常高效，文件系统级 GC 完全可以消除。这种"将问题推到最适合解决它的层次"的思路也体现在 AWUPF（将崩溃一致性推到 SSD 硬件）和 OPIMQ（将顺序保证推到 FTL）等工作中。

### 5. Learned/ML 技术渗透存储内部机制

3L-Cache 用学习方法优化缓存驱逐、HiDPU 用 learned index 做地址翻译路由、PIMLex 将 learned index 映射到 PIM——ML 技术不再只是存储系统的"客户"，而是开始成为存储系统内部的优化工具。这种双向渗透（存储为 ML 服务 + ML 为存储优化）是一个值得关注的长期趋势。

---

## 存储 × AI Infra/MLSys 交叉研究发现

> 以下是专门面向你的需求整理的跨领域交叉洞察。

### 发现 1：KV Cache 正在演变为一种分布式存储抽象

MOONCAKE 和 IMPRESS 共同揭示了一个深刻变化：LLM 推理的 KV cache 不再是简单的 GPU 显存管理问题，而是一个完整的**分布式存储系统设计问题**。MOONCAKE 将集群闲置的 CPU/DRAM/NIC 池化为 PB 级分布式 cache pool，本质上是在构建一个专为 KV cache 定制的分布式存储系统。IMPRESS 则发现 attention heads 的重要性具有极高的 intra-layer 相似性（Jaccard >0.95），这意味着可以用极少的 I/O 识别需要从 SSD 加载的 KV 子集。

**启示**：传统存储领域的 tiered storage、prefetching、importance-aware caching 技术可以直接迁移到 LLM KV cache 管理中——但需要根据 attention 的统计特性重新设计策略。

### 发现 2：GPU 存储栈是一个被严重忽视的领域

GeminiFS 表明 GPU ML 工作负载有可预测的 I/O 模式和大量只读数据，但目前 GPU 与存储之间要么经 CPU 中转（瓶颈），要么缺乏文件系统抽象。FusionANNS 进一步展示了 CPU/GPU 协同过滤向量数据时的存储层级设计空间。随着 GPU Direct Storage 的成熟，GPU 原生的存储栈（包括文件系统、缓存策略、I/O 调度）将成为 AI infra 的关键缺失组件。

### 发现 3：Near-data Processing 天然适合 AI 推理的 I/O 密集阶段

PIMLex 证明了 PIM 的"高带宽 + 弱计算"特性可以通过"用更多访问换更少计算"来对齐；AegonKV 证明了 SmartSSD FPGA 可以在不消耗主机资源的情况下完成数据过滤。这两个 insight 对 AI 推理的 decoding 阶段（memory-bound，计算简单但访问频繁）有直接启发：将 KV cache 的 attention 计算部分卸载到 near-memory 或 near-storage 设备，有可能突破当前 memory bandwidth wall。

### 发现 4：存储系统的 Learned Components 已证明可行但需极致优化

3L-Cache 证明了 ML-based 缓存驱逐策略可以在 3.4-6.4× LRU 的 CPU 开销下工作（之前是 172×），核心技巧是大幅降低训练频率和过滤训练数据。HiDPU 在 23KB 内存中用 learned index 路由地址翻译。这说明 learned components 在存储系统中的工程化已有突破——关键是找到正确的 accuracy-overhead 权衡点，而非追求最高精度。

---

## 小实验室的机会窗口

### 1. KV Cache 感知的存储层级策略

- **方向描述**：设计专门针对 LLM KV cache 特性的多层存储管理策略，利用 attention 的统计规律（如 IMPRESS 发现的 heads 间 importance 相似性）优化 SSD → CPU → GPU 的数据迁移
- **为什么小团队能做**：不需要大规模 GPU 集群，只需要 1-2 台配备 NVMe SSD 的 GPU 服务器；核心是算法和策略设计而非工程规模；可以在开源 LLM 推理框架（vLLM、SGLang）上实现
- **哪些论文指向了这个空白**：IMPRESS 揭示了 importance-aware tiering 的可行性但仅限于 prefix 场景；MOONCAKE 展示了分布式 KV pool 但未深入单机多层存储策略
- **具体 open problems**：
  - 不同 LLM 架构（MHA/GQA/MQA）下 attention importance 的统计分布差异如何影响存储策略？
  - KV cache 的时间局部性模式（哪些 token 的 KV 会被反复使用）是否可以预测？
  - 如何设计 SSD-friendly 的 KV cache 布局以最小化读放大？

### 2. Learned Index 在 AI 系统中的轻量化应用

- **方向描述**：将 HiDPU 和 PIMLex 展示的轻量级 learned index 技术应用到 AI 系统的元数据管理中，如 checkpoint 索引、embedding table lookup、feature store 索引
- **为什么小团队能做**：Learned index 的核心代码量小（几百行）；3L-Cache 证明了训练开销可以降到极低；不需要特殊硬件，可以纯软件实现
- **哪些论文指向了这个空白**：HiDPU 在 23KB 内存中实现了 PB 级地址翻译；3L-Cache 证明了训练频率可降低 64 倍而不损失精度；PIMLex 展示了 learned index 的计算-内存权衡空间
- **具体 open problems**：
  - LLM checkpoint 的 tensor 分片索引能否用 learned index 加速定位？
  - Embedding table 的访问模式是否有足够的分布规律支撑 learned index？
  - 如何在 GPU 上实现 warp-friendly 的 learned index 查询？

### 3. 面向 ML 工作负载的文件系统 I/O 优化

- **方向描述**：利用 ML 训练/推理工作负载 I/O 模式的高度可预测性（GeminiFS 的核心发现），设计专用的预取、缓存和调度策略
- **为什么小团队能做**：可以在现有文件系统（ext4/F2FS/XFS）之上用 eBPF 或 FUSE 实现轻量原型；ML 工作负载的 I/O trace 容易获取（PyTorch DataLoader 等）
- **哪些论文指向了这个空白**：GeminiFS 证明 GPU ML I/O 可预测且大多只读；OrchFS 展示了对齐 + 直接 I/O 可释放 SSD 全部带宽；FlacIO 展示了预组织数据的冷启动加速效果
- **具体 open problems**：
  - ML 训练的 data loading 阶段能否通过 I/O pattern 预测实现零等待 prefetch？
  - 模型 checkpoint 的读写模式（大量顺序写 + 偶发全量读）是否值得专用文件布局？
  - 多租户 GPU 集群中不同训练任务的 I/O 干扰如何隔离？

### 4. 存储硬件异构性的 AI 推理调度利用

- **方向描述**：将 PolyStore 的水平异构存储架构思路应用到 AI 推理系统中，根据不同阶段（prefill vs decode）和数据类型（model weights vs KV cache vs activation）选择最优存储路径
- **为什么小团队能做**：不需要特殊硬件，现有服务器通常已配备多种存储（DRAM、NVMe、SATA SSD）；核心是调度策略而非硬件开发
- **哪些论文指向了这个空白**：PolyStore 证明水平布局优于层级缓存；MOONCAKE 展示了 prefill/decode 分离架构；SODE 展示了自适应 on-device vs in-kernel 执行路径选择
- **具体 open problems**：
  - LLM 推理的不同数据类型（weights/KV/activations）在异构存储上的最优放置策略是什么？
  - 如何根据请求特征（prompt 长度、生成长度）动态调整存储路径？
  - PM（如 CXL-attached DRAM）作为 KV cache 的 overflow tier 的性价比如何量化？

### 5. 近数据计算辅助的 AI 推理加速

- **方向描述**：探索将 AI 推理中 memory-bound 操作（如 KV cache attention、embedding lookup）卸载到 PIM/CSD/DPU 等近数据计算设备的可行性
- **为什么小团队能做**：可以先用软件模拟验证思路（如 Ramulator、gem5）；PIMLex 和 HiDPU 已证明在弱计算设备上通过算法适配可以实现有效卸载；不需要流片
- **哪些论文指向了这个空白**：PIMLex 展示了"用更多访问换更少计算"适配 PIM 弱计算能力的范式；AegonKV 展示了 SmartSSD FPGA 零主机开销的数据过滤；HiDPU 在 23KB DPU 内存中实现了有效索引
- **具体 open problems**：
  - KV cache 的 attention 计算（矩阵-向量乘法）能否有效映射到 PIM 的 bank-level 并行？
  - 哪些 AI 推理 operator 的计算强度足够低以适合 near-storage 执行？
  - 如何设计 PIM-friendly 的 KV cache 数据布局以最大化 bank-level parallelism？
