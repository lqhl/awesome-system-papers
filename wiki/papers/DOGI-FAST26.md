---
type: paper
name: DOGI
full_title: "DOGI: Data Placement with Oracle-Guided Insights for Log-Structured Systems"
authors: [Jeeyun Kim, Seonggyun Oh, Jungwoo Kim, Jisung Park, Jaeho Kim, Sungjin Lee, Sam H. Noh]
venue: FAST
year: 2026
tags: [log-structured-storage, garbage-collection, data-placement, machine-learning, zns]
source_pdf: "[[fast2026-kim-jeeyun.pdf]]"
source_md: "[[fast2026-kim-jeeyun]]"
---

# DOGI: Data Placement with Oracle-Guided Insights for Log-Structured Systems (FAST 2026)

> **一句话总结**：先设计离线 oracle baseline NoDaP 量化 SOTA 数据放置技术与最优 GC 的差距，再用「轻量启发式 + 紧凑 MLP + 动态分组配置」组合的 DOGI 在 [[ZNS]] 设备原型上把 WAF 降低最多 23.2%、写吞吐提升 13.3%（vs SepBIT / MiDAS / PHFTL / ML-DT）。

## 问题

Log-structured 存储（FTL、KV store、分布式 FS）靠把随机写转顺序 append 拿高吞吐，但 [[Garbage Collection|GC]] 把存活 block 搬迁带来 write amplification factor (WAF) 损失。把生命期相近的 block 放到同 segment 可以减少搬迁，已有 SOTA（SepBIT、MiDAS、PHFTL、ML-DT）做了不少工作但与最优仍有差距。三个具体短板：
1. user-written block 的 invalidation time 预测：启发式快但不准（76–82%），ML 准（87%）但单次推理 6.5 µs (PHFTL) 或 173 µs (ML-DT) 把吞吐拖到 22.6 MB/s。
2. GC-written block 的重定位：现有 age-based 或「全部丢一个冷组」都没识别出 GC 阶段 block 实际生命期分布很宽。
3. group 数量配置：固定 6/20 个组忽略「分得越细 vs 误判惩罚越大」的权衡。

## 核心方法

**三阶段 oracle-guided 设计**：

- **NoDaP（near-optimal baseline）**：假设知道未来精确 invalidation time，离线 exhaustive 搜 N、group sizes、BIRs 使 WAF 趋近 1.0。用作 SOTA 短板诊断的 reference。
- **DOGI Hot Filter (HF) + ML-Alloc（user-written block）**：HF 用 latest-invalidation-time 启发式快速隔离最热块到 G_hot，迭代算法动态调 BIR 上界 µ；剩下的非热块走 ML-Alloc。ML 模型选 1.6 K 参数的 MLP（实测 vs MLP/DeepFM/RF/LightGBM 综合最优），输入 6 个 PCC/MI 筛选后的特征（LBA、prev LBA、frequency、frequency per chunk、recency-weighted frequency、latest invalidation time）。10 类分类。**Batch inference (128 blocks/batch) 把延迟从 10.6 µs/block 降到 0.9 µs/block**，再 double buffer 完全 overlap I/O。
- **Frozen Filter (FF) + ML-Reloc（GC-written block）**：FF 用 1-bit/block flag 把从未更新的块归到 G_frzn；其它块用 PLog（<predicted category, actual invalidation time> 历史记录表）算每个类别的 average remaining invalidation time，按此重定位到合适 BIR 的组。
- **动态 group 配置**：PLog 给出每组的 misprediction 比例，[[Markov Chain]] 模型把（组数、user-block 分布、misprediction 比例）转成预期 WAF；brute-force 搜 2⁹=512 种配置取 WAF 最低，10 秒完成；运行时模型预测准确率跌破阈值（如 10%）就 fallback 到经典 2 user / 2 GC 组。

## 关键结果

- 仿真器（128 GiB、256 MiB segment、10% OP）+ Western Digital ZN540 [[ZNS]] 2 TB SSD 原型 + ZenFS 实测。
- WAF 比最强 baseline 降 15.5%（平均）、最多 23.2%；写吞吐提升最多 13.3%（DOGI 968+ MB/s）。
- 预测准确率比 SOTA 高 0.9–8.1%。
- 工作负载覆盖 FIO、YCSB-A/-F、Varmail、Alibaba、Exchange。

## 相关

- **相关概念**：[[Garbage Collection]]、[[Write Amplification]]、[[Markov Chain]]、log-structured storage
- **同类系统**：SepBIT、MiDAS、PHFTL、ML-DT
- **相关存储**：[[ZNS]]、[[FTL]]、[[F2FS]]、RocksDB
- **同会议**：[[FAST-2026]]
