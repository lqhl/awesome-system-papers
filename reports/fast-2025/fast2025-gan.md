# Revisiting Network Coding for Warm Blob Storage

**作者**：Chuang Gan, Yuchong Hu (通讯作者), Leyan Zhao, Xin Zhao, Pengyu Gong, Dan Feng — 华中科技大学计算机科学与技术学院；深圳华中科技大学研究院
**会议**：USENIX FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/gan
**源文件**：[fast2025-gan.pdf](../../papers/fast-2025/fast2025-gan.pdf)

---

## 一、背景

Erasure coding 在分布式存储系统中被广泛部署，用于以较低的存储开销实现容错。Blob 存储系统（如 Facebook f4、Azure）通常将 blob 分为 hot、warm、cold 等层级。Warm blob 占据存储的主要份额（如 Facebook 超过 80%），其访问频率低于 hot 但仍需要合理的读取性能。

Minimum-Storage Regenerating (MSR) codes 是修复带宽最优的纠删码，在保持与 RS codes 相同存储效率的前提下最小化单块修复所需的数据传输量。当前最先进的系统化 MSR 码是 Clay codes，它支持通用参数、存储最优、修复最优且 access-optimal。

---

## 二、要解决的问题

Clay codes 的 sub-packetization level 随 n−k 呈指数增长（α = (n−k)^⌈n/(n−k)⌉），这带来两个实际问题：

1. **小 blob 的 stripe layout 下修复慢**：高 sub-packetization 导致修复时每个节点需要读取大量非连续的 sub-block，产生大量非连续 I/O。对于小 blob（block size 小），非连续 I/O 的 seek 时间积累严重拖慢修复速度。例如 (14,10) Clay code 修复时每个节点最多产生 64 次非连续 I/O。

2. **Contiguous layout 下小 blob 的 degraded read 慢**：将多个小 blob 合并成大 block 时，Clay codes 以整个 block 粒度修复，读取一个小 blob 却需要解码整个大 block，造成严重的 read amplification。实验显示在 16MB merged block 中读取 1024KB blob 比读取 4096KB blob 慢 74%。

同时，传统非系统化 MSR codes 虽然 sub-packetization level 最低（α = n−k），但由于不保留原始数据块，读取任何数据都需要解码 k 个 parity block，造成读放大。

---

## 三、洞察与设计

**关键洞察**：实际 warm blob 存储的工作负载以小 blob 为主（如 Facebook f4 中高达 99% 的 blob 小于 1MB），而存储系统天然存在数据访问局部性（intra-blob locality 和 inter-blob locality）。如果将具有访问局部性的数据编码在同一个 stripe 中，那么即使非系统化 MSR codes 需要读取 k 个 parity block 来解码，由于局部性保证这些解码出的数据很快也会被访问，read amplification 在实际中被消除。

基于此洞察，NCBlob 的设计包含三个核心部分：

### 1. 基于局部性的编码方案（减少读放大）

- **Split-merge-encode**（利用 intra-blob locality）：将单个小 blob 切分为 k 个 sub-blob，多个 blob 的对应位置 sub-blob 合并成 data block，再用非系统化 MSR codes 编码。读取某个 blob 时只需从每个 parity block 中读取与该 blob 大小相等的片段即可解码，无读放大。

- **Merge-split-encode**（利用 inter-blob locality）：将具有 inter-blob locality 的多个小 blob 合并成固定大小的 group（默认 4MB），再切分为 k 个 data block 编码。读取 group 中任一 blob 时，解码出的其他 blob 也会很快被访问，后续读取直接从 DRAM 获取。

### 2. 混合 MSR 编码架构

- 小 blob 用非系统化 MSR codes 编码（低 sub-packetization，修复友好）
- 大 blob 用 Clay codes 编码（系统化，读取友好，大 blob 下修复性能恒定）
- 通过分析 Clay codes 修复时间模型，找到 disk seek time 开始主导总修复时间的 blob size 阈值来区分大小 blob

### 3. 通用化编码参数支持

- 提出 rotation-based sub-block selection 策略，使非系统化 MSR codes 在迭代修复后仍保持 MDS 性质
- 通过 two-phase checking 验证 MDS 和 repair MDS 性质
- 理论证明 n−k=3 时 NCBlob 总是可行的；模拟验证 n−k=3 或 4 时可支持数万次迭代修复（如 (14,10) 支持 10K 次，对应约 2857 年寿命）

---

## 四、实现细节

- **语言与规模**：C++ 实现，约 18.6K SLoC，运行在 Linux 上
- **架构**：三组件——Client、MetadataServer（含 Coordinator）、DataServer（含 Agent 和 Requestor）
- **通信**：使用 Redis 进行内部通信
- **编码库**：RS 和 Clay codes 基于 Ceph erasure coding 库实现，非系统化 MSR codes 基于 Jerasure
- **并行优化**：
  - SPR (Slice-grained Parallelized Read)：将 sub-block 切分为 n 个 slice，round-robin 分组解码，使所有节点带宽均匀利用
  - GPR (Group-based Parallel Repair)：基于 partial-parallel-repair 思想，将修复分解为可并行的子操作
- **分布策略**：类似 Ceph 的 Placement Group 机制均匀分布 block
- **源码开放**：https://github.com/YuchongHu/NCBlob

---

## 五、实验结果

**实验平台**：阿里云 22 节点集群（1 Coordinator + 20 Agents + 1 Client），ecs.d3s.2xlarge 实例（8 vCPU, 32GB RAM, 44TB HDD），15Gbps 网络。编码参数：(6,4), (9,6), (12,8), (14,10)。工作负载：Azure Blob Access Trace（约 60GB 采样），大小 blob 比例 5%:95%（数量），大小 blob 总大小比 4:1。

| 实验 | 关键结果 |
|------|---------|
| 读吞吐量 | NCBlob with locality 与 RS/Clay 相当，仅低 2.1%–10.5%；比 NCBlob without locality 高约 4.9× |
| Merge size 影响 | 1MB 合并大小时读吞吐量与 RS/Clay 相当；增大到 2MB 时下降约 11.9% |
| 单块修复时间 | 比 Clay codes 减少最多 45.0%（(14,10), 64MB block），比 RS 减少最多 44.1% |
| 全节点修复时间 | 比 Hybrid:RS+Clay 减少最多 33.3%，比 Clay 减少最多 38.4%，比 RS 减少最多 76.4%（(14,10), 256MB） |
| 单 blob degraded read | 比 Clay codes 延迟降低最多 9.1×（(14,10), 256MB） |
| 编码吞吐量 | NCBlob with merge 与 Clay 相当，(6,4) 仅低 0.5% |
| CPU 开销 | (6,4) 时 CPU 使用率 80.1%，比 Clay 高 4.8% |
| 内存开销 | NCBlob with locality 比 without locality 最多减少 56.3% |

---

## 六、批判性分析

1. **局部性假设的强依赖**：NCBlob 的读性能优势完全依赖于访问局部性的存在。论文承认缺乏局部性时可以退化到 Clay codes，但没有量化分析局部性质量下降时性能如何 graceful degradation。实际系统中局部性的程度和稳定性可能波动较大。

2. **n−k>3 时缺乏理论保证**：论文仅证明了 n−k=3 时 NCBlob 总是可行的，n−k=4 时仅通过模拟验证。虽然模拟显示可支持数万次迭代修复，但这并非理论保证，在极端情况下可能出现 MDS 性质失效。

3. **实验基线的局限**：实验未与 F-MSR codes 直接比较（因 F-MSR 仅支持 n−k=2），但 F-MSR 在其支持的参数范围内是 NCBlob 的直接前身，缺少这个比较使得 NCBlob 的增量贡献难以精确量化。

4. **merge 策略的静态性**：默认 4MB group size、基于 trace 分析的局部性分组策略较为静态。论文没有讨论工作负载漂移（workload drift）时如何动态调整分组策略，也没有评估 re-encoding 的成本。

5. **CPU 开销在高参数下显著**：(14,10) 时 NCBlob 需要并行解码，CPU 使用率明显高于 Clay codes 的直接读取，在 CPU 资源受限的环境下可能成为瓶颈，但论文未深入讨论这一 trade-off。

6. **仅评估 HDD 场景**：所有实验在 HDD 上进行，SSD 环境下 seek time 大幅降低，NCBlob 相对于 Clay codes 的优势可能显著缩小，但论文未提供 SSD 实验数据。

---

## 七、总结

NCBlob 针对 warm blob 存储中小 blob 占主导的特点，提出利用非系统化 MSR codes 的低 sub-packetization level 来改善小 blob 修复性能，同时通过访问局部性感知的编码方案消除非系统化编码的读放大问题。系统采用混合编码架构（小 blob 用非系统化 MSR、大 blob 用 Clay codes），并将非系统化 MSR codes 推广到 n−k≤4 的通用参数。在阿里云实验中，NCBlob 在仅损失 2.1%–10.5% 读吞吐量的前提下，将单块修复时间减少最多 45%、全节点修复时间减少最多 38.4%。主要局限在于对访问局部性的依赖、n−k>3 时缺乏理论保证、以及仅在 HDD 场景下验证。
