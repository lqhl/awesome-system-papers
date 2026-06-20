---
type: paper
name: GoFS
full_title: "Managing Scalable Direct Storage Accesses for GPUs with GoFS"
authors: [Shaobo Li, Yirui Eric Zhou, Yuqi Xue, Yuan Xu, Jian Huang]
venue: SOSP
year: 2025
tags: [gpu-storage, gpudirect-storage, filesystem, cuda, f2fs]
source_pdf: "[[3731569.3764857.pdf]]"
source_md: "[[3731569.3764857]]"
---

# Managing Scalable Direct Storage Accesses for GPUs with GoFS (SOSP 2025)

> **一句话总结**：GPU 端运行 F2FS-compatible 文件系统（POSIX API），control+data path 脱离 host CPU，多 SM 并发下比 GDS/cuFile 等平均 **1.61×**，保留 crash consistency 与 primary/secondary 协同。

## 问题与动机

[[GPUDirect Storage]] 允许 GPU 经 PCIe P2P 访问 SSD，但 cuFile/GPUfs 仍依赖 host [[F2FS]]/ext4 管 metadata，control path 成瓶颈。BaM 绕过 FS 让应用自管 raw disk，负担大。GeminiFS 预加载 metadata 假设 read-mostly 且 pattern 可预测，对 GNN/RAG 等多变写不适。

## 关键观察 / 隐含假设

- **观察 1**：GPU 上百 SM 并行访问 inode/dentry/bitmap 时，CPU FS 的 mutex+interval tree 模式严重争用，需 per-SM/per-warp 定制结构。
  - **依赖假设**：GPU warp reduction 等原语可加速 range check；batched inode(bnode) 可摊销 metadata op。
  - **可能失效场景**：极高文件数量随机小 IO，bnode 优势下降。
  - **证据强度**：强——1.61× 平均 + scaling 多 SSD。
- **观察 2**：GPU 应用偏 stream/batch，零拷贝 DMA 直写 user buffer 可省 page cache，且仍须 crash consistency。
  - **依赖假设**：primary(GPU daemon)/secondary(host FUSE client) 协同可维护一致性。
  - **可能失效场景**：host 与 GPU 同时活跃写同一文件，协调延迟。
  - **证据强度**：中——primary/secondary 模式合理，冲突频率未量化。
- **假设 1**：on-disk layout 兼容 F2FS 使 host/GPU 可共享盘。
  - **证据强度**：强——明确基于 F2FS 实现。

## 核心方法

**GoFS**：GPU-orchestrated FS。

- Metadata：GPU range lock、per-SM bitmap、bnode、level-synchronous data pointer 遍历
- Data I/O：多 NVMe queue in GPU memory、zero-copy DMA、CUDA dynamic parallelism 扩 I/O 线程
- Consistency：GoFS daemon(primary) + host FUSE client(secondary)
- Security：host 签发 process signature，daemon 校验

7.9K LOC CUDA daemon + 0.8K host client。

## 设计取舍

- **取舍 1**：GPU 内存放 metadata 结构，受 VRAM 限制，靠 on-demand 拉盘 metadata。
- **取舍 2**：F2FS 绑定，换兼容性；非通用 VFS for all GPU FS research。
- **边界条件**：GDS 硬件可用；batch/stream GPU analytics workload。

## 实验与结果

- A100 + Samsung 990 Pro：**1.61×** avg vs SOTA GDS 方案
- Workload：graph analytics、DL query、GNN、LLM RAG
- 多 SSD scaling 良好
- Crash consistency 保留

## Critical Analysis

### 论证链条

「host metadata bottleneck → full GPU FS」逻辑直接，optimization 与 GPU 编程模型对齐（SM、warp、dynamic parallelism）。

### 假设压力测试

- VRAM 紧张时 metadata cache 行为？与 GeminiFS 在 read-heavy 谁赢需场景细分。
- Primary/secondary 切换失败模式（daemon crash）恢复流程？
- 非 F2FS 文件系统共存迁移成本。

### 实验可信度

多 application 类型好。Baseline 含 cuFile、GPUfs、BaM 等。单 A100 单机，多 GPU 多盘生产拓扑未测。

### 系统性缺陷

论文未讨论：GPU FS bug 导致数据损坏的 recovery；多 tenant 签名伪造面；与 CXL-SSD 统一内存路径关系。

## 局限与 Future Work

- **局限 1**：F2FS 专用，VRAM 约束。
- **局限 2**：host/GPU 并发写协调开销未充分量化。
- **Future work 1**：metadata 分层放 host DRAM + GPU cache 的 hybrid，按 access pattern 自适应。

## 相关

- **相关概念**：GPUDirect Storage、GPU file system、[[F2FS]]、zero-copy I/O
- **同类系统**：cuFile、BaM、GeminiFS、GPUfs
- **同会议**：[[SOSP-2025]]