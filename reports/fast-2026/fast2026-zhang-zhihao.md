# SkySync: Accelerating File Synchronization with Collaborative Delta Generation

**作者**：Zhihao Zhang (Xiamen University & Alibaba Cloud), Huiba Li (Alibaba Cloud), Lu Tang (Xiamen University), Guangtao Xue (Shanghai Jiao Tong University), Jiwu Shu (Tsinghua University), Yiming Zhang (Shanghai Jiao Tong University & Xiamen University)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/zhang-zhihao
**源文件**：[[fast2026-zhang-zhihao.pdf]]

---

## 一、背景

随着云计算向 Sky Computing 范式演进，多个地理分布的云之间需要高效的文件同步（file sync）。Sky Computing 通过云服务代理（broker）在多个独立云供应商间无缝调度任务，用户不再绑定单一云厂商。在这种架构下，跨云的数据同步变得越来越重要。

现有的文件同步方案分为全量同步和增量同步（delta sync）。Delta sync 只传输文件的修改部分，因此通常更高效。Delta sync 的核心流程包括三步：(1) 文件分块（chunking），(2) 分块校验和计算（checksum calculation），(3) 分块搜索匹配（chunk searching）。目前主流方案有基于固定大小分块（FSC）的 rsync 和基于内容定义分块（CDC）的 dsync。

---

## 二、要解决的问题

现有 delta sync 方案的核心瓶颈在于 **delta 数据生成的计算开销过高**：

1. **校验和计算代价大**：rsync 需要对文件所有字节做滑动窗口逐字节计算弱校验和（Adler32）；dsync 虽然用了更轻量的 rolling hash（FastFP），但仍需对全部文件字节计算弱校验和。
2. **分块搜索效率低**：rsync 和 dsync 都需从 16-bit hash code 遍历到 32-bit weak checksum 再到 strong checksum，多层查找开销大。
3. **客户端和服务端同步时间占比过高**：实验显示校验和计算和分块搜索占总同步时间的 71.2%–93.7%，即使使用 AVX-512 等硬件加速，由于不规则访问模式和 cache 利用率低，加速效果有限。

这些计算开销不仅消耗额外资源、与主要计算任务争抢 CPU，还显著增加了文件同步延迟，限制了 Sky Computing 的实用性。

---

## 三、洞察与设计

**关键洞察**：现代存储层（block devices、file systems、deduplication systems、distributed systems）为了数据完整性验证、错误检测、去重等管理目的，已经维护了丰富的元数据（校验和、密码学摘要）。这些已有的存储层元数据可以被复用于 delta 生成，从而避免重复计算。

基于此洞察，SkySync 提出"协作式 delta 生成"（collaborative delta generation）：

1. **复用存储层校验和**：直接从存储层（如 BTRFS 的 CRC32C、fs-verity 的 SHA-256、HDFS 的块校验和等）读取已有的固定大小分块校验和，避免重新计算。
2. **快速校验和组合算法**：对于 CDC 场景，变长分块的边界通常不与存储层的固定 4KB 分块对齐。SkySync 利用 CRC32C 的代数线性性质（基于 GF(2) 有限域），通过简单的 XOR 和追加零操作，从多个固定大小分块的校验和高效组合出变长分块的校验和。只需对边界处不对齐的少量字节单独计算。
3. **基于 Cuckoo Hashing 的轻量级分块搜索**：替换 rsync/dsync 的多层哈希查找，采用 Cuckoo hashing 结构。直接从 CRC32C 校验和派生两个候选桶位置（P₁ = CRC mod 2ˡ，P₂ = P₁ XOR 2ˡ⁻¹），每个桶固定 4 个条目。查找最多访问 2 个桶、8 个条目，减少了内存访问次数和 cache miss。

---

## 四、实现细节

**架构**：SkySync 在 rsync/dsync 的客户端和服务端各增加一个"Checksum Calculation & Searching Module"，该模块从底层存储系统的元数据中提取校验和。通信协议增加了元数据协商阶段。

**通信协议增强**：
- 客户端和服务端在初始请求中交换各自的分块大小和校验和类型
- FSC 场景：客户端对齐服务端的分块大小；CDC 场景：服务端对齐客户端的分块策略
- 校验和类型不一致时：弱校验和默认 CRC32C，强校验和优先采用服务端的类型

**存储层元数据提取的三种方式**：
- **用户态工具**：如 fs-verity、btrfs-progs，适用于 EXT4/F2FS/BTRFS
- **系统 API**：如 HDFS NameNode API，适用于分布式存储系统
- **自定义函数**：直接解析磁盘元数据格式，适用于缺少工具/API 的系统如 MeGA

**代码实现**：
- FSC-based SkySync：基于 librsync 库，约 1100 行 C++ 代码
- dsync 原型：约 1800 行 C++ 代码（原版未开源，自行实现）
- CDC-based SkySync：在 dsync 基础上增加约 1600 行 C++ 代码
- 开源地址：https://github.com/skysync-project/skysync

**Cuckoo Hash Table 细节**：每个桶预分配 4 个条目，弱校验和匹配的条目只存 CRC32C（4 字节），强校验和匹配后再存 SHA-256（32 字节），减少内存占用。

---

## 五、实验结果

**测试环境**：两台阿里云服务器（Intel Xeon 8269CY 4核 vCPU, 32GB 内存, 1TB EBS SSD），跨数据中心 WAN（RTT 35ms, 500Mbps），BTRFS 文件系统。

**基线**：rsync、dsync，以及各自的硬件加速版本（AVX-512/SSE SHA-NI/CRC 指令）。

### Micro-benchmark 结果（10MB/100MB 文件，insert/cut/inverse 修改）

| 指标 | SkySync-F vs rsync | SkySync-C vs dsync |
|------|-------------------|-------------------|
| 客户端同步加速 | 1.2×–2.0× (无 HW) / 1.1×–1.8× (HW) | 1.3×–1.7× (无 HW) / 1.2×–1.6× (HW) |
| 客户端计算开销降低 | 32.1%–64.9% (无 HW) / 20.5%–54.3% (HW) | 25.7%–42.3% (无 HW) / 20.5%–35.3% (HW) |
| 服务端计算开销降低 | 最高 89.3% (无 HW) / 76.5% (HW) | — |
| 校验和计算时间降低 | 23.4%–88.3% (无 HW) | 24.5%–33.6% (无 HW) |
| 分块搜索时间降低 | 最高 61.3% | 65.7% |

### 真实数据集结果（5 个数据集：Chat 25.4GB, Ubuntu 32.8GB, Nutsnap 53.7GB, Enwiki 188.5GB, Kernel 221.3GB）

| 指标 | SkySync vs rsync/dsync |
|------|----------------------|
| 多线程同步加速 | 约 1.2×–1.5× (无 HW) / 1.15×–1.4× (HW) |
| 客户端+服务端时间降低 | 19.2%–43.7% (无 HW) / 16.2%–36.4% (HW) |
| 网络流量 | 与 rsync/dsync 基本一致 |

### 元数据提取开销

- BTRFS 提取最快（原生校验和），EXT4/F2FS 需 fs-verity 开销更大
- 元数据提取时间远小于直接计算校验和（1.8s–119.2s vs 26s–246s）
- 提取时间占总同步时间 0.11%–7.14%（BTRFS）

---

## 六、批判性分析

1. **改进幅度在硬件加速下显著缩水**：无 HW 时客户端加速 1.2×–2.0×，有 HW 后降至 1.1×–1.8×，真实数据集仅 1.15×–1.4×。随着硬件加速成为标配（Intel CRC32 指令已广泛可用），SkySync 的优势空间会进一步收窄。

2. **对存储层的强依赖是部署障碍**：SkySync 要求底层存储系统提供可用的校验和元数据，且需要 fs-verity 启用、BTRFS/ZFS 特定配置、或自定义函数解析。这意味着：(a) 不能在任意文件系统上开箱即用；(b) 不同存储系统需要不同的集成方式（三种提取方法各有限制）；(c) 自定义函数需要跟随目标系统版本更新维护。论文轻描淡写了这些部署复杂性。

3. **Sky Computing 动机与实验场景不匹配**：论文以 Sky Computing 跨云同步作为核心动机，但实验仅在两个阿里云数据中心之间进行（同一云厂商内），未验证跨不同云厂商（如 AWS ↔ GCP ↔ Azure）的异构存储环境下的表现。跨厂商场景下存储层元数据类型不统一的问题可能更加突出。

4. **真实数据集的加速倍率 modest**：在真实数据集上 1.2×–1.5× 的加速，考虑到需要额外的存储层集成工作，实际收益与部署成本之比值得商榷。特别是论文没有量化部署和维护 SkySync 的工程开销。

5. **Cuckoo Hashing 的碰撞处理不够充分**：论文声称每桶 4 个条目足够，但仅基于"经验发现"，缺乏理论分析或极端情况下的性能退化讨论。大文件高修改率下桶溢出的概率和影响未被分析。

6. **校验和安全性降级风险**：通信协议中，当客户端和服务端强校验和类型不一致时，默认采用服务端的类型。若服务端使用较弱的 SHA-1 而客户端使用 SHA-256，则整体安全性被拉低到 SHA-1 水平，论文未讨论这一安全隐患。

---

## 七、总结

SkySync 提出了一种利用存储层已有元数据来加速文件同步的方法，核心思路是复用存储系统为数据完整性等目的维护的校验和，配合 CRC32C 的代数线性性质实现快速校验和组合，以及基于 Cuckoo Hashing 的轻量级分块搜索。在 BTRFS 等原生提供校验和的文件系统上，SkySync 可将计算开销降低最高 89.3%，同步速度提升 1.1×–2×，且不增加网络流量。其主要局限在于对存储层元数据的强依赖限制了通用性，且在硬件加速已普及的环境下改进幅度收窄。适用于存储系统已部署校验和机制的大规模云存储和跨云同步场景。
