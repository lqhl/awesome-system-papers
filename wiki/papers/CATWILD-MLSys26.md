---
type: paper
name: CATWILD
full_title: "CATWILD: Compiler Autotuning for TPU Workloads in the Wild"
authors: [Ignacio Cano, Yu Emma Wang, Mike Burrows, Ziqiang Feng, et al.]
venue: MLSys
year: 2026
tags: [compiler-autotuning, xla, tpu, production, google]
source_pdf: "[[ac627ab1ccbdb62ec96e702f07f6425b.pdf]]"
source_md: "[[ac627ab1ccbdb62ec96e702f07f6425b]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# CATWILD：面向真实 TPU 工作负载的编译器自动调优（MLSys 2026）

> **原题**：CATWILD: Compiler Autotuning for TPU Workloads in the Wild

> **一句话总结**：Google TPU 训练 fleet 中 XLA 启发式对异构图/新硬件次优；CATWILD 用 offline fleet profiling、扩展 XTAT autotuner 与版本化配置回灌，候选配置覆盖约 70% 的日 TPU-training chip-time，作者报告 graph flag tuning 5–15%、tile-size 10–25% 的平均加速。

## 问题与动机

ML 编译器面临 NP-hard fusion/tile/layout；硬件代际快速轮换（Fig. 1 两年 footprint 巨变）。人工 case-by-case 不可扩展；纯在线 autotune 伤害开发迭代 latency。

## 关键观察 / 隐含假设

- **观察 1：编译时间 CDF 长尾显著，在线 autotune 叠加在热路径不现实（Fig. 2）。**
  - **依赖假设**：offline 调好的配置可跨 job 复用（同 symbol 重复多）。
  - **可能失效场景**：compiler 日更（Fig. 4 高 churn）致配置 stale。

- **观察 2：tuning 65–85% 最大 speedup 可在首小时内达到，但继续调仍有益（Fig. 3）——需持续后台 autotuner 而非一次性。**
  - **依赖假设**：有预算持续跑 worker pool；遗传式搜索可逃离局部最优。
  - **可能失效场景**：极低流量 graph 不值得调。

- **观察 3：大 job（1024+ chip）无法全规模 profiling；单芯片执行 + ML simulator 投影 multi-chip 时间可行。**
  - **依赖假设**：simulator fidelity 经生产验证。
  - **可能失效场景**：通信主导 job 单芯片投影偏差大。

## 核心方法

三子系统：

1. **Fleet Profiling**：XProf 轻量采集 + compiler 上传 unoptimized/optimized graphs→Spanner/Blobstore；与 runtime 指标 join 排名。
2. **Autotuner**：CPU pool 编译 + TPU pool 执行分离（duty cycle **2–5×**）；Pub/Sub 任务；flag/tile-size 等任务。
3. **Fleet Delivery**：monorepo 存配置；后台验证 staleness、跨 compiler 版本适用性。

## 设计取舍

- **Offline transparent vs 用户驱动 tuning**：零用户负担，infra 复杂。
- **Top job 覆盖 70% vs 100%**：芯片节省集中，长尾 graph 放弃。
- **Shared config vs per-workspace pin**：共享省算力，版本错配风险靠 validator。
- **边界条件**：Google Borg+XLA+TPU 栈；GPU fleet 未声称。

## 实验与结果

- 候选配置覆盖约 70% 的日 TPU-training chip-time；约 10% 是短或低资源长尾 job，另约 20% opt out（§4.2.1）。
- 四种匿名 accelerator、60 天数据中，作者报告 graph-level flags 平均 5–15%、op-level tiles 平均 10–25% speedup（§4.2.2，Fig. 9）。
- 对全规模 TPU wall-clock ground truth，single-chip predictor 的平均误差为 2.0–4.8%，95th percentile 为 5.6–14.3%（§4.2.3，Table 1）。
- 相对 compiler default，以上 graph/tile speedup 来自四种 anonymized accelerator 的 60-day workload；其边界不包括其他 vendor 或 ISA（§4.2.2，Fig. 9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CATWILD 候选配置覆盖大部分日训练 chip-time | 约 70% candidate coverage；约 10% 长尾、20% opt out（§4.2.1） | Google TPU training fleet 的候选覆盖，不等于实际采用率 | high |
| graph 与 tile tuning 带来作者报告的加速 | graph 5–15%、tile 10–25% average speedup（§4.2.2，Fig. 9） | 四种匿名 accelerator、60 天；tile 是局部 op 测量 | high |
| predictor 对全规模 wall-clock 有可量化误差 | ACC-X/Y/Z/W 的平均误差 2.0–4.8%、95th 5.6–14.3%（§4.2.3，Table 1） | 周期性验证、28/26/19/29 representative models；非日常全量测量 | high |
| graph flag 是节省 chip 的主要来源 | 三个月 accounting 中 graph flag 约占 80%、tile 约占 20%（§4.3.1，Fig. 10） | 相对 accounting，非绝对 chip total 或因果对照 | high |
| validator 更新的配置有持续使用 | 90-day sample 中占每日 configuration hits 的 20–60%（§4.3.1，Fig. 11） | 特定 sample 的 hit share；day-55 原因仅为作者假设 | medium |

## 批判性分析

### 论证链条

fleet 异构 + compile 长尾 → offline CATWILD 闭环，生产部署支撑「首个 datacenter-scale ML autotuner」claim。外部复现依赖 Google 内部 symbol 管道。

### 假设压力测试

monorepo 极速更新使配置频繁失效；simulator 对全新 fusion pattern 外推；多租户公平性（谁被优先调）未讨论。

### 实验可信度

内部规模大；公开数字偏 aggregate。与 public OpenTuner on XLA 对比有限。

### 系统性缺陷

vendor lock-in Google stack；错误配置 rollback 机制论文简述；用户 repro 困难。

## 局限与后续工作

- **局限**：Google 专用；配置 staleness 持续运维负担；simulator 边界。
- **Future work**：开放 symbol 格式；GPU path；与 LLM 编译 pass 协同 autotune。

## 相关

- **相关概念**：[[XLA]]、[[Auto-Tuning]]
- **同类系统**：XTAT、OpenTuner
- **同会议**：[[MLSys-2026]]
