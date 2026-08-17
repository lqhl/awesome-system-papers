---
type: paper
name: SkyServe
full_title: "SkyServe: Serving AI Models across Regions and Clouds with Spot Instances"
authors: [Ziming Mao, Tian Xia, Zhanghao Wu, Wei-Lin Chiang, Tyler Griggs, Romil Bhardwaj, Zongheng Yang, Scott Shenker, Ion Stoica]
venue: EuroSys
year: 2025
tags: [ml-serving, spot-instances, multi-cloud, geo-distributed, availability]
source_pdf: "[[eurosys25-mao-skyserve.pdf]]"
source_md: "[[eurosys25-mao-skyserve]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# SkyServe：跨区域与跨云使用 Spot 实例服务 AI 模型（EuroSys 2025）

> **原题**：SkyServe: Serving AI Models across Regions and Clouds with Spot Instances

> **一句话总结**：SkyServe 观察到不同 region/cloud 的 spot preemption 相关性远低于单故障域内，于是以跨故障域复制、廉价冗余和 on-demand fallback 把 spot 变成可用 serving capacity；真实 AI workload 上相对 on-demand 最多省 44% 成本，并相对研究/生产 baseline 将 P50/P90/P99 最多改善 2.6×/3.1×/2.7×（§6，图 8–12）。

## 问题与动机

Spot GPU 折扣很高，却会被随时回收；模型加载慢、GPU 稀缺和在线 SLO 使单 region spot serving 很脆。仅用 on-demand 保证可用性又失去成本优势。

SkyServe 把供给风险视为跨云、跨 region 的组合问题：通过地理与供应商多样性降低相关抢占，同时保留少量按需容量作为最后防线。

## 关键观察 / 隐含假设

- **观察 1**：spot availability/preemption 在不同 failure domain 之间存在可利用的非相关性（§2、图 2–3）。
- **观察 2**：多放几个廉价 spot replica 仍可低于全 on-demand 成本，因而 redundancy 可以买 availability（§3）。
- **假设 1**：跨 region latency 对目标 workload 可接受，模型 image/weight 能足够快地部署到候选云。
  - **证据强度**：中；模型和网络地域覆盖有限。

## 核心方法

控制平面根据历史价格、availability 与 failure domain 选择 spot/on-demand replica placement。系统主动 overprovision spot，在抢占或容量不足时迁移流量，并以 on-demand fallback 保住 availability。

数据平面将 client 路由到健康 replica；策略同时考虑 cost、load 与跨域 latency。与纯 autoscaling 不同，SkyServe 不假设 GPU 能按需立即获得，而是预先把风险分散到多个市场。

## 设计取舍

- **冗余换可靠性**：多开 spot 降低单点抢占风险，却增加空闲 capacity 和跨云运维。
- **多云换 failure independence**：供应更稳，但模型分发、凭据、网络 egress 和 observability 更复杂。
- **边界条件**：数据驻留、低 TTFT 或不能跨境传输的服务可能无法使用远端 replica。

## 实验与结果

- 真实 AI workload 与真实 spot trace 上，相对全 on-demand 最高降低 44% cost，同时保持高 availability（§6.2，图 8–9）。
- 相对研究与生产 serving baseline，P50/P90/P99 latency 最多改善 2.6×/3.1×/2.7×（§6.3，图 10–12）。
- sensitivity 覆盖不同模型大小、抢占强度和 fallback 策略；结论依赖被测云的 spot correlation 与价格（§6.4）。
- 系统没有证明在大范围云故障、跨云 control-plane partition 或权重更新风暴下仍满足同一 SLO。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 跨 failure domain 的 spot 可用于在线 serving | 保持 availability 且最高省 44%（§6.2） | 指定 cloud/region 与 trace | 强 |
| placement/fallback 改善 tail latency | P99 最多改善 2.7×（§6.3） | 对比选定 baseline 与模型 | 中强 |
| 冗余 spot 仍有成本优势 | placement sensitivity（§6.4） | 价格与抢占分布会变化 | 中 |

## 批判性分析

### 论证链条

论文将 spot 的“单实例不可靠”重新表述为 portfolio diversification，设计简单且证据直接。最大风险是把历史上较低的跨域相关性视为未来保证；云级容量事件可能同时冲击多个 region。

### 假设压力测试

大模型冷启动、模型频繁更新、跨云 egress 收费或数据合规会侵蚀收益。若所有云同时缺 GPU，on-demand fallback 也未必可获得。

### 实验可信度

真实 trace 和多类 latency/cost metric 强于纯模拟，但长期故障窗口与 provider policy shift 覆盖有限；availability headline 不是形式保证。

### 系统性缺陷

多云凭据、版本、quota、监控与安全边界扩大 operational surface。论文重点是调度收益，未完整量化运维人力和数据传输成本。

## 局限与后续工作

- 用相关 region outage、quota exhaustion 和模型更新风暴做 fault campaign。
- 将 egress、碳排、数据驻留和冷启动纳入 placement objective。

## 相关

- **相关概念**：[[LLM-Inference]]、[[Disaggregation]]
- **同类系统**：SkyPilot、INFaaS
- **同会议**：EuroSys 2025

