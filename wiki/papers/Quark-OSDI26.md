---
type: paper
name: Quark
full_title: "Stop Pretending to be Busy: A Case for Serverless Paradigms in Co-located Batch Workloads (Operational Systems)"
authors: [Xiaohu Chai, Jianfeng Tan, Congsi Yuan, Bowen Yang, Hao Dai, Tongkai Yang, Chao Huang, Dong Du, Yu Chen]
venue: OSDI
year: 2026
tags: [serverless, batch-processing, spark, colocation, scheduling]
source_pdf: "[[osdi26-chai.pdf]]"
source_md: "[[osdi26-chai]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 别再假装忙碌：共置批处理的 [[Serverless|Serverless]] 化（OSDI 2026）

> **原题**：Stop Pretending to be Busy: A Case for Serverless Paradigms in Co-located Batch Workloads (Operational Systems)

> **一句话总结**：Ant Group trace 显示 overcommit 虽收回 26.8% CPU，Spark 所分配资源却仅 67% 用于有效计算；Quark 以 task 级 serverless 分配、干扰感知调度和 fork-based 快速启动消除四类 idle，生产迁移后节省 37.37% 资源，并把不平衡 stage 比例从 15% 降至 2%。

## 问题与动机

云厂商常把低优先级 [[Apache-Spark|Spark]] batch job 与高优先级在线服务共置，通过 overcommit 收割空闲资源。Ant Group 的在线服务实际只用 22.0% CPU，共置额外利用 26.8%，但 allocation 看似繁忙并不等于有效计算：一个月 trace 中 batch 资源有 33% 落在等待、启动或持有状态。

论文把浪费拆成四类：executor 固定规格造成 slot idle；硬件异构和在线干扰造成 straggler 与 gap idle；JVM/SparkEnv 初始化造成 start idle；为摊薄冷启动而长期保留 executor 又造成 stop idle。根因是长寿命、粗粒度 Spark executor 与动态、可抢占的共置资源池不匹配。

## 关键观察 / 隐含假设

- **观察 1：高 allocation 掩盖低 effective utilization。** 生产 trace 中 Spark 只有 67% allocated CU 用于有效计算，四类 idle 各自来自不同生命周期阶段（图 2–3）。
  - **依赖假设**：论文对“有效计算”的 telemetry 分类准确，等待状态没有必要的系统价值。
  - **可能失效场景**：I/O-bound job 或缓存复用强的 executor，保留资源可能减少后续数据搬移，不能简单视作浪费。
- **观察 2：task-level allocation 能消除 slot/stop idle，却会放大 control-plane 和启动成本。** Spark-F 已平均节省 42.68% CU，但 task time 方差反而从 79.2s 增至 103.4s（图 12–13）。
  - **依赖假设**：异步控制面、配额限制和快速 clone 可承受数十万 task 的短生命周期。
  - **可能失效场景**：大量亚秒任务、频繁镜像变化或不可安全 fork 的 native/plugin 状态。
- **观察 3：共置环境中的“机器容量”是时间变化的有效算力，而非静态 core 数。** 干扰感知 score 与 variance-optimal placement 把同 stage 的完成时间对齐（§4.2）。
  - **依赖假设**：节点 metric 能预测未来一个 task 的速度，且数据 locality/网络成本次于算力方差。
- **假设 1：task 级进程隔离不会破坏 Spark 语义和共享状态收益。**
  - **证据强度**：中；六个月生产规模支持可用性，但 shuffle、cache、UDF 与版本兼容的完整语义边界未形式化。

## 核心方法

Quark 把 executor 占有模式改为每个 task 按需创建独立 secure-container instance。Slots Ring 限制每个 job/stage 的可运行并行度，Quota Manager 统一执行 overcommit 上限；资源请求、task dispatch 与回收异步化，避免 task 数增长直接阻塞 central scheduler。这回应 task-level granularity 对 control plane 的压力。

干扰感知调度器把 CPU 型号、频率、在线负载与历史 task runtime 等转成统一 capacity score，再以最小化同一 stage 完成时间方差为目标放置 task。目标不是让每个 task 单独最快，而是减少 [[Bulk-Synchronous-Parallel|BSP]] barrier 前的 gap idle。

快速 provisioning 预先准备含 JVM、SparkEnv 和公共依赖的单线程安全 template，通过 `fork()` 继承已初始化状态；child 重新绑定 RpcEnv、ShuffleManager 等 task/application 特定连接。非关键 MetricsSystem、安全组件和依赖异步或 lazy-load，从 critical path 移除（表 4）。三层 failure detection 覆盖启动 timeout、heartbeat 与 crash callback，OOM task 可提高资源后原地重试。

## 设计取舍

- **精细分配换更高调度频率**：task-level resource 回收消除 idle，但每个 task 都进入资源控制、启动和隔离路径。
- **fork 速度换模板约束**：预热状态将启动从 6,078ms 降到 626.53ms，却需要 quiesce 多线程、重绑连接，并在 Spark/image 更新后重建模板。
- **完成时间同步换局部最优/数据 locality**：variance-optimal placement 有利于 BSP stage，但可能跳过数据更近或单 task 更快的节点。
- **边界条件**：计算密集、task 足够长、异构/干扰明显时收益最大；Q3 这类 shuffle/memory-heavy query 和少于 1K CU 的轻 job 收益小，3.4% replay job 出现 CU regression。

## 实验与结果

- TPC-H SF=1000、22 queries、20 次均值下，Quark 相对 Spark 的 CU 降低 26.70%–87.86%，平均 56.01%；I/O-heavy Q3 最低，易并行 Q16 最高（图 12）。
- 800-task Fibonacci compute benchmark 中，Quark CU 降 33.06%、completion time 加速 19.11%，task duration 标准差从 Spark 的 79.20s 降至 47.07s（图 13）。
- 21-node 异构共置 microbenchmark 中，调度器使平均 task time 改善 18%–33%，tail ratio 在 allocation ratio 70%/100% 下由 1.76/2.75 降至 1.64/2.22（图 14）；启动耗时由 6,078ms 降到 626.53ms，少 89.7%（图 15）。
- 22,532-job、4,610 TB 的 24 小时 trace 在两套 320-node 集群 replay 时，总 CU 低 26.5%、总执行时间由 4,501h 降至 3,501h（22.4%）；3.4% job 回退，集中于只占总 CU 1%的轻量 tier（图 16–18）。
- 生产切换后每 job 资源降低 37.37%，tail ratio 约从 20 倍降至 8 倍，不平衡 stage 从 15% 降至 2%（图 19–20）。六个月部署覆盖约 6,000 servers/600K cores，日均 902K jobs、105.4 PB I/O，job success 99.11%，节省超过 100K cores（图 21–23）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Spark 共置资源存在可观的非有效占用 | 图 2–3：33% allocation 为四类 idle | Ant Group 一个月生产 cluster，论文自定义 effective CU | 强 |
| Quark 显著降低 batch 资源成本 | 图 12：TPC-H 平均 56.01%；图 17：trace replay 26.5% | SF=1000 与 24h production trace、两套 320-node cluster | 强 |
| 干扰感知调度降低 stage 长尾 | 图 14、20：生产不平衡 stage 15%→2% | Ant Group 异构共置环境 | 强 |
| 架构能在 hyperscale 长期运行 | 图 21：六个月日均 902K jobs、99.11% success | 单一企业栈与 secure-container 平台 | 中 |

## 批判性分析

### 论证链条

论文先用 trace 拆出 idle，再通过 Spark-F/Spark-S 分离 fine-grained scheduling 与 interference-aware placement，最后以 replay 和长期部署验证组合，论证链条很强。标题中的 serverless 主要指 task 级按需 provisioning；它仍依赖持久控制面、预热模板和外部 shuffle/data service，不等同于完全无状态 FaaS。

### 假设压力测试

当 task 短于 600ms 冷启动、强依赖 executor cache，或 shuffle/data locality 主导时，每 task instance 的固定成本会吞噬收益。capacity score 若面对突发在线流量会过时；fork template 遇到不安全 native thread、随机数、credential 或用户 UDF 也可能复制错误状态。论文证明其自家受控 runtime 可行，没有证明任意 Spark ecosystem plugin 都兼容。

### 实验可信度

TPC-H、合成 compute、24h trace replay、40-day migration 与六个月 operation 构成罕见的多层证据；拆分 ablation 与等规模双 cluster replay 也较公平。缺口是无公开 trace/artifact、Spark 配置与同等投入优化的 serverless Spark baseline 较少，生产成功率口径与 Spark 对照不完全一致。

### 系统性缺陷

Quark 把复杂性从 executor 搬到模板生命周期、Quota Manager、FGSB、capacity telemetry 和外部 shuffle。论文报告 shuffle failure 仍占 6.0%，数据丢失可级联重算 upstream stage；HTTP 200 success 为 98.55%，突发时 429 rate limiting 明显。OOM 重试成功 94.7%，但失败 retry 消耗了 retry CU 的 35.2%，data skew 仍未解决。

## 局限与后续工作

- **局限 1**：系统深度绑定 Ant Group secure container、远程数据/ShuffleManager 与受控 Spark image，跨 Kubernetes/Spark 发行版移植成本未量化。
- **局限 2**：轻量 job、I/O-heavy query 和 executor cache 受益边界有限，生产 aggregate 节省不能代表每类 workload。
- **后续工作 1**：按 task duration、shuffle bytes、cache reuse 和 cold-start ratio 建立 break-even surface，公开每个 bucket 的 CU/latency 回退率。
- **后续工作 2**：对 template 注入多线程 native library、credential rollover 和 image upgrade，验证 clone 安全性与 rolling regeneration 的失败隔离。
- **后续工作 3**：将 user-provided skew/memory hint 与历史预测组合，以一次重试成功率、浪费 CU 和 P99 stage time 客观评估剩余 5.3% OOM 长尾。

## 相关

- **相关概念**：[[Serverless-Computing]]、[[Workload-Colocation]]、[[Straggler-Mitigation]]、[[Resource-Overcommitment]]
- **同类系统**：[[Apache-Spark]]、[[Kubernetes]]、[[Celeborn]]
- **同会议**：[[OSDI-2026]]
