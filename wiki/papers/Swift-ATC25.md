---
type: paper
name: Swift
full_title: "Swift: Fast Performance Tuning with GAN-Generated Configurations"
authors: [Chao Chen, Shixin Huang, Xuehai Qian, Zhibin Yu]
venue: ATC
year: 2025
tags: [bayesian-optimization, gan, autotuning, big-data, spark, flink]
source_pdf: "[[atc2025-chen-chao.pdf]]"
source_md: "[[atc2025-chen-chao]]"
---

# Swift: Fast Performance Tuning with GAN-Generated Configurations (ATC 2025)

> **一句话总结**：在 Bayesian Optimization 每轮搜索中，把当前最优配置喂进 [[GAN]] 生成 150 个分布相近的候选，混入 100K 随机配置一起给 acquisition function 选，把 Spark/Flink 调参收敛时间从 12.5+ 小时压到 5.8 小时，吞吐 +1.59×、延迟 -1.68×。

## 问题

Spark / Flink 等大数据系统有 30-40 个性能关键参数，参数间非线性交互，调参极难：

- 传统规则 / 解析模型不准；
- ML-based 方法（[[OPPerTune]]、[[SelfTune]]、PARIS、Quasar）需要数百样本，每样本要在真集群上跑分钟级；
- [[Bayesian-Optimization]]（CherryPick）虽然样本少，但仍要数十次实跑，单 query 1 TB 数据要 100+ 小时收敛。

直觉的 "在最优配置周围采样" 方法（One-Neighbor，Manhattan 距离 + 5%/25% 随机扰动）不奏效——5% 太相似无信息，25% 时性能可差 2×。

## 核心方法

**Swift** 用 [[GAN]] 在 BO 每轮迭代中生成"分布相近、性能相近但不完全相同"的候选配置，关键洞察是：靠近不仅要向量距离短，更要 *元素值分布相似*——而 [[GAN]] 天然用 [[JS-Divergence]] 度量分布相似度。

- **Configuration Generator**：RCG（uniform 100K）+ GCG（GAN 150 个）。GCG 用 G + D 两个全连接网络，G 输入 = 当前最优配置 + 高斯噪声，D 区分真假；27/34 维一维向量训练比图像快得多，固定 20 epoch 即可保证生成配置性能在 ±25% 内；
- **Configuration Profiler**：实跑评估，比当前最优好则插入 evaluated set (ES)；
- **GP Builder**：用 ES 维护 [[Gaussian-Process]]，Matern5/2 kernel；
- **Configuration Arbiter**：每轮把 100,000 random + 150 GAN 候选合在一起，让 EI acquisition function 挑；当 "current best" 更新时重训 GAN。

不需要训到 G/D 平衡（如果一直生成同性能就探索不到更好），只需 fixed 20 iter。

## 关键结果

- **Flink**：4 个程序吞吐提升 1.28× avg / 1.59× max；延迟降 1.31× avg / 1.68× max；优化时间 5.8 h vs CherryPick 12.5+ h。
- **Spark**：24 程序 × 3 输入大小，执行时间降 1.2× avg / 2.2× max；调参时间快 61% avg / 156% max。
- **TPC-DS**：23 个 SQL query，500 GB 数据下 BO 单 query 30+ 小时，1 TB 100+ 小时——Swift 显著缩短。
- **生产环境**：互联网公司 Flink 程序，工程师手调 4 天，Swift 6.8 小时把吞吐提升 2.3×，延迟降 2.8×。

## 相关

- **相关概念**：[[Bayesian-Optimization]]、[[GAN]]、[[Gaussian-Process]]、[[Auto-Tuning]]
- **同类系统**：[[CherryPick]]、[[OPPerTune]]、[[SelfTune]]
- **同会议**：[[ATC-2025]]
