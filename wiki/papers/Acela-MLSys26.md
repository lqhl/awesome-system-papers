---
type: paper
name: Acela
full_title: "Cost-Aware Duration Prediction for Software Upgrades in Datacenters"
authors: [Yi Ding, Aijia Gao, Thibaud Ryden, Michal Sedlak, Essam Ewaisha, Igor Marnat, Henry Hoffmann]
venue: MLSys
year: 2026
tags: [datacenter, scheduling, prediction, firmware-upgrade, slo]
source_pdf: "[[3c59dc048e8850243be8079a5c74d079.pdf]]"
source_md: "[[3c59dc048e8850243be8079a5c74d079]]"
---

# Cost-Aware Duration Prediction for Software Upgrades in Datacenters (MLSys 2026)

> **一句话总结**：Acela 用非对称代价感知的 quantile regression 预测 Meta 生产环境 firmware upgrade 时长，使 upgrade window 利用率 **1.25×**、调度/完成量 +33%/+41%，取消率降 **2.4×** 且仍满足 95% SLO。

## 问题

超大规模数据中心软件升级（OS/firmware/kernel）需在固定 upgrade window 内完成，SLO 要求 **≥95%** 升级按时结束。Meta 现网采用 worst-case 固定时长，window 利用率仅 **20–40%**，idle 严重。升级类型多、尾延迟长，且 underprediction 比 overprediction 代价更高（违反 SLO、触发 repair 歧义）。

## 核心方法

**Quantile Gradient Boosting Trees**：用 τ>0.5 的 quantile loss 偏 mild overprediction，匹配非对称 misprediction cost。

**Custom scoring**：在验证集上平衡 MAE 与 overprediction rate（OPR），OPR≥SLO 时最小化 MAE，否则惩罚 under-SLO 风险。

**Training set diversification**：剔除 p99/p99.9 straggler 训练多个截断数据集，减轻极端 overprediction bias。

**调度集成**：在优先级语义不变前提下，同等优先级选更短预测时长；冲突时仍优先 policy-critical 升级。

## 关键结果

- upgrade window 利用率 **1.25×**（相对现网 20–40% 基线）
- 调度升级量 **+33%**，完成量 **+41%**，取消率 **÷2.4**
- 训练 400 万+、测试 100 万真实 Meta firmware upgrade

## 相关

- **相关概念**：[[Continuous-Batching]]
- **同类系统**：Meta circle-based upgrade scheduler
- **同会议**：[[MLSys-2026]]