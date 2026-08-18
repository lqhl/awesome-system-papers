---
type: theme
topic: Storage-Systems
theme_kind: area
member_tag: area/storage-systems
paper_count: 8
first_generated: 2026-08-17
last_updated: 2026-08-18
tags: [topic-overview, storage, file-systems, disaggregated-memory]
---

# 存储系统与解聚内存综述

> 8 篇论文覆盖 DNA storage、云块存储索引、生成式文件系统、AI storage pipeline 和 RNIC-managed disaggregated memory；主线是让介质、workload 与数据路径的自然粒度直接进入系统抽象。

## 核心论文

### 新介质、块存储与文件系统（4 篇）

- [[LiqSD-FAST25|LiqSD]] — 用 dual DTL、symbiotic metadata 和 delayed invalidation 构造 DNA block device。
- [[RASK-FAST26|RASK]] — 把连续写 range 直接作为 EBS index key，减少 point-entry 内存与 lookup。
- [[SysSpec-FAST26|SysSpec]] — 用 formal specification 驱动 [[LLM]] 生成文件系统实现。
- [[ProbeFS-SOSP26|ProbeFS]] — 以 biochemical content addressing 和 parallelism 构造 hierarchical DNA file system；当前仅有公开 metadata。

### AI 数据与分布式文件系统（2 篇）

- [[AITurbo-FAST26|AITurbo]] — 用 grouped I/O API、host DRAM 与 compute fabric 加速 checkpoint/KV bulk I/O。
- [[FalconFS-NSDI26|FalconFS]] — 删除 DL client metadata cache，把 path resolution 和 namespace state 移到 metadata server。

### 解聚内存管理（2 篇）

- [[ODRP-NSDI25|ODRP]] — 把 4 KiB remote paging 的 allocation、translation 和 access 编成 RNIC WR chain。
- [[OneSidedMW-NSDI26|OneSidedMW]] — 用 RNIC-offloaded type-2 MW bind/unbind 解耦 memory management 与原生 one-sided access。

## 主题综述

DNA storage 路线从 [[LiqSD-FAST25]] 的 block abstraction 延伸到 [[ProbeFS-SOSP26]] 的 hierarchical filesystem。LiqSD 已明确展示介质粒度不对称如何逼出 dual DTL 与 delayed invalidation，但当前单 block 操作仍是几十分钟；ProbeFS 是否用 biochemical addressing/parallelism 改变这条物理边界，要等全文公开后判断。

[[RASK-FAST26]] 与 [[FalconFS-NSDI26]] 都用 production trace 推翻通用数据结构直觉：EBS 写入应以 range 而非 point 建索引，DL random traversal 应删除 client metadata cache 而不是继续扩大它。[[AITurbo-FAST26]] 同样让 checkpoint/KV 的 grouped bulk I/O 暴露给 storage layer，三者共同强调 workload-native granularity。

解聚内存形成清楚的两代设计。[[ODRP-NSDI25]] 用 page translation 得到严格 4 KiB allocation 与 100% utilization，但每次 access 要走 WR chain；[[OneSidedMW-NSDI26]] 只 offload type-2 MW control path，让 READ/WRITE 回到 native one-sided path，并支持 variable-size I/O。

## 设计空间矩阵

| 论文 | 工作负载 | 瓶颈 | 机制 | 主要资源 | 证据边界 |
|---|---|---|---|---|---|
| [[LiqSD-FAST25]] | archival DNA block | metadata/update amplification | dual DTL+delayed invalidation | DNA/SSD | simulator、分钟级 I/O |
| [[RASK-FAST26]] | cloud block store | index memory | range-as-key | DRAM/storage | 多 vendor trace |
| [[SysSpec-FAST26]] | FS evolution | implementation maintenance | formal spec→LLM generation | LLM/verifier | selected modules/features |
| [[ProbeFS-SOSP26]] | DNA filesystem | 未公开 | biochemical addressing | DNA | metadata-only |
| [[AITurbo-FAST26]] | checkpoint/KV I/O | frontend/network | grouped API+staging | DRAM/RDMA/storage | Huawei production |
| [[FalconFS-NSDI26]] | DL small files | metadata cache/amplification | stateless client | MDS/SSD | 10,000 NPU deployment |
| [[ODRP-NSDI25]] | remote swap | allocation CPU | page WR chain | RNIC/DRAM | 1 MN+8 CN、4 KiB |
| [[OneSidedMW-NSDI26]] | swap+DM KV | management/access tradeoff | type-2 MW offload | RNIC/DRAM | 1 MN+6 CN |

## 共同观察

- **粒度错配是首要成本。** DNA strand/SC/spot、EBS range、DL directory traversal、AI grouped I/O 和 remote-memory chunk 都要求不同于传统 point/page/cache 的单位。
- **控制面可能压过数据传输。** [[ODRP-NSDI25]]、[[OneSidedMW-NSDI26]] 绕开弱 MNode CPU，[[FalconFS-NSDI26]] 消除 path-walk amplification，[[LiqSD-FAST25]] 把根 DTL 放入 SSD。
- **真实 trace 是抽象选择的证据。** [[RASK-FAST26]]、[[FalconFS-NSDI26]]、[[AITurbo-FAST26]] 都依赖生产 workload，而不是只凭硬件 peak bandwidth 设计。

## 假设冲突与脆弱点

- [[ODRP-NSDI25]] 的 page-specific translation 与 [[OneSidedMW-NSDI26]] 的 variable-size capability 分别优化 utilization 和 access latency；crossover 取决于 fragmentation、allocation frequency、QP/MW capacity。
- [[FalconFS-NSDI26]] 假设 client locality 极弱；通用 POSIX、source tree 和 metadata-hot workload 可能仍更适合 stateful cache。
- [[LiqSD-FAST25]] 用 amplification 代表未来介质趋势，不能掩盖当前绝对 latency；[[ProbeFS-SOSP26]] 尚无全文，不能被当作该问题已经解决。

## 值得关注的方向

- **自适应远端内存 primitive**：按 allocation/access ratio 在线选择 ODRP page mapping 或 OneSidedMW capability。
- **Stateless/stateful DFS hybrid**：根据 directory reuse、packing 和 memory pressure 切换 client/server path resolution。
- **DNA 系统实机证据**：在小规模生化实验台验证 metadata、GC、content addressing 的错误率、成本和恢复时间。
