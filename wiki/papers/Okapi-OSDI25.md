---
type: paper
name: Okapi
full_title: "Okapi: Decoupling Data Striping and Redundancy Grouping in Cluster File Systems"
authors: [Sanjith Athlur, Timothy Kim, Saurabh Kadekodi, Francisco Maturana, Xavier Ramos, et al.]
venue: OSDI
year: 2025
tags: [distributed-storage, erasure-coding, cluster-filesystem, hdfs, striping]
source_pdf: "[[osdi25-athlur.pdf]]"
source_md: "[[osdi25-athlur]]"
---

# Okapi: Decoupling Data Striping and Redundancy Grouping in Cluster File Systems (OSDI 2025)

> **一句话总结**：Okapi 将 data striping 与 erasure grouping 解耦，Google 实测 64%–94% 文件读大小长期稳定而 EC 方案可变 4 次；独立调 stripe 宽可让 12-of-15 读吞吐提升最高 115%、seek 降 70%，EC 转换 IO 降 38%–70%，元数据开销 <1%。

## 问题与动机

Colossus、Lustre、Ceph、HDFS 等将 k-of-n 纠删码的 **stripe width**（数据并行 spread）与 **group width**（共同编码的 k）强制相等。这带来两重低效：(1) 性能与可靠性/空间效率无法独立调——视频流要窄 stripe+宽 group，批处理要宽 stripe+窄 group；(2) 变更 EC 方案必须 **re-stripe** 全文件，与数据降温、磁盘故障率变化、紧急降 k 等日益频繁的 EC transition 冲突。

Google 观测：mid-sized read（>1 MB、≤~50 MB）占已读字节 65%；大量文件用 k>50 换空间却牺牲 IO；64%–94% 抽样文件 150 天内读大小几乎不变，但 EC 可变多达 4 次。

## 关键观察 / 隐含假设

- **观察 1**：stripe 与 group 服务不同目标——前者决定 seek/amortization 与并行度，后者决定 MTTDL、空间开销与重建 IO；耦合迫使单一 k 同时妥协。
  - **依赖假设**：工作负载读大小分布相对稳定，且由内部服务驱动（非随机用户读）。
  - **可能失效场景**：读模式剧烈变化而 stripe 未重配；极端宽 group+窄 stripe 下 degraded read 放大。
- **观察 2**：group 由文件内连续 data block 组成时，可从现有 stripe 映射 **推断** group 位置，无需双倍元数据。
  - **依赖假设**：顺序写、关闭后不改是 EC 文件主路径（HDFS/Ceph/Azure 现状）。
  - **证据强度**：强——live cluster 上增量元数据 <1%。
- **假设 1**：partial parity 可把宽 group 写路径的 client 内存从「缓存全部 cell」降到「缓存 r 个 parity 块」量级。
  - **证据强度**：中——数学上成立，极端 stripe/group 组合仍需验证峰值内存。

## 核心方法

Okapi 允许每文件独立配置 stripe width 与 (k, r)。数据按 cell 在 stripe 内 round-robin；parity 对**连续 k 个 data block**（可跨 stripe 边界）计算。

**降元数据**：block x 的 stripe = ⌈x/stripe_width⌉，group = ⌈x/group_width⌉，从 stripe 列表推断 group 磁盘映射。

**写路径 partial parity**：把 Galois 编码拆成 k 次独立部分积，client 缓冲 partial parity 而非全部 data cell（6-of-8、4-wide stripe 时从 34 cells 降到 2 parity 块量级）。

**degraded read**：大顺序读时缓存已读数据，避免为重建重复拉取；小读行为与 coupled 相近。

**re-grouping**：EC transition 只读 data、重写 parity，不移动 data block；配合 smart EC transition 可再减 IO。

## 设计取舍

- **取舍 1**：保留「k 个 cell 到齐才算 parity、之前 data 无保护」语义，与 coupled 公平对比；不引入 sync-on-write 的强耐久。
- **取舍 2**：re-grouping 可能需搬迁同 failure domain 的 block，但可通过创建时 mindful placement 消除。
- **边界条件**：部分 mid-sized degraded read 在 decoupled 下略差，论文量化后认为可接受。

## 实验与结果

- HDFS 原型 vs coupled 6-of-9：读吞吐最高 +80%，seek/s 最高 -70%。
- 12-of-15、8 MB 读：吞吐最高 +115%；Google 合成 workload 端到端延迟 -36%。
- EC transition：比 read-reencode-write 少 50% IO；配合 [29] 技术少 70%；紧急降 k 场景少 38%–45% IO。
- 开销：元数据与 file manager 内存 <1%；file creation 与 degraded read 资源增加可控。

## Critical Analysis

### 论证链条

Google 生产 trace 证明读模式稳、EC 常变 → 解耦有经济动机 → 推断式元数据+partial parity 控制开销 → 微基准与合成 workload 验证吞吐/transition 收益。链条在 hyperscaler 顺序写 EC 文件上闭合；随机小文件改写路径论文未覆盖。

### 假设压力测试

- 若应用读大小漂移而 stripe 静态配置，性能优势会衰减。
- 极宽 group 下 partial parity 仍可能给 client 带来压力（论文有界但未给最坏公式）。
- Ceph/Colossus 集成成本与跨团队调参流程论文略写。

### 实验可信度

学术集群 + Google 派生 workload 有代表性；缺长期生产 A/B。baseline 公平（同 durability 语义）。

### 系统性缺陷

论文未讨论：自动 stripe/group 选择误配运维成本、与 tiering/cache 层交互、在线改 stripe 是否需数据移动（re-grouping 不改 stripe，但改 stripe 仍可能要移动）。

## 局限与 Future Work

- **局限 1**：EC 文件仍以顺序写为主，不支持通用 append/modify。
- **局限 2**：部分 decoupled 配置 degraded read 略差于 coupled。
- **Future work 1**：在线自适应 stripe width 与读 trace 联动；与 disk-adaptive redundancy [25–27] 联合优化。
- **Future work 2**：在 Colossus 规模上验证 partial parity 的 tail memory 与 GC 压力。

## 相关

- **相关概念**：Erasure Coding、[[RDMA]]（对比语境）
- **同类系统**：HDFS、Ceph、Colossus、Lustre
- **同会议**：[[OSDI-2025]]