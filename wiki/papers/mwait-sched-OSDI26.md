---
type: paper
name: mwait-sched
full_title: "What Are You (M)Waiting For: The Hidden Cost of Idle in the Hyperscale Cloud"
authors: [Yun Wang, Xingguo Jia, Ben Luo, Kenan Liu, Shengdong Dai, et al.]
venue: OSDI
year: 2026
tags: [virtualization, cpu-scheduling, cloud]
source_pdf: "[[osdi26-wang-yun.pdf]]"
source_md: "[[osdi26-wang-yun]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 超大规模云中 mwait 空闲的隐性代价
> **原题**：What Are You (M)Waiting For: The Hidden Cost of Idle in the Hyperscale Cloud

## 问题与动机

超售云中，guest 通过 `mwait` 进入低功耗等待时，passthrough 会让 hypervisor 看不见 vCPU 已经空闲；该 vCPU 仍占住 pCPU，使真正可运行的邻居承受 steal time、迁移和尾延迟。论文关注的不是平均利用率，而是[[CPU-Scheduling|调度器]]可观测性缺失形成的生产 SLO 风险。

## 关键观察 / 隐含假设

- `mwait` 是架构级 idle 提示，却没有自然穿过虚拟化边界成为调度信号。
- 超售比例即使约 1%，短时错误占用也足以放大交互服务尾延迟。
- 假设 host 能以低开销识别 guest 的等待地址及唤醒语义。

## 核心方法

`mwait-sched` 将 `mwait` 重新设计为 virtualization-aware 调度原语：识别等待状态、按等待类型分类，并用可扩展的 multi-address proxy 代理监视与唤醒；hypervisor 因而可以让出 pCPU，同时保留 guest 预期的唤醒行为。

## 实验与结果

在超售 VM 与共置服务负载上，原始 passthrough 可将共置尾延迟放大至 3×；`mwait-sched` 相对该方案把尾延迟降低 30–50%，steal ratio 降低 30–40%（§6，图 12）。边界是采用 x86 `mwait` 且存在 pCPU 共享的云主机。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| idle 不可见会造成真实 SLO 损失 | 生产观测与共置实验出现最高 3× 尾延迟 | §2，§6 | 强 |
| 把等待变成调度信号可回收 CPU | 尾延迟和 steal ratio 同时下降 | 图 12 | 强 |

## 批判性分析

### 论证链条
论文从 production symptom 追到跨虚拟化层语义丢失，再以代理等待机制恢复可观测性，因果链较完整。

### 假设压力测试
收益依赖超售和 `mwait` 使用密度；专属核、polling 或非 x86 guest 上未必成立。

### 实验可信度
生产数据与受控共置实验互相支撑，但硬件代际、guest OS 与更激进 oversubscription 的外推仍有限。

## 局限与后续工作

- 可进一步验证 ARM 等待原语、嵌套虚拟化，以及恶意 guest 伪造等待地址时的隔离与公平性。

## 相关

- [[OSDI-2026]]
- [[Virtualization]]
- [[CPU-Scheduling]]
