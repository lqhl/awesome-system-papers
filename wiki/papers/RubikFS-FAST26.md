---
type: paper
name: RubikFS
full_title: "Towards Condensed and Efficient Read-Only File System via Sort-Enhanced Compression"
authors: [Hao Huang, Yifeng Zhang, Yanqi Pan, Wen Xia, Xiangyu Zou, Darong Yang, Jubin Zhong, Hua Liao]
venue: FAST
year: 2026
tags: [file-system, compression, read-only, deduplication, embedded]
source_pdf: "[[fast2026-huang.pdf]]"
source_md: "[[fast2026-huang]]"
---

# Towards Condensed and Efficient Read-Only File System via Sort-Enhanced Compression (FAST 2026)

> **一句话总结**：只读压缩 FS 的 block 压缩因 **data mixture**（相似数据跨 block 分散）损失字典压缩收益、又因冷热混排加剧读放大；RubikFS 在压缩前用 **相似图分簇排序 + hotness 分组** 把相似 chunk 聚入同一 block，在 6 个开源镜像上比 [[EROFS]]/[[Squashfs]] 压缩比最高提升 42.60%、无效读最高减少 70.70%，部分场景甚至超过 Direct 整镜像压缩。

## 问题与动机

只读压缩文件系统（[[EROFS]]、[[Squashfs]]）面向 IoT 内核、Android GSI、Docker 容器镜像等 **write-once, read-many** 场景：先把文件打包成连续 bitstream，再切成 block（4 KB–1 MB）独立压缩，在「压缩比」与「随机读可承受性」之间折中。随着系统升级和功能叠加，镜像体积持续增长，直接影响硬件成本（数十亿级 IoT 设备）和容器拉取/启动延迟。

作者在 openEuler 镜像上的初步测量（Figure 1/5）表明：即便把 block 增大到 1 MB，[[EROFS]]/[[Squashfs]] 的压缩比仍显著低于 **Direct**（整镜像不切块直接压缩）。Direct 可视为 FS 压缩的理论上界，但运行时必须解压整镜像才能取数，不可实用。根因被归结为 **data mixture**：切块后每个 block 内混入不相似数据，相似数据却分散在不同 block，字典压缩（[[LZ4]]/[[ZSTD]]/[[LZMA]] 的前半段）无法跨 block 消除冗余；同时大 block 把不同 hotness 的数据绑在一起，在内存受限的嵌入式设备上引发严重 **read amplification**。

论文 claim 是：在不改变只读 FS 基本读路径的前提下，通过 **sort-enhanced compression** 在构建期重排数据布局，同时逼近 Direct 的压缩比并控制读放大。这与备份存储里的 Finesse/Odess/Palantir 等相似度检测不同——后者面向大规模备份、只做 0/1 相似判定，且排序开销与只读镜像构建的工作流不匹配。

## 关键观察 / 隐含假设

- **观察 1：block 压缩的主要收益来自 dictionary compression，而非 entropy coding**。openEuler + [[LZMA]] 实验中，固定 4 KB dictionary 时增大 block 几乎不提升压缩比；只有把 dictionary size 随 block 同步放大，intra-block 相似冗余才能被理论上去尽（Figure 5a）。
  - **依赖假设**：评估镜像的冗余主要是「可跨距离匹配的字节串重复」，entropy 阶段对 block 大小的边际收益很小。
  - **可能失效场景**：高度随机或已强熵编码的数据（加密 payload、预压缩媒体），字典压缩本身收益有限，排序带来的提升会缩水。

- **观察 2：data mixture 是 block 压缩与 Direct 差距的主因；排序可显著弥补**。把数据按相似度聚簇后再切块（Data Sorted vs Data Mixed），无论 block 大小如何，压缩比都一致高于未排序基线（Figure 5b）。
  - **依赖假设**：镜像内存在大量 **partial similarity**（部分相似 chunk），且这些 chunk 在原始文件布局中物理距离超过 compressor dictionary 范围。
  - **可能失效场景**：镜像以 tar 层叠的异构大文件为主（如 Friendica 容器，Others 组占绝大多数），跨类型相似性极少，排序收益趋近于 dedupe  alone。

- **观察 3：嵌入式只读镜像的读模式高度集中在启动阶段**。hot data 定义为「系统启动到 steady state 期间访问的 chunk」；运行时多数数据已 prefetch/cache，额外 I/O 很少（§4.4，引用数字 TV 等嵌入式工作）。
  - **依赖假设**：生产部署能提供代表性启动 trace（kprobe readpage → trace.txt），且应用 I/O 模式确定性较强。
  - **可能失效场景**：容器镜像在运行期持续读冷数据、或多租户动态 workload；Friendica 类镜像的 hotness 定义与嵌入式板卡差异大，论文仅对 openEuler 做了读放大实验。

- **假设 1：按文件类型（ELF Code/Data、Binary、Text、Others）预分组不会损失跨类型相似压缩机会**。
  - **证据强度**：**中**。敏感分析显示 w/ Grouper 压缩比略高于 w/o Grouper（Figure 12a），说明风险目前可忽略，但仅在一个镜像、一种算法上验证。

- **假设 2：固定大小切块（FSC）+ 相似排序可补偿 CDC 在边界漂移上的 dedupe 优势，同时避免页未对齐带来的最坏读放大**。
  - **证据强度**：**中强**。chunk size = min(4 KB, BlockSize/16) 在多种 block 下接近最优；full dedupe 与 tail dedupe 压缩比差异 < 0.02×，但论文未在真实「单字节插入」文件更新场景下测 FSC 边界漂移。

## 核心方法

RubikFS 在 [[EROFS]] 上实现：userspace 构建工具 RubikFS.mkfs（基于 erofs-utils 1.8.10，~3.5K LoC 改动）+ Linux 6.16 内核 FS。核心是把传统「打包 → 切块 → 压缩」流水线前面插入四段式重排，回应上述 data mixture 与读放大观察。

**Data grouper**（回应构建复杂度挑战）：按 Figure 2a 的五类（ELF Code / ELF Data / Binary / Text / Others）预分组，ELF 以 .rodata 为切分点；同类数据更可能相似，分组后相似度计算规模从全局 O(N²) 降到各组独立。Harm-3516/3518 大镜像上排序时间可从 +287 s 降到 +208 s（Table 3）。

**Data chunker**：默认 **FSC** 而非 [[Content-Defined Chunking|CDC]]，chunk size 按式 (1) 自适应：`min(4 KB, BlockSize/16)`，在页局部性与细粒度排序间折中；之后做 **full dedupe**（非 [[EROFS]] 的 tail dedupe），重复 chunk 只存一份，读取时由 dupe fixer 根据索引还原。

**Hotness grouper**（回应读放大）：摄入 `--trace=trace.txt`，把每组再分为 hot/cold 子组，分别排序压缩，使启动热数据在物理上更集中。接口设计为嵌入式确定性 workload；可扩展到多级 hot 子组。

**Similarity sorter**（核心，回应 partial similarity 与备份算法不匹配）：(1) gear hash 抽样提取特征，采样率 P=1/128，每个特征代表 1/P 字节相似性；(2) 构建相似图，边权 = 相同特征数 / 总特征数（0–1 连续值，区别于 Finesse/Odess 的 0/1）；(3) 去掉 0 边后用 [[METIS]] 做子图划分，默认子图 64 chunk；(4) intra-subgraph 与 inter-subgraph 均按相似度排序；(5) 打包成单一 data stream 并生成索引。特征经 hash table 分桶，构图复杂度从 O(N²·M²) 降到近似 O(N)。

**索引与读路径**：每个 chunk 12 B 条目（orig_offset, packed_offset, size），开销 0.018%–2.93%；读时 decompressor → dupe fixer → file recreator 三步还原，逻辑路径与 [[EROFS]] 相近。`-Esort` 可关闭排序回退原生 EROFS 流程。

## 设计取舍

- **排序换压缩比，以离线构建成本为代价**：相似图 + [[METIS]] 使大镜像构建时间增加数分钟（如 Harm-3516 LZMA 1 MB：+208 s vs 无排序 163 s），但完全离线，不影响设备端 CPU 需求（§7 论证）。
- **FSC 换最坏读放大可控性**：放弃 CDC 对字节级更新的 dedupe 鲁棒性，依赖 similarity sorter 处理「部分相似」；页对齐友好，但边界漂移场景未覆盖。
- **hot/cold 硬分割换启动读性能**：12% hot 数据下读量减少高达 70.70%，40% hot 极端情况下压缩比损失仍 < 0.11×——用极小压缩比代价换显著 I/O 削减。
- **类型分组换构建可扩展性**：跨类型相似数据不再共同排序；对容器 tar-heavy 镜像（Friendica）分组收益有限（Table 3 仅 +18.71 s vs +29.06 s）。
- **边界条件**：在 Harm-3861 等小镜像、1 MB block 下，原生 [[EROFS]] 因镜像小而接近 Direct，RubikFS 优势收窄；[[LZ4]] 字典上限 64 KB 使 block > 64 KB 后压缩比平台化，排序收益相对更显著。

## 实验与结果

- **压缩比**（6 镜像 × [[LZ4]]/[[ZSTD]]/[[LZMA]]，block 4 KB–1 MB，对比 [[EROFS]]、[[Squashfs]]、Direct）：RubikFS 一致最高；相对现有 ROFS 最多 **+42.60%** 压缩比；Harm-3516/3518/3861 上甚至超过 Direct（因分簇跨越 [[LZ4]] 64 KB 字典限制，聚到远距离相似串）。
- **模块分解**（Figure 11）：dedupe alone 收益镜像敏感；similarity sorter 对所有镜像稳定正向；Palantir 式 naive sorter 不稳定、有时负收益。
- **读放大**（openEuler，1 MB block，12%/40% hot trace，FEMU 模拟 MT29F16G08CBACA 75 µs 页延迟）：有 hotness grouper 时 runtime 最多降 **65.03%**，读取量最多降 **70.70%**（12% hot + [[LZ4]]：16.41 MB vs 无 grouper 55.72 MB）；无 grouper 时与 [[EROFS]] 同级，说明排序本身不恶化读放大，瓶颈仍在 block 压缩。
- **构建时间**（LZMA 1 MB）：data grouper 对大相似镜像排序加速 21.97%–74.39%；小镜像 Harm-3861 排序反而略快于 No Sort（压缩更容易）。
- **敏感分析**（openEuler）：默认配置（类型分组、自适应 chunk、full dedupe、12% hot、P=1/128、子图 64）在压缩比上鲁棒，红线默认项均接近最优。

## Critical Analysis

### 论证链条

观察链条较闭合：Figure 5 把「dictionary size 需匹配 block」→「data mixture 限制跨 block 冗余」→「排序可恢复 compressibility」三步测量清楚，再映射到四组件设计。结果上压缩比主 claim 有 6 镜像 × 3 算法 × 多 block 支撑；读放大 claim 有 Table 2 定量支撑。薄弱环节在于：**读放大实验仅 openEuler 一个嵌入式镜像**，且 hot trace 用随机选文件/页合成，与真实启动路径的保真度未验证；「超过 Direct」出现在特定小板镜像 + [[LZ4]] 场景，外推到通用容器镜像需谨慎。

### 假设压力测试

- **启动集中读假设**：对 Friendica 等运行时持续读取的容器，hotness grouper 的收益可能远低于 70%；论文未测。
- **trace 可获取性**：依赖 kprobe + 跑到 steady state，对 CI/CD 批量构建镜像的流程可行，但对第三方闭源应用或安全沙箱环境，trace 采集成本论文未量化。
- **partial similarity 特征充分性**：gear hash 1/128 抽样 + 图划分是启发式，对加密或高熵二进制，相似图可能退化为稀疏图，收益接近 dedupe only——Yocto/Friendica 分解实验暗示低相似镜像排序时间虽短、压缩比提升也较小。
- **已证明 vs 推断**：压缩比提升为直接测量；「不需要更强 CPU」主要基于嵌入式启动文献 + 本机 FEMU 实验推断，未在多种真实板卡上测 CPU 占用峰值。

### 实验可信度

- **Workload 代表性**：6 镜像覆盖嵌入式内核、OpenHarmony 板卡、Yocto rootfs、Docker 容器，比单镜像工作更广；但规模均在 42 MB–771 MB（Table 1），GB 级镜像仅作者讨论声称可扩展，无实测。
- **Baseline 公平性**：与 [[EROFS]]/[[Squashfs]] 对比时注意到 Squashfs block 为压缩前大小、EROFS 为压缩后固定页对齐块——作者有说明，但跨 FS 对比需读者自行换算；Direct 作为上界合理。
- **Ablation**：Figure 11 有效分解 dedupe vs similarity sorter；Figure 12 覆盖主要超参；缺少「只开 hotness 不开 similarity」等交叉 ablation。
- **Metric 覆盖**：压缩比、构建时间、启动读延迟/读量较全；**尾延迟、运行时随机读、多进程并发读、故障恢复** 未测。

### 系统性缺陷

- **构建复杂度与内存**：相似图 + [[METIS]] 对大镜像（Harm-3516 +287 s 排序开销）仍是生产流水线瓶颈；峰值内存开销论文未给出曲线，仅定性说 hash 分桶降复杂度。
- **索引与元数据**：chunk 级索引增加 0.018%–2.93% 空间及读路径上的 dupe fixer/file recreator 逻辑，增加实现与正确性验证负担；论文未报告 fuzz/崩溃一致性测试。
- **可观测性与运维**：`-Esort` 回退路径存在，但排序失败、trace 缺失、类型误判时的降级策略论文未讨论。
- **兼容性**：基于 [[EROFS]] 主线，对 [[Squashfs]] 生态、已有镜像增量重建工具链的迁移成本未评估。
- **隔离与安全**：只读 FS 不涉及多租户，但排序改变物理布局后侧信道或取证性影响论文未讨论。

## 局限与 Future Work

- **局限 1**：读放大评估仅限 openEuler + 合成 hot trace，对容器/桌面场景的泛化证据不足。
- **局限 2**：镜像规模 MB 级，GB 级镜像的构建时间、内存峰值、[[METIS]] 分区质量缺少实测。
- **局限 3**：hotness 仅二分类（hot/cold），对「温数据」或多级缓存策略未探索。
- **Future work 1**：在真实容器启动/IoT OTA 全流程上采集 production trace，量化 hotness grouper 在非嵌入式部署中的读放大上界。
- **Future work 2**：测量 GB 级镜像构建的内存-时间 Pareto 曲线，评估是否需近似排序（采样构图、分层聚类）以换可接受的压缩比损失。
- **Future work 3**：与 [[Content-Defined Chunking|CDC]]/tail dedupe 的混合策略——在 Text/ELF 组用 FSC、在 tar 层用 CDC——是否能在不牺牲页对齐的前提下进一步提升 Friendica 类镜像收益。

## 相关

- **相关概念**：[[Content-Defined Chunking]]、dictionary compression、[[METIS]] 图分割、read amplification、data deduplication
- **同类系统**：[[EROFS]]、[[Squashfs]]、Finesse、Odess、Palantir、Migratory Compression
- **同会议**：[[FAST-2026]]
- **对比**：RubikFS 在 [[EROFS]] 固定页对齐 block 上叠加排序；与 Squashfs 可变长 block + 元数据压缩的路线正交