# Lockify: Understanding Linux Distributed Lock Management Overheads in Shared Storage

**作者**：Taeyoung Park, Yunjae Jo, Daegyu Han, Beomseok Nam, Jaehyun Hwang（Sungkyunkwan University）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/park
**源文件**：[[fast2026-park.pdf]]

---

## 一、背景

存储解耦（storage disaggregation）在云数据中心中日益普及，NVMe-over-Fabrics 等远程存储访问技术使得多个客户端可以通过 GFS2、OCFS2、VMFS 等 shared-disk 文件系统同时访问共享存储。这些文件系统依赖分布式锁管理器（Distributed Lock Manager, DLM）来协调跨客户端的锁操作。

DLM 通常用于锁竞争可控的场景，例如高可用系统中主备节点共享存储，正常运行时仅主节点需要锁。已有研究报告 76.1%–97.1% 的文件很少被多个客户端同时访问，因此 DLM 理论上不应成为瓶颈。

---

## 二、要解决的问题

尽管低竞争场景下 DLM 不应引入显著开销，但作者发现 Linux 内核 DLM 在文件/目录创建操作中存在严重的可扩展性问题：

1. **低竞争不等于高吞吐**：即使只有一个活跃客户端，随着集群中客户端数量增加（从 1 到 5），GFS2 上目录/文件创建吞吐量下降高达 86%，而普通文件 I/O 不受影响。

2. **DLM 通信延迟是瓶颈**：延迟分析显示，DLM 操作占总延迟的 47%，其中锁获取本身仅占 15%，主要开销来自与 directory node 和 owner node 的跨节点通信。

3. **问题跨 DLM 设计普遍存在**：无论是 Linux 内核 DLM 还是 O2CB（OCFS2 原生 DLM），都存在同样的性能退化趋势。O2CB 因缺少 directory node 设计，需与所有客户端通信来确定 owner，性能更差。

---

## 三、洞察与设计

**关键洞察**：当创建新文件或目录时，对应的锁对象尚不存在，因此不需要查询远程 directory node 来确定 owner——创建者可以直接声明自己为 owner。

基于这一洞察，Lockify 引入两个核心机制：

### Self-Owner Notification

创建新文件/目录时，节点直接声明自身为 owner，向 directory node 发送通知（而非查询），然后立即返回控制权给文件系统，无需等待确认。这消除了 DLM 的查询-响应往返延迟。

### Asynchronous Ownership Management

为保证一致性，Lockify 维护一个 wait-list 跟踪未确认的通知。Directory node 收到通知后更新 lock-owner table 并回复确认。若超时未收到确认（如节点/网络故障），Lockify 重发通知。确认收到后从 wait-list 中移除条目。

### Extended DLM Interface

Lockify 引入带 `NOTIFY` 标志的扩展锁获取接口 `dlm_lock(..., NOTIFY)`，文件系统通过此标志显式告知 DLM 当前请求是针对新创建的对象，应使用 self-owner 路径。对于已存在文件的操作，仍走标准 DLM 流程。

---

## 四、实现细节

- **实现位置**：Linux 内核 6.6.23，基于内核 DLM 模块
- **代码开源**：https://github.com/skku-syslab/lockify
- **修改范围**：DLM 核心模块（`dlm/`）、GFS2（`gfs2/`）和 OCFS2（`ocfs2/`）文件系统，以及相关内核头文件（`include/`）
- **Wait-list 数据结构**：每个锁请求创建一个条目，追踪是否已收到 directory node 的确认。设有重传定时器。
- **Crash Recovery**：扩展标准 DLM 恢复机制，在 crash 后检查 wait-list 并向新 directory node 重发未确认通知
- **Parent Directory Lock Contention**：创建子实体前必须持有父目录的排他锁。Lockify 在 ownership update 和文件操作并发执行期间保持父目录锁，不引入额外通信开销

---

## 五、实验结果

**测试环境**：5 台服务器，双路 Intel Xeon Gold 5115（20 核/socket），64 GB RAM，250 GB Samsung 970 EVO Plus NVMe SSD，56 Gbps 网络互联，Ubuntu 18.04（内核 6.6.23），NVMe-over-TCP 连接共享存储。

### Microbenchmarks（mdtest，35,000 文件/目录创建）

| 场景 | 指标 | GFS2+Lockify vs GFS2+DLM | OCFS2+Lockify vs OCFS2+DLM |
|------|------|--------------------------|----------------------------|
| 低竞争（5 client，1 活跃） | 目录创建 | ~6.4× | ~2.9× |
| 低竞争（1 client） | 目录创建 | 无提升（已是最优） | 无提升 |
| 高竞争（5 client 并发） | 目录创建 | 5.2× | 1.09× |
| 高竞争（5 client 并发） | 文件创建 | 5.4× | 1.11× |

### 延迟分析（低竞争，GFS2）

| 配置 | DLM 延迟占比 |
|------|-------------|
| 1 client | 4.4% |
| 5 clients + 内核 DLM | 46.7% |
| 5 clients + Lockify | 8% |

### Real-world Workloads（5 client，1 活跃）

| Workload | GFS2+Lockify vs GFS2+DLM | OCFS2+Lockify vs OCFS2+DLM |
|----------|--------------------------|----------------------------|
| Postmark | 2.0× | 1.7× |
| Filebench fileserver | 1.14× | 1.07× |
| Filebench webproxy | 2.5× | 1.08× |

### 与 RDMA-based DLM 对比

Lockify 在 TCP 环境下达到模拟 RDMA-based DLM 吞吐量的 87–88%。

### Crash 一致性

Xfstests 75 项测试中，GFS2 通过 70/75（与原始 DLM 一致），OCFS2 通过 67/75（同样一致）。

---

## 六、批判性分析

1. **实验规模偏小**：仅使用 5 个节点，而云数据中心集群通常远大于此。论文声称 5 节点"足以展示可扩展性问题"，但未验证 Lockify 在更大规模（如 50、100 节点）下的表现。5 节点下 hash 分配到远程 directory node 的概率为 80%，100 节点下为 99%，性能特征可能不同。

2. **OCFS2 上收益有限**：高竞争场景下 Lockify 对 OCFS2 仅有 1.09–1.11× 提升，因为 parent directory lock contention 是主要瓶颈而非 directory node lookup。论文对此轻描淡写，但实际部署中多客户端并发写同一目录是常见模式。

3. **RDMA 对比不够直接**：论文用单客户端零通信延迟来"模拟" RDMA-based DLM，但实际 RDMA DLM 在多客户端场景下仍需处理锁协调和一致性。这个对比过于理想化，可能高估了 Lockify 相对于真实 RDMA DLM 的竞争力。

4. **无网络负载下的评估**：所有实验在无背景网络流量的环境下进行。论文仅在最后简要提及 Lockify 在网络拥塞下可能更有优势，但缺乏实际数据支持。

5. **仅适用于创建操作**：Lockify 的优化仅针对文件/目录创建（新锁对象），对已有文件的读写操作无效。对于以读写为主的工作负载（如大多数数据库场景），Lockify 没有帮助。

6. **GFS2 的内部队列优化让对比不够公平**：高竞争实验中 GFS2+Lockify 能获得 5.2× 提升，部分原因是 GFS2 自身的重复锁请求合并优化减少了 parent directory lock 的通信次数。这一优势并非 Lockify 带来的，在不具备类似优化的文件系统上可能无法复现。

---

## 七、总结

Lockify 针对 shared-disk 文件系统中 DLM 在低竞争场景下仍存在高锁获取开销的问题，提出了 self-owner notification 和异步 ownership 管理两个简洁有效的优化。通过避免文件/目录创建时不必要的远程通信，Lockify 在 Linux 内核中实现并在 GFS2 和 OCFS2 上验证，最高可提升 6.4× 吞吐量，且不影响 crash 一致性。其局限在于仅优化创建操作、实验规模较小、且在高竞争场景下对部分文件系统收益有限。
