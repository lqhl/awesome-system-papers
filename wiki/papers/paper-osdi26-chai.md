# Quark（OSDI 2026）

> **原题**：Stop Pretending to be Busy: A Case for Serverless Paradigms in Co-located Batch Workloads

> **一句话总结**：Ant Group 测量显示共置 Spark 批处理约 33% 资源处于非有效状态；Quark 将资源粒度降至 task，结合配额控制、干扰感知调度和快速启动，在生产中节省 37.37% 资源，并将长尾 stage 比例从约 15% 降至 2%。

## 问题与方法

传统 Spark 使用长期存在、固定规格的 executor，不适合与在线服务共置的过量分配环境。论文将浪费拆为 slot idle、gap idle、start idle 和 stop idle。Quark 以 task 为资源申请和释放单位，用 Slots Ring 控制并行度，Quota Manager 管理全局配额；Resource Normalizer 根据硬件异构和在线干扰计算有效容量，再以最小化分配比例方差的策略放置任务（图 8、§4）。

任务启动通过预初始化模板、sfork、driver 预生成 Codegen 状态和 lazy-load 降低成本。Startup Monitor、heartbeat 与 crash callback 提供 task 级故障检测；OOM 可只扩大失败 task 的资源后重试（§5）。

## 观察与假设

- 生产数据中约 33% 分配资源处于等待或初始化等非有效状态（图 2、图 3）。这依赖任务可独立运行，且 shuffle 与状态可由远端服务承载。
- 异构机器和在线干扰制造 straggler，BSP stage 必须等待慢任务（§2.2）。模型假设节点指标足以预测批处理有效容量。
- Spark executor 启动约 6078 ms，task 级实例化必须依赖状态复用才能成立（图 15）。

## 实验与结果

- TPC-H、1 TB 数据、30 节点上，Quark 平均减少 56.01% CU，范围为 26.70%–87.86%（图 12）。
- 800-task 计算负载中，资源消耗减少 33.06%，完成时间加速 19.11%（图 13）。
- 异构集群微基准中平均 task 时间降低 18%–33%，尾时长比从 2.75× 降至 2.22×（图 14）。
- 22,532 个生产 job replay 中 CU 降低 26.5%，执行时间从 4501 h 降至 3501 h（图 17、图 18）。
- 真实迁移覆盖 350,000 个 job，资源节省 37.37%，尾时长比约从 20× 降至 8×，不平衡 stage 比例从约 15% 降至 2%（图 19、图 20）。
- 六个月运营平均每天 902K jobs，成功率 99.11%；部署约 600K CPU cores（图 21、图 22）。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| task 级管理减少资源空转 | TPC-H CU 平均降低 56.01%，图 12 | 30 节点、1 TB | 强 |
| 干扰感知调度减少尾部 | 2.75×→2.22×，图 14 | 21 节点合成负载 | 中 |
| 能够生产运行 | 902K jobs/day、99.11%，图 21 | Ant Group 六个月 | 强 |

## 批判性分析

逐步基线 Spark-F、Spark-S、Quark 能隔离主要设计贡献。生产迁移也支持系统可运维性的判断。但实验缺少控制面 CPU、配额服务吞吐和远端 I/O 成本；轻量 job 中有 3.4% 出现 CU 回归（§6.3），说明 626.53 ms 的启动成本仍限制适用范围。Resource Normalizer 依赖离线权重，跨机器代际、算子和租户分布的漂移风险未充分评估。单 leader Quota Manager 的故障恢复窗口少于 1 分钟，影响尚未量化。

## 局限与后续工作

- 按 task 时长和 I/O 类型测量收益交叉点，并报告控制面开销。
- 在数据倾斜、强数据局部性和 shuffle 故障注入下评估尾延迟与重试放大。
- 补充与 stage-level resource management 及 serverless analytics 系统的直接对照。

## 相关

- **相关概念**：[[Serverless]]、[[Resource Overcommitment]]、[[Straggler]]
- **同类系统**：[[Ditto]]、[[SKernel]]
