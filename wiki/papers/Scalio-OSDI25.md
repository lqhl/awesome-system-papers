---
type: paper
name: Scalio
full_title: "Scalio: Scaling up DPU-based JBOF Key-value Store with NVMe-oF Target Offload"
authors: [Xun Sun, Mingxing Zhang, Yingdi Shan, Kang Chen, Jinlei Jiang, Yongwei Wu]
venue: OSDI
year: 2025
tags: [storage, dpu, jbof, key-value-store, rdma, nvme-of]
source_pdf: "[[osdi25-sun.pdf]]"
source_md: "[[osdi25-sun]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Scalio: Scaling up DPU-based JBOF Key-value Store with NVMe-oF Target Offload (OSDI 2025)

> **一句话总结**：DPU JBOF 上 LEED 在 4 块 SSD 后吞吐饱和、网络 IOPS 利用率 <1%，Scalio 用 NVMe-oF Target Offload + 客户端单边 [[RDMA]] 热读缓存 + group commit 写缓冲，配合 occupied/complete 一致性协议保证 linearizability，7 SSD 配置下比 LEED 高 2.5–17×、比 LEED+Ditto 高 1.8–3.3×。

## 问题与动机

高密度 DPU-based JBOF（单 DPU 挂多块 NVMe）是能效友好的存储形态，但现有 JBOF KV（如 LEED）在 small KV workload 下随 SSD 数量增加无法线性扩展：LEED 在 4 SSD 时 DPU CPU 已饱和（SSD I/O 核占用 ~400%），吞吐不再增长，而 Mellanox ConnectX-6 网络 IOPS 能力 200M、实测仅 ~600K（<1% 利用率）。瓶颈在弱 ARM 核处理 SSD I/O，而非 SSD 或网络本身。

## 关键观察 / 隐含假设

- **观察 1**：NVMe-oF Target Offload 可把 target 端 SSD 读路径 CPU 占用降到 0，且 IOPS 与标准 NVMe-oF 相当。
  - **依赖假设**：部署环境有支持 Target Offload 的 HCA（如 ConnectX-6 类），且客户端能发 NVMe-oF 命令直达 SSD。
  - **可能失效场景**：无 offload 硬件时回退标准路径，CPU 瓶颈依旧；非 small-KV workload 下网络带宽可能先饱和。
- **观察 2**：小 KV 场景下 [[RDMA]] read/write IOPS 远高于 CAS（约 10×），应把索引维护尽量卸载到客户端单边操作，少用 CAS。
  - **依赖假设**：workload 以 100B 级小 KV 为主（YCSB 类），hash block 可放大到 ~1KB 仍不压满网络。
  - **可能失效场景**：大 value 或极高写比例时，DPU CPU 的 group commit 与 ring buffer 仍可能成为瓶颈。
- **假设 1**：disaggregated 架构下 DPU DRAM 与 SSD 无硬件 cache coherence，必须显式协议而非依赖 CPU 式一致性。
  - **证据强度**：强——论文用 linearizability 反例（write-cache-first / write-SSD-first）证明 naive 协议不成立。

## 核心方法

**读路径**：客户端 [[RDMA]] read hash block（~1KB，多 slot 内联 KV）；hit 则直接返回；miss 则 NVMe-oF Target Offload 直读 SSD，再 RDMA write 回填 victim slot，用 occupied/complete + double-read 锁定。

**写路径**：客户端 RDMA append 到 DPU ring buffer；DPU CPU 批量刷 SSD 并更新 next_offset，group commit 后通知客户端；客户端 RDMA 失效过时 cache entry。

**一致性**：RDMA 驱动的缓存一致性协议，在 disaggregated 多客户端场景保证 linearizability，刻意限制重 CAS 使用。

## 设计取舍

- **取舍 1**：把读索引与部分 cache 维护卸载到客户端，换取 DPU CPU 可扩展性，但增加客户端复杂度与一致性协议负担。
- **取舍 2**：写路径仍依赖 DPU CPU polling + batch flush，写密集时 CPU 仍可能是次瓶颈。
- **边界条件**：7 SSD 以内 YCSB A/B/C/D/F 表现稳健；更高密度、非均匀 key 分布与故障恢复路径论文覆盖有限。

## 实验与结果

- YCSB，1–7 SSD：相对 LEED **2.5–17×** 吞吐；相对 LEED + Ditto 内存缓存 **1.8–3.3×**。
- NVMe-oF Target Offload：target CPU 0% vs 标准实现 562%（fio 微基准）。
- LEED 网络 I/O 利用率 <1%；Scalio 更好利用 HCA IOPS 余量。
- 参数敏感性（block size 等）在 §6.5 中表现稳健。

## Critical Analysis

### 论证链条

观察（CPU 瓶颈 + 网络闲置 + offload 零 CPU）→ 卸载读与 SSD 直达 → YCSB 吞吐随 SSD 数扩展，链条在 small KV + JBOF 设定下闭合。linearizability 论证依赖 occupied/complete 协议，实验以功能/性能为主，形式化验证范围论文未展开。

### 假设压力测试

大 value、扫描型读、多租户强隔离场景下客户端参与一致性是否仍可维护？Target Offload 与多种 SSD/HCA 组合的兼容性论文主要在单一 testbed。生产级故障恢复（DPU 崩溃 mid-batch）依赖 group commit 到 SSD 的持久化边界，需对照实现细节。

### 实验可信度

Baseline LEED 与 LEED+Ditto 合理；YCSB 代表 cloud small-op 但非全场景。7 SSD 上限可能低于商用 26/36 SSD JBOF 机箱，外推需谨慎。

### 系统性缺陷

客户端需实现 NVMe-oF + [[RDMA]] 一致性逻辑，运维与升级复杂；论文未讨论 tail latency SLO、多租户公平性、可观测性指标。

## 局限与 Future Work

- **局限 1**：写密集 workload 下 DPU CPU 与 group commit 延迟仍可能限制扩展。
- **局限 2**：实验规模与硬件代际固定，超高密度 JBOF 未充分验证。
- **Future work 1**：在 20+ SSD 商用 JBOF 上测量 CPU/网络/SSD 三瓶颈转移点。
- **Future work 2**：故障注入下 linearizability 与恢复时间的系统化测试。

## 相关

- **相关概念**：[[RDMA]]
- **同类系统**：LEED、Ditto（论文 baseline，无 wiki 页）
- **同会议**：[[OSDI-2025]]
