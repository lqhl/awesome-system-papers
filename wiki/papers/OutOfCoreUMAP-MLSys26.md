---
type: paper
name: OutOfCoreUMAP
full_title: "Massive-Scale Out-of-Core UMAP on the GPU"
authors: [Jinsol Park, Corey J. Nolet, Akira Naruse, Edward Raff, Tim Oates]
venue: MLSys
year: 2026
tags: [umap, gpu, out-of-core, knn-graph, cuml, data-mining]
source_pdf: "[[5f93f983524def3dca464469d2cf9f3e.pdf]]"
source_md: "[[5f93f983524def3dca464469d2cf9f3e]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Massive-Scale Out-of-Core UMAP on the GPU (MLSys 2026)

> **一句话总结**：基于 all-neighbors kNN 构图占 UMAP 端到端 75–99% 且必须驻留全量数据的观察，用 IVF+spilling 的 out-of-core 多 GPU 分 cluster 独立构图再 merge，突破单卡显存限制；单 GPU 小数据集 **22.7×** 端到端加速，MIRACL 8 GPU **74×**（外推 CPU）、预计算 kNN 后 **121×**，trustworthiness 与 CPU 参考实现相当。

## 问题与动机

[[UMAP]] 是探索式数据分析与下游 ML 预处理中的核心流形学习工具，但第一步 **all-neighbors kNN 构图** 在 CPU 上对数十到数百 GB 向量需数小时到数天。与在线向量检索不同，all-neighbors 要求每个点既作 train 又作 query，计算与内存都随 $N$ 急剧膨胀。

既有 GPU UMAP（Nolet et al. 2021）把 UMAP 端到端搬到 GPU，但构图仍占 **75–99%** 时间，且 **全量数据必须 fit 单卡显存**——这是大规模数据集上的硬瓶颈。CPU 参考实现（pynndescent）在 Wiki-all / MIRACL 规模上即使 2TiB 主机内存也无法完成端到端运行（MIRACL 16M 子样本已需 ~1.4TB）。论文要解决的问题是：**在 GPU 显存远小于数据集时，如何高效、保质地完成 all-neighbors 构图并支撑交互式 UMAP 探索**。

## 关键观察 / 隐含假设

- 观察 1：all-neighbors 构图是 UMAP 在 CPU 与 GPU 上的共同主导瓶颈，且占比随规模增大。 Figure 1 显示 GPU brute-force 构图在较大数据集上占端到端 99%，CPU approximate 构图也超 75%；quadratic brute-force 使该比例随 $N$ 继续上升。
  - **依赖假设**：UMAP 后续步骤（fuzzy simplicial set、layout optimization）相对构图已可忽略；用户关心的是 **端到端** 而非仅构图。
  - **可能失效场景**：极小数据集或已预计算 kNN 并反复调 layout 参数时，瓶颈会转移到 embedding 优化；论文主要覆盖「每次重跑构图」的探索式 workflow。
- **观察 2：标准 IVF / uniform sharding 的 all-neighbors 需要 all-to-all 向量广播或多播，多 GPU 扩展性差。** 与 DiskANN、Faiss multi-GPU 的 search-oriented 优化不同，all-neighbors 要求每个向量参与全局邻居搜索，partition 间通信成为硬伤。
  - **依赖假设**：**分 cluster 完全独立构图 + spill 跨 partition 连接 + 全局 merge** 能在避免 all-to-all 的同时保持足够 kNN recall。
  - **可能失效场景**：数据分布极度不均匀、cluster 边界处真实邻居跨多个 distant partition 时，小 $s$ 可能漏邻居；需增大 spill factor 换计算量。
- **观察 3：分层 balanced k-means 子样本足以代表全局空间结构，用于划分 $c$ 个近似均衡的 cluster。** 在 $N_c \ll N$ 的子样本上跑两层 balanced k-means，得到 $\sqrt{c} \times \sqrt{c}$ 层次结构。
  - **依赖假设**：子样本对整体分布 **representative**；balanced 划分使每 cluster 工作量均匀，利于多 GPU load balance。
  - **可能失效场景**：长尾/多模态分布下子样本可能欠采样稀有区域；degenerate tiny cluster 虽被启发式 split 处理，但 spatial locality 仍可能变差。
- 假设 1：最终全局 all-neighbors 图（$N \times k$ 的 dists/inds）能驻留 单张 GPU 显存。
  - **证据强度**：强（方法设计显式依赖）；论文承认这是 **primary limitation**，上界约为单卡可容纳的 $N \times k$ 图规模。
- 假设 2：对 Wiki-all / MIRACL 的 CPU 端到端时间做 power-law 外推（$T(N)=aN^b$）是 保守上界，因不存在公开多节点 CPU UMAP。
  - **证据强度**：中–弱。作者明确外推 **高估** CPU（完美线性扩展、零通信开销），使 74× claim 偏保守；但 32M MIRACL 子样本在 2TiB 机器上已 OOM，外推区间较短。

## 核心方法

### 四步 out-of-core all-neighbors 构图

受 DiskANN clustered graph-build 与 IVF **spilling** 启发，但 **不做 online query routing**，而是在每个 partition 上 **独立** 构建 local all-neighbors 图，再 stitch 为全局图。实现开源于 NVIDIA **cuVS**（独立构图框架）与 **cuML**（端到端 UMAP）。

1. **分层 balanced k-means**：从数据集随机抽 $N_c$ 向量在 GPU 上聚类；meso 层分 $ \sqrt{c} $ 粗 cluster，每层内再细分为 $\sqrt{c}$ fine cluster，共 $c$ 个近似均衡 partition；过小 cluster 被移除并由最大 cluster 分裂补偿。
2. **Spilling 分配**：每向量分配到最近 **$s$** 个 cluster（非硬划分），CSR inverted index 记录 cluster→vector 映射，保证边界邻居跨 partition 可见。
3. **Per-cluster local kNN**：按 inverted index 从 host gather 向量到 GPU，在单卡内构图（支持 brute-force 或 nn-descent）；每 cluster 约 $N \cdot s / c$ 向量，$c$ 与 $s$ 控制峰值显存。
4. **Global merge**：维护单卡上的全局 CSR 图；每完成一个 local 图，用 CUDA kernel 做行级 **2k→k** 合并排序（CUB BlockMergeSort）+ 去重，映射回全局 index。

### 多 GPU 扩展

- **Cluster 分配阶段**：各 GPU 处理约 $N/n_{gpu}$ 向量的 batch assignment。
- **Local 构图阶段**：各 GPU 处理约 $c/n_{gpu}$ 个 cluster，**无需 inter-GPU 向量通信**。
- **Merge 阶段**：各 GPU 将 local 图 merge 进全局图；可选 hierarchical tree reduction 降低同步点。

参数 $(c, s)$ 构成显存–精度–耗时三角：`$z = s/c$` 固定时增大 $s$ 可提升 kNN recall/trustworthiness，但线性增加每 cluster 计算量；增大 $c$ 缩小每 cluster 规模、降低峰值显存（Wiki-all 上 $c: 16 \to 64$ 时峰值显存约减半）。

### 与 UMAP 的衔接

构图的固定度 $k$ 对应 UMAP 的 `n_neighbors`，直接控制 local vs global structure 权衡。构图完成后，其余 UMAP 步骤沿用 Nolet et al. 2021 的 GPU 加速实现。

## 设计取舍

- **近似构图 vs 精确构图**：spilling + per-partition ANN 换取 out-of-core 可行性；trustworthiness 与 CPU pynndescent 接近，但非 bitwise 等价。
- **避免 all-to-all vs 重复计算**：向量可属于 $s$ 个 cluster，同一向量可能在多个 local 图中被 distance 计算，换通信消除。
- **单卡全局图 vs 多卡分片图**：merge 全程在单 GPU 全局图上进行，简化正确性但 **硬性限制最大 $N$**；merge kernel 高度优化（单次 merge 占 kNN 构图 **0.4%**），不是当前瓶颈。
- **子样本聚类 vs 全量聚类**：$N_c \ll N$ 使聚类可 fit GPU，但引入 partition 质量对下游 recall 的依赖。
- **CPU 侧 nn-descent 辅助**：GPU nn-descent 实现含多线程 CPU 操作；多 GPU 时每 GPU 分到的 CPU 核减少，造成 **sublinear strong scaling**（8 GPU 时该 CPU 阶段占 kNN 构图 **13%**）。

## 实验与结果

**环境**：NVIDIA DGX，8× H100、Intel Xeon 8480CL（224 核）、2TiB RAM。对比 CPU 参考 UMAP（pynndescent + Numba JIT，全核）。

**数据集**：Amazon Reviews 四类（Beauty 640K×384 至 Electronics 16.8M×768）、Wiki-all（88M×768）、MIRACL（多语言 Wikipedia passage embedding）。大表超过单卡显存。

**主结果（端到端，各自构图）**：
- 小数据集（CPU 可跑完）：单 GPU **22.7×** 加速（abstract 声明；Figure 3b 覆盖多 scale）
- Wiki-all / MIRACL：8 GPU 端到端 **74×** vs **外推** CPU（MIRACL 全量）；trustworthiness 与 CPU 相当
- GPU 预计算 kNN + 剩余 UMAP 步骤：MIRACL 最大 **121×**；trustworthiness 无明显下降
- 2D embedding 视觉检查与 CPU 高度一致（Figure 5；UMAP 对全局旋转/平移不变）

**kNN 构图专项（Table 2, k=15）**：
- 单 GPU Beauty：**5.6s**；Appliances **18.7s**
- 8 GPU Wiki-all / MIRACL：秒级到分钟级（具体表值见 source_md；MinerU 表格 OCR 可能有噪声）

**多 GPU scaling（Figure 6）**：
- 端到端时间随 GPU 数下降；trustworthiness 对 GPU 数不敏感
- kNN 构图 speedup 次线性：MIRACL 上 GPU compute-bound 比例更高，扩展优于 Wiki-all

**参数敏感性（Figure 7, Wiki-all）**：
- 固定 $s=2$，$c: 16 \to 64$：峰值显存约减半，trustworthiness 略降
- 固定 $z=s/c$，增大 $s$：trustworthiness 升、runtime 升

**与替代方案（Appendix）**：
- vs Faiss multi-GPU IVF-PQ（4×H100，匹配 recall）：**3.5×–19.8×** 更快（规模越大差距越大）
- vs LargeVis CPU kNN：**20×**（Beauty）、**41×**（Appliances）
- vs TorchDR / GPUMAP：小数据集上 TorchDR 慢 **5.7×** 且 Food 数据集 H100 OOM；GPUMAP 质量/性能均不足

**正确性指标**：trustworthiness（Monte Carlo 子采样近似）+ 2D 可视化；作者承认 trustworthiness 有时与视觉保真度不一致。

## Critical Analysis

### 论证链条

链条 **bottleneck 测量 → IVF+spilling 避免通信 → out-of-core per-cluster 构图 → merge 保质量 → 大幅加速** 整体闭合。PIKE 式 ablation 虽无，但 Figure 7 的 $(s,c)$ sweep、Appendix E 的 recall@k、与 Faiss/LargeVis 对比支撑「近似构图足够好且更快」。

较弱环节是把 **74× / 121×** 与「交互式大规模 UMAP」直接挂钩：大表 CPU 数字是 **外推** 而非实测；且实验仅限 **单节点多 GPU**，未验证跨节点或生产 ETL pipeline 中的 I/O 与 host gather 开销。

### 假设压力测试

- **全局图单卡上限**：$N \times k$ 的 dists/inds 必须 fit 一张 GPU——这是比「数据集 fit 单卡」更松但仍存在的硬顶。十亿级向量、较大 $k$ 或 float64 距离可能再次 OOM；论文 Future work 指向 system memory / NVMe，说明作者认知到该边界。
- **Spill 质量与数据几何**：高维 embedding、极度不均匀密度时，$s=2$ 可能不足；增大 $s$ 缓解但计算近线性上升。用户需按 Equation (1) 风格估算显存并调 $(c,s)$——**运维复杂度**高于「一键 UMAP」。
- **子样本聚类代表性**：罕见簇、领域漂移数据可能 partition 不佳，错误无法被后续 UMAP 参数完全弥补；论文未做 adversarial / heavy-tailed 分布实验。
- **Workload 外推**：结论建立在 **text embedding**（384–768 维）与探索式降维；若用于 genomics 等高维稀疏数据，gather/merge 与 nn-descent 行为可能不同——论文未覆盖。

### 实验可信度

- **Baseline 公平性**：CPU 用最快公开单节点实现 + **乐观外推**，对大表加速比偏保守，方向可信。但未与 **仅预计算 kNN 一次、反复调参** 的生产实践对比——后者在固定 $k$ 时 CPU 仍可能「够用」。
- **质量指标**：trustworthiness 侧重 local structure，对 global structure 与下游 clustering 任务保真度覆盖不足；视觉检查仅 30K 子采样点。
- **缺失面**：无 multi-node GPU、无 AMD GPU、无端到端 cloud object storage 直读、无与 CPU nn-descent 在同等 approximate 质量下的 iso-recall 端到端对比（Faiss 对比仅在 appendix 子样本上）。

### 系统性缺陷

- **Host–device 数据搬运**：每 cluster gather 全量向量子集经 PCIe；多 tenant / 慢存储下可能成为新瓶颈——**论文未量化** host I/O 占比。
- **可观测性与调参**：$(c,s)$、子样本率 $N_c/N$、local ANN 算法选择影响质量与显存，缺乏自动调参或 quality guardrail。
- **故障与一致性**：多 GPU 线程提交、部分 cluster 失败时的恢复语义 **未讨论**。
- **框架绑定**：实现嵌在 NVIDIA cuML/cuVS 生态，与 RAPIDS 栈耦合；非 CUDA 环境无法受益。

## 局限与 Future Work

- **局限 1（论文承认）**：最终 all-neighbors 图必须 fit **单 GPU** 显存，限制可达向量规模上界。
- **局限 2**：多 GPU strong scaling 次线性，部分源于 nn-descent 的 **CPU 多线程争用**（8 GPU 时相关 CPU 时间增 **1.95×** vs 2 GPU）。
- **局限 3**：最大数据集 CPU 结果为 **外推**，非实测端到端；公开多节点 CPU UMAP 缺失使对比不完整。
- **局限 4**：构图近似性依赖 $(c,s)$ 手工调优，无自动 recall–cost Pareto 选择。
- **Future work 1**：将全局图 spill 到 **system memory / NVMe**（PCIe 5+ 带宽），支持 billion-scale。
- **Future work 2**：**多物理节点** 扩展 hierarchical merge 与 cluster 调度，测量跨节点 gather 与同步开销。
- **Future work 3**：对 production embedding pipeline 做 **端到端 latency** 测量（含存储读取、重复调参 session），而非 isolated benchmark。

## 相关

- **相关概念**：[[Manifold-Learning]]、[[Approximate-Nearest-Neighbor]]、[[IVF]]、[[Embedding-Based-Retrieval]]
- **同类系统**：cuML、cuVS、pynndescent、[[Faiss]]、LargeVis、CAGRA、nn-descent
- **可复用框架**：构图算法亦适用于 Isomap、LLE、t-SNE、Laplacian Eigenmaps 等共享 all-neighbors 第一步的流形方法
- **前序工作**：Nolet et al. 2021 GPU UMAP
- **同会议**：[[MLSys-2026]]
