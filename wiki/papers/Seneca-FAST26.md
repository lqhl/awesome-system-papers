---
type: paper
name: Seneca
full_title: "Preparation Meets Opportunity: Enhancing Data Preprocessing for ML Training With Seneca"
authors: [Omkar Desai, Ziyang Jiao, Shuyi Pei, Janki Bhimani, Bryan S. Kim]
venue: FAST
year: 2026
tags: [ml-training, data-loading, caching, dsi-pipeline, pytorch]
source_pdf: "[[fast2026-desai.pdf]]"
source_md: "[[fast2026-desai]]"
---

# Preparation Meets Opportunity: Enhancing Data Preprocessing for ML Training With Seneca (FAST 2026)

> **一句话总结**：在 multimedia ML 并发训练且 [[DSI-Pipeline]] 受 CPU–GPU 差距（4.63–7.66×）与 random sampling 拖累的前提下，Seneca 用性能模型做 encoded/decoded/augmented 三态 cache 最优分区（MDP）+ 跨 job 机会性优先服务 cache 命中样本（ODS），相比 [[PyTorch]] 缩短 makespan **45.23%**，DSI 吞吐相对 next best dataloader 至多 **3.45×**，且不损训练精度。

## 问题与动机

并发训练 image/video/audio/[[DLRM]] 等多媒体模型时，data storage and ingestion (DSI) pipeline——从远端存储 fetch、decode、augment、collate 再喂给 GPU——常常比 gradient computation 更慢。Figure 1 显示 CPU 与 GPU peak TFLOPS 差距持续扩大，SwinT 等模型在 RTX 5000 到 A100 系统上 DSI 与训练吞吐差距从 **4.63×** 增至 **7.66×**。有限 host DRAM 迫使更多数据从慢存储重复读取，GPU 等待数据导致 utilization 下降。

已有 caching 方案（[[MINIO]]、[[SHADE]]、[[Quiver]]、PRESTO、Revamper、[[Cachew]]、[[Pecan]]、[[FastFlow]]）主要优化 fetch 或 offload 预处理，但作者指出两个未被系统对待的核心难题：

1. **Cache 哪种数据形态？** 训练数据可存为 encoded（密度高、需 CPU decode+augment）、decoded（中等）、augmented（最 ready 但体积可达 encoded 的 **15×**、跨 epoch 复用 augmented 样本易过拟合）。最优形态取决于 cache 容量、CPU/GPU/NIC/PCIe/远端 cache 带宽中谁是最慢环节——这是一个多变量非线性问题，而非「总 cache 越大越好」。
2. **并发 job 不互助**：[[Random-Sampling]] 使 OS page cache 的 LRU 在随机访问下失效（dataset 从 400GB 增至 600GB 时 [[PyTorch]] DSI 吞吐降 **67.34%**、[[DALI]] 降 **28.41%**）；多 job 共享同一 dataset 时各自独立预处理（4 jobs 跑 1.7M OpenImages 样本却产生 **7.16M** 次 preprocess）。[[SHADE]] 的 importance sampling 跨 job 不兼容；[[Quiver]] 的 substitution 需 **10× oversample**，带来带宽争抢。

Seneca 针对 **data parallelism 下、预处理重的多媒体训练、多 job 共享 dataset** 这一部署形态，把 cache 分区与 sampling 策略联合优化。

## 关键观察 / 隐含假设

- **观察 1：cache 形态选择对容量高度敏感，不存在全局最优单形态策略**。
  - **依赖假设**：样本大小膨胀因子 M（论文 ImageNet 上约 **5.12×**）、远端 cache 带宽与 CPU augment/decode 速率可 profile；训练 job 的 augment 在 epoch 内随机、跨 epoch 不应重复同一 augmented tensor。
  - **可能失效场景**：450GB cache 时 augmented 形态节省 preprocess **69.91%**；250GB 时仅节省 **11.36%** 且 fetch 时间反增 **87.2%**（Figure 3）。若 cache 远小于 dataset（如 ImageNet-22K 1.4TB vs 400GB cache），MDP 会退化为 **100% encoded**，ODS 成为主要增益来源——形态收益随硬件代际（更快 CPU 削弱 decoded/augmented 优势）剧烈变化。

- **观察 2：random sampling 下 cache 命中率可被「跨 job 的 unseen hit 替换」系统性抬高，且不必牺牲 epoch 内样本唯一性**。
  - **依赖假设**：多个并发 job 训练 **同一 dataset**（相同样本 ID 空间）；每个 epoch 每样本恰用一次；augmented cache 的 eviction threshold 设为并发 job 数，保证跨 epoch 不重复同一 augmented 样本；替换后 batch 顺序仍「看起来随机」。
  - **可能失效场景**：各 job 用不同 dataset、不同 augment policy、或 strict reproducibility 要求固定 pseudo-random 序列时 ODS 不适用；job 数动态变化时需重算 eviction threshold 与 MDP 分区（论文在初始化时算一次）。

- **观察 3：DSI 吞吐可由「四路径 min-bottleneck 模型」较好预测，Pearson 相关 ≥0.90**。
  - **依赖假设**：homogeneous n-node 集群上 GPU/CPU/NIC/PCIe 性能线性乘以 n；远端 cache/storage 带宽可抽象为训练节点视角的最大可达带宽；gradient sync（ring-reduce）开销可叠加到 NIC/PCIe 有效带宽上；NVLink 集群上 intra/inter-node 通信开销可为 0。
  - **证据强度**：**强**——4 平台 × 6 种分区 × 变 dataset size，24 组对比相关 ≥0.90；2×in-house 时瓶颈正确预测为 **10 Gbps** 远端 cache 带宽。
  - **可能失效场景**：heterogeneous 集群、pipeline/model parallelism、storage 尾延迟波动、或 profile 参数随负载漂移时，模型可能系统性偏差；论文未在线重 profile。

- **假设 1：CPU 侧预处理是默认路径，远端 [[Redis]] in-memory cache 是合理部署**。
  - **证据强度**：**中**——实现基于 [[PyTorch]] v1.12.0 + Redis，但论文承认概念可扩展到 [[DALI]]/GPU/FPGA 加速路径；生产环境未必愿意维护独立 Redis 集群与网络 hop。

- **假设 2：对比 baseline 的公平重实现足以代表原系统能力**。
  - **证据强度**：**弱**——[[Quiver]]、[[MINIO]] 非开源，作者在 [[PyTorch]] 上忠实复现；[[SHADE]] 用公开版但未调优；与原生 [[DALI]] GPU pipeline 的对比受 GPU 显存限制（in-house/AWS 上 2+ concurrent job 时 DALI-GPU OOM）。

## 核心方法

Seneca = **Model-Driven Partitioning (MDP)** + **Opportunistic Data Sampling (ODS)**，在 [[PyTorch]] dataloader 上约 **4200 LOC** 修改，远端 cache 用 [[Redis]]（可替换为任意低延迟 KV）。

**MDP（回应观察 1、3）**：为 data parallel 训练建立 DSI pipeline 性能模型（Figure 5）。按数据所在位置分四条路径，各自吞吐为 cache bandwidth、NIC、PCIe、GPU ingestion、CPU decode/augment 的 **min**：

- $DSI_A$：augmented 命中 cache——瓶颈可能在 $B_{cache}/(M \cdot S_{data})$ 或 GPU/NIC/PCIe。
- $DSI_D$：decoded 命中——额外受 CPU augment 速率 $T_A$ 限制。
- $DSI_E$：encoded 命中——受 $T_{D+A}$ decode+augment 限制。
- $DSI_S$：storage fetch——在 $DSI_E$ 基础上再受 $B_{storage}$ 限制。

给定 cache 容量比例 $(x_E, x_D, x_A)$，用 Equations 2/4/6 计算各形态可缓存样本数 $N_A, N_D, N_E$，再按 Equation 9 加权得 $DSI_{overall}$。初始化时用 **1% 粒度 brute-force** 搜索最优三分区（<1s，每 dataset 算一次）。Table 6 显示同一 dataset 在不同硬件上最优分区差异很大（如 ImageNet-1K 在 in-house 为 58-42-0，Azure 单节点为 0-48-52）。

**ODS（回应观察 2）**：维护两类元数据：(i) per-job **seen bit vector**（epoch 内样本唯一性）；(ii) per-dataset **status + reference count**（样本在 augmented/decoded/encoded/storage 哪一层）。batch 请求时，对 cache miss 的样本，若存在同 batch 中 unseen 的 cache hit，则替换；hit 的 refcount++；refcount 达 job 数阈值时后台线程 evict 并以伪随机样本 refill。epoch 结束重置 seen vector。ImageNet-1K 上 8 job 并发仅 **2.6MB** 元数据，替换逻辑为 O(1) 内存操作。

**与 [[Quiver]] 的差异**：ODS 不做 oversample，无额外 fetch 带宽浪费；与 [[SHADE]] 的差异：不依赖 per-job importance，可跨 job 共享 cache 层。

## 设计取舍

- **模型精度 vs 实现简单**：brute-force 1% 分区搜索 + 静态 profile 参数，换取可解释、低开销的初始化；未做在线自适应或学习型分区。
- **吞吐 vs 采样严格性**：ODS 放宽「必须遵循预生成 pseudo-random 序列」，换取更高 cache 命中；用 seen vector + eviction threshold 守住 epoch 唯一性与跨 epoch augment 不复用。
- **远端 cache vs 本地 DRAM**：Redis 使多 job/multi-node 共享预处理结果，但引入 NIC/cache 带宽新瓶颈（2×in-house 仅 **1.62×** 扩展 vs Azure 80Gbps 下 **1.89×**）。
- **CPU 预处理 vs GPU offload**：坚持 CPU augment 保留 user-defined transform 灵活性；放弃 [[DALI]] 式 GPU pipeline 在并发时的显存优势。
- **边界条件**：dataset ≪ DRAM 时 OS page cache 已足够，Seneca 相对 [[PyTorch]] 优势缩小（ImageNet-1K on 880GB DRAM Azure，stable ECT 仅比 PyTorch 好 **31.36%** for ViT-h）；dataset ≫ cache 时 MDP 倾向 encoded-only，ODS 成为主要差异化；单 job 时 ODS 收益随并发 job 数增加而增大。

## 实验与结果

- **模型验证**：4 硬件配置 × 6 cache 分区，model vs measured DSI 吞吐 Pearson **≥0.90**；大 dataset 下单形态 cache 时 encoded 优于 augmented，双分区时最优配置非显然（Figure 8）。
- **端到端收敛**：Azure 上 ResNet-18/50、VGG-19、DenseNet-169 训练 250 epochs，Seneca 相对 [[PyTorch]] 加速 **38–49%**，相对 [[DALI]] **60–71%**；final top-5 accuracy 误差 **<2.83%**（Figure 9）。
- **多 job makespan**：AWS 上 12 job（最多 2 并发）scheduler 仿真，总训练时间降至 [[PyTorch]] 的 **45.23%**；后启动的 DenseNet-169 因共享 cache 反而比单独跑的第 6 个 job 更快（6.97h vs 7.84h）。
- **并发吞吐**：Azure 4×A100、400GB cache、4 concurrent job，聚合 DSI 吞吐比 [[Quiver]] 高 **1.81×**；GPU utilization **98%** vs PyTorch **72%**、CPU **54%** vs PyTorch **88%**（Table 8）。
- **Cache 命中率**：三模型并发训 ImageNet-1K，仅 cache **20%** dataset 时命中率 **54%**（比 Quiver 高 **11%**）；60–80% cache 时 [[SHADE]] 命中率更高但吞吐仍最慢（单线程）。
- **跨模型/数据集**：7 模型（3.4M–633.4M 参数）× 3 数据集（142GB–1.4TB）× 5 硬件；OpenImages 上 stable ECT 比 DALI-CPU 低 **47–87%**；ImageNet-22K 上 Seneca 平均比 next best 低 **29.35%** ECT，SwinT 达 **8.37×**；ViT-h stable ECT 比 next best（PyTorch）低 **31.36%**，ResNet-50 比 [[MINIO]] 快 **3.45×**。
- **分布式扩展**：2×Azure Seneca 比单节点 **1.89×**，比 MINIO 高 **42.39%**；2×in-house 受 10Gbps 限制仅 **1.62×**。
- **开源**：https://github.com/swiftomkar/seneca-fast26-pytorch

## Critical Analysis

### 论证链条

observation → design → result 在「预处理重、共享 dataset、有限远端 cache」这一主线上较闭合：Figure 3/4 的 measurement 直接支撑「形态选择非平凡」与「并发不互助」；MDP 模型验证（r≥0.90）支撑分区决策可信；ODS 的命中率与 CPU/GPU utilization 数据支撑「替换 miss 不破坏吞吐且抬高 GPU 饱和」。薄弱环节在于 **把 ImageNet 类 image classification 实验外推为 general DSI 优化**：text/low-resource-demand 预处理（Table 1）几乎不在评测矩阵中；**makespan 45.23%** 来自特定 scheduler（max 2 并发、12 job 混合大小），与「GPU 集群满载多租户」的真实 arrival process 可能不符。

accuracy 论证较扎实（多模型、<2.83% 误差），但 **ODS 改变有效采样分布**——作者用 epoch 唯一性论证足够，未报告不同 random seed 间 variance 或 downstream calibration 敏感性。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 并发 job 共享同一 dataset | 实验刻意构造 | 多 tenant 各用私有数据；federated/curriculum sampling |
| Profile 参数静态且准确 | DS-Analyzer + fio 标定，模型拟合好 | 动态负载、热 throttling、NUMA 效应、cache 节点争用 |
| Redis 带宽可抽象为固定 $B_{cache}$ | 多平台验证 | cache 与训练同机争 DRAM；跨 AZ 高延迟 object store |
| ODS 保持「足够随机」 | 精度对比 | 需 bit-exact reproducibility 的研究场景；极小 dataset 上替换改变 effective epoch composition |
| NFS 代表远端存储 | 实验设定 | S3/GCS 高延迟高吞吐、checkpoint 交错读、erasure-coded 后端 |
| CPU 预处理主导 | multimedia 模型 | [[DALI]]/TrainBox/FusionFlow GPU 预处理已部署且显存充足 |

### 实验可信度

- **优势**：baseline 覆盖 PyTorch、DALI、SHADE、MINIO、Quiver、MDP-only；多硬件（RTX5000/V100/A100）、单/双节点、冷/热 cache（first vs stable epoch）；ablation 隐含于 MDP-only vs Seneca 对比。
- **局限**：Quiver/MINIO 为复现而非原版；SHADE 因单线程被反复提及但未做公平多线程改造；storage 统一 NFS **10–12 Gbps**，与 hyperscale 对象存储差异大；**无成本 metric**（Redis 内存、网络 egress、cache 填充时间）；tail latency / straggler job 未报告。
- **Scalability 上限**：4 job  on 4×A100 已达 **98% GPU**，更多并发无法继续线性加速——论文诚实报告，但也意味着 Seneca 在「DSI 已非瓶颈」时收益有限。

### 系统性缺陷

- **故障恢复与一致性**：远端 Redis cache 失效、partial write、训练 checkpoint 与 cache 不一致时行为——**论文未讨论**。
- **多 tenant 隔离**：共享 Redis 上不同 customer dataset 的 keyspace、quota、安全隔离——**论文未讨论**。
- **Cache warming 成本**：first epoch 时间（Figure 15 折线）仍显著高于 stable epoch；大规模集群同时冷启动的填充风暴——仅定性提及，无定量。
- **运维复杂度**：每 dataset×hardware 需 profile + MDP 分区 + 独立 Redis 部署；brute-force 搜索虽 <1s，但参数漂移时需人工重跑——**论文未讨论**自动化运维。
- **可观测性**：无内置 DSI bottleneck 诊断（对比 [[Plumber]]/Lobster 类工具）；ODS 替换率、各分区 hit/miss 分布未作为 first-class metric 暴露。
- **尾延迟**：只报告吞吐与 epoch 时间，**未讨论** batch 级 p99 延迟或 straggler 对 distributed sync 的影响。

## 局限与 Future Work

- **局限 1**（论文自述）：实现基于 CPU 预处理；GPU/FPGA 加速 loader 需额外适配，且 random augment 与 SIMD 加速器特性不匹配。
- **局限 2**（论文自述）：聚焦 data parallelism 下 multimedia/DLRM；未覆盖 pipeline/model parallelism 或 text 低预处理负载。
- **局限 3**（实验边界）：远端存储统一为 NFS；cache 服务带宽（10–30 Gbps）在部分配置下成为显式瓶颈，结论对高速本地 NVMe cache 或超大规模 object store 的外推需谨慎。
- **局限 4**（设计边界）：Quiver 等非开源 baseline 为复现；ODS 牺牲 strict pseudo-random 顺序，对 audit/reproducibility 场景需额外验证。
- **Future work 1**：在 **heterogeneous 集群 + 在线 profile 更新** 下测量 MDP 分区漂移频率，以及 brute-force vs 解析/学习型求解器的精度–开销 trade-off。
- **Future work 2**：与 **GPU 预处理 pipeline**（[[DALI]]、FusionFlow）在显存充足、单 job 与多 job 两端的 Pareto 曲线，而非仅 DALI-GPU OOM 场景。
- **Future work 3**：在 **真实 multi-tenant scheduler trace**（非合成 12-job 队列）上测 makespan、cache 污染与 warming 成本，并量化 Redis 内存$/训练-hour 的 TCO。
- **Future work 4**：对 **ODS 采样分布偏移** 做更细粒度统计检验（per-class recall、校准曲线、多 seed variance），验证「<2.83% accuracy 误差」在更多任务上的稳健性。

## 相关

- **相关概念**：[[Data-Loading]]、[[Random-Sampling]]、[[Caching]]、[[DSI-Pipeline]]、[[Data-Parallelism]]、[[PyTorch]]、[[Redis]]
- **同类系统**：[[MINIO]]、[[SHADE]]、[[Quiver]]、[[DALI]]、[[Cachew]]、[[Pecan]]、[[FastFlow]]、PRESTO、Revamper、Lobster、NoPFS
- **同会议**：[[FAST-2026]]
- **对比**：相对 [[Quiver]] 用「无 oversample 的机会替换」换命中率；相对 [[SHADE]] 用跨 job 兼容的 cache-aware sampling 换 importance 语义；相对 [[MINIO]]/纯 encoded cache 用三态 MDP 换 CPU decode/augment 重复劳动