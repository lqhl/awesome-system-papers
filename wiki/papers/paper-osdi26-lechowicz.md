---
type: paper
name: SPADE
full_title: SPADE: Signal-Aware DAG Scheduling and Dynamic Provisioning for Data Processing Clusters
authors: [Adam Lechowicz, Rohan Shenoy, Noman Bashir, Mohammad Hajiesmaili, Adam Wierman, Christina Delimitrou]
venue: OSDI
year: 2026
tags: [dag-scheduling, signal-aware-computing, carbon-aware, spark, resource-provisioning]
source_pdf: "[[osdi26-lechowicz.pdf]]"
source_md: "[[osdi26-lechowicz]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向外部信号的 DAG 调度与动态供给（OSDI 2026）

> **原题**：SPADE: Signal-Aware DAG Scheduling and Dynamic Provisioning for Data Processing Clusters

> **一句话总结**：SPADE 假设批处理 DAG 可以等待更有利的外部信号，通过把 DAG 中任务的相对重要性与当前碳强度或电力信号结合，在高信号时保护瓶颈任务、延后低重要性任务；在 Spark 原型和模拟器中，它将碳排放降低 32.9%，并以有限的整体 makespan 增幅换取这一收益。

## 问题与动机

数据中心面对的约束不再只有机器内部的 CPU、内存和网络容量。碳强度、电价、可用功率和用水条件都会随时间变化。交互式服务通常无法等待，但批量数据处理工作负载具有时间弹性，适合把执行推迟到信号较低的时段。

Spark 作业以有向无环图（DAG）表示。只按外部信号统一缩减资源，会在错误的时刻停住关键路径上的任务，延迟会传播到所有下游阶段；只做 DAG 调度又无法利用信号变化。论文因此把任务调度和资源供给视为一个联合决策，而不是把信号感知资源配额叠加到现有调度器上。

## 关键观察 / 隐含假设

- **观察 1：DAG 中任务的重要性不均匀。** 高分或高概率任务通常对应瓶颈任务，推迟它们会阻塞较长的下游路径；低重要性任务则更适合在高信号时暂缓。该判断来自图 1、图 3 的示例及对 Decima、Graphene 任务分布的抽象（§2.2、§3.1）。
  - **依赖假设**：底层 scorer 能把 makespan 意义上的瓶颈任务排在前面。
  - **可能失效场景**：DAG 很平坦、任务同质，或 scorer 对新工作负载失配时，相对重要性提供的信息有限。
- **观察 2：信号波动越大，等待低信号时段的收益越高，但等待也会拉长完成时间。** SPADE 用参数 α 控制这一取舍；α=0 恢复信号无关调度，α=1 最积极地遵循信号（§2.2、§3.1）。
  - **依赖假设**：信号上下界可由历史数据或短期预测得到，且批处理任务确实允许延迟。
  - **可能失效场景**：信号近似平坦、预测窗口不可靠，或作业存在严格截止时间时，等待收益可能不足以抵偿延迟。
- **假设 3：系统可以在线运行且不知道未来信号。** 论文只要求信号有已知上下界，并在信号变化或调度事件发生时重新决策。
  - **证据强度**：强。问题定义、算法和实验都采用在线信号模型（§2.1、Algorithm 1）。

## 核心方法

SPADE 接收底层 DAG 调度器产生的 ready-task 分数或概率分布 D(t)。它对候选任务 v 的分数按当前候选集合中的最大值归一化，得到相对重要性 r(v,t)。高分任务的 r 接近 1，低分任务的 r 接近 0。该设计复用了 [[Decima]] 和 [[Graphene]] 的 DAG 结构信息，但不要求 SPADE 重新训练 scorer。

每次调度事件，SPADE 从 D(t) 中采样任务，而不是直接选择 argmax。随后用一个随 α 和相对重要性变化的指数阈值函数比较当前信号 s(t)。高重要性任务的阈值接近最坏信号值，因此几乎总会执行；低重要性任务只有在信号足够好时才执行。采样是必要的：若始终选 argmax，该任务的相对重要性恒为 1，过滤器将无法延迟任何任务（§3.1）。

资源供给由同一个过滤器隐式完成。被拒绝的任务会让新释放的 executor 空闲；当整个集群将变为空闲时，算法仍强制派发任务以保证进度。系统还支持最低吞吐比例和目标截止时间两个操作员旋钮，但实验主要考察 α。

论文同时实现 SAP 作为消融：SAP 只根据外部信号调整集群可用 executor 数量，再交给 FIFO、Weighted Fair、Decima 或 Graphene 调度。它保留了信号感知供给，却丢失了任务级 DAG 信息，用于检验联合决策的价值。

## 设计取舍

- **任务级选择换来更好的帕累托取舍。** SPADE 需要接入 Spark 的 stage 选择、Kubernetes scheduler plugin 和外部信号 API；SAP 则可作为配额模块叠加到现有调度器，改造成本更低，但更容易在高信号时压住瓶颈。
- **指数阈值提供可解释旋钮，但不是全局最优解。** α 能连续调节信号响应程度，论文给出有限 stretch-factor 上界；然而 DAG 调度本身是 NP-hard，参数扫描得到的前沿不等于未知的真实帕累托前沿。
- **信号感知牺牲尾部 JCT。** 为降低全局碳或功率代价，单个作业可能在高信号期间长时间等待。最低配额和截止时间模式可限制这一风险，但论文没有完整评估它们。

## 实验与结果

- **原型结果**：在 100 个 executor 的 Spark-on-Kubernetes 集群上，使用六个区域的碳强度轨迹、TPC-H 和 Alibaba DAG，α=0.5 的 SPADE-Decima 平均碳排放较默认策略降低 32.9%，较 Decima 降低 32.1%（表 2、§5.3）。
- **原型延迟边界**：SPADE 相对默认策略的中位 JCT 增加 7.8%，P95 JCT 增加 45.4%；相对 Decima 的 P95 增加 59.6%。平均 makespan 相对默认仅增加 1.3%，相对 Decima 增加 12.4%（图 6、表 2）。
- **模拟器结果**：在完整碳和可用功率轨迹上，SPADE-Decima 较 FIFO 的碳排放降低 39.7%，较 Decima 降低 23.1%；SPADE-Graphene 较 FIFO 降低 40.1%，较 Graphene 降低 25.7%（表 3、§5.4）。
- **电力信号**：SPADE-Graphene 较 FIFO 将 power overloading 降低 51%，较 Graphene 降低 26.5%（表 3）。
- **联合决策消融**：在碳节省 35%–45% 的区间，SPADE-Decima 的 makespan 增幅平均为 7.9%，SAP-Decima 为 42.7%；SPADE-Graphene 为 1.2%，SAP-Graphene 为 17.7%（图 13、§5.4）。
- **工作负载边界**：当 DAG 具有长依赖链或高度连接的关键任务时，SPADE 优势最大；平坦 DAG 或单阶段作业中，SAP 式统一供给已经能捕获大部分收益（§5.4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 联合调度与供给比仅调整资源配额更有效 | 图 13：相同碳节省下 SPADE 的 makespan 增幅明显更小 | TPC-H、Alibaba DAG；Spark 模拟器；Decima/Graphene scorer | 强 |
| SPADE 能降低外部信号代价 | 表 2、表 3：碳排放降低 32.9%–40.1%，功率过载降低最高 51% | 六个碳轨迹、八个 Google power trace；中等信号感知参数 | 强 |
| 性能损失主要集中在尾部 JCT | 图 6、图 10：P95 增幅高于中位数，平均 makespan 增幅较小 | 连续到达的批处理作业；实验规模有限 | 中 |
| 相对重要性依赖底层 scorer 识别瓶颈 | 定义 3.1–3.2 及 §3.1 的 black-box 假设 | 未系统评估 scorer 错误或分布外 DAG | 中 |

## 批判性分析

### 论证链条

论文的主链条较完整：信号波动带来等待机会，DAG 瓶颈决定哪些任务不能等待，relative importance 将两者合并，图 13 的 SAP 对照验证了任务级信息的价值。理论上，α=0 的退化性质和 stretch-factor 上界解释了为什么系统不会无限等待。

但“保持整体吞吐”需要谨慎理解。原型中 SPADE 相对默认 makespan 只增加 1.3%，而模拟器中相对 Decima 增加 7.7%；论文的主结论依赖于把全局 makespan 作为 throughput 代理，不能直接推出每个租户的服务质量都得到保持。

### 假设压力测试

实验把碳轨迹按 1 分钟对应 1 小时进行时间缩放，以模拟长时间数据处理。这便于在实验中观察信号变化，却不等价于真实集群中的所有作业；短作业、突发到达和信号 API 延迟可能改变等待收益。信号上下界取 48 个时隙 lookahead 窗口的最大最小值，也把预测或历史窗口质量隐藏在参数中。

SPADE 依赖分数分布表达跨作业公平性。论文认为采样能继承 Graphene 等 scorer 的公平属性，但随机采样是否在高负载、不同优先级和强制截止时间下仍满足可接受的隔离，缺少独立测量。

### 实验可信度

论文同时使用真实 Alibaba DAG、TPC-H、六个碳轨迹和 Google 集群功率轨迹，并有 Spark 原型与高保真模拟器，覆盖面较好。SAP 是针对联合设计的直接消融，且比较了 Decima、Graphene、Weighted Fair 和 GreenHadoop。

边界在于：原型只有 50 个 worker、100 个 executor，单作业最多 25 个 executor；实验主要使用 CPU/内存 quota，没有报告信号获取、scheduler plugin 和 scorer 推理的运行时开销。Simulator 与 Kubernetes 原型的 FIFO 行为不同，论文虽解释了差异，但跨环境的绝对数值不宜直接比较。

### 系统性缺陷

高 P95 JCT 是最直接的运维风险。论文没有报告租户级公平、优先级抢占、故障恢复、信号失真、executor 创建失败或 quota 更新失败时的行为。实现依赖修改 Spark、定制 Kubernetes scheduler 和动态 allocation；这些组件的版本兼容与升级成本也未量化。系统不做 preemption，信号突然变差时已有 executor 仍会继续运行，短时响应可能偏离目标。

## 局限与后续工作

- **局限 1**：相对重要性是由外部 scorer 间接提供的，若 scorer 未识别真实关键路径，SPADE 的保护策略会继承该错误。
- **局限 2**：实验没有充分覆盖严格 SLO、多租户优先级和作业取消；P95 JCT 的增幅说明这些场景不能只看平均 makespan。
- **后续工作 1**：在真实 trace 回放中加入可预测性受控的信号误差，测量 α、lookahead 窗口和信号刷新延迟对碳节省与 P99 JCT 的影响。
- **后续工作 2**：构造 scorer 失配和 DAG 结构变化的实验，比较 relative importance 与关键路径 oracle 的差距，并验证最低配额/目标截止时间是否能给出可执行的租户 SLO。

## 相关

- **相关概念**：[[DAG Scheduling]]、[[Carbon-Aware Computing]]、[[Resource Provisioning]]
- **同类系统**：[[Decima]]、[[Graphene]]、[[GreenHadoop]]
- **同会议**：[[OSDI-2026]]
