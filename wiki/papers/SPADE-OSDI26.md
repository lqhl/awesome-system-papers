---
type: paper
name: SPADE
full_title: "SPADE: Signal-Aware DAG Scheduling and Dynamic Provisioning for Data Processing Clusters"
authors: [Adam Lechowicz, Rohan Shenoy, Noman Bashir, Mohammad Hajiesmaili, Adam Wierman, Christina Delimitrou]
venue: OSDI
year: 2026
tags: [cluster-scheduling, dag, resource-provisioning, carbon-aware-computing]
source_pdf: "[[osdi26-lechowicz.pdf]]"
source_md: "[[osdi26-lechowicz]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# SPADE：面向外部信号的数据处理 DAG 调度与动态供给（OSDI 2026）

> **原题**：SPADE: Signal-Aware DAG Scheduling and Dynamic Provisioning for Data Processing Clusters

SPADE 将 DAG 内任务的重要性与碳强度、电价或可用功率等时间变化信号共同纳入决策，联合决定“何时调度任务”和“供给多少 executor”。

## 问题与动机

传统 Spark 等数据处理调度器假定资源供给稳定，主要优化 makespan；既有 signal-aware 系统则常把作业当黑盒，按外部信号整体伸缩。对具有前驱依赖的 DAG，错误地推迟瓶颈阶段会阻塞全部下游任务，因此独立组合“信号感知供给器”和“信号无关调度器”并不能得到良好的成本—性能权衡。

SPADE 面向可延迟的批处理作业，在未来信号未知、但上下界已知的在线环境中，同时优化集群吞吐与由信号定义的次级目标。

## 关键观察 / 隐含假设

### 关键观察

- 相同信号值下，不同 DAG 位置的任务不应受到相同抑制：关键路径或高连接度任务延迟一小段时间，也可能放大为整个作业的长停顿。
- 调度和供给是耦合决策。SAP 消融只做 signal-aware provisioning、继续使用普通调度策略，其 Pareto 权衡持续被 SPADE 支配。
- 现有 DAG scorer 已能表达任务对 makespan 的贡献；SPADE 无须重建调度器，只需把 scorer 输出转为跨作业可比的“相对重要性”。

### 隐含假设

- 外部信号的最小值与最大值可由历史或短期预测可靠界定，且作业具有足够时间弹性。
- 底层 DAG scorer 至少能合理识别瓶颈；若 scorer 本身排序错误，SPADE 会继承并放大这一误差。
- 碳强度或功率信号可作为执行成本的近似，任务功耗与 executor 数量之间足够接近论文模型。

## 核心方法

### 相对重要性

SPADE 将底层 FIFO、Graphene 或 Decima 等调度器给出的任务分数归一化，得到任务相对于当前可运行集合的重要性。重要任务即使处于“不利”信号区间也优先执行，低重要性任务则更适合等待信号改善。

### 阈值式在线决策

系统借鉴 online search 的 threshold design，把信号上下界、任务相对重要性和用户指定的 signal-awareness 参数组合为指数阈值。参数在追求 makespan 与追求次级目标之间提供连续旋钮，同时通过保底规则保证作业不会无限等待。

### 联合调度与供给

每个决策周期，SPADE 一方面选择应执行的 ready tasks，另一方面调整 Kubernetes 上的 Spark executors；供给量由当前信号和被选任务的重要性共同决定。SAP 消融保留同一供给逻辑，但把任务选择交回信号无关调度器，用来隔离联合设计的价值。

## 设计取舍

- SPADE 只假定信号上下界而不依赖完整未来预测，增强在线适用性，但不能利用高质量预测提前规划。
- 单一 signal-awareness 参数便于运营者配置，却不能直接表达每个作业的 deadline、优先级或公平性约束。
- 复用现有 DAG scorer 降低集成成本，也使最终质量受制于 scorer 对未知 workload 的泛化能力。
- 信号被处理为次级目标；对于严格功率上限等硬约束，仍需外部 enforcement layer 限制实际容量。

## 实验与结果

- 在 100 节点 Spark-on-Kubernetes 集群、Alibaba 与 TPC-H DAG workload 上，SPADE 相比默认基线最多减少 32.9% 碳排放，同时总体 makespan 增幅少于 5%，支持其成本—吞吐权衡主张（§5，图 7）。
- 对 Google 可用功率 trace，SPADE 相比 FIFO 将功率过载指标最多降低 51%；该结果衡量的是与可用功率的对齐，而非数据中心端到端能耗。
- 原型实验中，SPADE 的 32.9% 碳减排优于同组 SAP 的 24.7%；SAP 在获得相似次级目标收益时需要更大的 makespan 牺牲，验证 DAG-aware 联合决策的必要性。
- 模拟器中，相比 Decima 与 Graphene，SPADE 的平均 makespan 分别增加 7.9% 和 1.2%；SAP 的对应增幅更高，说明收益不是来自单纯减少 executor。
- 论文使用六个地区的真实碳强度 trace、Google 功率 trace，并通过 30 次试验报告部分结果的标准差；但 trace replay 未包含真实电网反馈与功耗计量误差。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| DAG 结构必须与信号联合考虑 | 用相对重要性保护瓶颈任务 | SPADE 碳减排 32.9%，同组 SAP 为 24.7% | 依赖底层 scorer 正确识别重要任务 |
| 可通过一个参数平滑控制成本—性能取舍 | 指数阈值随 signal-awareness 参数变化 | 参数 sweep 形成连续 Pareto 曲线 | 参数不等价于 deadline 或硬 SLO |
| 方法适用于不同外部信号 | 统一把有界信号映射为调度阈值 | 碳减排最高 32.9%，功率过载降低最高 51% | 只回放碳与功率 trace，未验证水或实时电价 |
| 联合设计可部署于现有数据处理栈 | Spark/Kubernetes 模块与可插拔 scorer | 100 节点原型和高保真模拟器结果一致 | 未报告长期生产部署和控制面故障 |

## 批判性分析

### 论证链条

论文先通过 DAG 瓶颈说明黑盒伸缩的结构性问题，再以 SAP 消融直接检验“调度与供给必须联合”这一核心论断。形式化在线策略给出有限等待性质，原型和模拟器则覆盖真实规模与更广参数空间，论证链条较完整。

### 假设压力测试

若未来信号突变超出已知上下界，阈值保证会失效；若作业并不 delay-tolerant，少于 5% 的集群平均 makespan 增幅仍可能违反单作业 SLO。异构机器、任务功耗差异及数据 locality 也可能使 executor 数量无法准确代表实际信号成本。

### 实验可信度

100 节点原型、真实 DAG/信号 trace、多个 scorer 和 SAP 消融使结果具有说服力。主要缺口是没有报告尾部 JCT、公平性、调度控制开销和真实功率测量；模拟器结果虽扩大覆盖面，仍依赖其 Spark 执行模型。

### 系统性缺陷

SPADE 优化的是集中式、单数据中心、可延迟 DAG workload。它没有解决互动服务与 batch 混部时的容量竞争，也未说明多个运营目标同时出现时如何组合信号。把复杂政策压缩成一个旋钮，可能隐藏不同租户之间由延迟换来的收益分配问题。

## 局限与后续工作

- 加入 per-job deadline、优先级与公平性约束，并报告尾部 JCT，而不只看总体 makespan。
- 使用真实功率计量和在线电网接口验证 trace replay 之外的闭环行为。
- 扩展到异构 executor、数据 locality、抢占成本和互动服务混部环境。
- 研究信号预测误差、范围越界和多个冲突信号下的鲁棒决策。

## 相关

- [[Spark]]
- [[Kubernetes]]
- [[Cluster-Scheduling]]
- [[Carbon-Aware-Computing]]
