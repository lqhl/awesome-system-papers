---
type: paper
name: LogCrisp
full_title: "LogCrisp: Fast Aggregated Analysis on Large-scale Compressed Logs by Enabling Two-Phase Pattern Extraction and Vectorized Queries"
authors: [Junyu Wei, Guangyan Zhang, Junchao Chen, Qi Zhou]
venue: ATC
year: 2025
tags: [log-analysis, compression, simd, log-storage, vectorization]
source_pdf: "[[atc2025-wei.pdf]]"
source_md: "[[atc2025-wei]]"
---

# LogCrisp: Fast Aggregated Analysis on Large-scale Compressed Logs by Enabling Two-Phase Pattern Extraction and Vectorized Queries (ATC 2025)

> **一句话总结**：把 log 压缩 pattern 解耦为 Sketch（全局结构）+ Spec（局部细节）两阶段抽取，并用 AVX SIMD 把前缀/后缀全文查询转换为 range/point 查询，比 LogGrep 分析快 4.65×、ingestion 快 3.8×。

## 问题

云日志压缩需要兼顾压缩率、ingestion 速度、聚合分析延迟（counting/sum/max/min），但有两个根本矛盾：

- **全局描述 vs 过滤效果的两难**：global pattern（CLP）描述粗，过滤效果差；local pattern（LogGrep）每 block 一个 pattern 精细但缺乏全局描述，无法做跨 block 的聚合
- **数值编码 vs 全文查询语义**：53% 的 unit 是纯数字，编码成整数才能高效压缩和算术聚合；但日志本质是文本，前缀/后缀查询（如 `blk_4FF_3*`）天然不兼容整数编码

## 核心方法

1. **Two-phase Pattern Extraction**：观察到 11,954 个 fragment 边界中 >98% 是非字母数字 (NAU) 字符——offline 阶段只抽取 Sketch（NAU 边界，提供全局结构 `<*>_<*>_<*>`），online 阶段为每个 log block 抽取 Spec（具体常量字符 / 类型 hex|num / 长度），存到 Sketch warehouse；多 Sketch 用 64-bit fingerprint 索引；ingestion 时 cacheline-aligned 64-byte batch（7 个 position pair + next pointer）
2. **Vectorized Prefix/Suffix Query**：把 prefix 查询转成 range 查询。关键定理：给定 b（2 的幂且 < 10），任意整数都属于唯一 squeezing range `[b^(m-1), b^m)`，且每个 squeezing range 至多包含一个 compared range。先用 SIMD shift 算 squeezing range，再用 AVX 的 conditional blending 一次加载每个值的 compared range，向量化范围查询
3. **AVX shuffle 构建 indexed bitmap**：加速 unit 间合并和后续聚合

深度细节回 [[atc2025-wei]]。

## 关键结果

- 聚合分析延迟比 CLP 快 **15.32×**、比 LogGrep 快 **4.65×**
- Ingestion 速度比 LogGrep 快最高 **3.8×**
- 压缩率与 CLP 持平（约 1.1×），与 LogGrep 持平（约 96%）
- 13 类日志、近 7 TB 数据评测（含阿里云生产日志）

## 相关

- **相关概念**：[[Quantization]]
- **同会议**：[[ATC-2025]]
