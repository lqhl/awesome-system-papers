---
type: paper
name: DINGO
full_title: Scaling the IO wall with Declarative IO
authors: [Sanjith Athlur, Sara McAllister, Theo Gregersen, Timothy Kim, Yiwei Chen, et al.]
venue: OSDI
year: 2026
tags: [distributed-storage, hdd, maintenance-io, io-scheduling, caching]
source_pdf: "[[osdi26-athlur.pdf]]"
source_md: "[[osdi26-athlur]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 用声明式 IO 跨越存储 IO 墙（OSDI 2026）

> **原题**：Scaling the IO wall with Declarative IO

> **一句话总结**：六家 hyperscaler 的测量显示维护任务占 after-cache HDD IO 的 45%–70%，且跨任务重用通常相隔过久；DINGO 让任务声明数据集合与 deadline 并集中对齐访问，在 HDFS 原型中少读 26%，在 100 PB 仿真中少读 28%–51%，从而把可用 HDD 容量上限提高约 1.7 倍。

## 问题与动机

HAMR 等技术持续增加 HDD 容量，却没有同比增加单盘带宽与 IOPS，因此每 TB 可获得的 IO 快速下降。作者将容量增长最终受制于设备 IO 的现象称为 IO 墙（IO wall）：在相同维护读需求下，传统系统约到 36 TB 设备便耗尽可分配给维护任务的磁盘时间。

进一步增加 SSD cache 不能根治问题。前台应用中容易复用的数据已经大多被 cache 吸收，落到 HDD 的请求越来越多是 scrubbing、reconstruction、rebalancing、garbage collection 和 transcoding 等大范围扫描。对六家 hyperscaler 的分析显示，这些维护任务至少消耗 45%–70% 的 HDD IO，而且需求往往随存储容量线性增长。

论文的机会来自跨任务重用：单个任务内部很少复用，但不同任务会访问相同 block；只是独立团队和软件层通过 read/write 发出的命令式请求在时间上错开，cache 看不到这种重用。作者提出声明式 IO（Declarative IO），把“何时、以何种顺序、读哪些候选数据”的自由度交给存储系统统一安排。

## 关键观察 / 隐含假设

- **观察 1**：六家 hyperscaler 的 after-cache HDD IO 中，维护任务占 45%–70%；Google 一周 trace 中，24 小时重排窗口内约 24% 的读冗余，七天窗口内约 42%（§3、图 4–7）。
  - **依赖假设**：这些匿名或聚合 workload 能代表未来大容量 HDD 集群；维护读仍会随容量增长，而不会被介质、编码或应用结构变化消除。
  - **可能失效场景**：全闪存层级、维护任务已被强协调、数据非常热，或 maintenance IO 并非主导瓶颈的系统。
- **观察 2**：维护任务通常只要求在 deadline 前覆盖某组数据，对访问时间、顺序乃至具体 block 有自由度，但 imperative IO 隐藏了这些自由度（§3.4、图 9–10）。
  - **依赖假设**：业务能给出足够长且可信的 deadline，任务也能改为 callback 驱动；紧急 reconstruction 等任务仍须走 imperative 路径。
  - **可能失效场景**：维护工作本身延迟敏感、候选数据很少，或任务团队无法配合新 API。
- **假设 1**：Declarative IO 主要操作 append-only 系统中已经 sealed、不可原地修改的 block；删除、权限变化和新 append 由 callback 后的普通读及任务自身处理（§4.4）。
  - **证据强度**：中。HDFS 原型验证了该模型，但原地更新、事务性对象或复杂 metadata 语义未被覆盖。
- **假设 2**：磁盘 IO 是首要稀缺资源，callback 时有足够 compute，短期 pin cache 能承接被对齐的重用。
  - **证据强度**：中。实验测量了磁盘读和前台延迟，但 write、CPU、network 与 compute admission 尚未纳入调度目标。

## 核心方法

Declarative IO 的 `declare` 接口接收若干 `BlockSet`、必须完成的集合数量 `sets_needed`、deadline 与 callback。任务可以一次声明完整扫描范围，IO Planner 再选择访问顺序与时机；若任务只需候选集合的一部分，例如 capacity balancing，则 `sets_needed` 还能显式暴露数据选择自由度。callback 只通知任务此刻适合读取哪些 block，真正的读取仍走原 imperative API，从而复用既有 lease、权限与一致性机制。

DINGO 在 append-only 分布式文件系统旁增加 IO Planner。每个 scheduling quantum 内，Planner 计算各 declaration 为按时完成所需的 IO rate，优先调度所需 rate 更高的 declaration；本 quantum 已被其他任务选择的 block 被视为“免费”，同一 declaration 内优先选择免费 block 较多的 `BlockSet`。该启发式刻意优先 deadline，而非求解 NP-hard 的全局最优重用。

长 quantum 有利于控制调度开销，却意味着需要很大 cache 才能保存整个 quantum 的重用。DINGO 因此把调度结果拆成更小的 dispatch group，并利用 erasure-coding group 的索引将重叠搜索从朴素的二次复杂度降到对 scheduled `BlockSet` 的线性扫描。IO Planner 同时发出 cache directive，把当前 dispatch round 的 block 放入专用小空间并临时 pin，避免普通 replacement policy 提前驱逐或将维护流量误判成热点。

文件级 declaration 在提交时由 metadata service 翻译成 block snapshot。deadline 无法满足时 callback 标记 `overloaded=true`，任务回退到普通读；删除 block 可省略 callback，新 append 则需新 declaration。这使优化不会改变 sealed block 的内容语义，但把处理 stale metadata、compute availability 和 overload 的责任显式留给调用方。

## 设计取舍

- **deadline 优先于最优重用**：rate-based heuristic 保证可预测进度和可扩展性，代价是可能错过未来更好的重叠；仿真中距无约束理论下界少于 5%，但这个差距依赖所测 workload。
- **任务负责最终读取**：保留已有 consistency、failure handling 和 access control，代价是 callback 与实际读之间可能失配，造成 cache miss 或重复 IO。
- **集中 planner**：获得跨团队、跨软件层的全局视野和统一 rate limit，却引入高内存控制面与故障/过载集中点；1 EB 配置峰值内存为 205 GB。
- **边界条件**：对长 deadline、扫描型、block 不可变且有明显数据重叠的 maintenance workload 最有效；对 urgent repair、原地更新、短任务或多资源瓶颈会变脆。

## 实验与结果

- 在 10 节点 HDFS 原型、18 TB 初始数据、四类维护任务和 81 小时实验中，DINGO 每个 logical byte 只产生 0.74 个 disk-read byte，比未修改 HDFS 少 26%；planner 预测值为 28%（§6.2、图 14）。
- 加入基于 Alibaba block trace 的前台读后，DINGO 与 baseline 吞吐分别为 6.82 与 6.36 MB/s；平均 P50 延迟为 86 与 167 ms，平均 P99 为 832 与 1181 ms，但集中 transcoding write 仍会造成阶段性延迟升高（§6.2、图 15）。
- 在 100 PB、30 天、3 小时步长的两个 hyperscaler workload 仿真中，DINGO 减少 28%–51% 的维护读；48 TB 盘、2 MB/s/TB 维护需求下，Cluster A 的 disk-head utilization 从 64% 降至最低 34.8%（§6.1–6.2、图 16）。
- 当维护任务最多占 50% 磁盘带宽时，imperative 系统支持约 36 TB 盘，DINGO 在 Cluster A/B 分别支持 64/58 TB，即容量上限提高 1.7/1.5 倍（图 16b）。
- 1 EB、2 MB/s/TB 的仿真中，单台 240 GB RAM 服务器在 15 分钟内算完一小时 quantum 的 dispatch group，峰值内存 205 GB；说明算法可运行，但控制面资源并不轻量（§6.2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| maintenance IO 已成为 HDD 的主要不可缓存需求 | §3、图 4–7：六家 hyperscaler 为 45%–70%，七天窗口重用约 42% | 匿名聚合数据；三家给出任务拆分，一家给出 block trace | 强 |
| Declarative IO 能在真实系统中减少物理读 | §6.2、图 14：比 HDFS baseline 少 26% disk-read bytes | 10 节点、18 TB、四类任务、81 小时 | 强 |
| DINGO 能让更大 HDD 在同一 IO 预算内可用 | §6.2、图 16：36 TB 提至 64/58 TB | 100 PB 模拟、两个 workload、2 MB/s/TB、维护占用上限 50% | 中 |
| 对齐维护 IO 不恶化前台读延迟 | §6.2、图 15：平均 P50 86 vs 167 ms，P99 832 vs 1181 ms | 单一 trace 驱动读负载；write burst 仍会伤害阶段延迟 | 中 |
| Planner 可扩展到 exabyte 控制面 | §6.2：一小时 quantum 少于 15 分钟，峰值 205 GB | 单服务器仿真，未验证控制面 HA 与线上 churn | 中 |

## 批判性分析

### 论证链条

论文从生产测量建立“维护 IO 主导且跨任务有远距离重用”，再用新接口暴露自由度，用原型证明机制可工作、用仿真外推容量收益，整体链条完整。最重要的外推发生在 1.7 倍容量结论：它不是 64 TB 生产集群的直接部署结果，而是结合 workload mix、设备模型、50% 维护 IO 预算与 100 PB 仿真得到的容量边界，应理解为条件性 capacity-planning 结论。

### 假设压力测试

核心收益随 declaration deadline、block overlap 和候选集合增大。任务 deadline 较短、多个任务的数据不重叠，或工作集中到 CPU/network/write bottleneck 时，节省会下降。更危险的是 overload 后回退 imperative IO：若部署容量已经依赖预期重用，deadline miss 会增加读负载并诱发 metastable failure；论文识别了风险，却没有给出 admission control、容量安全裕量或闭环恢复实验。

### 实验可信度

原型 baseline 是同配置 HDFS，物理读和前台 P50/P99 均被测量，仿真还以对应原型校验到 5% 内，证据组合较强。局限是原型只有 18 TB 且任务种类缩至四种，大规模结论主要来自参数化模拟；hyperscaler trace 无法公开复核，Optimal 又忽略 deadline 和 quantum 限制，只是宽松下界。论文也未系统比较“各任务统一 rate limit + 手工有限协调”等更易部署的中间方案。

### 系统性缺陷

新接口需要多个组织和软件层修改维护任务，并维护 declaration lifecycle；论文未量化迁移与运维成本。单 planner 在 1 EB 已使用 205 GB 内存，故障恢复、状态复制、重复 callback、control-plane partition 和 declaration churn 没有经过 fault-injection。调度只以 read IO 为预算，图 15 已显示 clustered transcoding write 会伤害延迟，说明多资源隔离尚不完整。access control 被推回 callback 后的 imperative read，保证了正确性，却可能降低实际复用并放大调度预测误差。

## 局限与后续工作

- **局限 1**：适用对象限定为 sealed immutable block；原地更新、事务快照和跨对象一致性没有实现或评测。
- **局限 2**：1.7 倍容量收益依赖仿真与固定 workload mix，缺少 48–64 TB 设备上的长期 production deployment。
- **局限 3**：Planner 的 HA、恢复、过载和 metastability 仅定性讨论，未做 failure-injection。
- **后续工作 1**：在公开 trace 上改变 deadline、overlap、cache pin 时间与 declaration churn，测出 IO savings 低于容量规划安全线的相变边界。
- **后续工作 2**：把 write bandwidth、CPU、network 和前台 tail-latency SLO 加入 scheduler，并用与图 15 相同 workload 检验 P99 是否始终不劣于 baseline。
- **后续工作 3**：实现 replicated IO Planner，注入 crash、partition、重复 callback 与大规模 deadline miss，客观验证 exactly/at-least-once 行为及恢复后的额外 IO。

## 相关

- **相关概念**：[[Declarative-IO]]、[[IO-Wall]]、[[Cache-Reuse]]、[[Erasure-Coding]]
- **同类系统**：[[HDFS]]、[[Ceph]]、[[Tectonic]]
- **同会议**：[[OSDI-2026]]
- **对比**：[[DINGO-vs-Imperative-IO]]
