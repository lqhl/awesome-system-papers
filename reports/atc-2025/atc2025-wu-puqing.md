# Turbocharge ANNS on Real Processing-in-Memory by Enabling Fine-Grained Per-PIM-Core Scheduling

**作者**：Puqing Wu, Minhui Xie, Enrui Zhao, Dafang Zhang, Jing Wang (Renmin University of China); Xiao Liang, Kai Ren (Kuaishou); Yunpeng Chai (Renmin University of China)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wu-puqing
**源文件**：[[atc2025-wu-puqing.pdf]]

---

## 一、背景

Approximate Nearest Neighbor Search (ANNS) 是数据库和 AI 基础设施中的核心组件，广泛应用于搜索、推荐、RAG 等场景。ANNS 具有极高的内存访问密集度，计算与内存访问比接近 1:1。传统 CPU 方案受限于 DRAM 带宽（约 200 GB/s），GPU 方案受限于显存容量（如 H100 仅 100 GB），均难以同时满足大规模向量检索对容量和性能的需求。

Processing-in-Memory (PIM) 是解决内存墙问题的经典思路。2022 年发布的 UPMEM 是全球首款商用 PIM 硬件，单服务器可提供 2,560 个 Processing Unit (PU)、超过 40,000 线程、聚合内存带宽达 2 TB/s，理论上非常适合内存密集型的 ANNS 工作负载。

---

## 二、要解决的问题

现有 PIM 编程模型采用 **batching 范式**，导致硬件利用率极低——在 UPMEM 上运行 ANNS 仅能达到理论吞吐上限的 18.2%，超过 65% 的时间 PU 完全空闲。具体表现为两类利用率不足：

1. **Inter-batch 利用率不足**：UPMEM 复用 DDR 总线，CPU 和 PU 无法同时访问内存。batch 范式要求在两个 batch 之间由 CPU 独占总线进行数据拷贝，期间所有 PU 空闲，这段空闲时间占单个 batch 时长的 65%。

2. **Intra-batch 利用率不足**：PU 之间采用 share-nothing 架构，无法互相访问内存。batch 内各 PU 的负载不均衡导致部分 PU 提前完成后空等，整个 batch 被最慢的 PU 拖慢。

---

## 三、洞察与设计

**关键洞察**：每个 PU 拥有一个额外的、未公开文档记录的控制接口（原本用于 PIM kernel 的启动和同步等控制命令），该接口完全绑定 DDR 总线。可以利用这个控制接口实现对每个 PU 的 DDR 总线访问权的细粒度仲裁，从而打破"CPU 和 PU 只能在 batch 边界交互"的传统假设。

基于此洞察，PIMANN 提出 **per-PU 调度范式**，取代传统的 batch gang-scheduling。核心设计包括：

- **Persistent PIM Kernel**（解决 inter-batch 问题）：系统初始化时只启动一次 PIM kernel，PU 持续运行，通过消息队列不断接收和处理查询请求，消除 batch 间的空闲期。
- **Per-PU Query Dispatching**（解决 intra-batch 问题）：根据每个 PU 的实时负载动态分发查询，配合选择性复制热点 cluster 到多个 PU，实现负载均衡。

---

## 四、实现细节

### Hot Transfer 机制

- **控制路径**：在 WRAM 上实现消息队列，通过控制接口链路传输（绕过 DDR 总线），用于传递元数据和控制消息（如查询 ID、ownership 切换通知）。
- **数据路径**：修改 UPMEM 驱动，暴露 MRAM 给 CPU 进行直接读写。构建变量符号到 MRAM 地址的映射表，解决驱动原本不支持 PIM 运行时 CPU 访问 MRAM 的限制。需要对数据进行 transpose 操作以适配 memory-level parallelism。

### Per-PU 总线 Ownership 切换

- 通过 MUX 寄存器控制每个 PU 的总线归属（CPU-side 或 PU-side），将 MUX 映射暴露到用户空间。
- 发现两个相邻 PU 共享一个物理 MUX 寄存器，因此最小切换粒度为两个相邻 PU（pairwise switching）。
- 采用 **pairwise cluster slicing**：将每个 IVF cluster 切成两片分配给相邻 PU 对，确保两个 PU 始终同时活跃。

### Coroutine 优化

- 使用协程隐藏总线 ownership 切换延迟（单 rank 64 个 PU 的消息队列轮询需 0.9 ms）。
- 协程调度优先处理 ownership 已切换到 CPU 侧的 PU，并基于 PU 确定性执行时间预测 ownership 可用时机。

### 选择性复制数据放置

- 按 cluster 热度（size × access frequency）决定副本数量：`replica_count_i = p_i / p_avg`。
- 将 cluster 切成统一大小的 slice，MRAM 按固定长度 slot 分配，减少内存碎片。
- 支持运行时热度漂移检测和动态数据放置调整，无需关闭 PIM。

### 在线请求分发

- 维护 cluster ID → PU ID 映射表，dispatcher 选择当前负载最轻的副本发送请求，负载用消息队列深度表示。

---

## 五、实验结果

**实验平台**：双路 Intel Xeon Silver 4210 (20 物理核，2.4 GHz)，128 GB DDR4，20 块 UPMEM DIMM（2,560 PU，400 MHz），NVIDIA RTX A6000。Ubuntu 22.04，kernel 5.15。

**数据集**：SIFT-1B（10 亿 128 维向量）和 SPACE-1B（10 亿 100 维向量）。

**主要结果**（recall@10 = 0.9）：

| 指标 | PIMANN vs Faiss-CPU | PIMANN vs PIMANN-Batch | PIMANN vs Faiss-GPU |
|------|---------------------|------------------------|---------------------|
| 吞吐 (QPS) | 5.9-10.4× | 2.4-2.9× | 2.4-3.7× |
| 平均延迟 | — | 降低 32-43% | — |
| P99 尾延迟 | — | 降低 26-63% | — |
| PIM 利用率 | — | 65-83% vs ~20% | — |
| 能效 (QPS/W) | — | — | 1.6-2.5× |
| 成本效率 (QPS/$) | 2.4× | — | 4.8× |

**技术拆解**：

| 技术 | 吞吐增益 |
|------|---------|
| Persistent PIM Kernel | +30%-70% |
| Per-PU Query Dispatching | 再 +88%-112% |
| Coroutine 优化 | ~3× (vs 无协程) |

**成本效率**：

| 方案 | 价格 ($) | QPS | QPS/$ |
|------|---------|-----|-------|
| Faiss-CPU | 1,500 | 144 | 0.096 |
| Faiss-GPU | 9,685 | 478 | 0.049 |
| PIMANN | 5,473 | 1,276 | 0.233 |

---

## 六、批判性分析

1. **仅支持 cluster-based ANNS（IVFPQ）**：论文明确承认 graph-based 方法不适合 UPMEM（PU 间通信带宽仅 0.41 GB/s），但 graph-based 方法（如 HNSW、Vamana）在实际部署中往往比 IVF 系列有更好的 recall-throughput 权衡。这意味着 PIMANN 只能在 IVF 算法的范围内比较，其通用性受限。

2. **GPU 基线选择存疑**：与 Faiss-GPU 的比较中，GPU 端只使用了一块 RTX A6000，而 UPMEM 侧使用了 20 块 DIMM。虽然论文强调了价格和功耗的对比，但未考虑现代 GPU 端的优化方案（如 CAGRA）。Faiss-GPU 的 IVFPQ 实现并非 GPU ANNS 的最优方案。

3. **UPMEM 硬件的可获取性**：论文的所有优化都依赖 UPMEM 这一特定硬件，且涉及未文档化的控制接口和驱动修改。UPMEM 硬件的商业可获取性有限，未来硬件迭代是否保持兼容性尚不明确（尽管论文在 Discussion 中做了乐观论述）。

4. **pairwise 切换的代价被弱化**：两个相邻 PU 共享 MUX 导致必须成对切换，论文用 pairwise cluster slicing 来缓解资源浪费。但这引入了额外的设计约束和碎片化问题，论文对此的开销分析不够充分。

5. **动态负载均衡的 overhead 未充分量化**：热度检测、动态副本迁移、在线 cluster 复制调整等机制的 CPU 侧 overhead 没有单独量化。在高 QPS 场景下这些额外操作是否成为瓶颈未被讨论。

6. **功耗数据不利但被轻描淡写**：UPMEM 总功耗 462 W 而 GPU 仅 300 W，论文用 "future PIM designs can reduce it" 一笔带过。当前硬件世代的实际能效优势来自更高的 QPS，而非更低的功耗。

---

## 七、AI Infra / MLSys 视角

1. **RAG 系统的向量检索加速**：PIMANN 直接适用于 LLM RAG pipeline 中的向量检索环节。在大规模知识库场景下（十亿级向量），PIM 方案比 GPU 有更好的容量扩展性，可作为 RAG 推理系统的专用检索硬件。

2. **PIM 编程模型的通用启示**：论文发现的 per-PU fine-grained scheduling 范式对其他 PIM 应用有借鉴价值。现有 PIM 应用（数据库 join、稀疏矩阵运算、CNN 推理等）普遍采用 batch 范式，persistent kernel + per-core scheduling 可能是提升 PIM 利用率的通用方法。

3. **Embedding 存储与检索的异构架构**：可以设想 GPU 负责 embedding 生成（encoding），PIM 负责大规模向量存储和检索（decoding/search），形成异构推理流水线。这需要解决 GPU-PIM 之间的数据传输问题。

4. **值得跟进的方向**：
   - 在 PIM 上实现 graph-based ANNS（需要解决 PU 间通信瓶颈，可能结合 CXL 互连）
   - 将 persistent PIM kernel 思路推广到 Attention 计算中的 KV cache 查找（内存密集、计算轻量）
   - 探索下一代 PIM 硬件（如 Samsung HBM-PIM、SK Hynix AiM）上的 ANNS 系统设计

---

## 八、总结

PIMANN 通过发现并利用 UPMEM 的未文档化控制接口，实现了从 batch gang-scheduling 到 per-PU fine-grained scheduling 的范式转变，将 PIM 利用率从 ~20% 提升至 65-83%。系统在十亿级向量数据集上实现了相比 Faiss-CPU 5.9-10.4×、相比 GPU 2.4-3.7× 的吞吐提升，且成本效率是 GPU 方案的 4.8×。主要局限在于仅支持 cluster-based ANNS 算法、依赖特定 PIM 硬件、以及 UPMEM 当前世代较高的功耗。
