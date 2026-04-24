---
type: paper
name: FineMem
full_title: "FineMem: Breaking the Allocation Overhead vs. Memory Waste Dilemma in Fine-Grained Disaggregated Memory Management"
authors: [Xiaoyang Wang, Yongkun Li, Kan Wu, Wenzhe Zhu, Yuqi Li, Yinlong Xu]
venue: OSDI
year: 2025
tags: [disaggregated-memory, rdma, memory-management, allocation]
source_pdf: "[[osdi25-wang-xiaoyang.pdf]]"
source_md: "[[osdi25-wang-xiaoyang]]"
---

# FineMem: Breaking the Allocation Overhead vs. Memory Waste Dilemma in Fine-Grained Disaggregated Memory Management (OSDI 2025)

> **一句话总结**：用 RDMA Memory Window + 两层 bitmap tree + per-compute-node 分配服务，在 disaggregated memory 里实现 4KB 粒度的单边 RDMA 分配，延迟比 SOTA 降 95%，内存利用率提升 2.25-2.8×。

## 问题

RDMA-based disaggregated memory 系统面临两难：MR (Memory Region) 注册非常昂贵——4MB 注册要 480 µs，所以实际系统要么预注册整块内存，要么按 1GB 粗粒度从远端 pool 抓。粗粒度分配摊平开销但造成严重浪费：大块中未用部分无法在多 DM 系统间回收共享。

已有单边 RDMA 方案（如 CXL-SHM）虽避免了 memory node CPU 瓶颈，但用 uncompacted chunk array 要 per-chunk round-trip，用 compact bitmap 又会在多 client 并发时频繁 CAS 重试；都缺乏 isolation（单 rkey 覆盖全 MR，任何拿到 rkey 的 client 都能乱访问别人的 chunk 和元数据）。

## 核心方法

**消除 MR 注册开销 + 提供隔离**：memory node 启动时把整块远程内存预注册为一个 MR；然后用 RDMA Memory Window (MW) 给每个 chunk 绑定独立 rkey（MW 可以每微秒生成/失效一个），分配时只需单边操作 acquire/invalidate rkey，注册开销移出关键路径。元数据保护靠每个 compute node 上运行的 trusted allocation service（inspired by 软件虚拟化），DM 应用通过 IPC 调它，只有 service 持有元数据的 rkey。

**两层 bitmap tree 加速并发分配**：section 层（32-bit bitmap，16 spans，每 span 128KB）+ span 层（32-bit free map，32 chunks，每 chunk 4KB）。大于 128KB 的分配一次 CAS 改 section bitmap；小于 128KB 进入 span 层。section header 用 2 bit per span 编码「空/满/in-use/contended」状态；allocator 检测到某 span 上 CAS 失败次数超阈值就标为 contended，后续分配选 normal > empty > contended，用 back-pressure 避免 CAS 重试风暴。compute node 上缓存 section/span 元数据（64 个 section = 512B）进一步减少 round-trip。

**crash consistency**：在 64-bit bitmap 里嵌入 compact 临时 log（user ID + timestamp），记录每次成功分配的 commit point；任意线程都能把临时 log flush 成 full log；timestamp 用来防止 fail-slow 场景下过期 log 覆盖新 log。

## 关键结果

- 远端内存分配延迟相比 SOTA（CXL-SHM 等）减少最多 95%
- 内存利用率提升 2.25× 到 2.8×（相比粗粒度 1GB 分配）
- 额外 overhead 仅 2.5% - 4.1%
- 兼容 jemalloc / mimalloc / FastSwap / FUSEE (KV store) 等系统，改用 FineMem 的 malloc/free API
- 开源：https://github.com/ADSLMemoryDisaggregation/FineMem

## 相关

- **相关概念**：[[RDMA]]、[[Disaggregation]]
- **同会议**：[[OSDI-2025]]
