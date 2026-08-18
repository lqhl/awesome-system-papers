---
type: paper
name: Quark
full_title: "Stop Pretending to be Busy: A Case for Serverless Paradigms in Co-located Batch Workloads (Operational Systems)"
authors: [Xiaohu Chai, Jianfeng Tan, Congsi Yuan, Bowen Yang, Hao Dai, Tongkai Yang, Chao Huang, Dong Du, Yu Chen]
venue: OSDI
year: 2026
tags: [serverless, batch-processing, spark, colocation, scheduling, area/operating-systems]
source_pdf: "[[osdi26-chai.pdf]]"
source_md: "[[osdi26-chai]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 别再假装忙碌：共置批处理的 [[Serverless|Serverless 化]]（OSDI 2026）

> **原题**：Stop Pretending to be Busy: A Case for Serverless Paradigms in Co-located Batch Workloads (Operational Systems)

> **一句话总结**：Ant Group 的生产画像显示，Spark batch 获得的资源只有 67% 真正在计算；Quark 把长寿命 executor 改成 task 级按需实例，再用显式配额、干扰感知放置和安全 fork 缩短启动，生产迁移后每 job 资源消耗降低 37.37%，不平衡 stage 比例约从 15% 降到 2%。

## 问题与动机

Ant Group 把低优先级 Spark batch job 与高优先级在线服务共置。在线服务平均只实际使用 22.0% 的 CPU，共置和 overcommit 又收获了 26.8% CPU 容量；为了给故障恢复和突发流量留余量，节点总利用率仍控制在约 60% 以下（图 1）。这提高了“机器有多少资源被分配”，却没有回答“分到 batch 的资源有多少在做有用计算”。

一个月生产数据表明，batch allocation 中只有 67% 是 compute，其余 33% 看起来被占用，实际处于四种空闲状态（图 2–3）：

- **Start Idle，1%**：pod、JVM、RPC、SparkEnv、BlockManager、shuffle 和用户代码等尚在初始化。
- **Slot Idle，13%**：executor 规格按峰值固定，stage 需求变化时，多余 core/memory 不能及时归还。
- **Gap Idle，2%**：硬件异构和高优先级服务干扰制造 straggler；BSP barrier 让已完成 task 的资源等待最慢 task。
- **Stop Idle，17%**：为避免反复支付冷启动，Spark 在任务结束后继续保留 executor；默认 `executorIdleTimeout` 为 60 秒，生产中常被拉长到几分钟甚至几十分钟。

根本矛盾是：共置资源随时可能被 throttle 或 evict，最适合细粒度按需领取；传统 Spark 却以长寿命、固定规格 executor 预占资源。把资源单位下沉到 task 可以消除 slot/stop idle，但会显著放大请求量：超过 10% 的 stage 并行度高于 184，论文 trace 中单个 stage 最高有 52,383 个 task（图 7）。每个 task 还会支付原本超过 6 秒的 Java/Spark 冷启动。

## 关键观察 / 隐含假设

- **观察 1：allocation utilization 不等于 effective utilization。** 33% 资源浪费中，stop idle 和 slot idle 合计 30 个百分点，主要来自 executor 生命周期，而不是任务本身算得慢（图 3）。
  - **可能失效场景**：executor cache、broadcast state 或数据 locality 有很高复用价值时，保留资源不一定是纯浪费。
- **观察 2：task-level allocation 本身不够。** TPC-H 中只加入细粒度模型的 Spark-F 平均少用 42.68% CU，但计算 benchmark 的 task duration 标准差反而从 Spark 的 79.20 秒升到 103.40 秒；每个 task 独立申请资源，也放大了启动与节点差异（图 12–13）。
  - **设计含义**：必须同时解决控制面吞吐、干扰/异构和冷启动，不能只把 executor 换成 function。
- **观察 3：共置节点的有效算力不是静态 core 数。** Ant Group 有六个数据中心区域、多代和多厂商机器；batch 又会被 system、prod、mid workload 抢占。相同的一核配额不保证相同完成时间（图 4–5）。
  - **隐含假设**：当前节点 telemetry 和离线拟合的线性权重足以预测 task 运行期间的有效容量；突发干扰不会让 score 立即过时。
- **假设 1：task 可以近似无状态。** Driver/executor metadata 转存到远程 object storage，shuffle 继续由 Spark ShuffleManager 管理，每个 task 在独立安全容器中启动。
  - **证据强度**：中。六个月部署证明 Ant Group workload 可运行，但强 executor-local cache、自定义 native plugin 和外部状态的兼容边界没有系统枚举。
- **假设 2：约 600 ms 启动成本能被 task 时长摊薄。** 生产共置环境中 Quark 平均启动 626.53 ms，专用机器约 100 ms（图 15）。
  - **可能失效场景**：亚秒 task 或小 job。Trace replay 中确有 3.4% job 的 CU 变差，主要集中在轻量 workload。

## 核心方法

### 1. 从 executor 占有改为 task 级按需实例

Quark 建在完整 Spark 栈之上，保持 Spark SQL 用户代码不变。Spark Core 仍由 DAGScheduler 生成 task，但 Fine-GrainedTaskScheduler（FGTS）和 Fine-GrainedSchedulerBackend（FGSB）以单个 task 为资源单位；cluster scheduler 把它放到节点，每个 task 启动一个轻量 VM-based secure container。实例完成后立即释放资源（图 8）。

传统上留在 executor 内存的 broadcast/driver metadata 改从远程 object storage 按需取，shuffle 仍用原 Spark ShuffleManager。论文据此认为不再需要 rack-aware data locality，但没有单独测量网络或 shuffle locality 的代价。

### 2. Slots Ring 与显式配额保护控制面

FGSB 内的 **Slots Ring** 只容纳当前允许进入调度流水线的 task。FGTS 只在有空 slot 时 refill；FGSB 再依次 grant quota、invoke instance。Ring 大小直接限制全局并行度，把传统 task/executor 的 `O(M×N)` 匹配关键路径变成每个 scheduling event 的 `O(1)` 入队/出队，避免把数万 task 一次性打向 cluster scheduler（§4.1）。

**Quota Manager（QM）** 管理每个 project 的 overcommit 总额度。FGSB 先汇总 Ring 内 task 的 CPU/memory 需求，只有 QM grant 后才调用 serverless platform，避免大量注定失败的 API request。QM 先回收已完成 job 和超出当前 expected demand 的额度，再按显式 priority 与 submission time 分配；先保证 running job 的 required allocation，剩余资源尽量补到 expected demand，部分满足时优先给小 container 以提高吞吐。

QM 是“多副本、单 leader 决策”：leader 用内存 cache 做分配，周期性同步数据库；leader 失效检测与选举少于 1 分钟，已获 grant 的 job 不受影响，需要新 grant 的 submission 暂停。入口 QueueManager 还会在 project quota 不足时把整个 job 排队（§4.1、§5）。

### 3. 把 refill、grant、invoke 解耦

三个线程通过 Slots Ring 异步协作：Refill Thread 约每 500 ms 填空 slot；Grant Thread 约每 3 秒向 QM 请求额度，并用 resource-demand signature 跳过没有变化的重新计算；Invoke Thread 约每 500 ms 发出已经获 grant 的 task。这样 QM 一次变慢不会挡住先前已获额度的 task 启动（§4.1）。

FGTS/FGSB 与 Spark driver 一样仍是集中决策，QM 也只有一个 active leader。它们靠缩短关键路径和异步流水线扩展，而不是把 scheduling policy 完全分布化。

### 4. 先归一化有效容量，再最小化负载方差

节点 agent 从 kernel 收集各优先级 workload 的 CPU allocation/usage、[[NUMA]] topology 和 machine type。Resource Normalizer 用线性模型，把机型固有性能权重 `Wm`，以及 system/prod/mid/batch 各自 allocation 与干扰权重 `Wi`，换算成 batch 可用的统一 capacity。权重由生产性能数据通过 Bayesian optimization 离线求得；LLC contention 则由 Intel RDT、AMD QoS 等节点级机制另行限制（§4.2、公式 1）。

放置器在归一化容量上最小化各节点 `allocated / effective-total` 比例的方差（公式 2），目标是让同一批 task 更接近同时完成，减少 BSP barrier 前的 gap idle。在线服务突发时，本地 agent 根据 SLO degradation、LLC miss 等信号执行 online-first：压低 batch entitlement，并下调节点上报的可用容量。

### 5. 复用、预制和延迟加载缩短冷启动

- **State Reuse**：预先启动包含 JVM、RpcEnv、RemoteDataManager 等公共状态的暂停模板。Quark 使用 sfork/vmfork，在 fork 前暂时让 VM 只有一个 runnable thread、其余线程 quiesce，避免多线程 JVM 直接 POSIX `fork()` 的安全问题。child 启动后重绑 RpcEnv endpoint、ShuffleManager connection 和 task/application-specific setting；Spark image 更新时重建模板。
- **State Pre-Prepare**：Spark Whole-Stage Codegen 在 driver 和 executor 要编译的代码相同，因此 driver 先编译 bytecode，再随 invocation payload 发给 task，省掉 executor 端重复生成和编译。
- **State Lazy-Load**：MetricsSystem、SecurityManager 等不在第一条执行路径上必需的组件异步或按需初始化，让 task 先开始工作（§4.3、表 4）。

### 6. task 级失败隔离与放大重试

FGSB 用 startup timeout、process heartbeat 和 node watcher crash callback 三层信号判断失败（图 11）。若原因是 OOM，只给失败 task 申请更大 quota 后重试，不牵连同 executor 的其他 task。实现规模约为 FGTS/FGSB 10K 行 Java/Scala、QM 5K 行、QueueManager 3K 行 Java、cluster scheduler 1.5K 行 Go（§5）。

## 实验设计

### 受控实验与消融

端到端实验使用 30 台节点，每台为 96-core Xeon Platinum 8163、Linux 5.10；每个 task 分到 1 CPU、3 GB memory、300 GB storage，本节把 1 CPU + 3 GB 持续 1 分钟记作 1 CU。四个版本依次加入机制：Spark 3.2/Kubernetes baseline；Spark-F 加 task-level resource model；Spark-S 再加 interference-aware scheduler；Quark 最后加 fast provisioning。TPC-H 使用 1 TB 数据（SF=1000），22 个 query 各跑 20 次取均值（§6.1）。

干扰调度 microbenchmark 使用 21 台异构节点，prod 占 20%–30%，mid 与 system 各占 5%–10%。另有一个无 IO 的 800-task Fibonacci job 分析任务时间与方差。冷启动结果来自 100 次试验（§6.1–6.2）。

### 生产 replay、迁移与长期运行

24 小时 trace 含 22,532 个 Spark job、4,610 TB IO；Spark 与 Quark 分别在两套同规模的 320-node 集群 replay，每台仍为 96-core CPU、512 GB DRAM、3.52 TB SSD。随后实际迁移覆盖 57,000 张表、350,000 个 job 和 219 个 project；day 0–40 为 Spark，day 40 后完全切到 Quark。最后报告约 6,000 台服务器、600K cores 上六个月的运行数据（§6.3–6.5）。

## 实验与结果

- **TPC-H 总资源消耗。** 相对 Spark，Spark-F 每个 query 少用 6.26%–84.31% CU，平均 42.68%；Spark-S 平均 50.26%；完整 Quark 为 26.70%–87.86%，平均 56.01%（图 12）。Shuffle/memory-heavy Q3 收益最低，过滤和聚合、并行度高的 Q16 最高。
- **计算消融说明细粒度分配需要干扰调度配合。** 800-task Fibonacci 中，Spark-F、Spark-S、Quark 分别少用 25.53%、30.41%、33.06% 资源，完成时间分别改善 7.24%、8.78%、19.11%。Task duration 标准差从 Spark 的 79.20 秒变为 103.40、52.40、47.07 秒，说明细粒度分配单独使用会增加抖动（图 13）。在 21-node 异构 microbenchmark 中，干扰感知放置又把 70% allocation 下的平均 task time 从 250 降到 191 秒、tail ratio 从 1.76 降到 1.64；满载时分别从 306 降到 286 秒、2.75 降到 2.22（图 14）。
- **启动仍不是零成本。** Spark executor 平均启动 6078 ms，Quark task 为 626.53 ms，减少 89.7%；专用机器约 100 ms。剩余时间来自低优先级共置调度、driver/shuffle 连接、task code/plugin 加载等 Spark 特有状态（图 15）。
- **同 trace replay 显示 aggregate 收益。** Quark 总 CU 比 Spark 低 26.5%，大于等于 1K CU 的各档 job 节省 22%–29%；总执行时间从 4501 小时降到 3501 小时，减少 22.4%。3.4% job 的 CU 反而升高，主要是冷启动占比高的轻量档；该档只占总 CU 的 1.0%（图 17–18）。
- **实际迁移和六个月运行证明规模，但迁移不是随机对照。** 切换后每 job 归一化资源消耗降低 37.37%；stage 内最长/最短 task 比约从 20 倍降到 8 倍，“最长 task 超过 stage 平均值 5 倍”的不平衡 stage 比例约从 15% 降到 2%（图 19–20）。§6.5 进一步报告日均 902K job、峰值 1.27M，日均 IO 105.4 PB，job success rate 99.11%；集群 overcommit ratio 为 1.592–1.803，实际利用率 41.7%–61.4%。Function invocation 平均 534/s、峰值 2130/s，HTTP 200 比例为 98.55%，主要非成功响应是 burst 时的 429 rate limit（图 21–23）。
- **失败没有消失，只是隔离粒度更小。** 六个月记录 1.31M 次失败：用户 SQL 44.0%、权限 12.5%、UDF/environment 8.9%，论文合计 user-attributable 为 65.3%；storage/tunnel IO 为 9.5%，OOM 为 7.8%，driver/coordinator 为 7.5%，shuffle/compute engine 为 6.0%（表 6）。OOM task 加资源重试后 94.7% 成功；剩余 5.3% 多为严重 data skew，失败 retry 占全部 retry CU 的 35.2%（§7）。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 共置 Spark 的分配资源有三分之一未做有效计算 | 图 2–3：compute 67%，四类 idle 共 33% | Ant Group 一个月 telemetry；“有效计算”由内部分类定义 | 强 |
| task-level 分配是主要资源收益来源，但单独使用会放大波动 | 图 12–13：Spark-F 平均少 42.68% CU，task 标准差 79.20→103.40 秒 | 30 节点 TPC-H 与一个无 IO 合成 job | 强 |
| 完整 Quark 能降低生产型 workload 的资源成本 | 图 17–18：双 320-node replay 少 26.5% CU、22.4% 总时间 | 单日、单 project trace；两套同规格集群 | 强 |
| 生产迁移后资源和 stage 长尾改善 | 图 19–20：37.37% 资源节省，15%→2% 不平衡 stage | 前后时间序列，不是同 workload 同时 A/B | 中 |
| 架构能在大规模持续运行 | 图 21–23：600K cores、六个月、日均 902K jobs、99.11% job success | 单一企业技术栈；artifact 与原始数据不公开 | 中 |

## 批判性分析

### 论证链条

论文先把浪费分成 start/slot/gap/stop 四类，再让 Spark-F、Spark-S、Quark 依次加入细粒度分配、干扰调度和快速启动，消融能对应问题与机制；双集群 replay 和长期部署又补上生产证据。这条链比只报告 aggregate utilization 更有解释力。标题中的“serverless”应理解为 task 级按需 provisioning；系统仍依赖常驻的 QueueManager、QM、Spark driver、预热模板、object storage 和 shuffle service，并不是完全无状态的 FaaS。

### 假设压力测试

约 626 ms 冷启动对分钟级 task 很小，对亚秒 task 却可能超过计算本身，3.4% replay regression 已显示这个边界。强依赖 executor cache、rack locality 或大量 shuffle 的 job 也可能失去共享状态收益；TPC-H Q3 的较小改善与此一致。Capacity score 是线性且主要基于当前 allocation/机型，面对突然的在线流量或新硬件可能失准；sfork template 若含 native thread、随机状态、credential 或未知 plugin，复制安全性也不能由单线程 quiesce 自动保证。

### 实验可信度

30-node benchmark、21-node 干扰实验、两套 320-node trace replay、真实迁移和六个月运行形成多层证据，内部消融尤其有价值。局限是 Spark-F/Spark-S 都是作者自建版本，没有与 Ditto、MetaQ 等外部 serverless analytics 在同一环境直接比较；生产数据与代码不公开。迁移前后 workload 数量还在变化，因此 37.37% 不如双集群 replay 的 26.5% 具有因果确定性。

论文的统计口径也需要谨慎。画像中的 1 CU 是 1 CPU + 4 GB 持续 1 小时，TPC-H 章节的 1 CU 却是 1 CPU + 3 GB 持续 1 分钟；只能在各自实验内比较。摘要/引言写每天 350K job、7.5–10 PB 数据，§6.5 又写六个月日均 902K job、105.4 PB IO，可能分别指迁移 workload 与完整运行面，但正文没有明确对齐。`99.11% job success` 与 `98.55% HTTP 200` 也对应不同层级，不能互换。

### 系统性缺陷

Quark 没有消除复杂性，而是把它从 executor 搬到 Slots Ring、单-leader QM、模板生命周期、capacity telemetry、远程 metadata 和 shuffle service。Leader failover 期间新 quota 最长暂停约一分钟，论文没有故障注入数据；也没有给 control plane 极限吞吐曲线。Shuffle/compute engine 仍占 6.0% 失败，丢一个 shuffle partition 可级联重算 upstream stage。OOM 放大重试虽有 94.7% 成功率，剩余 data-skew 长尾仍消耗明显 retry CU。因而“near-zero waste”更适合看作方向性目标，而不是实测的严格结论。

## 局限与后续工作

- **局限 1**：深度依赖 Ant Group secure container、cluster scheduler、远程 metadata 和受控 Spark image，跨平台移植成本未量化。
- **局限 2**：轻量 task、shuffle-heavy query、强 cache/locality workload 的 break-even 边界没有完整给出。
- **局限 3**：QM 和 Spark 侧决策仍有单 active leader，恢复窗口与极限吞吐缺少 fault-injection 和压力曲线。
- **局限 4**：生产 scale、CU、job success 与 invocation success 有多套口径，跨章节不可直接相加或比较。
- **后续工作 1**：按 task duration、shuffle bytes、executor-cache reuse 和 cold-start ratio 分桶，画出 Quark 相对 Spark 的 CU 与 P99 break-even surface。
- **后续工作 2**：对 QM 注入 leader crash、database lag 和 burst grant request，报告新 job stall、已运行 task 影响与恢复后 quota 一致性。
- **后续工作 3**：向 template 注入多线程 native library、credential rollover、随机数状态和 image rolling upgrade，验证 clone 安全性与故障隔离。
- **后续工作 4**：把 user-provided skew/memory hint 与历史预测组合，以一次重试成功率、浪费 CU 和 P99 stage time 衡量剩余 OOM 长尾。
- **后续工作 5**：在同一公开 trace 上与外部 serverless Spark 系统及强优化 Spark baseline 比较，统一 CU 定义并公开 job-level regression 分布。

## 相关

- **相关概念**：[[Serverless]]、[[NUMA]]
- **同会议**：[[OSDI-2026]]
