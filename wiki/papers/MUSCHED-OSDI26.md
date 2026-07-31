---
type: paper
name: MUSCHED
full_title: "Surviving the Impossible Trinity: Revisiting CPU Scheduling Problem on Modern COTS Mobile Devices"
authors: [Jun Xiao, Qinhui Gu, Ligeng Chen, Lizhi Sun, Zicheng Wang, et al.]
venue: OSDI
year: 2026
tags: [cpu-scheduling, mobile, production]
source_pdf: "[[osdi26-xiao.pdf]]"
source_md: "[[osdi26-xiao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 现代商用移动设备上的 CPU 调度“不可能三角”
> **原题**：Surviving the Impossible Trinity: Revisiting CPU Scheduling Problem on Modern COTS Mobile Devices

## 问题与动机

移动 SoC 同时面对稀缺 prime core、跨进程 IPC 依赖和严格交互 deadline。CFS 的公平性、RT 的强优先级与移动应用语义之间存在缺口，单靠静态线程优先级无法兼顾响应性、吞吐与能耗。

## 关键观察 / 隐含假设

- 用户可感知任务的关键路径会跨进程传播。
- 需要一种位于 RT 与 CFS 之间、可撤销的优先级类别。
- 假设系统可从交互事件可靠追踪依赖且应用无需修改。

## 核心方法

MUSCHED 增加 VIP scheduling class，跟踪 IPC 交互依赖，并通过可插拔 userspace policy 决定提升与回收；内核机制负责低开销执行，策略层保留不同设备和场景的可演化性。

## 实验与结果

相对 CFS 等现有调度基线，实验室应用 cold-start latency 平均降低 14.8%；系统自 2024 年部署到超过 2000 万台设备，生产启动异常降低 30.7%（§7，图 14）。边界是 Android/COTS 异构移动 SoC 的交互 workload。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 语义感知调度改善交互关键路径 | cold-start 平均下降 14.8% | §7 | 强 |
| 机制具备生产可用性 | 2000 万设备部署、异常下降 30.7% | §8 | 强 |

## 批判性分析

### 论证链条
论文以“三类约束”刻画旧抽象不足，再用 VIP、依赖传播、策略分离逐项回应。

### 假设压力测试
错误依赖传播可能引发优先级膨胀；后台高价值任务和能耗目标也可能与交互策略冲突。

### 实验可信度
大规模部署是强证据，但生产指标受版本、机型和同期优化影响，因果隔离细节仍重要。

## 局限与后续工作

- 需要更系统评估能耗、公平性、安全滥用，以及对更多移动 OS 和新型异构核的迁移。

## 相关

- [[OSDI-2026]]
- [[CPU-Scheduling]]
- [[Mobile-Systems]]
