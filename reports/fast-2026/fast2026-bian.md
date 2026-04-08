# Discard-Based Garbage Collection for Distributed Log-Structured Storage Systems in ByteDance

**作者**：Runhua Bian (ByteDance & Tsinghua University), Liqiang Zhang, Jinxin Liu, Jiacheng Zhang, Jianong Zhong, Jiahao Gu (ByteDance), Hao Guo (Tsinghua University), Zhihong Guo, Yunhao Li, Fenghao Zhang, Jiangkun Zhao, Yangming Chen, Guojun Li (ByteDance), Ruwen Fan (Tsinghua University), Haijia Shen, Chengyu Dong, Yao Wang, Rui Shi (ByteDance), Jiwu Shu, Youyou Lu (Tsinghua University)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/bian
**源文件**：[[fast2026-bian.pdf]]

---

## 一、背景

ByteDance 构建了一个层次化存储栈：底层是 ByteStore（分布式 append-only 存储系统），上层部署了 ByteDrive（弹性块存储）、TOS（对象存储）、NAS 等多种存储服务，支撑抖音、飞书、豆包等核心业务。ByteStore 作为基础设施，采用 append-only 语义以简化 Erasure Coding、数据一致性和快照等功能的实现。

Append-only 存储系统需要周期性的 Garbage Collection（GC）来回收过时数据占用的空间。ByteDrive + ByteStore 早期采用 compaction-only GC：将旧 LogFile 中的有效数据读出并写入新 LogFile，再删除旧文件。这种方式面临 write amplification（写放大）与 space amplification（空间放大）之间的根本性权衡——更激进的 compaction 能释放更多空间，但代价是更多的写操作和更快的 SSD 磨损。这一权衡导致每月数百万美元的额外 TCO。

---

## 二、要解决的问题

1. **Write amplification 与 space amplification 的两难权衡**：Compaction-only GC 在降低空间放大时不可避免地增加写放大，反之亦然。两者都直接增加 TCO（SSD 采购成本 + 磨损更换成本）。
2. **大规模生产环境中的 GC 效率问题**：ByteDance 的 ByteDrive 管理 exabyte 级数据，GC 开销直接影响数月数百万美元量级的成本。
3. **多层存储栈中引入 discard 的工程挑战**：
   - 相邻存储层之间的 allocation unit 不对齐，导致 discard 请求在边界处无法完全回收垃圾（boundary loss）
   - 频繁 discard 触发大量 metadata 更新，与前台 I/O 争抢资源
   - Discard 在 LogFile 中打洞，增加碎片化和元数据管理开销
   - SSD 的 trim IOPS 有限，不同型号差异巨大，可能导致空间回收不及时

---

## 三、洞察与设计

**关键洞察**：ByteDance 生产环境中 SAR（搜索/广告/推荐）和离线计算工作负载表现出高度顺序写和频繁覆写的特征——超过一半的写操作修改大于 256 KiB 的连续范围，且覆写间隔仅数秒。这导致 LogFile 中出现大段连续的过时数据，可以通过直接"丢弃"（discard）而非搬移有效数据来回收，从而在不增加写放大的前提下降低空间放大。

基于此洞察，论文提出 DisCoGC（Discard-and-Compaction combined Garbage Collection）：

- **Discard 机制**：BlockServer 扫描 LSM-tree 识别无效数据范围，向 ByteStore 发起 discard 请求，逐层传递至 UFS 释放 cluster。无需读写有效数据，O(1) 时间回收空间。
- **Boundary extension**：针对 EC stripe 和 cluster 对齐导致的边界损失，将 discard 范围略微扩展至已丢弃的相邻区域，消除边界垃圾。同时将 EC stripe unit size 对齐到 cluster size，消除 cluster 级别的对齐损失。
- **Discard batching & scheduling**：同一 LogFile 的多个 discard 范围合并为一个批量请求（batch size 最大 64），减少 MetaPage 修改次数；通过并行度控制和流量控制限制 discard 对前台 I/O 的影响。
- **Compaction 与 discard 协同**：高频轻量 discard 作为主要回收手段，低频 compaction 负责合并碎片化的 LogFile 和 chunk，缓解元数据膨胀。双模调度——正常时按 garbage ratio 选择 compaction 目标，LogFile 数量过多时转为按 LogFile 数量选择。
- **Trim filter & merger**：针对 SSD trim IOPS 不足的问题，trim filter 只对大范围（≥128 KiB）执行 trim，trim merger 将 LBA 相邻的小范围合并为大范围，减少 trim 次数。

---

## 四、实现细节

- **存储栈**：ByteDrive Volume Layer 将随机写转为 append-only 写（128 KiB stripe round-robin 分布到 segment），Segment Layer 用 LZ4/deflate 压缩后写入 ByteStore LogFile。ByteStore 的 LogFile 由多个 chunk 组成（每个 chunk 数十至数百 MiB），chunk replica 分布在不同 ChunkServer 上（3-replica 或 EC）。
- **UFS（用户态文件系统）**：ChunkServer 上运行自研用户态文件系统，每个 4 KiB sector 自包含（32B header + 4064B data），4 个 sector 组成一个 cluster 作为分配单元。MetaPage zone 存储 cluster 分配和 chunk 映射信息。
- **Discard-friendly EC stripes**：将 EC stripe unit size 配置为 n × 4 × 4064B，与 cluster 大小对齐，消除 cluster loss。
- **Crash consistency**：BlockServer 为每个 segment 维护一个 discard LogFile，使用 WAL 机制持久化 "issued" 和 "successfully discarded" 范围。重启后比较两者找到中断的 discard 并重试。
- **内存管理**：使用两个 bitmap（issued + failed）跟踪 discard 范围，采用 roaring bitmap 压缩（减半），用 failed bitmap 代替 success bitmap 进一步节省 25%-45% 内存。
- **渐进式部署**：先在离线集群部署，per-volume 粒度启用。先用 mock discard（只记日志不释放数据）验证正确性，再切换为真实 discard。

---

## 五、实验结果

**生产集群**（混合工作负载，双路 24C48T CPU，256 GiB DRAM，200 Gbps 网络，16 块 SSD）：

| 指标 | Compaction-only | DisCoGC | 变化 |
|------|----------------|---------|------|
| Space amplification | 1.37 | 1.23 | -10% |
| Logical write amplification | 基准 | 降低 32% | -32% |
| Total write amplification | 基准 | 降低 25% | -25% |
| TCO | 基准 | 降低约 20% | -20% |
| 前台延迟 | 基准 | 无明显变化 | ≈0 |

**离线测试床**（10 台服务器，三种 trace + FIO）：

| 工作负载 | 特征 | TCO 改善 |
|----------|------|---------|
| SAR（搜索/广告/推荐） | 高顺序性，频繁覆写 | >25% |
| Offline（分布式计算） | 高顺序性，突发 I/O | 显著改善 |
| Online（实时服务） | 碎片化写，稀疏覆写 | 2%-5% |
| FIO（合成负载） | 32 MiB 随机写 | 显著改善 |

**Factor analysis**（以固定 space amplification 测量）：
- +Discard：LWA 降低 8.4%-13.9%
- +Batch：LWA 再降 2.7%-11.7%
- +BoundExt：LWA 再降 5.5%-16.1%

**资源开销**：CPU 使用降至 compaction-only 的 82.9%，内存增加至 102.9%。

---

## 六、批判性分析

1. **工作负载适用性的选择性呈现**：论文承认 online 工作负载（碎片化写）仅获得 2%-5% 的 TCO 改善，但对这类工作负载的深入分析不足。考虑到 ByteDance 大量业务属于 online 类型，DisCoGC 的实际整体收益可能低于论文重点呈现的 SAR/offline 场景。
2. **TCO 计算缺乏透明度**：论文多次提及"数百万美元 TCO 节约"和"20% TCO 减少"，但未给出 TCO 模型的具体构成（SSD 采购、磨损更换、电力、运维人力等各占多少比例），也未明确 write amplification 减少与 TCO 减少之间的映射关系，读者难以独立验证这些数字。
3. **Physical write amplification 增加被轻描淡写**：DisCoGC 导致 2%-10% 的 physical write amplification 增加（由于 LogFile 碎片化加剧 SSD GC），但论文将其与 logical write amplification 的下降相乘后声称总体改善，这种聚合方式掩盖了在某些 SSD 型号上 PWA 增加可能更严重的风险。
4. **SSD 型号依赖性问题**：论文在 SSD Model B（trim IOPS 仅 6K）上的实验显示，不启用 filter + merger 时系统甚至可能崩溃。这说明 DisCoGC 对 SSD 硬件特性有较强依赖，但论文仅测试了 2 款 SSD，生产中面临的 SSD 异构性挑战未充分讨论。
5. **与学术基线对比缺失**：论文仅与自家的 compaction-only GC 做对比，未与学术界提出的其他 GC 优化方案（如 Spooky、AegonKV 等 cited works 中的方法）做实验对比，降低了结论的说服力。

---

## 七、AI Infra / MLSys 视角

1. **AI 模型下载/推理场景的存储优化**：论文明确指出 SAR 工作负载中包含 AI 模型下载和推理，这恰恰是获益最大的场景（TCO >25% 改善）。随着大模型参数量增长，模型存储和分发的 I/O 模式（大块顺序写 + 频繁版本更新覆写）天然适合 DisCoGC，可为 AI Infra 的模型仓库和 checkpoint 存储提供参考。
2. **Checkpoint 存储优化的潜在应用**：分布式训练中的 checkpoint 写入模式（周期性大块顺序写覆盖旧 checkpoint）与 DisCoGC 的最佳适用场景高度吻合。将 discard 机制引入训练 checkpoint 存储可以显著降低存储成本。
3. **Append-only 存储 + GC 的设计范式**：ByteStore 的 append-only + GC 架构与许多 AI Infra 系统（如 KV cache 存储、embedding 存储）面临相似的空间管理问题。DisCoGC 中 discard/compaction 协同、boundary extension、trim filter/merger 等技术可以迁移到这些场景。
4. **值得跟进的方向**：
   - 针对 LLM 推理中的 KV cache offloading 到 SSD 的场景，研究类似 discard 机制减少 GC 开销
   - 在分布式 checkpoint 系统中，利用 checkpoint 版本语义自动识别可 discard 的范围，实现零 compaction 的 checkpoint 空间回收

---

## 八、总结

DisCoGC 是 ByteDance 在其分布式 append-only 存储系统 ByteStore 上的 GC 优化方案，核心思路是利用工作负载中大块连续垃圾的特征，通过 discard 直接回收空间而非搬移有效数据，打破了 compaction-only GC 中写放大与空间放大的两难权衡。系统解决了多层存储栈中边界对齐损失、元数据更新开销、碎片化管理和 SSD trim IOPS 限制等工程挑战，在生产集群实现约 20% 的 TCO 降低且不影响前台性能。该方案最适合高顺序性、频繁覆写的工作负载（如 AI 模型分发、索引构建），对碎片化工作负载的收益有限但仍有正向改善。
