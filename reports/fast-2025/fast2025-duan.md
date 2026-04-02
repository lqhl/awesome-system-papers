# AegonKV: A High Bandwidth, Low Tail Latency, and Low Storage Cost KV-Separated LSM Store with SmartSSD-based GC Offloading

**作者**：Zhuohui Duan, Hao Feng, Haikun Liu, Xiaofei Liao, Hai Jin, Bangyu Li（华中科技大学）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/duan
**源文件**：[[fast2025-duan.pdf]]

---

## 一、背景

基于 Log-Structured Merge Tree (LSM-tree) 的 Key-Value 存储在数据密集型应用中扮演核心角色，但 compaction 带来的读写放大问题一直是行业痛点。KV 分离（KV separation）架构通过将 value 从 LSM 结构中解耦，单独存储在 Value region（vLog/Blob），仅在 LSM 中保留 key 和 value 的偏移地址，显著降低了 compaction 开销。然而，KV 分离引入了对 Value region 的垃圾回收（Garbage Collection, GC）需求——需要定期整合包含大量过期数据的文件，回收存储空间并维护 scan 性能。

目前 KV 分离系统的 GC 策略主要分为两类：Direct GC（如 Titan）直接扫描 Blob 文件并查询 LSM 验证有效性后重写；Compaction-triggered GC（如 DiffKV、BlobDB）将 GC 与 compaction 合并执行。两种策略各有优劣，但都无法同时在吞吐量、尾延迟和存储空间三个维度达到最优。

---

## 二、要解决的问题

1. **Direct GC 的带宽和 CPU 竞争**：以 Titan 为代表，GC 过程中大量的 LSM 索引读写（占 GC 时间的 91.2%）与前台读写请求争夺带宽和 CPU 资源，导致吞吐量下降 40% 以上（关闭 GC 后吞吐提升 67.7%，尾延迟降低 69.1%）。

2. **Compaction-triggered GC 的空间膨胀和 write stall**：DiffKV 和 BlobDB 虽然避免了 Direct GC 的带宽竞争问题，但将 GC 负担转移到 compaction，导致 compaction I/O 增大 5.4-14.4 倍，冗余空间分别膨胀 53GB 和 135GB（对比 RocksDB 的 9GB），并引发 write stall。

3. **三指标不可兼得**：现有系统在吞吐量、尾延迟、存储空间三个维度上存在 trade-off，无法同时优化。

---

## 三、洞察与设计

**关键洞察**：Direct GC 的性能瓶颈本质上是 GC 操作与前台 LSM 读写竞争 host 端的带宽和 CPU 资源；而 SmartSSD 集成了 FPGA 和内部 P2P 数据通路，可以在存储设备内部独立完成 GC 的 I/O 和计算，从而将 GC 完全从 host 的关键路径中移除，无需在三个指标之间做 trade-off。

基于此洞察，AegonKV 在 Titan 基础上设计了三个核心组件：

1. **GC Manager + ValidMap**：利用 compaction 过程中天然产生的失效信息，为每个 Blob 文件维护一个 Bitmap（ValidMap），以极低开销（32MB Blob 仅需 4KB ValidMap）实时追踪每个 KV 位置的有效性。这样 FPGA 端的 GC 无需回查 LSM 验证数据有效性，解决了 "Read Back Travel" 挑战。

2. **GC Scheduler**：包含 I/O Control、CU Control 和 Meta Install 三个模块。I/O Control 充分利用 SmartSSD 内部 P2P 带宽；CU Control 在软件层管理 FPGA 上有限的 Compute Unit 资源分配；Meta Install 通过 buffer queue 批量刷入 GC 元数据，避免写回竞争。

3. **GC Friendly Metadata Install**：将 GC 结果的元数据直接批量插入 MemTable 而不做有效性验证，通过延迟验证（deferred validation）机制在后续 Get 和 compaction 操作中保证数据一致性，避免写回过程的带宽争用。

---

## 四、实现细节

- **ValidMap 数据结构**：每个 Blob 文件对应一个 Bitmap，bit "0" 表示有效，"1" 表示失效。更新通过 compaction 回调，构建临时 ValidMap 后与当前 ValidMap 做 bitwise OR。SSTable 中增加了每个 KV 在 Blob 文件中的序号索引。

- **FPGA Compute Unit (CU)**：抽象为 Input Decode → Data Compute → Output Encode 三阶段流水线，使用 Vitis-HLS 开发。Data Compute 阶段分为 Filter（根据 ValidMap 流式过滤无效数据）和 Fetcher（仅移动有效 KV 的起止位置间数据，无需解析内部结构）。输入采用无限流式接口，不硬编码文件数量或大小限制。SmartSSD 上部署 8 个 CU，CLB 利用率 97.6%。

- **P2P 数据对齐**：SmartSSD 的 P2P 传输基本单位为 4KB，Blob 文件增加 padding 对齐。

- **GC Write-back State**：在 KV 分离标志位中增加 GC write-back 状态。Get 操作遇到 GC 元数据时，继续向后查找旧版本比对地址一致性；compaction 遇到元数据时将其提升为普通数据，控制元数据冗余。

- **系统基于 Titan（TiKV 的 KV 分离引擎）最新版本实现**，开源于 https://github.com/CGCL-codes/AegonKV。

---

## 五、实验结果

**实验平台**：2×18-core Intel Xeon Gold 5220 @ 2.20GHz，64GB DDR4-2666，Samsung SmartSSD（Xilinx UltraScale+ FPGA + 3.84TB SSD），Ubuntu 20.04。

**基线系统**：RocksDB、BlobDB、Titan、Titan w/o GC（理想上界）、DiffKV。

### YCSB 基准测试（20M KV pairs，key=24B，value=1KB，200M ops）

| 指标 | AegonKV vs Titan | AegonKV vs DiffKV | AegonKV vs BlobDB |
|------|-----------------|-------------------|-------------------|
| 吞吐量（写密集 A/F） | 1.28-3.3× 提升 | 1.11-1.5× 提升 | 1.1-4.66× 提升 |
| 99% 尾延迟（写密集 A/F） | 降低 85.9% | 降低 14.7% | 降低 36.8% |
| 存储空间开销 | 降低 15%-85% | 显著降低 | 显著降低 |
| Write stall | 0 秒 | — | — |
| Compaction I/O | 比 DiffKV/BlobDB 低 5.4-14.4× | — | — |

### 生产负载

| 负载 | 吞吐提升 | 尾延迟降低 |
|------|---------|-----------|
| Social Graph | 1.07-2.16× | 10%-52% |
| Twitter Cluster 39（写密集） | 7.6%-97.7% | — |

### 资源效率

| 指标 | AegonKV | 说明 |
|------|---------|------|
| CPU 利用率 | 77.17% | 比其他系统节省约 20% |
| 能效 | 901.78 ops/J | 最高，比 Titan 提升 265% |
| FPGA 资源 | 8 CU，CLB 97.6% | 充分利用 SmartSSD 硬件 |

---

## 六、批判性分析

1. **硬件依赖性极强**：整个方案依赖 Samsung SmartSSD 这一特定商用计算存储设备，市场渗透率有限。论文未讨论方案在其他计算存储设备（如 ScaleFlux、NGD Systems）或 CXL-attached FPGA 上的可移植性。如果 Samsung 停产或改变 SmartSSD 架构，方案的实际价值将大打折扣。

2. **对比基线的公平性存疑**：Titan 默认配置下性能本就较差（甚至比 RocksDB 低 18.3%），用它作为主要基线放大了 AegonKV 的改进幅度。论文虽然对比了 DiffKV 和 BlobDB，但它们也有各自的已知缺陷。缺少与 PinK（KV-SSD 方案）的直接性能对比尤为遗憾，仅在 Related Work 中一笔带过。

3. **Value 大小敏感性**：实验主要使用 1KB value size，但 Twitter 真实负载中 value 仅 80-221B。论文自己也承认小 value 场景下各系统差异不大，这意味着在很多真实场景中 AegonKV 的优势可能不明显。

4. **延迟验证的隐含成本被低估**：GC Friendly Metadata Install 将验证推迟到 Get 和 compaction，论文声称开销很小，但未量化在高 GC 频率 + 高读取频率场景下的额外读放大。如果 GC metadata 累积较多，Get 操作需要多次回溯查找，这对尾延迟的影响值得深入分析。

5. **FPGA 资源已近饱和**：8 CU 部署后 CLB 利用率 97.6%，几乎没有扩展空间。如果未来需要增加功能（如支持更复杂的 GC 策略或 compaction offloading），硬件资源将成为瓶颈。论文未讨论这一限制。

6. **仅考虑单 SSD 场景**：现代存储系统通常使用多 SSD 或分布式架构，论文未讨论 AegonKV 在多设备环境下的扩展性。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint 存储的启发**：大模型训练的 checkpoint 写入本质上也是 "大 value 的顺序写 + 定期清理旧版本" 的模式。AegonKV 的 SmartSSD-based GC offloading 思路可以借鉴到 checkpoint 存储系统中——用计算存储设备在后台自动清理过期 checkpoint，不占用 host CPU 和 PCIe 带宽，对训练吞吐的影响更小。

2. **KV Cache 存储的潜在应用**：LLM 推理中的 KV Cache offloading 到 SSD 是热门方向。KV Cache 的特点是 token 粒度的频繁更新和淘汰，与 KV 分离存储的 GC 模式有相似之处。ValidMap 这种轻量级有效性追踪机制可以迁移到 KV Cache 管理中，用于高效识别和回收已淘汰的 cache 条目。

3. **Near-data Processing 在 AI 数据管道中的机会**：训练数据预处理（shuffle、filter、transform）是 I/O 密集型任务。AegonKV 展示了 SmartSSD 上 FPGA 流水线化数据处理的可行性，这一模式可扩展到训练数据管道中，在存储设备端完成数据过滤和预处理，减少 host 端数据搬运。

4. **可跟进方向**：将 GC offloading 的思路扩展到分布式 KV 存储（如 TiKV）中，在多副本场景下利用计算存储设备在本地完成 GC，减少跨节点数据搬运，这对 AI 训练集群中的参数服务器或嵌入表存储可能有实际价值。

---

## 八、总结

AegonKV 首次将 SmartSSD 的近数据处理能力应用于 KV 分离系统的 GC 优化，通过 ValidMap 消除 GC 对 LSM 的回查依赖，通过 FPGA 流水线实现 GC 的计算和 I/O offloading，通过延迟验证的元数据安装避免写回竞争，在吞吐量（1.28-3.3× 提升）、尾延迟（37%-66% 降低）和存储空间（15%-85% 降低）三个维度同时超越现有 KV 分离系统。主要局限在于对 Samsung SmartSSD 硬件的强依赖、小 value 场景下优势减弱，以及 FPGA 资源已近饱和。适用于大 value、写密集、对尾延迟敏感的 KV 存储场景。
