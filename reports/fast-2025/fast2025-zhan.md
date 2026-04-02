# Rethinking the Request-to-IO Transformation Process of File Systems for Full Utilization of High-Bandwidth SSDs

**作者**：Yekang Zhan, Haichuan Hu, Xiangrui Yang, Qiang Cao (华中科技大学), Hong Jiang (UT Arlington), Shaohua Wang, Jie Yao (华中科技大学)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/zhan
**源文件**：[[fast2025-zhan.pdf]]

---

## 一、背景

现代 SSD 的带宽持续增长，PCIe 4.0 SSD 写带宽已达 4-6 GB/s，PCIe 5.0 SSD 更是翻倍。然而，现有 SSD 文件系统（EXT4、F2FS、XFS、BTRFS）在随机写场景下仅能利用 SSD 裸带宽的 1/4 到 1/3，即便是接近 1MB 的大写请求，吞吐量也不到裸带宽的 1/2。与此同时，新兴的非易失性内存（NVM）技术虽然已经停产了 Intel Optane DCPMM，但 RRAM、PCRAM、MRAM 和 memory-semantic SSD 仍在持续发展，NVM 具有字节可寻址和低延迟持久化的特性，适合小粒度 IO 访问。

---

## 二、要解决的问题

现有 SSD 文件系统的 request-to-IO 转换流程存在三个根本性能瓶颈：

1. **SSD-page 对齐开销**：未对齐的写需要 read-modify-write（RMW），16KB 未对齐写延迟高达对齐写的 10.71 倍，即使 1MB 大写也有 1.85 倍的额外延迟。

2. **Page cache 软件开销**：buffered IO 模式下的 page caching（页分配、锁、LRU 管理、数据拷贝）和 fsync() 调用占写时间的 9.5%-65.8%，而 direct IO 模式可以避免这些开销但要求严格对齐。

3. **IO 并发不足**：即使单线程做完美对齐的大写 direct IO，也只能利用 SSD 裸带宽的约 89%，显式的 IO 拆分 + 多线程执行可进一步提高 1.02×-1.56× 吞吐。

现有混合 NVM-SSD 系统要么把 NVM 当上层缓存（Strata、SPFS），导致 SSD 高带宽被浪费；要么简单按写大小分流到 NVM/SSD（UHS、DAOS），忽视了 SSD 写的对齐问题。

---

## 三、洞察与设计

**关键洞察**：SSD 日益增长的高写带宽可以被充分利用的前提是所有发往 SSD 的 IO 都必须是 SSD-page 对齐的、direct IO 模式的、且多线程并发执行的；而 NVM 的字节可寻址和低延迟特性恰好与 SSD 的 IO 特征互补——NVM 可以快速吸收残余的未对齐小 IO，使得 SSD 始终工作在最优数据路径上。

基于这一洞察，OrchFS 重新设计了文件系统的 request-to-IO 转换功能，核心设计包括：

**异构数据布局**：定义三种存储单元——SSD block（默认 32KB，两个 SSD-page）、NVM page（4KB）、NVM Upage（用于存储未对齐的 chunk，含 56B header 索引 chunk 位置）。

**基于对齐的写分区（Write Partition）**：采用两个策略：
- **对齐优先（AP）策略**：将任意模式的写拆分为 block 对齐的 SSD-IO、page 对齐的 NVM-IO、和 page 未对齐的 chunk-IO
- **碎片最小化（FM）策略**：尽量使用最少的存储单元，Upage 内的 chunk 支持地址重叠合并

**统一的 per-file 映射结构（HRtree）**：在 Linux radix tree 底层加一个异构层，包含 Append-write ELN 和 Overwrite ELN 两种扩展叶节点，统一索引跨 NVM 和 SSD 的分散数据，避免维护两套独立索引。

**嵌入式并行 IO 引擎**：默认 4 个 NVM IO 线程 + 32 个 SSD IO 线程，地址空间交错绑定，每个大 SSD-IO 被透明拆分为多个 32KB 对齐 IO 并行执行。SSD 写走 direct IO，SSD 读走 buffered IO，NVM 走 memory-semantic 路径。

**三条数据路径**：
1. SSD 写路径：direct IO + 多线程，用于 block 对齐的写
2. SSD 读路径：buffered IO + page cache，天然受益于对齐写
3. NVM 路径：memory-semantic load/store，用于小的未对齐 IO 和元数据

---

## 四、实现细节

- 从零实现原型，参考了 NOVA、Strata、OdinFS、ArckFS、F2FS，代码开源于 GitHub
- 基于 Linux kernel 5.18.18，修改内核 radix tree 实现 HRtree
- 继承 LibFS-KernelFS 架构：LibFS 运行在用户态处理请求，KernelFS 负责元数据安全验证和全局状态
- 引入地址对齐的共享内存空间，在 KernelFS 和 LibFS 之间交换 SSD 写数据，同时满足 direct IO 的 buffer 对齐要求和 SSD 数据安全，性能开销 <10%
- NVM Upage header 56B，含 14 个 4B 条目（2B offset + 2B size），当 header 条目用完时自动将 Upage 数据回写到对应 SSD block 并回收 NVM 空间
- Crash consistency 通过 NVM 上的 logical journaling 实现，默认保证原子元数据操作
- 数据迁移：NVM 利用率高或空闲时触发，优先迁移占用更多 NVM page/Upage 的逻辑块，细粒度的 block 级锁而非 file 级锁

---

## 五、实验结果

**实验环境**：2× Intel Xeon Gold 6348 (28 cores, 2.6GHz), 256GB DDR4, 128GB Intel Optane PM, PCIe 4.0 Samsung PM9A3 (6.8/4.2 GB/s 读/写), PCIe 5.0 Samsung PM1743 (14/6 GB/s 读/写)

**基线**：EXT4, F2FS (SSD); NOVA, OdinFS, ArckFS (NVM); Strata, SPFS, PHFS (混合)

| 实验 | OrchFS 提升 | 说明 |
|------|------------|------|
| 单线程随机写延迟 | 最高 29.76× (vs EXT4) | 大写仅 <5% 数据写入 NVM |
| 单线程读吞吐 | 最高 6.79× | 得益于对齐写后的大块对齐读 |
| 多线程写吞吐 | 2 线程即饱和 SSD 带宽 | 基线需 6+ 线程 |
| Filebench (16线程) | 1.76×-15.12× | Fileserver/Webproxy/Varmail |
| YCSB + LevelDB | 最高 9.82× (vs SSD FS) | >95% 数据在 NVM（小 KV 写） |
| GridGraph PageRank | 1.69×-3.20× | Twitter/LiveJournal/Friendster |
| NVM 空间使用 | 1MB 写仅 4.7% 数据到 NVM | 极端 1KB 全写 NVM，迁移 12s 完成 |
| 并行引擎贡献 | 最高降低 48.6% 写延迟 | 32 SSD-IO 线程最优 |

---

## 六、批判性分析

1. **NVM 硬件依赖的现实困境**：论文依赖 Intel Optane DCPMM 做 NVM，而 Intel 已停产该产品线。论文虽然提到 RRAM/PCRAM/MRAM/memory-semantic SSD 在发展，但这些替代品在延迟、带宽、耐久性方面与 Optane PM 差异显著，论文未在任何替代 NVM 上验证，整个系统的实用前景存疑。

2. **实验评估的公平性问题**：OrchFS 对比的 SSD 文件系统（EXT4、F2FS）都是 buffered IO + fsync 模式，而 OrchFS 的 SSD 写走 direct IO 且不经过 page cache。这个比较本质上是"传统文件系统的通用路径" vs "针对特定硬件组合的优化路径"，优势很大程度来自绕过了 page cache，而非 OrchFS 独有的创新。若 EXT4 也配合 io_uring + direct IO 使用，差距可能大幅缩小。

3. **29.76× 的 speedup 具有误导性**：这个最大加速比来自小写（1-4KB）场景，此时 OrchFS 100% 写入 NVM，本质上退化为一个 NVM 文件系统与 SSD 文件系统的比较。真正体现 OrchFS 核心价值（写分区 + 对齐优化）的大写场景加速比在 1.41×-7.16× 之间，摘要中的 29.76× 放大了印象。

4. **写分区的 overhead 在混合负载中未充分评估**：写分区、HRtree 索引、跨 NVM-SSD 数据分布增加了文件系统复杂度。论文的 Filebench 和 YCSB 评估虽然涵盖了一些混合场景，但缺乏对 write partition 本身计算开销的 microbenchmark（如 partition 决策时间与写 IO 时间的比值）。

5. **数据迁移的成本模型缺失**：论文只给了极端场景（1KB 全写 NVM）的迁移时间（12s），但未分析正常工作负载下迁移的触发频率、迁移期间对前台性能的干扰、以及 NVM 空间不足时的降级行为。

6. **单机假设，缺乏分布式场景讨论**：高带宽 SSD 更多部署在分布式存储系统中（如 Ceph、DAOS），OrchFS 的 LibFS-KernelFS 架构如何适配分布式场景未被讨论。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint 写加速**：大模型训练中 checkpoint 写入是典型的大文件顺序/半顺序写，OrchFS 的对齐分区 + 并行 IO 引擎思路可直接应用于加速 checkpoint 持久化，尤其在 NVMe SSD 上避免 page cache 开销。

2. **KV Cache offloading 的启示**：LLM 推理中 KV cache 的 offload 到 SSD 是热门方向（如 FlexGen），OrchFS 揭示的 SSD 对齐敏感性（16KB 未对齐写 10.71× 延迟惩罚）对 KV cache 的 SSD offload 方案设计有直接参考价值——需要确保 swap 粒度与 SSD-page 对齐。

3. **训练数据加载**：大规模数据加载（如 WebDataset）涉及混合大小的读操作，OrchFS 的多线程 IO 引擎和对齐优化思路可借鉴，但需注意 AI 数据加载主要是读密集型，OrchFS 的核心优化在写侧。

4. **可操作的研究方向**：
   - 将 OrchFS 的写分区思想移植到用户态存储引擎（如基于 io_uring 的方案），摆脱对 NVM 硬件的依赖，用 DRAM buffer 替代 NVM 吸收未对齐写
   - 研究 GPU Direct Storage (GDS) 场景下的 IO 对齐问题，GDS 绕过 CPU page cache 直接从 SSD 到 GPU 内存，与 OrchFS 的 direct IO 路径有相似的对齐需求

---

## 八、总结

OrchFS 是首个 SSD-NVM 异构 IO 编排文件系统，通过重新设计 request-to-IO 转换过程，将任意模式的写请求主动分区为 SSD-page 对齐的 SSD-IO 和残余的小粒度 NVM-IO，配合 direct IO + 多线程并行引擎，使 SSD 始终工作在最优写路径上。在多种 benchmark 和真实应用中相比传统 SSD 文件系统获得显著提升。主要局限在于依赖已停产的 Intel Optane NVM 硬件，且小写场景本质上退化为 NVM 文件系统，核心创新的适用范围主要在中大写混合场景。
