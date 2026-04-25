---
type: paper
name: GoFS
full_title: "Managing Scalable Direct Storage Accesses for GPUs with GoFS"
authors: [Shaobo Li, Yirui Eric Zhou, Yuqi Xue, Yuan Xu, Jian Huang]
venue: SOSP
year: 2025
tags: [gpu, file-system, nvme, gpudirect-storage, storage]
source_pdf: "[[3731569.3764857.pdf]]"
source_md: "[[3731569.3764857]]"
---

# Managing Scalable Direct Storage Accesses for GPUs with GoFS (SOSP 2025)

> **一句话总结**:把整套文件系统 offload 到 GPU(POSIX API、inode/dentry/块位图/NVMe queue 全在 GPU 内存),绕开 host CPU 对 GPUDirect Storage 的瓶颈,平均吞吐 1.61× 优于 state-of-the-art,F2FS 兼容。

## 问题

GPU 加速数据处理中,存储 I/O 耗时占比很大。NVIDIA GPUDirect Storage (GDS) 允许 GPU 经 [[PCIe]] P2P 直接从 [[NVMe]] SSD 取数,但主流方案(cuFile、GPUfs)仍让 host FS 管元数据 → host CPU 成瓶颈。BaM 让 GPU 直访裸 block 设备,但把 FS 丢给应用开发者。GeminiFS 把元数据 preload 到 GPU,只适合可预测 + read-only workload。真实 GNN、LLM RAG、图计算有不可预测 I/O 和写入。

## 核心方法

- **GPU-orchestrated FS**:GoFS daemon 跑在 GPU,持有 in-memory 元数据、直接发 NVMe 命令,控制面+数据面都不过 host CPU;host 侧有 FUSE-based client 在 primary/secondary 模式下协同,保持与 F2FS 的 on-disk 格式兼容。
- **Scalable 元数据**:
  - 自定义 GPU range lock(用 warp-level reduction 替代 interval tree,把 range check 从 O(log n) 降到近 O(1))。
  - Batched inode (bnode) 把同目录多文件元数据聚合,摊薄对上千 GPU core 的 metadata cost。
  - Per-SM block bitmap + thread-block 合并分配,消除 per-core 结构。
  - Tree 数据指针用 level-synchronous parallel 遍历,metadata/data 两阶段。
- **Scalable 数据 I/O**:多个 NVMe queue 映射到 GPU 内存,zero-copy DMA 到用户 buffer,基于 CUDA dynamic parallelism 按 I/O 大小自动扩 I/O 线程。
- **Consistency**:基于 log-structured F2FS,保留 crash consistency;host/GPU 共享 SSD 时主次模式同步。
- **Protection**:GPU 虚拟内存隔离 FS daemon 与 app;cryptographic signature 做文件访问控制。

## 关键结果

- 多种 GPU workload(graph analytics、vision/text/audio DL query、GNN、LLM RAG)上平均 1.61× 优于 cuFile、BaM、GeminiFS。
- 随 SSD 数量良好线性扩展。
- 实现:daemon 5.5K LOC CUDA + host client 0.8K LOC C/C++(FUSE)。A100 + 16-core Xeon + 多 Samsung 990 Pro。

## 相关

- **相关概念**:[[NVMe]]、[[PCIe]]、GPUDirect Storage、F2FS、log-structured FS
- **同类系统**:cuFile、GPUfs、BaM、GeminiFS
- **同会议**:[[SOSP-2025]]
