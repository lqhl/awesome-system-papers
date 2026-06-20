---
type: paper
name: LogCrisp
full_title: "LogCrisp: Fast Aggregated Analysis on Large-scale Compressed Logs by Enabling Two-Phase Pattern Extraction and Vectorized Queries"
authors: [Junyu Wei, Guangyan Zhang, Junchao Chen, Qi Zhou]
venue: ATC
year: 2025
tags: [log-analysis, log-storage, compression, simd, vectorization, partial-decompression]
source_pdf: "[[atc2025-wei.pdf]]"
source_md: "[[atc2025-wei]]"
---

# LogCrisp: Fast Aggregated Analysis on Large-scale Compressed Logs by Enabling Two-Phase Pattern Extraction and Vectorized Queries (ATC 2025)

> **一句话总结**：观察到 log variable fragment 边界 >98% 由 NAU 字符决定，因而把 pattern 解耦为 offline Sketch（全局结构）+ online Spec（局部过滤细节）两阶段抽取，并用 AVX SIMD 把 prefix/suffix 全文查询转为 range/point 查询以兼容整数编码；在 13 类近 7TB 日志上分析比 [[CLP]] 快 15.32×、比 [[LogGrep]] 快 4.65×，ingestion 最高快 3.8×，压缩率与 SOTA 基本持平。

## 问题与动机

云厂商日志日增量可达 PB 级，且常需保留 180 天用于审计。运维与安全场景普遍需要对压缩日志做 **aggregated analysis**（counting、sum、max/min 等），而不是只做 keyword grep。现有 **pattern-based log storage** 把变量按 pattern 切成 fragment 再编码压缩，既能高压缩率，又能用 pattern 过滤无关 unit，避免全量解压。

但作者在 Introduction 指出两个**根本矛盾**，也是 [[CLP]]（global pattern）与 [[LogGrep]]（local pattern）长期 trade-off 的根源：

1. **全局描述 vs 过滤效果**：global pattern 跨 block 共享、描述粗（如 `blk_<all,10>`），过滤弱，分析时常需解压更多 unit——prior work 称 global 方法分析延迟可比 local 方法高 10×；local pattern 每 block 精细（如 `blk_<hex,3>_<num,2>`），过滤强，但缺乏跨 block 的全局 fragment 位置描述，难以做跨 block 聚合，且 ingestion 需每 block 完整 pattern extraction，比 [[CLP]] 慢 2–5×。
2. **数值编码 vs 全文查询语义**：为压缩率与算术聚合，纯数字 fragment 需编码为整数；但日志本质是文本，prefix/suffix 查询（如 `blk_4FF_3*`）与整数编码天然不兼容。[[LogGrep]] 对数值 unit 退化为普通文本查询；[[CLP]] 则无法对数值 fragment 做向量化聚合。

作者 claim：若能把「全局结构」与「局部过滤细节」解耦，并在整数编码上直接执行向量化 prefix/suffix 查询，就能同时获得 global 方法的跨 block 聚合能力、local 方法的过滤效率，以及数值 unit 的 SIMD 加速——这正是 LogCrisp 的设计目标。论文与作者前序 [[LogGrep]]、FAST'21 parser feasibility 工作一脉相承，面向阿里云生产 + 公开 benchmark 的大规模压缩日志分析。

## 关键观察 / 隐含假设

- **观察 1：local pattern 的 fragment 边界高度集中于非字母数字（NAU）字符。** 从 7 类日志、3,259 个 [[LogGrep]] local pattern 中统计 11,954 个边界，>98% 为 NAU（Tab. 2；Hadoop 97.37%，OpenStackC 100%）。这使「仅用 NAU 字符刻画全局结构」在统计上可行。
  - **依赖假设**：目标日志的 semi-structured 变量仍主要由 `_`、`.`、`/` 等分隔符切分；pattern extraction 方法（Drain、LogZip 等）继续以 NAU 为切分启发式。
  - **可能失效场景**：用户自定义格式、无固定分隔符的 free-text 变量、或 delimiter 全为字母数字时，Sketch 会退化或多义，outlier 比例上升。

- **观察 2：数值 unit 占比高且决定分析路径。** 7 类日志 15,402 个 unit 中平均 53% 为纯数字，占压缩空间约 60%（部分日志 >80%）。整数编码 + 向量化查询的收益与 workload 中数值查询比例强相关。
  - **依赖假设**：生产分析大量涉及 chunk ID、字节数、IP 段等可整数化的变量；prefix/suffix 查询主要落在这些数值 unit 上。
  - **可能失效场景**：查询集中在常量字符串、混合字母数字 unit，或语义相近但数值编码反而更占空间的 Hadoop 类 workload（论文称 LogGrep 在 Hadoop 压缩率高 16%）。

- **观察 3：Sketch 由 NAU 决定，但 NAU 并不总是边界（观察非双向）。** 同一 local pattern 下的变量值可能对应多个 Sketch，需 Sketch warehouse + 64-bit fingerprint 索引，main/backup Sketch 分流存储。
  - **依赖假设**：offline training 用 1% 采样即可达 >99% Sketch 匹配率；miss rate 超 5% 时重训可维持精度。
  - **可能失效场景**：生产日志格式漂移更频繁（LogA 需 6 次重训 vs Hadoop 3 次）；Windows 等 Sketch warehouse 较大时压缩率可降 9%。

- **假设 1：prefix 查询可通过 squeezing range 定理转为向量化 range 查询。** 对 b 为 2 的幂且 b<10，每个整数属于唯一 squeezing range `[b^(m-1), b^m)`，且其中至多包含一个 compared range；实现选 b=8，用 AVX shift + conditional blending 批量加载 queried range。
  - **证据强度：强（算法层面）/ 中（端到端）。** Ablation 显示 point/prefix/suffix 分别快 1.46×/1.50×/1.22×；但 suffix 的 modulo 本身未向量化，论文留作 future work。

- **假设 2：预提取 Sketch 后可用 cacheline-aligned 预分配 metadata 显著加速 ingestion，且不必牺牲过滤精度。**
  - **证据强度：强。** 相对 tree-based metadata（仿 LogGrep），cache-friendly 设计 ingestion 快 6–43%（均 19%）；two-phase extraction 相对纯 global pattern 分析快 2.59×（最高 5.55× on Spark）。

## 核心方法

LogCrisp 约 15,000 行 C++，workflow 分 Training → Compression → Analysis 三阶段（Fig. 5）。深度实现见 [[atc2025-wei]]。

### Two-phase Pattern Extraction（Sketch + Spec）

核心是把 pattern 内消息**显式解耦**：

- **Sketch（offline）**：只保留 fragment 边界信息，如 `blk_4ff_34` → `<*>_<*>_<*>`。offline 从样本集提取全部 Sketch，合并入 **Sketch warehouse**，最常见者为主 Sketch，其余为 backup；64-bit fingerprint + hash 索引加速 ingestion 匹配。
- **Spec（online）**：ingestion 时按 Sketch 定位 fragment 后，piggyback 提取常量字符（如 `blk`）、类型消息（hex/num，6-bit 向量）、长度消息（最大 fragment 长）。不同 log block 可对同一 Sketch 有不同 Spec，从而保留 local 过滤精度。

**多 Sketch 处理**：不同 Sketch 的 fragment 存于不同 unit；main Sketch unit 用 placeholder（负序号）记录 backup Sketch 值的 ingestion 顺序，供分析时回溯。不匹配任何 Sketch 的 entry 记为 outlier。

**过滤逻辑**：分析时若指定 fragment，直接聚合对应 unit；否则组合 Sketch+Spec 重建 pattern 做 keyword 匹配（延续 [[LogGrep]] 思路）。含 NAU 的查询串可先用 Sketch 定位，过滤效果随查询类型波动更大（Fig. 11）。

### Cache-friendly Ingestion（§3.3）

Sketch 预提取使 unit 数量与结构可预知：metadata 连续预分配，fragment position 以 64-byte cacheline batch 存储（7 个 offset-length pair + next pointer），压缩器单次访存可取 7 个连续 position。相对 [[LogGrep]] 的 hash/tree 动态索引，减少 ingestion 路径上的指针追逐。

### Vectorized Query Processing（§4）

**Prefix query**：将 `502*` 类查询转为 compared range（如 `[502000,503000)`）。对每个编码整数，用 SIMD 右移求 squeezing range，查表得 compared range，`_mm256_blendv_epi8` 装入寄存器后做向量化 range 比较。16 个 YMM 寄存器缓存备选 range，减少重复加载。

**Suffix query**：转为 modulo point query（如 `*502` → `% 1000 == 502`），modulo 未向量化但 point 查询已向量化；论文称性能仍不低于 plain string 路径。

**Indexed Bitmap 向量化构建**：沿用 prior work 的 indexed bitmap（bitmap + index array），用 AVX shuffle（`_mm256_permutevar8x32_epi32`）把 hit 位置移到数组前端，配合 scatter/gather 加速多 unit 查询合并；对稠密结果查询（Q1/Q3/Q5）latency 可再降 1.4–2×。

### 存储与查询接口

- **压缩**：数值 unit → integer vector + zstd；其他 → string vector；Spec 与压缩 unit 打包为 zipped file。
- **查询**：支持 grep-like 全文查询与 designated unit 查询；counting、point、prefix/suffix 两模式均支持；sum/min/max、range query 需 designated unit。
- **Training**：用 [[LogGrep]] parser 提取 output statement；1% 采样训练 Sketch，训练开销约为压缩时间的 5–10%。

## 设计取舍

- **NAU 启发式 vs 完备边界推导**：收益是 offline 可轻量提取全局 Sketch、ingestion 无需每 block 完整 pattern matching；代价是观察非双向，需 warehouse/outlier/backup 机制，Windows 等场景压缩率略降。
- **整数编码 + SIMD vs 字符串保真**：收益是 53% 数值 unit 上更高压缩与算术聚合、prefix 查询 1.5× 加速；代价是 Hadoop 等「语义相近数字」场景整数编码反而更占空间，且 suffix modulo 尚未向量化。
- **Sketch 全局 + Spec 局部 vs 纯 global/local**：收益是同时有 global description 与 local 过滤（Spark 分析 5.55×于 LC-global）；代价是系统复杂度显著高于 [[CLP]]，且需周期性 retraining。
- **单线程 ingestion 为主**：除 6TB 级 LogF 用 8 线程外均单线程评测；收益是结果可解释；代价是未展示多线程 ingestion 与 query 的资源隔离、尾延迟。
- **Baseline 公平性**：与 [[LogGrep]] 均改用 zstd；[[CLP]] 因生产环境自研 OS 不兼容未在阿里云日志上对比——生产场景结论仅相对 LogGrep。

## 实验与结果

- **规模**：13 类日志、近 7TB（LogHub 4 类 + CLP 开源 4 类 + 阿里云生产 6 类）；22/28 条生产/公开查询串覆盖各执行路径。
- **分析延迟**：相对 [[CLP]] 平均 **15.32×**（open 4.03–40.11×，Windows 最高 40.11×因变量少、global index 过滤弱）；相对 [[LogGrep]] 平均 **4.65×**（open 4.30–10.90×，Hadoop 10.90×因大量整数 unit；生产 2.50–7.27×，均 5.07×）。
- **Ingestion**：相对 LogGrep 最高 **3.8×**（生产 LogA 69.79 vs 23.93 MB/s），open 均快 2.43×；相对 CLP 为均 95% 速度，Thunderbird/HadoopL 上反超最高 1.61×。
- **压缩率**：相对 CLP 约 **1.11×**（即 CLP 略优）；相对 LogGrep 约 **96%**；Hadoop LogGrep 优 16%，OpenStackC/Windows CLP 优 20–33%。
- **Ablation**：two-phase vs LC-global 分析 2.59×；cache-friendly ingestion +19%；Int-encoded vs Str-encoded point/prefix/suffix 1.46×/1.50×/1.22×；Int+Shuffle indexed bitmap 对稠密查询 1.4–2×。
- **Training**：1% 采样 miss rate 可接受；Hadoop 16GB 重训 3 次、LogA 18GB 重训 6 次（生产格式漂移更频）。

## Critical Analysis

### 论证链条

论文链条闭合度较高：**测量证明 global/local pattern 两极各有硬伤**（Fig. 1 + LogGrep/CLP 引用）→ **NAU 边界统计支撑 Sketch 最小全局描述**（Tab. 2）→ **Sketch+Spec 两阶段同时服务过滤与聚合**（Fig. 3, §3.2 ablation）→ **squeezing range 定理打通整数编码与 prefix 全文语义**（§4.1 证明 + Fig. 6）→ **7TB 上三维指标同时优于或持平 SOTA**（Tab. 5）。

薄弱跳步在于：把「首次向量化 aggregated analysis on compressed logs」的 claim 主要建立在 AVX2 实现与 Hadoop 类数值密集日志上，对字符串主导、range query 少、或 Sketch warehouse 膨胀的 workload，链条后半段增益会缩水。作者也承认 Windows 上 CLP 因「条目高度重复 + 变量极少」反而更优，说明方法并非普适 dominate，而是针对「变量多、需精细过滤、数值查询密集」的 cloud log。

### 假设压力测试

- **Log 格式稳定性**：生产 LogA 重训频率是 Hadoop 2×，说明 Sketch warehouse 维护是长期运维成本；论文未给出自动化触发、多租户格式并存时的 warehouse 管理策略。
- **查询分布**：评测以 counting + grep-like 全文查询为主（因 LogGrep 不支持 designated unit）；真实 SIEM 中复杂 range/join、多变量关联聚合的覆盖有限。
- **硬件绑定**：AVX2 SIMD 是核心加速来源；ARM cloud、无 AVX 环境或更新 ISA（AVX-512）下的性能与可移植性论文未测。
- **Parser 依赖**：Training 复用 [[LogGrep]] parser 与 output statement；parser 错误会级联到 Sketch/Spec，论文未量化 parser quality 对 outlier 率的影响。
- **已证明 vs 推断**：「order of magnitude lower latency」在 abstract 与 evaluation 平均 15.32×/4.65× 一致；但单日志类型上 CLP 在压缩率/ingestion 仍可能更优，不能外推为全面碾压。

### 实验可信度

- **Benchmark 代表性**：7TB 含 6TB 级单类生产 LogF，规模真实；但 CLP 缺席生产对比，生产结论只有 LogGrep 一条基线，且 LogGrep 与 LogCrisp 同源团队，需关注实现公平性（虽已统一 zstd）。
- **Baseline 强度**：CLP（OSDI'21）与 LogGrep（EuroSys'23）确为 pattern-based [[Partial-Decompression]] SOTA；未与 [[ElasticSearch]]/Splunk 等未压缩方案比 storage cost，符合论文问题设定。
- **Ablation 充分**：§6.2 对两阶段提取、cache ingestion、整数编码、shuffle bitmap 四类技术均有独立版本，能支撑设计分解。
- **Metric 缺口**：未报告 query 尾延迟分布、并发查询、ingestion 与 analysis 资源竞争、outlier 比例对分析正确性的影响；正确性仅隐含于与 baseline 同语义查询对比。

### 系统性缺陷

- **Outlier 路径**：Sketch miss 的 entry 单独存储，论文未讨论 outlier 累积后对压缩率、查询需全扫比例的上界。
- **可观测性与运维**：retraining 触发（miss rate >5%）、Sketch warehouse 版本与已压缩 block 的兼容性、多 log type 并存时的配置管理——论文未讨论。
- **故障恢复**：zipped block 损坏、warehouse 与存量数据不一致时的恢复策略未涉及。
- **隔离与多租户**：单线程 ingestion 评测为主，未讨论多 tenant 日志混存时的 pattern 隔离与安全。
- **尾延迟**：breakdown（Fig. 10）显示 point/suffix 在 pattern matching 上耗 0.84–1.12s，prefix/range 仅 0.03s；不同查询类型延迟差异大，生产 SLO 下需按查询类分别评估。

## 局限与 Future Work

- **局限 1**：NAU→Sketch 启发式非双向，需 backup Sketch/outlier 机制；Windows 等 warehouse 较大日志压缩率可降约 9%（§6.2）。
- **局限 2**：Training 与格式漂移绑定，生产日志重训更频繁；training 本身占压缩时间 5–10%，对短窗口日志不友好。
- **局限 3**：suffix query 的 modulo 未向量化；range/sum 等聚合需 designated unit，接口能力弱于全文 grep 模式。
- **局限 4**：[[CLP]] 未在生产 OS 上评测，跨方案「三维同时最优」的 claim 在 production 上仅相对 LogGrep 成立。
- **Future work 1**：向量化 suffix modulo，量化能否缩小 LogCrisp 在 prefix/suffix 上相对 point/range 的性能差距（§4.1 自述）。
- **Future work 2**：在格式高度动态、少 NAU 分隔的日志上测量 outlier 率与 warehouse 膨胀曲线，明确需退回 local-only 或 hybrid parser 的阈值。
- **Future work 3**：多线程 ingestion + 并发查询下的吞吐/尾延迟与 Sketch warehouse 热更新一致性，验证能否保持单线程评测中的 4–15× 分析优势。

## 相关

- **相关概念**：[[Partial-Decompression]]、[[SIMD]]、[[Log-Parsing]]、[[Indexed-Bitmap]]、pattern-based compression、aggregated log analysis
- **同类系统**：[[CLP]]、[[LogGrep]]、[[ElasticSearch]]、LogArchive、LogZip、[[Loom-SOSP25]]（高频 telemetry 存储，问题设定不同）
- **同会议**：[[ATC-2025]]
- **对比**：相对 [[CLP]]，LogCrisp 用 Sketch+Spec 换取更强 unit 过滤与数值 SIMD，牺牲部分极简 global pattern 场景（Windows）的压缩/ingestion 优势；相对 [[LogGrep]]，补上 global description 与跨 block 聚合，ingestion 快 2–3.8×，分析快 4–10×