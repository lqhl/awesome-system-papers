---
type: paper
name: SPADE
full_title: "SPADE: Signal-Aware DAG Scheduling and Dynamic Provisioning for Data Processing Clusters"
authors: [Adam Lechowicz, Rohan Shenoy, Noman Bashir, Mohammad Hajiesmaili, Adam Wierman, Christina Delimitrou]
venue: OSDI
year: 2026
tags: [cluster-scheduling, dag, resource-provisioning, carbon-aware-computing, spark]
source_pdf: "[[osdi26-lechowicz.pdf]]"
source_md: "[[osdi26-lechowicz]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# SPADE：感知外部信号的 DAG 调度与动态供给（OSDI 2026）

> **原题**：SPADE: Signal-Aware DAG Scheduling and Dynamic Provisioning for Data Processing Clusters

> **一句话总结**：外部信号很差时，统一缩减 executor 会误伤 [[DAG]] 瓶颈并阻塞下游；SPADE 用现有调度器的任务分数估计相对重要性，只推迟不重要任务并同步限制 stage 并行度，原型中模型估算的碳足迹相对 Spark/Kubernetes Default 降低 32.9%、平均 makespan 增加 1.3%，但 p95 JCT 增加 45.4%，而且碳结果来自 trace 与 executor 利用率模型，不是真实功率计量。

## 问题与动机

数据中心越来越需要根据随时间变化的外部信号安排计算，例如电网碳强度、电价、可用功率或用水压力。批处理作业可以把一部分工作从“信号差”的时段移到“信号好”的时段，但等待也会增加 job completion time（JCT）和整个批次的 makespan。

已有 signal-aware 方法常把一个作业或整个集群当作黑盒，只按当前信号改变资源配额。这对 [[Spark]] DAG 不够：一个低优先级 leaf task 可以安全等待，而关键路径上的 bottleneck task 一旦被推迟，所有依赖它的 stage 都不能开始。只把信号感知供给器接在信号无关调度器外面，可能省下一些碳，却付出不必要的长尾完成时间。

SPADE 面向可延迟的数据处理作业，把“现在运行哪个 ready task”和“给 stage 多少并行度”放进同一决策。它优化的是一个软的次级目标；论文明确指出，严格功率上限仍要由独立 enforcement layer 保证。交互服务、不可延迟作业和硬 deadline 不是主要评测对象。

## 关键观察 / 隐含假设

- **观察 1**：同一信号值下，DAG 中不同 ready task 的延迟代价不同；高分 bottleneck 应继续执行，低分 task 才适合等到低信号时段（§2.2、图 2、图 3）。
  - **依赖假设**：底层 scorer 的高分确实代表对 makespan 重要的任务。
  - **可能失效场景**：score 未校准、分布外 DAG、错误的关键路径估计，或真正目标是租户公平性而不是 makespan 时，相对重要性会选错任务。
- **观察 2**：只做供给的 SAP 消融实验不能识别 DAG bottleneck；在相同碳收益区间内，它比 SPADE 付出更大的 makespan 代价（§5.4、图 13）。
  - **依赖假设**：SPADE 与 SAP 的实现、scorer 和资源限制足够可比，拟合曲线没有掩盖离散 trial 的差异。
  - **可能失效场景**：DAG 很平、几乎所有 task 同时 ready，或作业接近单 stage 时，没有多少结构可利用，论文也承认 SPADE 相对 SAP 的优势会缩小。
- **观察 3**：现有 Decima、Graphene 等 DAG scheduler 已产生跨作业的 score/probability distribution，SPADE 可以作为过滤层复用，不必重新解决 DAG 排序（§3.1）。
  - **依赖假设**：归一化后的相对分数在每次事件上足够稳定，sampling 带来的随机性不会破坏公平性和尾延迟。
  - **可能失效场景**：一个异常高分 task 会压低其他 task 的相对重要性，或 scorer 的概率高度尖锐时，过滤行为可能不稳定。
- **假设 1**：运行时不知道未来每个信号值，但知道可靠的上下界。
  - **证据强度**：中弱。设计只使用当前信号和上下界；实验却把上下界设为未来 48 个 time slot 的最大值和最小值（§5.1），因此实际评测仍利用了有限 lookahead。
- **假设 2**：executor 利用率可以近似能耗，固定满载能耗乘以碳强度可代表碳足迹。
  - **证据强度**：弱。§5.1 给出模型，但没有功率计、idle power、非线性功耗、PUE、异构机器或 embodied carbon 的验证。

## 核心方法

SPADE（Scheduling and Provisioning for Adaptive DAG Execution）接收底层 DAG scheduler 对所有 active job 的 ready task 给出的分数或概率。论文使用 [[Decima]] 和 [[Graphene]]；前者由强化学习输出概率，后者把关键路径、packing efficiency 和 priority 编进分数。SPADE 把 scorer 当黑盒，并继承它的跨作业优先级与潜在偏差。

对候选任务，SPADE 用“该任务的概率除以当前 ready set 的最大概率”计算相对重要性，范围是 0 到 1。值为 1 的任务视为 bottleneck。系统把相对重要性、当前信号及一个 signal-awareness 参数放进指数 threshold：参数为 0 时退化为原调度器，参数为 1 时最重视外部信号；bottleneck 的 threshold 等于信号上界，因此任何信号下都放行（§3.1、图 2）。

SPADE 不是直接取最高分任务，而是按分布 sampling，再判断放行或等待。若总取 argmax，候选的重要性永远是 1，过滤器就永远不会推迟任务。Sampling 让低分 task 偶尔成为候选：低信号时执行，高信号时推迟；如果整个集群已没有 busy executor，系统仍强制放行一个任务来保证进展。论文还给出 minimum-throughput 和 target-deadline 接口，但主要实验只扫描 signal-awareness 参数。

调度与供给在实现中表现为两个动作：高信号时可以让新空出的 executor idle；每次 stage 被调度时，还按信号和参数降低底层 scheduler 给出的 parallelism limit。后者避免一次给单个 stage 太多 executor，挤掉其他 job。SAP 消融则只根据信号设置集群资源 quota，不看任务结构，也不抢占已经运行的 pod（§3.2、§4.1）。

作者把 SPADE 做成 Spark 3.5.3 的 scheduler plugin 和外部 scheduling service，并修改 Spark driver 来发送 DAG 更新、接受 stage 决策；资源层运行在 [[Kubernetes]] 1.31。另一个实现接入 Decima 的 Spark simulator，加入 SPADE、SAP、Graphene 和 GreenHadoop，以便回放完整的多年信号 trace（§4）。

理论上，SPADE 的 stretch factor 有有限上界，取决于 executor 数和被推迟任务的期望比例。这个结果说明算法不会无限卡住，但一般参数下没有闭式值，也没有直接给运营者一个可兑现的 per-job SLO。

## 设计取舍

- **复用 scorer，换取易集成**：SPADE 不重训一个多目标 scheduler；代价是公平性、priority 和 bottleneck 识别都继承自 scorer，论文没有单独验证这些性质。
- **Sampling 产生可推迟候选，换取随机性**：它解决 argmax 永远放行的问题，却可能增加 run-to-run variance 和单作业尾延迟。
- **一个连续参数，换取简单接口**：运营者容易扫描碳—性能曲线，但该参数不是 deadline、租户预算或硬 SLO。
- **非抢占式控制，换取 Spark 兼容性**：正在运行的长 task 不会被撤回，因此可能跨过整个高信号窗口；信号响应速度受 task duration 限制。
- **软信号优化，换取通用性**：同一机制能处理碳和可用功率，但不能独立保证 hard power cap，水与价格也只停留在动机中。

## 实验与结果

- 原型运行在 Chameleon Cloud 的 51 台 `m1.xlarge` VM 上：1 台 control plane、50 台 worker，每台 worker 放 2 个 pod，共 100 个 executor，每个 job 最多用 25 个。Alibaba DAG duration 被缩短到原来的 1/60，1 分钟真实时间对应 1 小时 carbon trace；每个设置跨 25、50、100 个 job batch 和六条碳 trace，平均 10 次 trial（§5.1、§5.3）。
- 中等 signal-awareness 下，SPADE-Decima 相对 Spark/Kubernetes Default 的模型碳足迹减少 32.9%，高于 SAP-Default 的 24.7%；平均 makespan 分别为 Default 的 1.013 和 1.126 倍。SPADE 相对 Decima 的碳足迹减少 32.1%；正文报告其 makespan 比 Decima 高 12.4%，这一百分比不能由表 2 的两个归一化均值 1.013 与 0.857 直接复算，论文未解释聚合口径（§5.3、表 2）。
- 同一原型中，SPADE 的 median JCT 相对 Default 和 Decima 分别增加 7.8% 与 11.8%，p95 JCT 则增加 45.4% 与 59.6%；SAP 的 p95 增幅达到 223% 与 254.4%。因此“makespan 代价较小”不等于单作业长尾代价较小（§5.3、图 6）。
- 完整 trace 模拟中，SPADE-Decima 相对 Decima/FIFO 的碳足迹分别减少 23.1%/39.7%，SPADE-Graphene 相对 Graphene/FIFO 分别减少 25.7%/40.1%；可用功率实验中，两者相对 FIFO 的 power-overload 指标分别减少 43.9% 和 51.0%。对应 makespan 相对各自 scorer 增加 7.7% 和 2.9%，相对 FIFO 增加 4.5% 和 1.1%（§5.4、表 3）。
- DE trace、50-job、十个参数设置中，在碳收益为 35%–45% 的 trial 上，SPADE-Decima/Graphene 的平均 makespan 增幅为 7.9%/1.2%，SAP 为 42.7%/17.7%；把 makespan 增幅限制在 0%–10% 时，SPADE 的碳收益为 35.6%/52.4%，SAP 为 20.1%/24.8%。这是参数扫描得到的经验前沿，不是未知全局 Pareto frontier 的证明（§5.4、图 13）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 保护 DAG bottleneck 能改善信号目标与 makespan 的权衡 | 图 13：相同 35%–45% 碳收益区间内，SPADE 的 makespan 增幅显著低于 SAP | DE trace、50 个 TPC-H job、经验 cubic fit | 强 |
| SPADE 能在真实 Spark/Kubernetes 栈中获得显著的模型碳收益 | 表 2：相对 Default 减少 32.9%，平均 makespan 为 1.013 倍 | 51 台 VM、100 executors、压缩时间、利用率能耗模型 | 强 |
| 低平均 makespan 代价会隐藏较大单作业尾延迟 | 图 6：p95 JCT 相对 Default 增加 45.4%，而平均 makespan只增加 1.3% | 原型六条碳 trace，delay-tolerant batch workload | 强 |
| 同一框架可处理碳强度和可用功率两种信号 | 表 3：相对 FIFO 碳足迹最多减少 40.1%，power overload 最多减少 51.0% | 模拟器、六条碳 trace 与八条 Google power trace | 强 |
| 方法不需要未来信号预测 | 设计只在每次事件读取当前信号；但 §5.1 的上下界来自未来 48-slot window | 理论模型与实验设置不完全一致 | 中弱 |

## 批判性分析

### 论证链条

论文的主线是闭合的：先指出 black-box provisioning 不理解 DAG，再用底层 scorer 提取 bottleneck 信息，最后以 SAP 消融直接比较“只供给”和“联合调度供给”。图 13 在相似碳收益或相似 makespan 区间内都显示 SPADE 更好，支持“DAG 结构有额外价值”。

不过，论文把三个不同参照系放在一起叙述：相对 FIFO/Default 的 makespan 增幅少于 5%，相对更强的 Decima/Graphene 则是 7.7%/2.9%，原型正文还报告相对 Decima 增加 12.4%。如果只记住“少于 5%”，会高估与底层强 scheduler 组合后的性能。平均 makespan 也不能代表用户看到的 JCT，p95 增幅已经达到 35.8%–59.6%。

### 假设压力测试

方法依赖 scorer 把高分分给真正的 makespan bottleneck。Graphene 的规则或 Decima 在 20,000 epoch 训练后可以适配论文 workload，但分布外 DAG、租户 priority 变化或新的 stage runtime 可能破坏排序。论文说 fairness 从 scorer 继承；sampling 与 signal filter 是否仍保持 per-tenant fairness 并没有实验证据。

在线设定也没有完全脱离预测：实验用未来 48-slot 的极值设置上下界。如果信号突然越界、forecast window 选错，指数 threshold 的尺度会改变。长而不可抢占的 task、executor 启动、shuffle 和 locality 开销还会让系统无法在信号变化时立即改变实际能耗。

### 实验可信度

优点是同时有可运行原型、完整 trace simulator、两个强 DAG scorer、多个 baseline 和直接的 SAP 消融。六个地区的三年小时级碳 trace与 Google 八个 production cell 的 5 分钟 trace 比单一合成波形更有代表性；论文也报告参数 sweep 与 trial variance。

主要缺口是碳足迹没有真实测量。模型把满载能耗设为常数，再乘 executor utilization 和碳强度；它不覆盖 idle power、DVFS、不同 stage 的 CPU/内存/网络功耗、PUE 或 embodied carbon。把 1 小时压成 1 分钟、把 Alibaba duration 缩短 60 倍，也会改变 pod 启动、task duration 和信号周期的相对尺度。模拟器虽引用既有“runtime error 在 5% 内”的验证，但作者指出其 FIFO 会过度分配 executor，与原型 Default 行为不同。

### 系统性缺陷

SPADE 的坏信号应对方式是等待，因此成本集中落在恰好于坏时段到达的 job 上。论文没有给出 admission control、租户补偿、per-job SLO 违约率或 starvation 分布。Target deadline 和 minimum-throughput 虽在设计中出现，却没有进入主实验。

系统还需要修改 Spark driver、维护外部 scheduling service，并依赖 scorer inference。论文未报告控制面延迟、service 故障时的 fallback、状态恢复或多 scheduler 冲突。对 hard power cap，作者要求额外 enforcement layer；两层控制若同时收紧资源，是否振荡或过度限流也没有讨论。

## 局限与后续工作

- **局限 1**：碳结果是 trace replay 与 executor-utilization 模型，不是整机或集群功率计量；water、price 和真实 curtailment 没有实验。
- **局限 2**：原型使用时间压缩、51 台同构 VM 和可延迟 batch job，没有覆盖异构 executor、shuffle locality、interactive co-location 与生产故障。
- **局限 3**：p95 JCT 代价很高，fairness、deadline violation 和每租户收益分配没有评测。
- **后续工作 1**：在同一组作业上同时记录 RAPL/BMC、PDU 与 executor utilization，报告模型碳估计对实测能耗的每 stage 误差和 p95 误差。
- **后续工作 2**：把 signal bound 加入 0、6、12、48-slot forecast error sweep，并注入越界突变，测碳收益、makespan、p95 JCT 和 hard-cap violation。
- **后续工作 3**：加入 per-job deadline 和 tenant weight，在不同到达时段分别报告 violation rate、slowdown 与 Jain fairness，而不是只看全局 makespan。
- **后续工作 4**：在 scorer service crash、driver 重启和 enforcement layer 同时限流时做 fault injection，验证调度状态恢复、进展保证和控制环稳定性。

## 相关

- **相关概念**：[[DAG]]、[[Cluster-Scheduling]]、[[Carbon-Aware-Computing]]、[[Dynamic-Resource-Provisioning]]
- **同类系统**：[[Spark]]、[[Kubernetes]]、[[Decima]]、[[Graphene]]、[[GreenHadoop]]
- **同会议**：[[OSDI-2026]]
