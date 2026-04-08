# DOGI: Data Placement with Oracle-Guided Insights for Log-Structured Systems

**作者**：Jeeyun Kim (POSTECH), Seonggyun Oh (DGIST), Jungwoo Kim (DGIST), Jisung Park (POSTECH), Jaeho Kim (Gyeongsang National University), Sungjin Lee (POSTECH), Sam H. Noh (Virginia Tech)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/kim-jeeyun
**源文件**：[[fast2026-kim-jeeyun.pdf]]

---

## 一、背景

Log-structured 存储系统（LSS）广泛部署于存储固件、键值存储、分布式文件系统等场景，通过将随机写转化为顺序追加写来获取高写吞吐。然而，追加写设计不可避免地产生无效数据，需要 Garbage Collection（GC）回收空间。GC 选择 victim segment 后需要迁移其中仍然有效的数据块，由此产生的额外写入开销用 Write Amplification Factor（WAF）衡量——即存储系统实际写入字节数与用户请求写入字节数之比。

降低 WAF 是 LSS 设计的核心挑战。已有大量研究提出了各种 data placement 技术，试图将预期失效时间相近的数据块放在同一 segment 中，从而让 GC 时 victim segment 中的有效块更少。然而，现有技术与理论最优之间仍存在显著差距。

---

## 二、要解决的问题

现有 SOTA data placement 技术（SepBIT、MiDAS、PHFTL、ML-DT）存在三个关键不足：

1. **User-written block 的失效时间预测不精确**：基于启发式的方法（SepBIT、MiDAS）准确率较低（76%–87%）；基于 ML 的方法（PHFTL、ML-DT）准确率更高但推理延迟过大（PHFTL 6.5μs、ML-DT 173μs），严重拖累写吞吐（ML-DT 仅 22.6 MB/s）。

2. **GC-written block 的重定位策略粗糙**：GC 过程中被迁移的有效块实际上具有非常多样的剩余失效时间分布，但现有方法要么简单按 age 级联到下一个更冷的 group（SepBIT/MiDAS/PHFTL），要么将所有 GC 块统一隔离到单一 group（ML-DT），无法捕捉这种多样性。

3. **Group 配置固定不变**：现有技术固定 group 数量，忽略了 group 粒度与预测精度之间的 trade-off。更多 group 可以更细粒度地分离数据，但也放大了预测错误的惩罚；最优 group 数量取决于预测模型的准确率，需要动态调整。

---

## 三、洞察与设计

**关键洞察**：数据块失效时间的预测准确率与 group 配置之间存在强耦合——group 数量越多，对预测准确率的要求越高，误预测的代价越大。最优 group 配置不是固定的，而必须随预测模型的实际准确率动态变化。此外，热数据块（频繁更新）和冷数据块（极少更新）的失效行为具有明显规律性，可以用简单启发式高效识别，只需将 ML 模型的算力集中在中间温度的数据块上。

基于此洞察，DOGI 的设计围绕三个核心组件展开：

### 1. NoDaP：近最优 Oracle 基线

作者首先设计了 NoDaP（Near-optimal Data Placement），一个利用未来知识（block 的精确失效时间）的离线 oracle 基线。NoDaP 将存储划分为 N 个 group，每个 group 分配一个 Block Invalidation time Range（BIR），通过穷举搜索找到最小化 WAF 的 group 配置。NoDaP 不可用于实际部署，但提供了可达的 WAF 上界，并通过对比分析揭示了现有技术的三个瓶颈。

### 2. 混合预测机制（User-written Block Placement）

- **Hot Filter (HF)**：用最近失效时间判断热块，将其分配到专用 G_hot group。HF 采用迭代算法动态调整热块阈值 μ，无需 ML 推理，延迟仅 0.13μs。
- **ML-Assisted Allocator (ML-Alloc)**：对非热块使用轻量级 MLP（仅 1.6K 参数、两层全连接）进行十分类预测。通过精选 6 个输入特征（LBA、前一个 LBA、频率、chunk 频率、recency-weighted 频率、最近失效时间），结合 batch inference（128 块/批）和 double buffering 技术，将推理延迟降至 0.9μs/block，有效隐藏在 I/O 流水线中。

### 3. ML-Assisted GC-Written Block Relocation

- **Frozen Filter (FF)**：用 1-bit/block 标记从未被更新过的极冷块，直接迁移到专用 G_frzn group。
- **ML-Assisted Relocator (ML-Reloc)**：利用 Prediction Log（PLog）中记录的 <预测类别, 实际失效时间> 对，估算被误预测块的平均剩余失效时间，将 GC-written block 重定位到匹配 BIR 的 group。

### 4. 预测精度感知的动态 Group 配置

- 利用 PLog 构建每个 group 的实际失效时间分布，计算误预测比例。
- 用 Markov-chain 模型估算给定 group 配置下的 WAF。
- 穷举搜索所有 2^9 = 512 种 group 合并方案（从初始 10 个 group 中选择合并），选择 WAF 最低的配置。
- 当预测准确率显著下降（<10%）时，自动回退到基线双 group 设计。

---

## 四、实现细节

- **存储架构**：基于 ZNS SSD（Western Digital ZN540 2TB）上的 ZenFS 实现原型系统，segment 与 ZoneFile 一一对应。Segment 大小 256 MiB，逻辑块 4 KiB，over-provisioning 比例 10%。
- **ML 模型**：MLP 架构，1.6K 参数，2 层全连接。训练数据 300K 样本（每 10 个非热块采样 1 个），在线收集。训练每轮约 30 秒，每写入 100 GiB 重训一次，在专用 CPU 核上执行不干扰前台 I/O。
- **特征存储开销**：6 个特征的元数据结构共需 64 MiB（128 GiB 存储容量时），Frozen Filter 额外需 4 MiB。
- **PLog**：复用训练数据集中的 <预测类别, 实际失效时间> 记录，无额外采集成本。
- **Group 配置搜索**：穷举 512 种配置约需 10 秒完成。
- **Batch inference + Double buffering**：使用两个 4 MiB buffer 交替吸收写入和执行推理，完全隐藏推理延迟。
- **Segment footer**：每个 segment 末尾保留元数据空间，存储块的预测类别等管理信息。

---

## 五、实验结果

### 实验平台

- 模拟器（trace-driven LSS simulator）+ 真实原型（ZNS SSD + ZenFS）
- 64 核 2.4 GHz AMD EPYC Genoa，384 GB DDR4

### 工作负载

| 工作负载 | 类型 | 写入量 | 存储容量 |
|---------|------|--------|---------|
| FIO | S-type（偏斜静态） | 4 TiB | 132 GiB |
| YCSB-A | S-type | 4.1 TiB | 55–132 GiB |
| YCSB-F | S-type | 4.1 TiB | 55–132 GiB |
| Varmail | D-type（动态） | 3.5 TiB | 41 GiB |
| Alibaba | D-type | ≤13.7 TiB | — |
| Exchange | D-type | ≤1.9 TiB | — |

### 主要结果

| 指标 | DOGI vs. 最优 baseline (MiDAS) |
|------|-------------------------------|
| WAF 降低（平均） | 15.5%（所有工作负载），25.1%（vs. 所有 SOTA 平均） |
| WAF 降低（最大） | 23.2% |
| 写吞吐提升（平均） | 9.2%（vs. MiDAS） |
| 写吞吐提升（最大） | 13.3% |
| 推理延迟 | 0.39μs（vs. ML-DT 173μs，PHFTL 6.5μs） |
| 吞吐对比 | DOGI 19.4× vs. ML-DT，1.19× vs. PHFTL，1.09× vs. MiDAS |

### 预测准确率

| 方法 | User-written block 准确率 |
|------|-------------------------|
| Latest (启发式) | 最低 |
| ML-DT | 中等 |
| DOGI | 最高（+0.9%–8.1% vs. SOTA） |

- DOGI 的 Hot Filter 对热块分类准确率达 98.27%–99.0%。
- GC-written block 重定位准确率在大多数工作负载上优于 age-based 策略。
- 读延迟与 MiDAS 相当或略优（50th 和 99th percentile）。

---

## 六、批判性分析

1. **NoDaP 作为 "near-optimal" 基线缺乏严格证明**：论文承认 NoDaP 没有形式化最优性证明，仅通过穷举搜索找到 WAF 接近 1 的配置。相比 Lange et al. 的理论最优离线算法，NoDaP 的 WAF 更高。这使得 DOGI 相对于 NoDaP 的差距分析可能低估了实际的改进空间。

2. **内存开销的可扩展性问题被轻描淡写**：DOGI 在 128 GiB 设备上需要 68 MiB 元数据，但线性扩展到 64 TiB 时将达到 34 GiB。论文提出每 4 块共享元数据的方案会损失 0.6%–5.2% 准确率，但未深入评估这种精度损失对 WAF 的实际影响，仅留作 future work。

3. **工作负载覆盖面有限**：所有评估均基于写密集型工作负载，对读写混合或读密集型场景未做考察。实际存储系统中读写比例多样，DOGI 的 GC 优化收益在读主导场景下可能不显著。

4. **D-type 工作负载上的改进有限**：对于 Alibaba 和 Exchange 等动态访问模式，DOGI 的 WAF 降低仅 4.9%–10.4%，且频繁触发 fallback 机制回退到简单双 group 设计。这说明 DOGI 的 ML 模型在访问模式快速变化时适应能力有限。

5. **穷举搜索的局限性**：Group 配置搜索固定为 512 种方案（从 10 个 group 合并），且仅考虑相邻 group 合并。这一搜索空间的设计缺乏理论依据，可能错过非相邻合并或更复杂的配置方案。

6. **训练数据采样比例和重训频率的敏感性分析不足**：1/10 的采样率和 100 GiB 的重训周期是固定参数，论文未分析这些参数对不同工作负载的敏感性。

---

## 七、AI Infra / MLSys 视角

1. **轻量 ML + 启发式混合范式的借鉴价值**：DOGI 展示了一种有效的设计模式——用简单启发式处理 easy case（热/冷块），将 ML 模型的算力集中在 hard case（中间温度块）。这种思路直接适用于 AI 推理系统中的请求调度（如 KV cache eviction、prefill/decode 调度），先用规则过滤明确的 case，再用模型处理边界情况。

2. **预测精度与系统配置的耦合关系**：DOGI 揭示了预测模型精度与系统参数（group 数量）之间的强耦合。这一 insight 对 AI Infra 中的自适应系统设计有启发：例如，自动并行度调整、batch size 动态配置等场景中，系统参数的最优值同样取决于 workload predictor 的准确率。

3. **可迁移到 KV Cache / Paged Attention 管理**：LLM 推理中的 KV cache eviction 面临类似问题——预测哪些 KV cache block 将被重访。DOGI 的 PLog 机制（用历史预测记录估算误预测块的剩余生命周期）可以迁移到 KV cache 管理中，指导 eviction 和 prefetch 策略。

4. **值得跟进的方向**：
   - 将 DOGI 的 group 配置搜索方法应用于 GPU 显存分层管理（HBM + DRAM + SSD），动态决定各层容量分配
   - 探索 DOGI 的 Frozen Filter 思路在 checkpoint 存储中的应用——识别模型训练过程中不再更新的参数分片，优化 checkpoint I/O

---

## 八、总结

DOGI 通过设计近最优 oracle 基线 NoDaP 揭示了现有 data placement 技术的三个瓶颈，并提出了混合预测（Hot Filter + 轻量 MLP）、ML-assisted GC 块重定位、以及预测精度感知的动态 group 配置三个相互配合的组件。在多种写密集型工作负载上，DOGI 相比最优 baseline MiDAS 平均降低 WAF 15.5%，提升写吞吐 9.2%，同时推理延迟仅 0.39μs，具备实际部署可行性。主要局限在于内存开销随容量线性增长、对动态访问模式适应能力有限，以及与理论最优仍存在可观差距。
