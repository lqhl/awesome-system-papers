---
type: paper
name: Z-LFS
full_title: "Z-LFS: A Zoned Namespace-tailored Log-structured File System for Commodity Small-zone ZNS SSDs"
authors: [Inhwi Hwang, Sangjin Lee, Sunggon Kim, Hyeonsang Eom, Yongseok Son]
venue: ATC
year: 2025
tags: [file-system, zns-ssd, log-structured, f2fs, storage]
source_pdf: "[[atc2025-hwang.pdf]]"
source_md: "[[atc2025-hwang]]"
---

# Z-LFS: A Zoned Namespace-tailored Log-structured File System for Commodity Small-zone ZNS SSDs (ATC 2025)

> **一句话总结**：基于「ZNS 上 LFS metadata 生命周期与 segment 对齐」这一观察，Z-LFS 用 append-only metadata + 按写入热度推测分配 active zone + die/channel 冲突感知 superzone 分配，在单机 commodity small-zone ZNS SSD 上相对 F2FS(+CNS) 最高 33.44×、相对 eZNS+F2FS 最高 3.5×，且无需额外 CNS SSD。

## 问题与动机

[[ZNS-SSD]] 把物理地址空间切成固定大小 zone，要求 zone 内顺序写、显式 RESET 才能重用，并把 [[Garbage-Collection]] 等数据管理责任上移到 host。这能降低 SSD 内部 DRAM、over-provisioning 和 log-on-log 问题，但让传统面向 CNS SSD 设计的文件系统难以直接部署。

作者 claim 的核心痛点是：成熟 [[Log-Structured-File-System]]（以 [[F2FS]] 为代表）虽可做 out-of-place 更新，却在 commodity small-zone ZNS SSD 上遭遇三类结构性失配：

1. **Metadata 原地更新依赖 CNS SSD**：F2FS 把 metadata 放在块对齐、固定位置并原地更新，以缓解 wandering tree 问题。ZNS 禁止 zone 内随机写，因此 F2FS 通常需要额外 CNS SSD 承载 metadata，抬高存储系统成本，也无法把 ZNS SSD 当 standalone 设备使用。简单把 metadata 改成 zone 粒度双 zone 交替写，在随机更新场景下性能可下降 9.32×、写入量增 7.8×（论文 preliminary）。
2. **Active zone 利用率极低**：F2FS 的六路 hot/warm/cold × data/node 日志流各绑一个 zone，最多只用 6 个 active zone；而评测用 Samsung PM1731A 类 small-zone 设备最多支持 384 个 active zone。静态把 active zone 均分给六路日志流又会在 workload 偏斜时浪费 zone、饿死热点流。
3. **Zone 与内部资源冲突**：small-zone 设备中每个 zone 通常映射到单一 die/channel；即使 host 开了多个 active zone，若它们落在同一 channel 或 die，zone-level parallelism 仍会被内部争用吃掉（channel 冲突约 -19%，die 冲突 >50%）。

已有 [[eZNS]] 等 ZNS interface 通过 logical zone（v-zone）弹性分配 active zone，但与 F2FS 缺乏跨层感知：F2FS 仍把每个 v-zone 当普通 zone 只绑一路日志流，eZNS 也按 v-zone 是否发生写而非写入强度分配 active zone。论文因此主张在 **文件系统层** 做 ZNS-tailored 设计，纯软件、不改 commodity 设备，目标同时提升成本效率与 small-zone 并行度。

## 关键观察 / 隐含假设

- **观察 1**：在 ZNS 约束下，LFS segment 一旦写完便不可原地修改，只能 invalidate 后等 GC 擦除；因此部分 metadata（如 segment summary）与 segment 同生命周期，写一次后不再更新。
  - **依赖假设**：workload 以 out-of-place segment 更新为主，且 immutable metadata 类型划分（SS vs SIT/NAT）与 F2FS 语义长期稳定。
  - **可能失效场景**：若未来 LFS 在 ZNS 上引入类似 slack space recycling 的 segment 内复用，immutable/mutable 边界会模糊；或 metadata 类型扩展后分类规则需重做。

- **观察 2**：small-zone ZNS SSD 的峰值吞吐强烈依赖 active zone 数量与请求大小——128KB 写可在 128/256 active zones 饱和到约 2.4 GB/s，但 4KB/2MB 在 128 zones 时分别只有峰值的 20%/47%；同时 die/channel 映射呈周期性冲突点（zone ID 为 16/128 倍数）。
  - **依赖假设**：评测设备的 16 channel × 128 die、round-robin zone 映射模型可推广到其他 commodity small-zone 产品；host 能通过足够并发把 I/O 摊到多 zone。
  - **可能失效场景**：不同厂商 zone 拓扑、active zone 上限、或请求大小分布与 FIO/Filebench 设定差异大时，$A_{peak}$ 与 superzone/IG 组织需重标定。

- **观察 3**：F2FS 的 data 与 node 日志流通常不同时写入——node 流主要在 checkpoint 期间活跃，此时 data 流会被阻塞。
  - **依赖假设**：checkpoint 与 data 写互斥的时序在 Linux F2FS 路径上成立，且该行为在 Z-LFS 改造后仍保持。
  - **可能失效场景**：若并发 metadata/data 写路径变化、或多租户下交错 checkpoint，则 data/node 共用 IG 分配表可能产生 die 冲突，削弱 conflict-aware 策略收益。

- **假设 1**：workload 的日志流写入强度在短时间窗内可被比例配额较好地近似，且动态 scale-up/down 的开销低于静态错配带来的带宽损失。
  - **证据强度**：**中**——active zone scaling ablation 在三阶段 hot/warm/cold 随机写下接近各阶段最优静态方案，但仅 300s、单租户、合成偏斜。

- **假设 2**：为 standalone ZNS 部署接受 delta log + merge 的额外空间与内存缓冲，换取去掉 CNS SSD 的 TCO 收益。
  - **证据强度**：**强**——metadata 总空间开销约 0.02% 容量，WAF 与 F2FS_SS 相近；但内存 额外 250–380MB，论文未与「CNS SSD 成本」做端到端 TCO 量化。

## 核心方法

Z-LFS 在 [[F2FS]] 基础上实现三大策略，对应上述观察。

**Strategy #1：生命周期分化的 append-only metadata**。Immutable metadata（如 SS）直接 append 到 segment 末尾，随 segment GC 一并清理，无需 metadata GC 或位置追踪。Mutable metadata（SIT、NAT）走 delta logging：checkpoint 时只把变更 entry（带 table 内 pos）写入 delta log 区的双 zone 循环日志；日志区满一半触发异步 merge，把 delta 合并到 merge 区的 metadata table 对（交替有效侧），再 RESET 日志 zone。SIT 与 NAT 各自独立的 delta log、merge 区和内存缓冲，避免快变 SIT 拖慢 NAT merge。该设计直接回应「ZNS 上 segment 不可原地改」观察，使 ZNS SSD 可 standalone 承载全部 metadata。

**Strategy #2：推测式日志流管理（speculative log stream management）**。六路日志流保留 F2FS 温度分类。全局维护 active zone pool；对 data 流与 node 流分别计算可用配额 $A = \min(A_{peak}, A_{avail}/2)$，再按时间窗内写入量比例分配 $A_i = A \times W_i / W_T$。高强度流从 pool scale-up superzone，低强度流 scale-down 并后台 FINISH zone。Segment 切成 subsegment 散布到 superzone 内多 zone，既满足 zone 内顺序写，又提高并行。该设计回应「六路静态绑 zone 浪费 small-zone 并行度」与「workload 偏斜」观察。

**Strategy #3：冲突感知 zone 分配**。按 channel 数把连续 zone 组成 superzone；映射同一 die 的 superzone 组成 interference group（IG）。为 data/node 流维护独立 IG 分配表，优先从尚未占用的 IG 选 superzone，避免同流写到重叠 die；IG 耗尽时才 fallback 到重叠 IG。利用「data/node 不同时写」观察，避免不必要的 IG 互斥。该设计回应 §3.2 的 channel/die 冲突测量。

**Crash consistency**：沿用 F2FS roll-back/roll-forward；mutable metadata 通过 log version 与 checkpoint version 比较恢复有效 delta；崩溃后重建 active zone pool（对 closed zone 发 FINISH），不恢复运行时 zone 分配状态。实现基于 Linux 5.17.4 kernel F2FS 改造。架构与恢复细节见 [[atc2025-hwang]] / [[atc2025-hwang.pdf]]。

## 设计取舍

- **Immutable/mutable 硬分类 vs 通用 append-only metadata**：把 SS 绑死在 segment 尾部，换取无需 metadata 位置索引与 metadata GC；代价是 metadata 布局与 F2FS 假设深度耦合，换文件系统或 metadata 类型需重新分类。
- **Delta log + 内存缓冲 vs 纯日志式 metadata**：合并 delta 到固定 merge table，避免「metadata 的 metadata」追踪链；代价是 checkpoint/merge 路径更复杂，峰值内存比 F2FS 高 3%–38%（绝对值 +250–380MB），且 merge 异步仍可能在高压下影响尾延迟（论文未细拆 merge stall）。
- **动态 active zone 配额 vs 静态条带（F2FS_SS）**：按强度分配 superzone 可让热点流用到 128 zones；代价是 FINISH/RESET、IG 簿记和 speculation 错误时的 scale 抖动，实现与调试复杂度显著高于静态方案。
- **Superzone/IG 静态拓扑 vs 设备抽象**：按 16 channel / 128 die 硬编码组织，换设备需重新建模；收益是 host 侧零设备改动、部署简单。
- **边界条件**：在 small-zone、多线程、偏斜写、4KB 主导的应用下设计最优雅；large-zone ZNS（intra-zone 并行已够）、单日志流 LFS（speculation 收益有限）、或需要 in-place metadata 更新的场景下，部分策略收益下降（作者 §5 亦承认）。

## 实验与结果

**Setup**：i7-13700K / 32GB RAM；Samsung PM1731A 类 ZNS SSD（40704 zones × 96MB，max 384 active zones）+ 对等 CNS SSD；Linux 5.17.4。对比 F2FS(+CNS)、F2FS_SS(+CNS)、[[eZNS]]、eZNS+F2FS(+CNS)、[[ZenFS]]（RocksDB 用例）、Raw/eZNS 裸设备。

- **微基准（FIO 16 线程，FS 路径 4KB）**：顺序/随机写吞吐 vs F2FS 最高 **12.4×/25.2×**，vs F2FS_SS **+47%/+30%**；vs eZNS+F2FS 随机写 **3.5×**；顺序读 **+50%**（vs F2FS）。
- **尾延迟（随机写）**：平均延迟 24.5µs（F2FS 626µs）；P99.9 **45.3µs**（F2FS 47ms，eZNS+F2FS 39ms）。
- **MDtest 百万文件创建**：vs F2FS **27.7×**，vs F2FS_SS **11.4×**，vs eZNS+F2FS **1.6×**。
- **GC 压力（150GB 分区预填 128GB 后随机写 10min）**：吞吐 vs F2FS **3.3×**。
- **Filebench**：varmail 最高 **33.44×**（vs F2FS）；fileserver **7.21×**；videoserver **13.7×**；webserver 读为主仍 **2.09×**。
- **RocksDB db_bench**：fillseq/fillrandom/overwrite vs F2FS 最高 **25.0×/9.28×/9.01×**；vs eZNS+F2FS **1.27×–1.55×**；readrandom 与基线相近。
- **开销**：metadata 空间开销 **0.02%**；WAF 与 F2FS_SS 相当；active zone scaling ablation 在三阶段 hot/warm/cold 下接近各阶段最优静态分配。

## Critical Analysis

### 论证链条

观察链较完整：ZNS segment 不可原地改 → metadata 生命周期分化 → append-only 去 CNS 依赖；microbenchmark 证明多 active zone 与避免 die/channel 冲突对 small-zone 设备关键 → speculative quota + superzone/IG 直接作用于 F2FS 的六路日志流瓶颈；实验从 raw device → FS 微基准 → GC/metadata → Filebench → RocksDB 逐级验证。薄弱环节在于：**standalone 成本主张**主要靠「不需要第二块盘」定性论证，缺少与真实部署（小容量 CNS 缓存盘、云盘定价）的 TCO 对比；**对 eZNS 的公平性**部分来自 F2FS 语义不匹配而非 eZNS 本身失效，3.5× 的「interface SOTA」结论绑定在「必须用 F2FS 类 LFS」前提下。

### 假设压力测试

- **Workload 偏斜稳定性**：配额按时间窗比例调整；突发短周期热点（秒级）可能导致 speculation 滞后，论文 100s 相位实验偏长，未测快速抖动。
- **请求大小分布**：峰值 $A_{peak}$ 标定于 128KB 附近；若生产以 4KB 随机写为主，多 zone 收益可能低于 microbenchmark 外推（§3.1 已显示 4KB 多 zone 效率低）。
- **设备拓扑泛化**：superzone=16 zones、8 IG 来自单一 Samsung 设备；其他 zone 容量/通道数不同的 ZNS 需重配，论文未提供自动探测。
- **多租户与 QoS**：作者明确仅 single-tenant 评测；多租户下 IG/zone 池与 fairness 未验证——**论文已承认**，需 I/O scheduling/rate limiting 扩展。

### 实验可信度

- **Benchmark 代表性**：Filebench/RocksDB 覆盖常见存储场景，但均为单机合成负载；缺少 cloud block trace 或长期 aging。
- **Baseline 强度**：包含 F2FS_SS 与 eZNS+F2FS 较完整；F2FS 依赖 +CNS SSD 使其在 standalone ZNS 场景本身不利，放大了 Z-LFS 收益倍数。ZenFS 在 RocksDB 评测仍用 CNS 支持 log/lock in-place 更新，与 Z-LFS standalone 目标不完全同构。
- **Ablation**：active zone scaling vs 多种静态方案较有说服力；metadata 三分策略（immutable append / delta / conflict-aware）缺少独立开关消融。
- **Metric 覆盖**：吞吐与 P99.9 写延迟较全；读尾延迟、merge/checkpoint 延迟、恢复时间、CPU 开销论文未系统报告。

### 系统性缺陷

- **崩溃恢复**：重启后丢弃 active zone 分配状态并 FINISH closed zones，恢复后需重新 warm-up zone 并行，大规模部署的 recovery 时间论文未讨论。
- **可观测性/运维**：superzone、IG、quota 动态变化使性能调优与故障定位比静态 F2FS 更难；论文未讨论 tracing 接口。
- **隔离性**：单租户设计无 tenant 级 zone 预算；与 [[eZNS]] 强调的 performance isolation 形成反差。
- **兼容性**：深度绑定 F2FS metadata 布局与 Linux 5.17.4；上游 F2FS 演进可能带来 merge 成本。论文未讨论双盘（ZNS+CNS）混合降级路径。

## 局限与 Future Work

- **局限 1（论文承认）**：仅在 **single-tenant** 环境评估；multi-tenant fairness、burst 写与性能隔离未验证。
- **局限 2（论文承认）**：**large-zone ZNS** 上 speculative log stream 与 conflict-aware 收益有限，因设备已在 zone 内提供更高并行；append-only metadata 仍可用。
- **局限 3（论文承认）**：**单日志流 LFS** 无法从 speculative 跨流配额获益，只剩 metadata 与冲突感知策略。
- **局限 4（可从实验边界推出）**：缺少 metadata merge、checkpoint、FINISH zone 对 **尾延迟** 与 **recovery time** 的系统测量；长期运行下的 zone 碎片化与 GC 交互未知。
- **Future work 1**：在 Z-LFS 内集成 tenant-aware I/O scheduling / rate limiting（借鉴 [[eZNS]]、PAIO），用 multi-tenant Filebench 或生产 trace 量化 fairness–吞吐折中。
- **Future work 2**：自动探测 ZNS zone→channel/die 映射并生成 superzone/IG 拓扑，避免 per-device 硬编码。
- **Future work 3**：对 4KB-heavy、checkpoint-heavy、fsync-heavy 等边界 workload 做 speculation 时间窗与 merge 触发阈值的 sensitivity study，并补齐三分策略的独立 ablation。

## 相关

- **相关概念**：[[Log-Structured-File-System]]、[[Garbage-Collection]]、[[ZNS-SSD]]、[[F2FS]]
- **同类系统**：[[eZNS]]、[[ZenFS]]、[[ZoneFS]]、ZNS+、F2FS_SS
- **同会议**：[[ATC-2025]]
- **对比**：Z-LFS 在文件系统层内嵌 zone 配额与冲突感知，相对 device/interface 层 [[eZNS]] 强调与 LFS 日志流语义同层协同；相对 [[ZenFS]] 面向通用 kernel FS 而非单一 LSM 后端