# An Efficient Cloud Storage Model with Compacted Metadata Management for Performance Monitoring Timeseries Systems

**作者**：Kai Zhang (The Chinese University of Hong Kong), Tianyu Wang (Shenzhen University), Zili Shao (The Chinese University of Hong Kong)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/zhang-kai
**源文件**：[[fast2026-zhang-kai.pdf]]

---

## 一、背景

云端性能监控时序系统（如 Prometheus via Cortex、InfluxDB、TimescaleDB）因云的弹性和按需付费能力而快速发展。这些系统需要收集大量性能指标（CPU、内存、网络等），并支持基于 tag 的灵活查询。随着容器和微服务的兴起，时序数据库面临管理海量动态时序数据的需求——例如 ByteDance 的监控系统每天需处理超过 100 亿条不同的时序数据。

然而，将时序系统迁移到云端后，云存储的对象模型（object-based）与本地文件系统存在根本差异，导致查询性能显著下降。现有系统的存储模型是为本地存储设计的，直接迁移到云端会带来严重的 read amplification 和 metadata 冗余问题。

---

## 二、要解决的问题

1. **Read amplification 严重**：现有系统（如 Cortex）将元数据和数据混合存储在一个 data block 中，直接转为云对象后，即使只需要少量数据也必须加载整个对象。Apache Parquet 的列式存储在访问特定时序的特定时间范围时仍需读取不必要的行。JSON Time Series (JTS) 为每个时序维护独立对象，但 tag-based 查询需扫描所有对象。

2. **Metadata 高度冗余**：在大规模监控场景中，超过 70% 的 tag 在多个时序间重复，部分 tag（如 region、cluster）被 90% 以上的数据共享。这些 tag 在每个 time partition 中重复存储，导致元数据膨胀并拖慢查询。

3. **云存储带宽利用不足**：传统方法每个查询请求单线程顺序访问数据 chunk，无法充分利用云对象存储的高带宽。

---

## 三、洞察与设计

**关键洞察**：时序系统中的元数据（tag）和数据在访问模式上有根本差异——元数据被频繁访问且高度冗余，而数据访问是稀疏的。将两者分离管理，并对元数据进行全局去重和压缩索引，可以同时减少 read amplification 和存储开销。

基于此洞察，CloudTS 采用「元数据-数据分离」的双结构设计：

### 元数据管理

- **TagDict**：基于 Patricia Trie 的全局 tag 字典，利用共享前缀去重（如 `cpu=core1` 和 `cpu=coren` 共享 `cpu` 前缀）。每个唯一 tag pair 分配全局编码，支持双向查找（tag pair ↔ encoding）。每个 time partition 维护局部 Tag Array，仅包含该分区涉及的 tag，按频率排序。

- **TTMapping**：二维 bitmap 表示时序与 tag 的映射关系（行=时序，列=tag，1 表示关联）。由于 bitmap 极度稀疏（实测仅 0.7% 的 bit 为 1），设计了 TMMC（Timeseries Metadata Mapping Compression）压缩方案——基于 CSR 格式的变体，只保存 `ind`（值为 1 的位置）和 `ptr`（每行累计 1 的数量）两个数组，将空间复杂度从 O(M×N) 降至 O(M+N)。

### 时序分组

分析 tag pair 的频率分布，将时序按 tag 相似性分组：低频 tag 提供高选择性用于过滤，高频 tag（跨大多数时序共享）用于并行分组访问。

### 数据组织

- **TSObject**：每个 time partition 中一组时序的压缩数据 chunk 按时序 ID 和时间顺序排列存储在一个对象中。平衡了文件大小与访问效率。

### 查询流程

1. TagDict 查找：检查本地缓存的 Tag Array 和 TTMapping，必要时从云端获取
2. Tag-based 时序识别：通过 TTMapping 定位目标时序 ID
3. 并行 TSObject 检索：针对目标时序组和时间范围并行发起 get 请求

---

## 四、实现细节

- 使用 Go 语言实现完整原型，集成到 Cortex 1.16.0
- CloudWriter 作为 daemon 进程，仅在 data block 不可变时激活，不影响正常监控服务
- TMMC 压缩算法：遍历 bitmap 记录所有值为 1 的列索引到 `ind` 数组，记录每行累计 1 数量到 `ptr` 数组。查询时通过 `ptr` 定位行范围，再从 `ind` 读取列信息
- 时序分组策略：基于 tag name 的互斥性和频率分布，将原始大 TTMapping 分割为更小的子矩阵
- TSObject 的 key 基于时序组生成，作为云存储中的唯一标识
- TTMapping 作为本地 metadata cache 缓存，避免重复网络请求
- 部署在 Amazon EC2 + S3 环境

---

## 五、实验结果

**实验平台**：Amazon EC2 (Intel Xeon Platinum 8259CL, 64GB RAM, 100Gbps 网络) + Amazon S3，10 台 Debian 监控目标

**基线**：Cortex (原始)、Apache Parquet 集成 Cortex、JSON Time Series 集成 Cortex、InfluxDB 3.x

### 生产环境评估（100 个监控目标，48h 数据采集后查询）

| 指标 | CloudTS vs Baseline |
|------|-------------------|
| 端到端查询延迟 | 平均 1.43× 加速 |
| 查询吞吐 | ~130 MB/s |
| 上传过程对查询影响 | 无显著影响 |

### 合成负载评估（500K 时序，8 种 TSBS 查询模式）

| 查询模式 | Baseline | Parquet | JTS | CloudTS |
|---------|----------|---------|-----|---------|
| 1-8-1 | 0.145s | 0.139s | 0.178s | 0.126s |
| 5-8-1 | 0.149s | 0.141s | 0.163s | 0.128s |
| 5-1-1 | 0.143s | 0.138s | 0.165s | 0.124s |
| 5-1-12 | 0.155s | 0.151s | 0.178s | 0.130s |
| high-1 | 0.195s | 0.184s | 0.244s | 0.150s |
| high-all | 0.235s | 0.241s | 0.322s | 0.188s |
| cpu-all-1 | 0.216s | 0.230s | 0.292s | 0.187s |
| cpu-all-8 | 0.255s | 0.263s | 0.304s | 0.233s |

- 平均查询延迟改善 36%（vs Baseline）
- 数据访问量减少 36–61%
- 网络利用率：CloudTS 8 线程平均 230.7 MB/s vs Baseline 102.5 MB/s
- vs InfluxDB 3.x：复杂查询（high-all）降低 15.5% 延迟

### 资源开销

| 系统 | CPU 利用率 | 内存 (high-all) | 内存 (cpu-all-8) |
|------|----------|----------------|-----------------|
| Cortex | 60.4% | 5.21 GB | 4.92 GB |
| Parquet | 53.8% | 4.73 GB | 4.49 GB |
| JTS | 78.3% | 5.92 GB | 5.82 GB |
| CloudTS | 45.7% | 3.35 GB | 3.26 GB |

### 高 Label Churn 场景

200 个分区、2.74 亿短生命周期时序下，CloudTS 的 per-partition 内存消耗控制在 30MB 以下，TagDict 内存保持稳定。

---

## 六、批判性分析

1. **实验规模偏小**：核心实验仅用 10 台监控目标（合成负载 500K 时序），而论文动机部分提到 ByteDance 需处理 100 亿时序。500K 到 10B 之间有 4 个数量级的差距，O(M+N) 的理论分析在真正大规模场景下的实际表现未被验证。

2. **基线选择不够强**：Parquet 和 JTS 的集成方式是作者自行修改 Cortex 存储引擎实现的，并非这些格式的最优使用方式。例如 Parquet 在实际使用中通常配合 predicate pushdown 和 row group pruning 等优化，论文未说明是否实现了这些。InfluxDB 3.x 的比较仅在 Section 4.3.5 简要出现，缺乏详细配置说明。

3. **写入代价被淡化**：CloudWriter 需要在 data block 不可变后进行格式转换和上传，但论文几乎没有报告转换延迟和 CPU/内存开销。仅在 Figure 6(b) 中显示了上传吞吐量，未量化转换过程的计算成本。

4. **Cache 效果未隔离**：CloudTS 维护本地 TTMapping cache，但实验中未区分 cache hit 和 cache miss 场景的性能差异。在冷启动或 cache 失效时，查询性能可能显著不同。

5. **TMMC 压缩的局限性**：当 bitmap 不再稀疏（如每个时序关联大量 tag）时，TMMC 的压缩效果会退化。论文仅在 0.7% 稀疏度下验证，未讨论边界情况。

6. **并发查询和多租户场景缺失**：实验均为单用户顺序查询，未评估多用户并发查询、不同查询模式交叉时的性能表现。

---

## 七、总结

CloudTS 针对云端性能监控时序系统的查询瓶颈，提出了元数据-数据分离的存储模型。核心贡献包括：基于 Patricia Trie 的全局 TagDict 去重冗余 tag、TMMC 压缩的二维 bitmap TTMapping 索引、按时序分组的 TSObject 数据组织。在 Amazon S3 上的实验表明，CloudTS 相比 Cortex 平均降低 36% 查询延迟，减少 36–61% 数据访问量。主要局限在于实验规模与动机中描述的真实场景差距较大，写入端开销和 cache 效果未充分评估。该方案适用于中等规模、tag 冗余度高的云端监控场景。
