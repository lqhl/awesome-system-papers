# VectorCDC: Accelerating Data Deduplication with Vector Instructions

**作者**：Sreeharsha Udayashankar, Abdelrahman Baba, Samer Al-Kiswany（University of Waterloo）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/udayashankar
**源文件**：[[fast2025-udayashankar.pdf]]

---

## 一、背景

数据去重（Data Deduplication）是云存储系统中节省存储空间的核心技术。微软和 EMC 的研究表明，云端存储的数据中存在大量冗余。数据去重包含四个阶段：数据分块（Data Chunking）、块哈希与比较、元数据创建和存储。其中数据分块和块哈希是最消耗计算资源的阶段。

Content-Defined Chunking (CDC) 算法是生产系统中广泛使用的分块方法，它根据数据内容特征确定块边界，比固定大小分块能获得更好的空间节省。CDC 算法分为两大类：基于哈希的算法（如 CRC、FastCDC、Gear、Rabin）和无哈希算法（如 AE、RAM、MAXP）。由于分块阶段在关键路径上执行数百万次，加速 CDC 算法对去重系统性能至关重要。

现代 CPU 普遍支持 SIMD 向量指令（SSE/AVX），已被广泛用于加速数学运算和多媒体应用，但在 CDC 加速方面的应用仍然有限。

---

## 二、要解决的问题

1. **CDC 分块是去重系统的性能瓶颈**：每次上传新数据都需要扫描全部数据进行分块，此阶段运行频率极高。

2. **已有的向量加速方案效果有限**：SS-CDC 是此前唯一尝试用 AVX 指令加速 CDC 的工作，但它针对的是基于哈希的算法，存在两个根本性问题：
   - SS-CDC 将滚动哈希与边界检测解耦，需要在整个源数据上运行滚动哈希，消除了最小块大小跳跃（minimum chunk size skipping）带来的吞吐量优势。
   - 滚动哈希具有天然的数据依赖性（当前哈希值依赖前一个字节的哈希值），SS-CDC 不得不使用昂贵的 scatter/gather 指令加载非相邻字节，导致加速比仅有 1.18×–1.59×。

3. **无哈希算法虽然更快但尚未被向量化**：无哈希算法（如 AE、RAM）通过局部极值确定块边界，比大多数哈希算法快 2–3×，但缺乏系统性的向量加速方案。

---

## 三、洞察与设计

**关键洞察**：所有无哈希 CDC 算法都可以分解为两个共同的子阶段——极值字节搜索（Extreme Byte Search）和范围扫描（Range Scan），而这两个阶段都天然适合使用向量指令进行并行加速，无需处理哈希算法中固有的数据依赖问题。

基于此洞察，VectorCDC 提出了两种加速技术：

### Tree-based Extreme Byte Search

用于加速在固定窗口内搜索最大/最小字节的操作：
1. 将窗口分成多个子区域，每个子区域加载到 m512i 向量寄存器中
2. 使用 `_mm512_max` 指令对相邻寄存器进行逐字节取最大值
3. 通过树状归约方式逐层合并，最终得到包含全局最大值的单个寄存器
4. 顺序扫描最终寄存器确定极值字节的位置

### Packed Scanning for Range Scan

用于加速字节逐一与目标值比较的操作：
1. 将目标值广播到向量寄存器 V1
2. 将 64 个相邻字节打包加载到向量寄存器 V2
3. 使用 `_mm512_cmpge` 向量比较指令一次比较 64 个字节，生成 64-bit 掩码
4. 若掩码非零则存在块边界，通过掩码值确定精确位置；否则加载下一批 64 字节

### 与具体算法的结合

- **RAM**：先用 Extreme Byte Search 找窗口最大值，再用 Range Scan 找第一个不小于该最大值的边界。每个块只需一轮迭代。
- **AE**：需要多轮 Range Scan + Extreme Byte Search 交替执行，因此加速比低于 RAM。

---

## 四、实现细节

- 用 **700 行 C++ 代码** 实现，集成到 DedupBench 基准测试框架中
- 支持三种指令集宽度：SSE-128（VRAM-128）、AVX-256（VRAM-256）、AVX-512（VRAM-512）
- 兼容最小块大小跳跃优化：与 SS-CDC 不同，VectorCDC 的边界检测和插入在 Range Scan 中同步完成，发现边界后可直接跳过 minimum_chunk_size 字节
- 不使用昂贵的 scatter/gather 指令，仅使用常规的 packed load、max、compare 操作
- 代码已开源：https://github.com/UWASL/dedup-bench（commit 17c5209 及之后版本）

---

## 五、实验结果

**实验平台**：
- Intel Ice Lake：双路 Xeon Silver 4314（32核），256GB RAM
- AMD EPYC Rome：16核 AMD 7302P，128GB RAM
- 均来自 CloudLab 平台

**数据集**：

| 数据集 | 大小 | 描述 |
|--------|------|------|
| DEB | 40GB | 65个 Debian VM 镜像 |
| DEV | 230GB | 100个 Rust nightly build 备份 |
| LNX | 65GB | 160个 Linux 内核发行版 (TAR) |
| RDS | 122GB | 100个 Redis 快照 |
| TPCC | 106GB | 25个 MySQL VM 快照 (TPC-C) |

**关键结果**：

| 指标 | 结果 |
|------|------|
| VRAM-512 吞吐量 | 24–26 GB/s（8KB 块） |
| vs SS-Gear 加速比 | **21×** |
| vs SS-CRC 加速比 | **46×** |
| vs 原生 RAM 加速比 | **16×** |
| VRAM-256 吞吐量 | ~19.5 GB/s |
| VRAM-128 吞吐量 | ~13.3 GB/s |
| VAE-512 vs AE 加速比 | ~4–5×（多轮迭代限制） |
| 空间节省影响 | **无影响**（与原生算法完全一致） |

- 向量加速不影响空间节省率，块大小分布与原生算法完全一致
- VRAM 在 Intel 和 AMD 平台上吞吐量相近
- 加速 FastCDC 使用 SS-CDC 方法无任何提速（minimum chunk size skipping 失效）
- VectorCDC 吞吐量比 FastCDC 高 12×

**吞吐量分解**（VRAM-128, 8KB, DEB vs LNX）：
- DEB：Extreme Byte Search 加速贡献 10 GB/s，Range Scan 额外贡献 3 GB/s
- LNX：Extreme Byte Search 贡献 5.7 GB/s，Range Scan 额外贡献 11 GB/s
- 两个阶段的加速效果取决于数据集特性，因此两者都需要加速

---

## 六、批判性分析

1. **仅评估了两种无哈希算法**：虽然论文声称 VectorCDC 可以加速所有无哈希 CDC 算法，但实际只评估了 AE 和 RAM，MAXP 等算法以"原生版本较慢"为由被省略。缺乏对更广泛算法族的验证削弱了通用性声明的说服力。

2. **空间节省的差距被轻描淡写**：论文承认无哈希算法在某些数据集上空间节省率低于哈希算法（最多 6%），但对于大规模存储系统，6% 的空间节省差异可能意味着数十 TB 的额外存储成本。论文未对此进行成本分析。

3. **实验场景单一**：所有实验均为单线程离线分块，未评估在真实去重系统中集成 VectorCDC 后的端到端性能提升。分块只是去重四个阶段之一，即使分块加速 16×，如果其他阶段（如哈希比较、I/O）成为新瓶颈，端到端收益可能远小于微基准结果。

4. **内存带宽瓶颈未讨论**：VRAM-512 达到 24–26 GB/s 的分块吞吐量，这已接近单路内存带宽的限制。论文未分析 VectorCDC 是否已经成为内存带宽受限（memory bandwidth bound），以及在多线程场景下是否存在带宽争用。

5. **AVX-512 的频率降低副作用未提及**：在 Intel CPU 上使用 AVX-512 指令会导致核心频率显著降低（thermal throttling），这可能影响同一核心上其他工作的性能。论文未讨论这一实际部署中的重要考量。

6. **缺乏与 GPU 加速方案的对比**：论文在相关工作中提到 StoreGPU 用 GPU 加速块哈希，但未讨论用 GPU 加速分块的可能性和对比，考虑到现代服务器普遍配备 GPU，这是一个有意义的基线。

---

## 七、总结

VectorCDC 提出了一种利用 SSE/AVX 向量指令加速无哈希 CDC 算法的方法，通过识别无哈希算法的两个共同子阶段（极值字节搜索和范围扫描），分别设计了树状搜索和打包扫描两种向量化技术。该方法在不影响空间节省率的前提下，将分块吞吐量提升至 24–26 GB/s，比已有的 AVX 加速方案（SS-CDC）快 21–46×。方法实现简洁（700 行 C++），兼容多种指令集宽度和 CPU 平台，已集成到开源基准框架 DedupBench。主要局限在于仅适用于无哈希算法、缺乏端到端系统评估、以及未分析内存带宽瓶颈等实际部署问题。
