# MedFS: Pursuing Low Update Overhead via Metadata-Enabled Delta Compression for Log-structured File System on Mobile Device

**作者**：Chao Wu, Cheng Ji (南京理工大学), Li-Pin Chang (阳明交通大学), Zongwei Zhu (中国科学技术大学), Congming Gao (厦门大学), Weichao Guo, Chao Yu (OPPO), Yanzhi Wang (Northeastern University)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/wu
**源文件**：[fast2025-wu.pdf](../../papers/fast-2025/fast2025-wu.pdf)

---

## 一、背景

移动设备上数据密集型应用（视频/照片编辑、社交媒体、即时通讯等）日益普及，这些应用频繁产生大量小文件和小更新，对基于 NAND Flash 的文件系统提出了严峻挑战。Flash 存储的 P/E 周期有限，写入量直接影响存储寿命。F2FS 作为广泛部署在商用移动设备上的 Log-structured File System (LFS)，通过将随机写转为顺序写来缓解写放大。然而，移动工作负载中 77.1% 的写流量来自文件更新，且更新前后的内容差异平均仅 13.8%，这为 delta 压缩提供了巨大空间。

传统数据压缩（LZO、LZ4、Zlib）在移动设备上计算开销过大，压缩效果对小文件也不理想。Delta 压缩（仅保存新旧数据的 XOR 差异）虽然高效，但需要额外维护 base page、delta chunk 及其索引，带来显著的读写放大。已有方案依赖 NVRAM 或电池供电 DRAM 等外部缓冲来存储 delta，但对成本敏感的移动设备来说并不可行。

---

## 二、要解决的问题

1. **Delta 压缩的维护开销**：传统 delta 压缩需要额外 I/O 来持久化 delta chunk 及其索引到 Flash，无论更新发生在 page cache 还是 Flash 上都无法避免。
2. **外部硬件依赖**：现有 delta 压缩方案依赖 NVRAM 或 battery-backed DRAM 作为 delta 缓冲，增加了硬件成本，不适合移动设备。
3. **Inline area 空间有限**：F2FS 的 inode inline area 仅约 3.69KB，无法容纳所有 delta chunk，需要精细的空间管理策略。
4. **读放大问题**：将 delta 存储在数据区会降低 cache 命中率，增加读延迟，影响用户体验。

---

## 三、洞察与设计

**关键洞察**：移动应用中大部分文件（90%）小于 3.69MB，其 inode inline area 有 94% 的空间未被利用；同时 inode 的 cache 命中率极高（平均 99.97%），因为任何文件操作都需要先访问 inode。因此，将小 delta chunk 嵌入 inode 的 inline area 中，可以在 inode 被标记为 dirty 时随 inode 一起刷盘，无需额外 I/O 即可完成 delta 的持久化。

MedFS 基于上述洞察，设计了两个核心组件：

**DCI (Delta Chunk Inlining)**：在文件更新时，计算 New 与 Base 页面的 XOR 差异并用 LZO 压缩为 delta chunk（平均压缩率 97.43%，每页仅约 106 字节）。如果 inline area 有足够空间且 delta 小于 256 字节阈值，则将 delta 存入 inline area 的 delta zone。Delta zone 从 inline area 尾部向头部扩展，与 data offset area 方向相反。由于 LFS 的 out-of-place 更新特性，base page 通过原始 LBA 即可访问，无需额外地址信息。

**DCM (Delta Chunk Maintenance)**：处理 DCI 无法容纳的 delta chunk。通过 HCluster（基于 K-Means 的在线文件热度聚类）将文件分为四类（read-hot-write-cold、read-cold-write-hot 等）。对 write-hot-read-cold 文件，将 delta chunk 打包到 Compact page 中以减少写 I/O；对其他文件则直接刷盘避免读放大。BGRes（Background Restoration）在系统空闲时评估文件热度变化，对不再适合压缩的文件进行解压恢复。

---

## 四、实现细节

- **基于 F2FS 实现**，修改了 Linux 内核 4.19 的 F2FS 代码
- **Delta 压缩时机**：在 `write_end()` 中执行，确保 Base 页面仍在 page cache 中
- **Inline area 布局**：delta zone 包含 delta chunk、c_addr（2B，页面偏移）和 c_size（1B），从 Xattr 旁向头部扩展。每个压缩后的 delta 约 109 字节，inline area 最多可存约 23 个 delta chunk
- **D2D 映射**：DCI 通过遍历 inline area 中的 delta zone 定位目标 delta；DCM 通过伪文件的 inode 中存储的 INO（4B）定位 meta-page，meta-page 中存储 Compact page 的映射信息（CN/FS/PI/DO 字段）
- **数据一致性**：严格按"先刷数据/delta、再刷 inode"的顺序。Delta eviction 和 BGRes 通过先在内存中复制 delta 来保证 crash consistency
- **Segment Cleaning**：DCI 仅更新 LBA，不改变文件内偏移；DCM 的 meta-page 和 Compact page 按普通页面迁移
- **HCluster 参数**：时间窗口 T = 60 秒，质心更新在 BGRes 后台完成

---

## 五、实验结果

**平台**：OnePlus 8T（Snapdragon 865, 8GB DRAM, 128GB UFS 3.1）, LineageOS (Android 14, Linux 4.19)

**测试应用**：Gmail(GM), Polish(PS), Spotify(ST), Telegram(TG), Twitter(TW), WeChat(WC), Zoom(ZM)

| 指标 | MedFS vs F2FS-NODC |
|------|-------------------|
| 平均写流量降低 | 55.1%（最佳 TG: 64.8%）|
| 存储寿命延长 | 122.7% |
| 平均写 I/O 延迟降低 | 28.8%（最佳 TG: 37.3%）|
| 平均读 I/O 延迟降低 | 25.3%（最佳 TG: 35.6%）|
| 用户感知延迟降低 | 平均 7.9%（IM 场景: 19.0%）|
| 能耗降低 | 9.2%（vs F2FS-NODC），2.6%（vs FPC）|

**组件贡献对比**：

| 方案 | 写流量降低 | Page cache 命中率 |
|------|-----------|-----------------|
| DCI alone | 37.9% | 78.0% |
| DCM alone | 47.4% | 59.9% |
| MedFS (DCI+DCM) | 55.1% | 71.6% |
| F2FS-DC | 10.9% | - |
| FPC | 37.6% | - |

**开销**：Delta 压缩/解压延迟分别为 7.4/8.3 μs（传统方法为 48.8/45.2 μs）；HCluster 平均 1.2 μs；DCM 存储 meta/Compact page 仅需 7.1MB（对应 4.2GB 文件）。

---

## 六、批判性分析

1. **App launching 场景性能倒退被轻描淡写**：MedFS 在应用启动时延迟增加约 3.0%，作者将其归因于解压开销。但应用启动是用户最敏感的场景之一，这个负面结果没有得到充分讨论。作者仅提到"用户可以选择不压缩关键 I/O"——这种 ad hoc 的解决方案削弱了系统的通用性。

2. **DCI 的 delta eviction 尾延迟问题严重**：Fig. 12(b) 显示 delta eviction 的处理时间从 42ms 到 475ms 不等，作者承认这会导致帧阻塞或丢帧。这个问题本质上是 DCI 设计的固有缺陷——当 inline area 空间不足时的 eviction 路径会阻塞前台 I/O。DCM 被引入来"缓解"这个问题，但并非根本解决。

3. **实验平台单一**：仅在一台 OnePlus 8T 上测试，UFS 3.1 存储。不同厂商的 Flash 固件行为差异很大，写放大因子不同，结论的可泛化性存疑。

4. **工作负载回放方法的局限**：虽然号称在真实手机上实验，但实际上是先录制 I/O trace，再通过用户态进程回放。这种方式忽略了真实多任务场景下的 I/O 竞争、内存压力导致的 page cache eviction 等因素。

5. **K-Means 聚类的合理性未充分验证**：HCluster 将文件分为四类，但为何选择 K=4？聚类效果仅在 Gmail 一个应用上展示（Fig. 11a），缺乏跨应用的系统性评估。文中提到 56.4% 的文件热度会发生变化，说明分类不稳定，BGRes 的开销可能在某些场景下不可忽略。

6. **与 SOTA delta 压缩方案未直接比较**：作者以"依赖外部缓冲、不适合移动设备"为由排除了 SOTA delta 压缩方案的对比，但这些方案在写流量降低方面可能更优。至少应该在同等硬件约束下进行模拟对比。

7. **存储寿命估算过于乐观**：122.7% 的寿命延长是在假设所有写流量都能被 MedFS 处理的情况下得出的，但实际中不可压缩的写流量（如多媒体文件写入）占比未被讨论。

---

## 七、总结

MedFS 提出了一种面向移动设备 LFS 的 metadata-enabled delta 压缩方案，巧妙利用 F2FS inode inline area 的空闲空间存储 delta chunk，避免了额外硬件成本和 I/O 开销。通过 DCI 和 DCM 两个组件的协同，在 7 个主流应用上实现了平均 55.1% 的写流量降低和 122.7% 的存储寿命延长。该方案适用于以小文件更新为主的移动工作负载，主要局限在于 app launching 等读密集场景的轻微性能回退、delta eviction 的尾延迟问题，以及单一平台验证的泛化性风险。
