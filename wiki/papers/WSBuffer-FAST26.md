---
type: paper
name: WSBuffer
full_title: "Rearchitecting Buffered I/O in the Era of High-Bandwidth SSDs"
authors: [Yekang Zhan, Tianze Wang, Zheng Peng, Haichuan Hu, Jiahao Wu, Xiangrui Yang, Qiang Cao, Hong Jiang, Jie Yao]
venue: FAST
year: 2026
tags: [buffered-io, page-cache, nvme-ssd, file-system, linux-kernel]
source_pdf: "[[fast2026-zhan.pdf]]"
source_md: "[[fast2026-zhan]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# WSBuffer：高带宽 SSD 时代重新架构缓冲 I/O（FAST 2026）

> **原题**：Rearchitecting Buffered I/O in the Era of High-Bandwidth SSDs

> **一句话总结**：测量表明高带宽 [[NVMe]] SSD 下 Linux [[Page-Cache]] 把**全部写**塞进关键路径导致管理开销与 `xa_lock` 争用压过内存带宽优势（direct I/O 写带宽高 1.10–4.46×），且 partial-page write 的 read-before-write 延迟高 1.51–84.37×；WSBuffer 用 scrap buffer 承接小写/非对齐写、把 ≥1MB 对齐部分直送 SSD，配合 OTflush 与 SXArray 并发管理，相对 EXT4/F2FS/BTRFS/XFS 与 SOTA [[ScaleCache]] 吞吐最多 **3.91×**、延迟最多 **82.80×**，且不改 POSIX [[Buffered-IO]] 接口。

## 问题与动机

几十年来 [[Buffered-IO]] 经 kernel [[Page-Cache]] 透明吸收读写，是应用默认路径。PCIe5.0 [[NVMe]] SSD 写带宽已超 10GB/s，多盘聚合后软件栈更需跟上硬件 scale。与此同时 [[Direct-IO]] 虽能 bypass page cache 释放盘带宽，却要求 offset/size/buffer 严格对齐，且 SSD 延迟仍远高于 DRAM，legacy 代码与读优化（folio batch alloc 等）使 buffered 模式在读写混合场景仍占主导。

作者 claim：问题不在「page cache 不够快」，而在**架构**——传统 buffered I/O 把 buffer 放在**写关键路径**上缓冲**所有** incoming writes，在 mem/storage 带宽鸿沟收窄后，page 分配、XArray 查找、LRU、脏页状态维护的成本从「可忽略」变成写瓶颈。三类根因（C1–C3）在 §2.3 用 FIO microbenchmark 量化。已有路线分两类：(1) 优化 page cache（[[ScaleCache]]、StreamCache、uncached buffered I/O）受全缓冲架构上限；(2) 部分/完全 bypass（Lustre AutoIO、[[OrchFS]]、[[SPDK]]）牺牲通用性与零改码优势。WSBuffer 目标是在**不改 I/O 编程接口**前提下重架构写数据路径，让 page cache **专注读**，写路径主动吃 SSD 带宽。

## 关键观察 / 隐含假设

- **观察 1**：在 8 盘 RAID0（~55GB/s）上，即使给 buffered I/O 无限内存并关闭 background flush，sequential 2MB 写的带宽仍系统性低于 [[Direct-IO]]（1.10–4.46×）。
  - **依赖假设**：写带宽瓶颈来自 page cache 管理而非 DRAM 带宽本身；评测用 ideal sequential large write。
  - **可能失效场景**：极小写、元数据密集、或底层 FS 自身 metadata 锁成为主瓶颈时，C1 叙事权重下降；单盘低带宽环境「直送 SSD」收益缩小。

- **观察 2**：开启 page flushing 后，16 线程 4KB full-page 写的吞吐强烈依赖可用内存比例——内存供给为写入量 70% 时相对 100% 场景吞吐最多低 **54%**；根因是 XArray `xa_lock` 上 free 插入、clean 删除、脏→writeback→clean 多次抢锁。
  - **依赖假设**：写密集 + 有限内存 + 多线程各写独立文件（避免文件锁）；Linux page cache XArray 仍是统一索引与状态机。
  - **可能失效场景**：内存充裕到几乎不 reclaim、单线程写、或已部署 ccXArray 等并发索引优化时，C2 压力减轻。

- **观察 3**：page cache miss 的 partial-page write 必须先 SSD-read 填页再写，延迟比 full-page write 高 **1.51–84.37×**，惩罚几乎全来自慢随机读而非带宽。
  - **依赖假设**：应用写偏移/大小多样；冷页或空洞页上的局部更新普遍。
  - **可能失效场景**：工作负载已对齐且顺序覆盖整页（如某些 checkpoint）、或数据已在 cache 中命中。

- **假设 1**：在评测平台（单盘 ~6.9GB/s 写、8 盘 RAID0）上，**≥1MB 且按 256KB data-zone 对齐**的写直送 SSD 比经 scrap buffer 更快——默认 request-size threshold = 1MB。
  - **证据强度**：**中**——基于该平台 FIO 测量；换 slower SSD、更高 NUMA 跨节点拷贝成本或不同 RAID stripe 时需重标定。

- **假设 2**：scrap-page 上先写 partial 数据、再异步 OTflush Stage-1 做 read-before-write，在应用时间尺度上可隐藏 C3 惩罚，且与 foreground 直写 SSD 通过 per-SSD `Bcount` 粗粒度避让 busy 设备。
  - **证据强度**：**中**——microbenchmark 与多类 app 有效；`Bcount` 阈值 4MB 为启发式，未覆盖复杂 SSD 内部 GC/并行度动态。

## 核心方法

WSBuffer（write-scrap buffering）在 [[Linux]] kernel 6.8 上基于 [[XFS]] 实现约 4500 LoC，核心是把**写缓冲**从 page cache 迁到 scrap buffer，读路径基本保留 legacy page cache。

### Scrap Buffer（§3.2）（废料缓冲区（§3.2））

新型内存页结构：**128B header**（有效字节计数、segment 数、SSD-id、flush tag、最多 15 个 8B index entry 记录段偏移/长度）+ **256KB data-zone**（= 2×128KB，对齐 8 channel × 16KB SSD-page，利于 SSD 内部并行）。与 page cache「页总是满的」不同，scrap-page 原生表达**部分填充**与多段 disjoint 数据；>95% 场景 segment 数 <15。分配以 32 页为 batch，header 区与 data-zone 区分区存放（4KB headers + 8MB data-zones），减碎片与跨界访问。

写路径：**不做同步 read-before-write**——先直接写 scrap-page，再 merge 重叠 segment 并更新 header；页变 full 时入 OTflush Stage-2 队列。partial-page 的 SSD-read 推迟到 OTflush Stage-1 异步完成。

### Buffer-Minimized Data Access（§3.3）（缓冲区最小化数据访问（§3.3））

写：< threshold（默认 1MB）全进 scrap buffer；大写按 **scrap-page-data-zone（256KB）** 切分为 partial 部分（scrap buffer）与 large-aligned 部分（`submit_bio` 直写 SSD）。对齐粒度选 256KB 而非 4KB 是为 (1) SSD 最小存储单元对齐、抗 file fragmentation；(2) OTflush 大块 writeback。直写 SSD 后 reclaim 覆盖范围内 obsolete 的 scrap-page 与只读 memory-page（后台执行，§3.5）。

读：先查 scrap buffer（最新数据），未命中再走 legacy page cache + page fault SSD-read。一致性模型：**dirty 只在 scrap-page；memory-page 恒 clean**，专做读缓存——与写路径分离简化三路（scrap / page cache / SSD）一致性。

### OTflush（§3.4）

两阶段 opportunistic flush：**Stage-1** 对 unfilled scrap-page 在 idle SSD 上执行 read-fill；**Stage-2** 将 full scrap-page 以 data-zone 粒度 writeback 并立即 reclaim。每 SSD 维护 `Bcount`（提交增、完成减）与 4MB busy 阈值做负载感知，忙则回队尾避免 head-of-line blocking。默认仅 **2 个 OTflush 线程**（Stage-1/2 各一）；scrap-page 生命周期短，高 SSD 带宽下内存占用窗口小。

### Concurrent Page Management（§3.5）（并发页面管理（§3.5））

读-only memory-page 仍用 XArray，但无脏页状态翻转，争用大减。scrap-page 用改良 **SXArray**：插入正常；删除仅 index-entry 置 NULL + entry 级轻锁，树结构更新延迟到负载轻或文件关闭时——用可能更大的树换更少 `xa_lock` 争用。scrap-page 状态用 **per-page lock**，写与 OTflush Stage-1 可并行；Stage-2 writeback 后只需 entry 级锁更新索引。可与 [[ScaleCache]] 的 ccXArray 等优化正交叠加。

`fsync()`：只查 scrap-page，唤醒专用线程批量 flush；因 OTflush 已高效，sync 路径通常剩余页很少。

## 设计取舍

- **取舍 1：写路径重架构 vs 实现与可移植成本**。放弃「所有写经 page cache」的统一模型，引入 scrap buffer + SXArray + OTflush 第二套索引/flush 状态机；换不改应用、保留 [[Buffered-IO]] 语义。移植到其他 FS 需重做 data-access 与 OTflush 胶水层（论文称 scrap 结构与并发管理可复用）。
- **取舍 2：大粒度 scrap-page（256KB）vs 内存灵活度**。更大 data-zone 利 OTflush 与 SSD 并行，但小写全部缓冲时粒度粗于 4KB page；header 15 segment 上限对极端碎片化写可能不够（可扩 header）。
- **取舍 3：平台相关 threshold（1MB）vs 自适应**。固定阈值实现简单，但不同 SSD/RAID/CPU 拷贝能力下最优切分点不同；Table 4 显示 threshold 从 1MB 降到 256KB 会显著改变「进内存比例」。
- **取舍 4：粗粒度 SSD busy 感知 vs 精确调度**。`Bcount` 低开销但无法建模 SSD 内部队列/GC；foreground 直写与 background flush 仍可能间接干扰。
- **边界条件**：写密集、多线程、NVMe 带宽高于 page cache 管理吞吐时收益最大；纯读与 XFS 几乎持平；读偏重且关闭/弱化 OTflush 时可能因双索引查找（SXArray + XArray）略逊于调优后的 XFS。

## 实验与结果

**环境**：2×Xeon Gold 6348、256GB DDR4、8×PCIe4 Samsung 990 PRO RAID0（~55GB/s 聚合）、Ubuntu 22.04、kernel 6.8；对比 EXT4/F2FS/BTRFS/XFS、[[ScaleCache]]-XFS（kernel 5.4）、自实现 XFS-AutoIO（Lustre AutoIO 原则）。

- **Microbenchmark（flush 关闭、内存充足）**：full-page 写延迟 1.03–3.29× 于 baseline；partial-page 写 1.70–**82.80×**；相对 XFS-direct I/O 与 XFS-AutoIO 1.59–231.28×。≥1MB 写几乎全部直送 SSD。
- **多线程 FIO（bsrange 4K–4M）**：吞吐 1.21–**3.91×**；峰值受 ~55GB/s SSD 聚合带宽与 user buffer→kernel 对齐拷贝约束。
- **Filebench**：Fileserver（写偏重）1.23–2.51×（充足内存）/ 1.23–4.48×（限内存+flush）；Varmail（>60% 时间在 `fsync`）1.06–2.84×；Webproxy（读偏重 5:1）充足内存且 flush 关闭时**略低于 XFS**，启用 OTflush 可拉近。
- **真实应用**：LevelDB+YCSB 1.32–2.02×；GridGraph 1.09–4.37× OPS；Nek5000 HPC 1.74–3.09×（ScaleCache-XFS 次之）。
- **资源**：相对 XFS/ScaleCache-XFS，CPU 利用低 3.2–28.4%（>80% 写字节直写 SSD、DMA 为主）；真实 app 写路径内存缓冲占比仅 0.34–1.67%（大写直写 + 小写后被大写覆盖 reclaim）。
- **Sensitivity**：RAID stripe 大小不影响相对优势；SSD 数量从 1 增至 8 时 WSBuffer 吞吐随带宽近线性升，XFS 几乎不变——支持「能 scale 用满盘带宽」的 claim。

## 批判性分析

### 论证链条

测量（C1 direct 更快、C2 内存比例敏感、C3 partial-page 灾难）→ 诊断全缓冲写路径与 XArray 状态机 → scrap buffer 去同步 read-before-write + 大写直送 SSD（G1）→ OTflush 异步 fill/大块 writeback（G2/G3）→ SXArray/ per-page lock 降争用（G2）→ micro + macro + 三类 app 全面提速。链条在**本地 RAID0 NVMe、写密集或混合、buffered POSIX 接口**设定下较闭合；读路径故意不改，故 read-only 等价 XFS 符合设计预期。

薄弱跳步：(1) **ScaleCache 基线跑在 kernel 5.4、WSBuffer 在 6.8**，作者承认 mainline XFS/folio 改进使 SC-XFS 部分实验偏弱，与「击败 SOTA page cache 优化」的对比需打折；(2) 峰值吞吐论证依赖 8 盘 RAID0，单盘生产默认可否复现 3.91× 需读者自行对照 Figure 16；(3) Webproxy 读偏重场景暴露**双索引读路径开销**，与「保留读优势」叙事存在条件性张力。

### 假设压力测试

- **慢速或高延迟存储**：SATA SSD、网络盘、CXL 扩展存储上，「直送 SSD 优于 buffer」的 1MB 阈值可能上移或失效；论文 sensitivity 仅扫 RAID stripe 与 SSD 数量，未扫单盘延迟主导场景。
- **极端碎片化小写**：KV/compaction 若持续产生大量长期存活的小 scrap-page，OTflush Stage-1 队列与 SXArray 条目数上升，内存与 CPU 维护成本可能逆转 Table 5 的「<2% 内存」结论（LevelDB 实验已提示小写全缓冲）。
- **多租户/共享文件**：实验用 per-thread 独立文件避文件锁；多进程写同一文件、或 mmap 共享写时 scrap-page 与 page cache reclaim 交叉，论文未测隔离性与公平性。
- **崩溃一致性**：durability 委托底层 FS journaling（与 legacy buffered 相同层级），scrap-page 未刷盘前的窗口行为依赖 XFS 元数据路径；论文未单独做 crash/recovery 实验——**论文未讨论**断电时 scrap buffer 与直写 SSD 交错顺序的细粒度保证。
- **与 [[Direct-IO]]/用户态引擎共存**：同一节点混部 SPDK/[[OrchFS]] 类直写应用时，WSBuffer 的 SSD busy 启发式未协调全局 I/O 调度。

### 实验可信度

- **Benchmark 代表性**：FIO + Filebench 三件套 + LevelDB/GridGraph/Nek5000 覆盖 DB、图、HPC，对「本地 NVMe 数据密集」代表性强；缺少云对象/分布式 FS（S3、[[Lustre]] 生产 trace）与容器 overlay 栈。
- **Baseline 公平性**：对 EXT4/F2FS/BTRFS/XFS 较公平；ScaleCache 内核版本落后是已知 asymmetry；XFS-AutoIO 为用户态复现，与 WSBuffer 内核路径对比合理但未必代表调优后的 Lustre AutoIO 生产配置。
- **Ablation**：Table 4 threshold 扫描、OTflush 线程数在正文分散提及，缺少对 SXArray vs XArray-only、Stage-1/2 分拆、scrap-page 256KB vs 4KB 的系统性 ablation。
- **Metrics**：吞吐、平均延迟、OPS、CPU、内存比例覆盖充分；**尾延迟分布、sync 延迟方差、故障注入、可观测性开销**论文未系统报告。

### 系统性缺陷

- **运维复杂度**：第二套缓冲层 + 延迟 SXArray 树压缩使 debug「数据在哪（scrap/page cache/SSD）」比纯 page cache 更难；论文未讨论 tracepoint/计数器。
- **读偏重退化**：Webproxy 充足内存无 flush 时略输 XFS，说明读路径并非严格无损；生产需保证 OTflush 资源，否则读多写少服务可能倒退。
- **参数敏感**：1MB threshold、4MB busy 阈值、256KB zone、默认 2 OTflush 线程均绑定评测机；缺少自适应调参或管理面指南。
- **工程移植**：声明 FS 无关但实现绑定 XFS；其他 CoW FS（[[BTRFS]]）或 log-structured（[[F2FS]]）集成成本未验证。

## 局限与后续工作

- **局限 1**：默认仅 2 个 OTflush 线程；限内存 Fileserver 上内存释放仍可能跟不上 foreground 缓冲速率，需更多 flush 线程（论文在 §4.3.2 明确承认）。
- **局限 2**：读偏重且 OTflush 弱化时，scrap-page 堆积导致 SXArray+XArray 双查找，吞吐可能低于优化后的 XFS（§4.3.1 Webproxy）。
- **局限 3**：crash consistency 与持久化语义完全依赖底层 FS，scrap buffer 自身一致性边界未单独证明。
- **Future work 1**：将 WSBuffer 移植到 EXT4/F2FS 等并量化各 FS metadata 路径交互——可验证「架构正交性」是否跨 FS 成立。
- **Future work 2**：自适应 request-size threshold 与 OTflush 并发度（基于实时 `Bcount`、内存压力、写吞吐反馈）——需 production trace 驱动测量，而非固定 1MB/2 线程。
- **Future work 3**：与 [[ScaleCache]] ccXArray、folio 等读优化**叠加**的端到端收益与锁路径干扰——论文声称正交但缺少组合实验。

## 相关

- **相关概念**：[[Page-Cache]]、[[Buffered-IO]]、[[Direct-IO]]、[[NVMe]]、[[XArray]]、[[XFS]]、[[F2FS]]、[[EXT4]]
- **同类系统**：[[ScaleCache]]、StreamCache、Lustre AutoIO、[[OrchFS]]、[[SPDK]]、uncached buffered I/O
- **同会议**：[[FAST-2026]]
- **对比**：WSBuffer vs [[ScaleCache]] 是「写路径重架构 + 大写直送 SSD」vs「并发 page cache 索引」；vs [[OrchFS]]/[[Direct-IO]] 是「保留 POSIX buffered 语义」vs「对齐约束下 bypass」；vs MAIO（[[MAIO-FAST26]]）共享「page cache 默认策略跟不上硬件」叙事，但 WSBuffer 改内核写数据路径、MAIO 改可编程读 cache 策略
