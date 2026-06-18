---
type: paper
name: Gohil-UncertaintyAware
full_title: "When Machine Learning Isn't Sure: Building Resilient ML-Based Computer Systems by Embracing Uncertainty"
authors: [Varun Gohil, Nevena Stojkovic, Noman Bashir, Sundar Dev, Gaurang Upasani, David Lo, Parthasarathy Ranganathan, Christina Delimitrou]
venue: MLSys
year: 2026
tags: [ml-for-systems, uncertainty-estimation, ood-detection, graceful-degradation, production-ml]
source_pdf: "[[182be0c5cdcd5072bb1864cdee4d3d6e.pdf]]"
source_md: "[[182be0c5cdcd5072bb1864cdee4d3d6e]]"
---

# When Machine Learning Isn't Sure: Building Resilient ML-Based Computer Systems by Embracing Uncertainty (MLSys 2026)

> **一句话总结**：提出 uncertainty-aware 框架：推理时用 uncertainty 估计器识别不可靠预测并拒绝，再降级到安全 fallback；在 Google 服务器容量规划、Sinan 集群调度、Heimdall SSD 准入三个 case study 上证明「最佳 estimator 与 fallback 都取决于任务延迟/设计约束」，而非单一万能方案。

## 问题

ML 已广泛用于 workload scheduling、资源管理、编译优化，但生产部署仍受 **generalizability** 制约：OOD 数据、分布漂移、对抗样本会让模型静默失效。周期性重训练是 reactive 且慢；在线学习在训练周期间仍允许错误发生。

理想「generalizability oracle」不可能（要知道对错需事后 ground truth），但 **prediction uncertainty 与 misprediction 强相关**，可在推理时 proactive 检测。核心问题变成两个：(1) 如何检测不确定？(2) 不确定时做什么？

## 核心方法

框架在 ML 预测路径上插入 uncertainty estimator + decision module：超阈值则拒绝预测并执行 fallback。

三个 case study 覆盖 classification/regression、静态/动态环境、微秒到分钟级延迟：

**1. Server resource capacity provisioning（Google，分钟级）**
- 任务：用 ML 预测 90th percentile memory bandwidth，辅助服务器设计。
- 未见服务器 Amber 上 MAPE 从 8.7% 飙到 47%，但简单线性模型在 seen 上更准。
- 选用 **2-layer BNN + Monte Carlo sampling**（~600 ms/batch 可接受）：OOD 时 uncertainty 15.6 vs ID 1.2，单位一致（GBps）。
- Fallback：人工审查或切到 simulator/analytical model。

**2. Cluster resource management（Sinan，毫秒级）**
- 任务：微服务 tail latency 预测 + 资源分配；负载超训练分布后 QoS violation 从 5% 升到 22%。
- 模型固定，需 **model-agnostic** 方法：conformal prediction 最优。
- 相对 uncertainty 阈值 15% 时，与 AutoScaleOpt heuristic **并行执行** fallback，不增加端到端延迟；QoS violation 比 baseline Sinan 降 2–11%。
- BNN 虽 violation 最低（4–16%），但需替换模型且 CPU 98.3%，不满足设计约束。

**3. Storage I/O admission（Heimdall，微秒级）**
- 任务：预测 SSD I/O 快慢并做准入/hedging；BNN 单次 238 µs、conformal 需扫 calibration set，均不可用。
- 唯一可行：**distance-based**（Euclidean/Mahalanobis 到训练集 centroid），开销 ~7 µs。
- 不确定时 fallback 到 hedging（双发取先返回）；Euclidean 仅 5.22% 请求不确定，99.9th latency 降 **56%**。

## 关键结果

- Google 生产规模 profiling：1.2M 数据点、4 种 seen 服务器 + 1 种 unseen；BNN 能区分 OOD 与「分布相近的 unseen」。
- Sinan + conformal：多种负载模式下稳定降 violation，CPU/内存开销仅 KB 级 calibration 样本。
- Heimdall + distance：平均 latency 降 12–18%，tail 最高降 57%，hedging 开销可控。
- Table 3 总结三类 estimator 在 latency、内存、model-agnostic、unit-consistent 上的 tradeoff，并给出 practitioner guideline。

## 相关

- **相关概念**：Conformal-Prediction、Bayesian-Neural-Network、OOD-Detection、Graceful-Degradation
- **同类工作**：Predictions-with-Rejections、Guardrails/Safeguards、Data-Slicing
- **同会议**：[[MLSys-2026]]