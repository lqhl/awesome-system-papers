---
type: paper
name: Lockify
full_title: "Lockify: Understanding Linux Distributed Lock Management Overheads in Shared Storage"
authors: [Taeyoung Park, Yunjae Jo, Daegyu Han, Beomseok Nam, Jaehyun Hwang]
venue: FAST
year: 2026
tags: [distributed-lock, dlm, shared-disk, gfs2, ocfs2, nvme-of]
source_pdf: "[[fast2026-park.pdf]]"
source_md: "[[fast2026-park]]"
---

# Lockify: Understanding Linux Distributed Lock Management Overheads in Shared Storage (FAST 2026)

> **一句话总结**：观察到 Linux 内核 DLM 在文件/目录创建时即使低争用也因远程 directory node 通信而严重退化（5 客户端比 1 客户端慢 86%），Lockify 用 self-owner notification + asynchronous ownership management 把 DLM 延迟从总延迟的 47% 降到 8%，整体吞吐提升 **\~6.4×**，逼近 RDMA 方案的 87-88%。

## 问题

shared-disk 文件系统（[[GFS2]]、[[OCFS2]]、VMFS）在 NVMe-over-Fabrics 这类存储 disaggregation 场景下越来越重要，依赖 [[DLM]] 协调多客户端锁。生产中 76.1-97.1% 文件实际不被多客户端共享，大家以为低争用就没事——但作者实测发现 **即便只有一个客户端做创建工作，文件/目录创建吞吐随客户端数增加掉 86%**。原因：DLM 创建新 lock object 时要先 hash 找 directory node、远程查 owner、再向 owner 请求，跨节点通信成主导（占创建延迟的 47%，而 lock acquisition 本身仅 15%）。OCFS2 的 O2CB 因无 directory node 反而要广播给所有客户端，更慢。

## 核心方法

关键观察：创建新文件时还没有 owner，directory node 一定会把请求方设为 owner——既然如此何必去问？

- **Self-Owner Notification**：发起 create 的节点直接 declare 自己是 owner，立即拿到锁、立即返回；同时异步通知 directory node 更新 lock-owner table。
- **Extended Lock Acquisition Interface**：`dlm_lock(..., NOTIFY)` 让 FS 显式标注「这是新建对象」，对已存在对象仍走标准查 owner 路径，对 FS 改动最小。
- **Asynchronous Ownership Management**：维护 wait-list 跟踪未确认的 notification，超时则重发；crash recovery 时把未确认 notification 重发到新 directory node；保持父目录锁直到 ownership 与 file op 都完成以处理并发 create 同名冲突。

实现：基于 Linux 6.6.23 内核 DLM 改造，对 GFS2/OCFS2 极小修改。

## 关键结果

- 低争用 mdtest（5 客户端、1 active）：GFS2 throughput **+6.4×**，OCFS2 +2.9×，几乎追平 1-客户端理想值
- DLM 延迟在 5 客户端 GFS2 下从 46.7% 降到 8%（接近 1-客户端基准的 4.4%）
- Postmark 真实负载：GFS2 +2.0×、OCFS2 +1.7×
- Filebench webproxy：GFS2 +2.5×
- Crash consistency 通过 75 个 xfstests 通用用例（与原 DLM 同），证明改动不破坏一致性
- 对比 emulated DLM-over-RDMA：达 87-88% 性能，纯 TCP 即可逼近 RDMA 方案

## 相关

- **相关概念**：[[DLM]]、[[Distributed-Lock]]、[[Shared-Disk-FS]]、[[NVMe-over-Fabrics]]
- **同类系统**：[[GFS2]]、[[OCFS2]]、[[Lustre]]、[[CXFS]]、[[Citron]]（RDMA range lock）
- **同会议**：[[FAST-2026]]
