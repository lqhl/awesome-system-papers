---
type: paper
name: Kamino
full_title: "Kamino: Efficient VM Allocation at Scale with Latency-Driven Cache-Aware Scheduling"
authors: [David Domingo, Abhisek Pan, Hugo Barbalho, David Dion, Marco Molinaro, Thomas Moscibroda, Kuan Liu, Sudarsun Kannan, Ishai Menache]
venue: OSDI
year: 2025
tags: [cloud-scheduling, vm-allocation, caching, azure, latency]
source_pdf: "[[osdi25-domingo.pdf]]"
source_md: "[[osdi25-domingo]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-16
---

# Kamino: Efficient VM Allocation at Scale with Latency-Driven Cache-Aware Scheduling (OSDI 2025)

> **一句话总结**：Kamino 的 LatCache 用队列与分层 cache 部分状态估计端到端延迟来选择 AA；五个代表性 Azure zones 的部署前后测量中，平均分配延迟 **−21.1%**、P90 **−11.9%**、cache miss **−33%**（§6.7），为 before/after 而非随机对照。

## 问题与动机

云 VM allocator（Protean 类）要在 tens of ms 内完成高质量放置，依赖 **分层 cache**（fast path 全同请求、slow path 部分规则命中），单 slot 10–100 MB，每节点仅少数 AA。现有调度 round-robin/work-stealing **不看 cache**，且纯 cache-aware pinning 会在热点请求上制造排队 tail。内存占满而 CPU 欠用（~90% mem、~39%–74% CPU），限制 AA 数量。

## 关键观察 / 隐含假设

- **观察 1**：VM 分配 cache 的 hit/miss 延迟随请求类型变化极大，hierarchical cache 使「hit」仍可能需部分重算；burst 时 inventory 更新放大延迟。
  - **依赖假设**：latency 估计需结合队列长度、pending 请求对 cache 的增量影响，而非 hit rate 代理。
  - **可能失效场景**：请求类型空间极小、cache 极大时调度收益缩小。
- **观察 2**：增加 AA 数若均分 cache slot 会降低 hit rate（仿真 4→8 AA 平均延迟先降后升）。
  - **依赖假设**：应在 latency 与 locality 间动态权衡，而非静态 affinity。
  - **证据强度**：强——生产四 observation 驱动设计。
- **假设 1**：每 AA 私有 cache（避免共享锁）是既定架构，调度器只能优化请求→AA 映射。
  - **证据强度**：强——Protean 生产实践。

## 核心方法

**Kamino + LatCache**：每 AA 有请求队列；新请求分配到预估 **排队+处理** 延迟最小的队列。处理时间由 cache 部分状态（类型、规则命中预测）与队列中前置请求对 cache 的演化估算。

**架构**：与 VM 放置逻辑解耦；流水线化分类与入队。生产部署简化版 LatCache。

## 设计取舍

- **取舍 1**：估计基于部分 cache 指标，非全状态仿真，换可扩展性。
- **取舍 2**：不共享 cache，换多核并行；靠 smarter routing 补 hit rate。
- **边界条件**：规则集剧变时估计需重新校准。

## 实验与结果

- 仿真：六条 24h 生产 trace 中，LatCache 两个版本相对 Protean 的 P90 都改善超过 **50%**；Hash+WS 的平均/尾改善为 **4.4%/9.1%**（§6.1–6.2，Fig.6）。
- burst 边界：两个连续 burst window 中吞吐为 Protean 的 **2×**（§6.2，Fig.7），非全天平均。
- 生产测量：五个代表性 zone、部署前后各 15 天，平均 185.6±20.4→146.3±17.4 ms（**−21.1%**）、P90 378.8±90.8→333.5±64.7 ms（**−11.9%**）（§6.7，Table 4）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| LatCache 选择估计端到端延迟最低的 AA 队列 | 估计结合队列、top-level hit 与规则级 cache 状态；调度开销为每请求微秒级（§3–5） | Azure Protean 节点内私有 hierarchical AA cache | high |
| trace 仿真中的尾延迟低于 Protean | 两版本相对 Protean 的 P90 均改善超过 50%（§6.2，Fig.6） | 六条 24h trace、固定 4 AA、cache 最多节点内存 58% | high |
| burst 吞吐可达 Protean 的 2× | 两个连续 burst 的 Fig.7 结果（§6.2） | 仿真 burst window，非生产全天吞吐 | high |
| 生产部署降低分配延迟与资源占用 | avg −21.1%、P90 −11.9%、miss −33%、memory −17%、CPU −18.6%（§6.7，Table 4/Fig.11） | 五个代表性 zones 的 before/after；部署为较简单 LatCache-request | high |
| 规则级状态在仿真中减少 cache memory | normalized memory：Protean 1.00、request 0.85、rule 0.77（§6.3，Table 3） | 六条 trace simulator；不是 LatCache-rule 的生产部署 | high |
- LSM 原型：lookup 延迟 -22%（附录，LatCache 原则外推）。

## Critical Analysis

### 论证链条

生产 characterization → hit/miss 非单调 → latency-centric scheduling → 仿真+生产验证。链条在 Azure 控制面闭合；其他云厂商 allocator 细节未知。

### 假设压力测试

- 请求类型爆炸式增长时估计误差累积。
- 跨 zone inventory 不一致时 cache 模型失效。
- 与 SSD 二级 cache 的未来工作尚未量化 ROI。

### 实验可信度

生产部署是亮点；仿真与生产指标一致性好。对比策略含 Protean 自身变体，需读清是否公平共享资源上限。

### 系统性缺陷

论文未讨论：调度器故障模式、恶意请求类型探测、与 autoscaling 反馈环路的稳定性。

## 局限与 Future Work

- **局限 1**：依赖 Azure 特定 cache/规则结构。
- **局限 2**：LatCache 理论最优性未证明（推广 job scheduling 难问题）。
- **Future work 1**：SSD 二级 cache 缓解 memory bottleneck。
- **Future work 2**：更精细的 tail SLO 约束与多维资源（NUMA、disk）联合调度。

## 相关

- **相关概念**：Caching、Load Balancing
- **同类系统**：Protean、Omega、Kubernetes scheduler
- **同会议**：[[OSDI-2025]]
