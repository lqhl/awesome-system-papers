---
type: paper
name: RCuckoo
full_title: "Cuckoo for Clients: Disaggregated Cuckoo Hashing"
authors: [Stewart Grant, Alex C. Snoeren]
venue: ATC
year: 2025
tags: [rdma, disaggregated-memory, key-value-store, cuckoo-hashing, locking]
source_pdf: "[[atc2025-grant.pdf]]"
source_md: "[[atc2025-grant]]"
---

# Cuckoo for Clients: Disaggregated Cuckoo Hashing (ATC 2025)

> **一句话总结**：基于纯单向 [[RDMA]] 的全 disaggregated cuckoo 哈希 KV store，small-value 读 1 跳、写/删 2 跳、median insert 2 跳；YCSB-A（写密集）下吞吐相比现有系统最多 7.1×。

## 问题

Disaggregated memory 需要 KV 接口提供共享访问，但现有 RDMA KV：(a) 依赖 server-side CPU 处理两边 RDMA（FaRM 类），打破 disaggregation；(b) 用 lock-free 乐观协议+8B 索引指向 extent（FUSEE）——读小值要 2 跳，写密集场景慢。RDMA atomic 在 ConnectX-5 上 contended 时仅 3 MOPS，传统认知是 lock-based RDMA KV 不可行。

## 核心方法

RCuckoo 用 lock-based cuckoo hashing 全部跑在 client 上，passive memory server 只暴露内存。三个关键设计：

1. **Locality-enhanced dependent hashing**：传统 cuckoo 两个位置独立随机，破坏 locality。RCuckoo 把第二位置 offset 取 `h2(K) mod ⌊f^(f+Z(h3(K)))⌋`，参数 `f=2.3`，让 68% 的 key 两个位置在 5 行内；既保住 95%+ max fill，又让 99% cuckoo path 跨度 < 256 行——绝大多数 insert 一次 MCAS 锁全部行。
2. **NIC-memory bit-vector lock table**：1-bit 锁存在 ConnectX-5 的 256KB device memory 里（contended atomic 比 host memory 快 3×）；用 RDMA masked CAS 一次拿/放最多 64 把锁。表大于 64M 行时用 virtual lock（多 logical → 1 physical）。
3. **Lease-based fault recovery**：client 失败时 repair lease 给定独占区域，把 cuckoo path 中间状态归类成 4 种并按确定顺序修复 CRC + 去重。

Inline value（默认）让小值读单跳完成；CRC + version number 让 lock-free 读侦测 torn write。

## 关键结果

- 320 clients 下 YCSB-B（95%R/5%W）吞吐 2.5× FUSEE/Sherman；YCSB-A（50/50）7.1× over Sherman / 与 FUSEE 持平但能 scale 更高。
- Insert I/O amplification 在 90% fill 下 < 2×，median 仍 2 round trip。
- 失败注入：每秒 100s 客户端失败下吞吐保持稳定。
- 锁 granularity sweet spot：每锁 2–16 行；用 16 行/锁 + dependent hashing，绝大多数 insert 1 个 MCAS 拿全锁。

## 相关

- **相关概念**：[[RDMA]]、cuckoo-hashing、disaggregated-memory
- **同类系统**：FUSEE、Clover、Sherman、FaRM
- **同会议**：[[ATC-2025]]
