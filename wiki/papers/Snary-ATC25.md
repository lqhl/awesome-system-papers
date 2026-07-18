---
type: paper
name: Snary
full_title: "SNARY: A High-Performance and Generic SmartNIC-accelerated Retrieval System"
authors: [Qiaoyin Gan, Heng Pan, Luyang Li, Kai Lv, Hongtao Guan, Zhaohua Wang, Zhenyu Li, Gaogang Xie]
venue: ATC
year: 2025
tags: [smartnic, fpga, embedding-retrieval, top-k, lsh, hbm]
source_pdf: "[[atc2025-gan.pdf]]"
source_md: "[[atc2025-gan]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# SNARY: A High-Performance and Generic SmartNIC-accelerated Retrieval System (ATC 2025)

> **一句话总结**：SNARY 建立在大规模 [[Embedding-Based-Retrieval]] 的端到端延迟主要由 corpus 扫描和 [[Top-K-Selection]] pipeline 决定这一观察上，把 exact search 和基于 [[LSH]] 的 fuzzy search 放到带 [[HBM]] 的 [[SmartNIC]]/[[FPGA]] 上，exact 场景比 [[Faiss]]/[[FAERY]] 降低 20.91%-83.88% 延迟，fuzzy 场景比 Faiss 降低 85.13%-87.40% 延迟，但这些结论主要来自 synthetic 128-d embedding corpus，production relevance 仍要单独验证。

## 问题与动机

工业推荐系统通常把请求拆成 retrieval 和 ranking 两段：retrieval 先从百万级或更大的 corpus 中召回几千个候选，ranking 再做更高精度的排序。论文关注的是 retrieval 阶段，尤其是 embedding-based retrieval 中“读 corpus、算相似度、选 Top-K”的硬件路径。

作者的核心判断是：当 corpus 足够大时，retrieval 系统不只是一个 SIMD 计算问题，而是一个端到端 pipeline 问题。CPU 缺少足够内存带宽和数据并行度；GPU 适合相似度计算，但 Top-K 选择涉及跨核通信和外部内存交互，论文引用的 prior work 指出成熟 GPU 框架可能把约 80% 延迟花在 Top-K 阶段；已有 FPGA 系统 FAERY 只支持 exact search，缺少现代 retrieval 常用的 fuzzy/ANN 模式。

SNARY 的 claim 边界比较明确：它不是改进 embedding 模型或推荐质量，而是在 embedding 已经离线生成、查询 embedding 已经到达系统的前提下，把 retrieval search engine offload 到 SmartNIC。SmartNIC 的动机是“离请求最近”：远端用户查询进入服务器时先经过 NIC，如果 NIC 上的 FPGA/HBM 能直接完成 retrieval，就能缩短 host/GPU 路径并保持确定性 pipeline。

## 关键观察 / 隐含假设

- **观察 1：fully-pipelined EBR 的 latency 近似由 corpus access 主导，公式可写成 `L = M / B + C`。** 论文把 corpus size `M`、外部内存带宽 `B`、pipeline 固定开销 `C` 分离开，并在 exact search 的 Figure 9 中展示 SNARY latency 随 corpus size 近似线性增长；在 fuzzy search 中，减少被扫描 corpus 的比例后，延迟下降也接近 `1 - eta`。
  - **依赖假设**：query embedding 已经准备好，ranking、feature fetch、network stack、host coordination 不是主导瓶颈；corpus 必须大到足以让 `M / B` 压过固定 pipeline 开销。
  - **可能失效场景**：小 corpus、复杂 query encoder、强 host-side feature join、多阶段 ranking 或多 tenant 排队成为主瓶颈时，HBM scan 的收益会被稀释。

- **观察 2：Top-K 是硬件 retrieval pipeline 的资源和时延热点，尤其在大 recall count 下会限制可扩展性。** 论文的模块分析显示 Top-K module 加 filter 在 cycle 和 resource 占比中占主导；随着 K 从 512 增到 4096，SNARY 的频率从 302.0 MHz 降到 235.3 MHz，batch 支持也从 3 降到 1。
  - **依赖假设**：recall rate `gamma = K / M` 足够小，使 filter 能把 `N_E` 个 similarity scores/cycle 压到 Top-K 可消费的 1 score/cycle；论文的 filter 分析还假设 score 分布近似随机均匀。
  - **可能失效场景**：K 相对 corpus 变大、score 分布高度相关或 bursty、filter FIFO 经常积压时，Top-K 不再只是 O(K) memory 的问题，而可能重新变成 pipeline backpressure 问题。

- **观察 3：对 fuzzy search，fuzzify corpus access 比 fuzzify similarity calculation 更贴近 SNARY 的硬件优势。** 论文没有在 similarity stage 做近似，而是用 simHash/LSH 先把 corpus 缩小成命中 bucket 与邻近 bucket，再复用 exact search pipeline。
  - **依赖假设**：LSH bucket 能较均匀地切分 embedding space，并且单表 `L_h = 1` 加 Hamming-neighbor probing 已经足以达到业务可接受的 recall/MRR。
  - **可能失效场景**：真实推荐 embedding 分布偏斜、热点 bucket 很大、需要 multi-table union/intersection 才能达到质量要求，或者业务要求的 ANN 算法更接近 [[HNSW]]/[[Product-Quantization]]/IVF-PQ 时，单表 LSH 的 pipeline 友好性可能要拿检索质量来换。

- **隐含假设：retrieval corpus 可以静态或低频更新，适合离线预处理后常驻 HBM。**
  - **证据强度**：中。论文实现了 corpus upload/update 的 100 Gbps TCP/IP 栈，也报告 9M corpus 的 LSH offline preprocessing 约 1-2 秒，但没有深入展示在线更新期间的一致性、双版本切换、partial rebuild 或服务不中断策略。

## 核心方法

SNARY 的 exact search 从 HBM layout 开始。实现中使用 16 个 HBM channels 存 corpus，每个 128-d embedding 由 1 byte/dim 组成，并跨 4 个连续 channel 存放，因此每个 pipeline cycle 可以读取 4 个完整 embedding。相似度计算使用 dot product，并把不同 embedding 之间、同一 embedding 内不同位置的计算都做硬件展开，以匹配 HBM 的输入速率。

Top-K 模块是论文最关键的 exact-search 设计。它维护一个长度 K 的数组，约定第 0 位始终保存当前 Top-K 中的最小值；每个新 score 进入时先与第 0 位比较，必要时替换，然后做两轮 parallel swaps：一轮从位置 1 开始成对比较交换，另一轮从位置 0 开始成对比较交换。这样每个 cycle 可以维持“第 0 位是当前 Top-K 最小值”的不变量，最后再追加 `K / 2` 个空输入 cycle 完成全排序。相比 FAERY 使用的 Top-K 方案，SNARY 的数组占用是 `O(K)` on-chip memory，而不是约 `O(9K/2)`，pipeline depth 也从 `O(log K)` 降到 1-2 stages。

因为相似度计算每个 cycle 产生 `N_E` 个 scores，而 Top-K 每个 cycle 只消费 1 个 score，SNARY 在两者之间插入 filter。filter 使用 Top-K 反馈的当前最小 Top-K score，丢掉低于阈值的 scores，并用 4 个 FIFO pipelines 缓存同一 cycle 内仍可能进入 Top-K 的 scores。这个设计把并行读/算和串行 Top-K 连接起来，但也把系统正确运行绑定到 recall rate、score 分布和 FIFO 深度上。

Fuzzy search 复用 exact search pipeline，只在 corpus access 前加一层 [[ANN]] filter。SNARY 使用 simHash 做 locality-sensitive hashing：离线把 corpus embedding 映射到 `2^K_h` 个 bucket，并在 HBM 中存 hash table 和 index table；在线查询也被映射到 bucket，然后扫描命中 bucket 与 Hamming distance 不超过 `T_h` 的 neighbor buckets。论文故意选择单表 `L_h = 1`，因为多表 intersection/union 会破坏 streaming access：系统必须先判断重复或集合成员关系，才能继续 pipeline 读取 embedding。

为了让 fuzzy search 仍然保持每 cycle 读 `N_E` 个 embedding，SNARY 对每个 bucket 的 index 做 channel-aware preprocessing：先按 embedding 所在 HBM channel 分类，补 padding 到各类等长，再重排成连续 `N_E` 个 index 分别落在不同 channel。padding 对应的 embedding 带 flag 进入 pipeline，最后由 filter 去掉。这一步是 fuzzy search 的关键工程折中：牺牲一些 HBM/index 空间，换取不破坏 exact pipeline 的并行 access。

完整系统在 Xilinx AMD Alveo U50 上实现，使用 HBM2、8GB storage、32 channels 和 100 Gbps TCP/IP stack。论文实现了 K = 512/1024/2048/4096 四种 recall count；由于 on-chip resource 限制，batch size 分别为 3、3、2、1，说明 SNARY 的 throughput 扩展主要受 Top-K/filter 资源而不是相似度计算本身限制。

## 设计取舍

- **取舍 1：选择 pipeline-friendly 的单表 LSH，而不是表达力更强的多表 ANN。** 收益是 index lookup 后可以立刻 streaming access corpus，避免 intersection/union 带来的额外状态和阻塞；代价是 fuzzy search 的质量空间受 `K_h`、`T_h` 和 bucket 分布限制。
- **取舍 2：用 padding 和 channel-aware bucket reorder 维持 HBM 并行访问。** 收益是 fuzzy search 能复用 exact search 的宽 pipeline；代价是 index 结构更依赖 HBM layout，并引入 padding 空间、预处理和更新复杂度。
- **取舍 3：用 filter 桥接 `N_E` scores/cycle 和 1 score/cycle Top-K。** 收益是相似度计算和 corpus access 可以保持并行；代价是 filter 有概率/分布假设，且 K 变大时 FIFO、on-chip memory、routing 和 frequency 都会受压。
- **边界条件**：SNARY 在静态 corpus、低 recall rate、质量可由近似搜索参数调节、硬件资源可专用于 retrieval 的场景下很优雅；在高频更新、强隔离/多租户、复杂 ANN quality requirement、corpus 超出单卡 HBM 或需要 host/GPU 紧耦合特征处理的场景下会变脆。

## 实验与结果

- **实验设置**：SNARY 和 FAERY 都在 Alveo U50 上评估；Faiss 运行在 4 张 Nvidia A100 GPU、CUDA 12.0 的服务器上。corpus 是随机生成的 128-dimensional embedding，每维 1 byte；实验最多放 9M embeddings，占约 28% HBM，论文称总容量可到约 32M embeddings。默认 K = 1024，latency-bounded throughput 使用 10 ms latency limit。
- **Exact search，固定 K = 1024、变化 corpus size**：SNARY latency 比 Faiss 低 82.42%-83.63%，比 FAERY 低 34.52%-45.19%；10 ms 限制下 throughput 比 Faiss 高 18.27x，比 FAERY 高 1.52x-1.76x。
- **Exact search，固定 corpus size = 1M、变化 K**：SNARY latency 比 Faiss 低 78.75%-83.88%，比 FAERY 低 20.91%-38.85%；throughput 比 Faiss 高 14.12x-18.27x，比 FAERY 高 1.26x-1.64x。Faiss 在更高 recall count 下受 1024 上限限制，不能覆盖所有 K。
- **Fuzzy search**：Faiss baseline 使用 IndexIVFFlat，`nlist = 100`、`nprobe = 10`；SNARY 选择 `K_h = 4`、`T_h = 1` 来获得相近 accuracy。论文报告 SNARY 在 similar/slightly higher Recall 和 MRR 下，latency 比 Faiss 低 85.13%-87.40%，10 ms throughput 高 20.18x-23.81x。相对 exact search，SNARY fuzzy latency 降低 78.05%-78.72%，Faiss 只降低 35.41%-39.17%。
- **Fuzzy 参数 tradeoff**：论文用 `eta` 表示被保留 corpus 比例，测试 `eta = 6.25%/12.50%/18.75%/31.25%/50.00%`。`eta` 越小，latency 越低、throughput 越高，但 recall/MRR 越差；latency reduction 大致跟 `1 - eta` 一致。
- **系统 characterization**：parallel corpus access 从 PL=1 提到 PL=8 明显降低 latency、提升 throughput，但 PL=8 后收益变小；SNARY 在相同 U50 上的 power 低于 FAERY；Vitis 模块分析显示 Top-K/filter 模块在 cycle/resource 中占主导，是后续优化的主要目标。

## Critical Analysis

### 论证链条

论文的硬件效率论证链条相对闭合：先把 EBR 拆成 corpus access、similarity calculation、Top-K；再说明 GPU/FAERY 的主要缺口在 Top-K pipeline 和 fuzzy search；然后用 HBM layout、parallel dot product、O(K) Top-K 和 LSH corpus filtering 对应这些瓶颈；最后用 corpus size、K、fuzzy 参数和模块分析验证 latency/throughput 的变化趋势。

主要跳步在“generic retrieval system”这个 claim 上。实验确实证明了 SNARY 对 synthetic embedding scan 的 search-engine datapath 很有效，但没有证明真实推荐 workload 的 embedding 分布、query 分布、quality requirement、在线更新和 host-side integration 也适合这个 datapath。更准确地说，论文证明的是“在 embedding 已经存在且 corpus scan 是主瓶颈时，SmartNIC FPGA 可以提供高效 exact/fuzzy search engine”，而不是完整推荐系统的端到端 superiority。

### 假设压力测试

最脆的是 LSH quality 假设。SNARY 为了 pipeline 选择 `L_h = 1`，避免多表 union/intersection；这在硬件上非常干净，但把 ANN 质量押在单表 simHash 和 neighbor bucket 上。真实 embedding 常有 cluster skew、hot items、业务分桶和非均匀 query distribution，bucket size 可能远离公式中的均匀估计，使 fuzzy search 同时遇到质量下降和 pipeline load imbalance。

第二个压力点是 filter 的 score 分布假设。Appendix A.2 为 filter effectiveness 做了概率分析，但简化为 similarity scores 近似随机均匀分布。真实推荐场景中，同一 query 对热门类目、相似商品、重复内容或 adversarial/degenerate embedding 的 score 可能高度相关，导致同一 cycle 有多个 scores 超过当前 Top-K minimum，FIFO 压力和 backpressure 风险会升高。

第三个压力点是 deployment assumption。SmartNIC “离 query 最近”成立，但 retrieval 服务通常还需要 query embedding 生成、feature fetch、权限过滤、业务规则、A/B 配置和 observability。若这些逻辑仍在 host/GPU，NIC offload 可能变成一段额外的专用路径，而不是替代完整 retrieval service。

### 实验可信度

FAERY 同板卡对比是论文里最有说服力的部分，因为它把收益主要归因到 Top-K/filter 和 pipeline 设计；Faiss 对比说明 GPU 在低 latency、high recall Top-K 上有弱点，但硬件配置、成本、功耗和实现细节并不完全对齐。论文报告了 SmartNIC power 与 FAERY 对比，但没有给出 Faiss 的 power/cost-normalized comparison。

最大实验缺口是数据集。论文明确使用 synthetic random 128-d embeddings，理由是 SNARY 关注硬件架构而非语义；这对 exact scan latency 是合理简化，但对 fuzzy search 的 recall/MRR、bucket distribution 和 query locality 就比较弱。Figure 10 中 fuzzy accuracy 的绝对值也不是很高，论文更像是在证明“相近近似质量下 SNARY 更快”，而不是证明“这个 fuzzy retrieval 质量足以服务真实推荐”。

metric 覆盖了 latency、10 ms bounded throughput、Recall/MRR、power 和模块资源，但缺少 production 常见的 tail latency under concurrent load、online update disruption、multi-tenant isolation、failure recovery、host-NIC queueing 和 end-to-end request latency。对于一个要放到 SmartNIC 上接 query 的系统，这些 operational metrics 会影响部署可行性。

### 系统性缺陷

SNARY 把 retrieval state 下沉到 NIC/FPGA/HBM，换来了低延迟 pipeline，也引入了更难的运维面：corpus/index 如何热更新、更新时 exact 和 fuzzy 视图是否一致、失败后如何回滚、多个业务或 tenant 如何共享 HBM、如何观测 bucket skew 和 FIFO backpressure，论文基本未讨论。

容量也是硬边界。U50 的 8GB HBM 在论文实验中能放 9M embeddings，理论上约 32M embeddings；对 billion-scale retrieval，需要 sharding、多卡或外部内存协同。论文在 Discussion 提到 multi-card cooperation 和 HBM utilization，但没有实现或评估跨卡 Top-K merge、routing、consistency 或 network overhead。

最后，SNARY 的 fuzzy search 与现代 ANN design space 的关系还不充分。Faiss 的 IndexIVFFlat 是常用 baseline，但没有和 HNSW、PQ/OPQ、IVF-PQ、ScaNN-like 或 graph+quantization hybrids 做质量/延迟曲线比较。若业务需要更高 recall 或更低 memory footprint，LSH 的硬件友好性未必能覆盖 algorithmic gap。

## 局限与 Future Work

- **局限 1：synthetic embeddings 支撑硬件 datapath claim，但不足以支撑 retrieval quality claim。** Future work 可以用真实推荐/search embedding trace，报告 bucket skew、Recall@K、NDCG/MRR、tail latency 和业务可接受的 fuzzy/exact switching policy。
- **局限 2：online update 和 consistency 只被轻描淡写提到。** Future work 应实现双版本 hash/index table、增量 bucket rebuild、更新期间 query correctness 语义，并测量 update throughput 与服务抖动。
- **局限 3：单卡 HBM 容量限制了 corpus scale。** Future work 可以做 multi-card sharding 和跨卡 Top-K merge，量化 routing、merge latency、fault domain 和 load balancing，而不是只讨论 batch parallelism。
- **局限 4：filter 和 Top-K 的压力场景还不够。** Future work 可以构造高 K/M、score-correlated、hot-bucket 和 adversarial query workloads，直接测 FIFO occupancy、backpressure、frequency degradation 和 tail latency。
- **局限 5：ANN baseline 覆盖不足。** Future work 应与 HNSW、IVF-PQ、PQ/OPQ 等更强 ANN 配置画完整 recall-latency-memory 曲线，并做 power/cost-normalized comparison。

## 相关

- **相关概念**：[[Embedding-Based-Retrieval]]、[[SmartNIC]]、[[FPGA]]、[[HBM]]、[[LSH]]、[[ANN]]、[[Top-K-Selection]]
- **同类系统**：[[Faiss]]、[[FAERY]]、[[CXL-ANNS]]
- **同会议**：[[ATC-2025]]
