# SNARY: A High-Performance and Generic SmartNIC-accelerated Retrieval System

**作者**：Qiaoyin Gan (ICT, CAS), Heng Pan (CNIC, CAS), Luyang Li, Kai Lv, Hongtao Guan (ICT, CAS), Zhaohua Wang (CNIC, CAS), Zhenyu Li (ICT, CAS), Gaogang Xie (CNIC, CAS)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/gan
**源文件**：[[atc2025-gan.pdf]]

---

## 一、背景

工业级大规模推荐系统普遍采用检索-排序（retrieval-ranking）两阶段范式。检索阶段需要从数百万甚至更多的候选库中选出数千个相关候选，通常成为性能瓶颈。随着深度学习的发展，基于向量表示学习的嵌入式检索（Embedding-based Retrieval, EBR）已成为主流方案：将所有候选项和用户查询编码为语义向量，检索过程转化为向量空间中的相似度搜索问题。

EBR 系统的核心流程包括三步：语料库访问（corpus access）、相似度计算（similarity computation）和 Top-K 选择。其中语料库访问是内存密集操作，相似度计算和 Top-K 选择是计算密集操作。

现有硬件加速方案中，GPU 有成熟的框架（如 Faiss），但 GPU 在 Top-K 选择阶段存在跨核通信开销和单核内存限制，难以支持全流水线化；FPGA 则具有可编程性和丰富的片上存储优势，但已有的 FPGA 方案（如 FAERY）仅支持精确搜索，缺乏模糊搜索的通用性。

---

## 二、要解决的问题

1. **性能问题**：随着语料库规模持续增长（百万至千万级），EBR 系统需要遍历全部候选项计算相似度并排序，检索延迟随语料库规模线性增长，严重影响用户体验。GPU 系统在 Top-K 选择阶段消耗约 80% 的延迟，且最大支持的 recall count 仅为 1024。

2. **通用性不足**：现实场景需要精确搜索和模糊搜索（ANN）的灵活切换——如高流量时段用模糊搜索降低延迟，低流量时段用精确搜索保证精度。然而现有 FPGA 加速方案（FAERY）仅支持精确搜索，无法覆盖模糊搜索需求。

3. **Top-K 模块资源消耗大**：FAERY 采用的 FIFO-based Top-K 算法需要 O(9K/2) 片上内存和 O(logK) 流水线级数，可扩展性差，随 recall count 增大工作频率显著下降。

---

## 三、洞察与设计

**关键洞察**：对于大规模语料库的检索，系统延迟主要由语料库读取时间决定（L = M/B + C）。与其在相似度计算环节做模糊化（如词法模糊、同义词扩展），不如直接模糊化语料库访问——通过 LSH 将语料库预先分桶，在线查询时只读取命中桶及其邻居桶中的候选项，从而将语料库规模 M 缩减为 M'，直接降低占主导地位的读取延迟。

基于这一洞察，SNARY 的整体设计如下：

- **HBM 存储与并行读取**：利用 FPGA 上的 HBM（High Bandwidth Memory）存储大规模语料库，采用水平存储策略将 embedding 均匀分布到多个 HBM 通道，实现并行读取，每个时钟周期读取 N_E 个完整 embedding。

- **数据并行相似度计算**：实例化 N_E 个相似度计算单元，每个单元计算一个候选项与用户查询的相似度，与语料库读取吞吐量匹配。

- **流水线并行 Top-K 选择**：设计基于并行交换（parallel swap）的 Top-K 算法，维护一个大小为 K 的数组，每个流水线周期以 O(1) 时间复杂度完成一次更新。相比 FAERY 的 O(9K/2) 内存，仅需 O(K) 片上内存，且只占 1-2 个流水线级数（vs. O(logK)）。

- **Filter 模块**：在相似度计算和 Top-K 选择之间插入 filter，利用 Top-K 模块的前馈反馈过滤掉低于当前最小 Top-K 值的分数，平衡两个模块之间的吞吐量差异。

- **LSH-based 模糊搜索**：采用 simHash 方法将高维 embedding 映射到低维签名，构建 LSH 哈希表。在线查询时通过哈希表查找命中桶及 Hamming 距离 ≤ T_h 的邻居桶，组成新的小规模语料库后执行精确搜索。采用单表查询策略避免多表交集/并集操作破坏流水线数据流。

---

## 四、实现细节

- **硬件平台**：Xilinx AMD Alveo U50 Data Center Accelerator Card，集成 HBM2，提供 400 GB/s 带宽、8 GB 存储、32 通道并行读取。

- **语料库存储**：使用 16 个 HBM 通道存储语料库（4 GB 容量），每个 embedding（128 维 × 1 字节）存储在 4 个连续通道中，每个流水线周期并行读取 4 个 embedding。

- **相似度计算**：采用点积（dot product）度量，不同 embedding 的计算和单个 embedding 不同维度的计算完全展开（fully unrolled）。

- **Top-K 模块**：基于并行交换算法，使用数组分区（array partitioning）增加读写端口；大 recall count 时将数组分为上下游两段（各 K/2），上游接收新分数并传递替换值给下游。最后追加 K/2 个空输入周期完成排序。

- **Filter**：4 个 FIFO 管道，深度为 2K，接收相似度计算的 N_E 个分数，根据当前 Top-K 最小值反馈进行过滤或暂存。Filter 有效工作条件：1/N_E² ≥ γ - γlnγ。

- **LSH 数据结构**：2 个空闲 HBM 通道存储哈希表和索引表。对桶内 embedding 进行预处理（按通道分类、填充、重排），保证流水线并行访问。

- **Batch 支持**：单卡多计算单元共享 HBM，K=512/1024 时 batch=3，K=2048 时 batch=2，K=4096 时 batch=1。

- **网络栈**：100 Gbps TCP/IP stack 实现语料库上传、更新和结果传输。

- **资源占用**（K=1024）：LUT 26.41%，FF 14.09%，BRAM 18.42%，DSP 0.07%，频率 285 MHz。

---

## 五、实验结果

### 实验配置

- **基线**：Faiss（4× NVIDIA A100 12GB，CUDA 12.0）、FAERY（同型号 Alveo U50）
- **数据集**：128 维随机生成 embedding（1 字节/维），语料库最大 9M
- **延迟约束**：10 ms（业界通用标准）

### 精确搜索

| 指标 | SNARY vs Faiss | SNARY vs FAERY |
|------|---------------|----------------|
| 查询延迟降低 | 78.75%–83.88% | 20.91%–45.19% |
| 延迟约束吞吐量提升 | 14.12×–18.27× | 1.26×–1.64× |

- SNARY 延迟与语料库大小呈线性关系，符合理论公式
- Faiss 最大支持 recall count 为 1024，SNARY 可达 4096
- FPGA 系统（SNARY/FAERY）延迟抖动远小于 GPU

### 模糊搜索

| 指标 | SNARY vs Faiss |
|------|---------------|
| 查询延迟降低 | 85.13%–87.40% |
| 延迟约束吞吐量提升 | 20.18×–23.81× |

- 在 K_h=4, T_h=1 参数下，SNARY 与 Faiss 的 Recall 和 MRR 相近且略高
- SNARY 模糊搜索相比自身精确搜索延迟降低 78.05%–78.72%
- FAERY 不支持模糊搜索

### 参数调节

| 参数组合 | K_h | T_h | η (语料库缩减比) |
|---------|-----|-----|-----------------|
| param1 | 4 | 0 | 6.25% |
| param2 | 3 | 0 | 12.50% |
| param3 | 5 | 1 | 18.75% |
| param4 | 4 | 1 | 31.25% |
| param5 | 3 | 1 | 50.00% |

延迟缩减与语料库缩减比 η 一致，用户可根据精度/速度需求灵活选择参数。

### 能耗

SNARY 功耗优于 FAERY，得益于优化的 Top-K 模块设计。功耗与语料库大小无显著相关性，随 recall count 增加而上升。

---

## 六、批判性分析

1. **合成数据集的代表性存疑**：作者声称 SNARY 是通用检索系统且性能不受数据集语义影响，但所有实验使用随机生成的 128 维 embedding。实际推荐系统中 embedding 分布具有聚类特性，这会直接影响 LSH 分桶的均匀性和 filter 的过滤效率——论文中 filter 有效性的数学证明依赖"分数均匀分布"假设（附录 A.2），在真实数据上是否成立未经验证。

2. **基线对比不完全公平**：SNARY 使用单张 Alveo U50（约 $2,000–3,000）对比 4× A100（约 $40,000+）。虽然延迟指标上 SNARY 占优，但 Faiss 使用 IndexIVFFlat（一个 ANN 方法）作为模糊搜索基线，而非更先进的 HNSW 或 IVF-PQ。同时缺乏成本效益（cost-efficiency）和 TCO 的定量对比。

3. **语料库规模上限较低**：HBM 总容量 8 GB，16 通道存储语料库仅 4 GB，最大支持约 32M 个 128 维 embedding。实际工业场景中语料库可达数十亿级（如论文引用的 Facebook Search、阿里巴巴），单卡方案的可扩展性存在明显瓶颈。论文提到的 multi-card cooperation 仅在 Discussion 中一笔带过，未给出任何实验数据。

4. **模糊搜索的精度评估不充分**：模糊搜索的 Recall 和 MRR 仅在合成数据上测量，且只展示了与 Faiss-IVFFlat 的对比。缺少在标准 ANN 评测基准（如 ANN-Benchmarks 中的 SIFT、GloVe、Deep 数据集）上的精度-召回-延迟 Pareto 曲线。

5. **单表 LSH 策略的精度代价被低估**：论文选择单表查询（L_h=1）是为了避免多表交集/并集破坏流水线，这是一个工程妥协。但单表 LSH 的召回率理论上界远低于多表 LSH，论文未分析这一取舍对不同数据分布的影响。

6. **缺乏端到端系统评估**：论文仅评估了检索阶段的延迟和吞吐量，未考虑网络传输延迟（尽管强调 SmartNIC 在数据路径上的位置优势）、与上游/下游模块的集成开销，以及在完整推荐系统中的端到端收益。

---

## 七、AI Infra / MLSys 视角

1. **SmartNIC 作为近数据计算的加速器**：SNARY 展示了将 embedding 检索这一 AI 推理的关键子任务卸载到 SmartNIC 上的可行性。对于 AI Infra 来说，这启发了一种部署模式：将推理系统中计算模式规则、延迟敏感的子任务（如 KV cache 查找、特征检索、向量相似度搜索）卸载到网络路径上的可编程硬件，减少数据搬运开销。

2. **流水线并行 Top-K 的通用价值**：SNARY 的 O(K) 内存 Top-K 选择算法及其正确性证明具有独立的工程价值。在 LLM 推理中的 beam search、speculative decoding 的 token 验证、MoE 模型的 expert 路由等场景中，高效的 Top-K 选择同样是关键操作，该算法思路可迁移应用。

3. **HBM 利用率优化经验**：论文中关于 HBM 通道分配、embedding 水平存储策略、以及通道利用率与并行度之间的权衡分析（Equation 3-4），对在 HBM-equipped 硬件（包括 GPU 和 AI 加速器）上设计 KV cache 存储、embedding table 等数据结构有参考价值。

4. **值得跟进的方向**：
   - 将 SNARY 的 LSH 语料库过滤思路与 GPU-based 向量数据库结合，探索 SmartNIC + GPU 异构加速的 RAG 检索系统
   - 在 LLM serving 中，利用 SmartNIC 做 prefix cache lookup 或 semantic cache 匹配，在网络入口即完成请求路由
   - 探索 CXL 互连下 SmartNIC 与 host 内存池的协同，突破单卡 HBM 容量限制

---

## 八、总结

SNARY 是首个同时支持精确搜索和模糊搜索的 SmartNIC 加速检索系统，核心贡献在于：(1) 基于 HBM 的数据并行相似度计算和流水线并行 Top-K 选择架构；(2) 基于 LSH 的语料库预过滤实现模糊搜索加速；(3) 资源高效的 O(K) Top-K 算法。在精确搜索中，SNARY 比 Faiss 延迟降低 78-84%、吞吐量提升 14-18 倍；在模糊搜索中延迟降低 85-87%、吞吐量提升 20-24 倍。主要局限在于仅使用合成数据评估、单卡语料库容量有限（~32M embedding），以及缺乏端到端系统层面的验证。
