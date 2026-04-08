# Towards Condensed and Efficient Read-Only File System via Sort-Enhanced Compression

**作者**：Hao Huang, Yifeng Zhang, Yanqi Pan, Wen Xia, Xiangyu Zou, Darong Yang (Harbin Institute of Technology, Shenzhen); Jubin Zhong, Hua Liao (Huawei Technologies Co., Ltd)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：[USENIX](https://www.usenix.org/conference/fast26/presentation/huang)
**源文件**：[[fast2026-huang.pdf]]

---

## 一、背景

只读压缩文件系统（如 EROFS、Squashfs）在 IoT 设备内核、Android 智能手机和 Docker 容器镜像等空间敏感场景中广泛使用。这些文件系统通过禁止写入来构建紧凑的存储布局，并结合块压缩进一步缩小镜像体积。随着 IoT 设备预计在 2030 年达到 254.4 亿台，即使微小的压缩率提升也能带来巨大的硬件成本节约；对于容器镜像，更小的体积意味着更短的拉取和启动延迟。

现有的只读文件系统将数据分成固定大小的块（如 1MB），然后分别压缩每个块。然而，这种块划分方式无法充分利用压缩算法的能力——即使增大块尺寸，压缩率仍远低于直接压缩整个镜像（不做块划分）的效果。

---

## 二、要解决的问题

1. **数据混合问题（Data Mixture Problem）**：块划分不可避免地将不相似的数据混合在同一个块中，同时将相似的数据分散到不同块中。字典压缩只能在块内寻找重复数据串，无法跨块消除冗余，导致压缩率显著低于理论上限。

2. **读放大问题（Read Amplification）**：使用大块（如 1MB）虽然能略微提升压缩率，但在随机读取场景下会导致严重的读放大——需要加载并解压整个大块才能获取少量所需数据。排序进一步加剧了这个问题，因为排序后热数据和冷数据混杂在不同块中。

3. **镜像构建时间过长**：基于相似性的排序需要计算所有 chunk 对之间的相似度，计算复杂度高达 O(N²×M²)，对于较大的镜像来说构建时间不可接受。

---

## 三、洞察与设计

**关键洞察**：块压缩的压缩率瓶颈来自字典压缩（而非熵编码），其根因是块内数据混合导致字典压缩无法跨块发现重复数据串。如果在压缩前先按相似性对数据 chunk 进行排序和聚类，使相似 chunk 落入同一个压缩块，就能让字典压缩在块内充分消除冗余，逼近甚至超越直接压缩的效果。

基于这一洞察，论文提出 RubikFS——一个排序增强的只读文件系统。其核心设计是在传统的「打包文件 → 分块 → 压缩」工作流中插入四个组件：

- **Data Grouper**：按文件类型（ELF Code、ELF Data、Binary、Text、Others）预分组，相同类型的数据更可能相似，分组后可减少相似度计算量
- **Data Chunker**：将数据流切分为固定大小的 chunk（大小为 BlockSize/16，最小 4KB），并进行全量去重
- **Hotness Grouper**：基于 trace 信息将 chunk 分为热/冷子组，热数据集中存放以减少启动阶段的读放大
- **Similarity Sorter**：提取 chunk 特征 → 构建相似度图 → 用 METIS 算法做子图划分 → 子图内和子图间分别按相似度排序

---

## 四、实现细节

RubikFS 基于 EROFS 实现，修改约 3.5K 行代码，包含用户态镜像构建工具（RubikFS.mkfs，基于 erofs-utils 1.8.10）和内核文件系统（基于 Linux 6.16 的 EROFS 源码）。

**特征提取**：使用 gear hash 以字节粒度扫描 chunk，每 1/P 字节（默认 P=1/128）记录一个最大哈希值作为特征。两个 chunk 的相似度 = 相同特征数 × 2 / 总特征数。

**相似度图生成**：用哈希表将相同特征散列到同一桶中，复杂度从 O(N²×M²) 降至 O(N)（特征均匀分布时）。移除 0 值边进一步加速。

**子图划分**：使用 METIS 算法将相似度图划分为大小为 64 的子图，目标是最大化子图内边权重、最小化跨子图边权重。复杂度 O(V+E)，移除 0 值边后可降至 O(V)。

**排序策略**：两阶段排序——子图内按相似度排序（相同特征最多的 chunk 在前），子图间按聚合特征的相似度排序。

**索引**：每个 chunk 需要 12B 索引项（原始文件偏移、打包偏移、chunk 大小），存储开销 0.018%–2.93%。特征在排序完成后丢弃，不占用运行时空间。

**压缩算法支持**：LZ4、ZSTD、LZMA，均配置为最高压缩级别。压缩后生成固定大小、页对齐的块。

---

## 五、实验结果

**实验平台**：构建用 32 核 CPU + 128GiB DRAM 服务器；运行时用 FEMU（QEMU-based NVMe SSD 模拟器），配置 2 核 CPU、1GiB DRAM，页读延迟 75µs。

**评估镜像**：6 个开源镜像（openEuler 155MB、Harm-3516 667MB、Harm-3518 440MB、Harm-3861 42MB、Yocto 374MB、Friendica 771MB）。

**压缩率提升**：

| 对比基线 | 最大压缩率提升 |
|---------|--------------|
| EROFS / Squashfs | 最高 42.60% |
| Direct（直接压缩） | 在 Harm-3516/3518/3861 上甚至超越 Direct |

RubikFS 在所有镜像、所有压缩算法、所有块大小配置下均一致优于 EROFS 和 Squashfs。在 LZ4（字典仅 64KB）场景下提升最为显著。

**读放大缓解**（openEuler，1MB 块，12% 热数据）：

| 压缩算法 | RubikFS 启动时间 | EROFS 启动时间 | 读数据量降低 |
|---------|----------------|---------------|------------|
| LZ4 | 1.21s | 2.89s | 70.70% |
| ZSTD | 1.63s | 2.99s | 61.66% |
| LZMA | 3.72s | 9.15s | 66.09% |

**构建时间**（LZMA，1MB 块）：Data Grouper 使大镜像（Harm-3516）的排序时间从 +287.88s 降至 +208.37s。小镜像（Harm-3861）排序甚至加速了整体构建。

---

## 六、批判性分析

1. **评估镜像规模偏小**：所有测试镜像均在 42MB–771MB 范围，最大不到 1GB。论文声称 RubikFS 可扩展到更大镜像，但缺乏 GB 级甚至更大规模的实证数据。Discussion 中的可扩展性论证主要是定性分析，未提供实际的大规模镜像构建时间和内存占用数据。

2. **热数据 trace 获取方式的实用性存疑**：Hotness Grouper 依赖预先采集的 trace 文件来标记热 chunk。论文承认通用 I/O tracing 不在范围内，仅提供了一种基于 kprobe 的实践方法。对于容器场景，workload 多样且动态变化，固定 trace 的适用性有限。实验中热数据甚至是随机选取的文件，与真实访问模式可能存在差距。

3. **读放大实验设计可能偏向 RubikFS**：读放大评估仅在 openEuler 一个镜像上进行（"for space efficiency"），缺乏其他镜像（尤其是容器镜像 Friendica）的读放大数据。容器镜像的访问模式与嵌入式系统差异很大，仅报告最有利的场景不够全面。

4. **与 Direct 的超越缺乏深入解释**：论文提到 RubikFS 在部分镜像上甚至超越了 Direct（不做块划分的直接压缩），理由是排序让压缩器发现了 Direct 因字典距离限制而遗漏的冗余。但这实际上说明 Direct 的配置并非最优（例如可以增大字典），将其作为上界来对比的前提被削弱了。

5. **Naive Sorter 基线的公平性**：Breakdown 实验中的 Naive Sorter 使用 Palantir 的 12 个 super-features，但 RubikFS 使用远多于 12 个的特征（chunk_size/128 个）。特征数量的巨大差异使得两者的对比更多反映了特征数量的影响，而非算法本身的优劣。

6. **仅针对嵌入式和容器的特定场景**：论文的 Hotness Grouper 假设绝大多数读发生在启动阶段、运行时读很少，这适合嵌入式设备但不一定适合所有容器场景（如数据库容器、Web 服务器）。

---

## 七、总结

RubikFS 通过在只读文件系统的镜像构建流程中引入相似性排序，有效解决了块压缩的数据混合问题。其四个组件（Data Grouper、Data Chunker、Hotness Grouper、Similarity Sorter）协同工作，在 6 个开源镜像上实现了最高 42.60% 的压缩率提升和最高 70.70% 的读放大缓解。系统适用于 IoT 嵌入式设备和容器镜像等只读场景，主要局限在于热数据 trace 的获取依赖离线分析、大规模镜像的可扩展性缺乏实证验证、以及对非启动密集型 workload 的适用性尚未充分评估。
