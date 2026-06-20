---
type: paper
name: Catur
full_title: "VIRTUAL MACHINE NUMA PLACEMENT AT SCALE: LEARNING THE NORM, SHIELDING THE TAIL"
authors: [Authors from paper]
venue: MLSys
year: 2026
tags: [numa, cloud, reinforcement-learning, vm-placement, hypervisor]
source_pdf: "[[ea5d2f1c4608232e07d3aa3d998e5135.pdf]]"
source_md: "[[ea5d2f1c4608232e07d3aa3d998e5135]]"
---

# VIRTUAL MACHINE NUMA PLACEMENT AT SCALE: LEARNING THE NORM, SHIELDING THE TAIL (MLSys 2026)

> **一句话总结**：云 VM 跨 [[NUMA]] 错误放置可导致 **30%** 性能损失且规则策略难适配多样拓扑/负载；Catur 用 **placement defect**（core+memory defect）作 RL 奖励，配合 robust action、drift-aware 训练与 speculative shielding，在 1 亿 VM 生产 trace 上平均 defect 降 **34–50%**（**1.5–2×**），correctable anomaly 降 **13–23×**。

## 问题与动机

数据中心 [[NUMA]] 不对称使 VM 远程内存/超卖 vCPU 引发尾延迟（ScyllaDB/Azure/AWS 案例）。规则放置器难覆盖 VM 配置空间、硬件拓扑漂移与 workload 演变。Catur 在 HyperX 生产 hypervisor 上用 RL 从生产数据学习放置，并处理 model collapse 与尾 VM 异常。

## 关键观察 / 隐含假设

- **观察 1：placement defect = α×core_defect + β×memory_defect 可量化 NUMA 决策质量。** core_defect 捕获每 NUMA 超卖 vCPU；memory_defect 捕获远程内存比例。
  - **依赖假设**：线性组合默认 α=β=1；已知服务类型可调权重。
  - **可能失效场景**：NUMA-unaware 应用 defect 与 QoE 相关性弱。

- **观察 2：生产 trace 一个月有 **~25%** 未见 RL state，导致 model collapse（defective VM 4.5%→19%）。**
  - **依赖假设**：drift-aware continuous training + robust action space 可抑制。
  - **可能失效场景**：剧烈集群架构变更需重训。

- **观察 3：speculative shielding（1-step 模拟）把 correctable performance anomaly 从 **222K–383K** 降到 **~17K**（相对启发式 **13–23×**）。**
  - **依赖假设**：轻量模拟成本可接受于在线路径。
  - **可能失效场景**：模拟与真实性能偏差时 shield 误杀好放置。

- **假设 1**：单 VM 最多拆 2 个 vNUMA 实例，Catur 对全部实例统一决策。**
  - **证据强度**：**中**——匹配生产 trace 约束。

## 核心方法

**RL agent**：状态含 NUMA 资源与 VM 请求；动作选 NUMA 节点（robust action 防 collapse）。

**Reward shaping + drift-aware training**：应对 workload 漂移。

**Speculative shielding**：部署前模拟一步，拦截高 anomaly 风险放置。

**部署**：CloudX early trial；训练效率 vs vanilla **16.4×**，成本 **-93.9%**。

## 设计取舍

- **RL vs 规则**：适应复杂拓扑（4 NUMA/socket-aware **5.97×** Ticket Ratio），但运维黑盒。
- **Shielding vs 平均 defect**：换少量平均性能换尾 QoE。
- **生产数据训练 vs 隐私**：需大规模 trace 访问。
- **边界条件**：100M VM trace；Xen/Nova-Pack 等启发式 baseline。

## 实验与结果

- 平均 placement defect：**34.2–50.0%** 降（**1.5–2×** vs SOTA policies）。
- Correctable anomalies：**13–23×** 优于启发式。
- 复杂 4-NUMA 拓扑：socket-aware **5.97×** Ticket Ratio。
- Training：效率 **16.4×**，成本 **-93.9%** vs vanilla training。

## Critical Analysis

### 论证链条

NUMA 尾问题普遍 → defect metric → RL+shield → 生产 scale 验证，系统论文链条完整。RL 泛化到新硬件代际需持续 retrain 证据仍有限。

### 假设压力测试

GPU/ML workload VM 的 defect-QoE 映射可能不同。多租户争抢下「好放置」可能被邻居噪声淹没。

### 实验可信度

1 亿 VM trace 极强；SPECjbb 等基准补充。缺：公开复现 RL 训练栈。

### 系统性缺陷

论文未讨论 RL 策略可解释性、失败回滚、与 cluster autoscaler 联动。对抗性 VM 规格 gaming defect 未覆盖。

## 局限与 Future Work

- **局限 1**：绑定 HyperX/CloudX 栈。
- **局限 2**：RL 漂移需持续训练运维。
- **Future work 1**：defect 与 ML training job 完成时间联合标定。
- **Future work 2**：与 [[Guard]] 类 straggler 检测联动 VM 迁移。

## 相关

- **相关概念**：[[NUMA]]、[[VM-Placement]]、[[Reinforcement-Learning]]
- **同类系统**：Xen、Nova-Pack 启发式
- **同会议**：[[MLSys-2026]]