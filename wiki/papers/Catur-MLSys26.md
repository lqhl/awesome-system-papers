---
type: paper
name: Catur
full_title: "VIRTUAL MACHINE NUMA PLACEMENT AT SCALE: LEARNING THE NORM, SHIELDING THE TAIL"
authors: [Yibo Zhao, Tianyuan Wu, Hui Xue, Qi Chen, Zhenhua Han, et al.]
venue: MLSys
year: 2026
tags: [numa, cloud, reinforcement-learning, vm-placement, hypervisor]
source_pdf: "[[ea5d2f1c4608232e07d3aa3d998e5135.pdf]]"
source_md: "[[ea5d2f1c4608232e07d3aa3d998e5135]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Catur：大规模虚拟机 NUMA 放置——学习常态、保护长尾（MLSys 2026）

> **原题**：VIRTUAL MACHINE NUMA PLACEMENT AT SCALE: LEARNING THE NORM, SHIELDING THE TAIL

> **一句话总结**：Catur 用 placement defect 奖励、robust action、持续训练和 speculative shielding 学习云 VM 的 [[NUMA]] 放置；在 CloudX 一个月、1 亿 VM 的 trace replay 中，Ticket Ratio / placement defect 为 0.66% / 0.73%，并把可纠正异常从启发式策略的 222K–383K 降至约 17K（§6.1–6.3，Table 1，Fig. 15）。

## 问题与动机

数据中心 [[NUMA]] 不对称使 VM 远程内存/超卖 vCPU 引发尾延迟（ScyllaDB/Azure/AWS 案例）。规则放置器难覆盖 VM 配置空间、硬件拓扑漂移与 workload 演变。Catur 在 HyperX 生产 hypervisor 上用 RL 从生产数据学习放置，并处理 model collapse 与尾 VM 异常。

## 关键观察 / 隐含假设

- **观察 1：placement defect = α×core_defect + β×memory_defect 可量化 NUMA 决策质量。** core_defect 捕获每 NUMA 超卖 vCPU；memory_defect 捕获远程内存比例。
  - **依赖假设**：线性组合默认 α=β=1；已知服务类型可调权重。
  - **可能失效场景**：NUMA-unaware 应用 defect 与 QoE 相关性弱。

- **观察 2：生产 trace 一个月约有 25% 未见 RL state，可能导致 model collapse（defective VM 4.5%→19%）。**
  - **依赖假设**：drift-aware continuous training + robust action space 可抑制。
  - **可能失效场景**：剧烈集群架构变更需重训。

- **观察 3：speculative shielding（1-step 模拟）把 correctable performance anomaly 从 222K–383K 降到约 17K（相对启发式 13–23×，§6.3，Fig. 15）。**
  - **依赖假设**：轻量模拟成本可接受于在线路径。
  - **可能失效场景**：模拟与真实性能偏差时 shield 误杀好放置。

- **假设 1**：单 VM 最多拆 2 个 vNUMA 实例，Catur 对全部实例统一决策。
  - **证据强度**：**中**——匹配生产 trace 约束。

## 核心方法

**RL agent**：状态含 NUMA 资源与 VM 请求；动作选 NUMA 节点（robust action 防 collapse）。

**Reward shaping + drift-aware training**：应对 workload 漂移。

**Speculative shielding**：部署前模拟一步，拦截高 anomaly 风险放置。

**部署**：CloudX early trial；连续微调把单轮训练时间从 784 小时降至 48 小时，即减少 93.9%（§6.3，Fig. 13）。

## 设计取舍

- **RL vs 规则**：适应复杂拓扑（4 NUMA/socket-aware **5.97×** Ticket Ratio），但运维黑盒。
- **Shielding vs 平均 defect**：换少量平均性能换尾 QoE。
- **生产数据训练 vs 隐私**：需大规模 trace 访问。
- **边界条件**：100M VM trace；Xen/Nova-Pack 等启发式 baseline。

## 实验与结果

- **生产 trace replay**：CloudX 一个月 1 亿 VM trace，前 15 天训练、后 15 天测试；相对 Xen、Nova、Tetris 和 E-PVM baseline，Catur 的 Ticket Ratio / placement defect 为 0.66% / 0.73%，baseline 分别为 0.94% / 1.11%、1.22% / 1.33%、1.28% / 1.46% 和 1.22% / 1.41%（§6.1–6.2，Table 1；硬件未披露）。
- **尾部异常**：相同 replay、默认 shielding depth 1 下，Catur 的可纠正异常约 17K，启发式 baseline 为 222K–383K，即少 13–23×；异常由论文的 Oracle placement 定义（§6.3，Fig. 15）。
- **Reward shaping ablation**：一个生产 cluster、50 epochs 下，Ticket Ratio 为 0.08%，no-shaping 与 MemMostIdle 分别为 0.48% 和 0.41%；variance 为 0.18，而 no-shaping 为 0.64（§6.3，Fig. 14）。
- **持续训练**：11 次迭代中 Ticket Ratio 从 0.72% 降至 0.68%，单轮训练时间从 784 小时降至 48 小时；初始模型使用 10% clusters，并持续加入表现最差的 5% clusters（§4.4、§6.3，Fig. 13）。
- **拓扑敏感性**：五类 workload 均匀分配的受控实验中，placement defect 从 7.23 降至 3.08，Ticket Ratio 从 5.94% 降至 0.10%（§6.4；硬件配置见论文 appendix）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Catur 在生产 trace replay 中优于四个放置 baseline | §6.1–6.2, Table 1 | CloudX；100M VMs；days 1–15 train / 16–30 test；硬件未披露 | strong |
| Speculative shielding 将可纠正异常降至约 17K | §6.3, Fig. 15 | 相同 replay；depth 1；Oracle-defined anomalies | strong |
| Reward shaping 将 Ticket Ratio 降至 0.08% | §6.3, Fig. 14 | 单个 cluster；50 epochs；对比 no-shaping 与 MemMostIdle | strong |
| 持续训练把单轮训练时间从 784 小时降至 48 小时 | §4.4, §6.3, Fig. 13 | 11 iterations；initial 10% clusters；每轮加入 worst 5% | strong |
| Catur 在复杂拓扑压力测试中降低 defect 与 Ticket Ratio | §6.4 | 五类 workload 均匀分配；受控硬件见 appendix | medium |

## 批判性分析

### 论证链条

NUMA 尾问题普遍 → defect metric → RL+shield → 生产 scale 验证，系统论文链条完整。RL 泛化到新硬件代际需持续 retrain 证据仍有限。

### 假设压力测试

GPU/ML workload VM 的 defect-QoE 映射可能不同。多租户争抢下「好放置」可能被邻居噪声淹没。

### 实验可信度

1 亿 VM trace 极强；SPECjbb 等基准补充。缺：公开复现 RL 训练栈。

### 系统性缺陷

论文未讨论 RL 策略可解释性、失败回滚、与 cluster autoscaler 联动。对抗性 VM 规格 gaming defect 未覆盖。

## 局限与后续工作

- **局限 1**：绑定 HyperX/CloudX 栈。
- **局限 2**：RL 漂移需持续训练运维。
- **Future work 1**：defect 与 ML training job 完成时间联合标定。
- **Future work 2**：与 [[Guard]] 类 straggler 检测联动 VM 迁移。

## 相关

- **相关概念**：[[NUMA]]、[[VM-Placement]]、[[Reinforcement-Learning]]
- **同类系统**：Xen、Nova-Pack 启发式
- **同会议**：[[MLSys-2026]]
