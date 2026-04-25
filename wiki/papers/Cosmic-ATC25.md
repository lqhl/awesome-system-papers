---
type: paper
name: Cosmic
full_title: "Cosmic: Cost-Effective Support for Cloud-Assisted 3D Printing"
authors: [Yuan Yao, Chuan He, Chinedum Okwudire, Harsha V. Madhyastha]
venue: ATC
year: 2025
tags: [serverless, 3d-printing, latency-sensitive, aws-lambda, speculation]
source_pdf: "[[atc2025-yao.pdf]]"
source_md: "[[atc2025-yao]]"
---

# Cosmic: Cost-Effective Support for Cloud-Assisted 3D Printing (ATC 2025)

> **一句话总结**：把 LPBF 3D 打印的 SmartScan 控制算法跑在 AWS Lambda 上，通过 cell-grouping + 投机预调度同时压住 50 ms 时序约束，对 30 个打印任务比基线方案省 2.8×–3.5× 成本。

## 问题

LPBF（laser powder bed fusion）打印需要 SmartScan 控制器在每个 ~50 ms 时间窗内决定下一个要扫描的 cell；算法核心是温度向量与 11.92 GB heat transfer 矩阵的乘法，本地 CPU 跑一次要 450 ms，且单个齿轮就有 1514 GB 矩阵不可能放进打印机内存。VM 方案要常驻几十台高内存机器、还要付层间 15 s 空闲费用；Serverless（Lambda）天然按需付费、warm start 还能在 invocation 间保留 in-memory 矩阵，但**单次 invocation 开销 10 ms 中位、13.2 ms p90**，加上 coordinator-to-N-worker 的网络分发延迟，naive Invoke-on-demand / All-persistent / All-active 三种现有方案要么超时（4.28 s / layer 超过 3.33 s 约束）要么把成本推回 VM 水平。

## 核心方法

Cosmic 把"哪些 cell 共享一个 worker 组、何时调起函数"展开成更大的配置空间：

- **Grouping**：N 个 worker 分成 G 组，每组承担 1/G 的 cell。G=1（All-active）网络瓶颈，G=N（Invoke-on-demand）每窗都吃 invocation 开销；中间区间用 cell-per-group 在两种 overhead 间权衡
- **Speculation**：用近似温度图（只加 laser 输入、忽略热扩散）在当前 window 内预测下一 cell 所属组，提前 D ms（D=invocation 中位延迟）调起，命中率高时 invocation 开销几乎归零
- **配置选择**：穷举所有 (cells/group, functions/group, speculation 模式) 组合，用模型基于 invocation 延迟分布、PCIe/网络带宽、矩阵乘法 profile 估算 per-window 时间和成本，选最便宜的可行解（10 s 内枚举完）

打印中 coordinator VM 同时维护实际 SmartScan（决定真 cell）和近似版（生成 speculation guess）。深度细节回 [[atc2025-yao]]。

## 关键结果

- 30 个打印任务（10 形状 × 3 尺寸）在 4 GPU/Lambda 上全部满足时序约束
- 比 Invoke-on-demand / All-persistent / All-active 三种 baseline 方案中**唯一不超时的那一个**省 2.8×–3.5× 成本；其他三种 baseline 在 23/30 任务上违反时序
- 16cm² 齿轮需要 1514 GB 矩阵 / 159 worker；Lambda warm start 在 24h 实测 50 ms–1 s 间隔下 cold start <0.1%

## 相关

- **相关概念**：[[Serverless]]、[[Speculative-Execution]]
- **同会议**：[[ATC-2025]]
