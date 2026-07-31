---
type: paper
name: Helmsman
full_title: "The Clustering Strikes Back: Building Cost-Effective and High-Performance ANNS at Scale with Helmsman (Operational Systems)"
authors: [Yuchen Huang, Baiteng Ma, Yiping Sun, Yang Shi, Xiao Chen, et al.]
venue: OSDI
year: 2026
tags: [anns, vector-search, nvme, clustering, production-system]
source_pdf: "[[osdi26-huang-yuchen.pdf]]"
source_md: "[[osdi26-huang-yuchen]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# All-Flash Clustering ANNS 的生产化反击（OSDI 2026）

> **原题**：The Clustering Strikes Back: Building Cost-Effective and High-Performance ANNS at Scale with Helmsman (Operational Systems)

> **一句话总结**：RedNote 的大 top-k workload 让 SSD graph traversal 因串行 IO 失去优势；Helmsman 以 SPDK userspace stack、top-k/query-aware 分级 learned pruning 和 GPU+elastic CPU 建索引，在 SLA 内达到 hybrid baseline 的 2–16×、DRAM HNSW 的 47%–85% throughput，并用 40 台机替代约 35,000 cores/0.35 PB DRAM，硬件成本降 90%以上。

## 问题与动机

RedNote 搜索、推荐、广告管理数百 billion embedding、数百万 QPS，并要求平均 5–10 ms；为 latency 使用 in-DRAM HNSW，已达 PB DRAM。Gen5 SSD 单价约 DRAM 的 1/40、阵列 bandwidth 约 30%，但 DiskANN/Starling/PipeANN 的 greedy graph walk 对大 top-k 需 1500–4000 candidate/hop，serialized IO 不能吃满带宽。

clustering ANNS 可一次 batch 读多个独立 cluster list，更适合 SSD array；现有 SPANN 又受 kernel I/O stack、固定 pruning 和单 CPU build 限制。生产还要求 top-k 10–3000、频繁 model/index rebuild，故 serving 与 construction 必须一起解决。

## 关键观察 / 隐含假设

- **观察 1**：在 production large top-k 下，graph search 的依赖链/SSD latency 比 IO 数更重要；clustering 的 dependency-free batch IO 可利用现代高 bandwidth array（§3、图 4–5）。
  - **依赖假设**：每 query 可接受读多个 cluster，DRAM 存 centroid/metadata，SSD bandwidth 充足。
  - **可能失效场景**：top-k 极小、SSD 数少、graph cache hit 高或 strict ultra-low tail。
- **观察 2**：固定 nprobe 对 top-k/query distribution 过扫；逐 cluster decide 虽自适应，却串行化 IO（§4.3）。
  - **依赖假设**：近期约 1% log sample、近似 large-nprobe label 可代表未来 query/recall。
  - **可能失效场景**：distribution drift、新 embedding model、rare query 被 duplication-heavy sample 淹没。
- **观察 3**：coarse k-means 占 build 60%–80%且适合 GPU；小 fine split 适合 local CPU，大数据再弹性扩到 10³–10⁴ cores（§4.4）。
  - **依赖假设**：有可抢占 idle CPU pool，online QoS 优先，失败/retry 不支配 tail。
- **假设 1**：约 90% recall 和大 top-k 对 downstream rerank 比小 top-k 的 99%+ recall 更有业务价值。
  - **证据强度**：production experience 强，但公开 benchmark 的 end-to-end quality 未证明。

## 核心方法

ANNS-oriented storage backend 基于 SPDK bypass syscall/kernel，直接把 fixed-size cluster-list read 成批提交 [[NVMe|NVMe]] hardware queue，每 batch 只敲一次 [[PCIe|PCIe]] doorbell，并用 polling completion；内存与 thread/device partition 贴合 search pipeline，减少 libaio 可占至 58%的 software overhead。

leveling-learned pruning 先按 nprobe 上限划 level。router 以 query、top-k 等特征选择最小能达到 recall 的 level；level 内模型预测实际 nprobe。训练从近期 trace 抽约 1%，以 nprobe 4096 search 近似 ground truth，避免 per-cluster online decision，最终仍一次 batch 发出所有 IO。

construction 先用 L20 GPU 做 coarse clustering；小于约 0.1B 的 fine split/duplication 留本机 CPU，大到 10B 则切 task 分发 elastic CPU pool。online task 可抢占 build；重试超阈值后 task reassign、坏 node eviction，避免 straggler 支配总 build。

## 设计取舍

- **cluster scan 换 bandwidth parallelism**：比 graph 多读数据，但减少 dependency depth；适合多 SSD/大 top-k。
- **learned pruning 换 drift risk**：少冗余 read且保持 batch，需 trace、label、recall monitor与 retrain。
- **SPDK 换资源独占/工程复杂度**：高 IOPS，需 polling core、device ownership、custom failure handling。
- **periodic rebuild 换 update simplicity**：10B 数小时可行，但实时 insert/delete 仍靠 auxiliary HNSW+tombstone。

## 实验与结果

- public SIFT 与 5 个 production dataset（4M–10B），top-k 10–3000/production trace；96-core EPYC、12×1.92 TB Gen5 NVMe、12×96 GB DRAM，对比 DiskANN/Starling/PipeANN/SPANN/HNSW（§5.1）。
- 相对 DRAM-SSD baseline throughput 提高 2–16×；SIFT0.1B top-k 10–3000 时平均少于 10 ms、P99.9 少于 20 ms（§5.2、图 14）。
- 10B 时单机 Helmsman 用 160–330 GB DRAM 达到 10-shard HNSW（2.5 TB DRAM/320 cores）的 47%–85% throughput，CPU 少约 3–4×、DRAM 近少一个数量级（§5.2、图 17）。
- pruning 相对无 pruning 提升 1.1–1.6×，相对 fixed policy 高 5%–25%；Gen4→Gen5 SSD 吞吐增 55%–87%，graph baseline 仅 10%–30%（§5.3–5.4）。
- 0.1B CPU build 9–12 h，4×L20 后少于 1 h、最高约 10×；10B 用 1,024→10⁴ CPU cores 从超过 16 h 降到约 4–7 h（§5.5、图 21）。
- RedSrch10B cost efficiency 从 HNSW 1.2 提至 10 QPS/$（8.3×）；production 40 machines 承接此前约 35,000 cores/0.35 PB DRAM，device cost 少 90%以上（§5.6、§6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| clustering+userspace IO 能满足在线 large-top-k SLA | §5.2、图 14–17：2–16×、5–10 ms | 12×Gen5 SSD、90% recall、top-k 至 3000 | 强 |
| 性价比显著高于 in-DRAM HNSW | §5.6：10B 8.3× QPS/$、DRAM 少 90% | RedSrch 与给定价格模型 | 强 |
| learned pruning 兼顾 batch IO 与少扫描 | §5.4、图 19–20：1.1–1.6×、recall target | 五 production/public dataset | 强 |
| construction 可支持日常重建 | §5.5：0.1B 少于 1 h、10B 4–7 h | 4 L20 与最高 10⁴ CPU cores | 中 |

## 批判性分析

### 论证链条

生产 observation 反转了“graph IO 少必更适合 SSD”的常识：大 top-k 下 dependency depth 更关键。storage、pruning、builder 分别回应 serving bandwidth、query variance、freshness，部署数字证明系统价值。40 台替代旧资源仍需注意承接的具体 traffic/index subset，不等于 RedNote 全量 PB fleet 已替换。

### 假设压力测试

收益依赖 12-drive Gen5 array；小部署或 cloud network-attached SSD 可能无同样 parallelism。learned router drift 会漏 recall，近似 ground truth 也可能把错误固化。hot cluster burst 已在 rollout 中触发 die conflict，即使全局 bandwidth 少于 20%；复制 cluster list 提升 1.5–2×说明 average device model 不足。

### 实验可信度

真实 top-k、六 dataset、强 baseline、tail/recall/cost/build/deployment 覆盖全面，是优势。SIFT10B 由 SIFT1B 复制，结构不等价于真实 10B；production trace/data难外部复核。cost 按特定硬件价格且忽略 SPDK polling、GPU/CPU pool opportunity cost与运维复杂度。

### 系统性缺陷

SPDK 设备直控扩大 crash recovery、bad block、firmware 与 observability 责任。learned pruning 是在线 correctness-adjacent component，需要 recall canary、rollback 和 per-segment fallback；论文未完整描述模型失效保护。周期 rebuild+auxiliary index/tombstone 会增加 query merge、memory 与 consistency risk。

## 局限与后续工作

- **局限 1**：不原生支持高率 in-place update，依赖 rebuild+delta index。
- **局限 2**：SPDK/polling 与多 Gen5 SSD 是主要硬件前提。
- **局限 3**：learned pruning 的 drift、rare-query recall 与安全 fallback 未充分量化。
- **后续工作 1**：回放 embedding/query drift，按 query cohort 报 recall violation，并建立自动 fallback 到 conservative nprobe 的阈值。
- **后续工作 2**：对 hot cluster 做 die/channel-aware replication/placement，测 P99.9 与空间放大 Pareto frontier。
- **后续工作 3**：把 online update、auxiliary index、tombstone 和 rebuild 合并成本计入 QPS/$，比较 SPFresh/Quake 等 dynamic ANNS。

## 相关

- **相关概念**：[[Approximate-Nearest-Neighbor-Search]]、[[HNSW]]、[[SPDK]]、[[Vector-Database]]
- **同类系统**：[[SPANN]]、[[DiskANN]]、[[PipeANN]]、[[Starling]]
- **同会议**：[[OSDI-2026]]
