# ParaSync: Exploiting Fine-Grained Parallelism for Efficient File Synchronization

**作者**：Zhihao Zhang (NICE Lab, Xiamen University; Alibaba Cloud), Lu Tang (NICE Lab, Xiamen University), Huiba Li (Alibaba Cloud), Yue Yu (Sun Yat-sen University), Guangtao Xue (Shanghai Jiao Tong University), Jiwu Shu (Tsinghua University), Yiming Zhang (Shanghai Jiao Tong University; NICE Lab, Xiamen University)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/zhang-zhihao-parasync
**源文件**：[[fast2026-zhang-zhihao-parasync.pdf]]

---

## 一、背景

文件同步（File Synchronization）广泛应用于云存储服务（Dropbox、Google Drive、OneDrive）、分布式存储系统和备份工具中，用于在多个节点和地理分散的位置之间更新和共享文件。Content-Defined Chunking (CDC) 是一种被广泛采用的分块算法，通过检测和消除同步文件之间的重复数据，显著减少网络传输量。

基于 CDC 的文件同步通常包含三个阶段：文件分块（File Chunking）、块匹配（Chunk Matching）和增量重建（Delta Reconstruction）。随着数据量和文件大小持续增长，特别是在分布式数据密集型计算环境中，CDC 同步的计算开销成为关键瓶颈。将大量小文件打包成无元数据的大文件的常见做法进一步加剧了这一问题。

---

## 二、要解决的问题

现有 CDC 文件同步方案存在三个核心问题：

1. **文件分块的顺序瓶颈**：分块阶段占总同步时间的 49.5%–75.1%。现有并行分块方法（如 SS-CDC）虽然并行化了边界搜索，但 checksum 计算被推迟到单线程的第二阶段，因为 checksum 只能在块边界串行确定之后才能计算。这导致并行扩展性有限（8 核仅约 2.9× 加速）。

2. **块匹配的 All-or-Nothing 交换依赖**：客户端必须等待服务器处理完整个文件的弱 checksum 匹配后，才能开始自己的强 checksum 验证。这种刚性的客户端-服务器依赖导致一端空闲等待另一端完成，网络利用率低。

3. **增量重建的顺序依赖**：传统 patch 命令使用相对偏移量，patch N 的目标位置依赖于 patch N-1 的完成，无法并行或乱序执行 patch 操作，导致网络传输、磁盘 I/O 和计算串行叠加。

此外，rsync 的流水线模型与 CDC 工作流不兼容——CDC 涉及三次同步屏障（client-server-client 依赖），破坏了 rsync 所需的连续单向数据流。

---

## 三、洞察与设计

**关键洞察**：CRC32C checksum 具有线性代数性质，合并块的 checksum 可以通过组合其子块的 checksum 高效推导，无需重新读取原始数据。这使得 checksum 计算可以与边界确定解耦——先并行计算子块的 checksum，再在轻量级合并阶段组合它们。

基于这一洞察，ParaSync 提出三项关键设计：

### 1. 并行文件分块（两阶段设计）

- **Stage 1（并行）**：将文件分割为等大的 segment，每个线程独立扫描其 segment，识别潜在块边界并计算每个子块（sub-chunk）的 CRC32C checksum，结果存入线程本地 FIFO 队列。每个队列条目仅 12 字节（8 字节偏移 + 4 字节 CRC32C）。
- **Stage 2（单线程合并）**：单线程按顺序扫描所有子块元数据，根据大小约束（S_min < S_chunk < S_max）合并相邻子块为最终块。合并块的 CRC32C 通过公式 `CRC32C(C1) = CRC32C(SC'1) ⊕ CRC32C(SC2)` 计算（其中 SC'1 是 SC1 附加零字节后的结果），无需重读文件数据。

### 2. 流式并行块匹配

- 服务器端 wmatcher 将共享同一弱 checksum 的块列表视为工作队列，动态分割为多个 segment 分配给不同线程，解决 checksum 分布高度倾斜（单个 checksum 可关联 120,000 个块）导致的负载不均衡问题。
- 匹配结果以小批次立即流式发送给客户端，而非等待整个文件处理完毕。
- 客户端 smatcher 收到每批 matching token 后立即构建小型强 hash 子表并开始并行验证，将刚性批量交换转变为连续流。

### 3. 基于绝对偏移量的流水线增量重建

- 每个 patch 命令嵌入绝对目标偏移量（而非相对偏移量），使 delta 生成与应用解耦。
- 服务器无需等待前一个 patch 完成即可知道下一个 patch 的写入位置，支持并行和乱序执行。
- Literal 数据分割为固定大小块，通过多流并发传输（类似 BitTorrent）。
- 服务器端使用双线程流水线：一个线程顺序写入 literal 数据，另一个线程同时从旧文件复制匹配块到新文件，最大化网络和磁盘 I/O 的重叠。

---

## 四、实现细节

- **实现规模**：ParaSync 约 4200 行 C++ 代码（对比 dsync ~1800 行，pdsync ~2900 行）。
- **Hash 算法**：Rolling hash 和弱 checksum 均使用 CRC32C（利用 Intel SSE 硬件指令加速），强 checksum 使用 BLAKE3。
- **块大小配置**：最小/期望平均/最大块大小为 4KB/8KB/12KB（与 Dell-EMC Data Domain 系统默认配置一致）。
- **Hash 表**：使用内存高效的 cuckoo hash table 构建索引。
- **I/O 处理**：使用 C++ 轻量级协程库（PhotonLibOS）进行高效 I/O 处理，每个线程 4 个协程。
- **线程绑定**：每个线程固定到单独的物理核心，最大线程数为 16（匹配物理核心数）。
- **内存优化**：线程本地队列采用按需分配的小型固定大小数组，支持 jemalloc/tcmalloc 等内存分配器优化。
- **CRC32C 组合**：利用 CRC32C 的线性性质，通过 XOR 操作和零字节扩展高效组合子块 checksum。
- **开源地址**：https://github.com/nicexlab/parasync

---

## 五、实验结果

**实验平台**：3 台云 ECS 实例，每台 16 核 Intel Xeon 8269CY @ 2.5GHz，512GB 内存，Ubuntu 22.04，4TB 云盘（顺序读/写 1400/1000 MB/s）。WAN: 50ms RTT, 500Mbps；LAN: 0.4ms RTT, 10Gbps。

**数据集**（覆盖 GB 到 TB 级别）：

| 数据集 | 描述 | 大小 |
|--------|------|------|
| Chat | WeChat 聊天记录备份 | 25.4 GB |
| Ubuntu | Ubuntu 版本镜像 | 32.8 GB |
| Nuts | NutStore 快照 | 53.7 GB |
| Enwiki | Wikipedia 备份 | 188.5 GB |
| Kernel | Linux Kernel 源码 | 221.3 GB |
| MySQL | MySQL 数据库备份 | 2.1 TB |
| VM | 虚拟机快照（含 LLM 模型和训练数据） | 2.4 TB |

**主要结果**：

| 指标 | ParaSync vs dsync | ParaSync vs pdsync |
|------|-------------------|-------------------|
| 文件分块吞吐量（8 线程） | 7.6× 加速 | 2.6× 加速 |
| 块匹配时间（WAN） | 减少 72.5%–84.2% | 减少 43.4%–60.3% |
| 块匹配时间（LAN） | 减少 75.1%–85.6% | 减少 43.1%–59.7% |
| 增量重建（WAN） | 减少 8.5%–35.2% | 减少 5.1%–21.5% |
| 增量重建（LAN） | 减少 15.2%–49.1% | 减少 10.3%–26.7% |
| 端到端同步（WAN） | 1.25×–2.4× 加速 | 1.14×–1.6× 加速 |
| 端到端同步（LAN） | 2.3×–3.7× 加速 | 1.5×–1.74× 加速 |
| 网络流量开销 | 仅多 3.2%（最多） | — |

ParaSync 的分块算法展现出近线性的线程扩展性。在 8 线程配置下，网络传输 literal bytes 占总同步时间的 76.1%–96.7%，表明计算已不再是瓶颈。

---

## 六、批判性分析

1. **端到端加速远低于分块加速**：分块阶段声称 7.6× 加速，但端到端仅 2.3×–3.7×（LAN）和 1.25×–2.4×（WAN）。WAN 场景下 literal bytes 传输占 76%–97% 的总时间，意味着 ParaSync 的计算优化在网络受限场景中收益有限。论文虽承认这一点，但标题和摘要给人的印象是大幅加速。

2. **dsync 基线的公平性存疑**：dsync 原型未开源，作者自行实现了 dsync 和 pdsync 作为基线。虽然声称基于发表的描述实现，但自行实现的基线可能无法完全反映原始系统的优化水平，存在无意中降低基线性能的风险。

3. **CRC32C 线性性质的适用范围**：核心设计依赖 CRC32C 的代数线性性质来组合子块 checksum。这意味着该方法不能直接推广到不具备此性质的 checksum 算法（如 Adler-32、SHA 系列）。论文未充分讨论这一限制对通用性的影响。

4. **实验配置单一**：所有实验在同一型号的 Intel Xeon 8269CY 上运行，未验证在 AMD 处理器或 ARM 架构上的表现。CRC32C 的 SSE 硬件加速是性能关键，不同硬件的指令支持差异可能显著影响结果。

5. **负载不均衡的讨论不够深入**：论文提到 checksum 分布高度倾斜（单个 checksum 关联 120,000 个块），但动态分割策略的具体调度算法和开销未详细分析。在极端倾斜场景下，动态分割本身可能引入额外的同步开销。

6. **绝对偏移量的空间开销被轻描淡写**：相比相对偏移量，绝对偏移量需要更多字节表示每个 patch 命令的目标位置，但论文仅提到"几乎相同"的元数据格式而未给出具体比较。

---

## 七、AI Infra / MLSys 视角

1. **模型 checkpoint 同步的潜在应用**：大模型分布式训练中，checkpoint 的增量同步是实际痛点。ParaSync 的并行 CDC 方法可直接应用于加速跨节点的 checkpoint 同步，特别是 TB 级模型权重的增量传输。VM 数据集（2.4TB，包含 LLM 模型和训练数据）的实验已初步验证了这一场景。

2. **CRC32C 线性组合思路可迁移**：这一将"计算问题降维为组合问题"的思路可迁移到 AI Infra 中的其他场景，例如分布式数据加载中的数据完整性校验、梯度 checksum 验证等。

3. **流式匹配协议的启发**：将 All-or-Nothing 交换转变为流式小批次处理的设计，与 AI 推理中的流式生成、分布式训练中的梯度流水线有异曲同工之处。这种"打破同步屏障、转为异步流"的设计模式值得在 AI 系统中更多借鉴。

4. **值得跟进的方向**：
   - 将 ParaSync 集成到分布式训练框架的 checkpoint 管理模块中，评估在真实训练场景下的端到端收益
   - 探索 GPU Direct Storage + ParaSync 的组合，利用 GPU 加速 hash 计算和数据传输
   - 研究模型权重的语义感知分块（而非纯内容定义分块），利用模型结构信息提高匹配率

---

## 八、总结

ParaSync 是一个针对 CDC 文件同步全流程进行细粒度并行优化的系统。其核心贡献是利用 CRC32C 的代数线性性质将 checksum 计算问题转化为 checksum 组合问题，实现分块阶段的近线性扩展；设计流式匹配协议打破客户端-服务器的 All-or-Nothing 依赖；引入绝对偏移量 patch 命令实现增量重建的流水线化。在 7 个真实数据集上，ParaSync 相比 dsync 实现 LAN 下 2.3×–3.7× 的端到端加速，且网络流量开销几乎不变。主要局限在于 WAN 场景下网络传输仍是主导瓶颈，计算优化收益有限；且核心设计依赖 CRC32C 的特殊代数性质，通用性受限。
