---
type: paper
name: CATWILD
full_title: "CATWILD: Compiler Autotuning for TPU Workloads in the Wild"
authors: [Ignacio Cano, Yu Emma Wang, Mike Burrows, Ziqiang Feng, Matheus Camargo, et al.]
venue: MLSys
year: 2026
tags: [compiler-autotuning, xla, tpu, fleet-optimization, production-system]
source_pdf: "[[ac627ab1ccbdb62ec96e702f07f6425b.pdf]]"
source_md: "[[ac627ab1ccbdb62ec96e702f07f6425b]]"
---

# CATWILD: Compiler Autotuning for TPU Workloads in the Wild (MLSys 2026)

> **一句话总结**：Google 首个数据中心规模部署的 XLA 编译器 autotuning 系统，离线搜优 graph-level flags 与 op-level tile size，透明注入 fleet，覆盖约 **70%** 日训练 chip-time，graph 调优 5–15%、op 调优 10–25% 加速，显著节省 TPU 芯片。

## 问题

XLA 启发式 + 人工 trace 调优难扩展：NP-hard 融合/layout/tile 问题、~2^37 flag 搜索空间、硬件代际快速更替（两年 fleet footprint 大幅迁移）。在线 autotuning 会拉长编译尾延迟（P90 ~50 s）；逐版本逐 job 离线 tune 又不现实。需要透明、可版本化、可复用的 fleet 级 autotune 闭环。

## 核心方法

三子系统（Figure 6）：

1. **Fleet Profiling**：XProf 轻量持续采集 + Symbols Service 上传 unoptimized/optimized HLO；~90% accelerator 覆盖率
2. **Autotuner**（扩展 XTAT）：CPU worker 编译 + TPU worker 执行分离（duty cycle **2–5×**）；graph flag tuning + op tile-size tuning；**single-chip performance predictor** 用 stub 通信在单芯片上估 multi-chip runtime（~5% 误差界）
3. **Fleet Delivery**：fingerprint → KV store（版本控制嵌入 binary）；编译时查表应用；Configurations Validator 后台重验防 stale/数值回归；失败透明 fallback 默认配置

离线 tune 数千 graph/op/天，每任务预算约 12 h；65–85% 最大加速首小时内达到。

## 关键结果

- 日覆盖：**~70%** TPU training chip-time（~10% 长尾不值得 tune，~20% opt-out）
- Graph-level flag tuning：平均加速 **5–15%**（因 accelerator 而异）
- Op-level tile tuning：平均加速 **10–25%**
- Predictor：多数模型误差 <5%；多 chip 图用单 chip 仿真
- Validator 贡献：**20–60%** 日配置 hit 来自跨编译器版本 fingerprint 更新
- 五年生产运营经验报告（首个 datacenter-scale ML compiler autotuning）

## 相关

- **相关概念**：XLA、compiler autotuning、feedback-directed optimization
- **同类系统**：XTAT、TVM AutoTuner、Halide autoscheduler
- **同会议**：[[MLSys-2026]]