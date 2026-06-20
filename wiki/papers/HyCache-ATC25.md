---
type: paper
name: HyCache
full_title: "HyCache: Hybrid Caching for Accelerating DNN Input Preprocessing Pipelines"
authors: [Keshav Vinayak Jha, Shweta Pandey, Murali Annavaram, Arkaprava Basu]
venue: ATC
year: 2025
tags: [dnn-training, input-pipeline, caching, ilp, preprocessing]
source_pdf: "[[atc2025-jha.pdf]]"
source_md: "[[atc2025-jha]]"
---

# HyCache: Hybrid Caching for Accelerating DNN Input Preprocessing Pipelines (ATC 2025)

> **一句话总结**：观察到 GPU 训练加速后 CPU 预处理成为瓶颈（消除 stall 有 1.13×–2.3× headroom），且 prior work 的 all-or-nothing、单层缓存策略浪费了大量可缓存空间；HyCache 用 profile-guided ILP 在内存与 SSD 间做 partial、exclusive、coordinated 缓存，对 6 条 pipeline 实现 1.11×–10.1× 吞吐提升、最高 1.67× 端到端训练加速。

## 问题与动机

[[DNN-Training]] 通常跨多个 epoch 重复遍历数据集。每个 sample 都要经过 CPU 端的 input preprocessing pipeline（fetch → decode → resize → normalize → augment 等）才能变成 GPU 可消费的 tensor。随着 GPU 算力持续提升，这条 CPU pipeline  increasingly 成为 critical path：Google 报告 62% 训练 job 每 epoch 至少 stall 1 ms，16% stall >100 ms；另有测量显示最多 65% epoch 时间花在预处理上。

缓解思路是跨 epoch 缓存昂贵 offline step 的中间结果。现有方案包括框架内置的 tf.data cache、[[PRESTO]]、Cachew、MinIO 等，但作者 claim 它们有四个结构性缺陷：

1. **All-or-nothing**：某 step 全部输出装不下就完全不缓存，放弃 partial reuse 机会
2. **内存与存储割裂**：要么只 cache 内存，要么只 cache 存储，不协同
3. **同 step 双层缓存**：即便两层都用，也只缓存同一 step，忽略内存与 SSD 延迟差异
4. **无 working memory 估算**：用户手动指定 cache size，易 OOM 或浪费 DRAM

HyCache 针对的是**单机、多 epoch、CPU 预处理 bound** 的训练场景，假设 pipeline 中存在大量可复用的 deterministic offline step，且系统同时拥有足够 DRAM 与本地 SSD 带宽。

## 关键观察 / 隐含假设

- **观察 1**：消除 preprocessing stall 后，端到端训练有 1.13×–2.3× 的 headroom（Figure 1，6 条 pipeline 上 preload 16K 全预处理 tensor 对比 baseline）。
  - **依赖假设**：瓶颈确实在 CPU 预处理而非 GPU 训练或网络 I/O；且 offline step 占预处理时间主体（6 条 pipeline 中 4 条 online step 时间为 0%，ImageNet/CubePP 也仅 7%–18%）。
  - **可能失效场景**：compute-heavy 模型（如 ViT-LoRA）使 GPU 成为主导，端到端加速仅 1.05×；或 pipeline 以 online augmentation 为主时缓存收益有限。

- **观察 2**：Prior work 的 all-or-nothing + 单层策略显著低估可缓存收益。Partial memory caching 单独带来 28%（Voice）/10%（Detection）提升；再加 exclusive storage 达 2.35×/24%；允许不同 step 分别缓存到 memory 与 storage 后达 5.3×/38%（Figure 2，相对不允许 partial 的 in-memory caching）。
  - **依赖假设**：中间 tensor 大小与 step 计算成本呈非单调关系（如 Detection 的 Pad vs Mux、Voice 的 Spectrogram vs Mel Filter），且数据集规模大于单层容量，partial + multi-step 才有意义。
  - **可能失效场景**：小数据集上 PRESTO 的整 step 缓存已足够（论文用小数据集实验显示 PRESTO 1.21×–2.86×），HyCache 优势收窄。

- **观察 3**：内存与存储的 per-tensor 节省 $C_{M_i}$ 普遍高于 $C_{D_i}$，但最优缓存 step 取决于 size × savings × budget 的联合优化，而非单一「最省算力」或「最小 footprint」step（Figure 3）。
  - **依赖假设**：SSD 访问延迟足以让部分 step「重算比读盘快」；profile 在 1% 数据上的 $C_{M_i}$、$C_{D_i}$、$Sz_i$ 可代表全量。
  - **可能失效场景**：远程 NFS（64.8 MiB/s 上限）下 IR-1/Segmentation 性能大幅下降；存储介质或网络带宽变化会改变 ILP 最优解。

- **假设 1**：Working memory 可用公式 $(\max(Sz_i) \times bs \times prefetch\_depth) + (mem\_per\_fetcher \times F_i) + metadata$ 稳定估算，剩余 DRAM 可安全用于 cache。
  - **证据强度**：**中**——6 条 pipeline 上 working memory 16–77 GB 的测量支撑公式结构，但 prefetch_depth 固定为 2、metadata 经验估算，未见动态 workload 压力测试。

- **假设 2**：只缓存 offline step 不影响训练正确性；online augmentation 必须每 epoch 重算以保留随机性。
  - **证据强度**：**强**——符合标准 ML 实践，Table 1/2 显示 offline 占 82%–100% 预处理时间，且论文明确不做 accuracy 对比因为不改变输出分布。

## 核心方法

HyCache 是构建在 [[Nvidia-DALI|NVIDIA DALI]] 之上的 **hybrid caching runtime**（hcLib），核心是把「缓存哪些 step、缓存多少 tensor、放在哪一层」形式化为 ILP，并自动生成多源 ingestion pipeline。

**Step Filter**：对每个 step 用 sample batch 测输出维度；连续输出大小相同的 step 序列只保留最后一个作为候选（缓存更早 step 无额外空间收益）。

**Profiler**（第一个 epoch 的前 1% 数据）：
- 计算每 step 的 $C_{M_i}$、$C_{D_i}$（式 1：raw fetch+preprocess 时间减去从 cache 接入时间）与平均 $Sz_i$
- 二分搜索最优 fetcher 数 $F_i$：在 CPU core 上限内找吞吐不再提升的点

**ILP Solver**（式 2–5）：
- 约束：$\sum N_{M_i} Sz_i \leq M$，$\sum N_{D_i} Sz_i \leq D$，$N_{optM} + N_{optD} \leq N$（总缓存 tensor 数不超过数据集大小，且 memory/storage 互斥）
- 目标：最大化 $\sum N_{M_i} C_{M_i} + \sum N_{D_i} C_{D_i}$
- 输出：每层的 optimal step 集合 $S_{optM}$、$S_{optD}$ 及各自缓存 tensor 数

**Pipeline 生成与 cache population**：
- 为每个被缓存的 step 生成独立 ingestion 分支，必要时再加 raw 分支
- 用 if-then-else 条件执行：全缓存则跳过前缀 step，partial 缓存则从中间 step 续算
- Epoch 0 填充 memory/SSD cache 并维护 sample→cache location 映射
- 向用户暴露单一 iterator，训练 loop 无需改动

**Working memory 预留**：从用户给定的总 memory budget $M$ 中扣除 working memory，剩余才是 in-memory cache 容量；用户给的是总预算而非 cache 大小。

与 [[PRESTO]]（SIGMOD'22，整 step SSD 缓存）、MinIO（OS page cache 缓存 raw data）、Cachew（managed service，all-or-nothing）对比，HyCache 的关键差异是 **partial + exclusive + coordinated multi-tier**。深度实现细节见 [[atc2025-jha]]。

## 设计取舍

- **取舍 1：ILP 最优 vs 运行时开销**——用离线 profile + ILP 换取自动策略，但第一个 epoch 有 2.5%–18.2% profiling 开销，且 ILP 求解与多 pipeline 生成增加实现复杂度；收益是用户零手工选 step/cache size。
- **取舍 2：Exclusive 缓存 vs 简单性**——memory 与 storage 内容互斥避免 OS page cache 重复，但无法在两层对同一 tensor 做 hot/cold 分层；简化了容量 accounting，放弃了「热数据 DRAM + 冷数据 SSD 备份」的冗余策略。
- **取舍 3：只缓存 offline step vs 覆盖全部 pipeline**——保留 augmentation 随机性，放弃对 online step（Data Echoing、Revamper 等方向）的加速；在 augmentation-heavy pipeline 上收益上限被锁定。
- **取舍 4：DALI 绑定 vs 通用性**——hcLib 要求继承 BasePipeline（DALI wrapper），集成简单但框架锁定；论文声称 model framework agnostic，但 preprocessing 必须走 DALI。
- **边界条件**：在预处理瓶颈显著、数据集 ≥550 GB、本地 SSD 充足的 server 上表现最好；远程存储或极小数据集时优势不稳定；大 batch size 压缩 working memory 后 cache 空间变小，加速比下降（Figure 9）。

## 实验与结果

- **Pipeline 吞吐**（6 条 pipeline，C2 配置，相对 OS page cache）：vs MinIO **1.11×–5.3×**（Voice 5.3×，IR-1 1.84×，IR-2 1.74×）；vs PRESTO **1.24×–2.26×**；Voice pipeline 节省 >80% 重计算时间
- **硬件可扩展性**（C1–C5）：Voice **3.14×–7.10×** vs MinIO、**1.2×–3.5×** vs PRESTO；IR-2 **1.73×–2.13×** / **1.61×–2.57×**
- **端到端训练**（C4，含 GPU 训练）：**1.05×–1.67×** vs MinIO、**1.05×–1.47×** vs PRESTO；ViT-LoRA 仅 1.05×（GPU compute bound）
- **远程 NFS 存储**：**1.11×–10.1×** vs MinIO、**1.19×–9.28×** vs PRESTO；IR-2/Voice 受益大，IR-1/Segmentation 受 64.8 MiB/s 带宽限制
- **Profiling 开销**：一次性，占单 epoch 预处理时间 2.5%–18.2%（Table 7）
- **策略多样性**（Table 6）：如 Detection 在 memory 缓存 6 个 step、SSD 缓存 5 个 step；CubePP 在 memory 缓存 2 个不同 step

## Critical Analysis

### 论证链条

Observation（预处理 stall headroom 1.13×–2.3×）→ Motivation（prior 四层局限）→ Design（partial/exclusive/coordinated ILP）→ Result（pipeline 1.11×–10.1×）逻辑基本闭合。关键跳步在于：**pipeline-only 加速能否线性转化为端到端收益**——实验显示当 GPU 训练占比高时增益被稀释（ViT-LoRA 1.05×），作者诚实报告但未系统量化「预处理占比 vs 端到端加速」的回归关系。ILP 基于 first-epoch profile 的静态 plan，未讨论 dataset drift 或 step 耗时随硬件热状态变化时的 re-profiling 需求。

### 假设压力测试

- **已证明**：在 6 条 NVIDIA DALI pipeline、550–650 GB 级数据集、单机 512 GB DRAM + 本地 NVMe 上，partial multi-tier 缓存优于 MinIO/PRESTO。
- **可能失效**（推断）：
  - **多 tenant / 共享 cache**：论文未实现跨 job 的 cache 共享或淘汰（Quiver 方向），HyCache 独占 memory/SSD budget
  - **Pipeline 变更**：用户修改 preprocessing graph 后需重新 profile + 重建 cache，论文未讨论增量更新成本
  - **分布式训练**：Section 7.9 仅设计讨论（同构集群复用 plan、异构集群 per-node profile），**无实验**
  - **Epoch 间 shuffle 模式**：假设 random shuffle 下 partial cache hit 仍有效；若 production 使用 strict sequential 或 curriculum sampling，ILP 基于 uniform 1% sample 的假设可能偏差
  - **Storage 磨损**：大量中间 tensor 写 SSD 的长期耐久性与成本论文未讨论

### 实验可信度

- **Benchmark 代表性**：覆盖 image/voice/detection/segmentation，数据集规模大，比 PRESTO 原论文 250 MB–146 GB 更接近现代训练；但全部基于 DALI + PyTorch，未覆盖 TensorFlow/JAX 生态。
- **Baseline 强度**：MinIO 本质是 OS page cache + raw caching，作为弱 baseline 合理；PRESTO 重新实现于 DALI 且仅整 step SSD cache，对比公平但未能代表 Cachew/Plumber 等更强自动化方案。
- **Ablation**：Figure 2 的渐进策略（partial mem → +exclusive storage → +coordinated）有力支撑设计分解；缺少对 ILP vs greedy、exclusive vs 允许重叠、working memory 公式各分项的独立 ablation。
- **Metrics**：聚焦吞吐与端到端训练时间，**未报告** tail latency、OOM 发生率、cache 填充时间、多 epoch 稳定性、训练 accuracy/loss 曲线（虽声称不影响正确性）。

### 系统性缺陷

- **实现复杂度**：自动生成多分支 conditional pipeline + 多 fetcher 配置，调试与可观测性成本高；论文未讨论 logging/metrics 接口。
- **尾延迟**：未分析 partial cache miss 时「部分从 SSD、部分重算」的 batch 组装延迟方差。
- **故障恢复**：SSD cache 损坏、profile 中断、epoch 0 cache population 失败时的恢复策略论文未讨论。
- **资源隔离**：多 job 共享机器时 HyCache 独占 DRAM/SSD budget，无 cgroup 感知。
- **部署成本**：首次 epoch 需在 SSD 写入大量中间 tensor，存储空间与写入带宽是一次性资本支出；远程 NFS 场景下部分 pipeline 反而更慢。

## 局限与 Future Work

- **局限 1**：实现与评估限定于**单机**；分布式仅设计描述，无 multi-node 实验。
- **局限 2**：**不处理 online/stochastic augmentation** 缓存，对 augmentation-heavy pipeline 收益有硬上限。
- **局限 3**：缓存 plan 在首个 epoch profile 后**静态固定**，未探索 epoch 间 re-optimization 或在线 adaptation。
- **局限 4**：绑定 **NVIDIA DALI**，未验证 TensorFlow tf.data 或 JAX 生态的可移植性。
- **Future work 1**：在**真实 production trace**（多 tenant、异构硬件、远程 object storage）上测量 partial hit rate 与 ILP plan 稳定性，量化何时需要 re-profile。
- **Future work 2**：将 HyCache 的 ILP 策略与 **跨 job 共享 cache**（如 Quiver 的 hash-based addressing）结合，测量集群级 DRAM/SSD 利用率与隔离性 trade-off。
- **Future work 3**：对 **online augmentation** 探索近似缓存（如 Revamper/Data Echoing 的 partial reuse）与 HyCache offline 缓存的混合策略，用 accuracy + throughput 联合指标评估。
- **Future work 4**：加入 **tail latency / SLO** 约束的 ILP 公式（而非仅最大化平均 recompute savings），验证对端到端 training stall 的影响。

## 相关

- **相关概念**：[[Data-Pipeline]]、[[DNN-Training]]、Caching、ILP
- **同类系统**：[[PRESTO]]、MinIO、Cachew、Plumber、tf.data、Quiver
- **同会议**：[[ATC-2025]]
- **对比**：HyCache 在 partial multi-tier coordinated caching 上相对 PRESTO 的 all-or-nothing single-tier 策略