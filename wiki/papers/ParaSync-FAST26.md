---
type: paper
name: ParaSync
full_title: "ParaSync: Exploiting Fine-Grained Parallelism for Efficient File Synchronization"
authors: [Zhihao Zhang, Lu Tang, Huiba Li, Yue Yu, Guangtao Xue, et al.]
venue: FAST
year: 2026
tags: [file-sync, content-defined-chunking, parallelism, delta-sync, checksum]
source_pdf: "[[fast2026-zhang-zhihao-parasync.pdf]]"
source_md: "[[fast2026-zhang-zhihao-parasync]]"
---

# ParaSync: Exploiting Fine-Grained Parallelism for Efficient File Synchronization (FAST 2026)

> **一句话总结**：CDC-based 文件同步的三阶段（chunking / matching / reconstruction）受制于「checksum 须在 boundary 定型后算」「all-or-nothing checksum exchange」「relative-offset patch 序列依赖」三道阻塞；ParaSync 用「checksum 组合代替 checksum 重算 + streaming matching + absolute-offset 流水化 patch」解开依赖，chunking 加速 **7.6×**，端到端 sync **3.7×**，网络流量持平。

## 问题

CDC-based 文件同步（[[dsync]]、NetSync）相对 FSC-based 的 [[rsync]] 减少了 boundary-shift 引起的网络流量，但其三阶段在现代多核硬件上跑不出多核扩展性：

- **Phase I — Chunking 是主瓶颈**：rolling hash + CRC32C 占总同步时间 49.5–75.1%。SS-CDC 等并行 CDC 把 boundary 搜索并行化，但 checksum 计算被推到一个串行第二阶段（boundary 定下来才能算 checksum），AVX scatter/gather 又被非连续访问拖累，8 核仅小幅提速。
- **Phase II — Matching 卡在 All-or-Nothing Checksum Exchange**：客户端必须等服务端处理完整个文件、把所有 strong checksum 一次性回传后才能开始本地 strong checksum 校验，网络与计算无法 overlap。
- **Phase III — Reconstruction 卡在 Relative-Offset 依赖**：patch 命令用相对位移（"接前一块之后"），patch N 应用前必须等 patch N-1 写完，无法并行 apply 也无法 overlap network/disk I/O。

[[rsync]] 的 pipeline 模型反方向流动数据流（server 先发 checksum），不能直接套到 dsync 的 client-server-client 数据流上。

## 核心方法

**Parallel Chunking（§3.1）**：把 checksum 计算问题归约为 checksum **组合**问题。Stage 1 多线程在等大 segment 上独立 rolling-hash，每命中一个 boundary 就把 sub-chunk 的 metadata（offset 8B + CRC32C 4B）写入 thread-local FIFO。Stage 2 单线程合并相邻 sub-chunk 形成最终 chunk，关键是利用 [[CRC32C]] 的线性性质：$\text{CRC}(C_1) = \text{CRC}(SC_1') \oplus \text{CRC}(SC_2)$（$SC_1'$ 在 $SC_1$ 后追加 $|SC_2|$ 个零字节）。merge 阶段只处理小元数据，不再读文件本身——彻底消除 SS-CDC 的串行瓶颈。

**Streaming Matching（§3.2）**：服务端 wmatcher 不静态分配 checksum 给线程（数据严重倾斜，单 CRC 可对应 12 万 chunk），改用动态 work-stealing 队列把同 CRC 的 chunk 切段给多线程。每个线程算完一段就**立刻**把 matching token 小批量发给客户端，客户端收到批次就启动 strong-checksum 校验（构建该批次的小 strong hash sub-table），把 server wmatcher / 网络传输 / client smatcher 三者 overlap 起来。

**Pipelined Delta Reconstruction（§3.3）**：patch 命令改用**绝对偏移**（相对老文件 `f` 和新文件 `f'` 的位置），任何 patch 可独立 apply。配合协程驱动的 I/O，让 dtransmitter（生成）/网络（传输）/patcher（写盘）三段流水线满拉，computation/network/disk 三种 latency 全部 overlap 而非堆叠。

## 关键结果

- File chunking 加速最高 **7.6×**（相比 dsync 单线程及 SS-CDC 并行版本）。
- 端到端 sync 加速最高 **3.7×**（在 WAN 与 LAN 多个真实数据集）。
- 网络流量保持一致——并行化不破坏 chunk invariability，未引入额外 literal byte。
- 完整覆盖三类 intra-phase parallelism + inter-phase pipelining；既有方法（rsync / dsync / pdsync）至少有一项 Inefficient 或 Not Supported。

## 相关

- **相关概念**：[[Content-Defined-Chunking]]、[[CRC32C]]、[[Rolling-Hash]]、[[Delta-Sync]]、[[Pipeline-Parallelism]]
- **同类系统**：[[rsync]]、[[dsync]]、SS-CDC、NetSync、[[SkySync-FAST26|SkySync]]（同作者另一篇）
- **同会议**：[[FAST-2026]]
