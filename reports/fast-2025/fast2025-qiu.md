# GeminiFS: A Companion File System for GPUs

**作者**：Shi Qiu, Weinan Liu, Yifan Hu, Jianqin Yan, Zhirong Shen (NICE Lab, Xiamen University); Xin Yao, Renhai Chen, Gong Zhang (Huawei Theory Lab); Yiming Zhang (NICE Lab, Xiamen University & Shanghai Jiao Tong University)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/qiu
**源文件**：[fast2025-qiu.pdf](../../papers/fast-2025/fast2025-qiu.pdf)

---

## 一、背景

GPU 加速的机器学习应用（GNN、LLM 等）产生了海量的数据存储需求，数据规模可达数十 TB 甚至 PB 级。GPU 显存容量虽然持续增长，但与应用需求之间的差距仍在扩大。基于存储（SSD/NVMe）的 GPU 显存扩展方案比基于 DRAM 的方案更具成本效益，成为重要的研究方向。

现有的 GPU 存储访问方案分为两类：
- **CPU-centric**（如 GPUfs、GDS、Dragon）：依赖 CPU 发起存储访问，CPU 成为瓶颈，CPU-GPU 同步开销大，无法满足 GPU 高并行度需求。
- **GPU-centric**（如 BaM）：GPU 直接通过 NVMe 队列访问存储设备，绕过 CPU，但缺乏文件系统抽象，无法提供文件管理、数据隔离、crash consistency 等能力。

---

## 二、要解决的问题

1. **GPU-centric 方案缺乏文件系统支持**：BaM 等方案将 NVMe 作为裸设备使用，缺少文件抽象和元数据管理，无法与 host 文件系统共享数据，GPU 进程间也难以共享数据。
2. **CPU-centric 方案性能不足**：GPUfs 在 1024 线程时延迟暴涨约 250%；GDS 软件栈开销占总延迟 90% 以上；CPU 核数有限导致并行度瓶颈。
3. **在 GPU 上构建通用文件系统极其困难**：GPU 不适合运行需要复杂元数据维护的有状态软件，缺乏特权模式、分支预测、乱序执行等 CPU 特性。
4. **NVMe 驱动限制**：现有内核 NVMe 驱动不支持 CPU 和 GPU 同时建立 I/O 队列对。
5. **GPU page cache 效率问题**：GPU 缺乏特权模式，page cache 只能在用户空间进程内分配，多进程间难以共享，锁竞争更严重。

---

## 三、洞察与设计

**关键洞察**：GPU 加速的 ML 工作负载具有两个关键特征——（1）存储 I/O 模式具有可预测性，数据访问模式和大小可以根据模型配置在运行前静态分析得出；（2）大部分磁盘数据在其生命周期内是只读的，写入仅通过 append 方式进行。这意味着文件元数据也是可预测且稳定的，可以预先分配固定大小文件并嵌入元数据，从而避免在 GPU 侧动态分配和同步元数据。

基于这一洞察，GeminiFS 设计了一个**伴侣文件系统（Companion File System）**，与 host 文件系统共存：

### 3.1 元数据嵌入（GVDK 文件格式）
- 选择性地将文件私有元数据（文件类型、大小、I/O block size、索引结构、block bitmap）嵌入文件本身，而非嵌入全部文件系统元数据。
- 使用两级映射表（L1/L2 table）将文件偏移映射到 NVMe 物理偏移，避免 GPU 执行复杂的 extent tree 遍历。
- 通过 GVDKhelper 内核模块在文件创建时获取物理 block 映射并嵌入文件，容量开销仅约 0.2%。

### 3.2 CPU/GPU 共享 NVMe 驱动（SNVMe）
- 扩展内核 NVMe 驱动，增加 GPU 缓冲区管理模块，在 NVMe 初始化时同时在 GPU 内存中创建 I/O 队列对。
- 利用 `nvidia_p2p_get_pages_persistent` 和 `nvidia_p2p_dma_map_pages` 将 GPU 内存中的队列转换为 DMA 地址，使 NVMe 设备可见。
- GPU 侧使用 BaM 的高吞吐 I/O 队列驱动进行 SQ 提交和 CQ polling。

### 3.3 GPU 专用 Page Cache
- **跨进程共享**：通过 host 侧管理模块和 CUDA IPC memory handle 实现多 GPU 进程共享同一 page cache。
- **Warp 级锁获取**：以 warp 而非 thread 为粒度获取 page，将并发锁竞争从数千级降低到 ~432 级（108 SM × 4 warp scheduler）。
- **常数时间容器**：使用 hash table + 双向链表实现 O(1) 的 page 插入、删除和查找。
- **可配置参数**：page size、cache size、prefetch 页数均可调，提供大调优空间。

### 3.4 编程模型（libGemini）
- 提供 POSIX-like API（G_open、G_close、G_read、G_write、G_sync），降低编程复杂度。
- CPU 侧接口负责初始化和文件打开，GPU 侧接口负责读写，可直接集成到 PyTorch DataLoader 等框架。

---

## 四、实现细节

- **代码规模**：共享 NVMe 内核模块约 2000 LoC，libGemini 约 3000 LoC。
- **GVDK 文件格式**：以 host 文件系统 block 大小（如 EXT4 的 4KB）为单位组织。第一个 block 存储私有元数据，open 时加载到 GPU 内存。两级索引表（L1 可变大小但连续，L2 固定一个 block）实现文件偏移到 NVMe 偏移的快速翻译。
- **SNVMe 初始化**：分三步——（1）在 GPU 内存分配 I/O 队列并转换为 DMA 地址；（2）执行标准 NVMe 初始化；（3）向 NVMe 控制器注册 GPU 侧 I/O 队列，GPU 队列使用 GPU 线程 polling 而非 host 中断。
- **Page Cache 实现**：zero-reference page 集合使用 hash table + 双向链表（LRU 淘汰），支持 prefetch 策略（cache miss 时预取多页）。
- **Crash Consistency**：通过 dirty bitmap 跟踪已写页面，提供 G_sync 接口由应用显式调用，不自动保证 crash consistency（因大部分数据只读，中间数据不需要一致性保证）。

---

## 五、实验结果

**实验平台**：64 核 Intel Xeon 5416S，512GB 内存，NVIDIA A100 80GB GPU（PCIe Gen4 x16, 64GB/s），Intel Optane P5800X NVMe SSD（7GB/s，4µs 延迟），EXT4 文件系统，Ubuntu 20.04，Linux 5.15.0。GPU 分配 32 个 NVMe I/O QP，host 分配 64 个。

### 微基准测试（4KB 随机读）

| 指标 | GeminiFS vs GPUfs | GeminiFS vs GDS | GeminiFS vs BaM |
|------|------------------|-----------------|-----------------|
| 带宽 | 平均 7.33× | 128-512 线程时 6.2× | 略低 4.6% |
| 延迟 | 降低 79.6%-90.9% | 1024 线程时仅为 GDS 的 17% | 仅增加 4.8% |

- GeminiFS 在 1024 线程时达到 NVMe 设备带宽上限。
- GDS 在低线程（1-16）时延迟比 GeminiFS 低 57.2%（CPU 4GHz vs GPU 1GHz 的频率优势），但高并行度下急剧退化。

### Page Cache 性能

| 配置 | 结果 |
|------|------|
| Prefetch 效果 | 读/写带宽分别提升 2.4×/2.34×，接近理论峰值 |
| Warp 数量扩展 | 从 1 warp 的 ~2.3 GB/s 线性扩展到 1024 warp 的 ~658 GB/s |
| Page size 影响 | 4KB→1024KB，读写带宽从 ~48 GB/s 提升到 ~121 GB/s |
| 峰值带宽 | 超过 640 GB/s，需约 100 块 NVMe 才能饱和 |

### LLM 训练（GPT2-124M）

| 场景 | GeminiFS 相比 Native | 相比 DLRover-RM | 相比 GDS |
|------|---------------------|-----------------|---------|
| 不卸载 activation | 运行时间减少 25% | 减少 12% | 减少 10% |
| 卸载 activation | 运行时间减少 94.5% | - | 减少 91% |
| Checkpoint 写入时间 | 减少 85% | 减少 75% | 减少 59% |

---

## 六、批判性分析

1. **实验规模和代表性不足**：LLM 训练实验仅使用 GPT2-124M（1.5B 参数），只跑 3 步训练，且只用单 GPU。这与论文声称面向的 "大规模 ML 工作负载" 场景差距巨大。现代 LLM 训练通常涉及数十到数千 GPU 和数万亿参数，论文在多 GPU 场景下的表现完全未验证。

2. **多 GPU 支持缺失**：论文承认 GeminiFS 尚未完全支持多 GPU，但这恰恰是实际 AI 训练最核心的需求。在多 GPU 场景下，NVMe QP 的分配、跨 GPU page cache 共享、并发元数据同步等问题的复杂度会显著上升，当前设计能否扩展尚不清楚。

3. **基线比较不完全公平**：与 BaM 的比较中，BaM 使用裸设备而 GeminiFS 使用文件系统接口，这是合理的开销对比。但 activation offloading 实验中 94.5% 的提升很可能主要来自 GPU-centric 架构本身（绕过 CPU），而非 GeminiFS 的文件系统设计贡献。论文未拆分这两方面的贡献。

4. **工作负载假设过强**：论文的核心假设是 GPU 存储 I/O 可预测且大部分只读/append-only。但实际场景中，动态 batching、弹性训练、模型并行策略切换等都可能产生不可预测的 I/O 模式。论文未讨论 GeminiFS 在这些情况下的退化表现。

5. **仅支持 EXT4**：GVDK 格式依赖于从 host 文件系统获取物理 block 映射，论文仅在 EXT4 上验证。对于 XFS、Btrfs 等文件系统的兼容性未讨论，且 EXT4 的 block size 不能超过系统 page size 的限制也被直接继承。

6. **Crash Consistency 被弱化处理**：论文将 crash consistency 留给应用通过 G_sync 显式处理，理由是 "大部分数据只读"。但 checkpoint、KV-cache 写入等场景确实需要一致性保证，将此责任完全推给应用开发者增加了使用复杂度，与论文宣称的 "降低编程复杂度" 存在矛盾。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴价值
- **GPU-centric 存储路径**的思路对 AI Infra 有重要参考意义。当前 LLM 训练/推理中的 checkpoint、KV-cache 持久化、activation offloading 都涉及大量 GPU-Storage 数据搬运，绕过 CPU 的方案值得在生产系统中探索。
- **ML 工作负载特征驱动的系统设计**方法论值得学习：利用 I/O 可预测性和数据只读特性简化文件系统设计，是一种有效的 co-design 思路。

### 可迁移的技术
- **Warp 级 page cache 锁设计**可推广到 GPU 上的其他共享数据结构（如 KV-cache 管理、GPU 内存池）。
- **元数据嵌入文件**的思路可应用于 AI 训练框架的 checkpoint 格式设计，将 tensor 布局信息嵌入 checkpoint 文件以加速恢复。
- **SNVMe 共享驱动**的思路可扩展到 CXL 设备、远程 NVMe-oF 等新兴存储互连场景。

### 值得跟进的方向
1. **多 GPU + 多 NVMe RAID 的 GeminiFS 扩展**：论文 roadmap 提到但未实现，这是将该工作推向实用的关键一步。特别是在 NVMe-oF 场景下，如何为多 GPU 提供聚合存储带宽。
2. **与 vLLM/SGLang 等推理框架集成**：将 GeminiFS 用于 KV-cache 的 prefix caching 持久化，替代现有的 CPU-centric 方案。
3. **GPU-centric Checkpoint 系统**：结合 GeminiFS 的直接存储访问能力和 PyTorch DCP（Distributed Checkpoint）框架，实现 GPU 直接写 checkpoint 到 NVMe，消除 CPU 内存中转。

---

## 八、总结

GeminiFS 提出了 GPU 伴侣文件系统的概念，通过元数据嵌入、共享 NVMe 驱动和 GPU 专用 page cache 三个核心设计，在保留文件系统抽象的同时实现了 GPU 到 NVMe 的直接高效访问。微基准测试显示其带宽达到 BaM（裸设备）的 95% 以上，同时大幅优于 CPU-centric 方案。主要局限在于仅支持单 GPU、实验规模小、工作负载假设较强，距离实际大规模 AI 训练场景的应用还需要在多 GPU 扩展和框架集成方面做大量工作。
