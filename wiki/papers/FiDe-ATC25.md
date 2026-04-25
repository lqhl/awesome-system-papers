---
type: paper
name: FiDe
full_title: "FiDe: Reliable and Fast Crash Failure Detection to Boost Datacenter Coordination"
authors: [Davide Rovelli, Pavel Chuprikov, Philipp Berdesinski, Ali Pahlevan, Patrick Jahnke, Patrick Eugster]
venue: ATC
year: 2025
tags: [failure-detection, distributed-systems, consensus, datacenter, sdn]
source_pdf: "[[atc2025-rovelli.pdf]]"
source_md: "[[atc2025-rovelli]]"
---

# FiDe: Reliable and Fast Crash Failure Detection to Boost Datacenter Coordination (ATC 2025)

> **一句话总结**：system-driven crash failure detector，用 OS 隔离 + XDP + SDN 流量工程的双冗余 multicast tree 把 crash detection 压到 < 30µs（比 SOTA uKharon-FD 快 7.2×、平均 4.58µs），并在其上设计 N-1 容错的新 consensus，使 Redis/Zookeeper 吞吐 +1.7×–2.23×、延迟最低 0.46×。

## 问题

datacenter failure detector 的核心矛盾：timeout 太短假阳性、太长拖慢 µs-级服务恢复。多层级 / gray failure detector（Falcon、uKharon、Panorama）覆盖广但要"监视监视者"、需要 application-specific 探针，反而引入处理 jitter，常靠主动 kill 来兜底假阳性。RDMA-based 的 uKharon-FD 也会偶发 latency 突刺（70 亿 packet 后冲到 243µs），表明仅靠 kernel-bypass 不足。

## 核心方法

FiDe 把整个 detection 分成两个 domain：best-effort domain（应用）+ FiDe domain（特权系统底座），externally observed：

- **Reactive uninterrupted processing**：FiDe 进程钉到独立 CPU core（isolcpus + 屏蔽 IRQ + C0 power state + hugepage），LKM 用 active pacemaker loop 直接发心跳绕过网络栈；接收端用 XDP hook 直接拦包、专用 NIC queue + IRQ。
- **Fast-track redundant networking**：SDN controller 给每个 FiDe cluster 分配两棵 vertex-disjoint 的有向 multicast tree，配合优先级队列 + 端到端 rate-limit 做流量工程，给定 (i, J, σ_max, π_min) 后保证 latency/jitter 上界；任一树出问题就 recovery 切到另一棵。
- **OS watchdog**：LKM 在 do_exit 上用 kprobe pre-handler，进程"官宣退出"瞬间就被检测到（technically negative latency）。
- **FiDe-based consensus**：把 FiDe 当作 perfect failure detector P 的实践近似，提出
  - OSRB (Optimistic Stabilizing Reliable Broadcast) 带 STABILIZE 限制 buffer 增长
  - HSUC (Hierarchical Stabilizing UC) — 3 message delays，N-1 crash 容错
  - HUC (Heartbeat UC) — 利用 FiDe 心跳 piggyback 把 leader decision 直接捎带，2 message delays、N-1 crash 容错
- 用 TLA+/TLC 形式化验证。

## 关键结果

- 2.3 万亿 packet 跨数周测试：peer-to-peer latency 上界 < 45µs，比 X-Lane / RDMA / Falcon 稳定 5.4× 以上
- 平均 crash detection 4.58µs / 最大 26.54µs（vs uKharon-FD 17.39 / 193.56µs，X-Lane 354.75 / 718.54µs）
- timeout 可设到 48µs（uKharon-FD/X-Lane 要 ~800µs 才零假阳）
- Redis SET：HUC 比 RedisRaft 吞吐平均 1.22×、最高 1.7×；延迟最低 0.46×
- Zookeeper SET：HUC 比 Zab 吞吐平均 1.71×、最高 2.23×；延迟最低 0.57×
- critical compound failure 估计 22.7 年/次，比 Ethernet+TCP 报文损坏概率高 3 个数量级可靠
- 代码：FiDe 4032 LoC C，HSUC 910 / HUC 810 LoC

## 相关

- **相关概念**：[[Failure-Detector]]、[[Consensus]]、[[XDP]]、[[SDN]]、[[Heartbeat]]、[[Traffic-Engineering]]
- **同类系统**：Falcon、uKharon、X-Lane、Panorama、Raft、Zab
- **同会议**：[[ATC-2025]]
