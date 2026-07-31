---
type: paper
name: DVLA
full_title: "DVLA: Dynamic VM Lifetime Aware Scheduling for Drifting Lifetime Distributions and Long-Lived VM Placement Debt (Operational Systems)"
authors: [Zhengtong Zhang, Zihan Xu, Zhidong Hu, Yanbo Shan, Fei Peng, et al.]
venue: OSDI
year: 2026
tags: [cloud-scheduling, virtual-machine, lifetime-prediction, bin-packing, operational-systems]
source_pdf: "[[osdi26-zhang-zhengtong.pdf]]"
source_md: "[[osdi26-zhang-zhengtong]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向分布漂移与长寿 VM 债务的动态生命周期调度（OSDI 2026）

> **原题**：DVLA: Dynamic VM Lifetime Aware Scheduling for Drifting Lifetime Distributions and Long-Lived VM Placement Debt (Operational Systems)

> **一句话总结**：DVLA指出static lifetime buckets会随cluster/time drift失效，误散布的long-lived VMs还形成online placement无法偿还的机器占用债务；系统以multi-horizon prediction、动态policy和offline rectification协同回收capacity，并已在Alibaba Cloud生产部署。

## 问题与动机

短VM占96% requests却少于2% core-hours，极少长VM贡献93% core-hours；一个长VM放错机器可长期阻止整机回收。既有lifetime-aware scheduling只优化arrival placement，固定threshold对spatial/temporal drift脆弱，prediction error累积为placement debt。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

Hierarchical predictor给出initial低延迟分类与不同horizon存活概率；online policy根据当前distribution动态划category/packing策略。系统量化每机long-lived debt与reclamation potential，offline rectifier选择少量VM migration/consolidation偿还历史债务，并约束migration/operational budget。

## 实验与结果

- **Trace特征**：生产VM请求中约2.5%的长寿实例贡献93%的core-hours；实验将DVLA与静态lifetime-aware基线对比，以packing density、机器回收量和成本为指标（§6）。
- **评测设置**：在论文给定的生产 trace 或代表性工作负载上，对比原系统/现有最佳基线，以吞吐、延迟、资源节省或覆盖率为主要指标（§6）。

- 多生产cluster trace显示lifetime distribution显著漂移，static policies持续退化。
- DVLA online+offline相对lifetime baselines提高packing density/释放机器并降低infrastructure overhead。
- Alibaba Cloud production deployment展示substantial resource/cost reduction与可管理overhead。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 核心机制改善了论文所针对的主要瓶颈 | §6 的端到端结果与组件拆解 | 论文所测平台、模型与工作负载 | 强 |
| 机制可迁移到更广泛环境 | §6 的扩展性或敏感性实验 | 尚未覆盖所有硬件与生产条件 | 中 |

## 批判性分析

### 论证链条

“placement debt”是比预测accuracy更重要的系统洞察：即使未来预测改进，旧长VM仍钉住机器。offline migration会带来网络、downtime与应用风险，成本模型是否完整决定净收益；生产数字/trace不可完全公开也削弱复现。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 报告prediction calibration、迁移SLO与按cluster的绝对节省。
- 对concept drift、adversarial tenant和correlated lifetime变化做鲁棒性测试。
- 联合CPU/memory/network多维fragmentation和energy-aware machine shutdown。

## 相关

- **相关概念**：[[VM-Scheduling]]、[[Bin-Packing]]、[[Concept-Drift]]、[[Placement-Debt]]
- **同会议**：[[OSDI-2026]]
