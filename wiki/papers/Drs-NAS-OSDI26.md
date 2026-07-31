---
type: paper
name: Drs.NAS
full_title: "Drs.NAS: Ultra-Efficient Neural Architecture Search for Recommendation Systems"
authors: [Ruixuan Wang, Xun Jiao]
venue: OSDI
year: 2026
tags: [neural-architecture-search, recommendation-system, efficiency]
source_pdf: "[[osdi26-wang-ruixuan.pdf]]"
source_md: "[[osdi26-wang-ruixuan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 推荐系统的超高效神经架构搜索
> **原题**：Drs.NAS: Ultra-Efficient Neural Architecture Search for Recommendation Systems

## 问题与动机

深度推荐模型的 [[Neural-Architecture-Search|NAS]] 通常需要反复训练验证，搜索耗时 5–18 GPU-hours；得到的 architecture 仍可能参数多、FLOPs 高，不适合快速生产迭代。

## 关键观察 / 隐含假设

- 搜索期间的 architecture gradient 与无需训练的结构统计可构成预测最终质量的 superproxy。
- 若 proxy 能排序候选者，就可跳过昂贵的 candidate training/validation。
- 假设 Criteo、Avazu、KDD 上 proxy 与 AUC/LogLoss 的关系可迁移到目标 DRS search space。

## 核心方法

[[Drs-NAS]] 以 superproxy 评价候选架构，在 differentiable search 中同时约束预测表现、parameter count 与 FLOPs；搜索只需 commodity CPU，最后才训练选出的 architecture。

## 实验与结果

在 Criteo、Avazu、KDD 三个 recommendation benchmark 上，Drs.NAS 将 SOTA baseline 的 5–18 GPU-hours 搜索降到 commodity CPU 约 2 minutes，最高约 692× search-time improvement；相对 SOTA NAS，model size 平均缩小 34.9×、FLOPs 减少 14.7×，平均 AUC 高 0.0056（§5，表 1、图 4）。CPU/GPU inference time 分别平均降低 60.8%/24%。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| superproxy 可替代逐候选训练 | 搜索从 GPU-hours 降到 2 CPU-minutes | 三个 DRS benchmark | 强 |
| 搜索速度未以模型质量换取 | AUC 高 0.0056 且 FLOPs 少 14.7× | SOTA NAS baseline | 强 |

## 批判性分析

### 论证链条
论文先以 proxy 消除 search inner-loop training，再把资源指标纳入目标，因而同时解释搜索成本与产物成本的下降。

### 假设压力测试
superproxy 可能过拟合特定 operator/search space；数据分布、特征交互或 latency hardware 改变后，排序相关性可能失效。

### 实验可信度
三个公开 benchmark、多 NAS/handcrafted baseline 和真实 inference latency 较完整；缺少 hyperscale online A/B、长期 retraining 与 energy 数据。

## 局限与后续工作

- 验证更多推荐 search space、硬件和线上分布漂移。
- 将 tail latency、memory bandwidth 与 energy 直接纳入 hardware-aware objective。

## 相关

- [[OSDI-2026]]
- [[Neural-Architecture-Search]]
- [[Recommendation-System]]
