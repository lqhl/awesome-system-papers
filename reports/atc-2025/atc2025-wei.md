# LogCrisp: Fast Aggregated Analysis on Large-scale Compressed Logs by Enabling Two-Phase Pattern Extraction and Vectorized Queries

**作者**：Junyu Wei, Guangyan Zhang, Junchao Chen (Tsinghua University); Qi Zhou (Alibaba Cloud)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wei
**源文件**：[[atc2025-wei.pdf]]

---

## 一、背景

大型云服务商每天产生 PB 级别的系统日志，这些日志需要保留较长时间（如 180 天）用于审计。为了降低存储成本，现有日志存储系统普遍采用基于 pattern 的压缩方法：提取日志中的模式，将变量值拆分为 fragment 并进行编码压缩。同时，日志上的聚合分析（counting、summation、max/min）对于错误诊断、安全攻击检测和用户行为分析至关重要。

现有方法分为两大类：
- **Global-pattern-based**（如 CLP）：预定义全局 pattern，所有 log block 共享。优点是提供全局描述、支持聚合分析；缺点是 pattern 过于笼统，过滤效率低，分析延迟高。
- **Local-pattern-based**（如 LogGrep）：为每个 log block 单独提取局部 pattern。优点是 pattern 精确、过滤效率高；缺点是缺乏全局描述，只能做 grep-like 关键词搜索，且 ingestion 速度慢（比 CLP 慢 2-5×）。

---

## 二、要解决的问题

在高度压缩的日志上执行聚合分析存在两个根本性挑战：

1. **全局描述与过滤效率的两难**：全局 pattern 能提供跨 log block 的统一描述，支持聚合操作，但太笼统导致过滤效率差（分析延迟高达 10×）；局部 pattern 过滤效率高，但缺乏全局描述，无法支持高效聚合。

2. **数值编码格式与全文查询语义的不兼容**：约 53% 的 unit 是纯数值型，编码为整数可提高压缩率并支持向量化算术聚合。但日志本质是文本格式，实际分析中需要对数值变量执行前缀/后缀查询（如查找以 "3" 开头的 block number），这与整数编码格式天然不兼容。现有方法要么将数值 unit 存为字符串（放弃向量化优势），要么在查询时将整数转回字符串（额外开销）。

---

## 三、洞察与设计

**关键洞察**：日志 pattern 中的消息可以被清晰地解耦为两部分——全局共享的结构信息（Sketch）和局部定制的细节信息（Spec）。通过对 7 种日志类型中 3,259 个局部 pattern 的 11,954 个 fragment 边界的统计分析，发现超过 98% 的 fragment 边界是非字母数字（NAU）字符。这意味着仅通过 NAU 字符就能以极高的准确率定位 fragment 边界，从而在离线阶段提取出足够的全局结构信息。

### Two-Phase Pattern Extraction

基于上述洞察，LogCrisp 将 pattern 提取分为两个阶段：

- **Off-line 阶段（提取 Sketch）**：从日志样本中提取 Sketch——仅包含最少的全局结构消息（即 NAU 字符定义的 fragment 边界）。例如 pattern `blk_<hex,3>_<num,2>` 的 Sketch 为 `<*>_<*>_<*>`。由于同一变量可能对应多个 Sketch，系统维护一个 Sketch Warehouse，用 64-bit fingerprint 索引，最常见的 Sketch 作为 main Sketch，其余为 backup Sketch。

- **On-line 阶段（提取 Spec）**：在日志 ingestion 过程中，利用 Sketch fingerprint 匹配定位 fragment，同时 piggyback 提取 Spec 信息（常量字符、类型消息、最大长度）。不同 log block 的 Spec 可以不同，保留了局部定制能力。

### Vectorized Pre/Suffix Query

对于数值编码 unit 上的前缀/后缀查询，LogCrisp 将其转换为与整数编码兼容的 range/point 查询：

- **前缀查询 → Range 查询**：核心思路是为每个编码整数计算一个 "squeezing range" [bm-1, bm)（b 为 2 的幂且 b < 10，取 b=8）。论文证明当 b < 10 时，每个 squeezing range 至多包含一个 compared range。利用 AVX SIMD 的 shift、conditional blending、comparison 指令实现向量化处理。

- **后缀查询 → Point 查询**：判断编码整数对固定模数的余数是否等于查询后缀，相对简单。

### Vectorized Indexed Bitmap Construction

利用 AVX SIMD shuffle 指令向量化构建 Indexed Bitmap（记录中间查询结果），将 bitmap 中标记为 "1" 的位置索引高效聚集到数组前端。

---

## 四、实现细节

LogCrisp 使用约 15,000 行 C++ 代码实现，整体流程分为三个阶段：

**Training**：从日志样本（1% 采样率）中提取 output statement 和 Sketch。使用 LogGrep 的 log parser 识别 output statement。Sketch 通过 NAU 字符提取，存入 Sketch Warehouse 并用 hashing-based 索引加速查找。

**Compression**：
- 基于 output statement 解析日志变量
- 用 pre-extracted Sketch 定位 fragment
- Fragment 位置用 (offset, length) 对表示，按 64 字节（CPU cache line 对齐）批量存储，每批最多 7 个位置对 + 4 字节 next 指针
- 所有可能 unit 的 metadata 预分配在连续内存中，实现 cache-friendly 的 ingestion
- 数值 unit 编码为 integer vector，其余用 string vector，统一用 zstd 压缩

**Analysis**：
- Step 1: 匹配 output statement 定位查询变量
- Step 2: 结合 Sketch 和 Spec 过滤相关 unit
- Step 3: 在 integer-encoded unit 上执行向量化查询，在 string-encoded unit 上执行定长查询
- Step 4: 通过 Indexed Bitmap 执行后续查询并生成最终结果

支持的操作：counting、summation、min/max 聚合；point、prefix/suffix、range 查询。

---

## 五、实验结果

**测试环境**：
- Open logs: 2×Intel Xeon Silver 4210R (2.40GHz, 16 cores), 64GB RAM
- Production logs: 2×Intel Xeon E5-2682 v4 (2.50GHz, 32 cores), 188GB RAM

**数据集**：13 种日志类型，总计近 7TB，包括 LogHub 公开数据集、CLP 开放日志和阿里云生产日志。

**对比系统**：CLP（global-pattern-based SOTA）、LogGrep（local-pattern-based SOTA）

### 整体性能

| 指标 | vs CLP | vs LogGrep |
|------|--------|------------|
| 分析延迟 | 平均快 15.32×（4.03×–40.11×） | 平均快 4.65×（4.30×–10.90×） |
| Ingestion 速度 | 平均达 CLP 的 95% | 平均快 2.43×（生产日志最高 3.72×） |
| 压缩率 | 平均为 CLP 的 1.11× | 平均为 LogGrep 的 96% |

### 各技术贡献的消融实验

| 技术 | 效果 |
|------|------|
| Two-phase extraction | 分析延迟降低平均 2.59×，最高 5.55×（Spark）；ingestion 速度持平或提升（最高 7%） |
| Cache-friendly ingestion | Ingestion 速度提升 6%–43%（平均 19%） |
| Vectorized pre/suffix query | Point query 延迟降低 1.46×，prefix 1.50×，suffix 1.22× |
| Vectorized Indexed Bitmap | 额外降低延迟 1.4×–2×（对结果密集的查询效果显著） |

### Training 开销

- 1% 采样率下，training 时间占压缩时间的 5.9%–10%
- Hadoop（16GB）需 train 3 次，LogA（18GB 生产日志）需 train 6 次
- Sketch 匹配率超过 99%

---

## 六、批判性分析

1. **生产日志缺少 CLP 对比**：由于阿里云使用自研 OS 与 CLP 不兼容，6 种生产日志（含 6.1TB 的 LogF）完全没有 CLP 基线。这恰恰是数据量最大、最能体现实际价值的部分，读者无法判断 LogCrisp 相对 CLP 在真实场景中的全面表现。

2. **单线程 ingestion 的局限性**：除 LogF 外所有日志都使用单线程 ingestion，而 LogF 使用了 8 线程然后归一化到单线程。这种不一致的测试方法使得跨日志类型的 ingestion 速度比较不够严谨。更重要的是，现代日志系统通常都是多线程并行 ingestion，单线程性能的实际参考价值有限。

3. **Query string 的代表性存疑**：Open logs 仅 28 条查询字符串（"覆盖所有执行路径"），生产日志 22 条。查询字符串的选择显著影响分析延迟结果（如 Figure 11 所示 LogCrisp 的速度范围跨度极大），但论文未分析查询字符串的分布特征是否反映真实工作负载。

4. **Sketch 匹配率下降时的 graceful degradation 未充分讨论**：论文提到当匹配率低于 5% 时需要重新 training，但 Figure 9 显示生产日志 LogA 的 miss rate 可飙升至 70% 以上。在 miss rate 高企但尚未触发 retraining 的窗口期，系统性能如何退化？这是生产环境中的关键问题。

5. **NAU 边界假设的脆弱性**：98% 的 NAU 边界准确率看起来很高，但对于每天 PB 级日志来说，2% 的误判意味着大量 fragment 被错误分割。论文通过 backup Sketch 机制缓解，但未量化 backup Sketch 带来的额外存储和查询开销。

6. **后缀查询的向量化优化留作 future work**：后缀查询仅使用标量模运算，性能提升有限（1.22×），与前缀查询（1.50×）差距明显。这是一个已知的弱点，但论文未深入讨论其对整体性能的影响。

---

## 七、AI Infra / MLSys 视角

1. **日志分析对 AI 系统运维的价值**：大规模 AI 训练/推理集群产生海量日志，LogCrisp 的高效压缩分析能力可直接用于 AI Infra 的可观测性场景——如训练任务的错误诊断、GPU 利用率分析、推理请求的性能 profiling。

2. **Two-phase 解耦思想的可迁移性**：将全局结构信息与局部细节信息解耦的设计思路，可以迁移到 AI Infra 中其他需要平衡全局视图和局部精度的场景。例如分布式训练中的 communication pattern 分析、模型 serving 中的 request routing 决策等。

3. **SIMD 向量化在 AI 系统中的启发**：LogCrisp 将文本查询转换为与数值编码兼容的 range/point 查询的思路，对 AI 系统中的 metadata 管理有借鉴意义——如 KV cache 的 key 匹配、embedding lookup 的加速等场景。

4. **可跟进的方向**：
   - 将 LogCrisp 的模式应用于 AI 训练日志（如 NCCL 通信日志、CUDA error 日志）的实时分析
   - 结合 LLM 自动生成 output statement，替代人工定义或简单解析器
   - GPU 加速版本：将 SIMD 向量化查询扩展到 GPU，利用 AI 集群的空闲 GPU 资源加速日志分析

---

## 八、总结

LogCrisp 通过 two-phase pattern extraction 解耦了日志 pattern 中的全局结构（Sketch）和局部细节（Spec），同时获得全局描述能力和高过滤效率。在此基础上，通过将前缀/后缀查询转换为 range/point 查询，首次实现了在整数编码压缩日志上的向量化聚合分析。实验表明 LogCrisp 在分析延迟上比 CLP 快 15.32×、比 LogGrep 快 4.65×，同时保持可比的压缩率和 ingestion 速度。主要局限在于需要离线 training 阶段且生产日志中缺乏与 CLP 的完整对比。适用于需要在大规模压缩日志上执行频繁聚合分析的云服务场景。
